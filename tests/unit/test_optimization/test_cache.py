"""Unit tests for caching infrastructure."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from harness.optimization.cache import (
    BaseCache,
    CacheConfig,
    CachedResult,
    CachedTestSuite,
    CacheEntry,
    CacheManager,
    CacheStats,
    EvalCriteria,
    ResearchCache,
    ResearchCacheKey,
    ResultCache,
    ResultCacheKey,
    TestCache,
    TestCacheKey,
    TestCase,
    TestResult,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_creation(self) -> None:
        """CacheEntry creates with all fields."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "value"},
            input_hash="abc123",
        )

        assert entry.key == "test_key"
        assert entry.value == {"data": "value"}
        assert entry.input_hash == "abc123"
        assert entry.expires_at is None

    def test_is_expired_no_expiry(self) -> None:
        """CacheEntry without expiry never expires."""
        entry = CacheEntry(key="test", value="data")

        assert not entry.is_expired()

    def test_is_expired_future(self) -> None:
        """CacheEntry with future expiry is not expired."""
        entry = CacheEntry(
            key="test",
            value="data",
            expires_at=time.time() + 3600,
        )

        assert not entry.is_expired()

    def test_is_expired_past(self) -> None:
        """CacheEntry with past expiry is expired."""
        entry = CacheEntry(
            key="test",
            value="data",
            expires_at=time.time() - 1,
        )

        assert entry.is_expired()

    def test_is_valid_matching_hash(self) -> None:
        """CacheEntry is valid when hash matches."""
        entry = CacheEntry(
            key="test",
            value="data",
            input_hash="abc123",
        )

        assert entry.is_valid("abc123")

    def test_is_valid_mismatched_hash(self) -> None:
        """CacheEntry is invalid when hash mismatches."""
        entry = CacheEntry(
            key="test",
            value="data",
            input_hash="abc123",
        )

        assert not entry.is_valid("xyz789")

    def test_is_valid_expired(self) -> None:
        """CacheEntry is invalid when expired."""
        entry = CacheEntry(
            key="test",
            value="data",
            input_hash="abc123",
            expires_at=time.time() - 1,
        )

        assert not entry.is_valid("abc123")

    def test_to_dict(self) -> None:
        """CacheEntry.to_dict() serializes correctly."""
        entry = CacheEntry(
            key="test",
            value={"data": "value"},
            input_hash="hash",
            metadata={"key": "value"},
        )

        result = entry.to_dict()

        assert result["key"] == "test"
        assert result["value"] == {"data": "value"}
        assert result["input_hash"] == "hash"

    def test_from_dict(self) -> None:
        """CacheEntry.from_dict() deserializes correctly."""
        data = {
            "key": "test",
            "value": "data",
            "input_hash": "abc",
        }

        entry = CacheEntry.from_dict(data)

        assert entry.key == "test"
        assert entry.value == "data"


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_hit_rate_calculation(self) -> None:
        """CacheStats calculates hit rate correctly."""
        stats = CacheStats(hits=7, misses=3)

        assert stats.hit_rate == 70.0

    def test_hit_rate_empty(self) -> None:
        """CacheStats handles empty stats."""
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_to_dict(self) -> None:
        """CacheStats.to_dict() serializes correctly."""
        stats = CacheStats(
            hits=10,
            misses=5,
            invalidations=2,
            evictions=1,
            writes=15,
        )

        result = stats.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["hit_rate"] > 0


class DictCache(BaseCache[dict[str, Any]]):
    """Simple dict cache for testing."""

    def _serialize(self, value: dict[str, Any]) -> Any:
        return value

    def _deserialize(self, data: Any) -> dict[str, Any]:
        return data


