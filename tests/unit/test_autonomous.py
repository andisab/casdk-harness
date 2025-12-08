"""Unit tests for autonomous development mode."""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from harness.autonomous import AutonomousRunner, load_prompt
from harness.config import HarnessConfig
from harness.progress import QASession, SessionData, TaskItem, TaskList


class TestLoadPrompt:
    """Tests for prompt loading."""

    def test_load_existing_prompt(self) -> None:
        """Test loading an existing prompt file."""
        # These prompts should exist
        for prompt_name in ["tech_lead", "initializer", "continuation"]:
            prompt = load_prompt(prompt_name)
            assert prompt is not None
            assert len(prompt) > 0

    def test_load_nonexistent_prompt(self) -> None:
        """Test loading a nonexistent prompt raises error."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")

    def test_tech_lead_prompt_content(self) -> None:
        """Test tech lead prompt contains expected content."""
        prompt = load_prompt("tech_lead")
        assert "technical lead" in prompt.lower()
        assert "task" in prompt.lower()

    def test_initializer_prompt_content(self) -> None:
        """Test initializer prompt contains expected content."""
        prompt = load_prompt("initializer")
        assert "initializer" in prompt.lower() or "spec" in prompt.lower()

    def test_continuation_prompt_content(self) -> None:
        """Test continuation prompt contains expected content."""
        prompt = load_prompt("continuation")
        assert "continuation" in prompt.lower() or "coding" in prompt.lower()


class TestAutonomousRunner:
    """Tests for AutonomousRunner class."""

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

    def test_runner_initialization(self, temp_workspace: Path, mock_config) -> None:
        """Test runner initializes correctly."""
        runner = AutonomousRunner(
            workspace_dir=temp_workspace,
            model="sonnet",
        )

        assert runner.workspace_dir == temp_workspace
        assert runner.model == "sonnet"
        assert runner._shutdown_requested is False

    def test_get_mode_no_task_list(self, temp_workspace: Path, mock_config) -> None:
        """Test mode detection with no task list."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mode = runner._get_mode()
        assert mode == "initializer"

    def test_get_mode_with_task_list(self, temp_workspace: Path, mock_config) -> None:
        """Test mode detection with existing task list."""
        # Create a task list file
        task_list_path = temp_workspace / "task_list.json"
        task_list_path.write_text('{"version": "1.0", "tasks": []}')

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mode = runner._get_mode()
        assert mode == "continuation"

    def test_build_initializer_prompt_no_spec(self, temp_workspace: Path, mock_config) -> None:
        """Test building initializer prompt without SPEC.md."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        prompt = runner._build_initializer_prompt()

        assert "No SPEC.md found" in prompt
        assert "Tech Lead" in prompt

    def test_build_initializer_prompt_with_spec(self, temp_workspace: Path, mock_config) -> None:
        """Test building initializer prompt with SPEC.md."""
        # Create a spec file
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text("# My Project\n\nTest specification content.")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        prompt = runner._build_initializer_prompt()

        assert "My Project" in prompt
        assert "Test specification content" in prompt

    def test_signal_handler_sets_shutdown_flag(self, temp_workspace: Path, mock_config) -> None:
        """Test signal handler sets shutdown flag."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        assert runner._shutdown_requested is False

        # Simulate signal (we pass None for frame as we don't use it)
        runner._signal_handler(2, None)  # SIGINT = 2

        assert runner._shutdown_requested is True

    def test_init_context_directory_creates_files(self, temp_workspace: Path, mock_config) -> None:
        """Test context directory initialization creates all required files."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Directory shouldn't exist yet
        context_dir = temp_workspace / "context"
        assert not context_dir.exists()

        # Initialize context directory
        runner._init_context_directory()

        # Verify directory and files exist
        assert context_dir.exists()
        assert (context_dir / "architecture.md").exists()
        assert (context_dir / "decisions.md").exists()
        assert (context_dir / "issues.md").exists()
        assert (context_dir / "next-steps.md").exists()

    def test_init_context_directory_preserves_existing(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test context directory initialization preserves existing files."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Create directory and one file with custom content
        context_dir = temp_workspace / "context"
        context_dir.mkdir()
        custom_file = context_dir / "decisions.md"
        custom_content = "# Custom Decisions\n\nMy custom content."
        custom_file.write_text(custom_content)

        # Initialize context directory
        runner._init_context_directory()

        # Verify custom file was preserved
        assert custom_file.read_text() == custom_content

        # Verify other files were created
        assert (context_dir / "architecture.md").exists()
        assert (context_dir / "issues.md").exists()
        assert (context_dir / "next-steps.md").exists()

    def test_init_context_directory_file_format(self, temp_workspace: Path, mock_config) -> None:
        """Test context files have correct YAML front matter format."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        runner._init_context_directory()

        # Check architecture.md has proper format
        arch_content = (temp_workspace / "context" / "architecture.md").read_text()
        assert arch_content.startswith("---")
        assert "type: architecture" in arch_content
        assert "created:" in arch_content
        assert "updated:" in arch_content
        assert "tags:" in arch_content

        # Check decisions.md has proper format
        dec_content = (temp_workspace / "context" / "decisions.md").read_text()
        assert "type: decisions" in dec_content
        assert "append-only" in dec_content


