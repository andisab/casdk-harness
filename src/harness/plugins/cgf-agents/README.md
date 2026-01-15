# CGF Agents Plugin

CGF (Claude Gradient Feedback) pipeline orchestration for optimizing context-engineering resources through agentic workflows.

## Overview

This plugin provides the orchestration layer for the CGF optimization framework. It coordinates:

- **Research** - Domain knowledge gathering via research-team plugin
- **Test Generation** - Creating evaluation test suites (M3)
- **Optimization** - Running DSPy MIPROv2 or TextGrad TGD
- **Evaluation** - Assessing results and recommending actions (M4)

## Components

### Agents

| Agent | Purpose |
|-------|---------|
| `cgf-orchestrator` | Pipeline coordinator with state machine |
| `cgf-research-lead` | Competency-focused research coordinator (M2) |
| `cgf-criteria-synthesizer` | Research findings to eval_criteria.yaml (M2) |
| `cgf-test-architect` | Criteria-to-tests transformation (M3) |
| `cgf-test-validator` | Test suite validation and coverage analysis (M3) |

### Skills

| Skill | Usage |
|-------|-------|
| `cgf-optimize` | `/cgf-optimize <resource> <goal> [--review]` |

### Commands

| Command | Usage |
|---------|-------|
| `/cgf optimize` | Start optimization run |
| `/cgf status` | Check run status |
| `/cgf resume` | Resume from checkpoint |
| `/cgf abort` | Cancel current run |
| `/cgf proceed` | Continue from checkpoint (review mode) |
| `/cgf edit` | Mark artifact as edited |

## Quick Start

### Basic Optimization

```bash
# Via Makefile
make cgf-optimize RESOURCE=python-expert GOAL="async programming"

# Via skill
/cgf-optimize python-expert async programming

# Via command
/cgf optimize python-expert async programming
```

### With Human Review

```bash
make cgf-optimize-review RESOURCE=typescript-expert GOAL="error handling"
```

Review mode pauses at checkpoints:
- After RESEARCH phase (eval_criteria.yaml)
- After TEST_GEN phase (test_suite.yaml)
- After EVALUATE phase (review report)

## Pipeline States

```
INIT → RESEARCH → [CHECKPOINT_RESEARCH] → TEST_GEN → [CHECKPOINT_TEST_GEN]
                                                              ↓
COMPLETE ← FINALIZE ← [CHECKPOINT_EVALUATE] ← EVALUATE ← OPTIMIZE
```

| State | Purpose |
|-------|---------|
| INIT | Parse request, create workspace |
| RESEARCH | Gather domain knowledge |
| TEST_GEN | Generate test suite |
| OPTIMIZE | Run DSPy/TextGrad optimization |
| EVALUATE | Assess results |
| FINALIZE | Accept/Refine/Reject |
| COMPLETE | Terminal state |

Checkpoint states (CHECKPOINT_*) only entered when `--review` flag is set.

## Workspace Structure

All runs create a workspace at `workspace/{resource_id}/`:

```
workspace/{resource_id}/
├── run_state.json           # State for resume
├── run_config.yaml          # Configuration
├── research/
│   ├── notes/               # Research findings
│   └── eval_criteria.yaml   # Synthesized criteria
├── tests/
│   ├── test_suite.yaml      # Test cases
│   └── coverage_report.md   # Coverage analysis
├── {resource_id}-orig.md    # Original resource
├── {resource_id}-v{N}.md    # Optimized versions
└── reviews/
    └── v{N}_review.md       # Evaluation reports
```

## Resource Types

The orchestrator supports optimizing any context-engineering resource:

| Type | Strategy | Example |
|------|----------|---------|
| agent | prompt_optimization | `python-expert` |
| skill | trigger_optimization | `joplin-research` |
| command | schema_optimization | `create-agent` |
| mcp | schema_optimization | `context7` |
| workflow | workflow_optimization | deployment flows |
| hook | trigger_optimization | pre-commit hooks |

## Makefile Targets

```bash
make cgf-optimize RESOURCE=x GOAL="y"   # Start optimization
make cgf-optimize-review RESOURCE=x GOAL="y"  # With checkpoints
make cgf-status                          # Show status
make cgf-clean                           # Remove state files
make cgf-reset                           # Remove all workspaces
```

## Resume Capability

Optimization runs can be resumed from any state:

```bash
# If interrupted, simply run again
make cgf-optimize RESOURCE=python-expert GOAL="async programming"

# Or explicitly resume
/cgf resume python-expert
```

The orchestrator reads `run_state.json` and continues from the current state.

## Configuration

Run configuration is stored in `run_config.yaml`:

