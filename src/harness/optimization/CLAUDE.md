# src/harness/optimization/ — CGF Pipeline

Technical reference for the CGF optimization framework. Auto-loaded when
editing this package. Pair with:

- **Project-root `CLAUDE.md`** — high-level architecture, modes, plugins.
- **`src/harness/CLAUDE.md`** — observability touchpoints in this package.
- **`docs/CGF-EVAL-ROADMAP.md`** — forward plan (Phase A polish, B/C/D, Stage 4).
- **`docs/PHASEA_SUMMARY.md`** — Phase A retrospective, cost characteristics.
- **`docs/CGF-USER-GUIDE.md`** — user-facing surface (CLI, env knobs, Grafana).

## Two execution paths

The package ships two distinct optimization paths. They share telemetry
helpers (`harness.monitoring.record_run_*`, `init_run_phases`) but not
state machines.

| Path | Entry | State machine | State file |
|---|---|---|---|
| **Single-resource** (CGF session) | `harness.cgf_session.main()` via `python -m harness.cgf_session` | Tracked in `progress.TaskList`; phases: `research`, `optimize`, `finalize`, `complete`, `failed` | `sessions/task_list.json` |
| **Multi-resource** (Phase A) | `MultiResourceOrchestrator.run()` or `run_multi_resource_optimization(workspace_dir, verbose=True)` (async) | 9-phase `OptimizationPhase` enum + `failed` terminal | `sessions/optimization-state.json` |

The Makefile's `make optimize` and `make smoke` branch on whether SPEC.md
contains `## Capabilities` (multi-resource marker) to choose path.

## Multi-resource pipeline (Phase A shipped)

### Phase order

Canonical order from `protocols/state.py::PHASE_ORDER`:

```
RESEARCH → DESIGN → QA → GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → COMPLETE
```

Plus `failed` as a terminal phase (recorded via
`record_phase_entry(resource, "failed")` at ~9 error sites in
`cgf_session.py`; not in `PHASE_ORDER` but in
`monitoring.MULTI_PATH_PHASES`).

Forward transitions move one step. Two backward transitions are allowed
(`protocols/state.py::_BACKWARD_TRANSITIONS`):

- `EXECUTION_EVAL → ITERATE` — Phase-A eval gate loop-back when a
  candidate fails to clear the promotion threshold.
- `VALIDATE → ITERATE` — coherence validator flagged issues; refine
  before completing.

Both are bounded: `DEFAULT_MAX_FEEDBACK_ITERATIONS=2` for the eval
loop-back, `DEFAULT_MAX_VALIDATE_REFINEMENTS=2` for the validate
loop-back (both in `_orchestrator_helpers.py`).

### Phase → agent mapping

Constants from `_orchestrator_helpers.py:48–54`. Each phase module lives
under `_orchestrator_phases/` and is mounted onto
`MultiResourceOrchestrator` via class-attribute assignment.

| Phase | Driver | Signal emitted | Module |
|---|---|---|---|
| RESEARCH | `cgf-agents:cgf-research-lead` | `[RESEARCH_COMPLETE]` | `_orchestrator_phases/research.py` |
| DESIGN | `cgf-agents:cgf-resource-architect` | `[DESIGN_COMPLETE]` | `_orchestrator_phases/design.py` |
| QA | Python auto-accept (no agent) | — | `_orchestrator_phases/qa.py` |
| GENERATE | `context-engineering:context-engineer` | `[GENERATE_COMPLETE:{path}]` | `_orchestrator_phases/generate.py` |
| EVAL_DESIGN | `cgf-agents:cgf-eval-architect` | `[EVAL_DESIGN_COMPLETE]` | `_orchestrator_phases/eval_design.py` |
| ITERATE | `cgf-agents:cgf-prompt-optimizer` | `[ITERATE_COMPLETE:{path}]` | `_orchestrator_phases/iterate.py` |
| EXECUTION_EVAL | `EvalHarness` (no agent — runs graders) | — (Python advances state) | `_orchestrator_phases/execution_eval.py` |
| VALIDATE | `cgf-agents:cgf-coherence-validator` | `[VALIDATE_COMPLETE]` / `[VALIDATE_ISSUES:{count}]` | `_orchestrator_phases/validate.py` |

