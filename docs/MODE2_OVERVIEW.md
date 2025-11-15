# Mode 2: Autonomous Long-Running Sessions - Overview

**Last Updated**: 2025-11-13
**Status**: Planning Phase

## Documentation Navigation

This documentation is split across multiple phase-specific files for clarity:

- **MODE2_OVERVIEW.md** (this file) - Architecture, design decisions, and natural language interface
- **[MODE2_PHASE_1A_REPOSITORY_SUPPORT.md](./MODE2_PHASE_1A_REPOSITORY_SUPPORT.md)** - Repository management infrastructure (prerequisite)
- **[MODE2_PHASE_2A_FOUNDATION.md](./MODE2_PHASE_2A_FOUNDATION.md)** - Natural language objective system and progress tracking
- **[MODE2_PHASE_2B_ORCHESTRATION.md](./MODE2_PHASE_2B_ORCHESTRATION.md)** - Multi-agent coordination and task execution
- **[MODE2_PHASE_2C_EXECUTION.md](./MODE2_PHASE_2C_EXECUTION.md)** - Autonomous execution loop and entry points
- **[MODE2_PHASE_2D_OBSERVABILITY.md](./MODE2_PHASE_2D_OBSERVABILITY.md)** - Monitoring, dashboards, and polish

**Current Implementation Status**: Mode 1 (interactive) complete, Mode 2 in planning phase

## Executive Summary

Mode 2 enables autonomous, long-running (20+ hour) development sessions where agents work toward high-level objectives without continuous human interaction. Unlike Mode 1 (interactive chat), Mode 2 is designed for:

- **Objective-Driven Work**: Agent reads YAML-defined objectives and executes autonomously
- **Multi-Agent Orchestration**: Orchestrator coordinates specialized agents (development, review, testing)
- **Progress Tracking**: Persistent phase/task state with checkpoint integration
- **Verification Loops**: Testing agent validates work before handoff
- **Fault Tolerance**: Retry logic with debugging agent assessment

**Current State**: Mode 1 (interactive) is complete and functional. Mode 2 requires additional infrastructure for objective definition, orchestration, and autonomous execution.

## Current State vs Requirements

### What Exists (Phase 1 - Mode 1)

✅ **Interactive conversation mode** (`make interactive`)
- Rich CLI with colored panels and syntax highlighting
- Real-time agent interaction with Claude Agent SDK
- Automatic checkpointing every hour (configurable)
- Metrics collection (Prometheus + Grafana)
- MCP server integration (git, docker, memory, context7, playwright, joplin)
- Session recovery from checkpoints
- Quiet mode for clean chat output

✅ **Infrastructure**
- Docker Compose orchestration with SDK runtime containers
- Three primary agent instances (main, reviewer, tester) that can load any of the 44 agent definitions
- Postgres and Redis for state management
- Prometheus metrics with 10+ interactive session metrics
- Grafana dashboards with real-time visualization
- Structured logging with correlation IDs
- Resource limits and health checks
- Checkpoint system with auto-cleanup (keeps 5 most recent)

✅ **Core SDK Integration**
- `AgentSession` wrapper with retry logic
- `ClaudeSDKClient` integration with streaming
- MCP server configuration and management
- Token usage tracking and cost calculation
- Context compaction support

### What's Missing (Mode 2 Requirements)

#### Infrastructure Prerequisites (Phase 1A)

❌ **Repository Management** (blocking Phase 2A)
- External repository cloning (git clone approach)
- Volume mounting for local repositories
- Workspace path configuration
- See [MODE2_PHASE_1A_REPOSITORY_SUPPORT.md](./MODE2_PHASE_1A_REPOSITORY_SUPPORT.md)

❌ **Objective Definition System**
- Natural language to structured format conversion
- ObjectiveBuilder for interpreting user input
- ObjectiveLoader for YAML validation (internal)
- Schema validation with Pydantic
- Natural language templates and examples

