# CGF Eval Roadmap & Harness Forward Plan

The canonical forward-looking plan for `ab-casdk-harness`. Covers:

1. **CGF eval framework** continuing work: Phase A polish → Phase B (statistical gate) → Phase C (ephemeral runtime) → Phase D (calibration & CI).
2. **Cross-cutting harness work**: independent TODOs, build improvements, hardening backlog.

Companion docs:

- **[PHASEA_SUMMARY.md](./PHASEA_SUMMARY.md)** — Phase A retrospective (shipped 2026-05-14). What was built, what was learned, what cost characteristics look like. Source of truth for the "as-built" state of the eval pipeline.
- **[OBSERVABILITY.md](./OBSERVABILITY.md)** — operator guide for the OTel + Prometheus + Grafana + AlertManager stack: 10 dashboards, 13 alert rules, full metric inventory.
- **[CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md)** — day-to-day CGF usage, environment variables, how to run.
- **[CLAUDE.md](../CLAUDE.md)** — repo overview, current status snapshot, "Completed Recently" log, SDK loading behavior.

**Branch:** `contextgrad-eval` (currently ahead of `main` with Phase A + the F3–F22 fix series).
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

**As of 2026-05-14:**

- All four reorganization blocks (1, 2, 3, 4) merged to `main`.
- Branch `contextgrad-eval` carries **CGF Stage 3 Phase A shipped end-to-end** plus the `phase-a-fixes` (F3–F16) and `phase-a-perf` (F17–F22) follow-ups, both smoke-validated. The first full pipeline reached `COMPLETE` in run #6 (85m 06s, exit 0). See [PHASEA_SUMMARY.md § 1](./PHASEA_SUMMARY.md#1-current-state).
- **Tests:** 1863 unit passing (was 1534 pre-Phase-A), 41 integration tests across 21 files, 82 e2e tests across 5 files.
- **Pipeline:** 9 phases working end-to-end — `RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → COMPLETE`, with `EXECUTION_EVAL → ITERATE` feedback loop bounded at 2 rounds.
- **Observability stack live:** OTel Collector → Prometheus, 10 pre-provisioned Grafana dashboards, AlertManager + 13 active alert rules. Canonical reference: [OBSERVABILITY.md](./OBSERVABILITY.md).

| Stage | Status | Where |
|---|---|---|
| **Stage 1 — Protocol layer + resource architect + DESIGN phase** | shipped | `main`, via Block 1 |
| **Stage 2 — MCP tool/server creation skills + Python/TypeScript scaffolds** | shipped | `main`, via Block 1 |
| **Stage 3 Phase A — Comparison-aware eval harness** | **shipped** | `contextgrad-eval` |
| **Stage 3 Phase A polish (near-term, this doc § 3)** | in-flight | `contextgrad-eval` |
| **Stage 3 Phase B — Statistical promotion gating** | not started | future |
| **Stage 3 Phase C — Ephemeral runtime** | not started | future |
| **Stage 3 Phase D — Calibration & CI** | not started | future |
| **Stage 4 — Integration & hardening** | not started; depends on Phase D | future |

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

## 3. Near-term — Phase A polish (in-flight)

