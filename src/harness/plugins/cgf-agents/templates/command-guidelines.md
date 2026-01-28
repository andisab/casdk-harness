# Slash Command Optimization Guidelines

This document provides guidelines for creating and optimizing slash commands in the Claude Code ecosystem. Use these guidelines during CGF optimization to improve command quality.

## What Makes a Good Slash Command

### 1. Clear Purpose

**Good:**
- Single, well-defined action
- Name clearly indicates function
- Focused scope (do one thing well)

**Avoid:**
- Commands that try to do too many things
- Vague or generic names
- Overlapping functionality with other commands

### 2. Structure Requirements

```markdown
---
description: Short (1 sentence) explanation shown in /help
argument-hint: <required-arg> [optional-arg]
allowed-tools: Read, Write, Bash(git:*)
model: sonnet
---

[Command prompt content with $1, $2, $ARGUMENTS placeholders]
```

#### Frontmatter Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `description` | Recommended | Brief explanation for /help listing |
| `argument-hint` | Recommended | Shows expected arguments to user |
| `allowed-tools` | Optional | Restricts available tools for security |
| `model` | Optional | Override model (haiku/sonnet/opus) |
| `disable-model-invocation` | Optional | Prevent SlashCommand tool from calling |

### 3. Argument Handling

**Positional Arguments:**
- Use `$1`, `$2`, `$3` for ordered arguments
- Document required vs optional in `argument-hint`
- Use `<angle>` for required, `[brackets]` for optional

**Default Values:**
- Use `${1:-default}` syntax for defaults
- Provide sensible defaults for optional args
- Document defaults in help text

**Full Arguments:**
- Use `$ARGUMENTS` for all user input as single string
- Best for free-form text inputs
- Avoid combining with positional args

**Examples:**
```markdown
# Positional with defaults
Deploy to ${1:-staging} environment with ${2:-fast} mode

# File reference
Review the code in: @$1

# Full arguments for free-form input
Please analyze: $ARGUMENTS
```

### 4. File References

Use `@file` syntax to include file contents:
- `@src/app.py` - Static file reference
- `@$1` - File from argument
- Multiple files separated by sections

**Best Practices:**
- Always describe what the file will be used for
- Handle missing files gracefully in prompt text
- Use Glob for pattern matching, not @

### 5. Bash Execution

Use `!command` prefix for bash:
- Requires `allowed-tools: Bash(command:*)` in frontmatter
- Use specific patterns, not wildcards
- Chain related commands with `&&`

**Security:**
```yaml
# Good - specific commands
allowed-tools: Bash(git:*), Bash(npm:test)

# Avoid - too broad
allowed-tools: Bash(*)
```

### 6. Help Text Quality

**Good help text:**
- Explains what the command does (not how)
- Shows example usage
- Documents all arguments
- Notes any prerequisites

**Example:**
```markdown
---
description: Run tests with coverage report and fix failing tests
argument-hint: [--fix] [--verbose]
---
```

## Optimization Criteria

When optimizing a command, evaluate against these criteria:

### Usability Criteria

| Criterion | Weight | Indicators |
|-----------|--------|------------|
| **Clarity** | High | Users understand purpose from name + help |
| **Discoverability** | Medium | Appears in relevant /help searches |
| **Learnability** | Medium | New users succeed on first try |
| **Memorability** | Low | Users remember syntax between uses |

### Technical Criteria

| Criterion | Weight | Indicators |
|-----------|--------|------------|
| **Argument Handling** | High | All documented patterns work correctly |
| **Error Messages** | High | Failures explain what went wrong |
| **Output Quality** | Medium | Results are well-formatted and useful |
| **Performance** | Low | Command completes in reasonable time |

### Safety Criteria

| Criterion | Weight | Indicators |
|-----------|--------|------------|
| **Tool Restrictions** | High | Only necessary tools are allowed |
| **Bash Scoping** | High | Bash patterns are specific, not broad |
| **Destructive Guards** | Medium | Dangerous operations have confirmations |

## Common Optimization Patterns

### 1. Improve Argument Handling

**Before:**
```markdown
Analyze $1
```

**After:**
```markdown
---
argument-hint: <file-path>
---

Analyze the following file for issues:
@$1

If the file is not found, inform the user and suggest alternatives.
```

### 2. Add Error Guidance

**Before:**
```markdown
!git push
```

**After:**
```markdown
---
allowed-tools: Bash(git:*)
---

Pushing changes to remote...

!git push

If push fails due to conflicts, explain the issue and suggest:
1. How to pull and merge
2. How to force push (with warnings)
```

### 3. Improve Output Structure

**Before:**
```markdown
Review this code: @$1
```

**After:**
```markdown
Review the code in @$1 and provide analysis in this format:

## Summary
Brief overview of code quality

## Issues Found
- **Issue 1**: Description
  - Location: file:line
  - Severity: high/medium/low
  - Fix: Suggested solution

## Recommendations
Prioritized list of improvements
```

### 4. Add Progress Feedback

**Before:**
```markdown
!npm run build
```

**After:**
```markdown
Building project...

!npm run build

Build complete. Summary:
- Output directory
- Bundle sizes
- Any warnings

If build failed, explain the error and suggest fixes.
```

## Anti-Patterns to Avoid

### 1. Undefined Arguments
```markdown
# Bad - $2 may be undefined
Compare $1 with $2
```

### 2. Broad Tool Permissions
```yaml
# Bad - too permissive
allowed-tools: Bash(*)
```

### 3. No Error Handling
```markdown
# Bad - no guidance on failure
!risky-command
```

### 4. Complex Logic in Commands
```markdown
# Bad - commands should be templates, not programs
If $1 is production then... else if $1 is staging...
```

### 5. Missing Help Text
```markdown
# Bad - no frontmatter
Do something with $1
```

## Test Cases for Commands

When generating tests for command optimization:

### Positive Tests
- Basic usage with required args
- Usage with optional args
- Edge cases (empty args, special characters)
- Help text accuracy

### Negative Tests
- Missing required args
- Invalid argument values
- Tool permission boundaries
- Error message clarity

### Regression Tests
- Previously working patterns still work
- Output format consistency
- Performance within acceptable range

## Summary

Optimized commands should:

1. Have clear, focused purpose
2. Include complete frontmatter
3. Handle arguments robustly
4. Provide helpful error messages
5. Restrict tool access appropriately
6. Follow the template structure
7. Include usage examples

Use these guidelines during CGF optimization to ensure command quality improves consistently across iterations.
