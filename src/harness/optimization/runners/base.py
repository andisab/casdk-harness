"""Base runner protocol and types for agent optimization.

Provides the foundation for executing agents on test cases with tracing,
feedback collection, and result aggregation.

Example usage:
    from harness.optimization.runners import RunnerProtocol, RunnerConfig

    class CustomRunner(RunnerProtocol):
        async def run_test_case(self, test_case, system_prompt_override=None):
            # Custom implementation
            pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from harness.optimization.testcases import SuiteResult, TestCase, TestResult, TestSuite


@dataclass
class RunnerConfig:
    """Configuration for test runners.

    Attributes:
        agent_name: Name of the agent to run.
        permission_mode: Permission mode for tools (default: acceptEdits).
        cwd: Working directory for agent execution.
        verbose: Whether to print progress during execution.
        collect_spans: Whether to collect spans for feedback.
        timeout_seconds: Default timeout per test case.
        max_concurrent: Max concurrent test case executions.
        eval_model: Override model for test evaluation (sonnet/haiku/opus).
    """

    agent_name: str
    permission_mode: str = "acceptEdits"
    cwd: str | None = None  # None means use current directory
    verbose: bool = False
    collect_spans: bool = True
    timeout_seconds: int = 300
    max_concurrent: int = 1
    eval_model: str | None = None  # Override model for test evaluation


@dataclass
class RunContext:
    """Context for a test run.

    Attributes:
        trace_id: Unique identifier for the trace.
        test_case_id: ID of the test case being run.
        start_time: When execution started.
        system_prompt: The system prompt used (may be overridden).
        metadata: Additional context metadata.
    """

    trace_id: str
    test_case_id: str
    start_time: float
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RunnerProtocol(Protocol):
    """Protocol defining the interface for test runners.

    Runners execute agents on test cases and collect results including:
    - Agent output text
    - Execution spans for feedback
    - Validation scores
    - Timing and resource metrics
    """

    async def run_test_case(
        self,
        test_case: TestCase,
        system_prompt_override: str | None = None,
    ) -> TestResult:
        """Run a single test case.

        Args:
            test_case: The test case to execute.
            system_prompt_override: Optional system prompt to use instead of default.

        Returns:
            TestResult with output, feedback, and score.
        """
        ...

    async def run_suite(
        self,
        suite: TestSuite,
        system_prompt_override: str | None = None,
    ) -> SuiteResult:
        """Run all test cases in a suite.

        Args:
            suite: The test suite to execute.
            system_prompt_override: Optional system prompt to use.

        Returns:
            SuiteResult with aggregated results and metrics.
        """
        ...


class BaseRunner(ABC):
    """Abstract base class for test runners.

    Provides common functionality for executing agents on test cases
    with tracing and feedback collection.
    """

    def __init__(self, config: RunnerConfig) -> None:
        """Initialize the runner.

        Args:
            config: Runner configuration.
        """
        self.config = config

    @abstractmethod
    async def run_test_case(
        self,
        test_case: TestCase,
        system_prompt_override: str | None = None,
    ) -> TestResult:
        """Run a single test case.

        Args:
            test_case: The test case to execute.
            system_prompt_override: Optional system prompt to use.

        Returns:
            TestResult with output, feedback, and score.
        """
        pass

    @abstractmethod
    async def run_suite(
        self,
        suite: TestSuite,
        system_prompt_override: str | None = None,
    ) -> SuiteResult:
        """Run all test cases in a suite.

        Args:
            suite: The test suite to execute.
            system_prompt_override: Optional system prompt to use.

        Returns:
            SuiteResult with aggregated results.
        """
        pass

    def _validate_agent_name(self, suite: TestSuite) -> None:
        """Validate that runner config matches suite agent.

        Args:
            suite: The test suite to validate against.

        Raises:
            ValueError: If agent names don't match.
        """
        if self.config.agent_name != suite.agent_name:
            raise ValueError(
                f"Runner configured for '{self.config.agent_name}' but "
                f"suite targets '{suite.agent_name}'"
            )
