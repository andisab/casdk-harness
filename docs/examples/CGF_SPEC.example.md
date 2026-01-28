# CGF Optimization Spec: Example

> This is an example SPEC.md file for CGF (ContextGrad Framework) optimization.
> Copy this template to your workspace directory and customize for your resource.

---

## Quick Start

1. Create a workspace directory: `mkdir -p workspace/my-agent`
2. Copy this file: `cp docs/examples/CGF_SPEC.example.md workspace/my-agent/SPEC.md`
3. Copy your resource: `cp path/to/agent.md workspace/my-agent/my-agent.md`
4. Edit SPEC.md with your optimization goals
5. Run: `make optimize WORKSPACE=workspace/my-agent`

---

## Resource

- **Type:** agent
- **File:** python-expert.md

## Optimization Goals

- Improve async/await pattern guidance with modern Python 3.12+ features
- Add better error handling examples using exception groups and ExceptionGroup
- Strengthen type hint recommendations with TypedDict and Protocol patterns
- Include practical asyncio.TaskGroup usage examples

## Target Improvements

- [ ] Add async context manager patterns (`async with` best practices)
- [ ] Include exception chaining examples (`raise ... from` patterns)
- [ ] Document Protocol vs ABC tradeoffs for structural typing
- [ ] Add asyncio.TaskGroup examples for concurrent task management
- [ ] Include typing.Self usage for fluent interfaces

## Evaluation Criteria

The optimized resource should demonstrate:

- **Correctness**: Code examples must be syntactically valid and runnable
- **Modernity**: Use Python 3.12+ features where appropriate
- **Completeness**: Cover common async patterns developers encounter
- **Clarity**: Explanations should be concise but comprehensive
- **Best Practices**: Follow PEP 8, type hints, and async conventions

## Constraints

- Do NOT remove existing content that's working well
- Preserve the overall structure and section organization
- Keep code examples under 30 lines each
- Avoid introducing dependencies beyond the standard library

## Success Metrics

| Metric | Target |
|--------|--------|
| Code example validity | 100% syntactically correct |
| Modern feature coverage | At least 5 Python 3.10+ features |
| Example completeness | Each pattern has usage + output |
| Documentation clarity | No ambiguous instructions |

---

## Alternative: Minimal Spec

If you prefer a minimal spec, CGF can work with just the essentials:

```markdown
# Optimization Spec: my-agent

## Resource
- **File:** my-agent.md

## Optimization Goals
- Improve X capability
- Add better Y examples
```

CGF will use defaults for everything else.

---

## Q&A Session Results

> This section is automatically appended when you run CGF without a complete spec.
> If you provide a complete spec above, Q&A is skipped.

**Session Date:** 2026-01-27
**Mode:** agentic

### Questions & Answers

1. **Q:** What specific async patterns need improvement?
   **A:** Focus on asyncio.gather, TaskGroups, and cancellation handling.

2. **Q:** Should we focus on any specific sections?
   **A:** Core approach and examples sections need the most work.

3. **Q:** What optimization mode do you prefer?
   **A:** Agentic mode (faster, no test suite needed).

4. **Q:** Do you want to review each iteration?
   **A:** Yes, I'd like to provide feedback after each round.

### Derived Settings

```yaml
optimizer_mode: agentic
max_iterations: 5
iteration_review: true
eval_model: sonnet
target_sections:
  - core_approach
  - examples
  - best_practices
```

---

## Workspace Structure After Optimization

After running CGF, your workspace will contain:

```
workspace/my-agent/
├── SPEC.md                    # This file (optimization spec)
├── CHANGELOG.md               # Human-readable optimization history (accumulates)
├── my-agent.md                # Original resource (NEVER modified)
├── my-agent-v1.md             # First optimized version
├── my-agent-v2.md             # Second version (if REFINE recommended)
├── research/                  # Research artifacts
│   ├── notes/
│   │   └── *.yaml             # Research findings
│   ├── eval_criteria.yaml     # Evaluation criteria
│   └── reviews/
│       └── v1_review.md       # Evaluation report
└── sessions/                  # Runtime state (delete to reset)
    ├── task_list.json         # Phase tracking
    ├── qa_session.json        # Q&A history
    └── *.summary.json         # Machine-readable summaries (for debugging)
```

### CHANGELOG.md

The `CHANGELOG.md` file is the primary human-readable record of optimization:
- **Accumulates entries** after each iteration (newest first)
- **Includes Final Results** section when optimization completes
- **Replaces final_report.md** as the single source of truth for review

Example structure:
```markdown
# CGF Optimization Changelog: my-agent

**Resource:** my-agent.md
**Mode:** agentic
**Started:** 2026-01-27
**Status:** COMPLETE

---

## Final Results

**Recommendation:** ACCEPT
**Total Iterations:** 2
...

---

## Iteration 2 (2026-01-28)

**Output:** my-agent-v2.md
**Words:** 6,842 → 11,247 (+64%)

### Top Changes
1. **Type System Depth**: Added ParamSpec, TypeVarTuple examples
...

---

## Iteration 1 (2026-01-27)

**Output:** my-agent-v1.md
**Words:** 2,847 → 6,842 (+140%)

### Top Changes
1. **Modern Type System**: PEP 695 syntax throughout
...
```

**To reset optimization state:** Delete `sessions/` directory
**To start fresh:** Delete everything except SPEC.md and original resource

---

## Resource Type Examples

### Agent Spec

```markdown
## Resource
- **Type:** agent
- **File:** my-agent.md

## Optimization Goals
- Improve domain expertise guidance
- Add better code examples
```

### Skill Spec

```markdown
## Resource
- **Type:** skill
- **File:** SKILL.md

## Optimization Goals
- Improve trigger keyword accuracy
- Enhance activation instructions
```

### Command Spec

```markdown
## Resource
- **Type:** command
- **File:** my-command.md

## Optimization Goals
- Improve help text clarity
- Add more usage examples
```

---

## Environment Variables

Override defaults via `.env` or command line:

```bash
# Optimization mode
CGF_OPTIMIZER_MODE=agentic    # agentic (default), python, or both
CGF_ITERATIONS=10             # Max iterations per section
CGF_ITERATION_REVIEW=false    # Pause for review after each iteration
CGF_EVAL_MODEL=sonnet         # sonnet (default), haiku, or opus
CGF_VERBOSE=true              # Show progress output
```

---

## Tips

1. **Be specific**: Vague goals like "make it better" won't help. Specify what aspects need improvement.

2. **Provide context**: If you have examples of good output or known issues, mention them.

3. **Set constraints**: Tell CGF what NOT to change if you have working sections.

4. **Use iteration review**: For important resources, enable `iteration_review: true` to provide feedback between rounds.

5. **Start with agentic mode**: It's faster and doesn't require test generation. Use programmatic mode only for critical resources needing quantitative validation.
