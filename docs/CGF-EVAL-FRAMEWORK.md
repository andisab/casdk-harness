# CGF Evaluation Framework — Implementation Plan v2

**Last updated:** 2026-05-07
**Branch:** `contextgrad-eval` (renamed 2026-05-07 from `contextgrad-framework`; equal to `main`)
**Status:** Stages 1+2 shipped; Stage 3 (this plan) not started; Stage 4 deferred.

This is the canonical engineering plan for the CGF evaluation framework. It supersedes the v1 draft (Stages 3–4 task lists) and the predecessor `docs/CGF-PLAN.md` (deleted 2026-05-07). Stage-3 forward content in `docs/REFACTOR.md` is now a one-paragraph pointer to this file.

---

## 0. Overview & rationale

CGF Stage 1 added a protocol layer + resource-architect agent + DESIGN phase. Stage 2 added MCP tool/server creation. Both shipped on `main`. **Stage 3** is the eval framework: the part that closes the optimization loop by *measuring whether the resources we generate actually work*, not just whether they pass coherence checks.

The original v1 plan structured Stage 3 as ten linear tasks producing a single-arm in-process eval. v2 reorganizes that work into four phases (A → D) so that the harness is **comparison-aware from day one** (baseline vs candidate, not just "pass/fail of the latest version") and so each phase ships an independently usable system.

### What changed from v1

| v1 | v2 |
|---|---|
| Single-arm eval (run the optimized resource, score it) | Two-arm eval (baseline vs candidate) from Phase A, with explicit `win_rate` |
| Simple-threshold promotion (`pass^k > τ`) | Phased rollout: simple threshold in A, bootstrap-CI gate in B, calibrated multi-judge in D |
| In-process harness | In-process for A; ephemeral container in C for SWE-bench-style determinism |
| LLM-judge errors → unspecified | Retry-once-then-mark-no-decision (resolved decision) |
| Eval-suite format unspecified | YAML + JSON Schema validation (resolved decision) |
| 10 + 8 task linear list | 4 phases × 4–7 tasks each, each phase independently shippable |

### Key decisions

| Decision | Choice | Phase |
|---|---|---|
| Eval-suite storage format | YAML + JSON Schema (Draft-07) validation | A |
| Sandbox isolation (Phase A) | In-process (fastest iteration; harness runs in same container as agents) | A |
| Sandbox isolation (Phase C) | Ephemeral container per arm × scenario, `--rm` + `tmpfs` | C |
| Grader composition | Three columns (deterministic / trajectory / llm_judge) + composite gate | A → B |
| LLM-judge failure mode | Retry-once, then mark "no decision"; gate treats no-decision as tie | A |
| Token budget per eval run | `CGF_EVAL_TOKEN_BUDGET` env var, default 1,000,000 tokens | A |
| Promotion gate (Phase A) | Simple threshold: `candidate.win_rate ≥ baseline.win_rate + ε` | A |
| Promotion gate (Phase B+) | Bootstrap CI on win rate (95% lower bound > 0.5), token-regression check, trigger precision/recall | B |
| Judge model defaults | `CGF_DESIGN_MODEL=sonnet`, `CGF_JUDGE_MODEL=opus` | A |
| Held-out scenarios | 20–30% of generated scenarios marked `held_out: true`; never visible to optimizer | A |
| Pool separation | `cgf-agents/agents/{design,eval}/` subdirs (currently flat) | A |

### Reference material

Five Anthropic engineering articles inform the design:

- [Implement Tool Use: Best Practices](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use#best-practices-for-tool-definitions)
- [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

---

## 1. Pipeline architecture

```
SPEC.md (business objective + capabilities + constraints)
    |
    v
+------------------------------------------------------------------+
|  PHASE 1: RESEARCH                                    [SHIPPED]  |
|  Owner: cgf-research-lead -> research-specialists                |
|  Output: research/notes/*_findings.yaml, eval_criteria.yaml      |
|  Signal: [RESEARCH_COMPLETE]                                     |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 2: DESIGN                                      [SHIPPED]  |
|  Owner: cgf-resource-architect                                   |
|  Output: resource-plan.yaml                                      |
|  Signal: [DESIGN_COMPLETE]                                       |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 3: GENERATE                                    [SHIPPED]  |
|  Owner: context-engineering:context-engineer                     |
|  Output: Generated resource files (agents, skills, MCP, etc.)    |
|  Signal: [GENERATE_COMPLETE:{path}] per resource                 |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 4: EVAL_DESIGN                                 [PHASE A]  |
|  Owner: cgf-eval-architect (NEW agent in cgf-agents/eval/)       |
|  Output: eval/eval-suite.yaml (unit + trajectory + e2e suites,   |
|          20–30% held_out: true)                                  |
|  Signal: [EVAL_DESIGN_COMPLETE]                                  |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 5: ITERATE                                     [SHIPPED]  |
|  Owner: cgf-prompt-optimizer                                     |
|  Output: Versioned candidates ({resource}-v{N}.md)               |
|  Signal: [ITERATE_COMPLETE:{path}] + quality scores              |
+------------------------------------------------------------------+
    |
    v
+------------------------------------------------------------------+
|  PHASE 6: EXECUTION_EVAL                              [PHASE A]  |
|  Owner: Python EvalHarness (NOT an agent — deterministic)        |
|  Method: Two-arm eval (baseline=v{N-1} vs candidate=v{N})        |
|          via either in-process (A) or ephemeral container (C)    |
|  Output: eval/results/v{N}_eval-results.json                     |
|  Metrics: win_rate, pass@k per arm, tokens_to_goal, judge scores |
|  Gate (A): simple threshold | (B+): bootstrap CI + multi-signal  |
|  Signal: [EVAL_COMPLETE] + Promote | Refine | Reject             |
+------------------------------------------------------------------+
    |
    +--- Refine -> loop back to ITERATE with execution feedback
    |    (allowed backward transition; max 2 feedback iterations)
    v
+------------------------------------------------------------------+
|  PHASE 7: VALIDATE                                    [SHIPPED]  |
|  Owner: cgf-coherence-validator                                  |
|  Signal: [VALIDATE_COMPLETE] or [VALIDATE_ISSUES:{count}]        |
+------------------------------------------------------------------+
    |
    v
  FINALIZE -> Versioned, calibrated, comparison-validated resources
```

**Phase enum and signals already exist** in `src/harness/optimization/protocols/{state,signals}.py` — `EVAL_DESIGN_COMPLETE` and `EVAL_COMPLETE` are registered, and the backward transitions `EXECUTION_EVAL → ITERATE` and `VALIDATE → ITERATE` are already allowed. Stage 3 wires the dispatch handlers; the protocol layer is ready.

---

## 2. Completed work (Stages 1+2, shipped on `main`)

### Stage 1: Protocol Layer + Resource Architect (2026-03-02)

- 5 protocol modules: `signals.py`, `resource_types.py`, `quality.py`, `state.py`, `workspace.py`
- `cgf-resource-architect` agent (opus) producing `resource-plan.yaml`
- `resource_plan.schema.json` JSON Schema
- `OptimizationPhase` enum extended from 6 to 9 phases
- SPEC parser extended with `ProposedMCPTool` and `ProposedMCPServer` types
- 120 tests

### Stage 2: MCP Creation Skills (2026-03-02)

- `mcp-tool-creation` skill (FastMCP patterns)
- `mcp-server-creation` skill (Python FastMCP + TypeScript `@modelcontextprotocol/sdk`)
- 3 templates: `mcp-tool-template.py`, Python server template, TypeScript server template
- `resource-type-guide.md` updated with MCP entries
- `context-engineer.md` updated with MCP awareness
- Orchestrator: conditional MCP directory creation, generation instructions
- 47 tests

---

## 3. Phase A — Comparison-aware harness (~weeks 1–4)

**Goal:** Wire `EVAL_DESIGN` and `EXECUTION_EVAL` into the orchestrator with a working two-arm in-process eval. Ship a simple-threshold promotion gate (bootstrap CI lands in Phase B). End state: `make optimize` on a tiny SPEC produces telemetry showing baseline-vs-candidate scoring and a promote/refine decision.

### A.1 Eval-suite schema

**Files**
- Create: `src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json` (Draft-07)
- Test: `tests/unit/test_optimization/test_eval_suite_schema.py`

**Content**
- Top-level: `version`, `target_resource`, `scenarios[]`, `config{trials_per_scenario, timeout_seconds, eval_model, token_budget}`
- Per-scenario: `id`, `level` ∈ `{unit, trajectory, e2e}`, `target_resource`, `description`, `prompt`, `setup.files[]`, `graders[]`, `tags[]`, **`held_out: bool`**
- Grader polymorphism on `type` ∈ `{exact, contains, regex, code, trajectory, llm_judge, composite}`
- Validate against JSON Schema Draft-07 in tests; fail fast on schema mismatch at runtime

### A.2 `cgf-eval-architect` agent + plugin reorganization

**Files**
- Create: `src/harness/plugins/cgf-agents/agents/eval/cgf-eval-architect.md`
- Move: existing 9 agents from `agents/` → `agents/design/`
- Update: `src/harness/plugins/cgf-agents/.claude-plugin/plugin.json` (paths now `./agents/design/*.md` and `./agents/eval/*.md`)
- Validate: `docker compose exec main-agent claude plugin validate src/harness/plugins/cgf-agents`

**Agent design** (per spec lines 174–193 of v1)
- Model: `sonnet` (configurable via `CGF_DESIGN_MODEL`)
- Tools: `Read, Write, Glob, Grep`
- Max turns: 100
- Reads: generated resources, SPEC.md, research findings, resource-plan.yaml
- Reasoning rules:
  - Agent resource → trajectory evals (tool usage, constraints)
  - Skill resource → unit evals (content quality, trigger accuracy)
  - MCP tool → executable evals (function correctness, error handling)
  - MCP server → server evals (tool registration, response format, error messages)
  - All types → e2e evals (full task completion)
- Balanced design: positive + negative cases, 40/40/20 difficulty split (easy/medium/hard)
- Held-out: marks 20–30% of scenarios `held_out: true`
- Emits `[EVAL_DESIGN_COMPLETE]`

**Caveat:** Plugin manifests must pass `claude plugin validate` — silent-drop bug burned this repo before (see [CLAUDE.md § Verified SDK Loading Behavior](../CLAUDE.md)). Add the validate call to `make test-unit` as a pre-check.

### A.3 Grader infrastructure

**Files**
- Create: `src/harness/optimization/graders/{__init__,base,transcript,deterministic,trajectory,llm_judge,composite}.py`
- Test: `tests/unit/test_optimization/test_graders.py`

**`base.py`**
```python
@dataclass
class GraderResult:
    passed: bool
    score: float          # 0.0–1.0
    details: str          # human-readable explanation
    grader_type: str
    arm: Literal["baseline", "candidate"] | None = None

class BaseGrader(ABC):
    @abstractmethod
    async def grade(
        self,
        transcript: AgentTranscript,
        scenario: EvalScenario,
    ) -> GraderResult: ...
```

**`transcript.py`** — Structured representation built from `subagent.call_agent()` message stream
```python
@dataclass
class AgentTranscript:
    messages: list[TranscriptMessage]
    tool_calls: list[ToolCall]
    final_output: str
    total_turns: int
    total_tokens: int

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    result: str
    turn_number: int
    timestamp: float
```

**`deterministic.py`** — `Exact`, `Contains` (case-insensitive option), `Regex`, `Code` (executes Python snippet, checks assertions)

**`trajectory.py`** — Most complex grader; transcript-walking logic. Assertions:
- `tool_called(name, before=..., after=...)`
- `no_tool(name)` — tool was NOT called
- `ordering(before, after)` — tool A invoked before tool B
- `constraint(text)` — LLM-verified constraint from transcript

**`llm_judge.py`** — Takes rubric + transcript/output, calls eval model (configurable: haiku/sonnet/opus, default `CGF_JUDGE_MODEL=opus`), parses 1–5 score → 0.0–1.0, pass threshold per scenario. **Failure mode:** retry-once-then-mark-no-decision (no-decision → gate treats as tie, never auto-fails).

**`composite.py`** — `AndGrader`, `OrGrader`. Composite gate (three columns: deterministic / trajectory / judge) lands in Phase B; A ships with simple AND/OR.

### A.4 `EvalHarness` runner with two-arm comparison

**Files**
- Create: `src/harness/optimization/eval_harness.py`
- Test: `tests/unit/test_optimization/test_eval_harness.py`

**Core loop** — extended vs v1 with two-arm comparison
```python
class EvalHarness:
    async def run(
        self,
        eval_suite_path: Path,
        baseline_resource: Path,
        candidate_resource: Path,
        workspace: Path,
        runtime: Literal["in_process", "ephemeral_container"] = "in_process",
    ) -> EvalResults:
        suite = self._load_suite(eval_suite_path)
        results: list[ScenarioResult] = []
        for scenario in suite.scenarios:
            baseline_trials = await self._run_arm(scenario, baseline_resource, "baseline")
            candidate_trials = await self._run_arm(scenario, candidate_resource, "candidate")
            outcome = self._compare(baseline_trials, candidate_trials)  # BaselineWin | CandidateWin | Tie
            results.append(ScenarioResult(scenario, baseline_trials, candidate_trials, outcome))
        return self._aggregate(results)
```

**`_run_arm()`** — temp dir for `setup.files`, calls `subagent.call_agent()` with target resource as system prompt, captures full transcript, cleans up. Per-trial timeout from `suite.config.timeout_seconds`.

**`_aggregate()`** — Computes per-arm `pass@1`, `pass@k`, `pass^k`; cross-arm `win_rate`; per-level (unit/trajectory/e2e) and per-tag rollups. Saves to `eval/results/v{N}_eval-results.json`. Failed-trial transcripts → `eval/transcripts/`.

**Two-arm cost optimization:** Baseline arm can be cached across iterations (only re-runs when previous candidate promotes to become new baseline). Implement via content-hash on `(baseline_resource_path, baseline_resource_content_sha256)`.

**Held-out separation:** Held-out scenarios are run *only* in EXECUTION_EVAL, never visible to the optimizer in ITERATE. Enforce via assertion in `_delegate_iteration()`: feedback prompt cannot contain held-out scenario IDs.

### A.5 Wire phases into orchestrator

**Files**
- Modify: `src/harness/optimization/multi_resource_orchestrator.py` (currently 2157 LoC — be careful)
- Consider: extract phase handlers into `src/harness/optimization/phases/` package as part of this task. One file per `_delegate_*` and `_run_*` method. Keeps the dispatcher slim.
- Test: `tests/unit/test_optimization/test_orchestrator_eval_design_phase.py`
- Test: `tests/unit/test_optimization/test_orchestrator_execution_eval.py`

**Changes**
- Add `AGENT_EVAL_ARCHITECT = "cgf-agents:cgf-eval-architect"` constant alongside existing six (line 116)
- Add `eval_design_timeout` and `execution_eval_timeout` to `MultiResourceConfig` dataclass
- Add `_delegate_eval_design()` modeled on `_delegate_design()` (line 705); parses `[EVAL_DESIGN_COMPLETE]`, stores `eval_suite_path` in state
- Add `_run_execution_eval()` — calls `EvalHarness` directly (not an agent); naming distinguishes from `_delegate_*`
- Insert `EVAL_DESIGN` after `GENERATE` and `EXECUTION_EVAL` after `ITERATE` in phase dispatch loop (lines 370–393)
- Promotion logic (Phase A simple threshold): `candidate.win_rate ≥ baseline.win_rate + CGF_EVAL_PROMOTION_EPSILON` (default 0.0)
- Loop-back: if not promoted, transition `EXECUTION_EVAL → ITERATE` with feedback prompt built from failing scenarios. Max 2 feedback-driven iterations before escalating.
- State persistence: `eval_suite_path`, `eval_results_path`, `feedback_history`, `held_out_results_path`, `baseline_content_hash`

### A.6 Telemetry

**Files**
- Modify: `src/harness/monitoring.py` — add eval-specific instruments
- Modify: `docker-compose.yml` — add new env vars to explicit `environment:` block (per env-passthrough gotcha)
- Modify: `.env.example` — document new vars
- Modify: `config/monitoring/grafana/dashboards/casdk-cgf.json` — populate the "Future" placeholder row

**OTel resource attributes** (added to spans)
- `harness.eval.task_id` — unique per eval run
- `harness.eval.arm` — enum `baseline | candidate`
- `harness.eval.outcome` — enum `pass | fail | timeout | no_decision`

**New instruments**
- `harness_tokens_to_goal` (Histogram) — tokens spent until first promotable candidate
- `harness_eval_scenarios_total{level, status, arm}` (Counter)
- `harness_eval_arm_score{arm, scenario_id}` (Gauge)
- `harness_eval_phase_duration_seconds{phase}` (Histogram) — covers EVAL_DESIGN and EXECUTION_EVAL
- `harness_eval_judge_no_decision_total{model, scenario_id}` (Counter) — how often LLM-judge fails

**New env vars** (default values shown)
```
CGF_DESIGN_MODEL=sonnet
CGF_JUDGE_MODEL=opus
CGF_EVAL_TOKEN_BUDGET=1000000
CGF_EVAL_PROMOTION_EPSILON=0.0
CGF_EVAL_HELD_OUT_FRACTION=0.25
```

### A.7 Smoke test + docs

- Hand-craft a tiny SPEC.md producing 1 agent + 1 skill, run `make optimize`, watch full pipeline `RESEARCH → DESIGN → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE` end-to-end
- Verify Grafana shows phase transitions, scenario pass/fail, arm scores, tokens-to-goal histogram
- Update [CLAUDE.md](../CLAUDE.md) "Completed Recently" with Phase A summary
- Update auto-memory `MEMORY.md` to mark Phase A complete

**PR #7 ship gate:** `make test-unit` green (~1600 tests, +~60 net), runtime smoke green, Grafana shows new instruments.

---

## 4. Phase B — Statistical promotion gating (~weeks 5–6)

**Goal:** Replace simple-threshold promotion with statistically-honest multi-signal gating.

### B.1 `Gate.decide()` decision engine

**Files**
- Create: `src/harness/optimization/eval_gate.py`
- Test: `tests/unit/test_optimization/test_eval_gate.py`

**API**
```python
class Gate:
    def decide(
        self,
        baseline: ArmResults,
        candidate: ArmResults,
        held_out: ArmResults,
        config: GateConfig,
    ) -> Decision:  # Promote | Refine | Reject
```

### B.2 Bootstrap confidence intervals

- Bootstrap CI on `win_rate`: 1000 resamples, 95% CI; promote only when **lower bound > 0.5**
- Use fixed seed in tests for reproducibility (`numpy.random.default_rng(42)`)
- Fail fast on insufficient sample size (< 20 scenarios → `Decision.Refine` with reason "underpowered")

### B.3 Token regression check

- Candidate `tokens_to_goal ≤ baseline × (1 + CGF_TOKEN_REGRESSION_TOLERANCE)`, default 10%
- Block promotion even if win_rate passes, when token cost regresses past tolerance
- Surface in `Decision.reason`

### B.4 Trigger precision/recall (held-out set)

- Default thresholds: precision ≥ 0.9, recall ≥ 0.8
- Held-out scenarios drive these checks; never visible to optimizer
- Configurable via `CGF_EVAL_PRECISION_THRESHOLD`, `CGF_EVAL_RECALL_THRESHOLD`

### B.5 Pairwise judge with position balancing

**Modify**: `src/harness/optimization/graders/llm_judge.py`
- Run A-B and B-A orderings of pairwise comparison
- Disagreement → tie (not retry — disagreement is information)
- Adds 2× judge cost but eliminates position bias

### B.6 Wire `Gate.decide()` into orchestrator

- Replace simple threshold in `_run_execution_eval()` with `Gate.decide()` call
- Surface decision rationale in eval-results.json
- Telemetry: `harness_eval_gate_decision{outcome, reason}` counter, `harness_eval_ci_lower_bound` gauge

**PR #8 ship gate:** Phase A smoke still green; new tests cover Gate.decide() decision matrix; bootstrap CI numerically validated against fixed-seed fixtures.

---

## 5. Phase C — Ephemeral runtime (~week 7)

**Goal:** SWE-bench-style determinism. Switch from in-process eval execution to ephemeral container per arm × scenario.

### C.1 Layered Dockerfile

**Modify**: `agents/main/Dockerfile`
- Layer 1: `harness-base` (existing) — Python deps for harness + agent runtime
- Layer 2: `harness-eval-base` (new) — Python deps for eval harness only, no agent runtime baggage
- Layer 3: `harness-eval-instance` (new) — per-run scratch, `--rm` cleanup

### C.2 Compose `eval` profile

**Modify**: `docker-compose.yml`
- New `eval` profile with `--rm`, `tmpfs` on `/workspace` and `/memory` (no persistence between runs)
- Pin `CLAUDE_MODEL` per run; record in `eval-results.json` for reproducibility
- Inherits from `harness-eval-instance` layer

### C.3 Make targets

**Modify**: `Makefile`
- `make eval` — run full suite (both arms, all scenarios)
- `make eval-arm ARM=baseline` — single arm only
- `make eval-quick` — held-out scenarios only (for CI)
- `make eval-clean` — sweep stale eval containers and tmpfs mounts

### C.4 `EvalHarness` runtime knob

**Modify**: `src/harness/optimization/eval_harness.py`
- `runtime: Literal["in_process", "ephemeral_container"]` — already shown in A.4 signature
- Default flips to `ephemeral_container` when running under `make eval`
- Stays `in_process` for unit tests (fastest)
- Container-mode invocation via `docker compose run --rm --profile eval ...`

### C.5 Docs

- Update `docs/REFACTOR.md § Observability` — document the new compose profile
- Update [CLAUDE.md](../CLAUDE.md) "Available Tools" — note `make eval-*` targets
- Update [README.md](../README.md) — add Phase C to "Monitoring" section

**PR #9 ship gate:** `make eval` end-to-end on the SPEC from A.7 produces identical `pass^k` results across two consecutive runs (determinism check).

---

## 6. Phase D — Calibration & CI (~weeks 8–9)

**Goal:** Validate that judge models are actually trustworthy. Without calibration, automatic gating is theater.

### D.1 HTML calibration viewer

**Files**
- Create: `src/harness/optimization/eval_calibrate.py` (CLI)
- Create: `src/harness/optimization/templates/calibration_viewer.html.j2` (Jinja2 template)

Renders one-page-per-scenario from `eval-results.json` + transcripts: scenario prompt, both arm outputs, judge verdict, human-label-input box. Output to `eval/calibration/v{N}/`.

### D.2 `make eval-calibrate`

- Runs eval, opens viewer for human labeling (in browser via `open` / `xdg-open`)
- After human labels are saved, computes Cohen's kappa per `(resource_type × judge_model × rubric_version)`
- Writes `eval/calibration/kappa.json` with kappa scores + sample sizes + timestamps

### D.3 Calibration freshness gate

**Modify**: `Gate.decide()` from B.1
- Refuses promotion when calibration is stale (> 30 days, configurable via `CGF_CALIBRATION_TTL_DAYS`) or kappa < 0.8 (configurable via `CGF_CALIBRATION_THRESHOLD`)
- Surface reason in `Decision`: "calibration_stale" or "calibration_insufficient"

### D.4 Judge ensemble fallback

**Modify**: `src/harness/optimization/graders/llm_judge.py`
- When calibration kappa < 0.8 for a `(resource_type, model, rubric)` triple, run k=3 judges (haiku + sonnet + opus) and majority-vote
- Costs 3× but only triggers when single-judge calibration is poor — bounded blast radius

### D.5 GitHub Actions CI

**Files**
- Create: `.github/workflows/eval.yml`

Runs `make eval-quick` on PR (held-out subset only, ~5 min runtime), comments stats on the PR. Uses `${{ secrets.ANTHROPIC_API_KEY }}`. Pinned model version per run.

### D.6 Optimizer reads eval feedback

**Modify**: `src/harness/optimization/multi_resource_orchestrator.py:_delegate_iteration`
- When iteration is triggered by EXECUTION_EVAL feedback, optimizer reads `reviews/v{n}_eval.json` failure entries as critiques
- Builds a structured feedback prompt: failing scenario IDs (excluding held-out), failure modes, judge rationales
- Closes the gradient loop CGF is named after

### D.7 Tests

- `tests/unit/test_optimization/test_eval_calibrate.py` — kappa computation correctness
- `tests/unit/test_optimization/test_eval_ensemble.py` — majority-vote logic
- `tests/integration/test_eval_ci_workflow.py` — GitHub Actions YAML + workflow validation

**PR #10 ship gate:** Phase A smoke green, GitHub Action runs and posts a comment on a test PR, calibration viewer renders for at least one resource type.

---

## 7. Stage 4 — Hardening (deferred until post-Phase-D)

After Phase D ships and the eval system has run on real workloads, return to:

- **Full pipeline E2E test** (`tests/e2e/cgf/test_full_pipeline.py`) — `SPEC.md → RESEARCH → DESIGN → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → FINALIZE` with mocked external API calls but real Python orchestration
- **Checkpoint/resume across new phases** — verify resume from each of `EVAL_DESIGN`, `EXECUTION_EVAL`; preserve `eval-suite.yaml` and partial `eval-results.json`
- **Human review gates** with `--review` flag — pause after DESIGN, EVAL_DESIGN, EXECUTION_EVAL; user runs `/cgf proceed` or `/cgf edit` to continue
- **Edge case hardening** — empty eval results, all-fail scenarios, MCP server build failures, agent timeouts, disk exhaustion (transcript truncation)
- **Error recovery and retry** — distinguish transient (rate-limit, timeout) from permanent (schema invalid, build failure); structured logging for all retries
- **Comprehensive doc rewrite** — pipeline diagram with all 9 phases, full agent table, full resource type table, troubleshooting section for eval-related issues

I deliberately defer detailed Stage-4 planning until after Phase D — the shape of the human-review UX depends on what calibration tells us about which gates actually need human eyes vs which can stay automated.

---

## 8. Cross-cutting concerns

### 8.1 Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `multi_resource_orchestrator.py` already 2157 LoC; adding 2 phases pushes past maintainability | High | Extract phase handlers into `orchestrator/phases/` package as part of A.5. One file per method. |
| Plugin manifest silently dropped if `plugin.json` not updated correctly | High (already burned this repo) | Add `claude plugin validate` to `make test-unit` as pre-check |
| LLM-judge cost explosion during Phase A iteration | Medium | `CGF_EVAL_TOKEN_BUDGET` (default 1M) hard-kills runs. Wire to `harness_tokens_to_goal` histogram. |
| Bootstrap CI wrong because of test-set pollution (optimizer learned from held-out scenarios) | Medium | Held-out physical separation; `assert` in `_delegate_iteration()` that feedback prompt cannot reference held-out scenario IDs |
| Sub-agent `HOME` mismatch (CLAUDE.md known limitation) bites eval-architect when it writes eval-suite.yaml | Medium | Fix env passthrough in `_build_sdk_options()` before Phase A starts (also queued as independent TODO) |
| Two-arm comparison doubles eval cost vs v1's single-arm assumption | Definite | Cache baseline-arm results across iterations (baseline only changes when candidate promotes); document in budget |
| Position bias in pairwise judge (always preferring left answer) | Medium | Phase B.5 mitigates via A-B + B-A balancing; disagreement → tie |
| Judge calibration drift over model versions | Medium | Phase D.3 calibration freshness gate (TTL 30 days); pin `CGF_JUDGE_MODEL` per run |
| Phase A in-process harness leaks state between scenarios | Medium | Phase C ephemeral container resolves; A mitigates via per-scenario temp dirs |

### 8.2 Telemetry conventions

OTel resource attribute namespacing established in this plan:
- `harness.eval.*` — all eval-specific attributes
- `harness_eval_*` instrument prefix — Prometheus metrics
- `cgf_*` — existing CGF tracer instruments (preserved, untouched)

### 8.3 Verification rule (binding)

Per [CLAUDE.md](../CLAUDE.md): every phase boundary must end with a runtime smoke test, not just unit-test-pass. Specifically:

| Phase | Required runtime smoke |
|---|---|
| A | `make optimize` on tiny SPEC; full 9-phase pipeline executes; Grafana shows new instruments |
| B | `make optimize` re-run with intentionally-flaky scenarios; bootstrap CI declines promotion correctly |
| C | `make eval` produces identical `pass^k` across two consecutive runs (determinism) |
| D | GitHub Actions runs on a test PR and posts a comment with calibrated stats |

---

## 9. Sequencing summary

| Phase | Duration | PR | Key deliverable | Ship gate |
|---|---|---|---|---|
| 0 (this doc) | ½ day | — | This rewrite | Doc on disk, MEMORY.md updated |
| A | ~weeks 1–4 | #7 | Comparison-aware in-process harness, simple-threshold gate | 9-phase pipeline runs end-to-end on tiny SPEC |
| B | ~weeks 5–6 | #8 | Bootstrap CI + multi-signal gate | Flaky scenarios correctly declined |
| C | ~week 7 | #9 | Ephemeral container runtime + `make eval-*` | Determinism across consecutive runs |
| D | ~weeks 8–9 | #10 | Calibration + CI + ensemble fallback | GH Action posts stats; calibration viewer works |
| Stage 4 | TBD | post-D | Hardening (E2E test, resume, human gates) | Replanned after D ships |

Each PR is a single squash-merge from `contextgrad-eval` → `main`. Branch stays alive across all phases.

---

## 10. Open items

- **Stage 4 detailed planning** — defer until Phase D ships; shape of human-review gates depends on calibration data
- **`cgf-eval-architect` tool budget** — current default `max_turns=100` may be too low for complex resource plans; revisit during A.7 smoke test
- **Held-out fraction default** — 25% is a guess; B.4 trigger precision/recall data will tell us if more or less is needed
- **Container-mode eval with `claude_code` CLI inside the eval container** — Phase C requires deciding whether to install the full agent runtime in `harness-eval-instance` or to call out to a network-attached agent service. Lean toward in-container for hermeticity.

---

**Maintainer:** Andis A. Blukis (andis.blukis@gmail.com)
**License:** MIT