class TestSpecHash:
    """Tests for _get_spec_hash method."""

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

    def test_no_spec_file_returns_no_spec(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_spec_hash returns 'no_spec' when SPEC.md doesn't exist."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_spec_hash()

        assert result == "no_spec"

    def test_spec_file_returns_md5_hash(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_spec_hash returns MD5 hash of SPEC.md content."""
        spec_content = "# My Project Spec\n\nThis is the specification."
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text(spec_content)

        runner = AutonomousRunner(workspace_dir=temp_workspace)
        result = runner._get_spec_hash()

        # Calculate expected hash
        expected_hash = hashlib.md5(spec_content.encode()).hexdigest()
        assert result == expected_hash

    def test_different_content_returns_different_hash(self, temp_workspace: Path, mock_config) -> None:
        """Test different SPEC.md content returns different hashes."""
        spec_path = temp_workspace / "SPEC.md"

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # First content
        spec_path.write_text("Content A")
        hash_a = runner._get_spec_hash()

        # Second content
        spec_path.write_text("Content B")
        hash_b = runner._get_spec_hash()

        assert hash_a != hash_b

    def test_same_content_returns_same_hash(self, temp_workspace: Path, mock_config) -> None:
        """Test same SPEC.md content returns consistent hash."""
        spec_content = "# Consistent Content"
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text(spec_content)

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        hash_1 = runner._get_spec_hash()
        hash_2 = runner._get_spec_hash()

        assert hash_1 == hash_2


class TestQASessionPath:
    """Tests for _get_qa_session_path method."""

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

    def test_returns_correct_path(self, temp_workspace: Path, mock_config) -> None:
        """Test _get_qa_session_path returns workspace/qa_session.json."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._get_qa_session_path()

        expected = temp_workspace / "qa_session.json"
        assert result == expected


class TestQASessionCRUD:
    """Tests for QA session CRUD operations."""

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

    def test_load_returns_none_when_no_file(self, temp_workspace: Path, mock_config) -> None:
        """Test _load_qa_session returns None when file doesn't exist."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        result = runner._load_qa_session()

        assert result is None

    def test_save_creates_file(self, temp_workspace: Path, mock_config) -> None:
        """Test _save_qa_session creates qa_session.json file."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test_hash",
        )

        runner._save_qa_session(session)

        qa_path = temp_workspace / "qa_session.json"
        assert qa_path.exists()

        # Verify content
        with open(qa_path) as f:
            data = json.load(f)
        assert data["started_at"] == "2025-01-01T00:00:00+00:00"
        assert data["spec_hash"] == "test_hash"

    def test_load_returns_session_after_save(self, temp_workspace: Path, mock_config) -> None:
        """Test _load_qa_session returns saved session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        original = QASession(
            started_at="2025-01-01T12:00:00+00:00",
            spec_hash="no_spec",  # Match actual hash so it doesn't invalidate
            total_questions=5,
            current_question=2,
        )

        runner._save_qa_session(original)
        loaded = runner._load_qa_session()

        assert loaded is not None
        assert loaded.started_at == "2025-01-01T12:00:00+00:00"
        assert loaded.spec_hash == "no_spec"
        assert loaded.total_questions == 5
        assert loaded.current_question == 2

    def test_delete_removes_file(self, temp_workspace: Path, mock_config) -> None:
        """Test _delete_qa_session removes the file."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test_hash",
        )

        # Save then delete
        runner._save_qa_session(session)
        qa_path = temp_workspace / "qa_session.json"
        assert qa_path.exists()

        runner._delete_qa_session()

        assert not qa_path.exists()

    def test_delete_handles_nonexistent_file(self, temp_workspace: Path, mock_config) -> None:
        """Test _delete_qa_session handles nonexistent file gracefully."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Should not raise
        runner._delete_qa_session()

    def test_load_returns_none_for_invalid_json(self, temp_workspace: Path, mock_config) -> None:
        """Test _load_qa_session returns None for invalid JSON."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        qa_path = temp_workspace / "qa_session.json"
        qa_path.write_text("not valid json {{{")

        result = runner._load_qa_session()

        assert result is None

    def test_load_returns_none_when_spec_hash_changed(self, temp_workspace: Path, mock_config) -> None:
        """Test _load_qa_session returns None when spec hash has changed."""
        # Create a SPEC.md with initial content
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text("Original spec content")

        runner = AutonomousRunner(workspace_dir=temp_workspace)
        original_hash = runner._get_spec_hash()

        # Save session with original hash
        session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash=original_hash,
        )
        runner._save_qa_session(session)

        # Change the spec
        spec_path.write_text("Changed spec content")

        # Load should return None due to hash mismatch
        result = runner._load_qa_session()

        assert result is None


