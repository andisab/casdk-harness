"""Unit tests for AgentSession initialization and configuration.

Tests verify proper initialization of:
- MCP server loading (in-process and subprocess)
- Plugin skill discovery
- State initialization
- Configuration handling
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.agent import AgentSession
from harness.config import HarnessConfig


@pytest.fixture
def mock_config(tmp_path: Path) -> HarnessConfig:
    """Create a mock config with temporary directories."""
    return HarnessConfig(
        workspace_dir=tmp_path / "workspace",
        memory_dir=tmp_path / "memory",
        claude_checkpoint_interval=3600,
        claude_model="claude-sonnet-4-5-20250929",
        interactive_permission_mode="acceptEdits",
        claude_max_turns=100,
    )


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for AgentSession."""
    with (
        patch("harness.agent.RedisMessageBroker") as mock_redis,
        patch("harness.agent.docker_server") as mock_docker,
        patch("harness.agent.context7_server") as mock_context7,
        patch("harness.agent.memory_server") as mock_memory,
    ):
        # Make Redis silently fail to connect
        mock_redis_instance = MagicMock()
        mock_redis_instance.connect.side_effect = ConnectionError("Test: Redis not available")
        mock_redis_instance.connected = False
        mock_redis.return_value = mock_redis_instance

        yield {
            "redis": mock_redis,
            "docker": mock_docker,
            "context7": mock_context7,
            "memory": mock_memory,
        }