class TestBaseCache:
    """Tests for BaseCache functionality."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create temp cache directory."""
        return tmp_path / "cache"

    def test_compute_hash_consistency(self, cache_dir: Path) -> None:
        """BaseCache.compute_hash() is consistent."""
        cache = DictCache(cache_dir)

        hash1 = cache.compute_hash("input1", "input2")
        hash2 = cache.compute_hash("input1", "input2")

        assert hash1 == hash2

    def test_compute_hash_different_inputs(self, cache_dir: Path) -> None:
        """BaseCache.compute_hash() differs for different inputs."""
        cache = DictCache(cache_dir)

        hash1 = cache.compute_hash("input1")
        hash2 = cache.compute_hash("input2")

        assert hash1 != hash2

    def test_put_and_get(self, cache_dir: Path) -> None:
        """BaseCache put/get round-trip works."""
        cache = DictCache(cache_dir)

        cache.put("key1", {"data": "value"})
        result = cache.get("key1")

        assert result == {"data": "value"}

    def test_get_nonexistent(self, cache_dir: Path) -> None:
        """BaseCache.get() returns None for missing key."""
        cache = DictCache(cache_dir)

        result = cache.get("nonexistent")

        assert result is None

    def test_hash_validation(self, cache_dir: Path) -> None:
        """BaseCache validates input hash."""
        cache = DictCache(cache_dir)

        cache.put("key1", {"data": "value"}, inputs=["a", "b"])

        # Same inputs - should hit
        assert cache.get("key1", inputs=["a", "b"]) is not None

        # Different inputs - should miss (invalidate)
        assert cache.get("key1", inputs=["a", "c"]) is None

    def test_invalidate(self, cache_dir: Path) -> None:
        """BaseCache.invalidate() removes entry."""
        cache = DictCache(cache_dir)

        cache.put("key1", {"data": "value"})
        assert cache.get("key1") is not None

        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self, cache_dir: Path) -> None:
        """BaseCache.clear() removes all entries."""
        cache = DictCache(cache_dir)

        cache.put("key1", {"data": "1"})
        cache.put("key2", {"data": "2"})
        cache.put("key3", {"data": "3"})

        count = cache.clear()

        assert count == 3
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats_tracking(self, cache_dir: Path) -> None:
        """BaseCache tracks hit/miss statistics."""
        cache = DictCache(cache_dir)

        cache.put("key1", {"data": "value"})
        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.get_stats()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.writes == 1

    def test_ttl_expiration(self, cache_dir: Path) -> None:
        """BaseCache respects TTL expiration."""
        cache = DictCache(cache_dir, ttl_seconds=0.01)

        cache.put("key1", {"data": "value"})
        time.sleep(0.02)  # Wait for expiration

        result = cache.get("key1")

        assert result is None

    def test_eviction(self, cache_dir: Path) -> None:
        """BaseCache evicts old entries when over capacity."""
        cache = DictCache(cache_dir, max_entries=5)

        # Add more than max entries
        for i in range(10):
            cache.put(f"key{i}", {"i": i})
            time.sleep(0.01)  # Ensure different mtime

        # Should have evicted some entries
        entries = cache.get_entries()
        assert len(entries) <= 5


class TestResearchCache:
    """Tests for ResearchCache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ResearchCache:
        """Create temp research cache."""
        return ResearchCache(cache_dir=tmp_path)

    def test_put_and_get_criteria(self, cache: ResearchCache) -> None:
        """ResearchCache stores and retrieves criteria."""
        key = ResearchCacheKey(
            resource_id="test-agent",
            resource_type="agent",
            goal="improve async handling",
            resource_content_hash="abc123",
        )
        criteria = EvalCriteria(
            competencies=[{"name": "async", "weight": 1.0}],
            criteria={"async": ["handles await"]},
            rubrics={"async": "0-1 scale"},
            research_summary="Test summary",
        )

        cache.put_criteria(key, criteria)
        result = cache.get_criteria(key)

        assert result is not None
        assert len(result.competencies) == 1
        assert result.research_summary == "Test summary"

    def test_cache_miss_different_goal(self, cache: ResearchCache) -> None:
        """ResearchCache misses when goal changes."""
        key1 = ResearchCacheKey(
            resource_id="test-agent",
            resource_type="agent",
            goal="improve async",
            resource_content_hash="abc",
        )
        criteria = EvalCriteria(
            competencies=[],
            criteria={},
            rubrics={},
        )

        cache.put_criteria(key1, criteria)

        # Different goal
        key2 = ResearchCacheKey(
            resource_id="test-agent",
            resource_type="agent",
            goal="improve error handling",
            resource_content_hash="abc",
        )

        result = cache.get_criteria(key2)

        assert result is None

    def test_invalidate_resource(self, cache: ResearchCache) -> None:
        """ResearchCache.invalidate_resource() removes entries."""
        key = ResearchCacheKey(
            resource_id="test-agent",
            resource_type="agent",
            goal="test",
            resource_content_hash="abc",
        )
        criteria = EvalCriteria(
            competencies=[],
            criteria={},
            rubrics={},
        )

        cache.put_criteria(key, criteria)
        assert cache.get_criteria(key) is not None

        cache.invalidate_resource("test-agent", "agent")
        assert cache.get_criteria(key) is None


class TestTestCache:
    """Tests for TestCache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> TestCache:
        """Create temp test cache."""
        return TestCache(cache_dir=tmp_path)

    def test_put_and_get_suite(self, cache: TestCache) -> None:
        """TestCache stores and retrieves test suites."""
        key = TestCacheKey(
            resource_id="test-agent",
            criteria_hash="criteria123",
        )
        suite = CachedTestSuite(
            resource_id="test-agent",
            tests=[
                TestCase(
                    id="test1",
                    name="Test One",
                    description="Tests async",
                    input="prompt",
                    expected="response",
                ),
            ],
            criteria_hash="criteria123",
        )

        cache.put_suite(key, suite)
        result = cache.get_suite(key)

        assert result is not None
        assert len(result.tests) == 1
        assert result.total_tests == 1

    def test_cache_miss_criteria_change(self, cache: TestCache) -> None:
        """TestCache misses when criteria hash changes."""
        key1 = TestCacheKey(
            resource_id="test-agent",
            criteria_hash="hash1",
        )
        suite = CachedTestSuite(
            resource_id="test-agent",
            tests=[],
            criteria_hash="hash1",
        )

        cache.put_suite(key1, suite)

        key2 = TestCacheKey(
            resource_id="test-agent",
            criteria_hash="hash2",
        )
        result = cache.get_suite(key2)

        assert result is None


