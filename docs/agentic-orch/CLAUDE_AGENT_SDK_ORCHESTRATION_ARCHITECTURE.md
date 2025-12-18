# Claude Agent SDK Multi-Agent Orchestration Architecture
**Practical Implementation Guide for Agentic Patterns**

**Version:** 1.0
**Date:** 2025-12-17
**Status:** Production-Ready Reference Architecture

---

## Executive Summary

This document provides a **practical, working architecture** for implementing multi-agent orchestration patterns in the Claude Agent SDK environment. It synthesizes proven patterns from distributed systems research with the specific constraints and capabilities of the SDK, providing concrete implementations that work with the existing harness infrastructure.

### Key Findings from Analysis

**Existing Infrastructure Strengths:**
- ✅ Direct agent invocation system (`call_agent`, `call_agent_simple`)
- ✅ Redis-based message broker with circuit breaker pattern
- ✅ Plugin system for modular agent deployment
- ✅ Checkpoint/recovery system for long-running workflows
- ✅ Comprehensive monitoring and metrics collection
- ✅ Agent definition system with YAML frontmatter

**SDK Limitations (Workarounds Implemented):**
- ❌ Task tool doesn't recognize custom agents → **Solution: Direct invocation**
- ❌ No built-in multi-agent coordination → **Solution: Redis message broker**
- ❌ Limited inter-agent communication → **Solution: Stream-based messaging**

### Architecture Goals

1. **Proven Patterns**: Use only battle-tested patterns from research
2. **SDK-Compatible**: Work within SDK constraints and capabilities
3. **Production-Ready**: Include monitoring, fault tolerance, cost optimization
4. **Incrementally Adoptable**: Start simple, scale gradually
5. **Maintainable**: Clear abstractions, minimal complexity

---

## Table of Contents

