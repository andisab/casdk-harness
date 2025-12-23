"""StoreSpanExporter - Export spans to the OptimizationStore.

This exporter bridges the tracing and optimization infrastructure by sending
spans directly to the OptimizationStore for persistence and later analysis.

Usage:
    from harness.tracer.exporters import StoreSpanExporter
    from harness.tracer import get_tracer

    exporter = StoreSpanExporter()
    tracer = get_tracer(auto_configure=False)
    tracer.add_exporter(exporter)

    # Spans will now be stored in the optimization store
    with tracer.span("agent.execute") as span:
        span.set_attribute("agent.name", "test")
        do_work()

This exporter is automatically configured when:
    - cgf_enabled = True
    - cgf_exporter = "memory" (default for testing)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from harness.optimization.store import OptimizationStore
    from harness.tracer.base import Span

logger = structlog.get_logger(__name__)


class StoreSpanExporter:
    """Export spans to the OptimizationStore.

    This exporter sends spans to the optimization store for:
    - Persistence (memory or Redis backend)
    - Later transformation via adapters
    - Reward computation and optimization
    """

    def __init__(
        self,
        store: OptimizationStore | None = None,
        buffer_size: int = 0,
    ) -> None:
        """Initialize the store exporter.

        Args:
            store: OptimizationStore instance. If None, uses get_store().
            buffer_size: Number of spans to buffer before flushing.
                0 (default) means immediate writes.
        """
        self._store = store
        self._buffer_size = buffer_size
        self._buffer: list[Span] = []
        self._lock = threading.Lock()
        self._closed = False

    def _get_store(self) -> OptimizationStore:
        """Lazily get the store instance.

        Returns:
            The configured OptimizationStore.
        """
        if self._store is None:
            from harness.optimization.store import get_store

            self._store = get_store()
        return self._store

    def export(self, span: Span) -> None:
        """Export a single span.

        Args:
            span: The span to export.
        """
        if self._closed:
            logger.warning("Exporter closed, dropping span", span_id=span.span_id)
            return

        if self._buffer_size > 0:
            with self._lock:
                self._buffer.append(span)
                if len(self._buffer) >= self._buffer_size:
                    self._flush_buffer()
        else:
            # Immediate write
            try:
                store = self._get_store()
                store.store_span(span)
                logger.debug(
                    "Span exported to store",
                    span_id=span.span_id[:8],
                    trace_id=span.trace_id[:8],
                )
            except Exception as e:
                logger.error(
                    "Failed to export span to store",
                    span_id=span.span_id,
                    error=str(e),
                )

    def export_batch(self, spans: list[Span]) -> None:
        """Export multiple spans in a batch.

        Args:
            spans: List of spans to export.
        """
        if self._closed:
            logger.warning("Exporter closed, dropping spans", count=len(spans))
            return

        if not spans:
            return

        if self._buffer_size > 0:
            with self._lock:
                self._buffer.extend(spans)
                if len(self._buffer) >= self._buffer_size:
                    self._flush_buffer()
        else:
            # Immediate write
            try:
                store = self._get_store()
                store.store_spans(spans)
                logger.debug("Spans exported to store", count=len(spans))
            except Exception as e:
                logger.error(
                    "Failed to export spans to store",
                    count=len(spans),
                    error=str(e),
                )

    def _flush_buffer(self) -> None:
        """Flush buffered spans to the store.

        Must be called with self._lock held.
        """
        if not self._buffer:
            return

        spans_to_flush = self._buffer.copy()
        self._buffer.clear()

        try:
            store = self._get_store()
            store.store_spans(spans_to_flush)
            logger.debug("Buffer flushed to store", count=len(spans_to_flush))
        except Exception as e:
            logger.error(
                "Failed to flush buffer to store",
                count=len(spans_to_flush),
                error=str(e),
            )

    def flush(self) -> None:
        """Flush any buffered spans to the store."""
        with self._lock:
            self._flush_buffer()

    def shutdown(self) -> None:
        """Clean up exporter resources.

        Flushes any remaining buffered spans before closing.
        """
        if self._closed:
            return

        # Flush any remaining spans
        self.flush()
        self._closed = True

        logger.debug("StoreSpanExporter shutdown complete")

    @property
    def is_closed(self) -> bool:
        """Check if the exporter is closed."""
        return self._closed
