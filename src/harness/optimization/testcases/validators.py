"""Output validators for test cases.

Provides different validation strategies for agent outputs:
- ExactValidator: Exact string match
- ContainsValidator: Substring match
- RegexValidator: Regular expression match
- LLMJudgeValidator: LLM-based evaluation
- CodeValidator: Extract code from markdown, validate syntax and content
- CodeSyntaxValidator: Extract code and validate syntax only
- CodeLLMValidator: Extract code and use LLM judge on code only

Example usage:
    from harness.optimization.testcases import (
        get_validator,
        ValidationConfig,
        ValidationType,
    )

    # Simple contains validation
    config = ValidationConfig(type=ValidationType.CONTAINS, criteria="def ")
    validator = get_validator(config)
    score = await validator.validate("def sort(lst): return sorted(lst)")

    # Code validation with syntax checking
    config = ValidationConfig(
        type=ValidationType.CODE,
        criteria="def ",  # Content to find in extracted code
        require_syntax_valid=True,
        min_code_lines=3,
    )
    validator = get_validator(config)
    score = await validator.validate("```python\\ndef sort(lst):\\n    return sorted(lst)\\n```")
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from harness.optimization.testcases.models import ValidationConfig, ValidationType

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = structlog.get_logger(__name__)


# Shared HTTP client instance for validators (lazy initialization)
_shared_client: "AsyncAnthropic | None" = None

# Default model for LLM validators, can be overridden via set_eval_model()
DEFAULT_EVAL_MODEL = "claude-sonnet-4-20250514"
_eval_model_override: str | None = None


def set_eval_model(model: str | None) -> None:
    """Set the model to use for LLM validators.

    Args:
        model: Model name (sonnet, haiku, opus) or full model ID.
               None resets to default.
    """
    global _eval_model_override
    if model is None:
        _eval_model_override = None
        return

    # Map short names to full model IDs
    model_map = {
        "sonnet": "claude-sonnet-4-20250514",
        "haiku": "claude-3-5-haiku-20241022",
        "opus": "claude-opus-4-5-20250929",
    }
    _eval_model_override = model_map.get(model, model)


def get_eval_model() -> str:
    """Get the current eval model."""
    return _eval_model_override or DEFAULT_EVAL_MODEL


def get_shared_anthropic_client() -> "AsyncAnthropic":
    """Get or create a shared AsyncAnthropic client.

    Reuses a single client instance across all validators to avoid
    the overhead of creating new HTTP connections for each validation call.

    Returns:
        Shared AsyncAnthropic client instance.
    """
    global _shared_client
    if _shared_client is None:
        from anthropic import AsyncAnthropic
        _shared_client = AsyncAnthropic()
    return _shared_client


# =============================================================================
# Code Extraction Utilities
# =============================================================================


@dataclass
class ExtractedCode:
    """Result of code extraction from mixed text/code output."""

    code: str
    language: str | None
    source: str  # "markdown_block", "indented", "raw"
    line_count: int

    @property
    def is_empty(self) -> bool:
        """Check if extracted code is empty or whitespace only."""
        return not self.code.strip()


class CodeExtractor:
    """Extracts code from mixed text/code output (markdown blocks, etc.).

    Handles common patterns in LLM output:
    - Markdown code blocks (```python ... ```)
    - Indented code blocks
    - Raw code without markdown

    Example:
        extractor = CodeExtractor()
        result = extractor.extract('''
            Here's a solution:
            ```python
            def sort(lst):
                return sorted(lst)
            ```
        ''')
        print(result.code)  # "def sort(lst):\\n    return sorted(lst)"
    """

    # Pattern for markdown code blocks with optional language
    MARKDOWN_PATTERN = re.compile(
        r"```(?P<lang>\w+)?\s*\n(?P<code>.*?)\n\s*```",
        re.DOTALL,
    )

    # Pattern for indented code (4+ spaces or tabs)
    INDENTED_PATTERN = re.compile(
        r"^(?:[ ]{4,}|\t+).+$",
        re.MULTILINE,
    )

    def extract(
        self,
        output: str,
        preferred_language: str = "python",
    ) -> ExtractedCode:
        """Extract code from mixed text/code output.

        Priority order:
        1. Markdown code blocks with matching language
        2. Any markdown code block
        3. Indented code blocks
        4. Raw text as fallback

        Args:
            output: The mixed text/code output to extract from.
            preferred_language: Preferred language for code blocks.

        Returns:
            ExtractedCode with the extracted code and metadata.
        """
        # Try markdown code blocks first
        code_blocks = list(self.MARKDOWN_PATTERN.finditer(output))

        if code_blocks:
            # Prefer blocks with matching language
            for match in code_blocks:
                lang = match.group("lang")
                if lang and lang.lower() == preferred_language.lower():
                    code = match.group("code").strip()
                    return ExtractedCode(
                        code=code,
                        language=lang,
                        source="markdown_block",
                        line_count=len(code.splitlines()),
                    )

            # Fall back to first code block
            first = code_blocks[0]
            code = first.group("code").strip()
            return ExtractedCode(
                code=code,
                language=first.group("lang"),
                source="markdown_block",
                line_count=len(code.splitlines()),
            )

        # Try indented code blocks
        indented_lines = self.INDENTED_PATTERN.findall(output)
        if indented_lines:
            # Join consecutive indented lines
            code = "\n".join(line.lstrip() for line in indented_lines)
            return ExtractedCode(
                code=code,
                language=None,
                source="indented",
                line_count=len(code.splitlines()),
            )

        # Fallback: return raw text (may not be actual code)
        stripped = output.strip()
        return ExtractedCode(
            code=stripped,
            language=None,
            source="raw",
            line_count=len(stripped.splitlines()),
        )

    def extract_all(
        self,
        output: str,
        preferred_language: str = "python",
    ) -> list[ExtractedCode]:
        """Extract all code blocks from output.

        Args:
            output: The mixed text/code output to extract from.
            preferred_language: Preferred language (used for sorting results).

        Returns:
            List of all extracted code blocks, with preferred language first.
        """
        results: list[ExtractedCode] = []

        # Extract all markdown code blocks
        for match in self.MARKDOWN_PATTERN.finditer(output):
            code = match.group("code").strip()
            lang = match.group("lang")
            results.append(
                ExtractedCode(
                    code=code,
                    language=lang,
                    source="markdown_block",
                    line_count=len(code.splitlines()),
                )
            )

        # Sort: preferred language first
        results.sort(
            key=lambda x: (
                x.language != preferred_language if x.language else True,
                -x.line_count,  # Then by size (larger first)
            )
        )

        return results


def is_valid_python_syntax(code: str) -> tuple[bool, str | None]:
    """Check if code is syntactically valid Python.

    Args:
        code: Python code to validate.

    Returns:
        Tuple of (is_valid, error_message).
        error_message is None if valid.
    """
    try:
        compile(code, "<string>", "exec")
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


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
    """Validates output contains the criteria substring(s).

    If criteria contains comma-separated values (e.g., "foo, bar, baz"),
    ALL values must be present in the output for full score.
    With partial_credit=True, score is proportional to keywords found.
    """

    async def validate(self, output: str) -> float:
        """Check if output contains criteria substring(s).

        If criteria contains ", " (comma+space), it's treated as a list
        of required keywords - ALL must be present for full score.

        Args:
            output: Agent's output text.

        Returns:
            1.0 if all keywords present, 0.0 otherwise.
            With partial_credit, returns proportion of keywords found.
        """
        criteria = self.config.criteria

        # Check if criteria is a comma-separated list
        if ", " in criteria:
            keywords = [kw.strip() for kw in criteria.split(", ") if kw.strip()]
            if not keywords:
                return 0.0

            # Count how many keywords are found (case-insensitive)
            output_lower = output.lower()
            found = sum(1 for kw in keywords if kw.lower() in output_lower)

            if self.config.partial_credit:
                # Return proportion of keywords found
                return found / len(keywords)
            else:
                # All-or-nothing: all keywords must be present
                return 1.0 if found == len(keywords) else 0.0
        else:
            # Single keyword - exact substring match (case-sensitive)
            contains = criteria in output
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
        client = get_shared_anthropic_client()

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
            model=get_eval_model(),
            max_tokens=10,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        logger.debug(
            "LLM judge evaluation",
            model=get_eval_model(),
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


class CodeSyntaxValidator(Validator):
    """Validates that output contains syntactically valid code.

    Extracts code from markdown blocks or raw text and validates
    that it is syntactically correct Python.
    """

    def __init__(self, config: ValidationConfig) -> None:
        """Initialize code syntax validator.

        Args:
            config: Validation configuration with optional min_code_lines.
        """
        super().__init__(config)
        self._extractor = CodeExtractor()

    async def validate(self, output: str) -> float:
        """Extract code and validate syntax.

        Args:
            output: Agent's output text (may contain markdown).

        Returns:
            1.0 if valid Python syntax, 0.0 otherwise.
        """
        extracted = self._extractor.extract(output, self.config.language)

        if extracted.is_empty:
            logger.debug("No code extracted from output")
            return 0.0

        # Check minimum line count
        if (
            self.config.min_code_lines > 0
            and extracted.line_count < self.config.min_code_lines
        ):
            logger.debug(
                "Code too short",
                lines=extracted.line_count,
                required=self.config.min_code_lines,
            )
            return 0.0

        # Validate syntax
        is_valid, error = is_valid_python_syntax(extracted.code)
        if not is_valid:
            logger.debug("Syntax validation failed", error=error)
            return 0.0

        return self._apply_partial_credit(1.0)


class CodeValidator(Validator):
    """Validates code with extraction, syntax check, and content validation.

    This is a composite validator that:
    1. Extracts code from markdown blocks
    2. Validates Python syntax (if require_syntax_valid=True)
    3. Checks that extracted code contains the criteria substring

    Use this for tasks where the agent should produce working code
    that contains specific patterns (e.g., "def ", "async def", etc.).
    """

    def __init__(self, config: ValidationConfig) -> None:
        """Initialize code validator.

        Args:
            config: Validation configuration with criteria for content check.
        """
        super().__init__(config)
        self._extractor = CodeExtractor()

    async def validate(self, output: str) -> float:
        """Extract code, validate syntax, and check content.

        Args:
            output: Agent's output text (may contain markdown).

        Returns:
            Score from 0.0 to 1.0 based on validation results.
        """
        extracted = self._extractor.extract(output, self.config.language)

        if extracted.is_empty:
            logger.debug("No code extracted from output")
            return 0.0

        # Check minimum line count
        if (
            self.config.min_code_lines > 0
            and extracted.line_count < self.config.min_code_lines
        ):
            logger.debug(
                "Code too short",
                lines=extracted.line_count,
                required=self.config.min_code_lines,
            )
            return 0.0

        # Validate syntax if required
        if self.config.require_syntax_valid:
            is_valid, error = is_valid_python_syntax(extracted.code)
            if not is_valid:
                logger.debug("Syntax validation failed", error=error)
                return 0.0

        # Check that criteria is in the extracted code (not full output)
        if self.config.criteria and self.config.criteria not in extracted.code:
            logger.debug(
                "Criteria not found in extracted code",
                criteria=self.config.criteria,
            )
            return 0.0

        return self._apply_partial_credit(1.0)


class CodeLLMValidator(Validator):
    """Validates extracted code using an LLM judge.

    Extracts code from the output and sends only the code
    (not the full output) to an LLM for evaluation.
    This prevents the LLM from being confused by explanatory text.
    """

    def __init__(self, config: ValidationConfig) -> None:
        """Initialize code LLM validator.

        Args:
            config: Validation configuration with LLM judge criteria.
        """
        super().__init__(config)
        self._extractor = CodeExtractor()

    async def validate(self, output: str) -> float:
        """Extract code and evaluate with LLM judge.

        Args:
            output: Agent's output text (may contain markdown).

        Returns:
            Score from 0.0 to 1.0 based on LLM evaluation.
        """
        extracted = self._extractor.extract(output, self.config.language)

        if extracted.is_empty:
            logger.debug("No code extracted from output")
            return 0.0

        # Check minimum line count
        if (
            self.config.min_code_lines > 0
            and extracted.line_count < self.config.min_code_lines
        ):
            logger.debug(
                "Code too short",
                lines=extracted.line_count,
                required=self.config.min_code_lines,
            )
            return 0.0

        # Validate syntax if required
        if self.config.require_syntax_valid:
            is_valid, error = is_valid_python_syntax(extracted.code)
            if not is_valid:
                logger.debug("Syntax validation failed", error=error)
                return 0.0

        try:
            score = await self._call_llm_judge(extracted.code)
            return self._apply_partial_credit(score)
        except Exception as e:
            logger.error("LLM judge evaluation failed", error=str(e))
            return 0.0

    async def _call_llm_judge(self, code: str) -> float:
        """Call LLM to evaluate extracted code.

        Args:
            code: Extracted code to evaluate.

        Returns:
            Score from 0.0 to 1.0.
        """
        client = get_shared_anthropic_client()

        system_prompt = """You are an evaluation judge for code quality.
