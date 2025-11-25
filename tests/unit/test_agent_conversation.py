"""Unit tests for agent conversation persistence.

Tests verify that the SDK client is created once and reused across
multiple execute() calls to maintain conversation history.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from harness.agent import AgentSession


class TestAgentConversationPersistence:
    """Test suite for conversation persistence via persistent SDK client."""

    @pytest.mark.asyncio
    async def test_client_created_once(self):
        """Verify client is created once in start() and reused in execute()."""
        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.query = AsyncMock()
            mock_client.disconnect = AsyncMock()

            # Mock receive_response to yield a simple message
            async def mock_receive():
                yield {"type": "text", "content": "Response 1"}

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            # Create session and start
            session = AgentSession(agent_name="test")
            await session.start()

            # Verify client created once
            assert mock_client_class.call_count == 1
            assert mock_client.connect.call_count == 1

            # Store client ID
            client_id = id(session.client)
            assert session.client is not None

            # Execute multiple times
            async for _ in session.execute("Message 1"):
                pass

            async for _ in session.execute("Message 2"):
                pass

            # Verify same client instance used
            assert id(session.client) == client_id
            assert mock_client_class.call_count == 1  # Still only 1 client created
            assert mock_client.query.call_count == 2  # 2 queries sent

            # Cleanup
            await session.shutdown()
            assert mock_client.disconnect.call_count == 1

    @pytest.mark.asyncio
    async def test_start_creates_client(self):
        """Verify start() creates and connects the SDK client."""
        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test")
            assert session.client is None  # Before start

            await session.start()

            assert session.client is not None  # After start
            assert mock_client.connect.called

            await session.shutdown()

    @pytest.mark.asyncio
    async def test_execute_without_start_raises_error(self):
        """Verify execute() raises error if start() not called."""
        session = AgentSession(agent_name="test")

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="SDK client not connected"):
            async for _ in session.execute("Test"):
                pass

    @pytest.mark.asyncio
    async def test_shutdown_clears_client(self):
        """Verify shutdown() disconnects and clears the client."""
        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test")
            await session.start()

            assert session.client is not None
            assert session.session_id is None  # No query yet

            await session.shutdown()

            # Verify cleanup
            assert mock_client.disconnect.called
            assert session.client is None
            assert session.session_id is None

    @pytest.mark.asyncio
    async def test_session_id_captured_from_system_message(self):
        """Verify session_id is captured from SDK SystemMessage."""
        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.query = AsyncMock()
            mock_client.disconnect = AsyncMock()

            # Mock SystemMessage with session_id
            mock_system_message = MagicMock()
            mock_system_message.__class__.__name__ = "SystemMessage"
            mock_system_message.data = {"session_id": "test-session-123"}

            async def mock_receive():
                yield mock_system_message
                yield {"type": "text", "content": "Response"}

            mock_client.receive_response = mock_receive
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test")
            await session.start()

            assert session.session_id is None  # Before first query

            # Execute query
            async for _ in session.execute("Hello"):
                pass

            # Verify session_id captured
            assert session.session_id == "test-session-123"
            assert session.state["session_id"] == "test-session-123"

            await session.shutdown()

    @pytest.mark.asyncio
    async def test_get_state_async_includes_session_id(self):
        """Verify _get_state_async() includes SDK session_id."""
        with patch("harness.agent.ClaudeSDKClient"):
            session = AgentSession(agent_name="test")

            # Set session_id manually
            session.session_id = "test-session-456"

            state = await session._get_state_async()

            assert "sdk_session_id" in state
            assert state["sdk_session_id"] == "test-session-456"
            assert "timestamp" in state

    @pytest.mark.asyncio
    async def test_resume_from_session_id(self):
        """Verify resume_from_session_id() sets session_id."""
        with patch("harness.agent.ClaudeSDKClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client_class.return_value = mock_client

            session = AgentSession(agent_name="test")
            await session.start()

            assert session.session_id is None

            # Resume from session ID
            await session.resume_from_session_id("resume-session-789")

            assert session.session_id == "resume-session-789"
            assert session.state["session_id"] == "resume-session-789"

            await session.shutdown()

    @pytest.mark.asyncio
    async def test_resume_without_start_raises_error(self):
        """Verify resume_from_session_id() raises error if start() not called."""
        session = AgentSession(agent_name="test")

        with pytest.raises(RuntimeError, match="SDK client not connected"):
            await session.resume_from_session_id("test-session")