❌ **Autonomous Execution Loop**
- autonomous.py entry point for background execution
- Objective-aware execution logic
- Phase/task state management
- Graceful shutdown and recovery

❌ **Progress Tracking**
- ProgressTracker module for phase/task state
- JSON persistence with checkpoint integration
- Status reporting (completed, in_progress, failed, blocked)
- Progress visualization in Grafana

❌ **Multi-Agent Orchestration**
- Orchestrator module to coordinate agents
- Task decomposition and agent assignment
- Handoff logic with verification
- Failure detection and retry with debugging agent
- Inter-agent communication patterns

❌ **Testing & Verification Integration**
- Testing agent triggers and handoff protocols
- Test result validation before phase completion
- Automated test execution on code changes
- Test failure debugging loop

❌ **User Interface for Mode 2**
- Natural language input methods (`make objective`, `make objective-from-prd`)
- Interactive objective builder with Rich CLI
- Status monitoring commands (`make status`, `make progress`)
- Human-readable plan summaries before execution
- Session management (pause, resume, abort)

## Architecture Clarification

**Important**: Mode 2 involves three distinct layers that should not be confused:

1. **Docker Services (Infrastructure Layer)**
   - Containers that host the Claude Agent SDK runtime environment
   - Defined in `docker-compose.yml` as services (e.g., `main-agent`, `reviewer-agent`, `tester-agent`)
   - Provide the execution environment for agents

2. **Agent Instances (Execution Layer)**
   - The actual AI agents that execute tasks within the SDK
   - Referenced in objectives as "main", "reviewer", "tester"
   - Each instance can load different agent definitions based on the task

3. **Agent Definitions (Configuration Layer)**
   - 44 instruction files in `.claude/agents/` with prefix-based organization
   - Define capabilities, personality, and expertise for agents
   - Can be dynamically loaded by any agent instance

**Example**: When an objective specifies `agent: "main"`, it means the main agent instance should execute that phase. The main agent could be configured with `dev-python-expert.md` for Python tasks or `infra-docker-engineer.md` for Docker tasks.

## Natural Language Interface

**Important**: Users should express objectives naturally, not write YAML files.

### User Input Methods

Mode 2 accepts objectives in multiple natural formats:

1. **Plain Text Commands**
   ```bash
   make objective
   > "Build a user authentication system with JWT"
   ```

2. **Document References**
   ```bash
   make objective-from-prd PRD=docs/auth-feature.md
   make objective-from-issue ISSUE=#42
   ```

3. **Markdown Outlines**
   ```markdown
   # Add Rate Limiting
   - 100 requests per minute per user
   - Store counts in Redis
   - Return 429 with Retry-After header
   ```

### Translation Process

The system automatically converts natural language to structured format:

```
Natural Language → Context Analysis → Task Decomposition → YAML Generation
     (User)        (build-context)    (build-planner)      (Internal)
```

**Key Points**:
- YAML is generated internally, not written by users
- Users see human-readable summaries, not YAML
- Advanced users can access/edit YAML if needed
- All objectives saved as YAML for reproducibility

### User Experience Flow

1. **Understanding**: User describes objective, system analyzes codebase
2. **Discussion**: Interactive refinement to resolve ambiguities
3. **Execution**: User approves final plan, system runs autonomously

This mirrors the natural Claude Code workflow where understanding comes before implementation, ensuring the system fully grasps the user's intent before proceeding.

## Three-Phase Workflow

Mode 2 follows a natural conversational workflow similar to Claude Code:

### Phase 1: Understanding (Context Gathering)

**What happens**: User submits natural language objective, system analyzes codebase

```bash
make objective
> "I need to add authentication to my API"
```

System responds:
```
🔍 Analyzing your codebase...
✓ Found FastAPI application at src/api/
✓ Detected PostgreSQL database
✓ No existing auth implementation found
✓ Found user model at src/models/user.py

I understand you want to add authentication to your FastAPI application.
Let me ask a few questions to clarify the requirements...
```

