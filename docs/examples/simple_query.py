"""
Simple Query Example - Claude Agent SDK

This example demonstrates the two basic ways to query Claude:
1. Using `query()` for one-off questions (stateless, new session each time)
2. Using `ClaudeSDKClient` for continuous conversations (stateful sessions)

Prerequisites:
- ANTHROPIC_API_KEY set in .env file or environment
- Claude Agent SDK installed (should already be in harness dependencies)

Run directly:
    python examples/simple_query.py

Or with a specific model:
    python examples/simple_query.py --model opus
    python examples/simple_query.py --model haiku
"""

import asyncio
import argparse
from claude_agent_sdk import query, ClaudeSDKClient, ClaudeAgentOptions
from rich import print


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Simple Claude Agent SDK query example")
    parser.add_argument(
        "--model",
        "-m",
        default="haiku",
        choices=["haiku", "sonnet", "opus"],
        help="Model to use (default: haiku for cost-effective testing)"
    )
    return parser.parse_args()


async def main():
    """Run simple query examples"""
    args = parse_args()

    # Configure agent options
    # Using haiku by default for cost-effective testing
    options = ClaudeAgentOptions(
        model=args.model,
    )

    print(f"\n[bold cyan]Using model:[/bold cyan] {args.model}\n")

    # ----------------------------
    # 1. Example using `query()`
    # ----------------------------
    # Best for: One-off questions, independent tasks, new sessions

    input_prompt = "Say hello in a friendly way!"
    print(f"[bold yellow]User:[/bold yellow] {input_prompt}")

    print("\n[bold green]Example 1: Using query()[/bold green]")
    print("[dim]This creates a new session for each query[/dim]\n")

    async for message in query(prompt=input_prompt, options=options):
        print(message)

    # ----------------------------
    # 2. Example using `ClaudeSDKClient`
    # ----------------------------
    # Best for: Multi-turn conversations, maintaining context

    print("\n" + "=" * 60)
    print("[bold green]Example 2: Using ClaudeSDKClient[/bold green]")
    print("[dim]This maintains conversation state across multiple queries[/dim]\n")

    # Use context manager for automatic connection/cleanup
    async with ClaudeSDKClient(options=options) as client:

        # Send a query
        await client.query(input_prompt)

        # Receive messages including ResultMessage
        async for message in client.receive_response():
            # See message types at:
            # https://docs.claude.com/en/api/agent-sdk/python#message-types
            print(message)

    print("\n[bold cyan]✓ Examples complete![/bold cyan]")
    print("[dim]Once disconnected, re-running query() starts a new session.[/dim]\n")


if __name__ == "__main__":
    asyncio.run(main())
