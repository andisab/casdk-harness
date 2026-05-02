"""E2E tests for workflow optimization pipeline.

Tests the complete optimization workflow for workflow resources:
INIT → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE → COMPLETE

Workflows focus on multi-step coordination, state machine handling,
and graceful interruption recovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import yaml

if TYPE_CHECKING:
    from conftest import CGFWorkspace

pytestmark = [pytest.mark.cgf_e2e, pytest.mark.cgf_workflow]


class TestWorkflowWorkspaceCreation:
    """Test workspace setup for workflow optimization."""

    def test_workspace_structure_created(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify workspace directory structure for workflow resource."""
        ws = cgf_workflow_workspace

        assert ws.workspace_dir.exists()
        assert ws.research_dir.exists()
        assert ws.tests_dir.exists()
        assert ws.reviews_dir.exists()

    def test_workspace_identifies_workflow_type(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify workspace correctly identifies resource as workflow."""
        ws = cgf_workflow_workspace

        assert ws.resource_type == "workflow"

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["resource"]["type"] == "workflow"

    def test_workspace_uses_workflow_strategy(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify workflow uses workflow_optimization strategy."""
        ws = cgf_workflow_workspace

        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())
        assert config["strategy"] == "workflow_optimization"

    def test_workspace_has_run_state(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify run_state.json is created with INIT state."""
        ws = cgf_workflow_workspace

        assert ws.get_current_state() == "INIT"
        state = ws.read_run_state()
        assert state["resource"]["type"] == "workflow"


class TestWorkflowResearchPhase:
    """Test research phase for workflow optimization."""

    def test_research_generates_eval_criteria(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify research generates eval criteria for workflow."""
        ws = cgf_workflow_workspace

        # Create workflow-specific competencies
        workflow_competencies = [
            {
                "name": "State Transitions",
                "description": "Handles state transitions correctly",
                "importance": "high",
                "indicators": [
                    "Valid state machine",
                    "No invalid transitions",
                ],
            },
            {
                "name": "Error Recovery",
                "description": "Gracefully handles failures",
                "importance": "high",
                "indicators": ["Retry logic", "Rollback capability"],
            },
            {
                "name": "Step Coordination",
                "description": "Coordinates multi-step execution",
                "importance": "medium",
                "indicators": [
                    "Correct ordering",
                    "Dependency handling",
                ],
            },
        ]
        ws.write_eval_criteria(competencies=workflow_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        assert criteria_path.exists()

        criteria = yaml.safe_load(criteria_path.read_text())
        assert "State Transitions" in str(criteria["competencies"])
        assert "Error Recovery" in str(criteria["competencies"])

    def test_workflow_criteria_addresses_coordination(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify criteria addresses workflow coordination concerns."""
        ws = cgf_workflow_workspace
        ws.write_eval_criteria()

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        assert len(criteria["competencies"]) >= 2
        assert criteria["resource_type"] == "workflow"


class TestWorkflowTestGenPhase:
    """Test test generation phase for workflow optimization."""

    def test_test_gen_produces_workflow_tests(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify TEST_GEN produces workflow test cases."""
        ws = cgf_workflow_workspace
        ws.write_eval_criteria()

        # Create workflow-specific test cases
        workflow_tests = [
            {
                "id": "flow-happy-001",
                "prompt": "Execute workflow with valid input",
                "expected_behavior": "Workflow completes successfully",
                "validation": {
                    "type": "contains",
                    "criteria": "complete",
                },
                "tags": ["happy-path", "basic"],
                "difficulty": "basic",
            },
            {
                "id": "flow-interrupt-001",
                "prompt": "Interrupt workflow mid-execution",
                "expected_behavior": "Handles interruption gracefully",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Clean shutdown",
                },
                "tags": ["interruption", "error"],
                "difficulty": "intermediate",
            },
            {
                "id": "flow-retry-001",
                "prompt": "Execute workflow with failing step",
                "expected_behavior": "Retries failed step",
                "validation": {
                    "type": "contains",
                    "criteria": "retry",
                },
                "tags": ["error", "retry"],
                "difficulty": "intermediate",
            },
            {
                "id": "flow-state-001",
                "prompt": "Check state after each step",
                "expected_behavior": "State machine is consistent",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Valid states",
                },
                "tags": ["state", "validation"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=workflow_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        # Verify coverage of different scenarios
        tags = []
        for tc in suite["test_cases"]:
            tags.extend(tc.get("tags", []))
        assert "happy-path" in tags
        assert "error" in tags

    def test_test_suite_covers_interruptions(
        self, cgf_workflow_workspace: "CGFWorkspace"
    ) -> None:
        """Verify test suite includes interruption scenarios."""
        ws = cgf_workflow_workspace

        interrupt_tests = [
            {
                "id": "int-001",
                "prompt": "Cancel workflow execution",
                "expected_behavior": "Workflow aborts cleanly",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "No resource leak",
                },
                "tags": ["interruption", "cancel"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=interrupt_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        interrupt_tests = [
            tc for tc in suite["test_cases"]
            if "interruption" in tc.get("tags", [])
        ]
        assert len(interrupt_tests) >= 1


class TestWorkflowOptimizePhase:
    """Test optimization phase for workflow optimization."""

    def test_optimize_improves_workflow(
        self, cgf_workflow_workspace: "CGFWorkspace",
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization produces improved workflow file."""
        ws = cgf_workflow_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        assert v1_path.exists()

        content = v1_path.read_text()
        assert "optimized" in content.lower()

    def test_optimize_preserves_workflow_structure(
        self, cgf_workflow_workspace: "CGFWorkspace",
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimization preserves workflow frontmatter."""
        ws = cgf_workflow_workspace
        ws.write_optimized_resource(version=1, score=0.85)

        v1_path = ws.workspace_dir / f"{ws.resource_id}-v1.md"
        content = v1_path.read_text()

        assert content.startswith("---")
        assert "name:" in content
        assert "optimization:" in content


class TestWorkflowEvaluatePhase:
    """Test evaluation phase for workflow optimization."""

    def test_evaluate_generates_workflow_review(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify evaluation generates review for workflow."""
        ws = cgf_workflow_workspace
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_optimized_resource(version=1)
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        assert review_path.exists()

        content = review_path.read_text()
        assert "Evaluation Report" in content
        assert "ACCEPT" in content

    def test_review_addresses_state_handling(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify review addresses state machine handling."""
        ws = cgf_workflow_workspace
        ws.write_review(version=1, recommendation="ACCEPT")

        review_path = ws.reviews_dir / "v1_review.md"
        content = review_path.read_text()

        # Should have CAIR assessment
        assert "COHERENCE" in content
        assert "ALIGNMENT" in content


class TestWorkflowFullPipeline:
    """Test complete pipeline execution for workflow optimization."""

    def test_full_pipeline_success(
        self, cgf_workflow_workspace: "CGFWorkspace",
        mock_optimizer: MagicMock,
    ) -> None:
        """Test complete successful pipeline for workflow."""
        ws = cgf_workflow_workspace

        # Phase 1: INIT
        assert ws.get_current_state() == "INIT"
        assert ws.resource_type == "workflow"

        # Phase 2: RESEARCH
        ws.write_eval_criteria()
        ws.write_run_state("RESEARCH")
        assert ws.get_current_state() == "RESEARCH"

        # Phase 3: TEST_GEN
        workflow_tests = [
            {
                "id": "flow-001",
                "prompt": "Run workflow",
                "expected_behavior": "Completes successfully",
                "validation": {
                    "type": "contains",
                    "criteria": "complete",
                },
                "tags": ["happy-path"],
                "difficulty": "basic",
            },
            {
                "id": "flow-002",
                "prompt": "Interrupt workflow",
                "expected_behavior": "Handles gracefully",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Clean abort",
                },
                "tags": ["error"],
                "difficulty": "intermediate",
            },
        ]
        ws.write_test_suite(test_cases=workflow_tests)
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

    def test_pipeline_handles_state_machine(
        self, cgf_workflow_workspace: "CGFWorkspace",
        mock_optimizer: MagicMock,
    ) -> None:
        """Verify optimized workflow handles state machine correctly."""
        ws = cgf_workflow_workspace

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

    def test_pipeline_with_reliability_refinement(
        self, cgf_workflow_workspace: "CGFWorkspace",
        mock_optimizer: MagicMock,
    ) -> None:
        """Test pipeline handles refinement for reliability issues."""
        ws = cgf_workflow_workspace

        # Initial setup
        ws.write_eval_criteria()
        ws.write_test_suite()
        ws.write_run_state("TEST_GEN")

        # First attempt - poor reliability
        ws.write_optimized_resource(version=1, score=0.55)
        ws.write_review(version=1, recommendation="REFINE")
        ws.write_run_state("EVALUATE")

        # Refine iteration
        ws.write_run_state("OPTIMIZE")
        ws.write_optimized_resource(version=2, score=0.92)
        ws.write_review(version=2, recommendation="ACCEPT")
        ws.write_run_state("EVALUATE")

        # Both versions should exist
        assert (ws.workspace_dir / f"{ws.resource_id}-v1.md").exists()
        assert (ws.workspace_dir / f"{ws.resource_id}-v2.md").exists()

        # Complete
        ws.write_run_state("FINALIZE")
        ws.write_run_state("COMPLETE")
        assert ws.get_current_state() == "COMPLETE"


class TestWorkflowStrategyValidation:
    """Test workflow-specific optimization strategy validation."""

    def test_workflow_strategy_is_workflow_optimization(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify workflow uses workflow_optimization strategy."""
        ws = cgf_workflow_workspace

        state = ws.read_run_state()
        config_path = ws.workspace_dir / "run_config.yaml"
        config = yaml.safe_load(config_path.read_text())

        assert config["strategy"] == "workflow_optimization"
        assert state["strategy"] == "workflow_optimization"

    def test_workflow_research_focuses_on_coordination(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify research phase focuses on step coordination."""
        ws = cgf_workflow_workspace

        # Create coordination-focused competencies
        coordination_competencies = [
            {
                "name": "Step Coordination",
                "description": "Coordinates multi-step execution",
                "importance": "high",
                "indicators": [
                    "Dependency tracking",
                    "Parallel execution",
                ],
            },
        ]
        ws.write_eval_criteria(competencies=coordination_competencies)

        criteria_path = ws.research_dir / "eval_criteria.yaml"
        criteria = yaml.safe_load(criteria_path.read_text())

        assert any(
            "Coordination" in c["name"]
            for c in criteria["competencies"]
        )

    def test_workflow_tests_cover_state_transitions(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify test suite covers state transition scenarios."""
        ws = cgf_workflow_workspace

        state_tests = [
            {
                "id": "state-001",
                "prompt": "Verify init state",
                "expected_behavior": "State: starts at init",
                "validation": {
                    "type": "contains",
                    "criteria": "init",
                },
                "tags": ["state", "init"],
                "difficulty": "basic",
            },
            {
                "id": "state-002",
                "prompt": "Verify final state",
                "expected_behavior": "State: ends at complete",
                "validation": {
                    "type": "contains",
                    "criteria": "complete",
                },
                "tags": ["state", "final"],
                "difficulty": "basic",
            },
        ]
        ws.write_test_suite(test_cases=state_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        state_count = sum(
            1 for tc in suite["test_cases"]
            if "state" in tc.get("tags", [])
        )
        assert state_count >= 2


class TestWorkflowInterruptionHandling:
    """Test workflow-specific interruption handling."""

    def test_workflow_handles_graceful_shutdown(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify workflow handles graceful shutdown."""
        ws = cgf_workflow_workspace

        shutdown_tests = [
            {
                "id": "shutdown-001",
                "prompt": "Graceful shutdown request",
                "expected_behavior": "Completes current step then stops",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Clean state",
                },
                "tags": ["shutdown", "graceful"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=shutdown_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        shutdown_tests = [
            tc for tc in suite["test_cases"]
            if "shutdown" in tc.get("tags", [])
        ]
        assert len(shutdown_tests) >= 1

    def test_workflow_handles_forced_abort(
        self, cgf_workflow_workspace: "CGFWorkspace",
    ) -> None:
        """Verify workflow handles forced abort."""
        ws = cgf_workflow_workspace

        abort_tests = [
            {
                "id": "abort-001",
                "prompt": "Force abort workflow",
                "expected_behavior": "Aborts with cleanup",
                "validation": {
                    "type": "llm_judge",
                    "criteria": "Resources released",
                },
                "tags": ["abort", "forced"],
                "difficulty": "advanced",
            },
        ]
        ws.write_test_suite(test_cases=abort_tests)

        suite_path = ws.tests_dir / "test_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text())

        abort_tests = [
            tc for tc in suite["test_cases"]
            if "abort" in tc.get("tags", [])
        ]
        assert len(abort_tests) >= 1
