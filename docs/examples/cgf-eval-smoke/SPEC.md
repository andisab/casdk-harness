# CGF Eval Smoke Test

A tiny 2-resource spec for end-to-end testing of the CGF eval framework.
Hand-crafted to exercise every phase of the pipeline (RESEARCH → DESIGN → QA →
GENERATE → EVAL_DESIGN → ITERATE → EXECUTION_EVAL → VALIDATE → COMPLETE) with
the smallest possible workload.

## Purpose

Smoke-test fixture for verifying that the CGF eval pipeline (Phase A) runs
end-to-end against real LLM calls. Run this whenever you want to confirm:

- Agent dispatch works for all 7 CGF agents (research-lead, resource-architect,
  context-engineer, eval-architect, prompt-optimizer, coherence-validator,
  result-evaluator).
- The eval-suite YAML the architect produces validates against the schema.
- `EvalHarness` runs scenarios against baseline (v0) and candidate (v1) files.
- Promotion / refinement / loop-back logic kicks in correctly.
- Telemetry surfaces in Grafana (phase duration, scenarios, arm scores,
  judge no-decisions, tokens-to-goal).

## Capabilities

- **Greeting** — Respond politely to a simple "say hello" prompt with a
  contextually-appropriate greeting.
- **Calculation** — Perform a single arithmetic computation given two
  numbers and an operator, returning the numeric result.

## Constraints

- Each resource MUST be under 50 lines so the pipeline finishes quickly.
- The agent MUST NOT call Bash or Write — its tools are limited to plain
  conversational response.
- The skill MUST activate on the literal phrase "calculate" and stay quiet
  for any other prompt.

## Proposed Structure

- `agents/greeter.md` — Greeter agent (reads prompt, returns greeting).
- `skills/calculator/SKILL.md` — Calculator skill (activates on "calculate",
  performs single op).

## Notes

This spec is deliberately trivial — the value is in exercising the pipeline,
not in producing useful resources. After the run completes, expect to see:

- `workspace/cgf-eval-smoke/agents/greeter.md` and `agents/greeter-v1.md`
- `workspace/cgf-eval-smoke/skills/calculator/SKILL.md` and `SKILL-v1.md`
- `workspace/cgf-eval-smoke/eval/eval-suite.yaml`
- `workspace/cgf-eval-smoke/eval/results/<resource>-v1/eval-results.json`
- `workspace/cgf-eval-smoke/eval/execution-eval-round-1.json`
- `workspace/cgf-eval-smoke/CHANGELOG.md`

If the resources don't promote on the first round, the loop-back to ITERATE
will fire (max 2 feedback rounds), which is itself useful smoke for the
feedback-history wiring.

## How to run

```bash
# 1. Copy this fixture into a workspace under workspace/.
mkdir -p workspace/cgf-eval-smoke
cp docs/examples/cgf-eval-smoke/SPEC.md workspace/cgf-eval-smoke/SPEC.md

# 2. Run the optimizer (requires ANTHROPIC_API_KEY in .env).
make optimize

# 3. While it runs, watch Grafana:
#    open http://localhost:3000 → "Claude Agent Harness — CGF Optimization"
#    Look for the new "Eval Framework (Stage 3 Phase A)" row.
#
#    Expected (post-Phase-A-merge): phase-duration p50/p95 by phase,
#    tokens-to-goal histogram by resource_type, scenarios-by-outcome rate,
#    per-arm pass-rate distribution, judge no-decisions over time.

# 4. After completion, inspect artifacts:
ls workspace/cgf-eval-smoke/eval/
cat workspace/cgf-eval-smoke/eval/execution-eval-round-1.json | jq
```

## Cost ballpark

With small resources and a single eval scenario per resource, expect
~$0.10–$0.50 in API spend per full run (varies with judge model). Set
`CGF_JUDGE_MODEL=haiku` and `CGF_DESIGN_MODEL=haiku` in `.env` to cut cost
roughly 5–10× at the price of noisier verdicts (acceptable for a smoke
test).
