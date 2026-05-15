# CGF Run Report — Design

A human-readable markdown summary of each CGF optimization run, regenerated incrementally as the pipeline progresses. Single place to glance at "what's happening / what happened" without opening Grafana or JSON.

**Branch:** `cgf-eval-ab` (ships alongside the four Phase A refinements in [PHASEA_SUMMARY.md § 4](./PHASEA_SUMMARY.md#4-phase-a-refinement-plan)).
**Status:** Design.

---

## 1. Goal

Produce `workspace/{spec}/sessions/RUN_REPORT.md`: a markdown view over the existing state files. The report:

- Updates incrementally — refreshed on every phase boundary and per-resource event.
- **Is purely derived.** No new source of truth, no parallel tracking system. Render-on-write.
- Is **edited in place**, not versioned. The underlying JSON + `CHANGELOG.md` are the durable record; the report is convenience.
- Costs ~milliseconds to regenerate (in-memory JSON reads + string templating).

### Non-goals

- **Not** a replacement for Grafana (live ops time-series, alerts, oncall).
- **Not** a replacement for `optimization-state.json` (machine-readable truth).
- **Not** a replacement for `CHANGELOG.md` (human-authored per-resource summaries; the report *links to* it, doesn't duplicate).
- **Not** a cross-run dashboard or cost-attribution view.

---

## 2. Sources of truth

The report reads from files the pipeline already writes. No new persistence (with one tiny exception, § 7).

| Source | Path | What it gives us |
|---|---|---|
| Run state | `sessions/optimization-state.json` | `spec_path`, `spec_type`, `current_phase`, `phases_completed`, `resources{}`, `feedback_history`, `started_at`, `updated_at`, `max_iterations`, `validate_refinement_count` |
| Per-resource per-version summary | `sessions/{resource}-v{n}.summary.json` and sub-resource paths (e.g. `agents/sessions/*.summary.json`, `commands/sessions/*.summary.json`) | `quality{overall,completeness,accuracy,clarity}`, `word_count`, `iterations`, `key_improvements`, `competencies_addressed` |
| Eval verdicts | `eval/execution-eval-round-{1,2}.json` | per-resource `win_rate`, `baseline_pass_rate`, `candidate_pass_rate`, `no_decision_rate`, `scenarios`, `promoted` |
| QA decisions | `sessions/qa-decisions.json` | auto-acceptance log for `resource-plan.yaml` |
| Human-authored history | `CHANGELOG.md` (workspace root) | Per-version narrative summaries — **linked from**, not duplicated into, the report |

### Real-data confirmation

The `workspace/iac-team/` directory after run #6 contains:

```
workspace/iac-team/
├── CHANGELOG.md
├── sessions/
│   ├── optimization-state.json
│   ├── qa-decisions.json
│   ├── iac-generator-v1.summary.json
│   └── iac-analyzer-v1.summary.json
├── agents/sessions/
│   └── iac-validator-v1.summary.json
├── commands/sessions/
│   └── iac-v1.summary.json
└── eval/
    ├── execution-eval-round-1.json
    └── execution-eval-round-2.json
```

The renderer globs the three `sessions/` paths and the two `eval/execution-eval-round-*.json` files, joins on `resource_path` + `version`, and renders.

---

## 3. Output

Single file, in place, no archiving:

```
workspace/{spec}/sessions/RUN_REPORT.md     # current run, regenerated on every event
```

Reasons against archiving:
- `CHANGELOG.md` already preserves per-version history (workspace-root, survives `cgf-clean`).
- `optimization-state.json` and `*.summary.json` survive in their pre-reset state.
- A user wanting "what did the last run produce" reads CHANGELOG.md; a user wanting "what's happening now" reads RUN_REPORT.md. Two roles, two files.
- Saves the "filename = original-run start time, written by next run" off-by-one.

`cgf-clean` wipes `sessions/RUN_REPORT.md` along with the rest of the session state — the next `make optimize` regenerates it from scratch.

---

## 4. Content

Seven sections. Sketch with real fields from run #6 below.

### 4.1 Header

```markdown
# CGF Run Report — iac-team

**Status:** 🟢 Running · **Phase:** EXECUTION_EVAL r2
**Spec:** `workspace/iac-team/SPEC.md` (sha256: `4f8c2a…`)
**Started:** 2026-05-14 10:42:33 UTC · **Last update:** 2026-05-14 12:07:11 UTC
**Wall time:** 1h 24m · **Grafana:** [casdk-cgf dashboard](http://localhost:3000/d/casdk-cgf)
```

Status badges: 🟢 running / ✅ complete / ❌ failed / ⏸ paused / 🔄 resumed.

### 4.2 Summary

```markdown
| Metric | Value |
|---|---|
| Resources planned | 18 |
| Promoted | 8 |
| Refined (in feedback loop) | 5 |
| Rejected | 2 |
| Unwinnable | 1 (`agents/iac-analyzer`) |
| GENERATE failed | 1 (`skills/aws-eks`, F25) |
| Pending | 1 |
| Total cost | $2.84 |
| Total tokens | 451,552 |
| Mean quality (overall) | 0.89 |
```

### 4.3 Phase progression (Mermaid)

Gantt renders inline on GitHub, GitLab, IntelliJ, VS Code (with Mermaid extension), and most markdown previewers. Render cost: zero (text-only). Falls back to a normal table view if Mermaid isn't supported.

```markdown
```mermaid
gantt
    title CGF Pipeline — iac-team (run started 2026-05-14 10:42 UTC)
    dateFormat HH:mm:ss
    axisFormat %H:%M

    section Setup
    RESEARCH        :done, r1, 10:42:33, 4m 56s
    DESIGN          :done, d1, after r1, 1m 33s
    QA              :done, q1, after d1, 1s

    section Build
    GENERATE        :done, g1, after q1, 17m 10s
    EVAL_DESIGN     :done, e1, after g1, 6m 27s

    section Loop r1
    ITERATE r1      :done, i1, after e1, 33m 09s
    EXECUTION_EVAL r1 :done, x1, after i1, 10m 43s

    section Loop r2
    ITERATE r2      :done, i2, after x1, 7m 01s
    EXECUTION_EVAL r2 :active, x2, after i2, 1m
    VALIDATE        :, v1, after x2, 3m
    COMPLETE        :, c1, after v1, 1s
```
```

Followed by a table for accessibility / non-Mermaid viewers:

```markdown
| Phase | Status | Started | Duration |
|---|---|---|---|
| RESEARCH | ✅ | 10:42:33 | 4m 56s |
| DESIGN | ✅ | 10:47:29 | 1m 33s |
...
```

### 4.4 Per-resource results

One row per resource, sorted by status then path. Real values from run #6's `execution-eval-round-1.json` + `*.summary.json`:

```markdown
| Resource | Type | Latest | Baseline pass | Candidate pass | Δ | Quality | Status |
|---|---|---|---|---|---|---|---|
| skills/aws-cli              | skill   | v1 | 1.00 | 1.00 |  0.00 | 0.92 | ✅ Promoted r1 (tie) |
| skills/container-analysis   | skill   | v1 | 1.00 | 1.00 |  0.00 | 0.91 | ✅ Promoted r1 (tie) |
| skills/crossplane           | skill   | v1 | 0.33 | 0.33 |  0.00 | 0.88 | ✅ Promoted r1 |
| skills/security-validation  | skill   | v1 |  —   |  —   |   —  | 0.88 | ✅ Promoted r1 |
| agents/iac-generator        | agent   | v1 | 0.00 | 0.33 | +0.33 | 0.92 | ✅ Promoted r1 |
| commands/iac                | command | v1 | 0.00 | 0.33 | +0.33 | 0.88 | ✅ Promoted r1 |
| agents/pulumi-cdk           | agent   | v2 | 1.00 | 1.00 |  0.00 | 0.90 | ✅ Promoted r2 (recovered) |
| agents/iac-analyzer         | agent   | v1 | 0.00 | 0.00 |   —  | 0.91 | ⚠️ Unwinnable |
| skills/aws-eks              | skill   | —  |  —   |  —   |   —  |  —   | ❌ GENERATE timeout (F25) |
```

Once 4.3's cost gate lands, add a `cost_per_success` column between Δ and Quality.

### 4.5 Iteration history

Collapsible per-resource (HTML `<details>` tag inside markdown). For each resource that had >1 version, render the version chain with values pulled from each `*.summary.json` and the matching `execution-eval-round-N.json` entry:

```markdown
<details>
<summary><strong>agents/pulumi-cdk</strong> — 2 versions, recovered after r1 regression</summary>

| Version | Round | Pass rate | Quality | Words | Iterations | Gate | Notes |
|---|---|---|---|---|---|---|---|
| v0 | baseline | 1.00 | — | — | — | n/a | First draft |
| v1 | r1 | 0.67 | 0.89 | 3,512 → 4,128 | 1 | ❌ Reject | `medium-component-01` hit 180s trial timeout |
| v2 | r2 | 1.00 | 0.90 | 4,128 → 4,201 | 2 | ✅ Promote | Feedback addressed slow scenario |

**Improvements applied (v2):**
- Reduced verbose multi-step plan output for medium-component scenario
- Added explicit time-budget guidance in component generation phase

[Full CHANGELOG.md entry →](../CHANGELOG.md#resource-agentspulumi-cdkmd)
</details>
```

The `key_improvements` array comes from `summary.json`; the link points back to `CHANGELOG.md` for the human-authored narrative.

### 4.6 Open issues

Auto-emitted callouts based on state:

```markdown
- ❌ **GENERATE timeout (F25):** `skills/aws-eks` exceeded 905s (cap: 900s). Last 27 turns produced 0 tool_calls.
- ⚠️ **Unwinnable:** `agents/iac-analyzer` scored 0/0 across all 3 scenarios. F21 marked it unwinnable; excluded from round 2.
- 🔄 **Pending verdict:** EXECUTION_EVAL r2 running on 1 resource (`agents/pulumi-cdk`).
```

### 4.7 Artifacts

```markdown
- **Eval suite:** `eval/eval-suite.yaml` (sha256: `abc123…`)
- **Eval results:** [`eval/execution-eval-round-1.json`](../eval/execution-eval-round-1.json), [`eval/execution-eval-round-2.json`](../eval/execution-eval-round-2.json)
- **State file:** [`sessions/optimization-state.json`](./optimization-state.json)
- **Per-version summaries:** [`sessions/*.summary.json`](./)
- **Human-authored history:** [`CHANGELOG.md`](../CHANGELOG.md)
- **Grafana dashboard:** http://localhost:3000/d/casdk-cgf
```

---

## 5. Render mechanics

Pure-function pipeline, no shared state, no locks beyond the orchestrator's existing one:

```python
# src/harness/optimization/run_report.py

def render(workspace_root: Path) -> str:
    """Read all state files, produce markdown string."""
    state = _load_optimization_state(workspace_root / "sessions/optimization-state.json")
    summaries = _load_summaries(workspace_root)  # globs sessions/*.summary.json + sub-resource paths
    eval_rounds = _load_eval_rounds(workspace_root / "eval")
    return _render_markdown(state, summaries, eval_rounds)

def write(workspace_root: Path) -> Path:
    """Render and atomically write to sessions/RUN_REPORT.md."""
    target = workspace_root / "sessions" / "RUN_REPORT.md"
    content = render(workspace_root)
    _write_atomic(target, content)  # tempfile + os.replace
    return target
```

- **Atomic write:** `pathlib.Path.write_text()` via a sibling tempfile + `os.replace`. Same pattern as the existing checkpoint writer (`harness/checkpoint.py`).
- **No new lock.** Render fires *after* `_save_state()` inside the orchestrator's existing `_state_lock`. By the time render runs, all JSON sources are coherent.
- **Tolerant of missing files.** Sub-resource summary directories don't always exist; render emits `—` rather than erroring.

---

## 6. Integration points

Single hook. The orchestrator already saves state on every phase transition and every per-resource event; piggyback there:

```python
# multi_resource_orchestrator.py (sketch)

async def _save_state(self) -> None:
    async with self._state_lock:
        self._write_optimization_state()
        if self.config.run_report_enabled:           # CGF_RUN_REPORT=1, default on
            run_report.write(self.workspace_root)
```

Every existing call site to `_save_state()` then implicitly updates the report — no per-callsite plumbing needed. This is also why we don't need a write-cadence enumeration; the cadence is already correct because `_save_state()` is called at exactly the right boundaries (phase entries, per-resource events, error paths).

---

## 7. The one new field

`optimization-state.json` doesn't currently track per-phase wall-clock times. The state file has `started_at` and `updated_at` (run-level), and `phases_completed` (a list), but no per-phase start/end.

Smallest additive change — extend the existing state schema:

```json
{
  "phases_completed": ["RESEARCH", "DESIGN", "QA", "GENERATE", "EVAL_DESIGN", "ITERATE", "EXECUTION_EVAL"],
  "phase_timings": {
    "RESEARCH":        {"started_at": "...", "completed_at": "...", "duration_s": 296},
    "DESIGN":          {"started_at": "...", "completed_at": "...", "duration_s": 93},
    "QA":              {"started_at": "...", "completed_at": "...", "duration_s": 0.4},
    "GENERATE":        {"started_at": "...", "completed_at": "...", "duration_s": 1030},
    "EVAL_DESIGN":     {"started_at": "...", "completed_at": "...", "duration_s": 387},
    "ITERATE":         {"started_at": "...", "completed_at": null, "duration_s": null}
  }
}
```

~10 LOC change in `_advance_phase()`: record `started_at` on entry, set `completed_at` + compute `duration_s` on exit. Backward-compatible (renderer treats missing field as "—"). Multi-round phases (ITERATE r1 / r2, EXECUTION_EVAL r1 / r2) get the *last* timing — the Mermaid gantt and the per-phase table both already split by round when reading `feedback_history`.

---

## 8. CLI surface

1. **Auto-emit during `make optimize`.** Path printed on startup and completion:
   ```
   📋 Run report: workspace/iac-team/sessions/RUN_REPORT.md (updates live)
   ```
2. **`make report SPEC=workspace/iac-team`** — re-render from existing state without re-running the pipeline. Useful after a kill, on a finished workspace, or while iterating on the report template itself.
3. **`CGF_RUN_REPORT=0`** — opt-out env var (defaults on). Reserved escape hatch in case the writer ever introduces overhead worth measuring.

`--watch` mode (tail-the-file via `entr` or `watchman`) is a nice-to-have; defer until the report has been in the workflow for a week.

---

## 9. Implementation plan

Estimated ~1.5 days of work. Single PR; lands on `cgf-eval-ab` before the four eval refinements so they benefit from the visibility.

**Order:**

1. Add `phase_timings` to `optimization-state.json` and instrument `_advance_phase()`. ~10 LOC + 2 unit tests.
2. New module `src/harness/optimization/run_report.py`:
   - `load_optimization_state(path) -> RunState`
   - `load_summaries(workspace_root) -> dict[str, list[VersionSummary]]` (handles top-level + sub-resource glob)
   - `load_eval_rounds(eval_dir) -> list[EvalRound]`
   - `render(state, summaries, eval_rounds) -> str` — pure
   - `write(workspace_root) -> Path` — atomic write of `sessions/RUN_REPORT.md`
   - All dataclasses Pydantic; tolerant of missing fields. ~250 LOC.
3. Wire into `MultiResourceOrchestrator._save_state()`. ~5 LOC.
4. `make report SPEC=...` target + `harness.optimization.cli.run_report` argparse entry. ~30 LOC.
5. Mermaid renderer with fallback table — both always emitted (the table is the accessibility fallback; cost is trivial). ~50 LOC of the 250.
6. Tests:
   - **Unit:** ~12 tests against a fixture workspace tree (copy of `workspace/iac-team/sessions/` + `eval/`). Verify rendered markdown contains expected substrings, missing-file tolerance, mermaid block emission, status badge selection.
   - **Integration:** 1 test that runs the smoke fixture end-to-end and asserts `sessions/RUN_REPORT.md` reaches a "COMPLETE" status badge.

**Sequencing within `cgf-eval-ab`:**

| Step | Why before the eval refinements |
|---|---|
| Run-report ships first | Low-risk derived view; immediately accelerates debugging of 4.1 (eval-agent isolation) by giving you a "what's the optimizer doing right now" view during long iac-team runs. |
| 4.1 isolation | Largest mechanical change; biggest beneficiary of having the report already live. |
| 4.2 dual baseline | Adds `baseline_floor_pass_rate` column to the report's per-resource table — additive. |
| 4.3 cost gate | Adds `cost_per_success` column — additive. |
| 4.4 pipeline tightening | No new report content; eval-suite hash already surfaces as an artifact link. |

---

## 10. What this deliberately doesn't track

- **Cross-run comparison.** "Was today's run better than yesterday's?" — That's a Grafana / external-tooling problem.
- **Cost attribution per model call.** Aggregates only; the per-call detail lives in OTel spans.
- **Diff between versions.** `CHANGELOG.md` carries the narrative; `git diff workspace/iac-team/agents/pulumi-cdk-v1.md workspace/iac-team/agents/pulumi-cdk-v2.md` carries the bytes.
- **Approval / sign-off workflow.** Future Stage 4 `--review` mode adds checkpoints; the report renders the *current* checkpoint state but doesn't host the UI.

---

## 11. Open questions

None blocking implementation. Decisions taken with this design (recorded so they don't reopen mid-implementation):

| Decision | Value |
|---|---|
| Output location | `sessions/RUN_REPORT.md` (ephemeral, with the rest of session state) |
| Archive policy | None — CHANGELOG.md + JSON files already preserve history |
| Source of truth | Existing `optimization-state.json` + `*.summary.json` + `execution-eval-round-*.json` + `CHANGELOG.md` |
| Mermaid | Yes; emit both gantt and fallback table |
| New persistence | One field: `phase_timings` in `optimization-state.json` (~10 LOC) |
| Write trigger | Piggyback on existing `_save_state()`; no per-phase plumbing |
