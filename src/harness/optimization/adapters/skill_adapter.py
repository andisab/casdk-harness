"""Skill adapter for transforming spans to skill feedback.

Analyzes execution spans from skill invocations to extract structured metrics
for skill optimization.

Example usage:
    from harness.optimization.adapters import SkillAdapter
    from harness.tracer import Span

    adapter = SkillAdapter()
    feedback = adapter.adapt(spans)

    print(f"Activation accuracy: {feedback.activation_accuracy:.2%}")
    print(f"Execution success rate: {feedback.execution_success_rate:.2%}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.optimization.adapters.base import BaseAdapter, SkillFeedback

if TYPE_CHECKING:
    from harness.tracer.base import Span


class SkillAdapter(BaseAdapter[SkillFeedback]):
    """Adapter for transforming skill execution spans into feedback.

    Extracts metrics specific to skill behavior:
    - Activation frequency and accuracy
    - Execution success rates
    - Output quality indicators
    - Relevance to context
    """

    @property
    def resource_type(self) -> str:
        """Return resource type."""
        return "skill"

    def adapt(self, spans: list[Span]) -> SkillFeedback:
        """Transform skill spans into structured feedback.

        Args:
            spans: List of spans from skill execution traces.

        Returns:
            SkillFeedback with extracted metrics.
        """
        if not spans:
            return SkillFeedback(resource_type="skill")

        # Extract base metrics
        base_metrics = self._extract_base_metrics(spans)

        # Create feedback with base metrics
        feedback = SkillFeedback(
            resource_type="skill",
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

        # Extract skill-specific metrics
        self._extract_activation_metrics(spans, feedback)
        self._extract_execution_metrics(spans, feedback)
        self._extract_quality_metrics(spans, feedback)

        return feedback

    def _extract_activation_metrics(
        self,
        spans: list[Span],
        feedback: SkillFeedback,
    ) -> None:
        """Extract skill activation metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        activation_count = 0
        correct_activations = 0

        for span in spans:
            # Check for skill activation events
            if span.resource_type == "skill":
                activation_count += 1

                # Check if activation was appropriate
                if span.attributes.get("skill.activation_correct", True):
                    correct_activations += 1

            # Also check span attributes
            if "skill.activated" in span.attributes:
                if span.attributes["skill.activated"]:
                    activation_count += 1
                    if span.attributes.get("skill.activation_correct", True):
                        correct_activations += 1

            # Get resource ID
            if span.resource_id and span.resource_type == "skill":
                feedback.resource_id = span.resource_id

        feedback.activation_count = activation_count
        if activation_count > 0:
            feedback.activation_accuracy = correct_activations / activation_count
        else:
            feedback.activation_accuracy = 1.0

    def _extract_execution_metrics(
        self,
        spans: list[Span],
        feedback: SkillFeedback,
    ) -> None:
        """Extract skill execution metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        execution_count = 0
        success_count = 0

        for span in spans:
            # Count skill-related executions
            if span.resource_type == "skill":
                execution_count += 1
                if span.status.value == "ok":
                    success_count += 1

            # Also check for resource evaluation spans
            if span.kind.value == "resource_evaluation":
                if span.resource_type == "skill":
                    execution_count += 1
                    if span.status.value == "ok":
                        success_count += 1

        feedback.execution_count = execution_count
        feedback.execution_success_count = success_count

    def _extract_quality_metrics(
        self,
        spans: list[Span],
        feedback: SkillFeedback,
    ) -> None:
        """Extract output quality metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        quality_scores: list[float] = []
        relevance_scores: list[float] = []

        for span in spans:
            # Extract quality scores from attributes
            if "skill.output_quality" in span.attributes:
                quality_scores.append(span.attributes["skill.output_quality"])

            if "skill.relevance_score" in span.attributes:
                relevance_scores.append(span.attributes["skill.relevance_score"])

            # Check evaluation attributes
            if "evaluation.quality" in span.attributes:
                quality_scores.append(span.attributes["evaluation.quality"])

        # Average quality scores
        if quality_scores:
            feedback.output_quality = sum(quality_scores) / len(quality_scores)
        else:
            # Default based on success
            feedback.output_quality = 1.0 if feedback.success else 0.5

        # Average relevance scores
        if relevance_scores:
            feedback.relevance_score = sum(relevance_scores) / len(relevance_scores)
        else:
            feedback.relevance_score = feedback.activation_accuracy

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate spans are suitable for skill adaptation.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed.
        """
        if not spans:
            return False

        # Check for skill-related spans
        for span in spans:
            if span.resource_type == "skill":
                return True

            if span.attributes.get("skill.activated"):
                return True

            if "skill." in str(span.attributes):
                return True

        return len(spans) > 0


def create_skill_adapter() -> SkillAdapter:
    """Factory function to create a skill adapter.

    Returns:
        Configured SkillAdapter instance.
    """
    return SkillAdapter()
