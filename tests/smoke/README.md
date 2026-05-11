# Smoke Tests for the CGF Optimization Harness

End-to-end smoke fixtures used to exercise and refine the harness against
real LLM calls. **Not** unit tests — these are slow, costly, and
non-deterministic by design. The point is to validate that the
full optimization pipeline produces the artifacts and telemetry it
claims to, and to surface refinement opportunities after each run.

---

## Goals

1. **Validate that Phase A runs end-to-end** — every phase produces its
   documented deliverable on disk, with telemetry visible in
   Prometheus/Grafana.
2. **Surface harness defects** — agent prompts that misbehave, signal
   parsers that miss edge cases, orchestrator phases that silently
   short-circuit, telemetry that doesn't reach Prometheus.
3. **Drive iterative improvement** — each smoke run is followed by a
   research pass to identify what could be more robust, generalizable,
   or stable. Findings feed back into harness code, agent prompts, or
   the smoke fixtures themselves.

---

## Running a smoke test

From the repo root, with services up (`make up`):

```bash
make smoke FIXTURE=python-expert     # single-resource agent
make smoke FIXTURE=iac-team          # multi-resource plugin (3 agents + 1 command + 17 skills)
```

The `make smoke` target:

1. Copies the fixture's directory into `workspace/<fixture-name>/`
   (overwrites any prior contents — fresh start every run).
2. Invokes the multi-resource orchestrator against the copied workspace.
3. Streams logs to the host terminal.

After the run completes, inspect:

- `workspace/<fixture-name>/sessions/optimization-state.json` — final
  phase state, per-resource quality scores, feedback history.
- `workspace/<fixture-name>/eval/eval-suite.yaml` — eval suite the
  architect produced (must exist post-EVAL_DESIGN).
- `workspace/<fixture-name>/eval/execution-eval-round-*.json` —
  aggregate eval results (must exist post-EXECUTION_EVAL).
- `workspace/<fixture-name>/CHANGELOG.md` — human-readable run history.
- Grafana CGF dashboard (`http://localhost:3000/d/casdk-cgf`) — Phase A
  panels (Eval Phase Duration, Tokens to Goal, Scenarios by Outcome,
  Per-Arm Pass Rate, Judge No-Decisions) should have data after the
  EXECUTION_EVAL phase fires.

---

## PASS criteria

A smoke run is **PASS** when:

1. **Artifacts** — every documented deliverable file exists on disk:
   - `eval/eval-suite.yaml`
   - `eval/execution-eval-round-1.json`
   - per-resource `-v1.md` files (and `-v2.md` if any refinement loops fired)
   - `CHANGELOG.md`
2. **Telemetry** — Prometheus queries return non-empty results for the
   five Phase A series:
   - `harness_eval_phase_duration_seconds_count`
   - `harness_eval_scenarios_total`
   - `harness_eval_arm_score_count`
   - `harness_eval_tokens_to_goal_count`
   - `harness_eval_judge_no_decision_total` (may be zero — that's a clean signal too)
3. **State** — `optimization-state.json` reaches `current_phase: COMPLETE`
   with no resource in `status: "failed"` (unless the fixture's
   `EXPECTED.md` documents an intentional failure).

Additional criteria layer on as the harness matures (e.g., promotion-loop
coverage, refinement-feedback round-trip, deterministic re-runs).

---

## Fixtures

| Fixture | Type | Resources | Tests |
|---|---|---|---|
| [`python-expert/`](./python-expert/) | single-resource | 1 agent | Baseline single-agent optimization; deep iteration on prose-style content; demonstrates ITERATE → EVAL_DESIGN → EXECUTION_EVAL on one resource |
| [`iac-team/`](./iac-team/) | multi-resource | 3 agents + 1 command + 17 skills | Plugin-scale orchestration; tests resource-architect's dependency handling, cross-resource coherence, per-resource eval suites |

Each fixture has its own `README.md` documenting purpose, expected
outcomes, and known caveats.

---

## Workflow: smoke → research → refine

The smoke tests are inputs to a refinement loop, not a final check:

1. **Run** a smoke fixture against the current harness.
2. **Assess** the results:
   - Did all PASS criteria hold? If not, which failed and why?
   - Look at the agent transcripts (in `eval/transcripts/`) — were the
     completions reasonable? Did the optimizer iterate productively?
   - Did the LLM-judge make sensible verdicts?
   - Are any harness logs warning or erroring repeatedly?
3. **Research** the defect classes that surfaced:
   - Agent prompts that need sharpening?
   - Signal/parser logic edge cases?
   - Phase orchestration ordering or fail-fast gaps?
   - Telemetry exposure gaps?
4. **Refine** — open a fix branch, address the defects, add unit-test
   coverage where applicable.
5. Repeat — the smoke run is a regression check for the previous
   refinement and a fresh diagnostic surface for the next.

Findings worth keeping (across runs) are written into the fixture's
`README.md` or this top-level doc.

---

## Planned future smoke fixtures

We expect to grow this directory to roughly half a dozen fixtures
covering different aspects of the harness. Candidates being considered:

- **MCP server + tools** — exercises deterministic graders (schema
  validation, exact-match outputs)
- **Skill-trigger accuracy** — positive + negative invocation contexts;
  tests trigger precision/recall measurement (Phase B)
- **Resume / checkpoint** — kill orchestrator mid-phase, restart, verify
  the phase resumes from the saved state
- **Error recovery** — deliberately broken SPEC; tests fail-fast and
  human-review escalation paths
- **Cost-control** — verify `CGF_EVAL_TOKEN_BUDGET` enforcement
- **Concurrent runs** — two smokes in parallel; verify metrics-server
  port-collision handling and workspace isolation

Each new fixture should land with its own subdirectory, `README.md`,
and any baseline files needed.

---

## Cost note

Smoke runs make real LLM calls. Typical per-run cost (with default
sonnet for design + opus for judge, sonnet-only is ~3-5× cheaper):

| Fixture | Approximate cost |
|---|---|
| python-expert | $0.50 – $2 |
| iac-team | $3 – $8 |

Cost is **not** the primary optimization target for this surface —
correctness of the harness is. Don't optimize away an exercise that
catches a real defect just to save 50 cents.
