"""Context engineering conventions for quality assessment.

Extracts quality signals from context-engineering patterns to inform
agentic optimization heuristics.

Example usage:
    from harness.optimization.analysis.conventions import (
        ConventionsChecker,
        StructureQuality,
        get_conventions_checker,
    )

    checker = get_conventions_checker()
    quality = checker.assess_structure(prompt_content)
    signals = checker.get_quality_signals(prompt_content)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QualityLevel(str, Enum):
    """Quality level for structural assessment."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class StructureQuality:
    """Assessment of prompt structure quality.

    Attributes:
        level: Overall quality level.
        has_frontmatter: Whether YAML frontmatter is present.
        has_title: Whether a main title (H1) is present.
        section_count: Number of major sections found.
        expected_sections_found: List of expected sections present.
        missing_sections: List of expected sections missing.
        has_examples: Whether code examples are present.
        has_constraints: Whether constraints/limitations are defined.
        word_count: Total word count.
        detail_score: Score for appropriate level of detail (0-1).
        issues: List of structural issues found.
    """

    level: QualityLevel
    has_frontmatter: bool = False
    has_title: bool = False
    section_count: int = 0
    expected_sections_found: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    has_examples: bool = False
    has_constraints: bool = False
    word_count: int = 0
    detail_score: float = 0.5
    issues: list[str] = field(default_factory=list)


@dataclass
class QualitySignal:
    """Individual quality signal from conventions.

    Attributes:
        name: Signal identifier.
        present: Whether the signal is present.
        weight: Importance weight (0-1).
        details: Additional details about the signal.
    """

    name: str
    present: bool
    weight: float = 0.5
    details: str = ""


# Expected sections based on subagent-template.md conventions
EXPECTED_AGENT_SECTIONS = [
    "core responsibilities",
    "approach",
    "best practices",
    "constraints",
    "success criteria",
]

# Alternative names for expected sections
SECTION_ALIASES = {
    "core responsibilities": [
        "responsibilities",
        "core expertise",
        "expertise",
        "capabilities",
    ],
    "approach": [
        "methodology",
        "approach",
        "workflow",
        "process",
        "architectural approach",
        "development approach",
    ],
    "best practices": [
        "best practices",
        "guidelines",
        "standards",
        "patterns",
    ],
    "constraints": [
        "constraints",
        "limitations",
        "what you cannot do",
        "boundaries",
        "restrictions",
    ],
    "success criteria": [
        "success criteria",
        "success",
        "your work is successful when",
        "deliverables",
        "outcomes",
    ],
}

# Token thresholds based on progressive-disclosure pattern
TOKEN_THRESHOLDS = {
    "metadata": 60,  # Level 1: ~60 tokens
    "overview": 2000,  # Level 2: 500-2000 tokens
    "detailed": 20000,  # Level 3: 5000-20000 tokens
    "optimal_agent": (1500, 5000),  # Ideal range for agent prompts
}

# Quality signals based on tool-restriction-patterns
QUALITY_SIGNALS = [
    ("has_clear_role_definition", 0.15),
    ("has_structured_sections", 0.15),
    ("has_concrete_examples", 0.12),
    ("has_constraints_defined", 0.12),
    ("has_success_criteria", 0.10),
    ("appropriate_detail_level", 0.10),
    ("has_actionable_guidance", 0.08),
    ("avoids_vague_language", 0.08),
    ("has_code_examples", 0.05),
    ("follows_progressive_disclosure", 0.05),
]


