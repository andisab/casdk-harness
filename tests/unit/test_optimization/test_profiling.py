"""Unit tests for CGF profiling infrastructure."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from harness.optimization.profiling import (
    PerformanceReport,
    PhaseMetrics,
    PipelineProfiler,
    ProfilerContext,
    ReportGenerator,
)
from harness.optimization.profiling.profiler import ProfilePhase


class TestPhaseMetrics:
    """Tests for PhaseMetrics dataclass."""

    def test_creation_with_defaults(self) -> None:
        """PhaseMetrics initializes with sensible defaults."""
        metrics = PhaseMetrics(phase=ProfilePhase.INIT)

        assert metrics.phase == ProfilePhase.INIT
        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.duration_seconds == 0.0
        assert metrics.api_calls == 0
        assert metrics.tokens_input == 0
        assert metrics.tokens_output == 0
        assert metrics.agent_invocations == 0
        assert metrics.test_executions == 0
        assert metrics.iterations == 0
        assert metrics.errors == 0
        assert metrics.metadata == {}

    def test_to_dict_serialization(self) -> None:
        """PhaseMetrics converts to dictionary correctly."""
        now = datetime.now()
        metrics = PhaseMetrics(
            phase=ProfilePhase.OPTIMIZE,
            start_time=now,
            end_time=now,
            duration_seconds=10.5,
            api_calls=5,
            tokens_input=1000,
            tokens_output=500,
            iterations=3,
        )

        result = metrics.to_dict()

        assert result["phase"] == "optimize"
        assert result["duration_seconds"] == 10.5
        assert result["api_calls"] == 5
        assert result["tokens_input"] == 1000
        assert result["tokens_output"] == 500
        assert result["iterations"] == 3


class TestProfilerContext:
    """Tests for ProfilerContext."""

    def test_record_api_call(self) -> None:
        """ProfilerContext tracks API calls and tokens."""
        metrics = PhaseMetrics(phase=ProfilePhase.OPTIMIZE)
        ctx = ProfilerContext(metrics=metrics)

        ctx.record_api_call(tokens_input=100, tokens_output=50)
        ctx.record_api_call(tokens_input=200, tokens_output=100)

        assert metrics.api_calls == 2
        assert metrics.tokens_input == 300
        assert metrics.tokens_output == 150

    def test_record_agent_invocation(self) -> None:
        """ProfilerContext tracks agent invocations."""
        metrics = PhaseMetrics(phase=ProfilePhase.RESEARCH)
        ctx = ProfilerContext(metrics=metrics)

        ctx.record_agent_invocation()
        ctx.record_agent_invocation()

        assert metrics.agent_invocations == 2

    def test_record_test_execution(self) -> None:
        """ProfilerContext tracks test executions."""
        metrics = PhaseMetrics(phase=ProfilePhase.TEST_GEN)
        ctx = ProfilerContext(metrics=metrics)

        ctx.record_test_execution(count=5)
        ctx.record_test_execution(count=3)

        assert metrics.test_executions == 8

    def test_record_iteration(self) -> None:
        """ProfilerContext tracks optimization iterations."""
        metrics = PhaseMetrics(phase=ProfilePhase.OPTIMIZE)
        ctx = ProfilerContext(metrics=metrics)

        ctx.record_iteration()
        ctx.record_iteration()
        ctx.record_iteration()

        assert metrics.iterations == 3

    def test_record_error(self) -> None:
        """ProfilerContext tracks errors."""
        metrics = PhaseMetrics(phase=ProfilePhase.EVALUATE)
        ctx = ProfilerContext(metrics=metrics)

        ctx.record_error()

        assert metrics.errors == 1

    def test_add_metadata(self) -> None:
        """ProfilerContext stores custom metadata."""
        metrics = PhaseMetrics(phase=ProfilePhase.FINALIZE)
        ctx = ProfilerContext(metrics=metrics)

        ctx.add_metadata("best_score", 0.85)
        ctx.add_metadata("strategy", "prompt_optimization")

        assert metrics.metadata["best_score"] == 0.85
        assert metrics.metadata["strategy"] == "prompt_optimization"

    def test_finalize_sets_end_time_and_duration(self) -> None:
        """ProfilerContext.finalize() calculates duration."""
        metrics = PhaseMetrics(phase=ProfilePhase.INIT)
        ctx = ProfilerContext(metrics=metrics)

        ctx.finalize()

        assert metrics.end_time is not None
        assert metrics.duration_seconds >= 0


class TestPipelineProfiler:
    """Tests for PipelineProfiler."""

    def test_initialization(self) -> None:
        """PipelineProfiler initializes with run_id."""
        profiler = PipelineProfiler(run_id="test_run_123")

        assert profiler.run_id == "test_run_123"
        assert profiler.start_time is not None
        assert profiler.end_time is None
        assert profiler.phases == {}

    def test_phase_context_manager(self) -> None:
        """PipelineProfiler.phase() works as context manager."""
        profiler = PipelineProfiler(run_id="test_run")

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            ctx.record_api_call(tokens_input=500)

        assert ProfilePhase.RESEARCH in profiler.phases
        metrics = profiler.phases[ProfilePhase.RESEARCH]
        assert metrics.api_calls == 1
        assert metrics.tokens_input == 500

    def test_multiple_phases(self) -> None:
        """PipelineProfiler tracks multiple phases."""
        profiler = PipelineProfiler(run_id="test_run")

        with profiler.phase(ProfilePhase.INIT) as ctx:
            ctx.record_agent_invocation()

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            ctx.record_api_call(tokens_input=1000)

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_iteration()
            ctx.record_iteration()

        assert len(profiler.phases) == 3
        assert profiler.phases[ProfilePhase.INIT].agent_invocations == 1
        assert profiler.phases[ProfilePhase.RESEARCH].api_calls == 1
        assert profiler.phases[ProfilePhase.OPTIMIZE].iterations == 2

    def test_get_total_tokens(self) -> None:
        """PipelineProfiler.get_total_tokens() sums across phases."""
        profiler = PipelineProfiler(run_id="test_run")

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            ctx.record_api_call(tokens_input=500, tokens_output=200)

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_api_call(tokens_input=1000, tokens_output=400)

        input_total, output_total = profiler.get_total_tokens()

        assert input_total == 1500
        assert output_total == 600

    def test_get_total_api_calls(self) -> None:
        """PipelineProfiler.get_total_api_calls() sums across phases."""
        profiler = PipelineProfiler(run_id="test_run")

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            ctx.record_api_call()
            ctx.record_api_call()

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_api_call()

        assert profiler.get_total_api_calls() == 3

    def test_get_summary(self) -> None:
        """PipelineProfiler.get_summary() returns structured summary."""
        profiler = PipelineProfiler(run_id="test_summary")

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_api_call(tokens_input=1000, tokens_output=500)
            ctx.record_iteration()
            ctx.record_test_execution(count=10)

        profiler.finalize()
        summary = profiler.get_summary()

        assert summary["run_id"] == "test_summary"
        assert summary["total_api_calls"] == 1
        assert summary["total_tokens_input"] == 1000
        assert summary["total_tokens_output"] == 500
        assert summary["total_tokens"] == 1500
        assert summary["total_iterations"] == 1
        assert summary["total_test_executions"] == 10
        assert "optimize" in summary["phases"]

    def test_record_api_call_outside_phase(self) -> None:
        """PipelineProfiler.record_api_call() works outside context."""
        profiler = PipelineProfiler(run_id="test_run")

        # Call without active phase should not crash
        profiler.record_api_call(tokens_input=100)

        # No phases recorded yet
        assert len(profiler.phases) == 0


class TestPerformanceReport:
    """Tests for PerformanceReport."""

    def test_creation_with_defaults(self) -> None:
        """PerformanceReport initializes with defaults."""
        report = PerformanceReport(run_id="test_report")

        assert report.run_id == "test_report"
        assert report.total_duration == 0.0
        assert report.phase_breakdown == {}
        assert report.token_usage == {}
        assert report.recommendations == []

    def test_to_dict(self) -> None:
        """PerformanceReport.to_dict() serializes correctly."""
        report = PerformanceReport(
            run_id="test_report",
            total_duration=120.5,
            token_usage={"input": 1000, "output": 500, "total": 1500},
            recommendations=["Optimize phase X"],
        )

        result = report.to_dict()

        assert result["run_id"] == "test_report"
        assert result["total_duration"] == 120.5
        assert result["token_usage"]["total"] == 1500
        assert "Optimize phase X" in result["recommendations"]

    def test_to_json(self) -> None:
        """PerformanceReport.to_json() produces valid JSON."""
        report = PerformanceReport(
            run_id="test_json",
            total_duration=60.0,
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["run_id"] == "test_json"
        assert parsed["total_duration"] == 60.0

    def test_to_markdown(self) -> None:
        """PerformanceReport.to_markdown() produces markdown output."""
        report = PerformanceReport(
            run_id="test_markdown",
            total_duration=120.0,
            token_usage={"input": 1000, "output": 500, "total": 1500},
            api_metrics={"total_calls": 10},
            agent_metrics={"total": 5},
            test_metrics={"total": 20},
            phase_breakdown={
                "optimize": {
                    "duration_seconds": 100.0,
                    "duration_percent": 83.3,
                    "api_calls": 8,
                    "tokens_input": 800,
                    "tokens_output": 400,
                }
            },
            recommendations=["Consider caching"],
        )

        md = report.to_markdown()

        assert "# Performance Report: test_markdown" in md
        assert "| Total Duration | 120.00s |" in md
        assert "| Total Tokens | 1,500 |" in md
        assert "## Phase Breakdown" in md
        assert "optimize" in md
        assert "## Recommendations" in md
        assert "Consider caching" in md


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def test_generate_from_profiler(self) -> None:
        """ReportGenerator generates report from profiler data."""
        profiler = PipelineProfiler(run_id="test_gen")

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            ctx.record_api_call(tokens_input=500, tokens_output=200)

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_iteration()
            ctx.record_api_call(tokens_input=1000, tokens_output=400)

        profiler.finalize()

        generator = ReportGenerator(profiler)
        report = generator.generate()

        assert report.run_id == "test_gen"
        assert report.token_usage["input"] == 1500
        assert report.token_usage["output"] == 600
        assert report.token_usage["total"] == 2100
        assert report.api_metrics["total_calls"] == 2

    def test_save_json(self) -> None:
        """ReportGenerator.save_json() writes JSON file."""
        profiler = PipelineProfiler(run_id="test_save_json")

        with profiler.phase(ProfilePhase.INIT) as ctx:
            ctx.record_agent_invocation()

        profiler.finalize()

        generator = ReportGenerator(profiler)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            generator.save_json(output_path)

            assert output_path.exists()
            content = json.loads(output_path.read_text())
            assert content["run_id"] == "test_save_json"

    def test_save_markdown(self) -> None:
        """ReportGenerator.save_markdown() writes Markdown file."""
        profiler = PipelineProfiler(run_id="test_save_md")

        with profiler.phase(ProfilePhase.INIT) as ctx:
            ctx.record_agent_invocation()

        profiler.finalize()

        generator = ReportGenerator(profiler)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            generator.save_markdown(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "# Performance Report: test_save_md" in content

    def test_save_all(self) -> None:
        """ReportGenerator.save_all() writes both formats."""
        profiler = PipelineProfiler(run_id="test_save_all")

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_iteration()

        profiler.finalize()

        generator = ReportGenerator(profiler)

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "report"
            generator.save_all(base_path)

            json_path = Path(tmpdir) / "report.json"
            md_path = Path(tmpdir) / "report.md"

            assert json_path.exists()
            assert md_path.exists()

    def test_recommendations_slow_phase(self) -> None:
        """ReportGenerator adds recommendation for slow phases."""
        profiler = PipelineProfiler(run_id="test_slow_phase")

        # Create a phase with metrics that appear slow
        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            ctx.record_iteration()

        # Set duration after context manager exits to avoid overwrite
        profiler.phases[ProfilePhase.OPTIMIZE].duration_seconds = 120.0

        profiler.finalize()

        generator = ReportGenerator(profiler)
        report = generator.generate()

        # Should have recommendation about slow phase
        slow_rec = [
            r for r in report.recommendations if "optimize" in r.lower()
        ]
        assert len(slow_rec) > 0

    def test_recommendations_high_token_usage(self) -> None:
        """ReportGenerator adds recommendation for high token usage."""
        profiler = PipelineProfiler(run_id="test_high_tokens")

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            # Record high token usage
            ctx.record_api_call(tokens_input=80000, tokens_output=30000)

        profiler.finalize()

        generator = ReportGenerator(profiler)
        report = generator.generate()

        # Should have recommendation about tokens
        token_rec = [r for r in report.recommendations if "token" in r.lower()]
        assert len(token_rec) > 0

    def test_recommendations_no_issues(self) -> None:
        """ReportGenerator gives positive feedback when no issues."""
        profiler = PipelineProfiler(run_id="test_good")

        with profiler.phase(ProfilePhase.INIT) as ctx:
            ctx.record_api_call(tokens_input=100, tokens_output=50)

        profiler.finalize()

        generator = ReportGenerator(profiler)
        report = generator.generate()

        # Should have positive recommendation
        assert any("good" in r.lower() for r in report.recommendations)