`AGENT_EVALUATE = "cgf-agents:cgf-result-evaluator"` is also exported
but not currently called by any orchestrator phase (placeholder for the
old single-EVALUATE phase that was split into EVAL_DESIGN +
EXECUTION_EVAL during Phase A).

### Signal vocabulary

All recognized signal tags are in `protocols/signals.py::SignalType`:

```
RESEARCH_COMPLETE       DESIGN_COMPLETE         GENERATE_COMPLETE
EVAL_DESIGN_COMPLETE    ITERATE_COMPLETE        EVAL_COMPLETE
VALIDATE_COMPLETE       VALIDATE_ISSUES
```

`EVAL_COMPLETE` is parsed but not emitted by any orchestrator phase —
keep it in the enum so future agents can use it.

Parser accepts decorated tags: `[TAG]`, `[TAG:arg]`, ``` `[TAG]` ```,
`**[TAG]**`. The line must otherwise contain only the signal —
content on the same line breaks metadata collection. Metadata lines
(`key: value`) following the tag are collected until a non-metadata
line is encountered. For `[VALIDATE_ISSUES:N]`, the argument is
parsed as an integer into `metadata["issue_count"]`. For other
`[TAG:arg]` forms, `arg` is stored as `Signal.resource_path`.

### Single-resource path signals

The single-resource `cgf_session.py` path uses different signals
emitted by the `cgf-orchestrator` agent:

- `[ITERATION_COMPLETE]` (per version produced)
- `[EVALUATE_COMPLETE]` (per evaluation round)
- `[OPTIMIZATION_COMPLETE]` / `[OPTIMIZATION_FAILED]` (terminal)

Contract enforcement (phase-a-fixes): `cgf_session.py` rejects
`[OPTIMIZATION_COMPLETE]` if `iterate` count == 0 OR `evaluate`
count == 0. Failed runs call `record_phase_entry(resource, "failed")`
so Grafana surfaces a red `failed` row.

## State file: `sessions/optimization-state.json`

Shape from `progress.MultiResourceState`:

```python
{
  "spec_path": str,
  "spec_type": str,          # "plugin", "skill-set", "workflow", ...
  "spec_hash": str,          # SHA-256, drives baseline-integrity check
  "current_phase": str,      # one of PHASE_ORDER + "failed"
  "phases_completed": list[str],
  "resources": {             # keyed by resource path
    "<path>": {
      "path": str,
      "resource_type": str,
      "status": str,         # "pending", "optimized", "failed", ...
      "version": int,
      "last_evaluated_version": int,
      "quality": {...},      # ResourceQuality
      "iterations": int,
      "refinement_count": int,
      "depends_on": list[str],
      "depended_by": list[str],
      "error": str | None,
    }
  },
  "research_findings_path": str,
  "user_decisions_path": str,
  "resource_plan_path": str,
  "eval_suite_path": str,
  "eval_results_path": str,
  "feedback_history": list,
  "quality_threshold": float,
  "max_iterations": int,
  "validate_refinement_count": int,
  "started_at": str,
  "updated_at": str,
}
```

To **reset to a specific phase**, edit `current_phase`, set
`phases_completed` accordingly, clear `eval_suite_path` /
`eval_results_path` / `feedback_history` / `validate_refinement_count`,
and per-resource set `status="optimized"`, `version=1`,
`last_evaluated_version=0` (F17 forces re-eval). Then re-run
`make optimize`.

## Eval framework (Phase A)

### Schemas

JSON-Schema Draft-07 documents live under
`src/harness/plugins/cgf-agents/schemas/`:

- `eval_suite.schema.json` — full eval suite shape with polymorphic
  graders. Enforced by `eval_harness/loader.py::load_eval_suite()`.
- `eval_criteria.schema.json` — research-phase output.
- `resource_plan.schema.json` — DESIGN-phase output.
- `run_state.schema.json` — single-resource state file shape.
- `test_suite.schema.json` — legacy test-suite shape (pre-Phase-A).

