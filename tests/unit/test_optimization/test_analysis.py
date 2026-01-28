"""Unit tests for the optimization analysis module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from harness.optimization.analysis import (
    CommonMistake,
    Competency,
    EdgeCase,
    EvalCriteria,
    OptimizableSection,
    OptimizationStrategy,
    PromptSection,
    assess_coverage,
    is_quantitative_test,
    load_eval_criteria,
    map_tests_to_competencies,
)
from harness.optimization.analysis.synthesizer import (
    ParsedPrompt,
    PromptSynthesizer,
    SynthesisResult,
    merge_optimized_sections,
)
from harness.optimization.analysis.test_subset import (
    create_focused_suite,
    write_temp_suite,
)
from harness.optimization.testcases import (
    TestCase,
    TestSuite,
    ValidationConfig,
)


class TestCompetency:
    """Tests for Competency dataclass."""

    def test_competency_id_generation(self) -> None:
        """Test ID is generated from name."""
        comp = Competency(name="Async/await fundamentals")
        assert comp.id == "async-await-fundamentals"

    def test_competency_section_mapping(self) -> None:
        """Test competency maps to correct section."""
        comp = Competency(name="Async patterns", category="async")
        assert comp.get_section() == PromptSection.CORE_APPROACH

        comp2 = Competency(name="Error handling", category="error_handling")
        assert comp2.get_section() == PromptSection.CONSTRAINTS

    def test_competency_default_section(self) -> None:
        """Test unknown category defaults to core_approach."""
        comp = Competency(name="Unknown skill")
        assert comp.get_section() == PromptSection.CORE_APPROACH


class TestEdgeCase:
    """Tests for EdgeCase dataclass."""

    def test_edge_case_id_generation(self) -> None:
        """Test ID is generated from scenario."""
        edge = EdgeCase(scenario="Cancellation during await operation")
        assert edge.id == "cancellation-during-await-operation"


class TestCommonMistake:
    """Tests for CommonMistake dataclass."""

    def test_mistake_id_generation(self) -> None:
        """Test ID is generated from mistake description."""
        mistake = CommonMistake(mistake="Using time.sleep instead of asyncio")
        assert mistake.id == "using-time.sleep-instead-of"


class TestLoadEvalCriteria:
    """Tests for load_eval_criteria function."""

    def test_load_valid_criteria(self) -> None:
        """Test loading valid eval criteria YAML."""
        criteria_data = {
            "resource_id": "python-expert",
            "resource_type": "agent",
            "optimization_goal": "async programming",
            "competencies": [
                {
                    "name": "Async fundamentals",
                    "description": "Understanding async/await",
                    "importance": "high",
                    "category": "async",
                    "positive_indicators": ["Uses await correctly"],
                    "negative_indicators": ["Blocks event loop"],
                    "test_scenarios": ["Write async fetcher"],
                }
            ],
            "edge_cases": [
                {
                    "scenario": "Task cancellation",
                    "importance": "Handle gracefully",
                    "expected_handling": "Use try/finally",
                    "common_failure": "Resource leak",
                }
            ],
            "common_mistakes": [
                {
                    "mistake": "Using time.sleep",
                    "correction": "Use asyncio.sleep",
                    "severity": "high",
                }
            ],
        }

        with TemporaryDirectory() as tmpdir:
            criteria_path = Path(tmpdir) / "eval_criteria.yaml"
            with open(criteria_path, "w") as f:
                yaml.dump(criteria_data, f)

            criteria = load_eval_criteria(criteria_path)

            assert criteria.resource_id == "python-expert"
            assert criteria.resource_type == "agent"
            assert len(criteria.competencies) == 1
            assert len(criteria.edge_cases) == 1
            assert len(criteria.common_mistakes) == 1
            assert criteria.competencies[0].name == "Async fundamentals"

    def test_load_missing_file_raises(self) -> None:
        """Test loading missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_eval_criteria(Path("/nonexistent/path/criteria.yaml"))

    def test_load_empty_file_raises(self) -> None:
        """Test loading empty file raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            criteria_path = Path(tmpdir) / "empty.yaml"
            criteria_path.write_text("")

            with pytest.raises(ValueError, match="Empty criteria"):
                load_eval_criteria(criteria_path)


class TestIsQuantitativeTest:
    """Tests for is_quantitative_test function."""

    def test_code_validation_is_quantitative(self) -> None:
        """Test code validation type is quantitative."""
        test = TestCase(
            id="test-1",
            prompt="Write a function",
            expected_behavior="Valid function",
            validation=ValidationConfig(
                type="code",
                criteria="def ",
                require_syntax_valid=True,
            ),
        )
        assert is_quantitative_test(test) is True

    def test_code_validation_without_syntax_check_not_quantitative(self) -> None:
        """Test code validation without syntax check is not quantitative."""
        test = TestCase(
            id="test-1",
            prompt="Write code",
            expected_behavior="Some code",
            validation=ValidationConfig(
                type="code",
                criteria="def ",
                require_syntax_valid=False,
            ),
        )
        assert is_quantitative_test(test) is False

    def test_llm_judge_not_quantitative(self) -> None:
        """Test llm_judge validation is not quantitative."""
        test = TestCase(
            id="test-1",
            prompt="Explain something",
            expected_behavior="Good explanation",
            validation=ValidationConfig(
                type="llm_judge",
                criteria="Evaluate the quality",
            ),
        )
        # LLM-judge tests ARE quantitative (provide numeric scores 0-100)
        # They just use different threshold (3+) vs deterministic (6+)
        assert is_quantitative_test(test) is True

    def test_regex_is_quantitative(self) -> None:
        """Test regex validation is quantitative."""
        test = TestCase(
            id="test-1",
            prompt="Generate output",
            expected_behavior="Matches pattern",
            validation=ValidationConfig(
                type="regex",
                criteria=r"def \w+\(",
            ),
        )
        assert is_quantitative_test(test) is True

    def test_contains_is_quantitative(self) -> None:
        """Test contains validation is quantitative."""
        test = TestCase(
            id="test-1",
            prompt="Generate output",
            expected_behavior="Contains keyword",
            validation=ValidationConfig(
                type="contains",
                criteria="async def",
            ),
        )
        assert is_quantitative_test(test) is True


class TestMapTestsToCompetencies:
    """Tests for map_tests_to_competencies function."""

    def test_mapping_by_tags(self) -> None:
        """Test mapping tests to competencies by tags."""
        criteria = EvalCriteria(
            resource_id="test",
            competencies=[
                Competency(name="Async", category="async"),
                Competency(name="Errors", category="error_handling"),
            ],
        )

        tests = [
            TestCase(
                id="test-async-1",
                prompt="Test async",
                expected_behavior="Works",
                validation=ValidationConfig(type="code", criteria="async"),
                tags=["async"],
            ),
            TestCase(
                id="test-error-1",
                prompt="Test errors",
                expected_behavior="Handles",
                validation=ValidationConfig(type="code", criteria="except"),
                tags=["error_handling"],
            ),
        ]

        mapping = map_tests_to_competencies(tests, criteria)

        assert "async" in mapping
        assert len(mapping["async"]) == 1
        assert mapping["async"][0].id == "test-async-1"

        assert "errors" in mapping
        assert len(mapping["errors"]) == 1
        assert mapping["errors"][0].id == "test-error-1"


class TestAssessCoverage:
    """Tests for assess_coverage function."""

    def test_programmatic_strategy_with_enough_tests(self) -> None:
        """Test programmatic strategy when 6+ deterministic tests exist."""
        mapping = {
            "comp1": [
                TestCase(
                    id=f"test-{i}",
                    prompt="Test",
                    expected_behavior="Works",
                    validation=ValidationConfig(
                        type="code", criteria="def", require_syntax_valid=True
                    ),
                )
                for i in range(7)  # Need 6+ deterministic tests
            ]
        }

        criteria = EvalCriteria(
            resource_id="test",
            competencies=[Competency(name="comp1", category="async")],
        )

        sections = assess_coverage(mapping, criteria)

        # Find the core_approach section (async maps there)
        core_section = next(
            (s for s in sections if s.section == PromptSection.CORE_APPROACH),
            None,
        )
        assert core_section is not None
        assert core_section.strategy == OptimizationStrategy.PROGRAMMATIC
        assert core_section.quantitative_count >= 6

    def test_preserve_strategy_with_insufficient_tests(self) -> None:
        """Test preserve strategy when fewer than threshold tests exist."""
        mapping = {
            "comp1": [
                TestCase(
                    id="test-1",
                    prompt="Test",
                    expected_behavior="Works",
                    validation=ValidationConfig(
                        type="code", criteria="def", require_syntax_valid=True
                    ),
                )
            ]
        }

        criteria = EvalCriteria(
            resource_id="test",
            competencies=[Competency(name="comp1", category="async")],
        )

        sections = assess_coverage(mapping, criteria)

        core_section = next(
            (s for s in sections if s.section == PromptSection.CORE_APPROACH),
            None,
        )
        assert core_section is not None
        # With only 1 test, should preserve or use agentic
        assert core_section.strategy in (
            OptimizationStrategy.PRESERVE,
            OptimizationStrategy.AGENTIC,
        )


class TestCreateFocusedSuite:
    """Tests for create_focused_suite function."""

    def test_create_focused_suite_filters_tests(self) -> None:
        """Test focused suite contains only specified tests."""
        base_suite = TestSuite(
            name="full-suite",
            agent_name="test-agent",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Test 1",
                    expected_behavior="Works",
                    validation=ValidationConfig(type="code", criteria="def"),
                ),
                TestCase(
                    id="test-2",
                    prompt="Test 2",
                    expected_behavior="Works",
                    validation=ValidationConfig(type="code", criteria="def"),
                ),
                TestCase(
                    id="test-3",
                    prompt="Test 3",
                    expected_behavior="Works",
                    validation=ValidationConfig(type="code", criteria="def"),
                ),
            ],
        )

        focused = create_focused_suite(base_suite, ["test-1", "test-3"])

        assert len(focused.test_cases) == 2
        assert focused.test_cases[0].id == "test-1"
        assert focused.test_cases[1].id == "test-3"
        assert focused.metadata["focused"] is True
        assert focused.metadata["parent_suite"] == "full-suite"


class TestWriteTempSuite:
    """Tests for write_temp_suite function."""

    def test_write_and_load_suite(self) -> None:
        """Test writing and reading back a suite."""
        suite = TestSuite(
            name="test-suite",
            agent_name="test-agent",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Test prompt",
                    expected_behavior="Expected behavior",
                    validation=ValidationConfig(
                        type="code", criteria="def", language="python"
                    ),
                    tags=["tag1", "tag2"],
                ),
            ],
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            path = write_temp_suite(suite, output_dir)

            assert path.exists()
            assert path.suffix == ".yaml"

            # Read back and verify
            with open(path) as f:
                data = yaml.safe_load(f)

            assert data["name"] == "test-suite"
            assert data["agent_name"] == "test-agent"
            assert len(data["test_cases"]) == 1
            assert data["test_cases"][0]["id"] == "test-1"


class TestPromptSynthesizer:
    """Tests for PromptSynthesizer."""

    def test_parse_prompt_with_frontmatter(self) -> None:
        """Test parsing prompt with YAML frontmatter."""
        prompt = """---
