>[toc]

# Claude Agent SDK Harness - Technical Documentation

**Last updated**: December 2, 2025

> For user documentation and usage instructions, see [README.md](./README.md).
> This file contains implementation details, development workflows, and technical references for developers and Claude.

## Current Status

**Phase**: Phase 1C Complete (MCP Servers Active)
**Test Coverage**: ~61% (Target: 80%+)
**Last Updated**: December 2, 2025

### What's Working
- ✅ Interactive conversation mode with Rich CLI (cli.py, interactive.py)
- ✅ Quiet mode for clean chat (--quiet flag suppresses system logs)
- ✅ Action logging hooks and session metrics (infrastructure in place)
- ✅ Grafana dashboard with real-time metrics (verified working with live data)
- ✅ Docker orchestration with Prometheus + Grafana monitoring
- ✅ Checkpoint & recovery system with auto-save
- ✅ MCP servers (6 total: 3 in-process + 3 subprocess)
- ✅ CLI tools for git/GitHub/GitLab (git, gh, glab)
- ✅ Token usage tracking and cost calculation (verified in Grafana)


## Project Overview

The Claude Agent SDK Harness is a production-ready framework for building autonomous software development systems using Anthropic's Claude Agent SDK. This harness provides infrastructure, tooling, and patterns for running long-duration (20+ hour) agent sessions with full observability, fault tolerance, and recovery.

### Architecture Principles

1. **KISS, DRY, SOLID, YAGNI** - Follow universal code standards
2. **Separation of Concerns** - Clear boundaries between agents, infrastructure, and business logic
3. **Fail Fast** - Comprehensive validation and error handling
4. **Observability First** - Everything is logged, metered, and traceable
5. **Security by Default** - Least privilege, secret rotation, audit logs
6. **Cloud Native** - Container-first, stateless where possible, config via environment

See [README.md](./README.md) for key features and user-facing capabilities.

## Repository Structure

```
claudeagentsdk-harness/
├── .claude/                    # Claude Configuration (SDK-compliant structure)
│   ├── agents/                 # Agent reference definitions - flat structure with prefixes (44 total)
│   │   ├── build-*.md          # Build/orchestration agents (3)
│   │   ├── data-*.md           # Data engineering agents (1)
│   │   ├── db-*.md             # Database experts (7)
│   │   ├── dev-*.md            # Development language experts (16)
│   │   ├── doc-*.md            # Documentation writers (2)
│   │   ├── infra-*.md          # Infrastructure & cloud specialists (8)
│   │   ├── ml-*.md             # Machine learning experts (4)
│   │   └── web-*.md            # Web/frontend specialists (3)
│   ├── hooks/                  # Action logging hooks
│   │   ├── hooks.json          # Hook configuration
│   │   └── log_agent_actions.py
│   ├── skills/                 # Skill directories with SKILL.md (12 total)
│   │   ├── api-development/    # REST/GraphQL API patterns
│   │   ├── code-review/        # Review workflows and standards
│   │   ├── database-management/# Database patterns and schemas
│   │   ├── debugging/          # Troubleshooting workflows
│   │   ├── deployment-operations/# CI/CD and deployment
│   │   ├── documentation/      # Documentation generation
│   │   ├── frontend-development/# React/TypeScript patterns
│   │   ├── git-workflow/       # Git best practices
│   │   ├── microservices-architecture/# Distributed systems
│   │   ├── performance-optimization/# Caching and optimization
│   │   ├── security/           # Security hardening
│   │   └── testing-strategies/ # Testing patterns
│   └── specs/                  # Shared coding standards (python, make, javascript, etc.)
│
├── agents/                     # Agent container configurations
│   └── main/                   # Primary development agent
│       └── Dockerfile          # Multi-stage Dockerfile (deps, dev, builder, prod)
│
├── src/                        # Python SDK wrapper and utilities
│   ├── harness/
│   │   ├── __init__.py
│   │   ├── agent.py            # Agent session wrapper with retry logic
│   │   ├── checkpoint.py       # Checkpoint manager with auto-save
│   │   ├── cli.py              # Rich CLI formatting and message parsing
│   │   ├── config.py           # Pydantic config management
│   │   ├── interactive.py      # Interactive conversation loop
│   │   ├── monitoring.py       # Prometheus metrics collector
│   │   └── py.typed            # PEP 561 type marker
│   └── mcp_servers/            # Custom MCP servers
│       ├── __init__.py
│       ├── context7/           # Library documentation lookup
│       ├── docker/             # Docker container management
│       └── memory/             # Knowledge graph for persistent memory
│
├── config/                     # Configuration files
│   └── monitoring/             # Prometheus & Grafana configs
│       ├── prometheus.yml      # Scrape configs for all agents
│       ├── alerting.yml        # Alert rules (errors, latency, cost)
│       └── dashboards/
│           ├── overview.json           # Grafana overview dashboard
│           └── interactive_sessions.json  # Interactive sessions dashboard
│
├── workspace/                  # Agent working directory (gitignored)
│   └── context/              # Technical context files (created by autonomous mode)
│       ├── architecture.md   # System design overview
│       ├── decisions.md      # Technical decisions log (append-only)
│       ├── issues.md         # Known issues and blockers
│       └── next-steps.md     # Priorities for next session
├── memory/                     # Persistent agent memory (gitignored)
│   ├── checkpoints/
│   └── graph/                # Memory MCP knowledge graph
├── logs/                       # Application logs (gitignored)
│   ├── main/
│   ├── reviewer/
│   ├── tester/
│   ├── orchestrator/
│   └── actions/                # Action log files from hooks
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── unit/                   # Unit tests (checkpoint, config)
│   │   ├── test_checkpoint.py
│   │   └── test_config.py
│   ├── integration/            # Integration tests
│   │   ├── test_agent_sdk_direct.py
│   │   ├── test_mcp_git.py
│   │   └── test_mcp_docker.py
│   └── e2e/                    # End-to-end tests (placeholder)
│
├── examples/                   # Example workflows
│   ├── simple_query.py         # Basic query pattern example
│   └── interactive_basic.py    # Basic interactive mode example
│
├── docs/                       # Additional documentation
│   └── HARDENING.md            # Production readiness and security audit
│
├── .mcp.json                   # MCP server configuration
├── docker-compose.yml          # Base compose configuration
├── docker-compose.dev.yml      # Development override with hot-reload
├── docker-compose.prod.yml     # Production override with security
├── Makefile                    # 60+ build and operation commands
├── pyproject.toml              # Python project configuration
├── .env.example                # Environment variables template
├── .dockerignore               # Docker build exclusions
├── .gitignore                  # Git exclusions
├── CLAUDE.md                   # This file
└── README.md                   # User-facing documentation
```

