"""CGF eval-suite graders (Stage 3 Phase A.3).

Public API is finalized at the bottom of this file once all submodules
are imported.  See ``docs/CGF-EVAL-ROADMAP.md`` § 2.2 (grader hierarchy)
for the design rationale and ``schemas/eval_suite.schema.json`` for
the wire format that ``build_grader`` consumes.
"""

from __future__ import annotations

from harness.optimization.graders.base import BaseGrader, GraderResult, GraderType
from harness.optimization.graders.composite import (
    CompositeGrader,
    CompositeOperator,
)
from harness.optimization.graders.deterministic import (
    CodeGrader,
    ContainsGrader,
    ExactGrader,
    RegexGrader,
)
from harness.optimization.graders.llm_judge import LLMJudgeGrader
from harness.optimization.graders.scenario import (
    Difficulty,
    EvalScenario,
    ScenarioLevel,
    ScenarioSetup,
    SetupFile,
)
from harness.optimization.graders.trajectory import (
    ConstraintAssertion,
    NoToolAssertion,
    OrderingAssertion,
    ToolCalledAssertion,
    TrajectoryAssertion,
    TrajectoryGrader,
)
from harness.optimization.graders.transcript import (
    AgentTranscript,
    ToolCall,
    TranscriptBuilder,
    TranscriptMessage,
)

__all__ = [
    # base
    "BaseGrader",
    "GraderResult",
    "GraderType",
    # data model
    "AgentTranscript",
    "ToolCall",
    "TranscriptBuilder",
    "TranscriptMessage",
    "EvalScenario",
    "ScenarioSetup",
    "SetupFile",
    "ScenarioLevel",
    "Difficulty",
    # graders
    "ExactGrader",
    "ContainsGrader",
    "RegexGrader",
    "CodeGrader",
    "LLMJudgeGrader",
    "TrajectoryGrader",
    "TrajectoryAssertion",
    "ToolCalledAssertion",
    "NoToolAssertion",
    "OrderingAssertion",
    "ConstraintAssertion",
    "CompositeGrader",
    "CompositeOperator",
    # factory
    "build_grader",
]


def build_grader(spec: dict) -> BaseGrader:
    """Construct a grader from one entry in the ``graders`` array of an
    eval-suite YAML document.

    The ``spec`` dict should already have been validated against
    ``schemas/eval_suite.schema.json``; this function does shape-checking
    only via dict lookups and trusts the schema for type correctness.
    Unknown grader types raise ``ValueError``.
    """
    grader_type = spec.get("type")

    if grader_type == "exact":
        return ExactGrader(
            expected=spec["expected"],
            field=spec.get("field", "final_output"),
        )
    if grader_type == "contains":
        return ContainsGrader(
            needle=spec["needle"],
            case_insensitive=spec.get("case_insensitive", False),
            field=spec.get("field", "final_output"),
        )
    if grader_type == "regex":
        return RegexGrader(
            pattern=spec["pattern"],
            flags=tuple(spec.get("flags", [])),
            field=spec.get("field", "final_output"),
        )
    if grader_type == "code":
        return CodeGrader(code=spec["code"])
    if grader_type == "trajectory":
        return TrajectoryGrader(
            assertions=[
                _build_trajectory_assertion(a) for a in spec["assertions"]
            ]
        )
    if grader_type == "llm_judge":
        return LLMJudgeGrader(
            rubric=spec["rubric"],
            pass_threshold=spec.get("pass_threshold", 0.7),
            eval_model=spec.get("eval_model"),
            pairwise=spec.get("pairwise", False),
        )
    if grader_type == "composite":
        return CompositeGrader(
            operator=spec["operator"],
            graders=[build_grader(g) for g in spec["graders"]],
        )
    raise ValueError(f"Unknown grader type: {grader_type!r}")


def _build_trajectory_assertion(spec: dict) -> TrajectoryAssertion:
    kind = spec.get("kind")
    if kind == "tool_called":
        return ToolCalledAssertion(
            tool=spec["tool"],
            min_count=spec.get("min_count", 1),
            with_arg=dict(spec.get("with_arg", {})) or None,
        )
    if kind == "no_tool":
        return NoToolAssertion(tool=spec["tool"])
    if kind == "ordering":
        return OrderingAssertion(before=spec["before"], after=spec["after"])
    if kind == "constraint":
        return ConstraintAssertion(text=spec["text"])
    raise ValueError(f"Unknown trajectory assertion kind: {kind!r}")
