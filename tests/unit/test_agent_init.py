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
        claude_permission_mode="acceptEdits",
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


class TestPluginSkillDiscovery:
    """Tests for _load_plugin_skills_manually() method."""

    def test_plugin_skills_dict_created(self, mock_config: HarnessConfig, mock_dependencies, tmp_path: Path):
        """Verify plugin_skills is initialized as a dict."""
        (tmp_path / "workspace").mkdir(exist_ok=True)
        (tmp_path / "memory").mkdir(exist_ok=True)

        session = AgentSession(agent_name="test", config=mock_config)
        assert isinstance(session.plugin_skills, dict)

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

            async with AgentSession(agent_name="test", config=mock_config) as session:
                pass

            # After context exit, shutdown should have been called
            assert mock_client.disconnect.called
