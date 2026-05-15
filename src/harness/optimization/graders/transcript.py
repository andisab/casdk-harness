"""Agent transcript data model + builder (CGF Stage 3 Phase A.3).

Wraps the message stream produced by ``harness.subagent.call_agent`` into a
structured form that graders can introspect: every tool call extracted with
its arguments and result, every text message captured with its role and
turn number, plus aggregate counters (turns, tokens) drawn from the SDK's
``ResultMessage``.

Usage:

    builder = TranscriptBuilder()
    async for msg in subagent.call_agent("python-expert", prompt):
        builder.add_message(msg)
    transcript = builder.build()

The builder is incremental so the harness can also stream output to
telemetry / progress UX without buffering everything twice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

MessageRole = Literal["user", "assistant", "result", "system"]


@dataclass
class ToolCall:
    """One tool invocation extracted from the agent transcript.

    ``arguments`` and ``result`` are kept as parsed objects when the SDK
    provides them; ``result`` is the empty string if the harness never
    observed a matching ``tool_result`` block (rare but possible if the
    session was aborted mid-call).
    """

    tool_name: str
    arguments: dict[str, Any]
    result: str
    turn_number: int
    timestamp: float
    tool_use_id: str | None = None


@dataclass
class TranscriptMessage:
    """One assistant or user message, with extracted text content.

    Tool-use blocks are recorded separately on ``AgentTranscript.tool_calls``;
    this object only carries the surrounding prose.
    """

    role: MessageRole
    text: str
    turn_number: int


@dataclass
class AgentTranscript:
    """Full record of one agent run, structured for grader consumption."""

    messages: list[TranscriptMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_output: str = ""
    total_turns: int = 0
    total_tokens: int = 0
    is_error: bool = False
    error_message: str = ""

    @property
    def last_message(self) -> str:
        """Text of the last message, regardless of role.  Empty if none."""
        return self.messages[-1].text if self.messages else ""

    @property
    def all_text(self) -> str:
        """All message texts concatenated with newlines (any-message search)."""
        return "\n".join(m.text for m in self.messages)

    def tool_calls_named(self, tool_name: str) -> list[ToolCall]:
        """All tool calls with the given name (preserves order)."""
        return [tc for tc in self.tool_calls if tc.tool_name == tool_name]


class TranscriptBuilder:
    """Incrementally assembles an :class:`AgentTranscript` from SDK messages.

    Accepts any object with the SDK's duck-typed shape (``.content``
    attribute that's either ``str`` or a list of blocks; result-message
    types with ``num_turns``, ``total_tokens``, ``is_error``, etc.).
    Unknown message types are silently ignored — the builder is forgiving
    so SDK upgrades don't crash existing graders.
    """

    def __init__(self) -> None:
        self._messages: list[TranscriptMessage] = []
        self._tool_calls: list[ToolCall] = []
        self._tool_results_by_id: dict[str, str] = {}
        self._turn = 0
        self._final_output = ""
        self._total_turns = 0
        self._total_tokens = 0
        self._is_error = False
        self._error_message = ""

    def add_message(self, message: Any) -> None:
        """Consume one SDK message and update internal state."""
        cls_name = type(message).__name__

        # ResultMessage / SystemMessage carry aggregate counters
        if cls_name == "ResultMessage":
            self._total_turns = getattr(message, "num_turns", self._total_turns)
            usage = getattr(message, "usage", None)
            # F15: ``usage`` is ``dict[str, Any] | None`` on the SDK side
            # (see claude_agent_sdk.types.ResultMessage).  The previous
            # ``getattr(usage, "input_tokens", 0)`` always returned 0
            # because dicts have no attribute access — every transcript
            # reported ``total_tokens=0`` despite real usage data
            # arriving from the SDK.
            if isinstance(usage, dict):
                input_tokens = (
                    usage.get("input_tokens")
                    or usage.get("prompt_tokens")
                    or usage.get("input_token_count")
                    or 0
                )
                output_tokens = (
                    usage.get("output_tokens")
                    or usage.get("completion_tokens")
                    or usage.get("output_token_count")
                    or 0
                )
                self._total_tokens = int(input_tokens) + int(output_tokens)
            elif usage is not None:
                # Fallback for forward-compat: if a future SDK version
                # returns a typed object instead of a dict, still try.
                self._total_tokens = (
                    int(getattr(usage, "input_tokens", 0) or 0)
                    + int(getattr(usage, "output_tokens", 0) or 0)
                )
            self._is_error = bool(getattr(message, "is_error", False))
            if self._is_error:
                self._error_message = str(getattr(message, "result", ""))[:500]
            return

        # Skip system / init messages — no transcript content
        if cls_name == "SystemMessage":
            return

        role = self._role_from_class(cls_name)
        content = getattr(message, "content", None)
        text = self._extract_text(content)

        if text:
            self._turn += 1
            self._messages.append(
                TranscriptMessage(role=role, text=text, turn_number=self._turn)
            )
            if role == "assistant":
                self._final_output = text

        # Tool uses + tool results are nested in content blocks
        if isinstance(content, list):
            for block in content:
                self._process_block(block)

    def build(self) -> AgentTranscript:
        """Finalize and return the assembled transcript.

        Pairs up tool-use blocks with any matching tool_result blocks seen
        during ingestion, falling back to empty string when no result was
        observed (mid-stream abort).
        """
        for tc in self._tool_calls:
            if tc.tool_use_id and tc.tool_use_id in self._tool_results_by_id:
                tc.result = self._tool_results_by_id[tc.tool_use_id]

        # If total_turns wasn't reported by ResultMessage, fall back to count
        total_turns = self._total_turns or self._turn

        return AgentTranscript(
            messages=list(self._messages),
            tool_calls=list(self._tool_calls),
            final_output=self._final_output,
            total_turns=total_turns,
            total_tokens=self._total_tokens,
            is_error=self._is_error,
            error_message=self._error_message,
        )

    # ----- internals -----

    def _role_from_class(self, cls_name: str) -> MessageRole:
        if cls_name == "AssistantMessage":
            return "assistant"
        if cls_name == "UserMessage":
            return "user"
        if cls_name == "ResultMessage":
            return "result"
        return "system"

    def _extract_text(self, content: Any) -> str:
        """Pull plain text from SDK content (str or list of blocks)."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        chunks: list[str] = []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type in (None, "text") and hasattr(block, "text"):
                chunks.append(str(block.text))
        return "".join(chunks)

    def _process_block(self, block: Any) -> None:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            tool_input = getattr(block, "input", {}) or {}
            if not isinstance(tool_input, dict):
                tool_input = {}
            self._tool_calls.append(
                ToolCall(
                    tool_name=str(getattr(block, "name", "unknown")),
                    arguments=dict(tool_input),
                    result="",
                    turn_number=self._turn,
                    timestamp=time.time(),
                    tool_use_id=getattr(block, "id", None),
                )
            )
        elif block_type == "tool_result":
            tool_use_id = getattr(block, "tool_use_id", None)
            if tool_use_id is None:
                return
            result_content = getattr(block, "content", "")
            self._tool_results_by_id[tool_use_id] = self._stringify_result(
                result_content
            )

    def _stringify_result(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        chunks.append(str(block["text"]))
                    else:
                        chunks.append(str(block))
                else:
                    text = getattr(block, "text", None)
                    chunks.append(str(text) if text is not None else str(block))
            return "".join(chunks)
        return str(content)
