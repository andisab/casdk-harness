# Pre-filing de-risk plan

Three runtime tests to confirm the issues reproduce against a known-good
configuration before filing. Each is throwaway — make the change, run
the test in `make interactive`, revert. None of these get committed.

The goal is to rule out **harness misconfiguration** as the cause, so
we file with confidence.

## Test 1 — Disable the harness's plugin-agent workaround, retry Task dispatch

The harness pre-registers plugin agents via `ClaudeAgentOptions(agents={...})`
to work around the apparent gap. To verify the gap exists, disable that
registration and see whether plugin agents are still dispatchable via
Task.

### Patch (temporary)

In `src/harness/agent.py`, find `_build_sdk_options()` (~line 636) and
change the `agents=` line from:

```python
agents=sdk_agents,  # Register custom subagents for Task tool
```

to:

```python
agents={},  # DERISK: disabled workaround — verify SDK plugin loader exposes plugin agents
```

The SDK source dev-mounts into the container, so just edit and run
`make interactive` (no rebuild).

### Tests

1. `Use the Task tool with subagent_type "cgf-agents:cgf-orchestrator" to say hi.` — Expect: `Unknown agent: cgf-agents:cgf-orchestrator` (we're testing the namespaced form).

2. `Use the Task tool with subagent_type "cgf-orchestrator" to say hi.` — Expect: `Unknown agent: cgf-orchestrator` (bare name, in case namespacing is the issue and the SDK exposes plugin agents under their bare name).

3. `Use the Task tool with subagent_type "research-team:research-specialist" to say hi.` — Expect: same failure (this would have been working via SDK's plugin loader if it surfaced agents at all).

### Outcomes

- **All three fail with "unknown agent"** → strong confirmation of issue 5a. SDK's `plugins=` field doesn't expose any agent to Task in any namespacing form. File 5a with confidence.
- **One of them succeeds** → SDK does expose plugin agents but under a different naming we hadn't tried. Update the harness instead of filing.
- **Mixed** → narrow the issue's scope before filing.

### Revert

After testing: restore `agents=sdk_agents,` and remove the `# DERISK` comment.

---

## Test 2 — Try `setting_sources=["user", "project"]`

The harness uses `setting_sources=["project"]` for hermetic container
behavior. The SDK's internal `_apply_skills_defaults` defaults to
`["user", "project"]` when unset. Maybe plugin discovery requires
`"user"` for some reason.

### Patch

In the same `_build_sdk_options()` function, change:

```python
setting_sources=["project"],
```

to:

```python
setting_sources=["user", "project"],  # DERISK: see if plugin loader needs user source
```

(This is in addition to or after Test 1's revert — apply one change at a time.)

### Test

Re-run the Test 1 prompts, plus:

4. `/cgf status` — see if slash command becomes invokable.

### Outcomes

- **Plugin agents/commands work with `["user", "project"]` but not `["project"]`** → not a bug, just a doc gap. Update harness, don't file. Note this in CLAUDE.md gotchas.
- **Same failures** → confirms `setting_sources` isn't the missing piece for issue 5a / 5b.

### Revert

Restore `setting_sources=["project"],`.

---

## Test 3 — Try via `claude plugin install` instead of `plugins=`

The CLI has a different plugin pathway: `claude plugin marketplace add` +
`claude plugin install`. Plugins installed this way land in
`~/.claude/plugins/` and the CLI loads them automatically (no
`plugins=` field in Python options needed).

This tests whether the canonical user-facing flow works, even if
`plugins=` doesn't.

### Steps inside the container

```bash
# Inside the container shell (docker compose exec -it main-agent bash)
claude plugin marketplace add https://github.com/andisab/swe-marketplace
claude plugin install research-team@swe-marketplace
ls ~/.claude/plugins/  # Should show research-team
```

Then in the harness `_build_sdk_options()`, *temporarily* drop
`plugins=` entirely (or set to `[]`) and use `setting_sources=["user"]`
to discover the user-installed plugins.

### Test

5. `Use the Task tool with subagent_type "research-team:research-specialist" to say hi.`

### Outcomes

- **Works via `~/.claude/plugins/` flow but not via `plugins=`** → strong confirmation of 5a. The SDK has two plugin loading paths and only one (the install-flow one) actually surfaces resources to Task. File 5a referencing the install-flow as proof of capability.
- **Fails both ways** → bigger gap than 5a alone. Update issue body to make this clear.
- **Works via install flow at parity with `plugins=`** (i.e. both fail equivalently) → SDK plugin loading from disk is broken in streaming mode regardless of pathway. Reframe issue.

### Revert

Restore the original `plugins=` and `setting_sources=["project"]`.
Optionally `claude plugin uninstall research-team` to clean up the
container's user dir.

---

## Decision matrix after the three tests

| Test 1 | Test 2 | Test 3 | Conclusion |
|---|---|---|---|
| All fail | Same | Both fail | File 5a + 5b with strong evidence |
| All fail | Works | n/a | Don't file. Update harness `setting_sources`. Document gotcha. |
| All fail | Same | Install-flow works | File 5a/5b with the install-flow as a comparison |
| Mixed in 1 | — | — | Narrow issue scope before filing |

## Public/private repo link decision

The drafts at `5a-...md` and `5b-...md` link to specific commits on
`andisab/casdk-harness`. Two clean options:

1. **Wait for the repo to go public, then file with links.** Simpler.
2. **File now without external links.** Inline the relevant code excerpts
   directly in the issue body (~20-30 lines for 5a's `_load_plugin_agents`,
   ~15 lines for 5b's slash command path). I can prepare these inline
   versions in `5a-inline.md` / `5b-inline.md` if you want to file
   immediately.

## Time budget

| Test | Duration |
|---|---|
| 1 — agents={} | 5 min (3 prompts + revert) |
| 2 — setting_sources expand | 5 min (4 prompts + revert) |
| 3 — install flow | 15 min (CLI install + reconfigure + 1 prompt + revert + uninstall) |
| **Total** | **~25 min** |

If all three tests cleanly confirm the issues, file with confidence.
If any test reveals a config we should adopt, fix the harness instead
and skip filing.
