"""Core agent session management and execution."""

import asyncio
import signal
import sys
from collections.abc import AsyncGenerator
from datetime import datetime
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
from harness.config import HarnessConfig, get_config
from harness.health import HealthServer
from harness.mcp_loader import MCPConfigLoader
from harness.messaging import CircuitBreakerOpenError, RedisMessageBroker
from harness.monitoring import MetricsCollector

# In-process MCP servers (Method A)
from mcp_servers.context7 import context7_server
from mcp_servers.docker import docker_server
from mcp_servers.memory import memory_server

logger = structlog.get_logger(__name__)


class AgentTimeoutError(Exception):
    """Raised when agent execution exceeds the configured timeout."""

    pass


class AgentSession:
    """Manages a Claude agent session with checkpointing and monitoring."""

    def __init__(
        self,
        agent_name: str = "main",
        config: HarnessConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        metrics_collector: MetricsCollector | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """
        Initialize agent session.

        Args:
            agent_name: Name of the agent
            config: Configuration object (uses global config if None)
            checkpoint_manager: Checkpoint manager instance
            metrics_collector: Metrics collector instance
            model: Override model (uses config.claude_model if None)
            system_prompt: Override system prompt (loads from file if None)
        """
        self.agent_name = agent_name
        self.config = config or get_config()
        self._model_override = model
        self._system_prompt_override = system_prompt

        # Plugin configuration (Phase 1B)
        from pathlib import Path
        plugin_base = Path(__file__).parent.parent.parent / ".claude" / "plugins"
        self.plugins = [
            {"type": "local", "path": str(plugin_base / "arch")},
            {"type": "local", "path": str(plugin_base / "context-engineering")},
            {"type": "local", "path": str(plugin_base / "research-team")},
        ]
        self.plugin_base = plugin_base  # Store for manual loading workaround

        self.checkpoint_manager = checkpoint_manager or CheckpointManager(
            checkpoint_dir=self.config.checkpoint_dir,
            interval=self.config.claude_checkpoint_interval,
            max_checkpoints=self.config.checkpoint_keep_count,
        )
        self.metrics = metrics_collector or MetricsCollector(
            workspace_dir=self.config.workspace_dir,
            checkpoint_dir=self.config.checkpoint_dir,
        )

        # Initialize Redis message broker for cross-agent communication
        # Set to None on connection failure to make disabled state explicit
        # Uses circuit breaker pattern for resilience (see messaging.py)
        self.message_broker: RedisMessageBroker | None = None
        self.redis_available: bool = False
        try:
            broker = RedisMessageBroker(config=self.config)
            broker.connect()
            self.message_broker = broker
            self.redis_available = True
            logger.info("Redis message broker connected", agent=agent_name)
        except CircuitBreakerOpenError as e:
            # Circuit breaker is open - Redis was failing, skip connection
            logger.warning(
                "Redis circuit breaker is open - inter-agent messaging disabled. "
                "Will retry automatically after recovery timeout.",
                agent=agent_name,
                error=str(e),
            )
        except Exception as e:
            # Redis unavailable - inter-agent messaging disabled
            # This is expected in single-agent mode or when Redis is not running
            logger.warning(
                "Redis not available - inter-agent messaging disabled. "
                "This is normal for single-agent deployments.",
                agent=agent_name,
                error=str(e),
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

        # Load MCP servers (Phase 1C - Method A + Method B)
        # 1. Load in-process servers (Method A) - docker, context7, memory
        self.inprocess_servers = self._load_inprocess_servers()
        # 2. Load subprocess servers (Method B) - playwright, joplin, excel
        subprocess_servers = self._load_mcp_servers(tiers=[1, 2])
        # 3. Merge: in-process takes precedence over subprocess
        self.mcp_servers = {**subprocess_servers, **self.inprocess_servers}

        # TEMPORARY: Manually discover plugin skills (SDK workaround)
        self.plugin_skills = self._load_plugin_skills_manually()

        logger.info(
            "Agent session initialized",
            agent=agent_name,
            session_id=self.session_id,
            mcp_servers=len(self.mcp_servers),
            plugin_skills=len(self.plugin_skills),
        )

    async def __aenter__(self) -> "AgentSession":
        """Async context manager entry - starts the session."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - shuts down the session."""
        await self.shutdown()

    def _load_plugin_skills_manually(self) -> dict[str, dict[str, str]]:
        """Manually discover plugin skills as workaround for SDK bug.

        TEMPORARY WORKAROUND (2025-11-25):
        Python SDK v0.1.9 accepts plugins parameter but Claude CLI subprocess
        not loading them. See GitHub issues:
        - https://github.com/anthropics/claude-code/issues/11620
        - https://github.com/anthropics/claude-agent-sdk-python/issues/213

        This function manually discovers plugin skills until SDK bug is fixed.

        Returns:
            Dict mapping skill names to metadata (plugin, path)
        """
        import json

        plugin_skills = {}

        # Scan each plugin directory for skills
        for plugin_path in self.plugin_base.glob("*/"):
            if not plugin_path.is_dir():
                continue

            plugin_name = plugin_path.name
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

            # Skip if no manifest
            if not manifest_path.exists():
                logger.warning(
                    "Plugin missing manifest, skipping",
                    plugin=plugin_name,
                    expected_path=str(manifest_path)
                )
                continue

            # Load manifest to check for skills paths
            try:
                manifest = json.loads(manifest_path.read_text())
                skill_paths = manifest.get("skills", [])

                if not skill_paths:
                    continue

                # Discover skills in each specified path
                for skill_rel_path in skill_paths:
                    skills_dir = plugin_path / skill_rel_path.lstrip("./")

                    if not skills_dir.exists():
                        continue

                    # Find all SKILL.md files
                    for skill_path in skills_dir.glob("*/SKILL.md"):
                        skill_name = skill_path.parent.name
                        plugin_skills[skill_name] = {
                            "plugin": plugin_name,
                            "path": str(skill_path),
                            "source": "plugin-manual-discovery"
                        }

            except Exception as e:
                logger.warning(
                    "Failed to load plugin manifest",
                    plugin=plugin_name,
                    error=str(e)
                )

        if plugin_skills:
            logger.info(
                "Manually discovered plugin skills (SDK workaround)",
                count=len(plugin_skills),
                skills=list(plugin_skills.keys())
            )

        return plugin_skills

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
        logger.info(
            "Loaded in-process MCP server",
            server="docker",
            method="A (in-process)",
        )

        # Context7 - always available (no API key required, works with rate limits)
        servers["context7"] = context7_server
        logger.info(
            "Loaded in-process MCP server",
            server="context7",
            method="A (in-process)",
        )

        # Memory - always available (knowledge graph for persistent memory)
        servers["memory"] = memory_server
        logger.info(
            "Loaded in-process MCP server",
            server="memory",
            method="A (in-process)",
        )

        logger.info(
            "In-process MCP servers loaded",
            count=len(servers),
            servers=list(servers.keys()),
        )

        return servers

    def _load_mcp_servers(self, tiers: list[int] = [1]) -> dict[str, Any]:
        """Load subprocess MCP servers (Method B) for specified tiers.

        Phase 1C Architecture: Subprocess servers for external dependencies.
        - Tier 1: Empty (all fast servers now in-process)
        - Tier 2: External servers (memory, playwright, joplin) - 120s timeout

        Note: git, docker, context7, and github are now loaded as in-process
        servers (Method A). See _load_inprocess_servers() for those.

        All servers here are subprocess servers using stdio protocol.

        Args:
            tiers: List of tier numbers to load (default: [1])

        Returns:
            Dict mapping server names to stdio server configurations
        """
        from pathlib import Path

        # Get plugin paths for merging plugin .mcp.json files
        plugin_paths = [Path(p["path"]) for p in self.plugins]

        loader = MCPConfigLoader()
        base_mcp_path = Path(__file__).parent.parent.parent / ".claude" / ".mcp.json"

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

                # Map all servers uniformly as subprocess servers (stdio protocol)
                for server_name, server_config in tier_config["mcpServers"].items():
                    # Format for SDK: {"type": "stdio", "command": "...", "args": [...]}
                    all_mcp_servers[server_name] = {
                        "type": "stdio",
                        "command": server_config["command"],
                        "args": server_config["args"],
                        **({"env": server_config["env"]} if server_config.get("env") else {})
                    }
                    logger.info(
                        "Loaded MCP server",
                        server=server_name,
                        tier=tier,
                        command=server_config["command"],
                        transport="stdio"
                    )

                loaded_tiers.append(tier)
                logger.info(
                    "MCP tier loaded successfully",
                    tier=tier,
                    server_count=len(tier_config["mcpServers"]),
                    servers=list(tier_config["mcpServers"].keys())
                )

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
            logger.info(
                "MCP servers loaded successfully",
                tiers=loaded_tiers,
                total_servers=len(all_mcp_servers),
                servers=list(all_mcp_servers.keys())
            )
        else:
            logger.warning("No MCP servers loaded", requested_tiers=tiers)

        return all_mcp_servers

    def _load_system_prompt(self) -> str:
        """Load system prompt from .claude/CLAUDE.md file.

        Returns:
            System prompt content with plugin skills appended if any.
        """
        from pathlib import Path

        # Load base system prompt from .claude/CLAUDE.md
        prompt_file = Path(__file__).parent.parent.parent / ".claude" / "CLAUDE.md"

        if prompt_file.exists():
            system_prompt = prompt_file.read_text()
            logger.debug("Loaded system prompt from file", path=str(prompt_file))
        else:
            logger.warning(
                "System prompt file not found, using minimal prompt",
                expected_path=str(prompt_file)
            )
            system_prompt = "Work in /workspace directory. Use absolute paths."

        # Append plugin skills info if any
        if self.plugin_skills:
            skills_list = "\n".join([
                f"  - {name} (from {info['plugin']} plugin)"
                for name, info in self.plugin_skills.items()
            ])
            system_prompt += f"""

---

## Available Plugin Skills

Plugin skills discovered (via manual SDK workaround):
{skills_list}

Use them via: Skill tool with skill name (e.g., "joplin-research")
"""

        return system_prompt

    def _build_sdk_options(self) -> ClaudeAgentOptions:
        """Build SDK options with MCP servers and configuration."""
        import os

        # Prepare environment variables for Claude CLI subprocess
        # CRITICAL: Pass PYTHONUNBUFFERED=1 to ensure stdout is unbuffered
        cli_env = os.environ.copy()
        cli_env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered mode

        # Use override or load from file
        system_prompt = self._system_prompt_override or self._load_system_prompt()
        model = self._model_override or self.config.claude_model

        return ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch", "Skill"],
            permission_mode=self.config.claude_permission_mode,
            max_turns=self.config.claude_max_turns,
            cwd="/app",  # SDK needs /app to find .claude/skills/
            model=model,
            mcp_servers=self.mcp_servers,  # Register custom MCP servers
            setting_sources=["user", "project"],  # Enable skills from .claude/skills/
            plugins=self.plugins,  # Phase 1B: Enable plugin loading
            system_prompt=system_prompt,
            env=cli_env,  # Pass environment to CLI subprocess
            stderr=lambda msg: logger.debug(f"[CLI stderr] {msg}"),  # Capture stderr
            # Note: Removed invalid "debug-to-stderr" - use "debug" or nothing
        )

    async def start(self) -> None:
        """Start the agent session and background tasks."""
        logger.info("Starting agent session", agent=self.agent_name)

        # Create and connect persistent SDK client
        options = self._build_sdk_options()
        self.client = ClaudeSDKClient(options=options)

        try:
            await self.client.connect()
            logger.info(
                "SDK client connected",
                agent=self.agent_name,
            )

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

        logger.debug(
            "Background tasks started",
            agent=self.agent_name,
            task_count=len(self._background_tasks),
        )

        # Start health check server
        self.health_server = HealthServer(session=self)
        await self.health_server.start()

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
        self.state["current_task"] = prompt

        try:
            logger.info(
                "Executing agent task",
                agent=self.agent_name,
                prompt_length=len(prompt),
                timeout=self.config.claude_api_timeout,
            )

            # Execute with retry and timeout
            try:
                async with asyncio.timeout(self.config.claude_api_timeout):
                    async for message in self._execute_with_retry(prompt, **kwargs):
                        yield message
            except asyncio.TimeoutError:
                self.metrics.record_request(self.agent_name, "timeout")
                logger.error(
                    "Request timeout exceeded",
                    agent=self.agent_name,
                    timeout=self.config.claude_api_timeout,
                )
                raise AgentTimeoutError(
                    f"Agent execution timed out after {self.config.claude_api_timeout}s"
                )

            # Record successful execution
            duration = (datetime.now() - start_time).total_seconds()
            self.metrics.record_request(self.agent_name, "success")
            self.metrics.record_duration(self.agent_name, duration)

            self.state["completed_tasks"].append(
                {
                    "prompt": prompt[:100],  # Store first 100 chars
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
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def _execute_with_retry(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute using persistent SDK client (maintains conversation history).

        The client is created once in start() and reused for all queries,
        which allows the SDK to maintain conversation context across messages.

        Args:
            prompt: Task prompt
            **kwargs: Additional arguments (unused, kept for compatibility)

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

                # Track token usage from ResultMessage
                if isinstance(message, ResultMessage) and hasattr(message, "usage"):
                    usage = message.usage
                    self.metrics.record_tokens(
                        agent=self.agent_name,
                        model=self.config.claude_model,
                        usage=usage,
                    )
                    logger.debug(
                        "Token usage recorded",
                        agent=self.agent_name,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cached_tokens=usage.get("cache_read_input_tokens", 0),
                    )

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
            logger.info("No checkpoint found for recovery")
            return False

        try:
            recovered_state = self.checkpoint_manager.recover_from_checkpoint(checkpoint)
            self.state.update(recovered_state)

            logger.info(
                "Successfully recovered from checkpoint",
                checkpoint_time=checkpoint.get("timestamp"),
            )

            # Resume SDK session if session_id exists in checkpoint
            if "sdk_session_id" in recovered_state and recovered_state["sdk_session_id"]:
                try:
                    await self.resume_from_session_id(recovered_state["sdk_session_id"])
                    logger.info(
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
        permission_mode=config.claude_permission_mode,
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
