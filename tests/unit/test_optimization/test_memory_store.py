"""Unit tests for MemoryOptimizationStore."""

from datetime import UTC, datetime, timedelta

import pytest

from harness.optimization.store.memory_store import MemoryOptimizationStore
from harness.optimization.store.models import EvaluationStatus
from harness.tracer.base import Span, SpanKind, SpanStatus


@pytest.fixture
def store() -> MemoryOptimizationStore:
    """Create a fresh memory store for each test."""
    return MemoryOptimizationStore()


@pytest.fixture
def sample_span() -> Span:
    """Create a sample span for testing."""
    return Span(
        trace_id="a" * 32,
        span_id="b" * 16,
        name="test.operation",
        kind=SpanKind.AGENT_EXECUTION,
        start_time=datetime.now(UTC),
        status=SpanStatus.OK,
        resource_id="agent-1",
        agent_name="test-agent",
    )


class TestMemoryStoreBasics:
    """Basic store functionality tests."""

    def test_store_creation(self) -> None:
        """Test creating a memory store."""
        store = MemoryOptimizationStore()

        assert store.name == "memory"

    def test_store_with_custom_name(self) -> None:
        """Test creating store with custom name."""
        store = MemoryOptimizationStore(name="test-store")

        assert store.name == "test-store"

    def test_repr(self) -> None:
        """Test string representation."""
        store = MemoryOptimizationStore(name="custom")

        assert "MemoryOptimizationStore" in repr(store)
        assert "custom" in repr(store)


