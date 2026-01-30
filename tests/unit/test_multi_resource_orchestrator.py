"""Unit tests for multi_resource_orchestrator module.

Tests the pipeline improvements:
- Path validation and enforcement
- Versioned path generation
- Signal parsing
- Resource-specific instructions
- Configuration options
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.optimization.multi_resource_orchestrator import (
    DEFAULT_MAX_REFINEMENT,
    MultiResourceConfig,
    PathViolationError,
    _versioned_path,
    validate_write_path,
)


class TestValidateWritePath:
    """Tests for validate_write_path function."""

    def test_path_inside_workspace_passes(self, tmp_path: Path) -> None:
        """Path inside workspace should not raise."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = workspace / "agents" / "foo.md"

        # Should not raise
        validate_write_path(target, workspace)

    def test_path_outside_workspace_raises(self, tmp_path: Path) -> None:
        """Path outside workspace should raise PathViolationError."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = Path("/etc/passwd")

        with pytest.raises(PathViolationError) as exc_info:
            validate_write_path(target, workspace)

        assert "outside workspace" in str(exc_info.value)

    def test_relative_path_resolved_correctly(self, tmp_path: Path) -> None:
        """Relative paths should be resolved before validation."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # This relative path escapes workspace
        target = workspace / ".." / "outside.md"

        with pytest.raises(PathViolationError):
            validate_write_path(target, workspace)

    def test_nested_path_inside_workspace(self, tmp_path: Path) -> None:
        """Deeply nested path inside workspace should pass."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = workspace / "a" / "b" / "c" / "d" / "file.md"

        # Should not raise
        validate_write_path(target, workspace)

    def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        """Symlinks that escape workspace should be blocked."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()

        # Create symlink inside workspace pointing outside
        link = workspace / "escape_link"
        link.symlink_to(outside)

        target = link / "file.md"

        with pytest.raises(PathViolationError):
            validate_write_path(target, workspace)


class TestVersionedPath:
    """Tests for _versioned_path function."""

    def test_preserves_parent_directory(self) -> None:
        """Versioned path should preserve parent directory."""
        result = _versioned_path("agents/foo.md", 1)
        assert result == Path("agents/foo-v1.md")

    def test_handles_nested_paths(self) -> None:
        """Should handle deeply nested paths."""
        result = _versioned_path("skills/kubernetes-native/SKILL.md", 3)
        assert result == Path("skills/kubernetes-native/SKILL-v3.md")

    def test_version_zero(self) -> None:
        """Should handle version 0 (original backup)."""
        result = _versioned_path("commands/iac.md", 0)
        assert result == Path("commands/iac-v0.md")

    def test_path_object_input(self) -> None:
        """Should accept Path object as input."""
        result = _versioned_path(Path("agents/foo.md"), 2)
        assert result == Path("agents/foo-v2.md")

    def test_preserves_extension(self) -> None:
        """Should preserve file extension."""
        result = _versioned_path("config/settings.yaml", 1)
        assert result == Path("config/settings-v1.yaml")


