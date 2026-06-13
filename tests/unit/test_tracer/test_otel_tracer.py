"""Unit tests for OTelTracer implementation."""

from unittest.mock import MagicMock

import pytest

from harness.tracer.base import Span, SpanKind, SpanStatus
from harness.tracer.otel_tracer import OTelTracer


class MockExporter:
    """Mock exporter for testing."""

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.batches: list[list[Span]] = []
        self.flushed = False
        self.shutdown_called = False

    def export(self, span: Span) -> None:
        self.spans.append(span)

    def export_batch(self, spans: list[Span]) -> None:
        self.batches.append(spans)

    def flush(self) -> None:
        self.flushed = True

    def shutdown(self) -> None:
        self.shutdown_called = True


class TestOTelTracerBasics:
    """Basic OTelTracer functionality tests."""

    def test_tracer_creation(self) -> None:
        """Test creating a tracer with default settings."""
        tracer = OTelTracer()
        assert tracer.service_name == "cgf"
        assert tracer.enabled is True
        assert tracer.exporters == []

    def test_tracer_disabled(self) -> None:
        """Test disabled tracer returns minimal span."""
        tracer = OTelTracer(enabled=False)
        span = tracer.start_span("test", SpanKind.AGENT_EXECUTION)

        assert span.trace_id == "disabled"
        assert span.span_id == "disabled"

    def test_start_span_creates_valid_span(self) -> None:
        """Test starting a span creates proper Span object."""
        tracer = OTelTracer()
        span = tracer.start_span(
            name="test.operation",
            kind=SpanKind.TOOL_CALL,
            attributes={"key": "value"},
        )

        assert len(span.trace_id) == 32
        assert len(span.span_id) == 16
        assert span.name == "test.operation"
        assert span.kind == SpanKind.TOOL_CALL
        assert span.attributes["key"] == "value"
        assert span.parent_span_id is None

    def test_child_span_has_parent(self) -> None:
        """Test child span properly references parent."""
        tracer = OTelTracer()
        parent = tracer.start_span("parent", SpanKind.AGENT_EXECUTION)
        child = tracer.start_span("child", SpanKind.TOOL_CALL, parent=parent)

        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id
        assert child.span_id != parent.span_id


class TestOTelTracerContextManager:
    """Tests for the span context manager."""

    def test_span_context_manager(self) -> None:
        """Test span context manager creates and finishes span."""
        tracer = OTelTracer()
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        with tracer.span("test.operation", SpanKind.AGENT_EXECUTION) as span:
            span.set_attribute("test", "value")

        assert len(exporter.spans) == 1
        exported = exporter.spans[0]
        assert exported.name == "test.operation"
        assert exported.status == SpanStatus.OK
        assert exported.end_time is not None

    def test_span_context_manager_records_exception(self) -> None:
        """Test span context manager records exceptions."""
        tracer = OTelTracer()
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        with pytest.raises(ValueError):
            with tracer.span("failing.operation", SpanKind.AGENT_EXECUTION):
                raise ValueError("test error")

        assert len(exporter.spans) == 1
        exported = exporter.spans[0]
        assert exported.status == SpanStatus.ERROR
        assert exported.error_message == "test error"
        # Exception type is in events
        assert len(exported.events) == 1
        assert exported.events[0]["attributes"]["exception.type"] == "ValueError"

    def test_nested_spans(self) -> None:
        """Test nested span context managers maintain parent chain."""
        tracer = OTelTracer()
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        with tracer.span("parent", SpanKind.AGENT_EXECUTION) as parent:
            with tracer.span("child", SpanKind.TOOL_CALL) as child:
                assert child.parent_span_id == parent.span_id
                assert child.trace_id == parent.trace_id

        # Both spans should be exported
        assert len(exporter.spans) == 2
        # Child exported first (when its context exits)
        assert exporter.spans[0].name == "child"
        assert exporter.spans[1].name == "parent"

    def test_current_span(self) -> None:
        """Test current_span returns the active span."""
        tracer = OTelTracer()

        assert tracer.current_span() is None

        with tracer.span("test", SpanKind.AGENT_EXECUTION) as span:
            current = tracer.current_span()
            assert current is span

        assert tracer.current_span() is None


