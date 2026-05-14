# Agentic Orchestration Implementation Roadmap

> **Created**: December 2025
> **Last Updated**: March 2026
> **Status**: Phase 0 + Phase 1 complete; CGF Stages 1-2 complete; Plans A/B deferred
> **Related**: [ORCHESTRATION_PATTERNS.md](./ORCHESTRATION_PATTERNS.md) | [CGF Plan](./CGF-EVAL-FRAMEWORK.md)

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

### Phase 1: Single-Agent Optimization Validation ✅

Phase 1 validates the optimization loop works end-to-end on a single agent before implementing multi-agent orchestration (Plans A & B):

| Sub-Phase | Description | Status |
|-----------|-------------|--------|
| 1A | Test case infrastructure - YAML-based test suites with validation | ✅ Complete |
| 1B | Agent runner - Execute agent with full tracing | ✅ Complete |
| 1C | Agentic optimizer - LLM self-critique optimization | ✅ Complete |
| 1D | Pipeline CLI - `python -m harness.optimization.cli.optimize` | ✅ Complete |

**Total Tests**: 1,182 optimization tests passing
**Target Agent**: `python-expert`
**Success Criteria**: Run optimization end-to-end with measurable improvement metric ✅

### CGF Stages (Eval Framework & Plugin Integration)

After Phase 1 validation, work shifted to a staged approach for evaluation framework and plugin integration. See [CGF Plan](./CGF-EVAL-FRAMEWORK.md) for full details.

| Stage | Description | Status | Tests |
|-------|-------------|--------|-------|
| **Stage 1** | Protocol layer + resource architect agent + DESIGN phase | ✅ Complete | 120 |
| **Stage 2** | MCP tool/server creation skills + orchestrator support | ✅ Complete | 47 |
| **Stage 3** | Evaluation framework (eval-architect, graders, eval harness) | Draft | - |
| **Stage 4** | End-to-end integration, hardening, documentation | Draft | - |

---

## Feature Index

Detailed specifications for each major capability:

| Feature | Specification | Status | Description |
|---------|---------------|--------|-------------|
| **CGF Infrastructure** | See [CLAUDE.md](../CLAUDE.md#cgf-optimization-framework) | **Phase 0 ✅, Phase 1 ✅, Stages 1-2 ✅** | Tracing, store, adapters, rewards, optimization, protocols, MCP creation |
| CGF Eval & Plugin Integration | [CGF Plan](./CGF-EVAL-FRAMEWORK.md) | Stages 1-2 complete, 3-4 draft | Protocol layer, resource architect, MCP skills, evaluation framework |
| Context Engineering Workflow | Superseded | - | Q&A workflow integrated into cgf-orchestrator |
| Container Architecture | [CONTAINERIZATION.md](./CONTAINERIZATION.md) | Decided | Subagent-first Docker model |
| Agentic Examples | Superseded | - | Merged into ORCHESTRATION_PATTERNS.md |
| Observability | Not yet written | Planning | Grafana dashboards, session reports |

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

> **Status**: Complete
> **Specification**: See [CLAUDE.md](../CLAUDE.md#cgf-optimization-framework) and [CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md)
> **Origin**: Patterns adopted from agent-lightning framework research

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
│   │  └─ Agentic (LLM self-critique with research heuristics)           │  │
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
| **0.1** | OpenTelemetry Tracing | `src/harness/tracer/` module, SDK instrumentation | ✅ Complete (97 tests) |
| **0.2** | Optimization Store | `src/harness/optimization/store/` with Redis backend | ✅ Complete (89 tests) |
| **0.3** | Resource Registry | Multi-type resource management (agents, skills, prompts) | ✅ Complete (65 tests) |
| **0.4** | Adapter Framework | Trace → Feedback adapters for each resource type | ✅ Complete (87 tests) |
| **0.5** | Reward System | Multi-dimensional scoring with configurable weights | ✅ Complete (50 tests) |

### Container Roles in CGF

| Container | Role | Responsibilities |
|-----------|------|------------------|
| **main-agent** | Executor | Run resources against tasks, emit spans |
| **agent-two** | Evaluator | Score output quality, code review (formerly reviewer-agent) |
| **agent-three** | Validator | Run tests, check correctness (formerly tester-agent) |

### Dependencies

- **OpenTelemetry**: `opentelemetry-api>=1.27.0`, `opentelemetry-sdk>=1.27.0`
- **Redis**: Existing from multi-agent profile

### Integration with Existing CGF Spec

Phase 0 implements the infrastructure layer enhanced with agent-lightning patterns. The optimization workflow is documented in [CLAUDE.md](../CLAUDE.md#cgf-optimization-framework); Phase 0 provides the underlying infrastructure that makes it possible.

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

**Dependencies**: Plan A Phases 1-4, CGF infrastructure (see [CLAUDE.md](../CLAUDE.md#cgf-optimization-framework))

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

## Implementation Timelines

**Execution Order**: Phase 0 must complete first. Plans A and B can then proceed in parallel.

### Phase 0 Timeline (CGF Infrastructure) - ✅ COMPLETE

| Sub-Phase | Feature | Dependencies | Status |
|-----------|---------|--------------|--------|
| **0.1** | OpenTelemetry Tracing (`src/harness/tracer/`) | None | ✅ Complete |
| **0.2** | Optimization Store (`src/harness/optimization/store/`) | 0.1 | ✅ Complete |
| **0.3** | Resource Registry (`src/harness/optimization/resources/`) | 0.2 | ✅ Complete |
| **0.4** | Adapter Framework (`src/harness/optimization/adapters/`) | 0.3 | ✅ Complete |
| **0.5** | Reward System (`src/harness/optimization/rewards.py`) | 0.4 | ✅ Complete |

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

**Phase 0 (CGF Infrastructure) - ✅ COMPLETE** (404 tests)

**CGF Stages (Eval Framework & Plugin Integration)** — See [CGF Plan](./CGF-EVAL-FRAMEWORK.md)
- Stage 1: Protocol layer + resource architect ✅ (120 tests)
- Stage 2: MCP creation skills ✅ (47 tests)
- Stage 3: Evaluation framework (draft)
- Stage 4: Integration & hardening (draft)

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

**Priority 1: CGF Stage 3 (Evaluation Framework)**

See [CGF Plan](./CGF-EVAL-FRAMEWORK.md) for full task list. Key deliverables:
- `cgf-eval-architect` agent for dynamic eval suite generation
- Grader infrastructure (deterministic, trajectory, LLM-judge)
- Eval harness for sandboxed agent sessions
- EVAL_DESIGN and EXECUTION_EVAL phases in orchestrator
- Feedback loop from execution results to optimizer

**Priority 2: CGF Stage 4 (Integration & Hardening)**

- Full pipeline E2E test
- Checkpoint/resume for new phases
- Human review gates
- Performance optimization and documentation

**Deferred: Plans A/B (Orchestration Infrastructure & Tooling)**

Plans A and B are deferred pending completion of CGF Stages 3-4. The CGF pipeline is the active development track. `src/harness/orchestration/` does not yet exist.

---

## Consolidated Amendments Reference

The following amendments were merged into feature specifications during the December 2025 planning phase. The original `features/` directory was consolidated into the [CGF Plan](./CGF-EVAL-FRAMEWORK.md).

| Former Amendment | Status |
|------------------|--------|
| Amendment 4: Validation Mechanism | Superseded by CGF Stage 3 eval framework |
| Amendment 5: Pattern Inference | Integrated into cgf-orchestrator agent |
| Amendment 7: Feedback Loop | Superseded by CGF Stage 3 feedback loop |
