---
name: tool-creation
description: >
  Use this skill when creating MCP tools, MCP servers, or custom tool integrations for Claude Code.
  Tools are programmatic functions that extend Claude's capabilities through the Model Context Protocol.
  Helps design tools with proper schemas, error handling, and server registration. Automatically
  invoked when user requests "create a tool", "make an MCP server", "add custom tool", "build MCP
  integration", "tool development", or mentions MCP server implementation.

  Activate for:
  - "Create a tool for Docker management"
  - "Build an MCP server for my API"
  - "Add a custom tool that queries our database"
  - "Make an MCP integration for Slack"
  - "How do I write an MCP tool?"

  Do NOT use for:
  - Configuring existing MCP servers (use plugin-development or official mcp-integration skill)
  - Creating skills, agents, or commands (use their respective skills)
  - General API development (not MCP-specific)
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(mkdir:*), Bash(tree:*), Bash(ls:*), mcp__Conventions__search_conventions
---

# Tool Creation Skill

This skill helps create production-ready MCP tools and servers for Claude Code following the Claude Agent SDK patterns and best practices.

## Tools vs Skills vs Agents vs Commands vs Hooks

| Need | Use | Example |
|------|-----|---------|
| Programmatic API/function, external service integration, custom data source | **Tool** (MCP server) | Docker management, database queries, API calls |
| Autonomous capability (model-invoked) | **Skill** | PDF processing, code formatting |
| Specialized AI assistant | **Agent** (sub-agent) | PostgreSQL expert, security auditor |
| User-invoked reusable prompt | **Command** (slash command) | `/deploy`, `/review` |
| Lifecycle event automation | **Hook** | Auto-format on save, audit logging |

**When to create a Tool**: You need Claude to call a programmatic function that interacts with external systems, performs computations, or accesses data sources that Claude can't reach through its built-in tools.

## MCP Server Types

### In-Process Python Server

Runs in the same Python process as the agent. Best for:
- Fast startup (no subprocess spawn)
- Direct access to Python libraries
- Easy debugging (same process, same exceptions)
- Tools that need shared state or singletons

**Examples in this harness**: `docker/server.py`, `context7/server.py`, `memory/server.py`

### In-Process TypeScript Server

Runs in the same Node.js process. Best for:
- Node.js-based agent environments
- NPM ecosystem integrations
- TypeScript type safety with Zod schemas

### Subprocess Server

Runs as a separate process via stdio. Best for:
- Third-party MCP servers from npm/pip
- Language-agnostic servers
- Isolation from the main agent process
- Servers that need their own runtime (Node.js, Python, etc.)

**Examples in this harness**: `playwright`, `puppeteer` (configured in `.mcp.json`)

## Tool Definition Best Practices

### Naming

- Use `snake_case` for tool names: `list_containers`, `search_nodes`
- Start with a descriptive verb: `get_`, `list_`, `create_`, `delete_`, `search_`, `update_`
- Be specific: `container_logs` not `logs`, `search_nodes` not `search`

### Descriptions

The description is critical for Claude's tool selection:

```python
# Good - specific, tells Claude when to use it
@tool(
    "container_logs",
    "Get logs from a Docker container by name or ID",
    {"container": str, "tail": int},
)

# Bad - too vague
@tool(
    "get_logs",
    "Gets some logs",
    {"target": str},
)
```

**Rules**:
- First sentence matters most (Claude uses it for selection)
- Include the object type (container, entity, file, etc.)
- Mention required parameters in the description
- State what the tool returns

### Input Schemas

Use Python type hints for the schema parameter:

```python
# Simple types
{"container": str, "tail": int}

# Optional with defaults (handled in handler)
{"query": str, "limit": int}  # limit defaults to 10 in handler

# Complex types
{"entities": list}  # list of dicts
{"config": dict}    # nested object
```

### Return Format

All tools must return the MCP content format:

```python
return {
    "content": [
        {
            "type": "text",
            "text": "Your result string here",
        }
    ]
}
```

**Rules**:
- Always return a dict with `content` key containing a list
- Each item has `type` (usually `"text"`) and corresponding data
- Format text for readability (newlines, indentation, structured output)
- Include error context in error responses

### Error Handling Pattern

Follow validate-process-format-return:

```python
async def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    # 1. Validate inputs
    required_param = args.get("param", "").strip()
    if not required_param:
        return {
            "content": [{"type": "text", "text": "Error: param is required"}]
        }

    # 2. Process (with try/except)
    try:
        result = do_work(required_param)
    except SpecificError as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Unexpected error: {e}"}]
        }

    # 3. Format output
    formatted = format_result(result)

    # 4. Return
    return {
        "content": [{"type": "text", "text": formatted}]
    }
```

