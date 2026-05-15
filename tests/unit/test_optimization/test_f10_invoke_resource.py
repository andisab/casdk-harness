"""Unit tests for F10 — ``_invoke_from_resource`` must construct
``ClaudeAgentOptions`` with sane fields (no ``allowed_tools=None``) and
must wire ``plugins`` / ``skills="all"`` / ``setting_sources=["project"]``
so that scenarios actually invoke skills/agents instead of crashing
with ``'NoneType' object is not iterable``.

Before F10, the harness passed ``allowed_tools=spec["tools"]`` where
``spec["tools"]`` was ``None`` for any skill file with no ``tools:``
frontmatter.  The SDK iterated over allowed_tools internally and raised
``TypeError``, which the wrapper caught and turned into a no-decision
transcript — every grader scored 0 and the gate trivially "promoted"
0-vs-0 ties.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.eval_harness.runner import EvalHarness


@pytest.fixture
def skill_file_no_tools(tmp_path: Path) -> Path:
    """A typical skill file with no ``tools:`` in frontmatter.

    Triggers the F10 bug: ``spec["tools"]`` is ``None`` → previously
    fed straight into ``ClaudeAgentOptions(allowed_tools=None)``.
    """
    f = tmp_path / "skill.md"
    f.write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill\n"
        "model: sonnet\n"
        "---\n"
        "Skill body content here.\n",
    )
    return f


@pytest.fixture
def agent_file_with_tools(tmp_path: Path) -> Path:
    """An agent file with explicit ``tools:`` field."""
    f = tmp_path / "agent.md"
    f.write_text(
        "---\n"
        "name: test-agent\n"
        "description: A test agent\n"
        "model: sonnet\n"
        "tools: Read, Write, Bash\n"
        "max_turns: 50\n"
        "---\n"
        "Agent body content here.\n",
    )
    return f


# ---------------------------------------------------------------------------
# _invoke_from_resource — allowed_tools must be a list, never None
# ---------------------------------------------------------------------------


class TestInvokeFromResourceOptions:
    """Pin the SDK-options contract that F10 enforces."""

    @pytest.mark.asyncio
    async def test_skill_with_no_tools_uses_empty_list(
        self, skill_file_no_tools: Path, tmp_path: Path
    ) -> None:
        """A skill without ``tools:`` frontmatter must construct
        ``ClaudeAgentOptions(allowed_tools=[])``, not ``None``.  This is
        the headline F10 bug — passing None tripped TypeError inside
        the SDK because something downstream iterated it."""
        captured: dict[str, Any] = {}

        def fake_options(**kwargs: Any) -> MagicMock:
            captured.update(kwargs)
            return MagicMock()

        async def fake_query(prompt: str, options: Any) -> Any:
            return
            yield  # never reached, but keeps function async-generator

        with patch(
            "claude_agent_sdk.ClaudeAgentOptions", side_effect=fake_options
        ), patch(
            "claude_agent_sdk.query", side_effect=fake_query
        ):
            harness = EvalHarness()
            agen = harness._invoke_from_resource(
                resource=skill_file_no_tools,
                prompt="hello",
                cwd=tmp_path,
            )
            # Drain the generator (no messages yielded by the fake).
            async for _ in agen:
                pass

        # F10 invariant: allowed_tools must be a list (empty allowed).
        assert "allowed_tools" in captured, "ClaudeAgentOptions kwargs missing"
        assert captured["allowed_tools"] is not None, (
            "F10 regression: allowed_tools=None passed to SDK"
        )
        assert isinstance(captured["allowed_tools"], list), (
            f"allowed_tools should be list, got {type(captured['allowed_tools'])}"
        )

    @pytest.mark.asyncio
    async def test_agent_with_tools_preserves_list(
        self, agent_file_with_tools: Path, tmp_path: Path
    ) -> None:
        """When a resource declares tools, they pass through unchanged."""
        captured: dict[str, Any] = {}

        def fake_options(**kwargs: Any) -> MagicMock:
            captured.update(kwargs)
            return MagicMock()

        async def fake_query(prompt: str, options: Any) -> Any:
            return
            yield

        with patch(
            "claude_agent_sdk.ClaudeAgentOptions", side_effect=fake_options
        ), patch(
            "claude_agent_sdk.query", side_effect=fake_query
        ):
            harness = EvalHarness()
            agen = harness._invoke_from_resource(
                resource=agent_file_with_tools,
                prompt="hello",
                cwd=tmp_path,
            )
            async for _ in agen:
                pass

        assert captured["allowed_tools"] == ["Read", "Write", "Bash"]

    @pytest.mark.asyncio
    async def test_plugin_skills_setting_sources_wired(
        self, skill_file_no_tools: Path, tmp_path: Path
    ) -> None:
        """F2-pattern wiring: plugins=[], skills='all', setting_sources=
        ['project'] must all be set.  Without these, the SDK creates a
        sandbox view that rejects plugin-skill names like
        ``cgf-agents:cgf-prompt-optimizer``."""
        captured: dict[str, Any] = {}

        def fake_options(**kwargs: Any) -> MagicMock:
            captured.update(kwargs)
            return MagicMock()

        async def fake_query(prompt: str, options: Any) -> Any:
            return
            yield

        with patch(
            "claude_agent_sdk.ClaudeAgentOptions", side_effect=fake_options
        ), patch(
            "claude_agent_sdk.query", side_effect=fake_query
        ):
            harness = EvalHarness()
            agen = harness._invoke_from_resource(
                resource=skill_file_no_tools,
                prompt="hello",
                cwd=tmp_path,
            )
            async for _ in agen:
                pass

        assert "skills" in captured, "F10 regression: skills= not set"
        assert captured["skills"] == "all", (
            f"F10 regression: skills should be 'all', got {captured['skills']!r}"
        )
        assert "setting_sources" in captured, (
            "F10 regression: setting_sources= not set"
        )
        assert captured["setting_sources"] == ["project"], (
            f"F10 regression: setting_sources should be ['project'], "
            f"got {captured['setting_sources']!r}"
        )
        # plugins should be a list (possibly empty if discovery failed).
        assert "plugins" in captured, "F10 regression: plugins= not set"
        assert isinstance(captured["plugins"], list)

    @pytest.mark.asyncio
    async def test_max_turns_from_frontmatter(
        self, agent_file_with_tools: Path, tmp_path: Path
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_options(**kwargs: Any) -> MagicMock:
            captured.update(kwargs)
            return MagicMock()

        async def fake_query(prompt: str, options: Any) -> Any:
            return
            yield

        with patch(
            "claude_agent_sdk.ClaudeAgentOptions", side_effect=fake_options
        ), patch(
            "claude_agent_sdk.query", side_effect=fake_query
        ):
            harness = EvalHarness()
            agen = harness._invoke_from_resource(
                resource=agent_file_with_tools,
                prompt="hello",
                cwd=tmp_path,
            )
            async for _ in agen:
                pass

        assert captured["max_turns"] == 50

    @pytest.mark.asyncio
    async def test_messages_pass_through_from_sdk(
        self, skill_file_no_tools: Path, tmp_path: Path
    ) -> None:
        """End-to-end: when the SDK yields messages, _invoke_from_resource
        passes them through.  Sanity check that the F10 fix doesn't
        accidentally swallow messages."""
        sentinel_messages = [MagicMock(name="msg1"), MagicMock(name="msg2")]

        async def fake_query(prompt: str, options: Any) -> Any:
            for msg in sentinel_messages:
                yield msg

        with patch(
            "claude_agent_sdk.ClaudeAgentOptions", return_value=MagicMock()
        ), patch(
            "claude_agent_sdk.query", side_effect=fake_query
        ):
            harness = EvalHarness()
            collected: list[Any] = []
            agen = harness._invoke_from_resource(
                resource=skill_file_no_tools,
                prompt="hello",
                cwd=tmp_path,
            )
            async for msg in agen:
                collected.append(msg)

        assert collected == sentinel_messages
