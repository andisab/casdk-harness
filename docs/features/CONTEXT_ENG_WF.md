# Context Engineering Workflow Specification

> **Created**: December 2025
> **Status**: Under refinement
> **Related**: [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md), [ORCHESTRATION_PATTERNS.md](../ORCHESTRATION_PATTERNS.md), [CONTEXT-GRAD-SPEC.md](./CONTEXT-GRAD-SPEC.md)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Stage 1: Objective Elicitation](#3-stage-1-objective-elicitation)
4. [Stage 2: Pattern & Resource Planning](#4-stage-2-pattern--resource-planning)
5. [Stage 3: Resource Generation](#5-stage-3-resource-generation)
6. [Stage 3b: Validation](#6-stage-3b-validation)
7. [Stage 4: CGF Handoff](#7-stage-4-cgf-handoff)
8. [Unified Schema: context_spec.json](#8-unified-schema-context_specjson)
9. [Implementation Checklist](#9-implementation-checklist)
10. [Appendices](#appendices)

---

## 1. Overview

This document defines a **Q&A-driven workflow** for context engineering, enabling the context-engineer agent to:

1. Accept a business or technical objective description from the user
2. Conduct structured Q&A to refine requirements and success metrics
3. Infer the appropriate agentic pattern and identify required resources
4. Generate all necessary context artifacts (agents, skills, commands, workflows)
5. Validate generated resources and transition to CGF optimization

### Relationship to Tech Lead Agent Pattern

This workflow mirrors the tech-lead agent's Q&A approach but focuses on **orchestration and context engineering** rather than task generation:

| Aspect | Tech Lead Agent | Context Engineer |
|--------|-----------------|------------------|
| **Input** | Feature specification (SPEC.md) | Business objective description |
| **Q&A Focus** | Requirements, scope, constraints | Coordination needs, success metrics, failure modes |
| **Output** | `task_list.json` | `context_spec.json` + generated resources |
| **Validation** | Specification completeness | Pattern applicability + resource correctness |
| **Handoff** | Main agent executes tasks | CGF optimizes generated resources |

### Integration Points

- **context-engineering plugin**: Provides templates and skills for resource generation
- **research-team plugin**: Provides on-demand research for best practices
- **ContextGrad Framework (CGF)**: Provides iterative testing and optimization

---

## 2. Architecture

### Single Agent Model with Skill Activation

The workflow uses the existing **context-engineer** agent enhanced with a new `orchestration-definition` skill, rather than a separate orchestration-architect agent.

**Rationale**:
- Simpler architecture - follows existing skill-activation pattern
- The context-engineer already handles all resource types (agents, skills, plugins, commands, hooks)
- Orchestration is a specialized capability that fits naturally as a skill

### Activation Methods

**Method 1: Config Substitution**
```bash
# Similar to tech-lead substitution in autonomous mode
CONTEXT_ENGINEERING_MODE=true
CONTEXT_ENGINEERING_PROMPT=src/harness/plugins/context-engineering/prompts/context-eng-qa.md
```

**Method 2: Slash Command**
```bash
/context-engineering "Build a code review pipeline with security and performance checks"
```

**Method 3: Natural Language Activation**
```
User: "Help me design an orchestration workflow for automated PR reviews"
→ context-engineer agent activates with orchestration-definition skill
```

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `orchestration-definition/` | `plugins/context-engineering/skills/` | Q&A workflow + pattern selection |
| `context-eng-qa.md` | `plugins/context-engineering/prompts/` | System prompt for Q&A mode |
| `context_spec_schema.json` | `plugins/context-engineering/specs/` | JSON Schema for validation |
| `validate-context-spec.md` | `plugins/context-engineering/commands/` | Validation command |

### orchestration-definition Skill Structure

The skill uses progressive disclosure with supporting files for pattern selection:

```
skills/orchestration-definition/
├── SKILL.md                      # Main skill (Q&A workflow, pattern heuristics)
├── heuristics.md                 # Pattern selection matrix + decision tree
├── examples/
│   ├── sequential-example.md     # Code review pipeline example
│   ├── hierarchical-example.md   # Feature development with tech lead
│   ├── broadcast-example.md      # Multi-perspective code analysis
│   └── event-driven-example.md   # Async PR processing queue
└── templates/
    ├── sequential-template.json  # Sequential pattern context_spec template
    ├── hierarchical-template.json
    ├── broadcast-template.json
    └── event-driven-template.json
```

**Progressive Disclosure**:
- **Level 1**: SKILL.md loads with core Q&A workflow and inline heuristics summary
- **Level 2**: heuristics.md loaded when pattern selection begins (Stage 2)
- **Level 3**: examples/ and templates/ loaded on-demand based on selected pattern

---

## 3. Stage 1: Objective Elicitation

**Purpose**: Conduct structured Q&A to understand the business objective and define success criteria.

### Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: OBJECTIVE ELICITATION                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT: User's business objective description                        │
│  ───────────────────────────────────────────                        │
│  Example: "I need an automated code review system that checks        │
│  security, performance, and code quality for all PRs"               │
│                                                                      │
│  PROCESS: Structured Q&A                                            │
│  ───────────────────────                                            │
│  1. Display progress: "Question 1/N"                                │
│  2. Ask one question at a time                                      │
│  3. Record answer and update session                                │
│  4. Repeat until all categories covered                             │
│  5. Summarize understanding and ask for approval                    │
│                                                                      │
│  OUTPUT: context_spec.json (objective section populated)            │
│  ─────────────────────────────────────────────────                  │
│  Signal: [SPEC_APPROVED]                                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Q&A Categories

The context-engineer asks questions across 5 categories (~20 questions total). Questions are adapted based on the objective type.

#### Category 1: Objective Understanding
1. What is the business problem you're trying to solve?
2. What would success look like? (measurable outcomes)
3. Who are the users of this system?
4. What triggers this workflow? (manual, automated, event-based)

#### Category 2: Coordination Needs
5. Do steps need to happen in a specific order?
6. Can some steps run in parallel?
7. Does one central entity need to coordinate specialists?
8. Are there multiple perspectives needed on the same input?

#### Category 3: Failure Modes
9. What happens if one step fails? (fail-fast vs continue)
10. Is human review required at any stage?
11. What are the timeout constraints?
12. How critical is this workflow? (production vs experimental)

#### Category 4: Resource Requirements
13. What existing agents/skills could be leveraged?
14. What new capabilities are needed?
15. What external services or APIs are involved?
16. What data sources are needed?

#### Category 5: Success Metrics
17. How will you measure success? (KPIs)
18. What accuracy/quality level is acceptable?
19. What latency is acceptable?
20. What cost constraints exist?

### Session Persistence

The Q&A session is persisted to allow resume after interruption:

```python
@dataclass
class ContextEngineeringSession:
    """Tracks Context Engineering Q&A session state."""

    # Base Q&A tracking
    started_at: str
    objective_hash: str          # Hash of initial objective
    total_questions: int = 0
    current_question: int = 0
    questions_asked: list[str] = field(default_factory=list)
    answers_received: list[str] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)

    # Status tracking
    status: str = "objective_gathering"
    # Values: objective_gathering | pattern_planning | resource_generation |
    #         validation | awaiting_confirmation | cgf_handoff | completed

    # Context engineering specific
    pattern_selected: str | None = None
    resources_identified: list[dict] = field(default_factory=list)
    resources_generated: list[str] = field(default_factory=list)
    validation_passed: bool = False
    cgf_ready: bool = False
```

### Completion Signal

When the user approves the objective summary:
```
[SPEC_APPROVED]
```

---

## 4. Stage 2: Pattern & Resource Planning

**Purpose**: Select the appropriate orchestration pattern and identify required resources.

> **Reference**: See [ORCHESTRATION_PATTERNS.md](../ORCHESTRATION_PATTERNS.md) for detailed specifications of all 8 orchestration patterns, including implementation examples and decision criteria.

### Pattern Selection Heuristics

Apply the following decision logic based on Q&A responses:

#### Pattern Selection Matrix

| Business Signal | Recommended Pattern | Rationale |
|-----------------|---------------------|-----------|
| "must happen in order", "pipeline", "stages", "depends on previous" | Sequential Pipeline | Strict dependencies require ordered execution |
| "multiple specialists", "coordinate", "delegate", "oversee" | Hierarchical Coordinator | Central authority needed to manage specialists |
| "get multiple opinions", "compare approaches", "consensus" | Broadcast/Consensus | Same input needs multiple perspectives |
| "async", "event-driven", "reactive", "queue", "decouple" | Event-driven Async | Loose coupling, high throughput requirements |
| Complex combinations with mixed signals | Hybrid Pipeline | Layer patterns (e.g., sequential stages with broadcast within) |

#### Decision Tree

```
START: What is the coordination requirement?
│
├─► Strict ordering between steps?
│   └─► YES → Sequential Pipeline
│       └─► Any step needs multiple perspectives?
│           └─► YES → Hybrid: Sequential + Broadcast
│
├─► Central authority coordinating specialists?
│   └─► YES → Hierarchical Coordinator
│       └─► Specialists work in parallel?
│           └─► YES → Hierarchical with parallel fanout
│
├─► Same input, multiple independent processors?
│   └─► YES → Broadcast/Consensus
│       └─► Need to aggregate results?
│           └─► YES → Broadcast with reducer
│
└─► Decoupled, event-based processing?
    └─► YES → Event-driven Async
        └─► Need guaranteed delivery?
            └─► YES → Event-driven with Redis Streams
```

### Resource Identification

After pattern selection, identify required resources:

1. **Existing Resources**: Query conventions-mcp and check `src/harness/agents/configs/`
2. **New Resources Needed**: Flag agents/skills/commands that must be created
3. **External Dependencies**: APIs, services, data sources

### Research Phase (Optional)

If domain knowledge is needed, invoke research-team plugin:

```
Agent: "Before proceeding, would you like me to research best practices
       for [domain]? This can help refine success metrics and patterns."

User: "Yes, research security scanning best practices for code review"

→ research-team plugin executes parallel research
→ Insights update context_spec.json goals section
```

### Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                STAGE 2: PATTERN & RESOURCE PLANNING                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT: context_spec.json with objective section                    │
│  ─────────────────────────────────────────────                      │
│                                                                      │
│  STEP 1: Apply Pattern Selection Heuristics                         │
│  ──────────────────────────────────────────                         │
│  - Analyze coordination signals from Q&A                            │
│  - Select primary pattern                                           │
│  - Identify hybrid needs                                            │
│                                                                      │
│  STEP 2: Identify Required Resources                                │
│  ───────────────────────────────────                                │
│  - Query existing agents via conventions-mcp                        │
│  - Map stages to agents (existing or new)                          │
│  - Identify skills, commands, workflows needed                      │
│                                                                      │
│  STEP 3: Research Phase (Optional)                                  │
│  ─────────────────────────────────                                  │
│  - If user requests, invoke research-team plugin                    │
│  - Gather best practices and patterns                               │
│  - Update goals and metrics                                         │
│                                                                      │
│  OUTPUT: context_spec.json (pattern + resources sections)           │
│  ───────────────────────────────────────────────────               │
│  Signal: [RESOURCES_PLANNED]                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Completion Signal

When resources are planned:
```
[RESOURCES_PLANNED]
```

---

## 5. Stage 3: Resource Generation

**Purpose**: Generate all required context artifacts using templates from the context-engineering plugin.

### Generation Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   STAGE 3: RESOURCE GENERATION                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  INPUT: context_spec.json with pattern + resources                  │
│  ─────────────────────────────────────────────                      │
│                                                                      │
│  FOR EACH resource in context_spec.resources:                       │
│  ────────────────────────────────────────────                       │
│                                                                      │
│    1. Load template from context-engineering plugin                 │
│       - subagent-template.md for agents                            │
│       - skill-template.md for skills                               │
│       - slash-command-template.md for commands                     │
│                                                                      │
│    2. Generate resource definition                                  │
│       - Apply objective-specific context                           │
│       - Set appropriate tools (least privilege)                    │
│       - Write discovery-optimized description                      │
│                                                                      │
│    3. Write to filesystem                                           │
│       - Agents: workspace/orchestration/agents/                    │
│       - Skills: workspace/orchestration/skills/                    │
│       - Commands: workspace/orchestration/commands/                │
│                                                                      │
│  THEN: Generate Test Cases                                          │
│  ───────────────────────────                                        │
│    - Create test_cases.json from success metrics                   │
│    - Write validation scripts                                       │
│    - Document expected inputs/outputs                              │
│                                                                      │
│  OUTPUT: Generated resources + tests                                │
│  ───────────────────────────────                                    │
│  Signals: [RESOURCES_GENERATED] + [TESTS_WRITTEN]                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Template Usage

The context-engineering plugin provides **generic templates**. The context-engineer agent generates **specific resources** tailored to the objective.

**Example: Generic vs Specific**

Generic template (`subagent-template.md`):
```yaml
---
name: agent-name
description: >
  [Domain] expert specializing in [specific capabilities].
  Use PROACTIVELY for [scenarios].
tools: [Minimal necessary set]
model: sonnet
---
```

Generated specific agent:
```yaml
---
name: security-scanner
description: >
  Security expert specializing in static code analysis and vulnerability detection.
  Use PROACTIVELY when reviewing code changes, analyzing PRs, or auditing codebases.

  Examples:
  <example>
  Context: User submits a PR with Python code changes
  user: "Review this PR for security issues"
  assistant: "I'll use the security-scanner agent to analyze the code for vulnerabilities."
  </example>
tools: Read, Grep, Glob, Bash(bandit:*), Bash(semgrep:*)
model: sonnet
---
You are a security specialist focusing on static code analysis...
```

### Test Case Generation

Generate test cases based on success metrics in `context_spec.json`:

```json
{
  "test_cases": [
    {
      "id": "tc-001",
      "name": "Simple Python PR - No Issues",
      "description": "Basic Python file change with no security vulnerabilities",
      "inputs": {
        "diff": "...",
        "files": ["app.py"]
      },
      "expected_output": {
        "issues_found": 0,
        "status": "passed"
      },
      "weight": 1.0,
      "success_metric": "accuracy_score"
    }
  ]
}
```

### Completion Signals

When resources are generated:
```
[RESOURCES_GENERATED]
```

When tests are written:
```
[TESTS_WRITTEN]
```

---

## 6. Stage 3b: Validation

**Purpose**: Validate generated resources before transitioning to CGF optimization.

### Validation Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                       STAGE 3b: VALIDATION                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  STEP 1: Schema Validation                                          │
│  ─────────────────────────                                          │
│  - Validate context_spec.json against JSON schema                  │
│  - Validate all agent definitions have required fields             │
│  - Validate workflow references existing agents                    │
│                                                                      │
│  STEP 2: Dry-Run Execution                                          │
│  ─────────────────────────                                          │
│  - Execute pattern with mock agents (if available)                 │
│  - Verify data flows correctly between stages                      │
│  - Check timeout and error handling                                │
│                                                                      │
│  STEP 3: Basic Test Execution                                       │
│  ────────────────────────────                                       │
│  - Run test cases from test_cases.json                            │
│  - Collect baseline metrics                                        │
│  - Document any failures                                           │
│                                                                      │
│  OUTPUT: validation_report.json                                     │
│  ─────────────────────────────                                      │
│  Signal: [VALIDATION_COMPLETE]                                      │
│                                                                      │
│  USER CONFIRMATION GATE                                             │
│  ──────────────────────────                                         │
│  "Validation complete. X/Y tests passed.                           │
│   Generated resources are ready for review.                        │
│   Would you like to:                                               │
│   1. Review and edit generated resources manually                  │
│   2. Proceed to CGF optimization testing                          │
│   3. Refine objectives and regenerate"                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Validation Report

```json
{
  "timestamp": "2025-12-19T10:30:00Z",
  "context_spec_version": "1.0.0",
  "schema_validation": {
    "passed": true,
    "errors": []
  },
  "resource_validation": {
    "agents_checked": 3,
    "agents_valid": 3,
    "skills_checked": 1,
    "skills_valid": 1
  },
  "dry_run": {
    "executed": true,
    "pattern": "sequential",
    "stages_completed": 3,
    "errors": []
  },
  "test_execution": {
    "total_tests": 6,
    "passed": 5,
    "failed": 1,
    "baseline_metrics": {
      "task_completion_rate": 0.83,
      "avg_latency_seconds": 45.2,
      "cost_per_run_usd": 0.24
    }
  }
}
```

### Completion Signal

When validation completes:
```
[VALIDATION_COMPLETE]
```

---

## 7. Stage 4: CGF Handoff

**Purpose**: Transition to ContextGrad Framework for iterative optimization.

### Prerequisites

Before CGF handoff:
1. `[VALIDATION_COMPLETE]` signal received
2. User has confirmed readiness to proceed
3. All critical test cases pass (or user accepts baseline)

### Handoff Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│                       STAGE 4: CGF HANDOFF                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  STEP 1: Create Optimization Branch                                 │
│  ──────────────────────────────────                                 │
│  git checkout -b optimize/[workflow-name]                          │
│                                                                      │
│  STEP 2: Prepare CGF Configuration                                  │
│  ─────────────────────────────────                                  │
│  - context_spec.json serves as goal definition                     │
│  - Success metrics map to CGF optimization targets                 │
│  - Test cases become CGF test suite                                │
│                                                                      │
│  STEP 3: Initialize CGF Run                                         │
│  ──────────────────────────                                         │
│  make optimize-workflow SPEC=context_spec.json                     │
│                                                                      │
│  Signal: [CGF_TESTING_STARTED]                                      │
│                                                                      │
│  → CGF takes over with DSPy/TextGrad optimization cycle            │
│  → Human review checkpoints at 80% threshold                       │
│  → Final approval before production merge                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### CGF Integration Points

The `context_spec.json` provides all data CGF needs:

| context_spec.json Section | CGF Usage |
|---------------------------|-----------|
| `goals.primary/secondary/anti_goals` | Optimization objectives |
| `success_metrics` | Target thresholds and weights |
| `test_cases` | Training and evaluation data |
| `resources.agents[]` | Resources to optimize |
| `infrastructure` | Execution environment config |

### Completion Signal

When CGF testing starts:
```
[CGF_TESTING_STARTED]
```

---

## 8. Unified Schema: context_spec.json

The `context_spec.json` schema merges:
- Pattern selection and workflow structure (from orchestration_spec.json)
- Goals and success metrics (from CGF goal-definition.yaml)
- Resource definitions and test cases

### Full Schema

```json
{
  "$schema": "context-spec-v1",

  "metadata": {
    "name": "code-review-pipeline",
    "description": "Multi-stage code review with security and performance analysis",
    "version": "1.0.0",
    "created": "2025-12-19T00:00:00Z",
    "objective_hash": "sha256:abc123...",
    "status": "draft"
  },

  "objective": {
    "business_description": "Automated code review for PRs that checks security, performance, and code quality",
    "success_criteria": [
      "All PRs reviewed within 5 minutes",
      "Security vulnerabilities detected with 95% accuracy",
      "False positive rate below 10%"
    ],
    "constraints": [
      "Must work with GitHub PRs",
      "Support Python, TypeScript, Go codebases"
    ],
    "users": ["developers", "security team"],
    "trigger": "PR opened or updated"
  },

  "goals": {
    "primary": [
      "Detect security vulnerabilities (SQL injection, XSS, secrets exposure)",
      "Identify performance bottlenecks (N+1 queries, large loops)",
      "Ensure code quality standards (linting, type coverage)"
    ],
    "secondary": [
      "Provide actionable fix suggestions",
      "Track improvement trends over time"
    ],
    "anti_goals": [
      "Do NOT block PRs without human review option",
      "Do NOT store code outside secure boundaries",
      "Do NOT report duplicate issues"
    ]
  },

  "pattern": {
    "type": "sequential",
    "variant": null,
    "selection_rationale": "Security must complete before performance analysis uses its results",
    "selection_signals": ["must happen in order", "depends on previous step"]
  },

  "stages": [
    {
      "name": "security-scan",
      "agent": "security-scanner",
      "agent_exists": false,
      "required": true,
      "timeout_seconds": 120,
      "inputs": ["code_diff", "file_paths"],
      "outputs": ["security_findings"],
      "success_criteria": ["No critical vulnerabilities missed"]
    },
    {
      "name": "performance-check",
      "agent": "python-expert",
      "agent_exists": true,
      "required": true,
      "timeout_seconds": 180,
      "inputs": ["code_diff", "security_findings"],
      "outputs": ["performance_findings"],
      "success_criteria": ["Identify N+1 queries, large allocations"]
    },
    {
      "name": "quality-review",
      "agent": "code-review-expert",
      "agent_exists": true,
      "required": false,
      "timeout_seconds": 120,
      "inputs": ["code_diff", "security_findings", "performance_findings"],
      "outputs": ["quality_findings", "summary_report"],
      "success_criteria": ["Synthesize findings into actionable report"]
    }
  ],

  "resources": {
    "agents": [
      {
        "name": "security-scanner",
        "exists": false,
        "template": "subagent-template.md",
        "path": "workspace/orchestration/agents/security-scanner.md",
        "specification": {
          "description": "Security vulnerability scanner for code review",
          "model": "sonnet",
          "tools": ["Read", "Grep", "Glob", "Bash(bandit:*)", "Bash(semgrep:*)"]
        }
      },
      {
        "name": "python-expert",
        "exists": true,
        "path": "src/harness/agents/configs/python-expert.md",
        "modifications_needed": []
      },
      {
        "name": "code-review-expert",
        "exists": true,
        "path": "src/harness/agents/configs/code-review-expert.md",
        "modifications_needed": []
      }
    ],
    "skills": [],
    "commands": [
      {
        "name": "review-pr",
        "exists": false,
        "template": "slash-command-template.md",
        "path": "workspace/orchestration/commands/review-pr.md"
      }
    ],
    "workflows": []
  },

  "test_cases": [
    {
      "id": "tc-001",
      "name": "Simple Python PR - No Issues",
      "description": "Basic Python file change with no vulnerabilities",
      "inputs": {
        "diff": "...",
        "files": ["app.py"]
      },
      "expected_output": {
        "security_issues": 0,
        "performance_issues": 0,
        "status": "passed"
      },
      "weight": 1.0
    },
    {
      "id": "tc-002",
      "name": "SQL Injection Vulnerability",
      "description": "PR with SQL injection vulnerability that should be caught",
      "inputs": {
        "diff": "...",
        "files": ["db_handler.py"]
      },
      "expected_output": {
        "security_issues": 1,
        "issue_type": "sql_injection",
        "status": "blocked"
      },
      "weight": 1.5
    }
  ],

  "success_metrics": {
    "task_completion_rate": 0.95,
    "accuracy_score": 0.90,
    "max_latency_seconds": 300,
    "max_cost_per_run_usd": 0.50,
    "custom_metrics": {
      "false_positive_rate": 0.10,
      "critical_vuln_detection": 0.99
    }
  },

  "failure_mode": "continue_on_optional",
  "global_timeout_seconds": 600,

  "infrastructure": {
    "requires_redis": false,
    "requires_containers": false,
    "estimated_resources": {
      "memory_mb": 2048,
      "cpu_cores": 2
    }
  },

  "qa_session": {
    "started_at": "2025-12-19T10:00:00Z",
    "completed_at": "2025-12-19T10:15:00Z",
    "questions_asked": 18,
    "conversation_hash": "sha256:def456..."
  }
}
```

### Status Values

The `metadata.status` field tracks workflow progress:

| Status | Description |
|--------|-------------|
| `draft` | Initial creation, Q&A in progress |
| `planned` | Pattern and resources identified |
| `generated` | Resources generated, awaiting validation |
| `validated` | Validation passed, ready for CGF |
| `cgf_testing` | CGF optimization in progress |
| `production` | Approved and deployed |

---

## 9. Implementation Checklist

### New Components to Create

#### orchestration-definition Skill
- [ ] Create `skills/orchestration-definition/SKILL.md`
- [ ] Define Q&A question templates
- [ ] Create `heuristics.md` with pattern selection matrix + decision tree
- [ ] Create `examples/sequential-example.md` (code review pipeline)
- [ ] Create `examples/hierarchical-example.md` (feature development)
- [ ] Create `examples/broadcast-example.md` (multi-perspective analysis)
- [ ] Create `examples/event-driven-example.md` (async processing)
- [ ] Create `templates/sequential-template.json`
- [ ] Create `templates/hierarchical-template.json`
- [ ] Create `templates/broadcast-template.json`
- [ ] Create `templates/event-driven-template.json`

#### context-eng-qa Prompt
- [ ] Create `prompts/context-eng-qa.md`
- [ ] Mirror tech-lead-agent Q&A structure
- [ ] Add orchestration-specific sections
- [ ] Define completion signals

#### context_spec Schema
- [ ] Create `specs/context_spec_schema.json`
- [ ] Add JSON Schema validation rules
- [ ] Document pattern-specific extensions

#### validate-context-spec Command
- [ ] Create `commands/validate-context-spec.md`
- [ ] Schema validation implementation
- [ ] Dry-run capability
- [ ] Test case execution

#### Session Management
- [ ] Define `ContextEngineeringSession` dataclass
- [ ] Add persistence (context_session.json)
- [ ] Implement resume capability

### Plugin Updates
- [ ] Update plugin.json with new components
- [ ] Add prompts directory reference
- [ ] Add specs directory reference

### Integration
- [ ] Add CGF handoff protocol to `harness.autonomous`
- [ ] Create `make context-engineering` target
- [ ] Update documentation

---

## Appendices

### Appendix A: Pattern-Specific Extensions

#### Hierarchical Pattern Extension
```json
{
  "pattern": {
    "type": "hierarchical",
    "coordinator": "tech-lead-agent",
    "specialists": ["python-expert", "security-expert", "sdet-expert"]
  },
  "delegation_strategy": "parallel",
  "aggregation": "coordinator_synthesizes"
}
```

#### Broadcast Pattern Extension
```json
{
  "pattern": {
    "type": "broadcast",
    "perspectives": ["security-expert", "performance-expert", "maintainability-expert"]
  },
  "consensus_mode": "majority",
  "minimum_responses": 2
}
```

#### Event-Driven Pattern Extension
```json
{
  "pattern": {
    "type": "event_driven",
    "event_source": "redis_stream",
    "consumer_group": "review-workers"
  },
  "events": [
    {"name": "code_pushed", "handler": "security-scanner"},
    {"name": "security_passed", "handler": "performance-checker"}
  ]
}
```

### Appendix B: Signal Reference

| Signal | Stage | Meaning |
|--------|-------|---------|
| `[QUESTIONS_PLANNED: N]` | 1 | Q&A session starting with N questions |
| `[SPEC_APPROVED]` | 1 | User approved objective summary |
| `[RESOURCES_PLANNED]` | 2 | Pattern selected, resources identified |
| `[RESOURCES_GENERATED]` | 3 | All resources written to filesystem |
| `[TESTS_WRITTEN]` | 3 | Test cases generated |
| `[VALIDATION_COMPLETE]` | 3b | Validation finished |
| `[CGF_TESTING_STARTED]` | 4 | CGF optimization initiated |

### Appendix C: Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT ENGINEERING WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Build an automated PR review system"                                │
│                    │                                                         │
│                    ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 1: Objective Elicitation                                       │   │
│  │ - Q&A across 5 categories (~20 questions)                           │   │
│  │ - Session persisted to context_session.json                         │   │
│  │ → [SPEC_APPROVED]                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                         │
│                    ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 2: Pattern & Resource Planning                                 │   │
│  │ - Apply pattern selection heuristics                                │   │
│  │ - Identify existing vs new resources                                │   │
│  │ - Optional: research-team for best practices                        │   │
│  │ → [RESOURCES_PLANNED]                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                         │
│                    ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 3: Resource Generation                                         │   │
│  │ - Generate agents, skills, commands using templates                 │   │
│  │ - Generate test cases from success metrics                          │   │
│  │ → [RESOURCES_GENERATED] + [TESTS_WRITTEN]                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                         │
│                    ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 3b: Validation                                                 │   │
│  │ - Schema validation                                                 │   │
│  │ - Dry-run pattern execution                                         │   │
│  │ - Execute basic test cases                                          │   │
│  │ → [VALIDATION_COMPLETE]                                             │   │
│  │                                                                      │   │
│  │ ══════════════════════════════════════════════════════════════════ │   │
│  │ USER CONFIRMATION GATE: "Ready for CGF testing?"                    │   │
│  │ ══════════════════════════════════════════════════════════════════ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                         │
│                    ▼ (user confirms)                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 4: CGF Handoff                                                 │   │
│  │ - Create optimize/[workflow-name] branch                            │   │
│  │ - Initialize CGF optimization run                                   │   │
│  │ → [CGF_TESTING_STARTED]                                             │   │
│  │                                                                      │   │
│  │ CGF takes over:                                                     │   │
│  │ - DSPy compilation phase                                            │   │
│  │ - TextGrad refinement phase                                         │   │
│  │ - Human review at 80% threshold                                     │   │
│  │ - Final approval → merge to main                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

After completing this specification:
1. See [CONTEXT-GRAD-IMP.md](./CONTEXT-GRAD-IMP.md) "Context Spec Validation" for detailed validation implementation
2. Pattern inference integrated into orchestration-definition skill (Phase 2 in roadmap)
3. Implement components per checklist above
4. Track progress in [ORCHESTRATION_ROADMAP.md](../ORCHESTRATION_ROADMAP.md)
