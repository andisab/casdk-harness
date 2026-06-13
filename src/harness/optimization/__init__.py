"""CGF Optimization Module.

Provides infrastructure for optimizing agents, skills, prompts, and commands
through execution tracing, evaluation, and reward-based feedback.

Core Components:
    - Store: Persistent storage for spans, resources, evaluations, and results
    - Resources: Wrapper types for optimizable resources
    - Adapters: Transform execution spans into structured feedback
    - Rewards: Multi-dimensional scoring system for optimization

Quick Start:
    from harness.optimization import get_store, ResourceRegistry

    # Get configured store
    store = get_store()

    # Discover all resources
    registry = ResourceRegistry.discover()
    agents = registry.list_agents()

    # Register a resource in the store
    version = store.register_resource("my-agent", "agent", content)

    # Queue for evaluation
    eval_id = store.enqueue_evaluation("my-agent", "agent", config)

    # Store results
    store.store_result(eval_id, "my-agent", {"accuracy": 0.9})

Adapters:
    from harness.optimization import get_adapter, AgentFeedback

    # Transform spans to feedback
    adapter = get_adapter("agent")
    feedback = adapter.adapt(spans)

    # Get reward dimensions
    reward_dict = feedback.to_reward()

Rewards:
    from harness.optimization import ResourceReward, create_reward

    # Create reward from feedback
    reward = ResourceReward.from_feedback(feedback)

    # Compute composite score
    score = reward.composite()

    # Compare rewards
    improvement = new_reward.improvement_over(baseline)
"""

from __future__ import annotations

# Re-export adapter components
from harness.optimization.adapters import (
    AdapterProtocol,
    AdapterRegistry,
    AgentAdapter,
    AgentFeedback,
    BaseFeedback,
    CommandAdapter,
    CommandFeedback,
    PromptAdapter,
    PromptFeedback,
    SkillAdapter,
    SkillFeedback,
    TrainingTriplet,
    TripletAdapter,
    get_adapter,
    get_default_registry,
)

# Re-export optimizer components
from harness.optimization.optimizers import (
    AgenticOptimizationConfig,
    AgenticOptimizationResult,
    # Agentic optimizer (primary)
    AgenticSectionOptimizer,
    # Protocol and base types
    BaseOptimizer,
    CritiqueResult,
    IterationResult,
    OptimizationConfig,
    OptimizationResult,
    OptimizerProtocol,
    PromptCandidate,
    get_agentic_optimizer,
    # Metrics
    suite_average_score,
    validation_score_metric,
)

# Re-export orchestration components
from harness.optimization.orchestrator import (
    OrchestrationResult,
    SectionOptimizationConfig,
    SectionOptimizer,
    SectionResult,
    run_section_optimization,
)

# Re-export pipeline components
from harness.optimization.pipeline import (
    OutputFormat,
    PipelineConfig,
)

# Re-export resource components
from harness.optimization.resources import (
    AgentResource,
    CommandResource,
    PromptResource,
    ResourceProtocol,
    ResourceRegistry,
    SkillResource,
    ValidationError,
)

# Re-export reward components
from harness.optimization.rewards import (
    DEFAULT_WEIGHTS,
    WEIGHT_PRESETS,
    ResourceReward,
    aggregate_rewards,
    compare_rewards,
    create_reward,
)

# Re-export runner components
from harness.optimization.runners import (
    AgentRunner,
    BaseRunner,
    BatchRunner,
    RunContext,
    RunnerConfig,
    RunnerProtocol,
)

# Re-export store components
from harness.optimization.store import (
    EvaluationResult,
    EvaluationStatus,
    EvaluationTask,
    MemoryOptimizationStore,
    OptimizationStore,
    Resource,
    ResourceType,
    ResourceVersion,
    StoreMetrics,
    get_store,
    reset_store,
)

# Re-export test case components
from harness.optimization.testcases import (
    SuiteResult,
    TestCase,
    TestResult,
    TestSuite,
    TestSuiteLoader,
    ValidationConfig,
    ValidationType,
)

__all__ = [
    # Store Factory
    "get_store",
    "reset_store",
    # Store Protocol
    "OptimizationStore",
    # Store Implementations
    "MemoryOptimizationStore",
    # Store Models
    "EvaluationTask",
    "EvaluationResult",
    "EvaluationStatus",
    "Resource",
    "ResourceVersion",
    "ResourceType",
    "StoreMetrics",
    # Resource Types
    "ResourceProtocol",
    "AgentResource",
    "SkillResource",
    "PromptResource",
    "CommandResource",
    "ValidationError",
    # Resource Registry
    "ResourceRegistry",
    # Adapter Protocol & Registry
    "AdapterProtocol",
    "AdapterRegistry",
    "get_adapter",
    "get_default_registry",
    # Adapters
    "AgentAdapter",
    "SkillAdapter",
    "PromptAdapter",
    "CommandAdapter",
    "TripletAdapter",
    # Feedback Types
    "BaseFeedback",
    "AgentFeedback",
    "SkillFeedback",
    "PromptFeedback",
    "CommandFeedback",
    # Training Data
    "TrainingTriplet",
    # Reward System
    "ResourceReward",
    "DEFAULT_WEIGHTS",
    "WEIGHT_PRESETS",
    "aggregate_rewards",
    "compare_rewards",
    "create_reward",
    # Test Cases
    "TestCase",
    "TestSuite",
    "TestResult",
    "SuiteResult",
    "ValidationConfig",
    "ValidationType",
    "TestSuiteLoader",
    # Runners
    "RunnerProtocol",
    "BaseRunner",
    "RunnerConfig",
    "RunContext",
    "AgentRunner",
    "BatchRunner",
    # Optimizers - Protocol and base types
    "OptimizerProtocol",
    "BaseOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "IterationResult",
    "PromptCandidate",
    # Optimizers - Agentic (primary)
    "AgenticSectionOptimizer",
    "AgenticOptimizationConfig",
    "AgenticOptimizationResult",
    "CritiqueResult",
    "get_agentic_optimizer",
    # Metrics
    "validation_score_metric",
    "suite_average_score",
    # Pipeline
    "PipelineConfig",
    "OutputFormat",
    # Orchestration
    "SectionOptimizationConfig",
    "SectionOptimizer",
    "SectionResult",
    "OrchestrationResult",
    "run_section_optimization",
]