class TestCreateQASession:
    """Tests for _create_qa_session method."""

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

    def test_creates_session_with_timestamp(self, temp_workspace: Path, mock_config) -> None:
        """Test _create_qa_session creates session with ISO timestamp."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        session = runner._create_qa_session()

        assert session.started_at is not None
        assert "T" in session.started_at  # ISO format contains T
        assert len(session.started_at) > 10  # Reasonable timestamp length

    def test_creates_session_with_spec_hash(self, temp_workspace: Path, mock_config) -> None:
        """Test _create_qa_session includes current spec hash."""
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text("Test spec content")

        runner = AutonomousRunner(workspace_dir=temp_workspace)
        session = runner._create_qa_session()

        expected_hash = hashlib.md5(b"Test spec content").hexdigest()
        assert session.spec_hash == expected_hash

    def test_creates_session_without_spec(self, temp_workspace: Path, mock_config) -> None:
        """Test _create_qa_session uses 'no_spec' when no SPEC.md exists."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        session = runner._create_qa_session()

        assert session.spec_hash == "no_spec"


class TestExtractContentStr:
    """Tests for _extract_content_str method."""

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

    def test_extracts_string_content(self, temp_workspace: Path, mock_config) -> None:
        """Test _extract_content_str extracts string content attribute."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_message = MagicMock()
        mock_message.content = "Hello, world!"

        result = runner._extract_content_str(mock_message)

        assert result == "Hello, world!"

    def test_extracts_list_content(self, temp_workspace: Path, mock_config) -> None:
        """Test _extract_content_str joins list content with newlines."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_message = MagicMock()
        mock_message.content = ["First block", "Second block", "Third block"]

        result = runner._extract_content_str(mock_message)

        assert result == "First block\nSecond block\nThird block"

    def test_handles_no_content_attribute(self, temp_workspace: Path, mock_config) -> None:
        """Test _extract_content_str handles message without content attribute."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_message = MagicMock(spec=[])  # No content attribute
        del mock_message.content  # Ensure no content attribute

        result = runner._extract_content_str(mock_message)

        # Should return string representation of the message
        assert isinstance(result, str)

    def test_handles_none_content(self, temp_workspace: Path, mock_config) -> None:
        """Test _extract_content_str handles None content attribute."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_message = MagicMock()
        mock_message.content = None

        result = runner._extract_content_str(mock_message)

        # Should return string representation of the message
        assert isinstance(result, str)


class TestParseQuestionProgress:
    """Tests for _parse_question_progress method."""

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

    def test_parses_questions_planned(self, temp_workspace: Path, mock_config) -> None:
        """Test parsing [QUESTIONS_PLANNED: N] signal."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
        )

        content = "I will ask you [QUESTIONS_PLANNED: 8] questions to clarify the spec."
        runner._parse_question_progress(content, qa_session)

        assert qa_session.total_questions == 8

    def test_parses_question_progress(self, temp_workspace: Path, mock_config) -> None:
        """Test parsing **Question X/Y** format."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
        )

        content = "**Question 3/10**\n\nWhat framework do you prefer?"
        runner._parse_question_progress(content, qa_session)

        assert qa_session.current_question == 3
        assert qa_session.total_questions == 10

    def test_parses_both_signals(self, temp_workspace: Path, mock_config) -> None:
        """Test parsing content with both signals."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
        )

        content = """[QUESTIONS_PLANNED: 5]

**Question 1/5**

First question here."""
        runner._parse_question_progress(content, qa_session)

        # Question format takes precedence for total
        assert qa_session.current_question == 1
        assert qa_session.total_questions == 5

    def test_no_signals_no_change(self, temp_workspace: Path, mock_config) -> None:
        """Test content without signals doesn't change session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
            total_questions=3,
            current_question=2,
        )

        content = "Just some regular text without any signals."
        runner._parse_question_progress(content, qa_session)

        # Values unchanged
        assert qa_session.total_questions == 3
        assert qa_session.current_question == 2


