"""Competency mapper for CGF optimization pipeline.

Maps test cases to competencies from evaluation criteria to determine
which prompt sections should be optimized agentically vs preserved.

Example usage:
    from harness.optimization.analysis import (
        load_eval_criteria,
        map_tests_to_competencies,
        assess_coverage,
    )

    criteria = load_eval_criteria(Path("workspace/python-expert/research/eval_criteria.yaml"))
    mapping = map_tests_to_competencies(test_suite.test_cases, criteria)
    optimizable = assess_coverage(mapping)

    for section in optimizable:
        if section.strategy == OptimizationStrategy.AGENTIC:
            # Use self-improvement
        else:
            # Preserve original
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

if TYPE_CHECKING:
    from harness.optimization.testcases.models import TestCase

logger = structlog.get_logger(__name__)


class OptimizationStrategy(str, Enum):
    """Strategy for optimizing a prompt section."""

    AGENTIC = "agentic"  # Use LLM self-critique
    PRESERVE = "preserve"  # Keep original (insufficient test coverage)


class PromptSection(str, Enum):
    """Standard prompt sections from agent template."""

    ROLE_DEFINITION = "role_definition"
    CORE_APPROACH = "core_approach"
    BEST_PRACTICES = "best_practices"
    CONSTRAINTS = "constraints"
    EXAMPLES = "examples"
    OUTPUT_FORMAT = "output_format"
    SUMMARY = "summary"


# Mapping from competency categories to prompt sections
CATEGORY_TO_SECTION: dict[str, PromptSection] = {
    # Patterns and syntax → core approach
    "patterns": PromptSection.CORE_APPROACH,
    "syntax": PromptSection.CORE_APPROACH,
    "fundamentals": PromptSection.CORE_APPROACH,
    "async": PromptSection.CORE_APPROACH,
    "concurrency": PromptSection.CORE_APPROACH,
    # Performance and optimization → best practices
    "performance": PromptSection.BEST_PRACTICES,
    "optimization": PromptSection.BEST_PRACTICES,
    "efficiency": PromptSection.BEST_PRACTICES,
    "code_quality": PromptSection.BEST_PRACTICES,
    "style": PromptSection.BEST_PRACTICES,
    "conventions": PromptSection.BEST_PRACTICES,
    # Error handling and edge cases → constraints
    "error_handling": PromptSection.CONSTRAINTS,
    "edge_cases": PromptSection.CONSTRAINTS,
    "safety": PromptSection.CONSTRAINTS,
    "security": PromptSection.CONSTRAINTS,
    "validation": PromptSection.CONSTRAINTS,
    # Testing and quality → output format
    "testing": PromptSection.OUTPUT_FORMAT,
    "quality": PromptSection.OUTPUT_FORMAT,
    "documentation": PromptSection.OUTPUT_FORMAT,
    # Negative/mistake tests → examples
    "negative": PromptSection.EXAMPLES,
    "common_mistake": PromptSection.EXAMPLES,
}


@dataclass
class Competency:
    """Single competency from evaluation criteria.

    Attributes:
        competency_id: Explicit ID from YAML (e.g., "async-001").
        name: Human-readable competency name.
        description: Detailed description of the competency.
        importance: Priority level (high, medium, low).
        category: Category tag for mapping to sections.
        positive_indicators: Behaviors that indicate competency.
        negative_indicators: Behaviors that violate competency.
        test_scenarios: Specific scenarios to test.
    """

    name: str
    competency_id: str = ""  # Explicit ID from YAML (e.g., "async-001")
    description: str = ""
    importance: str = "medium"
    category: str = ""
    positive_indicators: list[str] = field(default_factory=list)
    negative_indicators: list[str] = field(default_factory=list)
    test_scenarios: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Return explicit ID or generate from name if not provided."""
        if self.competency_id:
            return self.competency_id
        return self.name.lower().replace(" ", "-").replace("/", "-")

    def get_section(self) -> PromptSection:
        """Determine which prompt section this competency maps to."""
        category_lower = self.category.lower() if self.category else ""

        # Try direct category match
        if category_lower in CATEGORY_TO_SECTION:
            return CATEGORY_TO_SECTION[category_lower]

        # Try matching category in competency name
        name_lower = self.name.lower()
        for cat, section in CATEGORY_TO_SECTION.items():
            if cat in name_lower:
                return section

        # Default to core approach
        return PromptSection.CORE_APPROACH


