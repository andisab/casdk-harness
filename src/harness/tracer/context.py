"""Trace context propagation for distributed tracing.

This module provides utilities for propagating trace context across
process boundaries, containers, and async contexts. Follows W3C Trace
Context specification patterns.

Example usage:
    # Serialize context for cross-process propagation
    context = TraceContext.from_span(current_span)
    headers = context.to_headers()

    # Restore context in another process
    context = TraceContext.from_headers(headers)
    span = tracer.start_span("child", parent=context.to_span())
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.tracer.base import Span


# W3C Trace Context header names
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"

# CGF-specific context header
CGF_CONTEXT_HEADER = "x-cgf-context"


@dataclass
class TraceContext:
    """Immutable trace context for propagation.

    Captures the essential trace information needed to continue a trace
    across process boundaries.

    Attributes:
        trace_id: The trace ID (32 hex chars).
        span_id: The parent span ID (16 hex chars).
        trace_flags: W3C trace flags (00 = not sampled, 01 = sampled).
        trace_state: Optional vendor-specific key-value pairs.
        agent_name: CGF-specific: the originating agent name.
        resource_id: CGF-specific: the resource being traced.
        resource_type: CGF-specific: type of resource.
    """

    trace_id: str
    span_id: str
    trace_flags: str = "01"  # Default: sampled
    trace_state: dict[str, str] | None = None

    # CGF-specific context
    agent_name: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None

    @classmethod
    def from_span(cls, span: Span) -> TraceContext:
        """Extract trace context from a span.

        Args:
            span: The span to extract context from.

        Returns:
            TraceContext for propagation.
        """
        return cls(
            trace_id=span.trace_id,
            span_id=span.span_id,
            trace_flags="01",
            agent_name=span.agent_name or None,
            resource_id=span.resource_id,
            resource_type=span.resource_type,
        )

    def to_traceparent(self) -> str:
        """Format as W3C traceparent header value.

        Format: {version}-{trace_id}-{span_id}-{trace_flags}

        Returns:
            Traceparent header string.
        """
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def from_traceparent(cls, traceparent: str) -> TraceContext | None:
        """Parse W3C traceparent header.

        Args:
            traceparent: Header value like "00-{trace_id}-{span_id}-{flags}".

        Returns:
            TraceContext or None if invalid.
        """
        try:
            parts = traceparent.split("-")
            if len(parts) != 4:
                return None
            version, trace_id, span_id, trace_flags = parts
            if version != "00":
                return None
            if len(trace_id) != 32 or len(span_id) != 16:
                return None
            return cls(
                trace_id=trace_id,
                span_id=span_id,
                trace_flags=trace_flags,
            )
        except Exception:
            return None

    def to_headers(self) -> dict[str, str]:
        """Export context as HTTP headers.

        Returns:
            Dictionary of header name -> value.
        """
        headers = {
            TRACEPARENT_HEADER: self.to_traceparent(),
        }

        # Add CGF-specific context
        cgf_context = {}
        if self.agent_name:
            cgf_context["agent_name"] = self.agent_name
        if self.resource_id:
            cgf_context["resource_id"] = self.resource_id
        if self.resource_type:
            cgf_context["resource_type"] = self.resource_type

        if cgf_context:
            headers[CGF_CONTEXT_HEADER] = json.dumps(cgf_context)

        if self.trace_state:
            # Format: key1=value1,key2=value2
            state_str = ",".join(f"{k}={v}" for k, v in self.trace_state.items())
            headers[TRACESTATE_HEADER] = state_str

        return headers

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> TraceContext | None:
        """Parse context from HTTP headers.

        Args:
            headers: HTTP headers dictionary.

        Returns:
            TraceContext or None if traceparent not found.
        """
        traceparent = headers.get(TRACEPARENT_HEADER) or headers.get(
            TRACEPARENT_HEADER.title()
        )
        if not traceparent:
            return None

        context = cls.from_traceparent(traceparent)
        if not context:
            return None

        # Parse tracestate if present
        tracestate = headers.get(TRACESTATE_HEADER) or headers.get(
            TRACESTATE_HEADER.title()
        )
        if tracestate:
            with contextlib.suppress(ValueError):
                context.trace_state = dict(
                    pair.split("=", 1) for pair in tracestate.split(",")
                )

        # Parse CGF context if present
        cgf_header = headers.get(CGF_CONTEXT_HEADER) or headers.get(
            CGF_CONTEXT_HEADER.title()
        )
        if cgf_header:
            try:
                cgf_data = json.loads(cgf_header)
                context.agent_name = cgf_data.get("agent_name")
                context.resource_id = cgf_data.get("resource_id")
                context.resource_type = cgf_data.get("resource_type")
            except json.JSONDecodeError:
                pass

        return context

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "trace_flags": self.trace_flags,
            "trace_state": self.trace_state,
            "agent_name": self.agent_name,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceContext:
        """Deserialize context from dictionary.

        Args:
            data: Dictionary from to_dict().

        Returns:
            TraceContext instance.
        """
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            trace_flags=data.get("trace_flags", "01"),
            trace_state=data.get("trace_state"),
            agent_name=data.get("agent_name"),
            resource_id=data.get("resource_id"),
            resource_type=data.get("resource_type"),
        )

    def __repr__(self) -> str:
        return f"TraceContext(trace={self.trace_id[:8]}..., span={self.span_id})"


def inject_context(span: Span, carrier: dict[str, str]) -> None:
    """Inject trace context into a carrier dictionary.

    Useful for adding trace context to outgoing requests.

    Args:
        span: The current span to propagate.
        carrier: Dictionary to inject headers into.
    """
    context = TraceContext.from_span(span)
    carrier.update(context.to_headers())


def extract_context(carrier: dict[str, str]) -> TraceContext | None:
    """Extract trace context from a carrier dictionary.

    Useful for extracting context from incoming requests.

    Args:
        carrier: Dictionary containing headers.

    Returns:
        TraceContext or None if not found.
    """
    return TraceContext.from_headers(carrier)


class ContextManager:
    """Manages trace context for a session.

    Provides a higher-level API for managing context across
    multiple operations in a session.
    """

    def __init__(self) -> None:
        self._stack: list[TraceContext] = []

    def push(self, context: TraceContext) -> None:
        """Push a context onto the stack.

        Args:
            context: Context to push.
        """
        self._stack.append(context)

    def pop(self) -> TraceContext | None:
        """Pop the most recent context from the stack.

        Returns:
            The popped context or None if empty.
        """
        return self._stack.pop() if self._stack else None

    def current(self) -> TraceContext | None:
        """Get the current context without removing it.

        Returns:
            Current context or None if stack is empty.
        """
        return self._stack[-1] if self._stack else None

    def clear(self) -> None:
        """Clear all contexts from the stack."""
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)
