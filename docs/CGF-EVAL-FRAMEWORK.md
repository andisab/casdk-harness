# CGF Stage 3 — Evaluation Framework

**Status:** Draft v2 (consolidates predecessor `CGF-EVAL-FRAMEWORK.md` v1
2026-03-02 with `CGF-PLAN.md` 2026-05-07 and `REFACTOR.md § 2 Forward Plan`).
**Branch:** `contextgrad-eval` (currently equal to `main`).
**Owner:** @andisab
**Depends on:** Stage 1 (protocol layer, phase extensions), Stage 2 (MCP
resources to evaluate). Both shipped on `main`.

> This document is the canonical Stage-3 plan. Predecessor `CGF-PLAN.md` was
> deleted after merge; the Stage-3 section in `REFACTOR.md` is a
> one-paragraph pointer back here.

---

## 1. Context & Goals

CGF — the **ContextGrad Framework** The premise of the framework
is that resource quality should improve through measured comparison between
versions, not only pointwise scoring. Stages 1 and 2 shipped the optimization
loop (RESEARCH → DESIGN → QA → GENERATE → ITERATE → VALIDATE → COMPLETE)
with pointwise rubric scoring against a 0.85 threshold. Stage 3 wires the
gradient: a candidate version is promoted only when it is *provably and
statistically better* than the prior version on a held-out scenario set.

### What the existing pipeline does *not* yet do

- **Comparative evaluation.** Quality is currently scored pointwise. There
  is no head-to-head A/B between candidate and baseline (or v{n} vs v{n-1})
  on a held-out scenario set.
- **Trigger accuracy measurement.** For agents and skills, whether a
  description correctly fires in the right contexts (and stays silent in
  the wrong ones) is not measured.
- **Token-efficiency benchmarking.** Token consumption is observable via
  the OTel pipeline shipped in Block 4, but not labeled by eval arm, not
  gated against baselines, and lacks a "tokens-to-goal" signal.
- **Resource-type-aware evaluation.** Skills, agents, commands, MCP
  servers, and plugins are all currently optimized through the same path.
  They need different evaluation profiles.
- **Hard role separation.** Design and evaluation agents share patterns,
  models, and (potentially) context. For unbiased benchmarking the eval
  pool must be isolated.
- **Ephemeral, reproducible runtime.** Eval runs need fresh containers per
  arm to eliminate cross-run contamination.

### Goals

1. Promote a candidate version only when it is **provably and statistically
   better** than the prior version on a held-out scenario set.
2. Make every promotion decision **auditable**: traces, token counts, judge
   verdicts, and statistics persist for inspection.
