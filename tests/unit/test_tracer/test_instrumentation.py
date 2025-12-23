"""Unit tests for instrumentation decorators."""

import asyncio

import pytest

from harness.tracer.base import Span, SpanKind, SpanStatus
from harness.tracer.instrumentation import (
    TracedClass,
    get_global_tracer,
    record_tokens,
    set_global_tracer,
    trace_method,
    traced,
)
from harness.tracer.otel_tracer import OTelTracer


class MockExporter:
    """Mock exporter for testing."""

    def __init__(self) -> None:
        self.spans: list[Span] = []

    def export(self, span: Span) -> None:
        self.spans.append(span)

    def export_batch(self, spans: list[Span]) -> None:
        self.spans.extend(spans)

    def flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


@pytest.fixture
def tracer_with_exporter() -> tuple[OTelTracer, MockExporter]:
    """Create a tracer with mock exporter."""
    tracer = OTelTracer()
    exporter = MockExporter()
    tracer.add_exporter(exporter)
    set_global_tracer(tracer)
    return tracer, exporter


@pytest.fixture(autouse=True)
def cleanup_global_tracer() -> None:
    """Reset global tracer after each test."""
    yield
    set_global_tracer(None)  # type: ignore[arg-type]


class TestGlobalTracer:
    """Tests for global tracer management."""

    def test_set_and_get_global_tracer(self) -> None:
        """Test setting and getting global tracer."""
        tracer = OTelTracer()

        set_global_tracer(tracer)
        retrieved = get_global_tracer()

        assert retrieved is tracer

    def test_get_global_tracer_when_not_set(self) -> None:
        """Test getting global tracer when not set."""
        set_global_tracer(None)  # type: ignore[arg-type]

        tracer = get_global_tracer()

        assert tracer is None


