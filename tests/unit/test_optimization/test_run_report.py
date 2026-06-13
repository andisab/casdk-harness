"""Unit tests for ``harness.optimization.run_report``.

The renderer is a pure-function view over state files written by the
multi-resource orchestrator.  We exercise it against synthetic fixtures
that mirror the on-disk shapes of ``optimization-state.json``,
``*.summary.json``, and ``execution-eval-round-*.json``.  See
``config/monitoring/CLAUDE.md`` (§ Other operator-facing surfaces) for
the renderer's non-goals + deferred-TODO list.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from harness.optimization import run_report

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _state(
    *,
    current_phase: str = "EXECUTION_EVAL",
    phases_completed: list[str] | None = None,
    resources: dict[str, dict[str, Any]] | None = None,
    feedback_history: list[dict[str, Any]] | None = None,
    phase_timings: dict[str, dict[str, Any]] | None = None,
    started_at: str | None = None,
    updated_at: str | None = None,
    spec_hash: str = "abcdef0123456789",
    eval_suite_path: str = "eval/eval-suite.yaml",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "spec_path": "SPEC.md",
        "spec_type": "plugin",
        "spec_hash": spec_hash,
        "current_phase": current_phase,
        "phases_completed": phases_completed or [],
        "resources": resources or {},
        "research_findings_path": "research/eval_criteria.yaml",
        "user_decisions_path": "sessions/qa-decisions.json",
        "resource_plan_path": "resource-plan.yaml",
        "eval_suite_path": eval_suite_path,
        "eval_results_path": "eval/execution-eval-round-1.json",
        "feedback_history": feedback_history or [],
        "quality_threshold": 0.85,
        "max_iterations": 5,
        "validate_refinement_count": 0,
        "started_at": started_at or (now - timedelta(minutes=42)).isoformat(),
        "updated_at": updated_at or now.isoformat(),
        "phase_timings": phase_timings or {},
    }


def _resource(
    *,
    path: str,
    rtype: str = "skill",
    status: str = "optimized",
    version: int = 1,
    overall: float | None = 0.88,
    error: str = "",
) -> dict[str, Any]:
    return {
        "path": path,
        "resource_type": rtype,
        "status": status,
        "version": version,
        "last_evaluated_version": version,
        "quality": (
            {"completeness": 0.9, "accuracy": 0.87, "clarity": 0.85, "overall": overall}
            if overall is not None
            else None
        ),
        "iterations": 1,
        "refinement_count": 0,
        "depends_on": [],
        "depended_by": [],
        "error": error,
    }


def _make_workspace(
    tmp_path: Path,
    *,
    state: dict[str, Any] | None,
    summaries: dict[str, dict[str, Any]] | None = None,
    eval_rounds: list[dict[str, Any]] | None = None,
) -> Path:
    """Build a fake workspace tree under tmp_path."""
    root = tmp_path / "ws"
    sessions = root / "sessions"
    sessions.mkdir(parents=True)
    if state is not None:
        (sessions / "optimization-state.json").write_text(json.dumps(state))

    for filename, content in (summaries or {}).items():
        target = root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(content))

    if eval_rounds:
        eval_dir = root / "eval"
        eval_dir.mkdir(parents=True, exist_ok=True)
        for i, rnd in enumerate(eval_rounds, start=1):
            (eval_dir / f"execution-eval-round-{i}.json").write_text(
                json.dumps(rnd)
            )
    return root


# ---------------------------------------------------------------------------
# Tests — loaders
# ---------------------------------------------------------------------------


def test_render_empty_state(tmp_path: Path) -> None:
    """Renderer produces a placeholder when no state file exists."""
    root = tmp_path / "ws"
    root.mkdir()
    out = run_report.render(root)
    assert "Run has not started yet" in out
    assert "ws" in out  # workspace name


def test_loaders_tolerate_missing_files(tmp_path: Path) -> None:
    """Each loader returns a sensible empty default for missing files."""
    root = tmp_path / "empty"
    root.mkdir()
    assert run_report.load_optimization_state(root) is None
    assert run_report.load_summaries(root) == {}
    assert run_report.load_eval_rounds(root) == []


def test_load_eval_rounds_reads_verdict_field(tmp_path: Path) -> None:
    """Post-cgf-eval-ab aggregate JSON carries a ``verdict`` field; the
    loader should surface it on EvalRoundEntry."""
    root = _make_workspace(
        tmp_path,
        state=_state(),
        eval_rounds=[
            {
                "feedback_iteration": 1,
                "timestamp": "2026-05-15T00:00:00+00:00",
                "resources": [
                    {
                        "path": "agents/iac.md",
                        "version": 1,
                        "win_rate": 0.0,
                        "baseline_pass_rate": 0.5,
                        "candidate_pass_rate": 0.9,
                        "no_decision_rate": 0.0,
                        "scenarios": 3,
                        "verdict": "reject_cost",
                        "promoted": False,
                    },
                ],
            }
        ],
    )
    rounds = run_report.load_eval_rounds(root)
    assert len(rounds) == 1
    entry = rounds[0].entries[0]
    assert entry.verdict == "reject_cost"
    assert entry.promoted is False


def test_load_eval_rounds_falls_back_to_promoted_for_legacy_files(
    tmp_path: Path,
) -> None:
    """Round files written before cgf-eval-ab don't have ``verdict``.
    Loader synthesizes one from the legacy ``promoted`` boolean so old
    workspaces continue to render."""
    root = _make_workspace(
        tmp_path,
        state=_state(),
        eval_rounds=[
            {
                "feedback_iteration": 1,
                "timestamp": "2026-05-08T00:00:00+00:00",
                "resources": [
                    {
                        "path": "agents/promoted.md",
                        "version": 1,
                        "win_rate": 0.8,
                        "baseline_pass_rate": 0.5,
                        "candidate_pass_rate": 0.9,
                        "no_decision_rate": 0.0,
                        "scenarios": 3,
                        "promoted": True,  # no verdict field
                    },
                    {
                        "path": "agents/refined.md",
                        "version": 1,
                        "win_rate": 0.0,
                        "baseline_pass_rate": 0.7,
                        "candidate_pass_rate": 0.4,
                        "no_decision_rate": 0.0,
                        "scenarios": 3,
                        "promoted": False,  # no verdict field
                    },
                ],
            }
        ],
    )
    rounds = run_report.load_eval_rounds(root)
    assert len(rounds) == 1
    entries = {e.path: e for e in rounds[0].entries}
    assert entries["agents/promoted.md"].verdict == "promote"
    assert entries["agents/refined.md"].verdict == "refine"


def test_load_summaries_with_resource_path_field(tmp_path: Path) -> None:
    """Summary file with explicit resource_path is keyed correctly."""
    root = _make_workspace(
        tmp_path,
        state=_state(),
        summaries={
            "sessions/foo-v1.summary.json": {
                "resource_id": "foo",
                "resource_path": "agents/foo.md",
                "version": 1,
                "timestamp": "2026-05-14",
                "quality": {"overall": 0.9},
                "word_count": 1000,
                "iterations": 2,
                "key_improvements": ["did a thing"],
            }
        },
    )
    summaries = run_report.load_summaries(root)
    assert "agents/foo.md" in summaries
    assert summaries["agents/foo.md"][0].quality_overall == 0.9


def test_load_summaries_infers_path_from_parent_dir(tmp_path: Path) -> None:
    """When resource_path is null, infer from the summary file's parent dir."""
    root = _make_workspace(
        tmp_path,
        state=_state(
            resources={"skills/widget/SKILL.md": _resource(path="skills/widget/SKILL.md")}
        ),
        summaries={
            "skills/widget/sessions/SKILL-v1.summary.json": {
                "resource_id": None,
                "resource_path": None,
                "version": 1,
                "quality": {"overall": 0.85},
            }
        },
    )
    summaries = run_report.load_summaries(
        root, known_resource_paths=["skills/widget/SKILL.md"]
    )
    assert "skills/widget/SKILL.md" in summaries


