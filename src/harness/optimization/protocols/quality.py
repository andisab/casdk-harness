"""Quality scoring protocol for multi-resource optimization pipeline.

Provides dataclasses for quality assessment, execution evaluation, and
combined scoring with recommendation logic (ACCEPT / REFINE / REJECT).

Usage:
    from harness.optimization.protocols.quality import (
        QualityScore,
        ExecutionScore,
        CombinedScore,
    )

    quality = QualityScore(completeness=0.9, accuracy=0.85, clarity=0.8)
    execution = ExecutionScore(pass_pow_k=0.90, total_scenarios=20)
    combined = CombinedScore(quality=quality, execution=execution)
    print(combined.recommendation)  # "ACCEPT"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -- weight constants ----------------------------------------------------------

COMPLETENESS_WEIGHT: float = 0.35
ACCURACY_WEIGHT: float = 0.35
CLARITY_WEIGHT: float = 0.30

# -- threshold constants -------------------------------------------------------

ACCEPT_QUALITY_THRESHOLD: float = 0.85
ACCEPT_EXECUTION_THRESHOLD: float = 0.80
REFINE_EXECUTION_THRESHOLD: float = 0.50


@dataclass
class QualityScore:
    """Content quality score across three dimensions.

    When ``overall`` is left at 0.0 and at least one dimension is non-zero,
    ``__post_init__`` computes the weighted average automatically.

    Attributes:
        completeness: How thoroughly the resource covers requirements.
        accuracy: Correctness of the resource content.
        clarity: Readability and structural clarity.
        overall: Weighted combination; auto-calculated if not provided.
    """

    completeness: float = 0.0
    accuracy: float = 0.0
    clarity: float = 0.0
    overall: float = 0.0

    def __post_init__(self) -> None:
        has_dimensions = (
            self.completeness != 0.0
            or self.accuracy != 0.0
            or self.clarity != 0.0
        )
        if has_dimensions and self.overall == 0.0:
            self.overall = (
                COMPLETENESS_WEIGHT * self.completeness
                + ACCURACY_WEIGHT * self.accuracy
                + CLARITY_WEIGHT * self.clarity
            )

    def meets_threshold(self, threshold: float) -> bool:
        """Return True if ``overall`` is at or above *threshold*."""
        return self.overall >= threshold

    def to_dict(self) -> dict[str, float]:
        """Serialize to a plain dictionary."""
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "clarity": self.clarity,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityScore:
        """Deserialize from a dictionary, defaulting missing keys to 0.0."""
        return cls(
            completeness=float(data.get("completeness", 0.0)),
            accuracy=float(data.get("accuracy", 0.0)),
            clarity=float(data.get("clarity", 0.0)),
            overall=float(data.get("overall", 0.0)),
        )


@dataclass
class ExecutionScore:
    """Execution-based evaluation score from running test scenarios.

    Attributes:
        pass_at_1: Fraction of scenarios passed on the first attempt.
        pass_at_k: Fraction of scenarios passed within *k* attempts.
        pass_pow_k: ``pass^k`` composite metric (power-weighted).
        k: Number of attempts per scenario.
        total_scenarios: How many scenarios were evaluated.
        by_level: Pass rates broken down by difficulty level.
        by_capability: Pass rates broken down by capability area.
    """

    pass_at_1: float = 0.0
    pass_at_k: float = 0.0
    pass_pow_k: float = 0.0
    k: int = 3
    total_scenarios: int = 0
    by_level: dict[str, float] = field(default_factory=dict)
    by_capability: dict[str, float] = field(default_factory=dict)

    @classmethod
    def none(cls) -> ExecutionScore:
        """Return an empty sentinel representing no execution results."""
        return cls()

    @property
    def has_results(self) -> bool:
        """True if at least one scenario was evaluated."""
        return self.total_scenarios > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "pass_at_1": self.pass_at_1,
            "pass_at_k": self.pass_at_k,
            "pass_pow_k": self.pass_pow_k,
            "k": self.k,
            "total_scenarios": self.total_scenarios,
            "by_level": dict(self.by_level),
            "by_capability": dict(self.by_capability),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionScore:
        """Deserialize from a dictionary, defaulting missing keys."""
        return cls(
            pass_at_1=float(data.get("pass_at_1", 0.0)),
            pass_at_k=float(data.get("pass_at_k", 0.0)),
            pass_pow_k=float(data.get("pass_pow_k", 0.0)),
            k=int(data.get("k", 3)),
            total_scenarios=int(data.get("total_scenarios", 0)),
            by_level=dict(data.get("by_level", {})),
            by_capability=dict(data.get("by_capability", {})),
        )


@dataclass
class CombinedScore:
    """Combined quality and execution score with recommendation logic.

    Recommendation rules:
        - **ACCEPT**: quality >= 0.85 AND (no execution results OR pass^k >= 0.80)
        - **REFINE**: quality meets threshold but execution below 0.80,
          OR execution pass^k >= 0.50 (regardless of quality)
        - **REJECT**: everything else

    Attributes:
        quality: Content quality assessment.
        execution: Execution-based evaluation (may be empty sentinel).
    """

    quality: QualityScore
    execution: ExecutionScore

    @property
    def recommendation(self) -> str:
        """Derive ACCEPT / REFINE / REJECT from scores."""
        q_meets = self.quality.meets_threshold(ACCEPT_QUALITY_THRESHOLD)
        has_exec = self.execution.has_results

        if q_meets and (not has_exec or self.execution.pass_pow_k >= ACCEPT_EXECUTION_THRESHOLD):
            return "ACCEPT"

        if q_meets and has_exec:
            # Quality is high but execution is below ACCEPT threshold
            return "REFINE"

        if has_exec and self.execution.pass_pow_k >= REFINE_EXECUTION_THRESHOLD:
            return "REFINE"

        return "REJECT"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary including the recommendation."""
        return {
            "quality": self.quality.to_dict(),
            "execution": self.execution.to_dict(),
            "recommendation": self.recommendation,
        }
