>[toc]

# AI-Assisted Development Framework - Implementation Plan

**Last Updated**: October 28, 2025
**Purpose**: Track present state and plan future work for the 3-repository agentic framework

---

## Executive Summary

The AI-Assisted Development Framework consists of three repositories with clear separation of concerns:

| Repository | Purpose | Status |
|------------|---------|--------|
| **ABDotfiles** | Personal environment configuration (Claude Code, shell, IDE) | ✅ Production-ready |
| **conventions-mcp** | Dynamic retrieval of conventions, agents, workflows | ✅ v1.0.2 published |
| **claudeagentsdk-harness** | Long-running agent execution platform with observability | ✅ Phase 1 complete |

---

## Repository Purposes

### ABDotfiles - Personal Environment Layer
**Role**: Configure your personal development environment consistently across machines

**What It Manages**:
- Claude Code configuration (`~/.claude/`)
- IDE settings (VS Code, Cursor, Windsurf)
- Shell configuration (bash, zsh)
- Personal default agents, commands, skills, specs

**Key Mechanism**: Dotfiles sync via `config_parser.py` and `dotfiles.conf`

**Storage Location**: `/Users/andisblukis/Projects/ABDotfiles`

---

### Conventions MCP - Dynamic Convention Retrieval
**Role**: Pull context files dynamically based on task requirements

**What It Provides**:
- Fuzzy search across multiple sources (built-in, local, Git repos)
- Token-aware retrieval (respects context windows)
- Agent definitions, workflows, skills, patterns
- Team/project conventions via Git repositories

**Key Mechanism**: MCP server with 9 tools (search, retrieve, manage repos, stats)

**Storage Location**: `/Users/andisblukis/Projects/conventions-mcp`

---

### Claude Agent SDK Harness - Execution Platform
**Role**: Run long-running agent teams for complex projects

**What It Provides**:
- Multi-agent orchestration (main, reviewer, tester)
- Checkpoint & recovery (hourly auto-save)
- Full observability (Prometheus + Grafana)
- Interactive conversation mode
- Docker infrastructure with resource management

**Key Mechanism**: Agent session wrapper around Claude Agent SDK

**Storage Location**: `/Users/andisblukis/Projects/claudeagentsdk-harness`

---

## ARCHITECTURAL DECISION: 3-Layer Resource Management

**Date**: October 28, 2025

### The Problem
Where should we store custom slash commands, agents, workflows, skills, and similar resources? Three options:
1. ABDotfiles (personal use, version controlled)
2. Conventions MCP (dynamic discovery, multi-source)
3. Harness (co-located with execution)

### The Decision: Layered Hybrid Architecture

Resources flow through three layers based on lifecycle and scope:

```
┌────────────────────────────────────────────────────────┐
│  Layer 3: Execution Context (harness)                  │
│  - Active session state                                │
│  - Loaded agent configurations                         │
│  - Runtime cache: config/agents/active/                │
│  - Session context: memory/context/                    │
│  Priority: HIGH (currently executing)                  │
└─────────────────┬──────────────────────────────────────┘
                  │ (loads from)
┌─────────────────▼──────────────────────────────────────┐
│  Layer 2: Dynamic Discovery (Conventions MCP)          │
│  - Task-specific conventions                           │
│  - Team workflows and standards                        │
│  - Specialized agents for current task                 │
│  - Multi-source: built-in + local + Git repos          │
│  Priority: MEDIUM (task-specific)                      │
└─────────────────┬──────────────────────────────────────┘
                  │ (searches in)
┌─────────────────▼──────────────────────────────────────┐
│  Layer 1: Personal Defaults (ABDotfiles)               │
│  - Core personal preferences                           │
│  - Default agent definitions                           │
│  - Favorite commands and workflows                     │
│  - Synced to: ~/.claude/                               │
│  Priority: LOW (fallback)                              │
└────────────────────────────────────────────────────────┘
```

