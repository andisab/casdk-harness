# Claude Agent SDK Harness

> Production-ready framework for autonomous software development with Claude Agent SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-24.0+-blue.svg)](https://www.docker.com/)

**Claude Agent SDK Harness** is an enterprise-grade automation toolkit that enables 20+ hour autonomous development sessions using Anthropic's Claude Agent SDK. Built for teams that want to accelerate software delivery while maintaining quality, security, and observability.

## Key Features

- 🤖 **Multi-Agent Coordination** - Run multiple specialized agents (dev, review, test) in parallel
- 💾 **Checkpoint & Recovery** - Automatic state persistence every hour with instant recovery
- 📊 **Full Observability** - Prometheus metrics + Grafana dashboards out of the box
- 🔒 **Security First** - Non-root containers, secret management, audit logging
- 🐳 **Docker Native** - Develop locally, deploy anywhere
- ☸️ **Kubernetes Ready** - Production manifests for GCP GKE and AWS EKS
- 🔌 **Extensible** - Plugin architecture for custom agents and tools
- 📈 **Cost Optimized** - Smart caching reduces API costs by 90%

## Prerequisites

**Required:**
- Docker 24.0+ with BuildKit
- Docker Compose 2.22+
- Python 3.12 or 3.13
- Anthropic API key
- 8GB+ RAM
- 50GB+ disk space

**Verify versions:**
```bash
docker --version
docker compose version
python --version
```

**Recommended:**
- OrbStack (macOS) - 2x faster than Docker Desktop

## Getting Started

```bash
# 1. Navigate to repository
cd ~/Projects/claudeagentsdk-harness

# 2. Initialize directories and environment
make init

# 3. Edit .env and add your ANTHROPIC_API_KEY
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# 4. (Optional) Edit .env.mcp and add MCP server API keys
#    - Copy .env.mcp.example to see available servers
#    - GitHub: GITHUB_PERSONAL_ACCESS_TOKEN
#    - GitLab: GITLAB_PERSONAL_ACCESS_TOKEN
#    - Joplin: JOPLIN_API_TOKEN

# 5. Build containers
make build

# 6. Start development environment
make dev
```

That's it! Your environment is running at:
- **Main Agent**: http://localhost:8080
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

### Authentication: SSH Keys vs Personal Access Tokens

| Method | Protocol | Use Case |
|--------|----------|----------|
| **SSH Keys** | Git over SSH | `git clone`, `push`, `pull`, `fetch` |
| **Personal Access Tokens** | REST API over HTTPS | Search, issues, PRs, repo metadata |

- **SSH Keys** (`.ssh/`): Authenticate Git CLI operations
- **PATs** (`.env.mcp`): Authenticate MCP server API calls

If you only need Git operations, SSH keys are sufficient. PATs are required for MCP tools like `search_projects`, `list_issues`, etc.

## Quick Start Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start development environment with hot-reload |
| `make down` | Stop all services |
| `make interactive` | Start interactive chat with agent |
| `make logs` | View all service logs |
| `make shell` | Shell into main agent container |
| `make test` | Run test suite (see [CLAUDE.md](./CLAUDE.md) for testing strategy) |
| `make metrics` | Open Grafana dashboard |
| `make health` | Check all services health |
| `make restart` | Restart all services |
| `make clean` | Remove containers and volumes |

> **Always use `make` commands** instead of direct `docker compose` commands. The Makefile handles proper compose file selection and environment settings automatically.

## Interactive Mode

The primary way to interact with agents is through interactive mode, which provides a Rich console UI for chatting with Claude.

### Starting a Session

```bash
# Start with default model (sonnet)
make interactive

# Use different models
make interactive-model MODEL=opus    # Most capable
make interactive-model MODEL=haiku   # Fastest, cheapest

# Quiet mode (clean chat, suppress system logs)
make interactive-quiet
```

### What You'll See

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

### Features

- ✅ Rich formatted messages with colored panels
- ✅ Syntax highlighting for code and JSON
- ✅ Real-time tool use display
- ✅ Session statistics on exit (tokens, cost, duration)
- ✅ Automatic checkpoint recovery if interrupted
- ✅ MCP servers (8 total: git, docker, context7, memory, github, gitlab, playwright, joplin)

### Session Stats

When you exit with "quit" or "exit":

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

### Checkpoint Recovery

If your session is interrupted, the next session automatically recovers:

```bash
make interactive
# Output: ✓ Recovered from previous checkpoint
```

## Working with External Repositories

The harness supports working on external repositories. Clone them to `/workspace/projects/` and work with them directly.

### Directory Structure

```
/app/
└── .claude/              # System configuration (READ-ONLY)
    ├── skills/           # 12 base skills accessible via Skill tool
    ├── plugins/          # 3 plugins (arch, context-engineering, research-team)
    │   ├── arch/         # 2 agents for orchestration
    │   ├── context-engineering/  # 1 agent + 5 skills for resource creation
    │   └── research-team/        # 3 agents + 1 skill for research
    ├── agents/           # 44 agent definitions (reference)
    ├── hooks/            # Action logging hooks
    └── specs/            # Coding standards

/workspace/               # Clean canvas for development
└── projects/             # Clone external repos here
    └── your-repo/        # External repository
        └── .claude/      # Repository's own .claude (optional)
```

**Plugin Resources (Phase 1B)**:
- **Total Skills**: 18 (12 base + 6 from plugins)
- **Plugin Agents**: 6 agents from 3 plugins (auto-discovered by SDK)
- **Plugins Loaded**: arch, context-engineering, research-team

**Note**: Agent cwd is `/app` but ALL file operations must use `/workspace` paths.

### Working with Cloned Repositories

```bash
# Access shell in main agent container
make shell

# Inside container - clone and work on external repo
cd /workspace/projects
git clone https://github.com/user/your-repo.git
cd your-repo

# Run commands directly in the repo directory
# All standard tools (Read, Write, Bash, etc.) work here
```

**Note**: Automatic repository context switching is not yet implemented. See [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) for planned features.

## Complete Command Reference

### Development

| Command | Description |
|---------|-------------|
| `make dev` | Start with hot-reload and watch mode |
| `make shell` | Shell into main agent container |
| `make shell-reviewer` | Shell into reviewer agent |
| `make shell-tester` | Shell into tester agent |
| `make logs` | Tail all service logs |
| `make logs-main` | Main agent logs only |
| `make logs-json` | Structured JSON logs |

### Operations

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make restart` | Restart services |
| `make ps` | Show running containers |
| `make clean` | Remove containers and volumes |
| `make prune` | Clean up unused Docker resources |
| `make reset` | Full reset (destructive!) |

### Testing

| Command | Description |
|---------|-------------|
| `make test` | Run full test suite |
| `make test-unit` | Unit tests only |
| `make test-integration` | Integration tests |
| `make test-e2e` | End-to-end tests |
| `make coverage` | Generate coverage report |

> See [CLAUDE.md](./CLAUDE.md) for complete testing strategy and cost management.

### Monitoring

| Command | Description |
|---------|-------------|
| `make metrics` | Open Grafana (localhost:3000) |
| `make prometheus` | Open Prometheus (localhost:9090) |
| `make health` | Check all services health |

### Maintenance

| Command | Description |
|---------|-------------|
| `make backup` | Backup workspace and checkpoints |
| `make restore` | Restore from latest backup |
| `make db-shell` | PostgreSQL shell |
| `make db-backup` | Backup database |
| `make db-restore` | Restore database |

### Interactive Agent

| Command | Description |
|---------|-------------|
| `make interactive` | Start interactive session (default: sonnet) |
| `make chat` | Alias for interactive mode |
| `make interactive-model MODEL=opus` | Use specific model |
| `make interactive-quiet` | Quiet mode (suppress system logs) |

## Configuration

Configuration is done through `.env` file (copy from `.env.example`):

### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key (required) | `sk-ant-...` |

### Agent Behavior

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_MODEL` | Model to use | `claude-sonnet-4-5-20250929` |
| `CLAUDE_PERMISSION_MODE` | Permission mode | `acceptEdits` |
| `CLAUDE_MAX_TURNS` | Maximum conversation turns | `1000` |
| `CLAUDE_SESSION_TIMEOUT` | Session timeout (seconds) | `72000` (20 hours) |
| `CLAUDE_CHECKPOINT_INTERVAL` | Checkpoint interval (seconds) | `3600` (1 hour) |

**Permission modes:**
- `manual` - Require approval for every action
- `acceptEdits` - Auto-approve file edits, prompt for commands
- `acceptAll` - Auto-approve all actions

### Resource Limits

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_CPU_LIMIT` | CPU cores per agent | `4` |
| `AGENT_MEMORY_LIMIT` | Memory per agent | `8G` |
| `AGENT_CPU_RESERVATION` | Reserved CPU | `2` |
| `AGENT_MEMORY_RESERVATION` | Reserved memory | `4G` |

### Monitoring

| Variable | Description | Default |
|----------|-------------|---------|
| `GRAFANA_PASSWORD` | Grafana admin password | `changeme123` |
| `GRAFANA_PORT` | Grafana port | `3000` |
| `PROMETHEUS_PORT` | Prometheus port | `9090` |
| `PROMETHEUS_RETENTION` | Data retention period | `30d` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format | `json` |

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL host | `postgres` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `claude_harness` |
| `POSTGRES_USER` | Database user | `claude` |
| `POSTGRES_PASSWORD` | Database password | (set in .env) |

### Redis

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis host | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password | (set in .env) |

### SSH Keys (for private repositories)

To clone private repositories from GitHub or GitLab inside containers:

```bash
# 1. Initialize SSH directory
make ssh-init

# 2. Generate dedicated keys
make ssh-keygen-github
make ssh-keygen-gitlab

# 3. Add the public keys to your GitHub/GitLab accounts
#    Output will show the public key to copy

# 4. Test connections
make ssh-test

# 5. Rebuild containers (to pick up the new volume mount)
make build
make dev

# 6. Test from inside container
make ssh-test-container
```

**Security Notes:**
- SSH keys are stored in `.ssh/` (gitignored)
- Keys are mounted read-only into containers
- Dedicated keys are revocable without affecting your host SSH identity

See [`.ssh/README.md`](.ssh/README.md) for alternative setup options.

See [`.env.example`](./.env.example) for complete configuration template.

### Agent Definitions (Reference Only)

The harness includes 44 agent definition files in `.claude/agents/` organized by specialty:

- **Development (dev-\*)**: Python, TypeScript, Node.js, Go, Rust, C++, React, Vue, Next.js, JavaScript, PHP, Perl, Lua, HTML, Kotlin, refactoring (16 total)
- **Database (db-\*)**: PostgreSQL, MongoDB, Neo4j, Cassandra, SQL, Vector DB, MariaDB (7 total)
- **Infrastructure (infra-\*)**: Docker, Kubernetes, Terraform, GCP, AWS, GitHub Actions, GitLab CI, security (8 total)
- **ML/AI (ml-\*)**: PyTorch, TensorFlow, LangChain, scikit-learn (4 total)
- **Build (build-\*)**: Orchestrator, project planner, context (3 total)
- **Documentation (doc-\*)**: Content writer, PRD writer (2 total)
- **Web (web-\*)**: Frontend designer, FastAPI architect, Next.js (3 total)
- **Data (data-\*)**: Python data engineer (1 total)

⚠️ **Note**: These agent definitions are currently reference documentation only. Agent auto-discovery is not yet implemented. See [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) for implementation roadmap.

## Monitoring & Observability

### Accessing Dashboards

**Grafana** (http://localhost:3000):
- **Login**: `admin` / `admin` (or `GRAFANA_PASSWORD` from `.env`)
- **Dashboards**:
  - **Overview**: System health and general metrics
  - **Interactive Sessions**: Real-time chat metrics, tool usage, cache performance
  - **Agent Performance**: Per-agent metrics and timing
  - **Resource Usage**: CPU, memory, disk utilization
  - **Costs**: API usage and cost breakdown

**Prometheus** (http://localhost:9090):
- **No authentication required** (development mode)
- Direct access to all metrics
- Query builder for ad-hoc analysis

### Key Metrics

**Interactive Session Metrics:**
- `interactive_session_prompts_total` - User prompts count
- `interactive_session_responses_total` - Agent responses count
- `interactive_tool_calls_total` - Tool usage by name
- `interactive_cache_hit_ratio` - Cache effectiveness (0-1)
- `interactive_cache_read_tokens_total` - Cache read tokens
- `interactive_cache_creation_tokens_total` - Cache creation tokens

**Agent Metrics:**
- `agent_requests_total{agent, status}` - Request counts by status
- `agent_duration_seconds{agent}` - Execution duration histogram
- `agent_active_sessions{agent}` - Active session count

**Cost Metrics:**
- `api_tokens_used_total{model, type}` - Token consumption
- `api_cost_dollars_total{model}` - API costs in USD

**Resource Metrics:**
- `checkpoint_size_bytes` - Total checkpoint storage
- `workspace_files_total` - Files in workspace
- `memory_usage_bytes{component}` - Memory usage by component

### Useful Prometheus Queries

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
```

### Viewing Logs

```bash
# All logs (live tail)
make logs

# Structured JSON logs with filtering
make logs-json | jq 'select(.event == "Token usage recorded")'

# View interactive session events only
make logs-json | jq 'select(.session_id != null)'

# Specific agent logs
make logs-main
docker compose logs reviewer-agent
```

### Cost Tracking

Real-time cost calculation based on current Anthropic pricing:
- **Input tokens**: $0.003 per 1K tokens
- **Output tokens**: $0.015 per 1K tokens
- **Cached tokens**: $0.0003 per 1K tokens

View costs in Grafana:
1. Open http://localhost:3000
2. Navigate to "Cost Dashboard"
3. Monitor $/hour trends and token usage breakdown

## Architecture

### System Overview

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

### Services & Ports

| Service | Port | Purpose | Access |
|---------|------|---------|--------|
| Main Agent | 8080 | Primary development agent | http://localhost:8080 |
| Reviewer Agent | 8081 | Code review agent | http://localhost:8081 |
| Tester Agent | 8082 | Testing agent | http://localhost:8082 |
| Grafana | 3000 | Monitoring dashboards | http://localhost:3000 |
| Prometheus | 9090 | Metrics collection | http://localhost:9090 |
| PostgreSQL | 5432 | Database (dev mode only) | localhost:5432 |
| Redis | 6379 | Cache (dev mode only) | localhost:6379 |

### Volume Mounts

| Path | Purpose | Persistent |
|------|---------|------------|
| `./workspace` | Agent working directory | Yes (gitignored) |
| `./memory` | Checkpoints and context | Yes (gitignored) |
| `./logs` | Application logs | Yes (gitignored) |
| `./config` | Configuration files | Yes (committed) |
| `./src` | Source code (dev mode) | Yes (committed) |

### MCP Server Loading Methods

The SDK supports three methods for loading MCP servers:

| Method | Description | Use Case |
|--------|-------------|----------|
| **A: In-Process** | `create_sdk_mcp_server()` with `@tool` decorator | Custom tools with tight integration |
| **B: Stdio/Subprocess** | External process via `command` + `args` | Existing MCP servers, process isolation |
| **C: HTTP/SSE** | Remote servers via HTTP or SSE transport | Shared services, cloud-hosted tools |

Methods can be mixed in a single `ClaudeAgentOptions.mcp_servers` configuration.

### Agent Architecture Model

The SDK follows a **main agent + subagents** architecture:
- One primary `ClaudeSDKClient` session runs the main agent
- Main agent orchestrates specialized **subagents** via the `agents` parameter
- Subagents are invoked automatically (by context) or explicitly (by prompt)
- Parallelization happens at the subagent level, not via multi-threaded agents
- For true parallel execution, orchestrate multiple SDK client instances externally

## Long-Running Sessions (20+ Hours)

The harness is designed for extended autonomous sessions with built-in safeguards.

### Starting a Long Session

```bash
# 1. Stop any existing sessions
make down

# 2. Clean start
make clean

# 3. Build fresh
make build

# 4. Start in detached mode (runs in background)
make up

# 5. Verify everything is running
make health
make ps
```

### Before Starting

**Prevent Mac Sleep:**
```bash
# Keep Mac awake
caffeinate -s &

# Or: System Settings > Energy Saver > Prevent automatic sleep
```

**Monitor Disk Space:**
```bash
# Check available space
df -h .

# Monitor growth during session
du -sh workspace/ memory/ logs/
```

**Verify Checkpointing:**
```bash
# Check checkpoints are being created
ls -lh memory/checkpoints/

# Should see new files every hour
```

### During the Session

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

### Recovery from Interruption

If containers stop unexpectedly:

```bash
make up

# Agents automatically:
# 1. Load latest checkpoint
# 2. Resume from last known state
# 3. Continue task execution
```

### Monitoring Without Blocking Terminal

```bash
# View logs when needed (non-blocking)
make logs

# Check service health
make health

# View metrics dashboard
make metrics          # Opens Grafana

# Check resource usage
docker stats claude-main-agent
```

### Important Considerations

- **Checkpoint interval**: Default 1 hour (configurable via `CLAUDE_CHECKPOINT_INTERVAL`)
- **Checkpoint retention**: Keeps 5 most recent checkpoints
- **Health checks**: Every 30 seconds with auto-restart
- **Log rotation**: Automatic (configured in monitoring)
- **API budget**: Monitor in Grafana, set alerts in `.env`

## Security

### Built-in Security Features

- ✅ **Non-root containers** - All services run as non-root users
- ✅ **Read-only filesystems** - Where possible
- ✅ **Network isolation** - Bridge network with isolated services
- ✅ **Secret rotation** - Rotate every 30 days (recommended)
- ✅ **Audit logging** - Structured logs with correlation IDs
- ✅ **Resource limits** - Prevent DoS via container limits
- ✅ **No secrets in version control** - All secrets in `.env` (gitignored)

### Best Practices

1. **API Keys**: Rotate `ANTHROPIC_API_KEY` every 90 days
2. **Passwords**: Change default Grafana password immediately
3. **Service Accounts**: Use dedicated service accounts (not personal)
4. **Access Control**: Enable GitHub/GitLab SSO when available
5. **Audit Logs**: Review logs weekly for suspicious activity
6. **Container Scanning**: Scan with Trivy/Snyk before deployment
7. **Backups**: Backup checkpoints to S3/GCS with encryption

### Secret Management

```bash
# .env.example (committed to git)
DATABASE_URL=postgresql://user:pass@host:5432/db
API_KEY=your_api_key_here

# .env (never committed, gitignored)
DATABASE_URL=postgresql://prod:real_secret@prod:5432/mydb
API_KEY=sk_live_actual_key
```

## Troubleshooting

### Container Issues

**Containers won't start:**
```bash
# Check Docker daemon
docker info

# Check for port conflicts
make ps
lsof -i :8080

# View service logs
make logs-main
make logs
```

**Out of memory errors:**
```bash
# Increase memory in .env
AGENT_MEMORY_LIMIT=16G

# Restart services
make down && make up
```

### Configuration Issues

**API key not set:**
```bash
# Check .env file
cat .env | grep ANTHROPIC_API_KEY

# Add to .env
echo "ANTHROPIC_API_KEY=sk-ant-your_key" >> .env
```

**Environment not loading:**
```bash
# Verify .env exists
ls -la .env

# Restart with clean build
make down
make build
make up
```

### Build Issues

**Build cache issues:**
```bash
# Clean build without cache
make build-no-cache

# Or prune everything
make prune
make clean
```

**OrbStack issues (macOS):**
```bash
# Verify OrbStack is running
orb status

# Restart OrbStack
orb restart
```

### Performance Issues

**Slow responses:**
```bash
# Check resource usage
docker stats

# Increase resources in .env
AGENT_CPU_LIMIT=8
AGENT_MEMORY_LIMIT=16G

# Restart
make down && make up
```

**High API costs:**
```bash
# Check costs in Grafana
make metrics

# Reduce session timeout
CLAUDE_SESSION_TIMEOUT=36000  # 10 hours

# Use cheaper model
CLAUDE_MODEL=claude-haiku-3-5-20250311
```

### Monitoring Issues

**Grafana not accessible:**
```bash
# Check Grafana is running
make ps | grep grafana

# Check logs
docker compose logs grafana

# Restart Grafana
docker compose restart grafana
```

**Metrics not appearing:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify metrics endpoint
docker compose exec main-agent curl http://localhost:9090/metrics
```

### Debug Mode

```bash
# Start with debug logging
DEBUG=true LOG_LEVEL=DEBUG make dev

# Access shell for debugging
make shell

# Check service health
make health

# Run diagnostics
make doctor
```

## Resources

### Documentation
- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)
- [Technical Documentation (CLAUDE.md)](./CLAUDE.md) - Implementation details, development guide

### SDKs
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [TypeScript SDK](https://github.com/anthropics/claude-agent-sdk-typescript)

### Community
- [Example Agents Collection](https://github.com/wshobson/agents)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Contact
- **Author**: Andis A. Blukis
- **Email**: andis.blukis@gmail.com
- **GitHub**: [@andisab](https://github.com/andisab)
- **LinkedIn**: [andisab](https://linkedin.com/in/andisab)

---

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

**Built with ❤️ by developers, for developers**

*Star ⭐ this repository if you find it useful!*
