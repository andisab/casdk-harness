"""Unit tests for F15 — TranscriptBuilder must capture token usage
from SDK ResultMessage.

Before F15, the builder used ``getattr(usage, "input_tokens", 0)``
which silently returned 0 because the SDK ships ``usage`` as a
``dict[str, Any]``, not a typed object.  Every transcript reported
``total_tokens=0`` regardless of actual usage.

F15 switches to dict access (``usage.get("input_tokens")``) with
fallbacks for common key aliases (``prompt_tokens``,
``input_token_count``), and keeps the attribute-style branch as
forward-compat for a future typed SDK.
"""

from __future__ import annotations

from typing import Any

from harness.optimization.graders.transcript import TranscriptBuilder


class _ResultMessage:
    """Stand-in for claude_agent_sdk.types.ResultMessage with a dict ``usage``."""

    def __init__(
        self,
        *,
        usage: Any = None,
        num_turns: int = 1,
        is_error: bool = False,
        result: str = "",
    ) -> None:
        self.usage = usage
        self.num_turns = num_turns
        self.is_error = is_error
        self.result = result

    def __class__getattr__(self) -> str:  # so cls_name = 'ResultMessage'
        return "ResultMessage"


# Force class name to match the duck-type check in TranscriptBuilder.
_ResultMessage.__name__ = "ResultMessage"


class TestTokenCaptureFromDict:
    """The headline F15 case: dict-shaped usage must produce non-zero
    total_tokens."""

    def test_input_output_tokens_summed(self) -> None:
        builder = TranscriptBuilder()
        msg = _ResultMessage(
            usage={"input_tokens": 1200, "output_tokens": 350}
        )
        builder.add_message(msg)
        assert builder.build().total_tokens == 1550

    def test_alias_prompt_tokens(self) -> None:
        """Some SDK versions might use ``prompt_tokens``/``completion_tokens``
        — those map onto the same input/output buckets."""
        builder = TranscriptBuilder()
        msg = _ResultMessage(
            usage={"prompt_tokens": 800, "completion_tokens": 200}
        )
        builder.add_message(msg)
        assert builder.build().total_tokens == 1000

    def test_input_only(self) -> None:
        """Output absent → just input counts."""
        builder = TranscriptBuilder()
        msg = _ResultMessage(usage={"input_tokens": 500})
        builder.add_message(msg)
        assert builder.build().total_tokens == 500

    def test_empty_dict_means_zero(self) -> None:
        builder = TranscriptBuilder()
        msg = _ResultMessage(usage={})
        builder.add_message(msg)
        assert builder.build().total_tokens == 0

    def test_no_usage_means_zero(self) -> None:
        """usage=None → 0, no crash."""
        builder = TranscriptBuilder()
        msg = _ResultMessage(usage=None)
        builder.add_message(msg)
        assert builder.build().total_tokens == 0


class TestTokenCaptureForwardCompat:
    """If a future SDK ships a typed Usage object instead of a dict,
    the attribute-style fallback should still work."""

    def test_typed_usage_object(self) -> None:
        class _TypedUsage:
            input_tokens = 600
            output_tokens = 400

        builder = TranscriptBuilder()
        msg = _ResultMessage(usage=_TypedUsage())
        builder.add_message(msg)
        assert builder.build().total_tokens == 1000


class TestF15RegressionGuard:
    """Pin the source contract — the bug fix must remain in place."""

    def test_uses_dict_access_for_usage(self) -> None:
        import inspect

        from harness.optimization.graders import transcript

        src = inspect.getsource(transcript.TranscriptBuilder.add_message)
        # Must call .get() on the dict, not getattr (the bug).
        assert "usage.get(" in src, (
            "F15 regression: dict access lost; tokens will silently be 0"
        )
        assert "isinstance(usage, dict)" in src, (
            "F15 regression: dict branch removed"
        )
