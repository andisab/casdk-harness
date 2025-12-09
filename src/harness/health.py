"""Health check HTTP server for agent liveness and readiness probes.

Provides /health and /ready endpoints for Kubernetes-style health checks.
Used by Docker health checks and orchestration systems to verify agent status.
"""

from typing import TYPE_CHECKING, Any

import structlog
from aiohttp import web

if TYPE_CHECKING:
    from harness.agent import AgentSession

logger = structlog.get_logger(__name__)


class HealthServer:
    """HTTP server for health check endpoints.

    Provides:
    - /health - Liveness probe (is the process running?)
    - /ready - Readiness probe (is the agent ready to accept work?)
    - /status - Detailed status information
    """

    def __init__(
        self,
        session: "AgentSession",
        port: int | None = None,
    ) -> None:
        """
        Initialize health server.

        Args:
            session: AgentSession instance to monitor
            port: HTTP port (defaults to config.health_port)
        """
        self.session = session
        self.port = port or session.config.health_port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._started = False

        logger.debug(
            "Health server initialized",
            port=self.port,
            agent=session.agent_name,
        )

    async def health_handler(self, _request: web.Request) -> web.Response:
        """Handle /health liveness probe.

        Returns 200 if process is running, regardless of readiness.
        """
        return web.json_response(
            {
                "status": "healthy",
                "agent": self.session.agent_name,
            }
        )

    async def ready_handler(self, _request: web.Request) -> web.Response:
        """Handle /ready readiness probe.

        Returns 200 only if agent is fully ready to accept work.
        Returns 503 if not ready (SDK not connected, etc.).
        """
        is_ready = self.session.client is not None

        status_code = 200 if is_ready else 503
        status = "ready" if is_ready else "not_ready"

        return web.json_response(
            {
                "status": status,
                "agent": self.session.agent_name,
                "sdk_connected": self.session.client is not None,
                "redis_available": self.session.redis_available,
            },
            status=status_code,
        )

    async def status_handler(self, _request: web.Request) -> web.Response:
        """Handle /status detailed status endpoint.

        Returns comprehensive status information for debugging.
        """
        # Gather detailed status
        status: dict[str, Any] = {
            "agent": self.session.agent_name,
            "session_id": self.session.session_id,
            "sdk_connected": self.session.client is not None,
            "redis_available": self.session.redis_available,
            "background_tasks": len(self.session._background_tasks),
            "state": {
                "started_at": self.session.state.get("started_at"),
                "current_task": self.session.state.get("current_task"),
                "completed_tasks_count": len(
                    self.session.state.get("completed_tasks", [])
                ),
            },
        }

        # Add Redis circuit breaker state if available
        if self.session.message_broker is not None:
            status["redis_circuit_breaker"] = (
                self.session.message_broker.get_circuit_breaker_state()
            )

        return web.json_response(status)

    async def start(self) -> None:
        """Start the health check HTTP server."""
        if self._started:
            logger.debug("Health server already started")
            return

        try:
            self._app = web.Application()
            self._app.router.add_get("/health", self.health_handler)
            self._app.router.add_get("/ready", self.ready_handler)
            self._app.router.add_get("/status", self.status_handler)

            self._runner = web.AppRunner(self._app)
            await self._runner.setup()

            self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
            await self._site.start()

            self._started = True
            logger.info(
                "Health server started",
                port=self.port,
                endpoints=["/health", "/ready", "/status"],
            )
        except OSError as e:
            if e.errno in (98, 48):  # Address already in use (Linux: 98, macOS: 48)
                logger.warning(
                    "Health server port already in use, skipping",
                    port=self.port,
                    error=str(e),
                )
            else:
                logger.error(
                    "Failed to start health server",
                    port=self.port,
                    error=str(e),
                    exc_info=True,
                )
                raise
        except Exception as e:
            logger.error(
                "Failed to start health server",
                port=self.port,
                error=str(e),
                exc_info=True,
            )
            raise

    async def stop(self) -> None:
        """Stop the health check HTTP server."""
        if not self._started:
            return

        try:
            if self._site:
                await self._site.stop()
            if self._runner:
                await self._runner.cleanup()

            logger.info("Health server stopped", port=self.port)
        except Exception as e:
            logger.warning(
                "Error stopping health server",
                error=str(e),
            )
        finally:
            # Always mark as stopped, even if cleanup fails
            self._started = False

    @property
    def is_running(self) -> bool:
        """Check if health server is running."""
        return self._started
