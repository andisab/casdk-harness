# SDK Upstream Issue 5a — Plugin agents not exposed to Task tool with `plugin:agent` namespacing

**Target repo:** https://github.com/anthropics/claude-agent-sdk-python

**Suggested title:**

> Plugin agents loaded via `plugins=[]` not exposed to Task tool with `plugin:agent` namespacing

**Body:**

---

### Summary

When a plugin is loaded via `ClaudeAgentOptions(plugins=[{"type": "local", "path": "/path/to/plugin"}])`, sub-agents declared in `<path>/agents/*.md` (with valid YAML frontmatter, including `name:`) are auto-loaded but **not addressable from the Task tool under any namespacing scheme** — neither bare (`Task(subagent_type="foo")`) nor plugin-qualified (`Task(subagent_type="my-plugin:foo")`).

To make plugin agents dispatchable, consumers must reimplement plugin-agent loading themselves and pass the result via the separate `agents=` field with manually constructed namespaced keys:

```python
ClaudeAgentOptions(
    plugins=[{"type": "local", "path": "/path/to/plugin"}],
    agents={
        "my-plugin:foo": SDKAgentDefinition(
            description="...",
            prompt="...",
            tools=["..."],
            model="sonnet",
        ),
        # ... one entry per plugin agent
    },
)
```

This duplicates work the SDK already does (parsing the plugin's `plugin.json` and walking `agents/*.md`) and forces every harness or wrapper to ship its own plugin-agent loader.

### Repro

SDK version: `claude-agent-sdk-python` 0.1.72.

1. Plugin at `/tmp/myplugin/`:

   ```
   /tmp/myplugin/
   ├── .claude-plugin/
   │   └── plugin.json     # {"name": "my-plugin", "version": "0.1.0", "agents": ["./agents/foo.md"]}
   └── agents/
       └── foo.md          # ---\nname: foo\ndescription: A test agent\nmodel: sonnet\n---\nyou are foo
   ```

2. Validate the plugin manifest:

   ```bash
   claude plugin validate /tmp/myplugin
   # ✔ Validation passed
   ```

3. Construct an `AgentSession` and connect:

   ```python
   options = ClaudeAgentOptions(
       plugins=[{"type": "local", "path": "/tmp/myplugin"}],
       allowed_tools=["Task"],
       setting_sources=["project"],
       skills="all",
       model="sonnet",
       system_prompt="...",
   )
   client = ClaudeSDKClient(options=options)
   await client.connect()
   ```

4. Dispatch via Task:

   ```python
   await client.query('Use the Task tool to ask my-plugin:foo "say hi"')
   # → tool_use_error: Unknown agent: my-plugin:foo
   ```

   The bare `foo` form also fails:

   ```
   tool_use_error: Unknown agent: foo
   ```

   Available agents (from `Task` tool error context) include only filesystem-discovered agents from `setting_sources=["project"]` (i.e., `<cwd>/.claude/agents/*.md`) — no plugin agents.

### Expected

Plugin agents declared in a plugin's `agents/` directory should be auto-namespaced as `<plugin.json.name>:<agent.YAML.name>` and exposed to the Task tool, matching the convention already in use for plugin skills (which work correctly under `plugin-name:skill-name` namespacing once `skills="all"` is set).

### Workaround in the wild

The casdk-harness ([andisab/casdk-harness](https://github.com/andisab/casdk-harness)) currently maintains a ~100-LoC `PluginManager` that walks each plugin path, parses `agents/*.md` frontmatter, builds `SDKAgentDefinition` objects, and registers them under `plugin:agent` keys via the `agents=` parameter. See [`src/harness/plugin_manager.py`](https://github.com/andisab/casdk-harness/blob/contextgrad-framework/src/harness/plugin_manager.py) at commit `bc3e8db` for the reference implementation.

If this gap is closed, that loader can be deleted entirely.

### Impact

Any SDK-based harness that wants to surface plugin agents to the Task tool must reimplement plugin-agent loading. This is duplicated work and an inconsistency with how plugin skills are surfaced (skills work via the same `plugins=` pathway without an additional `skills=` override map).

### Verified

- 2026-05-04, casdk-harness Phase 3 verification experiment (commit `f704536`).
- Re-verified post-Phase-2 cleanup (commit `bc3e8db`) — the workaround is still required after the harness collapsed its plugin loader to discovery + namespacing only.
