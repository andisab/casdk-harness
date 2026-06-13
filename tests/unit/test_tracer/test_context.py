"""Unit tests for trace context propagation."""


from harness.tracer.base import Span, SpanKind
from harness.tracer.context import (
    CGF_CONTEXT_HEADER,
    TRACEPARENT_HEADER,
    TRACESTATE_HEADER,
    ContextManager,
    TraceContext,
    extract_context,
    inject_context,
)


class TestTraceContext:
    """Tests for TraceContext dataclass."""

    def test_context_creation(self) -> None:
        """Test creating a trace context."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
        )

        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16
        assert ctx.trace_flags == "01"  # Default: sampled
        assert ctx.trace_state is None
        assert ctx.agent_name is None

    def test_context_with_cgf_fields(self) -> None:
        """Test context with CGF-specific fields."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            agent_name="python-expert",
            resource_id="res-123",
            resource_type="agent",
        )

        assert ctx.agent_name == "python-expert"
        assert ctx.resource_id == "res-123"
        assert ctx.resource_type == "agent"

    def test_from_span(self) -> None:
        """Test extracting context from a span."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )
        span.agent_name = "test-agent"
        span.resource_id = "res-456"
        span.resource_type = "skill"

        ctx = TraceContext.from_span(span)

        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16
        assert ctx.agent_name == "test-agent"
        assert ctx.resource_id == "res-456"
        assert ctx.resource_type == "skill"


class TestTraceparentFormat:
    """Tests for W3C traceparent format."""

    def test_to_traceparent(self) -> None:
        """Test formatting as traceparent header."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            trace_flags="01",
        )

        traceparent = ctx.to_traceparent()

        expected = f"00-{'a' * 32}-{'b' * 16}-01"
        assert traceparent == expected

    def test_from_traceparent_valid(self) -> None:
        """Test parsing valid traceparent header."""
        traceparent = f"00-{'a' * 32}-{'b' * 16}-01"
        ctx = TraceContext.from_traceparent(traceparent)

        assert ctx is not None
        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16
        assert ctx.trace_flags == "01"

    def test_from_traceparent_invalid_version(self) -> None:
        """Test parsing traceparent with wrong version."""
        traceparent = f"99-{'a' * 32}-{'b' * 16}-01"
        ctx = TraceContext.from_traceparent(traceparent)

        assert ctx is None

    def test_from_traceparent_invalid_format(self) -> None:
        """Test parsing malformed traceparent."""
        assert TraceContext.from_traceparent("not-valid") is None
        assert TraceContext.from_traceparent("00-abc-def-01") is None
        assert TraceContext.from_traceparent("") is None
        assert TraceContext.from_traceparent("00-" + "a" * 31 + "-" + "b" * 16 + "-01") is None

    def test_traceparent_round_trip(self) -> None:
        """Test traceparent serialization/deserialization round-trip."""
        original = TraceContext(
            trace_id="1234567890abcdef" * 2,
            span_id="fedcba0987654321",
            trace_flags="01",
        )

        traceparent = original.to_traceparent()
        restored = TraceContext.from_traceparent(traceparent)

        assert restored is not None
        assert restored.trace_id == original.trace_id
        assert restored.span_id == original.span_id
        assert restored.trace_flags == original.trace_flags