def test_load_summaries_ambiguous_stem_falls_back(tmp_path: Path) -> None:
    """Two SKILL.md files in different dirs both keyed by parent_dir match."""
    root = _make_workspace(
        tmp_path,
        state=_state(
            resources={
                "skills/a/SKILL.md": _resource(path="skills/a/SKILL.md"),
                "skills/b/SKILL.md": _resource(path="skills/b/SKILL.md"),
            }
        ),
        summaries={
            "skills/a/sessions/SKILL-v1.summary.json": {
                "resource_id": None,
                "resource_path": None,
                "version": 1,
            },
            "skills/b/sessions/SKILL-v1.summary.json": {
                "resource_id": None,
                "resource_path": None,
                "version": 1,
            },
        },
    )
    known = ["skills/a/SKILL.md", "skills/b/SKILL.md"]
    summaries = run_report.load_summaries(root, known_resource_paths=known)
    assert "skills/a/SKILL.md" in summaries
    assert "skills/b/SKILL.md" in summaries


def test_normalize_improvements_handles_mixed_shapes() -> None:
    """Dict and string improvements both render to display strings."""
    raw = [
        "plain string",
        {"title": "T", "detail": "D", "category": "Fix"},
        {"section": "Section 3", "change": "added stuff"},
        {"name": "N", "description": "Desc"},
        {"only-unknown-keys": "ignored"},
    ]
    out = run_report._normalize_improvements(raw)
    assert out[0] == "plain string"
    assert "**[Fix]**" in out[1] and "T — D" in out[1]
    assert "Section 3 — added stuff" in out[2]
    assert "N — Desc" in out[3]
    # Fifth falls back to JSON dump (truncated).
    assert out[4].startswith("{")


