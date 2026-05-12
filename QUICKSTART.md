# Quickstart (5 Minutes)

Get the harness running and pick one of three modes: **interactive**, **autonomous**, or **optimize**.

## Prerequisites

- **Docker Desktop** (or [OrbStack](https://orbstack.dev) on Mac — faster)
- **Anthropic API Key** from [console.anthropic.com](https://console.anthropic.com)

Verify Docker is running:
```bash
docker info
```

## Setup
The repository uses `make` commands for consistency and simplicity. 

```bash
# 1. Clone and enter the repository
git clone https://github.com/andisab/ab-casdk-harness.git
cd ab-casdk-harness

# 2. Initialize (creates .env and required directories)
make init

# 3. Add your API key to .env
ANTHROPIC_API_KEY=sk-ant-your_key_here

# 4. Build and start services
make build
make up
```

`make up` brings up `main-agent` plus the observability stack (Prometheus, Grafana, OTel Collector, AlertManager). Run `make doctor` if anything looks off.

---

## Pick one of Three Modes

| Mode | Command | Use When |
|------|---------|----------|
| **Interactive** | `make interactive` | You want to chat with Claude — explore code, prototype, ask questions |
| **Autonomous** | `make autonomous` | You have created a SPEC.md for a larger project and want Claude to build it end-to-end in a long-running autonomous session. |
| **Optimize** | `make optimize` | You want to create or improve an agent / skill / plugin with specialized tools for contenxt engineering. |

Each mode runs inside the same `main-agent` container — no separate setup needed.

### 1. Interactive Mode — chat
---
Direct conversation with Claude through a Rich console UI. Tool calls, syntax highlighting, and session checkpoints are handled automatically. This can be thought of as a generic reference implementation for the setup of a containerized agentic system. Additional security measures and other work is needed for a production-ready system. 

```bash
make interactive                 # Default model (sonnet)
make interactive MODEL=haiku     # Faster and cost-effective
make interactive MODEL=opus      # Most capable
```

Try:
- `"List files in /workspace"`
- `"Create a Python script that validates email addresses"`
- `"What MCP servers are available?"`

Type `exit` or `quit` to end the session.


### 2. Autonomous Mode — spec-driven development
---
Give Claude a SPEC.md and it builds the project end-to-end. The `workspace` directory is your sandbox; a local `.git` repository is created there and commits are made as tasks complete.

```bash
# 1. Create a spec template
make init-spec

# 2. Edit workspace/SPEC.md with what you want built
#    (see docs/examples/AUTONOMOUS_SPEC.example.md for reference)

# 3. Run autonomous mode
make autonomous

# 4. Check progress (any time, from another terminal)
make autonomous-status
```

The run has two layers:

**Initializer phase** (one-time, Tech Lead agent):

```
REVIEW-SPEC → Q&A → FINALIZE-SPEC → TASK-LIST
```

The Tech Lead reads `SPEC.md`, asks clarifying questions one at a time (`Question X/Y` format), writes a "Decisions from Q&A" section back into `SPEC.md`, and emits `[TASK_LIST_READY]` once `task_list.json` is approved.

**Continuation phase** (per-task loop, Main Autodev agent):

```
RESEARCH → GENERATE → VALIDATE / ITERATE → COMMIT → (next task)
```

For each task the agent gets its bearings (Explore agent or direct read of context files), runs a regression check, picks the highest-priority pending task, plans complex changes (Plan agent), implements with tests alongside, validates with `code-review` and `sdet-expert` sub-agents (plus the Playwright MCP server for UI work), then commits and emits `[TASK_COMPLETE: task-XXX]` and `[COMMIT: <hash>: <message>]`. Loops until every task is `PASS` or `FAIL`.

If you Ctrl+C, run `make autonomous` again to resume from the last checkpoint. Sessions checkpoint every hour; tasks commit to git as they complete.


### 3. Optimize Mode — CGF prompt optimization
---
Improve a prompt resource (agent, skill, or whole plugin) using the ContextGrad Framework: research → design → generate → iterate → validate. The core CGF framework is shipped on `main`; an eval harness extension is in active development on the `contextgrad-eval` branch.

**Single resource** (improve one agent or skill):

```bash
# 1. Create a workspace with a SPEC.md template
make cgf-init NAME=my-agent

# 2. Drop the resource you want to optimize alongside the spec
cp path/to/my-agent.md workspace/my-agent/

# 3. Edit workspace/my-agent/SPEC.md with your goals

# 4. Run optimization (auto-discovers SPEC.md)
make optimize
```

**Multi-resource** (generate a whole plugin / skill set / workflow):

```bash
mkdir -p workspace/my-plugin
cp docs/examples/CGF_MULTI_RESOURCE_SPEC.example.md workspace/my-plugin/SPEC.md
# edit SPEC.md to describe purpose, capabilities, constraints
make optimize
```

Output lands in `workspace/<name>/` — versioned files (`my-agent-v1.md`, `-v2.md`, …), a `CHANGELOG.md`, plus `research/` and `reviews/` artifacts. The original is never modified. Delete `sessions/` to reset run state without losing artifacts.

Run `make optimize-dryrun` to validate setup before kicking off a full run.

---

## Common Issues

| Problem | Solution |
|---------|----------|
| Container won't start | Run `docker info` — is Docker running? |
| API key invalid | Check `.env` — key must start with `sk-ant-` |
| Port already in use | `make down` first, or `lsof -i :8080` |
| 60s timeout on startup | `CLAUDE_PERMISSION_MODE` must be `acceptEdits`, `bypassPermissions`, or `default` |
| Build failures | `make build-no-cache` |
| Multiple SPEC.md found | `make optimize` requires exactly one — delete extras |

Run `make doctor` for automated diagnostics.

---

## Essential Commands

```bash
# Modes
make interactive           # Chat with the agent
make autonomous            # Spec-driven autonomous development
make optimize              # CGF prompt optimization

# Lifecycle
make up                    # Start services
make down                  # Stop services
make logs                  # Tail all logs
make logs-main             # Tail main agent only
make shell                 # Shell into the main agent container

# Status / diagnostics
make autonomous-status     # Autonomous progress summary
make cgf-status            # Active CGF runs and phases
make health                # Service health check
make doctor                # Setup diagnostics
```

---

## Next Steps

- **Full overview**: [README.md](./README.md)
- **Technical reference**: [CLAUDE.md](./CLAUDE.md) — architecture, configuration, troubleshooting
- **Spec templates**: [docs/examples/](./docs/examples/) — `AUTONOMOUS_SPEC.example.md`, `CGF_SPEC.example.md`, `CGF_MULTI_RESOURCE_SPEC.example.md`
- **CGF deep dive**: [docs/CGF-USER-GUIDE.md](./docs/CGF-USER-GUIDE.md)
- **Monitoring**: Grafana at <http://localhost:3000> (`admin` / `${GRAFANA_PASSWORD:-changeme123}`)
