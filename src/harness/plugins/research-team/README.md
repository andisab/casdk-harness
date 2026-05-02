# Research Team Plugin

Multi-agent research system for comprehensive topic investigation with parallel execution and professional report synthesis.

## Overview

The Research Team plugin provides a coordinated multi-agent system designed to conduct thorough research on complex topics. It breaks research into distinct subtopics, investigates them in parallel using multiple specialized agents, and synthesizes findings into professional reports.

## Features

- **Multi-Agent Orchestration**: Lead coordinator breaks topics into 2-4 subtopics and manages parallel research
- **Parallel Research Execution**: Multiple researchers investigate simultaneously for 4x speedup
- **Smart Source Routing**: Automatic selection of optimal information sources (Context7, WebSearch, Codebase)
- **Context7 Integration**: Direct access to library/framework documentation for technical research
- **Web Research**: WebSearch for industry practices, patterns, trends, and comparisons
- **Codebase Analysis**: Local code exploration for internal project research
- **Professional Reports**: Synthesized findings with citations and proper formatting
- **CGF Output Mode**: Structured YAML output for optimization pipeline integration
- **Joplin Integration**: Optional markdown formatting optimized for Joplin note-taking
- **Context Isolation**: Each researcher operates independently with focused context
- **File-Based Coordination**: Researchers save findings, report-writer synthesizes

## Installation

```bash
/plugin install research-team
```

Or from marketplace:
```bash
/plugin install research-team@swe-marketplace
```

## Components

### Agents

#### 1. lead-research-coordinator
**Role**: Orchestrator
**Model**: Sonnet
**Tools**: Task

Coordinates the entire research workflow:
- Analyzes user research requests
- Breaks topics into 2-4 distinct subtopics
- Spawns researcher subagents in parallel
- Coordinates report synthesis
- Provides completion notifications

**Trigger**: Automatically activated for complex research requests

#### 2. research-specialist
**Role**: Information Gatherer with Smart Source Routing
**Model**: Sonnet
**Tools**: WebSearch, Write, Read, Glob, Grep, Context7 (resolve-library-id, query-docs)

Conducts focused research with intelligent source selection:
- **Context7**: Used for library/framework documentation (FastAPI, Kubernetes, React, etc.)
- **WebSearch**: Used for industry practices, patterns, trends (3-7 queries per subtopic)
- **Codebase Analysis**: Used for local code exploration (Glob, Grep, Read)
- Extracts findings from authoritative sources
- Saves concise summaries (3-4 paragraphs) in standard or CGF format
- Includes URLs, library IDs, and citations

**Source Routing Logic**:
- Detects library/framework names in topic → Uses Context7 first
- Detects practice/pattern keywords → Uses WebSearch
- Detects codebase references → Uses local exploration
- Multiple sources combined when appropriate

**Output Location**: `/workspace/temp/research/notes/`

**Output Modes**:
- **Standard**: Markdown prose (default)
- **CGF**: Structured YAML for optimization pipeline

#### 3. research-report-writer
**Role**: Report Synthesizer
**Model**: Sonnet
**Tools**: Glob, Read, Write, Skill

Creates comprehensive summary reports:
- Reads all research notes from files
- Synthesizes findings into coherent narrative
- Maintains citations from original research
- Uses joplin-research skill when Joplin mentioned
- Saves final reports (500-800 words)

**Output Location**: `~/Documents/ClaudeResearch/reports/`

### Skills

#### joplin-research
Comprehensive markdown formatting guidelines for research artifacts:
- Technical rundowns and surveys
- Book and article summaries
- Research notes
- Optimized for Joplin note-taking app with custom CSS

**Trigger**: Automatically activates when user mentions "Joplin"

### Patterns

#### multi-agent-research
Documents the orchestration pattern:
- Parallel execution architecture
- File-based coordination
- Context isolation strategy
- Usage guidelines and best practices

#### parallel-research-workflow
Documents the workflow:
- Phase-by-phase execution
- File structure and organization
- Timing and performance metrics
- Quality assurance checks

## Usage

### Basic Research Request

```
User: Research the latest developments in quantum computing

Lead Coordinator:
"Researching 4 areas: hardware/qubits, algorithms/applications,
industry players/investments, and challenges/timeline. Spawning researchers."

[Spawns 4 researcher subagents in parallel]
[Each conducts 3-7 WebSearch queries on their subtopic]
[Each saves findings to ~/Documents/ClaudeResearch/research_notes/]
[All complete in 2-5 minutes]

[Spawns report-writer subagent]
[Report-writer reads all notes and creates synthesis]
[Saves to ~/Documents/ClaudeResearch/reports/]

"Research complete. Report saved to
~/Documents/ClaudeResearch/reports/quantum_computing_summary_20251117.txt"
```

### With Joplin Formatting

