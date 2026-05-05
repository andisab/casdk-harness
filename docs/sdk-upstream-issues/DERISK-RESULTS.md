# De-risk results

Run date: 2026-05-05
Probe: `scripts/derisk_plugin_loading.py`
SDK version: claude-agent-sdk-python 0.1.72
Harness commit at test time: `de22a61`

## Decision matrix outcome

| # | Test | Workaround | Plugins | setting_sources | Probe | Result | Duration |
|---|---|---|---|---|---|---|---|
| Baseline | sanity | ON | ✓ | `[project]` | Task `cgf-agents:cgf-orchestrator` | PASS | 8981 ms |
| 1a | workaround off, namespaced | OFF | ✓ | `[project]` | Task `cgf-agents:cgf-orchestrator` | **PASS** | 21993 ms |
| 1b | workaround off, bare | OFF | ✓ | `[project]` | Task `cgf-orchestrator` | **PASS** | 23964 ms |
| 1c | workaround off, marketplace | OFF | ✓ | `[project]` | Task `research-team:research-specialist` | **PASS** | 25272 ms |
| 2-task | broader sources, marketplace agent | OFF | ✓ | `[user,project]` | Task `research-team:research-specialist` | (not retested — already PASS) | — |
| 2-slash | broader sources, slash | OFF | ✓ | `[user,project]` | `/cgf status` | **SILENT_NOOP** | 8 ms |
| pre-3 | slash with default sources | OFF | ✓ | `[project]` | `/cgf status` | **SILENT_NOOP** | 13 ms |
| 3a | install flow + Task | OFF | ✗ | `[user]` | Task `research-team:research-specialist` | **PASS** | (~25 s) |
| 3b | install flow + slash | OFF | ✗ | `[user]` | `/research-team:research foo` | **SILENT_NOOP** | 17 ms |

For all PASS results, the transcript was inspected and confirmed
to contain a real `Agent`-tool `ToolUseBlock` followed by a
`TaskStartedMessage` and a successful `task_notification`. No
`tool_use_error` or `Unknown agent` strings appeared anywhere.

For all SILENT_NOOP results, the session terminated in <20 ms with
`num_turns=0`, `total_cost_usd=0`, `is_error=False`, and zero
input/output tokens.

## Follow-up bisection — slash commands (added 2026-05-05)