### Phase 2: Discussion (Planning & Refinement)

**What happens**: Interactive discussion to resolve ambiguities and refine the plan

```
Questions about your authentication system:

1. Authentication method?
   [x] JWT tokens
   [ ] Session-based
   [ ] OAuth2
   [ ] API keys

2. User registration?
   [x] Email/password
   [ ] Social login (Google, GitHub)
   [ ] Magic links
   [ ] Phone/SMS

3. Additional features?
   [x] Password reset
   [x] Email verification
   [ ] Two-factor authentication
   [ ] Role-based permissions

Any other requirements? (or press Enter to continue)
> "Make sure to add rate limiting on login attempts"

Got it! I'll include rate limiting. Here's my plan...
```

System presents refined plan:
```
📋 Authentication Implementation Plan

Based on our discussion, I will:

Phase 1: Core Authentication (1-2 hours)
  ✓ JWT token generation and validation
  ✓ Password hashing with bcrypt
  ✓ Login endpoint with rate limiting
  ✓ Register endpoint with email validation

Phase 2: User Management (1 hour)
  ✓ Password reset flow
  ✓ Email verification system
  ✓ User profile endpoints

Phase 3: Testing & Documentation (1 hour)
  ✓ Comprehensive test suite (80%+ coverage)
  ✓ API documentation updates
  ✓ Security audit

Estimated: 3-4 hours, $4-6

Is this what you had in mind?
[Y] Yes, looks good
[e] Edit the plan
[d] Discuss more details
[n] Start over
```

### Phase 3: Execution (Build Session)

**What happens**: User approves plan and kicks off autonomous execution

```
> Y

✅ Plan approved! Starting build session...

🚀 Build Session: auth-implementation-2024-11-12-145023
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1: Core Authentication (in progress)
  ⏳ Creating JWT utilities...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Monitor: make status
Pause: make pause-session
Abort: make abort-session
```

### Key Principles

1. **No Surprises**: System always discusses the plan before execution
2. **User Control**: Multiple opportunities to refine or abort
3. **Clear Communication**: Each phase has distinct purpose and outputs
4. **Flexible Depth**: Quick approvals for simple tasks, detailed discussion for complex ones
5. **Resumable**: Each phase can be saved and resumed later

### Terminology

- **Objective**: The natural language goal provided by the user
- **Plan**: The structured breakdown created through discussion
- **Build Session**: The autonomous execution phase after approval
- **Phase**: A stage within the build session (e.g., "Backend API", "Testing")
- **Task**: Individual work items within a phase

### Workflow Variations

**Quick Fix** (minimal discussion):
```
User: "Fix the typo on line 42 of README"
System: "I'll fix the typo on line 42. Proceed? [Y/n]"
User: "Y"
[Executes immediately]
```

**Complex Feature** (extensive discussion):
```
User: "Redesign the entire API architecture"
System: [Multiple rounds of questions and refinement]
System: [Detailed multi-day plan with checkpoints]
User: [Reviews, edits, approves]
```

**PRD-Based** (skip initial understanding):
```
User: make objective-from-prd PRD=specs/feature.md
System: [Jumps to Phase 2 with extracted requirements]
System: "Based on the PRD, I have some questions..."
```

## Design Decisions

### 1. Concurrent vs Sequential Task Execution

**Decision**: Orchestration agent decides based on efficiency and operational constraints

**Rationale**:
- Extended thinking and token management should inform parallelization decisions
- Tasks should run as quickly as possible while optimizing token usage
- If there are "operational" reasons a task should be sequential for best results, respect those dependencies
- Example operational constraint: Database migrations must complete before code changes that depend on new schema

**Implementation**:
- Orchestrator uses extended thinking (if model supports it) to analyze task dependencies
- Task metadata can specify `requires: [task_id]` for explicit dependencies
- Default to parallel execution for independent tasks
- Track token usage per parallelization decision to refine heuristics

