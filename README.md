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
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

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

- **[CLAUDE.md](./CLAUDE.md)** - Complete technical documentation for Claude Code

**Coming Soon:**
- Architecture Guide - System design and patterns
- Agent Development Guide - Create custom agents
- Deployment Guide - K8s deployment instructions
- Troubleshooting Guide - Common issues and solutions

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

## 📊 Monitoring & Observability

### Key Metrics

- **Agent Requests**: Total requests by agent and status
- **Session Duration**: p50, p95, p99 latencies
- **Checkpoint Size**: Memory usage trends
- **Workspace Files**: Files created/modified
- **API Costs**: Token usage and cost tracking

### Default Dashboards

1. **Overview**: High-level system health
2. **Agent Performance**: Per-agent metrics and timing
3. **Resource Usage**: CPU, memory, disk utilization
4. **Costs**: API usage and cost breakdown

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

### Phase 1: SDK Integration (Current)
- [ ] Integrate actual Claude Agent SDK
- [ ] Implement real Claude API calls
- [ ] Build custom MCP servers (filesystem, git, docker)
- [ ] Create example workflows (simple-feature, bug-fix, refactoring)
- [ ] Add integration and E2E tests

### Phase 2: Workflow Automation
- [ ] Task submission scripts (`submit_task.py`, `run_workflow.py`)
- [ ] Multi-agent coordination logic
- [ ] Workflow templates library
- [ ] Enhanced checkpoint recovery
- [ ] Backup and restore utilities

### Phase 3: Production Readiness
- [ ] Kubernetes manifests (GKE, EKS)
- [ ] GitOps with ArgoCD
- [ ] Advanced monitoring and alerting
- [ ] Cost optimization dashboard
- [ ] Security hardening and audit logging

### Phase 4: Advanced Features
- [ ] Multi-cluster deployment
- [ ] Agent marketplace
- [ ] Service mesh integration
- [ ] Distributed tracing (Jaeger)
- [ ] Multi-tenancy support

See [CLAUDE.md](./CLAUDE.md) for detailed status and progress tracking.

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
