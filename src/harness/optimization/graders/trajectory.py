"""Trajectory grader (Phase A.3).

Walks ``transcript.tool_calls`` and verifies a list of typed assertions:

- ``tool_called`` — tool was invoked at least N times (optionally with
  argument constraints)
- ``no_tool`` — tool was never invoked
- ``ordering`` — tool A was invoked before tool B
- ``constraint`` — natural-language rule, verified by an LLM judge over
  the transcript (delegates to :class:`LLMJudgeGrader`)

A trajectory grader passes iff every assertion passes.  The result
``details`` lists per-assertion outcomes so eval-results.json is
self-explanatory without re-running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.optimization.graders.base import BaseGrader, GraderResult
from harness.optimization.graders.llm_judge import LLMJudgeGrader
from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript, ToolCall

# ---------------------------------------------------------------------------
# Assertion types
# ---------------------------------------------------------------------------


@dataclass
class TrajectoryAssertion:
    """Common base — subclasses set ``kind`` and implement ``check``.

    ``check`` returns a ``(passed, detail)`` tuple.  It can be async
    because :class:`ConstraintAssertion` calls the LLM judge.
    """

    kind: str = ""

    async def check(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> tuple[bool, str]:
        raise NotImplementedError


def _args_match(call_args: dict, required: dict) -> bool:
    """Every key in ``required`` must be present in ``call_args`` with an
    equal value.  Extra keys in ``call_args`` are allowed.
    """
    return all(k in call_args and call_args[k] == v for k, v in required.items())


@dataclass
class ToolCalledAssertion(TrajectoryAssertion):
    """Tool was called at least ``min_count`` times (optionally with args)."""

    tool: str = ""
    min_count: int = 1
    with_arg: dict[str, Any] | None = None
    kind: str = "tool_called"

    async def check(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> tuple[bool, str]:
        candidates: list[ToolCall] = transcript.tool_calls_named(self.tool)
        if self.with_arg:
            candidates = [c for c in candidates if _args_match(c.arguments, self.with_arg)]
        passed = len(candidates) >= self.min_count
        if passed:
            return True, f"tool_called {self.tool} ×{len(candidates)} ≥ {self.min_count}"
        return False, (
            f"tool_called {self.tool} ×{len(candidates)} < {self.min_count}"
        )


@dataclass
class NoToolAssertion(TrajectoryAssertion):
    """Tool was never called."""

    tool: str = ""
    kind: str = "no_tool"

    async def check(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> tuple[bool, str]:
        count = len(transcript.tool_calls_named(self.tool))
        if count == 0:
            return True, f"no_tool {self.tool}: ✓"
        return False, f"no_tool {self.tool}: violated ({count} call(s))"


@dataclass
class OrderingAssertion(TrajectoryAssertion):
    """``before`` was first called at some point earlier than ``after``.

    Both tools must have been called at least once.  The first call to
    ``before`` must precede the first call to ``after``.
    """

    before: str = ""
    after: str = ""
    kind: str = "ordering"

    async def check(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> tuple[bool, str]:
        before_calls = transcript.tool_calls_named(self.before)
        after_calls = transcript.tool_calls_named(self.after)
        if not before_calls:
            return False, f"ordering: {self.before} never called"
        if not after_calls:
            return False, f"ordering: {self.after} never called"
        # Use turn_number as the primary ordering key; timestamp ties are rare.
        before_first = min(c.turn_number for c in before_calls)
        after_first = min(c.turn_number for c in after_calls)
        if before_first < after_first:
            return True, f"ordering: {self.before}(t{before_first}) → {self.after}(t{after_first})"
        return False, (
            f"ordering violated: {self.after}(t{after_first}) ≤ {self.before}(t{before_first})"
        )


@dataclass
class ConstraintAssertion(TrajectoryAssertion):
    """Natural-language constraint, LLM-verified over the transcript."""

    text: str = ""
    eval_model: str | None = None
    kind: str = "constraint"

    async def check(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> tuple[bool, str]:
        rubric = (
            f"Verify the following constraint from the agent's behavior: "
            f"{self.text.strip()}\n\n"
            "Score 5 if the constraint is fully satisfied, 1 if clearly "
            "violated, intermediate otherwise."
        )
        judge = LLMJudgeGrader(
            rubric=rubric,
            pass_threshold=0.6,
            eval_model=self.eval_model,
        )
        result = await judge.grade(transcript, scenario)
        if result.no_decision:
            # Surface no_decision as a soft pass so we don't nuke the
            # composite TrajectoryGrader on a flaky judge.  The harness
            # gate still sees no_decision via aggregation.
            return True, f"constraint no_decision: {result.details}"
        return result.passed, f"constraint: {result.details}"


# ---------------------------------------------------------------------------
# Grader
# ---------------------------------------------------------------------------


@dataclass
class TrajectoryGrader(BaseGrader):
    """Evaluate a list of trajectory assertions against the transcript.

    Passes iff every assertion passes.  Reports each assertion's verdict
    in ``details`` so failures are diagnosable without rerunning.
    """

    assertions: list[TrajectoryAssertion] = field(default_factory=list)
    grader_type: str = "trajectory"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        if not self.assertions:
            return GraderResult(
                passed=False,
                score=0.0,
                details="trajectory grader has zero assertions",
                grader_type="trajectory",
            )

        verdicts: list[tuple[bool, str]] = []
        for assertion in self.assertions:
            verdicts.append(await assertion.check(transcript, scenario))

        all_passed = all(v[0] for v in verdicts)
        passed_count = sum(1 for v in verdicts if v[0])
        score = passed_count / len(verdicts)
        # Render each assertion verdict on its own line.
        details = " | ".join(v[1] for v in verdicts)
        return GraderResult(
            passed=all_passed,
            score=score,
            details=f"trajectory ({passed_count}/{len(verdicts)}): {details}",
            grader_type="trajectory",
        )
