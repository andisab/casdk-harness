# Remaining Paradigms and Sections

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

## Paradigm 5: Mediator Pattern

**Rank: #5 | Prominence: ★★★☆☆ | Appeared in 5/8 research documents**

### Core Concept

Central mediator facilitates all agent communication. Agents don't communicate directly; all interactions go through mediator. Star topology with routing logic.

```
      A1      A2      A3
       ↓       ↓       ↓
       ← MEDIATOR →
       ↑       ↑       ↑
      A4      A5      A6
```

### Key Characteristics

- Star topology
- Centralized routing
- Policy enforcement
- Message transformation
- Agent decoupling

### Claude SDK Implementation

```python
from typing import Dict, Callable
import asyncio

class MediatorOrchestrator:
    """Central mediator for agent communication."""

    def __init__(self):
        self.agents = {}  # {name: capabilities}
        self.routing_rules = []

    def register_agent(self, name: str, capabilities: list):
        """Register agent with capabilities."""
        self.agents[name] = capabilities

    def add_routing_rule(self, condition: Callable, target_agent: str):
        """Add routing rule: if condition(message), route to target_agent."""
        self.routing_rules.append((condition, target_agent))

    async def route_message(self, message: str):
        """Route message to appropriate agent."""

        # Find matching agent based on rules
        for condition, target_agent in self.routing_rules:
            if condition(message):
                print(f"Routing to: {target_agent}")
                return await self._send_to_agent(target_agent, message)

        # Default: route to most capable agent
        return await self._send_to_agent(self._select_default_agent(message), message)

    async def _send_to_agent(self, agent_name: str, message: str):
        """Send message to specific agent."""
        from harness.direct_agent import call_agent_simple
        return await call_agent_simple(agent_name, message)

    def _select_default_agent(self, message: str):
        """Select agent based on content analysis."""
        # Simple keyword matching
        message_lower = message.lower()

        for agent_name, capabilities in self.agents.items():
            if any(cap in message_lower for cap in capabilities):
                return agent_name

        # Fallback to first agent
        return list(self.agents.keys())[0]


# Usage
mediator = MediatorOrchestrator()

mediator.register_agent("security-expert", ["security", "vulnerability"])
mediator.register_agent("performance-expert", ["performance", "optimization"])

mediator.add_routing_rule(
    lambda msg: "security" in msg.lower(),
    "security-expert"
)

result = await mediator.route_message("Check for security vulnerabilities")
```

### Advantages

- Decouples agents
- Centralized policy enforcement
- Easy to add/remove agents
- Single point for monitoring
- Complex routing logic

### Disadvantages

- Single point of failure
- Can become bottleneck
- Adds latency (extra hop)
- Mediator complexity grows

### Best For

- Complex routing needs
- Policy enforcement
- Agent pool changes frequently
- Centralized monitoring critical

---

## Decision Framework: Choosing Your Paradigm

### Quick Selection Guide

```
START: What's your primary need?

STRUCTURE & CONTROL?
├─ Clear task decomposition? → HIERARCHICAL
├─ Sequential processing? → PIPELINE
└─ Complex routing? → MEDIATOR

FLEXIBILITY & ROBUSTNESS?
├─ Fault tolerance critical? → PEER-TO-PEER
├─ Multiple perspectives? → PEER-TO-PEER
└─ Incremental solution building? → BLACKBOARD

PROBLEM CHARACTERISTICS?
├─ Well-defined algorithm? → HIERARCHICAL or PIPELINE
├─ No clear solution path? → BLACKBOARD
└─ Dynamic environment? → PEER-TO-PEER
```

### Decision Matrix

| If You Need... | Choose | Why |
|----------------|--------|-----|
| Predictable workflow | Hierarchical or Pipeline | Deterministic execution |
| Fault tolerance | Peer-to-Peer | No single point of failure |
| Complex problem-solving | Blackboard | Incremental, multi-perspective |
| Cost optimization | Pipeline or Hierarchical | Lower communication overhead |
| Agent autonomy | Peer-to-Peer | Distributed decision-making |
| Centralized control | Hierarchical | Clear authority |
| Policy enforcement | Mediator | Routing and validation logic |

### Scale Recommendations

**Small (1-5 agents)**: Pipeline or simple Hierarchical
**Medium (5-20 agents)**: Hierarchical or Mediator
**Large (20+ agents)**: Hierarchical (multi-level) or Hybrid

### By Use Case

**Code Review**: Hierarchical (coordinator + specialists)
**Research**: Hierarchical or Blackboard
**Content Generation**: Pipeline
**Multi-perspective Analysis**: Peer-to-Peer or Ensemble
**Data Processing**: Pipeline
**Complex Problem-Solving**: Blackboard
**Dynamic Routing**: Mediator