## Python In-Process Server Pattern

Based on `src/mcp_servers/docker/server.py`:

```python
"""My Custom MCP server for Claude Agent SDK.

Provides [capability] through the Model Context Protocol.
Tools include [tool1], [tool2], and [tool3].
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "tool_name",
    "Clear description of what this tool does",
    {"param1": str, "param2": int},
)
async def tool_name(args: dict[str, Any]) -> dict[str, Any]:
    """Docstring for the tool handler.

    Args:
        args: Dictionary with:
            - param1: Description (required)
            - param2: Description (optional, default: 10)

    Returns:
        Dictionary with result content
    """
    # Validate inputs
    param1 = args.get("param1", "").strip()
    if not param1:
        return {
            "content": [{"type": "text", "text": "Error: param1 is required"}]
        }

    param2 = args.get("param2", 10)

    try:
        # Process
        result = await do_something(param1, param2)

        # Format and return
        return {
            "content": [{"type": "text", "text": str(result)}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}]
        }


# Create and export the MCP server
my_server = create_sdk_mcp_server(
    name="my-server",
    version="1.0.0",
    tools=[tool_name],
)
```

### Key elements:
1. **Imports**: `create_sdk_mcp_server` and `tool` from `claude_agent_sdk`
2. **`@tool` decorator**: Takes name, description, and schema dict
3. **Async handler**: Always `async def`, takes `dict[str, Any]`, returns `dict[str, Any]`
4. **Server export**: `create_sdk_mcp_server()` with name, version, and tools list

## TypeScript In-Process Server Pattern

Equivalent using the TypeScript SDK:

```typescript
import { createSdkMcpServer, tool } from "@anthropic/claude-agent-sdk";
import { z } from "zod";

const myTool = tool({
  name: "tool_name",
  description: "Clear description of what this tool does",
  schema: z.object({
    param1: z.string().describe("Description of param1"),
    param2: z.number().optional().default(10).describe("Description of param2"),
  }),
  handler: async (args) => {
    if (!args.param1) {
      return {
        content: [{ type: "text", text: "Error: param1 is required" }],
      };
    }

    try {
      const result = await doSomething(args.param1, args.param2);
      return {
        content: [{ type: "text", text: String(result) }],
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Error: ${error}` }],
      };
    }
  },
});

export const myServer = createSdkMcpServer({
  name: "my-server",
  version: "1.0.0",
  tools: [myTool],
});
```

## Subprocess Server Configuration

Subprocess MCP servers are configured in `.mcp.json` files.

### Configuration Locations

| Location | Scope | Example |
|----------|-------|---------|
| `.claude/.mcp.json` | Project-specific | Project tools |
| `~/.claude/.mcp.json` | User-wide | Personal tools |
| `plugin-name/.mcp.json` | Plugin-bundled | Plugin tools |

### Format

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["@package/mcp-server@latest"],
      "env": {
        "API_KEY": "your-key-here"
      }
    }
  }
}
```

### Real examples from this harness (`src/harness/config/.mcp.json`):

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    },
    "puppeteer": {
      "command": "npx",
      "args": ["puppeteer-mcp-server"]
    }
  }
}
```

### Common subprocess server patterns:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
      }
    },
    "custom-python": {
      "command": "python",
      "args": ["-m", "my_mcp_server"]
    }
  }
}
```

## Server Registration

### In-Process Registration

In-process servers register via the `mcp_servers` dict in `ClaudeAgentOptions`:

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from my_servers.custom import custom_server

options = ClaudeAgentOptions(
    mcp_servers={
        "custom": custom_server,  # In-process server object
    },
    # ... other options
)
client = ClaudeSDKClient(options=options)
```

### Tool Naming Convention

Tools become accessible as `mcp__<server-name>__<tool-name>`:
- Server `docker` + tool `list_containers` = `mcp__docker__list_containers`
- Server `memory` + tool `search_nodes` = `mcp__memory__search_nodes`

This naming is automatic when registering via `mcp_servers`.

### Subprocess Registration

Subprocess servers are auto-discovered from `.mcp.json` files. The SDK reads the config and spawns the process on connect.

## Advanced Patterns

### Stateful Server with Class-Based State

Based on `src/mcp_servers/memory/server.py` (KnowledgeGraph pattern):

```python
"""Stateful MCP server with persistent storage."""

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


