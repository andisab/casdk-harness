"""Test suite cache for CGF optimization pipeline.

Caches generated test suites to avoid regenerating tests when
evaluation criteria haven't changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.cache.base import BaseCache

logger = structlog.get_logger(__name__)


@dataclass
class TestCacheKey:
    """Key components for test cache lookup.

    Attributes:
        resource_id: Unique identifier for the resource.
        criteria_hash: Hash of the evaluation criteria.
        test_config_hash: Hash of test generation config.
    """

    resource_id: str
    criteria_hash: str
    test_config_hash: str = ""

    def to_cache_key(self) -> str:
        """Generate cache key string."""
        return f"tests_{self.resource_id}"


@dataclass
class TestCase:
    """A single test case from the cached test suite.

    Attributes:
        id: Unique test identifier.
        name: Human-readable test name.
        description: What the test validates.
        input: Test input/prompt.
        expected: Expected output or behavior.
        competency: Which competency this tests.
        difficulty: Test difficulty (easy/medium/hard).
        metadata: Additional test metadata.
    """

    id: str
    name: str
    description: str
    input: str
    expected: str
    competency: str = ""
    difficulty: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "input": self.input,
            "expected": self.expected,
            "competency": self.competency,
            "difficulty": self.difficulty,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestCase:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            input=data.get("input", ""),
            expected=data.get("expected", ""),
            competency=data.get("competency", ""),
            difficulty=data.get("difficulty", "medium"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CachedTestSuite:
    """Cached test suite with metadata.

    Attributes:
        resource_id: Resource the tests are for.
        tests: List of test cases.
        criteria_hash: Hash of criteria used to generate tests.
        total_tests: Total number of tests.
        by_competency: Tests grouped by competency.
        by_difficulty: Tests grouped by difficulty.
        generation_metadata: Metadata from test generation.
    """

    resource_id: str
    tests: list[TestCase]
    criteria_hash: str
    total_tests: int = 0
    by_competency: dict[str, int] = field(default_factory=dict)
    by_difficulty: dict[str, int] = field(default_factory=dict)
    generation_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate derived fields."""
        if self.total_tests == 0:
            self.total_tests = len(self.tests)

        if not self.by_competency:
            self.by_competency = {}
            for test in self.tests:
                comp = test.competency or "general"
                self.by_competency[comp] = self.by_competency.get(comp, 0) + 1

        if not self.by_difficulty:
            self.by_difficulty = {}
            for test in self.tests:
                diff = test.difficulty
                self.by_difficulty[diff] = self.by_difficulty.get(diff, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "resource_id": self.resource_id,
            "tests": [t.to_dict() for t in self.tests],
            "criteria_hash": self.criteria_hash,
            "total_tests": self.total_tests,
            "by_competency": self.by_competency,
            "by_difficulty": self.by_difficulty,
            "generation_metadata": self.generation_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedTestSuite:
        """Deserialize from dictionary."""
        return cls(
            resource_id=data["resource_id"],
            tests=[TestCase.from_dict(t) for t in data.get("tests", [])],
            criteria_hash=data.get("criteria_hash", ""),
            total_tests=data.get("total_tests", 0),
            by_competency=data.get("by_competency", {}),
            by_difficulty=data.get("by_difficulty", {}),
            generation_metadata=data.get("generation_metadata", {}),
        )


class TestCache(BaseCache[CachedTestSuite]):
    """Cache for generated test suites.

    Stores test_suite.yaml content keyed by resource+criteria hash.
    Invalidates when evaluation criteria change.

    Example:
        cache = TestCache(cache_dir=Path("workspace/.cache"))

        # Check cache before generating tests
        key = TestCacheKey(
            resource_id="python-expert",
            criteria_hash=compute_hash(eval_criteria),
        )

        cached = cache.get_suite(key)
        if cached:
            # Use cached test suite
            pass
        else:
            # Generate tests and cache
            suite = generate_tests(resource, criteria)
            cache.put_suite(key, suite)
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float | None = 86400 * 3,  # 3 days default
    ) -> None:
        """Initialize test cache.

        Args:
            cache_dir: Directory for cache files.
            ttl_seconds: Time-to-live (default 3 days).
        """
        super().__init__(
            cache_dir=cache_dir / "tests",
            ttl_seconds=ttl_seconds,
            max_entries=200,  # Keep up to 200 test suites
        )

    def _serialize(self, value: CachedTestSuite) -> Any:
        """Serialize CachedTestSuite for storage."""
        return value.to_dict()

    def _deserialize(self, data: Any) -> CachedTestSuite:
        """Deserialize CachedTestSuite from storage."""
        return CachedTestSuite.from_dict(data)

    def get_suite(
        self,
        key: TestCacheKey,
    ) -> CachedTestSuite | None:
        """Get cached test suite.

        Args:
            key: Test cache key.

        Returns:
            Cached test suite if valid, None otherwise.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.criteria_hash,
            key.test_config_hash,
        ]
        return self.get(cache_key, inputs=inputs)

    def put_suite(
        self,
        key: TestCacheKey,
        suite: CachedTestSuite,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store test suite in cache.

        Args:
            key: Test cache key.
            suite: Test suite to cache.
            metadata: Additional metadata to store.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.criteria_hash,
            key.test_config_hash,
        ]
        self.put(cache_key, suite, inputs=inputs, metadata=metadata)

        logger.info(
            "Cached test suite",
            resource_id=key.resource_id,
            test_count=suite.total_tests,
        )

    def invalidate_resource(self, resource_id: str) -> bool:
        """Invalidate all cache entries for a resource.

        Args:
            resource_id: Resource identifier.

        Returns:
            True if any entries were invalidated.
        """
        cache_key = f"tests_{resource_id}"
        return self.invalidate(cache_key)
