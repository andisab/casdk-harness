"""Phase A refinement 4.3 — cost-per-success two-gate.

Three layers of test:

- :class:`TestCostPerSuccess` — aggregate math (failed-trial penalty,
  exempt-scenario exclusion, zero-success None).
- :class:`TestGateDecideCostStage` — verdict when cost stage interacts
  with quality stages.
- :class:`TestEnvKnob` — ``CGF_TOKEN_REGRESSION_TOLERANCE`` parsing.
"""

from __future__ import annotations

import pytest

from harness.optimization._orchestrator_phases.execution_eval import (
    _resolve_cost_tolerance,
)
from harness.optimization.eval_harness.aggregate import cost_per_success
from harness.optimization.eval_harness.models import (
    ArmResults,
    ScenarioResult,
    TrialResult,
)
from harness.optimization.gating import GateInputs, decide
from harness.optimization.graders.transcript import AgentTranscript

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial(*, passed: bool, cost: float, no_decision: bool = False, error: str = "") -> TrialResult:
    """Build a TrialResult with a transcript carrying ``cost`` USD."""
    return TrialResult(
        arm="candidate",
        trial_index=0,
        transcript=AgentTranscript(total_cost_usd=cost),
        grader_results=[],
        passed=passed,
        no_decision=no_decision,
        error=error,
    )


def _scenario(
    *,
    sid: str,
    baseline_trials: list[TrialResult],
    candidate_trials: list[TrialResult],
) -> ScenarioResult:
    """Build a minimal ScenarioResult with the given per-arm trial lists.

    ArmResults aggregate fields aren't used by ``cost_per_success`` —
    that function reads ``arm.trials`` directly — so we leave them at
    sensible defaults.
    """
    return ScenarioResult(
        scenario_id=sid,
        level="unit",
        held_out=False,
        tags=[],
        difficulty=None,
        baseline=ArmResults(
            arm="baseline",
            trials=baseline_trials,
            decisive=len(baseline_trials),
            pass_rate=0.0,
            pass_at_k=0.0,
            pass_caret_k=0.0,
            avg_score=0.0,
        ),
        candidate=ArmResults(
            arm="candidate",
            trials=candidate_trials,
            decisive=len(candidate_trials),
            pass_rate=0.0,
            pass_at_k=0.0,
            pass_caret_k=0.0,
            avg_score=0.0,
        ),
        outcome="candidate_win",
    )


# ---------------------------------------------------------------------------
# TestCostPerSuccess — aggregate math
# ---------------------------------------------------------------------------


