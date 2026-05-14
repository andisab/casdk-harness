"""Unit tests for harness.agent_progress.

Focus is on F3 — :func:`extract_tool_calls` returns ALL tool_use blocks
from a message, not just the first.  The legacy
:func:`extract_tool_info` is kept for backwards compatibility and still
returns the first block.
"""

from __future__ import annotations

from typing import Any

from harness.agent_progress import (
    extract_text_preview,
    extract_tool_calls,
    extract_tool_info,
)


class _Block:
    """Minimal stand-in for a claude_agent_sdk content block.

    The real SDK types have ``type``, ``name``, ``input`` attributes;
    we only need the duck-type to match.
    """

    def __init__(self, type: str, name: str = "", input: Any = None) -> None:
        self.type = type
        self.name = name
        self.input = input if input is not None else {}


class _TextBlock:
    """Text-only block — has ``.text`` but no ``.type=='tool_use'``."""

    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Message:
    """Minimal stand-in for AssistantMessage with a content list."""

    def __init__(self, content: Any) -> None:
        self.content = content


# ---------------------------------------------------------------------------
# extract_tool_calls — the new F3 helper
# ---------------------------------------------------------------------------


class TestExtractToolCalls:
    """Per-message count must include every tool_use block."""

    def test_single_tool_use_block(self) -> None:
        msg = _Message([_Block("tool_use", name="Read", input={"file_path": "/a"})])
        calls = extract_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0][0] == "Read"
        assert "file_path=" in calls[0][1]

    def test_multiple_tool_use_blocks_all_counted(self) -> None:
        """A single AssistantMessage may carry parallel tool_use blocks
        (Read + Write + Bash).  All three must be counted."""
        msg = _Message(
            [
                _Block("tool_use", name="Read", input={"file_path": "/a"}),
                _Block("tool_use", name="Write", input={"file_path": "/b"}),
                _Block("tool_use", name="Bash", input={"command": "ls"}),
            ]
        )
        calls = extract_tool_calls(msg)
        assert len(calls) == 3
        names = [c[0] for c in calls]
        assert names == ["Read", "Write", "Bash"]

    def test_text_blocks_ignored(self) -> None:
        """Mixed content (text + tool_use) returns only the tool_use
        blocks, not the prose."""
        msg = _Message(
            [
                _TextBlock("I'll run two reads:"),
                _Block("tool_use", name="Read", input={"file_path": "/a"}),
                _Block("tool_use", name="Read", input={"file_path": "/b"}),
            ]
        )
        calls = extract_tool_calls(msg)
        assert len(calls) == 2

    def test_no_content_attribute_returns_empty(self) -> None:
        """ResultMessage / SystemMessage have no ``.content`` — return
        an empty list rather than crash."""

        class _NoContent:
            pass

        assert extract_tool_calls(_NoContent()) == []

    def test_string_content_returns_empty(self) -> None:
        msg = _Message("just a string")
        assert extract_tool_calls(msg) == []

    def test_task_subagent_summary(self) -> None:
        """Task tool's args summary uses subagent_type, not the first key."""
        msg = _Message(
            [
                _Block(
                    "tool_use",
                    name="Task",
                    input={"subagent_type": "python-expert", "prompt": "hi"},
                )
            ]
        )
        calls = extract_tool_calls(msg)
        assert calls[0][1] == "subagent_type=python-expert"

    def test_long_arg_value_truncated(self) -> None:
        """args_summary is truncated to 120 chars + ellipsis."""
        long_val = "x" * 500
        msg = _Message(
            [_Block("tool_use", name="Bash", input={"command": long_val})]
        )
        calls = extract_tool_calls(msg)
        assert "..." in calls[0][1]
        # 120 chars of value + "command=" prefix + "..." suffix.
        assert len(calls[0][1]) < 200


# ---------------------------------------------------------------------------
# extract_tool_info — legacy first-only helper
# ---------------------------------------------------------------------------


class TestExtractToolInfo:
    """The legacy helper returns the first tool_use only — still useful
    for boolean "did this message tool-call?" checks."""

    def test_returns_first_block_only(self) -> None:
        msg = _Message(
            [
                _Block("tool_use", name="Read", input={"file_path": "/a"}),
                _Block("tool_use", name="Write", input={"file_path": "/b"}),
            ]
        )
        info = extract_tool_info(msg)
        assert info is not None
        assert info[0] == "Read"

    def test_no_tool_use_returns_none(self) -> None:
        msg = _Message([_TextBlock("hello")])
        assert extract_tool_info(msg) is None


# ---------------------------------------------------------------------------
# extract_text_preview — leave untouched, but pin behavior
# ---------------------------------------------------------------------------


class TestExtractTextPreview:
    def test_truncates_long_text(self) -> None:
        msg = _Message([_TextBlock("a" * 500)])
        preview = extract_text_preview(msg, max_len=50)
        assert preview.endswith("...")
        assert len(preview) <= 53  # 50 + "..."

    def test_short_text_passes_through(self) -> None:
        msg = _Message([_TextBlock("hi")])
        assert extract_text_preview(msg) == "hi"
