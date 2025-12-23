# Agentic Orchestration Implementation Roadmap

> **Created**: December 2025
> **Status**: Planning complete, ready for implementation
> **Related**: [ORCHESTRATION_PATTERNS.md](./ORCHESTRATION_PATTERNS.md) | [Feature Specs](./features/)

---

## Executive Summary

This roadmap defines the implementation path for a complete agentic orchestration system that spans:

0. **CGF Infrastructure** (NEW - Foundation) - OpenTelemetry tracing, optimization store, adapters, rewards
1. **Context Engineering** - Elicit objectives, plan resources, generate agents/skills
2. **Orchestration Patterns** - 8 production-ready patterns for multi-agent coordination
3. **ContextGrad Framework (CGF)** - Automated testing and optimization of context resources
4. **Production Infrastructure** - Redis messaging, container coordination, observability

**Why CGF Infrastructure First?**
- Tracing provides execution visibility for debugging orchestration patterns
- Reward signals inform pattern selection heuristics
- Store pattern enables distributed execution from the start
- Adapter framework supports multiple resource types (agents, skills, prompts, commands)

**End-to-End Flow:**
```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                   CGF INFRASTRUCTURE (Phase 0)                   │
                    │  OpenTelemetry Tracing → Store → Adapters → Rewards             │
                    └─────────────────────────────────────────────────────────────────┘
                                                    ↓
User Objective → Context Engineering → Resource Generation → CGF Optimization → Production Deployment
                       ↓                      ↓                    ↓
                 context_spec.json    agents/skills/commands    optimized resources
```

### Phase 1: Single-Agent Optimization Validation

Before implementing multi-agent orchestration (Plans A & B), Phase 1 validates the optimization loop works end-to-end on a single agent:

| Sub-Phase | Description |
|-----------|-------------|
| 1A | Test case infrastructure - YAML-based test suites with validation |
| 1B | Agent runner - Execute agent with full tracing |
| 1C | DSPy integration - MIPROv2 prompt optimization |
| 1D | TextGrad integration - Textual gradient refinement |
| 1E | Pipeline CLI - `python -m harness.optimization.cli.optimize` |

**Target Agent**: `python-expert`
**Success Criteria**: Run optimization end-to-end with measurable improvement metric.

---

## Feature Index

Detailed specifications for each major capability:

| Feature | Specification | Status | Description |
|---------|---------------|--------|-------------|
| **CGF Infrastructure** | [CGF-INFRASTRUCTURE.md](./features/CGF-INFRASTRUCTURE.md) | **Phase 0 ✅, Phase 1 🚧** | Tracing, store, adapters, rewards (Phase 0) + Single-agent optimization (Phase 1) |
| Context Engineering Workflow | [CONTEXT_ENG_WF.md](./features/CONTEXT_ENG_WF.md) | Refined | 4-stage workflow for resource generation |
| ContextGrad Framework | [CONTEXT-GRAD-SPEC.md](./features/CONTEXT-GRAD-SPEC.md) | Design Complete | DSPy + TextGrad optimization system |
| CGF Implementation Guide | [CONTEXT-GRAD-IMP.md](./features/CONTEXT-GRAD-IMP.md) | Design Complete | Detailed implementation patterns |
| Container Architecture | [CONTAINERIZATION.md](./features/CONTAINERIZATION.md) | Decided | Subagent-first Docker model |
| Agentic Examples | [AGENTIC_EXAMPLES.md](./features/AGENTIC_EXAMPLES.md) | Extracted | 8+ working multi-agent examples |
| Observability | [OBSERVABILITY.md](./features/OBSERVABILITY.md) | Planning | Grafana dashboards, session reports |

**Pattern Reference**: See [ORCHESTRATION_PATTERNS.md](./ORCHESTRATION_PATTERNS.md) for the 8 core orchestration patterns with production implementations.

---

## Context Engineering Workflow

The Context Engineering Workflow is the entry point for creating new agentic capabilities. It produces validated resources ready for CGF optimization.

### Workflow Stages

