# Claude Agent SDK Dockerized Implementation Reference

**Version**: 2025.1
**Last Updated**: November 2025
**Scope**: Production-ready containerized Claude Agent SDK deployments

---

## Overview

The [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview) is Anthropic's official framework for building autonomous AI agents. Built on the infrastructure powering Claude Code, it provides file operations, code execution, web search, and [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) extensibility with automatic context management and production-grade error handling.

**Key Capabilities**: Long-running sessions (20+ hours), automatic prompt caching, subagent spawning via `Task` tool, fine-grained permission control, custom tool integration, event-driven hooks

**SDKs**: [Python](https://github.com/anthropics/claude-agent-sdk-python) (3.10+) | [TypeScript](https://github.com/anthropics/claude-agent-sdk-typescript) (Node 18+)

**Pricing**: Token costs dominate (~$0.05/hour minimum container + API usage). See [Anthropic pricing](https://www.anthropic.com/pricing).

---

## Installation & Quick Start

### Python SDK

```bash
pip install claude-agent-sdk
```

**Stateless Query** (no conversation history):
```python
import anyio
from claude_agent_sdk import query

async def main():
    async for message in query(prompt="What is 2 + 2?"):
        print(message)

anyio.run(main)
```

**Stateful Session** (maintains context):
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async with ClaudeSDKClient(options=ClaudeAgentOptions()) as client:
    await client.connect("Start coding task")
    async for message in client.receive_response():
        print(message)
```

### TypeScript SDK

```bash
npm install @anthropic-ai/claude-agent-sdk
```

**Basic Usage**:
```typescript
import { query } from '@anthropic-ai/claude-agent-sdk';

for await (const message of query({ prompt: "Hello!" })) {
  console.log(message);
}
```

---

## Core Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer (Your Code)                          │
│  ├─ ClaudeSDKClient / query()                          │
│  └─ Custom Tools / Hooks                               │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│  Claude Agent SDK (subprocess management)               │
│  ├─ Context management & compaction                    │
│  ├─ Tool execution & permission system                 │
│  └─ MCP server orchestration                           │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│  Claude Code CLI (bundled)                              │
│  ├─ .claude/ filesystem structure loader               │
│  ├─ Subagent spawning (Task tool)                      │
│  └─ Built-in tools (Read, Write, Bash, WebSearch)      │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│  Anthropic API (api.anthropic.com)                      │
│  └─ Claude Sonnet 4.5 / Haiku models                   │
└─────────────────────────────────────────────────────────┘
```

### Filesystem Structure

The SDK leverages Claude Code's [`.claude/` directory conventions](https://docs.claude.com/en/docs/claude-code/configuration):

```
project-root/
├── .claude/
│   ├── agents/              # Subagent definitions (Markdown files)
│   ├── skills/              # Reusable skill sets (SKILL.md files)
│   ├── settings.json        # Hook configurations
│   ├── commands/            # Custom slash commands
│   ├── specs/               # Coding standards
│   └── .mcp.json            # MCP server configurations (subprocess servers)
└── CLAUDE.md                # Project context & memory
```

**Loading Behavior**: Set `setting_sources` in `ClaudeAgentOptions`:
- `"user"` - Global settings from `~/.claude/`
- `"project"` - Project settings from `./.claude/`
- `"local"` - Local overrides (default)

---

## Python SDK API Reference

### ClaudeAgentOptions

**Configuration object** for SDK behavior:

```python
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    # Model selection
    model="claude-sonnet-4-5-20250929",  # or claude-3-5-haiku-20241022

    # Permission control
    permission_mode="default",  # acceptEdits, plan, bypassPermissions, dontAsk
    allowed_tools=["Read", "Write", "Bash"],
    disallowed_tools=["WebSearch"],

    # System behavior
    system_prompt="claude_code",  # or custom string
    max_turns=500,
    cwd="/workspace",

    # MCP integration
    mcp_servers={
        "memory": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"]
        }
    },

    # Event hooks
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[check_bash_safety])]
    },

    # Config loading
    setting_sources=["project", "local"],  # Load .claude/ from project
)
```

### ClaudeSDKClient

**Stateful session manager** with conversation history:

```python
from claude_agent_sdk import ClaudeSDKClient

async with ClaudeSDKClient(options=options) as client:
    # Initialize session
    await client.connect("Write a FastAPI endpoint")

    # Stream responses
    async for message in client.receive_response():
        if message.type == "assistant":
            print(message.content)

    # Continue conversation
    await client.query("Add error handling")
    async for message in client.receive_response():
        process_message(message)

    # Interrupt mid-execution
    await client.interrupt()
```

### Custom Tools (SDK MCP Servers)

**In-process tools** with zero IPC overhead:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("calculate_tax", "Calculate sales tax", {"amount": float, "rate": float})
async def calculate_tax(args):
    result = args["amount"] * args["rate"]
    return {
        "content": [{"type": "text", "text": f"Tax: ${result:.2f}"}]
    }

@tool("lookup_customer", "Find customer by ID", {"customer_id": str})
async def lookup_customer(args):
    # Database lookup logic
    return {"content": [{"type": "text", "text": json.dumps(customer_data)}]}

# Bundle tools into MCP server
calculator = create_sdk_mcp_server(
    name="business-tools",
    version="1.0.0",
    tools=[calculate_tax, lookup_customer]
)

options = ClaudeAgentOptions(
    mcp_servers={"business": calculator}
)
```

**Input Schemas**: Use simple type mapping (`{"field": float}`) or full JSON Schema with validation rules.

### Hooks

**Event-driven callbacks** for deterministic processing:

```python
from claude_agent_sdk import HookMatcher

async def block_dangerous_commands(input_data, tool_use_id, context):
    """PreToolUse hook - prevent risky bash commands"""
    if input_data["tool_name"] != "Bash":
        return {}

    command = input_data["tool_input"].get("command", "")
    dangerous_patterns = ["rm -rf /", ":(){ :|:& };:", "dd if=/dev/zero"]

    for pattern in dangerous_patterns:
        if pattern in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Blocked dangerous pattern: {pattern}"
                }
            }
    return {}

