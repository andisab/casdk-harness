# CGF Infrastructure Specification

> **Version**: 1.2.0
> **Status**: 🚧 Phase 1 In Progress (Phase 0 Complete)
> **Related**: [CONTEXT-GRAD-SPEC.md](./CONTEXT-GRAD-SPEC.md) | [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md)
> **Origin**: Patterns adopted from agent-lightning framework research

---

## Implementation Status

| Phase | Description | Status | Tests |
|-------|-------------|--------|-------|
| **0.1** | OpenTelemetry Tracing | ✅ Complete | 97 tests |
| **0.2** | Optimization Store | ✅ Complete | 89 tests |
| **0.3** | Resource Registry | ✅ Complete | 65 tests |
| **0.4** | Adapter Framework | ✅ Complete | 87 tests |
| **0.5** | Reward System | ✅ Complete | 50 tests |
| **0.6** | Integration | ✅ Complete | 16 tests |
| **1.0** | Single-Agent Optimization Validation | 🚧 In Progress | - |

**Phase 0 Total**: 404 tests passing

### Phase 0.6 Integration Summary

Phase 0.6 validates the full CGF pipeline end-to-end:

```
AgentSession.execute() → tracer → StoreSpanExporter → OptimizationStore → adapters → rewards
```

**Key Components Added**:
- `StoreSpanExporter` - Bridges tracer to OptimizationStore
- CGF configuration in `config.py` (`cgf_enabled`, `cgf_exporter`, etc.)
- Tracer initialization in `AgentSession`
- CGF Prometheus metrics in `monitoring.py`
- Integration tests in `tests/integration/test_cgf_pipeline.py`

### Phase 1: Single-Agent Optimization Validation

**Status**: 🚧 In Progress
**Goal**: Validate end-to-end optimization on single agent before multi-agent orchestration

| Sub-Phase | Description | Status |
|-----------|-------------|--------|
| 1A | Test case infrastructure | Pending |
| 1B | Agent runner with tracing | Pending |
| 1C | DSPy MIPROv2 integration | Pending |
| 1D | TextGrad TGD integration | Pending |
| 1E | Pipeline orchestration + CLI | Pending |

**New Modules:**
- `src/harness/optimization/testcases/` - Test case loading and validation
- `src/harness/optimization/runners/` - Agent execution with tracing
- `src/harness/optimization/optimizers/` - DSPy and TextGrad wrappers
- `src/harness/optimization/pipeline/` - End-to-end orchestration
- `src/harness/optimization/cli/` - CLI entry points

**CLI Usage (Target):**
```bash
python -m harness.optimization.cli.optimize \
    --agent python-expert \
    --test-suite tests/optimization/python_expert_tests.yaml \
    --optimizer dspy
```

---

## Executive Summary

CGF Infrastructure provides the foundational layer for the ContextGrad Framework, implementing patterns from the agent-lightning framework to enable:

- **OpenTelemetry-based tracing** for rich execution data collection
- **Decoupled store architecture** for distributed optimization
- **Adapter pattern** for flexible trace-to-feedback transformation
- **Multi-dimensional rewards** for nuanced resource evaluation