```
User: Research electric vehicles for my Joplin notes

[Same workflow as above, but...]
[Report-writer loads joplin-research skill]
[Output format changes to markdown with proper formatting]

"Research complete. Report saved to
~/Documents/ClaudeResearch/reports/electric_vehicles_summary_20251117.md"
```

### Library/Framework Research (Context7)

```
User: Research FastAPI async dependency injection patterns

Lead Coordinator:
"Library detected: FastAPI. Using DOCS scope for Context7 documentation.
Researching: dependency injection basics, async patterns, best practices."

[Spawns researchers with Scope: DOCS]
[Researchers use Context7 (resolve-library-id → query-docs) as primary source]
[WebSearch supplements with industry patterns]
[Findings include library IDs and doc references]

"Research complete. Report saved to
/workspace/temp/research/reports/fastapi_async_di_summary.md"
```

### CGF Pipeline Integration

```
# Called by CGF orchestrator with output_mode: cgf
Orchestrator prompt: "Research Python async programming patterns.
Scope: DOCS
output_mode: cgf

Focus on competencies needed for an async programming expert agent."

[Researcher produces structured YAML output]
[Output includes: key_competencies, edge_cases, common_mistakes]
[Format designed for test case generation]

Output: /workspace/temp/research/notes/python_async_findings.yaml
```

## Source Routing

The research-specialist uses intelligent source routing to select optimal information sources.

### Scope Types

| Scope | Primary Source | When to Use |
|-------|---------------|-------------|
| **EXTERNAL** | WebSearch | General knowledge, trends, comparisons |
| **INTERNAL** | Codebase (Glob/Grep/Read) | Local implementation questions |
| **MIXED** | Codebase + WebSearch | Comparison to best practices |
| **DOCS** | Context7 + WebSearch | Library/framework documentation |

### Library Detection

When these technologies are mentioned, DOCS scope is used automatically:

| Category | Technologies |
|----------|--------------|
| **Python** | FastAPI, Django, Flask, pandas, numpy, SQLAlchemy, Pydantic, pytest |
| **JavaScript** | React, Vue, Next.js, Express, Axios, TypeScript |
| **Infrastructure** | Kubernetes, Docker, Terraform, Helm, Ansible |
| **Databases** | PostgreSQL, MongoDB, Redis, Elasticsearch |
| **Cloud** | AWS SDK, Google Cloud, Azure SDK |

### Context7 Usage

Context7 provides authoritative library documentation:

```
1. resolve-library-id(libraryName="fastapi", query="async dependency injection")
   → Returns: /tiangolo/fastapi

2. query-docs(libraryId="/tiangolo/fastapi", query="dependency injection async")
   → Returns: Official documentation on async DI patterns
```

## Output Modes

### Standard Mode (Default)

Markdown prose suitable for human reading:

```markdown
# FastAPI Async Patterns

FastAPI provides excellent support for async programming...

## Key Sources
- FastAPI Docs: Async dependencies (Context7)
- Real Python: Best practices (WebSearch)

## Summary
[Conclusions and recommendations]
```

### CGF Mode

Structured YAML for optimization pipeline:

```yaml
topic: "FastAPI async programming"
source_mix:
  context7: 60%
  websearch: 40%

key_competencies:
  - name: "Async Dependency Injection"
    importance: high
    positive_indicators:
      - "Uses async def for async dependencies"
    test_scenarios:
      - "Database connection with async context manager"

edge_cases:
  - scenario: "Nested async dependencies"
    expected_handling: "Use proper dependency resolution order"
```

See `templates/cgf-findings-template.yaml` for full schema.

## File Structure

After running research, you'll find:

```
~/Documents/ClaudeResearch/
├── research_notes/              # Intermediate findings
│   ├── quantum_hardware_qubits.md
│   ├── quantum_algorithms_apps.md
│   ├── quantum_industry_investments.md
│   └── quantum_challenges_timeline.md
└── reports/                     # Final synthesized reports
    └── quantum_computing_summary_20251117.txt
```

## Configuration

### Output Directory

Default: `~/Documents/ClaudeResearch/`

To use a different location, the agents would need to be modified (advanced users only).

### Model Selection

All agents default to `sonnet` for high-quality output. This can be changed per-use by specifying model in agent invocation.

### Research Depth

- Number of subtopics: 2-4 (configured by lead coordinator based on topic complexity)
- WebSearch queries per researcher: 3-7
- Research note length: 3-4 paragraphs per researcher
- Final report length: 500-800 words (adjustable in report-writer prompt)

## Use Cases

### ✅ Excellent For

- **Market Research**: Investigate competitors, trends, technology, regulations
- **Technical Comparisons**: Compare tools on features, pricing, performance, ecosystem
- **Academic Research**: Explore history, current state, future directions, applications
- **Competitive Analysis**: Product features, market position, customer sentiment, financials
- **Technology Surveys**: Overview multiple tools/frameworks in a space