## Getting Started for Development

> Prerequisites listed in [README.md](./README.md#prerequisites). This section covers development-specific setup.

### Additional Development Tools

- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checker for Python
- **pytest** - Testing framework
- **uv** - Fast Python package installer

### Development Setup

```bash
# 1. Follow README.md setup instructions first
cd ~/Projects/claudeagentsdk-harness
make init
# Edit .env with ANTHROPIC_API_KEY

# 2. Build containers
make build

# 3. Start in development mode (hot-reload enabled)
make dev

# 4. In another terminal, verify setup
make health
make test-unit

# 5. Access development shell
make shell
```

### Development Workflow

```bash
# Watch logs during development
make logs

# Run linting
make lint
make lint-fix  # Auto-fix issues

# Run type checking
make typecheck

# Format code
make format

# Run tests
make test-unit           # Fast, no API calls
make test-integration    # Requires ANTHROPIC_API_KEY

# Coverage report
make coverage
```

### Important: Always Use Make Commands

**ALWAYS use `make` commands instead of direct `docker compose` commands**. The Makefile handles proper compose file selection, environment variables, and platform settings automatically.

✅ Correct: `make down`, `make up`, `make dev`
❌ Incorrect: `docker compose down`, `docker compose up -d`

## Implementation Details

### Core Python Modules

#### config.py

Pydantic-based configuration with environment variable loading:

**Key Features:**
- Type-safe settings with validation
- Database and Redis URL generation
- Directory path management
- Feature flags

**Usage:**
```python
from harness.config import get_config

config = get_config()
print(config.redis_url)           # redis://redis:6379/0
print(config.checkpoint_dir)      # /memory/checkpoints
print(config.claude_model)        # claude-sonnet-4-5-20250929
```

**Implementation:**
- Uses `pydantic-settings` for .env loading
- Validates all configuration on startup
- Provides sensible defaults
- Type hints for IDE support

#### checkpoint.py

Automatic checkpoint management with configurable intervals:

**Key Features:**
- Auto-save every hour (configurable)
- Auto-cleanup (keeps 5 most recent)
- JSON-based state persistence
- Recovery from latest checkpoint
- Workspace and memory snapshots

**Usage:**
```python
from harness.checkpoint import CheckpointManager

manager = CheckpointManager(checkpoint_dir=Path("/memory/checkpoints"))

# Save checkpoint
checkpoint_file = manager.save_checkpoint({
    "agent": "main",
    "tasks": ["task1", "task2"],
    "timestamp": "2025-10-28T12:00:00"
})

# Load latest
latest = manager.load_latest_checkpoint()
if latest:
    print(f"Recovered from {latest['timestamp']}")
```

**Implementation:**
- Uses `fcntl` for file locking
- Atomic writes via temp files
- Automatic cleanup via `_cleanup_old_checkpoints()`
- ISO 8601 timestamps in filenames

#### monitoring.py

Prometheus metrics collection with comprehensive tracking:

**Key Metrics Implemented:**
- `agent_requests_total{agent, status}` - Counter
- `agent_duration_seconds{agent}` - Histogram
- `agent_active_sessions{agent}` - Gauge
- `interactive_session_prompts_total{agent, session_id}` - Counter
- `interactive_tool_calls_total{agent, tool_name, status}` - Counter
- `interactive_cache_hit_ratio{agent}` - Gauge
- `api_tokens_used_total{model, type}` - Counter
- `api_cost_dollars_total{model}` - Counter

**Usage:**
```python
from harness.monitoring import MetricsCollector

metrics = MetricsCollector(port=9090)
metrics.start()

# Record request
metrics.record_request(agent="main", status="success")

# Record duration
metrics.record_duration(agent="main", duration=1.5)

# Record tool call
metrics.record_tool_call(agent="main", tool_name="Read", status="success")

# Update cache metrics
metrics.update_cache_metrics(
    agent="main",
    model="claude-sonnet-4-5-20250929",
    cache_read_tokens=1000,
    cache_creation_tokens=500,
    total_input_tokens=2000
)
```

**Implementation:**
- Uses `prometheus_client` library
- Metrics exposed on port 9090
- Thread-safe counters and gauges
- Automatic cost calculation based on current Anthropic pricing

#### agent.py

Agent session wrapper with lifecycle management:

**Key Features:**
- Session lifecycle management
- Automatic checkpointing integration
- Metrics collection integration
- Retry logic with exponential backoff
- Error handling and recovery
- MCP server registration

**Usage:**
```python
from harness.agent import AgentSession

session = AgentSession(agent_name="main")
await session.start()

async for message in session.execute("Build a FastAPI endpoint"):
    # Process message
    print(message)

await session.shutdown()
```

**Implementation:**
- Integrates with `ClaudeSDKClient`
- MCP server registration (6 servers: 3 in-process + 3 subprocess)
- Automatic token tracking
- Session state persistence

#### cli.py

Rich console formatting for interactive mode:

**Key Features:**
- Colored panels for different message types
- Syntax highlighting for code and JSON
- Session statistics display
- Structured logging integration

**Message Types Handled:**
- `user` - User input
- `assistant` - Agent responses
- `tool_use` - Tool calls
- `tool_result` - Tool outputs
- `system` - System messages

**Usage:**
```python
from harness.cli import parse_and_print_message
from rich.console import Console

console = Console()

# Parse and display message
parse_and_print_message(message, console)

# Display session stats
from harness.cli import display_session_stats
display_session_stats(stats, console)
```

#### interactive.py

Interactive conversation loop with Rich UI:

**Key Features:**
- Conversation loop with Rich UI
- Integration with AgentSession
- Checkpoint recovery on startup
- Graceful error handling
- CLI argument support (--model, --stats, --quiet)

**Usage:**
```bash
# Run interactively
python -m harness.interactive

# With options
python -m harness.interactive --model opus --quiet --stats
```

**Implementation:**
- Uses `Rich` for UI
- Integrates with checkpoint manager
- Records metrics automatically
- Handles Ctrl+C gracefully

### Docker Compose Services

#### Service Definitions

**main-agent:**
- **Image**: Built from `agents/main/Dockerfile`
- **Ports**: 8080 (HTTP), 5678 (debugger in dev mode)
- **Resources**: 4 CPU, 8GB RAM (configurable)
- **Volumes**: workspace, memory, logs, config, src (dev mode)
- **Health Check**: HTTP endpoint on port 8080
- **Restart Policy**: unless-stopped

**reviewer-agent:**
- **Purpose**: Code review and security audit
- **Access**: Read-only workspace
- **Permission Mode**: manual (require approval)
- **Max Turns**: 50 (focused reviews)

**tester-agent:**
- **Purpose**: Test generation and execution
- **Access**: Full workspace access
- **Permission Mode**: acceptAll
- **Max Turns**: 100

**redis:**
- **Version**: Redis 7
- **Persistence**: AOF enabled
- **Health Check**: `redis-cli ping`

**prometheus:**
- **Retention**: 30 days (configurable)
- **Scrape Interval**: 15 seconds
- **Scrapes**: All agent metrics endpoints

**grafana:**
- **Admin Password**: Configurable via `GRAFANA_PASSWORD`
- **Dashboards**: Pre-configured (overview, interactive sessions)
- **Data Source**: Prometheus

### MCP Server Configuration

**In-Process SDK Servers** (custom Python implementations in `src/mcp_servers/`):

**docker** (`src/mcp_servers/docker/server.py`):
- Tools: `mcp__docker__list_containers`, `mcp__docker__container_logs`, `mcp__docker__container_stats`
- Purpose: Container management and monitoring
- Implementation: Uses Docker SDK for Python

**context7** (`src/mcp_servers/context7/server.py`):
- Tools: `mcp__context7__resolve_library_id`, `mcp__context7__get_library_docs`
- Purpose: Library documentation lookup
- Implementation: Uses Context7 API

**memory** (`src/mcp_servers/memory/server.py`):
- Tools: `mcp__memory__create_entities`, `mcp__memory__search_nodes`, etc.
- Purpose: Knowledge graph for persistent memory
- Implementation: In-process knowledge graph

**Subprocess MCP Servers** (via npx/uvx):

**joplin**:
- Package: `@joplin/mcp-server`
- Purpose: Note-taking and documentation integration
- Tools: search_notes, create_note, update_note, etc.

**playwright**:
- Package: `@modelcontextprotocol/server-playwright`
- Purpose: Browser automation and testing
- Tools: Navigate, screenshot, click, fill

**excel-haris-musa**:
- Package: `excel-mcp-server` (via uvx)
- Purpose: Excel file manipulation
- Tools: read_data, write_data, create_chart, etc.

**CLI Tools** (use via Bash tool - NOT MCP):

Git, GitHub, and GitLab operations use CLI tools instead of MCP servers:
- **git**: Version control (always available, SSH keys in .ssh/)
- **gh**: GitHub CLI for repos, issues, PRs (requires `gh auth login` or GITHUB_PERSONAL_ACCESS_TOKEN)
- **glab**: GitLab CLI for projects, issues, MRs (requires `glab auth login` or GITLAB_PERSONAL_ACCESS_TOKEN)

### Message Flow & Integration

**Interactive Session Flow:**
```
User Input (CLI)
    ↓
interactive.py (conversation loop)
    ↓
AgentSession.execute()
    ↓
ClaudeSDKClient.query() (with MCP servers)
    ↓
← Message Stream ←
    ↓
cli.parse_and_print_message()
    ↓
Rich Console Display
```

**Integration Points:**
- `AgentSession` - Handles checkpointing, metrics, retry logic
- `MetricsCollector` - Tracks tokens, cost, duration automatically
- `CheckpointManager` - Auto-saves every hour, recovers on startup
- `MCP Servers` - Docker, Context7, Memory, Joplin, etc.
- `CLI Tools` - git, gh, glab for version control and platform operations
- `structlog` - Structured logging with correlation IDs

## Development Workflow

### Git Workflow

```bash
# Feature branch workflow
git checkout -b feature/descriptive-name

# Make changes with TDD approach
# Write failing test → Implement → Pass test → Refactor

# Commit with conventional commits
git commit -m "feat(agent): add retry logic with exponential backoff"
git commit -m "fix(checkpoint): handle race condition in cleanup"
git commit -m "docs(readme): update configuration examples"

# Push and create PR
git push origin feature/descriptive-name
```

### Conventional Commit Format

- `feat(scope):` - New feature
- `fix(scope):` - Bug fix
- `docs(scope):` - Documentation only
- `refactor(scope):` - Code change that neither fixes a bug nor adds a feature
- `test(scope):` - Adding or updating tests
- `chore(scope):` - Build process or auxiliary tool changes

### Code Review Process

**Before submitting PR:**
1. Run `make lint` and fix all issues
2. Run `make typecheck` and fix type errors
3. Run `make test` and ensure all tests pass
4. Ensure test coverage is ≥80% for new code
5. Update documentation if needed

**Review Focus:**
1. Logic correctness - Does it solve the problem?
2. Edge cases - Are errors handled?
3. Performance - Any obvious bottlenecks?
4. Security - Input validation present?
5. Maintainability - Will others understand?

## Testing Strategy

### Test Structure

```
tests/
├── unit/                   # Fast, isolated unit tests
│   ├── test_checkpoint.py  # Checkpoint save/load/cleanup
│   └── test_config.py      # Configuration validation
├── integration/            # Multi-service integration tests
│   ├── test_agent_sdk_direct.py   # Direct SDK calls (real API)
│   └── test_mcp_docker.py         # Docker MCP server tests
└── e2e/                    # Full workflow end-to-end tests (placeholder)
```

### Test Coverage Requirements

| Type | Coverage Target | Notes |
|------|----------------|-------|
| Overall | 80%+ | Measured by pytest-cov |
| Critical paths | 95%+ | Checkpointing, config, metrics |
| Core modules | 90%+ | agent.py, monitoring.py, cli.py |

**Current Coverage**: ~61% (needs improvement to 80%+)

### Running Tests

```bash
# Daily development: Unit tests only (fast, free)
make test-unit

# Integration tests: Use selectively (costs ~$0.10-$0.50 per run)
ANTHROPIC_API_KEY=xxx make test-integration

# Skip expensive tests during development
make test-unit && pytest tests/integration/ -m "not slow"

# Full suite (costs ~$1-$5 depending on tests)
ANTHROPIC_API_KEY=xxx make test

# Coverage report
make coverage
```

### Cost Management

**Why No VCR.py:**
The Claude Agent SDK uses subprocess communication (stdin/stdout), not HTTP. VCR.py cannot intercept subprocess I/O, so all integration tests make real API calls.

**Token Budget Tracking:**
- **Limit**: 1,000,000 tokens per test session
- **Tracking**: Automatic via `token_budget` fixture in conftest.py
- **Behavior**: Tests fail if budget exceeded

**Test Markers:**
- `@pytest.mark.slow` - Expensive tests (can be skipped with `-m "not slow"`)
- `@pytest.mark.integration` - Requires API key and makes real calls

**Cost Optimization:**
- Run unit tests frequently (free, instant)
- Run integration tests only when needed (before commits, weekly)
- Mock SDK responses in unit tests when possible
- Monitor token usage in test output

### Test Examples

**Unit Test:**
```python
def test_save_checkpoint(checkpoint_manager):
    """Test checkpoint save creates file with correct structure."""
    state = {"agent": "main", "tasks": ["task1"]}
    checkpoint_file = checkpoint_manager.save_checkpoint(state)

    assert checkpoint_file.exists()
    loaded = checkpoint_manager.load_checkpoint(checkpoint_file)
    assert loaded["agent"] == "main"
    assert "tasks" in loaded
```

**Integration Test:**
```python
@pytest.mark.integration
@pytest.mark.slow
def test_agent_query_with_real_api(token_budget):
    """Test real API call with token budget tracking."""
    from harness.agent import AgentSession

    session = AgentSession(agent_name="main")
    response = await session.execute("What is 2+2?")

    # Verify response
    assert "4" in response.text

    # Check token budget
    assert token_budget.remaining > 0
```

## Build & Deployment

### Docker Build Configuration

**Multi-Stage Dockerfile** (`agents/main/Dockerfile`):

**Stage 1: base**
- Common system dependencies
- Non-root user setup
- Base Python environment

**Stage 2: dependencies**
- Python packages with cache mounts
- Uses `uv` for fast installs
- Separate layer for dependencies

**Stage 3: development**
- Full dev tools (ruff, mypy, pytest)
- Claude CLI installation
- Hot-reload support

**Stage 4: builder**
- Compile and prepare production assets
- Remove dev dependencies
- Optimize for size

**Stage 5: production**
- Minimal runtime image
- Only production dependencies
- Non-root user
- Read-only filesystem where possible

### Build Optimizations

**BuildKit Caching:**
```bash
# Cache mounts for uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt
```

**Layer Ordering:**
- System packages (changes rarely)
- Python dependencies (changes occasionally)
- Source code (changes frequently)

**OrbStack Optimizations (macOS):**
- Native ARM64 builds (2x faster than Docker Desktop)
- Faster volume mounts
- Better resource management

### Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| **Hot-reload** | ✅ Yes (watch mode) | ❌ No |
| **Debugger** | ✅ Port 5678 | ❌ Not exposed |
| **Source mount** | ✅ `./src` mounted | ❌ Copied into image |
| **Restart policy** | `unless-stopped` | `always` |
| **Logging** | DEBUG level | INFO level |
| **Health checks** | 30s interval | 10s interval |

## Configuration Management

### Environment Variables

See [README.md](./README.md#configuration) for complete user-facing configuration reference.

**Development-Specific Configuration:**

```bash
# Development mode toggles
DEBUG=true                      # Enable debug logging
LOG_LEVEL=DEBUG                # Verbose logging
DOCKER_BUILDKIT=1              # Enable BuildKit
BUILDKIT_PROGRESS=plain        # Build output format

# Development resources (lower limits)
AGENT_CPU_LIMIT=2
AGENT_MEMORY_LIMIT=4G

# Fast checkpointing (for testing)
CLAUDE_CHECKPOINT_INTERVAL=300  # 5 minutes
```

### Docker Compose Overrides

**Development** (`docker-compose.dev.yml`):
- Hot-reload enabled
- Source code mounted
- Debugger port exposed
- Relaxed security (for debugging)

**Production** (`docker-compose.prod.yml`):
- Read-only root filesystem
- No source mounts
- Strict security policies
- Resource limits enforced

**Usage:**
```bash
# Development
make dev                        # Uses base + dev override

# Production (future)
ENVIRONMENT=production make up  # Uses base + prod override
```

## Extending the System

### Adding New Agents

1. **Create agent definition** in `.claude/agents/` with appropriate prefix:

```markdown
---
name: data-analyst-expert
description: Specialized in data analysis and visualization
tools: Read, Write, Bash, mcp__context7
model: sonnet
---

You are a data analysis specialist...
```

**Note**: Use consistent prefix naming (e.g., `data-analyst-expert.md` for data agents, `dev-julia-expert.md` for development agents)

2. **Add agent service** in `docker-compose.yml`:

```yaml
data-analyst-agent:
  build:
    context: .
    dockerfile: agents/main/Dockerfile
    target: development
  environment:
    - AGENT_NAME=data-analyst
    - CLAUDE_MODEL=claude-sonnet-4-5-20250929
  volumes:
    - ./workspace:/workspace:ro  # Read-only for analysts
```

3. **Update Makefile** with agent-specific commands:

```makefile
.PHONY: shell-analyst
shell-analyst:
	docker compose exec -it data-analyst-agent /bin/bash
```

### Adding Custom Tools

1. **Create tool module** in `src/harness/tools/`:

```python
# src/harness/tools/custom_search.py
from typing import Dict, Any

class AdvancedSearchTool:
    """Advanced search with filters and ranking."""

    def __init__(self):
        self.name = "advanced_search"
        self.description = "Search with advanced filters"

    def execute(self, query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation
        return {"results": [...]}
```

2. **Register tool** in `agent.py`:

```python
from harness.tools.custom_search import AdvancedSearchTool

# In AgentSession.__init__
self.tools = {
    "advanced_search": AdvancedSearchTool(),
    # ... other tools
}
```

### Adding MCP Servers

**In-Process SDK Server:**

1. **Create server module** in `src/mcp_servers/your_server/`:

```python
# src/mcp_servers/database/server.py
class DatabaseMCPServer:
    def __init__(self):
        self.tools = {
            "mcp__database__query": self.query,
            "mcp__database__execute": self.execute,
        }

    def query(self, sql: str) -> Dict[str, Any]:
        # Implementation
        return {"rows": [...]}
```

2. **Register in agent.py**:

```python
from mcp_servers.database.server import DatabaseMCPServer

mcp_servers = {
    "database": DatabaseMCPServer(),
    # ... other servers
}
```

**External Subprocess Server:**

```python
mcp_servers = {
    "custom_server": {
        "command": "npx",
        "args": ["-y", "@your-org/custom-mcp-server"]
    }
}
```

## Code Quality Standards

### Linting & Formatting

**Ruff** (fast Python linter):
```bash
# Check code
make lint

# Auto-fix issues
make lint-fix

# Format code
make format
```

**Configuration** (`pyproject.toml`):
```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

### Type Checking

**Mypy** (static type checker):
```bash
# Run type checking
make typecheck
```

**Configuration** (`pyproject.toml`):
```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Type Hints Example:**
```python
from typing import Dict, List, Optional
from pathlib import Path

def save_checkpoint(
    state: Dict[str, Any],
    checkpoint_dir: Path,
    keep_last: int = 5
) -> Optional[Path]:
    """Save checkpoint with type-safe parameters."""
    # Implementation
```

### Security Implementation

**Non-Root Containers:**
```dockerfile
# Create non-root user
RUN useradd -m -u 1000 claude
USER claude
```

**Read-Only Filesystem:**
```yaml
services:
  agent:
    read_only: true
    tmpfs:
      - /tmp
```

**Secret Management:**
- All secrets in `.env` (gitignored)
- No hardcoded credentials
- Secret rotation recommended every 30 days
- Use environment variables for sensitive data

**Input Validation:**
```python
from pydantic import BaseModel, validator

class AgentConfig(BaseModel):
    agent_name: str
    max_turns: int

    @validator('max_turns')
    def validate_max_turns(cls, v):
        if v < 1 or v > 10000:
            raise ValueError("max_turns must be between 1 and 10000")
        return v
```

## Troubleshooting Development Issues

### Build Failures

**Cache issues:**
```bash
# Clear build cache
make build-no-cache

# Prune all unused resources
make prune
```

**Dependency issues:**
```bash
# Update dependencies
uv pip compile pyproject.toml -o requirements.txt

# Rebuild with fresh dependencies
make clean
make build
```

**Platform issues (ARM vs x86):**
```bash
# Check current platform
docker info | grep Architecture

# Force specific platform (if needed)
PLATFORM=linux/amd64 make build
```

### Test Failures

**Unit test failures:**
```bash
# Run specific test with verbose output
pytest tests/unit/test_checkpoint.py::test_save_checkpoint -v

# Run with debugging
pytest tests/unit/test_checkpoint.py --pdb
```

**Integration test failures (API errors):**
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Check token budget
pytest tests/integration/ -v | grep "tokens"

# Skip expensive tests
pytest tests/integration/ -m "not slow"
```

### Performance Issues

**Slow builds:**
```bash
# Use BuildKit caching
export DOCKER_BUILDKIT=1

# Use OrbStack (macOS)
# Much faster than Docker Desktop
```

**Slow tests:**
```bash
# Profile tests
pytest tests/ --durations=10

# Run only fast tests
pytest tests/unit/
```

### Debug Techniques

**Access container shell:**
```bash
make shell

# Inside container
python -m pdb script.py
```

**View logs with filtering:**
```bash
# Structured logs
make logs-json | jq 'select(.level == "error")'

# Grep for specific errors
make logs | grep -A 5 "ERROR"
```

**Performance profiling:**
```bash
make shell
python -m cProfile -o profile.stats -m harness.agent

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats
```

## Future Development

For production readiness status and security audit findings, see [docs/HARDENING.md](./docs/HARDENING.md).

## Contributing

### Coding Standards

Follow standards from `.claude/specs/`:
- **General**: `.claude/specs/general_code_standards.md`
- **Python**: `.claude/specs/python.md`
- **Make/Docker**: `.claude/specs/make.md`

### Pull Request Process

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Follow TDD: Write test → Implement → Pass → Refactor
4. Ensure 80%+ test coverage
5. Run `make lint` and `make typecheck`
6. Update documentation if needed
7. Submit PR with detailed description

### Development Requirements

- Python 3.12+ with type hints on all functions
- Ruff for linting and formatting
- Conventional commit messages
- 80%+ test coverage for new code
- Documentation for public APIs

## Resources

### Documentation
- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)
- [README.md](./README.md) - User-facing documentation

### SDKs
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [TypeScript SDK](https://github.com/anthropics/claude-agent-sdk-typescript)

### Development Tools
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Ruff](https://docs.astral.sh/ruff/) - Fast Python linter
- [pytest](https://docs.pytest.org/) - Testing framework
- [mypy](https://mypy.readthedocs.io/) - Static type checker

---

## Working Environment

You are running within the Claude Agent SDK Harness, a production-ready framework for autonomous software development.

### Directory Structure
- **App**: `/app` - System configuration (READ-ONLY)
  - `.claude/` - Agent definitions, skills, hooks, and specs (mounted from host)
    - `skills/` - 12 skills accessible via Skill tool
    - `agents/` - 44 agent definitions (reference documentation)
    - `specs/` - Coding standards (python, make, javascript, etc.)
- **Workspace**: `/workspace` - Clean canvas for development work
  - `/workspace/projects/` - Clone external repositories here
  - `/workspace/context/` - Technical context files (architecture, decisions, issues, next-steps)
  - `/workspace/` - Scratch space for agent operations
- **Memory**: `/memory` - Persistent state storage (checkpoints, MCP memory graph)
- **Logs**: `/logs` - Structured application and action logs
- **Config**: `/config` - System configuration files

**Important**: Agent cwd is `/app` for SDK configuration, but ALL development work must use `/workspace` with absolute paths.

### Configuration Files
- **`.env`** - All secrets and configuration (ANTHROPIC_API_KEY, MCP tokens, database credentials, etc.)
- **`.env.example`** - Template showing all available configuration options

### Working with External Repositories

When working on external repositories:
1. Clone repos to `/workspace/projects/{repo-name}/`
2. Access container shell: `make shell`
3. Change directory: `cd /workspace/projects/{repo-name}/`
4. Run commands directly in that directory

**Note**: External repos can have their own `.claude/` directories, but repository context switching is not yet implemented.

### Available MCP Servers

**In-Process MCP Servers** (Method A - loaded via `_load_inprocess_servers()`):
- **docker**: Container management and orchestration (always available)
- **context7**: Library documentation lookup (always available)
- **memory**: Knowledge graph for persistent memory (always available)

**Subprocess MCP Servers** (Method B - loaded via `.claude/.mcp.json`):
- **joplin**: Note-taking and documentation via npx (requires `JOPLIN_API_TOKEN`)
- **playwright**: Browser automation and testing via npx
- **excel-haris-musa**: Excel file manipulation via uvx (Python)

**CLI Tools** (use via Bash tool - NOT MCP):
- **git**: Version control (always available, SSH keys in `.ssh/`)
- **gh**: GitHub CLI for repos, issues, PRs (requires `gh auth login` or GITHUB_PERSONAL_ACCESS_TOKEN)
- **glab**: GitLab CLI for projects, issues, MRs (requires `glab auth login` or GITLAB_PERSONAL_ACCESS_TOKEN)

### Git, GitHub & GitLab CLI Reference

Use these CLI tools via the Bash tool for version control and platform operations.

#### Git (always available)
```bash
git status                          # Check working tree status
git diff                            # Show unstaged changes
git add . && git commit -m "msg"    # Stage and commit
git log --oneline -10               # Recent commit history
git checkout -b feature/name        # Create feature branch
git clone git@github.com:user/repo  # Clone via SSH
```

#### GitHub CLI (gh)
```bash
# Authentication (run once per container)
gh auth login                       # Interactive login
# Or set GITHUB_PERSONAL_ACCESS_TOKEN environment variable

# Common operations
gh repo view owner/repo             # View repo details
gh issue list                       # List issues
gh issue create --title "T" --body "B"
gh pr list                          # List pull requests
gh pr create --title "T" --body "B"
gh search code "pattern" --repo owner/repo
```

#### GitLab CLI (glab)
```bash
# Authentication (run once per container)
glab auth login                     # Interactive login
# Or set GITLAB_PERSONAL_ACCESS_TOKEN environment variable

# Common operations
glab repo view owner/project        # View project details
glab issue list                     # List issues
glab issue create --title "T" --description "B"
glab mr list                        # List merge requests
glab mr create --title "T" --description "B"
```

### SSH Keys (for Git Authentication)

SSH keys are configured for authenticating with GitHub and GitLab from within containers:

**Directory**: `.ssh/` (gitignored, read-only mount at `/home/claude/.ssh`)

**Configuration**: `.ssh/config` defines host entries for:
- `github.com` → uses `id_ed25519_github`
- `gitlab.com` → uses `id_ed25519_gitlab`

**Setup Commands**:
```bash
make ssh-init           # Initialize directory structure
make ssh-keygen-github  # Generate GitHub key
make ssh-keygen-gitlab  # Generate GitLab key
make ssh-test           # Test from host
make ssh-test-container # Test from inside container
```

**Security**: Keys are dedicated to this project, mounted read-only, and easily revocable.

See `.ssh/README.md` for detailed setup instructions.

### Monitoring & Observability
- Prometheus metrics are collected on port 9090
- Grafana dashboards available for session monitoring
- Action logging via hooks for audit trails
- Token usage and cost tracking enabled

## Guidelines for Agents

### Checkpointing
- Checkpoints are automatically saved every hour
- Recovery from latest checkpoint on restart
- Use memory MCP server for important context persistence

### Task Management
- Use TodoWrite tool for task planning and tracking
- Mark tasks as in_progress when starting
- Mark as completed immediately when done
- Break complex tasks into smaller steps

### Autonomous Mode

The harness supports long-running autonomous development sessions via `make autonomous`.

**Workspace State Detection:**

Before starting, the runner detects the workspace state and handles it appropriately:

| State | Condition | Action |
|-------|-----------|--------|
| **EMPTY** | Only SPEC.md or nothing | Run `git init`, proceed to initializer |
| **WORK_IN_PROGRESS** | task_list.json with incomplete tasks | Continue normally |
| **COMPLETED** | All tasks PASS/FAIL | Prompt: review or archive |
| **CONFLICT** | Multiple SPEC.md or task_list.json | REFUSE, require manual cleanup |
| **EXTERNAL_REPO** | .git exists, no SPEC.md + task_list.json | Ask: work on repo or clean |
| **MIXED** | Files exist, no .git | Warn, ask about cleanup |

**Workflow:**
```
1. Detect workspace state (see table above)
   → Handle state appropriately (git init, prompt user, etc.)

2. No task_list.json exists?
   → Run Initializer Mode (Tech Lead Q&A)
   → Generate task_list.json when requirements clear

3. task_list.json exists?
   → Run Continuation Mode (Coding Agent)
   → Work on highest priority incomplete task
   → Mark tasks complete or blocked
   → Commit changes
   → Loop until all tasks done
```

**External Repository Support:**

When working on an external repository (cloned from GitHub, GitLab, etc.), the SPEC.md **must** include a `branch` field:

```markdown
# Project: Feature Name

branch: casdk-feature-name

## Overview
...
```

**Branch Naming Convention:**
- Must start with `casdk-` prefix
- Use lowercase letters, numbers, and hyphens only
- Examples: `casdk-auth-system`, `casdk-api-v2`, `casdk-fix-123`

**Subagent Definitions (8 available):**

| Agent | Model | Purpose |
|-------|-------|---------|
| `tech-lead` | sonnet | Spec refinement, task planning |
| `python-expert` | sonnet | Python/FastAPI development |
| `typescript-expert` | sonnet | TS/React/Node development |
| `testing-agent` | haiku | Test writing and execution |
| `deployment-agent` | haiku | Docker/CI-CD configuration |
| `reviewer-agent` | sonnet | Code review (read-only) |
| `database-expert` | sonnet | Schema design, queries |
| `frontend-expert` | sonnet | React/CSS/UI development |

**Progress Tracking Files:**

| File | Purpose | Mutability |
|------|---------|------------|
| `task_list.json` | Task definitions with status and workspace config | Status field mutable |
| `sessions/session_N.json` | Session metadata + transcript | One per session |

**Commands:**
```bash
make autonomous          # Start autonomous development mode
make autonomous-model    # With specific model (MODEL=opus)
make autonomous-unsafe   # With all commands allowed (dangerous)
make autonomous-status   # Show progress status
```

### Agent Definitions (Not Yet Loaded)
- 44 agent definition files exist in `.claude/agents/` as reference documentation
- ⚠️ **Agent auto-discovery NOT implemented** - agents are not currently loaded by the SDK
- Agent definitions are organized by prefix: `dev-*`, `db-*`, `infra-*`, `ml-*`, `web-*`

### Plugins (Phase 1B - Workaround Active ⚠️)

The harness has 3 plugins configured in `.claude/plugins/`, but due to an SDK limitation (see below), plugin skills are manually discovered:

**1. arch** - Architecture and build orchestration
- **Agents**: build-orchestrator, arch-context-agent
- **Purpose**: System design, multi-agent coordination, context management
- **Location**: `/app/.claude/plugins/arch/`

**2. context-engineering** - Agent/skill/plugin creation toolkit
- **Agents**: context-engineer
- **Skills**: agent-definition-creation, skill-creation, plugin-development, command-creation, hook-configuration
- **Purpose**: Create production-ready Claude Code resources
- **Location**: `/app/.claude/plugins/context-engineering/`

**3. research-team** - Multi-agent research system
- **Agents**: lead-research-coordinator, research-specialist, research-report-writer
- **Skills**: joplin-research
- **Purpose**: Comprehensive topic investigation with parallel execution
- **Location**: `/app/.claude/plugins/research-team/`

**Plugin Discovery (SDK Limitation - Workaround Active)**:
- ⚠️ **SDK Bug**: Python SDK v0.1.9 accepts `plugins` parameter but Claude CLI subprocess not loading them
- **Known Issues**: [GitHub #11620](https://github.com/anthropics/claude-code/issues/11620), [#213](https://github.com/anthropics/claude-agent-sdk-python/issues/213)
- ✅ **Workaround**: Manual plugin skill discovery implemented in `src/harness/agent.py`
- ✅ Plugin skills (6 total) are discovered and available via Skill tool
- ⚠️ Plugin agents NOT accessible (deferred to Phase 2)
- Each plugin has a `.claude-plugin/plugin.json` manifest file
- Skills available: 12 base + 6 plugin = 18 total (via manual discovery)

**Adding New Plugins**:
1. Install plugin to `.claude/plugins/{plugin-name}/`
2. Create `.claude-plugin/plugin.json` manifest with required fields
3. Add to `plugins` array in `src/harness/agent.py`
4. Restart agent session to load new plugin

**Plugin Structure**:
```
.claude/plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json          # Required manifest
├── agents/                   # Optional
├── skills/                   # Optional
├── commands/                 # Optional
└── hooks/                    # Optional
```


### Best Practices
1. Check memory for existing project context before starting
2. Log important decisions and findings to memory
3. Provide progress updates for long-running operations
4. Follow the coding standards in `.claude/specs/`
5. Test code changes before committing
6. Use structured logging for better observability

### Security & Permissions
- Permission mode can be `manual`, `acceptAll`, or `acceptNone`
- Workspace access is read-write by default
- Some agents may have read-only access (e.g., reviewer agents)
- Never expose secrets in logs or commits

## Session Context

This harness supports two primary modes:
1. **Interactive Mode**: Direct conversation with immediate feedback
2. **Service Mode**: Long-running autonomous development sessions

The SDK currently loads:
- This CLAUDE.md file for runtime context
- ✅ MCP servers (6 total: 3 in-process + 3 subprocess) - see "Available MCP Servers" section
- ✅ CLI tools (git, gh, glab) for version control and platform operations
- ~~Plugins from `.claude/plugins/`~~ ⚠️ Phase 1B Workaround (plugin skills manually discovered)
- ~~Skills from `.claude/skills/`~~ ✅ Phase 1 Complete (12 base skills + 6 plugin skills via workaround)

**Not Yet Implemented**:
- Agent definitions from `.claude/agents/` (SDK limitation)
- Coding standards from `.claude/specs/`

---

**Maintainer**: Andis A. Blukis (andis.blukis@gmail.com)
**License**: MIT
**Version**: 0.1.0 (Alpha)
