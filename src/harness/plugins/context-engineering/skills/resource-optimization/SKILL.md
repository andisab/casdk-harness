---
name: resource-optimization
description: >
  Use this skill to optimize recently created Claude Code resources (agents, skills, commands, plugins)
  using the CGF optimization framework. Detects resource type, auto-generates test suites using
  cgf-test-architect patterns, runs baseline evaluation, and applies targeted optimization.
  Automatically invoked when user says "optimize the agent I just created", "generate tests for this
  resource", "improve my agent with optimization", or mentions "CGF optimization".

  Examples:
  <example>
  Context: User just created a new agent definition
  user: "Optimize the agent I just created"
  assistant: "I'll use the resource-optimization skill to generate tests and optimize your agent."
  <commentary>
  The user wants to enhance a recently created agent through the CGF pipeline.
  </commentary>
  </example>

  <example>
  Context: User has an agent that needs testing
  user: "Generate tests for my python-expert agent"
  assistant: "I'll use the resource-optimization skill to create a comprehensive test suite."
  <commentary>
  Test generation is a key capability before optimization can begin.
  </commentary>
  </example>

  <example>
  Context: User wants to improve an existing resource
  user: "Run CGF optimization on my skill"
  assistant: "I'll use the resource-optimization skill to run the optimization pipeline."
  <commentary>
  Explicit request for CGF optimization workflow.
  </commentary>
  </example>

allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# Resource Optimization Skill

This skill bridges resource creation (context-engineering) with resource optimization (CGF framework)
to enable end-to-end improvement of Claude Code resources.

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Resource Optimization Pipeline                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. DETECT    →   Identify resource type and location               │
│                   (agent/skill/command/plugin)                       │
│                                                                      │
│  2. RESEARCH  →   Spawn cgf-research-lead for domain research       │
│                   Generate eval_criteria.yaml                        │
│                                                                      │
│  3. TEST      →   Spawn cgf-test-architect to create test suite     │
│                   Generate tests.yaml                                │
│                                                                      │
│  4. BASELINE  →   Run test suite against original resource          │
│                   Record baseline scores                             │
│                                                                      │
│  5. OPTIMIZE  →   Execute CGF optimization with appropriate         │
│                   strategy (programmatic vs agentic)                 │
│                                                                      │
│  6. COMPARE   →   Present before/after metrics                      │
│                   Show improvements per section                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Step 1: Resource Detection

Detect the resource type based on file location and structure:

| Resource Type | Location Pattern | Key Indicators |
|---------------|------------------|----------------|
| **Agent** | `agents/*.md`, `.claude/agents/*.md` | YAML frontmatter with `name`, `description` |
| **Skill** | `skills/*/SKILL.md` | `allowed-tools` in frontmatter |
| **Command** | `commands/*/COMMAND.md` | `command` field in frontmatter |
| **Plugin** | `.claude-plugin/plugin.json` | `resources` and `manifest` sections |

**Detection Algorithm**:
```python
def detect_resource_type(path: Path) -> ResourceType:
    if path.name.endswith(".md"):
        content = path.read_text()
        if "allowed-tools:" in content:
            return ResourceType.SKILL
        elif "command:" in content:
            return ResourceType.COMMAND
        elif "name:" in content and "description:" in content:
            return ResourceType.AGENT
    elif path.name == "plugin.json":
        return ResourceType.PLUGIN
    return ResourceType.UNKNOWN
```

## Step 2: Research Phase

Spawn `cgf-research-lead` to gather domain-specific competencies:

```bash
# Via direct agent invocation
python -m harness.direct_agent \
  --agent cgf-agents:cgf-research-lead \
  --prompt "Research competencies for: [resource name and description]" \
  --verbose
```

**Expected Output**: `workspace/{resource-name}/research/eval_criteria.yaml`

**eval_criteria.yaml Structure**:
```yaml
name: resource-name
version: "1.0"

competencies:
  - id: comp_001
    name: "Primary Competency"
    description: "What the resource should excel at"
    section: core_approach
    priority: high
    test_patterns:
      - "Pattern to validate"

edge_cases:
  - id: edge_001
    competency_id: comp_001
    description: "Tricky scenario"
    expected_behavior: "How to handle it"

common_mistakes:
  - id: mistake_001
    competency_id: comp_001
    pattern: "What goes wrong"
    correction: "How to fix it"
```

## Step 3: Test Generation

Spawn `cgf-test-architect` to create comprehensive test suite:

```bash
python -m harness.direct_agent \
  --agent cgf-agents:cgf-test-architect \
  --prompt "Generate test suite for: [resource path] using eval criteria: [criteria path]" \
  --verbose
```

**Expected Output**: `workspace/{resource-name}/tests/tests.yaml`

**Test Types to Generate**:

| Type | Validator | Purpose |
|------|-----------|---------|
| **Deterministic** | `regex`, `exact_match`, `code` | Objective, quantifiable tests |
| **Qualitative** | `llm_judge`, `semantic` | Subjective quality assessment |
| **Edge Cases** | `code_llm` | Complex scenarios requiring LLM evaluation |

