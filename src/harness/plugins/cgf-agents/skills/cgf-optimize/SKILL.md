---
name: cgf-optimize
description: >
  Start or resume CGF (Claude Gradient Feedback) optimization on a context-engineering
  resource. Supports agents, skills, commands, and other resource types.

  Invoke with resource name/path and optimization goal. Add --review for checkpoint mode
  where you can review and approve intermediate artifacts.

  <examples>
  - "/cgf-optimize python-expert async programming" - Optimize for async patterns
  - "/cgf-optimize typescript-expert --review" - With human review checkpoints
  - "/cgf-optimize research-team:research-specialist Context7 integration"
  </examples>

allowed-tools: Read, Write, Bash, Task, Glob, Grep
argument-hint: <resource> <goal> [--review]
---

# CGF Optimize Skill

This skill launches the CGF (Claude Gradient Feedback) optimization pipeline for a specified resource.

## Usage

```
/cgf-optimize <resource> <optimization_goal> [--review]
```

### Arguments

- **resource**: Resource identifier - can be:
  - Agent name: `python-expert`, `refactor-agent`
  - Namespaced agent: `research-team:research-specialist`
  - Full path: `src/harness/agents/configs/dev-python-expert.md`

- **optimization_goal**: What to optimize for:
  - `async programming`
  - `better error handling`
  - `code quality improvements`
  - `Context7 usage patterns`

- **--review** (optional): Enable checkpoint mode for human review at each phase

## Examples

### Basic Optimization
```
/cgf-optimize python-expert async programming
```
Runs full optimization pipeline automatically.

### With Review Checkpoints
```
/cgf-optimize typescript-expert --review
```
Pauses after research, test generation, and evaluation for your review.

### Plugin Agent
```
/cgf-optimize research-team:research-specialist Context7 integration
```
Optimizes a plugin agent.

## Workflow

1. **INIT**: Creates workspace, detects resource type
2. **RESEARCH**: Investigates domain best practices (via research-team)
3. **TEST_GEN**: Creates test suite from research findings
4. **OPTIMIZE**: Runs DSPy/TextGrad optimization
5. **EVALUATE**: Assesses results, recommends accept/refine/reject
6. **FINALIZE**: Applies recommendation

## Output

Results saved to `workspace/{resource_id}/`:
- `run_state.json` - Current state (supports resume)
- `{resource_id}-v{N}.md` - Optimized version
- `reviews/v{N}_review.md` - Evaluation report

## Resume

If optimization was interrupted, simply re-run the same command - it will resume from the last checkpoint.