class MyState:
    """Manages state with file persistence."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                self.data = json.load(f)

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.data, f)

    def add(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._save()


# Initialize singleton
_state = MyState(Path("/data/state.json"))


@tool("add_entry", "Add an entry to the state store", {"key": str, "value": str})
async def add_entry(args: dict[str, Any]) -> dict[str, Any]:
    key = args.get("key", "").strip()
    value = args.get("value", "").strip()
    if not key or not value:
        return {"content": [{"type": "text", "text": "Error: key and value are required"}]}

    _state.add(key, value)
    return {"content": [{"type": "text", "text": f"Added: {key} = {value}"}]}
```

**Key points**:
- State class initialized at module level as singleton
- File persistence with `_load()` / `_save()` methods
- Tool handlers reference the singleton instance

### Graceful Dependency Handling

Based on `src/mcp_servers/docker/server.py`:

```python
import docker
from docker.errors import DockerException

# Try to connect, but don't fail if unavailable
try:
    docker_client = docker.from_env()
except DockerException as e:
    docker_client = None
    _docker_error = str(e)

@tool("list_containers", "List Docker containers", {"all": bool})
async def list_containers(args: dict[str, Any]) -> dict[str, Any]:
    # Gracefully handle unavailable dependency
    if docker_client is None:
        return {
            "content": [{"type": "text", "text": f"Error: Docker unavailable - {_docker_error}"}]
        }
    # ... normal operation
```

**Key points**:
- Try to initialize at import time
- Store error message if initialization fails
- Every tool handler checks availability before proceeding

### Separable Handlers for Testability

Based on `src/mcp_servers/memory/server.py` (raw handler + @tool wrapper pattern):

```python
# Raw handler (directly testable)
async def _search_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Search implementation - directly testable without @tool decorator."""
    query = args.get("query", "").strip()
    if not query:
        return {"content": [{"type": "text", "text": "Error: query is required"}]}
    # ... implementation
    return {"content": [{"type": "text", "text": result}]}