The eval-suite schema is the most actively maintained — any change to
grader shape needs both `schemas/eval_suite.schema.json` and
`graders/build_grader()`.

### `eval_harness/` package

```
eval_harness/
├── __init__.py        # public re-exports
├── loader.py          # load_eval_suite() — YAML → EvalSuite + schema validation
├── models.py          # EvalSuite, EvalConfig, ScenarioWithGraders, TrialResult, ArmResults, EvalResults
├── runner.py          # EvalHarness — two-arm execution; runtime: in_process | ephemeral_container (Phase C)
└── aggregate.py       # aggregate_arm, compare_arms, aggregate_subset, group_by_level, group_by_tag
```

Runner entrypoint:

```python
from harness.optimization.eval_harness import EvalHarness, load_eval_suite

suite = load_eval_suite(suite_path)
harness = EvalHarness(runtime="in_process")
results = await harness.run(suite, baseline=baseline_path, candidate=candidate_path)
```

Phase A ships `runtime="in_process"` only. Phase C will add
`"ephemeral_container"` (wraps each trial in `docker compose run --rm`
for SWE-bench-style determinism). The `Runtime` literal type is
already in place.

Per-scenario behavior: trials run concurrently under
`CGF_EVAL_SCENARIO_CONCURRENCY` (default 6); the two arms of a
scenario also run concurrently (free 2x on top). Each trial
materializes scenario setup files in a tempdir, invokes the resource
via SDK `query()` (not `harness.subagent`, which only handles named
registry agents), captures the message stream into an
`AgentTranscript`, runs every grader against it.

### `graders/` package

| Module | Exports |
|---|---|
| `base.py` | `BaseGrader`, `GraderResult`, `GraderType` |
| `deterministic.py` | `ExactGrader`, `ContainsGrader`, `RegexGrader`, `CodeGrader` |
| `llm_judge.py` | `LLMJudgeGrader` (retry-once-then-no-decision) |
| `trajectory.py` | `TrajectoryGrader` + 4 assertion kinds (`tool_called`, `no_tool`, `ordering`, `constraint`) |
| `composite.py` | `CompositeGrader` (AND/OR over child graders) |
| `scenario.py` | `EvalScenario`, `ScenarioSetup`, `SetupFile`, `ScenarioLevel`, `Difficulty` |
| `transcript.py` | `AgentTranscript`, `ToolCall`, `TranscriptBuilder`, `TranscriptMessage` |

Factory: `graders.build_grader(spec)` dispatches on `spec["type"]`.
Trusts the schema for type correctness — does dict lookups only,
doesn't re-validate. Unknown types raise `ValueError`.

Pass semantics: a `TrialResult` is `passed` only when every grader
passes **and** no grader returns `no_decision`. `no_decision` is
sticky — one indeterminate grader marks the whole trial as
`no_decision`.

### Promotion gate

Three-stage gate in `optimization/gating.py::decide` (Phase A
refinements 4.1–4.3, branch `cgf-eval-ab`):

1. **Floor stage** — first-time-promotion only.  `candidate >= floor + 2*ε`.
   Fail → `"reject_floor"`.  Floor arm is the bare model (no system
   prompt); built once per resource by `_orchestrator_phases/_baseline_floor.py`
   and gated by `ResourceStatus.last_promoted_version`.
2. **Incumbent stage** — always.  `candidate >= incumbent + ε`.
   Fail → `"refine"`.  Preserves Phase A `>=` semantics (equality
   promotes).
3. **Cost stage** — `candidate.cost_per_success <= incumbent.cost_per_success
   × (1 + τ)`.  Fail → `"reject_cost"`.  Auto-passes when either side
   has `None` (no signal to regress against).

`epsilon = CGF_EVAL_PROMOTION_EPSILON` (default 0.0).
`τ = CGF_TOKEN_REGRESSION_TOLERANCE` (default 0.10).
Phase B replaces the incumbent stage with a bootstrap-CI gate.

Held-out scenarios drive the gate but are **stripped from feedback** to
the optimizer. The optimizer never sees the held-out subset; this
keeps EVAL_DESIGN cheap to repeat without leaking labels.

