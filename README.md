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
git clone https://github.com/andisab/ab-casdk-harness.git
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

See [docs/examples/SPEC.example.md](./docs/examples/SPEC.example.md) for spec writing best practices.

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

## CGF Prompt Optimization

The ContextGrad Framework (CGF) optimizes agent prompts through a two-phase workflow: interactive Q&A to gather requirements, then autonomous optimization.

### Quick Start

```bash
# Initialize a CGF workspace
make cgf-init NAME=my-agent

# Copy your resource file and edit SPEC.md
cp path/to/agent.md workspace/my-agent/my-agent.md

# Run optimization (auto-discovers SPEC.md)
make optimize

# Validate setup without running
make optimize-dryrun
```

### How It Works

**Two-Phase Workflow:**

1. **Q&A Phase** (`cgf-initializer` agent):
   - Analyzes the resource file
   - Asks 4 clarifying questions about optimization goals
   - Generates `cgf_spec.yaml` specification
   - Supports resume if interrupted

2. **Optimization Phase** (`cgf-orchestrator` agent):
   - Runs autonomously using the spec
   - Researches domain best practices
   - Generates test cases and criteria
   - Optimizes with LLM self-critique
   - Produces versioned output with review

### Commands

| Command | Description |
|---------|-------------|
| `make cgf-init NAME=<name>` | Initialize new CGF workspace |
| `make optimize` | Run optimization (auto-discovers SPEC.md) |
| `make optimize-dryrun` | Validate setup |
| `make cgf-status` | Show optimization run status |
| `make cgf-clean` | Remove run state files |
| `make cgf-reset` | Full reset (remove all workspaces) |
| `/cgf create <description>` | Create + optimize new resource |

### Output

Results saved to `workspace/{agent}/`:
- `CHANGELOG.md` - Human-readable optimization history (accumulates)
- `cgf_spec.yaml` - Optimization specification (from Q&A)
- `{agent}-v1.md` - Optimized version
- `reviews/v1_review.md` - Evaluation report
- `research/eval_criteria.yaml` - Evaluation criteria
- `sessions/` - Runtime state (delete to reset)

For detailed documentation on resource types, goal writing, and troubleshooting, see [docs/features/CGF-USER-GUIDE.md](./docs/features/CGF-USER-GUIDE.md).

### Multi-Resource Optimization

Generate and optimize entire plugins, skill-sets, or workflows from a single SPEC.md:

```bash
# Create a multi-resource SPEC.md
mkdir -p workspace/my-plugin
cp docs/examples/MULTI_RESOURCE_SPEC.example.md workspace/my-plugin/SPEC.md

# Run optimization (auto-discovers and detects multi-resource)
make optimize
```

**Pipeline:** RESEARCH → Q&A → GENERATE → ITERATE → VALIDATE → COMPLETE

Each phase delegates to specialized agents:
- **RESEARCH**: `cgf-research-lead` gathers domain best practices
- **GENERATE**: `context-engineer` creates each resource
- **ITERATE**: `cgf-prompt-optimizer` improves until quality >= 0.85
- **VALIDATE**: `cgf-coherence-validator` checks cross-resource consistency

