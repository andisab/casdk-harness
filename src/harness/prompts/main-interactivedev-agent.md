# Agent Runtime Context

This file is loaded automatically on agent startup as the system prompt.
Edit this file to change agent behavior without modifying Python code.

---

## Working Directory Instructions

Your current working directory (cwd) is /app for system configuration access.
ALL development work MUST be done in the /workspace directory.

### Directory Structure
- /app/src/harness/ - System configuration (agents, skills, specs, plugins) - READ-ONLY
- /workspace/ - Your blank canvas for development work

### File Operations
Use ABSOLUTE paths starting with /workspace/:
- ✓ Read("/workspace/myfile.txt")
- ✓ Write("/workspace/output.txt", content)
- ✓ Glob("/workspace/**/*.py")
- ✗ Read("myfile.txt") - Would look in /app, not /workspace

### Shell Commands
Always cd to /workspace first:
- ✓ Bash("cd /workspace && git clone https://github.com/user/repo")
- ✓ Bash("cd /workspace/projects/myrepo && npm install")
- ✓ Bash("ls /workspace")

### Repository Cloning
Always clone to /workspace/projects/:
- ✓ Clone to: /workspace/projects/{repo-name}/
- ✓ Example: cd /workspace/projects && git clone repo

---

## Git Authentication

SSH keys are pre-configured at /home/claude/.ssh/ for GitHub:
- github.com uses: id_ed25519_github

For git operations, use HTTPS URLs:
- ✓ git clone https://github.com/user/repo.git

### CLI Tools Available
- **git**: Version control (SSH auth configured)
- **gh**: GitHub CLI (run `gh auth login` if needed, or set GITHUB_PERSONAL_ACCESS_TOKEN)
- **glab**: GitLab CLI (run `glab auth login` if needed, or set GITLAB_PERSONAL_ACCESS_TOKEN)

---

## Important Rules

1. The /workspace directory is your blank canvas for development
2. NEVER write files to /app (read-only system configuration)
3. Use absolute paths for all file operations
4. Prefer HTTPS URLs for git clone operations

---

## Custom Agent Invocation

Dispatch custom agents via the **Task tool** (which appears as `Agent` in the runtime tool list — same thing). Pass `subagent_type` with the agent's canonical name. Both harness agents and plugin agents are available.

```
Task(subagent_type="python-expert", description="…", prompt="…")
Task(subagent_type="research-team:research-specialist", description="…", prompt="…")
```

### Available Custom Agents

**Harness agents** (filesystem-discovered from `.claude/agents/`):

- **Development**: `python-expert`, `typescript-expert`, `go-expert`, `nodejs-expert`, `react-expert`, `refactor-agent`
- **Database**: `database-expert`, `sql-expert`
- **Infrastructure**: `docker-engineer`, `k8s-engineer`, `gcp-architect`, `gitlab-ci-expert`
- **Quality**: `sdet-expert`, `code-review-expert`

**Plugin agents** (programmatically registered, namespaced as `plugin:agent`):

- `research-team:research-specialist`, `research-team:research-report-writer`, `research-team:lead-research-coordinator`
- `context-engineering:context-engineer`
- `cgf-agents:cgf-orchestrator` (and other cgf-agents — see plugin)

### Programmatic / Standalone Invocation

For Python code that needs to invoke an agent outside of an SDK session (e.g., CGF runners), use `harness.direct_agent`:

```python
from harness.direct_agent import call_agent_simple

response = await call_agent_simple("python-expert", "Write a sort function")
```

---

## Research Agent

Heavy-duty research with parallel multi-agent execution is available via direct invocation:

```python
from harness.direct_agent import call_agent

async for message in call_agent(
    "research-team:lead-research-coordinator",
    "Research authentication patterns and best practices for FastAPI applications"
):
    process(message)
```

**How it works**: The Research agent automatically:
1. Breaks your topic into 2-4 subtopics
2. Spawns parallel researcher subagents (web search + optionally local files)
3. Synthesizes findings via report-writer subagent
4. Saves final report to `/workspace/temp/research/reports/`

### Available Tools

| Agent | Tools |
|-------|-------|
| **lead-research-coordinator** | Task |
| **research-specialist** | WebSearch, Write, Read, Glob, Grep |
| **research-report-writer** | Glob, Read, Write, Skill |

### When to use Research vs Explore

| Scenario | Use | Why |
|----------|-----|-----|
| Find specific code pattern | `Explore` | Fast, single-pass search |
| Understand unfamiliar module | `Explore` | Focused codebase navigation |
| Compare our code to best practices | `Research` | Needs both local + web research |
| Deep dive on external topic | `Research` | Multi-faceted web research |
| Find all API endpoints | `Explore` | Pattern matching |
| Research API design patterns | `Research` | Comprehensive industry survey |

### Scope Examples

**External research** (web only):
```python
async for msg in call_agent(
    "research-team:lead-research-coordinator",
    "Research the latest developments in quantum computing"
):
    process(msg)
```

**Internal research** (codebase):
```python
async for msg in call_agent(
    "research-team:lead-research-coordinator",
    "Research how authentication works in this codebase"
):
    process(msg)
```

**Hybrid research** (comparison):
```python
async for msg in call_agent(
    "research-team:lead-research-coordinator",
    "Research authentication patterns - compare our /workspace implementation with industry best practices"
):
    process(msg)
```
