"""Core agent session management and execution."""

import asyncio
import os
import signal
import sys
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import structlog
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    ResultMessage,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from harness.checkpoint import CheckpointManager
from harness.config import HarnessConfig, RuntimeConfig, get_config
from harness.health import HealthServer
from harness.mcp_loader import MCPConfigLoader
from harness.messaging import CircuitBreakerOpenError, RedisMessageBroker
from harness.monitoring import MetricsCollector
from harness.plugin_manager import PluginManager
from harness.security import sanitize_sensitive_data

# In-process MCP servers (Method A)
from mcp_servers.context7 import context7_server
from mcp_servers.docker import docker_server
from mcp_servers.memory import memory_server

logger = structlog.get_logger(__name__)


@contextmanager
def _suppress_subprocess_stderr() -> Generator[None, None, None]:
    """Suppress stderr at the OS file descriptor level.

    This is needed to suppress output from subprocesses (like the Claude CLI)
    that write directly to fd 2, bypassing Python's sys.stderr.
    Used to hide "Using bundled Claude Code CLI: ..." message during connect.

    Note: Only stderr is suppressed to allow stdout (used by Rich spinner) to continue.
    """
    # Flush any pending output
    sys.stderr.flush()

    # Save the original stderr file descriptor
    original_stderr_fd = os.dup(2)

    # Open /dev/null and redirect stderr to it
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)

    try:
        yield
    finally:
        # Restore original stderr
        sys.stderr.flush()
        os.dup2(original_stderr_fd, 2)
        os.close(original_stderr_fd)


# Playwright MCP tools for browser automation (DOM-based, faster)
PLAYWRIGHT_TOOLS = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_drag",
    "mcp__playwright__browser_press_key",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_close",
    "mcp__playwright__browser_navigate_back",
    "mcp__playwright__browser_resize",
    "mcp__playwright__browser_file_upload",
    "mcp__playwright__browser_handle_dialog",
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",
    "mcp__playwright__browser_run_code",
]

# Puppeteer MCP tools for browser automation (visual verification)
PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]


class AgentTimeoutError(Exception):
    """Raised when agent execution exceeds the configured timeout."""

    pass


class SessionTimeoutError(Exception):
    """Raised when the session exceeds the configured maximum duration."""

    pass


