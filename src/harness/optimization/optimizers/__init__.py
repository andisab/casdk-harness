"""Optimization algorithms for agent prompt improvement.

This module provides optimizer implementations for improving agent system prompts
using various techniques including DSPy MIPROv2 and TextGrad.

Example usage:
    from harness.optimization.optimizers import (
        DSPyAgentOptimizer,
        OptimizationConfig,
        OptimizationResult,
    )
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuiteLoader

    # Load agent and test suite
    resource = AgentResource.load(Path("agents/configs/python-expert.md"))
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    # Configure optimization
    config = OptimizationConfig(
        max_iterations=10,
        num_candidates=5,
    )

    # Run optimization
    optimizer = DSPyAgentOptimizer()
    result = await optimizer.optimize(resource, suite, config)

    if result.success:
        print(f"Improved score: {result.final_score:.2f}")
        print(f"Improvement: {result.improvement_percent:.1f}%")

    # Save optimized prompt
    result.save("optimization_result.json")
"""

from harness.optimization.optimizers.metrics import (
    MetricFunction,
    MetricRegistry,
    aggregate_metrics,
    create_dspy_metric,
    create_suite_metric,
    execution_time_metric,
    get_metric,
    get_suite_metric,
    pass_fail_metric,
    register_metric,
    reward_composite_metric,
    suite_average_score,
    suite_composite_metric,
    suite_pass_rate,
    suite_weighted_score,
    validation_score_metric,
)
from harness.optimization.optimizers.protocol import (
    BaseOptimizer,
    IterationResult,
    OptimizationConfig,
    OptimizationResult,
    OptimizerProtocol,
    OptimizerType,
    PromptCandidate,
)

# Import DSPy optimizer (may fail if dspy not installed)
try:
    from harness.optimization.optimizers.dspy_optimizer import (
        DSPyAgentModule,
        DSPyAgentOptimizer,
        get_dspy_optimizer,
    )

    DSPY_AVAILABLE = True
except ImportError:
    DSPyAgentModule = None  # type: ignore
    DSPyAgentOptimizer = None  # type: ignore
    get_dspy_optimizer = None  # type: ignore
    DSPY_AVAILABLE = False

__all__ = [
    # Protocol and base types
    "OptimizerProtocol",
    "OptimizerType",
    "BaseOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "IterationResult",
    "PromptCandidate",
    # DSPy optimizer
    "DSPyAgentOptimizer",
    "DSPyAgentModule",
    "get_dspy_optimizer",
    "DSPY_AVAILABLE",
    # Metrics
    "MetricFunction",
    "MetricRegistry",
    "validation_score_metric",
    "pass_fail_metric",
    "execution_time_metric",
    "reward_composite_metric",
    "suite_average_score",
    "suite_pass_rate",
    "suite_weighted_score",
    "suite_composite_metric",
    "create_dspy_metric",
    "create_suite_metric",
    "aggregate_metrics",
    "get_metric",
    "get_suite_metric",
    "register_metric",
]
