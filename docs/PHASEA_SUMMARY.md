# Phase-A Eval Pipeline — Summary

This doc has four objectives:

1. **Current state** — what works today, what's shipped, where the code lives. (§ 1)
2. **Architecture & technical decisions** — what was built and *why*, including a per-phase walkthrough. (§ 2)
3. **Key learnings from test runs** — what we observed under real load. (§ 3)
4. **Phase A refinement plan** — the four refinements (eval-agent isolation, dual baseline, token-efficiency gating, pipeline tightening) that landed on branch `cgf-eval-ab` before opening Phase B, plus the post-review polish, the Run #7 I-series fixes, and the Run #8 validation that followed. Each refinement is grounded in Anthropic canonical guidance + 2024–2025 LLM-as-judge literature. (§ 4, especially §§ 4.8–4.10)

This is the retrospective companion to [CGF-EVAL-ROADMAP.md](./CGF-EVAL-ROADMAP.md), which carries the *longer*-term forward plan (Phases B/C/D, Stage 4, cross-cutting harness work). §§ 4.8–4.10 capture what landed on `cgf-eval-ab` (merged to `main` via `29456bd` on 2026-05-19); per-step engineering details live in the individual commit messages. For per-defect fix histories on the earlier rounds see `git log` on `phase-a-fixes` / `phase-a-perf`. For day-to-day operational reference (env vars, how to run, resume from existing state) see [CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md).

---

## 1. Current state

### Branch ledger

| Branch | Carries | Status |
|---|---|---|
| `contextgrad-eval` | Stages 1+2 + Phase A.1–A.7 (eval framework end-to-end) + `phase-a-fixes` (F3–F16) + `phase-a-perf` (F17–F22) | **Merged to `main`** via `2e762c5` (2026-05-14) |
| `grafana-refactor` | 10-dashboard architecture + 13 alert rules + OBSERVABILITY.md | Merged to `main` via `cca6fe7` |
| `cgf-eval-ab` | Phase A refinement work (eval-agent isolation, dual-baseline, token-efficiency gating, pipeline tightening) + pre-smoke polish + Run #7 I-series fixes + Run #8 validation + J1/J2 + Grafana dashboard reorg — see §§ 4.8–4.10 | **Merged to `main`** via `29456bd` (2026-05-19) |

**Unit suite:** 2082 passing (was 1986 after § 4.8, 2035 after § 4.9; +47 across the I-series and J-series in § 4.10). 111 integration tests collected.

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

#### What each phase does

| Phase | Driver | Consumes | Produces | Notes |
|---|---|---|---|---|
| **RESEARCH** | `cgf-research-lead` (sonnet) | `SPEC.md` | `research/notes/*.yaml`, `eval_criteria.yaml` | Domain investigation; one-shot per spec. Held-out scenario seeds drafted here. |
| **DESIGN** | `cgf-resource-architect` (opus) | research notes, SPEC | `resource-plan.yaml` — list of resources, types (agent/skill/cmd/mcp), per-resource criteria | Decides *what* to build, not *how*. Single decision point; no loop. |
| **QA** | Python (no agent) | `resource-plan.yaml` | validated plan, auto-acceptance log | Schema check + sanity rules; auto-accepts in production cadence. Holds a manual review hook for `--review` mode. |
| **GENERATE** | `context-engineer` (sonnet) per resource, `CGF_GENERATE_CONCURRENCY=8` | resource plan entry | `workspace/{spec}/{resource}.md` (canonical name; the prior fixture content is preserved as `{resource}-v0.md`) | One subagent invocation per resource, parallel. Biggest single phase by wall time (~20% post-F17). The first versioned audit copy (`-v1.md`) is written by ITERATE round 1, not GENERATE — see ITERATE row. |
| **EVAL_DESIGN** | `cgf-eval-architect` (sonnet) | resource files, SPEC, `eval_criteria.yaml` | `eval-suite.yaml` (3 scenarios/resource × ~18 resources = ~54 scenarios) | Authors scenarios with per-level graders (deterministic / trajectory / LLM-judge). **Held-out scenarios** marked here are stripped from optimizer feedback. |
| **ITERATE** | `cgf-prompt-optimizer` per resource, `CGF_ITERATE_CONCURRENCY=4` | candidate file (`{resource}.md`), latest feedback entry (if any) | `{resource}-v{n+1}.md` audit copy + overwrites canonical `{resource}.md` with the same content (canonical name is always the latest promotable candidate; versioned `-vN.md` files are the audit trail) | Round 1 fires unconditionally after EVAL_DESIGN. Rounds 2+ fire only for resources that failed the gate AND have feedback. |
| **EXECUTION_EVAL** | `EvalHarness` runner (no agent — runs graders), `CGF_EXECUTION_EVAL_CONCURRENCY=4`, `CGF_EVAL_SCENARIO_CONCURRENCY=6` | scenarios, baseline + candidate files | `eval-results.json`, promotion verdict per resource, `feedback_history` entry if gate failed | Two-arm: runs each scenario once against baseline, once against candidate. Judge calls live here. Gate logic: `candidate.pass_rate ≥ baseline.pass_rate + ε` (simple threshold, Phase A). |
| **VALIDATE** | `cgf-coherence-validator` (opus) | promoted resources, plan | `coherence_score`, `validation-report.md` | Cross-resource consistency check. Can loop back to ITERATE (max 2 rounds) on inconsistency. Run #6 produced 0.93 without retry. |
| **COMPLETE** | Python (no agent) | all of the above | `CHANGELOG.md` entries, final state | Terminal. Phase-progression Grafana row shows green. |

