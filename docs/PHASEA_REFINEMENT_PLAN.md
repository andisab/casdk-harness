# Phase A Refinement — Implementation Plan

Branch: `cgf-eval-ab`. Companion to [PHASEA_SUMMARY.md § 4](./PHASEA_SUMMARY.md#4-phase-a-refinement-plan) (the canonical refinement description) and the industry research notes captured during the Phase A retrospective.

This document is the **engineering plan**: concrete files, symbols, ordering, smoke checkpoints. It does not re-argue the *why* — that's settled in PHASEA_SUMMARY § 4.

---

## Scope reminder

The four refinements sharpen **gate semantics**. None reshape the 9-phase topology.

1. **4.1** Eval-agent isolation — prove and harden the separation between architect / judge / optimizer.
2. **4.2** Dual baseline — `baseline_floor` (one-shot sanity check) + `baseline_incumbent` (recurring promotion gate).
3. **4.3** Cost as a first-class gate — two-gate (quality AND cost), never weighted sum.
4. **4.4** Pipeline tightening — eval-suite hash, stagnation early-stop, held-out bookkeeping.

---

## Step 0 — Pre-flight (~30 min, no code)

1. **Baseline snapshot.** Copy `workspace/iac-team/eval/execution-eval-round-*.json` + per-resource `eval-results.json` into `docs/baselines/run-6/` so post-refinement smokes (run #7, #8, #9) are diffable.
2. **Decision ledger.** Record the locked-in values for this branch in this doc's § "Decisions" below (judge model, design model, gate tolerances). The branch is a single experimental control; model swaps mid-branch invalidate the comparison.
3. **Acceptance criterion.** After each step, `make smoke FIXTURE=iac-team` must (a) reach COMPLETE within 60–120 min, (b) produce ≥1 real promotion (Δ > 0), (c) emit all `harness_eval_*` Prom series.

---

## Step 1 — Refinement 4.1: Eval-Agent Isolation

Highest leverage. Everything downstream assumes a clean gate.

### Audit + harden (most isolation is already true; this step **proves it** and locks in artifacts)

| File | Change |
|---|---|
| `src/harness/optimization/graders/llm_judge.py` | Add `_resolve_judge_model()` WARN log when `CGF_JUDGE_MODEL` resolves to the same model as `CGF_DESIGN_MODEL` (self-preference risk). |
| `src/harness/optimization/graders/llm_judge.py::_build_user_prompt` | Add docstring/assert that prompt body contains only `rubric + transcript.final_output + turn/tool counts`. No orchestrator state. |
| `src/harness/optimization/graders/transcript.py` | Capture `ResultMessage.total_cost_usd` and `model_usage` (already-present SDK fields). New `AgentTranscript.total_cost_usd: float`. Used by Step 3 cost gate. |
| `src/harness/optimization/eval_harness/models.py` | Add to `EvalResults`: `judge_model_id: str`, `judge_prompt_hash: str`, `total_cost_usd: float`. Surface in `to_dict()`. Recorded once per run so Phase D Cohen's-κ has stable keys. |
| `src/harness/optimization/eval_harness/runner.py::_assemble_results` | Plumb judge model + prompt hash + total cost up from grader / trial layer. |
| `src/harness/optimization/_orchestrator_phases/eval_design.py` | Lock the eval-architect prompt's inputs to {SPEC, resource-plan, eval_criteria, resource file paths}. No optimizer rationale, no iteration count, no version. Add comment. |

### Tests (new)

- `tests/unit/test_optimization/test_eval_isolation.py`
  - judge prompt is built from `rubric + transcript` only — no orchestrator state, no version, no diff
  - `EvalResults.judge_model_id` populated and matches `CGF_JUDGE_MODEL` resolution
  - `EvalResults.judge_prompt_hash` is deterministic for the same (rubric, transcript)
  - WARN log fires when judge == design model

### Risk

Low. Most isolation is already correct; we're proving it and emitting artifacts.

### Smoke

`make smoke FIXTURE=python-expert` (cheap), then `make smoke FIXTURE=iac-team`. Confirm baselines/run-6 budget held.

---

## Step 2 — Refinement 4.2: Dual Baseline Gate

### Floor semantics (revised — simpler than original draft)

- `baseline_floor` is **one-shot per resource** at the moment v1 is trying to become the first incumbent.
- Once we have any promoted version, the floor is irrelevant. Subsequent rounds compare candidate to `baseline_incumbent` only.
- **Model is never changed mid-branch.** That's the experimental control. If a user bumps `CLAUDE_MODEL` between runs, that's a new experiment; cached floor results are invalidated by the cache key.
- Floor cost is therefore bounded: **at most one floor arm per resource per branch**. No "cadence" knob.

### What changes

| File | Change |
|---|---|
| `src/harness/progress.py::ResourceStatus` | Add `last_promoted_version: int = 0`. The orchestrator uses this to detect the "first-time promotion" regime. |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py` | Replace `_resolve_baseline_path` with `_resolve_baselines(resource) -> (floor_path \| None, incumbent_path)`. Return `floor_path` only when `last_promoted_version == 0`. |
| New: `src/harness/optimization/_orchestrator_phases/_baseline_floor.py` | Build a synthetic "bare model" resource file at runtime: empty system prompt body, frontmatter preserves `model` + `name`. Materialized to a tempdir per scenario invocation (same lifecycle as scenario setup). |
| `src/harness/optimization/eval_harness/runner.py::EvalHarness.run()` | New optional `baseline_floor: Path \| None`. When present, run a third arm sequentially (after the incumbent arm) and attach to results. |
| `src/harness/optimization/eval_harness/models.py` | `EvalResults.floor: SubsetStats \| None`. `ScenarioResult.floor: ArmResults \| None`. |
| New: `src/harness/optimization/gating.py` | `Gate.decide(candidate, incumbent, floor=None, epsilon=0.0) -> Verdict`. Two-stage when floor present: (1) `candidate ≥ floor + 2ε` (first-promotion margin), (2) `candidate ≥ incumbent + ε`. When floor is None: just stage (2). Verdict = `Literal["promote", "refine", "reject_floor"]`. |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py::_should_promote` | Delegate to `Gate.decide()`. Update promotion path to set `last_promoted_version = resource.version`. |
| `src/harness/optimization/eval_harness/aggregate.py::compare_arms` | When candidate and baseline both pass, prefer arm with lower `total_cost_usd` within a 10% band; below band = tie. Cheap length-control approximation (Dubois 2024). Phase B does the rigorous regression. |

### Tests

- `tests/unit/test_optimization/test_gating.py` — matrix of (floor_pass, incumbent_pass, candidate_pass) × first-time-vs-incumbent regime → expected verdict.
- `tests/unit/test_optimization/test_baseline_floor.py` — synthetic stub generation correctness.

### Risk

Medium. The floor arm adds one full eval per first-time-promotion resource. Bounded — only fires once per resource per branch.

### Smoke

`make smoke FIXTURE=iac-team`. Expect run #7 cost +15-20% vs run #6 (first-promotion floor checks), tapering to baseline on subsequent runs.

---

## Step 3 — Refinement 4.3: Cost-per-Success Two-Gate

### Cost source of truth (revised)

`ResultMessage.total_cost_usd` is already on the SDK. **No pricing table needed.** Step 1 captures this on `AgentTranscript.total_cost_usd`; Step 3 aggregates and gates on it.

### What changes

| File | Change |
|---|---|
| `src/harness/optimization/eval_harness/models.py` | `TrialResult.total_cost_usd` (already on transcript, re-exposed for convenience). `ArmResults.total_cost_usd`, `ArmResults.cost_per_success: float \| None`. `EvalResults.candidate_cost_per_success`, `EvalResults.baseline_cost_per_success`. |
| `src/harness/optimization/eval_harness/aggregate.py` | `cost_per_success(arm) = total_cost_usd / decisive_passes` or `None` when zero passes. Failed trials contribute zero passes — correctly penalizes brittle candidates per § 4.3. |
| `src/harness/optimization/gating.py::Gate.decide` | Add cost stage: `candidate.cost_per_success ≤ baseline.cost_per_success × (1 + τ)` where `τ = CGF_TOKEN_REGRESSION_TOLERANCE` (default 0.10). When baseline `cost_per_success` is None (no passes), cost gate auto-passes (no signal to regress against). |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py` | Aggregate JSON records `quality_gate: pass\|fail`, `cost_gate: pass\|fail`, `verdict`. Updated `CHANGELOG.md` writer to log a `**Cost:** $X.XX → $Y.YY (Δ%)` line alongside the existing `**Quality:**`. |
| `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json` | Add optional `scenarios[].cost_gate_exempt: bool` (default false). Per-scenario opt-out for intentional verbosity. |
| `src/harness/monitoring.py` | New instruments: `harness_eval_cost_per_success_usd{resource_type, arm}` (histogram); `harness_eval_cost_gate_total{outcome}` (counter). |
| `config/monitoring/dashboards/70-mode-cgf.json` | New panel: cost-per-success Pareto (baseline vs candidate). |
| `.env.example`, `docker-compose.yml` | `CGF_TOKEN_REGRESSION_TOLERANCE=0.10`. |
| `docs/OBSERVABILITY.md` § 3, § 4 | Document the new instruments + dashboard panel. |

### Tests

- `tests/unit/test_optimization/test_cost_gate.py` — gate verdict matrix (quality × cost).
- `tests/unit/test_optimization/test_transcript_cost.py` — `ResultMessage.total_cost_usd=$X` → `AgentTranscript.total_cost_usd=$X`; missing field → 0.0.
- `tests/unit/test_optimization/test_cost_aggregate.py` — `cost_per_success` math, including zero-passes edge case.

### Risk

Low-medium. SDK already emits the data; we're surfacing it. Main risk is `cost_per_success=None` edge cases — explicitly handled in `Gate.decide()`.

### Smoke

`make smoke FIXTURE=iac-team`. Verify `harness_eval_cost_per_success_usd` populates Grafana and matches the per-resource `total_cost_usd` in `eval-results.json`. Compare against `claude_code_cost_usage_USD_total` for the same time window — they should agree within rounding.

---

## Step 4 — Refinement 4.4: Pipeline Tightening (3 small independent fixes)

### 4.4.a — Hash the eval suite; refuse mid-loop mutations

| File | Change |
|---|---|
| `src/harness/progress.py::MultiResourceState` | `eval_suite_hash: str = ""`. |
| `src/harness/optimization/_orchestrator_phases/eval_design.py` | After successful suite write, SHA-256 the file bytes; store on state. |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py` | Before each round, recompute live suite hash. Mismatch → `RuntimeError("eval-suite.yaml changed mid-loop")`. Hard abort. |
| Tests | `test_eval_suite_hash_guard.py` — mutate suite mid-run → abort. |

### 4.4.b — Stagnation early-stop

| File | Change |
|---|---|
| `_orchestrator_helpers.py` | `DEFAULT_MIN_GAIN_PER_ROUND = 0.02`. |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py` | Escalate to VALIDATE when `Δcandidate_pass_rate < CGF_MIN_GAIN_PER_ROUND` between consecutive feedback rounds, even before max-feedback. |
| `.env.example` | `CGF_MIN_GAIN_PER_ROUND=0.02`. |
| Tests | `test_stagnation_stop.py` — round-N delta < 0.02 → escalate. |

### 4.4.c — Held-out usage bookkeeping (rotation deferred to Phase D)

| File | Change |
|---|---|
| `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json` | Optional `scenarios[].first_used_at: timestamp\|null`, `scenarios[].uses: int`. |
| `src/harness/optimization/_orchestrator_phases/execution_eval.py` | After gate decision, increment `uses` (and set `first_used_at` if null) on every held-out scenario that was decisive. Writes back to `eval-suite.yaml`. Note: this is the **only** sanctioned mutation of the suite mid-loop; § 4.4.a's hash check must hash the suite *before* this write-back, or treat `first_used_at` / `uses` as ignored fields when hashing. Recommended: hash a normalized form of the suite that excludes these two fields. |

### Smoke

After all three: `make smoke FIXTURE=iac-team`. Confirm (a) tampering with a non-bookkeeping field aborts, (b) early-stop fires on a plateau, (c) held-out `uses` increments.

---

## Step 5 — Docs & release notes

| File | Change |
|---|---|
| `docs/PHASEA_SUMMARY.md` | Append § 5: "What landed on `cgf-eval-ab`" with per-step PR + run-number deltas. |
| `docs/CGF-EVAL-ROADMAP.md` | Move "Phase B token-regression check" → shipped in Phase A polish. Phase B retains bootstrap-CI gate + pairwise judge + calibration items. |
| `docs/CGF-USER-GUIDE.md` | New env vars: `CGF_TOKEN_REGRESSION_TOLERANCE`, `CGF_MIN_GAIN_PER_ROUND`. |
| `src/harness/optimization/CLAUDE.md` | Updated env-var table + new modules (`gating.py`, `_baseline_floor.py`). |
| `MEMORY.md` | One-line entry. |

---

## Decisions locked for this branch

| Decision | Value | Why |
|---|---|---|
| Judge model | `opus` (`claude-opus-4-5-20250929`) | Established Phase A default; do not change mid-branch. |
| Design / optimizer model | `sonnet` (current default) | Must differ from judge to avoid self-preference bias. |
| `CGF_EVAL_PROMOTION_EPSILON` | `0.0` (existing) | Phase A simple-threshold; bootstrap CI lands in Phase B. |
| `CGF_TOKEN_REGRESSION_TOLERANCE` | `0.10` | Per § 4.3 of PHASEA_SUMMARY. |
| `CGF_MIN_GAIN_PER_ROUND` | `0.02` | Per § 4.4.b. |
| Floor arm | One-shot per resource at first promotion; never re-run within a branch | Model is the experimental control; no in-branch drift. |
| Cost gate exemption | Per-scenario opt-in (`cost_gate_exempt: true`) | Per-resource granularity preserved; no resource-type fallback. |

---

## Ordering recap

```
Step 1 (4.1 isolation + cost capture) ── must come first
   │   establishes total_cost_usd on transcript; locks judge prompt isolation
   │
Step 2 (4.2 dual baseline) ──────────── depends on Step 1
   │   floor arm is itself an isolated agent run
   │
Step 3 (4.3 cost gate) ──────────────── depends on Step 1's cost capture
   │   gate logic; new Prom instruments; CHANGELOG row
   │
Step 4 (4.4 tightening, 3 independent) ─ batchable last
   │
Step 5 (docs)
```

Each step ends with `make smoke FIXTURE=iac-team`. Regressions kill the step's PR; fix forward, no merge red.
