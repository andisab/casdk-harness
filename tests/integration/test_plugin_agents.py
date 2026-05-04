"""Integration tests for plugin agent accessibility.

Tests whether plugin agents (defined in plugin agents/ directories)
are accessible via the Task tool.

Expected plugin agents from local plugins:
- context-engineering:context-engineer
- research-team:research-specialist  # in-tree before Step 2a; via marketplace after
- research-team:research-report-writer
- research-team:research-report-writer

Reference: CLAUDE.md states "Plugin agents NOT accessible (SDK issue #213, #11620)"
"""

import tempfile
from pathlib import Path

import pytest
import structlog
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, SystemMessage

logger = structlog.get_logger(__name__)

# Path to our plugins
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests."""
    with tempfile.TemporaryDirectory(prefix="plugin_agent_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def plugin_paths() -> list[dict[str, str]]:
    """Return plugin configurations for SDK."""
    return [
        {"type": "local", "path": str(PLUGIN_BASE / "context-engineering")},
        {"type": "local", "path": str(PLUGIN_BASE / "research-team")},
    ]


class TestPluginAgentDiscovery:
    """Test plugin agent discovery in SystemMessage."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agents_appear_in_system_message(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Verify plugin agents appear in the agents list in SystemMessage.

        Expected agents from plugins (post-Step 2a):
        - context-engineering:context-engineer
        - research-team:research-specialist
        - research-team:research-report-writer
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Task"],
            permission_mode="bypassPermissions",
            max_turns=3,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,
        )

        logger.info("Testing plugin agents in SystemMessage")

        system_agents = None
        async with ClaudeSDKClient(options=options) as client:
            await client.query("List available agents")

            async for msg in client.receive_response():
                if isinstance(msg, SystemMessage):
                    if hasattr(msg, "subtype") and msg.subtype == "init":
                        data = msg.data if hasattr(msg, "data") else {}
                        system_agents = data.get("agents", [])
                        plugins_in_msg = data.get("plugins", [])

                        logger.info(
                            "SystemMessage analysis",
                            agents_count=len(system_agents) if system_agents else 0,
                            plugins_count=len(plugins_in_msg) if plugins_in_msg else 0,
                            sample_agents=system_agents[:10] if system_agents else [],
                        )
                        break

        # Check for expected plugin agents (research-team coordinator is a
        # main-thread skill post-Step 2a, not a Task-dispatchable agent).
        expected_plugin_agents = [
            "context-engineering:context-engineer",
            "research-team:research-specialist",
            "research-team:research-report-writer",
        ]

        if system_agents:
            found_agents = []
            missing_agents = []

            for expected in expected_plugin_agents:
                # Check if agent appears (might be with or without namespace)
                agent_name = expected.split(":")[-1]  # Get just the name part
                found = any(
                    agent_name in str(a) or expected in str(a)
                    for a in system_agents
                )
                if found:
                    found_agents.append(expected)
                else:
                    missing_agents.append(expected)

            logger.info(
                "Plugin agent discovery result",
                found=found_agents,
                missing=missing_agents,
                all_agents=system_agents,
            )

            if missing_agents:
                logger.warning(
                    "Plugin agents NOT found in SystemMessage - this is the known limitation",
                    missing=missing_agents,
                    see_issues=["#213", "#11620"],
                )
        else:
            logger.warning("No agents in SystemMessage")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPluginAgentInvocation:
    """Test invoking plugin agents via Task tool."""

    async def test_invoke_context_engineer_agent(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Attempt to invoke the context-engineering:context-engineer agent.

        This tests if the Task tool can spawn plugin agents.
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Task", "Skill"],
            permission_mode="bypassPermissions",
            max_turns=10,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,
        )

        logger.info("Testing context-engineer agent invocation")

        messages = []
        task_tool_used = False
        error_messages = []

        async with ClaudeSDKClient(options=options) as client:
            # Ask Claude to use the Task tool with the plugin agent
            await client.query(
                "Use the Task tool to spawn a context-engineer agent (from the context-engineering plugin) "
                "to explain what it can do. Use subagent_type='context-engineering:context-engineer'. "
                "If you can't find that agent, tell me what agents ARE available."
            )

            async for msg in client.receive_response():
                messages.append(msg)
                msg_type = type(msg).__name__

                # Check for Task tool usage
                if hasattr(msg, "name") and "Task" in str(getattr(msg, "name", "")):
                    task_tool_used = True
                    logger.info("Task tool invoked", message=str(msg)[:200])

                # Check for errors
                if hasattr(msg, "content"):
                    content = str(msg.content)
                    if "error" in content.lower() or "not found" in content.lower():
                        error_messages.append(content[:200])

        logger.info(
            "Context-engineer invocation result",
            message_count=len(messages),
            task_tool_used=task_tool_used,
            errors=error_messages,
        )

        if error_messages:
            logger.warning(
                "Errors during agent invocation - likely plugin agents not accessible",
                errors=error_messages,
            )

    # The original test_invoke_research_coordinator_agent test was removed in
    # Step 2a: the in-tree lead-research-coordinator agent was deleted in favor
    # of the marketplace research-team:coordinator skill. Skill invocation
    # follows a different pattern (Skill tool, main-thread only) and is not
    # in scope for this integration suite.


@pytest.mark.integration
@pytest.mark.asyncio
class TestAvailableAgents:
    """Test what agents are actually available."""

    async def test_list_all_available_agents(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Get a comprehensive list of all agents available to the SDK.

        This helps identify which agents work (harness agents) vs
        which don't (plugin agents).
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Task"],
            permission_mode="bypassPermissions",
            max_turns=5,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,
        )

        logger.info("Listing all available agents")

        all_agents = []
        async with ClaudeSDKClient(options=options) as client:
            await client.query(
                "List ALL the subagent_type values you can use with the Task tool. "
                "Include both the agent name and a one-line description. "
                "Format as a numbered list."
            )

            async for msg in client.receive_response():
                if isinstance(msg, SystemMessage):
                    if hasattr(msg, "data"):
                        all_agents = msg.data.get("agents", [])

                # Also capture the assistant's response
                if hasattr(msg, "content"):
                    content = str(msg.content)
                    if "agent" in content.lower():
                        logger.info("Agent list response", content=content[:500])

        logger.info(
            "Available agents from SystemMessage",
            count=len(all_agents),
            agents=all_agents[:20] if all_agents else "None found",
        )
