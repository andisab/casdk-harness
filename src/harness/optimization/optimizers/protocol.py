"""Optimizer protocol and base types.

Defines the interface for prompt optimization algorithms.

Example usage:
    from harness.optimization.optimizers import OptimizerProtocol, OptimizationConfig

    class MyOptimizer(OptimizerProtocol):
        async def optimize(
            self,
            resource: AgentResource,
            test_suite: TestSuite,
            config: OptimizationConfig,
        ) -> OptimizationResult:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import SuiteResult, TestSuite


class OptimizerType(str, Enum):
    """Supported optimizer types."""

    DSPY = "dspy"
    TEXTGRAD = "textgrad"


@dataclass
class OptimizationConfig:
    """Configuration for optimization runs.

    Attributes:
        max_iterations: Maximum optimization iterations.
        early_stopping_threshold: Stop if improvement is below this.
        learning_rate: Learning rate for gradient-based optimizers.
        num_candidates: Number of prompt candidates to generate.
        temperature: LLM temperature for generation.
        seed: Random seed for reproducibility.
        verbose: Whether to log detailed progress.
        metadata: Additional optimizer-specific configuration.
    """

    max_iterations: int = 10
    early_stopping_threshold: float = 0.01
    learning_rate: float = 0.1
    num_candidates: int = 5
    temperature: float = 0.7
    seed: int | None = None
    verbose: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptCandidate:
    """A candidate prompt generated during optimization.

    Attributes:
        prompt: The candidate prompt text.
        score: Evaluation score (0.0 - 1.0).
        iteration: Which iteration generated this candidate.
        metadata: Additional information about the candidate.
    """

    prompt: str
    score: float
    iteration: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationResult:
    """Results from a single optimization iteration.

    Attributes:
        iteration: Iteration number (0-indexed).
        best_prompt: Best prompt from this iteration.
        best_score: Score of the best prompt.
        candidates: All candidates evaluated.
        suite_result: Full test suite result for best candidate.
        improvement: Score improvement over previous iteration.
        duration_seconds: Time taken for this iteration.
    """

    iteration: int
    best_prompt: str
    best_score: float
    candidates: list[PromptCandidate]
    suite_result: SuiteResult | None = None
    improvement: float = 0.0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "best_prompt": self.best_prompt,
            "best_score": self.best_score,
            "candidates": [
                {"prompt": c.prompt[:100] + "..." if len(c.prompt) > 100 else c.prompt,
                 "score": c.score,
                 "iteration": c.iteration}
                for c in self.candidates
            ],
            "improvement": self.improvement,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class OptimizationResult:
    """Final result of an optimization run.

    Attributes:
        success: Whether optimization completed successfully.
        original_prompt: The starting prompt.
        optimized_prompt: The improved prompt.
        original_score: Score before optimization.
        final_score: Score after optimization.
        improvement: Absolute improvement in score.
        improvement_percent: Relative improvement percentage.
        iterations: Results from each iteration.
        total_iterations: Number of iterations run.
        total_duration_seconds: Total optimization time.
        config: Configuration used.
        agent_name: Name of the optimized agent.
        suite_name: Name of the test suite used.
        error: Error message if optimization failed.
        timestamp: When optimization completed.
    """

    success: bool
    original_prompt: str
    optimized_prompt: str
    original_score: float
    final_score: float
    improvement: float
    improvement_percent: float
    iterations: list[IterationResult]
    total_iterations: int
    total_duration_seconds: float
    config: OptimizationConfig
    agent_name: str
    suite_name: str
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "original_prompt": self.original_prompt,
            "optimized_prompt": self.optimized_prompt,
            "original_score": self.original_score,
            "final_score": self.final_score,
            "improvement": self.improvement,
            "improvement_percent": self.improvement_percent,
            "total_iterations": self.total_iterations,
            "total_duration_seconds": self.total_duration_seconds,
            "agent_name": self.agent_name,
            "suite_name": self.suite_name,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "config": {
                "max_iterations": self.config.max_iterations,
                "early_stopping_threshold": self.config.early_stopping_threshold,
                "num_candidates": self.config.num_candidates,
            },
            "iterations": [it.to_dict() for it in self.iterations],
        }

    def save(self, path: str) -> None:
        """Save result to JSON file.

        Args:
            path: Path to save the result.
        """
        import json
        from pathlib import Path

        Path(path).write_text(json.dumps(self.to_dict(), indent=2))


@runtime_checkable
class OptimizerProtocol(Protocol):
    """Protocol for prompt optimization algorithms.

    All optimizers must implement this interface.
    """

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
        config: OptimizationConfig | None = None,
    ) -> OptimizationResult:
        """Run optimization on an agent resource.

        Args:
            resource: The agent resource to optimize.
            test_suite: Test cases for evaluation.
            config: Optimization configuration.

        Returns:
            OptimizationResult with improved prompt.
        """
        ...

    async def evaluate(
        self,
        prompt: str,
        test_suite: TestSuite,
    ) -> tuple[float, SuiteResult]:
        """Evaluate a prompt against the test suite.

        Args:
            prompt: The system prompt to evaluate.
            test_suite: Test cases for evaluation.

        Returns:
            Tuple of (score, suite_result).
        """
        ...


class BaseOptimizer(ABC):
    """Base class for optimizers with common functionality.

    Provides shared utilities for optimization implementations.
    """

    def __init__(self, default_config: OptimizationConfig | None = None) -> None:
        """Initialize the optimizer.

        Args:
            default_config: Default configuration for optimization runs.
        """
        self._default_config = default_config or OptimizationConfig()

    def _get_config(self, config: OptimizationConfig | None) -> OptimizationConfig:
        """Get effective configuration.

        Args:
            config: Provided configuration or None.

        Returns:
            Effective configuration to use.
        """
        return config or self._default_config

    @abstractmethod
    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
        config: OptimizationConfig | None = None,
    ) -> OptimizationResult:
        """Run optimization on an agent resource.

        Args:
            resource: The agent resource to optimize.
            test_suite: Test cases for evaluation.
            config: Optimization configuration.

        Returns:
            OptimizationResult with improved prompt.
        """
        ...

    @abstractmethod
    async def evaluate(
        self,
        prompt: str,
        test_suite: TestSuite,
    ) -> tuple[float, SuiteResult]:
        """Evaluate a prompt against the test suite.

        Args:
            prompt: The system prompt to evaluate.
            test_suite: Test cases for evaluation.

        Returns:
            Tuple of (score, suite_result).
        """
        ...