---

## Claude Agent SDK Best Practices

### 1. Model Selection Strategy

```python
# Task complexity → Model tier
def select_model(task_complexity: str) -> str:
    return {
        "simple": "claude-3-haiku",      # $0.00025/1K in, $0.00125/1K out
        "medium": "claude-3-5-sonnet",   # $0.003/1K in, $0.015/1K out
        "complex": "claude-opus-4-5"     # $0.015/1K in, $0.075/1K out
    }[task_complexity]

# Role → Model tier
coordinator = "claude-opus-4-5"  # Strategic planning
managers = "claude-3-5-sonnet"   # Tactical coordination
workers = "claude-3-haiku"       # Specialized execution
```

### 2. Context Management

```python
class ContextManager:
    """Manage context to stay within token limits."""

    def __init__(self, max_tokens=100000):
        self.max_tokens = max_tokens
        self.messages = []

    def add_message(self, message: str):
        """Add message with automatic summarization."""
        self.messages.append(message)

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        total_tokens = sum(len(m) // 4 for m in self.messages)

        if total_tokens > self.max_tokens:
            # Summarize oldest messages
            self._summarize_oldest()

    def _summarize_oldest(self):
        """Summarize oldest 25% of messages."""
        cutoff = len(self.messages) // 4
        to_summarize = self.messages[:cutoff]

        # Use LLM to summarize
        summary = self._summarize(to_summarize)

        # Replace with summary
        self.messages = [summary] + self.messages[cutoff:]

    def get_context(self) -> str:
        """Get full context for agent."""
        return "\n\n".join(self.messages)
```

### 3. Error Handling Pattern

```python
async def resilient_agent_call(agent_name: str, prompt: str, max_retries=3):
    """Call agent with retry and error handling."""

    for attempt in range(max_retries):
        try:
            result = await call_agent_simple(agent_name, prompt)

            # Validate result
            if not result or len(result) < 10:
                raise ValueError("Response too short")

            return result

        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                return f"[ERROR: Timeout after {max_retries} attempts]"
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except Exception as e:
            if attempt == max_retries - 1:
                return f"[ERROR: {str(e)}]"
            await asyncio.sleep(2 ** attempt)
```

### 4. Caching Strategy

```python
import hashlib
import json

class ResponseCache:
    """Cache agent responses for cost savings."""

    def __init__(self):
        self.cache = {}

    def get_key(self, agent_name: str, prompt: str) -> str:
        """Generate cache key."""
        content = f"{agent_name}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_or_call(self, agent_name: str, prompt: str):
        """Get from cache or call agent."""
        key = self.get_key(agent_name, prompt)

        if key in self.cache:
            print(f"Cache hit for {agent_name}")
            return self.cache[key]

        print(f"Cache miss for {agent_name}")
        result = await call_agent_simple(agent_name, prompt)

        self.cache[key] = result
        return result

# Global cache instance
cache = ResponseCache()

# Usage
result = await cache.get_or_call("analyst", "Analyze this code...")
```

### 5. Parallel Execution

```python
async def parallel_execution_example():
    """Execute multiple agents in parallel."""

    # Independent tasks that can run concurrently
    tasks = [
        call_agent_simple("security", "Check security"),
        call_agent_simple("performance", "Check performance"),
        call_agent_simple("style", "Check style")
    ]

    # Run all in parallel
    results = await asyncio.gather(*tasks)

    return {
        "security": results[0],
        "performance": results[1],
        "style": results[2]
    }
```

### 6. Working with /workspace

```python
import os
from pathlib import Path

def read_workspace_file(relative_path: str) -> str:
    """Read file from /workspace."""
    full_path = Path("/workspace") / relative_path

    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {full_path}")

    with open(full_path, 'r') as f:
        return f.read()


def write_workspace_file(relative_path: str, content: str):
    """Write file to /workspace."""
    full_path = Path("/workspace") / relative_path

    # Create directories if needed
    full_path.parent.mkdir(parents=True, exist_ok=True)

    with open(full_path, 'w') as f:
        f.write(content)


# Usage in agent prompt
code_content = read_workspace_file("src/auth.py")

prompt = f"""
Analyze this code for security issues:

```python
{code_content}
```

Provide findings with line numbers.
"""
```

### 7. Structured Output Parsing

```python
import json
import re

def extract_json_from_response(text: str) -> dict:
    """Robustly extract JSON from agent response."""

    # Try code block first
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: return as string in dict
    return {"raw_response": text}
```

### 8. Cost Tracking

