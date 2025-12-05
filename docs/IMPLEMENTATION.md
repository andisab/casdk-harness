# Agent Architecture & Implementation Plan

**Last Updated**: 2025-12-04
**Overall Status**: Phase 1 ✅ Complete | Phase 2 ✅ Complete

## Current Implementation Status

### Phase 1: Skills, Plugins & MCP Servers ✅

| Component | Status | Summary |
|-----------|--------|---------|
| **Skills** | ✅ Complete | 12 base + 6 plugin skills accessible via Skill tool |
| **Plugins** | ⚠️ Workaround | SDK bug prevents native loading; manual discovery active |
| **MCP Servers** | ✅ Complete | 6 servers (3 in-process + 3 subprocess) |
| **CLI Tools** | ✅ Complete | git, gh (GitHub CLI), glab (GitLab CLI) |

**Key Files**: `src/harness/agent.py`, `src/harness/mcp_loader.py`, `.claude/.mcp.json`

**Architecture**: Clean workspace separation (`/app` for config, `/workspace` for development)

### Phase 2: Dual-Mode Architecture ✅

| Component | Status | Summary |
|-----------|--------|---------|
| **Interactive Mode** | ✅ Complete | `make interactive` - Human-guided conversation |
| **Autonomous Mode** | ✅ Complete | `make autonomous` - Long-running development |
| **Progress Tracking** | ✅ Complete | task_list.json (with status), sessions/session_N.json |
| **Security** | ✅ Complete | Bash command allowlist/blocklist |
| **Agent Definitions** | ✅ Complete | 8 subagent definitions for Task tool |

**Key Files**:
- `src/harness/autonomous.py` - Autonomous mode entry point
- `src/harness/progress.py` - Progress tracking
- `src/harness/security.py` - Bash security validation
- `src/harness/agents/definitions.py` - Subagent definitions
- `src/harness/prompts/*.md` - Agent prompts

---

## Phase 1: Skills, Plugins & MCP

**Status**: ✅ Complete (2025-12-02)

### Skills (12 base + 6 plugin)

All skills accessible via Skill tool from `/app/.claude/skills/`.

**Base Skills**: api-development, code-review, database-management, debugging, deployment-operations, documentation, frontend-development, git-workflow, microservices-architecture, performance-optimization, security, testing-strategies

**Plugin Skills**: agent-definition-creation, skill-creation, plugin-development, command-creation, hook-configuration, joplin-research

### Plugins (⚠️ SDK Workaround Active)

3 plugins configured but blocked by SDK bug. Plugin skills work via manual discovery.

**Installed Plugins**: arch, context-engineering, research-team

**SDK Bug**: Python SDK v0.1.9 accepts `plugins` parameter but Claude CLI subprocess doesn't load them.
- [claude-code#11620](https://github.com/anthropics/claude-code/issues/11620)
- [claude-agent-sdk-python#213](https://github.com/anthropics/claude-agent-sdk-python/issues/213)

**When SDK Is Fixed**:
1. Verify `SystemMessage.data.get("plugins")` returns plugin list
2. Remove `_load_plugin_skills_manually()` from `agent.py`
3. Test: `tests/integration/test_sdk_plugin_awareness.py`

### MCP Servers (6 total)

| Type | Servers |
|------|---------|
| **In-Process** | docker, context7, memory |
| **Subprocess (npx)** | playwright, joplin |
| **Subprocess (uvx)** | excel-haris-musa |

API key validation with graceful degradation for joplin.

### CLI Tools (git, gh, glab)

Git, GitHub, and GitLab operations use CLI tools instead of MCP servers:
- **git**: Version control (always available, SSH keys in `.ssh/`)
- **gh**: GitHub CLI for repos, issues, PRs (requires `gh auth login` or GITHUB_PERSONAL_ACCESS_TOKEN)
- **glab**: GitLab CLI for projects, issues, MRs (requires `glab auth login` or GITLAB_PERSONAL_ACCESS_TOKEN)

### Architecture: Clean Workspace Separation

```
Container Filesystem:
├── /app/.claude/           # System config (READ-ONLY) - system prompt, skills, agents, specs
└── /workspace/             # Development work - clone repos here
```

**Key Configuration** (`src/harness/agent.py`):
- `cwd="/app"` - SDK finds skills at `/app/.claude/skills/`
- `setting_sources=["user", "project"]` - Enable skill discovery
- Docker mount: `./.claude:/app/.claude:ro`
- System prompt loaded from `.claude/CLAUDE.md`

---

## Phase 2: Dual-Mode Architecture

**Status**: ✅ Complete (2025-12-04)

### Operation Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Interactive** | `make interactive` | Human-guided conversation with immediate feedback |
| **Autonomous** | `make autonomous` | Long-running development with task tracking |

### Autonomous Mode Workflow

```
1. No task_list.json exists?
   → Run Initializer Mode (Tech Lead Q&A)
   → Generate task_list.json when requirements clear

2. task_list.json exists?
   → Run Continuation Mode (Coding Agent)
   → Work on highest priority incomplete task
   → Mark tasks complete or blocked
   → Commit changes
   → Loop until all tasks done
```

### Progress Tracking Files

| File | Purpose | Mutability |
|------|---------|------------|
| `task_list.json` | Task definitions with status (PASS/FAIL/null) | Status field mutable |
| `sessions/session_N.json` | Session metadata + transcript | One per session |

### Agent Definitions (8 subagents)

| Agent | Model | Purpose |
|-------|-------|---------|
| `tech-lead` | sonnet | Spec refinement, task planning |
| `python-expert` | sonnet | Python/FastAPI development |
| `typescript-expert` | sonnet | TS/React/Node development |
| `testing-agent` | haiku | Test writing and execution |
| `deployment-agent` | haiku | Docker/CI-CD configuration |
| `reviewer-agent` | sonnet | Code review (read-only) |
| `database-expert` | sonnet | Schema design, queries |
| `frontend-expert` | sonnet | React/CSS/UI development |

### Security

Bash command security with allowlist approach:
- **Allowed**: git, ls, python, npm, docker, make, etc.
- **Blocked**: rm -rf /, sudo, credential access, force push to main
- **Configurable**: `BASH_ALLOW_ALL=true` disables checks (dangerous)

### Makefile Commands

```bash
make autonomous          # Start autonomous development mode
make autonomous-model    # With specific model (MODEL=opus)
make autonomous-unsafe   # With all commands allowed (dangerous)
make autonomous-status   # Show progress status
make init-spec           # Create SPEC.md template
```

---

## Infrastructure Changes

### Removed: PostgreSQL

PostgreSQL was configured but never used. Removed from:
- docker-compose.yml
- config.py
- Makefile
- tests

### Kept: Redis

Redis remains for future multi-agent messaging:
- Inter-agent communication
- Session state sharing
- Pub/Sub coordination

### Kept: Prometheus + Grafana

Monitoring infrastructure unchanged:
- Agent metrics collection
- Token/cost tracking
- Session dashboards
