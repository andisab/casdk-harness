"""Prompt adapter for transforming spans to prompt feedback.

Analyzes execution spans from prompt rendering and usage to extract
structured metrics for prompt optimization.

Example usage:
    from harness.optimization.adapters import PromptAdapter
    from harness.tracer import Span

    adapter = PromptAdapter()
    feedback = adapter.adapt(spans)

    print(f"Response quality: {feedback.response_quality:.2%}")
    print(f"Clarity score: {feedback.clarity_score:.2%}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.optimization.adapters.base import BaseAdapter, PromptFeedback

if TYPE_CHECKING:
    from harness.tracer.base import Span


class PromptAdapter(BaseAdapter[PromptFeedback]):
    """Adapter for transforming prompt execution spans into feedback.

    Extracts metrics specific to prompt template effectiveness:
    - Render counts and variable usage
    - Response quality and length
    - Clarity and instruction compliance
    """

    @property
    def resource_type(self) -> str:
        """Return resource type."""
        return "prompt"

    def adapt(self, spans: list[Span]) -> PromptFeedback:
        """Transform prompt spans into structured feedback.

        Args:
            spans: List of spans from prompt usage traces.

        Returns:
            PromptFeedback with extracted metrics.
        """
        if not spans:
            return PromptFeedback(resource_type="prompt")

        # Extract base metrics
        base_metrics = self._extract_base_metrics(spans)

        # Create feedback with base metrics
        feedback = PromptFeedback(
            resource_type="prompt",
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

        # Extract prompt-specific metrics
        self._extract_render_metrics(spans, feedback)
        self._extract_variable_metrics(spans, feedback)
        self._extract_response_metrics(spans, feedback)
        self._extract_quality_metrics(spans, feedback)

        return feedback

    def _extract_render_metrics(
        self,
        spans: list[Span],
        feedback: PromptFeedback,
    ) -> None:
        """Extract prompt render metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        render_count = 0

        for span in spans:
            # Check for prompt-related spans
            if span.resource_type == "prompt":
                render_count += 1
                if span.resource_id:
                    feedback.resource_id = span.resource_id

            # Check for render events
            if "prompt.rendered" in span.attributes:
                render_count += 1

            # Check LLM request spans for prompt usage
            if span.kind.value == "llm_request":
                render_count += 1

        feedback.render_count = render_count

    def _extract_variable_metrics(
        self,
        spans: list[Span],
        feedback: PromptFeedback,
    ) -> None:
        """Extract variable substitution metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        variables_used: set[str] = set()
        missing_variables: set[str] = set()

        for span in spans:
            # Extract variable lists from attributes
            if "prompt.variables_used" in span.attributes:
                vars_used = span.attributes["prompt.variables_used"]
                if isinstance(vars_used, list):
                    variables_used.update(vars_used)

            if "prompt.variables_missing" in span.attributes:
                vars_missing = span.attributes["prompt.variables_missing"]
                if isinstance(vars_missing, list):
                    missing_variables.update(vars_missing)

            # Check for individual variable attributes
            for key, value in span.attributes.items():
                if key.startswith("prompt.var."):
                    var_name = key.replace("prompt.var.", "")
                    variables_used.add(var_name)

        feedback.variables_used = sorted(variables_used)
        feedback.missing_variables = sorted(missing_variables)

    def _extract_response_metrics(
        self,
        spans: list[Span],
        feedback: PromptFeedback,
    ) -> None:
        """Extract response metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        response_lengths: list[int] = []

        for span in spans:
            # Get response length from LLM spans
            if span.kind.value == "llm_request":
                if "response.length" in span.attributes:
                    response_lengths.append(span.attributes["response.length"])
                elif span.token_usage:
                    # Estimate from output tokens (rough: 4 chars per token)
                    output_tokens = span.token_usage.get("output", 0)
                    response_lengths.append(output_tokens * 4)

            # Check prompt-specific attributes
            if "prompt.response_length" in span.attributes:
                response_lengths.append(span.attributes["prompt.response_length"])

        if response_lengths:
            feedback.response_length = sum(response_lengths) // len(response_lengths)

    def _extract_quality_metrics(
        self,
        spans: list[Span],
        feedback: PromptFeedback,
    ) -> None:
        """Extract quality metrics from spans.

        Args:
            spans: List of spans.
            feedback: Feedback to update.
        """
        quality_scores: list[float] = []
        clarity_scores: list[float] = []
        compliance_scores: list[float] = []

        for span in spans:
            # Extract quality scores
            if "prompt.response_quality" in span.attributes:
                quality_scores.append(span.attributes["prompt.response_quality"])

            if "prompt.clarity_score" in span.attributes:
                clarity_scores.append(span.attributes["prompt.clarity_score"])

            if "prompt.instruction_compliance" in span.attributes:
                compliance_scores.append(span.attributes["prompt.instruction_compliance"])

            # Check evaluation attributes
            if "evaluation.quality" in span.attributes:
                quality_scores.append(span.attributes["evaluation.quality"])

        # Set quality scores
        if quality_scores:
            feedback.response_quality = sum(quality_scores) / len(quality_scores)
        else:
            # Default based on success and missing variables
            if feedback.missing_variables:
                feedback.response_quality = 0.7
            else:
                feedback.response_quality = 1.0 if feedback.success else 0.5

        if clarity_scores:
            feedback.clarity_score = sum(clarity_scores) / len(clarity_scores)
        else:
            # Penalize for missing variables
            feedback.clarity_score = max(0.0, 1.0 - len(feedback.missing_variables) * 0.2)

        if compliance_scores:
            feedback.instruction_compliance = sum(compliance_scores) / len(compliance_scores)
        else:
            feedback.instruction_compliance = feedback.response_quality

    def validate_spans(self, spans: list[Span]) -> bool:
        """Validate spans are suitable for prompt adaptation.

        Args:
            spans: List of spans to validate.

        Returns:
            True if spans can be processed.
        """
        if not spans:
            return False

        # Check for prompt-related spans
        for span in spans:
            if span.resource_type == "prompt":
                return True

            if span.kind.value == "llm_request":
                return True

            if "prompt." in str(span.attributes):
                return True

        return len(spans) > 0


def create_prompt_adapter() -> PromptAdapter:
    """Factory function to create a prompt adapter.

    Returns:
        Configured PromptAdapter instance.
    """
    return PromptAdapter()