class TestResultCache:
    """Tests for ResultCache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> ResultCache:
        """Create temp result cache."""
        return ResultCache(cache_dir=tmp_path)

    def test_put_and_get_result(self, cache: ResultCache) -> None:
        """ResultCache stores and retrieves results."""
        key = ResultCacheKey(
            resource_id="test-agent",
            optimized_content_hash="content123",
            test_suite_hash="suite456",
        )
        result = CachedResult(
            resource_id="test-agent",
            version="v1",
            overall_score=0.85,
            test_results=[
                TestResult(
                    test_id="test1",
                    passed=True,
                    score=0.9,
                ),
            ],
            recommendation="ACCEPT",
        )

        cache.put_result(key, result)
        cached = cache.get_result(key)

        assert cached is not None
        assert cached.overall_score == 0.85
        assert cached.recommendation == "ACCEPT"

    def test_pass_rate_calculation(self) -> None:
        """CachedResult calculates pass rate correctly."""
        result = CachedResult(
            resource_id="test",
            version="v1",
            overall_score=0.7,
            test_results=[
                TestResult(test_id="t1", passed=True),
                TestResult(test_id="t2", passed=True),
                TestResult(test_id="t3", passed=False),
            ],
        )

        assert result.pass_rate == pytest.approx(66.67, rel=0.1)


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_values(self) -> None:
        """CacheConfig has sensible defaults."""
        config = CacheConfig()

        assert config.enabled is True
        assert config.research_ttl_seconds == 86400 * 7
        assert config.max_research_entries == 100

    def test_custom_values(self) -> None:
        """CacheConfig accepts custom values."""
        config = CacheConfig(
            enabled=False,
            research_ttl_seconds=3600,
            max_test_entries=50,
        )

        assert config.enabled is False
        assert config.research_ttl_seconds == 3600
        assert config.max_test_entries == 50

    def test_to_dict(self) -> None:
        """CacheConfig.to_dict() serializes correctly."""
        config = CacheConfig(enabled=True)
        result = config.to_dict()

        assert "enabled" in result
        assert "base_dir" in result

    def test_from_dict(self) -> None:
        """CacheConfig.from_dict() deserializes correctly."""
        data = {
            "enabled": False,
            "base_dir": "/tmp/cache",
        }
        config = CacheConfig.from_dict(data)

        assert config.enabled is False
        assert config.base_dir == Path("/tmp/cache")


class TestCacheManager:
    """Tests for CacheManager."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> CacheManager:
        """Create temp cache manager."""
        config = CacheConfig(base_dir=tmp_path)
        return CacheManager(config)

    def test_enabled_by_default(self, manager: CacheManager) -> None:
        """CacheManager is enabled by default."""
        assert manager.enabled is True

    def test_disabled_manager(self, tmp_path: Path) -> None:
        """CacheManager works when disabled."""
        config = CacheConfig(enabled=False)
        manager = CacheManager(config)

        assert manager.enabled is False
        assert manager.get_research(
            ResearchCacheKey("r", "t", "g", "h")
        ) is None
        assert manager.get_tests(
            TestCacheKey("r", "c")
        ) is None
        assert manager.get_result(
            ResultCacheKey("r", "c", "s")
        ) is None

    def test_research_operations(self, manager: CacheManager) -> None:
        """CacheManager research operations work."""
        key = ResearchCacheKey(
            resource_id="test",
            resource_type="agent",
            goal="test goal",
            resource_content_hash="hash",
        )
        criteria = EvalCriteria(
            competencies=[],
            criteria={},
            rubrics={},
        )

        manager.put_research(key, criteria)
        result = manager.get_research(key)

        assert result is not None

    def test_test_operations(self, manager: CacheManager) -> None:
        """CacheManager test operations work."""
        key = TestCacheKey(
            resource_id="test",
            criteria_hash="hash",
        )
        suite = CachedTestSuite(
            resource_id="test",
            tests=[],
            criteria_hash="hash",
        )

        manager.put_tests(key, suite)
        result = manager.get_tests(key)

        assert result is not None

    def test_result_operations(self, manager: CacheManager) -> None:
        """CacheManager result operations work."""
        key = ResultCacheKey(
            resource_id="test",
            optimized_content_hash="opt",
            test_suite_hash="suite",
        )
        result = CachedResult(
            resource_id="test",
            version="v1",
            overall_score=0.8,
            test_results=[],
        )

        manager.put_result(key, result)
        cached = manager.get_result(key)

        assert cached is not None
        assert cached.overall_score == 0.8

    def test_clear_all(self, manager: CacheManager) -> None:
        """CacheManager.clear_all() clears all caches."""
        # Add entries to each cache
        manager.put_research(
            ResearchCacheKey("r1", "t", "g", "h"),
            EvalCriteria([], {}, {}),
        )
        manager.put_tests(
            TestCacheKey("r2", "c"),
            CachedTestSuite("r2", [], "c"),
        )
        manager.put_result(
            ResultCacheKey("r3", "o", "s"),
            CachedResult("r3", "v1", 0.5, []),
        )

        counts = manager.clear_all()

        assert counts["research"] == 1
        assert counts["tests"] == 1
        assert counts["results"] == 1

    def test_get_all_stats(self, manager: CacheManager) -> None:
        """CacheManager.get_all_stats() returns combined stats."""
        # Generate some activity
        manager.put_research(
            ResearchCacheKey("r1", "t", "g", "h"),
            EvalCriteria([], {}, {}),
        )
        manager.get_research(
            ResearchCacheKey("r1", "t", "g", "h")
        )  # hit
        manager.get_research(
            ResearchCacheKey("miss", "t", "g", "h")
        )  # miss

        stats = manager.get_all_stats()

        assert "research" in stats
        assert "combined" in stats
        assert stats["combined"]["total_hits"] >= 1
        assert stats["combined"]["total_misses"] >= 1

    def test_get_summary(self, manager: CacheManager) -> None:
        """CacheManager.get_summary() returns complete summary."""
        summary = manager.get_summary()

        assert summary["enabled"] is True
        assert "stats" in summary
        assert "config" in summary


