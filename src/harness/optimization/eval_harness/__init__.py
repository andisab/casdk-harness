"""CGF eval harness — runs eval suites against (baseline, candidate)
resource pairs (Stage 3 Phase A.4).

Public surface:

- :class:`EvalHarness` — main runner; ``await harness.run(suite, baseline,
  candidate)`` returns :class:`EvalResults`.
- :func:`load_eval_suite` — parse + schema-validate a suite YAML.
- :class:`EvalSuite`, :class:`EvalConfig`, :class:`ScenarioWithGraders` —
  the loaded shape.
- :class:`TrialResult`, :class:`ArmResults`, :class:`ScenarioResult`,
  :class:`SubsetStats`, :class:`EvalResults` — the result types.
- :func:`aggregate_arm`, :func:`compare_arms`, :func:`aggregate_subset` —
  reusable aggregation primitives, public for tests / orchestrator.

Design as-built: ``docs/CGF-EVAL-ROADMAP.md`` § 2 (Architecture) +
``docs/PHASEA_SUMMARY.md`` § 2 (technical decisions).
"""

from __future__ import annotations

from harness.optimization.eval_harness.aggregate import (
    aggregate_arm,
    aggregate_subset,
    compare_arms,
    group_by_level,
    group_by_tag,
)
from harness.optimization.eval_harness.loader import (
    EvalSuiteValidationError,
    load_eval_suite,
)
from harness.optimization.eval_harness.models import (
    Arm,
    ArmResults,
    EvalConfig,
    EvalResults,
    EvalSuite,
    ScenarioOutcome,
    ScenarioResult,
    ScenarioWithGraders,
    SubsetStats,
    TrialResult,
)
from harness.optimization.eval_harness.runner import EvalHarness, Runtime

__all__ = [
    # runner
    "EvalHarness",
    "Runtime",
    # loader
    "load_eval_suite",
    "EvalSuiteValidationError",
    # models
    "EvalSuite",
    "EvalConfig",
    "ScenarioWithGraders",
    "TrialResult",
    "ArmResults",
    "ScenarioResult",
    "SubsetStats",
    "EvalResults",
    "Arm",
    "ScenarioOutcome",
    # aggregation primitives
    "aggregate_arm",
    "compare_arms",
    "aggregate_subset",
    "group_by_level",
    "group_by_tag",
]
