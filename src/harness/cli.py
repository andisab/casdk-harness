"""CLI tools and convenience functions for interactive agent sessions.

This module provides Rich console formatting for Claude Agent SDK messages,
making it easy to build interactive CLI interfaces for agent conversations.
"""

import argparse
import contextlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import structlog
from claude_agent_sdk import (
    AssistantMessage,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Optional dependency: ASCII banner is decorative, fall back gracefully if absent.
try:
    from pyfiglet import Figlet  # type: ignore[import-not-found]

    _HAS_FIGLET = True
except ImportError:  # pragma: no cover
    _HAS_FIGLET = False

from harness.agents.definitions import AGENT_DEFINITIONS

logger = structlog.get_logger(__name__)

# Track whether init message has been displayed this session
_init_message_shown = False

# prompt_toolkit session — lazy-initialized so import-time cost is paid only
# when interactive mode actually runs. The history file is separate from
# readline's so neither side overwrites the other; readline still backs any
# `Prompt.ask()` calls in autonomous.py / cgf_session.py.
_PT_HISTORY_FILE = Path("/memory/.interactive_history_pt")
_pt_session: PromptSession | None = None

# Context window per model. The SDK doesn't expose this; default to 200K
# (current Sonnet/Opus/Haiku family). Override with HARNESS_CONTEXT_WINDOW
# for the 1M-token Opus variants or future models.
_MODEL_CONTEXT_WINDOW: dict[str, int] = {
    "claude-sonnet-4-5-20250929": 200_000,
    "claude-opus-4-5-20250929": 200_000,
    "claude-opus-4-7": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
}
_DEFAULT_CONTEXT_WINDOW = 200_000


@dataclass
class SessionTotals:
    """Per-session running totals for the status footer.

    Updated once per ResultMessage. The "context used" estimate uses only the
    most recent turn's prompt + completion size, since each turn includes the
    prior conversation in its input — summing across turns would double-count.
    """

    started_at: datetime = field(default_factory=datetime.now)
    turns: int = 0
    cumulative_input_tokens: int = 0
    cumulative_output_tokens: int = 0
    cumulative_cache_read_tokens: int = 0
    cumulative_cache_creation_tokens: int = 0
    cumulative_cost_usd: float = 0.0
    last_turn_total_tokens: int = 0  # input + cache_read + cache_creation + output

    def update_from_result(self, message: ResultMessage) -> None:
        """Record a completed turn into the running totals."""
        self.turns += 1
        usage = message.usage or {}
        in_t = usage.get("input_tokens", 0) or 0
        out_t = usage.get("output_tokens", 0) or 0
        cache_r = usage.get("cache_read_input_tokens", 0) or 0
        cache_c = usage.get("cache_creation_input_tokens", 0) or 0
        self.cumulative_input_tokens += in_t
        self.cumulative_output_tokens += out_t
        self.cumulative_cache_read_tokens += cache_r
        self.cumulative_cache_creation_tokens += cache_c
        if message.total_cost_usd:
            self.cumulative_cost_usd += message.total_cost_usd
        self.last_turn_total_tokens = in_t + cache_r + cache_c + out_t


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as `HhMMmSSs` / `MmSSs` / `Ss`."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m{seconds % 60:02d}s"


def _format_count(n: int) -> str:
    """Compact token-count formatting: 1234 → '1k', 65362 → '65k'."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n // 1000}k"
    return f"{n / 1_000_000:.1f}M"


def print_status_footer(
    console: Console,
    totals: SessionTotals,
    model: str,
    last_result: ResultMessage | None = None,
) -> None:
    """Print a one-line dim status footer after each completed turn.

    Includes cumulative cache totals (read / write) and a short session_id
    slug (first 8 chars of UUID, git-shorthash style) — both genuinely
    add to the footer's at-a-glance value without making it unwieldy.

    Format:
        ─ 4m12s · turn 7 · ctx 22% · 16k in / 4k out · cache 65k r / 22k w · $0.0631 · sonnet · 61011358 ─
    """
    elapsed = (datetime.now() - totals.started_at).total_seconds()
    ctx_window = _MODEL_CONTEXT_WINDOW.get(model, _DEFAULT_CONTEXT_WINDOW)
    ctx_pct = min(
        100, int(round(100 * totals.last_turn_total_tokens / max(1, ctx_window)))
    )
    # Compact model label — strip the date suffix for readability.
    model_label = model.replace("claude-", "").split("-")[0] if model else "?"
    sid_slug = (
        last_result.session_id[:8] if last_result and last_result.session_id else None
    )
    parts = [
        f"─ {_format_duration(elapsed)}",
        f"turn {totals.turns}",
        f"ctx {ctx_pct}%",
        f"{_format_count(totals.cumulative_input_tokens)} in"
        f" / {_format_count(totals.cumulative_output_tokens)} out",
        f"cache {_format_count(totals.cumulative_cache_read_tokens)} r"
        f" / {_format_count(totals.cumulative_cache_creation_tokens)} w",
        f"${totals.cumulative_cost_usd:.4f}",
        model_label,
    ]
    if sid_slug:
        parts.append(sid_slug)
    line = " · ".join(parts) + " ─"
    console.print(f"[dim]{line}[/dim]\n")


def _build_session_totals_table(
    totals: SessionTotals, model: str, duration_s: float
) -> Table:
    """Build the cumulative-totals table used by /stats and the exit summary."""
    table = Table(title="Session Totals", show_header=False, title_style="bold blue")
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="yellow")
    table.add_row("Turns", str(totals.turns))
    table.add_row("Duration", _format_duration(duration_s))
    table.add_row("Input Tokens", f"{totals.cumulative_input_tokens:,}")
    table.add_row("Output Tokens", f"{totals.cumulative_output_tokens:,}")
    table.add_row("Cost (USD)", f"${totals.cumulative_cost_usd:.4f}")
    ctx_window = _MODEL_CONTEXT_WINDOW.get(model, _DEFAULT_CONTEXT_WINDOW)
    ctx_pct = min(
        100, int(round(100 * totals.last_turn_total_tokens / max(1, ctx_window)))
    )
    table.add_row("Context Used", f"{ctx_pct}% of {ctx_window:,}")
    table.add_row("Model", model)
    return table


def _build_last_turn_table(message: ResultMessage) -> Table:
    """Build the last-turn breakdown table used by /stats."""
    table = Table(title="Last Turn", show_header=False, title_style="bold blue")
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="yellow")
    usage = message.usage or {}
    table.add_row("Session ID", message.session_id or "—")
    table.add_row("Result", message.subtype or "—")
    table.add_row("Duration", f"{message.duration_ms / 1000:.2f}s")
    table.add_row(
        "Cost (USD)",
        f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "N/A",
    )
    table.add_row("Input", f"{usage.get('input_tokens', 0):,}")
    table.add_row("Output", f"{usage.get('output_tokens', 0):,}")
    table.add_row("Cache Read", f"{usage.get('cache_read_input_tokens', 0):,}")
    table.add_row("Cache Created", f"{usage.get('cache_creation_input_tokens', 0):,}")
    return table


def render_stats(
    totals: SessionTotals,
    last_result: ResultMessage | None,
    model: str,
    console: Console,
) -> None:
    """Render cumulative + last-turn tables side-by-side.

    Used by both the interactive `/stats` slash command and the
    session-exit summary. If no turn has completed yet, only the
    cumulative table is printed.
    """
    duration_s = (datetime.now() - totals.started_at).total_seconds()
    totals_table = _build_session_totals_table(totals, model, duration_s)
    if last_result is None:
        console.print(totals_table)
        console.print(
            "[dim](no completed turns yet — last-turn breakdown unavailable)[/dim]\n"
        )
        return
    last_turn_table = _build_last_turn_table(last_result)
    console.print(Columns([totals_table, last_turn_table], equal=False, expand=False))


def render_help(console: Console) -> None:
    """Print the list of available harness-side slash commands."""
    table = Table(title="Commands", show_header=False, title_style="bold blue")
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="dim")
    table.add_row("/stats", "Show session statistics (cumulative + last turn)")
    table.add_row("/help", "Show this help")
    table.add_row("/clear", "Clear the screen")
    table.add_row("exit | quit | q", "End the session")
    console.print(table)
    console.print(
        "\n[dim]Plugin commands (e.g. /cgf-agents:cgf) are forwarded to the agent.[/dim]\n"
    )


def handle_slash_command(
    user_input: str,
    console: Console,
    totals: SessionTotals,
    last_result: ResultMessage | None,
    model: str,
) -> bool:
    """Try to handle a harness-side slash command.

    Returns True if the input was a recognized meta command (caller should
    skip agent dispatch), False otherwise so the caller can forward to the
    agent (for SDK/plugin commands like `/cgf-agents:cgf`).

    Slash commands are intercepted client-side — they never reach the
    agent, consume no tokens, and incur no API cost.
    """
    cmd = user_input.strip().lower()
    if cmd == "/stats":
        render_stats(totals, last_result, model, console)
        return True
    if cmd == "/help":
        render_help(console)
        return True
    if cmd == "/clear":
        console.clear()
        return True
    return False


def _get_prompt_session() -> PromptSession:
    """Return a singleton prompt_toolkit session for interactive input.

    prompt_toolkit gives us bracketed paste (multi-line works), persistent
    file-backed history, Ctrl+R reverse search, and optional vi-mode via the
    HARNESS_INPUT_MODE env var. Replaces the bare Rich Prompt.ask() that fell
    back to dumb-tty input().
    """
    global _pt_session
    if _pt_session is None:
        with contextlib.suppress(OSError):
            _PT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        vi_mode = os.environ.get("HARNESS_INPUT_MODE", "emacs").lower() == "vi"
        _pt_session = PromptSession(
            history=FileHistory(str(_PT_HISTORY_FILE)),
            vi_mode=vi_mode,
            multiline=False,  # Esc-Enter still toggles multi-line for power users
            enable_history_search=True,
            mouse_support=False,  # mouse breaks terminal copy/paste in some emulators
        )
    return _pt_session

# Plugin skills and agents discovered during startup (set by AgentSession)
_plugin_skills: list[str] = []
_plugin_agents: list[str] = []


def set_plugin_skills(skills: list[str]) -> None:
    """Set the list of discovered plugin skills for display in SystemMessage.

    Called by AgentSession after plugin discovery to make skills available
    for display when SDK sends SystemMessage.

    Args:
        skills: List of plugin skill names
    """
    global _plugin_skills
    _plugin_skills = skills


def set_plugin_agents(agents: list[str]) -> None:
    """Set the list of discovered plugin agents for display in SystemMessage.

    Called by AgentSession after plugin discovery to make agents available
    for display when SDK sends SystemMessage.

    Args:
        agents: List of plugin agent names
    """
    global _plugin_agents
    _plugin_agents = agents

# --------------------------------
# Parse runtime args from CLI
# --------------------------------

parser = argparse.ArgumentParser(
    description="Claude Agent SDK Harness - Interactive Mode"
)
parser.add_argument(
    "--stats",
    "-s",
    default="False",
    help="Print the full stats table after every turn (default: False; use /stats on demand instead)",
)
parser.add_argument(
    "--model",
    "-m",
    default="sonnet",
    help="Model to use (default: sonnet)",
)
parser.add_argument(
    "--profile",
    "-p",
    default=None,
    help="Configuration profile to load (default: None)",
)
parser.add_argument(
    "--print-raw",
    "-pr",
    default="False",
    help="Print raw messages for debugging (default: False)",
)
parser.add_argument(
    "--quiet",
    "-q",
    action="store_true",
    help="Suppress all system logs (only show chat messages)",
)
parser.add_argument(
    "--debug",
    "-d",
    action="store_true",
    help=(
        "Verbose mode: DEBUG-level logs, raw SDK messages, per-turn stats "
        "table. Overrides --quiet if both are set."
    ),
)


# --------------------------------
# Convenience functions for printing messages
# --------------------------------


def display_session_info(session_info: dict, console: Console) -> None:
    """Display session info panel without making an API call.

    Used for recovered sessions to show session summary immediately.

    Args:
        session_info: Dict from AgentSession.get_session_info()
        console: Rich console instance
    """
    global _init_message_shown
    if _init_message_shown:
        return
    _init_message_shown = True

    # Build MCP server status
    mcp_status = []
    for server in session_info.get("mcp_servers", []):
        status_icon = "✓" if server.get("status") == "connected" else "✗"
        mcp_status.append(f"{status_icon} {server.get('name')}")

    # Agents with source breakdown
    harness_agents = session_info.get("harness_agents", [])
    plugin_agents = session_info.get("plugin_agents", [])
    total_agents = len(harness_agents) + len(plugin_agents)

    agent_summary = f"{total_agents} available" if total_agents > 0 else "None"

    # Skills with source breakdown
    base_skills = session_info.get("base_skills", [])
    plugin_skills = session_info.get("plugin_skills", [])
    total_skills = len(base_skills) + len(plugin_skills)
    skill_summary = f"{total_skills} available" if total_skills > 0 else "None"

    # Build the full summary
    init_summary = (
        f"Session: {session_info.get('session_id', 'N/A')}\n"
        f"Model: {session_info.get('model', 'N/A')}\n"
        f"MCP Servers: {', '.join(mcp_status) if mcp_status else 'None'}\n"
        f"Sub-agents: {agent_summary}"
    )
    if harness_agents:
        init_summary += f"\n  → harness: {', '.join(sorted(harness_agents))}"
    if plugin_agents:
        init_summary += f"\n  → plugins: {', '.join(sorted(plugin_agents))}"

    init_summary += f"\nSkills: {skill_summary}"
    if base_skills:
        init_summary += f"\n  → base: {', '.join(sorted(base_skills))}"
    if plugin_skills:
        init_summary += f"\n  → plugins: {', '.join(sorted(plugin_skills))}"

    print_rich_message("system", init_summary, console)
    logger.debug("Local session info displayed", session_id=session_info.get("session_id"))


def print_rich_message(
    type: Literal["user", "assistant", "tool_use", "tool_result", "system"],
    message: str,
    console: Console,
) -> None:
    """
    Print a message in a Rich panel with styling based on message type.

    Args:
        type: Type of message (user, assistant, tool_use, tool_result, system)
        message: Message content to display
        console: Rich console instance
    """
    styles = {
        "user": {
            "message_style": "bold yellow",
            "panel_title": "User Prompt",
            "border_style": "yellow",
        },
        "assistant": {
            "message_style": "bold green",
            "panel_title": "Assistant",
            "border_style": "green",
        },
        "tool_use": {
            "message_style": "bold blue",
            "panel_title": "Tool Use",
            "border_style": "blue",
        },
        "tool_result": {
            "message_style": "bold magenta",
            "panel_title": "Tool Result",
            "border_style": "magenta",
        },
        "system": {
            "message_style": "bold cyan",
            "panel_title": "System Message",
            "border_style": "cyan",
        },
    }

    # For tool results, try to apply JSON syntax highlighting
    if type == "tool_result" and is_json_string(message):
        panel_content = Syntax(message, "json", theme="monokai", line_numbers=False)
    else:
        panel_content = Text(message, style=styles[type]["message_style"])

    # Use expand=True for consistent full-width panels that adapt to terminal size
    panel = Panel(
        panel_content,
        title=styles[type]["panel_title"],
        border_style=styles[type]["border_style"],
        expand=True,
    )
    console.print(panel, end="\n\n")

    # Log to structlog as well for observability. DEBUG, not INFO — at INFO
    # this fires once per panel and clutters the chat surface.
    logger.debug(
        "Message displayed",
        message_type=type,
        message_length=len(message),
    )


def is_json_string(text: str) -> bool:
    """Check if a string is valid JSON.

    Args:
        text: String to check

    Returns:
        True if text is valid JSON, False otherwise
    """
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def format_tool_result(content: any) -> str:
    """
    Format tool result content nicely, handling nested JSON strings.

    Args:
        content: Tool result content (string, dict, or list)

    Returns:
        Formatted string representation
    """
    if isinstance(content, str):
        # Try to parse as JSON and format it
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            return content
    elif isinstance(content, list):
        # Handle list of content blocks (common format)
        formatted_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                # Try to parse the text field as JSON
                text_content = item["text"]
                try:
                    parsed_json = json.loads(text_content)
                    formatted_json = json.dumps(parsed_json, indent=2)
                    formatted_parts.append(formatted_json)
                except json.JSONDecodeError:
                    # If not JSON, just use the text as-is
                    formatted_parts.append(text_content)
            else:
                # For other dict structures, format as JSON
                formatted_parts.append(json.dumps(item, indent=2))
        return "\n\n".join(formatted_parts)
    else:
        # For other types, convert to JSON
        return json.dumps(content, indent=2)


async def get_user_input(console: Console) -> str:
    """
    Get user input via prompt_toolkit (paste-aware, history-aware).

    Must be awaited from within a running asyncio loop — uses prompt_toolkit's
    async API because the sync `session.prompt(...)` calls `asyncio.run()`
    internally, which raises when an outer loop is already running.

    Args:
        console: Rich console instance (used for leading whitespace; the
            actual input rendering is done by prompt_toolkit).

    Returns:
        User input string. Raises EOFError on Ctrl+D, KeyboardInterrupt on Ctrl+C
        (interactive.py's main loop catches these).
    """
    console.print()  # blank line above the prompt for breathing room
    session = _get_prompt_session()
    user_input = await session.prompt_async(HTML("<b><ansiyellow>You</ansiyellow></b>: "))
    logger.debug("User input received", input_length=len(user_input))
    console.print()
    return user_input


def _handle_dict_message(message: dict, console: Console, quiet: bool) -> None:
    """
    Handle custom dict messages from the harness (e.g., budget warnings).

    Args:
        message: Custom dict message with type/subtype fields
        console: Rich console instance
        quiet: Whether to suppress system messages
    """
    msg_type = message.get("type")
    subtype = message.get("subtype")

    # Handle context budget warnings
    if msg_type == "system" and subtype == "context_budget_warning":
        # Always show budget warnings, even in quiet mode
        level = message.get("level", "warning")
        content = message.get("content", "")
        tokens_used = message.get("tokens_used", 0)
        tokens_remaining = message.get("tokens_remaining", 0)
        percent_used = message.get("percent_used", 0)

        # Color coding based on severity
        colors = {
            "warning": "yellow",
            "urgent": "orange1",
            "critical": "red bold",
        }
        border_style = colors.get(level, "yellow")

        # Create a panel with budget info
        budget_panel = Panel(
            content,
            title=f"Context Budget ({level.upper()})",
            subtitle=f"{tokens_used:,} / {tokens_used + tokens_remaining:,} tokens ({percent_used:.0f}%)",
            border_style=border_style,
            expand=True,
        )
        console.print(budget_panel)

    elif msg_type == "system":
        # Generic system message from harness
        if quiet:
            return
        content = message.get("content", str(message))
        print_rich_message("system", content, console)

    else:
        # Unknown dict message - log and display raw
        logger.debug("Unknown dict message type", message=message)
        if not quiet:
            print_rich_message("system", str(message), console)


def parse_and_print_message(
    message: Message | dict,
    console: Console,
    print_stats: bool = False,
    quiet: bool = False,
) -> None:
    """
    Parse and print a message based on its type and content.

    Args:
        message: SDK message or custom dict message to parse and display
        console: Rich console instance
        print_stats: Whether to print session statistics for ResultMessage
        quiet: Whether to suppress system messages
    """
    logger.debug(
        "parse_and_print_message called",
        message_type=type(message).__name__,
        quiet=quiet,
    )

    # Handle custom dict messages (e.g., budget warnings from harness)
    if isinstance(message, dict):
        _handle_dict_message(message, console, quiet)
        return

    # Assistant messages include TextBlock, ToolUseBlock, ThinkingBlock
    # https://docs.claude.com/en/api/agent-sdk/python#content-block-types
    if isinstance(message, SystemMessage):
        # Skip system messages in quiet mode
        if quiet:
            return

        # Show init message once at startup with formatted summary
        if message.subtype == "init":
            global _init_message_shown
            if _init_message_shown:
                return
            _init_message_shown = True

            data = message.data
            # Build concise session info
            mcp_status = []
            for server in data.get("mcp_servers", []):
                status_icon = "✓" if server.get("status") == "connected" else "✗"
                mcp_status.append(f"{status_icon} {server.get('name')}")

            # Agents grouped by source
            harness_agents = sorted(AGENT_DEFINITIONS.keys())
            plugin_agents = sorted(_plugin_agents)
            total_agents = len(harness_agents) + len(plugin_agents)

            # Skills grouped by source (base from SDK, plugin from discovery)
            base_skills = sorted(data.get("skills", []))
            plugin_skills = sorted(_plugin_skills)
            total_skills = len(base_skills) + len(plugin_skills)

            # Build init summary
            init_summary = (
                f"Session: {data.get('session_id', 'N/A')[:8]}...\n"
                f"Model: {data.get('model', 'N/A')}\n"
                f"MCP Servers: {', '.join(mcp_status) if mcp_status else 'None'}\n"
                f"Tools: {len(data.get('tools', []))} available\n"
                f"Sub-agents: {total_agents} available"
            )
            if harness_agents:
                init_summary += f"\n  → harness: {', '.join(harness_agents)}"
            if plugin_agents:
                init_summary += f"\n  → plugins: {', '.join(plugin_agents)}"

            init_summary += f"\nSkills: {total_skills} available"
            if base_skills:
                init_summary += f"\n  → base: {', '.join(base_skills)}"
            if plugin_skills:
                init_summary += f"\n  → plugins: {', '.join(plugin_skills)}"

            print_rich_message("system", init_summary, console)
            logger.debug(
                "Session init message displayed",
                session_id=data.get("session_id"),
                harness_agents=len(harness_agents),
                plugin_agents=len(plugin_agents),
                total_agents=total_agents,
            )
            return

        if message.subtype == "compact_boundary":
            compact_meta = message.data.get("compact_metadata", {})
            print_rich_message(
                "system",
                f"Compaction completed\n"
                f"Pre-compaction tokens: {compact_meta.get('pre_tokens', 'N/A')}\n"
                f"Trigger: {compact_meta.get('trigger', 'N/A')}",
                console,
            )
        else:
            print_rich_message(
                "system",
                json.dumps(message.data, indent=2),
                console,
            )

    elif isinstance(message, AssistantMessage):
        # Coalesce ThinkingBlocks: an assistant turn often emits many of them,
        # and rendering one full green Panel per block buries the actual reply.
        # One dim "Thinking…" line per turn, regardless of block count.
        thinking_announced = False
        for block in message.content:
            if isinstance(block, TextBlock):
                print_rich_message("assistant", block.text, console)
            elif isinstance(block, ToolUseBlock):
                tool_input_str = json.dumps(block.input, indent=2)
                print_rich_message(
                    "tool_use",
                    f"Tool: <{block.name}>\n\n{tool_input_str}",
                    console,
                )
            elif isinstance(block, ThinkingBlock) and not thinking_announced:
                console.print("[dim italic]Thinking…[/dim italic]\n")
                thinking_announced = True

    elif isinstance(message, UserMessage):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                formatted_content = format_tool_result(block.content)
                print_rich_message("tool_result", formatted_content, console)

    elif isinstance(message, ResultMessage):
        # Per-turn data is captured by:
        #   - compact status footer (printed by interactive.py / autonomous.py)
        #   - /stats command (cumulative + last-turn tables on demand)
        #   - Prometheus metrics (SDK emits token/cost via claude_code_*)
        #   - OTel tracer spans (session_id, duration)
        # The full Session Stats table renders only when print_stats=True
        # (--stats=true on CLI; default is False).
        if print_stats:
            usage = message.usage or {}
            session_stats = {
                "Session ID": message.session_id,
                "Result": message.subtype,
                "Duration (s)": f"{message.duration_ms / 1000:.2f}",
                "Cost (USD)": (
                    f"${message.total_cost_usd:.4f}"
                    if message.total_cost_usd
                    else "N/A"
                ),
                "Input Tokens": f"{usage.get('input_tokens', 0):,}",
                "Output Tokens": f"{usage.get('output_tokens', 0):,}",
                "Cache Read Tokens": f"{usage.get('cache_read_input_tokens', 0):,}",
                "Cache Creation Tokens": (
                    f"{usage.get('cache_creation_input_tokens', 0):,}"
                ),
            }
            stats_table = Table(
                title="Session Stats",
                show_header=False,
                title_style="bold blue",
            )
            stats_table.add_column(style="cyan", no_wrap=True)
            stats_table.add_column(style="yellow")
            for stat_name, stat_value in session_stats.items():
                stats_table.add_row(stat_name, str(stat_value))
            console.print(stats_table, end="\n")


def print_welcome_banner(console: Console, agent_name: str, model: str) -> None:
    """
    Print a welcome banner for the interactive session.

    Args:
        console: Rich console instance
        agent_name: Name of the agent
        model: Model being used
    """
    # Optional ASCII art banner — figlet adds visual identity at startup
    # without dominating the screen. Skip silently if pyfiglet isn't installed
    # so the harness still starts cleanly in stripped-down environments.
    if _HAS_FIGLET:
        with contextlib.suppress(Exception):
            ascii_art = Figlet(font="small").renderText("CASDK HARNESS")
            console.print(f"[bright_cyan]{ascii_art}[/bright_cyan]", end="")

    banner_text = f"""
[bold cyan]Claude Agent SDK Harness[/bold cyan]
[dim]Interactive mode - chat with Claude as an autonomous development agent[/dim]

[yellow]Agent:[/yellow] {agent_name}  [dim]|[/dim]  [yellow]Model:[/yellow] {model}

[dim]Try these:[/dim]
  [green]"List files in /workspace"[/green]
  [green]"Create a hello world script"[/green]
  [green]"What MCP servers are available?"[/green]

[dim]Type 'exit' or 'quit' to end. New here? See QUICKSTART.md[/dim]
    """
    panel = Panel(
        banner_text.strip(),
        title="Welcome",
        border_style="bright_blue",
        padding=(1, 2),
        expand=True,
    )
    console.print(panel, end="\n\n")
    logger.info("Interactive session started", agent=agent_name, model=model)


def print_autonomous_welcome_banner(console: Console, model: str) -> None:
    """
    Print a welcome banner for the autonomous session.

    Mirrors `print_welcome_banner` (same ASCII art + panel framing) but
    tailored to non-interactive autonomous mode — no "try these" prompts,
    different mode label.

    Args:
        console: Rich console instance
        model: Model being used
    """
    if _HAS_FIGLET:
        with contextlib.suppress(Exception):
            ascii_art = Figlet(font="small").renderText("CASDK HARNESS")
            console.print(f"[bright_cyan]{ascii_art}[/bright_cyan]", end="")

    banner_text = f"""
[bold cyan]Claude Agent SDK Harness[/bold cyan]
[dim]Autonomous mode - spec-driven development with Tech Lead Q&A + Coding Agent[/dim]

[yellow]Mode:[/yellow] autonomous  [dim]|[/dim]  [yellow]Model:[/yellow] {model}

[dim]Workflow:[/dim]
  [green]1.[/green] Initializer runs Tech Lead Q&A to refine SPEC.md
  [green]2.[/green] Continuation loop executes tasks until complete
  [green]3.[/green] Progress saved to sessions/ — Ctrl+C is interruptible

[dim]Press Ctrl+C to stop. New here? See QUICKSTART.md[/dim]
    """
    panel = Panel(
        banner_text.strip(),
        title="Welcome",
        border_style="bright_blue",
        padding=(1, 2),
        expand=True,
    )
    console.print(panel, end="\n\n")
    logger.info("Autonomous session started", model=model)


def print_goodbye_banner(
    console: Console,
    totals: SessionTotals | None = None,
    last_result: ResultMessage | None = None,
    model: str | None = None,
) -> None:
    """Print the session-end panel.

    When `totals` is provided, the panel embeds the cumulative + last-turn
    stats tables side-by-side above the persistence-confirmation line.
    When omitted, the panel shows only the persistence line (used by
    modes that don't track SessionTotals).
    """
    renderables: list = []

    if totals is not None:
        duration_s = (datetime.now() - totals.started_at).total_seconds()
        totals_table = _build_session_totals_table(totals, model or "?", duration_s)
        if last_result is not None:
            last_turn_table = _build_last_turn_table(last_result)
            renderables.append(
                Columns([totals_table, last_turn_table], equal=False, expand=False)
            )
        else:
            renderables.append(totals_table)
        renderables.append(Text(""))  # blank-line spacer

    renderables.append(
        Text.from_markup("[dim]Session data saved and checkpointed.[/dim]")
    )

    panel = Panel(
        Group(*renderables),
        title="Session ended. Goodbye! 👋",
        border_style="green",
        padding=(1, 2),
        expand=True,
    )
    console.print("\n", panel, end="\n\n")
    logger.info("Interactive session ended")