class TestAgentSessionInit:
    """Tests for AgentSession.__init__() behavior."""

    def test_agent_name_stored(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify agent_name is stored correctly."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test-agent", config=mock_config)
        assert session.agent_name == "test-agent"

    def test_config_stored(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify config is stored correctly."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.config == mock_config

    def test_client_initially_none(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify client is None before start()."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.client is None

    def test_session_id_initially_none(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify session_id is None before first query."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.session_id is None

    def test_state_initialized(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify state dict is initialized with required fields."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        assert "agent_name" in session.state
        assert "session_id" in session.state
        assert "started_at" in session.state
        assert "completed_tasks" in session.state
        assert "current_task" in session.state
        assert session.state["agent_name"] == "test"
        assert session.state["completed_tasks"] == []
        assert session.state["current_task"] is None

    def test_checkpoint_manager_created(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify checkpoint manager is created."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.checkpoint_manager is not None

    def test_metrics_collector_created(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify metrics collector is created."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.metrics is not None

    def test_model_override(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify model can be overridden."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(
            agent_name="test",
            config=mock_config,
            model="claude-opus-4-5-20251101"
        )
        assert session._model_override == "claude-opus-4-5-20251101"

    def test_system_prompt_override(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify system prompt can be overridden."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        custom_prompt = "Custom system prompt for testing"
        session = AgentSession(
            agent_name="test",
            config=mock_config,
            system_prompt=custom_prompt
        )
        assert session._system_prompt_override == custom_prompt


class TestInprocessServerLoading:
    """Tests for _load_inprocess_servers() method."""

    def test_inprocess_servers_loaded(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify in-process servers are loaded."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        assert "docker" in session.inprocess_servers
        assert "context7" in session.inprocess_servers
        assert "memory" in session.inprocess_servers

    def test_inprocess_servers_in_mcp_servers(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify in-process servers are included in mcp_servers."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        # In-process servers should be in the merged mcp_servers dict
        assert "docker" in session.mcp_servers
        assert "context7" in session.mcp_servers
        assert "memory" in session.mcp_servers


class TestSkillDiscovery:
    """Tests for _load_all_skills() method."""

    def test_discovered_skills_dict_created(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify discovered_skills is initialized as a dict."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert isinstance(session.discovered_skills, dict)

    def test_plugin_base_path_set(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify plugin_base path is set."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.plugin_base is not None
        assert isinstance(session.plugin_base, Path)


class TestGetState:
    """Tests for get_state() and _get_state_async() methods."""

    def test_get_state_returns_copy(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify get_state() returns a copy of state."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        state1 = session.get_state()
        state2 = session.get_state()

        # Should be equal but not same object
        assert state1 == state2
        assert state1 is not state2

    def test_get_state_modifications_dont_affect_original(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify modifying returned state doesn't affect session state."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        state = session.get_state()

        original_name = session.state["agent_name"]
        state["agent_name"] = "modified"

        assert session.state["agent_name"] == original_name

    @pytest.mark.asyncio
    async def test_get_state_async_includes_timestamp(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify _get_state_async() includes timestamp."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        state = await session._get_state_async()

        assert "timestamp" in state

    @pytest.mark.asyncio
    async def test_get_state_async_includes_sdk_session_id(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify _get_state_async() includes sdk_session_id."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        session.session_id = "test-sdk-session"

        state = await session._get_state_async()

        assert "sdk_session_id" in state
        assert state["sdk_session_id"] == "test-sdk-session"


class TestRedisMessaging:
    """Tests for Redis message broker integration."""

    def test_redis_connection_failure_logged(self, mock_config: HarnessConfig, tmp_path: Path):
        """Verify Redis connection failure is handled gracefully."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        with (
            patch("harness.agent.RedisMessageBroker") as mock_redis,
            patch("harness.agent.docker_server"),
            patch("harness.agent.context7_server"),
            patch("harness.agent.memory_server"),
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.connect.side_effect = ConnectionError("Redis unavailable")
            mock_redis.return_value = mock_redis_instance

            # Should not raise - Redis failure is expected and handled
            session = AgentSession(agent_name="test", config=mock_config)
            assert session is not None

    def test_publish_task_result_without_redis(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify publish_task_result returns None when Redis not connected."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        # Redis should not be connected (mock raises ConnectionError)
        result = session.publish_task_result("task-123", {"status": "done"})
        assert result is None


class TestContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_aenter_calls_start(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify __aenter__ calls start()."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            from unittest.mock import AsyncMock
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test", config=mock_config)

            async with session:
                assert session.client is not None
                assert mock_client.connect.called

    @pytest.mark.asyncio
    async def test_aexit_calls_shutdown(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify __aexit__ calls shutdown()."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            from unittest.mock import AsyncMock
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client_class.return_value = mock_client

            async with AgentSession(agent_name="test", config=mock_config):
                pass

            # After context exit, shutdown should have been called
            assert mock_client.disconnect.called


class TestContextBudgetTracking:
    """Tests for context budget tracking functionality."""

    def test_token_budget_initialized(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify token_budget is initialized based on model context window."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        # Default model is claude-sonnet-4-5-20250929 with 200K context
        assert session.token_budget == 200_000

    def test_tokens_used_initially_zero(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify tokens_used is initialized to 0."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert session.tokens_used == 0

    def test_triggered_warnings_initially_empty(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify triggered warnings set is empty initially."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert len(session._triggered_warnings) == 0

    def test_budget_thresholds_calculated(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify budget thresholds are calculated from percentages."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        # With 200K budget and default percentages (70%, 75%, 85%)
        expected_warning = int(200_000 * 0.70)   # 140,000
        expected_urgent = int(200_000 * 0.75)    # 150,000
        expected_critical = int(200_000 * 0.85)  # 170,000

        assert expected_warning in session._budget_warning_thresholds
        assert expected_urgent in session._budget_warning_thresholds
        assert expected_critical in session._budget_warning_thresholds

        assert session._budget_warning_thresholds[expected_warning] == "warning"
        assert session._budget_warning_thresholds[expected_urgent] == "urgent"
        assert session._budget_warning_thresholds[expected_critical] == "critical"

    def test_budget_override_used(self, mock_dependencies, tmp_path: Path):
        """Verify context_budget_override is used when set."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        config = HarnessConfig(
            workspace_dir=tmp_path / "workspace",
            memory_dir=tmp_path / "memory",
            claude_model="claude-sonnet-4-5-20250929",
            context_budget_override=100_000,  # Override to 100K
        )

        session = AgentSession(agent_name="test", config=config)

        # Should use override instead of model's context window
        assert session.token_budget == 100_000

    def test_check_budget_threshold_returns_none_below_threshold(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify _check_budget_threshold returns None when below all thresholds."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        session.tokens_used = 50_000  # 25%, below all thresholds

        result = session._check_budget_threshold()
        assert result is None

    def test_check_budget_threshold_returns_warning(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify _check_budget_threshold returns warning dict when threshold crossed."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        session.tokens_used = 145_000  # 72.5%, above warning threshold (70%)

        result = session._check_budget_threshold()

        assert result is not None
        assert result["type"] == "system"
        assert result["subtype"] == "context_budget_warning"
        assert result["level"] == "warning"
        assert result["tokens_used"] == 145_000
        assert "content" in result

    def test_check_budget_threshold_only_triggers_once(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify each threshold only triggers once per session."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        session.tokens_used = 145_000  # Above warning threshold

        # First call should return warning
        result1 = session._check_budget_threshold()
        assert result1 is not None
        assert result1["level"] == "warning"

        # Second call at same level should return None (already triggered)
        result2 = session._check_budget_threshold()
        assert result2 is None

    def test_budget_thresholds_scale_with_model(self, mock_dependencies, tmp_path: Path):
        """Verify thresholds scale correctly for different model context windows."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        # Use extended model with 1M context
        config = HarnessConfig(
            workspace_dir=tmp_path / "workspace",
            memory_dir=tmp_path / "memory",
            claude_model="claude-3-5-sonnet-20241022-extended",
        )

        session = AgentSession(agent_name="test", config=config)

        # With 1M budget, thresholds should be much higher
        assert session.token_budget == 1_000_000
        expected_warning = int(1_000_000 * 0.70)  # 700,000
        assert expected_warning in session._budget_warning_thresholds

    def test_format_budget_warning_messages(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify _format_budget_warning returns appropriate messages."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)

        warning_msg = session._format_budget_warning("warning", 72.5, 55000)
        assert "CONTEXT_BUDGET" in warning_msg
        assert "72%" in warning_msg

        urgent_msg = session._format_budget_warning("urgent", 76.0, 48000)
        assert "Checkpoint saved" in urgent_msg

        critical_msg = session._format_budget_warning("critical", 86.0, 28000)
        assert "Stop new work" in critical_msg

    @pytest.mark.asyncio
    async def test_budget_reset_on_session_start(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify tokens_used and triggered_warnings reset on session start."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            from unittest.mock import AsyncMock
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test", config=mock_config)

            # Simulate some tokens used and warnings triggered
            session.tokens_used = 100_000
            session._triggered_warnings.add(140_000)

            await session.start()

            # Should be reset after start()
            assert session.tokens_used == 0
            assert len(session._triggered_warnings) == 0