This infrastructure must be implemented **before** orchestration patterns (Plan A) and tooling (Plan B) to provide the tracing and evaluation capabilities they depend on.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [OpenTelemetry Tracing](#2-opentelemetry-tracing)
3. [Optimization Store](#3-optimization-store)
4. [Resource Registry](#4-resource-registry)
5. [Adapter Framework](#5-adapter-framework)
6. [Reward System](#6-reward-system)
7. [Container Roles](#7-container-roles)
8. [Implementation Guide](#8-implementation-guide)
9. [Configuration](#9-configuration)
10. [Migration Notes](#10-migration-notes)

---

## 1. Architecture Overview

### 1.1 High-Level Design

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
│   │ (Executor)   │    │ (Evaluator)  │    │ (Validator)  │               │
│   │              │    │              │    │              │               │
│   │ Run tasks    │    │ Score        │    │ Run tests    │               │
│   │ Emit spans   │    │ quality      │    │ Verify       │               │
│   └──────────────┘    └──────────────┘    └──────────────┘               │
│                                                                            │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                      ADAPTERS (Trace → Feedback)                    │  │
│   │  ├─ AgentAdapter      ├─ SkillAdapter                              │  │
│   │  ├─ PromptAdapter     └─ CommandAdapter                            │  │
│   └────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│                                 ▼                                          │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                      OPTIMIZATION ALGORITHMS                        │  │
│   │  ├─ DSPy Bootstrap    ├─ TextGrad APO    └─ Hybrid                 │  │
│   └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Design Principles

| Principle | Description | Implementation |
|-----------|-------------|----------------|
| **Decoupled Store** | Components communicate through central store, not directly | Redis-based `OptimizationStore` |
| **Span-Based Tracing** | Rich execution data via industry-standard format | OpenTelemetry SDK integration |
| **Adapter Pattern** | Flexible trace → feedback transformation | Per-resource-type adapters |
| **Multi-Dimensional Rewards** | Composite scoring for nuanced optimization | `ResourceReward` dataclass |
| **Resource Versioning** | Full history of all resource changes | Git integration + store metadata |

### 1.3 Component Dependencies

```
OpenTelemetry Tracing (0.1)
         │
         ▼
Optimization Store (0.2)
         │
         ▼
Resource Registry (0.3)
         │
         ▼
Adapter Framework (0.4)
         │
         ▼
Reward System (0.5)
```

---

## 2. OpenTelemetry Tracing

### 2.1 Directory Structure

```
src/harness/tracer/
├── __init__.py           # Public API: get_tracer(), SpanKind, Span
├── base.py               # TracerProtocol, Span, SpanKind, SpanStatus
├── otel_tracer.py        # OpenTelemetry implementation
├── context.py            # Trace context propagation
├── instrumentation.py    # SDK client auto-instrumentation
└── exporters/
    ├── __init__.py
    ├── file.py           # Export to JSON files (debugging)
    ├── redis.py          # Export to Redis store
    └── store.py          # Export to OptimizationStore (Phase 0.6)
```

### 2.2 Span Schema

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

class SpanKind(Enum):
    AGENT_EXECUTION = "agent_execution"
    TOOL_CALL = "tool_call"
    SUBAGENT_INVOCATION = "subagent_invocation"
    LLM_REQUEST = "llm_request"
    RESOURCE_EVALUATION = "resource_evaluation"

@dataclass
class Span:
    """OpenTelemetry-compatible span for CGF."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: datetime
    end_time: Optional[datetime]

    # Structured attributes
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Execution context
    agent_name: str = ""
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None

    # Status
    status: str = "OK"  # OK, ERROR, TIMEOUT
    error_message: Optional[str] = None

    # Metrics
    duration_ms: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None  # input, output, cached

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attributes": self.attributes,
            "agent_name": self.agent_name,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
        }
```

### 2.3 Instrumentation Points

| Location | Span Kind | Captured Data |
|----------|-----------|---------------|
| `AgentSession.execute()` | AGENT_EXECUTION | Full prompt, response, turns |
| `AgentSession._call_tool()` | TOOL_CALL | Tool name, args, result, duration |
| `direct_agent.call_agent()` | SUBAGENT_INVOCATION | Subagent name, prompt, response |
| SDK client calls | LLM_REQUEST | Model, tokens, latency, cost |

### 2.4 Tracer Protocol

```python
from typing import Protocol, Optional, Iterator, ContextManager

class TracerProtocol(Protocol):
    """Interface for tracing implementations."""

    def start_span(
        self,
        name: str,
        kind: SpanKind,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None,
    ) -> ContextManager[Span]:
        """Start a new span as context manager."""
        ...

    def current_span(self) -> Optional[Span]:
        """Get the current active span."""
        ...

    def export(self, span: Span) -> None:
        """Export span to configured exporters."""
        ...

    def flush(self) -> None:
        """Flush all pending spans."""
        ...
```

### 2.5 Usage Example

```python
from harness.tracer import get_tracer, SpanKind

tracer = get_tracer()

async def execute_agent_task(agent_name: str, prompt: str):
    with tracer.start_span(
        name=f"agent.{agent_name}.execute",
        kind=SpanKind.AGENT_EXECUTION,
        attributes={"agent_name": agent_name, "prompt_length": len(prompt)},
    ) as span:
        try:
            result = await agent.execute(prompt)
            span.attributes["result_length"] = len(result)
            return result
        except Exception as e:
            span.status = "ERROR"
            span.error_message = str(e)
            raise
```

---

## 3. Optimization Store

### 3.1 Directory Structure

```
src/harness/optimization/store/
├── __init__.py
├── protocol.py           # OptimizationStore protocol
├── models.py             # Pydantic models
├── redis_store.py        # Redis implementation
└── memory_store.py       # In-memory (testing)
```

### 3.2 Store Protocol

```python
from typing import Protocol, List, Optional
from datetime import datetime

class OptimizationStore(Protocol):
    """Central store for optimization data."""

    # Task Queue Operations
    def enqueue_evaluation(
        self,
        resource_id: str,
        resource_type: str,
        config: EvaluationConfig,
    ) -> EvaluationID:
        """Queue a resource for evaluation."""
        ...

    def dequeue_evaluation(self, runner_id: str) -> Optional[EvaluationTask]:
        """Get next evaluation task for a runner."""
        ...

    def update_evaluation_status(
        self,
        eval_id: EvaluationID,
        status: EvaluationStatus,
        result: Optional[EvaluationResult] = None,
    ) -> None:
        """Update evaluation status."""
        ...

    # Span Operations
    def store_span(self, span: Span) -> None:
        """Store a single span."""
        ...

    def store_spans(self, spans: List[Span]) -> None:
        """Batch store spans."""
        ...

    def query_spans(
        self,
        trace_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Span]:
        """Query spans with filters."""
        ...

    # Resource Operations
    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> ResourceVersion:
        """Register a new resource version."""
        ...

    def get_resource(
        self,
        resource_id: str,
        version: Optional[str] = None,
    ) -> Optional[Resource]:
        """Get resource by ID, optionally specific version."""
        ...

    def list_resource_versions(
        self,
        resource_id: str,
    ) -> List[ResourceVersion]:
        """List all versions of a resource."""
        ...

    # Results Operations
    def store_result(
        self,
        eval_id: EvaluationID,
        reward: ResourceReward,
        metadata: Dict[str, Any],
    ) -> None:
        """Store evaluation result."""
        ...

    def query_results(
        self,
        resource_id: str,
        limit: int = 100,
    ) -> List[EvaluationResult]:
        """Get results for a resource."""
        ...
```

### 3.3 Redis Implementation

```python
import redis
import json
from typing import Optional, List

class RedisOptimizationStore:
    """Redis-backed optimization store."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.client = redis.from_url(redis_url)

        # Key prefixes
        self.EVAL_QUEUE = "cgf:eval:queue"
        self.EVAL_STATUS = "cgf:eval:status:{eval_id}"
        self.SPANS = "cgf:spans:{trace_id}"
        self.RESOURCES = "cgf:resources:{resource_id}"
        self.RESOURCE_VERSIONS = "cgf:resources:{resource_id}:versions"
        self.RESULTS = "cgf:results:{resource_id}"

    def enqueue_evaluation(
        self,
        resource_id: str,
        resource_type: str,
        config: EvaluationConfig,
    ) -> EvaluationID:
        eval_id = generate_eval_id()
        task = {
            "eval_id": eval_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "config": config.to_dict(),
            "enqueued_at": datetime.utcnow().isoformat(),
        }
        self.client.rpush(self.EVAL_QUEUE, json.dumps(task))
        return eval_id

    def dequeue_evaluation(self, runner_id: str) -> Optional[EvaluationTask]:
        result = self.client.blpop(self.EVAL_QUEUE, timeout=5)
        if result:
            _, task_json = result
            return EvaluationTask.from_dict(json.loads(task_json))
        return None

    def store_span(self, span: Span) -> None:
        key = self.SPANS.format(trace_id=span.trace_id)
        self.client.zadd(key, {json.dumps(span.to_dict()): span.start_time.timestamp()})
        # Expire after 7 days
        self.client.expire(key, 7 * 24 * 60 * 60)

    # ... additional implementations
```

### 3.4 Memory Store (Testing)

```python
from collections import defaultdict
from threading import Lock

class MemoryOptimizationStore:
    """In-memory store for testing."""

    def __init__(self):
        self._lock = Lock()
        self._eval_queue: List[EvaluationTask] = []
        self._spans: Dict[str, List[Span]] = defaultdict(list)
        self._resources: Dict[str, Resource] = {}
        self._results: Dict[str, List[EvaluationResult]] = defaultdict(list)

    # ... implementations with thread-safe operations
```

---

## 4. Resource Registry

### 4.1 Directory Structure

```
src/harness/optimization/resources/
├── __init__.py
├── base.py               # Resource protocol, ResourceVersion
├── agent_resource.py     # Agent definition wrapper
├── skill_resource.py     # Skill wrapper
├── prompt_resource.py    # Raw prompt wrapper
└── command_resource.py   # Command wrapper
```

### 4.2 Resource Protocol

```python
from typing import Protocol, Dict, Any, Optional
from pathlib import Path

class ResourceProtocol(Protocol):
    """Interface for optimizable resources."""

    @property
    def resource_id(self) -> str:
        """Unique identifier."""
        ...

    @property
    def resource_type(self) -> str:
        """Type: agent, skill, prompt, command."""
        ...

    @property
    def content(self) -> str:
        """Raw content (markdown, yaml, etc.)."""
        ...

    @property
    def metadata(self) -> Dict[str, Any]:
        """Parsed metadata (frontmatter, etc.)."""
        ...

    @classmethod
    def load(cls, path: Path) -> "ResourceProtocol":
        """Load resource from file."""
        ...

    def save(self, path: Path) -> None:
        """Save resource to file."""
        ...

    def diff(self, other: "ResourceProtocol") -> str:
        """Generate diff between versions."""
        ...

    def validate(self) -> List[ValidationError]:
        """Validate resource structure."""
        ...
```

### 4.3 Agent Resource

```python
@dataclass
class AgentResource:
    """Wrapper for agent definition files."""

    name: str
    description: str
    model: str
    tools: List[str]
    system_prompt: str
    max_turns: int = 100
    color: Optional[str] = None

    _file_path: Optional[Path] = None

    @property
    def resource_id(self) -> str:
        return f"agent:{self.name}"

    @property
    def resource_type(self) -> str:
        return "agent"

    @property
    def content(self) -> str:
        """Generate markdown with YAML frontmatter."""
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "tools": ", ".join(self.tools),
        }
        if self.max_turns != 100:
            frontmatter["max_turns"] = self.max_turns
        if self.color:
            frontmatter["color"] = self.color

        yaml_str = yaml.dump(frontmatter, default_flow_style=False)
        return f"---\n{yaml_str}---\n\n{self.system_prompt}"

    @classmethod
    def load(cls, path: Path) -> "AgentResource":
        """Load from .md file with YAML frontmatter."""
        content = path.read_text()
        # Parse YAML frontmatter
        match = re.match(r"^---\n(.+?)\n---\n\n(.+)$", content, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid agent file format: {path}")

        frontmatter = yaml.safe_load(match.group(1))
        system_prompt = match.group(2)

        return cls(
            name=frontmatter["name"],
            description=frontmatter.get("description", ""),
            model=frontmatter.get("model", "sonnet"),
            tools=frontmatter.get("tools", "").split(", "),
            system_prompt=system_prompt,
            max_turns=frontmatter.get("max_turns", 100),
            color=frontmatter.get("color"),
            _file_path=path,
        )
```

---

## 5. Adapter Framework

### 5.1 Directory Structure

```
src/harness/optimization/adapters/
├── __init__.py
├── base.py               # Adapter protocol
├── agent_adapter.py      # Spans → AgentFeedback
├── skill_adapter.py      # Spans → SkillFeedback
├── prompt_adapter.py     # Spans → PromptFeedback
├── command_adapter.py    # Spans → CommandFeedback
└── triplet_adapter.py    # Spans → Training triplets
```

### 5.2 Adapter Protocol

```python
from typing import Protocol, TypeVar, Generic, Sequence

T_from = TypeVar("T_from")
T_to = TypeVar("T_to")

class Adapter(Protocol[T_from, T_to]):
    """Generic adapter for data transformation."""

    def adapt(self, source: T_from) -> T_to:
        """Transform source data to target format."""
        ...

class TraceAdapter(Protocol[T_to]):
    """Specialized adapter for span sequences."""

    def adapt(self, spans: Sequence[Span]) -> T_to:
        """Transform spans to feedback."""
        ...

    @property
    def resource_type(self) -> str:
        """Resource type this adapter handles."""
        ...
```

### 5.3 Agent Adapter

```python
@dataclass
class AgentFeedback:
    """Structured feedback for agent optimization."""

    # Execution metrics
    task_completed: bool
    turns_taken: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    duration_seconds: float

    # Tool usage
    tools_used: List[str]
    tool_success_rate: float
    tool_error_count: int

    # Quality indicators
    error_count: int
    retry_count: int
    timeout_count: int

    # Computed scores
    efficiency_score: float
    reliability_score: float

    def to_reward(self) -> "ResourceReward":
        """Convert to ResourceReward."""
        return ResourceReward(
            task_completion=1.0 if self.task_completed else 0.0,
            efficiency=self._compute_efficiency(),
            quality=self._compute_quality(),
            safety=1.0 - (self.error_count / max(self.turns_taken, 1)),
        )

class AgentAdapter:
    """Transform agent execution spans to feedback."""

    @property
    def resource_type(self) -> str:
        return "agent"

    def adapt(self, spans: Sequence[Span]) -> AgentFeedback:
        """Extract agent feedback from execution spans."""

        agent_spans = [s for s in spans if s.kind == SpanKind.AGENT_EXECUTION]
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]

        # Compute metrics
        total_tokens = sum(
            (s.token_usage or {}).get("total", 0) for s in spans
        )

        tool_success = sum(1 for s in tool_spans if s.status == "OK")
        tool_errors = sum(1 for s in tool_spans if s.status == "ERROR")

        return AgentFeedback(
            task_completed=self._detect_completion(spans),
            turns_taken=len(agent_spans),
            total_tokens=total_tokens,
            input_tokens=sum((s.token_usage or {}).get("input", 0) for s in spans),
            output_tokens=sum((s.token_usage or {}).get("output", 0) for s in spans),
            duration_seconds=self._compute_duration(spans),
            tools_used=list(set(s.attributes.get("tool_name") for s in tool_spans)),
            tool_success_rate=tool_success / max(len(tool_spans), 1),
            tool_error_count=tool_errors,
            error_count=sum(1 for s in spans if s.status == "ERROR"),
            retry_count=sum(1 for s in spans if "retry" in s.name.lower()),
            timeout_count=sum(1 for s in spans if s.status == "TIMEOUT"),
            efficiency_score=self._compute_efficiency_score(spans),
            reliability_score=self._compute_reliability_score(spans),
        )
```

---

## 6. Reward System

### 6.1 Multi-Dimensional Rewards

```python
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ResourceReward:
    """Multi-dimensional reward for resource evaluation."""

    # Core dimensions (0.0 - 1.0)
    task_completion: float      # Did it achieve the goal?
    efficiency: float           # Token usage, turn count, latency
    quality: float              # Output quality, formatting, correctness
    safety: float               # No errors, no destructive actions

    # Resource-specific dimensions
    extra: Dict[str, float] = field(default_factory=dict)

    # Primary metric for optimization
    primary_metric: str = "task_completion"

    def composite(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute weighted composite score."""
        if weights is None:
            weights = {
                "task_completion": 0.4,
                "efficiency": 0.2,
                "quality": 0.3,
                "safety": 0.1,
            }

        score = 0.0
        for dim, weight in weights.items():
            if dim in ["task_completion", "efficiency", "quality", "safety"]:
                score += getattr(self, dim) * weight
            elif dim in self.extra:
                score += self.extra[dim] * weight

        return score

    def improvement_over(self, baseline: "ResourceReward") -> Dict[str, float]:
        """Calculate percentage improvement over baseline."""
        improvements = {}

        for dim in ["task_completion", "efficiency", "quality", "safety"]:
            baseline_val = getattr(baseline, dim)
            current_val = getattr(self, dim)
            if baseline_val > 0:
                improvements[dim] = (current_val - baseline_val) / baseline_val * 100
            else:
                improvements[dim] = current_val * 100

        return improvements

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "task_completion": self.task_completion,
            "efficiency": self.efficiency,
            "quality": self.quality,
            "safety": self.safety,
            "extra": self.extra,
            "primary_metric": self.primary_metric,
            "composite_score": self.composite(),
        }
```

### 6.2 Resource-Specific Rewards

```python
# Agent-specific extra dimensions
agent_reward = ResourceReward(
    task_completion=0.85,
    efficiency=0.72,
    quality=0.90,
    safety=0.95,
    extra={
        "tool_usage_accuracy": 0.88,
        "response_coherence": 0.92,
        "instruction_following": 0.85,
    },
)

# Skill-specific extra dimensions
skill_reward = ResourceReward(
    task_completion=0.90,
    efficiency=0.80,
    quality=0.85,
    safety=1.0,
    extra={
        "activation_accuracy": 0.95,  # Skill triggered when needed
        "coverage": 0.88,             # Handles expected scenarios
    },
)
```

---

## 7. Container Roles

### 7.1 Role Assignment

| Container | Role | Responsibilities | CGF Functions |
|-----------|------|------------------|---------------|
| **main-agent** | Executor | Execute resources against tasks | `dequeue_evaluation()`, emit spans |
| **agent-two** | Evaluator | Score output quality | `store_result()` with quality scores |
| **agent-three** | Validator | Run tests, verify correctness | `store_result()` with test results |

### 7.2 Distributed Workflow

```
1. Orchestrator enqueues evaluation task to Redis
   └─> cgf:eval:queue

2. main-agent dequeues task
   └─> Executes resource
   └─> Emits spans to cgf:spans:{trace_id}

3. agent-two evaluates quality (parallel)
   └─> Queries spans
   └─> Applies AgentAdapter
   └─> Stores quality scores

4. agent-three runs tests (parallel)
   └─> Queries spans
   └─> Runs validation scripts
   └─> Stores test results

5. Orchestrator aggregates results
   └─> Computes ResourceReward
   └─> Decides: keep, improve, or rollback

6. Algorithm generates improved version
   └─> DSPy/TextGrad optimization
   └─> New resource version registered

7. Repeat until convergence
```

### 7.3 Container Communication

All communication through Redis:

```python
# Channels
cgf:eval:queue          # Evaluation task queue
cgf:eval:status:{id}    # Per-evaluation status
cgf:spans:{trace_id}    # Spans for a trace
cgf:results:{resource}  # Results for a resource
cgf:resources:{id}      # Resource content and versions
```

---

## 8. Implementation Guide

### 8.1 Phase 0.1: OpenTelemetry Tracing

1. Create `src/harness/tracer/` module
2. Implement `OTelTracer` with `start_span()`, `current_span()`, `export()`
3. Add Redis exporter for span storage
4. Instrument `AgentSession.execute()` and tool calls
5. Add tracing to `direct_agent.call_agent()`

### 8.2 Phase 0.2: Optimization Store

1. Create `src/harness/optimization/store/` module
2. Define `OptimizationStore` protocol
3. Implement `RedisOptimizationStore`
4. Implement `MemoryOptimizationStore` for testing
5. Add store initialization to `HarnessConfig`

### 8.3 Phase 0.3: Resource Registry

1. Create `src/harness/optimization/resources/` module
2. Define `ResourceProtocol`
3. Implement `AgentResource`, `SkillResource`, `PromptResource`, `CommandResource`
4. Add resource loading/saving to store
5. Integrate with existing `AgentDefinition` from `agents/definitions.py`

### 8.4 Phase 0.4: Adapter Framework

1. Create `src/harness/optimization/adapters/` module
2. Define `TraceAdapter` protocol
3. Implement `AgentAdapter`, `SkillAdapter`, `PromptAdapter`, `CommandAdapter`
4. Add `TripletAdapter` for training data generation

### 8.5 Phase 0.5: Reward System

1. Create `src/harness/optimization/rewards.py`
2. Implement `ResourceReward` dataclass
3. Add composite scoring with configurable weights
4. Integrate with adapters for automatic reward computation

---

## 9. Configuration

### 9.1 Environment Variables

```bash
# CGF Infrastructure Settings
CGF_ENABLED=true
CGF_STORE_TYPE=redis                    # redis, memory
CGF_REDIS_URL=redis://localhost:6379

# Tracing Settings
CGF_TRACING_ENABLED=true
CGF_TRACING_EXPORTER=redis              # redis, file, both
CGF_TRACING_FILE_PATH=logs/spans.jsonl
CGF_SPAN_RETENTION_DAYS=7

# Reward Weights
CGF_REWARD_WEIGHT_COMPLETION=0.4
CGF_REWARD_WEIGHT_EFFICIENCY=0.2
CGF_REWARD_WEIGHT_QUALITY=0.3
CGF_REWARD_WEIGHT_SAFETY=0.1
```

### 9.2 HarnessConfig Extensions

```python
# src/harness/config.py additions

class CGFConfig(BaseSettings):
    """CGF Infrastructure configuration."""

    enabled: bool = True
    store_type: str = "redis"
    redis_url: str = "redis://localhost:6379"

    tracing_enabled: bool = True
    tracing_exporter: str = "redis"
    tracing_file_path: str = "logs/spans.jsonl"
    span_retention_days: int = 7

    reward_weights: Dict[str, float] = {
        "task_completion": 0.4,
        "efficiency": 0.2,
        "quality": 0.3,
        "safety": 0.1,
    }

    class Config:
        env_prefix = "CGF_"
```

---

## 10. Migration Notes

### 10.1 Changes from Original CGF Spec

| Original (CONTEXT-GRAD-SPEC.md) | Enhanced (CGF Infrastructure) |
|--------------------------------|-------------------------------|
| Direct component coupling | Decoupled via OptimizationStore |
| Prometheus metrics only | OpenTelemetry span tracing |
| Single-dimensional metrics | Multi-dimensional ResourceReward |
| Test harness evaluation | Adapter-based feedback |
| Manual resource management | Resource registry with versioning |

### 10.2 Integration with Existing Code

- **checkpoint.py**: CGF store uses checkpoint for resource versioning
- **monitoring.py**: Prometheus metrics exported alongside spans
- **messaging.py**: Redis channels extended for CGF communication
- **plugin_manager.py**: Resource registry integrates with plugin resources

### 10.3 Backward Compatibility

- Existing agent definitions unchanged
- Prometheus metrics still exported
- Checkpoint system unmodified
- New infrastructure is additive, not replacing

---

## Appendix A: Dependencies

```toml
# pyproject.toml additions

[project.optional-dependencies]
cgf = [
    "opentelemetry-api>=1.27.0",
    "opentelemetry-sdk>=1.27.0",
    "opentelemetry-exporter-otlp>=1.27.0",
    "dspy-ai>=3.0.0",
    "textgrad>=0.1.6",
]
```

---

## Appendix B: Testing Strategy

### Unit Tests

```python
# tests/unit/test_tracer.py
def test_span_creation():
    tracer = OTelTracer()
    with tracer.start_span("test", SpanKind.AGENT_EXECUTION) as span:
        assert span.trace_id is not None
        assert span.kind == SpanKind.AGENT_EXECUTION

# tests/unit/test_store.py
def test_memory_store_roundtrip():
    store = MemoryOptimizationStore()
    eval_id = store.enqueue_evaluation("agent:test", "agent", config)
    task = store.dequeue_evaluation("runner-1")
    assert task.eval_id == eval_id

# tests/unit/test_adapters.py
def test_agent_adapter():
    adapter = AgentAdapter()
    spans = [create_test_span()]
    feedback = adapter.adapt(spans)
    assert feedback.turns_taken >= 1
```

### Integration Tests

```python
# tests/integration/test_cgf_workflow.py
async def test_full_optimization_cycle():
    store = RedisOptimizationStore(redis_url)
    tracer = OTelTracer(exporter=RedisSpanExporter(store))

    # 1. Register resource
    resource = AgentResource.load(Path("agents/configs/test-agent.md"))
    version = store.register_resource(resource)

    # 2. Enqueue evaluation
    eval_id = store.enqueue_evaluation(resource.resource_id, "agent", config)

    # 3. Execute with tracing
    task = store.dequeue_evaluation("test-runner")
    async with tracer.start_span("evaluation", SpanKind.RESOURCE_EVALUATION):
        result = await execute_resource(resource, task)

    # 4. Apply adapter
    spans = store.query_spans(resource_id=resource.resource_id)
    feedback = AgentAdapter().adapt(spans)

    # 5. Store result
    store.store_result(eval_id, feedback.to_reward(), {"iteration": 1})

    # Verify
    results = store.query_results(resource.resource_id)
    assert len(results) == 1
```

---

**Last Updated**: December 23, 2025
**Maintainer**: Andis A. Blukis
**Phase 0 Complete**: All infrastructure components implemented and tested
