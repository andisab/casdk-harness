# CGF Examples

Practical examples demonstrating CGF optimization workflows.

> **Note**: CGF uses a SPEC.md-based workflow via `make optimize`. The Q&A phase
> captures your optimization goals interactively, or you can provide a goal directly.
> See [CGF-USER-GUIDE.md](./CGF-USER-GUIDE.md) for detailed documentation.

## Example 1: Basic Agent Optimization

Optimize the python-expert agent for better async programming guidance.

### Goal

Improve the agent's ability to explain and demonstrate async/await patterns.

### Setup

```bash
# View current agent
cat agents/configs/python-expert.md
```

**Original Agent (excerpt)**:
```markdown
---
name: python-expert
description: Python development assistant
model: sonnet
tools: Read, Write, Bash
---
You are a Python expert specializing in modern Python development...
```

### Run Optimization

```bash
# Initialize workspace and set up SPEC.md
make cgf-init NAME=python-expert
cp src/harness/agents/configs/python-expert.md workspace/python-expert/

# Edit SPEC.md with your goal, or run with direct goal
make optimize WORKSPACE=workspace/python-expert \
  GOAL="improve async/await pattern explanations with practical concurrent examples"
```

### Expected Output

```
CGF Optimization Pipeline
=========================
Resource: python-expert (agent)
Goal: improve async/await pattern explanations with practical concurrent examples
Strategy: prompt_optimization
Optimizer: agentic (default)

Phase: INIT ✓
Phase: RESEARCH ✓
  - Identified 4 competencies
  - Documented 3 edge cases
  - Found 5 best practices

Phase: TEST_GEN ✓
  - Generated 18 test cases
  - Coverage: basic (6), intermediate (8), advanced (4)

Phase: OPTIMIZE
  Iteration 1/10: 0.65 → 0.71 (+9.2%)
  Iteration 2/10: 0.71 → 0.76 (+7.0%)
  Iteration 3/10: 0.76 → 0.79 (+3.9%)
  Iteration 4/10: 0.79 → 0.81 (+2.5%)
  Iteration 5/10: 0.81 → 0.82 (+1.2%)
  Early stopping: improvement below threshold

Phase: EVALUATE ✓
  Recommendation: ACCEPT
  COHERENCE: Good
  ALIGNMENT: Excellent
  IMPROVEMENT: Significant
  REGRESSION: None detected

Phase: FINALIZE ✓
Phase: COMPLETE ✓

Results:
  Original Score: 0.65
  Final Score: 0.82
  Improvement: +26.2%
  Output: workspace/python-expert/python-expert-v1.md
```

### Review Changes

```bash
# Compare original to optimized
diff agents/configs/python-expert.md workspace/python-expert/python-expert-v1.md
```

**Key Improvements**:
- Added section on asyncio event loop fundamentals
- Included asyncio.gather examples for concurrent execution
- Added error handling patterns for async code
- Documented common pitfalls (blocking calls, exception propagation)

---

## Example 2: Skill Trigger Refinement

Improve the joplin-research skill's trigger detection accuracy.

### Problem

The skill has high false positive rate - activating on phrases that mention "research" but aren't research requests.

### Setup

**Original Skill**:
```markdown
---
name: joplin-research
description: Research and document topics in Joplin
trigger_patterns:
  - "/research"
  - "research"
  - "research this"
---
When triggered, search for information and create Joplin notes...
```

### Run Optimization

```bash
# Initialize workspace
make cgf-init NAME=joplin-research
cp skills/joplin-research.md workspace/joplin-research/

# Run with review mode (set CGF_ITERATION_REVIEW=true)
CGF_ITERATION_REVIEW=true make optimize WORKSPACE=workspace/joplin-research \
  GOAL="reduce false positive activations while maintaining recall for valid research requests"
```

### Review Mode Interaction

```
Phase: RESEARCH ✓
  Competencies identified:
  1. Trigger Precision - Activate only on valid research requests
  2. Trigger Recall - Catch all valid research command variations
  3. Context Awareness - Consider surrounding context

[CHECKPOINT] Review eval_criteria.yaml? (y/n): y

Opening workspace/joplin-research/research/eval_criteria.yaml...

Continue with TEST_GEN? (y/n): y

Phase: TEST_GEN ✓
  Test cases generated:
  - Positive: "/research async patterns", "please research this topic"
  - Negative: "my research shows", "research paper review"
  - Edge: "research?", "RESEARCH THIS"

[CHECKPOINT] Review test_suite.yaml? (y/n): y
```