# ---------------------------------------------------------------------------
# Tests — renderer sections
# ---------------------------------------------------------------------------


def test_header_status_running(tmp_path: Path) -> None:
    state = _state(current_phase="EXECUTION_EVAL")
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "🟢 Running" in out
    assert "EXECUTION_EVAL" in out


def test_header_status_complete(tmp_path: Path) -> None:
    state = _state(current_phase="COMPLETE")
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "✅ Complete" in out


def test_header_status_paused_on_stale_update(tmp_path: Path) -> None:
    """Update timestamp older than 10 minutes flips status to paused."""
    stale = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    state = _state(
        current_phase="ITERATE",
        started_at=stale,
        updated_at=stale,
    )
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "⏸ Paused" in out


def test_summary_buckets_resources_correctly(tmp_path: Path) -> None:
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(path="a.md"),
            "b.md": _resource(path="b.md", status="failed"),
            "c.md": _resource(path="c.md", status="unwinnable"),
            "d.md": _resource(path="d.md"),
            "e.md": _resource(path="e.md", status="cost_unwinnable"),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "a.md", "version": 1,
                    "win_rate": 0.5, "baseline_pass_rate": 0.5,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True,
                },
            ],
        },
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    assert "✅ Promoted | 1 |" in out
    assert "Unwinnable | 1 |" in out
    assert "Cost-unwinnable | 1 |" in out
    assert "GENERATE failed | 1 |" in out
    assert "⏸ Pending | 1 |" in out


def test_phase_progression_uses_timings_when_present(tmp_path: Path) -> None:
    """When phase_timings populated, table shows durations."""
    started = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    completed = (datetime.now(UTC) - timedelta(minutes=8)).isoformat()
    state = _state(
        current_phase="DESIGN",
        phases_completed=["RESEARCH"],
        phase_timings={
            "RESEARCH": {
                "started_at": started,
                "completed_at": completed,
                "duration_s": 120.0,
            },
        },
    )
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "2m 00s" in out
    # Mermaid gantt should appear when timings exist
    assert "```mermaid" in out
    assert "section Pipeline" in out


