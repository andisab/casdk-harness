"""Checkpoint and recovery system for long-running agent sessions."""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CheckpointManager:
    """Manages checkpoint creation, recovery, and cleanup for agent sessions."""

    def __init__(
        self,
        checkpoint_dir: Path,
        interval: int = 3600,
        max_checkpoints: int = 5,
    ) -> None:
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
            interval: Checkpoint interval in seconds (default: 1 hour)
            max_checkpoints: Maximum number of checkpoints to keep (default: 5)
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.interval = interval
        self.max_checkpoints = max_checkpoints
        self.last_checkpoint: datetime | None = None

        # Ensure directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async def auto_checkpoint(
        self,
        get_state_fn: Callable[[], Any],
    ) -> None:
        """
        Automatically create checkpoints at regular intervals.

        Args:
            get_state_fn: Function that returns current agent state
        """
        logger.info(
            "Starting auto-checkpoint",
            interval=self.interval,
            directory=str(self.checkpoint_dir),
        )

        while True:
            try:
                await asyncio.sleep(self.interval)
                state = await get_state_fn()
                checkpoint_file = self.save_checkpoint(state)
                logger.info(
                    "Auto-checkpoint saved",
                    file=str(checkpoint_file),
                    size=checkpoint_file.stat().st_size,
                )
            except Exception as e:
                logger.error("Auto-checkpoint failed", error=str(e), exc_info=True)

    def save_checkpoint(self, state: dict[str, Any]) -> Path:
        """
        Save checkpoint with current state and metadata.

        Args:
            state: Current agent state to checkpoint

        Returns:
            Path to created checkpoint file
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.isoformat().replace(":", "-")

        checkpoint = {
            "timestamp": timestamp.isoformat(),
            "version": "0.1.0",
            "state": state,
            "workspace_snapshot": self._snapshot_workspace(),
            "memory_snapshot": self._snapshot_memory(),
            "metadata": {
                "checkpoint_interval": self.interval,
                "created_at": timestamp.isoformat(),
            },
        }

        checkpoint_file = self.checkpoint_dir / f"checkpoint_{timestamp_str}.json"

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, default=str)

        self.last_checkpoint = timestamp
        self._cleanup_old_checkpoints()

        logger.info(
            "Checkpoint saved",
            file=str(checkpoint_file),
            size=checkpoint_file.stat().st_size,
        )

        return checkpoint_file

    def load_latest_checkpoint(self) -> dict[str, Any] | None:
        """
        Load the most recent checkpoint.

        Returns:
            Checkpoint data or None if no checkpoints exist
        """
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not checkpoints:
            logger.info("No checkpoints found")
            return None

        latest = checkpoints[0]
        logger.info("Loading latest checkpoint", file=str(latest))

        with open(latest, encoding="utf-8") as f:
            checkpoint = json.load(f)

        return checkpoint

    def recover_from_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """
        Recover agent state from checkpoint.

        Args:
            checkpoint: Checkpoint data to recover from

        Returns:
            Recovered agent state
        """
        logger.info(
            "Recovering from checkpoint",
            timestamp=checkpoint.get("timestamp"),
            version=checkpoint.get("version"),
        )

        # Restore workspace snapshot if available
        if "workspace_snapshot" in checkpoint:
            self._restore_workspace(checkpoint["workspace_snapshot"])

        # Restore memory snapshot if available
        if "memory_snapshot" in checkpoint:
            self._restore_memory(checkpoint["memory_snapshot"])

        return checkpoint.get("state", {})

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """
        List all available checkpoints.

        Returns:
            List of checkpoint metadata
        """
        checkpoints = []

        for checkpoint_file in sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(checkpoint_file, encoding="utf-8") as f:
                    checkpoint = json.load(f)

                checkpoints.append(
                    {
                        "file": str(checkpoint_file),
                        "timestamp": checkpoint.get("timestamp"),
                        "size": checkpoint_file.stat().st_size,
                        "version": checkpoint.get("version"),
                    }
                )
            except Exception as e:
                logger.warning(
                    "Failed to read checkpoint",
                    file=str(checkpoint_file),
                    error=str(e),
                )

        return checkpoints

    def delete_checkpoint(self, checkpoint_file: Path) -> None:
        """
        Delete a specific checkpoint.

        Args:
            checkpoint_file: Path to checkpoint file to delete
        """
        checkpoint_file = Path(checkpoint_file)
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.info("Checkpoint deleted", file=str(checkpoint_file))

    def _snapshot_workspace(self) -> dict[str, Any]:
        """
        Create snapshot of workspace state.

        Returns:
            Workspace snapshot metadata
        """
        # In a real implementation, this would capture file hashes,
        # modification times, etc. For now, just basic stats.
        return {
            "timestamp": datetime.now().isoformat(),
            "file_count": 0,  # Placeholder
        }

    def _snapshot_memory(self) -> dict[str, Any]:
        """
        Create snapshot of memory state.

        Returns:
            Memory snapshot metadata
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "context_size": 0,  # Placeholder
        }

    def _restore_workspace(self, snapshot: dict[str, Any]) -> None:
        """
        Restore workspace from snapshot.

        Args:
            snapshot: Workspace snapshot to restore
        """
        logger.info("Restoring workspace", timestamp=snapshot.get("timestamp"))
        # Implementation would restore files here

    def _restore_memory(self, snapshot: dict[str, Any]) -> None:
        """
        Restore memory from snapshot.

        Args:
            snapshot: Memory snapshot to restore
        """
        logger.info("Restoring memory", timestamp=snapshot.get("timestamp"))
        # Implementation would restore memory here

    def _cleanup_old_checkpoints(self) -> None:
        """Remove old checkpoints, keeping only the most recent max_checkpoints."""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if len(checkpoints) > self.max_checkpoints:
            for old_checkpoint in checkpoints[self.max_checkpoints :]:
                old_checkpoint.unlink()
                logger.debug(
                    "Old checkpoint removed",
                    file=str(old_checkpoint),
                )
