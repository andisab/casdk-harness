"""Base types and protocols for CGF adapters.

Adapters transform execution spans into structured feedback for optimization.
Each resource type (agent, skill, prompt, command) has a specific adapter
that extracts relevant metrics from span data.

Example usage:
    from harness.optimization.adapters import AgentAdapter, AgentFeedback
    from harness.tracer import Span

    # Transform spans into feedback
    adapter = AgentAdapter()
    feedback = adapter.adapt(spans)

    # Convert feedback to reward for optimization
    reward = feedback.to_reward()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from harness.tracer.base import Span


# =============================================================================
# Feedback Data Structures
# =============================================================================


@dataclass
class BaseFeedback:
    """Base feedback structure with common fields.

    All feedback types share these core metrics that are relevant
    for any resource optimization.
    """

    # Execution metrics
    execution_time_ms: float = 0.0
    """Total execution time in milliseconds."""

    token_count: int = 0
    """Total tokens used (input + output)."""

    input_tokens: int = 0
    """Input/prompt tokens."""

    output_tokens: int = 0
    """Output/completion tokens."""

    cached_tokens: int = 0
    """Tokens served from cache."""

    # Success metrics
    success: bool = True
    """Whether the execution completed successfully."""

    error_count: int = 0
    """Number of errors encountered."""

    error_messages: list[str] = field(default_factory=list)
    """Error messages if any."""

    # Resource context
    resource_id: str = ""
    """ID of the resource being evaluated."""

    resource_type: str = ""
    """Type of resource (agent, skill, prompt, command)."""

    trace_id: str = ""
    """Trace ID for debugging."""

    span_count: int = 0
    """Number of spans processed."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize feedback to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "execution_time_ms": self.execution_time_ms,
            "token_count": self.token_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "success": self.success,
            "error_count": self.error_count,
            "error_messages": self.error_messages,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "trace_id": self.trace_id,
            "span_count": self.span_count,
        }


