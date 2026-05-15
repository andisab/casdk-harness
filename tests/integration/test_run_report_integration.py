"""Integration test: run_report regenerates from a real workspace.

Asserts the renderer can consume an authentic ``optimization-state.json``
+ summaries + eval rounds (copied from ``workspace/iac-team/``) and
produce a well-formed RUN_REPORT.md.

This pairs with the focused unit tests in
``tests/unit/test_optimization/test_run_report.py``; here we verify
the renderer against actual on-disk data shapes, not just synthetic
fixtures.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness.optimization import run_report

SOURCE_WORKSPACE = Path("/workspace/iac-team")


@pytest.mark.integration
def test_render_against_real_workspace(tmp_path: Path) -> None:
    """Copy a real workspace into tmp_path and render the report."""
    if not SOURCE_WORKSPACE.exists():
        pytest.skip(
            "iac-team workspace not available; run `make smoke FIXTURE=iac-team`"
            " or copy a finished workspace into /workspace/iac-team first."
        )

    dest = tmp_path / "iac-team"
    shutil.copytree(SOURCE_WORKSPACE, dest, dirs_exist_ok=False)

    target = run_report.write(dest)
    assert target is not None
    assert target.exists()

    content = target.read_text()
    # Header smoke checks
    assert content.startswith("# CGF Run Report")
    assert "iac-team" in content
    # The legacy state has 18 resources, 1 unwinnable, 1 failed.
    assert "Resources planned | 18" in content
    assert "Unwinnable" in content
    # Iteration history must surface pulumi-cdk (the only multi-version).
    assert "skills/pulumi-cdk/SKILL.md" in content
    # Artifacts pointing at the existing files
    assert "eval-suite.yaml" in content
    assert "CHANGELOG.md" in content


@pytest.mark.integration
def test_render_handles_empty_workspace(tmp_path: Path) -> None:
    """Workspace without sessions/ should produce a placeholder, not crash."""
    root = tmp_path / "empty"
    root.mkdir()
    out = run_report.render(root)
    assert "Run has not started yet" in out
