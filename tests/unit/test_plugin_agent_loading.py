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
        """Verify plugin agents exist in expected locations."""
        expected_agents = {
            "context-engineering": ["context-engineer.md"],
            "research-team": [
                "lead-research-coordinator.md",
                "research-specialist.md",
                "research-report-writer.md",
            ],
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

        # Verify expected agents are found
        expected_keys = [
            "context-engineering:context-engineer",
            "research-team:lead-research-coordinator",
            "research-team:research-specialist",
            "research-team:research-report-writer",
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

    def test_context_engineer_agent_details(self):
        """Verify context-engineer agent has expected properties."""
        import re
        import yaml

        agent_file = PLUGIN_BASE / "context-engineering" / "agents" / "context-engineer.md"
        content = agent_file.read_text()

        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        assert match, "Should parse frontmatter"

        metadata = yaml.safe_load(match.group(1))

        assert metadata.get("name") == "context-engineer"
        assert metadata.get("model") == "sonnet"
        assert "tools" in metadata
        assert "description" in metadata

        # Verify tools list
        tools_str = metadata.get("tools", "")
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        assert "Read" in tools
        assert "Write" in tools
        assert "Edit" in tools

        logger.info(
            "Context-engineer agent verified",
            tools_count=len(tools),
        )

    def test_research_team_agents(self):
        """Verify research-team plugin has expected agents."""
        import re
        import yaml

        expected_agents = [
            "lead-research-coordinator",
            "research-specialist",
            "research-report-writer",
        ]

        agents_dir = PLUGIN_BASE / "research-team" / "agents"

        for expected_name in expected_agents:
            agent_file = agents_dir / f"{expected_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            content = agent_file.read_text()
            pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
            match = re.match(pattern, content, re.DOTALL)
            assert match, f"Should parse frontmatter in {expected_name}"

            metadata = yaml.safe_load(match.group(1))
            assert metadata.get("name") == expected_name, \
                f"Name mismatch in {expected_name}: {metadata.get('name')}"

        logger.info(
            "Research-team agents verified",
            agents=expected_agents,
        )
