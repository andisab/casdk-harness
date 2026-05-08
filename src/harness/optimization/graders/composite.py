"""Composite grader (Phase A.3).

Combines child graders with ``and`` or ``or``.  Children run sequentially
in order: ``and`` short-circuits on first fail, ``or`` short-circuits on
first pass.  This matters for cost — a deterministic check followed by an
LLM-judge in an ``and`` will skip the judge whenever the cheap check
fails.

``no_decision`` propagation:

- ``and``: any no_decision child → composite is no_decision (the
  optimizer can't tell whether to celebrate or fix)
- ``or``: a passing sibling overrides a no_decision; otherwise a
  no_decision child poisons the result

The grader's score is an aggregate: ``and`` returns the *minimum* child
score (so a partial pass remains visible without claiming full
success); ``or`` returns the *maximum*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from harness.optimization.graders.base import BaseGrader, GraderResult
from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript

CompositeOperator = Literal["and", "or"]


@dataclass
class CompositeGrader(BaseGrader):
    """Combine child graders via boolean operator with short-circuit eval."""

    operator: CompositeOperator = "and"
    graders: list[BaseGrader] = field(default_factory=list)
    grader_type: str = "composite"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        if not self.graders:
            return GraderResult(
                passed=False,
                score=0.0,
                details="composite has zero children",
                grader_type="composite",
            )

        if self.operator == "and":
            return await self._grade_and(transcript, scenario)
        if self.operator == "or":
            return await self._grade_or(transcript, scenario)
        raise ValueError(f"Unknown composite operator: {self.operator!r}")

    async def _grade_and(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        results: list[GraderResult] = []
        for child in self.graders:
            r = await child.grade(transcript, scenario)
            results.append(r)
            if not r.passed:
                # Short-circuit: aggregate over what we evaluated and bail.
                return self._aggregate_and(results, short_circuited=True)
        return self._aggregate_and(results, short_circuited=False)

    async def _grade_or(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        results: list[GraderResult] = []
        for child in self.graders:
            r = await child.grade(transcript, scenario)
            results.append(r)
            if r.passed:
                return self._aggregate_or(results, short_circuited=True)
        return self._aggregate_or(results, short_circuited=False)

    @staticmethod
    def _aggregate_and(
        results: list[GraderResult],
        short_circuited: bool,
    ) -> GraderResult:
        any_no_decision = any(r.no_decision for r in results)
        all_passed = all(r.passed for r in results) and not short_circuited
        score = min(r.score for r in results)
        labels = [
            f"{r.grader_type}={'✓' if r.passed else '✗'}"
            + ("(no_decision)" if r.no_decision else "")
            for r in results
        ]
        suffix = " (short-circuited)" if short_circuited else ""
        return GraderResult(
            passed=all_passed and not any_no_decision,
            score=score,
            details=f"and: {' & '.join(labels)}{suffix}",
            grader_type="composite",
            no_decision=any_no_decision and not all_passed,
        )

    @staticmethod
    def _aggregate_or(
        results: list[GraderResult],
        short_circuited: bool,
    ) -> GraderResult:
        any_passed = any(r.passed for r in results)
        # OR rule: a passing sibling overrides no_decision; no_decision
        # only sticks when nothing else passed.
        any_no_decision = any(r.no_decision for r in results) and not any_passed
        score = max(r.score for r in results)
        labels = [
            f"{r.grader_type}={'✓' if r.passed else '✗'}"
            + ("(no_decision)" if r.no_decision else "")
            for r in results
        ]
        suffix = " (short-circuited)" if short_circuited else ""
        return GraderResult(
            passed=any_passed,
            score=score,
            details=f"or: {' | '.join(labels)}{suffix}",
            grader_type="composite",
            no_decision=any_no_decision,
        )
