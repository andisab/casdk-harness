>[toc]

# Claude Agent SDK Harness - Technical Documentation

**Last updated**: October 26, 2025

## Current Status

**Phase**: Enhanced Observability (Fixes Applied, Testing Required)
**Test Coverage**: ~61% (Target: 80%+)
**Last Updated**: October 26, 2025

### What's Working
- ✅ Interactive conversation mode with Rich CLI (cli.py, interactive.py)
- ✅ Action logging hooks and session metrics (infrastructure in place)
- ✅ Grafana dashboard with 10 panels (visible and accessible)
- ✅ Docker orchestration with Prometheus + Grafana monitoring
- ✅ Checkpoint & recovery system with auto-save
- ✅ MCP server integration (git, docker, memory, context7, playwright, joplin)
- ✅ Token usage tracking and cost calculation (implementation complete)
- ✅ **FIXED**: Grafana datasource configuration (Prometheus connection)
- ✅ **FIXED**: Metrics port exposure in docker-compose.yml (9090 now exposed)
- ✅ **FIXED**: Token usage tracking in interactive sessions (ResultMessage handling)

### Recent Fixes (October 26, 2025)

**Issue #1: Missing Grafana Datasource Configuration**
- **Problem**: Grafana had no datasource configuration to connect to Prometheus
- **Fix**: Created `config/monitoring/datasources/prometheus.yml` and mounted in docker-compose.yml
- **Impact**: Grafana can now query Prometheus for metrics data

**Issue #2: Metrics Port Not Exposed**
- **Problem**: Agent containers didn't expose port 9090 for Prometheus scraping
- **Fix**: Added port mappings in docker-compose.yml:
  - main-agent: 9091:9090
  - reviewer-agent: 9092:9090
  - tester-agent: 9093:9090
- **Impact**: Prometheus can now scrape metrics from all agent containers

**Issue #3: Token Usage Not Tracked in Interactive Sessions**
- **Problem**: Type checking in agent.py used `isinstance(message, dict)` but SDK yields `ResultMessage` objects
- **Fix**: Updated agent.py:src/harness/agent.py:220 to check for `ResultMessage` type instead
- **Impact**: Token usage, costs, and cache metrics are now properly recorded during interactive sessions

