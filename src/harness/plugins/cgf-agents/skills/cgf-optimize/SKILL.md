---
name: cgf-optimize
description: >
  Start or resume CGF (Claude Gradient Feedback) optimization on a context-engineering
  resource. Supports agents, skills, commands, and other resource types.

  Invoke with resource name/path and optimization goal. Add --review for checkpoint mode
  where you can review and approve intermediate artifacts.

  Supports two modes:
  - **Optimization mode**: Optimize an existing resource
  - **Creation mode**: Create and optimize a new resource from description (use /cgf-create)

  <examples>
  - "/cgf-optimize python-expert async programming" - Optimize for async patterns
  - "/cgf-optimize typescript-expert --review" - With human review checkpoints
  - "/cgf-optimize research-team:research-specialist Context7 integration"
  - "/cgf-create Python async expert that helps with asyncio patterns"
  - "/cgf-create Kubernetes deployment agent --review"
  </examples>

allowed-tools: Read, Write, Bash, Task, Glob, Grep
argument-hint: <resource|description> <goal> [--review]
---

# CGF Optimize Skill

This skill launches the CGF (Claude Gradient Feedback) optimization pipeline for a specified resource or creates a new resource from description.

## Usage

### Optimization Mode (Existing Resource)
```
/cgf-optimize <resource> <optimization_goal> [--review]
```

### Creation Mode (New Resource)
```
/cgf-create <description> [--review]
```

### Arguments

**For optimization mode:**
- **resource**: Resource identifier - can be:
  - Agent name: `python-expert`, `refactor-agent`
  - Namespaced agent: `research-team:research-specialist`
  - Full path: `.claude/agents/dev-python-expert.md`

- **optimization_goal**: What to optimize for:
  - `async programming`
  - `better error handling`
  - `code quality improvements`
  - `Context7 usage patterns`

**For creation mode:**
- **description**: Natural language description of the desired resource:
  - `Python async expert that helps with asyncio patterns`
  - `Kubernetes deployment agent for managing k8s resources`
  - `Code review skill for security-focused reviews`

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

### Create New Agent
```
/cgf-create Python async expert that helps with asyncio patterns
```
Creates initial agent draft using context-engineer, then optimizes.

### Create With Review
```
/cgf-create Kubernetes deployment agent --review
```
Creates and optimizes with human review at each phase.

## Workflow

### Optimization Mode
1. **INIT**: Creates workspace, detects resource type
2. **RESEARCH**: Investigates domain best practices (via research-team)
3. **RESEARCH_ITERATE**: Agentic optimization using research findings and LLM self-critique
4. **EVALUATE**: Assesses results, recommends accept/refine/reject
5. **FINALIZE**: Applies recommendation

### Creation Mode
1. **INIT**: Creates workspace, detects creation mode
2. **CREATE**: Spawns context-engineer to create initial resource draft
3. **RESEARCH**: Investigates domain best practices
4. **RESEARCH_ITERATE**: Agentic optimization using research findings and LLM self-critique
5. **EVALUATE**: Assesses results, recommends accept/refine/reject
6. **FINALIZE**: Applies recommendation

## Output

Results saved to `workspace/{resource_id}/`:
- `run_state.json` - Current state (supports resume)
- `{resource_id}-v{N}.md` - Optimized version
- `reviews/v{N}_review.md` - Evaluation report

## Resume

If optimization was interrupted, simply re-run the same command - it will resume from the last checkpoint.
