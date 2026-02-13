# MCP Tool/Server Template

This template provides ready-to-use MCP server scaffolding for common integration patterns.

## Template 1: Python In-Process Server (Minimal)

Single-tool server, copy-paste ready:

```python
"""Minimal MCP server for Claude Agent SDK.

Provides [description] through the Model Context Protocol.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "tool_name",
    "Description of what this tool does and when to use it",
    {"param1": str},
)
async def tool_name(args: dict[str, Any]) -> dict[str, Any]:
    """Handle tool_name requests.

    Args:
        args: Dictionary with 'param1' key (required)

    Returns:
        Dictionary with result content
    """
    param1 = args.get("param1", "").strip()
    if not param1:
        return {
            "content": [{"type": "text", "text": "Error: param1 is required"}]
        }

    try:
        result = f"Processed: {param1}"
        return {
            "content": [{"type": "text", "text": result}]
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

---

## Template 2: Python In-Process Server (Full)

Multi-tool server with error handling, dependency management, and testable handlers:

```python
"""Custom MCP server for Claude Agent SDK.

Provides [capability area] through the Model Context Protocol.
Tools include [tool1], [tool2], and [tool3].

Dependencies:
    - [library]: [purpose]
"""

import os
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

# --- Configuration ---

API_BASE_URL = os.getenv("CUSTOM_API_URL", "https://api.example.com/v1")
REQUEST_TIMEOUT = float(os.getenv("CUSTOM_TIMEOUT", "30.0"))
DEFAULT_LIMIT = 50

# --- Dependency Initialization ---
# Graceful handling: server loads even if dependency unavailable

try:
    import some_library
    _client = some_library.Client()
except ImportError:
    _client = None
    _init_error = "some_library not installed. Run: pip install some-library"
except Exception as e:
    _client = None
    _init_error = str(e)


# --- Helper Functions ---

def _format_items(items: list[dict]) -> str:
    """Format a list of items for display."""
    if not items:
        return "No items found"

    lines = []
    for item in items:
        lines.append(f"- {item.get('name', 'unknown')}: {item.get('description', 'N/A')}")
    return "\n".join(lines)


def _check_client() -> dict[str, Any] | None:
    """Check if the client is available. Returns error response or None."""
    if _client is None:
        return {
            "content": [
                {"type": "text", "text": f"Error: Client unavailable - {_init_error}"}
            ]
        }
    return None


# --- Raw Handler Functions (for testing) ---

