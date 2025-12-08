"""Unit tests for checkpoint manager."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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


# =============================================================================
# Workspace Snapshot Tests (Git-based)
# =============================================================================


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """Create temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Create temporary memory directory."""
    memory = tmp_path / "memory"
    memory.mkdir()
    return memory


@pytest.fixture
def manager_with_dirs(
    checkpoint_dir: Path, workspace_dir: Path, memory_dir: Path
) -> CheckpointManager:
    """Create checkpoint manager with workspace and memory directories."""
    return CheckpointManager(
        checkpoint_dir=checkpoint_dir,
        workspace_dir=workspace_dir,
        memory_dir=memory_dir,
        interval=3600,
        max_checkpoints=3,
    )


def test_snapshot_workspace_git_repo(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace snapshot for a git repository."""
    # Create .git directory to simulate git repo
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    # Mock subprocess.run for git commands
    # Git porcelain format: XY PATH where XY is 2 status chars + space + path
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if cmd[1] == "rev-parse" and cmd[2] == "HEAD":
            result.stdout = "abc123def456789"
        elif cmd[1] == "rev-parse" and "--abbrev-ref" in cmd:
            result.stdout = "main"
        elif cmd[1] == "status":
            # Git porcelain: " M " + filename for modified in worktree
            # "?? " + filename for untracked
            result.stdout = " M src/modified.py\n?? untracked.txt"
        elif cmd[1] == "ls-files":
            result.stdout = "file1.py\nfile2.py\nfile3.py"
        return result

    with patch("harness.checkpoint.subprocess.run", side_effect=mock_run):
        snapshot = manager_with_dirs._snapshot_workspace()

    # Assert
    assert snapshot["type"] == "git"
    assert snapshot["git_head"] == "abc123def456789"
    assert snapshot["git_branch"] == "main"
    assert snapshot["has_uncommitted_changes"] is True
    assert snapshot["uncommitted_count"] == 2
    assert snapshot["file_count"] == 3
    # The parsing uses line[3:] which should extract path after "XY "
    assert len(snapshot["git_status"]["modified"]) == 1
    assert "modified.py" in snapshot["git_status"]["modified"][0]
    assert len(snapshot["git_status"]["untracked"]) == 1
    assert "untracked.txt" in snapshot["git_status"]["untracked"][0]


