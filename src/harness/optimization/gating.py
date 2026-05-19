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

Phase A refinement 4.3 added a third, **cost** stage.  Step 4 (this
refinement, I15) makes the cost gate's tolerance ``τ`` **quality-aware**:
big quality gains earn extra cost-growth headroom, so a candidate that
shifts pass-rate by +13pp doesn't get rejected for a 16% cost-per-success
bump.  See :func:`effective_cost_tolerance` below — it does NOT collapse
quality and cost into a weighted scalar (Goodhart-on-tokens, Han et al.
2025); it just lets ``τ`` borrow signal from the quality delta.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Verdict = Literal["promote", "refine", "reject_floor", "reject_cost"]

# I15 — quality-scaled cost tolerance defaults.
#
# ``DEFAULT_COST_QUALITY_BONUS = 1.0`` means: each percentage point of
# candidate quality gain over incumbent grants 1 percentage point of
# extra cost-growth headroom on top of ``base_tau``.  At +10pp quality,
# effective τ rises from 0.10 to 0.20.  Clamped at ``DEFAULT_COST_TAU_CAP``
# so a +60pp quality jump can't make the cost gate functionally useless.
DEFAULT_COST_QUALITY_BONUS = 1.0
DEFAULT_COST_TAU_CAP = 0.5


def _resolve_cost_quality_bonus() -> float:
    """Resolve ``CGF_COST_QUALITY_BONUS`` env override.

    Default ``DEFAULT_COST_QUALITY_BONUS = 1.0``.  Operators tune this
    when they want to permit faster cost growth for quality wins (raise)
    or hold the cost line strictly (lower toward 0).  Negative values
    are clamped to 0 (we never punish quality gains with a tighter cost
    gate; only Phase A.4.4.b stagnation early-stop handles "quality drop
    that was within ε").
    """
    raw = os.environ.get("CGF_COST_QUALITY_BONUS")
    if not raw:
        return DEFAULT_COST_QUALITY_BONUS
    try:
        v = float(raw)
    except ValueError:
        return DEFAULT_COST_QUALITY_BONUS
    return max(0.0, v)


def effective_cost_tolerance(
    base_tau: float,
    quality_delta: float,
    bonus_factor: float | None = None,
    bonus_cap: float = DEFAULT_COST_TAU_CAP,
) -> float:
    """Quality-scaled cost-growth tolerance for the cost gate.

    .. math::

        \\tau_\\mathrm{eff} = base\\_tau + \\min\\bigl(bonus\\_cap,\\ \\max(0, \\Delta \\cdot bonus\\_factor)\\bigr)

    Where ``Δ`` is ``candidate.pass_rate - incumbent.pass_rate`` (a value
    in roughly ``[-1, 1]``; positive when candidate quality improved).
    ``bonus_factor`` defaults to ``CGF_COST_QUALITY_BONUS`` env (default
    ``1.0``).

    The ``bonus_cap`` clamps only the **quality-derived bonus**, never
    ``base_tau`` itself.  Operators who deliberately set
    ``CGF_TOKEN_REGRESSION_TOLERANCE=1.0`` (permissive run) still get
    their chosen ceiling; we only refuse to let a single huge quality
    jump grant unbounded extra cost headroom on top of that.

    **Worked examples** at default ``bonus_factor=1.0``,
    ``bonus_cap=0.5``, ``base_tau=0.10``:

    +-----------------+-------+--------------------------------+
    | Quality Δ       | τ_eff | Comment                        |
    +=================+=======+================================+
    | −0.10           | 0.10  | floor at base (max(0, …) clamp)|
    +-----------------+-------+--------------------------------+
    |  0.00           | 0.10  | unchanged from Phase A.4.3     |
    +-----------------+-------+--------------------------------+
    | +0.13 (13 pp)   | 0.23  | sample real-quality win case   |
    +-----------------+-------+--------------------------------+
    | +0.30 (30 pp)   | 0.40  | recovery (0.33 → 0.63) ok      |
    +-----------------+-------+--------------------------------+
    | +0.60 (60 pp)   | 0.60  | bonus clamped at 0.50          |
    +-----------------+-------+--------------------------------+

    This is **not** a weighted-sum scalar (PHASEA_SUMMARY § 4.3 explicitly
    warned against that).  The quality and cost stages remain
    independent: we just let ``τ`` borrow signal from the quality delta
    so that a +N pp quality win can absorb up to N pp of cost-per-success
    regression without rejection.
    """
    if bonus_factor is None:
        bonus_factor = _resolve_cost_quality_bonus()
    bonus = min(bonus_cap, max(0.0, quality_delta * bonus_factor))
    return base_tau + bonus


