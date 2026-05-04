# Harness Reorganization + Plugin Loader Modernization

## Context

Two threads of work are tangled together on the `contextgrad-framework` branch and need to be separated:

1. **CGF infrastructure** that's already shipped, tested, and stable (protocol layer, multi-resource orchestrator, MCP creation skills, etc.).
2. **Eval harness work** for specialized context-engineering resources — the actual ongoing project this branch should represent (Stages 3-4).

In addition, the harness has a custom 633-line `plugin_manager.py` and a 781-line `direct_agent.py` workaround that predate recent SDK improvements (~v0.1.5 through v0.1.72). Those should be retired in favor of native SDK mechanisms — and that modernization is independent of CGF, so it belongs on `main`.

This document describes the reorganization, the modernization, and the new plugin-consumption model (consume `swe-marketplace` plugins from public git instead of vendoring under `src/harness/plugins/`).

---

## Anthropic-canonical references

Two published Anthropic implementations most closely match this harness's shape and should be the reference points during execution:

- **`anthropics/claude-agent-sdk-demos/research-agent`** — closest analog for programmatic resource loading. Uses `ClaudeAgentOptions(setting_sources=["project"], agents={...}, hooks={...})` directly with no custom plugin loader. Confirms the planned approach matches reference style.
- **`anthropics/claude-cookbooks/claude_agent_sdk/chief_of_staff_agent`** — closest analog for filesystem-based discovery. Uses `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, `.claude/output-styles/` directly. Confirms the move of `src/harness/agents/configs/*.md` → `.claude/agents/*.md` matches canonical layout.

Plugin distribution follows `anthropics/claude-plugins-official` and `anthropics/skills` (both ship `.claude-plugin/marketplace.json`). Hosting patterns follow the [Anthropic Hosting Guide](https://code.claude.com/docs/en/agent-sdk/hosting) — Pattern 2 (Long-Running Sessions) and Pattern 3 (Hybrid + session resume) describe this harness directly.

**Future-state option:** Anthropic's overview suggests prototyping with the Agent SDK and migrating to [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) for long-running asynchronous sessions without operating sandbox/session infrastructure. Not a near-term migration, but worth keeping in mind as the harness scales beyond what self-hosted infra can support easily.

---

## Verified branch state

- **`contextgrad-framework` is 72 ahead, 1 behind `main`.** (Earlier "2 commits ahead" estimate was wrong.)
- **Main is 1 ahead** via `00ece0e` "feat(plugin): add tool-creation resource type to context-engineering". cgf-framework needs this merged in.
- **Stage 1 + Stage 2 are exclusively on `contextgrad-framework`** — none of `c491972`, `8c2f956`, `c263aa9`, `c109c8e`, `f263adc`, `2f81582`, `6f0105a`, `fec48cf`, `748e12a` are on main.
- **Diff is 65,368 insertions / 9,372 deletions across 237 files** — massive divergence, not "two commits".
- Other commits on cgf-framework not on main include: multi-resource orchestrator (`09ab3da`), DSPy/TextGrad removal (`55ceb11`), CGF phase timeouts (`b3f5891`), context-engineering doc consolidation (`cac9865`), and many test/doc updates.

**Implication:** the reorganization is a real surgery, not a quick relabel. The clean strategy is to **promote nearly everything currently on cgf-framework to main**, then reset cgf-framework to a slim branch that only carries Stage 3-4 eval-harness work going forward.

---

## Plugin source decisions (confirmed with user)

| Decision | Choice |
|---|---|
| Stage 2 destination | **Port to `swe-marketplace` under marketplace's naming convention** (`mcp-tool-dev`, `mcp-server-dev`). Harness consumes from marketplace. Requires content-merge between the two versions before adopting. |
| `research-team` plugin | **Adopt swe-marketplace version wholesale.** The agent→skill migration (`research-team:coordinator`, marketplace commit `2a17fa3`) fixes a real nested-spawn bug. Drop harness's `lead-research-coordinator` agent. |
| Consumption mechanism | **Clone `swe-marketplace` from public git** to a known local path; SDK references that path via `SdkPluginConfig {"type":"local","path": ...}`. SDK does not yet support remote plugin sources (verified v0.1.72). |
| Branch sync direction | **Merge `main` → `contextgrad-framework`** periodically. Preserves history and is simpler than rebasing 72 commits. |

---

## Part 1 — Branch Reorganization

### 1A. Promote CGF infrastructure to `main`

Goal: make `main` the home for all *shipped* CGF work plus the modernization in Part 2. `contextgrad-framework` then carries only forward-looking eval-harness work.

The simplest path is a one-shot merge rather than 72 cherry-picks:

1. **Audit cgf-framework for anything *not* ready for main.** Walk the 72 commits and flag any that should be dropped or squashed (e.g., draft plan files in `docs/features/`, half-done experiments). Move flagged content to a new `cgf/eval-harness-staging` branch off cgf-framework, then revert from cgf-framework.
2. **Resolve the 1-commit lag.** `git checkout contextgrad-framework && git merge origin/main` to absorb `00ece0e`. Resolve any conflicts in the context-engineering plugin's `tool-creation` resource type (the merge is likely the trickiest spot since cgf-framework has Stage 2 work in the same area).
3. **Open a single PR `contextgrad-framework` → `main`.** Title: "Promote CGF Stages 1-2 + multi-resource pipeline to main". Reviewers can scan by commit; the squashed delta is the 65k/9k lines.
4. **After merge:** `git branch -D contextgrad-framework && git push origin --delete contextgrad-framework`, then re-create as a fresh branch off the new `main` for Stage 3+ work.

**Files that move with this promotion** (everything currently on cgf-framework, minus anything flagged in step 1):

- `src/harness/optimization/protocols/` (Stage 1)
- `src/harness/optimization/multi_resource_orchestrator.py`, `multi_resource_spec.py` (multi-resource infra)
- `src/harness/agents/configs/cgf-resource-architect.md` and the rest of the cgf-agents plugin
- `src/harness/plugins/context-engineering/skills/mcp-tool-creation/`, `mcp-server-creation/` — but see Section 1C; these get ported to swe-marketplace before or after promotion, not retained in-tree
- All Stage 1/2 tests under `tests/unit/test_optimization/test_protocols_*`, `test_spec_mcp_parsing.py`, etc.
- Doc updates: `docs/ORCHESTRATION_ROADMAP.md`, `docs/CGF-EVAL-FRAMEWORK.md`, etc.

### 1B. Reset `contextgrad-framework` to eval-harness-only

After 1A merges, recreate the branch:

```bash
git checkout main
git pull
git checkout -b contextgrad-framework
git push -u origin contextgrad-framework  # force push if old branch was kept
```

Going forward, `contextgrad-framework` carries only:

- **Stage 3 — Evaluation Framework** (draft `docs/CGF-EVAL-FRAMEWORK.md`):
  - `cgf-eval-architect` agent — generates eval suites from resource specs
  - Grader infrastructure: deterministic, trajectory-based, LLM-judge
  - Sandboxed agent-session eval harness
  - Wires the EVAL_DESIGN / EXECUTION_EVAL phases that already exist in the enum
  - Feedback loop from execution → optimizer refinement
- **Stage 4 — Integration & hardening:** end-to-end pipeline tests, checkpoint/resume across new phases, ACCEPT/REFINE/REJECT human-review gates.

### 1C. Plugin source consolidation

#### `research-team` — adopt swe-marketplace wholesale

Marketplace version is materially better. Recent commits document the architectural fix:

- `2a17fa3` — replaced coordinator agent with main-thread skill (resolves nested-spawn constraint)
- `bfce530` — retry killed researchers, default to .md, sync README to v1.2.1
- `ef72814` — standardize manifest fence, raise subtopic ceiling to 5
- `c692af5` — namespace subagent types
- `88877ea` — Glob-based verification instead of `Bash(test -f)`
- `84d4a55` — enforce file-only findings, conditional mkdir
- `d5efabe` — verification-based orchestration, output-manifest contract

**Action items** when adopting:

1. Delete `src/harness/plugins/research-team/` entirely.
2. Update CGF orchestrator code that references `research-team:lead-research-coordinator` (an agent) to use `research-team:coordinator` (a skill). Likely call sites: `src/harness/optimization/multi_resource_orchestrator.py` and any agent-config files that reference it. Run `grep -rn 'lead-research-coordinator\|research-team:lead' src/ tests/` before deleting.
3. Verify research-team skill works with main-thread `Task` tool calls (the whole reason for the skill conversion). If the harness invokes `research-team:coordinator` from a subagent context, the nested-spawn bug recurs and the call site must move to a main-thread context.

#### `context-engineering` — port Stage 2 to marketplace, then consume from there

The harness has Stage 2 skills (`mcp-tool-creation`, `mcp-server-creation`) that swe-marketplace lacks. Marketplace has analogous-but-different `mcp-tool-dev`, `mcp-server-dev` skills plus `patterns/` (4 docs) and `templates/` (11+ files including Python/TypeScript MCP scaffolds).

**Compatibility assessment is a prerequisite, not an assumption.** Before porting:

1. **Diff content** between harness's `mcp-tool-creation/SKILL.md` and marketplace's `mcp-tool-dev/SKILL.md` (and the same for `mcp-server-*`). Are they:
   - **Same intent, different naming** → rename harness skills to `mcp-tool-dev`/`mcp-server-dev`, then merge content (keep richer of the two), commit to swe-marketplace.
   - **Different intent (e.g., creation = scaffolding, dev = guidance)** → keep both under distinct names; harness skills get adopted under `mcp-tool-creation`/`mcp-server-creation` in marketplace alongside the existing `-dev` skills.
2. **Diff `context-engineer` agent definitions** between harness and marketplace — whichever is canonical for the agent must be reconciled too.
3. **Verify naming dependencies in CGF code.** `grep -rn 'mcp-tool-creation\|mcp-server-creation\|context-engineering:' src/ tests/` to find every call site. Update them to whatever names land in marketplace.
4. **Compatibility with local agent definitions.** The harness has 14 agent configs in `src/harness/agents/configs/`. Confirm none of them reference `context-engineering:` skills by names that change.
5. **Adopt marketplace's `patterns/` and `templates/`** as they ship in swe-marketplace — they're additive and useful.

After porting and merging upstream: delete `src/harness/plugins/context-engineering/` and consume the swe-marketplace version.

##### Deferred CE plugin redundancies (introduced by 2026-05-01 merge)

The cgf-framework → main merge took the **union** of skills/templates from both branches because cleaning them up requires the marketplace adoption that happens here in Part 1C. Until that lands, the in-tree CE plugin contains overlapping resources that need reconciling:

**Overlapping skills (3 cover similar ground):**
| Skill | Origin | Granularity | Has references/ | Notes |
|---|---|---|---|---|
| `skills/mcp-tool-creation/` | cgf-framework, Stage 2 | Tool-only | yes (`tool-design-patterns.md`) | Most specific; FastMCP / Anthropic tool-description focused |
| `skills/mcp-server-creation/` | cgf-framework, Stage 2 | Server-only | yes (`python-server-patterns.md`, `typescript-server-patterns.md`, `server-testing-guide.md`) | Most specific; ships full Python + TypeScript server scaffolds in `templates/` |
| `skills/tool-creation/` | main, commit `00ece0e` (Feb 2026) | Tool + server combined | no | Older single-skill version; broader / less detailed |

**Overlapping templates:**
- `templates/mcp-tool-template.py` (cgf, FastMCP-specific)
- `templates/mcp-server-python-template/` (cgf, full Python scaffold)
- `templates/mcp-server-typescript-template/` (cgf, full TypeScript scaffold)
- `templates/tool-template.md` (main, broader single template covering Python + TypeScript + subprocess patterns)

**Reconciliation plan in this Part 1C:**
1. When swe-marketplace adoption begins, treat marketplace's `mcp-tool-dev` / `mcp-server-dev` as the canonical names. The harness's `mcp-tool-creation` and `mcp-server-creation` content gets ported upstream under the marketplace names (richer of the two wins per skill).
2. The single `tool-creation` skill from main is **superseded** by the granular pair. Drop it during marketplace adoption — its content is fully covered by `mcp-tool-dev` + `mcp-server-dev` post-port.
3. `tool-template.md` from main is also superseded by the cgf MCP-specific templates. Drop it.
4. The merge artifacts in README.md and agents/context-engineer.md have inline `_(Part 1C cleanup)_` notes pointing at this section.

**Markers to grep when starting Part 1C:**
- `grep -rn 'Part 1C cleanup' src/harness/plugins/context-engineering/` — finds every inline note in the README and agent doc
- `grep -rn 'tool-creation' src/harness/plugins/context-engineering/` — finds the to-be-dropped skill references
- `grep -rn 'tool-template' src/harness/plugins/context-engineering/` — finds the to-be-dropped template references

#### `cgf-agents` — stays in-tree

Not in swe-marketplace and harness-specific. Lives under `src/harness/plugins/cgf-agents/` indefinitely (or moves to a private marketplace later if useful).

#### Marketplace consumption mechanism

SDK supports only `{"type":"local","path": ...}` — no git source. So:

- **Bootstrap step** clones `https://github.com/andisab/swe-marketplace` to a known path. Two reasonable conventions:
  - **In Docker:** `git clone https://github.com/andisab/swe-marketplace.git /opt/plugins/swe-marketplace` in the Dockerfile (with optional pin to a tag/SHA).
  - **Local dev:** `make plugins-sync` target that clones/updates to `<repo>/.plugins/swe-marketplace/` (gitignored).
- **Harness config** (env or settings): `SWE_MARKETPLACE_PATH=/opt/plugins/swe-marketplace` (default in container) or auto-detected `<repo>/.plugins/swe-marketplace`.
- **Plugin loader** (post-modernization, see Part 2) reads marketplace.json from that path and emits one `SdkPluginConfig` per enabled plugin under `<marketplace_path>/plugins/<name>`.
- **Pinning:** for reproducibility, support `SWE_MARKETPLACE_REF` env var (tag, SHA, or branch). Default to a known-good ref; bump deliberately.

### 1D. Move "Known limitations" to main TODOs

These items are infra/ops, not eval-harness:

- Grafana overview dashboard is a stub → **handled by Part 3C**
- AlertManager rules defined but not wired into `docker-compose.yml` → **handled by Part 3D**
- Stale postgres exporter target in `prometheus.yml` → **handled by Part 3D**
- SDK Task tool bug references — re-verify against current SDK; #12212 is closed (2025-11-27), #11205 may not exist on `anthropics/claude-code`. Update CLAUDE.md. → **handled by Part 2 Phase 0**

Action: remove these from CLAUDE.md's "Known Limitations" section as each Part lands. The remaining items here are pointers, not separate TODOs.

### 1E. Pre-existing test failures fixed 2026-05-02 ✓

`make test-unit` totals on cgf-framework after merging `origin/main` (pre-fix): **1585 passed, 6 failed, 22 warnings.** The 6 failures pre-existed on cgf-framework (verified against parent commit `0e7199a`). The merge introduced no regressions.

**All 5 follow-ups landed as 3 small commits on `main` (2026-05-02):**

1. **`a7f6d4f` — `test(config): isolate test_new_config_fields_defaults from .env`**
   Pass `_env_file=None` so the test verifies code defaults rather than the developer's local `.env` (which had `AUTONOMOUS_DELAY_SECONDS=3` overriding the canonical default of 5).

2. **`f734b5c` — `test(testcases): reset shared anthropic client singleton between tests`**
   Single root cause for 4 failures (#2, #3, #4, #5). `validators.get_shared_anthropic_client()` cached a module-level singleton populated by the FIRST test's mock; subsequent tests' patches couldn't replace it, so they received the prior test's response ("The score is 0.7") regardless of their own mock. Added autouse fixture that resets `_shared_client = None` between tests.

3. **`9bf5a28` — `fix(config): treat empty ENABLED_PLUGINS env value as "no filter"`**
   Real user-facing bug, not just a test issue. The `enabled_plugins_list` property treated empty-string `""` (a common `.env` state) as "filter to nothing" → 0 plugins loaded. Now empty resolves to `None` → "no filter, enable all". Anyone with `ENABLED_PLUGINS=` in their `.env` previously had zero plugins silently — that's now fixed.

**Post-fix totals: 1591 passed, 0 failed, 21 warnings.**

---

## Part 2 — Plugin Loader Modernization (lands on `main`)

This is independent of eval-harness work and should land on `main` first. After it lands, merge `main` → `contextgrad-framework` to pick it up.

### Current architecture (verified)

- **`src/harness/plugin_manager.py`** (633 LoC) — discovers `src/harness/plugins/*/.claude-plugin/plugin.json`, parses agent/skill/command/hook markdown manually, namespaces as `plugin:resource`, wires into `CommandRegistry` and `HookRegistry`.
- **`src/harness/direct_agent.py`** (781 LoC) — bypasses `Task` tool because of SDK issue #12212 by calling `query()` directly with a per-agent system prompt.
- **`src/harness/agent.py:684-693`** — already passes `agents=`, `setting_sources=["user","project"]`, `plugins=self.plugins` to `ClaudeAgentOptions`. The hard parts are wired; what remains is delegation rather than duplication.
- **`src/harness/agents/configs/*.md`** — 14 harness agent definitions live here, NOT in `.claude/agents/`, so SDK auto-discovery cannot see them.
- **`.claude/`** in repo holds only `settings.json` (permission allowlist + MCP enables). No `agents/`, `skills/`, `commands/`, `hooks/`.
- **SDK version pin** — `pyproject.toml` requests `claude-agent-sdk>=0.1.0`; `uv.lock` resolves to **0.1.12 (2025-12-04)**. Latest is **0.1.72** (May 2026).

### What the SDK now provides natively

| Native capability | SDK version | Replaces |
|---|---|---|
| `ClaudeAgentOptions.plugins=[{"type":"local","path":...}]` auto-loads `.claude-plugin/plugin.json` (skills, agents, hooks, MCP, LSP, monitors) | 0.1.5+ | Most of `plugin_manager.py` |
| `setting_sources=["user","project","local"]` auto-discovers `.claude/agents/`, `.claude/skills/`, `.claude/commands/` | 0.1.0 (empty list correctly disables, post-bug) | Manual frontmatter parsing |
| `skills="all" \| list[str] \| []` parameter | 0.1.62 | `allowed_tools=["Skill",...]` plumbing |
| Task tool finds custom agents from filesystem AND `agents=` dict | issue #12212 fixed 2025-11-27 | `harness.direct_agent` |
| Plugin commands and skills unified — `/foo` resolves from either `commands/foo.md` or `skills/foo/SKILL.md` | 2026 | `CommandRegistry` |
| `AgentDefinition` camelCase fields: `maxTurns`, `permissionMode`, `mcpServers`, `disallowedTools`, plus newer `skills`, `memory`, `effort`, `background`, `initialPrompt` | recent | YAML `max_turns` → manual translation |
| `hooks/hooks.json` standard event names: `PreToolUse`, `PostToolUse`, `SessionStart`, `Stop`, `UserPromptSubmit`, `Notification` | stable | Harness's non-standard `PostSessionStart` / `STOP` |

Caveats:
- `allowed-tools` in `SKILL.md` frontmatter is **CLI-only** — the SDK ignores it; use `ClaudeAgentOptions.allowed_tools`.
- Skills are filesystem-only — no programmatic registration. CGF-generated skills must be written to disk before the session starts (the orchestrator already does this).
- `setting_sources=[]` is the documented way to make autonomous runs hermetic.
- `SdkPluginConfig` does **not** support remote/git sources as of v0.1.72 — clone first, then point to local path.

### Phased modernization

**Phase 0 — Bump and verify (low risk, days; lands on `main`) ✓ DONE 2026-05-04**
- [x] Pin `claude-agent-sdk>=0.1.72` in `pyproject.toml`; `uv.lock` refreshed (0.1.12 → 0.1.72).
- [x] Smoke test passed: `make interactive` → `Task(subagent_type="python-expert", ...)` returned a real response with `ResultMessage(is_error=False, num_turns=2, duration_ms=16492)`. Issue #12212 fix confirmed live in this harness's setup. (Session `ff3d4686-4d77-4ae2-9dc7-e7391498a1e8`.)
- [x] Bonus: confirmed `ClaudeAgentOptions.skills=` parameter exists in 0.1.72 — closes Risk item below ("`skills=` parameter existence").
- [x] Unit tests unchanged at 1591 passed / 0 failed.
- Outcome: green. `direct_agent.py` retirement (Phase 3) is technically unblocked; deferred until Phases 1-2 land per the staged plan.

**Phase 1 — Filesystem discovery for harness agents (1-2 days; `main`) ✓ DONE 2026-05-04**
- [x] Moved 14 files: `src/harness/agents/configs/*.md` → `.claude/agents/*.md` (git-mv preserved history).
- [x] `definitions.py:31` `CONFIGS_DIR` repointed to repo-root `.claude/agents/` via `parents[3]`.
- [x] `ResourceRegistry.discover()` (CGF) updated similarly — `base_path / "agents" / "configs"` → `base_path / ".claude" / "agents"`, default `base_path` walks up to repo root.
- [x] `setting_sources=["user", "project"]` → `["project"]` (drops host `~/.claude/` bleed-over; container hermetic).
- [x] Dockerfile copies `.claude/` into dev + production stages.
- [x] All `src/`, `tests/`, `CLAUDE.md`, `README.md` references to old path updated. Plugin agent prompts (cgf-orchestrator, cgf-prompt-optimizer, cgf-test-architect, cgf-optimize SKILL) repointed.
- [x] **YAML model field normalized:** 12 files had `model: opus 4.1` which SDK filesystem auto-discovery read as `opus-4-1[1m]` (a 1M-context variant) and rejected at runtime. Normalized to canonical `opus`/`sonnet`/`haiku`. Pre-Phase-1 `agents=AGENT_DEFINITIONS` translated via `MODEL_MAP` so the issue was hidden.
- [x] Unit tests 1591/0/0 unchanged.
- [x] Runtime smoke verified: `Task(subagent_type="python-expert")` returns real response, `ResultMessage(is_error=False)`. Session `9010bda7-53c7-485f-86e2-f85ff4382978`.
- Frontmatter adapter (snake_case → camelCase) was not required: existing YAML matches what SDK reads on-disk.

**Latent name-mismatch — to be reconciled in Phase 3.** Filesystem auto-discovery uses each file's YAML `name:` field, while `agents=AGENT_DEFINITIONS` exposes logical aliases. The 2026-05-04 experiment (see Phase 3) confirmed 4 alias divergences (`database-expert`, `gcp-architect`, `code-review-expert`/`reviewer-agent`, `sdet-expert`). Today both registration paths are active simultaneously so any caller can use either name; Phase 3's harness-agent removal from programmatic registration drops the aliases unless we rename. Concrete reconciliation plan is in Phase 3 below.

**Phase 2 — Delegate plugin loading to the SDK (~3-5 days; `main`)**

Phase 2 minimal landed 2026-05-04 (commit `a0d1744`): hook event rename `PostSessionStart` → `SessionStart`; dropped unused `PreSessionStart`. Tests 1591/0/0.

The full Phase 2 (collapse `plugin_manager.py` to <80 LoC, delete `CommandRegistry`, slim `HookRegistry`) is **gated on the verification experiment described in Phase 3 below.** The shape of the collapse depends on whether `setting_sources=["project"]` + `plugins=[...]` is sufficient for SDK Task tool dispatch, or whether programmatic `agents=` registration is still required.

Once the experiment runs:
- **If filesystem auto-discovery is sufficient:** drop `_convert_to_sdk_agents()` and `_load_plugin_agents()` from `agent.py`; `plugin_manager.py` collapses to a thin path-resolver. `CommandRegistry` deletion becomes safe.
- **If programmatic registration is still required:** `plugin_manager.py` keeps its loader role but can still slim. `CommandRegistry` deletion needs a separate decision.

In both branches: `~~Verify `skills=` parameter exists~~` is **closed** as of Phase 0 (confirmed in SDK 0.1.72). Existing plan items for hook rename and event canonicalization are now done.

**Phase 3 — Slim `direct_agent.py` and lean on SDK loading conventions (~2 days; `main`) ✓ DONE 2026-05-04**

Landed across 6 commits (`a4315d7` through Step 6 commit). Final state: `direct_agent.py` (780 LoC) → `subagent.py` (~530 LoC) + new `agent_progress.py` (196 LoC). Harness agents now auto-discover from `.claude/agents/` via `setting_sources=["project"]`; plugin agents continue to be programmatically registered (the SDK's `plugins=[{type:local,path:...}]` does not auto-expose them with `plugin:resource` namespacing). Both runtime-verified.

Step-by-step record (kept for archeology):

_Renamed scope (2026-05-04): the goal is "use established SDK conventions for loading agents/plugins/resources at startup", not "delete `direct_agent.py`". `direct_agent.py` solves a real standalone-Python use case (CGF runners invoke agents without a parent SDK session) for which SDK Task tool dispatch is not applicable. The goal is to slim it and possibly rename._

#### Verification experiment — RUN 2026-05-04 ✓

Test setup: commented out `agents=sdk_agents,` in `agent.py:_build_sdk_options()`. Left `setting_sources=["project"]` and `plugins=self.plugins` active. Rebuilt container. Two Task dispatches inside `make interactive`.

**Test A — harness agent (`subagent_type="python-expert"`):** ✅ **PASS.** python-expert returned a real response (`ResultMessage(success)`, $0.17, 17s). SDK filesystem auto-discovery from `.claude/agents/` is sufficient for Task dispatch. Session `aed22c67-c36b-4cc5-a4bf-598b00bfe048`.

**Test B — plugin agent (`subagent_type="cgf-agents:cgf-orchestrator"`):** ❌ **FAIL.** `"Agent type 'cgf-agents:cgf-orchestrator' not found."` Available list at runtime included all 14 filesystem-discovered harness agents + SDK built-ins — but **zero plugin agents**. The `plugins=[{type:local, path:...}]` parameter does not auto-expose plugin agents to Task with the `plugin-name:agent-name` namespacing the harness uses.

**Bonus finding — latent name-mismatch surfaces.** With programmatic registration off, the available list was the YAML `name:` fields verbatim:
- `postgres-expert` present, `database-expert` (programmatic alias) **gone**
- `gcp-cloud-architect` present, `gcp-architect` (programmatic alias) **gone**
- `dev-code-review-expert` (with `dev-` prefix in YAML) present, `reviewer-agent` and `code-review-expert` (aliases) **gone**
- `testing-agent` present, `sdet-expert` (alias) **gone**

These aliases only existed because `_convert_to_sdk_agents()` registered them. Phase 3 must reconcile (recommend: rename YAML to canonical short forms and drop alias dict).

#### Phase 3 work — finalized scope (~1-2 days)

Concrete changes per the experiment outcome:

**In `agent.py:_build_sdk_options()`:**
- **Drop** the harness-agents portion of `_convert_to_sdk_agents()` (lines 624-631) — filesystem discovery covers it.
- **Keep** the plugin-agents portion (lines 633-635) — still required for namespaced Task dispatch. `_load_plugin_agents()` continues to do real work until SDK adds native plugin-agent namespacing.

**Reconcile latent name-mismatches** (4 files):
- Rename YAML `name:` fields to canonical short forms; rename files to match:
  - `db-postgres-expert.md` → `database-expert.md` (YAML `name: database-expert`)
  - `infra-gcp-architect.md` → `gcp-architect.md` (YAML `name: gcp-architect`)
  - `dev-code-review-expert.md` → `code-review-expert.md` (YAML `name: code-review-expert`)
  - `test-sdet-expert.md` → `sdet-expert.md` (YAML `name: sdet-expert`)
- Drop the `agent_files` alias dict in `definitions.py` (logical-name → filename mapping no longer needed).
- Update plugin agent prompts and CGF orchestrator paths that reference the old filenames (per Phase 1 grep audit).

**Slim `direct_agent.py` (780 → ~400-500 LoC):**
- Drop `MODEL_MAP` (Phase 1 normalized YAML).
- Share filesystem walker with `definitions.py` and `ResourceRegistry.discover()` (extract a small helper module if it reduces duplication).
- Convert `register_workspace_agent` from in-memory cache to writing `workspace/.claude/agents/<name>.md`; for CGF standalone runs that need workspace-local agents, set `setting_sources=["project", "local"]` (or `["local"]` for hermetic).
- Extract `AgentProgress` (~190 LoC) to `harness/agent_progress.py` — reusable terminal UX.
- Update module docstring (no longer a "Task tool workaround"; standalone agent invocation utility).
- Rename module → `harness/subagent_query.py` (reflects real role).
- Update all 7 production import sites: `optimization/multi_resource_orchestrator.py` (5 sites), `optimization/runners/agent_runner.py` (1 site), and `optimization/cli/section_optimize.py` if applicable.
- Update plugin docs that reference `harness.direct_agent` (~10 doc references in `plugins/cgf-agents/agents/*.md`, `plugins/context-engineering/examples/*.md`, etc.).

**SDK follow-up to file (after Phase 3 lands):**
- Issue/discussion upstream: does `plugins=[{type:local, path:...}]` expose plugin-defined agents to the Task tool with `plugin:resource` namespacing? If not, request the feature or document the gap. If yes, future work could drop `_load_plugin_agents()` too.

**Target after Phase 3:**
- `direct_agent.py` (renamed `subagent_query.py`): ~400-500 LoC
- `agent.py:_convert_to_sdk_agents()`: ~5 lines (just plugin agents)
- `definitions.py`: alias dict gone, ~200 LoC
- New: `harness/agent_progress.py`: ~190 LoC (extracted)

**Phase 4 — Marketplace bootstrap & CI hooks (`main`)**
- Add `make plugins-sync` target that clones/pulls `swe-marketplace` to `.plugins/swe-marketplace/` (gitignored).
- Add Dockerfile step that clones `swe-marketplace` to `/opt/plugins/swe-marketplace` at known SHA/tag.
- `SWE_MARKETPLACE_PATH` and `SWE_MARKETPLACE_REF` env vars; defaults documented in `.env.example`.

---

## Part 3 — Observability: OpenTelemetry integration + Prometheus/Grafana polish (lands on `main`)

This is its own stage rather than a sub-phase of Part 2. It addresses both a documented Anthropic capability we're not yet using (native OTLP signals) and a known limitation (Grafana stub dashboard, AlertManager unwired). Independent of CGF and modernization, so it can ship to `main` in parallel or after Part 2.

### Scope

The current state has Prometheus metrics emitted from `src/harness/monitoring.py` (agent requests, durations, token counts, costs, tool calls), a Grafana stack via `docker-compose.yml`, and an `alerting.yml` with rules but no AlertManager. The Grafana overview dashboard is a placeholder. Anthropic shipped native OTLP support for the Agent SDK (April 2026) gated by `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus standard `OTEL_EXPORTER_OTLP_*` env vars — we should bridge that into the same observability stack rather than running parallel pipelines.

### Phased plan

**Phase 3A — Enable native OTel and route into existing collector (~2 days)**
- Add `CLAUDE_CODE_ENABLE_TELEMETRY=1` and `OTEL_EXPORTER_OTLP_ENDPOINT` env vars to `Dockerfile`, `.env.example`, and `docker-compose.yml`.
- Stand up an OTel Collector service in `docker-compose.yml` configured to receive OTLP from the SDK and export to Prometheus (existing) and a structured-log destination.
- Reference: [Anthropic Observability with OpenTelemetry](https://code.claude.com/docs/en/agent-sdk/observability).
- **Verify at runtime**: SDK metrics (token usage, model calls, tool invocations) appear in Prometheus alongside existing harness metrics. Capture metric names from `/metrics` endpoint to confirm.

**Phase 3B — Trim duplicate metrics, keep harness-specific ones (~1 day)**
- Audit `src/harness/monitoring.py` against what the SDK now emits natively (token counters, request counters, model-call durations).
- Remove harness counters that duplicate SDK counters. Keep only signals the SDK does not emit: checkpoint events, session-state transitions, autonomous-mode task transitions, plugin/agent registry counts, harness-specific cost calculations.
- Document which counters are harness-owned vs SDK-owned in `docs/HARDENING.md` or a new `docs/OBSERVABILITY.md`.

**Phase 3C — Grafana dashboards: build out properly (~2-3 days)**
- Replace the stub overview dashboard with a real one. Required panels:
  - Session metrics: active sessions, session-start rate, session duration p50/p99
  - Token & cost: tokens/min by model, cumulative cost, cost-per-session
  - Tool calls: top tools by call rate, tool-error rate, tool-call duration p99
  - Agent dispatch: subagent invocations by name, error rate per agent
  - Autonomous mode: tasks completed/blocked/in-progress, Tech Lead Q&A duration
  - Plugin/registry health: number of loaded plugins/agents/skills, discovery errors
- Add a second dashboard for CGF optimization runs (phase transitions, optimizer iterations, eval scores once Stage 3 lands).
- Provision dashboards as code via Grafana JSON in `config/monitoring/grafana/dashboards/` so they survive container rebuilds.
- **Verify at runtime**: load each dashboard against a live session, confirm every panel returns data (not "N/A" or "No data"). Screenshot the working state for the doc.

**Phase 3D — AlertManager wiring (~1-2 days)**
- Add AlertManager service to `docker-compose.yml`. Wire `config/monitoring/alerting.yml` rules into it.
- Add at minimum: receiver config (webhook or email — user choice), routing tree, inhibition rules.
- Audit existing `alerting.yml` rules for relevance: confirm thresholds match current production load; remove stale rules.
- Remove the stale postgres exporter target from `prometheus.yml` while in this area.
- **Verify at runtime**: synthetically trigger one alert (e.g., kill the main-agent container or spike an error rate) and confirm the receiver fires.

**Phase 3E — Documentation polish (~1 day)**
- New `docs/OBSERVABILITY.md` covering: how SDK OTel signals reach Prometheus, what each Grafana dashboard shows, how to add a new alert rule, how to interpret common alert states.
- Cross-link from `README.md`, `CLAUDE.md`, and `QUICKSTART.md`.
- Remove "Grafana overview dashboard is a stub" and "AlertManager unconfigured" from CLAUDE.md known-limitations.

### Definition of done for Part 3

The harness has feature-complete observability:

- SDK-native OTLP signals are flowing into Prometheus via the OTel Collector.
- No metric is emitted by both the SDK and the harness.
- Every Grafana panel on every shipped dashboard shows real data after a 5-minute live session.
- AlertManager is wired and at least one alert has been synthetically triggered and received.
- Stale postgres exporter target is removed.
- `docs/OBSERVABILITY.md` exists; CLAUDE.md known-limitations no longer mentions any of the above.

---

## Critical files to modify

**Branch reorganization:**
- All 72 commits currently on `contextgrad-framework` (promote to `main` via merge PR)
- `src/harness/plugins/research-team/` — delete after marketplace adoption
- `src/harness/plugins/context-engineering/` — delete after Stage 2 ports upstream and marketplace adoption
- `src/harness/optimization/multi_resource_orchestrator.py` and any agent configs referencing `lead-research-coordinator` — update to `coordinator` skill
- `Dockerfile`, `Makefile`, `.env.example` — marketplace bootstrap

**Modernization (lands on main):**
- `pyproject.toml`, `uv.lock` — SDK pin to ≥0.1.72
- `src/harness/agent.py` — `_build_sdk_options()` (lines 647-693), narrow `setting_sources` to `["project"]`, conditionally add `skills=` only after verifying it exists in pinned SDK
- `src/harness/plugin_manager.py` — collapse to <80 LoC, delegate to swe-marketplace clone path
- `src/harness/commands.py` — delete (after verifying no callers)
- `src/harness/hooks.py` — slim to harness-internal hooks only; rename events
- `src/harness/direct_agent.py` — delete after callers migrate
- `src/harness/agents/configs/*.md` → `.claude/agents/*.md` (14 file moves)
- `src/harness/agents/definitions.py` — likely deletable

**Observability (Part 3, lands on main):**
- `Dockerfile`, `.env.example`, `docker-compose.yml` — `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `OTEL_EXPORTER_OTLP_*` env, OTel Collector service
- `src/harness/monitoring.py` — trim metrics that duplicate SDK-native OTLP signals
- `config/monitoring/grafana/dashboards/` — real overview dashboard + CGF dashboard, provisioned as code
- `config/monitoring/prometheus.yml` — remove stale postgres exporter target
- `config/monitoring/alerting.yml` + new AlertManager service config
- New `docs/OBSERVABILITY.md`

**Upstream to swe-marketplace:**
- `mcp-tool-creation/SKILL.md` and `mcp-server-creation/SKILL.md` content (after compatibility diff with `mcp-tool-dev`/`mcp-server-dev`)

---

## Files to reuse / preserve

- `src/harness/optimization/protocols/` — Stage 1 work, moves to main intact
- `.claude/settings.json` permission allowlist — already canonical
- `register_workspace_agent()` semantics — keep the capability, change the mechanism (write to `workspace/.claude/agents/`)

---

## Verification plan

**Hard rule for every phase: tests pass ≠ feature works.** Plugin/agent loading silently degrades in ways unit tests do not catch (path mismatches, namespace collisions, swallowed discovery exceptions). Every phase must end with a *runtime* smoke test, and the user must do their own confirmation run before any phase is declared complete.

### Required at every phase boundary

1. **Run the full test suite and report actual numbers** — `make test-unit && make test-integration`, not "tests pass." Include passed/failed/skipped counts.
2. **Boot the harness and inspect the runtime registry**:
   - `make build && make up`, confirm container is healthy
   - `make interactive`, confirm session starts cleanly
   - From the structured logs, capture and report the actual values of: `discovered_skills=[...]`, `agents=[...]`, `plugins=[...]`. List names, not just counts.
   - Compare against the expected list for that phase. If a single resource is missing or unnamed, the phase is **not done** — investigate before moving on.
3. **Invoke at least one resource end-to-end** for any change that touches loading: dispatch `Task` to a custom agent, run a slash command, or invoke a skill. Confirm the actual response, not just that the call returned.
4. **Stop and ask the user to do their own verification run** before declaring the phase complete. Provide exact commands and what to look for in the output. Do not move on until the user confirms.

### Phase-specific checks

**Branch reorganization (Part 1):**
1. `make test-unit && make test-integration` green on the merged `main` after Part 1A — report numbers.
2. `grep -rn 'lead-research-coordinator\|research-team:lead' src/ tests/` returns zero results after research-team swap.
3. `grep -rn 'mcp-tool-creation\|mcp-server-creation' src/ tests/` matches whatever names landed in marketplace.
4. **Runtime check:** `make up && make interactive`, then dispatch `Task` with `subagent_type="research-team:coordinator"` and `subagent_type="context-engineering:context-engineer"`. Both must return real responses. If either errors with "agent not found" or returns nothing, plugin loading is broken — do not proceed.
5. `make autonomous` and `make optimize` smoke runs from a fresh clone with a throwaway SPEC.md exercise the most plugin surface area. Both must complete a full Q&A turn without dropping a resource.

**Modernization (Part 2):**
6. New integration test: spawn a session, dispatch a `Task` to `python-expert` registered via filesystem (`.claude/agents/python-expert.md`), assert success — proves filesystem discovery works.
7. New regression test: load all marketplace plugins via `plugins=`, list visible skills/commands/agents, compare to the pre-modernization `plugin_manager` output. Delta should be empty (or strictly larger). **If the modernized loader exposes fewer resources than the legacy loader, the modernization is wrong** — do not declare Phase 2 done.
8. After Phase 3, delete `direct_agent.py` only when grep shows zero imports AND a runtime smoke proves Task-tool dispatch works for both filesystem and `agents=` agents.

**Plugin marketplace bootstrap (Part 1C):**
9. From a fresh clone: `make plugins-sync && make build && make up && make interactive` — confirm marketplace plugins load without manual setup, and the runtime registry contains the expected swe-marketplace plugins.
10. With `SWE_MARKETPLACE_REF=v1.x.y`: confirm the pin is honored (verify the resolved git SHA in the clone matches the requested ref).

**Observability (Part 3):**
11. **Phase 3A:** After enabling `CLAUDE_CODE_ENABLE_TELEMETRY=1`, hit the OTel Collector's debug exporter and confirm SDK-native signals are arriving. Then confirm the same signals are scraped into Prometheus (`curl http://localhost:9090/api/v1/label/__name__/values | grep claude_code`). If no native signals arrive, do not proceed.
12. **Phase 3B:** Diff the metric list before and after the trim. No metric should appear from both the SDK and `monitoring.py`.
13. **Phase 3C:** Run a 5-minute live session (`make interactive` with several Task dispatches and a CGF run). Open every Grafana dashboard panel and confirm each shows real data, not "No data". Take screenshots for `docs/OBSERVABILITY.md`. **A dashboard with even one "No data" panel is not done.**
14. **Phase 3D:** Synthetically trigger an alert (e.g., `docker kill main-agent` or scripted error spike) and confirm the configured receiver fires. Confirm AlertManager UI at its exposed port shows the firing alert.
15. **Phase 3E:** `docs/OBSERVABILITY.md` exists, is cross-linked, and CLAUDE.md known-limitations no longer references Grafana stub or AlertManager.

### User-confirmation gate at completion

Before any phase is closed:
- Provide the user with the exact commands to run (`make up`, `make interactive`, `make autonomous`, etc.) and the exact log lines to look for.
- Tell the user what *should* be in the runtime registry (which plugins, which agents, which skills).
- Wait for the user to confirm. Do not assume.

---

## Risks / open questions to resolve during execution

- **Compatibility of `mcp-tool-creation` ↔ `mcp-tool-dev`** (and server variants): same intent or different? Determines whether we merge content or keep both. Treat as a prerequisite to Part 1C; do the diff before opening PRs.
- **CGF orchestrator dependencies on plugin resource names.** The full `grep` audit must run before adopting marketplace versions, not after.
- **`research-team:coordinator` invocation context.** It's a *skill*, must run in the main-thread context. If CGF currently invokes the old agent from a subagent, we have to move the call site too — not just rename.
- **`direct_agent.py` progress UX.** If colored turn-by-turn output during CGF runs is a hard requirement, keep a thin streaming wrapper rather than fully delete.
- **Marketplace pin policy.** Always-latest (auto-pull on every container build) vs pinned-to-SHA. Recommend pin-and-bump-deliberately for reproducibility.
- **Stage 2 already-merged commit on main (`00ece0e`).** Confirm during the merge PR that it doesn't conflict with cgf-framework's parallel work in the same context-engineering area.
- ~~**`skills=` parameter existence.**~~ ✓ Resolved 2026-05-04 — confirmed present in SDK 0.1.72 alongside `setting_sources`, `plugins`, and `agents`.
- **OTel Collector vs direct OTLP export.** Phase 3A assumes a Collector service in docker-compose. Alternative: SDK exports OTLP directly to a remote-hosted Prometheus/OTLP endpoint, no Collector. Decide based on whether observability stays in-cluster (Collector preferred) or external (direct export simpler).
