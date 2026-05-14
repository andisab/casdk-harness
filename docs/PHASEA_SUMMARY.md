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
| `phase-a-perf` | F17–F22 (skip-unchanged, concurrency bumps, per-level timeouts, command-prompt fix, unwinnable detector, subagent audit) | **Smoke-validated end-to-end** (run #6, 85m 06s wall time, exit 0) |

**Unit suite:** 1863 passing, 0 failing on `phase-a-perf` (1856 baseline + 7 new). Pre-existing path-issue errors in `test_eval_telemetry.py::TestEnvVarsExposed` are unrelated.

### What works end-to-end (validated under real load, run #6 — first full pipeline to COMPLETE)

- **All 9 pipeline phases reached COMPLETE** in a single run for the first time (run #6, 85m 06s). VALIDATE produced `coherence_score=0.93`. Previous runs were killed before reaching VALIDATE.
- **F17 skip-unchanged works perfectly.** EXECUTION_EVAL round 2 evaluated exactly 1 resource (pulumi-cdk, the only regression), saving ~14 redundant evals.
- **F21 unwinnable detector caught its first real case.** `agents/iac-analyzer` scored 0/0 across all 3 scenarios (1 trial timed out at 180s, 2 produced output but failed graders); F21 marked it `unwinnable` and excluded it from round 2.
- **F20 commands prompt fix delivered real signal.** `commands/iac` scored 0.33/0.33 with non-zero turns/tokens (vs vacuous 0/0 in run #5i where the literal `/iac` slash strings silently no-op'd).
- **Feedback loop recovers regressions.** pulumi-cdk regressed in round 1 (1.00 → 0.67 — candidate hit F19's 180s timeout on one scenario); ITERATE r2 produced a v2 that completed cleanly; round 2 promoted at 1.00/1.00.
- **Per-resource scenario attribution remains correct** (F13/F16).
- **Promotion gate fails closed** when every resource errors (F8).

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
| Per-resource generation | 4 – 11 min (avg ~5 min at 8-way) |
| EVAL_DESIGN (architect) | 6 – 10 min for 54 scenarios |
| Full pipeline (pre-F17–F22) | ~107 min (projected) |
| **Full pipeline (post-F17–F22, observed)** | **85 m 06 s** (run #6) |
| Tokens per full run (post-F17) | **451 k** (was ~620 k pre-F17; -27 %) |
| Cost per full run | ~$3 at sonnet rates |

The user-facing target is 10–15 min for simple single-resource (e.g. python-expert) and 60–120 min for complex multi-resource (e.g. iac-team). iac-team is now well inside the upper bound; python-expert path was not exercised in run #6.

### Per-phase wall-time (iac-team, observed in runs #5 + #5i vs run #6)

Run #6 is the first full pipeline to reach COMPLETE.

| Phase | Pre-F17–F22 | **Post-F17–F22 (run #6)** | Δ |
|---|---|---|---|
| RESEARCH | 5 m 47 s | **4 m 56 s** | −15 % |
| DESIGN | 1 m 24 s | **1 m 33 s** | +11 % |
| QA | < 1 s (no-op) | < 1 s | — |
| **GENERATE** (concurrency 4 → 8) | 31 m 43 s | **17 m 10 s** | **−46 %** |
| EVAL_DESIGN | 9 m 38 s | **6 m 27 s** | **−33 %** |
| ITERATE round 1 | not measured (run #5i resumed past it) | **33 m 09 s** | new baseline |
| **EXECUTION_EVAL r1** (concurrency 2 → 4) | 25 m 36 s | **10 m 43 s** | **−58 %** |
| ITERATE round 2 (feedback) | 15 m 49 s (3 resources) | **7 m 01 s** (1 resource) | — |
| **EXECUTION_EVAL r2** (F17 skip-unchanged) | 12 m 53 s partial (13 of 18, 10 redundantly) | **1 m 07 s** (1 of 17) | **−91 %** |
| **VALIDATE** | never reached | **3 m 01 s** | first-ever validation |
| **Full pipeline** | ~107 min (projected) | **85 m 06 s** | **−21 %** vs projection |

GENERATE remains the biggest single phase (now ~20 % of wall time, was ~30 %). EXECUTION_EVAL r2 went from second-biggest cost to negligible (1 m 07 s for 1 resource) — F17's `last_evaluated_version` filter eliminates redundant work entirely.

### Eval signal characteristics (run #6, trials = 1)

| Metric | Run #5i | **Run #6** | Notes |
|---|---|---|---|
| Resources evaluated | 18 round 1 + 11 round 2 = 21 unique | **17 round 1 + 1 round 2 = 17 unique** | F17 + F21 elimination |
| Real wins (Δ > 0) round 1 | 1 (container-analysis) | **1 (iac-generator: 0.00 → 0.33)** | first time iac-generator got real signal |
| Pure ties (b == c, both ≥ 0) round 1 | 13 of 18 | 13 of 17 | simple-threshold gate symptom |
| Round-1 regressions | 3 | **1 (pulumi-cdk)** | F19 trial timeout caught a slow candidate |
| Regressions recovered via feedback | 3 / 3 | **1 / 1** | feedback contract holds |
| Unwinnable (F21) | n/a (didn't exist) | **1 (iac-analyzer)** | 0/0 on all 3 scenarios; correctly skipped in round 2 |
| Total tokens (eval only) | 619 908 | **451 552** | −27 % via F17 + better scenario hits |
| Candidate pass-rate distribution (round 1) | mostly 0.67 / 0.67 | **8 × 1.00, 5 × 0.67, 3 × 0.33, 1 × 0.00** | scenarios now more discriminating |

The pass-rate distribution shifted up materially (8 resources at 1.00 in round 1 vs zero at 1.00 in run #5i). Two explanations: scenario quality is better (architect prompt evolved across runs), and the F18 concurrency raise gave each resource genuine API headroom.

### Signal-quality issues that remain

| Problem | Detail | Mitigation |
|---|---|---|
| Pass-rate ties dominate | 13 of 17 round-1 outcomes in run #6 were ties (e.g. 1.00 / 1.00); the simple-threshold gate calls these "promoted" despite zero improvement signal. | Multi-grader scenarios (F23) — same model call, N graders → richer signal. |
| Simple-threshold gate | `candidate ≥ baseline + 0` treats a flat tie as success. | Phase B bootstrap-CI gate on win rate, lower CI bound > 0.5. |
| 180 s timeout occasionally penalizes legitimate candidates | Run #6: `pulumi-cdk medium-component-01` (e2e level) candidate hit F19's 180 s cap with `turns=0 tokens=0`, regressed; ITERATE r2 produced a faster v2 that passed. Also `iac-analyzer hard-iac-assessment-01` (unit level) timed out on both arms, contributing to F21's unwinnable verdict. | Operator escape hatch via `CGF_EVAL_TRIAL_TIMEOUT` / `CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT`. Phase B should also surface scenario-level timeout patterns so the architect can mark a scenario as needing more time. |
| Trajectory scenarios penalize content-only skills | A skill that's documentation rather than tool orchestration scores 0 on `tool_called: Glob` assertions. | Phase B can route trajectory scenarios by `resource_type`; trim trajectory share for content-skills. |
| Unwinnable resources still consume tokens before being skipped | F21 only fires *after* round 1. `iac-analyzer` burned 13 k tokens in round 1 before being marked unwinnable; subsequent rounds skip it (F17 + F21 work together). | Acceptable for now — round-1 cost bounded; round-2+ cost zero. A pre-flight architect heuristic could pre-flag obviously-mismatched resource/scenario pairs. |

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

- **F25 — GENERATE timeout under 8-way concurrency.** Run #6: `skills/aws-eks/SKILL.md` GENERATE timed out at 905 s (5 s over `CGF_GENERATE_TIMEOUT=900`). The `context-engineer` subagent ran 27 turns with **0 tool_calls** — a planning loop without writing. Pre-fix run #5 finished this resource in 611 s at concurrency=4. Three working theories: (a) rate-limit tail-latency under 8-way fan-out pushes some resources past the cap; (b) the architect prompt for aws-eks induces a planning loop under contention; (c) random SDK hang. Next steps: instrument context-engineer to log when it spends > 60 s without a tool call; consider raising the GENERATE timeout to 1200 s OR lowering `CGF_GENERATE_CONCURRENCY` to 6 as a middle ground; investigate aws-eks prompt for ambiguity.
- **F23 — Multi-grader scenarios.** Schema + runner + architect changes so one model call can be scored by N graders. Targets 4× signal-per-dollar for content-evaluation skills.
- **F24 — Shared-generation graph.** Bipartite scenarios↔grader-pools for cross-scenario grader reuse. Discussion item; design after F23 validates the multi-grader model.
- **F1 (cosmetic, deferred).** `setup.sh` host-side tooling probe false-positives.
- **F5 (mitigated, deferred).** Hard-abort path on EVAL_DESIGN architect timeout; currently bandaided by raised budget.

### Validation gaps

- **~~VALIDATE has never run under load.~~** Cleared in run #6 (coherence_score = 0.93 in 3 m 01 s).
- **~~F17–F22 are code-complete but not smoke-validated.~~** Cleared in run #6 (85 m 06 s end-to-end, all six fixes observed working).
- **Full 54-scenario suite at `trials=3`.** Smoke uses `trials=1` for speed; production cadence is `trials=3`. Not yet run end-to-end — would 3× per-trial cost but smooth the pass-rate distribution.
- **F25 (aws-eks GENERATE timeout) reproducibility.** Single observation in run #6; need a follow-up run to determine if it's deterministic or rate-limit roulette.
- **VALIDATE refinement loop never exercised.** Coherence passed cleanly in run #6; the VALIDATE → ITERATE retry path (gated by `max_validate_refinements = 2`) has not yet fired under load.

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
