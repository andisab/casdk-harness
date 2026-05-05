# SDK Upstream Issue Drafts

> **Status after de-risk pass (2026-05-05):** One issue (5b) is **real**
> and ready to file. One issue (5a) was **invalidated** by the de-risk
> and is archived as not-filed. See [`DERISK-RESULTS.md`](./DERISK-RESULTS.md)
> for the full test matrix and decision rationale.

## Issue 5b — Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions

**File:** [`5b-plugin-slash-commands.md`](./5b-plugin-slash-commands.md)
**Status:** Ready to file. Self-contained — does not depend on any
external repo link.

**One-line:** Sending a plugin-defined slash command (e.g. `/cgf status`)
through `ClaudeSDKClient.query()` returns `success` after ~10-20 ms
with `num_turns=0` and zero tokens — neither expanded into a prompt
nor errored as unrecognized. The same command works in the standalone
`claude` TUI.

**Evidence strength after de-risk:** The bug reproduces across both
plugin loading pathways (`plugins=[]` and `claude plugin install`),
both `setting_sources` variants (`["project"]` and `["user", "project"]`),
and multiple plugins from different sources. The probe is small enough
(~120 LoC) to be inlined in the issue body, so no external repo link
is needed.

**Why it matters:** Worse than a hard error. Chat-style harness UIs
display a successful round-trip with empty output; users can't tell
whether the command was rejected, misspelled, or doing background
work. Real-world example: the casdk-harness shipped a non-functional
`CommandRegistry` for two release cycles before the gap was
understood, then deleted it once it was clear nothing was wired up
to dispatch the registered commands.

## Issue 5a — Archived (not filed)

**File:** [`archived/5a-plugin-agent-namespacing-NOT-FILED.md`](./archived/5a-plugin-agent-namespacing-NOT-FILED.md)
**Status:** Archived as not-filed. The de-risk pass showed that the
SDK's `plugins=` field correctly exposes plugin sub-agents to the
Task tool — both bare names and `plugin:agent` namespacing work. The
original Phase 3 finding was an artifact of the synthesizer producing
CLI-invalid `plugin.json` files; once those were fixed in 3a (commit
`0e8b31e`), plugin agents became reachable, but the harness was
already programmatically registering them via `agents=` and we never
tested without the workaround until the de-risk pass.

**Implication for the harness:** the `_register_agents` /
`_parse_agent_file` / `get_all_agents` methods in
`src/harness/plugin_manager.py` are now redundant, as is the
`agents=sdk_agents` wiring in `agent.py` `_build_sdk_options()`.
Removing them is a ~50-LoC further simplification, queued as a
**Block 3.5 follow-up commit** before Block 4 starts. Tests 1a/1b/1c
in `DERISK-RESULTS.md` are the proof.

---

## Filing checklist

After review, file 5b via `gh`:

```bash
gh issue create \
  --repo anthropics/claude-agent-sdk-python \
  --title "Plugin slash commands silently no-op in ClaudeSDKClient streaming sessions (0 turns, 0 tokens, no error)" \
  --body-file docs/sdk-upstream-issues/5b-plugin-slash-commands.md
```

5b's body has no external links and no `[#TBD]` placeholders to fix
post-filing — it's complete as-is.

## What I'm asking you to check before filing 5b

- **Tone.** The draft frames the gap as a request for behavior
  alignment, not a complaint. Adjust if you'd prefer warmer/cooler.
- **Repro accuracy.** I assert SDK 0.1.72; the matrix in
  `DERISK-RESULTS.md` was run against this version. Confirm you'd
  file at this exact pin (vs. retesting on a newer point release first).
- **Probe attachment.** I included an inline minimal probe (~30 LoC)
  in the body. The full `scripts/derisk_plugin_loading.py` (120 LoC)
  is committed in the harness for future regression testing — happy
  to also attach as a gist or in a comment if reviewers want it.
- **"Companion finding" footnote.** The body mentions that plugin
  agents *do* work via Task. Trim or expand this section based on
  whether you think it's helpful context or noise.

## Files in this directory

| File | Purpose |
|---|---|
| `README.md` (this file) | Review surface and filing instructions |
| `5b-plugin-slash-commands.md` | The issue body to file |
| `DERISK-RESULTS.md` | Test matrix + decision rationale (links from 5b) |
| `PRE-FILING-DERISK.md` | Original de-risk plan; superseded by results |
| `archived/5a-plugin-agent-namespacing-NOT-FILED.md` | Archived original 5a draft, kept for archaeology |
