"""Base types and protocols for CGF tracing infrastructure.

This module defines the core data structures and protocols for span-based
execution tracing, following OpenTelemetry conventions.

Example usage:
    from harness.tracer import Span, SpanKind, SpanStatus

    span = Span(
        trace_id="abc123",
        span_id="def456",
        name="agent.execute",
        kind=SpanKind.AGENT_EXECUTION,
    )
    span.set_attribute("agent.name", "python-expert")
    span.finish()
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterator, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


class SpanKind(Enum):
    """Categories of spans for different execution contexts.

    These align with OpenTelemetry span kinds but are specific to CGF use cases.
    """

    AGENT_EXECUTION = "agent_execution"
    """Top-level agent task execution."""

    TOOL_CALL = "tool_call"
    """Individual tool invocation within an agent turn."""

    SUBAGENT_INVOCATION = "subagent_invocation"
    """Delegation to a subagent via Task tool or subagent."""

    LLM_REQUEST = "llm_request"
    """Raw LLM API request to Claude."""

    RESOURCE_EVALUATION = "resource_evaluation"
    """CGF resource (agent, skill, prompt) evaluation run."""


class SpanStatus(Enum):
    """Status of a completed span."""

    OK = "ok"
    """Span completed successfully."""

    ERROR = "error"
    """Span failed with an error."""

    TIMEOUT = "timeout"
    """Span exceeded time limit."""


def generate_trace_id() -> str:
    """Generate a unique trace ID (32 hex characters)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a unique span ID (16 hex characters)."""
    return uuid.uuid4().hex[:16]


@dataclass
class Span:
    """OpenTelemetry-compatible execution span.

    Spans capture discrete execution units (tool calls, agent turns, etc.)
    with timing, attributes, and nested structure for optimization attribution.

    Attributes:
        trace_id: Unique ID for the entire trace (shared by all spans in a trace).
        span_id: Unique ID for this specific span.
        parent_span_id: Parent span ID for nested spans (None for root spans).
        name: Human-readable span name (e.g., "agent.python-expert.execute").
        kind: Category of span (AGENT_EXECUTION, TOOL_CALL, etc.).
        start_time: When the span started (UTC).
        end_time: When the span ended (UTC), None if still active.
        attributes: Flexible key-value data for span context.
        status: Completion status (OK, ERROR, TIMEOUT).
        error_message: Error description if status is ERROR.
        duration_ms: Computed duration in milliseconds.
        token_usage: Token counts for LLM spans (input, output, cached).
        agent_name: Name of the agent that created this span.
        resource_id: ID of the CGF resource being evaluated (if applicable).
        resource_type: Type of CGF resource (agent, skill, prompt, command).
        events: List of timestamped events that occurred during the span.
    """

    trace_id: str
    span_id: str
    name: str
    kind: SpanKind
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional fields with defaults
    parent_span_id: str | None = None
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: SpanStatus = SpanStatus.OK
    error_message: str | None = None
    duration_ms: float | None = None
    token_usage: dict[str, int] | None = None

    # CGF-specific context
    agent_name: str = ""
    resource_id: str | None = None
    resource_type: str | None = None

    # Events within the span
    events: list[dict[str, Any]] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute.

        Args:
            key: Attribute name (e.g., "tool.name", "prompt.length").
            value: Attribute value (should be JSON-serializable).
        """
        self.attributes[key] = value

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        """Set multiple span attributes at once.

        Args:
            attributes: Mapping of attribute names to values.
        """
        self.attributes.update(attributes)

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Add an event to the span.

        Events are timestamped occurrences during the span's lifetime,
        such as "retry_attempted" or "cache_hit".

        Args:
            name: Event name.
            attributes: Optional event-specific attributes.
            timestamp: Event time (defaults to now).
        """
        self.events.append({
            "name": name,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "attributes": attributes or {},
        })

    def finish(
        self,
        status: SpanStatus = SpanStatus.OK,
        error_message: str | None = None,
    ) -> None:
        """Mark the span as finished.

        Computes duration and sets final status.

        Args:
            status: Final span status.
            error_message: Error description if status is ERROR.
        """
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        if error_message:
            self.error_message = error_message

    def record_exception(self, exception: BaseException) -> None:
        """Record an exception that occurred during the span.

        Adds an event with exception details and sets ERROR status.

        Args:
            exception: The exception that occurred.
        """
        self.add_event(
            "exception",
            attributes={
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
            },
        )
        self.status = SpanStatus.ERROR
        self.error_message = str(exception)

    def to_dict(self) -> dict[str, Any]:
        """Serialize span to dictionary for storage/export.

        Returns:
            Dictionary representation compatible with JSON serialization.
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attributes": self.attributes,
            "status": self.status.value,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
            "agent_name": self.agent_name,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Span:
        """Deserialize span from dictionary.

        Args:
            data: Dictionary from to_dict() or JSON.

        Returns:
            Reconstructed Span instance.
        """
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            name=data["name"],
            kind=SpanKind(data["kind"]),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=(
                datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None
            ),
            attributes=data.get("attributes", {}),
            status=SpanStatus(data.get("status", "ok")),
            error_message=data.get("error_message"),
            duration_ms=data.get("duration_ms"),
            token_usage=data.get("token_usage"),
            agent_name=data.get("agent_name", ""),
            resource_id=data.get("resource_id"),
            resource_type=data.get("resource_type"),
            events=data.get("events", []),
        )

    def __repr__(self) -> str:
        status_str = self.status.value
        duration_str = f"{self.duration_ms:.1f}ms" if self.duration_ms else "active"
        return f"Span({self.name!r}, kind={self.kind.name}, status={status_str}, {duration_str})"


class SpanExporter(Protocol):
    """Protocol for span exporters.

    Exporters receive spans and persist them to a storage backend
    (Redis, file, OTLP collector, etc.).
    """

    def export(self, span: Span) -> None:
        """Export a single span.

        Args:
            span: The span to export.
        """
        ...

    def export_batch(self, spans: list[Span]) -> None:
        """Export multiple spans in a batch.

        Args:
            spans: List of spans to export.
        """
        ...

    def flush(self) -> None:
        """Flush any buffered spans to the backend."""
        ...

    def shutdown(self) -> None:
        """Clean up exporter resources."""
        ...


class TracerProtocol(Protocol):
    """Protocol for tracer implementations.

    Tracers create and manage spans, propagate context, and coordinate
    with exporters for persistence.
    """

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Span:
        """Start a new span.

        Args:
            name: Span name.
            kind: Span kind category.
            attributes: Initial attributes.
            parent: Parent span for nesting.

        Returns:
            New active span.
        """
        ...

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT_EXECUTION,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Context manager for automatic span lifecycle.

        Automatically finishes the span and exports it when the context exits.
        Records exceptions if they occur.

        Args:
            name: Span name.
            kind: Span kind category.
            attributes: Initial attributes.

        Yields:
            The active span.
        """
        ...

    def current_span(self) -> Span | None:
        """Get the current active span.

        Returns:
            Current span or None if no span is active.
        """
        ...

    def add_exporter(self, exporter: SpanExporter) -> None:
        """Register an exporter to receive spans.

        Args:
            exporter: Exporter to add.
        """
        ...

    def flush(self) -> None:
        """Flush all exporters."""
        ...

    def shutdown(self) -> None:
        """Shutdown the tracer and all exporters."""
        ...
