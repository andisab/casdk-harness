"""Pipeline module for optimization orchestration.

Provides configuration and parallel execution utilities for optimization runs.

Example usage:
    from harness.optimization.pipeline import PipelineConfig

    config = PipelineConfig(
        agent_path=".claude/agents/python-expert.md",
        test_suite_path="tests/optimization/python_expert_tests.yaml",
        output_path="optimized_prompt.md",
    )
"""

from harness.optimization.pipeline.config import (
    OutputFormat,
    PipelineConfig,
)
from harness.optimization.pipeline.parallel import (
    BatchResult,
    ParallelConfig,
    ParallelExecutor,
    TaskResult,
    batch_process,
    gather_with_concurrency,
)

__all__ = [
    # Config
    "PipelineConfig",
    "OutputFormat",
    # Parallel execution
    "ParallelConfig",
    "ParallelExecutor",
    "TaskResult",
    "BatchResult",
    "gather_with_concurrency",
    "batch_process",
]