### Test Suite Review

```yaml
# workspace/joplin-research/tests/test_suite.yaml
test_cases:
  # Positive cases - should activate
  - id: trigger-pos-001
    prompt: "/research async patterns"
    expected_behavior: Skill activates
    validation:
      type: contains
      criteria: "Researching"
    tags: [positive, command]

  - id: trigger-pos-002
    prompt: "Can you research Python decorators?"
    expected_behavior: Skill activates
    validation:
      type: contains
      criteria: "Researching"
    tags: [positive, natural]

  # Negative cases - should NOT activate
  # Negative cases - should NOT activate (use llm_judge for semantic evaluation)
  - id: trigger-neg-001
    prompt: "My research indicates the bug is in line 42"
    expected_behavior: Skill does NOT activate
    validation:
      type: llm_judge
      criteria: |
        Response should NOT indicate skill activation.
        Should not start with "Researching..." or similar.
    tags: [negative, false-positive]

  - id: trigger-neg-002
    prompt: "This is a research paper about ML"
    expected_behavior: Skill does NOT activate
    validation:
      type: llm_judge
      criteria: |
        Response should NOT indicate skill activation.
        Should treat "research paper" as content reference, not command.
    tags: [negative, false-positive]
```

> **Note**: Available validation types are: `exact`, `contains`, `regex`, `llm_judge`,
> `code`, `code_syntax`, `code_llm`. Use `llm_judge` for semantic evaluation.

### Results

```
Phase: OPTIMIZE ✓
  Iterations: 7
  Original Score: 0.58
  Final Score: 0.89

Phase: EVALUATE
  Recommendation: ACCEPT

  COHERENCE: Good
    Trigger patterns are well-structured

  ALIGNMENT: Excellent
    Optimized triggers match the precision/recall goal

  IMPROVEMENT:
    - False positive rate reduced from 35% to 8%
    - Added context-aware patterns
    - Better handling of command prefix variations

  REGRESSION: None
    - All valid trigger patterns still work
    - Natural language requests recognized
```

**Optimized Triggers**:
```yaml
trigger_patterns:
  - "/research"
  - "^research (?:this|about|on) "
  - "^(?:can you |please )?research "
  - "^I need research on "
```

---

## Example 3: Command Error Handling

Improve error messages for the cgf optimize command.

### Problem

Users report that error messages are unclear when they provide invalid arguments.

### Setup

**Current Error**:
```
$ make optimize
Error: No SPEC.md found. Run 'make cgf-init NAME=<name>' first.
```

**Desired Error**:
```
$ make optimize
Error: No SPEC.md found in workspace.

To start optimization:
  1. Run: make cgf-init NAME=<agent-name>
  2. Copy your resource to the workspace
  3. Edit SPEC.md with your optimization goal
  4. Run: make optimize WORKSPACE=workspace/<name>

Example:
  make cgf-init NAME=python-expert
  cp agents/python-expert.md workspace/python-expert/
  make optimize WORKSPACE=workspace/python-expert
```

### Run Optimization

```bash
# Initialize workspace for the command resource
make cgf-init NAME=cgf-optimize
cp commands/cgf-optimize.md workspace/cgf-optimize/

# Run optimization with specific goal
make optimize WORKSPACE=workspace/cgf-optimize \
  GOAL="provide clear, actionable error messages with usage examples"
```

### Generated Test Cases

```yaml
test_cases:
  # Missing required argument
  - id: err-missing-001
    prompt: "cgf optimize --goal 'test'"
    expected_behavior: |
      Error message mentions 'resource_path',
      shows correct usage syntax,
      provides example command
    validation:
      type: llm_judge
      criteria: |
        Error is specific about missing argument,
        includes usage example,
        suggests --help option

  # Invalid file path
  - id: err-path-001
    prompt: "cgf optimize nonexistent.md --goal 'test'"
    expected_behavior: |
      Error mentions file not found,
      shows the invalid path,
      suggests checking the path
    validation:
      type: contains
      criteria: "not found"

  # Invalid optimizer
  - id: err-opt-001
    prompt: "make optimize OPTIMIZER=invalid"
    expected_behavior: |
      Error lists valid optimizer options,
      suggests correct usage
    validation:
      type: llm_judge
      criteria: |
        Lists valid optimizers (agentic, mipro, textgrad),
        shows correct option syntax
```

