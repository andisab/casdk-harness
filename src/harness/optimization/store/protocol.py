"""Protocol definition for the CGF Optimization Store.

The OptimizationStore protocol defines the interface for storing and retrieving
spans, resources, evaluation tasks, and results. Implementations include
Redis (production) and Memory (testing).

Example usage:
    store = get_store()  # Returns configured store implementation

    # Span storage
    store.store_span(span)
    spans = store.query_spans(trace_id="abc123")

    # Resource management
    version = store.register_resource("agent-1", "agent", content, metadata)
    resource = store.get_resource("agent-1")

    # Evaluation queue
    eval_id = store.enqueue_evaluation("agent-1", "agent", config)
    task = store.dequeue_evaluation("runner-1")
    store.store_result(eval_id, reward, metadata)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from harness.optimization.store.models import (
        EvaluationResult,
        EvaluationTask,
        Resource,
        ResourceVersion,
    )
    from harness.tracer.base import Span


@runtime_checkable
class OptimizationStore(Protocol):
    """Protocol for CGF optimization store implementations.

    Provides a unified interface for:
    - Span storage and querying
    - Resource versioning and retrieval
    - Evaluation task queue management
    - Result storage and querying

    Implementations must be thread-safe for concurrent access.
    """

    # =========================================================================
    # Span Operations
    # =========================================================================

    def store_span(self, span: Span) -> None:
        """Store a completed span.

        Args:
            span: The span to store.
        """
        ...

    def store_spans(self, spans: list[Span]) -> None:
        """Store multiple spans in a batch.

        Args:
            spans: List of spans to store.
        """
        ...

    def query_spans(
        self,
        trace_id: str | None = None,
        resource_id: str | None = None,
        agent_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[Span]:
        """Query spans with optional filters.

        Args:
            trace_id: Filter by trace ID.
            resource_id: Filter by resource ID.
            agent_name: Filter by agent name.
            start_time: Filter spans starting after this time.
            end_time: Filter spans starting before this time.
            limit: Maximum number of spans to return.

        Returns:
            List of matching spans, ordered by start_time descending.
        """
        ...

    def get_trace_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a specific trace.

        Args:
            trace_id: The trace ID to query.

        Returns:
            List of spans in the trace, ordered by start_time.
        """
        ...

    def delete_trace(self, trace_id: str) -> bool:
        """Delete all spans for a trace.

        Args:
            trace_id: The trace ID to delete.

        Returns:
            True if deleted, False if trace not found.
        """
        ...

    # =========================================================================
    # Resource Operations
    # =========================================================================

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ResourceVersion:
        """Register a new resource or version.

        If the resource already exists, creates a new version.
        Content is hashed to detect duplicates.

        Args:
            resource_id: Unique resource identifier.
            resource_type: Type of resource (agent, skill, prompt, command).
            content: The resource content (definition, prompt text, etc.).
            metadata: Optional metadata (source path, author, etc.).

        Returns:
            ResourceVersion with version number and timestamp.
        """
        ...

    def get_resource(
        self,
        resource_id: str,
        version: int | None = None,
    ) -> Resource | None:
        """Get a resource by ID, optionally at a specific version.

        Args:
            resource_id: The resource ID to retrieve.
            version: Specific version number (None = latest).

        Returns:
            Resource or None if not found.
        """
        ...

    def list_resources(
        self,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[Resource]:
        """List registered resources.

        Args:
            resource_type: Filter by type (agent, skill, prompt, command).
            limit: Maximum number of resources to return.

        Returns:
            List of resources.
        """
        ...

    def get_resource_versions(
        self,
        resource_id: str,
        limit: int = 10,
    ) -> list[ResourceVersion]:
        """Get version history for a resource.

        Args:
            resource_id: The resource ID.
            limit: Maximum versions to return.

        Returns:
            List of versions, most recent first.
        """
        ...

    def delete_resource(self, resource_id: str) -> bool:
        """Delete a resource and all its versions.

        Args:
            resource_id: The resource ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    # =========================================================================
    # Evaluation Queue Operations
    # =========================================================================

    def enqueue_evaluation(
        self,
        resource_id: str,
        resource_type: str,
        config: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> str:
        """Enqueue a resource for evaluation.

        Args:
            resource_id: The resource to evaluate.
            resource_type: Type of resource.
            config: Evaluation configuration (test cases, parameters).
            priority: Higher priority = processed first (default: 0).

        Returns:
            Evaluation ID for tracking.
        """
        ...

    def dequeue_evaluation(
        self,
        runner_id: str,
        timeout_seconds: int = 30,
    ) -> EvaluationTask | None:
        """Dequeue the next evaluation task.

        Claims the task for the specified runner. Task is marked as
        in-progress and must be completed or failed within timeout.

        Args:
            runner_id: Identifier of the runner claiming the task.
            timeout_seconds: Seconds before task can be reclaimed.

        Returns:
            EvaluationTask or None if queue is empty.
        """
        ...

    def get_evaluation_status(self, evaluation_id: str) -> dict[str, Any] | None:
        """Get status of an evaluation.

        Args:
            evaluation_id: The evaluation ID.

        Returns:
            Status dict with state, runner_id, timestamps, etc.
        """
        ...

    def complete_evaluation(
        self,
        evaluation_id: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> bool:
        """Mark an evaluation as complete.

        Args:
            evaluation_id: The evaluation ID.
            success: Whether evaluation succeeded.
            error_message: Error details if failed.

        Returns:
            True if updated, False if evaluation not found.
        """
        ...

    def get_queue_length(self) -> int:
        """Get number of pending evaluations in the queue.

        Returns:
            Number of queued evaluations.
        """
        ...

    # =========================================================================
    # Result Operations
    # =========================================================================

    def store_result(
        self,
        evaluation_id: str,
        resource_id: str,
        reward: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store an evaluation result.

        Args:
            evaluation_id: The evaluation this result is for.
            resource_id: The evaluated resource.
            reward: Multi-dimensional reward scores.
            metadata: Additional result metadata.
        """
        ...

    def query_results(
        self,
        resource_id: str | None = None,
        resource_type: str | None = None,
        min_score: float | None = None,
        limit: int = 100,
    ) -> list[EvaluationResult]:
        """Query evaluation results.

        Args:
            resource_id: Filter by resource.
            resource_type: Filter by resource type.
            min_score: Minimum composite score.
            limit: Maximum results to return.

        Returns:
            List of results, highest scores first.
        """
        ...

    def get_best_result(
        self,
        resource_id: str,
    ) -> EvaluationResult | None:
        """Get the best evaluation result for a resource.

        Args:
            resource_id: The resource ID.

        Returns:
            Best result or None if no results exist.
        """
        ...

    def get_result_history(
        self,
        resource_id: str,
        limit: int = 50,
    ) -> list[EvaluationResult]:
        """Get evaluation history for a resource.

        Args:
            resource_id: The resource ID.
            limit: Maximum results to return.

        Returns:
            List of results, most recent first.
        """
        ...

    # =========================================================================
    # Lifecycle Operations
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Check store health and connectivity.

        Returns:
            Health status with connection info, metrics, etc.
        """
        ...

    def clear(self) -> None:
        """Clear all data from the store.

        WARNING: This deletes all spans, resources, and results.
        Primarily for testing.
        """
        ...

    def close(self) -> None:
        """Close connections and release resources."""
        ...
