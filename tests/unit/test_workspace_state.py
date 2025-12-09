"""Unit tests for workspace state detection and handling."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harness.autonomous import AutonomousRunner
from harness.config import HarnessConfig
from harness.progress import WorkspaceState, WorkspaceConfig, TaskList, TaskItem


class TestWorkspaceStateDetection:
    """Tests for _detect_workspace_state method."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_workspace: Path):
        """Mock get_config to use temp directories."""
        config = HarnessConfig(
            workspace_dir=temp_workspace,
            memory_dir=temp_workspace / "memory",
        )
        with patch("harness.autonomous.get_config", return_value=config):
            yield config

    def test_empty_workspace_no_files(self, temp_workspace: Path, mock_config) -> None:
        """Test empty workspace returns EMPTY state."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.EMPTY
        assert context == {"has_spec": False}

    def test_empty_workspace_with_spec_only(self, temp_workspace: Path, mock_config) -> None:
        """Test workspace with only SPEC.md returns EMPTY state."""
        (temp_workspace / "SPEC.md").write_text("# My Project\n\nSpec content.")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.EMPTY
        assert context == {"has_spec": True}

    def test_conflict_multiple_spec_files(self, temp_workspace: Path, mock_config) -> None:
        """Test multiple SPEC.md files returns CONFLICT state."""
        # Create SPEC.md in root
        (temp_workspace / "SPEC.md").write_text("# Spec 1")

        # Create SPEC.md in subdirectory
        subdir = temp_workspace / "subproject"
        subdir.mkdir()
        (subdir / "SPEC.md").write_text("# Spec 2")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.CONFLICT
        assert "spec_files" in context
        assert len(context["spec_files"]) == 2

    def test_conflict_multiple_task_list_files(self, temp_workspace: Path, mock_config) -> None:
        """Test multiple task_list.json files returns CONFLICT state."""
        # Create task_list.json in root
        (temp_workspace / "task_list.json").write_text('{"version": "1.0", "tasks": []}')

        # Create task_list.json in subdirectory
        subdir = temp_workspace / "subproject"
        subdir.mkdir()
        (subdir / "task_list.json").write_text('{"version": "1.0", "tasks": []}')

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.CONFLICT
        assert "task_list_files" in context
        assert len(context["task_list_files"]) == 2

    def test_wip_with_incomplete_tasks(self, temp_workspace: Path, mock_config) -> None:
        """Test task_list.json with incomplete tasks returns WORK_IN_PROGRESS state."""
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Description",
                    acceptance_criteria=["Done"],
                    priority=1,
                    status="PASS",
                ),
                TaskItem(
                    id="task-002",
                    title="Task 2",
                    description="Description",
                    acceptance_criteria=["Done"],
                    priority=2,
                    status=None,  # Incomplete
                ),
            ],
        )
        (temp_workspace / "task_list.json").write_text(
            __import__("json").dumps(task_list.to_dict())
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.WORK_IN_PROGRESS
        assert "task_list" in context
        assert context["task_list"].get_completion_stats()["remaining"] > 0

    def test_completed_with_all_tasks_done(self, temp_workspace: Path, mock_config) -> None:
        """Test task_list.json with all tasks done returns COMPLETED state."""
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Description",
                    acceptance_criteria=["Done"],
                    priority=1,
                    status="PASS",
                ),
                TaskItem(
                    id="task-002",
                    title="Task 2",
                    description="Description",
                    acceptance_criteria=["Done"],
                    priority=2,
                    status="FAIL",
                ),
            ],
        )
        (temp_workspace / "task_list.json").write_text(
            __import__("json").dumps(task_list.to_dict())
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.COMPLETED
        assert "task_list" in context
        assert context["task_list"].get_completion_stats()["remaining"] == 0

    def test_external_repo_with_git(self, temp_workspace: Path, mock_config) -> None:
        """Test workspace with .git but no SPEC.md returns EXTERNAL_REPO state."""
        # Create .git directory
        (temp_workspace / ".git").mkdir()

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.EXTERNAL_REPO

    def test_external_repo_with_git_and_files(self, temp_workspace: Path, mock_config) -> None:
        """Test workspace with .git and other files (no SPEC.md) returns EXTERNAL_REPO."""
        # Create .git directory
        (temp_workspace / ".git").mkdir()
        # Create some files
        (temp_workspace / "README.md").write_text("# Project")
        (temp_workspace / "src").mkdir()
        (temp_workspace / "src" / "main.py").write_text("print('hello')")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.EXTERNAL_REPO

    def test_mixed_with_files_no_git(self, temp_workspace: Path, mock_config) -> None:
        """Test workspace with files but no .git returns MIXED state."""
        # Create some files but no .git
        (temp_workspace / "README.md").write_text("# Project")
        (temp_workspace / "src").mkdir()
        (temp_workspace / "src" / "main.py").write_text("print('hello')")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        assert state == WorkspaceState.MIXED

    def test_local_project_with_spec_and_git(self, temp_workspace: Path, mock_config) -> None:
        """Test workspace with SPEC.md, .git, and no task_list returns EMPTY."""
        # This is a local project ready for initialization
        (temp_workspace / ".git").mkdir()
        (temp_workspace / "SPEC.md").write_text("# My Project")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        state, context = runner._detect_workspace_state()

        # Has SPEC.md but no task_list, so it's EMPTY (ready for initializer)
        assert state == WorkspaceState.EMPTY


class TestGitHelpers:
    """Tests for git helper methods."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_workspace: Path):
        """Mock get_config to use temp directories."""
        config = HarnessConfig(
            workspace_dir=temp_workspace,
            memory_dir=temp_workspace / "memory",
        )
        with patch("harness.autonomous.get_config", return_value=config):
            yield config

    def test_get_git_remote_url_no_git(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_git_remote_url returns None when not a git repo."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_git_remote_url()

        assert result is None

    def test_get_git_remote_url_with_remote(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_git_remote_url returns remote URL."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=temp_workspace,
            capture_output=True,
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_git_remote_url()

        assert result == "https://github.com/user/repo.git"

    def test_get_current_branch_no_git(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_current_branch returns None when not a git repo."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_current_branch()

        assert result is None

    def test_get_current_branch_with_commits(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_current_branch returns branch name."""
        # Initialize git repo with a commit
        subprocess.run(["git", "init"], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_workspace,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_workspace,
            capture_output=True,
        )
        (temp_workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_workspace,
            capture_output=True,
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_current_branch()

        assert result in ["main", "master"]

    def test_parse_branch_from_spec_valid(self, temp_workspace: Path, mock_config) -> None:
        """Test _parse_branch_from_spec extracts branch from SPEC.md."""
        spec_content = """# My Project

branch: casdk-my-feature

## Overview
Some content here.
"""
        (temp_workspace / "SPEC.md").write_text(spec_content)

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._parse_branch_from_spec()

        assert result == "casdk-my-feature"

    def test_parse_branch_from_spec_no_branch(self, temp_workspace: Path, mock_config) -> None:
        """Test _parse_branch_from_spec returns None when no branch field."""
        spec_content = """# My Project

## Overview
Some content here.
"""
        (temp_workspace / "SPEC.md").write_text(spec_content)

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._parse_branch_from_spec()

        assert result is None

    def test_parse_branch_from_spec_no_file(self, temp_workspace: Path, mock_config) -> None:
        """Test _parse_branch_from_spec returns None when no SPEC.md."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._parse_branch_from_spec()

        assert result is None

    def test_parse_branch_from_spec_invalid_format(self, temp_workspace: Path, mock_config) -> None:
        """Test _parse_branch_from_spec returns None for invalid branch format."""
        spec_content = """# My Project

branch: invalid-branch-no-prefix

## Overview
Some content here.
"""
        (temp_workspace / "SPEC.md").write_text(spec_content)

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._parse_branch_from_spec()

        # Must start with casdk-
        assert result is None

    def test_run_git_init(self, temp_workspace: Path, mock_config) -> None:
        """Test _run_git_init creates git repository."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # _run_git_init is synchronous, not async
        result = runner._run_git_init()

        assert result is True
        assert (temp_workspace / ".git").exists()


class TestWorkspaceStateHandlers:
    """Tests for workspace state handler methods."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_workspace: Path):
        """Mock get_config to use temp directories."""
        config = HarnessConfig(
            workspace_dir=temp_workspace,
            memory_dir=temp_workspace / "memory",
        )
        with patch("harness.autonomous.get_config", return_value=config):
            yield config

    @pytest.mark.asyncio
    async def test_handle_empty_workspace(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_empty_workspace runs git init and returns True."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = await runner._handle_empty_workspace({})

        assert result is True
        assert (temp_workspace / ".git").exists()

    @pytest.mark.asyncio
    async def test_handle_wip_workspace(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_wip_workspace returns True."""
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Desc",
                    acceptance_criteria=["Done"],
                    priority=1,
                    status=None,
                ),
            ],
        )
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = await runner._handle_wip_workspace({"task_list": task_list})

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_completed_workspace_continue(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _handle_completed_workspace with continue response."""
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Desc",
                    acceptance_criteria=["Done"],
                    priority=1,
                    status="PASS",
                ),
            ],
        )
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "y" for continue
        with patch("harness.autonomous.Prompt.ask", return_value="y"):
            result = await runner._handle_completed_workspace({"task_list": task_list, "stats": task_list.get_completion_stats()})

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_completed_workspace_exit(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _handle_completed_workspace with exit response."""
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Desc",
                    acceptance_criteria=["Done"],
                    priority=1,
                    status="PASS",
                ),
            ],
        )
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "n" for exit
        with patch("harness.autonomous.Prompt.ask", return_value="n"):
            result = await runner._handle_completed_workspace({"task_list": task_list, "stats": task_list.get_completion_stats()})

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_conflict_workspace(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_conflict_workspace returns False and prints message."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        spec_files = [str(temp_workspace / "SPEC.md"), str(temp_workspace / "sub" / "SPEC.md")]
        task_list_files = []

        # Mock the console to capture output
        mock_console = MagicMock()
        runner.console = mock_console

        result = await runner._handle_conflict_workspace({
            "spec_files": spec_files,
            "task_list_files": task_list_files,
        })

        assert result is False
        # Verify console.print was called with error message
        assert mock_console.print.called
        # Check that "ERROR" is in one of the print calls
        call_args_list = mock_console.print.call_args_list
        assert any("ERROR" in str(call) for call in call_args_list)

    @pytest.mark.asyncio
    async def test_handle_external_repo_work(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_external_repo with work on repo response."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_workspace,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_workspace,
            capture_output=True,
        )
        (temp_workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_workspace,
            capture_output=True,
        )

        # Create SPEC.md with branch field
        (temp_workspace / "SPEC.md").write_text("# Project\n\nbranch: casdk-feature\n")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "work"
        with patch("harness.autonomous.Prompt.ask", return_value="work"):
            result = await runner._handle_external_repo({})

        assert result is True
        # Verify branch was created or pending workspace config set
        assert runner._pending_workspace_config is not None

    @pytest.mark.asyncio
    async def test_handle_external_repo_clean(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_external_repo with clean response."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "clean"
        with patch("harness.autonomous.Prompt.ask", return_value="clean"):
            result = await runner._handle_external_repo({})

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_mixed_workspace_continue(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _handle_mixed_workspace with continue response."""
        (temp_workspace / "README.md").write_text("# Test")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "continue"
        with patch("harness.autonomous.Prompt.ask", return_value="continue"):
            result = await runner._handle_mixed_workspace({})

        assert result is True
        # Should have run git init
        assert (temp_workspace / ".git").exists()

    @pytest.mark.asyncio
    async def test_handle_mixed_workspace_clean(self, temp_workspace: Path, mock_config) -> None:
        """Test _handle_mixed_workspace with clean response."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock Rich Prompt.ask to return "clean"
        with patch("harness.autonomous.Prompt.ask", return_value="clean"):
            result = await runner._handle_mixed_workspace({})

        assert result is False


class TestHandleWorkspaceState:
    """Tests for _handle_workspace_state dispatcher."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_workspace: Path):
        """Mock get_config to use temp directories."""
        config = HarnessConfig(
            workspace_dir=temp_workspace,
            memory_dir=temp_workspace / "memory",
        )
        with patch("harness.autonomous.get_config", return_value=config):
            yield config

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _handle_workspace_state calls correct handler for each state."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Test EMPTY state
        with patch.object(
            runner, "_handle_empty_workspace", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = True
            await runner._handle_workspace_state(WorkspaceState.EMPTY, {})
            mock_handler.assert_called_once()

        # Test CONFLICT state
        with patch.object(
            runner, "_handle_conflict_workspace", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = False
            await runner._handle_workspace_state(WorkspaceState.CONFLICT, {})
            mock_handler.assert_called_once()

        # Test EXTERNAL_REPO state
        with patch.object(
            runner, "_handle_external_repo", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = True
            await runner._handle_workspace_state(WorkspaceState.EXTERNAL_REPO, {})
            mock_handler.assert_called_once()


class TestEnsureBranch:
    """Tests for _ensure_branch method."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_config(self, temp_workspace: Path):
        """Mock get_config to use temp directories."""
        config = HarnessConfig(
            workspace_dir=temp_workspace,
            memory_dir=temp_workspace / "memory",
        )
        with patch("harness.autonomous.get_config", return_value=config):
            yield config

    def test_ensure_branch_creates_new_branch(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _ensure_branch creates new branch if it doesn't exist."""
        # Initialize git repo with a commit
        subprocess.run(["git", "init"], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_workspace,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_workspace,
            capture_output=True,
        )
        (temp_workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_workspace,
            capture_output=True,
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # _ensure_branch is synchronous, not async
        result = runner._ensure_branch("casdk-test-feature")

        assert result is True
        # Verify we're on the new branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=temp_workspace,
            capture_output=True,
            text=True,
        )
        assert branch_result.stdout.strip() == "casdk-test-feature"

    def test_ensure_branch_switches_to_existing(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test _ensure_branch switches to existing branch."""
        # Initialize git repo with a commit
        subprocess.run(["git", "init"], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_workspace,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_workspace,
            capture_output=True,
        )
        (temp_workspace / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=temp_workspace, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=temp_workspace,
            capture_output=True,
        )

        # Create the branch first
        subprocess.run(
            ["git", "checkout", "-b", "casdk-existing"],
            cwd=temp_workspace,
            capture_output=True,
        )
        # Switch back to main/master
        subprocess.run(
            ["git", "checkout", "-"],  # Go back to previous branch
            cwd=temp_workspace,
            capture_output=True,
        )

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # _ensure_branch is synchronous, not async
        result = runner._ensure_branch("casdk-existing")

        assert result is True
        # Verify we're on the existing branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=temp_workspace,
            capture_output=True,
            text=True,
        )
        assert branch_result.stdout.strip() == "casdk-existing"