### What's Pending
- [ ] **TEST: Restart containers to apply fixes** (`docker compose down && docker compose up -d`)
- [ ] **TEST: Verify Prometheus is scraping metrics** (check http://localhost:9090/targets)
- [ ] **TEST: Verify Grafana shows accurate data** (check Interactive Sessions dashboard)
- [ ] End-to-end testing of full observability stack
- [ ] Commit untracked files to git (cli.py, interactive.py, hooks/, datasources/)
- [ ] Increase test coverage to 70%+ (interim goal toward 80%)
- [ ] Test action logging with real agent sessions

✅ **Status Update**: Three critical issues identified and fixed. Metrics pipeline should now work correctly after container restart.

### Next Steps
1. Complete testing of observability features
2. Commit working changes to git
3. Polish core functionality and improve test coverage
4. Then: Configuration & extensibility features (see docs/future/)

⚠️ **Note**: Some documented features are implemented but not yet committed to git.

## To Do

### Immediate (Complete Current Phase)
- [x] **FIXED: Grafana datasource configuration** (created prometheus.yml datasource)
- [x] **FIXED: Prometheus scraping configuration** (exposed port 9090 on agent containers)
- [x] **FIXED: Metric collection in interactive sessions** (ResultMessage type handling)
- [ ] **TEST: Restart containers and verify fixes** (`docker compose down && docker compose up -d`)
- [ ] **TEST: Check Prometheus targets** (http://localhost:9090/targets should show all agents)
- [ ] **TEST: Verify Grafana data accuracy** (Interactive Sessions dashboard)
- [ ] Test full observability stack end-to-end with real agent session
- [ ] Test action logging hook with real agent sessions
- [ ] Commit all implementation files (cli.py, interactive.py, hooks/, datasources/, agent.py changes)
- [ ] Improve test coverage to 70%+ (interim goal)

### Near-term (Polish & Stabilize)
- [ ] Verify all MCP servers function correctly
- [ ] Run integration tests with real API (record VCR cassettes if applicable)
- [ ] Create example workflow scripts
- [ ] Improve test coverage to 80%+ (final goal)
- [ ] Stabilize Docker service startup and health checks

### Future (Deferred - See docs/future/)
- Configuration builder system (YAML/JSON profiles)
- Agent library with auto-discovery
- Tool registry and custom tool development
- External repository support (git clone, volume mounting)
- Web frontend UI (separate project)
- Jaeger distributed tracing
- K8s deployment manifests
- CI/CD pipeline templates

## Project Overview

The Claude Agent SDK Harness is a production-ready, enterprise-grade framework for building autonomous software development systems using Anthropic's Claude Agent SDK. This harness provides the infrastructure, tooling, and patterns needed to run long-running (20+ hour) autonomous agent sessions with full observability, fault tolerance, and recovery capabilities.

### Key Features

- **Multi-Agent Orchestration**: Coordinate multiple specialized agents (development, review, testing)
- **Checkpoint & Recovery**: Automatic state persistence with configurable intervals
- **Full Observability**: Prometheus metrics, Grafana dashboards, structured logging
- **Resource Management**: Container-level CPU/memory limits, OrbStack optimized builds
- **Security**: Non-root containers, secret management, network isolation
- **Extensibility**: Plugin architecture for custom agents and MCP servers
- **Cloud Ready**: Local Docker Compose for development, future K8s support

### Architecture Principles

1. **KISS, DRY, SOLID, YAGNI**: Follow universal code standards
2. **Separation of Concerns**: Clear boundaries between agents, infrastructure, and business logic
3. **Fail Fast**: Comprehensive validation and error handling
4. **Observability First**: Everything is logged, metered, and traceable
5. **Security by Default**: Least privilege, secret rotation, audit logs
6. **Cloud Native**: Container-first, stateless where possible, config via environment

## Repository File Structure & Architecture

```
claudeagentsdk-harness/
├── .claude/                    # Claude Code configuration
│   ├── agents/                 # Agent definitions (copied from ABDotfiles)
│   │   ├── development/        # Language-specific experts (python, typescript, go, rust, etc.)
│   │   └── infrastructure/     # Cloud & K8s specialists (docker, k8s, terraform, aws, gcp)
│   └── specs/                  # Coding standards (python, make, general)
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
│   └── mcp/                    # Custom MCP servers (placeholders)
│       ├── __init__.py
│       ├── filesystem/
│       ├── git/
│       └── docker/
│
├── config/                     # Configuration files
│   └── monitoring/             # Prometheus & Grafana configs
│       ├── prometheus.yml      # Scrape configs for all agents
│       ├── alerting.yml        # Alert rules (errors, latency, cost)
│       └── dashboards/
│           └── overview.json   # Grafana overview dashboard
│
├── workspace/                  # Agent working directory (gitignored)
│   └── .gitkeep
│
├── memory/                     # Persistent agent memory (gitignored)
│   ├── checkpoints/
│   │   └── .gitkeep
│   └── context/
│       └── .gitkeep
│
├── logs/                       # Application logs (gitignored)
│   ├── main/.gitkeep
│   ├── reviewer/.gitkeep
│   ├── tester/.gitkeep
│   └── orchestrator/.gitkeep
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── unit/                   # Unit tests (checkpoint, config)
│   │   ├── test_checkpoint.py
│   │   └── test_config.py
│   ├── smoke/                  # Smoke tests (placeholder)
│   ├── integration/            # Integration tests (placeholder)
│   └── e2e/                    # End-to-end tests (placeholder)
│
├── examples/                   # Example workflows (placeholders)
│   ├── simple-feature/
│   ├── bug-fix/
│   ├── refactoring/
│   └── full-project/
│
├── k8s/                        # Kubernetes manifests (future)
│   ├── base/
│   ├── overlays/
│   └── helm/
│
├── scripts/                    # Utility scripts (future)
│
├── docs/                       # Additional documentation (future)
│
├── docker-compose.yml          # Base compose configuration ✅
├── docker-compose.dev.yml      # Development override with hot-reload ✅
├── docker-compose.prod.yml     # Production override with security ✅
├── Makefile                    # 60+ build and operation commands ✅
├── pyproject.toml              # Python project configuration ✅
├── .env.example                # Environment variables template ✅
├── .dockerignore               # Docker build exclusions ✅
├── .gitignore                  # Git exclusions ✅
├── CLAUDE.md                   # This file
└── README.md                   # User-facing documentation
```

## Getting Started

### Prerequisites

- **Docker**: 24.0+ with BuildKit enabled
- **Docker Compose**: 2.22+ (for watch mode support)
- **Python**: 3.12 or 3.13
- **Make**: GNU Make 4.0+
- **API Key**: Anthropic API key with appropriate quota
- **Git**: For version control
- **8GB+ RAM**: Minimum for running multiple agents
- **50GB+ Disk**: For workspace, logs, and checkpoints
- **OrbStack** (recommended for macOS): Optimized builds with better performance

### Important: Always Use Make Commands

**ALWAYS use `make` commands instead of direct `docker compose` commands**. The Makefile handles proper compose file selection, environment variables, and platform settings automatically.

✅ Correct: `make down`, `make up`, `make dev`
❌ Incorrect: `docker compose down`, `docker compose up -d`

The Makefile uses the correct compose file combinations and environment settings for your platform.

### Initial Setup

```bash
# Navigate to repository
cd ~/Projects/claudeagentsdk-harness

# Initialize directories and create .env file
make init

# Edit .env and add your ANTHROPIC_API_KEY
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# Build all containers (OrbStack optimized with BuildKit caching)
make build

# Start development environment with hot-reload
make dev
```

### Quick Start Commands

```bash
# Development
make dev                    # Start with hot-reload and watch mode
make shell                  # Shell into main agent container
make logs                   # Tail all service logs
make logs-json              # Structured JSON logs

# Operations
make up                     # Start all services
make down                   # Stop all services
make restart                # Restart services
make ps                     # Show running containers
make clean                  # Remove containers and volumes

# Testing
make test                   # Run full test suite
make test-unit              # Unit tests only
make test-integration       # Integration tests (when implemented)
make test-e2e               # End-to-end tests (when implemented)
make coverage               # Generate coverage report

# Code Quality
make lint                   # Run ruff linter
make lint-fix               # Auto-fix linting issues
make format                 # Format code with ruff
make typecheck              # Run mypy type checking

# Monitoring
make metrics                # Open Grafana dashboard (localhost:3000)
make prometheus             # Open Prometheus UI (localhost:9090)
make health                 # Check all services health

# Database
make db-shell               # PostgreSQL shell
make db-backup              # Backup database
make db-restore             # Restore from backup

# Maintenance
make backup                 # Backup workspace and checkpoints
make restore                # Restore from latest backup
make prune                  # Clean up unused Docker resources
make reset                  # Full reset (destructive!)

# Diagnostics
make doctor                 # Run diagnostics
make version                # Show version information

# Interactive Agent (Phase 1)
make interactive            # Start interactive conversation session
make chat                   # Alias for interactive mode
make interactive-model MODEL=opus  # Use specific model (opus, sonnet, haiku)
```

## Quick Start Examples (No Docker Required)

Before diving into the full harness infrastructure, you can try these simple examples to understand the Claude Agent SDK basics. These examples run directly without Docker and are perfect for learning or quick testing.

### Prerequisites

```bash
# Make sure you're in the repository root
cd ~/Projects/claudeagentsdk-harness

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Ensure ANTHROPIC_API_KEY is set in .env
echo "ANTHROPIC_API_KEY=sk-ant-your_key_here" >> .env
```

### Example 1: Simple Query Pattern

**File**: `examples/simple_query.py`

**What it demonstrates**:
- Basic `query()` function for one-off questions (stateless)
- `ClaudeSDKClient` for multi-turn conversations (stateful)
- Message streaming and parsing

**Run it**:
```bash
# Run with default model (haiku - cheapest)
python examples/simple_query.py

# Run with more powerful models
python examples/simple_query.py --model sonnet
python examples/simple_query.py --model opus
```

**What you'll see**:
- Example 1: A simple query/response using `query()`
- Example 2: Same query using `ClaudeSDKClient` (shows stateful pattern)

**Cost**: ~$0.001-0.01 per run (using haiku model)

### Example 2: Basic Interactive Mode

**File**: `examples/interactive_basic.py`

**What it demonstrates**:
- Continuous conversation loop
- Rich formatted output with colored panels
- Integration with harness CLI utilities
- Session management with graceful exit

**Run it**:
```bash
# Run with default model (haiku)
python examples/interactive_basic.py

# Run with sonnet for better performance
python examples/interactive_basic.py --model sonnet

# Show session stats on exit
python examples/interactive_basic.py --model sonnet --stats
```

**What you'll see**:
```
┌──────────────────────────────────────┐
│     Basic Interactive Mode           │
│                                      │
│ Selected model: haiku                │
│                                      │
│ Type your questions or requests      │
│ Type 'exit' or 'quit' to end        │
└──────────────────────────────────────┘

You: _
```

**Features**:
- Type naturally and get formatted responses
- Maintains conversation context across turns
- Type `exit` or `quit` to end the session
- Optional `--stats` flag shows token usage and costs

**Cost**: ~$0.01-0.10 per session (depending on length and model)

### Key Differences from Full Interactive Mode

| Feature | Basic Examples | Full Harness (`make interactive`) |
|---------|----------------|-----------------------------------|
| Docker Required | ❌ No | ✅ Yes |
| Checkpointing | ❌ No | ✅ Auto-save every hour |
| Metrics | ❌ No | ✅ Prometheus + Grafana |
| MCP Servers | ❌ Basic only | ✅ Git, Docker, Memory, etc. |
| Multi-Agent | ❌ No | ✅ Orchestration support |
| Setup Time | < 1 minute | ~5-10 minutes |
| Best For | Learning, testing | Production, long sessions |

### Next Steps

Once you're comfortable with these examples:

1. **Try the full interactive mode** (see next section) for production features
2. **Explore MCP integration** - Add custom tools and servers
3. **Build workflows** - Combine multiple agents for complex tasks
4. **Add monitoring** - Use Grafana dashboards to track costs and performance

## Phase 1: Interactive Agent Setup

### Overview

Phase 1 adds interactive conversation mode to the harness, allowing you to chat directly with Claude agents using a Rich console UI. This mode integrates seamlessly with the existing infrastructure (checkpointing, monitoring, MCP servers) while providing an intuitive CLI experience.

### Components

**CLI Module** (`src/harness/cli.py`):
- Rich console formatting for all message types (user, assistant, tool_use, tool_result, system)
- Message parsing for SDK messages (AssistantMessage, UserMessage, SystemMessage, ResultMessage)
- Session statistics display (tokens, cost, duration, cache usage)
- Structured logging integration with correlation IDs

**Interactive Module** (`src/harness/interactive.py`):
- Conversation loop with Rich UI
- Integration with AgentSession (automatic checkpointing, metrics)
- Checkpoint recovery on session start
- Graceful error handling and session shutdown
- Support for CLI arguments (--model, --stats, --print-raw)

**Makefile Targets**:
- `make interactive` - Start interactive session with default model (sonnet)
- `make chat` - Alias for interactive mode
- `make interactive-model MODEL=opus` - Use specific model

### Usage

**Start an Interactive Session**:
```bash
# 1. Ensure Docker is running
make dev

# 2. In another terminal, start interactive mode
make interactive
```

**What You'll See**:
```
┌─────────────────────────────────────────────┐
│            🤖 Welcome                       │
├─────────────────────────────────────────────┤
│ Claude Agent SDK Harness                    │
│ Production-ready autonomous framework       │
│                                             │
│ Agent: main                                 │
│ Model: claude-sonnet-4-5-20250929          │
│                                             │
│ Type 'exit' or 'quit' to end the session   │
└─────────────────────────────────────────────┘

You: _
```

**Features**:
- ✅ Rich formatted messages with colored panels
- ✅ Syntax highlighting for JSON tool results
- ✅ Real-time tool use display
- ✅ Session statistics on exit
- ✅ Automatic checkpoint recovery
- ✅ Graceful error handling
- ✅ Integration with all MCP servers

**Using Different Models**:
```bash
# Use Opus (most capable)
make interactive-model MODEL=opus

# Use Haiku (fastest, cheapest)
make interactive-model MODEL=haiku

# Use Sonnet (default, balanced)
make interactive
```

**View Session Stats**:
When you exit with "quit" or "exit", you'll see:
```
┌─────────────────────┬──────────────────────┐
│      Session Stats                        │
├─────────────────────┼──────────────────────┤
│ Session ID          │ main_2025-10-26...  │
│ Result              │ success             │
│ Duration (s)        │ 125.34              │
│ Cost (USD)          │ $0.0342             │
│ Input Tokens        │ 12,450              │
│ Output Tokens       │ 3,210               │
│ Cache Read Tokens   │ 8,940               │
│ Cache Creation ...  │ 1,200               │
└─────────────────────┴──────────────────────┘
```

### Architecture

**Message Flow**:
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

**Integration Points**:
- `AgentSession` - Handles checkpointing, metrics, retry logic
- `MetricsCollector` - Tracks tokens, cost, duration automatically
- `CheckpointManager` - Auto-saves every hour, recovers on startup
- `MCP Servers` - Git, Docker, Memory, Context7, Playwright, etc.
- `structlog` - Structured logging with correlation IDs

### Checkpoint Recovery

If your session is interrupted, the next session will automatically recover:

```bash
make interactive

# Output:
✓ Recovered from previous checkpoint

You: _
```

The agent resumes with:
- Completed tasks list
- Session state (agent name, session ID, timestamps)
- Workspace and memory context

### Troubleshooting

**Issue: "Module not found: harness.cli"**
```bash
# Rebuild the container
make build
make dev
```

**Issue: "Not running in Docker container"**
```bash
# Start Docker services first
make dev

# Then in another terminal:
make interactive
```

**Issue: "Permission denied" or "No tty available"**
```bash
# Ensure you're using make interactive, not direct docker commands
make interactive  # Correct
docker compose exec main-agent python -m harness.interactive  # Wrong (missing -it)
```

**Issue: "Session stats not displayed"**
```bash
# Stats are enabled by default. To disable:
make interactive-model MODEL=sonnet STATS=false
```

### Next Steps (Phase 2)

Now that interactive mode is working, Phase 2 will add:

1. **Configuration Builder** - Load agent configs from YAML/JSON profiles
2. **Agent Library** - Auto-discover and load agent definitions from `.claude/agents/`
3. **Tool Registry** - Plugin architecture for custom tools
4. **Enhanced Observability** - Port logging hooks from intro repository
5. **Workflow Templates** - Pre-built workflows (feature, bug-fix, refactor)
6. **Session Management** - Save/load conversations, session analytics

See [Phase 2 Roadmap](#phase-2-configuration--extensibility-roadmap) below for details.

## Configuration Settings

### Environment Variables

All configuration is done through `.env` file (copy from `.env.example`):

```bash
# ============================================================================
# Required Configuration
# ============================================================================
ANTHROPIC_API_KEY=sk-ant-your_api_key_here

# ============================================================================
# Agent Configuration
# ============================================================================
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_PERMISSION_MODE=acceptEdits  # manual|acceptEdits|acceptAll
CLAUDE_MAX_TURNS=1000
CLAUDE_SESSION_TIMEOUT=72000  # 20 hours in seconds
CLAUDE_CHECKPOINT_INTERVAL=3600  # 1 hour

# ============================================================================
# Infrastructure
# ============================================================================
DOCKER_BUILDKIT=1
BUILDKIT_PROGRESS=plain
COMPOSE_PROJECT_NAME=claude-harness
PLATFORM=linux/arm64  # OrbStack default

# ============================================================================
# Resource Limits
# ============================================================================
AGENT_CPU_LIMIT=4
AGENT_MEMORY_LIMIT=8G
AGENT_CPU_RESERVATION=2
AGENT_MEMORY_RESERVATION=4G

# ============================================================================
# Monitoring
# ============================================================================
GRAFANA_PASSWORD=changeme123
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION=30d
LOG_LEVEL=INFO              # DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG_FORMAT=json             # json|text

# ============================================================================
# Database Configuration
# ============================================================================
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=claude_harness
POSTGRES_USER=claude
POSTGRES_PASSWORD=changeme_postgres_password

# ============================================================================
# Redis Configuration
# ============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=changeme_redis_password
```

### Agent Configuration

Agent definitions are in `.claude/agents/` (copied from ABDotfiles):

**Development Agents**:
- `python-expert.md` - Python with FastAPI, async, type safety
- `typescript-expert.md` - TypeScript with modern patterns
- `nodejs-expert.md` - Node.js backend development
- `go-expert.md`, `rust-expert.md`, `cpp-expert.md`, etc.

**Infrastructure Agents**:
- `docker-engineer.md` - Docker and container optimization
- `k8s-engineer.md` - Kubernetes orchestration
- `terraform-engineer.md` - Infrastructure as Code
- `gcp-cloud-architect.md`, `aws-cloud-architect.md`

Each agent definition includes:
- Name and description
- Allowed tools (Read, Write, Bash, Grep, etc.)
- Model selection (sonnet, opus, haiku)
- Specialized prompts and instructions

## Setup, Build, & Test Settings

### Docker Build Configuration

Multi-stage Dockerfile optimized for OrbStack with BuildKit caching:

**Stage 1: Base** - Common system dependencies
**Stage 2: Dependencies** - Python packages with cache mounts
**Stage 3: Development** - Full dev tools + Claude CLI
**Stage 4: Builder** - Compile and prepare production assets
**Stage 5: Production** - Minimal runtime image

Build optimizations:
- Cache mounts for `uv` package manager
- Layer ordering from least to most frequently changing
- Separate dependency and source code layers
- Non-root user for security

### Testing Strategy

Following TDD principles with 80%+ coverage requirement:

```bash
# Unit tests (fast, isolated)
make test-unit

# Integration tests (with Docker services)
make test-integration

# E2E tests (full workflows)
make test-e2e

# Smoke tests (quick validation)
make test-smoke

# Coverage report
make coverage
```

**Current Test Coverage**:
- ✅ `test_checkpoint.py` - Checkpoint save, load, cleanup
- ✅ `test_config.py` - Configuration, URLs, paths
- ✅ `test_agent_sdk_direct.py` - Direct SDK integration tests with real API
- ✅ `test_mcp_git.py` - Git MCP server integration tests
- ✅ `test_mcp_docker.py` - Docker MCP server integration tests
- 🚧 E2E tests - Not yet implemented
- **Overall**: ~61% (target: 80%+)

**Important Testing Notes**:
- **No VCR.py**: The Claude Agent SDK uses subprocess communication (stdin/stdout), not HTTP. VCR.py cannot intercept subprocess I/O, so all integration tests make real API calls.
- **API Costs**: Integration tests consume API tokens. Use `ANTHROPIC_API_KEY` environment variable and monitor costs.
- **Test Markers**: Use `@pytest.mark.slow` for expensive tests that can be skipped with `-m "not slow"`

### Cost Management & Testing Strategy

**Integration tests make real API calls** because the Claude Agent SDK uses subprocess communication (not HTTP), which VCR.py cannot intercept.

#### Token Budget Tracking

Tests include automatic token budget tracking to prevent runaway costs:

- **Limit**: 1,000,000 tokens per test session
- **Tracking**: Automatic via `token_budget` fixture in conftest.py
- **Behavior**: Tests fail if budget exceeded

#### Recommended Test Strategy

```bash
# Daily development: Unit tests only (fast, free)
make test-unit

# Integration tests: Use selectively (costs ~$0.10-$0.50 per run)
ANTHROPIC_API_KEY=xxx make test-integration

# Skip expensive tests during development
make test-unit && pytest tests/integration/ -m "not slow"

# Full suite (costs ~$1-$5 depending on tests)
ANTHROPIC_API_KEY=xxx make test
```

#### Cost Optimization

To minimize API costs during testing:
- Run unit tests frequently (free, instant)
- Run integration tests only when needed (e.g., before commits, weekly)
- Use `@pytest.mark.slow` for expensive tests
- Mock SDK responses in unit tests when possible
- Monitor token usage in test output

## Verification Checklist

Before first real use:

- [ ] Verify `ANTHROPIC_API_KEY` is set in `.env`
- [ ] Run `make test-unit` to confirm existing tests pass
- [ ] Run `ANTHROPIC_API_KEY=xxx make test-integration` to record cassettes
- [ ] Run `make test-integration` again to verify replay works
- [ ] Check Prometheus metrics are being collected at `localhost:9090`
- [ ] Verify workspace and checkpoint directories are writable
- [ ] Test at least one MCP server manually (filesystem recommended)
- [ ] View Grafana dashboards at `localhost:3000` to confirm monitoring

## Implementation Notes

### Core Python Modules

#### config.py
Pydantic-based configuration with:
- Environment variable loading from `.env`
- Type-safe settings with validation
- Database and Redis URL generation
- Directory path management
- Feature flags

```python
from harness.config import get_config

config = get_config()
print(config.database_url)  # postgresql+asyncpg://...
print(config.checkpoint_dir)  # /memory/checkpoints
```

#### checkpoint.py
Automatic checkpoint management:
- Configurable checkpoint intervals (default: 1 hour)
- Auto-cleanup of old checkpoints (keep 5 most recent)
- JSON-based state persistence
- Recovery from latest checkpoint
- Workspace and memory snapshots

```python
from harness.checkpoint import CheckpointManager

manager = CheckpointManager(checkpoint_dir=Path("/memory/checkpoints"))
checkpoint_file = manager.save_checkpoint({"state": "data"})
latest = manager.load_latest_checkpoint()
```

#### monitoring.py
Prometheus metrics collection:
- Request counters by agent and status
- Duration histograms for latency tracking
- Active session gauges
- Checkpoint size monitoring
- API token usage and cost tracking

```python
from harness.monitoring import MetricsCollector

metrics = MetricsCollector(port=9090)
metrics.start()
metrics.record_request(agent="main", status="success")
metrics.record_duration(agent="main", duration=1.5)
```

#### agent.py
Agent session wrapper:
- Session lifecycle management
- Automatic checkpointing integration
- Metrics collection integration
- Retry logic with exponential backoff
- Error handling and recovery

**Note**: Currently uses placeholder execution. Needs Claude Agent SDK integration.

```python
from harness.agent import AgentSession

session = AgentSession(agent_name="main")
await session.start()

async for message in session.execute("Build a FastAPI endpoint"):
    print(message)

await session.shutdown()
```

### Docker Compose Services

**main-agent**: Primary development agent
- Ports: 8080 (HTTP), 5678 (debugger in dev mode)
- Resources: 4 CPU, 8GB RAM
- Volumes: workspace, memory, logs, config
- Health checks enabled

**reviewer-agent**: Code review agent
- Read-only workspace access
- Manual permission mode
- 50 max turns (focused reviews)

**tester-agent**: Test generation and execution
- Full workspace access
- Accept-all permission mode
- 100 max turns

**postgres**: PostgreSQL 16 database
- Persistent volume for data
- Health checks

**redis**: Redis 7 cache and pub/sub
- AOF persistence enabled
- Health checks

**prometheus**: Metrics collection
- 30-day retention (configurable)
- Scrapes all agent metrics
- Alert rules configured

**grafana**: Visualization dashboards
- Admin password configurable
- Overview dashboard pre-configured
- Connected to Prometheus

### MCP Server Configuration

The harness integrates multiple MCP (Model Context Protocol) servers to extend Claude's capabilities:

**In-Process SDK Servers** (custom Python implementations):
- **git**: Structured git operations (status, diff, log)
  - Tools: `mcp__git__git_status`, `mcp__git__git_diff`, `mcp__git__git_log`
  - Implementation: `src/mcp_servers/git/server.py`
- **docker**: Container management and monitoring
  - Tools: `mcp__docker__list_containers`, `mcp__docker__container_logs`, `mcp__docker__container_stats`
  - Implementation: `src/mcp_servers/docker/server.py`

**External MCP Servers** (subprocess via npx):
- **memory**: Knowledge graph for agent memory persistence
  - Package: `@modelcontextprotocol/server-memory`
- **context7**: Library documentation lookup
  - Package: `@context7/mcp-server`
- **joplin**: Note-taking and documentation integration
  - Package: `@joplin/mcp-server`
- **github**: GitHub operations via CLI
  - Package: `@modelcontextprotocol/server-github`
- **playwright**: Browser automation and testing
  - Package: `@modelcontextprotocol/server-playwright`

**Configuration:**
MCP servers are registered in `src/harness/agent.py` as a dictionary combining both in-process SDK servers and external subprocess servers. External servers are launched via `npx` (Node.js) automatically when the agent starts.

**Note:** Claude Code built-in tools (Read, Write, Bash, Glob, Grep, etc.) are always available and don't require MCP server configuration.

### Monitoring & Observability

#### Prometheus Metrics

**General Agent Metrics** (all agents, port 9090):
- `agent_requests_total{agent, status}` - Request counts by status
- `agent_duration_seconds{agent}` - Execution duration histogram
- `agent_active_sessions{agent}` - Active session count
- `checkpoint_size_bytes` - Total checkpoint storage
- `workspace_files_total` - Files in workspace
- `memory_usage_bytes{component}` - Memory usage by component
- `api_tokens_used_total{model, type}` - Token consumption (input/output/cached)
- `api_cost_dollars_total{model}` - API costs in USD

**Interactive Session Metrics** (NEW):
- `interactive_session_prompts_total{agent, session_id}` - User prompt count
- `interactive_session_responses_total{agent, session_id}` - Agent response count
- `interactive_session_duration_seconds{agent}` - Session duration histogram
- `interactive_tool_calls_total{agent, tool_name, status}` - Tool usage frequency
- `interactive_message_types_total{agent, message_type}` - Message type distribution
- `interactive_cache_read_tokens_total{agent, model}` - Cache read tokens
- `interactive_cache_creation_tokens_total{agent, model}` - Cache creation tokens
- `interactive_cache_hit_ratio{agent}` - Cache hit ratio (0-1)

#### Alert Rules

Pre-configured alerts in `config/monitoring/alerting.yml`:

**Agent Alerts**:
- High error rate (>5% for 5min)
- Slow response time (p95 >30s for 10min)
- No active sessions (15min)

**Resource Alerts**:
- High memory usage (>7GB for 5min)
- Large checkpoint size (>1GB for 10min)
- High workspace file count (>10,000 files)

**Cost Alerts**:
- High API costs (>$10/hour)
- High token usage (>1M tokens/hour)

#### Grafana Dashboards

Access at http://localhost:3000 (default: admin / changeme123)

**Overview Dashboard**:
- Active sessions count
- Request rate by agent and status
- Response time (p95) by agent
- API cost per hour by model

### Security Best Practices

1. **Secrets Management**: All secrets in `.env` (gitignored)
2. **Non-root Containers**: All services run as non-root users
3. **Network Isolation**: Bridge network with isolated services
4. **Resource Limits**: CPU and memory limits on all services
5. **Read-only Filesystems**: Where possible
6. **Health Checks**: All services monitored
7. **Audit Logging**: Structured logs with correlation IDs

### Performance Optimization

1. **BuildKit Caching**: Cache mounts reduce build time from minutes to seconds
2. **OrbStack**: Native ARM64 builds on macOS (2x faster than Docker Desktop)
3. **Layer Ordering**: Dependencies change less frequently than source code
4. **Multi-stage Builds**: Minimal production images
5. **Async I/O**: Non-blocking operations throughout Python SDK
6. **Connection Pooling**: Reuse database and Redis connections

## Troubleshooting

### Common Issues

**Issue**: `ANTHROPIC_API_KEY` not set
```bash
# Check .env file
cat .env | grep ANTHROPIC_API_KEY

# Add to .env
echo "ANTHROPIC_API_KEY=sk-ant-your_key" >> .env
```

**Issue**: Containers won't start
```bash
# Check Docker daemon
docker info

# Check for port conflicts
docker compose ps

# View specific service logs
make logs-main
```

**Issue**: Out of memory errors
```bash
# Increase memory in .env
AGENT_MEMORY_LIMIT=16G

# Restart services
make down && make up
```

**Issue**: Build cache issues
```bash
# Clean build without cache
make build-no-cache

# Or prune everything
make prune
```

### Debug Mode

```bash
# Start with debug logging
DEBUG=true make dev

# Access shell for debugging
make shell

# Check service health
make health
```

### Performance Profiling

```bash
# Inside container
make shell
python -m cProfile -o profile.stats -m harness.agent

# Analyze results
pip install snakeviz
snakeviz profile.stats
```

## Enhanced Observability & Hooks

### Overview

The harness includes comprehensive observability for interactive sessions with real-time Prometheus metrics, Grafana dashboards, and action logging hooks. All metrics are automatically collected during interactive sessions without any additional configuration.

### Action Logging Hooks

**Location**: `.claude/hooks/log_agent_actions.py`

**What It Does**:
- Parses JSONL transcript files from Claude Agent SDK
- Extracts all tool calls with timestamps, inputs, and IDs
- Logs to `logs/actions/{timestamp}_{session_id}.log`
- Deduplicates actions (only logs new tool calls)
- Runs automatically on session Stop events

**Hook Configuration** (`.claude/settings.json`):
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/log_agent_actions.py",
            "description": "Log all agent tool calls"
          }
        ]
      }
    ]
  }
}
```

**Action Log Format**:
```
================================================================================
Agent Actions Log - Session: main_2025-10-26T15:30:45.123456
================================================================================