### 2. Agent Configuration & Discovery

**Decision**: Start with manual configuration, open to auto-discovery later

**Rationale**:
- Manual configuration provides control and predictability initially
- Auto-discovery can be added once patterns are established
- Existing `.claude/agents/` definitions provide a foundation (44 agents with prefix-based organization)

**Current Agent Organization**:
- **Agent Definitions**: 44 files in flat `.claude/agents/` structure with prefix naming:
  - `dev-*` (16): Development specialists (python, typescript, go, rust, etc.)
  - `db-*` (7): Database experts (postgres, mongodb, neo4j, cassandra, etc.)
  - `infra-*` (8): Infrastructure engineers (docker, k8s, terraform, aws, gcp, etc.)
  - `ml-*` (4): Machine learning specialists (pytorch, tensorflow, langchain, scikit-learn)
  - `web-*` (3): Web/frontend specialists (fastapi, frontend-designer, nextjs)
  - `data-*` (1): Data engineering specialist
  - `build-*` (3): Build/orchestration agents (context, orchestrator, project-planner)
  - `doc-*` (2): Documentation specialists (content-writer, prd-writer)
- **Skills**: 12 skills in directory format with SKILL.md files
- **Configuration**: `.mcp.json` for MCP servers, `.claude/hooks/hooks.json` for action logging

**Implementation**:
- Phase 2A: Manual agent configuration in objective YAML
- Phase 2B+: Add auto-discovery for agents based on task requirements and prefix categories
- Agent registry with capabilities metadata for matching (leverage prefix organization)

### 3. Agent Handoff Triggers

**Decision**: Agents signal completion after verification that tests pass (validated by testing agent)

**Rationale**:
- Quality gate before moving to next phase
- Reduces cascading failures from untested code
- Clear separation of concerns (dev agent writes, test agent verifies)

**Implementation**:
- Development agent signals "ready for review" after implementation
- Testing agent automatically triggered to run test suite
- If tests pass → Testing agent signals "verified" → Handoff to next phase
- If tests fail → Testing agent signals "failed" → Retry loop initiated

### 4. Failure Handling Strategy

**Decision**: 3 retries with exponential backoff, orchestration + debugging agent assess failures on each cycle

**Rationale**:
- Balances persistence with cost control (3 retries = ~4 total attempts)
- Debugging agent provides fresh perspective on failure root cause
- Orchestrator learns from failure patterns to improve future task assignment

**Implementation**:
```python
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        result = execute_task(task)
        if result.success:
            break
    except Exception as e:
        retry_count += 1

        # Log failure with context
        log_failure(task, e, retry_count)

        # Debugging agent analyzes failure
        failure_analysis = debugging_agent.analyze(task, e, logs)

        # Orchestrator adjusts context/instructions
        task = orchestrator.adjust_task(task, failure_analysis)

        # Exponential backoff
        await asyncio.sleep(2 ** retry_count)
```

**Logging**:
- Summary of each failure (task, error, logs, analysis)
- Stored in `logs/failures/{session_id}/{task_id}.log`
- Accessible via `make show-failures SESSION=<id>`

### 5. State Sharing Between Agents

**Decision**: Use Postgres, Redis, filesystem, or Memory MCP - whatever is most straightforward and robust for each type of state

**Rationale**:
- Different state types have different requirements (durability, speed, structure)
- Flexibility allows choosing best tool for each use case
- All infrastructure already exists in harness

**Implementation**:

| State Type | Storage | Rationale |
|------------|---------|-----------|
| **Objective Definition** | Filesystem (YAML) | Human-readable, version controlled |
| **Progress Tracking** | Postgres | Structured queries, ACID guarantees |
| **Task Queue** | Redis | Fast, atomic operations, pub/sub |
| **Agent Context** | Memory MCP | Knowledge graph for agent memory |
| **Checkpoints** | Filesystem (JSON) | Existing system, easy recovery |
| **Session Metadata** | Postgres | Queryable, historical analysis |
| **Real-time Events** | Redis Pub/Sub | Low latency, event streaming |

