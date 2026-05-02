"""CGF Optimization Store.

Provides storage backends for spans, resources, evaluation tasks, and results.

Usage:
    from harness.optimization.store import get_store, OptimizationStore

    # Get configured store (based on environment)
    store = get_store()

    # Or specify backend explicitly
    from harness.optimization.store import MemoryOptimizationStore, RedisOptimizationStore

    memory_store = MemoryOptimizationStore()
    redis_store = RedisOptimizationStore(url="redis://localhost:6379")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from harness.optimization.store.memory_store import MemoryOptimizationStore
from harness.optimization.store.models import (
    EvaluationResult,
    EvaluationStatus,
    EvaluationTask,
    Resource,
    ResourceType,
    ResourceVersion,
    StoreMetrics,
)
from harness.optimization.store.protocol import OptimizationStore

if TYPE_CHECKING:
    from harness.optimization.store.redis_store import RedisOptimizationStore as RedisStore

__all__ = [
    # Protocol
    "OptimizationStore",
    # Implementations
    "MemoryOptimizationStore",
    "RedisOptimizationStore",
    # Models
    "EvaluationTask",
    "EvaluationResult",
    "EvaluationStatus",
    "Resource",
    "ResourceVersion",
    "ResourceType",
    "StoreMetrics",
    # Factory
    "get_store",
]

# Global store instance (lazy singleton)
_store_instance: OptimizationStore | None = None


def get_store(
    backend: str | None = None,
    redis_url: str | None = None,
    **kwargs,
) -> OptimizationStore:
    """Get or create the optimization store instance.

    Factory function that returns a store implementation based on configuration.
    Uses lazy singleton pattern - subsequent calls return the same instance.

    Args:
        backend: Store backend to use: "redis" or "memory".
            If not specified, uses CGF_STORE_BACKEND env var (default: "memory").
        redis_url: Redis connection URL for redis backend.
            If not specified, uses CGF_REDIS_URL env var (default: "redis://localhost:6379").
        **kwargs: Additional arguments passed to store constructor.

    Returns:
        OptimizationStore implementation.

    Raises:
        ValueError: If an unknown backend is specified.
        RuntimeError: If redis backend requested but redis package not installed.

    Examples:
        # Use default (memory) store
        store = get_store()

        # Use Redis store
        store = get_store(backend="redis")

        # Use Redis with custom URL
        store = get_store(backend="redis", redis_url="redis://custom:6379")

        # Force memory store for testing
        store = get_store(backend="memory")
    """
    global _store_instance

    # Determine backend
    if backend is None:
        backend = os.environ.get("CGF_STORE_BACKEND", "memory").lower()

    # Return existing instance if compatible
    if _store_instance is not None:
        current_backend = "redis" if "Redis" in type(_store_instance).__name__ else "memory"
        if current_backend == backend:
            return _store_instance

    # Create new instance
    if backend == "memory":
        _store_instance = MemoryOptimizationStore(**kwargs)

    elif backend == "redis":
        if redis_url is None:
            redis_url = os.environ.get("CGF_REDIS_URL", "redis://localhost:6379")

        # Import lazily to avoid requiring redis for memory-only usage
        from harness.optimization.store.redis_store import RedisOptimizationStore

        _store_instance = RedisOptimizationStore(url=redis_url, **kwargs)

    else:
        raise ValueError(
            f"Unknown store backend: {backend}. "
            "Valid options: 'memory', 'redis'"
        )

    return _store_instance


def reset_store() -> None:
    """Reset the global store instance.

    Primarily for testing - allows creating a fresh store.
    """
    global _store_instance
    if _store_instance is not None:
        _store_instance.close()
        _store_instance = None


# Lazy import for RedisOptimizationStore to avoid requiring redis package
def __getattr__(name: str):
    if name == "RedisOptimizationStore":
        from harness.optimization.store.redis_store import RedisOptimizationStore

        return RedisOptimizationStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