class AgentSession:
    """Manages a Claude agent session with checkpointing and monitoring."""

    def __init__(
        self,
        agent_name: str = "main",
        config: HarnessConfig | None = None,
        runtime_config: RuntimeConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        metrics_collector: MetricsCollector | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        permission_mode: str | None = None,
        quiet: bool = False,
    ) -> None:
        """
        Initialize agent session.

        Args:
            agent_name: Name of the agent
            config: Configuration object (uses global config if None)
            runtime_config: Immutable runtime config with CLI overrides applied.
                            If None, created from config with legacy overrides.
            checkpoint_manager: Checkpoint manager instance
            metrics_collector: Metrics collector instance
            model: Deprecated - use runtime_config. Override model.
            system_prompt: Override system prompt (loads from file if None)
            permission_mode: Deprecated - use runtime_config. Override permission mode.
            quiet: Deprecated - use runtime_config. Suppress logging.
        """
        self.agent_name = agent_name
        self.config = config or get_config()

        # Build runtime config if not provided (backward compatibility)
        if runtime_config is None:
            runtime_config = RuntimeConfig.from_harness_config(
                self.config,
                mode="interactive",  # Default assumption for backward compat
                model_override=model,
                permission_mode_override=permission_mode,
                quiet=quiet,
            )
        self.runtime = runtime_config

        # Keep legacy attributes for any code still using them (deprecated)
        self._model_override = model
        self._system_prompt_override = system_prompt
        self._permission_mode_override = permission_mode
        self._quiet = quiet

        # Plugin configuration via PluginManager
        from pathlib import Path
        plugin_base = Path(__file__).parent / "plugins"
        plugin_dirs: list[Path] = []
        # Marketplace first; in-tree last so in-tree wins on duplicate plugin name
        # (lets us migrate plugins one-by-one without immediate breakage).
        marketplace_path = self.config.swe_marketplace_resolved_path
        if marketplace_path is not None:
            marketplace_plugin_dir = marketplace_path / "plugins"
            if marketplace_plugin_dir.exists():
                plugin_dirs.append(marketplace_plugin_dir)
                logger.info(
                    "swe-marketplace plugin source resolved",
                    path=str(marketplace_plugin_dir),
                )
        plugin_dirs.append(plugin_base)
        self.plugin_manager = PluginManager(
            plugin_dirs=plugin_dirs,
            enabled_plugins=self.config.enabled_plugins_list,
        )
        self.plugin_manager.discover()

        # Get plugin paths for SDK to auto-load commands/hooks/skills/MCP
        self.plugins = self.plugin_manager.get_plugin_paths()
        self.plugin_base = plugin_base  # Keep for backward compatibility

        self.checkpoint_manager = checkpoint_manager or CheckpointManager(
            checkpoint_dir=self.config.checkpoint_dir,
            interval=self.config.claude_checkpoint_interval,
            max_checkpoints=self.config.checkpoint_keep_count,
        )
        self.metrics = metrics_collector or MetricsCollector(
            workspace_dir=self.config.workspace_dir,
            checkpoint_dir=self.config.checkpoint_dir,
        )

        # Initialize CGF tracer if enabled
        # Provides span-based execution tracing for optimization
        self.tracer = None
        if self.config.cgf_enabled and self.config.cgf_tracing_enabled:
            try:
                from harness.tracer import get_tracer

                self.tracer = get_tracer(
                    service_name=f"harness.{agent_name}",
                    enabled=True,
                )
                logger.debug("CGF tracer initialized", agent=agent_name)
            except Exception as e:
                logger.warning(
                    "Failed to initialize CGF tracer",
                    agent=agent_name,
                    error=str(e),
                )

        # Initialize Redis message broker for cross-agent communication
        # Only connect when in multi-agent mode (AGENT_NAME explicitly set in docker-compose)
        # Uses circuit breaker pattern for resilience (see messaging.py)
        self.message_broker: RedisMessageBroker | None = None
        self.redis_available: bool = False

        # Check if multi-agent mode is active (AGENT_NAME is set for container agents)
        agent_name_env = os.environ.get("AGENT_NAME")
        if agent_name_env is not None:
            try:
                broker = RedisMessageBroker(config=self.config)
                broker.connect()
                self.message_broker = broker
                self.redis_available = True
                logger.debug(
                    "Redis connected for multi-agent messaging",
                    agent=agent_name,
                    url=self.config.redis_url,
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "Redis circuit breaker open - inter-agent messaging disabled",
                    agent=agent_name,
                    error=str(e),
                )
            except Exception as e:
                logger.warning(
                    "Redis not available - inter-agent messaging disabled",
                    agent=agent_name,
                    error=str(e),
                )
        else:
            logger.debug(
                "Single-agent mode - Redis messaging disabled",
                agent=agent_name,
            )

        # SDK client and session management (persistent across execute() calls)
        self.client: ClaudeSDKClient | None = None  # Persistent SDK client
        self.session_id: str | None = None  # SDK session ID (set on connect)

        # Background task tracking for proper lifecycle management
        # All background tasks (checkpointing, metrics) are tracked here for cleanup
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # Health check server (started in start(), stopped in shutdown())
        self.health_server: HealthServer | None = None

        # Temporary local session ID until SDK connects
        self._local_session_id = f"{agent_name}_{datetime.now().isoformat()}"

        self.state: dict[str, Any] = {
            "agent_name": agent_name,
            "session_id": self._local_session_id,  # Will be updated with SDK session_id
            "started_at": datetime.now().isoformat(),
            "completed_tasks": [],
            "current_task": None,
        }

        # Session timeout tracking (enforces claude_session_timeout config)
        self._session_start_time = datetime.now(UTC)

        # Context budget tracking for graceful session management
        # Budget is calculated based on model's context window
        from harness.config import get_context_window

        self.token_budget = (
            self.config.context_budget_override
            if self.config.context_budget_override
            else get_context_window(self.config.claude_model)
        )
        self.tokens_used = 0

        # Percentage-based warning thresholds (calculated from budget)
        self._budget_warning_thresholds = {
            int(self.token_budget * self.config.context_budget_warning_pct): "warning",
            int(self.token_budget * self.config.context_budget_urgent_pct): "urgent",
            int(self.token_budget * self.config.context_budget_critical_pct): "critical",
        }
        self._triggered_warnings: set[int] = set()

        # Load MCP servers (Phase 1C - Method A + Method B)
        # 1. Load in-process servers (Method A) - docker, context7, memory
        self.inprocess_servers = self._load_inprocess_servers()
        # 2. Load subprocess servers (Method B) - playwright
        subprocess_servers = self._load_mcp_servers(tiers=[1, 2])
        # 3. Merge: in-process takes precedence over subprocess
        self.mcp_servers = {**subprocess_servers, **self.inprocess_servers}

        # Discover all skills (base + plugin)
        self.discovered_skills = self._load_all_skills()

        # Share discovered plugin skills and agents with CLI for display in SystemMessage
        if self.discovered_skills:
            from harness.cli import set_plugin_skills
            plugin_skill_names = [
                name for name, info in self.discovered_skills.items()
                if info.get("source") == "plugin"
            ]
            set_plugin_skills(plugin_skill_names)

        # Share plugin agents with CLI
        plugin_agents = self.plugin_manager.get_all_agents()
        if plugin_agents:
            from harness.cli import set_plugin_agents
            set_plugin_agents(list(plugin_agents.keys()))

        # Consolidated MCP servers log (debug to avoid spinner interference)
        logger.debug(
            "MCP servers loaded",
            inprocess=len(self.inprocess_servers),
            subprocess=len(subprocess_servers),
            total=len(self.mcp_servers),
            servers=list(self.mcp_servers.keys()),
        )

    async def __aenter__(self) -> "AgentSession":
        """Async context manager entry - starts the session."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - shuts down the session."""
        await self.shutdown()

    def _load_all_skills(self) -> dict[str, dict[str, str]]:
        """Discover all skills from base directory and plugins.

        Discovers skills from:
        1. Base skills directory (src/harness/skills/)
        2. Plugin skills directories (via PluginManager)

        Returns:
            Dict mapping skill names to metadata (source, path, plugin)
        """
        from pathlib import Path

        all_skills: dict[str, dict[str, str]] = {}

        # 1. Discover base skills from src/harness/skills/
        base_skills_dir = Path(__file__).parent / "skills"
        if base_skills_dir.exists():
            for skill_path in base_skills_dir.glob("*/SKILL.md"):
                skill_name = skill_path.parent.name
                all_skills[skill_name] = {
                    "source": "base",
                    "path": str(skill_path),
                }

        # 2. Get plugin skills from PluginManager
        plugin_skills = self.plugin_manager.get_all_skills()
        all_skills.update(plugin_skills)

        # Log with breakdown by source
        if all_skills:
            base_count = len([s for s in all_skills.values() if s.get("source") == "base"])
            plugin_count = len([s for s in all_skills.values() if s.get("source") == "plugin"])
            logger.debug(
                "Discovered skills",
                total=len(all_skills),
                base=base_count,
                plugins=plugin_count,
                skills=list(all_skills.keys()),
            )

        return all_skills

    def _load_inprocess_servers(self) -> dict[str, Any]:
        """Load in-process MCP servers (Method A).

        In-process servers run in the same process as the agent, providing:
        - Faster startup (no subprocess spawn)
        - Easier debugging (same process)
        - Python exception handling instead of process exit codes

        Currently loads:
        - docker: Docker container management (Docker SDK, always available)
        - context7: Library documentation lookup (no API key required)
        - memory: Knowledge graph for persistent memory (always available)

        Note: Git, GitHub, and GitLab operations use CLI tools (git, gh, glab)
        via the Bash tool instead of MCP servers.

        Returns:
            Dict mapping server names to SDK server objects
        """
        servers: dict[str, Any] = {}

        # Docker - always available (uses Docker SDK)
        servers["docker"] = docker_server

        # Context7 - always available (no API key required, works with rate limits)
        servers["context7"] = context7_server

        # Memory - always available (knowledge graph for persistent memory)
        servers["memory"] = memory_server

        logger.debug(
            "In-process MCP servers loaded",
            count=len(servers),
            servers=list(servers.keys()),
        )

        return servers

    def _load_mcp_servers(self, tiers: list[int] | None = None) -> dict[str, Any]:
        """Load subprocess MCP servers (Method B) for specified tiers.

        Phase 1C Architecture: Subprocess servers for external dependencies.
        - Tier 1: Empty (all fast servers now in-process)
        - Tier 2: External servers (playwright) - 120s timeout

        Note: git, docker, context7, and github are now loaded as in-process
        servers (Method A). See _load_inprocess_servers() for those.

        All servers here are subprocess servers using stdio protocol.

        Args:
            tiers: List of tier numbers to load (default: [1])

        Returns:
            Dict mapping server names to stdio server configurations
        """
        if tiers is None:
            tiers = [1]

        from pathlib import Path

        # Get plugin paths for merging plugin .mcp.json files
        plugin_paths = [Path(p["path"]) for p in self.plugins]

        loader = MCPConfigLoader()
        base_mcp_path = Path(__file__).parent / "config" / ".mcp.json"

        all_mcp_servers = {}
        loaded_tiers = []

        for tier in tiers:
            try:
                tier_config = loader.load_tier(
                    base_path=base_mcp_path,
                    plugin_paths=plugin_paths,
                    tier=tier,
                    check_keys=True  # Check API keys and skip servers with missing keys
                )

                # Map all servers as subprocess servers (SDK format: just command + args)
                for server_name, server_config in tier_config["mcpServers"].items():
                    # Format for SDK: {"command": "...", "args": [...]}
                    # NOTE: Do NOT wrap with "type": "stdio" - SDK handles transport internally
                    mcp_config = {
                        "command": server_config["command"],
                        "args": server_config["args"],
                    }
                    if server_config.get("env"):
                        mcp_config["env"] = server_config["env"]
                    all_mcp_servers[server_name] = mcp_config
                    logger.debug(
                        "Loaded MCP server config",
                        server=server_name,
                        command=server_config["command"],
                        tier=tier,
                    )

                loaded_tiers.append(tier)

            except FileNotFoundError as e:
                if tier == 1:
                    # Only warn for Tier 1 (base config missing)
                    logger.warning(
                        "Base .mcp.json not found, MCP servers disabled",
                        error=str(e),
                        expected_path=str(base_mcp_path)
                    )
                    return {}  # If base config missing, can't load anything
                else:
                    logger.debug(
                        "No servers found for tier (expected if no servers in tier)",
                        tier=tier
                    )

            except Exception as e:
                logger.error(
                    "Failed to load MCP tier, continuing with other tiers",
                    error=str(e),
                    tier=tier
                )
                # Continue loading other tiers

        if all_mcp_servers:
            logger.debug(
                "Subprocess MCP servers loaded",
                tiers=loaded_tiers,
                count=len(all_mcp_servers),
                servers=list(all_mcp_servers.keys())
            )
        elif tiers != [1]:  # Only warn if we expected servers (tier 1 is now empty by design)
            logger.debug("No subprocess MCP servers loaded", requested_tiers=tiers)

        return all_mcp_servers

    def _load_system_prompt(self) -> str:
        """Load system prompt based on AGENT_NAME environment variable.

        Supports different prompts for different agent types:
        - main (default): main-interactivedev-agent.md
        - agent-two: agent-two.md (Evaluator, default: code review)
        - agent-three: agent-three.md (Validator, default: testing)

        Returns:
            System prompt content with plugin skills appended if any.
        """
        import os
        from pathlib import Path

        # Map agent names to their prompt files
        prompt_map = {
            "main": "main-interactivedev-agent.md",
            "agent-two": "agent-two.md",
            "agent-three": "agent-three.md",
        }

        # Get agent name from environment (default: main)
        agent_name = os.environ.get("AGENT_NAME", "main")
        prompt_filename = prompt_map.get(agent_name, "main-interactivedev-agent.md")

        # Load the appropriate prompt file
        prompt_file = Path(__file__).parent / "prompts" / prompt_filename

        if prompt_file.exists():
            system_prompt = prompt_file.read_text()
            logger.info(
                "Loaded system prompt for agent",
                agent_name=agent_name,
                prompt_file=prompt_filename,
            )
        else:
            logger.warning(
                "System prompt file not found, using minimal prompt",
                agent_name=agent_name,
                expected_path=str(prompt_file),
            )
            workspace = str(self.config.workspace_dir)
            system_prompt = f"Work in {workspace} directory. Use absolute paths."

        # Append discovered skills info if any
        if self.discovered_skills:
            skills_list = "\n".join([
                f"  - {name} ({info.get('plugin', 'base')} {'plugin' if info['source'] == 'plugin' else 'skill'})"
                for name, info in self.discovered_skills.items()
            ])
            system_prompt += f"""

---

## Available Skills

Skills discovered:
{skills_list}

Use them via: Skill tool with skill name (e.g., "debugging")
"""

        return system_prompt

    def _build_sdk_options(self) -> ClaudeAgentOptions:
        """Build SDK options with MCP servers and configuration."""
        import os

        # Prepare environment variables for Claude CLI subprocess
        # CRITICAL: Pass PYTHONUNBUFFERED=1 to ensure stdout is unbuffered
        cli_env = os.environ.copy()
        cli_env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered mode

        # Use override or load from file/config
        system_prompt = self._system_prompt_override or self._load_system_prompt()
        # Use RuntimeConfig for model and permission_mode (immutable, CLI overrides applied)
        model = self.runtime.model
        permission_mode = self.runtime.permission_mode

        # Built-in tools + MCP browser automation tools
        allowed_tools = [
            # Built-in SDK tools
            "Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch", "Skill",
            # Playwright MCP tools (DOM-based, faster)
            *PLAYWRIGHT_TOOLS,
            # Puppeteer MCP tools (visual verification)
            *PUPPETEER_TOOLS,
        ]

        logger.debug(
            "Building SDK options",
            allowed_tools_count=len(allowed_tools),
            mcp_servers=list(self.mcp_servers.keys()),
            permission_mode=permission_mode,
            model=model,
        )

        # Plugin sub-agents are exposed to the Task tool by the SDK directly
        # via ``plugins=`` (verified 2026-05-05; see docs/REFACTOR.md
        # "SDK upstream investigation"). Harness sub-agents are auto-discovered
        # from ``.claude/agents/`` through ``setting_sources=["project"]``.
        # No ``agents=`` workaround needed.
        return ClaudeAgentOptions(
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            max_turns=self.config.claude_max_turns,
            cwd="/app",  # SDK needs /app to find .claude/skills/
            model=model,
            mcp_servers=self.mcp_servers,
            setting_sources=["project"],
            plugins=self.plugins,
            skills="all",  # SDK 0.1.72+: "all" or list[str]; None hides skills from the Skill tool
            system_prompt=system_prompt,
            env=cli_env,
            stderr=lambda msg: logger.debug(f"[CLI stderr] {msg}"),
        )

    async def start(self) -> None:
        """Start the agent session and background tasks."""
        logger.debug("Starting agent session", agent=self.agent_name)

        # Create and connect persistent SDK client
        options = self._build_sdk_options()
        self.client = ClaudeSDKClient(options=options)

        try:
            # Suppress "Using bundled Claude Code CLI: ..." message from SDK
            with _suppress_subprocess_stderr():
                await self.client.connect()
            logger.debug("SDK client connected", agent=self.agent_name)

            # Reset budget tracking for new session
            # Each session starts fresh with its own context window
            self.tokens_used = 0
            self._triggered_warnings.clear()

            # Capture session ID from first SystemMessage
            # Note: SDK automatically sends SystemMessage on connect
            # We'll capture it in the first execute() call
            # For now, session_id remains None until first query

        except Exception as e:
            logger.error(
                "Failed to connect SDK client",
                agent=self.agent_name,
                error=str(e),
            )
            raise

        # Start metrics collection
        self.metrics.start()
        self.metrics.set_active_sessions(self.agent_name, 1)

        # Start auto-checkpoint task (tracked for cleanup)
        checkpoint_task = asyncio.create_task(
            self.checkpoint_manager.auto_checkpoint(
                get_state_fn=self._get_state_async
            )
        )
        self._background_tasks.add(checkpoint_task)
        checkpoint_task.add_done_callback(self._background_tasks.discard)

        # Start metrics collection task (tracked for cleanup)
        metrics_task = asyncio.create_task(self.metrics.collect_system_metrics())
        self._background_tasks.add(metrics_task)
        metrics_task.add_done_callback(self._background_tasks.discard)

        # Start health check server
        self.health_server = HealthServer(session=self)
        await self.health_server.start()

        # Consolidated startup log (debug level to avoid spinner interference)
        logger.debug(
            "Agent session ready",
            agent=self.agent_name,
            mcp_servers=len(self.mcp_servers),
            skills=len(self.discovered_skills),
            checkpoint_interval=f"{self.checkpoint_manager.interval}s",
            health_port=8080,
            metrics_port=9090,
        )

    async def execute(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute agent task with retry and monitoring.

        Args:
            prompt: Task prompt for the agent
            **kwargs: Additional arguments for execution

        Yields:
            Agent response messages
        """
        start_time = datetime.now()
        self.state["current_task"] = sanitize_sensitive_data(prompt)

        # Check session timeout before executing
        self._check_session_timeout()

        # Start CGF execution span if tracing is enabled
        exec_span = self._start_execution_span(prompt)
        tool_count = 0
        token_usage: dict[str, int] = {"input": 0, "output": 0}

        try:
            logger.info(
                "Executing agent task",
                agent=self.agent_name,
                prompt_length=len(prompt),
                inactivity_timeout=self.config.claude_api_timeout,
            )

            # Execute with retry and inactivity timeout
            # Each message resets the timer - only timeout if no activity
            try:
                async_gen = self._execute_with_retry(prompt, **kwargs)
                inactivity_timeout = self.config.claude_api_timeout
                while True:
                    try:
                        message = await asyncio.wait_for(
                            anext(async_gen),
                            timeout=inactivity_timeout,
                        )

                        # Track tool calls for CGF tracing
                        if exec_span and isinstance(message, dict):
                            if message.get("type") == "tool_use":
                                tool_count += 1
                                self._trace_tool_call(
                                    exec_span,
                                    message.get("name", "unknown"),
                                    str(message.get("input", ""))[:500],
                                )
                            # Track token usage from result messages
                            if message.get("type") == "result" and "usage" in message:
                                usage = message["usage"]
                                token_usage["input"] += usage.get("input_tokens", 0)
                                token_usage["output"] += usage.get("output_tokens", 0)

                        yield message
                    except StopAsyncIteration:
                        break
            except TimeoutError:
                self.metrics.record_request(self.agent_name, "timeout")
                logger.error(
                    "Inactivity timeout exceeded",
                    agent=self.agent_name,
                    inactivity_timeout=self.config.claude_api_timeout,
                )
                # End span with timeout error
                self._end_execution_span(
                    exec_span,
                    success=False,
                    error="timeout",
                    tool_count=tool_count,
                    token_usage=token_usage,
                )
                raise AgentTimeoutError(
                    f"Agent inactivity timeout after {self.config.claude_api_timeout}s without messages"
                ) from None

            # Record successful execution
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics.record_request(self.agent_name, "success")
            self.metrics.record_duration(self.agent_name, duration)

            self.state["completed_tasks"].append(
                {
                    "prompt": sanitize_sensitive_data(prompt[:100]),  # Sanitized first 100 chars
                    "completed_at": datetime.now().isoformat(),
                    "duration": duration,
                }
            )
            self.state["current_task"] = None

            logger.info(
                "Task completed successfully",
                agent=self.agent_name,
                duration=duration,
            )

            # End span successfully
            self._end_execution_span(
                exec_span,
                success=True,
                tool_count=tool_count,
                token_usage=token_usage,
            )

        except AgentTimeoutError:
            # Re-raise timeout errors (already logged and recorded above)
            raise
        except Exception as e:
            self.metrics.record_request(self.agent_name, "error")
            logger.error(
                "Task execution failed",
                agent=self.agent_name,
                error=str(e),
                exc_info=True,
            )
            # End span with error
            self._end_execution_span(
                exec_span,
                success=False,
                error=str(e),
                tool_count=tool_count,
                token_usage=token_usage,
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def _execute_with_retry(
        self,
        prompt: str,
        **_kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute using persistent SDK client (maintains conversation history).

        The client is created once in start() and reused for all queries,
        which allows the SDK to maintain conversation context across messages.

        Args:
            prompt: Task prompt
            **_kwargs: Additional arguments (unused, kept for API compatibility)

        Yields:
            Agent response messages

        Raises:
            RuntimeError: If SDK client not connected (call start() first)
        """
        if not self.client:
            raise RuntimeError("SDK client not connected. Call start() first.")

        logger.debug("Sending query to persistent SDK client", prompt_length=len(prompt))

        try:
            # Send query to persistent client (maintains conversation context)
            await self.client.query(prompt)
            logger.debug("Query sent to SDK client", agent=self.agent_name)

            # Receive messages from persistent client
            first_message = True
            async for message in self.client.receive_response():
                logger.debug(
                    "Message received from SDK",
                    message_type=type(message).__name__,
                    agent=self.agent_name,
                )

                # Capture session ID from first SystemMessage
                if first_message and message.__class__.__name__ == "SystemMessage":
                    if hasattr(message, "data"):
                        sdk_session_id = message.data.get("session_id")
                        if sdk_session_id:
                            self.session_id = sdk_session_id
                            self.state["session_id"] = sdk_session_id  # Update state too
                            logger.info(
                                "Captured SDK session ID",
                                session_id=self.session_id,
                                agent=self.agent_name,
                            )
                    first_message = False

                # Accumulate token usage for in-process budget tracking. Prometheus
                # token + cost counters are emitted by the Claude Code CLI directly
                # (claude_code_token_usage_tokens_total, claude_code_cost_usage_USD_total).
                if isinstance(message, ResultMessage) and hasattr(message, "usage"):
                    usage = message.usage
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    self.tokens_used += input_tokens + output_tokens

                    logger.debug(
                        "Token usage recorded",
                        agent=self.agent_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_tokens=usage.get("cache_read_input_tokens", 0),
                        tokens_used_total=self.tokens_used,
                        token_budget=self.token_budget,
                    )

                    # Check budget thresholds and yield warning if crossed
                    budget_warning = self._check_budget_threshold()
                    if budget_warning:
                        yield budget_warning

                yield message

        except CLINotFoundError as e:
            logger.error(
                "Claude CLI not found - ensure Claude Agent SDK is installed",
                error=str(e),
                exc_info=True,
            )
            raise

        except CLIConnectionError as e:
            logger.error(
                "SDK client connection error",
                error=str(e),
                exc_info=True,
            )
            # Let retry decorator handle reconnection
            raise

        except ProcessError as e:
            logger.error(
                "Claude CLI process error",
                exit_code=getattr(e, "exit_code", None),
                error=str(e),
                exc_info=True,
            )
            raise

        except CLIJSONDecodeError as e:
            logger.error(
                "Failed to decode Claude CLI JSON response",
                raw_output=getattr(e, "raw_output", None),
                error=str(e),
                exc_info=True,
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during agent execution",
                error=str(e),
                exc_info=True,
            )
            raise

    def publish_task_result(self, task_id: str, result: dict[str, Any]) -> str | None:
        """
        Publish task result to Redis for other agents to consume.

        Args:
            task_id: Unique task identifier
            result: Result data to publish

        Returns:
            Message ID if published successfully, None otherwise
        """
        if not self.redis_available or self.message_broker is None:
            logger.debug(
                "Skipping task result publish - Redis not available",
                agent=self.agent_name,
                task_id=task_id,
            )
            return None

        try:
            message_id = self.message_broker.publish_result(
                agent_id=self.agent_name,
                result={"task_id": task_id, **result},
                stream_name="agent:tasks",
            )
            logger.info(
                "Published task result",
                agent=self.agent_name,
                task_id=task_id,
                message_id=message_id,
            )
            return message_id
        except Exception as e:
            logger.error(
                "Failed to publish task result",
                agent=self.agent_name,
                task_id=task_id,
                error=str(e),
                exc_info=True,
            )
            return None

    async def wait_for_dependency(
        self,
        dependency_agent: str,
        task_id: str,
        timeout: int = 60,
    ) -> dict[str, Any] | None:
        """
        Wait for a task result from another agent.

        Args:
            dependency_agent: Name of the agent to wait for
            task_id: Task ID to wait for
            timeout: Maximum wait time in seconds

        Returns:
            Task result if found within timeout, None otherwise
        """
        if not self.redis_available or self.message_broker is None:
            logger.debug(
                "Cannot wait for dependency - Redis not available",
                agent=self.agent_name,
                dependency_agent=dependency_agent,
                task_id=task_id,
            )
            return None

        logger.info(
            "Waiting for dependency",
            agent=self.agent_name,
            dependency_agent=dependency_agent,
            task_id=task_id,
            timeout=timeout,
        )

        start_time = datetime.now()
        last_id = "0"

        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                # Read messages from stream
                messages = self.message_broker.consume_results(
                    stream_name="agent:tasks",
                    last_id=last_id,
                    count=10,
                    block=1000,  # Block for 1 second
                )

                for msg in messages:
                    # Update last_id for next iteration
                    last_id = msg["message_id"]

                    # Check if this is the message we're waiting for
                    if (
                        msg["agent_id"] == dependency_agent
                        and msg["content"].get("task_id") == task_id
                    ):
                        logger.info(
                            "Dependency satisfied",
                            agent=self.agent_name,
                            dependency_agent=dependency_agent,
                            task_id=task_id,
                        )
                        return msg["content"]

                # Brief sleep before next iteration
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(
                    "Error while waiting for dependency",
                    agent=self.agent_name,
                    dependency_agent=dependency_agent,
                    task_id=task_id,
                    error=str(e),
                    exc_info=True,
                )
                return None

        logger.warning(
            "Dependency wait timeout",
            agent=self.agent_name,
            dependency_agent=dependency_agent,
            task_id=task_id,
            timeout=timeout,
        )
        return None

    async def _get_state_async(self) -> dict[str, Any]:
        """
        Get current agent state for checkpointing (async version).

        Returns:
            Current state dictionary with SDK session ID for resume capability
        """
        state = self.state.copy()
        # Explicitly include SDK session ID for checkpoint resume
        state["sdk_session_id"] = self.session_id
        state["timestamp"] = datetime.now().isoformat()
        return state

    def get_state(self) -> dict[str, Any]:
        """
        Get current agent state.

        Returns:
            Current state dictionary
        """
        return self.state.copy()

    def get_session_info(self) -> dict[str, Any]:
        """Get session information for display without an API call.

        Returns local session info including MCP servers, agents, skills.
        Used to display session summary at startup without needing
        to make an API call to the SDK.

        Returns:
            Dict with session_id, model, mcp_servers, agents, skills, tools,
            and counts for harness_agents and plugin_agents.
        """
        from harness.agents.definitions import AGENT_DEFINITIONS

        # MCP servers with status
        mcp_servers = [
            {"name": name, "status": "connected"}
            for name in self.mcp_servers
        ]

        # Harness agents from definitions
        harness_agents = list(AGENT_DEFINITIONS.keys())

        # Plugin agents from PluginManager
        plugin_agents = list(self.plugin_manager.get_all_agents().keys())

        # All agents combined
        all_agents = harness_agents + plugin_agents

        # Discovered skills (base + plugin) with source info
        base_skills = []
        plugin_skills = []
        if self.discovered_skills:
            for name, skill_info in self.discovered_skills.items():
                if skill_info.get("source") == "plugin":
                    plugin_skills.append(name)
                else:
                    base_skills.append(name)

        return {
            "session_id": self.session_id or self._local_session_id,
            "model": self.runtime.model,
            "mcp_servers": mcp_servers,
            "agents": all_agents,
            "harness_agents": harness_agents,
            "plugin_agents": plugin_agents,
            "harness_agent_count": len(harness_agents),
            "plugin_agent_count": len(plugin_agents),
            "skills": base_skills + plugin_skills,
            "base_skills": base_skills,
            "plugin_skills": plugin_skills,
            "base_skill_count": len(base_skills),
            "plugin_skill_count": len(plugin_skills),
            "tools": [],  # Tools are only known after SDK connect
        }

    async def recover_from_checkpoint(self) -> bool:
        """
        Attempt to recover from latest checkpoint and resume conversation.

        If the checkpoint contains an SDK session ID, attempts to resume
        the conversation from that session to maintain conversation context.

        Returns:
            True if recovery successful, False otherwise
        """
        checkpoint = self.checkpoint_manager.load_latest_checkpoint()

        if checkpoint is None:
            logger.debug("No checkpoint found for recovery")
            return False

        try:
            recovered_state = self.checkpoint_manager.recover_from_checkpoint(checkpoint)
            self.state.update(recovered_state)

            # Extract summary info for consolidated log
            workspace_snapshot = checkpoint.get("workspace_snapshot", {})
            memory_snapshot = checkpoint.get("memory_snapshot", {})

            logger.info(
                "Checkpoint recovered",
                checkpoint_time=checkpoint.get("timestamp"),
                workspace_files=workspace_snapshot.get("file_count", 0),
                workspace_type=workspace_snapshot.get("type", "unknown"),
                memory_entities=memory_snapshot.get("context_size", 0),
            )

            # Resume SDK session if session_id exists in checkpoint
            if "sdk_session_id" in recovered_state and recovered_state["sdk_session_id"]:
                try:
                    await self.resume_from_session_id(recovered_state["sdk_session_id"])
                    logger.debug(
                        "Resumed SDK conversation from checkpoint",
                        session_id=recovered_state["sdk_session_id"],
                    )
                except Exception as e:
                    logger.warning(
                        "Could not resume SDK session, starting fresh conversation",
                        error=str(e),
                    )

            return True

        except Exception as e:
            logger.error(
                "Failed to recover from checkpoint",
                error=str(e),
                exc_info=True,
            )
            return False

    def _check_budget_threshold(self) -> dict[str, Any] | None:
        """
        Check if any budget thresholds have been crossed.

        Returns warning message dict if a threshold was crossed, None otherwise.
        Each threshold only triggers once per session.
        """
        for threshold, level in sorted(self._budget_warning_thresholds.items()):
            if (
                self.tokens_used >= threshold
                and threshold not in self._triggered_warnings
            ):
                self._triggered_warnings.add(threshold)

                remaining = self.token_budget - self.tokens_used
                percent_used = (self.tokens_used / self.token_budget) * 100

                logger.warning(
                    "Context budget threshold crossed",
                    level=level,
                    tokens_used=self.tokens_used,
                    tokens_remaining=remaining,
                    percent_used=f"{percent_used:.1f}%",
                    agent=self.agent_name,
                )

                # Trigger checkpoint at urgent threshold
                if level == "urgent":
                    asyncio.create_task(self._save_budget_checkpoint())

                return {
                    "type": "system",
                    "subtype": "context_budget_warning",
                    "level": level,
                    "content": self._format_budget_warning(level, percent_used, remaining),
                    "tokens_used": self.tokens_used,
                    "tokens_remaining": remaining,
                    "percent_used": percent_used,
                }

        return None

    def _check_session_timeout(self) -> None:
        """Check if session has exceeded the configured timeout.

        Raises:
            SessionTimeoutError: If session has exceeded claude_session_timeout seconds.
        """
        elapsed = (datetime.now(UTC) - self._session_start_time).total_seconds()
        timeout = self.config.claude_session_timeout

        if elapsed > timeout:
            hours = elapsed / 3600
            logger.error(
                "Session timeout exceeded",
                elapsed_seconds=elapsed,
                elapsed_hours=f"{hours:.2f}",
                timeout_seconds=timeout,
                agent=self.agent_name,
            )
            raise SessionTimeoutError(
                f"Session exceeded {timeout}s timeout (running for {hours:.2f}h). "
                "Save your work and start a new session."
            )

    # =========================================================================
    # CGF Tracing Methods
    # =========================================================================

    def _start_execution_span(self, prompt: str) -> Any | None:
        """Start a span for agent execution.

        Args:
            prompt: The task prompt being executed.

        Returns:
            The started span, or None if tracing is disabled.
        """
        if not self.tracer:
            return None

        try:
            from harness.tracer import SpanKind

            span = self.tracer.start_span(
                name=f"agent.execute.{self.agent_name}",
                kind=SpanKind.AGENT_EXECUTION,
            )
            span.set_attribute("agent.name", self.agent_name)
            span.set_attribute("agent.model", self.runtime.model)
            span.set_attribute("agent.input", prompt[:500])  # Truncate for storage
            span.set_attribute("resource_type", "agent")
            span.set_attribute("resource_id", self.agent_name)
            return span
        except Exception as e:
            logger.warning(
                "Failed to start execution span",
                agent=self.agent_name,
                error=str(e),
            )
            return None

    def _end_execution_span(
        self,
        span: Any,
        success: bool = True,
        error: str | None = None,
        tool_count: int = 0,
        token_usage: dict[str, int] | None = None,
    ) -> None:
        """End an execution span.

        Args:
            span: The span to end.
            success: Whether execution was successful.
            error: Error message if unsuccessful.
            tool_count: Number of tools called during execution.
            token_usage: Token usage statistics.
        """
        if not span or not self.tracer:
            return

        try:
            from harness.tracer import SpanStatus

            span.set_attribute("agent.tool_count", tool_count)
            span.set_attribute("agent.success", success)

            if token_usage:
                span.set_attribute("tokens.input", token_usage.get("input", 0))
                span.set_attribute("tokens.output", token_usage.get("output", 0))

            # Use finish() method with status parameter
            if error:
                span.finish(status=SpanStatus.ERROR, error_message=error)
            else:
                span.finish(status=SpanStatus.OK)
        except Exception as e:
            logger.warning(
                "Failed to end execution span",
                agent=self.agent_name,
                error=str(e),
            )

    def _trace_tool_call(
        self,
        parent_span: Any,
        tool_name: str,
        tool_input: str | None = None,
        success: bool = True,
    ) -> None:
        """Record a tool call as a child span.

        Args:
            parent_span: The parent execution span.
            tool_name: Name of the tool being called.
            tool_input: Input to the tool (truncated).
            success: Whether the tool call succeeded.
        """
        if not self.tracer or not parent_span:
            return

        try:
            from harness.tracer import SpanKind, SpanStatus

            # Use start_span with explicit parent to create child span
            tool_span = self.tracer.start_span(
                name=f"tool.{tool_name}",
                kind=SpanKind.TOOL_CALL,
                parent=parent_span,
            )
            tool_span.set_attribute("tool.name", tool_name)
            if tool_input:
                tool_span.set_attribute("tool.input", tool_input[:500])
            tool_span.finish(status=SpanStatus.OK if success else SpanStatus.ERROR)
        except Exception as e:
            logger.debug(
                "Failed to trace tool call",
                tool_name=tool_name,
                error=str(e),
            )

    def _format_budget_warning(
        self, level: str, percent: float, remaining: int
    ) -> str:
        """Format a budget warning message based on severity level."""
        messages = {
            "warning": (
                f"[CONTEXT_BUDGET: {percent:.0f}% used, ~{remaining:,} tokens remaining. "
                "Consider wrapping up current work.]"
            ),
            "urgent": (
                f"[CONTEXT_BUDGET: {percent:.0f}% used. Checkpoint saved. "
                "Update context files and prepare to end session.]"
            ),
            "critical": (
                f"[CONTEXT_BUDGET: {percent:.0f}% used. Stop new work. "
                "Save state and signal session end.]"
            ),
        }
        return messages.get(level, messages["warning"])

    async def _save_budget_checkpoint(self) -> None:
        """Save checkpoint triggered by budget threshold."""
        logger.info(
            "Saving budget-triggered checkpoint",
            tokens_used=self.tokens_used,
            token_budget=self.token_budget,
            agent=self.agent_name,
        )
        try:
            await self.checkpoint_manager.save_checkpoint(
                await self._get_state_async()
            )
        except Exception as e:
            logger.error(
                "Failed to save budget checkpoint",
                error=str(e),
                agent=self.agent_name,
            )

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent session and cleanup SDK client."""
        logger.info("Shutting down agent session", agent=self.agent_name)

        # Cancel all background tasks first
        if self._background_tasks:
            logger.debug(
                "Cancelling background tasks",
                agent=self.agent_name,
                task_count=len(self._background_tasks),
            )
            for task in self._background_tasks:
                task.cancel()

            # Wait for cancellation with timeout
            try:
                await asyncio.wait(
                    self._background_tasks,
                    timeout=self.config.shutdown_timeout,
                )
            except Exception as e:
                logger.warning(
                    "Error waiting for background tasks to cancel",
                    error=str(e),
                )
            finally:
                self._background_tasks.clear()

        # Stop health server
        if self.health_server is not None:
            await self.health_server.stop()
            self.health_server = None

        # Disconnect SDK client
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("SDK client disconnected", agent=self.agent_name)
            except Exception as e:
                logger.warning("Error disconnecting SDK client", error=str(e))
            finally:
                self.client = None
                self.session_id = None

        # Save final checkpoint
        self.checkpoint_manager.save_checkpoint(self.state)

        # Disconnect from Redis if connected
        if self.redis_available and self.message_broker is not None:
            self.message_broker.disconnect()
            self.redis_available = False

        # Update metrics
        self.metrics.set_active_sessions(self.agent_name, 0)
        self.metrics.stop()

        logger.info("Agent session shutdown complete", agent=self.agent_name)

    async def resume_from_session_id(self, session_id: str) -> None:
        """
        Resume conversation from a previous session ID.

        This allows continuing a conversation from a checkpoint or previous session.
        The SDK automatically maintains conversation history when resuming.

        Args:
            session_id: SDK session ID to resume from

        Raises:
            RuntimeError: If SDK client not connected (call start() first)

        Note:
            Call this BEFORE the first execute() after start() to resume
            a previous conversation. The SDK handles the actual resume logic.
        """
        if not self.client:
            raise RuntimeError("SDK client not connected. Call start() first.")

        logger.info("Resuming from session", session_id=session_id, agent=self.agent_name)
        self.session_id = session_id
        self.state["session_id"] = session_id

        # Note: SDK handles resume automatically when we have session_id
        # The next query() will continue from this session's conversation history


async def run() -> None:
    """Run the agent as a standalone service with graceful shutdown."""
    config = get_config()

    logger.info(
        "Starting Claude Agent Harness",
        model=config.claude_model,
        permission_mode=config.interactive_permission_mode,
    )

    # Track shutdown state
    shutdown_event = asyncio.Event()

    async def graceful_shutdown(signame: str) -> None:
        """Handle SIGTERM/SIGINT gracefully."""
        logger.info(f"Received {signame}, starting graceful shutdown...")

        # Critical: Flush all output streams
        sys.stdout.flush()
        sys.stderr.flush()

        # Cancel all pending tasks
        current_task = asyncio.current_task()
        for task in asyncio.all_tasks():
            if task is not current_task and not task.done():
                task.cancel()

        # Signal shutdown to components monitoring the event
        shutdown_event.set()

        # Brief sleep to allow task cancellation
        await asyncio.sleep(0.1)

    # Register signal handlers using event loop
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                graceful_shutdown(signal.Signals(s).name)
            ),
        )

    # Create and start agent session
    session = AgentSession(agent_name="main", config=config)
    await session.start()

    try:
        # Keep running until shutdown event is set
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except asyncio.CancelledError:
        logger.info("Agent task cancelled during shutdown")
    finally:
        logger.info("Agent shutdown sequence initiated")

        # Ensure final streams are flushed
        await asyncio.sleep(0.1)
        sys.stdout.flush()
        sys.stderr.flush()

        # Shutdown session
        await session.shutdown()

        logger.info("Agent shutdown complete")


if __name__ == "__main__":
    asyncio.run(run())
