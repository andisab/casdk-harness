"""Checkpoint and recovery system for long-running agent sessions."""

import asyncio
import hashlib
import json
import subprocess
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
        workspace_dir: Path | None = None,
        memory_dir: Path | None = None,
    ) -> None:
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints
            interval: Checkpoint interval in seconds (default: 1 hour)
            max_checkpoints: Maximum number of checkpoints to keep (default: 5)
            workspace_dir: Path to workspace directory for snapshots
            memory_dir: Path to memory directory (knowledge graph)
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.interval = interval
        self.max_checkpoints = max_checkpoints
        self.last_checkpoint: datetime | None = None
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path("/workspace")
        self.memory_dir = Path(memory_dir) if memory_dir else Path("/memory/graph")

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
        logger.debug(
            "Auto-checkpoint task started",
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
            logger.debug("No checkpoints found")
            return None

        latest = checkpoints[0]
        logger.debug("Loading checkpoint", file=str(latest))

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
        logger.debug(
            "Processing checkpoint data",
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
        Create snapshot of workspace state using git if available.

        If workspace is a git repository:
          - Captures HEAD commit hash
          - Captures git status (modified/untracked files)
        Otherwise:
          - Captures file list with SHA256 hashes

        Returns:
            Workspace snapshot metadata
        """
        snapshot: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "workspace_path": str(self.workspace_dir),
        }

        if not self.workspace_dir.exists():
            snapshot["error"] = "Workspace directory does not exist"
            snapshot["file_count"] = 0
            return snapshot

        git_dir = self.workspace_dir / ".git"
        if git_dir.exists():
            # Git-based snapshot
            snapshot["type"] = "git"
            try:
                # Get current HEAD commit
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    snapshot["git_head"] = result.stdout.strip()
                else:
                    snapshot["git_head"] = None
                    snapshot["git_error"] = result.stderr.strip()

                # Get current branch
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    snapshot["git_branch"] = result.stdout.strip()

                # Get status (modified/untracked files)
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    status_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
                    snapshot["git_status"] = {
                        "modified": [line[3:] for line in status_lines if line.startswith(" M") or line.startswith("M ")],
                        "added": [line[3:] for line in status_lines if line.startswith("A ")],
                        "deleted": [line[3:] for line in status_lines if line.startswith(" D") or line.startswith("D ")],
                        "untracked": [line[3:] for line in status_lines if line.startswith("??")],
                    }
                    snapshot["has_uncommitted_changes"] = len(status_lines) > 0
                    snapshot["uncommitted_count"] = len(status_lines)

                # Count tracked files
                result = subprocess.run(
                    ["git", "ls-files"],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    tracked_files = result.stdout.strip().split("\n") if result.stdout.strip() else []
                    snapshot["file_count"] = len(tracked_files)

                logger.debug(
                    "Git workspace snapshot created",
                    head=snapshot.get("git_head", "")[:8],
                    branch=snapshot.get("git_branch"),
                    uncommitted=snapshot.get("uncommitted_count", 0),
                )

            except subprocess.TimeoutExpired:
                snapshot["error"] = "Git command timed out"
                logger.warning("Git command timed out during snapshot")
            except Exception as e:
                snapshot["error"] = str(e)
                logger.error("Error creating git snapshot", error=str(e))
        else:
            # File-based snapshot (no git)
            snapshot["type"] = "files"
            try:
                files_info: list[dict[str, Any]] = []
                total_size = 0

                for file_path in self.workspace_dir.rglob("*"):
                    if file_path.is_file():
                        # Skip large files (>10MB) and common exclusions
                        if file_path.stat().st_size > 10 * 1024 * 1024:
                            continue
                        if any(part.startswith(".") for part in file_path.parts):
                            continue
                        if "__pycache__" in str(file_path) or "node_modules" in str(file_path):
                            continue

                        file_hash = self._hash_file(file_path)
                        rel_path = file_path.relative_to(self.workspace_dir)
                        files_info.append({
                            "path": str(rel_path),
                            "hash": file_hash,
                            "size": file_path.stat().st_size,
                            "mtime": file_path.stat().st_mtime,
                        })
                        total_size += file_path.stat().st_size

                snapshot["file_count"] = len(files_info)
                snapshot["total_size_bytes"] = total_size
                # Only include file details if reasonable count
                if len(files_info) <= 1000:
                    snapshot["files"] = files_info
                else:
                    snapshot["files_truncated"] = True
                    snapshot["files"] = files_info[:100]  # First 100 for reference

                logger.debug(
                    "File-based workspace snapshot created",
                    file_count=len(files_info),
                    total_size=total_size,
                )

            except Exception as e:
                snapshot["error"] = str(e)
                snapshot["file_count"] = 0
                logger.error("Error creating file snapshot", error=str(e))

        return snapshot

    def _hash_file(self, file_path: Path, chunk_size: int = 8192) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to file
            chunk_size: Size of chunks to read

        Returns:
            Hex digest of file hash
        """
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()[:16]  # First 16 chars for brevity
        except Exception:
            return "error"

    def _snapshot_memory(self) -> dict[str, Any]:
        """
        Create snapshot of memory state (knowledge graph).

        Captures:
          - Size of memory graph file(s)
          - Entity count if parseable
          - Last modification time

        Returns:
            Memory snapshot metadata
        """
        snapshot: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "memory_path": str(self.memory_dir),
        }

        if not self.memory_dir.exists():
            snapshot["error"] = "Memory directory does not exist"
            snapshot["context_size"] = 0
            return snapshot

        try:
            # Look for memory graph file
            memory_file = self.memory_dir / "memory.json"
            if memory_file.exists():
                stat = memory_file.stat()
                snapshot["file_size_bytes"] = stat.st_size
                snapshot["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

                # Try to parse and count entities
                try:
                    with open(memory_file, encoding="utf-8") as f:
                        memory_data = json.load(f)

                    if isinstance(memory_data, dict):
                        snapshot["entity_count"] = len(memory_data.get("entities", []))
                        snapshot["relation_count"] = len(memory_data.get("relations", []))
                        snapshot["context_size"] = snapshot["entity_count"] + snapshot["relation_count"]
                    else:
                        snapshot["context_size"] = len(memory_data) if isinstance(memory_data, list) else 1

                except json.JSONDecodeError:
                    snapshot["parse_error"] = "Could not parse memory file"
                    snapshot["context_size"] = 0

            else:
                # Check for any JSON files in memory directory
                json_files = list(self.memory_dir.glob("*.json"))
                if json_files:
                    total_size = sum(f.stat().st_size for f in json_files)
                    snapshot["file_count"] = len(json_files)
                    snapshot["total_size_bytes"] = total_size
                    snapshot["context_size"] = len(json_files)
                else:
                    snapshot["context_size"] = 0

            logger.debug(
                "Memory snapshot created",
                context_size=snapshot.get("context_size", 0),
                file_size=snapshot.get("file_size_bytes", 0),
            )

        except Exception as e:
            snapshot["error"] = str(e)
            snapshot["context_size"] = 0
            logger.error("Error creating memory snapshot", error=str(e))

        return snapshot

    def _restore_workspace(self, snapshot: dict[str, Any]) -> None:
        """
        Validate workspace state against checkpoint snapshot.

        For git-based workspaces, compares current HEAD to checkpoint HEAD
        and warns if there are differences. Does NOT automatically restore
        files (that would be destructive).

        Args:
            snapshot: Workspace snapshot to compare against
        """
        logger.debug(
            "Validating workspace against checkpoint",
            timestamp=snapshot.get("timestamp"),
            snapshot_type=snapshot.get("type"),
        )

        if snapshot.get("type") == "git" and snapshot.get("git_head"):
            # Compare git state
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    current_head = result.stdout.strip()
                    checkpoint_head = snapshot["git_head"]

                    if current_head != checkpoint_head:
                        logger.debug(
                            "Workspace changed since checkpoint",
                            checkpoint_head=checkpoint_head[:8],
                            current_head=current_head[:8],
                            checkpoint_branch=snapshot.get("git_branch"),
                        )
                    else:
                        logger.debug(
                            "Workspace matches checkpoint",
                            head=current_head[:8],
                            branch=snapshot.get("git_branch"),
                        )

                    # Check for uncommitted changes
                    if snapshot.get("has_uncommitted_changes"):
                        logger.warning(
                            "Checkpoint had uncommitted changes",
                            uncommitted_count=snapshot.get("uncommitted_count", 0),
                        )

            except Exception as e:
                logger.error("Error validating git workspace", error=str(e))

        elif snapshot.get("type") == "files":
            # For file-based snapshots, just log the comparison
            checkpoint_count = snapshot.get("file_count", 0)
            logger.debug(
                "File-based checkpoint (manual verification recommended)",
                checkpoint_file_count=checkpoint_count,
            )

    def _restore_memory(self, snapshot: dict[str, Any]) -> None:
        """
        Validate memory state against checkpoint snapshot.

        Compares current memory state to checkpoint and logs differences.
        Does NOT automatically restore memory (that would require the
        memory MCP server).

        Args:
            snapshot: Memory snapshot to compare against
        """
        logger.debug(
            "Validating memory against checkpoint",
            checkpoint_context_size=snapshot.get("context_size", 0),
        )

        # Get current memory state for comparison
        current_snapshot = self._snapshot_memory()

        checkpoint_size = snapshot.get("context_size", 0)
        current_size = current_snapshot.get("context_size", 0)

        if checkpoint_size != current_size:
            logger.debug(
                "Memory state differs from checkpoint",
                checkpoint_context_size=checkpoint_size,
                current_context_size=current_size,
                difference=current_size - checkpoint_size,
            )
        else:
            logger.debug(
                "Memory matches checkpoint",
                context_size=current_size,
            )

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
