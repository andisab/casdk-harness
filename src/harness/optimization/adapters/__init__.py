"""CGF Adapter Framework.

Provides adapters for transforming execution spans into structured feedback
for resource optimization. Each resource type (agent, skill, prompt, command)
has a specialized adapter that extracts relevant metrics.

Usage:
    from harness.optimization.adapters import (
        AdapterRegistry,
        AgentAdapter,
        AgentFeedback,
        get_adapter,
    )

    # Get adapter by resource type
    adapter = get_adapter("agent")
    feedback = adapter.adapt(spans)

    # Or use the registry
    registry = AdapterRegistry()
    adapter = registry.get("agent")

    # Access feedback rewards
    reward = feedback.to_reward()
    print(f"Task completion: {reward['task_completion']}")

Training Data:
    from harness.optimization.adapters import TripletAdapter, TrainingTriplet

    triplet_adapter = TripletAdapter()
    triplets = triplet_adapter.create_comparison_triplets(
        good_spans=successful_trace,
        bad_spans=failed_trace,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from harness.optimization.adapters.agent_adapter import AgentAdapter, create_agent_adapter
from harness.optimization.adapters.base import (
    AdapterProtocol,
    AgentFeedback,
    BaseAdapter,
    BaseFeedback,
    CommandFeedback,
    PromptFeedback,
    SkillFeedback,
    TrainingTriplet,
)
from harness.optimization.adapters.command_adapter import (
    CommandAdapter,
    create_command_adapter,
)
from harness.optimization.adapters.prompt_adapter import (
    PromptAdapter,
    create_prompt_adapter,
)
from harness.optimization.adapters.skill_adapter import (
    SkillAdapter,
    create_skill_adapter,
)
from harness.optimization.adapters.triplet_adapter import (
    TripletAdapter,
    create_triplet_adapter,
)

if TYPE_CHECKING:
    from harness.tracer.base import Span

__all__ = [
    # Base types
    "AdapterProtocol",
    "BaseAdapter",
    "BaseFeedback",
    # Feedback types
    "AgentFeedback",
    "SkillFeedback",
    "PromptFeedback",
    "CommandFeedback",
    # Training data
    "TrainingTriplet",
    # Adapters
    "AgentAdapter",
    "SkillAdapter",
    "PromptAdapter",
    "CommandAdapter",
    "TripletAdapter",
    # Factory functions
    "create_agent_adapter",
    "create_skill_adapter",
    "create_prompt_adapter",
    "create_command_adapter",
    "create_triplet_adapter",
    # Registry
    "AdapterRegistry",
    "get_adapter",
    "get_default_registry",
]


# Type mapping for adapters
ADAPTER_TYPES: dict[str, type[BaseAdapter[Any]]] = {
    "agent": AgentAdapter,
    "skill": SkillAdapter,
    "prompt": PromptAdapter,
    "command": CommandAdapter,
}


@dataclass
class AdapterRegistry:
    """Registry for span-to-feedback adapters.

    Provides centralized access to adapters by resource type with
    caching for reuse.
    """

    _adapters: dict[str, BaseAdapter[Any]] = field(default_factory=dict)
    _triplet_adapter: TripletAdapter | None = None

    def get(self, resource_type: str) -> BaseAdapter[Any]:
        """Get an adapter for a resource type.

        Args:
            resource_type: Type of resource (agent, skill, prompt, command).

        Returns:
            Adapter instance.

        Raises:
            ValueError: If resource type is unknown.
        """
        if resource_type not in self._adapters:
            adapter_class = ADAPTER_TYPES.get(resource_type)
            if adapter_class is None:
                raise ValueError(
                    f"Unknown resource type: {resource_type}. "
                    f"Valid types: {list(ADAPTER_TYPES.keys())}"
                )
            self._adapters[resource_type] = adapter_class()

        return self._adapters[resource_type]

    def get_agent_adapter(self) -> AgentAdapter:
        """Get the agent adapter.

        Returns:
            AgentAdapter instance.
        """
        adapter = self.get("agent")
        assert isinstance(adapter, AgentAdapter)
        return adapter

    def get_skill_adapter(self) -> SkillAdapter:
        """Get the skill adapter.

        Returns:
            SkillAdapter instance.
        """
        adapter = self.get("skill")
        assert isinstance(adapter, SkillAdapter)
        return adapter

    def get_prompt_adapter(self) -> PromptAdapter:
        """Get the prompt adapter.

        Returns:
            PromptAdapter instance.
        """
        adapter = self.get("prompt")
        assert isinstance(adapter, PromptAdapter)
        return adapter

    def get_command_adapter(self) -> CommandAdapter:
        """Get the command adapter.

        Returns:
            CommandAdapter instance.
        """
        adapter = self.get("command")
        assert isinstance(adapter, CommandAdapter)
        return adapter

    def get_triplet_adapter(self) -> TripletAdapter:
        """Get the triplet adapter for training data generation.

        Returns:
            TripletAdapter instance.
        """
        if self._triplet_adapter is None:
            self._triplet_adapter = TripletAdapter()
        return self._triplet_adapter

    def adapt(
        self,
        resource_type: str,
        spans: list[Span],
    ) -> BaseFeedback:
        """Transform spans to feedback using the appropriate adapter.

        Args:
            resource_type: Type of resource.
            spans: Spans to transform.

        Returns:
            Feedback for the resource type.
        """
        adapter = self.get(resource_type)
        return adapter.adapt(spans)

    def adapt_all(
        self,
        spans_by_type: dict[str, list[Span]],
    ) -> dict[str, BaseFeedback]:
        """Transform multiple span lists to feedback.

        Args:
            spans_by_type: Dictionary mapping resource types to span lists.

        Returns:
            Dictionary mapping resource types to feedback.
        """
        results: dict[str, BaseFeedback] = {}

        for resource_type, spans in spans_by_type.items():
            if resource_type in ADAPTER_TYPES:
                results[resource_type] = self.adapt(resource_type, spans)

        return results

    def list_resource_types(self) -> list[str]:
        """List supported resource types.

        Returns:
            List of resource type names.
        """
        return list(ADAPTER_TYPES.keys())


# Global default registry
_default_registry: AdapterRegistry | None = None


def get_default_registry() -> AdapterRegistry:
    """Get the default adapter registry.

    Returns:
        Shared AdapterRegistry instance.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = AdapterRegistry()
    return _default_registry


def get_adapter(resource_type: str) -> BaseAdapter[Any]:
    """Get an adapter for a resource type from the default registry.

    Args:
        resource_type: Type of resource (agent, skill, prompt, command).

    Returns:
        Adapter instance.

    Raises:
        ValueError: If resource type is unknown.
    """
    return get_default_registry().get(resource_type)


def reset_default_registry() -> None:
    """Reset the default registry.

    Useful for testing.
    """
    global _default_registry
    _default_registry = None
