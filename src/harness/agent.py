"""Core agent session management and execution."""

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from harness.checkpoint import CheckpointManager
from harness.config import HarnessConfig, get_config
from harness.monitoring import MetricsCollector

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

        self.session_id = f"{agent_name}_{datetime.now().isoformat()}"
        self.state: dict[str, Any] = {
            "agent_name": agent_name,
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "completed_tasks": [],
            "current_task": None,
        }

        logger.info(
            "Agent session initialized",
            agent=agent_name,
            session_id=self.session_id,
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

        Args:
            prompt: Task prompt
            **kwargs: Additional arguments

        Yields:
            Agent response messages
        """
        # Placeholder for actual Claude Agent SDK integration
        # This will be implemented with the actual SDK
        logger.debug("Executing agent prompt", prompt_length=len(prompt))

        # Simulate response for now
        yield {
            "type": "message",
            "content": f"[Simulated response to: {prompt[:50]}...]",
            "timestamp": datetime.now().isoformat(),
        }

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

        # Update metrics
        self.metrics.set_active_sessions(self.agent_name, 0)
        self.metrics.stop()

        logger.info("Agent session shutdown complete", agent=self.agent_name)


async def run() -> None:
    """Run the agent as a standalone service."""
    config = get_config()

    logger.info(
        "Starting Claude Agent Harness",
        model=config.claude_model,
        permission_mode=config.claude_permission_mode,
    )

    # Create and start agent session
    session = AgentSession(agent_name="main", config=config)
    await session.start()

    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await session.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
