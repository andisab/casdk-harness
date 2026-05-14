# Phase-A Eval Pipeline — Summary

This doc has three objectives:

1. **Current state** — what works today, what's shipped, where the code lives.
2. **Architecture & technical decisions** — what was built and *why*.
3. **Open issues & future work** — what's queued, what needs investigation, what's deliberately deferred.

For per-defect fix histories see `git log` on `phase-a-fixes` / `phase-a-perf`; for the canonical Stage-3 plan see [CGF-EVAL-FRAMEWORK.md](./CGF-EVAL-FRAMEWORK.md).

---

## 1. Current state

### Branch ledger

| Branch | Carries | Status |
|---|---|---|
| `contextgrad-eval` | Stages 1+2 + Phase A.1–A.7 (eval framework end-to-end) | Merged |
| `phase-a-fixes` | F3–F16 (14 defects: parallelism, architect prompt, gate logic, scenario attribution) | Merged into `contextgrad-eval` |
| `phase-a-perf` | F17–F22 (skip-unchanged, concurrency bumps, per-level timeouts, command-prompt fix, unwinnable detector, subagent audit) | Code-complete; not yet smoke-validated |

**Unit suite:** 1863 passing, 0 failing on `phase-a-perf` (1856 baseline + 7 new). Pre-existing path-issue errors in `test_eval_telemetry.py::TestEnvVarsExposed` are unrelated.

### What works end-to-end (validated under real load, run #5i)

- All 9 pipeline phases exercise across two EXECUTION_EVAL rounds with state-machine resume.
- Per-resource scenario attribution is correct (only 3 of 54 scenarios run per resource).
- Self-contained scenarios run (agents invoke their resource and produce transcripts).
- Optimizer adds real value: 3 of 18 resources had genuine candidate wins ≥ +0.33 pass-rate.
- Feedback loop recovers regressions: 3 of 3 round-1 regressions promoted on round 2 after feedback injection.
- Token signal is real (~620k tokens captured per run; previously read as 0).
- Parallelism delivers ~12× speedup over the projected sequential baseline.
- Promotion gate fails closed when every resource errored (no spurious "all promoted").

### Where the code lives

| Concern | Module |
|---|---|
| Multi-resource state machine | `harness/optimization/multi_resource_orchestrator.py` |
| Per-phase implementations | `harness/optimization/_orchestrator_phases/` |
| Eval runner (two-arm) | `harness/optimization/eval_harness/runner.py` |
| Graders (deterministic / LLM-judge / trajectory) | `harness/optimization/graders/` |
| Eval-architect agent | `src/harness/plugins/cgf-agents/agents/eval/cgf-eval-architect.md` |
| Eval-suite schema | `src/harness/optimization/eval_harness/eval_suite.schema.json` |
| Smoke fixtures | `tests/smoke/iac-team`, `tests/smoke/python-expert` |

---

## 2. Architecture & technical decisions

### Pipeline

```
RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE
                                                     ↓
                                       EXECUTION_EVAL → VALIDATE → COMPLETE
                                              ↑              ↓
                                              └─── feedback ──┘ (max 2 rounds)
```

Nine phases, single linear flow with one bounded loop. Per-resource status lives in `optimization-state.json`; deleting `sessions/` is the canonical reset.

### Two-arm eval

Each candidate is scored against its own baseline (`{resource}-v0.md`). The promotion gate is the bare `candidate.pass_rate ≥ baseline.pass_rate + ε` (Phase A simple-threshold; Phase B replaces with bootstrap CI on win rate). Held-out scenarios drive the gate but are NEVER shown to the optimizer in feedback prompts.

### Concurrency model

Per-resource phases run under `asyncio.gather` + `Semaphore`. State writes serialize through `MultiResourceOrchestrator._state_lock`. Per-call timeouts are independent of the semaphore (worst-case makespan is bounded by the slowest single resource × ceil(N/concurrency)).

| Knob | Default | Rationale |
|---|---|---|
| `CGF_GENERATE_CONCURRENCY` | 8 | I/O-bound on SDK API; 8-way saturates a typical sonnet rate window. |
| `CGF_ITERATE_CONCURRENCY` | 4 | Each iteration is expensive (~1200s timeout, ~30k tokens); marginal speedup vs 429-risk is poor above 4. |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 4 | Judge calls are I/O-bound; 2-way left ~6 scenario slots idle in run #5i. |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | Inside one resource: 6 scenarios × 2 arms = 12 in-flight calls, well below rate limit. |

D9 retry covers transient 429s; env-var downgrade is the rate-limit escape hatch.

### Scenario sandboxing

Every scenario runs in a fresh `/tmp/eval-<id>-<arm>-<hex>` directory. Nothing exists there until `setup.files` (inline content, sandbox-relative paths) materializes it. **No `/sample-app`, no `/manifests`, no `/workspace`** at eval time. Architect prompt forbids absolute paths and `..` segments.

