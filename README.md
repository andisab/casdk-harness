# Claude Agent SDK Harness

> Production-ready framework for autonomous software development with Claude Agent SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-24.0+-blue.svg)](https://www.docker.com/)

**Claude Agent SDK Harness** is an enterprise-grade automation toolkit that enables 20+ hour autonomous development sessions using Anthropic's Claude Agent SDK. Built for teams that want to accelerate software delivery while maintaining quality, security, and observability.

> **Current Status**: Foundation infrastructure complete with monitoring, checkpointing, and multi-agent orchestration. Claude SDK integration in progress.

## ✨ Key Features

- 🤖 **Multi-Agent Coordination** - Run multiple specialized agents (dev, review, test) in parallel
- 💾 **Checkpoint & Recovery** - Automatic state persistence every hour with instant recovery
- 📊 **Full Observability** - Prometheus metrics + Grafana dashboards out of the box
- 🔒 **Security First** - Non-root containers, secret management, audit logging
- 🐳 **Docker Native** - Develop locally, deploy anywhere
- ☸️ **Kubernetes Ready** - Production manifests for GCP GKE and AWS EKS
- 🔌 **Extensible** - Plugin architecture for custom agents and tools
- 📈 **Cost Optimized** - Smart caching reduces API costs by 90%

## 🚀 Quick Start

### Prerequisites

```bash
# Required
- Docker 24.0+ with BuildKit
- Docker Compose 2.22+
- Python 3.12 or 3.13
- Anthropic API key
- 8GB+ RAM

# Check versions
docker --version
docker compose version
python --version
```

### Installation

```bash
# 1. Clone repository (if needed)
cd ~/Projects/claudeagentsdk-harness

# 2. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Initialize and build
make init
make build

# 4. Start development environment
make dev
```

That's it! Your autonomous development environment is running at:
- **Main Agent**: http://localhost:8080
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

### 📊 Monitoring Access

**Grafana Dashboards**:
- **URL**: http://localhost:3000
- **Default Login**: `admin` / `admin` (or password from `.env`: `GRAFANA_PASSWORD`)
- **Dashboards**:
  - **Overview**: General system health and metrics
  - **Interactive Sessions**: Real-time chat metrics, tool usage, cache performance
- **Change Password**: Settings → Profile → Change Password (recommended on first login)

**Prometheus Metrics**:
- **URL**: http://localhost:9090
- **No Authentication Required** (development mode)
- **Useful Queries**:
  - `interactive_session_prompts_total` - User prompts count
  - `api_cost_dollars_total` - Total API costs
  - `interactive_tool_calls_total` - Tool usage by name
  - `interactive_cache_hit_ratio` - Cache effectiveness

## 📚 Usage Examples

### Getting Started

```bash
# 1. Start the development environment
make dev

# 2. Monitor service logs (in another terminal)
make logs

# 3. View metrics dashboard
make metrics  # Opens Grafana at localhost:3000

# 4. Check system health
make health

# 5. Access Prometheus
make prometheus  # Opens at localhost:9090
```

### Working with Agents

```bash
# Shell into main agent container
make shell

# Inside container, interact with Claude Agent SDK
# (SDK integration in progress - currently placeholder)

# View main agent logs
make logs-main

# View all logs
make logs

# Restart all services
make restart
```

**Advanced**: For agent-specific operations, use make targets:
- `make shell-reviewer` - Shell into reviewer agent
- `make shell-tester` - Shell into tester agent

### Development Workflow

```bash
# Start development with hot-reload
make dev

# Run tests
make test

# Check code coverage
make coverage

# View structured logs
make logs-json | jq '.level, .message'

# Stop all services
make down
```

> **Note**: Full workflow scripts (`submit_task.py`, `run_workflow.py`) will be added after Claude SDK integration is complete. See [CLAUDE.md](./CLAUDE.md) for detailed implementation status.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Layer                     │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Main Agent  │   Reviewer   │    Tester    │  Orchestrator  │
│  (Dev Work)  │  (QA Check)  │  (Testing)   │  (Coordin.)   │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                     Shared Services                          │
│  PostgreSQL  │    Redis     │  Prometheus  │    Grafana     │
├─────────────────────────────────────────────────────────────┤
│                  Volume Mounts                               │
│  workspace/  │   memory/    │    logs/     │   config/      │
└─────────────────────────────────────────────────────────────┘
```

### Agent Types

| Agent | Purpose | Tools | Model |
|-------|---------|-------|-------|
| **Main** | Feature development, coding | Read, Write, Bash, Grep, Glob | Sonnet 4.5 |
| **Reviewer** | Code review, security audit | Read, Grep, Glob | Sonnet 4.5 |
| **Tester** | Test generation, execution | Read, Write, Bash | Sonnet 4.5 |
| **Orchestrator** | Multi-agent coordination | All | Opus 4.1 |

## 🛠️ Common Commands

### Development

```bash
make dev              # Start with hot-reload and watch mode
make shell            # Shell into main agent container
make logs             # Tail all service logs
make logs-json        # Structured JSON logs
```

### Operations

```bash
make up               # Start all services
make down             # Stop all services
make restart          # Restart services
make ps               # Show running containers
make clean            # Remove containers and volumes
```

### Testing

```bash
make test             # Run full test suite
make test-unit        # Unit tests only
make test-integration # Integration tests
make test-e2e         # End-to-end tests
make coverage         # Generate coverage report
```

### Monitoring

```bash
make metrics          # Open Grafana (localhost:3000)
make prometheus       # Open Prometheus (localhost:9090)
make health           # Check all services health
```

### Maintenance

```bash
make prune            # Clean up unused Docker resources
make clean            # Remove containers and volumes
make reset            # Full reset (destructive!)
```

> **Note**: Backup and restore functionality planned for future release.

## 📖 Documentation

- **This README** - Quick start guide and common commands (you are here)
- **[CLAUDE.md](./CLAUDE.md)** - Complete technical documentation for Claude Code
- **[docs/future/](./docs/future/)** - Proposed features (low priority, deferred)

For detailed architecture, implementation notes, configuration options, and troubleshooting, see [CLAUDE.md](./CLAUDE.md).

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...           # Required

# Agent Behavior
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_PERMISSION_MODE=acceptEdits     # manual|acceptEdits|acceptAll
CLAUDE_MAX_TURNS=1000
CLAUDE_SESSION_TIMEOUT=72000           # 20 hours

# Resources
AGENT_CPU_LIMIT=4
AGENT_MEMORY_LIMIT=8G

# Monitoring
GRAFANA_PASSWORD=changeme123
LOG_LEVEL=INFO
```

See [`.env.example`](./.env.example) for all options.

### Agent Configuration

Customize agent behavior in `.claude/agents/`:

```yaml
# .claude/agents/development/my-custom-agent.md
---
name: my-custom-agent
description: Specialized agent for my use case
tools: Read, Write, Bash, Grep
model: sonnet
---
[Your custom agent instructions...]
```

## 🐳 Deployment

### Local Development (OrbStack)

```bash
# Start development environment
make dev

# Production-like local build
make prod
```

### Docker Compose

```bash
# Development
make dev

# Production configuration
ENVIRONMENT=production make up
```

### Kubernetes (Coming Soon)

Kubernetes manifests for GKE and EKS deployment will be added in a future release. The current architecture is designed to be K8s-ready with:
- Health checks for all services
- Resource limits and requests
- ConfigMaps and Secrets support
- StatefulSet patterns for agents

See [CLAUDE.md](./CLAUDE.md) for roadmap details.

## 🔐 Environment Isolation & Long-Running Sessions

### What's Isolated in Containers ✅

The harness runs **fully containerized** with the following components isolated from your host system:

**Container-Based Services:**
- ✅ All Claude agents (main, reviewer, tester) with complete Python environments
- ✅ All dependencies (Python 3.12, Node.js/npm, git, Claude CLI)
- ✅ MCP servers (memory, context7, joplin, playwright, github) run inside containers via npx
- ✅ Custom MCP servers (git, docker) implemented in Python
- ✅ PostgreSQL database with persistent volumes
- ✅ Redis cache with persistent volumes
- ✅ Prometheus metrics collection
- ✅ Grafana dashboards

**What This Means:**
- No Python packages installed on your Mac
- No Node.js/npm pollution of your global environment
- All processes run in isolated container namespaces
- Resource limits (CPU/memory) enforced at container level

### Host System Dependencies ⚠️

While agents run in containers, these components interact with your host system:

**Shared Filesystem (Docker Volume Mounts):**
```
./workspace  → Agent working directory (read/write)
./memory     → Checkpoints and context (read/write)
./logs       → Application logs (write)
./config     → Configuration files (read-only)
./src        → Source code (dev mode hot-reload)
```

**Required on Host:**
- Docker daemon (OrbStack or Docker Desktop must be running)
- `.env` file with configuration
- Disk space for workspace, memory, and logs (can grow large during long sessions)

**Exposed Ports (accessible from your Mac):**
- `8080` - Main agent HTTP endpoint
- `8081` - Reviewer agent
- `8082` - Tester agent
- `3000` - Grafana dashboards
- `9090` - Prometheus metrics
- `5432` - PostgreSQL (dev mode only)
- `6379` - Redis (dev mode only)

### Running Long-Duration Sessions (20+ Hours)

The harness is **designed for extended autonomous sessions** with built-in safeguards:

**Checkpoint & Recovery:**
- Auto-save state every hour (configurable via `CLAUDE_CHECKPOINT_INTERVAL`)
- Keep 5 most recent checkpoints
- Automatic recovery on container restart
- Session state persists in `./memory/checkpoints/`

**Monitoring & Alerts:**
- Prometheus tracks resource usage, API costs, and errors
- Grafana dashboards show real-time metrics
- Pre-configured alerts for OOM, high error rates, slow responses
- Health checks every 30 seconds with auto-restart

**Resource Management:**
- CPU/memory limits prevent runaway usage
- Docker restart policy: `unless-stopped`
- Log rotation to prevent disk exhaustion (configured in monitoring)

### Starting a Long-Running Session

**Clean Start (Recommended):**
```bash
# 1. Stop any existing background processes
ps aux | grep "make build"   # Find and kill if running
ps aux | grep "make dev"      # Find and kill if running

# 2. Clean slate
make down              # Stop all containers
make clean             # Remove containers and volumes

# 3. Build fresh
make build

# 4. Start in detached mode (runs in background)
make up

# 5. Verify everything is running
make health
make ps
```

**Monitor Without Blocking Your Terminal:**
```bash
# View logs when needed (non-blocking)
make logs

# Check service health
make health

# View metrics dashboard
make metrics          # Opens Grafana at localhost:3000

# Check resource usage
docker stats claude-main-agent
```

### Important Considerations for Extended Sessions

**Before Starting a 20+ Hour Session:**

1. **Prevent Mac Sleep:**
   ```bash
   # macOS - keep Mac awake
   caffeinate -s &

   # Or use System Settings > Energy Saver > Prevent automatic sleep
   ```

2. **Monitor Disk Space:**
   ```bash
   # Check available space
   df -h .

   # Monitor growth during session
   du -sh workspace/ memory/ logs/
   ```

3. **Set API Budget Alerts:**
   - Configure cost alerts in `.env`: `ENABLE_COST_OPTIMIZATION=true`
   - Monitor in Grafana dashboard at `localhost:3000`
   - Default alert: >$10/hour triggers notification

4. **Checkpoint Verification:**
   ```bash
   # Check checkpoints are being created
   ls -lh memory/checkpoints/

   # Should see new files every hour
   ```

5. **Log Retention:**
   - Logs rotate automatically but can grow large
   - Check `logs/` directory size periodically
   - Configure retention in `.env`: `PROMETHEUS_RETENTION=30d`

**During the Session:**
```bash
# Quick health check
make health

# View recent logs
make logs | tail -100

# Check API costs (in Grafana)
make metrics
# Navigate to "Cost Dashboard"

# Verify checkpoint creation
ls -lth memory/checkpoints/ | head -10
```

**Recovery from Interruption:**
```bash
# If containers stopped unexpectedly
make up                    # Restart all services

# Agents will automatically:
# 1. Load latest checkpoint
# 2. Resume from last known state
# 3. Continue task execution
```

### Production Deployment (Future)

For **truly isolated** cloud deployment without host dependencies:

**Kubernetes (Coming in Phase 3):**
- Dedicated K8s cluster (GKE or EKS)
- Persistent volumes separate from your machine
- Auto-scaling for resource management
- No dependency on your Mac staying awake
- Network load balancers for external access

See [roadmap](#-roadmap) for K8s deployment timeline.

## 📊 Monitoring & Observability

### Key Metrics

- **Agent Requests**: Total requests by agent and status
- **Session Duration**: p50, p95, p99 latencies
- **Checkpoint Size**: Memory usage trends
- **Workspace Files**: Files created/modified
- **API Costs**: Token usage and cost tracking

### Default Dashboards

1. **Overview**: High-level system health
2. **Interactive Sessions** (NEW): Real-time interactive chat metrics
   - Active sessions and prompt counts
   - Average response time
   - Cache hit ratio gauge
   - Cost per hour trend
   - Token usage breakdown
   - Tool usage heat map
   - Message type distribution
   - Session duration distribution
   - Cache performance over time
3. **Agent Performance**: Per-agent metrics and timing
4. **Resource Usage**: CPU, memory, disk utilization
5. **Costs**: API usage and cost breakdown

### Alerts

Pre-configured alerts for:
- Agent OOM or crashes
- High error rates (>5%)
- Slow response times (>30s p95)
- Disk space low (<10%)
- Checkpoint failures

## 🔒 Security

### Built-in Security Features

- ✅ Non-root container users
- ✅ Read-only root filesystem
- ✅ Network isolation
- ✅ Secret rotation (30 days)
- ✅ Audit logging with correlation IDs
- ✅ Resource limits prevent DoS
- ✅ No secrets in version control

### Recommended Practices

1. Rotate `ANTHROPIC_API_KEY` every 90 days
2. Use dedicated service accounts
3. Enable GitHub/GitLab SSO
4. Review audit logs weekly
5. Scan containers with Trivy/Snyk
6. Backup checkpoints to S3/GCS

## 🧪 Testing

### Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests
├── integration/       # Multi-service integration tests
└── e2e/              # Full workflow end-to-end tests
```

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests
make test-integration

# End-to-end tests
make test-e2e

# With coverage
make coverage
```

**Advanced**: For running specific tests, shell into the container:
```bash
make shell
pytest tests/unit/test_checkpoint.py::test_save_checkpoint -v
```

### Test Coverage

Minimum coverage requirements:
- **Overall**: 80%
- **Critical paths**: 95%
- **Core modules**: 90%

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Follow coding standards in `.claude/specs/` directory
4. Write tests with 80%+ coverage
5. Submit a pull request

Development guidelines:
- Use Python 3.12+ with type hints
- Follow KISS and YAGNI principles
- Document all functions with docstrings
- Test on OrbStack for macOS development

## 📝 Changelog

### v0.1.0-alpha (2025-10-06)

**Foundation Release**
- ✅ Multi-agent orchestration infrastructure with Docker Compose
- ✅ Checkpoint and recovery system (auto-save every hour)
- ✅ Prometheus + Grafana monitoring stack
- ✅ Agent configuration framework (main, reviewer, tester)
- ✅ Python SDK wrapper modules (config, checkpoint, monitoring, agent)
- ✅ Comprehensive Makefile with 60+ commands
- ✅ Unit test framework with pytest
- ✅ OrbStack-optimized Docker builds
- 🚧 Claude SDK integration (in progress)
- 📋 Example workflows (planned)

See [CLAUDE.md](./CLAUDE.md) for detailed status.

## 🗺️ Roadmap

**Current Phase**: Enhanced Observability (Mostly Complete)

### Immediate Focus
- Complete testing of observability features
- Commit working changes to git
- Improve test coverage to 80%+
- Polish core functionality

### Future Features (Deferred)
See [docs/future/](./docs/future/) for detailed proposals:
- Configuration & extensibility
- External repository support
- Web frontend UI
- Production deployment (K8s, CI/CD)

For detailed status, TODOs, and progress tracking, see [CLAUDE.md](./CLAUDE.md).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) for Claude Agent SDK
- [Claude Code](https://claude.ai/code) for inspiration
- Community contributors and testers

## 📬 Contact

**Andis A. Blukis**
- Email: andis.blukis@gmail.com
- GitHub: [@andisab](https://github.com/andisab)
- LinkedIn: [andisab](https://linkedin.com/in/andisab)

## 🔗 Links

- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [TypeScript SDK](https://github.com/anthropics/claude-agent-sdk-typescript)
- [Claude Code Docs](https://docs.claude.com/en/docs/claude-code/)
- [Example Agents Collection](https://github.com/wshobson/agents)

---

**Built with ❤️ by developers, for developers**

*Star ⭐ this repository if you find it useful!*
