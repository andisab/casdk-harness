"""File-based span exporter for debugging and development.

Exports spans to JSON Lines format for easy inspection and debugging.
Supports automatic rotation based on file size.

Example usage:
    exporter = FileSpanExporter("/logs/spans.jsonl")
    tracer.add_exporter(exporter)

    # Spans are written as JSON lines:
    # {"trace_id": "abc", "span_id": "123", "name": "agent.execute", ...}
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from harness.tracer.base import Span

logger = structlog.get_logger(__name__)


@dataclass
class FileSpanExporter:
    """Exports spans to a JSON Lines file.

    Thread-safe implementation with optional file rotation.

    Attributes:
        file_path: Path to the output file.
        max_file_size_mb: Maximum file size before rotation (0 = no rotation).
        max_files: Maximum number of rotated files to keep.
        buffer_size: Number of spans to buffer before writing (0 = immediate).
        pretty_print: If True, format JSON with indentation (not recommended for production).
    """

    file_path: str | Path
    max_file_size_mb: float = 10.0
    max_files: int = 5
    buffer_size: int = 0
    pretty_print: bool = False

    _buffer: list[Span] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _file_handle: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.file_path = Path(self.file_path)
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("File exporter initialized", path=str(self.file_path))

    def export(self, span: Span) -> None:
        """Export a single span.

        Args:
            span: The span to export.
        """
        if self.buffer_size > 0:
            with self._lock:
                self._buffer.append(span)
                if len(self._buffer) >= self.buffer_size:
                    self._flush_buffer()
        else:
            self._write_span(span)

    def export_batch(self, spans: list[Span]) -> None:
        """Export multiple spans.

        Args:
            spans: List of spans to export.
        """
        with self._lock:
            if self.buffer_size > 0:
                self._buffer.extend(spans)
                if len(self._buffer) >= self.buffer_size:
                    self._flush_buffer()
            else:
                for span in spans:
                    self._write_span_unsafe(span)

    def _write_span(self, span: Span) -> None:
        """Write a single span to file (thread-safe).

        Args:
            span: Span to write.
        """
        with self._lock:
            self._write_span_unsafe(span)

    def _write_span_unsafe(self, span: Span) -> None:
        """Write a span to file (not thread-safe, call within lock).

        Args:
            span: Span to write.
        """
        self._check_rotation()

        try:
            data = span.to_dict()
            if self.pretty_print:
                line = json.dumps(data, indent=2, default=str)
            else:
                line = json.dumps(data, default=str)

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        except Exception as e:
            logger.warning(
                "Failed to write span to file",
                error=str(e),
                span_id=span.span_id,
                path=str(self.file_path),
            )

    def _flush_buffer(self) -> None:
        """Flush buffered spans to file (call within lock)."""
        if not self._buffer:
            return

        spans_to_write = self._buffer[:]
        self._buffer.clear()

        for span in spans_to_write:
            self._write_span_unsafe(span)

    def _check_rotation(self) -> None:
        """Check if file needs rotation and rotate if needed."""
        if self.max_file_size_mb <= 0:
            return

        try:
            if not self.file_path.exists():
                return

            file_size_mb = self.file_path.stat().st_size / (1024 * 1024)
            if file_size_mb >= self.max_file_size_mb:
                self._rotate_file()
        except Exception as e:
            logger.warning("Failed to check file rotation", error=str(e))

    def _rotate_file(self) -> None:
        """Rotate the current log file."""
        try:
            # Generate rotated filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            rotated_name = f"{self.file_path.stem}_{timestamp}{self.file_path.suffix}"
            rotated_path = self.file_path.parent / rotated_name

            # Rename current file
            self.file_path.rename(rotated_path)
            logger.debug("Rotated span file", old=str(self.file_path), new=str(rotated_path))

            # Clean up old files if needed
            self._cleanup_old_files()

        except Exception as e:
            logger.warning("Failed to rotate file", error=str(e))

    def _cleanup_old_files(self) -> None:
        """Remove old rotated files beyond max_files limit."""
        if self.max_files <= 0:
            return

        try:
            pattern = f"{self.file_path.stem}_*{self.file_path.suffix}"
            rotated_files = sorted(
                self.file_path.parent.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Remove files beyond limit
            for old_file in rotated_files[self.max_files :]:
                old_file.unlink()
                logger.debug("Removed old span file", path=str(old_file))

        except Exception as e:
            logger.warning("Failed to cleanup old files", error=str(e))

    def flush(self) -> None:
        """Flush any buffered spans to the file."""
        with self._lock:
            self._flush_buffer()

    def shutdown(self) -> None:
        """Shutdown the exporter, flushing remaining spans."""
        self.flush()
        logger.debug("File exporter shutdown", path=str(self.file_path))

    def read_spans(self, limit: int = 1000) -> list[dict]:
        """Read spans from the file (for debugging/testing).

        Args:
            limit: Maximum number of spans to read.

        Returns:
            List of span dictionaries.
        """
        spans = []
        try:
            if not self.file_path.exists():
                return spans

            with open(self.file_path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    line = line.strip()
                    if line:
                        spans.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed to read spans from file", error=str(e))

        return spans

    def clear(self) -> None:
        """Clear the span file (for testing)."""
        with self._lock:
            self._buffer.clear()
            try:
                if self.file_path.exists():
                    self.file_path.unlink()
            except Exception as e:
                logger.warning("Failed to clear span file", error=str(e))

    def __repr__(self) -> str:
        return f"FileSpanExporter({self.file_path})"
