"""Tests for the EVAL_DESIGN phase delegate (CGF Stage 3 Phase A.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.multi_resource_orchestrator import (
    MultiResourceConfig,
    MultiResourceOrchestrator,
)
from harness.progress import ResourceStatus

# =============================================================================
# Fixtures
# =============================================================================


def _make_orchestrator(
    tmp_path: Path,
    *,
    generated_resources: list[dict[str, Any]] | None = None,
) -> MultiResourceOrchestrator:
    """Build an orchestrator with state pre-populated for EVAL_DESIGN.

    Bypasses _initialize() (which requires SPEC.md on disk) by hand-
    populating ``_state``, ``_spec``, and ``_progress``.
    """
    config = MultiResourceConfig(
        workspace_dir=tmp_path,
        eval_design_timeout=60,
        verbose=False,
        follow_logs=False,
    )
    orch = MultiResourceOrchestrator(config)

    # Mock spec
    spec = MagicMock()
    spec.source_path = "SPEC.md"
    spec.name = "test-plugin"
    orch._spec = spec

    # Mock progress manager
    progress = MagicMock()
    progress.save_optimization_state = MagicMock()
    orch._progress = progress

    # Build state with generated resources
    state = MagicMock()
    state.eval_suite_path = ""
    generated = []
    if generated_resources:
        for entry in generated_resources:
            r = MagicMock(spec=ResourceStatus)
            r.path = entry["path"]
            r.resource_type = entry.get("type", "agent")
            r.status = entry.get("status", "generated")
            r.version = entry.get("version", 0)
            generated.append(r)
    state.get_generated_resources = MagicMock(return_value=generated)
    orch._state = state

    return orch


# =============================================================================
# Tests
# =============================================================================


class TestEvalDesignPhase:
    @pytest.mark.asyncio
    async def test_skips_when_no_generated_resources(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, generated_resources=[])
        with patch(
            "harness.subagent.call_agent_simple"
        ) as mock_call:
            await orch._delegate_eval_design()
        mock_call.assert_not_called()
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_happy_path_signal_and_file(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        # The architect "writes" the suite to disk.
        suite_path = tmp_path / "eval" / "eval-suite.yaml"
        suite_path.parent.mkdir(parents=True, exist_ok=True)
        suite_path.write_text(
            "version: '1.0'\ntarget_resource: agents/iac.md\nscenarios: []\nconfig: {}\n"
        )

        response = (
            "Done.\n"
            "[EVAL_DESIGN_COMPLETE]\n"
            "eval_suite_path: eval/eval-suite.yaml\n"
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value=response),
        ):
            await orch._delegate_eval_design()

        assert orch._state.eval_suite_path == "eval/eval-suite.yaml"

    @pytest.mark.asyncio
    async def test_signal_received_but_no_file(self, tmp_path: Path) -> None:
        """Architect signals success but writes nothing — fail-fast.

        Previously this was tolerated as a soft failure (EXECUTION_EVAL
        would skip). Phase A in practice has the architect describing the
        suite inline instead of using Write, so we surface the deficiency
        loudly rather than letting downstream phases short-circuit.
        """
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        response = "[EVAL_DESIGN_COMPLETE]\n"
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value=response),
        ):
            with pytest.raises(ValueError, match="no eval-suite.yaml on disk"):
                await orch._delegate_eval_design()

        # State should NOT mark suite as written.
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_no_signal_but_file_present(self, tmp_path: Path) -> None:
        # Tolerate sloppy agents that produce the file without the signal.
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        suite_path = tmp_path / "eval" / "eval-suite.yaml"
        suite_path.parent.mkdir(parents=True, exist_ok=True)
        suite_path.write_text(
            "version: '1.0'\ntarget_resource: agents/iac.md\nscenarios: []\nconfig: {}\n"
        )

        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value="No signal here, but I wrote the file."),
        ):
            await orch._delegate_eval_design()

        assert orch._state.eval_suite_path == "eval/eval-suite.yaml"

    @pytest.mark.asyncio
    async def test_no_signal_and_no_file(self, tmp_path: Path) -> None:
        """Neither signal nor file — fail-fast.

        Previously this was a soft-skip. Phase A's smoke-fixture run
        revealed that EXECUTION_EVAL silently skipping makes the whole
        pipeline appear to succeed without producing eval data, so we
        now surface the missing deliverable as a phase failure.
        """
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value="totally unrelated reply"),
        ):
            with pytest.raises(ValueError, match="no completion signal AND no eval-suite.yaml"):
                await orch._delegate_eval_design()

        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_timeout_does_not_raise(self, tmp_path: Path) -> None:
        """Timeout in EVAL_DESIGN shouldn't kill the pipeline — EXECUTION_EVAL
        will simply skip if the suite isn't on disk."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(side_effect=TimeoutError("t")),
        ):
            # Should NOT raise.
            await orch._delegate_eval_design()
        assert orch._state.eval_suite_path == ""

    @pytest.mark.asyncio
    async def test_eval_directory_created(self, tmp_path: Path) -> None:
        """eval/ directory must be created before the architect is called,
        even on the failure path — the architect needs somewhere to Write."""
        orch = _make_orchestrator(
            tmp_path,
            generated_resources=[{"path": "agents/iac.md", "type": "agent"}],
        )
        with patch(
            "harness.subagent.call_agent_simple",
            new=AsyncMock(return_value=""),
        ):
            # Empty response → no signal, no file → fail-fast raises.
            with pytest.raises(ValueError):
                await orch._delegate_eval_design()

        # The phase ensures eval/ exists for the architect to write into,
        # regardless of how the call ended up.
        assert (tmp_path / "eval").is_dir()


class TestEvalDesignDispatcherIntegration:
    """Verify the orchestrator dispatcher routes through EVAL_DESIGN
    between GENERATE and ITERATE."""

    def test_phase_ordering(self) -> None:
        # PHASE_ORDER lives in protocols.state — sanity check it matches.
        from harness.optimization.protocols.state import PHASE_ORDER

        idx = {name: i for i, name in enumerate(PHASE_ORDER)}
        assert idx["GENERATE"] < idx["EVAL_DESIGN"]
        assert idx["EVAL_DESIGN"] < idx["ITERATE"]
        assert idx["ITERATE"] < idx["EXECUTION_EVAL"]
        assert idx["EXECUTION_EVAL"] < idx["VALIDATE"]

    def test_orchestrator_advances_generate_to_eval_design(
        self, tmp_path: Path
    ) -> None:
        # Smoke: the dispatcher in _run_pipeline transitions GENERATE → EVAL_DESIGN.
        # We don't run a full pipeline; just verify the constant strings line up.
        config = MultiResourceConfig(workspace_dir=tmp_path)
        orch = MultiResourceOrchestrator(config)

        # Verify the new mounted method exists.
        assert hasattr(orch, "_delegate_eval_design")
        assert hasattr(orch, "_run_execution_eval")

    def test_orchestrator_has_new_config_fields(self, tmp_path: Path) -> None:
        config = MultiResourceConfig(workspace_dir=tmp_path)
        # New fields exist with sensible defaults.
        assert config.eval_design_timeout > 0
        assert config.execution_eval_timeout > 0
        assert config.eval_promotion_epsilon is None  # opt-in via env / explicit
        assert config.max_feedback_iterations is None