### Mid-loop suite-hash guard (4.4.a)

EVAL_DESIGN writes `MultiResourceState.eval_suite_hash` (SHA-256 of
`eval-suite.yaml` bytes after CRLF→LF normalisation).  EXECUTION_EVAL
recomputes on every round and `RuntimeError`s on mismatch — guards
against mid-loop suite rewrites leaking optimizer reasoning into the
gate.  The held-out usage sidecar (4.4.c) writes to a **separate**
file (`eval/held-out-usage.json`) precisely to keep this invariant
clean.

### Stagnation early-stop (4.4.b)

EXECUTION_EVAL escalates to VALIDATE when the round-over-round
Δmean_candidate_pass_rate falls below `CGF_MIN_GAIN_PER_ROUND`
(default 0.02 = 2pp).  Cheap insurance against lateral drift within
the max-feedback cap.  Each feedback entry persists
`round_mean_candidate_pass_rate` so the check is O(1) lookup.

## Single-resource path: `cgf_session.py`

Entry: `python -m harness.cgf_session [--path WORKSPACE] [--goal "..."] [--non-interactive]`.

Two-phase flow:

1. **Q&A** — `cgf-initializer` agent gathers requirements interactively,
   writes `sessions/qa_session.json` and updates SPEC.md.
2. **Optimization** — `cgf-orchestrator` agent runs autonomously,
   emitting the single-resource signals above.

`--non-interactive` auto-continues at every phase checkpoint (used by
`make smoke` because `docker compose exec -T` has no TTY).

`CGF_MAX_ITERATIONS` is the hard Python-side ceiling on
`[ITERATION_COMPLETE]` signals. `CGF_ITERATIONS` is the soft hint
passed to the agent.

## Module map (rest of the package)

```
optimization/
├── __init__.py                    # public re-exports
├── multi_resource_orchestrator.py # MultiResourceOrchestrator (multi-resource entry)
├── multi_resource_spec.py         # SPEC.md parser; is_multi_resource_spec()
├── orchestrator.py                # SectionOptimizer (section-based; legacy single-agent)
├── quality_evaluator.py           # QualityEvaluator (agentic scoring)
├── _orchestrator_helpers.py       # shared constants, path validators, eval span helper
├── _orchestrator_phases/          # one module per multi-resource phase
│   └── _baseline_floor.py         # Phase A refinement 4.2 — synthetic bare-model resource generator
├── gating.py                      # Phase A refinement 4.2/4.3 — Gate.decide (floor + incumbent + cost stages)
├── eval_harness/                  # Phase A two-arm runner (optional 3rd floor arm under refinement 4.2)
├── graders/                       # Phase A grader implementations
├── protocols/                     # signals, resource_types, quality, state, workspace
├── resources/                     # AgentResource, SkillResource, CommandResource, PromptResource
├── optimizers/                    # AgenticSectionOptimizer (LLM self-critique)
├── testcases/                     # legacy test-suite loader + 7 validators
├── runners/                       # AgentRunner, BatchRunner
├── adapters/                      # span → feedback transformers
├── analysis/                      # competency_mapper, coherence, synthesizer
├── pipeline/                      # PipelineConfig, OutputFormat, parallel exec helpers
├── store/                         # OptimizationStore (in-memory persistence)
├── cache/                         # response cache helpers
├── cli/                           # section_optimize.py CLI
├── api.py                         # public Python API surface
├── rewards.py                     # ResourceReward composite scoring
└── profiling/                     # cost / latency profiling helpers
```

`orchestrator.py` (the section-based `SectionOptimizer`) and the
section_optimize CLI predate the multi-resource path. Still used for
direct section-by-section optimization of a single resource without a
SPEC.md.

## Env-var → code-path map

Multi-resource Phase A:

