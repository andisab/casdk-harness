# CGF Review Report Template
# Guide for cgf-result-evaluator agent output

# Use this structure when generating review reports.
# Replace {placeholders} with actual values.

---

## Template Structure

```markdown
# Evaluation Report: {resource_id} v{version}

## Summary

| Metric | Value |
|--------|-------|
| Original Score | {original_score:.2f} |
| Final Score | {final_score:.2f} |
| Improvement | {improvement_percent:.1f}% |
| Iterations | {iterations} |
| Duration | {duration_seconds}s |
| Recommendation | **{ACCEPT/REFINE/REJECT}** |

## Optimization Goal

{optimization_goal}

## Multi-Dimensional Evaluation

### 1. COHERENCE (Structure & Readability)

{coherence_analysis}

**Assessment:** {GOOD/CONCERN/PROBLEM}

**Evidence:**
- {coherence_evidence_1}
- {coherence_evidence_2}

### 2. ALIGNMENT (Goal Fidelity)

{alignment_analysis}

**Assessment:** {GOOD/CONCERN/PROBLEM}

**Competency Coverage:**
- {competency_1}: {covered/partially/missed}
- {competency_2}: {covered/partially/missed}

### 3. IMPROVEMENT (What Got Better)

{improvement_analysis}

**Specific Improvements:**
- **{improvement_category_1}**: {description}
- **{improvement_category_2}**: {description}

**Best Practices Incorporated:**
- {practice_1}
- {practice_2}

### 4. REGRESSION (What Was Lost)

{regression_analysis}

**Issues Detected:**
- {regression_1}: {impact}
- {regression_2}: {impact}

*Or: "No significant regressions detected."*

## Recommendation

**{ACCEPT/REFINE/REJECT}**

### Reasoning

{detailed_reasoning_paragraph}

### Refinement Hints

*Include only if recommendation is REFINE:*

1. {hint_1}
2. {hint_2}
3. {hint_3}

## Conclusion

{conclusion_paragraph}
```

---

## Field Definitions

### Summary Fields

| Field | Source | Format |
|-------|--------|--------|
| resource_id | run_config.yaml | String |
| version | Filename pattern | Integer (1, 2, 3...) |
| original_score | summary.json | Float (0.0-1.0) |
| final_score | summary.json | Float (0.0-1.0) |
| improvement_percent | summary.json | Float (%) |
| iterations | summary.json | Integer |
| duration_seconds | summary.json | Float |

### Assessment Values

| Value | Meaning | Impact on Recommendation |
|-------|---------|--------------------------|
| GOOD | No issues, positive result | Supports ACCEPT |
| CONCERN | Minor issues, fixable | May lead to REFINE |
| PROBLEM | Serious issues | Likely REJECT |

### Recommendation Thresholds

| Recommendation | Primary Criteria |
|----------------|------------------|
| ACCEPT | improvement > 5%, no regressions, CAIR all GOOD |
| REFINE | improvement 0-5%, OR mixed CAIR, OR fixable issues |
| REJECT | improvement <= 0, OR serious regressions, OR CAIR PROBLEM |

---

## Example: ACCEPT Report

```markdown
# Evaluation Report: python-expert v1

## Summary

| Metric | Value |
|--------|-------|
| Original Score | 0.65 |
| Final Score | 0.82 |
| Improvement | 26.2% |
| Iterations | 8 |
| Duration | 450s |
| Recommendation | **ACCEPT** |

## Optimization Goal

Improve async programming guidance and patterns

## Multi-Dimensional Evaluation

### 1. COHERENCE (Structure & Readability)

The optimized prompt maintains clear structure with improved organization
of async-specific sections. Tool usage guidance is now consolidated.

**Assessment:** GOOD

**Evidence:**
- Async patterns section now has clear subsections
- Examples are more consistently formatted

### 2. ALIGNMENT (Goal Fidelity)

Optimization directly addresses async programming goal. All competencies
from research phase are covered with specific guidance.

**Assessment:** GOOD

**Competency Coverage:**
- Async/await fundamentals: covered
- Error handling in async: covered
- Concurrent execution patterns: covered

### 3. IMPROVEMENT (What Got Better)

Significant enhancement in async pattern guidance. New sections address
specific scenarios identified in research.

**Specific Improvements:**
- **Async patterns**: Added context manager patterns for async
- **Error handling**: Enhanced with cancellation handling examples
- **Performance**: Added guidance on concurrency limits

**Best Practices Incorporated:**
- Always use asyncio.sleep() not time.sleep()
- Use try/finally for cleanup in async contexts

### 4. REGRESSION (What Was Lost)

No significant regressions detected.

## Recommendation

**ACCEPT**

### Reasoning

The optimization achieved 26.2% improvement, well above the 5% threshold.
All four CAIR dimensions assessed as GOOD. The optimized prompt addresses
the async programming goal comprehensively while maintaining coherence and
avoiding regressions. The improvements are substantive and align with
research findings.

## Conclusion

This optimization run successfully enhanced the python-expert agent for
async programming. The significant score improvement reflects genuine
enhancement in async guidance, error handling, and best practice
incorporation. Recommend accepting the optimized resource.
```

---

## Example: REFINE Report

```markdown
# Evaluation Report: typescript-expert v1

## Summary

| Metric | Value |
|--------|-------|
| Original Score | 0.70 |
| Final Score | 0.73 |
| Improvement | 4.3% |
| Iterations | 10 |
| Duration | 520s |
| Recommendation | **REFINE** |

...

## Recommendation

**REFINE**

### Reasoning

The 4.3% improvement is positive but below the 5% acceptance threshold.
Additionally, while type inference competency improved, strict mode
handling regressed slightly. Another iteration focusing on preserving
strict mode guidance while enhancing type inference could achieve
acceptable results.

### Refinement Hints

1. Preserve existing strict mode guidance from original
2. Focus type inference improvements on complex generic scenarios
3. Add explicit edge case handling for union type inference
```

---

## Example: REJECT Report

```markdown
# Evaluation Report: react-expert v1

## Summary

| Metric | Value |
|--------|-------|
| Original Score | 0.75 |
| Final Score | 0.68 |
| Improvement | -9.3% |
| Iterations | 10 |
| Duration | 480s |
| Recommendation | **REJECT** |

...

## Recommendation

**REJECT**

### Reasoning

The optimization resulted in a 9.3% score decrease. Analysis reveals
the optimizer over-specialized on hooks patterns while degrading general
component guidance. The regression in core React concepts outweighs
any improvements in hooks handling. The original resource should be
preserved.

## Conclusion

This optimization attempt failed to improve the react-expert agent.
The negative score change and significant regressions in core competencies
indicate the optimization direction was incorrect. Recommend keeping the
original resource and potentially adjusting the optimization goal or
research criteria for future attempts.
```
