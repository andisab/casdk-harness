"""Terminal progress UX for streaming agent invocations.

Shared between standalone agent runners (`harness.subagent`) and any
future caller that streams `query()` messages and wants colored
turn-by-turn output to stderr.

Extracted from `harness.subagent` (formerly `direct_agent`) in
REFACTOR.md Phase 3 Step 4.
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any


# J1: signal markers we always want to surface in the preview even
# when prose preamble would push them past the truncation cap.
# Matches `[TAG_COMPLETE]`, `[TAG_COMPLETE:arg]`, `[TAG_ISSUES:arg]`
# for any UPPER_SNAKE TAG (RESEARCH, DESIGN, GENERATE, EVAL_DESIGN,
# ITERATE, EVAL, VALIDATE, OPTIMIZATION, ITERATION, EVALUATE, ...).
_SIGNAL_MARKER_RE = re.compile(r"\[[A-Z_]+_(?:COMPLETE|ISSUES)(?::[^\]]*)?\]")


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    WHITE = "\033[37m"


@dataclass
class AgentProgress:
    """Tracks agent execution progress for verbose output."""

    agent_name: str
    max_turns: int
    start_time: float = field(default_factory=time.time)
    turn_count: int = 0
    tool_calls: int = 0
    subagents_spawned: list[str] = field(default_factory=list)
    _last_print_len: int = 0

    def elapsed(self) -> str:
        """Return formatted elapsed time."""
        seconds = time.time() - self.start_time
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs:02d}s"

    def format_header(self) -> str:
        """Format the start header."""
        return (
            f"{Colors.CYAN}{Colors.BOLD}▶ [{self.agent_name}]{Colors.RESET} "
            f"{Colors.DIM}Starting (max_turns={self.max_turns}){Colors.RESET}"
        )

    def format_turn(self, msg_type: str, summary: str) -> str:
        """Format a turn progress line."""
        elapsed = self.elapsed()
        turn_info = f"{self.turn_count}/{self.max_turns}"
        return (
            f"{Colors.DIM}[{elapsed:>7}]{Colors.RESET} "
            f"{Colors.YELLOW}Turn {turn_info:>9}{Colors.RESET} "
            f"{Colors.WHITE}{msg_type:<18}{Colors.RESET} "
            f"{summary}"
        )

    def format_tool_call(self, tool_name: str, args_summary: str = "") -> str:
        """Format a tool call line."""
        elapsed = self.elapsed()
        icon = "🔧"
        if "task" in tool_name.lower():
            icon = "🚀"
        elif "read" in tool_name.lower():
            icon = "📖"
        elif "write" in tool_name.lower():
            icon = "✏️"
        elif "search" in tool_name.lower():
            icon = "🔍"
        elif "bash" in tool_name.lower():
            icon = "💻"

        line = (
            f"{Colors.DIM}[{elapsed:>7}]{Colors.RESET} "
            f"{icon} {Colors.MAGENTA}{tool_name}{Colors.RESET}"
        )
        if args_summary:
            line += f" {Colors.DIM}{args_summary}{Colors.RESET}"
        return line

    def format_subagent(self, subagent_name: str) -> str:
        """Format a subagent spawn line."""
        elapsed = self.elapsed()
        return (
            f"{Colors.DIM}[{elapsed:>7}]{Colors.RESET} "
            f"🚀 {Colors.BLUE}Spawning subagent:{Colors.RESET} "
            f"{Colors.CYAN}{subagent_name}{Colors.RESET}"
        )

    def format_completion(self) -> str:
        """Format the completion summary."""
        elapsed = self.elapsed()
        subagent_info = ""
        if self.subagents_spawned:
            subagent_info = f", {len(self.subagents_spawned)} subagents"
        return (
            f"{Colors.GREEN}{Colors.BOLD}✓ [{self.agent_name}]{Colors.RESET} "
            f"{Colors.DIM}Completed in {elapsed} "
            f"({self.turn_count} turns, {self.tool_calls} tool calls{subagent_info}){Colors.RESET}"
        )

    def print_status(self, line: str, newline: bool = True) -> None:
        """Print a status line to stderr."""
        if newline:
            print(line, file=sys.stderr, flush=True)
        else:
            # Overwrite current line
            print(f"\r{line}", end="", file=sys.stderr, flush=True)


def extract_tool_info(message: Any) -> tuple[str, str] | None:
    """Extract the first tool_use block's (name, args_summary).

    Kept for backwards compatibility — callers that only care about
    "did this message do a tool call?" can use it.  For accurate counting
    (one tool_use block = one tool call), use :func:`extract_tool_calls`
    instead, since a single AssistantMessage can carry multiple tool_use
    blocks (e.g. parallel Read + Write).
    """
    calls = extract_tool_calls(message)
    if not calls:
        return None
    return calls[0]


def extract_tool_calls(message: Any) -> list[tuple[str, str]]:
    """Extract ALL tool_use blocks from a message.

    Returns a list of ``(tool_name, args_summary)`` pairs in declaration
    order.  Empty list when the message has no tool_use blocks (text-only
    AssistantMessage, ResultMessage, SystemMessage).

    F3 fix: the prior :func:`extract_tool_info` returned the first
    tool_use block only, so the progress counter undercounted parallel
    tool calls (Read+Write+Bash in one assistant turn = 1 displayed
    instead of 3).
    """
    if not hasattr(message, "content"):
        return []

    content = message.content
    if isinstance(content, str):
        return []

    if not isinstance(content, list):
        return []

    out: list[tuple[str, str]] = []
    for block in content:
        if not hasattr(block, "type") or block.type != "tool_use":
            continue

        tool_name = getattr(block, "name", "unknown")
        tool_input = getattr(block, "input", {})

        args_summary = ""
        if isinstance(tool_input, dict):
            # For Task tool, show subagent type
            if tool_name == "Task" and "subagent_type" in tool_input:
                args_summary = f"subagent_type={tool_input['subagent_type']}"
            elif tool_input:
                first_key = next(iter(tool_input))
                first_val = str(tool_input[first_key])[:120]
                if len(str(tool_input[first_key])) > 120:
                    first_val += "..."
                args_summary = f"{first_key}={first_val}"

        out.append((tool_name, args_summary))

    return out


def extract_text_preview(message: Any, max_len: int = 150) -> str:
    """Extract a text preview from a message.

    Args:
        message: SDK message object that may have `content` attribute.
        max_len: Maximum length of returned preview.

    Returns:
        Cleaned text preview, truncated with "..." if longer than max_len.
    """
    if not hasattr(message, "content"):
        return ""

    content = message.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        texts = []
        for block in content:
            if hasattr(block, "text"):
                texts.append(block.text)
        text = " ".join(texts)
    else:
        return ""

    # Clean and truncate
    text = " ".join(text.split())  # Normalize whitespace
    if len(text) <= max_len:
        return text

    # J1: prefer a slice that ends with a CGF signal marker over a
    # plain head-of-text truncation.  Agent messages often have prose
    # preamble before `[*_COMPLETE:...]`, and a fixed-head slice clips
    # the very signal the operator is watching for in logs.
    match = _SIGNAL_MARKER_RE.search(text)
    if match is not None and match.end() > max_len:
        end = match.end()
        start = max(0, end - max_len)
        prefix = "..." if start > 0 else ""
        return prefix + text[start:end]

    return text[:max_len] + "..."
