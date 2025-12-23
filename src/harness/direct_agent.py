"""Direct agent invocation - bypasses SDK Task tool limitation.

The Claude Agent SDK's Task tool doesn't recognize custom agents passed via
ClaudeAgentOptions(agents=...). This module provides direct invocation using
SDK query() with the agent's system prompt.

This is a workaround for GitHub issues #11205 and #12212.

Usage:
    from harness.direct_agent import call_agent, list_available_agents

    # List all available agents
    agents = list_available_agents()

    # Call an agent directly
    async for message in call_agent(
        agent_name="python-expert",
        prompt="Write a function to sort a list"
    ):
        print(message)

    # Call with verbose progress output
    async for message in call_agent(
        agent_name="research-team:lead-research-coordinator",
        prompt="Research quantum computing",
        verbose=True
    ):
        pass  # Progress is printed automatically
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Union

import structlog

# Environment variable for verbose mode inheritance
VERBOSE_ENV_VAR = "CLAUDE_AGENT_VERBOSE"


def _get_default_verbose() -> bool:
    """Get default verbose setting from environment or default to True."""
    env_val = os.environ.get(VERBOSE_ENV_VAR, "").lower()
    if env_val in ("0", "false", "no", "off"):
        return False
    # Default to True if not explicitly disabled
    return True

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    UserMessage,
)

from harness.agents.definitions import AGENT_DEFINITIONS
from harness.plugin_manager import PluginManager

if TYPE_CHECKING:
    from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

logger = structlog.get_logger(__name__)

# Module-level cache for plugin agents
_plugin_agents_cache: dict[str, SDKAgentDefinition] | None = None
_plugin_manager: PluginManager | None = None


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


def _extract_tool_info(message: Any) -> tuple[str, str] | None:
    """Extract tool name and args summary from a message with tool use."""
    if not hasattr(message, "content"):
        return None

    content = message.content
    if isinstance(content, str):
        return None

    if not isinstance(content, list):
        return None

    for block in content:
        # Check for tool_use block
        if hasattr(block, "type") and block.type == "tool_use":
            tool_name = getattr(block, "name", "unknown")
            tool_input = getattr(block, "input", {})

            # Create args summary
            args_summary = ""
            if isinstance(tool_input, dict):
                # For Task tool, show subagent type
                if tool_name == "Task" and "subagent_type" in tool_input:
                    args_summary = f"subagent_type={tool_input['subagent_type']}"
                # For other tools, show first key-value
                elif tool_input:
                    first_key = next(iter(tool_input))
                    first_val = str(tool_input[first_key])[:50]
                    if len(str(tool_input[first_key])) > 50:
                        first_val += "..."
                    args_summary = f"{first_key}={first_val}"

            return tool_name, args_summary

    return None


def _extract_text_preview(message: Any, max_len: int = 60) -> str:
    """Extract a text preview from a message."""
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
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def _get_plugin_base_path() -> Path:
    """Get the path to the plugins directory."""
    return Path(__file__).parent / "plugins"


def _load_plugin_agents() -> dict[str, Any]:
    """Load plugin agents if not already loaded.

    Returns:
        Dictionary mapping agent names to SDK AgentDefinition objects.
    """
    global _plugin_agents_cache, _plugin_manager

    if _plugin_agents_cache is None:
        plugin_base = _get_plugin_base_path()
        _plugin_manager = PluginManager(
            plugin_dirs=[plugin_base],
            enabled_plugins=None,
            use_sdk_only=False,
        )
        _plugin_manager.discover_plugins()
        _plugin_manager.load_all_plugins()
        _plugin_agents_cache = _plugin_manager.get_all_agents()

        logger.debug(
            "Loaded plugin agents for direct invocation",
            count=len(_plugin_agents_cache),
            agents=list(_plugin_agents_cache.keys()),
        )

    return _plugin_agents_cache


def list_available_agents() -> dict[str, str]:
    """List all available agents (harness + plugin).

    Returns:
        Dictionary mapping agent names to their descriptions.

    Example:
        >>> agents = list_available_agents()
        >>> for name, desc in agents.items():
        ...     print(f"{name}: {desc}")
    """
    agents: dict[str, str] = {}

    # Harness agents
    for name, agent in AGENT_DEFINITIONS.items():
        agents[name] = agent.description

    # Plugin agents
    plugin_agents = _load_plugin_agents()
    for name, agent in plugin_agents.items():
        agents[name] = agent.description

    return agents


def get_agent_info(agent_name: str) -> dict[str, Any]:
    """Get detailed information about an agent.

    Args:
        agent_name: Name of the agent (e.g., "python-expert",
                   "research-team:lead-research-coordinator")

    Returns:
        Dictionary with agent details:
        - name: Agent name
        - description: Agent description
        - model: Model to use (sonnet, opus, haiku)
        - tools: List of allowed tools or None for all
        - prompt: System prompt content
        - source: "harness" or "plugin"

    Raises:
        ValueError: If agent not found.

    Example:
        >>> info = get_agent_info("python-expert")
        >>> print(info["model"])
        sonnet
    """
    # Check harness agents first
    if agent_name in AGENT_DEFINITIONS:
        agent = AGENT_DEFINITIONS[agent_name]
        return {
            "name": agent_name,
            "description": agent.description,
            "model": agent.model,
            "tools": agent.tools,
            "prompt": agent.system_prompt,
            "max_turns": agent.max_turns,
            "source": "harness",
        }

    # Check plugin agents
    plugin_agents = _load_plugin_agents()
    if agent_name in plugin_agents:
        agent = plugin_agents[agent_name]
        # Plugin agents use 'max_turns' attribute if available, else default to 100
        max_turns = getattr(agent, "max_turns", 100)
        return {
            "name": agent_name,
            "description": agent.description,
            "model": agent.model,
            "tools": agent.tools,
            "prompt": agent.prompt,
            "max_turns": max_turns,
            "source": "plugin",
        }

    available = list(list_available_agents().keys())
    raise ValueError(
        f"Agent '{agent_name}' not found. Available agents: {available}"
    )


async def call_agent(
    agent_name: str,
    prompt: str,
    permission_mode: str = "acceptEdits",
    cwd: str = "/workspace",
    verbose: bool | None = None,
    on_progress: Callable[[str], None] | None = None,
    system_prompt_override: str | None = None,
    **extra_options: Any,
) -> AsyncIterator[Union[UserMessage, AssistantMessage, SystemMessage, ResultMessage, StreamEvent]]:
    """Call an agent directly, bypassing the Task tool.

    This function loads the agent's configuration and invokes it directly
    using the SDK's query() function.

    Args:
        agent_name: Name of the agent to invoke (e.g., "python-expert")
        prompt: The prompt to send to the agent
        permission_mode: Permission mode for tools (default: "acceptEdits")
        cwd: Working directory for the agent (default: "/workspace")
        verbose: Print progress updates to stderr. None=inherit from
                 CLAUDE_AGENT_VERBOSE env var (defaults to True if unset)
        on_progress: Optional callback for progress updates
        system_prompt_override: Optional system prompt to use instead of the
                               agent's default. Used for prompt optimization.
        **extra_options: Additional ClaudeAgentOptions parameters

    Yields:
        Messages from the agent conversation (UserMessage, AssistantMessage,
        SystemMessage, ResultMessage, or StreamEvent).

    Raises:
        ValueError: If agent not found.

    Example:
        >>> async for message in call_agent("python-expert", "Write a sort function"):
        ...     pass  # Progress printed automatically by default

        >>> # Quiet mode (no progress output)
        >>> async for message in call_agent(
        ...     "python-expert",
        ...     "Write a sort function",
        ...     verbose=False
        ... ):
        ...     if isinstance(message, AssistantMessage):
        ...         print(message.content)

        >>> # With custom system prompt for optimization
        >>> async for message in call_agent(
        ...     "python-expert",
        ...     "Write a sort function",
        ...     system_prompt_override="You are a Python expert. Always use type hints."
        ... ):
        ...     pass
    """
    agent_info = get_agent_info(agent_name)
    max_turns = agent_info.get("max_turns", 100)

    # Resolve verbose from env var if not explicitly set
    if verbose is None:
        verbose = _get_default_verbose()

    # Initialize progress tracker
    progress: AgentProgress | None = None
    if verbose:
        progress = AgentProgress(agent_name=agent_name, max_turns=max_turns)
        progress.print_status(progress.format_header())

    logger.info(
        "Invoking agent directly",
        agent=agent_name,
        source=agent_info["source"],
        model=agent_info["model"],
        max_turns=max_turns,
        verbose=verbose,
    )

    # Build options
    # Use override prompt if provided, otherwise use agent's default
    effective_prompt = system_prompt_override if system_prompt_override else agent_info["prompt"]

    options_dict: dict[str, Any] = {
        "system_prompt": effective_prompt,
        "model": agent_info["model"],
        "allowed_tools": agent_info["tools"] if agent_info["tools"] else None,
        "permission_mode": permission_mode,
        "cwd": cwd,
        "max_turns": max_turns,
    }
    options_dict.update(extra_options)

    options = ClaudeAgentOptions(**options_dict)

    # Call the agent
    try:
        async for message in query(prompt=prompt, options=options):
            # Track progress
            if progress:
                msg_type = type(message).__name__

                # Check for tool use
                tool_info = _extract_tool_info(message)
                if tool_info:
                    tool_name, args_summary = tool_info
                    progress.tool_calls += 1

                    # Track subagent spawns
                    if tool_name == "Task" and "subagent_type=" in args_summary:
                        subagent = args_summary.replace("subagent_type=", "")
                        progress.subagents_spawned.append(subagent)
                        progress.print_status(progress.format_subagent(subagent))
                    else:
                        progress.print_status(progress.format_tool_call(tool_name, args_summary))

                elif isinstance(message, AssistantMessage):
                    progress.turn_count += 1
                    preview = _extract_text_preview(message)
                    if preview:
                        progress.print_status(
                            progress.format_turn("AssistantMessage", preview)
                        )

                elif isinstance(message, ResultMessage):
                    progress.turn_count += 1
                    progress.print_status(
                        progress.format_turn("ResultMessage", "Tool result received")
                    )

            # Call progress callback if provided
            if on_progress:
                on_progress(f"{type(message).__name__}")

            yield message

    finally:
        # Print completion summary
        if progress:
            progress.print_status(progress.format_completion())


async def call_agent_simple(
    agent_name: str,
    prompt: str,
    verbose: bool | None = None,
    system_prompt_override: str | None = None,
    **kwargs: Any,
) -> str:
    """Call an agent and return just the text response.

    This is a simplified version that collects all text blocks from
    AssistantMessage responses and returns them as a single string.

    Args:
        agent_name: Name of the agent to invoke
        prompt: The prompt to send to the agent
        verbose: Print progress to stderr. None=inherit from CLAUDE_AGENT_VERBOSE
        system_prompt_override: Optional system prompt to use instead of default.
        **kwargs: Additional options passed to call_agent()

    Returns:
        The text response from the agent.

    Example:
        >>> response = await call_agent_simple("python-expert", "Explain list comprehensions")
        >>> print(response)

        >>> # With verbose progress
        >>> response = await call_agent_simple(
        ...     "research-team:lead-research-coordinator",
        ...     "Research quantum computing",
        ...     verbose=True
        ... )

        >>> # With custom system prompt for optimization
        >>> response = await call_agent_simple(
        ...     "python-expert",
        ...     "Write a sort function",
        ...     system_prompt_override="You are a Python expert. Always use type hints."
        ... )
    """
    responses: list[str] = []

    async for message in call_agent(
        agent_name,
        prompt,
        verbose=verbose,
        system_prompt_override=system_prompt_override,
        **kwargs,
    ):
        if isinstance(message, AssistantMessage) and hasattr(message, "content"):
            content = message.content
            if isinstance(content, str):
                responses.append(content)
            elif isinstance(content, list):
                for block in content:
                    if hasattr(block, "text"):
                        responses.append(block.text)

    return "\n".join(responses)


# CLI interface for standalone usage
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Directly invoke a subagent (bypasses Task tool)"
    )
    parser.add_argument("--list", action="store_true", help="List available agents")
    parser.add_argument("--info", metavar="AGENT", help="Show info about an agent")
    parser.add_argument("--agent", metavar="AGENT", help="Agent to invoke")
    parser.add_argument("--prompt", metavar="PROMPT", help="Prompt to send")
    parser.add_argument("--simple", action="store_true", help="Simple text output only")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show progress updates"
    )

    args = parser.parse_args()

    if args.list:
        agents = list_available_agents()
        print("Available agents:")
        for name, desc in sorted(agents.items()):
            desc_short = desc[:80] + "..." if len(desc) > 80 else desc
            print(f"  {name}: {desc_short}")

    elif args.info:
        info = get_agent_info(args.info)
        print(f"Agent: {info['name']}")
        print(f"Source: {info['source']}")
        print(f"Model: {info['model']}")
        print(f"Max Turns: {info['max_turns']}")
        print(f"Tools: {', '.join(info['tools']) if info['tools'] else 'All'}")
        print(f"\nDescription:\n{info['description']}")

    elif args.agent and args.prompt:

        async def run() -> None:
            if args.simple:
                response = await call_agent_simple(
                    args.agent, args.prompt, verbose=args.verbose
                )
                print(response)
            else:
                async for message in call_agent(
                    args.agent, args.prompt, verbose=args.verbose
                ):
                    if not args.verbose:
                        print(f"[{type(message).__name__}] {message}")

        asyncio.run(run())

    else:
        parser.print_help()
