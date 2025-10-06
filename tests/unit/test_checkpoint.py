"""Unit tests for checkpoint manager."""

import json
from pathlib import Path

import pytest

from harness.checkpoint import CheckpointManager


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    """Create temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def checkpoint_manager(checkpoint_dir: Path) -> CheckpointManager:
    """Create checkpoint manager instance."""
    return CheckpointManager(
        checkpoint_dir=checkpoint_dir,
        interval=3600,
        max_checkpoints=3,
    )


def test_save_checkpoint(checkpoint_manager: CheckpointManager) -> None:
    """Test saving a checkpoint."""
    # Arrange
    state = {
        "session_id": "test-session",
        "completed_tasks": ["task1", "task2"],
        "current_task": "task3",
    }

    # Act
    checkpoint_file = checkpoint_manager.save_checkpoint(state)

    # Assert
    assert checkpoint_file.exists()
    assert checkpoint_file.suffix == ".json"

    # Verify contents
    with open(checkpoint_file, encoding="utf-8") as f:
        checkpoint = json.load(f)

    assert checkpoint["state"] == state
    assert "timestamp" in checkpoint
    assert "version" in checkpoint


def test_load_latest_checkpoint(checkpoint_manager: CheckpointManager) -> None:
    """Test loading the latest checkpoint."""
    # Arrange
    state1 = {"task": "task1"}
    state2 = {"task": "task2"}

    checkpoint_manager.save_checkpoint(state1)
    checkpoint_manager.save_checkpoint(state2)

    # Act
    latest = checkpoint_manager.load_latest_checkpoint()

    # Assert
    assert latest is not None
    assert latest["state"] == state2


def test_load_no_checkpoints(checkpoint_manager: CheckpointManager) -> None:
    """Test loading when no checkpoints exist."""
    # Act
    result = checkpoint_manager.load_latest_checkpoint()

    # Assert
    assert result is None


def test_cleanup_old_checkpoints(checkpoint_manager: CheckpointManager) -> None:
    """Test cleanup of old checkpoints."""
    # Arrange - create more than max_checkpoints
    for i in range(5):
        checkpoint_manager.save_checkpoint({"task": f"task{i}"})

    # Act
    checkpoints = list(checkpoint_manager.checkpoint_dir.glob("checkpoint_*.json"))

    # Assert - should only keep max_checkpoints (3)
    assert len(checkpoints) == 3


def test_list_checkpoints(checkpoint_manager: CheckpointManager) -> None:
    """Test listing all checkpoints."""
    # Arrange
    checkpoint_manager.save_checkpoint({"task": "task1"})
    checkpoint_manager.save_checkpoint({"task": "task2"})

    # Act
    checkpoints = checkpoint_manager.list_checkpoints()

    # Assert
    assert len(checkpoints) == 2
    assert all("timestamp" in c for c in checkpoints)
    assert all("size" in c for c in checkpoints)
