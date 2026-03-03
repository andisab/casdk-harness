"""Protocol modules for the multi-resource optimization pipeline.

Signals:
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

Quality scoring:
    from harness.optimization.protocols import (
        QualityScore,
        ExecutionScore,
        CombinedScore,
    )

    quality = QualityScore(completeness=0.9, accuracy=0.85, clarity=0.8)
    execution = ExecutionScore(pass_pow_k=0.90, total_scenarios=20)
    combined = CombinedScore(quality=quality, execution=execution)
    print(combined.recommendation)  # "ACCEPT"

State transitions:
    from harness.optimization.protocols import PHASE_ORDER, is_valid_transition

    assert is_valid_transition("RESEARCH", "DESIGN")

Workspace layout:
    from harness.optimization.protocols import WorkspaceLayout

    layout = WorkspaceLayout(root=Path("workspace/my-agent"))
    spec_path = layout.spec
"""

from __future__ import annotations

from harness.optimization.protocols.quality import (
    ACCEPT_EXECUTION_THRESHOLD,
    ACCEPT_QUALITY_THRESHOLD,
    ACCURACY_WEIGHT,
    CLARITY_WEIGHT,
    COMPLETENESS_WEIGHT,
    REFINE_EXECUTION_THRESHOLD,
    CombinedScore,
    ExecutionScore,
    QualityScore,
)
from harness.optimization.protocols.resource_types import (
    ResourceType,
    ResourceTypeConfig,
    ResourceTypeRegistry,
)
from harness.optimization.protocols.signals import Signal, SignalParser, SignalType
from harness.optimization.protocols.state import PHASE_ORDER, is_valid_transition
from harness.optimization.protocols.workspace import WorkspaceLayout

__all__ = [
    # quality
    "ACCEPT_EXECUTION_THRESHOLD",
    "ACCEPT_QUALITY_THRESHOLD",
    "ACCURACY_WEIGHT",
    "CLARITY_WEIGHT",
    "COMPLETENESS_WEIGHT",
    "CombinedScore",
    "ExecutionScore",
    "QualityScore",
    "REFINE_EXECUTION_THRESHOLD",
    # resource_types
    "ResourceType",
    "ResourceTypeConfig",
    "ResourceTypeRegistry",
    # signals
    "Signal",
    "SignalParser",
    "SignalType",
    # state
    "PHASE_ORDER",
    "is_valid_transition",
    # workspace
    "WorkspaceLayout",
]
