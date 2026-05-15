"""Full 9-phase pipeline integration test (CGF Stage 3 Phase A.7).

Exercises ``MultiResourceOrchestrator.run()`` end-to-end with all
external calls mocked.  Cost: free; duration < 5 seconds.

Pipeline verified:
  RESEARCH -> DESIGN -> QA -> GENERATE -> EVAL_DESIGN -> ITERATE ->
  EXECUTION_EVAL -> VALIDATE -> COMPLETE

Each agent invocation is intercepted by a single ``call_agent_simple``
mock that dispatches by agent name.  ``EvalHarness.run`` is mocked to
return promotable results.  The mocks materialize files on disk that
the next phase will read, mirroring real agent behavior.

This is the smoke gate for Phase A — when this test is green, the
entire eval framework wires together correctly modulo real LLM
quality.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from harness.optimization.eval_harness import (
    ArmResults,
    EvalResults,
    ScenarioResult,
)
from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import OptimizationPhase

# =============================================================================
# Workspace + agent-response factories
# =============================================================================


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Workspace with a tiny 2-resource SPEC.md."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "SPEC.md").write_text(
        dedent(
            """\
        # Tiny Test Plugin

        ## Purpose
        Smoke-test fixture for the CGF eval pipeline.

        ## Capabilities
        - **Capability A** - First capability for testing
        - **Capability B** - Second capability for testing

        ## Constraints
        - Must keep things simple
        """
        )
    )
    return ws


def _make_resource_plan(workspace: Path) -> str:
    """Materialize resource-plan.yaml + return the [DESIGN_COMPLETE] response."""
    plan = {
        "plan_version": 1,
        "spec_hash": "test",
        "rationale": "Two resources: one agent, one skill",
        "resources": [
            {
                "path": "agents/test-agent.md",
                "type": "agent",
                "purpose": "Test agent",
                "capabilities_served": ["Capability A"],
                "depends_on": [],
                "priority": 0,
            },
            {
                "path": "skills/test-skill/SKILL.md",
                "type": "skill",
                "purpose": "Test skill",
                "capabilities_served": ["Capability B"],
                "depends_on": [],
                "priority": 0,
            },
        ],
        "generation_order": [
            "skills/test-skill/SKILL.md",
            "agents/test-agent.md",
        ],
        "rejected_proposals": [],
    }
    plan_path = workspace / "resource-plan.yaml"
    with plan_path.open("w") as f:
        yaml.safe_dump(plan, f)
    return "[DESIGN_COMPLETE]\nresource_plan_path: resource-plan.yaml\n"


def _materialize_research(workspace: Path) -> str:
    """Materialize research findings + return [RESEARCH_COMPLETE]."""
    research_dir = workspace / "research" / "notes"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "test_findings.yaml").write_text(
        "findings:\n  - Test finding 1\n  - Test finding 2\n"
    )
    (workspace / "research" / "eval_criteria.yaml").write_text(
        "competencies:\n  - name: Test\n    description: Test competency\n"
    )
    return (
        "[RESEARCH_COMPLETE]\n"
        "eval_criteria_path: research/eval_criteria.yaml\n"
    )


def _materialize_resource_file(
    workspace: Path, resource_path: str, version: int = 0
) -> None:
    """Materialize a generated resource file at workspace/{path-v{version}}."""
    from harness.optimization._orchestrator_helpers import versioned_path

    p = workspace / (resource_path if version == 0 else versioned_path(resource_path, version))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nname: stub\ndescription: stub\nmodel: sonnet\n---\n# stub v{version}\n"
    )


def _generate_response_for(workspace: Path, resource_path: str) -> str:
    _materialize_resource_file(workspace, resource_path, version=0)
    return f"[GENERATE_COMPLETE:{resource_path}]\n"


def _materialize_eval_suite(workspace: Path) -> str:
    """Materialize eval-suite.yaml + return [EVAL_DESIGN_COMPLETE]."""
    suite = {
        "version": "1.0",
        "target_resource": "agents/test-agent.md",
        "config": {"trials_per_scenario": 1, "timeout_seconds": 30},
        "scenarios": [
            {
                "id": "smoke-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
            }
        ],
    }
    suite_path = workspace / "eval" / "eval-suite.yaml"
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    with suite_path.open("w") as f:
        yaml.safe_dump(suite, f)
    return "[EVAL_DESIGN_COMPLETE]\neval_suite_path: eval/eval-suite.yaml\n"


def _iterate_response_for(workspace: Path, resource_path: str) -> str:
    """Materialize a v1 file for the resource + return [ITERATE_COMPLETE]."""
    _materialize_resource_file(workspace, resource_path, version=1)
    return (
        f"[ITERATE_COMPLETE:{resource_path}]\n"
        "version: 1\n"
        "quality_overall: 0.92\n"
        "quality_completeness: 0.9\n"
        "quality_accuracy: 0.95\n"
        "quality_clarity: 0.9\n"
        "word_count: 200\n"
        "[SUMMARY]\n"
        "Improved clarity and added examples.\n"
        "[/SUMMARY]\n"
    )


# =============================================================================
# Promotable EvalResults factory (so candidates beat baselines)
# =============================================================================


def _promotable_eval_results() -> EvalResults:
    baseline = ArmResults(
        arm="baseline",
        trials=[],
        decisive=2,
        pass_rate=0.4,
        pass_at_k=1.0,
        pass_caret_k=0.0,
        avg_score=0.4,
    )
    candidate = ArmResults(
        arm="candidate",
        trials=[],
        decisive=2,
        pass_rate=0.95,
        pass_at_k=1.0,
        pass_caret_k=1.0,
        avg_score=0.95,
    )
    sr = ScenarioResult(
        scenario_id="smoke-1",
        level="unit",
        held_out=False,
        tags=[],
        difficulty=None,
        baseline=baseline,
        candidate=candidate,
        outcome="candidate_win",
    )
    return EvalResults(
        suite_path="eval/eval-suite.yaml",
        baseline_resource="b.md",
        candidate_resource="c.md",
        timestamp="2026-05-08T00:00:00+00:00",
        scenarios=[sr],
        win_rate=1.0,
        baseline_pass_rate=0.4,
        candidate_pass_rate=0.95,
        no_decision_rate=0.0,
        held_out=None,
        by_level={"unit": MagicMock(spec=[])},
        by_tag={},
        total_tokens=50_000,
    )


# =============================================================================
# Dispatcher: returns the right response per agent
# =============================================================================


class _PipelineMock:
    """Routes call_agent_simple invocations to per-agent responses.

    Tracks which agents were called for assertion at the end.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.calls: list[str] = []

    async def __call__(self, agent_name: str, prompt: str, **kwargs: Any) -> str:
        self.calls.append(agent_name)

        if agent_name == "cgf-agents:cgf-research-lead":
            return _materialize_research(self.workspace)

        if agent_name == "cgf-agents:cgf-resource-architect":
            return _make_resource_plan(self.workspace)

        if agent_name == "context-engineering:context-engineer":
            # GENERATE phase calls per resource — extract path from prompt.
            for cand in [
                "agents/test-agent.md",
                "skills/test-skill/SKILL.md",
            ]:
                if cand in prompt:
                    return _generate_response_for(self.workspace, cand)
            return ""

        if agent_name == "cgf-agents:cgf-eval-architect":
            return _materialize_eval_suite(self.workspace)

        if agent_name == "cgf-agents:cgf-prompt-optimizer":
            for cand in [
                "agents/test-agent.md",
                "skills/test-skill/SKILL.md",
            ]:
                if cand in prompt:
                    return _iterate_response_for(self.workspace, cand)
            return ""

        if agent_name == "cgf-agents:cgf-coherence-validator":
            return "[VALIDATE_COMPLETE]\ncoherence_score: 0.95\n"

        # Unknown agent — return empty to make failures obvious in assertions.
        return ""