### Next Steps: Risk Mitigation Pladn

  - Schema Governance Across Repos
      - Extract agent/workflow schemas into a versioned conventions-schema package consumed by ABDotfiles, conventions-mcp, and the harness.
      - Add a contract test suite in CI that loads canonical examples from each repo and executes round‑trip validation (conventions-mcp → harness → back) so TeamBuilderAgent can’t drift into incompatible YAML (docs/future/FUTURE.md:711).
      - Introduce semantic versioning plus compatibility metadata (e.g., requires_harness>=1.4) so TeamBuilderAgent can refuse configs that target a newer schema before write.
  - Persisted Configuration History & Learning Loop
      - Leverage the existing Postgres instance to store signed snapshots of every assembled team (raw YAML, normalized schema, diff to previous) alongside run metadata (duration, cost, failure flags).
      - Use Redis for fast session-scoped state: current validation checklist, outstanding approvals, temporary rollbacks.
      - Build a nightly job that mines Postgres for failure patterns (e.g., tool permission denials, high-cost overruns) and produces heuristic updates or recommendations that seed the next TeamBuilderAgent session—closing the “learn from mistakes” loop.
  - Preflight Validation & Policy Enforcement
      - Implement a multi-stage gate before TeamBuilderAgent is allowed to call write_config: schema validation, policy checks (dangerous bash patterns, model cost ceilings), dependency checks (MCP availability, local file permissions).
      - When any gate fails, abort assembly immediately and surface actionable guidance to the user, aligning with the “block at first sign of likely failure” requirement (docs/future/FUTURE.md:275-345, 645-683).
      - Add an approval workflow: high-cost models, broad bash permissions, or cross-team resource pulls require explicit user confirmation before the gate passes.
  - Runtime Safety & Rollback
      - Replace the single-step reload_harness with a transactional state machine: stage assets, verify staging, commit by swapping symlinks/config pointers, and roll back automatically if any MCP or agent init fails.
      - Emit structured events to Redis so a lightweight supervisor (or the TeamBuilderAgent itself) can detect “partial loads” and revert without manual intervention.
  - Cache Invalidation & Freshness
      - Extend the hybrid cache with robust invalidation triggers: file watchers for local dirs, git commit hooks for repo sources, and TTL-based fallbacks.
      - Keep a cache fingerprint per resource in Postgres so the harness can verify the cached version matches the stored snapshot before allowing a run.
  - Continuous Feedback to the Agent
      - Feed validation failures, reload errors, and run outcomes back into TeamBuilderAgent via a “lessons learned” context assembled from Postgres (top recurring fixes, rollback causes).
      - Over time, let the agent adjust its default team templates or policy requests based on these insights, giving you the recursive improvement channel you’re after.

  Next Steps to Plan Out

  1. Carve out the shared schema library and wire lightweight compatibility tests across all three repos.
  2. Stand up the Postgres tables/Redis keys outlined above and capture configs + run metadata from the current harness flow.
  3. Implement the gating pipeline and approval UX so TeamBuilderAgent can’t write unsafe configs.
  4. Refactor reload_harness into a reversible state machine with telemetry hooks.
  5. Layer in the cache invalidation improvements and the feedback ingestion step for the agent.


### Resource Storage Guidelines

| Resource Type | Primary Storage | Rationale |
|---------------|----------------|-----------|
| **Personal default agents** | ABDotfiles → `~/.claude/agents/` | Stable, follows you across machines |
| **Project-specific agents** | Conventions MCP (Git repo) | Team sharing, project-scoped |
| **Active agent configs** | Harness → `config/agents/active/` | Fast access during execution |
| **Personal slash commands** | ABDotfiles → `~/.claude/commands/` | Personal workflow automation |
| **Team workflows** | Conventions MCP (team repo) | Collaborative workflows |
| **Session state** | Harness → `memory/context/` | Ephemeral session data |
| **Coding standards** | ABDotfiles → `~/.claude/specs/` | Personal coding preferences |
| **Team standards** | Conventions MCP (company repo) | Shared team standards |

### Example Flow: "Build a FastAPI authentication endpoint"

1. **Session Start** (Layer 3: harness):
   ```bash
   make interactive
   ```

2. **Context Loading** (Layer 2: MCP):
   ```python
   # Harness calls team-builder to search conventions
   results = mcp.search_conventions(
       query="fastapi authentication",
       type="agent,workflow,pattern",
       tokenBudget=10000
   )
   # Returns: FastAPI agent, auth patterns, testing workflow
   ```

3. **Fallback** (Layer 1: ABDotfiles):
   ```python
   # If no fastapi-specific agent found, use default Python expert
   # from ~/.claude/agents/development/python-expert.md
   ```

4. **Session Execution** (Layer 3: harness):
   ```python
   # Resources cached in config/agents/active/ and memory/context/
   # Fast access during agent execution
   ```

---

## OPEN QUESTIONS & IMPLEMENTATION PRIORITIES

### Question 1: Team-Builder Component Design

**Problem**: Need a component that assembles agent teams for specific tasks through a 5-step interactive workflow:
1. Design the team (reasoning, user interaction)
2. Retrieve resources (search conventions-mcp)
3. Validate & adjust (conflict resolution, user confirmation)
4. Assemble resources (write config files)
5. Reload harness (initialize agents and MCP servers)

**DECISION: TeamBuilderAgent with Skills as Tools**

**Architecture**: Single agent that orchestrates the entire workflow using tools provided to it.

```
TeamBuilderAgent (Claude Agent SDK)
├─ Built-in Tools
│  ├─ Read
│  ├─ Write
│  └─ Bash
│
├─ MCP Tools (conventions-mcp)
│  ├─ search_conventions
│  ├─ get_agent_configuration
│  └─ search_agents_by_capability
│
└─ Custom Skills (harness-provided tools)
   ├─ write_config
   ├─ validate_config
   └─ reload_harness
```

**Why This Approach**:
1. ✅ **Agent autonomy**: Agent decides when to use each tool based on context
2. ✅ **Consistent architecture**: Everything is a tool the agent reasons about
3. ✅ **Error recovery**: Agent can retry or adjust if assembly fails
4. ✅ **Follows Claude Agent SDK patterns**: Tools are the primary abstraction
5. ✅ **Testing**: Can mock skills like any other tool