class TestCostPerSuccess:
    def test_single_passing_trial(self) -> None:
        s = _scenario(
            sid="s1",
            baseline_trials=[_trial(passed=True, cost=0.10)],
            candidate_trials=[_trial(passed=True, cost=0.05)],
        )
        assert cost_per_success([s], "candidate") == pytest.approx(0.05)
        assert cost_per_success([s], "baseline") == pytest.approx(0.10)

    def test_failed_trials_count_zero_successes(self) -> None:
        """Brittle candidates that spend tokens without winning should
        get a HIGHER cost_per_success — failures still consume cost."""
        s = _scenario(
            sid="s1",
            baseline_trials=[_trial(passed=True, cost=0.10)],
            candidate_trials=[
                _trial(passed=True, cost=0.20),
                _trial(passed=False, cost=0.30),  # failure, still costs
            ],
        )
        # 1 success, total cost 0.50 → cps = 0.50
        assert cost_per_success([s], "candidate") == pytest.approx(0.50)

    def test_zero_successes_returns_none(self) -> None:
        s = _scenario(
            sid="s1",
            baseline_trials=[_trial(passed=False, cost=0.10)],
            candidate_trials=[_trial(passed=False, cost=0.20)],
        )
        assert cost_per_success([s], "candidate") is None
        assert cost_per_success([s], "baseline") is None

    def test_no_decision_does_not_count_as_success(self) -> None:
        s = _scenario(
            sid="s1",
            baseline_trials=[_trial(passed=True, cost=0.10)],
            candidate_trials=[
                _trial(passed=True, cost=0.10, no_decision=True),
            ],
        )
        # Despite passed=True, no_decision excludes from successes.
        assert cost_per_success([s], "candidate") is None

    def test_error_does_not_count_as_success(self) -> None:
        s = _scenario(
            sid="s1",
            baseline_trials=[_trial(passed=True, cost=0.10)],
            candidate_trials=[
                _trial(passed=True, cost=0.10, error="timeout"),
            ],
        )
        assert cost_per_success([s], "candidate") is None

    def test_exempt_scenarios_excluded_entirely(self) -> None:
        """Exempt scenarios contribute neither cost nor successes —
        an exempt scenario costing 10× should not affect the per-arm
        aggregate at all."""
        s_normal = _scenario(
            sid="normal",
            baseline_trials=[_trial(passed=True, cost=0.10)],
            candidate_trials=[_trial(passed=True, cost=0.05)],
        )
        s_exempt = _scenario(
            sid="exempt",
            baseline_trials=[_trial(passed=True, cost=10.00)],  # absurd cost
            candidate_trials=[_trial(passed=True, cost=20.00)],
        )
        cps = cost_per_success(
            [s_normal, s_exempt], "candidate", exempt_scenario_ids={"exempt"}
        )
        # Only the normal scenario contributes: cost 0.05 / 1 success.
        assert cps == pytest.approx(0.05)

    def test_floor_arm_included_when_requested(self) -> None:
        """Floor arm trials live on ``scenario.floor`` (optional).
        ``cost_per_success(arm="floor")`` aggregates them when set."""
        sr = ScenarioResult(
            scenario_id="s1",
            level="unit",
            held_out=False,
            tags=[],
            difficulty=None,
            baseline=ArmResults(
                arm="baseline", trials=[], decisive=0,
                pass_rate=0.0, pass_at_k=0.0, pass_caret_k=0.0, avg_score=0.0,
            ),
            candidate=ArmResults(
                arm="candidate", trials=[], decisive=0,
                pass_rate=0.0, pass_at_k=0.0, pass_caret_k=0.0, avg_score=0.0,
            ),
            outcome="no_decision",
            floor=ArmResults(
                arm="floor",
                trials=[_trial(passed=True, cost=0.03)],
                decisive=1, pass_rate=1.0, pass_at_k=1.0, pass_caret_k=1.0,
                avg_score=1.0,
            ),
        )
        assert cost_per_success([sr], "floor") == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# TestGateDecideCostStage — verdict matrix with cost
# ---------------------------------------------------------------------------


def _ginputs(
    *,
    quality_passes: bool = True,
    candidate_cps: float | None,
    incumbent_cps: float | None,
    tau: float = 0.10,
    candidate_pass: float | None = None,
    incumbent_pass: float | None = None,
) -> GateInputs:
    """Quality stays at parity (1.0 == 1.0) by default so quality_delta=0
    and the I15 quality-bonus contributes nothing — letting these tests
    exercise the cost stage in isolation.  Older tests assumed quality_delta=0
    implicitly; after I15 we make it explicit.  Pass ``quality_passes=False``
    to force a quality-stage failure, or override ``candidate_pass`` /
    ``incumbent_pass`` to test the quality-bonus behaviour.
    """
    cp = candidate_pass if candidate_pass is not None else (
        1.0 if quality_passes else 0.0
    )
    ip = incumbent_pass if incumbent_pass is not None else 1.0
    return GateInputs(
        candidate_pass_rate=cp,
        incumbent_pass_rate=ip,
        floor_pass_rate=None,
        is_first_promotion=False,
        epsilon=0.0,
        candidate_cost_per_success=candidate_cps,
        incumbent_cost_per_success=incumbent_cps,
        tau=tau,
    )


