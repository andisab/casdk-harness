"""Tests for the EXECUTION_EVAL phase (CGF Stage 3 Phase A.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.eval_harness import (
    ArmResults,
    EvalResults,
    ScenarioResult,
    SubsetStats,
)
from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import OptimizationPhase, ResourceStatus

# =============================================================================
# Helpers
# =============================================================================


def _make_eval_results(
    *,
    candidate_pass_rate: float,
    baseline_pass_rate: float,
    win_rate: float = 0.0,
    no_decision_rate: float = 0.0,
    held_out_count: int = 0,
    failing_scenarios: list[dict[str, Any]] | None = None,
) -> EvalResults:
    """Build an EvalResults skeleton with the per-scenario / arm details
    we need to exercise the gate."""
    scenarios: list[ScenarioResult] = []
    for entry in failing_scenarios or []:
        baseline = ArmResults(
            arm="baseline",
            trials=[],
            decisive=2,
            pass_rate=entry.get("baseline_pass_rate", 0.5),
            pass_at_k=1.0,
            pass_caret_k=0.0,
            avg_score=0.5,
        )
        candidate = ArmResults(
            arm="candidate",
            trials=[],
            decisive=2,
            pass_rate=entry.get("candidate_pass_rate", 0.0),
            pass_at_k=0.0,
            pass_caret_k=0.0,
            avg_score=0.0,
        )
        scenarios.append(
            ScenarioResult(
                scenario_id=entry["scenario_id"],
                level=entry.get("level", "unit"),
                held_out=entry.get("held_out", False),
                tags=entry.get("tags", []),
                difficulty=None,
                baseline=baseline,
                candidate=candidate,
                outcome=entry.get("outcome", "baseline_win"),  # type: ignore[arg-type]
            )
        )
    held_out_stats = (
        SubsetStats(
            count=held_out_count,
            win_rate=0.0,
            baseline_pass_rate=baseline_pass_rate,
            candidate_pass_rate=candidate_pass_rate,
            no_decision_rate=0.0,
        )
        if held_out_count > 0
        else None
    )
    return EvalResults(
        suite_path="suite.yaml",
        baseline_resource="b.md",
        candidate_resource="c.md",
        timestamp="2026-05-08T00:00:00+00:00",
        scenarios=scenarios,
        win_rate=win_rate,
        baseline_pass_rate=baseline_pass_rate,
        candidate_pass_rate=candidate_pass_rate,
        no_decision_rate=no_decision_rate,
        held_out=held_out_stats,
        by_level={},
        by_tag={},
        total_tokens=200,
    )


def _make_orchestrator(
    tmp_path: Path,
    *,
    resources: list[dict[str, Any]],
    eval_suite_path: str = "eval/eval-suite.yaml",
    create_suite: bool = True,
    feedback_history: list[dict[str, Any]] | None = None,
    eval_promotion_epsilon: float | None = None,
    max_feedback_iterations: int | None = None,
) -> MultiResourceOrchestrator:
    """Build an orchestrator with state pre-populated for EXECUTION_EVAL.

    Materializes the eval-suite file and per-resource versioned files on
    disk so the phase's existence checks pass.
    """
    config = MultiResourceConfig(
        workspace_dir=tmp_path,
        execution_eval_timeout=60,
        verbose=False,
        follow_logs=False,
        eval_promotion_epsilon=eval_promotion_epsilon,
        max_feedback_iterations=max_feedback_iterations,
    )
    orch = MultiResourceOrchestrator(config)

    spec = MagicMock()
    spec.source_path = "SPEC.md"
    spec.name = "test-plugin"
    orch._spec = spec

    progress = MagicMock()
    progress.save_optimization_state = MagicMock()
    orch._progress = progress

    # Build state.
    state = MagicMock()
    state.eval_suite_path = eval_suite_path
    state.eval_results_path = ""
    state.feedback_history = list(feedback_history or [])
    state.current_phase = OptimizationPhase.EXECUTION_EVAL
    state.phases_completed = []

    # Resources
    resource_objects: list[ResourceStatus] = []
    state_resources: dict[str, ResourceStatus] = {}
    for entry in resources:
        r = ResourceStatus(
            path=entry["path"],
            resource_type=entry.get("type", "agent"),
            status=entry.get("status", "optimized"),
            version=entry.get("version", 1),
        )
        r.refinement_count = entry.get("refinement_count", 0)
        resource_objects.append(r)
        state_resources[r.path] = r

        # Materialize the candidate file at workspace/{path-v{version}}.
        from harness.optimization._orchestrator_helpers import versioned_path

        cand = tmp_path / versioned_path(r.path, r.version)
        cand.parent.mkdir(parents=True, exist_ok=True)
        cand.write_text("# candidate")

        # Optionally materialize the v0 baseline.
        if entry.get("create_baseline_v0", True):
            v0 = tmp_path / versioned_path(r.path, 0)
            v0.parent.mkdir(parents=True, exist_ok=True)
            v0.write_text("# baseline v0")

    state.resources = state_resources
    state.update_resource = MagicMock(
        side_effect=lambda path, **fields: setattr_resource(
            state_resources[path], **fields
        )
    )
    state.advance_phase = MagicMock(
        side_effect=lambda next_phase: _advance(state, next_phase)
    )
    orch._state = state

    # Materialize the eval suite file (the phase only checks existence).
    if create_suite:
        suite = tmp_path / eval_suite_path
        suite.parent.mkdir(parents=True, exist_ok=True)
        suite.write_text("version: '1.0'\nscenarios: []\nconfig: {}\n")

    return orch


def setattr_resource(resource: ResourceStatus, **fields: Any) -> None:
    for k, v in fields.items():
        setattr(resource, k, v)


def _advance(state: MagicMock, next_phase: OptimizationPhase) -> None:
    state.phases_completed.append(state.current_phase)
    state.current_phase = next_phase


# =============================================================================
# Tests
# =============================================================================


class TestExecutionEvalSkipPaths:
    @pytest.mark.asyncio
    async def test_no_eval_suite_path_skips(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[],
            eval_suite_path="",
            create_suite=False,
        )
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness"
        ) as MockHarness:
            await orch._run_execution_eval()
        MockHarness.assert_not_called()
        # No phase transition triggered by the phase itself.
        orch._state.advance_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_suite_missing_on_disk_skips(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
            create_suite=False,
        )
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness"
        ) as MockHarness:
            await orch._run_execution_eval()
        MockHarness.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_iterated_resources_skips(self, tmp_path: Path) -> None:
        # Resource with version=0 → not yet iterated.
        orch = _make_orchestrator(
            tmp_path,
            resources=[
                {"path": "agents/iac.md", "version": 0, "status": "generated"},
            ],
        )
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness"
        ) as MockHarness:
            await orch._run_execution_eval()
        MockHarness.assert_not_called()


class TestExecutionEvalPromotion:
    @pytest.mark.asyncio
    async def test_all_resources_promote_advances_to_validate(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[
                {"path": "agents/iac.md", "version": 1},
                {"path": "agents/security.md", "version": 1},
            ],
        )

        # Both candidates strictly beat baseline.
        good_results = _make_eval_results(
            candidate_pass_rate=0.9,
            baseline_pass_rate=0.5,
            win_rate=0.8,
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=good_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Both resources should be marked optimized.
        for path in ("agents/iac.md", "agents/security.md"):
            r = orch._state.resources[path]
            assert r.status == "optimized"
        # Phase should have advanced to VALIDATE.
        orch._state.advance_phase.assert_called_once_with(
            OptimizationPhase.VALIDATE
        )
        # No feedback entry written (no regressions).
        assert orch._state.feedback_history == []

    @pytest.mark.asyncio
    async def test_regression_loops_back_to_iterate(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        # Candidate regressed.
        bad_results = _make_eval_results(
            candidate_pass_rate=0.3,
            baseline_pass_rate=0.6,
            win_rate=0.2,
            failing_scenarios=[
                {
                    "scenario_id": "unit-iac-easy-01",
                    "outcome": "baseline_win",
                    "candidate_pass_rate": 0.3,
                    "baseline_pass_rate": 0.6,
                },
                {
                    "scenario_id": "e2e-iac-hard-01",
                    "outcome": "tie",
                    "held_out": True,  # should be filtered from feedback
                },
            ],
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=bad_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Resource flagged for refinement.
        r = orch._state.resources["agents/iac.md"]
        assert r.status == "needs_refinement"
        # Phase looped back to ITERATE (state.current_phase set directly,
        # NOT via advance_phase).
        assert orch._state.current_phase == OptimizationPhase.ITERATE
        orch._state.advance_phase.assert_not_called()
        # A feedback entry was added.
        assert len(orch._state.feedback_history) == 1
        entry = orch._state.feedback_history[0]
        assert entry["feedback_iteration"] == 1
        # Held-out scenario should NOT appear in feedback failing_scenarios.
        regression_records = entry["regressions"]
        assert len(regression_records) == 1
        failing = regression_records[0]["failing_scenarios"]
        assert all(s["scenario_id"] != "e2e-iac-hard-01" for s in failing)
        assert any(s["scenario_id"] == "unit-iac-easy-01" for s in failing)

    @pytest.mark.asyncio
    async def test_max_feedback_escalates_to_validate(
        self, tmp_path: Path
    ) -> None:
        # Already 2 feedback rounds done → next regression escalates.
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
            feedback_history=[
                {"feedback_iteration": 1, "regressions": []},
                {"feedback_iteration": 2, "regressions": []},
            ],
            max_feedback_iterations=2,
        )
        bad_results = _make_eval_results(
            candidate_pass_rate=0.3, baseline_pass_rate=0.7
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=bad_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Resource STILL flagged for refinement (so VALIDATE / human review
        # can see the issue) but pipeline advances forward.
        r = orch._state.resources["agents/iac.md"]
        assert r.status == "needs_refinement"
        orch._state.advance_phase.assert_called_once_with(
            OptimizationPhase.VALIDATE
        )
        # Feedback history unchanged (no new entry added on escalation).
        assert len(orch._state.feedback_history) == 2

    @pytest.mark.asyncio
    async def test_partial_promotion_one_promotes_one_regresses(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[
                {"path": "agents/winner.md", "version": 1},
                {"path": "agents/loser.md", "version": 1},
            ],
        )
        # Different results per resource — use side_effect.
        winner = _make_eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)
        loser = _make_eval_results(candidate_pass_rate=0.3, baseline_pass_rate=0.6)
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(side_effect=[winner, loser])
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        assert orch._state.resources["agents/winner.md"].status == "optimized"
        assert orch._state.resources["agents/loser.md"].status == "needs_refinement"
        # Should loop back since one regressed and feedback < max.
        assert orch._state.current_phase == OptimizationPhase.ITERATE


class TestExecutionEvalGate:
    @pytest.mark.asyncio
    async def test_epsilon_via_config(self, tmp_path: Path) -> None:
        # Candidate beats baseline by exactly 0.05; with epsilon=0.1 → reject.
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
            eval_promotion_epsilon=0.1,
        )
        results = _make_eval_results(
            candidate_pass_rate=0.55, baseline_pass_rate=0.5
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # 0.55 < 0.5 + 0.1 → not promoted.
        assert orch._state.resources["agents/iac.md"].status == "needs_refinement"

    @pytest.mark.asyncio
    async def test_tie_does_not_promote(self, tmp_path: Path) -> None:
        # Equality with eps=0 → not promoted (strict requirement).
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
            eval_promotion_epsilon=0.001,  # tiny epsilon, equality still fails
        )
        results = _make_eval_results(
            candidate_pass_rate=0.7, baseline_pass_rate=0.7
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        assert orch._state.resources["agents/iac.md"].status == "needs_refinement"


class TestExecutionEvalErrorHandling:
    @pytest.mark.asyncio
    async def test_harness_exception_marks_for_refinement(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(side_effect=RuntimeError("kaboom"))
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Treated as regression → flagged for refinement, loops back.
        r = orch._state.resources["agents/iac.md"]
        assert r.status == "needs_refinement"

    @pytest.mark.asyncio
    async def test_missing_candidate_file_skipped(self, tmp_path: Path) -> None:
        # Resource has version=1 but candidate file doesn't exist on disk.
        orch = _make_orchestrator(
            tmp_path,
            resources=[
                {"path": "agents/iac.md", "version": 1},
                {"path": "agents/missing.md", "version": 1},
            ],
        )
        # Remove the candidate for the second resource.
        from harness.optimization._orchestrator_helpers import versioned_path

        (tmp_path / versioned_path("agents/missing.md", 1)).unlink()

        good = _make_eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=good)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Only iac.md was actually evaluated.
        assert mock_harness.run.await_count == 1
        # iac.md promoted; missing.md untouched (still its initial state).
        assert orch._state.resources["agents/iac.md"].status == "optimized"


class TestExecutionEvalAggregateOutput:
    @pytest.mark.asyncio
    async def test_aggregate_json_written(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        results = _make_eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Aggregate file written.
        agg = tmp_path / "eval" / "execution-eval-round-1.json"
        assert agg.exists()
        # state.eval_results_path points at relative location.
        assert orch._state.eval_results_path.endswith("execution-eval-round-1.json")


class TestFeedbackBlockBuilder:
    """Direct unit tests for the iterate.py feedback prompt builder."""

    def test_no_feedback_returns_empty(self) -> None:
        from harness.optimization._orchestrator_phases.iterate import (
            _build_feedback_block,
        )

        assert _build_feedback_block([], "agents/iac.md") == ""

    def test_resource_not_in_feedback_returns_empty(self) -> None:
        from harness.optimization._orchestrator_phases.iterate import (
            _build_feedback_block,
        )

        history = [
            {
                "feedback_iteration": 1,
                "regressions": [
                    {"path": "agents/other.md", "failing_scenarios": []}
                ],
            }
        ]
        assert _build_feedback_block(history, "agents/iac.md") == ""

    def test_renders_failing_scenarios(self) -> None:
        from harness.optimization._orchestrator_phases.iterate import (
            _build_feedback_block,
        )

        history = [
            {
                "feedback_iteration": 1,
                "regressions": [
                    {
                        "path": "agents/iac.md",
                        "candidate_pass_rate": 0.3,
                        "baseline_pass_rate": 0.7,
                        "win_rate": 0.2,
                        "failing_scenarios": [
                            {
                                "scenario_id": "unit-iac-easy-01",
                                "level": "unit",
                                "outcome": "baseline_win",
                                "baseline_pass_rate": 0.8,
                                "candidate_pass_rate": 0.3,
                            }
                        ],
                    }
                ],
            }
        ]
        block = _build_feedback_block(history, "agents/iac.md")
        assert "unit-iac-easy-01" in block
        assert "round 1" in block
        assert "Held-out" in block  # warning about held-out scenarios

    def test_caps_at_8_failing_scenarios(self) -> None:
        from harness.optimization._orchestrator_phases.iterate import (
            _build_feedback_block,
        )

        history = [
            {
                "feedback_iteration": 1,
                "regressions": [
                    {
                        "path": "agents/iac.md",
                        "candidate_pass_rate": 0.0,
                        "baseline_pass_rate": 0.7,
                        "win_rate": 0.0,
                        "failing_scenarios": [
                            {
                                "scenario_id": f"s{i:02d}",
                                "level": "unit",
                                "outcome": "baseline_win",
                            }
                            for i in range(15)
                        ],
                    }
                ],
            }
        ]
        block = _build_feedback_block(history, "agents/iac.md")
        # First 8 listed inline; rest summarized.
        assert "s00" in block
        assert "s07" in block
        assert "s08" not in block
        assert "plus 7 more" in block