### Feedback loop

When the gate fails for a resource, EXECUTION_EVAL writes a feedback entry (failing scenarios, baseline/candidate scores, held-out scenarios stripped) into `state.feedback_history` and transitions back to ITERATE. The optimizer reads the latest entry for the resource it's iterating and injects it as additional context. Max 2 feedback rounds before VALIDATE escalation.

### Per-level trial timeout

Trajectory scenarios get 300s; unit / e2e get 180s. At `trials_per_scenario=3` (production cadence), the global 300s would have allowed one slow scenario to burn 900s on a single resource — F19 caps that.

### Skip-unchanged-resources filter

`_resources_to_evaluate` filters by `version > last_evaluated_version`. ITERATE round 2 only touches resources flagged `needs_refinement`; EXECUTION_EVAL round 2 now mirrors that by skipping resources whose candidate file didn't change. Saved ~12 min + ~300k tokens per feedback cycle.

### Unwinnable-resource detection

A resource where every scenario scores 0 on both arms is marked `status="unwinnable"`. Feedback iteration cannot help — either the scenarios are unwinnable for this resource type, or the rubric is mis-calibrated. The gate treats unwinnable as non-blocking (counts as "no actionable feedback"); the F17 filter excludes them from future eval rounds.

### Why an in-process eval runner (today) and ephemeral container (Phase C)

Phase A.4 chose in-process for speed of iteration. Phase C will swap to `docker compose run --rm` per eval scenario for SWE-bench-style determinism (tmpfs workspace, pinned model, isolated `/memory`). The runner already has `runtime: Literal["in_process", "ephemeral_container"]` as a knob — Phase C only wires the container variant.

### Phase-boundary subprocess audit

`_audit_child_processes()` snapshots `claude` descendants of the orchestrator PID before/after each phase. Non-empty diff → warning log. Observe-only; soft-kill follow-up is gated behind a week of telemetry data showing the actual orphan rate.

---

## 3. Key learnings from test runs

### Validated assumptions

- **Parallelism is correct AND fast.** No state-race symptoms across 18-resource batches; lock contention is invisible compared to per-resource wall time.
- **The optimizer responds to feedback.** Resources that regressed in round 1 (crossplane, github-actions, gitlab-ci) recovered after EXECUTION_EVAL feedback was injected — one of them swung from 0.00 to 0.67.
- **Per-resource scenario attribution works.** Pre-F13 every resource ran all 54 scenarios; post-F13/F16 the harness filters down to the 3 designed for that resource. Cross-resource ties (the 0.40-vs-0.40 noise floor that masked everything) disappeared.
- **Fail-closed gate logic is sound.** A run where every resource errored (F8 pre-fix) silently advanced to VALIDATE with `promoted=0`; the gate now hard-aborts when all resources error and refuses to advance with zero real promotions.

### Real cost characteristics (iac-team, 18 resources, smoke = trials=1)

| Metric | Value |
|---|---|
| Per-resource eval | 30 s – 5 min wall time, 7 k – 72 k tokens |
| Per-resource generation | 4 – 11 min |
| EVAL_DESIGN (architect) | ~10 min for 54 scenarios |
| Full pipeline (pre-F17–F22) | ~107 min |
| Full pipeline (post-F17–F22, projected) | ~73 min |
| Tokens per full run | ~620 k |
| Cost per full run | ~$3–5 at sonnet rates |

The user-facing target is 10–15 min for simple single-resource (e.g. python-expert) and 60–120 min for complex multi-resource (e.g. iac-team). Both are achievable post-F17–F22.

### Per-phase wall-time baseline (iac-team, run #5 + #5i)

Sourced from run #5 (RESEARCH → GENERATE, full pipeline start at `21:38:00`) and run #5i (EVAL_DESIGN onward, resume run). The next post-F17–F22 smoke should be compared against this baseline.

| Phase | Observed (pre-F17–F22) | Projected (post-F17–F22) | Source of change |
|---|---|---|---|
| RESEARCH | 5 m 47 s | unchanged | — |
| DESIGN | 1 m 24 s | unchanged | — |
| QA | < 1 s (no-op) | unchanged | — |
| GENERATE | 31 m 43 s (concurrency = 4) | ~18 min | F18 (4 → 8) |
| EVAL_DESIGN | 9 m 38 s (architect, 54 scenarios) | unchanged | — |
| ITERATE round 1 | < 1 s (no-op; all resources at v=1) | unchanged | — |
| EXECUTION_EVAL r1 | 25 m 36 s (concurrency = 2) | ~14 min | F18 (2 → 4) |
| ITERATE round 2 (feedback) | 15 m 49 s (3 resources) | unchanged | — |
| EXECUTION_EVAL r2 | 12 m 53 s (13 of 18 resources re-evaluated; 10 redundantly) | ~3 – 5 min | F17 (skip unchanged) |
| VALIDATE | never reached | ~5 min | — |
| **Full pipeline** | **~107 min** (interpolating VALIDATE) | **~73 min** | — |

