"""LLM-judge grader (Phase A.3).

Calls an LLM to score the agent transcript against a rubric on an
anchored 1–7 integer scale (per-level anchors in the system prompt),
normalized to 0.0–1.0 via ``(score - 1) / 6``.  Phase A.5 A3 widened the
scale from 1–5: frontier judges compress a 5-point scale to ~2–3 effective
points, and retry→tie then collapses it further; a 7-point anchored scale
recovers usable resolution (the discrimination lever from the eval
literature). G-Eval probability-weighting would be finer still but needs
token logprobs the Anthropic Messages API does not expose.  When the judge
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

from harness.config import MODEL_SHORTHAND_MAP
from harness.optimization.graders.base import BaseGrader, GraderResult
from harness.optimization.graders.scenario import EvalScenario
from harness.optimization.graders.transcript import AgentTranscript

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = structlog.get_logger(__name__)


# Short-name → full model ID resolution is centralized in
# ``harness.config.MODEL_SHORTHAND_MAP`` (the single source of truth for
# both the harness and the CGF graders).  We expose ``_DEFAULT_JUDGE_MODEL``
# as a derived constant so callers that want "the canonical judge model"
# get it via one import, but ``MODEL_SHORTHAND_MAP`` is the only place
# the IDs live.
_DEFAULT_JUDGE_MODEL = MODEL_SHORTHAND_MAP["opus"]


def _resolve_judge_model(model: str | None) -> str:
    """Apply the precedence: explicit param > env var > default opus.

    Short names (haiku/sonnet/opus) are expanded to full model IDs via
    :data:`harness.config.MODEL_SHORTHAND_MAP` — same table the rest of
    the harness uses, so a single edit there picks up every consumer.

    Phase A refinement 4.1: WARN when the resolved judge model matches
    ``CGF_DESIGN_MODEL`` (self-preference bias — judges prefer text from
    their own model family; see Panickssery et al. 2024, arXiv 2410.21819).
    Anthropic's *Three-Agent Harness* guidance is explicit: the agent
    judging must differ from the agent producing.
    """
    candidate = model or os.environ.get("CGF_JUDGE_MODEL") or _DEFAULT_JUDGE_MODEL
    resolved = MODEL_SHORTHAND_MAP.get(candidate, candidate)

    design_raw = os.environ.get("CGF_DESIGN_MODEL")
    if design_raw:
        design_resolved = MODEL_SHORTHAND_MAP.get(design_raw, design_raw)
        if design_resolved == resolved:
            logger.warning(
                "judge model matches design/optimizer model — "
                "self-preference bias risk",
                model=resolved,
                hint=(
                    "set CGF_JUDGE_MODEL and CGF_DESIGN_MODEL to different "
                    "models (e.g. opus / sonnet) so the judge cannot favor "
                    "text in its own family"
                ),
            )
    return resolved


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
    "You are an evaluation judge for an AI agent's transcript. Score how "
    "well the transcript satisfies the rubric on a 1–7 integer scale with "
    "these anchors:\n"
    "1 = fails the rubric entirely (wrong, irrelevant, or missing).\n"
    "2 = major gaps; addresses the task only superficially.\n"
    "3 = partially correct but with significant errors or omissions.\n"
    "4 = roughly half-right; meets some criteria, misses others.\n"
    "5 = mostly correct with minor errors or omissions.\n"
    "6 = correct and complete; only trivial nits.\n"
    "7 = fully correct, complete, and well-executed against the rubric.\n"
    "Judge against the rubric ONLY — length, formatting, and confident "
    "phrasing are not quality. Respond with ONLY a single integer 1-7."
)


def build_user_prompt(rubric: str, transcript: AgentTranscript) -> str:
    """Build the judge's user prompt from rubric + transcript only.

    Phase A refinement 4.1 — strict isolation contract: the judge sees
    only the **rubric** and the **agent transcript surface**.  It MUST
    NOT see any orchestrator state: no optimizer rationale, no version
    number, no diff vs baseline, no iteration count, no feedback
    history, no other-resource scores.  This function is the single
    chokepoint; tests assert it.

    Adding anything else here would let the optimizer's narrative leak
    into the gate.  Don't.
    """
    return (
        f"## Rubric\n{rubric.strip()}\n\n"
        f"## Agent transcript\n"
        f"Final output:\n{transcript.final_output[:4000]}\n\n"
        f"Total turns: {transcript.total_turns}\n"
        f"Tool calls: {len(transcript.tool_calls)}\n\n"
        f"## Your score (1–7):"
    )


# Backwards-compatible private alias — pre-refinement code referenced
# the underscore form.  Renamed to ``build_user_prompt`` so the runner
# can compute a hash for ``EvalResults.judge_prompt_hash``.
_build_user_prompt = build_user_prompt


def judge_prompt_hash(rubric: str, transcript: AgentTranscript) -> str:
    """SHA-256 of the *user prompt* that would be sent for this (rubric,
    transcript) pair.

    Intended for per-trial debugging / replay — the hash IS transcript-
    sensitive so two trials of the same scenario produce different
    hashes.  Not suitable as a calibration key (see
    :func:`judge_rubric_hash` for that — recorded on EvalResults).

    Kept stable so existing tests that pin (rubric, transcript) →
    deterministic hash continue to pass.
    """
    import hashlib

    body = build_user_prompt(rubric, transcript)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def judge_rubric_hash(rubric: str, judge_model_id: str = "") -> str:
    """SHA-256 of the *judge identity* for this rubric — stable across
    runs of the same suite.

    Hashes ``(rubric_text, judge_system_prompt, judge_model_id)``.
    Excludes the agent transcript intentionally: transcripts vary
    run-to-run from LLM stochasticity, so transcript-mixed hashes are
    unique per run and useless as Phase D's Cohen's-κ calibration key
    (which needs to compare grader behaviour across runs of the same
    suite/rubric).

    Recorded on :class:`EvalResults.judge_prompt_hash` so the
    calibration check can group judgments by
    ``(judge_model_id, rubric_version)`` and compute kappa per group.

    Args:
        rubric: The rubric text that anchors the judge.
        judge_model_id: Resolved judge model identifier (e.g.
            ``claude-opus-4-5-20250929``).  When empty, hash captures
            rubric + system-prompt identity only.
    """
    import hashlib

    payload = (
        f"rubric:\n{rubric.strip()}\n"
        f"system:\n{_SYSTEM_PROMPT}\n"
        f"model:\n{judge_model_id.strip()}\n"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_INTEGER_RE = re.compile(r"\b([1-7])\b")


def _parse_score(text: str) -> int | None:
    """Pull a 1–7 integer score out of the model's reply, or ``None``."""
    stripped = text.strip()
    if stripped in {"1", "2", "3", "4", "5", "6", "7"}:
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
        user_prompt = build_user_prompt(self.rubric, transcript)

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

            normalized = (score_int - 1) / 6.0
            passed = normalized >= self.pass_threshold
            return GraderResult(
                passed=passed,
                score=normalized,
                details=(
                    f"judge={score_int}/7 (norm={normalized:.2f}, "
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
        # Phase A.6 telemetry: bump the counter so operators can see how
        # often the judge model fails to decide.  Imported lazily so unit
        # tests that don't exercise prometheus state stay decoupled from
        # the registry.
        try:
            from harness.monitoring import harness_eval_judge_no_decision_total

            model = _resolve_judge_model(self.eval_model)
            harness_eval_judge_no_decision_total.labels(model=model).inc()
        except Exception:  # noqa: BLE001 — telemetry MUST NOT break grading
            pass

        return GraderResult(
            passed=False,
            score=0.0,
            details=f"no_decision: {reason}",
            grader_type="llm_judge",
            no_decision=True,
        )