name: test-agent
description: A test agent
---

# Test Agent

<role_definition>
You are a test agent.
</role_definition>

<constraints>
Follow these rules.
</constraints>
"""
        synthesizer = PromptSynthesizer()
        parsed = synthesizer.parse_prompt(prompt)

        assert parsed.frontmatter["name"] == "test-agent"
        assert parsed.title == "Test Agent"
        assert "role_definition" in parsed.sections
        assert "constraints" in parsed.sections
        assert "You are a test agent." in parsed.sections["role_definition"]

    def test_merge_optimized_sections(self) -> None:
        """Test merging optimized sections into prompt."""
        original = """---
name: test
description: A test agent
---

# Test

<core_approach>
Original approach.
</core_approach>

<constraints>
Original constraints.
</constraints>
"""
        synthesizer = PromptSynthesizer()
        result = synthesizer.merge(
            original,
            optimized_sections={"core_approach": "Optimized approach content."},
        )

        assert result.success
        assert "Optimized approach content" in result.merged_prompt
        assert "Original constraints" in result.merged_prompt
        assert "core_approach" in result.sections_merged
        assert "constraints" in result.sections_preserved

    def test_validate_prompt_structure(self) -> None:
        """Test validation detects missing frontmatter."""
        synthesizer = PromptSynthesizer()
        errors = synthesizer.validate("# No Frontmatter")
        assert any("frontmatter" in e.lower() for e in errors)

    def test_validate_unbalanced_tags(self) -> None:
        """Test validation detects unbalanced XML tags."""
        prompt = """---
