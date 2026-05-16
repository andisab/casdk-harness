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
    # Phase A refinement 4.4.a: empty string disables the suite-hash
    # mid-loop guard in EXECUTION_EVAL.  Tests that want to exercise
    # the guard set this explicitly.
    state.eval_suite_hash = ""
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
        """F8: when EVERY resource errors, the run aborts with RuntimeError
        rather than silently advancing.  Before F8, this test passed by
        relying on the silent-advance fail-OPEN bug; now we expect the
        abort and verify the state was still updated before it fired."""
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
            with pytest.raises(
                RuntimeError, match=r"all \d+ resources errored"
            ):
                await orch._run_execution_eval()

        # F8: state is updated to needs_refinement BEFORE the abort,
        # so the resource record reflects the error.
        r = orch._state.resources["agents/iac.md"]
        assert r.status == "needs_refinement"
        assert "kaboom" in r.error

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


class TestExecutionEvalAggregateVerdict:
    """Aggregate JSON records the actual gate verdict, and the legacy
    ``promoted`` field is derived strictly from that verdict — no more
    pre-refinement pass-rate-delta approximation."""

    @pytest.mark.asyncio
    async def test_promote_verdict_in_aggregate(self, tmp_path: Path) -> None:
        import json as _json

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        # Quality + cost both clear.
        results = _make_eval_results(
            candidate_pass_rate=0.9, baseline_pass_rate=0.5
        )
        results.candidate_cost_per_success = 0.05
        results.baseline_cost_per_success = 0.06
        # Skip first-promotion floor for cleanliness — last_promoted=1.
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        agg = _json.loads(
            (tmp_path / "eval" / "execution-eval-round-1.json").read_text()
        )
        entry = agg["resources"][0]
        assert entry["verdict"] == "promote"
        assert entry["promoted"] is True
        # Status agrees with verdict.
        assert orch._state.resources["agents/iac.md"].status == "optimized"

    @pytest.mark.asyncio
    async def test_reject_cost_verdict_in_aggregate(
        self, tmp_path: Path
    ) -> None:
        """The headline data-integrity case: candidate beats baseline on
        quality but is too expensive.  Old aggregate would have written
        ``promoted: true`` (pre-refinement formula); the new aggregate
        writes ``verdict: reject_cost`` and ``promoted: false`` —
        agreeing with the orchestrator state."""
        import json as _json

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        results = _make_eval_results(
            candidate_pass_rate=0.9, baseline_pass_rate=0.5
        )
        # Cost regressed 10x past 10% tolerance.
        results.candidate_cost_per_success = 1.00
        results.baseline_cost_per_success = 0.10
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        agg = _json.loads(
            (tmp_path / "eval" / "execution-eval-round-1.json").read_text()
        )
        entry = agg["resources"][0]
        assert entry["verdict"] == "reject_cost"
        assert entry["promoted"] is False
        # Status agrees with verdict — needs_refinement, NOT optimized.
        assert (
            orch._state.resources["agents/iac.md"].status
            == "needs_refinement"
        )

    @pytest.mark.asyncio
    async def test_refine_verdict_in_aggregate(self, tmp_path: Path) -> None:
        """Quality regression → verdict=refine, promoted=false."""
        import json as _json

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        bad = _make_eval_results(
            candidate_pass_rate=0.3, baseline_pass_rate=0.7
        )
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=bad)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        agg = _json.loads(
            (tmp_path / "eval" / "execution-eval-round-1.json").read_text()
        )
        entry = agg["resources"][0]
        assert entry["verdict"] == "refine"
        assert entry["promoted"] is False

    @pytest.mark.asyncio
    async def test_unwinnable_verdict_in_aggregate(
        self, tmp_path: Path
    ) -> None:
        """Both arms zero → unwinnable verdict (never reached the gate),
        promoted=false."""
        import json as _json

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        # Both arms 0 across all scenarios → F21 unwinnable.
        unwinnable_results = _make_eval_results(
            candidate_pass_rate=0.0,
            baseline_pass_rate=0.0,
            failing_scenarios=[
                {
                    "scenario_id": "scn-1",
                    "outcome": "no_decision",
                    "candidate_pass_rate": 0.0,
                    "baseline_pass_rate": 0.0,
                },
            ],
        )

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=unwinnable_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        agg = _json.loads(
            (tmp_path / "eval" / "execution-eval-round-1.json").read_text()
        )
        entry = agg["resources"][0]
        assert entry["verdict"] == "unwinnable"
        assert entry["promoted"] is False
        assert (
            orch._state.resources["agents/iac.md"].status == "unwinnable"
        )


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


