"""Unit tests for F11 — EVAL_DESIGN must run when resources are at
any non-failed status, not just ``generated``.

Before F11, ``eval_design.delegate()`` checked
``self._state.get_generated_resources()`` and silently skipped when
empty.  This broke resume-from-EVAL_DESIGN with already-iterated
resources (status=optimized version=1): the phase would log "Phase
complete" in <1s without writing the eval-suite.yaml, then
EXECUTION_EVAL also skipped with "No eval-suite.yaml in state",
leaving the whole eval half of the pipeline dead.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization._orchestrator_phases import eval_design
from harness.progress import (
    MultiResourceState,
    OptimizationPhase,
    ResourceQuality,
    ResourceStatus,
)


def _make_state_with_optimized_resources() -> MultiResourceState:
    """Build a state where all resources have already been iterated.

    Reproduces the F11 reproducer: after run #5c shipped, we reset
    state to ``current_phase=EVAL_DESIGN`` with resources at
    ``status=optimized``.  Pre-F11 this caused EVAL_DESIGN to silently
    skip; post-F11 it must run."""
    state = MultiResourceState(
        spec_path="/x/SPEC.md",
        spec_type="PLUGIN",
        spec_hash="abc",
        current_phase=OptimizationPhase.EVAL_DESIGN,
    )
    for path in ["skills/a/SKILL.md", "agents/b.md", "commands/c.md"]:
        state.resources[path] = ResourceStatus(
            path=path,
            resource_type="skill" if "skills" in path else (
                "agent" if "agents" in path else "command"
            ),
            status="optimized",
            version=1,
            iterations=1,
            quality=ResourceQuality(
                overall=0.88, completeness=0.88, accuracy=0.88, clarity=0.88
            ),
        )
    return state


class TestEvalDesignSkipCondition:
    """The skip condition is the F11 contract:
    only skip when there are NO non-failed resources."""

    @pytest.mark.asyncio
    async def test_optimized_resources_do_not_cause_skip(
        self, tmp_path: Path
    ) -> None:
        """The F11 regression scenario: resources at status=optimized
        (resume from EVAL_DESIGN with already-iterated work) MUST cause
        EVAL_DESIGN to run, not silently skip."""
        # Build a minimal orchestrator stand-in.
        orch = MagicMock()
        orch._state = _make_state_with_optimized_resources()
        orch._spec = MagicMock(source_path=Path("SPEC.md"), constraints=[])
        orch._spec.name = "test-plugin"
        orch.config = MagicMock(
            workspace_dir=tmp_path,
            eval_design_timeout=600,
            verbose=False,
            follow_logs=False,
        )
        orch._signal_parser = MagicMock(parse=MagicMock(return_value=[]))
        orch._save_state = MagicMock()
        orch._emit_progress = MagicMock()

        # Spec.md needs to exist for the workspace check.
        (tmp_path / "SPEC.md").write_text("# spec")

        # Mock the agent call to return a faux success signal.
        async def fake_call(*args, **kwargs):
            return "[EVAL_DESIGN_COMPLETE]\neval_suite_path: eval/eval-suite.yaml\n"

        # Also make sure the suite file appears on disk (since the
        # phase verifies the file exists after the signal).
        (tmp_path / "eval").mkdir()
        (tmp_path / "eval" / "eval-suite.yaml").write_text("version: '1.0'\n")

        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(side_effect=fake_call),
        ):
            # The signal parser needs to return an EVAL_DESIGN_COMPLETE
            # signal for the phase to mark eval_suite_path.  Build a
            # minimal signal object.
            from harness.optimization.protocols.signals import (
                Signal,
                SignalType,
            )

            orch._signal_parser.parse = MagicMock(
                return_value=[
                    Signal(
                        type=SignalType.EVAL_DESIGN_COMPLETE,
                        metadata={
                            "eval_suite_path": "eval/eval-suite.yaml"
                        },
                    )
                ]
            )

            await eval_design.delegate(orch)

        # F11 invariant: EVAL_DESIGN ran (eval_suite_path was set,
        # which only happens after the agent call succeeded).
        assert orch._state.eval_suite_path == "eval/eval-suite.yaml", (
            f"F11 regression: EVAL_DESIGN should have run on "
            f"optimized resources, eval_suite_path is "
            f"{orch._state.eval_suite_path!r}"
        )

    @pytest.mark.asyncio
    async def test_no_resources_still_skips(self, tmp_path: Path) -> None:
        """The opposite check: an empty resource map (or all failed)
        legitimately skips."""
        state = MultiResourceState(
            spec_path="/x/SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.EVAL_DESIGN,
        )
        # No resources at all.
        orch = MagicMock()
        orch._state = state
        orch._spec = MagicMock(source_path=Path("SPEC.md"))
        orch.config = MagicMock(
            workspace_dir=tmp_path, eval_design_timeout=600
        )
        orch._emit_progress = MagicMock()

        await eval_design.delegate(orch)

        # eval_suite_path should remain empty (skip path).
        assert state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_all_failed_resources_skip(self, tmp_path: Path) -> None:
        """Resources at status=failed are NOT eligible; skip if that's all."""
        state = MultiResourceState(
            spec_path="/x/SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.EVAL_DESIGN,
        )
        state.resources["a.md"] = ResourceStatus(
            path="a.md", resource_type="agent", status="failed", version=0
        )
        orch = MagicMock()
        orch._state = state
        orch._spec = MagicMock(source_path=Path("SPEC.md"))
        orch.config = MagicMock(
            workspace_dir=tmp_path, eval_design_timeout=600
        )
        orch._emit_progress = MagicMock()

        await eval_design.delegate(orch)
        assert state.eval_suite_path == ""
