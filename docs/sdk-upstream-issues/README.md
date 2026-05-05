# SDK Upstream Issue Drafts — final outcome

> **Status after both de-risk passes (2026-05-05):** Both originally
> drafted issues turned out to be **invalid** — neither is filed. See
> [`DERISK-RESULTS.md`](./DERISK-RESULTS.md) for the full test
> matrices.

## Summary

| Issue | Status | Reason |
|---|---|---|
| 5a — Plugin agents not exposed to Task tool with namespacing | **NOT FILED** | SDK does expose them; original Phase 3 finding was an artifact of CLI-invalid `plugin.json` files at the time |
| 5b — Plugin slash commands silently no-op in streaming mode | **NOT FILED** | Plugin slash commands are registered under `/plugin:command` namespacing; original test sent bare `/cgf` which has no registered match. Silent no-op on unknown commands is consistent SDK behavior. |

## What we actually found

The "SDK gaps" we initially identified turned out to be:

1. **A synthesizer bug producing invalid `plugin.json` files** —
   fixed in Block 3 Step 3a. Once fixed, plugin agents became
   reachable via `plugins=` and the Task tool with both bare and
   namespaced forms.
2. **An incorrect smoke prompt** — we typed `/cgf status` but the
   SDK had registered the command as `cgf-agents:cgf` (namespaced).
   The SDK silently no-ops unknown slash commands (built-in or
   plugin), which is consistent behavior. Sending the namespaced
   form `/cgf-agents:cgf status` works perfectly.

Both findings updated CLAUDE.md "Known Limitations" with the relevant
gotchas so future sessions don't relitigate the same conclusions.

## Slash commands are not deprecated

On 24 January 2026 Anthropic merged slash commands into the Skills
system. Both live in `~/.claude/skills/` (or in plugins'
`commands/` and `skills/` directories), both use markdown + YAML
frontmatter, and both are invoked with `/`. Skills additionally
support autonomous invocation by Claude. Legacy `.claude/commands/`
still works. There is a dedicated SDK doc page —
[Slash Commands in the SDK](https://code.claude.com/docs/en/agent-sdk/slash-commands).

## Files in this directory

| File | Purpose |
|---|---|
| `README.md` (this file) | Final outcome and summary |
| `DERISK-RESULTS.md` | Full test matrix from both de-risk passes |
| `archived/5a-plugin-agent-namespacing-NOT-FILED.md` | Original 5a draft, kept for archaeology |
| `archived/5b-plugin-slash-commands-NOT-FILED.md` | Original 5b draft, kept for archaeology |
| `archived/PRE-FILING-DERISK.md` | Original de-risk plan, superseded by results |

## Probe scripts retained

`scripts/derisk_plugin_loading.py` and
`scripts/derisk_slash_init.py` are committed in the harness as
regression probes against future SDK releases. Re-run after any SDK
bump to confirm plugin-agent dispatch and slash-command registration
still work as expected.
