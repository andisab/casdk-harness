# Container Architecture

> **Created**: December 2025
> **Status**: Decided
> **Related**: [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md), [ORCHESTRATION_PATTERNS.md](../ORCHESTRATION_PATTERNS.md)

---

## Summary

**Decision**: Subagent-first architecture with pre-started generic worker pool as escape hatch.

| Component | Configuration |
|-----------|---------------|
| Primary execution | Subagents via `direct_agent.py` |
| Container model | Generic workers (not role-specific) |
| Pool size | 1 main-agent + 2 worker-agents |
| Container spawn | Pre-started pool (dynamic spawn documented for future) |
| Workspace | Shared `/workspace` volume (all RW) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SIMPLIFIED HYBRID                              │
│                                                                      │
│  PRIMARY (99% of cases): Subagents via direct_agent.py              │
│  ──────────────────────────────────────────────────────             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Main Agent Container                       │   │
│  │                                                               │   │
│  │  AgentSession.execute()                                       │   │
│  │  └─> direct_agent.call_agent()                               │   │
│  │      ├─> python-expert (same process)                        │   │
│  │      ├─> security-expert (same process)                      │   │
│  │      └─> orchestration-architect (same process)              │   │
│  │                                                               │   │
│  │  /workspace (shared volume, RW)                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  OPTIONAL (when needed): Generic Worker Containers                   │
│  ─────────────────────────────────────────────────                  │
│  Triggered by orchestration_spec.infrastructure.use_containers      │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │  worker-1       │  │  worker-2       │  (generic, not role-    │
│  │  (loads config  │  │  (loads config  │   specific; scale 0-N   │
│  │   from Redis)   │  │   from Redis)   │   based on workload)    │
│  └─────────────────┘  └─────────────────┘                          │
│                                                                      │
│  All share /workspace volume                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Rationale

### Why Subagent-First?

1. **Scale**: 1-3 concurrent tasks don't require container parallelization
2. **Speed**: Same-process execution (no IPC overhead)
3. **Simplicity**: Already working via `direct_agent.py`
4. **Cost**: No idle container resources

### Why Generic Workers?

1. **Flexibility**: Any agent type can run in container without docker-compose changes
2. **Simplicity**: One container image, one configuration
3. **Maintainability**: No role-specific container definitions to maintain

### Why Pre-Started Pool?

1. **Latency**: No cold start when tasks arrive
2. **Simplicity**: Standard docker-compose, no Docker API calls
3. **Predictability**: Known resource allocation

---

## Current vs Proposed

| Current | Proposed |
|---------|----------|
| main-agent (port 8080) | main-agent (unchanged) |
| reviewer-agent (port 8081, RO workspace) | worker-agent-1 (generic, RW) |
| tester-agent (port 8082, RW workspace) | worker-agent-2 (generic, RW) |

---

## Pattern-Container Mapping

How orchestration patterns map to container strategies. See [ORCHESTRATION_PATTERNS.md](../ORCHESTRATION_PATTERNS.md) for pattern details.

> **Note**: This mapping is preliminary and needs refinement during implementation.

| Pattern | Container Strategy | Notes |
|---------|-------------------|-------|
| Sequential Pipeline | Single container (subagent) | Stages execute sequentially, no parallelism needed |
| Hierarchical Coordinator | Main + workers | Coordinator in main, specialists in worker pool |
| Broadcast Multi-Perspective | Parallel workers | Same task to multiple workers for consensus |
| Blackboard Architecture | Main + shared state | Workers contribute to Redis-based blackboard |
| Mediator Pattern | Main container | Mediator routes between subagents, no extra containers |
| Peer-to-Peer | Worker pool | All peers equal, coordinate via Redis |
| Hybrid Pipeline | Main + workers | Depends on sub-pattern composition |
| Event-Driven Async | Worker pool + Redis | Workers consume from Redis streams |

**Decision criteria for container use**:
- Use subagents (in-process) for sequential or coordinator-only patterns
- Use worker containers when true parallelism is needed
- All container communication goes through Redis streams

---

## Implementation Details

### Docker Compose Configuration

**Before (role-specific)**:
```yaml
reviewer-agent:
  image: casdk-agent:latest
  environment:
    - AGENT_NAME=reviewer
    - AGENT_PROMPT_FILE=reviewer-agent.md
    - CLAUDE_PERMISSION_MODE=default
  volumes:
    - ./workspace:/workspace:ro  # Read-only
  ports:
    - "8081:8080"

tester-agent:
  image: casdk-agent:latest
  environment:
    - AGENT_NAME=tester
    - AGENT_PROMPT_FILE=tester-agent.md
    - CLAUDE_PERMISSION_MODE=bypassPermissions
  volumes:
    - ./workspace:/workspace
  ports:
    - "8082:8080"
```