### Results

**Before**:
```
Error: missing required argument
```

**After**:
```
Error: Missing required argument 'resource_path'

The optimize command requires a path to the resource file.

Usage:
  cgf optimize <resource_path> --goal <optimization_goal>

Arguments:
  resource_path    Path to the agent, skill, or command file
  --goal          Description of desired improvements (required)

Example:
  cgf optimize agents/configs/python-expert.md --goal "improve error handling"

For all options, run:
  cgf optimize --help
```

---

## Example 4: Multi-Iteration Refinement

Handle the REFINE loop when first optimization attempt needs improvement.

### Scenario

Optimizing an agent, but first attempt has regression in code quality guidance.

### Initial Run

```bash
# Initialize workspace
make cgf-init NAME=code-reviewer
cp agents/configs/code-reviewer.md workspace/code-reviewer/

# Run with review mode
CGF_ITERATION_REVIEW=true make optimize WORKSPACE=workspace/code-reviewer \
  GOAL="improve feedback specificity"
```

### First Evaluation

```
Phase: EVALUATE
  Recommendation: REFINE

  COHERENCE: Good
  ALIGNMENT: Good

  IMPROVEMENT:
    - Feedback is more specific
    - Better issue categorization
    - Added severity levels

  REGRESSION: DETECTED
    - Lost guidance on code style conventions
    - Reduced explanation of why issues matter
    - Less context on best practices

  Refinement Guidance:
    - Preserve code style guidance from original
    - Keep "why this matters" explanations
    - Maintain best practice references
```

### Refinement Iteration

The pipeline automatically iterates with refined constraints:

```
Phase: OPTIMIZE (Iteration 2)
  Constraint: Preserve code style guidance
  Constraint: Keep explanatory context
  Constraint: Maintain best practice references

  Iteration 6/10: 0.75 → 0.78
  Iteration 7/10: 0.78 → 0.81
  Iteration 8/10: 0.81 → 0.84
  Iteration 9/10: 0.84 → 0.85

Phase: EVALUATE
  Recommendation: ACCEPT

  IMPROVEMENT:
    - All previous improvements retained
    - Code style guidance preserved
    - Explanatory context maintained

  REGRESSION: None detected
```

### Final Output

```
Results:
  Original Score: 0.68
  Final Score: 0.85
  Improvement: +25.0%
  Iterations: 9 (including refinement)
  Versions:
    - v1: REFINE (regression detected)
    - v2: ACCEPT (improvements preserved)
  Output: workspace/code-reviewer/code-reviewer-v2.md
```

---

## Example 5: Custom Test Cases

Write domain-specific test cases for specialized optimization.

### Scenario

Optimize an agent for a specific domain (financial analysis) that requires custom test cases.

### Create Custom Test Suite

```yaml
# tests/optimization/financial-analyst-tests.yaml
name: financial-analyst-optimization
agent_name: financial-analyst
version: "1.0"

test_cases:
  # Domain-specific terminology
  - id: fin-term-001
    prompt: "What is EBITDA and how is it calculated?"
    expected_behavior: |
      Accurate definition,
      correct formula,
      mentions common adjustments
    validation:
      type: llm_judge
      criteria: |
        Defines EBITDA correctly,
        shows calculation formula,
        mentions industry variations
    tags: [terminology, basic]
    difficulty: basic

  # Regulatory compliance
  - id: fin-reg-001
    prompt: "What are the key SOX compliance requirements?"
    expected_behavior: |
      Lists main requirements,
      mentions internal controls,
      references relevant sections
    validation:
      type: llm_judge
      criteria: |
        Covers Section 302 and 404,
        explains internal control requirements,
        accurate and current
    tags: [compliance, intermediate]
    difficulty: intermediate

  # Complex analysis
  - id: fin-dcf-001
    prompt: "Walk me through a DCF valuation"
    expected_behavior: |
      Step-by-step explanation,
      mentions key assumptions,
      discusses limitations
    validation:
      type: llm_judge
      criteria: |
        Explains free cash flow calculation,
        discusses discount rate selection,
        mentions terminal value,
        addresses common pitfalls
    tags: [analysis, advanced]
    difficulty: advanced

  # Edge case: Conflicting data
  - id: fin-edge-001
    prompt: "Revenue is growing but cash flow is declining. What might this indicate?"
    expected_behavior: |
      Identifies potential causes,
      suggests investigation areas,
      doesn't jump to conclusions
    validation:
      type: llm_judge
      criteria: |
        Mentions working capital issues,
        suggests revenue recognition review,
        recommends further analysis
    tags: [edge-case, analysis]
    difficulty: advanced

  # Negative case: Out of scope
  - id: fin-neg-001
    prompt: "Write me a poem about quarterly earnings"
    expected_behavior: |
      Redirects to financial analysis tasks,
      maintains professional tone
    validation:
      type: llm_judge
      criteria: |
        Does not write poem,
        offers relevant financial assistance instead
    tags: [negative, boundary]
    difficulty: basic
```

