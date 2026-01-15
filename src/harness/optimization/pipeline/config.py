"""Pipeline configuration for optimization runs.

Defines the configuration needed to run an end-to-end optimization pipeline,
including paths, optimizer selection, and output settings.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from harness.optimization.optimizers import OptimizationConfig, OptimizerType


def _env_bool(key: str, default: bool = False) -> bool:
    """Read a boolean from environment variable.

    Accepts: true, 1, yes, on (case-insensitive) as True.
    """
    val = os.environ.get(key, "").lower()
    if not val:
        return default
    return val in ("true", "1", "yes", "on")


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
        token_tracking_enabled: Enable token usage tracking (env: CGF_TOKEN_TRACKING).
        cache_enabled: Enable caching for repeated runs (env: CGF_CACHE_ENABLED).
        token_budget: Max tokens allowed (0 = unlimited).

    Environment Variables:
        CGF_TOKEN_TRACKING: Enable token tracking (default: false)
        CGF_CACHE_ENABLED: Enable result caching (default: false)
        CGF_TOKEN_BUDGET: Max token budget, 0 = unlimited (default: 0)
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
    # Feature flags - default OFF for initial testing
    token_tracking_enabled: bool = field(
        default_factory=lambda: _env_bool("CGF_TOKEN_TRACKING", default=False)
    )
    cache_enabled: bool = field(
        default_factory=lambda: _env_bool("CGF_CACHE_ENABLED", default=False)
    )
    token_budget: int = field(
        default_factory=lambda: int(os.environ.get("CGF_TOKEN_BUDGET", "0"))
    )

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
        """Get the output path, defaulting to workspace/{agent}/{agent}-vN.md.

        Uses versioned naming: {agent}-v1.md, {agent}-v2.md, etc.
        Finds the next available version number in the workspace directory.

        Returns:
            Path for the output file.
        """
        if self.output_path is not None:
            # After __post_init__, output_path is always a Path
            return Path(self.output_path)

        # Default to workspace/{agent_name}/{agent_name}-vN.{ext}
        agent_name = Path(self.agent_path).stem
        workspace_dir = Path("workspace") / agent_name
        workspace_dir.mkdir(parents=True, exist_ok=True)

        suffix = ".md" if self.output_format == OutputFormat.MARKDOWN else f".{self.output_format.value}"

        # Find next version number
        next_version = self._get_next_version(workspace_dir, agent_name, suffix)
        return workspace_dir / f"{agent_name}-v{next_version}{suffix}"

    def _get_next_version(self, workspace_dir: Path, agent_name: str, suffix: str) -> int:
        """Find the next available version number in workspace directory.

        Args:
            workspace_dir: Directory to search for existing versions.
            agent_name: Base name of the agent.
            suffix: File extension (e.g., '.md').

        Returns:
            Next available version number (starts at 1).
        """
        pattern = re.compile(rf"^{re.escape(agent_name)}-v(\d+){re.escape(suffix)}$")
        max_version = 0

        if workspace_dir.exists():
            for file in workspace_dir.iterdir():
                match = pattern.match(file.name)
                if match:
                    version = int(match.group(1))
                    max_version = max(max_version, version)

        return max_version + 1

    def get_iterations_dir(self) -> Path | None:
        """Get iterations directory, defaulting to sibling of output.

        Returns:
            Path for iterations directory, or None if save_iterations is False.
        """
        if not self.save_iterations:
            return None
        if self.iterations_dir is not None:
            # After __post_init__, iterations_dir is always a Path
            return Path(self.iterations_dir)
        return self.get_output_path().parent / "iterations"

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
            "iterations_dir": (
                str(self.iterations_dir) if self.iterations_dir else None
            ),
            "verbose": self.verbose,
            "dry_run": self.dry_run,
            "metadata": self.metadata,
            # Feature flags
            "token_tracking_enabled": self.token_tracking_enabled,
            "cache_enabled": self.cache_enabled,
            "token_budget": self.token_budget,
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
            # Feature flags - use env defaults if not in dict
            token_tracking_enabled=data.get(
                "token_tracking_enabled",
                _env_bool("CGF_TOKEN_TRACKING", False),
            ),
            cache_enabled=data.get(
                "cache_enabled",
                _env_bool("CGF_CACHE_ENABLED", False),
            ),
            token_budget=data.get(
                "token_budget",
                int(os.environ.get("CGF_TOKEN_BUDGET", "0")),
            ),
        )
