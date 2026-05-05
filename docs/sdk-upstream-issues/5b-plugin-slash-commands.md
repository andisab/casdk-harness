# SDK Upstream Issue 5b — Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions

**Target repo:** https://github.com/anthropics/claude-agent-sdk-python

**Suggested title:**

> Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions (0 turns, 0 tokens, no error)

**Body:**

---

### Summary

Plugin-defined slash commands sent through `ClaudeSDKClient.query()` are
silently swallowed by the underlying CLI in streaming mode. The session
returns `ResultMessage(subtype='success', num_turns=0, total_cost_usd=0,
is_error=False)` after 8-20 ms, with no model invocation and no error
surfaced to the consumer. The same plugin commands expand correctly
when invoked from the standalone `claude` TUI.

This is a worse failure mode than a hard "unknown command" error: SDK
consumers building chat-style UIs see a successful round-trip with
empty output, leaving the user with no signal whether the command was
rejected, misspelled, or doing background work.

### Repro

SDK version: `claude-agent-sdk-python` 0.1.72.

The behavior reproduces consistently across:

- Both plugin loading pathways:
  - `ClaudeAgentOptions(plugins=[{"type": "local", "path": ...}])`
  - Canonical install flow (`claude plugin marketplace add` + `claude plugin install`) with `setting_sources=["user"]`
- Both `setting_sources` configurations (`["project"]` and `["user", "project"]`)
- Multiple plugins, in-tree and from a marketplace
- Both bare and namespaced slash commands (e.g. `/cgf status`, `/research-team:research foo`)

#### Minimal probe

```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient


async def probe(plugin_path: str, slash: str) -> None:
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": plugin_path}],
        agents={},                   # No programmatic registration — verify SDK loader behavior
        setting_sources=["project"],
        allowed_tools=["Read", "Bash", "Task", "Skill"],
        skills="all",
        model="claude-sonnet-4-5-20250929",
        cwd="/app",
        permission_mode="acceptEdits",
        system_prompt="You are a test probe. Follow instructions literally.",
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(slash)
        async for msg in client.receive_response():
            print(type(msg).__name__, repr(msg)[:200])


asyncio.run(probe("/path/to/my-plugin", "/my-command status"))
```

Where `/path/to/my-plugin` contains a CLI-valid `plugin.json` (passes
`claude plugin validate`) and a `commands/my-command.md` with valid
frontmatter (`description`, optional `argument-hint`) and a body.

#### Observed output

```
SystemMessage SystemMessage(subtype='init', ...)
ResultMessage ResultMessage(subtype='success', duration_ms=13, duration_api_ms=0,
                            is_error=False, num_turns=0, stop_reason=None,
                            total_cost_usd=0, usage={'input_tokens': 0,
                            'output_tokens': 0, ...})
```

No `AssistantMessage`. No `ToolUseBlock`. No error. The command is
neither expanded nor reported.

For comparison, sending the same plugin's *agent* via the Task tool
through the same probe (with `agents={}` workaround intentionally
disabled) **works correctly** — the SDK's `plugins=` field successfully
exposes agents to Task with both bare and `plugin:agent` namespacing.
Only slash command dispatch silently fails.

### Expected (or proposed)

Pick one:

1. **Expand and forward** — substitute `$1`/`$ARGUMENTS` placeholders
   into the command body and forward the resulting prompt to the model,
   matching the standalone `claude` TUI's behavior. This is the most
   useful behavior for SDK consumers building interactive UIs.

2. **Surface a clear error** — return a `tool_use_error`-style payload
   or a dedicated `ResultMessage` subtype indicating "slash commands not
   supported in streaming mode" or "unknown slash command", so SDK
   consumers can detect the failure and fall back gracefully (e.g.
   dispatch the command body manually or surface the error to the user).

The current silent-no-op is the worst of both worlds: consumers cannot
tell whether the command worked, and there is no signal to write a
fallback against.

### Impact

Any SDK-based harness exposing a chat-style UI cannot surface plugin
slash commands to its users. Workarounds are unattractive: shelling
out to the standalone `claude` TUI loses streaming/observability/programmatic
control, and reimplementing slash-command parsing in the harness
duplicates the SDK CLI's existing logic.

A real-world example: the casdk-harness shipped a `CommandRegistry`
that registered every plugin command but had no functional dispatch
path for two release cycles before the gap was understood and the
registry was removed. This was confirmed by code archaeology — the
registry stored commands but had no caller.

### Verified

- 2026-05-05, [DERISK-RESULTS.md](../DERISK-RESULTS.md) test matrix:
  rows "2-slash" / "pre-3" / "3b" all reproduce the silent no-op across
  the two plugin-loading pathways and two `setting_sources` configurations.
- Probe script: a 120-LoC standalone Python script that doesn't depend
  on any harness code is available; happy to attach as a gist if useful.

### Companion finding (not a separate issue)

The same de-risk pass verified that plugin sub-agents *do* surface
correctly to the Task tool via `ClaudeAgentOptions(plugins=[...])` —
both bare names and `plugin:agent` namespacing work end-to-end. So
the gap is specifically in plugin slash commands, not plugin resource
loading in general.