def test_phase_progression_legacy_state_uses_phases_completed(tmp_path: Path) -> None:
    """Without phase_timings, falls back to phases_completed for status."""
    state = _state(
        current_phase="COMPLETE",
        phases_completed=[
            "RESEARCH", "DESIGN", "QA", "GENERATE",
            "EVAL_DESIGN", "ITERATE", "EXECUTION_EVAL", "VALIDATE",
        ],
        phase_timings={},
    )
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    # All phases prior to COMPLETE should show ✅
    for phase in ("RESEARCH", "DESIGN", "QA", "GENERATE",
                  "EVAL_DESIGN", "ITERATE", "EXECUTION_EVAL", "VALIDATE"):
        assert f"| {phase} | ✅" in out
    # No mermaid block when no timings
    assert "```mermaid" not in out


def test_per_resource_table_renders_all_resources(tmp_path: Path) -> None:
    state = _state(
        current_phase="COMPLETE",
        resources={
            "skills/a/SKILL.md": _resource(path="skills/a/SKILL.md", rtype="skill"),
            "agents/x.md": _resource(path="agents/x.md", rtype="agent", overall=0.92),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "skills/a/SKILL.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 1.0,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True,
                },
                {
                    "path": "agents/x.md", "version": 1,
                    "win_rate": 0.33, "baseline_pass_rate": 0.0,
                    "candidate_pass_rate": 0.33, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True,
                },
            ],
        },
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # Paths surface in the per-resource summary lines (wrapped in <code>
    # since the merged section uses inline <details> blocks rather than
    # a flat markdown table).
    assert "<code>skills/a/SKILL.md</code>" in out
    assert "<code>agents/x.md</code>" in out
    assert "+0.33" in out
    assert "✅ Promoted r1" in out


def test_per_resource_status_recovered_after_regression(tmp_path: Path) -> None:
    """A resource rejected in round 1 then promoted in round 2 shows 'recovered'."""
    state = _state(
        current_phase="COMPLETE",
        resources={"skills/p.md": _resource(path="skills/p.md", version=2)},
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [{
                "path": "skills/p.md", "version": 1,
                "win_rate": 0.0, "baseline_pass_rate": 1.0,
                "candidate_pass_rate": 0.67, "no_decision_rate": 0.33,
                "scenarios": 3, "promoted": False,
            }],
        },
        {
            "feedback_iteration": 2,
            "resources": [{
                "path": "skills/p.md", "version": 2,
                "win_rate": 0.0, "baseline_pass_rate": 1.0,
                "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                "scenarios": 3, "promoted": True,
            }],
        },
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    assert "Promoted r2 (recovered)" in out


def test_iteration_history_emitted_for_multi_version_resource(tmp_path: Path) -> None:
    """The merged per-resource section emits a <details> block with the
    full version chain for any resource with >1 verdict."""
    state = _state(
        current_phase="COMPLETE",
        resources={"skills/p.md": _resource(path="skills/p.md", version=2)},
    )
    eval_rounds = [
        {"feedback_iteration": 1, "resources": [{
            "path": "skills/p.md", "version": 1,
            "win_rate": 0.0, "baseline_pass_rate": 1.0,
            "candidate_pass_rate": 0.67, "no_decision_rate": 0.33,
            "scenarios": 3, "promoted": False,
        }]},
        {"feedback_iteration": 2, "resources": [{
            "path": "skills/p.md", "version": 2,
            "win_rate": 0.0, "baseline_pass_rate": 1.0,
            "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
            "scenarios": 3, "promoted": True,
        }]},
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # Section title is now just per-resource results.
    assert "## Per-resource results" in out
    assert "## Iteration history" not in out
    # Multi-version resource opens an inline <details> block.
    assert "<details>" in out
    assert "skills/p.md" in out
    # Both versions and gate verdicts visible inside the details block.
    assert "v1" in out and "v2" in out
    assert "❌ Reject" in out and "✅ Promote" in out


def test_open_issues_emits_failed_and_unwinnable(tmp_path: Path) -> None:
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(
                path="a.md", status="failed",
                error="Generation timed out after 900s",
            ),
            "b.md": _resource(path="b.md", status="unwinnable"),
            "c.md": _resource(path="c.md"),  # fine
            "d.md": _resource(path="d.md", status="cost_unwinnable"),
        },
    )
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "GENERATE failed" in out
    assert "Generation timed out after 900s" in out
    assert "Unwinnable" in out
    assert "b.md" in out
    assert "Cost-unwinnable" in out
    assert "d.md" in out


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    state = _state(current_phase="COMPLETE")
    root = _make_workspace(tmp_path, state=state)
    target = run_report.write(root)
    assert target is not None
    assert target.exists()
    assert target.name == "RUN_REPORT.md"
    content = target.read_text()
    assert "# CGF Run Report" in content


