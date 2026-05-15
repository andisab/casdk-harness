"""Phase A refinement 4.1 — eval-agent isolation contract.

These tests pin the invariants that keep the judge / architect / optimizer
sessions from leaking into each other.  They do not exercise the full
EvalHarness — they assert the *contract* that the harness relies on.

Three classes of assertion:

- :class:`TestJudgePromptIsolation` — the LLM judge sees only the
  rubric and a small surface of the agent transcript.  No orchestrator
  state, no version, no diff.
- :class:`TestJudgeModelResolution` — env-var precedence and the
  self-preference WARN log when judge == design model.
- :class:`TestJudgePromptHash` — hash is deterministic for the same
  (rubric, transcript), differs when either changes.
"""

from __future__ import annotations

import pytest

from harness.optimization.graders.llm_judge import (
    _resolve_judge_model,
    build_user_prompt,
    judge_prompt_hash,
)
from harness.optimization.graders.transcript import AgentTranscript

# ---------------------------------------------------------------------------
# TestJudgePromptIsolation — the heart of the isolation contract
# ---------------------------------------------------------------------------


class TestJudgePromptIsolation:
    """The judge user-prompt MUST be built only from rubric + transcript."""

    def test_prompt_contains_rubric(self) -> None:
        rubric = "Score 5 if the agent uses async/await correctly."
        transcript = AgentTranscript(final_output="async def foo(): ...")
        prompt = build_user_prompt(rubric, transcript)
        assert rubric in prompt

    def test_prompt_contains_transcript_surface(self) -> None:
        rubric = "Score 5 if correct."
        transcript = AgentTranscript(
            final_output="THE_AGENT_OUTPUT",
            total_turns=7,
            tool_calls=[],
        )
        prompt = build_user_prompt(rubric, transcript)
        assert "THE_AGENT_OUTPUT" in prompt
        assert "Total turns: 7" in prompt

    def test_prompt_excludes_optimizer_rationale(self) -> None:
        """If a transcript field somehow contained optimizer text, the judge
        prompt should not include it.  The contract is "transcript surface
        only" — final_output, turn count, tool-call count.  No raw messages
        list, no tool-call arguments dump."""
        transcript = AgentTranscript(
            final_output="agent reply",
            total_turns=3,
        )
        # Forge a "leak attempt": add a TranscriptMessage with optimizer-y text
        from harness.optimization.graders.transcript import TranscriptMessage

        transcript.messages.append(
            TranscriptMessage(
                role="user",
                text="OPTIMIZER_RATIONALE: I improved async handling",
                turn_number=1,
            )
        )
        prompt = build_user_prompt("R", transcript)
        assert "OPTIMIZER_RATIONALE" not in prompt

    def test_prompt_has_no_orchestrator_keys(self) -> None:
        """Pin against accidental additions: prompt must not contain any of
        these keys, which would all be signs of orchestrator-state leakage."""
        transcript = AgentTranscript(final_output="x", total_turns=1)
        prompt = build_user_prompt("rubric", transcript)
        forbidden = [
            "version",
            "iteration",
            "feedback",
            "baseline",
            "candidate",  # would imply gate decision leak
            "diff",
            "rationale",
            "previous_score",
            "incumbent",
        ]
        lowered = prompt.lower()
        for key in forbidden:
            assert key not in lowered, (
                f"judge prompt leaked orchestrator key {key!r}: {prompt!r}"
            )


# ---------------------------------------------------------------------------
# TestJudgeModelResolution — env precedence + self-preference WARN
# ---------------------------------------------------------------------------


