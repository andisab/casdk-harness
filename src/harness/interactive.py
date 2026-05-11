"""Interactive conversation mode for Claude Agent SDK Harness.

This module provides an interactive CLI for chatting with Claude agents,
combining the AgentSession infrastructure with Rich console UI.
"""

import asyncio
import atexit
import contextlib
import readline
import sys
from datetime import datetime
from pathlib import Path

import structlog
from claude_agent_sdk import AssistantMessage, ResultMessage, ToolUseBlock
from rich.console import Console
from rich.status import Status

from harness.agent import AgentSession
from harness.cli import (
    SessionTotals,
    display_session_info,
    get_user_input,
    handle_slash_command,
    parse_and_print_message,
    parser,
    print_goodbye_banner,
    print_status_footer,
    print_welcome_banner,
)
from harness.config import (
    RuntimeConfig,
    configure_logging,
    get_config,
    resolve_model_name,
)

logger = structlog.get_logger(__name__)

# Persistent input history. The /memory volume is mounted into the container
# so this survives `make down`/`make up` cycles. Importing `readline` (above)
# is what wires arrow-keys, in-line cursor movement, and Ctrl+A/E/W/U/R into
# the built-in input() that Rich's Prompt.ask() delegates to — without the
# import, input() falls back to dumb-tty editing.
_HISTORY_FILE = Path("/memory/.interactive_history")
_HISTORY_MAX_LINES = 1000


def _setup_input_history() -> None:
    """Load persistent input history and register save-on-exit."""
    readline.set_history_length(_HISTORY_MAX_LINES)
    if _HISTORY_FILE.exists():
        # File unreadable → start fresh, don't fail startup.
        with contextlib.suppress(OSError):
            readline.read_history_file(str(_HISTORY_FILE))
    atexit.register(_save_input_history)


def _save_input_history() -> None:
    """Persist input history to the /memory volume."""
    with contextlib.suppress(OSError):
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        readline.write_history_file(str(_HISTORY_FILE))


