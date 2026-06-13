"""Triplet adapter for generating training data from spans.

Transforms execution traces into preference triplets for optimization.
Triplets consist of (prompt, positive, negative) examples that can be
used for learning preferences.

Example usage:
    from harness.optimization.adapters import TripletAdapter
    from harness.tracer import Span

    adapter = TripletAdapter()

    # Generate triplets from good and bad traces
    triplets = adapter.create_comparison_triplets(
        good_spans=successful_trace_spans,
        bad_spans=failed_trace_spans,
    )

    for triplet in triplets:
        print(f"Prompt: {triplet.prompt[:50]}...")
        print(f"Positive score: {triplet.positive_score}")
        print(f"Negative score: {triplet.negative_score}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.optimization.adapters.base import (
    AgentFeedback,
    BaseFeedback,
    CommandFeedback,
    PromptFeedback,
    SkillFeedback,
    TrainingTriplet,
)

if TYPE_CHECKING:
    from harness.tracer.base import Span


class TripletAdapter:
    """Adapter for generating training triplets from execution spans.

    Creates preference-based training data by comparing successful and
    failed executions, or by ranking multiple executions by quality.
    """

    def create_comparison_triplets(
        self,
        good_spans: list[Span],
        bad_spans: list[Span],
        resource_id: str = "",
        resource_type: str = "",
    ) -> list[TrainingTriplet]:
        """Create triplets by comparing good and bad execution traces.

        Args:
            good_spans: Spans from a successful/high-quality execution.
            bad_spans: Spans from a failed/low-quality execution.
            resource_id: ID of the resource being optimized.
            resource_type: Type of resource (agent, skill, prompt, command).

        Returns:
            List of training triplets.
        """
        triplets: list[TrainingTriplet] = []

        # Extract task/prompt from spans
        prompt = self._extract_prompt(good_spans) or self._extract_prompt(bad_spans)
        if not prompt:
            prompt = self._generate_prompt_from_context(good_spans, bad_spans)

        # Extract positive (good) response
        positive = self._extract_response(good_spans)
        positive_score = self._compute_score(good_spans)

        # Extract negative (bad) response
        negative = self._extract_response(bad_spans)
        negative_score = self._compute_score(bad_spans)

        # Create triplet if we have valid data
        if prompt and (positive or negative):
            triplet = TrainingTriplet(
                prompt=prompt,
                positive=positive or "[No response]",
                negative=negative or "[No response]",
                resource_id=resource_id or self._extract_resource_id(good_spans + bad_spans),
                resource_type=resource_type or self._extract_resource_type(good_spans + bad_spans),
                positive_score=positive_score,
                negative_score=negative_score,
                trace_id=self._extract_trace_id(good_spans),
                metadata={
                    "good_span_count": len(good_spans),
                    "bad_span_count": len(bad_spans),
                },
            )
            triplets.append(triplet)

        return triplets

    def create_ranked_triplets(
        self,
        ranked_traces: list[tuple[list[Span], float]],
        resource_id: str = "",
        resource_type: str = "",
    ) -> list[TrainingTriplet]:
        """Create triplets from ranked execution traces.

        Takes traces ordered by quality (best first) and creates pairwise
        comparison triplets.

        Args:
            ranked_traces: List of (spans, score) tuples, ordered by quality descending.
            resource_id: ID of the resource being optimized.
            resource_type: Type of resource.

        Returns:
            List of training triplets from pairwise comparisons.
        """
        triplets: list[TrainingTriplet] = []

        if len(ranked_traces) < 2:
            return triplets

        # Create triplets from adjacent pairs
        for i in range(len(ranked_traces) - 1):
            good_spans, good_score = ranked_traces[i]
            bad_spans, bad_score = ranked_traces[i + 1]

            comparison_triplets = self.create_comparison_triplets(
                good_spans=good_spans,
                bad_spans=bad_spans,
                resource_id=resource_id,
                resource_type=resource_type,
            )

            # Update scores from the rankings
            for triplet in comparison_triplets:
                triplet.positive_score = good_score
                triplet.negative_score = bad_score

            triplets.extend(comparison_triplets)

        return triplets

    def create_from_feedback(
        self,
        good_feedback: BaseFeedback,
        bad_feedback: BaseFeedback,
        prompt: str,
        good_response: str,
        bad_response: str,
    ) -> TrainingTriplet:
        """Create a triplet from feedback objects.

        Args:
            good_feedback: Feedback from a good execution.
            bad_feedback: Feedback from a bad execution.
            prompt: The input prompt.
            good_response: The good response.
            bad_response: The bad response.

        Returns:
            Training triplet.
        """
        # Compute scores from feedback
        good_score = self._score_from_feedback(good_feedback)
        bad_score = self._score_from_feedback(bad_feedback)

        return TrainingTriplet(
            prompt=prompt,
            positive=good_response,
            negative=bad_response,
            resource_id=good_feedback.resource_id or bad_feedback.resource_id,
            resource_type=good_feedback.resource_type or bad_feedback.resource_type,
            positive_score=good_score,
            negative_score=bad_score,
            trace_id=good_feedback.trace_id,
            metadata={
                "good_token_count": good_feedback.token_count,
                "bad_token_count": bad_feedback.token_count,
                "good_execution_time_ms": good_feedback.execution_time_ms,
                "bad_execution_time_ms": bad_feedback.execution_time_ms,
            },
        )

    def _extract_prompt(self, spans: list[Span]) -> str:
        """Extract the input prompt from spans.

        Args:
            spans: List of spans.

        Returns:
            Extracted prompt or empty string.
        """
        for span in spans:
            # Check common prompt attributes
            if "prompt.input" in span.attributes:
                return str(span.attributes["prompt.input"])

            if "task.input" in span.attributes:
                return str(span.attributes["task.input"])

            if "agent.input" in span.attributes:
                return str(span.attributes["agent.input"])

            if "user.message" in span.attributes:
                return str(span.attributes["user.message"])

            # Check span name for context
            if "input" in span.name.lower() and span.attributes:
                # Return first string attribute as fallback
                for value in span.attributes.values():
                    if isinstance(value, str) and len(value) > 10:
                        return value

        return ""

    def _extract_response(self, spans: list[Span]) -> str:
        """Extract the output response from spans.

        Args:
            spans: List of spans.

        Returns:
            Extracted response or empty string.
        """
        responses: list[str] = []

        for span in spans:
            # Check common response attributes
            if "response.output" in span.attributes:
                responses.append(str(span.attributes["response.output"]))

            if "agent.output" in span.attributes:
                responses.append(str(span.attributes["agent.output"]))

            if "assistant.message" in span.attributes:
                responses.append(str(span.attributes["assistant.message"]))

            if "llm.response" in span.attributes:
                responses.append(str(span.attributes["llm.response"]))

        # Return longest response (most complete)
        if responses:
            return max(responses, key=len)

        return ""

    def _generate_prompt_from_context(
        self,
        good_spans: list[Span],
        bad_spans: list[Span],
    ) -> str:
        """Generate a prompt description from context.

        Args:
            good_spans: Good execution spans.
            bad_spans: Bad execution spans.

        Returns:
            Generated prompt description.
        """
        all_spans = good_spans + bad_spans
        if not all_spans:
            return ""

        # Try to construct from span metadata
        parts: list[str] = []

        # Get resource info
        resource_type = self._extract_resource_type(all_spans)
        resource_id = self._extract_resource_id(all_spans)

        if resource_type:
            parts.append(f"Execute {resource_type}")
        if resource_id:
            parts.append(f"'{resource_id}'")

        # Get any task description
        for span in all_spans:
            if "task.description" in span.attributes:
                parts.append(str(span.attributes["task.description"]))
                break

        return " ".join(parts) if parts else "Execute task"

    def _compute_score(self, spans: list[Span]) -> float:
        """Compute a quality score from spans.

        Args:
            spans: List of spans.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        if not spans:
            return 0.0

        # Count successes and errors
        success_count = 0
        error_count = 0

        for span in spans:
            if span.status.value == "ok":
                success_count += 1
            elif span.status.value == "error":
                error_count += 1

        total = success_count + error_count
        if total == 0:
            return 0.5  # Neutral if no status info

        return success_count / total

    def _score_from_feedback(self, feedback: BaseFeedback) -> float:
        """Compute score from feedback object.

        Args:
            feedback: Feedback object.

        Returns:
            Score between 0.0 and 1.0.
        """
        if isinstance(feedback, AgentFeedback):
            reward = feedback.to_reward()
            return (
                reward.get("task_completion", 0.0) * 0.4 +
                reward.get("efficiency", 0.0) * 0.2 +
                reward.get("reliability", 0.0) * 0.4
            )

        if isinstance(feedback, SkillFeedback):
            reward = feedback.to_reward()
            return (
                reward.get("task_completion", 0.0) * 0.3 +
                reward.get("quality", 0.0) * 0.4 +
                reward.get("activation_accuracy", 0.0) * 0.3
            )

        if isinstance(feedback, PromptFeedback):
            reward = feedback.to_reward()
            return (
                reward.get("quality", 0.0) * 0.4 +
                reward.get("clarity", 0.0) * 0.3 +
                reward.get("instruction_compliance", 0.0) * 0.3
            )

        if isinstance(feedback, CommandFeedback):
            reward = feedback.to_reward()
            return (
                reward.get("task_completion", 0.0) * 0.3 +
                reward.get("quality", 0.0) * 0.3 +
                reward.get("safety", 0.0) * 0.4
            )

        # Generic fallback
        return 1.0 if feedback.success else 0.0

    def _extract_resource_id(self, spans: list[Span]) -> str:
        """Extract resource ID from spans.

        Args:
            spans: List of spans.

        Returns:
            Resource ID or empty string.
        """
        for span in spans:
            if span.resource_id:
                return span.resource_id
        return ""

    def _extract_resource_type(self, spans: list[Span]) -> str:
        """Extract resource type from spans.

        Args:
            spans: List of spans.

        Returns:
            Resource type or empty string.
        """
        for span in spans:
            if span.resource_type:
                return span.resource_type
        return ""

    def _extract_trace_id(self, spans: list[Span]) -> str:
        """Extract trace ID from spans.

        Args:
            spans: List of spans.

        Returns:
            Trace ID or empty string.
        """
        for span in spans:
            if span.trace_id:
                return span.trace_id
        return ""


def create_triplet_adapter() -> TripletAdapter:
    """Factory function to create a triplet adapter.

    Returns:
        Configured TripletAdapter instance.
    """
    return TripletAdapter()
