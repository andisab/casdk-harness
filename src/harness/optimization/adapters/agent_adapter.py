"""Agent adapter for transforming spans to agent feedback.

Analyzes execution spans from agent runs to extract structured metrics
for agent optimization.

Example usage:
    from harness.optimization.adapters import AgentAdapter
    from harness.tracer import Span

    adapter = AgentAdapter()
    feedback = adapter.adapt(spans)

    print(f"Task completed: {feedback.task_completed}")
    print(f"Tool success rate: {feedback.tool_success_rate:.2%}")
    print(f"Efficiency score: {feedback.efficiency_score:.2f}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.optimization.adapters.base import AgentFeedback, BaseAdapter

if TYPE_CHECKING:
    from harness.tracer.base import Span


class AgentAdapter(BaseAdapter[AgentFeedback]):
    """Adapter for transforming agent execution spans into feedback.

    Extracts metrics specific to agent behavior:
    - Task completion status
    - Turn counts and limits
    - Tool usage patterns and success rates
    - Subagent delegation metrics
    - Efficiency and reliability scores
    """

    @property
    def resource_type(self) -> str:
        """Return resource type."""
        return "agent"

    def adapt(self, spans: list[Span]) -> AgentFeedback:
        """Transform agent spans into structured feedback.

        Args:
            spans: List of spans from an agent execution trace.

        Returns:
            AgentFeedback with extracted metrics.
        """
        if not spans:
            return AgentFeedback(resource_type="agent")

        # Extract base metrics
        base_metrics = self._extract_base_metrics(spans)

        # Create feedback with base metrics
        feedback = AgentFeedback(
            resource_type="agent",
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

        # Extract agent-specific metrics
        self._extract_task_completion(spans, feedback)
        self._extract_turn_metrics(spans, feedback)
        self._extract_tool_metrics(spans, feedback)
        self._extract_subagent_metrics(spans, feedback)

        # Compute derived scores
        feedback.compute_efficiency_score()
        feedback.compute_reliability_score()

        return feedback

    def _extract_task_completion(
        self,
        spans: list[Span],
        feedback: AgentFeedback,
    ) -> None:
        """Extract task completion status from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        # Look for agent execution spans
        agent_spans = self._filter_spans_by_kind(spans, "agent_execution")

        for span in agent_spans:
            # Check for task completion attributes
            if "task.completed" in span.attributes:
                feedback.task_completed = span.attributes["task.completed"]

            if "task.completion_reason" in span.attributes:
                feedback.task_completion_reason = span.attributes["task.completion_reason"]

            # Check span status
            if span.status.value == "ok" and not feedback.task_completed:
                # Assume OK status means task completed if no explicit attribute
                feedback.task_completed = True

            # Get resource ID from agent span
            if span.resource_id:
                feedback.resource_id = span.resource_id
            elif span.agent_name:
                feedback.resource_id = span.agent_name

        # If no agent spans, check root span
        if not agent_spans and spans:
            root_span = spans[0]
            if root_span.status.value == "ok":
                feedback.task_completed = True
            feedback.task_completion_reason = root_span.status.value

    def _extract_turn_metrics(
        self,
        spans: list[Span],
        feedback: AgentFeedback,
    ) -> None:
        """Extract conversation turn metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        # Count LLM request spans as turns
        llm_spans = self._filter_spans_by_kind(spans, "llm_request")
        feedback.turns_taken = len(llm_spans)

        # Check for max turns reached
        for span in spans:
            if "agent.max_turns_reached" in span.attributes:
                feedback.max_turns_reached = span.attributes["agent.max_turns_reached"]
                break

            if "agent.max_turns" in span.attributes:
                max_turns = span.attributes["agent.max_turns"]
                if feedback.turns_taken >= max_turns:
                    feedback.max_turns_reached = True

    def _extract_tool_metrics(
        self,
        spans: list[Span],
        feedback: AgentFeedback,
    ) -> None:
        """Extract tool usage metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        # Get tool call spans
        tool_spans = self._filter_spans_by_kind(spans, "tool_call")
        feedback.tool_call_count = len(tool_spans)

        # Count successes and extract unique tools
        tools_used: set[str] = set()
        success_count = 0
        error_count = 0

        for span in tool_spans:
            # Get tool name
            tool_name = span.attributes.get("tool.name", "")
            if tool_name:
                tools_used.add(tool_name)

            # Count success/failure
            if span.status.value == "ok":
                success_count += 1
            else:
                error_count += 1

        feedback.tools_used = sorted(tools_used)
        feedback.tool_success_count = success_count
        feedback.tool_error_count = error_count

    def _extract_subagent_metrics(
        self,
        spans: list[Span],
        feedback: AgentFeedback,
    ) -> None:
        """Extract subagent invocation metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        # Get subagent invocation spans
        subagent_spans = self._filter_spans_by_kind(spans, "subagent_invocation")
        feedback.subagent_calls = len(subagent_spans)

        # Count successes
        success_count = 0
        for span in subagent_spans:
            if span.status.value == "ok":
                success_count += 1

        feedback.subagent_success_count = success_count

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate spans are suitable for agent adaptation.

        Checks that there's at least one agent-related span.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed.
        """
        if not spans:
            return False

        # Check for agent execution or related spans
        for span in spans:
            if span.kind.value in ("agent_execution", "llm_request", "tool_call"):
                return True

            # Check for agent resource type
            if span.resource_type == "agent":
                return True

        return False


def create_agent_adapter() -> AgentAdapter:
    """Factory function to create an agent adapter.

    Returns:
        Configured AgentAdapter instance.
    """
    return AgentAdapter()
