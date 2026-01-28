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
- 25 subagents (14 harness + 11 plugin) via direct invocation
- 13 skills via Skill tool (6 base + 7 plugin)
- **CGF Optimization Framework** (600+ tests):
  - Phase 0: Infrastructure (tracer, store, adapters, rewards)
  - Phase 1: Single-agent optimization (test cases, runners, DSPy, TextGrad, CLI)
  - Phase 2: Section-based optimization (agentic, coherence, MIPROv2)

### Completed Recently
- **CGF Phase 4: End-to-End Pipeline**
  - [x] Creation mode: Create + optimize new resources from description (`/cgf create`)
  - [x] Targeted refinement loop: Skip full research, focus on specific sections
  - [x] Cross-section regression detection with automatic rollback
  - [x] Post-synthesis validation against full test suite
  - [x] Updated threshold: 6+ deterministic tests for PROGRAMMATIC strategy
  - [x] DSPy Metric Bridge: `TestSuiteMetric` bridges CGF validators to DSPy

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
│   │   ├── prompts/                # 5 prompt files (3 container + 2 autonomous)
│   │   ├── plugins/                # 3 plugins (cgf-agents, context-engineering, research-team)
│   │   ├── skills/                 # 6 base skills
│   │   ├── optimization/           # CGF optimization framework
│   │   │   ├── cli/                # optimize.py, section_optimize.py
│   │   │   ├── analysis/           # competency_mapper, coherence, synthesizer
│   │   │   ├── optimizers/         # dspy, textgrad, mipro, agentic
│   │   │   ├── testcases/          # loader, validators, models
│   │   │   ├── runners/            # agent_runner, batch_runner
│   │   │   ├── resources/          # agent, prompt, skill resources
│   │   │   └── orchestrator.py     # Section-based optimization
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

---

## CGF Optimization Framework

The ContextGrad Framework (CGF) provides prompt optimization with **agentic (LLM-based) optimization as the default**. Programmatic optimization (DSPy MIPROv2, TextGrad) is available but disabled by default.

**Default Mode (Agentic)**: Uses LLM self-critique and research heuristics. No test suite required.
**Programmatic Mode**: Requires `CGF_ENABLE_PROGRAMMATIC=true` and 6+ deterministic tests.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CGF OPTIMIZATION ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                      PRE-OPTIMIZATION SETUP                               │  │
│  │                                                                           │  │
│  │  1. Load Agent ───────────► workspace/AGENT/AGENT.md                     │  │
│  │  2. Generate Tests ───────► cgf-test-architect → tests/tests.yaml        │  │
│  │  3. Generate Criteria ────► cgf-criteria-synthesizer → eval_criteria.yaml│  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                               │
│                                  ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                   FIVE-PHASE ORCHESTRATION                                │  │
│  │  orchestrator.py (SectionOptimizer)                                       │  │
│  │                                                                           │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌──────────┐     │  │
│  │  │ ANALYZE │→ │  PLAN   │→ │ EXECUTE │→ │ SYNTHESIZE│→ │ VALIDATE │     │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └─────┬─────┘  └────┬─────┘     │  │
│  │       │            │            │             │              │           │  │
│  │   Load agent   Create      Run optimizer  Merge sections  Full suite    │  │
│  │   Load tests   focused     per section    Coherence pass  validation    │  │
│  │   Map tests→   test        Cross-section  Auto-reorder    Rollback on   │  │
│  │   competencies suites      regression     (if enabled)    regression    │  │
│  │   Set eval_model           detection                                     │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                               │
│              ┌───────────────────┼───────────────────┐                          │
│              ▼                   ▼                   ▼                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │
│  │  PROGRAMMATIC  │  │    AGENTIC     │  │    PRESERVE    │                    │
│  │  (6+ determ)   │  │  (qualitative) │  │  (no coverage) │                    │
│  │                │  │                │  │                │                    │
│  │  ┌──────────┐  │  │  Self-critique │  │  Keep original │                    │
│  │  │  DSPy    │  │  │  LLM-based     │  │  section       │                    │
│  │  │  MIPROv2 │  │  │  improvement   │  │                │                    │
│  │  └──────────┘  │  │                │  │                │                    │
│  │  ┌──────────┐  │  │                │  │                │                    │
│  │  │ TextGrad │  │  │                │  │                │                    │
│  │  │   TGD    │  │  │                │  │                │                    │
│  │  └──────────┘  │  │                │  │                │                    │
│  └────────────────┘  └────────────────┘  └────────────────┘                    │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                      VALIDATORS & EVAL MODEL                              │  │
│  │                                                                           │  │
│  │  Deterministic (→ PROGRAMMATIC):   LLM-Based (→ AGENTIC):                │  │
│  │    exact, contains, regex            llm_judge                            │  │
│  │    code, code_syntax                 code_llm                             │  │
│  │                                                                           │  │
│  │  Eval Model (default: Sonnet): LLMJudgeValidator, CodeLLMValidator       │  │
│  │    Override: --eval-model haiku/sonnet/opus                              │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                      ANALYSIS & SYNTHESIS                                 │  │
│  │                                                                           │  │
│  │  competency_mapper.py ──► Map tests → competencies → sections            │  │
│  │  test_subset.py ────────► Create focused test suites per section         │  │
│  │  synthesizer.py ────────► Merge optimized sections into final prompt     │  │
│  │  coherence.py ──────────► Detect inversions, reorder for flow            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Optimization Strategies

