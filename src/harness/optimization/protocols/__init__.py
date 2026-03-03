"""Signal protocol module for multi-resource optimization pipeline.

Provides a unified parser for structured agent signals, replacing scattered
regex patterns throughout the orchestrator with a single, testable protocol.

Usage:
    from harness.optimization.protocols import Signal, SignalParser, SignalType

    parser = SignalParser()
    signals = parser.parse(agent_response)

    for signal in signals:
        if signal.type == SignalType.GENERATE_COMPLETE:
            path = signal.resource_path
            word_count = signal.metadata.get("word_count")

Resource type registry:
    from harness.optimization.protocols import (
        ResourceType,
        ResourceTypeConfig,
        ResourceTypeRegistry,
    )

    registry = ResourceTypeRegistry.default()
    config = registry.get(ResourceType.AGENT)
    path = config.resolve_path("iac-analyzer")
"""

from __future__ import annotations

from harness.optimization.protocols.resource_types import (
    ResourceType,
    ResourceTypeConfig,
    ResourceTypeRegistry,
)
from harness.optimization.protocols.signals import Signal, SignalParser, SignalType

__all__ = [
    "ResourceType",
    "ResourceTypeConfig",
    "ResourceTypeRegistry",
    "Signal",
    "SignalParser",
    "SignalType",
]