### Run with Custom Tests (Programmatic Mode)

To use a custom test suite with programmatic optimization (DSPy MIPROv2 or TextGrad),
enable programmatic mode:

```bash
# Initialize workspace
make cgf-init NAME=financial-analyst
cp agents/configs/financial-analyst.md workspace/financial-analyst/

# Copy custom test suite to workspace
cp tests/optimization/financial-analyst-tests.yaml workspace/financial-analyst/tests/tests.yaml

# Enable programmatic mode and run with MIPROv2
CGF_ENABLE_PROGRAMMATIC=true make optimize WORKSPACE=workspace/financial-analyst \
  GOAL="improve accuracy of financial analysis explanations"
```

> **Note**: Programmatic mode (DSPy MIPROv2, TextGrad) requires:
> - `CGF_ENABLE_PROGRAMMATIC=true` environment variable
> - At least 6 deterministic tests (exact, contains, regex, code, code_syntax)
> - DSPy or TextGrad installed: `pip install 'dspy-ai>=2.5.0'` or `pip install 'textgrad>=0.1.6'`

### Domain-Specific Validation with llm_judge

For domain-specific validation, use `llm_judge` with detailed criteria:

```yaml
test_cases:
  - id: fin-formula-001
    prompt: "How do you calculate EBITDA?"
    expected_behavior: Shows correct EBITDA formula
    validation:
      type: llm_judge
      criteria: |
        Response must include the correct EBITDA formula:
        Net Income + Interest + Taxes + Depreciation + Amortization

        Also acceptable: Revenue - Operating Expenses (excluding D&A)

        Should mention that EBITDA is a non-GAAP metric.
    tags: [formula, validation]
    difficulty: basic
```

The `llm_judge` validator uses Claude to evaluate responses against your criteria,
providing semantic understanding for domain-specific validation without needing
custom code.

---

## Tips and Best Practices

### Writing Effective Goals

```bash
# Good: Specific and measurable
GOAL="improve error message clarity with actionable guidance"

# Good: Targeted capability
GOAL="better explain async/await with concurrent execution examples"

# Bad: Too vague
GOAL="make it better"

# Bad: Multiple unrelated goals
GOAL="improve errors and add new features and fix bugs"
```

### Test Suite Design

1. **Balance coverage**: Include basic, intermediate, and advanced cases
2. **Test boundaries**: Add edge cases and negative cases
3. **Use appropriate validators**:
   - `exact` / `contains` / `regex` - Deterministic checks (enable programmatic mode)
   - `llm_judge` - Nuanced semantic evaluation (agentic mode)
   - `code` / `code_syntax` - Code validation
4. **Tag tests**: Enable filtering and analysis by category

### Review Mode Strategy

1. **First run**: Always use `CGF_ITERATION_REVIEW=true` for new optimizations
2. **Check competencies**: Verify research identified right focus areas
3. **Review test cases**: Ensure tests target your goals
4. **Inspect regressions**: Pay attention to what might be lost

### Handling Refinement

1. **Read the feedback**: Evaluation explains what needs improvement
2. **Check regressions**: Often the issue is losing important capabilities
3. **Consider constraints**: Sometimes it's better to narrow the goal
4. **Know when to stop**: After 2-3 REFINE cycles, reassess the goal

### Optimizer Selection

| Optimizer | Best For | Requirements |
|-----------|----------|--------------|
| `agentic` (default) | Most use cases, LLM self-critique | None |
| `mipro` | Large test suites, Bayesian optimization | CGF_ENABLE_PROGRAMMATIC=true, 6+ deterministic tests |
| `textgrad` | Gradient-based refinement | CGF_ENABLE_PROGRAMMATIC=true, 6+ deterministic tests |
