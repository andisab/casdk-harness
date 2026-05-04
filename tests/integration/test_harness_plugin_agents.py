"""Integration tests for plugin agents via harness AgentSession.

Tests that the harness correctly loads and passes plugin agents
to the SDK via the agents parameter in ClaudeAgentOptions.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import structlog

logger = structlog.get_logger(__name__)


@pytest.fixture
def temp_dirs():
    """Create temporary directories that mimic container environment."""
    with tempfile.TemporaryDirectory(prefix="harness_test_") as base:
        base_path = Path(base)
        workspace = base_path / "workspace"
        memory = base_path / "memory"
        logs = base_path / "logs"

        workspace.mkdir()
        memory.mkdir()
        logs.mkdir()
        (memory / "checkpoints").mkdir()

        yield {
            "workspace": workspace,
            "memory": memory,
            "logs": logs,
            "checkpoint_dir": memory / "checkpoints",
        }


class TestHarnessPluginAgentLoading:
    """Test plugin agents are loaded via harness AgentSession."""

    def test_plugin_agents_in_sdk_options(self, temp_dirs):
        """Verify plugin agents are included in SDK options."""
        # Mock the config to use temp directories
        with patch("harness.agent.get_config") as mock_config:
            config = MagicMock()
            config.workspace_dir = temp_dirs["workspace"]
            config.checkpoint_dir = temp_dirs["checkpoint_dir"]
            config.claude_model = "claude-sonnet-4-20250514"
            config.claude_max_turns = 100
            config.claude_checkpoint_interval = 3600
            config.checkpoint_keep_count = 5
            config.interactive_permission_mode = "acceptEdits"
            config.claude_api_timeout = 300
            config.claude_session_timeout = 14400
            config.context_budget_override = None
            config.context_budget_warning_pct = 0.7
            config.context_budget_urgent_pct = 0.85
            config.context_budget_critical_pct = 0.95
            config.shutdown_timeout = 10
            config.redis_url = "redis://localhost:6379"
            config.enabled_plugins_list = None  # All plugins enabled
            config.plugin_use_sdk_only = False  # Use workarounds
            mock_config.return_value = config

            # Create runtime config mock
            with patch("harness.agent.RuntimeConfig") as mock_runtime:
                runtime = MagicMock()
                runtime.model = "claude-sonnet-4-20250514"
                runtime.permission_mode = "acceptEdits"
                mock_runtime.from_harness_config.return_value = runtime

                # Mock MCP loader to avoid file dependencies
                with patch("harness.agent.MCPConfigLoader") as mock_loader:
                    mock_loader.return_value.load_tier.return_value = {"mcpServers": {}}

                    # Mock messaging broker
                    with patch("harness.agent.RedisMessageBroker"):
                        # Import after patches are in place
                        from harness.agent import AgentSession

                        session = AgentSession(agent_name="test", config=config)

                        # Get SDK options
                        options = session._build_sdk_options()

                        # Check agents are included
                        assert hasattr(options, "agents"), "Options should have agents"
                        assert options.agents is not None, "Agents should not be None"

                        agent_names = list(options.agents.keys())
                        logger.info(
                            "SDK options agents",
                            count=len(agent_names),
                            agents=agent_names,
                        )

                        # Check for plugin agents (namespaced)
                        plugin_agent_keys = [
                            k for k in agent_names
                            if ":" in k
                        ]

                        assert len(plugin_agent_keys) > 0, \
                            f"Should have plugin agents (namespaced). Found: {agent_names}"

                        # Verify expected plugin agents (post-Step 2a; the
                        # research-team coordinator is a skill, not an agent)
                        expected = [
                            "context-engineering:context-engineer",
                            "research-team:research-specialist",
                            "research-team:research-report-writer",
                        ]

                        for exp in expected:
                            assert exp in agent_names, f"Missing expected agent: {exp}"

                        logger.info(
                            "Plugin agents verified in SDK options",
                            plugin_agents=plugin_agent_keys,
                        )

    def test_load_plugin_agents_method(self):
        """Test _load_plugin_agents() directly."""
        from pathlib import Path
        from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

        # Get plugin base path
        plugin_base = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"

        # Create a minimal mock that has plugin_base
        class MockSession:
            def __init__(self):
                self.plugin_base = plugin_base

        # Import and call the method
        import json
        import re
        import yaml

        mock_session = MockSession()
        plugin_agents = {}

        for plugin_path in mock_session.plugin_base.glob("*/"):
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

                    model_map = {
                        "opus 4.1": "opus", "opus 4.5": "opus", "opus": "opus",
                        "sonnet 4.5": "sonnet", "sonnet 4.0": "sonnet", "sonnet": "sonnet",
                        "haiku 3.5": "haiku", "haiku": "haiku",
                    }
                    normalized_model = model_map.get(model.lower(), "sonnet")

                    namespaced_key = f"{plugin_name}:{agent_name}"

                    plugin_agents[namespaced_key] = SDKAgentDefinition(
                        description=str(description) if description else "",
                        prompt=body,
                        tools=tools,
                        model=normalized_model if normalized_model in ("sonnet", "opus", "haiku") else None,
                    )

        # Verify results (post-Step 2a: research-team coordinator is a skill,
        # so 3 plugin agents instead of 4)
        assert len(plugin_agents) == 3, f"Expected 3 plugin agents, got {len(plugin_agents)}"

        expected = [
            "context-engineering:context-engineer",
            "research-team:research-specialist",
            "research-team:research-report-writer",
        ]

        for exp in expected:
            assert exp in plugin_agents, f"Missing: {exp}"
            agent = plugin_agents[exp]
            assert agent.prompt, f"Empty prompt for {exp}"
            assert agent.description is not None, f"Missing description for {exp}"

        logger.info(
            "Plugin agents loaded successfully",
            count=len(plugin_agents),
            agents=list(plugin_agents.keys()),
        )

    def test_harness_agents_count(self, temp_dirs):
        """Verify total agent count includes both harness and plugin agents."""
        with patch("harness.agent.get_config") as mock_config:
            config = MagicMock()
            config.workspace_dir = temp_dirs["workspace"]
            config.checkpoint_dir = temp_dirs["checkpoint_dir"]
            config.claude_model = "claude-sonnet-4-20250514"
            config.claude_max_turns = 100
            config.claude_checkpoint_interval = 3600
            config.checkpoint_keep_count = 5
            config.interactive_permission_mode = "acceptEdits"
            config.claude_api_timeout = 300
            config.claude_session_timeout = 14400
            config.context_budget_override = None
            config.context_budget_warning_pct = 0.7
            config.context_budget_urgent_pct = 0.85
            config.context_budget_critical_pct = 0.95
            config.shutdown_timeout = 10
            config.redis_url = "redis://localhost:6379"
            config.enabled_plugins_list = None  # All plugins enabled
            config.plugin_use_sdk_only = False  # Use workarounds
            mock_config.return_value = config

            with patch("harness.agent.RuntimeConfig") as mock_runtime:
                runtime = MagicMock()
                runtime.model = "claude-sonnet-4-20250514"
                runtime.permission_mode = "acceptEdits"
                mock_runtime.from_harness_config.return_value = runtime

                with patch("harness.agent.MCPConfigLoader") as mock_loader:
                    mock_loader.return_value.load_tier.return_value = {"mcpServers": {}}

                    with patch("harness.agent.RedisMessageBroker"):
                        from harness.agent import AgentSession
                        from harness.agents.definitions import AGENT_DEFINITIONS

                        session = AgentSession(agent_name="test", config=config)
                        options = session._build_sdk_options()

                        harness_agent_count = len(AGENT_DEFINITIONS)
                        plugin_agent_count = 4  # Expected: 4 from plugins
                        total_expected = harness_agent_count + plugin_agent_count

                        actual_count = len(options.agents)

                        logger.info(
                            "Agent count verification",
                            harness_agents=harness_agent_count,
                            plugin_agents=plugin_agent_count,
                            expected_total=total_expected,
                            actual_total=actual_count,
                        )

                        assert actual_count >= total_expected, \
                            f"Expected at least {total_expected} agents, got {actual_count}"
