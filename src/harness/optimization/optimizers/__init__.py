"""Optimization algorithms for agent prompt improvement.

This module provides optimizer implementations for improving agent system prompts.

**Primary approach**: Agentic optimization (LLM self-critique based on research
and conventions). This is the default and recommended approach.

**Optional**: Programmatic optimization (DSPy MIPROv2, TextGrad) is available
but disabled by default. Set CGF_ENABLE_PROGRAMMATIC=true to enable.

Example usage:
    from harness.optimization.optimizers import (
        AgenticSectionOptimizer,
        AgenticOptimizationConfig,
        get_agentic_optimizer,
    )

    # Agentic optimization (default, recommended)
    optimizer = get_agentic_optimizer()
    result = await optimizer.optimize_section(
        section_content="...",
        section=optimizable_section,
        criteria=eval_criteria,
    )

    # Programmatic optimization (optional, requires CGF_ENABLE_PROGRAMMATIC=true)
    from harness.optimization.optimizers import get_mipro_optimizer, PROGRAMMATIC_ENABLED
    if PROGRAMMATIC_ENABLED:
        optimizer = get_mipro_optimizer()
        result = await optimizer.optimize(resource, suite, config)
"""

import os

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

# =============================================================================
# CONFIGURATION: Programmatic optimization is disabled by default
# =============================================================================
# Set CGF_ENABLE_PROGRAMMATIC=true to enable DSPy/TextGrad optimizers.
# Agentic optimization (LLM self-critique) is the default and recommended approach.
PROGRAMMATIC_ENABLED = os.environ.get("CGF_ENABLE_PROGRAMMATIC", "false").lower() == "true"

# =============================================================================
# AGENTIC OPTIMIZER (Primary - Always Available)
# =============================================================================
from harness.optimization.optimizers.agentic_optimizer import (
    AgenticSectionOptimizer,
    AgenticOptimizationConfig,
    AgenticOptimizationResult,
    CritiqueResult,
    get_agentic_optimizer,
)

# =============================================================================
# PROGRAMMATIC OPTIMIZERS (Optional - Disabled by Default)
# =============================================================================
# DSPy MIPROv2 optimizer (replaces legacy dspy_optimizer.py)
MIPRO_AVAILABLE = False
MIPROv2AgentOptimizer = None  # type: ignore
MIPROv2Config = None  # type: ignore
get_mipro_optimizer = None  # type: ignore

if PROGRAMMATIC_ENABLED:
    try:
        from harness.optimization.optimizers.dspy_mipro_optimizer import (
            MIPROv2AgentOptimizer,
            MIPROv2Config,
            get_mipro_optimizer,
        )
        MIPRO_AVAILABLE = True
    except ImportError:
        pass

# TextGrad TGD optimizer
TEXTGRAD_AVAILABLE = False
TextGradAgentOptimizer = None  # type: ignore
get_textgrad_optimizer = None  # type: ignore

if PROGRAMMATIC_ENABLED:
    try:
        from harness.optimization.optimizers.textgrad_optimizer import (
            TextGradAgentOptimizer,
            get_textgrad_optimizer,
        )
        TEXTGRAD_AVAILABLE = True
    except ImportError:
        pass

__all__ = [
    # Configuration
    "PROGRAMMATIC_ENABLED",
    # Protocol and base types
    "OptimizerProtocol",
    "OptimizerType",
    "BaseOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "IterationResult",
    "PromptCandidate",
    # Agentic optimizer (PRIMARY - always available)
    "AgenticSectionOptimizer",
    "AgenticOptimizationConfig",
    "AgenticOptimizationResult",
    "CritiqueResult",
    "get_agentic_optimizer",
    # MIPROv2 optimizer (optional, requires CGF_ENABLE_PROGRAMMATIC=true)
    "MIPROv2AgentOptimizer",
    "MIPROv2Config",
    "get_mipro_optimizer",
    "MIPRO_AVAILABLE",
    # TextGrad optimizer (optional, requires CGF_ENABLE_PROGRAMMATIC=true)
    "TextGradAgentOptimizer",
    "get_textgrad_optimizer",
    "TEXTGRAD_AVAILABLE",
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