@dataclass
class EdgeCase:
    """Edge case scenario from evaluation criteria.

    Attributes:
        scenario: Description of the edge case.
        importance: Why this edge case matters.
        expected_handling: How the agent should handle it.
        common_failure: Common failure mode.
    """

    scenario: str
    importance: str = ""
    expected_handling: str = ""
    common_failure: str = ""

    @property
    def id(self) -> str:
        """Generate a slug-style ID from the scenario."""
        # Take first few words
        words = self.scenario.lower().split()[:4]
        return "-".join(words).replace("/", "-")


@dataclass
class CommonMistake:
    """Common mistake from evaluation criteria.

    Attributes:
        mistake: Description of the mistake.
        correction: How to correct the mistake.
        severity: Severity level (high, medium, low).
    """

    mistake: str
    correction: str = ""
    severity: str = "medium"

    @property
    def id(self) -> str:
        """Generate a slug-style ID from the mistake."""
        words = self.mistake.lower().split()[:4]
        return "-".join(words).replace("/", "-")


@dataclass
class EvalCriteria:
    """Evaluation criteria loaded from YAML.

    Attributes:
        resource_id: ID of the resource being optimized.
        resource_type: Type of resource (agent, skill, etc.).
        optimization_goal: Goal of the optimization.
        competencies: List of competencies to evaluate.
        edge_cases: List of edge cases to test.
        common_mistakes: List of common mistakes to avoid.
        metadata: Additional metadata from the YAML.
    """

    resource_id: str
    resource_type: str = "agent"
    optimization_goal: str = ""
    competencies: list[Competency] = field(default_factory=list)
    edge_cases: list[EdgeCase] = field(default_factory=list)
    common_mistakes: list[CommonMistake] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizableSection:
    """A prompt section that can be optimized.

    Attributes:
        section: The prompt section identifier.
        strategy: Optimization strategy to use.
        test_count: Number of tests covering this section.
        quantitative_count: Number of quantitative tests.
        qualitative_count: Number of qualitative tests.
        test_ids: IDs of tests covering this section.
        competency_ids: IDs of competencies in this section.
        reason: Human-readable reason for the strategy.
    """

    section: PromptSection
    strategy: OptimizationStrategy
    test_count: int = 0
    quantitative_count: int = 0
    qualitative_count: int = 0
    test_ids: list[str] = field(default_factory=list)
    competency_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "section": self.section.value,
            "strategy": self.strategy.value,
            "test_count": self.test_count,
            "quantitative_count": self.quantitative_count,
            "qualitative_count": self.qualitative_count,
            "test_ids": self.test_ids,
            "competency_ids": self.competency_ids,
            "reason": self.reason,
        }


