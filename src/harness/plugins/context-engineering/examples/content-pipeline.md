# Content Generation Pipeline

Multi-stage content creation with quality gates.

## Architecture

```
Topic/Requirements
    ↓
Research Agent (gather information)
    ↓
Outline Agent (structure content)
    ↓
Writing Agents (parallel sections)
    ├→ Introduction Writer
    ├→ Section 1 Writer
    ├→ Section 2 Writer
    └→ Conclusion Writer
    ↓
Editor Agent (coherence, flow)
    ↓
Fact Checker Agent
    ↓
Style Agent (tone, formatting)
    ↓
Final Content
```

## Pattern: Sequential + Parallel Hybrid

- **Sequential stages**: Research → Outline → Write → Edit → Check → Style
- **Parallel within stages**: Multiple section writers work concurrently
- **Quality gates**: Each stage validates output before proceeding

## Implementation

```python
class ContentPipeline:
    async def generate(self, topic, requirements):
        # Stage 1: Research
        research = await self.research_agent.research(topic)

        # Stage 2: Outline
        outline = await self.outline_agent.create_outline(topic, research)

        # Stage 3: Parallel writing
        writing_tasks = [
            self.writing_agent.write_section(section, research)
            for section in outline.sections
        ]
        sections = await asyncio.gather(*writing_tasks)

        # Stage 4: Edit
        edited = await self.editor_agent.edit(sections)

        # Stage 5: Fact check
        checked = await self.fact_checker.verify(edited, research)

        # Stage 6: Style
        final = await self.style_agent.polish(checked, requirements.style)

        # Quality gate
        quality_score = await self.quality_agent.assess(final)
        if quality_score < requirements.min_quality:
            feedback = await self.quality_agent.get_feedback(final)
            return await self.generate_with_feedback(topic, requirements, feedback)

        return final
```

## Stage Details

### Stage 1: Research
- Gather background information
- Identify key points and sources
- Build knowledge base for writers

### Stage 2: Outline
- Structure content logically
- Define section boundaries
- Establish narrative flow

### Stage 3: Parallel Writing
- Each section writer works independently
- Shared context from research stage
- Section-specific requirements

### Stage 4: Editing
- Ensure coherence between sections
- Smooth transitions
- Consistent voice and tone

### Stage 5: Fact Checking
- Verify claims against research
- Flag unsupported statements
- Suggest corrections

### Stage 6: Style Polish
- Apply formatting requirements
- Tone adjustment
- Final cleanup

## Quality Gates

```python
class QualityGate:
    def __init__(self, min_score: float = 0.8):
        self.min_score = min_score

    async def check(self, content, requirements) -> bool:
        score = await self.quality_agent.assess(content)
        if score < self.min_score:
            feedback = await self.quality_agent.get_feedback(content)
            raise QualityGateFailure(score, feedback)
        return True
```

## Retry Logic

When quality gate fails:
1. Collect specific feedback
2. Re-run failing stage with feedback context
3. Limit retries (max 3 per stage)
4. Escalate to human review if still failing

## Harness Integration

```python
from harness.direct_agent import call_agent_simple

async def content_with_harness(topic: str, style: str):
    # Research phase
    research = await call_agent_simple(
        "research-team:research-specialist",
        f"Research: {topic}"
    )

    # Writing phase
    content = await call_agent_simple(
        "research-team:research-report-writer",
        f"Write content about {topic} in {style} style.\n\nResearch:\n{research}"
    )

    return content
```

## Optimization Notes

- **Parallel writing**: Major time savings for multi-section content
- **Caching**: Cache research for similar topics
- **Progressive streaming**: Show progress as sections complete
- **Model tiering**: Haiku for research, Sonnet for writing, Opus for editing
