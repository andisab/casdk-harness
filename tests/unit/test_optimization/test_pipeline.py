"""Tests for optimization pipeline module."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.optimization.optimizers import OptimizationConfig
from harness.optimization.pipeline import (
    OutputFormat,
    PipelineConfig,
)


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_values(self) -> None:
        """Test enum values."""
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.YAML.value == "yaml"


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    @pytest.fixture
    def temp_files(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create temporary agent and test suite files."""
        agent_path = tmp_path / "agent.md"
        agent_path.write_text("""---
name: test-agent
description: Test agent
model: sonnet
tools: []
---
You are a test agent.
""")

        suite_path = tmp_path / "suite.yaml"
        suite_path.write_text("""
name: test-suite
agent_name: test-agent
test_cases:
  - id: test-1
    prompt: "Test prompt"
    expected_behavior: "Test behavior"
    validation:
      type: contains
      criteria: "test"
""")

        return agent_path, suite_path

    def test_basic_config(self, temp_files: tuple[Path, Path]) -> None:
        """Test basic configuration creation."""
        agent_path, suite_path = temp_files

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

        assert config.agent_path == agent_path
        assert config.test_suite_path == suite_path
        assert config.output_format == OutputFormat.MARKDOWN
        assert config.optimization_config is not None

    def test_config_with_options(self, temp_files: tuple[Path, Path]) -> None:
        """Test configuration with all options."""
        agent_path, suite_path = temp_files

        opt_config = OptimizationConfig(max_iterations=20)

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
            output_format=OutputFormat.JSON,
            optimization_config=opt_config,
            verbose=False,
            dry_run=True,
        )

        assert config.output_format == OutputFormat.JSON
        assert config.optimization_config.max_iterations == 20
        assert config.verbose is False
        assert config.dry_run is True

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test error when files don't exist."""
        with pytest.raises(FileNotFoundError, match="Agent file not found"):
            PipelineConfig(
                agent_path=tmp_path / "nonexistent.md",
                test_suite_path=tmp_path / "suite.yaml",
            )

    def test_get_output_path_default(self, temp_files: tuple[Path, Path]) -> None:
        """Test default output path generation with versioned naming."""
        agent_path, suite_path = temp_files

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

        output_path = config.get_output_path()
        import re
        assert re.match(r"agent-v\d+\.md", output_path.name), f"Expected versioned name, got {output_path.name}"
        assert output_path.parent.name == "agent"
        assert output_path.parent.parent.name == "workspace"

    def test_get_output_path_custom(self, temp_files: tuple[Path, Path]) -> None:
        """Test custom output path."""
        agent_path, suite_path = temp_files

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
            output_path=Path("/custom/output.md"),
        )

        assert config.get_output_path() == Path("/custom/output.md")

    def test_to_dict(self, temp_files: tuple[Path, Path]) -> None:
        """Test serialization to dict."""
        agent_path, suite_path = temp_files

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

        data = config.to_dict()
        assert "agent_path" in data
        assert "test_suite_path" in data

    def test_feature_flags_default(
        self, temp_files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test feature flags default to OFF."""
        agent_path, suite_path = temp_files

        monkeypatch.delenv("CGF_TOKEN_TRACKING", raising=False)
        monkeypatch.delenv("CGF_CACHE_ENABLED", raising=False)
        monkeypatch.delenv("CGF_TOKEN_BUDGET", raising=False)

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

        assert config.token_tracking_enabled is False
        assert config.cache_enabled is False
        assert config.token_budget == 0

    def test_feature_flags_from_env(
        self, temp_files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test feature flags read from environment."""
        agent_path, suite_path = temp_files

        monkeypatch.setenv("CGF_TOKEN_TRACKING", "true")
        monkeypatch.setenv("CGF_CACHE_ENABLED", "1")
        monkeypatch.setenv("CGF_TOKEN_BUDGET", "100000")

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

        assert config.token_tracking_enabled is True
        assert config.cache_enabled is True
        assert config.token_budget == 100000

    def test_feature_flags_in_to_dict(
        self, temp_files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test feature flags included in to_dict."""
        agent_path, suite_path = temp_files

        monkeypatch.delenv("CGF_TOKEN_TRACKING", raising=False)
        monkeypatch.delenv("CGF_CACHE_ENABLED", raising=False)

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
            token_tracking_enabled=True,
            cache_enabled=True,
            token_budget=50000,
        )

        data = config.to_dict()

        assert data["token_tracking_enabled"] is True
        assert data["cache_enabled"] is True
        assert data["token_budget"] == 50000


class TestCLIImports:
    """Tests for CLI module imports."""

    def test_cli_imports(self) -> None:
        """Test that CLI module can be imported."""
        from harness.optimization.cli import cli, main
        assert cli is not None
        assert main is not None

    def test_cli_function_exists(self) -> None:
        """Test that CLI function is a Click command."""
        import click

        from harness.optimization.cli.section_optimize import cli
        assert isinstance(cli, click.Command)
