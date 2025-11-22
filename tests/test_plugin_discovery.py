"""Test script to verify plugin discovery via setting_sources."""

import asyncio
from pathlib import Path
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient


async def test_plugin_discovery():
    """Test if SDK discovers agents and skills from plugins."""

    print("Testing plugin discovery...\n")

    # Initialize SDK with setting_sources
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Skill"],
        cwd="/app",
        setting_sources=["user", "project"],  # Discovers from .claude/ and plugins
        system_prompt="List all available skills and agents you have access to.",
    )

    client = ClaudeSDKClient(options)
    await client.connect()

    # Query agent about available resources
    prompt = """
    What skills and agents are available to you?
    Please list:
    1. All skills you can access via the Skill tool
    2. All agent definitions you have access to

    Focus on showing if you can see plugins from .claude/plugins/ directory.
    """

    print("Sending query to agent...\n")
    await client.query(prompt)

    async for message in client.receive_response():
        msg_type = message.get("type")

        if msg_type == "text":
            print(f"Agent: {message.get('text', '')}\n")
        elif msg_type == "tool_use":
            tool = message.get("name")
            print(f"Tool used: {tool}")
            if tool == "Skill":
                print(f"  Skill: {message.get('input', {})}")

    await client.close()
    print("\n✓ Test complete")


if __name__ == "__main__":
    asyncio.run(test_plugin_discovery())