**Agent Configuration**:
```yaml
name: team-builder
model: sonnet-4.5  # Cost/capability balance
permission_mode: acceptEdits
max_turns: 100

tools:
  # Built-in
  - Read
  - Write
  - Bash

  # MCP (conventions-mcp)
  - mcp:conventions:search_conventions
  - mcp:conventions:get_agent_configuration
  - mcp:conventions:search_agents_by_capability

  # Custom skills (harness)
  - skill:team_assembler:write_config
  - skill:team_assembler:validate_config
  - skill:team_assembler:reload_harness
```

**Implementation Timeline**:
- Week 1: Add 3 new MCP tools to conventions-mcp (3 days)
- Week 2: Implement 3 custom skill tools in harness (2 days)
- Week 3: Build TeamBuilderAgent with tool integration (4 days)
- Week 4: Integration testing and refinement (3 days)

**Total effort**: ~12 days

**Cost per team assembly**: $0.02-0.10 (using sonnet model)
**Time per assembly**: 30-60 seconds with user interaction

---

#### Detailed Workflow: 5-Step Team Assembly

**Example Task**: "Build a FastAPI authentication endpoint with testing"

**Step 1: Design Team (TeamBuilderAgent - Interactive)**
```
Agent analyzes task and proposes:
- python-expert (main developer)
- fastapi-architect (specialized knowledge)
- tester-agent (test generation)
- reviewer-agent (code review)

Asks user:
- "Include database setup? (Y/N)"
- "Testing framework? (pytest/unittest)"
- "Code review timing? (each step/end)"
```

**Step 2: Retrieve Resources (MCP Tools - Automated)**
```python
# Agent calls conventions-mcp
config1 = mcp.get_agent_configuration("python-expert")
config2 = mcp.get_agent_configuration("fastapi-architect")
config3 = mcp.get_agent_configuration("tester-agent")
config4 = mcp.get_agent_configuration("reviewer-agent")

workflow = mcp.search_conventions(
    query="fastapi authentication workflow",
    type="workflow"
)

patterns = mcp.search_conventions(
    query="authentication patterns",
    type="pattern",
    tokenBudget=5000
)
```

**Step 3: Validate & Adjust (TeamBuilderAgent - Interactive)**
```
Agent reviews configs and finds:
- Dangerous permission: Bash(rm -rf:*) → Remove
- MCP servers needed: [context7, docker, memory, git]
- Model costs: 2 agents using opus → Propose downgrade

Proposes adjustments:
- Use opus for python-expert (main work)
- Use sonnet for fastapi-architect (consulting)
- Remove dangerous Bash permissions
- Add required MCP servers

User confirms: "Looks good, proceed"
```

**Step 4: Assemble Resources (Agent calls write_config tool)**
```python
# Agent uses write_config tool
result = await tools.write_config(
    team_name="fastapi-auth-team",
    agents=[config1, config2, config3, config4],
    mcp_servers=["context7", "docker", "memory", "git"],
    workflows=[workflow],
    patterns=[patterns]
)

# Tool generates files:
# - config/agents/active/team-config.yaml
# - config/agents/active/python-expert.yaml
# - config/agents/active/fastapi-architect.yaml
# - memory/context/patterns/authentication-patterns.md
# - memory/context/workflows/fastapi-workflow.yaml

# Tool returns:
# {
#   "success": true,
#   "files_written": ["...", "..."],
#   "message": "Wrote 7 configuration files"
# }
```

**Step 5: Reload Harness (Agent calls validate_config + reload_harness tools)**
```python
# Agent first validates
validation = await tools.validate_config()
# Returns: {"valid": true, "errors": []}

# Then reloads harness
status = await tools.reload_harness()

# Tool performs:
# 1. Initialize MCP servers (context7, docker, memory, git)
# 2. Load agent definitions into AgentSession
# 3. Load workflows and patterns into context cache
# 4. Start primary agent (python-expert)
# 5. Set up agent handoff rules
# 6. Verify initialization

# Tool returns:
# {
#   "ready": true,
#   "agents_loaded": 4,
#   "mcp_servers_connected": 4,
#   "workflows_loaded": 1,
#   "message": "Team ready: 4 agents, 4 MCP servers"
# }

# Agent reports to user:
# ✅ Team assembled and ready
# ✅ 4 agents loaded
# ✅ 4 MCP servers connected
# ✅ Workflow loaded: fastapi-authentication
```

#### Implementation Components

**Component 1: TeamBuilderAgent Configuration**

```yaml
# config/agents/team-builder.yaml
name: team-builder
description: Interactive agent that designs and assembles agent teams
model: sonnet-4.5
permission_mode: acceptEdits
max_turns: 100

system_prompt: |
  You are a team builder agent that helps users assemble agent teams for software development tasks.

  Your workflow:
  1. Analyze the user's task and propose an agent team structure
  2. Ask clarifying questions about requirements
  3. Use get_agent_configuration to retrieve agent definitions from conventions-mcp
  4. Validate configurations and check for conflicts
  5. Use write_config to generate configuration files
  6. Use validate_config to verify correctness
  7. Use reload_harness to initialize the team

  Always explain your reasoning and get user approval before making changes.

tools:
  - Read
  - Write
  - Bash
  - mcp:conventions:search_conventions
  - mcp:conventions:get_agent_configuration
  - mcp:conventions:search_agents_by_capability
  - skill:team_assembler:write_config
  - skill:team_assembler:validate_config
  - skill:team_assembler:reload_harness
```