| Strategy | Trigger | Optimizer | Validators |
|----------|---------|-----------|------------|
| **AGENTIC** (default) | Default mode, no tests required | Self-critique LLM | llm_judge, code_llm (optional) |
| **PROGRAMMATIC** | `CGF_ENABLE_PROGRAMMATIC=true` + ≥6 deterministic tests | DSPy MIPROv2 / TextGrad | exact, contains, regex, code, code_syntax |
| **PRESERVE** | No test coverage (programmatic mode only) | None | - |

**Default (Agentic)**: Uses research heuristics + LLM self-critique. Fastest, no test suite needed.
**Programmatic**: Requires explicit opt-in. Tests provide gradient signal for DSPy/TextGrad optimization.

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

```bash
# Discover SPEC.md automatically (preferred)
make optimize

# Explicit workspace path (when multiple SPEC.md exist)
make optimize WORKSPACE=workspace/python-expert

# Legacy mode with agent name
make optimize AGENT=python-expert

# Skip Q&A with direct goal
make optimize AGENT=python-expert GOAL="improve async guidance"

# Validate setup and show configuration
make optimize-dryrun                          # Discover mode
make optimize-dryrun WORKSPACE=workspace/x    # Explicit path
make optimize-dryrun AGENT=python-expert
```

**Workspace Structure (SPEC.md location = workspace root):**
```
{workspace_root}/                  # Directory containing SPEC.md
├── SPEC.md                        # Optimization spec (user OR Q&A-generated)
├── CHANGELOG.md                   # Human-readable optimization history (accumulates)
├── {resource}.md                  # Original resource (NEVER modified)
├── {resource}-v1.md               # First optimization
├── {resource}-v2.md               # Second optimization (if REFINE)
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
# Optimization mode
CGF_OPTIMIZER_MODE=agentic    # agentic (default), python, or both
CGF_ITERATIONS=10             # max optimization iterations per section
CGF_ITERATION_REVIEW=false    # pause for review after each iteration
CGF_EVAL_MODEL=sonnet         # sonnet (default), haiku, or opus
CGF_VERBOSE=true              # show progress output

# Programmatic mode settings (when CGF_OPTIMIZER_MODE=python or both)
CGF_OPTIMIZER=mipro           # mipro or textgrad
CGF_CANDIDATES=5              # candidates per iteration
CGF_LEARNING_RATE=0.1         # optimizer learning rate
CGF_EARLY_STOP=0.01           # early stopping threshold
```

