"""Pipeline module for end-to-end optimization orchestration.

Provides the OptimizationRun orchestrator that ties together resource loading,
test suite execution, and optimizer invocation.

Example usage:
    from harness.optimization.pipeline import OptimizationRun, PipelineConfig

    config = PipelineConfig(
        agent_path="agents/configs/python-expert.md",
        test_suite_path="tests/optimization/python_expert_tests.yaml",
        optimizer_type="dspy",
        output_path="optimized_prompt.md",
    )

    run = OptimizationRun(config)
    result = await run.execute()

    if result.success:
        print(f"Improvement: {result.improvement_percent:.1f}%")
"""

from harness.optimization.pipeline.config import (
    OutputFormat,
    PipelineConfig,
)
from harness.optimization.pipeline.optimization_run import (
    OptimizationRun,
    RunPhase,
    RunStatus,
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
    # Orchestrator
    "OptimizationRun",
    "RunPhase",
    "RunStatus",
    # Parallel execution
    "ParallelConfig",
    "ParallelExecutor",
    "TaskResult",
    "BatchResult",
    "gather_with_concurrency",
    "batch_process",
]
