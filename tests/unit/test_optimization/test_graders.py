"""Tests for the graders package (CGF Stage 3 Phase A.3)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.graders import (
    AgentTranscript,
    BaseGrader,
    CodeGrader,
    CompositeGrader,
    ConstraintAssertion,
    ContainsGrader,
    EvalScenario,
    ExactGrader,
    GraderResult,
    LLMJudgeGrader,
    NoToolAssertion,
    OrderingAssertion,
    RegexGrader,
    ScenarioSetup,
    SetupFile,
    ToolCall,
    ToolCalledAssertion,
    TrajectoryGrader,
    TranscriptBuilder,
    TranscriptMessage,
    build_grader,
)
from harness.optimization.graders import llm_judge as llm_judge_module

# =============================================================================
# Mock SDK message fixtures
# =============================================================================


@dataclass
class _MockTextBlock:
    text: str
    type: str = "text"


@dataclass
class _MockToolUseBlock:
    name: str
    input: dict
    id: str | None = None
    type: str = "tool_use"


@dataclass
class _MockToolResultBlock:
    tool_use_id: str
    content: Any
    type: str = "tool_result"


@dataclass
class _MockUsage:
    input_tokens: int = 0
    output_tokens: int = 0


def _make_message(cls_name: str, content: Any = None, **extras: Any):
    """Construct an SDK-shaped message with an arbitrary class name.

    The TranscriptBuilder uses ``type(message).__name__`` as a discriminator,
    so we synthesize subclasses on the fly.
    """
    fields = {"content": content, **extras}
    new_cls = type(cls_name, (), {})
    instance = new_cls()
    for k, v in fields.items():
        setattr(instance, k, v)
    return instance


def _scenario(**overrides: Any) -> EvalScenario:
    """Default minimal scenario; tests override specific fields."""
    base: dict[str, Any] = {
        "id": "test-scenario",
        "level": "unit",
        "prompt": "do the thing",
    }
    base.update(overrides)
    return EvalScenario(**base)


def _transcript(
    final_output: str = "",
    tool_calls: list[ToolCall] | None = None,
    messages: list[TranscriptMessage] | None = None,
    total_turns: int = 1,
) -> AgentTranscript:
    return AgentTranscript(
        messages=messages or [TranscriptMessage("assistant", final_output, 1)],
        tool_calls=tool_calls or [],
        final_output=final_output,
        total_turns=total_turns,
    )


# =============================================================================
# GraderResult basics
# =============================================================================


class TestGraderResult:
    def test_score_clamped_high(self) -> None:
        r = GraderResult(passed=True, score=1.5, details="x", grader_type="exact")
        assert r.score == 1.0

    def test_score_clamped_low(self) -> None:
        r = GraderResult(passed=False, score=-0.2, details="x", grader_type="exact")
        assert r.score == 0.0

    def test_default_no_decision_false(self) -> None:
        r = GraderResult(passed=True, score=1.0, details="x", grader_type="exact")
        assert r.no_decision is False
        assert r.arm is None


# =============================================================================
# TranscriptBuilder
# =============================================================================


class TestTranscriptBuilder:
    def test_build_empty(self) -> None:
        t = TranscriptBuilder().build()
        assert t.messages == []
        assert t.tool_calls == []
        assert t.final_output == ""
        assert t.total_turns == 0

    def test_assistant_text_message(self) -> None:
        b = TranscriptBuilder()
        b.add_message(
            _make_message("AssistantMessage", content=[_MockTextBlock("hello world")])
        )
        t = b.build()
        assert t.final_output == "hello world"
        assert len(t.messages) == 1
        assert t.messages[0].role == "assistant"
        assert t.messages[0].text == "hello world"

    def test_string_content_falls_back(self) -> None:
        b = TranscriptBuilder()
        b.add_message(_make_message("AssistantMessage", content="raw string"))
        t = b.build()
        assert t.final_output == "raw string"

    def test_tool_use_extracted(self) -> None:
        b = TranscriptBuilder()
        b.add_message(
            _make_message(
                "AssistantMessage",
                content=[
                    _MockTextBlock("calling tool"),
                    _MockToolUseBlock(
                        name="Read", input={"path": "/tmp/x"}, id="tu_1"
                    ),
                ],
            )
        )
        t = b.build()
        assert len(t.tool_calls) == 1
        assert t.tool_calls[0].tool_name == "Read"
        assert t.tool_calls[0].arguments == {"path": "/tmp/x"}
        assert t.tool_calls[0].tool_use_id == "tu_1"

    def test_tool_result_paired_with_tool_use(self) -> None:
        b = TranscriptBuilder()
        b.add_message(
            _make_message(
                "AssistantMessage",
                content=[_MockToolUseBlock(name="Read", input={}, id="tu_1")],
            )
        )
        b.add_message(
            _make_message(
                "UserMessage",
                content=[_MockToolResultBlock(tool_use_id="tu_1", content="file body")],
            )
        )
        t = b.build()
        assert t.tool_calls[0].result == "file body"

    def test_result_message_carries_aggregates(self) -> None:
        b = TranscriptBuilder()
        b.add_message(_make_message("AssistantMessage", content=[_MockTextBlock("hi")]))
        b.add_message(
            _make_message(
                "ResultMessage",
                content=None,
                num_turns=4,
                usage=_MockUsage(input_tokens=120, output_tokens=80),
                is_error=False,
            )
        )
        t = b.build()
        assert t.total_turns == 4
        assert t.total_tokens == 200
        assert t.is_error is False

    def test_result_message_error_captured(self) -> None:
        b = TranscriptBuilder()
        b.add_message(
            _make_message(
                "ResultMessage",
                content=None,
                is_error=True,
                result="agent timed out",
                num_turns=1,
            )
        )
        t = b.build()
        assert t.is_error is True
        assert "agent timed out" in t.error_message

    def test_unknown_message_class_ignored(self) -> None:
        b = TranscriptBuilder()
        b.add_message(_make_message("MysteryMessage", content="ignore me"))
        t = b.build()
        # MysteryMessage is treated as a system message with extracted text
        # — we don't crash on unknown classes.
        assert t.final_output == ""

    def test_all_text_concatenates(self) -> None:
        b = TranscriptBuilder()
        b.add_message(_make_message("AssistantMessage", content=[_MockTextBlock("first")]))
        b.add_message(_make_message("AssistantMessage", content=[_MockTextBlock("second")]))
        t = b.build()
        assert "first" in t.all_text
        assert "second" in t.all_text

    def test_tool_calls_named_filters(self) -> None:
        b = TranscriptBuilder()
        b.add_message(
            _make_message(
                "AssistantMessage",
                content=[
                    _MockToolUseBlock(name="Read", input={}, id="t1"),
                    _MockToolUseBlock(name="Bash", input={}, id="t2"),
                    _MockToolUseBlock(name="Read", input={}, id="t3"),
                ],
            )
        )
        t = b.build()
        reads = t.tool_calls_named("Read")
        assert len(reads) == 2
        assert all(r.tool_name == "Read" for r in reads)


# =============================================================================
# Deterministic graders
# =============================================================================


class TestExactGrader:
    @pytest.mark.asyncio
    async def test_passes_on_exact(self) -> None:
        g = ExactGrader(expected="hello")
        r = await g.grade(_transcript("hello"), _scenario())
        assert r.passed
        assert r.score == 1.0
        assert r.grader_type == "exact"

    @pytest.mark.asyncio
    async def test_fails_on_mismatch(self) -> None:
        g = ExactGrader(expected="hello")
        r = await g.grade(_transcript("goodbye"), _scenario())
        assert not r.passed
        assert r.score == 0.0
        assert "goodbye" in r.details

    @pytest.mark.asyncio
    async def test_strips_whitespace(self) -> None:
        g = ExactGrader(expected="hello")
        r = await g.grade(_transcript("  hello  "), _scenario())
        assert r.passed


class TestContainsGrader:
    @pytest.mark.asyncio
    async def test_finds_substring(self) -> None:
        g = ContainsGrader(needle="world")
        r = await g.grade(_transcript("hello world"), _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_misses_substring(self) -> None:
        g = ContainsGrader(needle="missing")
        r = await g.grade(_transcript("hello world"), _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_case_sensitive_default(self) -> None:
        g = ContainsGrader(needle="World")
        r = await g.grade(_transcript("hello world"), _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_case_insensitive_opt_in(self) -> None:
        g = ContainsGrader(needle="WORLD", case_insensitive=True)
        r = await g.grade(_transcript("hello world"), _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_any_message_field(self) -> None:
        msgs = [
            TranscriptMessage("assistant", "hello", 1),
            TranscriptMessage("user", "magic-token-here", 2),
        ]
        t = AgentTranscript(messages=msgs, final_output="hello")
        g = ContainsGrader(needle="magic-token", field="any_message")
        assert (await g.grade(t, _scenario())).passed


class TestRegexGrader:
    @pytest.mark.asyncio
    async def test_matches(self) -> None:
        g = RegexGrader(pattern=r"\d{3}")
        r = await g.grade(_transcript("error 404 not found"), _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_no_match(self) -> None:
        g = RegexGrader(pattern=r"^begin")
        r = await g.grade(_transcript("does not start with begin"), _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_ignorecase_flag(self) -> None:
        g = RegexGrader(pattern=r"hello", flags=("IGNORECASE",))
        r = await g.grade(_transcript("HELLO WORLD"), _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_invalid_flag_fails_cleanly(self) -> None:
        g = RegexGrader(pattern=r"x", flags=("BOGUS",))
        r = await g.grade(_transcript("x"), _scenario())
        assert not r.passed
        assert "BOGUS" in r.details

    @pytest.mark.asyncio
    async def test_invalid_pattern_fails_cleanly(self) -> None:
        g = RegexGrader(pattern=r"(unclosed")
        r = await g.grade(_transcript("x"), _scenario())
        assert not r.passed
        assert "invalid regex" in r.details


class TestCodeGrader:
    @pytest.mark.asyncio
    async def test_pass_when_assertion_holds(self) -> None:
        g = CodeGrader(code="assert 'ok' in transcript.final_output")
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.passed
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_fail_on_assertion_error(self) -> None:
        g = CodeGrader(code="assert False, 'boom'")
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed
        assert "boom" in r.details

    @pytest.mark.asyncio
    async def test_fail_on_runtime_exception(self) -> None:
        g = CodeGrader(code="raise ValueError('nope')")
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed
        assert "ValueError" in r.details

    @pytest.mark.asyncio
    async def test_can_use_re_and_json(self) -> None:
        code = (
            "import re\n"
            "matches = re.findall(r'\\d+', transcript.final_output)\n"
            "assert len(matches) == 2"
        )
        g = CodeGrader(code=code)
        r = await g.grade(_transcript("err 42 line 7"), _scenario())
        assert r.passed


# =============================================================================
# LLM-judge
# =============================================================================


@pytest.fixture(autouse=True)
def reset_llm_judge_client() -> None:
    """Reset the module-level shared client between tests so mocks don't leak."""
    llm_judge_module._shared_client = None
    yield
    llm_judge_module._shared_client = None


