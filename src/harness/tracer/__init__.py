"""CGF Tracing Module - OpenTelemetry-style span-based tracing.

This module provides comprehensive tracing infrastructure for the CGF
(ContextGrad Framework), enabling execution visibility across agent
operations, tool calls, and LLM requests.

Example usage:
    from harness.tracer import get_tracer, SpanKind

    # Get or create a tracer instance
    tracer = get_tracer()

    # Create spans for operations
    with tracer.span("agent.execute", SpanKind.AGENT_EXECUTION) as span:
        span.set_attribute("agent.name", "python-expert")
        result = await execute_task()
        span.set_attribute("result.length", len(result))

    # Use decorators for automatic instrumentation
    from harness.tracer import traced

    @traced("tool.call", SpanKind.TOOL_CALL)
    async def call_tool(name: str, args: dict) -> dict:
        return await execute_tool(name, args)

Public API:
    - get_tracer(): Get or create global tracer instance
    - Span: Span data structure
    - SpanKind: Span category enumeration
    - SpanStatus: Span completion status
    - SpanExporter: Protocol for custom exporters
    - TracerProtocol: Protocol for custom tracers
    - TraceContext: Context propagation across boundaries
    - traced: Decorator for automatic function tracing
    - trace_method: Decorator for class method tracing
    - record_tokens: Helper for recording token usage
    - FileSpanExporter: JSON Lines file exporter
    - RedisSpanExporter: Redis-based exporter
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.tracer.base import (
    Span,
    SpanExporter,
    SpanKind,
    SpanStatus,
    TracerProtocol,
    generate_span_id,
    generate_trace_id,
)
from harness.tracer.context import (
    CGF_CONTEXT_HEADER,
    TRACEPARENT_HEADER,
    TRACESTATE_HEADER,
    ContextManager,
    TraceContext,
    extract_context,
    inject_context,
)
from harness.tracer.exporters import FileSpanExporter, RedisSpanExporter, StoreSpanExporter
from harness.tracer.instrumentation import (
    TracedClass,
    get_global_tracer,
    record_tokens,
    set_global_tracer,
    trace_method,
    traced,
)
from harness.tracer.otel_tracer import (
    AsyncSpanContextManager,
    OTelTracer,
    extend_tracer_with_async,
)

if TYPE_CHECKING:
    pass

__all__ = [
    # Core types
    "Span",
    "SpanKind",
    "SpanStatus",
    "SpanExporter",
    "TracerProtocol",
    # Tracer implementation
    "OTelTracer",
    "AsyncSpanContextManager",
    # Context propagation
    "TraceContext",
    "ContextManager",
    "inject_context",
    "extract_context",
    "TRACEPARENT_HEADER",
    "TRACESTATE_HEADER",
    "CGF_CONTEXT_HEADER",
    # Instrumentation
    "traced",
    "trace_method",
    "TracedClass",
    "record_tokens",
    # Exporters
    "FileSpanExporter",
    "RedisSpanExporter",
    "StoreSpanExporter",
    # Factory function
    "get_tracer",
    # Utilities
    "generate_trace_id",
    "generate_span_id",
    "get_global_tracer",
    "set_global_tracer",
]

# Module-level singleton tracer
_tracer: OTelTracer | None = None


def get_tracer(
    service_name: str = "cgf",
    enabled: bool | None = None,
    auto_configure: bool = True,
) -> OTelTracer:
    """Get or create the global tracer instance.

    This is the primary entry point for obtaining a tracer. It returns
    a singleton instance, creating one if it doesn't exist.

    Args:
        service_name: Name of the service for span metadata.
        enabled: Whether tracing is enabled. If None, reads from config.
        auto_configure: If True, automatically configure exporters from config.

    Returns:
        The global OTelTracer instance.

    Example:
        tracer = get_tracer()
        with tracer.span("my.operation") as span:
            span.set_attribute("key", "value")
            do_work()
    """
    global _tracer

    if _tracer is not None:
        return _tracer

    # Determine if tracing is enabled
    if enabled is None:
        try:
            from harness.config import get_config

            config = get_config()
            enabled = getattr(config, "cgf_tracing_enabled", True)
        except Exception:
            enabled = True

    # Create tracer
    _tracer = OTelTracer(
        service_name=service_name,
        enabled=enabled,
    )

    # Add async span support
    extend_tracer_with_async(_tracer)

    # Set as global tracer for instrumentation decorators
    set_global_tracer(_tracer)

    # Auto-configure exporters if requested
    if auto_configure and enabled:
        _auto_configure_exporters(_tracer)

    return _tracer


def _auto_configure_exporters(tracer: OTelTracer) -> None:
    """Configure exporters based on config settings.

    Args:
        tracer: Tracer to configure exporters for.
    """
    try:
        from harness.config import get_config

        config = get_config()

        # Use new field name with fallback to old name for compatibility
        exporter_type = getattr(
            config, "cgf_exporter", getattr(config, "cgf_tracing_exporter", "memory")
        )
        retention_days = getattr(config, "cgf_span_retention_days", 7)

        if exporter_type in ("file", "both"):
            # Configure file exporter using config path or default
            file_export_path = getattr(config, "cgf_file_export_path", None)
            if file_export_path is None:
                import os
                from pathlib import Path

                file_export_path = Path(os.environ.get("LOG_DIR", "/logs")) / "spans"

            span_file = file_export_path / "spans.jsonl"
            file_exporter = FileSpanExporter(
                file_path=span_file,
                max_file_size_mb=10.0,
                max_files=5,
            )
            tracer.add_exporter(file_exporter)

        if exporter_type in ("redis", "both"):
            # Configure Redis exporter
            redis_url = getattr(config, "redis_url", None)
            if redis_url:
                redis_exporter = RedisSpanExporter(
                    redis_url=redis_url,
                    ttl_seconds=retention_days * 24 * 3600,
                )
                tracer.add_exporter(redis_exporter)

        if exporter_type == "memory":
            # Configure store exporter for memory backend
            # This exports spans directly to the optimization store
            try:
                from harness.tracer.exporters import StoreSpanExporter

                store_exporter = StoreSpanExporter()
                tracer.add_exporter(store_exporter)
            except ImportError:
                # StoreSpanExporter not yet implemented - will be added in Phase 0.6
                pass

    except Exception as e:
        import structlog

        logger = structlog.get_logger(__name__)
        logger.warning(
            "Failed to auto-configure tracer exporters",
            error=str(e),
        )


def reset_tracer() -> None:
    """Reset the global tracer (primarily for testing).

    This shuts down the existing tracer and clears the singleton,
    allowing get_tracer() to create a fresh instance.
    """
    global _tracer

    if _tracer is not None:
        _tracer.shutdown()
        _tracer = None
        set_global_tracer(None)  # type: ignore[arg-type]
