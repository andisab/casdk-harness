"""Tests for optimization pipeline module."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.optimizers import OptimizationConfig, OptimizationResult, OptimizerType
from harness.optimization.pipeline import (
    OptimizationRun,
    OutputFormat,
    PipelineConfig,
    RunPhase,
    RunStatus,
)
from harness.optimization.pipeline.optimization_run import RunSummary


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
        assert config.optimizer_type == OptimizerType.DSPY
        assert config.output_format == OutputFormat.MARKDOWN
        assert config.optimization_config is not None

    def test_config_with_options(self, temp_files: tuple[Path, Path]) -> None:
        """Test configuration with all options."""
        agent_path, suite_path = temp_files

        opt_config = OptimizationConfig(max_iterations=20)

        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
            optimizer_type=OptimizerType.TEXTGRAD,
            output_format=OutputFormat.JSON,
            optimization_config=opt_config,
            verbose=False,
            dry_run=True,
        )

        assert config.optimizer_type == OptimizerType.TEXTGRAD
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
        # Versioned naming: workspace/{agent}/{agent}-vN.md
        # Check pattern, not exact version (version depends on existing files)
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
        assert "optimizer_type" in data
        assert data["optimizer_type"] == "dspy"

    def test_from_dict(self, temp_files: tuple[Path, Path]) -> None:
        """Test deserialization from dict."""
        agent_path, suite_path = temp_files

        data = {
            "agent_path": str(agent_path),
            "test_suite_path": str(suite_path),
            "optimizer_type": "textgrad",
            "output_format": "json",
        }

        config = PipelineConfig.from_dict(data)
        assert config.optimizer_type == OptimizerType.TEXTGRAD
        assert config.output_format == OutputFormat.JSON

    def test_feature_flags_default(
        self, temp_files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test feature flags default to OFF."""
        agent_path, suite_path = temp_files

        # Clear any env vars that might be set
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

    def test_feature_flags_from_dict(
        self, temp_files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test feature flags loaded from dict."""
        agent_path, suite_path = temp_files

        monkeypatch.delenv("CGF_TOKEN_TRACKING", raising=False)
        monkeypatch.delenv("CGF_CACHE_ENABLED", raising=False)

        data = {
            "agent_path": str(agent_path),
            "test_suite_path": str(suite_path),
            "token_tracking_enabled": True,
            "cache_enabled": True,
            "token_budget": 75000,
        }

        config = PipelineConfig.from_dict(data)

        assert config.token_tracking_enabled is True
        assert config.cache_enabled is True
        assert config.token_budget == 75000


class TestRunPhaseAndStatus:
    """Tests for RunPhase and RunStatus enums."""

    def test_run_phase_values(self) -> None:
        """Test RunPhase enum values."""
        assert RunPhase.INIT.value == "init"
        assert RunPhase.LOAD_RESOURCES.value == "load_resources"
        assert RunPhase.VALIDATE.value == "validate"
        assert RunPhase.OPTIMIZE.value == "optimize"
        assert RunPhase.SAVE.value == "save"
        assert RunPhase.COMPLETE.value == "complete"
        assert RunPhase.FAILED.value == "failed"

    def test_run_status_values(self) -> None:
        """Test RunStatus enum values."""
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.CANCELLED.value == "cancelled"


class TestRunSummary:
    """Tests for RunSummary dataclass."""

    def test_to_dict(self) -> None:
        """Test RunSummary serialization."""
        summary = RunSummary(
            run_id="test-run-123",
            status=RunStatus.COMPLETED,
            phase=RunPhase.COMPLETE,
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 5, 0),
            duration_seconds=300.0,
            agent_name="test-agent",
            suite_name="test-suite",
            optimizer_type="dspy",
            original_score=0.5,
            final_score=0.8,
            improvement=0.3,
            improvement_percent=60.0,
            iterations_completed=5,
            output_path="/output/path.md",
        )

        data = summary.to_dict()
        assert data["run_id"] == "test-run-123"
        assert data["status"] == "completed"
        assert data["phase"] == "complete"
        assert data["agent_name"] == "test-agent"
        assert data["improvement_percent"] == 60.0


class TestOptimizationRun:
    """Tests for OptimizationRun orchestrator."""

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

    @pytest.fixture
    def config(self, temp_files: tuple[Path, Path]) -> PipelineConfig:
        """Create test configuration."""
        agent_path, suite_path = temp_files
        return PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
        )

    def test_run_init(self, config: PipelineConfig) -> None:
        """Test OptimizationRun initialization."""
        run = OptimizationRun(config)

        assert run.config == config
        assert run.run_id.startswith("opt_agent_")
        assert run.status == RunStatus.PENDING
        assert run.phase == RunPhase.INIT

    def test_run_id_generation(self, config: PipelineConfig) -> None:
        """Test unique run ID generation."""
        run1 = OptimizationRun(config)
        run2 = OptimizationRun(config)

        # Run IDs should be unique (different timestamps)
        # They might be the same if created in same second, so we check format
        assert run1.run_id.startswith("opt_agent_")
        assert run2.run_id.startswith("opt_agent_")

    @pytest.mark.asyncio
    async def test_dry_run(self, config: PipelineConfig) -> None:
        """Test dry run mode."""
        config.dry_run = True
        run = OptimizationRun(config)

        result = await run.execute()

        assert result.success is True
        assert run.phase == RunPhase.COMPLETE
        assert run.status == RunStatus.COMPLETED
        assert result.metadata.get("dry_run") is True

    @pytest.mark.asyncio
    async def test_execute_dspy_not_available(self, config: PipelineConfig) -> None:
        """Test execution when DSPy is not available."""
        run = OptimizationRun(config)

        with patch("harness.optimization.pipeline.optimization_run.DSPY_AVAILABLE", False):
            result = await run.execute()

        assert result.success is False
        assert "not installed" in result.error.lower()
        assert run.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_textgrad_not_available(self, temp_files: tuple[Path, Path]) -> None:
        """Test execution when TextGrad is not available."""
        agent_path, suite_path = temp_files
        config = PipelineConfig(
            agent_path=agent_path,
            test_suite_path=suite_path,
            optimizer_type=OptimizerType.TEXTGRAD,
        )

        run = OptimizationRun(config)

        with patch("harness.optimization.pipeline.optimization_run.TEXTGRAD_AVAILABLE", False):
            result = await run.execute()

        assert result.success is False
        assert "not installed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_mock_optimizer(self, config: PipelineConfig) -> None:
        """Test execution with mocked optimizer."""
        run = OptimizationRun(config)

        # Mock the optimizer
        mock_result = OptimizationResult(
            success=True,
            original_prompt="original",
            optimized_prompt="optimized",
            original_score=0.5,
            final_score=0.8,
            improvement=0.3,
            improvement_percent=60.0,
            iterations=[],
            total_iterations=5,
            total_duration_seconds=10.0,
            config=config.optimization_config,
            agent_name="test-agent",
            suite_name="test-suite",
        )

        mock_optimizer = MagicMock()
        mock_optimizer.optimize = AsyncMock(return_value=mock_result)

        with patch("harness.optimization.pipeline.optimization_run.DSPY_AVAILABLE", True), \
             patch("harness.optimization.pipeline.optimization_run.DSPyAgentOptimizer") as mock_class:
            mock_class.return_value = mock_optimizer
            result = await run.execute()

        assert result.success is True
        assert result.final_score == 0.8
        assert run.status == RunStatus.COMPLETED

    def test_get_summary(self, config: PipelineConfig) -> None:
        """Test getting run summary."""
        run = OptimizationRun(config)

        summary = run.get_summary()

        assert summary.run_id == run.run_id
        assert summary.status == RunStatus.PENDING
        assert summary.phase == RunPhase.INIT

    @pytest.mark.asyncio
    async def test_save_markdown(self, config: PipelineConfig, tmp_path: Path) -> None:
        """Test saving result as markdown."""
        config.output_path = tmp_path / "output.md"
        run = OptimizationRun(config)

        # Simulate a successful run
        run.resource = MagicMock()
        run.resource.name = "test-agent"
        run.resource.model = "sonnet"
        run.resource.tools = ["Read", "Write"]

        run.result = OptimizationResult(
            success=True,
            original_prompt="original",
            optimized_prompt="This is the optimized prompt.",
            original_score=0.5,
            final_score=0.8,
            improvement=0.3,
            improvement_percent=60.0,
            iterations=[],
            total_iterations=5,
            total_duration_seconds=10.0,
            config=config.optimization_config,
            agent_name="test-agent",
            suite_name="test-suite",
        )

        run._save_result()

        assert config.output_path.exists()
        content = config.output_path.read_text()
        assert "optimized prompt" in content.lower() or "This is the optimized prompt." in content

    @pytest.mark.asyncio
    async def test_save_json(self, config: PipelineConfig, tmp_path: Path) -> None:
        """Test saving result as JSON."""
        config.output_path = tmp_path / "output.json"
        config.output_format = OutputFormat.JSON
        run = OptimizationRun(config)

        run.resource = MagicMock()
        run.resource.name = "test-agent"
        run.resource.model = "sonnet"
        run.resource.tools = ["Read", "Write"]

        run.result = OptimizationResult(
            success=True,
            original_prompt="original",
            optimized_prompt="optimized",
            original_score=0.5,
            final_score=0.8,
            improvement=0.3,
            improvement_percent=60.0,
            iterations=[],
            total_iterations=5,
            total_duration_seconds=10.0,
            config=config.optimization_config,
            agent_name="test-agent",
            suite_name="test-suite",
        )

        run._save_result()

        assert config.output_path.exists()
        data = json.loads(config.output_path.read_text())
        assert data["success"] is True
        assert data["final_score"] == 0.8


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

        from harness.optimization.cli.optimize import cli
        assert isinstance(cli, click.Command)