def _mock_judge_response(text: str) -> Any:
    response = MagicMock()
    block = MagicMock()
    block.text = text
    response.content = [block]
    return response


class TestLLMJudgeGrader:
    @pytest.mark.asyncio
    async def test_score_7_passes(self) -> None:
        with patch.object(
            llm_judge_module, "get_judge_client"
        ) as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("7")
            )
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score quality 1-7.")
            r = await g.grade(_transcript("good output"), _scenario())
            assert r.passed
            assert r.score == 1.0
            assert "judge=7/7" in r.details

    @pytest.mark.asyncio
    async def test_score_4_normalized_to_half(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("4")
            )
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score 1-7.", pass_threshold=0.7)
            r = await g.grade(_transcript("ok"), _scenario())
            # (4 - 1) / 6 = 0.5 < 0.7
            assert r.score == 0.5
            assert not r.passed

    @pytest.mark.asyncio
    async def test_score_with_extra_text_extracted(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("Score: 6 (good)")
            )
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score 1-7.", pass_threshold=0.6)
            r = await g.grade(_transcript("ok"), _scenario())
            assert r.score == pytest.approx(5 / 6)  # (6-1)/6 ≈ 0.833
            assert r.passed

    @pytest.mark.asyncio
    async def test_unparseable_response_retries(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    _mock_judge_response("???"),  # first attempt: junk
                    _mock_judge_response("4"),  # retry: clean
                ]
            )
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score 1-5.", pass_threshold=0.5)
            r = await g.grade(_transcript("ok"), _scenario())
            assert r.passed
            assert mock_client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_no_decision_after_two_unparseable(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("absolutely not a score")
            )
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score 1-5.")
            r = await g.grade(_transcript("ok"), _scenario())
            assert r.no_decision
            assert not r.passed
            assert mock_client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_no_decision_after_two_exceptions(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=RuntimeError("rate limit"))
            patched_client.return_value = mock_client

            g = LLMJudgeGrader(rubric="Score 1-5.")
            r = await g.grade(_transcript("ok"), _scenario())
            assert r.no_decision
            assert not r.passed

    def test_model_alias_resolves(self) -> None:
        from harness.config import MODEL_SHORTHAND_MAP
        from harness.optimization.graders.llm_judge import _resolve_judge_model

        # Aliases resolve to the canonical map's values — no duplication.
        assert _resolve_judge_model("opus") == MODEL_SHORTHAND_MAP["opus"]
        assert _resolve_judge_model("sonnet") == MODEL_SHORTHAND_MAP["sonnet"]
        assert _resolve_judge_model("haiku") == MODEL_SHORTHAND_MAP["haiku"]

    def test_model_alias_targets_current_versions(self) -> None:
        """Guards I14: the alias map MUST track current Anthropic model IDs.

        When Anthropic ships a newer minor (e.g. Sonnet 4.7), update
        ``MODEL_SHORTHAND_MAP`` in ``harness/config.py`` and bump these
        assertions in lockstep.  If this test fails because the alias
        moved forward by a minor version, you almost certainly want to
        update the test; if it fails because the alias regressed to an
        older version, that's the bug this test was written to catch.
        """
        from harness.config import MODEL_SHORTHAND_MAP

        # Current canonical pair as of 2026-05.  Unversioned forms
        # (major.minor without date suffix) auto-resolve to latest patch.
        assert MODEL_SHORTHAND_MAP["opus"] == "claude-opus-4-7"
        assert MODEL_SHORTHAND_MAP["sonnet"] == "claude-sonnet-4-6"
        assert MODEL_SHORTHAND_MAP["haiku"] == "claude-haiku-4-5"

    def test_llm_judge_imports_canonical_alias_map(self) -> None:
        """Single-source guarantee: llm_judge has no local alias table.

        Prevents the I14 regression — a stale ``_MODEL_ALIAS`` dict
        living inside ``llm_judge.py`` that drifts from ``config.py``.
        """
        from harness.optimization.graders import llm_judge as llm_judge_module

        assert not hasattr(llm_judge_module, "_MODEL_ALIAS"), (
            "llm_judge must not own a private _MODEL_ALIAS dict; "
            "import MODEL_SHORTHAND_MAP from harness.config instead"
        )

    def test_model_explicit_passthrough(self) -> None:
        from harness.optimization.graders.llm_judge import _resolve_judge_model

        # Full model IDs pass through unchanged
        assert (
            _resolve_judge_model("claude-3-7-sonnet-20250219")
            == "claude-3-7-sonnet-20250219"
        )

    def test_model_default_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from harness.config import MODEL_SHORTHAND_MAP
        from harness.optimization.graders.llm_judge import _resolve_judge_model

        monkeypatch.delenv("CGF_JUDGE_MODEL", raising=False)
        assert _resolve_judge_model(None) == MODEL_SHORTHAND_MAP["opus"]

    def test_model_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from harness.config import MODEL_SHORTHAND_MAP
        from harness.optimization.graders.llm_judge import _resolve_judge_model

        monkeypatch.setenv("CGF_JUDGE_MODEL", "haiku")
        assert _resolve_judge_model(None) == MODEL_SHORTHAND_MAP["haiku"]


