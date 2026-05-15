"""Aggregation math for eval results (Phase A.4).

Three layers of aggregation:

- :func:`aggregate_arm` — collapse trials of one arm into :class:`ArmResults`
- :func:`compare_arms` — pick the per-scenario winner given both arms
- :func:`aggregate_subset` — roll a list of scenarios into :class:`SubsetStats`

The core invariant is that *no_decision never counts against the
candidate*.  Trials that ended in no_decision (any grader returned
no_decision, or the runtime errored) are excluded from ``decisive``.
A scenario with zero decisive trials on either arm is a per-scenario
no_decision; the gate treats that as a tie.

Phase B will replace the simple-threshold compare with a bootstrap CI;
the API of these functions stays compatible.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from harness.optimization.eval_harness.models import (
    Arm,
    ArmResults,
    ScenarioOutcome,
    ScenarioResult,
    SubsetStats,
    TrialResult,
)


def aggregate_arm(arm: Arm, trials: list[TrialResult]) -> ArmResults:
    """Compute per-arm metrics for one scenario.

    Decisive trials are those where ``no_decision`` is False AND
    ``error`` is empty.  Pass-rate / pass@k / pass^k are computed only
    over decisive trials.  Avg-score is the mean of (mean grader score
    per trial) across decisive trials, or 0.0 when none exist.
    """
    if not trials:
        return ArmResults(
            arm=arm,
            trials=[],
            decisive=0,
            pass_rate=0.0,
            pass_at_k=0.0,
            pass_caret_k=0.0,
            avg_score=0.0,
        )

    decisive_trials = [t for t in trials if not t.no_decision and not t.error]
    decisive_count = len(decisive_trials)

    if decisive_count == 0:
        return ArmResults(
            arm=arm,
            trials=list(trials),
            decisive=0,
            pass_rate=0.0,
            pass_at_k=0.0,
            pass_caret_k=0.0,
            avg_score=0.0,
        )

    passing = sum(1 for t in decisive_trials if t.passed)
    pass_rate = passing / decisive_count
    pass_at_k = 1.0 if passing >= 1 else 0.0
    pass_caret_k = 1.0 if passing == decisive_count else 0.0

    # avg_score: per-trial = mean of grader scores; arm = mean over trials.
    per_trial_means: list[float] = []
    for t in decisive_trials:
        if t.grader_results:
            per_trial_means.append(
                sum(g.score for g in t.grader_results) / len(t.grader_results)
            )
        else:
            per_trial_means.append(0.0)
    avg_score = sum(per_trial_means) / len(per_trial_means)

    return ArmResults(
        arm=arm,
        trials=list(trials),
        decisive=decisive_count,
        pass_rate=pass_rate,
        pass_at_k=pass_at_k,
        pass_caret_k=pass_caret_k,
        avg_score=avg_score,
    )


def compare_arms(
    baseline: ArmResults,
    candidate: ArmResults,
    epsilon: float = 0.0,
) -> ScenarioOutcome:
    """Decide the per-scenario winner given both arms' results.

    Phase A simple threshold: candidate wins if ``candidate.pass_rate >
    baseline.pass_rate + epsilon``.  Either arm with zero decisive
    trials → no_decision (we can't tell what the candidate would do
    against an unanswered baseline).

    Phase B replaces this with bootstrap CI on win rate.
    """
    if baseline.decisive == 0 or candidate.decisive == 0:
        return "no_decision"
    if candidate.pass_rate > baseline.pass_rate + epsilon:
        return "candidate_win"
    if baseline.pass_rate > candidate.pass_rate + epsilon:
        return "baseline_win"
    return "tie"


def aggregate_subset(scenarios: Iterable[ScenarioResult]) -> SubsetStats:
    """Roll up an arbitrary subset of scenarios into a single stats record.

    Win-rate is the fraction of scenarios with ``outcome == 'candidate_win'``.
    Pass-rate per arm is the *mean of per-scenario per-arm pass_rate* —
    which weights every scenario equally regardless of trial counts.
    """
    scenarios = list(scenarios)
    count = len(scenarios)
    if count == 0:
        return SubsetStats(
            count=0,
            win_rate=0.0,
            baseline_pass_rate=0.0,
            candidate_pass_rate=0.0,
            no_decision_rate=0.0,
        )

    wins = sum(1 for s in scenarios if s.outcome == "candidate_win")
    no_decisions = sum(1 for s in scenarios if s.outcome == "no_decision")
    baseline_pass = sum(s.baseline.pass_rate for s in scenarios) / count
    candidate_pass = sum(s.candidate.pass_rate for s in scenarios) / count

    return SubsetStats(
        count=count,
        win_rate=wins / count,
        baseline_pass_rate=baseline_pass,
        candidate_pass_rate=candidate_pass,
        no_decision_rate=no_decisions / count,
    )


def group_by_level(
    scenarios: Iterable[ScenarioResult],
) -> dict[str, SubsetStats]:
    """Bucket scenarios by ``level`` (unit/trajectory/e2e) and roll each up."""
    buckets: dict[str, list[ScenarioResult]] = defaultdict(list)
    for s in scenarios:
        buckets[s.level].append(s)
    return {level: aggregate_subset(items) for level, items in buckets.items()}


def group_by_tag(
    scenarios: Iterable[ScenarioResult],
) -> dict[str, SubsetStats]:
    """Bucket scenarios by tag (a scenario can appear in multiple buckets)."""
    buckets: dict[str, list[ScenarioResult]] = defaultdict(list)
    for s in scenarios:
        for tag in s.tags:
            buckets[tag].append(s)
    return {tag: aggregate_subset(items) for tag, items in buckets.items()}


# ---------------------------------------------------------------------------
# Phase A refinement 4.3 — cost-per-success
# ---------------------------------------------------------------------------


def cost_per_success(
    scenarios: Iterable[ScenarioResult],
    arm: Arm,
    exempt_scenario_ids: set[str] | None = None,
) -> float | None:
    """Compute cost-per-success for one arm across a set of scenarios.

    ``cost_per_success = total_cost_usd / successful_completions`` where
    *successful completions* are decisive trials that passed (per the
    same definition as :func:`aggregate_arm`).  Failed trials count
    zero successes — this correctly penalises brittle candidates that
    spend tokens without producing wins (research § 3.2).

    Returns ``None`` when the arm has zero successes; callers treat
    None as "no signal" and let the cost gate auto-pass.

    Scenarios in ``exempt_scenario_ids`` are excluded entirely — both
    their cost and their successes (Phase A refinement 4.3
    cost_gate_exempt opt-out).  Default empty set = no exemptions.
    """
    exempt = exempt_scenario_ids or set()
    total_cost = 0.0
    successes = 0
    for sr in scenarios:
        if sr.scenario_id in exempt:
            continue
        arm_results = _arm_of(sr, arm)
        if arm_results is None:
            continue
        for trial in arm_results.trials:
            total_cost += trial.transcript.total_cost_usd
            # Successful = decisive AND passed (matches aggregate_arm's
            # ``passing`` count semantics, not pass_rate which divides
            # by decisive count).
            if trial.passed and not trial.no_decision and not trial.error:
                successes += 1
    if successes == 0:
        return None
    return total_cost / successes


def _arm_of(scenario: ScenarioResult, arm: Arm) -> ArmResults | None:
    """Pick the named arm off a ScenarioResult, or None if absent.

    Floor arm is optional; baseline / candidate are always populated.
    """
    if arm == "baseline":
        return scenario.baseline
    if arm == "candidate":
        return scenario.candidate
    if arm == "floor":
        return scenario.floor
    return None
