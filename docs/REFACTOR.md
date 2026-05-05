# Harness Reorganization & Forward Plan

## Status

This document originally tracked a multi-block reorganization of the harness
(branch surgery, plugin loader modernization, observability stack). **As of
2026-05-05 all four reorganization blocks are complete and merged to `main`.**
The document now serves two purposes:

1. **Look back** — a compact record of what shipped, with pointers to the PRs
   and commits that hold the detail.
2. **Look forward** — the plan for the next major work item, **Stage 3 (Eval
   Harness)**, which is the original purpose of `contextgrad-framework`.

---

## Anthropic-canonical references

Two published Anthropic implementations match this harness's shape and remain
useful as design north stars:

- **`anthropics/claude-agent-sdk-demos/research-agent`** — closest analog for
  programmatic resource loading. Uses `ClaudeAgentOptions(setting_sources=["project"], agents={...}, hooks={...})`
  directly with no custom plugin loader.
- **`anthropics/claude-cookbooks/claude_agent_sdk/chief_of_staff_agent`** —
  closest analog for filesystem-based discovery. Uses `.claude/agents/`,
  `.claude/commands/`, `.claude/hooks/`, `.claude/output-styles/` directly.

Plugin distribution follows `anthropics/claude-plugins-official` and
`anthropics/skills` (both ship `.claude-plugin/marketplace.json`). Hosting
patterns follow the [Anthropic Hosting Guide](https://code.claude.com/docs/en/agent-sdk/hosting).

**Future-state option:** Anthropic's overview suggests prototyping with the
Agent SDK and migrating to [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview)
for long-running asynchronous sessions. Not a near-term migration, but worth
keeping in mind as the harness scales beyond what self-hosted infra can support.

---

## What shipped (chronological)

Execution happened in four "Blocks" rather than the Part/Phase taxonomy this
doc was originally drafted in. CLAUDE.md and MEMORY.md track the Block
terminology; this section is the canonical map.

| Block | Date | Scope | Promotion |
|---|---|---|---|
| **Block 1** | 2026-05-01/02 | Branch reorganization: 73 commits of Stage 1+2 CGF work + multi-resource pipeline promoted from `contextgrad-framework` to `main`; branch reset off the new main. | [PR #1](https://github.com/andisab/casdk-harness/pull/1) |
| **Block 2** | 2026-05-04 | SDK bump (`>=0.1.72`); filesystem agent discovery via `.claude/agents/`; hook event SDK-canonical names; `direct_agent.py` → `subagent.py` rename + slim. | [PR #2](https://github.com/andisab/casdk-harness/pull/2) |
| **Block 3** | 2026-05-04/05 | Plugin pipeline modernization: marketplace adoption (research-team, context-engineering); `plugin_manager.py` collapsed to discovery + namespacing; `commands.py` and `hooks.py` deleted; SDK upstream investigation closed (no issues filed). | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |
| **Block 4** | 2026-05-05 | Observability: OTel Collector sidecar bridging SDK telemetry into Prometheus; harness metrics renamed `harness_*`; SDK-duplicate counters dropped; two pre-provisioned Grafana dashboards; AlertManager + alert rules wired (rules had been dead since project start). New `docs/OBSERVABILITY.md`. | [PR #3](https://github.com/andisab/casdk-harness/pull/3) |

Block 3 and Block 4 shipped together in PR #3 because both were authored on
`contextgrad-framework` after Block 2's promotion.

For phase-level detail, see:
- Commit messages on each Block's promotion PR (no-squash merges preserve every phase SHA on `main`).
- `CLAUDE.md` "Completed Recently" section.
- `~/.claude/projects/-Users-andisblukis-Projects-ab-github-ab-casdk-harness/memory/MEMORY.md` "Recent Work" section.

---

## CGF Stage status

The "Stage" taxonomy tracks the CGF (ContextGrad Framework) feature surface,
independent of the Block taxonomy used for reorganization work.

| Stage | Status | Where |
|---|---|---|
| **Stage 1 — Protocol layer + resource architect + DESIGN phase** | shipped | `main`, via Block 1 |
| **Stage 2 — MCP tool/server creation skills + Python/TypeScript scaffolds** | shipped | `main`, via Block 1 |
| **Stage 3 — Evaluation Framework** | **not started** | `contextgrad-framework` (slim, off `main`) |
| **Stage 4 — Integration & hardening** | not started; depends on Stage 3 | `contextgrad-framework` |

The multi-resource orchestrator state machine `PLANNING → RESEARCH → DESIGN →
GENERATE → ITERATE → VALIDATE` is fully wired and tested end-to-end. Two
phases exist in the `OptimizationPhase` enum but are not yet wired into the
orchestrator: `EVAL_DESIGN` and `EXECUTION_EVAL` — those are Stage 3's job.

---

## Next: Stage 3 — Eval Harness

Branch: `contextgrad-framework` (currently equal to `main`).

Reference spec: `docs/CGF-EVAL-FRAMEWORK.md` (draft).

### Goals

1. **`cgf-eval-architect` agent** — generates eval suites from resource specs
   (the same SPEC.md that drives optimization). Output: structured eval
   manifest (testcases, expected behaviors, grading rubrics).
2. **Grader infrastructure** — three tiers, escalating in cost and richness:
   - **Deterministic** — pattern-match outputs, exact-match assertions, schema
     validation. Cheapest, suitable for syntactic checks.
   - **Trajectory-based** — uses CGF tracer spans (already collected) to grade
     based on tool-call sequences, error rates, and execution paths rather
     than just final outputs.
   - **LLM-judge** — for behavioral / qualitative criteria where the first
     two tiers can't reach.
3. **Sandboxed agent-session eval harness** — runs the optimized resource
   against the eval suite in an isolated session, captures traces, scores
   against the grading rubric. Produces both per-testcase verdicts and an
   aggregate score.
4. **Wire `EVAL_DESIGN` and `EXECUTION_EVAL` phases** into
   `multi_resource_orchestrator.py`. Both already exist in the
   `OptimizationPhase` enum; the orchestrator currently skips them.
5. **Feedback loop** — execution results feed back into `cgf-prompt-optimizer`
   for refinement (closes the gradient loop CGF is named after). This makes
   the optimizer's iteration choices data-driven rather than purely
   self-critique-driven.

### Bonus: live data for the CGF dashboard

Block 4 Phase 3C shipped a `casdk-cgf` Grafana dashboard with placeholder
panels in a "Future" row. Stage 3 is what populates them — phase transitions,
optimizer iterations, eval scores. No dashboard work needed; the panels are
already provisioned.

### Open questions for Stage 3

- **Eval suite storage format.** YAML (matches existing CGF SPEC pattern) vs
  JSON (machine-friendlier) vs hybrid. Recommend YAML for human authoring +
  the workspace already-canonical pattern.
- **Sandbox isolation level.** Run the eval session in a fresh subprocess?
  Fresh container? In-process? Trade-off: realism (subprocess/container is
  closer to real usage) vs latency/cost (in-process is fastest).
- **Grader composition.** When deterministic + trajectory + LLM-judge all
  apply to the same testcase, how do their scores combine? Worst-of, weighted
  average, or each tier produces its own column in the result?
- **Failure mode for LLM-judge.** If the judge model itself errors or hits
  rate-limit mid-eval, do we retry, mark "no decision", or fail the run?
  Cost-conscious design suggests retry-once-then-mark.

### Stage 4 (after Stage 3 stabilizes)

End-to-end pipeline tests, checkpoint/resume across the new phases,
ACCEPT/REFINE/REJECT human-review gates surfacing in the orchestrator.

---

## Independent forward TODOs

Two items queued in CLAUDE.md "TODOs" that are unrelated to Stage 3 but worth
addressing when bandwidth allows:

- **Sub-agent `HOME` mismatch** — when sub-agents (e.g.,
  `research-team:research-specialist`) expand `~` in paths via Bash, it
  sometimes resolves to `/root` while the runtime user is `claude`
  (`$HOME=/home/claude`). The subsequent Write tool fails with `EACCES`.
  Three fix candidates queued; (a) explicit `HOME=/home/claude` env
  passthrough in `_build_sdk_options()` is the leading suspect.
- **`make interactive` terminal UX audit** — corrupted Rich panel borders,
  repeated "Thinking..." displays, verbose logs interleaved with conversation.
  Audit `harness/cli.py`, `harness/interactive.py`, possibly
  `harness/agent_progress.py`.

---

## SDK upstream investigation (closed 2026-05-05)

Block 3 Step 5 originally planned to file two issues against
[`anthropics/claude-agent-sdk-python`](https://github.com/anthropics/claude-agent-sdk-python).
Both went through bisection passes, both turned out to be invalid. **Neither
was filed.** The investigation is preserved here in case the same suspicions
resurface later.

### Issue candidate 5a — Plugin agents not exposed to Task tool with `plugin:agent` namespacing

**Original suspicion:** Block 2 Phase 3's verification experiment showed that
with the harness's `agents=sdk_agents` programmatic registration disabled,
`Task(subagent_type="cgf-agents:cgf-orchestrator")` returned `"Agent type ...
not found."` Attributed to an SDK gap; workaround kept.

**Bisection (2026-05-05) — `scripts/derisk_plugin_loading.py`:**

| # | Test | Workaround | Probe | Result |
|---|---|---|---|---|
| 1a | namespaced plugin agent | OFF | `Task("cgf-agents:cgf-orchestrator")` | **PASS** |
| 1b | bare plugin agent | OFF | `Task("cgf-orchestrator")` | **PASS** |
| 1c | marketplace plugin agent | OFF | `Task("research-team:research-specialist")` | **PASS** |
| 3a | install-flow plugin agent | OFF, no `plugins=` | `Task("research-team:research-specialist")` | PASS via `setting_sources=["user"]` |

**Actual cause:** The original experiment ran against marketplace plugins
whose `.claude-plugin/plugin.json` files were CLI-invalid (synthesizer bug,
fixed in Block 3 Step 3a, commit `0e8b31e`). The CLI silently dropped them,
which manifested as "plugin agents not addressable." With valid manifests, the
SDK exposes plugin agents to Task tool dispatch via `plugins=` natively, with
both bare and `plugin:agent` namespacing.

**Outcome:** The harness's `_register_agents` / `agents=sdk_agents` workaround
was redundant. Removed in the 5a follow-up commit (`d8571b2`).
`plugin_manager.py` retained `_register_agents` / `get_all_agents` for
`harness.subagent` (which uses standalone `query()` with the agent's prompt as
`system_prompt`, not Task dispatch) and the SystemMessage banner display.

### Issue candidate 5b — Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions

**Original suspicion:** Sending `/cgf status` from a streaming session
returned `ResultMessage(success, num_turns=0, total_cost_usd=0)` after ~14 ms
with no model invocation. Drafted as a real SDK bug.

**Bisection follow-up (2026-05-05) — `scripts/derisk_slash_init.py`:**

After re-reading [Anthropic's Slash Commands in the SDK doc](https://code.claude.com/docs/en/agent-sdk/slash-commands)
carefully, we noticed it specifies `SystemMessage(subtype="init").data["slash_commands"]`
as the authoritative list of available commands. We had never inspected that field.

| # | Test | Result |
|---|---|---|
| 7 | Inspect `slash_commands` list | **29 entries**: `cgf-agents:cgf`, `cgf-agents:cgf-optimize`, `research-team:coordinator`, etc. |
| 8a | Bare `/cgf status` (no entry in list) | SILENT_NOOP (14 ms, 0 turns) |
| 8b | **Namespaced** `/cgf-agents:cgf status` | **PASS** — 4 turns, 17.9 s, real CGF status report |
| 8c | `/totally-fake-command-that-does-not-exist` | SILENT_NOOP (14 ms, 0 turns) |

**Actual cause:** Plugin slash commands are registered correctly under their
namespaced form (`/plugin-name:command-name`). The original test was sending
the bare form `/cgf` which has no registered match. Silent no-op on unknown
slash commands is consistent SDK behavior across the board (built-in commands,
plugin commands, and entirely fake commands all silent-no-op identically),
presumably to forward-compat with future TUI-only commands.

**Slash commands aren't deprecated.** They were merged with Skills on
2026-01-24; both live in `~/.claude/skills/` (or in plugins'
`commands/`/`skills/` directories), both use markdown + YAML frontmatter,
both invoked with `/`. Skills additionally support autonomous invocation by
Claude. Legacy `.claude/commands/` still works.

**Outcome:** No SDK issue to file. Logged the namespacing requirement in
CLAUDE.md "Known Limitations" so future sessions don't relitigate. The
SystemMessage banner already shows commands in the namespaced form.

### Probe scripts retained for future regressions

- `scripts/derisk_plugin_loading.py` — exercises plugin-agent dispatch via
  Task without the workaround, configurable per-test via env vars
  (`DERISK_AGENTS_WORKAROUND`, `DERISK_SETTING_SOURCES`, `DERISK_USE_PLUGINS`,
  `DERISK_PROBE`).
- `scripts/derisk_slash_init.py` — opens a session and dumps the
  `system/init.slash_commands` list.

Re-run either after any SDK bump to confirm both behaviors still hold. If a
future SDK release changes plugin loading semantics, the probes will surface
it before the harness's runtime smoke does.

### Lessons

1. **A failing test against an undocumented field is not a bug** — read the
   SDK's official docs for the field's actual contract before drafting an
   issue. Both findings were resolved by reading the docs we hadn't read yet
   (the `claude plugin validate` schema for 5a; the
   `system/init.slash_commands` list for 5b).
2. **De-risk before filing.** Caught the misframing on both issues before
   they shipped to Anthropic. Worth the 25 minutes.
3. **The synthesizer bug class is sneaky.** Producing manifests that the CLI
   silently drops (rather than erroring on) caused both Block 2 Phase 3's
   wrong "plugin agents need programmatic registration" finding AND the
   original mass-skill-failure during Block 3 Step 3a smoke testing. Always
   validate generated artifacts (`claude plugin validate <plugin>`) at every
   layer, not just at the SDK boundary.

---

## Verification rule (still binding for Stage 3)

**Tests pass ≠ feature works.** Plugin/agent loading silently degrades in
ways unit tests do not catch (path mismatches, namespace collisions, swallowed
discovery exceptions). Every Stage 3 phase boundary must end with a *runtime*
smoke test, and the user must do their own confirmation run before any phase
is declared complete.

Required at every phase boundary:

1. **Run the full test suite and report actual numbers** — `make test-unit && make test-integration`,
   not "tests pass." Include passed/failed/skipped counts.
2. **Boot the harness and inspect the runtime registry** — capture the actual
   values of `discovered_skills`, `agents`, `plugins`. Names, not just counts.
3. **Invoke at least one resource end-to-end** for any change that touches
   loading. Confirm the actual response, not just that the call returned.
4. **Stop and ask the user to do their own verification run** before declaring
   any phase complete.