**Component 2: MCP Tools (conventions-mcp/server.ts)**

Three new tools to add to conventions-mcp:

**Tool 1: `get_agent_configuration`**
```typescript
{
  name: "get_agent_configuration",
  description: "Retrieve complete configuration for a specific agent including frontmatter, tools, permissions, and MCP servers",
  inputSchema: {
    type: "object",
    properties: {
      agentName: {
        type: "string",
        description: "Agent name or ID (e.g., 'python-expert', 'fastapi-architect')"
      }
    },
    required: ["agentName"]
  }
}

// Returns:
{
  name: "python-expert",
  type: "agent",
  description: "Expert Python development with async, type safety",
  model: "opus 4.1",
  tools: ["Read", "Write", "MultiEdit", "Bash"],
  toolPermissions: {
    allow: ["Bash(git:*)", "Bash(pytest:*)"],
    deny: ["Bash(rm -rf:*)", "Bash(curl:* | bash:*)"]
  },
  mcpServers: ["context7", "memory"],
  dependencies: ["general_code_standards", "python_spec"],
  capabilities: ["python", "async", "type-safety", "fastapi"],
  content: "# Python Development Expert\n...",
  tokenCount: 3450
}
```

**Tool 2: `search_agents_by_capability`**
```typescript
{
  name: "search_agents_by_capability",
  description: "Find agents with specific capabilities or expertise",
  inputSchema: {
    type: "object",
    properties: {
      capabilities: {
        type: "array",
        items: { type: "string" },
        description: "Required capabilities (e.g., ['python', 'fastapi', 'async'])"
      },
      maxResults: {
        type: "number",
        default: 5
      }
    },
    required: ["capabilities"]
  }
}

// Returns: Array of agent summaries matching capabilities
```

**Tool 3: `validate_agent_compatibility`**
```typescript
{
  name: "validate_agent_compatibility",
  description: "Check if multiple agents can work together without conflicts",
  inputSchema: {
    type: "object",
    properties: {
      agentNames: {
        type: "array",
        items: { type: "string" }
      }
    },
    required: ["agentNames"]
  }
}

// Returns:
{
  compatible: true,
  conflicts: [],
  sharedMcpServers: ["context7", "memory"],
  warnings: ["Both agents use opus model - high cost"]
}
```

**Component 3: Custom Skill Tools (src/harness/tools/team_assembler_tools.py)**

Three custom tools implemented as Claude Agent SDK tools:

**Tool 1: `write_config`**
```python
from typing import Any, Dict, List
from pathlib import Path
from claude_agent_sdk import Tool

class WriteConfigTool(Tool):
    """Custom tool for writing team configuration files"""

    name = "write_config"
    description = """
    Write team configuration files to disk.

    Args:
        team_name: Name for this team
        agents: List of agent configurations (from get_agent_configuration)
        mcp_servers: List of MCP server names to initialize
        workflows: List of workflow definitions (optional)
        patterns: List of patterns to load into context (optional)

    Returns:
        success: Boolean
        files_written: List of file paths created
        message: Summary message
    """

    async def execute(self, **kwargs) -> Dict[str, Any]:
        config_dir = Path("config/agents/active")
        context_dir = Path("memory/context")

        # Ensure directories exist
        config_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "workflows").mkdir(parents=True, exist_ok=True)
        (context_dir / "patterns").mkdir(parents=True, exist_ok=True)

        files_written = []

        # Write team-config.yaml
        team_config = {
            "team_name": kwargs["team_name"],
            "agents": [a["name"] for a in kwargs["agents"]],
            "mcp_servers": kwargs["mcp_servers"],
            "created_at": datetime.now().isoformat()
        }
        team_file = config_dir / "team-config.yaml"
        self._write_yaml(team_file, team_config)
        files_written.append(str(team_file))

        # Write individual agent configs
        for agent in kwargs["agents"]:
            agent_file = config_dir / f"{agent['name']}.yaml"
            self._write_yaml(agent_file, agent)
            files_written.append(str(agent_file))

        # Write workflows
        for workflow in kwargs.get("workflows", []):
            wf_file = context_dir / "workflows" / f"{workflow['name']}.yaml"
            self._write_yaml(wf_file, workflow)
            files_written.append(str(wf_file))

        # Write patterns
        for pattern in kwargs.get("patterns", []):
            pat_file = context_dir / "patterns" / f"{pattern['name']}.md"
            pat_file.write_text(pattern['content'])
            files_written.append(str(pat_file))

        return {
            "success": True,
            "files_written": files_written,
            "message": f"Wrote {len(files_written)} configuration files"
        }
```