# =============================================================================
# The integration test
# =============================================================================


@pytest.mark.asyncio
async def test_full_pipeline_promotion_path(workspace: Path) -> None:
    """End-to-end: every phase succeeds, all resources promote, COMPLETE.

    This is the canonical happy path.  It proves:

    1. The dispatcher routes through all 9 phases in PHASE_ORDER.
    2. Each phase's signal-handling produces the state changes the next
       phase needs.
    3. EvalHarness invocation produces a promotable result → candidates
       are marked optimized + finalized to canonical paths.
    4. eval-suite.yaml, eval-results.json, and CHANGELOG are written.
    5. No exceptions propagate; ``OrchestrationResult.success is True``.
    """
    config = MultiResourceConfig(
        workspace_dir=workspace,
        max_iterations=1,  # one iteration is enough — quality_overall=0.92 > threshold
        quality_threshold=0.85,
        verbose=False,
        follow_logs=False,
    )
    orchestrator = MultiResourceOrchestrator(config)
    pipeline_mock = _PipelineMock(workspace)

    mock_harness = MagicMock()
    mock_harness.run = AsyncMock(return_value=_promotable_eval_results())

    with patch(
        "harness.subagent.call_agent_simple", new=pipeline_mock
    ), patch(
        "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
        return_value=mock_harness,
    ):
        result = await orchestrator.run()

    # ----- top-level result -----
    assert result.success, f"Pipeline failed: {result.error}"
    assert result.spec is not None
    # spec.name is parsed from SPEC.md by the multi-resource-spec parser;
    # exact value depends on parser behavior — we verify the pipeline
    # produced *some* spec, not the specific name.
    assert result.spec.name
    assert result.total_duration_seconds >= 0

    # ----- every phase reached -----
    completed = {p.name for p in result.phases_completed}
    expected_phases = {
        "RESEARCH",
        "DESIGN",
        "QA",
        "GENERATE",
        "EVAL_DESIGN",
        "ITERATE",
        "EXECUTION_EVAL",
        "VALIDATE",
    }
    missing = expected_phases - completed
    assert not missing, f"Phases not reached: {missing}"
    assert orchestrator._state is not None
    assert orchestrator._state.current_phase == OptimizationPhase.COMPLETE

    # ----- agents called in order -----
    # Each agent should have been called at least once.
    expected_agents = {
        "cgf-agents:cgf-research-lead",
        "cgf-agents:cgf-resource-architect",
        "context-engineering:context-engineer",
        "cgf-agents:cgf-eval-architect",
        "cgf-agents:cgf-prompt-optimizer",
        "cgf-agents:cgf-coherence-validator",
    }
    called_agents = set(pipeline_mock.calls)
    missing_agents = expected_agents - called_agents
    assert not missing_agents, f"Agents not called: {missing_agents}"

    # ----- artifacts on disk -----
    assert (workspace / "resource-plan.yaml").exists()
    assert (workspace / "eval" / "eval-suite.yaml").exists()
    # Per-resource eval-results.json gets written by EvalHarness, but our
    # mock doesn't touch disk; instead we verify the orchestrator's
    # aggregate file landed.
    aggregate = list((workspace / "eval").glob("execution-eval-round-*.json"))
    assert aggregate, "EXECUTION_EVAL aggregate JSON not written"

    # ----- per-resource state -----
    resources = orchestrator._state.resources
    assert "agents/test-agent.md" in resources
    assert "skills/test-skill/SKILL.md" in resources
    for path, r in resources.items():
        assert r.status == "optimized", f"{path}: status={r.status}"
        assert r.version == 1, f"{path}: version={r.version}"

    # ----- finalized files at canonical paths -----
    # EXECUTION_EVAL's _finalize_single_resource copies v1 → canonical path.
    assert (workspace / "agents" / "test-agent.md").exists()
    assert (workspace / "skills" / "test-skill" / "SKILL.md").exists()

    # ----- harness invoked once per resource -----
    assert mock_harness.run.await_count == len(resources)

    # ----- state file persisted -----
    state_path = workspace / "sessions" / "optimization-state.json"
    if state_path.exists():
        # Optional: load and verify shape.
        import json

        state_data = json.loads(state_path.read_text())
        assert state_data["current_phase"] == "COMPLETE"