GENERATE dominates the pre-F17–F22 budget at ~30 % of wall time — 8-way concurrency is the largest single win. EXECUTION_EVAL r2 redundancy (re-evaluating identical files for 10 of 13 resources) was the second largest, fixed by F17's `last_evaluated_version` filter.

### Signal-quality issues that remain

| Problem | Detail | Mitigation |
|---|---|---|
| Pass-rate ties dominate | At `trials=1` and 3 scenarios per resource, both arms commonly saturate at 0.67 (2-of-3) and the gate promotes a flat tie as "promoted". | Multi-grader scenarios (F23) — same model call, N graders → richer signal. |
| Simple-threshold gate | `candidate ≥ baseline + 0` treats a flat tie as success. | Phase B bootstrap-CI gate on win rate, lower CI bound > 0.5. |
| 0/0 unwinnable resources | `iac-generator` (71 k tokens, 0/0) and `commands/iac` (0 turns, 0 tokens, vacuous tie) failed for resource-type-specific reasons. | F20 fixes the command case (architect prompt now forbids literal `/cmd` strings); F21 catches the rest after round 1 instead of looping. |
| Trajectory scenarios penalize content-only skills | A skill that's documentation rather than tool orchestration scores 0 on `tool_called: Glob` assertions. | Phase B can route trajectory scenarios by `resource_type`; trim trajectory share for content-skills. |
| VALIDATE phase has never run under load | Run #5i auto-killed before round-2 completion; no cross-resource coherence pass has executed in anger. | Next full smoke (with F17-F22) should reach VALIDATE; if it doesn't, raise the auto-shutdown deadline. |

### Where the eval design itself is the bottleneck

Several "tie at zero" or "saturate at 0.67" outcomes are scenario-design artifacts, not optimizer failures. The eval-architect agent produces a working schema-valid suite, but the scenarios it writes aren't always *discriminating* — they don't separate a good candidate from a bad baseline. This is the single biggest lever for improving signal quality, and it argues for the work in §4.

---

## 4. Open issues & future work

### Architectural

- **Eval as a distinct agent with isolated context (probably Opus).** The eval pipeline currently runs as part of the same conversation/context as the orchestrator; the architect agent is bounded by the orchestrator's overall turn budget. A separate eval-only agent with its own context window, model selection (Opus for rubric authoring quality), and isolated tool access would (a) free up the orchestrator's context, (b) let the architect think harder about discriminating scenarios, and (c) make eval reproducibility easier (separate inputs, separate logs).
- **Phase B — statistical promotion gate.** Bootstrap-CI on win rate, lower bound > 0.5 to promote. Token regression check. Trigger precision/recall over held-out set. Pairwise judge with position balancing.
- **Phase C — ephemeral container runtime.** Layered Dockerfile (`harness-base` → `harness-eval-base` → `harness-eval-instance`). `docker compose run --rm`, tmpfs workspace, pinned model per run. SWE-bench-style determinism target.
- **Phase D — judge calibration.** `make eval-calibrate` computes Cohen's kappa per `(resource_type × judge_model × rubric_version)`; gate refuses promotion when calibration is stale or < 0.8. Judge ensemble (haiku + sonnet + opus majority) when calibration is below threshold.

### Eval-design quality (biggest signal-quality lever)

- **Scenario discrimination.** Many scenarios pass on both arms or fail on both, producing flat outcomes. The architect prompt needs explicit guidance to author scenarios that *separate* baseline from candidate (e.g. scenarios that exercise documented improvements over the v0 file).
- **Scenario difficulty distribution.** Today 1 easy + 1 medium + 1 hard per resource at `trials=1` is too coarse; at `trials=3` the signal would smooth but the cost triples. Multi-grader scenarios (F23) get more bits per model call without scaling trials.
- **Two persistently broken resource types.** `commands/*` (F20 mitigates via natural-language prompt rewrite; long-term fix is to register workspace commands as plugin commands in the eval runtime). `agents/iac-generator` (scenarios unwinnable for both arms — needs rubric redesign or scenario simplification).

### Queued F-series defects

- **F23 — Multi-grader scenarios.** Schema + runner + architect changes so one model call can be scored by N graders. Targets 4× signal-per-dollar for content-evaluation skills.
- **F24 — Shared-generation graph.** Bipartite scenarios↔grader-pools for cross-scenario grader reuse. Discussion item; design after F23 validates the multi-grader model.
- **F1 (cosmetic, deferred).** `setup.sh` host-side tooling probe false-positives.
- **F5 (mitigated, deferred).** Hard-abort path on EVAL_DESIGN architect timeout; currently bandaided by raised budget.

