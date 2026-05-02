"""Command adapter for transforming spans to command feedback.

Analyzes execution spans from command invocations to extract structured
metrics for command optimization.

Example usage:
    from harness.optimization.adapters import CommandAdapter
    from harness.tracer import Span

    adapter = CommandAdapter()
    feedback = adapter.adapt(spans)

    print(f"Tool compliance: {feedback.tool_compliance:.2%}")
    print(f"Output quality: {feedback.output_quality:.2%}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.optimization.adapters.base import BaseAdapter, CommandFeedback

if TYPE_CHECKING:
    from harness.tracer.base import Span


class CommandAdapter(BaseAdapter[CommandFeedback]):
    """Adapter for transforming command execution spans into feedback.

    Extracts metrics specific to command behavior:
    - Invocation counts
    - Argument handling and validation
    - Tool usage compliance
    - Output quality
    """

    @property
    def resource_type(self) -> str:
        """Return resource type."""
        return "command"

    def adapt(self, spans: list[Span]) -> CommandFeedback:
        """Transform command spans into structured feedback.

        Args:
            spans: List of spans from command execution traces.

        Returns:
            CommandFeedback with extracted metrics.
        """
        if not spans:
            return CommandFeedback(resource_type="command")

        # Extract base metrics
        base_metrics = self._extract_base_metrics(spans)

        # Create feedback with base metrics
        feedback = CommandFeedback(
            resource_type="command",
            execution_time_ms=base_metrics["execution_time_ms"],
            token_count=base_metrics["token_count"],
            input_tokens=base_metrics["input_tokens"],
            output_tokens=base_metrics["output_tokens"],
            cached_tokens=base_metrics["cached_tokens"],
            success=base_metrics["success"],
            error_count=base_metrics["error_count"],
            error_messages=base_metrics["error_messages"],
            resource_id=base_metrics["resource_id"],
            trace_id=base_metrics["trace_id"],
            span_count=base_metrics["span_count"],
        )

        # Extract command-specific metrics
        self._extract_invocation_metrics(spans, feedback)
        self._extract_argument_metrics(spans, feedback)
        self._extract_tool_metrics(spans, feedback)
        self._extract_quality_metrics(spans, feedback)

        return feedback

    def _extract_invocation_metrics(
        self,
        spans: list[Span],
        feedback: CommandFeedback,
    ) -> None:
        """Extract command invocation metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        invocation_count = 0

        for span in spans:
            # Check for command-related spans
            if span.resource_type == "command":
                invocation_count += 1
                if span.resource_id:
                    feedback.resource_id = span.resource_id

            # Check for command execution events
            if "command.invoked" in span.attributes:
                invocation_count += 1

            # Check agent execution spans for command context
            if span.kind.value == "agent_execution":
                if "command.name" in span.attributes:
                    invocation_count += 1

        feedback.invocation_count = invocation_count

    def _extract_argument_metrics(
        self,
        spans: list[Span],
        feedback: CommandFeedback,
    ) -> None:
        """Extract argument handling metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        arguments: list[str] = []
        validation_errors: list[str] = []
        parse_success = True

        for span in spans:
            # Extract arguments
            if "command.arguments" in span.attributes:
                args = span.attributes["command.arguments"]
                if isinstance(args, list):
                    arguments.extend(args)
                elif isinstance(args, str):
                    arguments.append(args)

            # Check for parsing errors
            if "command.argument_parse_error" in span.attributes:
                parse_success = False
                error = span.attributes["command.argument_parse_error"]
                if error:
                    validation_errors.append(str(error))

            # Check for validation errors
            if "command.validation_errors" in span.attributes:
                errors = span.attributes["command.validation_errors"]
                if isinstance(errors, list):
                    validation_errors.extend(errors)

        feedback.arguments_provided = arguments
        feedback.argument_parse_success = parse_success
        feedback.argument_validation_errors = validation_errors

    def _extract_tool_metrics(
        self,
        spans: list[Span],
        feedback: CommandFeedback,
    ) -> None:
        """Extract tool usage compliance metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        tools_allowed: set[str] = set()
        tools_used: set[str] = set()
        unauthorized_attempts = 0

        for span in spans:
            # Get allowed tools
            if "command.allowed_tools" in span.attributes:
                allowed = span.attributes["command.allowed_tools"]
                if isinstance(allowed, list):
                    tools_allowed.update(allowed)

            # Track actual tool usage
            if span.kind.value == "tool_call":
                tool_name = span.attributes.get("tool.name", "")
                if tool_name:
                    tools_used.add(tool_name)

                    # Check if tool was authorized
                    if tools_allowed and tool_name not in tools_allowed:
                        unauthorized_attempts += 1

            # Check for unauthorized access events
            if "command.unauthorized_tool_attempt" in span.attributes:
                unauthorized_attempts += 1

        feedback.tools_allowed = sorted(tools_allowed)
        feedback.tools_actually_used = sorted(tools_used)
        feedback.unauthorized_tool_attempts = unauthorized_attempts

    def _extract_quality_metrics(
        self,
        spans: list[Span],
        feedback: CommandFeedback,
    ) -> None:
        """Extract output quality metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        quality_scores: list[float] = []

        for span in spans:
            # Extract quality scores from attributes
            if "command.output_quality" in span.attributes:
                quality_scores.append(span.attributes["command.output_quality"])

            if "evaluation.quality" in span.attributes:
                quality_scores.append(span.attributes["evaluation.quality"])

        if quality_scores:
            feedback.output_quality = sum(quality_scores) / len(quality_scores)
        else:
            # Default based on success and compliance
            base_quality = 1.0 if feedback.success else 0.5
            compliance_penalty = feedback.unauthorized_tool_attempts * 0.1
            feedback.output_quality = max(0.0, base_quality - compliance_penalty)

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate spans are suitable for command adaptation.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed.
        """
        if not spans:
            return False

        # Check for command-related spans
        for span in spans:
            if span.resource_type == "command":
                return True

            if "command." in str(span.attributes):
                return True

        return len(spans) > 0


def create_command_adapter() -> CommandAdapter:
    """Factory function to create a command adapter.

    Returns:
        Configured CommandAdapter instance.
    """
    return CommandAdapter()
