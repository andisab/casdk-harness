"""Test plugin auto-discovery by SDK.

These tests verify that the Claude Agent SDK properly loads and discovers
resources from plugins when configured via the plugins parameter.
"""

import pytest

from harness.agent import AgentSession


@pytest.mark.integration
async def test_plugin_configuration_loaded():
    """Verify SDK session includes plugin configuration."""
    session = AgentSession(agent_name="test-plugins")

    # Verify plugins are configured
    assert hasattr(session, "plugins"), "AgentSession missing plugins attribute"
    assert len(session.plugins) == 3, f"Expected 3 plugins, got {len(session.plugins)}"

    # Verify plugin types
    for plugin in session.plugins:
        assert plugin["type"] == "local", f"Invalid plugin type: {plugin['type']}"
        assert "path" in plugin, "Plugin missing path"


@pytest.mark.integration
async def test_sdk_options_include_plugins():
    """Verify SDK options include plugins parameter."""
    session = AgentSession(agent_name="test-plugins")

    # Build SDK options (doesn't require API call)
    options = session._build_sdk_options()

    # Verify plugins are in options
    assert hasattr(options, "plugins"), "ClaudeAgentOptions missing plugins"
    assert options.plugins is not None, "Plugins should not be None"
    assert len(options.plugins) == 3, f"Expected 3 plugins in options, got {len(options.plugins)}"


@pytest.mark.integration
async def test_plugin_paths_are_absolute():
    """Verify all plugin paths are absolute and valid."""
    from pathlib import Path

    session = AgentSession(agent_name="test-plugins")

    for plugin_config in session.plugins:
        path = Path(plugin_config["path"])
        assert path.is_absolute(), f"Plugin path not absolute: {path}"
        assert path.exists(), f"Plugin path does not exist: {path}"

        # Verify .claude-plugin/plugin.json exists
        manifest_path = path / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), f"Plugin manifest not found: {manifest_path}"


@pytest.mark.integration
@pytest.mark.slow
async def test_sdk_loads_plugins_without_error():
    """
    Verify SDK can be initialized with plugin configuration.

    This test actually initializes the SDK client to ensure no errors occur
    during plugin loading. Requires ANTHROPIC_API_KEY.
    """
    session = AgentSession(agent_name="test-plugins")
    options = session._build_sdk_options()

    # This will initialize the SDK with plugins
    # If plugin loading fails, this will raise an exception
    from claude_agent_sdk import ClaudeSDKClient

    try:
        # Initialize client (this is where SDK loads plugins)
        client = ClaudeSDKClient(options)

        # If we get here, plugins loaded successfully
        assert True

    except Exception as e:
        pytest.fail(f"SDK failed to load plugins: {str(e)}")


@pytest.mark.integration
def test_plugin_resources_exist():
    """Verify plugin resources (agents, skills) exist in filesystem."""
    from pathlib import Path

    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    # arch plugin
    arch_path = base_path / "arch"
    assert (arch_path / "agents").exists(), "arch plugin missing agents/"
    assert (
        arch_path / "agents" / "build-orchestrator.md"
    ).exists(), "arch plugin missing build-orchestrator agent"

    # context-engineering plugin
    ce_path = base_path / "context-engineering"
    assert (ce_path / "agents").exists(), "context-engineering plugin missing agents/"
    assert (ce_path / "skills").exists(), "context-engineering plugin missing skills/"
    assert (
        ce_path / "skills" / "skill-creation" / "SKILL.md"
    ).exists(), "context-engineering plugin missing skill-creation skill"

    # research-team plugin
    rt_path = base_path / "research-team"
    assert (rt_path / "agents").exists(), "research-team plugin missing agents/"
    assert (rt_path / "skills").exists(), "research-team plugin missing skills/"
    assert (
        rt_path / "skills" / "joplin-research" / "SKILL.md"
    ).exists(), "research-team plugin missing joplin-research skill"