Action:
  Timestamp: 2025-10-26T15:31:12.456789
  Tool: Read
  Tool ID: toolu_01ABC123
  Input: {
      "file_path": "/workspace/example.py"
  }

Action:
  Timestamp: 2025-10-26T15:31:15.789012
  Tool: Write
  Tool ID: toolu_02DEF456
  Input: {
      "file_path": "/workspace/output.txt",
      "content": "Hello World"
  }
```

### Interactive Session Metrics

**Real-time Metrics Collected**:

1. **User Prompts** - Counted when user submits input
2. **Agent Responses** - Counted for each AssistantMessage
3. **Tool Calls** - Tracked by tool name and success/failure status
4. **Message Types** - Distribution of text, tool_use, thinking blocks
5. **Cache Performance** - Read/creation tokens and hit ratio
6. **Session Duration** - Total time from start to exit

**Metrics Integration in Code**:
```python
# In interactive.py, metrics are recorded automatically:

# User input recorded
session.metrics.record_user_prompt(agent_name, session.session_id)

# Agent response recorded
session.metrics.record_agent_response(agent_name, session.session_id)

# Tool calls tracked
session.metrics.record_tool_call(agent_name, tool_name, "success")

# Message types logged
session.metrics.record_message_type(agent_name, "tool_use")

