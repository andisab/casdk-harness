"""
Basic Interactive Mode - Claude Agent SDK

This example demonstrates a simple conversation loop with Claude using
the harness's Rich CLI formatting utilities for a polished user experience.

Features:
- Continuous conversation loop
- Rich formatted output with colored panels
- Syntax highlighting for tool results
- Type 'exit' or 'quit' to end the session

Prerequisites:
- ANTHROPIC_API_KEY set in .env file or environment
- Claude Agent SDK installed (should already be in harness dependencies)

Run directly:
    python examples/interactive_basic.py

Or with a specific model:
    python examples/interactive_basic.py --model sonnet
    python examples/interactive_basic.py --model opus
"""

import asyncio
import argparse
from pathlib import Path
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Import CLI utilities from harness
try:
    from harness.cli import parse_and_print_message
except ImportError:
    # Fallback if running outside harness context
    print("Warning: harness.cli not found. Using basic output.")
    def parse_and_print_message(message, console, print_stats=False):
        print(message)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Basic interactive Claude session")
    parser.add_argument(
        "--model",
        "-m",
        default="haiku",
        choices=["haiku", "sonnet", "opus"],
        help="Model to use (default: haiku)"
    )
    parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        help="Print session statistics on exit"
    )
    return parser.parse_args()


async def main():
    """Run interactive conversation loop"""
    console = Console()
    args = parse_args()

    # Configure agent options
    options = ClaudeAgentOptions(
        model=args.model,
        permission_mode="acceptEdits",  # Accept file edits without prompting
        setting_sources=["project"]      # Load project settings from .claude/
    )

    # Display welcome banner
    welcome_text = f"""[bold cyan]Basic Interactive Mode[/bold cyan]

Selected model: [yellow]{args.model}[/yellow]

Type your questions or requests below.
Type [red]'exit'[/red] or [red]'quit'[/red] to end the session.
"""
    console.print(Panel(welcome_text, border_style="cyan", padding=(1, 2)))

    # Start conversation loop
    async with ClaudeSDKClient(options=options) as client:

        while True:
            # Get user input
            user_input = Prompt.ask("\n[bold yellow]You[/bold yellow]")

            # Check for exit command
            if user_input.lower() in ("exit", "quit"):
                console.print("\n[bold cyan]✓ Session ended[/bold cyan]\n")
                break

            # Send query to Claude
            await client.query(user_input)

            # Display responses
            async for message in client.receive_response():
                # Use harness CLI utilities for formatted output
                parse_and_print_message(
                    message=message,
                    console=console,
                    print_stats=args.stats
                )


if __name__ == "__main__":
    asyncio.run(main())
