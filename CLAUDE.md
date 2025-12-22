# Claude Agent SDK Harness - Technical Documentation

Technical reference for developers working on this repository and for Claude's operational context.

> **User documentation**: See [README.md](./README.md) for user-focused guide.
> **Quick setup**: See [QUICKSTART.md](./QUICKSTART.md) for 5-minute setup.

---

## Current Status & TODOs

### Working Features
- Interactive mode with Rich CLI (`interactive.py`)
- Autonomous mode with Tech Lead + Main agent (`autonomous.py`)
- Docker orchestration with Prometheus + Grafana monitoring
- Checkpoint & recovery system with hourly auto-save
- 5 MCP servers (3 in-process + 2 subprocess)
- CLI tools: git, gh, glab
- Plugin system with agents, skills, commands, and hooks
- 18 subagents (14 harness + 4 plugin) via direct invocation
- 12 skills via Skill tool (6 base + 6 plugin)

### Known Limitations
- **SDK Task tool bug**: Custom agents not recognized (GitHub #11205, #12212). Use `harness.direct_agent` module instead
- Grafana overview dashboard is placeholder (stub file)
- AlertManager not configured (alerting rules defined but unused)

### TODOs
- [ ] Fix `config/monitoring/dashboards/overview.json` (currently 41-byte stub)
- [ ] Configure AlertManager in docker-compose for `alerting.yml` rules
- [ ] Remove postgres/redis exporter targets from `prometheus.yml` (services don't exist)

---

## Repository Structure

```
casdk-harness/
├── src/
│   ├── harness/                    # Main Python package
│   │   ├── agent.py                # AgentSession wrapper with SDK integration
│   │   ├── autonomous.py           # Autonomous mode orchestration
│   │   ├── checkpoint.py           # Checkpoint manager with auto-save
│   │   ├── cli.py                  # Rich CLI formatting
│   │   ├── commands.py             # Slash command registry
│   │   ├── config.py               # Pydantic configuration
│   │   ├── direct_agent.py         # Direct agent invocation (bypasses Task tool)
│   │   ├── hooks.py                # Lifecycle hook registry
│   │   ├── interactive.py          # Interactive conversation loop
│   │   ├── monitoring.py           # Prometheus metrics collector
│   │   ├── plugin_manager.py       # Plugin discovery and loading
│   │   ├── progress.py             # Task list and session tracking
│   │   ├── agents/configs/         # 14 agent definition files
│   │   ├── prompts/                # 8 prompt files (5 container modes + 3 autonomous workflow)
│   │   ├── plugins/                # 2 plugins (context-engineering, research-team)
│   │   ├── skills/                 # 6 base skills
│   │   └── config/.mcp.json        # MCP subprocess server config
│   └── mcp_servers/                # 3 in-process MCP servers
│       ├── context7/               # Library documentation lookup
│       ├── docker/                 # Container management
│       └── memory/                 # Knowledge graph persistence
├── agents/main/Dockerfile          # Multi-stage build (base, deps, dev, builder, prod)
├── config/monitoring/              # Prometheus & Grafana configs
├── workspace/                      # Agent working directory (gitignored)
├── memory/                         # Checkpoints, knowledge graph (gitignored)
├── logs/                           # Application logs (gitignored)
└── tests/                          # Unit, integration, e2e tests
```

---

## Working Environment

When running inside the harness container:

### Directory Layout
- **`/app`** - System configuration (READ-ONLY, agent cwd)
- **`/workspace`** - Development work directory (READ-WRITE)
  - `/workspace/projects/` - Clone external repos here
  - `/workspace/context/` - Technical context files
- **`/memory`** - Persistent state (checkpoints, knowledge graph)
- **`/logs`** - Structured application logs
- **`/config`** - Prometheus/Grafana configs

**Important**: All development work must use `/workspace` with absolute paths.

### Available Tools

**MCP Servers** (5 total):

| Server | Type | Purpose |
|--------|------|---------|
| `docker` | In-process | Container management |
| `context7` | In-process | Library documentation lookup |
| `memory` | In-process | Knowledge graph persistence |
| `playwright` | Subprocess | DOM-based browser automation |
| `puppeteer` | Subprocess | Visual browser automation |

**CLI Tools** (use via Bash):
- `git` - Version control (SSH keys in `.ssh/`)
- `gh` - GitHub CLI (requires auth or `GITHUB_PERSONAL_ACCESS_TOKEN`)
- `glab` - GitLab CLI (requires auth or `GITLAB_PERSONAL_ACCESS_TOKEN`)

---

## Core Architecture

### Interactive vs Autonomous Mode

```
┌─────────────────────────────────────────────────────────────────────┐
│                         config.py                                    │
│  ┌──────────────────────────┐  ┌──────────────────────────┐        │
│  │ interactive_permission   │  │ autonomous_permission    │        │
│  │ = "acceptEdits"          │  │ = "bypassPermissions"    │        │
│  └──────────────────────────┘  └──────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
                │                              │
                ▼                              ▼
┌───────────────────────────┐    ┌───────────────────────────────────┐
│    interactive.py         │    │         autonomous.py              │
│                           │    │                                    │
│  run_interactive_session()│    │  AutonomousRunner.run()           │
│  └─> AgentSession(        │    │  └─> async with AgentSession(     │
│        agent_name="main", │    │        agent_name="autonomous-*", │
│        config=config,     │    │        model=self.model,          │
│        quiet=args.quiet   │    │        system_prompt=prompt,      │
│      )                    │    │        permission_mode=auto_mode  │
│                           │    │      )                            │
│  Manual lifecycle:        │    │                                    │
│  - start()                │    │  Context manager lifecycle         │
│  - execute() in loop      │    │  - __aenter__ → start()           │
│  - shutdown()             │    │  - execute() in loop              │
│                           │    │  - __aexit__ → shutdown()         │
└───────────────────────────┘    └───────────────────────────────────┘
                │                              │
                └──────────────┬───────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          agent.py                                    │
│                                                                      │
│  AgentSession                                                        │
│  ├── __init__()         # Load config, MCP servers, plugins         │
│  ├── start()            # Connect SDK, start background tasks        │
│  ├── execute()          # Send prompts, yield responses             │
│  ├── _build_sdk_options() # Build ClaudeAgentOptions                │
│  ├── _load_system_prompt() # Load from file (interactive default)   │
│  └── shutdown()         # Cleanup SDK, save checkpoint              │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode Comparison

| Aspect | Interactive | Autonomous |
|--------|-------------|------------|
| **Entry point** | `harness.interactive` | `harness.autonomous` |
| **Agent name** | `"main"` | `"autonomous-initializer"` or `"autonomous-continuation"` |
| **Permission mode** | `acceptEdits` | `bypassPermissions` |
| **System prompt** | From `main-interactivedev-agent.md` | Built dynamically |
| **Session management** | Manual start/shutdown | Context manager |
| **User interaction** | Every turn | Initializer mode only |
| **Progress tracking** | Checkpoints only | ProgressManager + checkpoints |
| **Multiple sessions** | No | Yes (loop until done) |

### Autonomous Mode Workflow

**Workspace State Detection:**

| State | Condition | Action |
|-------|-----------|--------|
| EMPTY | Only SPEC.md or nothing | Run `git init`, proceed to initializer |
| WORK_IN_PROGRESS | task_list.json with incomplete tasks | Continue normally |
| COMPLETED | All tasks PASS/FAIL | Prompt: review or archive |
| CONFLICT | Multiple SPEC.md or task_list.json | REFUSE, require manual cleanup |
| EXTERNAL_REPO | .git exists, no SPEC.md + task_list.json | Ask: work on repo or clean |
| MIXED | Files exist, no .git | Warn, ask about cleanup |

**Two-Phase Workflow:**

1. **Initializer Mode** (Tech Lead Q&A):
   - Loads `tech-lead-agent.md` prompt
   - Interactive Q&A to refine requirements
   - QA session saved to `qa_session.json` for resume
   - Generates `task_list.json` when ready

2. **Continuation Mode** (Autonomous coding):
   - Loads `main-autodev-agent.md` prompt
   - Works on highest priority incomplete task
   - Parses completion signals: `[TASK_COMPLETE:]`, `[TASK_BLOCKED:]`, `[COMMIT:]`
   - Updates task_list.json status in real-time
   - Loops until all tasks done

---

## Multi-Agent Architecture

### Agent Types

| Type | Location | Invocation | Process |
|------|----------|------------|---------|
| **Subagents** | `src/harness/agents/configs/*.md` | `harness.direct_agent` | Same process |
| **Plugin Agents** | `src/harness/plugins/*/agents/*.md` | `harness.direct_agent` | Same process |
| **Container Agents** | `docker-compose.yml` services | Docker | Separate containers |

### Subagents (14 harness + 4 plugin)

Invoked via `harness.direct_agent` module (Task tool has SDK bug):

| Category | Agents |
|----------|--------|
| **Development** (7) | python-expert, typescript-expert, go-expert, nodejs-expert, react-expert, refactor-agent, code-review-expert |
| **Database** (2) | postgres-expert, sql-expert |
| **Infrastructure** (4) | docker-engineer, k8s-engineer, gcp-architect, gitlab-ci-expert |
| **Testing** (1) | sdet-expert |

**Definition files**: `src/harness/agents/configs/` with YAML frontmatter:
```markdown
---
name: python-expert
description: Python/FastAPI/async development
model: sonnet
tools: Read, Write, Bash, mcp__context7
---
System prompt content...
```

### Direct Agent Invocation

Due to SDK Task tool bug (#11205, #12212), use `harness.direct_agent` module:

```python
from harness.direct_agent import call_agent, call_agent_simple, list_available_agents

# List agents
agents = list_available_agents()

# Simple call (returns text)
response = await call_agent_simple("python-expert", "Write a sort function")

# Streaming call with verbose progress
async for msg in call_agent("research-team:lead-research-coordinator", "Research X", verbose=True):
    process(msg)
```

**CLI usage:**
```bash
python -m harness.direct_agent --list                    # List agents
python -m harness.direct_agent --info python-expert      # Agent details
python -m harness.direct_agent --agent python-expert --prompt "..." --verbose
```

**Agent settings**: `max_turns` in YAML frontmatter controls conversation length (default: 100, research agents: 200-500).

### Container Agents (Multi-Agent Profile)

Enabled with `make up-multi`:

| Service | Permission | Workspace | Prompt |
|---------|------------|-----------|--------|
| main-agent | acceptEdits | Read-write | `main-interactivedev-agent.md` |
| agent-two | default | **Read-only** | `agent-two.md` |
| agent-three | bypassPermissions | Read-write | `agent-three.md` |

Container agents communicate via Redis Streams (`src/harness/messaging.py`).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              HARNESS ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        MAIN AGENT CONTAINER                              │   │
│  │                                                                          │   │
│  │   AgentSession                                                           │   │
│  │   ├── ClaudeSDKClient                                                    │   │
│  │   │   ├── agents=sdk_agents ─────────────────────┐                      │   │
│  │   │   ├── mcp_servers (docker, context7, memory) │                      │   │
│  │   │   └── plugins (context-engineering, etc.)    │                      │   │
│  │   │                                              │                      │   │
│  │   └── RedisMessageBroker ──────────────────────────────┐                │   │
│  │                                              │         │                │   │
│  │                                              ▼         │                │   │
│  │   ┌──────────────────────────────────────────────┐    │                │   │
│  │   │         SUBAGENTS (Task Tool)                │    │                │   │
│  │   │         Same Process - Isolated Context      │    │                │   │
│  │   │                                              │    │                │   │
│  │   │  ┌────────────┐ ┌────────────┐ ┌──────────┐ │    │                │   │
│  │   │  │  python-   │ │ typescript │ │   go-    │ │    │                │   │
│  │   │  │  expert    │ │  -expert   │ │  expert  │ │    │                │   │
│  │   │  └────────────┘ └────────────┘ └──────────┘ │    │                │   │
│  │   │           ... (14 total subagents)          │    │                │   │
│  │   └──────────────────────────────────────────────┘    │                │   │
│  └───────────────────────────────────────────────────────│────────────────┘   │
│                                                          │                     │
│                          Redis Streams                   │                     │
│                    ┌─────────────────────────────────────┘                     │
│                    ▼                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                           REDIS SERVER                                   │  │
│  │   Stream: agent:tasks    Stream: agent:results    Consumer Groups       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                    │                                     │                     │
│         ┌─────────┴─────────┐               ┌───────────┴───────────┐        │
│         ▼                   ▼               ▼                       ▼        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │  AGENT-TWO   │    │ AGENT-THREE  │    │   (future)   │    │  (future) │  │
│  │  (Evaluator) │    │  (Validator) │    │   DEPLOYER   │    │  MONITOR  │  │
│  │              │    │              │    │              │    │           │  │
│  │ Workspace:   │    │ Workspace:   │    │              │    │           │  │
│  │  READ-ONLY   │    │ read-write   │    │              │    │           │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Python Modules

### agent.py

AgentSession wrapper with SDK lifecycle management:

- Session lifecycle (start, execute, shutdown)
- MCP server registration (5 servers)
- Automatic checkpointing integration
- Metrics collection integration
- Retry logic with exponential backoff

### autonomous.py

Orchestrates autonomous development sessions:

**Classes:**
- `AutonomousRunner` - Main workflow controller
- `ProgressManager` - Task list and session tracking

**Key Features:**
- Workspace state detection (6 states)
- Tech Lead Q&A with resume capability (`qa_session.json`)
- Completion signal parsing
- Configurable delay between sessions
- External repo support with `casdk-` branch naming

### checkpoint.py

Automatic checkpoint management:

- Auto-save every hour (configurable via `CLAUDE_CHECKPOINT_INTERVAL`)
- Keeps last 5 checkpoints (configurable via `CHECKPOINT_KEEP_COUNT`)
- Atomic writes with file locking
- Recovery from latest on startup

### config.py

Pydantic-based configuration:

- Type-safe settings with validation
- Environment variable loading from `.env`
- Default values for all optional settings

**Key settings:**
```python
claude_model = "claude-sonnet-4-5-20250929"
interactive_permission_mode = "acceptEdits"
autonomous_permission_mode = "bypassPermissions"
claude_max_turns = 1000
claude_checkpoint_interval = 3600  # 1 hour
autonomous_delay_seconds = 5
```

### monitoring.py

Prometheus metrics collector:

- `agent_requests_total{agent, status}` - Request counter
- `agent_duration_seconds{agent}` - Request histogram
- `api_tokens_used_total{model, type}` - Token counter
- `api_cost_dollars_total{model}` - Cost counter
- `interactive_tool_calls_total{agent, tool_name, status}` - Tool call counter

Metrics exposed on port 9090.

### plugin_manager.py

Centralized plugin lifecycle management:

- Plugin discovery from configured directories
- Manifest parsing and validation
- Resource loading (agents, skills, commands, hooks)
- SDK-compatible agent conversion
- Namespaced resource access

### commands.py

Slash command infrastructure:

- CommandRegistry for registration and execution
- Argument substitution ($1, $2, $ARGUMENTS, $FILE)
- Namespaced and short-name lookups

### hooks.py

Lifecycle hook infrastructure:

- HookRegistry for registration and triggering
- Async and sync execution modes
- Pattern matching (tool_name, file_path globs)
- Timeout handling

---

## Plugin System

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentSession                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │PluginManager │  │CommandRegistry│  │ HookRegistry │      │
│  │              │  │              │  │              │      │
│  │ discover()   │  │ register()   │  │ register()   │      │
│  │ load_all()   │  │ execute()    │  │ trigger()    │      │
│  └──────┬───────┘  └──────────────┘  └──────────────┘      │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Plugin                              │  │
│  │  .claude-plugin/plugin.json                           │  │
│  │  ├── agents/      → SDKAgentDefinition               │  │
│  │  ├── skills/      → Skill metadata                   │  │
│  │  ├── commands/    → PluginCommand                    │  │
│  │  └── hooks/       → PluginHook                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Resource Types

| Type | Count | Invocation | Status |
|------|-------|------------|--------|
| Harness Agents | 14 | `harness.direct_agent.call_agent()` | Working |
| Plugin Agents | 4 | `harness.direct_agent.call_agent()` | Working |
| Base Skills | 6 | `Skill(skill="...")` | Working |
| Plugin Skills | 6 | `Skill(skill="plugin:name")` | Working |
| Commands | 2 | CommandRegistry | Working |
| Hooks | 2 | HookRegistry | Working |

### Plugins (2 total)

**context-engineering** (`src/harness/plugins/context-engineering/`):
- 1 agent: context-engineer
- 5 skills: agent-definition-creation, skill-creation, plugin-development, command-creation, hook-configuration
- 1 command: create-agent
- Hook configuration for lifecycle events

**research-team** (`src/harness/plugins/research-team/`):
- 3 agents: lead-research-coordinator, research-specialist, research-report-writer
- 1 skill: joplin-research
- 1 command: research

### Namespacing

All plugin resources use `plugin-name:resource-name` format:
- Skills: `context-engineering:skill-creation`
- Commands: `context-engineering:create-agent`

### Hook Events

| Event | Triggered | Purpose |
|-------|-----------|---------|
| PostSessionStart | After start() | Post-init actions |
| STOP | Before shutdown() | Cleanup actions |
| PreToolUse | Before tool call | Tool filtering (defined, not triggered) |
| PostToolUse | After tool call | Post-processing (defined, not triggered)

---

## Configuration Reference

### Required
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

### Agent Settings
```bash
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_PERMISSION_MODE=acceptEdits  # default, acceptEdits, bypassPermissions
CLAUDE_MAX_TURNS=1000
CLAUDE_CHECKPOINT_INTERVAL=3600     # seconds
```

### Autonomous Mode
```bash
AUTONOMOUS_PERMISSION_MODE=bypassPermissions
AUTONOMOUS_DELAY_SECONDS=5          # Note: .env.example shows 3, code default is 5
AUTONOMOUS_MAX_SESSIONS=100
AUTONOMOUS_TASK_TIMEOUT=1800        # 30 minutes
```

### Resources
```bash
AGENT_CPU_LIMIT=4
AGENT_MEMORY_LIMIT=8G
```

### Plugin Settings
```bash
ENABLED_PLUGINS=context-engineering,research-team  # Comma-separated (empty = all)
PLUGIN_USE_SDK_ONLY=false                          # Disable workarounds when SDK fixed
```

See [.env.example](/.env.example) for complete list.

---

## Docker Services

### Critical Container Requirements

The Dockerfile includes two critical settings that prevent common SDK issues:

1. **`ENV PYTHONUNBUFFERED=1`** - Forces unbuffered stdout. Without this, Python subprocess uses 8KB block buffering in containers (no TTY), causing messages to accumulate unsent and SDK initialization timeouts ("0 messages received").

2. **`ENTRYPOINT ["/usr/bin/tini", "--"]`** - Proper init system for signal handling. Without tini, the shell becomes PID 1 and receives SIGTERM but doesn't forward to Python, causing agent subprocess to never flush buffers and messages lost on container stop.

### Default Profile
```bash
make up  # Starts these services
```
- **main-agent** (port 8080, metrics 9091) - Primary development agent
- **prometheus** (port 9090) - Metrics collection
- **grafana** (port 3000) - Dashboards (admin/admin)

### Multi-Agent Profile
```bash
make up-multi  # Adds these services
```
- **agent-two** (port 8081) - Evaluator (read-only workspace, default: code review)
- **agent-three** (port 8082) - Validator (full access, default: testing)
- **redis** (port 6379) - Inter-agent communication via Redis Streams

---

## Development Workflow

### Git Workflow
```bash
git checkout -b feature/descriptive-name
# Make changes
git commit -m "feat(agent): add retry logic"
git push origin feature/descriptive-name
```

### Conventional Commits
- `feat(scope):` - New feature
- `fix(scope):` - Bug fix
- `docs(scope):` - Documentation
- `refactor(scope):` - Code restructure
- `test(scope):` - Tests

### Testing
```bash
make test                # Full test suite
make test-unit           # Fast, no API calls
make test-integration    # Requires API key
make test-multi          # Multi-agent coordination tests
make coverage            # Coverage report
```

### Code Quality
```bash
make lint       # Check with ruff
make lint-fix   # Auto-fix issues
make typecheck  # Run mypy
make format     # Format code
```

---

## Troubleshooting

Run `make doctor` for automated diagnostics.

### Common Gotchas & Solutions

| Problem | Symptom | Root Cause | Solution |
|---------|---------|-----------|----------|
| **0 messages received** | SDK initialization timeout | Block buffering in subprocess | Dockerfile has `ENV PYTHONUNBUFFERED=1` (verify present) |
| **Timeout on initialize** | 60s timeout during startup | Invalid permission mode or MCP server failure | Check `CLAUDE_PERMISSION_MODE` is valid (`acceptEdits`, `bypassPermissions`, `default`) |
| **Process hangs on stop** | Container requires `docker kill` | Shell is PID 1, doesn't forward signals | Dockerfile uses `ENTRYPOINT ["/usr/bin/tini", "--"]` |
| **Partial message loss** | StreamReader truncates output | Default 64KB buffer too small | SDK uses `limit=1024*256` in subprocess |
| **Container restarts fail** | Healthcheck always failing | Health endpoint not responding | Verify port 8080 is exposed and agent started |
| **Cross-container IPC fails** | Subagents can't communicate | Subprocess pipes don't cross containers | Use `--profile multi-agent` for Redis Streams |
| **Permission denied errors** | Tools blocked unexpectedly | `permission_mode` misconfigured | Set `CLAUDE_PERMISSION_MODE=bypassPermissions` for autonomous |
| **API rate limits** | 429 Too Many Requests | Too many concurrent requests | Reduce parallel agent instances |

### Quick Checks

- Container won't start → `docker info` (is Docker running?)
- API key invalid → Verify `.env` has `sk-ant-` prefix
- Port conflict → `make down` first, or check `lsof -i :8080`

See [README.md#troubleshooting](./README.md#troubleshooting) for user-focused solutions.

---

## Resources

### Project Documentation
- [README.md](./README.md) - User-facing documentation
- [QUICKSTART.md](./QUICKSTART.md) - 5-minute setup
- [docs/HARDENING.md](./docs/HARDENING.md) - Production security

### Claude Agent SDK
- [Agent SDK Overview](https://docs.claude.com/en/api/agent-sdk/overview)
- [Python SDK Reference](https://docs.claude.com/en/docs/agent-sdk/python)
- [MCP in SDK](https://docs.claude.com/en/docs/agent-sdk/mcp)
- [Hosting Guide](https://docs.claude.com/en/docs/agent-sdk/hosting)

### GitHub Repositories
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [SDK Demos](https://github.com/anthropics/claude-agent-sdk-demos)
- [MCP Servers](https://github.com/modelcontextprotocol/servers)

### Docker Resources
- [tini (init for containers)](https://github.com/krallin/tini)
- [Multi-stage Build Docs](https://docs.docker.com/build/building/multi-stage/)

---

**Maintainer**: Andis A. Blukis (andis.blukis@gmail.com)
**License**: MIT