def load_eval_criteria(criteria_path: Path) -> EvalCriteria:
    """Load evaluation criteria from YAML file.

    Args:
        criteria_path: Path to eval_criteria.yaml.

    Returns:
        EvalCriteria object with parsed content.

    Raises:
        FileNotFoundError: If criteria file doesn't exist.
        ValueError: If YAML is invalid or missing required fields.
    """
    if not criteria_path.exists():
        raise FileNotFoundError(f"Criteria file not found: {criteria_path}")

    with open(criteria_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty criteria file: {criteria_path}")

    # Parse competencies
    competencies = []
    for comp_data in data.get("competencies", []):
        if isinstance(comp_data, dict):
            competencies.append(
                Competency(
                    name=comp_data.get("name", ""),
                    competency_id=comp_data.get("id", ""),  # Explicit ID from YAML
                    description=comp_data.get("description", ""),
                    importance=comp_data.get("importance", "medium"),
                    category=comp_data.get("category", ""),
                    positive_indicators=comp_data.get("positive_indicators", [])
                    or comp_data.get("success_indicators", []),  # Support both field names
                    negative_indicators=comp_data.get("negative_indicators", []),
                    test_scenarios=comp_data.get("test_scenarios", []),
                )
            )

    # Parse edge cases
    edge_cases = []
    for edge_data in data.get("edge_cases", []):
        if isinstance(edge_data, dict):
            edge_cases.append(
                EdgeCase(
                    scenario=edge_data.get("scenario", ""),
                    importance=edge_data.get("importance", ""),
                    expected_handling=edge_data.get("expected_handling", ""),
                    common_failure=edge_data.get("common_failure", ""),
                )
            )

    # Parse common mistakes
    common_mistakes = []
    for mistake_data in data.get("common_mistakes", []):
        if isinstance(mistake_data, dict):
            common_mistakes.append(
                CommonMistake(
                    mistake=mistake_data.get("mistake", ""),
                    correction=mistake_data.get("correction", ""),
                    severity=mistake_data.get("severity", "medium"),
                )
            )

    logger.info(
        "Loaded eval criteria",
        resource_id=data.get("resource_id", "unknown"),
        competencies=len(competencies),
        edge_cases=len(edge_cases),
        common_mistakes=len(common_mistakes),
    )

    return EvalCriteria(
        resource_id=data.get("resource_id", ""),
        resource_type=data.get("resource_type", "agent"),
        optimization_goal=data.get("optimization_goal", ""),
        competencies=competencies,
        edge_cases=edge_cases,
        common_mistakes=common_mistakes,
        metadata=data.get("metadata", {}),
    )


def is_quantitative_test(test: TestCase) -> bool:
    """Check if a test uses quantitative (code-based) validation.

    Quantitative tests provide deterministic, measurable feedback.

    Args:
        test: Test case to check.

    Returns:
        True if test uses quantitative validation, False otherwise.
    """
    return is_deterministic_test(test) or is_llm_judge_test(test)


def is_deterministic_test(test: TestCase) -> bool:
    """Check if a test uses deterministic (non-LLM) validation.

    Deterministic tests produce consistent, reproducible results.
    These require 6+ tests to avoid overfitting due to their binary nature.

    Args:
        test: Test case to check.

    Returns:
        True if test uses deterministic validation.
    """
    validation = test.validation

    # Get validation type as string
    val_type = validation.type
    if hasattr(val_type, "value"):
        val_type = val_type.value

    # Regex, contains, and exact match are deterministic
    deterministic_types = (
        "regex", "contains", "exact", "contains_all", "contains_any"
    )
    if val_type in deterministic_types:
        return True

    # Code validators with syntax checking are deterministic
    if val_type in ("code", "code_syntax"):
        return validation.require_syntax_valid

    # JSON schema validation is deterministic
    if val_type in ("json", "json_schema"):
        return True

    return False


def is_llm_judge_test(test: TestCase) -> bool:
    """Check if a test uses LLM-as-judge validation.

    LLM-judge tests can score outputs on a scale (0-100).

    Args:
        test: Test case to check.

    Returns:
        True if test uses LLM-judge validation.
    """
    validation = test.validation

    # Get validation type as string
    val_type = validation.type
    if hasattr(val_type, "value"):
        val_type = val_type.value

    # LLM-based validators
    if val_type in ("llm_judge", "semantic", "code_llm"):
        return True

    return False


def map_tests_to_competencies(
    tests: list[TestCase],
    criteria: EvalCriteria,
) -> dict[str, list[TestCase]]:
    """Map test cases to competencies based on tags and metadata.

    The mapping algorithm:
    1. For each test, check if any tag matches a competency ID directly
    2. Also check category-based matches
    3. Build competency_id → [tests] mapping

    Args:
        tests: List of test cases from test suite.
        criteria: Evaluation criteria with competencies.

    Returns:
        Dictionary mapping competency IDs to lists of test cases.
    """
    mapping: dict[str, list[TestCase]] = {}

    # Initialize mapping with all competency IDs
    competency_ids: set[str] = set()
    for comp in criteria.competencies:
        mapping[comp.id] = []
        competency_ids.add(comp.id)

    # Build category → competencies lookup
    category_to_competencies: dict[str, list[Competency]] = {}
    for comp in criteria.competencies:
        category = comp.category.lower() if comp.category else ""
        if category:
            if category not in category_to_competencies:
                category_to_competencies[category] = []
            category_to_competencies[category].append(comp)

    # Map each test to competencies
    for test in tests:
        matched_competencies: set[str] = set()

        # Check tags for direct ID matches (e.g., "async-001", "perf-002")
        for tag in test.tags:
            tag_lower = tag.lower()

            # Direct ID match (most important)
            if tag_lower in competency_ids:
                matched_competencies.add(tag_lower)

            # Category match (e.g., "patterns" → all pattern competencies)
            elif tag_lower in category_to_competencies:
                for comp in category_to_competencies[tag_lower]:
                    matched_competencies.add(comp.id)

        # Also check metadata for competency references
        source_comp = test.metadata.get("source_competency", "")
        if source_comp:
            source_lower = source_comp.lower()
            for comp in criteria.competencies:
                if source_lower in comp.name.lower():
                    matched_competencies.add(comp.id)

        # Add test to all matched competencies
        for comp_id in matched_competencies:
            if comp_id in mapping:
                mapping[comp_id].append(test)

    # Log mapping results
    total_mapped = sum(len(tests) for tests in mapping.values())
    logger.info(
        "Mapped tests to competencies",
        total_tests=len(tests),
        total_mappings=total_mapped,
        competencies_with_tests=sum(
            1 for tests in mapping.values() if tests
        ),
    )

    for comp_id, comp_tests in mapping.items():
        if comp_tests:
            logger.debug(
                "Competency test mapping",
                competency_id=comp_id,
                test_count=len(comp_tests),
            )

    return mapping


def assess_coverage(
    mapping: dict[str, list[TestCase]],
    criteria: EvalCriteria | None = None,
) -> list[OptimizableSection]:
    """Assess test coverage and determine optimization strategy per section.

    Strategy Selection:
    - AGENTIC: Sections with test coverage (LLM self-critique)
    - PRESERVE: Sections with no test coverage

    Args:
        mapping: Competency ID → test cases mapping.
        criteria: Optional criteria for competency lookup.

    Returns:
        List of OptimizableSection objects with strategies.
    """
    # Group by prompt section
    section_data: dict[PromptSection, dict[str, Any]] = {}

    for comp_id, tests in mapping.items():
        # Determine section for this competency
        section = PromptSection.CORE_APPROACH
        if criteria:
            comp = next(
                (c for c in criteria.competencies if c.id == comp_id), None
            )
            if comp:
                section = comp.get_section()

        if section not in section_data:
            section_data[section] = {
                "tests": [],
                "test_ids": set(),
                "competency_ids": set(),
                "deterministic_count": 0,
                "llm_judge_count": 0,
                "qualitative_count": 0,
            }

        data = section_data[section]
        data["competency_ids"].add(comp_id)

        for test in tests:
            if test.id not in data["test_ids"]:
                data["test_ids"].add(test.id)
                data["tests"].append(test)

                if is_deterministic_test(test):
                    data["deterministic_count"] += 1
                elif is_llm_judge_test(test):
                    data["llm_judge_count"] += 1
                else:
                    data["qualitative_count"] += 1

    # Determine strategy for each section
    results: list[OptimizableSection] = []

    for section in PromptSection:
        data = section_data.get(section)

        if not data or len(data["tests"]) == 0:
            results.append(
                OptimizableSection(
                    section=section,
                    strategy=OptimizationStrategy.PRESERVE,
                    test_count=0,
                    quantitative_count=0,
                    qualitative_count=0,
                    test_ids=[],
                    competency_ids=[],
                    reason="no test coverage",
                )
            )
            continue

        deterministic = data["deterministic_count"]
        llm_judge = data["llm_judge_count"]
        qualitative = data["qualitative_count"]
        total = len(data["tests"])
        quantitative = deterministic + llm_judge

        strategy = OptimizationStrategy.AGENTIC
        reason = f"{total} tests ({deterministic} det, {llm_judge} llm, {qualitative} qual)"

        results.append(
            OptimizableSection(
                section=section,
                strategy=strategy,
                test_count=total,
                quantitative_count=quantitative,
                qualitative_count=qualitative,
                test_ids=list(data["test_ids"]),
                competency_ids=list(data["competency_ids"]),
                reason=reason,
            )
        )

        logger.info(
            "Assessed section coverage",
            section=section.value,
            strategy=strategy.value,
            test_count=total,
            quantitative=quantitative,
            qualitative=qualitative,
        )

    return results


def get_section_tests(
    section: PromptSection,
    mapping: dict[str, list[TestCase]],
    criteria: EvalCriteria,
) -> list[TestCase]:
    """Get all tests relevant to a specific prompt section.

    Args:
        section: The prompt section to get tests for.
        mapping: Competency ID → test cases mapping.
        criteria: Evaluation criteria with competencies.

    Returns:
        List of test cases for the section (deduplicated).
    """
    test_ids_seen: set[str] = set()
    tests: list[TestCase] = []

    for comp in criteria.competencies:
        if comp.get_section() == section:
            for test in mapping.get(comp.id, []):
                if test.id not in test_ids_seen:
                    test_ids_seen.add(test.id)
                    tests.append(test)

    return tests
