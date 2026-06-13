"""Unit tests for F7 (eval-architect prompt), F8 (promotion gate
fail-OPEN bug), and F9 (validate-loop cap + versioned-path bug).

F7 is a prompt-only change with no unit test surface — the runtime
smoke test in tests/smoke/iac-team is the only meaningful gate.

F8 and F9 are pure logic fixes with clean unit-test surfaces.
"""

from __future__ import annotations

from harness.optimization._orchestrator_phases.validate import (
    _strip_version_suffix,
)

# ---------------------------------------------------------------------------
# F9 — version-suffix stripping
# ---------------------------------------------------------------------------


class TestStripVersionSuffix:
    """The coherence validator emits paths with -v{N} suffixes (the file
    it actually inspected). The orchestrator stores resources by their
    canonical base path. The strip helper bridges the two so refinement
    counts get applied to the right resource."""

    def test_agent_versioned(self) -> None:
        assert (
            _strip_version_suffix("agents/iac-analyzer-v3.md")
            == "agents/iac-analyzer.md"
        )

    def test_skill_versioned(self) -> None:
        assert (
            _strip_version_suffix("skills/aws-cli/SKILL-v2.md")
            == "skills/aws-cli/SKILL.md"
        )

    def test_command_versioned(self) -> None:
        assert (
            _strip_version_suffix("commands/iac-v1.md") == "commands/iac.md"
        )

    def test_no_version_unchanged(self) -> None:
        assert (
            _strip_version_suffix("agents/iac-analyzer.md")
            == "agents/iac-analyzer.md"
        )

    def test_multidigit_version(self) -> None:
        assert (
            _strip_version_suffix("agents/foo-v42.md") == "agents/foo.md"
        )

    def test_dash_v_in_name_not_stripped(self) -> None:
        """`-vsphere` looks like a v-suffix but isn't (no digits after the v)."""
        assert (
            _strip_version_suffix("agents/iac-vsphere.md")
            == "agents/iac-vsphere.md"
        )

    def test_handles_py_extension(self) -> None:
        assert (
            _strip_version_suffix("tools/my-tool-v5.py") == "tools/my-tool.py"
        )


# ---------------------------------------------------------------------------
# F9 — state field round-trip
# ---------------------------------------------------------------------------


class TestValidateRefinementStateField:
    def test_default_is_zero(self) -> None:
        from harness.progress import (
            MultiResourceState,
            OptimizationPhase,
        )

        state = MultiResourceState(
            spec_path="/x/SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.RESEARCH,
        )
        assert state.validate_refinement_count == 0

    def test_roundtrip_through_dict(self) -> None:
        from harness.progress import (
            MultiResourceState,
            OptimizationPhase,
        )

        state = MultiResourceState(
            spec_path="/x/SPEC.md",
            spec_type="PLUGIN",
            spec_hash="abc",
            current_phase=OptimizationPhase.VALIDATE,
            validate_refinement_count=2,
        )
        d = state.to_dict()
        assert d["validate_refinement_count"] == 2
        loaded = MultiResourceState.from_dict(d)
        assert loaded.validate_refinement_count == 2

    def test_loaded_from_old_state_defaults_to_zero(self) -> None:
        """A state file written before F9 has no validate_refinement_count
        key. Loading must not crash and must default to 0."""
        from harness.progress import (
            MultiResourceState,
            OptimizationPhase,
        )

        old_state_dict = {
            "spec_path": "/x/SPEC.md",
            "spec_type": "PLUGIN",
            "spec_hash": "abc",
            "current_phase": "VALIDATE",
            "phases_completed": [],
            "resources": {},
            "feedback_history": [],
            "started_at": "",
            "updated_at": "",
        }
        loaded = MultiResourceState.from_dict(old_state_dict)
        assert loaded.validate_refinement_count == 0
        assert loaded.current_phase == OptimizationPhase.VALIDATE


# ---------------------------------------------------------------------------
# F9 — config knob default
# ---------------------------------------------------------------------------


class TestMaxValidateRefinementsConfig:
    def test_default_is_two(self) -> None:
        from pathlib import Path

        from harness.optimization._orchestrator_helpers import (
            DEFAULT_MAX_VALIDATE_REFINEMENTS,
        )
        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceConfig,
        )

        assert DEFAULT_MAX_VALIDATE_REFINEMENTS == 2
        cfg = MultiResourceConfig(workspace_dir=Path("/tmp"))
        assert cfg.max_validate_refinements == 2

    def test_override(self) -> None:
        from pathlib import Path

        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceConfig,
        )

        cfg = MultiResourceConfig(
            workspace_dir=Path("/tmp"), max_validate_refinements=5
        )
        assert cfg.max_validate_refinements == 5


# ---------------------------------------------------------------------------
# F6 — iterate_timeout default raised to 1200s
# ---------------------------------------------------------------------------


class TestIterateTimeoutDefault:
    def test_default_is_1200s(self) -> None:
        """600s was too tight for ~2000-line SKILLs (15 timeouts in
        run #5b). Bumped to 1200s (20 min) as the new floor."""
        from pathlib import Path

        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceConfig,
        )

        cfg = MultiResourceConfig(workspace_dir=Path("/tmp"))
        assert cfg.iterate_timeout == 1200


# ---------------------------------------------------------------------------
# F8 — EXECUTION_EVAL fail-open regression
# ---------------------------------------------------------------------------
#
# Full integration testing of EXECUTION_EVAL requires mocking
# EvalHarness, _eval_single_resource, and a populated state.  We pin
# the structural invariant here: the gate logic now requires both
# (no regressions AND no harness errors AND at least one promotion)
# to advance to VALIDATE.  Verified by reading the source.

import inspect  # noqa: E402 — imported at point of use; see the invariant note above


class TestExecutionEvalGateLogic:
    def test_gate_requires_promotion(self) -> None:
        """Read the source of run_phase to confirm it checks
        `harness_errors` and `promotions` before advancing to VALIDATE.
        This is a regression-prevention test for F8 — without these
        checks the gate fails OPEN when every resource errors."""
        from harness.optimization._orchestrator_phases import (
            execution_eval as ee,
        )

        source = inspect.getsource(ee._run_phase_body)
        # The forward branch must check harness_errors AND require at
        # least one non-blocking terminal state (promotion or — F21 —
        # unwinnable).  Previously it was `if not regressions:` which
        # fails-open when every resource errored.
        assert "harness_errors" in source, (
            "F8 regression: gate must track harness_errors"
        )
        # F8+F21: the gate-advance condition references both `promotions`
        # and `unwinnable` since either signals "no actionable feedback".
        assert "promotions or unwinnable" in source, (
            "F8/F21 regression: gate forward branch must require at "
            "least one promotion or unwinnable resource before "
            "advancing to VALIDATE"
        )

    def test_abort_on_all_errored(self) -> None:
        """When every iterated resource errored, the run aborts with
        RuntimeError rather than looping back forever."""
        from harness.optimization._orchestrator_phases import (
            execution_eval as ee,
        )

        source = inspect.getsource(ee._run_phase_body)
        assert "ALL resources errored" in source, (
            "F8 regression: missing abort path for all-errored case"
        )
        assert "raise RuntimeError" in source, (
            "F8 regression: all-errored must raise, not silently continue"
        )