@dataclass(frozen=True)
class GateInputs:
    """The numbers ``Gate.decide`` operates on.

    All pass-rates are in [0.0, 1.0].

    **Naming gotcha (I11).** ``floor_pass_rate`` reads as "the pass rate
    of the floor (bare-model) arm" — that is NOT what it means here.
    It is the floor arm's **own** pass rate (i.e. how the bare model
    scored on its own arm of the scenario suite).  Compare against
    ``candidate_pass_rate`` directly to detect "candidate is worse than
    no prompt at all."  Specifically the floor stage checks
    ``candidate_pass_rate >= floor_pass_rate + 2 * epsilon``.

    ``floor_pass_rate`` is ``None`` when the floor arm did not run —
    which is the common case after the first promotion (see module
    docstring).

    Phase A refinement 4.3: cost-per-success inputs.  ``None`` for
    either side means "no signal" and the cost stage auto-passes.
    This handles the common case where the baseline has zero successes
    (every passing candidate would otherwise be rejected for "infinite
    cost regression").  ``tau`` is the cost tolerance (default 0.10 =
    10 %); candidate cost ≤ baseline × (1 + tau) passes.
    """

    candidate_pass_rate: float
    incumbent_pass_rate: float
    floor_pass_rate: float | None
    is_first_promotion: bool
    epsilon: float = 0.0
    # Cost stage (Step 3).  Defaults preserve Step 2 behaviour when
    # callers haven't been updated yet — None values disable the gate.
    candidate_cost_per_success: float | None = None
    incumbent_cost_per_success: float | None = None
    tau: float = 0.10


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

    Returns ``"promote"`` only when all stages pass.

    Phase A refinement 4.3 added a **cost stage** after the quality
    stages.  Failing it returns ``"reject_cost"`` — quality is fine
    but the candidate is too expensive vs the incumbent.  The two-gate
    pattern (quality AND cost) is the multi-objective canon; weighted
    scalars are explicitly avoided (Goodhart-on-tokens, Han et al.
    2025).
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

    # Stage 3 (Phase A refinement 4.3 + I15): cost.  Auto-passes when
    # either side is None — incumbent=None means no signal to regress
    # against (typically zero baseline successes), candidate=None means
    # the candidate had zero successes and the quality stage would have
    # already rejected it.
    #
    # I15: τ is scaled by the quality delta so a real quality win can
    # absorb proportional cost growth.  See
    # :func:`effective_cost_tolerance` for the math.
    if (
        inputs.candidate_cost_per_success is not None
        and inputs.incumbent_cost_per_success is not None
    ):
        quality_delta = inputs.candidate_pass_rate - inputs.incumbent_pass_rate
        effective_tau = effective_cost_tolerance(
            base_tau=inputs.tau,
            quality_delta=quality_delta,
        )
        cost_ceiling = inputs.incumbent_cost_per_success * (1.0 + effective_tau)
        if inputs.candidate_cost_per_success > cost_ceiling:
            return "reject_cost"

    return "promote"


def is_first_promotion(last_promoted_version: int) -> bool:
    """``True`` iff this resource has never had a promoted version.

    Centralised so callers don't open-code the ``== 0`` check.  When
    Phase D adds "promoted but stale" semantics (e.g., calibration
    expired and we want to re-run the floor) this helper grows the
    extra arms.
    """
    return last_promoted_version == 0