**Q&A Flow Example:**
```
$ make optimize AGENT=python-expert

CGF Optimization Q&A
====================

[cgf-initializer] Analyzing resource: python-expert.md
[cgf-initializer] Detected: Agent (705 lines, 12 sections)

Question 1/5: What do you want to improve?
> Better async/await patterns and error handling

Question 2/5: Focus on specific sections? (2, 3, 5 or "all")
> 2, 3, 5

Question 3/5: Optimization mode? (1=agentic, 2=python, 3=both)
> 1

Question 4/5: Review after each iteration? (y/n)
> y

Question 5/5: Number of iterations? (default: 10)
> 5

[cgf-initializer] Saved: workspace/python-expert/cgf_spec.yaml
[SPEC_READY]

CGF Optimization Phase
======================
Goal: Better async/await patterns and error handling
Mode: agentic | Iterations: 5 | Review: enabled

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
make optimize WORKSPACE=workspace/my-agent
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

Default mode (agentic - no tests required):
```bash
# Default agentic optimization (no test suite needed)
uv run python -m harness.optimization.cli.section_optimize \
  --agent src/harness/agents/configs/dev-python-expert.md \
  --criteria workspace/dev-python-expert/research/eval_criteria.yaml \
  --workspace workspace/dev-python-expert \
  --iterations 2 \
  --verbose
```

Programmatic mode (requires `CGF_ENABLE_PROGRAMMATIC=true`):
```bash
# Enable test-based optimization
CGF_ENABLE_PROGRAMMATIC=true uv run python -m harness.optimization.cli.section_optimize \
  --agent src/harness/agents/configs/dev-python-expert.md \
  --test-suite workspace/dev-python-expert/tests/tests.yaml \
  --criteria workspace/dev-python-expert/research/eval_criteria.yaml \
  --workspace workspace/dev-python-expert \
  --optimizer mipro \
  --iterations 2 \
  --verbose

# Dry run (analyze test coverage)
CGF_ENABLE_PROGRAMMATIC=true uv run python -m harness.optimization.cli.section_optimize \
  --agent ... --test-suite ... --criteria ... --workspace ... \
  --dry-run
```

### Key Files

| File | Purpose |
|------|---------|
| `cli/optimize.py` | Single-agent optimization CLI |
| `cli/section_optimize.py` | Section-based optimization CLI |
| `orchestrator.py` | Section optimization orchestrator |
| `analysis/competency_mapper.py` | Map tests → competencies → sections |
| `analysis/coherence.py` | Detect and fix structural issues |
| `analysis/synthesizer.py` | Merge optimized sections |
| `optimizers/agentic_optimizer.py` | Self-critique optimizer (DEFAULT) |
| `optimizers/dspy_mipro_optimizer.py` | MIPROv2 Bayesian optimizer (requires CGF_ENABLE_PROGRAMMATIC) |
| `optimizers/textgrad_optimizer.py` | TextGrad TGD optimizer (requires CGF_ENABLE_PROGRAMMATIC) |
| `optimizers/dspy_metrics.py` | DSPy metric bridge for validators |

### Test Coverage

| Phase | Component | Tests |
|-------|-----------|-------|
| 0.1 | OpenTelemetry Tracing | 97 |
| 0.2 | Optimization Store | 89 |
| 0.3 | Resource Registry | 65 |
| 0.4 | Adapter Framework | 87 |
| 0.5 | Reward System | 50 |
| 0.6 | Integration | 16 |
| 1.0 | Single-Agent Optimization | 398 |
| **Total** | | **802+** |

### DSPy MIPROv2 Integration

The DSPy optimizer uses MIPROv2 (Bayesian optimization with TPE) via the metric bridge:

```python
# TestSuiteMetric bridges CGF validators to DSPy
metric = TestSuiteMetric(
    test_suite=suite,
    resource=resource,
    pass_threshold=0.5,
    cache_validators=True,
)

# Create trainset from test cases
trainset = create_trainset_from_suite(suite, include_expected=True)

# MIPROv2 three-stage optimization:
# 1. Bootstrapping: Collect high-quality traces
# 2. Grounded proposal: Draft instructions from task data
# 3. Discrete search: Bayesian TPE optimization
```

### TextGrad TGD Integration

TextGrad uses textual gradient descent with structure-aware optimization:

```python
# Trainable prompt variable
system_prompt_var = tg.Variable(
    prompt,
    requires_grad=True,
    role_description=f"{base_role}\n\n{structure_guidance}",
)

