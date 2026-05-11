# Smoke Test Validation Plan

**Status as of 2026-05-11 end-of-session:** `phase-a-fixes` branch holds
all 5 Phase A defect fixes + the new `tests/smoke/` framework with two
fixtures (`python-expert`, `iac-team`). Nothing pushed to remote yet.
This document defines the two-phase validation plan to take from here.

---

## Phase 1 — Validate python-expert (single-resource path)

**Goal:** confirm the single-resource code path
(`harness.cgf_session.py`) produces correct grading + refinement on a
real agent. This is the cheapest, simplest test surface; if it fails,
all the more complex multi-resource work is wasted effort.

### Pre-flight

```bash
# Ensure services are up
make up

# Verify the fixture is present
ls tests/smoke/python-expert/
# Expected: README.md  SPEC.md  python-expert.md

# Verify make target works (no API calls yet)
make smoke-list
```

### Run

```bash
make smoke FIXTURE=python-expert
```

Expect: ~$0.50 – $2 in API calls, ~5–15 minutes wall time.

### What to look for during the run

- **Plugin discovery line** should show all three plugins:
  `Plugin discovery complete agents=13 plugins=['research-team', 'context-engineering', 'cgf-agents'] skills=10`
  (Verifies defect 1 stays fixed on the single-resource path.)
- **Phase sequence** should be RESEARCH → ITERATE → VALIDATE → COMPLETE
  (single-resource path skips EVAL_DESIGN / EXECUTION_EVAL).
- **No silent log errors** — watch for `[error]`-level lines that
  weren't there in previous runs.

### PASS criteria

A successful Phase 1 produces:

1. `workspace/python-expert/python-expert-v1.md` — the optimized
   agent (longer or restructured vs the v0 baseline, with the
   target improvements from SPEC.md reflected in the content)
2. `workspace/python-expert/CHANGELOG.md` — readable run history
3. `workspace/python-expert/sessions/python-expert-v1.md.summary.json`
   — per-iteration quality scores (non-null)
4. `workspace/python-expert/research/eval_criteria.yaml` — synthesized
   criteria from the research pass
5. Final state: `current_phase: COMPLETE` in
   `workspace/python-expert/sessions/optimization-state.json` (if the
   single-resource path uses optimization-state.json; cgf_session.py
   may use task_list.json instead — verify which)

### Assessment after the run

Spend ~15 minutes reading the produced artifacts and answering:

1. **Does python-expert-v1.md actually reflect the SPEC's target
   improvements?** Specifically:
   - Are the 5 checklist items from "Target Improvements" addressed?
     (async context managers, exception chaining, Protocol vs ABC,
     TaskGroup, typing.Self)
   - Is the structure / length reasonable, or did the optimizer
     bloat the file?
2. **Are the quality scores believable?** Review
   `sessions/python-expert-v1.md.summary.json`. If overall quality
   is 0.92, does the diff actually look that improved?
3. **Was there any silent failure?** Search for `[warning]` and
   `[error]` lines in the run log; do any indicate broken paths the
   smoke didn't surface?
4. **Were research findings actually used?** Check
   `research/eval_criteria.yaml` and compare to changes in v1 —
   evidence the optimizer pulled from research vs hallucinated?

### Defect classes to look for

- Optimizer producing prose-style improvements when SPEC asked for
  specific patterns
- Self-critique inflating quality scores without real content delta
- Research phase producing irrelevant/generic findings
- The single-resource path quietly skipping a phase

### If Phase 1 PASSES

Move to Phase 2 (iac-team). Document any nits found in
`tests/smoke/python-expert/README.md` under a new "Known caveats"
section.

### If Phase 1 FAILS

Treat it as a new defect to triage. Common likely causes:
- Plugin discovery missed something in the single-resource path
  (subagent fix may need a sibling fix in `cgf_session.py`)
- The python-expert.md baseline file's format triggers an unexpected
  optimizer behavior
- One of the 5 phase-a-fixes has an unintended interaction with the
  single-resource flow

Surface the defect, file a fix on a sub-branch, retry. Repeat the
smoke → research → refine loop.

