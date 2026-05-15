# CGF User Guide

Practical guide to running the Context Gradient Feedback (CGF) optimization
pipeline. For internals (phase machine, schemas, Python API, extension
points), see `src/harness/optimization/CLAUDE.md`. For the metrics &
dashboards stack, see `docs/OBSERVABILITY.md`.

## Quick start

```bash
# One-time: build images and start the harness
make build
make up

# Initialize a workspace and edit the SPEC
make cgf-init NAME=python-expert
$EDITOR workspace/python-expert/SPEC.md

# Drop the resource file you want to optimize into the workspace
cp src/harness/agents/configs/python-expert.md workspace/python-expert/

# Run optimization (auto-discovers SPEC.md in workspace/)
make optimize
```

There must be exactly one `SPEC.md` under `workspace/`. Auto-discovery
fails fast if there are zero or multiple.

The fastest way to see the pipeline in action is to run a smoke fixture
instead:

```bash
make smoke FIXTURE=python-expert   # single-resource, ~$0.10–$0.50 on sonnet
make smoke FIXTURE=iac-team        # multi-resource, AWS + K8s
```

Smoke fixtures live in `tests/smoke/<name>/` and are end-to-end against
real LLMs.

## What CGF does

CGF takes a resource (an agent prompt, a skill, a multi-resource SPEC
that bundles several) plus an optimization goal, and runs an iterative
loop of:

1. **Research** the resource and goal — identify competencies to target.
2. **Design** how to refactor (multi-resource only — single-resource
   skips this).
3. **Generate / iterate** improved versions.
4. **Evaluate** the new version against the baseline on a generated
   eval suite. Promote only if it beats the baseline.
5. **Validate** structural coherence before declaring done.

The optimized version is written as `{resource}-v{N}.md` next to the
original. **The original file is never modified.** Delete the
`sessions/` directory to reset state without losing artifacts.

### Two paths

The pipeline branches on whether your SPEC.md has a `## Capabilities`
section:

| Path | Triggered by | Used for |
|---|---|---|
| Single-resource | No `## Capabilities` in SPEC | One agent/skill/command |
| Multi-resource | `## Capabilities` present | Plugins, skill-sets, coordinated agent groups |

Both are launched the same way (`make optimize`). The multi-resource
path is the Phase A pipeline — 9 phases, two-arm eval gate, per-resource
loop-back on failure.

## Resource types

| Type | What it optimizes |
|---|---|
| Agent | System prompt, task handling, examples |
| Skill | Trigger precision, activation boundary, false-positive rate |
| Command | Argument shape, error messages, help text |
| Workflow | Step coordination, error recovery |
| Hook | Event matching, execution reliability |
| MCP server | Tool descriptions, validation, error responses |

For a multi-resource SPEC, you mix any of these in one `## Capabilities`
section and CGF figures out the resource plan in the DESIGN phase.

## Writing good optimization goals

Specific, measurable, achievable. The eval-architect agent grounds the
eval suite in your goal — vague goals produce vague evals.

Good:

- `improve async/await pattern explanations with concrete asyncio.gather examples`
- `reduce false activations on commands that don't match the trigger pattern`
- `add error recovery guidance for transient database failures`

Bad:

- `make it better`
- `feel more natural`
- `add support for a new programming language` (outside scope of optimizing an existing resource)

## Running the pipeline

```bash
make optimize          # Auto-discover SPEC.md
make optimize-dryrun   # Print discovered SPEC and env settings, don't run
make smoke FIXTURE=python-expert | iac-team
```

The Makefile target does not take `WORKSPACE=` or `GOAL=` arguments.
Put your goal in `SPEC.md`, then run.

For finer control, invoke the CLI directly:

```bash
docker compose exec main-agent python -m harness.cgf_session \
  --path /workspace/python-expert \
  --non-interactive
```

`--non-interactive` auto-continues at every phase checkpoint (no TTY
needed). Used by `make smoke`.

### What to watch

Three places to look while a run is in progress:

| Look at | For |
|---|---|
| Terminal output | Phase transitions, agent activity, errors |
| `workspace/<name>/sessions/optimization-state.json` | Current phase, per-resource status, version, quality scores |
| Grafana `/d/casdk-cgf` | Run timeline, iteration count, cost so far |

Inspect after a run completes:

