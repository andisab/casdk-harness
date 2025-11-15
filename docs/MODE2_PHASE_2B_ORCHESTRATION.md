# MODE2 Phase 2B: Orchestration & Coordination

**Phase**: 2B - Orchestration
**Duration**: 2 weeks
**Dependencies**: Phase 2A (Foundation) complete

## Goals

Build multi-agent coordination and task execution capabilities:
1. Implement Orchestrator for coordinating multiple agents
2. Add Redis-based task queue management
3. Implement retry logic with exponential backoff
4. Add debugging agent integration for failures
5. Implement testing verification between phases

## Deliverables

- [ ] `src/harness/orchestrator.py` - Multi-agent orchestration
- [ ] `src/harness/task_queue.py` - Redis task queue management
- [ ] `src/harness/retry_logic.py` - Retry with exponential backoff
- [ ] `src/harness/debugging.py` - Debugging agent integration
- [ ] `tests/unit/test_orchestrator.py` - Unit tests
- [ ] `tests/integration/test_orchestration.py` - Integration tests

## Component Specifications

### Component 4: Orchestrator

**Purpose:** Coordinate multiple agents to execute objective

**Location:** `src/harness/orchestrator.py` (new file)

**Key Responsibilities:**
- Decompose phases into tasks
- Assign tasks to appropriate agents
- Manage task queue (Redis)
- Handle agent handoffs
- Coordinate testing verification
- Trigger debugging agent on failures
- Make concurrency decisions (parallel vs sequential)

**Interface:**
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

**Implementation Estimate:** ~400 lines

### Component 5: Task Queue Manager

**Purpose:** Manage task queue with Redis for parallel execution

**Location:** `src/harness/task_queue.py` (new file)

**Key Responsibilities:**
- Enqueue tasks for execution
- Track task state (pending, in_progress, completed, failed)
- Support parallel task execution
- Handle task timeouts
- Provide queue status and metrics

**Interface:**
```python
class TaskQueueManager:
    """Manages task queue using Redis."""

    def __init__(self, redis_client):
        """Initialize with Redis client."""

    async def enqueue_task(self, task: Task, priority: int = 0) -> str:
        """Add task to queue and return task ID."""

    async def dequeue_task(self, agent_id: str) -> Optional[Task]:
        """Get next task for agent to execute."""

    async def mark_in_progress(self, task_id: str, agent_id: str) -> None:
        """Mark task as being executed by agent."""

    async def mark_completed(self, task_id: str, result: Dict) -> None:
        """Mark task as completed with result."""

    async def mark_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed with error."""

    async def get_task_status(self, task_id: str) -> Dict:
        """Get current status of task."""

    async def get_queue_metrics(self) -> Dict:
        """Get queue statistics (pending, in_progress, etc.)."""
```

**Redis Schema:**
```
task_queue:pending     - LIST of task IDs
task_queue:in_progress - HASH {task_id: agent_id}
task_queue:completed   - SET of task IDs
task_queue:failed      - SET of task IDs
task:{id}:data        - JSON task definition
task:{id}:status      - Task status
task:{id}:result      - Task result/error
```

### Component 6: Retry Logic

**Purpose:** Intelligent retry logic with exponential backoff

**Location:** `src/harness/retry_logic.py` (new file)

**Key Features:**
- Exponential backoff with jitter
- Different strategies for different error types
- Integration with debugging agent for analysis
- Cost-aware retry decisions

**Interface:**
```python
class RetryStrategy:
    """Manages retry logic for failed tasks."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """Initialize retry strategy."""

    def should_retry(self, error: Exception, retry_count: int) -> bool:
        """Determine if task should be retried."""

    def get_retry_delay(self, retry_count: int) -> float:
        """Calculate delay before retry (exponential backoff)."""

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error type for retry decision."""

    async def analyze_failure(self, task: Task, error: Exception) -> Dict:
        """Use debugging agent to analyze failure."""
```

**Error Categories:**
- **Transient:** Network errors, rate limits → Retry immediately
- **Logic:** Code errors, missing dependencies → Debug first, then retry
- **Fatal:** Permission denied, invalid credentials → Don't retry
- **Resource:** Out of memory, disk full → Wait longer before retry

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

