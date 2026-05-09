"""CLI tools and convenience functions for interactive agent sessions.

This module provides Rich console formatting for Claude Agent SDK messages,
making it easy to build interactive CLI interfaces for agent conversations.
"""

import argparse
import json
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
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from harness.agents.definitions import AGENT_DEFINITIONS

logger = structlog.get_logger(__name__)

# Track whether init message has been displayed this session
_init_message_shown = False

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
    default="True",
    help="Print session stats on exit (default: True)",
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


def get_user_input(console: Console) -> str:
    """
    Get user input and display it in a rich panel.

    Args:
        console: Rich console instance

    Returns:
        User input string
    """
    user_input = Prompt.ask("\n[bold yellow]You[/bold yellow]", console=console)
    logger.debug("User input received", input_length=len(user_input))
    print()
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
        if print_stats:
            result = message.subtype
            session_id = message.session_id
            duration_s = message.duration_ms / 1000
            cost_usd = message.total_cost_usd
            input_tokens = message.usage.get("input_tokens", 0)
            output_tokens = message.usage.get("output_tokens", 0)
            cache_read_tokens = message.usage.get("cache_read_input_tokens", 0)
            cache_creation_tokens = message.usage.get("cache_creation_input_tokens", 0)

            session_stats = {
                "Session ID": session_id,
                "Result": result,
                "Duration (s)": f"{duration_s:.2f}",
                "Cost (USD)": f"${cost_usd:.4f}" if cost_usd else "N/A",
                "Input Tokens": f"{input_tokens:,}",
                "Output Tokens": f"{output_tokens:,}",
                "Cache Read Tokens": f"{cache_read_tokens:,}",
                "Cache Creation Tokens": f"{cache_creation_tokens:,}",
            }

            if session_stats:
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

                # Log stats to structlog
                logger.info(
                    "Session completed",
                    session_id=session_id,
                    result=result,
                    duration_seconds=duration_s,
                    cost_usd=cost_usd,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                )


def print_welcome_banner(console: Console, agent_name: str, model: str) -> None:
    """
    Print a welcome banner for the interactive session.

    Args:
        console: Rich console instance
        agent_name: Name of the agent
        model: Model being used
    """
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


def print_goodbye_banner(console: Console) -> None:
    """
    Print a goodbye banner when exiting the session.

    Args:
        console: Rich console instance
    """
    goodbye_text = """
[bold green]Session Ended[/bold green]

[dim]Thank you for using Claude Agent SDK Harness![/dim]
[dim]All session data has been saved and checkpointed.[/dim]
    """
    panel = Panel(
        goodbye_text.strip(),
        title="👋 Goodbye",
        border_style="green",
        padding=(1, 2),
        expand=True,
    )
    console.print("\n", panel, end="\n\n")
    logger.info("Interactive session ended")
