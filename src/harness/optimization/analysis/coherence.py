"""Coherence analysis for merged prompts.

Analyzes the structural flow of prompts and detects organization issues
like detail inversions, duplicate content, and broken references.

Example usage:
    from harness.optimization.analysis.coherence import (
        PromptCoherenceAnalyzer,
        CoherenceAnalysis,
    )

    analyzer = PromptCoherenceAnalyzer()
    analysis = await analyzer.analyze(merged_prompt)

    if analysis.issues:
        fixed_prompt = await analyzer.fix(merged_prompt, analysis)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from harness.optimization.analysis.synthesizer import (
    ParsedPrompt,
    PromptSynthesizer,
)

logger = structlog.get_logger(__name__)


class IssueType(str, Enum):
    """Types of coherence issues."""

    DETAIL_INVERSION = "detail_inversion"
    DUPLICATE_CONTENT = "duplicate"
    BROKEN_REFERENCE = "broken_reference"
    MISSING_TRANSITION = "missing_transition"
    INCONSISTENT_STYLE = "inconsistent_style"


class IssueSeverity(str, Enum):
    """Severity levels for coherence issues."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetailLevel(str, Enum):
    """Detail level classification for sections."""

    HIGH = "high"  # Code examples, detailed instructions
    MEDIUM = "medium"  # Guidelines, bullet points
    LOW = "low"  # High-level concepts, principles


@dataclass
class CoherenceIssue:
    """A detected coherence issue in the prompt.

    Attributes:
        type: Type of the issue.
        severity: Severity level.
        location: Section name where issue was found.
        description: Human-readable description.
        suggested_fix: Suggested fix for the issue.
        related_sections: Other sections involved.
    """

    type: IssueType
    severity: IssueSeverity
    location: str
    description: str
    suggested_fix: str
    related_sections: list[str] = field(default_factory=list)


@dataclass
class SectionAnalysis:
    """Analysis of a single section.

    Attributes:
        name: Section name.
        detail_level: Classified detail level.
        has_code_examples: Whether section contains code.
        line_count: Number of lines in section.
        word_count: Number of words in section.
        key_concepts: Key concepts/topics found.
        references_to: Sections this section references.
        referenced_by: Sections that reference this one.
    """

    name: str
    detail_level: DetailLevel
    has_code_examples: bool = False
    line_count: int = 0
    word_count: int = 0
    key_concepts: list[str] = field(default_factory=list)
    references_to: list[str] = field(default_factory=list)
    referenced_by: list[str] = field(default_factory=list)


