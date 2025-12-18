# Agentic Orchestration Paradigms: A Comprehensive Guide

**A Developer's Reference for Multi-Agent Coordination with Claude Agent SDK**

Version 1.0 | December 17, 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Top 5 Orchestration Paradigms](#the-top-5-orchestration-paradigms)
3. [Paradigm 1: Hierarchical Coordination](#paradigm-1-hierarchical-coordination)
4. [Paradigm 2: Peer-to-Peer Coordination](#paradigm-2-peer-to-peer-coordination)
5. [Paradigm 3: Blackboard Architecture](#paradigm-3-blackboard-architecture)
6. [Paradigm 4: Pipeline/Workflow](#paradigm-4-pipelineworkflow)
7. [Paradigm 5: Mediator Pattern](#paradigm-5-mediator-pattern)
8. [Decision Framework: Choosing Your Paradigm](#decision-framework-choosing-your-paradigm)
9. [Claude Agent SDK Best Practices](#claude-agent-sdk-best-practices)
10. [Production-Ready Code Examples](#production-ready-code-examples)
11. [Hybrid Approaches](#hybrid-approaches)
12. [Performance Optimization](#performance-optimization)
13. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)
14. [References and Further Reading](#references-and-further-reading)

---

## Executive Summary

### Overview

Multi-agent orchestration is the art and science of coordinating multiple AI agents to solve complex problems that exceed the capabilities of a single agent. This guide presents the **five dominant orchestration paradigms** identified through comprehensive research and analysis of production multi-agent systems, with specific focus on implementation using the **Claude Agent SDK**.

### The Top 5 Paradigms

Based on frequency of use, depth of coverage in research, and proven effectiveness in production systems, the top five orchestration paradigms are:

| Rank | Paradigm | Best For | Complexity | Scalability |
|------|----------|----------|------------|-------------|
| 1 | **Hierarchical Coordination** | Structured problems, clear decomposition | Low-Medium | High |
| 2 | **Peer-to-Peer (P2P)** | Dynamic environments, fault tolerance | High | Very High |
| 3 | **Blackboard Architecture** | Complex problem-solving, incremental solutions | Medium | Medium |
| 4 | **Pipeline/Workflow** | Sequential data processing, predictable steps | Low | Medium |
| 5 | **Mediator Pattern** | Complex routing, policy enforcement | Medium | Medium |

### Key Insights from Research

1. **No Universal Solution**: Different patterns excel in different scenarios. Pattern selection depends on problem characteristics, team size, budget constraints, and performance requirements.

2. **Hybrid Approaches Dominate**: Production systems rarely use pure implementations. Most successful systems combine multiple patterns (e.g., Hierarchical planning + Pipeline execution + Ensemble verification).

3. **Context Management is Critical**: For LLM agents, token costs and context window limits require careful management through summarization, filtering, and hierarchical compression.

4. **Start Simple, Add Complexity**: Research consistently recommends beginning with Hierarchical or Pipeline patterns, then evolving to more complex hybrid approaches based on actual needs.

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

### Implementation Progression

**Phase 1: Single Agent (Baseline)** - 1-2 weeks
- Validate use case
- Establish performance baselines
- Build comprehensive toolset

**Phase 2: Coordinator-Executor** - 2-4 weeks
- Add task decomposition
- 2-3 specialized executors
- Parallel execution

**Phase 3: Advanced Patterns** - 4-6 weeks
- Multi-level hierarchies or hybrid patterns
- Review/validation agents
- Quality gates and error handling

**Phase 4: Scale and Optimize** - Ongoing
- Caching implementation
- Model cascading
- Advanced context management
- Production monitoring

### Document Purpose

This guide provides:

- **Detailed analysis** of each paradigm with strengths, weaknesses, and use cases
- **Production-ready code examples** for the Claude Agent SDK
- **Implementation guidance** specific to Python, `harness.direct_agent`, and Task tools
- **Decision frameworks** to select the right paradigm for your use case
- **Performance optimization** techniques tested in production
- **Common pitfalls** and how to avoid them

### Who Should Read This

- **AI Engineers** building multi-agent systems
- **Software Architects** designing agentic applications
- **Product Teams** evaluating agent orchestration approaches
- **Researchers** studying agent coordination patterns
- **Anyone** working with Claude Agent SDK for complex workflows

---

## The Top 5 Orchestration Paradigms

### Selection Criteria

These five paradigms were selected based on:

1. **Frequency**: Appeared in 5-8 out of 8 research documents analyzed
2. **Implementation maturity**: Multiple production examples available
3. **Claude SDK compatibility**: Natural fit with SDK capabilities
4. **Practical effectiveness**: Proven results in real-world systems
5. **Developer accessibility**: Reasonable implementation complexity

### Comparison Matrix

| Paradigm | Control | Coupling | Best Use Case | Latency | Token Efficiency | Implementation Difficulty |
|----------|---------|----------|---------------|---------|------------------|---------------------------|
| Hierarchical | Centralized | Tight | Structured tasks | Medium | High (with summarization) | Low-Medium |
| Peer-to-Peer | Distributed | Loose | Dynamic tasks | Variable | Low (high communication) | High |
| Blackboard | Centralized | Medium | Complex problem-solving | Medium | Medium | Medium |
| Pipeline | Centralized | Tight | Data processing | High (sequential) | High | Low |
| Mediator | Centralized | Loose | Routing needs | Medium | High | Medium |

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

## Paradigm 1: Hierarchical Coordination

**Rank: #1 | Prominence: ★★★★★ | Appeared in 8/8 research documents**

### Core Concept

Hierarchical coordination organizes agents in a tree structure with clear authority levels. Superior agents delegate tasks to subordinates who report results back up the hierarchy. This creates a clear chain of command with centralized decision-making at each level.

```
           Master Coordinator
          /        |         \
    Manager A  Manager B  Manager C
    /    \        |       /    \
  W1    W2      W3      W4    W5
```

### Key Characteristics

**Structural Organization:**
- Tree-structured with clear authority levels
- Top-down task delegation, bottom-up result aggregation
- Span of control: 5-10 direct reports per level (optimal)
- Clear responsibility boundaries
- Sibling agents don't communicate directly

**Communication Flow:**
- Commands flow downward through levels
- Results and status flow upward
- Parent agent mediates all sibling coordination
- Progressive context refinement down the tree
- Hierarchical summarization going up

**Control Mechanisms:**
- Centralized decision-making at each level
- Strong, predictable control flow
- Deterministic execution ordering
- Explicit dependency management
- Quality gates at each level

### Variants

**1. Coordinator-Executor Pattern** (Most Common)
- Single coordinator with multiple specialized executors
- Coordinator plans, executors perform
- Extensively used in Claude Agent SDK examples
- Best for: 2-10 agents, well-defined tasks

**2. Multi-Level Hierarchy** (3+ levels)
- Master → Domain Managers → Specialized Workers
- Progressive task refinement at each level
- Context becomes more specific down the tree
- Best for: 20-200 agents, complex domains

**3. Hierarchical Task Network (HTN) Decomposition**
- Recursive decomposition into primitive actions
- Formal task definitions and operators
- Strong theoretical foundation
- Best for: Planning systems, known task structures

### Advantages

- **Clear responsibility**: Each agent has defined role and scope
- **Predictable behavior**: Deterministic execution flow
- **Easy to debug**: Straightforward execution trace
- **Scalable**: Add sub-hierarchies as needed
- **Efficient for structured problems**: Natural decomposition
- **Token-efficient**: Manager maintains global context, workers get local views
- **Natural mapping**: Mirrors organizational structures

### Disadvantages

- **Bottleneck risk**: Higher levels can become overloaded
- **Single point of failure**: Each level creates dependency
- **Communication latency**: Multiple hops for deep trees
- **Inflexible**: Difficult to adapt to dynamic changes
- **Limited worker autonomy**: Workers can't make high-level decisions
- **Context loss**: Information may be lost in summarization

### When to Use Hierarchical

**Most Effective For:**
- Well-structured problems with clear decomposition
- Business process automation
- Code review systems
- Content generation pipelines
- Tasks with explicit subtask dependencies
- When centralized control is desired
- Strong consistency requirements
- Audit trail and accountability critical

**Less Effective For:**
- Highly dynamic, exploratory tasks
- When agent autonomy is paramount
- Flat, collaborative problem-solving
- When single point of failure is unacceptable
- Real-time systems requiring minimal latency

### Claude Agent SDK Implementation

#### Model Selection by Level

```python
# Master Agent - Strategic planning and high-level decomposition
master_config = {
    "model": "claude-opus-4-5",  # or claude-3-5-sonnet for cost savings
    "role": "Master Coordinator",
    "responsibilities": [
        "Receive and analyze complex requests",
        "Decompose into high-level phases/domains",
        "Delegate to domain managers",
        "Synthesize final comprehensive response"
    ]
}

# Domain Manager - Tactical coordination
manager_config = {
    "model": "claude-3-5-sonnet",
    "role": "Domain Manager",
    "responsibilities": [
        "Receive domain-specific phase",
        "Break into specific executable tasks",
        "Assign to specialized workers",
        "Validate and aggregate worker results",
        "Report summary to master"
    ]
}

# Worker Agent - Specialized execution
worker_config = {
    "model": "claude-3-haiku",  # or sonnet for complex tasks
    "role": "Specialized Worker",
    "responsibilities": [
        "Execute atomic task with specialized tools",
        "Return structured result",
        "Report status to manager"
    ]
}
```

#### Implementation Pattern

```python
from harness.direct_agent import call_agent, call_agent_simple
import asyncio
import json

class HierarchicalOrchestrator:
    """
    Hierarchical orchestration with master coordinator and specialized workers.
    """

    def __init__(self):
        self.master_agent = "coordinator"
        self.worker_agents = {
            "security": "security-analyst",
            "performance": "performance-analyst",
            "documentation": "doc-reviewer"
        }

    async def execute(self, user_request: str):
        """
        Execute hierarchical workflow:
        1. Master creates plan
        2. Workers execute in parallel
        3. Master synthesizes results
        """

        # Step 1: Master analyzes and creates execution plan
        plan_prompt = f"""
You are a Master Coordinator. Analyze this request and create an execution plan.

Request: {user_request}

Available specialist agents:
- security-analyst: Security and vulnerability analysis
- performance-analyst: Performance and optimization analysis
- doc-reviewer: Documentation quality review

Create a plan as JSON:
{{
  "subtasks": [
    {{
      "id": "T1",
      "agent": "security-analyst",
      "instruction": "Detailed instruction for agent",
      "depends_on": []
    }}
  ],
  "synthesis_strategy": "How to combine results"
}}
"""

        plan_response = await call_agent_simple(self.master_agent, plan_prompt)
        plan = json.loads(self._extract_json(plan_response))

        # Step 2: Execute workers in parallel (respecting dependencies)
        worker_results = await self._execute_parallel_workers(plan["subtasks"])

        # Step 3: Master synthesizes final response
        synthesis_prompt = f"""
You are a Master Coordinator. Synthesize the following worker results into a comprehensive response.

Original Request: {user_request}

Worker Results:
{json.dumps(worker_results, indent=2)}

Synthesis Strategy: {plan.get("synthesis_strategy", "Combine all findings")}

Provide a comprehensive, user-friendly response.
"""

        final_response = await call_agent_simple(self.master_agent, synthesis_prompt)

        return {
            "plan": plan,
            "worker_results": worker_results,
            "final_response": final_response
        }

    async def _execute_parallel_workers(self, subtasks):
        """Execute workers in parallel, respecting dependencies."""
        completed = {}

        # Build dependency graph
        task_by_id = {task["id"]: task for task in subtasks}

        # Execute in waves based on dependencies
        while len(completed) < len(subtasks):
            # Find tasks with satisfied dependencies
            ready_tasks = [
                task for task in subtasks
                if task["id"] not in completed
                and all(dep in completed for dep in task.get("depends_on", []))
            ]

            if not ready_tasks:
                raise RuntimeError("Circular dependency detected")

            # Execute ready tasks in parallel
            tasks_to_execute = [
                self._execute_worker(task, completed)
                for task in ready_tasks
            ]

            results = await asyncio.gather(*tasks_to_execute)

            # Store results
            for task, result in zip(ready_tasks, results):
                completed[task["id"]] = result

        return completed

    async def _execute_worker(self, task, context):
        """Execute a single worker task."""
        agent_name = self.worker_agents.get(task["agent"])

        if not agent_name:
            raise ValueError(f"Unknown agent: {task['agent']}")

        # Build context from dependencies
        dep_context = "\n".join([
            f"Result from {dep}: {context[dep]}"
            for dep in task.get("depends_on", [])
        ])

        prompt = f"""
{task['instruction']}

{f"Context from previous tasks:\n{dep_context}" if dep_context else ""}

Provide your analysis with a confidence score.
"""

        result = await call_agent_simple(agent_name, prompt)

        return {
            "agent": task["agent"],
            "result": result,
            "task_id": task["id"]
        }

    def _extract_json(self, text: str) -> str:
        """Extract JSON from markdown code blocks or raw text."""
        import re

        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return text


# Usage example
async def main():
    orchestrator = HierarchicalOrchestrator()

    result = await orchestrator.execute(
        "Review the authentication module for security issues, "
        "performance bottlenecks, and documentation quality."
    )

    print("Final Response:", result["final_response"])


if __name__ == "__main__":
    asyncio.run(main())
```

### Best Practices for Hierarchical Patterns

1. **Span of Control**: Keep 5-10 direct reports per manager for optimal coordination
2. **Context Compression**: Summarize at each level to manage token costs
3. **Parallel Execution**: Execute independent siblings concurrently with `asyncio.gather`
4. **Quality Gates**: Validate results at each level before passing up
5. **Error Escalation**: Failed tasks escalate to parent for handling
6. **Model Selection**: Use powerful models (Opus/Sonnet) for coordinators, Haiku for simple workers
7. **Caching**: Cache coordinator decisions for similar requests
8. **Monitoring**: Log coordination decisions and worker performance

### Performance Characteristics

- **Latency**: O(log n) for balanced trees, O(n) for deep chains
- **Throughput**: High with parallel execution at each level
- **Token Usage**: Medium to High (manager needs context, workers are focused)
- **Cost**: Moderate (premium model for coordinator, cheaper for workers)
- **Scalability**: Excellent (logarithmic with tree depth)

### Common Pitfalls

1. **Over-centralization**: Don't route all decisions through single coordinator
2. **Context explosion**: Summarize aggressively at each level
3. **Synchronous execution**: Always parallelize independent subtasks
4. **Brittle plans**: Build error handling into coordination logic
5. **Token waste**: Don't pass full context to workers who don't need it

---

## Paradigm 4: Pipeline/Workflow

**Rank: #4 | Prominence: ★★★★☆ | Appeared in 7/8 research documents**

### Core Concept

Sequential chain of agents where each specializes in one stage. Output of stage N becomes input of stage N+1. Linear or branching data flow with clear handoff points.

```
Input → Agent 1 (Parse) → Agent 2 (Process) → Agent 3 (Format) → Output
```

### Key Characteristics

- Sequential agent chain
- Clear handoff points between stages
- Each agent specializes in one transformation
- Deterministic flow (usually)
- Can parallelize independent branches

### Claude SDK Implementation

```python
from harness.direct_agent import call_agent_simple
import asyncio

class PipelineOrchestrator:
    """Sequential pipeline with specialized stages."""

    def __init__(self, stages):
        """
        Args:
            stages: List of {"agent_name": str, "transform": callable}
        """
        self.stages = stages

    async def execute(self, initial_input: str):
        """Execute pipeline sequentially."""
        current_data = initial_input
        results = []

        for i, stage in enumerate(self.stages):
            print(f"Stage {i+1}/{len(self.stages)}: {stage['agent_name']}")

            # Execute stage
            prompt = stage.get("prompt_template", "{input}").format(
                input=current_data
            )

            result = await call_agent_simple(
                stage["agent_name"],
                prompt
            )

            # Optional transformation
            if "transform" in stage:
                result = stage["transform"](result)

            results.append({
                "stage": i+1,
                "agent": stage["agent_name"],
                "output": result
            })

            # Output becomes input for next stage
            current_data = result

        return {
            "final_output": current_data,
            "stage_results": results
        }


# Content generation pipeline example
async def content_pipeline_example():
    pipeline = PipelineOrchestrator([
        {
            "agent_name": "researcher",
            "prompt_template": "Research this topic and provide key facts: {input}"
        },
        {
            "agent_name": "outliner",
            "prompt_template": "Create an article outline based on: {input}"
        },
        {
            "agent_name": "writer",
            "prompt_template": "Write full article following this outline: {input}"
        },
        {
            "agent_name": "editor",
            "prompt_template": "Edit for clarity and flow: {input}"
        },
        {
            "agent_name": "fact-checker",
            "prompt_template": "Verify all factual claims: {input}"
        }
    ])

    result = await pipeline.execute("The impact of AI on healthcare")
    return result["final_output"]
```

### Advantages

- Simple to understand and implement
- Clear data dependencies
- Predictable execution
- Modular and testable
- Easy to debug (linear trace)

### Disadvantages

- Sequential bottleneck
- Inflexible to dynamic changes
- Brittle (failure cascades)
- High latency for long pipelines

### Best For

- Data processing tasks
- Content generation workflows
- Multi-pass refinement
- Predictable transformations

---
