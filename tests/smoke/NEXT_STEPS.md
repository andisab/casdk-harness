# Smoke Test Validation Plan

## Status

| Phase | Status | Next |
|---|---|---|
| Phase 1 — `python-expert` single-resource | ✅ **PASSED** (run #7, commit `12633e9`) | Done |
| Phase 2 — `iac-team` multi-resource | 🟡 In progress (4 runs, last stopped early) | Implement F4 + F3 → run #5 |

**Immediate next action:** implement F4 (parallelize per-resource phases) + F3 (display counter fix), then launch run #5. F4 design sketch is below; estimated ~150–200 LoC production + 80–120 LoC tests; expected ~3.6× wall-time speedup.

**Branch state:** `phase-a-fixes` is N commits ahead of `contextgrad-eval` (run `git log contextgrad-eval..phase-a-fixes --oneline` to see). After F4/F3 + a passing run #5, merge to `contextgrad-eval` and push.

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
| `CGF_GENERATE_CONCURRENCY` | 4 | *(F4)* Parallel resource generation |
| `CGF_ITERATE_CONCURRENCY` | 4 | *(F4)* Parallel resource iteration |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 2 | *(F4)* Parallel per-resource eval |

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
| F3 | Progress display shows "0 tool calls" even when tools called | 🟡 Open — bundled with F4 |
| F4 | Per-resource phases sequential → 4-8h wall-time | 🟡 **Open — next to ship** (this doc, top section) |

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

After run #5 PASS:
```bash
git checkout contextgrad-eval
git merge phase-a-fixes
git push origin contextgrad-eval
```

---

## Between-session resumption

If context clears:

1. Read this file top-to-bottom.
2. `git log --oneline contextgrad-eval..phase-a-fixes` — see what's unmerged.
3. If F4 + F3 not yet shipped: follow F4's "Implementation order" section above.
4. Run `make smoke FIXTURE=iac-team` (run #5 validation).
5. If pass: assess against the Phase 2 pass criteria, then merge `phase-a-fixes` → `contextgrad-eval` + push.
6. If fail: new defect → file in the F-series ledger above, fix on `phase-a-fixes`, re-run.
