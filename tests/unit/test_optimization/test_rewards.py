"""Unit tests for CGF Reward System (Phase 0.5).

Tests ResourceReward dataclass, composite scoring, reward comparison,
aggregation, and integration with feedback types.
"""

from __future__ import annotations

import pytest

from harness.optimization.rewards import (
    DEFAULT_WEIGHTS,
    WEIGHT_PRESETS,
    ResourceReward,
    aggregate_rewards,
    compare_rewards,
    create_reward,
)
from harness.optimization.adapters.base import (
    AgentFeedback,
    CommandFeedback,
    PromptFeedback,
    SkillFeedback,
)


# =============================================================================
# ResourceReward Basic Tests
# =============================================================================


class TestResourceRewardBasics:
    """Test basic ResourceReward functionality."""

    def test_default_initialization(self) -> None:
        """Test default values on initialization."""
        reward = ResourceReward()

        assert reward.task_completion == 0.0
        assert reward.efficiency == 0.0
        assert reward.quality == 0.0
        assert reward.safety == 1.0  # Defaults to safe
        assert reward.extra == {}
        assert reward.weights == DEFAULT_WEIGHTS

    def test_custom_initialization(self) -> None:
        """Test custom values on initialization."""
        reward = ResourceReward(
            task_completion=0.9,
            efficiency=0.7,
            quality=0.8,
            safety=0.95,
            resource_id="test-agent",
            resource_type="agent",
        )

        assert reward.task_completion == 0.9
        assert reward.efficiency == 0.7
        assert reward.quality == 0.8
        assert reward.safety == 0.95
        assert reward.resource_id == "test-agent"
        assert reward.resource_type == "agent"

    def test_dimension_clamping(self) -> None:
        """Test that dimensions are clamped to [0.0, 1.0]."""
        reward = ResourceReward(
            task_completion=1.5,
            efficiency=-0.3,
            quality=2.0,
            safety=-1.0,
        )

        assert reward.task_completion == 1.0
        assert reward.efficiency == 0.0
        assert reward.quality == 1.0
        assert reward.safety == 0.0

    def test_extra_dimension_clamping(self) -> None:
        """Test that extra dimensions are clamped."""
        reward = ResourceReward(
            extra={"custom": 1.5, "negative": -0.2}
        )

        assert reward.extra["custom"] == 1.0
        assert reward.extra["negative"] == 0.0

    def test_core_dimensions_property(self) -> None:
        """Test core_dimensions property."""
        reward = ResourceReward(
            task_completion=0.9,
            efficiency=0.7,
            quality=0.8,
            safety=0.95,
        )

        core = reward.core_dimensions
        assert core == {
            "task_completion": 0.9,
            "efficiency": 0.7,
            "quality": 0.8,
            "safety": 0.95,
        }

    def test_all_dimensions_property(self) -> None:
        """Test all_dimensions property includes extra."""
        reward = ResourceReward(
            task_completion=0.9,
            extra={"custom": 0.5},
        )

        all_dims = reward.all_dimensions
        assert "task_completion" in all_dims
        assert "custom" in all_dims
        assert all_dims["custom"] == 0.5


# =============================================================================
# Composite Scoring Tests
# =============================================================================


class TestCompositeScoring:
    """Test composite score computation."""

    def test_composite_default_weights(self) -> None:
        """Test composite with default weights."""
        reward = ResourceReward(
            task_completion=1.0,
            efficiency=1.0,
            quality=1.0,
            safety=1.0,
        )

        # Perfect scores with default weights
        score = reward.composite()
        assert score == pytest.approx(1.0)

    def test_composite_zero_reward(self) -> None:
        """Test composite with all zeros."""
        reward = ResourceReward.zero()
        score = reward.composite()
        assert score == pytest.approx(0.0)

    def test_composite_custom_weights(self) -> None:
        """Test composite with custom weights."""
        reward = ResourceReward(
            task_completion=1.0,
            efficiency=0.0,
            quality=0.0,
            safety=0.0,
        )

        # Only task_completion has value, weight it 100%
        score = reward.composite(weights={"task_completion": 1.0})
        assert score == pytest.approx(1.0)

        # Weight efficiency which is 0
        score = reward.composite(weights={"efficiency": 1.0})
        assert score == pytest.approx(0.0)

    def test_composite_mixed_weights(self) -> None:
        """Test composite with mixed dimension values."""
        reward = ResourceReward(
            task_completion=0.8,
            efficiency=0.6,
            quality=0.9,
            safety=1.0,
        )

        # Default weights: task=0.4, efficiency=0.2, quality=0.3, safety=0.1
        expected = (0.8 * 0.4 + 0.6 * 0.2 + 0.9 * 0.3 + 1.0 * 0.1)
        score = reward.composite()
        assert score == pytest.approx(expected)

    def test_composite_with_extra_dimensions(self) -> None:
        """Test composite includes extra dimensions when enabled."""
        reward = ResourceReward(
            task_completion=0.5,
            extra={"custom": 1.0},
            weights={"task_completion": 0.5, "custom": 0.5},
        )

        score = reward.composite(include_extra=True)
        assert score == pytest.approx(0.75)

        # Without extra
        score_no_extra = reward.composite(include_extra=False)
        assert score_no_extra == pytest.approx(0.5)

    def test_composite_with_preset(self) -> None:
        """Test composite using weight presets."""
        reward = ResourceReward(
            task_completion=1.0,
            efficiency=1.0,
            quality=1.0,
            safety=1.0,
        )

        # All presets should work
        for preset in WEIGHT_PRESETS:
            score = reward.composite_with_preset(preset)
            assert score == pytest.approx(1.0)

    def test_composite_with_invalid_preset(self) -> None:
        """Test composite with invalid preset raises error."""
        reward = ResourceReward()

        with pytest.raises(ValueError, match="Unknown preset"):
            reward.composite_with_preset("invalid_preset")