async def _list_items_handler(args: dict[str, Any]) -> dict[str, Any]:
    """List items with optional filtering."""
    error = _check_client()
    if error:
        return error

    limit = args.get("limit", DEFAULT_LIMIT)
    if not isinstance(limit, int) or limit < 1 or limit > 1000:
        return {
            "content": [{"type": "text", "text": "Error: limit must be between 1 and 1000"}]
        }

    try:
        items = _client.list(limit=limit)
        return {
            "content": [{"type": "text", "text": _format_items(items)}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error listing items: {e}"}]
        }


async def _get_item_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Get a specific item by ID."""
    error = _check_client()
    if error:
        return error

    item_id = args.get("id", "").strip()
    if not item_id:
        return {
            "content": [{"type": "text", "text": "Error: id is required"}]
        }

    try:
        item = _client.get(item_id)
        if not item:
            return {
                "content": [{"type": "text", "text": f"Item '{item_id}' not found"}]
            }

        result = f"Name: {item['name']}\nDescription: {item['description']}\nStatus: {item['status']}"
        return {
            "content": [{"type": "text", "text": result}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error getting item: {e}"}]
        }


async def _create_item_handler(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new item."""
    error = _check_client()
    if error:
        return error

    name = args.get("name", "").strip()
    description = args.get("description", "").strip()

    if not name:
        return {
            "content": [{"type": "text", "text": "Error: name is required"}]
        }

    try:
        item = _client.create(name=name, description=description)
        return {
            "content": [{"type": "text", "text": f"Created item: {item['id']} ({item['name']})"}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error creating item: {e}"}]
        }


# --- @tool Decorated Wrappers ---

@tool(
    "list_items",
    "List available items with optional limit",
    {"limit": int},
)
async def list_items(args: dict[str, Any]) -> dict[str, Any]:
    """List items with optional limit parameter."""
    return await _list_items_handler(args)


@tool(
    "get_item",
    "Get details of a specific item by its ID",
    {"id": str},
)
async def get_item(args: dict[str, Any]) -> dict[str, Any]:
    """Get a specific item by ID."""
    return await _get_item_handler(args)


@tool(
    "create_item",
    "Create a new item with a name and optional description",
    {"name": str, "description": str},
)
async def create_item(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new item."""
    return await _create_item_handler(args)


# --- Create and Export MCP Server ---

custom_server = create_sdk_mcp_server(
    name="custom",
    version="1.0.0",
    tools=[list_items, get_item, create_item],
)
```

---

## Template 3: TypeScript In-Process Server

```typescript
/**
 * Custom MCP server for Claude Agent SDK (TypeScript).
 *
 * Provides [capability] through the Model Context Protocol.
 */

import { createSdkMcpServer, tool } from "@anthropic/claude-agent-sdk";
import { z } from "zod";

// Configuration
const API_BASE = process.env.CUSTOM_API_URL ?? "https://api.example.com/v1";
const TIMEOUT = Number(process.env.CUSTOM_TIMEOUT ?? 30000);

// Tool definitions
const listItems = tool({
  name: "list_items",
  description: "List available items with optional limit",
  schema: z.object({
    limit: z.number().min(1).max(1000).optional().default(50)
      .describe("Maximum number of items to return"),
  }),
  handler: async ({ limit }) => {
    try {
      const response = await fetch(`${API_BASE}/items?limit=${limit}`, {
        signal: AbortSignal.timeout(TIMEOUT),
      });

      if (!response.ok) {
        return {
          content: [{ type: "text" as const, text: `API error: ${response.status}` }],
        };
      }

      const items = await response.json();
      const formatted = items
        .map((item: any) => `- ${item.name}: ${item.description}`)
        .join("\n");

      return {
        content: [{ type: "text" as const, text: formatted || "No items found" }],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error}` }],
      };
    }
  },
});

const getItem = tool({
  name: "get_item",
  description: "Get details of a specific item by ID",
  schema: z.object({
    id: z.string().min(1).describe("The item ID to retrieve"),
  }),
  handler: async ({ id }) => {
    try {
      const response = await fetch(`${API_BASE}/items/${id}`, {
        signal: AbortSignal.timeout(TIMEOUT),
      });

      if (response.status === 404) {
        return {
          content: [{ type: "text" as const, text: `Item '${id}' not found` }],
        };
      }

      if (!response.ok) {
        return {
          content: [{ type: "text" as const, text: `API error: ${response.status}` }],
        };
      }

      const item = await response.json();
      return {
        content: [{
          type: "text" as const,
          text: `Name: ${item.name}\nDescription: ${item.description}\nStatus: ${item.status}`,
        }],
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error}` }],
      };
    }
  },
});

// Export server
export const customServer = createSdkMcpServer({
  name: "custom",
  version: "1.0.0",
  tools: [listItems, getItem],
});
```

---

## Template 4: Subprocess Server Configuration

### Minimal Configuration

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["my-mcp-server"]
    }
  }
}
```

### With Environment Variables

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "@org/mcp-server@latest"],
      "env": {
        "API_KEY": "${CUSTOM_API_KEY}",
        "API_URL": "https://api.example.com"
      }
    }
  }
}
```

### Multiple Servers

```json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    },
    "database": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      }
    },
    "custom-python": {
      "command": "python",
      "args": ["-m", "my_custom_server"],
      "env": {
        "LOG_LEVEL": "info"
      }
    }
  }
}
```

### Common npm MCP Packages

| Package | Purpose | Command |
|---------|---------|---------|
| `@playwright/mcp` | Browser automation (DOM) | `npx @playwright/mcp@latest` |
| `puppeteer-mcp-server` | Browser automation (visual) | `npx puppeteer-mcp-server` |
| `@modelcontextprotocol/server-filesystem` | File system access | `npx -y @modelcontextprotocol/server-filesystem /path` |
| `@modelcontextprotocol/server-postgres` | PostgreSQL queries | `npx -y @modelcontextprotocol/server-postgres` |
| `@modelcontextprotocol/server-github` | GitHub API | `npx -y @modelcontextprotocol/server-github` |
| `@modelcontextprotocol/server-slack` | Slack messaging | `npx -y @modelcontextprotocol/server-slack` |

---

## Tool Definition Patterns

### Simple Tool (No Parameters)

```python
@tool("get_status", "Get the current system status", {})
async def get_status(args: dict[str, Any]) -> dict[str, Any]:
    status = check_system()
    return {"content": [{"type": "text", "text": f"Status: {status}"}]}
```

### Required Parameters

```python
@tool(
    "get_user",
    "Get user details by username",
    {"username": str},
)
async def get_user(args: dict[str, Any]) -> dict[str, Any]:
    username = args.get("username", "").strip()
    if not username:
        return {"content": [{"type": "text", "text": "Error: username is required"}]}
    # ...
```

### Optional Parameters with Defaults

```python
@tool(
    "search",
    "Search items with optional filters",
    {"query": str, "limit": int, "category": str},
)
async def search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "").strip()
    if not query:
        return {"content": [{"type": "text", "text": "Error: query is required"}]}

    limit = args.get("limit", 20)
    category = args.get("category", "all")
    # ...
```

### Complex Schema (Nested Objects/Arrays)

```python
@tool(
    "batch_create",
    "Create multiple items at once",
    {"items": list},
)
async def batch_create(args: dict[str, Any]) -> dict[str, Any]:
    items = args.get("items", [])
    if not items:
        return {"content": [{"type": "text", "text": "Error: items array is required"}]}

    created = []
    for item in items:
        name = item.get("name", "").strip()
        if name:
            # process item
            created.append(name)

    return {
        "content": [{"type": "text", "text": f"Created {len(created)} items: {', '.join(created)}"}]
    }
```

### External API Integration (httpx)

```python
import httpx
from typing import Any
from claude_agent_sdk import tool

API_URL = "https://api.example.com"
TIMEOUT = 30.0

@tool("fetch_data", "Fetch data from the example API", {"endpoint": str})
async def fetch_data(args: dict[str, Any]) -> dict[str, Any]:
    endpoint = args.get("endpoint", "").strip()
    if not endpoint:
        return {"content": [{"type": "text", "text": "Error: endpoint is required"}]}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{API_URL}/{endpoint}")

            if response.status_code == 429:
                return {"content": [{"type": "text", "text": "Rate limited. Try again later."}]}
            if response.status_code != 200:
                return {"content": [{"type": "text", "text": f"API error: {response.status_code}"}]}

            return {"content": [{"type": "text", "text": response.text}]}

    except httpx.TimeoutException:
        return {"content": [{"type": "text", "text": "Request timed out"}]}
    except httpx.RequestError as e:
        return {"content": [{"type": "text", "text": f"Network error: {e}"}]}
```

### State Management (Class-Based)

```python
import json
from pathlib import Path
from typing import Any
from claude_agent_sdk import create_sdk_mcp_server, tool


class Cache:
    """Simple key-value cache with file persistence."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            self.data = json.loads(path.read_text())

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data))


_cache = Cache(Path("/data/cache.json"))


@tool("cache_get", "Get a value from the cache", {"key": str})
async def cache_get(args: dict[str, Any]) -> dict[str, Any]:
    key = args.get("key", "").strip()
    if not key:
        return {"content": [{"type": "text", "text": "Error: key is required"}]}

    value = _cache.get(key)
    if value is None:
        return {"content": [{"type": "text", "text": f"Key '{key}' not found in cache"}]}
    return {"content": [{"type": "text", "text": f"{key} = {value}"}]}


@tool("cache_set", "Store a value in the cache", {"key": str, "value": str})
async def cache_set(args: dict[str, Any]) -> dict[str, Any]:
    key = args.get("key", "").strip()
    value = args.get("value", "")
    if not key:
        return {"content": [{"type": "text", "text": "Error: key is required"}]}

    _cache.set(key, value)
    return {"content": [{"type": "text", "text": f"Stored: {key} = {value}"}]}


cache_server = create_sdk_mcp_server(
    name="cache",
    version="1.0.0",
    tools=[cache_get, cache_set],
)
```

---

## Schema Reference

### Python Type Hints to JSON Schema

| Python Type | JSON Schema | Notes |
|-------------|-------------|-------|
| `str` | `{"type": "string"}` | Most common |
| `int` | `{"type": "integer"}` | Whole numbers |
| `float` | `{"type": "number"}` | Decimal numbers |
| `bool` | `{"type": "boolean"}` | True/false flags |
| `list` | `{"type": "array"}` | Arrays of items |
| `dict` | `{"type": "object"}` | Nested objects |

### Common Schema Patterns

| Pattern | Schema Dict | Description |
|---------|-------------|-------------|
| Single required string | `{"name": str}` | One required parameter |
| String + optional int | `{"query": str, "limit": int}` | Required + optional (defaulted in handler) |
| Boolean flag | `{"all": bool}` | Toggle behavior |
| Array input | `{"items": list}` | List of objects |
| No parameters | `{}` | Status/read-only tools |

---

## Server Registration Patterns

### In-Process with SDK (Python)

```python
# In your agent setup (e.g., agent.py)
from my_servers.custom import custom_server

options = ClaudeAgentOptions(
    mcp_servers={
        "custom": custom_server,
        "docker": docker_server,
        "memory": memory_server,
    },
    # ...
)
```

### In-Process with SDK (TypeScript)

```typescript
import { customServer } from "./servers/custom";

const options: ClaudeAgentOptions = {
  mcpServers: {
    custom: customServer,
    // ...
  },
};
```

### Subprocess via .mcp.json

Place in `.claude/.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["my-mcp-server@latest"]
    }
  }
}
```

The SDK automatically discovers and starts subprocess servers from `.mcp.json` on connect.

---

## Testing Templates

### Unit Test Template (pytest + async)

```python
"""Tests for custom MCP server handlers."""