| Stage | Output | Completion Signal |
|-------|--------|-------------------|
| 1. Objective Elicitation | `context_spec.json` (objective) | `[SPEC_APPROVED]` |
| 2. Pattern & Resource Planning | Pattern selection + resource inventory | `[RESOURCES_PLANNED]` |
| 3. Resource Generation | Generated agents/skills/commands | `[RESOURCES_GENERATED]` |
| 3b. Validation | `validation_report.json` | `[VALIDATION_COMPLETE]` |
| 4. CGF Handoff | Optimization branch + CGF run | `[CGF_TESTING_STARTED]` |

### Stage Details

**Stage 1: Objective Elicitation**
- Interactive Q&A to understand user's goal
- Captures constraints, success criteria, domain context
- Outputs structured `context_spec.json`

**Stage 2: Pattern & Resource Planning**
- Analyzes objective for pattern fit (see Pattern Selection Matrix below)
- Inventories required resources (agents, skills, commands)
- Identifies dependencies and execution order

**Stage 3: Resource Generation**
- Creates agent definitions with appropriate tools
- Generates skill files with guidelines
- Produces command wrappers for workflows

**Stage 3b: Validation**
- Syntax validation of generated resources
- Schema conformance checking
- Dependency resolution verification
- Outputs `validation_report.json`

**Stage 4: CGF Handoff**
- Creates optimization branch in git
- Initializes CGF test harness
- Triggers first optimization run

### Pattern Selection Matrix

Use these business signals to select the appropriate orchestration pattern:

| Business Signal | Recommended Pattern |
|-----------------|---------------------|
| "must happen in order", "pipeline", "stages" | Sequential Pipeline |
| "multiple specialists", "coordinate", "delegate" | Hierarchical Coordinator |
| "get multiple opinions", "compare approaches" | Broadcast/Consensus |
| "async", "event-driven", "reactive", "queue" | Event-driven Async |
| "shared workspace", "incremental refinement" | Blackboard Architecture |
| "mediate between services", "decouple" | Mediator Pattern |
| "equal peers", "collaborative", "negotiate" | Peer-to-Peer Coordination |
| "complex workflow", "multiple patterns needed" | Hybrid Pipeline |

---

## Phase 0: CGF Infrastructure (Foundation)