# Cache metrics updated
session.metrics.update_cache_metrics(agent_name, model, cache_read, cache_creation, total_input)
```

### Grafana Dashboard: Interactive Sessions

**Access**: http://localhost:3000 → Dashboards → Interactive Sessions

**10 Real-time Panels**:

1. **Active Interactive Sessions** (Stat)
   - Shows current number of active sessions
   - Updates every 5 seconds

2. **Total User Prompts** (Stat)
   - Cumulative count of user inputs
   - Per session breakdown

3. **Average Response Time** (Stat)
   - Mean agent response latency
   - Calculated from last 5 minutes

4. **Cache Hit Ratio** (Gauge)
   - Visual gauge from 0-100%
   - Green (>60%), Orange (30-60%), Red (<30%)

5. **Session Cost Over Time** (Graph)
   - Cost per hour trend
   - Per-model breakdown

6. **Token Usage Breakdown** (Graph)
   - Input, output, and cached tokens
   - Tokens per minute rate

7. **Tool Usage Heat Map** (Bar Gauge)
   - Most frequently used tools
   - Horizontal bars with gradient coloring

8. **Message Type Distribution** (Pie Chart)
   - Percentage of text vs tool_use vs thinking
   - Donut chart with legend

9. **Session Duration Distribution** (Heatmap)
   - Duration buckets: 10s, 30s, 1m, 2m, 5m, 10m, 30m, 1h, 2h
   - Color intensity shows frequency

10. **Cache Performance Over Time** (Graph)
    - Cache read and creation tokens per minute
    - Stacked area chart

### Prometheus Queries

**Useful Queries for Ad-hoc Analysis**:

```promql
# Total prompts in last hour
sum(increase(interactive_session_prompts_total[1h]))

