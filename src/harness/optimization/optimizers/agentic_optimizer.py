"""Agentic optimizer for qualitative section optimization.

Uses LLM self-critique guided by evaluation criteria and context-engineering
conventions to optimize prompt sections. This is the foundational optimization
approach, enhanced by research-informed heuristics.

Key principles:
- Agentic optimization is foundational, not a fallback
- Research + context-engineering conventions define "good"
- Test suite enhances validation when available, but isn't required
- Heuristics are informed by established patterns, not arbitrary

Example usage:
    from harness.optimization.optimizers.agentic_optimizer import (
        AgenticSectionOptimizer,
        AgenticOptimizationConfig,
    )

    optimizer = AgenticSectionOptimizer()
    config = AgenticOptimizationConfig(verbose=True)

    result = await optimizer.optimize_section(
        section_content="...",
        section=optimizable_section,
        criteria=eval_criteria,
        config=config,
    )
    if result.improved:
        print(f"Improvement: {result.improvement_reason}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from harness.optimization.analysis.conventions import (
    get_conventions_checker,
)

if TYPE_CHECKING:
    from harness.optimization.analysis import (
        EvalCriteria,
        OptimizableSection,
    )
    from harness.optimization.testcases import TestSuite

logger = structlog.get_logger(__name__)


@dataclass
class AgenticOptimizationConfig:
    """Configuration for agentic optimization.

    Attributes:
        max_critique_rounds: Maximum number of critique-improve iterations.
        temperature: Temperature for LLM generation.
        model: Model to use for optimization.
        verbose: Enable verbose output.
        min_improvement_threshold: Minimum score improvement to accept changes.
        test_weight: Weight for test validation score (0-1, default 0.4).
            Heuristic score gets weight (1 - test_weight).
            Only applies when test_suite is provided.
    """

    max_critique_rounds: int = 2
    temperature: float = 0.7
    model: str = "claude-sonnet-4-20250514"
    verbose: bool = False
    min_improvement_threshold: float = 0.05
    test_weight: float = 0.4


@dataclass
class CritiqueResult:
    """Result from analyzing a section.

    Attributes:
        issues: List of identified issues.
        strengths: List of identified strengths.
        suggestions: Specific improvement suggestions.
        severity: Overall severity (high, medium, low).
    """

    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    severity: str = "medium"


@dataclass
class AgenticOptimizationResult:
    """Result from agentic optimization.

    Attributes:
        improved: Whether the section was improved.
        original_content: Original section content.
        optimized_content: Optimized section content.
        critique: The critique that guided improvement.
        improvement_reason: Human-readable reason for improvement.
        rounds_completed: Number of critique rounds completed.
        duration_seconds: Time taken for optimization.
        validation_score: Score from validation tests (if available).
        error: Error message if optimization failed.
    """

    improved: bool
    original_content: str
    optimized_content: str
    critique: CritiqueResult | None = None
    improvement_reason: str = ""
    rounds_completed: int = 0
    duration_seconds: float = 0.0
    validation_score: float | None = None
    error: str = ""


class AgenticSectionOptimizer:
    """Optimizes prompt sections using LLM self-critique.

    This optimizer serves as the foundational optimization approach,
    enhanced by context-engineering conventions and research-informed
    heuristics. It can work standalone or be enhanced with test suites.

    The optimization flow:
    1. Build critique context from evaluation criteria + conventions
    2. Generate critique identifying issues and improvements
    3. Generate improved version addressing the critique
    4. Validate improvement against conventions and heuristics
    5. Run test validation if test suite provided (enhancement)
    6. Accept if improved, else preserve original
    """

    def __init__(self) -> None:
        """Initialize the agentic optimizer."""
        self._client = None
        self._conventions = get_conventions_checker()

    async def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic()
        return self._client

    async def optimize_section(
        self,
        section_content: str,
        section: OptimizableSection,
        criteria: EvalCriteria,
        config: AgenticOptimizationConfig,
        test_suite: TestSuite | None = None,
    ) -> AgenticOptimizationResult:
        """Run self-critique optimization on a section.

        Args:
            section_content: Current content of the section.
            section: OptimizableSection with metadata.
            criteria: Evaluation criteria with competencies.
            config: Agentic optimization configuration.
            test_suite: Optional test suite for validation.

        Returns:
            AgenticOptimizationResult with optimization details.
        """
        start_time = time.time()

        logger.info(
            "Starting agentic optimization",
            section=section.section.value,
            competencies=len(section.competency_ids),
            max_rounds=config.max_critique_rounds,
        )

        try:
            # 1. Build critique context from criteria + conventions
            context = self._build_critique_context(
                section, criteria, section_content
            )

            best_content = section_content
            best_critique: CritiqueResult | None = None
            best_validation_score: float | None = None
            total_rounds = 0

            # 2. Run critique-improve iterations
            for round_num in range(config.max_critique_rounds):
                total_rounds = round_num + 1

                logger.info(
                    "Running critique round",
                    round=round_num + 1,
                    max_rounds=config.max_critique_rounds,
                )

                # Generate critique
                critique = await self._generate_critique(
                    best_content, context, config
                )

                if config.verbose:
                    logger.info(
                        "Critique generated",
                        issues=len(critique.issues),
                        suggestions=len(critique.suggestions),
                        severity=critique.severity,
                    )

                # If no significant issues, we're done
                if critique.severity == "low" and len(critique.issues) <= 1:
                    logger.info("No significant issues found, stopping")
                    best_critique = critique
                    break

                # Generate improved version
                improved = await self._generate_improvement(
                    best_content, critique, context, config
                )

                # Validate improvement using heuristics (foundational)
                heuristic_valid = self._is_valid_improvement(
                    section_content, improved, section
                )

                # Run test validation if test suite provided (enhancement)
                test_score = 1.0
                test_issues: list[str] = []
                if test_suite is not None:
                    test_score, test_issues = await self._run_test_validation(
                        improved, test_suite, section
                    )

                    if config.verbose and test_issues:
                        logger.info(
                            "Test validation issues",
                            issues=test_issues[:3],
                        )

                # Combine scores: 60% heuristic, 40% tests (configurable)
                if test_suite is not None:
                    should_accept, combined = self._combine_validation_scores(
                        heuristic_valid, test_score, config
                    )
                else:
                    # No tests: use heuristic only
                    should_accept = heuristic_valid
                    combined = 1.0 if heuristic_valid else 0.0

                if should_accept:
                    best_content = improved
                    best_critique = critique
                    best_validation_score = test_score if test_suite else None

                    logger.info(
                        "Improvement accepted",
                        round=round_num + 1,
                        original_len=len(section_content),
                        improved_len=len(improved),
                        heuristic=heuristic_valid,
                        test_score=f"{test_score:.2f}" if test_suite else "N/A",
                        combined=f"{combined:.2f}",
                    )
                else:
                    logger.info(
                        "Improvement rejected",
                        round=round_num + 1,
                        heuristic=heuristic_valid,
                        test_score=f"{test_score:.2f}" if test_suite else "N/A",
                        combined=f"{combined:.2f}",
                    )
                    break

            duration = time.time() - start_time

            # Determine if we actually improved
            improved = best_content != section_content

            improvement_reason = ""
            if improved and best_critique:
                improvement_reason = (
                    f"Addressed {len(best_critique.issues)} issues: "
                    + "; ".join(best_critique.issues[:3])
                )

            logger.info(
                "Agentic optimization complete",
                section=section.section.value,
                improved=improved,
                rounds=total_rounds,
                duration=f"{duration:.1f}s",
            )

            return AgenticOptimizationResult(
                improved=improved,
                original_content=section_content,
                optimized_content=best_content,
                critique=best_critique,
                improvement_reason=improvement_reason,
                rounds_completed=total_rounds,
                duration_seconds=duration,
                validation_score=best_validation_score,
            )

        except Exception as e:
            logger.error(
                "Agentic optimization failed",
                section=section.section.value,
                error=str(e),
            )
            return AgenticOptimizationResult(
                improved=False,
                original_content=section_content,
                optimized_content=section_content,
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    def _build_critique_context(
        self,
        section: OptimizableSection,
        criteria: EvalCriteria,
        section_content: str | None = None,
    ) -> dict[str, Any]:
        """Build context for critique from evaluation criteria + conventions.

        Combines:
        1. Evaluation criteria (competencies, indicators, mistakes)
        2. Context-engineering conventions (structure, patterns, signals)

        Args:
            section: The section being optimized.
            criteria: Evaluation criteria with competencies.
            section_content: Optional content for conventions analysis.

        Returns:
            Dictionary with context for critique prompts.
        """
        # Get competencies for this section
        relevant_competencies = []
        for comp in criteria.competencies:
            if comp.id in section.competency_ids:
                relevant_competencies.append(comp)

        # Build positive indicators (what to include)
        positive_indicators = []
        for comp in relevant_competencies:
            positive_indicators.extend(comp.positive_indicators)

        # Build negative indicators (what to avoid)
        negative_indicators = []
        for comp in relevant_competencies:
            negative_indicators.extend(comp.negative_indicators)

        # Get test scenarios for context
        test_scenarios = []
        for comp in relevant_competencies:
            test_scenarios.extend(comp.test_scenarios)

        # Get common mistakes for this type of content
        common_mistakes = [
            m.mistake for m in criteria.common_mistakes
        ]

        # Get conventions context for research-informed guidance
        conventions_context = self._conventions.get_conventions_context()

        # If content provided, get specific suggestions
        conventions_suggestions = []
        quality_score = 0.0
        if section_content:
            conventions_suggestions = self._conventions.get_improvement_suggestions(
                section_content
            )
            quality_score = self._conventions.calculate_quality_score(
                section_content
            )

        return {
            "section_name": section.section.value,
            "competencies": [
                {
                    "name": c.name,
                    "description": c.description,
                    "importance": c.importance,
                }
                for c in relevant_competencies
            ],
            "positive_indicators": positive_indicators[:10],
            "negative_indicators": negative_indicators[:10],
            "test_scenarios": test_scenarios[:5],
            "common_mistakes": common_mistakes[:5],
            "optimization_goal": criteria.optimization_goal,
            # Conventions-based context (research-informed)
            "conventions": {
                "expected_sections": conventions_context["expected_sections"],
                "structural_requirements": conventions_context[
                    "structural_requirements"
                ],
                "token_guidance": conventions_context["token_guidance"],
                "quality_signals": conventions_context["quality_signals"][:5],
            },
            "conventions_suggestions": conventions_suggestions,
            "conventions_quality_score": quality_score,
        }

    async def _generate_critique(
        self,
        section_content: str,
        context: dict[str, Any],
        config: AgenticOptimizationConfig,
    ) -> CritiqueResult:
        """Generate critique of the section content.

        Uses both evaluation criteria and context-engineering conventions
        to provide research-informed critique.

        Args:
            section_content: Content to critique.
            context: Critique context with criteria and conventions.
            config: Configuration for generation.

        Returns:
            CritiqueResult with issues and suggestions.
        """
        client = await self._get_client()

        # Build conventions guidance from context
        conventions = context.get("conventions", {})
        conv_reqs = conventions.get("structural_requirements", [])
        conv_signals = conventions.get("quality_signals", [])

        conventions_text = ""
        if conv_reqs:
            conventions_text = f"""
