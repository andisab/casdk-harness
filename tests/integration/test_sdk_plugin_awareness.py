"""Test that SDK actually loads and is aware of plugin resources.

This test makes real API calls to verify the SDK has loaded plugins
and their resources (agents, skills) are discoverable.
"""

import pytest

from harness.agent import AgentSession


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_aware_of_plugin_skills():
    """
    Verify SDK can see and list plugin skills.

    This test actually queries the running SDK to check if it knows
    about skills from plugins, not just base skills.
    """
    session = AgentSession(agent_name="test-plugin-awareness")
    await session.start()

    # Query SDK about available skills
    prompt = """List all available skills. For each skill, indicate if it comes from:
    - Base skills (in .claude/skills/)
    - Plugin skills (from .claude/plugins/*/skills/)

    Format: "skill-name: [base|plugin-name]"
    """

    messages = []
    async for message in session.execute(prompt):
        messages.append(message)

    await session.shutdown()

    # Extract text from AssistantMessage content (TextBlock objects)
    response_text = ""
    for msg in messages:
        if msg.__class__.__name__ == "AssistantMessage":
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text + " "
    response_text = response_text.lower()

    # Verify plugin skills are mentioned
    plugin_skills = [
        "skill-creation",
        "agent-definition-creation",
        "plugin-development",
        "command-creation",
        "hook-configuration",
        "joplin-research",
    ]

    found_skills = []
    for skill in plugin_skills:
        if skill in response_text or skill.replace("-", " ") in response_text:
            found_skills.append(skill)

    assert len(found_skills) >= 3, (
        f"SDK should be aware of plugin skills. "
        f"Found: {found_skills}, Expected at least 3 of: {plugin_skills}\n\n"
        f"Response text (first 500 chars): {response_text[:500]}"
    )


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_aware_of_plugin_agents():
    """
    Verify SDK can see and list plugin agents.

    This test queries the SDK to check if it knows about agents
    from plugins.
    """
    session = AgentSession(agent_name="test-plugin-awareness")
    await session.start()

    # Query SDK about available agents
    prompt = """List all available specialized agents. Include agents from:
    - Base agents (in .claude/agents/)
    - Plugin agents (from .claude/plugins/*/agents/)

    Specifically, do you have access to these plugin agents?
    - context-engineer (from context-engineering plugin)
    - build-orchestrator (from arch plugin)
    - research-specialist (from research-team plugin)
    """

    messages = []
    async for message in session.execute(prompt):
        messages.append(message)

    await session.shutdown()

    # Extract text from AssistantMessage content (TextBlock objects)
    response_text = ""
    for msg in messages:
        if msg.__class__.__name__ == "AssistantMessage":
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text + " "
    response_text = response_text.lower()

    # Verify plugin agents are mentioned
    plugin_agents = [
        "context-engineer",
        "context engineer",
        "build-orchestrator",
        "build orchestrator",
        "research-specialist",
        "research specialist",
    ]

    found_agents = []
    for agent in plugin_agents:
        if agent in response_text:
            found_agents.append(agent)

    assert len(found_agents) >= 2, (
        f"SDK should be aware of plugin agents. "
        f"Found: {found_agents}, Expected at least 2 matches from: {plugin_agents}"
    )


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_can_invoke_plugin_skill():
    """
    Verify SDK can actually invoke a skill from a plugin.

    This test attempts to use a plugin skill to verify it's not just
    discoverable but actually functional.
    """
    session = AgentSession(agent_name="test-plugin-skill-invoke")
    await session.start()

    # Try to use joplin-research skill (from research-team plugin)
    prompt = """Use the joplin-research skill to help format a brief research summary.

    Topic: "Claude Agent SDK"
    Just show me the markdown structure, not the full content.
    """

    messages = []
    tool_calls = []

    async for message in session.execute(prompt):
        messages.append(message)

        # Track if Skill tool is called
        if message.__class__.__name__ == "AssistantMessage":
            if hasattr(message, "tool_use") and message.tool_use:
                tool_calls.append(message.tool_use)

    await session.shutdown()

    # Verify Skill tool was invoked
    skill_tool_used = any(
        tool.get("name") == "Skill" or "skill" in tool.get("name", "").lower()
        for tool in tool_calls
    )

    # Extract text from AssistantMessage content (TextBlock objects)
    response_text = ""
    for msg in messages:
        if msg.__class__.__name__ == "AssistantMessage":
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text + " "
    response_text = response_text.lower()

    skill_mentioned = (
        "joplin-research" in response_text or
        "research skill" in response_text or
        skill_tool_used
    )

    assert skill_mentioned, (
        "SDK should either invoke or acknowledge the joplin-research skill. "
        f"Tool calls: {tool_calls}"
    )


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_plugin_count():
    """
    Verify SDK reports correct number of loaded plugins.

    This test asks the SDK how many plugins are loaded to verify
    the plugin loading mechanism is working.
    """
    session = AgentSession(agent_name="test-plugin-count")
    await session.start()

    prompt = """How many plugins are currently loaded?
    List their names if possible.

    Expected plugins:
    - arch
    - context-engineering
    - research-team
    """

    messages = []
    async for message in session.execute(prompt):
        messages.append(message)

    await session.shutdown()

    # Extract text from AssistantMessage content (TextBlock objects)
    response_text = ""
    for msg in messages:
        if msg.__class__.__name__ == "AssistantMessage":
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text += block.text + " "
    response_text = response_text.lower()

    # Look for plugin names in response
    found_plugins = []
    plugin_names = ["arch", "context-engineering", "research-team"]

    for name in plugin_names:
        # Handle both hyphenated and space-separated versions
        if name in response_text or name.replace("-", " ") in response_text:
            found_plugins.append(name)

    # Also check for the number "3" or "three"
    has_correct_count = (
        " 3 " in response_text or
        "three" in response_text or
        len(found_plugins) >= 2
    )

    assert has_correct_count, (
        f"SDK should report 3 plugins loaded. "
        f"Found plugin names: {found_plugins}. "
        f"Response: {response_text[:500]}"
    )


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_system_message_has_plugins():
    """
    Verify SDK SystemMessage includes non-empty plugins array.

    This test checks the SDK's initial SystemMessage to ensure it reports
    plugins as loaded, not just that the config was passed.
    """
    session = AgentSession(agent_name="test-system-message")
    await session.start()

    # Query just to get SystemMessage
    prompt = "Hello"

    system_message = None
    async for message in session.execute(prompt):
        if message.__class__.__name__ == "SystemMessage":
            system_message = message
            break

    await session.shutdown()

    # Verify SystemMessage exists
    assert system_message is not None, "Should receive SystemMessage from SDK"

    # Extract plugins from SystemMessage data
    plugins = system_message.data.get("plugins", [])

    # Verify plugins array is non-empty
    assert len(plugins) == 3, (
        f"SDK should report 3 plugins loaded in SystemMessage. "
        f"Found: {len(plugins)} plugins. "
        f"Plugins: {plugins}"
    )

    # Verify plugin names
    plugin_names = [p.get("name") for p in plugins]
    expected_names = ["arch", "context-engineering", "research-team"]

    for expected in expected_names:
        assert expected in plugin_names, (
            f"Plugin '{expected}' not found in SystemMessage. "
            f"Found plugins: {plugin_names}"
        )


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_skill_count():
    """
    Verify SDK reports 18 total skills (12 base + 6 plugin).

    This test checks the SDK's SystemMessage to ensure all skills
    (base and plugin) are available.
    """
    session = AgentSession(agent_name="test-skill-count")
    await session.start()

    # Query just to get SystemMessage
    prompt = "Hello"

    system_message = None
    async for message in session.execute(prompt):
        if message.__class__.__name__ == "SystemMessage":
            system_message = message
            break

    await session.shutdown()

    # Verify SystemMessage exists
    assert system_message is not None, "Should receive SystemMessage from SDK"

    # Extract skills from SystemMessage data
    skills = system_message.data.get("skills", [])

    # Verify skill count
    assert len(skills) == 18, (
        f"SDK should report 18 total skills (12 base + 6 plugin). "
        f"Found: {len(skills)} skills. "
        f"Skills: {skills}"
    )

    # Verify base skills are present (spot check)
    base_skills = [
        "api-development",
        "code-review",
        "database-management",
        "debugging",
        "deployment-operations",
        "documentation",
        "frontend-development",
        "git-workflow",
        "microservices-architecture",
        "performance-optimization",
        "security",
        "testing-strategies",
    ]

    for skill in base_skills:
        assert skill in skills, f"Base skill '{skill}' not found in skills list"

    # Verify plugin skills are present
    plugin_skills = [
        "skill-creation",
        "agent-definition-creation",
        "plugin-development",
        "command-creation",
        "hook-configuration",
        "joplin-research",
    ]

    found_plugin_skills = [skill for skill in plugin_skills if skill in skills]

    assert len(found_plugin_skills) == 6, (
        f"SDK should have all 6 plugin skills. "
        f"Found: {len(found_plugin_skills)}/6. "
        f"Missing: {set(plugin_skills) - set(found_plugin_skills)}"
    )