## Testing Strategy for Phase 2B

### Unit Tests
```python
# tests/unit/test_orchestrator.py
- test_phase_execution_sequential()
- test_phase_execution_parallel()
- test_task_assignment_logic()
- test_agent_handoff()
- test_failure_handling()
- test_retry_logic()
- test_debugging_agent_trigger()

# tests/unit/test_task_queue.py
- test_enqueue_dequeue()
- test_task_state_transitions()
- test_parallel_task_handling()
- test_queue_metrics()

# tests/unit/test_retry_logic.py
- test_exponential_backoff()
- test_error_categorization()
- test_retry_decision_logic()
- test_max_retry_limit()
```

### Integration Tests
```python
# tests/integration/test_orchestration.py
- test_simple_objective_execution()
- test_multi_phase_objective()
- test_parallel_task_execution()
- test_failure_and_retry()
- test_debugging_agent_integration()
- test_testing_agent_verification()
```

## Implementation Order

1. **Task Queue Manager** (task_queue.py)
   - Set up Redis schema
   - Implement basic queue operations
   - Add metrics collection

2. **Retry Logic** (retry_logic.py)
   - Implement exponential backoff
   - Add error categorization
   - Create retry strategies

3. **Orchestrator** (orchestrator.py)
   - Implement phase execution
   - Add task assignment
   - Integrate retry logic
   - Add testing verification

4. **Debugging Integration**
   - Connect debugging agent
   - Implement failure analysis
   - Add context adjustment

## Success Criteria

- [ ] Orchestrator executes multi-phase objectives
- [ ] Task queue handles parallel execution correctly
- [ ] Retry logic recovers from transient failures
- [ ] Debugging agent provides useful failure analysis
- [ ] Testing agent validates work between phases
- [ ] Integration tests pass with multiple agents
- [ ] Unit test coverage > 85% for orchestration components

## Example Scenarios

### Scenario 1: Simple Sequential Execution
```yaml
phases:
  - name: "Implementation"
    agent: "main"
    tasks:
      - name: "Create model"
      - name: "Add endpoints"
    parallel: false  # Sequential
```

**Execution:**
1. Task 1 assigned to main agent
2. Wait for completion
3. Task 2 assigned to main agent
4. Wait for completion
5. Phase complete

### Scenario 2: Parallel Task Execution
```yaml
phases:
  - name: "Testing"
    agent: "tester"
    tasks:
      - name: "Unit tests"
      - name: "Integration tests"
      - name: "E2E tests"
    parallel: true  # Parallel
```

**Execution:**
1. All 3 tasks enqueued simultaneously
2. Multiple tester instances pick up tasks
3. Wait for all to complete
4. Phase complete when all finish

### Scenario 3: Failure and Recovery
```yaml
phases:
  - name: "Deployment"
    agent: "main"
    tasks:
      - name: "Build container"
      - name: "Push to registry"
```

**Execution:**
1. Task 1 completes successfully
2. Task 2 fails (network error)
3. Debugging agent analyzes failure
4. Retry with exponential backoff
5. Task 2 succeeds on retry
6. Phase complete

## Monitoring and Metrics

### Prometheus Metrics (Phase 2B)
```python
orchestrator_phases_total{status}     # Phase executions
orchestrator_tasks_total{status}      # Task executions
orchestrator_retries_total{reason}    # Retry attempts
task_queue_size{state}                # Queue depths
task_execution_duration_seconds       # Task duration
agent_handoffs_total                  # Agent transitions
debugging_triggers_total{error_type}  # Debug activations
```

### Grafana Dashboard Panels
- Task queue depth over time
- Phase execution timeline
- Retry rate by error type
- Agent utilization heatmap
- Failure analysis summary

## Next Phase Preview

Phase 2C (Autonomous Execution) will build on orchestration:
- Implement autonomous.py entry point
- Add CLI commands for autonomous mode
- Implement graceful shutdown and recovery
- Add progress monitoring via Grafana
- Create end-to-end workflow tests