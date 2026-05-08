"""LLM-judge grader (Phase A.3).

Calls an LLM to score the agent transcript against a rubric on a 1–5
scale, normalized to 0.0–1.0 via ``(score - 1) / 4``.  When the judge
itself errors (rate limit, network, parse failure), the grader retries
exactly once and then marks the result ``no_decision=True``.  The eval
gate treats no-decision results as ties — neither arm wins, neither
arm loses — so a flaky judge can't auto-fail real candidates.

The ``pairwise`` flag is reserved for Phase B (position-balanced A-B vs
B-A comparison).  In Phase A we ship the flag but always run solo
scoring — see CGF-EVAL-FRAMEWORK.md § 4.B.5.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from harness.optimization.graders.base import BaseGrader, GraderResult
from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = structlog.get_logger(__name__)


# Maps short model names to full model IDs.  Mirrors the table in
# ``harness.optimization.testcases.validators`` for consistency.
_MODEL_ALIAS = {
    "haiku": "claude-3-5-haiku-20241022",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-5-20250929",
}

_DEFAULT_JUDGE_MODEL = "claude-opus-4-5-20250929"


def _resolve_judge_model(model: str | None) -> str:
    """Apply the precedence: explicit param > env var > default opus.

    Short names (haiku/sonnet/opus) are expanded to full model IDs.
    """
    candidate = model or os.environ.get("CGF_JUDGE_MODEL") or _DEFAULT_JUDGE_MODEL
    return _MODEL_ALIAS.get(candidate, candidate)


# Lazily-initialized shared client.  We do NOT reuse the singleton from
# ``testcases.validators`` because that module's ``set_eval_model``
# overrides global state — graders should not be affected by tests' fixture
# setup or vice versa.
_shared_client: AsyncAnthropic | None = None


def get_judge_client() -> AsyncAnthropic:
    """Return a shared :class:`AsyncAnthropic` client for graders.

    Tests can monkeypatch this to inject mocks; clear via
    ``llm_judge._shared_client = None`` between tests if needed.
    """
    global _shared_client
    if _shared_client is None:
        from anthropic import AsyncAnthropic

        _shared_client = AsyncAnthropic()
    return _shared_client


_SYSTEM_PROMPT = (
    "You are an evaluation judge for an AI agent's transcript. "
    "Score the transcript on a 1–5 integer scale against the rubric. "
    "Respond with ONLY a single integer 1, 2, 3, 4, or 5 — no other text."
)


def _build_user_prompt(rubric: str, transcript: AgentTranscript) -> str:
    return (
        f"## Rubric\n{rubric.strip()}\n\n"
        f"## Agent transcript\n"
        f"Final output:\n{transcript.final_output[:4000]}\n\n"
        f"Total turns: {transcript.total_turns}\n"
        f"Tool calls: {len(transcript.tool_calls)}\n\n"
        f"## Your score (1–5):"
    )


_INTEGER_RE = re.compile(r"\b([1-5])\b")


def _parse_score(text: str) -> int | None:
    """Pull a 1–5 integer score out of the model's reply, or ``None``."""
    stripped = text.strip()
    if stripped in {"1", "2", "3", "4", "5"}:
        return int(stripped)
    match = _INTEGER_RE.search(stripped)
    if match is not None:
        return int(match.group(1))
    return None


@dataclass
class LLMJudgeGrader(BaseGrader):
    """Score transcript with an LLM judge against ``rubric``."""

    rubric: str
    pass_threshold: float = 0.7
    eval_model: str | None = None
    pairwise: bool = False  # reserved for Phase B
    grader_type: str = "llm_judge"

    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult:
        model = _resolve_judge_model(self.eval_model)
        user_prompt = _build_user_prompt(self.rubric, transcript)

        # Retry once; if the second attempt also fails to produce a
        # parseable score, return a no_decision result.
        for attempt in (1, 2):
            try:
                client = get_judge_client()
                response = await client.messages.create(
                    model=model,
                    max_tokens=8,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
            except Exception as exc:  # noqa: BLE001 — judge error → retry/no-decision
                logger.warning(
                    "llm_judge call failed",
                    attempt=attempt,
                    model=model,
                    error=str(exc),
                )
                if attempt == 2:
                    return self._no_decision(f"judge errored twice: {exc}")
                continue

            raw = self._extract_text(response)
            score_int = _parse_score(raw)
            if score_int is None:
                logger.warning(
                    "llm_judge unparseable response",
                    attempt=attempt,
                    raw=raw[:80],
                )
                if attempt == 2:
                    return self._no_decision(
                        f"could not parse score from {raw[:80]!r}"
                    )
                continue

            normalized = (score_int - 1) / 4.0
            passed = normalized >= self.pass_threshold
            return GraderResult(
                passed=passed,
                score=normalized,
                details=(
                    f"judge={score_int}/5 (norm={normalized:.2f}, "
                    f"threshold={self.pass_threshold:.2f}, model={model})"
                ),
                grader_type="llm_judge",
            )

        # Unreachable — both attempts handled above.  Defensive fallback.
        return self._no_decision("retry loop exited without verdict")

    @staticmethod
    def _extract_text(response: object) -> str:
        """Pull the text out of Anthropic's response object."""
        content = getattr(response, "content", None)
        if not content:
            return ""
        first = content[0]
        # SDK shape: list of TextBlock with .text
        return str(getattr(first, "text", first))

    def _no_decision(self, reason: str) -> GraderResult:
        return GraderResult(
            passed=False,
            score=0.0,
            details=f"no_decision: {reason}",
            grader_type="llm_judge",
            no_decision=True,
        )