---

## Phase 2 — Research + design iac-team smoke

**Goal:** decide and implement the actual setup.sh / teardown.sh and
fill in the SPEC's grader expectations so iac-team is a real
end-to-end Phase A test, not a scaffold.

This phase splits into **research** (no LLM calls, ~30 min of
investigation) and **implementation** (filling in the TODO blocks
and SPEC adjustments).

### Research questions to answer before running iac-team

#### R1. Local-infrastructure mode

Which provisioning approach gives the right cost / fidelity tradeoff?

| Option | Pros | Cons | Decision criteria |
|---|---|---|---|
| **kind** (K8s in Docker) | Free, fast, real K8s API | No EKS-specific behavior | Best if eval graders use `kubectl --dry-run=client` / `kubeconform` |
| **kind + localstack** | + Local AWS API emulation | localstack CE doesn't cover EKS fully (Pro does) | Best if graders need both `kubectl` AND `aws` CLI calls |
| **Real AWS EKS** | High fidelity | Costs ($0.10/hr + data), slow to spin up (~15 min), needs cleanup | Best for periodic / pre-release smoke; overkill for daily refinement |
| **No cluster** (terraform-validate only) | Free, fastest | Skips Helm/K8s graders entirely | Best if Phase 1 has shown the multi-resource path needs more iteration before realistic graders |

**Recommendation to investigate:** start with **kind only** for the
first iac-team run. Reasons: simplest, most repeatable, and the
SPEC's existing quality criteria
(`kubectl --dry-run`, `helm lint`, `kubeconform`, `terraform validate`,
`tfsec`, `trivy`) all work without cloud creds.

If/when smoke catches real defects in EKS-specific generation paths,
upgrade to kind + localstack or real AWS.

#### R2. What graders should cgf-eval-architect actually pick?

When iac-team runs, the cgf-eval-architect agent reads the SPEC and
designs eval scenarios with graders. We want to verify it picks
deterministic graders where they apply rather than defaulting to
llm_judge for everything. Research questions:

- For each of the 21 resources, what's the cheapest grader that
  would catch a real regression?
  - Agents (3): trajectory graders (tool-call ordering) + llm_judge
    for narrative quality
  - Command (1): code_syntax + trajectory
  - Skills (17): mostly `contains` / `regex` checks on output
    content + maybe `code` graders for any Python/shell snippets
- Does the architect, given this SPEC, actually generate those
  graders? Or does it fall back to llm_judge for everything?
  Inspect `eval/eval-suite.yaml` after the run to find out.

#### R3. Setup.sh implementation

Concrete tasks to fill in `tests/smoke/iac-team/setup.sh`:

- [ ] Provision a kind cluster if not present (`kind create cluster --name casdk-smoke-iac --image kindest/node:v1.31.0`)
- [ ] (Optional) Spin up localstack if `SMOKE_USE_LOCALSTACK=1`
- [ ] (Optional) Verify real AWS creds if `SMOKE_USE_REAL_AWS=1`
- [ ] Verify required CLIs are on PATH (`kubectl`, `helm`, `terraform`, `kubeconform`, `tfsec`, `trivy`)
- [ ] Set env vars the eval graders need (e.g., `KUBECONFIG`, `AWS_ENDPOINT_URL` for localstack)

#### R4. Teardown.sh implementation

Concrete tasks to fill in `tests/smoke/iac-team/teardown.sh`:

- [ ] Delete the kind cluster (`kind delete cluster --name casdk-smoke-iac`)
- [ ] Stop localstack container if started
- [ ] Tolerate "not found" / partial failures (best-effort cleanup)
- [ ] Respect `SMOKE_KEEP_RESOURCES=1` (leave running for post-mortem)

#### R5. Cost ceiling

iac-team has 21 resources. With sonnet for design and opus for judge,
worst case is ~$8/run. Decide:

- Initial smoke runs: cap with `CGF_EVAL_TOKEN_BUDGET=2_000_000` to
  prevent runaway feedback loops?
- Use sonnet-only (skip opus judge) for the first few iterations to
  cut cost while still catching gross harness defects?

