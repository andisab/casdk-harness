"""Run-report renderer for the multi-resource CGF pipeline.

Pure-function view over the existing state files written by the
:class:`~harness.optimization.multi_resource_orchestrator.MultiResourceOrchestrator`:

- ``sessions/optimization-state.json`` — run shape, per-resource status,
  feedback_history, phase_timings.
- ``sessions/**/*.summary.json`` — per-resource per-version quality
  summaries (key_improvements, competencies_addressed, word_count).
- ``eval/execution-eval-round-*.json`` — promotion verdicts per round.

The renderer joins these into a human-readable markdown report at
``sessions/RUN_REPORT.md``.  No new persistence; the report is purely
derived.  See ``config/monitoring/CLAUDE.md`` (§ Other operator-facing
surfaces) for the non-goals + deferred-TODO list.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes (mirror the on-disk shape, tolerant of missing fields)
# ---------------------------------------------------------------------------


@dataclass
class PhaseTiming:
    started_at: str | None = None
    completed_at: str | None = None
    duration_s: float | None = None


@dataclass
class VersionSummary:
    """One ``*.summary.json`` file."""

    resource_id: str
    resource_path: str
    version: int
    timestamp: str
    quality_overall: float | None
    word_count: int | None
    iterations: int | None
    key_improvements: list[str] = field(default_factory=list)
    competencies_addressed: list[str] = field(default_factory=list)


@dataclass
class EvalRoundEntry:
    path: str
    version: int
    win_rate: float
    baseline_pass_rate: float
    candidate_pass_rate: float
    no_decision_rate: float
    scenarios: int
    promoted: bool
    # ``verdict`` is the authoritative gate decision (post-cgf-eval-ab).
    # Older round files don't have it; loader falls back to ``promoted``
    # and synthesizes "promote" / "refine" accordingly.  New code should
    # read ``verdict`` for the full distinction.
    verdict: str = "promote"
    # I15: cost-per-success surfaces in per-version rows so the Gate
    # column can label "reject_cost" with concrete numbers.  Both
    # ``None`` when the arm had zero successful trials (auto-pass).
    baseline_cost_per_success: float | None = None
    candidate_cost_per_success: float | None = None
    # Phase A.4.2 floor pass rate — populated only on first-promotion
    # rounds.  Lets the report's summary table show "N candidates
    # below floor" without re-deriving from optimization-state.
    floor_pass_rate: float | None = None


@dataclass
class EvalRound:
    feedback_iteration: int
    timestamp: str
    entries: list[EvalRoundEntry]


# ---------------------------------------------------------------------------
# Loaders (tolerant of missing files; never raise)
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("run_report: skipping unreadable file %s (%s)", path, exc)
        return None


def load_optimization_state(workspace_root: Path) -> dict[str, Any] | None:
    """Load ``sessions/optimization-state.json`` as a dict.

    Returns ``None`` if the file is missing or unreadable — the
    renderer will emit a "no run state yet" placeholder report.
    """
    state_path = workspace_root / "sessions" / "optimization-state.json"
    data = _read_json(state_path)
    return data if isinstance(data, dict) else None


def load_summaries(
    workspace_root: Path,
    known_resource_paths: list[str] | None = None,
) -> dict[str, list[VersionSummary]]:
    """Load every ``*.summary.json`` under the workspace tree.

    Files live at multiple depths: ``sessions/``, ``agents/sessions/``,
    ``commands/sessions/``, ``skills/{name}/sessions/``.  We glob
    recursively under ``**/sessions/`` to catch all of them.

    Many older summary files have ``resource_id`` and ``resource_path``
    as ``null``.  When ``known_resource_paths`` is supplied (typically
    from ``state["resources"].keys()``), we match the summary file's
    on-disk location against the known paths to recover the binding.

    Returns a dict mapping resource path → list of versions, sorted by
    version ascending.
    """
    summaries: dict[str, list[VersionSummary]] = {}
    known = known_resource_paths or []

    for path in workspace_root.glob("**/sessions/*.summary.json"):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue

        resource_path = (data.get("resource_path") or "").strip()
        resource_id = (data.get("resource_id") or "").strip()

        if not resource_path:
            resource_path = _infer_resource_path(path, workspace_root, known)
        if not resource_id:
            # Best-effort: strip "-v{N}.summary" from filename stem.
            resource_id = _infer_resource_id(path) or path.stem

        try:
            summary = VersionSummary(
                resource_id=resource_id,
                resource_path=resource_path,
                version=int(data.get("version", 0)),
                timestamp=data.get("timestamp", ""),
                quality_overall=_safe_float(
                    (data.get("quality") or {}).get("overall")
                ),
                word_count=_extract_word_count(data.get("word_count")),
                iterations=_extract_iterations(data),
                key_improvements=_normalize_improvements(
                    data.get("key_improvements", [])
                ),
                competencies_addressed=list(
                    data.get("competencies_addressed", []) or []
                ),
            )
        except (TypeError, ValueError) as exc:
            logger.debug("run_report: skipping malformed summary %s (%s)", path, exc)
            continue

        key = summary.resource_path or summary.resource_id
        if not key:
            continue
        summaries.setdefault(key, []).append(summary)

    for entries in summaries.values():
        entries.sort(key=lambda s: s.version)
    return summaries


def _infer_resource_path(
    summary_file: Path, workspace_root: Path, known_paths: list[str]
) -> str:
    """Infer a resource path from a summary file's location.

    Strategy:
    1. The summary lives at ``{workspace}/{parent_dir}/sessions/{stem}-v{N}.summary.json``.
       For a "deep" path like ``skills/github-actions/sessions/...``, the
       parent dir (``skills/github-actions/``) usually contains exactly one
       known resource — match against it.
    2. For top-level ``sessions/iac-generator-v1.summary.json``, the
       filename stem (``iac-generator``) usually matches one known
       resource's filename.
    Returns an empty string if no unambiguous match is found.
    """
    try:
        rel = summary_file.relative_to(workspace_root)
    except ValueError:
        return ""
    if not rel.parts or rel.parts[-2] != "sessions":
        return ""

    parent_dir = "/".join(rel.parts[:-2])  # everything before /sessions/
    stem_no_version = _infer_resource_id(summary_file) or ""

    # 1. Strongest signal: parent_dir of the summary file matches the
    #    parent_dir of a known resource path.  Unambiguous for nested
    #    paths like ``skills/github-actions/sessions/...`` →
    #    ``skills/github-actions/SKILL.md``.
    if parent_dir:
        parent_candidates = [
            kp for kp in known_paths
            if "/".join(Path(kp).parts[:-1]) == parent_dir
        ]
        if len(parent_candidates) == 1:
            return parent_candidates[0]
        if len(parent_candidates) > 1:
            # Multiple resources share this parent dir — try filename match.
            stem_filtered = [
                kp for kp in parent_candidates
                if Path(kp).stem == stem_no_version
            ]
            if len(stem_filtered) == 1:
                return stem_filtered[0]
        # parent_dir empty list → fall through to stem-only matching for
        # the top-level ``sessions/`` case.

    # 2. Fallback: stem match (only when parent_dir didn't already
    #    produce candidates).  Useful for top-level ``sessions/`` files
    #    where ``parent_dir == ""``.
    if not parent_dir and stem_no_version:
        stem_candidates = [
            kp for kp in known_paths if Path(kp).stem == stem_no_version
        ]
        if len(stem_candidates) == 1:
            return stem_candidates[0]

    return ""


_VERSION_SUFFIX_RE = re.compile(r"-v\d+$")


def _infer_resource_id(summary_file: Path) -> str:
    """Strip ``-v{N}.summary`` from the filename stem."""
    name = summary_file.name
    # Strip ``.summary.json`` then ``-v{N}``.
    stem = (
        name[: -len(".summary.json")]
        if name.endswith(".summary.json")
        else summary_file.stem
    )
    return _VERSION_SUFFIX_RE.sub("", stem)


def _normalize_improvements(raw: Any) -> list[str]:
    """Coerce ``key_improvements`` entries to display strings.

    Different runs / agents serialize improvements in different shapes:
    plain strings, ``{title, detail, category}``, ``{section, change,
    rationale}``, etc.  We try common key sets in priority order before
    falling back to a compact JSON dump.
    """
    # Each tuple is (head_key, body_key, optional_prefix_key).
    SHAPES: list[tuple[str, str, str | None]] = [
        ("title", "detail", "category"),
        ("name", "description", "category"),
        ("section", "change", None),
        ("change", "rationale", "section"),
        ("summary", "detail", None),
    ]

    out: list[str] = []
    for item in raw or []:
        if isinstance(item, str):
            out.append(item)
            continue
        if not isinstance(item, dict):
            out.append(str(item))
            continue

        rendered: str | None = None
        for head_key, body_key, prefix_key in SHAPES:
            head = item.get(head_key)
            body = item.get(body_key)
            if not (head and body):
                continue
            prefix_val = item.get(prefix_key) if prefix_key else None
            prefix = f"**[{prefix_val}]** " if prefix_val else ""
            rendered = f"{prefix}{head} — {body}"
            break

        if rendered is None:
            # Try one-field forms.
            for k in ("title", "name", "section", "change", "summary"):
                v = item.get(k)
                if v:
                    rendered = str(v)
                    break

        if rendered is None:
            rendered = json.dumps(item)[:200]
        out.append(rendered)
    return out


def load_eval_rounds(workspace_root: Path) -> list[EvalRound]:
    """Load every ``eval/execution-eval-round-N.json``, sorted by round."""
    rounds: list[EvalRound] = []
    eval_dir = workspace_root / "eval"
    if not eval_dir.exists():
        return rounds
    for path in sorted(eval_dir.glob("execution-eval-round-*.json")):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        entries: list[EvalRoundEntry] = []
        for raw in data.get("resources", []) or []:
            try:
                promoted = bool(raw.get("promoted", False))
                # Prefer the new ``verdict`` field; fall back to
                # synthesizing one from the legacy boolean.  Old aggregate
                # files predating cgf-eval-ab only carry ``promoted``,
                # which conflated quality regressions with cost rejections —
                # we can't recover the lost distinction, so the fallback
                # is just promote-vs-refine.
                verdict_raw = raw.get("verdict")
                if isinstance(verdict_raw, str) and verdict_raw:
                    verdict = verdict_raw
                else:
                    verdict = "promote" if promoted else "refine"
                # I15: pull cost-per-success + floor.  Defensive nulls;
                # legacy aggregate files predating cgf-eval-ab 4.3 don't
                # carry these fields, so renderer must degrade gracefully.
                def _opt_float(v: Any) -> float | None:
                    if v is None:
                        return None
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None

                entries.append(
                    EvalRoundEntry(
                        path=raw.get("path", ""),
                        version=int(raw.get("version", 0)),
                        win_rate=float(raw.get("win_rate", 0.0)),
                        baseline_pass_rate=float(
                            raw.get("baseline_pass_rate", 0.0)
                        ),
                        candidate_pass_rate=float(
                            raw.get("candidate_pass_rate", 0.0)
                        ),
                        no_decision_rate=float(raw.get("no_decision_rate", 0.0)),
                        scenarios=int(raw.get("scenarios", 0)),
                        promoted=promoted,
                        verdict=verdict,
                        baseline_cost_per_success=_opt_float(
                            raw.get("baseline_cost_per_success")
                        ),
                        candidate_cost_per_success=_opt_float(
                            raw.get("candidate_cost_per_success")
                        ),
                        floor_pass_rate=_opt_float(raw.get("floor_pass_rate")),
                    )
                )
            except (TypeError, ValueError):
                continue
        rounds.append(
            EvalRound(
                feedback_iteration=int(data.get("feedback_iteration", 0)),
                timestamp=data.get("timestamp", ""),
                entries=entries,
            )
        )
    rounds.sort(key=lambda r: r.feedback_iteration)
    return rounds


# ---------------------------------------------------------------------------
# Renderer (pure)
# ---------------------------------------------------------------------------


_STATUS_BADGE = {
    "running": "🟢 Running",
    "complete": "✅ Complete",
    "failed": "❌ Failed",
    "paused": "⏸ Paused",
}

# Canonical phase order — kept in sync with
# ``harness.optimization.protocols.state.PHASE_ORDER`` but duplicated here
# to keep the renderer free of orchestrator imports.
_PHASE_ORDER: tuple[str, ...] = (
    "RESEARCH",
    "DESIGN",
    "QA",
    "GENERATE",
    "EVAL_DESIGN",
    "ITERATE",
    "EXECUTION_EVAL",
    "VALIDATE",
    "COMPLETE",
)


# I15 — verdict + cost rendering helpers.

# Verdict → Gate column label.  Pre-cgf-eval-ab aggregate files only
# carry promote/refine; new files distinguish reject_floor / reject_cost.
# Operators read this column for at-a-glance triage so labels stay
# under ~16 chars to keep table cells tight.
_GATE_LABEL: dict[str, str] = {
    "promote": "✅ Promote",
    "refine": "❌ Refine",
    "reject_cost": "❌ Reject cost",
    "reject_floor": "❌ Reject floor",
    "unwinnable": "⚠️ Unwinnable",
}


def _gate_label(verdict: str) -> str:
    """Map a gate verdict to its Gate-column markdown label.

    Unknown verdicts fall back to a literal echo so a future verdict
    addition surfaces in the report rather than silently displaying
    a generic ❌ Reject.
    """
    return _GATE_LABEL.get(verdict, f"❌ {verdict}")


def _cps_label(entry: EvalRoundEntry) -> str:
    """Render baseline / candidate cost-per-success as a column cell.

    Returns ``"—"`` when either side is unavailable.  Format:
    ``$0.12 → $0.18 (+50%)`` so the delta is the most-glanceable token.
    """
    b = entry.baseline_cost_per_success
    c = entry.candidate_cost_per_success
    if b is None or c is None:
        return "—"
    if b > 0:
        delta_pct = (c - b) / b
        return f"${b:.2f} → ${c:.2f} ({delta_pct:+.0%})"
    # b == 0: candidate vs zero-cost baseline — render without delta.
    return f"${b:.2f} → ${c:.2f}"


def render(workspace_root: Path) -> str:
    """Render the run-report markdown string.

    Reads every state source under ``workspace_root`` and returns the
    fully-rendered markdown.  No file writes; pair with :func:`write` to
    persist.
    """
    state = load_optimization_state(workspace_root)
    if state is None:
        return _render_empty(workspace_root)

    known_paths = list((state.get("resources") or {}).keys())
    summaries = load_summaries(workspace_root, known_resource_paths=known_paths)
    eval_rounds = load_eval_rounds(workspace_root)

    parts = [
        _render_header(workspace_root, state),
        _render_summary(state, eval_rounds),
        _render_phase_progression(state),
        _render_per_resource(state, summaries, eval_rounds),
        _render_open_issues(state, eval_rounds),
        _render_artifacts(workspace_root, state),
    ]
    return "\n\n".join(p for p in parts if p) + "\n"


def write(workspace_root: Path) -> Path | None:
    """Render and atomically write ``sessions/RUN_REPORT.md``.

    Returns the written path on success, ``None`` if the
    ``sessions/`` directory doesn't yet exist (orchestrator hasn't
    written initial state).  Never raises.
    """
    sessions_dir = workspace_root / "sessions"
    if not sessions_dir.exists():
        return None
    target = sessions_dir / "RUN_REPORT.md"
    try:
        content = render(workspace_root)
        _atomic_write(target, content)
        return target
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("run_report: failed to write %s (%s)", target, exc)
        return None


# ---------------------------------------------------------------------------
# Renderer internals
# ---------------------------------------------------------------------------


def _render_empty(workspace_root: Path) -> str:
    """Emitted when no optimization-state.json exists yet."""
    return (
        f"# CGF Run Report — {workspace_root.name}\n\n"
        "_Run has not started yet — no `sessions/optimization-state.json` found._\n"
    )


def _render_header(workspace_root: Path, state: dict[str, Any]) -> str:
    current_phase = state.get("current_phase", "?")
    started_at = state.get("started_at", "")
    updated_at = state.get("updated_at", "")
    spec_path = state.get("spec_path", str(workspace_root / "SPEC.md"))
    spec_hash = state.get("spec_hash", "")

    status_key = _classify_run_status(state)
    badge = _STATUS_BADGE.get(status_key, "🟢 Running")
    phase_display = current_phase if status_key == "running" else current_phase

    wall_time = _format_wall_time(started_at, updated_at)
    spec_hash_display = f"sha256: `{spec_hash[:12]}…`" if spec_hash else "_(no hash)_"

    lines = [
        f"# CGF Run Report — {workspace_root.name}",
        "",
        f"**Status:** {badge} · **Phase:** `{phase_display}`",
        f"**Spec:** `{_relative_to(spec_path, workspace_root)}` ({spec_hash_display})",
        f"**Started:** {_fmt_ts(started_at)} · **Last update:** {_fmt_ts(updated_at)}",
        f"**Wall time:** {wall_time} · "
        f"**Grafana:** [casdk-cgf dashboard](http://localhost:3000/d/casdk-cgf)",
    ]
    return "\n".join(lines)


def _render_summary(state: dict[str, Any], eval_rounds: list[EvalRound]) -> str:
    resources = state.get("resources", {}) or {}
    n_total = len(resources)

    # Bucket counts by status + latest eval verdict.
    promoted = 0
    refined = 0
    rejected = 0
    # I15: split rejected into sub-buckets so operators see whether the
    # cost gate vs floor gate vs quality stage is the dominant rejection
    # mode.  Sum still equals ``rejected`` (the old aggregate stays
    # accurate for legacy readers).
    rejected_cost = 0
    rejected_floor = 0
    rejected_quality = 0
    unwinnable = 0
    generate_failed = 0
    pending = 0
    # I15: count of first-promotion rounds that actually ran the floor
    # arm.  Surfaces "the floor mechanism is engaged" without forcing
    # operators to grep optimization-state for last_promoted_version.
    floor_ran = 0
    floor_below = 0

    latest_verdict = _latest_verdict_by_path(eval_rounds)
    for path, res in resources.items():
        status = (res.get("status") or "").lower()
        if status == "failed":
            generate_failed += 1
        elif status == "unwinnable":
            unwinnable += 1
        else:
            verdict = latest_verdict.get(path)
            if verdict is None:
                pending += 1
            elif verdict.promoted:
                promoted += 1
                # J2: "refined" is a sub-count of promoted — resources
                # that cleared the gate after at least one prior
                # rejection.  Previous `elif` chain made this
                # unreachable because every recovered resource has
                # verdict.promoted=True on its final round.
                if _has_recovered(path, eval_rounds):
                    refined += 1
            else:
                rejected += 1
                v = (verdict.verdict or "").lower()
                if v == "reject_cost":
                    rejected_cost += 1
                elif v == "reject_floor":
                    rejected_floor += 1
                else:
                    rejected_quality += 1
        # I15: tally floor-arm signal across all resources / rounds.  A
        # floor result lives only on first-promotion rounds; once an
        # incumbent exists, floor_pass_rate is None.  ``floor_below``
        # counts cases where candidate < floor (the safety-net catch).
        for r in eval_rounds:
            for e in r.entries:
                if e.path != path or e.floor_pass_rate is None:
                    continue
                floor_ran += 1
                if e.candidate_pass_rate < e.floor_pass_rate:
                    floor_below += 1

    mean_quality = _mean_quality(resources)

    lines = [
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Resources planned | {n_total} |",
        f"| ✅ Promoted | {promoted} |",
        f"|     · 🔄 recovered via feedback | {refined} |",
        f"| ❌ Rejected | {rejected} |",
    ]
    # I15 sub-breakdown — only emit when at least one was hit, to keep
    # the table compact for clean runs.
    if rejected_cost or rejected_floor or rejected_quality:
        lines.append(
            f"|     · cost regression | {rejected_cost} |"
        )
        lines.append(
            f"|     · below floor | {rejected_floor} |"
        )
        lines.append(
            f"|     · quality regression | {rejected_quality} |"
        )
    lines.extend(
        [
            f"| ⚠️ Unwinnable | {unwinnable} |",
            f"| ❌ GENERATE failed | {generate_failed} |",
            f"| ⏸ Pending | {pending} |",
        ]
    )
    if floor_ran:
        lines.append(
            f"| 🏁 Floor arm ran | {floor_ran} time(s); "
            f"candidate below floor in {floor_below} |"
        )
    lines.append(
        f"| Mean quality (overall) | {mean_quality:.2f} |"
        if mean_quality is not None
        else "| Mean quality (overall) | — |"
    )
    return "\n".join(lines)


def _render_phase_progression(state: dict[str, Any]) -> str:
    timings = state.get("phase_timings", {}) or {}
    current_phase = state.get("current_phase", "")
    completed = set(state.get("phases_completed", []) or [])

    # Mermaid gantt — emit only timings we have, in canonical order.
    gantt_rows = []
    seen_first = False
    for phase in _PHASE_ORDER:
        timing = timings.get(phase)
        if not timing:
            continue
        duration_s = timing.get("duration_s")
        # Mermaid gantt with `dateFormat X` (numeric/unix-time) requires the
        # duration field to be a plain integer count of seconds. Composite
        # strings like "6m 07s" / "1h 35m 22s" / "<1s" silently parse to 0
        # and collapse every bar to the start time. Use _format_duration only
        # for the human-readable per-phase table below.
        try:
            duration_int = max(1, int(round(float(duration_s)))) if duration_s else 1
        except (TypeError, ValueError):
            duration_int = 1
        # COMPLETE is terminal — when it's the current phase the run is
        # finished, so render it as `done` rather than `active`.
        is_terminal_complete = phase == "COMPLETE" and current_phase == "COMPLETE"
        is_active = (
            phase == current_phase and phase not in completed and not is_terminal_complete
        )
        marker = (
            "active, "
            if is_active
            else ("done, " if (duration_s or is_terminal_complete) else "")
        )
        tag = phase.lower().replace("_", "")
        anchor = "0" if not seen_first else f"after {gantt_rows[-1][0]}"
        gantt_rows.append((tag, f"    {phase}        :{marker}{tag}, {anchor}, {duration_int}s"))
        seen_first = True

    mermaid_block = ""
    if gantt_rows:
        mermaid_block = (
            "```mermaid\n"
            "gantt\n"
            "    title CGF Pipeline\n"
            "    dateFormat X\n"
            "    axisFormat %Mm%Ss\n"
            "\n"
            "    section Pipeline\n"
            + "\n".join(row for _, row in gantt_rows)
            + "\n```\n"
        )

    # Fallback / accessible table.
    table_lines = [
        "| Phase | Status | Started | Duration |",
        "|---|---|---|---|",
    ]
    current_idx = (
        _PHASE_ORDER.index(current_phase) if current_phase in _PHASE_ORDER else -1
    )
    for idx, phase in enumerate(_PHASE_ORDER):
        timing = timings.get(phase)
        if not timing:
            # Fallback: derive status from phases_completed / current_phase
            # for legacy state files that lack phase_timings.
            if phase in completed or (current_idx >= 0 and idx < current_idx):
                table_lines.append(f"| {phase} | ✅ | — | — |")
            elif phase == current_phase:
                table_lines.append(f"| {phase} | 🔄 Running | — | — |")
            else:
                table_lines.append(f"| {phase} | ⏸ Pending | — | — |")
            continue
        started = _fmt_ts(timing.get("started_at"))
        duration_s = timing.get("duration_s")
        # COMPLETE is terminal — when it's the current phase the run is
        # finished, even though it has no duration_s (nothing transitions
        # away from it).
        is_terminal_complete = phase == "COMPLETE" and current_phase == "COMPLETE"
        if duration_s is not None:
            status_marker = "✅" if phase in completed else "🔄"
            table_lines.append(
                f"| {phase} | {status_marker} | {started} | {_format_duration(duration_s)} |"
            )
        elif is_terminal_complete:
            table_lines.append(f"| {phase} | ✅ | {started} | — |")
        else:
            table_lines.append(f"| {phase} | 🔄 Running | {started} | — |")

    sections = ["## Phase progression"]
    if mermaid_block:
        sections.append("")
        sections.append(mermaid_block.rstrip())
    sections.append("")
    sections.extend(table_lines)
    return "\n".join(sections)


def _render_per_resource(
    state: dict[str, Any],
    summaries: dict[str, list[VersionSummary]],
    eval_rounds: list[EvalRound],
) -> str:
    """One ``<details>`` block per resource, summary line up top, version
    chain inside.

    Replaces the prior split between ``## Per-resource results`` (flat
    summary table) and ``## Iteration history`` (per-resource detail
    blocks).  The two carried overlapping data — latest pass rates,
    quality, and gate decision appeared in both — so this collapses
    them into a single section keyed by resource path.

    Single-version resources with no eval verdict get rendered as a
    flat list item (no ``<details>``) since there's nothing to drill
    into.
    """
    resources = state.get("resources", {}) or {}
    if not resources:
        return "## Per-resource results\n\n_No resources tracked yet._"

    latest_verdict = _latest_verdict_by_path(eval_rounds)
    blocks = ["## Per-resource results", ""]

    for path in sorted(resources.keys()):
        res = resources[path]
        rtype = res.get("resource_type", "?")
        version = res.get("version", 0) or 0
        version_label = f"v{version}" if version else "—"

        verdict = latest_verdict.get(path)
        verdicts_by_version = _verdicts_for_resource(path, eval_rounds)
        path_summaries = {s.version: s for s in summaries.get(path, [])}

        if verdict is not None:
            baseline = f"{verdict.baseline_pass_rate:.2f}"
            candidate = f"{verdict.candidate_pass_rate:.2f}"
            delta = verdict.candidate_pass_rate - verdict.baseline_pass_rate
            delta_label = (
                f"{'+' if delta > 0 else ''}{delta:.2f}" if delta else "±0.00"
            )
            pass_summary = f"pass {baseline}→{candidate} ({delta_label})"
        else:
            pass_summary = "_pending eval_"

        quality_overall = _safe_float((res.get("quality") or {}).get("overall"))
        quality_summary = (
            f" · quality {quality_overall:.2f}" if quality_overall else ""
        )
        status_label = _resource_status_label(path, res, eval_rounds)

        summary_line = (
            f"<strong><code>{path}</code></strong> — "
            f"{status_label} · {rtype} · {version_label} · "
            f"{pass_summary}{quality_summary}"
        )

        # Version chain.  Drawn from eval verdicts + summary files +
        # state.version so we surface every version the orchestrator
        # touched, even when artifacts are partial.
        versions_seen = (
            set(verdicts_by_version.keys())
            | set(path_summaries.keys())
            | {version}
        )
        versions_seen.discard(0)
        versions_sorted = sorted(versions_seen)

        # Bare list item when there's nothing to drill into.
        if len(versions_sorted) <= 1 and not verdicts_by_version:
            blocks.append(f"- {summary_line}")
            blocks.append("")
            continue

        body: list[str] = ["", "<details>", f"<summary>{summary_line}</summary>", ""]
        body.append(
            "| Version | Pass rate | Quality | Words | Iterations | "
            "Cost/success | Gate |"
        )
        body.append("|---|---|---|---|---|---|---|")
        for v in versions_sorted:
            v_verdict = verdicts_by_version.get(v)
            v_summary = path_summaries.get(v)
            pass_rate = (
                f"{v_verdict.candidate_pass_rate:.2f}" if v_verdict else "—"
            )
            # I15: verdict-aware Gate column.  Collapse pre-cgf-eval-ab
            # legacy "refine" / "reject" into a single ❌ Reject for
            # backcompat; new verdicts get their own labels so operators
            # can spot reject_cost vs reject_floor at a glance.
            gate = "—"
            if v_verdict is not None:
                gate = _gate_label(v_verdict.verdict)
            # I15: cost-per-success column.  When both baseline and
            # candidate have signal, render "$baseline → $candidate
            # (Δ%)" so a glance shows whether cost regressed.  When
            # either is None, show "—".
            cps = _cps_label(v_verdict) if v_verdict is not None else "—"
            quality = (
                f"{v_summary.quality_overall:.2f}"
                if v_summary and v_summary.quality_overall
                else "—"
            )
            words = (
                f"{v_summary.word_count:,}"
                if v_summary and v_summary.word_count
                else "—"
            )
            iterations = (
                str(v_summary.iterations)
                if v_summary and v_summary.iterations is not None
                else "—"
            )
            body.append(
                f"| v{v} | {pass_rate} | {quality} | {words} | "
                f"{iterations} | {cps} | {gate} |"
            )

        latest_summary = path_summaries.get(versions_sorted[-1])
        if latest_summary and latest_summary.key_improvements:
            body.append("")
            body.append(
                f"**Improvements applied (v{latest_summary.version}):**"
            )
            for imp in latest_summary.key_improvements[:8]:
                body.append(f"- {imp}")
            if len(latest_summary.key_improvements) > 8:
                body.append(
                    f"- _…and {len(latest_summary.key_improvements) - 8} more_"
                )
        body.append("")
        body.append(
            f"[Full CHANGELOG.md entry →]"
            f"(../CHANGELOG.md#resource-{_anchorize(path)})"
        )
        body.append("</details>")
        blocks.extend(body)

    return "\n".join(blocks).rstrip()


def _render_open_issues(
    state: dict[str, Any], eval_rounds: list[EvalRound]
) -> str:
    items: list[str] = []
    resources = state.get("resources", {}) or {}

    for path, res in resources.items():
        status = (res.get("status") or "").lower()
        error = res.get("error") or ""
        if status == "failed":
            msg = error.strip().splitlines()[0] if error else "(no error message)"
            items.append(
                f"- ❌ **GENERATE failed:** `{path}` — {msg}"
            )
        elif status == "unwinnable":
            items.append(
                f"- ⚠️ **Unwinnable:** `{path}` scored 0/0 on both arms; "
                "excluded from subsequent rounds (F21)."
            )

    # Pending verdicts: resources in state but not in any eval round.
    seen_in_eval = {
        entry.path for rnd in eval_rounds for entry in rnd.entries
    }
    pending_paths = [
        p for p, r in resources.items()
        if p not in seen_in_eval
        and (r.get("status") or "").lower() not in {"failed", "unwinnable"}
    ]
    if pending_paths and state.get("current_phase") != "COMPLETE":
        items.append(
            f"- 🔄 **Pending verdict:** {len(pending_paths)} resource(s) "
            "not yet evaluated."
        )

    # Feedback-loop summary.
    fh = state.get("feedback_history", []) or []
    if fh:
        items.append(
            f"- 📋 **Feedback rounds applied:** {len(fh)} "
            f"(max: {state.get('max_iterations', '?')})."
        )

    if not items:
        return "## Open issues\n\n_None._"
    return "## Open issues\n\n" + "\n".join(items)


def _render_artifacts(workspace_root: Path, state: dict[str, Any]) -> str:
    lines = [
        "## Artifacts",
        "",
    ]
    eval_suite_path = state.get("eval_suite_path") or "_(not generated yet)_"
    eval_results_path = state.get("eval_results_path") or "_(not generated yet)_"
    research_path = state.get("research_findings_path") or "_(not generated yet)_"
    resource_plan_path = state.get("resource_plan_path") or "_(not generated yet)_"

    lines.append(f"- **Eval suite:** `{_relative_to(eval_suite_path, workspace_root)}`")
    lines.append(
        f"- **Eval results:** `{_relative_to(eval_results_path, workspace_root)}`"
    )
    lines.append(
        f"- **Research findings:** `{_relative_to(research_path, workspace_root)}`"
    )
    lines.append(
        f"- **Resource plan:** `{_relative_to(resource_plan_path, workspace_root)}`"
    )
    lines.append("- **State file:** [`sessions/optimization-state.json`](./optimization-state.json)")
    lines.append("- **Per-version summaries:** [`sessions/`](./) and `*/sessions/*.summary.json`")
    lines.append("- **Human-authored history:** [`CHANGELOG.md`](../CHANGELOG.md)")
    lines.append("- **Grafana dashboard:** http://localhost:3000/d/casdk-cgf")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Status classifiers + small helpers
# ---------------------------------------------------------------------------


def _classify_run_status(state: dict[str, Any]) -> str:
    current_phase = state.get("current_phase", "")
    if current_phase == "COMPLETE":
        return "complete"
    if current_phase == "failed" or current_phase == "FAILED":
        return "failed"
    # Heuristic: if updated_at is older than 10 minutes AND not COMPLETE, mark paused.
    updated_at = state.get("updated_at", "")
    if updated_at:
        try:
            updated = datetime.fromisoformat(updated_at)
            age = (datetime.now(UTC) - updated).total_seconds()
            if age > 600:
                return "paused"
        except (TypeError, ValueError):
            pass
    return "running"


def _resource_status_label(
    path: str, res: dict[str, Any], eval_rounds: list[EvalRound]
) -> str:
    status = (res.get("status") or "").lower()
    if status == "failed":
        return "❌ Failed"
    if status == "unwinnable":
        return "⚠️ Unwinnable"

    # Find the latest round this resource appears in.
    latest_round: int | None = None
    latest_promoted = False
    rounds_seen: list[tuple[int, bool]] = []
    for rnd in eval_rounds:
        for entry in rnd.entries:
            if entry.path == path:
                rounds_seen.append((rnd.feedback_iteration, entry.promoted))
                if latest_round is None or rnd.feedback_iteration > latest_round:
                    latest_round = rnd.feedback_iteration
                    latest_promoted = entry.promoted

    if latest_round is None:
        if status == "optimized":
            return "🔄 Pending eval"
        return "⏸ Pending"

    if latest_promoted:
        # If promoted in round >1 AND failed an earlier round → "recovered"
        if latest_round > 1 and any(not p for r, p in rounds_seen if r < latest_round):
            return f"✅ Promoted r{latest_round} (recovered)"
        return f"✅ Promoted r{latest_round}"
    return f"❌ Rejected r{latest_round}"


def _latest_verdict_by_path(
    eval_rounds: list[EvalRound],
) -> dict[str, EvalRoundEntry]:
    """Map path → latest-round entry."""
    latest: dict[str, EvalRoundEntry] = {}
    for rnd in eval_rounds:
        for entry in rnd.entries:
            existing = latest.get(entry.path)
            if existing is None or rnd.feedback_iteration > 0:
                latest[entry.path] = entry
    return latest


def _verdicts_for_resource(
    path: str, eval_rounds: list[EvalRound]
) -> dict[int, EvalRoundEntry]:
    """Map version → eval-round entry for one resource."""
    by_version: dict[int, EvalRoundEntry] = {}
    for rnd in eval_rounds:
        for entry in rnd.entries:
            if entry.path == path:
                by_version[entry.version] = entry
    return by_version


def _has_recovered(path: str, eval_rounds: list[EvalRound]) -> bool:
    seen_rejection = False
    seen_promotion = False
    for rnd in sorted(eval_rounds, key=lambda r: r.feedback_iteration):
        for entry in rnd.entries:
            if entry.path != path:
                continue
            if entry.promoted:
                seen_promotion = True
            else:
                seen_rejection = True
    return seen_rejection and seen_promotion


def _mean_quality(resources: dict[str, dict[str, Any]]) -> float | None:
    scores = []
    for res in resources.values():
        overall = _safe_float((res.get("quality") or {}).get("overall"))
        if overall is not None:
            scores.append(overall)
    if not scores:
        return None
    return sum(scores) / len(scores)


def _relative_to(path: str | Path, root: Path) -> str:
    """Best-effort relative path; falls back to the input string."""
    if not path or path == "":
        return "_(not generated yet)_"
    try:
        p = Path(path)
        if p.is_absolute():
            return str(p.relative_to(root))
        return str(p)
    except (ValueError, TypeError):
        return str(path)


def _fmt_ts(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError):
        return value


def _format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "—"
    if s < 1:
        return "<1s"
    if s < 60:
        return f"{s:.0f}s"
    minutes, sec = divmod(int(s), 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {sec:02d}s"


def _format_wall_time(started_at: str, updated_at: str) -> str:
    if not started_at or not updated_at:
        return "—"
    try:
        s = datetime.fromisoformat(started_at)
        u = datetime.fromisoformat(updated_at)
        return _format_duration((u - s).total_seconds())
    except (TypeError, ValueError):
        return "—"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_word_count(value: Any) -> int | None:
    """Accept either an int or a dict-of-counts shape.

    Some agents emit ``"word_count": 4834``; others emit a richer
    ``{"original": 3450, "optimized": 5967, "delta": 2517, ...}``.
    Prefer the optimized count when present; otherwise fall back to
    original / delta / first numeric value.
    """
    if isinstance(value, dict):
        for key in ("optimized", "final", "after", "current", "original", "before"):
            n = _safe_int(value.get(key))
            if n is not None:
                return n
        for v in value.values():
            n = _safe_int(v)
            if n is not None:
                return n
        return None
    return _safe_int(value)


def _extract_iterations(data: dict[str, Any]) -> int | None:
    """Read the iteration count from either schema variant.

    Two shapes in the wild: ``"iterations": 1`` (int) and
    ``"iteration": "2/2"`` (current/max string). The latter comes from
    ITERATE-phase agents; pull the leading current-iteration number.
    """
    n = _safe_int(data.get("iterations"))
    if n is not None:
        return n
    raw = data.get("iteration")
    if isinstance(raw, str):
        head = raw.split("/", 1)[0].strip()
        return _safe_int(head)
    return _safe_int(raw)


_ANCHOR_RE = re.compile(r"[^a-z0-9]+")


def _anchorize(path: str) -> str:
    """Best-effort GitHub-style anchor slug for a resource path."""
    return _ANCHOR_RE.sub("", path.lower())


def _atomic_write(target: Path, content: str) -> None:
    """Write ``content`` to ``target`` atomically via tempfile + replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        dir=target.parent,
        prefix=target.name + ".",
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)