class TestParseIterationResult:
    """Tests for _parse_iteration_result method."""

    @pytest.fixture
    def orchestrator(self, tmp_path: Path) -> MagicMock:
        """Create a mock orchestrator with the parse method."""
        # Import the actual method
        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceOrchestrator,
        )

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orch = MultiResourceOrchestrator(config)
        return orch

    def test_parses_quality_overall_pattern(self, orchestrator: MagicMock) -> None:
        """Should parse quality_overall: X.XX pattern."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        quality_overall: 0.87
        word_count: 500
        """
        result = orchestrator._parse_iteration_result(response)
        assert result["quality_overall"] == 0.87

    def test_parses_quality_pattern(self, orchestrator: MagicMock) -> None:
        """Should parse quality: X.XX pattern (fallback)."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        quality: 0.92
        """
        result = orchestrator._parse_iteration_result(response)
        assert result["quality_overall"] == 0.92

    def test_parses_score_pattern(self, orchestrator: MagicMock) -> None:
        """Should parse score: X.XX pattern (fallback)."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        score: 0.85
        """
        result = orchestrator._parse_iteration_result(response)
        assert result["quality_overall"] == 0.85

    def test_parses_overall_score_pattern(self, orchestrator: MagicMock) -> None:
        """Should parse overall_score: X.XX pattern (fallback)."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        overall_score: 0.88
        """
        result = orchestrator._parse_iteration_result(response)
        assert result["quality_overall"] == 0.88

    def test_ignores_invalid_quality_scores(self, orchestrator: MagicMock) -> None:
        """Should ignore quality scores outside 0.0-1.0 range."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        quality: 1.5
        score: 0.85
        """
        result = orchestrator._parse_iteration_result(response)
        # Should use score: 0.85 since quality: 1.5 is invalid
        assert result["quality_overall"] == 0.85

    def test_parses_word_count(self, orchestrator: MagicMock) -> None:
        """Should parse word_count: XXX pattern."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        quality_overall: 0.87
        word_count: 1234
        """
        result = orchestrator._parse_iteration_result(response)
        assert result["word_count"] == 1234

    def test_parses_summary_block(self, orchestrator: MagicMock) -> None:
        """Should parse [SUMMARY]...[/SUMMARY] block."""
        response = """
        [ITERATE_COMPLETE:agents/foo.md]
        quality_overall: 0.87
        [SUMMARY]
        Added better error handling and examples.
        [/SUMMARY]
        """
        result = orchestrator._parse_iteration_result(response)
        assert "error handling" in result["summary"]

    def test_handles_missing_fields(self, orchestrator: MagicMock) -> None:
        """Should handle missing fields gracefully."""
        response = "[ITERATE_COMPLETE:agents/foo.md]"
        result = orchestrator._parse_iteration_result(response)
        assert result["quality_overall"] is None
        assert result["word_count"] is None
        assert result["summary"] is None


class TestGetResourceInstructions:
    """Tests for _get_resource_instructions method."""

    @pytest.fixture
    def orchestrator(self, tmp_path: Path) -> MagicMock:
        """Create a mock orchestrator."""
        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceOrchestrator,
        )

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orch = MultiResourceOrchestrator(config)
        return orch

    def test_skill_instructions_include_trigger_terms(
        self, orchestrator: MagicMock
    ) -> None:
        """Skill instructions should mention trigger terms."""
        result = orchestrator._get_resource_instructions(
            "kubernetes-native", "skill", "K8s patterns"
        )
        assert "trigger" in result.lower()
        assert "SKILL.md" in result

    def test_skill_instructions_include_progressive_disclosure(
        self, orchestrator: MagicMock
    ) -> None:
        """Skill instructions should mention progressive disclosure."""
        result = orchestrator._get_resource_instructions(
            "terraform-modules", "skill", "Terraform patterns"
        )
        assert "examples/" in result or "templates/" in result

    def test_agent_instructions_include_tools(self, orchestrator: MagicMock) -> None:
        """Agent instructions should mention tool access."""
        result = orchestrator._get_resource_instructions(
            "iac-analyzer", "agent", "Repository analysis"
        )
        assert "tool" in result.lower()

    def test_agent_instructions_include_examples(
        self, orchestrator: MagicMock
    ) -> None:
        """Agent instructions should mention examples."""
        result = orchestrator._get_resource_instructions(
            "iac-generator", "agent", "Resource generation"
        )
        assert "example" in result.lower()

    def test_command_instructions_include_arguments(
        self, orchestrator: MagicMock
    ) -> None:
        """Command instructions should mention arguments."""
        result = orchestrator._get_resource_instructions(
            "iac", "command", "IaC operations"
        )
        assert "argument" in result.lower() or "$" in result

    def test_unknown_type_returns_empty(self, orchestrator: MagicMock) -> None:
        """Unknown resource type should return empty string."""
        result = orchestrator._get_resource_instructions(
            "foo", "unknown_type", "Some purpose"
        )
        assert result == ""


