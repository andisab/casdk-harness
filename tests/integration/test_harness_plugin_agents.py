"""Integration tests for plugin agents via harness AgentSession.

Verifies the post-5a contract:

- ``ClaudeAgentOptions.agents`` is no longer populated by the harness
  for plugin agents. The SDK exposes them to the Task tool directly via
  ``plugins=`` (verified 2026-05-05; see docs/REFACTOR.md "SDK upstream investigation").
- ``ClaudeAgentOptions.plugins`` contains paths for all enabled plugins.
- ``PluginManager.get_all_agents()`` still parses plugin agents for the
  consumers that aren't the SDK Task tool — namely
  ``harness.subagent`` (which dispatches via ``query()`` with the
  agent's prompt as ``system_prompt``) and the CLI banner display.
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


def _build_session(temp_dirs):
    """Construct an AgentSession with all external dependencies mocked."""
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

                    return AgentSession(agent_name="test", config=config)


class TestSDKOptionsContract:
    """Post-5a: SDK options expose plugins via plugins=, not agents=."""

    def test_options_agents_is_none(self, temp_dirs):
        """Plugin agents are no longer programmatically registered via agents=.

        The SDK loads them from each plugin path passed in ``plugins=`` and
        exposes them to the Task tool natively. The harness's old
        ``agents=sdk_agents`` workaround was removed in the 5a follow-up
        (2026-05-05); ``options.agents`` is now ``None``.
        """
        session = _build_session(temp_dirs)
        options = session._build_sdk_options()

        assert options.agents is None or options.agents == {}, (
            f"Expected options.agents to be empty/None post-5a; got "
            f"{type(options.agents).__name__} with "
            f"{len(options.agents) if options.agents else 0} entries"
        )

    def test_options_plugins_present(self, temp_dirs):
        """plugins= contains paths for all enabled plugins."""
        session = _build_session(temp_dirs)
        options = session._build_sdk_options()

        assert options.plugins, "options.plugins should not be empty"
        for entry in options.plugins:
            assert entry["type"] == "local"
            assert Path(entry["path"]).exists()


class TestPluginAgentParsing:
    """PluginManager still parses plugin agents for subagent.py + CLI display."""

    def test_plugin_manager_loads_namespaced_agents(self, temp_dirs):
        """Plugin agents are loaded under plugin:agent keys.

        Consumed by ``harness.subagent`` (for direct invocation via
        ``query()``) and ``agent.py``'s SystemMessage banner. Not
        consumed by the SDK Task tool — that path goes through
        ``plugins=`` directly.
        """
        session = _build_session(temp_dirs)
        plugin_agents = session.plugin_manager.get_all_agents()

        assert plugin_agents, "PluginManager should still expose parsed plugin agents"

        for key in plugin_agents:
            assert ":" in key, f"plugin agent key should be namespaced: {key}"

    def test_known_in_tree_agent_present(self, temp_dirs):
        """cgf-agents is the only in-tree plugin post-Step 2b."""
        session = _build_session(temp_dirs)
        plugin_agents = session.plugin_manager.get_all_agents()

        assert "cgf-agents:cgf-orchestrator" in plugin_agents, (
            f"Expected cgf-agents:cgf-orchestrator; got {sorted(plugin_agents.keys())}"
        )

    def test_loaded_agents_have_prompt_and_description(self, temp_dirs):
        """Each parsed plugin agent has the metadata subagent.py needs."""
        session = _build_session(temp_dirs)
        plugin_agents = session.plugin_manager.get_all_agents()

        for key, sdk_agent in plugin_agents.items():
            assert sdk_agent.prompt, f"empty prompt for {key}"
            assert hasattr(sdk_agent, "description")
