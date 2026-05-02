"""Unit tests for span exporters."""

import json
import tempfile
from pathlib import Path

import pytest

from harness.tracer.base import Span, SpanKind, SpanStatus
from harness.tracer.exporters.file import FileSpanExporter


def create_test_span(
    name: str = "test.operation",
    trace_id: str | None = None,
    span_id: str | None = None,
) -> Span:
    """Create a test span with optional custom IDs."""
    span = Span(
        trace_id=trace_id or "a" * 32,
        span_id=span_id or "b" * 16,
        name=name,
        kind=SpanKind.AGENT_EXECUTION,
    )
    span.finish(SpanStatus.OK)
    return span


class TestFileSpanExporter:
    """Tests for FileSpanExporter."""

    def test_exporter_creation(self, tmp_path: Path) -> None:
        """Test creating file exporter."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        assert exporter.file_path == span_file
        assert exporter.max_file_size_mb == 10.0
        assert exporter.max_files == 5

    def test_exporter_creates_parent_directory(self, tmp_path: Path) -> None:
        """Test exporter creates parent directories."""
        span_file = tmp_path / "nested" / "dir" / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        assert span_file.parent.exists()

    def test_export_single_span(self, tmp_path: Path) -> None:
        """Test exporting a single span."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        span = create_test_span()
        exporter.export(span)

        assert span_file.exists()
        with open(span_file) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["name"] == "test.operation"
            assert data["trace_id"] == "a" * 32

    def test_export_multiple_spans(self, tmp_path: Path) -> None:
        """Test exporting multiple spans creates JSON lines."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        for i in range(5):
            span = create_test_span(name=f"operation.{i}")
            exporter.export(span)

        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 5

            for i, line in enumerate(lines):
                data = json.loads(line)
                assert data["name"] == f"operation.{i}"

    def test_export_batch(self, tmp_path: Path) -> None:
        """Test batch export of spans."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        spans = [create_test_span(name=f"batch.{i}") for i in range(10)]
        exporter.export_batch(spans)

        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 10

    def test_read_spans(self, tmp_path: Path) -> None:
        """Test reading spans back from file."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        spans = [create_test_span(name=f"read.{i}") for i in range(5)]
        for span in spans:
            exporter.export(span)

        read_spans = exporter.read_spans(limit=10)

        assert len(read_spans) == 5
        for i, span_data in enumerate(read_spans):
            assert span_data["name"] == f"read.{i}"

    def test_read_spans_with_limit(self, tmp_path: Path) -> None:
        """Test reading spans respects limit."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        for i in range(20):
            exporter.export(create_test_span(name=f"limited.{i}"))

        read_spans = exporter.read_spans(limit=5)
        assert len(read_spans) == 5

    def test_clear(self, tmp_path: Path) -> None:
        """Test clearing span file."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        exporter.export(create_test_span())
        assert span_file.exists()

        exporter.clear()
        assert not span_file.exists()

    def test_flush_buffer(self, tmp_path: Path) -> None:
        """Test flushing buffered spans."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file, buffer_size=5)

        # Add spans to buffer (less than buffer size)
        for i in range(3):
            exporter.export(create_test_span(name=f"buffered.{i}"))

        # File shouldn't exist yet (buffered)
        assert not span_file.exists() or span_file.stat().st_size == 0

        # Flush should write spans
        exporter.flush()

        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 3

    def test_buffer_auto_flush(self, tmp_path: Path) -> None:
        """Test buffer auto-flushes when full."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file, buffer_size=3)

        # Add exactly buffer_size spans
        for i in range(3):
            exporter.export(create_test_span(name=f"auto.{i}"))

        # Should have auto-flushed
        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 3

    def test_shutdown(self, tmp_path: Path) -> None:
        """Test shutdown flushes remaining spans."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file, buffer_size=10)

        for i in range(5):
            exporter.export(create_test_span(name=f"shutdown.{i}"))

        exporter.shutdown()

        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 5

    def test_pretty_print(self, tmp_path: Path) -> None:
        """Test pretty print option."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file, pretty_print=True)

        exporter.export(create_test_span())

        with open(span_file) as f:
            content = f.read()
            # Pretty print should have newlines within the JSON
            assert "\n" in content.strip()

    def test_repr(self, tmp_path: Path) -> None:
        """Test string representation."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        repr_str = repr(exporter)
        assert "FileSpanExporter" in repr_str
        assert "spans.jsonl" in repr_str


class TestFileSpanExporterRotation:
    """Tests for file rotation functionality."""

    def test_rotation_on_size(self, tmp_path: Path) -> None:
        """Test file rotation when size exceeds limit."""
        span_file = tmp_path / "spans.jsonl"
        # Very small size limit to trigger rotation
        exporter = FileSpanExporter(
            file_path=span_file,
            max_file_size_mb=0.001,  # ~1KB
            max_files=3,
        )

        # Write enough spans to exceed limit
        for i in range(100):
            span = create_test_span(name=f"rotation.{i}")
            span.set_attribute("data", "x" * 100)  # Make span larger
            exporter.export(span)

        # Should have created rotated files
        rotated_files = list(tmp_path.glob("spans_*.jsonl"))
        # At least one rotated file should exist
        assert len(rotated_files) >= 1

    def test_cleanup_old_files(self, tmp_path: Path) -> None:
        """Test cleanup of old rotated files."""
        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(
            file_path=span_file,
            max_file_size_mb=0.0001,  # Very small to force rotation
            max_files=2,
        )

        # Create many rotations
        for i in range(50):
            span = create_test_span(name=f"cleanup.{i}")
            span.set_attribute("data", "x" * 500)
            exporter.export(span)

        # Should have at most max_files rotated files
        rotated_files = list(tmp_path.glob("spans_*.jsonl"))
        assert len(rotated_files) <= 2


class TestFileSpanExporterThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_exports(self, tmp_path: Path) -> None:
        """Test concurrent span exports are thread-safe."""
        import threading

        span_file = tmp_path / "spans.jsonl"
        exporter = FileSpanExporter(file_path=span_file)

        threads = []
        spans_per_thread = 50

        def export_spans(thread_id: int) -> None:
            for i in range(spans_per_thread):
                span = create_test_span(name=f"thread.{thread_id}.{i}")
                exporter.export(span)

        # Start multiple threads
        for t in range(4):
            thread = threading.Thread(target=export_spans, args=(t,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all spans were written
        with open(span_file) as f:
            lines = f.readlines()
            assert len(lines) == 4 * spans_per_thread

            # Verify each line is valid JSON
            for line in lines:
                json.loads(line)  # Should not raise
