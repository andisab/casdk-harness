# Smoke Test Validation Plan

## ✅ Phase 1 — PASSED (2026-05-11, commit `12633e9`)

Run #7 of the `python-expert` fixture met **all 10** pass criteria
(see the "Pass criteria for Phase 1 smoke run" section below):

- Exit 0; `task_list.current_phase == complete`; `iteration == 1`
- Signal counts: `research=1`, `iterate=1`, `evaluate=1`
- Baseline `python-expert.md` hash unchanged across the run
- `reviews/v1_review.md` written at the correct path with parseable
  `<cgf_directive>` XML; ACCEPT honored as terminal (no further iter)
- Wall time ~22 min (≤25 min target)
- 6 distinct defects surfaced + fixed across runs #1–#6; each fix
  prevented its target defect from recurring on subsequent runs

Hardening that landed with the PASS (commit `12633e9`):

- **P0.1** baseline-hash integrity check + `CGF_BASELINE_HASH_CHECK` override
- **P0.2** pair-wise `iter ≤ eval + 1` contract enforcement
- **P0.3** hard iteration cap via `CGF_MAX_ITERATIONS` (default 3)
- **P0.4** review-on-disk + recommendation parse; ACCEPT/REJECT force terminal
- **P1.4** signal watchdog (warn by default; `CGF_SIGNAL_STRICT=1` to fail)
- 10s file-poll grace period for Task-subagent filesystem-write race
- Stopped embedding resource content in orchestrator system prompt
  (was hitting Linux `MAX_ARG_STRLEN=128KB`)
- Orchestrator prompt rewritten with `<critical_rules>` /
  `<lock_step_protocol>` / `<stop_after_signal_contract>` XML sections,
  10 Hard Rules, lock-step transcript examples
- Evaluator prompt: SPEC.md is input #1; mandatory `<cgf_directive>`
  XML header replaces ambiguous markdown-bullet contract
- 40 new unit tests in `tests/unit/test_cgf_session.py`; suite at 1791
  passing post-hardening

Follow-up captured (deferred to after Phase 2): **Stage 4 Task 9 —
CREATE-mode support** in `cgf_session.py` (commit `822722c`,
`docs/CGF-EVAL-FRAMEWORK.md`). The orchestrator prompt documents a
CREATE phase but the Python runner hard-codes start-in-research; this
branch is dead from the runner's perspective. ~80–120 LoC sketch +
fixture derived from the Phase-1A v1 output.

### Runtime evidence — what's on disk now