| Var | Default | Read at |
|---|---|---|
| `CGF_MAX_ITERATIONS` | 3 | `cgf_session.py`, `multi_resource_orchestrator.py:861` |
| `CGF_JUDGE_MODEL` | opus | `graders/llm_judge.py:50` |
| `CGF_EVAL_TOKEN_BUDGET` | 1_000_000 | `multi_resource_orchestrator.py:908` |
| `CGF_EVAL_PROMOTION_EPSILON` | 0.0 | `_orchestrator_phases/execution_eval.py:177` |
| `CGF_TOKEN_REGRESSION_TOLERANCE` | 0.10 | `_orchestrator_phases/execution_eval.py::_resolve_cost_tolerance` (Phase A refinement 4.3) |
| `CGF_MIN_GAIN_PER_ROUND` | 0.02 | `_orchestrator_phases/execution_eval.py::_resolve_min_gain` (Phase A refinement 4.4.b stagnation early-stop) |
| `CGF_DESIGN_MODEL` | (sonnet via agent YAML) | `graders/llm_judge.py::_resolve_judge_model` reads it only to WARN on self-preference collision (Phase A refinement 4.1) |
| `CGF_GENERATE_CONCURRENCY` | 8 | `_orchestrator_phases/generate.py:47` |
| `CGF_ITERATE_CONCURRENCY` | 4 | `_orchestrator_phases/iterate.py:56` |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 4 | `_orchestrator_phases/execution_eval.py:63` |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | `eval_harness/runner.py` |
| `CGF_EVAL_TRIAL_TIMEOUT` | 180 | `eval_harness/runner.py::_resolve_trial_timeout` (level=unit/e2e) |
| `CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT` | 300 | same, level=trajectory |
| `CGF_ITERATE_TIMEOUT` | 1200 | `multi_resource_orchestrator.py:914` |
| `CGF_RESEARCH_TIMEOUT` | 1800 | `multi_resource_orchestrator.py:861` |
| `CGF_GENERATE_TIMEOUT` | 900 | `multi_resource_orchestrator.py:862` |
| `CGF_VALIDATE_TIMEOUT` | 300 | `multi_resource_orchestrator.py:864` |

Single-resource:

| Var | Default | Read at |
|---|---|---|
| `CGF_ITERATIONS` | 10 | `cgf_session.py` (soft hint to agent) |
| `CGF_ITERATION_REVIEW` | false | `cgf_session.py` |
| `CGF_EVAL_MODEL` | sonnet | `cgf_session.py` |
| `CGF_VERBOSE` | true | `cgf_session.py` |
| `CGF_BASELINE_HASH_CHECK` | 1 | `cgf_session.py` (SHA-256 integrity check) |
| `CGF_SIGNAL_STRICT` | 0 | `cgf_session.py` (versioned-file-without-signal: warn vs fail) |

Pipeline-config feature flags (`pipeline/config.py`):

| Var | Default |
|---|---|
| `CGF_TOKEN_TRACKING` | false |
| `CGF_TOKEN_BUDGET` | 0 (unlimited) |
| `CGF_CACHE_ENABLED` | false |

