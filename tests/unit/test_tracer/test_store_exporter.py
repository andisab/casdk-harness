"""Tests for StoreSpanExporter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from harness.tracer.base import Span, SpanKind, SpanStatus
from harness.tracer.exporters.store import StoreSpanExporter


@pytest.fixture
def mock_store():
    """Create a mock optimization store."""
    store = MagicMock()
    store.store_span = MagicMock()
    store.store_spans = MagicMock()
    return store


@pytest.fixture
def sample_span():
    """Create a sample span for testing."""
    return Span(
        trace_id="trace-123",
        span_id="span-456",
        name="test.operation",
        kind=SpanKind.AGENT_EXECUTION,
        status=SpanStatus.OK,
        start_time=datetime.now(),
        end_time=datetime.now(),
        attributes={"agent.name": "test-agent"},
    )


class TestStoreSpanExporter:
    """Tests for StoreSpanExporter."""

    def test_init_with_store(self, mock_store):
        """Test initialization with explicit store."""
        exporter = StoreSpanExporter(store=mock_store)
        assert exporter._store is mock_store
        assert exporter._buffer_size == 0
        assert not exporter.is_closed

    def test_init_default(self):
        """Test initialization with default values."""
        exporter = StoreSpanExporter()
        assert exporter._store is None
        assert exporter._buffer_size == 0

    def test_export_single_span_immediate(self, mock_store, sample_span):
        """Test exporting a single span with immediate write."""
        exporter = StoreSpanExporter(store=mock_store)
        exporter.export(sample_span)

        mock_store.store_span.assert_called_once_with(sample_span)

    def test_export_batch(self, mock_store, sample_span):
        """Test exporting multiple spans in a batch."""
        exporter = StoreSpanExporter(store=mock_store)
        spans = [sample_span, sample_span, sample_span]
        exporter.export_batch(spans)

        mock_store.store_spans.assert_called_once_with(spans)

    def test_export_batch_empty(self, mock_store):
        """Test exporting empty batch does nothing."""
        exporter = StoreSpanExporter(store=mock_store)
        exporter.export_batch([])

        mock_store.store_spans.assert_not_called()

    def test_buffered_export(self, mock_store, sample_span):
        """Test buffered exporting with buffer_size > 0."""
        exporter = StoreSpanExporter(store=mock_store, buffer_size=3)

        # Add two spans, should not flush yet
        exporter.export(sample_span)
        exporter.export(sample_span)
        mock_store.store_spans.assert_not_called()

        # Add third span, should trigger flush
        exporter.export(sample_span)
        mock_store.store_spans.assert_called_once()
        assert len(mock_store.store_spans.call_args[0][0]) == 3

    def test_flush(self, mock_store, sample_span):
        """Test manual flush."""
        exporter = StoreSpanExporter(store=mock_store, buffer_size=10)

        # Add spans without reaching buffer limit
        exporter.export(sample_span)
        exporter.export(sample_span)
        mock_store.store_spans.assert_not_called()

        # Manual flush
        exporter.flush()
        mock_store.store_spans.assert_called_once()
        assert len(mock_store.store_spans.call_args[0][0]) == 2

    def test_flush_empty_buffer(self, mock_store):
        """Test flush with empty buffer."""
        exporter = StoreSpanExporter(store=mock_store, buffer_size=10)
        exporter.flush()
        mock_store.store_spans.assert_not_called()

    def test_shutdown(self, mock_store, sample_span):
        """Test shutdown flushes remaining spans."""
        exporter = StoreSpanExporter(store=mock_store, buffer_size=10)

        # Add spans
        exporter.export(sample_span)
        exporter.export(sample_span)

        # Shutdown should flush
        exporter.shutdown()
        mock_store.store_spans.assert_called_once()
        assert exporter.is_closed

    def test_export_after_shutdown(self, mock_store, sample_span):
        """Test that export after shutdown is ignored."""
        exporter = StoreSpanExporter(store=mock_store)
        exporter.shutdown()

        # Reset mock to track new calls
        mock_store.store_span.reset_mock()

        # Should not export after shutdown
        exporter.export(sample_span)
        mock_store.store_span.assert_not_called()

    def test_export_batch_after_shutdown(self, mock_store, sample_span):
        """Test that export_batch after shutdown is ignored."""
        exporter = StoreSpanExporter(store=mock_store)
        exporter.shutdown()

        mock_store.store_spans.reset_mock()

        exporter.export_batch([sample_span])
        mock_store.store_spans.assert_not_called()

    def test_double_shutdown_safe(self, mock_store):
        """Test that double shutdown is safe."""
        exporter = StoreSpanExporter(store=mock_store)
        exporter.shutdown()
        exporter.shutdown()  # Should not raise
        assert exporter.is_closed

    def test_get_store_lazy(self, sample_span):
        """Test lazy store initialization."""
        with patch(
            "harness.optimization.store.get_store"
        ) as mock_get_store:
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            exporter = StoreSpanExporter()
            exporter.export(sample_span)

            mock_get_store.assert_called_once()
            mock_store.store_span.assert_called_once_with(sample_span)

    def test_export_error_handling(self, mock_store, sample_span):
        """Test error handling during export."""
        mock_store.store_span.side_effect = Exception("Connection error")

        exporter = StoreSpanExporter(store=mock_store)
        # Should not raise, just log error
        exporter.export(sample_span)

    def test_export_batch_error_handling(self, mock_store, sample_span):
        """Test error handling during batch export."""
        mock_store.store_spans.side_effect = Exception("Connection error")

        exporter = StoreSpanExporter(store=mock_store)
        # Should not raise, just log error
        exporter.export_batch([sample_span])

    def test_flush_error_handling(self, mock_store, sample_span):
        """Test error handling during flush."""
        mock_store.store_spans.side_effect = Exception("Connection error")

        exporter = StoreSpanExporter(store=mock_store, buffer_size=10)
        exporter.export(sample_span)
        # Should not raise, just log error
        exporter.flush()