@dataclass
class AgentFeedback(BaseFeedback):
    """Structured feedback for agent execution.

    Captures metrics specific to agent behavior including task completion,
    tool usage patterns, and efficiency metrics.
    """

    # Task completion
    task_completed: bool = False
    """Whether the agent completed its assigned task."""

    task_completion_reason: str = ""
    """Reason for task completion/failure."""

    # Turn metrics
    turns_taken: int = 0
    """Number of conversation turns."""

    max_turns_reached: bool = False
    """Whether max turns limit was hit."""

    # Tool usage
    tools_used: list[str] = field(default_factory=list)
    """List of unique tools used."""

    tool_call_count: int = 0
    """Total number of tool calls."""

    tool_success_count: int = 0
    """Number of successful tool calls."""

    tool_error_count: int = 0
    """Number of failed tool calls."""

    @property
    def tool_success_rate(self) -> float:
        """Calculate tool success rate.

        Returns:
            Success rate as float between 0.0 and 1.0.
        """
        if self.tool_call_count == 0:
            return 1.0
        return self.tool_success_count / self.tool_call_count

    # Subagent metrics
    subagent_calls: int = 0
    """Number of subagent invocations."""

    subagent_success_count: int = 0
    """Number of successful subagent calls."""

    # Efficiency scores (computed)
    efficiency_score: float = 0.0
    """Computed efficiency score (0.0 - 1.0)."""

    reliability_score: float = 0.0
    """Computed reliability score (0.0 - 1.0)."""

    def compute_efficiency_score(self) -> float:
        """Compute efficiency score based on resource usage.

        Higher score = better efficiency (fewer resources for same result).

        Returns:
            Efficiency score between 0.0 and 1.0.
        """
        if not self.task_completed:
            return 0.0

        # Factors: token usage, turns taken, time spent
        # Lower values = better efficiency

        # Token efficiency: penalize high token usage
        # Assume 50k tokens is "average", scale accordingly
        token_factor = max(0.0, 1.0 - (self.token_count / 100000))

        # Turn efficiency: penalize many turns
        # Assume 10 turns is "average"
        turn_factor = max(0.0, 1.0 - (self.turns_taken / 50))

        # Tool efficiency: penalize excessive tool calls
        # Assume 20 tool calls is "average"
        tool_factor = max(0.0, 1.0 - (self.tool_call_count / 100))

        # Weight the factors
        self.efficiency_score = (
            token_factor * 0.4 +
            turn_factor * 0.3 +
            tool_factor * 0.3
        )
        return self.efficiency_score

    def compute_reliability_score(self) -> float:
        """Compute reliability score based on success rates.

        Higher score = more reliable (fewer errors, better success rate).

        Returns:
            Reliability score between 0.0 and 1.0.
        """
        # Task completion weight
        task_weight = 1.0 if self.task_completed else 0.0

        # Tool success rate weight
        tool_reliability = self.tool_success_rate

        # Error penalty
        error_penalty = min(0.5, self.error_count * 0.1)

        self.reliability_score = max(0.0, (
            task_weight * 0.5 +
            tool_reliability * 0.4 -
            error_penalty
        ))
        return self.reliability_score

    def to_reward(self) -> dict[str, float]:
        """Convert feedback to reward dimensions.

        Returns:
            Dictionary with reward dimension scores.
        """
        self.compute_efficiency_score()
        self.compute_reliability_score()

        return {
            "task_completion": 1.0 if self.task_completed else 0.0,
            "efficiency": self.efficiency_score,
            "reliability": self.reliability_score,
            "tool_success_rate": self.tool_success_rate,
            "quality": self.reliability_score,  # Alias for now
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        base = super().to_dict()
        base.update({
            "task_completed": self.task_completed,
            "task_completion_reason": self.task_completion_reason,
            "turns_taken": self.turns_taken,
            "max_turns_reached": self.max_turns_reached,
            "tools_used": self.tools_used,
            "tool_call_count": self.tool_call_count,
            "tool_success_count": self.tool_success_count,
            "tool_error_count": self.tool_error_count,
            "tool_success_rate": self.tool_success_rate,
            "subagent_calls": self.subagent_calls,
            "subagent_success_count": self.subagent_success_count,
            "efficiency_score": self.efficiency_score,
            "reliability_score": self.reliability_score,
        })
        return base


@dataclass
class SkillFeedback(BaseFeedback):
    """Structured feedback for skill execution.

    Captures metrics specific to skill activation and execution quality.
    """

    # Activation metrics
    activation_count: int = 0
    """Number of times the skill was activated."""

    activation_accuracy: float = 0.0
    """Accuracy of skill activation (correct context identification)."""

    # Execution metrics
    execution_count: int = 0
    """Number of skill executions."""

    execution_success_count: int = 0
    """Number of successful executions."""

    @property
    def execution_success_rate(self) -> float:
        """Calculate execution success rate.

        Returns:
            Success rate as float between 0.0 and 1.0.
        """
        if self.execution_count == 0:
            return 1.0
        return self.execution_success_count / self.execution_count

    # Quality metrics
    output_quality: float = 0.0
    """Quality of skill output (0.0 - 1.0)."""

    relevance_score: float = 0.0
    """Relevance of skill application to context."""

    def to_reward(self) -> dict[str, float]:
        """Convert feedback to reward dimensions.

        Returns:
            Dictionary with reward dimension scores.
        """
        return {
            "task_completion": self.execution_success_rate,
            "efficiency": max(0.0, 1.0 - (self.token_count / 50000)),
            "quality": self.output_quality,
            "relevance": self.relevance_score,
            "activation_accuracy": self.activation_accuracy,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        base = super().to_dict()
        base.update({
            "activation_count": self.activation_count,
            "activation_accuracy": self.activation_accuracy,
            "execution_count": self.execution_count,
            "execution_success_count": self.execution_success_count,
            "execution_success_rate": self.execution_success_rate,
            "output_quality": self.output_quality,
            "relevance_score": self.relevance_score,
        })
        return base


@dataclass
class PromptFeedback(BaseFeedback):
    """Structured feedback for prompt execution.

    Captures metrics specific to prompt template effectiveness.
    """

    # Usage metrics
    render_count: int = 0
    """Number of times the prompt was rendered."""

    # Variable metrics
    variables_used: list[str] = field(default_factory=list)
    """Variables that were substituted."""

    missing_variables: list[str] = field(default_factory=list)
    """Variables referenced but not provided."""

    # Output metrics
    response_length: int = 0
    """Average response length in characters."""

    response_quality: float = 0.0
    """Quality of responses generated (0.0 - 1.0)."""

    # Clarity metrics
    clarity_score: float = 0.0
    """How clear/unambiguous the prompt is (0.0 - 1.0)."""

    instruction_compliance: float = 0.0
    """How well responses follow prompt instructions (0.0 - 1.0)."""

    def to_reward(self) -> dict[str, float]:
        """Convert feedback to reward dimensions.

        Returns:
            Dictionary with reward dimension scores.
        """
        # Penalize missing variables
        variable_penalty = len(self.missing_variables) * 0.1

        return {
            "task_completion": 1.0 if self.success else 0.0,
            "efficiency": max(0.0, 1.0 - (self.token_count / 30000)),
            "quality": self.response_quality,
            "clarity": max(0.0, self.clarity_score - variable_penalty),
            "instruction_compliance": self.instruction_compliance,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        base = super().to_dict()
        base.update({
            "render_count": self.render_count,
            "variables_used": self.variables_used,
            "missing_variables": self.missing_variables,
            "response_length": self.response_length,
            "response_quality": self.response_quality,
            "clarity_score": self.clarity_score,
            "instruction_compliance": self.instruction_compliance,
        })
        return base


@dataclass
class CommandFeedback(BaseFeedback):
    """Structured feedback for command execution.

    Captures metrics specific to command invocation and argument handling.
    """

    # Invocation metrics
    invocation_count: int = 0
    """Number of times the command was invoked."""

    # Argument metrics
    arguments_provided: list[str] = field(default_factory=list)
    """Arguments provided to the command."""

    argument_parse_success: bool = True
    """Whether arguments were parsed successfully."""

    argument_validation_errors: list[str] = field(default_factory=list)
    """Argument validation error messages."""

    # Tool metrics
    tools_allowed: list[str] = field(default_factory=list)
    """Tools the command is allowed to use."""

    tools_actually_used: list[str] = field(default_factory=list)
    """Tools that were actually used."""

    unauthorized_tool_attempts: int = 0
    """Attempts to use unauthorized tools."""

    # Output metrics
    output_quality: float = 0.0
    """Quality of command output (0.0 - 1.0)."""

    @property
    def tool_compliance(self) -> float:
        """Calculate tool usage compliance.

        Returns:
            Compliance score (1.0 = all tools authorized, 0.0 = violations).
        """
        if self.unauthorized_tool_attempts > 0:
            return max(0.0, 1.0 - (self.unauthorized_tool_attempts * 0.2))
        return 1.0

    def to_reward(self) -> dict[str, float]:
        """Convert feedback to reward dimensions.

        Returns:
            Dictionary with reward dimension scores.
        """
        return {
            "task_completion": 1.0 if self.success else 0.0,
            "efficiency": max(0.0, 1.0 - (self.token_count / 20000)),
            "quality": self.output_quality,
            "safety": self.tool_compliance,
            "argument_handling": 1.0 if self.argument_parse_success else 0.0,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        base = super().to_dict()
        base.update({
            "invocation_count": self.invocation_count,
            "arguments_provided": self.arguments_provided,
            "argument_parse_success": self.argument_parse_success,
            "argument_validation_errors": self.argument_validation_errors,
            "tools_allowed": self.tools_allowed,
            "tools_actually_used": self.tools_actually_used,
            "unauthorized_tool_attempts": self.unauthorized_tool_attempts,
            "tool_compliance": self.tool_compliance,
            "output_quality": self.output_quality,
        })
        return base


# =============================================================================
# Training Triplet Structure
# =============================================================================


@dataclass
class TrainingTriplet:
    """Triplet for preference-based optimization training.

    Used for learning from feedback signals via pairwise comparisons.

    Structure:
        - prompt: The input/task given to the resource
        - positive: A good response/behavior
        - negative: A bad response/behavior

    The optimizer learns to prefer positive over negative.
    """

    prompt: str
    """The input prompt or task."""

    positive: str
    """Example of good response/behavior."""

    negative: str
    """Example of bad response/behavior."""

    # Context
    resource_id: str = ""
    """ID of the resource being optimized."""

    resource_type: str = ""
    """Type of resource (agent, skill, prompt, command)."""

    # Scoring
    positive_score: float = 1.0
    """Score for the positive example."""

    negative_score: float = 0.0
    """Score for the negative example."""

    # Metadata
    trace_id: str = ""
    """Trace ID for provenance."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional context."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "prompt": self.prompt,
            "positive": self.positive,
            "negative": self.negative,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "positive_score": self.positive_score,
            "negative_score": self.negative_score,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingTriplet:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            TrainingTriplet instance.
        """
        return cls(
            prompt=data["prompt"],
            positive=data["positive"],
            negative=data["negative"],
            resource_id=data.get("resource_id", ""),
            resource_type=data.get("resource_type", ""),
            positive_score=data.get("positive_score", 1.0),
            negative_score=data.get("negative_score", 0.0),
            trace_id=data.get("trace_id", ""),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# Adapter Protocol
# =============================================================================

# Type variable for feedback types
F = TypeVar("F", bound=BaseFeedback)


class AdapterProtocol(Protocol[F]):
    """Protocol for span-to-feedback adapters.

    Adapters transform raw execution spans into structured feedback
    for a specific resource type.
    """

    @property
    def resource_type(self) -> str:
        """Type of resource this adapter handles."""
        ...

    def adapt(self, spans: list[Span]) -> F:
        """Transform spans into structured feedback.

        Args:
            spans: List of spans from a trace.

        Returns:
            Structured feedback for the resource type.
        """
        ...

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate that spans are suitable for this adapter.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed, False otherwise.
        """
        ...


class BaseAdapter(ABC, Generic[F]):
    """Abstract base class for adapters.

    Provides common functionality for extracting metrics from spans.
    """

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """Type of resource this adapter handles."""
        ...

    @abstractmethod
    def adapt(self, spans: list[Span]) -> F:
        """Transform spans into structured feedback.

        Args:
            spans: List of spans from a trace.

        Returns:
            Structured feedback for the resource type.
        """
        ...

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate that spans are suitable for this adapter.

        Default implementation checks for non-empty span list.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed.
        """
        return len(spans) > 0

    def _extract_base_metrics(self, spans: list[Span]) -> dict[str, Any]:
        """Extract common metrics from spans.

        Args:
            spans: List of spans.

        Returns:
            Dictionary with base metrics.
        """
        total_duration = 0.0
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        error_count = 0
        error_messages: list[str] = []
        trace_id = ""
        resource_id = ""

        for span in spans:
            # Duration
            if span.duration_ms:
                total_duration += span.duration_ms

            # Token usage
            if span.token_usage:
                input_tokens += span.token_usage.get("input", 0)
                output_tokens += span.token_usage.get("output", 0)
                cached_tokens += span.token_usage.get("cached", 0)
                total_tokens += (
                    span.token_usage.get("input", 0) +
                    span.token_usage.get("output", 0)
                )

            # Errors
            if span.status.value == "error":
                error_count += 1
                if span.error_message:
                    error_messages.append(span.error_message)

            # Context
            if not trace_id and span.trace_id:
                trace_id = span.trace_id
            if not resource_id and span.resource_id:
                resource_id = span.resource_id

        return {
            "execution_time_ms": total_duration,
            "token_count": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "error_count": error_count,
            "error_messages": error_messages,
            "trace_id": trace_id,
            "resource_id": resource_id,
            "span_count": len(spans),
            "success": error_count == 0,
        }

    def _filter_spans_by_kind(
        self,
        spans: list[Span],
        kind: str,
    ) -> list[Span]:
        """Filter spans by kind.

        Args:
            spans: List of spans.
            kind: SpanKind value to filter by.

        Returns:
            Filtered list of spans.
        """
        return [s for s in spans if s.kind.value == kind]

    def _get_unique_values(
        self,
        spans: list[Span],
        attribute_key: str,
    ) -> list[str]:
        """Get unique values for an attribute across spans.

        Args:
            spans: List of spans.
            attribute_key: Attribute key to extract.

        Returns:
            List of unique values.
        """
        values: set[str] = set()
        for span in spans:
            if attribute_key in span.attributes:
                value = span.attributes[attribute_key]
                if isinstance(value, str):
                    values.add(value)
        return sorted(values)