Pipeline caps (constants in `_orchestrator_helpers.py`):

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_QUALITY_THRESHOLD` | 0.85 | Per-resource quality target |
| `DEFAULT_MAX_ITERATIONS` | 5 | Per-resource iteration cap |
| `DEFAULT_MAX_REFINEMENT` | 1 | Per-resource refinement loops |
| `DEFAULT_MIN_CONTENT_SIZE_RATIO` | 0.5 | Structural smoke on candidate size |
| `DEFAULT_EVAL_PROMOTION_EPSILON` | 0.0 | Simple-threshold gate margin |
| `DEFAULT_MAX_FEEDBACK_ITERATIONS` | 2 | EXECUTION_EVAL → ITERATE loop-back cap |
| `DEFAULT_MAX_VALIDATE_REFINEMENTS` | 2 | VALIDATE → ITERATE loop-back cap |

## Tracing (Phase A.7)

`_orchestrator_helpers.py::eval_phase_span()` is an async context
manager that wraps eval phases in a CGF tracer span. Yields a `Span`
when tracing is available, a `_NoOpSpan` otherwise. Tracing must
never break grading — wrap any tracer setup that could fail in a
try/except that degrades to no-op.

OTel attributes: `harness.eval.{task_id, phase, resource_path,
resource_type, outcome, candidate_pass_rate, baseline_pass_rate,
win_rate, ...}`.

For Prometheus metrics emitted from these phases (`harness_eval_*`
family), see `docs/OBSERVABILITY.md` § 3 and `src/harness/CLAUDE.md`.

## Path discipline

`_orchestrator_helpers.py::validate_write_path()` enforces that every
file operation stays under the workspace root. Raises
`PathViolationError` (subclass of `ValueError`). Call it at the top
of every phase module before any write. The eval harness materializes
scenario setup files in `tempfile.TemporaryDirectory()` — not under
the workspace — to keep them isolated across concurrent trials.

`_orchestrator_helpers.py::versioned_path()` is the only way to
construct `{name}-v{N}.{ext}` paths. Preserves parent directory.

## Error classification

`_orchestrator_helpers.py::classify_sdk_error(exc)` turns a raw
exception into `(category, friendly_message)`. Categories:

- `transient` — network blip; retry exhausted (matches subagent.py's
  retry detector, e.g. `FailedToOpenSocket`, `ClientConnectorError`,
  `ProcessError`, plus the misleading
  `returned an error result: success`).
- `timeout` — `asyncio.TimeoutError`.
- `config` — bad agent name, path violation, workspace setup issue.
- `unknown` — anything else; raw message preserved.

Call this whenever a phase catches an exception before writing to
`state.error`, so `optimization-state.json` records a useful
`error_type` alongside the message.

## Public Python API

Re-exports from `harness.optimization.__init__`:

```python
# Resources
from harness.optimization import (
    AgentResource, SkillResource, PromptResource, CommandResource,
    ResourceRegistry,
)

# Agentic optimizer (single-resource section optimization)
from harness.optimization import (
    AgenticSectionOptimizer, AgenticOptimizationConfig,
    AgenticOptimizationResult, get_agentic_optimizer,
)

# Multi-resource orchestrator
from harness.optimization.multi_resource_orchestrator import (
    MultiResourceOrchestrator, MultiResourceConfig,
    run_multi_resource_optimization,   # async helper
)

# Eval harness
from harness.optimization.eval_harness import (
    EvalHarness, load_eval_suite, EvalSuite, EvalResults,
)

# Graders
from harness.optimization.graders import (
    BaseGrader, build_grader, AgentTranscript, TranscriptBuilder,
)
```

`OptimizerProtocol` (`optimizers/protocol.py`) is the extension point
for new optimizers. Methods: `async optimize(resource, test_suite,
config)` and `async evaluate(prompt, test_suite)`.

`AgentResource` is loaded via `AgentResource.load(path)`. There is no
`with_prompt()` method — to mutate, set `system_prompt` then `.save()`.

`ResourceRegistry.register(instance)` takes a resource instance, not
a class.

## Drive-by gotchas

- **No `OptimizationRun` class.** API docs once claimed one with
  `.execute()` / `.get_summary()`. It never existed. Real entry points
  are `AgenticSectionOptimizer.optimize()` and
  `MultiResourceOrchestrator.run()`.
- **No error codes E001–E010.** Earlier docs listed them; nothing in
  code emits or recognizes them.
- **`run_multi_resource_optimization()` is async.** Always wrap with
  `asyncio.run(...)` when calling from sync context — the Makefile
  does this; copy-pasted snippets often don't.
- **Schema files live under `plugins/cgf-agents/schemas/`**, not
  `optimization/schemas/`. They ship with the agent that produces
  them (eval-architect, resource-architect, research-lead).
- **The `EVALUATE` agent constant (`AGENT_EVALUATE`) is wired but
  unused.** Phase A split EVALUATE into EVAL_DESIGN + EXECUTION_EVAL.
  Leave the constant — removing it without a search would orphan any
  future re-use.
- **In-process eval ≠ in-process subagent.** `EvalHarness` calls SDK
  `query()` directly with the candidate file's content, never going
  through `harness.subagent` (which is for named registry agents
  only). Eval candidates are bare file paths.
- **`failed` is a phase, not a status.** Recorded as a phase entry
  for Grafana so the timeline goes red. `optimization-state.json`
  also has per-resource `status` (which can be `"failed"`); the two
  are separate signals.
