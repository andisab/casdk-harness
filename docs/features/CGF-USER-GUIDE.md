# CGF User Guide

This guide helps you optimize Claude Code resources using the Context Gradient Feedback (CGF) pipeline.

## Quick Start

Run your first optimization in 5 minutes.

### Prerequisites

- Python 3.10+
- Anthropic API key configured
- DSPy or TextGrad installed (optional, for advanced optimization)

### Basic Optimization

```bash
# Optimize an agent for a specific goal
cgf optimize agents/configs/python-expert.md --goal "improve async programming guidance"

# Run with review mode for human oversight
cgf optimize agents/configs/python-expert.md --goal "better error handling" --review

# Use a specific optimizer
cgf optimize agents/configs/python-expert.md --goal "clearer examples" --optimizer dspy
```

### What Happens

1. **Research Phase**: CGF analyzes the resource and goal, identifies competencies to optimize
2. **Test Generation**: Creates a test suite targeting the optimization goal
3. **Optimization**: Runs iterative improvements using the selected optimizer
4. **Evaluation**: Reviews changes using CAIR assessment (Coherence, Alignment, Improvement, Regression)
5. **Finalization**: Produces optimized resource file if evaluation passes

---

## Resource Types

CGF supports optimizing six resource types, each with a specialized strategy.

### Agents

Agent resources define AI assistant behaviors with system prompts.

**Strategy**: `prompt_optimization`
**Focus**: System prompt clarity, task handling, example quality

**Example**:
```bash
cgf optimize agents/configs/python-expert.md --goal "async programming"
```

**File Structure**:
```yaml
---
name: python-expert
description: Python development assistant
model: sonnet
tools: Read, Write, Bash
---
You are a Python expert...
```

### Skills

Skills define triggered behaviors activated by user commands or phrases.

**Strategy**: `trigger_optimization`
**Focus**: Activation precision, false positive reduction, boundary handling

**Example**:
```bash
cgf optimize skills/joplin-research.md --goal "better trigger detection"
```

**File Structure**:
```yaml
---
name: joplin-research
description: Research documentation skill
trigger_patterns:
  - "/research"
  - "research this topic"
---
When activated, search and document...
```

### Commands

Commands define slash commands with argument schemas.

**Strategy**: `schema_optimization`
**Focus**: Argument validation, error messages, help text quality

**Example**:
```bash
cgf optimize commands/optimize.md --goal "clearer error messages"
```

**File Structure**:
```yaml
---
name: cgf-optimize
command: /optimize
arguments:
  - name: resource
    required: true
  - name: --goal
    required: true
---
Run CGF optimization pipeline...
```

### Workflows

Workflows define multi-step processes with state machines.

**Strategy**: `workflow_optimization`
**Focus**: State transitions, error recovery, step coordination

**Example**:
```bash
cgf optimize workflows/deployment.md --goal "reliability improvements"
```

**File Structure**:
```yaml
---
name: deployment-flow
type: workflow
steps:
  - name: validate
  - name: build
  - name: deploy
---
Execute deployment sequence...
```

### Hooks

Hooks define lifecycle event handlers.

**Strategy**: `trigger_optimization`
**Focus**: Event matching, execution reliability

### MCP Servers

MCP server configurations define external tool integrations.

**Strategy**: `schema_optimization`
**Focus**: Configuration validation, error handling

---

## Optimization Goals

Writing effective optimization goals is crucial for good results.

### Goal Writing Guidelines

**Be Specific**: Target a particular capability or behavior.

```bash
# Good: Specific capability
--goal "improve async/await pattern explanations with practical examples"

# Bad: Too vague
--goal "make it better"
```

**Be Measurable**: Include criteria that can be evaluated.

```bash
# Good: Measurable outcome
--goal "reduce false positive trigger rate for similar commands"

# Bad: Subjective
--goal "feel more natural"
```

**Be Achievable**: Stay within the resource's scope.

```bash
# Good: Within scope
--goal "add error recovery guidance for database operations"

# Bad: Outside scope
--goal "add support for a new programming language"
```

### Example Goals by Resource Type

| Resource | Example Goals |
|----------|---------------|
| Agent | "improve code review feedback quality", "better explain complex algorithms" |
| Skill | "reduce false activations", "handle edge case triggers" |
| Command | "clearer validation errors", "better help text examples" |
| Workflow | "graceful interruption handling", "retry logic improvements" |

---

## Pipeline Phases

The CGF pipeline executes through these phases:

### INIT

Creates workspace and validates configuration.

**Artifacts Created**:
- `run_config.yaml` - Pipeline configuration
- `run_state.json` - State tracking

### RESEARCH

Analyzes the resource and goal to identify optimization competencies.

**What Happens**:
1. Loads resource definition
2. Analyzes optimization goal
3. Identifies key competencies
4. Documents edge cases and best practices

**Artifacts Created**:
- `research/eval_criteria.yaml` - Evaluation criteria with competencies

### TEST_GEN

Generates test cases targeting identified competencies.

**What Happens**:
1. Creates test cases for each competency
2. Includes positive and negative cases
3. Adds edge case coverage
4. Validates test suite structure

**Artifacts Created**:
- `tests/test_suite.yaml` - Test suite with 10-50 test cases

### OPTIMIZE

Runs iterative optimization using the selected optimizer.

