# Agentic Orchestration Implementation Plans

> **Created**: December 2025
> **Status**: Planning complete, ready for implementation

---

## Overview

Two compatible plans for building orchestration capabilities:

- **Plan A (Infrastructure)**: Wire Redis/messaging into working orchestration layer
- **Plan B (Tooling)**: Extend context-engineering plugin with orchestration resources

**Recommended sequence**: Plan B Phase 1-2 → Plan A Phase 1-2 → Plan B Phase 3-4 → Plan A Phase 3-4

---

## Plan A: Infrastructure

### Objective
Wire existing infrastructure (Redis, messaging, AgentSession IPC) into a working orchestration layer.

### Current State

| Built (Ready) | Designed (Not Implemented) |
|---------------|---------------------------|
| RedisMessageBroker (messaging.py) | Orchestrator class |
| CircuitBreaker (messaging.py) | TaskQueueManager class |
| AgentSession.publish_task_result() | RetryStrategy class |
| AgentSession.wait_for_dependency() | Sequential Pipeline pattern |
| direct_agent.py (call_agent) | Hierarchical Coordinator pattern |
| Docker multi-agent profile | Broadcast/Consensus pattern |
| Redis streams consumer groups | Event-driven async pattern |

### Phase 1: Foundation Wiring

**New module structure:**
```
src/harness/orchestration/
├── __init__.py
├── base.py                 # Abstract base classes
├── task_queue.py           # TaskQueueManager
├── retry.py                # RetryStrategy
└── patterns/
    ├── __init__.py
    ├── sequential.py
    ├── hierarchical.py
    ├── broadcast.py
    └── event_driven.py
```

**Deliverables:**
1. TaskQueueManager - Redis-based task queue with state tracking
2. RetryStrategy - Exponential backoff with error categorization
3. OrchestrationPattern abstract base
4. 4 pattern implementations

### Phase 2: Pattern Integration

Integrate patterns with AgentSession and direct_agent.

```python
from harness.orchestration import SequentialPipeline, HierarchicalCoordinator

pipeline = SequentialPipeline([
    ("security-scan", "dev-code-review-expert"),
    ("performance-check", "dev-python-expert"),
])
result = await pipeline.execute(code, context)
```

**Deliverables:**
1. Pattern-AgentSession integration
2. Pattern-direct_agent integration
3. Unit tests for each pattern

### Phase 3: Container Coordination

Enable peer-to-peer coordination between Docker containers.

**Deliverables:**
1. coordination-protocol.md - Shared protocol for container agents
2. Agent.py modification to append protocol in multi-agent mode
3. Role-specific coordination sections in prompts

### Phase 4: Production Hardening

**Deliverables:**
1. Prometheus metrics for orchestration
2. Grafana dashboard for task queue
3. Circuit breaker integration
4. Checkpoint integration for long-running orchestrations

---

## Plan B: Tooling (Context-Engineering Plugin)

### Objective
Extend context-engineering plugin with orchestration resources.

### Target Plugin Structure

```
context-engineering/
├── agents/
│   ├── context-engineer.md              # Existing
│   └── orchestration-architect.md       # NEW
├── skills/
│   ├── ... (5 existing)
│   ├── workflow-creation/               # NEW
│   └── orchestration-patterns/          # NEW
├── commands/
│   ├── create-agent.md                  # Existing
│   └── create-workflow.md               # NEW
├── specs/                               # NEW DIRECTORY
│   ├── orchestration-patterns/
│   │   ├── hierarchical-coordination.md
│   │   ├── peer-to-peer-coordination.md
│   │   ├── blackboard-architecture.md
│   │   ├── mediator-pattern.md
│   │   └── hybrid-pipeline.md
│   ├── infrastructure/
│   │   ├── redis-communication-protocol.md
│   │   ├── inter-agent-messaging.md
│   │   └── state-management-patterns.md
│   └── implementation/
│       └── orchestrator-class-spec.md
├── workflows/                           # NEW DIRECTORY
│   ├── code-review-pipeline.md
│   ├── research-synthesis-workflow.md
│   └── feature-development-workflow.md
├── patterns/
│   ├── progressive-disclosure.md        # Existing
│   ├── multi-agent-orchestration.md     # Existing
│   ├── tool-restriction-patterns.md     # Complete this
│   └── context-propagation.md           # NEW
├── templates/
│   ├── ... (5 existing)
│   ├── workflow-template.md             # NEW
│   └── orchestration-agent-template.md  # NEW
└── examples/                            # NEW DIRECTORY
    ├── code-review-system/
    ├── research-assistant/
    └── content-pipeline/
```

### Phase 1: Foundation (Specs & Patterns)

**Deliverables:**
1. specs/orchestration-patterns/ - Pattern specifications from main docs
2. specs/infrastructure/ - Redis protocol, messaging schemas
3. specs/implementation/ - Orchestrator class spec from RD2.md
4. Complete patterns/tool-restriction-patterns.md

### Phase 2: Skills & Commands

**Deliverables:**
1. skills/workflow-creation/SKILL.md
2. skills/orchestration-patterns/SKILL.md
3. commands/create-workflow.md

### Phase 3: Workflows & Examples

**Deliverables:**
1. workflows/ directory with reusable workflow definitions
2. examples/ directory from research.md Section 10
3. templates/workflow-template.md

### Phase 4: Agent Enhancement

**Deliverables:**
1. agents/orchestration-architect.md
2. Enhance context-engineer.md with orchestration awareness

---

## Future: DSPy/TextGrad Integration

The modular plugin structure supports future optimization:

- **specs/**: Formal specifications → training targets
- **examples/**: Known-good outputs → evaluation data
- **workflows/**: Structured pipelines → optimization graphs
- **patterns/**: Reusable templates → prompt libraries

DSPy can optimize agent prompts automatically. TextGrad can provide gradient feedback on workflow outputs.

---

## Content Consolidation Summary

| Source | Action | Destination |
|--------|--------|-------------|
| notes/*.txt (9 files) | DELETE | Content in .md files |
| ORCHESTRATION_RD.md | MERGE infrastructure section → DELETE | Architecture doc |
| ORCHESTRATION_RD2.md | MOVE | specs/implementation/orchestrator-class-spec.md |
| claude_agent_orchestration_research.md Section 10 | EXTRACT | examples/ directory |
| claude_agent_orchestration_research.md (rest) | DELETE | Duplicated in main docs |

---

## Execution Checklist

- [x] Delete notes/*.txt files
- [x] Create plugin directories: specs/, workflows/, examples/
- [x] Move RD2.md → specs/implementation/
- [x] Extract research.md examples → examples/
- [x] Delete consolidated reports
- [ ] Begin Plan B Phase 1 (specs extraction)
- [ ] Begin Plan A Phase 1 (infrastructure module)