After the initial de-risk above pointed at slash commands as the
remaining real issue, a closer reading of Anthropic's official
[Slash Commands in the SDK](https://code.claude.com/docs/en/agent-sdk/slash-commands)
doc showed that the SDK exposes the available command list via the
`SystemMessage(subtype="init").data["slash_commands"]` field. We never
inspected that.

A throwaway probe (``scripts/derisk_slash_init.py``) opened a session,
captured the slash_commands list, and matched against the commands we
expected:

| # | Probe | Result |
|---|---|---|
| 7 | Inspect `slash_commands` list | **29 entries** — includes `cgf-agents:cgf`, `cgf-agents:cgf-optimize`, `research-team:coordinator`, `research-team:joplin-research`, `context-engineering:agent-dev` (and 5 sibling skills), built-in `/clear`/`/compact`/`/context`/etc. |
| 8a | Bare `/cgf status` (no entry in list) | SILENT_NOOP (14 ms, 0 turns) |
| 8b | **Namespaced** `/cgf-agents:cgf status` (matches list entry) | **PASS** — 4 turns, 17.9 s, real CGF status report |
| 8c | `/totally-fake-command-that-does-not-exist` | SILENT_NOOP (14 ms, 0 turns) |

**Conclusion: 5b is also INVALID.** Plugin slash commands are
registered correctly under their namespaced form. The original test
was sending a non-existent command name. Silent-no-op on unknown
slash commands is consistent SDK behavior across the board (built-in
or plugin), presumably for forward compat with TUI-only commands.

This means **both 5a and 5b are not-file**. The full set of SDK
gaps the de-risk supposedly identified turned out to be harness
configuration / user-input issues, not SDK bugs.

## Conclusions

### Issue 5a — Plugin agents not exposed to Task tool — **INVALID, DO NOT FILE**

The SDK's `plugins=` field correctly exposes plugin sub-agents to the
Task tool. Both bare names (`cgf-orchestrator`) and `plugin:agent`
namespaced forms (`cgf-agents:cgf-orchestrator`) resolve to the
intended plugin agent end-to-end.

The original Phase 3 finding (commit `f704536`, 2026-05-04) was an
artifact of the synthesizer producing **invalid** `plugin.json` shims
that `claude plugin validate` rejected. The CLI silently dropped those
plugins, which manifested as "plugin agents not addressable." After
the synthesizer was rewritten in 3a (commit `0e8b31e`) to lift each
marketplace entry verbatim into a CLI-valid manifest, plugin agents
became reachable — but the harness was already programmatically
registering them via `agents=` and we never tested without that
workaround until now.

**Implication for the harness:** the plugin-agent registration in
`plugin_manager.py` (`_register_agents`, `_parse_agent_file`,
`get_all_agents`) and the `agents=sdk_agents` wiring in `agent.py`
`_build_sdk_options()` are all redundant now. Removing them is a
~50-LoC further simplification, eligible as a Block 3.5 cleanup
commit before Block 4 starts. Tests 1a/1b/1c are the proof.

### Issue 5b — ~~Plugin slash commands silently no-op — REAL, FILE WITH CONFIDENCE~~ → **INVALIDATED 2026-05-05**

> **Superseded by the follow-up bisection above.** Plugin slash
> commands ARE invokable; they require the namespaced form
> ``/plugin-name:command-name``. The original test was sending the
> bare form ``/cgf`` which has no registered match. Silent no-op on
> unknown commands is consistent SDK behavior. Original analysis
> below preserved for archaeology.

**~~REAL, FILE WITH CONFIDENCE~~**

Slash commands sent through `ClaudeSDKClient.query()` return after
8-17 ms with zero turns, zero tokens, no error, and no model
invocation, regardless of:

- How the plugin was loaded (`plugins=[]` directly OR canonical
  `claude plugin marketplace add` + `claude plugin install` flow)
- What `setting_sources` is set to (`["project"]` vs `["user", "project"]`)
- Which plugin's command (`/cgf status` from in-tree `cgf-agents`,
  `/research-team:research foo` from marketplace `research-team`)

The standalone `claude` TUI expands the same commands correctly. This
is specifically a streaming-mode (SDK) gap.

**File 5b** with the existing draft body, with the test matrix above
folded in to strengthen the evidence section.

## Public/private repo link decision

After this de-risk, the issue body for 5b doesn't need to link to the
casdk-harness for the SDK team to reproduce — the `derisk_plugin_loading.py`
probe is small enough (~120 LoC) to either inline into the issue body
or attach as a gist. **Recommendation:** inline a minimal version
(stripped of plugin-discovery convenience code) so the issue is
self-contained and reviewers don't need any external links.

## Follow-up actions

| Action | Where | When |
|---|---|---|
| Drop `_register_agents` / `_parse_agent_file` / `get_all_agents` from `plugin_manager.py` | `src/harness/plugin_manager.py` | Block 3.5 follow-up commit |
| Drop `agents=sdk_agents` wiring from `_build_sdk_options()` | `src/harness/agent.py` | same commit |
| Delete `5a-plugin-agent-namespacing.md` (or move to `archived/`) | `docs/sdk-upstream-issues/` | this commit |
| Strengthen `5b-plugin-slash-commands.md` with cross-pathway evidence + inline probe | `docs/sdk-upstream-issues/` | this commit |
| Update `README.md` review doc to reflect new conclusion | `docs/sdk-upstream-issues/` | this commit |

## Probe artifacts

- Probe script: `scripts/derisk_plugin_loading.py` (committed; useful for future SDK regressions)
- Container state restored: marketplace removed, plugin uninstalled, no residue
