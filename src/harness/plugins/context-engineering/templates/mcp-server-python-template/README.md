# {Server Name}

{Description of what this MCP server does.}

## Tools

| Tool | Description |
|------|-------------|
| `example_tool` | Search for items matching a query |

## Installation

```bash
# Via uvx
uvx {server-name}

# From source
uv pip install -e .
python -m {server_module}.server
```

## Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "{server-name}": {
      "command": "uvx",
      "args": ["{server-name}"],
      "env": {}
    }
  }
}
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy src/
```