import pytest
from my_server import (
    _list_items_handler,
    _get_item_handler,
    _create_item_handler,
)


class TestListItems:
    """Tests for list_items tool handler."""

    @pytest.mark.asyncio
    async def test_returns_items(self):
        result = await _list_items_handler({"limit": 10})
        assert result["content"][0]["type"] == "text"
        assert "Error" not in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_default_limit(self):
        result = await _list_items_handler({})
        assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_invalid_limit(self):
        result = await _list_items_handler({"limit": -1})
        assert "Error" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_limit_too_large(self):
        result = await _list_items_handler({"limit": 9999})
        assert "Error" in result["content"][0]["text"]


class TestGetItem:
    """Tests for get_item tool handler."""

    @pytest.mark.asyncio
    async def test_requires_id(self):
        result = await _get_item_handler({})
        assert "Error" in result["content"][0]["text"]
        assert "id" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_empty_id(self):
        result = await _get_item_handler({"id": ""})
        assert "Error" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await _get_item_handler({"id": "nonexistent"})
        assert "not found" in result["content"][0]["text"].lower()


class TestCreateItem:
    """Tests for create_item tool handler."""

    @pytest.mark.asyncio
    async def test_requires_name(self):
        result = await _create_item_handler({})
        assert "Error" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_creates_successfully(self):
        result = await _create_item_handler({"name": "test-item", "description": "A test"})
        assert "Created" in result["content"][0]["text"]