**After (generic workers)**:
```yaml
worker-agent:
  image: casdk-agent:latest
  environment:
    - AGENT_MODE=worker
    - REDIS_URL=redis://redis:6379
    # Prompt/tools/model loaded from Redis task message
  volumes:
    - ./workspace:/workspace
  depends_on:
    redis:
      condition: service_healthy
  deploy:
    replicas: 2
```

### Worker Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WORKER LIFECYCLE                              │
│                                                                      │
│  1. STARTUP                                                          │
│     └─> Connect to Redis                                            │
│         └─> Register in consumer group: "workers"                   │
│                                                                      │
│  2. IDLE (blocking read on agent:tasks stream)                      │
│     └─> XREADGROUP GROUP workers worker-{id} BLOCK 0 STREAMS ...   │
│                                                                      │
│  3. TASK RECEIVED                                                    │
│     ├─> Parse task message: { agent_name, prompt, tools, model }    │
│     ├─> Load agent definition (from harness or task message)        │
│     ├─> Configure AgentSession with task parameters                 │
│     └─> Execute via call_agent()                                    │
│                                                                      │
│  4. TASK COMPLETE                                                    │
│     ├─> Publish result to agent:results stream                      │
│     ├─> Acknowledge message (XACK)                                  │
│     └─> Return to step 2 (IDLE)                                     │
│                                                                      │
│  5. SHUTDOWN (graceful)                                              │
│     └─> Complete current task, then exit                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Task Message Schema

```json
{
  "id": "task-uuid-here",
  "agent_name": "python-expert",
  "prompt": "Analyze this code for performance issues...",
  "tools": ["Read", "Write", "Bash", "Grep"],
  "model": "sonnet",
  "timeout_seconds": 300,
  "context": {
    "workspace_path": "/workspace/project",
    "files": ["src/main.py", "src/utils.py"]
  },
  "metadata": {
    "submitted_by": "main-agent",
    "submitted_at": "2025-12-19T12:00:00Z",
    "priority": "normal"
  }
}
```

### Result Message Schema

```json
{
  "task_id": "task-uuid-here",
  "status": "completed",
  "agent_name": "python-expert",
  "result": {
    "content": "Analysis complete. Found 3 performance issues...",
    "files_modified": [],
    "tokens_used": 1500
  },
  "error": null,
  "completed_at": "2025-12-19T12:05:00Z",
  "duration_seconds": 45.2
}
```

### Main Agent Dispatch

```python
# src/harness/orchestration/dispatcher.py

from harness.messaging import RedisMessageBroker
from uuid import uuid4
import asyncio

class WorkerDispatcher:
    """Dispatch tasks to worker containers via Redis."""

    def __init__(self, broker: RedisMessageBroker):
        self.broker = broker
        self.pending_tasks: dict[str, asyncio.Future] = {}

    async def dispatch(self, task: AgentTask) -> AgentResult:
        """Send task to worker pool and await result."""
        task_id = str(uuid4())

        # Create future for result
        future = asyncio.get_event_loop().create_future()
        self.pending_tasks[task_id] = future

        # Publish task
        await self.broker.publish_task(
            stream="agent:tasks",
            task={
                "id": task_id,
                "agent_name": task.agent_name,
                "prompt": task.prompt,
                "tools": task.tools,
                "model": task.model,
                "timeout_seconds": task.timeout,
            }
        )

        # Wait for result with timeout
        try:
            result = await asyncio.wait_for(
                future,
                timeout=task.timeout + 30  # Buffer for overhead
            )
            return result
        except asyncio.TimeoutError:
            raise TaskTimeoutError(f"Task {task_id} timed out")
        finally:
            self.pending_tasks.pop(task_id, None)

    async def handle_results(self):
        """Background task to process results from workers."""
        async for message in self.broker.consume_results("agent:results"):
            task_id = message["task_id"]
            if task_id in self.pending_tasks:
                self.pending_tasks[task_id].set_result(message)
```

---

## When to Use Containers

The `orchestration_spec.json` can specify when to use container execution:

```json
{
  "infrastructure": {
    "use_containers": true,
    "reason": "long_running"
  }
}
```

### Decision Matrix

| Scenario | Use Subagent | Use Container |
|----------|--------------|---------------|
| Fast, interactive feedback | Yes | No |
| Long-running background task | No | Yes |
| Fault isolation required | No | Yes |
| CPU-intensive parallel work | No | Yes |
| Simple single-step task | Yes | No |
| Resource-limited environment | Yes | No |

