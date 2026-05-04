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
- **30 total agents** (17 harness + 13 plugin) via direct invocation
- **11 plugin skills** (9 context-engineering + 1 cgf-agents + 1 research-team)
- **CGF Optimization Framework** (1,585 passing tests):
  - Phase 0: Infrastructure (tracer, store, adapters, rewards)
  - Phase 1: Single-agent optimization (test cases, runners, agentic optimizer, CLI)
  - Phase 2: Section-based optimization (agentic, coherence)
  - Stage 1: Protocol layer, resource architect agent, DESIGN phase
  - Stage 2: MCP tool/server creation skills + Python/TypeScript scaffolds

### Completed Recently
- **Block 2 Part 2 Phase 1 — Filesystem Agent Discovery (2026-05-04)** — moved 14 agent configs from `src/harness/agents/configs/*.md` to canonical `.claude/agents/*.md`; `definitions.py` and `ResourceRegistry.discover()` repointed to new path; `setting_sources` narrowed `["user","project"]` → `["project"]` for container hermeticity; Dockerfile copies `.claude/` in dev + production stages; YAML `model: opus 4.1` normalized to canonical `opus` (12 files) — hidden by `MODEL_MAP` translation pre-Phase-1, but exposed by filesystem auto-discovery reading raw YAML. Unit tests 1591/0/0 unchanged. Runtime smoke verified single-call Task dispatch to `python-expert`. Latent name-mismatch issues (4 files where YAML `name:` differs from programmatic aliases) deferred to Phase 3 cleanup — see REFACTOR.md.
- **Block 2 Part 2 Phase 0 — SDK Bump + Task-Tool Verification (2026-05-04)** — `claude-agent-sdk` pinned `>=0.1.72` (was `>=0.1.0`, resolved to 0.1.12). Unit suite unchanged at 1591/0/0. **Runtime smoke verified**: `make interactive` → `Task(subagent_type="python-expert", ...)` returned a real response (`ResultMessage(is_error=False, num_turns=2)`), confirming issue #12212 is fixed for this harness. `ClaudeAgentOptions.skills=` parameter confirmed present (closes REFACTOR.md Risk #6). Unblocks Phases 1-3 (filesystem agent discovery, plugin_manager collapse, direct_agent.py retirement).
- **Block 1 — Branch Reorganization (2026-05-01/02)** — 73 commits from `contextgrad-framework` promoted to `main` via PR #1. Branches now equal. `contextgrad-framework` reset as a slim branch off `main` for forthcoming Stage 3-4 eval-harness work. See [docs/REFACTOR.md](./docs/REFACTOR.md) for the full reorganization spec.
- **Stage 2: MCP Tool/Server Creation Skills (2026-03-26)**
  - [x] `mcp-tool-creation` and `mcp-server-creation` skills with references/
  - [x] Full Python and TypeScript MCP server scaffolds in templates/
  - [x] GENERATE phase delegates MCP types to `context-engineer`
- **Stage 1: Protocol Layer + Resource Architect (2026-03-02)**
  - [x] Shared protocol layer: signals, resource types, quality scoring, state, workspace
  - [x] Resource architect agent (opus model) for SPEC → resource plan decisions
  - [x] DESIGN phase between RESEARCH and QA in multi-resource pipeline
  - [x] MCP tool/server types in SPEC parser (ProposedMCPTool, ProposedMCPServer)
  - [x] Extended OptimizationPhase enum (6 → 9 phases: +DESIGN, EVAL_DESIGN, EXECUTION_EVAL)
  - [x] Orchestrator refactored to use SignalParser protocol
  - [x] resource_plan.schema.json and resource-plan.yaml output

### Known Limitations
- Grafana overview dashboard is placeholder (stub file) — handled by REFACTOR.md Part 3C
- AlertManager not configured (alerting rules defined but unused) — handled by REFACTOR.md Part 3D
- `harness.direct_agent` module (781 LoC) is still in active use as a Task-tool workaround predating SDK 0.1.72. Retirement is REFACTOR.md Part 2 Phase 3 (Task dispatch verified working under 0.1.72 — see Phase 0 entry below).