### ❌ Not Suitable For

- Simple factual queries (single WebSearch sufficient)
- Real-time interaction with user required
- Topics with insufficient web information
- Highly specialized topics needing expert knowledge unavailable online

## Performance

### Timing

| Phase | Duration |
|-------|----------|
| Analysis | < 5 seconds |
| Research (parallel) | 2-5 minutes |
| Synthesis | 1-2 minutes |
| **Total** | **3-7 minutes** |

### Speedup

- **Parallel (4 researchers)**: 3-7 minutes
- **Sequential (4 researchers)**: 12-28 minutes
- **Improvement**: 4x faster

## Examples

### Example 1: Technology Research

**Request**: "Research Python web frameworks"

**Subtopics**:
- Django features and ecosystem
- Flask flexibility and use cases
- FastAPI performance and modern features
- Framework comparison and selection criteria

**Output**: Comprehensive comparison with recommendations

### Example 2: Market Research

**Request**: "Research the AI chip market"

**Subtopics**:
- Major players (NVIDIA, AMD, Intel, startups)
- Market size and growth projections
- Technology trends (inference vs training chips)
- Supply chain and manufacturing

**Output**: Market overview with key insights

### Example 3: Academic Topic

**Request**: "Research neural architecture search for Joplin"

**Subtopics**:
- NAS methodology and algorithms
- Key papers and breakthroughs
- Practical applications and results
- Tools and frameworks

**Output**: Markdown-formatted research summary for Joplin

## Troubleshooting

### No Research Notes Found

**Symptom**: Report-writer can't find files
**Solution**:
- Ensure `~/Documents/ClaudeResearch/research_notes/` exists
- Check researchers actually saved files
- Verify file permissions

### Poor Report Quality

**Symptom**: Report lacks depth or citations
**Solution**:
- Verify researchers ran 3-7 WebSearch queries each
- Check research notes include URLs
- Ensure report-writer read all files

### Slow Execution

**Symptom**: Takes > 10 minutes
**Solution**:
- Verify researchers spawned in parallel (not sequential)
- Check WebSearch API availability
- Reduce number of queries per researcher

### Missing Joplin Formatting

**Symptom**: Plain text instead of markdown
**Solution**:
- Ensure user mentioned "Joplin" in original request
- Verify joplin-research skill is installed
- Check report-writer's skill activation logic

## Best Practices

### For Users

1. **Be Specific**: State research topic and desired depth clearly
2. **Mention Joplin**: If you want markdown, say "Joplin" in request
3. **Allow Time**: Expect 3-7 minutes for completion
4. **Check Output**: Verify files in `~/Documents/ClaudeResearch/reports/`

### For Developers

1. **Maintain Parallelism**: Never make researchers execute sequentially
2. **Validate Paths**: Ensure directory structure exists before use
3. **Test End-to-End**: Run complete workflow from request to report
4. **Monitor Quality**: Verify WebSearch usage and citation preservation
5. **Update Prompts**: Adjust subtopic decomposition logic as needed

## Roadmap

### Completed (v1.1.0)

- [x] Context7 integration for library documentation
- [x] Smart source routing (Context7, WebSearch, Codebase)
- [x] CGF output mode for optimization pipeline
- [x] DOCS scope for documentation-focused research
- [x] CGF findings template schema

### Potential Future Enhancements

- [ ] Support for custom output directories
- [ ] Configurable research depth (light/standard/deep)
- [ ] Integration with additional note-taking apps
- [ ] Export to multiple formats (PDF, HTML, DOCX)
- [ ] Iterative research with user feedback loop
- [ ] Research archiving and versioning
- [ ] Cross-research citation linking
- [ ] Research template library

## Contributing

To contribute improvements:

1. Test changes thoroughly with end-to-end research workflows
2. Maintain backward compatibility with existing file structure
3. Update documentation for any prompt or workflow changes
4. Follow agent frontmatter conventions for metadata
5. Preserve parallel execution architecture

## License

MIT License - See repository root for details

## Support

For issues or questions:
- Check pattern documentation in `patterns/`
- Review troubleshooting section above
- Open issue in repository
- Reference agent prompts for implementation details

## Version

**Current Version**: 1.1.0
**Status**: Stable
**Last Updated**: 2026-01-14

### Changelog

**v1.1.0** (2026-01-14)
- Added Context7 integration for library/framework documentation
- Implemented smart source routing (Context7, WebSearch, Codebase)
- Added CGF output mode for optimization pipeline integration
- Added DOCS scope for documentation-focused research
- Created CGF findings template schema
- Updated lead-research-coordinator with scope guidance

**v1.0.0** (2025-11-17)
- Initial release with multi-agent research system
- Parallel execution with WebSearch
- Joplin integration for formatted output
