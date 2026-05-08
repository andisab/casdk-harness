"""Tests for the Phase A.7 OTel tracer-span attributes on eval phases.

Verifies:
- ``eval_phase_span`` helper degrades gracefully when the tracer is
  unavailable (no exceptions propagate).
- EVAL_DESIGN sets ``harness.eval.task_id``, ``harness.eval.phase``,
  ``harness.eval.outcome``.
- EXECUTION_EVAL parent span sets task_id + phase; per-resource sub-spans
  set resource_path, resource_type, resource_version, candidate_pass_rate,
  baseline_pass_rate, win_rate, outcome.
- Tracer attribute ops never break the eval phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization._orchestrator_helpers import (
    _NoOpSpan,
    eval_phase_span,
    new_eval_task_id,
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
# Fixtures
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


def _eval_results(
    *,
    candidate_pass_rate: float = 0.9,
    baseline_pass_rate: float = 0.5,
    win_rate: float = 0.8,
) -> EvalResults:
    baseline = _arm(pass_rate=baseline_pass_rate)
    candidate = _arm(pass_rate=candidate_pass_rate)
    candidate.arm = "candidate"
    sr = ScenarioResult(
        scenario_id="s1",
        level="unit",
        held_out=False,
        tags=[],
        difficulty=None,
        baseline=baseline,
        candidate=candidate,
        outcome="candidate_win",
    )
    return EvalResults(
        suite_path="suite.yaml",
        baseline_resource="b.md",
        candidate_resource="c.md",
        timestamp="2026-05-08T00:00:00+00:00",
        scenarios=[sr],
        win_rate=win_rate,
        baseline_pass_rate=baseline_pass_rate,
        candidate_pass_rate=candidate_pass_rate,
        no_decision_rate=0.0,
        held_out=None,
        by_level={},
        by_tag={},
        total_tokens=12_345,
    )


def _make_orchestrator(
    tmp_path: Path, *, resources: list[dict[str, Any]]
) -> MultiResourceOrchestrator:
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
    orch._progress = progress
    state = MagicMock()
    state.eval_suite_path = "eval/eval-suite.yaml"
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

    suite = tmp_path / "eval/eval-suite.yaml"
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text("version: '1.0'\nscenarios: []\nconfig: {}\n")

    return orch


class _RecordingSpan:
    """Span double that records every set_attribute call for assertions."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, *args: Any, **kwargs: Any) -> None:
        pass


# =============================================================================
# Tests for the eval_phase_span helper directly
# =============================================================================


class TestEvalPhaseSpanHelper:
    @pytest.mark.asyncio
    async def test_no_op_when_tracer_import_fails(self) -> None:
        """Importing the tracer raises → context manager yields _NoOpSpan,
        and ``async with`` exits cleanly without re-raising."""
        with patch(
            "builtins.__import__",
            side_effect=ImportError("simulated"),
        ):
            async with eval_phase_span(
                "test", task_id="abc", phase="EVAL_DESIGN"
            ) as span:
                assert isinstance(span, _NoOpSpan)
                # No-op set_attribute MUST NOT raise.
                span.set_attribute("k", "v")

    @pytest.mark.asyncio
    async def test_no_op_when_tracer_get_fails(self) -> None:
        """get_tracer() raising → degrade to NoOp."""
        with patch(
            "harness.tracer.get_tracer", side_effect=RuntimeError("no exporter")
        ):
            async with eval_phase_span(
                "test", task_id="abc", phase="EVAL_DESIGN"
            ) as span:
                assert isinstance(span, _NoOpSpan)

    @pytest.mark.asyncio
    async def test_no_op_when_async_span_missing(self) -> None:
        """Tracer instance without async_span attr → degrade to NoOp."""
        mock_tracer = MagicMock(spec=[])  # spec=[] means no attributes
        with patch("harness.tracer.get_tracer", return_value=mock_tracer):
            async with eval_phase_span(
                "test", task_id="abc", phase="EVAL_DESIGN"
            ) as span:
                assert isinstance(span, _NoOpSpan)

    @pytest.mark.asyncio
    async def test_initial_attributes_passed_to_tracer(self) -> None:
        """When the tracer is available, initial attributes flow through."""
        captured_attrs: dict[str, Any] = {}

        class _FakeAsyncSpan:
            async def __aenter__(self) -> _RecordingSpan:
                return _RecordingSpan("test")

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            captured_attrs.update(attributes)
            return _FakeAsyncSpan()

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span
        with patch("harness.tracer.get_tracer", return_value=mock_tracer):
            async with eval_phase_span(
                "test",
                task_id="abc123",
                phase="EXECUTION_EVAL",
                extra={"harness.eval.resource_path": "agents/x.md"},
            ):
                pass

        assert captured_attrs["harness.eval.task_id"] == "abc123"
        assert captured_attrs["harness.eval.phase"] == "EXECUTION_EVAL"
        assert captured_attrs["harness.eval.resource_path"] == "agents/x.md"