### TODOs
- [ ] Configure AlertManager in docker-compose for `alerting.yml` rules → REFACTOR.md Part 3D
- [ ] Remove postgres exporter target from `prometheus.yml` (service doesn't exist) → REFACTOR.md Part 3D
- [ ] **Block 2 next:** Part 2 Phase 2 — collapse `plugin_manager.py` to <80 LoC; delete `src/harness/commands.py`; slim `hooks.py`; rename `PostSessionStart`→`SessionStart`, `STOP`→`Stop` (see REFACTOR.md)

### Recent fixes (2026-05-02)
- ✓ All 5 pre-existing unit test failures fixed (1585 → 1591 passed, 0 failed). See REFACTOR.md Part 1E for the fix-by-fix breakdown. One of these (`9bf5a28`) was a real user-facing bug: `ENABLED_PLUGINS=` (empty) in `.env` previously caused zero plugins to load.

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
│   │   └── agents/definitions.py   # Loads from .claude/agents/ (REFACTOR Part 2 Phase 1)
│   │   ├── prompts/                # 5 prompt files (3 container + 2 autonomous)
│   │   ├── plugins/                # 3 plugins (cgf-agents, context-engineering, research-team)
│   │   ├── skills/                 # 6 base skills
│   │   ├── optimization/           # CGF optimization framework
│   │   │   ├── cli/                # section_optimize.py (section-based optimization CLI)
│   │   │   ├── analysis/           # competency_mapper, coherence, synthesizer
│   │   │   ├── optimizers/         # agentic optimizer
│   │   │   ├── testcases/          # loader, validators, models
│   │   │   ├── runners/            # agent_runner, batch_runner
│   │   │   ├── protocols/          # Shared protocol layer (signals, types, quality, state, workspace)
│   │   │   ├── resources/          # agent, prompt, skill resources
│   │   │   ├── orchestrator.py     # Section-based optimization
│   │   │   ├── multi_resource_spec.py      # Multi-resource SPEC parser
│   │   │   ├── multi_resource_orchestrator.py  # Multi-resource pipeline
│   │   │   └── quality_evaluator.py        # Agentic quality assessment
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

## Core Harness

### Execution Modes

#### Interactive vs Autonomous Mode

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

#### Mode Comparison

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

#### Key Module Details

- **agent.py** (`AgentSession`): SDK lifecycle (start, execute, shutdown), MCP server registration (5 servers), automatic checkpointing, metrics collection, retry logic with exponential backoff
- **autonomous.py**: `AutonomousRunner` + `ProgressManager` classes. Workspace state detection (6 states), Tech Lead Q&A with resume (`qa_session.json`), completion signal parsing, configurable delay, external repo support with `casdk-` branch naming
- **checkpoint.py**: Auto-save every hour (configurable via `CLAUDE_CHECKPOINT_INTERVAL`), keeps last 5 checkpoints (`CHECKPOINT_KEEP_COUNT`), atomic writes with file locking, recovery from latest on startup

#### Autonomous Mode Workflow

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

### Multi-Agent System

#### Agent Types

| Type | Location | Invocation | Process |
|------|----------|------------|---------|
| **Subagents** | `.claude/agents/*.md` | `harness.direct_agent` | Same process |
| **Plugin Agents** | `src/harness/plugins/*/agents/*.md` | `harness.direct_agent` | Same process |
| **Container Agents** | `docker-compose.yml` services | Docker | Separate containers |

#### Subagents (14 harness + 13 plugin)

Invoked via `harness.direct_agent` module (Task tool has SDK bug):

**Harness Agents** (14):
| Category | Agents |
|----------|--------|
| **Development** (7) | python-expert, typescript-expert, go-expert, nodejs-expert, react-expert, refactor-agent, code-review-expert |
| **Database** (2) | database-expert, sql-expert |
| **Infrastructure** (4) | docker-engineer, k8s-engineer, gcp-architect, gitlab-ci-expert |
| **Testing** (1) | sdet-expert |

**Plugin Agents** (13):
| Plugin | Agents |
|--------|--------|
| **cgf-agents** (9) | cgf-orchestrator, cgf-research-lead, cgf-test-architect, cgf-test-validator, cgf-criteria-synthesizer, cgf-result-evaluator, cgf-prompt-optimizer, cgf-coherence-validator, cgf-resource-architect |
| **context-engineering** (1) | context-engineer |
| **research-team** (3) | lead-research-coordinator, research-specialist, research-report-writer |

**Definition files**: `.claude/agents/` with YAML frontmatter:
```markdown
---
name: python-expert
description: Python/FastAPI/async development
model: sonnet
tools: Read, Write, Bash, mcp__context7
---
System prompt content...
```

#### Direct Agent Invocation

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

#### Plugin System

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

**Resource Types:**

| Type | Count | Invocation | Status |
|------|-------|------------|--------|
| Harness Agents | 14 | `harness.direct_agent.call_agent()` | Working |
| Plugin Agents | 13 | `harness.direct_agent.call_agent()` | Working |
| Base Skills | 6 | `Skill(skill="...")` | Working |
| Plugin Skills | 7 | `Skill(skill="plugin:name")` | Working |
| Commands | 2 | CommandRegistry | Working |
| Hooks | 2 | HookRegistry | Working |

**Plugins** (3 total):

- **cgf-agents** (`src/harness/plugins/cgf-agents/`): 1 skill (cgf-optimize), 1 command (cgf: create, optimize, status). Dependencies: context-engineering, research-team. Orchestrates multi-agent optimization workflows.
- **context-engineering** (`src/harness/plugins/context-engineering/`): 8 skills (agent-definition-creation, skill-creation, plugin-development, command-creation, hook-configuration, resource-optimization, mcp-tool-creation, mcp-server-creation). Hook configuration for lifecycle events. MCP tool/server templates (Python + TypeScript).
- **research-team** (`src/harness/plugins/research-team/`): 1 skill (joplin-research), 1 command (research).

**Namespacing**: All plugin resources use `plugin-name:resource-name` format (e.g., `context-engineering:skill-creation`, `cgf-agents:cgf`).

**Commands** (`commands.py`): CommandRegistry with argument substitution ($1, $2, $ARGUMENTS, $FILE), namespaced and short-name lookups.

**Hooks** (`hooks.py`): HookRegistry with async/sync execution modes, pattern matching (tool_name, file_path globs), timeout handling.

| Event | Triggered | Purpose |
|-------|-----------|---------|
| PostSessionStart | After start() | Post-init actions |
| STOP | Before shutdown() | Cleanup actions |
| PreToolUse | Before tool call | Tool filtering (defined, not triggered) |
| PostToolUse | After tool call | Post-processing (defined, not triggered) |

#### Container Agents

Enabled with `make up-multi`:

| Service | Permission | Workspace | Prompt |
|---------|------------|-----------|--------|
| main-agent | acceptEdits | Read-write | `main-interactivedev-agent.md` |
| agent-two | default | **Read-only** | `agent-two.md` |
| agent-three | bypassPermissions | Read-write | `agent-three.md` |

Container agents communicate via Redis Streams (`src/harness/messaging.py`).

**Docker Profiles:**
```bash
make up       # Default: main-agent (8080, metrics 9091), prometheus (9090), grafana (3000, admin/admin)
make up-multi # Adds: agent-two (8081), agent-three (8082), redis (6379)
```

#### Architecture Diagram

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

### Working Environment

When running inside the harness container:

#### Directory Layout
- **`/app`** - System configuration (READ-ONLY, agent cwd)
- **`/workspace`** - Development work directory (READ-WRITE)
  - `/workspace/projects/` - Clone external repos here
  - `/workspace/context/` - Technical context files
- **`/memory`** - Persistent state (checkpoints, knowledge graph)
- **`/logs`** - Structured application logs
- **`/config`** - Prometheus/Grafana configs

**Important**: All development work must use `/workspace` with absolute paths.

#### Available Tools

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

#### Prometheus Metrics

Exposed on port 9090 (`monitoring.py`):
- `agent_requests_total{agent, status}` - Request counter
- `agent_duration_seconds{agent}` - Request histogram
- `api_tokens_used_total{model, type}` - Token counter
- `api_cost_dollars_total{model}` - Cost counter
- `interactive_tool_calls_total{agent, tool_name, status}` - Tool call counter

### Configuration Reference

#### Required
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

#### Agent Settings
```bash
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_PERMISSION_MODE=acceptEdits  # default, acceptEdits, bypassPermissions
CLAUDE_MAX_TURNS=1000
CLAUDE_CHECKPOINT_INTERVAL=3600     # seconds
```

#### Autonomous Mode
```bash
AUTONOMOUS_PERMISSION_MODE=bypassPermissions
AUTONOMOUS_DELAY_SECONDS=5          # Note: .env.example shows 3, code default is 5
AUTONOMOUS_MAX_SESSIONS=100
AUTONOMOUS_TASK_TIMEOUT=1800        # 30 minutes
```

#### Resources
```bash
AGENT_CPU_LIMIT=4
AGENT_MEMORY_LIMIT=8G
```

#### Plugin Settings
```bash
ENABLED_PLUGINS=context-engineering,research-team  # Comma-separated (empty = all)
PLUGIN_USE_SDK_ONLY=false                          # Disable workarounds when SDK fixed
```

**Python defaults** (`config.py`):
```python
claude_model = "claude-sonnet-4-5-20250929"
interactive_permission_mode = "acceptEdits"
autonomous_permission_mode = "bypassPermissions"
claude_max_turns = 1000
claude_checkpoint_interval = 3600  # 1 hour
autonomous_delay_seconds = 5
```

See [.env.example](/.env.example) for complete list.

---

## CGF Optimization Framework

The ContextGrad Framework (CGF) provides prompt optimization using **agentic (LLM-based) optimization**. It uses LLM self-critique and research heuristics. No test suite required.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CGF OPTIMIZATION ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────-──────────────┐  │
│  │                      PRE-OPTIMIZATION SETUP                               │  │
│  │                                                                           │  │
│  │  1. Load Agent ───────────► workspace/AGENT/AGENT.md                      │  │
│  │  2. Generate Tests ───────► cgf-test-architect → tests/tests.yaml         │  │
│  │  3. Generate Criteria ────► cgf-criteria-synthesizer → eval_criteria.yaml │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                              │
│                                  ▼                                              │
│  ┌─────────────────────────────────────────────────────────-─────────────────┐  │
│  │                   FIVE-PHASE ORCHESTRATION                                │  │
│  │  orchestrator.py (SectionOptimizer)                                       │  │
│  │                                                                           │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌──────────┐       │  │
│  │  │ ANALYZE │→ │  PLAN   │→ │ EXECUTE │→ │ SYNTHESIZE│→ │ VALIDATE │       │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └─────┬─────┘  └────┬─────┘       │  │
│  │       │            │            │             │              │            │  │
│  │   Load agent   Create      Run optimizer  Merge sections  Full suite      │  │
│  │   Load tests   focused     per section    Coherence pass  validation      │  │
│  │   Map tests→   test        Cross-section  Auto-reorder    Rollback on     │  │
│  │   competencies suites      regression     (if enabled)    regression      │  │
│  │   Set eval_model           detection                                      │  │
│  └───────────────────────────────────────────────────────────────────────-───┘  │
│                                     │                                           │
│              ┌──────────────────────┼──────────────────────┐                    │
│              ▼                                             ▼                    │
│  ┌────────────────────────────┐              ┌────────────────┐                 │
│  │         AGENTIC            │              │    PRESERVE    │                 │
│  │      (qualitative)         │              │  (no coverage) │                 │
│  │                            │              │                │                 │
│  │  Self-critique LLM-based   │              │  Keep original │                 │
│  │  improvement               │              │  section       │                 │
│  └────────────────────────────┘              └────────────────┘                 │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────-──┐  │
│  │                      VALIDATORS & EVAL MODEL                              │  │
│  │                                                                           │  │
│  │  Deterministic:                    LLM-Based:                             │  │
│  │    exact, contains, regex            llm_judge                            │  │
│  │    code, code_syntax                 code_llm                             │  │
│  │                                                                           │  │
│  │  Eval Model (default: Sonnet): LLMJudgeValidator, CodeLLMValidator        │  │
│  │    Override: --eval-model haiku/sonnet/opus                               │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────-───┐  │
│  │                      ANALYSIS & SYNTHESIS                                 │  │
│  │                                                                           │  │
│  │  competency_mapper.py ──► Map tests → competencies → sections             │  │
│  │  test_subset.py ────────► Create focused test suites per section          │  │
│  │  synthesizer.py ────────► Merge optimized sections into final prompt      │  │
│  │  coherence.py ──────────► Detect inversions, reorder for flow             │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Optimization Strategies

| Strategy | Trigger | Optimizer | Validators |
|----------|---------|-----------|------------|
| **AGENTIC** (default) | Default mode, no tests required | Self-critique LLM | llm_judge, code_llm (optional) |
| **PRESERVE** | No test coverage for section | None | - |

**Agentic**: Uses research heuristics + LLM self-critique. No test suite needed.

### Eval Model Configuration

The eval model is used by `LLMJudgeValidator` and `CodeLLMValidator` for test scoring:

| Model | ID | Use Case |
|-------|-----|----------|
| **Sonnet** (default) | `claude-sonnet-4-20250514` | Balance of speed and quality |
| Haiku | `claude-3-5-haiku-20241022` | Fastest/cheapest evaluation |
| Opus | `claude-opus-4-5-20250929` | Highest quality evaluation |

Override via `--eval-model` CLI flag or `EVAL_MODEL` env var.

### Make Targets

The unified entry point `make optimize` runs in Docker (like `make autonomous`) and provides a two-phase workflow:
1. **Q&A Phase**: Interactive `cgf-initializer` agent gathers optimization requirements
2. **Optimization Phase**: Autonomous `cgf-orchestrator` runs optimization

**Key Principle:** SPEC.md location defines the workspace root. All files are created relative to its location.

**SPEC.md Auto-Discovery:**
- Exactly one SPEC.md must exist in `workspace/`
- If multiple found, an error is thrown (user must delete extras)
- If none found, user is prompted to create one with `make cgf-init`

```bash
# Run optimization (auto-discovers SPEC.md)
make optimize

# Validate setup and show configuration
make optimize-dryrun
```

**Workspace Structure (SPEC.md location = workspace root):**
```
{workspace_root}/                  # Directory containing SPEC.md
├── SPEC.md                        # Optimization spec (user OR Q&A-generated)
├── CHANGELOG.md                   # Human-readable optimization history (accumulates)
├── {resource}.md                  # Original resource (NEVER modified)
├── {resource}-v1.md               # First optimization
├── {resource}-v2.md               # Second optimization (if REFINE)
├── resource-plan.yaml             # Resource plan (created during DESIGN phase)
├── tools/                         # MCP tool definitions (multi-resource)
├── mcp-servers/                   # MCP server definitions (multi-resource)
├── eval/                          # Evaluation suites and results
├── research/                      # Created during RESEARCH phase
│   ├── notes/
│   │   └── *.yaml                 # Research findings
│   ├── eval_criteria.yaml         # Evaluation criteria
│   └── reviews/                   # Created during EVALUATE phase
│       └── v1_review.md
└── sessions/                      # Runtime state (delete to reset)
    ├── task_list.json             # Phase tracking
    ├── qa_session.json            # Q&A history
    └── *.summary.json             # Machine-readable summaries (for debugging)
```

**File Naming:**
| Resource Type | Original | Optimized Versions |
|---------------|----------|-------------------|
| Agent | `{name}.md` | `{name}-v1.md`, `{name}-v2.md` |
| Skill | `SKILL.md` | `SKILL-v1.md`, `SKILL-v2.md` |
| Command | `{name}.md` | `{name}-v1.md`, `{name}-v2.md` |

**The original file is NEVER modified.** Delete `sessions/` to reset state without losing artifacts.

**Configuration** (`.env` or command line):
```bash
# Optimization settings
CGF_ITERATIONS=10             # max optimization iterations per section
CGF_ITERATION_REVIEW=false    # pause for review after each iteration
CGF_EVAL_MODEL=sonnet         # sonnet (default), haiku, or opus
CGF_VERBOSE=true              # show progress output
```

**Q&A Flow Example:**
```
$ make optimize

Discovering SPEC.md in workspace...
Found: workspace/python-expert/SPEC.md

CGF Optimization Q&A
====================

[cgf-initializer] Analyzing resource: python-expert.md
[cgf-initializer] Detected: Agent (705 lines, 12 sections)

Question 1/4: What do you want to improve?
> Better async/await patterns and error handling

Question 2/4: Focus on specific sections? (2, 3, 5 or "all")
> 2, 3, 5

Question 3/4: Review after each iteration? (y/n)
> y

Question 4/4: Number of iterations? (default: 10)
> 5

[cgf-initializer] Saved: workspace/python-expert/cgf_spec.yaml
[SPEC_READY]

CGF Optimization Phase
======================
Goal: Better async/await patterns and error handling
Iterations: 5 | Review: enabled

[cgf-orchestrator] Starting optimization...
```

### Quick Start

```bash
# Initialize a new CGF workspace with template SPEC.md
make cgf-init NAME=my-agent

# Copy your resource file
cp path/to/agent.md workspace/my-agent/my-agent.md

# Edit SPEC.md with your optimization goals
# Then run optimization
make optimize
```

See `docs/examples/CGF_SPEC.example.md` for the full template with examples.

### Workspace Management

```bash
# Check optimization status (discovers all workspaces)
make cgf-status

# Clean session state files (keeps research and optimized files)
# Equivalent to: rm -rf workspace/*/sessions/
make cgf-clean

# Remove all CGF artifacts (destructive)
make cgf-reset
```

**Reset Strategies:**
- Delete `sessions/` only → Resume from appropriate phase
- Delete `research/` → Re-run research phase
- `make cgf-clean` → Clear all session states, keep artifacts
- `make cgf-reset` → Full reset (destructive)

### Advanced CLI (Section-Based)

```bash
# Agentic optimization (no test suite needed)
uv run python -m harness.optimization.cli.section_optimize \
  --agent .claude/agents/dev-python-expert.md \
  --criteria workspace/dev-python-expert/research/eval_criteria.yaml \
  --workspace workspace/dev-python-expert \
  --iterations 2 \
  --verbose
```

### Key Files

| File | Purpose |
|------|---------|
| `cli/section_optimize.py` | Section-based optimization CLI |
| `orchestrator.py` | Section optimization orchestrator |
| `analysis/competency_mapper.py` | Map tests → competencies → sections |
| `analysis/coherence.py` | Detect and fix structural issues |
| `analysis/synthesizer.py` | Merge optimized sections |
| `optimizers/agentic_optimizer.py` | Self-critique optimizer |
| `protocols/signals.py` | Signal parsing protocol and registry |
| `protocols/resource_types.py` | Resource type definitions (agent, skill, mcp_tool, mcp_server, etc.) |
| `protocols/quality.py` | Quality scoring models |
| `protocols/state.py` | Optimization state management |
| `protocols/workspace.py` | Workspace path resolution |

### Test Coverage

| Phase | Component | Tests |
|-------|-----------|-------|
| 0.1 | OpenTelemetry Tracing | 97 |
| 0.2 | Optimization Store | 89 |
| 0.3 | Resource Registry | 65 |
| 0.4 | Adapter Framework | 87 |
| 0.5 | Reward System | 50 |
| 0.6 | Integration | 16 |
| 1.0 | Single-Agent Optimization | 1,182 |
| S1 | Protocol Layer + Design Phase | 120 |
| S2 | MCP Resource Generation | 47 |
| **Total** | | **1,785** |

### Orchestration Workflows

**Agentic Mode**:
1. **LOAD**: Load agent, criteria, and research findings
2. **ITERATE**: LLM self-critique (1-3 rounds)
3. **OUTPUT**: Merge sections, run coherence analysis, save

### Creation Mode

Create and optimize new resources from natural language description:

```bash
/cgf create "Python async expert that helps with asyncio patterns"
```

Pipeline: INIT → CREATE (context-engineer) → RESEARCH → DESIGN → RESEARCH_ITERATE → EVALUATE → FINALIZE

### Targeted Refinement

After REFINE recommendation, orchestrator can skip full research and focus on specific sections:

```
RECOMMENDATION: REFINE

TARGET_SECTIONS:
- core_approach
- best_practices

TARGET_COMPETENCIES:
- comp_async_patterns
- comp_error_handling

PRESERVE_SECTIONS:
- role_definition
- constraints

REFINEMENT_HINTS:
- Focus on async/await best practices in core_approach
- Add more error handling examples
```

Max refinement iterations: 3 before escalating to human review.

### Multi-Resource Optimization (Agent Delegation)

For multi-resource SPEC.md files (plugins, skill-sets, workflows), the orchestrator delegates work to specialized agents:

**State Machine:**
```
PLANNING → RESEARCH → DESIGN → GENERATE → ITERATE → VALIDATE → COMPLETE
    │           │         │          │          │           │
    │     cgf-research  cgf-     context-   cgf-prompt  cgf-coherence
    │        -lead      resource  engineer   -optimizer   -validator
    │           │       -architect    │          │           │
    │      [RESEARCH_  [DESIGN_  [GENERATE_  [ITERATE_  [VALIDATE_
    │      COMPLETE]   COMPLETE] COMPLETE]   COMPLETE]  COMPLETE]
```
*Note: EVAL_DESIGN and EXECUTION_EVAL phases exist in the enum for future stages but are not yet orchestrated.*

**Phase-to-Agent Mapping:**

| Phase | Agent | Signal |
|-------|-------|--------|
| PLANNING | None (Python only) | State file created |
| RESEARCH | `cgf-agents:cgf-research-lead` | `[RESEARCH_COMPLETE]` |
| DESIGN | `cgf-agents:cgf-resource-architect` | `[DESIGN_COMPLETE]` |
| GENERATE | `context-engineering:context-engineer` | `[GENERATE_COMPLETE:{path}]` |
| ITERATE | `cgf-agents:cgf-prompt-optimizer` | `[ITERATE_COMPLETE:{path}]` |
| EVALUATE | `cgf-agents:cgf-result-evaluator` | `RECOMMENDATION: ACCEPT/REFINE/REJECT` |
| VALIDATE | `cgf-agents:cgf-coherence-validator` | `[VALIDATE_COMPLETE]` or `[VALIDATE_ISSUES:{count}]` |

**Core Principle:** Python is a thin state coordinator; agents do all the work. Each agent emits structured signals that Python parses to transition state.

**Resume Support:** State tracked in `sessions/optimization-state.json`. Delete to restart; keeps research/artifacts.

---

## Development & Operations

### Development Workflow

#### Git Workflow
```bash
git checkout -b feature/descriptive-name
# Make changes
git commit -m "feat(agent): add retry logic"
git push origin feature/descriptive-name
```

#### Conventional Commits
- `feat(scope):` - New feature
- `fix(scope):` - Bug fix
- `docs(scope):` - Documentation
- `refactor(scope):` - Code restructure
- `test(scope):` - Tests

#### Testing
```bash
make test                # Full test suite
make test-unit           # Fast, no API calls
make test-integration    # Requires API key
make test-multi          # Multi-agent coordination tests
make coverage            # Coverage report
```

#### Code Quality
```bash
make lint       # Check with ruff
make lint-fix   # Auto-fix issues
make typecheck  # Run mypy
make format     # Format code
```

### Troubleshooting

Run `make doctor` for automated diagnostics.

#### Common Gotchas & Solutions

| Problem | Symptom | Root Cause | Solution |
|---------|---------|-----------|----------|
| **0 messages received** | SDK initialization timeout | Python subprocess uses 8KB block buffering in containers (no TTY), messages accumulate unsent | Dockerfile must have `ENV PYTHONUNBUFFERED=1` to force unbuffered stdout |
| **Timeout on initialize** | 60s timeout during startup | Invalid permission mode or MCP server failure | Check `CLAUDE_PERMISSION_MODE` is valid (`acceptEdits`, `bypassPermissions`, `default`) |
| **Process hangs on stop** | Container requires `docker kill` | Shell becomes PID 1, receives SIGTERM but doesn't forward to Python; subprocess never flushes buffers | Dockerfile must have `ENTRYPOINT ["/usr/bin/tini", "--"]` for proper signal forwarding |
| **Partial message loss** | StreamReader truncates output | Default 64KB buffer too small | SDK uses `limit=1024*256` in subprocess |
| **Container restarts fail** | Healthcheck always failing | Health endpoint not responding | Verify port 8080 is exposed and agent started |
| **Cross-container IPC fails** | Subagents can't communicate | Subprocess pipes don't cross containers | Use `--profile multi-agent` for Redis Streams |
| **Permission denied errors** | Tools blocked unexpectedly | `permission_mode` misconfigured | Set `CLAUDE_PERMISSION_MODE=bypassPermissions` for autonomous |
| **API rate limits** | 429 Too Many Requests | Too many concurrent requests | Reduce parallel agent instances |

#### Quick Checks

- Container won't start → `docker info` (is Docker running?)
- API key invalid → Verify `.env` has `sk-ant-` prefix
- Port conflict → `make down` first, or check `lsof -i :8080`

See [README.md#troubleshooting](./README.md#troubleshooting) for user-focused solutions.

### Resources

#### Project Documentation
- [README.md](./README.md) - User-facing documentation
- [QUICKSTART.md](./QUICKSTART.md) - 5-minute setup
- [docs/HARDENING.md](./docs/HARDENING.md) - Production security

#### Claude Agent SDK
- [Agent SDK Overview](https://docs.claude.com/en/api/agent-sdk/overview)
- [Python SDK Reference](https://docs.claude.com/en/docs/agent-sdk/python)
- [MCP in SDK](https://docs.claude.com/en/docs/agent-sdk/mcp)
- [Hosting Guide](https://docs.claude.com/en/docs/agent-sdk/hosting)

#### GitHub Repositories
- [Python SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [SDK Demos](https://github.com/anthropics/claude-agent-sdk-demos)
- [MCP Servers](https://github.com/modelcontextprotocol/servers)

#### Docker Resources
- [tini (init for containers)](https://github.com/krallin/tini)
- [Multi-stage Build Docs](https://docs.docker.com/build/building/multi-stage/)

---

**Maintainer**: Andis A. Blukis (andis.blukis@gmail.com)
**License**: MIT
