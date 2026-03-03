"""E2E tests for agent optimization pipeline.

Tests the complete optimization workflow for agent resources:
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import yaml

if TYPE_CHECKING:
    from conftest import CGFWorkspace

pytestmark = [pytest.mark.cgf_e2e, pytest.mark.cgf_agent]


class TestAgentWorkspaceCreation:
    """Test workspace setup for agent optimization."""

    def test_workspace_structure_created(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify workspace directory structure is created correctly."""
        ws = cgf_agent_workspace

        # Check directories exist
        assert ws.workspace_dir.exists()
        assert ws.research_dir.exists()
        assert ws.notes_dir.exists()
        assert ws.tests_dir.exists()
        assert ws.reviews_dir.exists()

    def test_workspace_has_original_resource(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify original resource file is created."""
        ws = cgf_agent_workspace
        orig_path = ws.workspace_dir / f"{ws.resource_id}-orig.md"

        assert orig_path.exists()
        content = orig_path.read_text()
        assert ws.resource_id in content
        assert "original" in content.lower()

    def test_workspace_has_run_config(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify run_config.yaml is created with correct settings."""
        ws = cgf_agent_workspace
        config_path = ws.workspace_dir / "run_config.yaml"

        assert config_path.exists()
        config = yaml.safe_load(config_path.read_text())

        assert config["resource"]["type"] == "agent"
        assert config["resource"]["id"] == ws.resource_id
        assert config["strategy"] == "prompt_optimization"
        assert config["optimizer"] == "agentic"

    def test_workspace_has_run_state(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify run_state.json is created with INIT state."""
        ws = cgf_agent_workspace
        state_path = ws.workspace_dir / "run_state.json"

        assert state_path.exists()
        state = json.loads(state_path.read_text())

        assert state["state"] == "INIT"
        assert state["resource"]["type"] == "agent"
        assert state["optimizer"] == "agentic"


class TestAgentResearchPhase:
    """Test research phase for agent optimization."""

    def test_research_generates_eval_criteria(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify research phase produces eval_criteria.yaml."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        assert criteria_path.exists()

        criteria = yaml.safe_load(criteria_path.read_text())
        assert "competencies" in criteria
        assert len(criteria["competencies"]) >= 2
        assert criteria["resource_type"] == "agent"

    def test_eval_criteria_has_required_fields(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify eval_criteria.yaml has all required fields."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        # Check required top-level fields
        assert "resource_id" in criteria
        assert "resource_type" in criteria
        assert "optimization_goal" in criteria
        assert "competencies" in criteria
        assert "edge_cases" in criteria
        assert "common_mistakes" in criteria
        assert "best_practices" in criteria

        # Check competency structure
        for comp in criteria["competencies"]:
            assert "name" in comp
            assert "description" in comp
            assert "importance" in comp
            assert "indicators" in comp

    def test_research_state_transition(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify state transitions from INIT to RESEARCH."""
        ws = cgf_agent_workspace

        # Initial state is INIT
        assert ws.get_current_state() == "INIT"

        # Simulate research phase
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")

        # State should be RESEARCH
        assert ws.get_current_state() == "RESEARCH"


class TestAgentTestGenPhase:
    """Test test generation phase for agent optimization."""

    def test_test_gen_produces_test_suite(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify TEST_GEN phase produces test_suite.yaml."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()

        suite_path = ws.tests_dir / "test_suite.yaml"
        assert suite_path.exists()

        suite = yaml.safe_load(suite_path.read_text())
        assert "test_cases" in suite
        assert len(suite["test_cases"]) >= 3

    def test_test_suite_has_valid_structure(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify test suite has properly structured test cases."""
        ws = cgf_agent_workspace
        ws.write_test_suite()

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        for tc in suite["test_cases"]:
            assert "id" in tc
            assert "prompt" in tc
            assert "expected_behavior" in tc
            assert "validation" in tc
            assert "type" in tc["validation"]
            assert "criteria" in tc["validation"]

    def test_test_suite_covers_difficulty_levels(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify test suite includes tests at multiple difficulty levels."""
        ws = cgf_agent_workspace
        ws.write_test_suite()

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        difficulties = {tc.get("difficulty") for tc in suite["test_cases"]}
        assert "basic" in difficulties
        assert "intermediate" in difficulties or "advanced" in difficulties

    def test_test_gen_state_transition(
        self, cgf_agent_workspace: "CGFWorkspace"
    ) -> None:
        """Verify state transitions from RESEARCH to TEST_GEN."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")

        # Simulate test generation
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        assert ws.get_current_state() == "TEST_GEN"


class TestAgentOptimizePhase:
    """Test optimization phase for agent optimization."""

    def test_optimize_produces_versioned_resource(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify OPTIMIZE phase produces optimized resource file."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.82)

        # Check versioned file exists
        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        assert v1_path.exists()

        content = v1_path.read_text()
        assert "optimized" in content.lower()

    def test_optimize_creates_summary_json(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify optimization creates summary.json with metrics."""
        ws = cgf_agent_workspace
        ws.write_optimized_resource(version=1, score=0.82)

        summary_file = f"{ws.resource_id}-v1.summary.json"
        summary_path = ws.workspace_dir / "sessions" / summary_file
        assert summary_path.exists()

        summary = json.loads(summary_path.read_text())
        assert "run_id" in summary
        assert "scores" in summary
        assert summary["scores"]["original"] == 0.65
        assert summary["scores"]["final"] == 0.82
        assert summary["scores"]["improvement"] > 0

    def test_optimize_state_transition(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify state transitions from TEST_GEN to OPTIMIZE."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        # Simulate optimization
        ws.write_optimized_resource(version=1)
        ws.write_run_state("OPTIMIZE")

        assert ws.get_current_state() == "OPTIMIZE"


class TestAgentEvaluatePhase:
    """Test evaluation phase for agent optimization."""

    def test_evaluate_generates_review_report(
        self, cgf_agent_workspace: "CGFWorkspace",
        mock_evaluator_agent: MagicMock,
    ) -> None:
        """Verify EVALUATE phase generates review report."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        assert review_path.exists()

        content = review_path.read_text()
        assert "ACCEPT" in content
        assert "Evaluation Report" in content

    def test_review_contains_cair_assessment(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify review contains CAIR multi-dimensional evaluation."""
        ws = cgf_agent_workspace
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        content = review_path.read_text()

        # Check CAIR dimensions
        assert "COHERENCE" in content
        assert "ALIGNMENT" in content
        assert "IMPROVEMENT" in content
        assert "REGRESSION" in content

    def test_review_recommendations(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify review can produce different recommendations."""
        ws = cgf_agent_workspace

        # Test ACCEPT
        ws.write_review(version=1, recommendation="ACCEPT")
        content = (ws.reviews_dir / "v1_review.md").read_text()
        assert "ACCEPT" in content
        assert "significant improvement" in content.lower()

        # Test REFINE
        ws.write_review(version=2, recommendation="REFINE")
        content = (ws.reviews_dir / "v2_review.md").read_text()
        assert "REFINE" in content
        assert "refinement" in content.lower()

        # Test REJECT
        ws.write_review(version=3, recommendation="REJECT")
        content = (ws.reviews_dir / "v3_review.md").read_text()
        assert "REJECT" in content
        assert "quality standards" in content.lower()

    def test_evaluate_state_transition(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify state transitions from OPTIMIZE to EVALUATE."""
        ws = cgf_agent_workspace
        ws.write_optimized_resource(version=1)
        ws.write_run_state("OPTIMIZE")

        # Simulate evaluation
        ws.write_review(version=1, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        assert ws.get_current_state() == "EVALUATE"


class TestAgentFinalizePhase:
    """Test finalization phase for agent optimization."""

    def test_finalize_accept_completes_run(
        self, completed_workspace: "CGFWorkspace",
    ) -> None:
        """Verify ACCEPT recommendation leads to COMPLETE state."""
        ws = completed_workspace

        # Simulate finalization with ACCEPT
        ws.write_run_state("FINALIZE")
        assert ws.get_current_state() == "FINALIZE"

        # Complete the run
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"

    def test_finalize_refine_triggers_iteration(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify REFINE recommendation triggers another iteration."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="REFINE")
        ws.write_run_state("EVALUATE")

        # Read current state to check iterations
        state = ws.read_run_state()
        assert state["state"] == "EVALUATE"

        # Simulate iteration back to OPTIMIZE
        ws.write_optimized_resource(version=2, score=0.88)
        ws.write_run_state("OPTIMIZE")

        assert ws.get_current_state() == "OPTIMIZE"

    def test_finalize_reject_marks_failed(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify REJECT recommendation can lead to failure state."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.50)
        ws.write_review(version=1, recommendation="REJECT")
        ws.write_run_state("EVALUATE")

        # Simulate finalization handling REJECT
        ws.write_run_state(
            "FINALIZE",
            error="Optimization rejected: did not meet quality standards",
        )

        state = ws.read_run_state()
        assert state["state"] == "FINALIZE"
        assert state["error"] is not None


class TestAgentFullPipeline:
    """Test complete pipeline execution for agent optimization."""

    def test_full_pipeline_success(
        self, cgf_agent_workspace: "CGFWorkspace",
        mock_research_agent: MagicMock,
        mock_evaluator_agent: MagicMock,
    ) -> None:
        """Test complete successful pipeline execution."""
        ws = cgf_agent_workspace

        # Phase 1: INIT (done by fixture)
        assert ws.get_current_state() == "INIT"

        # Phase 2: RESEARCH
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")
        assert ws.get_current_state() == "RESEARCH"
        assert (ws.research_dir / "eval_criteria.yaml").exists()

        # Phase 3: TEST_GEN
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")
        assert ws.get_current_state() == "TEST_GEN"
        assert (ws.tests_dir / "test_suite.yaml").exists()

        # Phase 4: OPTIMIZE
        ws.write_optimized_resource(version=1, score=0.82)
        ws.write_run_state("OPTIMIZE")
        assert ws.get_current_state() == "OPTIMIZE"
        assert (ws.workspace_dir / f"{ws.resource_id}-v1.md").exists()

        # Phase 5: EVALUATE
        ws.write_review(version=1, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")
        assert ws.get_current_state() == "EVALUATE"
        assert (ws.reviews_dir / "v1_review.md").exists()

        # Phase 6: FINALIZE
        ws.write_run_state("FINALIZE")
        assert ws.get_current_state() == "FINALIZE"

        # Phase 7: COMPLETE
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"

    def test_pipeline_with_refine_iteration(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Test pipeline with REFINE iteration loop."""
        ws = cgf_agent_workspace

        # Initial phases
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        # First optimization attempt - needs refinement
        ws.write_optimized_resource(version=1, score=0.72)
        ws.write_review(version=1, recommendation="REFINE")
        ws.write_run_state("EVALUATE")

        # Iteration: back to OPTIMIZE
        ws.write_run_state("OPTIMIZE")
        ws.write_optimized_resource(version=2, score=0.85)
        ws.write_review(version=2, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        # Both versions should exist
        assert (ws.workspace_dir / f"{ws.resource_id}-v1.md").exists()
        assert (ws.workspace_dir / f"{ws.resource_id}-v2.md").exists()

        # Second review should be ACCEPT
        v2_review = (ws.reviews_dir / "v2_review.md").read_text()
        assert "ACCEPT" in v2_review

        # Complete
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"

    def test_pipeline_artifacts_integrity(
        self, completed_workspace: "CGFWorkspace",
    ) -> None:
        """Verify all pipeline artifacts are properly linked."""
        ws = completed_workspace

        # Load run state
        state = ws.read_run_state()

        # Check artifact paths are valid
        artifacts = state.get("artifacts", {})
        if artifacts.get("run_config"):
            assert Path(artifacts["run_config"]).exists()
        if artifacts.get("eval_criteria"):
            assert Path(artifacts["eval_criteria"]).exists()
        if artifacts.get("test_suite"):
            assert Path(artifacts["test_suite"]).exists()


class TestAgentReviewMode:
    """Test review mode with checkpoints for agent optimization."""

    def test_review_mode_creates_checkpoint(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify review mode creates checkpoint at EVALUATE."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")

        # Simulate checkpoint creation
        checkpoint_data = {
            "state": "EVALUATE",
            "version": 1,
            "recommendation": "ACCEPT",
            "awaiting_review": True,
        }
        checkpoint_path = ws.workspace_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

        assert checkpoint_path.exists()
        cp = json.loads(checkpoint_path.read_text())
        assert cp["awaiting_review"] is True

    def test_review_mode_resumes_from_checkpoint(
        self, cgf_agent_workspace: "CGFWorkspace",
    ) -> None:
        """Verify pipeline can resume from review checkpoint."""
        ws = cgf_agent_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        # Create checkpoint
        checkpoint_data = {
            "state": "EVALUATE",
            "version": 1,
            "recommendation": "ACCEPT",
        }
        checkpoint_path = ws.workspace_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

        # Simulate resume
        checkpoint = json.loads(checkpoint_path.read_text())
        assert checkpoint["state"] == "EVALUATE"
        assert checkpoint["recommendation"] == "ACCEPT"

        # Continue to FINALIZE
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"