class TestNewEvalTaskId:
    def test_format_and_uniqueness(self) -> None:
        a = new_eval_task_id()
        b = new_eval_task_id()
        assert len(a) == 16
        assert all(c in "0123456789abcdef" for c in a)
        assert a != b


# =============================================================================
# EXECUTION_EVAL — verify per-resource sub-span attributes
# =============================================================================


class TestExecutionEvalSpanAttributes:
    @pytest.mark.asyncio
    async def test_resource_span_promotion_outcome(
        self, tmp_path: Path
    ) -> None:
        """When a candidate promotes, the per-resource span gets
        ``harness.eval.outcome=promoted`` plus pass-rate attributes."""
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1, "type": "agent"}],
        )
        results = _eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)

        recorded_spans: list[_RecordingSpan] = []

        class _CapturingAsyncSpan:
            def __init__(self, name: str, attrs: dict[str, Any]) -> None:
                self.span = _RecordingSpan(name)
                # Initial attributes get pre-populated on the recording span.
                for k, v in attrs.items():
                    self.span.set_attribute(k, v)

            async def __aenter__(self) -> _RecordingSpan:
                recorded_spans.append(self.span)
                return self.span

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            return _CapturingAsyncSpan(name, attributes)

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span

        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)

        with patch(
            "harness.tracer.get_tracer", return_value=mock_tracer
        ), patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Two spans: parent ("eval.execution") and per-resource ("eval.execution.resource").
        assert any(s.name == "eval.execution" for s in recorded_spans)
        resource_spans = [s for s in recorded_spans if s.name == "eval.execution.resource"]
        assert len(resource_spans) == 1
        rs = resource_spans[0]
        assert rs.attributes["harness.eval.resource_path"] == "agents/iac.md"
        assert rs.attributes["harness.eval.resource_type"] == "agent"
        assert rs.attributes["harness.eval.resource_version"] == 1
        assert rs.attributes["harness.eval.outcome"] == "promoted"
        assert rs.attributes["harness.eval.candidate_pass_rate"] == 0.9
        assert rs.attributes["harness.eval.baseline_pass_rate"] == 0.5
        assert rs.attributes["harness.eval.win_rate"] == 0.8
        # Parent and child task_ids should match.
        parent = next(s for s in recorded_spans if s.name == "eval.execution")
        assert (
            rs.attributes["harness.eval.task_id"]
            == parent.attributes["harness.eval.task_id"]
        )

    @pytest.mark.asyncio
    async def test_resource_span_regression_outcome(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )
        results = _eval_results(candidate_pass_rate=0.3, baseline_pass_rate=0.7)

        recorded_spans: list[_RecordingSpan] = []

        class _CapturingAsyncSpan:
            def __init__(self, name: str, attrs: dict[str, Any]) -> None:
                self.span = _RecordingSpan(name)
                for k, v in attrs.items():
                    self.span.set_attribute(k, v)

            async def __aenter__(self) -> _RecordingSpan:
                recorded_spans.append(self.span)
                return self.span

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            return _CapturingAsyncSpan(name, attributes)

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)

        with patch(
            "harness.tracer.get_tracer", return_value=mock_tracer
        ), patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        rs = next(
            s for s in recorded_spans if s.name == "eval.execution.resource"
        )
        assert rs.attributes["harness.eval.outcome"] == "regressed"

    @pytest.mark.asyncio
    async def test_resource_span_error_outcome(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            resources=[{"path": "agents/iac.md", "version": 1}],
        )

        recorded_spans: list[_RecordingSpan] = []

        class _CapturingAsyncSpan:
            def __init__(self, name: str, attrs: dict[str, Any]) -> None:
                self.span = _RecordingSpan(name)
                for k, v in attrs.items():
                    self.span.set_attribute(k, v)

            async def __aenter__(self) -> _RecordingSpan:
                recorded_spans.append(self.span)
                return self.span

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            return _CapturingAsyncSpan(name, attributes)

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(side_effect=RuntimeError("kaboom"))

        with patch(
            "harness.tracer.get_tracer", return_value=mock_tracer
        ), patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        rs = next(s for s in recorded_spans if s.name == "eval.execution.resource")
        assert rs.attributes["harness.eval.outcome"] == "error"
        assert "kaboom" in rs.attributes["harness.eval.error"]

    @pytest.mark.asyncio
    async def test_phase_runs_when_tracer_unavailable(
        self, tmp_path: Path
    ) -> None:
        """Tracer broken → phase still runs; promotions still happen.

        Phase-A.6 telemetry continues unaffected; only the spans degrade
        to NoOp."""
        orch = _make_orchestrator(
            tmp_path, resources=[{"path": "agents/iac.md", "version": 1}]
        )
        results = _eval_results(candidate_pass_rate=0.9, baseline_pass_rate=0.5)
        mock_harness = MagicMock()
        mock_harness.run = AsyncMock(return_value=results)

        with patch(
            "harness.tracer.get_tracer", side_effect=RuntimeError("no tracer")
        ), patch(
            "harness.optimization._orchestrator_phases.execution_eval.EvalHarness",
            return_value=mock_harness,
        ):
            await orch._run_execution_eval()

        # Resource still promoted despite tracer failure.
        assert orch._state.resources["agents/iac.md"].status == "optimized"


