"""Standalone agent invocation utility.

Use this module to invoke a named subagent from Python code that runs OUTSIDE
of an active SDK session (e.g., CGF runners that need to evaluate an agent
before there's an orchestrator session to dispatch from). Inside an active
SDK session, prefer Task-tool dispatch (`subagent_type="<name>"`).

Originally written as a Task-tool workaround (GitHub issues #11205, #12212);
those are now resolved (verified 2026-05-04, REFACTOR.md Phase 0). The module
remains for the standalone-invocation use case for which it remains the
correct approach.

Usage:
    from harness.subagent import call_agent, call_agent_simple, list_available_agents

    # List all available agents
    agents = list_available_agents()

    # Simple text-only invocation
    response = await call_agent_simple("python-expert", "Write a sort function")

    # Streaming invocation with terminal progress UX
    async for message in call_agent(
        agent_name="research-team:research-specialist",
        prompt="Research quantum computing hardware in 2026",
        verbose=True,
    ):
        pass  # Progress is printed automatically by AgentProgress
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Union

import structlog

from harness.agent_progress import (
    AgentProgress,
    Colors,
    extract_text_preview,
    extract_tool_info,
)

# Environment variable for verbose mode inheritance
VERBOSE_ENV_VAR = "CLAUDE_AGENT_VERBOSE"

# Environment variable for query timeout (in seconds)
QUERY_TIMEOUT_ENV_VAR = "CLAUDE_QUERY_TIMEOUT"
DEFAULT_QUERY_TIMEOUT = 600  # 10 minutes default

# Heartbeat warning interval (seconds without messages before warning)
HEARTBEAT_WARNING_INTERVAL = 60


def _get_query_timeout() -> float:
    """Get query timeout from environment or use default."""
    env_val = os.environ.get(QUERY_TIMEOUT_ENV_VAR, "")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    return DEFAULT_QUERY_TIMEOUT


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


def _get_plugin_base_path() -> Path:
    """Get the path to the plugins directory."""
    return Path(__file__).parent / "plugins"


def _load_plugin_agents() -> dict[str, Any]:
    """Load plugin agents if not already loaded.

    Matches AgentSession's discovery surface: swe-marketplace plugins
    first (so a locally-edited marketplace plugin shadows in-tree), then
    the in-tree `src/harness/plugins/` fallback. Without this, standalone
    invocations from harness.subagent (used by the multi-resource
    orchestrator and CGF runners) silently miss every marketplace-hosted
    plugin and fail with "Agent not found" mid-pipeline.

    Returns:
        Dictionary mapping agent names to SDK AgentDefinition objects.
    """
    global _plugin_agents_cache, _plugin_manager

    if _plugin_agents_cache is None:
        from harness.config import get_config

        config = get_config()

        plugin_dirs: list[Path] = []
        marketplace_path = config.swe_marketplace_resolved_path
        if marketplace_path is not None:
            marketplace_plugin_dir = marketplace_path / "plugins"
            if marketplace_plugin_dir.exists():
                plugin_dirs.append(marketplace_plugin_dir)
        plugin_dirs.append(_get_plugin_base_path())

        _plugin_manager = PluginManager(
            plugin_dirs=plugin_dirs,
            enabled_plugins=config.enabled_plugins_list,
        )
        _plugin_manager.discover()
        _plugin_agents_cache = _plugin_manager.get_all_agents()

        logger.debug(
            "Loaded plugin agents for direct invocation",
            count=len(_plugin_agents_cache),
            agents=list(_plugin_agents_cache.keys()),
        )

    return _plugin_agents_cache


def list_available_agents() -> dict[str, str]:
    """List all available agents (harness + plugin + workspace).

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
                   "research-team:research-specialist")

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
    cwd: str | None = None,
    verbose: bool | None = None,
    on_progress: Callable[[str], None] | None = None,
    system_prompt_override: str | None = None,
    model_override: str | None = None,
    timeout: float | None = None,
    **extra_options: Any,
) -> AsyncIterator[Union[UserMessage, AssistantMessage, SystemMessage, ResultMessage, StreamEvent]]:
    """Call an agent directly, bypassing the Task tool.

    This function loads the agent's configuration and invokes it directly
    using the SDK's query() function.

    Args:
        agent_name: Name of the agent to invoke (e.g., "python-expert")
        prompt: The prompt to send to the agent
        permission_mode: Permission mode for tools (default: "acceptEdits")
        cwd: Working directory for the agent (default: current directory)
        verbose: Print progress updates to stderr. None=inherit from
                 CLAUDE_AGENT_VERBOSE env var (defaults to True if unset)
        on_progress: Optional callback for progress updates
        system_prompt_override: Optional system prompt to use instead of the
                               agent's default. Used for prompt optimization.
        model_override: Override the agent's default model (sonnet/haiku/opus).
                       Useful for faster test evaluation.
        timeout: Query timeout in seconds. If None, uses CLAUDE_QUERY_TIMEOUT
                env var or default (600s).
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

    # Determine effective model (override takes precedence)
    effective_model = model_override if model_override else agent_info["model"]

    logger.info(
        "Invoking agent directly",
        agent=agent_name,
        source=agent_info["source"],
        model=effective_model,
        max_turns=max_turns,
        verbose=verbose,
    )

    # Build options
    # Use override prompt if provided, otherwise use agent's default
    effective_prompt = system_prompt_override if system_prompt_override else agent_info["prompt"]

    # Resolve working directory - use current directory if not specified
    import os
    effective_cwd = cwd if cwd else os.getcwd()

    options_dict: dict[str, Any] = {
        "system_prompt": effective_prompt,
        "model": effective_model,
        "allowed_tools": agent_info["tools"] if agent_info["tools"] else None,
        "permission_mode": permission_mode,
        "cwd": effective_cwd,
        "max_turns": max_turns,
    }
    options_dict.update(extra_options)

    options = ClaudeAgentOptions(**options_dict)

    # Call the agent with timeout protection
    # Use provided timeout or fall back to env var / default
    query_timeout = timeout if timeout is not None else _get_query_timeout()

    logger.debug(
        "Starting agent query with timeout",
        agent=agent_name,
        timeout_seconds=query_timeout,
    )

    try:
        async with asyncio.timeout(query_timeout):
            async for message in query(prompt=prompt, options=options):
                # Track progress
                if progress:
                    # Check for tool use
                    tool_info = extract_tool_info(message)
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
                        preview = extract_text_preview(message)
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

    except TimeoutError:
        elapsed = time.time() - progress.start_time if progress else 0
        logger.error(
            "Agent query timed out",
            agent=agent_name,
            timeout_seconds=query_timeout,
            elapsed_seconds=elapsed,
            turns_completed=progress.turn_count if progress else 0,
            tool_calls=progress.tool_calls if progress else 0,
        )
        if progress:
            progress.print_status(
                f"{Colors.RED}{Colors.BOLD}✗ [{agent_name}]{Colors.RESET} "
                f"{Colors.DIM}Timed out after {progress.elapsed()} "
                f"(timeout: {query_timeout}s){Colors.RESET}"
            )
        raise TimeoutError(
            f"Agent '{agent_name}' query timed out after {query_timeout}s. "
            f"Set {QUERY_TIMEOUT_ENV_VAR} env var to increase timeout."
        )

    finally:
        # Print completion summary
        if progress:
            progress.print_status(progress.format_completion())


async def call_agent_simple(
    agent_name: str,
    prompt: str,
    verbose: bool | None = None,
    system_prompt_override: str | None = None,
    model_override: str | None = None,
    timeout: float | None = None,
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
        model_override: Override the agent's model (sonnet/haiku for faster eval).
        timeout: Query timeout in seconds. If None, uses CLAUDE_QUERY_TIMEOUT
                env var or default (600s).
        **kwargs: Additional options passed to call_agent()

    Returns:
        The text response from the agent.

    Example:
        >>> response = await call_agent_simple("python-expert", "Explain list comprehensions")
        >>> print(response)

        >>> # With verbose progress
        >>> response = await call_agent_simple(
        ...     "research-team:research-specialist",
        ...     "Research quantum computing hardware in 2026",
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
        model_override=model_override,
        timeout=timeout,
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
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help=f"Query timeout in seconds (overrides {QUERY_TIMEOUT_ENV_VAR}, default: {DEFAULT_QUERY_TIMEOUT})",
    )

    args = parser.parse_args()

    # Apply timeout override if specified
    if args.timeout:
        os.environ[QUERY_TIMEOUT_ENV_VAR] = str(args.timeout)

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