### Validation gaps

- **VALIDATE has never run under load.** The cross-resource coherence pass (terminology drift, manifest correctness) exists but every full run so far auto-killed before reaching it.
- **F17–F22 are code-complete but not smoke-validated.** The expected post-fix wall-time drop (~107 → ~73 min) and per-cycle savings (~$1, ~300 k tokens) need a real run to confirm.
- **Full 54-scenario suite at `trials=3`.** Smoke uses `trials=1` for speed; production cadence is `trials=3`. Have not yet run the latter end-to-end.

---

## 5. Configuration reference

### Env vars

| Var | Default | Purpose |
|---|---|---|
| `CGF_MAX_ITERATIONS` | 3 | Max iter↔eval cycles per resource |
| `CGF_DESIGN_MODEL` | sonnet | Eval-architect model |
| `CGF_JUDGE_MODEL` | opus | Eval-judge model (override to sonnet for cost) |
| `CGF_EVAL_TOKEN_BUDGET` | 1 000 000 | Token ceiling per eval round |
| `CGF_EVAL_PROMOTION_EPSILON` | 0.0 | Simple-threshold gate margin |
| `CGF_EVAL_HELD_OUT_FRACTION` | 0.25 | Architect target for held-out share |
| `CGF_GENERATE_CONCURRENCY` | 8 | Parallel resource generation |
| `CGF_ITERATE_CONCURRENCY` | 4 | Parallel resource iteration |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 4 | Parallel per-resource eval |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | Parallel scenarios inside one resource's eval |
| `CGF_EVAL_TRIAL_TIMEOUT` | 180 | Per-trial cap (unit / e2e) |
| `CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT` | 300 | Per-trial cap (trajectory) |
| `CGF_ITERATE_TIMEOUT` | 1200 | Per-iteration wall-time cap |

### Phase-level timeouts

| Phase | Default | Env var |
|---|---|---|
| RESEARCH | 1800 s | `CGF_RESEARCH_TIMEOUT` |
| GENERATE | 900 s | `CGF_GENERATE_TIMEOUT` |
| ITERATE | 1200 s | `CGF_ITERATE_TIMEOUT` |
| VALIDATE | 300 s | `CGF_VALIDATE_TIMEOUT` |
| DESIGN | 900 s | (config-only) |
| EVAL_DESIGN | 1200 s | (config-only) |
| EXECUTION_EVAL | 1800 s | (config-only) |

### Pipeline caps

| Knob | Default | Source |
|---|---|---|
| `max_iterations` (per resource) | 5 | `CGF_MAX_ITERATIONS` |
| `max_refinements` (per resource, validate-loop) | 1 | `DEFAULT_MAX_REFINEMENT` |
| `max_validate_refinements` (pipeline) | 2 | `DEFAULT_MAX_VALIDATE_REFINEMENTS` |
| `max_feedback_iterations` (execution-eval loop-back) | 2 | `DEFAULT_MAX_FEEDBACK_ITERATIONS` |

---

## 6. How to run

```bash
make build                                          # only if Dockerfile changed
docker compose up -d --force-recreate main-agent    # to pick up src/ edits
make smoke FIXTURE=iac-team                         # full multi-resource pipeline
make smoke FIXTURE=python-expert                    # single-resource sanity
```

Inspect after:

- `workspace/<fixture>/sessions/optimization-state.json` — state machine
- `workspace/<fixture>/eval/` — eval artifacts
- `workspace/<fixture>/CHANGELOG.md` — narrative
- Grafana CGF dashboard at <http://localhost:3000/d/casdk-cgf>

### Resuming from existing state (skip workspace wipe)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T main-agent python -c "
from harness.optimization.multi_resource_orchestrator import run_multi_resource_optimization
import asyncio
result = asyncio.run(run_multi_resource_optimization('/workspace/iac-team', verbose=True))
print('Success!' if result.success else f'Failed: {result.error}')
"
```

### Reset state to a specific phase

```python
import json
state = json.load(open('workspace/iac-team/sessions/optimization-state.json'))
state['current_phase'] = 'EVAL_DESIGN'
state['phases_completed'] = ['RESEARCH', 'DESIGN', 'QA', 'GENERATE']
state['eval_suite_path'] = ''
state['eval_results_path'] = ''
state['feedback_history'] = []
state['validate_refinement_count'] = 0
for r in state['resources'].values():
    r['status'] = 'optimized'
    r['version'] = 1
    r['last_evaluated_version'] = 0  # F17: force re-eval
json.dump(state, open('workspace/iac-team/sessions/optimization-state.json', 'w'), indent=2)
```