**What Happens**:
1. Establishes baseline score
2. Generates prompt variants
3. Evaluates against test suite
4. Selects best performing version
5. Repeats until convergence or max iterations

**Artifacts Created**:
- `{resource}-v{n}.md` - Optimized resource version
- `{resource}-v{n}.md.summary.json` - Optimization metrics

### EVALUATE

Reviews optimization results using CAIR assessment.

**CAIR Dimensions**:
- **C**oherence: Structure and readability
- **A**lignment: Goal fidelity
- **I**mprovement: What got better
- **R**egression: What was lost

**Recommendations**:
- `ACCEPT` - Changes approved, proceed to finalize
- `REFINE` - Further iteration needed
- `REJECT` - Changes not acceptable

**Artifacts Created**:
- `reviews/v{n}_review.md` - Evaluation report

### FINALIZE

Handles the evaluation decision.

**Actions by Recommendation**:
- `ACCEPT`: Moves to COMPLETE
- `REFINE`: Returns to OPTIMIZE for another iteration
- `REJECT`: Marks run as failed

### COMPLETE

Pipeline finished successfully.

**Final State**:
- Optimized resource saved
- Summary metrics recorded
- Original resource preserved

---

## Review Mode

Use `--review` flag for human oversight at key decision points.

### Enabling Review Mode

```bash
cgf optimize resource.md --goal "optimization goal" --review
```

### Checkpoint Behavior

In review mode, the pipeline pauses at:

1. **After RESEARCH**: Review eval_criteria.yaml before test generation
2. **After EVALUATE**: Review recommendations before finalizing

### Resuming from Checkpoint

```bash
# Resume from last checkpoint
cgf resume --workspace workspace/resource-id/

# Accept current recommendation and continue
cgf resume --workspace workspace/resource-id/ --accept

# Request refinement
cgf resume --workspace workspace/resource-id/ --refine
```

### When to Use Review Mode

- First time optimizing a critical resource
- When optimization goal is complex
- When you want to validate test cases before optimization
- When reviewing AI-generated changes is required by policy

---

## Configuration

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--goal` | Optimization goal (required) | - |
| `--optimizer` | Optimizer type: `dspy`, `textgrad` | `dspy` |
| `--review` | Enable review mode | `false` |
| `--max-iterations` | Maximum optimization iterations | `10` |
| `--early-stop` | Early stopping threshold | `0.01` |
| `--output` | Output path for optimized resource | Auto-generated |

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
CGF_MAX_ITERATIONS=10
CGF_EARLY_STOPPING_THRESHOLD=0.01
CGF_DEFAULT_OPTIMIZER=dspy
```

### run_config.yaml

```yaml
resource:
  path: agents/configs/python-expert.md
  type: agent
  id: python-expert
  optimization_goal: improve async programming guidance

strategy: prompt_optimization
optimizer: dspy

options:
  max_iterations: 10
  early_stopping_threshold: 0.01
  review_mode: false
```

---

## Troubleshooting

### Common Issues

#### "Optimizer not available"

**Symptom**: Error about DSPy or TextGrad not installed.

**Solution**:
```bash
# For DSPy
pip install 'dspy-ai>=2.5.0'

# For TextGrad
pip install 'textgrad>=0.1.6'
```

#### "Empty system prompt"

**Symptom**: Validation fails with empty prompt error.

**Solution**: Ensure resource file has content after the YAML frontmatter.

#### "No test cases generated"

**Symptom**: TEST_GEN phase produces empty test suite.

**Solution**:
- Check optimization goal is specific enough
- Verify eval_criteria.yaml has competencies defined
- Review research notes for context

#### "Low optimization scores"

**Symptom**: Final score not much better than baseline.

**Solutions**:
- Make optimization goal more specific
- Increase max_iterations
- Check test cases are relevant to goal
- Try different optimizer

#### "REJECT recommendation"

**Symptom**: Evaluation rejects optimization.

**Solutions**:
- Review the review report for specific issues
- Adjust optimization goal
- Check for regression in critical capabilities
- Consider running with `--review` for more control

### Debug Mode

```bash
# Enable verbose logging
cgf optimize resource.md --goal "goal" --verbose

# Dry run (validate without executing)
cgf optimize resource.md --goal "goal" --dry-run
```

### Getting Help

```bash
# Show all options
cgf optimize --help

# Check pipeline status
cgf status --workspace workspace/resource-id/
```

---

## Best Practices

### Before Optimization

1. **Backup original**: Keep a copy of the original resource
2. **Define clear goal**: Write specific, measurable optimization goal
3. **Start with review mode**: Use `--review` for first optimization

### During Optimization

1. **Monitor progress**: Check iteration scores for convergence
2. **Review test cases**: Ensure tests target the right capabilities
3. **Watch for regressions**: Check CAIR report's Regression section

### After Optimization

1. **Validate manually**: Test optimized resource in real scenarios
2. **Compare versions**: Review diff between original and optimized
3. **Document changes**: Note what changed and why
4. **Keep original**: Preserve `{resource}-orig.md` for rollback

### Iteration Strategy

```
First run: Broad goal, review mode
   ↓
Review: Check competencies and test cases
   ↓
Refine: Narrow goal based on results
   ↓
Final: Automatic mode with specific goal
```