# =============================================================================
# F17 — EXECUTION_EVAL skip unchanged resources
# =============================================================================


class TestExecutionEvalSkipUnchanged:
    """F17: ``_resources_to_evaluate`` must skip resources whose
    ``version`` has not advanced past ``last_evaluated_version`` since
    the last successful eval, and must bump ``last_evaluated_version``
    after each successful eval write."""

    def test_resources_to_evaluate_skips_when_version_unchanged_since_last_eval(
        self, tmp_path: Path
    ) -> None:
        from harness.optimization._orchestrator_phases.execution_eval import (
            _resources_to_evaluate,
        )

        orch = _make_orchestrator(
            tmp_path,
            resources=[
                # Already evaluated at v1 — should be skipped.
                {"path": "agents/a.md", "version": 1},
                # Not yet evaluated (last_evaluated_version=0, version=1).
                {"path": "agents/b.md", "version": 1},
                # New refinement (v2) since last eval at v1.
                {"path": "agents/c.md", "version": 2},
                # Unwinnable — always skipped regardless of versions.
                {"path": "agents/d.md", "version": 1},
                # Failed generation — always skipped.
                {"path": "agents/e.md", "version": 0},
            ],
        )
        # Pre-set last_evaluated_version + statuses where relevant.
        orch._state.resources["agents/a.md"].last_evaluated_version = 1
        orch._state.resources["agents/c.md"].last_evaluated_version = 1
        orch._state.resources["agents/d.md"].status = "unwinnable"
        orch._state.resources["agents/d.md"].last_evaluated_version = 1
        orch._state.resources["agents/e.md"].status = "failed"

        eligible = _resources_to_evaluate(orch)
        eligible_paths = sorted(r.path for r in eligible)
        assert eligible_paths == ["agents/b.md", "agents/c.md"]

    @pytest.mark.asyncio
    async def test_last_evaluated_version_updates_after_successful_write_only(
        self, tmp_path: Path
    ) -> None:
        """After a successful eval (promote OR regress), ``last_evaluated_version``
        equals ``version``.  Harness exceptions must NOT bump it."""
        # Case 1: promotion bumps last_evaluated_version.
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        good = _make_eval_results(
            candidate_pass_rate=0.9, baseline_pass_rate=0.5, win_rate=0.8,
        )
        mock_h = MagicMock()
        mock_h.run = AsyncMock(return_value=good)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_h,
        ):
            await orch._run_execution_eval()
        r = orch._state.resources["agents/iac.md"]
        assert r.status == "optimized"
        assert r.last_evaluated_version == 1

        # Case 2: regression also bumps last_evaluated_version (eval ran;
        # only the verdict was negative).
        orch2 = _make_orchestrator(
            tmp_path / "case2",
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        bad = _make_eval_results(
            candidate_pass_rate=0.3, baseline_pass_rate=0.6,
            failing_scenarios=[
                {"scenario_id": "u-01", "outcome": "baseline_win"},
            ],
        )
        mock_h2 = MagicMock()
        mock_h2.run = AsyncMock(return_value=bad)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_h2,
        ):
            await orch2._run_execution_eval()
        r2 = orch2._state.resources["agents/iac.md"]
        assert r2.status == "needs_refinement"
        assert r2.last_evaluated_version == 1

        # Case 3: harness raised — last_evaluated_version stays at 0 so
        # the resource remains eligible for re-eval next round.  With
        # only 1 resource and it erroring, F8's hard-abort fires (all
        # resources errored); catch the RuntimeError but inspect state
        # before/at-failure to confirm last_evaluated_version is unchanged.
        orch3 = _make_orchestrator(
            tmp_path / "case3",
            resources=[
                {"path": "agents/iac.md", "version": 1},
                # Second resource that succeeds so F8's "all errored"
                # abort doesn't fire — we only want to verify that the
                # erroring one keeps last_evaluated_version=0.
                {"path": "agents/other.md", "version": 1},
            ],
        )
        good_for_other = _make_eval_results(
            candidate_pass_rate=0.9, baseline_pass_rate=0.5, win_rate=0.8,
        )
        mock_h3 = MagicMock()
        # First call (iac.md) raises; second (other.md) returns good.
        mock_h3.run = AsyncMock(
            side_effect=[RuntimeError("boom"), good_for_other]
        )
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_h3,
        ):
            await orch3._run_execution_eval()
        r3 = orch3._state.resources["agents/iac.md"]
        # Eval raised → last_evaluated_version must NOT have advanced.
        assert r3.last_evaluated_version == 0
        # The successful sibling did advance.
        r3_other = orch3._state.resources["agents/other.md"]
        assert r3_other.last_evaluated_version == 1


