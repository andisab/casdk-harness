>[toc]

# Claude Agent SDK Harness - Technical Documentation

**Last updated**: October 6, 2025

## Project Status Summary

### Current Phase: SDK Integration Complete ✅
**Completed**: Early October, 2025

- [x] Architecture design
- [x] Core infrastructure implementation
- [x] Docker orchestration (dev + prod)
- [x] **Real Claude Agent SDK integration** (agent.py)
- [x] Monitoring and observability (Prometheus + Grafana)
- [x] **Token usage tracking with cost calculation** (monitoring.py)
- [x] **MCP server implementations** (filesystem, git, docker)
- [x] **Integration test suite with VCR.py** (12 tests)
- [x] **E2E test suite** (3 workflow tests)

### Next Milestones

#### Immediate (Required for First Real Use)
1. ⚠️ Run `make test-integration` with API key to record VCR cassettes
2. ⚠️ Verify MCP servers work by running filesystem/git tests
3. ⚠️ Run at least one E2E test to validate full workflow

#### Short-term (Nice to Have)
1. Add more MCP server tools (file read/write, git commit, etc.)
2. Improve test coverage to 80%+ (write tests for new agent.py code)
3. Add smoke tests for quick validation
4. Create example workflow scripts
5. Add utility scripts (setup.sh, backup.sh, restore.sh)

#### Long-term (Future Enhancements)
1. Add Jaeger distributed tracing
2. Create K8s deployment manifests
3. Build CI/CD pipeline
4. Create workflow template library
5. Add multi-cluster deployment support

### Known Limitations

1. **Agent SDK Dependency**: Requires `claude-agent-sdk>=0.1.0` to be available
2. **Docker Dependency**: Docker MCP server requires Docker daemon running
3. **Git Dependency**: Git MCP server requires git binary installed
4. **Test Coverage**: Currently 57.68% (target: 80%+) - needs more integration test runs
5. **E2E Tests**: Not yet run with real API (need API key and cassette recording)
6. **Example Workflows**: Placeholder directories exist but examples not yet created

### To Do
- [ ] Record VCR cassettes for integration tests
- [ ] Verify all MCP servers function correctly
- [ ] Improve test coverage to 80%+
- [ ] Create example workflow scripts
- [ ] Add distributed tracing with Jaeger
- [ ] Create CI/CD pipeline templates
- [ ] Build K8s deployment manifests

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
│   │   ├── config.py           # Pydantic config management
│   │   ├── monitoring.py       # Prometheus metrics collector
│   │   └── py.typed            # PEP 561 type marker
│   ├── mcp/                    # Custom MCP servers (placeholders)
│   │   ├── __init__.py
│   │   ├── filesystem/
│   │   ├── git/
│   │   └── docker/
│   └── utils/
│       └── __init__.py
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
```

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

All agents export metrics on port 9090:

- `agent_requests_total{agent, status}` - Request counts
- `agent_duration_seconds{agent}` - Execution duration histogram
- `agent_active_sessions{agent}` - Active session count
- `checkpoint_size_bytes` - Total checkpoint storage
- `workspace_files_total` - Files in workspace
- `memory_usage_bytes{component}` - Memory usage
- `api_tokens_used_total{model, type}` - Token consumption
- `api_cost_dollars_total{model}` - API costs

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
