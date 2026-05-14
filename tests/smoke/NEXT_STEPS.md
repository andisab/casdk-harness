# Smoke Test Validation Plan

## Status

| Phase | Status | Next |
|---|---|---|
| Phase 1 — `python-expert` single-resource | ✅ **PASSED** (run #7, commit `12633e9`) | Done |
| Phase 2 — `iac-team` multi-resource | 🟢 **Run #5i in flight** — F3/F4/F5/F6/F7/F8/F9/F10/F11/F12/F13/F14/F15/F16 all shipped | Wait for #5i COMPLETE → close-out |

**Immediate next action:** monitor run #5i (task `bra22wyod`, log `/tmp/smoke-run5i.log`). EVAL_DESIGN completed at 9m 38s (54 scenarios, F14 self-contained), ITERATE no-op (F11 working), EXECUTION_EVAL just started with `target_key=skills/aws-cli/SKILL.md scenarios=3 scenarios_in_suite=54` — confirming **F13 filter + F16 workspace-root resolution both working under real load**. First end-to-end run with correctly attributed per-resource scenarios.

**Branch state:** `phase-a-fixes` ~15 commits ahead of `contextgrad-eval`. **1856 unit tests passing** (118 new across F3/F4/F6/F7/F8/F9/F10/F11/F12/F13/F14/F15/F16). On run #5i pass: docs pass → squash commit → merge to `contextgrad-eval` → push.

---

## Session-accomplished summary (phase-a-fixes branch)

Started session at "F4 + F3 ready to ship, smoke run #5 next." Through runs #5 → #5i, surfaced and fixed **14 distinct defects** spanning the pipeline from prompt-engineering to harness internals to architectural parallelism. End state: first pipeline run with correctly-attributed per-resource eval underway.

### Defects shipped this session

| ID | Severity | Root cause | Fix |
|---|---|---|---|
| F3 | P2 cosmetic | `extract_tool_info()` returned only first tool_use block per AssistantMessage | New `extract_tool_calls()` returns full list; subagent loop iterates |
| F4 | P0 perf | Per-resource phases ran strictly sequential | `asyncio.gather` + semaphore in generate/iterate/execution_eval; `_state_lock` for state writes |
| F5 | P1 latent | EVAL_DESIGN silently advanced on architect timeout | Raised timeout 600→1200s; hard-abort still TODO |
| F6 | P1 perf | ITERATE 600s too tight for ~2000-line SKILLs (15 timeouts in run #5b) | Default raised to 1200s |
| F7 | P0 correctness | Eval-architect produced schema-invalid flat `tool_called` graders | Rewrote prompt with nested-trajectory shape + field-name precision section (`text:` not `rule:`) |
| F8 | P0 correctness | Promotion gate failed-OPEN: `regressions=[] → "all promoted" → advance`, even when every resource errored | Added `harness_errors` list parallel to regressions; require `promotions > 0`; raise on all-errored; fixed `eval_phase_span` over-catch |
| F9 | P1 robustness | VALIDATE → ITERATE loop ran 3 rounds in run #5b — versioned-path lookup bypassed per-resource refinement cap | Strip `-v{N}` before lookup + new pipeline-level `max_validate_refinements=2` cap |
| F10 | P0 correctness | `_invoke_from_resource` raised `'NoneType' object is not iterable` for every scenario (SDK couldn't iterate `allowed_tools=None`) | Pass `tools or []`; mirror subagent F2 wiring — `plugins=[]`, `skills="all"`, `setting_sources=["project"]` |
| F11 | P1 resumability | EVAL_DESIGN silently skipped when resources at `status=optimized` (resume scenario) | Filter widened: any non-failed resource is eligible |
| F12 | P0 perf | `EvalHarness.run` iterated scenarios serially within each resource — 54 × 30s = 27 min per arm | `asyncio.gather` + `CGF_EVAL_SCENARIO_CONCURRENCY=6` semaphore over scenarios; arms parallel inside `run_scenario` |
| F13 | P0 correctness | Every resource ran all 54 scenarios (architect designed 3-per-resource but harness ignored `target_resource`) — 0.40-vs-0.40 cross-resource ties everywhere | `_filter_scenarios_for_resource()` + `_resource_target_key()` with `-v{N}` strip |
| F14 | P0 correctness | Architect designed scenarios referencing `/sample-app` that doesn't exist in eval sandbox; agents reasonably refused; trajectory graders saw 0 tool calls → unwinnable | Prompt rewrite: every scenario must be self-contained via inline content OR `setup.files` (sandbox-relative paths) |
| F15 | P1 telemetry | `TranscriptBuilder` used `getattr(usage, "input_tokens", 0)` on a dict-shaped `usage` field → `total_tokens=0` always | Dict access with `usage.get(...)` + fallback aliases (`prompt_tokens`, etc.); typed-object branch retained for forward-compat |
| F16 | P0 correctness | `_resource_target_key` workspace-root detection picked per-resource `sessions/` dirs as root → `target_key="SKILL.md"` (bare filename) → F13 filter matched nothing → 0 scenarios per resource | Switched marker from `sessions/`/`eval/` to `SPEC.md` / `.claude-plugin/` / `resource-plan.yaml` |

### Test coverage added

- **F3** — 12 tests for `extract_tool_calls` (multi-block, text mix, truncation)
- **F4** — 23 tests for env-var concurrency, semaphore caps, lock serialization, exception isolation
- **F6** — 1 default-value test
- **F7** — runtime smoke only (prompt change)
- **F8** — 4 tests (2 source-inspection, 2 updated integration)
- **F9** — 13 tests (versioned-path strip, state field roundtrip, cap-config)
- **F10** — 5 tests (allowed_tools=[] not None, plugins/skills/setting_sources wiring)
- **F11** — 3 tests (optimized resources eligible, all-failed skip, no resources skip)
- **F12** — 11 tests (env resolver, semaphore caps, arm parallelism, source contract)
- **F13** — 11 tests (filter contract, suite-default inheritance, source wiring) — updated for F16
- **F15** — 7 tests (dict/typed-object/aliases/empty/None)
- **F16** — folded into F13 test class with regression case (nested sessions/ dirs)

**Total: ~90 new unit tests on top of baseline ~1740; full suite 1856 passing, 0 failing, 10 pre-existing unrelated errors.**

### Run history

| Run | Branch state | Outcome |
|---|---|---|
| #5 (`blrm3pgy6`) | F4+F3 only | EVAL_DESIGN timeout (F5) + ITERATE timeouts (F6) — killed after 2h |
| #5b (`b39dqzhai`) | + F5/F6 mitigations + slim architect prompt | EXECUTION_EVAL hit F7 schema bug for all 54 scenarios; F8 silently advanced with promoted=0; VALIDATE looped 3 rounds via F9 — killed after 2h 3m |
| #5c (`brb9z3ydh`) | + F7/F8/F9 (eval-suite patched in-place rule→text) | Confirmed F4 parallelism end-to-end (32 min GENERATE for 18 resources, 3.4× speedup). Hit F10 (NoneType in every scenario) — all 0-vs-0 ties; killed after 4h |
| #5d (`brt99tgm2`) | + F10 | Pipeline blasted through EVAL_DESIGN+ITERATE+EXECUTION_EVAL in 0 seconds (silent skip per F11) — killed |
| #5e (`by1ihn3d2`) | + F11 (eval-architect ran), no parallelism yet | EVAL_DESIGN 6m, EXECUTION_EVAL ran sequentially — 30s per single SDK call, projecting 8h total; killed for F12 |
| #5f (`bg5c4nu7z`) | trials=1 (no F12 yet) | Still serial inside resource; killed for F12 + suite-trim |
| #5g (`b0fnqfziw`) | + F12 (scenario parallel) + trimmed 5-scenario suite | First real non-zero pass rates! 13 promoted + 3 regression in ~7 min. But **all results were noise** — F13 surfaced (every resource ran all 5 scenarios regardless of target). Killed at 16/18 |
| #5h (`bnfb5myze`) | + F13/F14/F15 | F13 filter found 0 applicable scenarios for EVERY resource (target_key=`SKILL.md` bare) — F16 surfaced. Killed |
| **#5i (`bra22wyod`)** | + F16 | **In flight** — EVAL_DESIGN 9m 38s, F13/F16 confirmed working (`target_key=skills/aws-cli/SKILL.md scenarios=3 scenarios_in_suite=54`). EXECUTION_EVAL just started. |

### Cost so far (approximate)

Across runs #5 through #5i: estimated $30–50 of LLM spend. Most was burned on runs #5/#5b/#5c which ran for 2-4 hours each before defects surfaced. Runs #5d through #5i were short (5-15 min each) as defects were caught earlier.

---

---

## F4 — Parallelize per-resource phases (next to ship)

### Problem

Run #4 (post-F2-fix) confirmed the per-resource phases work but are sequential at 6–10 min per resource × 18 resources, projecting **4–8 hours** total wall-time for the iac-team fixture. The phases are I/O-bound (waiting on Claude API), so `asyncio` parallelism is the right fit.

### Target

```python
# generate.py pseudo-code
sem = asyncio.Semaphore(CGF_GENERATE_CONCURRENCY)  # default 4

async def _generate_one(resource):
    async with sem:
        try:
            await _generate_single_resource(resource)
        except Exception as exc:
            self._record_failure(resource, exc)  # isolate per-resource

await asyncio.gather(*[_generate_one(r) for r in pending])
```

### Affected files

| File | LoC | Loop |
|---|---|---|
| `_orchestrator_phases/generate.py` | 520 | per-resource for-loop |
| `_orchestrator_phases/iterate.py` | 769 | per-resource for-loop + inner refinement while-loop |
| `_orchestrator_phases/execution_eval.py` | 517 | per-resource baseline + candidate runs |

### Design decisions

1. **Concurrency cap, not unbounded** — `CGF_GENERATE_CONCURRENCY=4` (env, default 4). 18-way risks 429s.
2. **Per-resource isolation** — each coroutine catches its own exceptions; one failure must not poison the gather batch.
3. **State writes need a lock** — `asyncio.Lock()` wrapping `_state.update_resource()` + `_save_state()`.
4. **Metrics + tracer + cost telemetry** — already async-safe (Prometheus client, OTel). No changes.
5. **Per-call timeout stays per-call** — semaphore caps concurrency, not makespan. Worst-case: `ceil(18/4) × 10 min = 50 min` vs 180 min sequential.
6. **Phase ordering unchanged** — GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE; only the per-resource loops inside each phase parallelize.
7. **D9 retry covers rate-limit storms** under 4-way; if persistent, lower the env var.
8. **No FS write conflicts** — each resource writes to its own subdirectory.
9. **`plugin.json` is generated once, after the loop** — no race.

### Config knobs

| Var | Default | Range |
|---|---|---|
| `CGF_GENERATE_CONCURRENCY` | 4 | 1–8 |
| `CGF_ITERATE_CONCURRENCY` | 4 | 1–8 |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 2 | 1–4 (eval is more expensive) |

`=1` everywhere is the kill-switch back to sequential.

### Implementation order

1. Extract `_generate_single_resource()` async helper from generate.py's for-loop body (~40 LoC, no behavior change). Verify with existing tests.
2. Add `_state_lock = asyncio.Lock()` to `MultiResourceOrchestrator.__init__`.
3. Wrap state writes in the lock across all 3 phase files (~10–15 sites; `git grep '_save_state'`).
4. Convert generate.py outer loop to `asyncio.gather` with semaphore (~25 LoC).
5. Repeat for iterate.py and execution_eval.py (inner loops stay sequential within each coroutine).
6. Unit tests for the new helpers (mock LLM, verify gather + lock contention).
7. Smoke run on iac-team at `CGF_GENERATE_CONCURRENCY=4`.

### Risks

| Risk | Mitigation |
|---|---|
| State-write races | `asyncio.Lock` on every `_save_state()`; explicit unit test |
| Rate-limit storms (429) | D9 retry already handles; lower concurrency env var if persistent |
| OTel span ordering looks weird | Spans intrinsically parented; add `resource_path` attribute for filtering |
| One slow resource holds a slot for 15 min | Acceptable — bounded by semaphore, not makespan |

---

## F3 — Display counter fix (bundled with F4)

`agent_progress.py:extract_tool_info()` counts only Task / Skill toward the `tool_calls` shown in progress output. Should also count Read / Write / Edit / Bash. Result: all agents log "0 tool calls" even when they ran fine. ~10 LoC. Pure display bug — no functional impact.

---

## Pre-flight for run #5

1. F4 + F3 implementation complete; unit tests green
2. `make build` only if Dockerfile changed (likely not for F4)
3. `docker compose up -d --force-recreate main-agent` to pick up Python edits from volume-mounted `/app/src`
4. Confirm `.env` budget knobs:
   - `CGF_MAX_ITERATIONS=2`
   - `CGF_DESIGN_MODEL=sonnet`
   - `CGF_JUDGE_MODEL=sonnet`
   - `CGF_EVAL_TOKEN_BUDGET=2000000`
   - `CGF_GENERATE_CONCURRENCY=4` *(new, from F4)*
5. Open Grafana: <http://localhost:3000/d/casdk-cgf>
6. `make smoke FIXTURE=iac-team`

**Expected:** ~60–90 min wall-time (vs 4–8 h sequential), $3–8 cost.

---

## Phase 2 pass criteria (target for run #5)

A successful run produces:

1. `workspace/iac-team/eval/eval-suite.yaml` — generated by cgf-eval-architect, validates against `eval_suite.schema.json`
2. `workspace/iac-team/eval/execution-eval-round-*.json` — per-arm results across all 18 resources
3. `workspace/iac-team/eval/transcripts/baseline/` and `…/candidate/` populated
4. Per-resource `eval/results/{resource}-v1/eval-results.json`
5. State machine reaches `current_phase: COMPLETE` with all 18 resources in `optimized` / `needs_refinement` / `failed` (no stuck-in-progress)
6. At least one resource exhibits successful PROMOTE or feedback-loop-back to ITERATE — exercises both `_should_promote` branches
7. Grafana CGF dashboard: all five Phase A panels populated
8. No `[error]`-level log lines indicating contract violations from Phase-1 hardening (baseline-hash, iter↔eval pairing, signal watchdog)

### Assessment after run #5

1. **Did eval-architect pick reasonable graders?** Count grader types per resource in `eval-suite.yaml`. If everything is `llm_judge`, architect prompt needs tuning.
2. **Did the gate fire on both branches?** Check that at least one resource was rejected and at least one promoted (or accept that the baselines are uniformly bad/good and document why).
3. **Did the feedback loop fire?** `feedback_history` length > 0 in `optimization-state.json`.
4. **All five `harness_eval_*` Prometheus instruments populated?** If one missing, wiring defect.
5. **F4 parallelism actually delivered the speedup?** Compare wall-time to projection.

---

## Configuration matrix (env vars currently used)

| Var | Default | Purpose |
|---|---|---|
| `CGF_MAX_ITERATIONS` | 3 | Max iter↔eval cycles before forced terminal (Phase 1 + multi-resource) |
| `CGF_BASELINE_HASH_CHECK` | 1 | Enforce original-file protection |
| `CGF_SIGNAL_STRICT` | 0 | Hard-fail on signal-watchdog violations |
| `CGF_CALL_RETRIES` | 3 | Transient SDK retry attempts |
| `CGF_CALL_RETRY_BACKOFF` | 5.0 | Exponential backoff base (s) |
| `CGF_DESIGN_MODEL` | sonnet | Eval-architect model |
| `CGF_JUDGE_MODEL` | opus | Eval-judge model (override to sonnet for cost) |
| `CGF_EVAL_TOKEN_BUDGET` | 1_000_000 | Token ceiling per eval round |
| `CGF_EVAL_PROMOTION_EPSILON` | 0.0 | Simple-threshold gate margin (Phase B replaces) |
| `CGF_GENERATE_CONCURRENCY` | 4 | *(F4)* Parallel resource generation |
| `CGF_ITERATE_CONCURRENCY` | 4 | *(F4)* Parallel resource iteration |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 2 | *(F4)* Parallel per-resource eval |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | *(F12)* Parallel scenarios inside EvalHarness.run |
| `CGF_ITERATE_TIMEOUT` | 1200 | *(F6)* Per-iteration timeout (raised from 600) |

### Phase-timeout defaults (also env-overridable)

| Phase | Default timeout | Env var |
|---|---|---|
| RESEARCH | 1800s (30 min) | `CGF_RESEARCH_TIMEOUT` |
| GENERATE | 900s (15 min) | `CGF_GENERATE_TIMEOUT` |
| ITERATE | 1200s (20 min) — F6 | `CGF_ITERATE_TIMEOUT` |
| VALIDATE | 300s (5 min) | `CGF_VALIDATE_TIMEOUT` |
| DESIGN | 900s (15 min) | (config-only) |
| EVAL_DESIGN | 1200s (20 min) — F5 mitigation | (config-only) |
| EXECUTION_EVAL | 1800s (30 min) | (config-only) |

### Pipeline-level caps

| Knob | Default | Source |
|---|---|---|
| `max_iterations` (per resource) | 5 | `CGF_MAX_ITERATIONS` env |
| `max_refinements` (per resource, validate-loop) | 1 | `DEFAULT_MAX_REFINEMENT` |
| `max_validate_refinements` (pipeline, F9) | 2 | `DEFAULT_MAX_VALIDATE_REFINEMENTS` |
| `max_feedback_iterations` (execution-eval loop-back) | 2 | `DEFAULT_MAX_FEEDBACK_ITERATIONS` |

---

## Defect ledger (history)

### Runs #1-2 — pre-rebuild defects (D1–D11, all resolved)

| # | Defect | Status |
|---|---|---|
| D1 | Plugin discovery missed swe-marketplace | ✅ Run #1 → rebuild |
| D2 | EVAL_DESIGN unreachable | ✅ D1 symptom |
| D3 | "Success!" with 0 candidates | ✅ Orchestrator returns error |
| D4 | VALIDATE misleading score with no candidates | ✅ `b5eed9b` — early-skip |
| D5 | `CGF_MAX_ITERATIONS` ignored in multi-resource | ✅ `b5eed9b` — env-var read |
| D6 | Smoke metrics not in Prometheus | ✅ Rebuild |
| D7 | SDK OTel metrics not in Prometheus | ✅ Rebuild |
| D8 | Image missing helm/tfsec/trivy/kubeconform | ✅ `b5eed9b` + `914cad4` (dropped tfsec) + `2fff7ca` (added kubectl/terraform) |
| D9 | No retry on transient SDK errors | ✅ `b5eed9b` — backoff retry in `call_agent_simple` |
| D10 | Misleading "error result: success" | ✅ `b5eed9b` — `classify_sdk_error()` |
| D11 | Generated SKILL.md 75% smaller than baseline | ✅ `b5eed9b` — size guard + "PRESERVE BASELINE DEPTH" prompt |

### Runs #3-4 — post-rebuild defects (F1–F4)

| # | Defect | Status |
|---|---|---|
| F1 | `setup.sh` host-side tooling probe false-positives | 🟡 Open (cosmetic) |
| F2 | `context-engineer` 31 turns / 0 tool calls / 15 min timeout — Skill/Task tools not granted; SDK plugins/skills not wired into standalone calls | ✅ `800f20f` (harness) + swe-marketplace `2376404` — 6 agent tool-grants + `subagent.py` SDK wiring |
| F3 | Progress display shows "0 tool calls" even when tools called | ✅ `agent_progress.py:extract_tool_calls()` returns ALL tool_use blocks (was first-only) + `subagent.py` iterates the list. 12 unit tests. |
| F4 | Per-resource phases sequential → 4-8h wall-time | ✅ generate.py / iterate.py / execution_eval.py parallelized via `asyncio.gather` + `Semaphore`; `MultiResourceOrchestrator._state_lock` serializes state writes; 23 unit tests. |

### Runs #5 → #5i — eval-pipeline defects (F5–F16)

| # | Defect | Status |
|---|---|---|
| F5 | EVAL_DESIGN silently advances on architect timeout | 🟡 Mitigated (timeout 600→1200) — hard-abort path still TODO for future Phase B work |
| F6 | ITERATE 600s timeout too tight for ~2000-line SKILLs (15 timeouts in run #5b) | ✅ Default `iterate_timeout` raised 600→1200 in `MultiResourceConfig`; 1 default-value test |
| F7 | Eval-architect produced flat `type: tool_called` graders, schema-invalid for all 54 scenarios | ✅ Rewrote architect prompt with nested-trajectory shape + field-name precision section (`text:` not `rule:`, `before:`/`after:` not `first:`/`second:`) |
| F8 | Promotion gate failed-OPEN: `regressions=[]` from all-errored run was treated as "all promoted, advance to VALIDATE" | ✅ Added `harness_errors` list parallel to regressions; gate requires `not regressions AND not harness_errors AND promotions > 0`; new abort path on all-errored; fixed `eval_phase_span` over-catch that was wrapping user exceptions. 4 tests. |
| F9 | VALIDATE → ITERATE looped 3 rounds in run #5b — versioned-path lookup bypassed per-resource refinement cap | ✅ Strip `-v{N}` suffix before state lookup + new pipeline-level `max_validate_refinements=2` cap. 13 tests + state-field roundtrip. |
| F10 | `_invoke_from_resource` raised `'NoneType' object is not iterable` for every scenario (SDK couldn't iterate `allowed_tools=None` for skills with no `tools:` frontmatter) | ✅ Pass `tools or []`; add F2 wiring: `plugins=[]`, `skills="all"`, `setting_sources=["project"]`. 5 tests. |
| F11 | EVAL_DESIGN silently skipped when resources at `status=optimized` (resume scenario produced no eval-suite) | ✅ Filter widened from `get_generated_resources()` to "any non-failed resource". 3 tests. |
| F12 | `EvalHarness.run` iterated scenarios serially within each resource — 54 × 30s = 27 min per arm → 8h projected | ✅ `asyncio.gather` + `CGF_EVAL_SCENARIO_CONCURRENCY=6` semaphore over scenarios; baseline + candidate arms parallel inside `run_scenario`. 11 tests. |
| F13 | Every resource ran ALL 54 scenarios (architect designed 3-per-resource but harness ignored `target_resource`) — 0.40-vs-0.40 cross-resource ties everywhere | ✅ `_filter_scenarios_for_resource()` matches scenario's effective `target_resource` (per-scenario override OR suite default) against candidate's normalized path. 11 tests. |
| F14 | Architect designed trajectory scenarios referencing `/sample-app` that doesn't exist in eval sandbox; agents reasonably refused; trajectory graders penalized 0 tool_calls | ✅ Prompt rewrite with dedicated "Self-contained scenarios" section: every scenario MUST be self-contained via inline content OR `setup.files` (sandbox-relative paths, no `..` or absolute). Anti-pattern section explicitly forbids absolute paths in prompts. |
| F15 | `TranscriptBuilder` used `getattr(usage, "input_tokens", 0)` on a dict-shaped `usage` field → `total_tokens=0` in every trial | ✅ `isinstance(usage, dict)` branch with `usage.get(...)` and fallback aliases (`prompt_tokens`/`completion_tokens`/`input_token_count`). Typed-object branch retained for forward-compat. 7 tests. |
| F16 | `_resource_target_key` workspace-root detection picked per-resource `sessions/` dirs as root → `target_key="SKILL.md"` (bare filename) → F13 filter matched nothing → 0 scenarios per resource | ✅ Switched marker hierarchy to `SPEC.md` → `.claude-plugin/` → `resource-plan.yaml`. Pre-F16 markers (`sessions/`, `eval/`) appear nested inside resource dirs and falsely matched. Added regression test for nested-sessions/ scenario. |

### Phase 1 hardening (P0–P1, all shipped in `12633e9`)

Baseline-hash check, pair-wise iter↔eval contract, configurable iteration cap, review-on-disk + RECOMMENDATION parser, signal watchdog, XML directive contract, orchestrator + evaluator prompt rewrites, 40 new unit tests. Full breakdown in commit `12633e9` message.

---

## How to run

```bash
make build                                          # only if Dockerfile changed
docker compose up -d --force-recreate main-agent    # to pick up src/ edits
make smoke FIXTURE=iac-team                         # full pipeline
make smoke FIXTURE=python-expert                    # single-resource sanity
```

Inspect after:
- `workspace/iac-team/sessions/optimization-state.json` — state machine
- `workspace/iac-team/eval/` — eval artifacts
- `workspace/iac-team/CHANGELOG.md` — narrative
- Grafana CGF dashboard — telemetry

---

## Branch / merge strategy

`phase-a-fixes` lands on `contextgrad-eval` once each milestone has at least one real-LLM validation. All Phase 2 work stays on `contextgrad-eval` — no mirror to `main` planned.

### Close-out sequence (when run #5i passes)

1. **Quick python-expert smoke** — regression check that the single-resource path still works after all 14 fixes:
   ```bash
   make smoke FIXTURE=python-expert
   ```
2. **Documentation updates** — confirm `CLAUDE.md` "Completed Recently" section + `memory/MEMORY.md` reflect F3-F16.
3. **Single squash commit** to `phase-a-fixes`:
   ```bash
   git checkout phase-a-fixes
   # Stage all session changes
   git add -A
   git commit -m "fix(cgf): Phase-A end-to-end fixes (F3-F16, 14 defects)"
   ```
4. **Merge to `contextgrad-eval`**:
   ```bash
   git checkout contextgrad-eval
   git merge phase-a-fixes
   git push origin contextgrad-eval
   ```
5. Leave `phase-a-fixes` as-is for reference.

### Still deferred (next branch)

- **F1** (host-side tooling probe false-positives) — cosmetic
- **F5** hard-abort path on EVAL_DESIGN timeout (currently mitigated by raising budget)
- **Phase B** statistical promotion gate (bootstrap-CI on win rate)
- **Phase C** ephemeral runtime (`docker compose run --rm` per eval)
- **Phase D** judge calibration + multi-judge ensemble
- Full 54-scenario suite at trials=3 (currently trials=1 for smoke speed)

---

## Between-session resumption

If context clears mid-session:

1. Read this file top-to-bottom (status table at top tells you where we are).
2. `git log --oneline contextgrad-eval..phase-a-fixes` — see what's unmerged.
3. Active run? `tail /tmp/smoke-run5*.log` (latest letter suffix).
4. Defect ledger above shows what's shipped; **assume the current run is in flight at the latest letter** unless logs show otherwise.
5. If run #5i is still pre-COMPLETE: monitor + close out per "Close-out sequence" above when it lands.
6. If run #5i failed with a new defect: file it in the F-series ledger, fix on `phase-a-fixes`, re-run.

### Smoke fixture sanity

```bash
make smoke FIXTURE=iac-team          # full multi-resource pipeline
make smoke FIXTURE=python-expert     # single-resource sanity check
```

### Direct orchestrator invocation (for resume scenarios)

When `make smoke` would re-wipe the workspace and you want to resume from existing state:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T main-agent python -c "
from harness.optimization.multi_resource_orchestrator import run_multi_resource_optimization
import asyncio
result = asyncio.run(run_multi_resource_optimization('/workspace/iac-team', verbose=True))
print('Success!' if result.success else f'Failed: {result.error}')
"
```

To reset state to a specific phase (e.g., re-run EVAL_DESIGN with existing v1 files):
```python
import json
state = json.load(open('workspace/iac-team/sessions/optimization-state.json'))
state['current_phase'] = 'EVAL_DESIGN'  # or EXECUTION_EVAL, etc.
state['phases_completed'] = ['RESEARCH', 'DESIGN', 'QA', 'GENERATE']
state['eval_suite_path'] = ''
state['eval_results_path'] = ''
state['feedback_history'] = []
state['validate_refinement_count'] = 0
for r in state['resources'].values():
    r['status'] = 'optimized'  # F11 accepts; ITERATE no-ops
    r['version'] = 1
json.dump(state, open('workspace/iac-team/sessions/optimization-state.json', 'w'), indent=2)
```
