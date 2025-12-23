"""Output validators for test cases.

Provides different validation strategies for agent outputs:
- ExactValidator: Exact string match
- ContainsValidator: Substring match
- RegexValidator: Regular expression match
- LLMJudgeValidator: LLM-based evaluation

Example usage:
    from harness.optimization.testcases import (
        get_validator,
        ValidationConfig,
        ValidationType,
    )

    config = ValidationConfig(type=ValidationType.CONTAINS, criteria="def ")
    validator = get_validator(config)
    score = await validator.validate("def sort(lst): return sorted(lst)")
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

from harness.optimization.testcases.models import ValidationConfig, ValidationType

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class Validator(ABC):
    """Abstract base class for output validators."""

    def __init__(self, config: ValidationConfig) -> None:
        """Initialize validator with configuration.

        Args:
            config: Validation configuration.
        """
        self.config = config

    @abstractmethod
    async def validate(self, output: str) -> float:
        """Validate agent output.

        Args:
            output: Agent's output text.

        Returns:
            Validation score (0.0 - 1.0).
        """
        pass

    def _apply_partial_credit(self, score: float) -> float:
        """Apply partial credit policy.

        Args:
            score: Raw validation score.

        Returns:
            Score adjusted for partial credit setting.
        """
        if self.config.partial_credit:
            return score
        # Binary scoring: >= 0.5 passes, < 0.5 fails
        return 1.0 if score >= 0.5 else 0.0


class ExactValidator(Validator):
    """Validates output matches criteria exactly."""

    async def validate(self, output: str) -> float:
        """Check if output exactly matches criteria.

        Args:
            output: Agent's output text.

        Returns:
            1.0 if exact match, 0.0 otherwise.
        """
        matches = output.strip() == self.config.criteria.strip()
        score = 1.0 if matches else 0.0
        return self._apply_partial_credit(score)


class ContainsValidator(Validator):
    """Validates output contains the criteria substring."""

    async def validate(self, output: str) -> float:
        """Check if output contains criteria substring.

        Args:
            output: Agent's output text.

        Returns:
            1.0 if contains, 0.0 otherwise.
        """
        contains = self.config.criteria in output
        score = 1.0 if contains else 0.0
        return self._apply_partial_credit(score)


class RegexValidator(Validator):
    """Validates output matches a regular expression."""

    def __init__(self, config: ValidationConfig) -> None:
        """Initialize with compiled regex.

        Args:
            config: Validation configuration with regex pattern.
        """
        super().__init__(config)
        try:
            self._pattern = re.compile(config.criteria, re.MULTILINE | re.DOTALL)
        except re.error as e:
            logger.error("Invalid regex pattern", pattern=config.criteria, error=str(e))
            raise ValueError(f"Invalid regex pattern: {e}") from e

    async def validate(self, output: str) -> float:
        """Check if output matches regex pattern.

        Args:
            output: Agent's output text.

        Returns:
            1.0 if matches, 0.0 otherwise.
        """
        matches = bool(self._pattern.search(output))
        score = 1.0 if matches else 0.0
        return self._apply_partial_credit(score)


class LLMJudgeValidator(Validator):
    """Validates output using an LLM judge.

    Uses Claude to evaluate the output against criteria.
    The criteria should be a prompt describing what to evaluate.
    """

    async def validate(self, output: str) -> float:
        """Evaluate output using LLM judge.

        Args:
            output: Agent's output text.

        Returns:
            Score from 0.0 to 1.0 based on LLM evaluation.
        """
        try:
            score = await self._call_llm_judge(output)
            return self._apply_partial_credit(score)
        except Exception as e:
            logger.error("LLM judge evaluation failed", error=str(e))
            # Return 0 on failure to be conservative
            return 0.0

    async def _call_llm_judge(self, output: str) -> float:
        """Call LLM to evaluate output.

        Args:
            output: Agent's output text.

        Returns:
            Score from 0.0 to 1.0.
        """
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()

        system_prompt = """You are an evaluation judge for AI agent outputs.
Evaluate the given output against the provided criteria.
Respond with ONLY a score from 0.0 to 1.0, where:
- 1.0 = Fully meets all criteria
- 0.0 = Does not meet criteria at all
- Values in between indicate partial fulfillment

Output ONLY the numeric score, nothing else."""

        user_prompt = f"""## Evaluation Criteria
{self.config.criteria}

## Agent Output to Evaluate
{output}

## Your Score (0.0 to 1.0):"""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract score from response
        score_text = response.content[0].text.strip()
        try:
            score = float(score_text)
            # Clamp to valid range
            return max(0.0, min(1.0, score))
        except ValueError:
            logger.warning(
                "Could not parse LLM judge score",
                response=score_text,
            )
            # Try to find a number in the response
            numbers = re.findall(r"(\d+\.?\d*)", score_text)
            if numbers:
                score = float(numbers[0])
                return max(0.0, min(1.0, score))
            return 0.0


class CompositeValidator(Validator):
    """Combines multiple validators with weighted scoring."""

    def __init__(
        self,
        validators: list[tuple[Validator, float]],
        config: ValidationConfig | None = None,
    ) -> None:
        """Initialize with list of validators and weights.

        Args:
            validators: List of (validator, weight) tuples.
            config: Optional base config (not used directly).
        """
        if config is None:
            # Create a dummy config for the base class
            config = ValidationConfig(type=ValidationType.CONTAINS, criteria="")
        super().__init__(config)
        self.validators = validators

        # Normalize weights
        total_weight = sum(w for _, w in validators)
        if total_weight > 0:
            self.validators = [(v, w / total_weight) for v, w in validators]

    async def validate(self, output: str) -> float:
        """Validate using all validators and combine scores.

        Args:
            output: Agent's output text.

        Returns:
            Weighted average score.
        """
        total_score = 0.0
        for validator, weight in self.validators:
            score = await validator.validate(output)
            total_score += score * weight
        return total_score


def get_validator(config: ValidationConfig) -> Validator:
    """Get the appropriate validator for a validation config.

    Args:
        config: Validation configuration.

    Returns:
        Validator instance.

    Raises:
        ValueError: If validation type is not recognized.
    """
    validator_map = {
        ValidationType.EXACT: ExactValidator,
        ValidationType.CONTAINS: ContainsValidator,
        ValidationType.REGEX: RegexValidator,
        ValidationType.LLM_JUDGE: LLMJudgeValidator,
    }

    validator_type = config.type
    if isinstance(validator_type, str):
        validator_type = ValidationType(validator_type.lower())

    validator_class = validator_map.get(validator_type)
    if validator_class is None:
        raise ValueError(f"Unknown validation type: {config.type}")

    return validator_class(config)