## Context-Engineering Conventions
The following structural requirements should be met:
{chr(10).join(f'- {r}' for r in conv_reqs[:5])}

Quality signals to look for:
{chr(10).join(f'- {s["name"]}' for s in conv_signals[:5])}
"""

        system_prompt = f"""You are an expert prompt engineer evaluating a section of a system prompt.
Your task is to identify issues and suggest improvements based on:
1. The provided evaluation criteria (competencies, indicators)
2. Context-engineering best practices and conventions

Analyze the section for:
1. Clarity and completeness of instructions
2. Presence of required competencies and behaviors
3. Absence of anti-patterns or common mistakes
4. Consistency with the optimization goal
5. Adherence to structural conventions
6. Appropriate level of detail (not too brief, not verbose)
{conventions_text}
Be specific and actionable in your critique. Focus on substantive issues, not style.

Respond in the following format:
ISSUES:
- [issue 1]
- [issue 2]
...

STRENGTHS:
- [strength 1]
- [strength 2]
...

SUGGESTIONS:
- [specific improvement suggestion 1]
- [specific improvement suggestion 2]
...

SEVERITY: [high/medium/low]"""

        # Build user prompt with context
        competencies_text = "\n".join(
            f"- {c['name']}: {c['description']}"
            for c in context["competencies"]
        )

        positive_text = "\n".join(
            f"- {p}" for p in context["positive_indicators"]
        ) or "None specified"

        negative_text = "\n".join(
            f"- {n}" for n in context["negative_indicators"]
        ) or "None specified"

        # Include conventions-based suggestions if available
        conv_suggestions = context.get("conventions_suggestions", [])
        conv_quality = context.get("conventions_quality_score", 0.0)

        conventions_section = ""
        if conv_suggestions:
            suggestions_text = "\n".join(f"- {s}" for s in conv_suggestions)
            conventions_section = f"""