**Tool 2: `validate_config`**
```python
class ValidateConfigTool(Tool):
    """Custom tool for validating team configuration"""

    name = "validate_config"
    description = """
    Validate team configuration files for correctness.

    Returns:
        valid: Boolean indicating if config is valid
        errors: List of validation errors (empty if valid)
        warnings: List of non-critical warnings
        message: Summary message
    """

    async def execute(self) -> Dict[str, Any]:
        config_dir = Path("config/agents/active")
        errors = []
        warnings = []

        # Check team-config.yaml exists
        team_config_file = config_dir / "team-config.yaml"
        if not team_config_file.exists():
            return {
                "valid": False,
                "errors": ["Missing team-config.yaml"],
                "warnings": [],
                "message": "Configuration is invalid"
            }

        team_config = self._load_yaml(team_config_file)

        # Validate required fields
        required_fields = ["team_name", "agents", "mcp_servers"]
        for field in required_fields:
            if field not in team_config:
                errors.append(f"Missing required field: {field}")

        # Validate agent configs exist
        for agent_name in team_config.get("agents", []):
            agent_file = config_dir / f"{agent_name}.yaml"
            if not agent_file.exists():
                errors.append(f"Missing agent config: {agent_name}.yaml")
            else:
                # Validate agent config schema
                agent_config = self._load_yaml(agent_file)
                if "model" not in agent_config:
                    warnings.append(f"{agent_name}: No model specified, will use default")
                if "tools" not in agent_config:
                    warnings.append(f"{agent_name}: No tools specified")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "message": "Valid configuration" if not errors else f"Found {len(errors)} errors"
        }
```

**Tool 3: `reload_harness`**
```python
class ReloadHarnessTool(Tool):
    """Custom tool for reloading harness with new configuration"""

    name = "reload_harness"
    description = """
    Reload harness with new team configuration.

    This will:
    1. Initialize MCP servers specified in team config
    2. Load agent definitions into AgentSession
    3. Load workflows and patterns into context cache
    4. Start primary agent (first in team)
    5. Verify all agents initialized successfully

    Returns:
        ready: Boolean indicating if team is ready
        agents_loaded: Number of agents loaded
        mcp_servers_connected: Number of MCP servers connected
        workflows_loaded: Number of workflows loaded
        message: Summary message
    """

    async def execute(self) -> Dict[str, Any]:
        config_dir = Path("config/agents/active")
        context_dir = Path("memory/context")

        # Load team config
        team_config = self._load_yaml(config_dir / "team-config.yaml")

        # Initialize MCP servers
        mcp_servers_connected = 0
        for mcp_server in team_config["mcp_servers"]:
            try:
                success = await self._init_mcp_server(mcp_server)
                if success:
                    mcp_servers_connected += 1
            except Exception as e:
                # Log but don't fail - agent can decide what to do
                logger.warning(f"Failed to initialize MCP server {mcp_server}: {e}")

        # Load agent definitions
        agents_loaded = 0
        for agent_name in team_config["agents"]:
            try:
                agent_config = self._load_yaml(config_dir / f"{agent_name}.yaml")
                agent = await self._create_agent_session(agent_config)
                if agent:
                    agents_loaded += 1
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")

        # Load workflows
        workflows_loaded = len(list((context_dir / "workflows").glob("*.yaml")))

        # Verify all agents loaded
        all_loaded = agents_loaded == len(team_config["agents"])

        return {
            "ready": all_loaded,
            "agents_loaded": agents_loaded,
            "mcp_servers_connected": mcp_servers_connected,
            "workflows_loaded": workflows_loaded,
            "message": (
                f"Team ready: {agents_loaded} agents, {mcp_servers_connected} MCP servers, {workflows_loaded} workflows"
                if all_loaded
                else f"Partial load: {agents_loaded}/{len(team_config['agents'])} agents loaded"
            )
        }
```

---

#### Other Options Considered

**Option B: Skill/Module Only (Rejected)**
- Proposed using Python functions for deterministic configuration
- Pros: Fast, no API costs, predictable behavior
- Cons: No reasoning ability, requires pre-defined templates, inflexible
- Rejected because: Cannot handle interactive design or validation steps

**Option C: Built-in to conventions-mcp (Rejected)**
- Proposed adding team assembly logic to conventions-mcp server
- Pros: Co-located with convention data, single source of truth
- Cons: Increases conventions-mcp complexity, tight coupling, no user interaction
- Rejected because: Wrong separation of concerns (MCP should only provide data, not orchestrate workflows)

**Hybrid (A+B+C) Approach (Initial Proposal, Refined)**
- Initially proposed using separate components for each step
- Refined to: Single agent with tools (cleaner, more consistent)
- Evolution: Recognized that Steps 4 & 5 should be tools given to the agent, not separate modules

---

#### Required Schema Changes

**Enhanced Agent Frontmatter (conventions-mcp)**:
```yaml
---
name: python-expert
type: agent
tools: Read, Write, MultiEdit, Bash
model: opus 4.1

# NEW: Tool permissions
toolPermissions:
  allow:
    - "Bash(git:*)"
    - "Bash(pytest:*)"
  deny:
    - "Bash(rm -rf:*)"
    - "Bash(curl:* | bash:*)"

# NEW: MCP servers required
mcpServers:
  - context7
  - memory

# NEW: Dependencies (other conventions to load)
dependencies:
  - general_code_standards
  - python_spec

# NEW: Capabilities (for search)
capabilities:
  - python
  - async
  - type-safety
  - fastapi
---
```

