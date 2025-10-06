"""Monitoring and metrics collection for agent sessions."""

import asyncio
from pathlib import Path
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = structlog.get_logger(__name__)

# Prometheus Metrics
agent_requests_total = Counter(
    "agent_requests_total",
    "Total agent requests",
    ["agent", "status"],
)

agent_duration_seconds = Histogram(
    "agent_duration_seconds",
    "Agent execution time in seconds",
    ["agent"],
)

agent_active_sessions = Gauge(
    "agent_active_sessions",
    "Number of active agent sessions",
    ["agent"],
)

checkpoint_size_bytes = Gauge(
    "checkpoint_size_bytes",
    "Size of checkpoint files in bytes",
)

workspace_files_total = Gauge(
    "workspace_files_total",
    "Total number of files in workspace",
)

memory_usage_bytes = Gauge(
    "memory_usage_bytes",
    "Memory usage in bytes",
    ["component"],
)

api_tokens_used = Counter(
    "api_tokens_used_total",
    "Total API tokens used",
    ["model", "type"],
)

api_cost_dollars = Counter(
    "api_cost_dollars_total",
    "Total API cost in dollars",
    ["model"],
)


class MetricsCollector:
    """Collects and exports metrics for monitoring."""

    def __init__(
        self,
        port: int = 9090,
        workspace_dir: Path | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """
        Initialize metrics collector.

        Args:
            port: Port for Prometheus metrics endpoint
            workspace_dir: Path to workspace directory
            checkpoint_dir: Path to checkpoint directory
        """
        self.port = port
        self.workspace_dir = workspace_dir or Path("/workspace")
        self.checkpoint_dir = checkpoint_dir or Path("/memory/checkpoints")
        self.running = False

    def start(self) -> None:
        """Start metrics HTTP server."""
        try:
            start_http_server(self.port)
            logger.info("Metrics server started", port=self.port)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e), exc_info=True)

    async def collect_system_metrics(self) -> None:
        """Continuously collect system-level metrics."""
        self.running = True
        logger.info("Starting system metrics collection")

        while self.running:
            try:
                # Workspace statistics
                if self.workspace_dir.exists():
                    file_count = len(list(self.workspace_dir.rglob("*.py")))
                    workspace_files_total.set(file_count)

                # Checkpoint statistics
                if self.checkpoint_dir.exists():
                    total_size = sum(
                        f.stat().st_size for f in self.checkpoint_dir.iterdir()
                        if f.is_file()
                    )
                    checkpoint_size_bytes.set(total_size)

                await asyncio.sleep(60)  # Collect every minute

            except Exception as e:
                logger.error("Error collecting metrics", error=str(e), exc_info=True)
                await asyncio.sleep(60)

    def stop(self) -> None:
        """Stop metrics collection."""
        self.running = False
        logger.info("Metrics collection stopped")

    @staticmethod
    def record_request(agent: str, status: str) -> None:
        """
        Record an agent request.

        Args:
            agent: Agent name
            status: Request status (success, error, timeout)
        """
        agent_requests_total.labels(agent=agent, status=status).inc()

    @staticmethod
    def record_duration(agent: str, duration: float) -> None:
        """
        Record agent execution duration.

        Args:
            agent: Agent name
            duration: Duration in seconds
        """
        agent_duration_seconds.labels(agent=agent).observe(duration)

    @staticmethod
    def set_active_sessions(agent: str, count: int) -> None:
        """
        Set number of active sessions.

        Args:
            agent: Agent name
            count: Number of active sessions
        """
        agent_active_sessions.labels(agent=agent).set(count)

    @staticmethod
    def record_token_usage(model: str, token_type: str, count: int) -> None:
        """
        Record API token usage.

        Args:
            model: Model name
            token_type: Type of tokens (input, output, cached)
            count: Number of tokens used
        """
        api_tokens_used.labels(model=model, type=token_type).inc(count)

    @staticmethod
    def record_api_cost(model: str, cost: float) -> None:
        """
        Record API cost.

        Args:
            model: Model name
            cost: Cost in dollars
        """
        api_cost_dollars.labels(model=model).inc(cost)

    @staticmethod
    def set_memory_usage(component: str, bytes_used: int) -> None:
        """
        Set memory usage for a component.

        Args:
            component: Component name
            bytes_used: Memory usage in bytes
        """
        memory_usage_bytes.labels(component=component).set(bytes_used)
