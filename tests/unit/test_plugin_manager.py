"""Unit tests for PluginManager.

Tests plugin discovery, loading, and resource access for all 5 resource types.
"""

import json
from pathlib import Path

import pytest
import structlog

from harness.plugin_manager import (
    HookEvent,
    Plugin,
    PluginCommand,
    PluginHook,
    PluginManager,
    PluginManifest,
)

logger = structlog.get_logger(__name__)

# Path to our plugins
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


class TestPluginManifest:
    """Test PluginManifest dataclass."""

    def test_from_dict_minimal(self):
        """Test creating manifest from minimal dict."""
        data = {"name": "test-plugin"}
        manifest = PluginManifest.from_dict(data, "fallback-name")

        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.description == ""
        assert manifest.agents == []
        assert manifest.skills == []
        assert manifest.commands == []
        assert manifest.hooks == []
        assert manifest.mcp is None

    def test_from_dict_full(self):
        """Test creating manifest from full dict."""
        data = {
            "name": "full-plugin",
            "version": "2.0.0",
            "description": "A test plugin",
            "agents": ["./agents"],
            "skills": ["./skills"],
            "commands": ["./commands"],
            "hooks": ["./hooks"],
            "mcp": "./.mcp.json",
        }
        manifest = PluginManifest.from_dict(data, "fallback")

        assert manifest.name == "full-plugin"
        assert manifest.version == "2.0.0"
        assert manifest.description == "A test plugin"
        assert manifest.agents == ["./agents"]
        assert manifest.skills == ["./skills"]
        assert manifest.commands == ["./commands"]
        assert manifest.hooks == ["./hooks"]
        assert manifest.mcp == "./.mcp.json"

    def test_from_dict_fallback_name(self):
        """Test that fallback name is used when name not in dict."""
        data = {"version": "1.0.0"}
        manifest = PluginManifest.from_dict(data, "fallback-name")

        assert manifest.name == "fallback-name"