async def run_interactive_session() -> None:
    """Run an interactive conversation session with the agent."""
    # Parse CLI arguments
    args = parser.parse_args()
    console = Console()

    # Get configuration (immutable singleton)
    config = get_config()

    # Resolve model override from CLI arg (None if default or unrecognized)
    model_override = None
    if args.model and args.model != "sonnet":
        model_override = resolve_model_name(args.model)
        if model_override is None:
            console.print(
                f"[yellow]Warning: Unknown model '{args.model}'. "
                f"Valid options: sonnet, haiku, opus. Using default (sonnet).[/yellow]\n"
            )

    # --debug is a "show me everything" toggle: bumps log level, forces raw
    # SDK message dumps, and forces the per-turn stats table on. It supersedes
    # --quiet when both are passed.
    if args.debug:
        args.print_raw = "True"
        args.stats = "True"

    # Create immutable RuntimeConfig with CLI overrides applied
    runtime = RuntimeConfig.from_harness_config(
        config,
        mode="interactive",
        model_override=model_override,
        quiet=args.quiet,
        debug=args.debug,
    )

    # Configure logging using centralized function
    configure_logging(runtime)

    # Wire arrow-key/history line editing into Prompt.ask()
    _setup_input_history()

    logger.info("Runtime config created", model=runtime.model, quiet=runtime.quiet)

    # Determine whether to print stats
    print_stats = args.stats.lower() in ("true", "1", "yes")

    # Print welcome banner
    agent_name = "main"
    print_welcome_banner(console, agent_name, runtime.model)

    # Cumulative session metrics for the status footer printed after each turn.
    totals = SessionTotals()
    # Most recent ResultMessage — drives /stats and exit-summary tables.
    last_result: ResultMessage | None = None

    # Create and start agent session with loading spinner
    # Spinner wraps both constructor AND start() since both do I/O
    session_start_time = datetime.now()
    with Status(
        "[cyan]Initializing session...[/cyan]",
        console=console,
        spinner="dots",
    ):
        session = AgentSession(
            agent_name=agent_name,
            config=config,
            runtime_config=runtime,
        )
        await session.start()
        recovered = await session.recover_from_checkpoint()

    try:
        # Show recovery status if applicable
        if recovered and not args.quiet:
            console.print(
                "[green]✓ Recovered from previous checkpoint[/green]\n",
                style="dim",
            )
            # Display session info locally (no API call needed)
            display_session_info(session.get_session_info(), console)

        # Generate dynamic agent introduction for NEW sessions only
        # Recovered sessions already have context - skip intro to save time/tokens
        if not args.quiet and not recovered:
            intro_prompt = (
                "Briefly introduce yourself in 2-3 short paragraphs. Include: "
                "1) Who you are (name, that you're built on Anthropic's Claude Agent SDK), "
                "2) Key capabilities (tools you have access to like file operations, bash, "
                "web browser via Playwright, Docker, library docs, spawning sub-agents), "
                "3) Your working directory setup (/app vs /workspace), "
                "4) Available CLI tools (git, gh, glab with SSH keys configured). "
                "End by asking how you can help. Keep it concise and friendly."
            )
            async for message in session.execute(intro_prompt):
                parse_and_print_message(message, console, config.log_format == "json")

        # Main conversation loop
        while True:
            try:
                # Get user input — prompt_toolkit raises EOFError on Ctrl+D
                # (where Rich's Prompt.ask returned an empty string), so treat
                # EOF as an explicit exit signal.
                try:
                    user_input = await get_user_input(console)
                except EOFError:
                    logger.info("EOF received — exiting")
                    break

                # Check for exit commands
                if user_input.lower() in ("exit", "quit", "q"):
                    logger.info("User requested exit")
                    break

                # Skip empty inputs
                if not user_input.strip():
                    continue

                # Intercept harness-side meta commands (/stats, /help, /clear).
                # Plugin/SDK slash commands always include a colon
                # (e.g. /cgf-agents:cgf) and are forwarded to the agent.
                if user_input.startswith("/") and ":" not in user_input:
                    if not handle_slash_command(
                        user_input, console, totals, last_result, runtime.model
                    ):
                        console.print(
                            f"[yellow]Unknown command: {user_input.strip()}. "
                            f"Type /help for available commands.[/yellow]\n"
                        )
                    continue

                # Record user prompt metric
                session.metrics.record_user_prompt(agent_name)

                # Execute agent task
                logger.debug(
                    "Processing user input",
                    prompt_length=len(user_input),
                )

                async for message in session.execute(user_input):
                    logger.debug(
                        "Message received in interactive loop",
                        message_type=type(message).__name__,
                        message_repr=repr(message)[:200],
                    )

                    # Print raw message if debugging
                    if args.print_raw.lower() in ("true", "1", "yes"):
                        console.print(
                            f"[dim]Raw message: {message}[/dim]\n",
                            style="dim",
                        )

                    # Record metrics based on message type
                    if isinstance(message, AssistantMessage):
                        session.metrics.record_agent_response(agent_name)

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

                    # Cache token metrics (cacheRead / cacheCreation) are now
                    # emitted by the Claude Code CLI as
                    # claude_code_token_usage_tokens_total{type="cacheRead"|"cacheCreation"}.
                    # Cache hit ratio is computed from those on the dashboard.

                    # Parse and display message with Rich formatting
                    parse_and_print_message(
                        message,
                        console,
                        print_stats=print_stats,
                        quiet=args.quiet,
                    )

                    # Status footer after each completed turn (ResultMessage
                    # is the SDK's "turn ended" signal). Always-on, concise —
                    # complementary to the verbose --stats table above.
                    if isinstance(message, ResultMessage):
                        totals.update_from_result(message)
                        last_result = message
                        if not args.quiet:
                            print_status_footer(
                                console, totals, runtime.model, last_result=message
                            )

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                # Flush streams on interrupt
                sys.stdout.flush()
                sys.stderr.flush()
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
                # Provide helpful suggestions based on error type
                error_str = str(e).lower()
                if "api" in error_str or "key" in error_str or "auth" in error_str:
                    console.print(
                        "[dim]Suggestion: Check your ANTHROPIC_API_KEY in .env[/dim]"
                    )
                elif "connection" in error_str or "network" in error_str:
                    console.print(
                        "[dim]Suggestion: Check your network connection and try again[/dim]"
                    )
                elif "timeout" in error_str:
                    console.print(
                        "[dim]Suggestion: Try a simpler prompt or increase timeout[/dim]"
                    )
                elif "rate" in error_str or "limit" in error_str:
                    console.print(
                        "[dim]Suggestion: Wait a moment, then try again (rate limited)[/dim]"
                    )
                elif "memory" in error_str or "oom" in error_str:
                    console.print(
                        "[dim]Suggestion: Increase AGENT_MEMORY_LIMIT in .env[/dim]"
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
        console.print(f"\n[red bold]Fatal Error: {str(e)}[/red bold]")
        console.print(
            "[dim]Run 'make doctor' to diagnose or see docs/TROUBLESHOOTING.md[/dim]\n"
        )
        sys.exit(1)

    finally:
        # Record session duration
        session_duration = (datetime.now() - session_start_time).total_seconds()
        session.metrics.record_interactive_session_duration(agent_name, session_duration)

        # Graceful shutdown
        logger.info(
            "Shutting down interactive session", session_duration_seconds=session_duration
        )

        # Final session recap — the goodbye banner embeds cumulative +
        # last-turn stats tables when not in --quiet mode.
        if not args.quiet:
            print_goodbye_banner(
                console,
                totals=totals,
                last_result=last_result,
                model=runtime.model,
            )
        else:
            print_goodbye_banner(console)

        # Ensure streams are flushed before shutdown
        await asyncio.sleep(0.1)
        sys.stdout.flush()
        sys.stderr.flush()

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

        # Final flush after shutdown complete
        sys.stdout.flush()
        sys.stderr.flush()


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
        print(f"\n\nFatal error: {e}")
        print("Run 'make doctor' to diagnose or see docs/TROUBLESHOOTING.md\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
