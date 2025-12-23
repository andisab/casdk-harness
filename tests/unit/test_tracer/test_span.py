"""Unit tests for Span and related base types."""

from datetime import datetime, timezone

import pytest

from harness.tracer.base import (
    Span,
    SpanExporter,
    SpanKind,
    SpanStatus,
    generate_span_id,
    generate_trace_id,
)


class TestSpanKind:
    """Tests for SpanKind enumeration."""

    def test_all_kinds_defined(self) -> None:
        """Verify all expected span kinds exist."""
        assert SpanKind.AGENT_EXECUTION.value == "agent_execution"
        assert SpanKind.TOOL_CALL.value == "tool_call"
        assert SpanKind.SUBAGENT_INVOCATION.value == "subagent_invocation"
        assert SpanKind.LLM_REQUEST.value == "llm_request"
        assert SpanKind.RESOURCE_EVALUATION.value == "resource_evaluation"

    def test_kind_count(self) -> None:
        """Verify we have the expected number of span kinds."""
        assert len(SpanKind) == 5


class TestSpanStatus:
    """Tests for SpanStatus enumeration."""

    def test_all_statuses_defined(self) -> None:
        """Verify all expected statuses exist."""
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"
        assert SpanStatus.TIMEOUT.value == "timeout"

    def test_status_count(self) -> None:
        """Verify we have the expected number of statuses."""
        assert len(SpanStatus) == 3


class TestIdGeneration:
    """Tests for trace/span ID generation."""

    def test_trace_id_format(self) -> None:
        """Trace ID should be 32 hex characters."""
        trace_id = generate_trace_id()
        assert len(trace_id) == 32
        assert all(c in "0123456789abcdef" for c in trace_id)

    def test_trace_id_uniqueness(self) -> None:
        """Multiple trace IDs should be unique."""
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100

    def test_span_id_format(self) -> None:
        """Span ID should be 16 hex characters."""
        span_id = generate_span_id()
        assert len(span_id) == 16
        assert all(c in "0123456789abcdef" for c in span_id)

    def test_span_id_uniqueness(self) -> None:
        """Multiple span IDs should be unique."""
        ids = {generate_span_id() for _ in range(100)}
        assert len(ids) == 100


class TestSpan:
    """Tests for Span dataclass."""

    def test_span_creation(self) -> None:
        """Test basic span creation."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test.operation",
            kind=SpanKind.AGENT_EXECUTION,
        )

        assert span.trace_id == "a" * 32
        assert span.span_id == "b" * 16
        assert span.name == "test.operation"
        assert span.kind == SpanKind.AGENT_EXECUTION
        assert span.status == SpanStatus.OK  # Default status
        assert span.parent_span_id is None
        assert span.attributes == {}

    def test_span_with_parent(self) -> None:
        """Test span with parent span ID."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id="c" * 16,
            name="child.operation",
            kind=SpanKind.TOOL_CALL,
        )

        assert span.parent_span_id == "c" * 16

    def test_set_attribute(self) -> None:
        """Test setting span attributes."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        span.set_attribute("key", "value")
        span.set_attribute("number", 42)
        span.set_attribute("nested.key", {"a": 1})

        assert span.attributes["key"] == "value"
        assert span.attributes["number"] == 42
        assert span.attributes["nested.key"] == {"a": 1}

    def test_add_event(self) -> None:
        """Test adding events to span."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        span.add_event("event.start", {"detail": "starting"})
        span.add_event("event.end")

        assert len(span.events) == 2
        assert span.events[0]["name"] == "event.start"
        assert span.events[0]["attributes"] == {"detail": "starting"}
        assert span.events[1]["name"] == "event.end"

    def test_record_exception(self) -> None:
        """Test recording exceptions."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        try:
            raise ValueError("test error")
        except ValueError as e:
            span.record_exception(e)

        assert span.error_message == "test error"
        assert span.status == SpanStatus.ERROR
        assert len(span.events) == 1
        assert span.events[0]["name"] == "exception"
        assert span.events[0]["attributes"]["exception.type"] == "ValueError"
        assert span.events[0]["attributes"]["exception.message"] == "test error"

    def test_finish_ok(self) -> None:
        """Test finishing span with OK status."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        span.finish(SpanStatus.OK)

        assert span.status == SpanStatus.OK
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_finish_error(self) -> None:
        """Test finishing span with error."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        span.finish(SpanStatus.ERROR, "something went wrong")

        assert span.status == SpanStatus.ERROR
        assert span.error_message == "something went wrong"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test.operation",
            kind=SpanKind.TOOL_CALL,
            attributes={"key": "value"},
        )
        span.agent_name = "test-agent"
        span.finish(SpanStatus.OK)

        data = span.to_dict()

        assert data["trace_id"] == "a" * 32
        assert data["span_id"] == "b" * 16
        assert data["name"] == "test.operation"
        assert data["kind"] == "tool_call"
        assert data["status"] == "ok"
        assert data["attributes"]["key"] == "value"
        assert data["agent_name"] == "test-agent"
        assert "start_time" in data
        assert "end_time" in data
        assert "duration_ms" in data

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "trace_id": "a" * 32,
            "span_id": "b" * 16,
            "parent_span_id": "c" * 16,
            "name": "test.operation",
            "kind": "agent_execution",
            "status": "ok",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "duration_ms": 100.5,
            "attributes": {"key": "value"},
            "events": [],
            "token_usage": {"input": 100, "output": 50},
            "agent_name": "test-agent",
        }

        span = Span.from_dict(data)

        assert span.trace_id == "a" * 32
        assert span.span_id == "b" * 16
        assert span.parent_span_id == "c" * 16
        assert span.name == "test.operation"
        assert span.kind == SpanKind.AGENT_EXECUTION
        assert span.status == SpanStatus.OK
        assert span.attributes["key"] == "value"
        assert span.token_usage["input"] == 100
        assert span.agent_name == "test-agent"

    def test_round_trip_serialization(self) -> None:
        """Test that to_dict/from_dict round-trips correctly."""
        original = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id="c" * 16,
            name="test.operation",
            kind=SpanKind.SUBAGENT_INVOCATION,
            attributes={"nested": {"value": 123}},
        )
        original.agent_name = "my-agent"
        original.resource_id = "res-123"
        original.token_usage = {"input": 100, "output": 50, "total": 150}
        original.add_event("test.event", {"detail": "test"})
        original.finish(SpanStatus.OK)

        data = original.to_dict()
        restored = Span.from_dict(data)

        assert restored.trace_id == original.trace_id
        assert restored.span_id == original.span_id
        assert restored.parent_span_id == original.parent_span_id
        assert restored.name == original.name
        assert restored.kind == original.kind
        assert restored.status == original.status
        assert restored.agent_name == original.agent_name
        assert restored.resource_id == original.resource_id


class TestSpanExporterProtocol:
    """Tests for SpanExporter protocol compliance."""

    def test_protocol_methods_exist(self) -> None:
        """Verify SpanExporter protocol has required methods."""
        # This is a structural check - if it compiles, the protocol is defined
        assert hasattr(SpanExporter, "__protocol_attrs__") or callable(
            getattr(SpanExporter, "export", None)
        )
