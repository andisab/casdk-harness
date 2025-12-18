# Research Assistant

Multi-source research system with fact verification.

## Architecture

```
User query
    ↓
Query Understanding Agent (parse intent)
    ↓
Research Coordinator
    ├→ Web Search Agent (find sources)
    ├→ Document Analysis Agent (read sources)
    └→ Fact Verification Agent (cross-check)
    ↓
Synthesis Agent (create comprehensive answer)
    ↓
Citation Agent (add sources)
    ↓
Answer with sources
```

## Pattern: Pipeline + Verification

- **Query Understanding**: Parse user intent and requirements
- **Parallel Research**: Multiple agents gather information concurrently
- **Verification Loop**: Cross-check facts before synthesis
- **Citation**: Proper source attribution

## Key Features

1. **Multi-source information gathering**
   - Web search for current information
   - Document analysis for deep content
   - Cross-referencing for accuracy

2. **Fact verification**
   - Multiple source confirmation
   - Confidence scoring
   - Conflict resolution

3. **Proper citation**
   - Source tracking throughout pipeline
   - Automatic citation formatting
   - Link preservation

4. **Iterative refinement**
   - Quality assessment gates
   - Feedback loops for improvement
   - Progressive detail addition

## Implementation Notes

```python
class ResearchPipeline:
    async def research(self, query: str):
        # Stage 1: Understand query
        intent = await self.query_agent.parse(query)

        # Stage 2: Parallel research
        sources = await asyncio.gather(
            self.web_agent.search(intent.keywords),
            self.doc_agent.find_relevant(intent.topics)
        )

        # Stage 3: Verify facts
        verified = await self.verify_agent.cross_check(sources)

        # Stage 4: Synthesize
        answer = await self.synthesis_agent.create_answer(
            query, verified, intent.depth
        )

        # Stage 5: Add citations
        cited = await self.citation_agent.add_sources(answer, sources)

        return cited
```

## Harness Integration

Using research-team plugin agents:

```python
from harness.direct_agent import call_agent

async def research_with_harness(topic: str):
    async for msg in call_agent(
        "research-team:lead-research-coordinator",
        f"Research the following topic thoroughly:\n\n{topic}",
        verbose=True
    ):
        process_streaming_result(msg)
```

## Quality Gates

| Gate | Threshold | Action if Failed |
|------|-----------|------------------|
| Source count | >= 3 sources | Expand search |
| Fact confidence | >= 0.8 | Additional verification |
| Coverage score | >= 0.7 | Research more subtopics |
| Citation completeness | 100% | Add missing sources |
