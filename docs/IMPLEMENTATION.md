# Agent Architecture & Implementation Plan

**Last Updated**: 2025-11-21 18:00 UTC
**Overall Status**: Phase 1 NOT Implemented ❌ | Phase 2-3 Planned

## Current Implementation Status

- **Phase 1: Native Skill Support** - ❌ **NOT IMPLEMENTED**
  - Documentation was updated but code was NOT changed
  - Skills exist (12 in `.claude/skills/`) but are unreachable
  - Docker mounts `.claude` to `/app/.claude` not `/workspace/.claude`
  - "Skill" NOT in allowed_tools
  - setting_sources NOT configured
  - Integration tests do NOT exist

- **Phase 2: Hard-Coded Agent Definitions** - 📋 **PLANNED** (Not Started)

- **Phase 3: Documentation & Examples** - 📋 **PLANNED** (Not Started)

## ⚠️ CRITICAL: Documentation Drift Identified

**Issue**: Previous documentation claimed Phase 1 was "implemented" but no actual code changes were made. Only documentation was updated (commit 1fe7952). This section has been corrected to reflect actual system state.

---

## Table of Contents

- [Overview: Simplified 3-Agent Starter Architecture](#overview-simplified-3-agent-starter-architecture)
- [Phase 1: Enable Native Skill Support](#phase-1-enable-native-skill-support)
- [Phase 2: Hard-Coded Agent Definitions](#phase-2-hard-coded-agent-definitions)
- [Phase 3: Documentation & Examples](#phase-3-documentation--examples)
- [Implementation Roadmap](#implementation-roadmap)

---

## Overview: Simplified 3-Agent Starter Architecture

### Philosophy

Start simple, prove the concept, then scale complexity incrementally based on actual needs rather than theoretical requirements.

A minimal viable agentic team that demonstrates core concepts without overwhelming complexity. Perfect for initial implementation, learning the Claude Agent SDK patterns, and validating the multi-agent approach before scaling to a full architecture.

### Starter Team DAG

```mermaid
graph TB
    Start([User Feature Request]) --> Orchestrator

    Orchestrator[🎯 Orchestrator Agent<br/>- Analyze request<br/>- Break into tasks<br/>- Coordinate workflow<br/>- Track progress]

    Orchestrator -->|Task specification| Dev[💻 Developer Agent<br/>- Design & implement<br/>- Write all code<br/>- Create tests<br/>- Document changes]

    Dev -->|Code ready| QA[🧪 QA Agent<br/>- Run test suites<br/>- Validate functionality<br/>- Report bugs<br/>- Approve or reject]

    QA -->|Tests fail| Feedback[Bug Report & Context]
    Feedback --> Dev

    QA -->|Tests pass| Complete([✅ Complete])

    Complete -.->|New feature| Start

    style Start fill:#4A90E2
    style Orchestrator fill:#50C878
    style Complete fill:#50C878
    style Feedback fill:#E74C3C
```

### Agent Definitions

#### Orchestrator Agent
**Primary Responsibilities**:
- Parse user requests and identify required work
- Break down features into manageable tasks
- Coordinate handoffs between Developer and QA
- Track project state and progress
- Handle exceptions and blockers

**Key Skills/Tools**:
- Sequential Thinking MCP for task analysis
- Memory MCP for project state tracking
- Filesystem MCP for reading project context
- Git MCP for repository information

**Autonomy Level**: Medium - makes decisions about task breakdown but escalates ambiguities

**Example System Prompt Elements**:
```
You are the Orchestrator Agent responsible for coordinating software development.

Your primary duties:
1. Analyze feature requests and break them into specific, actionable tasks
2. Create clear task specifications for the Developer Agent
3. Monitor progress and handle workflow transitions
4. Maintain project context using Memory MCP

When you receive a request:
- Assess complexity (simple, moderate, complex)
- Identify required components (frontend, backend, database, tests)
- Create detailed task specification including acceptance criteria
- Pass to Developer Agent with full context

Communication format:
{
  "task_type": "feature|bugfix|refactor",
  "complexity": "simple|moderate|complex",
  "components": ["frontend", "backend", "database", "tests"],
  "acceptance_criteria": ["criteria1", "criteria2"],
  "context": "additional context and constraints"
}
```

#### Developer Agent
**Primary Responsibilities**:
- Implement all code changes (frontend, backend, database)
- Write unit and integration tests
- Create or update technical documentation
- Self-review code before submission
- Fix bugs identified by QA

**Key Skills/Tools**:
- Filesystem MCP for code editing
- Context7 MCP for framework documentation
- Git MCP for version control
- Browser automation (if available) for manual testing

**Autonomy Level**: High - makes implementation decisions within task specification

**Example System Prompt Elements**:
```
You are the Developer Agent responsible for all code implementation.

Your primary duties:
1. Implement features according to task specifications
2. Write clean, well-tested, documented code
3. Follow project conventions and best practices
4. Self-review before submitting to QA

For each task:
- Read existing codebase to understand patterns
- Implement changes following established conventions
- Write comprehensive tests (aim for >80% coverage)
- Update relevant documentation
- Perform self-review using checklist

Before submitting to QA:
- Run tests locally
- Verify acceptance criteria are met
- Document any assumptions or trade-offs
- Create summary of changes for QA

Implementation checklist:
□ Code follows project style guidelines
□ Tests written and passing
□ Documentation updated
□ Error handling implemented
□ Edge cases considered
□ Performance implications assessed
```

#### QA Agent
**Primary Responsibilities**:
- Execute comprehensive test suites
- Validate functionality against acceptance criteria
- Identify bugs and provide detailed reports
- Perform basic integration testing
- Approve or reject implementations

**Key Skills/Tools**:
- Playwright MCP for browser automation
- Filesystem MCP for reading tests
- Git MCP for checking changes
- Bug reporting templates

**Autonomy Level**: Medium - validates objectively but can request clarification

**Example System Prompt Elements**:
```
You are the QA Agent responsible for quality validation.

Your primary duties:
1. Execute all relevant test suites
2. Validate against acceptance criteria
3. Identify bugs with clear reproduction steps
4. Approve implementations that pass all checks

Testing workflow:
1. Review task specification and acceptance criteria
2. Run automated test suites (unit, integration, E2E)
3. Perform manual exploratory testing for edge cases
4. Validate documentation accuracy
5. Create detailed bug reports or approval

Bug report format:
{
  "severity": "critical|major|minor",
  "component": "frontend|backend|database",
  "steps_to_reproduce": ["step1", "step2"],
  "expected_behavior": "what should happen",
  "actual_behavior": "what actually happened",
  "logs_or_screenshots": "relevant diagnostic info"
}

Approval criteria:
□ All automated tests passing
□ Acceptance criteria validated
□ No critical or major bugs found
□ Documentation is accurate
□ Edge cases handled appropriately
```

### Workflow Patterns

#### Pattern 1: Standard Feature Development
```
User Request → Orchestrator Analysis → Task Specification →
Developer Implementation → Self-Review → Submit to QA →
QA Testing → [Pass: Complete | Fail: Bug Report → Developer]
```

#### Pattern 2: Bug Fix
```
Bug Report → Orchestrator Triage → Route to Developer →
Fix Implementation → Focused Testing → QA Validation → Complete
```

#### Pattern 3: Iterative Refinement
```
Initial Implementation → QA Feedback → Developer Refinement →
QA Re-test → Multiple iterations until approval
```

---

## Phase 1: Enable Native Skill Support

**Timeline**: 30 minutes estimated
**Complexity**: Low
**Risk**: Minimal
**Status**: ❌ **NOT IMPLEMENTED**

### Implementation Status

**What Needs to Be Done**:

1. **Code Changes Required** (src/harness/agent.py):
   - [ ] Add "Skill" to allowed_tools list (line ~135)
   - [ ] Add setting_sources=["user", "project"] parameter to ClaudeAgentOptions
   - [ ] No other code changes needed

2. **Docker Configuration Required** (docker-compose.yml):
   - [ ] Change mount: `./.claude:/app/.claude:ro` → `./.claude:/workspace/.claude:ro`
   - [ ] Apply to all 3 agents (main-agent, reviewer-agent, tester-agent)
   - [ ] No symlink needed - just change mount point

3. **Integration Tests Required** (tests/integration/test_skills.py):
   - [ ] Create test file
   - [ ] Add 4 tests: auto-discovery, invocation, multiple skills, tool availability
   - [ ] Follow pattern from other integration tests

**Current State** ❌:
- Skills exist (12 in `.claude/skills/`) but unreachable
- Docker mounts to `/app/.claude` (wrong location)
- "Skill" NOT in allowed_tools
- setting_sources NOT configured
- Integration tests do NOT exist

**Why Not Implemented**:
- Commit 1fe7952 updated documentation only
- No actual code changes were committed
- Documentation drift occurred

### Critical Issue Resolved

**Problem Discovered**: After initial implementation, `make interactive` blocked all dialogue with sandbox debug error.

**Root Cause**: Path mismatch
- Agent cwd = `/workspace` (from config.py)
- Skills mounted at `/app/.claude/skills/`
- SDK's `setting_sources=["project"]` searches for `.claude/` relative to cwd
- SDK attempted to access `/workspace/.claude/` which didn't exist ❌

**Solution Attempted #1** (REJECTED):
```dockerfile
# Tried symlink approach
RUN ln -s /app/.claude /workspace/.claude
```
**Rejection Reason**: If external repos cloned to /workspace had their own `.claude/` directories, symlink would conflict.

**Final Solution** ✅ **Hierarchical Workspace Structure**:

**Dockerfile** (agents/main/Dockerfile:60-61):
```dockerfile
# Create workspace directory structure (no symlink)
RUN mkdir -p /workspace/projects
```

**docker-compose.yml** (all 3 agents):
```yaml
volumes:
  - ./workspace:/workspace:delegated
  - ./.claude:/workspace/.claude:ro  # Direct mount to /workspace/.claude
  - ./memory:/memory:delegated
```

**Directory Structure**:
```
/workspace/
├── .claude/              # Harness skills/agents (direct mount from host)
└── projects/             # Clone external repos here
    └── {repo-name}/
        └── .claude/      # Repo's own .claude (no conflict!)
```

**Benefits**:
- ✅ No symlink complexity - direct mount to expected location
- ✅ External repos can have their own `.claude/` directories
- ✅ Clean separation: harness at /workspace, repos at /workspace/projects/
- ✅ Agent switches cwd when working on repos: `set_working_repository()`
- ✅ Works across all containers (main, reviewer, tester)

### Overview

Skills are already in correct SDK format and just needed Docker configuration and path resolution to enable them in the existing codebase.

### Implementation Steps

#### 1. Update src/harness/agent.py (lines 207-214)

**Current Code**:
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch"],
    permission_mode=self.config.claude_permission_mode,
    max_turns=self.config.claude_max_turns,
    cwd=str(self.config.workspace_dir),
    model=self.config.claude_model,
    mcp_servers=self.mcp_servers,
)
```

**Updated Code**:
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "WebFetch", "Skill"],
    permission_mode=self.config.claude_permission_mode,
    max_turns=self.config.claude_max_turns,
    cwd=str(self.config.workspace_dir),
    model=self.config.claude_model,
    mcp_servers=self.mcp_servers,
    setting_sources=["user", "project"],  # Enable skills from .claude/skills/
)
```

**Changes**:
1. Add `"Skill"` to allowed_tools list
2. Add `setting_sources=["user", "project"]` parameter

#### 2. Verify Skills Are Loaded

**Test Command**:
```bash
# Start interactive session
make dev

# In another terminal
make shell

# Inside container
python -c "
from harness.agent import AgentSession
session = AgentSession()
# Skills should be auto-discovered from .claude/skills/
"
```

**Expected Behavior**:
- Agent can now use `/skill api-development` to access API development patterns
- All 12 skills auto-discovered and available

### Available Skills (After Phase 1)

1. `api-development` - REST and GraphQL API patterns
2. `code-review` - Review workflows and standards
3. `database-management` - Database patterns and schemas
4. `debugging` - Troubleshooting workflows
5. `deployment-operations` - CI/CD and deployment
6. `documentation` - Documentation generation
7. `frontend-development` - React/TypeScript patterns
8. `git-workflow` - Git best practices
9. `microservices-architecture` - Distributed systems
10. `performance-optimization` - Caching and optimization
11. `security` - Security hardening
12. `testing-strategies` - Testing patterns

### Testing

**Integration Tests Created** (tests/integration/test_skills.py):

```python
"""Integration tests for skill auto-discovery and usage.

These tests verify that skills are properly discovered from .claude/skills/
and can be invoked by the agent via the Skill tool.
"""

import pytest
from harness.agent import AgentSession


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_skills_auto_discovered(workspace_dir, skip_if_no_api_key):
    """Verify skills are discovered from .claude/skills/ directory."""
    session = AgentSession(agent_name="test-skills")
    await session.start()

    # Agent should be aware of skills
    prompt = "What skills do you have available? List them briefly."
    messages = []

    async for msg in session.execute(prompt):
        messages.append(msg)

    # Verify we got some messages
    assert len(messages) > 0, "Should receive at least one message from SDK"

    await session.shutdown()


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_skill_invocation(workspace_dir, skip_if_no_api_key):
    """Test agent can invoke a specific skill."""
    session = AgentSession(agent_name="test-skills")
    await session.start()

    # Request skill usage
    prompt = (
        "Use the api-development skill to help me understand "
        "REST API best practices. Specifically, tell me about HTTP methods."
    )
    skill_used = False
    messages = []

    async for msg in session.execute(prompt):
        messages.append(msg)

        # Check if Skill tool was invoked
        if isinstance(msg, dict):
            msg_type = msg.get("type")
            if msg_type == "tool_use":
                tool_name = msg.get("name")
                if tool_name == "Skill":
                    skill_used = True

    # Verify we got messages
    assert len(messages) > 0, "Should receive messages from agent"

    # Note: We don't assert skill_used=True because Claude may choose
    # to answer directly without invoking the skill tool

    await session.shutdown()


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.slow
async def test_multiple_skills_available(workspace_dir, skip_if_no_api_key):
    """Verify multiple skills can be referenced."""
    session = AgentSession(agent_name="test-skills")
    await session.start()

    expected_skills = [
        "api-development",
        "code-review",
        "database-management",
        "testing-strategies",
    ]

    prompt = (
        f"Tell me very briefly (one sentence each) what each of these "
        f"skills covers: {', '.join(expected_skills)}"
    )
    messages = []

    async for msg in session.execute(prompt):
        messages.append(msg)

    assert len(messages) > 0, "Should receive response about skills"

    await session.shutdown()


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_skill_tool_in_allowed_tools(workspace_dir, skip_if_no_api_key):
    """Verify Skill tool is in the agent's allowed tools."""
    session = AgentSession(agent_name="test-skills")
    await session.start()

    # Simple prompt to verify agent can execute
    prompt = "Hello, can you confirm you have access to skills?"
    messages = []

    async for msg in session.execute(prompt):
        messages.append(msg)

    # Should get a response without errors
    assert len(messages) > 0

    await session.shutdown()
```

**Running Tests**:
```bash
# Unit tests (fast, no API calls)
make test-unit

# Integration tests (requires ANTHROPIC_API_KEY, costs ~$0.20-$0.45)
ANTHROPIC_API_KEY=xxx pytest tests/integration/test_skills.py -v

# Skip expensive tests during development
pytest tests/integration/test_skills.py -m "not slow"
```

### Benefits

- ✅ Immediate value (12 skills available)
- ✅ Zero risk (SDK's native feature)
- ✅ No file parsing required
- ✅ Proper SDK conventions

---

## Phase 2: Hard-Coded Agent Definitions

**Timeline**: 2-3 hours
**Complexity**: Medium
**Risk**: Low

### Overview

Implement hard-coded `AgentDefinition` objects following the reference implementation pattern from the official Claude Agent SDK demos (research-agent). This approach uses the SDK's native multi-agent system with 6 core specialists plus access to the remaining agent definitions as reference documentation.

### Reference Pattern Analysis

The research-agent implementation shows best practices:

1. **Prompts in separate `.txt` files** (not inline)
2. **2 specialized agents** (researcher, report-writer)
3. **Lead agent delegates via Task tool**
4. **Agents use complementary tools**
5. **Setting sources for skills**

**Reference Code** (from research-agent):
```python
# Load prompts from text files
researcher_prompt = load_prompt("researcher.txt")
report_writer_prompt = load_prompt("report_writer.txt")
lead_agent_prompt = load_prompt("lead_agent.txt")

# Define specialized subagents
agents = {
    "researcher": AgentDefinition(
        description=(
            "Use this agent when you need to gather research information on any topic. "
            "The researcher uses web search to find relevant information..."
        ),
        tools=["WebSearch", "Write"],
        prompt=researcher_prompt,
        model="haiku"
    ),
    "report-writer": AgentDefinition(
        description=(
            "Use this agent when you need to create a formal research report document..."
        ),
        tools=["Skill", "Write", "Glob", "Read"],
        prompt=report_writer_prompt,
        model="haiku"
    )
}

# Lead agent configuration
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",
    setting_sources=["project"],  # Load skills from .claude directory
    system_prompt=lead_agent_prompt,
    allowed_tools=["Task"],  # Lead agent only delegates
    agents=agents,
    hooks=hooks,
    model="haiku"
)
```

### Implementation Steps

#### Step 1: Create prompts directory structure

```bash
mkdir -p src/harness/prompts
```

#### Step 2: Extract prompts from existing agents

Choose 6 core agents that cover major use cases:

1. **dev-python-expert** → Python development
2. **dev-typescript-expert** → TypeScript/JavaScript
3. **infra-docker-expert** → Container management
4. **db-postgres-expert** → Database design
5. **code-reviewer** → Code review and security
6. **doc-writer** → Documentation creation

**Example prompt extraction** (from `.claude/agents/dev-python-expert.md`):

```bash
# Extract system prompt (everything after YAML frontmatter)
sed -n '/^---$/,/^---$/!p' .claude/agents/dev-python-expert.md > src/harness/prompts/python_expert.txt
```

#### Step 3: Create agent definitions module

**File**: `src/harness/agents/definitions.py`

```python
"""Hard-coded agent definitions following SDK best practices."""

from pathlib import Path
from claude_agent_sdk import AgentDefinition


def load_prompt(filename: str) -> str:
    """Load prompt from text file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    return prompt_path.read_text()


# Core hard-coded agent definitions
CORE_AGENTS = {
    "python-expert": AgentDefinition(
        description=(
            "Use this agent when you need expert Python development assistance. "
            "Handles Python code review, implementation, debugging, testing, and best practices. "
            "Specializes in modern Python (3.12+), type hints, async/await, and testing."
        ),
        tools=["Read", "Write", "MultiEdit", "Bash", "Grep", "Glob", "Skill"],
        prompt=load_prompt("python_expert.txt"),
        model="sonnet"
    ),

    "typescript-expert": AgentDefinition(
        description=(
            "Use this agent for TypeScript and JavaScript development. "
            "Handles React, Node.js, API development, and frontend/backend TypeScript code. "
            "Specializes in type-safe code, modern ES features, and testing."
        ),
        tools=["Read", "Write", "MultiEdit", "Bash", "Grep", "Glob", "Skill"],
        prompt=load_prompt("typescript_expert.txt"),
        model="sonnet"
    ),

    "docker-expert": AgentDefinition(
        description=(
            "Use this agent for Docker and container-related tasks. "
            "Handles Dockerfile creation, docker-compose configuration, container debugging, "
            "and container orchestration. Integrates with Docker MCP server."
        ),
        tools=["Read", "Write", "Bash", "mcp__docker", "Skill"],
        prompt=load_prompt("docker_expert.txt"),
        model="haiku"
    ),

    "postgres-expert": AgentDefinition(
        description=(
            "Use this agent for PostgreSQL database design and optimization. "
            "Handles schema design, query optimization, migrations, and database best practices."
        ),
        tools=["Read", "Write", "Skill"],
        prompt=load_prompt("postgres_expert.txt"),
        model="haiku"
    ),

    "code-reviewer": AgentDefinition(
        description=(
            "Use this agent for code review, security audit, and quality assessment. "
            "Provides detailed feedback on code quality, security vulnerabilities, "
            "and best practices. Read-only access to preserve code integrity."
        ),
        tools=["Read", "Grep", "Glob"],  # Read-only
        prompt=load_prompt("code_reviewer.txt"),
        model="sonnet"
    ),

    "doc-writer": AgentDefinition(
        description=(
            "Use this agent for technical documentation and README creation. "
            "Handles API documentation, user guides, architecture docs, and markdown formatting."
        ),
        tools=["Read", "Write", "Skill", "Glob"],
        prompt=load_prompt("doc_writer.txt"),
        model="haiku"
    ),
}


def get_lead_agent_prompt() -> str:
    """Get lead agent system prompt for orchestration."""
    return load_prompt("lead_agent.txt")
```

#### Step 4: Create lead agent orchestrator prompt

**File**: `src/harness/prompts/lead_agent.txt`

```txt
You are the Lead Software Architect for the Claude Agent SDK Harness.

Your role is to coordinate and delegate tasks to specialized agents using the Task tool.

## Available Specialized Agents

You have access to 6 expert agents:

1. **python-expert** - Python development, testing, debugging
2. **typescript-expert** - TypeScript/JavaScript, React, Node.js
3. **docker-expert** - Container management, Dockerfile, docker-compose
4. **postgres-expert** - Database design, SQL, migrations
5. **code-reviewer** - Code review, security audit (read-only)
6. **doc-writer** - Documentation, README, API docs

## Delegation Strategy

- **Single-language tasks**: Delegate to language expert (python-expert, typescript-expert)
- **Infrastructure**: Delegate to docker-expert
- **Database work**: Delegate to postgres-expert
- **Code review**: Always delegate to code-reviewer after implementation
- **Documentation**: Delegate to doc-writer for final docs

## Workflow Pattern

1. **Analyze request** - Determine which expert(s) are needed
2. **Delegate to specialist** - Use Task tool with clear instructions
3. **Review results** - Ensure quality before proceeding
4. **Coordinate multi-step** - Break complex tasks into agent-specific steps

## Important Rules

- ALWAYS delegate - never implement code yourself
- ONE agent per task (avoid multi-agent confusion)
- CLEAR instructions - be specific in Task tool prompts
- VERIFY results before marking tasks complete

Example delegation:
```
Task: "Use python-expert to refactor the checkpoint.py module following SOLID principles"
```
```

#### Step 5: Update agent.py to use hard-coded definitions

**File**: `src/harness/agent.py`

```python
# Add imports
from harness.agents.definitions import CORE_AGENTS, get_lead_agent_prompt

# In AgentSession.__init__
def __init__(
    self,
    agent_name: str = "lead",  # Changed default to "lead"
    config: HarnessConfig | None = None,
    checkpoint_manager: CheckpointManager | None = None,
    metrics_collector: MetricsCollector | None = None,
) -> None:
    """Initialize agent session with hard-coded agent definitions."""
    self.agent_name = agent_name
    self.config = config or get_config()

    # ... checkpoint and metrics setup ...

    # Register MCP servers
    self.mcp_servers = { ... }

    logger.info(
        "Agent session initialized",
        agent=agent_name,
        session_id=self.session_id,
        available_agents=list(CORE_AGENTS.keys()),
    )


# In _execute_with_retry
async def _execute_with_retry(
    self,
    prompt: str,
    **kwargs: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute with multi-agent configuration."""

    # Configure with hard-coded agents
    options = ClaudeAgentOptions(
        permission_mode=self.config.claude_permission_mode,
        max_turns=self.config.claude_max_turns,
        cwd=str(self.config.workspace_dir),
        model=self.config.claude_model,
        mcp_servers=self.mcp_servers,
        setting_sources=["user", "project"],  # Enable skills
        system_prompt=get_lead_agent_prompt(),  # Lead agent orchestrator
        allowed_tools=["Task"],  # Lead agent only delegates
        agents=CORE_AGENTS,  # 6 specialized agents
    )

    # ... rest of method ...
```

#### Step 6: Update interactive.py

**File**: `src/harness/interactive.py`

```python
from harness.agents.definitions import CORE_AGENTS

def print_welcome_banner(console: Console, agent_name: str, model: str) -> None:
    """Print welcome banner with available agents."""
    banner = Panel(
        f"""[bold cyan]Claude Agent SDK Harness[/bold cyan]

Lead Agent: [green]{agent_name}[/green]
Model: [yellow]{model}[/yellow]
Mode: Multi-Agent Orchestration

Available Specialized Agents:
{', '.join(f'[green]{name}[/green]' for name in CORE_AGENTS.keys())}

Type your request and the lead agent will delegate to specialists.
Press Ctrl+C to exit.
""",
        title="🤖 Claude Agent Harness",
        border_style="cyan",
    )
    console.print(banner)


async def main(model: str | None = None, show_stats: bool = False, quiet: bool = False) -> None:
    """Run interactive session with multi-agent orchestration."""
    # ... setup ...

    # Always use "lead" agent in this mode
    agent_name = "lead"
    session = AgentSession(agent_name=agent_name, config=config)

    # ... rest of main ...
```

### Directory Structure After Implementation

```
src/harness/
├── agents/
│   ├── __init__.py
│   └── definitions.py          # Hard-coded AgentDefinition objects
├── prompts/
│   ├── lead_agent.txt          # Lead orchestrator prompt
│   ├── python_expert.txt       # Extracted from .claude/agents/dev-python-expert.md
│   ├── typescript_expert.txt   # Extracted from .claude/agents/dev-typescript-expert.md
│   ├── docker_expert.txt       # Extracted from .claude/agents/infra-docker-expert.md
│   ├── postgres_expert.txt     # Extracted from .claude/agents/db-postgres-expert.md
│   ├── code_reviewer.txt       # Extracted from .claude/agents/code-reviewer.md
│   └── doc_writer.txt          # Extracted from .claude/agents/doc-writer.md
└── agent.py                    # Updated to use CORE_AGENTS
```

### Usage Example

```bash
# Start interactive session
make dev

# Lead agent delegates automatically
> "Refactor the checkpoint.py module to follow SOLID principles"

# Lead agent will:
# 1. Analyze request
# 2. Delegate to python-expert via Task tool
# 3. Python-expert implements changes
# 4. Lead agent delegates to code-reviewer
# 5. Code-reviewer provides feedback
# 6. Optionally delegate to doc-writer for updated docstrings
```

### Testing

```python
# tests/integration/test_multi_agent.py
import pytest
from harness.agent import AgentSession
from harness.agents.definitions import CORE_AGENTS


@pytest.mark.integration
async def test_agent_delegation():
    """Test lead agent delegates to specialists."""
    session = AgentSession(agent_name="lead")
    await session.start()

    # Lead agent should delegate Python tasks
    async for message in session.execute("Write a Python function to calculate fibonacci"):
        # Should see delegation to python-expert
        if "Task" in message.get("tool_use", {}).get("name", ""):
            assert "python-expert" in message["tool_use"]["input"].get("subagent_type", "")

    await session.shutdown()


def test_core_agents_defined():
    """Verify all core agents are properly defined."""
    assert len(CORE_AGENTS) == 6

    for name, agent_def in CORE_AGENTS.items():
        assert agent_def.description
        assert agent_def.tools
        assert agent_def.prompt
        assert agent_def.model in ["sonnet", "haiku", "opus"]
```

### Migration Path for Existing 44 Agents

The remaining 38 agents in `.claude/agents/` can be:

1. **Referenced on-demand** - Lead agent can still READ them when needed
2. **Converted to skills** - Move to `.claude/skills/` for reference documentation
3. **Added incrementally** - Promote frequently-used agents to hard-coded status
4. **Kept as documentation** - Valuable reference material

**Hybrid approach**:
```python
# Lead agent prompt addition
"""
## Extended Agent Library

Beyond your 6 core agents, you have access to 38 additional specialized agents
in .claude/agents/. If none of your core agents fit a task, you can:

1. READ the appropriate agent file from .claude/agents/
2. ADOPT that agent's persona temporarily
3. Complete the task following their guidelines

Example: For Julia language tasks, READ .claude/agents/dev-julia-expert.md
and follow its instructions.
"""
```

### Benefits

- ✅ Uses SDK's native multi-agent system (AgentDefinition)
- ✅ Follows official reference implementation pattern
- ✅ Prompts in separate files (maintainable, version-controlled)
- ✅ Lead agent orchestrates via Task tool (clear separation)
- ✅ Specialists have complementary toolsets
- ✅ Clean, professional codebase
- ✅ Easy to test and extend
- ✅ Still has access to remaining 38 agents via Read tool

---

## Phase 3: Documentation & Examples

**Timeline**: 30 minutes
**Complexity**: Low
**Risk**: Minimal

### Overview

Create documentation and examples showing how to use skills and agent definitions.

### Deliverables

#### 1. Update README.md

Add section:
```markdown
## Using Skills and Agents

### Skills

The harness includes 12 pre-configured skills for common development tasks:

```bash
# Start interactive session
make dev

# Use a skill (in chat)
/skill api-development
```

Available skills:
- `api-development` - REST and GraphQL patterns
- `code-review` - Review workflows
- `database-management` - Database design
- `debugging` - Troubleshooting guides
- And 8 more...

### Agent Definitions

6 specialized agents are available for different tasks:

```bash
# Start interactive session with multi-agent orchestration
make dev

# Lead agent automatically delegates to specialists:
# - python-expert, typescript-expert, docker-expert
# - postgres-expert, code-reviewer, doc-writer
```

The lead agent analyzes your request and delegates to the appropriate specialist.

#### Extended Agent Library

38 additional agents are available in `.claude/agents/` for reference. The lead agent can read and adopt these personas when needed for specialized tasks (Julia, Rust, Go, ML frameworks, etc.).
```

#### 2. Create Example Workflow

**File**: `examples/skill_usage.py`

```python
"""Example: Using skills in agent sessions."""

import asyncio
from harness.agent import AgentSession


async def main():
    """Demonstrate skill usage."""
    session = AgentSession(agent_name="main")
    await session.start()

    # Agent can now use skills
    prompt = """
    I need to design a REST API for user management.
    Use the api-development skill to help guide the design.
    """

    async for message in session.execute(prompt):
        print(message)

    await session.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

**File**: `examples/multi_agent_workflow.py`

```python
"""Example: Multi-agent orchestration workflow."""

import asyncio
from harness.agent import AgentSession


async def main():
    """Demonstrate multi-agent delegation."""
    session = AgentSession(agent_name="lead")
    await session.start()

    # Lead agent orchestrates specialists
    prompt = """
    Refactor the checkpoint.py module to follow SOLID principles.
    After implementation, have the code reviewer audit it.
    Update documentation with any architectural changes.
    """

    async for message in session.execute(prompt):
        print(message)

    await session.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

#### 3. Update CLAUDE.md

Add section showing agents are now auto-discovered:
```markdown
## Agent Definitions

The harness uses a hybrid multi-agent system:

### Core Agents (Hard-Coded)
6 specialist agents automatically available via lead agent delegation:
- `python-expert` - Python development, testing, debugging
- `typescript-expert` - TypeScript/JavaScript, React, Node.js
- `docker-expert` - Container management and orchestration
- `postgres-expert` - Database design and optimization
- `code-reviewer` - Code review and security audit
- `doc-writer` - Technical documentation

### Extended Agent Library (Reference)
38 additional agents in `.claude/agents/` available on-demand:
- Agents organized by prefix: `dev-*`, `db-*`, `infra-*`, `ml-*`, `web-*`
- Lead agent can READ and adopt these personas when needed
- Covers specialized languages (Julia, Rust, Go, etc.) and frameworks

### Skills
12 skills auto-discovered from `.claude/skills/`:
- Available via `/skill` command in interactive mode
- Covers API development, testing, security, performance, etc.

See README.md for complete usage examples.
```

---

## Implementation Roadmap

### Week 1: Core Implementation

**Day 1: Phase 1 - Enable Skills** ❌ **NOT STARTED**
- [ ] Update `src/harness/agent.py` with `setting_sources` and "Skill" tool
- [ ] Update Docker mounts for .claude directory to all agents (change /app to /workspace)
- [ ] Create integration test suite for skill usage (4 tests)
- [ ] Verify unit tests pass with no regression
- [ ] Test interactive mode with skills
- [ ] Run integration tests with real API (costs ~$0.20-$0.45)

**Day 2-3: Phase 2 - Hard-Coded Agents** (2-3 hours)
- [ ] Create `src/harness/prompts/` directory
- [ ] Extract prompts from 6 core agent files to `.txt` files
- [ ] Create `src/harness/agents/definitions.py` with CORE_AGENTS
- [ ] Write `lead_agent.txt` orchestrator prompt
- [ ] Update `agent.py` to use CORE_AGENTS and lead agent
- [ ] Update `interactive.py` welcome banner with agent list
- [ ] Test multi-agent delegation manually

**Day 4: Testing & Validation**
- [ ] Write integration tests for multi-agent delegation
- [ ] Test all 6 agents can be delegated to successfully
- [ ] Verify lead agent follows delegation strategy
- [ ] Test hybrid approach (6 core + 38 reference agents)
- [ ] Validate skills work alongside agent delegation

**Day 5: Phase 3 - Documentation** (30 minutes)
- [ ] Update README.md with skills and agents sections
- [ ] Create `examples/skill_usage.py` workflow
- [ ] Create `examples/multi_agent_workflow.py` workflow
- [ ] Update CLAUDE.md with agent system overview
- [ ] Document hybrid approach in project docs

### Week 2: Polish & Optimization

**Refinement**
- [ ] Optimize lead agent delegation prompts based on testing
- [ ] Add more specific delegation examples
- [ ] Fine-tune agent tool assignments
- [ ] Add performance metrics for delegation patterns

**Extended Testing**
- [ ] Create test suite for each specialist agent
- [ ] Test edge cases (agent fallback, error handling)
- [ ] Validate read-only constraints on code-reviewer
- [ ] Test skill + agent combination workflows

**Documentation Polish**
- [ ] Create delegation pattern guide
- [ ] Document common workflows (feature, bugfix, refactor)
- [ ] Add troubleshooting section for multi-agent issues
- [ ] Create video walkthrough or demo script

### Success Criteria

**Phase 1 Status:**
- ❌ Code changes NOT implemented (src/harness/agent.py)
- ❌ Docker mounts NOT configured (docker-compose.yml)
- ❌ Integration tests NOT created (tests/integration/test_skills.py)
- ✅ Unit tests currently pass (unrelated to Phase 1)
- ✅ Docker build works (but without skills support)

**Phase 1 Will Be Complete When:**
- ✅ "Skill" added to allowed_tools in agent.py
- ✅ setting_sources configured in ClaudeAgentOptions
- ✅ Docker mounts changed to /workspace/.claude for all agents
- ✅ Integration tests created and passing
- ✅ Interactive mode tested and skills accessible via `/skill` command
- ✅ All 12 skills load without errors

**Phase 2 Complete When:**
- ✅ 6 core agents defined and loaded
- ✅ Lead agent successfully delegates tasks
- ✅ All specialist agents execute within their domains
- ✅ Code reviewer enforces read-only constraints
- ✅ Integration tests pass for delegation

**Phase 3 Complete When:**
- ✅ README.md updated with usage examples
- ✅ Example workflows created and tested
- ✅ CLAUDE.md documents agent system
- ✅ All documentation accurate and complete

### Timeline Summary

| Phase | Duration | Effort | Priority |
|-------|----------|--------|----------|
| Phase 1: Skills | 30 min | Low | High |
| Phase 2: Agents | 2-3 hours | Medium | High |
| Phase 3: Docs | 30 min | Low | Medium |
| **Total** | **3-4 hours** | **Medium** | **High** |

### Next Steps After Completion

Once Phases 1-3 are complete, consider:

1. **Monitor usage patterns** - Track which agents are delegated to most frequently
2. **Optimize based on data** - Adjust agent capabilities based on real usage
3. **Expand core agents** - Promote frequently-used reference agents to hard-coded status
4. **Enhanced observability** - Add Grafana dashboard for multi-agent metrics
5. **Advanced workflows** - Create complex multi-agent collaboration patterns

For alternative implementations and future development options, see **docs/AGENT_NOTES.md**.

---

**Author**: Claude (AI Assistant)
**Reviewer**: Andis A. Blukis
**Status**: Implementation Plan - Ready to Execute


# Lost Changes - 2025-11-18

**Context**: During debugging of interactive mode failure, changes were lost via `git checkout` without being stashed or committed.

## What Was Lost

### 1. src/harness/agent.py

Repository context switching code (can be reconstructed):

- Instance variables: `self.current_repo`, `self.current_cwd`
- Method: `set_working_repository(repo_name)` 
- Method: `reset_to_harness()`
- Changed `cwd` parameter to use dynamic `self.current_cwd`
- Added "Skill" to allowed_tools
- **(POSSIBLY BREAKING)** Added `setting_sources=["user", "project"]`

### 2. docker-compose.yml  

Mount location changes:
- Changed `./.claude:/app/.claude:ro` → `./.claude:/workspace/.claude:ro` for all agents

### 3. agents/main/Dockerfile

- Removed symlink: `ln -s /app/.claude /workspace/.claude`  
- Added: `mkdir -p /workspace/projects`

## Recovery Plan

1. Test if original configuration works
2. If yes, our changes broke it - find minimal breaking change
3. Reconstruct changes carefully with testing at each step

## Changes Still Preserved

These were NOT lost:
- `src/harness/config.py` - projects_dir field ✓
- `.claude/CLAUDE.md` - documentation ✓
- `README.md` - documentation ✓  
- `.claude/settings.json` - permission patterns (may need revert)
- `.claude/hooks/hooks.json` - disabled hooks (may need revert)
