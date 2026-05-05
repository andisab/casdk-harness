# SDK Upstream Issue 5b — Plugin slash commands silently no-op in `ClaudeSDKClient` streaming sessions

**Target repo:** https://github.com/anthropics/claude-agent-sdk-python

**Suggested title:**

> Plugin slash commands not invokable from `ClaudeSDKClient` streaming sessions (silent no-op, not surfaced as error)

**Body:**

---

### Summary

When a plugin loaded via `ClaudeAgentOptions(plugins=[{"type": "local", "path": ...}])` declares slash commands in `<path>/commands/*.md`, sending the slash command from a `ClaudeSDKClient` streaming session is silently swallowed by the underlying CLI. The session returns `ResultMessage(subtype='success', num_turns=0, total_cost_usd=0)` after ~20 ms, with no model invocation and no error surfaced to the consumer.

This is a worse failure mode than a hard "unknown command" error: the consumer's interactive UI displays a successful round-trip with empty output, leaving the user uncertain whether the command was rejected, misspelled, or is doing background work.

### Repro

SDK version: `claude-agent-sdk-python` 0.1.72.

1. Plugin at `/tmp/myplugin/` with a slash command:

   ```
   /tmp/myplugin/
   ├── .claude-plugin/
   │   └── plugin.json    # {"name": "my-plugin", "version": "0.1.0", "commands": ["./commands/hello.md"]}
   └── commands/
       └── hello.md       # ---\ndescription: Test command\nargument-hint: <name>\n---\nSay hello to $1
   ```

2. Validate:

   ```bash
   claude plugin validate /tmp/myplugin
   # ✔ Validation passed
   ```

3. Connect a streaming client and send the slash command:

   ```python
   options = ClaudeAgentOptions(
       plugins=[{"type": "local", "path": "/tmp/myplugin"}],
       allowed_tools=["Read", "Bash"],
       setting_sources=["project"],
       skills="all",
       model="sonnet",
       system_prompt="...",
   )
   client = ClaudeSDKClient(options=options)
   await client.connect()
   async for msg in client.query("/hello world"):
       print(msg)
   ```

4. **Observed output:**

   ```
   SystemMessage(subtype='init', ...)
   ResultMessage(subtype='success', duration_ms=21, num_turns=0,
                 total_cost_usd=0, usage={'input_tokens': 0, 'output_tokens': 0, ...})
   ```

   No `AssistantMessage`, no `ToolUseBlock`, no error. The slash command was neither expanded into a prompt nor reported as unrecognized.

### Expected (or proposed)

Pick one of:

1. **Expand and forward** — match the standalone `claude` TUI's behavior: substitute `$1`/`$ARGUMENTS` placeholders into the command body and forward the result to the model, emitting the usual `AssistantMessage`/`ResultMessage` stream. This is the most useful behavior for SDK consumers.

2. **Surface a clear error** — return a `tool_use_error`-style payload or a dedicated `ResultMessage` subtype indicating either "Unknown slash command" or "Slash commands not supported in `ClaudeSDKClient` streaming mode," so consumers can detect the failure and either fall back (e.g., dispatch the command body manually) or surface the error to the user.

The current silent-no-op behavior is the worst of both worlds: consumers cannot tell whether the command worked, and there is no signal to write a fallback against.

### Impact

Any SDK-based harness that exposes a chat-style UI to its users (the casdk-harness, and any similar wrapper) cannot surface plugin slash commands to those users. The only workaround is to either (a) bypass the SDK and shell out to the standalone `claude` TUI, which loses streaming/observability/programmatic control; or (b) reimplement slash-command parsing and template expansion in the harness itself, which duplicates the SDK CLI's existing logic.

For two release cycles, the casdk-harness shipped a `CommandRegistry` that registered every plugin command but had no functional dispatch path — confirmed by code archaeology, never integrated into the interactive loop. This was deleted in [casdk-harness commit `d28b9ac`](https://github.com/andisab/casdk-harness/commit/d28b9ac) once the gap was understood.

### Verified

- 2026-05-04 in casdk-harness post-Phase-2 smoke tests (`/cgf status` against `cgf-agents` plugin).
- Same observation against `research-team` and `context-engineering` plugin commands.

### Related

Companion issue [#TBD] — Plugin agents not exposed to Task tool with `plugin:agent` namespacing. Same root cause class (SDK's `plugins=` field doesn't fully surface plugin resources to runtime consumers in streaming mode); they may share a fix.
