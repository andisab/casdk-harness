"""Unit tests for health check HTTP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from harness.health import HealthServer


class TestHealthServer:
    """Tests for HealthServer class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AgentSession."""
        session = MagicMock()
        session.agent_name = "test-agent"
        session.session_id = "session-123"
        session.client = MagicMock()  # SDK connected
        session.redis_available = True
        session._background_tasks = set()
        session.state = {
            "started_at": "2025-01-01T00:00:00+00:00",
            "current_task": "task-001",
            "completed_tasks": ["task-000"],
        }
        session.message_broker = None
        session.config = MagicMock()
        session.config.health_port = 8080
        return session

    def test_server_initialization(self, mock_session) -> None:
        """Test health server initializes correctly."""
        server = HealthServer(mock_session)

        assert server.session == mock_session
        assert server.port == 8080
        assert server._started is False

    def test_server_uses_custom_port(self, mock_session) -> None:
        """Test health server can use custom port."""
        server = HealthServer(mock_session, port=9000)

        assert server.port == 9000

    def test_is_running_property(self, mock_session) -> None:
        """Test is_running property reflects started state."""
        server = HealthServer(mock_session)

        assert server.is_running is False

        server._started = True
        assert server.is_running is True

    @pytest.mark.asyncio
    async def test_health_handler_returns_healthy(self, mock_session) -> None:
        """Test /health endpoint returns healthy status."""
        server = HealthServer(mock_session)
        request = MagicMock()

        response = await server.health_handler(request)

        assert response.status == 200
        # Parse JSON from response
        import json
        body = json.loads(response.text)
        assert body["status"] == "healthy"
        assert body["agent"] == "test-agent"

    @pytest.mark.asyncio
    async def test_ready_handler_returns_ready_when_connected(self, mock_session) -> None:
        """Test /ready endpoint returns ready when SDK connected."""
        server = HealthServer(mock_session)
        request = MagicMock()

        response = await server.ready_handler(request)

        assert response.status == 200
        import json
        body = json.loads(response.text)
        assert body["status"] == "ready"
        assert body["sdk_connected"] is True
        assert body["redis_available"] is True

    @pytest.mark.asyncio
    async def test_ready_handler_returns_not_ready_when_disconnected(self, mock_session) -> None:
        """Test /ready endpoint returns 503 when SDK not connected."""
        mock_session.client = None  # Not connected
        server = HealthServer(mock_session)
        request = MagicMock()

        response = await server.ready_handler(request)

        assert response.status == 503
        import json
        body = json.loads(response.text)
        assert body["status"] == "not_ready"
        assert body["sdk_connected"] is False

    @pytest.mark.asyncio
    async def test_status_handler_returns_detailed_status(self, mock_session) -> None:
        """Test /status endpoint returns comprehensive status info."""
        server = HealthServer(mock_session)
        request = MagicMock()

        response = await server.status_handler(request)

        assert response.status == 200
        import json
        body = json.loads(response.text)

        assert body["agent"] == "test-agent"
        assert body["session_id"] == "session-123"
        assert body["sdk_connected"] is True
        assert body["redis_available"] is True
        assert body["background_tasks"] == 0
        assert "state" in body
        assert body["state"]["current_task"] == "task-001"
        assert body["state"]["completed_tasks_count"] == 1

    @pytest.mark.asyncio
    async def test_status_handler_includes_circuit_breaker(self, mock_session) -> None:
        """Test /status endpoint includes circuit breaker state when available."""
        mock_broker = MagicMock()
        mock_broker.get_circuit_breaker_state.return_value = {
            "name": "redis",
            "state": "closed",
            "failures": 0,
        }
        mock_session.message_broker = mock_broker

        server = HealthServer(mock_session)
        request = MagicMock()

        response = await server.status_handler(request)

        import json
        body = json.loads(response.text)
        assert "redis_circuit_breaker" in body
        assert body["redis_circuit_breaker"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_start_creates_routes(self, mock_session) -> None:
        """Test start() creates expected routes."""
        server = HealthServer(mock_session)

        # Mock the aiohttp setup
        with patch.object(web, "Application") as mock_app_class:
            mock_app = MagicMock()
            mock_router = MagicMock()
            mock_app.router = mock_router
            mock_app_class.return_value = mock_app

            with patch.object(web, "AppRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.setup = AsyncMock()
                mock_runner_class.return_value = mock_runner

                with patch.object(web, "TCPSite") as mock_site_class:
                    mock_site = MagicMock()
                    mock_site.start = AsyncMock()
                    mock_site_class.return_value = mock_site

                    await server.start()

        # Verify routes were added
        assert mock_router.add_get.call_count == 3
        routes_added = [call[0][0] for call in mock_router.add_get.call_args_list]
        assert "/health" in routes_added
        assert "/ready" in routes_added
        assert "/status" in routes_added

        assert server._started is True

    @pytest.mark.asyncio
    async def test_start_handles_port_in_use(self, mock_session) -> None:
        """Test start() handles port already in use gracefully."""
        server = HealthServer(mock_session)

        with patch.object(web, "Application"):
            with patch.object(web, "AppRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.setup = AsyncMock()
                mock_runner_class.return_value = mock_runner

                with patch.object(web, "TCPSite") as mock_site_class:
                    mock_site = MagicMock()
                    # Simulate port already in use (errno 48 on macOS, 98 on Linux)
                    error = OSError()
                    error.errno = 48
                    mock_site.start = AsyncMock(side_effect=error)
                    mock_site_class.return_value = mock_site

                    # Should not raise
                    await server.start()

        # Server should not be marked as started
        assert server._started is False

    @pytest.mark.asyncio
    async def test_start_does_nothing_if_already_started(self, mock_session) -> None:
        """Test start() is idempotent."""
        server = HealthServer(mock_session)
        server._started = True

        # Should return early without doing anything
        await server.start()

        # No app should be created
        assert server._app is None

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self, mock_session) -> None:
        """Test stop() properly cleans up resources."""
        server = HealthServer(mock_session)
        server._started = True

        mock_site = MagicMock()
        mock_site.stop = AsyncMock()
        mock_runner = MagicMock()
        mock_runner.cleanup = AsyncMock()

        server._site = mock_site
        server._runner = mock_runner

        await server.stop()

        mock_site.stop.assert_called_once()
        mock_runner.cleanup.assert_called_once()
        assert server._started is False

    @pytest.mark.asyncio
    async def test_stop_does_nothing_if_not_started(self, mock_session) -> None:
        """Test stop() is safe to call when not started."""
        server = HealthServer(mock_session)

        # Should not raise
        await server.stop()

        assert server._started is False

    @pytest.mark.asyncio
    async def test_stop_handles_cleanup_errors(self, mock_session) -> None:
        """Test stop() handles cleanup errors gracefully."""
        server = HealthServer(mock_session)
        server._started = True

        mock_site = MagicMock()
        mock_site.stop = AsyncMock(side_effect=Exception("Cleanup error"))
        server._site = mock_site
        server._runner = None

        # Should not raise
        await server.stop()

        assert server._started is False