Evaluate the given code against the provided criteria.
Respond with ONLY a score from 0.0 to 1.0, where:
- 1.0 = Fully meets all criteria
- 0.0 = Does not meet criteria at all
- Values in between indicate partial fulfillment

Output ONLY the numeric score, nothing else."""

        user_prompt = f"""## Evaluation Criteria
{self.config.criteria}

## Code to Evaluate
```{self.config.language}
{code}
```

## Your Score (0.0 to 1.0):"""

        response = await client.messages.create(
            model=get_eval_model(),
            max_tokens=10,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        logger.debug(
            "Code LLM judge evaluation",
            model=get_eval_model(),
        )

        # Extract score from response
        score_text = response.content[0].text.strip()
        try:
            score = float(score_text)
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
    validator_map: dict[ValidationType, type[Validator]] = {
        ValidationType.EXACT: ExactValidator,
        ValidationType.CONTAINS: ContainsValidator,
        ValidationType.REGEX: RegexValidator,
        ValidationType.LLM_JUDGE: LLMJudgeValidator,
        # Code-specific validators
        ValidationType.CODE: CodeValidator,
        ValidationType.CODE_SYNTAX: CodeSyntaxValidator,
        ValidationType.CODE_LLM: CodeLLMValidator,
    }

    validator_type = config.type
    if isinstance(validator_type, str):
        validator_type = ValidationType(validator_type.lower())

    validator_class = validator_map.get(validator_type)
    if validator_class is None:
        raise ValueError(f"Unknown validation type: {config.type}")

    return validator_class(config)
