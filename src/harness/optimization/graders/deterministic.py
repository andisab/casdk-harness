"""Deterministic graders: exact, contains, regex, code (Phase A.3).

These are the cheapest tier — no LLM calls, no model variance.  Prefer
them over ``llm_judge`` whenever a pattern can capture the requirement.

The ``code`` grader executes a user-supplied Python snippet against the
transcript.  This is acceptable in Phase A because the eval harness runs
in-process inside the harness container (same trust domain as the agent
under test).  Phase C will move execution into ephemeral containers,
which is where the real isolation lives — see CGF-EVAL-FRAMEWORK.md § 5.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from harness.optimization.graders.base import BaseGrader, GraderResult
from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript

# Field selectors matching ``schemas/eval_suite.schema.json``.
TextField = Literal["final_output", "last_message", "any_message"]


def _select_text(transcript: AgentTranscript, field: TextField) -> str:
    if field == "final_output":
        return transcript.final_output
    if field == "last_message":
        return transcript.last_message
    if field == "any_message":
        return transcript.all_text
    raise ValueError(f"Unknown text field: {field!r}")


# ---------------------------------------------------------------------------
# Exact
# ---------------------------------------------------------------------------


@dataclass
class ExactGrader(BaseGrader):
    """Pass iff the chosen field equals ``expected`` exactly (after strip)."""

    expected: str
    field: Literal["final_output", "last_message"] = "final_output"
    grader_type: str = "exact"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        actual = _select_text(transcript, self.field).strip()
        passed = actual == self.expected.strip()
        return GraderResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            details=(
                "exact match"
                if passed
                else f"got {actual[:120]!r}, expected {self.expected[:120]!r}"
            ),
            grader_type="exact",
        )


# ---------------------------------------------------------------------------
# Contains
# ---------------------------------------------------------------------------


@dataclass
class ContainsGrader(BaseGrader):
    """Pass iff ``needle`` appears as a substring of the chosen field."""

    needle: str
    case_insensitive: bool = False
    field: TextField = "final_output"
    grader_type: str = "contains"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        haystack = _select_text(transcript, self.field)
        if self.case_insensitive:
            passed = self.needle.lower() in haystack.lower()
        else:
            passed = self.needle in haystack
        return GraderResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            details=(
                f"found {self.needle!r}"
                if passed
                else f"missing {self.needle!r} in {self.field}"
            ),
            grader_type="contains",
        )


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------


_RE_FLAG_NAMES = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


@dataclass
class RegexGrader(BaseGrader):
    """Pass iff the pattern matches anywhere in the chosen field."""

    pattern: str
    flags: tuple[str, ...] = ()
    field: TextField = "final_output"
    grader_type: str = "regex"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        flag_int = 0
        for name in self.flags:
            if name not in _RE_FLAG_NAMES:
                return GraderResult(
                    passed=False,
                    score=0.0,
                    details=f"unknown regex flag: {name!r}",
                    grader_type="regex",
                )
            flag_int |= _RE_FLAG_NAMES[name]

        try:
            compiled = re.compile(self.pattern, flag_int)
        except re.error as exc:
            return GraderResult(
                passed=False,
                score=0.0,
                details=f"invalid regex {self.pattern!r}: {exc}",
                grader_type="regex",
            )

        text = _select_text(transcript, self.field)
        match = compiled.search(text)
        passed = match is not None
        return GraderResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            details=(
                f"matched at offset {match.start()}"
                if match is not None
                else f"no match for {self.pattern!r} in {self.field}"
            ),
            grader_type="regex",
        )


# ---------------------------------------------------------------------------
# Code
# ---------------------------------------------------------------------------


@dataclass
class CodeGrader(BaseGrader):
    """Execute a Python snippet against the transcript.

    The snippet runs with ``transcript``, ``scenario``, ``re``, and
    ``json`` available as globals.  It passes by *not* raising; failure
    is signalled by ``assert`` (or any exception).  Stdout is suppressed.

    NOT a sandbox: the snippet has full process access in Phase A.  See
    module docstring.
    """

    code: str
    grader_type: str = "code"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        globs: dict = {
            "__builtins__": __builtins__,
            "transcript": transcript,
            "scenario": scenario,
            "re": re,
            "json": json,
        }
        try:
            exec(compile(self.code, "<code-grader>", "exec"), globs, globs)
        except AssertionError as exc:
            msg = str(exc) or "assertion failed"
            return GraderResult(
                passed=False,
                score=0.0,
                details=f"assert: {msg[:200]}",
                grader_type="code",
            )
        except Exception as exc:  # noqa: BLE001 — user code; surface anything
            return GraderResult(
                passed=False,
                score=0.0,
                details=f"{type(exc).__name__}: {str(exc)[:200]}",
                grader_type="code",
            )
        return GraderResult(
            passed=True,
            score=1.0,
            details="code-grader passed",
            grader_type="code",
        )