async def log_tool_results(input_data, tool_use_id, context):
    """PostToolUse hook - audit all tool executions"""
    logger.info(f"Tool executed: {input_data['tool_name']}", extra={
        "tool_use_id": tool_use_id,
        "result": input_data.get("tool_result")
    })
    return {}

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[block_dangerous_commands])],
        "PostToolUse": [HookMatcher(matcher="*", hooks=[log_tool_results])],
    }
)
```

**Available Hook Events**: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`

### Message Types

**Unified message type** with discriminated union:

```python
from claude_agent_sdk import Message

async for message in client.receive_messages():
    match message.type:
        case "user":
            print(f"User: {message.content}")
        case "assistant":
            for block in message.content:
                if block.type == "text":
                    print(block.text)
                elif block.type == "tool_use":
                    print(f"Tool: {block.tool_name}({block.tool_input})")
        case "result":
            print(f"Usage: {message.usage}")
            print(f"Cost: ${message.cost}")
```

---

## MCP Integration

### Configuration Format

**`.mcp.json`** at project root:

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {}
    },
    "database": {
      "command": "node",
      "args": ["./custom-mcp-server.js"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      }
    },
    "remote": {
      "type": "http",
      "url": "https://mcp.example.com/api",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

**Inline Configuration** (Python SDK):

```python
options = ClaudeAgentOptions(
    mcp_servers={
        # External subprocess servers
        "memory": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"]
        },

        # HTTP/SSE remote servers
        "analytics": {
            "type": "http",
            "url": "https://analytics-mcp.internal/api",
            "headers": {"X-API-Key": os.getenv("ANALYTICS_KEY")}
        },

        # In-process SDK MCP servers
        "custom_tools": custom_tool_server,
    },

    # Whitelist MCP-provided tools
    allowed_tools=["mcp__memory__create_entities", "mcp__custom_tools__*"]
)
```

### Official MCP Servers

| Server | Package | Tools |
|--------|---------|-------|
| **Memory** | `@modelcontextprotocol/server-memory` | Knowledge graph CRUD, search |
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | File operations |
| **GitHub** | `@modelcontextprotocol/server-github` | Code search, PRs, issues |
| **Postgres** | `@modelcontextprotocol/server-postgres` | SQL queries, schema inspection |
| **Puppeteer** | `@modelcontextprotocol/server-puppeteer` | Browser automation |
| **Slack** | `@modelcontextprotocol/server-slack` | Message posting, channel management |
| **Context7** | `@context7/mcp-server` | Library documentation lookup |

**Docker Hub MCP Images**: Available from [`docker.io/mcp/`](https://hub.docker.com/u/mcp) namespace for containerized MCP servers.

---

## Dockerization Patterns

### Critical Container Requirements

**1. Stream Buffering Fix**

Python subprocess uses 8KB block buffering in containers (no TTY), causing messages to accumulate unsent:

```dockerfile
# CRITICAL: Force unbuffered stdout
ENV PYTHONUNBUFFERED=1
```

**Why This Matters**: Without unbuffering, agent subprocess output sits in buffer until process exits, causing SDK initialization timeouts and "0 messages received" errors.

**2. Signal Propagation**

Docker sends SIGTERM to PID 1. Without proper init system, signals don't reach agent subprocess:

```dockerfile
# Install tini for signal forwarding
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "harness.agent"]
```

**Without tini**: Shell becomes PID 1, receives SIGTERM but doesn't forward to Python → agent subprocess never flushes buffers → messages lost on container stop.

### Production Dockerfile

**Multi-stage build** with security hardening:

```dockerfile
# Stage 1: Base dependencies
FROM python:3.12-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tini \
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*

# Stage 2: Dependencies
FROM base AS dependencies

WORKDIR /app
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Production
FROM base AS production

# Create non-root user
RUN useradd -m -u 1000 claude
USER claude

WORKDIR /app

# Copy dependencies from builder
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --chown=claude:claude . .

# Critical environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Tini as PID 1 for signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "harness.agent"]
```

### Docker Compose Configuration

**Multi-agent orchestration** with Redis message broker:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redis_data:/data
    networks:
      - agents

  main-agent:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    environment:
      - AGENT_ID=main
      - REDIS_URL=redis://redis:6379
      - PYTHONUNBUFFERED=1
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - agents
    volumes:
      - ./workspace:/workspace
      - ./memory:/memory

  reviewer-agent:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    environment:
      - AGENT_ID=reviewer
      - REDIS_URL=redis://redis:6379
      - PYTHONUNBUFFERED=1
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
    networks:
      - agents
    volumes:
      - ./workspace:/workspace:ro  # Read-only for reviewer

networks:
  agents:
    driver: bridge

volumes:
  redis_data:
```

### Deployment Strategies

**1. Ephemeral Sessions** (one-off tasks):
- New container per task
- Destroyed on completion
- Best for: Bug fixes, invoice processing, translations

**2. Long-Running Sessions** (persistent agents):
- Container runs continuously
- Multiple SDK processes simultaneously
- Best for: Chatbots, content servers, monitoring agents

**3. Hybrid Sessions** (intermittent work):
- Ephemeral containers hydrated with state from database/Redis
- Spin down when idle, resume with history
- Best for: Project management, research tasks

**4. Multi-Agent Coordination**:
- Separate containers per agent
- Redis Streams for inter-agent messaging
- Best for: Complex workflows requiring specialized agents

---

## Multi-Agent Communication

### Redis Streams Pattern

**Why Not Subprocess Stdio?** Agent SDK's `Task` tool spawns subagents via subprocess, which uses stdin/stdout pipes. These only work within a single process boundary—cannot cross container boundaries.

**Redis Streams Solution**:

```python
import redis
import json
import os

# Initialize broker
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))

