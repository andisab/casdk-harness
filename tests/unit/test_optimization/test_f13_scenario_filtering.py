"""Unit tests for F13 — EvalHarness must filter scenarios to those
targeting the candidate resource.

Pre-F13, every resource ran every scenario in the suite. Architect
designed 3 scenarios per resource × 18 resources = 54, but each
resource then ran all 54 — including the 51 designed for OTHER
resources. The 2-3 scenarios with generic `contains` graders
(e.g. needle: "language") happened to pass for almost every resource,
producing artificial 0.40-vs-0.40 ties everywhere and burying real
signal.

F13 filters scenarios to those whose `target_resource` matches the
candidate (suite-level default applies when scenario doesn't override).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from harness.optimization.eval_harness.models import EvalConfig, EvalSuite
from harness.optimization.eval_harness.runner import (
    _filter_scenarios_for_resource,
    _resource_target_key,
)

# ---------------------------------------------------------------------------
# _resource_target_key — path normalization
# ---------------------------------------------------------------------------


class TestResourceTargetKey:
    """Strip version suffix; return workspace-relative path.

    F16: workspace root is detected via SPEC.md (or .claude-plugin/),
    NOT via sessions/ or eval/.  Those directories appear nested
    inside resource dirs (per-resource progress state) and were the
    source of the F16 bug where target_key returned just the
    filename, breaking the F13 filter.
    """

    def test_skill_with_workspace_marker(self, tmp_path: Path) -> None:
        """SPEC.md at workspace root → correct path resolution."""
        workspace = tmp_path / "iac-team"
        workspace.mkdir(parents=True)
        (workspace / "SPEC.md").write_text("# spec")
        candidate = workspace / "skills" / "aws-cli" / "SKILL-v1.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# candidate")

        assert (
            _resource_target_key(candidate) == "skills/aws-cli/SKILL.md"
        )

    def test_agent_with_workspace_marker(self, tmp_path: Path) -> None:
        workspace = tmp_path / "iac-team"
        workspace.mkdir(parents=True)
        (workspace / "SPEC.md").write_text("# spec")
        candidate = workspace / "agents" / "iac-analyzer-v3.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# x")

        assert (
            _resource_target_key(candidate) == "agents/iac-analyzer.md"
        )

    def test_command_with_workspace_marker(self, tmp_path: Path) -> None:
        workspace = tmp_path / "iac-team"
        workspace.mkdir(parents=True)
        (workspace / "SPEC.md").write_text("# spec")
        candidate = workspace / "commands" / "iac-v1.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# x")

        assert _resource_target_key(candidate) == "commands/iac.md"

    def test_nested_sessions_dirs_ignored(self, tmp_path: Path) -> None:
        """F16 regression: per-resource sessions/ dirs (e.g.
        skills/aws-cli/sessions/) must NOT be mistaken for workspace
        root.  Only SPEC.md (or .claude-plugin/) is a valid marker."""
        workspace = tmp_path / "iac-team"
        workspace.mkdir(parents=True)
        (workspace / "SPEC.md").write_text("# spec")

        # Pollute resource dirs with sessions/ — the pre-F16 layout
        # that broke F13 in run #5h.
        skill_dir = workspace / "skills" / "aws-cli"
        skill_dir.mkdir(parents=True)
        (skill_dir / "sessions").mkdir()  # nested sessions/
        candidate = skill_dir / "SKILL-v1.md"
        candidate.write_text("# x")

        # Must still resolve to the FULL workspace-relative path,
        # not just "SKILL.md".
        assert (
            _resource_target_key(candidate) == "skills/aws-cli/SKILL.md"
        )

    def test_no_version_suffix(self, tmp_path: Path) -> None:
        """Paths without -v{N} pass through unchanged."""
        workspace = tmp_path / "iac-team"
        workspace.mkdir(parents=True)
        (workspace / "SPEC.md").write_text("# spec")
        candidate = workspace / "skills" / "aws-cli" / "SKILL.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# x")

        assert (
            _resource_target_key(candidate) == "skills/aws-cli/SKILL.md"
        )

    def test_claude_plugin_marker(self, tmp_path: Path) -> None:
        """Plugin layouts may use .claude-plugin/ as the workspace marker
        instead of SPEC.md."""
        workspace = tmp_path / "myplugin"
        workspace.mkdir(parents=True)
        (workspace / ".claude-plugin").mkdir()
        candidate = workspace / "agents" / "foo-v1.md"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# x")

        assert _resource_target_key(candidate) == "agents/foo.md"

    def test_fallback_when_no_workspace_marker(self) -> None:
        """When no SPEC.md / .claude-plugin neighbor exists, fall back to
        last 2-3 components (best-effort)."""
        p = Path("/tmp/some-random/skills/aws-cli/SKILL-v1.md")
        assert (
            _resource_target_key(p) == "skills/aws-cli/SKILL.md"
        )


# ---------------------------------------------------------------------------
# _filter_scenarios_for_resource — the F13 contract
# ---------------------------------------------------------------------------


def _make_swg(scenario_id: str, target_resource: str | None) -> Any:
    """Build a minimal ScenarioWithGraders stub."""
    swg = MagicMock()
    swg.scenario.id = scenario_id
    swg.scenario.target_resource = target_resource
    return swg


class TestFilterScenariosForResource:
    """The headline F13 behavior: only scenarios for THIS resource run."""

    def test_filter_keeps_matching_target(self) -> None:
        suite = EvalSuite(
            version="1.0",
            target_resource="skills/repo-analysis/SKILL.md",
            scenarios=[
                _make_swg("s1", "skills/aws-cli/SKILL.md"),
                _make_swg("s2", "skills/aws-eks/SKILL.md"),
                _make_swg("s3", "skills/aws-cli/SKILL.md"),
            ],
            config=EvalConfig(),
        )
        result = _filter_scenarios_for_resource(
            suite, "skills/aws-cli/SKILL.md"
        )
        ids = [s.scenario.id for s in result]
        assert ids == ["s1", "s3"]

    def test_filter_uses_suite_default_when_no_override(self) -> None:
        """Scenarios with target_resource=None inherit the suite-level
        default — F13 must respect that inheritance, not drop them."""
        suite = EvalSuite(
            version="1.0",
            target_resource="skills/aws-cli/SKILL.md",
            scenarios=[
                _make_swg("s1", None),  # inherits suite default
                _make_swg("s2", "skills/aws-eks/SKILL.md"),
                _make_swg("s3", None),  # inherits
            ],
            config=EvalConfig(),
        )
        result = _filter_scenarios_for_resource(
            suite, "skills/aws-cli/SKILL.md"
        )
        ids = [s.scenario.id for s in result]
        assert ids == ["s1", "s3"]

    def test_filter_drops_non_matching(self) -> None:
        """Pre-F13 behavior was to run ALL scenarios. F13 must drop
        non-matching ones — the test of correct attribution."""
        suite = EvalSuite(
            version="1.0",
            target_resource="skills/other/SKILL.md",
            scenarios=[
                _make_swg("only-aws-cli", "skills/aws-cli/SKILL.md"),
                _make_swg("only-aws-eks", "skills/aws-eks/SKILL.md"),
            ],
            config=EvalConfig(),
        )
        result = _filter_scenarios_for_resource(
            suite, "skills/different/SKILL.md"
        )
        assert result == []

    def test_filter_empty_suite(self) -> None:
        suite = EvalSuite(
            version="1.0",
            target_resource="a.md",
            scenarios=[],
            config=EvalConfig(),
        )
        assert _filter_scenarios_for_resource(suite, "a.md") == []


# ---------------------------------------------------------------------------
# Source-inspection: F13 wired into runner.run
# ---------------------------------------------------------------------------


class TestRunWiring:
    def test_run_calls_filter(self) -> None:
        import inspect

        from harness.optimization.eval_harness import runner

        src = inspect.getsource(runner.EvalHarness.run)
        assert "_filter_scenarios_for_resource" in src, (
            "F13 regression: EvalHarness.run lost the filter call"
        )
        assert "_resource_target_key" in src, (
            "F13 regression: EvalHarness.run lost target-key normalization"
        )

    def test_log_includes_target_key(self) -> None:
        """The 'no applicable scenarios' warning is a debugging anchor —
        when filtering trims everything, the log must surface why."""
        import inspect

        from harness.optimization.eval_harness import runner

        src = inspect.getsource(runner.EvalHarness.run)
        assert "no applicable scenarios" in src, (
            "F13 regression: empty-filter case must log the suite_default "
            "and target_key for debugging"
        )