class TestHeaderSerialization:
    """Tests for HTTP header serialization."""

    def test_to_headers_basic(self) -> None:
        """Test basic header serialization."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
        )

        headers = ctx.to_headers()

        assert TRACEPARENT_HEADER in headers
        assert headers[TRACEPARENT_HEADER] == f"00-{'a' * 32}-{'b' * 16}-01"

    def test_to_headers_with_cgf_context(self) -> None:
        """Test headers include CGF context."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            agent_name="test-agent",
            resource_id="res-123",
        )

        headers = ctx.to_headers()

        assert CGF_CONTEXT_HEADER in headers
        import json

        cgf_data = json.loads(headers[CGF_CONTEXT_HEADER])
        assert cgf_data["agent_name"] == "test-agent"
        assert cgf_data["resource_id"] == "res-123"

    def test_to_headers_with_tracestate(self) -> None:
        """Test headers include tracestate."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            trace_state={"key1": "value1", "key2": "value2"},
        )

        headers = ctx.to_headers()

        assert TRACESTATE_HEADER in headers
        # Tracestate format: key1=value1,key2=value2
        state = headers[TRACESTATE_HEADER]
        assert "key1=value1" in state
        assert "key2=value2" in state

    def test_from_headers(self) -> None:
        """Test parsing headers."""
        headers = {
            TRACEPARENT_HEADER: f"00-{'a' * 32}-{'b' * 16}-01",
        }

        ctx = TraceContext.from_headers(headers)

        assert ctx is not None
        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16

    def test_from_headers_case_insensitive(self) -> None:
        """Test parsing headers with different casing."""
        headers = {
            "Traceparent": f"00-{'a' * 32}-{'b' * 16}-01",
        }

        ctx = TraceContext.from_headers(headers)

        assert ctx is not None
        assert ctx.trace_id == "a" * 32

    def test_from_headers_with_cgf_context(self) -> None:
        """Test parsing CGF context header."""
        import json

        headers = {
            TRACEPARENT_HEADER: f"00-{'a' * 32}-{'b' * 16}-01",
            CGF_CONTEXT_HEADER: json.dumps(
                {
                    "agent_name": "test-agent",
                    "resource_id": "res-123",
                    "resource_type": "agent",
                }
            ),
        }

        ctx = TraceContext.from_headers(headers)

        assert ctx is not None
        assert ctx.agent_name == "test-agent"
        assert ctx.resource_id == "res-123"
        assert ctx.resource_type == "agent"

    def test_from_headers_with_tracestate(self) -> None:
        """Test parsing tracestate header."""
        headers = {
            TRACEPARENT_HEADER: f"00-{'a' * 32}-{'b' * 16}-01",
            TRACESTATE_HEADER: "key1=value1,key2=value2",
        }

        ctx = TraceContext.from_headers(headers)

        assert ctx is not None
        assert ctx.trace_state is not None
        assert ctx.trace_state["key1"] == "value1"
        assert ctx.trace_state["key2"] == "value2"

    def test_from_headers_missing_traceparent(self) -> None:
        """Test parsing headers without traceparent."""
        headers = {"other": "value"}

        ctx = TraceContext.from_headers(headers)

        assert ctx is None

    def test_header_round_trip(self) -> None:
        """Test full header serialization/deserialization round-trip."""
        original = TraceContext(
            trace_id="1234567890abcdef" * 2,
            span_id="fedcba0987654321",
            trace_flags="01",
            trace_state={"vendor": "data"},
            agent_name="my-agent",
            resource_id="my-resource",
            resource_type="agent",
        )

        headers = original.to_headers()
        restored = TraceContext.from_headers(headers)

        assert restored is not None
        assert restored.trace_id == original.trace_id
        assert restored.span_id == original.span_id
        assert restored.agent_name == original.agent_name
        assert restored.resource_id == original.resource_id
        assert restored.resource_type == original.resource_type


class TestDictSerialization:
    """Tests for dictionary serialization."""

    def test_to_dict(self) -> None:
        """Test dictionary serialization."""
        ctx = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            agent_name="test",
        )

        data = ctx.to_dict()

        assert data["trace_id"] == "a" * 32
        assert data["span_id"] == "b" * 16
        assert data["agent_name"] == "test"

    def test_from_dict(self) -> None:
        """Test dictionary deserialization."""
        data = {
            "trace_id": "a" * 32,
            "span_id": "b" * 16,
            "trace_flags": "01",
            "agent_name": "test-agent",
        }

        ctx = TraceContext.from_dict(data)

        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16
        assert ctx.agent_name == "test-agent"

    def test_dict_round_trip(self) -> None:
        """Test dictionary serialization round-trip."""
        original = TraceContext(
            trace_id="a" * 32,
            span_id="b" * 16,
            trace_state={"key": "value"},
            agent_name="agent",
            resource_id="resource",
            resource_type="type",
        )

        data = original.to_dict()
        restored = TraceContext.from_dict(data)

        assert restored.trace_id == original.trace_id
        assert restored.span_id == original.span_id
        assert restored.agent_name == original.agent_name


class TestContextHelpers:
    """Tests for context helper functions."""

    def test_inject_context(self) -> None:
        """Test injecting context into carrier."""
        span = Span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )

        carrier: dict[str, str] = {}
        inject_context(span, carrier)

        assert TRACEPARENT_HEADER in carrier

    def test_extract_context(self) -> None:
        """Test extracting context from carrier."""
        carrier = {
            TRACEPARENT_HEADER: f"00-{'a' * 32}-{'b' * 16}-01",
        }

        ctx = extract_context(carrier)

        assert ctx is not None
        assert ctx.trace_id == "a" * 32

    def test_inject_extract_round_trip(self) -> None:
        """Test inject/extract round-trip."""
        span = Span(
            trace_id="1234567890abcdef" * 2,
            span_id="fedcba0987654321",
            name="test",
            kind=SpanKind.AGENT_EXECUTION,
        )
        span.agent_name = "my-agent"

        carrier: dict[str, str] = {}
        inject_context(span, carrier)
        ctx = extract_context(carrier)

        assert ctx is not None
        assert ctx.trace_id == span.trace_id
        assert ctx.span_id == span.span_id
        assert ctx.agent_name == span.agent_name


class TestContextManager:
    """Tests for ContextManager class."""

    def test_push_pop(self) -> None:
        """Test push and pop operations."""
        manager = ContextManager()

        ctx1 = TraceContext(trace_id="a" * 32, span_id="1" * 16)
        ctx2 = TraceContext(trace_id="b" * 32, span_id="2" * 16)

        manager.push(ctx1)
        manager.push(ctx2)

        assert len(manager) == 2

        popped = manager.pop()
        assert popped is ctx2

        popped = manager.pop()
        assert popped is ctx1

        assert len(manager) == 0

    def test_current(self) -> None:
        """Test getting current context."""
        manager = ContextManager()

        assert manager.current() is None

        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        manager.push(ctx)

        assert manager.current() is ctx
        assert len(manager) == 1  # current doesn't remove

    def test_clear(self) -> None:
        """Test clearing all contexts."""
        manager = ContextManager()

        for i in range(5):
            manager.push(TraceContext(trace_id="a" * 32, span_id=f"{i}" * 16))

        assert len(manager) == 5

        manager.clear()

        assert len(manager) == 0
        assert manager.current() is None

    def test_pop_empty(self) -> None:
        """Test popping from empty stack returns None."""
        manager = ContextManager()

        result = manager.pop()

        assert result is None


class TestTraceContextRepr:
    """Tests for string representation."""

    def test_repr(self) -> None:
        """Test repr shows truncated IDs."""
        ctx = TraceContext(
            trace_id="1234567890abcdef" * 2,
            span_id="fedcba0987654321",
        )

        repr_str = repr(ctx)

        assert "TraceContext" in repr_str
        assert "12345678" in repr_str  # Truncated trace_id
        assert "fedcba0987654321" in repr_str  # Full span_id