def test_write_returns_none_when_no_sessions_dir(tmp_path: Path) -> None:
    """write() declines gracefully when sessions/ doesn't exist."""
    root = tmp_path / "no-sessions"
    root.mkdir()
    target = run_report.write(root)
    assert target is None


def test_artifacts_section_includes_links(tmp_path: Path) -> None:
    state = _state(current_phase="COMPLETE")
    root = _make_workspace(tmp_path, state=state)
    out = run_report.render(root)
    assert "## Artifacts" in out
    assert "eval/eval-suite.yaml" in out
    assert "[`CHANGELOG.md`](../CHANGELOG.md)" in out
    assert "Grafana dashboard" in out


# ---------------------------------------------------------------------------
# I15 — verdict subtype + cost-per-success surfacing in the report
# ---------------------------------------------------------------------------


def test_gate_column_distinguishes_verdict_subtypes(tmp_path: Path) -> None:
    """The Gate column must show distinct labels for reject_cost,
    reject_floor, and refine — collapsing them to a single
    ``❌ Reject`` (pre-I15 behaviour) loses critical diagnostic
    signal.
    """
    state = _state(
        current_phase="COMPLETE",
        resources={
            "skills/a.md": _resource(path="skills/a.md", version=1),
            "skills/b.md": _resource(path="skills/b.md", version=1),
            "skills/c.md": _resource(path="skills/c.md", version=1),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "skills/a.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.67,
                    "candidate_pass_rate": 0.67, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_cost",
                    "baseline_cost_per_success": 0.10,
                    "candidate_cost_per_success": 0.18,
                },
                {
                    "path": "skills/b.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.67,
                    "candidate_pass_rate": 0.33, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_floor",
                    "floor_pass_rate": 0.67,
                },
                {
                    "path": "skills/c.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.67,
                    "candidate_pass_rate": 0.33, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "refine",
                },
            ],
        }
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # Each subtype shows up as its own label — operators can grep for
    # "Reject cost" specifically to find cost-rejected resources.
    assert "Reject cost" in out
    assert "Reject floor" in out
    assert "Refine" in out


def test_per_version_row_renders_cost_per_success_delta(tmp_path: Path) -> None:
    """Each per-version row in the resource details table must surface
    cost-per-success when available, formatted as ``$baseline → $candidate (Δ%)``.
    """
    state = _state(
        current_phase="COMPLETE",
        resources={"skills/p.md": _resource(path="skills/p.md", version=1)},
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "skills/p.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.67,
                    "candidate_pass_rate": 0.67, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_cost",
                    "baseline_cost_per_success": 0.10,
                    "candidate_cost_per_success": 0.16,
                },
                {
                    "path": "skills/p.md", "version": 2,
                    "win_rate": 0.33, "baseline_pass_rate": 0.67,
                    "candidate_pass_rate": 1.00, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True,
                    "verdict": "promote",
                    "baseline_cost_per_success": 0.10,
                    "candidate_cost_per_success": 0.10,
                },
            ],
        }
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # Cost column header exists.
    assert "Cost/success" in out
    # v1 cost row: $0.10 → $0.16 (+60%)
    assert "$0.10" in out and "$0.16" in out
    assert "+60%" in out


