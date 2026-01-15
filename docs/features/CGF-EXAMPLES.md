# CGF Examples

Practical examples demonstrating CGF optimization workflows.

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
cgf optimize agents/configs/python-expert.md \
  --goal "improve async/await pattern explanations with practical concurrent examples" \
  --max-iterations 10
```

### Expected Output

```
CGF Optimization Pipeline
=========================
Resource: python-expert (agent)
Goal: improve async/await pattern explanations with practical concurrent examples
Strategy: prompt_optimization
Optimizer: dspy

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
cgf optimize skills/joplin-research.md \
  --goal "reduce false positive activations while maintaining recall for valid research requests" \
  --review
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
  - id: trigger-neg-001
    prompt: "My research indicates the bug is in line 42"
    expected_behavior: Skill does NOT activate
    validation:
      type: not_contains
      criteria: "Researching"
    tags: [negative, false-positive]

  - id: trigger-neg-002
    prompt: "This is a research paper about ML"
    expected_behavior: Skill does NOT activate
    validation:
      type: not_contains
      criteria: "Researching"
    tags: [negative, false-positive]
```

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
$ cgf optimize --goal "test"
Error: missing required argument
```

**Desired Error**:
```
$ cgf optimize --goal "test"
Error: Missing required argument 'resource_path'

Usage: cgf optimize <resource_path> --goal <goal>

Example:
  cgf optimize agents/python-expert.md --goal "improve async handling"

Run 'cgf optimize --help' for more information.
```

### Run Optimization

```bash
cgf optimize commands/cgf-optimize.md \
  --goal "provide clear, actionable error messages with usage examples" \
  --max-iterations 15
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
    prompt: "cgf optimize agent.md --goal 'test' --optimizer invalid"
    expected_behavior: |
      Error lists valid optimizer options,
      suggests correct usage
    validation:
      type: llm_judge
      criteria: |
        Lists valid optimizers (dspy, textgrad),
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
cgf optimize agents/configs/code-reviewer.md \
  --goal "improve feedback specificity" \
  --review
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

### Run with Custom Tests

```bash
cgf optimize agents/configs/financial-analyst.md \
  --goal "improve accuracy of financial analysis explanations" \
  --test-suite tests/optimization/financial-analyst-tests.yaml
```

### Custom Validation Function

For very domain-specific validation, implement a custom validator:

```python
# validators/financial_validator.py
from harness.optimization.testcases.validators import (
    BaseValidator,
    ValidationResult,
    ValidatorRegistry,
)

class FinancialAccuracyValidator(BaseValidator):
    """Validate financial calculations and terminology."""

    name = "financial_accuracy"

    # Known financial formulas for validation
    FORMULAS = {
        "EBITDA": "Net Income + Interest + Taxes + Depreciation + Amortization",
        "ROE": "Net Income / Shareholders Equity",
        "Current Ratio": "Current Assets / Current Liabilities",
    }

    async def validate(
        self,
        response: str,
        criteria: str,
        context: dict | None = None,
    ) -> ValidationResult:
        term = criteria.upper()

        if term not in self.FORMULAS:
            return ValidationResult(
                passed=False,
                score=0.0,
                reasoning=f"Unknown financial term: {term}",
            )

        # Check if response contains correct formula
        expected = self.FORMULAS[term]
        formula_components = expected.lower().split()

        matches = sum(
            1 for comp in formula_components
            if comp in response.lower()
        )

        score = matches / len(formula_components)
        passed = score >= 0.7

        return ValidationResult(
            passed=passed,
            score=score,
            reasoning=f"Formula accuracy: {score:.0%}",
            details={
                "term": term,
                "expected": expected,
                "component_matches": matches,
            },
        )

# Register validator
ValidatorRegistry.register(FinancialAccuracyValidator())
```

### Use Custom Validator in Tests

```yaml
test_cases:
  - id: fin-formula-001
    prompt: "How do you calculate EBITDA?"
    expected_behavior: Shows correct EBITDA formula
    validation:
      type: financial_accuracy
      criteria: EBITDA
    tags: [formula, validation]
    difficulty: basic
```

---

## Tips and Best Practices

### Writing Effective Goals

```bash
# Good: Specific and measurable
--goal "improve error message clarity with actionable guidance"

# Good: Targeted capability
--goal "better explain async/await with concurrent execution examples"

# Bad: Too vague
--goal "make it better"

# Bad: Multiple unrelated goals
--goal "improve errors and add new features and fix bugs"
```

### Test Suite Design

1. **Balance coverage**: Include basic, intermediate, and advanced cases
2. **Test boundaries**: Add edge cases and negative cases
3. **Use appropriate validators**: `contains` for simple checks, `llm_judge` for nuanced evaluation
4. **Tag tests**: Enable filtering and analysis by category

### Review Mode Strategy

1. **First run**: Always use `--review` for new optimizations
2. **Check competencies**: Verify research identified right focus areas
3. **Review test cases**: Ensure tests target your goals
4. **Inspect regressions**: Pay attention to what might be lost

### Handling Refinement

1. **Read the feedback**: Evaluation explains what needs improvement
2. **Check regressions**: Often the issue is losing important capabilities
3. **Consider constraints**: Sometimes it's better to narrow the goal
4. **Know when to stop**: After 2-3 REFINE cycles, reassess the goal