class TestTracedDecorator:
    """Tests for the @traced decorator."""

    def test_traced_sync_function(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test tracing synchronous function."""
        _, exporter = tracer_with_exporter

        @traced("test.operation", SpanKind.TOOL_CALL)
        def my_function() -> str:
            return "result"

        result = my_function()

        assert result == "result"
        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "test.operation"
        assert exporter.spans[0].kind == SpanKind.TOOL_CALL
        assert exporter.spans[0].status == SpanStatus.OK

    @pytest.mark.asyncio
    async def test_traced_async_function(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test tracing asynchronous function."""
        _, exporter = tracer_with_exporter

        @traced("async.operation", SpanKind.AGENT_EXECUTION)
        async def async_function() -> str:
            await asyncio.sleep(0.01)
            return "async result"

        result = await async_function()

        assert result == "async result"
        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "async.operation"

    def test_traced_with_exception(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test tracing function that raises exception."""
        _, exporter = tracer_with_exporter

        @traced("failing.operation")
        def failing_function() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_function()

        assert len(exporter.spans) == 1
        assert exporter.spans[0].status == SpanStatus.ERROR
        assert exporter.spans[0].error_message == "test error"
        assert exporter.spans[0].events[0]["attributes"]["exception.type"] == "ValueError"

    def test_traced_default_name(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test traced decorator uses function name as default."""
        _, exporter = tracer_with_exporter

        @traced()
        def auto_named_function() -> None:
            pass

        auto_named_function()

        assert len(exporter.spans) == 1
        # Should include module and function name
        assert "auto_named_function" in exporter.spans[0].name

    def test_traced_with_dynamic_name(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test traced decorator with dynamic name substitution."""
        _, exporter = tracer_with_exporter

        @traced("operation.{name}")
        def dynamic_operation(name: str) -> str:
            return f"processed {name}"

        result = dynamic_operation("test-item")

        assert result == "processed test-item"
        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "operation.test-item"

    def test_traced_extract_attrs(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test extracting attributes from arguments."""
        _, exporter = tracer_with_exporter

        @traced("tool.call", extract_attrs=["tool_name", "arg_count"])
        def call_tool(tool_name: str, arg_count: int) -> None:
            pass

        call_tool("Read", 5)

        assert len(exporter.spans) == 1
        attrs = exporter.spans[0].attributes
        assert attrs["arg.tool_name"] == "Read"
        assert attrs["arg.arg_count"] == "5"

    def test_traced_record_args(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test recording all arguments."""
        _, exporter = tracer_with_exporter

        @traced("full.record", record_args=True)
        def recorded_function(a: int, b: str, c: float) -> None:
            pass

        recorded_function(1, "two", 3.0)

        assert len(exporter.spans) == 1
        attrs = exporter.spans[0].attributes
        assert attrs["arg.a"] == "1"
        assert attrs["arg.b"] == "two"
        assert attrs["arg.c"] == "3.0"

    def test_traced_record_result(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test recording return value."""
        _, exporter = tracer_with_exporter

        @traced("result.record", record_result=True)
        def result_function() -> dict:
            return {"key": "value"}

        result_function()

        assert len(exporter.spans) == 1
        attrs = exporter.spans[0].attributes
        assert "result" in attrs
        assert "key" in attrs["result"]

    def test_traced_no_tracer(self) -> None:
        """Test decorated function works when no tracer is set."""
        set_global_tracer(None)  # type: ignore[arg-type]

        @traced("no.tracer")
        def untraced_function() -> str:
            return "still works"

        result = untraced_function()

        assert result == "still works"

    def test_traced_disabled_tracer(self) -> None:
        """Test decorated function works with disabled tracer."""
        tracer = OTelTracer(enabled=False)
        exporter = MockExporter()
        tracer.add_exporter(exporter)
        set_global_tracer(tracer)

        @traced("disabled.tracer")
        def disabled_function() -> str:
            return "works"

        result = disabled_function()

        assert result == "works"
        assert len(exporter.spans) == 0


class TestTraceMethodDecorator:
    """Tests for the @trace_method decorator."""

    def test_trace_method_sync(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test tracing sync class method."""
        _, exporter = tracer_with_exporter

        class MyClass:
            @trace_method(SpanKind.AGENT_EXECUTION)
            def my_method(self, value: int) -> int:
                return value * 2

        obj = MyClass()
        result = obj.my_method(5)

        assert result == 10
        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "myclass.my_method"
        assert exporter.spans[0].attributes["class"] == "MyClass"

    @pytest.mark.asyncio
    async def test_trace_method_async(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test tracing async class method."""
        _, exporter = tracer_with_exporter

        class AsyncClass:
            @trace_method(SpanKind.TOOL_CALL)
            async def async_method(self) -> str:
                await asyncio.sleep(0.01)
                return "async"

        obj = AsyncClass()
        result = await obj.async_method()

        assert result == "async"
        assert len(exporter.spans) == 1
        assert "asyncclass.async_method" in exporter.spans[0].name

    def test_trace_method_with_prefix(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test trace_method with custom name prefix."""
        _, exporter = tracer_with_exporter

        class PrefixedClass:
            @trace_method(SpanKind.AGENT_EXECUTION, name_prefix="custom")
            def prefixed_method(self) -> None:
                pass

        obj = PrefixedClass()
        obj.prefixed_method()

        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "custom.prefixed_method"

    def test_trace_method_exception(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test trace_method records exceptions."""
        _, exporter = tracer_with_exporter

        class FailingClass:
            @trace_method()
            def failing_method(self) -> None:
                raise RuntimeError("method failed")

        obj = FailingClass()
        with pytest.raises(RuntimeError):
            obj.failing_method()

        assert len(exporter.spans) == 1
        assert exporter.spans[0].status == SpanStatus.ERROR
        assert exporter.spans[0].error_message == "method failed"
        assert exporter.spans[0].events[0]["attributes"]["exception.type"] == "RuntimeError"


class TestTracedClass:
    """Tests for the TracedClass mixin."""

    def test_traced_class_methods(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test TracedClass automatically traces specified methods."""
        _, exporter = tracer_with_exporter

        class MyTracedClass(TracedClass):
            traced_methods = ["execute", "process"]
            traced_kind = SpanKind.AGENT_EXECUTION
            traced_prefix = "mytraced"

            def execute(self) -> str:
                return "executed"

            def process(self, data: str) -> str:
                return f"processed {data}"

            def untraced(self) -> str:
                return "not traced"

        obj = MyTracedClass()
        obj.execute()
        obj.process("test")
        obj.untraced()

        assert len(exporter.spans) == 2
        assert exporter.spans[0].name == "mytraced.execute"
        assert exporter.spans[1].name == "mytraced.process"


class TestRecordTokens:
    """Tests for the record_tokens helper function."""

    def test_record_tokens_on_current_span(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test recording token usage on current span."""
        tracer, exporter = tracer_with_exporter

        with tracer.span("llm.request", SpanKind.LLM_REQUEST) as span:
            record_tokens(input_tokens=100, output_tokens=50, cached_tokens=10, model="gpt-4")

        assert len(exporter.spans) == 1
        token_usage = exporter.spans[0].token_usage
        assert token_usage is not None
        assert token_usage["input"] == 100
        assert token_usage["output"] == 50
        assert token_usage["cached"] == 10
        assert token_usage["total"] == 150
        assert exporter.spans[0].attributes["llm.model"] == "gpt-4"

    def test_record_tokens_without_model(
        self, tracer_with_exporter: tuple[OTelTracer, MockExporter]
    ) -> None:
        """Test recording tokens without model name."""
        tracer, exporter = tracer_with_exporter

        with tracer.span("llm.request", SpanKind.LLM_REQUEST):
            record_tokens(input_tokens=50, output_tokens=25)

        assert len(exporter.spans) == 1
        token_usage = exporter.spans[0].token_usage
        assert token_usage is not None
        assert token_usage["input"] == 50
        assert token_usage["output"] == 25
        assert "llm.model" not in exporter.spans[0].attributes

    def test_record_tokens_no_current_span(self) -> None:
        """Test record_tokens is no-op when no current span."""
        tracer = OTelTracer()
        set_global_tracer(tracer)

        # Should not raise
        record_tokens(input_tokens=100, output_tokens=50)

    def test_record_tokens_no_tracer(self) -> None:
        """Test record_tokens is no-op when no tracer set."""
        set_global_tracer(None)  # type: ignore[arg-type]

        # Should not raise
        record_tokens(input_tokens=100, output_tokens=50)
