"""Unified signal parsing for multi-resource optimization pipeline.

Agent responses contain structured signals in the format:
    [SIGNAL_TAG]           — simple signal (no argument)
    [SIGNAL_TAG:argument]  — signal with path or numeric argument

Signals are optionally followed by metadata lines in `key: value` format.
Metadata lines are collected until the next signal or a non-metadata line.

Special cases:
    [VALIDATE_ISSUES:N]  — N is parsed as integer into metadata["issue_count"]
    [TAG:path]           — path is stored as signal.resource_path

Example:
    [GENERATE_COMPLETE:agents/iac-analyzer.md]
    resource_type: agent
    word_count: 1250

    Parses to:
        Signal(
            type=SignalType.GENERATE_COMPLETE,
            resource_path="agents/iac-analyzer.md",
            metadata={"resource_type": "agent", "word_count": "1250"},
        )
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    """Phase signal types emitted by orchestrator agents.

    Values are lowercase strings matching the signal tag convention.
    """

    RESEARCH_COMPLETE = "research_complete"
    DESIGN_COMPLETE = "design_complete"
    GENERATE_COMPLETE = "generate_complete"
    EVAL_DESIGN_COMPLETE = "eval_design_complete"
    ITERATE_COMPLETE = "iterate_complete"
    EVAL_COMPLETE = "eval_complete"
    VALIDATE_COMPLETE = "validate_complete"
    VALIDATE_ISSUES = "validate_issues"


# Map from uppercase tag text to SignalType for fast lookup.
_TAG_TO_SIGNAL: dict[str, SignalType] = {
    member.name: member for member in SignalType
}

# Regex matching a signal tag line: [TAG] or [TAG:arg]
#
# Permits Markdown-style inline-code / bold decoration around the signal so
# that an agent which writes `[EVAL_DESIGN_COMPLETE]` (backtick-wrapped for
# code formatting) or **[VALIDATE_COMPLETE]** (bold) is still detected. The
# line must otherwise contain ONLY the signal — content on the same line
# defeats the metadata-collection model below.
_SIGNAL_PATTERN = re.compile(
    r"^[\s`*]*\[([A-Z][A-Z0-9_]+)(?::([^\]]+))?\][\s`*]*$"
)

# Regex matching a metadata line: key: value (with optional leading whitespace)
_METADATA_PATTERN = re.compile(
    r"^\s*(\w+):\s*(.+)$"
)


@dataclass
class Signal:
    """A parsed agent signal with optional path and metadata.

    Attributes:
        type: The signal type enum value.
        resource_path: Optional file path argument from [TAG:path] syntax.
        metadata: Key-value pairs from lines following the signal tag.
    """

    type: SignalType
    resource_path: str | None = None
    metadata: dict[str, str | int] = field(default_factory=dict)


class SignalParser:
    """Parse structured signals from agent response text.

    Scans response text line-by-line for signal tags in [TAG] or [TAG:arg]
    format, then collects subsequent key: value metadata lines until the
    next signal or a non-metadata line is encountered.
    """

    def parse(self, response: str) -> list[Signal]:
        """Parse all signals from an agent response string.

        Args:
            response: Raw text response from an agent.

        Returns:
            List of Signal objects in the order they appear. Empty list
            if no valid signals are found.
        """
        signals: list[Signal] = []
        current_signal: Signal | None = None
        lines = response.split("\n")

        for line in lines:
            # Check if this line is a signal tag
            tag_match = _SIGNAL_PATTERN.match(line)
            if tag_match:
                # Finalize previous signal if any
                if current_signal is not None:
                    signals.append(current_signal)

                tag_name = tag_match.group(1)
                tag_arg = tag_match.group(2)

                # Look up the signal type
                signal_type = _TAG_TO_SIGNAL.get(tag_name)
                if signal_type is None:
                    # Unknown tag -- skip it
                    current_signal = None
                    continue

                # Build the new signal
                current_signal = Signal(type=signal_type)

                # Handle VALIDATE_ISSUES specially: arg is an integer count
                if signal_type == SignalType.VALIDATE_ISSUES and tag_arg is not None:
                    current_signal.metadata["issue_count"] = int(tag_arg)
                elif tag_arg is not None:
                    current_signal.resource_path = tag_arg

                continue

            # If we have a current signal, try to collect metadata
            if current_signal is not None:
                meta_match = _METADATA_PATTERN.match(line)
                if meta_match:
                    key = meta_match.group(1)
                    value = meta_match.group(2).strip()
                    current_signal.metadata[key] = value
                elif line.strip():
                    # Non-empty, non-metadata line: stop collecting for this signal
                    signals.append(current_signal)
                    current_signal = None
                # Empty lines are ignored (continue collecting metadata)

        # Don't forget the last signal
        if current_signal is not None:
            signals.append(current_signal)

        return signals
