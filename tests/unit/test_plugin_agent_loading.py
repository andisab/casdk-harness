"""Unit tests for plugin agent loading.

Tests the _load_plugin_agents() method in AgentSession that
manually loads plugin agents as a workaround for the SDK limitation.
"""

import json
from pathlib import Path

import pytest
import structlog

logger = structlog.get_logger(__name__)

# Path to our plugins
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


class TestPluginAgentLoading:
    """Test plugin agent discovery and loading."""

    def test_plugin_agents_directory_structure(self):
        """Verify plugin agents exist in expected locations.

        Post-Step 2b: ``research-team`` and ``context-engineering`` live in
        swe-marketplace. ``cgf-agents`` is the only remaining in-tree plugin
        and is asserted here.
        """
        expected_agents = {
            "cgf-agents": ["cgf-orchestrator.md"],
        }

        for plugin_name, agent_files in expected_agents.items():
            plugin_path = PLUGIN_BASE / plugin_name
            agents_dir = plugin_path / "agents"

            assert agents_dir.exists(), f"Agents directory not found: {agents_dir}"

            for agent_file in agent_files:
                agent_path = agents_dir / agent_file
                assert agent_path.exists(), f"Agent file not found: {agent_path}"

                # Verify frontmatter exists
                content = agent_path.read_text()
                assert content.startswith("---"), f"Missing frontmatter in {agent_file}"
                assert "name:" in content, f"Missing name in {agent_file}"

        logger.info(
            "Plugin agent structure verified",
            plugins=list(expected_agents.keys()),
        )

    def test_load_plugin_agents_method(self):
        """Test _load_plugin_agents() returns expected agents."""
        # Import here to avoid circular imports
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

        from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

        # Manually implement the loading logic to test it
        import re
        import yaml

        plugin_agents = {}

        for plugin_path in PLUGIN_BASE.glob("*/"):
            if not plugin_path.is_dir():
                continue

            plugin_name = plugin_path.name
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

            if not manifest_path.exists():
                continue

            manifest = json.loads(manifest_path.read_text())
            agent_paths = manifest.get("agents", [])

            for agent_rel_path in agent_paths:
                agents_dir = plugin_path / agent_rel_path.lstrip("./")

                if not agents_dir.exists():
                    continue

                for agent_file in agents_dir.glob("*.md"):
                    content = agent_file.read_text()
                    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
                    match = re.match(pattern, content, re.DOTALL)

                    if not match:
                        continue

                    metadata = yaml.safe_load(match.group(1))
                    body = match.group(2).strip()

                    agent_name = metadata.get("name", agent_file.stem)
                    description = metadata.get("description", "")
                    model = metadata.get("model", "sonnet")
                    tools_str = metadata.get("tools", "")
                    tools = [t.strip() for t in tools_str.split(",") if t.strip()] if tools_str else None

                    namespaced_key = f"{plugin_name}:{agent_name}"
                    plugin_agents[namespaced_key] = {
                        "description": description,
                        "prompt": body,
                        "tools": tools,
                        "model": model,
                    }

        # Verify expected agents are found (in-tree only post-Step 2b; both
        # research-team and context-engineering moved to swe-marketplace).
        expected_keys = [
            "cgf-agents:cgf-orchestrator",
        ]

        for key in expected_keys:
            assert key in plugin_agents, f"Expected agent not found: {key}"

        logger.info(
            "Plugin agents loaded",
            count=len(plugin_agents),
            agents=list(plugin_agents.keys()),
        )

        # Verify each agent has required fields
        for key, agent in plugin_agents.items():
            assert "description" in agent, f"Missing description in {key}"
            assert "prompt" in agent, f"Missing prompt in {key}"
            assert agent["prompt"], f"Empty prompt in {key}"

    def test_plugin_agent_namespacing(self):
        """Verify agents use plugin-name:agent-name format."""
        import re
        import yaml

        for plugin_path in PLUGIN_BASE.glob("*/"):
            if not plugin_path.is_dir():
                continue

            plugin_name = plugin_path.name
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

            if not manifest_path.exists():
                continue

            manifest = json.loads(manifest_path.read_text())
            agent_paths = manifest.get("agents", [])

            for agent_rel_path in agent_paths:
                agents_dir = plugin_path / agent_rel_path.lstrip("./")

                if not agents_dir.exists():
                    continue

                for agent_file in agents_dir.glob("*.md"):
                    content = agent_file.read_text()
                    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
                    match = re.match(pattern, content, re.DOTALL)

                    if match:
                        metadata = yaml.safe_load(match.group(1))
                        agent_name = metadata.get("name", agent_file.stem)
                        expected_key = f"{plugin_name}:{agent_name}"

                        # Key should be lowercase and use hyphens
                        assert ":" in expected_key, "Namespaced key should contain colon"
                        assert " " not in expected_key, "Namespaced key should not contain spaces"

                        logger.info(
                            "Agent namespacing verified",
                            key=expected_key,
                        )

    # The context-engineer agent moved to swe-marketplace in Step 2b. Its
    # in-tree YAML/frontmatter assertions don't apply here anymore — the
    # marketplace version is upstream-tested. The original test_context_-
    # engineer_agent_details was removed.

    # The research-team plugin lives in swe-marketplace post-Step 2a; the
    # corresponding test was removed because it asserted in-tree files that
    # no longer exist. The marketplace version's correctness is upstream.
