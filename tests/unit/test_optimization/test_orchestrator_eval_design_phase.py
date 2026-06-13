"""Tests for the EVAL_DESIGN phase delegate (CGF Stage 3 Phase A.5 +
EVAL_DESIGN v2 sharding, L1.3).

EVAL_DESIGN v2 changed the delegate from one monolithic architect call into
a per-resource sharded fan-out + Python merge:

- the architect is called once per resource, writing a per-resource
  ``eval/shards/{slug}.yaml``;
- Python merges the shard suites into ``eval/eval-suite.yaml`` (stamping each
  scenario's ``target_resource`` from its shard);
- success = at least one shard produced scenarios; ALL shards failing takes the
  loud no-suite error path (raise) so EXECUTION_EVAL never silently skips;
- partial failure (some shards fail) proceeds with the survivors.

Signal parsing was dropped — the file on disk is authoritative.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from harness.optimization._orchestrator_phases.eval_design import _shard_slug
from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import ResourceStatus

# =============================================================================
# Fixtures / helpers
# =============================================================================


def _make_orchestrator(
    tmp_path: Path,
    *,
    generated_resources: list[dict[str, Any]] | None = None,
    write_files: bool = True,
) -> MultiResourceOrchestrator:
    """Build an orchestrator with state pre-populated for EVAL_DESIGN.

    Bypasses _initialize() by hand-populating ``_state``, ``_spec``,
    ``_progress``. When ``write_files`` is set (default), a stub generated file
    is written for each resource so the sharded delegate (which reads the
    generated file to compute the v0→v1 diff) has something to read.
    """
    config = MultiResourceConfig(
        workspace_dir=tmp_path,
        eval_design_timeout=60,
        verbose=False,
        follow_logs=False,
    )
    orch = MultiResourceOrchestrator(config)

    spec = MagicMock()
    spec.source_path = "SPEC.md"
    spec.name = "test-plugin"
    orch._spec = spec

    progress = MagicMock()
    progress.save_optimization_state = MagicMock()
    orch._progress = progress

    state = MagicMock()
    state.eval_suite_path = ""
    generated = []
    resources_dict: dict[str, Any] = {}
    if generated_resources:
        for entry in generated_resources:
            r = MagicMock(spec=ResourceStatus)
            r.path = entry["path"]
            r.resource_type = entry.get("type", "agent")
            r.status = entry.get("status", "generated")
            r.version = entry.get("version", 0)
            generated.append(r)
            resources_dict[r.path] = r
            if write_files:
                gen = tmp_path / r.path
                gen.parent.mkdir(parents=True, exist_ok=True)
                gen.write_text(
                    f"# {r.path}\n\nGenerated candidate content for {r.path}.\n"
                )
    state.get_generated_resources = MagicMock(return_value=generated)
    # F11: eval_design iterates state.resources.values() to find any non-failed
    # resource — the fixture must populate that dict.
    state.resources = resources_dict
    orch._state = state

    return orch


def _shard_body(target: str, scenario_id: str) -> str:
    """A minimal schema-shaped shard suite (one scenario)."""
    return yaml.safe_dump(
        {
            "version": "1.0",
            "target_resource": target,
            "config": {
                "trials_per_scenario": 1,
                "timeout_seconds": 300,
                "held_out_fraction": 0.33,
            },
            "scenarios": [
                {
                    "id": scenario_id,
                    "level": "unit",
                    "prompt": "Do the thing.",
                    "graders": [{"type": "contains", "needle": "kubectl"}],
                    "difficulty": "easy",
                    "held_out": False,
                }
            ],
        },
        sort_keys=False,
    )


def _make_shard_writer(*, return_text: str = "[EVAL_DESIGN_COMPLETE]"):
    """Async stand-in for call_agent_simple that writes a valid shard.

    Parses the shard output path out of the prompt (the delegate embeds it),
    writes a one-scenario suite there, and returns ``return_text``.
    """

    async def _call(agent_name: str, prompt: str, **kwargs: Any) -> str:
        m = re.search(r"(\S+/eval/shards/\S+\.yaml)", prompt)
        assert m, "shard output path not found in prompt"
        shard_path = Path(m.group(1))
        shard_path.parent.mkdir(parents=True, exist_ok=True)
        slug = shard_path.stem
        # Recover the resource path from the prompt's "Resource:" line so the
        # shard's target_resource is realistic (the merge stamps it anyway).
        rm = re.search(r"Resource:\s+(\S+)", prompt)
        target = rm.group(1) if rm else "agents/x.md"
        shard_path.write_text(_shard_body(target, f"easy-{slug}-01"))
        return return_text

    return _call


# =============================================================================
# Tests
# =============================================================================


class TestEvalDesignPhase:
    @pytest.mark.asyncio
    async def test_skips_when_no_resources(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, generated_resources=[])
        with patch("harness.subagent.call_agent_simple") as mock_call:
            await orch._delegate_eval_design()
        mock_call.assert_not_called()
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_happy_path_merges_shard(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=_make_shard_writer(),
        ):
            await orch._delegate_eval_design()

        # The merged suite exists and is recorded in state.
        assert orch._state.eval_suite_path == "eval/eval-suite.yaml"
        suite_path = tmp_path / "eval" / "eval-suite.yaml"
        assert suite_path.exists()
        suite = yaml.safe_load(suite_path.read_text())
        assert len(suite["scenarios"]) == 1
        # Merge stamped the per-scenario target from the shard's resource.
        assert suite["scenarios"][0]["target_resource"] == "agents/iac.md"
        # The shard file itself also landed under eval/shards/.
        assert (
            tmp_path / "eval" / "shards" / f"{_shard_slug('agents/iac.md')}.yaml"
        ).exists()

    @pytest.mark.asyncio
    async def test_no_signal_still_succeeds(self, tmp_path: Path) -> None:
        """Signal text is no longer parsed — a shard file on disk with
        scenarios is authoritative, even with no completion signal."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=_make_shard_writer(return_text="no signal here, but wrote it"),
        ):
            await orch._delegate_eval_design()
        assert orch._state.eval_suite_path == "eval/eval-suite.yaml"

    @pytest.mark.asyncio
    async def test_all_shards_write_nothing_raises(self, tmp_path: Path) -> None:
        """Architect produces no shard file → that shard fails. When ALL
        shards fail, the phase raises (no silent EXECUTION_EVAL skip)."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with (
            patch(
                "harness.subagent.call_agent_simple",
                new=AsyncMock(return_value="[EVAL_DESIGN_COMPLETE]"),  # writes nothing
            ),
            pytest.raises(ValueError, match="shards failed"),
        ):
            await orch._delegate_eval_design()
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_partial_failure_proceeds(self, tmp_path: Path) -> None:
        """One shard succeeds, one fails → the phase proceeds with the
        survivor's scenarios rather than failing the whole run."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[
                {"path": "agents/good.md", "type": "agent"},
                {"path": "agents/bad.md", "type": "agent"},
            ],
        )
        good_slug = _shard_slug("agents/good.md")

        async def _selective(agent_name: str, prompt: str, **kwargs: Any) -> str:
            m = re.search(r"(\S+/eval/shards/\S+\.yaml)", prompt)
            assert m
            shard_path = Path(m.group(1))
            if shard_path.stem == good_slug:
                shard_path.parent.mkdir(parents=True, exist_ok=True)
                shard_path.write_text(
                    _shard_body("agents/good.md", "easy-good-01")
                )
            # the "bad" shard writes nothing
            return "[EVAL_DESIGN_COMPLETE]"

        with patch("harness.subagent.call_agent_simple", new=_selective):
            await orch._delegate_eval_design()

        assert orch._state.eval_suite_path == "eval/eval-suite.yaml"
        suite = yaml.safe_load(
            (tmp_path / "eval" / "eval-suite.yaml").read_text()
        )
        # Only the good resource contributed scenarios.
        targets = {s["target_resource"] for s in suite["scenarios"]}
        assert targets == {"agents/good.md"}

    @pytest.mark.asyncio
    async def test_all_shards_timeout_raises(self, tmp_path: Path) -> None:
        """A shard timing out is a shard failure. With a single resource that
        means all shards failed → raise (no eval suite produced)."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(side_effect=TimeoutError("t")),
        ), pytest.raises(ValueError, match="shards failed"):
            await orch._delegate_eval_design()
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_shard_dir_created(self, tmp_path: Path) -> None:
        """eval/shards/ is created before the architects are called, even on
        the all-failed path — the architects need somewhere to Write."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value=""),
        ), pytest.raises(ValueError):
            await orch._delegate_eval_design()
        assert (tmp_path / "eval" / "shards").is_dir()


class TestEvalDesignDispatcherIntegration:
    """Verify the orchestrator dispatcher routes through EVAL_DESIGN
    between GENERATE and ITERATE."""

    def test_phase_ordering(self) -> None:
        from harness.optimization.protocols.state import PHASE_ORDER

        idx = {name: i for i, name in enumerate(PHASE_ORDER)}
        assert idx["GENERATE"] < idx["EVAL_DESIGN"]
        assert idx["EVAL_DESIGN"] < idx["ITERATE"]
        assert idx["ITERATE"] < idx["EXECUTION_EVAL"]
        assert idx["EXECUTION_EVAL"] < idx["VALIDATE"]

    def test_orchestrator_advances_generate_to_eval_design(
        self, tmp_path: Path
    ) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        orch = MultiResourceOrchestrator(config)
        assert hasattr(orch, "_delegate_eval_design")
        assert hasattr(orch, "_run_execution_eval")

    def test_orchestrator_has_new_config_fields(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        assert config.eval_design_timeout > 0
        assert config.execution_eval_timeout > 0
        assert config.eval_promotion_epsilon is None
        assert config.max_feedback_iterations is None