# =============================================================================
# F21 — Unwinnable-resource detector
# =============================================================================


class TestExecutionEvalUnwinnable:
    """F21: when both arms score 0 across every scenario, mark the
    resource ``unwinnable`` and exclude from feedback rounds."""

    @pytest.mark.asyncio
    async def test_unwinnable_detected_when_all_scenarios_zero_both_arms(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "commands/iac.md", "version": 1}],
        )
        # Two scenarios, both arms score 0 on every one.
        zero_results = _make_eval_results(
            candidate_pass_rate=0.0,
            baseline_pass_rate=0.0,
            failing_scenarios=[
                {
                    "scenario_id": "easy-cmd-01",
                    "outcome": "tie",
                    "baseline_pass_rate": 0.0,
                    "candidate_pass_rate": 0.0,
                },
                {
                    "scenario_id": "hard-cmd-01",
                    "outcome": "tie",
                    "baseline_pass_rate": 0.0,
                    "candidate_pass_rate": 0.0,
                },
            ],
        )
        mock_h = MagicMock()
        mock_h.run = AsyncMock(return_value=zero_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_h,
        ):
            await orch._run_execution_eval()

        r = orch._state.resources["commands/iac.md"]
        assert r.status == "unwinnable"
        # last_evaluated_version is bumped — F17 filter will skip this
        # resource on the next round.
        assert r.last_evaluated_version == 1
        # No feedback iteration triggered — no regressions, no errors.
        orch._state.advance_phase.assert_called_once_with(
            OptimizationPhase.VALIDATE
        )
        assert orch._state.feedback_history == []

    def test_unwinnable_resource_excluded_from_feedback_round_2(
        self, tmp_path: Path
    ) -> None:
        """An unwinnable resource is filtered out of the eligible set on
        the next call to ``_resources_to_evaluate``, even after its
        version would naively re-qualify it."""
        from harness.optimization._orchestrator_phases.execution_eval import (
            _resources_to_evaluate,
        )

        orch = _make_orchestrator(
            tmp_path,
            resources=[
                {"path": "agents/regressed.md", "version": 2},
                {"path": "commands/dead.md", "version": 1},
            ],
        )
        # Simulate post-round-1 state: regressed needs another pass;
        # dead was marked unwinnable.
        orch._state.resources["agents/regressed.md"].status = "needs_refinement"
        orch._state.resources["agents/regressed.md"].last_evaluated_version = 1
        orch._state.resources["commands/dead.md"].status = "unwinnable"
        orch._state.resources["commands/dead.md"].last_evaluated_version = 1

        eligible = _resources_to_evaluate(orch)
        eligible_paths = sorted(r.path for r in eligible)
        assert eligible_paths == ["agents/regressed.md"]

    def test_is_unwinnable_helper_returns_false_for_partial_zero(
        self,
    ) -> None:
        """``_is_unwinnable`` requires zero on EVERY scenario — one
        non-zero clears the flag."""
        from harness.optimization._orchestrator_phases.execution_eval import (
            _is_unwinnable,
        )

        results = _make_eval_results(
            candidate_pass_rate=0.0,
            baseline_pass_rate=0.0,
            failing_scenarios=[
                {
                    "scenario_id": "easy-01",
                    "outcome": "tie",
                    "baseline_pass_rate": 0.0,
                    "candidate_pass_rate": 0.0,
                },
                {
                    "scenario_id": "easy-02",
                    "outcome": "candidate_win",
                    "baseline_pass_rate": 0.0,
                    "candidate_pass_rate": 0.5,
                },
            ],
        )
        assert _is_unwinnable(results) is False

    def test_is_unwinnable_helper_returns_false_for_empty_scenarios(
        self,
    ) -> None:
        """No scenarios at all is not unwinnable — likely a config issue."""
        from harness.optimization._orchestrator_phases.execution_eval import (
            _is_unwinnable,
        )

        results = _make_eval_results(
            candidate_pass_rate=0.0,
            baseline_pass_rate=0.0,
        )
        assert _is_unwinnable(results) is False


