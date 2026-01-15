"""Caching infrastructure for CGF optimization pipeline.

Provides file-based caching with hash-based invalidation for:
- Research artifacts (eval_criteria.yaml)
- Test suites (test_suite.yaml)
- Optimization results

Example:
    from harness.optimization.cache import CacheManager, CacheConfig

    config = CacheConfig(
        base_dir=Path("workspace/.cache"),
        enabled=True,
    )
    cache = CacheManager(config)

    # Check/store research
    key = ResearchCacheKey(...)
    criteria = cache.get_research(key)
    if not criteria:
        criteria = run_research()
        cache.put_research(key, criteria)
"""

from harness.optimization.cache.base import (
    BaseCache,
    CacheEntry,
    CacheStats,
)
from harness.optimization.cache.manager import (
    CacheConfig,
    CacheManager,
)
from harness.optimization.cache.research import (
    EvalCriteria,
    ResearchCache,
    ResearchCacheKey,
)
from harness.optimization.cache.results import (
    CachedResult,
    ResultCache,
    ResultCacheKey,
    TestResult,
)
from harness.optimization.cache.tests import (
    CachedTestSuite,
    TestCache,
    TestCacheKey,
    TestCase,
)

__all__ = [
    # Base
    "BaseCache",
    "CacheEntry",
    "CacheStats",
    # Manager
    "CacheManager",
    "CacheConfig",
    # Research
    "ResearchCache",
    "ResearchCacheKey",
    "EvalCriteria",
    # Tests
    "TestCache",
    "TestCacheKey",
    "TestCase",
    "CachedTestSuite",
    # Results
    "ResultCache",
    "ResultCacheKey",
    "TestResult",
    "CachedResult",
]