# Average cache hit ratio
avg(interactive_cache_hit_ratio)

# Most used tools
topk(5, sum by (tool_name) (interactive_tool_calls_total))

# Cost per session
sum(api_cost_dollars_total) / count(interactive_session_prompts_total)

# Response time p95
histogram_quantile(0.95, sum(rate(agent_duration_seconds_bucket[5m])) by (le))

# Tool failure rate
sum(interactive_tool_calls_total{status="error"}) / sum(interactive_tool_calls_total) * 100
```

### Viewing Metrics in Real-time

**During an Interactive Session**:

1. Start interactive mode in one terminal:
   ```bash
   make interactive
   ```

2. Open Grafana in browser:
   ```bash
   make metrics
   # Opens http://localhost:3000
   ```

3. Navigate to "Interactive Sessions" dashboard

4. Watch metrics update in real-time as you chat:
   - Type prompts → see prompt counter increment
   - Agent uses tools → see tool heat map update
   - Session runs → see cost graph climb
   - Cache used → see cache hit ratio adjust

### Structured Logging

**All metrics are also logged via structlog**:
```json
{
  "event": "Message displayed",
  "message_type": "tool_use",
  "message_length": 324,
  "timestamp": "2025-10-26T15:31:12.456789Z",
  "level": "info"
}