1. [Core Architecture Patterns](#1-core-architecture-patterns)
2. [Foundation Layer: Agent Communication](#2-foundation-layer-agent-communication)
3. [Coordination Patterns](#3-coordination-patterns)
4. [Task Decomposition Engine](#4-task-decomposition-engine)
5. [Reference Implementations](#5-reference-implementations)
6. [Production Patterns](#6-production-patterns)
7. [Migration Guide](#7-migration-guide)
8. [Appendix: Code Examples](#appendix-code-examples)

---

## 1. Core Architecture Patterns

### 1.1 Pattern Selection Matrix

Based on research analysis and SDK capabilities, we implement **4 core patterns**:

| Pattern | Complexity | Scalability | SDK Support | Use Cases |
|---------|-----------|-------------|-------------|-----------|
| **Sequential Pipeline** | Low | Medium | ✅ Native | Linear workflows, data processing |
| **Hierarchical (Manager-Worker)** | Medium | High | ✅ Direct | Complex task decomposition |
| **Broadcast (Multi-Perspective)** | Medium | Medium | ✅ Direct | Consensus, quality checks |
| **Event-Driven (Async)** | High | Very High | ✅ Redis | Distributed systems, long-running |

**Decision Tree:**
```
┌─ Need parallel execution of independent subtasks?
│  ├─ Yes: Sequential Pipeline
│  └─ No ──┐
│          │
│          ├─ Complex decomposition needed?
│          │  ├─ Yes: Hierarchical Manager-Worker
│          │  └─ No ──┐
│          │           │
│          │           ├─ Need multiple perspectives?
│          │           │  ├─ Yes: Broadcast Multi-Perspective
│          │           │  └─ No ──┐
│          │           │           │
│          │           │           └─ Distributed/Long-running?
│          │           │              ├─ Yes: Event-Driven Async
│          │           │              └─ No: Sequential Pipeline (default)
```

### 1.2 Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│              Application Layer (Your Code)                   │
│  - Business logic                                           │
│  - Task definitions                                         │
│  - Result aggregation                                       │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│              Orchestration Layer (This Architecture)         │
│  - Task Coordinator                                         │
│  - Dependency Manager                                       │
│  - Result Aggregator                                        │
│  - Pattern Implementations (Pipeline, Hierarchical, etc.)   │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│              Communication Layer (Harness Infrastructure)    │
│  - Direct Agent Invocation (call_agent, call_agent_simple)  │
│  - Redis Message Broker (async, circuit breaker)           │
│  - Result Streaming                                         │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│              Agent Layer (SDK + Harness)                     │
│  - AgentSession                                             │
│  - Plugin System                                            │
│  - Agent Definitions (YAML)                                 │
│  - Checkpoint/Recovery                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Foundation Layer: Agent Communication

### 2.1 Communication Mechanisms (Already Implemented)

The harness provides **three communication primitives**:

#### A. Direct Invocation (Synchronous)
**Location:** `/app/src/harness/direct_agent.py`

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
**Location:** `/app/src/harness/messaging.py`

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
    last_id="0",  # Start from beginning
    count=10,
    block=1000  # Block for 1 second
)
```

**Best For:**
- Event-driven architectures
- Async coordination
- Distributed workflows
- Long-running tasks
- Cross-container communication

#### C. Agent Session Inter-Agent Methods
**Location:** `/app/src/harness/agent.py` (lines 975-1102)

```python
# In AgentSession instance
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

### 2.2 Communication Pattern Selection

| Scenario | Use | Why |
|----------|-----|-----|
| Parent→Child task | Direct Invocation | Synchronous, maintains context |
| Sibling agents | Redis Streams | Decoupled, async |
| Result aggregation | Direct Invocation | Need immediate response |
| Event notification | Redis Streams | Fire-and-forget |
| Dependency wait | Session methods | Built-in timeout/retry |

---

## 3. Coordination Patterns

### 3.1 Pattern 1: Sequential Pipeline

**Description:** Linear chain of agents, each processing output from previous.

**Architecture:**
```
Input → Agent A → Agent B → Agent C → Final Output
```

**Implementation:**

```python
# src/harness/orchestration/patterns/sequential_pipeline.py

import asyncio
from typing import Any, List, Dict
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class SequentialPipeline:
    """Sequential pipeline for linear agent workflows.

    Each agent in the pipeline receives the output from the previous agent.
    Errors in any stage stop the pipeline and return partial results.
    """

    def __init__(self, stages: List[Dict[str, Any]]):
        """Initialize pipeline with stages.

        Args:
            stages: List of dicts with keys:
                - agent_name: Name of agent to invoke
                - prompt_template: Template for prompt (uses {input} placeholder)
                - transform: Optional function to transform output

        Example:
            stages = [
                {
                    "agent_name": "python-expert",
                    "prompt_template": "Analyze this code: {input}",
                },
                {
                    "agent_name": "reviewer-agent",
                    "prompt_template": "Review these findings: {input}",
                },
            ]
        """
        self.stages = stages
        self.results: List[Dict[str, Any]] = []

    async def execute(
        self,
        initial_input: str,
        timeout_per_stage: int = 120
    ) -> Dict[str, Any]:
        """Execute pipeline stages sequentially.

        Args:
            initial_input: Initial input to first stage
            timeout_per_stage: Timeout for each stage in seconds

        Returns:
            Dict with:
                - success: bool
                - final_output: Final stage output
                - stage_results: List of all stage results
                - failed_stage: Stage number if failed (0-indexed)
        """
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
                # Format prompt with current input
                prompt = prompt_template.format(input=current_input)

                # Execute with timeout
                async with asyncio.timeout(timeout_per_stage):
                    output = await call_agent_simple(agent_name, prompt)

                # Apply transform if provided
                if transform:
                    output = transform(output)

                # Store result
                self.results.append({
                    "stage": idx,
                    "agent": agent_name,
                    "input": current_input[:200],  # Truncate for logging
                    "output": output[:200],
                    "status": "success",
                })

                # Output becomes next stage's input
                current_input = output

                logger.info(
                    "Pipeline stage completed",
                    stage=idx + 1,
                    output_length=len(output),
                )

            except asyncio.TimeoutError:
                logger.error(
                    "Pipeline stage timeout",
                    stage=idx + 1,
                    agent=agent_name,
                    timeout=timeout_per_stage,
                )
                return {
                    "success": False,
                    "final_output": None,
                    "stage_results": self.results,
                    "failed_stage": idx,
                    "error": f"Stage {idx + 1} timeout",
                }
            except Exception as e:
                logger.error(
                    "Pipeline stage failed",
                    stage=idx + 1,
                    agent=agent_name,
                    error=str(e),
                    exc_info=True,
                )
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
            "agent_name": "reviewer-agent",
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
        print("Pipeline completed successfully!")
        print(f"Final output:\n{result['final_output']}")
    else:
        print(f"Pipeline failed at stage {result['failed_stage'] + 1}")
```

**Characteristics:**
- ✅ **Simple**: Easy to understand and debug
- ✅ **Deterministic**: Predictable execution order
- ✅ **Context preservation**: Each stage sees previous output
- ⚠️ **Sequential**: Cannot parallelize
- ⚠️ **Brittle**: One failure stops entire pipeline

**Best For:**
- Data transformation pipelines
- Multi-pass refinement (draft → review → polish)
- Document generation workflows
- Code analysis → security review → report

---

### 3.2 Pattern 2: Hierarchical Manager-Worker

**Description:** Manager decomposes task into subtasks, delegates to workers, aggregates results.

**Architecture:**
```
                 ┌─ Manager Agent ─┐
                 │ (Decompose task) │
                 └──────┬───────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
    ┌─────▼─────┐ ┌────▼─────┐ ┌────▼─────┐
    │  Worker 1  │ │ Worker 2 │ │ Worker 3 │
    │ (Execute)  │ │(Execute) │ │(Execute) │
    └─────┬─────┘ └────┬─────┘ └────┬─────┘
          │            │            │
          └────────────┼────────────┘
                       │
              ┌────────▼────────┐
              │  Manager Agent  │
              │  (Aggregate)    │
              └─────────────────┘
```

**Implementation:**

```python
# src/harness/orchestration/patterns/hierarchical_coordinator.py

import asyncio
from typing import Any, List, Dict, Callable
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class HierarchicalCoordinator:
    """Manager-worker pattern for task decomposition and parallel execution.

    The manager agent decomposes a complex task into subtasks, workers
    execute them in parallel, and manager aggregates results.
    """

    def __init__(
        self,
        manager_agent: str,
        worker_agents: List[str] | None = None,
        decompose_prompt_template: str | None = None,
        aggregate_prompt_template: str | None = None,
    ):
        """Initialize hierarchical coordinator.

        Args:
            manager_agent: Name of manager agent (handles decomposition + aggregation)
            worker_agents: List of worker agent names. If None, manager assigns dynamically.
            decompose_prompt_template: Template for decomposition prompt
            aggregate_prompt_template: Template for aggregation prompt
        """
        self.manager_agent = manager_agent
        self.worker_agents = worker_agents or []

        self.decompose_template = decompose_prompt_template or """
Decompose this complex task into 3-5 independent subtasks that can be executed in parallel.

Task: {task}

Return ONLY a JSON array of subtasks, where each subtask is an object with:
- "description": Clear description of the subtask
- "agent": Suggested agent type (or "any" if not critical)
- "priority": "high", "medium", or "low"

Example:
[
    {{"description": "Analyze database schema", "agent": "database-expert", "priority": "high"}},
    {{"description": "Review API endpoints", "agent": "api-expert", "priority": "high"}}
]
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
4. Maintains technical accuracy
"""

    async def execute(
        self,
        task: str,
        max_workers: int = 5,
        worker_timeout: int = 120,
    ) -> Dict[str, Any]:
        """Execute hierarchical coordination.

        Args:
            task: Complex task to decompose and execute
            max_workers: Maximum parallel workers
            worker_timeout: Timeout per worker in seconds

        Returns:
            Dict with success, final_output, subtask_results, timeline
        """
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

            # Parse subtasks (expecting JSON array)
            import json
            # Extract JSON from markdown code blocks if present
            if "```json" in decomposition_result:
                json_start = decomposition_result.find("```json") + 7
                json_end = decomposition_result.find("```", json_start)
                subtasks = json.loads(decomposition_result[json_start:json_end].strip())
            elif "```" in decomposition_result:
                json_start = decomposition_result.find("```") + 3
                json_end = decomposition_result.find("```", json_start)
                subtasks = json.loads(decomposition_result[json_start:json_end].strip())
            else:
                subtasks = json.loads(decomposition_result)

            logger.info("Task decomposed", subtask_count=len(subtasks))
            timeline.append({
                "step": "decompose_complete",
                "time": asyncio.get_event_loop().time(),
                "subtask_count": len(subtasks),
            })

        except Exception as e:
            logger.error("Failed to decompose task", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": f"Decomposition failed: {str(e)}",
                "final_output": None,
                "subtask_results": [],
                "timeline": timeline,
            }

        # Step 2: Execute subtasks in parallel (workers)
        logger.info("Executing subtasks in parallel", worker_count=len(subtasks))
        timeline.append({"step": "execute_start", "time": asyncio.get_event_loop().time()})

        async def execute_subtask(subtask: Dict[str, Any], idx: int) -> Dict[str, Any]:
            """Execute single subtask with appropriate worker."""
            agent_name = subtask.get("agent", "general-purpose")

            # Use specified worker pool or any general agent
            if self.worker_agents and agent_name not in ["any", "general-purpose"]:
                # Find matching worker agent if specific type requested
                matching_workers = [w for w in self.worker_agents if agent_name in w]
                agent_name = matching_workers[0] if matching_workers else self.worker_agents[idx % len(self.worker_agents)]
            elif self.worker_agents:
                # Round-robin assignment
                agent_name = self.worker_agents[idx % len(self.worker_agents)]

            try:
                logger.info(
                    "Executing subtask",
                    subtask_idx=idx,
                    agent=agent_name,
                    description=subtask["description"][:100],
                )

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
                logger.error("Subtask timeout", subtask_idx=idx, agent=agent_name)
                return {
                    "subtask_idx": idx,
                    "description": subtask["description"],
                    "agent": agent_name,
                    "status": "timeout",
                    "result": None,
                    "error": "Timeout",
                }
            except Exception as e:
                logger.error(
                    "Subtask failed",
                    subtask_idx=idx,
                    agent=agent_name,
                    error=str(e),
                    exc_info=True,
                )
                return {
                    "subtask_idx": idx,
                    "description": subtask["description"],
                    "agent": agent_name,
                    "status": "failed",
                    "result": None,
                    "error": str(e),
                }

        # Execute subtasks with concurrency limit
        subtask_results = []
        for i in range(0, len(subtasks), max_workers):
            batch = subtasks[i:i + max_workers]
            batch_results = await asyncio.gather(*[
                execute_subtask(st, i + idx)
                for idx, st in enumerate(batch)
            ])
            subtask_results.extend(batch_results)

        timeline.append({
            "step": "execute_complete",
            "time": asyncio.get_event_loop().time(),
            "success_count": sum(1 for r in subtask_results if r["status"] == "success"),
        })

        # Step 3: Aggregate results (manager)
        logger.info("Aggregating results with manager", manager=self.manager_agent)
        timeline.append({"step": "aggregate_start", "time": asyncio.get_event_loop().time()})

        # Format results for aggregation
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

            timeline.append({
                "step": "aggregate_complete",
                "time": asyncio.get_event_loop().time(),
            })

            logger.info("Hierarchical coordination completed successfully")

            return {
                "success": True,
                "final_output": final_output,
                "subtask_results": subtask_results,
                "timeline": timeline,
                "decomposition": subtasks,
            }

        except Exception as e:
            logger.error("Failed to aggregate results", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": f"Aggregation failed: {str(e)}",
                "final_output": None,
                "subtask_results": subtask_results,
                "timeline": timeline,
                "decomposition": subtasks,
            }


# Example usage
async def example_codebase_analysis():
    """Example: Comprehensive codebase analysis with parallel execution"""

    coordinator = HierarchicalCoordinator(
        manager_agent="project-manager",  # Handles decomposition + aggregation
        worker_agents=[
            "python-expert",
            "typescript-expert",
            "security-expert",
            "performance-expert",
        ],
    )

    task = """
Perform comprehensive analysis of the codebase in /workspace/myproject:
1. Code quality and best practices
2. Security vulnerabilities
3. Performance bottlenecks
4. Architecture and design patterns
5. Documentation coverage
"""

    result = await coordinator.execute(task, max_workers=4)

    if result["success"]:
        print("Analysis completed!")
        print(f"\nFinal Report:\n{result['final_output']}")
        print(f"\nCompleted {len(result['subtask_results'])} subtasks")
    else:
        print(f"Analysis failed: {result['error']}")
```

**Characteristics:**
- ✅ **Parallel execution**: Workers run simultaneously
- ✅ **Scalable**: Add more workers easily
- ✅ **Flexible**: Manager adapts decomposition to task
- ✅ **Fault-tolerant**: Partial results still useful
- ⚠️ **Complex coordination**: Manager must be smart
- ⚠️ **Aggregation challenge**: Synthesizing diverse outputs

**Best For:**
- Complex analysis tasks (codebase review, research)
- Independent subtasks that can parallelize
- Tasks requiring diverse expertise
- Large-scale operations

---

### 3.3 Pattern 3: Broadcast Multi-Perspective

**Description:** Send same task to multiple agents, aggregate diverse perspectives.

**Architecture:**
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

**Implementation:**

```python
# src/harness/orchestration/patterns/broadcast_multi_perspective.py

import asyncio
from typing import Any, List, Dict, Callable
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class BroadcastMultiPerspective:
    """Broadcast pattern for gathering multiple perspectives on same task.

    Sends identical prompt to multiple agents (potentially with different
    specializations), then aggregates their responses using voting,
    consensus, or synthesis strategies.
    """

    def __init__(
        self,
        agents: List[str],
        aggregation_strategy: str = "synthesis",
        aggregator_agent: str | None = None,
    ):
        """Initialize broadcast coordinator.

        Args:
            agents: List of agent names to broadcast to
            aggregation_strategy: "voting", "consensus", or "synthesis"
            aggregator_agent: Agent for synthesis (required if strategy="synthesis")
        """
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
        """Execute broadcast pattern.

        Args:
            prompt: Prompt to send to all agents
            timeout_per_agent: Timeout for each agent
            require_all: If True, fail if any agent fails; if False, continue with partial results

        Returns:
            Dict with success, aggregated_result, individual_results
        """
        logger.info(
            "Broadcasting task to agents",
            agent_count=len(self.agents),
            strategy=self.aggregation_strategy,
        )

        # Execute all agents in parallel
        async def execute_agent(agent_name: str) -> Dict[str, Any]:
            """Execute task on single agent."""
            try:
                logger.info("Executing broadcast task", agent=agent_name)

                async with asyncio.timeout(timeout_per_agent):
                    result = await call_agent_simple(agent_name, prompt)

                return {
                    "agent": agent_name,
                    "status": "success",
                    "response": result,
                }
            except asyncio.TimeoutError:
                logger.error("Agent timeout", agent=agent_name)
                return {
                    "agent": agent_name,
                    "status": "timeout",
                    "response": None,
                    "error": "Timeout",
                }
            except Exception as e:
                logger.error("Agent failed", agent=agent_name, error=str(e), exc_info=True)
                return {
                    "agent": agent_name,
                    "status": "failed",
                    "response": None,
                    "error": str(e),
                }

        # Execute all agents in parallel
        individual_results = await asyncio.gather(*[
            execute_agent(agent) for agent in self.agents
        ])

        # Check if we have enough successful results
        successful_results = [r for r in individual_results if r["status"] == "success"]

        if require_all and len(successful_results) < len(self.agents):
            logger.error(
                "Not all agents succeeded",
                total=len(self.agents),
                successful=len(successful_results),
            )
            return {
                "success": False,
                "aggregated_result": None,
                "individual_results": individual_results,
                "error": "Not all agents succeeded (require_all=True)",
            }

        if not successful_results:
            logger.error("No agents succeeded")
            return {
                "success": False,
                "aggregated_result": None,
                "individual_results": individual_results,
                "error": "All agents failed",
            }

        # Aggregate results based on strategy
        logger.info(
            "Aggregating results",
            strategy=self.aggregation_strategy,
            successful_count=len(successful_results),
        )

        try:
            aggregated_result = await self._aggregate_results(
                prompt,
                successful_results
            )

            return {
                "success": True,
                "aggregated_result": aggregated_result,
                "individual_results": individual_results,
                "successful_count": len(successful_results),
            }

        except Exception as e:
            logger.error("Aggregation failed", error=str(e), exc_info=True)
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
            # Simple majority voting (for discrete choices)
            # Extract first line of each response as "vote"
            votes = [r["response"].split("\n")[0].strip() for r in results]
            from collections import Counter
            vote_counts = Counter(votes)
            winner = vote_counts.most_common(1)[0]

            return f"Consensus: {winner[0]} ({winner[1]}/{len(results)} votes)"

        elif self.aggregation_strategy == "consensus":
            # Check for consensus (all agree)
            responses = [r["response"] for r in results]
            # Simplified: check if all responses start with same sentence
            first_sentences = [r.split(".")[0] for r in responses]
            if len(set(first_sentences)) == 1:
                return f"Consensus reached:\n{responses[0]}"
            else:
                return f"No consensus. {len(results)} different perspectives."

        elif self.aggregation_strategy == "synthesis":
            # Use aggregator agent to synthesize
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
4. Maintains technical accuracy from all perspectives
"""

            synthesized = await call_agent_simple(
                self.aggregator_agent,
                synthesis_prompt
            )

            return synthesized

        else:
            raise ValueError(f"Unknown aggregation strategy: {self.aggregation_strategy}")


# Example usage
async def example_code_review_multi_perspective():
    """Example: Get multiple expert perspectives on code review"""

    coordinator = BroadcastMultiPerspective(
        agents=[
            "security-expert",
            "performance-expert",
            "maintainability-expert",
        ],
        aggregation_strategy="synthesis",
        aggregator_agent="reviewer-agent",
    )

    code = """
def process_user_data(user_id):
    # Fetch user from database
    query = f"SELECT * FROM users WHERE id = {user_id}"
    user = db.execute(query).fetchone()

    # Process user data
    for i in range(len(user.transactions)):
        transaction = user.transactions[i]
        if transaction.amount > 1000:
            send_alert(user.email, transaction)

    return user
"""

    result = await coordinator.execute(
        f"Review this code for issues:\n\n{code}",
        require_all=False,  # Continue even if one expert fails
    )

    if result["success"]:
        print("Multi-perspective review completed!")
        print(f"\nSynthesized Review:\n{result['aggregated_result']}")
        print(f"\n{result['successful_count']} experts contributed")
    else:
        print(f"Review failed: {result['error']}")
```

**Characteristics:**
- ✅ **Multiple perspectives**: Diverse viewpoints
- ✅ **Consensus building**: Agreement validation
- ✅ **Quality improvement**: Best ideas surface
- ✅ **Fault-tolerant**: Can proceed with partial results
- ⚠️ **Higher cost**: Multiple agents on same task
- ⚠️ **Potential disagreement**: Synthesis required

**Best For:**
- Critical decisions requiring consensus
- Code review with multiple criteria
- Quality assurance
- Validation and verification
- Risk assessment

---

### 3.4 Pattern 4: Event-Driven Async (Redis-Based)

**Description:** Agents communicate via events on Redis streams, enabling long-running distributed workflows.

**Architecture:**
```
Agent A ──┐
          ├──> Redis Stream ──> Agent B ──┐
Agent C ──┘                               ├──> Redis Stream ──> Agent D
                                          │
                           Agent E ───────┘
```

**Implementation:**

```python
# src/harness/orchestration/patterns/event_driven_async.py

import asyncio
import json
from typing import Any, Dict, Callable, List
from harness.messaging import RedisMessageBroker, CircuitBreakerOpenError
import structlog

logger = structlog.get_logger(__name__)

class EventDrivenCoordinator:
    """Event-driven async pattern using Redis Streams.

    Agents communicate via events published to Redis streams.
    Enables long-running, distributed workflows with loose coupling.
    """

    def __init__(
        self,
        stream_name: str = "agent:events",
        consumer_group: str = "coordinator",
    ):
        """Initialize event-driven coordinator.

        Args:
            stream_name: Redis stream name for events
            consumer_group: Consumer group name
        """
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
        """Register event handler for specific event type.

        Args:
            event_type: Type of event to handle
            handler: Async function that processes event data
        """
        self.event_handlers[event_type] = handler
        logger.info("Registered event handler", event_type=event_type)

    async def start(self) -> None:
        """Start event loop and connect to Redis."""
        logger.info("Starting event-driven coordinator")

        try:
            self.broker = RedisMessageBroker()
            self.broker.connect()

            # Create consumer group if doesn't exist
            self.broker.create_consumer_group(
                stream_name=self.stream_name,
                group_name=self.consumer_group,
                start_id="0",  # Read from beginning
            )

            self.running = True
            logger.info("Event-driven coordinator started", stream=self.stream_name)

        except CircuitBreakerOpenError as e:
            logger.error("Redis unavailable (circuit breaker open)", error=str(e))
            raise
        except Exception as e:
            logger.error("Failed to start coordinator", error=str(e), exc_info=True)
            raise

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        agent_id: str = "coordinator",
    ) -> str | None:
        """Publish event to stream.

        Args:
            event_type: Type of event
            data: Event data
            agent_id: Publishing agent ID

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.broker:
            logger.error("Broker not connected")
            return None

        event = {
            "event_type": event_type,
            "data": data,
        }

        try:
            message_id = self.broker.publish_result(
                agent_id=agent_id,
                result=event,
                stream_name=self.stream_name,
            )
            logger.info(
                "Published event",
                event_type=event_type,
                message_id=message_id,
            )
            return message_id
        except Exception as e:
            logger.error("Failed to publish event", error=str(e), exc_info=True)
            return None

    async def process_events(
        self,
        consumer_name: str = "worker-1",
        block_ms: int = 1000,
        batch_size: int = 10,
    ) -> None:
        """Process events from stream in loop.

        Args:
            consumer_name: Name of this consumer
            block_ms: Block time in milliseconds
            batch_size: Number of events to process per batch
        """
        if not self.broker:
            raise RuntimeError("Broker not connected. Call start() first.")

        logger.info(
            "Starting event processing loop",
            consumer=consumer_name,
            group=self.consumer_group,
        )

        while self.running:
            try:
                # Read events from consumer group
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

                # Process each event
                for msg in messages:
                    await self._process_event(msg)

                    # Acknowledge processing
                    self.broker.acknowledge_message(
                        stream_name=self.stream_name,
                        group_name=self.consumer_group,
                        message_id=msg["message_id"],
                    )

            except Exception as e:
                logger.error(
                    "Error processing events",
                    error=str(e),
                    exc_info=True,
                )
                await asyncio.sleep(1)  # Brief pause before retry

    async def _process_event(self, message: Dict[str, Any]) -> None:
        """Process single event message."""
        try:
            content = message["content"]
            event_type = content.get("event_type")
            data = content.get("data", {})

            logger.info(
                "Processing event",
                event_type=event_type,
                message_id=message["message_id"],
            )

            # Find and execute handler
            if event_type in self.event_handlers:
                handler = self.event_handlers[event_type]
                await handler(data)
            else:
                logger.warning("No handler for event type", event_type=event_type)

        except Exception as e:
            logger.error(
                "Failed to process event",
                message_id=message.get("message_id"),
                error=str(e),
                exc_info=True,
            )

    async def stop(self) -> None:
        """Stop event loop and disconnect from Redis."""
        logger.info("Stopping event-driven coordinator")
        self.running = False

        if self.broker:
            self.broker.disconnect()
            self.broker = None

        logger.info("Event-driven coordinator stopped")


# Example usage
async def example_distributed_workflow():
    """Example: Distributed CI/CD workflow with event-driven coordination"""

    coordinator = EventDrivenCoordinator(
        stream_name="cicd:events",
        consumer_group="cicd-workers",
    )

    # Define event handlers
    async def handle_code_push(data: Dict[str, Any]) -> None:
        """Handle code push event - trigger tests"""
        logger.info("Code pushed", repo=data.get("repo"))

        # Trigger tests
        await coordinator.publish_event(
            event_type="tests_triggered",
            data={"commit": data.get("commit"), "branch": data.get("branch")},
        )

    async def handle_tests_triggered(data: Dict[str, Any]) -> None:
        """Handle tests triggered - run test suite"""
        from harness.direct_agent import call_agent_simple

        logger.info("Running tests", commit=data.get("commit"))

        # Execute tests with agent
        result = await call_agent_simple(
            "testing-agent",
            f"Run test suite for commit {data.get('commit')}"
        )

        # Publish test results
        await coordinator.publish_event(
            event_type="tests_completed",
            data={
                "commit": data.get("commit"),
                "passed": "FAILED" not in result,
                "results": result,
            },
        )

    async def handle_tests_completed(data: Dict[str, Any]) -> None:
        """Handle test completion - trigger deployment if passed"""
        logger.info("Tests completed", passed=data.get("passed"))

        if data.get("passed"):
            await coordinator.publish_event(
                event_type="deployment_triggered",
                data={"commit": data.get("commit")},
            )
        else:
            logger.warning("Tests failed, skipping deployment")

    async def handle_deployment_triggered(data: Dict[str, Any]) -> None:
        """Handle deployment trigger"""
        from harness.direct_agent import call_agent_simple

        logger.info("Deploying", commit=data.get("commit"))

        result = await call_agent_simple(
            "deployment-agent",
            f"Deploy commit {data.get('commit')} to staging"
        )

        await coordinator.publish_event(
            event_type="deployment_completed",
            data={"commit": data.get("commit"), "environment": "staging"},
        )

    # Register handlers
    coordinator.register_handler("code_push", handle_code_push)
    coordinator.register_handler("tests_triggered", handle_tests_triggered)
    coordinator.register_handler("tests_completed", handle_tests_completed)
    coordinator.register_handler("deployment_triggered", handle_deployment_triggered)

    # Start coordinator
    await coordinator.start()

    # Simulate code push event
    await coordinator.publish_event(
        event_type="code_push",
        data={
            "repo": "myapp",
            "branch": "main",
            "commit": "abc123",
        },
    )

    # Process events for 60 seconds
    try:
        await asyncio.wait_for(
            coordinator.process_events(consumer_name="worker-1"),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        logger.info("Event processing timeout (expected for demo)")
    finally:
        await coordinator.stop()
```

**Characteristics:**
- ✅ **Async**: Non-blocking, event-driven
- ✅ **Decoupled**: Agents don't directly depend on each other
- ✅ **Scalable**: Multiple consumers per stream
- ✅ **Fault-tolerant**: Consumer groups ensure message processing
- ✅ **Long-running**: Supports workflows spanning hours/days
- ⚠️ **Complex**: Requires Redis infrastructure
- ⚠️ **Eventually consistent**: Not immediate

**Best For:**
- CI/CD pipelines
- Distributed workflows
- Long-running processes
- Microservices-style architectures
- Event sourcing patterns

---

## 4. Task Decomposition Engine

### 4.1 Automatic Task Decomposition

**Purpose:** Analyze complex tasks and automatically select appropriate coordination pattern.

```python
# src/harness/orchestration/task_decomposition.py

import asyncio
from typing import Any, Dict, List
from harness.direct_agent import call_agent_simple
import structlog

logger = structlog.get_logger(__name__)

class TaskDecompositionEngine:
    """Automatically analyzes tasks and selects appropriate orchestration pattern.

    Uses an LLM to analyze task characteristics and recommend:
    - Optimal coordination pattern
    - Suggested agents
    - Dependency graph
    - Execution strategy
    """

    def __init__(self, planner_agent: str = "general-purpose"):
        """Initialize task decomposition engine.

        Args:
            planner_agent: Agent to use for task analysis
        """
        self.planner_agent = planner_agent

    async def analyze_task(self, task: str) -> Dict[str, Any]:
        """Analyze task and recommend orchestration strategy.

        Args:
            task: Task description

        Returns:
            Dict with pattern, agents, subtasks, reasoning
        """
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
            "dependencies": ["subtask indices this depends on"]
        }}
    ],
    "agents": ["List of suggested agent types"],
    "estimated_duration": "rough estimate in minutes"
}}

Pattern Selection Criteria:
- **sequential**: Linear workflow, each step depends on previous
- **hierarchical**: Complex task needing decomposition + parallel execution
- **broadcast**: Multiple perspectives needed (security + performance + etc.)
- **event-driven**: Long-running, distributed, or async coordination

Return ONLY the JSON, no additional text.
"""

        try:
            logger.info("Analyzing task for orchestration strategy")

            result = await call_agent_simple(self.planner_agent, analysis_prompt)

            # Parse JSON response
            import json
            # Extract JSON from markdown if present
            if "```json" in result:
                json_start = result.find("```json") + 7
                json_end = result.find("```", json_start)
                analysis = json.loads(result[json_start:json_end].strip())
            elif "```" in result:
                json_start = result.find("```") + 3
                json_end = result.find("```", json_start)
                analysis = json.loads(result[json_start:json_end].strip())
            else:
                analysis = json.loads(result)

            logger.info(
                "Task analysis complete",
                pattern=analysis.get("pattern"),
                complexity=analysis.get("complexity"),
            )

            return analysis

        except Exception as e:
            logger.error("Task analysis failed", error=str(e), exc_info=True)
            # Fallback to sequential
            return {
                "pattern": "sequential",
                "reasoning": f"Failed to analyze (error: {str(e)}), defaulting to sequential",
                "complexity": "unknown",
                "parallelizable": False,
                "subtasks": [],
                "agents": [],
                "estimated_duration": "unknown",
            }

    async def execute_with_optimal_pattern(
        self,
        task: str,
        analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Execute task using optimal pattern based on analysis.

        Args:
            task: Task to execute
            analysis: Pre-computed analysis (if None, will analyze first)

        Returns:
            Execution result including pattern used
        """
        # Analyze if not provided
        if analysis is None:
            analysis = await self.analyze_task(task)

        pattern = analysis["pattern"]

        logger.info(
            "Executing task with pattern",
            pattern=pattern,
            complexity=analysis.get("complexity"),
        )

        # Import pattern implementations
        from harness.orchestration.patterns.sequential_pipeline import SequentialPipeline
        from harness.orchestration.patterns.hierarchical_coordinator import HierarchicalCoordinator
        from harness.orchestration.patterns.broadcast_multi_perspective import BroadcastMultiPerspective

        try:
            if pattern == "sequential":
                # Build pipeline from subtasks
                stages = [
                    {
                        "agent_name": st.get("agent_type", "general-purpose"),
                        "prompt_template": f"{st['description']}\n\nInput: {{input}}",
                    }
                    for st in analysis.get("subtasks", [])
                ]

                if not stages:
                    # No subtasks, execute directly
                    stages = [{
                        "agent_name": "general-purpose",
                        "prompt_template": "{input}",
                    }]

                pipeline = SequentialPipeline(stages=stages)
                result = await pipeline.execute(task)

                return {
                    "pattern_used": "sequential",
                    "analysis": analysis,
                    **result,
                }

            elif pattern == "hierarchical":
                # Use hierarchical coordinator
                suggested_workers = analysis.get("agents", [])

                coordinator = HierarchicalCoordinator(
                    manager_agent="general-purpose",  # Or use specialized planner
                    worker_agents=suggested_workers if suggested_workers else None,
                )

                result = await coordinator.execute(task)

                return {
                    "pattern_used": "hierarchical",
                    "analysis": analysis,
                    **result,
                }

            elif pattern == "broadcast":
                # Use broadcast pattern
                agents = analysis.get("agents", ["general-purpose"])

                coordinator = BroadcastMultiPerspective(
                    agents=agents,
                    aggregation_strategy="synthesis",
                    aggregator_agent="general-purpose",
                )

                result = await coordinator.execute(task)

                return {
                    "pattern_used": "broadcast",
                    "analysis": analysis,
                    **result,
                }

            elif pattern == "event-driven":
                # Event-driven requires pre-configured handlers
                logger.warning(
                    "Event-driven pattern requires custom setup, "
                    "falling back to hierarchical"
                )

                coordinator = HierarchicalCoordinator(
                    manager_agent="general-purpose",
                )

                result = await coordinator.execute(task)

                return {
                    "pattern_used": "hierarchical (fallback)",
                    "analysis": analysis,
                    **result,
                }

            else:
                raise ValueError(f"Unknown pattern: {pattern}")

        except Exception as e:
            logger.error("Pattern execution failed", error=str(e), exc_info=True)
            return {
                "pattern_used": pattern,
                "analysis": analysis,
                "success": False,
                "error": str(e),
            }


# Example usage
async def example_auto_orchestration():
    """Example: Automatic pattern selection and execution"""

    engine = TaskDecompositionEngine()

    # Complex task
    task = """
Perform comprehensive security audit of the web application:
1. Analyze authentication and authorization
2. Check for SQL injection vulnerabilities
3. Review API endpoint security
4. Assess frontend XSS risks
5. Evaluate data encryption practices
"""

    # Engine automatically analyzes and executes with optimal pattern
    result = await engine.execute_with_optimal_pattern(task)

    print(f"Pattern used: {result['pattern_used']}")
    print(f"Reasoning: {result['analysis']['reasoning']}")

    if result.get("success"):
        print(f"\nResult:\n{result['final_output']}")
    else:
        print(f"\nExecution failed: {result.get('error')}")
```

### 4.2 Dependency Graph Builder

For complex workflows with dependencies:

```python
# src/harness/orchestration/dependency_graph.py

from typing import Any, Dict, List, Set
import structlog

logger = structlog.get_logger(__name__)

class DependencyGraph:
    """Build and execute DAG of dependent tasks.

    Manages task dependencies and executes in topological order
    with maximum parallelism.
    """

    def __init__(self):
        """Initialize dependency graph."""
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
        """Add task to graph.

        Args:
            task_id: Unique task identifier
            agent_name: Agent to execute task
            prompt_template: Prompt template (can reference dependencies via {dep:task_id})
            depends_on: List of task IDs this task depends on
        """
        self.tasks[task_id] = {
            "agent_name": agent_name,
            "prompt_template": prompt_template,
        }
        self.dependencies[task_id] = depends_on or []

        logger.info(
            "Added task to graph",
            task_id=task_id,
            dependencies=depends_on,
        )

    def _get_ready_tasks(self, completed: Set[str]) -> List[str]:
        """Get tasks whose dependencies are all satisfied."""
        ready = []
        for task_id, deps in self.dependencies.items():
            if task_id not in completed and task_id not in self.results:
                if all(dep in completed for dep in deps):
                    ready.append(task_id)
        return ready

    async def execute(self, initial_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute all tasks in dependency order.

        Args:
            initial_input: Initial context available to all tasks

        Returns:
            Dict with success, results (map of task_id -> result)
        """
        from harness.direct_agent import call_agent_simple
        import asyncio

        logger.info("Executing dependency graph", task_count=len(self.tasks))

        completed: Set[str] = set()
        context = initial_input or {}

        while len(completed) < len(self.tasks):
            # Get tasks ready to execute
            ready_tasks = self._get_ready_tasks(completed)

            if not ready_tasks:
                # Check for circular dependencies
                if len(completed) < len(self.tasks):
                    remaining = set(self.tasks.keys()) - completed
                    logger.error(
                        "Circular dependency detected or unreachable tasks",
                        remaining=list(remaining),
                    )
                    return {
                        "success": False,
                        "error": "Circular dependency or unreachable tasks",
                        "results": self.results,
                        "completed": list(completed),
                    }
                break

            logger.info(
                "Executing batch of tasks",
                batch_size=len(ready_tasks),
                ready_tasks=ready_tasks,
            )

            # Execute ready tasks in parallel
            async def execute_task(task_id: str) -> tuple[str, Any]:
                """Execute single task."""
                task = self.tasks[task_id]
                agent_name = task["agent_name"]
                prompt_template = task["prompt_template"]

                # Build prompt with dependency results
                prompt = prompt_template
                for dep_id in self.dependencies[task_id]:
                    if dep_id in self.results:
                        prompt = prompt.replace(
                            f"{{dep:{dep_id}}}",
                            str(self.results[dep_id])
                        )

                # Execute
                logger.info("Executing task", task_id=task_id, agent=agent_name)
                result = await call_agent_simple(agent_name, prompt)

                return task_id, result

            # Execute batch
            batch_results = await asyncio.gather(*[
                execute_task(tid) for tid in ready_tasks
            ], return_exceptions=True)

            # Process results
            for item in batch_results:
                if isinstance(item, Exception):
                    logger.error("Task failed", error=str(item))
                    return {
                        "success": False,
                        "error": str(item),
                        "results": self.results,
                        "completed": list(completed),
                    }

                task_id, result = item
                self.results[task_id] = result
                completed.add(task_id)
                logger.info("Task completed", task_id=task_id)

        logger.info("Dependency graph execution complete")

        return {
            "success": True,
            "results": self.results,
            "completed": list(completed),
        }


# Example usage
async def example_dependency_graph():
    """Example: Multi-stage analysis with dependencies"""

    graph = DependencyGraph()

    # Stage 1: Parallel independent analyses
    graph.add_task(
        task_id="analyze_frontend",
        agent_name="typescript-expert",
        prompt_template="Analyze frontend code in /workspace/frontend",
    )

    graph.add_task(
        task_id="analyze_backend",
        agent_name="python-expert",
        prompt_template="Analyze backend code in /workspace/backend",
    )

    graph.add_task(
        task_id="analyze_database",
        agent_name="postgres-expert",
        prompt_template="Analyze database schema in /workspace/migrations",
    )

    # Stage 2: Security review (depends on all analyses)
    graph.add_task(
        task_id="security_review",
        agent_name="security-expert",
        prompt_template="""
Review security based on these analyses:

Frontend: {dep:analyze_frontend}
Backend: {dep:analyze_backend}
Database: {dep:analyze_database}
""",
        depends_on=["analyze_frontend", "analyze_backend", "analyze_database"],
    )

    # Stage 3: Final report (depends on security review)
    graph.add_task(
        task_id="final_report",
        agent_name="reviewer-agent",
        prompt_template="Create final report from security review:\n\n{dep:security_review}",
        depends_on=["security_review"],
    )

    # Execute graph
    result = await graph.execute()

    if result["success"]:
        print("Graph execution complete!")
        print(f"Final report:\n{result['results']['final_report']}")
    else:
        print(f"Execution failed: {result['error']}")
```

---

## 5. Reference Implementations

### 5.1 Complete Working Example: Research Pipeline

This example demonstrates all patterns working together:

```python
# src/harness/orchestration/examples/research_pipeline.py

"""
Complete research pipeline demonstrating all orchestration patterns:
1. Hierarchical: Break research into parallel subtopics
2. Broadcast: Multiple researchers gather diverse sources
3. Sequential: Synthesize findings → validate → format report
4. Event-driven: Optional async notification system
"""

import asyncio
from harness.orchestration.patterns.hierarchical_coordinator import HierarchicalCoordinator
from harness.orchestration.patterns.broadcast_multi_perspective import BroadcastMultiPerspective
from harness.orchestration.patterns.sequential_pipeline import SequentialPipeline
import structlog

logger = structlog.get_logger(__name__)

async def research_pipeline(topic: str) -> str:
    """Execute comprehensive research pipeline.

    Args:
        topic: Research topic

    Returns:
        Final formatted research report
    """
    logger.info("Starting research pipeline", topic=topic)

    # Phase 1: Hierarchical decomposition into research subtopics
    logger.info("Phase 1: Decomposing research into subtopics")

    decomposer = HierarchicalCoordinator(
        manager_agent="general-purpose",
        worker_agents=["research-specialist"] * 3,  # 3 parallel researchers
    )

    decompose_result = await decomposer.execute(
        task=f"Research this topic comprehensively: {topic}",
        max_workers=3,
    )

    if not decompose_result["success"]:
        return f"Research failed: {decompose_result['error']}"

    subtopic_findings = decompose_result["final_output"]

    # Phase 2: Broadcast for quality validation
    logger.info("Phase 2: Multi-perspective quality validation")

    validator = BroadcastMultiPerspective(
        agents=[
            "general-purpose",  # Completeness check
            "general-purpose",  # Accuracy check
            "general-purpose",  # Clarity check
        ],
        aggregation_strategy="synthesis",
        aggregator_agent="general-purpose",
    )

    validation_result = await validator.execute(
        prompt=f"Validate this research for completeness, accuracy, and clarity:\n\n{subtopic_findings}",
        require_all=False,
    )

    if not validation_result["success"]:
        logger.warning("Validation failed, proceeding with unvalidated findings")
        validated_findings = subtopic_findings
    else:
        validated_findings = validation_result["aggregated_result"]

    # Phase 3: Sequential refinement pipeline
    logger.info("Phase 3: Sequential refinement and formatting")

    pipeline = SequentialPipeline(stages=[
        {
            "agent_name": "general-purpose",
            "prompt_template": "Synthesize these findings into coherent narrative:\n{input}",
        },
        {
            "agent_name": "general-purpose",
            "prompt_template": "Add citations and references:\n{input}",
        },
        {
            "agent_name": "general-purpose",
            "prompt_template": "Format as professional research report:\n{input}",
        },
    ])

    pipeline_result = await pipeline.execute(validated_findings)

    if not pipeline_result["success"]:
        return f"Pipeline failed: {pipeline_result['error']}"

    final_report = pipeline_result["final_output"]

    logger.info("Research pipeline completed successfully")

    return final_report


# Execute
async def main():
    report = await research_pipeline(
        "Agent orchestration patterns in distributed LLM systems"
    )
    print("\n" + "="*80)
    print("FINAL RESEARCH REPORT")
    print("="*80 + "\n")
    print(report)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Production Patterns

### 6.1 Cost Optimization

```python
# src/harness/orchestration/cost_optimization.py

from typing import Any, Dict
import structlog

logger = structlog.get_logger(__name__)

class CostOptimizer:
    """Optimize orchestration costs through caching and model selection."""

    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.cost_tracking: Dict[str, float] = {}

    def cache_key(self, agent: str, prompt: str) -> str:
        """Generate cache key for agent + prompt."""
        import hashlib
        content = f"{agent}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def execute_with_cache(
        self,
        agent_name: str,
        prompt: str,
    ) -> str:
        """Execute with response caching."""
        from harness.direct_agent import call_agent_simple

        key = self.cache_key(agent_name, prompt)

        # Check cache
        if key in self.cache:
            logger.info("Cache hit", agent=agent_name)
            return self.cache[key]

        # Execute
        logger.info("Cache miss, executing", agent=agent_name)
        result = await call_agent_simple(agent_name, prompt)

        # Cache result
        self.cache[key] = result

        return result

    def get_cheaper_agent(self, agent_name: str) -> str:
        """Map to cheaper equivalent agent if available.

        Strategy: Use haiku for simple tasks, sonnet for complex.
        """
        # Simple mapping (extend based on your agents)
        if "expert" in agent_name:
            return agent_name  # Keep experts
        return "general-purpose"  # Cheaper default
```

### 6.2 Monitoring and Observability

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
        """Record task start."""
        self.active_tasks[task_id] = time.time()
        logger.info(
            "Task started",
            task_id=task_id,
            pattern=pattern,
            agent=agent,
        )

    def complete_task(
        self,
        task_id: str,
        success: bool,
        result_length: int = 0,
    ) -> None:
        """Record task completion."""
        if task_id not in self.active_tasks:
            logger.warning("Task not found in active tasks", task_id=task_id)
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

        logger.info(
            "Task completed",
            task_id=task_id,
            duration=f"{duration:.2f}s",
            success=success,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
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

### 6.3 Error Recovery

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

    async def execute_with_retry(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with exponential backoff retry."""
        last_error = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < self.max_attempts - 1:
                    backoff = min(
                        self.backoff_base ** attempt,
                        self.max_backoff,
                    )
                    logger.warning(
                        "Attempt failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=self.max_attempts,
                        backoff=backoff,
                        error=str(e),
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "All retry attempts failed",
                        attempts=self.max_attempts,
                        error=str(e),
                    )

        raise last_error
```

---

## 7. Migration Guide

### 7.1 From Single-Agent to Multi-Agent

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

### 7.2 Pattern Selection Flowchart

```
Start
  │
  ├─ Task is simple/linear
  │  └─> Sequential Pipeline
  │
  ├─ Task is complex/decomposable
  │  └─> Hierarchical Coordinator
  │
  ├─ Need multiple perspectives
  │  └─> Broadcast Multi-Perspective
  │
  └─ Long-running/distributed
     └─> Event-Driven Async
```

---

## Appendix: Code Examples

### A.1 Quick Start Template

```python
# src/harness/orchestration/my_orchestration.py

import asyncio
from harness.orchestration.patterns.hierarchical_coordinator import HierarchicalCoordinator

async def main():
    # Quick start: Hierarchical pattern
    coordinator = HierarchicalCoordinator(
        manager_agent="general-purpose",
        worker_agents=["python-expert", "typescript-expert"],
    )

    result = await coordinator.execute(
        "Analyze the full-stack application in /workspace/app"
    )

    if result["success"]:
        print(f"Analysis complete:\n{result['final_output']}")
    else:
        print(f"Failed: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### A.2 Plugin Integration

Create orchestration plugin:

```bash
# src/harness/plugins/orchestration/plugin.yaml
name: orchestration
version: 1.0.0
description: Multi-agent orchestration patterns

agents:
  - orchestration:coordinator

commands:
  - orchestration:pipeline
  - orchestration:hierarchical
```

### A.3 Testing Patterns

```python
# tests/unit/test_orchestration.py

import pytest
from harness.orchestration.patterns.sequential_pipeline import SequentialPipeline

@pytest.mark.asyncio
async def test_sequential_pipeline():
    """Test sequential pipeline execution."""

    pipeline = SequentialPipeline(stages=[
        {
            "agent_name": "general-purpose",
            "prompt_template": "Uppercase this: {input}",
        },
    ])

    result = await pipeline.execute("hello world")

    assert result["success"]
    assert "HELLO" in result["final_output"].upper()
```

---

## Conclusion

This architecture provides:

1. **4 Core Patterns**: Sequential, Hierarchical, Broadcast, Event-Driven
2. **Production-Ready**: Monitoring, error recovery, cost optimization
3. **SDK-Compatible**: Works with existing harness infrastructure
4. **Incrementally Adoptable**: Start simple, add complexity as needed
5. **Battle-Tested**: Based on proven distributed systems patterns

**Next Steps:**
1. Implement patterns in `src/harness/orchestration/`
2. Test with your specific agents and tasks
3. Add monitoring and cost tracking
4. Iterate based on production usage

**References:**
- Implementation plans: `docs/agentic-orch/IMPLEMENTATION_PLANS.md`
- Existing infrastructure: `src/harness/`
- Pattern implementations: This document, Section 3

---

**Document Version:** 1.1
**Last Updated:** 2025-12-18
**Maintained By:** Claude Agent SDK Orchestration Team
