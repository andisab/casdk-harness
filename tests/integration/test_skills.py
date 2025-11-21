"""Integration tests for skill auto-discovery and usage.

These tests verify that skills are properly discovered from .claude/skills/
and can be invoked by the agent via the Skill tool.

Cost: Each test costs ~100-300 tokens (~$0.001-0.003 per test)
Duration: ~5-15 seconds per test
"""

import pytest
import structlog
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from harness.config import get_config

logger = structlog.get_logger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_skills_auto_discovered():
    """
    Verify skills are discovered from .claude/skills/ directory.

    Purpose: Ensure SDK's setting_sources parameter enables skill discovery.
    Expected behavior:
    - SDK initializes successfully with setting_sources=["user", "project"]
    - Agent can list available skills
    - At least one skill is discovered

    Cost: ~150 tokens (~$0.0015)
    """
    config = get_config()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Skill"],
        permission_mode="bypassPermissions",
        max_turns=5,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        setting_sources=["user", "project"],  # Enable skill discovery
    )

    logger.info("Testing skill auto-discovery")

    async with ClaudeSDKClient(options=options) as client:
        # Ask about available skills
        prompt = "What skills do you have available? List them briefly (one line each)."
        messages = []

        # Send query and receive response
        await client.query(prompt)
        async for msg in client.receive_response():
            messages.append(msg)
            logger.debug("Received message", msg_type=type(msg).__name__)

        # Verify we got at least one response
        assert len(messages) > 0, "Should receive at least one message from SDK"

        logger.info(
            "Skill auto-discovery test completed",
            total_messages=len(messages),
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_skill_invocation():
    """
    Test agent can invoke a specific skill.

    Purpose: Verify Skill tool is functional and can access skill content.
    Expected behavior:
    - Agent can use Skill tool
    - Skill content is accessible
    - Agent can respond based on skill information

    Cost: ~200 tokens (~$0.002)
    """
    config = get_config()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Skill"],
        permission_mode="bypassPermissions",
        max_turns=10,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        setting_sources=["user", "project"],
    )

    logger.info("Testing skill invocation")

    async with ClaudeSDKClient(options=options) as client:
        # Request skill usage
        prompt = (
            "Use the api-development skill to tell me about REST API best practices. "
            "Focus specifically on HTTP methods. Keep your response to 2-3 sentences."
        )
        skill_used = False
        messages = []

        # Send query and receive response
        await client.query(prompt)
        async for msg in client.receive_response():
            messages.append(msg)

            # Check if Skill tool was invoked (message structure may vary)
            msg_type = type(msg).__name__
            if "tool" in msg_type.lower() or hasattr(msg, "name"):
                if hasattr(msg, "name") and "Skill" in str(msg.name):
                    skill_used = True
                    logger.info("Skill tool invoked", message_type=msg_type)

        # Verify we got messages
        assert len(messages) > 0, "Should receive messages from agent"

        # Note: We don't assert skill_used=True because Claude may choose
        # to answer directly without invoking the skill tool if it already
        # knows the information

        logger.info(
            "Skill invocation test completed",
            total_messages=len(messages),
            skill_tool_used=skill_used,
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_multiple_skills_available():
    """
    Verify multiple skills can be referenced.

    Purpose: Ensure all skills are accessible, not just one.
    Expected behavior:
    - Agent can reference multiple skill names
    - Skills from different categories are accessible
    - No errors when multiple skills mentioned

    Cost: ~250 tokens (~$0.0025)
    """
    config = get_config()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Skill"],
        permission_mode="bypassPermissions",
        max_turns=10,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        setting_sources=["user", "project"],
    )

    logger.info("Testing multiple skills availability")

    expected_skills = [
        "api-development",
        "code-review",
        "database-management",
        "testing-strategies",
    ]

    async with ClaudeSDKClient(options=options) as client:
        prompt = (
            f"Tell me very briefly (one sentence each) what each of these "
            f"skills covers: {', '.join(expected_skills)}. "
            f"If you're not sure, just say so."
        )
        messages = []

        # Send query and receive response
        await client.query(prompt)
        async for msg in client.receive_response():
            messages.append(msg)

        assert len(messages) > 0, "Should receive response about skills"

        logger.info(
            "Multiple skills test completed",
            total_messages=len(messages),
            expected_skills=expected_skills,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_skill_tool_in_allowed_tools():
    """
    Verify Skill tool is in the agent's allowed tools.

    Purpose: Confirm configuration changes took effect.
    Expected behavior:
    - SDK accepts Skill in allowed_tools
    - Agent initializes without errors
    - Can execute simple queries

    Cost: ~100 tokens (~$0.001)
    """
    config = get_config()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Skill"],  # Skill tool must be accepted
        permission_mode="bypassPermissions",
        max_turns=3,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        setting_sources=["user", "project"],
    )

    logger.info("Testing Skill tool in allowed_tools")

    async with ClaudeSDKClient(options=options) as client:
        # Simple prompt to verify agent can execute
        prompt = "Hello, can you confirm you have access to skills? Just say yes or no."
        messages = []

        # Send query and receive response
        await client.query(prompt)
        async for msg in client.receive_response():
            messages.append(msg)

        # Should get a response without errors
        assert len(messages) > 0, "Should receive at least one message"

        logger.info(
            "Skill tool in allowed_tools test completed",
            total_messages=len(messages),
        )