{
  "event": "Token usage recorded",
  "agent": "main",
  "model": "claude-sonnet-4-5-20250929",
  "input_tokens": 1234,
  "output_tokens": 567,
  "cached_tokens": 890,
  "cost_dollars": 0.0234,
  "timestamp": "2025-10-26T15:31:15.789012Z",
  "level": "debug"
}
```

**View structured logs**:
```bash
# JSON format with jq filtering
make logs-json | jq 'select(.event == "Token usage recorded")'

# View all interactive session events
make logs-json | jq 'select(.session_id != null)'
```

### Action Log Directory

**Location**: `logs/actions/`

**Files Created**:
- `{timestamp}_{session_id}.log` - One per session
- Append mode - new actions added to existing file
- Deduplication - tool IDs prevent duplicate logging

**Example**:
```
logs/actions/
├── 20251026_153045_main_2025-10-26T15:30:45.123456.log
├── 20251026_161230_main_2025-10-26T16:12:30.789012.log
└── 20251026_174512_main_2025-10-26T17:45:12.345678.log
```

### Cost Tracking

**Real-time Cost Calculation**:
- Based on Sonnet 4.5 pricing (as of Oct 2025)
  - Input: $0.003 per 1K tokens
  - Output: $0.015 per 1K tokens
  - Cached: $0.0003 per 1K tokens

**Cost Metrics**:
```python
# Automatic cost recording in agent.py
cost = (
    (input_tokens / 1000.0) * 0.003
    + (output_tokens / 1000.0) * 0.015
    + (cached_tokens / 1000.0) * 0.0003
)
MetricsCollector.record_api_cost(model, cost)
```

**View Costs in Grafana**:
- "Session Cost Over Time" panel shows $/hour
- "Token Usage Breakdown" shows which token type dominates
- Set budget alerts in Prometheus (see alerting.yml)

### Troubleshooting Observability

**Issue**: Metrics not appearing in Grafana
```bash
# Check Prometheus is scraping
curl http://localhost:9090/api/v1/targets