- `workspace/<name>/sessions/optimization-state.json` — state machine final position
- `workspace/<name>/eval/` — eval suite + per-round results
- `workspace/<name>/CHANGELOG.md` — narrative of what changed
- `workspace/<name>/{resource}-v{N}.md` — optimized output(s)

## Review mode

To pause for human review after each iteration:

```bash
CGF_ITERATION_REVIEW=true make optimize
```

The orchestrator will pause and wait for input before generating the
next version. Useful for first-time optimization of a critical resource
or when validating that the eval suite is targeting the right
capabilities.

## Resuming

State is persisted in `workspace/<name>/sessions/`. To resume after
interruption, just re-run `make optimize` — it picks up at the phase
that was current when the run stopped.

To reset and start over:

```bash
make cgf-clean         # remove sessions/ dirs only (keep research, optimized files)
make cgf-reset         # destructive: remove all CGF artifacts in workspace/
```

To resume a multi-resource run from a specific phase, edit
`sessions/optimization-state.json` directly — see
`src/harness/optimization/CLAUDE.md` § "State file" for the schema.

## Configuration

Most users only touch a handful of env vars. Set them in `.env` (loaded
by `docker compose`) or override per-run on the command line.

### Common knobs

| Var | Default | When to change |
|---|---|---|
| `CGF_EVAL_MODEL` | sonnet | Drop to `haiku` for cheap iteration; raise to `opus` for highest-quality test scoring |
| `CGF_JUDGE_MODEL` | opus | The judge in EXECUTION_EVAL. Most expensive call — drop to `sonnet` if you trust your rubrics |
| `CGF_ITERATION_REVIEW` | false | Set `true` to pause after each iteration for review |
| `CGF_MAX_ITERATIONS` | 3 | Hard cap on iterations per resource. Raise for hard goals; lower to budget-bound |
| `CGF_VERBOSE` | true | Show agent activity in terminal |
| `CGF_TOKEN_TRACKING` | false | Track token usage in `pipeline/config.py` flag (also visible in Grafana) |

### Less-common knobs

| Var | Default | Purpose |
|---|---|---|
| `CGF_EVAL_PROMOTION_EPSILON` | 0.0 | Promotion threshold; raise to require clearer wins |
| `CGF_EVAL_TOKEN_BUDGET` | 1_000_000 | Observability + cost-warn; not a hard cutoff yet |
| `CGF_GENERATE_CONCURRENCY` | 8 | In-flight resource generation. Drop if you hit 429s |
| `CGF_ITERATE_CONCURRENCY` | 4 | In-flight per-resource iteration |
| `CGF_EXECUTION_EVAL_CONCURRENCY` | 4 | In-flight eval runs |
| `CGF_EVAL_SCENARIO_CONCURRENCY` | 6 | Scenarios per eval run |
| `CGF_BASELINE_HASH_CHECK` | 1 | SHA-256 protection against silent baseline edits |

### Phase timeouts

Each phase has a wall-time cap. Defaults are generous; raise only when a
specific phase consistently times out on hard goals.

| Phase | Default | Var |
|---|---|---|
| RESEARCH | 1800 s | `CGF_RESEARCH_TIMEOUT` |
| GENERATE | 900 s | `CGF_GENERATE_TIMEOUT` |
| ITERATE | 1200 s | `CGF_ITERATE_TIMEOUT` |
| VALIDATE | 300 s | `CGF_VALIDATE_TIMEOUT` |
| EVAL trial (unit/e2e) | 180 s | `CGF_EVAL_TRIAL_TIMEOUT` |
| EVAL trial (trajectory) | 300 s | `CGF_EVAL_TRAJECTORY_TRIAL_TIMEOUT` |

The full env-var-to-code-path map is in
`src/harness/optimization/CLAUDE.md`.

## Reading Grafana

Grafana lives at <http://localhost:3000> (login `admin` / `${GRAFANA_PASSWORD}`).
Ten dashboards ship pre-provisioned. The ones a CGF user cares about
during and after a run:

### `/d/casdk-cgf` — CGF Optimization

The dashboard built for this pipeline. Look here first.

- **Active Run Status** — current phase (highlighted across the 9-phase
  bar), active resource, iteration counter, cost & tokens in the last
  15 minutes. Path-specific phases dim gray when not applicable.
  `failed` shows red.
- **Eval Framework** — Phase A telemetry: per-arm pass rates, judge
  no-decision rate, scenarios run, token spend per eval round.
