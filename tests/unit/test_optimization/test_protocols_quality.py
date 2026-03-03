"""Unit tests for the quality scoring protocol module."""

from __future__ import annotations

from harness.optimization.protocols.quality import (
    ACCEPT_EXECUTION_THRESHOLD,
    ACCEPT_QUALITY_THRESHOLD,
    ACCURACY_WEIGHT,
    CLARITY_WEIGHT,
    COMPLETENESS_WEIGHT,
    REFINE_EXECUTION_THRESHOLD,
    CombinedScore,
    ExecutionScore,
    QualityScore,
)


class TestQualityScoreConstants:
    """Verify weight and threshold constants."""

    def test_weights_sum_to_one(self) -> None:
        total = COMPLETENESS_WEIGHT + ACCURACY_WEIGHT + CLARITY_WEIGHT
        assert abs(total - 1.0) < 1e-9

    def test_completeness_weight(self) -> None:
        assert COMPLETENESS_WEIGHT == 0.35

    def test_accuracy_weight(self) -> None:
        assert ACCURACY_WEIGHT == 0.35

    def test_clarity_weight(self) -> None:
        assert CLARITY_WEIGHT == 0.30

    def test_accept_quality_threshold(self) -> None:
        assert ACCEPT_QUALITY_THRESHOLD == 0.85

    def test_accept_execution_threshold(self) -> None:
        assert ACCEPT_EXECUTION_THRESHOLD == 0.80

    def test_refine_execution_threshold(self) -> None:
        assert REFINE_EXECUTION_THRESHOLD == 0.50


class TestQualityScore:
    """Verify QualityScore dataclass behavior."""

    def test_auto_calculation(self) -> None:
        score = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        expected = 0.35 * 0.8 + 0.35 * 0.9 + 0.30 * 0.7
        assert abs(score.overall - expected) < 1e-9

    def test_auto_calculation_value(self) -> None:
        score = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        assert abs(score.overall - 0.805) < 1e-9

    def test_explicit_overall_preserved(self) -> None:
        score = QualityScore(
            completeness=0.8, accuracy=0.9, clarity=0.7, overall=0.5
        )
        assert score.overall == 0.5

    def test_no_auto_calc_when_dimensions_zero(self) -> None:
        score = QualityScore()
        assert score.overall == 0.0

    def test_meets_threshold_true(self) -> None:
        score = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        assert score.meets_threshold(0.85)

    def test_meets_threshold_false(self) -> None:
        score = QualityScore(completeness=0.5, accuracy=0.5, clarity=0.5)
        assert not score.meets_threshold(0.85)

    def test_meets_threshold_exact_boundary(self) -> None:
        score = QualityScore(overall=0.85)
        assert score.meets_threshold(0.85)

    def test_to_dict(self) -> None:
        score = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        d = score.to_dict()
        assert d["completeness"] == 0.8
        assert d["accuracy"] == 0.9
        assert d["clarity"] == 0.7
        assert "overall" in d

    def test_from_dict_roundtrip(self) -> None:
        original = QualityScore(completeness=0.8, accuracy=0.9, clarity=0.7)
        restored = QualityScore.from_dict(original.to_dict())
        assert restored.completeness == original.completeness
        assert restored.accuracy == original.accuracy
        assert restored.clarity == original.clarity
        assert abs(restored.overall - original.overall) < 1e-9

    def test_from_dict_empty_defaults_to_zeros(self) -> None:
        score = QualityScore.from_dict({})
        assert score.completeness == 0.0
        assert score.accuracy == 0.0
        assert score.clarity == 0.0
        assert score.overall == 0.0