class TestEvalCriteria:
    """Tests for EvalCriteria dataclass."""

    def test_to_dict(self) -> None:
        """EvalCriteria.to_dict() serializes correctly."""
        criteria = EvalCriteria(
            competencies=[{"name": "async"}],
            criteria={"async": ["rule1"]},
            rubrics={"async": "rubric"},
            research_summary="summary",
        )

        result = criteria.to_dict()

        assert result["competencies"] == [{"name": "async"}]
        assert result["research_summary"] == "summary"

    def test_from_dict(self) -> None:
        """EvalCriteria.from_dict() deserializes correctly."""
        data = {
            "competencies": [{"name": "perf"}],
            "criteria": {},
            "rubrics": {},
        }

        criteria = EvalCriteria.from_dict(data)

        assert len(criteria.competencies) == 1


class TestCachedTestSuite:
    """Tests for CachedTestSuite dataclass."""

    def test_auto_calculate_stats(self) -> None:
        """CachedTestSuite auto-calculates statistics."""
        suite = CachedTestSuite(
            resource_id="test",
            tests=[
                TestCase(
                    id="t1",
                    name="Test 1",
                    description="",
                    input="",
                    expected="",
                    competency="async",
                    difficulty="easy",
                ),
                TestCase(
                    id="t2",
                    name="Test 2",
                    description="",
                    input="",
                    expected="",
                    competency="async",
                    difficulty="hard",
                ),
                TestCase(
                    id="t3",
                    name="Test 3",
                    description="",
                    input="",
                    expected="",
                    competency="errors",
                    difficulty="medium",
                ),
            ],
            criteria_hash="hash",
        )

        assert suite.total_tests == 3
        assert suite.by_competency["async"] == 2
        assert suite.by_competency["errors"] == 1
        assert suite.by_difficulty["easy"] == 1
        assert suite.by_difficulty["hard"] == 1
