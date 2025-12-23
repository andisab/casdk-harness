"""CGF Reward System.

Multi-dimensional scoring system for nuanced resource optimization.
ResourceReward provides weighted composite scores from feedback dimensions.

Example usage:
    from harness.optimization import ResourceReward, AgentFeedback

    # Create reward from feedback
    feedback = AgentFeedback(task_completed=True, efficiency_score=0.8)
    reward = ResourceReward.from_feedback(feedback)

    # Get composite score with default weights
    score = reward.composite()

    # Custom weights for specific optimization goals
    efficiency_focused = reward.composite(weights={
        "task_completion": 0.3,
        "efficiency": 0.5,
        "quality": 0.1,
        "safety": 0.1,
    })

    # Compare rewards
    improvement = new_reward.improvement_over(baseline_reward)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.optimization.adapters.base import BaseFeedback


# Default weights for composite scoring
DEFAULT_WEIGHTS: dict[str, float] = {
    "task_completion": 0.4,
    "efficiency": 0.2,
    "quality": 0.3,
    "safety": 0.1,
}

# Resource-specific weight presets
WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "agent": {
        "task_completion": 0.4,
        "efficiency": 0.2,
        "quality": 0.25,
        "safety": 0.15,
    },
    "skill": {
        "task_completion": 0.3,
        "efficiency": 0.2,
        "quality": 0.35,
        "safety": 0.15,
    },
    "prompt": {
        "task_completion": 0.25,
        "efficiency": 0.15,
        "quality": 0.45,
        "safety": 0.15,
    },
    "command": {
        "task_completion": 0.3,
        "efficiency": 0.15,
        "quality": 0.25,
        "safety": 0.30,
    },
    "balanced": DEFAULT_WEIGHTS,
    "efficiency_focused": {
        "task_completion": 0.25,
        "efficiency": 0.50,
        "quality": 0.15,
        "safety": 0.10,
    },
    "quality_focused": {
        "task_completion": 0.20,
        "efficiency": 0.10,
        "quality": 0.55,
        "safety": 0.15,
    },
    "safety_focused": {
        "task_completion": 0.20,
        "efficiency": 0.10,
        "quality": 0.20,
        "safety": 0.50,
    },
}


@dataclass
class ResourceReward:
    """Multi-dimensional reward for resource optimization.

    Core dimensions (each 0.0 - 1.0):
        - task_completion: Did the resource complete its objective?
        - efficiency: How efficiently were resources used?
        - quality: How good was the output/result?
        - safety: Were operations safe and compliant?

    Extra dimensions can be added for resource-specific metrics.

    Attributes:
        task_completion: Task completion score (0.0 - 1.0).
        efficiency: Efficiency score (0.0 - 1.0).
        quality: Quality score (0.0 - 1.0).
        safety: Safety/compliance score (0.0 - 1.0).
        extra: Resource-specific dimensions.
        weights: Custom weights for composite scoring.
        resource_id: ID of the evaluated resource.
        resource_type: Type of resource (agent, skill, prompt, command).
        trace_id: Trace ID for debugging.
        metadata: Additional context.
    """

    # Core dimensions (0.0 - 1.0)
    task_completion: float = 0.0
    """Whether the resource completed its objective."""

    efficiency: float = 0.0
    """How efficiently resources were used."""

    quality: float = 0.0
    """Quality of the output/result."""

    safety: float = 1.0
    """Safety and compliance score (defaults to safe)."""

    # Resource-specific dimensions
    extra: dict[str, float] = field(default_factory=dict)
    """Additional resource-specific dimensions."""

    # Weighting configuration
    weights: dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    """Weights for composite scoring."""

    # Context
    resource_id: str = ""
    """ID of the evaluated resource."""

    resource_type: str = ""
    """Type of resource."""

    trace_id: str = ""
    """Trace ID for debugging."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional context."""

    def __post_init__(self) -> None:
        """Validate dimension values after initialization."""
        self._clamp_dimensions()

    def _clamp_dimensions(self) -> None:
        """Ensure all dimensions are within [0.0, 1.0]."""
        self.task_completion = max(0.0, min(1.0, self.task_completion))
        self.efficiency = max(0.0, min(1.0, self.efficiency))
        self.quality = max(0.0, min(1.0, self.quality))
        self.safety = max(0.0, min(1.0, self.safety))

        for key in self.extra:
            self.extra[key] = max(0.0, min(1.0, self.extra[key]))

    @property
    def core_dimensions(self) -> dict[str, float]:
        """Get core dimension values.

        Returns:
            Dictionary of core dimension scores.
        """
        return {
            "task_completion": self.task_completion,
            "efficiency": self.efficiency,
            "quality": self.quality,
            "safety": self.safety,
        }

    @property
    def all_dimensions(self) -> dict[str, float]:
        """Get all dimension values including extra.

        Returns:
            Dictionary of all dimension scores.
        """
        result = self.core_dimensions.copy()
        result.update(self.extra)
        return result

    def composite(
        self,
        weights: dict[str, float] | None = None,
        include_extra: bool = True,
    ) -> float:
        """Compute weighted composite score.

        Args:
            weights: Custom weights (uses instance weights if not provided).
            include_extra: Whether to include extra dimensions.

        Returns:
            Weighted composite score between 0.0 and 1.0.

        Example:
            >>> reward = ResourceReward(
            ...     task_completion=1.0,
            ...     efficiency=0.8,
            ...     quality=0.9,
            ...     safety=1.0,
            ... )
            >>> reward.composite()  # Uses default weights
            0.92
        """
        effective_weights = weights or self.weights

        # Start with core dimensions
        dimensions = self.core_dimensions

        # Include extra dimensions if requested
        if include_extra and self.extra:
            dimensions = self.all_dimensions

        # Compute weighted sum
        total_weight = 0.0
        weighted_sum = 0.0

        for dim, value in dimensions.items():
            weight = effective_weights.get(dim, 0.0)
            weighted_sum += value * weight
            total_weight += weight

        # Normalize if we have weights
        if total_weight > 0:
            return weighted_sum / total_weight

        # Fallback to simple average if no weights
        if dimensions:
            return sum(dimensions.values()) / len(dimensions)

        return 0.0

    def composite_with_preset(self, preset: str) -> float:
        """Compute composite score using a weight preset.

        Args:
            preset: Name of weight preset (agent, skill, prompt, command,
                   balanced, efficiency_focused, quality_focused, safety_focused).

        Returns:
            Weighted composite score.

        Raises:
            ValueError: If preset is unknown.
        """
        if preset not in WEIGHT_PRESETS:
            raise ValueError(
                f"Unknown preset: {preset}. "
                f"Valid presets: {list(WEIGHT_PRESETS.keys())}"
            )
        return self.composite(weights=WEIGHT_PRESETS[preset])

    def improvement_over(self, baseline: ResourceReward) -> dict[str, float]:
        """Calculate improvement over a baseline reward.

        Args:
            baseline: The baseline reward to compare against.

        Returns:
            Dictionary with improvement percentages for each dimension.
            Positive = improvement, Negative = regression.

        Example:
            >>> baseline = ResourceReward(efficiency=0.5, quality=0.6)
            >>> new = ResourceReward(efficiency=0.7, quality=0.6)
            >>> new.improvement_over(baseline)
            {'task_completion': 0.0, 'efficiency': 40.0, 'quality': 0.0, ...}
        """
        result: dict[str, float] = {}

        # Compare core dimensions
        for dim in ["task_completion", "efficiency", "quality", "safety"]:
            current = getattr(self, dim)
            base = getattr(baseline, dim)

            if base == 0:
                # Avoid division by zero
                result[dim] = 100.0 if current > 0 else 0.0
            else:
                result[dim] = ((current - base) / base) * 100.0

        # Compare extra dimensions (only if both have the same key)
        all_extra_keys = set(self.extra.keys()) | set(baseline.extra.keys())
        for key in all_extra_keys:
            current = self.extra.get(key, 0.0)
            base = baseline.extra.get(key, 0.0)

            if base == 0:
                result[key] = 100.0 if current > 0 else 0.0
            else:
                result[key] = ((current - base) / base) * 100.0

        return result

    def delta(self, baseline: ResourceReward) -> dict[str, float]:
        """Calculate absolute delta from baseline.

        Args:
            baseline: The baseline reward to compare against.

        Returns:
            Dictionary with absolute differences for each dimension.
        """
        result: dict[str, float] = {}

        # Delta for core dimensions
        for dim in ["task_completion", "efficiency", "quality", "safety"]:
            current = getattr(self, dim)
            base = getattr(baseline, dim)
            result[dim] = current - base

        # Delta for extra dimensions
        all_extra_keys = set(self.extra.keys()) | set(baseline.extra.keys())
        for key in all_extra_keys:
            current = self.extra.get(key, 0.0)
            base = baseline.extra.get(key, 0.0)
            result[key] = current - base

        return result

    def is_better_than(
        self,
        other: ResourceReward,
        weights: dict[str, float] | None = None,
    ) -> bool:
        """Check if this reward is better than another.

        Args:
            other: The reward to compare against.
            weights: Custom weights for comparison.

        Returns:
            True if this reward has a higher composite score.
        """
        return self.composite(weights) > other.composite(weights)

    def meets_threshold(
        self,
        thresholds: dict[str, float],
        require_all: bool = True,
    ) -> bool:
        """Check if reward meets specified thresholds.

        Args:
            thresholds: Minimum values for each dimension.
            require_all: If True, all thresholds must be met.
                        If False, any threshold being met is sufficient.

        Returns:
            True if thresholds are met according to require_all.
        """
        dimensions = self.all_dimensions

        if require_all:
            # All specified thresholds must be met
            for dim, threshold in thresholds.items():
                if dimensions.get(dim, 0.0) < threshold:
                    return False
            return True
        else:
            # At least one threshold must be met
            for dim, threshold in thresholds.items():
                if dimensions.get(dim, 0.0) >= threshold:
                    return True
            return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize reward to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "task_completion": self.task_completion,
            "efficiency": self.efficiency,
            "quality": self.quality,
            "safety": self.safety,
            "extra": self.extra.copy(),
            "weights": self.weights.copy(),
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "trace_id": self.trace_id,
            "metadata": self.metadata.copy(),
            "composite": self.composite(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceReward:
        """Create reward from dictionary.

        Args:
            data: Dictionary with reward data.

        Returns:
            ResourceReward instance.
        """
        return cls(
            task_completion=data.get("task_completion", 0.0),
            efficiency=data.get("efficiency", 0.0),
            quality=data.get("quality", 0.0),
            safety=data.get("safety", 1.0),
            extra=data.get("extra", {}),
            weights=data.get("weights", DEFAULT_WEIGHTS.copy()),
            resource_id=data.get("resource_id", ""),
            resource_type=data.get("resource_type", ""),
            trace_id=data.get("trace_id", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_feedback(
        cls,
        feedback: BaseFeedback,
        weights: dict[str, float] | None = None,
    ) -> ResourceReward:
        """Create reward from feedback object.

        Automatically extracts dimensions from feedback's to_reward() method.

        Args:
            feedback: Feedback object with to_reward() method.
            weights: Custom weights (auto-detected from resource_type if not provided).

        Returns:
            ResourceReward instance.
        """
        # Get reward dimensions from feedback
        reward_dict = feedback.to_reward()

        # Extract core dimensions
        task_completion = reward_dict.get("task_completion", 0.0)
        efficiency = reward_dict.get("efficiency", 0.0)
        quality = reward_dict.get("quality", 0.0)
        safety = reward_dict.get("safety", 1.0)

        # Extra dimensions are anything not in core
        core_keys = {"task_completion", "efficiency", "quality", "safety"}
        extra = {k: v for k, v in reward_dict.items() if k not in core_keys}

        # Auto-detect weights from resource type
        effective_weights = weights
        if effective_weights is None and feedback.resource_type:
            effective_weights = WEIGHT_PRESETS.get(
                feedback.resource_type, DEFAULT_WEIGHTS.copy()
            )
        if effective_weights is None:
            effective_weights = DEFAULT_WEIGHTS.copy()

        return cls(
            task_completion=task_completion,
            efficiency=efficiency,
            quality=quality,
            safety=safety,
            extra=extra,
            weights=effective_weights,
            resource_id=feedback.resource_id,
            resource_type=feedback.resource_type,
            trace_id=feedback.trace_id,
        )

    @classmethod
    def zero(cls, resource_type: str = "") -> ResourceReward:
        """Create a zero reward (all dimensions at 0.0).

        Args:
            resource_type: Optional resource type for weight preset.

        Returns:
            ResourceReward with all dimensions at 0.0.
        """
        weights = WEIGHT_PRESETS.get(resource_type, DEFAULT_WEIGHTS.copy())
        return cls(
            task_completion=0.0,
            efficiency=0.0,
            quality=0.0,
            safety=0.0,
            weights=weights,
            resource_type=resource_type,
        )

    @classmethod
    def perfect(cls, resource_type: str = "") -> ResourceReward:
        """Create a perfect reward (all dimensions at 1.0).

        Args:
            resource_type: Optional resource type for weight preset.

        Returns:
            ResourceReward with all dimensions at 1.0.
        """
        weights = WEIGHT_PRESETS.get(resource_type, DEFAULT_WEIGHTS.copy())
        return cls(
            task_completion=1.0,
            efficiency=1.0,
            quality=1.0,
            safety=1.0,
            weights=weights,
            resource_type=resource_type,
        )

    def __add__(self, other: ResourceReward) -> ResourceReward:
        """Add two rewards (element-wise, clamped to 1.0).

        Useful for accumulating rewards over multiple evaluations.

        Args:
            other: Reward to add.

        Returns:
            New reward with summed dimensions.
        """
        # Merge extra dimensions
        merged_extra = self.extra.copy()
        for key, value in other.extra.items():
            merged_extra[key] = merged_extra.get(key, 0.0) + value

        return ResourceReward(
            task_completion=self.task_completion + other.task_completion,
            efficiency=self.efficiency + other.efficiency,
            quality=self.quality + other.quality,
            safety=self.safety + other.safety,
            extra=merged_extra,
            weights=self.weights.copy(),
            resource_id=self.resource_id or other.resource_id,
            resource_type=self.resource_type or other.resource_type,
        )

    def __mul__(self, scalar: float) -> ResourceReward:
        """Multiply reward by scalar.

        Useful for weighting or discounting rewards.

        Args:
            scalar: Value to multiply by.

        Returns:
            New reward with scaled dimensions.
        """
        return ResourceReward(
            task_completion=self.task_completion * scalar,
            efficiency=self.efficiency * scalar,
            quality=self.quality * scalar,
            safety=self.safety * scalar,
            extra={k: v * scalar for k, v in self.extra.items()},
            weights=self.weights.copy(),
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            trace_id=self.trace_id,
            metadata=self.metadata.copy(),
        )

    def __rmul__(self, scalar: float) -> ResourceReward:
        """Right multiplication by scalar."""
        return self.__mul__(scalar)


def aggregate_rewards(
    rewards: list[ResourceReward],
    method: str = "mean",
) -> ResourceReward:
    """Aggregate multiple rewards into a single reward.

    Args:
        rewards: List of rewards to aggregate.
        method: Aggregation method ("mean", "max", "min", "sum").

    Returns:
        Aggregated reward.

    Raises:
        ValueError: If method is unknown or rewards list is empty.
    """
    if not rewards:
        raise ValueError("Cannot aggregate empty list of rewards")

    if method == "mean":
        n = len(rewards)
        # Calculate mean directly to avoid clamping during summation
        task_completion = sum(r.task_completion for r in rewards) / n
        efficiency = sum(r.efficiency for r in rewards) / n
        quality = sum(r.quality for r in rewards) / n
        safety = sum(r.safety for r in rewards) / n

        # Merge extra dimensions
        all_extra_keys = set()
        for r in rewards:
            all_extra_keys.update(r.extra.keys())
        extra = {
            k: sum(r.extra.get(k, 0.0) for r in rewards) / n
            for k in all_extra_keys
        }

        return ResourceReward(
            task_completion=task_completion,
            efficiency=efficiency,
            quality=quality,
            safety=safety,
            extra=extra,
            weights=rewards[0].weights,
            resource_id=rewards[0].resource_id,
            resource_type=rewards[0].resource_type,
        )

    elif method == "max":
        result = rewards[0]
        for reward in rewards[1:]:
            result = ResourceReward(
                task_completion=max(result.task_completion, reward.task_completion),
                efficiency=max(result.efficiency, reward.efficiency),
                quality=max(result.quality, reward.quality),
                safety=max(result.safety, reward.safety),
                extra={
                    k: max(result.extra.get(k, 0.0), reward.extra.get(k, 0.0))
                    for k in set(result.extra.keys()) | set(reward.extra.keys())
                },
                weights=result.weights,
                resource_id=result.resource_id,
                resource_type=result.resource_type,
            )
        return result

    elif method == "min":
        result = rewards[0]
        for reward in rewards[1:]:
            result = ResourceReward(
                task_completion=min(result.task_completion, reward.task_completion),
                efficiency=min(result.efficiency, reward.efficiency),
                quality=min(result.quality, reward.quality),
                safety=min(result.safety, reward.safety),
                extra={
                    k: min(result.extra.get(k, 1.0), reward.extra.get(k, 1.0))
                    for k in set(result.extra.keys()) | set(reward.extra.keys())
                },
                weights=result.weights,
                resource_id=result.resource_id,
                resource_type=result.resource_type,
            )
        return result

    elif method == "sum":
        return sum(rewards, ResourceReward.zero())

    else:
        raise ValueError(
            f"Unknown aggregation method: {method}. "
            f"Valid methods: mean, max, min, sum"
        )


def compare_rewards(
    reward_a: ResourceReward,
    reward_b: ResourceReward,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compare two rewards and return detailed comparison.

    Args:
        reward_a: First reward.
        reward_b: Second reward.
        weights: Custom weights for comparison.

    Returns:
        Dictionary with comparison results.
    """
    composite_a = reward_a.composite(weights)
    composite_b = reward_b.composite(weights)

    return {
        "composite_a": composite_a,
        "composite_b": composite_b,
        "winner": "a" if composite_a > composite_b else ("b" if composite_b > composite_a else "tie"),
        "delta": composite_a - composite_b,
        "improvement_percent": reward_a.improvement_over(reward_b),
        "dimension_delta": reward_a.delta(reward_b),
    }


def create_reward(
    task_completion: float = 0.0,
    efficiency: float = 0.0,
    quality: float = 0.0,
    safety: float = 1.0,
    resource_type: str = "",
    **extra: float,
) -> ResourceReward:
    """Convenience factory for creating rewards.

    Args:
        task_completion: Task completion score.
        efficiency: Efficiency score.
        quality: Quality score.
        safety: Safety score.
        resource_type: Resource type for weight preset.
        **extra: Additional dimensions.

    Returns:
        ResourceReward instance.
    """
    weights = WEIGHT_PRESETS.get(resource_type, DEFAULT_WEIGHTS.copy())
    return ResourceReward(
        task_completion=task_completion,
        efficiency=efficiency,
        quality=quality,
        safety=safety,
        extra=extra,
        weights=weights,
        resource_type=resource_type,
    )