class TestSpanOperations:
    """Tests for span storage and retrieval."""

    def test_store_span(self, store: MemoryOptimizationStore, sample_span: Span) -> None:
        """Test storing a single span."""
        store.store_span(sample_span)

        spans = store.get_trace_spans(sample_span.trace_id)
        assert len(spans) == 1
        assert spans[0].span_id == sample_span.span_id

    def test_store_spans_batch(self, store: MemoryOptimizationStore) -> None:
        """Test storing multiple spans."""
        trace_id = "c" * 32
        spans = [
            Span(
                trace_id=trace_id,
                span_id=f"{i}" * 16,
                name=f"operation-{i}",
                kind=SpanKind.TOOL_CALL,
                start_time=datetime.now(UTC),
                status=SpanStatus.OK,
            )
            for i in range(5)
        ]

        store.store_spans(spans)

        result = store.get_trace_spans(trace_id)
        assert len(result) == 5

    def test_query_spans_by_trace_id(
        self, store: MemoryOptimizationStore, sample_span: Span
    ) -> None:
        """Test querying spans by trace ID."""
        store.store_span(sample_span)

        result = store.query_spans(trace_id=sample_span.trace_id)

        assert len(result) == 1
        assert result[0].trace_id == sample_span.trace_id

    def test_query_spans_by_resource_id(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test querying spans by resource ID."""
        span1 = Span(
            trace_id="a" * 32,
            span_id="1" * 16,
            name="op1",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=datetime.now(UTC),
            status=SpanStatus.OK,
            resource_id="resource-a",
        )
        span2 = Span(
            trace_id="b" * 32,
            span_id="2" * 16,
            name="op2",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=datetime.now(UTC),
            status=SpanStatus.OK,
            resource_id="resource-b",
        )

        store.store_span(span1)
        store.store_span(span2)

        result = store.query_spans(resource_id="resource-a")

        assert len(result) == 1
        assert result[0].resource_id == "resource-a"

    def test_query_spans_by_agent_name(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test querying spans by agent name."""
        span = Span(
            trace_id="a" * 32,
            span_id="1" * 16,
            name="op",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=datetime.now(UTC),
            status=SpanStatus.OK,
            agent_name="special-agent",
        )
        store.store_span(span)

        result = store.query_spans(agent_name="special-agent")

        assert len(result) == 1
        assert result[0].agent_name == "special-agent"

    def test_query_spans_by_time_range(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test querying spans by time range."""
        now = datetime.now(UTC)
        old_span = Span(
            trace_id="a" * 32,
            span_id="1" * 16,
            name="old",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=now - timedelta(hours=2),
            status=SpanStatus.OK,
        )
        new_span = Span(
            trace_id="b" * 32,
            span_id="2" * 16,
            name="new",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=now,
            status=SpanStatus.OK,
        )

        store.store_span(old_span)
        store.store_span(new_span)

        result = store.query_spans(start_time=now - timedelta(hours=1))

        assert len(result) == 1
        assert result[0].name == "new"

    def test_query_spans_limit(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test query limit."""
        trace_id = "a" * 32
        for i in range(10):
            span = Span(
                trace_id=trace_id,
                span_id=f"{i}" * 16,
                name=f"op-{i}",
                kind=SpanKind.TOOL_CALL,
                start_time=datetime.now(UTC),
                status=SpanStatus.OK,
            )
            store.store_span(span)

        result = store.query_spans(limit=5)

        assert len(result) == 5

    def test_get_trace_spans_sorted(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test trace spans are sorted by start time."""
        trace_id = "a" * 32
        now = datetime.now(UTC)

        for i in range(3):
            span = Span(
                trace_id=trace_id,
                span_id=f"{i}" * 16,
                name=f"op-{i}",
                kind=SpanKind.AGENT_EXECUTION,
                start_time=now + timedelta(seconds=i),
                status=SpanStatus.OK,
            )
            store.store_span(span)

        result = store.get_trace_spans(trace_id)

        assert result[0].name == "op-0"
        assert result[1].name == "op-1"
        assert result[2].name == "op-2"

    def test_delete_trace(
        self, store: MemoryOptimizationStore, sample_span: Span
    ) -> None:
        """Test deleting a trace."""
        store.store_span(sample_span)

        deleted = store.delete_trace(sample_span.trace_id)

        assert deleted is True
        assert store.get_trace_spans(sample_span.trace_id) == []

    def test_delete_trace_not_found(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test deleting non-existent trace."""
        deleted = store.delete_trace("nonexistent")

        assert deleted is False


class TestResourceOperations:
    """Tests for resource registration and retrieval."""

    def test_register_resource(self, store: MemoryOptimizationStore) -> None:
        """Test registering a new resource."""
        version = store.register_resource(
            resource_id="agent-1",
            resource_type="agent",
            content="system prompt content",
            metadata={"author": "test"},
        )

        assert version.version == 1
        assert version.content_hash != ""

    def test_register_resource_creates_new_version(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test updating resource creates new version."""
        store.register_resource("agent-1", "agent", "content v1")
        version2 = store.register_resource("agent-1", "agent", "content v2")

        assert version2.version == 2

    def test_register_resource_skips_duplicate(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test duplicate content doesn't create new version."""
        version1 = store.register_resource("agent-1", "agent", "same content")
        version2 = store.register_resource("agent-1", "agent", "same content")

        assert version1.version == version2.version == 1

    def test_get_resource(self, store: MemoryOptimizationStore) -> None:
        """Test retrieving a resource."""
        store.register_resource("skill-1", "skill", "skill content")

        resource = store.get_resource("skill-1")

        assert resource is not None
        assert resource.resource_id == "skill-1"
        assert resource.resource_type == "skill"
        assert resource.content == "skill content"

    def test_get_resource_not_found(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test retrieving non-existent resource."""
        resource = store.get_resource("nonexistent")

        assert resource is None

    def test_get_resource_specific_version(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test retrieving specific version."""
        store.register_resource("agent-1", "agent", "v1 content")
        store.register_resource("agent-1", "agent", "v2 content")

        v1 = store.get_resource("agent-1", version=1)
        v2 = store.get_resource("agent-1", version=2)

        assert v1 is not None
        assert v1.content == "v1 content"
        assert v2 is not None
        assert v2.content == "v2 content"

    def test_list_resources(self, store: MemoryOptimizationStore) -> None:
        """Test listing resources."""
        store.register_resource("agent-1", "agent", "content")
        store.register_resource("skill-1", "skill", "content")

        resources = store.list_resources()

        assert len(resources) == 2

    def test_list_resources_by_type(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test listing resources by type."""
        store.register_resource("agent-1", "agent", "content")
        store.register_resource("skill-1", "skill", "content")
        store.register_resource("agent-2", "agent", "content")

        agents = store.list_resources(resource_type="agent")

        assert len(agents) == 2
        assert all(r.resource_type == "agent" for r in agents)

    def test_get_resource_versions(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test getting version history."""
        store.register_resource("agent-1", "agent", "v1")
        store.register_resource("agent-1", "agent", "v2")
        store.register_resource("agent-1", "agent", "v3")

        versions = store.get_resource_versions("agent-1")

        assert len(versions) == 3
        # Most recent first
        assert versions[0].version == 3
        assert versions[1].version == 2
        assert versions[2].version == 1

    def test_delete_resource(self, store: MemoryOptimizationStore) -> None:
        """Test deleting a resource."""
        store.register_resource("agent-1", "agent", "content")

        deleted = store.delete_resource("agent-1")

        assert deleted is True
        assert store.get_resource("agent-1") is None

    def test_delete_resource_not_found(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test deleting non-existent resource."""
        deleted = store.delete_resource("nonexistent")

        assert deleted is False


class TestEvaluationQueueOperations:
    """Tests for evaluation queue operations."""

    def test_enqueue_evaluation(self, store: MemoryOptimizationStore) -> None:
        """Test enqueueing an evaluation."""
        eval_id = store.enqueue_evaluation(
            resource_id="agent-1",
            resource_type="agent",
            config={"test_cases": ["test1"]},
            priority=5,
        )

        assert eval_id.startswith("eval-")
        assert store.get_queue_length() == 1

    def test_dequeue_evaluation(self, store: MemoryOptimizationStore) -> None:
        """Test dequeuing an evaluation."""
        store.enqueue_evaluation("agent-1", "agent")

        task = store.dequeue_evaluation("runner-1")

        assert task is not None
        assert task.resource_id == "agent-1"
        assert task.status == EvaluationStatus.IN_PROGRESS
        assert task.runner_id == "runner-1"
        assert store.get_queue_length() == 0

    def test_dequeue_empty_queue(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test dequeuing from empty queue."""
        task = store.dequeue_evaluation("runner-1")

        assert task is None

    def test_dequeue_respects_priority(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test higher priority tasks are dequeued first."""
        store.enqueue_evaluation("low", "agent", priority=1)
        store.enqueue_evaluation("high", "agent", priority=10)
        store.enqueue_evaluation("medium", "agent", priority=5)

        task1 = store.dequeue_evaluation("runner")
        task2 = store.dequeue_evaluation("runner")
        task3 = store.dequeue_evaluation("runner")

        assert task1 is not None and task1.resource_id == "high"
        assert task2 is not None and task2.resource_id == "medium"
        assert task3 is not None and task3.resource_id == "low"

    def test_get_evaluation_status(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test getting evaluation status."""
        eval_id = store.enqueue_evaluation("agent-1", "agent")

        status = store.get_evaluation_status(eval_id)

        assert status is not None
        assert status["evaluation_id"] == eval_id
        assert status["status"] == "pending"

    def test_get_evaluation_status_not_found(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test getting status of non-existent evaluation."""
        status = store.get_evaluation_status("nonexistent")

        assert status is None

    def test_complete_evaluation_success(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test completing evaluation successfully."""
        eval_id = store.enqueue_evaluation("agent-1", "agent")
        store.dequeue_evaluation("runner-1")

        completed = store.complete_evaluation(eval_id, success=True)

        assert completed is True
        status = store.get_evaluation_status(eval_id)
        assert status is not None
        assert status["status"] == "completed"

    def test_complete_evaluation_failure(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test completing evaluation with failure."""
        eval_id = store.enqueue_evaluation("agent-1", "agent")
        store.dequeue_evaluation("runner-1")

        completed = store.complete_evaluation(
            eval_id, success=False, error_message="test error"
        )

        assert completed is True
        status = store.get_evaluation_status(eval_id)
        assert status is not None
        assert status["status"] == "failed"
        assert status["error_message"] == "test error"


class TestResultOperations:
    """Tests for result storage and retrieval."""

    def test_store_result(self, store: MemoryOptimizationStore) -> None:
        """Test storing a result."""
        store.register_resource("agent-1", "agent", "content")
        eval_id = store.enqueue_evaluation("agent-1", "agent")

        store.store_result(
            evaluation_id=eval_id,
            resource_id="agent-1",
            reward={"accuracy": 0.9, "efficiency": 0.8},
        )

        results = store.query_results(resource_id="agent-1")
        assert len(results) == 1
        assert results[0].reward["accuracy"] == 0.9

    def test_query_results_by_resource_id(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test querying results by resource ID."""
        store.register_resource("agent-1", "agent", "content")
        store.register_resource("agent-2", "agent", "content")

        store.store_result("eval-1", "agent-1", {"score": 0.9})
        store.store_result("eval-2", "agent-2", {"score": 0.8})

        results = store.query_results(resource_id="agent-1")

        assert len(results) == 1
        assert results[0].resource_id == "agent-1"

    def test_query_results_by_min_score(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test querying results by minimum score."""
        store.register_resource("agent-1", "agent", "content")

        store.store_result("eval-1", "agent-1", {"score": 0.3})
        store.store_result("eval-2", "agent-1", {"score": 0.7})
        store.store_result("eval-3", "agent-1", {"score": 0.9})

        results = store.query_results(min_score=0.5)

        assert len(results) == 2
        assert all(r.composite_score >= 0.5 for r in results)

    def test_get_best_result(self, store: MemoryOptimizationStore) -> None:
        """Test getting best result for resource."""
        store.register_resource("agent-1", "agent", "content")

        store.store_result("eval-1", "agent-1", {"score": 0.5})
        store.store_result("eval-2", "agent-1", {"score": 0.9})
        store.store_result("eval-3", "agent-1", {"score": 0.7})

        best = store.get_best_result("agent-1")

        assert best is not None
        assert best.composite_score == pytest.approx(0.9)

    def test_get_best_result_no_results(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test getting best result when none exist."""
        best = store.get_best_result("nonexistent")

        assert best is None

    def test_get_result_history(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test getting result history."""
        store.register_resource("agent-1", "agent", "content")

        for i in range(5):
            store.store_result(f"eval-{i}", "agent-1", {"score": 0.5 + i * 0.1})

        history = store.get_result_history("agent-1", limit=3)

        assert len(history) == 3


class TestLifecycleOperations:
    """Tests for lifecycle operations."""

    def test_health_check(self, store: MemoryOptimizationStore) -> None:
        """Test health check."""
        health = store.health_check()

        assert health["status"] == "healthy"
        assert health["store_type"] == "memory"
        assert health["connected"] is True
        assert "metrics" in health

    def test_get_metrics(self, store: MemoryOptimizationStore) -> None:
        """Test getting metrics."""
        store.register_resource("agent-1", "agent", "content")
        store.enqueue_evaluation("agent-1", "agent")

        metrics = store.get_metrics()

        assert metrics.resource_count == 1
        assert metrics.queue_length == 1
        assert metrics.connected is True

    def test_clear(self, store: MemoryOptimizationStore) -> None:
        """Test clearing all data."""
        store.register_resource("agent-1", "agent", "content")
        store.enqueue_evaluation("agent-1", "agent")

        store.clear()

        assert store.get_metrics().resource_count == 0
        assert store.get_queue_length() == 0

    def test_close(self, store: MemoryOptimizationStore) -> None:
        """Test closing store (no-op for memory)."""
        # Should not raise
        store.close()


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_span_storage(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test concurrent span storage."""
        import threading

        def store_spans():
            for i in range(100):
                span = Span(
                    trace_id=f"{threading.current_thread().name}-{i}",
                    span_id=f"{i}" * 16,
                    name="concurrent",
                    kind=SpanKind.AGENT_EXECUTION,
                    start_time=datetime.now(UTC),
                    status=SpanStatus.OK,
                )
                store.store_span(span)

        threads = [threading.Thread(target=store_spans) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = store.get_metrics()
        assert metrics.span_count == 500

    def test_concurrent_resource_registration(
        self, store: MemoryOptimizationStore
    ) -> None:
        """Test concurrent resource registration."""
        import threading

        def register_resources():
            for i in range(50):
                store.register_resource(
                    f"resource-{threading.current_thread().name}-{i}",
                    "agent",
                    f"content-{i}",
                )

        threads = [threading.Thread(target=register_resources) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = store.get_metrics()
        assert metrics.resource_count == 250
