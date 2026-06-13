"""Tests for the Phase A.6 eval-framework telemetry.

Verifies the five new Prometheus instruments are wired correctly into
EXECUTION_EVAL, EVAL_DESIGN, and the LLM-judge grader, and that the
docker-compose / .env.example configuration mentions the new env vars.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.monitoring import (
    harness_eval_arm_score,
    harness_eval_judge_no_decision_total,
    harness_eval_phase_duration_seconds,
    harness_eval_scenarios_total,
    harness_eval_tokens_to_goal,
)
from harness.optimization.eval_harness import (
    ArmResults,
    EvalResults,
    ScenarioResult,
)
from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import OptimizationPhase, ResourceStatus

# =============================================================================
# Helpers (small subset of test_orchestrator_execution_eval fixtures)
# =============================================================================


def _arm(*, pass_rate: float, decisive: int = 2, pass_caret_k: float = 0.0) -> ArmResults:
    return ArmResults(
        arm="baseline",
        trials=[],
        decisive=decisive,
        pass_rate=pass_rate,
        pass_at_k=1.0 if pass_rate > 0 else 0.0,
        pass_caret_k=pass_caret_k,
        avg_score=pass_rate,
    )


def _scenario_result(
    scenario_id: str,
    *,
    level: str = "unit",
    baseline_pass_rate: float = 0.5,
    candidate_pass_rate: float = 1.0,
    baseline_decisive: int = 2,
    candidate_decisive: int = 2,
    baseline_pass_caret: float = 0.0,
    candidate_pass_caret: float = 1.0,
    held_out: bool = False,
) -> ScenarioResult:
    baseline = _arm(
        pass_rate=baseline_pass_rate,
        decisive=baseline_decisive,
        pass_caret_k=baseline_pass_caret,
    )
    baseline.arm = "baseline"
    candidate = _arm(
        pass_rate=candidate_pass_rate,
        decisive=candidate_decisive,
        pass_caret_k=candidate_pass_caret,
    )
    candidate.arm = "candidate"
    return ScenarioResult(
        scenario_id=scenario_id,
        level=level,
        held_out=held_out,
        tags=[],
        difficulty=None,
        baseline=baseline,
        candidate=candidate,
        outcome="candidate_win",
    )


def _eval_results(
    *,
    candidate_pass_rate: float = 0.9,
    baseline_pass_rate: float = 0.5,
    total_tokens: int = 12_345,
    scenarios: list[ScenarioResult] | None = None,
) -> EvalResults:
    return EvalResults(
        suite_path="suite.yaml",
        baseline_resource="b.md",
        candidate_resource="c.md",
        timestamp="2026-05-08T00:00:00+00:00",
        scenarios=scenarios or [_scenario_result("s1")],
        win_rate=0.8,
        baseline_pass_rate=baseline_pass_rate,
        candidate_pass_rate=candidate_pass_rate,
        no_decision_rate=0.0,
        held_out=None,
        by_level={},
        by_tag={},
        total_tokens=total_tokens,
    )


def _make_orchestrator(
    tmp_path: Path, *, resources: list[dict[str, Any]]
) -> MultiResourceOrchestrator:
    """Minimal orchestrator stub focused on telemetry side effects."""
    config = MultiResourceConfig(
        workspace_dir=tmp_path,
        execution_eval_timeout=60,
        verbose=False,
        follow_logs=False,
    )
    orch = MultiResourceOrchestrator(config)

    spec = MagicMock()
    spec.source_path = "SPEC.md"
    spec.name = "test-plugin"
    orch._spec = spec

    progress = MagicMock()
    progress.save_optimization_state = MagicMock()
    orch._progress = progress

    state = MagicMock()
    state.eval_suite_path = "eval/eval-suite.yaml"
    # Phase A refinement 4.4.a: empty string disables the mid-loop hash guard.
    state.eval_suite_hash = ""
    state.eval_results_path = ""
    state.feedback_history = []
    state.current_phase = OptimizationPhase.EXECUTION_EVAL
    state.phases_completed = []

    state_resources: dict[str, ResourceStatus] = {}
    for entry in resources:
        r = ResourceStatus(
            path=entry["path"],
            resource_type=entry.get("type", "agent"),
            status="optimized",
            version=entry.get("version", 1),
        )
        state_resources[r.path] = r
        from harness.optimization._orchestrator_helpers import versioned_path

        cand = tmp_path / versioned_path(r.path, r.version)
        cand.parent.mkdir(parents=True, exist_ok=True)
        cand.write_text("# candidate")
        v0 = tmp_path / versioned_path(r.path, 0)
        v0.write_text("# baseline v0")
    state.resources = state_resources

    def update(path: str, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(state_resources[path], k, v)

    state.update_resource = MagicMock(side_effect=update)

    def advance(nxt: OptimizationPhase) -> None:
        state.phases_completed.append(state.current_phase)
        state.current_phase = nxt

    state.advance_phase = MagicMock(side_effect=advance)
    orch._state = state

    suite = tmp_path / "eval" / "eval-suite.yaml"
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text("version: '1.0'\nscenarios: []\nconfig: {}\n")

    return orch


# =============================================================================
# Tests
# =============================================================================


class TestInstrumentsExist:
    """The instruments must be importable and have the expected label sets."""

    def test_tokens_to_goal_has_resource_type_label(self) -> None:
        # Calling .labels() with the right kwargs must succeed.
        harness_eval_tokens_to_goal.labels(resource_type="agent").observe(100)

    def test_scenarios_total_has_three_labels(self) -> None:
        harness_eval_scenarios_total.labels(
            level="unit", status="pass", arm="candidate"
        ).inc()

    def test_arm_score_has_arm_and_level(self) -> None:
        harness_eval_arm_score.labels(arm="baseline", level="trajectory").observe(0.5)

    def test_phase_duration_has_phase_label(self) -> None:
        harness_eval_phase_duration_seconds.labels(phase="EVAL_DESIGN").observe(42)
        harness_eval_phase_duration_seconds.labels(phase="EXECUTION_EVAL").observe(120)

    def test_judge_no_decision_has_model_label(self) -> None:
        harness_eval_judge_no_decision_total.labels(model="opus").inc()


class TestExecutionEvalEmitsScenarioMetrics:
    @pytest.mark.asyncio
    async def test_scenarios_total_increments_per_arm(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        results = _eval_results(
            scenarios=[
                _scenario_result(
                    "s1",
                    level="unit",
                    baseline_pass_caret=0.0,  # baseline fails
                    candidate_pass_caret=1.0,  # candidate passes
                ),
            ]
        )

        # Snapshot counter values BEFORE.
        before_pass = _counter_value(
            harness_eval_scenarios_total, level="unit", status="pass", arm="candidate"
        )
        before_fail = _counter_value(
            harness_eval_scenarios_total, level="unit", status="fail", arm="baseline"
        )

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        after_pass = _counter_value(
            harness_eval_scenarios_total, level="unit", status="pass", arm="candidate"
        )
        after_fail = _counter_value(
            harness_eval_scenarios_total, level="unit", status="fail", arm="baseline"
        )

        assert after_pass == before_pass + 1
        assert after_fail == before_fail + 1

    @pytest.mark.asyncio
    async def test_no_decision_status_when_arm_has_zero_decisive(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        results = _eval_results(
            scenarios=[
                _scenario_result(
                    "s1",
                    level="trajectory",
                    candidate_decisive=0,  # candidate had no decisive trials
                    candidate_pass_caret=0.0,
                ),
            ]
        )

        before = _counter_value(
            harness_eval_scenarios_total,
            level="trajectory",
            status="no_decision",
            arm="candidate",
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        after = _counter_value(
            harness_eval_scenarios_total,
            level="trajectory",
            status="no_decision",
            arm="candidate",
        )
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_tokens_to_goal_observed_only_on_promotion(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        # Strict-improvement gate triggered → observe.
        results = _eval_results(
            candidate_pass_rate=0.95, baseline_pass_rate=0.6, total_tokens=42_000
        )

        before = _histogram_count(
            harness_eval_tokens_to_goal, resource_type="agent"
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        after = _histogram_count(harness_eval_tokens_to_goal, resource_type="agent")
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_tokens_to_goal_not_observed_on_regression(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        results = _eval_results(
            candidate_pass_rate=0.3, baseline_pass_rate=0.7
        )

        before = _histogram_count(
            harness_eval_tokens_to_goal, resource_type="agent"
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        after = _histogram_count(harness_eval_tokens_to_goal, resource_type="agent")
        assert after == before  # no observation — candidate didn't promote

    @pytest.mark.asyncio
    async def test_phase_duration_recorded_on_normal_exit(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        results = _eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)

        before = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EXECUTION_EVAL"
        )
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)
        with patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        after = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EXECUTION_EVAL"
        )
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_phase_duration_recorded_on_skip(self, tmp_path: Path) -> None:
        # Suite missing → early return.  Duration should still record.
        orch = _make_orchestrator(tmp_path, resources=[])
        # Force the suite path to point at something nonexistent.
        orch._state.eval_suite_path = "eval/missing.yaml"

        before = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EXECUTION_EVAL"
        )
        await orch._run_execution_eval()
        after = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EXECUTION_EVAL"
        )
        assert after == before + 1


class TestEvalDesignEmitsPhaseDuration:
    @pytest.mark.asyncio
    async def test_eval_design_phase_duration_recorded(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(
            workspace_dir=tmp_path, eval_design_timeout=60, verbose=False
        )
        orch = MultiResourceOrchestrator(config)
        spec = MagicMock()
        spec.source_path = "SPEC.md"
        spec.name = "p"
        orch._spec = spec
        progress = MagicMock()
        orch._progress = progress
        state = MagicMock()
        state.eval_suite_path = ""
        r = MagicMock(spec=ResourceStatus, path="agents/x.md", resource_type="agent")
        r.status = "generated"
        state.get_generated_resources = MagicMock(return_value=[r])
        # F11: phase iterates state.resources.values() to find non-failed
        # resources; fixture must populate this dict explicitly.
        state.resources = {"agents/x.md": r}
        orch._state = state

        # Sharded EVAL_DESIGN: the generated file must exist (the delegate
        # diffs v0→candidate per resource), and the architect writes a
        # per-resource shard which Python merges into eval-suite.yaml.
        import re as _re

        import yaml as _yaml

        gen = tmp_path / "agents" / "x.md"
        gen.parent.mkdir(parents=True, exist_ok=True)
        gen.write_text("# x\ncandidate content\n")

        async def _writer(agent_name: str, prompt: str, **kwargs: object) -> str:
            m = _re.search(r"(\S+/eval/shards/\S+\.yaml)", prompt)
            assert m
            shard = Path(m.group(1))
            shard.parent.mkdir(parents=True, exist_ok=True)
            shard.write_text(
                _yaml.safe_dump(
                    {
                        "version": "1.0",
                        "target_resource": "agents/x.md",
                        "config": {"trials_per_scenario": 1},
                        "scenarios": [
                            {
                                "id": "easy-x-01",
                                "level": "unit",
                                "prompt": "p",
                                "graders": [
                                    {"type": "contains", "needle": "x"}
                                ],
                            }
                        ],
                    }
                )
            )
            return "[EVAL_DESIGN_COMPLETE]"

        before = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EVAL_DESIGN"
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=_writer,
        ):
            await orch._delegate_eval_design()
        after = _histogram_count(
            harness_eval_phase_duration_seconds, phase="EVAL_DESIGN"
        )
        assert after == before + 1


class TestLLMJudgeNoDecisionCounter:
    @pytest.mark.asyncio
    async def test_no_decision_increments_counter(self) -> None:
        from harness.optimization.graders import llm_judge as llm_judge_module
        from harness.optimization.graders.llm_judge import LLMJudgeGrader
        from harness.optimization.graders.scenario import EvalScenario
        from harness.optimization.graders.transcript import AgentTranscript

        # Reset shared client so our patch sticks.
        llm_judge_module._shared_client = None

        # Mock the judge to error out twice → no_decision.
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(llm_judge_module, "get_judge_client", return_value=mock_client):
            from harness.config import MODEL_SHORTHAND_MAP

            opus_id = MODEL_SHORTHAND_MAP["opus"]
            grader = LLMJudgeGrader(rubric="Score 1-5.", eval_model="opus")
            transcript = AgentTranscript(final_output="x")
            scenario = EvalScenario(id="x", level="unit", prompt="hi")

            before = _counter_value(
                harness_eval_judge_no_decision_total,
                model=opus_id,
            )
            result = await grader.grade(transcript, scenario)
            after = _counter_value(
                harness_eval_judge_no_decision_total,
                model=opus_id,
            )

        assert result.no_decision is True
        assert after == before + 1


# =============================================================================
# Configuration file checks (not runtime tests but easy to bundle here)
# =============================================================================


REPO_ROOT = Path(__file__).resolve().parents[3]


class TestEnvVarsExposed:
    """Verify the new env vars are wired through docker-compose + .env.example.

    Not strictly a unit test — these are config-file regressions that
    would silently break the env-passthrough chain (per CLAUDE.md gotcha).
    """

    @pytest.fixture(scope="class")
    def compose_yaml(self) -> str:
        return (REPO_ROOT / "docker-compose.yml").read_text()

    @pytest.fixture(scope="class")
    def env_example(self) -> str:
        return (REPO_ROOT / ".env.example").read_text()

    @pytest.mark.parametrize(
        "var",
        [
            "CGF_JUDGE_MODEL",
            "CGF_EVAL_TOKEN_BUDGET",
            "CGF_EVAL_PROMOTION_EPSILON",
            "CGF_TOKEN_REGRESSION_TOLERANCE",
            "CGF_COST_QUALITY_BONUS",  # I15
            "CGF_MIN_GAIN_PER_ROUND",
        ],
    )
    def test_var_in_docker_compose(self, var: str, compose_yaml: str) -> None:
        assert var in compose_yaml, (
            f"{var} not found in docker-compose.yml — env passthrough will silently drop it."
        )

    @pytest.mark.parametrize(
        "var",
        [
            "CGF_JUDGE_MODEL",
            "CGF_EVAL_TOKEN_BUDGET",
            "CGF_EVAL_PROMOTION_EPSILON",
            "CGF_TOKEN_REGRESSION_TOLERANCE",
            "CGF_COST_QUALITY_BONUS",  # I15
            "CGF_MIN_GAIN_PER_ROUND",
        ],
    )
    def test_var_in_env_example(self, var: str, env_example: str) -> None:
        assert var in env_example, f"{var} not documented in .env.example"


class TestGrafanaDashboard:
    """Verify the Grafana dashboard references the new instruments."""

    @pytest.fixture(scope="class")
    def dashboard(self) -> dict[str, Any]:
        import json

        # Path renamed in G3 (grafana-refactor branch) — cgf.json →
        # 70-mode-cgf.json under the numeric tier scheme; UID
        # (casdk-cgf) is unchanged.
        with (REPO_ROOT / "config/monitoring/dashboards/70-mode-cgf.json").open() as f:
            return json.load(f)

    def test_no_placeholder_panels(self, dashboard: dict[str, Any]) -> None:
        # The Future placeholder should be gone.
        for panel in dashboard["panels"]:
            assert "placeholder" not in panel.get("title", "").lower()
            for sub in panel.get("panels") or []:
                assert "placeholder" not in sub.get("title", "").lower()

    @pytest.mark.parametrize(
        "metric",
        [
            "harness_eval_phase_duration_seconds",
            "harness_eval_tokens_to_goal",
            "harness_eval_scenarios_total",
            "harness_eval_arm_score",
            "harness_eval_judge_no_decision_total",
        ],
    )
    def test_dashboard_references_metric(
        self, metric: str, dashboard: dict[str, Any]
    ) -> None:
        import json

        as_text = json.dumps(dashboard)
        assert metric in as_text, (
            f"Grafana dashboard does not reference {metric} — panel will be empty."
        )


# =============================================================================
# Internal helpers
# =============================================================================


def _counter_value(counter: Any, **labels: str) -> float:
    """Read a Counter's current value at the given labelset."""
    metric = counter.labels(**labels)
    # prometheus_client stores the value on _value.get()
    return metric._value.get()


def _histogram_count(histogram: Any, **labels: str) -> int:
    """Read a Histogram's observation count at the given labelset.

    Uses ``collect()`` rather than internal attributes — the _count
    field isn't part of prometheus_client's Histogram public API.
    """
    # Eagerly create the labelset so collect() includes it even when
    # this is the first observation.
    histogram.labels(**labels)
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name.endswith("_count") and all(
                sample.labels.get(k) == v for k, v in labels.items()
            ):
                return int(sample.value)
    return 0