class TestGateDecideCostStage:
    def test_cost_within_tolerance_promotes(self) -> None:
        # incumbent=$1, tau=0.10 → ceiling=$1.10; candidate=$1.05 passes.
        v = decide(_ginputs(candidate_cps=1.05, incumbent_cps=1.0))
        assert v == "promote"

    def test_cost_at_tolerance_boundary_promotes(self) -> None:
        # Boundary is inclusive: candidate == incumbent * (1+τ) passes.
        v = decide(_ginputs(candidate_cps=1.10, incumbent_cps=1.0))
        assert v == "promote"

    def test_cost_above_tolerance_rejects(self) -> None:
        v = decide(_ginputs(candidate_cps=1.20, incumbent_cps=1.0))
        assert v == "reject_cost"

    def test_candidate_cheaper_promotes(self) -> None:
        # Candidate is half the cost — obviously promotes.
        v = decide(_ginputs(candidate_cps=0.50, incumbent_cps=1.0))
        assert v == "promote"

    def test_incumbent_none_auto_passes_cost(self) -> None:
        """No baseline cost signal → cost stage auto-passes (no regression
        to detect)."""
        v = decide(_ginputs(candidate_cps=99.0, incumbent_cps=None))
        assert v == "promote"

    def test_candidate_none_auto_passes_cost(self) -> None:
        """Candidate had zero successes → cost stage auto-passes (quality
        stage would've already failed, but the gate is defensive)."""
        v = decide(
            _ginputs(quality_passes=True, candidate_cps=None, incumbent_cps=1.0)
        )
        assert v == "promote"

    def test_both_none_auto_passes(self) -> None:
        v = decide(_ginputs(candidate_cps=None, incumbent_cps=None))
        assert v == "promote"

    def test_quality_fails_short_circuits_before_cost(self) -> None:
        """If quality fails, we never reach the cost stage — verdict is
        'refine', not 'reject_cost', even if cost would have failed too."""
        v = decide(
            _ginputs(quality_passes=False, candidate_cps=99.0, incumbent_cps=1.0)
        )
        assert v == "refine"

    def test_tau_zero_no_headroom(self) -> None:
        """τ=0 means any cost regression rejects."""
        v = decide(_ginputs(candidate_cps=1.001, incumbent_cps=1.0, tau=0.0))
        assert v == "reject_cost"
        v = decide(_ginputs(candidate_cps=1.0, incumbent_cps=1.0, tau=0.0))
        assert v == "promote"

    def test_tau_high_lets_everything_through(self) -> None:
        """τ=1.0 means candidate can double the cost and still pass."""
        v = decide(_ginputs(candidate_cps=1.99, incumbent_cps=1.0, tau=1.0))
        assert v == "promote"
        v = decide(_ginputs(candidate_cps=2.01, incumbent_cps=1.0, tau=1.0))
        assert v == "reject_cost"


# ---------------------------------------------------------------------------
# TestEnvKnob — CGF_TOKEN_REGRESSION_TOLERANCE
# ---------------------------------------------------------------------------


class TestEnvKnob:
    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CGF_TOKEN_REGRESSION_TOLERANCE", raising=False)
        assert _resolve_cost_tolerance() == 0.10

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_TOKEN_REGRESSION_TOLERANCE", "0.25")
        assert _resolve_cost_tolerance() == 0.25

    def test_zero_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_TOKEN_REGRESSION_TOLERANCE", "0.0")
        assert _resolve_cost_tolerance() == 0.0

    def test_invalid_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_TOKEN_REGRESSION_TOLERANCE", "not_a_number")
        assert _resolve_cost_tolerance() == 0.10

    def test_negative_clamped_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative tolerance would mean "candidate must be CHEAPER than
        baseline" which is a different policy.  Clamp to 0 (= "no
        regression allowed") for safety."""
        monkeypatch.setenv("CGF_TOKEN_REGRESSION_TOLERANCE", "-0.5")
        assert _resolve_cost_tolerance() == 0.0


# ---------------------------------------------------------------------------
# TestQualityScaledCostTolerance — I15
#
# When quality improves over the incumbent, ``effective_cost_tolerance``
# scales ``τ`` upward so cost-per-success regressions proportional to the
# quality gain still promote.  Quality drops never tighten the gate
# (max(0, …) clamp); the quality-stage check has already handled them.
# ---------------------------------------------------------------------------