**Workflow Schema (conventions-mcp)**:
```yaml
---
name: fastapi-authentication
type: workflow

agents:
  - role: primary
    name: python-expert
    tasks:
      - "Analyze requirements"
      - "Implement endpoint"

  - role: testing
    name: tester-agent
    tasks:
      - "Write tests"

handoffRules:
  - from: python-expert
    to: tester-agent
    trigger: "code complete"

contextToInclude:
  - type: pattern
    query: "authentication patterns"
    tokenBudget: 3000
---
```

---

#### Decision Summary: Question 1

**Final Architecture**: TeamBuilderAgent with 9 tools (3 built-in, 3 MCP, 3 custom skills)

**Key Insights**:
1. Agent reasoning is essential for steps 1 & 3 (design + validation)
2. MCP tools provide clean data access for step 2 (retrieval)
3. Custom skills handle deterministic operations for steps 4 & 5 (assembly + reload)
4. Skills should be tools given to the agent, not separate Python modules
5. Agent orchestrates entire workflow using tools at its disposal

**Implementation Priority**:
1. Add 3 MCP tools to conventions-mcp (Week 1)
2. Implement 3 custom skill tools in harness (Week 2)
3. Configure TeamBuilderAgent with all tools (Week 3)
4. Integration testing and refinement (Week 4)

---

### Question 2: Conventions-MCP Performance Optimization

**Current Performance** (baseline):
- Search latency: ~50ms (target: <100ms) ✅
- Repository clone: ~5s (target: <10s) ✅
- Convention retrieval: ~20ms (target: <50ms) ✅
- Memory usage: ~60MB (target: <100MB) ✅

**Current Implementation**:
- File scanning on each search (no persistent index)
- Fuse.js in-memory fuzzy matching
- Convention caching per session
- Lazy repository cloning

**Performance Concerns**:
1. Large convention sets (1000+ files) may degrade search
2. No persistent indexing between server restarts
3. Full file scan on every search request
4. Metadata parsing overhead (YAML frontmatter)

**Optimization Options**:

#### Option A: MongoDB Backend
**Pros**:
- Full-text search with indexes
- Persistent across restarts
- Rich query capabilities (aggregations, filtering)
- Scalable to large datasets

**Cons**:
- Additional Docker container (complexity)
- Network latency (harness → MCP → MongoDB)
- Operational overhead (backups, migrations)
- Overkill for personal use case?

**Implementation**:
```typescript
// ConventionStorage.ts changes
- File scanning → MongoDB queries
- Add MongoDB connection management
- Index on: type, tags, title, description, content
- Sync strategy: watch filesystem, update DB on change
```

#### Option B: SQLite with FTS5
**Pros**:
- Embedded (no separate container)
- Full-text search built-in (FTS5 extension)
- Persistent across restarts
- Zero configuration

**Cons**:
- Limited to single file (no distributed search)
- Less powerful than MongoDB
- Requires file writes (not always ideal)

**Implementation**:
```typescript
// Add SQLite integration
- Create conventions.db on first run
- FTS5 virtual table for full-text search
- Sync on repository add/sync
```

#### Option C: Pre-computed Index Files
**Pros**:
- No database dependency
- Very fast lookups (JSON parse only)
- Version controllable (commit index with conventions)
- Works offline

**Cons**:
- Index rebuild on every change
- No dynamic queries (pre-computed only)
- Larger repository size

**Implementation**:
```typescript
// Generate index files
npm run index  // Creates .conventions-index.json
- Metadata extracted and stored
- Search uses pre-built index
- Fuse.js still used for fuzzy matching
```

#### Option D: Hybrid Caching Layer
**Pros**:
- Minimal changes to current architecture
- Best of both worlds (fast + simple)
- Smart invalidation

**Cons**:
- Still scans on cache miss
- Memory footprint grows with cache

**Implementation**:
```typescript
// Add intelligent caching
- Cache parsed conventions in memory
- Watch filesystem for changes (invalidate cache)
- LRU eviction for memory management
- Persist cache to disk on shutdown
```

**DECISION: Implement Option D (Hybrid Caching), Defer Database Solutions**

**Rationale**:
- Current performance already meets targets (~50ms search, ~20ms retrieval)
- Optimization only needed when convention set > 500 files
- YAGNI principle: Don't optimize prematurely
- Option D provides immediate benefit with minimal risk/complexity

**Implementation Details (Option D - Hybrid Caching)**:

