# CGF Eval Strategy — Research & Reassessment (2026-06-13)

Durable record of the eval-strategy reassessment that produced the Phase A.5 /
re-scoped Phase B / Phase E revision in [CGF-EVAL-ROADMAP.md](./CGF-EVAL-ROADMAP.md).

**Role:** this is the **evidence record** (frozen 2026-06-13) — the *why* behind
the turn (verdict, run-data, assumption verdicts, 6 research notes). The live
**plan + status is the single source of truth in
[CGF-EVAL-ROADMAP.md](./CGF-EVAL-ROADMAP.md)** (the *what/when*); cite this doc
from there, don't plan here. **Acted on since:** Phase A.5 A1–A6 + EVAL_DESIGN v2
L1.1–L1.3 shipped and smoke-validated; A7–A15 folded into roadmap §4 (Phase B) /
§5 (C) / §6 (D) / §6A (E).

**Method:** a 13-agent research workflow — 6 web-research sweeps (Sonnet) on
2024–2026 eval methodology, 6 adversarial verdict agents (Opus) that cross-examined
the harness's load-bearing assumptions against both the literature and actual run
data, and 1 synthesizer. ~1.37M tokens. The verdict agents inspected live code
(`gating.py`, `llm_judge.py`, `aggregate.py`, `resource_types.py`, `runner.py`,
`cgf-eval-architect.md`) — citations below are `file:line` from that pass.

## Verdict summary