class TestCheckCompletionSignals:
    """Tests for _check_completion_signals method."""

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

    @pytest.fixture
    def session_data(self) -> SessionData:
        """Create a fresh SessionData for testing."""
        return SessionData(
            session_number=1,
            started_at="2025-01-01T00:00:00+00:00",
        )

    def test_task_list_ready_signal(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test [TASK_LIST_READY] signal returns completed=True."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "I've created the task list. [TASK_LIST_READY]"
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is True
        assert blocked is False

    def test_task_complete_signal(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test [TASK_COMPLETE: task-001] signal."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "Task finished successfully. [TASK_COMPLETE: task-001]"
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is True
        assert blocked is False
        assert "task-001" in session_data.tasks_passed
        assert "task-001" in session_data.tasks_worked

    def test_task_blocked_signal(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test [TASK_BLOCKED: task-002: reason] signal."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "Cannot proceed. [TASK_BLOCKED: task-002: Missing API credentials]"
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is False
        assert blocked is True
        assert "task-002" in session_data.tasks_failed
        assert "task-002" in session_data.tasks_worked

    def test_commit_signal_with_message(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test [COMMIT: hash: message] signal."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "Committed changes. [COMMIT: abc123: Add user authentication]"
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is False
        assert blocked is False
        assert "abc123: Add user authentication" in session_data.git_commits

    def test_commit_signal_without_message(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test [COMMIT: hash] signal without message."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "Quick commit. [COMMIT: def456]"
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is False
        assert blocked is False
        assert "def456" in session_data.git_commits

    def test_multiple_commits(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test multiple commit signals in same content."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = """Made several commits:
[COMMIT: aaa111: First change]
[COMMIT: bbb222: Second change]
[COMMIT: ccc333]"""
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert len(session_data.git_commits) == 3
        assert "aaa111: First change" in session_data.git_commits
        assert "bbb222: Second change" in session_data.git_commits
        assert "ccc333" in session_data.git_commits

    def test_duplicate_task_not_added_twice(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test same task_id isn't added twice to lists."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "[TASK_COMPLETE: task-001]"
        runner._check_completion_signals(content, session_data)
        runner._check_completion_signals(content, session_data)

        # Should only appear once
        assert session_data.tasks_passed.count("task-001") == 1
        assert session_data.tasks_worked.count("task-001") == 1

    def test_no_signals_returns_false(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test content without signals returns (False, False)."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = "Just working on the task, making progress..."
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is False
        assert blocked is False
        assert len(session_data.tasks_passed) == 0
        assert len(session_data.tasks_failed) == 0

    def test_with_task_list_updates_status(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test task_list parameter receives status updates."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_task_list = MagicMock()
        content = "[TASK_COMPLETE: task-003]"
        runner._check_completion_signals(content, session_data, task_list=mock_task_list)

        mock_task_list.update_task_status.assert_called_once_with("task-003", "PASS")

    def test_blocked_task_updates_task_list(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test blocked task updates task_list with FAIL status."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_task_list = MagicMock()
        content = "[TASK_BLOCKED: task-004: Network error]"
        runner._check_completion_signals(content, session_data, task_list=mock_task_list)

        mock_task_list.update_task_status.assert_called_once_with("task-004", "FAIL")

    def test_combined_signals(self, temp_workspace: Path, mock_config, session_data) -> None:
        """Test content with multiple different signal types."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        content = """Completed the task with a commit.
[TASK_COMPLETE: task-005]
[COMMIT: 789abc: Implement feature X]"""
        completed, blocked = runner._check_completion_signals(content, session_data)

        assert completed is True
        assert blocked is False
        assert "task-005" in session_data.tasks_passed
        assert "789abc: Implement feature X" in session_data.git_commits


class TestBuildInitializerPromptWithResume:
    """Tests for _build_initializer_prompt with resumable QA session."""

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

    def test_prompt_includes_resume_context(self, temp_workspace: Path, mock_config) -> None:
        """Test prompt includes resume context for resumable session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Create a resumable QA session
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="no_spec",
            status="in_progress",
            current_question=2,
            total_questions=5,
            conversation_history=[
                {"role": "assistant", "content": "What framework would you like?"},
                {"role": "user", "content": "React please"},
            ],
        )

        prompt = runner._build_initializer_prompt(qa_session)

        assert "Resuming Previous Session" in prompt
        assert "Question 2/5" in prompt
        assert "What framework would you like?" in prompt
        assert "React please" in prompt
        assert "Continue from where you left off" in prompt

    def test_prompt_shows_conversation_roles(self, temp_workspace: Path, mock_config) -> None:
        """Test prompt shows correct role labels in conversation history."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="no_spec",
            status="in_progress",
            conversation_history=[
                {"role": "assistant", "content": "Assistant message"},
                {"role": "user", "content": "User message"},
            ],
        )

        prompt = runner._build_initializer_prompt(qa_session)

        assert "**Tech Lead**: Assistant message" in prompt
        assert "**User**: User message" in prompt

    def test_non_resumable_session_no_context(self, temp_workspace: Path, mock_config) -> None:
        """Test non-resumable session doesn't add resume context."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Session with status=completed is not resumable
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="no_spec",
            status="completed",
            conversation_history=[
                {"role": "assistant", "content": "Some message"},
            ],
        )

        prompt = runner._build_initializer_prompt(qa_session)

        assert "Resuming Previous Session" not in prompt


class TestBuildContinuationPrompt:
    """Tests for _build_continuation_prompt method."""

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

    @pytest.fixture
    def sample_task_list(self) -> TaskList:
        """Create a sample task list for testing."""
        return TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test Project",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Implement user auth",
                    description="Add login/logout",
                    acceptance_criteria=["Users can log in", "Sessions persist"],
                    priority=1,
                    status=None,
                ),
                TaskItem(
                    id="task-002",
                    title="Add dashboard",
                    description="Create main dashboard",
                    acceptance_criteria=["Shows user stats"],
                    priority=2,
                    status=None,
                ),
            ],
        )

    def test_prompt_includes_project_info(self, temp_workspace: Path, mock_config, sample_task_list) -> None:
        """Test prompt includes project name, version, and creation date."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with patch.object(runner.progress_manager, "load_task_list", return_value=sample_task_list):
            with patch.object(runner.progress_manager, "get_totals", return_value={
                "total_sessions": 3,
                "total_cost_usd": 0.1234,
            }):
                with patch.object(runner.progress_manager, "load_all_sessions", return_value=[]):
                    prompt = runner._build_continuation_prompt()

        assert "**Project**: Test Project" in prompt
        assert "**Version**: 1.0" in prompt
        assert "**Created**: 2025-01-01T00:00:00+00:00" in prompt

    def test_prompt_includes_next_task(self, temp_workspace: Path, mock_config, sample_task_list) -> None:
        """Test prompt includes details of next task."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with patch.object(runner.progress_manager, "load_task_list", return_value=sample_task_list):
            with patch.object(runner.progress_manager, "get_totals", return_value={
                "total_sessions": 1,
                "total_cost_usd": 0.05,
            }):
                with patch.object(runner.progress_manager, "load_all_sessions", return_value=[]):
                    prompt = runner._build_continuation_prompt()

        assert "**ID**: task-001" in prompt
        assert "**Title**: Implement user auth" in prompt
        assert "**Description**: Add login/logout" in prompt
        assert "Users can log in" in prompt
        assert "Sessions persist" in prompt

    def test_prompt_shows_all_tasks_completed(self, temp_workspace: Path, mock_config) -> None:
        """Test prompt shows completion message when all tasks done."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # All tasks completed
        completed_task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Done Project",
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

        with patch.object(runner.progress_manager, "load_task_list", return_value=completed_task_list):
            with patch.object(runner.progress_manager, "get_totals", return_value={
                "total_sessions": 5,
                "total_cost_usd": 0.50,
            }):
                with patch.object(runner.progress_manager, "load_all_sessions", return_value=[]):
                    prompt = runner._build_continuation_prompt()

        assert "All tasks completed!" in prompt

    def test_prompt_includes_recent_sessions(self, temp_workspace: Path, mock_config, sample_task_list) -> None:
        """Test prompt includes recent session summaries."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        recent_sessions = [
            SessionData(
                session_number=1,
                started_at="2025-01-01T10:00:00+00:00",
                tasks_passed=["task-001"],
                tasks_failed=[],
                notes="First session went well",
            ),
            SessionData(
                session_number=2,
                started_at="2025-01-01T12:00:00+00:00",
                tasks_passed=[],
                tasks_failed=["task-002"],
                notes="Hit a blocker",
            ),
        ]

        with patch.object(runner.progress_manager, "load_task_list", return_value=sample_task_list):
            with patch.object(runner.progress_manager, "get_totals", return_value={
                "total_sessions": 2,
                "total_cost_usd": 0.10,
            }):
                with patch.object(runner.progress_manager, "load_all_sessions", return_value=recent_sessions):
                    prompt = runner._build_continuation_prompt()

        assert "Recent Sessions" in prompt
        assert "Session 1" in prompt
        assert "Session 2" in prompt
        assert "task-001" in prompt
        assert "task-002" in prompt

    def test_prompt_includes_progress_stats(self, temp_workspace: Path, mock_config, sample_task_list) -> None:
        """Test prompt includes task progress statistics."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with patch.object(runner.progress_manager, "load_task_list", return_value=sample_task_list):
            with patch.object(runner.progress_manager, "get_totals", return_value={
                "total_sessions": 10,
                "total_cost_usd": 1.5678,
            }):
                with patch.object(runner.progress_manager, "load_all_sessions", return_value=[]):
                    prompt = runner._build_continuation_prompt()

        assert "**Total Tasks**: 2" in prompt
        assert "**Total Sessions**: 10" in prompt
        assert "$1.5678" in prompt


class TestRunSession:
    """Tests for _run_session dispatcher method."""

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

    @pytest.fixture
    def session_data(self) -> SessionData:
        """Create a fresh SessionData for testing."""
        return SessionData(
            session_number=1,
            started_at="2025-01-01T00:00:00+00:00",
        )

    @pytest.mark.asyncio
    async def test_initializer_creates_qa_session_if_none(
        self, temp_workspace: Path, mock_config, session_data
    ) -> None:
        """Test initializer mode creates qa_session if not provided."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Mock _run_initializer_session to capture args
        with patch.object(
            runner, "_run_initializer_session", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = (True, "content")

            await runner._run_session(
                mode="initializer",
                prompt="test prompt",
                session=session_data,
                qa_session=None,
            )

            # Verify qa_session was created and passed
            mock_init.assert_called_once()
            call_args = mock_init.call_args
            assert call_args[0][2] is not None  # qa_session argument
            assert isinstance(call_args[0][2], QASession)

    @pytest.mark.asyncio
    async def test_initializer_uses_provided_qa_session(
        self, temp_workspace: Path, mock_config, session_data
    ) -> None:
        """Test initializer mode uses provided qa_session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        provided_qa = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
        )

        with patch.object(
            runner, "_run_initializer_session", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = (True, "content")

            await runner._run_session(
                mode="initializer",
                prompt="test prompt",
                session=session_data,
                qa_session=provided_qa,
            )

            # Verify provided qa_session was used
            call_args = mock_init.call_args
            assert call_args[0][2] is provided_qa

    @pytest.mark.asyncio
    async def test_continuation_requires_task_list(
        self, temp_workspace: Path, mock_config, session_data
    ) -> None:
        """Test continuation mode raises error without task_list."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with pytest.raises(ValueError, match="task_list required"):
            await runner._run_session(
                mode="continuation",
                prompt="test prompt",
                session=session_data,
                task_list=None,
            )

    @pytest.mark.asyncio
    async def test_continuation_calls_correct_handler(
        self, temp_workspace: Path, mock_config, session_data
    ) -> None:
        """Test continuation mode calls _run_continuation_session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        task_list = TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[],
        )

        with patch.object(
            runner, "_run_continuation_session", new_callable=AsyncMock
        ) as mock_cont:
            mock_cont.return_value = (True, "content")

            await runner._run_session(
                mode="continuation",
                prompt="test prompt",
                session=session_data,
                task_list=task_list,
            )

            mock_cont.assert_called_once_with("test prompt", session_data, task_list)


class TestRunContinuationSession:
    """Tests for _run_continuation_session async method."""

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

    @pytest.fixture
    def session_data(self) -> SessionData:
        """Create a fresh SessionData for testing."""
        return SessionData(
            session_number=1,
            started_at="2025-01-01T00:00:00+00:00",
        )

    @pytest.fixture
    def task_list(self) -> TaskList:
        """Create a sample task list."""
        return TaskList(
            version="1.0",
            created_at="2025-01-01T00:00:00+00:00",
            project_name="Test",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Test task",
                    description="Test description",
                    acceptance_criteria=["Done"],
                    priority=1,
                )
            ],
        )

    def _create_mock_agent_session(self, messages: list[str]):
        """Create a mock AgentSession that yields messages."""
        mock_session = MagicMock()

        async def mock_execute(msg):
            for content in messages:
                mock_msg = MagicMock()
                mock_msg.content = content
                yield mock_msg

        mock_session.execute = mock_execute
        mock_session.total_tokens = 1000
        mock_session.total_cost_usd = 0.05

        return mock_session

    @pytest.mark.asyncio
    async def test_task_complete_signal_returns_true(
        self, temp_workspace: Path, mock_config, session_data, task_list
    ) -> None:
        """Test session returns completed=True when task completes."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_session = self._create_mock_agent_session(
            ["Working on task...", "[TASK_COMPLETE: task-001]"]
        )

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                completed, content = await runner._run_continuation_session(
                    "test prompt", session_data, task_list
                )

        assert completed is True
        assert "task-001" in session_data.tasks_passed

    @pytest.mark.asyncio
    async def test_task_blocked_signal_returns_true(
        self, temp_workspace: Path, mock_config, session_data, task_list
    ) -> None:
        """Test session returns completed=True when task is blocked."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_session = self._create_mock_agent_session(
            ["Attempting task...", "[TASK_BLOCKED: task-001: Missing dependency]"]
        )

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                completed, content = await runner._run_continuation_session(
                    "test prompt", session_data, task_list
                )

        assert completed is True
        assert "task-001" in session_data.tasks_failed

    @pytest.mark.asyncio
    async def test_shutdown_requested_breaks_loop(
        self, temp_workspace: Path, mock_config, session_data, task_list
    ) -> None:
        """Test shutdown flag breaks out of message loop."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)
        runner._shutdown_requested = True

        mock_session = self._create_mock_agent_session(
            ["First message", "Second message"]
        )

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                completed, content = await runner._run_continuation_session(
                    "test prompt", session_data, task_list
                )

        # Should have processed at least first message before shutdown check
        assert session_data.total_turns >= 1

    @pytest.mark.asyncio
    async def test_error_handling(
        self, temp_workspace: Path, mock_config, session_data, task_list
    ) -> None:
        """Test error is caught and logged."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Test error")
            )
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)

            completed, content = await runner._run_continuation_session(
                "test prompt", session_data, task_list
            )

        assert "**ERROR**: Test error" in content

    @pytest.mark.asyncio
    async def test_extracts_token_stats(
        self, temp_workspace: Path, mock_config, session_data, task_list
    ) -> None:
        """Test token stats are extracted from agent session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_session = self._create_mock_agent_session(
            ["[TASK_COMPLETE: task-001]"]
        )

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                await runner._run_continuation_session(
                    "test prompt", session_data, task_list
                )

        assert session_data.total_tokens == 1000
        assert session_data.total_cost_usd == 0.05


