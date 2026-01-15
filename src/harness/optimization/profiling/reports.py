"""Performance report generation for CGF optimization pipeline.

Generates human-readable and machine-parseable reports from profiling data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.profiling.profiler import PipelineProfiler

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceReport:
    """Performance report for an optimization run.

    Attributes:
        run_id: Unique identifier for the run.
        generated_at: When the report was generated.
        total_duration: Total pipeline duration in seconds.
        phase_breakdown: Duration breakdown by phase.
        token_usage: Token usage statistics.
        api_metrics: API call metrics.
        agent_metrics: Agent invocation metrics.
        test_metrics: Test execution metrics.
        optimization_metrics: Optimization-specific metrics.
        recommendations: Performance improvement recommendations.
    """

    run_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    total_duration: float = 0.0
    phase_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
    api_metrics: dict[str, Any] = field(default_factory=dict)
    agent_metrics: dict[str, Any] = field(default_factory=dict)
    test_metrics: dict[str, Any] = field(default_factory=dict)
    optimization_metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "total_duration": self.total_duration,
            "phase_breakdown": self.phase_breakdown,
            "token_usage": self.token_usage,
            "api_metrics": self.api_metrics,
            "agent_metrics": self.agent_metrics,
            "test_metrics": self.test_metrics,
            "optimization_metrics": self.optimization_metrics,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate markdown report.

        Returns:
            Markdown formatted report.
        """
        lines = [
            f"# Performance Report: {self.run_id}",
            "",
            f"Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Duration | {self.total_duration:.2f}s |",
            f"| Total API Calls | {self.api_metrics.get('total_calls', 0)} |",
            f"| Total Tokens | {self.token_usage.get('total', 0):,} |",
            f"| Agent Invocations | {self.agent_metrics.get('total', 0)} |",
            f"| Test Executions | {self.test_metrics.get('total', 0)} |",
            "",
            "## Phase Breakdown",
            "",
            "| Phase | Duration | % of Total | API Calls | Tokens |",
            "|-------|----------|------------|-----------|--------|",
        ]

        for phase, data in self.phase_breakdown.items():
            duration = data.get("duration_seconds", 0)
            pct = data.get("duration_percent", 0)
            api_calls = data.get("api_calls", 0)
            tokens = data.get("tokens_input", 0) + data.get("tokens_output", 0)
            lines.append(
                f"| {phase} | {duration:.2f}s | {pct:.1f}% "
                f"| {api_calls} | {tokens:,} |"
            )

        lines.extend([
            "",
            "## Token Usage",
            "",
            "| Type | Count |",
            "|------|-------|",
            f"| Input Tokens | {self.token_usage.get('input', 0):,} |",
            f"| Output Tokens | {self.token_usage.get('output', 0):,} |",
            f"| Total Tokens | {self.token_usage.get('total', 0):,} |",
        ])

        if self.optimization_metrics:
            iters = self.optimization_metrics.get("iterations", 0)
            avg_time = self.optimization_metrics.get("avg_iteration_time", 0)
            best = self.optimization_metrics.get("best_score", 0)
            improve = self.optimization_metrics.get("improvement_percent", 0)
            lines.extend([
                "",
                "## Optimization Metrics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Iterations | {iters} |",
                f"| Avg Iteration Time | {avg_time:.2f}s |",
                f"| Best Score | {best:.3f} |",
                f"| Improvement | {improve:.1f}% |",
            ])

        if self.recommendations:
            lines.extend([
                "",
                "## Recommendations",
                "",
            ])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class ReportGenerator:
    """Generates performance reports from profiler data.

    Example:
        profiler = PipelineProfiler(run_id="opt_123")
        # ... run pipeline with profiling ...

        generator = ReportGenerator(profiler)
        report = generator.generate()

        # Save reports
        generator.save_json("workspace/reports/perf_report.json")
        generator.save_markdown("workspace/reports/perf_report.md")
    """

    # Thresholds for generating recommendations
    SLOW_PHASE_THRESHOLD = 60.0  # seconds
    HIGH_TOKEN_THRESHOLD = 100000  # tokens
    MANY_API_CALLS_THRESHOLD = 50  # calls
    SLOW_ITERATION_THRESHOLD = 30.0  # seconds per iteration

    def __init__(self, profiler: PipelineProfiler) -> None:
        """Initialize the report generator.

        Args:
            profiler: Pipeline profiler with collected data.
        """
        self.profiler = profiler
        self._report: PerformanceReport | None = None

    def generate(self) -> PerformanceReport:
        """Generate performance report from profiler data.

        Returns:
            PerformanceReport with all metrics and recommendations.
        """
        summary = self.profiler.get_summary()

        report = PerformanceReport(
            run_id=self.profiler.run_id,
            total_duration=summary["total_duration_seconds"],
            phase_breakdown=summary["phases"],
            token_usage={
                "input": summary["total_tokens_input"],
                "output": summary["total_tokens_output"],
                "total": summary["total_tokens"],
            },
            api_metrics={
                "total_calls": summary["total_api_calls"],
                "calls_per_second": (
                    summary["total_api_calls"] /
                    summary["total_duration_seconds"]
                    if summary["total_duration_seconds"] > 0 else 0
                ),
            },
            agent_metrics={
                "total": summary["total_agent_invocations"],
            },
            test_metrics={
                "total": summary["total_test_executions"],
            },
        )

        # Add optimization-specific metrics if available
        optimize_phase = summary["phases"].get("optimize", {})
        if optimize_phase:
            iterations = optimize_phase.get("iterations", 0)
            duration = optimize_phase.get("duration_seconds", 0)

            report.optimization_metrics = {
                "iterations": iterations,
                "avg_iteration_time": (
                    duration / iterations if iterations > 0 else 0
                ),
                "total_optimize_time": duration,
            }

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        self._report = report
        return report

    def _generate_recommendations(
        self, report: PerformanceReport
    ) -> list[str]:
        """Generate performance improvement recommendations.

        Args:
            report: The performance report.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # Check for slow phases
        for phase, data in report.phase_breakdown.items():
            duration = data.get("duration_seconds", 0)
            if duration > self.SLOW_PHASE_THRESHOLD:
                recommendations.append(
                    f"Phase '{phase}' took {duration:.1f}s. "
                    f"Consider optimizing or parallelizing this phase."
                )

        # Check token usage
        if report.token_usage.get("total", 0) > self.HIGH_TOKEN_THRESHOLD:
            total = report.token_usage["total"]
            recommendations.append(
                f"High token usage ({total:,} tokens). "
                f"Consider enabling prompt caching or reducing context size."
            )

        # Check API call volume
        total_calls = report.api_metrics.get("total_calls", 0)
        if total_calls > self.MANY_API_CALLS_THRESHOLD:
            recommendations.append(
                f"High API call count ({total_calls} calls). "
                f"Consider batching operations or caching responses."
            )

        # Check iteration time
        avg_iter_time = report.optimization_metrics.get(
            "avg_iteration_time", 0
        )
        if avg_iter_time > self.SLOW_ITERATION_THRESHOLD:
            recommendations.append(
                "Slow optimization iterations "
                f"({avg_iter_time:.1f}s avg). "
                "Consider reducing test suite size "
                "or parallelizing evaluation."
            )

        # Check for errors
        total_errors = sum(
            data.get("errors", 0)
            for data in report.phase_breakdown.values()
        )
        if total_errors > 0:
            recommendations.append(
                f"Encountered {total_errors} error(s). "
                f"Review error logs to identify and fix issues."
            )

        if not recommendations:
            recommendations.append(
                "Performance looks good! "
                "No immediate optimizations recommended."
            )

        return recommendations

    def save_json(self, path: str | Path) -> None:
        """Save report as JSON file.

        Args:
            path: Output file path.
        """
        if self._report is None:
            self._report = self.generate()

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._report.to_json())

        logger.info("Performance report saved", path=str(path), format="json")

    def save_markdown(self, path: str | Path) -> None:
        """Save report as Markdown file.

        Args:
            path: Output file path.
        """
        if self._report is None:
            self._report = self.generate()

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._report.to_markdown())

        logger.info(
            "Performance report saved",
            path=str(path),
            format="markdown",
        )

    def save_all(self, base_path: str | Path) -> None:
        """Save report in all formats.

        Args:
            base_path: Base path without extension.
        """
        base = Path(base_path)
        self.save_json(base.with_suffix(".json"))
        self.save_markdown(base.with_suffix(".md"))