## Conventions-Based Analysis (quality score: {conv_quality:.2f})
The following improvements are suggested based on established patterns:
{suggestions_text}"""

        user_prompt = f"""## Section to Analyze: {context['section_name']}

## Content:
{section_content}

## Relevant Competencies:
{competencies_text}

## Positive Indicators (should include):
{positive_text}

## Negative Indicators (should avoid):
{negative_text}

## Optimization Goal:
{context['optimization_goal'] or 'Improve clarity and completeness'}
{conventions_section}
Please analyze this section and provide your critique."""

        response = await client.messages.create(
            model=config.model,
            max_tokens=2000,
            temperature=config.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Parse the response
        response_text = response.content[0].text
        return self._parse_critique_response(response_text)

    def _parse_critique_response(self, response_text: str) -> CritiqueResult:
        """Parse the critique response into structured result.

        Args:
            response_text: Raw response from LLM.

        Returns:
            CritiqueResult with parsed content.
        """
        issues = []
        strengths = []
        suggestions = []
        severity = "medium"

        current_section = None
        for line in response_text.split("\n"):
            line = line.strip()

            if line.startswith("ISSUES:"):
                current_section = "issues"
                continue
            elif line.startswith("STRENGTHS:"):
                current_section = "strengths"
                continue
            elif line.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
                continue
            elif line.startswith("SEVERITY:"):
                severity_text = line.replace("SEVERITY:", "").strip().lower()
                if severity_text in ("high", "medium", "low"):
                    severity = severity_text
                current_section = None
                continue

            # Parse list items
            if line.startswith("- ") and current_section:
                item = line[2:].strip()
                if current_section == "issues":
                    issues.append(item)
                elif current_section == "strengths":
                    strengths.append(item)
                elif current_section == "suggestions":
                    suggestions.append(item)

        return CritiqueResult(
            issues=issues,
            strengths=strengths,
            suggestions=suggestions,
            severity=severity,
        )

    async def _generate_improvement(
        self,
        section_content: str,
        critique: CritiqueResult,
        context: dict[str, Any],
        config: AgenticOptimizationConfig,
    ) -> str:
        """Generate improved version of the section.

        Args:
            section_content: Original content to improve.
            critique: Critique with issues and suggestions.
            context: Context with criteria.
            config: Configuration for generation.

        Returns:
            Improved section content.
        """
        client = await self._get_client()

        system_prompt = """You are an expert prompt engineer improving a section of a system prompt.