# =============================================================================
# Trajectory grader
# =============================================================================


def _tc(name: str, turn: int, args: dict | None = None) -> ToolCall:
    return ToolCall(
        tool_name=name,
        arguments=args or {},
        result="",
        turn_number=turn,
        timestamp=time.time(),
    )


class TestTrajectoryAssertions:
    @pytest.mark.asyncio
    async def test_tool_called_passes(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1)])
        g = TrajectoryGrader(assertions=[ToolCalledAssertion(tool="Read")])
        r = await g.grade(t, _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_tool_called_min_count(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1), _tc("Read", 2)])
        g = TrajectoryGrader(
            assertions=[ToolCalledAssertion(tool="Read", min_count=3)]
        )
        r = await g.grade(t, _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_tool_called_with_arg_filter(self) -> None:
        t = _transcript(
            tool_calls=[
                _tc("Bash", 1, args={"cmd": "ls"}),
                _tc("Bash", 2, args={"cmd": "rm -rf /"}),
            ]
        )
        g = TrajectoryGrader(
            assertions=[
                ToolCalledAssertion(tool="Bash", with_arg={"cmd": "rm -rf /"})
            ]
        )
        r = await g.grade(t, _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_no_tool_passes_when_absent(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1)])
        g = TrajectoryGrader(assertions=[NoToolAssertion(tool="Bash")])
        r = await g.grade(t, _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_no_tool_fails_when_present(self) -> None:
        t = _transcript(tool_calls=[_tc("Bash", 1)])
        g = TrajectoryGrader(assertions=[NoToolAssertion(tool="Bash")])
        r = await g.grade(t, _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_ordering_passes(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1), _tc("Write", 2)])
        g = TrajectoryGrader(
            assertions=[OrderingAssertion(before="Read", after="Write")]
        )
        r = await g.grade(t, _scenario())
        assert r.passed

    @pytest.mark.asyncio
    async def test_ordering_violated(self) -> None:
        t = _transcript(tool_calls=[_tc("Write", 1), _tc("Read", 2)])
        g = TrajectoryGrader(
            assertions=[OrderingAssertion(before="Read", after="Write")]
        )
        r = await g.grade(t, _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_ordering_missing_tool(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1)])
        g = TrajectoryGrader(
            assertions=[OrderingAssertion(before="Read", after="Write")]
        )
        r = await g.grade(t, _scenario())
        assert not r.passed
        assert "never called" in r.details

    @pytest.mark.asyncio
    async def test_constraint_delegates_to_judge(self) -> None:
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("5")
            )
            patched_client.return_value = mock_client

            t = _transcript("agent did not use Bash")
            g = TrajectoryGrader(
                assertions=[ConstraintAssertion(text="Agent must not call Bash")]
            )
            r = await g.grade(t, _scenario())
            assert r.passed

    @pytest.mark.asyncio
    async def test_constraint_no_decision_treated_as_soft_pass(self) -> None:
        # Per design: a no_decision constraint should not nuke the
        # composite trajectory grader (the gate sees no_decision via
        # the LLM-judge path elsewhere).
        with patch.object(llm_judge_module, "get_judge_client") as patched_client:
            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_judge_response("nonsense")
            )
            patched_client.return_value = mock_client

            t = _transcript("ok")
            g = TrajectoryGrader(
                assertions=[ConstraintAssertion(text="Constraint")]
            )
            r = await g.grade(t, _scenario())
            assert r.passed
            assert "no_decision" in r.details

    @pytest.mark.asyncio
    async def test_empty_assertions_fails(self) -> None:
        g = TrajectoryGrader(assertions=[])
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed
        assert "zero assertions" in r.details

    @pytest.mark.asyncio
    async def test_partial_pass_score(self) -> None:
        t = _transcript(tool_calls=[_tc("Read", 1)])
        g = TrajectoryGrader(
            assertions=[
                ToolCalledAssertion(tool="Read"),  # passes
                NoToolAssertion(tool="Read"),  # fails
            ]
        )
        r = await g.grade(t, _scenario())
        assert not r.passed
        assert r.score == 0.5  # 1 of 2 passed


