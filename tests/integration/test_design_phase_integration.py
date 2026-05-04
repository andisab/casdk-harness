"""Integration test for DESIGN phase in multi-resource pipeline.

Tests the full flow: SPEC.md -> research (skipped) -> resource-architect (mocked) ->
resource-plan.yaml -> state populated with resources.

Cost: Free (no API calls, all agent responses are mocked)
Duration: <1 second
"""

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import OptimizationPhase


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with SPEC.md and mock research findings."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # SPEC.md -- must be detected as multi-resource (PLUGIN type).
    # Requires "## Capabilities" section for detect_spec_type to return PLUGIN.
    (ws / "SPEC.md").write_text(dedent("""\
        # IaC Compliance Team

        ## Purpose
        Infrastructure compliance analysis

        ## Capabilities
        - **Terraform Analysis** - Parse and validate Terraform files
        - **Policy Checking** - Check against compliance policies

        ## Constraints
        - Must support Terraform and CloudFormation
    """))

    # Mock research findings (would be created by RESEARCH phase)
    research_dir = ws / "research" / "notes"
    research_dir.mkdir(parents=True)
    (research_dir / "terraform_findings.yaml").write_text("findings: [test]")
    (ws / "research" / "eval_criteria.yaml").write_text("criteria: [test]")

    return ws


def _make_plan_yaml(workspace: Path) -> str:
    """Create a resource-plan.yaml and return the mock agent response.

    Writes the plan file to disk (simulating what the agent would do),
    then returns the text response the agent would emit.
    """
    plan = {
        "plan_version": 1,
        "spec_hash": "test",
        "rationale": "Two resources needed for compliance analysis",
        "resources": [
            {
                "path": "agents/iac-analyzer.md",
                "type": "agent",
                "purpose": "Analyze IaC for compliance",
                "capabilities_served": ["terraform_analysis", "policy_checking"],
                "depends_on": [],
                "priority": 0,
            },
            {
                "path": "skills/compliance-rules/SKILL.md",
                "type": "skill",
                "purpose": "Compliance rule knowledge base",
                "capabilities_served": ["policy_checking"],
                "depends_on": [],
                "priority": 0,
            },
        ],
        "generation_order": [
            "skills/compliance-rules/SKILL.md",
            "agents/iac-analyzer.md",
        ],
        "rejected_proposals": [],
    }

    plan_path = workspace / "resource-plan.yaml"
    with open(plan_path, "w") as f:
        yaml.dump(plan, f)

    return dedent("""\
        Analyzed SPEC and research findings.
        Designed architecture with 2 resources.

        [DESIGN_COMPLETE]
        resource_plan_path: resource-plan.yaml
        total_resources: 2
    """)


async def _setup_orchestrator(
    workspace: Path,
    *,
    skip_research: bool = True,
    skip_qa: bool = True,
) -> MultiResourceOrchestrator:
    """Initialize orchestrator through _initialize and create initial state.

    This calls the real _initialize method which parses SPEC.md, creates
    a ProgressManager, and sets up the QualityEvaluator, then creates
    the initial state so the orchestrator is ready for _delegate_design.
    """
    config = MultiResourceConfig(
        workspace_dir=workspace,
        skip_research=skip_research,
        skip_qa=skip_qa,
    )
    orchestrator = MultiResourceOrchestrator(config)
    await orchestrator._initialize()
    orchestrator._state = orchestrator._create_initial_state()
    return orchestrator


async def test_design_phase_populates_state_from_plan(workspace: Path) -> None:
    """DESIGN phase should parse resource-plan.yaml and populate state."""
    mock_response = _make_plan_yaml(workspace)

    orchestrator = await _setup_orchestrator(workspace)

    with patch(
        "harness.subagent.call_agent_simple",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        # Verify state starts empty
        assert len(orchestrator._state.resources) == 0

        # Advance to DESIGN (skip RESEARCH)
        orchestrator._state.current_phase = OptimizationPhase.DESIGN
        await orchestrator._delegate_design()

        # Verify resources populated
        assert len(orchestrator._state.resources) == 2
        assert "agents/iac-analyzer.md" in orchestrator._state.resources
        assert "skills/compliance-rules/SKILL.md" in orchestrator._state.resources
        assert orchestrator._state.resource_plan_path == "resource-plan.yaml"

        # Verify resource types
        agent = orchestrator._state.resources["agents/iac-analyzer.md"]
        assert agent.resource_type == "agent"
        skill = orchestrator._state.resources["skills/compliance-rules/SKILL.md"]
        assert skill.resource_type == "skill"

        # Verify generation order (dict preserves insertion order in Python 3.7+)
        paths = list(orchestrator._state.resources.keys())
        assert paths[0] == "skills/compliance-rules/SKILL.md"  # skills first
        assert paths[1] == "agents/iac-analyzer.md"


async def test_design_phase_handles_missing_plan_file(workspace: Path) -> None:
    """DESIGN phase should raise if agent emits signal but no plan file exists."""
    # Response contains signal, but we do NOT create the plan file on disk
    mock_response = "[DESIGN_COMPLETE]\nresource_plan_path: resource-plan.yaml"

    orchestrator = await _setup_orchestrator(workspace)

    with patch(
        "harness.subagent.call_agent_simple",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        orchestrator._state.current_phase = OptimizationPhase.DESIGN

        with pytest.raises(ValueError, match="resource-plan.yaml"):
            await orchestrator._delegate_design()


async def test_design_phase_handles_no_signal(workspace: Path) -> None:
    """DESIGN phase should handle agent response with no completion signal."""
    mock_response = "I analyzed the SPEC but something went wrong."

    orchestrator = await _setup_orchestrator(workspace)

    with patch(
        "harness.subagent.call_agent_simple",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        orchestrator._state.current_phase = OptimizationPhase.DESIGN

        # Should not raise -- just log warning. State remains unchanged.
        await orchestrator._delegate_design()
        assert len(orchestrator._state.resources) == 0


async def test_design_phase_saves_state_to_disk(workspace: Path) -> None:
    """DESIGN phase should persist state via ProgressManager after completion."""
    mock_response = _make_plan_yaml(workspace)

    orchestrator = await _setup_orchestrator(workspace)

    with patch(
        "harness.subagent.call_agent_simple",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        orchestrator._state.current_phase = OptimizationPhase.DESIGN
        await orchestrator._delegate_design()

    # Verify state was persisted to disk
    state_path = workspace / "sessions" / "optimization-state.json"
    assert state_path.exists(), "optimization-state.json should be saved after DESIGN"

    # Load the persisted state and verify it matches in-memory state
    import json

    with open(state_path) as f:
        persisted = json.load(f)

    assert len(persisted["resources"]) == 2
    assert persisted["resource_plan_path"] == "resource-plan.yaml"