## Git Worktrees for Concurrent Development

When Mode 2 enables concurrent development on multiple objectives, git worktrees will allow parallel feature development without branch switching:

### Setup Worktrees

```bash
# From main repository
cd ~/Projects/claudeagentsdk-harness

# Create worktree for Phase 2A development
git worktree add ../harness-mode2-phase2a feature/mode2-phase2a

# Create worktree for Phase 2B development (parallel)
git worktree add ../harness-mode2-phase2b feature/mode2-phase2b

# List all worktrees
git worktree list
```

### Benefits for Mode 2

1. **Parallel Objectives**: Multiple agents can work on different features simultaneously
2. **Clean Isolation**: Each objective gets its own working directory
3. **No Context Switching**: Agents don't need to stash/switch branches
4. **Simplified Testing**: Each worktree can run its own test suite

### Worktree Management

```bash
# Remove worktree when objective complete
git worktree remove ../harness-mode2-phase2a

# Prune stale worktree references
git worktree prune
```

### Future Integration

When Mode 2 supports concurrent objectives:
- Orchestrator creates worktree per objective
- Each agent session bound to specific worktree
- Automatic cleanup on objective completion
- Merge coordination through PR workflow

**Note**: Worktrees not needed for initial sequential implementation, but architecture supports future concurrent work.

## To Be Determined

### Open Questions & Future Decisions

**1. Checkpoint Format for Objective-Aware State**
- **Question**: How should objective-specific state be serialized in checkpoints?
- **Context**: Current checkpoint system is designed for interactive sessions. Need to extend for:
  - Current phase/task in objective
  - Partial task results (e.g., half-written file)
  - Task queue state (pending, in-progress)
  - Agent handoff context
- **Options**:
  - A) Extend existing checkpoint JSON with new `objective_state` key
  - B) Create separate checkpoint file for objective state
  - C) Store objective state in Postgres, checkpoint only references it
- **Decision Factors**: Recovery speed, checkpoint size limits, ease of debugging

**2. Orchestration Agent Model Selection**
- **Question**: Should orchestrator use Opus or Sonnet for decision-making?
- **Context**: Orchestrator needs to:
  - Decompose phases into tasks
  - Decide parallel vs sequential execution
  - Analyze debugging agent feedback
  - Adjust task context on failures
- **Tradeoff**:
  - Opus: Better reasoning, extended thinking, but 5x cost ($15/$75 vs $3/$15 per MTok)
  - Sonnet: Faster, cheaper, but may miss edge cases in decomposition
- **Data Needed**: Benchmark on real objectives to measure quality difference

**3. Testing Agent Integration Patterns**
- **Question**: How should testing agent coordinate with development agent?
- **Context**: After development completes a phase, tests must run. Options:
  - A) Orchestrator explicitly calls testing agent (current plan)
  - B) Testing agent polls for "ready to test" events (event-driven)
  - C) Development agent directly invokes testing agent (agent-to-agent)
- **Considerations**: Decoupling, failure isolation, debugging complexity
- **Related**: Should testing agent have write access to fix trivial test issues?

**4. Debugging Agent Responsibilities**
- **Question**: What exactly should debugging agent do on failure?
- **Scope Options**:
  - Minimal: Analyze error logs and suggest fixes (read-only)
  - Moderate: Run diagnostic commands (bash, grep) to gather more context
  - Extensive: Attempt simple fixes and re-run tests
- **Risk**: Extensive scope could lead to infinite debugging loops
- **Proposal**: Start minimal, expand based on failure analysis data

**5. State Schema for Postgres/Redis**
- **Question**: What level of detail should be stored in database vs in-memory?
- **Context**: Need to balance:
  - Queryability (e.g., "show all failed tasks in last week")
  - Performance (minimize database writes)
  - Recovery (restore state quickly from checkpoint)