class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    def test_discover_existing_plugins(self):
        """Test discovering plugins in the plugins directory."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        plugins = manager.discover_plugins()

        # Should find at least the two existing plugins
        assert len(plugins) >= 2

        plugin_names = [p.name for p in plugins]
        assert "context-engineering" in plugin_names
        # research-team moved to swe-marketplace in Step 2a; cgf-agents stays in-tree.
        assert "cgf-agents" in plugin_names

    def test_discover_with_enabled_filter(self):
        """Test filtering plugins by enabled list."""
        manager = PluginManager(
            plugin_dirs=[PLUGIN_BASE],
            enabled_plugins=["context-engineering"],
        )
        plugins = manager.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].name == "context-engineering"

    def test_discover_nonexistent_directory(self):
        """Test handling of nonexistent plugin directory."""
        manager = PluginManager(plugin_dirs=[Path("/nonexistent/path")])
        plugins = manager.discover_plugins()

        assert len(plugins) == 0


class TestPluginLoading:
    """Test plugin loading functionality."""

    def test_load_plugin_agents(self):
        """Test loading plugin agents."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover_plugins()
        manager.load_all_plugins()

        agents = manager.get_all_agents()

        # Should have loaded at least the in-tree plugin agents
        assert len(agents) >= 1  # context-engineer (research-team moved to marketplace in Step 2a)

        # Verify namespacing
        for key in agents:
            assert ":" in key, f"Agent key should be namespaced: {key}"

        # Verify expected in-tree agents exist
        expected = [
            "context-engineering:context-engineer",
        ]
        for exp in expected:
            assert exp in agents, f"Missing expected agent: {exp}"

    def test_load_plugin_skills(self):
        """Test loading plugin skills."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover_plugins()
        manager.load_all_plugins()

        skills = manager.get_all_skills()

        # Should have loaded some skills
        assert len(skills) >= 1

        # Verify each skill has required metadata
        for key, skill in skills.items():
            assert ":" in key, f"Skill key should be namespaced: {key}"
            assert "source" in skill
            assert skill["source"] == "plugin"
            assert "plugin" in skill
            assert "path" in skill

    def test_load_plugin_commands(self):
        """Test loading plugin commands."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover_plugins()
        manager.load_all_plugins()

        commands = manager.get_all_commands()

        # Should have loaded the cgf-agents command (research-team's command
        # moved to swe-marketplace in Step 2a).
        assert len(commands) >= 1

        # Verify command structure
        for key, cmd in commands.items():
            assert ":" in key, f"Command key should be namespaced: {key}"
            assert isinstance(cmd, PluginCommand)
            assert cmd.name == key
            assert cmd.plugin_name in key

    def test_load_plugin_hooks(self):
        """Test loading plugin hooks."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover_plugins()
        manager.load_all_plugins()

        hooks = manager.get_all_hooks()

        # Should have loaded the sample hooks we created
        assert len(hooks) >= 2

        # Verify hook structure
        for hook in hooks:
            assert isinstance(hook, PluginHook)
            assert hook.event in HookEvent
            assert hook.command
            assert hook.plugin_name

    def test_use_sdk_only_disables_agent_loading(self):
        """Test that use_sdk_only=True disables agent workaround."""
        manager = PluginManager(
            plugin_dirs=[PLUGIN_BASE],
            use_sdk_only=True,
        )
        manager.discover_plugins()
        manager.load_all_plugins()

        # With SDK-only mode, agents should be empty (SDK handles them)
        agents = manager.get_all_agents()
        assert len(agents) == 0


class TestPluginManagerAccessors:
    """Test PluginManager accessor methods."""

    @pytest.fixture
    def loaded_manager(self):
        """Create a fully loaded plugin manager."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover_plugins()
        manager.load_all_plugins()
        return manager

    def test_get_plugins(self, loaded_manager):
        """Test get_plugins returns discovered plugins."""
        plugins = loaded_manager.get_plugins()

        assert isinstance(plugins, dict)
        assert "context-engineering" in plugins
        assert "cgf-agents" in plugins

    def test_get_plugin_paths(self, loaded_manager):
        """Test get_plugin_paths returns SDK-compatible format."""
        paths = loaded_manager.get_plugin_paths()

        assert isinstance(paths, list)
        assert len(paths) >= 2

        for path in paths:
            assert "type" in path
            assert path["type"] == "local"
            assert "path" in path
            assert Path(path["path"]).exists()

    def test_get_mcp_configs(self, loaded_manager):
        """Test get_mcp_configs returns plugin MCP paths."""
        configs = loaded_manager.get_mcp_configs()

        # May be empty if plugins don't have MCP configs
        assert isinstance(configs, list)

    def test_get_summary(self, loaded_manager):
        """Test get_summary returns complete overview."""
        summary = loaded_manager.get_summary()

        assert "plugins" in summary
        assert "agents" in summary
        assert "skills" in summary
        assert "commands" in summary
        assert "hooks_count" in summary
        assert "mcp_configs_count" in summary
        assert "use_sdk_only" in summary

        assert isinstance(summary["plugins"], list)
        assert isinstance(summary["agents"], list)
        assert isinstance(summary["skills"], list)
        assert isinstance(summary["commands"], list)


class TestPluginIntegration:
    """Test plugin system integration."""

    def test_full_plugin_lifecycle(self):
        """Test complete plugin discovery -> load -> access cycle."""
        # Create manager
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])

        # Discover
        plugins = manager.discover_plugins()
        assert len(plugins) >= 2

        # Load
        manager.load_all_plugins()

        # Access all resource types
        agents = manager.get_all_agents()
        skills = manager.get_all_skills()
        commands = manager.get_all_commands()
        hooks = manager.get_all_hooks()
        mcp_configs = manager.get_mcp_configs()

        # Verify totals
        summary = manager.get_summary()
        assert summary["hooks_count"] == len(hooks)
        assert summary["mcp_configs_count"] == len(mcp_configs)

        logger.info(
            "Plugin lifecycle test complete",
            agents=len(agents),
            skills=len(skills),
            commands=len(commands),
            hooks=len(hooks),
        )

    def test_plugin_error_handling(self):
        """Test that plugin loading handles errors gracefully."""
        # Even with mixed valid/invalid paths, should work
        manager = PluginManager(
            plugin_dirs=[
                Path("/nonexistent"),
                PLUGIN_BASE,
            ]
        )

        plugins = manager.discover_plugins()

        # Should still find valid plugins
        assert len(plugins) >= 2