# =============================================================================
# Composite grader
# =============================================================================


class _AlwaysPass(BaseGrader):
    grader_type = "exact"

    async def grade(self, transcript, scenario):  # type: ignore[override]
        return GraderResult(passed=True, score=1.0, details="pass", grader_type="exact")


class _AlwaysFail(BaseGrader):
    grader_type = "exact"

    async def grade(self, transcript, scenario):  # type: ignore[override]
        return GraderResult(passed=False, score=0.0, details="fail", grader_type="exact")


class _NoDecision(BaseGrader):
    grader_type = "llm_judge"

    async def grade(self, transcript, scenario):  # type: ignore[override]
        return GraderResult(
            passed=False,
            score=0.0,
            details="no_decision: x",
            grader_type="llm_judge",
            no_decision=True,
        )


class TestCompositeGrader:
    @pytest.mark.asyncio
    async def test_and_all_pass(self) -> None:
        g = CompositeGrader(operator="and", graders=[_AlwaysPass(), _AlwaysPass()])
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.passed
        assert r.score == 1.0

    @pytest.mark.asyncio
    async def test_and_short_circuits_on_first_fail(self) -> None:
        spy = MagicMock(wraps=_AlwaysPass())
        spy.grade = AsyncMock(
            return_value=GraderResult(
                passed=True, score=1.0, details="ok", grader_type="exact"
            )
        )
        g = CompositeGrader(operator="and", graders=[_AlwaysFail(), spy])
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed
        spy.grade.assert_not_awaited()
        assert "short-circuited" in r.details

    @pytest.mark.asyncio
    async def test_or_first_pass_short_circuits(self) -> None:
        spy = MagicMock(wraps=_AlwaysFail())
        spy.grade = AsyncMock(
            return_value=GraderResult(
                passed=False, score=0.0, details="x", grader_type="exact"
            )
        )
        g = CompositeGrader(operator="or", graders=[_AlwaysPass(), spy])
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.passed
        spy.grade.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_or_all_fail(self) -> None:
        g = CompositeGrader(operator="or", graders=[_AlwaysFail(), _AlwaysFail()])
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed

    @pytest.mark.asyncio
    async def test_and_no_decision_propagates(self) -> None:
        g = CompositeGrader(operator="and", graders=[_AlwaysPass(), _NoDecision()])
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.no_decision
        assert not r.passed

    @pytest.mark.asyncio
    async def test_or_no_decision_overridden_by_pass(self) -> None:
        g = CompositeGrader(operator="or", graders=[_NoDecision(), _AlwaysPass()])
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.passed
        assert not r.no_decision

    @pytest.mark.asyncio
    async def test_or_no_decision_sticks_when_no_pass(self) -> None:
        g = CompositeGrader(operator="or", graders=[_NoDecision(), _AlwaysFail()])
        r = await g.grade(_transcript("ok"), _scenario())
        assert r.no_decision
        assert not r.passed

    @pytest.mark.asyncio
    async def test_empty_graders_fails(self) -> None:
        g = CompositeGrader(operator="and", graders=[])
        r = await g.grade(_transcript("ok"), _scenario())
        assert not r.passed
        assert "zero children" in r.details

    @pytest.mark.asyncio
    async def test_unknown_operator_raises(self) -> None:
        g = CompositeGrader(operator="xor", graders=[_AlwaysPass()])  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            await g.grade(_transcript("ok"), _scenario())