- **Specific Questions**:
  - Store full task results in Postgres JSONB, or just references?
  - Keep agent messages in Redis pub/sub, or also write to Postgres?
  - How long to retain historical state (7 days, 30 days, forever)?

**6. Memory MCP vs Filesystem Tradeoffs**
- **Question**: When to use Memory MCP knowledge graph vs plain filesystem?
- **Use Cases**:
  - Objective definition: Filesystem (YAML)
  - Progress tracking: Postgres (structured queries)
  - Agent context: Memory MCP (knowledge graph) OR Filesystem (JSON)?
- **Memory MCP Advantages**:
  - Semantic search ("find all failed authentication tasks")
  - Relationship queries ("what depends on this module?")
  - Cross-session learning
- **Filesystem Advantages**:
  - Simpler debugging (just read JSON file)
  - No dependency on MCP server availability
  - Easier to version control
- **Decision Needed**: Define clear heuristic for when to use each

**7. Progress Visualization in Grafana**
- **Question**: What visualizations are most useful for monitoring autonomous sessions?
- **Current Plan**: 10 panels (see MODE2_PHASE_2D_OBSERVABILITY.md)
- **Open Questions**:
  - Should there be a "live view" of agent thinking/tool calls?
  - How to visualize objective as a graph (nodes = tasks, edges = dependencies)?
  - Real-time vs historical view (separate dashboards or unified)?
  - User wants to see "what is the agent doing right now" - best panel type?

**8. Cost Budget Enforcement**
- **Question**: How strictly should cost limits be enforced?
- **Scenarios**:
  - Soft limit: Log warning, allow completion of current phase
  - Hard limit: Immediately abort session, save checkpoint
  - Configurable: Per-objective setting (`hard_cost_limit` vs `soft_cost_limit`)
- **Related**: Should there be per-phase cost budgets to catch expensive phases early?

**9. Objective Versioning & Migration**
- **Question**: How to handle changes to objective schema over time?
- **Context**: As features are added, objective YAML format may evolve
- **Options**:
  - A) Version field in YAML (current: `version: "1.0"`), with migration scripts
  - B) Maintain backwards compatibility indefinitely
  - C) Fail fast on old versions, require user to update manually
- **Decision Factors**: User experience, maintenance burden, breaking changes

**10. Agent Auto-Discovery Implementation**
- **Question**: How should auto-discovery match agents to tasks?
- **Context**: User approved manual config initially, but open to auto-discovery later
- **Design Considerations**:
  - Agent capabilities metadata leveraging prefix organization:
    - `dev-*` agents for development tasks (python, typescript, go, etc.)
    - `db-*` agents for database operations
    - `infra-*` agents for infrastructure/DevOps tasks
    - `ml-*` agents for machine learning tasks
  - Example: `dev-python-expert` can handle `python`, `fastapi`, `pytest`
  - Task requirements metadata (e.g., task needs `python` and `api-design`)
  - Matching algorithm: Start with prefix-based matching, then capabilities
  - Fallback if no exact match (use general "main" agent, or fail?)
- **Related**: Should there be a "suggest agents" command to preview auto-assignment?

**11. Parallel Task Execution Engine**
- **Question**: What library/pattern should be used for parallel task execution?
- **Options**:
  - A) asyncio.gather() for concurrent tasks
  - B) asyncio.TaskGroup() (Python 3.11+) for structured concurrency
  - C) Celery for distributed task queue
  - D) Redis pub/sub with multiple consumer workers
- **Considerations**: Simplicity (asyncio) vs scalability (Celery), error handling, resource limits
- **Decision Needed**: Start with asyncio, evaluate if Celery needed for >5 concurrent agents

**12. Graceful Degradation on MCP Server Failure**
- **Question**: What happens if an MCP server crashes mid-session?
- **Scenarios**:
  - Memory MCP fails: Fall back to filesystem for context?
  - Git MCP fails: Use bash git commands directly?
  - Context7 fails: Use web search instead?
