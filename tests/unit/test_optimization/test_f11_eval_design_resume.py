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

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

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
        EVAL_DESIGN to run, not silently skip. Under EVAL_DESIGN v2 the phase
        shards per resource and Python merges the shard suites; the invariant
        is unchanged — a suite must be produced."""
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
        orch._save_state = MagicMock()
        orch._emit_progress = MagicMock()

        (tmp_path / "SPEC.md").write_text("# spec")
        # The sharded delegate reads each resource's generated file to compute
        # the v0→candidate diff, so the files must exist on disk.
        for path in ("skills/a/SKILL.md", "agents/b.md", "commands/c.md"):
            f = tmp_path / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"# {path}\ncandidate content\n")

        async def _writer(agent_name, prompt, **kwargs):
            m = re.search(r"(\S+/eval/shards/\S+\.yaml)", prompt)
            assert m, "shard path missing from prompt"
            shard = Path(m.group(1))
            shard.parent.mkdir(parents=True, exist_ok=True)
            rm = re.search(r"Resource:\s+(\S+)", prompt)
            target = rm.group(1) if rm else "x.md"
            shard.write_text(
                yaml.safe_dump(
                    {
                        "version": "1.0",
                        "target_resource": target,
                        "config": {"trials_per_scenario": 1},
                        "scenarios": [
                            {
                                "id": f"easy-{shard.stem}-01",
                                "level": "unit",
                                "prompt": "p",
                                "graders": [
                                    {"type": "contains", "needle": "x"}
                                ],
                            }
                        ],
                    }
                )
            )
            return "[EVAL_DESIGN_COMPLETE]"

        with patch("harness.subagent.call_agent_simple", new=_writer):
            await eval_design.delegate(orch)

        # F11 invariant: EVAL_DESIGN ran (eval_suite_path set after the merge,
        # which only happens once at least one shard produced scenarios).
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