class TestEvalDesignSpanAttributes:
    @pytest.mark.asyncio
    async def test_eval_design_span_outcome_success(
        self, tmp_path: Path
    ) -> None:
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
        state.get_generated_resources = MagicMock(
            return_value=[
                MagicMock(
                    spec=ResourceStatus,
                    path="agents/x.md",
                    resource_type="agent",
                )
            ]
        )
        orch._state = state

        # Architect "writes" the suite to disk.
        suite = tmp_path / "eval" / "eval-suite.yaml"
        suite.parent.mkdir(parents=True, exist_ok=True)
        suite.write_text("version: '1.0'\nscenarios: []\nconfig: {}\n")

        recorded_spans: list[_RecordingSpan] = []

        class _CapturingAsyncSpan:
            def __init__(self, name: str, attrs: dict[str, Any]) -> None:
                self.span = _RecordingSpan(name)
                for k, v in attrs.items():
                    self.span.set_attribute(k, v)

            async def __aenter__(self) -> _RecordingSpan:
                recorded_spans.append(self.span)
                return self.span

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            return _CapturingAsyncSpan(name, attributes)

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span

        with patch(
            "harness.tracer.get_tracer", return_value=mock_tracer
        ), patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value="[EVAL_DESIGN_COMPLETE]"),
        ):
            await orch._delegate_eval_design()

        # One span recorded; outcome is success since suite was written.
        spans = [s for s in recorded_spans if s.name == "eval.design"]
        assert len(spans) == 1
        s = spans[0]
        assert s.attributes["harness.eval.phase"] == "EVAL_DESIGN"
        assert s.attributes["harness.eval.outcome"] == "success"
        assert s.attributes["harness.eval.resource_count"] == 1
        # task_id is a 16-char hex string.
        assert len(s.attributes["harness.eval.task_id"]) == 16

    @pytest.mark.asyncio
    async def test_eval_design_skipped_outcome(self, tmp_path: Path) -> None:
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
        state.get_generated_resources = MagicMock(return_value=[])  # no resources
        orch._state = state

        recorded_spans: list[_RecordingSpan] = []

        class _CapturingAsyncSpan:
            def __init__(self, name: str, attrs: dict[str, Any]) -> None:
                self.span = _RecordingSpan(name)
                for k, v in attrs.items():
                    self.span.set_attribute(k, v)

            async def __aenter__(self) -> _RecordingSpan:
                recorded_spans.append(self.span)
                return self.span

            async def __aexit__(self, *args: Any) -> None:
                pass

        def fake_async_span(name: str, kind: Any, attributes: dict[str, Any]) -> Any:
            return _CapturingAsyncSpan(name, attributes)

        mock_tracer = MagicMock()
        mock_tracer.async_span = fake_async_span

        with patch("harness.tracer.get_tracer", return_value=mock_tracer):
            await orch._delegate_eval_design()

        s = next(s for s in recorded_spans if s.name == "eval.design")
        assert s.attributes["harness.eval.outcome"] == "skipped"
