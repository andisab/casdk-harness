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

### SDK Task Tool Limitation

The Claude Agent SDK's Task tool doesn't recognize custom agents (GitHub issues #11205, #12212). Use direct invocation instead:

```python
from harness.direct_agent import call_agent, call_agent_simple, list_available_agents

# List all available agents
agents = list_available_agents()

# Simple invocation (returns text)
response = await call_agent_simple("python-expert", "Write a sort function")

# Streaming invocation
async for message in call_agent("python-expert", "Write a sort function"):
    process(message)
```

### Available Custom Agents

**Development**: python-expert, typescript-expert, go-expert, nodejs-expert, react-expert, refactor-agent

**Database**: postgres-expert, sql-expert

**Infrastructure**: docker-engineer, k8s-engineer, gcp-architect, gitlab-ci-expert

**Testing**: test-sdet-expert, dev-code-review-expert

**Plugin Agents**: research-team:lead-research-coordinator, research-team:research-specialist, research-team:research-report-writer, context-engineering:context-engineer

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
