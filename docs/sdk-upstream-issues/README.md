# SDK Upstream Issue Drafts

Two GitHub issue bodies awaiting your review before filing against
[`anthropics/claude-agent-sdk-python`](https://github.com/anthropics/claude-agent-sdk-python).
Both surfaced during Block 3 verification and share a root cause class:
the SDK's `plugins=` field doesn't fully surface plugin resources to
streaming-mode consumers — but the symptoms differ enough to warrant
two issues so the SDK team can close them independently.

## Issue 5a — Plugin agents not exposed to Task tool with `plugin:agent` namespacing

**File:** [`5a-plugin-agent-namespacing.md`](./5a-plugin-agent-namespacing.md)

**One-line:** Plugin sub-agents declared in `<plugin>/agents/*.md` are loaded
by the SDK but cannot be dispatched via the Task tool — neither bare
(`Task(subagent_type="foo")`) nor namespaced (`Task(subagent_type="my-plugin:foo")`).

**Why it matters:** Forces every SDK-based harness to ship a parallel
~100-LoC plugin-agent loader that re-walks `agents/*.md`, parses
frontmatter, and registers each agent under `plugin:agent` keys via the
separate `agents=` parameter. The casdk-harness's `plugin_manager.py`
exists almost entirely to work around this gap.

**Repro shape:** A valid plugin (passes `claude plugin validate`) is
loaded via `plugins=[{"type": "local", "path": "..."}]`. Task dispatch
to any namespacing form returns `Unknown agent`.

**Verified:** 2026-05-04, casdk-harness Phase 3 verification (commit
`f704536`); re-verified post-Phase-2 cleanup (commit `bc3e8db`).

## Issue 5b — Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions

**File:** [`5b-plugin-slash-commands.md`](./5b-plugin-slash-commands.md)

**One-line:** Sending a plugin-defined slash command (e.g. `/cgf status`)
through `ClaudeSDKClient.query()` returns `success` after ~20 ms with
`num_turns=0` and zero tokens — neither expanded into a prompt nor
errored as unrecognized. The same command works in the standalone
`claude` TUI.

**Why it matters:** Worse than a hard error. Chat-style harness UIs
display a successful round-trip with empty output; users can't tell
whether the command was rejected, misspelled, or doing background
work. The casdk-harness shipped a non-functional `CommandRegistry` for
two release cycles before the gap was understood and the registry was
deleted.

**Repro shape:** Plugin with valid `commands/foo.md` (frontmatter +
body with `$1`/`$ARGUMENTS` placeholders). Send `"/foo bar"` via
`ClaudeSDKClient`. Receive `ResultMessage(num_turns=0, total_cost_usd=0)`
with no AssistantMessage and no error.

**Verified:** 2026-05-04, casdk-harness post-Phase-2 smoke (`/cgf status`
against in-tree `cgf-agents` plugin and equivalent commands in
marketplace plugins).

---

## Filing checklist

After review, file via `gh`:

```bash
gh issue create \
  --repo anthropics/claude-agent-sdk-python \
  --title "Plugin agents loaded via plugins=[] not exposed to Task tool with plugin:agent namespacing" \
  --body-file docs/sdk-upstream-issues/5a-plugin-agent-namespacing.md

gh issue create \
  --repo anthropics/claude-agent-sdk-python \
  --title "Plugin slash commands not invokable from ClaudeSDKClient streaming sessions (silent no-op)" \
  --body-file docs/sdk-upstream-issues/5b-plugin-slash-commands.md
```

Each issue body has one `[#TBD]` placeholder in the **Related** section.
After both are filed, edit each draft to replace `[#TBD]` with the other
issue's number, then commit the cross-link update.

## What I'm asking you to check before filing

- **Tone.** Each draft frames the gap as a request for behavior alignment, not a complaint. Adjust if you'd prefer warmer/cooler phrasing.
- **Repro accuracy.** I assert SDK 0.1.72 in both. Confirm you'd file at this exact pin (vs. retesting on a newer point release first).
- **Workaround link.** Both drafts link to `andisab/casdk-harness` at commit SHAs (`bc3e8db` for 5a; `d28b9ac` for 5b). If you'd rather not link the personal fork, swap for `provectus/casdk-harness` or omit the link.
- **Issue 5b's "Expected" section** lists two alternative fixes (expand-and-forward vs. clear-error). If you have a strong preference, narrow it to one.
- **Both drafts are self-contained** — they don't assume the reader has cross-linked context. Trim or expand as you see fit.