```typescript
// conventions-mcp: src/core/ConventionCache.ts (NEW FILE)
export class ConventionCache {
    private cache: Map<string, Convention> = new Map();
    private lastScan: Map<string, number> = new Map();
    private maxCacheSize: number = 1000; // LRU eviction threshold

    async getConventions(sourceId: string): Promise<Convention[]> {
        const cacheKey = `source:${sourceId}`;
        const lastModified = await this.getSourceLastModified(sourceId);

        // Cache hit - return cached conventions
        if (this.lastScan.get(cacheKey) === lastModified) {
            return Array.from(this.cache.values())
                .filter(c => c.source.sourceId === sourceId);
        }

        // Cache miss - scan filesystem and update cache
        const conventions = await this.scanSource(sourceId);
        this.updateCache(sourceId, conventions, lastModified);
        return conventions;
    }

    private updateCache(sourceId: string, conventions: Convention[], timestamp: number): void {
        // Remove old conventions for this source
        for (const [key, convention] of this.cache) {
            if (convention.source.sourceId === sourceId) {
                this.cache.delete(key);
            }
        }

        // Add new conventions
        for (const convention of conventions) {
            this.cache.set(convention.id, convention);
        }

        this.lastScan.set(`source:${sourceId}`, timestamp);

        // LRU eviction if cache too large
        if (this.cache.size > this.maxCacheSize) {
            this.evictOldest();
        }
    }

    private async getSourceLastModified(sourceId: string): Promise<number> {
        // For local directories: check directory mtime
        // For repositories: check git HEAD commit hash
        // Returns timestamp or hash as number
    }

    invalidate(sourceId?: string): void {
        if (sourceId) {
            this.lastScan.delete(`source:${sourceId}`);
        } else {
            this.lastScan.clear();
        }
    }
}

// Integration into ConventionStorage.ts
export class ConventionStorage {
    private cache: ConventionCache;

    async listConventions(filter?: ConventionFilter): Promise<Convention[]> {
        const sources = await this.getSources();
        const allConventions: Convention[] = [];

        for (const source of sources) {
            // Use cache instead of direct file scan
            const conventions = await this.cache.getConventions(source.id);
            allConventions.push(...conventions);
        }

        return this.applyFilter(allConventions, filter);
    }
}
```

**Changes Required**:
- Create `ConventionCache.ts` (~150 lines)
- Update `ConventionStorage.ts` to use cache (~20 line change)
- Add cache invalidation on repository sync (~10 lines)
- Add filesystem watching for local directories (optional, ~50 lines)

**Expected Performance Improvement**:
- First search: ~50ms (no change - cache miss)
- Subsequent searches: ~5ms (10x faster - cache hit)
- Memory overhead: +5-10MB for cache
- Implementation time: 1 day

**Optimization Triggers** (when to implement more aggressive solutions):
- Convention set grows > 500 files
- Search latency consistently > 100ms
- User feedback indicates slowness
- Memory usage > 200MB

**Next Steps**:
1. ✅ Document Option D (complete)
2. ⏸️ Defer implementation until triggers met
3. ⏸️ Revisit after 6 months or when convention set > 300 files

---

#### Other Database Options Considered (Deferred)

**Option A: MongoDB Backend (Deferred)**
- Full-text search with indexes, rich query capabilities
- Rejected for now: Additional Docker container complexity, operational overhead, overkill for personal use
- Reconsider when: Convention set > 1000 files or team collaboration required

**Option B: SQLite with FTS5 (Deferred)**
- Embedded database, full-text search built-in, zero configuration
- Rejected for now: Current performance acceptable, adds file write complexity
- Reconsider when: Convention set > 500 files and persistent indexing needed

**Option C: Pre-computed Index Files (Deferred)**
- JSON index files committed with conventions, very fast lookups
- Rejected for now: Already using convention metadata, index rebuild overhead
- Reconsider when: Distribution to teams (include index in npm package)

---

#### Decision Summary: Question 2

**Final Decision**: Defer all optimization until performance triggers are met

**Rationale**:
- Current performance meets all targets (50ms search, 20ms retrieval)
- YAGNI principle: Don't optimize prematurely
- Option D (hybrid caching) is low-effort fallback if needed
- Focus effort on team-builder implementation instead

**Performance Monitoring**:
- Track search latency at 100, 300, 500, 1000 convention thresholds
- Implement Option D when latency > 100ms
- Implement database solution when latency > 500ms or team collaboration needed

---

## IMMEDIATE NEXT STEPS

### 1. Test Harness Observability Fixes
```bash
cd ~/Projects/claudeagentsdk-harness
docker compose down && docker compose up -d
# Verify: http://localhost:9090/targets
# Verify: http://localhost:3000
```

### 2. Configure Conventions MCP to Scan ABDotfiles
```yaml
# ~/.config/conventions-mcp/config.yaml
localDirectories:
  - id: personal
    path: ~/.claude
    enabled: true
    priority: 10
```

### 3. Implement Team-Builder (Priority: HIGH)
**Week 1: conventions-mcp (3 days)**
- [ ] Add `get_agent_configuration` MCP tool
- [ ] Add `search_agents_by_capability` MCP tool
- [ ] Add `validate_agent_compatibility` MCP tool
- [ ] Update agent frontmatter schema (add toolPermissions, mcpServers, capabilities)
- [ ] Test new tools via MCP protocol

**Week 2: harness (2 days)**
- [ ] Implement `WriteConfigTool` (write_config)
- [ ] Implement `ValidateConfigTool` (validate_config)
- [ ] Implement `ReloadHarnessTool` (reload_harness)
- [ ] Register custom tools with harness tool registry
- [ ] Unit test each tool

**Week 3: harness (4 days)**
- [ ] Create `config/agents/team-builder.yaml` configuration
- [ ] Implement TeamBuilderAgent initialization
- [ ] Wire up all 9 tools (3 built-in, 3 MCP, 3 custom)
- [ ] Test agent can call each tool
- [ ] Add system prompt for team-builder workflow

**Week 4: Integration (3 days)**
- [ ] End-to-end test: "Build FastAPI authentication endpoint"
- [ ] Verify all 5 steps work interactively
- [ ] Test error recovery (missing agents, invalid configs)
- [ ] Document team-builder usage patterns
- [ ] Create example workflow