### Automatic Routing (Future)

```python
def should_use_container(task: AgentTask, spec: OrchestrationSpec) -> bool:
    """Determine if task should run in container."""
    # Explicit spec override
    if spec.infrastructure.use_containers is not None:
        return spec.infrastructure.use_containers

    # Heuristics
    if task.timeout_seconds > 600:  # >10 min
        return True
    if task.requires_isolation:
        return True
    if spec.pattern == "broadcast" and len(spec.perspectives) > 2:
        return True  # Parallel execution benefits

    return False  # Default to subagent
```

---

## Future: Dynamic Spawn Transition

When scale exceeds pre-started pool, transition to dynamic spawning.

### Phase 1: Pre-Started Pool (Current)

- Workers always running, waiting for tasks
- Scale manually: `docker-compose up -d --scale worker-agent=N`
- Predictable resource usage

### Phase 2: Hybrid Pool + Dynamic

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HYBRID SCALING                                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Warm Pool (always running)                                 │    │
│  │  ┌─────────┐  ┌─────────┐                                  │    │
│  │  │worker-1 │  │worker-2 │   Low latency for burst traffic │    │
│  │  └─────────┘  └─────────┘                                  │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼ (pool exhausted)                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Dynamic Spawn (on-demand)                                  │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                    │    │
│  │  │worker-3 │  │worker-4 │  │worker-N │   5-10s cold start │    │
│  │  │(spawned)│  │(spawned)│  │(spawned)│                    │    │
│  │  └─────────┘  └─────────┘  └─────────┘                    │    │
│  │                                                             │    │
│  │  Auto-terminate after idle timeout (5 min)                 │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Full Dynamic (Kubernetes)

```python
# src/harness/orchestration/container_manager.py (future)

class ContainerManager:
    """Manage dynamic container lifecycle."""

    async def spawn_worker(self, task: AgentTask) -> str:
        """Spawn container on-demand, return container_id."""
        container = await self.docker.containers.run(
            image="casdk-agent:latest",
            environment={
                "AGENT_MODE": "worker",
                "TASK_ID": task.id,
                "REDIS_URL": self.redis_url,
            },
            detach=True,
            remove=True,  # Auto-remove on exit
        )
        return container.id

    async def terminate_worker(self, container_id: str):
        """Terminate container after completion or timeout."""
        container = await self.docker.containers.get(container_id)
        await container.stop(timeout=30)

    async def scale_pool(self, target_size: int):
        """Adjust pre-started pool size."""
        current = await self.get_pool_size()
        if target_size > current:
            await self.spawn_workers(target_size - current)
        elif target_size < current:
            await self.terminate_idle_workers(current - target_size)
```

---

## Files to Create/Modify

### Immediate (Documentation)

| File | Action | Description |
|------|--------|-------------|
| `docs/features/CONTAINERIZATION.md` | CREATE | This document (consolidated from Amendment 8) |

### Future (Implementation)

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | MODIFY | Replace reviewer/tester with generic worker |
| `docker-compose.multi.yml` | MODIFY | Update multi-agent profile |
| `src/harness/agent.py` | MODIFY | Add AGENT_MODE=worker handling |
| `src/harness/messaging.py` | MODIFY | Add task dispatch/receive methods |
| `src/harness/orchestration/dispatcher.py` | CREATE | Worker dispatch logic |
| `src/harness/prompts/worker-agent.md` | CREATE | Generic worker prompt |
| `Makefile` | MODIFY | Update build-multi target descriptions |

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_dispatcher.py

async def test_dispatch_to_worker():
    """Task is correctly published to Redis."""

async def test_result_handling():
    """Results are correctly matched to pending tasks."""

async def test_timeout_handling():
    """Timeout raises appropriate exception."""
```

### Integration Tests

```python
# tests/integration/test_worker_container.py

async def test_worker_lifecycle():
    """Worker starts, processes task, returns result."""

async def test_multiple_workers():
    """Tasks are distributed across worker pool."""

async def test_worker_failure():
    """Failed task is retried or reported correctly."""
```

---

## Rollback Plan

If generic workers cause issues, rollback to role-specific containers:

1. Revert docker-compose.yml changes
2. Re-enable reviewer-agent and tester-agent
3. Keep `AGENT_MODE=worker` code but don't use it

The subagent path (`direct_agent.py`) remains unchanged and is always available.

---

## Related Documents

- [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md) - Implementation roadmap with unified timeline
- [ORCHESTRATION_PATTERNS.md](../ORCHESTRATION_PATTERNS.md) - Pattern documentation (8 patterns)
