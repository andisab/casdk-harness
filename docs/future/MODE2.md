# Mode 2: Autonomous Long-Running Sessions

**Last Updated**: 2025-11-11
**Status**: Planning Phase

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
- Docker Compose orchestration with 3 agents (main, reviewer, tester)
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

❌ **Objective Definition System**
- YAML-based objective format with goals, phases, constraints
- ObjectiveLoader module to parse and validate objectives
- Schema validation with Pydantic
- Example objective templates

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
- Make targets for autonomous mode (`make autonomous OBJ=path/to/objective.yaml`)
- Status monitoring commands (`make status`, `make progress`)
- Objective validation (`make validate-objective`)
- Session management (pause, resume, abort)

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
- Existing `.claude/agents/` definitions from ABDotfiles provide a foundation

**Implementation**:
- Phase 2A: Manual agent configuration in objective YAML
- Phase 2B+: Add auto-discovery for agents based on task requirements
- Agent registry with capabilities metadata for matching

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

**Schema Examples**:

Postgres - Progress Tracking:
```sql
CREATE TABLE phase_progress (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    phase_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- pending, in_progress, completed, failed, blocked
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB,
    UNIQUE(session_id, phase_name)
);

CREATE TABLE task_progress (
    id SERIAL PRIMARY KEY,
    phase_id INTEGER REFERENCES phase_progress(id),
    task_name VARCHAR(255) NOT NULL,
    assigned_agent VARCHAR(100),
    status VARCHAR(50) NOT NULL,
    retry_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    UNIQUE(phase_id, task_name)
);
```

Redis - Task Queue:
```python
# Task format (JSON in Redis list)
{
    "task_id": "uuid",
    "phase_id": "phase_uuid",
    "task_name": "implement_api_endpoint",
    "agent_type": "development",
    "priority": 1,
    "dependencies": ["task_uuid_1", "task_uuid_2"],
    "context": {...}
}

# Queue operations
LPUSH task_queue:pending <task_json>
BRPOP task_queue:pending 5  # Blocking pop with 5s timeout
LPUSH task_queue:in_progress <task_json>
```

## Objective Definition Format

### YAML Structure

```yaml
# File: objectives/feature-implementation.yaml
name: "Implement User Authentication API"
description: "Add JWT-based authentication with email/password login"
version: "1.0"

# High-level goals
goals:
  - "Create FastAPI endpoints for registration, login, logout"
  - "Implement JWT token generation and validation"
  - "Add user model and database migration"
  - "Write comprehensive test suite (80%+ coverage)"
  - "Update API documentation"

# Execution phases (sequential by default)
phases:
  - name: "Planning"
    description: "Analyze requirements and design solution"
    agent: "main"
    tasks:
      - name: "Review existing auth patterns"
        tools: ["Read", "Grep", "Glob"]
      - name: "Design database schema"
        tools: ["Read", "Write"]
      - name: "Plan API endpoints"
        tools: ["Read", "Write"]
    success_criteria:
      - "Design document created"
      - "Schema diagram generated"

  - name: "Implementation"
    description: "Implement core authentication logic"
    agent: "main"
    tasks:
      - name: "Create user model"
        tools: ["Read", "Write", "Edit"]
      - name: "Implement JWT utilities"
        tools: ["Read", "Write", "Edit"]
      - name: "Build API endpoints"
        tools: ["Read", "Write", "Edit"]
      - name: "Add database migration"
        tools: ["Read", "Write", "Bash"]
    success_criteria:
      - "All endpoints respond correctly"
      - "JWT validation works"
      - "Migration runs successfully"

  - name: "Testing"
    description: "Verify implementation with tests"
    agent: "tester"
    tasks:
      - name: "Write unit tests"
        tools: ["Read", "Write", "Bash"]
      - name: "Write integration tests"
        tools: ["Read", "Write", "Bash"]
      - name: "Run full test suite"
        tools: ["Bash"]
    success_criteria:
      - "80%+ test coverage"
      - "All tests pass"

  - name: "Review"
    description: "Code review and quality check"
    agent: "reviewer"
    tasks:
      - name: "Review implementation"
        tools: ["Read", "Grep"]
      - name: "Check security best practices"
        tools: ["Read", "Grep"]
      - name: "Verify documentation"
        tools: ["Read"]
    success_criteria:
      - "No critical issues found"
      - "Documentation complete"

# Constraints and limits
constraints:
  max_duration: 14400  # 4 hours in seconds
  checkpoint_interval: 1800  # 30 minutes
  cost_limit: 5.0  # $5 USD
  permission_mode: "acceptEdits"  # manual | acceptEdits | acceptAll

# MCP tools configuration
mcp_servers:
  - git
  - memory
  - context7

# Environment configuration
environment:
  workspace_path: "/workspace"
  models:
    main: "sonnet"
    reviewer: "sonnet"
    tester: "haiku"
```

### Minimal Example

```yaml
# File: objectives/simple-fix.yaml
name: "Fix Typo in README"
description: "Correct spelling error on line 42"

goals:
  - "Fix typo in README.md"

phases:
  - name: "Fix"
    agent: "main"
    tasks:
      - name: "Correct typo"
        tools: ["Read", "Edit"]
    success_criteria:
      - "Typo corrected"

constraints:
  max_duration: 300  # 5 minutes
  permission_mode: "acceptAll"
```

### Objective Schema (Pydantic)

```python
# src/harness/objectives.py

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class Task(BaseModel):
    """Individual task within a phase."""
    name: str = Field(..., description="Task name")
    tools: List[str] = Field(default=["Read", "Write"], description="Allowed tools")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class Phase(BaseModel):
    """Execution phase with tasks."""
    name: str = Field(..., description="Phase name")
    description: str = Field(..., description="Phase description")
    agent: str = Field(..., description="Agent to execute phase")
    tasks: List[Task] = Field(..., description="Tasks in phase")
    success_criteria: List[str] = Field(..., description="Success criteria")
    parallel: bool = Field(False, description="Execute tasks in parallel")


class Constraints(BaseModel):
    """Execution constraints."""
    max_duration: int = Field(14400, description="Max duration in seconds")
    checkpoint_interval: int = Field(3600, description="Checkpoint interval")
    cost_limit: float = Field(10.0, description="Max cost in USD")
    permission_mode: str = Field("acceptEdits", description="Permission mode")

    @validator("permission_mode")
    def validate_permission_mode(cls, v):
        allowed = ["manual", "acceptEdits", "acceptAll"]
        if v not in allowed:
            raise ValueError(f"permission_mode must be one of {allowed}")
        return v


class Objective(BaseModel):
    """Complete objective definition."""
    name: str = Field(..., description="Objective name")
    description: str = Field(..., description="Objective description")
    version: str = Field("1.0", description="Objective format version")
    goals: List[str] = Field(..., description="High-level goals")
    phases: List[Phase] = Field(..., description="Execution phases")
    constraints: Constraints = Field(default_factory=Constraints)
    mcp_servers: List[str] = Field(default=["git", "memory"], description="MCP servers")
    environment: Dict[str, Any] = Field(default_factory=dict, description="Environment config")
```

## Required Components

### Component 1: ObjectiveLoader

**Purpose**: Load, parse, and validate objective YAML files

**Location**: `src/harness/objectives.py` (add to existing file)

**Key Responsibilities**:
- Load YAML from filesystem
- Validate against Pydantic schema
- Resolve relative paths (e.g., `./context_docs/design.md`)
- Provide helpful error messages for invalid objectives

**Interface**:
```python
class ObjectiveLoader:
    """Loads and validates objective definitions."""

    def load_from_file(self, path: Path) -> Objective:
        """Load objective from YAML file."""

    def load_from_string(self, yaml_str: str) -> Objective:
        """Load objective from YAML string."""

    def validate(self, objective: Objective) -> List[str]:
        """Validate objective and return any issues."""
```

**Implementation Estimate**: ~150 lines

### Component 2: ProgressTracker

**Purpose**: Track phase and task progress with persistent state

**Location**: `src/harness/progress.py` (new file)

**Key Responsibilities**:
- Initialize progress state from objective
- Update phase/task status (pending → in_progress → completed/failed)
- Persist state to Postgres
- Integrate with checkpoint system
- Provide progress queries (current phase, completed tasks, etc.)

**Interface**:
```python
class ProgressTracker:
    """Tracks progress through objective phases and tasks."""

    def __init__(self, session_id: str, objective: Objective, db_pool):
        """Initialize tracker with objective."""

    async def start_phase(self, phase_name: str) -> None:
        """Mark phase as in progress."""

    async def complete_phase(self, phase_name: str, metadata: Dict) -> None:
        """Mark phase as completed."""

    async def fail_phase(self, phase_name: str, error: str) -> None:
        """Mark phase as failed."""

    async def start_task(self, phase_name: str, task_name: str, agent: str) -> None:
        """Mark task as in progress."""

    async def complete_task(self, phase_name: str, task_name: str, result: Dict) -> None:
        """Mark task as completed."""

    async def get_current_phase(self) -> Optional[Phase]:
        """Get current phase being executed."""

    async def get_progress_summary(self) -> Dict[str, Any]:
        """Get overall progress summary."""

    async def save_checkpoint(self, checkpoint_data: Dict) -> None:
        """Save progress to checkpoint."""

    async def load_from_checkpoint(self, checkpoint_path: Path) -> None:
        """Restore progress from checkpoint."""
```

**Implementation Estimate**: ~250 lines

### Component 3: Orchestrator

**Purpose**: Coordinate multiple agents to execute objective

**Location**: `src/harness/orchestrator.py` (new file)

**Key Responsibilities**:
- Decompose phases into tasks
- Assign tasks to appropriate agents
- Manage task queue (Redis)
- Handle agent handoffs
- Coordinate testing verification
- Trigger debugging agent on failures
- Make concurrency decisions (parallel vs sequential)

**Interface**:
```python
class Orchestrator:
    """Orchestrates multi-agent execution of objectives."""

    def __init__(
        self,
        objective: Objective,
        progress_tracker: ProgressTracker,
        agents: Dict[str, AgentSession],
        redis_client,
    ):
        """Initialize orchestrator."""

    async def execute(self) -> Dict[str, Any]:
        """Execute objective and return summary."""

    async def execute_phase(self, phase: Phase) -> Dict[str, Any]:
        """Execute single phase."""

    async def execute_task(
        self,
        phase: Phase,
        task: Task,
        agent: AgentSession,
    ) -> Dict[str, Any]:
        """Execute single task with retry logic."""

    async def verify_with_tests(self, phase: Phase) -> bool:
        """Trigger testing agent to verify phase."""

    async def handle_failure(
        self,
        phase: Phase,
        task: Task,
        error: Exception,
        retry_count: int,
    ) -> Optional[Task]:
        """Handle task failure with debugging agent."""

    def should_parallelize(self, tasks: List[Task]) -> bool:
        """Decide if tasks should run in parallel."""

    async def wait_for_task_completion(self, task_ids: List[str]) -> List[Dict]:
        """Wait for parallel tasks to complete."""
```

**Implementation Estimate**: ~400 lines

### Component 4: Autonomous Execution Entry Point

**Purpose**: Main entry point for Mode 2 autonomous sessions

**Location**: `src/harness/autonomous.py` (new file)

**Key Responsibilities**:
- Load objective from YAML
- Initialize agents and orchestrator
- Start autonomous execution loop
- Handle graceful shutdown (SIGTERM, SIGINT)
- Save final checkpoint on exit
- Provide status updates via logs/metrics

**Interface**:
```python
async def run_autonomous_session(objective_path: Path) -> None:
    """Run autonomous session from objective file."""

async def main() -> None:
    """CLI entry point for autonomous mode."""
```

**Implementation Estimate**: ~200 lines

**Usage**:
```bash
# Via Make
make autonomous OBJ=objectives/feature-implementation.yaml

# Direct
python -m harness.autonomous objectives/feature-implementation.yaml
```

## Implementation Roadmap

### Phase 2A: Foundation (Week 1-2)

**Goals**: Objective definition system and basic progress tracking

**Deliverables**:
1. ✅ Pydantic schema for objectives (`objectives.py`)
2. ✅ ObjectiveLoader with YAML parsing
3. ✅ ProgressTracker with Postgres persistence
4. ✅ Example objective templates (simple, medium, complex)
5. ✅ Make target for objective validation (`make validate-objective`)

**Testing**:
- Unit tests for ObjectiveLoader
- Unit tests for ProgressTracker
- Integration test: Load objective → Initialize progress → Persist state

**Acceptance Criteria**:
- Can load and validate objective YAML
- Progress state persists to database correctly
- Recovery from checkpoint restores progress state

### Phase 2B: Orchestration (Week 3-4)

**Goals**: Multi-agent coordination and task execution

**Deliverables**:
1. ✅ Orchestrator module with task queue (Redis)
2. ✅ Task assignment and agent handoff logic
3. ✅ Testing agent integration for verification
4. ✅ Failure handling with retry logic
5. ✅ Debugging agent integration (analysis on failures)

**Testing**:
- Unit tests for Orchestrator (mocked agents)
- Integration test: Simple objective with 2 phases
- Integration test: Failure handling and retry

**Acceptance Criteria**:
- Orchestrator executes multi-phase objectives
- Testing agent validates work before handoff
- Failures trigger debugging agent and retry

### Phase 2C: Autonomous Execution (Week 5)

**Goals**: End-to-end autonomous mode

**Deliverables**:
1. ✅ `autonomous.py` entry point
2. ✅ Make targets for autonomous mode (`make autonomous`, `make status`)
3. ✅ Graceful shutdown with checkpoint save
4. ✅ Progress monitoring via Grafana dashboard
5. ✅ Documentation for Mode 2 usage in README.md

**Testing**:
- E2E test: Complete objective execution
- E2E test: Recovery from checkpoint mid-session
- E2E test: Graceful shutdown and resume

**Acceptance Criteria**:
- Can run autonomous session from start to finish
- Interruption and recovery works correctly
- Progress visible in Grafana

### Phase 2D: Polish & Observability (Week 6)

**Goals**: Enhanced monitoring and user experience

**Deliverables**:
1. ✅ Grafana dashboard for autonomous sessions (10 panels)
2. ✅ Prometheus metrics for orchestration (task queue, phase duration)
3. ✅ Action logging hooks for objective-aware logging
4. ✅ Session summary report (markdown output on completion)
5. ✅ Cost tracking and budget enforcement

**Testing**:
- Verify all metrics are collected
- Test cost limit enforcement
- Validate session report accuracy

**Acceptance Criteria**:
- Grafana shows real-time objective progress
- Session report provides useful summary
- Cost limits prevent budget overruns

## Architecture Patterns

### Message Flow: Autonomous Mode

```
User: make autonomous OBJ=objectives/feature.yaml
    ↓
autonomous.py
    ↓
ObjectiveLoader.load_from_file()
    ↓
Orchestrator.execute()
    ↓
┌─────────────────────────────────────┐
│  For each phase in objective:       │
│    1. ProgressTracker.start_phase() │
│    2. Orchestrator.execute_phase()  │
│        ↓                             │
│        For each task in phase:      │
│          a. Assign to agent         │
│          b. AgentSession.execute()  │
│          c. Record result           │
│          d. Update progress         │
│    3. Orchestrator.verify_tests()   │
│    4. ProgressTracker.complete()    │
└─────────────────────────────────────┘
    ↓
Generate session report
    ↓
Save final checkpoint
```

### Agent Handoff Pattern

```
Development Agent (Phase: Implementation)
    ↓
  "Implementation complete"
    ↓
Testing Agent (Triggered by Orchestrator)
    ↓
  Run test suite
    ↓
┌─────────────────────────┐
│  Tests Pass?            │
│    Yes → Signal success │
│    No → Signal failure  │
└─────────────────────────┘
    ↓ (Success)
Orchestrator marks phase complete
    ↓
Move to next phase (Review)
    ↓
Reviewer Agent

    ↓ (Failure)
Debugging Agent analyzes failure
    ↓
Orchestrator adjusts context
    ↓
Retry Implementation (up to 3 times)
```

### State Management Pattern

```
┌──────────────────────────────────────────┐
│             Objective YAML               │
│         (Filesystem, Immutable)          │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│          Progress State (Postgres)       │
│   - Phase status (pending/in_progress/   │
│     completed/failed)                    │
│   - Task assignments and results         │
│   - Retry counts and failure logs        │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│         Task Queue (Redis Lists)         │
│   - task_queue:pending                   │
│   - task_queue:in_progress               │
│   - task_queue:completed                 │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│       Agent Context (Memory MCP)         │
│   - Knowledge graph of project           │
│   - Learned patterns and gotchas         │
│   - Cross-session insights               │
└──────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────┐
│    Checkpoints (Filesystem, JSON)        │
│   - Full session state snapshot          │
│   - Progress tracker state               │
│   - Objective + current phase/task       │
│   - Agent context pointers               │
└──────────────────────────────────────────┘
```

## Usage Examples

### Example 1: Run Simple Objective

```bash
# 1. Create objective file
cat > objectives/fix-typo.yaml <<EOF
name: "Fix Documentation Typo"
goals:
  - "Fix typo in README.md line 42"
phases:
  - name: "Fix"
    agent: "main"
    tasks:
      - name: "Correct typo"
    success_criteria:
      - "Typo corrected"
constraints:
  max_duration: 300
  permission_mode: "acceptAll"
EOF

# 2. Validate objective
make validate-objective OBJ=objectives/fix-typo.yaml

# 3. Run autonomous session
make autonomous OBJ=objectives/fix-typo.yaml

# 4. Monitor progress (in another terminal)
make status

# Output:
# ┌─────────────────────────────────────────┐
# │  Session: main_2025-11-11T10:30:45     │
# │  Objective: Fix Documentation Typo      │
# │  Phase: Fix (1/1)                       │
# │  Status: ✅ Completed                   │
# │  Duration: 45 seconds                   │
# │  Cost: $0.02                            │
# └─────────────────────────────────────────┘
```

### Example 2: Complex Multi-Phase Objective

```bash
# 1. Use template
cp examples/objectives/feature-implementation.yaml objectives/auth-api.yaml

# 2. Customize for your project
vim objectives/auth-api.yaml

# 3. Validate
make validate-objective OBJ=objectives/auth-api.yaml

# 4. Run with monitoring
make dev  # Start all services in background
make autonomous OBJ=objectives/auth-api.yaml

# 5. View progress in Grafana
make metrics  # Opens http://localhost:3000
# Navigate to "Autonomous Sessions" dashboard

# 6. Check logs
make logs-autonomous

# 7. If interrupted, resume
make autonomous-resume SESSION=main_2025-11-11T10:30:45
```

### Example 3: Debugging a Failed Objective

```bash
# Session failed during testing phase
make show-failures SESSION=main_2025-11-11T10:30:45

# Output:
# ┌─────────────────────────────────────────────────┐
# │  Failure Report                                 │
# ├─────────────────────────────────────────────────┤
# │  Phase: Testing                                 │
# │  Task: Run integration tests                    │
# │  Retry: 2/3                                     │
# │  Error: AssertionError: test_login_endpoint     │
# │                                                 │
# │  Debugging Agent Analysis:                      │
# │  - JWT token validation missing timezone        │
# │  - Recommend: Add UTC timezone to timestamp     │
# │                                                 │
# │  Orchestrator Action:                           │
# │  - Updated task context with fix suggestion     │
# │  - Reassigned to development agent              │
# └─────────────────────────────────────────────────┘

# Review full logs
make logs-failures SESSION=main_2025-11-11T10:30:45
```

## Grafana Dashboard: Autonomous Sessions

**New Panels** (in addition to existing interactive session panels):

1. **Objective Progress** (Status Panel)
   - Shows current phase and completion percentage
   - Color-coded: Green (completed), Yellow (in progress), Red (failed)

2. **Phase Timeline** (Gantt Chart)
   - Visual timeline of phase start/end times
   - Shows which phases ran in parallel

3. **Task Queue Depth** (Graph)
   - Number of tasks in pending/in_progress/completed queues
   - Helps identify bottlenecks

4. **Agent Utilization** (Heatmap)
   - Shows which agents are active and idle
   - Helps optimize agent configuration

5. **Failure Rate by Phase** (Bar Chart)
   - Percentage of tasks that failed per phase
   - Identifies problematic phases

6. **Cost per Phase** (Stacked Area Chart)
   - API costs broken down by phase
   - Helps identify expensive operations

7. **Retry Rate** (Gauge)
   - Percentage of tasks that required retry
   - Lower is better (target: <10%)

8. **Testing Verification Time** (Graph)
   - Time taken for testing agent to verify each phase
   - Tracks test suite performance

9. **Checkpoint Frequency** (Timeline)
   - Shows when checkpoints were saved
   - Helps tune checkpoint interval

10. **Session Duration Estimate** (Stat)
    - Estimated time to completion based on current progress
    - Updates in real-time

## Make Targets for Mode 2

Add to `Makefile`:

```makefile
# ============================================================================
# Mode 2: Autonomous Sessions
# ============================================================================

.PHONY: autonomous
autonomous: ## Run autonomous session from objective YAML
autonomous:
	@echo "🤖 Starting autonomous session..."
	@docker compose exec main-agent python -m harness.autonomous $(OBJ)

.PHONY: validate-objective
validate-objective: ## Validate objective YAML file
validate-objective:
	@docker compose exec main-agent python -c \
		"from harness.objectives import ObjectiveLoader; \
		 loader = ObjectiveLoader(); \
		 obj = loader.load_from_file('$(OBJ)'); \
		 print('✅ Objective valid')"

.PHONY: status
status: ## Show current autonomous session status
status:
	@docker compose exec main-agent python -m harness.autonomous --status

.PHONY: autonomous-resume
autonomous-resume: ## Resume autonomous session from checkpoint
autonomous-resume:
	@echo "🔄 Resuming session $(SESSION)..."
	@docker compose exec main-agent python -m harness.autonomous --resume $(SESSION)

.PHONY: autonomous-pause
autonomous-pause: ## Pause running autonomous session
autonomous-pause:
	@docker compose exec main-agent python -m harness.autonomous --pause

.PHONY: autonomous-abort
autonomous-abort: ## Abort running autonomous session
autonomous-abort:
	@docker compose exec main-agent python -m harness.autonomous --abort

.PHONY: show-failures
show-failures: ## Show failure logs for session
show-failures:
	@cat logs/failures/$(SESSION)/*.log

.PHONY: logs-autonomous
logs-autonomous: ## Tail logs for autonomous session
logs-autonomous:
	@docker compose logs -f main-agent | grep autonomous

.PHONY: session-report
session-report: ## Generate session summary report
session-report:
	@docker compose exec main-agent python -m harness.autonomous --report $(SESSION)
```

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
- **Current Plan**: 10 panels (see "Grafana Dashboard" section above)
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
  - Agent capabilities metadata (e.g., `python-expert` can do `python`, `fastapi`, `pytest`)
  - Task requirements metadata (e.g., task needs `python` and `api-design`)
  - Matching algorithm (exact match, fuzzy match, LLM-based matching?)
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
