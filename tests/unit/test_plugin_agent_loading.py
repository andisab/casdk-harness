"""Unit tests for plugin agent loading.

Verifies that PluginManager loads in-tree plugin agents and registers them
under the ``plugin:agent`` namespacing convention used by the SDK Task tool.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from harness.plugin_manager import PluginManager

logger = structlog.get_logger(__name__)

PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


class TestPluginAgentLoading:
    """In-tree plugin agents are discovered, parsed, and namespaced correctly."""

    def test_plugin_agents_directory_structure(self):
        """Each in-tree plugin advertised in tests has its agent files on disk."""
        # Post-Step 2b: only cgf-agents stays in-tree.
        # Phase A.2: agents reorganized into design/ and eval/ subdirs.
        expected = {
            "cgf-agents": [
                "design/cgf-orchestrator.md",
                "eval/cgf-eval-architect.md",
            ],
        }

        for plugin_name, agent_files in expected.items():
            agents_dir = PLUGIN_BASE / plugin_name / "agents"
            assert agents_dir.exists(), f"Agents directory not found: {agents_dir}"
            for fname in agent_files:
                agent_path = agents_dir / fname
                assert agent_path.exists(), f"Agent file not found: {agent_path}"
                content = agent_path.read_text()
                assert content.startswith("---"), f"Missing frontmatter in {fname}"
                assert "name:" in content, f"Missing name in {fname}"

    def test_plugin_manager_loads_known_agent(self):
        """PluginManager.discover() registers the cgf-orchestrator agent."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()
        agents = manager.get_all_agents()

        assert "cgf-agents:cgf-orchestrator" in agents, (
            f"Expected agent not found in: {sorted(agents.keys())}"
        )

    def test_plugin_agent_keys_are_namespaced(self):
        """Every loaded agent key follows the plugin:agent format."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        for key in manager.get_all_agents():
            assert ":" in key, f"key should be namespaced: {key}"
            assert " " not in key, f"key should not contain spaces: {key}"

    def test_loaded_agents_have_prompt_and_description(self):
        """Each loaded agent has both a non-empty prompt and a description field."""
        manager = PluginManager(plugin_dirs=[PLUGIN_BASE])
        manager.discover()

        for key, sdk_agent in manager.get_all_agents().items():
            assert sdk_agent.prompt, f"empty prompt for {key}"
            # description may be empty by SDK convention but the attr must exist
            assert hasattr(sdk_agent, "description")
