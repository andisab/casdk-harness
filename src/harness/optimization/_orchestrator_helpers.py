"""Shared helpers for the multi-resource orchestrator.

Extracted from ``multi_resource_orchestrator.py`` so that phase modules
under :mod:`harness.optimization._orchestrator_phases` can use them
without creating circular imports against the orchestrator class.

Constants and pure-function helpers live here.  Stateful behavior stays
on the orchestrator class.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Default configuration values
# ---------------------------------------------------------------------------

DEFAULT_QUALITY_THRESHOLD = 0.85
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_REFINEMENT = 1  # Reduced from 3 to limit refinement loops

# Phase A.5: simple-threshold eval gate.  Phase B replaces with bootstrap CI.
DEFAULT_EVAL_PROMOTION_EPSILON = 0.0
DEFAULT_MAX_FEEDBACK_ITERATIONS = 2


# ---------------------------------------------------------------------------
# Agent names for delegation
# ---------------------------------------------------------------------------

AGENT_RESEARCH = "cgf-agents:cgf-research-lead"
AGENT_GENERATE = "context-engineering:context-engineer"
AGENT_ITERATE = "cgf-agents:cgf-prompt-optimizer"
AGENT_EVALUATE = "cgf-agents:cgf-result-evaluator"
AGENT_VALIDATE = "cgf-agents:cgf-coherence-validator"
AGENT_DESIGN = "cgf-agents:cgf-resource-architect"
AGENT_EVAL_ARCHITECT = "cgf-agents:cgf-eval-architect"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def versioned_path(resource_path: str | Path, version: int) -> Path:
    """Get versioned path preserving parent directory.

    Example: "agents/foo.md" + version=1 → "agents/foo-v1.md"

    Args:
        resource_path: Original resource path (e.g., "agents/iac-analyzer.md")
        version: Version number to append

    Returns:
        Path with version suffix, preserving parent directory
    """
    p = Path(resource_path)
    return p.parent / f"{p.stem}-v{version}{p.suffix}"


class PathViolationError(ValueError):
    """Raised when a file operation targets a path outside workspace."""


def validate_write_path(path: Path, workspace_root: Path) -> None:
    """Validate that a path is within the workspace root.

    Used to enforce that all file operations stay within the workspace
    directory, preventing accidental writes to the repository root or
    other system locations.

    Args:
        path: Path to validate (can be relative or absolute).
        workspace_root: Workspace root directory.

    Raises:
        PathViolationError: If path is outside workspace root.
    """
    resolved = path.resolve()
    root_resolved = workspace_root.resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathViolationError(
            f"Path violation: {path} is outside workspace {workspace_root}"
        ) from None


# ---------------------------------------------------------------------------
# Eval-framework tracing (CGF Stage 3 Phase A.7)
# ---------------------------------------------------------------------------
#
# OTel resource attributes per the v2 spec § 3.A.6: ``harness.eval.task_id``,
# ``harness.eval.phase``, ``harness.eval.resource_path``,
# ``harness.eval.resource_type``, ``harness.eval.outcome``.  Spans are added
# via the CGF tracer (``harness.tracer.get_tracer().async_span``).
#
# Tracing is OPTIONAL infrastructure — if the tracer fails to initialize
# (no exporter configured, registry collision, etc.), eval phases continue
# without spans.  Prometheus metrics from A.6 are unaffected.


def new_eval_task_id() -> str:
    """Generate a fresh task-id for one EVAL_DESIGN or EXECUTION_EVAL invocation.

    Format: short hex prefix to keep telemetry compact while remaining
    unique across concurrent runs.
    """
    return uuid.uuid4().hex[:16]


@contextlib.asynccontextmanager
async def eval_phase_span(
    name: str,
    *,
    task_id: str,
    phase: str,
    extra: dict[str, Any] | None = None,
) -> AsyncIterator[Any]:
    """Async context manager that wraps an eval phase in a CGF tracer span.

    Yields a ``Span`` (with ``set_attribute``) when tracing is available,
    or a no-op ``_NoOpSpan`` when the tracer can't be obtained.  Either
    way, ``async with eval_phase_span(...) as span: ...`` is safe and
    never propagates infrastructure errors out of the eval phase.

    Args:
        name: Span name (e.g., ``"eval.design"``, ``"eval.execution"``).
        task_id: Unique-per-phase id; set as ``harness.eval.task_id`` attr.
        phase: Phase name; set as ``harness.eval.phase`` attr.
        extra: Additional initial attributes (resource_path, etc.).

    Yields:
        A span-like object supporting ``set_attribute(key, value)``.
    """
    attributes: dict[str, Any] = {
        "harness.eval.task_id": task_id,
        "harness.eval.phase": phase,
    }
    if extra:
        attributes.update(extra)

    try:
        from harness.tracer import SpanKind, get_tracer
    except Exception:  # noqa: BLE001 — tracer module may not be importable
        yield _NoOpSpan()
        return

    try:
        tracer = get_tracer()
        async_span = getattr(tracer, "async_span", None)
        if async_span is None:
            yield _NoOpSpan()
            return
        async with async_span(
            name, kind=SpanKind.AGENT_EXECUTION, attributes=attributes
        ) as span:
            yield span
    except Exception:  # noqa: BLE001 — tracing must never break grading
        yield _NoOpSpan()


class _NoOpSpan:
    """Span placeholder when tracing is unavailable.  All operations no-op."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        return None

    def add_event(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def record_exception(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        return None