- **State Timeline** — phase transitions over time. Useful for seeing
  loop-backs (`EXECUTION_EVAL → ITERATE`) and stuck phases.

### `/d/casdk-overview` — Harness Overview

Top-level health: services up, agent activity, recent errors. Start
here if something feels off and you're not sure where to look.

### `/d/casdk-sdk-cost` — Cost & Spend

Token spend segmented by `model` (sonnet/opus/haiku) and `query_source`
(main agent vs. subagent invocations). Useful after a run for the
"what did this cost me" question.

### `/d/casdk-sdk-reliability` — Reliability & Errors

API errors, retries, transient failures. Check after a failed run to
distinguish "network blip the harness should have retried" from
"genuine config or agent error."

Other dashboards (`sdk-productivity`, `sdk-cache`, `sdk-tools`,
`mode-interactive`, `mode-autonomous`, `raw-events`) are less relevant
during optimization runs. See `docs/OBSERVABILITY.md` for the full
tour, alert rules, and metric inventory.

## Troubleshooting

### "No SPEC.md found" or "Multiple SPEC.md files found"

`make optimize` requires exactly one. Create with `make cgf-init NAME=foo`,
or remove extras.

### Run completed but no `*-v1.md` was produced

The contract enforcer rejected `[OPTIMIZATION_COMPLETE]` because no
iteration or evaluation happened. Check the terminal — the orchestrator
likely went straight from RESEARCH to COMPLETE without producing a
candidate. `optimization-state.json` will show `current_phase: failed`.
Re-run with a more specific goal or check the `cgf-orchestrator` prompt
for issues.

### Candidate scored well but didn't promote

The promotion gate requires `candidate.pass_rate ≥ baseline.pass_rate +
CGF_EVAL_PROMOTION_EPSILON`. Default epsilon is 0, so any strict
improvement wins. If you set epsilon above 0, raise the bar deliberately.

### EXECUTION_EVAL keeps looping back to ITERATE

Max two feedback rounds (`DEFAULT_MAX_FEEDBACK_ITERATIONS`). After
that, the run promotes whichever version had the best pass rate and
moves on. If you want more aggressive iteration, change the constant in
`_orchestrator_helpers.py` — there is no env var for this yet.

### Rate-limit errors (429)

Drop concurrency knobs: `CGF_GENERATE_CONCURRENCY=4`,
`CGF_EVAL_SCENARIO_CONCURRENCY=3`. The harness retries transient 429s
but sustained pressure means too much parallelism.

### `~` paths fail with EACCES inside subagents

Known issue with `HOME` resolving to `/root` in subagent bash calls.
Use absolute paths (`/home/claude/...`) until the env-passthrough fix
lands. Tracked in project-root `CLAUDE.md` TODOs.

### Debug mode

```bash
CGF_VERBOSE=true make optimize             # show progress
make optimize-dryrun                       # validate setup, don't run
```

## Best practices

**Before**
- Save a copy of the original resource somewhere safe. The harness
  doesn't modify it, but you may want to diff later anyway.
- Write a specific, measurable goal. "Improve X" is not a goal;
  "explain X with concrete asyncio.gather examples" is.
- For a first run on a critical resource, set `CGF_ITERATION_REVIEW=true`.

**During**
- Watch the CGF Grafana dashboard. The state timeline tells you whether
  loop-backs are happening (which means the eval gate is doing its job).
- Don't kill the container mid-run. Resume is the supported path:
  `make optimize` again.

**After**
- Diff `{resource}.md` vs `{resource}-v{N}.md`. Sometimes the win is
  obvious; sometimes you want to merge by hand.
- Read `CHANGELOG.md` for the narrative.
- If the optimized version regresses on something the eval missed,
  add a scenario to the eval suite and re-run. The eval suite is in
  `eval/eval-suite.yaml` and is editable.

## See also

- `src/harness/optimization/CLAUDE.md` — internals (state machine,
  schemas, Python API, gotchas)
- `docs/OBSERVABILITY.md` — full metrics/dashboards/alerts stack
- `docs/CGF-EVAL-ROADMAP.md` — forward plan (Phase B/C/D, Stage 4)
- `docs/PHASEA_SUMMARY.md` — Phase A retrospective
- `tests/smoke/python-expert/`, `tests/smoke/iac-team/` — runnable
  reference fixtures
- `README.md` — top-level quick start