name: test
---

<role_definition>
Missing closing tag.
"""
        synthesizer = PromptSynthesizer()
        errors = synthesizer.validate(prompt)
        assert any("unmatched" in e.lower() for e in errors)


class TestMergeOptimizedSections:
    """Tests for merge_optimized_sections convenience function."""

    def test_merge_with_prompt_section_enum(self) -> None:
        """Test merging using PromptSection enum keys."""
        original = """---
name: test
description: A test agent
---

# Test

<core_approach>
Original.
</core_approach>
"""
        result = merge_optimized_sections(
            original,
            {PromptSection.CORE_APPROACH: "New approach content."},
        )

        assert result.success
        assert "New approach content" in result.merged_prompt


class TestConventionsChecker:
    """Tests for ConventionsChecker."""

    def test_assess_structure_with_full_prompt(self) -> None:
        """Test structure assessment with a well-formed prompt."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()

        # Use a more complete prompt that meets all structural requirements
        prompt = """---
name: test-agent
description: A comprehensive test agent for validation
tools: Read, Write, Bash
---

# Test Agent

You are a test agent specializing in testing and validation.

## Core Responsibilities
- Test functionality thoroughly
- Validate behavior against specifications
- Ensure code quality meets standards
- Run regression tests

## Approach
When testing, follow these steps:
1. Analyze the code to understand the changes
2. Design test cases that cover edge cases
3. Execute tests and capture results
4. Report findings with actionable recommendations

## Best Practices
- Always run tests in isolation
- Use meaningful assertions
- Document test expectations

## Constraints
- Do not modify production code
- Never skip validation steps
- Always report failures

## Success Criteria
Your work is successful when:
- All tests pass
- Coverage is adequate
"""
        quality = checker.assess_structure(prompt)

        assert quality.has_frontmatter is True
        assert quality.has_title is True
        assert quality.section_count >= 4

    def test_assess_structure_missing_frontmatter(self) -> None:
        """Test structure assessment when frontmatter is missing."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()
        prompt = """# Test Agent