```python
class CostTracker:
    """Track token usage and costs."""

    PRICING = {
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
        "claude-opus-4-5": {"input": 0.015, "output": 0.075}
    }

    def __init__(self):
        self.calls = []

    def track(self, model: str, input_tokens: int, output_tokens: int):
        """Track a single call."""
        cost = (
            input_tokens * self.PRICING[model]["input"] / 1000 +
            output_tokens * self.PRICING[model]["output"] / 1000
        )

        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        })

    def get_total_cost(self) -> float:
        """Get total cost across all calls."""
        return sum(call["cost"] for call in self.calls)

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_calls": len(self.calls),
            "total_cost": self.get_total_cost(),
            "total_input_tokens": sum(c["input_tokens"] for c in self.calls),
            "total_output_tokens": sum(c["output_tokens"] for c in self.calls)
        }
```

---

## Production-Ready Code Examples

### Complete Code Review System

```python
from harness.direct_agent import call_agent_simple
import asyncio
import json
from pathlib import Path

class ProductionCodeReviewSystem:
    """
    Production-ready hierarchical code review system.
    Features: parallel execution, error handling, caching, monitoring.
    """

    def __init__(self):
        self.coordinator = "review-coordinator"
        self.specialists = {
            "security": "security-specialist",
            "performance": "performance-specialist",
            "style": "style-specialist",
            "documentation": "doc-specialist"
        }
        self.synthesizer = "review-synthesizer"
        self.cache = ResponseCache()
        self.cost_tracker = CostTracker()

    async def review_files(self, file_paths: list[str]):
        """
        Review multiple code files.

        Args:
            file_paths: Paths relative to /workspace

        Returns:
            Comprehensive review report
        """

        # Read all files
        files_content = {}
        for path in file_paths:
            try:
                full_path = Path("/workspace") / path
                with open(full_path, 'r') as f:
                    files_content[path] = f.read()
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue

        if not files_content:
            return {"error": "No files could be read"}

        # Phase 1: Coordinator creates plan
        print("Phase 1: Creating review plan...")
        plan = await self._create_plan(files_content)

        # Phase 2: Execute specialists in parallel
        print("Phase 2: Executing specialists...")
        reviews = await self._execute_specialists(files_content, plan)

        # Phase 3: Synthesize results
        print("Phase 3: Synthesizing final report...")
        report = await self._synthesize(files_content, reviews, plan)

        # Phase 4: Generate metrics
        stats = self.cost_tracker.get_stats()

        return {
            "report": report,
            "specialist_reviews": reviews,
            "metrics": stats,
            "files_reviewed": list(files_content.keys())
        }

    async def _create_plan(self, files_content: dict) -> dict:
        """Coordinator creates review plan."""

        file_list = "\n".join([
            f"- {path} ({len(content)} chars)"
            for path, content in files_content.items()
        ])

        prompt = f"""
You are a Code Review Coordinator. Create a review plan.

Files to review:
{file_list}

Available specialists:
- security: Security vulnerabilities, injection attacks, auth issues
- performance: Performance bottlenecks, inefficient algorithms, memory usage
- style: Code style, readability, maintainability, best practices
- documentation: Documentation quality, completeness, clarity

Create a review plan as JSON:
{{
  "specialists_needed": ["security", "performance", "style", "documentation"],
  "focus_areas": {{
    "security": "Check for injection vulnerabilities and auth issues",
    "performance": "Analyze algorithm efficiency"
  }},
  "synthesis_strategy": "Prioritize by severity: critical → high → medium → low"
}}
"""

        result = await self.cache.get_or_call(self.coordinator, prompt)
        return extract_json_from_response(result)

    async def _execute_specialists(self, files_content: dict, plan: dict) -> dict:
        """Execute specialist reviews in parallel."""

        specialists_needed = plan.get("specialists_needed", list(self.specialists.keys()))
        focus_areas = plan.get("focus_areas", {})

        # Create tasks for each specialist
        tasks = {}
        for specialist_type in specialists_needed:
            if specialist_type in self.specialists:
                agent_name = self.specialists[specialist_type]
                focus = focus_areas.get(specialist_type, f"Review for {specialist_type}")

                tasks[specialist_type] = self._execute_specialist(
                    agent_name,
                    files_content,
                    focus
                )

        # Execute all in parallel
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Combine results
        reviews = {}
        for (specialist_type, task), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                reviews[specialist_type] = {
                    "error": str(result),
                    "status": "failed"
                }
            else:
                reviews[specialist_type] = result

        return reviews

    async def _execute_specialist(self, agent_name: str, files_content: dict, focus: str) -> dict:
        """Execute a single specialist review."""

        # Format code for prompt
        code_sections = []
        for path, content in files_content.items():
            code_sections.append(f"File: {path}\n```\n{content}\n```")

        code_str = "\n\n".join(code_sections)

        prompt = f"""
You are a code review specialist. Review this code.

Focus: {focus}

Code:
{code_str}

Provide findings in JSON format:
{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "type": "specific issue type",
      "description": "detailed description",
      "file": "file path",
      "line": "line number or range",
      "recommendation": "how to fix",
      "code_snippet": "relevant code"
    }}
  ],
  "overall_assessment": "brief summary",
  "confidence": 0.0-1.0,
  "positive_findings": ["things done well"]
}}
"""

        result = await resilient_agent_call(agent_name, prompt, max_retries=3)
        return extract_json_from_response(result)

    async def _synthesize(self, files_content: dict, reviews: dict, plan: dict) -> str:
        """Synthesize final report."""

        prompt = f"""
You are a Review Synthesizer. Create a comprehensive code review report.

Files reviewed: {', '.join(files_content.keys())}

Specialist Reviews:
{json.dumps(reviews, indent=2)}

Synthesis Strategy: {plan.get('synthesis_strategy', 'Organize by severity')}

Create a professional report with:
1. Executive Summary
2. Critical Issues (must fix immediately)
3. High Priority Issues (should fix soon)
4. Medium Priority Issues (fix when convenient)
5. Low Priority Issues / Suggestions
6. Positive Findings (things done well)
7. Overall Assessment
8. Next Steps

Format with clear sections and actionable recommendations.
"""

        result = await self.cache.get_or_call(self.synthesizer, prompt)
        return result


# Usage
async def main():
    reviewer = ProductionCodeReviewSystem()

    result = await reviewer.review_files([
        "src/auth.py",
        "src/api.py",
        "src/database.py"
    ])

    print("\n=== CODE REVIEW REPORT ===\n")
    print(result["report"])

    print("\n=== METRICS ===")
    print(f"Total cost: ${result['metrics']['total_cost']:.4f}")
    print(f"Total calls: {result['metrics']['total_calls']}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Common Pitfalls and How to Avoid Them

### 1. Context Explosion

**Pitfall**: Passing full context to every agent, exceeding token limits.

**Solution**:
```python
# Bad: Pass everything
context = full_conversation_history + all_files

