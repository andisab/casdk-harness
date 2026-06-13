"""E2E tests for skill optimization pipeline.

Tests the complete optimization workflow for skill resources:
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE

Skills focus on trigger optimization for activation patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import yaml

if TYPE_CHECKING:
    from conftest import CGFWorkspace

pytestmark = [pytest.mark.cgf_e2e, pytest.mark.cgf_skill]


class TestSkillWorkspaceCreation:
    """Test workspace setup for skill optimization."""

    def test_workspace_structure_created(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify workspace directory structure for skill resource."""
        ws = cgf_skill_workspace

        assert ws.workspace_dir.exists()
        assert ws.research_dir.exists()
        assert ws.tests_dir.exists()
        assert ws.reviews_dir.exists()

    def test_workspace_identifies_skill_type(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify workspace correctly identifies resource as skill."""
        ws = cgf_skill_workspace

        assert ws.resource_type == "skill"

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["resource"]["type"] == "skill"

    def test_workspace_uses_trigger_strategy(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify skill uses trigger_optimization strategy."""
        ws = cgf_skill_workspace

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["strategy"] == "trigger_optimization"

    def test_workspace_has_run_state(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify run_state.json is created with INIT state."""
        ws = cgf_skill_workspace

        assert ws.get_current_state() == "INIT"
        state = ws.read_run_state()
        assert state["resource"]["type"] == "skill"


class TestSkillResearchPhase:
    """Test research phase for skill optimization."""

    def test_research_generates_eval_criteria(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify research generates eval criteria for skill."""
        ws = cgf_skill_workspace

        # Create skill-specific competencies
        skill_competencies = [
            {
                "name": "Trigger Precision",
                "description": "Activates only on valid triggers",
                "importance": "high",
                "indicators": [
                    "Low false positive rate",
                    "Pattern matching accuracy",
                ],
            },
            {
                "name": "Trigger Recall",
                "description": "Activates on all valid trigger variations",
                "importance": "high",
                "indicators": [
                    "Low false negative rate",
                    "Synonym recognition",
                ],
            },
            {
                "name": "Edge Case Handling",
                "description": "Handles ambiguous triggers correctly",
                "importance": "medium",
                "indicators": ["Partial match handling", "Context awareness"],
            },
        ]
        ws.write_eval_criteria(competencies=skill_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        assert criteria_path.exists()

        criteria = yaml.safe_load(criteria_path.read_text())
        assert "Trigger Precision" in str(criteria["competencies"])
        assert "Trigger Recall" in str(criteria["competencies"])

    def test_skill_criteria_addresses_activation_patterns(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify criteria addresses skill activation patterns."""
        ws = cgf_skill_workspace
        ws.write_eval_criteria()

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        # Should have competencies defined
        assert len(criteria["competencies"]) >= 2
        assert criteria["resource_type"] == "skill"


class TestSkillTestGenPhase:
    """Test test generation phase for skill optimization."""

    def test_test_gen_produces_trigger_tests(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify TEST_GEN produces trigger-focused test cases."""
        ws = cgf_skill_workspace
        ws.write_eval_criteria()

        # Create skill-specific test cases
        skill_tests = [
            {
                "id": "trigger-positive-001",
                "prompt": "/sample",
                "expected_behavior": "Skill activates",
                "validation": {"type": "contains", "criteria": "activated"},
                "tags": ["positive", "command"],
                "difficulty": "basic",
            },
            {
                "id": "trigger-positive-002",
                "prompt": "run sample test",
                "expected_behavior": "Skill activates on phrase",
                "validation": {"type": "contains", "criteria": "activated"},
                "tags": ["positive", "phrase"],
                "difficulty": "basic",
            },
            {
                "id": "trigger-negative-001",
                "prompt": "sample something else",
                "expected_behavior": "Skill does NOT activate",
                "validation": {
                    "type": "not_contains",
                    "criteria": "activated",
                },
                "tags": ["negative", "false-positive"],
                "difficulty": "intermediate",
            },
            {
                "id": "trigger-edge-001",
                "prompt": "run the sample",
                "expected_behavior": "Handle partial match",
                "validation": {"type": "llm_judge", "criteria": "Appropriate"},
                "tags": ["edge", "partial"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=skill_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        # Verify positive/negative test coverage
        tags = []
        for tc in suite["test_cases"]:
            tags.extend(tc.get("tags", []))
        assert "positive" in tags
        assert "negative" in tags

    def test_test_suite_covers_false_positives(
        self, cgf_skill_workspace: CGFWorkspace
    ) -> None:
        """Verify test suite includes false positive scenarios."""
        ws = cgf_skill_workspace

        skill_tests = [
            {
                "id": "fp-001",
                "prompt": "sample data analysis",
                "expected_behavior": "Should NOT activate (false positive)",
                "validation": {
                    "type": "not_contains",
                    "criteria": "activated",
                },
                "tags": ["negative", "false-positive"],
                "difficulty": "intermediate",
            },
        ]
        ws.write_test_suite(test_cases=skill_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        fp_tests = [
            tc for tc in suite["test_cases"]
            if "false-positive" in tc.get("tags", [])
        ]
        assert len(fp_tests) >= 1


class TestSkillOptimizePhase:
    """Test optimization phase for skill optimization."""

    def test_optimize_improves_trigger_patterns(
        self, cgf_skill_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization produces improved skill file."""
        ws = cgf_skill_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        assert v1_path.exists()

        content = v1_path.read_text()
        assert "optimized" in content.lower()

    def test_optimize_preserves_skill_structure(
        self, cgf_skill_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization preserves skill frontmatter structure."""
        ws = cgf_skill_workspace
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        content = v1_path.read_text()

        # Should have frontmatter
        assert content.startswith("---")
        assert "name:" in content
        assert "optimization:" in content


class TestSkillEvaluatePhase:
    """Test evaluation phase for skill optimization."""

    def test_evaluate_generates_skill_review(
        self, cgf_skill_workspace: CGFWorkspace,
    ) -> None:
        """Verify evaluation generates review for skill."""
        ws = cgf_skill_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        assert review_path.exists()

        content = review_path.read_text()
        assert "Evaluation Report" in content
        assert "ACCEPT" in content

    def test_review_addresses_trigger_quality(
        self, cgf_skill_workspace: CGFWorkspace,
    ) -> None:
        """Verify review addresses trigger detection quality."""
        ws = cgf_skill_workspace
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        content = review_path.read_text()

        # Should have CAIR assessment
        assert "COHERENCE" in content
        assert "ALIGNMENT" in content


class TestSkillFullPipeline:
    """Test complete pipeline execution for skill optimization."""

    def test_full_pipeline_success(
        self, cgf_skill_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Test complete successful pipeline for skill."""
        ws = cgf_skill_workspace

        # Phase 1: INIT
        assert ws.get_current_state() == "INIT"
        assert ws.resource_type == "skill"

        # Phase 2: RESEARCH
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")
        assert ws.get_current_state() == "RESEARCH"

        # Phase 3: TEST_GEN
        skill_tests = [
            {
                "id": "trigger-001",
                "prompt": "/sample",
                "expected_behavior": "Skill activates",
                "validation": {"type": "contains", "criteria": "activated"},
                "tags": ["positive"],
                "difficulty": "basic",
            },
            {
                "id": "trigger-002",
                "prompt": "unrelated text",
                "expected_behavior": "Skill does NOT activate",
                "validation": {
                    "type": "not_contains",
                    "criteria": "activated",
                },
                "tags": ["negative"],
                "difficulty": "basic",
            },
        ]
        ws.write_test_suite(test_cases=skill_tests)
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

    def test_pipeline_maintains_trigger_boundaries(
        self, cgf_skill_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimized skill maintains correct trigger boundaries."""
        ws = cgf_skill_workspace

        # Setup phases
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.85)
        ws.write_review(version=1, recommendation="ACCEPT")

        # Verify resource has frontmatter
        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        content = v1_path.read_text()

        # Should have YAML frontmatter with optimization info
        assert "---" in content
        assert "final_score" in content or "optimized" in content.lower()

    def test_pipeline_with_false_positive_refinement(
        self, cgf_skill_workspace: CGFWorkspace,
        mock_optimizer: MagicMock,
    ) -> None:
        """Test pipeline handles refinement for false positive issues."""
        ws = cgf_skill_workspace

        # Initial setup
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        # First attempt - high false positive rate
        ws.write_optimized_resource(version=1, score=0.65)
        ws.write_review(version=1, recommendation="REFINE")
        ws.write_run_state("EVALUATE")

        # Refine iteration
        ws.write_run_state("OPTIMIZE")
        ws.write_optimized_resource(version=2, score=0.88)
        ws.write_review(version=2, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        # Both versions should exist
        assert (ws.workspace_dir / f"{ws.resource_id}-v1.md").exists()
        assert (ws.workspace_dir / f"{ws.resource_id}-v2.md").exists()

        # Complete
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"


class TestSkillStrategyValidation:
    """Test skill-specific optimization strategy validation."""

    def test_skill_strategy_is_trigger_optimization(
        self, cgf_skill_workspace: CGFWorkspace,
    ) -> None:
        """Verify skill uses trigger_optimization strategy."""
        ws = cgf_skill_workspace

        state = ws.read_run_state()
        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())

        assert config["strategy"] == "trigger_optimization"
        assert state["strategy"] == "trigger_optimization"

    def test_skill_research_focuses_on_activation(
        self, cgf_skill_workspace: CGFWorkspace,
    ) -> None:
        """Verify research phase focuses on activation patterns."""
        ws = cgf_skill_workspace

        # Create activation-focused competencies
        activation_competencies = [
            {
                "name": "Activation Accuracy",
                "description": "Correctly identifies activation triggers",
                "importance": "high",
                "indicators": ["Pattern recognition", "Context sensitivity"],
            },
        ]
        ws.write_eval_criteria(competencies=activation_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        assert any(
            "Activation" in c["name"]
            for c in criteria["competencies"]
        )

    def test_skill_tests_cover_boundary_conditions(
        self, cgf_skill_workspace: CGFWorkspace,
    ) -> None:
        """Verify test suite covers trigger boundary conditions."""
        ws = cgf_skill_workspace

        boundary_tests = [
            {
                "id": "boundary-001",
                "prompt": "sample",
                "expected_behavior": "Boundary: single word match",
                "validation": {"type": "llm_judge", "criteria": "Appropriate"},
                "tags": ["boundary"],
                "difficulty": "advanced",
            },
            {
                "id": "boundary-002",
                "prompt": "SAMPLE TEST",
                "expected_behavior": "Boundary: case insensitive",
                "validation": {"type": "contains", "criteria": "activated"},
                "tags": ["boundary", "case"],
                "difficulty": "intermediate",
            },
        ]
        ws.write_test_suite(test_cases=boundary_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        boundary_count = sum(
            1 for tc in suite["test_cases"]
            if "boundary" in tc.get("tags", [])
        )
        assert boundary_count >= 2
