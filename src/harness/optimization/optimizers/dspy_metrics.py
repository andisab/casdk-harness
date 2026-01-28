"""DSPy metric bridge for test suite validation.

Bridges CGF test suite validators to DSPy-compatible metric functions,
enabling MIPROv2 to optimize prompts using our validation infrastructure.

Example usage:
    from harness.optimization.optimizers.dspy_metrics import (
        TestSuiteMetric,
        create_dspy_metric,
    )

    metric = TestSuiteMetric(test_suite, resource)

    # Use with MIPROv2
    teleprompter = MIPROv2(metric=metric, ...)
    optimized = teleprompter.compile(module, trainset=trainset)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import structlog

if TYPE_CHECKING:
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestCase, TestSuite

logger = structlog.get_logger(__name__)

# Check DSPy availability
try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None  # type: ignore


@dataclass
class MetricResult:
    """Result from metric evaluation.

    Attributes:
        score: Normalized score between 0.0 and 1.0.
        passed: Whether the validation passed (score >= threshold).
        validator_type: Type of validator used.
        details: Additional details from validation.
    """
    score: float
    passed: bool
    validator_type: str
    details: str = ""


class TestSuiteMetric:
    """DSPy-compatible metric that uses CGF test suite validators.

    This class wraps our validation infrastructure to work with DSPy's
    MIPROv2 optimizer. It supports both deterministic and LLM-based
    validators.

    Key features:
    - Maps test prompts to their validators
    - Supports async validators via synchronous wrapper
    - Distinguishes deterministic vs LLM-judge validators
    - Provides aggregated scoring across test suite
    """

    def __init__(
        self,
        test_suite: TestSuite,
        resource: AgentResource | None = None,
        pass_threshold: float = 0.5,
        cache_validators: bool = True,
    ) -> None:
        """Initialize the metric.

        Args:
            test_suite: Test suite with test cases and validators.
            resource: Optional agent resource for context.
            pass_threshold: Score threshold for passing (default 0.5).
            cache_validators: Whether to cache validator instances.
        """
        self.test_suite = test_suite
        self.resource = resource
        self.pass_threshold = pass_threshold
        self._validator_cache: dict[str, Any] = {} if cache_validators else {}

        # Build prompt -> test case lookup for fast access
        self._prompt_to_test: dict[str, TestCase] = {}
        for test in test_suite.test_cases:
            # Normalize prompt for lookup (strip, lowercase first 100 chars)
            normalized = test.prompt.strip()[:100].lower()
            self._prompt_to_test[normalized] = test
            # Also store full prompt for exact matches
            self._prompt_to_test[test.prompt.strip()] = test

    def __call__(
        self,
        example: dspy.Example,
        pred: dspy.Prediction,
        trace: Any = None,
    ) -> float:
        """Evaluate prediction against test case.

        This is the DSPy metric interface. Returns a float score.

        Args:
            example: DSPy Example with input task.
            pred: DSPy Prediction with solution.
            trace: Optional trace information (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        result = self.evaluate(example, pred)
        return result.score

    def evaluate(
        self,
        example: dspy.Example,
        pred: dspy.Prediction,
    ) -> MetricResult:
        """Evaluate prediction with full result details.

        Args:
            example: DSPy Example with input task.
            pred: DSPy Prediction with solution.

        Returns:
            MetricResult with score and details.
        """
        # Find matching test case
        task = getattr(example, 'task', '') or getattr(example, 'prompt', '')
        test_case = self._find_test_case(task)

        if not test_case:
            logger.debug(
                "No matching test case found",
                task_preview=task[:50],
            )
            return MetricResult(
                score=0.0,
                passed=False,
                validator_type="unknown",
                details="No matching test case found",
            )

        # Get solution from prediction
        solution = getattr(pred, 'solution', '') or getattr(pred, 'output', '')
        if not solution:
            return MetricResult(
                score=0.0,
                passed=False,
                validator_type=self._get_validator_type(test_case),
                details="Empty solution",
            )

        # Run validation
        try:
            score = self._run_validation(test_case, solution)
            validator_type = self._get_validator_type(test_case)
            passed = score >= self.pass_threshold

            return MetricResult(
                score=score,
                passed=passed,
                validator_type=validator_type,
                details=f"Validation complete: {validator_type}",
            )

        except Exception as e:
            logger.debug(
                "Validation failed",
                test_id=test_case.id,
                error=str(e),
            )
            return MetricResult(
                score=0.0,
                passed=False,
                validator_type=self._get_validator_type(test_case),
                details=f"Validation error: {e}",
            )

    def _find_test_case(self, task: str) -> TestCase | None:
        """Find test case matching the task prompt.

        Args:
            task: The task/prompt to find.

        Returns:
            Matching TestCase or None.
        """
        # Try exact match first
        if task.strip() in self._prompt_to_test:
            return self._prompt_to_test[task.strip()]

        # Try normalized match
        normalized = task.strip()[:100].lower()
        if normalized in self._prompt_to_test:
            return self._prompt_to_test[normalized]

        # Fallback: search test suite
        return self.test_suite.get_by_prompt(task)

    def _get_validator_type(self, test_case: TestCase) -> str:
        """Get the validator type for a test case.

        Args:
            test_case: The test case to check.

        Returns:
            String name of validator type.
        """
        val_type = test_case.validation.type
        if hasattr(val_type, 'value'):
            return val_type.value
        return str(val_type)

    def _run_validation(self, test_case: TestCase, solution: str) -> float:
        """Run validation for a test case.

        Handles async validators by running in event loop.

        Args:
            test_case: Test case with validation config.
            solution: Solution to validate.

        Returns:
            Validation score between 0.0 and 1.0.
        """
        # Get or create validator
        validator = self._get_or_create_validator(test_case)

        # Run async validation synchronously (DSPy metrics are sync)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            if loop.is_running():
                # Already in async context, use thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        validator.validate(solution)
                    )
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(validator.validate(solution))
        except Exception as e:
            logger.debug("Validation execution failed", error=str(e))
            return 0.0

    def _get_or_create_validator(self, test_case: TestCase) -> Any:
        """Get cached validator or create new one.

        Args:
            test_case: Test case with validation config.

        Returns:
            Validator instance.
        """
        from harness.optimization.testcases import get_validator

        cache = self._validator_cache
        if cache is not None and test_case.id in cache:
            return cache[test_case.id]

        validator = get_validator(test_case.validation)

        if self._validator_cache is not None:
            self._validator_cache[test_case.id] = validator

        return validator

    def is_deterministic(self, test_case: TestCase) -> bool:
        """Check if test case uses deterministic validation.

        Deterministic validators (regex, exact match, code) produce
        consistent results. LLM-based validators may vary.

        Args:
            test_case: Test case to check.

        Returns:
            True if deterministic, False if LLM-based.
        """
        val_type = self._get_validator_type(test_case)
        deterministic_types = {
            'exact', 'exact_match',
            'contains', 'contains_all', 'contains_any',
            'regex', 'regex_match',
            'code', 'code_execution', 'code_syntax',
            'json', 'json_schema',
        }
        return val_type.lower() in deterministic_types

    def get_deterministic_tests(self) -> list[TestCase]:
        """Get all test cases with deterministic validators.

        Returns:
            List of test cases using deterministic validation.
        """
        return [
            test for test in self.test_suite.test_cases
            if self.is_deterministic(test)
        ]

    def get_llm_judge_tests(self) -> list[TestCase]:
        """Get all test cases with LLM-based validators.

        Returns:
            List of test cases using LLM-judge validation.
        """
        return [
            test for test in self.test_suite.test_cases
            if not self.is_deterministic(test)
        ]


