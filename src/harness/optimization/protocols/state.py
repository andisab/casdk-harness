"""State phase ordering protocol for multi-resource optimization pipeline.

Defines the canonical phase ordering and transition validation rules
for the optimization state machine.

Usage:
    from harness.optimization.protocols.state import (
        PHASE_ORDER,
        is_valid_transition,
    )

    assert is_valid_transition("RESEARCH", "DESIGN")       # forward step
    assert is_valid_transition("EXECUTION_EVAL", "ITERATE") # allowed backward
    assert not is_valid_transition("RESEARCH", "GENERATE")  # skip not allowed
"""

from __future__ import annotations

# -- phase ordering ------------------------------------------------------------

PHASE_ORDER: list[str] = [
    "RESEARCH",
    "DESIGN",
    "QA",
    "GENERATE",
    "EVAL_DESIGN",
    "ITERATE",
    "EXECUTION_EVAL",
    "VALIDATE",
    "COMPLETE",
]

# -- allowed backward transitions ---------------------------------------------

_BACKWARD_TRANSITIONS: set[tuple[str, str]] = {
    ("EXECUTION_EVAL", "ITERATE"),
    ("VALIDATE", "ITERATE"),
}


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    """Check whether a state transition is allowed.

    A transition is valid if it moves forward by exactly one step in
    :data:`PHASE_ORDER`, or if it is an explicitly allowed backward
    transition (retry loops).

    Args:
        from_phase: Current phase name.
        to_phase: Target phase name.

    Returns:
        ``True`` if the transition is allowed, ``False`` otherwise.
    """
    if (from_phase, to_phase) in _BACKWARD_TRANSITIONS:
        return True

    try:
        from_idx = PHASE_ORDER.index(from_phase)
        to_idx = PHASE_ORDER.index(to_phase)
    except ValueError:
        return False

    return to_idx == from_idx + 1
