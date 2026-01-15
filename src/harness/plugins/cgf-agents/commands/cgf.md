---
description: CGF (Claude Gradient Feedback) optimization command - start, resume, check status, or abort runs
allowed-tools: Read, Write, Bash, Task, Glob, Grep
argument-hint: <optimize|status|resume|abort> [args]
---

# CGF Command

Command interface for CGF (Claude Gradient Feedback) optimization pipeline.

## Subcommands

### optimize

Start a new optimization run:

```
/cgf optimize <resource> <goal> [--review] [--optimizer dspy|textgrad]
```

**Arguments:**
- `resource` - Resource to optimize (agent name, path, or namespaced)
- `goal` - Optimization objective
- `--review` - Enable checkpoint mode for human review
- `--optimizer` - Choose optimizer (default: dspy)

**Examples:**
```
/cgf optimize python-expert async programming
/cgf optimize typescript-expert better error handling --review
/cgf optimize research-team:research-specialist Context7 usage --optimizer textgrad
```

### status

Check status of current or recent optimization runs:

```
/cgf status [resource_id]
```

Shows:
- Current state
- Progress through phases
- Latest scores and metrics
- Time elapsed

**Examples:**
```
/cgf status                    # All active runs
/cgf status python-expert      # Specific run
```

### resume

Resume an interrupted optimization run:

```
/cgf resume <resource_id>
```

Continues from the last saved state in run_state.json.

**Example:**
```
/cgf resume python-expert
```

### abort

Cancel an in-progress optimization run:

```
/cgf abort <resource_id>
```

Sets state to COMPLETE with aborted flag and preserves all artifacts.

**Example:**
```
/cgf abort python-expert
```

### proceed

Continue from a checkpoint state (only valid during --review mode):

```
/cgf proceed
```

Approves the current checkpoint artifact and moves to next phase.

### edit

Mark checkpoint artifact as edited and re-run phase:

```
/cgf edit [artifact_path]
```

Use after manually editing eval_criteria.yaml, test_suite.yaml, etc.

## Checkpoint Commands

When in `--review` mode, the orchestrator pauses at checkpoints. Use these commands:

| Command | Action |
|---------|--------|
| `/cgf proceed` | Accept current artifact, continue to next phase |
| `/cgf edit` | Signal that you've edited the artifact, re-run validation |
| `/cgf abort` | Cancel the run, preserve current state |

## Workspace

All CGF runs create a workspace at `workspace/{resource_id}/`:

```
workspace/{resource_id}/
├── run_state.json         # State for resume
├── run_config.yaml        # Configuration
├── research/              # Research artifacts
├── tests/                 # Test suite
├── {resource_id}-v*.md    # Optimized versions
└── reviews/               # Evaluation reports
```

## Tips

1. **Use --review first time** to understand the pipeline
2. **Check status** if unsure about run progress
3. **Resume** works across sessions - just run same command
4. **Abort** is safe - all artifacts preserved for analysis
