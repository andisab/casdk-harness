"""Phase A refinement 4.4 — pipeline tightening (3 small sub-fixes).

- :class:`TestEvalSuiteHashGuard` (4.4.a) — eval-suite.yaml hash
  captured at EVAL_DESIGN exit; mid-loop mutation triggers a hard
  abort in EXECUTION_EVAL.
- :class:`TestStagnationEarlyStop` (4.4.b) — Δpass-rate < min_gain
  between consecutive feedback rounds escalates to VALIDATE.
- :class:`TestHeldOutUsageSidecar` (4.4.c) — held-out scenarios that
  participate in a decision get their ``uses`` and ``first_used_at``
  recorded in a sidecar file (``eval/held-out-usage.json``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.optimization._orchestrator_helpers import eval_suite_sha256
from harness.optimization._orchestrator_phases.execution_eval import (
    _record_held_out_usage,
    _resolve_min_gain,
    _round_mean_candidate_pass_rate,
)
from harness.optimization.eval_harness.models import (
    ArmResults,
    EvalResults,
    ScenarioResult,
)
from harness.progress import ResourceStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arm(decisive: int = 1, pass_rate: float = 1.0) -> ArmResults:
    return ArmResults(
        arm="baseline",
        trials=[],
        decisive=decisive,
        pass_rate=pass_rate,
        pass_at_k=pass_rate,
        pass_caret_k=pass_rate,
        avg_score=pass_rate,
    )


def _eval_results(
    *,
    candidate_pass_rate: float = 0.5,
    held_out_ids: list[str] | None = None,
    decisive_both: bool = True,
) -> EvalResults:
    """Minimal EvalResults with the fields _record_held_out_usage cares about."""
    held_out_ids = held_out_ids or []
    scenarios = [
        ScenarioResult(
            scenario_id=sid,
            level="unit",
            held_out=True,
            tags=[],
            difficulty=None,
            baseline=_arm(decisive=1 if decisive_both else 0),
            candidate=_arm(decisive=1 if decisive_both else 0),
            outcome="candidate_win",
        )
        for sid in held_out_ids
    ]
    return EvalResults(
        suite_path="eval-suite.yaml",
        baseline_resource="r-v0.md",
        candidate_resource="r-v1.md",
        timestamp="2026-05-15T00:00:00Z",
        scenarios=scenarios,
        win_rate=0.5,
        baseline_pass_rate=0.5,
        candidate_pass_rate=candidate_pass_rate,
        no_decision_rate=0.0,
        held_out=None,
        by_level={},
        by_tag={},
        total_tokens=0,
    )


def _res(path: str = "agents/x.md") -> ResourceStatus:
    return ResourceStatus(path=path, resource_type="agent", version=1)


# ---------------------------------------------------------------------------
# 4.4.a — eval-suite hash guard
# ---------------------------------------------------------------------------


class TestEvalSuiteHashGuard:
    def test_hash_deterministic(self, tmp_path: Path) -> None:
        p = tmp_path / "eval-suite.yaml"
        p.write_text("version: 1.0\nscenarios: []\n", encoding="utf-8")
        h1 = eval_suite_sha256(p)
        h2 = eval_suite_sha256(p)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_changes_on_content_edit(self, tmp_path: Path) -> None:
        p = tmp_path / "eval-suite.yaml"
        p.write_text("scenarios: []\n", encoding="utf-8")
        h1 = eval_suite_sha256(p)
        p.write_text("scenarios: [a]\n", encoding="utf-8")
        h2 = eval_suite_sha256(p)
        assert h1 != h2

    def test_crlf_normalized(self, tmp_path: Path) -> None:
        """Line-ending changes (CRLF vs LF) must not trigger a mismatch."""
        p = tmp_path / "eval-suite.yaml"
        p.write_bytes(b"scenarios: []\n")
        h_lf = eval_suite_sha256(p)
        p.write_bytes(b"scenarios: []\r\n")
        h_crlf = eval_suite_sha256(p)
        assert h_lf == h_crlf

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert eval_suite_sha256(tmp_path / "missing.yaml") == ""


# ---------------------------------------------------------------------------
# 4.4.b — stagnation early-stop
# ---------------------------------------------------------------------------


class TestStagnationEarlyStop:
    def test_round_mean_across_resources(self) -> None:
        results = [
            (_res("a.md"), _eval_results(candidate_pass_rate=0.6)),
            (_res("b.md"), _eval_results(candidate_pass_rate=0.4)),
            (_res("c.md"), _eval_results(candidate_pass_rate=0.5)),
        ]
        assert _round_mean_candidate_pass_rate(results) == pytest.approx(0.5)

    def test_empty_results_zero(self) -> None:
        assert _round_mean_candidate_pass_rate([]) == 0.0

    def test_min_gain_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CGF_MIN_GAIN_PER_ROUND", raising=False)
        assert _resolve_min_gain() == 0.02

    def test_min_gain_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_MIN_GAIN_PER_ROUND", "0.05")
        assert _resolve_min_gain() == 0.05

    def test_min_gain_zero_disables_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting CGF_MIN_GAIN_PER_ROUND=0 means any non-regression
        survives — any Δ ≥ 0 lets the loop continue."""
        monkeypatch.setenv("CGF_MIN_GAIN_PER_ROUND", "0.0")
        assert _resolve_min_gain() == 0.0

    def test_min_gain_negative_clamped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_MIN_GAIN_PER_ROUND", "-0.1")
        assert _resolve_min_gain() == 0.0

    def test_min_gain_invalid_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_MIN_GAIN_PER_ROUND", "not_a_number")
        assert _resolve_min_gain() == 0.02