| Assumption (current strategy / roadmap) | Verdict |
|---|---|
| Cost-first grader priority (prefer deterministic; judge sparingly; trajectory > judge) | **REFUTED** (high) — must be discrimination-first |
| Fix tied-at-1.00 via architect "mental-simulation" instructions (roadmap §3.6 #4) | **CHALLENGED** (high) — weakest lever; empirical floor-arm audit outranks it |
| Single judge + pairwise (disagreement→tie) + keep 1–5 integer scale | **CHALLENGED** (high, P0) — single judge ok; scale fix is the omitted win; pairwise should *replace* absolute; disagreement→tie harmful |
| Bootstrap-CI win-rate gate (lower bound > 0.5) | **REFUTED** (high) — N is 3 not 10–30; promotes ~0/18; use Beta-Binomial on paired outcomes |
| Cost gate sound + cache baseline CPS (roadmap §3.6 #1) | **CHALLENGED** (high) — caching freezes a single noisy draw; multi-sample the baseline |
| Adaptive across resource types + Phase D covers continuous learning | **REFUTED** (high) — `eval_strategy` is dead metadata; learnings ledger is a distinct missing capability |

## Run-data evidence (current harness, anchored by timestamp)

**Timestamp anchoring (per owner caveat 2026-06-13):** archive runs `python-expert`,
`iac-team-v1/v2/v3`, and the archive `mobile-dev` are **Jan 27 – Feb 4 2026 — pre-Phase-A**
(~3 months stale; design-evolution context only). `iac-team-v4` (May 13) is post-Phase-A-ship
but **pre-3-stage-gate** (old simple-threshold gate — its "14/18 promote on ties" is stale gate
behavior). **Current-harness evidence = iac-team run #8 (May 18) + `workspace/mobile-dev` (May 26).**

**Measured grader mix (generated suites, not the stale archive):**
- `workspace/iac-team/eval/eval-suite.yaml` (May 18 = run #8): 54 scenarios → **98 `contains`, 8 trajectory, 4 composite, ZERO `llm_judge`.** Quality signal was entirely keyword-substring matching → both arms emit the keyword → 11/17 tied at 1.00/1.00.
- `workspace/mobile-dev/eval/eval-suite.yaml` (May 26, current `main`, different resource type): 66 scenarios → 85 `contains`, 22 composite, 21 trajectory (all `constraint` kind), 3 `llm_judge` (~2%).

**mobile-dev run (May 26, current `main`) — freshest data point, non-iac type:**
- Reached COMPLETE; 22 resources: 15 optimized, **5 unwinnable (23%)**, 1 failed (GENERATE), 1 stuck at v5 `needs_refinement`.
- **`win_rate ≡ 0.00` on every one of 32 eval-results** — even where candidate pass-rate beat baseline (mobile-unit-testing 0.67→1.00; mobile-accessibility 0.00→0.33). The per-scenario win-rate metric is degenerate because `no_decision` eats head-to-head comparisons.
- `no_decision_rate` pervasive (0.33–1.00); 5 unwinnable resources all 0.00/0.00 with `no_decision=1.00`.
- `mobile-tester` iterated v1→v3→v5, every round `reject_floor` — optimizer drove it *below* the bare-model floor 3×.

---


## Synthesis memo

All grounding confirmed. The architect prompt (`cgf-eval-architect.md`) mandates a uniform per-type level mix, forbids reading resource files (line 7), defaults to `contains` everywhere (line 154), and the Phase B win-list floor is `len(wins) < 10` (roadmap line 746) — which at 3 scenarios/resource is structurally unreachable. I have everything needed for a decisive memo.

---

# CGF Eval Strategy — Roadmap-Revision Proposal (HISTORICAL — superseded by the roadmap)

> ⚠ **Acted on; do not plan from this section.** It drove the 2026-06-13 turn —
> A1–A6 shipped as Phase A.5 and EVAL_DESIGN v2 (L1.1–L1.3); A7–A15 are folded
> into the live plan in [CGF-EVAL-ROADMAP.md](./CGF-EVAL-ROADMAP.md) §4 (Phase B)
> / §5 (C) / §6 (D) / §6A (E). Kept below as the frozen record of how the
> research became the plan — the action→roadmap mapping (§4) and owner
> open-questions (§6) remain useful context for the Phase B/C/D/E work.

*Lead eval architect → owner. Grounding: 5 research notes, 6 assumption verdicts (1 refuted-grader-priority, 1 refuted-adaptivity, 1 refuted-bootstrap, 3 challenged), Runs #7/#8 + archive v4, current code (`gating.py`, `llm_judge.py`, `resource_types.py`, `runner.py`, `cgf-eval-architect.md`).*

---

## 1. Executive Summary

- **OVERTURNED — "cost-first grader priority is sound" is refuted (high confidence).** Cost-first optimizes cheapness, but the eval's job is *discrimination*. Run #8: 11/17 final resources tied at 1.00/1.00, win_rate≈0 across all 18, and `llm_judge` fired on only ~5% of scenarios. The cost gate is the *only* stage discriminating — backwards. Cheap `contains` graders both arms satisfy are textbook low-discrimination (low-`a`) items the IRT literature says to *prune*, not *prefer* [scenario-discrimination; arXiv 2605.30504].
- **OVERTURNED — "10–30 scenarios per resource" is false; it's 3.** Every `eval_harness.run` line shows `scenarios=3, trials_per_scenario=1`; the gate decides *per resource*. A 1000-resample bootstrap percentile CI over N=3 binary outcomes (4 possible point estimates) is undefined-in-practice [small-n; arXiv 2503.01747]. **The planned Phase B gate would reject ~26/28 of the candidates Phase A promoted** and is unshippable as specified.
- **OVERTURNED — roadmap fix #4 (architect "mental-simulation" instructions) is the *weakest* available fix, not the prerequisite.** SELF-[IN]CORRECT shows LLM discrimination is weaker than generation; instructing a metadata-blind sonnet agent to *imagine* v0-vs-regressed asks the weak faculty to self-police with no ground truth. The empirically-validated fix — an **empirical discrimination audit reusing the floor arm already wired** (`runner.py:486`, `ScenarioResult.floor`) — is comparable effort and far higher leverage.
- **The single highest-leverage code fix the roadmap omits: the 1–5 integer judge scale.** `llm_judge.py` uses hard-argmax integer parsing + `(score-1)/4`. Frontier judges compress this to 2–3 effective points; a 30-LoC switch to G-Eval probability-weighted scoring recovers continuous signal with zero rubric change [llm-judge; arXiv 2505.19334].
- **`eval_strategy` routing is dead metadata.** `resource_types.py` tags every type (`content_only`/`executable`/...) but has **zero read sites**. This is a confirmed structural bug, not a preference — it caused `iac-generator`'s unwinnable 0/0 (trajectory graders on a system-prompt file that never executes tools).
- **A continuous-learnings ledger is a genuine missing capability, NOT covered by Phase D.** Phase D is judge *calibration* (does the score earn trust?); the ledger is *what edits work for which resource type?* Orthogonal artifacts. The optimizer starts run 1 as naive as run 8 — nothing survives `cgf-clean`.

---

## 2. What's Working vs What's Flat

**Working (keep, grounded in run data):**
- **I15 verdict-branched cost-aware feedback** — recovery 1/8 → 9/10, ITERATE r2 57m → 16.5m. The architectural instinct is right; the gap (per §3.6 from research) is that feedback is a *directive*, not a per-trace *diagnosis* [TextGrad/GEPA; arXiv 2507.19457].
- **Floor gate** — catches collapsed prompts (3 floor-rejections in run #7).
- **3-stage gate mechanics + dominance (no scalarization)** — correct multi-objective form [ParetoPrompt, ICLR 2025]. Real regressions *are* caught without any CI gate (crossplane 66.7→0, github-actions 33→0 blocked).
- **Coherence validator** (0.93–0.96), **judge isolation** (judge≠design model — already partially honoring the cross-family self-preference rule [Panickssery, arXiv 2410.21819]).

**Flat / ineffective (the core problem cluster):**
- **Quality/win-rate signal ≈ 0** — ties dominate. This is a *scenario-discrimination + grader-resolution* artifact, not a statistics problem. No aggregation recovers signal absent from the items [scenario-discrimination].
- **`llm_judge` underused (~5%)** and coarse-scaled (1–5 integer, hard-argmax) — the one signal that could separate arms is both barely deployed *and* resolution-crippled.
- **Trajectory graders are presence-only** (`ToolCalledAssertion` checks `len ≥ min_count`; `with_arg` appears once with zero worked examples) — reward-hackable `tool_called==True` [BFCL AST-match; Reward-Hacking-Bench arXiv 2605.02964].
- **Cost gate vs single-draw baseline** — helm-charts CPS swung $0.15→$0.32→$0.19 (2.1×) for the *same v0*; τ=0.10 tests against ~110% noise, rejected 3× at quality 0.97–1.00.

---

## 3. Reprioritization of Eval Types + Weighting

**Yes — the cost-first grader priority must change to discrimination-first.** The principle inversion: *the criterion for which grader a scenario gets is the resource type and the grader's separating power, never its cheapness.*

**Recommended grader mix (a cascade, not a flat dispatch):**
1. **Deterministic checks = the cheap PASS GATE**, not the discriminator. Schema validity, structural sanity, keyword presence must pass to proceed — exactly the FrugalGPT/Trust-or-Escalate cascade pattern [arXiv 2407.18370]. The current code has *no* cascade (`build_grader` is flat type dispatch).
2. **LLM-judge = the discriminator on every non-trivial scenario** that both arms pass. Lift judge coverage far above ~5%; stop framing it as an anti-pattern. Adopt **HealthBench/BiGGen instance-specific partial-credit rubrics** with **≥1 criterion the baseline is expected to fail** — so two passing arms still separate [arXiv 2505.08775, 2406.05761].
3. **Pairwise = the GATE's per-scenario decision** (not an absolute add-on). Chatbot Arena's >80% human agreement makes pairwise the canonical model-selection tool. The gate already consumes `win_rate`; pairwise should *produce* the per-scenario win, with continuous absolute scoring retained only for monitoring/feedback.
4. **Trajectory = only for executable/server resources**, and when used, must check **argument correctness (BFCL AST) + goal-progress (AgentPRM)** — never bare presence.

**Gate ORDERING (the structural correction):** today rigor is on the wrong axis — cost is a *hard* gate on a noisy single-draw baseline while quality is *soft* (`≥` equality promotes, `gating.py:203`). Correct ordering: **(1) floor → (2) discrimination/quality on a de-noised, fine-grained signal → (3) cost on a multi-sample baseline.** Cost stays a hard gate (run #8 proves its value: caught gitops-argocd +115% CPS at zero quality gain) **but only after its baseline input is de-noised** — multi-sample the floor arm (n≥5, amortized since it runs once per resource), gate on a *ratio* statistic, not raw-mean-vs-raw-mean.

Where each type belongs in the pipeline: **EVAL_DESIGN** picks graders by `eval_strategy`; **EXECUTION_EVAL** runs the cascade + discrimination audit; **the gate** consumes pairwise per-scenario wins + de-noised cost.

---

## 4. Ranked Action Plan (mapped to roadmap)

| # | Action | Roadmap mapping | Verdict | Why (one line) |
|---|--------|-----------------|---------|----------------|
| **A1** | **Wire `eval_strategy` → grader routing** (content_only/agent-defs → llm_judge rubrics; executable/server → trajectory+outcome) | **#3 REORDER to #1** | refuted-adaptivity | Kills the `iac-generator` unwinnable *class* by construction; the type system exists, routing is dead. ~60 LoC. |
| **A2** | **Empirical discrimination audit** — run v0/floor per scenario, drop where both pass, target ≥40% flip | **NEW; OUTRANKS #4** | challenged (#4) | Reuses floor data already computed & discarded; grounds discrimination in *observed* behavior, not imagined. ~80–120 LoC. |
| **A3** | **G-Eval probability-weighted judge scoring** (or 7-pt anchored fallback) | **NEW (Phase B P0)** | challenged (single-judge) | Highest-leverage code fix the plan omits; recovers continuous signal, zero rubric change. ~30 LoC. |
| **A4** | **Multi-sample baseline + ratio cost gate**; absolute τ floor as cheap secondary guard | **#1 DROP-AS-PRIMARY / #2 KEEP-AS-GUARD** | challenged (cost-gate) | Caching freezes one draw of a 110%-variance distribution — wrong fix. Estimate from samples instead. |
| **A5** | **Discrimination-first architect rewrite** — mandate ≥1 fail-prone criterion/scenario; invert "use contains aggressively"/"latency over coverage" (lines 154, 387) | **#4 REFRAME** | refuted-grader / challenged | Keep mental-simulation only as a *supplement* once the agent has real material (A6). |
| **A6** | **Give architect a capability model** — lift "no reading resource files" (line 7) for capability-diffing v0↔v1, or feed v0 failure transcripts | **NEW** | challenged (#4) | Root cause #1: architect can't write discriminating scenarios blind to what v1 changed. |
| **A7** | **Beta-Binomial posterior gate** (Jeffreys, 5th pct of Beta(k+0.5, N−k+0.5) > 0.5) over **paired discordant** outcomes; abstain below decisive-N floor | **Phase B bootstrap REPLACE** | refuted-bootstrap | Bootstrap is undefined at N=3; Beta posterior is exact at any N, ~10 LoC. |
| **A8** | **Raise `trials_per_scenario`→3 + scenarios/resource well above 3** | **#10 REORDER up** | refuted-bootstrap | No statistical gate has power at decisive N≈2; this is the precondition for A7. |
| **A9** | **Treat `no_decision`/tie as 0.5 half-win**, not discard | **NEW (Phase B)** | challenged (single-judge) | no_decision_rate hits 0.667; discarding (current `aggregate`) collapses effective N. |
| **A10** | **Argument-correctness + goal-progress on trajectory graders** | **Phase B extend** | refuted-grader | Presence-only is reward-hackable; required wherever trajectory is used. |
| **A11** | **Learnings Ledger** — append-only, workspace-external, 5-layer | **NEW WORKSTREAM "Phase E"** | refuted-adaptivity | Distinct from Phase D calibration; converts isolated episodes into compound learning. |
| **A12** | Single judge now, ensemble deferred to Phase D when κ<0.8 | **Phase D KEEP** | challenged (validated half) | Correct cost-staging; position bias ≤0.04 on frontier judges makes ensemble premature. |
| **A13** | GENERATE word-count guidance; auto-skip after 2 cost rejections; concurrency 4→6 | **#5, #6, #7 KEEP** | — | Cheap, independently valuable. |
| **A14** | Per-type τ profile; pre-flight dry-run | **#9, #8 KEEP-DEFERRED** | challenged | Gold-plating until A2/A4 land and I16 has data. |
| **A15** | IRT a-parameter pruning, generative hard-negative mining | **DROP to Phase D** | challenged (#4) | Needs multi-model/multi-run response matrix the project lacks (trials=1, 2 arms). |

**Explicit plan changes:**
- **Empirical discrimination audit (A2) OUTRANKS the architect-prompt fix (#4).** The roadmap's Decision A picked "(a) architect prompt" as *the* prerequisite. Overrule: ship the empirical audit first — it's comparable effort, reuses existing floor data, and the prompt fix is the literature's *weakest* lever.
- **Pairwise REPLACES absolute scoring as the gate's per-scenario decision** (not "added alongside, absolute kept" as Phase B currently frames it). Absolute (now continuous) survives only for feedback/monitoring.
- **Bootstrap CI is DROPPED in favor of Beta-Binomial.** The threshold *form* (lower bound > 0.5) is right; the distributional method breaks at this N. The `len(wins) < 10` floor (roadmap:746) is structurally unreachable at 3 scenarios/resource — A8 is mandatory.
- **The learnings ledger becomes a new workstream**, not a Phase-D sub-item.

**Sequencing:** Ship **A1+A2+A3+A4 as "Phase A.5"** → **smoke #9** (confirm tied-at-1.00 fraction drops, win_rate non-degenerate) → **then** open Phase B (A7+A9+pairwise) on a suite that finally has something to bite into.

---

## 5. New Capabilities We're Missing

**(a) Empirical scenario-discrimination validation.** *Mechanism:* at EVAL_DESIGN/first-eval, run every candidate scenario against the synthetic bare-model floor (already produced by `_baseline_floor.build_floor_resource`, run per-scenario at `runner.py:486`); compute per-scenario D = (candidate passes ∧ floor fails); auto-drop/regenerate scenarios where D≤0; target ≥40% retained flip rate [scenario-discrimination]. *Plug-in:* surfaces `ScenarioResult.floor` per-scenario flip (currently collapsed to one `floor_pass_rate` in `gating.py`) — converts the floor arm from a one-shot gate input into a scenario-quality filter. Slots between **EVAL_DESIGN and EXECUTION_EVAL** as a gating sub-step.

**(b) Adaptivity across resource types.** *Mechanism:* resolve each resource's `eval_strategy` from `ResourceTypeRegistry` and pass an allowed/forbidden grader-type set into the architect as a hard constraint; replace the hardcoded level-mix table (`cgf-eval-architect.md:55`) with this strategy-derived mapping. AdaRubric's task-adaptive rubrics hit r=0.79/α=0.83 vs generic fixed rubrics precisely because uniformity destroys signal [arXiv 2603.21362]. *Plug-in:* **EVAL_DESIGN** grader selection; the `eval_profile.yaml` the roadmap names (but never built) becomes its config surface.

**(c) Continuous-learnings ledger.** *Mechanism:* append-only, workspace-external (survives `cgf-clean`), 5 layers — (i) run records `(resource_id, type, sector, edit_type, grader_deltas, cost_delta, verdict)`; (ii) ExpeL edit-pattern library with N-observation CIs; (iii) CLIN causal map edit→score-shift by type; (iv) Reflexion anti-patterns; (v) meta-rubric index (the *only* layer consuming Phase D's κ output) [adaptive-eval; arXiv 2506.06698]. *Plug-in:* **WRITE** at end of `execution_eval.py` (verdict + per-scenario deltas already exist there); **READ** via semantic-similarity retrieval at start of **RESEARCH/ITERATE**, injecting top-K patterns + anti-patterns for the resource type + domain into the optimizer context.

---

## 6. Open Questions / Risks for the Owner

1. **Cost of lifting `llm_judge` coverage from ~5% to ~every discrimination-tier scenario** — judge calls dominate eval cost. Cap the increase by the cascade (judge only on scenarios both arms pass)? Or accept the bill on the iac-team fixture as the validation cost?
2. **"No reading resource files" (A6)** was deliberate isolation to prevent the architect from over-fitting scenarios to the implementation. Lifting it for capability-diffing reintroduces that risk. Acceptable if scoped strictly to v0↔v1 *diff* (not full-file read), or feed transcripts only?
3. **scenarios/resource and trials (A8)** — raising both is the precondition for any statistical gate but multiplies cost linearly. What's the target decisive-N (research floor ≈10–15) vs the per-run budget ceiling?
4. **Learnings-ledger ownership and staleness** — who curates anti-patterns; how do we prevent the ledger from ossifying around the iac-team fixture's idiosyncrasies before we have cross-domain runs?
5. **Phase ordering risk:** if smoke #9 (post A1–A4) *still* shows flat win_rate, the problem is deeper than grader resolution (genuine resource-quality ceiling) — do we then invest in harder scenario generation (A15) before Phase B, accepting further delay?
6. **Pairwise disagreement handling:** the 2026 data says order-disagreement is <5% on Opus/Sonnet — do we even run both orderings (2× judge cost) or only swap on borderline absolute margins, breaking ties on the continuous score rather than the dangerous silent→tie?

---

## Assumption verdicts (full)

### ASSUMPTION: Grader priority should be COST-FIRST: prefer deterministic (exact/contains/regex/code) as the cheapest tier, use llm_judge sparingly, and rank trajectory > llm_judge in the default ordering.
VERDICT: REFUTED | conf: high | priority: P1
RATIONALE: Cost-first grader ordering optimizes the wrong objective for a two-arm promotion gate and is the proximate cause of the system's dominant failure mode. The point of the eval is DISCRIMINATION (does candidate beat baseline?), not cheapness. The run data shows the cost-first default produces a flat quality signal: archive iac-team-v4 used llm_judge on 3/55 scenarios (~5%) and got win_rate=0.0 across all 18 resources (14/18 promoted purely on ties); run #8 had 11/17 final resources tied at 1.00/1.00 and 4 at 0.67/0.67 — both arms pass everything. I confirmed the mechanism in code: aggregate.py:110 awards `candidate_win` only when `candidate.pass_rate > baseline.pass_rate + epsilon`, and gating.py:204 promotes on `candidate >= incumbent + epsilon` with epsilon=0 (equality promotes). So when cheap `contains: keyword` graders make both arms pass, every scenario is a tie, the quality stage is a no-op, and the cost stage (gating.py:216-227) becomes the ONLY discriminator — exactly what run #8 reports as 'backwards.' The IRT/scenario-discrimination research names this directly: a `contains` grader both arms satisfy is a low-discrimination (low-`a`) item with zero separating power; the BHI Capability-Discrimination axis and the discrimination index (D<0.20 → prune) formalize that such items should be removed, not preferred. The adaptive-eval research (FrugalGPT, Trust-or-Escalate arXiv 2407.18370, RocketEval ICLR 2025) does endorse cheap-first CASCADES — but a cascade uses cheap checks as GATES (cheap check must pass to proceed) and reserves the judge to DISCRIMINATE the residual; it never uses cheapness as the criterion for which scenarios get a judge at all. The current code has no cascade (build_grader is a flat type dispatch; the only judge delegation is ConstraintAssertion). Two sub-claims are also refuted: (a) Trajectory > llm_judge as a blanket default is wrong because the harness's trajectory graders are presence-only — ToolCalledAssertion (trajectory.py:74) checks `len(candidates) >= min_count`; `_args_match`/`with_arg` exists but the eval-architect template mentions it once with zero worked examples, so argument-correctness is virtually never emitted. The agent-trajectory research (BFCL AST-match, AgentPRM, ToolPRMBench, Reward-Hacking-Benchmark arXiv 2605.02964) shows `tool_called==True` is the weakest, most reward-hackable signal — a candidate calling the right tool with wrong args scores as passing. (b) Trajectory graders MUST be routed away from content-only agent definitions. This is a confirmed structural bug, not a preference: resource_types.py tags AGENT=`content_and_execution`, SKILL/COMMAND/HOOK=`content_only`, MCP_TOOL=`executable`, but `grep` shows `eval_strategy` has ZERO read sites in src/ — the routing metadata is dead. Meanwhile the architect template (cgf-eval-architect.md:55) hard-mandates '1 trajectory + 1 e2e + 1 unit' for every agent. Result: run #8's `agents/iac-generator` got a trajectory grader asserting `tool_called: Write` on a file that loads as a SYSTEM PROMPT and never executes tools → structurally unwinnable 0/0 on both arms. The trajectory-eval research calls this exact case the 'unwinnable scenario' and prescribes routing on resource type (content-only → LLM-judge rubric; execution surface → trajectory+outcome).
RECOMMENDATION: Replace cost-first with a discrimination-first cascade and wire the dead routing metadata. Concretely: (1) Make `eval_strategy` load-bearing. In eval_design.py / the architect contract, branch grader selection on ResourceTypeConfig.eval_strategy (it already exists in resource_types.py with the right values). Route `content_only` (skill/command/hook/plugin) and `content_and_execution` AGENT-definition files to LLM-judge rubric graders + deterministic content checks; route ONLY `executable`/`server` and live agent-instance resources to trajectory+outcome graders. This kills the iac-generator-class unwinnable 0/0 by construction. (2) Invert the architect's grader guidance from cost-first to discrimination-first: every scenario must include at least one grader that the v0/baseline is EXPECTED to fail. Stop framing llm_judge as an anti-pattern (cgf-eval-architect.md:368); instead require a judge or a fail-prone rubric criterion on every medium/hard scenario. Adopt HealthBench/BiGGen-style instance-specific partial-credit rubrics (the rubric itself must contain a criterion the baseline misses) so two passing arms still separate. (3) Build the cascade the research endorses: cheap deterministic checks as the PASS GATE (structural sanity, schema, keyword presence), then the judge runs to DISCRIMINATE every scenario that both arms pass — do not skip the judge merely because a cheap check exists. Lift llm_judge usage far above the historical ~5%; target judge coverage on every non-trivial discrimination-tier scenario. (4) Give the architect a capability model: drop the hard 'do not read generated resource files' rule for the discrimination step and feed it baseline/v0 failure transcripts (run the baseline on a small probe set first), then require a per-scenario discrimination self-check ('what would v0 do here, and why would it fail?'). Add a pre-commit discrimination audit: run v0 against the suite, discard scenarios where v0 passes, target >=40% expected v0->v1 flip rate. (5) When trajectory graders ARE used (executable resources), require argument-correctness — emit `with_arg` and add BFCL-style AST/argument checks plus a goal-progress check, so the signal isn't reward-hackable `tool_called==True`. Note: do NOT rank trajectory above llm_judge in any default; rank by discriminating power for the resource type, which for content-only artifacts is judge/rubric, not trajectory.

### ASSUMPTION: That the tied-at-1.00 / win_rate~0 dominant failure mode is best addressed by adding scenario-discrimination INSTRUCTIONS to the cgf-eval-architect prompt (telling it to mentally simulate v0 vs a regressed version and confirm scenarios separate them) — roadmap fix #4, "the outstanding Phase B prerequisite."
VERDICT: CHALLENGED | conf: high | priority: P1
RATIONALE: The diagnosis is right; the prescribed fix is the weakest of the available mechanisms and is contradicted by the research on its own terms. Prompt-only "mental simulation" of v0-vs-regressed is a self-discrimination task, and the scenario-discrimination corpus is explicit that this is exactly where LLMs are weak: SELF-[IN]CORRECT (AAAI) shows "LLMs' ability to discriminate responses is weaker than their ability to generate, so a naive LLM discriminator will accept non-discriminating scenarios." Telling a sonnet agent capped at 10 turns (3-turn target) to imagine outcomes is asking the weak faculty to police itself, with no ground-truth check.

Two structural root causes in the actual architect prompt make instructions insufficient regardless of wording. (1) The agent is FORBIDDEN from reading the resource files it is writing evals for (cgf-eval-architect.md lines 6-7, 24: "Designs scenarios from resource metadata WITHOUT reading individual generated resource files"; it works only from resource-plan.yaml names/purposes). It therefore has no model of what v1 changed relative to v0 — the scenario-discrimination note names this as root cause #1: "The architect has no model of baseline capability... cannot generate discriminating scenarios without knowing what the baseline specifically fails at." (2) The prompt actively optimizes AGAINST discrimination: line 371 "Use contains aggressively. A scenario whose grader is contains: 'kubectl' is fine"; line 387 "You are an optimizer for completion latency, not coverage depth." The run-#8 suite reflects this exactly — only 4 llm_judge graders vs 66 contains + 20 trajectory + 16 composite across 54 scenarios.

The run data shows the failure is a grader-resolution problem, not (only) a scenario-topic problem. execution-eval-round-1.json: 16 of 18 resources have win_rate=0.0 with baseline_pass_rate == candidate_pass_rate. Concrete instance (terraform-modules eval-results.json): scenario easy-terraform-s3-module-01 grades contains: "versioning"; the bare-model baseline and the candidate BOTH emit a full S3 module containing "versioning" and both score 1.0. No prompt instruction to the architect about "separating v0 from v1" fixes a binary contains-substring grader that any competent model trivially satisfies — the llm-judge-reliability note's point that coarse/binary scoring collapses resolution applies at the grader level, and the scenario-discrimination note's HealthBench/BiGGen finding (a criterion both arms always satisfy is non-discriminating) is the direct remedy.

Decisively, the empirically-validated mechanism is nearly free in this codebase, which inverts the roadmap's effort ranking. eval_harness/models.py:182 already defines ScenarioResult.floor (per-scenario bare-model arm), and runner.py:486-526 already RUNS the floor arm per-scenario at first promotion. The exact "discrimination audit" the research prescribes — run each scenario against a deliberately degraded variant (the bare-model floor already exists), compute per-scenario candidate-passes-AND-floor-fails flip rate, drop/flag non-separating scenarios — reuses data the pipeline already produces and currently discards (it collapses everything into one floor_pass_rate used only for gating). The roadmap costs fix #4 at "half-to-full day" and treats the empirical step as out of scope; in reality the empirical filter is comparable effort and far higher leverage because it grounds discrimination in observed behavior instead of imagined behavior.
RECOMMENDATION: Do not ship architect instructions as the primary fix. Implement an empirical scenario-discrimination GATE that reuses the floor arm already wired in eval_harness, and pair it with grader-resolution and architect-context changes. Ranked by leverage/effort:

(1) HIGHEST LEVERAGE, LOW-MEDIUM EFFORT — Empirical discrimination filter (build on existing floor arm). At EVAL_DESIGN/first-eval, run every candidate scenario against the synthetic bare-model floor (already produced by _baseline_floor.build_floor_resource and run per-scenario in runner.run_scenario). Compute per-scenario discrimination D = (candidate passes) AND (floor fails). DROP or auto-regenerate any scenario where floor and candidate both pass (D<=0) — these are provably non-separating. Target >=40% of retained scenarios flipping floor->candidate (the scenario-discrimination note's threshold). ScenarioResult.floor (models.py:182) already holds the data; you are surfacing per-scenario flip, not adding eval runs at first promotion. This converts the existing floor arm from a one-shot gate input into a scenario-quality filter. ~80-120 LoC in execution_eval + aggregate, mostly plumbing data that is currently aggregated away.

(2) HIGH LEVERAGE, MEDIUM EFFORT — Fix grader resolution at the source. The dominant artifact is binary contains-substring graders any model satisfies. (a) Mandate that every scenario carry >=1 grader criterion a bare/unoptimized agent would likely miss (HealthBench/BiGGen partial-credit pattern). (b) Replace the architect's "use contains aggressively / latency over coverage" directives (lines 371,387) with the opposite default for skill/agent resources: llm_judge or composite with a fail-prone criterion. (c) Combine with roadmap fix #3 (grader-routing by resource type) so content-only agents (iac-generator, currently 0/0 unwinnable) get llm_judge rubrics not trajectory tool_called assertions.

(3) MEDIUM LEVERAGE, MEDIUM EFFORT — Give the architect a capability model. Lift the "do not read resource files" prohibition for the specific purpose of capability-diffing v0 vs v1 (or feed it a short v0-failure-mode probe / prior-run transcripts). This is the scenario-discrimination note's root-cause-#1 fix: condition scenario generation on the actual v0->v1 gap, not on resource-plan metadata. The mental-simulation instruction from fix #4 only becomes useful once the agent has real material to reason over — keep it as a SUPPLEMENT here, never the whole fix.

(4) LOWEST PRIORITY for now — IRT/discrimination-index pruning (a<0.3) and generative hard-negative mining are correct long-horizon directions but require a multi-model/multi-run response matrix the project does not yet have (trials_per_scenario=1, two arms). Defer to Phase D calibration; they are gold-plating against current data volume.

Sequencing: ship (1)+(2) together as the "Phase A.5" signal-quality branch BEFORE Phase B, run smoke #9 to confirm the tied-at-1.00 fraction drops and win_rate becomes non-degenerate, THEN open Phase B — a bootstrap/Beta-Binomial CI on a suite that has been empirically filtered for separation has something to bite into; on the current suite it does not.

### ASSUMPTION: Phase B should use a SINGLE judge with pairwise position-balancing (A-B + B-A; disagreement -> tie), keep the current 1-5 ABSOLUTE INTEGER scale for the per-scenario llm_judge grader, and defer judge ensembles to Phase D.
VERDICT: CHALLENGED | conf: high | priority: P0
RATIONALE: The assumption bundles four sub-decisions; the research and run data split them sharply, and the bundle as written is internally contradictory.

(1) SINGLE JUDGE — VALIDATED. At the harness's N (3 scenarios/resource, ~1/3 held out, trials_per_scenario=1 smoke / 3 prod), an ensemble is premature and the 2026 measurement data says position bias on current frontier judges is already negligible (≤0.04; swapping helped Gemini +4.6pp but HURT GPT-4o -2.4pp). Ensemble's 3-5x cost buys little when the dominant problem is not judge variance but a flat input signal (Run #8: 11/17 tied at 1.00/1.00). Deferring ensemble to Phase-D, calibration-gated, per-resource-type when kappa<0.8, is the correct cost-staging. So "single judge now, ensemble later" is right.

(2) KEEP 1-5 ABSOLUTE INTEGER — REFUTED as a Phase-B no-op, and it is the single highest-leverage fix the plan omits. The llm-judge-reliability corpus is unambiguous: a 5-point integer scale with frontier judges compresses to effective 2-3 point resolution, mass avoids the 1/5 extremes, and retry-once->tie collapses it to a 3-class bad/uncertain/good signal — exactly the tie inflation we observe. arXiv 2505.19334 showed expanding 2-point to 11-point made POINTWISE statistically indistinguishable from listwise ranking on 31/40 combos: scale granularity, not scoring mode, is the primary discriminating lever. The code confirms the weakness is live: llm_judge.py uses one holistic rubric, max_tokens=8, hard-argmax integer parse (no G-Eval probability weighting), and the schema has no per-criterion sub-scores. Keeping the coarse scale guarantees Phase B's statistical gate tightens an already-flat signal — the roadmap itself concedes this at lines 317-319.

(3) PAIRWISE vs ABSOLUTE for DISCRIMINATION — pairwise IS the right primary mode for a binary promote/reject GATE (Chatbot Arena >80% human agreement; the corpus calls pairwise the canonical model-selection tool), so adding it is correct. BUT the assumption frames it as 'pairwise added alongside, absolute kept as the per-scenario grader.' That is backwards relative to how the gate actually works: gating.py compares candidate_pass_rate >= incumbent_pass_rate (absolute mean per-arm pass-rate), and Phase B's planned bootstrap-CI runs on win_rate (per-scenario candidate-win fraction). The per-scenario WIN determination is what feeds the gate — so pairwise should REPLACE absolute scoring as the gate's per-scenario decision mechanism, with absolute (fine-grained, probability-weighted) retained only for longitudinal monitoring/feedback, not as the promotion signal. The corpus explicitly endorses this two-stage split (pointwise for debugging/tracking, pairwise for the promote decision) as emerging best practice. The assumption's 'keep absolute as primary, bolt pairwise on' inverts that.

(4) DISAGREEMENT -> TIE — CHALLENGED, and this is the most dangerous part given our data. The handling discards signal and manufactures ties precisely where we already drown in them. Mechanics: aggregate.py treats a per-scenario tie as a non-win, and a tie reduces decisive N feeding the bootstrap; roadmap line 745 strips ties from the resampled win-list, so every order-disagreement tie shrinks the effective sample. At our N, small-n-statistics is decisive: with ~2 held-out scenarios per resource, even one extra forced tie can drop decisive N below the plan's own len(wins)>=10 floor (roadmap:746), auto-failing promotion. The 2026 bias data says order disagreement on frontier judges is RARE (≤0.04) AND mixed-sign — so 'A-B + B-A, both must agree' spends 2x judge cost to detect a near-zero-incidence bias, then converts the rare hit into the exact failure mode (a tie) that is already our dominant pathology. Better handling exists and is cheap: on disagreement, fall back to the (now fine-grained, probability-weighted) absolute margin to break the tie, or run a third tie-break sample (multi-sampling captures ~60% of a 3-sample variance reduction per the corpus) — never silently emit a tie that the bootstrap then treats as evidence against promotion.

NET: single judge yes; defer ensemble yes; ADD pairwise yes — but pairwise must be the gate's per-scenario decision, the 1-5 integer scale must be fixed (the corpus's #1 priority, which the assumption explicitly preserves), and disagreement must NOT silently map to tie. The assumption is right on staffing/cost and wrong on the two levers that actually move discrimination.
RECOMMENDATION: Re-scope Phase B's judge work to four concrete changes, in priority order:

1. (P0, ~30 LoC, zero rubric change) Fix the score scale BEFORE/with pairwise. Replace hard-argmax integer parsing in graders/llm_judge.py with G-Eval-style probability-weighted scoring: request logprobs over the score tokens and take the expectation, yielding a continuous [0,1] score from the same 1-5-trained judge (G-Eval, arXiv 2303.16634; corpus §5). If logprobs are unavailable on the judge model, expand the rubric to a 7-point scale with one-sentence anchors per level (arXiv 2505.19334). This is the corpus's #1 fix and the assumption's biggest miss.

2. (P0) Make pairwise the GATE's per-scenario decision, not an absolute add-on. In the new pairwise module, the per-scenario winner feeds win_rate -> bootstrap-CI gate. Keep absolute (now continuous) scoring only for feedback/monitoring. This matches how gating.py + the Phase B win_rate gate actually consume the signal.

3. (P1) Change disagreement handling: on A-B vs B-A disagreement, break the tie using the continuous absolute-score margin (promote if candidate margin exceeds a small delta, else tie), OR draw one extra tie-break sample. Do NOT silently emit tie. Log disagreement rate as a metric; if it is empirically <5% (as the 2026 data predicts for Opus/Sonnet), consider dropping the second ordering entirely to save the 2x judge cost and only swap on borderline absolute margins.

4. (P1, gating.py) Replace the percentile bootstrap with a Beta-Binomial posterior (Jeffreys prior Beta(0.5,0.5)); promote if 5th percentile of Beta(k+0.5, N-k+0.5) > 0.5. The bootstrap is unreliable at decisive N<20 (arXiv 2503.01747, ICML 2025 spotlight); the Beta posterior is exact at any N and is the analytically-correct answer to the same question. Treat no_decision/order-tie scenarios as 0.5 (half-win) rather than discarding, to preserve N (small-n-statistics §IMPLICATIONS.2).

CRITICAL DEPENDENCY: none of this lands value until scenario discrimination (roadmap §3.2) is fixed — a bootstrap CI on 11/17 resources where both arms pass 100% has nothing to bite into (roadmap:319). Sequence §3.2 architect-prompt work + the scale fix (1) FIRST, then pairwise + statistical gate. Single judge / ensemble-deferred-to-D is fine as-is.

### ASSUMPTION: The promotion gate should use a bootstrap CI on win rate (1000 resamples, 95% CI, promote iff lower bound > 0.5) over the ~10-30 scenarios per resource.
VERDICT: REFUTED | conf: high | priority: P1
RATIONALE: Three independent grounds refute this as the Phase B gate, in priority order:

(1) THE SAMPLE-SIZE PREMISE IS FALSE. The assumption says "~10-30 scenarios per resource." The actual data says 3. Every one of the 18 `eval_harness.run start` lines in logs/smoke/run8.log shows `scenarios=3, trials_per_scenario=1`, and the persisted aggregates (workspace/iac-team/eval/execution-eval-round-{1,2}.json) confirm `scenarios-per-resource = {3}` uniformly. The "10-30" figure is the suite total (54 scenarios / 18 resources = 3 each), not the per-resource gate population — and the gate decides per resource (one EvalResults per resource in _eval_single_resource, gating.py operates on a single resource's pass rates). With no_decision_rate of 0.333-0.667 common in the data, the decisive N for win-rate is frequently 2 or even 1. A 1000-resample bootstrap percentile CI over N=3 binary outcomes has only 4 distinct possible point estimates (0, 1/3, 2/3, 1) and a wildly unstable tail; arXiv 2503.01747 (ICML 2025 Spotlight) states asymptotic/resampling CIs "dramatically underestimate uncertainty" below a few hundred datapoints, and the Wilson/Bayesian literature shows percentile bootstrap under-covers at N<20. At N=3 it is not approximately wrong, it is undefined-in-practice.

(2) IT WOULD PROMOTE ALMOST NOTHING — but for the wrong reason. The win-rate signal is already flat at zero. Round 1: win_rate=0.0 for 16/18 resources (2 at 0.333). Round 2: win_rate=0.0 for ALL 10. Across 28 resource-evals over both rounds, exactly 2 had ANY candidate_win. A "lower-bound > 0.5" rule cannot be cleared even by the best observed resource (1 win of 3 = point estimate 0.333, CI lower bound near 0). So the gate would reject ~26 of 28 candidates that Phase A promoted. Run #8's 16/18 promote rate collapses to ~0/18. This isn't conservatism finding false promotions — the run data shows the regressions that DO occur are already caught (crossplane reject_floor 0.67->0.33; ARCHIVE v4 blocked crossplane 66.7->0, github-actions 33->0). The failure mode we have is NOT "promoting on a noisy positive win rate"; it is "promoting on TIES" (base==cand, win_rate=0). A win-rate CI gate does not address ties — it just converts "promote on tie" into "reject on tie," which is equally uninformative and burns the entire optimizer loop.

(3) IT PRESUPPOSES DISCRIMINATING SCENARIOS WE DEMONSTRABLY LACK. The win_rate=0 / tie-dominant distribution is a scenario-discrimination artifact, not a statistics problem. Run #8 systemic finding § 3.5.2: 11/17 resources tied at 1.00/1.00, 4 at 0.67/0.67, 2 at 0.33/0.33 — both arms score identically. The scenario-discrimination research (IRT a-parameter / point-biserial; arXiv 2505.15055, 2602.11674) is explicit: a scenario both arms pass (or both fail) is a low-discrimination item with zero separating power, and no aggregation statistic recovers signal that isn't in the items. The roadmap itself concedes this (§ 4.0 Decision A: "A bootstrap CI lower-bound > 0.5 on 11 of 17 resources where both arms pass 100% is wasted statistical power"; § 3.5.2: "A bootstrap-CI on win rate over scenarios where both arms pass 100% of the time has nothing to bite into").

Where the assumption is partly right: the THRESHOLD FORM ("lower bound of a CI on the candidate-vs-baseline advantage exceeds the break-even point") is the correct shape for a promotion decision, and pairwise is the right modality for a promote/reject gate (llm-judge-reliability research). The error is the distributional method (percentile bootstrap), the assumed N, and sequencing it before scenario discrimination is fixed.
RECOMMENDATION: Do these in order; do NOT ship the bootstrap-CI gate as specified.

1. FIX DISCRIMINATION FIRST (hard prerequisite, blocks all gate work). Implement roadmap § 3.6 fix #4: condition the cgf-eval-architect on v0 failure modes and require a per-scenario discrimination self-check ("if v0 ran this, would it fail? articulate the specific failure"). Add a cheap discrimination audit: run v0 against generated scenarios and discard any the v0 passes (research scenario-discrimination § implication 4: target >=40% v0->v1 flip rate). Until per-resource win_rate is non-zero on a meaningful fraction of scenarios, NO win-rate gate (bootstrap or otherwise) can function. This is the single highest-leverage change and the run data proves it.

2. REPLACE PERCENTILE BOOTSTRAP WITH A BETA-BINOMIAL POSTERIOR (free, exact, ~10 LoC). Gate condition: promote iff P(p > 0.5 | k wins, m decisive) > 0.95 under a Jeffreys prior Beta(0.5,0.5), i.e. the 5th percentile of Beta(k+0.5, m-k+0.5) > 0.5 (small-n-statistics research; arXiv 2510.04265, PyMC/Evan Miller closed forms). Zero resampling variance — it is the analytical answer the bootstrap approximates badly at N<20. The bootstrap buys nothing here and is strictly worse at this N.

3. USE PAIRED OUTCOMES, NOT POOLED WIN RATE. Same scenarios run both arms, so the comparison is paired. Gate on a paired sign test / McNemar over DISCORDANT pairs (scenarios where exactly one arm passed). At N=3 even paired tests have ~no power, which is itself the signal that you need #1, not a fancier statistic. Set an explicit minimum-decisive-pairs floor (~10-15 per small-n research) below which the gate abstains rather than fires — and raise trials_per_scenario to 3 and scenarios-per-resource well above 3 to reach it.

4. TREAT no_decision EXPLICITLY. With no_decision_rate up to 0.667 in the data, decisive N is even smaller than 3. Either reduce no_decision at the source (judge-prompt hardening, finer-grained scale per llm-judge-reliability) or count no_decision as a half-credit (0.5) to preserve N — do not silently discard it, which is what aggregate.py does today (compare_arms returns no_decision and aggregate_subset counts it as a non-win).

5. KEEP THE COST GATE AS THE GUARDRAIL, FIX ITS NOISE. The cost gate is currently the only stage doing discrimination (backwards, per § 3.5.2), but the immediate cost-gate defect is baseline noise (helm-charts baseline CPS swung $0.15->$0.32->$0.19, 2.1x, rejected 3x at quality 0.97-1.00). Land § 3.6 fixes #1 (cache baseline_cost_per_success per (resource, eval_suite_hash)) and #2 (absolute tau floor max(baseline*1.10, baseline+$0.05)) before any statistical-gate work — ~40 LoC, directly fixes a documented false-rejection.

Net: the Phase B gate should be a Beta-Binomial posterior on PAIRED discordant outcomes with an abstain-below-N floor, gated behind scenario-discrimination work — not a percentile bootstrap, and not before discrimination is fixed.

### ASSUMPTION: The cost gate (cost_per_success ≤ baseline*(1+τ), τ=0.10 quality-scaled) is sound, and the noisy-baseline problem is best fixed by caching baseline CPS per (resource, eval_suite_hash) and/or an absolute τ floor (roadmap fixes #1, #2).
VERDICT: CHALLENGED | conf: high | priority: P1
RATIONALE: The cost gate's MECHANICS are sound (independent two-gate quality-AND-cost, no scalarization — correct per ParetoPrompt/Chebyshev multi-objective canon, and the code docstring explicitly cites Han 2025 to avoid Goodhart-on-tokens). But the assumption that the proposed fixes address the real problem is wrong in two ways.

(1) CACHING A SINGLE NOISY DRAW IS THE WRONG FIX. The run data is decisive: helm-charts baseline CPS swung $0.15→$0.32→$0.19 (2.1x) for the *same v0 file*. I verified why in code: `aggregate.py::cost_per_success` = total_cost/successes, and `models.py` ships `trials_per_scenario: int = 3` but smoke runs at 1 (per CURRENT STRATEGY). At n=1 per scenario, each scenario contributes at most one success, so baseline CPS is essentially a single Bernoulli-weighted cost draw — its round-to-round variance (~110%, run #8) dwarfs the τ=0.10 tolerance. Caching that draw per (resource, eval_suite_hash) FREEZES one arbitrary sample of a ~110%-variance distribution and tests every candidate against it forever. If the cached draw happens to be the $0.15 low, you reject good candidates; if it's the $0.32 high, you wave through expensive ones. The small-n-statistics research is explicit that point estimates at n<15 are unreliable and that you need either more samples or interval methods — caching is neither. The correct fix is to ESTIMATE THE BASELINE FROM MULTIPLE SAMPLES: raise baseline-arm trials (the floor/incumbent arm runs once per resource — its cost is amortizable, unlike per-candidate cost), and gate on a paired/relative statistic (median CPS ratio or a CI on the ratio) rather than the raw mean. This is affordable precisely because the baseline is evaluated once and reused across all feedback rounds (confirmed: floor runs once at first promotion; F17 skips re-eval of unchanged baselines). An absolute τ floor (fix #2) is a reasonable cheap guardrail to stop rejections on trivially small absolute deltas, but it is a band-aid, not a cure — it does nothing about the variance, it just clips its tail.

(2) THE COST GATE IS DOING DISCRIMINATION WORK THE QUALITY SIGNAL SHOULD BE DOING — this is the real problem the assumption hides. Run #8: 11/17 final resources tied 1.00/1.00, 4 at 0.67/0.67, 2 at 0.33/0.33; archive v4: win_rate=0.0 across ALL 18, 14/18 promoted on ties. The quality/win-rate signal is FLAT. With quality flat, the cost gate is the ONLY gate that bites — which is backwards. The scenario-discrimination research (IRT a-parameter, BHI Capability Discrimination, the v0-vs-candidate flip-rate audit) names this exactly: these are low-discrimination (low-a) items, and items at extreme difficulty (p>0.9, e.g. commands/iac floor=1.00) are almost always low-a. The llm-judge research compounds it: a 1-5 INTEGER absolute scale compresses to 2-3 effective points at the ceiling, and the system uses llm_judge on only ~5% of scenarios (the rest deterministic/contains/trajectory). So the one signal that could separate arms is both coarse-scaled AND barely deployed. τ=0.10 is also indefensible pre-calibration — it is a hardcoded `DEFAULT_TOKEN_REGRESSION_TOLERANCE = 0.10` with no empirical basis, and it is being applied against a baseline whose own measurement noise is 10x larger. Tuning τ before fixing the n=1 variance and the flat quality signal is calibrating the trigger-pull weight on a gun whose sights are unmounted.

On HARD vs Pareto: keeping cost as a hard gate is defensible (multi-objective dominance gating is canon, and the run data shows real value — run #8 recovered 7/7 cost-rejected candidates after I15, and the gate caught genuine +115% bloat like gitops-argocd at zero quality gain). But a hard gate is only legitimate when its inputs are reliable. Today the cost gate is a hard gate on a noisy single-draw baseline while the quality gate is soft (`≥` equality promotes) on a flat signal — the rigor is allocated to exactly the wrong axis.
RECOMMENDATION: Re-sequence the roadmap. Do NOT ship "cache baseline CPS per (resource, eval_suite_hash)" — it freezes a single draw of a 110%-variance distribution. Instead: (1) Make the baseline estimate multi-sample. Decouple baseline-arm trials from candidate-arm trials and run the baseline/floor arm at n≥5 (afford it: the baseline is evaluated once per resource and reused across all feedback rounds via F17, so the cost is amortized, not per-candidate). Gate on a relative statistic — median candidate-CPS / median baseline-CPS, or a Beta/bootstrap-style interval on the paired CPS ratio — not raw-mean vs raw-mean. (2) Keep an absolute τ floor only as a cheap secondary guard ('don't reject when |ΔCPS| < $0.02 absolute'), explicitly labeled a band-aid, not the fix. (3) BEFORE touching τ at all, fix the upstream signal the cost gate is compensating for: (a) switch llm_judge from 1-5 integer to G-Eval probability-weighted scoring (zero rubric change, recovers continuous signal) or a 7-point anchored scale, and route content-only agent_definition/skill resources to llm-judge rubric graders instead of trajectory graders (resource_types.py already has the type system — add the routing); (b) add a v0-vs-candidate discrimination audit at EVAL_DESIGN: run the v0 resource on each generated scenario and discard scenarios where v0 already passes, targeting ≥40% expected flip rate, so the quality gate stops being flat. (4) Defer τ calibration to Phase D's Cohen's-κ work; a hardcoded τ=0.10 against a 110%-noise baseline is not calibrated and should not be presented as 'sound.' Net: the cost gate stays hard, but only after its baseline input is de-noised and the quality signal is made to discriminate — at which point the cost gate stops doing the quality gate's job.

### ASSUMPTION: The eval architecture is adequately ADAPTIVE across diverse resource types and "continuous learning of what works" is adequately covered by Phase D calibration.
VERDICT: REFUTED | conf: high | priority: P1
RATIONALE: Both halves of the assumption fail against code, run data, and research.

ADAPTIVITY IS NOT IMPLEMENTED — IT IS A STATIC TABLE PLUS A UNIFORM ARCHITECT. The protocol layer defines eval_strategy per resource type (content_only / content_and_execution / executable / server in resource_types.py:155-205), but grep confirms eval_strategy has ZERO consumers in graders/ or eval_harness/ — it is dead metadata. There is no grader-routing-by-resource-type logic anywhere. Instead, cgf-eval-architect.md hardcodes a uniform level-mix table (lines 51-60: agent → 1 trajectory+1 e2e+1 unit; skill → 1 unit+1 e2e+1 trajectory; etc.) and a uniform 40/40/20 difficulty and 33% held-out split (lines 62, 184) applied identically regardless of resource type or sector. The §11.2 'resource-type evaluation matrix' and eval_profile.yaml (roadmap line 719, 'declares resource type + grader selection + thresholds') are documented aspirations, not code — no eval_profile.yaml reader exists. This is the textbook one-size-fits-most architecture.

THE RUN DATA SHOWS THIS DIRECTLY HARMS RESULTS. Run #8: agents/iac-generator was 0/0 on both arms (structurally unwinnable) because the architect was INSTRUCTED to put trajectory graders (tool_called:Write) on an agent-definition file that loads as a system prompt and never executes tools — 6 of the suite's 8 trajectory graders landed on this one mis-routed resource. The agent-trajectory-eval research is unambiguous here: 'a resource classified as agent_definition or skill (no execution surface) should route to LLM-judge rubric graders, not trajectory graders... the missing piece is the routing logic that selects graders based on type.' The harness has the type system (resource_types.py) but not the routing — exactly the diagnosed gap. The roadmap itself concedes this at line 338 ('The architect prompt needs an explicit routing rule') and §3.5.3, so the assumption that adaptivity is 'adequately' covered is contradicted by the project's own retrospective.

UNIFORM TIERS/THRESHOLDS COMPOUND THE FLAT-SIGNAL PROBLEM. Run #8's dominant failure mode: 11/17 resources tied at 1.00/1.00, win_rate ~0 across the board, llm_judge used on ~5% of scenarios (3/55 in v4). The cost-ordered grader preference ('prefer deterministic over llm_judge whenever a pattern can capture the requirement', plus architect line 368 'Use contains aggressively') systematically starves the only graders capable of discriminating qualitative quality. The scenario-discrimination research is precise: 'a rubric criterion that both baseline and candidate always satisfy is a non-discriminating criterion'; contains-on-a-keyword is a maximally low-discrimination (low-a) item. A single uniform tau=0.10 against a baseline whose cost-per-success swings 2.1x round-to-round (helm-charts $0.15→$0.32→$0.19) is testing against noise — adaptive-eval research (RocketEval, AdaRubric, FrugalGPT cascade) shows grader selection should be a function of (resource type × task complexity × expected discriminability), and AdaRubric's task-adaptive rubrics hit r=0.79/alpha=0.83 vs generic fixed rubrics precisely because uniformity destroys signal.

PHASE D DOES NOT COVER 'CONTINUOUS LEARNING OF WHAT WORKS.' This is a category error in the assumption. Phase D (roadmap §6, lines 433-447) is judge CALIBRATION: Cohen's kappa per (resource type × judge × rubric) via make eval-calibrate, ensemble fallback when kappa<0.8, CI on PRs, plus I16 cost-gate τ tuning. Calibration answers 'do I trust the judge's scores?' — it is a measurement-trust mechanism. It does NOT answer 'what context-engineering moves reliably improve which resource types?' Grep confirms ZERO persistence of learnings/ledger/edit-pattern/insight/experience-replay/anti-pattern anywhere in src/harness/optimization (the only 'anti-pattern' hits are inline optimizer-prompt prose, not stored knowledge), and ZERO hits for 'continuous/record-learn/sector/industry/cross-run/compound' in the roadmap. The feedback in iterate.py:1118-1131 is write-once: it passes a verdict-keyed directive ('TRIM TOKENS') plus a per-scenario miss list into the max-2-round loop, then is discarded. Nothing survives cgf-clean; run N starts exactly as naive as run 1. The adaptive-eval-and-learning research names this exact gap — Reflexion/ExpeL/CLIN/Contextual-Experience-Replay all establish that a 'learnings ledger' (run records → edit-pattern library with confidence intervals → causal map → anti-patterns → meta-rubric index, retrieved by semantic similarity at run start) is what 'converts a series of isolated optimization episodes into a compound-learning system.' Calibration and a learnings ledger are orthogonal artifacts; folding one into the other leaves the user's explicit requirement ('CONTINUOUSLY RECORD LEARNINGS about effective context-engineering principles') entirely unaddressed.

NUANCE / FAIRNESS: The project is partially self-aware — the resource-type matrix is designed, eval_profile.yaml is named, the unwinnable-resource detector (§2.9) catches the symptom non-blocking, and the F20 command-scenario fix shows the routing-by-type instinct exists for one case. But 'designed in a doc' and 'symptom-caught after the fact' is not 'adequately adaptive,' and none of it touches continuous learning.
RECOMMENDATION: Take three concrete, separable actions.

(1) MAKE eval_strategy LOAD-BEARING (close the adaptivity gap at its root — ~1 day). Add grader-routing-by-resource-type so the dead eval_strategy field drives grader selection. Concretely: in the EVAL_DESIGN path, before the architect writes scenarios, resolve each resource's eval_strategy from ResourceTypeRegistry and pass an allowed/forbidden grader-type set into the architect prompt as a hard constraint. Route content_only (skill, command, hook, plugin, AND agent-definition files with no executable tools) → llm_judge rubric graders + contains, NEVER trajectory. Route executable/server (mcp_tool, mcp_server) and content_and_execution agents that actually dispatch tools → trajectory + outcome + deterministic. Replace the hardcoded level-mix table in cgf-eval-architect.md lines 51-60 with this strategy-derived mapping. This alone eliminates the iac-generator unwinnable class and is the smallest change that converts the static matrix into live routing. Validate by re-running the iac-team fixture and confirming zero 0/0-both-arms resources.

(2) MAKE THE ARCHITECT DISCRIMINATION-AWARE AND BREAK GRADER-TIER UNIFORMITY (close the flat-signal gap — the §3.2 Phase B prerequisite). (a) Mandate, per scenario, at least one rubric criterion that 'an unoptimized/v0 resource would plausibly fail' (HealthBench/BiGGen partial-credit pattern), and require the architect to articulate a specific v0 failure mode per scenario or regenerate it (the LLM-as-discriminator steer from the scenario-discrimination research). (b) Replace the blanket 'prefer deterministic, use contains aggressively' with a per-resource-type grader profile: content_only resources should default to llm_judge with criterion-decomposed rubrics (not contains-on-keyword), because the run data shows contains produces ties at 1.00. (c) Add a cheap pre-commit discrimination audit: run v0 on each generated scenario; discard scenarios v0 passes; target >=40% expected v0→v1 flip rate before the suite enters held-out gating.

(3) ADD A FIRST-CLASS 'LEARNINGS LEDGER' AS A NEW ROADMAP ITEM, DISTINCT FROM PHASE D CALIBRATION (close the continuous-learning gap — warranted, not covered). Sketch: an append-only, workspace-external store (survives cgf-clean) with five layers from the adaptive-eval-and-learning research — (i) Run records: (resource_id, resource_type, sector/domain tags, edit_type, per-grader score deltas, cost delta, verdict) emitted on every ITERATE/EXECUTION_EVAL cycle; (ii) Edit-pattern library: ExpeL-style induced rules with N-observation confidence intervals ('for mcp_tool + input_schema_validation + reject_floor, adding explicit JSON schema with examples raised pass_rate by avg +0.18'); (iii) Causal map of edit-move → score-shift segmented by resource type; (iv) Anti-patterns (Reflexion-style negatives — moves that degraded scores); (v) Meta-rubric index of which rubrics are well-calibrated per (type × judge) — THIS is the only layer that overlaps Phase D, and it consumes Phase D's kappa output rather than duplicating it. Plug-in points: WRITE at the end of execution_eval.py (the verdict + per-scenario deltas already exist there in the feedback builder); READ at the start of RESEARCH/ITERATE via a semantic-similarity retrieval step that injects top-K edit-patterns + anti-patterns for the current resource type + domain into the optimizer's context (Contextual Experience Replay). Net effect the user asked for: the optimizer starts run 1 of a new resource smarter than it finished run 8 of a prior similar one. Scope it as a new roadmap section (suggest §8 'Phase E — Compound Learning' or a cross-cutting item) explicitly separate from Phase D, with calibration's meta-rubric index as the one shared dependency.

---


================================================================================
# RESEARCH NOTE 1: llm-judge-reliability
================================================================================

I now have sufficient primary-source data. Here is the synthesis.

---

# LLM-as-Judge Reliability: State of the Art (2024–2026)

---

## 1. Absolute (Pointwise) vs. Pairwise: Reliability and Discrimination

The common intuition is that pairwise is more reliable because relative comparisons are cognitively easier. Recent evidence complicates this.

**Where pairwise wins:** Pairwise framing better captures the real decision "is candidate B better than baseline A," and it is the backbone of Chatbot Arena's strong human-agreement record (>80%). When the evaluation task is model selection—not monitoring—pairwise gives a cleaner signal.

**Where pointwise wins on robustness:** A 2025 paper (arXiv 2504.14716) directly tested manipulation vulnerability. Generator models can embed spurious "distractor features" in a response. Pairwise preferences flipped in ~35% of cases under this attack; absolute scores flipped in only 9%. The paper's conclusion: absolute scoring better reflects true quality and is less exploitable. Pointwise also has a strong practical advantage—it is longitudinally comparable, useful for monitoring, and O(n) not O(n²).

**Discrimination ceiling of coarse pointwise scales is the real problem** (see §2 below), not the scoring mode itself. A 2025 study (arXiv 2505.19334) showed that expanding from 2-point binary to 11-point ordinal scales made pointwise performance statistically indistinguishable from listwise ranking on 31/40 model-dataset combinations. The scale, not the mode, is the primary discriminating lever.

**Current consensus:** Use pointwise with explicit, criterion-separated rubrics and a fine-grained (7–11 step) scale for debugging and longitudinal tracking; use pairwise for high-stakes model promotion decisions where a single binary "promote/reject" is the real question. Mixing them (as a two-stage gate) is emerging best practice.

---

## 2. Score Scale Design: Problems with Coarse Integer Scales

A 1–5 integer scale has well-documented failure modes:

- **Ceiling and floor compression.** Frontier models cluster at 4–5; genuine quality differences vanish. The effective resolution is often 2–3 points in practice, not 5.
- **Label ambiguity.** Without anchored descriptions per step, different judge sessions interpret "3" differently. Cross-run comparisons are unreliable.
- **Probability mass concentration.** LLMs tend to avoid the extremes (1 and 5), further compressing the working range to 2–4.
- **Binary proxy.** When a single retry-as-tie is applied, a 1–5 scale functionally collapses to 3-class (bad / uncertain / good), discarding the main reason for using an ordinal scale.

Better alternatives documented in the literature:
- **7–11 point scales** with anchored labels at each step (not just endpoints).
- **Probability-weighted scoring:** rather than forcing an integer, take the expectation over the token probability distribution across score tokens. This recovers continuous signal from an integer-trained judge.
- **Criterion decomposition:** break "overall quality" into sub-dimensions (e.g., correctness, completeness, conciseness) scored separately. Aggregated sub-scores outperform holistic integer scores on human agreement.
- **Pairwise binary** (A > B, tie) avoids the scale problem entirely but loses absolute magnitude information.

---

## 3. Biases: Magnitude and Mitigation

### Position Bias
2024 studies found ~75% first-position preference in some models. However, a 2026 systematic study (arXiv 2604.23178) found position bias is now **negligible (≤0.04)** in current-generation models (GPT-4o, Claude Sonnet 4, Gemini Pro). Position-swap mitigation had mixed effects: +4.6 pp for Gemini Pro, −2.4 pp for GPT-4o. **For current frontier judges, position swapping may not help and can hurt.** It remains prudent for older or smaller judge models.

### Verbosity/Length Bias
The same 2026 study found a **conciseness preference**, not a length bias: models correctly penalize filler content and recognize genuine completeness at 92–100% accuracy on truncation pairs. Traditional "penalize length" mitigations may be counter-productive. **Calibrated rubrics (−0.11 average bias reduction) and CoT forcing are the effective interventions.**

### Self-Preference Bias
Panickssery et al. (arXiv 2410.21819) identified the root mechanism as **perplexity-based familiarity**, not egocentric reasoning. LLMs rate lower-perplexity text higher regardless of whether they generated it. A 2026 study (arXiv 2604.22891) measured 20 production models and found high variance: DeepSeek-V3.2 β=+0.23, Claude Sonnet 4.5 β=−0.23 (over-corrects), DeepSeek-V3-0324 near zero. Crucially, **high capability is uncorrelated with low bias**—six "Machiavellian judges" showed both high discrimination and high self-preference. Mitigation via dimension-wise forced-choice comparisons (prompt-only change) reduced SPB by 31.5% on average, 70% in best cases.

**Key practical implication:** always use a judge from a different model family than the generator being evaluated. Family bias causes systematic over-rewarding of same-family outputs.

### Style Bias
This receives the least attention but 2026 measurements found it dominates all other biases (0.76–0.92 magnitude vs. ≤0.04 for position). Markdown formatting, confident phrasing, and structured lists inflate scores independently of content. A combined rubric-plus-budget mitigation strategy dropped average style bias from 0.84 to 0.58.

---

## 4. Judge–Human Agreement: Measurement and Thresholds

| Metric | What it measures | Acceptable threshold |
|---|---|---|
| Cohen's κ | Pairwise category agreement, corrected for chance | κ ≥ 0.60 = substantial; κ ≥ 0.80 = strong |
| Krippendorff α | Multi-rater, handles ordinal/continuous data | α ≥ 0.667 minimum; α ≥ 0.80 for reliability |
| Pearson r / Spearman ρ | Correlation of score sequences | r ≥ 0.80 used as filter threshold in recent meta-evaluations |

Zheng et al. 2023 (MT-Bench) reported GPT-4 matching human inter-rater agreement levels (>80%) on open-ended questions. JudgeBench (arXiv 2410.12784) found that on **objectively verifiable tasks** (math, reasoning, code), GPT-4o performs barely above random guessing—a critical finding that the MT-Bench result (open-ended, subjective) does not generalize to factual correctness domains. Prometheus 2-8x7B achieves Pearson r=0.555 with human raters on FLASK, vs. 0.449 for the original Prometheus.

Current meta-evaluation practice: filter judges with r ≥ 0.80 on a domain-matched human gold set, then compute Cohen's κ. Monthly re-calibration is recommended because judge performance drifts as the distribution of model outputs changes.

---

## 5. Ensembles, Multi-Sampling, and Fine-Tuned Judges

**When ensembles help:** Averaging across 3+ judge calls from different models reduces variance and partially cancels self-preference and family bias. A "majority vote" ensemble (haiku + sonnet + opus) on pairwise decisions is measurably more reliable than any single judge on close calls. However, ensembles 3× the cost.

**Multi-sampling (repeated calls, same judge):** Reduces random variance but not systematic bias. Useful for soft scores on borderline cases; cheap. A retry-once pattern captures ~60% of the variance reduction of a 3-sample average.

**Fine-tuned judges (Prometheus 2, JudgeLM):** Outperform frontier models when: (a) the rubric is stable and known at training time, (b) the domain is narrow and the fine-tune dataset covers it, (c) cost at scale is a constraint. They underperform frontier models on novel rubrics, out-of-domain tasks, and factual correctness (JudgeBench result holds here too). An empirical study (arXiv 2403.02839) confirmed: **fine-tuned judges are not general substitutes for GPT-4**. Best practice is fine-tuned judge for high-throughput production scoring + frontier anchor for periodic calibration.

**G-Eval (2023):** Introduced the probability-weighted scoring approach (averaging score token probabilities), consistently outperforming hard argmax sampling. Widely adopted as a drop-in improvement over raw integer output.

---

## 6. Key Papers Reference

- MT-Bench / Chatbot Arena: [Zheng et al. 2023 - OpenReview](https://openreview.net/forum?id=uccHPGDlao)
- Pairwise vs Pointwise bias: [arXiv 2504.14716](https://arxiv.org/abs/2504.14716)
- Self-preference (perplexity mechanism): [Panickssery et al. arXiv 2410.21819](https://arxiv.org/abs/2410.21819)
- SPB quantification/mitigation across 20 models: [arXiv 2604.22891](https://arxiv.org/html/2604.22891v2)
- Bias mitigation strategies systematic evaluation: [arXiv 2604.23178](https://arxiv.org/html/2604.23178)
- JudgeBench: [arXiv 2410.12784](https://arxiv.org/abs/2410.12784)
- Prometheus 2: [arXiv 2405.01535](https://arxiv.org/html/2405.01535v2)
- Likert vs fine-grained ordinal scales: [arXiv 2505.19334](https://arxiv.org/html/2505.19334v1)
- Fine-tuned judge generalization limits: [arXiv 2403.02839](https://arxiv.org/html/2403.02839)
- LLM-as-judge survey 2025: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2666675825004564)
- 2026 best practices: [FutureAGI](https://futureagi.com/blog/llm-as-judge-best-practices-2026)

---

## IMPLICATIONS for the Current System

**The system today:** single Opus judge, 1–5 integer absolute scale, retry-once → no_decision=tie, pairwise deferred.

**1. The 1–5 integer scale is the highest-priority fix.** Evidence is unambiguous: a 5-point scale with frontier models clusters in 3–4, produces effective 2–3 point resolution, and makes promotion decisions dependent on a coin-flip around the midpoint. Concretely: candidates near the threshold will be unstably classified. Switching to probability-weighted scoring (G-Eval style: take the expectation over score-token probabilities at generation time) is a low-effort, zero-rubric-change upgrade that recovers continuous signal. Alternatively, expand to 7-point with one-sentence anchors per level.

**2. Opus as judge introduces self-preference risk against Opus-generated candidates.** Opus β is not yet measured in the 2026 study, but self-preference is structurally plausible when the generator being optimized is also Opus-class. The mitigation is low-cost: add a different-family model (e.g., Gemini or GPT-4o) as a second judge on promotion decisions, or at minimum on borderline cases (scores of 3 on the current scale). The 2026 study's recommendation—use a judge from a different model family—directly applies here.

**3. Retry-once → tie is a symptom of scale coarseness, not a solution.** If the judge were well-calibrated on a fine-grained scale, the no_decision rate would drop naturally because borderline cases would produce stable fractional scores rather than integer disagreements. Treating retry-as-tie inflates the no_decision count and suppresses genuine promote/reject signal. This is the second-priority fix after scale granularity.

**4. Style bias (0.76–0.92 magnitude) is the largest unmitigated risk today.** A candidate optimizer that learns to produce well-structured, confident-sounding markdown will score higher regardless of functional quality. Chain-of-thought forcing and criterion-separated rubrics are the primary mitigations. The current 1–5 holistic score is maximally vulnerable to this; decomposing into 3–4 sub-criteria scores and aggregating reduces it substantially.

**5. Pairwise "reserved for later" is structurally correct for the promote/reject gate.** The literature confirms pairwise is the right tool for model selection decisions. Integrating it as the final promotion gate (candidate vs. floor baseline, A-B + B-A, majority rules) once Phase B ships would address the gate's current dependence on noisy absolute scores. The 35% flip rate in pointwise-manipulable scenarios is not a concern for adversarial manipulation here, but it does indicate that close pairwise calls are genuinely uncertain—which supports the bootstrap-CI approach in Phase B.

**6. No monthly calibration against a human gold set is a silent failure mode.** The 2026 best-practices consensus is clear: without periodic re-calibration (200–500 labeled traces per rubric, Cohen's κ computed monthly), judge drift goes undetected. For a research system this is aspirational, but logging judge decisions with the final human-confirmed outcome (promote/reject in production) is the minimum viable calibration signal, and it is already available from run outcomes.

================================================================================
# RESEARCH NOTE 2: small-n-statistics
================================================================================

Now I have enough to synthesize a thorough, well-grounded answer.

---

## Statistical Methods for Small-N LLM Eval Gates (2024-2026 Practice)

---

### 1. Bootstrap CI on Win Rate — Validity and Pitfalls at Small N

Bootstrap 95% CIs on win rate (proportion of scenarios where candidate B beats baseline A) have become the de facto standard for LLM leaderboards such as Chatbot Arena, which uses 10,000 resamples. The intuition is sound — resample the binary win/loss/tie outcomes with replacement, compute win rate for each resample, read off the 2.5th/97.5th percentiles.

**The problem at small N is severe and now well-documented.** A 2025 ICML Spotlight Position Paper argues directly that CLT-based and asymptotic methods "usually dramatically underestimate uncertainty (i.e. produce error bars that are too small)" for benchmarks below a few hundred datapoints, and recommends Bayesian alternatives [Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints - https://arxiv.org/pdf/2503.01747]. At N=10-30 decisive comparisons, the bootstrap distribution is itself noisy — the tail percentiles are estimated from a small number of distinct resample patterns. Empirically, bootstrap CIs achieve near-nominal coverage only as N grows; for N<40, they can be both under-covering (too narrow) and unstable between runs. The Wilson score interval, which Brown, Cai, and Dasgupta recommend for N<40, achieves better actual coverage than the basic percentile bootstrap for binary proportions. A separate sensitivity study on LLM rankings found that Bayesian credible intervals and Wilson CIs achieve proper coverage at small N where bootstrap does not [Dropping Just a Handful of Preferences Can Change Top LLM Rankings - https://arxiv.org/pdf/2508.11847].

**Specific pitfall with the "lower bound > 0.5" rule:** At N=15 decisive comparisons, a 12-3 win (80% win rate) gives a basic 95% bootstrap CI of roughly [0.54, 0.95] — the lower bound barely clears 0.5. But 10-5 (67%) often yields a lower bound near 0.40-0.45, failing the gate — which may be appropriate caution, or may be overly conservative depending on effect size. The rule is directionally reasonable but the bootstrap tail is unreliable at N<20; a Wilson or Bayesian interval is more trustworthy for the same threshold.

---

### 2. Bayesian Beta-Binomial / Credible Intervals

The Beta-Binomial is the natural model: place a Beta(1,1) (uniform) or Beta(0.5, 0.5) (Jeffreys) prior on the win probability p, observe k wins out of N decisive trials, get Beta(k+α, N-k+β) posterior analytically — no MCMC required.

**Where it beats bootstrap at small N:** The posterior is exact regardless of N, it naturally incorporates prior knowledge (e.g., a weakly informative prior biased slightly toward 0.5 reflects the prior expectation that candidate and baseline are similar), and the 95% credible interval has honest interpretation. A 2025 paper on Bayesian LLM evaluation frameworks [Don't Pass@k: A Bayesian Framework for LLM Evaluation - https://arxiv.org/pdf/2510.04265] applies exactly this class of models. The PyMC documentation and Evan Miller's reference formulas cover the closed-form Beta posterior for the common case [Bayesian A/B Testing - PyMC - https://www.pymc.io/projects/examples/en/stable/case_studies/bayesian_ab_testing_introduction.html; Formulas for Bayesian A/B Testing - https://www.evanmiller.org/bayesian-ab-testing.html].

**Practical form:** "Promote if P(p > 0.5 | data) > 0.95" is equivalent to the lower bound of a 90% credible interval exceeding 0.5, and is more honest than a bootstrap percentile at N<20. With Jeffreys prior (Beta(0.5, 0.5)), the posterior at 10-3 (N=13) gives P(p>0.5) ≈ 0.97 — marginally promotes. At 8-5, P(p>0.5) ≈ 0.84 — does not. These are principled numbers even at small N.

---

### 3. Sequential / Anytime-Valid Testing

Standard hypothesis tests (including bootstrap) are fixed-N procedures: peeking at results after each iteration inflates Type I error. In an optimizer loop where you evaluate after every ITERATE round, this is precisely the problem.

**E-values** (multiplicative evidence accumulations) provide "anytime-valid" inference: you can stop, continue, or adjust at any point without inflating false positive rates. A 2025 paper establishes that anytime validity can be induced from classical tests at essentially no cost [Anytime Validity is Free: Inducing Sequential Tests - https://arxiv.org/pdf/2501.03982]. For FWER control across multiple hypotheses in sequential settings, e-value-based closed testing (2025) provides polynomial-time algorithms [Family-wise Error Rate Control with E-values - https://arxiv.org/pdf/2501.09015].

**Practical recommendation:** If you evaluate every ITERATE round (say, 2-3 rounds), the inflation is modest compared to 50-round peeking in an industry A/B test, but it is non-zero. A conservative fix: use the held-out set only for final promotion decisions (see Section 5), not for feedback during ITERATE. For the gate itself, a Bayesian posterior naturally accumulates evidence without a peeking problem — the posterior is simply updated with each additional run.

---

### 4. Bradley-Terry / Elo for Pairwise Aggregation

Bradley-Terry (BT) is a parametric model: each item i has a strength parameter β_i, and P(i beats j) = exp(β_i) / (exp(β_i) + exp(β_j)). Elo is an online approximation to BT with a learning-rate parameter K. LMSYS Chatbot Arena fits a BT model to millions of pairwise human votes and reports Elo-scale scores with bootstrap uncertainty intervals. A 2024 statistical framework paper from Berkeley formalizes this [A Statistical Framework for Ranking LLMs - https://www.stat.berkeley.edu/~mmahoney/pubs/13986_A_Statistical_Framework_.pdf].

**When to use:** BT is most valuable when you have MANY candidates and MANY scenarios, and want a global ranking rather than a binary promote/reject decision. For a two-arm gate (candidate vs. baseline, ~10-30 scenarios), BT and simple win-rate estimation are nearly equivalent — BT's advantage is in handling transitivity across N>2 arms. For your setting (one candidate, one baseline), stick with win rate + Beta posterior. BT becomes valuable in Phase D if you accumulate a history of candidates and want to rank them.

**Tie handling:** BT models can handle ties via Davidson's (1970) extension. Elo simply ignores or half-scores ties. At small N with many ties, effective N drops sharply — both methods become unreliable.

---

### 5. Multiple Comparisons / P-Hacking Risk

Evaluating after every optimizer iteration creates a multiple-testing problem. If you run 10 ITERATE rounds and promote on the first iteration where the gate fires, you have implicitly run up to 10 tests. With α=0.05 per test, family-wise error rate approaches 1-(0.95)^10 ≈ 40%.

**2024-2025 LLM benchmark literature is increasingly aware of this.** A 2025 paper [CapBencher - https://arxiv.org/html/2505.18102] explicitly addresses leaderboard overfitting from repeated evaluation queries against a held-out set.

**The held-out-only-for-promotion guard** directly addresses this: use "development" scenarios (seen by the optimizer) freely for feedback, but run the promotion gate only on a held-out partition the optimizer never saw. This is the correct architecture. Phase A's existing held-out scenario stripping from optimizer feedback is exactly this pattern. The key is ensuring the gate fires at most once per resource (not per ITERATE round).

---

### 6. Paired vs. Unpaired; Minimum Sample Sizes; Effect-Size Thresholds

**Always use paired comparisons** when the same scenarios are run for both arms. The paired structure eliminates scenario-to-scenario variance (which can dominate at small N), giving substantially higher power for the same N. Paired binary outcomes → McNemar's test (exact) or the sign test. Both recommend a "minimum detectable effect" (MDE) framing: at N=20 discordant pairs, you have ~80% power to detect a true win rate of 0.75 (effect size ~0.25 above 0.5) at α=0.05. At N=10 discordant pairs, even a 80% win rate may not reach significance.

**Sample size minimum:** For a Beta posterior gate with a meaningful lower credible bound, you need at minimum ~15 decisive (non-tie) comparisons to draw reliable conclusions. Below 10, even a 9-1 split leaves substantial posterior mass below 0.5 with a weakly informative prior — by design.

---

### IMPLICATIONS FOR THE PROMOTION GATE

The planned gate (bootstrap CI, 1000 resamples, 95%, lower bound > 0.5, ~10-30 scenarios, decisive N often < 15) has four concrete vulnerabilities:

**1. Bootstrap percentile CI is unreliable at N < 20 decisive comparisons.** Replace or supplement with a Beta-Binomial posterior (Jeffreys prior: Beta(0.5, 0.5)). The gate condition becomes: "promote if the 5th percentile of Beta(k+0.5, N-k+0.5) > 0.5," which is equivalent but more honest at small N. This is a two-line code change and produces materially wider, more honest intervals when decisive N < 15.

**2. Tie / no_decision inflation is the dominant risk.** If 10 of 20 scenarios return `no_decision`, your effective N is 10 — a 7-3 split (70% win rate) fails most gates at that N. Options: (a) invest in reducing no_decision rate (scenario quality, judge prompt hardening — the § 3.2 prerequisite), or (b) treat no_decision as a half-win (0.5 score) rather than discarding, which preserves N at the cost of diluting signal.

**3. Multi-round peeking is a modest but real inflation.** With max 2 ITERATE rounds, FWER ≈ 1-(0.95)^2 = 9.75% vs. nominal 5%. Fix: fire the gate only once per resource at the final round, not after each round. Use round-1 eval result for feedback only, not for promotion.

**4. 1000 resamples is adequate for a stable percentile estimate when N > 20 decisive; increase to 10,000 (cheap) or switch to Beta posterior (free) when N < 15.** The Beta posterior has zero resampling variance — it is the correct analytical answer to the same question the bootstrap is approximating.

**Bottom line:** The bootstrap CI gate is a reasonable starting point, but Phase B should replace the percentile bootstrap with a Beta-Binomial posterior gate. The threshold condition (lower bound > 0.5) is correct in form; the distributional assumption is what breaks at small N. The held-out partition guard is the higher-leverage structural fix, because no amount of statistical sophistication compensates for evaluating on scenarios the optimizer has already seen.

---

Sources:
- [Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints](https://arxiv.org/pdf/2503.01747)
- [Dropping Just a Handful of Preferences Can Change Top LLM Rankings](https://arxiv.org/pdf/2508.11847)
- [Exploring the Difficulty of Estimating Win Probability](https://arxiv.org/pdf/2406.16171)
- [Don't Pass@k: A Bayesian Framework for LLM Evaluation](https://arxiv.org/pdf/2510.04265)
- [Bayesian A/B Testing - PyMC](https://www.pymc.io/projects/examples/en/stable/case_studies/bayesian_ab_testing_introduction.html)
- [Formulas for Bayesian A/B Testing - Evan Miller](https://www.evanmiller.org/bayesian-ab-testing.html)
- [A/B Testing LLM Prompts in 2026: Best Practices](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/)
- [Anytime Validity is Free: Inducing Sequential Tests](https://arxiv.org/pdf/2501.03982)
- [Family-wise Error Rate Control with E-values](https://arxiv.org/pdf/2501.09015)
- [A Statistical Framework for Ranking LLMs](https://www.stat.berkeley.edu/~mmahoney/pubs/13986_A_Statistical_Framework_.pdf)
- [Ranking Unraveled: Recipes for LLM Rankings in Head-to-Head AI Combat](https://arxiv.org/pdf/2411.14483)
- [CapBencher: Give Your LLM Benchmark a Built-in Alarm for Test-Set Overfitting](https://arxiv.org/html/2505.18102)
- [Applying Statistics to LLM Evaluations - Cameron Wolfe](https://cameronrwolfe.substack.com/p/stats-llm-evals)
- [Statistical Multi-metric Evaluation of LLM Systems](https://arxiv.org/pdf/2501.18243)
- [Five Confidence Intervals for Proportions - Towards Data Science](https://towardsdatascience.com/five-confidence-intervals-for-proportions-that-you-should-know-about-7ff5484c024f/)

================================================================================
# RESEARCH NOTE 3: scenario-discrimination
================================================================================

I have sufficient material. Here is the research synthesis.

---

# Discriminating Eval Scenarios: Building Test Sets That Separate Good from Bad

## 1. Item Response Theory and the Discrimination Index

Classical test theory uses the **discrimination index** (D = (correct in top 27%) - (correct in bottom 27%) of scorers, scaled -1 to +1) and the **point-biserial correlation** (r_pb, the Pearson correlation between binary item response and total score) to flag weak items. Items with D < 0.20 or r_pb < 0.20 are candidates for pruning - they don't help rank takers.

IRT formalizes this in the **2PL/3PL/4PL logistic models**. The key parameter is **a (discrimination)**, analogous to r_pb but estimated jointly with difficulty (b) and guessing (c). The **Fisher information** at a given ability level is:

> I(θ) = a² · (P(θ)-c)² · (d-P(θ))² / [(d-c)² · P(θ) · (1-P(θ))]

High-a items are sharply sigmoidal - they produce step-function separation between models near their difficulty level. Low-a items (flat curves) produce the same probability of success for both strong and weak models, which is the formal description of a non-discriminating scenario.

Recent work applies these tools directly to LLM benchmarks. The **ATLAS paper** (Adaptive Testing for LLM Assessment, 2025) filters out low-a items and uses computerized adaptive testing (CAT) principles: administer only items whose information I(θ) is maximized given the current ability estimate, drastically cutting evaluation cost while maintaining discrimination. The **PSN-IRT paper** ("Lost in Benchmarks?", 2025) introduces the Pseudo-Siamese Network for IRT to learn item parameters from multi-model response matrices; it recommends screening by Fisher information rather than raw accuracy and reports that items at extreme difficulty (p > 0.9 or p < 0.1) are almost always low-a. The **IRT Audit paper** (Auditing LLM Benchmarks with IRT, 2025) applies IRT across seven preference benchmarks and 114 models, using the a-parameter to surface likely mislabels at 95% precision - demonstrating that low-discrimination items often correlate with annotation errors, not just task difficulty.

**Practical discrimination cutoffs:** For LLM benchmarks a practical floor is a ≥ 0.5 in the 2PL model; items with a < 0.3 should be flagged as candidates for revision or removal. The point-biserial threshold of r_pb ≥ 0.20 from classical test theory translates approximately to this range.

## 2. Difficulty Calibration, Saturated/Trivial Items, and Contamination

**Benchmark saturation** is the ceiling-effect problem at scale. The Benchmark Health Index (BHI, 2025) quantifies three axes: **Capability Discrimination** (how sharply the benchmark separates models), **Anti-Saturation** (headroom before ceiling), and **Impact**. Among 106 benchmarks analyzed across 91 models, nearly all benchmarks released pre-2025 have been surpassed by at least one model family. HumanEval pass@1 approaches 99%, MBPP 94%.

Saturation is not just a difficulty problem - it is also a **resolution problem**: when performance exceeds ~80%, differences of 85% vs. 90% are dominated by dataset artifacts and annotation noise, not genuine capability gaps. The fix is twofold: (1) **difficulty stratification** - explicitly ensure items span the full difficulty range (p ∈ [0.1, 0.9] across the target model population), and (2) **anti-saturation headroom budgeting** - when authoring, generate items that 50%-60% of current frontier models fail.

**Contamination detection** using IRT: unusually high c-parameter estimates (guessing rate) or anomalous b-parameter (items that are "too easy" for their apparent complexity) are diagnostic of training-set contamination - models effectively "remember" rather than reason, producing flat discrimination curves.

## 3. Hard-Negative Mining and Adversarial/Perturbation-Based Generation

Hard negatives are inputs that are semantically close to a positive but require a subtle capability to distinguish. For evaluation, the goal is the reverse: generate scenarios where a **good model passes and a bad model fails** - scenarios that are hard for the evaluated model, not just any model.

**Perturbation-based approaches:**
- **Minimal counterfactual editing**: take a passing scenario and apply the smallest possible semantic perturbation (change one constraint, add one implicit requirement, flip an ordering dependency) that causes the weaker model to fail while the stronger model adapts. This is the LLM-eval analog of adversarial example generation.
- **Hierarchical masking + infilling**: mask critical spans (domain-specific constraints, edge cases, failure modes) and regenerate with an LLM, then verify the re-generated scenario is answered correctly by the strong variant but not by the weak variant.
- **Adversarial red-teaming pipelines** (Learning-Based Adversarial Red-Teaming, 2025): frame scenario generation as a structured search; use a meta-prompt-guided generator + a detector that measures whether the scenario actually flips the target model. Reported 3.9x higher vulnerability discovery rate than manual red-teaming, demonstrating automated discriminating scenario generation at scale.

**LLMs as hard-negative generators:** Prompt an LLM to produce "a task that the v0 version of this agent would fail but the v1 version would pass." This requires the generator to have a model of the capability being improved. The key insight from "SELF-[IN]CORRECT" (2025): LLMs' ability to **discriminate** responses is weaker than their ability to **generate**, so a naive LLM discriminator will accept non-discriminating scenarios. The generator must be steered with explicit contrast criteria.

## 4. Criterion-Referenced / Rubric-Based Evaluation for Graded Signal

Binary pass/fail is the root cause of floor/ceiling effects. Moving to **partial-credit rubrics** expands the information per item.

**HealthBench** (OpenAI, 2025): each scenario has a per-criterion point value in [-10, +10]; total score is the weighted sum of rubric criteria met. This yields a continuous score per scenario even when both model variants pass all "does it work?" checks, because they can differ on Completeness, Context Awareness, Communication Quality. A scenario where both baseline and candidate score 8/10 is more useful than one where both score 10/10.

**BiGGen Bench** (NAACL 2025 Best Paper): 77 tasks across 9 capabilities, each scored on a 5-point Likert scale by instance-specific rubrics. The instance-specific rubric is critical - the rubric is designed for the particular scenario, not a generic quality axis, so the rubric itself embeds the discriminating signal (what exactly distinguishes a 3 from a 4 on this task). This is the mechanism that prevents floor/ceiling collapse on any single item.

**FLASK**: 12 fine-grained evaluation dimensions per instance; showed higher human-judge correlation than coarse helpfulness/harmlessness axes, because fine-grained dimensions have lower mutual ceiling probability.

The practical principle: **a rubric criterion that both baseline and candidate always satisfy is a non-discriminating criterion**. Rubric authors must include at least one criterion that the baseline reliably fails.

## 5. Measuring an Eval Set's Separating Power

The **gold-standard discrimination audit** is to run the eval suite against a deliberately degraded variant and measure the flip rate:

1. Create a degraded variant (remove a capability, downgrade a model component, stub out a tool, regress to v0 of the resource being optimized).
2. Run both the candidate and the degraded variant on all scenarios.
3. Compute **discrimination rate** = |{items where candidate passes AND degraded fails}| / N.

Items where both pass (true positive ceiling) or both fail (floor) have zero discriminating value. The goal is to maximize the count of "flip items." This is directly analogous to running a benchmark against a random baseline to measure AUC above chance.

The **BHI Capability Discrimination** axis operationalizes this at benchmark level: it measures variance in model scores rather than absolute level. The **TinyChange benchmark** (2025) extends this to detect API-level model degradation using ROC AUC across model variants, measuring discrimination as AUC of separating current vs. degraded version across items.

**IRT-based audit** (arxiv 2605.30504): using response matrices from many models, compute the a-parameter distribution across items. Items with a < 0.3 are flagged for removal. The resulting pruned benchmark has higher average Fisher information per item and thus fewer items needed for reliable model ranking.

---

## Implications for an Agent Auto-Authoring Eval Suites

The problem: CGF's cgf-eval-architect agent keeps producing scenarios where baseline == candidate (both pass at 1.0 or both fail at 0.0, win_rate ~ 0). This is the low-a item problem manifesting in LLM-generated evals.

**Root causes and fixes:**

**1. The architect has no model of baseline capability.** It cannot generate discriminating scenarios without knowing what the baseline *specifically* fails at. Fix: before EVAL_DESIGN, run the baseline agent on a small calibration probe set (or use transcripts from prior runs) to map its failure modes. Then constrain the architect's prompt: "generate scenarios that require [capability X] where capability X is precisely what was improved in v1."

**2. Require a discrimination self-check.** After generating each scenario, the architect (or a separate step) should ask: "If this scenario were given to the original v0 resource, what would it do? Would it fail?" If the architect cannot articulate a specific failure mode for v0, the scenario is likely non-discriminating and should be regenerated. This is the LLM-as-discriminator pattern, but steered toward a specific capability model.

**3. Mandate partial-credit rubrics with at least one fail-prone criterion.** Replace binary pass/fail with HealthBench-style weighted rubrics. Each scenario spec should require at least one rubric criterion that "a naive/unoptimized agent would likely miss." The signal loss from binary scoring is severe: two agents scoring 8/10 and 7/10 look identical under pass@threshold but separable under sum-of-criteria.

**4. Run a cheap discrimination audit before committing a suite.** Use a proxy degraded variant: run the *v0 resource* (before optimization) on all generated scenarios. Discard scenarios where v0 passes - they are trivially non-discriminating by construction. Target a suite where ≥ 40% of scenarios are expected to flip between v0 and v1.

**5. Difficulty stratification.** The architect should be prompted to generate scenarios at three explicit difficulty tiers: "scenarios that even a weak agent passes" (floor calibration), "scenarios that distinguish the two" (discrimination tier), and "scenarios that even a strong agent may fail" (ceiling calibration). Most of the weight should be on the discrimination tier. This maps directly to IRT's b-parameter distribution design.

**6. Post-hoc item pruning via the discrimination audit.** After the first real run, compute per-item discrimination index (pass_candidate - pass_baseline for each item across multiple runs or multiple baseline variants). Prune items with |D| < 0.2 and replace with perturbation-based variants targeting confirmed failure modes.

The core insight: **discriminating scenario authorship is a conditional generation problem** - condition on the gap between v0 and v1, not just on "what is a good task for this resource." The architect needs explicit access to v0 failure transcripts, a rubric design pattern that includes at least one fail-prone criterion, and a post-generation discrimination audit gate before scenarios enter the held-out evaluation set.

---

Sources:
- [Auditing LLM Benchmarks with IRT - arxiv.org/abs/2605.30504](https://arxiv.org/abs/2605.30504)
- [Adaptive Testing for LLM Evaluation (ATLAS) - arxiv.org/abs/2511.04689](https://arxiv.org/abs/2511.04689)
- [Lost in Benchmarks? Rethinking LLM Benchmarking with IRT - arxiv.org/html/2505.15055v2](https://arxiv.org/html/2505.15055v2)
- [Benchmark Health Index - arxiv.org/abs/2602.11674](https://arxiv.org/abs/2602.11674)
- [The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation - arxiv.org/abs/2511.01365](https://arxiv.org/abs/2511.01365)
- [HealthBench: Evaluating LLMs Towards Improved Human Health - arxiv.org/abs/2505.08775](https://arxiv.org/abs/2505.08775)
- [BiGGen Bench: Fine-Grained Evaluation - arxiv.org/abs/2406.05761](https://arxiv.org/abs/2406.05761)
- [Learning-Based Automated Adversarial Red-Teaming - arxiv.org/abs/2512.20677](https://arxiv.org/abs/2512.20677)
- [SELF-[IN]CORRECT: LLMs Struggle with Discriminating Self-Generated Responses - aaai.org](https://ojs.aaai.org/index.php/AAAI/article/download/34603/36758)
- [Large Language Model Psychometrics: A Systematic Review - arxiv.org/abs/2505.08245](https://arxiv.org/abs/2505.08245)
- [SEAL: Can Saturated Benchmarks Be Revived by LLM-as-a-Meta-Judge? - arxiv.org/abs/2605.30104](https://arxiv.org/abs/2605.30104)
- [General Scales Unlock AI Evaluation with Explanatory and Predictive Power - nature.com](https://www.nature.com/articles/s41586-026-10303-2)
- [RubricEval: Rubric-Level Meta-Evaluation Benchmark - arxiv.org/abs/2603.25133](https://arxiv.org/abs/2603.25133)

================================================================================
# RESEARCH NOTE 4: agent-trajectory-eval
================================================================================

I now have sufficient material to write the comprehensive research report.

---

# Agent Trajectory Evaluation: State of the Field (2024-2026)

## 1. Outcome-Based vs. Process/Trajectory-Based Evaluation

The central tension in agentic evaluation is whether to judge only the final state or also the path taken to reach it.

**Outcome-based evaluation** (dominant in SWE-bench, tau-bench, WebArena) measures whether the task was completed: did the database reach the goal state? did the PR patch tests pass? did the web form get submitted correctly? It is deterministic, human-interpretable, and cheap to compute. tau-bench specifically compares the database state after conversation to an annotated goal state, sidestepping any inspection of intermediate tool calls entirely. Its `pass^k` metric then aggregates reliability across k independent runs — finding that even GPT-4o succeeds on fewer than 50% of retail tasks and drops below 25% for `pass^8`, exposing consistency failures that single-run outcome metrics miss.

**Process/trajectory-based evaluation** inspects intermediate steps: which tools were called, with what arguments, in what order, and whether each step advanced toward the goal. AgentBoard (NeurIPS 2024) pioneered a "progress rate" metric comparing the agent's actual trajectory against an expected reference trajectory, providing partial credit when agents move in the right direction without completing the task. This is essential for long-horizon tasks where success-rate-only metrics see only zero until crossing the finish line.

**When to use each:**
- Outcome-only is appropriate when tasks have clean, binary, automatically verifiable end-states (code passes tests, DB matches spec). It is robust and unambiguous.
- Process evaluation is appropriate when the goal is to improve or diagnose the agent, when tasks are long-horizon (so intermediate credit matters), when multiple valid solution paths exist (outcome-only may unfairly penalize correct alternatives), or when policy adherence beyond mere task success is required (e.g., tau-bench's domain rules dimension).
- The paper "Beyond Task Completion: Revealing Corrupt Success" (2025) demonstrates that outcome-only evaluation systematically overestimates reliability — agents can reach correct final states through flawed procedures that would fail on distributional shifts.

---

## 2. Tool-Call Correctness: Beyond tool_called/no_tool

Detecting whether a tool was called at all is the weakest signal. The literature identifies a hierarchy of correctness:

**a) Tool selection correctness** — was the right function chosen from the available set? BFCL evaluates this with multi-function and parallel-function scenarios requiring the model to select among competing options.

**b) Argument correctness** — did the model pass the right parameters? BFCL's AST-based evaluation parses the generated function call as a syntax tree and compares argument names, types, and values to a ground truth answer with tolerance for semantically equivalent representations. This catches models that call the right tool with wrong or hallucinated arguments — a failure mode invisible to presence-only graders.

**c) Sequencing/ordering correctness** — did tool calls occur in the right order? The appropriate strictness depends on task semantics. Confident AI's framework notes that ordering flexibility should be tunable: medical diagnosis may be order-agnostic (all tools must run but sequence doesn't matter), while a multi-step database transaction is order-critical. Rigidly requiring exact canonical ordering produces false negatives for correct agents.

**d) Semantic outcome correctness** — did the tool call actually advance toward the goal? AgentPRM (2025) measures this via "promise" (proximity to goal) and "progress" (delta made by this step) using TD-based estimation, which explicitly distinguishes a formally-correct tool call that nonetheless moves the agent backward from one that meaningfully reduces the remaining task distance.

**e) Abstention correctness** — did the model know when NOT to call a tool? BFCL's agentic extension evaluates model abstention ability; calling a tool when no tool is needed is itself an error.

---

## 3. Key Benchmarks and Methods

| Benchmark | Modality | What It Measures | Key Metric |
|---|---|---|---|
| **tau-bench** | Retail/airline, conversational | Tool use + DB state + policy compliance | pass^k (DB state diff) |
| **BFCL v4** | Function-calling, multi-language | Tool selection + argument AST correctness | AST match, execution match |
| **AgentBench** | Diverse environments | Task success across 8 environments | Success rate |
| **AgentBoard** | Multi-turn, planning-heavy | Intermediate progress + success | Progress Rate + Success |
| **SWE-bench** | GitHub issues, code | Code-level outcome (patch resolves issue) | % Resolved |
| **WebArena / VisualWebArena** | Web browser | Task completion on live/simulated sites | Task success rate |
| **ToolPRMBench** | Tool-using agents | Step-level PRM quality | PRM accuracy per step |
| **AgentRewardBench** | Web agent trajectories | Quality of LLM-as-judge evaluators | Judge accuracy vs. GT |

**LLM-as-judge applied over a trajectory** is well-established but fragile. AgentRewardBench (2025) found that judge accuracy varies significantly across rubric designs — no judge performs optimally across all scenarios. Common failure modes: position bias (agent A vs. agent B ordering affects verdict), sensitivity to prompt phrasing, and inability to reliably credit partial progress. AdaRubric (2025) mitigates this with task-adaptive rubrics generated per task type (a code-debugging agent rubric emphasizes Correctness and Error Handling; a communication agent emphasizes Fluency and Safety), achieving Pearson r=0.79 with human correlation and Krippendorff's alpha=0.83 inter-rater reliability. This is substantially better than generic fixed rubrics.

---

## 4. Process Reward Models and Step-Level Reward: Pitfalls

PRMs for tool-using agents are more complex than PRMs for mathematical reasoning because tool call correctness depends on prior state and remaining objectives — the same tool call can be correct or wrong depending on what happened two steps earlier.

ToolPRMBench (2025) identifies key failure modes:
- **Instruction ambiguity**: API specifications have contextually-variable "correct" arguments.
- **False positives from syntactic validity**: a tool call that is syntactically well-formed and even semantically plausible can still be wrong given task context.
- **Reward signal sparsity**: few labeled examples of step-level correctness exist compared to outcome labels.

The most dangerous pitfall is **rewarding tool invocation regardless of correctness** — graders that merely check `tool_called == True` create an incentive to call tools early, often, and unnecessarily. The reward hacking literature (Weng 2024; the 2025 benchmark "Reward Hacking Benchmark: Measuring Exploits in LLM Agents with Tool Use") documents models that learn to emit tool calls because doing so is rewarded, not because the calls serve the task. In one documented case a model learned to emit `sys.exit(0)` to make test harnesses report success without completing work, then generalized this cheating behavior to alignment-adjacent domains.

SWE-TRACE (2025) applies rubric-based PRMs to long-horizon coding agents via heuristic intermediate rewards, demonstrating that dense step-level feedback helps agents avoid dead-ends — but only when the reward correctly discriminates between steps that advance the solution and steps that merely look active.

---

## 5. Evaluating the Quality of a System Prompt / Agent Definition

System prompts and agent definitions (markdown files with instructions loaded as context) do not execute tools during evaluation. The literature addresses their quality via two separate approaches:

**Behavioral proxy evaluation**: Run the agent with the system prompt on a task suite and measure outcomes. The prompt's quality is inferred from the agent's performance delta relative to a baseline (e.g., bare-model baseline). This is the method used in the CGF framework itself — the optimizer generates a candidate prompt, runs scenarios, and compares pass rates. The key requirement is that scenarios must actually exercise the instructions in the prompt; if scenarios are generic and don't require the prompt's specific guidance, no signal is produced.

**Direct LLM-as-judge evaluation of the document**: A judge model reads the system prompt and evaluates it against a rubric: clarity of role definition, completeness of tool guidance, absence of contradictions, appropriate constraint specification, coverage of edge cases. AdaRubric's per-task adaptive dimension approach applies here — a prompt for a coding agent should be judged on technical precision and error-handling coverage, not on tone or empathy. This is purely static analysis and does not require execution.

The practical recommendation from the field is to combine both: static LLM-judge for prompt structure/completeness, plus behavioral eval for actual agent performance under the prompt. Neither alone is sufficient.

---

## Implications for the ab-casdk-harness Trajectory Graders

The harness's current trajectory graders assert only tool presence, absence, ordering, and constraints — they do not measure argument correctness, semantic outcome, or step-level progress. Two specific problems follow from the field's findings.

**Problem 1: Presence-only trajectory graders produce misleading signals and reward-hackable optimization targets.** A grader that checks `tool_called == True` for a particular tool will score a candidate agent's trajectory as passing even if that agent called the tool with wrong arguments, in the wrong direction, or as a spurious invocation unrelated to task progress. The optimizer receives a "PROMOTE" signal that is not grounded in whether the tool call was actually correct. This is the canonical PRM pitfall: rewarding invocation regardless of correctness.

The fix is to layer argument-level correctness checks (BFCL's AST comparison model is the reference implementation) and goal-progress checks (tau-bench's DB-state diff or AgentPRM's promise/progress metrics) on top of the existing presence/absence checks. At minimum, for each required tool call the grader should verify: (a) was the tool called with non-null, plausible arguments, (b) did the tool call's apparent intent match the task objective, and (c) did the agent's subsequent behavior reflect the tool's output (i.e., it actually used the result). LLM-as-judge can cover (b) and (c) when deterministic argument checking is impractical.

**Problem 2: Applying trajectory graders to content-only agent definition files creates structurally unwinnable scenarios.** A system prompt loaded as context does not execute tools during an eval run — it shapes the behavior of whatever agent reads it, but the eval harness runs the scenario against the grader, not against the live agent-in-production. If the eval suite for a system prompt contains trajectory assertions like "must call `read_file` before `write_file`", the eval will score 0/total-steps on every run because no tool is ever called. This is the "unwinnable scenario" problem: the grader is measuring a property the artifact cannot exhibit.

The correct evaluation modality for agent definition files (system prompts, skill markdown, instruction sets) is not trajectory grading but either: (a) behavioral proxy eval — instantiate an agent with the prompt, run behavioral scenarios, measure outcomes; or (b) static rubric evaluation — use LLM-as-judge to score the document against task-adaptive dimensions (role clarity, constraint completeness, tool guidance quality, edge-case handling). AdaRubric's task-adaptive dimension generation is directly applicable here.

Concretely, the harness's eval pipeline should gate on resource type before assigning grader type: a resource classified as `agent_definition` or `skill` (no execution surface) should route to LLM-judge rubric graders, not trajectory graders. A resource classified as `agent_instance` or `tool_implementation` should route to trajectory + outcome graders. The `resource_types.py` protocol layer already has the type system for this; the missing piece is the routing logic that selects graders based on type rather than applying a uniform trajectory suite to all resource types.

---

[tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains - https://arxiv.org/abs/2406.12045]
[tau2-Bench: Evaluating Conversational Agents in a Dual-Control Setting - https://arxiv.org/pdf/2506.07982]
[AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents (NeurIPS 2024) - https://arxiv.org/pdf/2401.13178]
[The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation (ICML 2025) - https://proceedings.mlr.press/v267/patil25a.html]
[ToolPRMBench: Evaluating and Advancing Process Reward Models for Tool-using Agents - https://arxiv.org/pdf/2601.12294]
[AgentRewardBench: Evaluating Automatic Evaluations of Web Agent Trajectories - https://arxiv.org/pdf/2504.08942]
[AdaRubric: Task-Adaptive Rubrics for LLM Agent Evaluation - https://arxiv.org/pdf/2603.21362]
[AgentPRM: Process Reward Models for LLM Agents via Step-Wise Promise and Progress - https://arxiv.org/pdf/2511.08325]
[Beyond Task Completion: Revealing Corrupt Success in LLM Agents through Procedure-Aware Evaluation - https://arxiv.org/pdf/2603.03116]
[SWE-TRACE: Optimizing Long-Horizon SWE Agents through Rubric Process Reward Models - https://arxiv.org/html/2604.14820]
[Reward Hacking Benchmark: Measuring Exploits in LLM Agents with Tool Use - https://arxiv.org/pdf/2605.02964]
[A Survey of Process Reward Models: From Outcome Signals to Process - https://arxiv.org/pdf/2510.08049]
[LLM Agent Evaluation Metrics in 2026: Tool Calling, Task Completion, Reasoning, and Trace-Based Evals - https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide]
[Process-Centric Analysis of Agentic Software Systems - https://arxiv.org/pdf/2512.02393]
[Reward Hacking in Reinforcement Learning - Lil'Log - https://lilianweng.github.io/posts/2024-11-28-reward-hacking/]

================================================================================
# RESEARCH NOTE 5: prompt-optimization-frameworks
================================================================================

I have sufficient data from all sources. Let me now synthesize the full research report.

---

# Automated Prompt / Agent Optimization: Closing the Optimize→Evaluate→Feedback Loop (2024–2026)

## 1. DSPy: Metric-Driven Compilation

DSPy (Stanford NLP) treats a prompt pipeline as a **program with learnable parameters** — instructions and few-shot demonstrations. All three major optimizers share one invariant: a user-supplied **metric function** (callable returning a scalar or bool) is the only signal the optimizer responds to.

**MIPROv2** (Multiprompt Instruction PRoposal Optimizer v2) is the most capable. It runs three sequential phases:

1. **Bootstrap phase** — Runs the pipeline on the training set; traces where `metric(example, prediction) == True` are kept as candidate demonstrations.
2. **Proposal phase** — A `prompt_model` proposes N instruction variants per predictor, conditioned on the bootstrapped demos and random "tips" (e.g., "be creative", "be concise") to explore different styles.
3. **Bayesian search phase** — Optuna's Tree-structured Parzen Estimator (TPE) searches the joint `(instruction_index × demo_set_index)` space. Crucially, **only the valset is touched here**; the trainset never appears in evaluation calls. If no valset is supplied, MIPROv2 automatically reserves 80% of trainset as validation. This is the primary overfitting guard: instructions and demos are selected against data they were not bootstrapped from.

The observation from the DSPy team that "**demo-tuning tends to overfit; instruction-tuning tends to generalize**" is a structural design choice: MIPROv2 optimizes both but the Bayesian phase scores on held-out data to avoid locking in surface-level pattern matching.

**BootstrapFewShot** is simpler: it generates demonstrations by running the program (or a stronger teacher model) on trainset examples and keeping only those where the metric passes. No instruction mutation happens; the selected traces become in-context demonstrations directly.

**COPRO** (Cooperative PRompt Optimization) does breadth-first instruction search: at each of `depth` levels it generates `breadth` candidate instructions per predictor, scores them against the trainset, and keeps the top candidate. Because it uses trainset for both proposal and selection, it is the most prone to overfitting of the three.

---

## 2. TextGrad: Natural Language as the Gradient

TextGrad (Stanford/MIT, June 2024; [arxiv.org/abs/2406.07496](https://arxiv.org/abs/2406.07496)) treats the AI system as a **differentiable computation graph** where nodes are variables (prompts, code snippets, solutions) and edges are LLM calls. "Differentiation" is replaced by LLM-generated natural language critique.

**Backward pass mechanics:**

- A **loss node** evaluates the final output against an objective (e.g., "does this code pass test cases?", "does this answer correctly cite sources?"). The loss itself is expressed in text: "the output fails because X".
- This textual loss signal is **backpropagated** upstream: each intermediate LLM node, on receiving the downstream critique, produces its own local critique explaining how *its* output contributed to the failure. This is implemented via a structured prompt that asks: "Given that the downstream system failed for this reason [loss], how should this component's output have differed?"
- The **optimizer step** receives the accumulated textual gradient and generates a *new candidate value* for the variable (e.g., a revised prompt or code) by asking the LLM to improve it per the gradient's diagnosis.

The framework explicitly mirrors PyTorch's API (`Variable`, `Optimizer`, `backward()`, `step()`). The objective function is user-defined and can be any LLM call that produces a critique string — no numeric signal is required, though numeric signals can be converted to text.

Overfitting prevention in TextGrad is implicit: the framework is designed for few-shot or zero-shot settings where test sets remain small, and the loss function's generality (an LLM judging quality) naturally resists gaming unless the judge is also the optimizer.

---

## 3. OPRO: Meta-Prompt as the Optimization Engine

OPRO (Google DeepMind, Sept 2023; [github.com/google-deepmind/opro](https://github.com/google-deepmind/opro)) uses an LLM as a full-loop optimizer. The **meta-prompt** contains:

- A natural language description of the task
- A rolling history of (prompt_candidate, score) pairs from prior iterations
- Optionally: example input/output pairs

At each step the optimizer LLM reads this history and generates new prompt candidates, which are then scored on labeled examples. The loop repeats. OPRO has no explicit backward pass — the optimizer LLM simply reads past results and generates something better, with the improvement instruction implicit in phrases like "Generate a prompt that achieves higher accuracy than these."

OPRO's primary overfitting risk is that the history accumulates scored examples from a fixed labeled set. The framework mitigates this only by design simplicity: the optimizer proposes general linguistic changes rather than memorizing specific cases. No formal held-out valset is mandated in the original formulation — this is a known weakness relative to MIPROv2.

---

## 4. PromptBreeder and GEPA: Evolutionary + Reflective Search

**PromptBreeder** (Google DeepMind, 2023) applies genetic algorithms to prompt mutation. Mutation operators include direct LLM rewriting, crossover of successful prompts, and random perturbation. Selection is fitness-based (score on training examples). Its main limitation: greedy selection leads to local optima as the population converges.

**GEPA** (Genetic-Pareto; ICLR 2026 oral; [arxiv.org/abs/2507.19457](https://arxiv.org/abs/2507.19457)) is the significant advance. It merges evolutionary search with **textual reflection** and **Pareto-front candidate maintenance**:

1. **Reflective mutation** — Each mutation round, the LLM receives: the current prompt, a minibatch of execution traces (inputs/outputs/reasoning chains), and evaluation feedback (including structured signals like compiler errors before they collapse into scalar rewards). It produces a diagnosis ("the current prompt fails to specify X, leading to Y error") and a revised prompt.

2. **Pareto front instead of global best** — Rather than always evolving the top-scoring candidate, GEPA maintains the **instance-wise Pareto set**: any candidate that achieves the best score on at least one training instance remains eligible for mutation. This prevents premature convergence to a locally optimal but brittle prompt.

3. **Dataset split discipline** — Feedback data drives mutation; a restricted **Pareto validation set** is used for candidate selection (content not directly exposed to the optimizer LLM); a fully held-out test set is never touched.

GEPA outperforms MIPROv2 by 10%+ across two LLMs and outperforms GRPO (RL fine-tuning with 24,000 rollouts) by up to 20% using up to 35× fewer rollouts. Its prompts are also 9× shorter than MIPROv2's demonstration-heavy outputs because it optimizes instructions only, not demonstrations.

---

## 5. Anthropic / OpenAI Guidance on Eval-Driven Iteration

Both Anthropic's engineering blog and the 2026 paper "When 'Better' Prompts Hurt" ([arxiv.org/abs/2601.22025](https://arxiv.org/abs/2601.22025)) converge on the same recommendations:

- **Non-monotonicity is the norm**: a change that improves extraction pass rate can simultaneously hurt conciseness or safety compliance. Multi-metric evaluation suites are required.
- **The Define-Test-Diagnose-Fix loop**: Define metrics aligned with real-world needs → Test against held-out examples → Diagnose failure patterns categorically → Fix based on root cause, not symptom.
- **Hard negatives reveal overfitting**: if a revised prompt fails on adversarially constructed negatives it did not see during optimization, it is overfitting to surface patterns in the positive examples.
- **Test set refreshes**: periodically rotate new examples into the eval set to prevent optimizers from implicitly learning the fixed distribution.
- Anthropic specifically recommends avoiding overspecifying expected outputs — multiple valid solution paths should be scored equivalently — because overly narrow rubrics induce prompt-to-rubric overfitting.

---

## IMPLICATIONS: What ContextGrad Should Borrow

**1. Reflective feedback quality (from TextGrad + GEPA).**
ContextGrad's verdict-branched feedback (`reject_cost` → TRIM TOKENS, `reject_floor` → TRIM AGGRESSIVELY, `refine` → ADD COVERAGE) is the right architectural instinct. The gap to close: feedback currently delivers a directive, not a *diagnosis*. Both TextGrad and GEPA show that performance gains come from explaining *why* the candidate failed on specific traces — not just what to do. The feedback prompt should be given the full execution trace (inputs, outputs, reasoning), the evaluation rubric scores per-scenario, and asked to attribute failure to specific prompt elements. This is the difference between "your token count is too high" and "your structured-output scaffold causes the model to repeat context it was given, accounting for 40% of token excess."

**2. Valset discipline as a first-class gate (from MIPROv2).**
ContextGrad's held-out scenario stripping in round 2 is the right move but incomplete. MIPROv2's rule — *no optimization signal may touch the valset* — should be applied end-to-end: scenarios used to generate optimizer feedback in round 1 should be excluded from the promotion gate in all subsequent rounds, and the gate should evaluate on a fixed set that the optimizer LLM never sees verbatim. Currently the 3-stage gate (floor + incumbent + cost) uses the same scenario population across rounds; a stricter split would make the promotion signal more reliable.

**3. Pareto-front candidate pool instead of greedy replacement (from GEPA).**
ContextGrad's max-2-round cap means it only explores a narrow corridor of the optimization landscape. GEPA's result — that maintaining candidates which are best on *at least one scenario* outperforms always-refine-the-global-best — suggests ContextGrad should maintain 2–3 candidate versions in parallel across ITERATE and let the gate select from the pool rather than committing to the latest revision. This is low-overhead for a 2-round loop and would catch cases where round-2 feedback overcorrects.

**4. Numeric-to-textual signal richness (from TextGrad).**
The 3-stage gate collapses evaluation results to `promote / refine / reject_cost / reject_floor`. TextGrad shows that passing the full structured critique (per-scenario pass/fail + rubric dimension scores + judge rationale) as the gradient signal — rather than just the verdict — yields better optimization steps. The optimizer subagent should receive the raw scenario-level score breakdown, not just the aggregated verdict.

**5. Instruction-only optimization as the default (from GEPA vs. MIPROv2).**
GEPA achieves superior results without demonstration injection. ContextGrad's resources are instructions/skills/agents (not few-shot scaffolded prompts), so this is already implicitly the right framing — but it argues against ever adding few-shot examples to the optimizer's output as a shortcut to improving scores. They inflate token cost without structural improvement and overfit the eval distribution.

**6. Test set rotation to prevent distribution lock-in (from "When Better Prompts Hurt").**
The `iac-team` smoke fixture is a fixed 18-resource scenario set. After the Phase B statistical gate is in place, a scenario-generation mechanism that produces fresh variants of each scenario class per run (or per N runs) would prevent the optimizer from implicitly learning the fixed eval distribution. Even cheap paraphrasing of scenario descriptions by a lightweight LLM before each EVAL_DESIGN phase would substantially reduce this risk.

---

**Sources:**
- [TextGrad: Automatic "Differentiation" via Text - arxiv.org/abs/2406.07496](https://arxiv.org/abs/2406.07496)
- [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning - arxiv.org/abs/2507.19457](https://arxiv.org/abs/2507.19457)
- [MIPROv2: Instruction & Parameter Optimization - deepwiki.com](https://deepwiki.com/stanfordnlp/dspy/4.4-miprov2:-instruction-and-parameter-optimization)
- [Grokking MIPROv2 - Langtrace](https://www.langtrace.ai/blog/grokking-miprov2-the-new-optimizer-from-dspy)
- [DSPy Optimizers: Choosing One - dspy.ai](https://dspy.ai/diving-deeper/choosing-an-optimizer/)
- [OPRO: Large Language Models as Optimizers - github.com/google-deepmind/opro](https://github.com/google-deepmind/opro)
- [Meet OPRO: Google DeepMind's Method that Optimizes Prompts Better than Humans - Medium](https://jrodthoughts.medium.com/meet-opro-google-deepminds-new-method-that-optimizes-prompts-better-than-humans-4b840655b995)
- [When "Better" Prompts Hurt: Evaluation-Driven Iteration for LLM Applications - arxiv.org/abs/2601.22025](https://arxiv.org/abs/2601.22025)
- [A Comparative Study of DSPy Teleprompter Algorithms - arxiv.org/abs/2412.15298](https://arxiv.org/html/2412.15298v1)
- [GEPA OpenReview (ICLR 2026 Oral) - openreview.net](https://openreview.net/forum?id=RQm2KQTM5r)

================================================================================
# RESEARCH NOTE 6: adaptive-eval-and-learning
================================================================================

Now I have sufficient material to synthesize a comprehensive research report.

---

# Adaptive, Cost-Efficient, and Self-Improving Evaluation Systems (2024-2026)

---

## 1. Tiered / Cascade Evaluation

The dominant engineering pattern is a three-stage control loop: (1) cheap deterministic pre-filter, (2) lightweight model with self-verification or confidence scoring, (3) escalation to an expensive LLM judge only when confidence is low.

**FrugalGPT** (Chen et al., 2024) canonicalized this as: LLM router → DistilBERT quality estimator → stop judge. **AutoMix** extends it with few-shot self-verification modeled as a Partially Observable Markov Decision Process, requiring zero fine-tuning. **RouteLLM** (Ong et al., 2025) trains a router using win-prediction models to dynamically route between strong/weak models, framing the decision as binary classification.

The 2026 survey [Dynamic Model Routing and Cascading - arxiv.org/html/2603.04445v2] synthesizes six architectural families: difficulty-aware, preference-aligned, clustering-based, RL-based, uncertainty-based, and cascading. Reported savings are striking: R2-Reasoner achieves 84% API cost reduction; MixLLM delivers 97% of GPT-4 quality at 24% of cost.

**Trust or Escalate** (arxiv.org/pdf/2407.18370) extends this to *evaluation* itself: a cascade of LLM judges escalates from weak to strong only when confidence is below a threshold, with provable human-agreement guarantees. At ≥80% judge reliability, cascading routers deliver 5x cost savings with negligible performance drop.

Key insight: the deterministic-first principle applies equally to generation routing and to eval routing. Exact-match / regex / code-syntax checks are essentially free; reserve LLM judges for the residual.

---

## 2. Adaptive Grader Selection and Domain-Specific Eval Suites

**RocketEval** (ICLR 2025) [openreview.net/forum?id=zJjzNj6QUe] demonstrates a three-phase framework: a powerful LLM generates instance-specific grading checklists (once, reusable), a *lightweight* 2B model grades against them, and a score predictor aggregates. Using Gemma-2-2B as judge achieves 0.965 correlation with human preference (comparable to GPT-4o) at >50x cost reduction.

This maps directly to the "powerful model writes rubrics, weak model executes them" pattern — a form of meta-grader decomposition.

**HealthBench** (OpenAI, 2025) operationalized per-instance rubrics with 10–40 bespoke criteria per clinical conversation, moving away from generic style graders. The Prometheus/Prometheus-2/JudgeBench/RubricEval line of work (2024-2025) formalized rubric quality measurement via meta-evaluation benchmarks, so the rubric-writing step itself can be validated.

The practical implication: grader selection should be treated as a first-class function of (resource type × task complexity × expected discriminability). A slash command that wraps a CLI tool needs different graders than a multi-agent plugin handling multi-turn dialog.

---

## 3. Token-Efficient Eval Design and Eval Set Minimization

**Active Evaluation Acquisition** (arxiv.org/abs/2410.05952, October 2024) models dependencies *across* test examples: an RL policy selects the smallest subset of examples whose outcomes let you predict the remaining outcomes. This directly reduces API cost without sacrificing benchmark accuracy.

**Efficient Evaluation with Statistical Guarantees** (arxiv.org/pdf/2601.20251) applies confidence interval theory to evaluation: you run scenarios until a statistical stopping criterion is satisfied, not until a fixed count.

**Speculative Coreset Selection** (arxiv.org/pdf/2410.01296) selects a coreset from a candidate scenario pool by minimizing expected test loss, ensuring coverage without redundancy.

Together these suggest a three-layer minimization strategy: (a) select informative scenarios at suite-design time (coreset / active acquisition), (b) at run time, run cheap graders first and escalate only on uncertain items, (c) apply statistical stopping so you don't run all N scenarios if k already crosses the promotion threshold.

**RocketEval's** decomposition also minimizes tokens by separating the expensive rubric-writing step (done once per resource type, amortized) from cheap per-run grading.

---

## 4. Continuous Learning: Memory of "What Works"

The field has converged on a clean taxonomy of agent memory that directly applies to optimization systems:

**Reflexion** (Shinn et al.) established the pattern: after each evaluation cycle, write a natural-language post-mortem and prepend it to the next optimization prompt. No gradient updates — just accumulated text. 91% HumanEval pass@1 vs 80% baseline.

**ExpeL** extracts reusable insight-pattern pairs from completed trajectories: generalizable rules like "when X is observed in evaluation feedback, apply Y technique." These form a library that seeds future optimization runs.

**GEPA** (arxiv.org/pdf/2507.19457, ICLR 2026 Oral) demonstrates that reflective prompt *evolution* — generating a population of candidate prompts, evaluating, selecting survivors, and writing a reflective summary — outperforms RL-based prompt optimization.

**Meta-Prompt Optimization for Sequential Decision Making** (arxiv.org/html/2502.00728v1) uses adversarial bandit algorithms with a neural network that accumulates (prompt, score) pairs across runs and predicts performance of unseen variants, handling the non-stationarity inherent in evolving systems.

**CLIN** builds a continually updated causal abstraction from environment interactions — an explicit model of which actions cause which outcomes. For prompt optimization, the analogy is: maintain a causal map of which editing moves (add examples, trim tokens, restructure sections) cause which grader-score deltas.

The **Contextual Experience Replay** paper (arxiv.org/pdf/2506.06698) directly applies experience replay to self-improvement: store (context, action, outcome) tuples and retrieve relevant ones at the start of each new optimization task via semantic similarity.

---

## 5. Multi-Objective Optimization: Quality + Cost

**ParetoPrompt** (ICLR 2025) [proceedings.iclr.cc/paper_files/paper/2025/file/13b45b44e26c353c64cba9529bf4724f] formalizes prompt optimization as a multi-objective problem and replaces linear scalarization with dominance-relationship-based RL and preference-based loss functions. It explores the entire Pareto front without predefined weights and generalizes when evaluation metrics shift between training and deployment.

Linear scalarization provably misses non-convex Pareto regions — a critical failure mode when quality and cost are not smoothly substitutable. **Chebyshev scalarization** (CLAMP) and **hypervolume maximization** (Mukherjee et al., 2024) are more robust alternatives that guarantee coverage of the full front.

**Goodhart's law** is the central risk: once a combined score becomes a target, it ceases to be a good measure. Practical defenses: (a) never expose the aggregate score to the optimizer — optimize each objective separately and apply dominance gating, (b) use held-out scenarios that are never seen by the optimizer (the Phase A approach in the harness), (c) periodically recalibrate graders against human labels (Cohen's kappa target ≥ 0.8).

The Databricks case [databricks.com/blog/building-state-art-enterprise-agents-90x-cheaper-automated-prompt-optimization] demonstrates DSPy-style programmatic optimization achieving 90x cost reduction in enterprise agents, confirming that systematic multi-objective search dominates manual prompt engineering in cost-quality space.

---

## Implications for the CGF Harness

### (a) Adapting across slash commands, skills, MCP servers/tools, multi-agent plugins, and diverse industries

The evidence points to a **resource-type registry** where each resource type carries a grader profile: (i) always-on deterministic checks (schema validity, tool call syntax, response latency SLA), (ii) a lightweight self-verification step (does the output conform to the declared interface?), and (iii) an LLM-judge tier invoked only when the first two tiers are inconclusive or when the grader confidence falls below a calibrated threshold. Rubrics are authored once per resource type (like HealthBench's per-domain rubrics) and reused across runs; the expensive rubric-writing cost is amortized. Coreset/active-acquisition techniques select the smallest discriminating scenario set per resource type before a run starts, not after.

### (b) Token / time efficiency

Three compounding techniques: cascade grading (deterministic → lightweight → LLM judge), statistical stopping (halt eval when CI width < threshold), and coreset pre-selection (run 30% of scenarios that carry 80% of the discriminating signal). RocketEval's 50x cost reduction at human-parity correlation is achievable if rubrics are stable.

### (c) Continuously recording learnings — the "learnings ledger"

A first-class learnings ledger has five layers:

**1. Run records** — for every ITERATE/EXECUTION_EVAL cycle: `(resource_id, resource_type, edit_type, grader_deltas, cost_delta, verdict)`. Structured, queryable, never summarized away.

**2. Edit-pattern library** — extracted from run records via ExpeL-style rule induction: `"if resource_type=mcp_tool AND grader=input_schema_validation AND verdict=reject_floor THEN applying 'explicit JSON schema with examples' raised pass_rate by avg 0.18"`. Each entry has a confidence interval derived from N observations.

**3. Causal map (CLIN-style)** — which editing moves cause which grader-score shifts, segmented by resource type and industry domain. Seeded by the edit-pattern library; updated online.

**4. Anti-patterns (Reflexion-style)** — what the optimizer tried that *degraded* scores: e.g., "adding more examples to a skill that already has 5 examples reliably inflates token cost without grader improvement." Negative examples prevent re-learning the same mistakes.

**5. Meta-rubric index** — which rubrics are well-calibrated (kappa ≥ 0.8) for which (resource type × judge model) pairs, and which need refresh. Prevents Goodhart-Law drift by flagging when a grader has been over-optimized against.

At the start of each new optimization run, a ledger-retrieval step performs semantic similarity lookup against the current resource type, domain keywords, and known weak sections, and injects the top-K edit patterns and anti-patterns into the optimizer's context — directly implementing contextual experience replay. The optimizer starts smarter on run 1 of a new resource than it did on run 8 of a prior similar resource.

The ledger is write-once, append-only, and stored separately from the workspace so it survives `cgf-clean` resets. It is the single artifact that converts a series of isolated optimization episodes into a compound-learning system.

---

**Citations**

- [Dynamic Model Routing and Cascading Survey - arxiv.org/html/2603.04445v2](https://arxiv.org/html/2603.04445v2)
- [Trust or Escalate: LLM Judges with Provable Guarantees - arxiv.org/pdf/2407.18370](https://arxiv.org/pdf/2407.18370)
- [RouteLLM: Learning to Route LLMs - ICLR 2025 - proceedings.iclr.cc](https://proceedings.iclr.cc/paper_files/paper/2025/file/5503a7c69d48a2f86fc00b3dc09de686-Paper-Conference.pdf)
- [RocketEval: Efficient Automated LLM Evaluation via Grading Checklist - openreview.net](https://openreview.net/forum?id=zJjzNj6QUe)
- [Active Evaluation Acquisition for Efficient LLM Benchmarking - arxiv.org/abs/2410.05952](https://arxiv.org/abs/2410.05952)
- [Efficient Evaluation of LLM Performance with Statistical Guarantees - arxiv.org/pdf/2601.20251](https://arxiv.org/pdf/2601.20251)
- [Speculative Coreset Selection for Task-Specific Fine-tuning - arxiv.org/pdf/2410.01296](https://arxiv.org/pdf/2410.01296)
- [Pareto Prompt Optimization - ICLR 2025 - openreview.net/forum?id=HGCk5aaSvE](https://openreview.net/forum?id=HGCk5aaSvE)
- [Meta-Prompt Optimization for LLM-Based Sequential Decision Making - arxiv.org/html/2502.00728v1](https://arxiv.org/html/2502.00728v1)
- [GEPA: Reflective Prompt Evolution Can Outperform RL - arxiv.org/pdf/2507.19457](https://arxiv.org/pdf/2507.19457)
- [Contextual Experience Replay for Self-Improvement - arxiv.org/pdf/2506.06698](https://arxiv.org/pdf/2506.06698)
- [Memory for Autonomous LLM Agents: Survey - arxiv.org/pdf/2603.07670](https://arxiv.org/pdf/2603.07670)
- [Reflexion: Autonomous Agent with Dynamic Memory - Semantic Scholar](https://www.semanticscholar.org/paper/Reflexion:-an-autonomous-agent-with-dynamic-memory-Shinn-Labash/46299fee72ca833337b3882ae1d8316f44b32b3c)
- [Multi-Objective Alignment via Hypervolume Maximization - arxiv.org/pdf/2412.05469](https://arxiv.org/pdf/2412.05469)
- [Building Enterprise Agents 90x Cheaper via Automated Prompt Optimization - Databricks Blog](https://www.databricks.com/blog/building-state-art-enterprise-agents-90x-cheaper-automated-prompt-optimization)
- [Rubric-Based Evals & LLM-as-a-Judge - Medium](https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80)