"""Shared helpers for the multi-resource orchestrator.

Extracted from ``multi_resource_orchestrator.py`` so that phase modules
under :mod:`harness.optimization._orchestrator_phases` can use them
without creating circular imports against the orchestrator class.

Constants and pure-function helpers live here.  Stateful behavior stays
on the orchestrator class.
"""

from __future__ import annotations

from pathlib import Path

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
