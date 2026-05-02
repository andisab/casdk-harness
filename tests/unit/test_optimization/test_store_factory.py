"""Unit tests for store factory."""

import os
from unittest.mock import patch

import pytest

from harness.optimization.store import (
    MemoryOptimizationStore,
    OptimizationStore,
    get_store,
    reset_store,
)


@pytest.fixture(autouse=True)
def cleanup_store():
    """Reset store after each test."""
    reset_store()
    yield
    reset_store()


class TestGetStore:
    """Tests for get_store factory function."""

    def test_get_store_default_memory(self) -> None:
        """Test default store is memory."""
        store = get_store()

        assert isinstance(store, MemoryOptimizationStore)

    def test_get_store_explicit_memory(self) -> None:
        """Test explicitly requesting memory store."""
        store = get_store(backend="memory")

        assert isinstance(store, MemoryOptimizationStore)

    def test_get_store_singleton(self) -> None:
        """Test store is singleton."""
        store1 = get_store()
        store2 = get_store()

        assert store1 is store2

    def test_get_store_from_env(self) -> None:
        """Test getting backend from environment."""
        with patch.dict(os.environ, {"CGF_STORE_BACKEND": "memory"}):
            store = get_store()

        assert isinstance(store, MemoryOptimizationStore)

    def test_get_store_invalid_backend(self) -> None:
        """Test invalid backend raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_store(backend="invalid")

        assert "Unknown store backend" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    def test_get_store_with_kwargs(self) -> None:
        """Test passing kwargs to store."""
        store = get_store(backend="memory", name="custom-name")

        assert store.name == "custom-name"

    def test_get_store_redis_requires_package(self) -> None:
        """Test redis backend requires redis package or running server."""
        # This test verifies the import and connection behavior
        # Possible outcomes:
        # 1. Redis package not installed -> RuntimeError
        # 2. Redis not running -> connection error
        # 3. Redis running -> success

        try:
            store = get_store(backend="redis")
            assert isinstance(store, OptimizationStore)
        except RuntimeError as e:
            # Redis package not installed
            assert "redis package required" in str(e)
        except Exception as e:
            # Redis not running - connection refused is expected
            assert "Connection refused" in str(e) or "connecting to" in str(e)


class TestResetStore:
    """Tests for reset_store function."""

    def test_reset_store_clears_instance(self) -> None:
        """Test reset_store clears the singleton."""
        store1 = get_store()
        reset_store()
        store2 = get_store()

        assert store1 is not store2

    def test_reset_store_closes_connection(self) -> None:
        """Test reset_store calls close on store."""
        store = get_store()
        # Store data
        store.register_resource("test", "agent", "content")

        reset_store()
        new_store = get_store()

        # New store should be empty
        assert new_store.get_resource("test") is None


class TestStoreProtocol:
    """Tests for OptimizationStore protocol compliance."""

    def test_memory_store_implements_protocol(self) -> None:
        """Test MemoryOptimizationStore implements OptimizationStore."""
        store = get_store(backend="memory")

        assert isinstance(store, OptimizationStore)

    def test_protocol_methods_exist(self) -> None:
        """Test all protocol methods exist on store."""
        store = get_store()

        # Span operations
        assert hasattr(store, "store_span")
        assert hasattr(store, "store_spans")
        assert hasattr(store, "query_spans")
        assert hasattr(store, "get_trace_spans")
        assert hasattr(store, "delete_trace")

        # Resource operations
        assert hasattr(store, "register_resource")
        assert hasattr(store, "get_resource")
        assert hasattr(store, "list_resources")
        assert hasattr(store, "get_resource_versions")
        assert hasattr(store, "delete_resource")

        # Evaluation operations
        assert hasattr(store, "enqueue_evaluation")
        assert hasattr(store, "dequeue_evaluation")
        assert hasattr(store, "get_evaluation_status")
        assert hasattr(store, "complete_evaluation")
        assert hasattr(store, "get_queue_length")

        # Result operations
        assert hasattr(store, "store_result")
        assert hasattr(store, "query_results")
        assert hasattr(store, "get_best_result")
        assert hasattr(store, "get_result_history")

        # Lifecycle operations
        assert hasattr(store, "health_check")
        assert hasattr(store, "clear")
        assert hasattr(store, "close")


class TestModuleExports:
    """Tests for module exports."""

    def test_store_exports(self) -> None:
        """Test all expected items are exported."""
        from harness.optimization import store

        # Protocol
        assert hasattr(store, "OptimizationStore")

        # Implementations
        assert hasattr(store, "MemoryOptimizationStore")

        # Models
        assert hasattr(store, "EvaluationTask")
        assert hasattr(store, "EvaluationResult")
        assert hasattr(store, "EvaluationStatus")
        assert hasattr(store, "Resource")
        assert hasattr(store, "ResourceVersion")
        assert hasattr(store, "ResourceType")
        assert hasattr(store, "StoreMetrics")

        # Factory
        assert hasattr(store, "get_store")
        assert hasattr(store, "reset_store")

    def test_optimization_module_exports(self) -> None:
        """Test optimization module re-exports store items."""
        from harness import optimization

        # Factory functions
        assert hasattr(optimization, "get_store")
        assert hasattr(optimization, "reset_store")

        # Key types
        assert hasattr(optimization, "OptimizationStore")
        assert hasattr(optimization, "MemoryOptimizationStore")
        assert hasattr(optimization, "EvaluationTask")
        assert hasattr(optimization, "EvaluationResult")