# TGD optimizer with validation revert
optimizer = tg.TGD(parameters=[system_prompt_var])

# Loss text from test failures drives backward pass
loss_var = tg.Variable(loss_text, requires_grad=False)
loss_var.backward()  # Generates textual gradients
optimizer.step()     # Applies improvements
```

### Orchestration Workflows

**Default (Agentic Mode)**:
1. **LOAD**: Load agent, criteria, and research findings
2. **ITERATE**: LLM self-critique (1-3 rounds)
3. **OUTPUT**: Merge sections, run coherence analysis, save

**Programmatic Mode** (CGF_ENABLE_PROGRAMMATIC=true):
1. **ANALYZE**: Map tests to competencies, assign strategies per section
2. **PLAN**: Create focused test suites for programmatic sections
3. **EXECUTE**: Run optimizers (MIPROv2/TextGrad/Agentic) per section
4. **SYNTHESIZE**: Merge sections, run coherence analysis, auto-reorder
5. **VALIDATE**: Post-synthesis full test suite validation with rollback

**Cross-Section Regression Detection** (programmatic mode): After optimizing section N, re-runs tests for sections 1..(N-1). If score drops > 5%, automatically rolls back.

### Creation Mode

Create and optimize new resources from natural language description:

```bash
/cgf create "Python async expert that helps with asyncio patterns"
```

Pipeline: INIT → CREATE (context-engineer) → RESEARCH → TEST_GEN → OPTIMIZE → EVALUATE → FINALIZE

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

---

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

### Subagents (14 harness + 11 plugin)

Invoked via `harness.direct_agent` module (Task tool has SDK bug):

**Harness Agents** (14):
| Category | Agents |
|----------|--------|
| **Development** (7) | python-expert, typescript-expert, go-expert, nodejs-expert, react-expert, refactor-agent, code-review-expert |
| **Database** (2) | postgres-expert, sql-expert |
| **Infrastructure** (4) | docker-engineer, k8s-engineer, gcp-architect, gitlab-ci-expert |
| **Testing** (1) | sdet-expert |

**Plugin Agents** (11):
| Plugin | Agents |
|--------|--------|
| **cgf-agents** (7) | cgf-orchestrator, cgf-research-lead, cgf-test-architect, cgf-test-validator, cgf-criteria-synthesizer, cgf-result-evaluator, cgf-prompt-optimizer |
| **context-engineering** (1) | context-engineer |
| **research-team** (3) | lead-research-coordinator, research-specialist, research-report-writer |

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
| Plugin Agents | 11 | `harness.direct_agent.call_agent()` | Working |
| Base Skills | 6 | `Skill(skill="...")` | Working |
| Plugin Skills | 7 | `Skill(skill="plugin:name")` | Working |
| Commands | 2 | CommandRegistry | Working |
| Hooks | 2 | HookRegistry | Working |

### Plugins (3 total)

**cgf-agents** (`src/harness/plugins/cgf-agents/`):
- 7 agents: cgf-orchestrator, cgf-research-lead, cgf-test-architect, cgf-test-validator, cgf-criteria-synthesizer, cgf-result-evaluator, cgf-prompt-optimizer
- 1 skill: cgf-optimize
- 1 command: cgf (with subcommands: create, optimize, status)
- Dependencies: context-engineering, research-team
- Orchestrates multi-agent optimization workflows

**context-engineering** (`src/harness/plugins/context-engineering/`):
- 1 agent: context-engineer
- 5 skills: agent-definition-creation, skill-creation, plugin-development, command-creation, hook-configuration
- Hook configuration for lifecycle events

**research-team** (`src/harness/plugins/research-team/`):
- 3 agents: lead-research-coordinator, research-specialist, research-report-writer
- 1 skill: joplin-research
- 1 command: research

### Namespacing

All plugin resources use `plugin-name:resource-name` format:
- Skills: `context-engineering:skill-creation`
- Commands: `cgf-agents:cgf`, `research-team:research`

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
