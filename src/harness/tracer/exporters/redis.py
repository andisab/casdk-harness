"""Redis-based span exporter for production tracing.

Exports spans to Redis for distributed trace collection and querying.
Supports TTL-based retention and efficient trace retrieval.

Example usage:
    exporter = RedisSpanExporter("redis://localhost:6379")
    tracer.add_exporter(exporter)

    # Spans are stored in Redis sorted sets:
    # cgf:spans:{trace_id} -> sorted set by timestamp
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import redis
import structlog
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from harness.tracer.base import Span

logger = structlog.get_logger(__name__)

# Redis key prefixes
SPAN_KEY_PREFIX = "cgf:spans"
TRACE_INDEX_KEY = "cgf:trace_index"
SPAN_COUNTER_KEY = "cgf:span_counter"


@dataclass
class RedisSpanExporter:
    """Exports spans to Redis for distributed tracing.

    Thread-safe implementation with connection pooling, retry logic,
    and automatic TTL-based cleanup.

    Attributes:
        redis_url: Redis connection URL.
        key_prefix: Prefix for all Redis keys (default: "cgf:spans").
        ttl_seconds: Time-to-live for spans in seconds (default: 7 days).
        buffer_size: Number of spans to buffer before writing (0 = immediate).
        connection_timeout: Connection timeout in seconds.
        socket_timeout: Socket timeout in seconds.
    """

    redis_url: str
    key_prefix: str = SPAN_KEY_PREFIX
    ttl_seconds: int = 7 * 24 * 3600  # 7 days default
    buffer_size: int = 0
    connection_timeout: float = 5.0
    socket_timeout: float = 5.0

    _client: redis.Redis | None = field(default=None, repr=False)
    _buffer: list[Span] = field(default_factory=list, repr=False)
    _connected: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection with retry."""
        try:
            self._connect_with_retry()
            logger.debug(
                "Redis span exporter connected",
                url=self._sanitize_url(self.redis_url),
            )
        except RetryError as e:
            logger.warning(
                "Redis span exporter failed to connect after retries",
                error=str(e),
            )
        except Exception as e:
            logger.warning(
                "Redis span exporter connection error",
                error=str(e),
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    def _connect_with_retry(self) -> None:
        """Internal connection with retry logic."""
        self._client = redis.Redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=self.connection_timeout,
            socket_timeout=self.socket_timeout,
        )
        # Test connection
        self._client.ping()
        self._connected = True

    def _sanitize_url(self, url: str) -> str:
        """Remove password from URL for logging."""
        if "@" in url:
            # Format: redis://user:pass@host:port
            parts = url.split("@")
            return f"redis://***@{parts[-1]}"
        return url

    def export(self, span: Span) -> None:
        """Export a single span to Redis.

        Args:
            span: The span to export.
        """
        if self.buffer_size > 0:
            self._buffer.append(span)
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
        else:
            self._write_span(span)

    def export_batch(self, spans: list[Span]) -> None:
        """Export multiple spans to Redis.

        Uses pipelining for efficient bulk writes.

        Args:
            spans: List of spans to export.
        """
        if not spans:
            return

        if self.buffer_size > 0:
            self._buffer.extend(spans)
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
        else:
            self._write_spans_pipelined(spans)

    def _write_span(self, span: Span) -> None:
        """Write a single span to Redis.

        Args:
            span: Span to write.
        """
        if not self._connected or not self._client:
            logger.warning(
                "Redis not connected, dropping span",
                span_id=span.span_id,
            )
            return

        try:
            trace_key = f"{self.key_prefix}:{span.trace_id}"
            span_data = json.dumps(span.to_dict(), default=str)

            # Use timestamp as score for sorted set ordering
            score = span.start_time.timestamp()

            pipe = self._client.pipeline()

            # Add span to trace's sorted set
            pipe.zadd(trace_key, {span_data: score})

            # Set TTL on the trace key
            pipe.expire(trace_key, self.ttl_seconds)

            # Add trace_id to index for enumeration
            index_key = f"{self.key_prefix}:index"
            pipe.zadd(index_key, {span.trace_id: score})
            pipe.expire(index_key, self.ttl_seconds)

            # Increment counter for metrics
            pipe.incr(f"{self.key_prefix}:counter")

            pipe.execute()

            logger.debug(
                "Span exported to Redis",
                span_id=span.span_id,
                trace_id=span.trace_id[:8],
            )

        except redis.ConnectionError as e:
            logger.warning(
                "Redis connection lost, attempting reconnect",
                error=str(e),
            )
            self._connected = False
            self._reconnect()
        except Exception as e:
            logger.warning(
                "Failed to export span to Redis",
                error=str(e),
                span_id=span.span_id,
            )

    def _write_spans_pipelined(self, spans: list[Span]) -> None:
        """Write multiple spans using Redis pipeline.

        Args:
            spans: List of spans to write.
        """
        if not self._connected or not self._client:
            logger.warning(
                "Redis not connected, dropping spans",
                count=len(spans),
            )
            return

        try:
            pipe = self._client.pipeline()

            for span in spans:
                trace_key = f"{self.key_prefix}:{span.trace_id}"
                span_data = json.dumps(span.to_dict(), default=str)
                score = span.start_time.timestamp()

                pipe.zadd(trace_key, {span_data: score})
                pipe.expire(trace_key, self.ttl_seconds)

                index_key = f"{self.key_prefix}:index"
                pipe.zadd(index_key, {span.trace_id: score})

            # Increment counter
            pipe.incrby(f"{self.key_prefix}:counter", len(spans))

            pipe.execute()

            logger.debug(
                "Spans exported to Redis",
                count=len(spans),
            )

        except redis.ConnectionError as e:
            logger.warning(
                "Redis connection lost during batch write",
                error=str(e),
            )
            self._connected = False
            self._reconnect()
        except Exception as e:
            logger.warning(
                "Failed to export spans to Redis",
                error=str(e),
                count=len(spans),
            )

    def _flush_buffer(self) -> None:
        """Flush buffered spans to Redis."""
        if not self._buffer:
            return

        spans_to_write = self._buffer[:]
        self._buffer.clear()
        self._write_spans_pipelined(spans_to_write)

    def _reconnect(self) -> None:
        """Attempt to reconnect to Redis."""
        try:
            self._connect_with_retry()
            logger.info("Redis span exporter reconnected")
        except Exception as e:
            logger.warning(
                "Redis span exporter reconnect failed",
                error=str(e),
            )

    def query_trace(self, trace_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Query all spans for a trace.

        Args:
            trace_id: The trace ID to query.
            limit: Maximum number of spans to return.

        Returns:
            List of span dictionaries ordered by timestamp.
        """
        if not self._connected or not self._client:
            return []

        try:
            trace_key = f"{self.key_prefix}:{trace_id}"
            # Get spans ordered by timestamp (score)
            span_data = self._client.zrange(trace_key, 0, limit - 1)

            spans = []
            for data in span_data:
                try:
                    spans.append(json.loads(data))
                except json.JSONDecodeError:
                    continue

            return spans

        except Exception as e:
            logger.warning(
                "Failed to query trace from Redis",
                error=str(e),
                trace_id=trace_id[:8],
            )
            return []

    def query_recent_traces(
        self,
        limit: int = 100,
        since_timestamp: float | None = None,
    ) -> list[str]:
        """Query recent trace IDs.

        Args:
            limit: Maximum number of trace IDs to return.
            since_timestamp: Only return traces after this timestamp.

        Returns:
            List of trace IDs ordered by most recent first.
        """
        if not self._connected or not self._client:
            return []

        try:
            index_key = f"{self.key_prefix}:index"

            if since_timestamp:
                # Get traces with score > since_timestamp
                trace_ids = self._client.zrangebyscore(
                    index_key,
                    since_timestamp,
                    "+inf",
                    start=0,
                    num=limit,
                )
            else:
                # Get most recent traces
                trace_ids = self._client.zrevrange(index_key, 0, limit - 1)

            return list(trace_ids)

        except Exception as e:
            logger.warning(
                "Failed to query recent traces from Redis",
                error=str(e),
            )
            return []

    def get_span_count(self) -> int:
        """Get total number of spans exported.

        Returns:
            Total span count or 0 if unavailable.
        """
        if not self._connected or not self._client:
            return 0

        try:
            count = self._client.get(f"{self.key_prefix}:counter")
            return int(count) if count else 0
        except Exception:
            return 0

    def delete_trace(self, trace_id: str) -> bool:
        """Delete all spans for a trace.

        Args:
            trace_id: The trace ID to delete.

        Returns:
            True if deleted successfully.
        """
        if not self._connected or not self._client:
            return False

        try:
            trace_key = f"{self.key_prefix}:{trace_id}"
            index_key = f"{self.key_prefix}:index"

            pipe = self._client.pipeline()
            pipe.delete(trace_key)
            pipe.zrem(index_key, trace_id)
            pipe.execute()

            logger.debug("Trace deleted from Redis", trace_id=trace_id[:8])
            return True

        except Exception as e:
            logger.warning(
                "Failed to delete trace from Redis",
                error=str(e),
                trace_id=trace_id[:8],
            )
            return False

    def flush(self) -> None:
        """Flush any buffered spans to Redis."""
        self._flush_buffer()

    def shutdown(self) -> None:
        """Shutdown the exporter, flushing remaining spans."""
        self.flush()
        if self._client:
            self._client.close()
            self._connected = False
        logger.debug("Redis span exporter shutdown")

    def is_connected(self) -> bool:
        """Check if connected to Redis.

        Returns:
            True if connected.
        """
        return self._connected

    def health_check(self) -> dict[str, Any]:
        """Get health status of the exporter.

        Returns:
            Health status dictionary.
        """
        status = {
            "connected": self._connected,
            "buffer_size": len(self._buffer),
            "redis_url": self._sanitize_url(self.redis_url),
        }

        if self._connected and self._client:
            try:
                self._client.ping()
                status["ping"] = "ok"
                status["span_count"] = self.get_span_count()
            except Exception as e:
                status["ping"] = "failed"
                status["error"] = str(e)

        return status

    def __repr__(self) -> str:
        return f"RedisSpanExporter({self._sanitize_url(self.redis_url)})"
