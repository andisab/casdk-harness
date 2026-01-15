"""Pipeline profiler for timing and resource tracking.

Provides context managers and decorators for profiling CGF pipeline
execution, including per-phase timing, API token usage, and agent
invocation counts.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ProfilePhase(str, Enum):
    """Pipeline phases that can be profiled."""

    INIT = "init"
    RESEARCH = "research"
    TEST_GEN = "test_gen"
    OPTIMIZE = "optimize"
    EVALUATE = "evaluate"
    FINALIZE = "finalize"
    COMPLETE = "complete"


@dataclass
class PhaseMetrics:
    """Metrics collected for a single pipeline phase.

    Attributes:
        phase: The pipeline phase.
        start_time: When the phase started.
        end_time: When the phase ended.
        duration_seconds: Total duration in seconds.
        api_calls: Number of API calls made.
        tokens_input: Total input tokens used.
        tokens_output: Total output tokens generated.
        agent_invocations: Number of agent invocations.
        test_executions: Number of test case executions.
        iterations: Number of optimization iterations (if applicable).
        errors: Number of errors encountered.
        metadata: Additional phase-specific data.
    """

    phase: ProfilePhase
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    api_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    agent_invocations: int = 0
    test_executions: int = 0
    iterations: int = 0
    errors: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": self.phase.value,
            "start_time": (
                self.start_time.isoformat() if self.start_time else None
            ),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "api_calls": self.api_calls,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "agent_invocations": self.agent_invocations,
            "test_executions": self.test_executions,
            "iterations": self.iterations,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class ProfilerContext:
    """Context for tracking metrics within a profiled scope.

    Provides methods to record various metrics during execution.
    """

    metrics: PhaseMetrics
    _start_time: float = field(default_factory=time.perf_counter)

    def record_api_call(
        self,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        """Record an API call with token usage.

        Args:
            tokens_input: Number of input tokens.
            tokens_output: Number of output tokens.
        """
        self.metrics.api_calls += 1
        self.metrics.tokens_input += tokens_input
        self.metrics.tokens_output += tokens_output

    def record_agent_invocation(self) -> None:
        """Record an agent invocation."""
        self.metrics.agent_invocations += 1

    def record_test_execution(self, count: int = 1) -> None:
        """Record test case executions.

        Args:
            count: Number of test cases executed.
        """
        self.metrics.test_executions += count

    def record_iteration(self) -> None:
        """Record an optimization iteration."""
        self.metrics.iterations += 1

    def record_error(self) -> None:
        """Record an error occurrence."""
        self.metrics.errors += 1

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the phase metrics.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self.metrics.metadata[key] = value

    def finalize(self) -> None:
        """Finalize the context and calculate duration."""
        self.metrics.end_time = datetime.now()
        elapsed = time.perf_counter() - self._start_time
        self.metrics.duration_seconds = elapsed


class PipelineProfiler:
    """Profiler for CGF optimization pipeline.

    Tracks timing and resource usage across pipeline phases.

    Example:
        profiler = PipelineProfiler(run_id="opt_agent_20250115")

        with profiler.phase(ProfilePhase.RESEARCH) as ctx:
            # Perform research
            ctx.record_api_call(tokens_input=1000, tokens_output=500)
            ctx.record_agent_invocation()

        with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
            for i in range(iterations):
                ctx.record_iteration()
                ctx.record_api_call(tokens_input=2000, tokens_output=1000)

        # Get summary
        summary = profiler.get_summary()
        print(f"Total duration: {summary['total_duration_seconds']:.2f}s")
    """

    def __init__(self, run_id: str) -> None:
        """Initialize the profiler.

        Args:
            run_id: Unique identifier for the optimization run.
        """
        self.run_id = run_id
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.phases: dict[ProfilePhase, PhaseMetrics] = {}
        self._current_phase: ProfilePhase | None = None

    @contextmanager
    def phase(
        self, phase: ProfilePhase
    ) -> Generator[ProfilerContext, None, None]:
        """Context manager for profiling a pipeline phase.

        Args:
            phase: The pipeline phase to profile.

        Yields:
            ProfilerContext for recording metrics.

        Example:
            with profiler.phase(ProfilePhase.OPTIMIZE) as ctx:
                ctx.record_iteration()
                ctx.record_api_call(tokens_input=1000)
        """
        metrics = PhaseMetrics(phase=phase, start_time=datetime.now())
        self.phases[phase] = metrics
        self._current_phase = phase

        context = ProfilerContext(metrics=metrics)

        logger.debug(
            "Phase started",
            run_id=self.run_id,
            phase=phase.value,
        )

        try:
            yield context
        finally:
            context.finalize()
            self._current_phase = None

            logger.debug(
                "Phase completed",
                run_id=self.run_id,
                phase=phase.value,
                duration=f"{metrics.duration_seconds:.2f}s",
                api_calls=metrics.api_calls,
                tokens_total=metrics.tokens_input + metrics.tokens_output,
            )

    def record_api_call(
        self,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        """Record an API call in the current phase.

        Can be called outside a phase context for convenience.

        Args:
            tokens_input: Number of input tokens.
            tokens_output: Number of output tokens.
        """
        if self._current_phase and self._current_phase in self.phases:
            metrics = self.phases[self._current_phase]
            metrics.api_calls += 1
            metrics.tokens_input += tokens_input
            metrics.tokens_output += tokens_output

    def finalize(self) -> None:
        """Finalize the profiler and record end time."""
        self.end_time = datetime.now()

    def get_total_duration(self) -> float:
        """Get total pipeline duration in seconds.

        Returns:
            Total duration in seconds.
        """
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

    def get_total_tokens(self) -> tuple[int, int]:
        """Get total token usage across all phases.

        Returns:
            Tuple of (input_tokens, output_tokens).
        """
        input_total = sum(m.tokens_input for m in self.phases.values())
        output_total = sum(m.tokens_output for m in self.phases.values())
        return input_total, output_total

    def get_total_api_calls(self) -> int:
        """Get total API calls across all phases.

        Returns:
            Total number of API calls.
        """
        return sum(m.api_calls for m in self.phases.values())

    def get_summary(self) -> dict[str, Any]:
        """Get profiling summary.

        Returns:
            Dictionary with profiling summary data.
        """
        input_tokens, output_tokens = self.get_total_tokens()
        total_duration = self.get_total_duration()

        phases_summary = {}
        for phase, metrics in self.phases.items():
            phases_summary[phase.value] = {
                "duration_seconds": metrics.duration_seconds,
                "duration_percent": (
                    (metrics.duration_seconds / total_duration * 100)
                    if total_duration > 0 else 0
                ),
                "api_calls": metrics.api_calls,
                "tokens_input": metrics.tokens_input,
                "tokens_output": metrics.tokens_output,
                "agent_invocations": metrics.agent_invocations,
                "test_executions": metrics.test_executions,
                "iterations": metrics.iterations,
                "errors": metrics.errors,
            }

        return {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": (
                self.end_time.isoformat() if self.end_time else None
            ),
            "total_duration_seconds": total_duration,
            "total_api_calls": self.get_total_api_calls(),
            "total_tokens_input": input_tokens,
            "total_tokens_output": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "total_agent_invocations": sum(
                m.agent_invocations for m in self.phases.values()
            ),
            "total_test_executions": sum(
                m.test_executions for m in self.phases.values()
            ),
            "total_iterations": sum(
                m.iterations for m in self.phases.values()
            ),
            "total_errors": sum(m.errors for m in self.phases.values()),
            "phases": phases_summary,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert profiler data to dictionary for serialization.

        Returns:
            Dictionary with all profiling data.
        """
        return {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": (
                self.end_time.isoformat() if self.end_time else None
            ),
            "phases": {
                phase.value: metrics.to_dict()
                for phase, metrics in self.phases.items()
            },
            "summary": self.get_summary(),
        }
