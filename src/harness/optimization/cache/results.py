"""Result cache for CGF optimization pipeline.

Caches optimization results to skip re-evaluation when the
optimized resource hasn't changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.cache.base import BaseCache

logger = structlog.get_logger(__name__)


@dataclass
class ResultCacheKey:
    """Key components for result cache lookup.

    Attributes:
        resource_id: Unique identifier for the resource.
        optimized_content_hash: Hash of the optimized resource content.
        test_suite_hash: Hash of the test suite used for evaluation.
    """

    resource_id: str
    optimized_content_hash: str
    test_suite_hash: str

    def to_cache_key(self) -> str:
        """Generate cache key string."""
        return f"result_{self.resource_id}"


@dataclass
class TestResult:
    """Result of a single test case execution.

    Attributes:
        test_id: ID of the test case.
        passed: Whether the test passed.
        score: Numeric score (0.0-1.0).
        output: Actual output from the test.
        expected: Expected output.
        error: Error message if failed.
        duration_seconds: Time taken to run test.
    """

    test_id: str
    passed: bool
    score: float = 0.0
    output: str = ""
    expected: str = ""
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "test_id": self.test_id,
            "passed": self.passed,
            "score": self.score,
            "output": self.output,
            "expected": self.expected,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestResult:
        """Deserialize from dictionary."""
        return cls(
            test_id=data["test_id"],
            passed=data.get("passed", False),
            score=data.get("score", 0.0),
            output=data.get("output", ""),
            expected=data.get("expected", ""),
            error=data.get("error"),
            duration_seconds=data.get("duration_seconds", 0.0),
        )


@dataclass
class CachedResult:
    """Cached optimization evaluation result.

    Attributes:
        resource_id: Resource that was evaluated.
        version: Version of the optimized resource.
        overall_score: Overall evaluation score (0.0-1.0).
        test_results: Individual test results.
        passed_count: Number of tests passed.
        failed_count: Number of tests failed.
        by_competency: Scores grouped by competency.
        recommendation: ACCEPT, REFINE, or REJECT.
        evaluation_metadata: Metadata from evaluation.
    """

    resource_id: str
    version: str
    overall_score: float
    test_results: list[TestResult]
    passed_count: int = 0
    failed_count: int = 0
    by_competency: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    evaluation_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate derived fields."""
        if not self.passed_count and not self.failed_count:
            self.passed_count = sum(1 for r in self.test_results if r.passed)
            self.failed_count = len(self.test_results) - self.passed_count

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        total = self.passed_count + self.failed_count
        if total == 0:
            return 0.0
        return (self.passed_count / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "resource_id": self.resource_id,
            "version": self.version,
            "overall_score": self.overall_score,
            "test_results": [r.to_dict() for r in self.test_results],
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "by_competency": self.by_competency,
            "recommendation": self.recommendation,
            "evaluation_metadata": self.evaluation_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedResult:
        """Deserialize from dictionary."""
        return cls(
            resource_id=data["resource_id"],
            version=data.get("version", "v1"),
            overall_score=data.get("overall_score", 0.0),
            test_results=[
                TestResult.from_dict(r) for r in data.get("test_results", [])
            ],
            passed_count=data.get("passed_count", 0),
            failed_count=data.get("failed_count", 0),
            by_competency=data.get("by_competency", {}),
            recommendation=data.get("recommendation", ""),
            evaluation_metadata=data.get("evaluation_metadata", {}),
        )


class ResultCache(BaseCache[CachedResult]):
    """Cache for optimization evaluation results.

    Stores evaluation results keyed by optimized resource hash.
    Allows skipping re-evaluation when resource unchanged.

    Example:
        cache = ResultCache(cache_dir=Path("workspace/.cache"))

        # Check cache before evaluation
        key = ResultCacheKey(
            resource_id="python-expert",
            optimized_content_hash=compute_hash(optimized_content),
            test_suite_hash=compute_hash(test_suite),
        )

        cached = cache.get_result(key)
        if cached:
            # Use cached evaluation result
            pass
        else:
            # Run evaluation and cache
            result = evaluate(optimized_resource, tests)
            cache.put_result(key, result)
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float | None = 86400,  # 1 day default
    ) -> None:
        """Initialize result cache.

        Args:
            cache_dir: Directory for cache files.
            ttl_seconds: Time-to-live (default 1 day).
        """
        super().__init__(
            cache_dir=cache_dir / "results",
            ttl_seconds=ttl_seconds,
            max_entries=500,  # Keep up to 500 results
        )

    def _serialize(self, value: CachedResult) -> Any:
        """Serialize CachedResult for storage."""
        return value.to_dict()

    def _deserialize(self, data: Any) -> CachedResult:
        """Deserialize CachedResult from storage."""
        return CachedResult.from_dict(data)

    def get_result(
        self,
        key: ResultCacheKey,
    ) -> CachedResult | None:
        """Get cached evaluation result.

        Args:
            key: Result cache key.

        Returns:
            Cached result if valid, None otherwise.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.optimized_content_hash,
            key.test_suite_hash,
        ]
        return self.get(cache_key, inputs=inputs)

    def put_result(
        self,
        key: ResultCacheKey,
        result: CachedResult,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store evaluation result in cache.

        Args:
            key: Result cache key.
            result: Evaluation result to cache.
            metadata: Additional metadata to store.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.optimized_content_hash,
            key.test_suite_hash,
        ]
        self.put(cache_key, result, inputs=inputs, metadata=metadata)

        logger.info(
            "Cached evaluation result",
            resource_id=key.resource_id,
            version=result.version,
            score=f"{result.overall_score:.2%}",
            recommendation=result.recommendation,
        )

    def invalidate_resource(self, resource_id: str) -> bool:
        """Invalidate all cache entries for a resource.

        Args:
            resource_id: Resource identifier.

        Returns:
            True if any entries were invalidated.
        """
        cache_key = f"result_{resource_id}"
        return self.invalidate(cache_key)

    def get_history(self, resource_id: str) -> list[CachedResult]:
        """Get all cached results for a resource.

        Useful for tracking optimization progress across iterations.

        Args:
            resource_id: Resource identifier.

        Returns:
            List of cached results, sorted by creation time.
        """
        results = []
        for entry in self.get_entries():
            if entry.key.startswith(f"result_{resource_id}"):
                try:
                    result = self._deserialize(entry.value)
                    results.append(result)
                except (KeyError, TypeError):
                    continue

        return sorted(results, key=lambda r: r.version)
