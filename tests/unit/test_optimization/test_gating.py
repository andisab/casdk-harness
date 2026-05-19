"""Phase A refinement 4.2 — dual-baseline promotion gate.

These tests pin the verdict matrix of :func:`harness.optimization.gating.decide`.
Two stages of the gate, evaluated in order:

1. **Floor stage** (first-time promotion only):
   ``candidate >= floor + 2*epsilon``.  Failure → ``"reject_floor"``.
2. **Incumbent stage** (always):
   ``candidate >= incumbent + epsilon``.  Failure → ``"refine"``.

Both pass → ``"promote"``.
"""

from __future__ import annotations

import pytest

from harness.optimization.gating import (
    GateInputs,
    Verdict,
    decide,
    is_first_promotion,
)


def _ginputs(
    *,
    candidate: float,
    incumbent: float,
    floor: float | None,
    first: bool,
    eps: float = 0.0,
) -> GateInputs:
    return GateInputs(
        candidate_pass_rate=candidate,
        incumbent_pass_rate=incumbent,
        floor_pass_rate=floor,
        is_first_promotion=first,
        epsilon=eps,
    )


class TestFirstPromotionWithFloor:
    """Resource has never promoted; floor arm ran."""

    def test_beats_floor_and_incumbent_promotes(self) -> None:
        # First-promotion: incumbent_pass_rate == baseline-v0 == floor in
        # the simplest case; assume the candidate clears both.
        v = decide(_ginputs(candidate=0.8, incumbent=0.5, floor=0.4, first=True))
        assert v == "promote"

    def test_below_floor_rejects(self) -> None:
        # Candidate worse than bare model → reject.  Even if it ties
        # incumbent, the floor failure takes precedence.
        v = decide(_ginputs(candidate=0.3, incumbent=0.5, floor=0.4, first=True))
        assert v == "reject_floor"

    def test_equal_to_floor_promotes_at_zero_epsilon(self) -> None:
        # Phase A pre-refinement gate used ``>=``; equality at ε=0 was
        # a tie that promoted.  We preserve that semantics — Phase B's
        # bootstrap-CI gate is what tightens ties.  When this becomes
        # a real problem operationally, set ε>0.
        v = decide(_ginputs(candidate=0.4, incumbent=0.4, floor=0.4, first=True))
        assert v == "promote"

    def test_beats_floor_misses_incumbent_refines(self) -> None:
        # Better than bare model but worse than incumbent (which in
        # first-promotion is usually v0 / a freshly-built incumbent).
        v = decide(_ginputs(candidate=0.5, incumbent=0.7, floor=0.3, first=True))
        assert v == "refine"

    def test_epsilon_widens_floor_margin_by_2x(self) -> None:
        """First-promotion uses ``+2*epsilon`` against the floor —
        candidate must beat it by twice the steady-state margin."""
        # With eps=0.1, 2*eps=0.2; floor=0.4 → required = 0.6 against floor.
        # candidate=0.55 clears incumbent+eps=0.5 but NOT floor+2eps=0.6.
        v = decide(
            _ginputs(candidate=0.55, incumbent=0.4, floor=0.4, first=True, eps=0.1)
        )
        assert v == "reject_floor"

        # candidate=0.65 clears both: floor+2eps=0.6 and incumbent+eps=0.5.
        v = decide(
            _ginputs(candidate=0.65, incumbent=0.4, floor=0.4, first=True, eps=0.1)
        )
        assert v == "promote"


class TestFirstPromotionNoFloor:
    """First-promotion but the harness didn't produce a floor arm result
    (edge case — should not happen in production but is_first_promotion
    semantics must degrade safely)."""

    def test_falls_through_to_incumbent_stage(self) -> None:
        v = decide(_ginputs(candidate=0.7, incumbent=0.5, floor=None, first=True))
        assert v == "promote"

    def test_misses_incumbent_refines(self) -> None:
        v = decide(_ginputs(candidate=0.3, incumbent=0.5, floor=None, first=True))
        assert v == "refine"


class TestSteadyStateNoFloor:
    """Resource has already promoted at least once; floor is skipped."""

    def test_beats_incumbent_promotes(self) -> None:
        v = decide(_ginputs(candidate=0.8, incumbent=0.6, floor=None, first=False))
        assert v == "promote"

    def test_equals_incumbent_promotes_at_zero_epsilon(self) -> None:
        # Preserves Phase A pre-refinement semantics (``>=``).  Tighten
        # via ε>0 if ties become a problem; Phase B replaces with
        # bootstrap CI on win rate.
        v = decide(_ginputs(candidate=0.5, incumbent=0.5, floor=None, first=False))
        assert v == "promote"

    def test_below_incumbent_refines(self) -> None:
        v = decide(_ginputs(candidate=0.4, incumbent=0.6, floor=None, first=False))
        assert v == "refine"

    def test_epsilon_widens_incumbent_margin(self) -> None:
        # eps=0.05 → required = 0.65; candidate=0.62 misses.
        v = decide(
            _ginputs(candidate=0.62, incumbent=0.6, floor=None, first=False, eps=0.05)
        )
        assert v == "refine"

        # candidate=0.66 clears.
        v = decide(
            _ginputs(candidate=0.66, incumbent=0.6, floor=None, first=False, eps=0.05)
        )
        assert v == "promote"


class TestSteadyStateWithFloor:
    """Defensive: floor data present but is_first_promotion=False.
    The gate must skip the floor stage entirely (we never re-run it
    in steady state, but a stale on-disk eval-results.json might still
    carry one)."""

    def test_floor_ignored_when_not_first(self) -> None:
        # Candidate is below the floor — but is_first_promotion=False,
        # so the floor stage doesn't fire.  Verdict driven entirely by
        # incumbent stage.
        v = decide(
            _ginputs(candidate=0.7, incumbent=0.5, floor=0.9, first=False)
        )
        assert v == "promote"


class TestIsFirstPromotionHelper:
    def test_zero_means_first(self) -> None:
        assert is_first_promotion(0) is True

    def test_positive_means_not_first(self) -> None:
        assert is_first_promotion(1) is False
        assert is_first_promotion(7) is False


@pytest.mark.parametrize(
    "candidate,incumbent,floor,first,eps,expected",
    [
        # (candidate, incumbent, floor, is_first, epsilon, expected verdict)
        # The headline matrix — first-promotion gauntlet
        (1.0, 0.0, 0.0, True, 0.0, "promote"),
        # candidate==floor==incumbent at ε=0 promotes — Phase A `>=` semantics
        (0.0, 0.0, 0.0, True, 0.0, "promote"),
        (0.5, 1.0, 0.4, True, 0.0, "refine"),
        # Steady-state matrix
        (1.0, 0.5, None, False, 0.0, "promote"),
        (0.5, 1.0, None, False, 0.0, "refine"),
        # ε behaviour
        (0.55, 0.5, None, False, 0.05, "promote"),
        (0.54, 0.5, None, False, 0.05, "refine"),
    ],
)
def test_verdict_matrix(
    candidate: float,
    incumbent: float,
    floor: float | None,
    first: bool,
    eps: float,
    expected: Verdict,
) -> None:
    """Parametrized matrix — keep concrete numbers grep-able from the
    spec, so when the gate semantics shift in Phase B we can update one
    table instead of N test bodies."""
    assert (
        decide(
            _ginputs(
                candidate=candidate,
                incumbent=incumbent,
                floor=floor,
                first=first,
                eps=eps,
            )
        )
        == expected
    )