# Agent 1: Publish task result
result = {
    "agent_id": "agent-1",
    "task": "code_review",
    "findings": ["Missing error handling", "SQL injection risk"],
    "timestamp": time.time()
}

stream_id = redis_client.xadd("results:all", {
    "content": json.dumps(result),
    "agent": "agent-1"
})
logger.info(f"Published result: {stream_id}")

# Agent 2: Consume results
last_id = "0"
while True:
    messages = redis_client.xread(
        {"results:all": last_id},
        count=10,
        block=5000  # 5 second timeout
    )

    for stream, data in messages:
        for msg_id, msg_data in data:
            result = json.loads(msg_data[b"content"])
            process_result(result)
            last_id = msg_id
```

**Consumer Groups** (load balancing across multiple agents):

```python
# Create consumer group
redis_client.xgroup_create("results:all", "reviewers", id="0", mkstream=True)

# Consume as part of group
while True:
    messages = redis_client.xreadgroup(
        groupname="reviewers",
        consumername="agent-2",
        streams={"results:all": ">"},
        count=1,
        block=5000
    )

    for stream, data in messages:
        for msg_id, msg_data in data:
            result = json.loads(msg_data[b"content"])
            process_result(result)
            # Acknowledge processing
            redis_client.xack("results:all", "reviewers", msg_id)
```

---

## Security Best Practices

### Container Hardening

**1. Non-Root User**:
```dockerfile
RUN useradd -m -u 1000 claude
USER claude
```

**2. Read-Only Filesystem**:
```yaml
services:
  agent:
    read_only: true
    tmpfs:
      - /tmp
      - /workspace
