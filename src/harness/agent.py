"""Core agent session management and execution."""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Any, AsyncGenerator

import structlog
from claude_agent_sdk import (
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ProcessError,
    ResultMessage,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from harness.checkpoint import CheckpointManager
from harness.config import HarnessConfig, get_config
from harness.messaging import RedisMessageBroker
from harness.monitoring import MetricsCollector
from mcp_servers.docker.server import docker_server
from mcp_servers.git.server import git_server

logger = structlog.get_logger(__name__)


class AgentSession:
    """Manages a Claude agent session with checkpointing and monitoring."""

    def __init__(
        self,
        agent_name: str = "main",
        config: HarnessConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        """
        Initialize agent session.

        Args:
            agent_name: Name of the agent
            config: Configuration object (uses global config if None)
            checkpoint_manager: Checkpoint manager instance
            metrics_collector: Metrics collector instance
        """
        self.agent_name = agent_name
        self.config = config or get_config()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager(
            checkpoint_dir=self.config.checkpoint_dir,
            interval=self.config.claude_checkpoint_interval,
        )
        self.metrics = metrics_collector or MetricsCollector(
            workspace_dir=self.config.workspace_dir,
            checkpoint_dir=self.config.checkpoint_dir,
        )

        # Initialize Redis message broker for cross-agent communication
        self.message_broker = RedisMessageBroker()
        try:
            self.message_broker.connect()
            logger.info("Redis message broker connected", agent=agent_name)
        except Exception as e:
            logger.warning(
                "Failed to connect to Redis message broker - inter-agent messaging disabled",
                agent=agent_name,
                error=str(e),
            )

        self.session_id = f"{agent_name}_{datetime.now().isoformat()}"
        self.state: dict[str, Any] = {
            "agent_name": agent_name,
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "completed_tasks": [],
            "current_task": None,
        }

        # Register MCP servers (both in-process SDK and external servers)
        # NOTE: ALL MCP servers disabled during SDK debugging (2025-11-19)
        # Previous timeout occurred during memory MCP initialization
        self.mcp_servers = {
            # Disabled for debugging - will re-enable once SDK issue resolved
            # # In-process SDK servers (custom Python implementations)
            # "git": git_server,
            # "docker": docker_server,
            # # External MCP servers (subprocess communication via npx)
            # "memory": {
            #     "type": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-memory"],
            # },
            # "context7": {
            #     "type": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@context7/mcp-server"],
            # },
            # "joplin": {
            #     "type": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@joplin/mcp-server"],
            # },
            # "github": {
            #     "type": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-github"],
            # },
            # "playwright": {
            #     "type": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@modelcontextprotocol/server-playwright"],
            # },
        }

        logger.info(
            "Agent session initialized",
            agent=agent_name,
            session_id=self.session_id,
            mcp_servers=len(self.mcp_servers),
        )

    def _build_sdk_options(self) -> ClaudeAgentOptions:
        """Build SDK options with MCP servers and configuration."""
        import os

        # Prepare environment variables for Claude CLI subprocess
        # CRITICAL: Pass PYTHONUNBUFFERED=1 to ensure stdout is unbuffered
        cli_env = os.environ.copy()
        cli_env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered mode

        return ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch"],
            permission_mode=self.config.claude_permission_mode,
            max_turns=self.config.claude_max_turns,
            cwd=str(self.config.workspace_dir),
            model=self.config.claude_model,
            mcp_servers=self.mcp_servers,  # Register custom MCP servers
            env=cli_env,  # Pass environment to CLI subprocess
            stderr=lambda msg: logger.debug(f"[CLI stderr] {msg}"),  # Capture stderr
            # Note: Removed invalid "debug-to-stderr" - use "debug" or nothing
        )

    async def start(self) -> None:
        """Start the agent session and background tasks."""
        logger.info("Starting agent session", agent=self.agent_name)

        # Start metrics collection
        self.metrics.start()
        self.metrics.set_active_sessions(self.agent_name, 1)

        # Start auto-checkpoint task
        asyncio.create_task(
            self.checkpoint_manager.auto_checkpoint(
                get_state_fn=self._get_state_async
            )
        )

        # Start metrics collection task
        asyncio.create_task(self.metrics.collect_system_metrics())

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
            )

            # Execute with retry
            async for message in self._execute_with_retry(prompt, **kwargs):
                yield message

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
        Execute agent task with automatic retry on failure.

        Uses ClaudeSDKClient pattern with context manager and two-step process:
        1. Create SDK client with context manager
        2. Send query via client.query()
        3. Receive messages via client.receive_response()

        Args:
            prompt: Task prompt
            **kwargs: Additional arguments

        Yields:
            Agent response messages
        """
        logger.debug("Executing agent prompt with Claude SDK", prompt_length=len(prompt))

        # Build SDK options
        options = self._build_sdk_options()

        try:
            # Use context manager for SDK client lifecycle
            async with ClaudeSDKClient(options=options) as client:
                logger.debug("SDK client initialized for query", agent=self.agent_name)

                # Step 1: Send query to Claude SDK
                await client.query(prompt)
                logger.debug("Query sent to SDK client", agent=self.agent_name)

                # Step 2: Receive response messages
                async for message in client.receive_response():
                    logger.debug(
                        "Message received from SDK",
                        message_type=type(message).__name__,
                        agent=self.agent_name,
                    )

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

                    logger.debug("Yielding message to caller", message_type=type(message).__name__)
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
                "Failed to connect to Claude CLI",
                error=str(e),
                exc_info=True,
            )
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
        if not self.message_broker.connected:
            logger.warning(
                "Cannot publish task result - Redis not connected",
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
        if not self.message_broker.connected:
            logger.warning(
                "Cannot wait for dependency - Redis not connected",
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
        Get current agent state (async version for checkpoint manager).

        Returns:
            Current state dictionary
        """
        return self.state.copy()

    def get_state(self) -> dict[str, Any]:
        """
        Get current agent state.

        Returns:
            Current state dictionary
        """
        return self.state.copy()

    async def recover_from_checkpoint(self) -> bool:
        """
        Attempt to recover from latest checkpoint.

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
            return True

        except Exception as e:
            logger.error(
                "Failed to recover from checkpoint",
                error=str(e),
                exc_info=True,
            )
            return False

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent session."""
        logger.info("Shutting down agent session", agent=self.agent_name)

        # Save final checkpoint
        self.checkpoint_manager.save_checkpoint(self.state)

        # Disconnect from Redis
        if self.message_broker.connected:
            self.message_broker.disconnect()

        # Update metrics
        self.metrics.set_active_sessions(self.agent_name, 0)
        self.metrics.stop()

        logger.info("Agent session shutdown complete", agent=self.agent_name)


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
