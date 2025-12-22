# Claude Agent SDK Harness

A framework for building autonomous development agents with Claude.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-24.0+-blue.svg)](https://www.docker.com/)

**New here?** See [QUICKSTART.md](./QUICKSTART.md) to get chatting in 5 minutes.

---

## What Is This?

A Dockerized framework for running Claude Agent SDK with:

- **Interactive Mode** - Chat with Claude to explore code, plan specs, and do development
- **Autonomous Mode** - Give Claude a spec file and let it build features end-to-end
- **Built-in Tools** - File operations, git, shell commands, MCP servers
- **State Persistence** - Checkpoints save your session state
- **GitHub/GitLab Integration** - Work on local or remote repositories
- **Sandboxed Environment** - Agents run in containers, not on your local system
- **Monitoring** - Usage and session data tracked with Grafana & Prometheus

## Prerequisites

- **Docker Desktop** (or [OrbStack](https://orbstack.dev) on Mac)
- **Anthropic API Key** from [console.anthropic.com](https://console.anthropic.com)

Verify Docker is running:
```bash
docker info
docker compose version
```

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for the complete 5-minute setup guide.

```bash
git clone https://www.github.com/andis/ab-casdk-harness.git
cd casdk-harness && make init
# Edit .env and set: ANTHROPIC_API_KEY=sk-ant-your_key_here
make build && make up && make interactive
```

Run `make doctor` to diagnose any setup issues.

---

## Interactive Mode

Chat with Claude directly through a Rich console UI.

```bash
make interactive              # Start chat (default: sonnet model)
make interactive MODEL=opus   # Use a specific model
make interactive MODEL=haiku  # Faster, cheaper model
```

**Example prompts:**
- `"List files in /workspace"`
- `"Create a Python script that sorts a CSV file"`
- `"What MCP servers are available?"`

**Features:**
- Syntax highlighting for code
- Real-time tool use display
- Session statistics on exit
- Automatic checkpoint recovery

Type `exit` or `quit` to end your session.

---

## Autonomous Mode

Let Claude build features autonomously from a specification file.

```bash
# 1. Create a spec file from the template
make init-spec
# Edit workspace/SPEC.md to describe your project

# 2. Start autonomous mode
make autonomous

# 3. Check progress (from another terminal)
make autonomous-status
```

**How it works:**
1. Write a SPEC.md describing what you want to build
2. Run `make autonomous` - a Tech Lead agent refines requirements through Q&A
3. Tasks are created in `task_list.json`
4. Claude works through each task, verifying with tests
5. Progress tracked until 100% completion

If interrupted with Ctrl+C, run `make autonomous` again to resume.

See [docs/SPEC.example.md](./docs/SPEC.example.md) for spec writing best practices.

---

## Essential Commands

| Command | Description |
|---------|-------------|
| `make interactive` | Start interactive chat |
| `make autonomous` | Start autonomous development |
| `make autonomous-status` | Show progress summary |
| `make build` | Build all services |
| `make up` | Start services (background) |
| `make down` | Stop all services |
| `make logs` | View all service logs |
| `make shell` | Shell into main agent container |
| `make doctor` | Diagnose setup issues |

**Tip**: Use `MODEL=opus make interactive` to select a different model.

### Service Profiles

| Profile | Command | Services |
|---------|---------|----------|
| Default | `make up` | main-agent, prometheus, grafana |
| Multi-Agent | `make up-multi` | + agent-two (evaluator), agent-three (validator), redis |

Multi-agent mode enables parallel evaluation and validation agents.

---

## Configuration

Configuration is managed through `.env` (copy from `.env.example`).

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | (required) |
| `CLAUDE_MODEL` | Model to use | `claude-sonnet-4-5-20250929` |
| `CLAUDE_PERMISSION_MODE` | `default`, `acceptEdits`, or `bypassPermissions` | `acceptEdits` |

See [.env.example](./.env.example) for all configuration options.

### SSH Keys (for private repositories)

```bash
make ssh-init             # Initialize SSH directory
make ssh-keygen-github    # Generate GitHub key
make ssh-keygen-gitlab    # Generate GitLab key
make ssh-test             # Test connections
```

Keys are dedicated to this project, mounted read-only into containers.

---

## Working with Plugins

The harness includes a plugin system for extending capabilities with custom agents, skills, commands, and hooks.

### Available Plugins

| Plugin | Agents | Skills | Purpose |
|--------|--------|--------|---------|
| context-engineering | 1 | 5 | Agent/skill creation toolkit |
| research-team | 3 | 1 | Research and documentation |

### Using Skills

Load domain expertise during conversation:

```bash
# In interactive mode, ask Claude to use a skill
"Load the debugging skill and help me troubleshoot this error"
"Use the python-development skill to review this FastAPI code"
```

Skills provide specialized knowledge and workflows for specific domains.

### Plugin Structure

Plugins live in `src/harness/plugins/` with this structure:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json      # Manifest declaring resources
├── agents/              # Agent definitions (*.md)
├── skills/              # Skills (skill-name/SKILL.md)
├── commands/            # Slash commands (*.md)
└── hooks/               # Lifecycle hooks (*.json)
```

### Creating Custom Resources

See existing plugins for examples:
- **Skills**: `src/harness/skills/debugging/SKILL.md`
- **Agents**: `src/harness/agents/configs/dev-python-expert.md`
- **Commands**: `src/harness/plugins/context-engineering/commands/create-agent.md`

For detailed plugin development, use the `context-engineering:plugin-development` skill.

---

## Working with External Repositories

Clone external repos to `/workspace/projects/`:

```bash
make shell
cd /workspace/projects
git clone https://github.com/user/your-repo.git
```

For autonomous mode on external repos, add a SPEC.md with a `branch` field:

```markdown
# Project: Add Authentication

branch: casdk-auth-feature

## Requirements
...
```

---

## Monitoring

| Service | URL | Purpose |
|---------|-----|---------|
| **Grafana** | http://localhost:3000 | Dashboards (login: admin/admin) |
| **Prometheus** | http://localhost:9090 | Metrics and queries |

```bash
make logs           # View all logs
make logs-main      # View main agent logs
make health         # Check service health
```

---

## Long-Running Sessions

The harness supports extended sessions with automatic checkpointing:

- **Checkpoints**: Saved every hour, keeps last 5
- **Recovery**: Run `make autonomous` again to resume from last checkpoint
- **Mac users**: Run `caffeinate -s &` to prevent sleep during long sessions

---

## Troubleshooting

Run `make doctor` for automated diagnostics.

### Quick Decision Tree

```
Agent not responding?
├─ 60s timeout? → Invalid permission mode (use: acceptEdits, bypassPermissions, default)
├─ No output? → Missing PYTHONUNBUFFERED=1
├─ Container restarting? → Check: docker compose logs main-agent
└─ Slow/partial messages? → Check resource limits in .env
```

### Common Issues

| Problem | Solution |
|---------|----------|
| Container won't start | `docker info` - is Docker running? |
| 60s timeout on startup | Invalid `CLAUDE_PERMISSION_MODE` in .env |
| API key invalid | Check `.env` - key should start with `sk-ant-` |
| Port already in use | `make down` first, or `lsof -i :8080` |
| Build failures | `make build-no-cache` |
| Out of memory | Set `AGENT_MEMORY_LIMIT=16G` in .env |
| High API costs | Use `MODEL=haiku make interactive` |
| Checkpoint not loading | `rm -rf memory/checkpoints/*` for fresh start |
| SPEC.md not detected | Verify `workspace/SPEC.md` exists |

### Debug Commands

```bash
make doctor          # Automated diagnostics
make logs            # View all service logs
make logs-main       # Main agent logs only
make health          # Service health check
make shell           # Shell into container
docker stats         # Resource usage
```

### Getting Help

1. Run `make doctor` - catches most common problems
2. Check `make logs` - usually reveals the issue
3. See [CLAUDE.md](./CLAUDE.md) for technical details

---

## Resources

- [QUICKSTART.md](./QUICKSTART.md) - 5-minute setup guide
- [CLAUDE.md](./CLAUDE.md) - Technical documentation for developers
- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)

---

**Author**: Andis A. Blukis ([@andisab](https://github.com/andisab))

MIT License
