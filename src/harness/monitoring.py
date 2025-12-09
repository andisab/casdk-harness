"""Monitoring and metrics collection for agent sessions."""

import asyncio
import base64
import os
import threading
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

import structlog
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, make_wsgi_app

logger = structlog.get_logger(__name__)


def _check_metrics_auth(environ: dict[str, Any]) -> bool:
    """Check basic auth credentials for metrics endpoint.

    Args:
        environ: WSGI environment dict

    Returns:
        True if authenticated or no auth required, False otherwise
    """
    auth_token = os.environ.get("METRICS_AUTH_TOKEN", "")
    if not auth_token:
        # No auth configured - allow access (backwards compatible)
        return True

    auth_header = environ.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Basic "):
        return False

    try:
        # Decode base64 credentials
        credentials = base64.b64decode(auth_header[6:]).decode("utf-8")
        return credentials == auth_token
    except Exception:
        return False


def _create_auth_middleware(app: Any) -> Any:
    """Create WSGI middleware that enforces basic auth.

    Args:
        app: WSGI application to wrap

    Returns:
        Wrapped WSGI application with auth middleware
    """
    def wrapped(environ: dict[str, Any], start_response: Any) -> Any:
        if not _check_metrics_auth(environ):
            start_response(
                "401 Unauthorized",
                [
                    ("WWW-Authenticate", 'Basic realm="metrics"'),
                    ("Content-Type", "text/plain"),
                ],
            )
            return [b"Unauthorized"]
        return app(environ, start_response)

    return wrapped


def start_authenticated_http_server(port: int = 9090) -> WSGIServer | None:
    """Start Prometheus metrics HTTP server with optional authentication.

    If METRICS_AUTH_TOKEN environment variable is set, requires basic auth
    with format 'username:password' matching the token value.

    Args:
        port: Port to listen on

    Returns:
        Server instance or None if failed
    """
    try:
        # Create Prometheus WSGI app and wrap with auth middleware
        metrics_app = make_wsgi_app(registry=REGISTRY)
        app = _create_auth_middleware(metrics_app)

        # Create and start server in a daemon thread
        server = make_server("", port, app, handler_class=None)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        return server
    except Exception as e:
        logger.error("Failed to start authenticated metrics server", error=str(e))
        return None

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

# Interactive Session Metrics
# Note: session_id removed from labels to prevent unbounded Prometheus cardinality
# Per-session metrics are tracked in-memory via SessionMetrics class instead
interactive_session_prompts_total = Counter(
    "interactive_session_prompts_total",
    "Total user prompts in interactive sessions",
    ["agent"],
)

interactive_session_responses_total = Counter(
    "interactive_session_responses_total",
    "Total agent responses in interactive sessions",
    ["agent"],
)

interactive_session_duration_seconds = Histogram(
    "interactive_session_duration_seconds",
    "Interactive session duration in seconds",
    ["agent"],
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600, 7200],  # Up to 2 hours
)

interactive_tool_calls_total = Counter(
    "interactive_tool_calls_total",
    "Total tool calls in interactive sessions",
    ["agent", "tool_name", "status"],
)

interactive_message_types_total = Counter(
    "interactive_message_types_total",
    "Count of message types in interactive sessions",
    ["agent", "message_type"],
)

interactive_cache_read_tokens = Counter(
    "interactive_cache_read_tokens_total",
    "Total cache read tokens in interactive sessions",
    ["agent", "model"],
)

interactive_cache_creation_tokens = Counter(
    "interactive_cache_creation_tokens_total",
    "Total cache creation tokens in interactive sessions",
    ["agent", "model"],
)

interactive_cache_hit_ratio = Gauge(
    "interactive_cache_hit_ratio",
    "Cache hit ratio for interactive sessions (read / total input)",
    ["agent"],
)