```yaml
resource:
  path: "src/harness/agents/configs/dev-python-expert.md"
  type: agent
  id: python-expert
  optimization_goal: "async programming"

strategy: prompt_optimization
optimizer: dspy  # or textgrad

options:
  max_iterations: 10
  early_stopping_threshold: 0.01
  review_mode: false
```

## Schemas

JSON schemas are provided for validation:

- `schemas/run_state.schema.json` - Run state persistence
- `schemas/eval_criteria.schema.json` - Evaluation criteria
- `schemas/test_suite.schema.json` - Test suite structure (M3)

## Development Status

**M1 Implementation** ✅:
- Orchestrator agent with state machine
- Run state management
- CLI integration

**M2 Implementation** ✅:
- cgf-research-lead agent - Competency-focused research coordination
- cgf-criteria-synthesizer agent - Research-to-criteria transformation
- Per-resource-type criteria templates (agent, skill, command)
- Integration with research-team plugin researchers

**M3 Implementation** ✅:
- cgf-test-architect agent - Generates test suites from eval_criteria.yaml
- cgf-test-validator agent - Validates test suite quality and coverage
- Per-resource-type test templates (agent, skill, command)
- test_suite.schema.json for validation
- Orchestrator TEST_GEN phase integration

**Future Milestones**:
- M4: Result Evaluator agent (cgf-result-evaluator)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  cgf-orchestrator                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  INIT    │→ │ RESEARCH │→ │ TEST_GEN │→ │OPTIMIZE │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                     │              │             │       │
│                     ▼              ▼             ▼       │
│               ┌──────────┐  ┌──────────┐  ┌─────────┐   │
│               │ research │  │   tests/ │  │  CLI    │   │
│               │  /notes/ │  │test_suite│  │optimize │   │
│               └──────────┘  └──────────┘  └─────────┘   │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ EVALUATE │→ │ FINALIZE │→ │ COMPLETE │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│       │                                                  │
│       ▼                                                  │
│  ┌──────────┐                                           │
│  │ reviews/ │                                           │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

### RESEARCH Phase Detail (M2)

```
cgf-orchestrator
      │
      ▼ (spawn)
┌─────────────────────────────────────────────────────────┐
│              cgf-research-lead                           │
│                                                          │
│  1. Decompose goal into competency aspects               │
│  2. Auto-detect scope (DOCS/EXTERNAL/INTERNAL/MIXED)    │
│  3. Spawn 2-4 parallel researchers                       │
│                                                          │
│     ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│     │ researcher │  │ researcher │  │ researcher │     │
│     │  (aspect1) │  │  (aspect2) │  │  (aspect3) │     │
│     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘     │
│           │               │               │             │
│           ▼               ▼               ▼             │
│     *_findings.yaml *_findings.yaml *_findings.yaml     │
└─────────────────────────────────────────────────────────┘
      │
      ▼ (spawn)
┌─────────────────────────────────────────────────────────┐
│          cgf-criteria-synthesizer                        │
│                                                          │
│  1. Read all *_findings.yaml                             │
│  2. Merge/deduplicate competencies (3-25)               │
│  3. Aggregate edge cases, mistakes, practices            │
│  4. Write eval_criteria.yaml                             │
└─────────────────────────────────────────────────────────┘
```

### TEST_GEN Phase Detail (M3)

```
cgf-orchestrator
      │
      ▼ (spawn)
┌─────────────────────────────────────────────────────────┐
│              cgf-test-architect                          │
│                                                          │
│  1. Read eval_criteria.yaml (competencies, edge cases)  │
│  2. Transform each competency → 1-3 test cases          │
│  3. Generate edge case tests                             │
│  4. Generate negative tests from common_mistakes         │
│  5. Select validation types per scenario                 │
│     - code/code_llm for code output                     │
│     - llm_judge for text output                         │
│     - contains/regex for pattern matching               │
│  6. Write test_suite.yaml (10-50 tests)                 │
└─────────────────────────────────────────────────────────┘
      │
      ▼ (spawn)
┌─────────────────────────────────────────────────────────┐
│              cgf-test-validator                          │
│                                                          │
│  1. Validate against test_suite.schema.json             │
│  2. Calculate coverage percentages                       │
│     - Competency coverage (target: 100%)                │
│     - Edge case coverage                                 │
│     - Mistake coverage                                   │
│  3. Assess quality metrics                               │
│     - Difficulty distribution (40/40/20)                │
│     - Validation type appropriateness                   │
│  4. Write coverage_report.md                            │
│  5. Return PASS/FAIL status                             │
└─────────────────────────────────────────────────────────┘
```

## Related Documentation

- [CGF Agentic Roadmap](../../../docs/features/CGF-AGENTIC-ROADMAP.md)
- [Optimization Pipeline](../../optimization/README.md)
- [Research Team Plugin](../research-team/README.md)
