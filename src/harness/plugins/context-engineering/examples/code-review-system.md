# Code Review System

Multi-agent code review with parallel specialist analysis.

## Architecture

```
User submits code
    ↓
Coordinator Agent (analyze requirements)
    ↓
    ├→ Security Agent (scan vulnerabilities)
    ├→ Performance Agent (identify bottlenecks)
    ├→ Style Agent (check code quality)
    └→ Documentation Agent (assess docs)
    ↓
Synthesis Agent (aggregate findings)
    ↓
Report to user
```

## Pattern: Hierarchical + Parallel

- **Coordinator**: Plans review scope, delegates to specialists
- **Specialists**: Run in parallel for 2-3x time savings
- **Synthesizer**: Aggregates findings into unified report

## Implementation

```python
class CodeReviewSystem:
    def __init__(self):
        self.coordinator = CoordinatorAgent()
        self.specialists = {
            "security": SecurityAgent(),
            "performance": PerformanceAgent(),
            "style": StyleAgent(),
            "documentation": DocumentationAgent()
        }
        self.synthesizer = SynthesisAgent()

    async def review_code(self, code, focus_areas=None):
        # Coordinator analyzes and plans
        plan = await self.coordinator.create_plan(code, focus_areas)

        # Execute specialists in parallel
        specialist_tasks = {}
        for area in plan.areas_to_review:
            if area in self.specialists:
                specialist_tasks[area] = self.specialists[area].analyze(code)

        results = await asyncio.gather(*specialist_tasks.values())
        specialist_results = dict(zip(specialist_tasks.keys(), results))

        # Synthesize results
        final_report = await self.synthesizer.synthesize(specialist_results)

        return final_report
```

## Optimizations

- **Parallel execution**: 2-3x time savings vs sequential
- **Model selection**: Haiku for simple code, Sonnet for complex
- **Caching**: Cache results for identical code snippets
- **Streaming**: Stream results to user as they arrive

## Harness Integration

Using `harness.direct_agent`:

```python
from harness.direct_agent import call_agent_simple

async def review_with_harness(code: str):
    # Security review
    security = await call_agent_simple(
        "dev-code-review-expert",
        f"Review this code for security vulnerabilities:\n\n{code}"
    )

    # Performance review
    performance = await call_agent_simple(
        "dev-python-expert",
        f"Review this code for performance issues:\n\n{code}"
    )

    return {"security": security, "performance": performance}
```

## Agent Definitions

Required agents (in `agents/configs/`):
- `coordinator-agent.md`: Planning and delegation
- `security-reviewer.md`: Vulnerability scanning
- `performance-reviewer.md`: Bottleneck identification
- `style-reviewer.md`: Code quality checks
- `synthesis-agent.md`: Report aggregation
