# Smoke fixture: python-expert (single-resource)

Single agent (`python-expert.md`, ~2600 lines) optimized via the
single-resource code path (`harness.cgf_session`).

## What this fixture exercises

- **Single-resource pipeline** — `cgf_session.py` orchestration
  (RESEARCH → ITERATE → VALIDATE)
- **Self-critique iteration** on prose-heavy agent content
- **Quality scoring** by `cgf-prompt-optimizer` (no EVAL_DESIGN /
  EXECUTION_EVAL — those phases live only in
  `multi_resource_orchestrator`)
- Research-team and context-engineering plugin agents reachable from
  the single-resource session

## What this fixture does NOT exercise

- Phase A two-arm comparison eval (`EvalHarness`)
- `cgf-eval-architect` agent
- Promotion gate / refinement loop-back
- Cross-resource dependency planning

For Phase A coverage, see [`../iac-team/`](../iac-team/) instead.

## PASS criteria

A run is PASS when:

1. **Artifacts exist** on completion:
   - `python-expert-v1.md` (the optimized output)
   - `CHANGELOG.md` (run history)
   - `research/eval_criteria.yaml` (synthesized criteria)
   - `sessions/python-expert-v1.md.summary.json` (per-iteration summary)
2. **Quality score recorded** — `sessions/task_list.json` shows the
   resource with a non-null quality value
3. **No silent errors** — no harness log lines at ERROR level beyond
   documented expected failures
4. **Telemetry registered** — even though Phase A panels stay empty for
   single-resource runs, the harness-side `harness_*` series should be
   visible in Prometheus

## Run

From the repo root:

```bash
make smoke FIXTURE=python-expert
```

This copies the fixture into `workspace/python-expert/` (overwriting
any prior contents) and runs the single-resource optimization session.

## Cost

Typical run cost: **$0.50 – $2** with sonnet for both design and judge.
Single-resource flow is shorter than multi-resource and doesn't run
two-arm eval comparisons.

## Source of the baseline

`python-expert.md` is a copy of the earlier (pre-optimization) version
of the python-expert agent that lived in `workspace/python-expert/`
prior to 2026-05-11. Preserved here as a stable v0 input so smoke runs
are repeatable.