class TestQualityScaledCostTolerance:
    def test_quality_flat_uses_base_tau(self) -> None:
        """Δquality = 0 → effective τ == base τ (no I15 effect)."""
        from harness.optimization.gating import effective_cost_tolerance

        assert effective_cost_tolerance(
            base_tau=0.10, quality_delta=0.0, bonus_factor=1.0
        ) == 0.10

    def test_quality_drop_clamped_to_base_tau(self) -> None:
        """Δquality < 0 must NOT tighten the cost gate.

        Quality regression is handled by the incumbent stage upstream;
        the cost gate's job is "cost regression on equal/better quality."
        """
        from harness.optimization.gating import effective_cost_tolerance

        assert effective_cost_tolerance(
            base_tau=0.10, quality_delta=-0.20, bonus_factor=1.0
        ) == 0.10

    def test_small_quality_gain_grants_proportional_bonus(self) -> None:
        """+13pp quality → +13pp τ headroom (with bonus_factor=1.0)."""
        from harness.optimization.gating import effective_cost_tolerance

        tau = effective_cost_tolerance(
            base_tau=0.10, quality_delta=0.13, bonus_factor=1.0
        )
        assert abs(tau - 0.23) < 1e-9

    def test_large_quality_gain_hits_bonus_cap(self) -> None:
        """+60pp quality with cap=0.5 → bonus clamped at 0.5; τ_eff = 0.6."""
        from harness.optimization.gating import effective_cost_tolerance

        tau = effective_cost_tolerance(
            base_tau=0.10,
            quality_delta=0.60,
            bonus_factor=1.0,
        )
        assert abs(tau - 0.60) < 1e-9

    def test_bonus_factor_two_doubles_per_pp_credit(self) -> None:
        """bonus_factor=2.0 → 2pp τ per pp quality."""
        from harness.optimization.gating import effective_cost_tolerance

        tau = effective_cost_tolerance(
            base_tau=0.10, quality_delta=0.10, bonus_factor=2.0
        )
        assert abs(tau - 0.30) < 1e-9

    def test_bonus_factor_zero_disables_scaling(self) -> None:
        """bonus_factor=0 reverts to pure Phase A.4.3 behaviour."""
        from harness.optimization.gating import effective_cost_tolerance

        for delta in [-0.5, 0.0, 0.3, 1.0]:
            assert effective_cost_tolerance(
                base_tau=0.10, quality_delta=delta, bonus_factor=0.0
            ) == 0.10

    def test_decide_promotes_when_quality_win_offsets_cost_growth(self) -> None:
        """Real I15 scenario: +13pp quality, +16% cps growth.

        Pre-I15: refine (cost gate ceiling = 1.10, candidate at 1.16
        exceeds → reject_cost).  Post-I15: effective τ = 0.23, ceiling
        = 1.23, candidate at 1.16 passes → promote.
        """
        v = decide(_ginputs(
            incumbent_pass=0.67,
            candidate_pass=0.80,    # +0.13 → +0.13 τ bonus
            candidate_cps=1.16,
            incumbent_cps=1.0,
            tau=0.10,
        ))
        assert v == "promote"

    def test_decide_rejects_when_cost_growth_exceeds_quality_credit(self) -> None:
        """Quality +5pp, cost +25% → still rejects (5pp credit not enough)."""
        v = decide(_ginputs(
            incumbent_pass=0.67,
            candidate_pass=0.72,    # +0.05 → +0.05 τ bonus
            candidate_cps=1.25,
            incumbent_cps=1.0,
            tau=0.10,
        ))
        # Effective τ = 0.15 → ceiling = 1.15.  Candidate at 1.25 > 1.15.
        assert v == "reject_cost"


# ---------------------------------------------------------------------------
# TestCostQualityBonusEnv — CGF_COST_QUALITY_BONUS parsing
# ---------------------------------------------------------------------------


class TestCostQualityBonusEnv:
    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from harness.optimization.gating import (
            DEFAULT_COST_QUALITY_BONUS,
            _resolve_cost_quality_bonus,
        )

        monkeypatch.delenv("CGF_COST_QUALITY_BONUS", raising=False)
        assert _resolve_cost_quality_bonus() == DEFAULT_COST_QUALITY_BONUS == 1.0

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from harness.optimization.gating import _resolve_cost_quality_bonus

        monkeypatch.setenv("CGF_COST_QUALITY_BONUS", "2.5")
        assert _resolve_cost_quality_bonus() == 2.5

    def test_zero_disables_scaling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from harness.optimization.gating import _resolve_cost_quality_bonus

        monkeypatch.setenv("CGF_COST_QUALITY_BONUS", "0")
        assert _resolve_cost_quality_bonus() == 0.0

    def test_negative_clamped_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative would PUNISH quality gains with tighter cost gate —
        nonsensical; clamp to 0 (revert to base τ behaviour)."""
        from harness.optimization.gating import _resolve_cost_quality_bonus

        monkeypatch.setenv("CGF_COST_QUALITY_BONUS", "-1.0")
        assert _resolve_cost_quality_bonus() == 0.0

    def test_invalid_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from harness.optimization.gating import (
            DEFAULT_COST_QUALITY_BONUS,
            _resolve_cost_quality_bonus,
        )

        monkeypatch.setenv("CGF_COST_QUALITY_BONUS", "abc")
        assert _resolve_cost_quality_bonus() == DEFAULT_COST_QUALITY_BONUS
