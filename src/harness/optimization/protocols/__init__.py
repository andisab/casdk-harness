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
"""

from __future__ import annotations

from harness.optimization.protocols.signals import Signal, SignalParser, SignalType

__all__ = [
    "Signal",
    "SignalParser",
    "SignalType",
]