class TestJudgeModelResolution:
    def test_explicit_param_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_JUDGE_MODEL", "sonnet")
        monkeypatch.delenv("CGF_DESIGN_MODEL", raising=False)
        assert _resolve_judge_model("opus") == "claude-opus-4-5-20250929"

    def test_env_when_no_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_JUDGE_MODEL", "sonnet")
        monkeypatch.delenv("CGF_DESIGN_MODEL", raising=False)
        assert _resolve_judge_model(None) == "claude-sonnet-4-20250514"

    def test_default_when_neither(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CGF_JUDGE_MODEL", raising=False)
        monkeypatch.delenv("CGF_DESIGN_MODEL", raising=False)
        assert _resolve_judge_model(None) == "claude-opus-4-5-20250929"

    def test_warn_when_judge_equals_design(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Self-preference risk: judge model resolves to the same value as
        the design/optimizer model.  Resolution must still succeed (we
        don't block the run), but a WARN must fire.

        Uses ``structlog.testing.capture_logs`` because the harness routes
        warnings through structlog, not stdlib ``logging`` — pytest's
        ``caplog`` fixture sees nothing.
        """
        import structlog

        monkeypatch.setenv("CGF_JUDGE_MODEL", "sonnet")
        monkeypatch.setenv("CGF_DESIGN_MODEL", "sonnet")
        with structlog.testing.capture_logs() as logs:
            resolved = _resolve_judge_model(None)
        assert resolved == "claude-sonnet-4-20250514"
        warn_events = [e for e in logs if e.get("log_level") == "warning"]
        assert any(
            "self-preference" in e.get("event", "").lower() for e in warn_events
        ), f"expected self-preference warning, got {warn_events!r}"

    def test_no_warn_when_different(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import structlog

        monkeypatch.setenv("CGF_JUDGE_MODEL", "opus")
        monkeypatch.setenv("CGF_DESIGN_MODEL", "sonnet")
        with structlog.testing.capture_logs() as logs:
            _resolve_judge_model(None)
        warn_events = [e for e in logs if e.get("log_level") == "warning"]
        assert not any(
            "self-preference" in e.get("event", "").lower() for e in warn_events
        ), f"unexpected self-preference warning: {warn_events!r}"


# ---------------------------------------------------------------------------
# TestJudgePromptHash — stable fingerprint for Phase D calibration
# ---------------------------------------------------------------------------


class TestJudgePromptHash:
    def test_deterministic(self) -> None:
        t = AgentTranscript(final_output="same", total_turns=2)
        h1 = judge_prompt_hash("r", t)
        h2 = judge_prompt_hash("r", t)
        assert h1 == h2

    def test_hash_changes_on_rubric_change(self) -> None:
        t = AgentTranscript(final_output="x", total_turns=1)
        h1 = judge_prompt_hash("rubric A", t)
        h2 = judge_prompt_hash("rubric B", t)
        assert h1 != h2

    def test_hash_changes_on_transcript_change(self) -> None:
        h1 = judge_prompt_hash("r", AgentTranscript(final_output="A", total_turns=1))
        h2 = judge_prompt_hash("r", AgentTranscript(final_output="B", total_turns=1))
        assert h1 != h2

    def test_hash_is_hex_sha256(self) -> None:
        h = judge_prompt_hash("r", AgentTranscript())
        # SHA-256 hex digest length
        assert len(h) == 64
        # All hex chars
        int(h, 16)


# ---------------------------------------------------------------------------
# TestTranscriptCostCapture — Step 3 prerequisite landed in Step 1
# ---------------------------------------------------------------------------


class TestTranscriptCostCapture:
    """``ResultMessage.total_cost_usd`` must flow through to
    :attr:`AgentTranscript.total_cost_usd`.  This is the prerequisite
    for the Step 3 cost gate — the cost gate's input must come from the
    same SDK field that feeds ``claude_code_cost_usage_USD_total`` in
    Prometheus, so the gate and operator dashboards agree."""

    def test_single_result_message_cost_captured(self) -> None:
        from harness.optimization.graders.transcript import TranscriptBuilder

        class _ResultMessage:
            usage = {"input_tokens": 100, "output_tokens": 50}
            num_turns = 1
            is_error = False
            result = ""
            total_cost_usd = 0.0123

        _ResultMessage.__name__ = "ResultMessage"

        builder = TranscriptBuilder()
        builder.add_message(_ResultMessage())
        assert builder.build().total_cost_usd == pytest.approx(0.0123)

    def test_multiple_result_messages_summed(self) -> None:
        """A single trial can produce multiple ResultMessages (sub-agent
        invocations).  Costs should sum, mirroring how the SDK's own
        Prom counter is monotonic across the trajectory."""
        from harness.optimization.graders.transcript import TranscriptBuilder

        class _RM:
            usage = {"input_tokens": 10, "output_tokens": 5}
            num_turns = 1
            is_error = False
            result = ""

            def __init__(self, cost: float) -> None:
                self.total_cost_usd = cost

        _RM.__name__ = "ResultMessage"

        builder = TranscriptBuilder()
        builder.add_message(_RM(0.01))
        builder.add_message(_RM(0.02))
        builder.add_message(_RM(0.005))
        assert builder.build().total_cost_usd == pytest.approx(0.035)

    def test_missing_cost_defaults_to_zero(self) -> None:
        from harness.optimization.graders.transcript import TranscriptBuilder

        class _RM:
            usage = {"input_tokens": 10, "output_tokens": 5}
            num_turns = 1
            is_error = False
            result = ""
            total_cost_usd = None

        _RM.__name__ = "ResultMessage"

        builder = TranscriptBuilder()
        builder.add_message(_RM())
        assert builder.build().total_cost_usd == 0.0

    def test_no_result_message_zero(self) -> None:
        from harness.optimization.graders.transcript import TranscriptBuilder

        builder = TranscriptBuilder()
        assert builder.build().total_cost_usd == 0.0
