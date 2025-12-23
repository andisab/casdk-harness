"""CGF Optimization Module.

Provides infrastructure for optimizing agents, skills, prompts, and commands
through execution tracing, evaluation, and reward-based feedback.

Core Components:
    - Store: Persistent storage for spans, resources, evaluations, and results
    - Resources: Wrapper types for optimizable resources (Phase 0.3)
    - Adapters: Transform execution spans into structured feedback (Phase 0.4)
    - Rewards: Multi-dimensional scoring system (Phase 0.5)

Quick Start:
    from harness.optimization import get_store

    # Get configured store
    store = get_store()

    # Register a resource
    version = store.register_resource("my-agent", "agent", content)

    # Queue for evaluation
    eval_id = store.enqueue_evaluation("my-agent", "agent", config)

    # Store results
    store.store_result(eval_id, "my-agent", {"accuracy": 0.9})
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

__all__ = [
    # Factory
    "get_store",
    "reset_store",
    # Protocol
    "OptimizationStore",
    # Implementations
    "MemoryOptimizationStore",
    # Models
    "EvaluationTask",
    "EvaluationResult",
    "EvaluationStatus",
    "Resource",
    "ResourceVersion",
    "ResourceType",
    "StoreMetrics",
]