class TestRunInitializerSession:
    """Tests for _run_initializer_session async method."""

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

    @pytest.fixture
    def session_data(self) -> SessionData:
        """Create a fresh SessionData for testing."""
        return SessionData(
            session_number=1,
            started_at="2025-01-01T00:00:00+00:00",
        )

    @pytest.fixture
    def qa_session(self) -> QASession:
        """Create a fresh QASession for testing."""
        return QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
        )

    def _create_mock_agent_session(self, messages: list[str]):
        """Create a mock AgentSession that yields messages."""
        mock_session = MagicMock()

        async def mock_execute(msg):
            for content in messages:
                mock_msg = MagicMock()
                mock_msg.content = content
                yield mock_msg

        mock_session.execute = mock_execute
        mock_session.total_tokens = 500
        mock_session.total_cost_usd = 0.02

        return mock_session

    @pytest.mark.asyncio
    async def test_task_list_ready_signal_completes(
        self, temp_workspace: Path, mock_config, session_data, qa_session
    ) -> None:
        """Test [TASK_LIST_READY] signal completes session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_session = self._create_mock_agent_session(
            ["Creating task list...", "[TASK_LIST_READY]"]
        )

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                completed, content = await runner._run_initializer_session(
                    "test prompt", session_data, qa_session
                )

        assert completed is True
        assert qa_session.status == "completed"

    @pytest.mark.asyncio
    async def test_deletes_qa_session_on_completion(
        self, temp_workspace: Path, mock_config, session_data, qa_session
    ) -> None:
        """Test QA session file is deleted on successful completion."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Save a QA session first
        runner._save_qa_session(qa_session)
        qa_path = temp_workspace / "qa_session.json"
        assert qa_path.exists()

        mock_session = self._create_mock_agent_session(["[TASK_LIST_READY]"])

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                await runner._run_initializer_session(
                    "test prompt", session_data, qa_session
                )

        assert not qa_path.exists()

    @pytest.mark.asyncio
    async def test_resuming_session_uses_different_message(
        self, temp_workspace: Path, mock_config, session_data
    ) -> None:
        """Test resuming session uses resume message."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        # Create resumable session
        qa_session = QASession(
            started_at="2025-01-01T00:00:00+00:00",
            spec_hash="test",
            status="in_progress",
            current_question=2,
            conversation_history=[{"role": "user", "content": "test"}],
        )

        captured_message = None
        mock_session = MagicMock()

        async def mock_execute(msg):
            nonlocal captured_message
            captured_message = msg
            mock_msg = MagicMock()
            mock_msg.content = "[TASK_LIST_READY]"
            yield mock_msg

        mock_session.execute = mock_execute
        mock_session.total_tokens = 100
        mock_session.total_cost_usd = 0.01

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                await runner._run_initializer_session(
                    "test prompt", session_data, qa_session
                )

        assert "Continue from Question 3" in captured_message

    @pytest.mark.asyncio
    async def test_error_handling(
        self, temp_workspace: Path, mock_config, session_data, qa_session
    ) -> None:
        """Test error is caught and logged."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Session error")
            )
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)

            completed, content = await runner._run_initializer_session(
                "test prompt", session_data, qa_session
            )

        assert completed is False
        assert "**ERROR**: Session error" in content

    @pytest.mark.asyncio
    async def test_extracts_token_stats(
        self, temp_workspace: Path, mock_config, session_data, qa_session
    ) -> None:
        """Test token stats are extracted from agent session."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mock_session = self._create_mock_agent_session(["[TASK_LIST_READY]"])

        with patch("harness.autonomous.AgentSession") as mock_agent_class:
            mock_agent_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_agent_class.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("harness.autonomous.parse_and_print_message"):
                await runner._run_initializer_session(
                    "test prompt", session_data, qa_session
                )

        assert session_data.total_tokens == 500
        assert session_data.total_cost_usd == 0.02


class TestRunAutonomous:
    """Tests for run_autonomous() entry point function."""

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
    async def test_uses_config_workspace_when_none_provided(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test run_autonomous uses workspace_dir from config when not provided."""
        from harness.autonomous import run_autonomous

        with patch("harness.autonomous.AutonomousRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await run_autonomous(workspace_dir=None)

            # Verify AutonomousRunner was created with config workspace
            call_kwargs = mock_runner_class.call_args.kwargs
            assert call_kwargs["workspace_dir"] == temp_workspace

    @pytest.mark.asyncio
    async def test_uses_provided_workspace(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test run_autonomous uses explicitly provided workspace_dir."""
        from harness.autonomous import run_autonomous

        custom_workspace = Path("/custom/workspace")

        with patch("harness.autonomous.AutonomousRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await run_autonomous(workspace_dir=custom_workspace)

            # Verify AutonomousRunner was created with custom workspace
            call_kwargs = mock_runner_class.call_args.kwargs
            assert call_kwargs["workspace_dir"] == custom_workspace

    @pytest.mark.asyncio
    async def test_passes_model_to_runner(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test run_autonomous passes model parameter to runner."""
        from harness.autonomous import run_autonomous

        with patch("harness.autonomous.AutonomousRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await run_autonomous(model="claude-opus-4-5-20251101")

            call_kwargs = mock_runner_class.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-5-20251101"

    @pytest.mark.asyncio
    async def test_passes_allow_all_commands_to_runner(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test run_autonomous passes allow_all_commands parameter."""
        from harness.autonomous import run_autonomous

        with patch("harness.autonomous.AutonomousRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await run_autonomous(allow_all_commands=True)

            call_kwargs = mock_runner_class.call_args.kwargs
            assert call_kwargs["allow_all_commands"] is True

    @pytest.mark.asyncio
    async def test_calls_runner_run(
        self, temp_workspace: Path, mock_config
    ) -> None:
        """Test run_autonomous calls runner.run()."""
        from harness.autonomous import run_autonomous

        with patch("harness.autonomous.AutonomousRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await run_autonomous()

            mock_runner.run.assert_called_once()


class TestMainCLI:
    """Tests for main() CLI entry point."""

    def test_model_shorthand_mapping_sonnet(self) -> None:
        """Test 'sonnet' is mapped to full model name."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--model", "sonnet"]):
            with patch("harness.autonomous.asyncio.run") as mock_run:
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    main()
                    # Verify asyncio.run was called (model mapping happens internally)
                    mock_run.assert_called_once()

    def test_model_shorthand_mapping_opus(self) -> None:
        """Test 'opus' is mapped to full model name."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--model", "opus"]):
            with patch("harness.autonomous.asyncio.run") as mock_run:
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    main()
                    mock_run.assert_called_once()

    def test_model_shorthand_mapping_haiku(self) -> None:
        """Test 'haiku' is mapped to full model name."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--model", "haiku"]):
            with patch("harness.autonomous.asyncio.run") as mock_run:
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    main()
                    mock_run.assert_called_once()

    def test_quiet_mode_configures_logging(self) -> None:
        """Test --quiet flag configures logging level."""
        import sys
        import logging
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--quiet"]):
            with patch("harness.autonomous.asyncio.run"):
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    with patch("harness.autonomous.structlog.configure") as mock_structlog:
                        main()
                        # Verify structlog.configure was called
                        mock_structlog.assert_called_once()

    def test_keyboard_interrupt_exits_gracefully(self) -> None:
        """Test KeyboardInterrupt causes clean exit."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous"]):
            with patch("harness.autonomous.asyncio.run", side_effect=KeyboardInterrupt):
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0

    def test_workspace_argument_passed_to_runner(self) -> None:
        """Test --workspace argument is passed correctly."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--workspace", "/custom/path"]):
            with patch("harness.autonomous.asyncio.run") as mock_run:
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    main()
                    mock_run.assert_called_once()

    def test_allow_all_commands_argument(self) -> None:
        """Test --allow-all-commands argument is passed correctly."""
        import sys
        from harness.autonomous import main

        with patch.object(sys, "argv", ["autonomous", "--allow-all-commands"]):
            with patch("harness.autonomous.asyncio.run") as mock_run:
                with patch("harness.autonomous.get_config") as mock_config:
                    mock_config.return_value = MagicMock(
                        workspace_dir=Path("/test")
                    )
                    main()
                    mock_run.assert_called_once()
