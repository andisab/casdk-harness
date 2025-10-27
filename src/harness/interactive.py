"""Interactive conversation mode for Claude Agent SDK Harness.

This module provides an interactive CLI for chatting with Claude agents,
combining the AgentSession infrastructure with Rich console UI.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import structlog
from claude_agent_sdk import AssistantMessage, ResultMessage, ToolUseBlock
from rich.console import Console

from harness.agent import AgentSession
from harness.cli import (
    get_user_input,
    parse_and_print_message,
    parser,
    print_goodbye_banner,
    print_welcome_banner,
)
from harness.config import get_config
from harness.monitoring import MetricsCollector

logger = structlog.get_logger(__name__)


async def run_interactive_session() -> None:
    """Run an interactive conversation session with the agent."""
    # Parse CLI arguments
    args = parser.parse_args()
    console = Console()

    # Get configuration
    config = get_config()

    # Override model if specified in args
    if args.model != "sonnet":
        config.claude_model = f"claude-{args.model}-4-20250514"
        logger.info("Model override", model=config.claude_model)

    # Determine whether to print stats
    print_stats = args.stats.lower() in ("true", "1", "yes")

    # Print welcome banner
    agent_name = "main"
    print_welcome_banner(console, agent_name, config.claude_model)

    # Create and start agent session
    session = AgentSession(agent_name=agent_name, config=config)
    session_start_time = datetime.now()

    try:
        # Start the session (begins metrics collection and checkpointing)
        await session.start()
        logger.info(
            "Interactive session initialized",
            session_id=session.session_id,
            checkpoint_interval=config.claude_checkpoint_interval,
        )

        # Attempt to recover from checkpoint if available
        recovered = await session.recover_from_checkpoint()
        if recovered:
            console.print(
                "[green]✓ Recovered from previous checkpoint[/green]\n",
                style="dim",
            )

        # Main conversation loop
        while True:
            try:
                # Get user input
                user_input = get_user_input(console)

                # Check for exit commands
                if user_input.lower() in ("exit", "quit", "q"):
                    logger.info("User requested exit")
                    break

                # Skip empty inputs
                if not user_input.strip():
                    continue

                # Record user prompt metric
                session.metrics.record_user_prompt(agent_name, session.session_id)

                # Execute agent task
                logger.info(
                    "Processing user input",
                    prompt_length=len(user_input),
                )

                async for message in session.execute(user_input):
                    # Print raw message if debugging
                    if args.print_raw.lower() in ("true", "1", "yes"):
                        console.print(
                            f"[dim]Raw message: {message}[/dim]\n",
                            style="dim",
                        )

                    # Record metrics based on message type
                    if isinstance(message, AssistantMessage):
                        session.metrics.record_agent_response(
                            agent_name, session.session_id
                        )

                        # Record message types
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                session.metrics.record_tool_call(
                                    agent_name, block.name, "success"
                                )
                                session.metrics.record_message_type(
                                    agent_name, "tool_use"
                                )
                            elif hasattr(block, "text"):
                                session.metrics.record_message_type(agent_name, "text")
                            elif hasattr(block, "thinking"):
                                session.metrics.record_message_type(
                                    agent_name, "thinking"
                                )

                    elif isinstance(message, ResultMessage):
                        # Update cache metrics from result
                        if hasattr(message, "usage"):
                            usage = message.usage
                            cache_read = usage.get("cache_read_input_tokens", 0)
                            cache_creation = usage.get("cache_creation_input_tokens", 0)
                            total_input = usage.get("input_tokens", 0)

                            if total_input > 0:
                                session.metrics.update_cache_metrics(
                                    agent_name,
                                    config.claude_model,
                                    cache_read,
                                    cache_creation,
                                    total_input,
                                )

                    # Parse and display message with Rich formatting
                    parse_and_print_message(
                        message,
                        console,
                        print_stats=print_stats,
                    )

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                console.print(
                    "\n[yellow]Interrupt received. Type 'exit' to quit or continue chatting.[/yellow]\n"
                )
                continue

            except Exception as e:
                logger.error(
                    "Error during message processing",
                    error=str(e),
                    exc_info=True,
                )
                console.print(
                    f"\n[red]Error: {str(e)}[/red]",
                    style="bold red",
                )
                console.print(
                    "[dim]You can continue chatting or type 'exit' to quit.[/dim]\n"
                )

    except Exception as e:
        logger.error(
            "Fatal error in interactive session",
            error=str(e),
            exc_info=True,
        )
        console.print(f"\n[red bold]Fatal Error: {str(e)}[/red bold]\n")
        sys.exit(1)

    finally:
        # Record session duration
        session_duration = (datetime.now() - session_start_time).total_seconds()
        session.metrics.record_interactive_session_duration(agent_name, session_duration)

        # Graceful shutdown
        logger.info(
            "Shutting down interactive session", session_duration_seconds=session_duration
        )
        print_goodbye_banner(console)

        try:
            await session.shutdown()
        except Exception as e:
            logger.error(
                "Error during session shutdown",
                error=str(e),
                exc_info=True,
            )
            console.print(
                f"\n[yellow]Warning: Error during shutdown: {str(e)}[/yellow]\n"
            )


def main() -> None:
    """Entry point for the interactive CLI."""
    # Check if running inside Docker
    in_docker = Path("/.dockerenv").exists()

    if not in_docker:
        print(
            "\n⚠️  Warning: Not running in Docker container.\n"
            "For production use, run via: make interactive\n"
        )

    try:
        asyncio.run(run_interactive_session())
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