### 4. Performance Monitoring (Priority: LOW - Defer)
- [ ] ⏸️ Create benchmark dataset (1000+ conventions)
- [ ] ⏸️ Measure search latency at scale
- [ ] ⏸️ Implement Option D if latency > 100ms
- [ ] ⏸️ Revisit after 6 months or when triggers met

---

## CONFIGURATION FILES

### ABDotfiles → ~/.claude/
```yaml
# ~/Projects/ABDotfiles/dotfiles.conf
llm/claude_code/.claude/CLAUDE.md:~/.claude/CLAUDE.md
llm/claude_code/.claude/agents:~/.claude/agents
llm/claude_code/.claude/commands:~/.claude/commands
llm/claude_code/.claude/specs:~/.claude/specs
llm/claude_code/.claude/skills:~/.claude/skills
```

### Conventions MCP Configuration
```yaml
# ~/.config/conventions-mcp/config.yaml
localDirectories:
  - id: personal
    path: ~/.claude
    enabled: true
    priority: 10  # Highest priority

  - id: project
    path: ./workspace/.conventions
    enabled: true
    priority: 5

repositories:
  - id: team-standards
    url: git@github.com:company/standards.git
    type: private
    authMethod: ssh
    priority: 7
    autoSync: true
    cacheTTL: 3600
```

### Harness Agent Configuration (Proposed)
```yaml
# ~/Projects/claudeagentsdk-harness/config/agents.yaml (NEW FILE)
agent_sources:
  - type: conventions_mcp
    priority: 1
    search_on_session_start: true

  - type: local_directory
    path: ~/.claude/agents
    priority: 2

session:
  context_cache_dir: ./memory/context
  max_cached_conventions: 50
  token_budget: 20000
```

---

## SUCCESS CRITERIA

### Phase 2 Complete When:
- ✅ Team-builder can assemble agent teams from conventions-mcp
- ✅ Harness loads agents dynamically (no hardcoded paths)
- ✅ Workflow templates executable via harness
- ✅ Single session can use multiple agents with context sharing
- ✅ Conventions-mcp performance < 100ms for searches with 1000+ conventions

### Metrics to Track:
- Search latency (p50, p95, p99)
- Agent startup time
- Token usage per session
- Cache hit ratio
- Memory footprint

---

## NOTES & DECISIONS

### October 28, 2025 - 3-Layer Architecture
**Decision**: Use layered approach with resources flowing from personal → dynamic → execution.

**Rationale**:
- Performance: Fast access via Layer 3 cache
- Ease of maintenance: Clear ownership per layer
- Modularity: Add sources to Layer 2 without changing Layers 1 or 3
- Extensibility: New resource types just need MCP integration

**Key Principle**: Resources flow from Layer 1 → Layer 2 → Layer 3, with each layer adding specificity and performance.

---

### October 28, 2025 - Team-Builder Architecture
**Decision**: TeamBuilderAgent with skills as tools (not separate Python modules)

**Rationale**:
- Agent autonomy: Agent orchestrates entire workflow using tools
- Consistent architecture: Everything is a tool the agent reasons about
- Error recovery: Agent can retry or adjust if assembly fails
- Follows Claude Agent SDK patterns: Tools are primary abstraction
- Testing: Can mock skills like any other tool

**Key Insight**: Skills should be tools given to the agent, not separate components it calls directly. This allows the agent to reason about when and how to use each tool based on context.

---

### October 28, 2025 - Performance Optimization Strategy
**Decision**: Defer all optimization until performance triggers are met

**Rationale**:
- Current performance already meets targets (50ms search)
- YAGNI principle: Don't optimize prematurely
- Option D (hybrid caching) provides low-effort fallback if needed
- Focus resources on team-builder implementation (higher value)

**Triggers for Optimization**:
- Convention set > 500 files
- Search latency > 100ms consistently
- User feedback indicates slowness
- Memory usage > 200MB

---

**Document Version**: 3.0
**Last Updated**: October 28, 2025
**Status**: Implementation plan finalized with detailed specifications

---

## Summary

This document defines the architecture and implementation plan for the AI-Assisted Development Framework, consisting of three interconnected repositories:

**Architectural Decisions Made**:
1. ✅ **3-Layer Resource Management**: Resources flow from ABDotfiles → conventions-mcp → harness
2. ✅ **Team-Builder Design**: Single agent (TeamBuilderAgent) with 9 tools orchestrates entire workflow
3. ✅ **Performance Strategy**: Defer optimization (YAGNI), focus on team-builder implementation

**Implementation Ready**:
- **Question 1 (Team-Builder)**: Detailed specs for 3 MCP tools, 3 custom skills, agent configuration
- **Question 2 (Performance)**: Option D documented, deferred until triggers met

**Next Actions**:
1. Implement 3 MCP tools in conventions-mcp (Week 1)
2. Implement 3 custom skill tools in harness (Week 2)
3. Configure and test TeamBuilderAgent (Weeks 3-4)

The framework is designed for extensibility, modularity, and performance, with clear separation of concerns between personal configuration (ABDotfiles), dynamic convention discovery (conventions-mcp), and agent execution (harness).