@dataclass
class CoherenceAnalysis:
    """Result of analyzing prompt coherence.

    Attributes:
        issues: List of detected issues.
        section_analyses: Analysis per section.
        section_detail_levels: Section name to detail level mapping.
        current_order: Current section order.
        recommended_order: Optimal section ordering.
        overall_score: 0-1 coherence score.
        summary: Human-readable summary.
    """

    issues: list[CoherenceIssue] = field(default_factory=list)
    section_analyses: list[SectionAnalysis] = field(default_factory=list)
    section_detail_levels: dict[str, str] = field(default_factory=dict)
    current_order: list[str] = field(default_factory=list)
    recommended_order: list[str] = field(default_factory=list)
    overall_score: float = 1.0
    summary: str = ""

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return len(self.issues) > 0

    @property
    def high_severity_count(self) -> int:
        """Count of high severity issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH)


class PromptCoherenceAnalyzer:
    """Analyzes and fixes prompt coherence issues.

    Detects:
    - Detail level inversions (detailed before high-level)
    - Duplicate content across sections
    - Broken cross-references
    - Missing transitions between sections
    """

    # Patterns for detecting code blocks
    CODE_BLOCK_PATTERN = re.compile(r"```[\w]*\n.*?\n```", re.DOTALL)

    # Patterns for detecting bullet lists
    BULLET_PATTERN = re.compile(r"^[-*]\s", re.MULTILINE)

    # Patterns for detecting references to other sections
    REFERENCE_PATTERN = re.compile(
        r"\b(see|refer to|as described in|mentioned in)\s+"
        r"(?:the\s+)?([A-Za-z\s]+)\s+section",
        re.IGNORECASE,
    )

    # Ideal section order (high-level to detailed)
    IDEAL_ORDER = [
        "role_definition",
        "summary",
        "best_practices",
        "constraints",
        "core_approach",
        "examples",
        "output_format",
    ]

    def __init__(self) -> None:
        """Initialize the coherence analyzer."""
        self._synthesizer = PromptSynthesizer()
        self._client = None

    async def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic()
        return self._client

    async def analyze(self, prompt: str) -> CoherenceAnalysis:
        """Analyze prompt for coherence issues.

        Args:
            prompt: Full prompt content.

        Returns:
            CoherenceAnalysis with issues and recommendations.
        """
        logger.info("Starting coherence analysis")

        # Parse the prompt into sections
        parsed = self._synthesizer.parse_prompt(prompt)

        # Analyze each section
        section_analyses = []
        for section_name in parsed.section_order:
            content = parsed.sections.get(section_name, "")
            analysis = await self._analyze_section(section_name, content)
            section_analyses.append(analysis)

        # Build detail levels dict
        detail_levels = {
            sa.name: sa.detail_level.value for sa in section_analyses
        }

        # Detect issues
        issues = []

        # Check for detail inversions
        inversion_issues = self._detect_detail_inversions(
            section_analyses, parsed.section_order
        )
        issues.extend(inversion_issues)

        # Check for duplicate content
        duplicate_issues = await self._detect_duplicates(
            parsed.sections
        )
        issues.extend(duplicate_issues)

        # Check for broken references
        reference_issues = self._detect_broken_references(
            section_analyses, parsed.section_order
        )
        issues.extend(reference_issues)

        # Calculate recommended order
        recommended_order = self._recommend_ordering(
            section_analyses, parsed.section_order
        )

        # Calculate overall score
        score = self._calculate_score(issues)

        # Generate summary
        summary = self._generate_summary(issues, section_analyses)

        logger.info(
            "Coherence analysis complete",
            issues_found=len(issues),
            score=score,
            sections=len(section_analyses),
        )

        return CoherenceAnalysis(
            issues=issues,
            section_analyses=section_analyses,
            section_detail_levels=detail_levels,
            current_order=parsed.section_order,
            recommended_order=recommended_order,
            overall_score=score,
            summary=summary,
        )

    async def _analyze_section(
        self, name: str, content: str
    ) -> SectionAnalysis:
        """Analyze a single section.

        Args:
            name: Section name.
            content: Section content.

        Returns:
            SectionAnalysis with classification.
        """
        # Count metrics
        line_count = len(content.splitlines())
        word_count = len(content.split())

        # Detect code blocks
        code_blocks = self.CODE_BLOCK_PATTERN.findall(content)
        has_code = len(code_blocks) > 0

        # Count bullets
        bullet_count = len(self.BULLET_PATTERN.findall(content))

        # Classify detail level
        detail_level = self._classify_detail_level(
            content, has_code, bullet_count, line_count
        )

        # Find references to other sections
        references = []
        for match in self.REFERENCE_PATTERN.finditer(content):
            ref_section = match.group(2).lower().strip()
            references.append(ref_section)

        return SectionAnalysis(
            name=name,
            detail_level=detail_level,
            has_code_examples=has_code,
            line_count=line_count,
            word_count=word_count,
            references_to=references,
        )

    def _classify_detail_level(
        self,
        content: str,
        has_code: bool,
        bullet_count: int,
        line_count: int,
    ) -> DetailLevel:
        """Classify the detail level of a section.

        Args:
            content: Section content.
            has_code: Whether section has code blocks.
            bullet_count: Number of bullet points.
            line_count: Number of lines.

        Returns:
            DetailLevel classification.
        """
        # High detail: code examples, long content, many specifics
        if has_code:
            return DetailLevel.HIGH

        # Also high if very long with lots of specific content
        if line_count > 50 and bullet_count > 10:
            return DetailLevel.HIGH

        # Low detail: short, conceptual, few specifics
        if line_count < 20 and bullet_count < 5:
            return DetailLevel.LOW

        # Medium: moderate length, some structure
        return DetailLevel.MEDIUM

    def _detect_detail_inversions(
        self,
        analyses: list[SectionAnalysis],
        order: list[str],
    ) -> list[CoherenceIssue]:
        """Detect detail level inversions in section order.

        A detail inversion occurs when a highly detailed section
        appears before a high-level conceptual section.

        Args:
            analyses: List of section analyses.
            order: Current section order.

        Returns:
            List of detected inversion issues.
        """
        issues = []

        # Build lookup
        analysis_map = {a.name: a for a in analyses}

        # Check each pair of adjacent sections
        for i, current_name in enumerate(order[:-1]):
            current = analysis_map.get(current_name)
            next_name = order[i + 1]
            next_section = analysis_map.get(next_name)

            if not current or not next_section:
                continue

            # Inversion: HIGH detail followed by LOW detail
            if (
                current.detail_level == DetailLevel.HIGH
                and next_section.detail_level == DetailLevel.LOW
            ):
                issues.append(
                    CoherenceIssue(
                        type=IssueType.DETAIL_INVERSION,
                        severity=IssueSeverity.MEDIUM,
                        location=current_name,
                        description=(
                            f"Detailed section '{current_name}' appears before "
                            f"high-level section '{next_name}'. Consider reordering."
                        ),
                        suggested_fix=(
                            f"Move '{next_name}' before '{current_name}' "
                            "for better cognitive flow."
                        ),
                        related_sections=[next_name],
                    )
                )

        # Check for major inversions (code examples before principles)
        code_section_idx = None
        principle_section_idx = None

        for i, name in enumerate(order):
            analysis = analysis_map.get(name)
            if not analysis:
                continue

            if analysis.has_code_examples and code_section_idx is None:
                code_section_idx = i

            if (
                analysis.detail_level == DetailLevel.LOW
                and not analysis.has_code_examples
                and principle_section_idx is None
                and code_section_idx is not None
            ):
                principle_section_idx = i

        if (
            code_section_idx is not None
            and principle_section_idx is not None
            and code_section_idx < principle_section_idx
        ):
            code_name = order[code_section_idx]
            principle_name = order[principle_section_idx]

            issues.append(
                CoherenceIssue(
                    type=IssueType.DETAIL_INVERSION,
                    severity=IssueSeverity.HIGH,
                    location=code_name,
                    description=(
                        f"Code examples in '{code_name}' appear before "
                        f"high-level concepts in '{principle_name}'. "
                        "This inverts the typical learning flow."
                    ),
                    suggested_fix=(
                        "Consider reorganizing: high-level concepts first, "
                        "then guidelines, then detailed examples."
                    ),
                    related_sections=[principle_name],
                )
            )

        return issues

    async def _detect_duplicates(
        self, sections: dict[str, str]
    ) -> list[CoherenceIssue]:
        """Detect duplicate content across sections.

        Uses simple heuristics (not LLM) for efficiency.

        Args:
            sections: Section name to content mapping.

        Returns:
            List of detected duplicate issues.
        """
        issues = []

        # Extract sentences from each section
        section_sentences: dict[str, set[str]] = {}

        for name, content in sections.items():
            # Simple sentence splitting
            sentences = set()
            for line in content.split("\n"):
                line = line.strip()
                # Only consider substantial sentences
                if len(line) > 50:
                    # Normalize for comparison
                    normalized = line.lower().strip(".-* ")
                    sentences.add(normalized)
            section_sentences[name] = sentences

        # Compare pairs
        section_names = list(sections.keys())
        for i, name1 in enumerate(section_names):
            for name2 in section_names[i + 1:]:
                sentences1 = section_sentences[name1]
                sentences2 = section_sentences[name2]

                if not sentences1 or not sentences2:
                    continue

                # Find overlapping sentences
                overlap = sentences1 & sentences2

                # If significant overlap, report
                if len(overlap) >= 3:
                    issues.append(
                        CoherenceIssue(
                            type=IssueType.DUPLICATE_CONTENT,
                            severity=IssueSeverity.LOW,
                            location=name1,
                            description=(
                                f"Found {len(overlap)} duplicate sentences "
                                f"between '{name1}' and '{name2}'."
                            ),
                            suggested_fix=(
                                "Consider consolidating duplicate content "
                                "into a single section."
                            ),
                            related_sections=[name2],
                        )
                    )

        return issues

    def _detect_broken_references(
        self,
        analyses: list[SectionAnalysis],
        order: list[str],
    ) -> list[CoherenceIssue]:
        """Detect broken cross-references between sections.

        Args:
            analyses: List of section analyses.
            order: Current section order.

        Returns:
            List of detected broken reference issues.
        """
        issues = []
        section_names_lower = {n.lower().replace("_", " ") for n in order}

        for analysis in analyses:
            for ref in analysis.references_to:
                ref_lower = ref.lower()
                # Check if referenced section exists
                if ref_lower not in section_names_lower:
                    issues.append(
                        CoherenceIssue(
                            type=IssueType.BROKEN_REFERENCE,
                            severity=IssueSeverity.LOW,
                            location=analysis.name,
                            description=(
                                f"Section '{analysis.name}' references "
                                f"'{ref}' which doesn't exist."
                            ),
                            suggested_fix=(
                                f"Remove or update the reference to '{ref}'."
                            ),
                        )
                    )

        return issues

    def _recommend_ordering(
        self,
        analyses: list[SectionAnalysis],
        current_order: list[str],
    ) -> list[str]:
        """Recommend an optimal section ordering.

        Follows cognitive flow: high-level concepts → guidelines →
        detailed examples.

        Args:
            analyses: List of section analyses.
            current_order: Current section order.

        Returns:
            Recommended section order.
        """
        # Build lookup
        analysis_map = {a.name: a for a in analyses}

        # Group sections by detail level
        low_detail = []
        medium_detail = []
        high_detail = []

        for name in current_order:
            analysis = analysis_map.get(name)
            if not analysis:
                medium_detail.append(name)
                continue

            if analysis.detail_level == DetailLevel.LOW:
                low_detail.append(name)
            elif analysis.detail_level == DetailLevel.HIGH:
                high_detail.append(name)
            else:
                medium_detail.append(name)

        # Apply ideal order within groups if matches
        def sort_by_ideal(names: list[str]) -> list[str]:
            def key(name: str) -> int:
                if name in self.IDEAL_ORDER:
                    return self.IDEAL_ORDER.index(name)
                return 100
            return sorted(names, key=key)

        low_detail = sort_by_ideal(low_detail)
        medium_detail = sort_by_ideal(medium_detail)
        high_detail = sort_by_ideal(high_detail)

        # Combine: low detail first, then medium, then high
        return low_detail + medium_detail + high_detail

    def _calculate_score(self, issues: list[CoherenceIssue]) -> float:
        """Calculate overall coherence score.

        Args:
            issues: List of detected issues.

        Returns:
            Score from 0.0 to 1.0.
        """
        if not issues:
            return 1.0

        # Deduct points based on severity
        deductions = 0.0
        for issue in issues:
            if issue.severity == IssueSeverity.HIGH:
                deductions += 0.2
            elif issue.severity == IssueSeverity.MEDIUM:
                deductions += 0.1
            else:
                deductions += 0.05

        return max(0.0, 1.0 - deductions)

    def _generate_summary(
        self,
        issues: list[CoherenceIssue],
        analyses: list[SectionAnalysis],
    ) -> str:
        """Generate a human-readable summary.

        Args:
            issues: List of detected issues.
            analyses: List of section analyses.

        Returns:
            Summary string.
        """
        if not issues:
            return "No coherence issues detected. Prompt structure is well-organized."

        parts = [f"Found {len(issues)} coherence issue(s):"]

        # Group by type
        by_type: dict[IssueType, list[CoherenceIssue]] = {}
        for issue in issues:
            if issue.type not in by_type:
                by_type[issue.type] = []
            by_type[issue.type].append(issue)

        for issue_type, type_issues in by_type.items():
            parts.append(
                f"- {issue_type.value}: {len(type_issues)} issue(s)"
            )

        return "\n".join(parts)

    async def fix(
        self,
        prompt: str,
        analysis: CoherenceAnalysis,
        auto_reorder: bool = False,
        auto_dedupe: bool = False,
    ) -> str:
        """Apply fixes for detected coherence issues.

        Args:
            prompt: Original prompt content.
            analysis: CoherenceAnalysis with detected issues.
            auto_reorder: If True, automatically reorder sections.
            auto_dedupe: If True, automatically deduplicate content.

        Returns:
            Fixed prompt content.
        """
        if not analysis.has_issues:
            return prompt

        logger.info(
            "Applying coherence fixes",
            issues=len(analysis.issues),
            auto_reorder=auto_reorder,
            auto_dedupe=auto_dedupe,
        )

        fixed_prompt = prompt

        # Reorder sections if requested
        if auto_reorder and analysis.recommended_order != analysis.current_order:
            fixed_prompt = await self._reorder_sections(
                fixed_prompt, analysis.recommended_order
            )
            logger.info(
                "Reordered sections",
                old_order=analysis.current_order,
                new_order=analysis.recommended_order,
            )

        # Deduplicate if requested (future enhancement)
        if auto_dedupe:
            # For now, just log - deduplication is complex
            logger.info("Auto-dedupe requested but not yet implemented")

        return fixed_prompt

    async def _reorder_sections(
        self, prompt: str, new_order: list[str]
    ) -> str:
        """Reorder sections in the prompt.

        Args:
            prompt: Original prompt content.
            new_order: Desired section order.

        Returns:
            Prompt with reordered sections.
        """
        parsed = self._synthesizer.parse_prompt(prompt)

        # Build new section order
        ordered_sections: dict[str, str] = {}
        for name in new_order:
            if name in parsed.sections:
                ordered_sections[name] = parsed.sections[name]

        # Add any sections not in new_order at the end
        for name in parsed.sections:
            if name not in ordered_sections:
                ordered_sections[name] = parsed.sections[name]

        # Reconstruct with new order
        # Create a modified ParsedPrompt with new order
        new_parsed = ParsedPrompt(
            frontmatter=parsed.frontmatter,
            frontmatter_raw=parsed.frontmatter_raw,
            title=parsed.title,
            sections=ordered_sections,
            section_order=list(ordered_sections.keys()),
            tail=parsed.tail,
        )

        return self._synthesizer._reconstruct_prompt(
            new_parsed, ordered_sections
        )


async def analyze_prompt_coherence(prompt: str) -> CoherenceAnalysis:
    """Convenience function to analyze prompt coherence.

    Args:
        prompt: Prompt content to analyze.

    Returns:
        CoherenceAnalysis with issues and recommendations.
    """
    analyzer = PromptCoherenceAnalyzer()
    return await analyzer.analyze(prompt)


async def fix_coherence_issues(
    prompt: str,
    auto_reorder: bool = True,
    auto_dedupe: bool = False,
) -> tuple[str, CoherenceAnalysis]:
    """Convenience function to analyze and fix coherence issues.

    Args:
        prompt: Prompt content to fix.
        auto_reorder: If True, automatically reorder sections.
        auto_dedupe: If True, automatically deduplicate.

    Returns:
        Tuple of (fixed_prompt, analysis).
    """
    analyzer = PromptCoherenceAnalyzer()
    analysis = await analyzer.analyze(prompt)

    if analysis.has_issues:
        fixed = await analyzer.fix(
            prompt, analysis, auto_reorder=auto_reorder, auto_dedupe=auto_dedupe
        )
        return fixed, analysis

    return prompt, analysis