# Good: Pass only relevant context
context = summarize(relevant_messages) + current_file
```

### 2. Sequential Execution When Parallel is Possible

**Pitfall**: Running independent tasks sequentially.

**Solution**:
```python
# Bad: Sequential (slow)
result1 = await agent1.execute()
result2 = await agent2.execute()

# Good: Parallel (fast)
result1, result2 = await asyncio.gather(
    agent1.execute(),
    agent2.execute()
)
```

### 3. No Error Handling

**Pitfall**: Agent failures crash entire system.

**Solution**:
```python
# Bad: No error handling
result = await call_agent_simple("agent", prompt)

# Good: Resilient
try:
    result = await resilient_agent_call("agent", prompt, max_retries=3)
except Exception as e:
    result = fallback_handler(e)
```

### 4. Ignoring Costs

**Pitfall**: No tracking of token usage and costs.

**Solution**:
```python
# Implement cost tracking
tracker = CostTracker()

# Track every call
result = await call_agent_simple("agent", prompt)
tracker.track("claude-3-5-sonnet", input_tokens, output_tokens)

# Alert on budget exceeded
if tracker.get_total_cost() > budget:
    send_alert()
```

### 5. Brittle JSON Parsing

**Pitfall**: Assuming agents always return perfect JSON.

**Solution**:
```python
# Bad: Assumes perfect JSON
result = json.loads(response)

# Good: Robust extraction
result = extract_json_from_response(response)
# Handles code blocks, malformed JSON, fallbacks
```

---

## References and Further Reading

### Official Documentation

- **Claude API**: https://docs.anthropic.com/
- **Claude Agent SDK**: Internal documentation
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

---

## Conclusion

This guide presented five dominant orchestration paradigms for multi-agent systems:

1. **Hierarchical**: Best for structured problems with clear decomposition
2. **Peer-to-Peer**: Best for dynamic environments requiring robustness
3. **Blackboard**: Best for complex problem-solving without clear algorithms
4. **Pipeline**: Best for sequential data processing
5. **Mediator**: Best for complex routing and policy enforcement

**Key Takeaways:**

- Start simple (Hierarchical or Pipeline) and add complexity as needed
- Hybrid approaches dominate in production systems
- Context management and caching are critical for cost control
- Always implement error handling and monitoring
- Choose paradigms based on problem characteristics, not preferences

**Next Steps:**

1. Identify your use case characteristics
2. Select appropriate paradigm using decision framework
3. Implement basic version with provided code examples
4. Add error handling, caching, and monitoring
5. Measure and optimize performance
6. Consider hybrid approaches as system evolves

Happy orchestrating!
