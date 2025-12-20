# Agentic Workflow Examples

> **Created**: December 2025
> **Status**: Planning
> **Related**: [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md), [CONTEXT_ENG_WF.md](./CONTEXT_ENG_WF.md)

---

## Overview

This document defines the structure and taxonomy for agentic workflow examples. Examples demonstrate real-world orchestration patterns and serve as templates for users building their own workflows.

**Purpose**:
- Provide working examples for each orchestration pattern
- Organize by business domain for easy discovery
- Include complete `context_spec.json` files as starting points

---

## Directory Structure

```
examples/
├── README.md                      # Index and selection guide
├── development/                   # Code-focused workflows
│   ├── code-review-pipeline/
│   │   ├── context_spec.json
│   │   ├── agents/
│   │   └── workflow.md
│   ├── feature-development/
│   └── refactoring-workflow/
├── research/                      # Information gathering
│   ├── research-synthesis/
│   ├── competitive-analysis/
│   └── documentation-generation/
├── content/                       # Content production
│   ├── content-pipeline/
│   ├── translation-workflow/
│   └── review-and-publish/
└── operations/                    # DevOps/infrastructure
    ├── deployment-pipeline/
    ├── incident-response/
    └── infrastructure-review/
```

---

## Pattern to Example Mapping

| Pattern | Examples | Domain |
|---------|----------|--------|
| Sequential | code-review-pipeline, deployment-pipeline | Development, Operations |
| Hierarchical | feature-development, incident-response | Development, Operations |
| Broadcast | competitive-analysis, infrastructure-review | Research, Operations |
| Event-driven | content-pipeline | Content |

---

## Domain Categories

### Development
Code-focused workflows for software engineering teams.

| Example | Pattern | Description |
|---------|---------|-------------|
| code-review-pipeline | Sequential | Multi-stage PR review (security → performance → quality) |
| feature-development | Hierarchical | Tech lead coordinates specialist agents |
| refactoring-workflow | Sequential | Analysis → planning → execution → verification |

### Research
Information gathering and synthesis workflows.

| Example | Pattern | Description |
|---------|---------|-------------|
| research-synthesis | Hierarchical | Coordinator aggregates findings from specialists |
| competitive-analysis | Broadcast | Multiple analysts evaluate same competitor |
| documentation-generation | Sequential | Research → draft → review → publish |

### Content
Content production and publishing workflows.

| Example | Pattern | Description |
|---------|---------|-------------|
| content-pipeline | Event-driven | Async content processing queue |
| translation-workflow | Broadcast | Parallel translation to multiple languages |
| review-and-publish | Sequential | Edit → review → approve → publish |

### Operations
DevOps and infrastructure workflows.

| Example | Pattern | Description |
|---------|---------|-------------|
| deployment-pipeline | Sequential | Build → test → stage → deploy |
| incident-response | Hierarchical | Incident commander coordinates responders |
| infrastructure-review | Broadcast | Multiple experts review same infrastructure |

---

## Example Structure

Each example directory contains:

```
example-name/
├── context_spec.json      # Complete context specification
├── agents/                # Agent definitions (if new agents needed)
│   └── specialist.md
├── workflow.md            # Human-readable workflow description
└── test_cases.json        # Test cases for validation
```

---

## Selection Guide

### By Pattern Type

**Choose Sequential when**:
- Steps must happen in order
- Each step depends on previous output
- Pipeline/stages metaphor fits

**Choose Hierarchical when**:
- Central coordinator needed
- Multiple specialists with different expertise
- Results need synthesis/aggregation

**Choose Broadcast when**:
- Same input needs multiple perspectives
- Consensus or comparison needed
- Independent parallel processing

**Choose Event-driven when**:
- Async/decoupled processing required
- High throughput needed
- Loose coupling between components

### By Use Case

1. Identify your business domain (Development, Research, Content, Operations)
2. Find a similar use case in that domain
3. Review the `context_spec.json` to understand the pattern
4. Adapt agents, stages, and metrics for your needs

---

## Implementation Checklist

- [ ] Create `examples/` directory structure
- [ ] Create `examples/README.md` index
- [ ] Implement `development/code-review-pipeline/` example
- [ ] Implement `development/feature-development/` example
- [ ] Implement `research/research-synthesis/` example
- [ ] Implement `operations/deployment-pipeline/` example
- [ ] Add remaining examples as needed

---

## Integration with Context Engineering Workflow

Examples serve as references during Stage 2 (Pattern & Resource Planning):

1. User describes objective
2. Context engineer identifies pattern via heuristics
3. **Loads relevant example** from this directory
4. Uses example as template for `context_spec.json` generation

The `orchestration-definition` skill references these examples in its `examples/` directory.