# =============================================================================
# Reward Comparison Tests
# =============================================================================


class TestRewardComparison:
    """Test reward comparison methods."""

    def test_improvement_over_baseline(self) -> None:
        """Test improvement calculation."""
        baseline = ResourceReward(
            task_completion=0.5,
            efficiency=0.5,
            quality=0.5,
            safety=0.5,
        )
        new = ResourceReward(
            task_completion=1.0,
            efficiency=0.75,
            quality=0.5,
            safety=0.5,
        )

        improvement = new.improvement_over(baseline)

        # 100% improvement in task_completion
        assert improvement["task_completion"] == pytest.approx(100.0)
        # 50% improvement in efficiency
        assert improvement["efficiency"] == pytest.approx(50.0)
        # 0% change in quality
        assert improvement["quality"] == pytest.approx(0.0)

    def test_improvement_from_zero(self) -> None:
        """Test improvement when baseline is zero."""
        baseline = ResourceReward.zero()
        new = ResourceReward(task_completion=0.5)

        improvement = new.improvement_over(baseline)
        assert improvement["task_completion"] == pytest.approx(100.0)

    def test_improvement_with_extra_dimensions(self) -> None:
        """Test improvement includes extra dimensions."""
        baseline = ResourceReward(extra={"custom": 0.4})
        new = ResourceReward(extra={"custom": 0.8})

        improvement = new.improvement_over(baseline)
        assert improvement["custom"] == pytest.approx(100.0)

    def test_delta_calculation(self) -> None:
        """Test absolute delta calculation."""
        baseline = ResourceReward(
            task_completion=0.5,
            efficiency=0.6,
        )
        new = ResourceReward(
            task_completion=0.8,
            efficiency=0.4,
        )

        delta = new.delta(baseline)
        assert delta["task_completion"] == pytest.approx(0.3)
        assert delta["efficiency"] == pytest.approx(-0.2)

    def test_is_better_than(self) -> None:
        """Test is_better_than comparison."""
        reward_a = ResourceReward(
            task_completion=0.9,
            efficiency=0.8,
            quality=0.7,
            safety=1.0,
        )
        reward_b = ResourceReward(
            task_completion=0.5,
            efficiency=0.5,
            quality=0.5,
            safety=0.5,
        )

        assert reward_a.is_better_than(reward_b)
        assert not reward_b.is_better_than(reward_a)

    def test_is_better_than_with_custom_weights(self) -> None:
        """Test is_better_than with custom weights."""
        # A has better efficiency, B has better quality
        reward_a = ResourceReward(efficiency=1.0, quality=0.0)
        reward_b = ResourceReward(efficiency=0.0, quality=1.0)

        # Efficiency-focused comparison
        assert reward_a.is_better_than(
            reward_b, weights={"efficiency": 1.0, "quality": 0.0}
        )
        # Quality-focused comparison
        assert reward_b.is_better_than(
            reward_a, weights={"efficiency": 0.0, "quality": 1.0}
        )

    def test_meets_threshold_all(self) -> None:
        """Test meets_threshold with require_all=True."""
        reward = ResourceReward(
            task_completion=0.8,
            efficiency=0.6,
            quality=0.9,
        )

        # All thresholds met
        assert reward.meets_threshold({
            "task_completion": 0.7,
            "efficiency": 0.5,
        })

        # One threshold not met
        assert not reward.meets_threshold({
            "task_completion": 0.9,  # Not met
            "efficiency": 0.5,
        })

    def test_meets_threshold_any(self) -> None:
        """Test meets_threshold with require_all=False."""
        reward = ResourceReward(
            task_completion=0.8,
            efficiency=0.3,
        )

        # At least one threshold met
        assert reward.meets_threshold(
            {"task_completion": 0.7, "efficiency": 0.5},
            require_all=False,
        )

        # No thresholds met
        assert not reward.meets_threshold(
            {"task_completion": 0.9, "efficiency": 0.5},
            require_all=False,
        )


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Test reward serialization and deserialization."""

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        reward = ResourceReward(
            task_completion=0.9,
            efficiency=0.7,
            quality=0.8,
            safety=0.95,
            extra={"custom": 0.5},
            resource_id="test",
            resource_type="agent",
        )

        data = reward.to_dict()

        assert data["task_completion"] == 0.9
        assert data["efficiency"] == 0.7
        assert data["quality"] == 0.8
        assert data["safety"] == 0.95
        assert data["extra"]["custom"] == 0.5
        assert data["resource_id"] == "test"
        assert "composite" in data

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "task_completion": 0.9,
            "efficiency": 0.7,
            "quality": 0.8,
            "safety": 0.95,
            "extra": {"custom": 0.5},
            "resource_id": "test",
            "resource_type": "agent",
        }

        reward = ResourceReward.from_dict(data)

        assert reward.task_completion == 0.9
        assert reward.efficiency == 0.7
        assert reward.extra["custom"] == 0.5
        assert reward.resource_id == "test"

    def test_round_trip_serialization(self) -> None:
        """Test round-trip through dict."""
        original = ResourceReward(
            task_completion=0.9,
            efficiency=0.7,
            quality=0.8,
            safety=0.95,
            extra={"custom": 0.5},
            resource_id="test",
            resource_type="agent",
            metadata={"key": "value"},
        )

        restored = ResourceReward.from_dict(original.to_dict())

        assert restored.task_completion == original.task_completion
        assert restored.efficiency == original.efficiency
        assert restored.quality == original.quality
        assert restored.safety == original.safety
        assert restored.extra == original.extra
        assert restored.resource_id == original.resource_id


# =============================================================================
# Factory Method Tests
# =============================================================================


class TestFactoryMethods:
    """Test ResourceReward factory methods."""

    def test_zero_factory(self) -> None:
        """Test zero() factory creates all-zero reward."""
        reward = ResourceReward.zero()

        assert reward.task_completion == 0.0
        assert reward.efficiency == 0.0
        assert reward.quality == 0.0
        assert reward.safety == 0.0

    def test_zero_factory_with_resource_type(self) -> None:
        """Test zero() uses resource-specific weights."""
        reward = ResourceReward.zero(resource_type="agent")

        assert reward.resource_type == "agent"
        assert reward.weights == WEIGHT_PRESETS["agent"]

    def test_perfect_factory(self) -> None:
        """Test perfect() factory creates all-perfect reward."""
        reward = ResourceReward.perfect()

        assert reward.task_completion == 1.0
        assert reward.efficiency == 1.0
        assert reward.quality == 1.0
        assert reward.safety == 1.0

    def test_perfect_factory_with_resource_type(self) -> None:
        """Test perfect() uses resource-specific weights."""
        reward = ResourceReward.perfect(resource_type="command")

        assert reward.resource_type == "command"
        assert reward.weights == WEIGHT_PRESETS["command"]

    def test_from_feedback_agent(self) -> None:
        """Test from_feedback with AgentFeedback."""
        feedback = AgentFeedback(
            task_completed=True,
            resource_type="agent",
            resource_id="test-agent",
        )
        feedback.compute_efficiency_score()
        feedback.compute_reliability_score()

        reward = ResourceReward.from_feedback(feedback)

        assert reward.task_completion == 1.0
        assert reward.resource_type == "agent"
        assert reward.resource_id == "test-agent"
        assert reward.weights == WEIGHT_PRESETS["agent"]

    def test_from_feedback_skill(self) -> None:
        """Test from_feedback with SkillFeedback."""
        feedback = SkillFeedback(
            execution_count=10,
            execution_success_count=9,
            output_quality=0.8,
            resource_type="skill",
        )

        reward = ResourceReward.from_feedback(feedback)

        assert reward.task_completion == pytest.approx(0.9)
        assert reward.quality == 0.8
        assert reward.resource_type == "skill"

    def test_from_feedback_prompt(self) -> None:
        """Test from_feedback with PromptFeedback."""
        feedback = PromptFeedback(
            success=True,
            response_quality=0.85,
            clarity_score=0.9,
            resource_type="prompt",
        )

        reward = ResourceReward.from_feedback(feedback)

        assert reward.task_completion == 1.0
        assert reward.quality == 0.85
        assert "clarity" in reward.extra

    def test_from_feedback_command(self) -> None:
        """Test from_feedback with CommandFeedback."""
        feedback = CommandFeedback(
            success=True,
            output_quality=0.75,
            unauthorized_tool_attempts=0,
            resource_type="command",
        )

        reward = ResourceReward.from_feedback(feedback)

        assert reward.task_completion == 1.0
        assert reward.quality == 0.75
        assert reward.safety == 1.0  # No unauthorized attempts

    def test_from_feedback_custom_weights(self) -> None:
        """Test from_feedback with custom weights."""
        feedback = AgentFeedback(task_completed=True)
        custom_weights = {"task_completion": 1.0}

        reward = ResourceReward.from_feedback(feedback, weights=custom_weights)

        assert reward.weights == custom_weights


# =============================================================================
# Arithmetic Operations Tests
# =============================================================================


class TestArithmeticOperations:
    """Test reward arithmetic operations."""

    def test_add_rewards(self) -> None:
        """Test adding two rewards."""
        a = ResourceReward(task_completion=0.5, efficiency=0.3)
        b = ResourceReward(task_completion=0.3, efficiency=0.4)

        result = a + b

        # Values are clamped to 1.0
        assert result.task_completion == 0.8
        assert result.efficiency == 0.7

    def test_add_rewards_with_clamping(self) -> None:
        """Test addition clamps to 1.0."""
        a = ResourceReward(task_completion=0.8)
        b = ResourceReward(task_completion=0.5)

        result = a + b

        assert result.task_completion == 1.0  # Clamped

    def test_add_rewards_merges_extra(self) -> None:
        """Test addition merges extra dimensions."""
        a = ResourceReward(extra={"custom": 0.3})
        b = ResourceReward(extra={"custom": 0.2, "other": 0.5})

        result = a + b

        assert result.extra["custom"] == 0.5
        assert result.extra["other"] == 0.5

    def test_multiply_by_scalar(self) -> None:
        """Test multiplying reward by scalar."""
        reward = ResourceReward(
            task_completion=0.8,
            efficiency=0.6,
        )

        result = reward * 0.5

        assert result.task_completion == pytest.approx(0.4)
        assert result.efficiency == pytest.approx(0.3)

    def test_rmul_scalar(self) -> None:
        """Test right multiplication by scalar."""
        reward = ResourceReward(task_completion=0.8)

        result = 0.5 * reward

        assert result.task_completion == pytest.approx(0.4)

    def test_multiply_scales_extra(self) -> None:
        """Test multiplication scales extra dimensions."""
        reward = ResourceReward(extra={"custom": 0.8})

        result = reward * 0.5

        assert result.extra["custom"] == pytest.approx(0.4)


# =============================================================================
# Aggregation Tests
# =============================================================================


class TestAggregation:
    """Test reward aggregation functions."""

    def test_aggregate_mean(self) -> None:
        """Test mean aggregation."""
        rewards = [
            ResourceReward(task_completion=0.8),
            ResourceReward(task_completion=0.6),
            ResourceReward(task_completion=0.4),
        ]

        result = aggregate_rewards(rewards, method="mean")

        assert result.task_completion == pytest.approx(0.6)

    def test_aggregate_max(self) -> None:
        """Test max aggregation."""
        rewards = [
            ResourceReward(task_completion=0.4, efficiency=0.9),
            ResourceReward(task_completion=0.8, efficiency=0.3),
        ]

        result = aggregate_rewards(rewards, method="max")

        assert result.task_completion == 0.8
        assert result.efficiency == 0.9

    def test_aggregate_min(self) -> None:
        """Test min aggregation."""
        rewards = [
            ResourceReward(task_completion=0.4, efficiency=0.9),
            ResourceReward(task_completion=0.8, efficiency=0.3),
        ]

        result = aggregate_rewards(rewards, method="min")

        assert result.task_completion == 0.4
        assert result.efficiency == 0.3

    def test_aggregate_sum(self) -> None:
        """Test sum aggregation."""
        rewards = [
            ResourceReward(task_completion=0.3),
            ResourceReward(task_completion=0.4),
        ]

        result = aggregate_rewards(rewards, method="sum")

        assert result.task_completion == 0.7

    def test_aggregate_empty_list(self) -> None:
        """Test aggregation with empty list raises error."""
        with pytest.raises(ValueError, match="Cannot aggregate empty"):
            aggregate_rewards([])

    def test_aggregate_invalid_method(self) -> None:
        """Test aggregation with invalid method raises error."""
        rewards = [ResourceReward()]

        with pytest.raises(ValueError, match="Unknown aggregation method"):
            aggregate_rewards(rewards, method="invalid")

    def test_aggregate_preserves_extra(self) -> None:
        """Test aggregation handles extra dimensions."""
        rewards = [
            ResourceReward(extra={"custom": 0.6}),
            ResourceReward(extra={"custom": 0.4}),
        ]

        result = aggregate_rewards(rewards, method="mean")

        assert result.extra["custom"] == pytest.approx(0.5)


# =============================================================================
# Compare Rewards Function Tests
# =============================================================================


class TestCompareRewards:
    """Test compare_rewards utility function."""

    def test_compare_rewards_a_wins(self) -> None:
        """Test comparison where A wins."""
        a = ResourceReward(task_completion=0.9)
        b = ResourceReward(task_completion=0.5)

        result = compare_rewards(a, b)

        assert result["winner"] == "a"
        assert result["composite_a"] > result["composite_b"]
        assert result["delta"] > 0

    def test_compare_rewards_b_wins(self) -> None:
        """Test comparison where B wins."""
        a = ResourceReward(task_completion=0.3)
        b = ResourceReward(task_completion=0.8)

        result = compare_rewards(a, b)

        assert result["winner"] == "b"
        assert result["composite_b"] > result["composite_a"]
        assert result["delta"] < 0

    def test_compare_rewards_tie(self) -> None:
        """Test comparison with tie."""
        a = ResourceReward(task_completion=0.5)
        b = ResourceReward(task_completion=0.5)

        result = compare_rewards(a, b)

        assert result["winner"] == "tie"
        assert result["delta"] == pytest.approx(0.0)

    def test_compare_rewards_with_custom_weights(self) -> None:
        """Test comparison with custom weights."""
        a = ResourceReward(efficiency=1.0, quality=0.0)
        b = ResourceReward(efficiency=0.0, quality=1.0)

        # Efficiency-focused weights
        result = compare_rewards(
            a, b, weights={"efficiency": 1.0, "quality": 0.0}
        )
        assert result["winner"] == "a"


# =============================================================================
# Create Reward Factory Tests
# =============================================================================


class TestCreateReward:
    """Test create_reward factory function."""

    def test_create_reward_basic(self) -> None:
        """Test basic create_reward usage."""
        reward = create_reward(
            task_completion=0.9,
            efficiency=0.7,
        )

        assert reward.task_completion == 0.9
        assert reward.efficiency == 0.7

    def test_create_reward_with_resource_type(self) -> None:
        """Test create_reward applies resource-specific weights."""
        reward = create_reward(resource_type="agent")

        assert reward.resource_type == "agent"
        assert reward.weights == WEIGHT_PRESETS["agent"]

    def test_create_reward_with_extra(self) -> None:
        """Test create_reward with extra dimensions."""
        reward = create_reward(
            task_completion=0.8,
            custom_dim=0.5,
            another_dim=0.3,
        )

        assert reward.task_completion == 0.8
        assert reward.extra["custom_dim"] == 0.5
        assert reward.extra["another_dim"] == 0.3


# =============================================================================
# Weight Presets Tests
# =============================================================================


class TestWeightPresets:
    """Test weight preset configurations."""

    def test_all_presets_sum_to_one(self) -> None:
        """Test all weight presets sum to approximately 1.0."""
        for preset_name, weights in WEIGHT_PRESETS.items():
            total = sum(weights.values())
            assert total == pytest.approx(1.0), f"Preset {preset_name} sums to {total}"

    def test_all_presets_have_core_dimensions(self) -> None:
        """Test all presets include core dimensions."""
        core = {"task_completion", "efficiency", "quality", "safety"}

        for preset_name, weights in WEIGHT_PRESETS.items():
            assert core <= set(weights.keys()), f"Preset {preset_name} missing core dims"

    def test_resource_type_presets_exist(self) -> None:
        """Test presets exist for all resource types."""
        resource_types = ["agent", "skill", "prompt", "command"]

        for rt in resource_types:
            assert rt in WEIGHT_PRESETS, f"Missing preset for {rt}"

    def test_default_weights_is_balanced(self) -> None:
        """Test DEFAULT_WEIGHTS matches balanced preset."""
        assert DEFAULT_WEIGHTS == WEIGHT_PRESETS["balanced"]
