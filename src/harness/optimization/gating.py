"""Promotion gate decision logic (Phase A refinement 4.2).

The gate decides whether an :class:`EvalResults` outcome should
**promote** the candidate, send it back for **refine**ment, or
**reject** it as worse than doing nothing.

Phase A pre-refinement was a one-line ``candidate.pass_rate ≥
baseline.pass_rate + ε`` check buried inside ``execution_eval.py``.
Phase A refinement 4.2 introduces two changes:

1. **Dual baseline.**  When a resource has never been promoted
   (``last_promoted_version == 0``), the candidate must also clear a
   ``baseline_floor`` — the bare model with no system prompt — by a
   wider margin (``+2ε``) before it can enshrine itself as the first
   incumbent.  Once any version has promoted, ``baseline_floor`` is
   never re-evaluated; the model is the experimental control and we
   compare candidate-against-incumbent only.

2. **Single source of truth.**  All gate semantics live here.
   ``execution_eval.py`` calls :func:`decide` and reacts to the
   returned :class:`Verdict`.  This keeps the gate testable in
   isolation and lets future phases (Phase B bootstrap CI, Phase D
   calibration) extend the decision without re-threading state
   through ``execution_eval``.

The cost stage of the gate lands in Step 3.  This module ships with a
quality-only :func:`decide` signature; Step 3 adds the ``cost`` axis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["promote", "refine", "reject_floor"]


@dataclass(frozen=True)
class GateInputs:
    """The numbers ``Gate.decide`` operates on.

    All pass-rates are in [0.0, 1.0].  ``floor_pass_rate`` is ``None``
    when the floor arm did not run — which is the common case after
    the first promotion (see module docstring).

    Keeping this as a small frozen dataclass instead of positional
    floats makes the call sites at execution_eval self-documenting and
    makes adding the Step 3 cost fields a pure additive change.
    """

    candidate_pass_rate: float
    incumbent_pass_rate: float
    floor_pass_rate: float | None
    is_first_promotion: bool
    epsilon: float = 0.0


def decide(inputs: GateInputs) -> Verdict:
    """Decide promotion verdict from quality numbers alone (Phase A).

    Two-stage gate, evaluated in order:

    1. **Floor stage** — only when ``is_first_promotion=True`` AND
       ``floor_pass_rate`` is not None.  Candidate must satisfy
       ``candidate >= floor + 2 * epsilon``.  Failing this returns
       ``"reject_floor"`` — the prompt engineering has net-negative
       value vs. the bare model.

    2. **Incumbent stage** — always.  Candidate must satisfy
       ``candidate >= incumbent + epsilon``.  Failing this returns
       ``"refine"`` — the candidate is not worse than nothing, but
       isn't an improvement over the current incumbent either.

    Equality at either stage is treated as success (Phase A semantics:
    pre-refinement the gate used ``candidate.pass_rate >=
    baseline.pass_rate + epsilon``; we preserve that).  Phase B's
    bootstrap-CI gate is what tightens ties when they become a
    real problem.

    Returns ``"promote"`` when both stages pass.

    Step 3 will extend the verdict matrix with a cost stage; the
    "refine" return value already covers "quality passes, cost fails"
    so callers don't need to change shape.
    """
    # Stage 1: floor — first-time promotion only, and only when the
    # floor arm actually ran.
    if inputs.is_first_promotion and inputs.floor_pass_rate is not None:
        floor_margin = inputs.floor_pass_rate + 2.0 * inputs.epsilon
        if inputs.candidate_pass_rate < floor_margin:
            return "reject_floor"

    # Stage 2: incumbent — always.
    incumbent_margin = inputs.incumbent_pass_rate + inputs.epsilon
    if inputs.candidate_pass_rate < incumbent_margin:
        return "refine"

    return "promote"


def is_first_promotion(last_promoted_version: int) -> bool:
    """``True`` iff this resource has never had a promoted version.

    Centralised so callers don't open-code the ``== 0`` check.  When
    Phase D adds "promoted but stale" semantics (e.g., calibration
    expired and we want to re-run the floor) this helper grows the
    extra arms.
    """
    return last_promoted_version == 0
