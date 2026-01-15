"""Base cache infrastructure for CGF optimization pipeline.

Provides file-based caching with hash-based invalidation for:
- Research artifacts (eval_criteria.yaml)
- Test suites (test_suite.yaml)
- Optimization results
- External API lookups
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CacheEntry[T]:
    """A cached entry with metadata.

    Attributes:
        key: Unique identifier for the cached data.
        value: The cached data.
        created_at: Unix timestamp when entry was created.
        expires_at: Unix timestamp when entry expires (None = never).
        input_hash: Hash of inputs used to validate cache.
        metadata: Additional metadata about the cached entry.
    """

    key: str
    value: T
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    input_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def is_valid(self, input_hash: str) -> bool:
        """Check if entry is valid for given input hash."""
        if self.is_expired():
            return False
        return self.input_hash == input_hash

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "input_hash": self.input_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry[Any]:
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            input_hash=data.get("input_hash", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CacheStats:
    """Statistics for cache operations.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        invalidations: Number of entries invalidated.
        evictions: Number of entries evicted.
        writes: Number of write operations.
    """

    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    evictions: int = 0
    writes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "invalidations": self.invalidations,
            "evictions": self.evictions,
            "writes": self.writes,
            "hit_rate": self.hit_rate,
        }


class BaseCache[T](ABC):
    """Abstract base class for file-based caches.

    Provides common functionality for hash-based invalidation
    and file persistence.

    Example:
        class MyCache(BaseCache[dict]):
            def _serialize(self, value):
                return json.dumps(value)

            def _deserialize(self, data):
                return json.loads(data)

        cache = MyCache(cache_dir=Path(".cache"))
        cache.put("key1", {"data": "value"}, inputs=["input1"])
        result = cache.get("key1", inputs=["input1"])
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float | None = None,
        max_entries: int = 1000,
    ) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory for cache files.
            ttl_seconds: Time-to-live for entries (None = no expiry).
            max_entries: Maximum number of entries before eviction.
        """
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.stats = CacheStats()

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_hash(self, *inputs: Any) -> str:
        """Compute hash from inputs for cache invalidation.

        Args:
            inputs: Any hashable inputs to include in hash.

        Returns:
            SHA-256 hash of serialized inputs.
        """
        hasher = hashlib.sha256()
        for inp in inputs:
            if isinstance(inp, (dict, list)):
                serialized = json.dumps(inp, sort_keys=True)
            elif isinstance(inp, Path):
                serialized = str(inp)
            else:
                serialized = str(inp)
            hasher.update(serialized.encode())
        return hasher.hexdigest()[:32]

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.json"

    @abstractmethod
    def _serialize(self, value: T) -> Any:
        """Serialize value for storage."""
        ...

    @abstractmethod
    def _deserialize(self, data: Any) -> T:
        """Deserialize value from storage."""
        ...

    def get(
        self,
        key: str,
        inputs: list[Any] | None = None,
    ) -> T | None:
        """Get cached value if valid.

        Args:
            key: Cache key.
            inputs: Inputs to validate against (for hash checking).

        Returns:
            Cached value if valid, None otherwise.
        """
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            self.stats.misses += 1
            logger.debug("Cache miss: file not found", key=key)
            return None

        try:
            with cache_path.open() as f:
                entry_data = json.load(f)
            entry = CacheEntry[Any].from_dict(entry_data)

            # Validate input hash if inputs provided
            if inputs is not None:
                input_hash = self.compute_hash(*inputs)
                if not entry.is_valid(input_hash):
                    self.stats.invalidations += 1
                    logger.debug(
                        "Cache invalidated: hash mismatch",
                        key=key,
                        expected=input_hash,
                        actual=entry.input_hash,
                    )
                    return None
            elif entry.is_expired():
                self.stats.invalidations += 1
                logger.debug("Cache invalidated: expired", key=key)
                return None

            self.stats.hits += 1
            logger.debug("Cache hit", key=key)
            return self._deserialize(entry.value)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Cache read error", key=key, error=str(e))
            self.stats.misses += 1
            return None

    def put(
        self,
        key: str,
        value: T,
        inputs: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            inputs: Inputs to hash for validation.
            metadata: Additional metadata to store.
        """
        # Check if we need to evict entries
        self._maybe_evict()

        input_hash = self.compute_hash(*inputs) if inputs else ""
        expires_at = (
            time.time() + self.ttl_seconds if self.ttl_seconds else None
        )

        entry = CacheEntry(
            key=key,
            value=self._serialize(value),
            expires_at=expires_at,
            input_hash=input_hash,
            metadata=metadata or {},
        )

        cache_path = self._get_cache_path(key)
        with cache_path.open("w") as f:
            json.dump(entry.to_dict(), f, indent=2)

        self.stats.writes += 1
        logger.debug(
            "Cache write",
            key=key,
            input_hash=input_hash[:8] if input_hash else "none",
        )

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate.

        Returns:
            True if entry was removed, False if not found.
        """
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            self.stats.invalidations += 1
            logger.debug("Cache entry invalidated", key=key)
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        self.stats = CacheStats()
        logger.info("Cache cleared", entries_removed=count)
        return count

    def _maybe_evict(self) -> None:
        """Evict oldest entries if over capacity."""
        cache_files = list(self.cache_dir.glob("*.json"))
        if len(cache_files) < self.max_entries:
            return

        # Sort by modification time, oldest first
        cache_files.sort(key=lambda p: p.stat().st_mtime)

        # Remove oldest 10%
        to_remove = max(1, len(cache_files) // 10)
        for cache_file in cache_files[:to_remove]:
            cache_file.unlink()
            self.stats.evictions += 1

        logger.debug("Cache eviction", entries_removed=to_remove)

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats

    def get_entries(self) -> list[CacheEntry[Any]]:
        """Get all cache entries."""
        entries = []
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with cache_file.open() as f:
                    data = json.load(f)
                entries.append(CacheEntry.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        return entries