### Run

```bash
# After R1-R5 are answered and setup.sh / teardown.sh are filled in:
make smoke FIXTURE=iac-team
```

Expect: ~$3 – $8 in API calls, ~30–60 minutes wall time.

### PASS criteria

A successful Phase 2 produces everything python-expert produces
**plus**:

1. `workspace/iac-team/eval/eval-suite.yaml` — generated by
   cgf-eval-architect (proves defect 2 + 3 + 4 fixes work end-to-end:
   architect uses Write, signal is parsed despite Markdown decoration,
   orchestrator doesn't false-positive when file missing)
2. `workspace/iac-team/eval/execution-eval-round-*.json` — per-arm
   eval results across all 21 resources
3. `workspace/iac-team/eval/transcripts/` populated with baseline +
   candidate transcripts
4. Per-resource `eval/results/{path}-v1/eval-results.json`
5. Prometheus / Grafana shows non-empty data on all five Phase A
   panels (proves defect 5 metrics-exposure fix works)
6. At least one resource exhibits either successful promotion **or**
   refinement loop-back to ITERATE — exercising the
   `_should_promote` gate's positive and negative paths

### Assessment after the run

Wider than Phase 1, because iac-team exercises more of the harness:

1. **Did eval-architect pick reasonable graders?** Inspect
   eval-suite.yaml. Count grader types per resource. If everything
   is llm_judge, the architect's prompt may need refinement to push
   it toward deterministic graders where applicable.
2. **Did the gate work?** If every resource promoted, are the v1
   versions actually better? If everything regressed, the gate
   threshold may need tuning.
3. **Did the feedback loop-back fire?** Check `feedback_history`
   length in optimization-state.json. If always 0, either every
   resource promoted (suspicious) or the loop-back code never fires
   when it should (defect).
4. **Did kind cluster actually validate anything?** Cross-reference
   eval transcripts with actual `kubectl --dry-run` / `helm lint`
   invocations. If graders never invoke the CLI tools, the cluster
   provisioning is wasted setup.
5. **Telemetry coverage:** every Phase A metric should have data.
   If one is missing, that instrument is wired wrong.

### Likely defects to surface

iac-team is bigger and exercises more code paths than python-expert.
Expect to find:
- Race conditions / order-of-operations issues across resources
- Memory / token budget exhaustion mid-run
- Eval graders that work on individual resources but fail on the
  21-resource aggregate
- Coherence validator findings that suggest real cross-resource
  issues the architect missed
- The "0 tool calls" anti-pattern in other agents besides eval-architect

Each defect → filed on a sub-branch, fixed, smoke re-run.

---

## Branch / merge strategy

`phase-a-fixes` lands on `contextgrad-eval` once Phase 1 PASSes and
the fixes have at least one real-LLM validation behind them. All this
work stays on `contextgrad-eval` for the foreseeable future — **no
mirror to `main` planned**. `main` continues to hold pre-Phase-A
work; the Phase A / eval-framework / smoke-test surface is an
integration branch experiment until further notice.

After Phase 1 PASS:

```bash
git checkout contextgrad-eval
git merge phase-a-fixes
git push origin contextgrad-eval
```

Phase 2 PASS does not trigger a `main` merge. Continue iterating on
`contextgrad-eval` with sub-branches for each defect class as it
surfaces.

---

## What to add to `phase-a-fixes` between sessions

If context clears and we pick up here next session:

1. Run `make smoke FIXTURE=python-expert` (Phase 1)
2. Read the resulting artifacts; fill in
   `tests/smoke/python-expert/README.md` "Known caveats" section
   with whatever was observed
3. Answer R1–R5 (Phase 2 research)
4. Fill in `tests/smoke/iac-team/setup.sh` and `teardown.sh` TODOs
5. Run `make smoke FIXTURE=iac-team` (Phase 2)
6. Same assessment loop
7. Merge to `contextgrad-eval` only (no `main` mirror — see branch
   strategy above)

After both PASS, the branch is integrated into `contextgrad-eval` for
continued iteration. The Phase A surface stays out of `main` for the
foreseeable future.
