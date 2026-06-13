"""Optimization algorithms for agent prompt improvement.

This module provides optimizer implementations for improving agent system prompts.

Agentic optimization (LLM self-critique based on research and conventions)
is the default and recommended approach.

Example usage:
    from harness.optimization.optimizers import (
        AgenticSectionOptimizer,
        AgenticOptimizationConfig,
        get_agentic_optimizer,
    )

    optimizer = get_agentic_optimizer()
    result = await optimizer.optimize_section(
        section_content="...",
        section=optimizable_section,
        criteria=eval_criteria,
    )
"""

# Agentic optimizer (always available)
from harness.optimization.optimizers.agentic_optimizer import (
    AgenticOptimizationConfig,
    AgenticOptimizationResult,
    AgenticSectionOptimizer,
    CritiqueResult,
    get_agentic_optimizer,
)
from harness.optimization.optimizers.metrics import (
    MetricFunction,
    MetricRegistry,
    aggregate_metrics,
    create_suite_metric,
    create_threshold_metric,
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
    PromptCandidate,
)

__all__ = [
    # Protocol and base types
    "OptimizerProtocol",
    "BaseOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "IterationResult",
    "PromptCandidate",
    # Agentic optimizer
    "AgenticSectionOptimizer",
    "AgenticOptimizationConfig",
    "AgenticOptimizationResult",
    "CritiqueResult",
    "get_agentic_optimizer",
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
    "create_threshold_metric",
    "create_suite_metric",
    "aggregate_metrics",
    "get_metric",
    "get_suite_metric",
    "register_metric",
]
