"""Grader base classes (CGF Stage 3 Phase A.3).

A grader takes one ``AgentTranscript`` and one ``EvalScenario`` and returns
a ``GraderResult``.  Graders compose: a ``CompositeGrader`` holds a list of
sub-graders and an ``and|or`` operator, and a ``TrajectoryGrader`` holds a
list of typed assertions.

All graders are async — even cheap deterministic ones — so that the harness
can run scenarios concurrently with ``asyncio.gather`` without tripping
over a sync grader blocking the event loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript

# Discriminator literals matching ``schemas/eval_suite.schema.json`` enum.
GraderType = Literal[
    "exact",
    "contains",
    "regex",
    "code",
    "trajectory",
    "llm_judge",
    "composite",
]


@dataclass
class GraderResult:
    """Result of grading one scenario with one grader.

    ``score`` is always in [0.0, 1.0].  ``passed`` is the canonical pass/fail
    decision; for non-binary graders (llm_judge) it derives from a
    grader-specific threshold.

    ``arm`` is set by the harness *after* grading, so a single ``GraderResult``
    can be tagged ``baseline`` or ``candidate`` for two-arm aggregation.

    ``no_decision`` is the LLM-judge retry-once-then-mark-no-decision escape
    hatch.  When True, the harness should treat the result as a tie (neither
    arm wins this scenario) rather than a fail.
    """

    passed: bool
    score: float
    details: str
    grader_type: GraderType
    arm: Literal["baseline", "candidate"] | None = None
    no_decision: bool = False

    def __post_init__(self) -> None:
        # Clamp score defensively so downstream aggregation can't NaN.
        if self.score < 0.0:
            self.score = 0.0
        elif self.score > 1.0:
            self.score = 1.0


class BaseGrader(ABC):
    """Abstract base for all graders.

    Subclasses override :meth:`grade`.  Concrete configuration (the regex
    pattern, LLM-judge rubric, etc.) lives on the subclass instance —
    graders are constructed once per scenario from the eval-suite YAML and
    re-used across both arms of a two-arm comparison.
    """

    grader_type: GraderType  # set on each subclass

    @abstractmethod
    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        """Score the transcript.  Must always return — never raise on
        graded-output failures (raise only for programmer errors like
        invalid configuration)."""
        ...
