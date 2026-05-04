# Multi-Agent Orchestration Patterns

**A Developer's Reference for Multi-Agent Coordination with Claude Agent SDK**

Version 2.0 | December 19, 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Quick Reference](#quick-reference)
3. [Foundation Layer: Agent Communication](#foundation-layer-agent-communication)
4. [Core Orchestration Patterns](#core-orchestration-patterns)
   - [Pattern 1: Sequential Pipeline](#pattern-1-sequential-pipeline)
   - [Pattern 2: Hierarchical Coordination](#pattern-2-hierarchical-coordination)
   - [Pattern 3: Broadcast Multi-Perspective](#pattern-3-broadcast-multi-perspective)
   - [Pattern 4: Blackboard Architecture](#pattern-4-blackboard-architecture)
   - [Pattern 5: Mediator Pattern](#pattern-5-mediator-pattern)
   - [Pattern 6: Peer-to-Peer Coordination](#pattern-6-peer-to-peer-coordination)
   - [Pattern 7: Hybrid Pipeline Architecture](#pattern-7-hybrid-pipeline-architecture)
   - [Pattern 8: Event-Driven Async](#pattern-8-event-driven-async)
5. [Advanced Components](#advanced-components)
6. [Production Patterns](#production-patterns)
7. [Framework-Specific Best Practices](#framework-specific-best-practices)
8. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)
9. [Migration Guide](#migration-guide)
10. [References](#references)

---

## Executive Summary

### Overview

Multi-agent orchestration is the art and science of coordinating multiple AI agents to solve complex problems that exceed the capabilities of a single agent. This guide presents **eight orchestration patterns** identified through comprehensive research and analysis of production multi-agent systems, with specific focus on implementation using the **Claude Agent SDK**.

> **Note: Design Specification**
> This document contains design specifications with example code. The patterns and implementations shown here are reference designs, not working code in the repository. The `src/harness/orchestration/` directory does not yet exist. See [ORCHESTRATION_ROADMAP.md](./ORCHESTRATION_ROADMAP.md) for implementation status and timeline.

### Pattern Selection Matrix

| Pattern | Best For | Complexity | Scalability | SDK Support |
|---------|----------|------------|-------------|-------------|
| **Sequential Pipeline** | Linear workflows, data processing | Low | Medium | Native |
| **Hierarchical Coordination** | Complex decomposition, structured problems | Medium | High | Direct |
| **Broadcast Multi-Perspective** | Consensus, quality checks | Medium | Medium | Direct |
| **Blackboard Architecture** | Complex problem-solving, incremental solutions | Medium | Medium | Custom |
| **Mediator Pattern** | Complex routing, policy enforcement | Medium | Medium | Custom |
| **Peer-to-Peer** | Dynamic environments, fault tolerance | High | Very High | Custom |
| **Hybrid Pipeline** | Production systems, multi-phase workflows | Medium-High | High | Direct |
| **Event-Driven Async** | Distributed systems, long-running | High | Very High | Redis |

### Key Insights from Research

1. **No Universal Solution**: Different patterns excel in different scenarios. Pattern selection depends on problem characteristics, team size, budget constraints, and performance requirements.

2. **Hybrid Approaches Dominate**: Production systems rarely use pure implementations. Most successful systems combine multiple patterns (e.g., Hierarchical planning + Pipeline execution + Ensemble verification).

3. **Context Management is Critical**: For LLM agents, token costs and context window limits require careful management through summarization, filtering, and hierarchical compression.

4. **Start Simple, Add Complexity**: Research consistently recommends beginning with Sequential or Hierarchical patterns, then evolving to more complex hybrid approaches based on actual needs.

5. **Optimization Hierarchy**:
   - **Caching**: 90%+ cost reduction (highest ROI)
   - **Model selection**: 30-90% cost reduction
   - **Parallel execution**: 30-70% latency reduction
   - **Context optimization**: 20-50% token savings

### Claude Agent SDK Advantages

The Claude Agent SDK is optimally suited for hierarchical and pipeline patterns due to:

- **200K context window**: Comprehensive analysis with full file inclusion
- **Extended thinking capability**: Deep reasoning for complex coordinator agents (Claude Opus 4.5)
- **Structured outputs**: Native JSON support for reliable agent communication
- **Multiple model tiers**: Haiku (fast/cheap) → Sonnet (balanced) → Opus (powerful)
- **Direct agent invocation**: Simple `harness.direct_agent` calls for parent-child relationships

### Existing Infrastructure

| Built (Ready) | Designed (Not Implemented) |
|---------------|---------------------------|
| RedisMessageBroker (messaging.py) | Orchestrator class |
| CircuitBreaker (messaging.py) | TaskQueueManager class |
| AgentSession.publish_task_result() | RetryStrategy class |
| AgentSession.wait_for_dependency() | Pattern implementations |
| direct_agent.py (call_agent) | Container coordination protocol |
| Docker multi-agent profile | |
| Redis streams consumer groups | |

---

## Quick Reference

### Pattern Decision Tree

```
Start
  │
  ├─ Task is simple/linear?
  │  └─> Sequential Pipeline
  │
  ├─ Task needs decomposition + parallel execution?
  │  └─> Hierarchical Coordinator
  │
  ├─ Need multiple perspectives/consensus?
  │  └─> Broadcast Multi-Perspective
  │
  ├─ Complex problem-solving, incremental solutions?
  │  └─> Blackboard Architecture
  │
  ├─ Need complex routing or policy enforcement?
  │  └─> Mediator Pattern
  │
  ├─ Need fault tolerance, no central coordinator?
  │  └─> Peer-to-Peer
  │
  ├─ Production system with multiple phases?
  │  └─> Hybrid Pipeline
  │
  └─ Long-running/distributed/async?
     └─> Event-Driven Async
```

### Pattern Relationships

```
Hierarchical ←→ Mediator (similar central control)
     ↓
Pipeline (subset of hierarchical with linear flow)

Peer-to-Peer ←→ Blackboard (both support collaboration)
     ↓
Swarm (extreme P2P with many simple agents)

Mediator + Peer-to-Peer = Hybrid with fallback
Hierarchical + Blackboard = Multi-level collaboration
```

---

## Foundation Layer: Agent Communication

### Communication Mechanisms

The harness provides **three communication primitives**:

#### A. Direct Invocation (Synchronous)
**Location:** `src/harness/direct_agent.py`

```python
from harness.direct_agent import call_agent, call_agent_simple

# Simple text response
response = await call_agent_simple(
    "python-expert",
    "Explain list comprehensions"
)

# Streaming response with full message types
async for message in call_agent("python-expert", "Review this code"):
    if isinstance(message, AssistantMessage):
        print(message.content)
```

**Best For:**
- Sequential workflows
- Request-response patterns
- Parent-child agent relationships
- Real-time interaction

#### B. Redis Streams (Asynchronous)
**Location:** `src/harness/messaging.py`

```python
from harness.messaging import RedisMessageBroker

broker = RedisMessageBroker()
broker.connect()

# Publish result
message_id = broker.publish_result(
    agent_id="agent-1",
    result={"status": "complete", "data": {...}},
    stream_name="agent:tasks"
)

# Consume results
messages = broker.consume_results(
    stream_name="agent:tasks",
    last_id="0",
    count=10,
    block=1000
)
```

**Best For:**
- Event-driven architectures
- Async coordination
- Distributed workflows
- Long-running tasks
- Cross-container communication

#### C. Agent Session Inter-Agent Methods
**Location:** `src/harness/agent.py`

```python
session = AgentSession(agent_name="coordinator")

# Publish result for other agents
session.publish_task_result(
    task_id="task_123",
    result={"findings": [...]}
)

# Wait for dependency
result = await session.wait_for_dependency(
    dependency_agent="analyzer",
    task_id="task_123",
    timeout=60
)
```

**Best For:**
- Dependency management
- Task coordination
- Result synchronization

### Communication Pattern Selection

| Scenario | Use | Why |
|----------|-----|-----|
| Parent→Child task | Direct Invocation | Synchronous, maintains context |
| Sibling agents | Redis Streams | Decoupled, async |
| Result aggregation | Direct Invocation | Need immediate response |
| Event notification | Redis Streams | Fire-and-forget |
| Dependency wait | Session methods | Built-in timeout/retry |

---

## Core Orchestration Patterns

### Pattern 1: Sequential Pipeline

**Complexity: Low | Scalability: Medium | SDK Support: Native**

#### Core Concept

Linear chain of agents, each processing output from previous. Most predictable and debuggable pattern for well-defined problems.

#### Architecture

```
Input → Agent A → Agent B → Agent C → Final Output
```

#### Characteristics

- ✅ **Simple**: Easy to understand and debug
- ✅ **Deterministic**: Predictable execution order
- ✅ **Context preservation**: Each stage sees previous output
- ⚠️ **Sequential**: Cannot parallelize
- ⚠️ **Brittle**: One failure stops entire pipeline

#### Best Use Cases

- Data transformation pipelines
- Multi-pass refinement (draft → review → polish)
- Document generation workflows
- Code analysis → security review → report

#### Implementation

```python
# src/harness/orchestration/patterns/sequential_pipeline.py

import asyncio
from typing import Any, List, Dict
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class SequentialPipeline:
    """Sequential pipeline for linear agent workflows."""

    def __init__(self, stages: List[Dict[str, Any]]):
        """Initialize pipeline with stages.

        Args:
            stages: List of dicts with keys:
                - agent_name: Name of agent to invoke
                - prompt_template: Template for prompt (uses {input} placeholder)
                - transform: Optional function to transform output
        """
        self.stages = stages
        self.results: List[Dict[str, Any]] = []

    async def execute(
        self,
        initial_input: str,
        timeout_per_stage: int = 120
    ) -> Dict[str, Any]:
        """Execute pipeline stages sequentially."""
        current_input = initial_input

        for idx, stage in enumerate(self.stages):
            agent_name = stage["agent_name"]
            prompt_template = stage["prompt_template"]
            transform = stage.get("transform")

            logger.info(
                "Executing pipeline stage",
                stage=idx + 1,
                total_stages=len(self.stages),
                agent=agent_name,
            )

            try:
                prompt = prompt_template.format(input=current_input)

                async with asyncio.timeout(timeout_per_stage):
                    output = await call_agent_simple(agent_name, prompt)

                if transform:
                    output = transform(output)

                self.results.append({
                    "stage": idx,
                    "agent": agent_name,
                    "input": current_input[:200],
                    "output": output[:200],
                    "status": "success",
                })

                current_input = output

            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "final_output": None,
                    "stage_results": self.results,
                    "failed_stage": idx,
                    "error": f"Stage {idx + 1} timeout",
                }
            except Exception as e:
                return {
                    "success": False,
                    "final_output": None,
                    "stage_results": self.results,
                    "failed_stage": idx,
                    "error": str(e),
                }

        return {
            "success": True,
            "final_output": current_input,
            "stage_results": self.results,
            "failed_stage": None,
        }


# Example usage
async def example_code_review_pipeline():
    """Example: Code analysis → Security review → Final report"""

    pipeline = SequentialPipeline(stages=[
        {
            "agent_name": "python-expert",
            "prompt_template": "Analyze this code for quality:\n{input}",
        },
        {
            "agent_name": "security-expert",
            "prompt_template": "Security review based on analysis:\n{input}",
        },
        {
            "agent_name": "dev-code-review-expert",
            "prompt_template": "Create final report from:\n{input}",
        },
    ])

    code = '''
    def login(username, password):
        query = f"SELECT * FROM users WHERE name='{username}' AND pass='{password}'"
        return db.execute(query)
    '''

    result = await pipeline.execute(code)

    if result["success"]:
        print(f"Final output:\n{result['final_output']}")
    else:
        print(f"Pipeline failed at stage {result['failed_stage'] + 1}")
```

---

### Pattern 2: Hierarchical Coordination

**Complexity: Medium | Scalability: High | SDK Support: Direct**

**Rank in Research: #1 | Appeared in 8/8 research documents**

#### Core Concept

Tree-structured organization with clear authority levels where tasks flow top-down and results aggregate bottom-up. Most predictable and debuggable pattern for well-defined problems.

#### Architecture

```
       Master Coordinator (Opus/Sonnet)
      /          |              \
Manager A     Manager B      Manager C (Sonnet)
/    \          |           /    \
W1    W2       W3          W4    W5 (Haiku/Sonnet)
```

#### Key Characteristics

- **Clear Chain of Command**: Each agent reports to exactly one parent
- **Span of Control**: 5-10 direct reports per coordinator
- **Top-Down Delegation**: Tasks decomposed at each level
- **Bottom-Up Aggregation**: Results summarized up the hierarchy
- **Model Selection**: Stronger models at higher levels (Opus → Sonnet → Haiku)

#### Variants

**1. Coordinator-Executor Pattern** (Most Common)
- Single coordinator with multiple specialized executors
- Coordinator plans, executors perform
- Best for: 2-10 agents, well-defined tasks

**2. Multi-Level Hierarchy** (3+ levels)
- Master → Domain Managers → Specialized Workers
- Progressive task refinement at each level
- Best for: 20-200 agents, complex domains

**3. Hierarchical Task Network (HTN) Decomposition**
- Recursive decomposition into primitive actions
- Formal task definitions and operators
- Best for: Planning systems, known task structures

#### Advantages

✅ Clear responsibility boundaries
✅ Predictable and debuggable behavior
✅ Efficient for well-defined problems
✅ Natural error escalation paths
✅ Easy to track progress
✅ Token-efficient (manager maintains global context, workers get local views)

#### Trade-offs

⚠️ Single point of failure at top
⚠️ Can be slow if not parallelized
⚠️ Less flexible for exploratory tasks
⚠️ Requires good upfront decomposition
⚠️ Communication latency for deep trees

#### Best Use Cases

- Well-structured problems (code review, security audits)
- Business process automation
- Tasks with clear subtask dependencies
- When centralized control is desired
- Compliance requiring audit trails

#### Implementation

```python
# src/harness/orchestration/patterns/hierarchical_coordinator.py

import asyncio
import json
from typing import Any, List, Dict
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class HierarchicalCoordinator:
    """Manager-worker pattern for task decomposition and parallel execution."""

    def __init__(
        self,
        manager_agent: str,
        worker_agents: List[str] | None = None,
        decompose_prompt_template: str | None = None,
        aggregate_prompt_template: str | None = None,
    ):
        self.manager_agent = manager_agent
        self.worker_agents = worker_agents or []

        self.decompose_template = decompose_prompt_template or """
Decompose this complex task into 3-5 independent subtasks that can be executed in parallel.

Task: {task}

Return ONLY a JSON array of subtasks, where each subtask is an object with:
- "description": Clear description of the subtask
- "agent": Suggested agent type (or "any" if not critical)
- "priority": "high", "medium", or "low"
"""

        self.aggregate_template = aggregate_prompt_template or """
Synthesize these subtask results into a comprehensive final output.

Original task: {task}

Subtask results:
{results}

Provide a cohesive summary that:
1. Identifies key findings from all subtasks
2. Resolves any conflicts or contradictions
3. Provides actionable recommendations
"""

    async def execute(
        self,
        task: str,
        max_workers: int = 5,
        worker_timeout: int = 120,
    ) -> Dict[str, Any]:
        """Execute hierarchical coordination."""
        timeline = []

        # Step 1: Decompose task (manager)
        logger.info("Decomposing task with manager", manager=self.manager_agent)
        timeline.append({"step": "decompose_start", "time": asyncio.get_event_loop().time()})

        try:
            decompose_prompt = self.decompose_template.format(task=task)
            decomposition_result = await call_agent_simple(
                self.manager_agent,
                decompose_prompt
            )

            # Parse subtasks from JSON
            subtasks = self._parse_json_response(decomposition_result)

            logger.info("Task decomposed", subtask_count=len(subtasks))

        except Exception as e:
            logger.error("Failed to decompose task", error=str(e))
            return {
                "success": False,
                "error": f"Decomposition failed: {str(e)}",
                "final_output": None,
                "subtask_results": [],
                "timeline": timeline,
            }

        # Step 2: Execute subtasks in parallel (workers)
        logger.info("Executing subtasks in parallel", worker_count=len(subtasks))

        async def execute_subtask(subtask: Dict[str, Any], idx: int) -> Dict[str, Any]:
            agent_name = subtask.get("agent", "general-purpose")

            if self.worker_agents and agent_name in ["any", "general-purpose"]:
                agent_name = self.worker_agents[idx % len(self.worker_agents)]

            try:
                async with asyncio.timeout(worker_timeout):
                    result = await call_agent_simple(
                        agent_name,
                        f"Complete this subtask:\n\n{subtask['description']}"
                    )

                return {
                    "subtask_idx": idx,
                    "description": subtask["description"],
                    "agent": agent_name,
                    "status": "success",
                    "result": result,
                }

            except asyncio.TimeoutError:
                return {
                    "subtask_idx": idx,
                    "description": subtask["description"],
                    "agent": agent_name,
                    "status": "timeout",
                    "result": None,
                }
            except Exception as e:
                return {
                    "subtask_idx": idx,
                    "description": subtask["description"],
                    "agent": agent_name,
                    "status": "failed",
                    "error": str(e),
                }

        # Execute with concurrency limit
        subtask_results = []
        for i in range(0, len(subtasks), max_workers):
            batch = subtasks[i:i + max_workers]
            batch_results = await asyncio.gather(*[
                execute_subtask(st, i + idx)
                for idx, st in enumerate(batch)
            ])
            subtask_results.extend(batch_results)

        # Step 3: Aggregate results (manager)
        results_text = "\n\n".join([
            f"### Subtask {r['subtask_idx'] + 1}: {r['description']}\n"
            f"Agent: {r['agent']}\n"
            f"Status: {r['status']}\n"
            f"Result:\n{r.get('result', r.get('error', 'No result'))}"
            for r in subtask_results
        ])

        try:
            aggregate_prompt = self.aggregate_template.format(
                task=task,
                results=results_text
            )
            final_output = await call_agent_simple(
                self.manager_agent,
                aggregate_prompt
            )

            return {
                "success": True,
                "final_output": final_output,
                "subtask_results": subtask_results,
                "timeline": timeline,
                "decomposition": subtasks,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Aggregation failed: {str(e)}",
                "final_output": None,
                "subtask_results": subtask_results,
                "timeline": timeline,
            }

    def _parse_json_response(self, response: str) -> List[Dict]:
        """Parse JSON from potentially markdown-wrapped response."""
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            return json.loads(response[json_start:json_end].strip())
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            return json.loads(response[json_start:json_end].strip())
        else:
            return json.loads(response)


class DependencyAwareCoordinator:
    """Hierarchical coordinator that respects task dependencies."""

    async def execute_with_dependencies(self, tasks: List[Dict[str, Any]]):
        """Execute tasks respecting dependencies, maximizing parallelism."""
        completed = {}
        pending = {task["id"]: task for task in tasks}

        while pending:
            ready = []
            for task_id, task in pending.items():
                deps = task.get("depends_on", [])
                if all(dep in completed for dep in deps):
                    ready.append(task)

            if not ready:
                raise Exception("Circular dependency detected!")

            results = await asyncio.gather(*[
                call_agent_simple(task["agent"], task["instruction"])
                for task in ready
            ])

            for task, result in zip(ready, results):
                completed[task["id"]] = result
                del pending[task["id"]]

        return completed
```

#### Context Management for Hierarchy

```python
class HierarchicalContextManager:
    """Manages context propagation in hierarchical structures."""

    def prepare_context_for_level(
        self,
        full_context: str,
        level: int,
        task_description: str
    ) -> str:
        """Provide appropriate detail based on hierarchy level.

        Level 0 (Master): High-level overview
        Level 1 (Manager): Domain-specific context
        Level 2 (Worker): Task-specific details
        """
        if level == 0:
            return self._create_overview(full_context)
        elif level == 1:
            return self._extract_relevant_context(full_context, task_description)
        else:
            return self._get_task_context(full_context, task_description)
```

#### Performance Characteristics

- **Latency**: O(log n) for balanced trees, O(n) for deep chains
- **Throughput**: High with parallel execution at each level
- **Token Usage**: Medium to High (manager needs context, workers are focused)
- **Cost**: Moderate (premium model for coordinator, cheaper for workers)
- **Scalability**: Excellent (logarithmic with tree depth)

---

### Pattern 3: Broadcast Multi-Perspective

**Complexity: Medium | Scalability: Medium | SDK Support: Direct**

**Rank in Research: Frequently combined with other patterns**

#### Core Concept

Send same task to multiple agents, aggregate diverse perspectives. Ideal for quality validation and consensus building.

#### Architecture

```
              Input Task
                  │
          ┌───────┼───────┐
          │       │       │
      ┌───▼──┐ ┌──▼──┐ ┌──▼──┐
      │Agent│ │Agent│ │Agent│
      │  1  │ │  2  │ │  3  │
      └───┬──┘ └──┬──┘ └──┬──┘
          │      │      │
          └──────┼──────┘
                 │
          ┌──────▼──────┐
          │  Aggregator │
          │   (Voting/  │
          │  Synthesis) │
          └─────────────┘
```

#### Aggregation Strategies

1. **Voting**: Simple majority for discrete choices
2. **Consensus**: Check if all agree
3. **Synthesis**: LLM-based integration of diverse perspectives

#### Advantages

✅ Multiple perspectives captured
✅ Consensus building
✅ Quality improvement through diversity
✅ Fault-tolerant (partial results still useful)

#### Trade-offs

⚠️ Higher cost (multiple agents on same task)
⚠️ Potential for disagreement
⚠️ Requires synthesis/aggregation logic

#### Best Use Cases

- Critical decisions requiring consensus
- Code review with multiple criteria (security, performance, maintainability)
- Quality assurance
- Validation and verification
- Risk assessment

#### Implementation

```python
# src/harness/orchestration/patterns/broadcast_multi_perspective.py

import asyncio
from typing import Any, List, Dict
from collections import Counter
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class BroadcastMultiPerspective:
    """Broadcast pattern for gathering multiple perspectives on same task."""

    def __init__(
        self,
        agents: List[str],
        aggregation_strategy: str = "synthesis",
        aggregator_agent: str | None = None,
    ):
        self.agents = agents
        self.aggregation_strategy = aggregation_strategy
        self.aggregator_agent = aggregator_agent

        if aggregation_strategy == "synthesis" and not aggregator_agent:
            raise ValueError("aggregator_agent required for synthesis strategy")

    async def execute(
        self,
        prompt: str,
        timeout_per_agent: int = 120,
        require_all: bool = False,
    ) -> Dict[str, Any]:
        """Execute broadcast pattern."""
        logger.info(
            "Broadcasting task to agents",
            agent_count=len(self.agents),
            strategy=self.aggregation_strategy,
        )

        async def execute_agent(agent_name: str) -> Dict[str, Any]:
            try:
                async with asyncio.timeout(timeout_per_agent):
                    result = await call_agent_simple(agent_name, prompt)
                return {
                    "agent": agent_name,
                    "status": "success",
                    "response": result,
                }
            except asyncio.TimeoutError:
                return {
                    "agent": agent_name,
                    "status": "timeout",
                    "response": None,
                }
            except Exception as e:
                return {
                    "agent": agent_name,
                    "status": "failed",
                    "response": None,
                    "error": str(e),
                }

        individual_results = await asyncio.gather(*[
            execute_agent(agent) for agent in self.agents
        ])

        successful_results = [r for r in individual_results if r["status"] == "success"]

        if require_all and len(successful_results) < len(self.agents):
            return {
                "success": False,
                "aggregated_result": None,
                "individual_results": individual_results,
                "error": "Not all agents succeeded (require_all=True)",
            }

        if not successful_results:
            return {
                "success": False,
                "aggregated_result": None,
                "individual_results": individual_results,
                "error": "All agents failed",
            }

        try:
            aggregated_result = await self._aggregate_results(
                prompt, successful_results
            )
            return {
                "success": True,
                "aggregated_result": aggregated_result,
                "individual_results": individual_results,
                "successful_count": len(successful_results),
            }
        except Exception as e:
            return {
                "success": False,
                "aggregated_result": None,
                "individual_results": individual_results,
                "error": f"Aggregation failed: {str(e)}",
            }

    async def _aggregate_results(
        self,
        original_prompt: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """Aggregate successful results based on strategy."""

        if self.aggregation_strategy == "voting":
            votes = [r["response"].split("\n")[0].strip() for r in results]
            vote_counts = Counter(votes)
            winner = vote_counts.most_common(1)[0]
            return f"Consensus: {winner[0]} ({winner[1]}/{len(results)} votes)"

        elif self.aggregation_strategy == "consensus":
            responses = [r["response"] for r in results]
            first_sentences = [r.split(".")[0] for r in responses]
            if len(set(first_sentences)) == 1:
                return f"Consensus reached:\n{responses[0]}"
            else:
                return f"No consensus. {len(results)} different perspectives."

        elif self.aggregation_strategy == "synthesis":
            synthesis_prompt = f"""
Original task: {original_prompt}

Multiple experts provided the following perspectives:

"""
            for idx, result in enumerate(results):
                synthesis_prompt += f"\n### Expert {idx + 1} ({result['agent']}):\n{result['response']}\n"

            synthesis_prompt += """

Synthesize these perspectives into a comprehensive response that:
1. Identifies areas of agreement
2. Acknowledges areas of disagreement
3. Provides balanced recommendations
"""

            return await call_agent_simple(
                self.aggregator_agent,
                synthesis_prompt
            )

        else:
            raise ValueError(f"Unknown aggregation strategy: {self.aggregation_strategy}")
```

---

### Pattern 4: Blackboard Architecture

**Complexity: Medium | Scalability: Medium**

**Rank in Research: #2 | Appeared in 7/8 research documents**

#### Core Concept

Shared workspace where multiple specialist agents observe, contribute partial solutions, and react to changes. Ideal for complex problem-solving where no single algorithm exists.

#### Architecture

```
        Control Component (Coordinator)
             ↓  ↑
        [BLACKBOARD]
        (Shared State)
     /  /    |    \  \
   A1  A2   A3   A4  A5
(Knowledge Sources / Specialists)
```

#### Key Characteristics

- **Shared Workspace**: Central repository visible to all agents
- **Opportunistic Problem Solving**: Agents contribute when they can add value
- **Incremental Solution Building**: Solution emerges from contributions
- **Control Component**: Manages agent activation and conflict resolution

#### Advantages

✅ Excellent for complex, unstructured problems
✅ Flexible - agents can be added/removed
✅ Natural for multi-modal reasoning
✅ Supports diverse specialist agents
✅ Good for hypothesis refinement

#### Trade-offs

⚠️ Can be unpredictable
⚠️ Requires sophisticated control logic
⚠️ Potential for conflicting contributions
⚠️ State management complexity

#### Best Use Cases

- Complex problem-solving (no clear algorithm)
- Research and analysis tasks
- Document collaboration
- Multi-perspective reasoning
- Incremental solution construction

#### Implementation

```python
# src/harness/orchestration/patterns/blackboard.py

import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from harness.direct_agent import call_agent_simple

class Blackboard:
    """Shared state that agents read from and write to."""

    def __init__(self, problem_id: str):
        self.problem_id = problem_id
        self.state_file = f"/workspace/temp/blackboard_{problem_id}.json"
        self.state = {
            "problem": {},
            "knowledge": {},
            "synthesis": {},
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": 0
            }
        }
        self._load_state()

    def _load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except FileNotFoundError:
            self._save_state()

    def _save_state(self):
        import os
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self.state["metadata"]["version"] += 1
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def read(self, section: str = None) -> Dict[str, Any]:
        if section:
            return self.state.get(section, {})
        return self.state

    def write(self, section: str, key: str, value: Any, author: str):
        if section not in self.state:
            self.state[section] = {}

        self.state[section][key] = {
            "content": value,
            "author": author,
            "timestamp": datetime.now().isoformat(),
            "version": self.state["metadata"]["version"] + 1
        }
        self._save_state()

    def get_updates_since(self, version: int) -> Dict[str, Any]:
        updates = {}
        for section, content in self.state.items():
            if section == "metadata":
                continue
            for key, data in content.items():
                if isinstance(data, dict) and data.get("version", 0) > version:
                    if section not in updates:
                        updates[section] = {}
                    updates[section][key] = data
        return updates


class KnowledgeSource:
    """Base class for specialist agents that contribute to blackboard."""

    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.last_seen_version = 0

    async def can_contribute(self, blackboard: Blackboard) -> bool:
        raise NotImplementedError

    async def contribute(self, blackboard: Blackboard):
        raise NotImplementedError


class BlackboardController:
    """Control component that manages agent activation."""

    def __init__(self, problem_id: str):
        self.blackboard = Blackboard(problem_id)
        self.knowledge_sources: List[KnowledgeSource] = []
        self.max_iterations = 10

    def register_knowledge_source(self, ks: KnowledgeSource):
        self.knowledge_sources.append(ks)

    async def solve(self, problem_description: str, initial_data: Dict[str, Any]):
        """Main problem-solving loop."""
        self.blackboard.write("problem", "description", problem_description, "system")
        for key, value in initial_data.items():
            self.blackboard.write("problem", key, value, "system")

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            contributions_made = False

            for ks in self.knowledge_sources:
                can_help = await ks.can_contribute(self.blackboard)
                if can_help:
                    await ks.contribute(self.blackboard)
                    contributions_made = True

            if await self._is_solution_complete():
                break

            if not contributions_made:
                break

        return await self._synthesize_solution()

    async def _is_solution_complete(self) -> bool:
        knowledge = self.blackboard.read("knowledge")
        return len(knowledge) >= 2

    async def _synthesize_solution(self) -> str:
        state = self.blackboard.read()

        synthesis_prompt = f"""
        Based on the accumulated knowledge, provide a comprehensive solution:

        PROBLEM: {state['problem'].get('description', {}).get('content', '')}

        KNOWLEDGE GATHERED:
        {json.dumps(state['knowledge'], indent=2)}

        Synthesize this into a clear, actionable response.
        """

        result = await call_agent_simple("general-purpose", synthesis_prompt)
        self.blackboard.write("synthesis", "final_solution", result, "controller")
        return result
```

---

### Pattern 5: Mediator Pattern

**Complexity: Medium | Scalability: Medium**

**Rank in Research: #3 | Appeared in 6/8 research documents**

#### Core Concept

Central mediator facilitates all agent communication, providing routing, load balancing, policy enforcement, and message transformation. Decouples agents from each other.

#### Architecture

```
      A1      A2      A3
       ↓       ↓       ↓
       ← MEDIATOR →
       ↑       ↑       ↑
      A4      A5      A6
```

#### Key Characteristics

- **Central Hub**: All communication flows through mediator
- **Smart Routing**: Content-based, capability-based, or load-based
- **Loose Coupling**: Agents don't know about each other
- **Policy Enforcement**: Security, rate limiting, auditing

#### Advantages

✅ Loose coupling between agents
✅ Centralized policy enforcement
✅ Easy to add/remove agents
✅ Comprehensive monitoring
✅ Complex routing logic supported

#### Trade-offs

⚠️ Single point of failure
⚠️ Can become bottleneck
⚠️ Mediator complexity grows with system

#### Best Use Cases

- Dynamic agent pools
- Policy enforcement required (security, compliance)
- Complex routing logic needed
- Monitoring and auditing critical
- When agents shouldn't communicate directly

#### Implementation

```python
# src/harness/orchestration/patterns/mediator.py

import asyncio
from typing import Dict, List, Any, Callable
from enum import Enum
from datetime import datetime
from harness.direct_agent import call_agent_simple

class RoutingStrategy(Enum):
    CONTENT_BASED = "content"
    CAPABILITY_BASED = "capability"
    LOAD_BASED = "load"
    ROUND_ROBIN = "round_robin"

class Message:
    def __init__(self, sender: str, content: str, metadata: Dict[str, Any] = None):
        import uuid
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

class AgentCapability:
    def __init__(self, agent_id: str, capabilities: List[str], load: int = 0):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.load = load
        self.max_load = 5

class Mediator:
    """Central coordinator that routes messages between agents."""

    def __init__(self, routing_strategy: RoutingStrategy = RoutingStrategy.CAPABILITY_BASED):
        self.routing_strategy = routing_strategy
        self.agents: Dict[str, AgentCapability] = {}
        self.policies: List[Callable] = []
        self.message_log = []
        self._register_available_agents()

    def _register_available_agents(self):
        agent_capabilities = {
            "python-expert": ["python", "code_review", "debugging"],
            "typescript-expert": ["typescript", "javascript", "code_review"],
            "go-expert": ["go", "code_review"],
            "postgres-expert": ["database", "postgresql", "sql"],
            "docker-engineer": ["docker", "containers", "infrastructure"],
            "testing-agent": ["testing", "qa", "test_generation"],
            "dev-code-review-expert": ["code_review", "quality_assurance"],
        }

        for agent_id, capabilities in agent_capabilities.items():
            self.register_agent(agent_id, capabilities)

    def register_agent(self, agent_id: str, capabilities: List[str]):
        self.agents[agent_id] = AgentCapability(agent_id, capabilities)

    def add_policy(self, policy: Callable):
        self.policies.append(policy)

    async def send_message(self, message: Message) -> str:
        # Apply policies
        for policy in self.policies:
            if not policy(message):
                raise Exception(f"Message rejected by policy: {policy.__name__}")

        # Log message
        self.message_log.append({
            "id": message.id,
            "sender": message.sender,
            "timestamp": message.timestamp,
            "content": message.content[:100]
        })

        # Route to appropriate agent
        agent_id = self._route_message(message)

        self.agents[agent_id].load += 1
        try:
            response = await call_agent_simple(agent_id, message.content)
            return response
        finally:
            self.agents[agent_id].load -= 1

    def _route_message(self, message: Message) -> str:
        if self.routing_strategy == RoutingStrategy.CONTENT_BASED:
            return self._route_by_content(message)
        elif self.routing_strategy == RoutingStrategy.CAPABILITY_BASED:
            return self._route_by_capability(message)
        elif self.routing_strategy == RoutingStrategy.LOAD_BASED:
            return min(self.agents.keys(), key=lambda a: self.agents[a].load)
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            return self._route_round_robin()
        raise Exception(f"Unknown routing strategy: {self.routing_strategy}")

    def _route_by_content(self, message: Message) -> str:
        content_lower = message.content.lower()
        if "python" in content_lower:
            return "python-expert"
        elif "typescript" in content_lower or "javascript" in content_lower:
            return "typescript-expert"
        elif "database" in content_lower or "sql" in content_lower:
            return "postgres-expert"
        elif "test" in content_lower:
            return "testing-agent"
        return "python-expert"

    def _route_by_capability(self, message: Message) -> str:
        required_caps = message.metadata.get("required_capabilities", [])
        if not required_caps:
            return self._route_by_content(message)

        candidates = []
        for agent_id, agent_cap in self.agents.items():
            if all(cap in agent_cap.capabilities for cap in required_caps):
                candidates.append(agent_id)

        if not candidates:
            raise Exception(f"No agent found with capabilities: {required_caps}")

        return min(candidates, key=lambda a: self.agents[a].load)

    def _route_round_robin(self) -> str:
        if not hasattr(self, '_rr_index'):
            self._rr_index = 0
        agent_ids = list(self.agents.keys())
        agent_id = agent_ids[self._rr_index % len(agent_ids)]
        self._rr_index += 1
        return agent_id
```

---

### Pattern 6: Peer-to-Peer Coordination

**Complexity: High | Scalability: Very High**

**Rank in Research: #4 | Appeared in 5/8 research documents**

#### Core Concept

All agents have equal status and communicate directly without a central coordinator. Self-organizing system where agents negotiate and collaborate as peers.

#### Architecture

```
    A1 ←→ A2
    ↕  ×  ↕
    A3 ←→ A4
```

#### Key Characteristics

- **No Hierarchy**: All agents are equal
- **Direct Communication**: Agents communicate peer-to-peer
- **Self-Organization**: Emergent behavior from local interactions
- **Dynamic Roles**: Agents can take on different roles as needed

#### Advantages

✅ Highly robust (no single point of failure)
✅ Scales well horizontally
✅ Flexible and adaptive
✅ Good for exploratory tasks
✅ Natural for distributed systems

#### Trade-offs

⚠️ Can be unpredictable
⚠️ Higher communication overhead
⚠️ Difficult to track global state
⚠️ Complex debugging
⚠️ Token-intensive for LLM agents

#### Best Use Cases

- Exploratory or creative tasks
- Distributed decision-making
- Brainstorming and ideation
- When no natural coordinator exists
- Highly dynamic environments

#### Implementation

```python
# src/harness/orchestration/patterns/peer_to_peer.py

import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime
from harness.direct_agent import call_agent_simple

class PeerAgent:
    """An autonomous peer agent that can communicate with other peers."""

    def __init__(self, agent_id: str, framework_agent: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.framework_agent = framework_agent
        self.capabilities = capabilities
        self.peers: List['PeerAgent'] = []
        self.messages = []
        self.state = {}

    def connect_to_peer(self, peer: 'PeerAgent'):
        if peer not in self.peers:
            self.peers.append(peer)
            peer.peers.append(self)

    async def broadcast_to_peers(self, message: str, exclude: List[str] = None):
        exclude = exclude or []
        responses = []
        for peer in self.peers:
            if peer.agent_id not in exclude:
                response = await peer.receive_message(self.agent_id, message)
                responses.append((peer.agent_id, response))
        return responses

    async def receive_message(self, sender_id: str, message: str) -> str:
        self.messages.append({
            "from": sender_id,
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        return await self._process_peer_message(sender_id, message)

    async def _process_peer_message(self, sender_id: str, message: str) -> str:
        context = self._build_context()
        prompt = f"""
        You are agent {self.agent_id} with capabilities: {self.capabilities}

        You received this message from peer {sender_id}:
        {message}

        Recent conversation:
        {context}

        Respond appropriately.
        """
        return await call_agent_simple(self.framework_agent, prompt)

    def _build_context(self) -> str:
        recent = self.messages[-5:]
        return json.dumps(recent, indent=2)

    async def initiate_task(self, task: str) -> str:
        analysis_prompt = f"""
        Task: {task}
        Your capabilities: {self.capabilities}

        Determine:
        1. Can you complete this task alone?
        2. If not, what capabilities are needed?
        """
        analysis = await call_agent_simple(self.framework_agent, analysis_prompt)

        try:
            analysis_data = json.loads(analysis)
            if analysis_data.get("can_complete_alone"):
                return await call_agent_simple(self.framework_agent, task)
            else:
                needed_caps = analysis_data.get("needed_capabilities", [])
                return await self._collaborate_on_task(task, needed_caps)
        except json.JSONDecodeError:
            return await call_agent_simple(self.framework_agent, task)

    async def _collaborate_on_task(self, task: str, needed_capabilities: List[str]) -> str:
        helpers = [
            peer for peer in self.peers
            if any(cap in peer.capabilities for cap in needed_capabilities)
        ]

        if not helpers:
            return "No peers available with needed capabilities"

        request_message = f"I need help with: {task}\nRequired capabilities: {needed_capabilities}"
        responses = []
        for helper in helpers:
            response = await helper.receive_message(self.agent_id, request_message)
            responses.append((helper.agent_id, response))

        synthesis_prompt = f"Original task: {task}\n\nResponses: {json.dumps(responses)}\n\nSynthesize."
        return await call_agent_simple(self.framework_agent, synthesis_prompt)


class PeerNetwork:
    """Manages a network of peer agents."""

    def __init__(self):
        self.agents: Dict[str, PeerAgent] = {}

    def add_agent(self, agent: PeerAgent):
        self.agents[agent.agent_id] = agent

    def connect_all_peers(self):
        agent_list = list(self.agents.values())
        for i, agent1 in enumerate(agent_list):
            for agent2 in agent_list[i+1:]:
                agent1.connect_to_peer(agent2)

    async def execute_distributed_task(self, task: str, initiator_id: str) -> str:
        initiator = self.agents[initiator_id]
        return await initiator.initiate_task(task)
```

---

### Pattern 7: Hybrid Pipeline Architecture

**Complexity: Medium-High | Scalability: High**

**Rank in Research: #5 | Most Common in Production**

#### Core Concept

Combines multiple patterns - typically hierarchical planning with specialized execution stages. Most common in production systems. Balances control with flexibility.

#### Architecture

```
Planning Phase (Hierarchical)
    ↓
[Research] → [Analysis] → [Synthesis] → [Review]
    ↓            ↓            ↓            ↓
Parallel      Parallel     Sequential   Validation
Execution    Execution    (Blackboard)  (Peer Review)
```

#### Key Characteristics

- **Multi-Phase**: Distinct stages with different patterns
- **Best-of-Breed**: Use optimal pattern for each phase
- **Flexible**: Adapt to task requirements
- **Practical**: Proven in production systems

#### Advantages

✅ Combines strengths of multiple patterns
✅ Highly adaptable
✅ Proven in production
✅ Balances control and flexibility
✅ Optimizes for real-world constraints

#### Trade-offs

⚠️ More complex to implement
⚠️ Requires careful design
⚠️ Higher initial development cost

#### Best Use Cases

- Production systems
- Complex multi-phase workflows
- When different phases have different needs
- Most real-world applications

#### Implementation

```python
# src/harness/orchestration/patterns/hybrid_pipeline.py

import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime
from harness.direct_agent import call_agent_simple

class PipelineStage:
    """Base class for pipeline stages."""

    def __init__(self, stage_name: str):
        self.stage_name = stage_name
        self.metrics = {"executions": 0, "total_time": 0, "errors": 0}

    async def execute(self, input_data: Any) -> Any:
        raise NotImplementedError


class ResearchStage(PipelineStage):
    """Stage 1: Research and information gathering (Parallel execution)."""

    def __init__(self):
        super().__init__("research")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        query = input_data.get("query", "")

        research_tasks = [
            ("research-specialist", f"Research background on: {query}"),
            ("research-specialist", f"Research best practices for: {query}"),
            ("research-specialist", f"Research common pitfalls for: {query}"),
        ]

        results = []
        for agent, task in research_tasks:
            response = await call_agent_simple(agent, task)
            results.append(response)

        return {
            "research_results": results,
            "query": query,
            "timestamp": datetime.now().isoformat()
        }


class AnalysisStage(PipelineStage):
    """Stage 2: Analyze gathered information (Blackboard-style)."""

    def __init__(self):
        super().__init__("analysis")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        research = input_data.get("research_results", [])
        query = input_data.get("query", "")

        analyses = {}

        if "code" in query.lower() or "security" in query.lower():
            analyses["security"] = await call_agent_simple(
                "python-expert",
                f"Analyze security implications: {json.dumps(research)}"
            )

        analyses["best_practices"] = await call_agent_simple(
            "python-expert",
            f"Identify best practices from research: {json.dumps(research)}"
        )

        return {
            "analyses": analyses,
            "research_summary": research,
            "query": query
        }


class SynthesisStage(PipelineStage):
    """Stage 3: Synthesize findings (Sequential processing)."""

    def __init__(self):
        super().__init__("synthesis")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        analyses = input_data.get("analyses", {})
        query = input_data.get("query", "")

        synthesis_prompt = f"""
        Based on the following analyses, create comprehensive recommendations:

        ORIGINAL QUERY: {query}

        ANALYSES:
        {json.dumps(analyses, indent=2)}

        Provide:
        1. Executive summary
        2. Key findings
        3. Actionable recommendations
        """

        synthesis = await call_agent_simple("python-expert", synthesis_prompt)

        return {
            "synthesis": synthesis,
            "input_analyses": analyses,
            "query": query
        }


class ReviewStage(PipelineStage):
    """Stage 4: Peer review for quality assurance (Broadcast validation)."""

    def __init__(self):
        super().__init__("review")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        synthesis = input_data.get("synthesis", "")
        query = input_data.get("query", "")

        review_tasks = [
            call_agent_simple(
                "dev-code-review-expert",
                f"Review for quality:\n\nQuery: {query}\n\nSynthesis: {synthesis}"
            ),
            call_agent_simple(
                "python-expert",
                f"Review technical accuracy:\n\nQuery: {query}\n\nSynthesis: {synthesis}"
            )
        ]

        reviews = await asyncio.gather(*review_tasks)

        all_approved = all("approved" in review.lower() or "good" in review.lower()
                          for review in reviews)

        return {
            "approved": all_approved,
            "reviews": reviews,
            "synthesis": synthesis,
            "query": query
        }


class HybridPipeline:
    """Main pipeline orchestrator that chains stages together."""

    def __init__(self):
        self.stages: List[PipelineStage] = []
        self.results = []

    def add_stage(self, stage: PipelineStage):
        self.stages.append(stage)

    async def execute(self, initial_input: Dict[str, Any]) -> Dict[str, Any]:
        current_data = initial_input

        for stage in self.stages:
            try:
                result = await stage.execute(current_data)
                current_data = result

                self.results.append({
                    "stage": stage.stage_name,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })

            except Exception as e:
                raise

        return current_data

    async def execute_with_checkpoints(self, initial_input: Dict[str, Any]):
        """Execute with checkpointing for fault tolerance."""
        checkpoint_dir = "/workspace/temp/pipeline_checkpoints"
        import os
        os.makedirs(checkpoint_dir, exist_ok=True)

        current_data = initial_input
        start_stage = 0

        checkpoint_file = f"{checkpoint_dir}/checkpoint.json"
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                start_stage = checkpoint["stage_index"] + 1
                current_data = checkpoint["data"]

        for i, stage in enumerate(self.stages[start_stage:], start=start_stage):
            result = await stage.execute(current_data)
            current_data = result

            with open(checkpoint_file, 'w') as f:
                json.dump({"stage_index": i, "data": current_data}, f, indent=2)

        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)

        return current_data
```

---

### Pattern 8: Event-Driven Async

**Complexity: High | Scalability: Very High | SDK Support: Redis**

#### Core Concept

Agents communicate via events on Redis streams, enabling long-running distributed workflows.

#### Architecture

```
Agent A ──┐
          ├──> Redis Stream ──> Agent B ──┐
Agent C ──┘                               ├──> Redis Stream ──> Agent D
                                          │
                           Agent E ───────┘
```

#### Key Characteristics

- **Async Communication**: Non-blocking, event-driven
- **Decoupled Agents**: No direct dependencies
- **Consumer Groups**: Reliable message processing
- **Long-Running Support**: Workflows spanning hours/days

#### Advantages

✅ Async, non-blocking
✅ Decoupled agents
✅ Highly scalable
✅ Fault-tolerant with consumer groups
✅ Supports long-running workflows

#### Trade-offs

⚠️ Requires Redis infrastructure
⚠️ Eventually consistent
⚠️ Complex setup

#### Best Use Cases

- CI/CD pipelines
- Distributed workflows
- Long-running processes
- Microservices-style architectures
- Event sourcing patterns

#### Implementation

```python
# src/harness/orchestration/patterns/event_driven_async.py

import asyncio
from typing import Any, Dict, Callable
from harness.messaging import RedisMessageBroker, CircuitBreakerOpenError
import structlog

logger = structlog.get_logger(__name__)

class EventDrivenCoordinator:
    """Event-driven async pattern using Redis Streams."""

    def __init__(
        self,
        stream_name: str = "agent:events",
        consumer_group: str = "coordinator",
    ):
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.broker: RedisMessageBroker | None = None
        self.event_handlers: Dict[str, Callable] = {}
        self.running = False

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        self.event_handlers[event_type] = handler

    async def start(self) -> None:
        self.broker = RedisMessageBroker()
        self.broker.connect()

        self.broker.create_consumer_group(
            stream_name=self.stream_name,
            group_name=self.consumer_group,
            start_id="0",
        )

        self.running = True

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        agent_id: str = "coordinator",
    ) -> str | None:
        if not self.broker:
            return None

        event = {"event_type": event_type, "data": data}

        try:
            message_id = self.broker.publish_result(
                agent_id=agent_id,
                result=event,
                stream_name=self.stream_name,
            )
            return message_id
        except Exception as e:
            logger.error("Failed to publish event", error=str(e))
            return None

    async def process_events(
        self,
        consumer_name: str = "worker-1",
        block_ms: int = 1000,
        batch_size: int = 10,
    ) -> None:
        if not self.broker:
            raise RuntimeError("Broker not connected. Call start() first.")

        while self.running:
            try:
                messages = self.broker.read_group(
                    stream_name=self.stream_name,
                    group_name=self.consumer_group,
                    consumer_name=consumer_name,
                    count=batch_size,
                    block=block_ms,
                )

                if not messages:
                    await asyncio.sleep(0.1)
                    continue

                for msg in messages:
                    await self._process_event(msg)
                    self.broker.acknowledge_message(
                        stream_name=self.stream_name,
                        group_name=self.consumer_group,
                        message_id=msg["message_id"],
                    )

            except Exception as e:
                logger.error("Error processing events", error=str(e))
                await asyncio.sleep(1)

    async def _process_event(self, message: Dict[str, Any]) -> None:
        content = message["content"]
        event_type = content.get("event_type")
        data = content.get("data", {})

        if event_type in self.event_handlers:
            handler = self.event_handlers[event_type]
            await handler(data)

    async def stop(self) -> None:
        self.running = False
        if self.broker:
            self.broker.disconnect()
            self.broker = None
```

---

## Advanced Components

### Task Decomposition Engine

Automatically analyzes tasks and selects appropriate orchestration pattern:

```python
# src/harness/orchestration/task_decomposition.py

import asyncio
import json
from typing import Any, Dict
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class TaskDecompositionEngine:
    """Automatically analyzes tasks and selects appropriate orchestration pattern."""

    def __init__(self, planner_agent: str = "general-purpose"):
        self.planner_agent = planner_agent

    async def analyze_task(self, task: str) -> Dict[str, Any]:
        """Analyze task and recommend orchestration strategy."""
        analysis_prompt = f"""
Analyze this task and recommend an orchestration strategy:

Task: {task}

Provide your analysis as JSON with the following structure:
{{
    "pattern": "sequential" | "hierarchical" | "broadcast" | "event-driven",
    "reasoning": "Why this pattern is appropriate",
    "complexity": "low" | "medium" | "high",
    "parallelizable": true | false,
    "subtasks": [
        {{
            "description": "Subtask description",
            "agent_type": "Suggested agent",
            "dependencies": []
        }}
    ],
    "agents": ["List of suggested agent types"]
}}

Pattern Selection Criteria:
- sequential: Linear workflow, each step depends on previous
- hierarchical: Complex task needing decomposition + parallel execution
- broadcast: Multiple perspectives needed
- event-driven: Long-running, distributed, or async coordination

Return ONLY the JSON.
"""
        try:
            result = await call_agent_simple(self.planner_agent, analysis_prompt)
            return self._parse_json_response(result)
        except Exception as e:
            return {
                "pattern": "sequential",
                "reasoning": f"Failed to analyze: {str(e)}, defaulting to sequential",
                "complexity": "unknown",
                "parallelizable": False,
                "subtasks": [],
                "agents": [],
            }

    def _parse_json_response(self, response: str) -> Dict:
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            return json.loads(response[json_start:json_end].strip())
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            return json.loads(response[json_start:json_end].strip())
        else:
            return json.loads(response)
```

### Dependency Graph

Build and execute DAG of dependent tasks with maximum parallelism:

```python
# src/harness/orchestration/dependency_graph.py

from typing import Any, Dict, List, Set
from harness.direct_agent import call_agent_simple
import asyncio
import structlog

logger = structlog.get_logger(__name__)

class DependencyGraph:
    """Build and execute DAG of dependent tasks."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.results: Dict[str, Any] = {}

    def add_task(
        self,
        task_id: str,
        agent_name: str,
        prompt_template: str,
        depends_on: List[str] | None = None,
    ) -> None:
        self.tasks[task_id] = {
            "agent_name": agent_name,
            "prompt_template": prompt_template,
        }
        self.dependencies[task_id] = depends_on or []

    def _get_ready_tasks(self, completed: Set[str]) -> List[str]:
        ready = []
        for task_id, deps in self.dependencies.items():
            if task_id not in completed and task_id not in self.results:
                if all(dep in completed for dep in deps):
                    ready.append(task_id)
        return ready

    async def execute(self, initial_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        completed: Set[str] = set()

        while len(completed) < len(self.tasks):
            ready_tasks = self._get_ready_tasks(completed)

            if not ready_tasks:
                if len(completed) < len(self.tasks):
                    remaining = set(self.tasks.keys()) - completed
                    return {
                        "success": False,
                        "error": "Circular dependency or unreachable tasks",
                        "results": self.results,
                        "completed": list(completed),
                    }
                break

            async def execute_task(task_id: str) -> tuple[str, Any]:
                task = self.tasks[task_id]
                agent_name = task["agent_name"]
                prompt_template = task["prompt_template"]

                prompt = prompt_template
                for dep_id in self.dependencies[task_id]:
                    if dep_id in self.results:
                        prompt = prompt.replace(
                            f"{{dep:{dep_id}}}",
                            str(self.results[dep_id])
                        )

                result = await call_agent_simple(agent_name, prompt)
                return task_id, result

            batch_results = await asyncio.gather(*[
                execute_task(tid) for tid in ready_tasks
            ], return_exceptions=True)

            for item in batch_results:
                if isinstance(item, Exception):
                    return {
                        "success": False,
                        "error": str(item),
                        "results": self.results,
                        "completed": list(completed),
                    }

                task_id, result = item
                self.results[task_id] = result
                completed.add(task_id)

        return {
            "success": True,
            "results": self.results,
            "completed": list(completed),
        }
```

---

## Production Patterns

### Cost Optimization

```python
# src/harness/orchestration/cost_optimization.py

import hashlib
import json
from typing import Dict
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class CostOptimizer:
    """Optimize orchestration costs through caching and model selection."""

    def __init__(self):
        self.cache: Dict[str, str] = {}

    def cache_key(self, agent: str, prompt: str) -> str:
        content = f"{agent}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def execute_with_cache(self, agent_name: str, prompt: str) -> str:
        key = self.cache_key(agent_name, prompt)

        if key in self.cache:
            logger.info("Cache hit", agent=agent_name)
            return self.cache[key]

        result = await call_agent_simple(agent_name, prompt)
        self.cache[key] = result
        return result

    def get_cheaper_agent(self, agent_name: str) -> str:
        """Map to cheaper equivalent agent if available."""
        if "expert" in agent_name:
            return agent_name
        return "general-purpose"
```

### Monitoring and Observability

```python
# src/harness/orchestration/monitoring.py

import time
from typing import Any, Dict, List
import structlog

logger = structlog.get_logger(__name__)

class OrchestrationMetrics:
    """Track orchestration metrics for monitoring."""

    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.active_tasks: Dict[str, float] = {}

    def start_task(self, task_id: str, pattern: str, agent: str) -> None:
        self.active_tasks[task_id] = time.time()
        logger.info("Task started", task_id=task_id, pattern=pattern, agent=agent)

    def complete_task(self, task_id: str, success: bool, result_length: int = 0) -> None:
        if task_id not in self.active_tasks:
            return

        start_time = self.active_tasks.pop(task_id)
        duration = time.time() - start_time

        self.metrics.append({
            "task_id": task_id,
            "duration": duration,
            "success": success,
            "result_length": result_length,
            "timestamp": time.time(),
        })

        logger.info("Task completed", task_id=task_id, duration=f"{duration:.2f}s", success=success)

    def get_summary(self) -> Dict[str, Any]:
        if not self.metrics:
            return {"total_tasks": 0}

        successful = [m for m in self.metrics if m["success"]]

        return {
            "total_tasks": len(self.metrics),
            "successful_tasks": len(successful),
            "failed_tasks": len(self.metrics) - len(successful),
            "avg_duration": sum(m["duration"] for m in self.metrics) / len(self.metrics),
            "total_duration": sum(m["duration"] for m in self.metrics),
        }
```

### Error Recovery

```python
# src/harness/orchestration/error_recovery.py

import asyncio
from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)

class RetryStrategy:
    """Configurable retry strategy for orchestration."""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0,
    ):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff

    async def execute_with_retry(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        last_error = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < self.max_attempts - 1:
                    backoff = min(self.backoff_base ** attempt, self.max_backoff)
                    logger.warning(
                        "Attempt failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=self.max_attempts,
                        backoff=backoff,
                        error=str(e),
                    )
                    await asyncio.sleep(backoff)

        raise last_error
```

---

## Framework-Specific Best Practices

### 1. Agent Invocation

```python
from harness.direct_agent import call_agent, call_agent_simple, list_available_agents

# Simple invocation (returns text)
result = await call_agent_simple("python-expert", "Review this code")

# Streaming invocation (for long responses)
async for message in call_agent("python-expert", "Write a detailed guide"):
    process(message)

# List available agents
agents = list_available_agents()
```

### 2. Working Directory Rules

```python
# ALWAYS use /workspace for development
output_file = "/workspace/results/analysis.json"

# NOT: output_file = "results/analysis.json"  # Would use /app
```

### 3. Research Skill Usage

```
# Heavy research tasks — invoke the coordinator skill from the main thread
Skill(skill="research-team:coordinator", args="Research authentication patterns")

# For programmatic single-subtopic research without skill invocation:
async for msg in call_agent(
    "research-team:research-specialist",
    "Research authentication patterns in FastAPI"
):
    process(msg)

# Reports saved to: ~/Documents/ClaudeResearch/reports/
```

### 4. Caching for Performance

```python
import hashlib
import json

class AgentCache:
    def __init__(self, cache_dir="/workspace/temp/cache"):
        self.cache_dir = cache_dir
        import os
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_key(self, agent: str, prompt: str) -> str:
        content = json.dumps({"agent": agent, "prompt": prompt})
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_or_execute(self, agent: str, prompt: str):
        key = self.get_cache_key(agent, prompt)
        cache_file = f"{self.cache_dir}/{key}.json"

        import os
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)["result"]

        result = await call_agent_simple(agent, prompt)

        with open(cache_file, 'w') as f:
            json.dump({"result": result}, f)

        return result
```

### 5. Token Budget Management

```python
class TokenBudget:
    def __init__(self, total_budget: int = 100000):
        self.total = total_budget
        self.used = 0
        self.agent_usage = {}

    def check_budget(self, agent: str, estimated_tokens: int):
        if self.used + estimated_tokens > self.total:
            raise Exception(f"Budget exceeded! Used: {self.used}, Limit: {self.total}")

    def record_usage(self, agent: str, tokens: int):
        self.used += tokens
        self.agent_usage[agent] = self.agent_usage.get(agent, 0) + tokens
```

---

## Common Pitfalls and How to Avoid Them

### 1. Context Explosion

**Pitfall**: Passing full context to every agent, exceeding token limits.

```python
# Bad: Pass everything
context = full_conversation_history + all_files

# Good: Pass only relevant context
context = summarize(relevant_messages) + current_file
```

### 2. Sequential Execution When Parallel is Possible

**Pitfall**: Running independent tasks sequentially.

```python
# Bad: Sequential (slow)
result1 = await agent1.execute()
result2 = await agent2.execute()

# Good: Parallel (fast)
result1, result2 = await asyncio.gather(agent1.execute(), agent2.execute())
```

### 3. No Error Handling

**Pitfall**: Agent failures crash entire system.

```python
# Bad
result = await call_agent_simple("agent", prompt)

# Good
try:
    result = await resilient_agent_call("agent", prompt, max_retries=3)
except Exception as e:
    result = fallback_handler(e)
```

### 4. Ignoring Costs

**Pitfall**: No tracking of token usage and costs.

```python
tracker = CostTracker()
result = await call_agent_simple("agent", prompt)
tracker.track("claude-sonnet", input_tokens, output_tokens)

if tracker.get_total_cost() > budget:
    send_alert()
```

### 5. Brittle JSON Parsing

**Pitfall**: Assuming agents always return perfect JSON.

```python
# Bad
result = json.loads(response)

# Good - handles code blocks, malformed JSON
result = extract_json_from_response(response)
```

---

## Migration Guide

### From Single-Agent to Multi-Agent

**Step 1: Identify Coordination Needs**
- Is task naturally sequential? → Start with Sequential Pipeline
- Is task decomposable? → Use Hierarchical Coordinator
- Need consensus? → Use Broadcast Pattern

**Step 2: Implement Incrementally**

```python
# Before: Single agent
result = await call_agent_simple("python-expert", "Analyze this codebase")

# After: Multi-agent pipeline
from harness.orchestration.patterns.sequential_pipeline import SequentialPipeline

pipeline = SequentialPipeline(stages=[
    {"agent_name": "python-expert", "prompt_template": "Code analysis: {input}"},
    {"agent_name": "security-expert", "prompt_template": "Security review: {input}"},
])

result = await pipeline.execute("/workspace/myproject")
```

**Step 3: Add Monitoring**

```python
from harness.orchestration.monitoring import OrchestrationMetrics

metrics = OrchestrationMetrics()
metrics.start_task("task_1", "pipeline", "python-expert")
# ... execute ...
metrics.complete_task("task_1", success=True)
```

**Step 4: Optimize**
- Add caching for repeated operations
- Use cheaper models for simple subtasks
- Implement retry strategies

---

## References

### Official Documentation

- **Claude API**: https://docs.anthropic.com/
- **LangChain**: https://python.langchain.com/docs/
- **LangGraph**: https://langchain-ai.github.io/langgraph/

### Research Papers

- "Multi-Agent Systems: A Survey" - Wooldridge & Jennings
- "Hierarchical Task Networks" - Erol, Hendler, Nau
- "Contract Net Protocol" - Smith
- "Blackboard Systems" - Engelmore & Morgan

### Related Patterns

- **Microservices Architecture**: Similar decoupling principles
- **Actor Model**: Message-passing concurrency
- **Map-Reduce**: Hierarchical data processing
- **Pub-Sub**: Event-driven coordination

### Implementation Roadmap

See [ORCHESTRATION_ROADMAP.md](./ORCHESTRATION_ROADMAP.md) for:
- Phased implementation plan
- Feature specifications
- Execution checklist

---

**Document Version**: 2.0
**Last Updated**: December 19, 2025
**Working Directory**: `/workspace/`
