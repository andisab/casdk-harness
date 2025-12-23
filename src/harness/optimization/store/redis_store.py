"""Redis implementation of the CGF Optimization Store.

Provides a production-ready Redis-backed store for distributed evaluation
coordination and persistent span storage.

Example usage:
    store = RedisOptimizationStore(url="redis://localhost:6379")

    # Store a span
    store.store_span(span)

    # Register a resource
    version = store.register_resource("agent-1", "agent", content)

    # Enqueue and process evaluations
    eval_id = store.enqueue_evaluation("agent-1", "agent", config)
    task = store.dequeue_evaluation("runner-1")
    store.store_result(eval_id, "agent-1", reward)

Redis Key Structure:
    cgf:eval:queue              # Evaluation task queue (List)
    cgf:eval:status:{eval_id}   # Per-evaluation status (Hash)
    cgf:spans:{trace_id}        # Spans for trace (Sorted Set by timestamp)
    cgf:resources:{resource_id} # Resource metadata (Hash)
    cgf:resources:{resource_id}:versions  # Resource versions (Sorted Set)
    cgf:resources:{resource_id}:content:{version}  # Version content (String)
    cgf:results:{resource_id}   # Evaluation results (Sorted Set by score)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
from harness.tracer.base import Span, SpanKind, SpanStatus

logger = structlog.get_logger(__name__)

# Key prefixes
KEY_EVAL_QUEUE = "cgf:eval:queue"
KEY_EVAL_STATUS = "cgf:eval:status:{eval_id}"
KEY_SPANS = "cgf:spans:{trace_id}"
KEY_SPANS_INDEX = "cgf:spans:index"
KEY_RESOURCES = "cgf:resources:{resource_id}"
KEY_RESOURCE_VERSIONS = "cgf:resources:{resource_id}:versions"
KEY_RESOURCE_CONTENT = "cgf:resources:{resource_id}:content:{version}"
KEY_RESULTS = "cgf:results:{resource_id}"
KEY_RESULTS_INDEX = "cgf:results:index"


def _serialize_span(span: Span) -> str:
    """Serialize a span to JSON string."""
    return json.dumps({
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "name": span.name,
        "kind": span.kind.value,
        "start_time": span.start_time.isoformat(),
        "end_time": span.end_time.isoformat() if span.end_time else None,
        "attributes": span.attributes,
        "status": span.status.value,
        "error_message": span.error_message,
        "events": span.events,
        "duration_ms": span.duration_ms,
        "token_usage": span.token_usage,
        "resource_id": span.resource_id,
        "agent_name": span.agent_name,
    })


def _deserialize_span(data: str) -> Span:
    """Deserialize a span from JSON string."""
    d = json.loads(data)
    return Span(
        trace_id=d["trace_id"],
        span_id=d["span_id"],
        parent_span_id=d.get("parent_span_id"),
        name=d["name"],
        kind=SpanKind(d["kind"]),
        start_time=datetime.fromisoformat(d["start_time"]),
        end_time=datetime.fromisoformat(d["end_time"]) if d.get("end_time") else None,
        attributes=d.get("attributes", {}),
        status=SpanStatus(d["status"]),
        error_message=d.get("error_message"),
        events=d.get("events", []),
        duration_ms=d.get("duration_ms"),
        token_usage=d.get("token_usage"),
        resource_id=d.get("resource_id"),
        agent_name=d.get("agent_name"),
    )


@dataclass
class RedisOptimizationStore:
    """Redis implementation of OptimizationStore.

    Production-ready store with distributed coordination support.
    Uses Redis data structures for efficient queuing and querying.

    Attributes:
        url: Redis connection URL.
        name: Store name for identification.
        span_ttl_days: Days to retain spans (default: 7).
        result_ttl_days: Days to retain results (default: 30).
    """

    url: str = "redis://localhost:6379"
    name: str = "redis"
    span_ttl_days: int = 7
    result_ttl_days: int = 30

    _client: Any = field(default=None, repr=False)
    _connected: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize Redis connection."""
        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection."""
        try:
            import redis

            self._client = redis.from_url(
                self.url,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.debug("Redis store connected", url=self.url)
        except ImportError:
            logger.error("redis package not installed")
            raise RuntimeError("redis package required: pip install redis")
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))
            self._connected = False
            raise

    # =========================================================================
    # Span Operations
    # =========================================================================

    def store_span(self, span: Span) -> None:
        """Store a completed span."""
        key = KEY_SPANS.format(trace_id=span.trace_id)
        score = span.start_time.timestamp()
        data = _serialize_span(span)

        pipe = self._client.pipeline()
        pipe.zadd(key, {data: score})
        pipe.expire(key, timedelta(days=self.span_ttl_days))
        # Track trace_id in index for querying
        pipe.sadd(KEY_SPANS_INDEX, span.trace_id)
        pipe.execute()

        logger.debug(
            "Span stored",
            trace_id=span.trace_id[:8],
            span_id=span.span_id,
        )

    def store_spans(self, spans: list[Span]) -> None:
        """Store multiple spans in a batch."""
        if not spans:
            return

        pipe = self._client.pipeline()

        for span in spans:
            key = KEY_SPANS.format(trace_id=span.trace_id)
            score = span.start_time.timestamp()
            data = _serialize_span(span)

            pipe.zadd(key, {data: score})
            pipe.expire(key, timedelta(days=self.span_ttl_days))
            pipe.sadd(KEY_SPANS_INDEX, span.trace_id)

        pipe.execute()
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
        results: list[Span] = []

        if trace_id:
            # Query specific trace
            trace_ids = [trace_id]
        else:
            # Query all traces from index
            trace_ids = list(self._client.smembers(KEY_SPANS_INDEX))

        # Build score range
        min_score = start_time.timestamp() if start_time else "-inf"
        max_score = end_time.timestamp() if end_time else "+inf"

        for tid in trace_ids:
            key = KEY_SPANS.format(trace_id=tid)
            span_data = self._client.zrangebyscore(
                key, min_score, max_score, start=0, num=limit
            )

            for data in span_data:
                span = _deserialize_span(data)

                # Apply filters
                if resource_id and span.resource_id != resource_id:
                    continue
                if agent_name and span.agent_name != agent_name:
                    continue

                results.append(span)

                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

        # Sort by start_time descending
        results.sort(key=lambda s: s.start_time, reverse=True)
        return results[:limit]

    def get_trace_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a specific trace."""
        key = KEY_SPANS.format(trace_id=trace_id)
        span_data = self._client.zrange(key, 0, -1)

        spans = [_deserialize_span(data) for data in span_data]
        return sorted(spans, key=lambda s: s.start_time)

    def delete_trace(self, trace_id: str) -> bool:
        """Delete all spans for a trace."""
        key = KEY_SPANS.format(trace_id=trace_id)

        pipe = self._client.pipeline()
        pipe.delete(key)
        pipe.srem(KEY_SPANS_INDEX, trace_id)
        results = pipe.execute()

        deleted = results[0] > 0
        if deleted:
            logger.debug("Trace deleted", trace_id=trace_id[:8])
        return deleted

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
        content_hash = compute_content_hash(content)
        now = datetime.now(timezone.utc)

        resource_key = KEY_RESOURCES.format(resource_id=resource_id)
        versions_key = KEY_RESOURCE_VERSIONS.format(resource_id=resource_id)

        # Check if resource exists
        existing = self._client.hgetall(resource_key)

        if existing:
            # Check for duplicate content
            if existing.get("content_hash") == content_hash:
                logger.debug(
                    "Resource unchanged, skipping version",
                    resource_id=resource_id,
                )
                # Return current version
                return ResourceVersion.from_dict(json.loads(existing["current_version"]))

            # Create new version
            current_version = json.loads(existing["current_version"])
            new_version_num = current_version["version"] + 1

            new_version = ResourceVersion(
                version=new_version_num,
                content_hash=content_hash,
                created_at=now,
                metadata=metadata or {},
            )

            # Store content for this version
            content_key = KEY_RESOURCE_CONTENT.format(
                resource_id=resource_id, version=new_version_num
            )

            pipe = self._client.pipeline()
            pipe.hset(resource_key, mapping={
                "content_hash": content_hash,
                "current_version": json.dumps(new_version.to_dict()),
                "updated_at": now.isoformat(),
            })
            pipe.zadd(versions_key, {json.dumps(new_version.to_dict()): new_version_num})
            pipe.set(content_key, content)
            pipe.execute()

            logger.debug(
                "Resource updated",
                resource_id=resource_id,
                version=new_version_num,
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

            content_key = KEY_RESOURCE_CONTENT.format(
                resource_id=resource_id, version=1
            )

            pipe = self._client.pipeline()
            pipe.hset(resource_key, mapping={
                "resource_id": resource_id,
                "resource_type": resource_type,
                "content_hash": content_hash,
                "current_version": json.dumps(version.to_dict()),
                "metadata": json.dumps(metadata or {}),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            pipe.zadd(versions_key, {json.dumps(version.to_dict()): 1})
            pipe.set(content_key, content)
            pipe.execute()

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
        resource_key = KEY_RESOURCES.format(resource_id=resource_id)
        data = self._client.hgetall(resource_key)

        if not data:
            return None

        if version is None:
            # Get latest version
            current_version = ResourceVersion.from_dict(
                json.loads(data["current_version"])
            )
            version_num = current_version.version
        else:
            version_num = version
            # Get specific version info
            versions_key = KEY_RESOURCE_VERSIONS.format(resource_id=resource_id)
            version_data = self._client.zrangebyscore(
                versions_key, version_num, version_num
            )
            if not version_data:
                return None
            current_version = ResourceVersion.from_dict(json.loads(version_data[0]))

        # Get content for version
        content_key = KEY_RESOURCE_CONTENT.format(
            resource_id=resource_id, version=version_num
        )
        content = self._client.get(content_key)
        if content is None:
            return None

        return Resource(
            resource_id=data["resource_id"],
            resource_type=data["resource_type"],
            content=content,
            current_version=current_version,
            metadata=json.loads(data.get("metadata", "{}")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def list_resources(
        self,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[Resource]:
        """List registered resources."""
        # Scan for all resource keys
        resources: list[Resource] = []

        cursor = 0
        pattern = "cgf:resources:*"

        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)

            for key in keys:
                # Skip version and content keys
                if ":versions" in key or ":content:" in key:
                    continue

                data = self._client.hgetall(key)
                if not data or "resource_id" not in data:
                    continue

                if resource_type and data.get("resource_type") != resource_type:
                    continue

                # Get content for current version
                current_version = ResourceVersion.from_dict(
                    json.loads(data["current_version"])
                )
                content_key = KEY_RESOURCE_CONTENT.format(
                    resource_id=data["resource_id"],
                    version=current_version.version,
                )
                content = self._client.get(content_key) or ""

                resource = Resource(
                    resource_id=data["resource_id"],
                    resource_type=data["resource_type"],
                    content=content,
                    current_version=current_version,
                    metadata=json.loads(data.get("metadata", "{}")),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"]),
                )
                resources.append(resource)

                if len(resources) >= limit:
                    break

            if cursor == 0 or len(resources) >= limit:
                break

        # Sort by updated_at descending
        resources.sort(key=lambda r: r.updated_at, reverse=True)
        return resources[:limit]

    def get_resource_versions(
        self,
        resource_id: str,
        limit: int = 10,
    ) -> list[ResourceVersion]:
        """Get version history for a resource."""
        versions_key = KEY_RESOURCE_VERSIONS.format(resource_id=resource_id)

        # Get versions sorted by version number descending
        version_data = self._client.zrevrange(versions_key, 0, limit - 1)

        return [ResourceVersion.from_dict(json.loads(v)) for v in version_data]

    def delete_resource(self, resource_id: str) -> bool:
        """Delete a resource and all its versions."""
        resource_key = KEY_RESOURCES.format(resource_id=resource_id)
        versions_key = KEY_RESOURCE_VERSIONS.format(resource_id=resource_id)

        # Check if exists
        if not self._client.exists(resource_key):
            return False

        # Get all versions to delete content keys
        version_data = self._client.zrange(versions_key, 0, -1)
        content_keys = []
        for v in version_data:
            version = json.loads(v)
            content_keys.append(
                KEY_RESOURCE_CONTENT.format(
                    resource_id=resource_id, version=version["version"]
                )
            )

        # Delete all keys
        pipe = self._client.pipeline()
        pipe.delete(resource_key)
        pipe.delete(versions_key)
        for ck in content_keys:
            pipe.delete(ck)
        pipe.execute()

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
        task = EvaluationTask(
            evaluation_id=generate_evaluation_id(),
            resource_id=resource_id,
            resource_type=resource_type,
            config=config or {},
            priority=priority,
            status=EvaluationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        task_data = json.dumps(task.to_dict())
        status_key = KEY_EVAL_STATUS.format(eval_id=task.evaluation_id)

        pipe = self._client.pipeline()
        # Use priority as score (negated so higher priority = lower score = first)
        pipe.zadd(KEY_EVAL_QUEUE, {task_data: -priority})
        pipe.hset(status_key, mapping=task.to_dict())
        pipe.execute()

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
        now = datetime.now(timezone.utc)

        # Pop highest priority item (lowest score)
        result = self._client.zpopmin(KEY_EVAL_QUEUE, count=1)
        if not result:
            return None

        task_data, _ = result[0]
        task = EvaluationTask.from_dict(json.loads(task_data))

        # Update task status
        task.status = EvaluationStatus.IN_PROGRESS
        task.runner_id = runner_id
        task.started_at = now
        task.timeout_at = now + timedelta(seconds=timeout_seconds)

        status_key = KEY_EVAL_STATUS.format(eval_id=task.evaluation_id)
        self._client.hset(status_key, mapping={
            "status": task.status.value,
            "runner_id": runner_id,
            "started_at": now.isoformat(),
            "timeout_at": task.timeout_at.isoformat(),
        })

        logger.debug(
            "Evaluation dequeued",
            evaluation_id=task.evaluation_id,
            runner_id=runner_id,
        )
        return task

    def get_evaluation_status(self, evaluation_id: str) -> dict[str, Any] | None:
        """Get status of an evaluation."""
        status_key = KEY_EVAL_STATUS.format(eval_id=evaluation_id)
        data = self._client.hgetall(status_key)

        if not data:
            return None

        return {
            "evaluation_id": data.get("evaluation_id", evaluation_id),
            "status": data.get("status", "unknown"),
            "runner_id": data.get("runner_id"),
            "created_at": data.get("created_at"),
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
            "error_message": data.get("error_message"),
        }

    def complete_evaluation(
        self,
        evaluation_id: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> bool:
        """Mark an evaluation as complete."""
        status_key = KEY_EVAL_STATUS.format(eval_id=evaluation_id)

        if not self._client.exists(status_key):
            return False

        now = datetime.now(timezone.utc)
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        self._client.hset(status_key, mapping={
            "status": status.value,
            "completed_at": now.isoformat(),
            "error_message": error_message or "",
        })

        logger.debug(
            "Evaluation completed",
            evaluation_id=evaluation_id,
            success=success,
        )
        return True

    def get_queue_length(self) -> int:
        """Get number of pending evaluations in the queue."""
        return self._client.zcard(KEY_EVAL_QUEUE)

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
        # Get resource info
        resource = self.get_resource(resource_id)
        resource_type = resource.resource_type if resource else ""
        resource_version = resource.current_version.version if resource else 1

        result = EvaluationResult(
            evaluation_id=evaluation_id,
            resource_id=resource_id,
            resource_type=resource_type,
            resource_version=resource_version,
            reward=reward,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
        )

        results_key = KEY_RESULTS.format(resource_id=resource_id)
        result_data = json.dumps(result.to_dict())

        pipe = self._client.pipeline()
        pipe.zadd(results_key, {result_data: result.composite_score})
        pipe.expire(results_key, timedelta(days=self.result_ttl_days))
        pipe.sadd(KEY_RESULTS_INDEX, resource_id)
        pipe.execute()

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
        results: list[EvaluationResult] = []

        if resource_id:
            resource_ids = [resource_id]
        else:
            resource_ids = list(self._client.smembers(KEY_RESULTS_INDEX))

        min_s = min_score if min_score is not None else "-inf"

        for rid in resource_ids:
            results_key = KEY_RESULTS.format(resource_id=rid)
            result_data = self._client.zrangebyscore(
                results_key, min_s, "+inf", start=0, num=limit
            )

            for data in result_data:
                result = EvaluationResult.from_dict(json.loads(data))

                if resource_type and result.resource_type != resource_type:
                    continue

                results.append(result)

                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

        # Sort by composite_score descending
        results.sort(key=lambda r: r.composite_score, reverse=True)
        return results[:limit]

    def get_best_result(
        self,
        resource_id: str,
    ) -> EvaluationResult | None:
        """Get the best evaluation result for a resource."""
        results_key = KEY_RESULTS.format(resource_id=resource_id)

        # Get highest score result
        result_data = self._client.zrevrange(results_key, 0, 0)
        if not result_data:
            return None

        return EvaluationResult.from_dict(json.loads(result_data[0]))

    def get_result_history(
        self,
        resource_id: str,
        limit: int = 50,
    ) -> list[EvaluationResult]:
        """Get evaluation history for a resource."""
        results_key = KEY_RESULTS.format(resource_id=resource_id)

        # Get all results
        result_data = self._client.zrange(results_key, 0, -1)

        results = [EvaluationResult.from_dict(json.loads(d)) for d in result_data]

        # Sort by created_at descending
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    # =========================================================================
    # Lifecycle Operations
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Check store health and connectivity."""
        try:
            self._client.ping()
            connected = True
        except Exception:
            connected = False

        metrics = self.get_metrics()
        return {
            "status": "healthy" if connected else "unhealthy",
            "store_type": "redis",
            "connected": connected,
            "url": self.url,
            "metrics": metrics.to_dict(),
        }

    def get_metrics(self) -> StoreMetrics:
        """Get store metrics."""
        try:
            span_count = len(self._client.smembers(KEY_SPANS_INDEX))
            resource_count = 0
            cursor = 0
            while True:
                cursor, keys = self._client.scan(
                    cursor, match="cgf:resources:*", count=100
                )
                resource_count += sum(
                    1 for k in keys
                    if ":versions" not in k and ":content:" not in k
                )
                if cursor == 0:
                    break

            result_count = 0
            for rid in self._client.smembers(KEY_RESULTS_INDEX):
                results_key = KEY_RESULTS.format(resource_id=rid)
                result_count += self._client.zcard(results_key)

            return StoreMetrics(
                span_count=span_count,
                resource_count=resource_count,
                evaluation_count=self._client.zcard(KEY_EVAL_QUEUE),
                result_count=result_count,
                queue_length=self.get_queue_length(),
                connected=True,
            )
        except Exception:
            return StoreMetrics(connected=False)

    def clear(self) -> None:
        """Clear all data from the store."""
        # Delete all CGF keys
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match="cgf:*", count=100)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

        logger.debug("Redis store cleared")

    def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            self._client.close()
            self._connected = False
        logger.debug("Redis store closed")

    def __repr__(self) -> str:
        return f"RedisOptimizationStore(url={self.url!r}, name={self.name!r})"
