"""Simple test to verify plugin discovery via setting_sources."""

import asyncio
from harness.agent import AgentSession


async def test_plugin_discovery():
    """Test if SDK discovers agents and skills from plugins."""

    print("Testing plugin discovery...\n")

    # Use existing harness agent session
    session = AgentSession(agent_name="main")
    await session.start()

    # Query agent about available resources
    prompt = """
    Please list all the skills available to you via the Skill tool.
    Include skills from both:
    1. Base .claude/skills/ directory
    2. Plugin directories in .claude/plugins/

    Just list the skill names.
    """

    print("Sending query to agent...\n")

    async for message in session.execute(prompt):
        # Messages are already handled by AgentSession
        print(f"Message: {message}")

    await session.shutdown()
    print("\n✓ Test complete")


if __name__ == "__main__":
    asyncio.run(test_plugin_discovery())