You are a test agent.

## Core Responsibilities
- Test things
"""
        quality = checker.assess_structure(prompt)

        assert quality.has_frontmatter is False
        assert quality.has_title is True
        assert "Missing YAML frontmatter" in quality.issues

    def test_calculate_quality_score(self) -> None:
        """Test quality score calculation."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()

        # Well-formed prompt should have higher score
        good_prompt = """---
name: test-agent
---

# Test Agent

You are a specialist in testing.

## Core Responsibilities
- Test things

## Constraints
You cannot modify production.

```python
def test():
    pass
```
"""
        # Minimal prompt should have lower score
        minimal_prompt = """Just some instructions."""

        good_score = checker.calculate_quality_score(good_prompt)
        minimal_score = checker.calculate_quality_score(minimal_prompt)

        assert good_score > minimal_score
        assert 0.0 <= good_score <= 1.0
        assert 0.0 <= minimal_score <= 1.0

    def test_get_improvement_suggestions(self) -> None:
        """Test improvement suggestions generation."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()
        prompt = """# Test Agent

Just some basic instructions without much structure.
"""
        suggestions = checker.get_improvement_suggestions(prompt)

        assert len(suggestions) > 0
        assert any("frontmatter" in s.lower() for s in suggestions)

    def test_get_quality_signals(self) -> None:
        """Test quality signals extraction."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()
        prompt = """---
name: test
---

# Test Agent

You are an expert in Python development.

## Approach
When coding, always follow these steps.

## Constraints
You cannot delete files.

```python
def example():
    return "test"
```
"""
        signals = checker.get_quality_signals(prompt)

        assert len(signals) > 0
        signal_names = [s.name for s in signals]
        assert "has_clear_role_definition" in signal_names
        assert "has_structured_sections" in signal_names
        assert "has_constraints_defined" in signal_names

    def test_get_conventions_context(self) -> None:
        """Test conventions context retrieval."""
        from harness.optimization.analysis.conventions import (
            get_conventions_checker,
        )

        checker = get_conventions_checker()
        context = checker.get_conventions_context()

        assert "expected_sections" in context
        assert "structural_requirements" in context
        assert "quality_signals" in context
        assert "token_guidance" in context
        assert len(context["expected_sections"]) > 0


