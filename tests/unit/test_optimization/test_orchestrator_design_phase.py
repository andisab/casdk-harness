"""Tests for the DESIGN phase in the multi-resource orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from harness.optimization.multi_resource_orchestrator import (
    AGENT_DESIGN,
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import MultiResourceState, OptimizationPhase


class TestDesignPhaseConstants:
    def test_agent_design_constant_exists(self) -> None:
        assert AGENT_DESIGN == "cgf-agents:cgf-resource-architect"


class TestCreateInitialState:
    """State should start at RESEARCH with NO pre-populated resources."""

    def test_initial_state_starts_at_research(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._spec = MagicMock()
        orchestrator._spec.source_path = "SPEC.md"
        orchestrator._spec.spec_type.name = "PLUGIN"
        orchestrator._spec.content_hash = "abc123"
        orchestrator._spec.proposed_agents = [MagicMock(name="agent1")]
        orchestrator._spec.proposed_skills = []
        orchestrator._spec.proposed_commands = []
        orchestrator._spec.proposed_mcp_tools = []
        orchestrator._spec.proposed_mcp_servers = []

        state = orchestrator._create_initial_state()
        assert state.current_phase == OptimizationPhase.RESEARCH
        # Resources should NOT be pre-populated
        assert len(state.resources) == 0


class TestLoadResourcePlan:
    """Verify resource-plan.yaml parsing populates state."""

    def test_load_plan_adds_resources(self, tmp_path: Path) -> None:
        plan = {
            "plan_version": 1,
            "spec_hash": "abc123",
            "rationale": "Two agents and one tool",
            "resources": [
                {
                    "path": "agents/iac-analyzer.md",
                    "type": "agent",
                    "purpose": "Analyze IaC",
                    "capabilities_served": ["cap_1"],
                    "depends_on": ["tools/tf-parser.py"],
                    "priority": 1,
                },
                {
                    "path": "tools/tf-parser.py",
                    "type": "mcp_tool",
                    "purpose": "Parse HCL",
                    "capabilities_served": ["cap_1"],
                    "depends_on": [],
                    "priority": 0,
                },
            ],
            "generation_order": ["tools/tf-parser.py", "agents/iac-analyzer.md"],
            "rejected_proposals": [],
        }
        plan_file = tmp_path / "resource-plan.yaml"
        with open(plan_file, "w") as f:
            yaml.dump(plan, f)

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._state = MultiResourceState(
            spec_path="SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc123",
            current_phase=OptimizationPhase.DESIGN,
        )

        orchestrator._load_resource_plan(plan_file)

        assert len(orchestrator._state.resources) == 2
        assert "agents/iac-analyzer.md" in orchestrator._state.resources
        assert "tools/tf-parser.py" in orchestrator._state.resources
        agent = orchestrator._state.resources["agents/iac-analyzer.md"]
        assert agent.resource_type == "agent"
        assert agent.depends_on == ["tools/tf-parser.py"]

    def test_load_plan_respects_generation_order(self, tmp_path: Path) -> None:
        plan = {
            "plan_version": 1,
            "rationale": "ordered test",
            "resources": [
                {
                    "path": "agents/a.md",
                    "type": "agent",
                    "purpose": "A",
                    "capabilities_served": [],
                    "depends_on": ["tools/b.py"],
                    "priority": 1,
                },
                {
                    "path": "tools/b.py",
                    "type": "mcp_tool",
                    "purpose": "B",
                    "capabilities_served": [],
                    "depends_on": [],
                    "priority": 0,
                },
            ],
            "generation_order": ["tools/b.py", "agents/a.md"],
        }
        plan_file = tmp_path / "resource-plan.yaml"
        with open(plan_file, "w") as f:
            yaml.dump(plan, f)

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._state = MultiResourceState(
            spec_path="SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.DESIGN,
        )

        orchestrator._load_resource_plan(plan_file)

        # Resources dict preserves insertion order (Python 3.7+)
        paths = list(orchestrator._state.resources.keys())
        assert paths == ["tools/b.py", "agents/a.md"]

    def test_load_plan_invalid_file_raises(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "resource-plan.yaml"
        plan_file.write_text("invalid: yaml\nno_resources: true")

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._state = MultiResourceState(
            spec_path="SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.DESIGN,
        )

        with pytest.raises(ValueError, match="Invalid resource plan"):
            orchestrator._load_resource_plan(plan_file)


class TestDesignTimeout:
    """Verify design_timeout field on MultiResourceConfig."""

    def test_default_design_timeout(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        assert config.design_timeout == 900

    def test_custom_design_timeout(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path, design_timeout=1200)
        assert config.design_timeout == 1200


class TestPipelineDesignPhaseOrdering:
    """Verify DESIGN is between RESEARCH and QA in _run_pipeline."""

    def test_research_advances_to_design(self, tmp_path: Path) -> None:
        """After RESEARCH phase, pipeline should advance to DESIGN."""
        config = MultiResourceConfig(
            workspace_dir=tmp_path,
            skip_research=True,
        )
        orchestrator = MultiResourceOrchestrator(config)
        orchestrator._state = MultiResourceState(
            spec_path="SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.RESEARCH,
        )
        orchestrator._progress = MagicMock()
        orchestrator._spec = MagicMock()

        # Track phase transitions
        transitions: list[str] = []

        def tracking_advance(next_phase: OptimizationPhase) -> None:
            transitions.append(next_phase.name)
            # Stop pipeline by setting to COMPLETE after first advance
            orchestrator._state.current_phase = OptimizationPhase.COMPLETE

        orchestrator._advance_phase = tracking_advance  # type: ignore[assignment]

        import asyncio

        asyncio.run(orchestrator._run_pipeline())

        assert transitions[0] == "DESIGN"
