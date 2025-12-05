"""Unit tests for autonomous development mode."""

import tempfile
from pathlib import Path

import pytest

from harness.autonomous import AutonomousRunner, load_prompt


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

    def test_runner_initialization(self, temp_workspace: Path) -> None:
        """Test runner initializes correctly."""
        runner = AutonomousRunner(
            workspace_dir=temp_workspace,
            model="sonnet",
        )

        assert runner.workspace_dir == temp_workspace
        assert runner.model == "sonnet"
        assert runner._shutdown_requested is False

    def test_get_mode_no_task_list(self, temp_workspace: Path) -> None:
        """Test mode detection with no task list."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mode = runner._get_mode()
        assert mode == "initializer"

    def test_get_mode_with_task_list(self, temp_workspace: Path) -> None:
        """Test mode detection with existing task list."""
        # Create a task list file
        task_list_path = temp_workspace / "task_list.json"
        task_list_path.write_text('{"version": "1.0", "tasks": []}')

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        mode = runner._get_mode()
        assert mode == "continuation"

    def test_build_initializer_prompt_no_spec(self, temp_workspace: Path) -> None:
        """Test building initializer prompt without SPEC.md."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        prompt = runner._build_initializer_prompt()

        assert "No SPEC.md found" in prompt
        assert "Tech Lead" in prompt

    def test_build_initializer_prompt_with_spec(self, temp_workspace: Path) -> None:
        """Test building initializer prompt with SPEC.md."""
        # Create a spec file
        spec_path = temp_workspace / "SPEC.md"
        spec_path.write_text("# My Project\n\nTest specification content.")

        runner = AutonomousRunner(workspace_dir=temp_workspace)

        prompt = runner._build_initializer_prompt()

        assert "My Project" in prompt
        assert "Test specification content" in prompt

    def test_signal_handler_sets_shutdown_flag(self, temp_workspace: Path) -> None:
        """Test signal handler sets shutdown flag."""
        runner = AutonomousRunner(workspace_dir=temp_workspace)

        assert runner._shutdown_requested is False

        # Simulate signal (we pass None for frame as we don't use it)
        runner._signal_handler(2, None)  # SIGINT = 2

        assert runner._shutdown_requested is True

    def test_init_context_directory_creates_files(self, temp_workspace: Path) -> None:
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
        self, temp_workspace: Path
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

    def test_init_context_directory_file_format(self, temp_workspace: Path) -> None:
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
