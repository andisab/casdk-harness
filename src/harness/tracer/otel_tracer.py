"""OpenTelemetry-based tracer implementation for CGF.

This module provides the main tracer class that implements span lifecycle
management, context propagation, and exporter coordination.

Example usage:
    from harness.tracer import OTelTracer, SpanKind

    tracer = OTelTracer(service_name="cgf")
    tracer.add_exporter(FileSpanExporter("/logs/spans.jsonl"))

    with tracer.span("agent.execute", SpanKind.AGENT_EXECUTION) as span:
        span.set_attribute("agent.name", "python-expert")
        result = await execute_task()
        span.set_attribute("result.length", len(result))
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from harness.tracer.base import (
    Span,
    SpanExporter,
    SpanKind,
    SpanStatus,
    generate_span_id,
    generate_trace_id,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Context variable for tracking current span in async contexts
_current_span: ContextVar[Span | None] = ContextVar("current_span", default=None)


@dataclass
class OTelTracer:
    """OpenTelemetry-style tracer for CGF span management.

    Handles span creation, context propagation, and exporter coordination.
    Thread-safe and async-safe via context variables.

    Attributes:
        service_name: Name of the service for span metadata.
        enabled: Whether tracing is active (can be disabled for performance).
        exporters: List of registered span exporters.
        buffer_size: Max spans to buffer before force-flushing (0 = no buffering).
    """

    service_name: str = "cgf"
    enabled: bool = True
    exporters: list[SpanExporter] = field(default_factory=list)
    buffer_size: int = 0

    # Internal state
    _buffer: list[Span] = field(default_factory=list, repr=False)
    _active_trace_id: str | None = field(default=None, repr=False)

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Span:
        """Start a new span.

        If no parent is provided, uses the current span from context.
        If no current span exists, starts a new trace.

        Args:
            name: Span name (e.g., "agent.python-expert.execute").
            kind: Category of span operation.
            attributes: Initial span attributes.
            parent: Explicit parent span (overrides context).

        Returns:
            New span instance (not yet finished).
        """
        if not self.enabled:
            # Return a minimal span for disabled tracing
            return Span(
                trace_id="disabled",
                span_id="disabled",
                name=name,
                kind=kind,
            )

        # Determine parent from explicit arg or context
        parent_span = parent or _current_span.get()

        # Generate IDs
        if parent_span:
            trace_id = parent_span.trace_id
            parent_span_id = parent_span.span_id
        else:
            trace_id = self._active_trace_id or generate_trace_id()
            parent_span_id = None

        span = Span(
            trace_id=trace_id,
            span_id=generate_span_id(),
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )

        logger.debug(
            "Span started",
            span_id=span.span_id,
            trace_id=span.trace_id,
            name=name,
            kind=kind.value,
        )

        return span

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Context manager for automatic span lifecycle.

        Handles:
        - Span creation with context propagation
        - Setting span as current in context
        - Exception recording
        - Automatic finish and export

        Args:
            name: Span name.
            kind: Span kind category.
            attributes: Initial attributes.

        Yields:
            The active span for adding attributes/events.

        Example:
            with tracer.span("tool.call", SpanKind.TOOL_CALL) as span:
                span.set_attribute("tool.name", "Read")
                result = await read_file(path)
                span.set_attribute("file.size", len(result))
        """
        span = self.start_span(name, kind, attributes)

        # Save previous span and set current
        token = _current_span.set(span)

        try:
            yield span
            span.finish(SpanStatus.OK)
        except Exception as e:
            span.record_exception(e)
            span.finish(SpanStatus.ERROR, str(e))
            raise
        finally:
            # Restore previous span
            _current_span.reset(token)
            # Export the completed span
            self._export_span(span)

    def current_span(self) -> Span | None:
        """Get the current active span from context.

        Returns:
            Current span or None if no span is active.
        """
        return _current_span.get()

    def start_trace(self, trace_id: str | None = None) -> str:
        """Start a new trace (root span context).

        Sets the active trace ID for subsequent spans without explicit parents.

        Args:
            trace_id: Explicit trace ID or None to generate.

        Returns:
            The trace ID being used.
        """
        self._active_trace_id = trace_id or generate_trace_id()
        logger.debug("Trace started", trace_id=self._active_trace_id)
        return self._active_trace_id

    def end_trace(self) -> None:
        """End the current trace context."""
        if self._active_trace_id:
            logger.debug("Trace ended", trace_id=self._active_trace_id)
            self._active_trace_id = None

    def add_exporter(self, exporter: SpanExporter) -> None:
        """Register an exporter to receive completed spans.

        Args:
            exporter: Exporter instance to add.
        """
        self.exporters.append(exporter)
        logger.debug(
            "Exporter added",
            exporter_type=type(exporter).__name__,
            total_exporters=len(self.exporters),
        )

    def remove_exporter(self, exporter: SpanExporter) -> None:
        """Remove a registered exporter.

        Args:
            exporter: Exporter to remove.
        """
        if exporter in self.exporters:
            self.exporters.remove(exporter)
            logger.debug("Exporter removed", exporter_type=type(exporter).__name__)

    def _export_span(self, span: Span) -> None:
        """Export a completed span to all registered exporters.

        Handles buffering if configured.

        Args:
            span: Completed span to export.
        """
        if not self.enabled or span.trace_id == "disabled":
            return

        if self.buffer_size > 0:
            self._buffer.append(span)
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
        else:
            self._export_immediately(span)

    def _export_immediately(self, span: Span) -> None:
        """Export a span to all exporters immediately.

        Args:
            span: Span to export.
        """
        for exporter in self.exporters:
            try:
                exporter.export(span)
            except Exception as e:
                logger.warning(
                    "Exporter failed",
                    exporter_type=type(exporter).__name__,
                    error=str(e),
                    span_id=span.span_id,
                )

    def _flush_buffer(self) -> None:
        """Flush buffered spans to all exporters."""
        if not self._buffer:
            return

        spans_to_export = self._buffer[:]
        self._buffer.clear()

        for exporter in self.exporters:
            try:
                exporter.export_batch(spans_to_export)
            except Exception as e:
                logger.warning(
                    "Batch export failed",
                    exporter_type=type(exporter).__name__,
                    error=str(e),
                    span_count=len(spans_to_export),
                )

    def flush(self) -> None:
        """Flush any buffered spans and all exporters."""
        self._flush_buffer()
        for exporter in self.exporters:
            try:
                exporter.flush()
            except Exception as e:
                logger.warning(
                    "Exporter flush failed",
                    exporter_type=type(exporter).__name__,
                    error=str(e),
                )

    def shutdown(self) -> None:
        """Shutdown the tracer and all exporters.

        Flushes remaining spans and releases resources.
        """
        logger.debug("Tracer shutting down", service=self.service_name)
        self.flush()

        for exporter in self.exporters:
            try:
                exporter.shutdown()
            except Exception as e:
                logger.warning(
                    "Exporter shutdown failed",
                    exporter_type=type(exporter).__name__,
                    error=str(e),
                )

        self.exporters.clear()
        self.enabled = False

    def __enter__(self) -> OTelTracer:
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit - ensures shutdown."""
        self.shutdown()


class AsyncSpanContextManager:
    """Async context manager wrapper for spans.

    Provides the same functionality as the sync span() method
    but works with async/await.

    Example:
        async with tracer.async_span("agent.execute") as span:
            span.set_attribute("agent.name", "test")
            await do_work()
    """

    def __init__(
        self,
        tracer: OTelTracer,
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
    ):
        self.tracer = tracer
        self.name = name
        self.kind = kind
        self.attributes = attributes
        self.span: Span | None = None
        self._token: object | None = None

    async def __aenter__(self) -> Span:
        self.span = self.tracer.start_span(self.name, self.kind, self.attributes)
        self._token = _current_span.set(self.span)
        return self.span

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self.span is None:
            return

        if exc_val is not None:
            self.span.record_exception(exc_val)
            self.span.finish(SpanStatus.ERROR, str(exc_val))
        else:
            self.span.finish(SpanStatus.OK)

        if self._token is not None:
            _current_span.reset(self._token)

        # Export asynchronously if in async context
        if asyncio.iscoroutinefunction(getattr(self.tracer.exporters[0], "export", None)):
            for exporter in self.tracer.exporters:
                try:
                    await exporter.export(self.span)  # type: ignore[misc]
                except Exception as e:
                    logger.warning(
                        "Async exporter failed",
                        exporter_type=type(exporter).__name__,
                        error=str(e),
                    )
        else:
            self.tracer._export_span(self.span)


def extend_tracer_with_async(tracer: OTelTracer) -> None:
    """Add async_span method to a tracer instance.

    This is called automatically when creating a tracer via get_tracer().

    Args:
        tracer: Tracer instance to extend.
    """

    def async_span(
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncSpanContextManager:
        """Async context manager for span lifecycle.

        Args:
            name: Span name.
            kind: Span kind.
            attributes: Initial attributes.

        Returns:
            Async context manager that yields a Span.
        """
        return AsyncSpanContextManager(tracer, name, kind, attributes)

    tracer.async_span = async_span  # type: ignore[attr-defined]