# @tool wrapper (for SDK registration)
@tool("search", "Search for items", {"query": str})
async def search(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for search tool."""
    return await _search_handler(args)
```

**Benefits**:
- `_search_handler` can be tested directly with `pytest` without SDK setup
- `search` wrapper handles SDK registration
- Clean separation of concerns

### External API Integration

Based on `src/mcp_servers/context7/server.py`:

```python
import os
from typing import Any

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

API_BASE = "https://api.example.com/v1"
REQUEST_TIMEOUT = 30.0

def _get_headers() -> dict[str, str]:
    """Build headers with optional API key."""
    headers = {"Accept": "application/json"}
    api_key = os.getenv("EXAMPLE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers

@tool("query_api", "Query the example API", {"endpoint": str, "params": dict})
async def query_api(args: dict[str, Any]) -> dict[str, Any]:
    endpoint = args.get("endpoint", "").strip()
    if not endpoint:
        return {"content": [{"type": "text", "text": "Error: endpoint is required"}]}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE}/{endpoint}",
                params=args.get("params", {}),
                headers=_get_headers(),
            )

            if response.status_code == 429:
                return {"content": [{"type": "text", "text": "Rate limited. Retry later."}]}
            if response.status_code != 200:
                return {"content": [{"type": "text", "text": f"API error: {response.status_code}"}]}

            return {"content": [{"type": "text", "text": response.text}]}

    except httpx.TimeoutException:
        return {"content": [{"type": "text", "text": "Error: Request timed out"}]}
    except httpx.RequestError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
```

**Key points**:
- Use `httpx.AsyncClient` for async HTTP
- Handle rate limits (429) explicitly
- Support optional API keys via environment variables
- Set reasonable timeouts

## Testing and Debugging

### Unit Testing Async Handlers

```python
import pytest
from my_server import _search_handler

@pytest.mark.asyncio
async def test_search_requires_query():
    result = await _search_handler({})
    assert "Error" in result["content"][0]["text"]

@pytest.mark.asyncio
async def test_search_returns_results():
    result = await _search_handler({"query": "test"})
    assert result["content"][0]["type"] == "text"
    assert "test" in result["content"][0]["text"].lower()

@pytest.mark.asyncio
async def test_search_empty_query():
    result = await _search_handler({"query": ""})
    assert "Error" in result["content"][0]["text"]
```

### Verifying Schema Validation

```python
@pytest.mark.asyncio
async def test_invalid_param_type():
    """Handler should gracefully handle wrong types."""
    result = await _handler({"count": "not-a-number"})
    # Should not crash - either coerce or return error
    assert result["content"][0]["type"] == "text"
```

### Common Debugging Scenarios

**Tool not appearing in Claude's available tools**:
1. Verify the server is registered in `mcp_servers` dict
2. Check server name and tool name follow naming conventions
3. Confirm `create_sdk_mcp_server()` includes the tool in its `tools` list

**Tool returns empty or unexpected results**:
1. Test the raw handler function directly
2. Check the return format matches `{"content": [{"type": "text", "text": "..."}]}`
3. Verify input parameter names match what Claude sends

**Subprocess server fails to start**:
1. Test the command manually: `npx @package/mcp-server`
2. Check `.mcp.json` syntax is valid JSON
3. Verify environment variables are set
4. Check npm package exists and is installable

## File Organization

### In-Process Server

```
src/mcp_servers/
├── my_server/
│   ├── __init__.py          # Export: from .server import my_server
│   └── server.py            # Server implementation
├── docker/
│   ├── __init__.py
│   └── server.py
├── context7/
│   ├── __init__.py
│   └── server.py
└── memory/
    ├── __init__.py
    └── server.py
```

### Subprocess Server Config

```
project/
├── .claude/
│   └── .mcp.json            # Project-level subprocess servers
├── src/harness/config/
│   └── .mcp.json            # Harness-bundled subprocess servers
└── plugins/my-plugin/
    └── .mcp.json             # Plugin-bundled subprocess servers
```

### Plugin MCP Server

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── mcp_servers/
│   └── custom/
│       ├── __init__.py
│       └── server.py
└── .mcp.json                 # Subprocess servers for this plugin
```

## Common Mistakes

### Missing Return Format

```python
# WRONG - returns raw string
async def my_tool(args):
    return "result"

# CORRECT - returns MCP content format
async def my_tool(args):
    return {"content": [{"type": "text", "text": "result"}]}
```

### Overly Broad Descriptions

```python
# WRONG - Claude won't know when to use this
@tool("do_stuff", "Does things with data", {"data": str})

# CORRECT - specific about capability and use case
@tool("parse_csv_file", "Parse a CSV file and return structured data as formatted text", {"file_path": str})
```

### No Input Validation

```python
# WRONG - crashes on missing input
async def my_tool(args):
    result = process(args["required_field"])  # KeyError if missing

# CORRECT - validate first
async def my_tool(args):
    field = args.get("required_field", "").strip()
    if not field:
        return {"content": [{"type": "text", "text": "Error: required_field is required"}]}
    result = process(field)
```

### Too Many Parameters

```python
# WRONG - overwhelming for Claude to use
@tool("complex_query", "Query database", {
    "table": str, "columns": list, "where": dict, "order_by": str,
    "limit": int, "offset": int, "group_by": str, "having": dict,
    "join": list, "distinct": bool, "timeout": int,
})

# CORRECT - focused, minimal parameters
@tool("query_table", "Query a database table with optional filtering", {
    "table": str, "query": str, "limit": int,
})
```

### Sync Blocking in Async Handler

```python
# WRONG - blocks the event loop
async def my_tool(args):
    result = requests.get(url)  # Sync HTTP blocks!

# CORRECT - use async HTTP
async def my_tool(args):
    async with httpx.AsyncClient() as client:
        result = await client.get(url)  # Non-blocking
```

### Exposing Secrets in Output

```python
# WRONG - leaks connection strings or keys
async def my_tool(args):
    return {"content": [{"type": "text", "text": f"Connected with {connection_string}"}]}

# CORRECT - redact sensitive information
async def my_tool(args):
    return {"content": [{"type": "text", "text": "Connected to database successfully"}]}
```

### Schema Mismatches

```python
# WRONG - schema says "name" but handler reads "entity_name"
@tool("get_entity", "Get entity", {"name": str})
async def get_entity(args):
    entity = args.get("entity_name")  # Never matches!

# CORRECT - schema and handler use same key
@tool("get_entity", "Get entity by name", {"name": str})
async def get_entity(args):
    entity = args.get("name")  # Matches schema
```

## Progressive Loading

For complete, copy-paste-ready scaffolding including multi-tool servers, TypeScript patterns, testing templates, and a best practices checklist, see `templates/tool-template.md`.

---

**Next Steps**: After creating a tool, register the server in your agent's `mcp_servers` configuration, test the tool handlers with unit tests, and verify Claude can discover and use the tools with natural language requests.