- **Policy Needed**: Fail fast vs degrade gracefully
- **Current Behavior**: Undefined - need explicit error handling

**13. Session Resume After Long Pause**
- **Question**: Can you resume a session days/weeks later?
- **Challenges**:
  - Code may have changed since checkpoint (merge conflicts)
  - Dependencies may have updated
  - Objective may be obsolete
- **Options**:
  - A) Allow resume, but warn user about staleness
  - B) Validate workspace state before resume (git status, dependency check)
  - C) Offer "resume with rebase" to sync with current main branch
- **Decision Needed**: Define staleness threshold (24 hours, 7 days?)

**14. Multi-Objective Sessions**
- **Question**: Can multiple objectives run in the same session?
- **Use Case**: "Implement feature A, then fix bug B"
- **Complexity**:
  - How to sequence objectives (serial, parallel, conditional?)
  - Shared vs isolated workspace
  - Checkpoint per objective or shared?
- **Proposal**: Start with single objective, add multi-objective in Phase 3

**15. Objective Templates & Library**
- **Question**: Should there be a library of reusable objective templates?
- **Examples**:
  - `templates/feature-implementation.yaml`
  - `templates/bug-fix.yaml`
  - `templates/refactoring.yaml`
  - `templates/documentation.yaml`
- **Features**:
  - Variable substitution (e.g., `${feature_name}`)
  - Inheritance (extend base template)
  - Make target: `make new-objective TEMPLATE=feature-implementation NAME=auth-api`
- **Decision Needed**: Template format, variable syntax, validation

**16. User Notification on Completion/Failure**
- **Question**: How should user be notified when autonomous session completes?
- **Options**:
  - A) Log message only (user must check logs)
  - B) Sound notification (afplay on macOS, as in hooks)
  - C) Email/Slack notification (requires integration)
  - D) Desktop notification (via notify-send or osascript)
- **Preference**: Start with sound + log, add integrations later

**17. Objective Dry-Run Mode**
- **Question**: Should there be a mode to preview what would happen without executing?
- **Use Case**: User wants to see:
  - Which agents would be assigned
  - Task execution order
  - Estimated cost and duration
- **Implementation**: `make dry-run OBJ=objectives/feature.yaml`
- **Decision Needed**: How detailed should preview be? (Just phase list, or full task tree?)

**18. Agent Warm-up / Cold Start Optimization**
- **Question**: Should agents be pre-loaded to reduce latency?
- **Context**: First request to agent can take 5-10 seconds (SDK startup, MCP server init)
- **Options**:
  - A) Lazy initialization (current) - start agents only when needed
  - B) Eager initialization - start all agents at session start
  - C) Warm pool - keep 1-2 agents running in background
- **Tradeoff**: Memory usage vs latency
- **Decision Needed**: Benchmark to quantify impact

**19. Tool Permission Management**
- **Question**: How to enforce tool restrictions per agent in autonomous mode?
- **Context**: Objective YAML specifies allowed tools per task, but:
  - How to prevent agent from using disallowed tools?
  - Should orchestrator filter tool list, or rely on SDK?
  - What happens if agent requests disallowed tool?
- **Security Consideration**: Reviewer agent should be read-only (no Write, Edit, Bash)
- **Implementation**: May require SDK wrapper to filter tool calls

**20. Objective Cancellation & Rollback**
- **Question**: Should there be a way to undo changes from failed objective?
- **Use Case**: Objective failed in phase 3, user wants to revert changes from phases 1-2
- **Options**:
  - A) Git integration: Create feature branch, rollback = `git reset --hard`
  - B) Checkpoint restore: Restore workspace to state before objective started
  - C) Manual cleanup: User responsible for undoing changes
- **Decision Needed**: Feasibility of automated rollback, edge cases

---

**Next Steps**: Review these questions, prioritize which to resolve in Phase 2A-2D, and defer others to Phase 3 or future iterations. Some questions may be answered through experimentation and real-world usage data.