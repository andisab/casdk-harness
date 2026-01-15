"""Test case models for agent optimization.

Defines dataclasses for test cases, test suites, validation configuration,
and test results used in the optimization pipeline.

Example usage:
    from harness.optimization.testcases import TestCase, TestSuite, ValidationConfig

    test_case = TestCase(
        id="sort-function",
        prompt="Write a Python function to sort a list",
        expected_behavior="Returns valid Python sort function",
        validation=ValidationConfig(type="contains", criteria="def "),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.optimization.adapters.base import AgentFeedback
    from harness.optimization.rewards import ResourceReward


class ValidationType(str, Enum):
    """Types of output validation."""

    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"
    LLM_JUDGE = "llm_judge"
    # Code-specific validators
    CODE = "code"  # Extract code, check syntax, then validate content
    CODE_SYNTAX = "code_syntax"  # Extract code and verify syntax only
    CODE_LLM = "code_llm"  # Extract code and use LLM judge on code only


@dataclass
class ValidationConfig:
    """Configuration for output validation.

    Attributes:
        type: Validation method (exact, contains, regex, llm_judge, code, etc.).
        criteria: Match criteria - exact string, substring, regex pattern,
            or LLM judge prompt.
        partial_credit: If True, allows partial scores (0.0-1.0).
            If False, only 0.0 or 1.0.
        language: Programming language for code validation (default: python).
        require_syntax_valid: If True, code must be syntactically valid to pass.
        min_code_lines: Minimum lines of code required (0 = no minimum).
    """

    type: ValidationType | str
    criteria: str
    partial_credit: bool = False
    # Code-specific validation options
    language: str = "python"
    require_syntax_valid: bool = True
    min_code_lines: int = 0

    def __post_init__(self) -> None:
        """Convert string type to enum if needed."""
        if isinstance(self.type, str):
            self.type = ValidationType(self.type.lower())


@dataclass
class TestCase:
    """Single test case for agent evaluation.

    Attributes:
        id: Unique identifier for this test case.
        prompt: Task prompt to send to the agent.
        expected_behavior: Human-readable description of expected behavior.
        validation: Configuration for validating agent output.
        timeout_seconds: Maximum time allowed for agent execution.
        tags: Optional tags for filtering test cases.
        metadata: Additional context or configuration.
    """

    id: str
    prompt: str
    expected_behavior: str
    validation: ValidationConfig
    timeout_seconds: int = 300
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Convert validation dict to ValidationConfig if needed."""
        if isinstance(self.validation, dict):
            self.validation = ValidationConfig(**self.validation)


@dataclass
class TestSuite:
    """Collection of test cases for an agent.

    Attributes:
        name: Suite name/identifier.
        description: Human-readable description.
        agent_name: Target agent for these tests.
        test_cases: List of test cases in this suite.
        version: Suite version for tracking changes.
        metadata: Additional suite-level configuration.
    """

    name: str
    agent_name: str
    test_cases: list[TestCase]
    description: str = ""
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Convert test case dicts to TestCase objects if needed."""
        converted = []
        for tc in self.test_cases:
            if isinstance(tc, dict):
                converted.append(TestCase(**tc))
            else:
                converted.append(tc)
        self.test_cases = converted

    def __len__(self) -> int:
        """Return number of test cases."""
        return len(self.test_cases)

    def __iter__(self):
        """Iterate over test cases."""
        return iter(self.test_cases)

    def filter_by_tags(self, tags: list[str]) -> list[TestCase]:
        """Filter test cases by tags.

        Args:
            tags: Tags to filter by. Returns test cases matching any tag.

        Returns:
            List of matching test cases.
        """
        return [tc for tc in self.test_cases if any(t in tc.tags for t in tags)]

    def get_by_id(self, test_id: str) -> TestCase | None:
        """Get test case by ID.

        Args:
            test_id: Test case ID to find.

        Returns:
            TestCase if found, None otherwise.
        """
        for tc in self.test_cases:
            if tc.id == test_id:
                return tc
        return None


@dataclass
class TestResult:
    """Result of running a single test case.

    Attributes:
        test_case_id: ID of the test case that was run.
        agent_name: Agent that executed the test.
        success: Whether the test passed validation.
        score: Validation score (0.0 - 1.0).
        output: Agent's final output text.
        trace_id: Trace ID for span lookup.
        feedback: AgentFeedback from adapter (optional).
        reward: Computed ResourceReward (optional).
        execution_time_ms: Wall-clock execution time.
        error: Error message if execution failed.
        timestamp: When the test was run.
    """

    test_case_id: str
    agent_name: str
    success: bool
    score: float
    output: str
    trace_id: str
    execution_time_ms: float
    feedback: AgentFeedback | None = None
    reward: ResourceReward | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the result.
        """
        result = {
            "test_case_id": self.test_case_id,
            "agent_name": self.agent_name,
            "success": self.success,
            "score": self.score,
            "output": self.output,
            "trace_id": self.trace_id,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.feedback is not None:
            result["feedback"] = self.feedback.to_reward()
        if self.reward is not None:
            result["reward"] = {
                "task_completion": self.reward.task_completion,
                "efficiency": self.reward.efficiency,
                "quality": self.reward.quality,
                "safety": self.reward.safety,
                "composite": self.reward.composite(),
            }
        return result


@dataclass
class SuiteResult:
    """Aggregated results from running a test suite.

    Attributes:
        suite_name: Name of the test suite.
        agent_name: Agent that was tested.
        results: Individual test results.
        total_score: Average score across all tests.
        pass_rate: Fraction of tests that passed.
        total_time_ms: Total execution time.
        timestamp: When the suite was run.
    """

    suite_name: str
    agent_name: str
    results: list[TestResult]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_score(self) -> float:
        """Calculate average score across all tests."""
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def pass_rate(self) -> float:
        """Calculate fraction of tests that passed."""
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.success)
        return passed / len(self.results)

    @property
    def total_time_ms(self) -> float:
        """Calculate total execution time."""
        return sum(r.execution_time_ms for r in self.results)

    @property
    def passed_count(self) -> int:
        """Count of passed tests."""
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        """Count of failed tests."""
        return sum(1 for r in self.results if not r.success)

    def get_failed_results(self) -> list[TestResult]:
        """Get all failed test results."""
        return [r for r in self.results if not r.success]

    def get_passed_results(self) -> list[TestResult]:
        """Get all passed test results."""
        return [r for r in self.results if r.success]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "suite_name": self.suite_name,
            "agent_name": self.agent_name,
            "total_score": self.total_score,
            "pass_rate": self.pass_rate,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "total_time_ms": self.total_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }
