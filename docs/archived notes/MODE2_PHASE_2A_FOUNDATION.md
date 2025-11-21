# MODE2 Phase 2A: Foundation Components

**Phase**: 2A - Foundation
**Duration**: 1 week
**Dependencies**:
- Phase 0.7 (Enhanced Observability) complete ✅
- Phase 1A (Repository Support) complete - See [MODE2_PHASE_1A_REPOSITORY_SUPPORT.md](./MODE2_PHASE_1A_REPOSITORY_SUPPORT.md)

## Prerequisites

Before implementing Phase 2A, ensure:
- [ ] Phase 0.7 (Enhanced Observability) complete ✅
- [ ] Phase 1A (Repository Support) complete - Required for `workspace_path` in objective YAML

The objective YAML's `environment.workspace_path` field depends on repository management capabilities from Phase 1A.

## Goals

Build foundational components for autonomous objective execution:
1. Define objective YAML schema with Pydantic models
2. Implement ObjectiveLoader for parsing and validation
3. Implement ObjectiveBuilder for natural language conversion
4. Implement ProgressTracker for state persistence
5. Create initial test suite for foundation components

## Deliverables

- [ ] `src/harness/objectives.py` - Pydantic models and ObjectiveLoader
- [ ] `src/harness/objective_builder.py` - Natural language to objective conversion
- [ ] `src/harness/progress.py` - Progress tracking with persistence
- [ ] `tests/unit/test_objectives.py` - Unit tests for objectives
- [ ] `tests/unit/test_objective_builder.py` - Unit tests for builder
- [ ] `tests/unit/test_progress.py` - Unit tests for progress tracker

## Component Specifications

### 1. Objective Definition Format

#### YAML Structure Example
```yaml
# Example: objectives/add-auth-system-2024-11-12-143052.yaml
name: "Add JWT Authentication System"
description: "Implement JWT-based authentication with refresh tokens"
version: "1.0"

# High-level goals (what success looks like)
goals:
  - "Secure user authentication with JWT"
  - "Refresh token mechanism for extended sessions"
  - "Role-based access control"
  - "Database-backed user management"

# Context documents (PRD, design docs, etc.)
context_documents:
  - "./context_docs/auth_prd.md"
  - "./context_docs/existing_api_patterns.md"

# Execution phases (sequential by default)
phases:
  - name: "Planning"
    description: "Analyze requirements and design solution"
    agent: "main"  # Agent instance (can load any agent definition)
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
    agent: "main"  # Could use dev-python-expert.md or dev-fastapi-expert.md definition
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
    agent: "tester"  # Testing agent instance
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
    agent: "reviewer"  # Review agent instance (could use infra-security-auditor.md)
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

# MCP tools configuration (references .mcp.json)
mcp_servers:
  - git        # Version control operations
  - memory     # Knowledge graph for agent memory
  - context7   # Library documentation lookup
  - docker     # Container management (if needed)
  - joplin     # Note-taking integration (if needed)

# Environment configuration
environment:
  workspace_path: "/workspace"
  models:
    main: "sonnet"
    reviewer: "sonnet"
    tester: "haiku"
```

#### User Input vs Generated Output

**What Users Provide:**
```text
"Fix the typo in README on line 42"
```

**What System Generates:**
```yaml
# GENERATED FILE: objectives/fix-typo-2024-11-12-143052.yaml
name: "Fix Typo in README"
description: "Correct spelling error on line 42"

goals:
  - "Fix typo in README.md"

phases:
  - name: "Fix"
    agent: "main"  # Main agent instance
    tasks:
      - name: "Correct typo"
        tools: ["Read", "Edit"]
    success_criteria:
      - "Typo corrected"

constraints:
  max_duration: 300  # 5 minutes
  permission_mode: "acceptAll"
```

**What Users See:**
```
📋 Quick Fix: Typo in README

I'll fix the spelling error on line 42 of README.md

Estimated: < 1 minute, < $0.01

Proceed? [Y/n]
```

### 2. Pydantic Schema Models

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
    skills: Optional[List[str]] = Field(None, description="Skills to load from .claude/skills/")
    agent_definitions: Optional[Dict[str, str]] = Field(None, description="Agent definition overrides")
```

### 3. Integration with .claude/ Structure

**Skills Integration:**
- The 12 skills in `.claude/skills/` can be referenced in objectives
- Skills provide patterns, templates, and workflows for specific domains
- Agents can load relevant skills based on the phase requirements
- Example: "api-development" skill for API implementation phases

**Agent Definition Selection:**
- Objectives can specify which agent definition to use for each instance
- Default behavior: Auto-select based on task type and prefix matching
- Override option: Explicitly specify agent definition file
- Example: `agent_definitions: {"main": "dev-python-expert", "reviewer": "infra-security-auditor"}`

**Hooks Integration:**
- `.claude/hooks/hooks.json` action logging applies to autonomous sessions
- Hooks can track objective progress and agent decisions
- Post-tool-use hooks can validate actions against objective constraints

## Required Components

### Component 1: ObjectiveLoader

**Purpose:** Load, parse, and validate objective YAML files

**Location:** `src/harness/objectives.py` (add to existing file)

**Key Responsibilities:**
- Load YAML from filesystem
- Validate against Pydantic schema
- Resolve relative paths (e.g., `./context_docs/design.md`)
- Provide helpful error messages for invalid objectives

**Interface:**
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

**Implementation Estimate:** ~150 lines

### Component 2: ObjectiveBuilder

**Purpose:** Convert natural language input to structured objectives

**Location:** `src/harness/objective_builder.py` (new file)

**Key Responsibilities:**
- Accept natural language descriptions
- Parse PRD documents and GitHub issues
- Use build-context-agent for codebase analysis
- Use build-project-planner for task decomposition
- Generate YAML internally
- Present human-readable summaries

**Interface:**
```python
class ObjectiveBuilder:
    """Manages the three-phase workflow for objective creation."""

    def __init__(self, context_agent, planner_agent, console):
        """Initialize with required agents and Rich console."""
        self.context_agent = context_agent  # build-context-agent
        self.planner_agent = planner_agent  # build-project-planner
        self.console = console              # Rich console for UI

    async def phase1_understanding(self, description: str) -> Dict:
        """Phase 1: Analyze codebase and understand objective."""
        # 1. Use context_agent to scan codebase
        # 2. Identify relevant files and patterns
        # 3. Detect existing implementations
        # 4. Return context summary

    async def phase2_discussion(self, context: Dict) -> Objective:
        """Phase 2: Interactive discussion to refine requirements."""
        # 1. Generate clarifying questions based on context
        # 2. Present options for user selection
        # 3. Handle follow-up questions
        # 4. Build refined objective iteratively
        # 5. Return draft objective for approval

    async def phase3_approval(self, objective: Objective) -> bool:
        """Phase 3: Present final plan and get approval."""
        # 1. Generate detailed execution plan
        # 2. Show time/cost estimates
        # 3. Offer edit/discuss/approve options
        # 4. Return approval status

    async def interactive(self) -> Objective:
        """Complete three-phase interactive workflow."""
        # Phase 1: Understanding
        description = await self.get_initial_description()
        context = await self.phase1_understanding(description)

        # Phase 2: Discussion
        objective = await self.phase2_discussion(context)

        # Phase 3: Approval
        approved = await self.phase3_approval(objective)

        if approved:
            return objective
        else:
            return None  # User cancelled or wants to restart

    async def from_prd(self, prd_path: Path) -> Objective:
        """Build from PRD (skips to Phase 2 with extracted requirements)."""
        # 1. Parse PRD content
        # 2. Extract requirements as context
        # 3. Jump to phase2_discussion() with context
        # 4. Continue to phase3_approval()

    def ask_clarifying_questions(self, context: Dict) -> List[Question]:
        """Generate smart questions based on codebase context."""
        # Dynamic questions based on what was found
        # E.g., if auth exists: "Extend existing auth or replace?"
        # E.g., if no tests: "Include comprehensive test suite?"
```

**Implementation Estimate:** ~300 lines

### Component 3: ProgressTracker

**Purpose:** Track phase and task progress with persistent state

**Location:** `src/harness/progress.py` (new file)

**Key Responsibilities:**
- Initialize progress state from objective
- Update phase/task status (pending → in_progress → completed/failed)
- Persist state to Postgres
- Integrate with checkpoint system
- Provide progress queries (current phase, completed tasks, etc.)

**Interface:**
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

**Implementation Estimate:** ~250 lines

## Testing Strategy for Phase 2A

### Unit Tests
```python
# tests/unit/test_objectives.py
- test_load_valid_objective_yaml()
- test_validate_objective_schema()
- test_reject_invalid_permission_mode()
- test_default_constraints()
- test_resolve_relative_paths()

# tests/unit/test_objective_builder.py
- test_parse_natural_language()
- test_generate_phases_from_description()
- test_ask_clarifying_questions()
- test_estimate_cost_and_duration()

# tests/unit/test_progress.py
- test_initialize_from_objective()
- test_phase_state_transitions()
- test_task_state_transitions()
- test_checkpoint_save_and_load()
- test_progress_summary()
```

### Integration Tests
```python
# tests/integration/test_objective_workflow.py
- test_load_and_validate_example_objectives()
- test_builder_with_real_agents()
- test_progress_tracker_with_postgres()
```

## Implementation Order

1. **Pydantic Models** (objectives.py)
   - Define Task, Phase, Constraints, Objective models
   - Add validation rules
   - Test with example YAML files

2. **ObjectiveLoader** (objectives.py)
   - Implement YAML loading
   - Add schema validation
   - Handle path resolution

3. **ProgressTracker** (progress.py)
   - Design database schema
   - Implement state transitions
   - Add checkpoint integration

4. **ObjectiveBuilder** (objective_builder.py)
   - Implement natural language parsing
   - Add three-phase workflow
   - Integrate with agents

## Success Criteria

- [ ] All Pydantic models validate example objectives
- [ ] ObjectiveLoader successfully loads 10+ test objectives
- [ ] ObjectiveBuilder converts 5+ natural language descriptions
- [ ] ProgressTracker maintains state across restarts
- [ ] Unit test coverage > 90% for new components
- [ ] Integration tests pass with real database

## Next Phase Preview

Phase 2B (Orchestration & Coordination) will build on these foundations:
- Implement Orchestrator for multi-agent coordination
- Add task queue management with Redis
- Implement retry logic and error recovery
- Add debugging agent integration