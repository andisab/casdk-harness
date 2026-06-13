"""Tests for the empirical scenario-discrimination audit (Phase A.5 A2).

Covers the per-scenario classification (candidate vs bare-model floor) and
the report aggregation (flip rate, non-discriminating IDs, meets_target),
including the float-partial-credit and indeterminate edge cases.
"""

from __future__ import annotations

from types import SimpleNamespace

from harness.optimization.eval_harness.discrimination import (
    DEAD,
    DISCRIMINATING,
    INDETERMINATE,
    INVERTED,
    SATURATED,
    analyze,
    classify,
)
from harness.optimization.eval_harness.models import ArmResults, ScenarioResult

# --- helpers ---------------------------------------------------------------


def _arm(pass_rate: float, *, decisive: int = 1, arm: str = "candidate") -> ArmResults:
    return ArmResults(
        arm=arm,  # type: ignore[arg-type]
        trials=[],
        decisive=decisive,
        pass_rate=pass_rate,
        pass_at_k=1.0 if pass_rate > 0 else 0.0,
        pass_caret_k=1.0 if pass_rate >= 1.0 else 0.0,
        avg_score=pass_rate,
    )


def _sr(
    sid: str,
    cand: float,
    floor: float | None,
    *,
    held_out: bool = False,
    cand_decisive: int = 1,
    floor_decisive: int = 1,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=sid,
        level="unit",
        held_out=held_out,
        tags=[],
        difficulty=None,
        baseline=_arm(0.0, arm="baseline"),
        candidate=_arm(cand, decisive=cand_decisive, arm="candidate"),
        outcome="tie",
        floor=(None if floor is None else _arm(floor, decisive=floor_decisive, arm="floor")),
    )


def _results(scenarios: list[ScenarioResult]):
    # analyze() only reads .scenarios.
    return SimpleNamespace(scenarios=scenarios)


# --- classify --------------------------------------------------------------


def test_classify_discriminating():
    assert classify(_arm(1.0), _arm(0.0)) == DISCRIMINATING


def test_classify_inverted():
    assert classify(_arm(0.0), _arm(1.0)) == INVERTED


def test_classify_saturated_both_pass():
    assert classify(_arm(1.0), _arm(1.0)) == SATURATED


def test_classify_dead_both_fail():
    assert classify(_arm(0.0), _arm(0.0)) == DEAD


def test_classify_partial_credit_discriminates():
    # 0.67 vs 0.33 separates the arms even though neither is a clean pass.
    assert classify(_arm(0.67), _arm(0.33)) == DISCRIMINATING


def test_classify_equal_midrange_is_saturated_at_half():
    assert classify(_arm(0.5), _arm(0.5)) == SATURATED
    assert classify(_arm(0.33), _arm(0.33)) == DEAD


def test_classify_indeterminate_when_no_floor():
    assert classify(_arm(1.0), None) == INDETERMINATE


def test_classify_indeterminate_when_arm_not_decisive():
    assert classify(_arm(1.0, decisive=0), _arm(0.0)) == INDETERMINATE
    assert classify(_arm(1.0), _arm(0.0, decisive=0)) == INDETERMINATE


# --- analyze: skip when no floor data --------------------------------------


def test_analyze_returns_none_without_floor_arm():
    results = _results([_sr("s1", 1.0, None), _sr("s2", 0.0, None)])
    assert analyze(results, resource_path="agents/x.md") is None


# --- analyze: counts, flip rate, target ------------------------------------


def test_analyze_counts_and_flip_rate():
    results = _results(
        [
            _sr("d1", 1.0, 0.0),    # discriminating
            _sr("sat", 1.0, 1.0),   # saturated
            _sr("dead", 0.0, 0.0),  # dead
            _sr("inv", 0.0, 1.0),   # inverted
            _sr("ind", 1.0, None),  # indeterminate (no floor on this one)
        ]
    )
    report = analyze(results, resource_path="agents/g.md", min_flip_rate=0.40)
    assert report is not None
    assert report.discriminating == 1
    assert report.saturated == 1
    assert report.dead == 1
    assert report.inverted == 1
    assert report.indeterminate == 1
    assert report.total == 5
    assert report.classifiable == 4  # excludes the indeterminate
    assert report.flip_rate == 0.25  # 1 / 4
    assert report.meets_target is False  # 0.25 < 0.40


def test_analyze_meets_target():
    results = _results([_sr("d1", 1.0, 0.0), _sr("d2", 1.0, 0.0), _sr("sat", 1.0, 1.0)])
    report = analyze(results, resource_path="skills/a/SKILL.md", min_flip_rate=0.40)
    assert report is not None
    assert report.classifiable == 3
    assert abs(report.flip_rate - (2 / 3)) < 1e-9
    assert report.meets_target is True


def test_analyze_non_discriminating_ids():
    results = _results([_sr("d1", 1.0, 0.0), _sr("sat", 1.0, 1.0), _sr("dead", 0.0, 0.0)])
    report = analyze(results, resource_path="agents/g.md")
    assert report is not None
    assert set(report.non_discriminating_ids) == {"sat", "dead"}


def test_analyze_all_saturated_flip_rate_zero():
    # The run-#8 pathology: every scenario saturated → flip_rate 0, fails target.
    results = _results([_sr(f"s{i}", 1.0, 1.0) for i in range(3)])
    report = analyze(results, resource_path="skills/aws-cli/SKILL.md")
    assert report is not None
    assert report.flip_rate == 0.0
    assert report.meets_target is False
    assert len(report.non_discriminating_ids) == 3


def test_analyze_classifiable_zero_does_not_divide_by_zero():
    # Floor present on one scenario (so analyze runs) but that scenario is
    # itself indeterminate (candidate not decisive) → classifiable 0.
    results = _results(
        [
            _sr("ind1", 1.0, 0.0, cand_decisive=0),  # candidate indeterminate
            _sr("ind2", 1.0, None),                  # no floor → indeterminate
        ]
    )
    report = analyze(results, resource_path="agents/g.md")
    assert report is not None
    assert report.classifiable == 0
    assert report.flip_rate == 0.0
    assert report.meets_target is False


def test_analyze_to_dict_shape_and_held_out_passthrough():
    results = _results([_sr("d1", 1.0, 0.0, held_out=True)])
    report = analyze(results, resource_path="agents/g.md", min_flip_rate=0.4)
    assert report is not None
    d = report.to_dict()
    assert d["resource_path"] == "agents/g.md"
    assert d["flip_rate"] == 1.0
    assert d["meets_target"] is True
    assert d["counts"][DISCRIMINATING] == 1
    assert d["scenarios"][0]["held_out"] is True
    assert d["scenarios"][0]["classification"] == DISCRIMINATING
