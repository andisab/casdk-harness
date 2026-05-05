"""Unit tests for PluginManager (slim post-3a API).

Tests plugin discovery, agent namespacing, and skill metadata collection.
Manual command/hook discovery has been dropped (SDK auto-loads them via
``plugins=`` — see REFACTOR.md Part 2 Phase 2). Plugin commands and hooks
are SDK-auto-loaded so no harness-side type or test is needed.
"""

from __future__ import annotations

from pathlib import Path

from harness.plugin_manager import DiscoveredPlugin, PluginManager

PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


class TestDiscovery:
    """Plugin discovery walks plugin_dirs and applies the enabled filter."""

    def test_discover_finds_in_tree_plugins(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        names = manager.get_plugin_names()
        # Post-Step 2b: only cgf-agents stays in-tree.
        assert "cgf-agents" in names

    def test_discover_with_enabled_filter(self):
        manager = PluginManager(
            plugin_dirs=[PLUGIN_BASE],
            enabled_plugins=["cgf-agents"],
        )
        manager.discover()

        assert manager.get_plugin_names() == ["cgf-agents"]

    def test_discover_with_unmatched_filter(self):
        manager = PluginManager(
            plugin_dirs=[PLUGIN_BASE],
            enabled_plugins=["does-not-exist"],
        )
        manager.discover()

        assert manager.get_plugin_names() == []

    def test_discover_nonexistent_directory(self):
        manager = PluginManager(plugin_dirs=[Path("/nonexistent/path")])
        manager.discover()

        assert manager.get_plugin_names() == []

    def test_discover_skips_non_plugin_directories(self, tmp_path):
        # A directory without `.claude-plugin/plugin.json` should be ignored.
        (tmp_path / "not-a-plugin").mkdir()
        manager = PluginManager(plugin_dirs=[tmp_path])
        manager.discover()

        assert manager.get_plugin_names() == []

    def test_discover_first_dir_wins_on_duplicate_name(self, tmp_path):
        # Two plugin dirs both contain a plugin named "alpha"; the first one
        # listed should win (matches in-tree-shadows-marketplace policy).
        a = tmp_path / "first"
        b = tmp_path / "second"
        for root, agent_desc in [(a, "from-first"), (b, "from-second")]:
            plugin = root / "alpha"
            (plugin / ".claude-plugin").mkdir(parents=True)
            (plugin / ".claude-plugin" / "plugin.json").write_text(
                '{"name": "alpha"}'
            )
            agents = plugin / "agents"
            agents.mkdir()
            (agents / "demo.md").write_text(
                f"---\nname: demo\ndescription: {agent_desc}\nmodel: sonnet\n---\nbody"
            )

        manager = PluginManager(plugin_dirs=[a, b])
        manager.discover()

        assert manager.get_plugin_names() == ["alpha"]
        agents = manager.get_all_agents()
        assert agents["alpha:demo"].description == "from-first"


class TestAgentRegistration:
    """Plugin agents are loaded and registered under plugin:agent keys."""

    def test_agents_namespaced_by_plugin(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        agents = manager.get_all_agents()
        assert agents, "expected at least one in-tree plugin agent"

        for key in agents:
            assert ":" in key, f"agent key should be namespaced: {key}"

    def test_known_in_tree_agent_present(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        # cgf-agents ships cgf-orchestrator; sample one as a smoke check.
        assert "cgf-agents:cgf-orchestrator" in manager.get_all_agents()

    def test_invalid_agent_frontmatter_is_skipped(self, tmp_path):
        plugin = tmp_path / "broken"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "broken"}')
        (plugin / "agents").mkdir()
        # Missing leading "---" — parser should skip with a warning, not raise.
        (plugin / "agents" / "bad.md").write_text("no frontmatter here\n")
        # Valid sibling — should still be picked up.
        (plugin / "agents" / "good.md").write_text(
            "---\nname: good\ndescription: ok\nmodel: sonnet\n---\nbody"
        )

        manager = PluginManager(plugin_dirs=[tmp_path])
        manager.discover()

        agents = manager.get_all_agents()
        assert "broken:good" in agents
        assert "broken:bad" not in agents


class TestSkillMetadata:
    """Plugin skills are surfaced as metadata for the CLI banner."""

    def test_skills_namespaced_with_source_metadata(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        for key, info in manager.get_all_skills().items():
            assert ":" in key
            assert info["source"] == "plugin"
            assert "plugin" in info
            assert "path" in info


class TestAccessors:
    """Public accessor methods return defensive copies and stable shapes."""

    def test_get_plugin_paths_format(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        for entry in manager.get_plugin_paths():
            assert entry["type"] == "local"
            assert Path(entry["path"]).exists()

    def test_get_summary_keys(self):
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        summary = manager.get_summary()
        assert set(summary.keys()) == {"plugins", "agents", "skills"}
        for value in summary.values():
            assert isinstance(value, list)

    def test_discovered_plugin_dataclass(self):
        plugin = DiscoveredPlugin(name="x", path=Path("/tmp/x"))
        assert plugin.name == "x"
        assert plugin.path == Path("/tmp/x")
