"""Cache manager for CGF optimization pipeline.

Provides unified access to all cache types with configuration
and statistics tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.cache.base import CacheStats
from harness.optimization.cache.research import (
    EvalCriteria,
    ResearchCache,
    ResearchCacheKey,
)
from harness.optimization.cache.results import (
    CachedResult,
    ResultCache,
    ResultCacheKey,
)
from harness.optimization.cache.tests import (
    CachedTestSuite,
    TestCache,
    TestCacheKey,
)

logger = structlog.get_logger(__name__)


@dataclass
class CacheConfig:
    """Configuration for cache behavior.

    Attributes:
        enabled: Whether caching is enabled.
        base_dir: Base directory for all caches.
        research_ttl_seconds: TTL for research cache.
        test_ttl_seconds: TTL for test cache.
        result_ttl_seconds: TTL for result cache.
        max_research_entries: Max research cache entries.
        max_test_entries: Max test cache entries.
        max_result_entries: Max result cache entries.
    """

    enabled: bool = True
    base_dir: Path = field(default_factory=lambda: Path(".cache"))
    research_ttl_seconds: float | None = 86400 * 7  # 7 days
    test_ttl_seconds: float | None = 86400 * 3  # 3 days
    result_ttl_seconds: float | None = 86400  # 1 day
    max_research_entries: int = 100
    max_test_entries: int = 200
    max_result_entries: int = 500

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "base_dir": str(self.base_dir),
            "research_ttl_seconds": self.research_ttl_seconds,
            "test_ttl_seconds": self.test_ttl_seconds,
            "result_ttl_seconds": self.result_ttl_seconds,
            "max_research_entries": self.max_research_entries,
            "max_test_entries": self.max_test_entries,
            "max_result_entries": self.max_result_entries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheConfig:
        """Deserialize from dictionary."""
        base_dir = data.get("base_dir", ".cache")
        return cls(
            enabled=data.get("enabled", True),
            base_dir=Path(base_dir) if base_dir else Path(".cache"),
            research_ttl_seconds=data.get("research_ttl_seconds"),
            test_ttl_seconds=data.get("test_ttl_seconds"),
            result_ttl_seconds=data.get("result_ttl_seconds"),
            max_research_entries=data.get("max_research_entries", 100),
            max_test_entries=data.get("max_test_entries", 200),
            max_result_entries=data.get("max_result_entries", 500),
        )


class CacheManager:
    """Unified manager for all optimization caches.

    Provides a single interface to manage research, test, and result
    caches with configurable behavior.

    Example:
        config = CacheConfig(
            base_dir=Path("workspace/.cache"),
            enabled=True,
        )
        manager = CacheManager(config)

        # Use research cache
        criteria = manager.get_research(key)
        if not criteria:
            criteria = run_research()
            manager.put_research(key, criteria)

        # Use test cache
        suite = manager.get_tests(key)

        # Use result cache
        result = manager.get_result(key)

        # Get combined statistics
        stats = manager.get_all_stats()
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize the cache manager.

        Args:
            config: Cache configuration.
        """
        self.config = config or CacheConfig()

        if self.config.enabled:
            self._research = ResearchCache(
                cache_dir=self.config.base_dir,
                ttl_seconds=self.config.research_ttl_seconds,
            )
            self._tests = TestCache(
                cache_dir=self.config.base_dir,
                ttl_seconds=self.config.test_ttl_seconds,
            )
            self._results = ResultCache(
                cache_dir=self.config.base_dir,
                ttl_seconds=self.config.result_ttl_seconds,
            )
            logger.info(
                "Cache manager initialized",
                base_dir=str(self.config.base_dir),
            )
        else:
            self._research = None
            self._tests = None
            self._results = None
            logger.info("Cache manager disabled")

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.enabled

    # Research cache methods
    def get_research(
        self,
        key: ResearchCacheKey,
    ) -> EvalCriteria | None:
        """Get cached research criteria."""
        if not self._research:
            return None
        return self._research.get_criteria(key)

    def put_research(
        self,
        key: ResearchCacheKey,
        criteria: EvalCriteria,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store research criteria in cache."""
        if self._research:
            self._research.put_criteria(key, criteria, metadata)

    # Test cache methods
    def get_tests(
        self,
        key: TestCacheKey,
    ) -> CachedTestSuite | None:
        """Get cached test suite."""
        if not self._tests:
            return None
        return self._tests.get_suite(key)

    def put_tests(
        self,
        key: TestCacheKey,
        suite: CachedTestSuite,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store test suite in cache."""
        if self._tests:
            self._tests.put_suite(key, suite, metadata)

    # Result cache methods
    def get_result(
        self,
        key: ResultCacheKey,
    ) -> CachedResult | None:
        """Get cached evaluation result."""
        if not self._results:
            return None
        return self._results.get_result(key)

    def put_result(
        self,
        key: ResultCacheKey,
        result: CachedResult,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store evaluation result in cache."""
        if self._results:
            self._results.put_result(key, result, metadata)

    def get_result_history(self, resource_id: str) -> list[CachedResult]:
        """Get all cached results for a resource."""
        if not self._results:
            return []
        return self._results.get_history(resource_id)

    # Management methods
    def invalidate_resource(self, resource_id: str) -> dict[str, bool]:
        """Invalidate all caches for a resource.

        Args:
            resource_id: Resource identifier.

        Returns:
            Dictionary of cache types and whether they were invalidated.
        """
        results = {}
        # Note: research cache needs resource_type, skip here
        if self._tests:
            results["tests"] = self._tests.invalidate_resource(resource_id)
        if self._results:
            results["results"] = self._results.invalidate_resource(resource_id)
        return results

    def clear_all(self) -> dict[str, int]:
        """Clear all caches.

        Returns:
            Dictionary of cache types and entries cleared.
        """
        counts = {}
        if self._research:
            counts["research"] = self._research.clear()
        if self._tests:
            counts["tests"] = self._tests.clear()
        if self._results:
            counts["results"] = self._results.clear()
        logger.info("All caches cleared", counts=counts)
        return counts

    def get_stats(self, cache_type: str) -> CacheStats | None:
        """Get statistics for a specific cache.

        Args:
            cache_type: Type of cache (research, tests, results).

        Returns:
            Cache statistics or None if disabled.
        """
        cache_map = {
            "research": self._research,
            "tests": self._tests,
            "results": self._results,
        }
        cache = cache_map.get(cache_type)
        if cache:
            return cache.get_stats()
        return None

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all caches.

        Returns:
            Dictionary with stats for each cache type.
        """
        stats = {}
        if self._research:
            stats["research"] = self._research.get_stats().to_dict()
        if self._tests:
            stats["tests"] = self._tests.get_stats().to_dict()
        if self._results:
            stats["results"] = self._results.get_stats().to_dict()

        # Calculate combined stats
        total_hits = sum(s.get("hits", 0) for s in stats.values())
        total_misses = sum(s.get("misses", 0) for s in stats.values())
        total_requests = total_hits + total_misses

        stats["combined"] = {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "total_requests": total_requests,
            "overall_hit_rate": (
                (total_hits / total_requests * 100) if total_requests else 0
            ),
        }

        return stats

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of cache state.

        Returns:
            Dictionary with summary information.
        """
        stats = self.get_all_stats()
        return {
            "enabled": self.config.enabled,
            "base_dir": str(self.config.base_dir),
            "stats": stats,
            "config": self.config.to_dict(),
        }
