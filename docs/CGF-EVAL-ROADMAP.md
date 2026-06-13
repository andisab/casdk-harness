# CGF Eval Roadmap & Harness Forward Plan

The canonical forward-looking plan for `ab-casdk-harness`. Covers:

1. **CGF eval framework** continuing work: Phase A polish → Phase B (statistical gate) → Phase C (ephemeral runtime) → Phase D (calibration & CI).
2. **Cross-cutting harness work**: independent TODOs, build improvements, hardening backlog.

Companion docs:

- **[PHASEA_SUMMARY.md](./PHASEA_SUMMARY.md)** — Phase A retrospective (shipped 2026-05-14). What was built, what was learned, what cost characteristics look like. Source of truth for the "as-built" state of the eval pipeline.
- **[OBSERVABILITY.md](./OBSERVABILITY.md)** — operator guide for the OTel + Prometheus + Grafana + AlertManager stack: 10 dashboards, 13 alert rules, full metric inventory.
- **[CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md)** — day-to-day CGF usage, environment variables, how to run.
- **[CLAUDE.md](../CLAUDE.md)** — repo overview, current status snapshot, "Completed Recently" log, SDK loading behavior.

**Branch:** `main` (Phase A end-to-end + F3–F22 fix series + Phase A refinement Steps 1–5 + pre-smoke polish + Run #7 I-series + Run #8 validation + J1/J2 + Grafana reorg all merged via `29456bd` on 2026-05-19). Phase B work will branch from `main`.
**Owner:** @andisab

---

## Terminology

The codebase has several overlapping "phase"-like concepts. To keep cross-references unambiguous:

| Term | Meaning | Example |
|---|---|---|
| **Stage** | A major CGF rollout. Stages 1, 2, and 3-Phase-A shipped (protocol layer; MCP creation skills; comparison-aware eval harness). Stage 3 Phases B–D and Stage 4 are this document. | "Stage 3 is the eval framework." |
| **Phase A/B/C/D** | Sub-divisions of Stage 3, each shipping independently. Unqualified "Phase X" in this document always means Stage 3's Phase X. | "Phase B — statistical promotion gating." |
| **A.1, A.2, …** | Individual tasks within a Phase. Phase A's A.1–A.7 are all shipped. | "A.4 was the EvalHarness runner." |
| **F-series** | Defect numbers from the Phase A smoke runs (`phase-a-fixes`, `phase-a-perf`). F3–F22 shipped; F23–F25 are queued (see § 3). | "F17 skip-unchanged-resources filter." |
| **Pipeline phase** | A runtime step in the orchestrator's state machine (`RESEARCH`, `DESIGN`, `GENERATE`, `EVAL_DESIGN`, `ITERATE`, `EXECUTION_EVAL`, `VALIDATE`, `COMPLETE`). Distinct from rollout phases above. | "Wire `EVAL_DESIGN` into the orchestrator." |
| **Block / Part** | Earlier 2026 reorganization milestones (Blocks 1–4). Block 4 Part 3 shipped the observability stack. The 2026-05-14 Grafana refactor (10 dashboards, 13 alerts, OBSERVABILITY.md as canonical) supersedes Block 4 Phase 3C's deliverables. | "Block 4 shipped OTel + Prometheus + Grafana." |
| **Task** | An item within Stage 4 (Tasks 1–9 in § 7 below). | "Task 9 — CREATE-mode support." |

---

## 1. Status snapshot

**As of 2026-05-19:**

- All four reorganization blocks (1, 2, 3, 4) merged to `main`.
- **CGF Stage 3 Phase A shipped end-to-end** plus `phase-a-fixes` (F3–F16), `phase-a-perf` (F17–F22), Phase A refinement Steps 1–5 (eval-agent isolation, dual baseline, cost-per-success gate, pipeline tightening, release notes), pre-smoke polish (A–E), Run #7 I-series (I1, I2, I4, I6, I7, I8, I10, I11, I14, I15), Run #8 validation, J1/J2 reporting fixes, and Grafana dashboard reorganization — **all merged to `main` via `29456bd` (2026-05-19)**. First full pipeline reached `COMPLETE` in run #6 (85m 06s); cost-aware feedback validated in production via run #8 (16/18 promote rate, ITERATE r2 3.5× faster than run #7). See [PHASEA_SUMMARY.md §§ 1, 4.10](./PHASEA_SUMMARY.md#1-current-state).
- **Tests:** 2082 unit passing (was 1863 at Phase A baseline; +219 across refinements + polish + I-series + J-series), 111 integration tests collected.
- **Pipeline:** 9 phases working end-to-end — `RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → COMPLETE`, with `EXECUTION_EVAL → ITERATE` feedback loop bounded at 2 rounds.
- **Gate:** 3-stage `Gate.decide()` — floor (one-shot bare-model arm at first promotion) + incumbent (`pass_rate ≥ baseline + ε`) + cost (`cost_per_success ≤ baseline × (1 + τ)` with quality-bonus relief). Verdict-branched optimizer feedback (`reject_cost` / `reject_floor` / `refine`).
- **Observability stack live:** OTel Collector → Prometheus, 10 pre-provisioned Grafana dashboards (reorganized 2026-05-19), AlertManager + 13 active alert rules. Canonical reference: [OBSERVABILITY.md](./OBSERVABILITY.md).
- **2026-06-13 — eval-strategy reassessment (§ 1.1):** discrimination-first turn. Phase A.5 (§ 3.7) and Phase E (§ 6A) added; Phase B re-scoped (§ 4). Full research record: [EVAL-RESEARCH-2026-06.md](./EVAL-RESEARCH-2026-06.md).

| Stage | Status | Where |
|---|---|---|
| **Stage 1 — Protocol layer + resource architect + DESIGN phase** | shipped | `main`, via Block 1 |
| **Stage 2 — MCP tool/server creation skills + Python/TypeScript scaffolds** | shipped | `main`, via Block 1 |
| **Stage 3 Phase A — Comparison-aware eval harness** | **shipped** | `main` |
| **Stage 3 Phase A polish + Run #7/#8 (this doc § 3, §§ 4.8–4.10 of PHASEA_SUMMARY)** | **shipped** | `main` via `29456bd` |
| **Stage 3 Phase A.5 — Signal-quality restoration (discrimination-first)** | **next** | planned (§ 3.7) |
| **Stage 3 Phase B — Statistical promotion gating (re-scoped 2026-06-13)** | not started | after A.5 |
| **Stage 3 Phase C — Ephemeral runtime** | not started | future |
| **Stage 3 Phase D — Calibration & CI** | not started; queues I9 + I16 | future |
| **Stage 3 Phase E — Compound learning (learnings ledger)** | not started | future (§ 6A) |
| **Stage 4 — Integration & hardening** | not started; depends on Phase D | future |

---

### 1.1 Strategy reassessment — the discrimination-first turn (2026-06-13)

A research + adversarial-review pass (13-agent workflow: 6 web-research sweeps on 2024–2026 eval methodology + 6 code-grounded verdict agents + synthesis; ~1.37M tokens) re-tested the eval strategy's load-bearing assumptions against both the literature and current-harness run data (iac-team run #8 + the 2026-05-26 `mobile-dev` run). Full record: **[EVAL-RESEARCH-2026-06.md](./EVAL-RESEARCH-2026-06.md)**.

**Core finding — the eval optimizes for cheapness when its job is discrimination.** The dominant failure mode is not a statistics problem; it is that contains-dominated, judge-starved suites cannot separate the two arms. Current-harness evidence:

- Run #8's generated suite used **0 `llm_judge` graders** (98 `contains`) → 11/17 resources tied at 1.00/1.00.
- The 2026-05-26 `mobile-dev` run (different resource type, current `main`) shows **`win_rate ≡ 0` across all 32 eval-results** — even where candidate pass-rate beat baseline — plus pervasive `no_decision` and **23% unwinnable**. The per-scenario `win_rate` metric is *degenerate*.
- `eval_strategy` (the per-resource-type grader-routing field in `resource_types.py`) has **zero read-sites** — dead metadata. This caused `iac-generator`'s structurally-unwinnable 0/0 (trajectory graders on a system-prompt file that never executes tools).

**What it overturned** (verdicts in the companion doc):

| Overturned assumption | Correction |
|---|---|
| Cost-first grader priority | **Discrimination-first cascade**: deterministic checks gate; the judge discriminates every scenario both arms pass. |
| Architect "mental-simulation" instructions are the § 3.2 prerequisite | An **empirical discrimination audit reusing the floor arm** outranks it; instructions become a supplement. |
| Keep the 1–5 integer judge scale | Coarse scale + retry→tie collapses signal → **anchored 7-pt scale + criterion-decomposed sub-scores**. |
| Bootstrap-CI win-rate gate | N is **3**, not 10–30; would promote ~0/18 → **Beta-Binomial posterior on paired discordant outcomes**. |
| Cache baseline cost-per-success (§ 3.6 #1) | Caching freezes one draw of a ~110%-variance distribution → **multi-sample the baseline, then cache the stable estimate**. |
| Adaptive across types; Phase D covers learning | `eval_strategy` routing is unbuilt; the **learnings ledger (Phase E)** is a distinct, uncovered capability. |

**Resolved direction (owner, 2026-06-13):** full reprioritization (this revision); **cascade-gated judge** posture (restore discrimination while capping judge spend); learnings ledger **committed as Phase E**. Sequencing: **Phase A.5 → smoke #9 → re-scoped Phase B**. The near-term work is § 3.7; Phase B is re-scoped in § 4; Phase E is § 6A.

---

## 2. Architecture (as built)

Phase A shipped via PRs #7, #8, #9, #11, #12, #13, plus the A.7 closing PR, plus the `phase-a-fixes` (F3–F16, merged via `d1f6351`) and `phase-a-perf` (F17–F22, merged via `c8c9d9f`) branches. Code lives in:

| Concern | Module |
|---|---|
| Multi-resource state machine | `src/harness/optimization/multi_resource_orchestrator.py` |
| Per-phase implementations | `src/harness/optimization/_orchestrator_phases/` |
| Eval runner (two-arm) | `src/harness/optimization/eval_harness/runner.py` |
| Graders (deterministic / LLM-judge / trajectory / composite) | `src/harness/optimization/graders/` |
| Eval-architect agent | `src/harness/plugins/cgf-agents/agents/eval/cgf-eval-architect.md` |
| Eval-suite schema | `src/harness/optimization/eval_harness/eval_suite.schema.json` |
| Smoke fixtures | `tests/smoke/iac-team/`, `tests/smoke/python-expert/` |

### 2.1 Pipeline

```
RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE
                                                     ↓
                                       EXECUTION_EVAL → VALIDATE → COMPLETE
                                              ↑              ↓
                                              └─── feedback ──┘ (max 2 rounds)
```

Nine phases, single linear flow with one bounded loop. Per-resource status lives in `optimization-state.json`; deleting `sessions/` is the canonical reset.

### 2.2 Eval-suite + grader model

**Eval suite** (`workspace/{spec}/eval/eval-suite.yaml`):

```yaml
config:
  trials_per_scenario: 1            # bumped in Phase B for statistical power
  timeout_seconds: 300
  eval_model: opus                  # CGF_JUDGE_MODEL
  token_budget: 1_000_000           # CGF_EVAL_TOKEN_BUDGET

scenarios:
  - id: scn_001_positive_async
    level: trajectory                # unit | trajectory | e2e
    target_resource: python-expert
    held_out: false                  # true → optimizer never sees this
    description: "Async retry with backoff under network jitter"
    prompt: "Write a function that retries an async HTTP call..."
    setup:
      files: { "input.txt": "..." }
    graders:
      - type: trajectory
        assert: tool_called
        tool: Bash
      - type: llm_judge
        rubric_id: rb_async_quality
    tags: [async, error-handling]

  - id: scn_002_negative_trigger
    level: unit
    target_resource: python-expert
    held_out: true
    description: "Should NOT activate when query is about JavaScript"
    prompt: "How do I add a click handler to a button?"
    graders:
      - type: trajectory
        assert: no_invocation
        target: python-expert
```

**Grader hierarchy** (`src/harness/optimization/graders/`):

| Tier | Module | Purpose | Cost |
|---|---|---|---|
| Deterministic | `deterministic.py` (`ExactGrader`, `ContainsGrader`, `RegexGrader`, `CodeGrader`) | Syntactic checks, schema validation, executable assertions | Cheapest |
| Trajectory | `trajectory.py` (`tool_called`, `no_tool`, `ordering`, `constraint`) | Uses CGF tracer spans + transcript to grade tool-call sequences | Moderate |
| LLM-judge | `llm_judge.py` (rubric-anchored) | Behavioral / qualitative criteria | Most expensive |
| Composite | `composite.py` (`AndGrader`, `OrGrader`) | Combine tiers per scenario | — |

Each tier emits its own `GraderResult` (`passed: bool`, `score: float`, `details: str`, `grader_type: str`). The gate combines them explicitly per scenario via `AndGrader` / `OrGrader` — three columns rather than worst-of, so debugging stays interpretable.

**Transcript model** (`src/harness/optimization/graders/transcript.py`):

```python
@dataclass
class AgentTranscript:
    messages: list[TranscriptMessage]   # All messages in order
    tool_calls: list[ToolCall]          # Extracted tool calls
    final_output: str
    total_turns: int
    total_tokens: int
    arm: str                            # "baseline" | "candidate"
    task_id: str                        # uuid per scenario invocation

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    result: str
    turn_number: int
    timestamp: float
```

Built from `harness.subagent.call_agent()` message stream.

### 2.3 Pool separation: design vs eval agents

Hard rule: **eval agents never see optimizer reasoning.** Failure modes if violated:

- Judge learns to prefer outputs that match the optimizer's stated intent → optimizer can game the judge.
- Token-efficiency analysis becomes confounded with optimizer planning overhead.

Enforcement is structural. `src/harness/plugins/cgf-agents/agents/` is split into two subdirectories:

```
src/harness/plugins/cgf-agents/agents/
  design/
    cgf-orchestrator.md
    cgf-prompt-optimizer.md
    cgf-research-lead.md
    cgf-resource-architect.md
    cgf-result-evaluator.md       # in-loop self-critique (not eval-pool)
    cgf-test-architect.md
    cgf-test-validator.md
    cgf-criteria-synthesizer.md
    cgf-coherence-validator.md
  eval/
    cgf-eval-architect.md         # shipped Phase A.2
    # pairwise-judge, trigger-accuracy-evaluator, token-efficiency-analyst — Phase B
```

**Today (post-Phase-A) the pool separation is structural only.** Eval still runs in the same Python process and (more consequentially) within the same conversation/context as the orchestrator. § 3.1 below upgrades this to a fully isolated Opus-context agent — the highest-leverage near-term change.

**Different model for eval vs design** is enforced via env vars:

```
CGF_DESIGN_MODEL=sonnet      # default
CGF_JUDGE_MODEL=opus         # default
```

### 2.4 Concurrency model

Per-resource phases run under `asyncio.gather` + `Semaphore`. State writes serialize through `MultiResourceOrchestrator._state_lock`. Per-call timeouts are independent of the semaphore (worst-case makespan is bounded by the slowest single resource × `ceil(N / concurrency)`).

| Knob | Default | Rationale |
|---|---|---|
| `CGF_GENERATE_CONCURRENCY` | 8 | I/O-bound on SDK API; 8-way saturates a typical sonnet rate window. |
| `CGF_ITERATE_CONCURRENCY` | 4 | Each iteration is expensive (~1200s timeout, ~30k tokens); marginal speedup vs 429-risk is poor above 4. |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 4 | Judge calls are I/O-bound; 2-way left ~6 scenario slots idle in run #5i. |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | Inside one resource: 6 scenarios × 2 arms = 12 in-flight calls. |

The D9 retry covers transient 429s; downgrade env vars are the rate-limit escape hatch.

### 2.5 Scenario sandboxing

Every scenario runs in a fresh `/tmp/eval-<id>-<arm>-<hex>` directory. Nothing exists there until `setup.files` (inline content, sandbox-relative paths) materializes it. **No `/sample-app`, no `/manifests`, no `/workspace`** at eval time. Architect prompt forbids absolute paths and `..` segments.

### 2.6 Feedback loop

When the gate fails for a resource, EXECUTION_EVAL writes a feedback entry (failing scenarios, baseline/candidate scores, **held-out scenarios stripped**) into `state.feedback_history` and transitions back to ITERATE. The optimizer reads the latest entry for the resource it's iterating and injects it as additional context. Max 2 feedback rounds before VALIDATE escalation.

### 2.7 Per-level trial timeout

Trajectory scenarios get 300s; unit / e2e get 180s. At `trials_per_scenario=3` (production cadence), the global 300s would have allowed one slow scenario to burn 900s on a single resource — F19 caps that.

### 2.8 Skip-unchanged-resources filter (F17)

`_resources_to_evaluate` filters by `version > last_evaluated_version`. ITERATE round 2 only touches resources flagged `needs_refinement`; EXECUTION_EVAL round 2 mirrors that by skipping resources whose candidate file didn't change. Saved ~12 min + ~300k tokens per feedback cycle in run #6.

### 2.9 Unwinnable-resource detection (F21)

A resource where every scenario scores 0 on both arms is marked `status="unwinnable"`. Feedback iteration cannot help — either the scenarios are unwinnable for this resource type, or the rubric is mis-calibrated. The gate treats unwinnable as non-blocking; the F17 filter excludes them from future eval rounds.

### 2.10 Telemetry

The harness emits `harness.eval.*` attributes on every span and metric during eval runs:

| Attribute | Type | Notes |
|---|---|---|
| `harness.eval.task_id` | string | UUID per scenario invocation |
| `harness.eval.arm` | string | `baseline`, `candidate`, or version label |
| `harness.eval.outcome` | string | `success`, `failure`, `tie` |
| `harness.resource.id` | string | resource under test |
| `harness.resource.type` | string | `agent`, `skill`, `command`, `mcp_server`, `plugin` |

Five Prometheus instruments (`harness_eval_phase_duration_seconds`, `harness_eval_tokens_to_goal`, `harness_eval_scenarios_total`, `harness_eval_arm_score`, `harness_eval_judge_no_decision_total`) plus OTel tracer spans. For the full inventory, call-site map, and alert rules see [OBSERVABILITY.md § 3](./OBSERVABILITY.md) and [src/harness/CLAUDE.md](../src/harness/CLAUDE.md) for the call-site map.

### 2.11 Phase-boundary subprocess audit

`_audit_child_processes()` snapshots `claude` descendants of the orchestrator PID before/after each phase. Non-empty diff → warning log. Observe-only; soft-kill follow-up is gated behind a week of telemetry data showing the actual orphan rate.

### 2.12 In-process eval runner (today) vs ephemeral container (Phase C)

Phase A.4 chose in-process for speed of iteration. Phase C will swap to `docker compose run --rm` per eval scenario for SWE-bench-style determinism (tmpfs workspace, pinned model, isolated `/memory`). The runner already has `runtime: Literal["in_process", "ephemeral_container"]` as a knob — Phase C only wires the container variant.

---

## 3. Near-term — Phase A polish (shipped 2026-05-19)

§§ 3.1, 3.3 token-regression check, and most of the validation gaps shipped on `cgf-eval-ab` and merged via `29456bd`. § 3.2 (scenario discrimination) is the **outstanding signal-quality lever before Phase B**; § 3.3 F23/F24/F25 remain queued. Source: [PHASEA_SUMMARY §§ 4.8–4.10](./PHASEA_SUMMARY.md#48-what-landed-on-cgf-eval-ab).

### 3.1 Eval as a distinct Opus agent with isolated context — **SHIPPED**

Shipped as Phase A refinement 4.1 (commit `de3a21e`, branch `cgf-eval-ab`, merged via `29456bd`). EVAL_DESIGN and the in-EXECUTION_EVAL judge calls now run in fully isolated SDK sessions with fresh `ClaudeAgentOptions`, no parent conversation, and no shared message history. The optimizer's diff/rationale never reaches a judge call. Opus is the default for the judge via `CGF_JUDGE_MODEL=opus`; communication is JSON-artifact only (`eval-suite.yaml` + `eval-results.json`).

What this unblocked: Phase B's bootstrap-CI gate now has a clean separation to operate on. The original framing — "this is the architectural blocker for Phase B's value to land" — is no longer outstanding.

### 3.2 Eval-design quality (biggest signal-quality lever)

Several "tie at zero" or "saturate at 0.67" outcomes in run #6 are scenario-design artifacts, not optimizer failures. The eval-architect agent produces a schema-valid suite, but the scenarios aren't always *discriminating* — they don't separate a good candidate from a bad baseline.

- **Scenario discrimination.** Many scenarios pass on both arms or fail on both, producing flat outcomes. The architect prompt needs explicit guidance to author scenarios that *separate* baseline from candidate (e.g. scenarios that exercise documented improvements over the v0 file).
- **Scenario difficulty distribution.** Today 1 easy + 1 medium + 1 hard per resource at `trials=1` is too coarse; at `trials=3` the signal would smooth but cost triples. Multi-grader scenarios (F23) get more bits per model call without scaling trials.
- **Two persistently broken resource types.**
  - `commands/*` — F20 mitigates via natural-language prompt rewrite; long-term fix is to register workspace commands as plugin commands in the eval runtime.
  - `agents/iac-generator` — scenarios unwinnable for both arms; needs rubric redesign or scenario simplification.

### 3.3 Queued F-series defects

- **F25 — GENERATE timeout under 8-way concurrency.** Run #6: `skills/aws-eks/SKILL.md` GENERATE timed out at 905s (5s over `CGF_GENERATE_TIMEOUT=900`). The `context-engineer` subagent ran 27 turns with **0 tool_calls** — a planning loop without writing. Pre-fix run #5 finished this resource in 611s at concurrency=4. Three working theories: (a) rate-limit tail-latency under 8-way fan-out pushes some resources past the cap; (b) the architect prompt for aws-eks induces a planning loop under contention; (c) random SDK hang. Next steps: instrument context-engineer to log when it spends >60s without a tool call; consider raising GENERATE timeout to 1200s OR lowering `CGF_GENERATE_CONCURRENCY` to 6; investigate aws-eks prompt for ambiguity.
- **F23 — Multi-grader scenarios.** Schema + runner + architect changes so one model call can be scored by N graders. Targets 4× signal-per-dollar for content-evaluation skills.
- **F24 — Shared-generation graph.** Bipartite scenarios ↔ grader-pools for cross-scenario grader reuse. Discussion item; design after F23 validates the multi-grader model.
- ~~**F1 (cosmetic, deferred).**~~ **Shipped as I1** (`14d1c24`) — `setup.sh` now probes IaC grader CLIs inside the container, not on the host.
- **F5 (mitigated, deferred).** Hard-abort path on EVAL_DESIGN architect timeout; currently bandaided by raised budget.

### 3.4 Validation gaps

- **Full 54-scenario suite at `trials=3`.** Smoke uses `trials=1` for speed; production cadence is `trials=3`. Not yet run end-to-end — would 3× per-trial cost but smooth the pass-rate distribution.
- **F25 reproducibility.** Single observation in run #6; runs #7 and #8 did not reproduce it. More smoke runs needed to decide deterministic vs rate-limit roulette.
- **VALIDATE refinement loop never exercised.** Coherence passed cleanly in runs #6, #7, #8; the `VALIDATE → ITERATE` retry path (gated by `max_validate_refinements = 2`) has not yet fired under load.

---

## 3.5 Run #8 systemic findings — what the data actually shows

Run #8 was the first end-to-end run with the full 3-stage gate (floor + incumbent + cost) and verdict-branched cost-aware feedback (I15). The headline outcome — 16 of 18 promoted, 7 of 7 cost-rejected candidates recovered on r2, ITERATE r2 3.5× faster than run #7 — is a clean validation of the polish work. But the run also surfaced three systemic issues that data from earlier runs couldn't show because the gate was never strict enough to expose them. They are listed here in priority order; § 3.6 below maps each to a concrete fix.

### 3.5.1 The cost gate operates against a noisy baseline

The same v0 file evaluated twice produces materially different `baseline_cost_per_success` values, because (a) scenarios run real LLM calls and (b) the bare-arm/candidate-arm pairing isn't cached across rounds. `skills/helm-charts/SKILL.md` is the canonical case:

| Round | Baseline CPS | Candidate CPS | Δ | Verdict |
|---|---|---|---|---|
| r1 (v1 candidate) | $0.15 | $0.19 | +32 % | Refine (quality bonus saved it: pass 0.67→1.00) |
| r2 (v2 candidate) | **$0.32** | $0.44 | +36 % | Reject cost |
| r3 (v3 candidate) | **$0.19** | $0.23 | +20 % | Reject cost |

The baseline CPS varied **$0.15 → $0.32 → $0.19** for the same v0 file across three rounds — a **2.1× swing**. A 10 % τ on a baseline with ~110 % round-to-round variance is statistical noise; the gate is testing a candidate against random draws of the baseline distribution rather than a stable reference. helm-charts was rejected three times running while every candidate scored quality 0.97–1.00.

This is the canonical "Phase A's cost gate is brittle, Phase B's bootstrap-CI fixes win rate but not cost" gap. The fix is either (i) cache the floor-CPS once per `(resource, eval_suite_hash)` and reuse it, or (ii) add an absolute τ floor (`max(baseline × 1.10, baseline + $0.05)`) so small absolute differences don't trigger relative-percentage gates. Both are ~30 LoC in `gating.py`. § 3.6 lists them as the highest-leverage low-hanging fixes. **(Superseded 2026-06-13: caching a single draw freezes a ~110%-variance baseline — replaced by *multi-sample then cache* + a ratio statistic, § 3.7 A4.)**

### 3.5.2 Tied-at-1.00 still dominates the pass-rate distribution

Final r2+ promotion outcomes (17 resources, 1 unwinnable excluded):

| Pass rate | Count | Resources |
|---|---|---|
| 1.00 / 1.00 | **11** | aws-cli, aws-eks, container-analysis, github-actions, gitlab-ci, gitops-argocd, gitops-flux, kubernetes-native, security-validation, terraform-modules, (helm-charts rejected) |
| 0.67 / 0.67 | 4 | crossplane, iac-analyzer, pulumi-cdk, repo-analysis |
| 0.33 / 0.33 | 2 | commands/iac, iac-validator |

Eleven of 17 resources are tied at 1.00 — the candidate and baseline both pass everything. This is **better than Run #6's mostly-0.67 distribution**, but the dominant failure mode is now "scenario passes regardless of which arm runs it." The cost gate is currently doing all the discrimination work (it's the only gate that can reject a tied-at-1.00 outcome), which is exactly the wrong way around — we want quality signal first, cost as a guardrail.

This is the canonical § 3.2 problem (eval-design discrimination), upgraded from "biggest signal-quality lever" to "**the** outstanding Phase B prerequisite." A bootstrap-CI on win rate over scenarios where both arms pass 100 % of the time has nothing to bite into. **(Refined 2026-06-13: the prerequisite is met by the empirical floor-arm discrimination audit (§ 3.7 A2), which outranks the architect-prompt fix; and the win-rate metric itself is degenerate — § 3.5.6.)**

### 3.5.3 Trajectory graders on content-only agents are structurally unwinnable

`agents/iac-generator.md` was marked unwinnable (0/0 on both arms, all 3 scenarios). Inspection of the eval suite shows why: its scenarios use trajectory graders asserting `tool_called: Write` (and `min_count: 3` on the K8s stack scenario). But agent-definition files are loaded as system prompts by Claude Code's Task tool — they don't actually invoke tools themselves during eval, because the eval harness runs the prompt as content, not as a sub-agent.

```yaml
- id: easy-generator-dockerfile-01
  target_resource: "agents/iac-generator.md"
  level: trajectory
  graders:
    - type: trajectory
      assertions:
        - kind: tool_called
          tool: Write          # ← always fails: the eval harness can't actually invoke Task
```

The pattern: **trajectory graders only make sense for resources that ARE themselves executable tool-calling units (skills with tools, commands that run subprocesses)**, not for agent system prompts. Run #8's eval suite has 8 trajectory graders out of 98 total; iac-generator gets 6 of those 8 (the other 2 are correctly applied to iac-validator and iac-analyzer scenarios). F20 in [PHASEA_SUMMARY § 3.3](./PHASEA_SUMMARY.md#33-queued-f-series-defects) noted this for `commands/*` and is mitigated for commands; the same pattern applies to generator-style agents and isn't yet caught.

The architect prompt needs an explicit routing rule: `resource_type=agent AND content-mode (no executable tools listed)` → use llm_judge graders, not trajectory.

### 3.5.4 Where ITERATE wall time actually goes

ITERATE dominates the pipeline at **1h 22m of 2h 09m (63 %)**. Breakdown:

| Round | Resources iterated | Wall time | Notes |
|---|---|---|---|
| r1 | 18 (all) | ~29 m | At concurrency=4; 4 batches of ~5 resources |
| r2 | 11 (cost rejections + 2 refines) | ~17 m | Down from 57 m in run #7 — I15 verdict-branched feedback let the optimizer trim correctly first try |
| r3 | 1 (helm-charts) | ~36 m | Helm-charts went deep; v3 still rejected |

The r3 helm-charts iteration alone burned ~36 minutes — half of r2's total. Two reads on this: (a) helm-charts is genuinely hard (see § 3.5.1), and (b) when the gate is wrong, the iteration cost is unbounded. Capping r3 cost or auto-skipping a resource after 2 cost-rejections in a row would save ~30 min on similar pathological cases.

`ITERATE_CONCURRENCY=4` could plausibly move to 6 — GENERATE already runs 8-way successfully (F18), and ITERATE uses the same model rate window. Test in next smoke run.

### 3.5.5 EVAL_DESIGN cost has roughly doubled

`EVAL_DESIGN` took 14m 43s in run #8 vs 6m 27s in run #6. The eval-architect now runs in an isolated SDK session (refinement 4.1) and the architect prompt has grown to include the held-out reservation logic, suite-hash invariants, and cost-gate exemption guidance. The trade is intentional — isolation buys reproducibility — but worth knowing: if EVAL_DESIGN regresses past ~20 m the architect prompt has likely accumulated cruft and needs a pruning pass.

---

### 3.5.6 Cross-resource-type confirmation + the degenerate win-rate metric (2026-06-13)

The 2026-05-26 `workspace/mobile-dev` run (current `main`; a non-iac resource type — Android/iOS/Flutter/RN skills + agents) confirms the § 3.5.2 flat-signal finding is not iac-specific and sits *upstream* of the gate:

- **`win_rate ≡ 0.00` on all 32 eval-results**, including resources where candidate pass-rate clearly beat baseline (mobile-unit-testing 0.67→1.00; mobile-accessibility 0.00→0.33). The per-scenario `win_rate` metric is **degenerate** — `no_decision` (driven by contains-dominated, judge-starved suites) eats the head-to-head comparisons before they count. **This upgrades § 3.5.2: Phase B's planned bootstrap-CI targets a metric that is ≈0 by construction.**
- **23% unwinnable** (5/22) vs ~6% on iac-team — the uniform grader recipe transfers worse to a different resource type.
- `mobile-tester` iterated v1→v3→v5, every round `reject_floor` — the optimizer drove it *below* the bare-model floor three times.
- Measured grader mix (run #8 suite): **0 `llm_judge`** of 98 graders; the quality signal was entirely keyword-substring matching.

These data drive the discrimination-first turn (§ 1.1) and Phase A.5 (§ 3.7). Archive runs `python-expert` / `iac-team-v1..v3` / archive `mobile-dev` are **pre-Phase-A (Jan–Feb 2026)** and `iac-team-v4` is **pre-3-stage-gate (May 13)** — see the timestamp anchoring in [EVAL-RESEARCH-2026-06.md](./EVAL-RESEARCH-2026-06.md); do not read their gate stats as current.

---

## 3.6 Low-hanging perf wins (do these before Phase B)

Ranked by **(impact, effort)**. The first three would have meaningfully changed Run #8's outcome.

> **Superseded ordering (2026-06-13).** The discrimination-first reassessment (§ 1.1) re-ranks this list and folds the top items into **Phase A.5 (§ 3.7)**. Two entries are *corrected*, not kept: **#1** (cache baseline CPS) → *multi-sample then cache* (§ 3.7 A4); **#4** (architect discrimination *instructions*) → demoted to a *supplement* behind the empirical floor-arm audit (§ 3.7 A2). The table is retained for provenance.

| # | Fix | Impact | Effort | What it changes |
|---|---|---|---|---|
| 1 | **Cache `baseline_cost_per_success` per `(resource, eval_suite_hash)`** | HIGH | LOW (~30 LoC in `gating.py` + 2 tests) | Eliminates the 2.1× round-to-round baseline-CPS variance (§ 3.5.1). helm-charts would have promoted on r3 (candidate $0.23 vs cached r1 baseline $0.15 → +53 %, still reject — but at least deterministic). Combine with #2 for the full effect. |
| 2 | **Absolute τ floor: `cost ≤ max(baseline × 1.10, baseline + $0.05)`** | HIGH | LOW (~10 LoC in `gating.py` + 3 tests) | Small absolute differences (a few cents) shouldn't trigger relative-percent rejections. helm-charts r3 would promote ($0.23 − $0.19 = $0.04 < $0.05). Doesn't help the noise problem on its own; pair with #1. |
| 3 | **Architect grader-routing rule by resource type** | HIGH | MED (~60 LoC in `cgf-eval-architect.md` + new tests in `test_eval_suite_schema.py`) | Generator-style agents get `llm_judge` not `trajectory`. iac-generator stops being unwinnable. Catches the F20 pattern for the agent class. |
| 4 | **Scenario discrimination instructions in architect prompt (§ 3.2)** | HIGH | MED (~80 LoC in `cgf-eval-architect.md` + 2 prompt-eval scenarios) | The architect must mentally run v0 against each scenario and confirm a regressed version would actually fail differently. Cuts tied-at-1.00 dominance. **The outstanding Phase B prerequisite.** |
| 5 | **GENERATE target word-count guidance in `context-engineer.md`** | MED | LOW (~20 lines of prompt) | Run #8 average word count: 8,400 (median 7,500). Optimizer trims ~50 % in r2. Telling context-engineer "target 4,000–5,000 words for SKILL.md unless complexity justifies more" front-loads the trim. Reduces r1 cost rejections directly. |
| 6 | **Auto-skip resource after 2 consecutive cost rejections** | MED | LOW (~15 LoC in `_orchestrator_phases/execution_eval.py`) | helm-charts burned ~36 min on r3 ITERATE for a candidate that still failed. After 2 cost rejections, mark `cost_unwinnable` (parallel to `unwinnable` for pass=0) and stop. Operator can rerun with relaxed τ if desired. |
| 7 | **Raise `CGF_ITERATE_CONCURRENCY` 4 → 6** | LOW | LOW (env knob) | Same model + rate window as GENERATE at 8-way. ~15–20 % wall-time win on ITERATE r1. Test in next smoke. |
| 8 | **Pre-flight architect dry-run after GENERATE** (I9 prerequisite) | MED | MED (~80 LoC) | Before ITERATE r1, run a cheap architect call: "given these 18 resources, which look unwinnable for the scenarios you'd write?" Pre-flag unwinnable resources and skip the ITERATE work. Pairs naturally with I9's GENERATE-output persistence in Phase D. |
| 9 | **Per-resource-type τ profile in `eval_profile.yaml`** | MED | MED (~40 LoC + schema) | Some resource types (large reference skills like `aws-eks`) genuinely need more content. A per-type τ override sidesteps the "every type uses 10 %" pathology. **But** waits on I16 empirical tuning data; doing this without data risks gold-plating. |
| 10 | **`trials=2` default for production cadence** | LOW | LOW (env knob) | Smooths pass-rate distribution mildly without the 3× cost of `trials=3`. Run #8 used `trials=1`; ties at 1.00 may partially be artefacts of single-trial noise. |

**Fixes 1, 2, 3, 5, 7** are ~3 hours of work and would meaningfully change the next smoke run's outcome. Fix 4 is half-to-full-day prompt engineering and is the Phase B prerequisite. Fixes 6, 8, 9, 10 are nice-to-haves that can land alongside Phase B work.

---

## 3.7 Phase A.5 — Signal-quality restoration (discrimination-first)

**New phase (2026-06-13), sequenced before Phase B.** Goal: make the quality signal *discriminate* before any statistical gate is built on top of it. Posture (owner decision): **cascade-gated judge** — deterministic checks act as a cheap pass-gate; the judge fires only on scenarios both arms pass (where discrimination is actually needed), capping judge spend while restoring signal. Grounding: [EVAL-RESEARCH-2026-06.md](./EVAL-RESEARCH-2026-06.md).

**Status (2026-06-13):** **A1 shipped** (`55ef803`) — `eval_strategy` grader routing + post-design enforcement, +22 tests. **A2 *measure-and-surface* shipped** — per-resource `eval/results/.../discrimination-audit.json`, `harness.eval.discrimination_*` span attributes, and an under-discrimination WARNING, reusing the floor arm at no extra eval cost (`CGF_DISCRIMINATION_MIN_FLIP_RATE`, default 0.40), +18 tests. A2 Step 2 (auto-prune / regenerate non-discriminating scenarios) is the queued follow-up. **A3 shipped** — the judge moved from a 1–5 hard-argmax scale to an anchored **1–7** scale (`(score-1)/6`) with per-level anchors + a length/style-bias guard, +3 tests updated; criterion-decomposed sub-scores deferred (logprob-weighting needs Anthropic logprobs the Messages API lacks). **A4 step 1 shipped** — absolute cost-per-success floor: the cost ceiling is `max(incumbent × (1 + τ_eff), incumbent + CGF_COST_ABS_FLOOR_USD)` (default $0.05), so a few-cents delta can't trip the relative gate against a noisy baseline (fixes the helm-charts run-#8 false-rejection), +4 tests; multi-sample-baseline + cache-the-estimate is A4 step 2 (deferred — needs runner/state changes + smoke validation). **A5 + A6 shipped** — the eval-architect prompt is rewritten discrimination-first (every scenario must carry a grader the v0 baseline fails; the `contains`-aggressive / `llm_judge`-avoidant / "completion-latency-not-coverage" framing is inverted) and given a capability model (reads each resource's v0 baseline + generated version — `eval_design.py` now passes both paths — to ground scenarios in the real v0→v1 gap; `max_turns` 10→20, turn budget relaxed). **Phase A.5 implementation complete (A1–A6).**

**Verified 2026-06-13** via a one-shot EVAL_DESIGN probe (`scripts/derisk_eval_design.py`) against the real iac-team resources: **28 `llm_judge` graders vs run #8's 0, 18/18 resources with a discriminating grader, 0 trajectory-on-content**, rubrics grounded in concrete v0→v1 capability gaps — the discrimination-first turn works as intended. The probe also surfaced a cost finding (EVAL_DESIGN 17m54s / 74 turns reading 36 v0+v1 files, near the 1200s timeout; `max_turns` not enforced) → **§ 3.7.2**. Full smoke (A2/A4 runtime + end-to-end promote-rate) still pending.

| ID | Task | Effort | Detail |
|---|---|---|---|
| **A1** | **Make `eval_strategy` load-bearing — grader routing by resource type** | ~60 LoC + tests | `resource_types.py` already tags `content_only` / `content_and_execution` / `executable` / `server`, but the field has **zero read-sites**. In EVAL_DESIGN, resolve each resource's `eval_strategy` and pass an allowed/forbidden grader-type set into the architect as a hard constraint. Route content-only (skill, command, hook, plugin, **and agent-definition files with no executable tools**) → `llm_judge` rubric + deterministic content checks, **never trajectory**. Route `executable`/`server` + tool-dispatching agents → trajectory + outcome. Replace the hardcoded level-mix table in `cgf-eval-architect.md`. **Kills the `iac-generator`/mobile unwinnable class by construction.** (was § 3.6 #3, promoted) |
| **A2** | **Empirical discrimination audit (reuse the floor arm)** — *Step 1 shipped* | ~120 LoC + 18 tests | The per-scenario bare-model floor arm already exists (`ScenarioResult.floor`) and was collapsed into one `floor_pass_rate`. **Shipped:** `eval_harness/discrimination.py` classifies each scenario by comparing the candidate arm to the floor arm — `discriminating` (cand > floor), `inverted` (cand < floor), `saturated` (both pass), `dead` (both fail), `indeterminate` — and computes a **flip rate** (discriminating / classifiable). EXECUTION_EVAL runs the audit per resource at no extra eval cost (reusing the floor arm that runs at first promotion), writes `discrimination-audit.json`, stamps `harness.eval.discrimination_*` span attributes, and logs a prominent WARNING when `flip_rate < CGF_DISCRIMINATION_MIN_FLIP_RATE` (default 0.40). This makes the run-#8 flat-signal pathology *visible* (it would surface as flip_rate≈0, mostly `saturated`). Observational — never gates. **Step 2 (queued):** drop / auto-regenerate `saturated`+`dead` scenarios once the audit data is validated against a smoke run (deferred so we don't destabilise the gate population / suite-hash before the signal is trusted). **Outranks the architect-prompt fix** — grounds discrimination in *observed*, not *imagined*, behavior. (supersedes § 3.6 #4 as the lead lever) |
| **A3** | **Judge scale fix — anchored 7-pt** — *shipped* | ~40 LoC + tests | **Shipped:** `llm_judge.py` moved from a 1–5 hard-argmax scale (frontier judges compress it to 2–3 effective points; retry→tie collapses it to 3 classes) to a **7-point scale with one-sentence anchors per level** (`(score-1)/6`), plus a "judge against the rubric only — length/formatting/confident phrasing are not quality" guard against verbosity/style bias. Parser, normalization, schema + architect rubric guidance, and the fallback rubric all updated to 1–7. **Deferred:** criterion-decomposed sub-scores; G-Eval probability-weighting needs token logprobs the Anthropic Messages API does not expose. (was NEW, P0 — omitted from the prior plan) |
| **A4** | **Cost gate de-noising** — *step 1 shipped* | ~30 LoC + 4 tests | **Shipped (step 1 — absolute floor):** the cost ceiling is now `max(incumbent × (1 + τ_eff), incumbent + cost_abs_floor)`, `cost_abs_floor = CGF_COST_ABS_FLOOR_USD` (default $0.05). A few-cents absolute CPS regression no longer trips the relative-percentage gate against a noisy single-draw baseline — fixes the helm-charts run-#8 false-rejection (rejected 3× on a ~$0.04 delta at quality ~1.0). `GateInputs.cost_abs_floor_usd` defaults 0.0 so existing callers stay pure-relative. **Deferred (step 2 — the variance cure):** multi-sample the baseline arm (n ≥ 5, amortised — runs once per resource via F17) and cache the stable estimate per `(resource, eval_suite_hash)`, gating on a ratio statistic; needs runner per-arm trial control + a state-cache schema, so it lands after smoke #9 validates the floor. τ stays uncalibrated → Phase D / I16. (revises § 3.6 #1 + #2) |
| **A5** | **Discrimination-first architect rewrite** — *shipped* | ~80 LoC prompt | **Shipped:** inverted `cgf-eval-architect.md`'s cost-first framing — the "write in 2-3 turns / use contains aggressively / use llm_judge only when contains can't / optimizer-for-completion-latency-not-coverage" directives are replaced by a **discrimination mandate**: every scenario MUST carry ≥1 grader the v0 baseline is expected to FAIL (HealthBench / BiGGen partial-credit pattern), pick the grader that *discriminates* (llm_judge / code for quality, not reflexive `contains`), and "ship a scenario both arms pass" is now an explicit anti-pattern. (reframes § 3.6 #4) |
| **A6** | **Give the architect a capability model** — *shipped* | ~40 LoC prompt + eval_design | **Shipped:** the architect no longer designs blind. Removed the "DO NOT read resource files" prohibition; `eval_design.py` now passes each resource's **v0 baseline + generated** paths and instructs a capability-diff (`_resource_block`), so scenarios target the real v0→v1 gap. `max_turns` 10→20 and the turn budget relaxed (turn-15 hard-stop) to afford the reads; prompt warns "skim for capability, don't transcribe implementation" to avoid overfitting. Reading artifacts is not an isolation breach — the 4.1 contract forbids the optimizer's *reasoning*, not the files. (§ 3.7.1 Q1/Q2 cost+overfit tradeoffs noted; full-suite read cost validated by smoke #9.) |

**Carry-forward from § 3.6 (unchanged):** #5 GENERATE word-count guidance, #6 auto-skip after 2 cost rejections, #7 `CGF_ITERATE_CONCURRENCY` 4→6. Defer #8 pre-flight dry-run, #9 per-type τ profile, #10 trials default behind A1–A4 and Phase D data.

**Sequencing:** ship A1–A4 (+ A5/A6) → run **smoke #9** → then open Phase B on a suite that finally discriminates.

**Exit criteria:** smoke #9 on the iac-team fixture shows (a) zero 0/0-both-arms (mis-routing) unwinnables, (b) tied-at-1.00 fraction materially below run #8's 11/17, (c) `win_rate` non-zero on a meaningful fraction of resources. ~30–40 new unit tests.

### 3.7.1 Open questions (carried from the reassessment)

1. **Judge-coverage cost.** Lifting `llm_judge` from ~0–5% toward every discrimination-tier scenario raises eval cost (judge calls dominate). The cascade (judge only where both arms pass) is the cap; confirm it holds the bill on the iac-team fixture.
2. **Architect isolation vs. capability model (A6).** "No reading resource files" was deliberate isolation to stop the architect over-fitting scenarios to the implementation. Lifting it for v0↔v1 capability-diffing reintroduces that risk — scope strictly to the *diff*, or feed transcripts only.
3. **Scenarios/trials budget (Phase B Task 3).** Raising both is the precondition for any statistical gate but multiplies cost linearly. Target decisive-N (~10–15) vs the per-run budget ceiling is an open trade.
4. **Ledger ownership & staleness (Phase E).** Who curates anti-patterns; how to stop the ledger ossifying around the iac-team fixture before cross-domain runs exist.
5. **Phase-ordering risk.** If smoke #9 (post A1–A4) *still* shows flat `win_rate`, the problem is deeper than grader resolution (a genuine resource-quality ceiling) — then invest in harder scenario generation (IRT pruning / hard-negative mining, deferred to Phase D) before Phase B.
6. **Pairwise disagreement (Phase B Task 1).** If order-disagreement is < 5% on Opus/Sonnet as the 2026 data predicts, skip the second ordering and break ties on the continuous score — never a silent tie.

### 3.7.2 EVAL_DESIGN cost finding + improvement candidates (2026-06-13 probe)

The `scripts/derisk_eval_design.py` probe confirmed A1/A3/A5/A6 produce a discriminating suite, and quantified the A6 cost flagged as § 3.7.1 Q1:

- **Cost:** EVAL_DESIGN took **17m54s / 74 turns** for the architect to read 36 v0+v1 files and write 54 scenarios — finishing only ~2 min under the `CGF_EVAL_DESIGN` 1200s timeout. The reads dominate (the suite write was the last ~4 min). At 18 resources this is near the ceiling; a larger plugin or slower run risks timing out → no suite → the eval half of the pipeline skips.
- **`max_turns` not enforced:** the agent frontmatter says `max_turns: 20`; the architect ran **74 turns**. The harness logs `max_turns=20` to the SDK, but the wall-clock timeout is the only effective cap — so bumping 10→20 (A6) was a no-op and the budget can't be reasoned about. A correctness bug to fix.

**Approaches considered.** EVAL_DESIGN is the hardest single judgement in the pipeline; higher cost is acceptable, but signal return must justify it. Candidates evaluated (the agreed plan is § 3.7.3):

| # | Approach | Effect |
|---|---|---|
| 1 | **Shard + fan out** — replace the one monster call with N parallel per-resource (or small-batch) architect calls, each reading only its own v0+v1. | Cuts per-call turns ~10×, parallelizes wall time, sharpens per-resource focus, makes `max_turns` enforceable (small bounded calls). More total tokens, far less wall time. The "workflow/methodology" direction. |
| 2 | **Python-computed capability diff** — feed a concise `v0→v1` diff (difflib) instead of two full files. | Smaller context, more targeted ("what changed = what to test"). Pairs with #1. Cheap, high-leverage. |
| 3 | **Empirical discrimination loop** — after authoring, run floor+candidate on the scenarios, drop non-discriminating, regenerate (A2 step 2 folded into design). | Maximises signal; adds eval cost at design time. Thoroughness lever; tiered / opt-in. |
| 4 | **Tiered depth by resource** — deep-read+judge complex resources; metadata+contains for trivial ones. | Cost control; risks under-testing "trivial" resources. |
| 5 | **Reuse via the learnings ledger (Phase E)** — cache discriminating scenarios per resource type across runs. | Amortises design cost; longer-horizon (depends on Phase E). |
| 6 | **`max_turns` enforcement fix** — find why the frontmatter cap is ignored on the `call_agent_simple` path; make it bind. | Correctness; required regardless. #1 makes a tight cap viable. |

### 3.7.3 EVAL_DESIGN v2 — agreed plan (2026-06-13)

**Decision:** build EVAL_DESIGN v2 now (before A7 / later stages), **incrementally and empirically** — ship each step, verify with the `derisk_eval_design.py` probe, document, then proceed. Target = a fan-out/merge orchestration with a type-adaptive aspect panel inside each shard, built in **two layers with a measurement gate**.

**Layer 1 — fan-out/merge orchestration (single architect per shard):**

- **L1.1 — `max_turns` enforcement + turn/tool-counting fix** — **SHIPPED** (`c87322b`). Root cause: the SDK forwards `--max-turns` to the CLI but it didn't bind (architect ran 73 turns at 20); separately `extract_tool_calls` checked `block.type == "tool_use"` but the SDK's `ToolUseBlock` is class-typed (no `.type` field) so it read 0 ("0 tool calls") and tool-bearing turns inflated the display. Fix: `call_agent` tracks assistant turns and **breaks at `max_turns`** (graceful, like the timeout path; caller keeps what was produced); counters corrected; architect frontmatter `max_turns` 20→120 for the monolithic interim (→ ~15 per-shard in L1.3). +2 tests.
- **L1.2 — v0→v1 capability-diff helper** — **SHIPPED** (`5928e27`). `_orchestrator_helpers.capability_diff(v0_text, v1_text, *, label, max_lines)` → truncated unified diff, with markers for new-resource (no v0) and identical. +5 tests. (Consumed by L1.3; not yet wired into the phase.)
- **L1.3 — shard the EVAL_DESIGN phase** — **SHIPPED (impl + unit tests green; container probe is the immediate next step).** Replaced the single monster `delegate` call in `_orchestrator_phases/eval_design.py` with **parallel per-resource architect calls + a Python merge**. As built:
  - **(a)** add a `max_turns` override param to `subagent.call_agent` / `call_agent_simple` (so a shard sets ~15 without touching frontmatter; ties into the L1.1 enforcement).
  - **(b)** rewrite `delegate`: per eligible resource, compute `capability_diff` (L1.2) over v0/v1 read in Python and embed it INLINE in a per-resource prompt (resource path/type + purpose + grader policy + diff; SPEC + eval_criteria as optional reads), call the architect to write a mini `eval-suite.yaml` to `eval/shards/{slug}.yaml`; run all shards in parallel under a new `CGF_EVAL_DESIGN_CONCURRENCY` (default ~4–6) semaphore.
  - **(c)** merge: read the shard files, collect `scenarios`, assemble `eval/eval-suite.yaml` (version / target_resource / config + merged scenarios), then the existing `_enforce_grader_policy` (A1) + `eval_suite_sha256` + telemetry (preserve the no-suite error + timeout/exception paths).
  - **(d)** partial failure: a shard with no output → that resource has no scenarios (log + continue); ALL fail → the existing no-suite error path.
  - **(e)** reframe `cgf-eval-architect.md` for **per-resource mode** ("design for the ONE resource your task names; write a valid eval-suite.yaml fragment to the given path") and set frontmatter `max_turns` → ~15.
  - Tests: `test_eval_design_sharding.py` (40 cases — slug / merge / prompt-builder / purpose-loader / env-resolvers); `test_orchestrator_eval_design_phase.py` + `test_f11_eval_design_resume.py` rewritten for the sharded contract (happy / no-signal / all-fail-raises / partial-proceeds / timeout-raises); `test_subagent.py` +1 for the `max_turns` override. The LLM calls themselves verify via the `derisk_eval_design` probe. **Per-resource is the default granularity.** Full unit suite green (2165), my-code ruff + mypy clean.
  - **Contract changes (deliberate):** (i) signal parsing dropped — the shard file on disk is authoritative (a written shard with scenarios = success, no signal needed); (ii) **all shards failing → raise** the no-suite error (the monolith soft-skipped on a single timeout), so EXECUTION_EVAL never silently runs without a suite; (iii) **partial failure proceeds** with the surviving resources' scenarios (a dead shard just yields no coverage for that one resource). New knobs `CGF_EVAL_DESIGN_CONCURRENCY=5` + `CGF_EVAL_DESIGN_SHARD_MAX_TURNS=15` (`.env.example` + optimization/CLAUDE.md env table). `cgf-eval-architect.md` frontmatter `max_turns` 120→15 and reframed per-resource (works from the inline diff; optional reads only). Each merged scenario is stamped with its shard's `target_resource` so the single merged top-level can't mis-route other shards' scenarios.
- **Measure (probe — IMMEDIATE NEXT):** run `scripts/derisk_eval_design.py` in the container against a copied multi-resource workspace; confirm EVAL_DESIGN wall-time + per-shard turns drop sharply, `max_turns` binds per shard, and discrimination holds (llm_judge present, 0 trajectory-on-content, scenarios v0 fails). Document before/after. Needs `make build && make up` (no image yet).

**Layer 2 — type-adaptive aspect panel inside each shard (after L1 + measurement):**

- Replace the single per-shard architect with **2–3 aspect-agents keyed by resource type** (a *simplified* catalog v1 — e.g. skill → {accuracy + currency, completeness, token-efficiency}; agent → {accuracy + doc-fidelity, workflow/sequencing, coverage}; mcp_* → {contract correctness, error-handling, idempotency}), each proposing scenarios from its lens on small context, in parallel.
- **One synthesis pass** pools the proposals: dedupe, **drop any scenario without a v0-failing criterion**, balance difficulty + held-out, apply A1 routing, write the resource's scenarios.
- **Measure (probe):** does the panel beat single-architect-per-resource enough to justify ~3× design calls, and for which resource types? Keep it where it pays.

**Deferred (noted now, built later):**
- **Sector-specific lenses / refined generation+eval research methodology** — the catalog starts type-keyed only; sector/domain-adaptive lenses are a later research-methodology pass of their own.
- **Cross-critique *round*** (aspects critique each other before synthesis) — single synthesis pass first; add a round only if the data shows the synthesizer misses things.
- **"By design" eval-grouping** — when inter-related resources need batching / cross-resource scenarios, the resource-architect (DESIGN) records an `eval_group` + `cross_resource` flag in `resource-plan.yaml` that L1.3 consumes; until a fixture needs it, per-resource sharding is the default (build when it helps, per the incremental approach).
- **Empirical discrimination loop** (candidate #3 / A2 step 2), **tiered depth** (#4), **ledger reuse** (#5) — later thoroughness/cost levers.

Sub-tasks ship as small commits with probe verification each; this section is the running ledger.

---

## 4. Phase B — Statistical promotion gating

End-state: the simple threshold from Phase A is replaced by a multi-signal statistical gate. Same data shape as Phase A — this is gating logic only.

### 4.0 Decisions facing Phase B kickoff

Four open decisions, each with the data from § 3.5 informing the recommendation. None are unilaterally blocking — the recommendation is to land § 3.6 fixes 1–5 in a short "Phase A.5" branch first, then open Phase B with cleaner signal.

> **Resolved (2026-06-13).** **Decision A** → the empirical floor-arm discrimination audit (§ 3.7 A2) is the prerequisite; the architect-prompt work (A5/A6) is a *supplement*, not the lead. **Decision B** → land the architectural cost-gate fix now as *multi-sample + cache* (§ 3.7 A4), not cache-single-draw; empirical τ tuning stays in Phase D (I16). **Decision C** → grader-routing by `eval_strategy` (§ 3.7 A1) fixes the generator-agent class wholesale. **Decision D** → yes — run smoke #9 after Phase A.5, before opening Phase B. Phase B itself is **re-scoped** below (Beta-Binomial replaces bootstrap; pairwise becomes the per-scenario decision).

| # | Decision | Options | Recommendation |
|---|---|---|---|
| A | **Invest in § 3.2 architect prompt OR proceed with flat signal?** | (a) Spend half-to-full day on scenario-discrimination prompt before Phase B. (b) Skip and let bootstrap-CI tighten the existing tied-at-1.00 signal. | **(a).** A bootstrap CI lower-bound > 0.5 on 11 of 17 resources where both arms pass 100 % is wasted statistical power. The architect-prompt work is the cheapest signal-quality lever in the project and is the prerequisite the roadmap has named for two months. |
| B | **Tune τ empirically (Phase D, I16) OR architecturally (cache + absolute floor) NOW?** | (a) Defer all τ work to I16's data collection in Phase D. (b) Land § 3.6 fixes #1 + #2 now (architectural), defer empirical tuning to I16. | **(b).** The cache + absolute floor fix the failure mode shown by helm-charts × 3 in Run #8 — that's a structural correction, not parameter tuning. I16 still has work to do (finding the right relative τ on top of these fixes), but doing nothing while waiting on I16 ships another smoke with the same noise. |
| C | **`agents/iac-generator` unwinnable — redesign / drop / accept?** | (a) Architect grader-routing fix (§ 3.6 #3) — generator agents get llm_judge. (b) Manually rewrite iac-generator's 3 scenarios. (c) Drop the resource from the suite. (d) Accept "unwinnable" and move on. | **(a).** The grader-routing fix solves the entire generator-agent class, not just iac-generator. ~60 LoC and a prompt-eval. The other options leave the architectural bug in place. |
| D | **Re-run smoke before opening Phase B?** | (a) Land § 3.6 #1–#5, run smoke #9, then decide. (b) Open Phase B in parallel with a smoke run. (c) Skip smoke and go straight to Phase B. | **(a).** A clean smoke run with the architectural fixes lands the dataset Phase B's bootstrap-CI tests against. Going straight to Phase B means debugging the gate and the dataset noise simultaneously. |

**Refresh note (post Phase A, post Run #8 — 2026-05-19):** Phase B's value depends on signal quality. Bootstrap CIs on tied-at-zero (or tied-at-one) scenarios don't help. § 3.1 (eval-as-Opus-agent) is shipped (refinement 4.1). § 3.2 (discriminating scenarios) and § 3.5.1 (cost-gate baseline noise) are the outstanding prerequisites — both addressable in 1–2 days of work per § 3.6, before opening Phase B.

**Tasks (re-scoped 2026-06-13 — depends on Phase A.5 landing first; see § 1.1):**

1. **Pairwise judge as the per-scenario *decision*** (not an absolute add-on). `src/harness/optimization/eval_harness/pairwise.py`. The gate consumes a per-scenario win; pairwise should *produce* it, with the now-continuous anchored absolute score (§ 3.7 A3) retained only for monitoring/feedback. **Disagreement handling: do NOT silently emit a tie** — break it on the continuous absolute-score margin, or draw one tie-break sample. 2026 measurements put order-disagreement on frontier judges at ≤ 0.04 and mixed-sign, so log the disagreement rate and consider dropping the second ordering (saves 2× judge cost) if it is empirically < 5%. (Position-bias background: Wang et al. 2024.)
2. **Beta-Binomial posterior gate on paired discordant outcomes** (replaces the bootstrap CI). `gating.py`. The arms are paired (same scenarios), so gate on the discordant pairs (exactly one arm passed) and promote iff the 5th percentile of `Beta(k + 0.5, N − k + 0.5)` (Jeffreys prior) > 0.5. The percentile bootstrap is undefined-in-practice at decisive N ≈ 3 (only 4 distinct point estimates) and under-covers below N ≈ 20 (arXiv 2503.01747); the Beta posterior is exact at any N (~10 LoC). **Abstain (don't fire) below a decisive-N floor (~10–15)** rather than promote/reject on noise. Decision + full stats → `reviews/v{n}_eval.json` alongside `v{n}_review.md`.
3. **Raise statistical power (precondition for Task 2).** `trials_per_scenario` → 3 and scenarios-per-resource well above the current 3 — no gate has power at decisive N ≈ 2, and the old `len(wins) < 10` floor was structurally unreachable at 3 scenarios/resource. Bounded by `CGF_EVAL_TOKEN_BUDGET`; the cascade (§ 3.7) keeps the judge-call multiplier in check.
4. **Treat `no_decision` / unbreakable tie as 0.5 (half-win), not discard.** `aggregate.py` currently drops them, collapsing effective N when `no_decision_rate` runs 0.33–0.67 (as in the mobile-dev data). Half-credit preserves N for Task 2.
5. ~~**Token-regression check.**~~ **Shipped in Phase A polish** (refinement 4.3); de-noised in Phase A.5 A4. `Gate.decide()` enforces `candidate.cost_per_success ≤ baseline × (1 + τ)`, `τ = CGF_TOKEN_REGRESSION_TOLERANCE` (default 0.10), cost from `ResultMessage.total_cost_usd`; per-scenario opt-out `cost_gate_exempt: true`.
6. **Trigger accuracy for agents/skills.** Scenarios already carry positive + negative trigger contexts; compute precision/recall, gate at default precision ≥ 0.9, recall ≥ 0.8. Tunable per resource via `eval_profile.yaml`.
7. **Trajectory argument-correctness.** Where trajectory graders apply (executable resources only, post-A1), require `with_arg` / BFCL-style AST argument checks + a goal-progress check — presence-only `tool_called == True` is reward-hackable.
8. **Multi-signal gate.** All applicable signals (paired Beta-Binomial win posterior, token regression, trigger precision/recall) must clear. Single `Gate.decide()` entry point; verdict shape `Promote | Refine | Reject`. Full statistics in the review file.

**Exit criteria:**

- Opens only after Phase A.5 + smoke #9 confirm a non-degenerate `win_rate`. A candidate that passed Phase A's threshold but fails any signal is rejected with full statistics. **Reproducibility:** identical traces → byte-identical verdicts.
- ~30 new tests (Beta-Binomial + paired-test math, pairwise position/disagreement handling, `no_decision` half-credit).

---

## 5. Phase C — Ephemeral runtime

End-state: identical inputs → byte-identical eval verdicts across runs and hosts. SWE-bench reports 99.78% determinism on this pattern.

**Tasks:**

- `agents/main/Dockerfile.eval` — layered build: `harness-base` → `harness-eval-base` (adds eval runners, judges, scenario loader) → `harness-eval-instance` (built per resource version, bakes in candidate or baseline artifact).
- New `eval` profile in `docker-compose.yml`:
  - `eval-worker` container with `--rm`.
  - `tmpfs` mounts on `/workspace` and `/memory` (no checkpoint persistence during eval).
  - Trace/metric output streamed to host-mounted persistent volume.
- Pin `CLAUDE_MODEL` to a specific date-stamped version for the eval-run duration; record the pin in `eval-results.json`.
- Disable auto-checkpointing under the `eval` profile.
- One fresh container per scenario instance.
- Make targets: `make eval`, `make eval-arm CANDIDATE=v3 BASELINE=v2`, `make eval-clean`.

**Exit criteria:** Run identical eval twice; `diff` on the statistics section of the review file shows no diff (or differs only in timestamps). ~15 new tests (Dockerfile build smoke, determinism integration test).

---

## 6. Phase D — Calibration & CI

End-state: judges are trusted (Cohen's kappa ≥ 0.8 vs human labels), eval runs on every PR.

**Tasks:**

- HTML viewer for trace + verdict + human-label slot: `scripts/eval-review/`. Reference pattern: skill-creator's `run_loop.py` viewer.
- `make eval-calibrate` — runs N=20–50 pairwise judgments through human review; computes Cohen's kappa per (resource type × judge model × rubric version). Persist scores to `docs/JUDGE-CALIBRATION.md`. Gate refuses to promote when calibration is stale (older than a quarter) or below 0.8.
- If calibration < 0.8 for a resource type, **escalate to judge ensemble** (3 judges, majority vote) for that type. Carries ~3–5× cost vs single judge; use only when needed.
- `.github/workflows/eval.yml` — detect changed resources, run `eval-quick` (held-out subset, fast feedback), post statistics as PR comment. Failing eval blocks merge.
- **Optimizer integration:** `cgf-prompt-optimizer` reads `reviews/v{n}_eval.json` failure entries as critiques (this closes the gradient loop CGF is named after). Limit feedback-driven iterations (max 2 before escalating to human review).
- **I9 — persist GENERATE-only artifact for replay.** Before ITERATE r1 overwrites the canonical `{resource}.md`, the `context-engineer` GENERATE output is captured under a stable name (`{resource}-generated.md` or `-v0.5.md`).  Today's pipeline overwrites it during ITERATE r1, so the calibration dataset can't include "judge-on-fresh-GENERATE" samples — that's a coverage gap in kappa measurement.  ~30 LoC in `_orchestrator_phases/generate.py` + 2 tests.  Land alongside `make eval-calibrate` so the writer and consumer ship together (else the file accumulates with no reader).  Surfaced by iac-team smoke run #7.
- **I16 — empirically tune `CGF_TOKEN_REGRESSION_TOLERANCE` and `CGF_COST_QUALITY_BONUS`.** Current defaults (`τ=0.10`, `bonus_factor=1.0`, `bonus_cap=0.5`) are educated guesses from the multi-objective eval literature.  The right values are data-dependent: collect cost-gate outcomes across runs, have humans label "should have promoted" vs "should have been rejected" on a sample, compute FP / FN rates across candidate τ values, pick the τ that minimises false-promotions.  Same `make eval-calibrate` machinery as the kappa work — calibration consumer #2.  Run #7's 8/18 cost rejections are the seed dataset; need ≥3–5 more runs of similar density to have signal.  Persist tuned defaults to `docs/JUDGE-CALIBRATION.md` next to the kappa scores so operators see both axes in one place.  Surfaced by iac-team smoke run #7's empirical fall-out; quality-scaled τ (I15) softens the worst symptom but doesn't replace empirical tuning of the base.

**Exit criteria:** A PR that regresses a resource gets a failing eval comment within 10 min on GitHub Actions; calibration page shows current kappa per resource type AND tuned cost-gate thresholds; passing PRs get statistics published. ~15–17 new tests (~+2 for I9 persist + 0 for I16 since the tuning is data work, not code work).

---

## 6A. Stage 3 Phase E — Compound learning (the learnings ledger)

**New committed workstream (2026-06-13), distinct from Phase D.** Phase D *calibration* answers "do I trust the judge's score?"; Phase E answers "**what context-engineering moves reliably improve which resource types?**" — and makes that knowledge survive `cgf-clean` so the optimizer starts run 1 of a new resource smarter than it finished run 8 of a similar one. Today nothing persists: the verdict-keyed feedback in `iterate.py` is write-once and discarded at the end of the loop. This is the capability the project brief calls for ("continuously track and record learnings on what works") and that Phase D does *not* cover.

**Design** — append-only, workspace-external store; five layers (from the ExpeL / Reflexion / CLIN / Contextual-Experience-Replay literature; see [EVAL-RESEARCH-2026-06.md](./EVAL-RESEARCH-2026-06.md)):

1. **Run records.** Per ITERATE/EXECUTION_EVAL cycle: `(resource_id, resource_type, sector/domain tags, edit_type, per-grader score deltas, cost delta, verdict)`.
2. **Edit-pattern library.** ExpeL-style induced rules with N-observation confidence intervals — e.g. "for `mcp_tool` + input-schema-validation + `reject_floor`, adding an explicit JSON schema with examples raised pass_rate by avg +0.18 (n = 7)".
3. **Causal map.** edit-move → score-shift, segmented by resource type.
4. **Anti-patterns.** Reflexion-style negatives — moves that *degraded* scores.
5. **Meta-rubric index.** Which rubrics are well-calibrated per `(resource type × judge)` — **the one layer that consumes Phase D's κ output** rather than duplicating it.

**Plug-in points:** **WRITE** at the end of `_orchestrator_phases/execution_eval.py` (the verdict + per-scenario deltas already exist there in the feedback builder); **READ** via a semantic-similarity retrieval step at the start of RESEARCH / ITERATE that injects the top-K edit-patterns + anti-patterns for the current resource type + domain into the optimizer's context.

**Status:** design-stage. Sequenced after Phase A.5/B produce trustworthy per-grader deltas, and after there are cross-domain runs (iac-team + mobile-dev + others) to induce patterns from — inducing a ledger off a single fixture risks ossifying around its idiosyncrasies (see § 3.7.1 Q4). **Exit criteria (draft):** a new-resource optimization measurably benefits from injected prior-run patterns (fewer ITERATE rounds to first promotion, or higher r1 pass-rate) vs a ledger-disabled control.

---

## 7. Stage 4 — Integration & hardening

After Phase D stabilizes. Carries forward from predecessor doc.

### Task 1 — Full pipeline E2E test

`tests/e2e/cgf/test_full_pipeline.py`. Test the complete pipeline from SPEC.md to finalized, evaluated resources:

```
SPEC.md → RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → FINALIZE
```

Approach: simple 2-resource plugin (1 agent + 1 skill); mock external API calls but exercise all Python orchestration code. Verify all phases execute in order, state file updated at each transition, resource files created with correct versions, eval suite generated and executed, final resources pass quality + execution thresholds, CHANGELOG.md populated, no orphaned temp files.

### Task 2 — Checkpoint / resume for new phases

Verify resume from each new phase: DESIGN, EVAL_DESIGN, EXECUTION_EVAL.

- `resource-plan.yaml` preserved on resume from DESIGN.
- `eval-suite.yaml` preserved on resume from EVAL_DESIGN.
- Partial `eval-results.json` loadable on resume from EXECUTION_EVAL.
- Test: kill orchestrator mid-phase, restart, verify correct phase resumes.

### Task 3 — Human review gates

Add `--review` flag with optional checkpoints after DESIGN and EVAL_DESIGN phases. After DESIGN: pause, display resource-plan.yaml summary, wait for `/cgf proceed` or `/cgf edit`. After EVAL_DESIGN: pause, display eval-suite.yaml summary, wait for approval. After EXECUTION_EVAL: pause, display eval-results.json summary with pass^k scores. State tracks `checkpoint_phase` and `checkpoint_approved` for resume.

### Task 4 — Performance optimization

- Parallel eval scenario execution (respecting API rate limits).
- Eval result caching: skip re-running scenarios that passed in previous iteration.
- Generation parallelism for independent resources.
- Timeout tuning: add DESIGN and EVAL_DESIGN timeouts to config.
- Token usage tracking per phase for cost awareness.

### Task 5 — Edge case handling

- Empty eval results (no scenarios generated → skip EXECUTION_EVAL).
- All scenarios fail (every pass^k = 0 → REJECT, don't loop forever).
- MCP server build failure (compilation error → mark resource as failed, continue others).
- Resource-architect proposes 0 resources (invalid plan → error with guidance).
- SPEC has no capabilities section (minimal SPEC → resource-architect uses defaults).
- Agent timeout during eval (individual scenario timeout → mark trial as fail, continue).
- Disk space exhaustion (transcript storage → warn and truncate).
- Circular dependencies in resource plan (validate and reject).
- Research phase produces no findings (proceed with reduced confidence).

### Task 6 — Error recovery and retry

- Configurable retry for agent delegation failures (1 retry with simplified prompt).
- Eval scenario retry for transient failures (API timeout, rate limit).
- Distinguish transient errors (retry) from permanent errors (mark failed).
- Log all retries with structured data for debugging.

### Task 7 — Comprehensive documentation update

- `CLAUDE.md` — full rewrite of CGF section to reflect new pipeline. (Done 2026-05-14: phase→agent table now reflects 9-phase pipeline including QA/EVAL_DESIGN/EXECUTION_EVAL.)
- `README.md` — update user-facing docs with new commands and workflow.
- `docs/CGF-USER-GUIDE.md` — rewritten 2026-05-14 around Phase A flow + Grafana section. The old `docs/CGF-API-REFERENCE.md` (which described a pre-Phase-A state machine that never shipped) was deleted; technical reference now lives in `src/harness/optimization/CLAUDE.md` so it auto-loads when Claude edits eval code.
- `docs/CGF-EXAMPLES.md` (currently archived in `docs/attic/`) — rewrite around Phase A flow with eval-suite-generation + feedback-loop examples, then restore.

### Task 8 — Memory and auto-memory updates

- Auto-memory `MEMORY.md` — update project status, key files, recent work.
- Memory MCP entity for `ab-casdk-harness` — update observations to reflect Stage 3 shipped.

### Task 9 — CREATE-mode support in `cgf_session.py` (single-resource path)

**Why this is here:** the orchestrator prompt (`cgf-orchestrator.md`) documents a CREATE phase that dispatches `context-engineering:context-engineer` to author an initial draft when no resource file exists. The multi-resource `multi_resource_orchestrator.py` path exercises this naturally via its GENERATE phase. The single-resource `cgf_session.py` path, however, hard-codes start-in-`research` and errors out when `_find_resource_path()` returns None — the CREATE branch in the orchestrator prompt is dead code from Python's perspective.

This was surfaced during Phase-1A smoke validation (May 2026) when an attempt to author a Phase-1B "from-zero" smoke fixture revealed the gap.

**Scope (~80–120 LoC + tests + prompt updates):**

- `src/harness/cgf_session.py`:
  - Add `"create"` to `CGF_PHASES`.
  - Detect creation mode: SPEC.md loads successfully but `spec.resource_path` does not exist on disk.
  - Initialize `task_list.current_phase = "create"` in creation mode.
  - Add a `[CREATE_COMPLETE]` signal handler that verifies the file now exists, captures `baseline_hash` at this point, transitions to `"research"`, and records a `create` checkpoint.
  - Defer P0.1 baseline-hash capture until after `[CREATE_COMPLETE]`.
  - Resume support.

- `src/harness/plugins/cgf-agents/agents/design/cgf-orchestrator.md`:
  - Add explicit creation-mode trigger to INIT phase: when the loaded spec's resource file is missing, dispatch `context-engineering:context-engineer` via Task tool, then emit `[CREATE_COMPLETE]` in a separate message after the Task returns AND the file exists.
  - Add `[CREATE_COMPLETE]` to the phase signals table.
  - Add a BAD transcript: dispatching context-engineer AND emitting `[CREATE_COMPLETE]` in the same message → file race.

- `tests/unit/test_cgf_session.py`: ~6–10 new tests.
- `tests/smoke/python-expert-create/` fixture derived from `workspace/python-expert/python-expert-v1.md`.

**Dependencies:** none — can ship independently. Doesn't interact with Stage 3 Phases B–D.

**Out of scope here (Stage 5+):** legacy `--agent NAME` CLI flag for creation mode without SPEC.md. Keep CREATE driven exclusively from SPEC.md.

---

## 8. Cross-cutting harness work

Items unrelated to the eval framework but worth addressing when bandwidth allows.

### Sub-agent `HOME` mismatch

When sub-agents (e.g., `research-team:research-specialist`) expand `~` in paths via Bash, it sometimes resolves to `/root` while the runtime user is `claude` (`$HOME=/home/claude`). The subsequent Write tool fails with `EACCES`. Three fix candidates queued; (a) explicit `HOME=/home/claude` env passthrough in `_build_sdk_options()` is the leading suspect.

### `make interactive` terminal UX audit

Corrupted Rich panel borders, repeated "Thinking…" displays, verbose logs interleaved with conversation. Audit `harness/cli.py`, `harness/interactive.py`, possibly `harness/agent_progress.py`.

---

## 9. Build improvements

Tier 1 + 2.3 + 2.4 from the 2026-05-07 build review shipped (see commit `build(docker): drop redundant uv install…`). Two follow-up commits handled the Playwright fallout:

1. **Browser channel correction.** `@playwright/mcp` defaults to `--browser=chrome` (Google Chrome stable), which has no Linux arm64 build — fails on Apple Silicon. We now install **chrome-for-testing** (Playwright's cross-platform CfT build, arm64 + amd64) via `npx @playwright/mcp install-browser chrome-for-testing` and pass `--browser chromium` in `.mcp.json` (which the MCP maps to CfT).
2. **Permissions per Microsoft's official Playwright Docker pattern.** Browsers are installed at `PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright` and the parent dir is `chmod -R 777` so non-root runtime users can create per-session profile dirs. Browser binaries themselves stay root-owned (immutable, good for layer dedup).
3. **`@playwright/mcp` pinned to `0.0.74`** in both build (`PLAYWRIGHT_MCP_VERSION` build arg) and runtime (`.mcp.json`). The earlier `@latest` caused two separate regressions over a 24-hour window.

The pieces below remain queued.

### Image size — recommended next

- **Prune `/opt/ms-playwright/chromium-1223/`** if `chromium_headless_shell-1223` covers all use cases. The `install-browser chrome-for-testing` step installs both the full chromium binary (~620 MB) and the headless-shell variant (~333 MB). The MCP server in headless mode (default) likely only uses headless-shell. Verification spike: take a screenshot, render a page, run a console-error check — all with the full chromium dir removed via `RUN rm -rf /opt/ms-playwright/chromium-1223` after install. If everything passes, ~620 MB drops out of the image. *Effort: ~1h with smoke tests.*
- **Drop CJK + emoji fonts** pulled in by `playwright install-deps`. The deps macro installs `fonts-ipafont-gothic` (3.5 MB), `fonts-noto-color-emoji` (10.1 MB), `fonts-wqy-zenhei` (7.5 MB), `fonts-freefont-ttf` (5.3 MB) — useful only if rendering pages with Asian scripts or emoji. Skipping `install-deps` and curating system libs explicitly saves ~25 MiB. Tradeoff: full-page screenshots of CJK-heavy pages will use fallback fonts. *Effort: ~2h, includes a curated apt list.*

### Build infrastructure

- **GHCR registry push cache.** `docker-compose.prod.yml` has `cache_to: type=registry,ref=${REGISTRY}/main:cache,mode=max` configured but it requires authenticated `docker login ghcr.io` to actually push. The dev compose's anonymous `cache_from` was removed in the Tier 1 commit because the cache image either didn't exist or wasn't world-readable. To re-enable cross-environment cache sharing: (a) confirm a CI job actually pushes the cache image, (b) make the cache image public on GHCR, (c) restore `cache_from` in dev compose. Until then, every fresh checkout pays the full cold-build cost. *Effort: ~3h including CI wiring.*
- **Restructure `deps` stage for finer cache invalidation.** Currently `COPY src/` precedes `uv pip install --system -e .`, so any `src/` edit busts the deps install. Splitting into two installs saves ~2–3s per src-only rebuild. *Effort: ~2h.*

### Larger spikes (do separately)

- **Bump `PYTHON_VERSION=3.13`** in the Dockerfile + `pyproject.toml` `requires-python` + `mypy` config. 3.13 has measurable interpreter perf wins (~10–15% on some workloads) and shorter startup. Risk: needs verification that `claude-agent-sdk`, `mcp`, `pydantic-core`, `cryptography`, `aiohttp`, `uvloop` all ship arm64 wheels for 3.13. *Effort: ~3h.*
- **Bump `glab` from v1.46.1** (Sept 2024) to current (~v1.50+). Pin update only, low risk. Bundle with the next dependency-refresh pass. *Effort: ~30min.*

### Considered and rejected

- **`python:3.12-alpine`** instead of `python:3.12-slim`. Many native wheels (`pydantic-core`, `cryptography`, `uvloop`, `aiohttp`) need musl rebuilds or aren't available. Almost certainly net-negative. Skip.
- **Move `npx playwright install` into `base` stage** to share across variants. Negative: would bloat the production image with browser binaries it doesn't use. Skip.
- **Combine `tini` install into a non-`gh` apt step.** Already done in the Tier 1 commit alongside the `gh` install.

---

## 10. Hardening backlog

Security + test-coverage prioritization. Items below are the open work; resolved items are listed at the end of this section.

### Priority summary (open items)

| Priority | Open items | Effort estimate |
|----------|-----------|-----------------|
| **P0 Critical** | 3 | ~20h |
| **P1 High** | 2 | ~6h |
| **P2 Medium** | 6 | ~16h |
| **P3 Low** | 4 | ~11h |
| **Test gaps** (P1) | 3 modules | ~12h |

### P0 — Critical (block release)

#### CRIT-01: Plaintext checkpoint data
- **CVSS:** 9.1 | **Location:** `src/harness/checkpoint.py` (567 LOC) | **Effort:** ~8h
- Checkpoints store complete agent state in plaintext JSON, including conversation history (may contain API keys / passwords), workspace snapshots, and session tokens.
- **Impact:** PII exposure, credential leakage, GDPR/HIPAA violations.
- **Remediation:** AES-256-GCM encryption + HMAC-SHA256 integrity, keys in vault (KMS/HashiCorp Vault), 30-day key rotation. Sanitization layer (`sanitize_sensitive_data()` in `security.py`) is already applied but is not a substitute for encryption.

#### CRIT-02: SSH private keys in containers
- **CVSS:** 8.8 | **Location:** `docker-compose.yml` lines 69-70, 149-150, 220-221 | **Effort:** ~4h
- SSH private keys mounted into all three agent containers (`./.ssh:/home/claude/.ssh:ro`). Compromised container = stolen credentials.
- **Impact:** Repository access, lateral movement, supply-chain attack.
- **Remediation:** Replace with ephemeral GitHub/GitLab PATs via git credential helper (24h expiry). Drop the SSH bind mounts. Move to container-level secret injection.

#### God-object refactor — `agent.py`
- **Location:** `src/harness/agent.py` (1603 LOC) | **Effort:** ~8h
- `AgentSession` still owns 9+ responsibilities. Block 3 split out the plugin pipeline (`plugin_manager.py` 637 → 182 LoC) but the rest of the decomposition is open.
- **Proposed structure:**
  ```
  AgentSession        ~300 LOC   session lifecycle + dispatch
  ├── MCPServerManager ~200 LOC  MCP discovery + lifecycle
  ├── SessionManager   ~150 LOC  state transitions
  ├── CheckpointManager        already separate (567 LOC, see CRIT-01)
  └── MetricsCollector         already separate (499 LOC, post-Block-4 trim)
  ```
- **Note:** `multi_resource_orchestrator.py` (2157 LOC) and `autonomous.py` (1618 LOC) are now the largest files in the tree. They're candidates for the same treatment in a future pass.

### P1 — High (fix before beta testing)

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Missing rate limiting | 7.5 | `src/harness/autonomous.py` (1618 LOC, no rate-limit primitives) | 4h |
| Redis password in env vars | 7.0 | `.env.example` | 2h |

#### Test coverage gaps (P1)

| Module | LOC | Tests | Status |
|--------|-----|-------|--------|
| `optimization/api.py` | 421 | **0** | Public API still untested |
| `optimization/cli/section_optimize.py` | ~300 | 0 | Entry point untested |
| `cli.py` (Rich UI formatting) | 581 | partial | Linked to interactive UX audit (§ 8) |

Closed since the previous HARDENING revision: `optimization/orchestrator.py` (511 LOC) has 8 tests in `test_orchestrator_design_phase.py`; `optimization/multi_resource_orchestrator.py` (2157 LOC) has 43 tests in `test_multi_resource_orchestrator.py`; `optimizers/agentic_optimizer.py` is exercised by 30 tests in `test_optimizers.py`; `pipeline` has 12 tests.

### P2 — Medium

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Security headers missing | 6.5 | `docker-compose.prod.yml` | 3h |
| Docker socket exposure | 9.0 | `mcp_servers/docker` | 4h |
| Checkpoint cleanup race | — | `checkpoint.py` | 2h |
| Error message sanitization | 5.0 | `agent.py` (~lines 600-630 area) | 2h |
| Dependency vulnerability scanning | 5.5 | `pyproject.toml` (no `.github/workflows/` yet) | 2h |
| Cost budget enforcement | 4.0 | `monitoring.py` cost path | 3h |

### P3 — Low

| Issue | CVSS | Location | Effort |
|-------|------|----------|--------|
| Memory graph encryption | 5.0 | `mcp_servers/memory` | 4h |
| Container image signing | 5.0 | Build pipeline | 3h |
| Redis stream ACLs | 4.5 | `messaging.py` | 3h |
| Test workspace isolation | 6.0 | `docker-compose.yml` | 1h |

### Recently resolved

| Item | CVSS | Resolution |
|-------|------|------------|
| ~~CRIT-03: Log sanitization~~ | 7.5 | `sanitize_sensitive_data()` in `security.py`, applied to prompt storage |
| ~~HIGH-04: Bash bypass flag (`--allow-all-commands`)~~ | 8.8 | Flag removed entirely; verified absent from `src/` |
| ~~P2: Session timeout~~ | 5.3 | `_check_session_timeout()` enforces `claude_session_timeout` |
| ~~P3: Default passwords~~ | 3.0 | All `.env.example` defaults use `CHANGE_ME_BEFORE_PRODUCTION` placeholders |
| ~~P3: Metrics auth~~ | 3.5 | Optional basic auth via `METRICS_AUTH_TOKEN` |
| ~~Plugin SDK Workaround (`agent.py:64-72`)~~ | — | Removed in Block 3 follow-up `d8571b2` |

---

## 11. References

### 11.1 Resolved decisions

| Question | Decision | Rationale |
|---|---|---|
| Eval suite format | **YAML** with JSON Schema validation | Matches existing CGF SPEC pattern, human-authorable, schema gives machine validation. |
| Sandbox isolation | **In-process for Phase A; ephemeral container in Phase C** | Phase A optimizes for iteration speed (still 2-arm comparison-aware); Phase C buys reproducibility once the harness is stable. |
| Grader composition | **Three columns + composite gate** — each tier emits its own `GraderResult`; the gate combines them with explicit `AndGrader`/`OrGrader` per scenario. | Keeps signal separable for debugging. |
| LLM-judge failure mode | **Retry-once-then-mark-no-decision** | Cost-conscious. **(Revised 2026-06-13:** Phase B half-credits `no_decision` at 0.5 rather than excluding it, to preserve effective N — § 4 Task 4.) |
| Grader priority | ~~Cost-first~~ → **discrimination-first cascade** (2026-06-13) | Cheap deterministic checks gate; the judge discriminates scenarios both arms pass. Cost-first produced flat signal (run #8: 0 `llm_judge`, 11/17 tied). See § 1.1, § 3.7 A1/A5. |
| Judge score scale | ~~1–5 integer (hard-argmax)~~ → **anchored 7-pt + criterion sub-scores** (2026-06-13) | Coarse scale compresses to 2–3 effective points; retry→tie collapses to 3 classes. G-Eval logprob weighting is unavailable on the Anthropic Messages API. See § 3.7 A3. |
| Promotion statistic | ~~Bootstrap CI lower-bound > 0.5~~ → **Beta-Binomial posterior on paired discordant outcomes** (2026-06-13) | Bootstrap undefined at decisive N ≈ 3; Beta posterior exact at any N; abstain below a decisive-N floor. See § 4 Task 2, § 11.4. |
| Held-out scenario sourcing | **Hand-authored seed (5–10) + cgf-research-lead expansion to 20–30**; optimizer never sees them | Hand-authored ensures coverage of constraints the LLM might miss; expansion keeps cost down. |
| Judge ensemble vs single | **Single judge + position balancing for Phase B; ensemble deferred to Phase D, applied per-resource-type only when calibration < 0.8** | Position balancing gets ~80% of the bias mitigation at 2× cost (vs ensemble's ~3–5×). |
| Cost cap per eval run | **`CGF_EVAL_TOKEN_BUDGET` env var, default 1M tokens**; surfaced in `eval-results.json` | Prevents runaway feedback loops. |
| Optimizer feedback granularity | **Scenario IDs + concrete failure outputs only**, not judge rationale | Risk: rationale leakage trains optimizer to game the judge. |
| Model-version drift | **`CGF_MODEL_PIN` env var, recorded per eval run**; calibration is per-pin | Lets us compare apples-to-apples across pin changes. |

### 11.2 Resource-type evaluation matrix

> **Make this load-bearing (§ 3.7 A1).** Today this matrix is documentation; `eval_strategy` in `resource_types.py` already encodes it but has zero read-sites. Phase A.5 A1 turns it into live grader-routing so each resource type gets the graders that actually discriminate it.

| Resource Type | Trigger Accuracy | Pairwise Output Quality | Token Efficiency | Unit/Contract Tests | Coherence | Vs No-Resource Baseline |
|---|---|---|---|---|---|---|
| **agent** | ✅ | ✅ | ✅ | — | ✅ (in plugin) | ✅ |
| **skill** | ✅ | ✅ | ✅ | — | ✅ (in plugin) | ✅ |
| **command** | — | partial (deterministic) | ✅ | ✅ scaffold validation | ✅ | — |
| **mcp_server** | — | — | ✅ (integration arm) | ✅ schema + errors | ✅ | — |
| **mcp_tool** | — | — | ✅ | ✅ schema + errors + idempotency | ✅ | — |
| **plugin** | — (per-constituent) | aggregate | aggregate | — | ✅ primary | — |

Per-resource `eval/` directory layout (sits under each workspace):

```
workspace/{spec}/eval/
  scenarios.yaml          # positive + negative trigger contexts + expected behaviors
  goldens/                # reference outputs (where applicable)
  held_out.yaml           # subset never seen by optimizer
  eval_profile.yaml       # declares resource type + grader selection + thresholds
  transcripts/
    baseline/             # per-arm transcripts
    candidate/
  eval-results.json       # aggregated per-scenario results
```

**Gold sets for judge calibration** — 30–50 human-labeled examples per resource type (Phase D). Standard size cited in the LLM-as-judge literature for stable agreement baselines.

### 11.3 Judge bias mitigations

| Bias | Description | Mitigation in this plan |
|---|---|---|
| Position bias | Judge prefers first or last option | ≤ 0.04 on 2026 frontier judges; run both orderings only if disagreement is empirically material, and break disagreements on the continuous score — never a silent tie (Phase B, revised 2026-06-13) |
| Verbosity bias | Judge prefers longer answers | Rubric explicitly notes length ≠ quality; token efficiency gates separately (Phase B) |
| Self-enhancement bias | Judge prefers outputs from its own model family | Different model for judge vs generator (`CGF_JUDGE_MODEL ≠ CGF_DESIGN_MODEL`) — shipped Phase A |
| Authority bias | Judge swayed by claims of authority in output | Rubric anchored to behavioral criteria, not vague "is it better" |
| Confirmation bias (loop) | Judge sees optimizer reasoning and rewards stated intent | Pool separation: eval agents launched with no parent context — § 3.1 upgrades from structural-only to fully isolated |
| Moderation bias | Judge softens verdicts on sensitive content | Out of scope; relevant for eval scenarios involving harmful content (none planned) |

### 11.4 Statistical methodology

**Paired Beta-Binomial promotion gate** (Phase B, revised 2026-06-13 — replaces the percentile bootstrap):

```python
from scipy.stats import beta

def promotion_gate(verdicts: list[Verdict], min_decisive=10) -> bool:
    # Arms are paired (same scenarios); count discordant pairs only.
    wins   = sum(1 for v in verdicts if v.candidate_wins and not v.tie)
    losses = sum(1 for v in verdicts if v.baseline_wins and not v.tie)
    decisive = wins + losses             # no_decision/tie -> 0.5 elsewhere (§ 4 Task 4)
    if decisive < min_decisive:
        return False                      # abstain on insufficient power
    # Jeffreys prior; promote iff 5th pct of the posterior win-rate > 0.5
    return beta.ppf(0.05, wins + 0.5, losses + 0.5) > 0.5
```

The percentile bootstrap (previous design) is undefined-in-practice at decisive N ≈ 3 (only four distinct point estimates) and under-covers below N ≈ 20 (arXiv 2503.01747); the Beta posterior is exact at any N. Raising `trials_per_scenario` and scenarios/resource (§ 4 Task 3) is what makes `min_decisive` reachable.

**Position balancing in pairwise judge** (Phase B):

```
For each scenario s:
  v_AB = judge(scenario=s, first=baseline, second=candidate)
  v_BA = judge(scenario=s, first=candidate, second=baseline)
  if v_AB == v_BA == "first wins":  → baseline wins (consistent)
  if v_AB == v_BA == "second wins": → candidate wins (consistent)
  else:                              → break on the continuous absolute-score margin, or one
                                       tie-break sample — never a silent tie (revised 2026-06-13).
                                       Log the disagreement rate; if < 5% on the judge, drop the 2nd ordering.
```

**Token regression check** (Phase B):

```
median(candidate.tokens_to_goal) ≤ median(baseline.tokens_to_goal) * (1 + tolerance)
```

#### Three statistical traps to avoid

1. **Small-N false positives.** A candidate winning 6/10 looks like 60% but the 95% CI is roughly 26%–88% — well below the "lower bound > 50%" gate. Bootstrap CIs make this explicit.
2. **Multiple testing.** Running eval on every iteration and promoting on first significant win is p-hacking. Use the held-out set for promotion only, not for iteration feedback.
3. **Goodhart on token efficiency.** A candidate that produces shorter but worse outputs will look efficient. Token efficiency is gated *together with* quality, never alone.

#### Scenario maintenance

Two failure modes:

- **Stale scenarios** that the candidate has effectively memorized via optimizer feedback.
- **Trivial scenarios** that pass for any reasonable resource and produce no signal.

Mitigation: rotate ~20% of held-out scenarios per quarter, and a "scenario coverage" review that flags scenarios where baseline and candidate always agree.

### 11.5 Reference material

Design informed by:

- [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [SWE-bench harness — per-task Docker pattern](https://www.swebench.com/SWE-bench/reference/harness/)
- [Wang et al. (2024) on position-bias calibration in LLM-as-Judge](https://arxiv.org/html/2506.22316v1)
- [Bradley-Terry models](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model) for aggregating pairwise comparisons (Bradley & Terry, 1952)

### 11.6 Anthropic-canonical references

Two published Anthropic implementations match this harness's shape and remain useful as design north stars:

- **`anthropics/claude-agent-sdk-demos/research-agent`** — closest analog for programmatic resource loading. Uses `ClaudeAgentOptions(setting_sources=["project"], agents={...}, hooks={...})` directly with no custom plugin loader.
- **`anthropics/claude-cookbooks/claude_agent_sdk/chief_of_staff_agent`** — closest analog for filesystem-based discovery. Uses `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, `.claude/output-styles/` directly.

Plugin distribution follows `anthropics/claude-plugins-official` and `anthropics/skills` (both ship `.claude-plugin/marketplace.json`). Hosting patterns follow the [Anthropic Hosting Guide](https://code.claude.com/docs/en/agent-sdk/hosting).

**Future-state option:** Anthropic's overview suggests prototyping with the Agent SDK and migrating to [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) for long-running asynchronous sessions. Not a near-term migration, but worth keeping in mind as the harness scales beyond what self-hosted infra can support.

### 11.7 What shipped — Block log

Execution happened in four "Blocks." Phase-level detail lives in the no-squash commit messages on each promotion PR.

| Block | Date | Scope | Promotion |
|---|---|---|---|
| **Block 1** | 2026-05-01/02 | Branch reorganization: 73 commits of Stage 1+2 CGF work + multi-resource pipeline promoted from `contextgrad-framework` to `main`; branch reset off the new main. | [PR #1](https://github.com/andisab/casdk-harness/pull/1) |
| **Block 2** | 2026-05-04 | SDK bump (`>=0.1.72`); filesystem agent discovery via `.claude/agents/`; hook event SDK-canonical names; `direct_agent.py` → `subagent.py` rename + slim. | [PR #2](https://github.com/andisab/casdk-harness/pull/2) |
| **Block 3** | 2026-05-04/05 | Plugin pipeline modernization: marketplace adoption (research-team, context-engineering); `plugin_manager.py` collapsed 637 → 182 LoC; `commands.py` and `hooks.py` deleted; SDK upstream investigation closed (no issues filed). | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |
| **Block 4** | 2026-05-05 | Observability: OTel Collector sidecar bridging SDK telemetry into Prometheus; harness metrics renamed `harness_*`; SDK-duplicate counters dropped; two pre-provisioned Grafana dashboards; AlertManager + alert rules wired (rules had been dead since project start). Later (2026-05-14) refactored to 10 dashboards + 13 alerts on the `grafana-refactor` branch — see [OBSERVABILITY.md](./OBSERVABILITY.md). | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |
| **Phase A (Stage 3)** | 2026-05-08 → 2026-05-14 | Eval framework end-to-end: schema, eval-architect agent, graders, EvalHarness, EVAL_DESIGN + EXECUTION_EVAL wiring, telemetry, tracer spans, smoke fixtures. Plus `phase-a-fixes` (F3–F16) and `phase-a-perf` (F17–F22) follow-ups. First full pipeline reached COMPLETE in run #6 (85m 06s). | PRs #7, #8, #9, #11, #12, #13, A.7, + follow-up branches |
| **Phase A refinement + Run #7/#8 + Grafana reorg** | 2026-05-15 → 2026-05-19 | Phase A refinement Steps 1–5 (eval-agent isolation, dual-baseline, cost-per-success gate, pipeline tightening), pre-smoke polish A–E, Run #7 I-series fixes (I1–I15 minus I9/I16 which are queued under Phase D), Run #8 validation (16/18 promote, 7/7 cost recoveries on r2, ITERATE r2 3.5× faster), J1/J2 reporting fixes, Grafana 12→10 dashboard reorg. See [PHASEA_SUMMARY.md §§ 4.8–4.10](./PHASEA_SUMMARY.md#48-what-landed-on-cgf-eval-ab). | merge commit `29456bd` |

Block 3 and Block 4 shipped together in PR #3 because both were authored on `contextgrad-framework` after Block 2's promotion. Two follow-up doc-only PRs (#4, #5) refreshed status docs and `CLAUDE.md` to match the new state.

For phase-level detail, see commit messages on the promotion PRs and CLAUDE.md "Completed Recently" section.

### 11.8 SDK loading behavior

Verified findings on how the SDK loads plugin resources, plus regression probes (`scripts/derisk_plugin_loading.py`, `scripts/derisk_slash_init.py`), live in [`CLAUDE.md` § Verified SDK Loading Behavior](../CLAUDE.md#verified-sdk-loading-behavior-2026-05-05). That's the canonical reference for sessions debugging plugin-loading or slash-command behavior.

### 11.9 Verification rule (still binding)

**Tests pass ≠ feature works.** Plugin/agent loading silently degrades in ways unit tests do not catch (path mismatches, namespace collisions, swallowed discovery exceptions). Every Stage 3 phase boundary must end with a *runtime* smoke test, and the user must do their own confirmation run before any phase is declared complete.

Required at every phase boundary:

1. **Run the full test suite and report actual numbers** — `make test-unit && make test-integration`, not "tests pass." Include passed/failed/skipped counts.
2. **Boot the harness and inspect the runtime registry** — capture the actual values of `discovered_skills`, `agents`, `plugins`. Names, not just counts.
3. **Invoke at least one resource end-to-end** for any change that touches loading. Confirm the actual response, not just that the call returned.
4. **Stop and ask the user to do their own verification run** before declaring any phase complete.

---

## Appendix — Runtime smoke checklists

Each Phase B/C/D exit must produce a runtime smoke result, not just unit tests. Per § 11.9 above.

### Phase B

```bash
# Statistical gating rejects regression
make eval-arm CANDIDATE=v_regressed BASELINE=v_good
# Expected: gate rejection in reviews/v_regressed_eval.json with
# ci_lower_bound clearly < 0.5; review.md cites win-rate + token regression
# + trigger precision/recall.
```

### Phase C

```bash
# Determinism
make eval && cp workspace/.../eval-results.json /tmp/run1.json
make eval && diff /tmp/run1.json workspace/.../eval-results.json
# Expected: identical (or differ only in timestamps)
```

### Phase D

```bash
# CI regression catch + calibration gate
gh pr create --title "regress python-expert" --body "deliberate regression"
# Expected: failing eval comment within 10 min on GitHub Actions
cat docs/JUDGE-CALIBRATION.md | grep "python-expert"
# Expected: kappa ≥ 0.8 line; if not, gate must refuse promotion until
# `make eval-calibrate` brings it back.
```

### Test count

Unit tests: 1863 (Phase A baseline) → ~1925 across Phases B–D (Phase B ~+30, Phase C ~+15, Phase D ~+15). No existing test dropped.

### Memory

Auto-memory `MEMORY.md` updated at end of each phase with new phase label, file pointers, new gotchas. Memory MCP entity for `ab-casdk-harness` updated when Stage 3 reaches a shippable milestone (probably end of Phase B, when statistical promotion is real).

### Appendix

[OpenAI Cookbooks: Evals](https://developers.openai.com/cookbook/topic/evals)