def create_test_suite_metric(
    test_suite: TestSuite,
    resource: AgentResource | None = None,
    pass_threshold: float = 0.5,
) -> Callable:
    """Create a DSPy-compatible metric from CGF test suite validators.

    This is the recommended way to create metrics for MIPROv2 when using
    CGF test suites. It integrates directly with CGF validators (regex,
    code, LLM-judge, etc.) for accurate evaluation.

    Note: For simpler threshold-based metrics without test suites,
    use metrics.create_threshold_metric instead.

    Args:
        test_suite: Test suite with test cases.
        resource: Optional agent resource.
        pass_threshold: Score threshold for passing.

    Returns:
        Callable metric function for DSPy.

    Example:
        metric = create_test_suite_metric(test_suite)
        teleprompter = MIPROv2(metric=metric, ...)
    """
    return TestSuiteMetric(
        test_suite=test_suite,
        resource=resource,
        pass_threshold=pass_threshold,
    )


# Backwards-compatible alias (deprecated)
create_dspy_metric = create_test_suite_metric


def create_trainset_from_suite(
    test_suite: TestSuite,
    include_expected: bool = True,
) -> list[Any]:
    """Create DSPy trainset from test suite.

    Converts test cases to DSPy Examples for use with MIPROv2.

    Args:
        test_suite: Test suite with test cases.
        include_expected: Include expected behavior as solution.

    Returns:
        List of dspy.Example objects.

    Example:
        trainset = create_trainset_from_suite(test_suite)
        teleprompter.compile(module, trainset=trainset)
    """
    if not DSPY_AVAILABLE:
        raise ImportError("DSPy not installed")

    examples = []

    for test in test_suite.test_cases:
        example_data = {
            'task': test.prompt,
        }

        if include_expected and test.expected_behavior:
            example_data['solution'] = test.expected_behavior
        else:
            # Use empty solution if no expected behavior
            example_data['solution'] = ""

        example = dspy.Example(**example_data).with_inputs('task')
        examples.append(example)

    return examples


def aggregate_scores(
    results: list[MetricResult],
    weight_by_type: bool = False,
) -> float:
    """Aggregate multiple metric results into single score.

    Args:
        results: List of MetricResult from individual evaluations.
        weight_by_type: Weight deterministic tests higher (1.2x).

    Returns:
        Aggregated score between 0.0 and 1.0.
    """
    if not results:
        return 0.0

    if not weight_by_type:
        return sum(r.score for r in results) / len(results)

    # Weight deterministic tests higher
    deterministic_types = {'exact', 'regex', 'code', 'json', 'contains'}

    total_weight = 0.0
    weighted_sum = 0.0

    for result in results:
        is_deterministic = any(
            dt in result.validator_type.lower()
            for dt in deterministic_types
        )
        weight = 1.2 if is_deterministic else 1.0
        weighted_sum += result.score * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0
