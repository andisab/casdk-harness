"""Focused test suite generator for targeted optimization.

Creates subset test suites containing only tests relevant to specific
competencies or prompt sections, enabling focused programmatic optimization.

Example usage:
    from harness.optimization.analysis import (
        load_eval_criteria,
        map_tests_to_competencies,
        assess_coverage,
    )
    from harness.optimization.analysis.test_subset import (
        create_focused_suite_for_section,
        write_temp_suite,
    )

    criteria = load_eval_criteria(criteria_path)
    mapping = map_tests_to_competencies(test_suite.test_cases, criteria)
    sections = assess_coverage(mapping, criteria)

    for section in sections:
        if section.strategy == OptimizationStrategy.PROGRAMMATIC:
            focused = create_focused_suite_for_section(
                base_suite, section, mapping, criteria
            )
            temp_path = write_temp_suite(focused, workspace_dir / "tests")
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

from harness.optimization.analysis.competency_mapper import (
    EvalCriteria,
    OptimizableSection,
    PromptSection,
    get_section_tests,
)
from harness.optimization.testcases.models import TestCase, TestSuite, ValidationConfig

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


def create_focused_suite(
    base_suite: TestSuite,
    test_ids: list[str],
    suffix: str = "focused",
) -> TestSuite:
    """Create a focused test suite with only specified tests.

    Args:
        base_suite: Original test suite to filter.
        test_ids: IDs of tests to include in focused suite.
        suffix: Suffix to add to suite name.

    Returns:
        New TestSuite containing only specified tests.
    """
    # Filter test cases by ID
    focused_tests = [tc for tc in base_suite.test_cases if tc.id in test_ids]

    if not focused_tests:
        logger.warning(
            "No tests found for focused suite",
            requested_ids=test_ids,
            available_ids=[tc.id for tc in base_suite.test_cases],
        )

    focused_suite = TestSuite(
        name=f"{base_suite.name}-{suffix}",
        agent_name=base_suite.agent_name,
        description=f"Focused subset of {base_suite.name} ({len(focused_tests)} tests)",
        version=base_suite.version,
        test_cases=focused_tests,
        metadata={
            **base_suite.metadata,
            "focused": True,
            "parent_suite": base_suite.name,
            "test_count": len(focused_tests),
            "original_test_count": len(base_suite.test_cases),
        },
    )

    logger.info(
        "Created focused test suite",
        name=focused_suite.name,
        test_count=len(focused_tests),
        test_ids=test_ids,
    )

    return focused_suite


def create_focused_suite_for_section(
    base_suite: TestSuite,
    section: OptimizableSection,
    mapping: dict[str, list[TestCase]],
    criteria: EvalCriteria,
) -> TestSuite:
    """Create a focused suite for a specific prompt section.

    Args:
        base_suite: Original test suite.
        section: The prompt section to create tests for.
        mapping: Competency ID → test cases mapping.
        criteria: Evaluation criteria with competencies.

    Returns:
        New TestSuite containing only tests for the section.
    """
    # Get all tests for this section
    section_tests = get_section_tests(section.section, mapping, criteria)

    # Use test IDs to create focused suite
    test_ids = [t.id for t in section_tests]

    suffix = f"{section.section.value}-focused"
    return create_focused_suite(base_suite, test_ids, suffix)


def create_focused_suite_for_competency(
    base_suite: TestSuite,
    competency_id: str,
    mapping: dict[str, list[TestCase]],
) -> TestSuite:
    """Create a focused suite for a specific competency.

    Args:
        base_suite: Original test suite.
        competency_id: ID of competency to create tests for.
        mapping: Competency ID → test cases mapping.

    Returns:
        New TestSuite containing only tests for the competency.
    """
    tests = mapping.get(competency_id, [])
    test_ids = [t.id for t in tests]

    suffix = f"{competency_id}-focused"
    return create_focused_suite(base_suite, test_ids, suffix)


def _validation_config_to_dict(config: ValidationConfig) -> dict[str, Any]:
    """Convert ValidationConfig to serializable dict.

    Args:
        config: Validation configuration object.

    Returns:
        Dictionary representation for YAML serialization.
    """
    result: dict[str, Any] = {}

    # Handle type (could be enum or string)
    val_type = config.type
    if hasattr(val_type, "value"):
        result["type"] = val_type.value
    else:
        result["type"] = str(val_type)

    result["criteria"] = config.criteria

    # Only include optional fields if non-default
    if config.partial_credit:
        result["partial_credit"] = config.partial_credit

    # Code-specific fields
    if result["type"] in ("code", "code_syntax", "code_llm"):
        result["language"] = config.language
        result["require_syntax_valid"] = config.require_syntax_valid
        if config.min_code_lines > 0:
            result["min_code_lines"] = config.min_code_lines

    return result


def _test_case_to_dict(test_case: TestCase) -> dict[str, Any]:
    """Convert TestCase to serializable dict for YAML.

    Args:
        test_case: Test case object.

    Returns:
        Dictionary representation for YAML serialization.
    """
    result: dict[str, Any] = {
        "id": test_case.id,
        "prompt": test_case.prompt,
        "expected_behavior": test_case.expected_behavior,
        "validation": _validation_config_to_dict(test_case.validation),
    }

    # Optional fields
    if test_case.timeout_seconds != 300:
        result["timeout_seconds"] = test_case.timeout_seconds

    if test_case.tags:
        result["tags"] = test_case.tags

    if test_case.metadata:
        result["metadata"] = test_case.metadata

    return result


def write_temp_suite(
    suite: TestSuite,
    output_dir: Path,
    filename: str | None = None,
) -> Path:
    """Write a test suite to a temporary YAML file.

    Args:
        suite: Test suite to write.
        output_dir: Directory to write the file to.
        filename: Optional custom filename. Defaults to {suite.name}.yaml.

    Returns:
        Path to the written YAML file.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    if filename is None:
        # Sanitize suite name for filename
        safe_name = suite.name.replace(" ", "_").replace("/", "-")
        filename = f"{safe_name}.yaml"

    output_path = output_dir / filename

    # Convert suite to dict for YAML serialization
    suite_dict: dict[str, Any] = {
        "name": suite.name,
        "agent_name": suite.agent_name,
        "description": suite.description,
        "version": suite.version,
        "test_cases": [_test_case_to_dict(tc) for tc in suite.test_cases],
    }

    if suite.metadata:
        suite_dict["metadata"] = {
            **suite.metadata,
            "generated_at": datetime.now().isoformat(),
            "generator": "cgf-prompt-optimizer",
        }

    # Write YAML with nice formatting
    with open(output_path, "w") as f:
        yaml.dump(
            suite_dict,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

    logger.info(
        "Wrote focused test suite",
        path=str(output_path),
        test_count=len(suite.test_cases),
    )

    return output_path


def load_focused_suite(suite_path: Path) -> TestSuite:
    """Load a test suite from YAML file.

    Args:
        suite_path: Path to the YAML file.

    Returns:
        TestSuite object.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If YAML is invalid.
    """
    if not suite_path.exists():
        raise FileNotFoundError(f"Test suite not found: {suite_path}")

    with open(suite_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty test suite file: {suite_path}")

    return TestSuite(
        name=data.get("name", ""),
        agent_name=data.get("agent_name", ""),
        description=data.get("description", ""),
        version=data.get("version", "1.0"),
        test_cases=data.get("test_cases", []),
        metadata=data.get("metadata", {}),
    )


def create_section_suites(
    base_suite: TestSuite,
    sections: list[OptimizableSection],
    mapping: dict[str, list[TestCase]],
    criteria: EvalCriteria,
    output_dir: Path,
) -> dict[PromptSection, Path]:
    """Create focused test suites for all programmatic sections.

    Args:
        base_suite: Original full test suite.
        sections: List of optimizable sections with strategies.
        mapping: Competency ID → test cases mapping.
        criteria: Evaluation criteria.
        output_dir: Directory to write focused suites.

    Returns:
        Dictionary mapping sections to their focused suite file paths.
    """
    from harness.optimization.analysis.competency_mapper import OptimizationStrategy

    result: dict[PromptSection, Path] = {}

    for section in sections:
        if section.strategy != OptimizationStrategy.PROGRAMMATIC:
            continue

        if section.test_count < 3:
            logger.warning(
                "Skipping section with insufficient tests",
                section=section.section.value,
                test_count=section.test_count,
            )
            continue

        # Create focused suite for this section
        focused = create_focused_suite_for_section(
            base_suite, section, mapping, criteria
        )

        # Write to file
        filename = f"focused_{section.section.value}.yaml"
        path = write_temp_suite(focused, output_dir, filename)
        result[section.section] = path

        logger.info(
            "Created section suite",
            section=section.section.value,
            path=str(path),
            test_count=len(focused.test_cases),
        )

    return result