See [docs/examples/MULTI_RESOURCE_SPEC.example.md](./docs/examples/MULTI_RESOURCE_SPEC.example.md) for template.

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CGF_ITERATIONS` | Max optimization iterations | `10` |
| `CGF_ITERATION_REVIEW` | Pause for review each iteration | `false` |
| `CGF_EVAL_MODEL` | Eval model (`sonnet`/`haiku`/`opus`) | `sonnet` |
| `CGF_VERBOSE` | Show progress output | `true` |

---

## Working with Plugins

The harness loads Claude Code plugins from two sources at runtime:

1. **In-tree** at `src/harness/plugins/` — only `cgf-agents` lives here today (the harness's own optimization pipeline).
2. **swe-marketplace** — a separate plugin marketplace at <https://github.com/andisab/swe-marketplace>. Cloned into `/opt/plugins/swe-marketplace` inside the container at build time and into `.plugins/swe-marketplace` locally on demand.

### Available plugins

| Plugin | Source | Agents | Skills | Purpose |
|---|---|---|---|---|
| `cgf-agents` | in-tree | 9 | 1 | CGF (Claude Gradient Feedback) prompt optimization pipeline |
| `context-engineering` | swe-marketplace | 1 | 8 | Agent / skill / command / plugin / MCP-tool authoring toolkit |
| `research-team` | swe-marketplace | 2 | 2 | Multi-agent research with Joplin integration |

The boot log lists exactly what loaded:

```
[info] Plugin discovery complete plugins=['research-team', 'context-engineering', 'cgf-agents'] agents=12 skills=10
```

### Choosing which plugins load

Set `ENABLED_PLUGINS` in `.env` to a comma-separated list of plugin names. Empty (or unset) loads every discovered plugin from both sources, which can be noisy — pin to what you actually use:

```dotenv
ENABLED_PLUGINS=research-team,context-engineering,cgf-agents
```

### swe-marketplace clone management

Local development:

```bash
make plugins-sync          # Clone or fast-forward .plugins/swe-marketplace
make plugins-sync SWE_MARKETPLACE_REF=v1.2.0   # Pin to a tag/SHA/branch
```

The Makefile target is idempotent: it clones on first run, and on subsequent runs fetches and either fast-forwards the default branch (no pin) or checks out the requested ref. After update it regenerates per-plugin `.claude-plugin/plugin.json` shims via `scripts/synthesize_marketplace_manifests.py`.

The container image clones marketplace at build time (`make build`), pinned to whatever `SWE_MARKETPLACE_REF` was set during the build. This means **the image's marketplace version is independent of your local `.plugins/` clone** — rebuild after changing the pin to get it into the container.

### Pin policy

For reproducible deployments, set `SWE_MARKETPLACE_REF` to a tag or commit SHA in `.env`. Empty (`SWE_MARKETPLACE_REF=`) tracks the marketplace's default branch HEAD — convenient for development, but reruns can pick up unrelated upstream changes.

```dotenv
SWE_MARKETPLACE_REF=          # HEAD of default branch (default for dev)
SWE_MARKETPLACE_REF=v1.2.0    # Tag pin (recommended for prod / CI)
SWE_MARKETPLACE_REF=ef72814   # SHA pin (most precise)
```

Bump deliberately: when the upstream marketplace ships a release you want, edit the `.env` value and rerun `make plugins-sync && make build`.

### Path resolution

`SWE_MARKETPLACE_PATH` overrides the auto-detect. Auto-detection order (when unset):

1. `/opt/plugins/swe-marketplace` — container default, populated at build time
2. `<repo-root>/.plugins/swe-marketplace` — local dev, populated by `make plugins-sync`

If neither exists, marketplace plugins are skipped (a log line says so). The harness still loads any in-tree plugins.

### Plugin layout

Each plugin follows the Claude Code convention:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json     # Manifest. Validate with: claude plugin validate <plugin-dir>
├── agents/*.md         # Sub-agent definitions (one per file)
├── skills/<name>/SKILL.md   # Skills (one subdirectory per skill)
├── commands/*.md       # Slash commands
└── hooks/hooks.json    # Lifecycle hooks
```

`plugin.json` schema is enforced by `claude plugin validate`. Common gotchas:
- `agents` is an array of file paths (`./agents/foo.md`), not a parent directory.
- `skills` is an array of subdirectory paths (`./skills/foo`).
- `repository` is a string URL; `dependencies` is an array; `author` is an object `{name, email?, url?}`.

### Authoring new plugins

The canonical home for shared plugins is **swe-marketplace** — open a PR there. The harness's own pipeline-specific plugin (`cgf-agents`) stays in-tree because it's tightly coupled to harness internals.

To scaffold from inside an interactive session, ask the `context-engineering:plugin-dev` skill or `context-engineering:context-engineer` agent.

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

The harness ships a self-contained OTel + Prometheus + Grafana + AlertManager stack.
SDK telemetry (`claude_code_*`) flows through an OTel Collector sidecar; harness
metrics (`harness_*`, `cgf_*`) are scraped directly. Two dashboards and a set of
alert rules are pre-provisioned.

| Service | URL | Purpose |
|---------|-----|---------|
| **Grafana** | http://localhost:3000 | Dashboards (default login: `admin` / `${GRAFANA_PASSWORD:-changeme123}`) |
| **Prometheus** | http://localhost:9090 | Metrics + alert rule status |
| **AlertManager** | http://localhost:9093 | Alert routing + silences |

```bash
make logs           # View all logs
make logs-main      # View main agent logs
make health         # Check service health
```

**Full guide:** [docs/REFACTOR.md § Observability](./docs/REFACTOR.md#4-observability) covers architecture,
the two dashboards (overview + CGF), how to add alert rules, first-response actions
for each rule, and how to wire a real receiver (Slack/email/PagerDuty).

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