def test_snapshot_workspace_no_git(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace snapshot for non-git directory (file-based)."""
    # Create some files
    (workspace_dir / "file1.py").write_text("print('hello')")
    (workspace_dir / "file2.txt").write_text("content")
    subdir = workspace_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.py").write_text("# nested file")

    snapshot = manager_with_dirs._snapshot_workspace()

    # Assert
    assert snapshot["type"] == "files"
    assert snapshot["file_count"] == 3
    assert snapshot["total_size_bytes"] > 0
    assert "files" in snapshot
    assert len(snapshot["files"]) == 3

    # Verify file info structure
    file_paths = [f["path"] for f in snapshot["files"]]
    assert "file1.py" in file_paths
    assert "file2.txt" in file_paths

    # Verify hash is present
    for file_info in snapshot["files"]:
        assert "hash" in file_info
        assert len(file_info["hash"]) == 16  # SHA256[:16]


def test_snapshot_workspace_nonexistent(tmp_path: Path) -> None:
    """Test workspace snapshot for non-existent directory."""
    manager = CheckpointManager(
        checkpoint_dir=tmp_path / "checkpoints",
        workspace_dir=tmp_path / "nonexistent",
        interval=3600,
    )

    snapshot = manager._snapshot_workspace()

    # Assert
    assert "error" in snapshot
    assert snapshot["error"] == "Workspace directory does not exist"
    assert snapshot["file_count"] == 0


def test_snapshot_workspace_git_timeout(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace snapshot handles git timeout gracefully."""
    # Create .git directory
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        snapshot = manager_with_dirs._snapshot_workspace()

    # Assert
    assert snapshot["type"] == "git"
    assert "error" in snapshot
    assert snapshot["error"] == "Git command timed out"


def test_snapshot_workspace_git_error(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace snapshot handles git errors gracefully."""
    # Create .git directory
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    with patch("subprocess.run", side_effect=Exception("Git not found")):
        snapshot = manager_with_dirs._snapshot_workspace()

    # Assert
    assert snapshot["type"] == "git"
    assert "error" in snapshot
    assert "Git not found" in snapshot["error"]


def test_snapshot_workspace_skips_hidden_and_large_files(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test file-based snapshot skips hidden dirs and large files."""
    # Create regular file
    (workspace_dir / "normal.py").write_text("normal")

    # Create hidden directory with file (should be skipped)
    hidden_dir = workspace_dir / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("secret")

    # Create __pycache__ (should be skipped)
    cache_dir = workspace_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "module.pyc").write_text("bytecode")

    snapshot = manager_with_dirs._snapshot_workspace()

    # Assert - only normal.py should be captured
    assert snapshot["type"] == "files"
    assert snapshot["file_count"] == 1
    file_paths = [f["path"] for f in snapshot["files"]]
    assert "normal.py" in file_paths
    assert ".hidden/secret.txt" not in str(file_paths)


def test_snapshot_workspace_truncates_many_files(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test file-based snapshot truncates when >1000 files."""
    # Create 1001 files
    for i in range(1001):
        (workspace_dir / f"file_{i:04d}.txt").write_text(f"content {i}")

    snapshot = manager_with_dirs._snapshot_workspace()

    # Assert
    assert snapshot["type"] == "files"
    assert snapshot["file_count"] == 1001
    assert snapshot["files_truncated"] is True
    assert len(snapshot["files"]) == 100  # Only first 100


# =============================================================================
# File Hashing Tests
# =============================================================================


def test_hash_file(manager_with_dirs: CheckpointManager, workspace_dir: Path) -> None:
    """Test SHA256 file hashing."""
    test_file = workspace_dir / "test.txt"
    test_file.write_text("Hello, World!")

    file_hash = manager_with_dirs._hash_file(test_file)

    # Assert
    assert len(file_hash) == 16  # First 16 chars of SHA256
    assert file_hash.isalnum()  # Should be hex


def test_hash_file_consistent(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test that hashing same content produces same hash."""
    file1 = workspace_dir / "file1.txt"
    file2 = workspace_dir / "file2.txt"
    file1.write_text("identical content")
    file2.write_text("identical content")

    hash1 = manager_with_dirs._hash_file(file1)
    hash2 = manager_with_dirs._hash_file(file2)

    # Assert
    assert hash1 == hash2


def test_hash_file_different(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test that different content produces different hash."""
    file1 = workspace_dir / "file1.txt"
    file2 = workspace_dir / "file2.txt"
    file1.write_text("content A")
    file2.write_text("content B")

    hash1 = manager_with_dirs._hash_file(file1)
    hash2 = manager_with_dirs._hash_file(file2)

    # Assert
    assert hash1 != hash2


def test_hash_file_error(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test hash_file returns 'error' for unreadable files."""
    nonexistent = workspace_dir / "nonexistent.txt"

    file_hash = manager_with_dirs._hash_file(nonexistent)

    # Assert
    assert file_hash == "error"


# =============================================================================
# Memory Snapshot Tests
# =============================================================================


def test_snapshot_memory_with_file(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory snapshot with memory.json file."""
    memory_file = memory_dir / "memory.json"
    memory_data = {
        "entities": [
            {"name": "entity1", "type": "project"},
            {"name": "entity2", "type": "component"},
        ],
        "relations": [{"from": "entity1", "to": "entity2", "type": "contains"}],
    }
    memory_file.write_text(json.dumps(memory_data))

    snapshot = manager_with_dirs._snapshot_memory()

    # Assert
    assert snapshot["entity_count"] == 2
    assert snapshot["relation_count"] == 1
    assert snapshot["context_size"] == 3
    assert "file_size_bytes" in snapshot
    assert "last_modified" in snapshot


def test_snapshot_memory_list_format(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory snapshot with list format memory.json."""
    memory_file = memory_dir / "memory.json"
    memory_data = ["item1", "item2", "item3"]
    memory_file.write_text(json.dumps(memory_data))

    snapshot = manager_with_dirs._snapshot_memory()

    # Assert
    assert snapshot["context_size"] == 3


def test_snapshot_memory_no_file(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory snapshot when memory.json doesn't exist but other JSON files do."""
    # Create other JSON files instead of memory.json
    (memory_dir / "other1.json").write_text('{"key": "value1"}')
    (memory_dir / "other2.json").write_text('{"key": "value2"}')

    snapshot = manager_with_dirs._snapshot_memory()

    # Assert
    assert snapshot["file_count"] == 2
    assert snapshot["context_size"] == 2
    assert "total_size_bytes" in snapshot


def test_snapshot_memory_empty_dir(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory snapshot with empty memory directory."""
    snapshot = manager_with_dirs._snapshot_memory()

    # Assert
    assert snapshot["context_size"] == 0


def test_snapshot_memory_nonexistent(tmp_path: Path) -> None:
    """Test memory snapshot for non-existent directory."""
    manager = CheckpointManager(
        checkpoint_dir=tmp_path / "checkpoints",
        memory_dir=tmp_path / "nonexistent_memory",
        interval=3600,
    )

    snapshot = manager._snapshot_memory()

    # Assert
    assert "error" in snapshot
    assert snapshot["error"] == "Memory directory does not exist"
    assert snapshot["context_size"] == 0


def test_snapshot_memory_invalid_json(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory snapshot handles invalid JSON gracefully."""
    memory_file = memory_dir / "memory.json"
    memory_file.write_text("not valid json {{{")

    snapshot = manager_with_dirs._snapshot_memory()

    # Assert
    assert "parse_error" in snapshot
    assert snapshot["parse_error"] == "Could not parse memory file"
    assert snapshot["context_size"] == 0


# =============================================================================
# Restore/Recovery Tests
# =============================================================================


def test_restore_workspace_git_match(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace restore when git HEAD matches checkpoint."""
    # Create .git directory
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    snapshot = {
        "type": "git",
        "git_head": "abc123def456789",
        "git_branch": "main",
        "timestamp": "2025-01-01T00:00:00",
    }

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "abc123def456789"  # Same as checkpoint
        return result

    with patch("subprocess.run", side_effect=mock_run):
        # Should not raise, should log info (matching)
        manager_with_dirs._restore_workspace(snapshot)


def test_restore_workspace_git_changed(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace restore when git HEAD differs from checkpoint."""
    # Create .git directory
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    snapshot = {
        "type": "git",
        "git_head": "abc123def456789",
        "git_branch": "main",
        "timestamp": "2025-01-01T00:00:00",
    }

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "different123456"  # Different from checkpoint
        return result

    with patch("subprocess.run", side_effect=mock_run):
        # Should not raise, should log warning (changed)
        manager_with_dirs._restore_workspace(snapshot)


def test_restore_workspace_with_uncommitted_changes(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace restore when checkpoint had uncommitted changes."""
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()

    snapshot = {
        "type": "git",
        "git_head": "abc123def456789",
        "git_branch": "main",
        "has_uncommitted_changes": True,
        "uncommitted_count": 5,
        "timestamp": "2025-01-01T00:00:00",
    }

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "abc123def456789"
        return result

    with patch("subprocess.run", side_effect=mock_run):
        # Should log warning about uncommitted changes
        manager_with_dirs._restore_workspace(snapshot)


def test_restore_workspace_file_based(
    manager_with_dirs: CheckpointManager, workspace_dir: Path
) -> None:
    """Test workspace restore for file-based snapshot."""
    snapshot = {
        "type": "files",
        "file_count": 10,
        "timestamp": "2025-01-01T00:00:00",
    }

    # Should just log info, no git operations
    manager_with_dirs._restore_workspace(snapshot)


def test_restore_memory_match(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory restore when context size matches."""
    # Create memory file with 3 items
    memory_file = memory_dir / "memory.json"
    memory_data = {"entities": [{"name": "e1"}, {"name": "e2"}], "relations": [{"r": 1}]}
    memory_file.write_text(json.dumps(memory_data))

    snapshot = {
        "context_size": 3,  # 2 entities + 1 relation
        "timestamp": "2025-01-01T00:00:00",
    }

    # Should log info (matching)
    manager_with_dirs._restore_memory(snapshot)


def test_restore_memory_changed(
    manager_with_dirs: CheckpointManager, memory_dir: Path
) -> None:
    """Test memory restore when context size differs."""
    # Create memory file with different count
    memory_file = memory_dir / "memory.json"
    memory_data = {"entities": [{"name": "e1"}], "relations": []}
    memory_file.write_text(json.dumps(memory_data))

    snapshot = {
        "context_size": 10,  # Different from current (1)
        "timestamp": "2025-01-01T00:00:00",
    }

    # Should log warning (changed)
    manager_with_dirs._restore_memory(snapshot)


def test_recover_from_checkpoint_full_flow(
    manager_with_dirs: CheckpointManager, workspace_dir: Path, memory_dir: Path
) -> None:
    """Test full recovery flow from checkpoint."""
    # Setup
    git_dir = workspace_dir / ".git"
    git_dir.mkdir()
    memory_file = memory_dir / "memory.json"
    memory_file.write_text('{"entities": [], "relations": []}')

    checkpoint = {
        "timestamp": "2025-01-01T00:00:00",
        "version": "0.1.0",
        "state": {"session_id": "test-123", "tasks": ["task1"]},
        "workspace_snapshot": {
            "type": "git",
            "git_head": "abc123",
            "git_branch": "main",
            "timestamp": "2025-01-01T00:00:00",
        },
        "memory_snapshot": {"context_size": 0, "timestamp": "2025-01-01T00:00:00"},
    }

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "abc123"
        return result

    with patch("subprocess.run", side_effect=mock_run):
        recovered_state = manager_with_dirs.recover_from_checkpoint(checkpoint)

    # Assert
    assert recovered_state == {"session_id": "test-123", "tasks": ["task1"]}


# =============================================================================
# Delete Checkpoint Test
# =============================================================================


def test_delete_checkpoint(checkpoint_manager: CheckpointManager) -> None:
    """Test deleting a specific checkpoint."""
    # Arrange
    checkpoint_file = checkpoint_manager.save_checkpoint({"task": "to_delete"})
    assert checkpoint_file.exists()

    # Act
    checkpoint_manager.delete_checkpoint(checkpoint_file)

    # Assert
    assert not checkpoint_file.exists()


def test_delete_checkpoint_nonexistent(checkpoint_manager: CheckpointManager) -> None:
    """Test deleting a non-existent checkpoint doesn't raise."""
    nonexistent = checkpoint_manager.checkpoint_dir / "nonexistent.json"

    # Should not raise
    checkpoint_manager.delete_checkpoint(nonexistent)


# =============================================================================
# Checkpoint includes snapshots
# =============================================================================


def test_save_checkpoint_includes_snapshots(
    manager_with_dirs: CheckpointManager, workspace_dir: Path, memory_dir: Path
) -> None:
    """Test that saved checkpoint includes workspace and memory snapshots."""
    # Create some workspace files
    (workspace_dir / "code.py").write_text("print('test')")

    # Create memory file
    (memory_dir / "memory.json").write_text('{"entities": [], "relations": []}')

    # Save checkpoint
    checkpoint_file = manager_with_dirs.save_checkpoint({"task": "test"})

    # Load and verify
    with open(checkpoint_file, encoding="utf-8") as f:
        checkpoint = json.load(f)

    assert "workspace_snapshot" in checkpoint
    assert "memory_snapshot" in checkpoint
    assert checkpoint["workspace_snapshot"]["type"] == "files"
    assert checkpoint["workspace_snapshot"]["file_count"] == 1
    assert checkpoint["memory_snapshot"]["context_size"] == 0