class MetricsCollector:
    """Collects and exports metrics for monitoring.

    This class uses the singleton pattern to ensure only one metrics
    server is started, avoiding port conflicts across sessions.
    """

    _instance: "MetricsCollector | None" = None
    _server_started: bool = False

    def __new__(
        cls,
        port: int = 9090,  # noqa: ARG004
        workspace_dir: Path | None = None,  # noqa: ARG004
        checkpoint_dir: Path | None = None,  # noqa: ARG004
    ) -> "MetricsCollector":
        """Create or return singleton instance.

        Args are unused here but required to match __init__ signature.
        Actual initialization happens in __init__.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

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
        # Only initialize once (singleton pattern)
        if getattr(self, "_initialized", False):
            return

        self.port = port
        self.workspace_dir = workspace_dir or Path("/workspace")
        self.checkpoint_dir = checkpoint_dir or Path("/memory/checkpoints")
        self.running = False
        self._initialized = True

    def start(self) -> None:
        """Start metrics HTTP server with optional authentication.

        If METRICS_AUTH_TOKEN is set, requires basic auth for /metrics endpoint.
        Otherwise, allows unauthenticated access (backwards compatible).
        """
        # Only start server once across all instances
        if MetricsCollector._server_started:
            logger.debug("Metrics server already running, skipping start")
            return

        try:
            server = start_authenticated_http_server(self.port)
            if server is not None:
                MetricsCollector._server_started = True
                auth_enabled = bool(os.environ.get("METRICS_AUTH_TOKEN"))
                logger.info(
                    "Metrics server started",
                    port=self.port,
                    auth_enabled=auth_enabled,
                )
        except OSError as e:
            # Port already in use - this is OK, metrics are still collected
            if e.errno == 98 or e.errno == 48:  # Linux: 98, macOS: 48 (Address already in use)
                MetricsCollector._server_started = True  # Mark as started even if port in use
                logger.warning(
                    "Metrics server port already in use - skipping HTTP server start. "
                    "Metrics will still be collected and available via Prometheus scraping.",
                    port=self.port
                )
            else:
                logger.error("Failed to start metrics server", error=str(e), exc_info=True)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e), exc_info=True)

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
        cls._server_started = False

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

    @staticmethod
    def record_tokens(agent: str, model: str, usage: dict[str, Any]) -> None:
        """
        Record token usage and calculate API costs from usage dictionary.

        Handles usage data from Claude Agent SDK and tracks both token counts
        and associated costs based on model pricing.

        Args:
            agent: Agent name
            model: Model name (e.g., 'claude-sonnet-4-5-20250929')
            usage: Usage dictionary with token counts:
                - input_tokens: Number of input tokens
                - output_tokens: Number of output tokens
                - cache_read_input_tokens: Number of cached input tokens (optional)

        Pricing (as of October 2025):
            - Sonnet 4.5: $0.003/1K input, $0.015/1K output, $0.0003/1K cached
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_tokens = usage.get("cache_read_input_tokens", 0)

        # Record individual token types
        if input_tokens > 0:
            MetricsCollector.record_token_usage(model, "input", input_tokens)

        if output_tokens > 0:
            MetricsCollector.record_token_usage(model, "output", output_tokens)

        if cached_tokens > 0:
            MetricsCollector.record_token_usage(model, "cached", cached_tokens)

        # Calculate cost based on model pricing (December 2025 pricing)
        # Pricing per 1K tokens:
        # - claude-opus-4-5-*:   $0.015 input, $0.075 output, $0.0015 cached
        # - claude-sonnet-4-5-*: $0.003 input, $0.015 output, $0.0003 cached
        # - claude-3-5-haiku-*:  $0.001 input, $0.005 output, $0.0001 cached
        model_lower = model.lower()
        if "opus" in model_lower:
            input_rate, output_rate, cached_rate = 0.015, 0.075, 0.0015
        elif "haiku" in model_lower:
            input_rate, output_rate, cached_rate = 0.001, 0.005, 0.0001
        else:  # Default to Sonnet pricing
            input_rate, output_rate, cached_rate = 0.003, 0.015, 0.0003

        cost = (
            (input_tokens / 1000.0) * input_rate
            + (output_tokens / 1000.0) * output_rate
            + (cached_tokens / 1000.0) * cached_rate
        )

        if cost > 0:
            MetricsCollector.record_api_cost(model, cost)

            logger.debug(
                "Recorded token usage and cost",
                agent=agent,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                cost_dollars=cost,
            )

    @staticmethod
    def record_user_prompt(agent: str) -> None:
        """
        Record a user prompt in an interactive session.

        Args:
            agent: Agent name
        """
        interactive_session_prompts_total.labels(agent=agent).inc()

    @staticmethod
    def record_agent_response(agent: str) -> None:
        """
        Record an agent response in an interactive session.

        Args:
            agent: Agent name
        """
        interactive_session_responses_total.labels(agent=agent).inc()

    @staticmethod
    def record_interactive_session_duration(agent: str, duration: float) -> None:
        """
        Record interactive session duration.

        Args:
            agent: Agent name
            duration: Duration in seconds
        """
        interactive_session_duration_seconds.labels(agent=agent).observe(duration)

    @staticmethod
    def record_tool_call(agent: str, tool_name: str, status: str = "success") -> None:
        """
        Record a tool call in an interactive session.

        Args:
            agent: Agent name
            tool_name: Name of the tool called
            status: Call status (success, error, timeout)
        """
        interactive_tool_calls_total.labels(
            agent=agent, tool_name=tool_name, status=status
        ).inc()

    @staticmethod
    def record_message_type(agent: str, message_type: str) -> None:
        """
        Record a message type occurrence.

        Args:
            agent: Agent name
            message_type: Type of message (text, tool_use, thinking, tool_result)
        """
        interactive_message_types_total.labels(
            agent=agent, message_type=message_type
        ).inc()

    @staticmethod
    def update_cache_metrics(
        agent: str, model: str, cache_read: int, cache_creation: int, total_input: int
    ) -> None:
        """
        Update cache-related metrics and calculate hit ratio.

        Args:
            agent: Agent name
            model: Model name
            cache_read: Number of cache read tokens
            cache_creation: Number of cache creation tokens
            total_input: Total input tokens
        """
        if cache_read > 0:
            interactive_cache_read_tokens.labels(agent=agent, model=model).inc(
                cache_read
            )

        if cache_creation > 0:
            interactive_cache_creation_tokens.labels(agent=agent, model=model).inc(
                cache_creation
            )

        # Calculate and update cache hit ratio
        if total_input > 0:
            hit_ratio = cache_read / total_input
            interactive_cache_hit_ratio.labels(agent=agent).set(hit_ratio)