> **Status**: In Progress
> **Specification**: [CGF-INFRASTRUCTURE.md](./features/CGF-INFRASTRUCTURE.md)
> **Origin**: Patterns adopted from [agent-lightning](https://github.com/...) framework research

### Objective

Build the tracing and optimization infrastructure that enables training data collection for all resources (agents, skills, prompts, commands) **before** implementing orchestration patterns. This infrastructure is foundational because:

- **Tracing** provides execution visibility for debugging orchestration patterns
- **Reward signals** inform pattern selection heuristics
- **Store pattern** enables distributed execution from the start
- **Adapter framework** supports multiple resource types simultaneously

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CGF INFRASTRUCTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                     OPTIMIZATION ORCHESTRATOR                       │   │
│   │  (Manages optimization loops, resource versioning, convergence)     │   │
│   └─────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      OPTIMIZATION STORE (Redis)                      │  │
│   │  ├─ Task Queue (evaluations, resource versions)                     │  │
│   │  ├─ Span Store (OpenTelemetry traces)                               │  │
│   │  ├─ Resource Registry (agents, skills, prompts, commands)           │  │
│   │  └─ Results Store (rewards, metrics, feedback)                      │  │
│   └─────────────────────────────┬──────────────────────────────────────┘  │
│              │                  │                  │                       │
│              ▼                  ▼                  ▼                       │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│   │ MAIN-AGENT   │    │ AGENT-TWO    │    │ AGENT-THREE  │               │
│   │ (Runner)     │    │ (Runner)     │    │ (Runner)     │               │
│   │              │    │              │    │              │               │
│   │ Executes     │    │ Evaluates    │    │ Tests        │               │
│   │ resources    │    │ quality      │    │ correctness  │               │
│   │ Emits spans  │    │ Scores       │    │ Scores       │               │
│   └──────────────┘    └──────────────┘    └──────────────┘               │
│                                                                            │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                      ADAPTERS (Trace → Feedback)                    │  │
│   │  ├─ AgentAdapter (tool usage, task completion, turns)              │  │
│   │  ├─ SkillAdapter (activation accuracy, execution success)          │  │
│   │  ├─ PromptAdapter (output quality, hallucination rate)             │  │
│   │  └─ CommandAdapter (parse success, execution results)              │  │
│   └────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│                                 ▼                                          │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                      OPTIMIZATION ALGORITHMS                        │  │
│   │  ├─ DSPy Bootstrap (few-shot example optimization)                 │  │
│   │  ├─ TextGrad APO (textual gradient descent)                        │  │
│   │  └─ Hybrid (DSPy for examples, TextGrad for prompts)               │  │
│   └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Patterns Adopted from Agent-Lightning

| Pattern | Description | CGF Implementation |
|---------|-------------|-------------------|
| **Store Protocol** | Decoupled components communicate through central store | Redis-based `OptimizationStore` |
| **Span-Based Tracing** | Rich execution data via OpenTelemetry | `src/harness/tracer/` module |
| **Adapter Pattern** | Flexible trace → feedback transformation | `src/harness/optimization/adapters/` |
| **Multi-Dimensional Rewards** | Composite scoring for nuanced optimization | `ResourceReward` dataclass |
| **Resource Versioning** | Git-based history of all resource changes | Integration with existing checkpoint |

### Phase 0 Deliverables

| Sub-Phase | Description | Deliverables | Status |
|-----------|-------------|--------------|--------|
| **0.1** | OpenTelemetry Tracing | `src/harness/tracer/` module, SDK instrumentation | Not started |
| **0.2** | Optimization Store | `src/harness/optimization/store/` with Redis backend | Not started |
| **0.3** | Resource Registry | Multi-type resource management (agents, skills, prompts) | Not started |
| **0.4** | Adapter Framework | Trace → Feedback adapters for each resource type | Not started |
| **0.5** | Reward System | Multi-dimensional scoring with configurable weights | Not started |

### Container Roles in CGF

| Container | Role | Responsibilities |
|-----------|------|------------------|
| **main-agent** | Executor | Run resources against tasks, emit spans |
| **agent-two** | Evaluator | Score output quality, code review (formerly reviewer-agent) |
| **agent-three** | Validator | Run tests, check correctness (formerly tester-agent) |

### Dependencies

- **OpenTelemetry**: `opentelemetry-api>=1.27.0`, `opentelemetry-sdk>=1.27.0`
- **DSPy**: `dspy-ai>=3.0.0`
- **TextGrad**: `textgrad>=0.1.6`
- **Redis**: Existing from multi-agent profile

### Integration with Existing CGF Spec

Phase 0 implements the infrastructure layer described in [CONTEXT-GRAD-SPEC.md](./features/CONTEXT-GRAD-SPEC.md) Sections 1-2, enhanced with agent-lightning patterns. The existing CGF spec focuses on the optimization workflow; Phase 0 provides the underlying infrastructure that makes it possible.

---

## Implementation Plans

Three implementation tracks that proceed in order (Phase 0 first, then A/B in parallel):

- **Phase 0 (CGF Infrastructure)**: OpenTelemetry tracing, store, adapters, rewards (PREREQUISITE)
- **Plan A (Orchestration Infrastructure)**: Wire Redis/messaging into working orchestration layer
- **Plan B (Tooling)**: Extend context-engineering plugin with orchestration resources

**Recommended Approach**: Complete Phase 0 first to establish tracing infrastructure. Then execute Plans A and B as separate tracks. Each plan has internal phase dependencies but can proceed independently after Phase 0.

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

### Phase 5: ContextGrad Framework Integration

**Objective**: Leverage orchestration patterns for CGF test execution and optimization workflows.

**Dependencies**: Plan A Phases 1-4, CGF infrastructure (see [CONTEXT-GRAD-SPEC.md](./features/CONTEXT-GRAD-SPEC.md))

**Integration Points:**

| CGF Component | Orchestration Pattern | Use Case |
|---------------|----------------------|----------|
| TestHarness | Sequential Pipeline | Ordered test stage execution (syntax → unit → integration) |
| ParallelTestRunner | Broadcast | Run same tests across multiple configurations |
| OptimizationEngine | Hierarchical | Coordinator manages optimizer agents per resource type |
| MetricsCollector | Event-Driven | Async metrics aggregation from distributed test runs |

**Deliverables:**
1. TestHarness orchestration adapter - wraps patterns for CGF test stages
2. OrchestrationOptimizer agent - applies meta-optimization to orchestration configs
3. CGF-specific metrics in Prometheus (optimization iterations, convergence rate)
4. Hybrid pipeline preset for multi-stage optimization workflows

**Example Integration:**

```python
from harness.orchestration import SequentialPipeline, BroadcastMultiPerspective
from harness.optimization import TestHarness, TestStage

# CGF TestHarness using orchestration patterns
class OrchestrationTestHarness(TestHarness):
    def __init__(self):
        self.pipeline = SequentialPipeline([
            (TestStage.SYNTAX, "syntax-validator"),
            (TestStage.UNIT, "unit-test-runner"),
            (TestStage.INTEGRATION, "integration-test-runner"),
        ])

    async def run_all_stages(self, resource: str) -> TestResults:
        return await self.pipeline.execute(resource)
```

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
3. specs/implementation/ - Orchestrator class spec
4. Complete patterns/tool-restriction-patterns.md

### Phase 2: Skills & Commands

**Deliverables:**
1. skills/workflow-creation/SKILL.md
2. skills/orchestration-patterns/SKILL.md
3. commands/create-workflow.md

### Phase 3: Workflows & Examples

**Deliverables:**
1. workflows/ directory with reusable workflow definitions
2. examples/ directory with working multi-agent systems
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

## Implementation Timelines

**Execution Order**: Phase 0 must complete first. Plans A and B can then proceed in parallel.

### Phase 0 Timeline (CGF Infrastructure) - PREREQUISITE

| Sub-Phase | Feature | Dependencies | Status |
|-----------|---------|--------------|--------|
| **0.1** | OpenTelemetry Tracing (`src/harness/tracer/`) | None | Not started |
| **0.2** | Optimization Store (`src/harness/optimization/store/`) | 0.1 | Not started |
| **0.3** | Resource Registry (`src/harness/optimization/resources/`) | 0.2 | Not started |
| **0.4** | Adapter Framework (`src/harness/optimization/adapters/`) | 0.3 | Not started |
| **0.5** | Reward System (`src/harness/optimization/rewards.py`) | 0.4 | Not started |

### Plan A Timeline (Orchestration Infrastructure)

| Phase | Feature | Dependencies | Status |
|-------|---------|--------------|--------|
| A1 | Infrastructure foundation (`src/harness/orchestration/`) | **Phase 0** | Not started |
| A2 | Pattern integration (all 8 patterns) | A1 | Not started |
| A3 | Container coordination (multi-agent profile) | A2 | Not started |
| A4 | Production hardening (circuit breakers, checkpoints) | A3 | Not started |
| A5 | CGF optimization + orchestration metrics | A4 | Not started |

### Plan B Timeline (Tooling)

| Phase | Feature | Dependencies | Status |
|-------|---------|--------------|--------|
| B1 | Context Engineering Workflow foundation | **Phase 0** | Not started |
| B2 | Skills & commands (`orchestration-definition`, `validate-context-spec`) | B1 | Not started |
| B3 | Context engineer skill activation | B2 | Not started |
| B4 | Agentic Examples documentation | B3 | Not started |

### Interdependencies

**Phase 0 is prerequisite for all other phases.** After Phase 0 completes, Plans A and B can proceed independently:

| Integration Point | Phase 0 Provides | Plan A Uses | Plan B Uses |
|-------------------|------------------|-------------|-------------|
| Execution tracing | OpenTelemetry spans | Pattern debugging | Workflow monitoring |
| Resource management | Store + Registry | Orchestration state | Resource generation |
| Evaluation framework | Adapters + Rewards | Pattern selection metrics | Resource quality |
| Container coordination | agent-two, agent-three roles | Distributed execution | Parallel evaluation |

**Recommended integration**: Complete Phase 0 in full. Then complete A1-A2 and B1-B2 in parallel. CGF optimization (A5 + B3) is the final integration point.

---

## Execution Checklist

### Documentation Consolidation (Completed)

- [x] Delete notes/*.txt files
- [x] Create plugin directories: specs/, workflows/, examples/
- [x] Move RD2.md → specs/implementation/
- [x] Extract research.md examples → examples/
- [x] Delete consolidated reports
- [x] Consolidate amendments into feature specs
- [x] Merge ORCHESTRATION.md + ORCHESTRATION_ARCHITECTURE.md → ORCHESTRATION_PATTERNS.md
- [x] Merge AMENDMENTS.md into this roadmap

### Implementation Phases

**Phase 0 (CGF Infrastructure) - PREREQUISITE**

| Sub-Phase | Description | Deliverables | Status |
|-----------|-------------|--------------|--------|
| 0.1 | OpenTelemetry Tracing | `src/harness/tracer/` module, SDK instrumentation | Not started |
| 0.2 | Optimization Store | `src/harness/optimization/store/` with Redis backend | Not started |
| 0.3 | Resource Registry | Multi-type resource management | Not started |
| 0.4 | Adapter Framework | Trace → Feedback adapters | Not started |
| 0.5 | Reward System | Multi-dimensional scoring | Not started |

**Plan A (Orchestration Infrastructure)**

| Phase | Description | Deliverables | Status |
|-------|-------------|--------------|--------|
| A1 | Infrastructure foundation | `src/harness/orchestration/` module | Not started |
| A2 | Pattern integration | All 8 pattern implementations with tests | Not started |
| A3 | Container coordination | coordination-protocol.md, multi-agent prompts | Not started |
| A4 | Production hardening | Metrics, dashboards, circuit breakers | Not started |
| A5 | CGF integration | TestHarness adapter, optimization metrics | Not started |

**Plan B (Tooling)**

| Phase | Description | Deliverables | Status |
|-------|-------------|--------------|--------|
| B1 | Context Engineering Workflow foundation | `orchestration-definition` skill structure | Not started |
| B2 | Skills & commands | `validate-context-spec` command | Not started |
| B3 | Context engineer skill activation | Enhanced context-engineer.md | Not started |
| B4 | Agentic Examples | 8+ working example systems | Not started |

---

## Next Actions

**Priority 1: Phase 0 (CGF Infrastructure)**

Must complete before Plans A/B:

1. **Phase 0.1**: Create `src/harness/tracer/` module
   - OpenTelemetry integration
   - Span schema and context propagation
   - Redis and file exporters
   - SDK client instrumentation

2. **Phase 0.2**: Create `src/harness/optimization/store/`
   - OptimizationStore protocol
   - Redis implementation
   - Memory fallback for testing

3. **Phase 0.3-0.5**: Resource registry, adapters, rewards
   - Multi-type resource management
   - Trace → Feedback adapters
   - Multi-dimensional scoring

**Priority 2: Plans A/B (after Phase 0)**

Can proceed in parallel after Phase 0 completes:

**Plan A Track:**
1. **Phase A1**: Create `src/harness/orchestration/` module
   - Abstract base classes
   - TaskQueueManager with Redis backend
   - RetryStrategy implementation

**Plan B Track:**
1. **Phase B1**: Create `orchestration-definition` skill structure
   - Define skill manifest
   - Implement Q&A flow for objective elicitation
   - Create `context_spec.json` schema

2. **Phase B2**: Implement `validate-context-spec` command
   - Schema validation logic
   - Dependency resolution checks
   - Integration with skill workflow

---

## Consolidated Amendments Reference

The following amendments have been merged into their respective feature specifications:

| Former Amendment | Merged Into | Section |
|------------------|-------------|---------|
| Amendment 4: Validation Mechanism | [CONTEXT-GRAD-IMP.md](./features/CONTEXT-GRAD-IMP.md) | "Context Spec Validation" |
| Amendment 5: Pattern Inference | [CONTEXT_ENG_WF.md](./features/CONTEXT_ENG_WF.md) | Integrated into orchestration-definition skill |
| Amendment 7: Feedback Loop | [CONTEXT-GRAD-SPEC.md](./features/CONTEXT-GRAD-SPEC.md) | Section 11.7 "Orchestration Pattern Learning" |

This section preserved for historical reference. All active content is now in the feature specifications linked above.