# Verify metrics endpoint
docker compose exec main-agent curl http://localhost:9090/metrics | grep interactive_session
```

**Issue**: Dashboard not loading
```bash
# Check Grafana logs
make logs | grep grafana

# Restart Grafana
docker compose restart grafana
```

**Issue**: Action logs not being created
```bash
# Verify hooks directory exists
ls -la .claude/hooks/

# Check hook script is executable
ls -l .claude/hooks/log_agent_actions.py

# Test hook manually
echo '{"transcript_path": "/path/to/transcript.jsonl", "session_id": "test"}' | python .claude/hooks/log_agent_actions.py
```

**Issue**: Cache hit ratio shows 0
```bash
# Cache metrics only update when cache is used
# Run a few prompts in the same session to build cache
# Check Prometheus query:
curl -s 'http://localhost:9090/api/v1/query?query=interactive_cache_hit_ratio' | jq .
```

## Phase 2: Configuration & Extensibility Roadmap

### Overview

Phase 2 transforms the harness from an interactive CLI into a full framework with configuration management, extensible agent/tool libraries, and enhanced observability. The goal is to make the harness reusable across different agent runs without rebuilding infrastructure.

### 2.1 Configuration Builder System

**Goal**: Support YAML/JSON configuration profiles for agents

**Files to Create**:
- `src/harness/config_builder.py` - Profile loader with validation
- `config/profiles/default.yaml` - Base configuration
- `config/profiles/research.yaml` - Research agent profile
- `config/profiles/coding.yaml` - Coding agent profile
- `config/profiles/analysis.yaml` - Data analysis profile

**Features**:
- Configuration inheritance (profiles extend base configs)
- Pydantic schema validation
- Environment variable overrides
- Hot-reload without container restart

**Example Profile** (`config/profiles/research.yaml`):
```yaml
name: "Research Agent"
base: "default"