class TestExecutionScore:
    """Verify ExecutionScore dataclass behavior."""

    def test_creation_defaults(self) -> None:
        score = ExecutionScore()
        assert score.pass_at_1 == 0.0
        assert score.pass_at_k == 0.0
        assert score.pass_pow_k == 0.0
        assert score.k == 3
        assert score.total_scenarios == 0
        assert score.by_level == {}
        assert score.by_capability == {}

    def test_creation_with_values(self) -> None:
        score = ExecutionScore(
            pass_at_1=0.85,
            pass_at_k=0.95,
            pass_pow_k=0.90,
            k=5,
            total_scenarios=20,
            by_level={"basic": 0.9},
            by_capability={"async": 0.8},
        )
        assert score.pass_at_1 == 0.85
        assert score.k == 5
        assert score.total_scenarios == 20

    def test_none_sentinel(self) -> None:
        score = ExecutionScore.none()
        assert score.pass_at_1 == 0.0
        assert score.pass_at_k == 0.0
        assert score.pass_pow_k == 0.0
        assert score.total_scenarios == 0

    def test_has_results_false_when_empty(self) -> None:
        score = ExecutionScore()
        assert not score.has_results

    def test_has_results_true_with_scenarios(self) -> None:
        score = ExecutionScore(total_scenarios=5)
        assert score.has_results

    def test_to_dict(self) -> None:
        score = ExecutionScore(pass_at_1=0.8, k=5, total_scenarios=10)
        d = score.to_dict()
        assert d["pass_at_1"] == 0.8
        assert d["k"] == 5
        assert d["total_scenarios"] == 10

    def test_from_dict_roundtrip(self) -> None:
        original = ExecutionScore(
            pass_at_1=0.85,
            pass_at_k=0.95,
            pass_pow_k=0.90,
            k=5,
            total_scenarios=20,
            by_level={"basic": 0.9},
            by_capability={"async": 0.8},
        )
        restored = ExecutionScore.from_dict(original.to_dict())
        assert restored.pass_at_1 == original.pass_at_1
        assert restored.pass_at_k == original.pass_at_k
        assert restored.pass_pow_k == original.pass_pow_k
        assert restored.k == original.k
        assert restored.total_scenarios == original.total_scenarios
        assert restored.by_level == original.by_level
        assert restored.by_capability == original.by_capability

    def test_from_dict_empty(self) -> None:
        score = ExecutionScore.from_dict({})
        assert score.pass_at_1 == 0.0
        assert score.total_scenarios == 0


class TestCombinedScore:
    """Verify CombinedScore recommendation logic."""

    def test_accept_both_high(self) -> None:
        quality = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        execution = ExecutionScore(pass_pow_k=0.85, total_scenarios=10)
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "ACCEPT"

    def test_accept_quality_high_no_execution(self) -> None:
        quality = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        execution = ExecutionScore.none()
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "ACCEPT"

    def test_refine_quality_high_execution_low(self) -> None:
        quality = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        execution = ExecutionScore(pass_pow_k=0.60, total_scenarios=10)
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "REFINE"

    def test_refine_quality_low_execution_meets_refine(self) -> None:
        quality = QualityScore(completeness=0.5, accuracy=0.5, clarity=0.5)
        execution = ExecutionScore(pass_pow_k=0.55, total_scenarios=10)
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "REFINE"

    def test_reject_both_low(self) -> None:
        quality = QualityScore(completeness=0.3, accuracy=0.3, clarity=0.3)
        execution = ExecutionScore(pass_pow_k=0.2, total_scenarios=10)
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "REJECT"

    def test_reject_quality_low_no_execution(self) -> None:
        quality = QualityScore(completeness=0.3, accuracy=0.3, clarity=0.3)
        execution = ExecutionScore.none()
        combined = CombinedScore(quality=quality, execution=execution)
        assert combined.recommendation == "REJECT"

    def test_to_dict(self) -> None:
        quality = QualityScore(completeness=0.9, accuracy=0.9, clarity=0.9)
        execution = ExecutionScore(pass_pow_k=0.85, total_scenarios=10)
        combined = CombinedScore(quality=quality, execution=execution)
        d = combined.to_dict()
        assert "quality" in d
        assert "execution" in d
        assert "recommendation" in d