# =============================================================================
# build_grader factory
# =============================================================================


class TestBuildGrader:
    def test_exact(self) -> None:
        g = build_grader({"type": "exact", "expected": "x"})
        assert isinstance(g, ExactGrader)
        assert g.expected == "x"

    def test_contains(self) -> None:
        g = build_grader(
            {"type": "contains", "needle": "y", "case_insensitive": True}
        )
        assert isinstance(g, ContainsGrader)
        assert g.case_insensitive is True

    def test_regex_with_flags(self) -> None:
        g = build_grader(
            {"type": "regex", "pattern": r"\d+", "flags": ["IGNORECASE"]}
        )
        assert isinstance(g, RegexGrader)
        assert g.flags == ("IGNORECASE",)

    def test_code(self) -> None:
        g = build_grader({"type": "code", "code": "assert True"})
        assert isinstance(g, CodeGrader)

    def test_trajectory_with_assertions(self) -> None:
        g = build_grader(
            {
                "type": "trajectory",
                "assertions": [
                    {"kind": "tool_called", "tool": "Read"},
                    {"kind": "no_tool", "tool": "Bash"},
                    {"kind": "ordering", "before": "Read", "after": "Write"},
                    {"kind": "constraint", "text": "be careful"},
                ],
            }
        )
        assert isinstance(g, TrajectoryGrader)
        assert len(g.assertions) == 4
        assert isinstance(g.assertions[0], ToolCalledAssertion)
        assert isinstance(g.assertions[1], NoToolAssertion)
        assert isinstance(g.assertions[2], OrderingAssertion)
        assert isinstance(g.assertions[3], ConstraintAssertion)

    def test_llm_judge(self) -> None:
        g = build_grader(
            {
                "type": "llm_judge",
                "rubric": "score it",
                "pass_threshold": 0.6,
                "eval_model": "haiku",
                "pairwise": True,
            }
        )
        assert isinstance(g, LLMJudgeGrader)
        assert g.pass_threshold == 0.6
        assert g.eval_model == "haiku"
        assert g.pairwise is True

    def test_composite_recursive(self) -> None:
        g = build_grader(
            {
                "type": "composite",
                "operator": "and",
                "graders": [
                    {"type": "contains", "needle": "ok"},
                    {
                        "type": "composite",
                        "operator": "or",
                        "graders": [
                            {"type": "regex", "pattern": "yes|no"},
                            {"type": "exact", "expected": "maybe"},
                        ],
                    },
                ],
            }
        )
        assert isinstance(g, CompositeGrader)
        assert g.operator == "and"
        assert len(g.graders) == 2
        assert isinstance(g.graders[1], CompositeGrader)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError):
            build_grader({"type": "telepathy"})

    def test_unknown_trajectory_kind_raises(self) -> None:
        with pytest.raises(ValueError):
            build_grader(
                {
                    "type": "trajectory",
                    "assertions": [{"kind": "telepathy", "tool": "Read"}],
                }
            )


# =============================================================================
# Scenario sanity (just round-trips dataclass defaults)
# =============================================================================


class TestEvalScenario:
    def test_minimal_construction(self) -> None:
        s = EvalScenario(id="x", level="unit", prompt="do it")
        assert s.held_out is False
        assert s.tags == []
        assert isinstance(s.setup, ScenarioSetup)

    def test_setup_with_files(self) -> None:
        s = EvalScenario(
            id="x",
            level="unit",
            prompt="do it",
            setup=ScenarioSetup(files=[SetupFile(path="a.txt", content="hi")]),
        )
        assert s.setup.files[0].path == "a.txt"