The most consequential improvement is § 3.1; § 3.2 is the biggest signal-quality lever; § 3.3/§ 3.4 are queued defects and validation gaps. Source: [PHASEA_SUMMARY § 4](./PHASEA_SUMMARY.md#4-open-issues--future-work).

### 3.1 Eval as a distinct Opus agent with isolated context

The eval pipeline currently runs as part of the same conversation/context as the orchestrator; the architect agent is bounded by the orchestrator's overall turn budget. A separate eval-only agent with its own context window, model selection (Opus for rubric authoring quality), and isolated tool access would:

- Free up the orchestrator's context.
- Let the architect think harder about discriminating scenarios.
- Make eval reproducibility easier (separate inputs, separate logs).
- Set up cleanly for Phase B — bootstrap-CI on a noisy gate is wasted; signal quality has to come first.

This is the architectural blocker for Phase B's value to land.

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
- **F1 (cosmetic, deferred).** `setup.sh` host-side tooling probe false-positives.
- **F5 (mitigated, deferred).** Hard-abort path on EVAL_DESIGN architect timeout; currently bandaided by raised budget.

### 3.4 Validation gaps

- **Full 54-scenario suite at `trials=3`.** Smoke uses `trials=1` for speed; production cadence is `trials=3`. Not yet run end-to-end — would 3× per-trial cost but smooth the pass-rate distribution.
- **F25 reproducibility.** Single observation in run #6; need a follow-up run to determine if it's deterministic or rate-limit roulette.
- **VALIDATE refinement loop never exercised.** Coherence passed cleanly in run #6; the `VALIDATE → ITERATE` retry path (gated by `max_validate_refinements = 2`) has not yet fired under load.

---

## 4. Phase B — Statistical promotion gating

End-state: the simple threshold from Phase A is replaced by a multi-signal statistical gate. Same data shape as Phase A — this is gating logic only.

**Refresh note (post Phase A):** Phase B's value depends on signal quality. Bootstrap CIs on tied-at-zero scenarios don't help. Order Phase B *after* § 3.1 (eval-as-Opus-agent) and § 3.2 (discriminating scenarios).

**Tasks:**

1. **Pairwise judge with position balancing.** Run both A-B and B-A orderings of (baseline, candidate); disagreement → tie. Module: `src/harness/optimization/eval_harness/pairwise.py`. Standard mitigation for position bias (Wang et al. 2024).
2. **Bootstrap CI gate.** `src/harness/optimization/gating.py`. 1000 resamples, 95% CI, **lower bound > 0.5 to promote** (more conservative than just "win rate > 0.5" — protects against false promotions on small N). Decision logged with per-scenario breakdown to `reviews/v{n}_eval.json` alongside the existing `v{n}_review.md`.
3. **Token-regression check.** Median `tokens_to_goal` for candidate must not exceed baseline median by more than `CGF_TOKEN_REGRESSION_TOLERANCE` (default 10%, tighten over time). Token efficiency gates *together with* quality, never alone.
4. **Trigger accuracy for agents/skills.** Eval-suite scenarios already include positive + negative trigger contexts (Phase A schema); now compute precision and recall, gate at default precision ≥ 0.9, recall ≥ 0.8. Tunable per resource via `eval_profile.yaml`.
5. **Multi-signal gate.** All applicable signals (win-rate CI, token regression, trigger precision, trigger recall) must clear for promotion. Single `Gate.decide()` entry point; verdict shape: `Promote | Refine | Reject`. Record full statistics in review file.

**Exit criteria:**

- A candidate that passed Phase A's threshold but fails any of the four signals is rejected with full statistics. **Reproducibility:** identical traces → byte-identical verdicts.
- ~30 new tests (gate logic, bootstrap math, position balancing).

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

**Exit criteria:** A PR that regresses a resource gets a failing eval comment within 10 min on GitHub Actions; calibration page shows current kappa per resource type; passing PRs get statistics published. ~15 new tests.

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
| LLM-judge failure mode | **Retry-once-then-mark-no-decision** | Cost-conscious; "no decision" trials excluded from win-rate denominator (Phase B). |
| Held-out scenario sourcing | **Hand-authored seed (5–10) + cgf-research-lead expansion to 20–30**; optimizer never sees them | Hand-authored ensures coverage of constraints the LLM might miss; expansion keeps cost down. |
| Judge ensemble vs single | **Single judge + position balancing for Phase B; ensemble deferred to Phase D, applied per-resource-type only when calibration < 0.8** | Position balancing gets ~80% of the bias mitigation at 2× cost (vs ensemble's ~3–5×). |
| Cost cap per eval run | **`CGF_EVAL_TOKEN_BUDGET` env var, default 1M tokens**; surfaced in `eval-results.json` | Prevents runaway feedback loops. |
| Optimizer feedback granularity | **Scenario IDs + concrete failure outputs only**, not judge rationale | Risk: rationale leakage trains optimizer to game the judge. |
| Model-version drift | **`CGF_MODEL_PIN` env var, recorded per eval run**; calibration is per-pin | Lets us compare apples-to-apples across pin changes. |

### 11.2 Resource-type evaluation matrix

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
| Position bias | Judge prefers first or last option | Run both A-B and B-A orderings; disagreement → tie (Phase B) |
| Verbosity bias | Judge prefers longer answers | Rubric explicitly notes length ≠ quality; token efficiency gates separately (Phase B) |
| Self-enhancement bias | Judge prefers outputs from its own model family | Different model for judge vs generator (`CGF_JUDGE_MODEL ≠ CGF_DESIGN_MODEL`) — shipped Phase A |
| Authority bias | Judge swayed by claims of authority in output | Rubric anchored to behavioral criteria, not vague "is it better" |
| Confirmation bias (loop) | Judge sees optimizer reasoning and rewards stated intent | Pool separation: eval agents launched with no parent context — § 3.1 upgrades from structural-only to fully isolated |
| Moderation bias | Judge softens verdicts on sensitive content | Out of scope; relevant for eval scenarios involving harmful content (none planned) |

### 11.4 Statistical methodology

**Pairwise win rate with bootstrap CI** (Phase B):

```python
def promotion_gate(verdicts: list[Verdict], n_bootstrap=1000, ci=0.95) -> bool:
    wins = [1 if v.candidate_wins else 0 for v in verdicts if not v.tie]
    if len(wins) < 10:
        return False  # insufficient sample
    boot_means = [
        np.mean(np.random.choice(wins, size=len(wins), replace=True))
        for _ in range(n_bootstrap)
    ]
    lower = np.percentile(boot_means, (1 - ci) / 2 * 100)
    return lower > 0.5
```

**Position balancing in pairwise judge** (Phase B):

```
For each scenario s:
  v_AB = judge(scenario=s, first=baseline, second=candidate)
  v_BA = judge(scenario=s, first=candidate, second=baseline)
  if v_AB == v_BA == "first wins":  → baseline wins (consistent)
  if v_AB == v_BA == "second wins": → candidate wins (consistent)
  else:                              → tie (judge order-dependent → low signal)
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