3. Treat **token efficiency** as a first-class promotion signal, not a
   side metric. Gate it *together with* quality (Goodhart trap: a candidate
   that's shorter but worse looks efficient).
4. **Match evaluation rigor to artifact type** — unit tests where
   deterministic, comparative judgments where qualitative.
5. **Decouple design from evaluation** to remove confirmation-bias loops in
   the optimizer.
6. **Reproducibility:** identical inputs produce identical eval outcomes
   across runs and machines.

### Reference material

Design informed by:
- [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [SWE-bench harness — per-task Docker pattern](https://www.swebench.com/SWE-bench/reference/harness/)
- Wang et al. (2024) on position-bias calibration in LLM-as-Judge
- Bradley-Terry models for aggregating pairwise comparisons (Bradley & Terry, 1952)

---

## 2. Architecture

### 2.1 Pipeline (post-Stage-3)

```
SPEC.md (business objective + capabilities + constraints)
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: RESEARCH                                    [SHIPPED]  │
│  Owner: cgf-research-lead → research-team:research-specialists   │
│  Output: research/notes/*_findings.yaml, eval_criteria.yaml      │
│  Signal: [RESEARCH_COMPLETE]                                     │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: DESIGN                                      [SHIPPED]  │
│  Owner: cgf-resource-architect (cgf-agents/design/)              │
│  Output: resource-plan.yaml                                      │
│  Signal: [DESIGN_COMPLETE]                                       │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: GENERATE                                    [SHIPPED]  │
│  Owner: context-engineering:context-engineer                     │
│  Output: Generated resource files (agents, skills, MCP, etc.)    │
│  Signal: [GENERATE_COMPLETE:{path}] per resource                 │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: EVAL_DESIGN                                 [STAGE 3]  │
│  Owner: cgf-eval-architect (cgf-agents/eval/)                    │
│  Input: Generated resources + SPEC + research findings           │
│  Output: eval-suite.yaml (positive + negative scenarios,         │
│          held-out flag on 20-30%, per-type grader selection)     │
│  Signal: [EVAL_DESIGN_COMPLETE]                                  │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 5: ITERATE                                     [SHIPPED]  │
│  Owner: cgf-prompt-optimizer (cgf-agents/design/)                │
│  Input: Resources + eval_criteria + research                     │
│         (held-out scenarios filtered out — gate-only)            │
│  Output: Versioned resources ({resource}-v{N}.md)                │
│  Signal: [ITERATE_COMPLETE:{path}] + quality scores              │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 6: EXECUTION_EVAL                              [STAGE 3]  │
│  Owner: Python eval harness (not an agent — deterministic)       │
│  Input: Optimized resources + eval-suite.yaml                    │
│  Method: Two arms per scenario (baseline = v{n-1}, candidate =   │
│          v{n}); position-balanced pairwise judge                 │
│  Output: eval-results.json (per-arm transcripts + grader scores) │
│          reviews/v{n}_eval.json (per-scenario verdicts)          │
│          reviews/v{n}_review.md (gate decision + statistics)     │
│  Signal: [EVAL_COMPLETE] + Promote | Refine | Reject verdict     │
└──────────────────────────────────────────────────────────────────┘
    │
    ├── Reject  → loop back to ITERATE with execution feedback
    ▼ Promote
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 7: VALIDATE                                    [SHIPPED]  │
│  Owner: cgf-coherence-validator                                  │
│  Output: Coherence report + [VALIDATE_COMPLETE]                  │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
  FINALIZE → Versioned, statistically-validated resources
```

### 2.2 Eval-suite + grader model

**Eval suite** (`workspace/{spec}/eval/eval-suite.yaml`):

```yaml
config:
  trials_per_scenario: 1            # bumped in Phase B for stat. power
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
| Trajectory | `trajectory.py` (`tool_called`, `no_tool`, `ordering`, `constraint`) | Uses CGF tracer spans + transcript to grade tool-call sequences and execution paths | Moderate |
| LLM-judge | `llm_judge.py` (rubric-anchored) | Behavioral / qualitative criteria where the first two tiers can't reach | Most expensive |
| Composite | `composite.py` (`AndGrader`, `OrGrader`) | Combine tiers per scenario | — |

Each tier emits its own `GraderResult` (`passed: bool`, `score: float`,
`details: str`, `grader_type: str`). The gate combines them explicitly per
scenario via `AndGrader`/`OrGrader` — three columns rather than worst-of, so
debugging stays interpretable.

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

Built from `harness.subagent.call_agent()` message stream — the existing
standalone-agent invocation path already used by CGF runners.

### 2.3 Pool separation: design vs eval agents

Hard rule: **eval agents never see optimizer reasoning.** Failure modes if
violated:

- Judge learns to prefer outputs that match the optimizer's stated intent →
  optimizer can game the judge.
- Token-efficiency analysis becomes confounded with optimizer planning
  overhead.

Enforcement is structural, not policy. Stage 3 splits `cgf-agents/agents/`
into two subdirectories:

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
    cgf-eval-architect.md         # NEW (Phase A)
    pairwise-judge.md             # NEW (Phase B)
    trigger-accuracy-evaluator.md # NEW (Phase B)
    token-efficiency-analyst.md   # NEW (Phase B)
```

Eval agents launched as fresh subagent invocations with **no parent
context** (no inherited scratchpad, no optimizer reasoning visible).
Separate session directories (`sessions/design/` and `sessions/eval/`).

**Different model for eval vs design.** Most-cited mitigation for
self-enhancement bias in the LLM-as-judge survey literature. New env vars:

```
CGF_DESIGN_MODEL=sonnet      # default
CGF_JUDGE_MODEL=opus         # default
```

### 2.4 Telemetry: harness.eval.* attrs + tokens_to_goal

Block 4 shipped the full OTel + Prometheus + Grafana + AlertManager stack.
Stage 3 layers eval-aware attributes on top of it; no new infra.

**OTel GenAI semconv** (already adopted by Block 4):
- `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.usage.{input_tokens, output_tokens}`
- `gen_ai.usage.cache_{creation, read}.input_tokens`
- `gen_ai.agent.name`

**New custom attributes** added on every span/metric emitted during an
eval run:

| Attribute | Type | Notes |
|---|---|---|
| `harness.eval.task_id` | string | UUID per scenario invocation |
| `harness.eval.arm` | string | `baseline`, `candidate`, or version label |
| `harness.eval.outcome` | string | `success`, `failure`, `tie` |
| `harness.resource.id` | string | resource under test |
| `harness.resource.type` | string | `agent`, `skill`, `command`, `mcp_server`, `plugin` |

**New custom metric:**
- `harness.tokens_to_goal` — histogram, emitted at the moment the eval
  judge confirms task success, with all five custom attributes above.

**Dashboards & alerts:** Block 4 Phase 3C shipped a `casdk-cgf` Grafana
dashboard with placeholder panels in a "Future" row. Stage 3 populates
them — phase transitions, optimizer iterations, eval scores. No new
dashboard work needed; the panels are already provisioned. New alert rule:
candidate median tokens-to-goal exceeding baseline by > X% across N
scenarios (Prometheus rule, AlertManager-routed).

---

## 3. Phased Rollout

**Working baseline first, but rigor wired in from day one.** Each phase
ships independently, gated by a runtime smoke + unit-test pass per the
binding "verification rule" in REFACTOR.md.

### Phase A — Comparison-aware harness *(weeks 1–4)*

End-state: a working `EVAL_DESIGN → EXECUTION_EVAL` loop that runs **two
arms** per scenario (baseline = prior version or "no resource baseline" for
first eval; candidate = current), tags all telemetry by arm, holds out
20–30% of scenarios from the optimizer, and feeds failures back to
`cgf-prompt-optimizer`. Promotion uses a simple threshold
(`candidate.pass_rate ≥ baseline.pass_rate + ε`) — bootstrap CI rigor lands
in Phase B on top of this same data shape.

**Files to create:**

- `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json` — JSON
  Schema draft-07. Includes `held_out: bool` per scenario from the start.
- `src/harness/plugins/cgf-agents/agents/eval/cgf-eval-architect.md`
  (model: sonnet; tools: Read, Write, Glob, Grep; max turns: 100). Reasons
  about resource type → appropriate eval strategies (see §5 matrix). Emits
  `[EVAL_DESIGN_COMPLETE]`.
- `src/harness/optimization/graders/__init__.py`
- `src/harness/optimization/graders/base.py` — `BaseGrader` ABC, `GraderResult`.
- `src/harness/optimization/graders/deterministic.py` — Exact / Contains /
  Regex / Code graders.
- `src/harness/optimization/graders/trajectory.py` — Tool-call assertions
  built on transcript model. Most complex grader; careful design needed.
- `src/harness/optimization/graders/llm_judge.py` — Rubric-anchored, reads
  `CGF_JUDGE_MODEL`. Retry-once-then-mark-no-decision on failure.
- `src/harness/optimization/graders/composite.py` — `AndGrader`, `OrGrader`.
- `src/harness/optimization/graders/transcript.py` — `AgentTranscript`,
  `ToolCall`. Built from `harness.subagent.call_agent()` message stream.
- `src/harness/optimization/eval_harness.py` — `EvalHarness.run(suite, ws)`.
  Runs both arms per scenario, captures transcripts, calls graders,
  aggregates pass-rate per arm, writes `eval-results.json`.

**Files to modify:**

- `src/harness/optimization/multi_resource_orchestrator.py` — add
  `AGENT_EVAL_ARCHITECT = "cgf-agents:cgf-eval-architect"` constant; add
  `_delegate_eval_design()` (post-GENERATE); add `_run_execution_eval()`
  (post-ITERATE; calls EvalHarness, not an agent); feedback loop in
  `_delegate_iteration()`. Existing pipeline is at `:356-399`.
- `src/harness/progress.py` — `EVAL_DESIGN` and `EXECUTION_EVAL` are
  already in `OptimizationPhase`; just wire the orchestrator to reference
  them.
- `src/harness/optimization/protocols/signals.py` — extend with
  `EVAL_DESIGN_COMPLETE` and `EVAL_COMPLETE` parsers via the existing
  `SignalParser` protocol. **No new ad-hoc regex.**
- `src/harness/optimization/protocols/quality.py` — add execution-grade
  fields and per-arm shape to existing model.
- `src/harness/optimization/protocols/state.py` — extend `state.json`
  schema with `eval_suite_path`, `eval_results_path`, `feedback_history`,
  `held_out_scenarios`. Resume support follows.
- `agents/main/Dockerfile` and `pyproject.toml` — add OTel SDK to harness
  Python deps if not already present (Block 4 wired Claude-side telemetry;
  this is for harness-emitted spans).
- `config/monitoring/otel-collector-config.yaml` — pass through
  `harness.eval.*` and `harness.resource.*` attributes; verify they reach
  Prometheus.

**Rigor wired in from Phase A:**

1. **Pool separation (structural).** Move existing 9 cgf-agents agents to
   `agents/design/`. New `agents/eval/cgf-eval-architect.md`. Update
   `plugin.json` agent paths. Validate via
   `claude plugin validate src/harness/plugins/cgf-agents`. Eval agent
   launched with no parent context; separate `sessions/eval/` directory.
2. **Telemetry tagging.** New OTel attributes (§2.4) on every span emitted
   during eval; new `harness.tokens_to_goal` histogram metric. Verify
   end-to-end via Prometheus query.
3. **Held-out scenarios.** Eval-architect generates 20–30% with
   `held_out: true`. `_delegate_iteration()` filters held-out scenarios
   out — they only feed the gate. Hand-authored seed (5–10) per resource
   type, expansion via `cgf-research-lead`.
4. **Two-arm eval (the gradient).** Every `EXECUTION_EVAL` runs both
   `baseline` and `candidate`. Per-arm transcripts saved to
   `eval/transcripts/{baseline,candidate}/`. Promotion is simple threshold
   in Phase A: `candidate.pass_rate ≥ baseline.pass_rate + ε` (default
   ε = 0.05). The bootstrap CI replaces this in Phase B on the same data.

**Reuse (don't duplicate):**

- `src/harness/subagent.py:call_agent()` — what `_run_scenario` should
  call; transcript capture builds on its message stream.
- `src/harness/optimization/quality_evaluator.py` and
  `cgf-result-evaluator.md` are Stages-1+2 LLM-judge patterns; the new
  `llm_judge.py` grader should reference them as prior art but **not
  import from them** (eval-pool isolation).

**Exit criteria:**

- Unit tests: 1 per grader type, 1 per orchestrator phase delegation,
  1 integration test for the round-trip with both arms. Target: ~40 new
  tests, ~1574 total. Pre-existing 1534 unchanged.
- **Runtime smoke:** `make optimize` on a 2-resource SPEC produces
  `eval-suite.yaml` (with held-out flag), runs through both arms, writes
  per-arm `eval-results.json`, and `reviews/v{n}_eval.md` with the gate
  decision and per-arm pass-rate diff.
- **Telemetry smoke:** query Prometheus
  `harness_tokens_to_goal_count{arm="candidate"}` returns a non-empty
  histogram.
- **Plugin validation:** `claude plugin validate` passes on both renamed
  cgf-agents subdirectories.

### Phase B — Statistical promotion gating *(weeks 5–6)*

End-state: the simple threshold from Phase A is replaced by a multi-signal
statistical gate. Same data shape as Phase A — this is gating logic only.

**Tasks:**

1. **Pairwise judge with position balancing.** Run both A-B and B-A
   orderings of (baseline, candidate); disagreement → tie. Module:
   `src/harness/optimization/eval_harness/pairwise.py`. Standard mitigation
   for position bias documented in Wang et al. (2024).
2. **Bootstrap CI gate.** `src/harness/optimization/gating.py`. 1000
   resamples, 95% CI, **lower bound > 0.5 to promote** (more conservative
   than just "win rate > 0.5" — protects against false promotions on
   small N). Decision logged with per-scenario breakdown to
   `reviews/v{n}_eval.json` alongside the existing `v{n}_review.md`.
3. **Token-regression check.** Median `tokens_to_goal` for candidate must
   not exceed baseline median by more than `CGF_TOKEN_REGRESSION_TOLERANCE`
   (default 10%, tighten over time). Token efficiency gates *together with*
   quality, never alone.
4. **Trigger accuracy for agents/skills.** Eval-suite scenarios already
   include positive + negative trigger contexts (Phase A schema); now
   compute precision and recall, gate at default precision ≥ 0.9, recall
   ≥ 0.8. Tunable per resource via `eval_profile.yaml`.
5. **Multi-signal gate.** All applicable signals (win-rate CI, token
   regression, trigger precision, trigger recall) must clear for
   promotion. Single `Gate.decide()` entry point; verdict shape:
   `Promote | Refine | Reject`. Record full statistics in review file.

**Exit criteria:**

- A candidate that passed Phase A's threshold but fails any of the four
  signals is rejected with full statistics. **Reproducibility:** identical
  traces → byte-identical verdicts.
- ~30 new tests (gate logic, bootstrap math, position balancing).

### Phase C — Ephemeral runtime *(week 7)*

End-state: identical inputs → byte-identical eval verdicts across runs and
hosts. SWE-bench reports 99.78% determinism on this pattern; we should hit
similar.

**Tasks:**

- `agents/main/Dockerfile.eval` — layered build: `harness-base` →
  `harness-eval-base` (adds eval runners, judges, scenario loader) →
  `harness-eval-instance` (built per resource version, bakes in candidate
  or baseline artifact).
- New `eval` profile in `docker-compose.yml`:
  - `eval-worker` container with `--rm`.
  - `tmpfs` mounts on `/workspace` and `/memory` (no checkpoint persistence
    during eval).
  - Trace/metric output streamed to host-mounted persistent volume.
- Pin `CLAUDE_MODEL` to a specific date-stamped version for the eval-run
  duration; record the pin in `eval-results.json`.
- Disable auto-checkpointing under the `eval` profile.
- One fresh container per scenario instance.
- Make targets: `make eval`, `make eval-arm CANDIDATE=v3 BASELINE=v2`,
  `make eval-clean`.

**Exit criteria:** Run identical eval twice; `diff` on the statistics
section of the review file shows no diff (or differs only in timestamps).
~15 new tests (Dockerfile build smoke, determinism integration test).

### Phase D — Calibration & CI *(weeks 8–9)*

End-state: judges are trusted (Cohen's kappa ≥ 0.8 vs human labels), eval
runs on every PR.

**Tasks:**

- HTML viewer for trace + verdict + human-label slot:
  `scripts/eval-review/`. Reference pattern: skill-creator's `run_loop.py`
  viewer.
- `make eval-calibrate` — runs N=20–50 pairwise judgments through human
  review; computes Cohen's kappa per (resource type × judge model × rubric
  version). Persist scores to `docs/JUDGE-CALIBRATION.md`. Gate refuses to
  promote when calibration is stale (older than a quarter) or below 0.8.
- If calibration < 0.8 for a resource type, **escalate to judge ensemble**
  (3 judges, majority vote) for that type. Carries ~3–5× cost vs single
  judge; use only when needed.
- `.github/workflows/eval.yml` — detect changed resources, run
  `eval-quick` (held-out subset, fast feedback), post statistics as PR
  comment. Failing eval blocks merge.
- **Optimizer integration:** `cgf-prompt-optimizer` reads
  `reviews/v{n}_eval.json` failure entries as critiques (this closes the
  gradient loop CGF is named after). Limit feedback-driven iterations
  (max 2 before escalating to human review).

**Exit criteria:** A PR that regresses a resource gets a failing eval
comment within 10 min on GitHub Actions; calibration page shows current
kappa per resource type; passing PRs get statistics published. ~15 new
tests.

---

## 4. Resolved decisions (was: REFACTOR.md open questions)

| Question | Decision | Rationale |
|---|---|---|
| Eval suite format | **YAML** with JSON Schema validation | Matches existing CGF SPEC pattern, human-authorable, schema gives machine validation. |
| Sandbox isolation | **In-process for Phase A; ephemeral container in Phase C** | Phase A optimizes for iteration speed (still 2-arm comparison-aware); Phase C buys reproducibility once the harness is stable. Skipping straight to containers in Phase A risks the timeline without buying day-one rigor that matters more (telemetry, pool separation, comparison). |
| Grader composition | **Three columns + composite gate** — each tier emits its own `GraderResult`; the gate combines them with explicit `AndGrader`/`OrGrader` per scenario. | Keeps signal separable for debugging; matches `composite.py` design. |
| LLM-judge failure mode | **Retry-once-then-mark-no-decision** | Cost-conscious; "no decision" trials excluded from win-rate denominator (Phase B). |
| Held-out scenario sourcing | **Hand-authored seed (5–10) + cgf-research-lead expansion to 20–30**; optimizer never sees them | Hand-authored ensures coverage of constraints the LLM might miss; expansion keeps cost down. |
| Judge ensemble vs single | **Single judge + position balancing for Phase B; ensemble deferred to Phase D, applied per-resource-type only when calibration < 0.8** | Position balancing gets ~80% of the bias mitigation at 2× cost (vs ensemble's ~3–5×). |
| Cost cap per eval run | **`CGF_EVAL_TOKEN_BUDGET` env var, default 1M tokens**; surfaced in `eval-results.json` | Prevents runaway feedback loops. |
| Optimizer feedback granularity | **Scenario IDs + concrete failure outputs only**, not judge rationale | Risk: rationale leakage trains optimizer to game the judge. |
| Model-version drift | **`CGF_MODEL_PIN` env var, recorded per eval run**; calibration is per-pin | Lets us compare apples-to-apples across pin changes. |

---

## 5. Resource-type evaluation matrix

| Resource Type | Trigger Accuracy | Pairwise Output Quality | Token Efficiency | Unit/Contract Tests | Coherence | Vs No-Resource Baseline |
|---|---|---|---|---|---|---|
| **agent** | ✅ | ✅ | ✅ | — | ✅ (in plugin) | ✅ |
| **skill** | ✅ | ✅ | ✅ | — | ✅ (in plugin) | ✅ |
| **command** | — | partial (deterministic) | ✅ | ✅ scaffold validation | ✅ | — |
| **mcp_server** | — | — | ✅ (integration arm) | ✅ schema + errors | ✅ | — |
| **mcp_tool** | — | — | ✅ | ✅ schema + errors + idempotency | ✅ | — |
| **plugin** | — (per-constituent) | aggregate | aggregate | — | ✅ primary | — |

Per-resource `evals/` directory layout (sits under each workspace):

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

**Gold sets for judge calibration** — 30–50 human-labeled examples per
resource type (Phase D). Standard size cited in the LLM-as-judge literature
for stable agreement baselines.

---

## 6. Telemetry & OTel GenAI conventions

Per [OTel GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/),
already adopted in Block 4:

| Attribute | Type | Notes |
|---|---|---|
| `gen_ai.system` | string | `"anthropic"` |
| `gen_ai.request.model` | string | model SHA pin during eval |
| `gen_ai.response.model` | string | actual model that served |
| `gen_ai.operation.name` | string | `"chat"`, `"agent_invocation"`, etc. |
| `gen_ai.usage.input_tokens` | int | includes cached tokens |
| `gen_ai.usage.output_tokens` | int | |
| `gen_ai.usage.cache_creation.input_tokens` | int | subset of input_tokens |
| `gen_ai.usage.cache_read.input_tokens` | int | subset of input_tokens |
| `gen_ai.agent.name` | string | for agent spans |

**Custom harness attributes (Stage 3):**

| Attribute | Type | Notes |
|---|---|---|
| `harness.eval.task_id` | string | UUID per scenario invocation |
| `harness.eval.arm` | string | `baseline`, `candidate`, or `v{n}` |
| `harness.resource.id` | string | resource under test |
| `harness.resource.type` | string | `agent`, `skill`, `command`, `mcp_server`, `mcp_tool`, `plugin` |
| `harness.eval.outcome` | string | `success`, `failure`, `tie` (set on goal events) |

**Custom metric:**

- `harness.tokens_to_goal` — histogram, emitted on goal-completion event,
  with all five custom attributes above.

**Alert rule** (Phase A deliverable, Prometheus):

```yaml
- alert: CandidateTokenRegression
  expr: |
    histogram_quantile(0.5, harness_tokens_to_goal_bucket{arm="candidate"})
      / histogram_quantile(0.5, harness_tokens_to_goal_bucket{arm="baseline"})
      > 1.10
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Candidate median tokens-to-goal exceeds baseline by >10%"
```

---

## 7. Judge bias mitigations

| Bias | Description | Mitigation in this plan |
|---|---|---|
| Position bias | Judge prefers first or last option | Run both A-B and B-A orderings; disagreement → tie (Phase B) |
| Verbosity bias | Judge prefers longer answers | Rubric explicitly notes length ≠ quality; token efficiency gates separately (Phase B) |
| Self-enhancement bias | Judge prefers outputs from its own model family | Different model for judge vs generator (`CGF_JUDGE_MODEL ≠ CGF_DESIGN_MODEL`) — Phase A |
| Authority bias | Judge swayed by claims of authority in output | Rubric anchored to behavioral criteria, not vague "is it better" |
| Confirmation bias (loop) | Judge sees optimizer reasoning and rewards stated intent | Pool separation: eval agents launched with no parent context — Phase A |
| Moderation bias | Judge softens verdicts on sensitive content | Out of scope; relevant for eval scenarios involving harmful content (none planned) |

---

## 8. Statistical methodology reference

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

### Three statistical traps to avoid

1. **Small-N false positives.** A candidate winning 6/10 looks like 60%
   but the 95% CI is roughly 26%–88% — well below the "lower bound > 50%"
   gate. Bootstrap CIs make this explicit.
2. **Multiple testing.** Running eval on every iteration and promoting on
   first significant win is p-hacking. Use the held-out set for promotion
   only, not for iteration feedback.
3. **Goodhart on token efficiency.** A candidate that produces shorter
   but worse outputs will look efficient. Token efficiency is gated
   *together with* quality, never alone.

### Scenario maintenance

Two failure modes:

- **Stale scenarios** that the candidate has effectively memorized via
  optimizer feedback.
- **Trivial scenarios** that pass for any reasonable resource and produce
  no signal.

Mitigation: rotate ~20% of held-out scenarios per quarter, and a "scenario
coverage" review that flags scenarios where baseline and candidate always
agree.

---

## 9. Stage 4 — Integration & Hardening

After Stage 3 stabilizes. Carries forward from predecessor doc.

### Task 1 — Full pipeline E2E test

`tests/e2e/cgf/test_full_pipeline.py`. Test the complete pipeline from
SPEC.md to finalized, evaluated resources:

```
SPEC.md → RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → FINALIZE
```

Approach: simple 2-resource plugin (1 agent + 1 skill); mock external API
calls but exercise all Python orchestration code. Verify all phases
execute in order, state file updated at each transition, resource files
created with correct versions, eval suite generated and executed, final
resources pass quality + execution thresholds, CHANGELOG.md populated, no
orphaned temp files.

### Task 2 — Checkpoint / resume for new phases

Verify resume from each new phase: DESIGN, EVAL_DESIGN, EXECUTION_EVAL.
- `resource-plan.yaml` preserved on resume from DESIGN.
- `eval-suite.yaml` preserved on resume from EVAL_DESIGN.
- Partial `eval-results.json` loadable on resume from EXECUTION_EVAL.
- Test: kill orchestrator mid-phase, restart, verify correct phase resumes.

### Task 3 — Human review gates

Add `--review` flag with optional checkpoints after DESIGN and EVAL_DESIGN
phases. After DESIGN: pause, display resource-plan.yaml summary, wait for
`/cgf proceed` or `/cgf edit`. After EVAL_DESIGN: pause, display
eval-suite.yaml summary, wait for approval. After EXECUTION_EVAL: pause,
display eval-results.json summary with pass^k scores. State tracks
`checkpoint_phase` and `checkpoint_approved` for resume.

### Task 4 — Performance optimization

- Parallel eval scenario execution (respecting API rate limits).
- Eval result caching: skip re-running scenarios that passed in previous
  iteration.
- Generation parallelism for independent resources.
- Timeout tuning: add DESIGN and EVAL_DESIGN timeouts to config.
- Token usage tracking per phase for cost awareness.

### Task 5 — Edge case handling

- Empty eval results (no scenarios generated → skip EXECUTION_EVAL).
- All scenarios fail (every pass^k = 0 → REJECT, don't loop forever).
- MCP server build failure (compilation error → mark resource as failed,
  continue others).
- Resource-architect proposes 0 resources (invalid plan → error with
  guidance).
- SPEC has no capabilities section (minimal SPEC → resource-architect uses
  defaults).
- Agent timeout during eval (individual scenario timeout → mark trial as
  fail, continue).
- Disk space exhaustion (transcript storage → warn and truncate).
- Circular dependencies in resource plan (validate and reject).
- Research phase produces no findings (proceed with reduced confidence).

### Task 6 — Error recovery and retry

- Configurable retry for agent delegation failures (1 retry with simplified
  prompt).
- Eval scenario retry for transient failures (API timeout, rate limit).
- Distinguish transient errors (retry) from permanent errors (mark failed).
- Log all retries with structured data for debugging.

### Task 7 — Comprehensive documentation update

- `CLAUDE.md` — full rewrite of CGF section to reflect new pipeline.
- `README.md` — update user-facing docs with new commands and workflow.
- `docs/CGF-API-REFERENCE.md` — add EVAL_DESIGN / EXECUTION_EVAL phases to
  state diagram + new artifact schemas.
- `docs/CGF-USER-GUIDE.md` — add "Stage 3: Eval Harness" user-flow section.
- `docs/CGF-EXAMPLES.md` — add eval-suite-generation + feedback-loop
  examples.
- `docs/examples/CGF_EVAL_EXAMPLE.md` — walkthrough of a full optimization
  with eval.

### Task 8 — Memory and auto-memory updates

- Auto-memory `MEMORY.md` — update project status, key files, recent work.
- Memory MCP entity for `ab-casdk-harness` — update observations to reflect
  Stage 3 shipped.

---

## Appendix — Verification / runtime smoke checklist

Each phase exit must produce a runtime smoke result, not just unit tests.
Per the binding "verification rule" in REFACTOR.md.

### Phase A

```bash
# Two-arm eval round-trip
make optimize    # On a 2-resource test SPEC
ls workspace/<spec>/eval/
# Expected: eval-suite.yaml (with held_out flagged scenarios),
#           eval-results.json (with baseline + candidate arms),
#           transcripts/{baseline,candidate}/

cat workspace/<spec>/eval/eval-results.json | jq '.arms | keys'
# Expected: ["baseline", "candidate"]

# Telemetry tagged by arm
curl -s 'localhost:9090/api/v1/query?query=harness_tokens_to_goal_count' | jq
# Expected: non-empty histogram tagged by arm

# Pool separation on disk
ls src/harness/plugins/cgf-agents/agents/{design,eval}/
# Expected: design/ has 9 agents, eval/ has cgf-eval-architect.md

# Plugin manifest validation
docker compose exec main-agent claude plugin validate /opt/plugins/swe-marketplace/plugins/cgf-agents
# Expected: passes
```

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

Unit tests: 1534 → ~1640 across Phases A–D (Phase A ~+40, Phase B ~+30,
Phase C ~+15, Phase D ~+15). No existing test dropped.

### Memory

Auto-memory `MEMORY.md` updated at end of each phase with new phase label,
file pointers, new gotchas. Memory MCP entity for `ab-casdk-harness`
updated when Stage 3 reaches a shippable milestone (probably end of Phase
B, when statistical promotion is real).
