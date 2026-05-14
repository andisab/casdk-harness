"""Monitoring and metrics collection for agent sessions."""

import asyncio
import base64
import os
import threading
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import structlog
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, make_wsgi_app

logger = structlog.get_logger(__name__)


class QuietWSGIRequestHandler(WSGIRequestHandler):
    """WSGI request handler that suppresses access logs.

    The default WSGIRequestHandler logs every request to stderr,
    which pollutes the console output during interactive sessions.
    """

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress all HTTP access log messages."""
        pass


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

        # Create and start server in a daemon thread with quiet handler
        server = make_server("", port, app, handler_class=QuietWSGIRequestHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        return server
    except Exception as e:
        logger.error("Failed to start authenticated metrics server", error=str(e))
        return None

# Prometheus Metrics
#
# Naming convention: harness-specific metrics use the `harness_` prefix.
# Token, cost, and cache metrics that the Claude Code CLI now emits natively
# (claude_code_token_usage_tokens_total, claude_code_cost_usage_USD_total —
# both segmented by model + query_source + type) have been removed in favor
# of the SDK-emitted equivalents. CGF metrics keep their `cgf_` prefix.
agent_requests_total = Counter(
    "harness_agent_requests_total",
    "Total agent requests handled by the harness",
    ["agent", "status"],
)

agent_duration_seconds = Histogram(
    "harness_agent_duration_seconds",
    "Agent execution time in seconds",
    ["agent"],
)

agent_active_sessions = Gauge(
    "harness_agent_active_sessions",
    "Number of active agent sessions",
    ["agent"],
)

checkpoint_size_bytes = Gauge(
    "harness_checkpoint_size_bytes",
    "Size of checkpoint files in bytes",
)

workspace_files_total = Gauge(
    "harness_workspace_files_total",
    "Total number of files in workspace",
)

memory_usage_bytes = Gauge(
    "harness_memory_usage_bytes",
    "Memory usage in bytes",
    ["component"],
)

# Interactive Session Metrics
# Note: session_id removed from labels to prevent unbounded Prometheus cardinality
# Per-session metrics are tracked in-memory via SessionMetrics class instead
interactive_session_prompts_total = Counter(
    "harness_session_prompts_total",
    "Total user prompts in interactive sessions",
    ["agent"],
)

interactive_session_responses_total = Counter(
    "harness_session_responses_total",
    "Total agent responses in interactive sessions",
    ["agent"],
)

interactive_session_duration_seconds = Histogram(
    "harness_session_duration_seconds",
    "Interactive session duration in seconds",
    ["agent"],
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600, 7200],  # Up to 2 hours
)

interactive_tool_calls_total = Counter(
    "harness_tool_calls_total",
    "Total tool calls in interactive sessions",
    ["agent", "tool_name", "status"],
)

interactive_message_types_total = Counter(
    "harness_message_types_total",
    "Count of message types in interactive sessions",
    ["agent", "message_type"],
)

# CGF Stage 3 — Eval Framework Metrics (Phase A.6)
#
# (Five legacy cgf_* instruments — cgf_spans_collected_total,
# cgf_spans_exported_total, cgf_adapter_transforms_total,
# cgf_reward_composite, cgf_feedback_dimensions — were removed
# 2026-05-14 after the G0 emission audit (docs/OBSERVABILITY.md § 3)
# confirmed zero call sites for any of them.  They were holdovers
# from an earlier optimization-store / reward-pipeline architecture
# simplified during Block 4.  The harness_eval_* family below
# functionally replaces them for Phase A onwards.)
#
# Cardinality notes:
# - ``arm`` ∈ {baseline, candidate} (2 values)
# - ``level`` ∈ {unit, trajectory, e2e} (3 values)
# - ``status`` ∈ {pass, fail, no_decision} (3 values)
# - ``phase`` ∈ {EVAL_DESIGN, EXECUTION_EVAL} (2 values)
# - ``model`` is the judge model alias / ID — bounded to a small set
# - ``resource_type`` ∈ the project-defined enum (~7 values)
#
# We deliberately do NOT label by ``scenario_id`` — that would unboundedly
# grow as new SPECs are evaluated.  Per-scenario detail lives in
# ``eval-results.json`` on disk.

harness_eval_tokens_to_goal = Histogram(
    "harness_eval_tokens_to_goal",
    "Tokens spent per resource until a candidate promotes (sum across "
    "feedback iterations).  Observed at promotion time.",
    ["resource_type"],
    buckets=[
        10_000,
        50_000,
        100_000,
        500_000,
        1_000_000,
        5_000_000,
        10_000_000,
    ],
)

harness_eval_scenarios_total = Counter(
    "harness_eval_scenarios_total",
    "Eval scenarios run, by level, status, and arm.",
    ["level", "status", "arm"],
)

harness_eval_arm_score = Histogram(
    "harness_eval_arm_score",
    "Per-scenario arm pass-rate distribution (0.0-1.0) by arm and level.",
    ["arm", "level"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

harness_eval_phase_duration_seconds = Histogram(
    "harness_eval_phase_duration_seconds",
    "Wall-clock duration of EVAL_DESIGN and EXECUTION_EVAL phases.",
    ["phase"],
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600, 7200],
)

harness_eval_judge_no_decision_total = Counter(
    "harness_eval_judge_no_decision_total",
    "LLM-judge no-decision events (parse failures or transport errors "
    "after retry).  By judge model.",
    ["model"],
)


# Run-level status gauges (low cardinality, always populated during a run).
# Designed for Grafana stat-panel queries like
# ``max by (phase) (harness_run_phase_info > 0)``.
harness_run_phase_info = Gauge(
    "harness_run_phase_info",
    "Current optimization run phase indicator (1 = active, 0 = inactive). "
    "Labels: resource (workspace-relative resource path), "
    "phase (state-machine name, e.g. research, research_iterate, design, "
    "generate, eval_design, iterate, execution_eval, validate, complete).",
    ["resource", "phase"],
)

harness_run_iteration = Gauge(
    "harness_run_iteration",
    "Current iteration count for an in-flight optimization run.",
    ["resource"],
)

harness_run_path_info = Gauge(
    "harness_run_path_info",
    "Active optimization path indicator (1 = active, 0 = inactive). "
    "path is 'single' (cgf_session.py for one resource at a time) or "
    "'multi' (multi_resource_orchestrator.py for plugin/skill-set/workflow "
    "SPECs). Used by the Grafana 'Active Run Status' row to render the "
    "correct pipeline panel for the run that's currently active.",
    ["resource", "path"],
)

_RUN_PATHS = ("single", "multi")


def record_run_path(resource: str, path: str) -> None:
    """Mark `path` (single | multi) as the active optimization path for
    `resource`.  Clears the other path to 0 so the dashboard query
    `harness_run_path_info == 1` returns exactly one path label.
    """
    if path not in _RUN_PATHS:
        logger.warning("record_run_path: unknown path", path=path)
        return
    try:
        for p in _RUN_PATHS:
            harness_run_path_info.labels(resource=resource, path=p).set(
                1 if p == path else 0
            )
    except Exception as e:  # pragma: no cover — observability never raises
        logger.debug("record_run_path failed", error=str(e))

_active_phases: dict[str, str] = {}

# Phase progression for Grafana — ordered set of every phase name either
# pipeline (single-resource cgf_session.py and multi-resource orchestrator) can
# emit. Pre-seeded with value 0 at run start so the dashboard bargauge shows
# all phases up front, with one of them transitioning to 1 as the run
# advances. Keep this synchronized with cgf_session.py phase transitions and
# OptimizationPhase enum (lowercased).
KNOWN_RUN_PHASES: tuple[str, ...] = (
    "research",
    "design",
    "qa",
    "test_gen",
    "generate",
    "optimize",
    "eval_design",
    "iterate",
    "execution_eval",
    "evaluate",
    "validate",
    "finalize",
    "complete",
    "failed",  # contract-violation terminal state
)


def init_run_phases(resource: str) -> None:
    """Seed phase gauge with 0 for every known phase so the Grafana bargauge
    shows the full progression from the start of the run."""
    try:
        for phase in KNOWN_RUN_PHASES:
            harness_run_phase_info.labels(resource=resource, phase=phase).set(0)
    except Exception as e:  # pragma: no cover
        logger.debug("init_run_phases failed", error=str(e))


def record_phase_entry(resource: str, phase: str) -> None:
    """Record entering a new phase. Marks any previous phase for the same
    resource as inactive (set to 0) and the new phase as active (set to 1).

    Safe to call from any code path; failures are swallowed so observability
    code never breaks the pipeline.
    """
    try:
        prev = _active_phases.get(resource)
        if prev and prev != phase:
            harness_run_phase_info.labels(resource=resource, phase=prev).set(0)
        _active_phases[resource] = phase
        harness_run_phase_info.labels(resource=resource, phase=phase).set(1)
    except Exception as e:  # pragma: no cover — observability must never raise
        logger.debug("record_phase_entry failed", error=str(e))


def record_iteration(resource: str, iteration: int) -> None:
    """Record current iteration count for a resource."""
    try:
        harness_run_iteration.labels(resource=resource).set(iteration)
    except Exception as e:  # pragma: no cover
        logger.debug("record_iteration failed", error=str(e))


# Run config info-metric — exposed as a single-row table on the Grafana
# overview dashboards via "Labels to fields" transform. Set to 1 at run
# start with every config dimension as a label; cleared to 0 at run end so
# stale rows don't accumulate.
#
# Cardinality caveat: token_budget and max_iterations are stringified
# numbers. For a single-developer harness this is fine. Do not point this
# series at a long-lived multi-tenant Prometheus without first moving the
# numeric dimensions to a separate event log.
harness_run_config_info = Gauge(
    "harness_run_config_info",
    "Active run configuration (info-metric, 1 = active run, 0 = cleared). "
    "Labels: resource, path (single|multi), mode (optimize|interactive|"
    "autonomous), model, effort, eval_enabled, token_budget, max_iterations.",
    [
        "resource",
        "path",
        "mode",
        "model",
        "effort",
        "eval_enabled",
        "token_budget",
        "max_iterations",
    ],
)

# Run start timestamp — used by the Grafana "Run Elapsed" stat panel as
# ``time() - harness_run_start_timestamp{resource="..."}``. Set at the same
# call site as ``init_run_phases`` and ``record_run_path``.
harness_run_start_timestamp = Gauge(
    "harness_run_start_timestamp",
    "Unix epoch seconds at which the active run started. "
    "Used by Grafana to compute run elapsed time as time() - this gauge.",
    ["resource"],
)

# Task progress — populated by autonomous mode whenever task_list.json is
# rewritten. Powers the Grafana D65 (Mode: Autonomous) "Task Progress"
# header panels.  Status maps to TaskItem.status:
#   completed = "PASS", failed = "FAIL", pending = None.
harness_task_progress = Gauge(
    "harness_task_progress",
    "Autonomous-mode task counts by status. "
    "Status is one of: completed, failed, pending.",
    ["status"],
)


def record_run_config(
    resource: str,
    path: str,
    mode: str,
    model: str,
    effort: str,
    eval_enabled: bool,
    token_budget: int,
    max_iterations: int,
) -> None:
    """Set the run config info-metric to 1 with all config dimensions as
    labels.  Call once at run start.  Observability never raises."""
    try:
        harness_run_config_info.labels(
            resource=resource,
            path=path,
            mode=mode,
            model=model,
            effort=effort,
            eval_enabled=str(eval_enabled).lower(),
            token_budget=str(token_budget),
            max_iterations=str(max_iterations),
        ).set(1)
    except Exception as e:  # pragma: no cover
        logger.debug("record_run_config failed", error=str(e))


def clear_run_config(
    resource: str,
    path: str,
    mode: str,
    model: str,
    effort: str,
    eval_enabled: bool,
    token_budget: int,
    max_iterations: int,
) -> None:
    """Clear the run config info-metric (set to 0) for the same label set
    used at run start.  Call at run end so stale config rows don't linger
    in Grafana."""
    try:
        harness_run_config_info.labels(
            resource=resource,
            path=path,
            mode=mode,
            model=model,
            effort=effort,
            eval_enabled=str(eval_enabled).lower(),
            token_budget=str(token_budget),
            max_iterations=str(max_iterations),
        ).set(0)
    except Exception as e:  # pragma: no cover
        logger.debug("clear_run_config failed", error=str(e))


def record_run_start(resource: str, timestamp: float | None = None) -> None:
    """Record run start timestamp.  Defaults to ``time.time()`` if not
    provided.  Observability never raises."""
    import time

    try:
        ts = timestamp if timestamp is not None else time.time()
        harness_run_start_timestamp.labels(resource=resource).set(ts)
    except Exception as e:  # pragma: no cover
        logger.debug("record_run_start failed", error=str(e))


_TASK_STATUSES = ("completed", "failed", "pending")


def record_task_progress(counts: dict[str, int]) -> None:
    """Record autonomous-mode task counts.  ``counts`` maps status →
    count for status in {completed, failed, pending}; missing
    statuses default to 0 so the gauge reflects the full snapshot.
    Observability never raises."""
    try:
        for status in _TASK_STATUSES:
            harness_task_progress.labels(status=status).set(
                counts.get(status, 0)
            )
    except Exception as e:  # pragma: no cover
        logger.debug("record_task_progress failed", error=str(e))


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
                logger.debug(
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
        logger.debug("System metrics collection started")

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

                # Process memory (RSS). Linux container only — read /proc.
                try:
                    with open("/proc/self/status") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                # Format: "VmRSS:    <kb> kB"
                                kb = int(line.split()[1])
                                memory_usage_bytes.labels(
                                    component="agent_rss"
                                ).set(kb * 1024)
                                break
                except (FileNotFoundError, ValueError, IndexError):
                    pass  # Non-Linux or unparseable — skip silently.

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
    def set_memory_usage(component: str, bytes_used: int) -> None:
        """
        Set memory usage for a component.

        Args:
            component: Component name
            bytes_used: Memory usage in bytes
        """
        memory_usage_bytes.labels(component=component).set(bytes_used)

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

    # (Five legacy CGF MetricsCollector methods — record_span_collected,
    # record_span_exported, record_adapter_transform, record_reward,
    # set_feedback_dimension — were removed 2026-05-14 alongside their
    # backing instruments after the G0 emission audit. They had zero
    # call sites. See the corresponding instrument-block comment above.)