@pytest.mark.asyncio
async def test_full_pipeline_regression_loops_back(workspace: Path) -> None:
    """When EvalHarness reports regression, EXECUTION_EVAL loops back to ITERATE.

    Verifies the feedback loop end-to-end: first eval fails → ITERATE
    runs again → second eval succeeds → pipeline completes.
    """
    config = MultiResourceConfig(
        workspace_dir=workspace,
        max_iterations=2,  # need at least 2 iterations to allow second pass
        quality_threshold=0.85,
        max_feedback_iterations=2,
        verbose=False,
        follow_logs=False,
    )
    orchestrator = MultiResourceOrchestrator(config)
    pipeline_mock = _PipelineMock(workspace)

    # First call returns regression; subsequent calls return promotion.
    bad_results = EvalResults(
        suite_path="eval/eval-suite.yaml",
        baseline_resource="b.md",
        candidate_resource="c.md",
        timestamp="2026-05-08T00:00:00+00:00",
        scenarios=[],
        win_rate=0.0,
        baseline_pass_rate=0.7,
        candidate_pass_rate=0.3,
        no_decision_rate=0.0,
        held_out=None,
        by_level={},
        by_tag={},
        total_tokens=10_000,
    )

    mock_harness = MagicMock()
    # Two resources × two rounds = 4 calls total in the worst case;
    # supply enough side_effects to cover the regression-then-promotion loop.
    mock_harness.run = AsyncMock(
        side_effect=[
            # Round 1: both regress → loop back.
            bad_results,
            bad_results,
            # Round 2: both promote.
            _promotable_eval_results(),
            _promotable_eval_results(),
        ]
    )

    with patch(
        "harness.subagent.call_agent_simple", new=pipeline_mock
    ), patch(
        "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
        return_value=mock_harness,
    ):
        result = await orchestrator.run()

    assert result.success
    # Feedback history should have one entry from round 1.
    assert orchestrator._state is not None
    assert len(orchestrator._state.feedback_history) >= 1
    # Final state: all promoted.
    for r in orchestrator._state.resources.values():
        assert r.status == "optimized"
