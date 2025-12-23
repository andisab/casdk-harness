"""CGF Optimization Module.

Provides infrastructure for optimizing agents, skills, prompts, and commands
through execution tracing, evaluation, and reward-based feedback.

Core Components:
    - Store: Persistent storage for spans, resources, evaluations, and results
    - Resources: Wrapper types for optimizable resources
    - Adapters: Transform execution spans into structured feedback
    - Rewards: Multi-dimensional scoring system (Phase 0.5)

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
    reward = feedback.to_reward()
"""

from __future__ import annotations

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
]
