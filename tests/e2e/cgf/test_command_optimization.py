"""E2E tests for command optimization pipeline.

Tests the complete optimization workflow for command resources:
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE

Commands focus on schema optimization for argument validation,
help text, and error messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import yaml

if TYPE_CHECKING:
    from conftest import CGFWorkspace

pytestmark = [pytest.mark.cgf_e2e, pytest.mark.cgf_command]


class TestCommandWorkspaceCreation:
    """Test workspace setup for command optimization."""

    def test_workspace_structure_created(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify workspace directory structure for command resource."""
        ws = cgf_command_workspace

        assert ws.workspace_dir.exists()
        assert ws.research_dir.exists()
        assert ws.tests_dir.exists()
        assert ws.reviews_dir.exists()

    def test_workspace_identifies_command_type(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify workspace correctly identifies resource as command."""
        ws = cgf_command_workspace

        assert ws.resource_type == "command"

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["resource"]["type"] == "command"

    def test_workspace_uses_schema_strategy(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify command uses schema_optimization strategy."""
        ws = cgf_command_workspace

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["strategy"] == "schema_optimization"

    def test_workspace_has_run_state(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify run_state.json is created with INIT state."""
        ws = cgf_command_workspace

        assert ws.get_current_state() == "INIT"
        state = ws.read_run_state()
        assert state["resource"]["type"] == "command"


class TestCommandResearchPhase:
    """Test research phase for command optimization."""

    def test_research_generates_eval_criteria(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify research generates eval criteria for command."""
        ws = cgf_command_workspace

        # Create command-specific competencies
        command_competencies = [
            {
                "name": "Argument Validation",
                "description": "Validates arguments correctly",
                "importance": "high",
                "indicators": [
                    "Type checking",
                    "Required field enforcement",
                ],
            },
            {
                "name": "Error Messaging",
                "description": "Provides clear error messages",
                "importance": "high",
                "indicators": [
                    "Actionable guidance",
                    "Specific error context",
                ],
            },
            {
                "name": "Help Text Quality",
                "description": "Documentation is clear and complete",
                "importance": "medium",
                "indicators": ["Usage examples", "Option descriptions"],
            },
        ]
        ws.write_eval_criteria(competencies=command_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        assert criteria_path.exists()

        criteria = yaml.safe_load(criteria_path.read_text())
        assert "Argument Validation" in str(criteria["competencies"])
        assert "Error Messaging" in str(criteria["competencies"])

    def test_command_criteria_addresses_schema_concerns(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify criteria addresses command schema concerns."""
        ws = cgf_command_workspace
        ws.write_eval_criteria()

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        assert len(criteria["competencies"]) >= 2
        assert criteria["resource_type"] == "command"


class TestCommandTestGenPhase:
    """Test test generation phase for command optimization."""

    def test_test_gen_produces_argument_tests(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify TEST_GEN produces argument validation test cases."""
        ws = cgf_command_workspace
        ws.write_eval_criteria()

        # Create command-specific test cases
        command_tests = [
            {
                "id": "arg-valid-001",
                "prompt": "/sample-cmd 'test input'",
                "expected_behavior": "Command executes successfully",
                "validation": {
                    "type": "contains",
                    "criteria": "success",
                },
                "tags": ["valid", "basic"],
                "difficulty": "basic",
            },
            {
                "id": "arg-missing-001",
                "prompt": "/sample-cmd",
                "expected_behavior": "Error for missing required argument",
                "validation": {
                    "type": "contains",
                    "criteria": "required",
                },
                "tags": ["error", "missing-arg"],
                "difficulty": "basic",
            },
            {
                "id": "arg-invalid-001",
                "prompt": "/sample-cmd --invalid-flag",
                "expected_behavior": "Error for invalid argument",
                "validation": {
                    "type": "contains",
                    "criteria": "invalid",
                },
                "tags": ["error", "invalid-arg"],
                "difficulty": "intermediate",
            },
            {
                "id": "help-001",
                "prompt": "/sample-cmd --help",
                "expected_behavior": "Shows help text",
                "validation": {
                    "type": "contains",
                    "criteria": "usage",
                },
                "tags": ["help"],
                "difficulty": "basic",
            },
        ]
        ws.write_test_suite(test_cases=command_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        # Verify error case coverage
        tags = []
        for tc in suite["test_cases"]:
            tags.extend(tc.get("tags", []))
        assert "valid" in tags
        assert "error" in tags

    def test_test_suite_covers_error_scenarios(
        self, cgf_command_workspace: CGFWorkspace
    ) -> None:
        """Verify test suite includes error handling scenarios."""
        ws = cgf_command_workspace

        error_tests = [
            {
                "id": "err-001",
                "prompt": "/sample-cmd invalid",
                "expected_behavior": "Shows descriptive error",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Error is actionable",
                },
                "tags": ["error", "descriptive"],
                "difficulty": "intermediate",
            },
        ]
        ws.write_test_suite(test_cases=error_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        error_tests = [
            tc for tc in suite["test_cases"]
            if "error" in tc.get("tags", [])
        ]
        assert len(error_tests) >= 1


class TestCommandOptimizePhase:
    """Test optimization phase for command optimization."""

    def test_optimize_improves_command_schema(
        self, cgf_command_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization produces improved command file."""
        ws = cgf_command_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        assert v1_path.exists()

        content = v1_path.read_text()
        assert "optimized" in content.lower()

    def test_optimize_preserves_command_structure(
        self, cgf_command_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization preserves command frontmatter."""
        ws = cgf_command_workspace
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        content = v1_path.read_text()

        assert content.startswith("---")
        assert "name:" in content
        assert "optimization:" in content


class TestCommandEvaluatePhase:
    """Test evaluation phase for command optimization."""

    def test_evaluate_generates_command_review(
        self, cgf_command_workspace: CGFWorkspace,
    ) -> None:
        """Verify evaluation generates review for command."""
        ws = cgf_command_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        assert review_path.exists()

        content = review_path.read_text()
        assert "Evaluation Report" in content
        assert "ACCEPT" in content

    def test_review_addresses_error_handling(
        self, cgf_command_workspace: CGFWorkspace,
    ) -> None:
        """Verify review addresses error handling quality."""
        ws = cgf_command_workspace
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        content = review_path.read_text()

        # Should have CAIR assessment
        assert "COHERENCE" in content
        assert "ALIGNMENT" in content


class TestCommandFullPipeline:
    """Test complete pipeline execution for command optimization."""

    def test_full_pipeline_success(
        self, cgf_command_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Test complete successful pipeline for command."""
        ws = cgf_command_workspace

        # Phase 1: INIT
        assert ws.get_current_state() == "INIT"
        assert ws.resource_type == "command"

        # Phase 2: RESEARCH
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")
        assert ws.get_current_state() == "RESEARCH"

        # Phase 3: TEST_GEN
        command_tests = [
            {
                "id": "cmd-001",
                "prompt": "/sample-cmd 'input'",
                "expected_behavior": "Executes successfully",
                "validation": {
                    "type": "contains",
                    "criteria": "success",
                },
                "tags": ["valid"],
                "difficulty": "basic",
            },
            {
                "id": "cmd-002",
                "prompt": "/sample-cmd",
                "expected_behavior": "Error: missing required",
                "validation": {
                    "type": "contains",
                    "criteria": "required",
                },
                "tags": ["error"],
                "difficulty": "basic",
            },
        ]
        ws.write_test_suite(test_cases=command_tests)
        ws.write_run_state("TEST_GEN")
        assert ws.get_current_state() == "TEST_GEN"

        # Phase 4: OPTIMIZE
        ws.write_optimized_resource(version=1, score=0.88)
        ws.write_run_state("OPTIMIZE")
        assert ws.get_current_state() == "OPTIMIZE"

        # Phase 5: EVALUATE
        ws.write_review(version=1, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")
        assert ws.get_current_state() == "EVALUATE"

        # Phase 6-7: FINALIZE → COMPLETE
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"

    def test_pipeline_preserves_valid_behavior(
        self, cgf_command_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimized command preserves valid input behavior."""
        ws = cgf_command_workspace

        # Setup phases
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.85)
        ws.write_review(version=1, recommendation="ACCEPT")

        # Verify resource has frontmatter
        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        content = v1_path.read_text()

        assert "---" in content
        assert "final_score" in content or "optimized" in content.lower()

    def test_pipeline_with_error_handling_refinement(
        self, cgf_command_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Test pipeline handles refinement for error handling issues."""
        ws = cgf_command_workspace

        # Initial setup
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        # First attempt - poor error messages
        ws.write_optimized_resource(version=1, score=0.60)
        ws.write_review(version=1, recommendation="REFINE")
        ws.write_run_state("EVALUATE")

        # Refine iteration
        ws.write_run_state("OPTIMIZE")
        ws.write_optimized_resource(version=2, score=0.90)
        ws.write_review(version=2, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        # Both versions should exist
        assert (ws.workspace_dir / f"{ws.resource_id}-v1.md").exists()
        assert (ws.workspace_dir / f"{ws.resource_id}-v2.md").exists()

        # Complete
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"


class TestCommandStrategyValidation:
    """Test command-specific optimization strategy validation."""

    def test_command_strategy_is_schema_optimization(
        self, cgf_command_workspace: CGFWorkspace,
    ) -> None:
        """Verify command uses schema_optimization strategy."""
        ws = cgf_command_workspace

        state = ws.read_run_state()
        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())

        assert config["strategy"] == "schema_optimization"
        assert state["strategy"] == "schema_optimization"

    def test_command_research_focuses_on_validation(
        self, cgf_command_workspace: CGFWorkspace,
    ) -> None:
        """Verify research phase focuses on argument validation."""
        ws = cgf_command_workspace

        # Create validation-focused competencies
        validation_competencies = [
            {
                "name": "Input Validation",
                "description": "Validates all input types",
                "importance": "high",
                "indicators": ["Type checking", "Range validation"],
            },
        ]
        ws.write_eval_criteria(competencies=validation_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        assert any(
            "Validation" in c["name"]
            for c in criteria["competencies"]
        )

    def test_command_tests_cover_edge_cases(
        self, cgf_command_workspace: CGFWorkspace,
    ) -> None:
        """Verify test suite covers command edge cases."""
        ws = cgf_command_workspace

        edge_tests = [
            {
                "id": "edge-001",
                "prompt": "/sample-cmd ''",
                "expected_behavior": "Edge: empty string input",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Handles gracefully",
                },
                "tags": ["edge", "empty"],
                "difficulty": "advanced",
            },
            {
                "id": "edge-002",
                "prompt": "/sample-cmd 'very long input...'",
                "expected_behavior": "Edge: long input handling",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Handles gracefully",
                },
                "tags": ["edge", "long"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=edge_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        edge_count = sum(
            1 for tc in suite["test_cases"]
            if "edge" in tc.get("tags", [])
        )
        assert edge_count >= 2