```

**3. Network Restrictions**:
```yaml
services:
  agent:
    networks:
      - agents  # Isolated bridge network
    # Only expose necessary ports
    ports:
      - "8000:8000"  # Health check only
```

**4. Secret Management**:
```bash
# .env (gitignored)
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql://user:pass@db:5432/prod

# .env.example (committed)
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**5. Resource Limits**:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
      pids: 100  # Prevent fork bombs
```

### Permission Management

**Bypass Permissions** (for unattended operation in isolated containers):
```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",  # No prompts
    disallowed_tools=["Bash"],  # Block shell access
)
```

**Manual Approval** (for sensitive operations):
```python
options = ClaudeAgentOptions(
    permission_mode="default",  # Require approval
    can_use_tool=async_permission_callback,
)
```

**Tool Whitelisting**:
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Grep"],
    disallowed_tools=["Bash", "WebFetch"],
)
```

### Authentication Methods

**Direct API** (default):
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Amazon Bedrock**:
```bash
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-west-2
```

**Google Vertex AI**:
```bash
export CLAUDE_CODE_USE_VERTEX=1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
export GOOGLE_CLOUD_PROJECT=my-project-id
```

---

## Signal Handling & Graceful Shutdown

### Python Implementation

```python
import asyncio
import signal
import sys
import logging

logger = logging.getLogger(__name__)

async def graceful_shutdown(signame: str):
    """Handle SIGTERM/SIGINT with stream flushing"""
    logger.info(f"Received {signame}, starting graceful shutdown")

    # Critical: Flush all output streams
    sys.stdout.flush()
    sys.stderr.flush()

    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(0.1)  # Allow cleanup

async def main():
    loop = asyncio.get_event_loop()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                graceful_shutdown(signal.Signals(s).name)
            )
        )

    try:
        await run_agent()
    except asyncio.CancelledError:
        logger.info("Agent task cancelled during shutdown")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()

if __name__ == "__main__":
    asyncio.run(main())
```

### Testing Signal Handling

```bash
# Start agent
docker compose up -d main-agent

# Send graceful stop
docker compose stop -t 10 main-agent

# Verify graceful shutdown in logs
docker compose logs main-agent | grep -i "shutdown\|sigterm"
# Expected: "Received SIGTERM, starting graceful shutdown"
```

---

## Common Gotchas & Solutions

| Problem | Symptom | Root Cause | Solution |
|---------|---------|-----------|----------|
| **0 messages received** | SDK initialization timeout | Block buffering in subprocess | Add `ENV PYTHONUNBUFFERED=1` to Dockerfile |
| **Timeout on `initialize`** | 60s timeout during `__aenter__()` | MCP server connection failure | Check MCP server logs, verify Node.js installed |
| **Process hangs on stop** | Container requires `docker kill` | Shell is PID 1, doesn't forward signals | Use `ENTRYPOINT ["/usr/bin/tini", "--"]` |
| **Partial message loss** | StreamReader truncates output | Default 64KB limit too small | Increase to `limit=1024*256` in `create_subprocess_exec()` |
| **Container restarts fail** | Healthcheck always failing | Health endpoint not implemented | Add Flask `/health` route returning 200 |
| **Cross-container IPC fails** | Subagents can't communicate | Subprocess pipes don't cross containers | Use Redis Streams message broker |
| **Permission denied errors** | Tools blocked unexpectedly | `permission_mode` or `allowed_tools` misconfigured | Set `permission_mode="bypassPermissions"` for isolated containers |
| **API rate limits** | 429 Too Many Requests | Concurrent agent instances | Implement token bucket rate limiting |

---

## Examples & Repositories

### Official Demos

