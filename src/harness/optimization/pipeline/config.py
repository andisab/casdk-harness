"""Pipeline configuration for optimization runs.

Defines the configuration needed to run an end-to-end optimization pipeline,
including paths, optimizer selection, and output settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from harness.optimization.optimizers import OptimizerType, OptimizationConfig


class OutputFormat(str, Enum):
    """Output format for optimization results."""

    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"


@dataclass
class PipelineConfig:
    """Configuration for an optimization pipeline run.

    Attributes:
        agent_path: Path to the agent definition file (.md with YAML frontmatter).
        test_suite_path: Path to the test suite file (YAML/JSON).
        optimizer_type: Which optimizer to use (dspy or textgrad).
        output_path: Path to write the optimized prompt (optional).
        output_format: Format for the output file.
        optimization_config: Optimizer-specific configuration.
        save_iterations: Whether to save intermediate iteration results.
        iterations_dir: Directory for iteration results (if save_iterations=True).
        verbose: Enable verbose logging.
        dry_run: Validate config without running optimization.
        metadata: Additional metadata for the run.
    """

    agent_path: str | Path
    test_suite_path: str | Path
    optimizer_type: OptimizerType = OptimizerType.DSPY
    output_path: str | Path | None = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    optimization_config: OptimizationConfig | None = None
    save_iterations: bool = False
    iterations_dir: str | Path | None = None
    verbose: bool = True
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize configuration."""
        # Ensure paths are Path objects
        self.agent_path = Path(self.agent_path)
        self.test_suite_path = Path(self.test_suite_path)

        if self.output_path is not None:
            self.output_path = Path(self.output_path)

        if self.iterations_dir is not None:
            self.iterations_dir = Path(self.iterations_dir)

        # Set default optimization config if not provided
        if self.optimization_config is None:
            self.optimization_config = OptimizationConfig()

        # Validate paths exist
        if not self.agent_path.exists():
            raise FileNotFoundError(f"Agent file not found: {self.agent_path}")

        if not self.test_suite_path.exists():
            raise FileNotFoundError(f"Test suite file not found: {self.test_suite_path}")

    def get_output_path(self) -> Path:
        """Get the output path, generating a default if not specified.

        Returns:
            Path for the output file.
        """
        if self.output_path is not None:
            return self.output_path

        # Generate default output path based on agent name and optimizer
        agent_name = self.agent_path.stem
        suffix = ".md" if self.output_format == OutputFormat.MARKDOWN else f".{self.output_format.value}"
        return Path(f"{agent_name}_optimized{suffix}")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization.

        Returns:
            Dictionary representation of the config.
        """
        return {
            "agent_path": str(self.agent_path),
            "test_suite_path": str(self.test_suite_path),
            "optimizer_type": self.optimizer_type.value,
            "output_path": str(self.output_path) if self.output_path else None,
            "output_format": self.output_format.value,
            "optimization_config": {
                "max_iterations": self.optimization_config.max_iterations,
                "early_stopping_threshold": self.optimization_config.early_stopping_threshold,
                "learning_rate": self.optimization_config.learning_rate,
                "num_candidates": self.optimization_config.num_candidates,
                "temperature": self.optimization_config.temperature,
                "seed": self.optimization_config.seed,
                "verbose": self.optimization_config.verbose,
            } if self.optimization_config else None,
            "save_iterations": self.save_iterations,
            "iterations_dir": str(self.iterations_dir) if self.iterations_dir else None,
            "verbose": self.verbose,
            "dry_run": self.dry_run,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary with config values.

        Returns:
            PipelineConfig instance.
        """
        opt_config_data = data.get("optimization_config")
        opt_config = None
        if opt_config_data:
            opt_config = OptimizationConfig(
                max_iterations=opt_config_data.get("max_iterations", 10),
                early_stopping_threshold=opt_config_data.get("early_stopping_threshold", 0.01),
                learning_rate=opt_config_data.get("learning_rate", 0.1),
                num_candidates=opt_config_data.get("num_candidates", 5),
                temperature=opt_config_data.get("temperature", 0.7),
                seed=opt_config_data.get("seed"),
                verbose=opt_config_data.get("verbose", True),
            )

        return cls(
            agent_path=data["agent_path"],
            test_suite_path=data["test_suite_path"],
            optimizer_type=OptimizerType(data.get("optimizer_type", "dspy")),
            output_path=data.get("output_path"),
            output_format=OutputFormat(data.get("output_format", "markdown")),
            optimization_config=opt_config,
            save_iterations=data.get("save_iterations", False),
            iterations_dir=data.get("iterations_dir"),
            verbose=data.get("verbose", True),
            dry_run=data.get("dry_run", False),
            metadata=data.get("metadata", {}),
        )
