"""Metric functions for optimization.

Converts TestResult and SuiteResult to scalar metrics for optimizer consumption.

Example usage:
    from harness.optimization.optimizers.metrics import (
        validation_score_metric,
        composite_metric,
        pass_rate_metric,
    )

    # Simple validation score
    score = validation_score_metric(test_result)

    # Multi-dimensional composite score
    score = composite_metric(suite_result, weights={"quality": 0.6, "efficiency": 0.4})
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness.optimization.testcases import SuiteResult, TestResult


# Type alias for metric functions
MetricFunction = Callable[..., float]


def validation_score_metric(result: TestResult) -> float:
    """Extract validation score from a single test result.

    This is the simplest metric - just uses the validator's score.

    Args:
        result: TestResult from running a test case.

    Returns:
        Validation score between 0.0 and 1.0.
    """
    return result.score


def pass_fail_metric(result: TestResult) -> float:
    """Binary pass/fail metric.

    Args:
        result: TestResult from running a test case.

    Returns:
        1.0 if passed, 0.0 if failed.
    """
    return 1.0 if result.success else 0.0


def execution_time_metric(
    result: TestResult,
    target_ms: float = 5000.0,
    max_penalty: float = 0.5,
) -> float:
    """Metric penalizing slow execution.

    Args:
        result: TestResult from running a test case.
        target_ms: Target execution time in milliseconds.
        max_penalty: Maximum penalty for slow execution.

    Returns:
        Score between (1.0 - max_penalty) and 1.0.
    """
    if result.execution_time_ms <= target_ms:
        return 1.0

    # Linear penalty for overtime
    overtime_ratio = (result.execution_time_ms - target_ms) / target_ms
    penalty = min(max_penalty, overtime_ratio * max_penalty)

    return 1.0 - penalty


def reward_composite_metric(result: TestResult) -> float:
    """Extract composite reward score if available.

    Falls back to validation score if no reward is present.

    Args:
        result: TestResult from running a test case.

    Returns:
        Composite reward score or validation score.
    """
    if result.reward is not None:
        return result.reward.composite()
    return result.score


def suite_average_score(suite_result: SuiteResult) -> float:
    """Calculate average validation score across suite.

    Args:
        suite_result: Results from running a full test suite.

    Returns:
        Average score across all test cases.
    """
    return suite_result.total_score


def suite_pass_rate(suite_result: SuiteResult) -> float:
    """Calculate pass rate across suite.

    Args:
        suite_result: Results from running a full test suite.

    Returns:
        Fraction of tests that passed (0.0 - 1.0).
    """
    return suite_result.pass_rate


def suite_weighted_score(
    suite_result: SuiteResult,
    weights: dict[str, float] | None = None,
) -> float:
    """Calculate weighted score with custom test weights.

    Args:
        suite_result: Results from running a full test suite.
        weights: Dictionary mapping test_case_id to weight.
            Missing tests use weight 1.0.

    Returns:
        Weighted average score.
    """
    weights = weights or {}

    total_weight = 0.0
    weighted_sum = 0.0

    for result in suite_result.results:
        weight = weights.get(result.test_case_id, 1.0)
        weighted_sum += result.score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def suite_composite_metric(
    suite_result: SuiteResult,
    score_weight: float = 0.6,
    pass_rate_weight: float = 0.3,
    efficiency_weight: float = 0.1,
    target_time_ms: float = 10000.0,
) -> float:
    """Multi-factor composite metric for suite evaluation.

    Combines validation score, pass rate, and execution efficiency.

    Args:
        suite_result: Results from running a full test suite.
        score_weight: Weight for average validation score.
        pass_rate_weight: Weight for pass rate.
        efficiency_weight: Weight for execution efficiency.
        target_time_ms: Target total execution time.

    Returns:
        Composite score between 0.0 and 1.0.
    """
    # Normalize weights
    total_weight = score_weight + pass_rate_weight + efficiency_weight
    if total_weight == 0:
        return 0.0

    score_weight /= total_weight
    pass_rate_weight /= total_weight
    efficiency_weight /= total_weight

    # Calculate component scores
    avg_score = suite_result.total_score
    pass_rate = suite_result.pass_rate

    # Efficiency score (inverse of time penalty)
    if suite_result.total_time_ms <= target_time_ms:
        efficiency = 1.0
    else:
        overtime_ratio = suite_result.total_time_ms / target_time_ms
        efficiency = max(0.5, 1.0 / overtime_ratio)  # Min 0.5 efficiency score

    # Combine
    return (
        avg_score * score_weight +
        pass_rate * pass_rate_weight +
        efficiency * efficiency_weight
    )


def create_threshold_metric(
    base_metric: MetricFunction = validation_score_metric,
    threshold: float = 0.5,
) -> Callable[[dict, dict], float]:
    """Create a metric function with threshold.

    Wraps a base metric with threshold-based scoring. The returned function
    expects (example, prediction) -> float signature.

    Args:
        base_metric: Base metric to use on TestResult.
        threshold: Minimum score to count as success.

    Returns:
        Metric function.
    """
    def metric(example: dict, prediction: dict) -> float:
        """Threshold metric wrapper.

        Args:
            example: Example with input.
            prediction: Prediction with output.

        Returns:
            Metric score.
        """
        # The prediction contains the TestResult in our case
        if "test_result" in prediction:
            result = prediction["test_result"]
            return base_metric(result)

        # If we only have output text, use binary match
        if "output" in prediction and "expected" in example:
            output = prediction["output"]
            expected = example["expected"]
            if expected.lower() in output.lower():
                return 1.0
            return 0.0

        # Fallback to checking if score is present
        if "score" in prediction:
            return float(prediction["score"])

        return 0.0

    return metric


def create_suite_metric(
    base_metric: Callable[[SuiteResult], float] = suite_average_score,
) -> Callable[[SuiteResult], float]:
    """Create a suite-level metric wrapper.

    Args:
        base_metric: Base metric function for SuiteResult.

    Returns:
        Configured metric function.
    """
    def metric(suite_result: SuiteResult) -> float:
        """Suite metric wrapper.

        Args:
            suite_result: Full suite results.

        Returns:
            Metric score.
        """
        if not suite_result.results:
            return 0.0
        return base_metric(suite_result)

    return metric


def aggregate_metrics(
    results: list[TestResult],
    metric_fn: MetricFunction = validation_score_metric,
    aggregation: str = "mean",
) -> float:
    """Aggregate metric across multiple results.

    Args:
        results: List of TestResults.
        metric_fn: Metric function to apply to each result.
        aggregation: Aggregation method ("mean", "min", "max", "sum").

    Returns:
        Aggregated metric value.

    Raises:
        ValueError: If aggregation method is unknown.
    """
    if not results:
        return 0.0

    scores = [metric_fn(r) for r in results]

    if aggregation == "mean":
        return sum(scores) / len(scores)
    elif aggregation == "min":
        return min(scores)
    elif aggregation == "max":
        return max(scores)
    elif aggregation == "sum":
        return sum(scores)
    else:
        raise ValueError(f"Unknown aggregation: {aggregation}")


class MetricRegistry:
    """Registry for metric functions.

    Allows registering and retrieving metrics by name.
    """

    def __init__(self) -> None:
        """Initialize the registry with default metrics."""
        self._metrics: dict[str, MetricFunction] = {}
        self._suite_metrics: dict[str, Callable[[SuiteResult], float]] = {}

        # Register defaults
        self.register("validation_score", validation_score_metric)
        self.register("pass_fail", pass_fail_metric)
        self.register("execution_time", execution_time_metric)
        self.register("reward_composite", reward_composite_metric)

        self.register_suite("average_score", suite_average_score)
        self.register_suite("pass_rate", suite_pass_rate)
        self.register_suite("composite", suite_composite_metric)

    def register(self, name: str, metric: MetricFunction) -> None:
        """Register a test result metric.

        Args:
            name: Metric name.
            metric: Metric function.
        """
        self._metrics[name] = metric

    def register_suite(
        self,
        name: str,
        metric: Callable[[SuiteResult], float],
    ) -> None:
        """Register a suite result metric.

        Args:
            name: Metric name.
            metric: Metric function.
        """
        self._suite_metrics[name] = metric

    def get(self, name: str) -> MetricFunction:
        """Get a test result metric by name.

        Args:
            name: Metric name.

        Returns:
            Metric function.

        Raises:
            KeyError: If metric not found.
        """
        if name not in self._metrics:
            raise KeyError(f"Unknown metric: {name}. Available: {list(self._metrics.keys())}")
        return self._metrics[name]

    def get_suite(self, name: str) -> Callable[[SuiteResult], float]:
        """Get a suite metric by name.

        Args:
            name: Metric name.

        Returns:
            Metric function.

        Raises:
            KeyError: If metric not found.
        """
        if name not in self._suite_metrics:
            raise KeyError(
                f"Unknown suite metric: {name}. "
                f"Available: {list(self._suite_metrics.keys())}"
            )
        return self._suite_metrics[name]

    def list_metrics(self) -> list[str]:
        """List registered test result metrics."""
        return list(self._metrics.keys())

    def list_suite_metrics(self) -> list[str]:
        """List registered suite metrics."""
        return list(self._suite_metrics.keys())


# Global registry instance
_registry = MetricRegistry()


def get_metric(name: str) -> MetricFunction:
    """Get a test result metric from the global registry.

    Args:
        name: Metric name.

    Returns:
        Metric function.
    """
    return _registry.get(name)


def get_suite_metric(name: str) -> Callable[[SuiteResult], float]:
    """Get a suite metric from the global registry.

    Args:
        name: Metric name.

    Returns:
        Metric function.
    """
    return _registry.get_suite(name)


def register_metric(name: str, metric: MetricFunction) -> None:
    """Register a metric in the global registry.

    Args:
        name: Metric name.
        metric: Metric function.
    """
    _registry.register(name, metric)