def test_summary_breaks_out_rejection_subtypes(tmp_path: Path) -> None:
    """When at least one rejection happened, the Summary table breaks
    out the reject_cost / reject_floor / quality counts as sub-rows so
    operators can spot which gate is firing most often.
    """
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(path="a.md", status="needs_refinement"),
            "b.md": _resource(path="b.md", status="needs_refinement"),
            "c.md": _resource(path="c.md", status="needs_refinement"),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "a.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.7,
                    "candidate_pass_rate": 0.7, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_cost",
                },
                {
                    "path": "b.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.7,
                    "candidate_pass_rate": 0.3, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_floor", "floor_pass_rate": 0.7,
                },
                {
                    "path": "c.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.7,
                    "candidate_pass_rate": 0.3, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "refine",
                },
            ],
        }
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    assert "cost regression | 1 |" in out
    assert "below floor | 1 |" in out
    assert "quality regression | 1 |" in out


def test_summary_surfaces_floor_arm_signal(tmp_path: Path) -> None:
    """When any floor arm ran, the Summary table mentions it; the
    "below floor in N" counter is the safety-net visibility signal."""
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(path="a.md", status="needs_refinement"),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "a.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 0.5,
                    "candidate_pass_rate": 0.3, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False,
                    "verdict": "reject_floor",
                    "floor_pass_rate": 0.5,
                },
            ],
        }
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    assert "Floor arm ran" in out
    assert "below floor in 1" in out


def test_summary_omits_subtype_breakdown_for_clean_run(tmp_path: Path) -> None:
    """When no rejections happened, the subtype rows are suppressed to
    keep the Summary table compact."""
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(path="a.md", version=1),
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "a.md", "version": 1,
                    "win_rate": 0.5, "baseline_pass_rate": 0.5,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True, "verdict": "promote",
                },
            ],
        }
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # No rejections → no breakdown.
    assert "cost regression" not in out
    assert "below floor" not in out
    assert "quality regression" not in out
    # Promoted count still surfaces.
    assert "✅ Promoted | 1 |" in out


def test_summary_refined_counter_tracks_recoveries(tmp_path: Path) -> None:
    """J2: `recovered via feedback` is a sub-count of Promoted —
    counts resources whose latest verdict is `promote` AND had at
    least one prior rejection.  Before the fix this row was always
    0 because the elif chain made `_has_recovered` unreachable for
    promoted resources.
    """
    state = _state(
        current_phase="COMPLETE",
        resources={
            "a.md": _resource(path="a.md", version=1),  # clean promote on r1
            "b.md": _resource(path="b.md", version=2),  # recovered on r2
            "c.md": _resource(path="c.md", version=2),  # still failing on r2
        },
    )
    eval_rounds = [
        {
            "feedback_iteration": 1,
            "resources": [
                {
                    "path": "a.md", "version": 1,
                    "win_rate": 0.5, "baseline_pass_rate": 0.5,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True, "verdict": "promote",
                },
                {
                    "path": "b.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 1.0,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False, "verdict": "reject_cost",
                },
                {
                    "path": "c.md", "version": 1,
                    "win_rate": 0.0, "baseline_pass_rate": 1.0,
                    "candidate_pass_rate": 0.67, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False, "verdict": "refine",
                },
            ],
        },
        {
            "feedback_iteration": 2,
            "resources": [
                {
                    "path": "b.md", "version": 2,
                    "win_rate": 0.0, "baseline_pass_rate": 1.0,
                    "candidate_pass_rate": 1.0, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": True, "verdict": "promote",
                },
                {
                    "path": "c.md", "version": 2,
                    "win_rate": 0.0, "baseline_pass_rate": 1.0,
                    "candidate_pass_rate": 0.67, "no_decision_rate": 0.0,
                    "scenarios": 3, "promoted": False, "verdict": "refine",
                },
            ],
        },
    ]
    root = _make_workspace(tmp_path, state=state, eval_rounds=eval_rounds)
    out = run_report.render(root)
    # a + b both ended in `promote`, so total Promoted = 2.
    assert "✅ Promoted | 2 |" in out
    # Of those, only b had a prior rejection → 1 recovered.
    assert "recovered via feedback | 1 |" in out
    # c is the lone Rejected.
    assert "❌ Rejected | 1 |" in out