class TestMultiResourceConfig:
    """Tests for MultiResourceConfig dataclass."""

    def test_accepts_progress_callback(self, tmp_path: Path) -> None:
        """Config should accept progress_callback."""
        callback_called = []

        def my_callback(phase: str, resource: str, msg: str) -> None:
            callback_called.append((phase, resource, msg))

        config = MultiResourceConfig(
            workspace_dir=tmp_path,
            progress_callback=my_callback,
        )

        assert config.progress_callback is not None
        config.progress_callback("TEST", "resource.md", "test message")
        assert len(callback_called) == 1

    def test_skip_refinement_defaults_false(self, tmp_path: Path) -> None:
        """skip_refinement should default to False."""
        config = MultiResourceConfig(workspace_dir=tmp_path)
        assert config.skip_refinement is False

    def test_skip_refinement_can_be_set(self, tmp_path: Path) -> None:
        """skip_refinement should be settable."""
        config = MultiResourceConfig(
            workspace_dir=tmp_path,
            skip_refinement=True,
        )
        assert config.skip_refinement is True

    def test_max_refinements_default(self, tmp_path: Path) -> None:
        """max_refinements should default to DEFAULT_MAX_REFINEMENT (1)."""
        config = MultiResourceConfig(workspace_dir=tmp_path)
        assert config.max_refinements == DEFAULT_MAX_REFINEMENT
        assert config.max_refinements == 1  # Verify it's 1, not 3

    def test_default_values(self, tmp_path: Path) -> None:
        """Verify all default values."""
        config = MultiResourceConfig(workspace_dir=tmp_path)

        assert config.quality_threshold == 0.85
        assert config.max_iterations == 5
        assert config.max_refinements == 1
        assert config.verbose is False
        assert config.skip_research is False
        assert config.skip_qa is False
        assert config.skip_refinement is False
        assert config.eval_model is None
        assert config.parallel_generation is True
        assert config.progress_callback is None


class TestEmitProgress:
    """Tests for _emit_progress method."""

    @pytest.fixture
    def orchestrator_with_callback(self, tmp_path: Path):
        """Create orchestrator with progress callback."""
        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceOrchestrator,
        )

        progress_log = []

        def callback(phase: str, resource: str, msg: str) -> None:
            progress_log.append({"phase": phase, "resource": resource, "msg": msg})

        config = MultiResourceConfig(
            workspace_dir=tmp_path,
            progress_callback=callback,
        )
        orch = MultiResourceOrchestrator(config)
        return orch, progress_log

    def test_emit_progress_calls_callback(self, orchestrator_with_callback) -> None:
        """_emit_progress should call the configured callback."""
        orch, log = orchestrator_with_callback

        orch._emit_progress("GENERATE", "agents/foo.md", "in_progress")

        assert len(log) == 1
        assert log[0]["phase"] == "GENERATE"
        assert log[0]["resource"] == "agents/foo.md"
        assert "in_progress" in log[0]["msg"]

    def test_emit_progress_includes_quality(self, orchestrator_with_callback) -> None:
        """_emit_progress should include quality score when provided."""
        orch, log = orchestrator_with_callback

        orch._emit_progress("ITERATE", "agents/foo.md", "complete", quality=0.92)

        assert len(log) == 1
        assert "0.92" in log[0]["msg"]

    def test_emit_progress_no_callback(self, tmp_path: Path) -> None:
        """_emit_progress should not fail without callback."""
        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceOrchestrator,
        )

        config = MultiResourceConfig(workspace_dir=tmp_path)
        orch = MultiResourceOrchestrator(config)

        # Should not raise
        orch._emit_progress("GENERATE", "agents/foo.md", "in_progress")
