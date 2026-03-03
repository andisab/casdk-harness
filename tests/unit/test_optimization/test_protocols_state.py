"""Unit tests for the state phase ordering protocol module."""

from __future__ import annotations

from harness.optimization.protocols.state import (
    PHASE_ORDER,
    is_valid_transition,
)


class TestPhaseOrder:
    """Verify the ordering and membership of PHASE_ORDER."""

    def test_design_comes_after_research(self) -> None:
        assert PHASE_ORDER.index("DESIGN") == PHASE_ORDER.index("RESEARCH") + 1

    def test_eval_design_comes_after_generate(self) -> None:
        assert PHASE_ORDER.index("EVAL_DESIGN") == PHASE_ORDER.index("GENERATE") + 1

    def test_execution_eval_comes_after_iterate(self) -> None:
        assert (
            PHASE_ORDER.index("EXECUTION_EVAL") == PHASE_ORDER.index("ITERATE") + 1
        )

    def test_complete_is_last(self) -> None:
        assert PHASE_ORDER[-1] == "COMPLETE"

    def test_phase_order_length(self) -> None:
        assert len(PHASE_ORDER) == 9

    def test_all_phases_present(self) -> None:
        expected = {
            "RESEARCH",
            "DESIGN",
            "QA",
            "GENERATE",
            "EVAL_DESIGN",
            "ITERATE",
            "EXECUTION_EVAL",
            "VALIDATE",
            "COMPLETE",
        }
        assert set(PHASE_ORDER) == expected


class TestIsValidTransition:
    """Verify forward and backward transition rules."""

    def test_forward_research_to_design(self) -> None:
        assert is_valid_transition("RESEARCH", "DESIGN")

    def test_forward_design_to_qa(self) -> None:
        assert is_valid_transition("DESIGN", "QA")

    def test_forward_qa_to_generate(self) -> None:
        assert is_valid_transition("QA", "GENERATE")

    def test_forward_generate_to_eval_design(self) -> None:
        assert is_valid_transition("GENERATE", "EVAL_DESIGN")

    def test_forward_eval_design_to_iterate(self) -> None:
        assert is_valid_transition("EVAL_DESIGN", "ITERATE")

    def test_forward_iterate_to_execution_eval(self) -> None:
        assert is_valid_transition("ITERATE", "EXECUTION_EVAL")

    def test_forward_execution_eval_to_validate(self) -> None:
        assert is_valid_transition("EXECUTION_EVAL", "VALIDATE")

    def test_forward_validate_to_complete(self) -> None:
        assert is_valid_transition("VALIDATE", "COMPLETE")

    def test_invalid_skip_research_to_generate(self) -> None:
        assert not is_valid_transition("RESEARCH", "GENERATE")

    def test_invalid_skip_design_to_iterate(self) -> None:
        assert not is_valid_transition("DESIGN", "ITERATE")

    def test_backward_execution_eval_to_iterate(self) -> None:
        assert is_valid_transition("EXECUTION_EVAL", "ITERATE")

    def test_backward_validate_to_iterate(self) -> None:
        assert is_valid_transition("VALIDATE", "ITERATE")

    def test_invalid_backward_complete_to_research(self) -> None:
        assert not is_valid_transition("COMPLETE", "RESEARCH")

    def test_invalid_same_phase(self) -> None:
        assert not is_valid_transition("RESEARCH", "RESEARCH")

    def test_invalid_unknown_phase(self) -> None:
        assert not is_valid_transition("RESEARCH", "UNKNOWN")

    def test_invalid_from_unknown_phase(self) -> None:
        assert not is_valid_transition("UNKNOWN", "DESIGN")


class TestWorkspaceLayoutImport:
    """Verify workspace module can be imported and instantiated."""

    def test_workspace_layout_import(self) -> None:
        from pathlib import Path

        from harness.optimization.protocols.workspace import WorkspaceLayout

        layout = WorkspaceLayout(root=Path("/tmp/test-workspace"))
        assert layout.spec == Path("/tmp/test-workspace/SPEC.md")

    def test_workspace_layout_research_dir(self) -> None:
        from pathlib import Path

        from harness.optimization.protocols.workspace import WorkspaceLayout

        layout = WorkspaceLayout(root=Path("/tmp/test-workspace"))
        assert layout.research_dir == Path("/tmp/test-workspace/research")

    def test_workspace_layout_sessions_dir(self) -> None:
        from pathlib import Path

        from harness.optimization.protocols.workspace import WorkspaceLayout

        layout = WorkspaceLayout(root=Path("/tmp/test-workspace"))
        assert layout.sessions_dir == Path("/tmp/test-workspace/sessions")