class TestOTelTracerTraceManagement:
    """Tests for trace lifecycle management."""

    def test_start_trace(self) -> None:
        """Test starting a new trace."""
        tracer = OTelTracer()
        trace_id = tracer.start_trace()

        assert len(trace_id) == 32
        assert tracer._active_trace_id == trace_id

        # New spans should use this trace ID
        span = tracer.start_span("test", SpanKind.AGENT_EXECUTION)
        assert span.trace_id == trace_id

    def test_start_trace_with_explicit_id(self) -> None:
        """Test starting trace with explicit ID."""
        tracer = OTelTracer()
        explicit_id = "a" * 32
        trace_id = tracer.start_trace(explicit_id)

        assert trace_id == explicit_id
        assert tracer._active_trace_id == explicit_id

    def test_end_trace(self) -> None:
        """Test ending a trace."""
        tracer = OTelTracer()
        tracer.start_trace()
        tracer.end_trace()

        assert tracer._active_trace_id is None


class TestOTelTracerExporters:
    """Tests for exporter management."""

    def test_add_exporter(self) -> None:
        """Test adding exporters."""
        tracer = OTelTracer()
        exporter1 = MockExporter()
        exporter2 = MockExporter()

        tracer.add_exporter(exporter1)
        tracer.add_exporter(exporter2)

        assert len(tracer.exporters) == 2
        assert exporter1 in tracer.exporters
        assert exporter2 in tracer.exporters

    def test_remove_exporter(self) -> None:
        """Test removing exporters."""
        tracer = OTelTracer()
        exporter = MockExporter()

        tracer.add_exporter(exporter)
        tracer.remove_exporter(exporter)

        assert exporter not in tracer.exporters

    def test_export_to_multiple_exporters(self) -> None:
        """Test spans are exported to all registered exporters."""
        tracer = OTelTracer()
        exporter1 = MockExporter()
        exporter2 = MockExporter()

        tracer.add_exporter(exporter1)
        tracer.add_exporter(exporter2)

        with tracer.span("test", SpanKind.AGENT_EXECUTION):
            pass

        assert len(exporter1.spans) == 1
        assert len(exporter2.spans) == 1

    def test_exporter_failure_doesnt_break_other_exporters(self) -> None:
        """Test one failing exporter doesn't prevent others from receiving spans."""
        tracer = OTelTracer()

        failing_exporter = MagicMock()
        failing_exporter.export.side_effect = Exception("export failed")

        working_exporter = MockExporter()

        tracer.add_exporter(failing_exporter)
        tracer.add_exporter(working_exporter)

        with tracer.span("test", SpanKind.AGENT_EXECUTION):
            pass

        # Working exporter should still receive the span
        assert len(working_exporter.spans) == 1


class TestOTelTracerBuffering:
    """Tests for span buffering."""

    def test_buffered_export(self) -> None:
        """Test buffered span export."""
        tracer = OTelTracer(buffer_size=3)
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        # First two spans shouldn't trigger export
        with tracer.span("span1", SpanKind.AGENT_EXECUTION):
            pass
        with tracer.span("span2", SpanKind.AGENT_EXECUTION):
            pass

        assert len(exporter.batches) == 0

        # Third span should trigger batch export
        with tracer.span("span3", SpanKind.AGENT_EXECUTION):
            pass

        assert len(exporter.batches) == 1
        assert len(exporter.batches[0]) == 3

    def test_flush_exports_buffered_spans(self) -> None:
        """Test flush exports remaining buffered spans."""
        tracer = OTelTracer(buffer_size=10)
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        with tracer.span("span1", SpanKind.AGENT_EXECUTION):
            pass
        with tracer.span("span2", SpanKind.AGENT_EXECUTION):
            pass

        assert len(exporter.batches) == 0

        tracer.flush()

        assert len(exporter.batches) == 1
        assert len(exporter.batches[0]) == 2
        assert exporter.flushed is True


class TestOTelTracerShutdown:
    """Tests for tracer shutdown."""

    def test_shutdown(self) -> None:
        """Test tracer shutdown."""
        tracer = OTelTracer()
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        tracer.shutdown()

        assert exporter.shutdown_called is True
        assert tracer.enabled is False
        assert len(tracer.exporters) == 0

    def test_context_manager_calls_shutdown(self) -> None:
        """Test using tracer as context manager calls shutdown."""
        exporter = MockExporter()

        with OTelTracer() as tracer:
            tracer.add_exporter(exporter)
            with tracer.span("test", SpanKind.AGENT_EXECUTION):
                pass

        assert exporter.shutdown_called is True


class TestDisabledTracer:
    """Tests for disabled tracer behavior."""

    def test_disabled_tracer_span_context(self) -> None:
        """Test disabled tracer with context manager."""
        tracer = OTelTracer(enabled=False)
        exporter = MockExporter()
        tracer.add_exporter(exporter)

        with tracer.span("test", SpanKind.AGENT_EXECUTION) as span:
            span.set_attribute("key", "value")

        # No spans should be exported
        assert len(exporter.spans) == 0