agent:
  model: "sonnet"
  permission_mode: "acceptEdits"
  max_turns: 500

tools:
  allowed:
    - Read
    - Write
    - WebSearch
    - WebFetch
  restricted:
    - Bash

mcp_servers:
  playwright:
    enabled: false
  memory:
    enabled: true

monitoring:
  checkpoint_interval: 3600
  log_level: "INFO"
```

**Usage**:
```bash
make interactive PROFILE=research
# or
make chat PROFILE=coding
```

### 2.2 Agent & Tool Library

**Agent Library** (`config/agents/library/`):
- Port agent definitions from `claude-agent-sdk-intro/.claude/agents/`
- Front-matter YAML parsing (name, description, tools, model)
- Auto-discovery via glob patterns
- Versioning for backwards compatibility

**Tool Library** (`src/harness/tools/`):
- Registry pattern with auto-discovery
- Each tool as Python module with `@tool` decorator
- Grouped by category (filesystem, web, data, etc.)
- Automatic MCP server generation

**Structure**:
```
src/harness/tools/
├── registry.py          # Auto-discovery engine
├── filesystem/
│   ├── advanced_search.py
│   └── file_watcher.py
├── web/
│   ├── scraper.py
│   └── api_client.py
└── data/
    ├── csv_processor.py
    └── json_validator.py
```

**Usage**:
```python
# Tools auto-register on import
from harness.tools import registry

# Get all available tools
tools = registry.get_all_tools()

# Load specific category
web_tools = registry.get_tools_by_category("web")
```

### 2.3 Enhanced Observability

**Port from `claude-agent-sdk-intro`**:
- `.claude/hooks/log_agent_actions.py` - JSONL transcript parsing
- Session hooks (Stop, Notification) with sound/logging
- Real-time action logging (not just on stop)

**New Features**:
- Structured logging with correlation IDs across all messages
- Export to observability platforms (Datadog, Honeycomb)
- Cost analytics dashboard in Grafana
- Session replay functionality

**Hook Configuration** (`.claude/settings.json`):
```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "uv run src/harness/hooks/log_actions.py"
      },
      {
        "type": "command",
        "command": "uv run src/harness/hooks/export_metrics.py"
      }
    ],
    "Notification": [
      {
        "type": "command",
        "command": "afplay /System/Library/Sounds/Purr.aiff"
      }
    ]
  }
}
```

### 2.4 Workflow Templates

**Location**: `examples/workflows/`

**Templates**:
1. **simple-feature/** - Single file feature implementation
2. **bug-fix/** - Debug, fix, test workflow
3. **refactoring/** - Code improvement workflow
4. **research-and-implement/** - Multi-agent (researcher → coder)
5. **full-project/** - Complete project from spec

**Each Template Includes**:
- `workflow.yaml` - Workflow definition and steps
- `agent_config.yaml` - Agent configuration
- `README.md` - Usage instructions and examples
- Example inputs/outputs

**Example** (`examples/workflows/simple-feature/workflow.yaml`):
```yaml
name: "Simple Feature Implementation"
description: "Implement a single-file feature with tests"

steps:
  - name: "Analyze requirements"
    agent: "main"
    tools: ["Read", "Grep", "Glob"]

  - name: "Implement feature"
    agent: "main"
    tools: ["Read", "Write", "Edit"]

  - name: "Write tests"
    agent: "tester"
    tools: ["Read", "Write", "Bash"]

  - name: "Review code"
    agent: "reviewer"
    tools: ["Read", "Grep"]

outputs:
  - "Feature implementation"
  - "Unit tests"
  - "Code review report"
```

### 2.5 Session Management Improvements

**Features**:
- Save/load conversation history as markdown
- Export conversations for sharing
- Conversation branching (try different approaches)
- Session analytics dashboard (time, cost, tasks completed)
- Compare sessions side-by-side

**CLI Commands**:
```bash
# Save session
make save-session NAME=feature-implementation

# Load session
make load-session NAME=feature-implementation

# Export to markdown
make export-session NAME=feature-implementation

# List all sessions
make list-sessions

# Session analytics
make session-stats NAME=feature-implementation
```

### 2.6 Multi-Agent Orchestration UI

**Advanced CLI Features**:
- View all active agents in real-time
- Switch between agent conversations
- Broadcast messages to multiple agents
- Monitor agent coordination and task delegation
- Visual workflow progress

**Example**:
```bash
make orchestrate

# Interactive menu:
# 1. View all agents
# 2. Chat with main agent
# 3. Chat with reviewer
# 4. Broadcast to all
# 5. View workflow status
# 6. Exit
```

### Implementation Timeline

**Week 1**: Configuration builder + YAML profiles
**Week 2**: Agent/tool library with auto-discovery
**Week 3**: Enhanced observability + hooks
**Week 4**: Workflow templates + session management

### Success Criteria

**Phase 2 Complete When**:
- ✅ Can load custom agent profiles via CLI
- ✅ Can add new tools without modifying core code
- ✅ Observability hooks capture all actions
- ✅ At least 3 workflow templates documented
- ✅ Configuration schema fully documented
- ✅ Agent library has 10+ pre-built agents
- ✅ Session save/load working
- ✅ Multi-agent orchestration UI functional

## Contributing

Follow coding standards from ABDotfiles:
- **General**: `.claude/specs/general_code_standards.md`
- **Python**: `.claude/specs/python.md`
- **Make/Docker**: `.claude/specs/make.md`

Key requirements:
- 80%+ test coverage
- Type hints on all functions
- Ruff for linting and formatting
- Conventional commit messages

## Resources

- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [TypeScript SDK](https://github.com/anthropics/claude-agent-sdk-typescript)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

**Maintainer**: Andis A. Blukis (andis.blukis@gmail.com)
**License**: MIT
**Version**: 0.1.0 (Alpha)
