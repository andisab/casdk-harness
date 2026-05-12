# Claude Agent SDK Harness

A Dockerized framework for running Claude Agent SDK agents — interactively, autonomously, or through a prompt optimization pipeline.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-24.0+-blue.svg)](https://www.docker.com/)

**New here?** Start with [QUICKSTART.md](./QUICKSTART.md) — running in 5 minutes.

---

## What Is This?

A self-contained harness for building and operating Claude agents:

- **Three modes** — Interactive chat, autonomous spec-driven development, and CGF prompt optimization.
- **Sandboxed environment** — Agents run in containers, isolated from your host.
- **Built-in tools** — File ops, git, shell, plus 4 MCP servers (docker, context7, memory, playwright).
- **State persistence** — Hourly checkpoints with automatic recovery.
- **Plugin system** — Loads Claude Code plugins from in-tree and the [swe-marketplace](https://github.com/andisab/swe-marketplace) repo.
- **GitHub / GitLab integration** — `gh`, `glab`, and SSH key management built in.
- **Observability** — OTel + Prometheus + Grafana + AlertManager pre-provisioned with two dashboards.

## Prerequisites

- **Docker Desktop** (or [OrbStack](https://orbstack.dev) on Mac)
- **Anthropic API Key** from [console.anthropic.com](https://console.anthropic.com)

```bash
docker info
docker compose version
```

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for the full 5-minute walkthrough.

```bash
git clone https://github.com/andisab/ab-casdk-harness.git
cd ab-casdk-harness && make init
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
make build && make up
```

Run `make doctor` to diagnose setup issues.

---

## Three Modes

| Mode | Entry point | Best for |
|------|-------------|----------|
| [Interactive](#interactive-mode) | `make interactive` | Exploration, prototyping, ad-hoc tasks |
| [Autonomous](#autonomous-mode) | `make autonomous` | Building features end-to-end from a SPEC.md |
| [Optimize (CGF)](#optimize-mode-cgf) | `make optimize` | Improving / generating agent, skill, or plugin prompts |

All three run inside the same `main-agent` container started by `make up`.

---

## Interactive Mode

Chat with Claude directly through a Rich console UI. Tool calls render inline, sessions are checkpointed, and recovery is automatic on the next start.

```bash
make interactive                 # Default model (sonnet)
make interactive MODEL=haiku     # Faster, cheaper
make interactive MODEL=opus      # Most capable
make interactive-debug           # Verbose: DEBUG logs, raw SDK messages, per-turn stats table
```

**Example prompts:**
- `"List files in /workspace"`
- `"Create a Python script that sorts a CSV file"`
- `"What MCP servers are available?"`

**What you get:**
- Syntax highlighting for code
- Real-time tool-use display
- Session statistics on exit
- Automatic checkpoint recovery

Type `exit` or `quit` to end the session.

---

## Autonomous Mode

Give Claude a SPEC.md and let it build the project end-to-end.

```bash
# 1. Create a spec from the template
make init-spec
#    Then edit workspace/SPEC.md to describe the project

# 2. Run autonomous mode
make autonomous

# 3. Check progress (from another terminal, any time)
make autonomous-status
```

**How it works:**

1. **Tech Lead Q&A** — On first run, an initializer agent loads `SPEC.md`, asks clarifying questions, and writes a structured `task_list.json`. The Q&A persists, so Ctrl+C / resume is safe.
2. **Continuation loop** — A coding agent picks the highest-priority incomplete task, works on it, and emits one of `[TASK_COMPLETE:]`, `[TASK_BLOCKED:]`, or `[COMMIT:]`. The runner updates `task_list.json` and starts the next task.
3. **Checkpoints** — Saved every hour. Run `make autonomous` again to resume.
4. **Workspace state detection** — The runner detects empty workspaces, work-in-progress, completed runs, conflicts, and external repos, and behaves accordingly.

**Spec template:** [docs/examples/AUTONOMOUS_SPEC.example.md](./docs/examples/AUTONOMOUS_SPEC.example.md)

For autonomous work on an existing repo, clone it under `/workspace/projects/` and add a `branch:` field to `SPEC.md` (the runner will create a `casdk-*` feature branch).

---

## Optimize Mode (CGF)

The **ContextGrad Framework (CGF)** improves or generates prompt resources — agents, skills, commands, or whole plugins — through a multi-phase pipeline driven by specialized sub-agents.

### Single resource — improve one agent / skill

```bash
# 1. Initialize a CGF workspace with a SPEC.md template
make cgf-init NAME=my-agent

# 2. Drop the resource file you want to optimize next to the spec
cp path/to/my-agent.md workspace/my-agent/

# 3. Edit workspace/my-agent/SPEC.md with your goals

# 4. Run optimization (auto-discovers SPEC.md)
make optimize
```

The single-resource flow runs a two-phase session: an **interactive Q&A** with the `cgf-initializer` agent, then **autonomous optimization** by `cgf-orchestrator`.

### Multi-resource — generate a plugin / skill set / workflow

```bash
mkdir -p workspace/my-plugin
cp docs/examples/CGF_MULTI_RESOURCE_SPEC.example.md workspace/my-plugin/SPEC.md
# Edit SPEC.md: purpose, capabilities, constraints
make optimize
```

Auto-detected by the presence of a `## Capabilities` section. Pipeline:

```
PLANNING → RESEARCH → DESIGN → GENERATE → ITERATE → VALIDATE → COMPLETE
            (cgf-     (cgf-    (context-  (cgf-      (cgf-
             research- resource- engineer)  prompt-    coherence-
             lead)     architect)           optimizer) validator)
```

ITERATE loops per resource until quality reaches `CGF_QUALITY_THRESHOLD` (default `0.85`) or `CGF_MAX_ITERATIONS` is hit.

### Output structure

Workspace root = the directory containing `SPEC.md`. The original resource is **never modified**.

```
workspace/my-agent/
├── SPEC.md                  # Your goals (or Q&A-generated)
├── CHANGELOG.md             # Human-readable run history (accumulates)
├── my-agent.md              # Original (unchanged)
├── my-agent-v1.md           # First optimization
├── my-agent-v2.md           # Subsequent refinements
├── research/                # Research notes, eval criteria, reviews
└── sessions/                # Runtime state (delete to reset)
```

### CGF commands

| Command | Description |
|---------|-------------|
| `make cgf-init NAME=<name>` | Initialize a new CGF workspace |
| `make optimize` | Run optimization (auto-discovers SPEC.md) |
| `make optimize-dryrun` | Validate setup without running |
| `make cgf-status` | Show active runs and current phase |
| `make cgf-clean` | Clear `sessions/` (keeps research + optimized files) |
| `make cgf-reset` | Destructive — remove all CGF artifacts |
| `/cgf create <description>` | Slash-command to create + optimize a new resource from a description |

### CGF configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CGF_ITERATIONS` | Max iterations per section (single-resource) | `10` |
| `CGF_MAX_ITERATIONS` | Max iterations per resource (multi-resource) | `5` |
| `CGF_QUALITY_THRESHOLD` | Quality target per resource (multi-resource) | `0.85` |
| `CGF_ITERATION_REVIEW` | Pause for review after each iteration | `false` |
| `CGF_EVAL_MODEL` | Eval model: `sonnet` / `haiku` / `opus` | `sonnet` |
| `CGF_VERBOSE` | Show progress output | `true` |

**Deep dive:** [docs/CGF-USER-GUIDE.md](./docs/CGF-USER-GUIDE.md)

---

## Essential Commands

| Command | Description |
|---------|-------------|
| `make interactive` | Start interactive chat |
| `make autonomous` | Start autonomous development |
| `make optimize` | Run CGF optimization |
| `make autonomous-status` | Autonomous progress summary |
| `make cgf-status` | CGF run status |
| `make build` | Build all services |
| `make up` / `make up-multi` | Start services |
| `make down` | Stop everything |
| `make logs` / `make logs-main` | Tail logs |
| `make shell` | Shell into main agent container |
| `make health` | Service health check |
| `make doctor` | Setup diagnostics |

**Tip:** `MODEL=opus make interactive` selects a different model.

### Service Profiles

| Profile | Command | Services |
|---------|---------|----------|
| Default | `make up` | `main-agent`, `prometheus`, `grafana`, `otel-collector`, `alertmanager`, `alertmanager-webhook` |
| Multi-Agent | `make up-multi` | + `agent-two` (read-only evaluator), `agent-three` (validator), `redis` |

Multi-agent mode adds parallel evaluator / validator agents that coordinate via Redis Streams.

---

## Configuration

All configuration goes through `.env` (copy from `.env.example`).

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | (required) |
| `CLAUDE_MODEL` | Claude model to use | `claude-sonnet-4-5-20250929` |
| `CLAUDE_PERMISSION_MODE` | Interactive: `default`, `acceptEdits`, or `bypassPermissions` | `acceptEdits` |
| `AUTONOMOUS_PERMISSION_MODE` | Permission mode for autonomous runs | `bypassPermissions` |
| `CLAUDE_CHECKPOINT_INTERVAL` | Auto-checkpoint cadence (seconds) | `3600` |
| `AGENT_CPU_LIMIT` / `AGENT_MEMORY_LIMIT` | Per-container resource limits | `4` / `8G` |
| `ENABLED_PLUGINS` | Comma-separated plugin allowlist (empty = all) | _empty_ |
| `SWE_MARKETPLACE_REF` | Pin marketplace to a tag/SHA/branch (empty = HEAD) | _empty_ |
| `LOG_LEVEL` | System-log verbosity: `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | `INFO` |

See [.env.example](./.env.example) for the full list.

### Logging

Three layers, in increasing precedence:

1. **`.env` (persistent default)** — `LOG_LEVEL=INFO` (or `DEBUG` / `WARNING` / `ERROR` / `CRITICAL`). Read at container start; `make down && make up` to apply, no rebuild needed. Affects every mode.
2. **Per-invocation CLI flags** — override `.env` for one run:

   | Flag | Effect |
   |---|---|
   | `--debug` / `-d` | Forces `DEBUG` plus raw SDK message dumps and the per-turn stats table |
   | `--quiet` / `-q` | Forces `CRITICAL` (silences everything below) |

   `--debug` wins if both are set.

3. **Makefile shortcuts**:

   | Command | Effect |
   |---|---|
   | `make interactive` | Uses `.env` (`LOG_LEVEL=INFO` by default) |
   | `make interactive-debug` | Passes `--debug` |
   | `make autonomous` | Passes `--quiet` (autonomous always runs quiet by design) |

**Cheat sheet:**
- Always-quiet sessions → `LOG_LEVEL=WARNING` in `.env`
- One-off troubleshooting → `make interactive-debug`
- Total silence → `python -m harness.interactive --quiet` (from inside the container)

### SSH Keys (for private repositories)

```bash
make ssh-init             # Initialize SSH directory
make ssh-keygen-github    # Generate dedicated GitHub key
make ssh-keygen-gitlab    # Generate dedicated GitLab key
make ssh-test             # Test connections (also seeds known_hosts)
```

Keys are dedicated to this project and mounted read-only into containers.

---

## Working with Plugins

The harness loads Claude Code plugins from two sources:

1. **In-tree** at `src/harness/plugins/` — only `cgf-agents` lives here today (the harness's own optimization pipeline, tightly coupled to internals).
2. **swe-marketplace** at <https://github.com/andisab/swe-marketplace> — cloned into `/opt/plugins/swe-marketplace` at image build time, and into `.plugins/swe-marketplace` locally on demand.

### Available plugins

| Plugin | Source | Agents | Skills | Purpose |
|--------|--------|--------|--------|---------|
| `cgf-agents` | in-tree | 9 | 1 | CGF prompt optimization pipeline |
| `context-engineering` | swe-marketplace | 1 | 8 | Agent / skill / command / plugin / MCP-tool authoring toolkit |
| `research-team` | swe-marketplace | 2 | 2 | Multi-agent research with Joplin integration |

Boot log shows what loaded:

```
[info] Plugin discovery complete plugins=['research-team', 'context-engineering', 'cgf-agents'] agents=12 skills=10
```

### Selecting plugins

Set `ENABLED_PLUGINS` in `.env` to a comma-separated list. Empty (or unset) loads everything discovered:

```dotenv
ENABLED_PLUGINS=research-team,context-engineering,cgf-agents
```

### Marketplace clone management

```bash
make plugins-sync                              # Clone or fast-forward .plugins/swe-marketplace
make plugins-sync SWE_MARKETPLACE_REF=v1.2.0   # Pin to a tag / SHA / branch
```

Idempotent: clones on first run, then either fast-forwards the default branch (no pin) or checks out the requested ref. Per-plugin `.claude-plugin/plugin.json` shims are regenerated by `scripts/synthesize_marketplace_manifests.py`.

The container image bakes in whatever `SWE_MARKETPLACE_REF` was set during `make build`. **Rebuild after changing the pin** to update the container's marketplace version.

### Pin policy

```dotenv
SWE_MARKETPLACE_REF=          # HEAD of default branch (dev convenience)
SWE_MARKETPLACE_REF=v1.2.0    # Tag pin (recommended for prod / CI)
SWE_MARKETPLACE_REF=ef72814   # SHA pin (most precise)
```

### Plugin layout

Each plugin follows the Claude Code convention:

```
my-plugin/
├── .claude-plugin/plugin.json   # Manifest (validate: claude plugin validate <dir>)
├── agents/*.md                   # Sub-agent definitions
├── skills/<name>/SKILL.md        # Skills
├── commands/*.md                 # Slash commands
└── hooks/hooks.json              # Lifecycle hooks
```

Common manifest gotchas: `agents` is an array of file paths, not a parent dir; `skills` is an array of subdirectory paths; `repository` is a string URL; `dependencies` is an array; `author` is `{name, email?, url?}`.

### Authoring new plugins

The canonical home for shared plugins is **swe-marketplace** — open a PR there. The pipeline-specific `cgf-agents` stays in-tree.

To scaffold from inside an interactive session, ask the `context-engineering:plugin-dev` skill or `context-engineering:context-engineer` agent.

---

## Working with External Repositories

Clone external repos to `/workspace/projects/`:

```bash
make shell
cd /workspace/projects
git clone https://github.com/user/your-repo.git
```

For autonomous mode on an external repo, add a `branch:` field to its `SPEC.md`:

```markdown
# Project: Add Authentication

branch: casdk-auth-feature

## Requirements
...
```

The runner will create the branch and work on it.

---

## Monitoring

The harness ships a self-contained OTel + Prometheus + Grafana + AlertManager stack. SDK telemetry (`claude_code_*`) flows through an OTel Collector sidecar; harness metrics (`harness_*`, `cgf_*`) are scraped directly. Two dashboards and a set of alert rules are pre-provisioned.

| Service | URL | Purpose |
|---------|-----|---------|
| **Grafana** | <http://localhost:3000> | Dashboards (default login: `admin` / `${GRAFANA_PASSWORD:-changeme123}`) |
| **Prometheus** | <http://localhost:9090> | Metrics + alert rule status |
| **AlertManager** | <http://localhost:9093> | Alert routing + silences |

```bash
make logs           # All logs
make logs-main      # Main agent only
make health         # Service health
make metrics        # Open Grafana
make prometheus     # Open Prometheus
```

**Full guide:** [docs/REFACTOR.md § Observability](./docs/REFACTOR.md#4-observability) — architecture, the two dashboards (overview + CGF), how to add alert rules, first-response actions, and how to wire a real receiver (Slack / email / PagerDuty).

---

## Long-Running Sessions

- **Checkpoints** — Saved hourly, last 5 retained.
- **Recovery** — Run `make autonomous` again to resume from the latest checkpoint.
- **macOS** — `caffeinate -s &` prevents sleep during long runs.

---

## Troubleshooting

Run `make doctor` for automated diagnostics.

### Quick decision tree

```
Agent not responding?
├─ 60s timeout? → Invalid permission mode (use: acceptEdits, bypassPermissions, default)
├─ No output? → Missing PYTHONUNBUFFERED=1 in Dockerfile
├─ Container restarting? → docker compose logs main-agent
└─ Slow / partial messages? → Check resource limits in .env
```

### Common issues

| Problem | Solution |
|---------|----------|
| Container won't start | `docker info` — is Docker running? |
| 60s timeout on startup | Invalid `CLAUDE_PERMISSION_MODE` in `.env` |
| API key invalid | Key must start with `sk-ant-` |
| Port already in use | `make down`, or `lsof -i :8080` |
| Build failures | `make build-no-cache` |
| Out of memory | `AGENT_MEMORY_LIMIT=16G` in `.env` |
| High API costs | Use `MODEL=haiku make interactive` |
| Checkpoint not loading | `rm -rf memory/checkpoints/*` for a fresh start |
| `make optimize` errors with multiple SPEC.md | Keep exactly one `SPEC.md` under `workspace/` |

### Debug commands

```bash
make doctor          # Automated diagnostics
make logs            # All service logs
make logs-main       # Main agent only
make health          # Service health
make shell           # Shell into container
docker stats         # Resource usage
```

### Getting help

1. Run `make doctor` — catches most common problems.
2. Check `make logs` — usually reveals the issue.
3. See [CLAUDE.md](./CLAUDE.md) for architecture and deeper troubleshooting.

---

## Resources

### Project documentation

- [QUICKSTART.md](./QUICKSTART.md) — 5-minute setup
- [CLAUDE.md](./CLAUDE.md) — Technical reference (architecture, CGF internals, configuration, gotchas)
- [docs/CGF-USER-GUIDE.md](./docs/CGF-USER-GUIDE.md) — CGF deep dive
- [docs/REFACTOR.md](./docs/REFACTOR.md) — Reorganization status, observability operator guide, hardening priorities
- [docs/ORCHESTRATION_PATTERNS.md](./docs/ORCHESTRATION_PATTERNS.md) — Multi-agent orchestration patterns reference
- [docs/examples/](./docs/examples/) — Spec templates

### Anthropic engineering references

Primary design influences for the harness — long-running agent design, harness architecture, and reference implementations:

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic engineering blog post on what makes long-running agent harnesses work in practice
- [Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) — Companion piece on architectural patterns for long-running agent applications
- [`anthropics/claude-quickstarts` — autonomous-coding](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) — Anthropic's reference autonomous coding agent quickstart
- [`anthropics/cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents) — Code-with-Claude long-running agent examples and patterns

### Anthropic SDK documentation

- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk/overview)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)

---

**Author**: Andis A. Blukis ([@andisab](https://github.com/andisab))

MIT License