The two backward edges are: `EXECUTION_EVAL → ITERATE` (gate failure, max 2 rounds), and `VALIDATE → ITERATE` (coherence failure, max 2 rounds). All other transitions are forward-only.

#### Why this shape (and why it's worth keeping)

Anthropic's *Three-Agent Harness* recommends separating "the agent doing the work from the agent judging it," and *Demystifying Evals* warns: design the eval before you see the candidate, or the gate leaks. Our shape encodes both:

- **EVAL_DESIGN runs before ITERATE round 1** — the architect cannot have seen the optimizer's diff because the optimizer hasn't produced one yet.
- **EXECUTION_EVAL is a pure runner** — no LLM-as-judge for promotion gating happens in the same agent that wrote the resource.
- **Bounded feedback (2 rounds)** matches PromptWizard/DSPy practice; lifting the cap is exactly how published prompt-optimization benchmarks inflate their numbers.

The refinements in § 4 *tighten the gate semantics* rather than reshape the topology.

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

## 4. Phase A refinement plan

Phase A delivered an eval pipeline that runs end-to-end (run #6 reached COMPLETE in 85m). The shape is sound, but a fresh pass against Anthropic's canonical guidance — *Three-Agent Harness for Long-Running Apps* (Apr 2026), *Building Effective Agents*, *Demystifying Evals for AI Agents* — plus the 2024–2025 LLM-as-judge literature surfaces four refinements we should land before opening Phase B. All four sharpen *gate semantics*; none reshape the pipeline.

This plan is the work happening on branch `cgf-eval-ab`.

### 4.1 Eval-agent isolation (highest-leverage)

**What's true today.** EVAL_DESIGN, EXECUTION_EVAL, and ITERATE are *structurally* separate — different agent definitions, different prompts, different env-var-controlled model selection. But they run in the same Python process and (more consequentially) within the same orchestrator conversation/context. The eval-architect agent is bounded by the orchestrator's overall turn budget, and there's no enforced barrier preventing the orchestrator from passing optimizer reasoning into a judge prompt.

**What Anthropic says.** From the *Three-Agent Harness* post: *"When asked to evaluate work they've produced, agents tend to respond by confidently praising the work — even when, to a human observer, the quality is obviously mediocre. Separating the agent doing the work from the agent judging it proves to be a strong lever to address this issue. Tuning a standalone evaluator to be skeptical turns out to be far more tractable than making a generator critical of its own work."* Their production architecture puts each role in a distinct agent with a distinct context, **communicating only via files**, not shared conversation history.

**Refinement.**
1. **Run the eval-architect (EVAL_DESIGN) and the judge (the LLM-judge calls inside EXECUTION_EVAL) in fully isolated SDK sessions** — fresh `ClaudeAgentOptions`, no parent conversation, no shared message history. The optimizer's diff, rationale, and self-narrative must never appear as input to any judge call.
2. **Use Opus for the judge by default.** `CGF_JUDGE_MODEL=opus` is already the documented default; verify it propagates to every LLM-judge grader call (today the path goes through `LLMJudgeValidator` and the grader subprocess). Cost impact: judge calls are ~10–20% of total run cost today; moving them to opus roughly doubles that share — still acceptable (~$5 per full iac-team run vs $3 on sonnet).
3. **Communicate via JSON artifacts only.** EVAL_DESIGN → `eval-suite.yaml`; EXECUTION_EVAL → `eval-results.json`. The orchestrator reads these; no agent-to-agent message passing.

**Confidence:** High. This is the single most explicit canonical recommendation in the research and the architectural blocker for Phase B's bootstrap-CI gate (a noisy gate on a leaky pipeline wastes the statistical power).

**Reference:** [Three-Agent Harness — Anthropic Engineering](https://www.anthropic.com/engineering/harness-design-long-running-apps).

### 4.2 Rethink "baseline" — dual baseline gate

**What's true today.** "Baseline" means `{resource}-v0.md` — the prior fixture content that was preserved by `_backup_original_resource` when GENERATE first ran. Candidates (`v1`, `v2`, …) are written by ITERATE rounds; the canonical `{resource}.md` always mirrors the latest candidate's content. Candidates are scored against the v0. The promotion gate is `candidate.pass_rate ≥ baseline.pass_rate + ε`.

**Why this is fragile.** Length-Controlled AlpacaEval (Dubois et al. 2024) shows that small surface-form changes to a baseline prompt can shift its win rate by ±15 points. A "first draft" is a noisy, unstable reference — it can be arbitrarily strong or weak, and once we promote v1 over v0, v0 is discarded forever, even if v0 was already worse than the bare model with no system prompt at all. AlpacaEval evolved its baseline from `text-davinci-003` (v1) → `gpt-4-turbo` (v2) precisely because a weak baseline produces ~95% win rates that don't discriminate.

**Refinement: two baselines, not one.**

| Baseline | What it is | Role |
|---|---|---|
| `baseline_floor` | The target model with **no engineered system prompt** — just the canonical user task | Sanity floor. Any candidate that doesn't beat this is worse than doing nothing. |
| `baseline_incumbent` | The most-recently-promoted version | The actual promotion target — what the candidate must clear to ship. |

**Two-stage gate:**
1. Candidate must beat `baseline_floor` (otherwise our prompt engineering has net-negative value).
2. Among candidates that pass (1), candidate must beat `baseline_incumbent` by `≥ ε`.

**First-time promotion is special-cased.** When there's no incumbent yet (v1 trying to become the first promoted version), require a wider margin against `baseline_floor` — e.g., `+2ε` — because v1's win-rate variance is highest.

**Confidence:** High. The pattern matches AlpacaEval's evolution and the broader LLM-as-judge literature; the user's intuition here ("if the first draft does better than default model with no instructions, then it becomes 'baseline'") is exactly correct.

**Be careful of:** A strong external baseline (e.g., GPT-4o) is a useful one-time sanity check but introduces cross-vendor coupling and is not appropriate as a recurring promotion gate for an Anthropic-SDK harness. Stick with same-model `baseline_floor`.

**References:** [Length-Controlled AlpacaEval (arXiv 2404.04475)](https://arxiv.org/abs/2404.04475); [AlpacaEval — tatsu-lab/alpaca_eval](https://github.com/tatsu-lab/alpaca_eval).

### 4.3 Token efficiency as a first-class eval signal

**What's true today.** SDK telemetry already exposes per-task tokens via `claude_code_token_usage_tokens_total{model, query_source, type}` and `claude_code_cost_usage_USD_total{model, query_source}` — the four `type` values are `input`, `output`, `cacheRead`, `cacheCreation`. Prometheus + Grafana scrape both. But the promotion gate today is purely pass-rate; tokens are observed, never decided on.

**What the literature says.** Multi-objective eval (CLEAR framework: Cost, Latency, Efficacy, Assurance, Reliability) is the 2025 industry consensus. Gate on each axis separately, **never via a weighted sum**. Han et al. 2025 (Token-Budget-Aware LLM Reasoning) and length-controlled AlpacaEval both demonstrate Goodhart-on-tokens: optimize purely for token reduction → quality regresses; optimize purely for accuracy → verbosity inflates. The robust pattern is a **two-gate** check.

**Refinement: two-gate promotion.**

| Gate | Condition | Tolerance knob |
|---|---|---|
| Quality | `candidate.pass_rate ≥ baseline.pass_rate + ε` *(unchanged from Phase A)* | `CGF_EVAL_PROMOTION_EPSILON` |
| Cost | `candidate.cost_per_success ≤ baseline.cost_per_success × (1 + τ)` | `CGF_TOKEN_REGRESSION_TOLERANCE` (default 0.10, tighten over time) |

Both must clear for promotion. **A weighted-sum scalar is explicitly not recommended** — it has known pathological optima.

**Define `cost_per_success` precisely.** Use **cost-USD**, not raw tokens, because cached-input tokens are ~10× cheaper but still count toward raw counts; a prompt edit that breaks the cache prefix would look like an "improvement" under raw-token gating. Specifically:

```
cost_per_success = total_USD_across_trajectory / successful_completions
```

where `total_USD` sums all four token types (input + output + cacheRead + cacheCreation) across the main session + every sub-agent call, and `successful_completions` is the count of scenarios where the candidate passed. **Failed scenarios contribute zero to the denominator** — this correctly penalizes brittle candidates that spend tokens without producing wins.

**Surface a Pareto view in Grafana.** Quality on one axis (pass_rate), `cost_per_success` on the other, one point per (resource, version). Promotion-eligible candidates are those Pareto-non-dominated AND clearing both gates. The eval framework already has the instruments; this is a Grafana-only change.

**Confidence:** High on the two-gate structure (canonical in multi-objective eval); medium-high on the specific `τ=0.10` default (should tighten as the gate matures).

**Be careful of:**
- **Cache hit ratio drift.** Prompt rewrites that break cache prefixes will inflate `cost_per_success` even when output quality is identical. Use cost-USD (which weights cache-reads at 10% of input), not raw tokens.
- **Intentional verbosity** (chain-of-thought, tool-trace logging) — exempt per resource-type in gate config if needed.

**References:** [Beyond Accuracy: Multi-Dimensional Enterprise Eval (arXiv 2511.14136)](https://arxiv.org/html/2511.14136v1); [Token-Budget-Aware LLM Reasoning (arXiv 2412.18547)](https://arxiv.org/html/2412.18547v5); [Budget-Aware Tool-Use (arXiv 2511.17006)](https://arxiv.org/abs/2511.17006).

### 4.4 Pipeline tightening (small, high-impact)

The 9-phase shape is canonical. Three small additions sharpen it.

1. **Hash the eval suite at EVAL_DESIGN exit; refuse re-runs if the hash changes mid-loop.** Today, nothing prevents the architect from being re-invoked between rounds 1 and 2, silently changing the scenarios the candidate is being graded against. Even if the architect prompt forbids it, a code path or operator slip could leak optimizer reasoning into the eval design. Concrete: write `eval_suite_hash` into `optimization-state.json`; EXECUTION_EVAL rejects with a hard abort if the live suite's hash doesn't match.

2. **Stagnation early-stop in the feedback loop.** Two rounds is the right cap. But within that cap, stop early if `iteration N` produces `Δpass_rate < min_gain` (e.g., 2 percentage points) versus `iteration N-1`. Cheap insurance against pathological loops where each round drifts laterally without improving. Variable: `CGF_MIN_GAIN_PER_ROUND=0.02`.

3. **Rotate held-out scenarios on contact.** Phase A correctly strips held-out from optimizer feedback. But over many candidates the optimizer's gradient can still leak through indirect signals (which resources improved, which didn't). The sustainable mitigation is: when a held-out scenario participates in a promotion decision, retire it and rotate in a fresh one from the architect's reserve. Tracked in `eval-suite.yaml`'s `scenario_history`.

**Confidence:** High on (1) — direct application of the Anthropic harness pre-commit-spec pattern. Medium-high on (2) — standard prompt-optimization practice. Medium on (3) — defers naturally to Phase D when calibration data tells us how fast scenarios go stale.

### 4.5 What this enables, and what it doesn't

These four refinements unblock Phase B without reshaping it. Concretely:

- **Phase B's bootstrap-CI gate** ([CGF-EVAL-ROADMAP § 4](./CGF-EVAL-ROADMAP.md#4-phase-b--statistical-promotion-gating)) becomes meaningful: a CI lower-bound > 0.5 on a leaky gate is wasted statistical power; isolation (4.1) fixes the leak first.
- **Phase B's token-regression check** ([CGF-EVAL-ROADMAP § 4 task 3](./CGF-EVAL-ROADMAP.md#4-phase-b--statistical-promotion-gating)) is exactly the cost gate in 4.3 — landing it in Phase A polish lets us measure it under real load before bootstrap CI complicates the picture.
- **Phase B's pairwise judge with position balancing** still belongs in Phase B; that's the bias mitigation, not the isolation primitive.

These refinements do **not** address:

- **Scenario discrimination** — the "13-of-17 ties at 1.00" problem in run #6. That's a content problem (the architect doesn't always write *discriminating* scenarios), not an architecture problem. See [CGF-EVAL-ROADMAP § 3.2](./CGF-EVAL-ROADMAP.md#32-eval-design-quality-biggest-signal-quality-lever).
- **Unwinnable resources** — F21 catches them post-round-1; F23 (multi-grader) would extract more signal per call. Tracked separately.

### 4.6 Sequencing

Within branch `cgf-eval-ab`, the order is set by dependency:

1. **4.1 isolation** first — everything else assumes a clean separation. Largest mechanical change (SDK session plumbing in `eval_harness/runner.py`).
2. **4.2 dual baseline** second — depends on 4.1 because `baseline_floor` is itself an isolated agent run.
3. **4.3 cost gate** third — depends on having reliable per-trajectory cost telemetry, which we already have; needs only the new gate logic in `gating.py` (currently the simple-threshold lives in `EXECUTION_EVAL` phase code).
4. **4.4 tightening** last — three small additions, each independent of the others, batchable.

Smoke after each: rerun the iac-team fixture and verify run #7 still hits COMPLETE inside the 60–120-minute budget, with the new gates active.

### 4.7 Cross-references

- **Phase B / C / D forward plan** (statistical gate, ephemeral runtime, calibration & CI) → [CGF-EVAL-ROADMAP.md §§ 4–6](./CGF-EVAL-ROADMAP.md#4-phase-b--statistical-promotion-gating).
- **Stage 4** (E2E test, resume, review gates, perf, edge cases, error recovery, docs, memory, CREATE-mode) → [CGF-EVAL-ROADMAP.md § 7](./CGF-EVAL-ROADMAP.md#7-stage-4--integration--hardening).
- **Operational reference** (env vars, how to run, resume from existing state) → [CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md).
- **Queued F-series defects** (F23 multi-grader, F24 shared-generation, F25 GENERATE timeout) → [CGF-EVAL-ROADMAP.md § 3.3](./CGF-EVAL-ROADMAP.md#33-queued-f-series-defects).

### 4.8 What landed on `cgf-eval-ab`

The four refinements were shipped in four sequential commits on branch `cgf-eval-ab`, each ending with the full unit suite green. Per-step engineering details in the commit messages.

| Step | Refinement | Commit | Tests added | Unit suite total | Status |
|---|---|---|---|---|---|
| 1 | 4.1 Eval-agent isolation + cost capture | `de3a21e` | +17 | 1918 | ✅ |
| 2 | 4.2 Dual baseline (floor + incumbent) | `bb48f32` | +29 / +14 | 1947 | ✅ |
| 3 | 4.3 Cost-per-success two-gate | `c02db21` | +22 | 1969 | ✅ |
| 4 | 4.4 Pipeline tightening (3 sub-fixes) | `fe85e96` | +17 | 1986 | ✅ |

**Surface changes:**

- **New modules.** `src/harness/optimization/gating.py` (3-stage gate: floor + incumbent + cost). `src/harness/optimization/_orchestrator_phases/_baseline_floor.py` (synthetic bare-model resource).
- **New state fields.** `ResourceStatus.last_promoted_version` (gates one-shot floor arm). `MultiResourceState.eval_suite_hash` (mid-loop mutation guard).
- **New eval surface.** `EvalResults` gains `judge_model_id`, `judge_prompt_hash`, `total_cost_usd`, `floor`, `floor_pass_rate`, `baseline_cost_per_success`, `candidate_cost_per_success`. `AgentTranscript.total_cost_usd` captured from `ResultMessage.total_cost_usd` (no separate pricing system). `judge_prompt_hash` is computed by `judge_rubric_hash(rubric, judge_model_id)` over `(rubric_text + judge_system_prompt + judge_model_id)` — **stable across runs of the same suite** (the original transcript-mixed implementation would have been unique per run, defeating its use as Phase D's Cohen's-κ calibration key). The per-trial debugging hash `judge_prompt_hash(rubric, transcript)` is still available for replay scenarios.
- **New env knobs.** `CGF_TOKEN_REGRESSION_TOLERANCE=0.10`, `CGF_MIN_GAIN_PER_ROUND=0.02`.
- **New schema field.** `eval-suite.yaml` `scenarios[].cost_gate_exempt: bool` (per-scenario only; no resource-type fallback).
- **New Prom instruments.** `harness_eval_cost_per_success_usd{resource_type, arm}` histogram. `harness_eval_cost_gate_total{outcome}` counter.
- **New sidecar file.** `eval/held-out-usage.json` tracks `{scenario_id: {uses, first_used_at}}` for Phase D rotation.
- **Verdict shape.** `Gate.Verdict = "promote" | "refine" | "reject_floor" | "reject_cost"`. `reject_floor` and `reject_cost` both transition to `needs_refinement` (same downstream feedback-loop semantics).

**Decisions locked for this branch:**

- Floor arm runs **once per resource at first promotion**, then never again. Model is the experimental control; do not change mid-branch.
- Judge model defaults to `opus`; emits WARN when it matches `CGF_DESIGN_MODEL` (self-preference risk).
- Cost gate auto-passes when either side has `None` cost_per_success (no signal to regress against).
- Held-out usage is written to a sidecar, not back into `eval-suite.yaml` — preserves the 4.4.a hash invariant.

**Not yet verified under real load.** The next smoke run on `iac-team` (run #7) is the first end-to-end test. Expect cost +15-20% vs run #6 on first-promotion rounds; near-zero floor cost thereafter.

### 4.9 Pre-smoke review polish (post-4.8)

A code-review pass over the four shipped refinements before kicking off
the iac-team smoke run #7 surfaced five additional fixes. None reshape
the gate semantics; three correct latent defects that would have
muddied the smoke data, two are independent guards. All five landed
as separate commits on `cgf-eval-ab`.

| # | Commit | Fix | Lines |
|---|---|---|---|
| A | `ecabe97` | Accept YAML-list `tools:` frontmatter in `_parse_resource_file` (smoke blocker — every iac-team agent uses the canonical list form). | +235 / −6 |
| B | `6cae9d6` | Aggregate JSON records authoritative gate verdict; cost-gate counter only fires when cost stage was actually consulted (was mislabelling quality-rejected outcomes as cost-gate successes). | +518 / −44 |
| C | `9bc2bb0` | Empty-scenario set fails closed via F8 path (was silently auto-promoting); `ResourceStatus.from_dict` infers `last_promoted_version` on resume from legacy state files. | +304 / −6 |
| D | `5f224a0` | `judge_prompt_hash` is rubric+identity only via new `judge_rubric_hash(rubric, judge_model_id)` — stable across runs of the same suite (was transcript-mixed and non-deterministic, making it useless as Phase D's calibration key). | +225 / −35 |
| E | `5f047e1` | Drop leading slash in `make report SPEC=…` --workspace handling (cosmetic). | +1 / −1 |

**New surface added in this polish pass:**
- `AggregateVerdict` literal type (superset of `gating.Verdict` with `"unwinnable"`) used by `execution_eval._eval_single_resource` return shape and `_write_aggregate_results`.
- `judge_rubric_hash(rubric, judge_model_id)` exported from `graders.llm_judge` alongside the existing transcript-sensitive `judge_prompt_hash` (now repurposed for per-trial debugging only).
- `_make_eval_results` test helper now injects a default 1-scenario list when `failing_scenarios` is omitted — pre-fix, every gate-exercising test silently relied on the empty-scenarios silent-promote bug.

**Unit suite:** 2035 passing (was 1986 after § 4.8; +49 new tests from this polish).

**Smoke status (at § 4.9 cutoff):** unverified under load; Run #7 was the next checkpoint. See § 4.10 for what Run #7 and Run #8 actually surfaced.

### 4.10 Run #7 + I-series + Run #8 validation (the actual smoke arc)

Run #7 was the first end-to-end smoke after the §§ 4.8–4.9 polish landed.
It reached `COMPLETE` but surfaced fourteen issues — the **I-series** —
ranging from grader-probe path bugs to a systemic finding that the
cost gate was rejecting candidates the optimizer couldn't recover from
because the feedback prompt didn't tell it to trim tokens. Most of
the I-series shipped as small fixes; I15 was the substantial one, and
Run #8 then validated it in production.

#### Run #7 — surfaced 14 issues, all addressed

| # | Commit | Fix | Severity |
|---|---|---|---|
| I1 | `14d1c24` | `setup.sh` probes IaC grader CLIs (`kubectl`, `helm`, `terraform`, `trivy`, `kubeconform`) inside the container, not on the host — eliminates false-positive WARN that masked real issues | smoke blocker |
| I2 | `a31c311` | `python -u` for unbuffered smoke logs (per-line vs 5–30 min freezes) | observability |
| I4 / I7 | `a31c311` | Doc sync + floor-naming gotcha clarifications | doc |
| I6 | `0fc0afd` | Drop architect's hardcoded `eval_model`; loader defaults to `None` so `CGF_JUDGE_MODEL` actually applies | correctness |
| I8 | `ca7a001` | Defensive cleanup of stray agent-written `summary.json` files (Python owns it, agent owns narrative blocks) | correctness |
| I10 | `7a01116` | Persist gate verdict in per-resource `eval-results.json` (was only in aggregate) | observability |
| I11 | `a31c311` | `floor_pass_rate` field naming gotcha noted in code + doc | clarity |
| I14 | `b15eaf9` | Single-source model aliases; drop stale `claude-sonnet-4-may-2025-…` references | hygiene |
| **I15** | `6e44f6d` | **Cost-aware feedback + quality-scaled τ + verdict-branched optimizer prompt.** The big one: `reject_cost` → TRIM TOKENS, `reject_floor` → TRIM AGGRESSIVELY, `refine` → ADD COVERAGE. Quality bonus `(1 + bonus_factor·Δpass_rate)` softens τ when the candidate is materially better. Plus surfacing rejection subtype in `RUN_REPORT.md`. | **HIGH — gate behavior** |
| (RUN_REPORT) | `f83e581`, `4cbc1b1` | Rendering fixes + merged results section; clean Python/agent ownership split | observability |
| I9 | (queued) | Persist GENERATE-only artifact for replay — calibration coverage gap. **Deferred to Phase D** (`CGF-EVAL-ROADMAP.md § 6`) so writer and consumer (`make eval-calibrate`) ship together. | Phase D |
| I16 | (queued) | Empirically tune `CGF_TOKEN_REGRESSION_TOLERANCE` + `CGF_COST_QUALITY_BONUS`. Run #7's 8/18 cost rejections are seed data. **Deferred to Phase D** as calibration consumer #2. | Phase D |

Run #7 raw issue log: `logs/smoke/run7-issues.md`.

#### Run #8 — validated I15 in production

I15 made specific predictions: ≥5 of run #7's 8 r1 cost-rejected
candidates should recover in r2; ITERATE r2 wall time should drop back
toward run #6's ~7 min (from run #7's 57 min); RUN_REPORT should show
verdict-branched recovery messaging in optimizer transcripts.

Run #8 outcomes (all from `logs/smoke/run8-issues.md` + the merge
commit body):

| Metric | Run #7 | Run #8 | Δ |
|---|---|---|---|
| Cost-rejected candidates recovered on r2 | 0 of 8 | **7 of 7** | from 0% → 100% |
| ITERATE r2 wall time | 57 min | **~16.5 min** | **3.5× faster** |
| Final promote rate | 10 of 18 | **16 of 18** | +33 % |
| Verdict-branched optimizer behavior | n/a | **Observable in subagent transcripts** | new |

Two low-severity reporting bugs surfaced (J-series) and shipped:

| # | Commit | Fix |
|---|---|---|
| J1 | `8e088f0` | `agent_progress` renderer no longer truncates lines that contain CGF signal markers (`[*_COMPLETE:`, `[*_ISSUES:`) — Run #8 had ~half the GENERATE markers clipped from the host log preview only (orchestrator state was always authoritative) |
| J2 | `8e088f0` | `run_report.py::_render_summary` counts resources whose final verdict is `promote` AND `iterations > 0` for the "Refined (recovered via feedback)" counter — was stuck at 0 despite Run #8 actually showing 9 recoveries in the per-resource view |

Run #8 was the first run where the cost-aware feedback loop closed
end-to-end. The 3.5× ITERATE r2 speedup matters because cost-rejection
recovery was previously the dominant failure mode of the two-gate
design; Phase B's bootstrap-CI gate would have amplified that failure,
not fixed it.

#### Grafana dashboard reorganization (`01cd8b2`)

Twelve dashboards collapsed to ten by merging the standalone "tools"
row into the "productivity" dashboard; renumbered for stable ordering;
dropped the `sdk-` UID prefix. No metric changes; pure operator-UX. See
`docs/OBSERVABILITY.md` for the current 10-dashboard inventory.

#### What's actually queued for Phase B

The roadmap (`CGF-EVAL-ROADMAP.md § 3`) named two architectural
prerequisites for Phase B: § 3.1 eval-as-Opus-agent isolation, and
§ 3.2 scenario discrimination quality. **§ 3.1 is shipped as Phase A
refinement 4.1 (commit `de3a21e`).** § 3.2 (scenario discrimination)
remains the outstanding signal-quality lever: Run #8's 16/18 promote
rate is high partly because many scenarios still don't discriminate
between baseline and candidate, so a tighter statistical gate has less
to bite into. The Phase B kickoff conversation should decide whether
to invest in architect-prompt work on scenario discrimination first
or accept that Phase B will tighten an already-flat signal.

Queued F-series defects (`CGF-EVAL-ROADMAP.md § 3.3`) — F23
multi-grader, F24 shared-generation, F25 GENERATE-timeout
investigation — remain not-blockers for Phase B.

### 4.11 Canonical references used in this plan

- [Three-Agent Harness for Long-Running Apps — Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps) — separation-of-concerns rationale (4.1)
- [Building Effective Agents — Anthropic](https://www.anthropic.com/engineering/building-effective-agents) — evaluator-optimizer pattern (4.4)
- [Demystifying Evals for AI Agents — Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — dimensional isolation, cost as eval signal (4.1, 4.3)
- [Length-Controlled AlpacaEval (Dubois et al., COLM 2024)](https://arxiv.org/abs/2404.04475) — baseline instability (4.2)
- [Self-Preference Bias in LLM-as-a-Judge (arXiv 2410.21819)](https://arxiv.org/abs/2410.21819) — judge-model-must-differ-from-optimizer (4.1)
- [Beyond Accuracy: Multi-Dimensional Enterprise Eval (arXiv 2511.14136)](https://arxiv.org/html/2511.14136v1) — two-gate cost+quality pattern (4.3)
- [Token-Budget-Aware LLM Reasoning (arXiv 2412.18547)](https://arxiv.org/html/2412.18547v5) — Goodhart-on-tokens (4.3)
- [Automatic Prompt Optimization Survey (arXiv 2502.16923)](https://arxiv.org/html/2502.16923v1) — bounded-feedback + early-stop conventions (4.4)