- **[claude-agent-sdk-demos](https://github.com/anthropics/claude-agent-sdk-demos)** - Research agent, email assistant, Excel processor, Hello World
- **[Python SDK Examples](https://github.com/anthropics/claude-agent-sdk-python/tree/main/examples)** - Hooks, streaming, custom tools

### Community Implementations

- **[claudebox](https://github.com/RchGrav/claudebox)** - Complete Docker dev environment with 15+ language profiles, network firewall, persistent sessions
- **[claude-agent-sdk-container](https://github.com/receipting/claude-agent-sdk-container)** - Minimal containerized SDK setup
- **[Agor](https://github.com/preset-io/agor)** - Multi-agent orchestration with Redis message passing

### Reference Projects

- **[claude-flow](https://github.com/ruvnet/claude-flow)** - Enterprise SDK integration patterns
- **[claude-agent-skills](https://github.com/meetrais/claude-agent-skills)** - Reusable skill examples

---

## Performance Optimization

### Caching Strategy

**Automatic Prompt Caching**: SDK caches system prompts and tool definitions automatically. Ensure consistent system prompts across requests for maximum cache hits.

**Cache Metrics** (from ResultMessage):
```python
async for message in client.receive_response():
    if message.type == "result":
        print(f"Cache read: {message.usage.cache_read_input_tokens} tokens")
        print(f"Cache write: {message.usage.cache_creation_input_tokens} tokens")
        print(f"Cache savings: ${message.cost - base_cost:.4f}")
```

### Resource Tuning

**Memory Limits**: Start with 2GB, increase if compaction triggers frequently:
```yaml
deploy:
  resources:
    limits:
      memory: 4G  # Allow headroom for context expansion
```

**CPU Allocation**: 1-2 cores sufficient for most agents:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
    reservations:
      cpus: '1'  # Guaranteed allocation
```

### Stream Reading Optimization

**Robust subprocess pattern** from `/Users/andisblukis/Projects/ab-casdk-harness/docs/MULTIAGENT_IMPLEMENTATION.md`:

```python
import asyncio
import subprocess

proc = await asyncio.create_subprocess_exec(
    cli_path, *args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    limit=1024*256,  # Increased from default 64KB
)

# Proper EOF handling prevents hung reads
while not proc.stdout.at_eof():
    try:
        line = await asyncio.wait_for(
            proc.stdout.readline(),
            timeout=60.0
        )
        if not line:
            break

        message = json.loads(line.decode())
        yield message
    except asyncio.TimeoutError:
        if proc.returncode is not None:
            break

# Drain remaining buffered data
remaining = await asyncio.wait_for(proc.stdout.read(), timeout=2.0)
if remaining:
    for line in remaining.split(b'\n'):
        if line:
            yield json.loads(line.decode())

await proc.wait()
```

---

## Monitoring & Observability

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Agent performance metrics
agent_requests = Counter('agent_requests_total', 'Total requests', ['agent', 'status'])
agent_duration = Histogram('agent_duration_seconds', 'Request duration', ['agent'])
agent_tokens = Counter('agent_tokens_total', 'Token usage', ['model', 'type'])
agent_cost = Counter('agent_cost_dollars_total', 'API costs', ['model'])

# Track usage
agent_requests.labels(agent='main', status='success').inc()
agent_duration.labels(agent='main').observe(12.5)
agent_tokens.labels(model='sonnet', type='input').inc(1500)
agent_cost.labels(model='sonnet').inc(0.045)

# Expose metrics endpoint
start_http_server(9090)
```

### Grafana Dashboard

**Key Panels**:
- Requests per minute (by agent, status)
- P50/P95/P99 latency
- Token usage breakdown (input/output/cache)
- Hourly cost trends
- Active session count
- Tool usage distribution

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

logger.info("agent_session_started",
    agent_id="main",
    session_id="abc123",
    model="claude-sonnet-4-5-20250929"
)

logger.info("tool_executed",
    tool_name="Bash",
    command="pytest tests/",
    duration_ms=2500,
    success=True
)
```

---

## Key Links

### Official Documentation
- [Agent SDK Overview](https://docs.claude.com/en/api/agent-sdk/overview)
- [Python SDK Reference](https://docs.claude.com/en/docs/agent-sdk/python)
- [TypeScript SDK Reference](https://docs.claude.com/en/docs/agent-sdk/typescript)
- [MCP in SDK](https://docs.claude.com/en/docs/agent-sdk/mcp)
- [Hosting Guide](https://docs.claude.com/en/docs/agent-sdk/hosting)

### GitHub Repositories
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [TypeScript SDK](https://github.com/anthropics/claude-agent-sdk-typescript)
- [SDK Demos](https://github.com/anthropics/claude-agent-sdk-demos)
- [MCP Servers](https://github.com/modelcontextprotocol/servers)

### Resources
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Anthropic Pricing](https://www.anthropic.com/pricing)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Building Agents Blog Post](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

### Docker Resources
- [Docker Hub MCP Images](https://hub.docker.com/u/mcp)
- [tini GitHub](https://github.com/krallin/tini)
- [Multi-stage Build Docs](https://docs.docker.com/build/building/multi-stage/)

---

**Document Status**: Production-Ready
**Confidence**: High (verified implementation from ab-casdk-harness project)
**Last Validation**: November 2025