class ConventionsChecker:
    """Checks prompt content against context-engineering conventions.

    Provides quality assessment based on established patterns from
    the context-engineering plugin templates and best practices.
    """

    def __init__(self) -> None:
        """Initialize the conventions checker."""
        self._section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        self._h3_pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
        self._code_block_pattern = re.compile(r"```[\s\S]*?```")
        self._frontmatter_pattern = re.compile(r"^---\n[\s\S]*?\n---", re.MULTILINE)
        self._title_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)

    def assess_structure(self, content: str) -> StructureQuality:
        """Assess the structural quality of prompt content.

        Args:
            content: Prompt content to assess.

        Returns:
            StructureQuality with assessment details.
        """
        issues = []

        # Check frontmatter
        has_frontmatter = bool(self._frontmatter_pattern.search(content))
        if not has_frontmatter:
            issues.append("Missing YAML frontmatter")

        # Check title
        title_match = self._title_pattern.search(content)
        has_title = bool(title_match)
        if not has_title:
            issues.append("Missing main title (H1)")

        # Find sections
        sections = self._section_pattern.findall(content)
        section_count = len(sections)

        # Check for expected sections
        section_lower = [s.lower() for s in sections]
        expected_found = []
        missing = []

        for expected in EXPECTED_AGENT_SECTIONS:
            aliases = SECTION_ALIASES.get(expected, [expected])
            found = any(
                any(alias in s for alias in aliases)
                for s in section_lower
            )
            if found:
                expected_found.append(expected)
            else:
                missing.append(expected)

        if missing:
            issues.append(f"Missing sections: {', '.join(missing)}")

        # Check for examples
        code_blocks = self._code_block_pattern.findall(content)
        has_examples = len(code_blocks) > 0

        # Check for constraints
        has_constraints = "constraints" in expected_found or (
            "cannot" in content.lower()
            or "should not" in content.lower()
            or "must not" in content.lower()
        )

        # Word count and detail assessment
        word_count = len(content.split())
        min_words, max_words = TOKEN_THRESHOLDS["optimal_agent"]
        # Rough token-to-word ratio is ~0.75
        min_words_approx = int(min_words * 0.75)
        max_words_approx = int(max_words * 0.75)

        if word_count < min_words_approx:
            detail_score = word_count / min_words_approx
            issues.append(f"Content may be too brief ({word_count} words)")
        elif word_count > max_words_approx:
            detail_score = max_words_approx / word_count
            issues.append(f"Content may be too verbose ({word_count} words)")  # noqa: E501
        else:
            detail_score = 1.0

        # Determine overall level
        score = self._calculate_structure_score(
            has_frontmatter=has_frontmatter,
            has_title=has_title,
            section_coverage=len(expected_found) / len(EXPECTED_AGENT_SECTIONS),
            has_examples=has_examples,
            has_constraints=has_constraints,
            detail_score=detail_score,
        )

        if score >= 0.85:
            level = QualityLevel.EXCELLENT
        elif score >= 0.70:
            level = QualityLevel.GOOD
        elif score >= 0.50:
            level = QualityLevel.ACCEPTABLE
        else:
            level = QualityLevel.POOR

        return StructureQuality(
            level=level,
            has_frontmatter=has_frontmatter,
            has_title=has_title,
            section_count=section_count,
            expected_sections_found=expected_found,
            missing_sections=missing,
            has_examples=has_examples,
            has_constraints=has_constraints,
            word_count=word_count,
            detail_score=detail_score,
            issues=issues,
        )

    def _calculate_structure_score(
        self,
        has_frontmatter: bool,
        has_title: bool,
        section_coverage: float,
        has_examples: bool,
        has_constraints: bool,
        detail_score: float,
    ) -> float:
        """Calculate overall structure score.

        Args:
            has_frontmatter: Whether frontmatter is present.
            has_title: Whether title is present.
            section_coverage: Ratio of expected sections found.
            has_examples: Whether examples are present.
            has_constraints: Whether constraints are defined.
            detail_score: Score for appropriate detail level.

        Returns:
            Overall score between 0 and 1.
        """
        score = 0.0
        score += 0.10 if has_frontmatter else 0.0
        score += 0.10 if has_title else 0.0
        score += 0.30 * section_coverage
        score += 0.15 if has_examples else 0.0
        score += 0.15 if has_constraints else 0.0
        score += 0.20 * detail_score
        return score

    def get_quality_signals(self, content: str) -> list[QualitySignal]:
        """Extract quality signals from content.

        Args:
            content: Prompt content to analyze.

        Returns:
            List of QualitySignal objects.
        """
        signals = []
        content_lower = content.lower()

        # Check for clear role definition
        role_patterns = [
            r"you are (a|an)",
            r"your role is",
            r"as (a|an)",
            r"specializing in",
        ]
        has_role = any(
            re.search(pattern, content_lower)
            for pattern in role_patterns
        )
        signals.append(QualitySignal(
            name="has_clear_role_definition",
            present=has_role,
            weight=0.15,
            details="Clear role/identity statement",
        ))

        # Check for structured sections
        structure = self.assess_structure(content)
        has_structure = structure.section_count >= 3
        signals.append(QualitySignal(
            name="has_structured_sections",
            present=has_structure,
            weight=0.15,
            details=f"{structure.section_count} sections found",
        ))

        # Check for concrete examples
        code_blocks = self._code_block_pattern.findall(content)
        has_examples = len(code_blocks) >= 1
        signals.append(QualitySignal(
            name="has_concrete_examples",
            present=has_examples,
            weight=0.12,
            details=f"{len(code_blocks)} code examples",
        ))

        # Check for constraints
        constraint_patterns = [
            "you cannot",
            "do not",
            "never",
            "avoid",
            "must not",
            "should not",
            "constraints",
        ]
        has_constraints = any(
            pattern in content_lower
            for pattern in constraint_patterns
        )
        signals.append(QualitySignal(
            name="has_constraints_defined",
            present=has_constraints,
            weight=0.12,
            details="Boundaries and limitations defined",
        ))

        # Check for success criteria
        success_patterns = [
            "success criteria",
            "successful when",
            "your work is successful",
            "deliverables",
            "outcomes",
        ]
        has_success = any(
            pattern in content_lower
            for pattern in success_patterns
        )
        signals.append(QualitySignal(
            name="has_success_criteria",
            present=has_success,
            weight=0.10,
            details="Success criteria defined",
        ))

        # Check for appropriate detail level
        appropriate_detail = 0.5 <= structure.detail_score <= 1.0
        signals.append(QualitySignal(
            name="appropriate_detail_level",
            present=appropriate_detail,
            weight=0.10,
            details=f"Detail score: {structure.detail_score:.2f}",
        ))

        # Check for actionable guidance
        action_patterns = [
            "when",
            "follow these steps",
            "you should",
            "always",
            "prioritize",
            "implement",
        ]
        action_count = sum(
            1 for pattern in action_patterns
            if pattern in content_lower
        )
        has_actionable = action_count >= 3
        signals.append(QualitySignal(
            name="has_actionable_guidance",
            present=has_actionable,
            weight=0.08,
            details=f"{action_count} action patterns found",
        ))

        # Check for vague language (inverse - we want to avoid it)
        vague_patterns = [
            "as needed",
            "if appropriate",
            "when applicable",
            "generally",
            "typically",
            "usually",
        ]
        vague_count = sum(
            1 for pattern in vague_patterns
            if pattern in content_lower
        )
        avoids_vague = vague_count <= 3
        signals.append(QualitySignal(
            name="avoids_vague_language",
            present=avoids_vague,
            weight=0.08,
            details=f"{vague_count} vague phrases found",
        ))

        # Check for code examples specifically
        has_code = len(code_blocks) >= 2
        signals.append(QualitySignal(
            name="has_code_examples",
            present=has_code,
            weight=0.05,
            details=f"{len(code_blocks)} code blocks",
        ))

        # Check for progressive disclosure (references to external resources)
        ref_patterns = [
            r"see `[^`]+`",
            r"refer to",
            r"for more details",
            r"documentation",
        ]
        ref_count = sum(
            len(re.findall(pattern, content_lower))
            for pattern in ref_patterns
        )
        has_disclosure = ref_count >= 1
        signals.append(QualitySignal(
            name="follows_progressive_disclosure",
            present=has_disclosure,
            weight=0.05,
            details=f"{ref_count} references to external resources",
        ))

        return signals

    def calculate_quality_score(self, content: str) -> float:
        """Calculate overall quality score based on signals.

        Args:
            content: Prompt content to score.

        Returns:
            Quality score between 0 and 1.
        """
        signals = self.get_quality_signals(content)
        total_weight = sum(s.weight for s in signals)
        achieved = sum(s.weight for s in signals if s.present)
        return achieved / total_weight if total_weight > 0 else 0.0

    def get_improvement_suggestions(self, content: str) -> list[str]:
        """Get suggestions for improving content based on conventions.

        Args:
            content: Prompt content to analyze.

        Returns:
            List of improvement suggestions.
        """
        suggestions = []
        structure = self.assess_structure(content)
        signals = self.get_quality_signals(content)

        # Structure-based suggestions
        if not structure.has_frontmatter:
            suggestions.append(
                "Add YAML frontmatter with name, description, tools, and model"
            )

        if not structure.has_title:
            suggestions.append("Add a main title (# Heading) at the start")

        for missing in structure.missing_sections[:3]:  # Limit to top 3
            suggestions.append(f"Add a '{missing}' section")

        # Signal-based suggestions
        signal_suggestions = {
            "has_clear_role_definition": (
                "Add clear role definition: 'You are a [role] specializing in...'"
            ),
            "has_concrete_examples": (
                "Add concrete code examples showing expected behavior"
            ),
            "has_constraints_defined": (
                "Define what the agent should NOT do in a Constraints section"
            ),
            "has_success_criteria": (
                "Add Success Criteria section: 'Your work is successful when...'"
            ),
            "has_actionable_guidance": (
                "Make guidance more actionable with specific steps and patterns"
            ),
            "avoids_vague_language": (
                "Replace vague phrases like 'as needed' with specific conditions"
            ),
        }

        for signal in signals:
            if not signal.present and signal.name in signal_suggestions:
                suggestions.append(signal_suggestions[signal.name])

        # Detail level suggestions
        if structure.detail_score < 0.5:
            suggestions.append(
                "Add more detail - current content may be too brief"
            )
        elif structure.detail_score < 0.8 and structure.word_count > 4000:
            suggestions.append(
                "Consider condensing content - aim for progressive disclosure"
            )

        return suggestions[:8]  # Limit to 8 suggestions

    def get_conventions_context(self) -> dict[str, Any]:
        """Get conventions context for critique prompts.

        Returns:
            Dictionary with conventions context for LLM prompts.
        """
        return {
            "expected_sections": EXPECTED_AGENT_SECTIONS,
            "section_aliases": SECTION_ALIASES,
            "quality_signals": [
                {"name": name, "weight": weight}
                for name, weight in QUALITY_SIGNALS
            ],
            "token_guidance": {
                "optimal_range": TOKEN_THRESHOLDS["optimal_agent"],
                "too_brief": "Less than 1500 tokens may lack necessary detail",
                "too_verbose": "More than 5000 tokens may reduce focus",
            },
            "structural_requirements": [
                "YAML frontmatter with name, description, tools",
                "Main title (H1 heading)",
                "Structured sections (H2 headings)",
                "Clear role definition",
                "Actionable guidance with examples",
                "Constraints and boundaries",
                "Success criteria",
            ],
        }


def get_conventions_checker() -> ConventionsChecker:
    """Factory function to create a conventions checker.

    Returns:
        Configured ConventionsChecker instance.
    """
    return ConventionsChecker()
