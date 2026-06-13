"""Empirical scenario-discrimination audit (Phase A.5 A2).

Reuses the per-scenario bare-model **floor** arm that the eval harness
already runs at first promotion (``ScenarioResult.floor``, today collapsed
into a single ``floor_pass_rate``) to answer the question run #8 and the
2026-05-26 mobile-dev run could not: *does each scenario actually separate
an optimized candidate from a bare model?*

A scenario is only useful if the two arms can score differently on it.
Per scenario we compare the candidate arm against the floor arm:

- ``discriminating`` — candidate scores higher than floor (healthy: the
  optimized resource beats the bare model).
- ``inverted``       — candidate scores *lower* than floor (the candidate
  is worse than a bare model here; a real signal, but about the candidate,
  not scenario quality).
- ``saturated``      — both pass equally (≥ 0.5): any reasonable resource
  passes, so it cannot discriminate (the tied-at-1.00 pathology).
- ``dead``           — both fail equally (< 0.5): even the candidate fails,
  so it cannot discriminate (the tied-at-0 / unwinnable pathology).
- ``indeterminate``  — an arm had no decisive trials, or no floor arm ran
  for this run (resume / already-promoted resource), so we can't classify.

The **flip rate** = discriminating / classifiable. ``run #8``'s suite
(0 llm_judge, 98 contains) would surface here as a flip rate near 0 with
most scenarios ``saturated`` — exactly the diagnostic that was missing.

This module is pure: it consumes an :class:`EvalResults` and emits a
:class:`DiscriminationReport`. The caller
(``_orchestrator_phases/execution_eval.py``) persists the report, logs it,
and stamps span attributes. Phase A.5 ships measure-and-surface; pruning /
auto-regenerating non-discriminating scenarios is a follow-up so it can be
validated against the audit data first (see CGF-EVAL-ROADMAP § 3.7 A2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.optimization.eval_harness.models import ArmResults, EvalResults

__all__ = [
    "DEFAULT_MIN_FLIP_RATE",
    "DISCRIMINATING",
    "INVERTED",
    "SATURATED",
    "DEAD",
    "INDETERMINATE",
    "ScenarioDiscrimination",
    "DiscriminationReport",
    "classify",
    "analyze",
]

DEFAULT_MIN_FLIP_RATE = 0.40

DISCRIMINATING = "discriminating"
INVERTED = "inverted"
SATURATED = "saturated"
DEAD = "dead"
INDETERMINATE = "indeterminate"

# Classifications that carry NO signal — the targets for pruning/regeneration.
NON_DISCRIMINATING = frozenset({SATURATED, DEAD})

_EPS = 1e-9


def classify(candidate: ArmResults | None, floor: ArmResults | None) -> str:
    """Classify one scenario by comparing its candidate and floor arms.

    Uses pass-rate magnitude (not a hard pass/fail boolean) so partial-credit
    differences at ``trials_per_scenario > 1`` register as discriminating.
    """
    if candidate is None or candidate.decisive <= 0:
        return INDETERMINATE
    if floor is None or floor.decisive <= 0:
        return INDETERMINATE
    c = candidate.pass_rate
    f = floor.pass_rate
    if c > f + _EPS:
        return DISCRIMINATING
    if f > c + _EPS:
        return INVERTED
    # equal pass rates → no separation; high = saturated, low = dead
    return SATURATED if c >= 0.5 else DEAD


@dataclass
class ScenarioDiscrimination:
    """Per-scenario audit row."""

    scenario_id: str
    classification: str
    candidate_pass_rate: float
    floor_pass_rate: float
    held_out: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "classification": self.classification,
            "candidate_pass_rate": self.candidate_pass_rate,
            "floor_pass_rate": self.floor_pass_rate,
            "held_out": self.held_out,
        }


@dataclass
class DiscriminationReport:
    """Per-resource discrimination audit."""

    resource_path: str
    min_flip_rate: float
    scenarios: list[ScenarioDiscrimination]
    discriminating: int
    inverted: int
    saturated: int
    dead: int
    indeterminate: int

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def classifiable(self) -> int:
        """Scenarios with a decisive candidate AND floor arm."""
        return self.total - self.indeterminate

    @property
    def flip_rate(self) -> float:
        """Fraction of classifiable scenarios that discriminate (cand > floor)."""
        if self.classifiable <= 0:
            return 0.0
        return self.discriminating / self.classifiable

    @property
    def non_discriminating_ids(self) -> list[str]:
        """Scenario IDs that carry no signal (saturated or dead)."""
        return [
            s.scenario_id
            for s in self.scenarios
            if s.classification in NON_DISCRIMINATING
        ]

    @property
    def meets_target(self) -> bool:
        """True when enough scenarios discriminate to trust the suite."""
        return self.classifiable > 0 and self.flip_rate >= self.min_flip_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_path": self.resource_path,
            "min_flip_rate": self.min_flip_rate,
            "flip_rate": self.flip_rate,
            "meets_target": self.meets_target,
            "total": self.total,
            "classifiable": self.classifiable,
            "counts": {
                DISCRIMINATING: self.discriminating,
                INVERTED: self.inverted,
                SATURATED: self.saturated,
                DEAD: self.dead,
                INDETERMINATE: self.indeterminate,
            },
            "non_discriminating_ids": self.non_discriminating_ids,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


def analyze(
    results: EvalResults,
    *,
    resource_path: str,
    min_flip_rate: float = DEFAULT_MIN_FLIP_RATE,
) -> DiscriminationReport | None:
    """Build a discrimination report from an eval run.

    Returns ``None`` when no scenario has floor-arm data (the floor arm
    only runs at first promotion — on resume / already-promoted resources
    there is nothing to audit against, so the audit is skipped rather than
    reported as all-indeterminate noise).
    """
    rows: list[ScenarioDiscrimination] = []
    counts = {
        DISCRIMINATING: 0,
        INVERTED: 0,
        SATURATED: 0,
        DEAD: 0,
        INDETERMINATE: 0,
    }
    any_floor = False
    for sr in results.scenarios:
        floor = getattr(sr, "floor", None)
        if floor is not None:
            any_floor = True
        cls = classify(sr.candidate, floor)
        counts[cls] += 1
        rows.append(
            ScenarioDiscrimination(
                scenario_id=sr.scenario_id,
                classification=cls,
                candidate_pass_rate=(
                    sr.candidate.pass_rate if sr.candidate is not None else 0.0
                ),
                floor_pass_rate=floor.pass_rate if floor is not None else 0.0,
                held_out=sr.held_out,
            )
        )

    if not any_floor:
        return None

    return DiscriminationReport(
        resource_path=resource_path,
        min_flip_rate=min_flip_rate,
        scenarios=rows,
        discriminating=counts[DISCRIMINATING],
        inverted=counts[INVERTED],
        saturated=counts[SATURATED],
        dead=counts[DEAD],
        indeterminate=counts[INDETERMINATE],
    )