```

### Integration Test Template

```python
"""Integration tests for MCP server with SDK."""

import pytest
from claude_agent_sdk import create_sdk_mcp_server
from my_server import list_items, get_item, create_item


class TestServerCreation:
    """Tests for MCP server creation and export."""

    def test_server_creates(self):
        server = create_sdk_mcp_server(
            name="test-server",
            version="1.0.0",
            tools=[list_items, get_item, create_item],
        )
        assert server is not None

    def test_server_has_correct_name(self):
        from my_server import custom_server
        # Verify server was created with expected configuration
        assert custom_server is not None
```

---

## Best Practices Checklist

Before deploying your MCP tool/server, verify:

**Tool Design**:
- [ ] Each tool has a single, clear responsibility
- [ ] Tool names use `snake_case` and start with descriptive verbs
- [ ] Descriptions are specific (not "does things" or "handles data")
- [ ] Parameters are minimal (3-5 max per tool)
- [ ] Schema types match what the handler expects

**Error Handling**:
- [ ] All required parameters are validated before processing
- [ ] Missing parameters return clear error messages
- [ ] Invalid parameter values return helpful guidance
- [ ] External service failures are caught and reported gracefully
- [ ] No unhandled exceptions can crash the server

**Return Format**:
- [ ] All paths return `{"content": [{"type": "text", "text": "..."}]}`
- [ ] Output is formatted for readability (newlines, structure)
- [ ] No sensitive data in output (connection strings, keys, passwords)
- [ ] Empty results have helpful messages (not just empty string)

**Security**:
- [ ] API keys read from environment variables (not hardcoded)
- [ ] Input is sanitized before use in queries/commands
- [ ] No secrets exposed in error messages
- [ ] File paths are validated (no path traversal)

**Testing**:
- [ ] Raw handler functions have unit tests
- [ ] Error paths are tested (missing params, invalid values, service down)
- [ ] Return format is verified in every test
- [ ] Edge cases covered (empty strings, large inputs, unicode)

**Registration**:
- [ ] Server exported with `create_sdk_mcp_server()`
- [ ] Server registered in `mcp_servers` dict or `.mcp.json`
- [ ] Tool names won't conflict with other servers
- [ ] `__init__.py` exports the server object