Your task is to rewrite the section addressing the identified issues while preserving its strengths.

Guidelines:
1. Preserve the overall structure and style of the original
2. Address each identified issue specifically
3. Incorporate the improvement suggestions
4. Maintain coherence with the rest of the prompt
5. Do not add unnecessary content or bloat
6. Keep the tone consistent with the original

Output ONLY the improved section content, without any preamble or explanation."""

        issues_text = "\n".join(f"- {i}" for i in critique.issues) or "None"
        suggestions_text = "\n".join(f"- {s}" for s in critique.suggestions) or "None"
        strengths_text = "\n".join(f"- {s}" for s in critique.strengths) or "None"

        user_prompt = f"""## Original Section: {context['section_name']}

{section_content}

## Issues to Address:
{issues_text}

## Improvement Suggestions:
{suggestions_text}

## Strengths to Preserve:
{strengths_text}

## Optimization Goal:
{context['optimization_goal'] or 'Improve clarity and completeness'}

Please rewrite this section to address the issues while preserving strengths."""

        response = await client.messages.create(
            model=config.model,
            max_tokens=4000,
            temperature=config.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text.strip()

    def _is_valid_improvement(
        self,
        original: str,
        improved: str,
        section: OptimizableSection,
    ) -> bool:
        """Validate improvement using conventions-informed heuristics.

        Research-informed validation checks:
        1. Basic sanity (not empty, reasonable length changes)
        2. Content preservation (maintains core concepts)
        3. Quality improvement (conventions score should not decrease)
        4. Structural integrity (maintains expected patterns)

        These heuristics are informed by context-engineering conventions
        rather than arbitrary thresholds.

        Args:
            original: Original section content.
            improved: Improved section content.
            section: Section metadata.

        Returns:
            True if improvement passes validation.
        """
        if not improved or not improved.strip():
            logger.debug("Improvement rejected: empty")
            return False

        original_len = len(original)
        improved_len = len(improved)

        # 1. Basic length sanity (informed by progressive-disclosure pattern)
        # Token guidance suggests 1500-5000 tokens optimal
        # Allow reasonable changes but prevent extremes
        if improved_len < original_len * 0.4:
            logger.debug(
                "Improvement rejected: excessive reduction",
                original_len=original_len,
                improved_len=improved_len,
                reduction_ratio=improved_len / original_len,
            )
            return False

        if improved_len > original_len * 2.5:
            # Progressive disclosure pattern suggests avoiding bloat
            logger.debug(
                "Improvement rejected: excessive expansion",
                original_len=original_len,
                improved_len=improved_len,
                expansion_ratio=improved_len / original_len,
            )
            return False

        # 2. Content preservation (maintain core concepts)
        # At least 25% of significant words should be preserved
        # (slightly higher threshold than before, informed by patterns)
        original_words = set(original.lower().split())
        improved_words = set(improved.lower().split())

        # Filter out common stop words for better signal
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be",
            "to", "of", "and", "or", "in", "on", "at", "for",
            "with", "that", "this", "it", "you", "your",
        }
        orig_significant = original_words - stop_words
        impr_significant = improved_words - stop_words

        if orig_significant:
            overlap = len(orig_significant & impr_significant)
            overlap_ratio = overlap / len(orig_significant)
            if overlap_ratio < 0.25:
                logger.debug(
                    "Improvement rejected: insufficient content preservation",
                    overlap_ratio=overlap_ratio,
                    overlap_count=overlap,
                )
                return False

        # 3. Quality score comparison (conventions-based)
        # Improvement should not decrease quality score significantly
        original_score = self._conventions.calculate_quality_score(original)
        improved_score = self._conventions.calculate_quality_score(improved)

        if improved_score < original_score - 0.1:
            # Allow small decreases but reject significant degradation
            logger.debug(
                "Improvement rejected: quality score decreased",
                original_score=original_score,
                improved_score=improved_score,
                delta=improved_score - original_score,
            )
            return False

        # 4. Structural integrity check
        original_structure = self._conventions.assess_structure(original)
        improved_structure = self._conventions.assess_structure(improved)

        # Improvement should not lose critical structural elements
        if (
            original_structure.has_title
            and not improved_structure.has_title
        ):
            logger.debug("Improvement rejected: lost title")
            return False

        # Check if we lost more sections than we gained
        orig_sections = len(original_structure.expected_sections_found)
        impr_sections = len(improved_structure.expected_sections_found)
        if impr_sections < orig_sections - 1:
            logger.debug(
                "Improvement rejected: lost too many sections",
                original_sections=orig_sections,
                improved_sections=impr_sections,
            )
            return False

        # Log successful validation with details
        logger.debug(
            "Improvement validated",
            length_ratio=improved_len / original_len,
            overlap_ratio=overlap_ratio if orig_significant else 1.0,
            original_quality=original_score,
            improved_quality=improved_score,
            quality_delta=improved_score - original_score,
        )

        return True

    async def _run_test_validation(
        self,
        improved_content: str,
        test_suite: TestSuite,
        section: OptimizableSection,
    ) -> tuple[float, list[str]]:
        """Run qualitative tests against improved content.

        This method runs qualitative tests (llm_judge, code_llm, semantic)
        to validate that the improved section content still enables proper
        agent behavior.

        Note: This does NOT run the full agent - it evaluates the section
        content itself against qualitative criteria from the test suite.

        Args:
            improved_content: The improved section content.
            test_suite: Test suite with qualitative tests.
            section: The section being optimized.

        Returns:
            Tuple of (average_score, list_of_issues).
        """
        from harness.optimization.testcases import ValidationType, get_validator

        # Filter to qualitative tests only
        qualitative_types = {
            ValidationType.LLM_JUDGE,
            ValidationType.CODE_LLM,
        }

        qualitative_tests = [
            tc for tc in test_suite.test_cases
            if tc.validation.type in qualitative_types
        ]

        if not qualitative_tests:
            logger.debug(
                "No qualitative tests available for validation",
                section=section.section.value,
            )
            return 1.0, []  # No tests = assume valid

        scores = []
        issues = []

        for test in qualitative_tests:
            try:
                validator = get_validator(test.validation)
                # We validate the section content, not full agent output
                # This checks if the section enables the expected behavior
                score = await validator.validate(improved_content)
                scores.append(score)

                if score < 0.5:
                    issues.append(
                        f"Test '{test.id}' failed: {test.expected_behavior[:50]}"
                    )

                logger.debug(
                    "Test validation result",
                    test_id=test.id,
                    score=score,
                    section=section.section.value,
                )

            except Exception as e:
                logger.debug(
                    "Test validation error",
                    test_id=test.id,
                    error=str(e),
                )
                # Don't penalize for validation errors
                continue

        if not scores:
            return 1.0, []

        avg_score = sum(scores) / len(scores)
        return avg_score, issues

    def _combine_validation_scores(
        self,
        heuristic_valid: bool,
        test_score: float,
        config: AgenticOptimizationConfig,
    ) -> tuple[bool, float]:
        """Combine heuristic validation and test score.

        Uses weighted combination: (1 - test_weight) * heuristic + test_weight * test

        Args:
            heuristic_valid: Whether heuristic validation passed (True/False).
            test_score: Score from test validation (0.0 - 1.0).
            config: Configuration with test_weight.

        Returns:
            Tuple of (should_accept, combined_score).
        """
        # Convert heuristic bool to score
        heuristic_score = 1.0 if heuristic_valid else 0.0

        # Weighted combination
        heuristic_weight = 1.0 - config.test_weight
        combined = (
            heuristic_weight * heuristic_score
            + config.test_weight * test_score
        )

        # Accept if combined score >= 0.5
        # This means:
        # - If heuristic passes (1.0) and tests score 0.25+, accept (0.6*1 + 0.4*0.25 = 0.7)
        # - If heuristic fails (0.0) and tests score 1.0, reject (0.6*0 + 0.4*1 = 0.4)
        # This ensures heuristics remain foundational
        should_accept = combined >= 0.5

        return should_accept, combined


def get_agentic_optimizer() -> AgenticSectionOptimizer:
    """Factory function to create an agentic optimizer.

    Returns:
        Configured AgenticSectionOptimizer.
    """
    return AgenticSectionOptimizer()
