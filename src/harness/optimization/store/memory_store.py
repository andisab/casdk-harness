"""In-memory implementation of the CGF Optimization Store.

Provides a thread-safe in-memory store for testing and development.
All data is lost when the process exits.

Example usage:
    store = MemoryOptimizationStore()

    # Store a span
    store.store_span(span)

    # Register a resource
    version = store.register_resource("agent-1", "agent", content)

    # Enqueue and process evaluations
    eval_id = store.enqueue_evaluation("agent-1", "agent", config)
    task = store.dequeue_evaluation("runner-1")
    store.store_result(eval_id, "agent-1", reward)
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from harness.optimization.store.models import (
    EvaluationResult,
    EvaluationStatus,
    EvaluationTask,
    Resource,
    ResourceVersion,
    StoreMetrics,
    compute_content_hash,
    generate_evaluation_id,
)
from harness.tracer.base import Span

logger = structlog.get_logger(__name__)


@dataclass
class MemoryOptimizationStore:
    """In-memory implementation of OptimizationStore.

    Thread-safe store for testing and development. Uses locks
    to ensure safe concurrent access.

    Attributes:
        name: Store name for identification.
    """

    name: str = "memory"

    # Internal storage
    _spans: dict[str, list[Span]] = field(default_factory=lambda: defaultdict(list))
    _resources: dict[str, Resource] = field(default_factory=dict)
    _resource_versions: dict[str, list[ResourceVersion]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _resource_contents: dict[str, dict[int, str]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    _evaluation_queue: list[EvaluationTask] = field(default_factory=list)
    _evaluations: dict[str, EvaluationTask] = field(default_factory=dict)
    _results: dict[str, list[EvaluationResult]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        logger.debug("Memory optimization store initialized", name=self.name)

    # =========================================================================
    # Span Operations
    # =========================================================================

    def store_span(self, span: Span) -> None:
        """Store a completed span."""
        with self._lock:
            self._spans[span.trace_id].append(span)
            logger.debug(
                "Span stored",
                trace_id=span.trace_id[:8],
                span_id=span.span_id,
            )

    def store_spans(self, spans: list[Span]) -> None:
        """Store multiple spans in a batch."""
        with self._lock:
            for span in spans:
                self._spans[span.trace_id].append(span)
            logger.debug("Spans stored", count=len(spans))

    def query_spans(
        self,
        trace_id: str | None = None,
        resource_id: str | None = None,
        agent_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[Span]:
        """Query spans with optional filters."""
        with self._lock:
            results: list[Span] = []

            # Collect all spans or filter by trace_id
            if trace_id:
                spans = self._spans.get(trace_id, [])
            else:
                spans = [s for spans_list in self._spans.values() for s in spans_list]

            for span in spans:
                # Apply filters
                if resource_id and span.resource_id != resource_id:
                    continue
                if agent_name and span.agent_name != agent_name:
                    continue
                if start_time and span.start_time < start_time:
                    continue
                if end_time and span.start_time > end_time:
                    continue

                results.append(span)

            # Sort by start_time descending and limit
            results.sort(key=lambda s: s.start_time, reverse=True)
            return results[:limit]

    def get_trace_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a specific trace."""
        with self._lock:
            spans = self._spans.get(trace_id, [])
            return sorted(spans, key=lambda s: s.start_time)

    def delete_trace(self, trace_id: str) -> bool:
        """Delete all spans for a trace."""
        with self._lock:
            if trace_id in self._spans:
                del self._spans[trace_id]
                logger.debug("Trace deleted", trace_id=trace_id[:8])
                return True
            return False

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
        """Register a new resource or version."""
        with self._lock:
            content_hash = compute_content_hash(content)
            now = datetime.now(UTC)

            # Check if resource exists
            existing = self._resources.get(resource_id)

            if existing:
                # Check for duplicate content
                if existing.current_version.content_hash == content_hash:
                    logger.debug(
                        "Resource unchanged, skipping version",
                        resource_id=resource_id,
                    )
                    return existing.current_version

                # Create new version
                new_version = ResourceVersion(
                    version=existing.current_version.version + 1,
                    content_hash=content_hash,
                    created_at=now,
                    metadata=metadata or {},
                )

                existing.content = content
                existing.current_version = new_version
                existing.updated_at = now

                self._resource_versions[resource_id].append(new_version)
                self._resource_contents[resource_id][new_version.version] = content

                logger.debug(
                    "Resource updated",
                    resource_id=resource_id,
                    version=new_version.version,
                )
                return new_version

            else:
                # Create new resource
                version = ResourceVersion(
                    version=1,
                    content_hash=content_hash,
                    created_at=now,
                    metadata=metadata or {},
                )

                resource = Resource(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    content=content,
                    current_version=version,
                    metadata=metadata or {},
                    created_at=now,
                    updated_at=now,
                )

                self._resources[resource_id] = resource
                self._resource_versions[resource_id].append(version)
                self._resource_contents[resource_id][1] = content

                logger.debug(
                    "Resource registered",
                    resource_id=resource_id,
                    resource_type=resource_type,
                )
                return version

    def get_resource(
        self,
        resource_id: str,
        version: int | None = None,
    ) -> Resource | None:
        """Get a resource by ID, optionally at a specific version."""
        with self._lock:
            resource = self._resources.get(resource_id)
            if not resource:
                return None

            if version is None:
                return resource

            # Get specific version
            versions = self._resource_versions.get(resource_id, [])
            version_info = next((v for v in versions if v.version == version), None)

            if not version_info:
                return None

            # Get content for that version
            content = self._resource_contents.get(resource_id, {}).get(version)
            if content is None:
                return None

            # Return resource with specific version
            return Resource(
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                content=content,
                current_version=version_info,
                metadata=resource.metadata,
                created_at=resource.created_at,
                updated_at=version_info.created_at,
            )

    def list_resources(
        self,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[Resource]:
        """List registered resources."""
        with self._lock:
            resources = list(self._resources.values())

            if resource_type:
                resources = [r for r in resources if r.resource_type == resource_type]

            # Sort by updated_at descending
            resources.sort(key=lambda r: r.updated_at, reverse=True)
            return resources[:limit]

    def get_resource_versions(
        self,
        resource_id: str,
        limit: int = 10,
    ) -> list[ResourceVersion]:
        """Get version history for a resource."""
        with self._lock:
            versions = self._resource_versions.get(resource_id, [])
            # Return most recent first
            return sorted(versions, key=lambda v: v.version, reverse=True)[:limit]

    def delete_resource(self, resource_id: str) -> bool:
        """Delete a resource and all its versions."""
        with self._lock:
            if resource_id not in self._resources:
                return False

            del self._resources[resource_id]
            self._resource_versions.pop(resource_id, None)
            self._resource_contents.pop(resource_id, None)

            logger.debug("Resource deleted", resource_id=resource_id)
            return True

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
        """Enqueue a resource for evaluation."""
        with self._lock:
            task = EvaluationTask(
                evaluation_id=generate_evaluation_id(),
                resource_id=resource_id,
                resource_type=resource_type,
                config=config or {},
                priority=priority,
                status=EvaluationStatus.PENDING,
                created_at=datetime.now(UTC),
            )

            self._evaluation_queue.append(task)
            self._evaluations[task.evaluation_id] = task

            # Sort by priority (higher first), then by created_at
            self._evaluation_queue.sort(
                key=lambda t: (-t.priority, t.created_at)
            )

            logger.debug(
                "Evaluation enqueued",
                evaluation_id=task.evaluation_id,
                resource_id=resource_id,
            )
            return task.evaluation_id

    def dequeue_evaluation(
        self,
        runner_id: str,
        timeout_seconds: int = 30,
    ) -> EvaluationTask | None:
        """Dequeue the next evaluation task."""
        with self._lock:
            now = datetime.now(UTC)

            # Find first pending task
            for i, task in enumerate(self._evaluation_queue):
                if task.status == EvaluationStatus.PENDING:
                    # Claim the task
                    task.status = EvaluationStatus.IN_PROGRESS
                    task.runner_id = runner_id
                    task.started_at = now
                    task.timeout_at = now + timedelta(seconds=timeout_seconds)

                    # Remove from queue
                    self._evaluation_queue.pop(i)

                    logger.debug(
                        "Evaluation dequeued",
                        evaluation_id=task.evaluation_id,
                        runner_id=runner_id,
                    )
                    return task

            return None

    def get_evaluation_status(self, evaluation_id: str) -> dict[str, Any] | None:
        """Get status of an evaluation."""
        with self._lock:
            task = self._evaluations.get(evaluation_id)
            if not task:
                return None

            return {
                "evaluation_id": task.evaluation_id,
                "status": task.status.value,
                "runner_id": task.runner_id,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
            }

    def complete_evaluation(
        self,
        evaluation_id: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> bool:
        """Mark an evaluation as complete."""
        with self._lock:
            task = self._evaluations.get(evaluation_id)
            if not task:
                return False

            task.status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED
            task.completed_at = datetime.now(UTC)
            task.error_message = error_message

            logger.debug(
                "Evaluation completed",
                evaluation_id=evaluation_id,
                success=success,
            )
            return True

    def get_queue_length(self) -> int:
        """Get number of pending evaluations in the queue."""
        with self._lock:
            return len([t for t in self._evaluation_queue if t.status == EvaluationStatus.PENDING])

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
        """Store an evaluation result."""
        with self._lock:
            # Get resource info
            resource = self._resources.get(resource_id)
            resource_type = resource.resource_type if resource else ""
            resource_version = resource.current_version.version if resource else 1

            result = EvaluationResult(
                evaluation_id=evaluation_id,
                resource_id=resource_id,
                resource_type=resource_type,
                resource_version=resource_version,
                reward=reward,
                metadata=metadata or {},
                created_at=datetime.now(UTC),
            )

            self._results[resource_id].append(result)

            # Sort by composite_score descending
            self._results[resource_id].sort(
                key=lambda r: r.composite_score, reverse=True
            )

            logger.debug(
                "Result stored",
                evaluation_id=evaluation_id,
                resource_id=resource_id,
                composite_score=result.composite_score,
            )

    def query_results(
        self,
        resource_id: str | None = None,
        resource_type: str | None = None,
        min_score: float | None = None,
        limit: int = 100,
    ) -> list[EvaluationResult]:
        """Query evaluation results."""
        with self._lock:
            if resource_id:
                results = self._results.get(resource_id, [])
            else:
                results = [r for rs in self._results.values() for r in rs]

            # Apply filters
            if resource_type:
                results = [r for r in results if r.resource_type == resource_type]
            if min_score is not None:
                results = [r for r in results if r.composite_score >= min_score]

            # Sort by composite_score descending
            results.sort(key=lambda r: r.composite_score, reverse=True)
            return results[:limit]

    def get_best_result(
        self,
        resource_id: str,
    ) -> EvaluationResult | None:
        """Get the best evaluation result for a resource."""
        with self._lock:
            results = self._results.get(resource_id, [])
            if not results:
                return None
            return max(results, key=lambda r: r.composite_score)

    def get_result_history(
        self,
        resource_id: str,
        limit: int = 50,
    ) -> list[EvaluationResult]:
        """Get evaluation history for a resource."""
        with self._lock:
            results = self._results.get(resource_id, [])
            # Sort by created_at descending
            results = sorted(results, key=lambda r: r.created_at, reverse=True)
            return results[:limit]

    # =========================================================================
    # Lifecycle Operations
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Check store health and connectivity."""
        with self._lock:
            metrics = self.get_metrics()
            return {
                "status": "healthy",
                "store_type": "memory",
                "connected": True,
                "metrics": metrics.to_dict(),
            }

    def get_metrics(self) -> StoreMetrics:
        """Get store metrics."""
        with self._lock:
            return StoreMetrics(
                span_count=sum(len(spans) for spans in self._spans.values()),
                resource_count=len(self._resources),
                evaluation_count=len(self._evaluations),
                result_count=sum(len(results) for results in self._results.values()),
                queue_length=self.get_queue_length(),
                connected=True,
            )

    def clear(self) -> None:
        """Clear all data from the store."""
        with self._lock:
            self._spans.clear()
            self._resources.clear()
            self._resource_versions.clear()
            self._resource_contents.clear()
            self._evaluation_queue.clear()
            self._evaluations.clear()
            self._results.clear()
            logger.debug("Memory store cleared")

    def close(self) -> None:
        """Close the store (no-op for memory store)."""
        logger.debug("Memory store closed")

    def __repr__(self) -> str:
        return f"MemoryOptimizationStore(name={self.name!r})"