# ---------------------------------------------------------------------------
# 4.4.c — held-out usage sidecar
# ---------------------------------------------------------------------------


class TestHeldOutUsageSidecar:
    def test_increments_uses_on_decisive_scenario(self, tmp_path: Path) -> None:
        results = [
            (_res(), _eval_results(held_out_ids=["s1", "s2"])),
        ]
        _record_held_out_usage(tmp_path, results)
        usage = json.loads(
            (tmp_path / "eval" / "held-out-usage.json").read_text()
        )
        assert usage["s1"]["uses"] == 1
        assert usage["s2"]["uses"] == 1
        assert usage["s1"]["first_used_at"] is not None

    def test_increments_across_invocations(self, tmp_path: Path) -> None:
        """Re-running with the same scenario should bump uses, not reset."""
        results = [(_res(), _eval_results(held_out_ids=["s1"]))]
        _record_held_out_usage(tmp_path, results)
        _record_held_out_usage(tmp_path, results)
        _record_held_out_usage(tmp_path, results)
        usage = json.loads(
            (tmp_path / "eval" / "held-out-usage.json").read_text()
        )
        assert usage["s1"]["uses"] == 3

    def test_first_used_at_set_once(self, tmp_path: Path) -> None:
        """first_used_at locks on the first contact and stays."""
        results = [(_res(), _eval_results(held_out_ids=["s1"]))]
        _record_held_out_usage(tmp_path, results)
        first_ts = json.loads(
            (tmp_path / "eval" / "held-out-usage.json").read_text()
        )["s1"]["first_used_at"]
        _record_held_out_usage(tmp_path, results)
        second_ts = json.loads(
            (tmp_path / "eval" / "held-out-usage.json").read_text()
        )["s1"]["first_used_at"]
        assert first_ts == second_ts

    def test_non_held_out_scenarios_skipped(self, tmp_path: Path) -> None:
        """Only ``held_out=True`` scenarios go into the sidecar."""
        # Build a result with a non-held-out scenario.
        sr = ScenarioResult(
            scenario_id="public",
            level="unit",
            held_out=False,  # the point
            tags=[],
            difficulty=None,
            baseline=_arm(),
            candidate=_arm(),
            outcome="candidate_win",
        )
        r = EvalResults(
            suite_path="x", baseline_resource="b", candidate_resource="c",
            timestamp="t", scenarios=[sr],
            win_rate=1.0, baseline_pass_rate=1.0, candidate_pass_rate=1.0,
            no_decision_rate=0.0, held_out=None, by_level={}, by_tag={},
            total_tokens=0,
        )
        _record_held_out_usage(tmp_path, [(_res(), r)])
        usage_path = tmp_path / "eval" / "held-out-usage.json"
        # Empty file is fine (no held-out scenarios to track).
        if usage_path.exists():
            usage = json.loads(usage_path.read_text())
            assert "public" not in usage

    def test_no_decision_scenarios_skipped(self, tmp_path: Path) -> None:
        """When neither arm was decisive, the scenario didn't actually
        participate in a verdict — don't burn it."""
        results = [
            (_res(), _eval_results(held_out_ids=["s1"], decisive_both=False)),
        ]
        _record_held_out_usage(tmp_path, results)
        usage_path = tmp_path / "eval" / "held-out-usage.json"
        if usage_path.exists():
            usage = json.loads(usage_path.read_text())
            assert "s1" not in usage

    def test_empty_results_no_file(self, tmp_path: Path) -> None:
        _record_held_out_usage(tmp_path, [])
        assert not (tmp_path / "eval" / "held-out-usage.json").exists()