The workspace dir on the host is clean (only `.DS_Store` + `.git` —
the smoke artifacts from run #7 were cleared post-run). The
authoritative record of the PASS is therefore:

- Commit `12633e9` message body (enumerates the 10 pass criteria met
  by run #7, including signal counts, baseline-hash, wall time)
- 40 new unit tests in `tests/unit/test_cgf_session.py` covering all
  P0/P1 hardening + the XML directive parser + the 3 legacy markdown
  fallbacks; full suite at **1791 passing** post-hardening
- `memory/checkpoints/` shows only later autonomous-mode checkpoints
  from 2026-05-12, not the smoke run — no live `summary.json` or
  `task_list.json` to re-summarize from disk

Re-running the smoke is the only way to regenerate the on-disk
artifacts; the contract is now enforced in code so a regression would
hard-fail rather than silently produce bad output.

### Branch state

- Branch: `phase-a-fixes` (10 commits ahead of `contextgrad-eval`,
  branched off `7c31269`; tip commits are `12633e9` hardening and
  `822722c` Stage 4 Task 9 doc).
- Per the Branch / merge strategy section below, the next step after
  Phase 1 PASS is `git merge phase-a-fixes` onto `contextgrad-eval`
  and push. **Not yet done** — the merge is pending.

**Next:** (a) merge `phase-a-fixes` → `contextgrad-eval`; (b) start
Phase 2 (iac-team, multi-resource path) with the R1–R5 research
questions below.

---

## ⏳ Phase 2 — prep complete (2026-05-12, awaiting paid run)

The merge to `contextgrad-eval` shipped as `4b6cb88` (pushed). Phase 2
prep work has now landed on `phase-a-fixes`:

- README inconsistency fixed: 21 → 18 resources (3 agents + 1 command
  + 14 skills); GCP skills (`gcloud-cli`, `gcp-gke`) confirmed removed.
- `setup.sh` rewritten from scaffold → actionable: tooling sanity probe
  always runs; kind / localstack / real-AWS are all opt-in via
  `SMOKE_USE_KIND=1` / `SMOKE_USE_LOCALSTACK=1` / `SMOKE_USE_REAL_AWS=1`.
- `teardown.sh` rewritten: best-effort cleanup, honors
  `SMOKE_KEEP_RESOURCES=1` for post-mortem.

### R1–R5 decisions (resolved)

**R1 — Local-infrastructure mode: no infra by default.** Phase A
graders that don't need a cluster — `terraform validate`,
`helm lint --strict`, `kubeconform`, `tfsec`, `trivy fs`,
`code_syntax`, `llm_judge` — cover the SPEC's quality criteria. If
the eval-architect picks `kubectl --dry-run=server` or any grader that
actually hits AWS, the run will surface it as a defect and the next
iteration opts into `SMOKE_USE_KIND=1`. Rationale: smallest-blast-radius
first run; we don't yet know which graders the architect will pick.

**R2 — Grader selection: post-run inspection.** We won't pre-constrain
the eval-architect. After the run, inspect
`workspace/iac-team/eval/eval-suite.yaml` and count grader types:

- Agents (3) — expect trajectory + llm_judge
- Command (1) — expect code_syntax + trajectory
- IaC skills (14) — expect a mix of `code_syntax` (terraform/yaml
  validation), `contains` / `regex` (link/version checks), `llm_judge`
  (narrative quality)

If everything falls back to `llm_judge`, file it as a prompt-tuning
defect on `cgf-eval-architect.md` and re-run.

**R3 — setup.sh: SHIPPED.** Actionable script, no-infra default,
opt-in flags documented above. Adds a tooling sanity probe so missing
CLIs in the harness image surface as warnings rather than silent
grader failures mid-run.

**R4 — teardown.sh: SHIPPED.** Same opt-in flag set; best-effort
cleanup; `SMOKE_KEEP_RESOURCES=1` preserves state for post-mortem.

**R5 — Cost ceiling: $4 target / $8 hard cap.** First-run budget:

| Knob | Value | Rationale |
|---|---|---|
| `CGF_DESIGN_MODEL` | `sonnet` | Architect needs reasoning; haiku is too noisy at scale |
| `CGF_JUDGE_MODEL` | `sonnet` | Skip opus for first run — catches harness defects, not subtle quality regressions |
| `CGF_MAX_ITERATIONS` | `2` | Cap loop-backs; 18 resources × 3 iter is runaway-cost territory |
| `CGF_EVAL_TOKEN_BUDGET` | `2_000_000` | Hard ceiling; orchestrator should refuse to start a new round once exceeded |
| `CGF_EVAL_PROMOTION_EPSILON` | (default) | Use shipped default; tune in Phase B |

Stop the run manually if Grafana cost panel exceeds **$8**.

### What's still required before pushing the button

1. `make build` (rebuild image so latest fixture changes are in the
   container's `/app/tests/smoke/iac-team/`)
2. `make up` (ensure all 6 default services healthy)
3. Confirm `.env` has the budget knobs set per R5 (or run with inline
   `CGF_MAX_ITERATIONS=2 CGF_DESIGN_MODEL=sonnet ... make smoke
   FIXTURE=iac-team`)
4. Open Grafana CGF dashboard in a browser tab so cost can be watched
   in real time
5. Kick off: `make smoke FIXTURE=iac-team`

Expected wall time: **30–60 min**. Cost target: **$3–8**.

### Assessment after the run

See the "Assessment after the run" + "Likely defects to surface
(Phase 2)" sections further below. Key questions:

1. Did eval-architect pick reasonable graders, or fall back to
   llm_judge everywhere?
2. Did the promotion gate fire on at least one resource (either
   promote or loop-back)?
3. Did all five `harness_eval_*` Prometheus instruments populate?
4. Any contract violations in logs from the Phase-1 hardening
   (baseline-hash, iter↔eval pairing, signal watchdog)?

---

**Original status (2026-05-11 mid-session):** `phase-a-fixes` branch
holds the Phase A defect fixes + the `tests/smoke/` framework with
two fixtures (`python-expert`, `iac-team`). Two python-expert smoke
runs have executed; both surfaced protocol bugs (orchestrator agent
skipping the evaluate phase, generating multiple iterations without
targeted feedback, overwriting the pristine baseline file). This
document is the **single source of truth** for both:

- **Phase 1** — finish hardening + a clean python-expert run (single-resource path) — ✅ PASSED, see banner above
- **Phase 2** — design + run iac-team smoke (multi-resource path)

Execute Phase 1 top-to-bottom first. Phase 2 work is gated on Phase 1
passing.

---

## Phase 1 — Harden + validate python-expert (single-resource path)

**Goal:** confirm the single-resource code path
(`harness.cgf_session.py`) produces correct grading + refinement on a
real agent. This is the cheapest, simplest test surface; if it fails,
all the more complex multi-resource work is wasted effort.

### Bugs surfaced from run #2 (the run that prompted this plan)

| # | Bug | Severity | Evidence |
|---|---|---|---|
| 1 | Original `python-expert.md` overwritten with v1 content | **CRITICAL — data loss** | `md5(python-expert.md) == md5(python-expert-v1.md)` after run |
| 2 | Agent fired `[ITERATION_COMPLETE]` for iters 1+2 then skipped iter3 | High | `task_list.iteration=2` but `python-expert-v3.md` exists |
| 3 | Three iterations produced, zero evaluations | High | No `reviews/` directory created; `EVALUATE_COMPLETE` count = 0 |
| 4 | Iterations were untargeted (each one added a new tangential section rather than addressing eval gaps) | High | CHANGELOG lists "AsyncExitStack section added in v2" / "Anti-Pattern section added in v3" — agent's own choices, no `REFINEMENT_HINTS` source |
| 5 | `summary.json` quality scores and word counts disagree with reality (~25% off vs `wc -w`) | Medium | Agent self-reported `v1=12850 words` but actual `wc -w` = 10344 |
| 6 | `CHANGELOG.md` says `Status: COMPLETE` mid-run | Medium | Written at 12:42 while state-machine still in `iterate` |
| 7 | Run took 90+ min for one resource (vs $0.50-2/15min predicted) | Medium | Cumulative $10+ spent before manual stop |
| 8 | Dashboard couldn't route correctly because run pre-dated `record_run_path` | Low | Expected — fixes itself on next run |

### Plan items

#### P0 — Correctness (blocks next smoke run)

##### P0.1 Protect original file
**File:** `src/harness/cgf_session.py`

- At start of `_run_optimization_phase`, compute SHA-256 of resource file
  (whatever `_find_resource_path()` returns)
- Store the hash in `task_list` (new field `baseline_hash`)
- Before processing each phase signal (`[RESEARCH_COMPLETE]`,
  `[ITERATION_COMPLETE]`, etc.), re-hash the baseline
- If hash changed: hard-fail with explicit error referencing the file,
  expected hash, observed hash. Call `record_phase_entry(resource,
  "failed")` and return `False`
- Add env-var override `CGF_BASELINE_HASH_CHECK=0` to disable
  (default: enabled)

**Test:** unit test in `tests/unit/test_cgf_session.py` that constructs
a runner, mutates the resource file, calls the signal handler, asserts
the run is rejected with `task_list.error` populated.

**LoC estimate:** ~40

##### P0.2 Pair-wise iter↔eval enforcement
**Files:** `src/harness/cgf_session.py`, `cgf-orchestrator.md`

Current contract: counts iter and eval signals independently and only
checks at `[OPTIMIZATION_COMPLETE]`. New contract is **stateful**:

- `iter_count` must never exceed `eval_count + 1`
  (i.e. each iteration must be followed by an evaluation before the next)
- Reject 2nd `[ITERATION_COMPLETE]` if `eval_count < 1`
- Reject 3rd `[ITERATION_COMPLETE]` if `eval_count < 2`
- General: on `[ITERATION_COMPLETE]`, if `iter_count > eval_count + 1`,
  mark the violation, log error, set phase to `failed`, return `False`

Update orchestrator prompt to lock-step the protocol:

> After writing `*-vN.md`, you MUST emit `[ITERATION_COMPLETE]` in the
> SAME message. You MUST then dispatch
> `cgf-agents:cgf-result-evaluator` via Task tool. When it returns,
> write the review to `workspace/{resource}/reviews/v{N}_review.md` and
> emit `[EVALUATE_COMPLETE]`. Only THEN may you start another iteration
> (if RECOMMENDATION is REFINE) OR emit `[OPTIMIZATION_COMPLETE]` (if
> ACCEPT). You may never write `v{N+1}.md` until `[EVALUATE_COMPLETE]`
> for `vN` has fired.

**Test:** unit test feeds a synthetic content stream with two
`[ITERATION_COMPLETE]` signals back-to-back and asserts the second one
triggers a violation.

**LoC estimate:** ~60 (Python) + prompt rewrite

##### P0.3 Configurable iteration cap
**Files:** `src/harness/config.py`, `src/harness/cgf_session.py`,
`.env.example`

- New env var: `CGF_MAX_ITERATIONS=3` (default 3)
- Wire through `RuntimeConfig`
- When `iter_count == CGF_MAX_ITERATIONS`, the next signal MUST be
  `[EVALUATE_COMPLETE]` then `[OPTIMIZATION_COMPLETE]` — refuse another
  `[ITERATION_COMPLETE]`
- Expose `harness_run_iteration_cap{resource}` gauge so Grafana can
  show "iter 2 of 3"
- Deprecate or rename the existing `CGF_ITERATIONS=10` (currently
  inactive code path; clarify in CLAUDE.md)

**LoC estimate:** ~40

##### P0.4 Require eval review on disk
**Files:** `src/harness/cgf_session.py`

- `[EVALUATE_COMPLETE]` is only accepted if
  `workspace/{resource}/reviews/v{N}_review.md` exists where `N =
  task_list.iteration` at the time
- If review file missing: hard-fail with explicit error
- Python parses the review for the `RECOMMENDATION: ...` line
  (frontmatter or first-match)
- Store recommendation in `task_list.checkpoints[-1].recommendation`
- If recommendation is `REFINE`, parse `TARGET_SECTIONS` /
  `TARGET_COMPETENCIES` / `REFINEMENT_HINTS` blocks; pass them as a
  structured prompt to the next iteration so the orchestrator can't
  ignore them
- If recommendation is `ACCEPT`, the next signal MUST be
  `[OPTIMIZATION_COMPLETE]` — refuse another iteration
- If recommendation is `REJECT`, also force terminal — `[OPTIMIZATION_FAILED]`

**Test:** unit test asserts missing review file → reject;
malformed review (no RECOMMENDATION line) → reject; ACCEPT
recommendation forces terminal on next iter attempt.

**LoC estimate:** ~80 (parser + enforcement + tests)

#### P1 — Compliance reinforcement (ships with P0)

##### P1.5 Orchestrator prompt: explicit lock-step + evaluator dispatch
**File:** `src/harness/plugins/cgf-agents/agents/design/cgf-orchestrator.md`

Already partially rewritten in earlier work. New additions:

- Make eval dispatch step-by-step explicit (Task tool call template)
- Show example transcript:
  ```
  [writing v1.md...]
  [ITERATION_COMPLETE]

  Now dispatching evaluator...
  <Task tool: subagent_type="cgf-agents:cgf-result-evaluator">

  [evaluator returns review with RECOMMENDATION: REFINE]
  [writing reviews/v1_review.md...]
  [EVALUATE_COMPLETE]

  Recommendation is REFINE. TARGET_SECTIONS: examples, best_practices.
  REFINEMENT_HINTS: Add CancelledError propagation patterns to examples.
  Starting iteration 2 with these constraints...

  [writing v2.md...]
  [ITERATION_COMPLETE]
  ...
  ```
- Hard rule: **NEVER** write `v{N+1}.md` before `[EVALUATE_COMPLETE]` for `vN` has fired

**Effort:** prompt rewrite, no code (~30 min)

##### P1.4 Signal watchdog
**File:** `src/harness/cgf_session.py`

- During the optimization loop, after each tool call, inspect the tool
  name + arguments
- If tool is `Write` and `file_path` matches `*-v\d+\.md` (regex), set
  a `pending_iteration_signal` flag with the version number
- Within the same agent turn (same `async for message in
  agent_session.execute(...)` iteration), if `[ITERATION_COMPLETE]`
  doesn't fire, log a WARN and either:
  - `CGF_SIGNAL_STRICT=0` (default): just warn
  - `CGF_SIGNAL_STRICT=1`: hard-fail with violation

**Test:** unit test feeds a synthetic stream with a `Write` to v1.md
followed by another assistant message (no signal); asserts warning is
logged (or violation raised, depending on strict mode).

**LoC estimate:** ~40

#### P2 — Trust boundaries (post-validation)

Defer these until P0/P1 are validated by a passing smoke run. Don't
block the next smoke on them.

##### P2.6 Python-owned CHANGELOG
- Agent writes its narrative to `agent_notes.md` instead
- Python generates CHANGELOG from `task_list.checkpoints` +
  recommendations + state-machine truth at end-of-run
- Eliminates "three different iteration counts" problem

##### P2.7 Summary validation
- After agent writes `summary.json`, Python re-computes word_count,
  line_count, section_count
- Overwrites verifiable fields; flags quality scores as
  `_self_reported: true` for traceability

#### P3 — UX (track, don't ship in this pass)

| # | Item | Rationale |
|---|------|-----------|
| C | Path-filtered dashboard (single vs multi pipelines as separate panels) | Partial — already shipped via path-discriminator + dashboard query (no fresh run yet validated it) |
| D-extend | Cost-per-phase tracking | Need on each `record_phase_entry` boundary |
| E | Collapse `iterate`/`optimize` across paths | Premature — defer to Stage 3 Phase B |
| F | Load-bearing `task_list.iteration` | **Partially shipped via P0.3** (cap). Full version: drives gates + promotion |
| UX-1 | Mid-run progress indicator (no 30-min Read loops) | Symptom of agent doing internal context-gathering; needs prompt + max_turns tuning |

### Implementation order (Phase 1)

```
1. P0.1 (baseline hash)          ~40 LoC + 1 test    [protects from data loss]
2. P0.3 (iteration cap)          ~40 LoC + 1 test    [prevents runaway cost]
3. P0.2 (pair-wise enforcement)  ~60 LoC + 1 test    [fixes ordering bug]
4. P0.4 (require review on disk) ~80 LoC + 2 tests   [forces eval to actually run]
5. P1.5 (prompt lock-step)       prompt edit          [forces compliance]
6. P1.4 (signal watchdog)        ~40 LoC + 1 test    [catches drift]
```

Total: ~260 LoC production + ~6 tests. Followed by:

7. Clear `workspace/python-expert/`
8. Run `make smoke FIXTURE=python-expert`
9. Validate against pass criteria below
10. If pass, commit; document Phase-1 PASS at the top of this file;
    move on to Phase 2 (iac-team)

### Configuration matrix (new env vars after Phase 1)

| Var | Default | Purpose |
|-----|---------|---------|
| `CGF_MAX_ITERATIONS` | `3` | Max iter↔eval cycles before forced terminal |
| `CGF_BASELINE_HASH_CHECK` | `1` | Enforce original-file protection |
| `CGF_SIGNAL_STRICT` | `0` | Hard-fail on signal-watchdog violations (vs warn) |
| `CGF_NON_INTERACTIVE` | `0` | Already shipped — auto-continue checkpoints (set by `make smoke`) |
| `CGF_ITERATIONS` | `10` | DEPRECATED — see CGF_MAX_ITERATIONS |

### Pass criteria for Phase 1 smoke run

The next `make smoke FIXTURE=python-expert` MUST:

1. Complete in ≤25 min, ≤$5
2. Final `task_list.json` shows `current_phase: complete`,
   `iteration ≥ 1` matching number of `*-v*.md` files
3. `workspace/python-expert/reviews/` exists with one `v{N}_review.md`
   per iteration
4. `python-expert.md` (original) has unchanged hash from start of run
5. `summary.json["iterations"]` matches `task_list.iteration` exactly
6. CHANGELOG references at least one ACCEPT, REFINE, or REJECT
   recommendation from a real `reviews/v{N}_review.md`
7. Grafana CGF dashboard shows: Active Path = "single", Phase
   Progression shows `complete` row active (green), single-only phases
   visible, multi-only phases marked `(N/A)`
8. `harness_run_iteration` gauge reflects the final iteration count
9. No `[error]`-level log lines indicating contract violations
10. Exit code 0

If any criterion fails: file as defect, fix on sub-branch, re-run.

### Quick reference — running Phase 1 smoke

```bash
# Ensure services are up
make up

# Verify the fixture is present
ls tests/smoke/python-expert/
# Expected: README.md  SPEC.md  python-expert.md

# Run smoke
make smoke FIXTURE=python-expert
```

Expect: ~$2-4 in API calls, ~15-25 min wall time (after hardening).

---

## Phase 2 — Research + design iac-team smoke (multi-resource path)

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

### Pass criteria (Phase 2)

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

### Likely defects to surface (Phase 2)

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

## Between-session resumption

If context clears and we pick up here next session:

1. Read this file end-to-end.
2. Check `git status` and `git log --oneline -10` to see what's already shipped.
3. If Phase 1 P0/P1 items not yet done: execute the implementation order section.
4. Run `make smoke FIXTURE=python-expert` (Phase 1 validation).
5. If pass, document Phase-1 PASS at the top of this file.
6. Move to Phase 2: answer R1-R5, fill in setup.sh / teardown.sh, run iac-team smoke.
7. Same assessment loop.
8. Merge to `contextgrad-eval` only (no `main` mirror — see branch
   strategy above).

After both pass, the branch is integrated into `contextgrad-eval` for
continued iteration. The Phase A surface stays out of `main` for the
foreseeable future.