class TestAgenticOptimizerTestIntegration:
    """Tests for agentic optimizer test suite integration."""

    def test_combine_validation_scores_heuristic_pass_tests_pass(self) -> None:
        """Test combining scores when both heuristic and tests pass."""
        from harness.optimization.optimizers.agentic_optimizer import (
            AgenticSectionOptimizer,
            AgenticOptimizationConfig,
        )

        optimizer = AgenticSectionOptimizer()
        config = AgenticOptimizationConfig(test_weight=0.4)

        # Heuristic passes (1.0), tests pass (0.8)
        should_accept, combined = optimizer._combine_validation_scores(
            heuristic_valid=True,
            test_score=0.8,
            config=config,
        )

        # Combined: 0.6 * 1.0 + 0.4 * 0.8 = 0.92
        assert should_accept is True
        assert combined >= 0.9

    def test_combine_validation_scores_heuristic_fail(self) -> None:
        """Test that heuristic failure leads to rejection."""
        from harness.optimization.optimizers.agentic_optimizer import (
            AgenticSectionOptimizer,
            AgenticOptimizationConfig,
        )

        optimizer = AgenticSectionOptimizer()
        config = AgenticOptimizationConfig(test_weight=0.4)

        # Heuristic fails (0.0), tests pass (1.0)
        should_accept, combined = optimizer._combine_validation_scores(
            heuristic_valid=False,
            test_score=1.0,
            config=config,
        )

        # Combined: 0.6 * 0.0 + 0.4 * 1.0 = 0.4 < 0.5
        assert should_accept is False
        assert combined < 0.5

    def test_combine_validation_scores_custom_weight(self) -> None:
        """Test custom test weight configuration."""
        from harness.optimization.optimizers.agentic_optimizer import (
            AgenticSectionOptimizer,
            AgenticOptimizationConfig,
        )

        optimizer = AgenticSectionOptimizer()
        # More weight to tests (50/50 split)
        config = AgenticOptimizationConfig(test_weight=0.5)

        # Heuristic passes, tests pass
        should_accept, combined = optimizer._combine_validation_scores(
            heuristic_valid=True,
            test_score=0.5,
            config=config,
        )

        # Combined: 0.5 * 1.0 + 0.5 * 0.5 = 0.75
        assert should_accept is True
        assert 0.74 <= combined <= 0.76

    def test_config_includes_test_weight(self) -> None:
        """Test that config has test_weight attribute."""
        from harness.optimization.optimizers.agentic_optimizer import (
            AgenticOptimizationConfig,
        )

        # Default config
        config = AgenticOptimizationConfig()
        assert hasattr(config, "test_weight")
        assert config.test_weight == 0.4

        # Custom config
        config2 = AgenticOptimizationConfig(test_weight=0.6)
        assert config2.test_weight == 0.6


class TestCrossSectionRegression:
    """Test cross-section regression detection in orchestrator."""

    def test_section_impact_dataclass(self) -> None:
        """Test SectionImpact dataclass fields."""
        from harness.optimization.orchestrator import SectionImpact
        from harness.optimization.analysis import PromptSection

        impact = SectionImpact(
            source_section=PromptSection.BEST_PRACTICES,
            target_section=PromptSection.CORE_APPROACH,
            score_before=0.9,
            score_after=0.85,
            delta=-0.05,
            is_regression=True,
        )

        assert impact.source_section == PromptSection.BEST_PRACTICES
        assert impact.target_section == PromptSection.CORE_APPROACH
        assert impact.delta == -0.05
        assert impact.is_regression is True

    def test_config_includes_cross_section_check(self) -> None:
        """Test that config has cross_section_check attribute."""
        from harness.optimization.orchestrator import SectionOptimizationConfig
        from pathlib import Path

        config = SectionOptimizationConfig(
            agent_path=Path("test.md"),
            test_suite_path=Path("tests.yaml"),
            criteria_path=Path("criteria.yaml"),
            workspace_dir=Path("workspace"),
        )

        assert hasattr(config, "cross_section_check")
        assert config.cross_section_check is True  # Default enabled
        assert hasattr(config, "regression_threshold")
        assert config.regression_threshold == 0.05

    def test_config_regression_threshold_customizable(self) -> None:
        """Test that regression threshold can be customized."""
        from harness.optimization.orchestrator import SectionOptimizationConfig
        from pathlib import Path

        config = SectionOptimizationConfig(
            agent_path=Path("test.md"),
            test_suite_path=Path("tests.yaml"),
            criteria_path=Path("criteria.yaml"),
            workspace_dir=Path("workspace"),
            cross_section_check=False,
            regression_threshold=0.10,
        )

        assert config.cross_section_check is False
        assert config.regression_threshold == 0.10

    def test_orchestration_result_includes_impact_matrix(self) -> None:
        """Test that OrchestrationResult includes impact matrix."""
        from harness.optimization.orchestrator import (
            OrchestrationResult,
            SectionImpact,
        )
        from harness.optimization.analysis import PromptSection

        impact = SectionImpact(
            source_section=PromptSection.CORE_APPROACH,
            target_section=PromptSection.CONSTRAINTS,
            score_before=0.8,
            score_after=0.7,
            delta=-0.1,
            is_regression=True,
        )

        result = OrchestrationResult(
            success=True,
            agent_name="test-agent",
            section_impact_matrix=[impact],
            regressions_detected=1,
        )

        assert len(result.section_impact_matrix) == 1
        assert result.regressions_detected == 1

        # Test serialization
        result_dict = result.to_dict()
        assert "section_impact_matrix" in result_dict
        assert len(result_dict["section_impact_matrix"]) == 1
        assert result_dict["section_impact_matrix"][0]["source"] == "core_approach"
        assert result_dict["section_impact_matrix"][0]["is_regression"] is True