# =============================================================================
# Cost-gate counter — fires only when the cost stage was consulted
# =============================================================================
#
# Phase A refinement (post-cgf-eval-ab review): ``gate_decide`` short-
# circuits inside the quality stages.  ``refine`` and ``reject_floor``
# never reach the cost stage, so counting them as ``outcome="promote"``
# (or ``outcome="auto_pass"``) on ``harness_eval_cost_gate_total`` is
# misleading.  The counter must only increment when the cost stage
# actually evaluated.


def _cost_counter_value(outcome: str) -> float:
    """Read ``harness_eval_cost_gate_total{outcome=...}`` directly."""
    from harness.monitoring import harness_eval_cost_gate_total

    return harness_eval_cost_gate_total.labels(outcome=outcome)._value.get()


class TestCostGateCounter:
    """``harness_eval_cost_gate_total`` only increments when cost stage fired."""

    @pytest.mark.asyncio
    async def test_quality_refine_does_not_touch_counter(
        self, tmp_path: Path
    ) -> None:
        """When the quality stage rejects (verdict=refine), the cost
        stage was never consulted.  Counter must NOT increment for any
        outcome label, even when cost data is present on the results."""
        before = {
            o: _cost_counter_value(o)
            for o in ("promote", "reject_cost", "auto_pass")
        }

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        # Quality regression (candidate < baseline) plus cost data
        # populated on both arms.
        bad_results = _make_eval_results(
            candidate_pass_rate=0.3,
            baseline_pass_rate=0.7,
        )
        bad_results.candidate_cost_per_success = 0.10
        bad_results.baseline_cost_per_success = 0.05
        # last_promoted_version=1 so we're in incumbent regime, not
        # first-promotion (no floor arm to confuse the verdict).
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=bad_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Verdict was "refine" → cost counter should be unchanged.
        for outcome, prev in before.items():
            assert _cost_counter_value(outcome) == prev, (
                f"cost counter outcome={outcome!r} incremented on a "
                f"quality-refine verdict (prev={prev}, now="
                f"{_cost_counter_value(outcome)})"
            )

    @pytest.mark.asyncio
    async def test_promote_with_cost_data_increments_promote(
        self, tmp_path: Path
    ) -> None:
        """When quality clears AND cost stage clears, counter increments
        outcome=promote."""
        before = _cost_counter_value("promote")

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        good_results = _make_eval_results(
            candidate_pass_rate=0.9,
            baseline_pass_rate=0.5,
        )
        good_results.candidate_cost_per_success = 0.05
        good_results.baseline_cost_per_success = 0.06  # candidate cheaper
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=good_results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        assert _cost_counter_value("promote") == before + 1.0

    @pytest.mark.asyncio
    async def test_promote_with_missing_cost_signal_increments_auto_pass(
        self, tmp_path: Path
    ) -> None:
        """When quality clears but one cost side is None (e.g., baseline
        had zero successful trials), the cost stage auto-passes.  Counter
        increments outcome=auto_pass."""
        before = _cost_counter_value("auto_pass")

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        results = _make_eval_results(
            candidate_pass_rate=0.9,
            baseline_pass_rate=0.0,  # zero successes → no cost signal
        )
        results.candidate_cost_per_success = 0.05
        results.baseline_cost_per_success = None
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        assert _cost_counter_value("auto_pass") == before + 1.0

    @pytest.mark.asyncio
    async def test_reject_cost_increments_reject_cost(
        self, tmp_path: Path
    ) -> None:
        """When quality clears but candidate is too expensive, verdict=
        reject_cost and counter increments outcome=reject_cost."""
        before = _cost_counter_value("reject_cost")

        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        # Quality clear (candidate >= baseline), but cost regressed
        # well past the default 10% tolerance.
        results = _make_eval_results(
            candidate_pass_rate=0.9,
            baseline_pass_rate=0.5,
        )
        results.candidate_cost_per_success = 1.00  # 10x more than baseline
        results.baseline_cost_per_success = 0.10
        orch._state.resources["agents/iac.md"].last_promoted_version = 1

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        assert _cost_counter_value("reject_cost") == before + 1.0
        # The resource should be flagged needs_refinement (not optimized).
        assert (
            orch._state.resources["agents/iac.md"].status
            == "needs_refinement"
        )