**Minimum Test Coverage**:
- 6+ deterministic tests for PROGRAMMATIC optimization
- 3+ LLM-judge tests for AGENTIC optimization
- At least 1 test per identified competency

## Step 4: Baseline Evaluation

Run the test suite against the original resource:

```bash
# Record baseline scores
uv run python -m harness.optimization.cli.optimize \
  --agent {resource-path} \
  --test-suite {tests-path} \
  --baseline-only \
  --output {workspace}/baseline.json
```

**Baseline Output**:
```json
{
  "resource": "resource-name",
  "timestamp": "2024-01-15T10:00:00Z",
  "overall_score": 0.73,
  "section_scores": {
    "role_definition": 0.85,
    "core_approach": 0.70,
    "best_practices": 0.65,
    "constraints": 0.75
  },
  "test_results": [
    {"id": "test_001", "passed": true, "score": 1.0},
    {"id": "test_002", "passed": false, "score": 0.3}
  ]
}
```

## Step 5: CGF Optimization

Execute optimization based on test coverage analysis:

### Strategy Selection

| Coverage | Strategy | Optimizer |
|----------|----------|-----------|
| 6+ deterministic tests | PROGRAMMATIC | DSPy MIPROv2 / TextGrad |
| 3+ LLM-judge tests | AGENTIC | Self-critique + conventions |
| < 3 tests | PRESERVE | Keep original |

### Execution

```bash
# Section-based optimization
uv run python -m harness.optimization.cli.section_optimize \
  --agent {resource-path} \
  --test-suite {tests-path} \
  --criteria {eval-criteria-path} \
  --workspace {workspace} \
  --optimizer mipro \
  --iterations 2 \
  --verbose
```

### Monitoring Progress

Key signals to watch:
- `EXECUTE: Section improved` - Section optimization succeeded
- `Cross-section regression detected` - Optimization caused regression in other section
- `Rolling back section` - Regression triggered rollback
- `VALIDATE: Passed` - Final prompt passed post-synthesis validation

## Step 6: Comparison Report

Present before/after analysis:

```markdown
# Optimization Report: {resource-name}

## Summary
- **Overall Improvement**: +12.5% (0.73 → 0.82)
- **Sections Optimized**: 3/5
- **Duration**: 45.2s
- **Strategy Used**: Hybrid (PROGRAMMATIC + AGENTIC)

## Section-by-Section Analysis

| Section | Before | After | Change | Strategy |
|---------|--------|-------|--------|----------|
| Role Definition | 0.85 | 0.90 | +5.9% | AGENTIC |
| Core Approach | 0.70 | 0.82 | +17.1% | PROGRAMMATIC |
| Best Practices | 0.65 | 0.78 | +20.0% | PROGRAMMATIC |
| Constraints | 0.75 | 0.80 | +6.7% | AGENTIC |
| Examples | 0.72 | 0.72 | 0% | PRESERVE |

## Cross-Section Impact Matrix

| Source → Target | Impact |
|-----------------|--------|
| Core Approach → Best Practices | +0.02 (beneficial) |
| Best Practices → Constraints | -0.01 (minor regression, below threshold) |

## Output Files
- Optimized resource: `workspace/{resource-name}/{resource-name}-v2.md`
- Test results: `workspace/{resource-name}/tests/results.json`
- Full report: `workspace/{resource-name}/optimization-report.md`
```

## Quick Commands

```bash
# Full optimization pipeline
/resource-optimization path/to/agent.md

# Test generation only
/resource-optimization path/to/agent.md --tests-only

# Baseline evaluation only
/resource-optimization path/to/agent.md --baseline-only

# Skip research phase (use existing eval_criteria.yaml)
/resource-optimization path/to/agent.md --skip-research
```

## Integration with context-engineering

When creating a new resource with context-engineer:

1. **After creation**: User is prompted to optimize
   ```
   "Resource created! Would you like to generate tests and optimize?"
   [Yes, optimize] [Generate tests only] [Skip]
   ```

2. **Automatic suggestions**: Based on resource complexity
   - Simple agents (< 500 words): Suggest test generation
   - Complex agents (> 1500 words): Recommend full optimization

3. **Continuous improvement**: Track optimization history
   ```yaml
   # .optimization-history.yaml
   - version: 1
     date: 2024-01-15
     score: 0.73
   - version: 2
     date: 2024-01-16
     score: 0.82
     changes:
       - "Improved async pattern coverage"
       - "Added error handling examples"
   ```

## Constraints

- **Never overwrite original**: Always create versioned outputs (v1, v2, etc.)
- **Human review for major changes**: Flag improvements > 30% for review
- **Respect resource boundaries**: Don't optimize unrelated files
- **Preserve user customizations**: Keep commented sections unchanged

## Success Criteria

Optimization is successful when:
1. Final score ≥ baseline score (no regression)
2. Cross-section impacts within threshold (< 5% regression)
3. All quantitative tests pass or improve
4. Post-synthesis validation passes
5. Human-reviewable diff is generated

---

**Next Steps**: After optimization, consider running the full test suite periodically to detect drift, or set up a CI/CD integration to validate resources on commit.
