"""Eval harness data model (CGF Stage 3 Phase A.4).

The structured shape of an eval-suite-in-memory and the records it
produces.  Loaders turn YAML into :class:`EvalSuite`; the runner produces
:class:`EvalResults` from running a suite against (baseline, candidate)
resource pairs; aggregation computes :class:`SubsetStats` slices.

All score / pass-rate values are in [0.0, 1.0].  Counts are non-negative
integers.  The dataclasses are JSON-serializable via ``to_dict()``
helpers — used by the runner when it writes ``eval-results.json``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from harness.optimization.graders import (
    AgentTranscript,
    BaseGrader,
    EvalScenario,
    GraderResult,
)

Arm = Literal["baseline", "candidate", "floor"]
ScenarioOutcome = Literal["baseline_win", "candidate_win", "tie", "no_decision"]


@dataclass
class EvalConfig:
    """Suite-level run configuration (mirrors ``config`` in the schema)."""

    trials_per_scenario: int = 3
    timeout_seconds: int = 300
    eval_model: str = "claude-opus-4-5-20250929"
    token_budget: int | None = None
    held_out_fraction: float = 0.25


@dataclass
class ScenarioWithGraders:
    """An :class:`EvalScenario` paired with its constructed graders.

    The loader produces these by validating each scenario's YAML against
    ``eval_suite.schema.json`` and feeding each grader spec through
    :func:`harness.optimization.graders.build_grader`.
    """

    scenario: EvalScenario
    graders: list[BaseGrader]


@dataclass
class EvalSuite:
    """Top-level loaded suite — what the runner consumes."""

    version: str
    target_resource: str
    scenarios: list[ScenarioWithGraders]
    config: EvalConfig
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def held_out_scenarios(self) -> list[ScenarioWithGraders]:
        """Subset where ``scenario.held_out`` is True."""
        return [s for s in self.scenarios if s.scenario.held_out]


# ---------------------------------------------------------------------------
# Trial / arm / scenario results
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    """One trial: one resource invoked once against one scenario, then graded.

    ``passed`` requires every grader to pass *and* no grader to return
    ``no_decision``.  ``no_decision`` is true if any grader did — the
    scenario aggregator uses it to avoid penalizing the candidate for
    flaky judges.

    ``error`` captures runtime / SDK failures (timeout, transport error)
    that prevented the trial from running to completion.  When set, the
    trial is treated as ``no_decision`` for aggregation purposes — the
    candidate didn't fail, the harness did.
    """

    arm: Arm
    trial_index: int
    transcript: AgentTranscript
    grader_results: list[GraderResult]
    passed: bool
    no_decision: bool
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "trial_index": self.trial_index,
            "passed": self.passed,
            "no_decision": self.no_decision,
            "error": self.error,
            "final_output": self.transcript.final_output[:2000],
            "total_turns": self.transcript.total_turns,
            "total_tokens": self.transcript.total_tokens,
            "total_cost_usd": self.transcript.total_cost_usd,
            "tool_calls": [
                {"tool": t.tool_name, "args": t.arguments, "turn": t.turn_number}
                for t in self.transcript.tool_calls
            ],
            "graders": [
                {
                    "type": gr.grader_type,
                    "passed": gr.passed,
                    "score": gr.score,
                    "no_decision": gr.no_decision,
                    "details": gr.details,
                }
                for gr in self.grader_results
            ],
        }


@dataclass
class ArmResults:
    """Aggregate metrics for one arm across all trials of one scenario.

    - ``pass_rate``: fraction of *decisive* trials that passed.  Decisive
      means the trial was neither no_decision nor errored.  When zero
      decisive trials exist, ``pass_rate`` is 0.0 and ``decisive`` is 0.
    - ``pass_at_k``: at least one decisive trial passed (1.0 or 0.0).
    - ``pass_caret_k``: every decisive trial passed (1.0 or 0.0).  Only
      meaningful when ``decisive >= 1``.
    """

    arm: Arm
    trials: list[TrialResult]
    decisive: int
    pass_rate: float
    pass_at_k: float
    pass_caret_k: float
    avg_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "decisive": self.decisive,
            "pass_rate": self.pass_rate,
            "pass_at_k": self.pass_at_k,
            "pass_caret_k": self.pass_caret_k,
            "avg_score": self.avg_score,
            "trials": [t.to_dict() for t in self.trials],
        }


@dataclass
class ScenarioResult:
    """One scenario, both arms, with the win/tie outcome."""

    scenario_id: str
    level: str
    held_out: bool
    tags: list[str]
    difficulty: str | None
    baseline: ArmResults
    candidate: ArmResults
    outcome: ScenarioOutcome
    # Phase A refinement 4.2: optional third arm.  Populated only on
    # first-time-promotion eval runs, where the bare-model floor must
    # be beaten before the candidate becomes the first incumbent.  Once
    # any version has promoted, this stays None for the rest of the
    # branch.
    floor: ArmResults | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "level": self.level,
            "held_out": self.held_out,
            "tags": list(self.tags),
            "difficulty": self.difficulty,
            "outcome": self.outcome,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "floor": self.floor.to_dict() if self.floor is not None else None,
        }


@dataclass
class SubsetStats:
    """Aggregate stats over a subset of scenarios.

    Used for the held-out subset, per-level rollups (unit/trajectory/e2e),
    and per-tag rollups.  All fields are float in [0.0, 1.0] except
    ``count``.
    """

    count: int
    win_rate: float
    baseline_pass_rate: float
    candidate_pass_rate: float
    no_decision_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalResults:
    """Top-level run output, written to ``eval-results.json``."""

    suite_path: str
    baseline_resource: str
    candidate_resource: str
    timestamp: str
    scenarios: list[ScenarioResult]
    win_rate: float
    baseline_pass_rate: float
    candidate_pass_rate: float
    no_decision_rate: float
    held_out: SubsetStats | None
    by_level: dict[str, SubsetStats]
    by_tag: dict[str, SubsetStats]
    total_tokens: int
    # Phase A refinement 4.2: floor arm aggregate, populated only on
    # first-time-promotion runs.  ``floor_pass_rate`` is the mean
    # per-scenario floor arm pass-rate; ``None``-equivalent value is
    # ``floor=None`` (i.e. the field below is also None).
    floor: SubsetStats | None = None
    floor_pass_rate: float | None = None
    # Phase A refinement 4.3: cost-per-success gate inputs.  ``None``
    # means the arm had zero successful completions, in which case the
    # cost gate auto-passes (no signal to regress against).  Cost is in
    # USD, summed from SDK ResultMessage.total_cost_usd across all
    # decisive trials.  Exempt scenarios (cost_gate_exempt: true) are
    # excluded from both cost and successes.
    baseline_cost_per_success: float | None = None
    candidate_cost_per_success: float | None = None
    # Phase A refinement 4.3: cost gate input.  Sum of every trial's
    # ``transcript.total_cost_usd`` across both arms — same value family
    # the SDK feeds to ``claude_code_cost_usage_USD_total`` in Prom, so
    # the gate's view and the operator dashboard agree.
    total_cost_usd: float = 0.0
    # Phase A refinement 4.1: pin the judge identity and prompt shape used
    # for this run so Phase D's Cohen's-κ calibration check has a stable
    # key per (judge_model_id, judge_prompt_hash, rubric).  Empty string
    # means no LLM-judge graders fired (deterministic-only suite).
    judge_model_id: str = ""
    judge_prompt_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_path": self.suite_path,
            "baseline_resource": self.baseline_resource,
            "candidate_resource": self.candidate_resource,
            "timestamp": self.timestamp,
            "win_rate": self.win_rate,
            "baseline_pass_rate": self.baseline_pass_rate,
            "candidate_pass_rate": self.candidate_pass_rate,
            "no_decision_rate": self.no_decision_rate,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "judge_model_id": self.judge_model_id,
            "judge_prompt_hash": self.judge_prompt_hash,
            "held_out": self.held_out.to_dict() if self.held_out is not None else None,
            "by_level": {k: v.to_dict() for k, v in self.by_level.items()},
            "by_tag": {k: v.to_dict() for k, v in self.by_tag.items()},
            "scenarios": [s.to_dict() for s in self.scenarios],
            "floor": self.floor.to_dict() if self.floor is not None else None,
            "floor_pass_rate": self.floor_pass_rate,
            "baseline_cost_per_success": self.baseline_cost_per_success,
            "candidate_cost_per_success": self.candidate_cost_per_success,
        }
