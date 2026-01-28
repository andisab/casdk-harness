# Resource Type Decision Guide

When should you create an **Agent**, **Command**, **Skill**, or **Hook**? This guide provides clear decision criteria for choosing the right resource type.

## Quick Decision Tree

```
What are you building?
│
├─ A persistent persona with expertise? ──────────────► AGENT
│   (domain expert, specialist, architect)
│
├─ A quick one-shot action? ──────────────────────────► COMMAND
│   (run tests, deploy, commit)
│
├─ Reusable knowledge/templates for Claude? ──────────► SKILL
│   (formatting guidelines, domain patterns)
│
└─ Automated reactions to events? ────────────────────► HOOK
    (auto-format, validation, notifications)
```

## Resource Type Comparison

| Aspect | Agent | Command | Skill | Hook |
|--------|-------|---------|-------|------|
| **Invocation** | Claude decides | User types `/name` | Claude loads automatically | System triggers |
| **Persistence** | Conversation-scoped | Single execution | Knowledge-scoped | Event-scoped |
| **Complexity** | High (multi-turn) | Low (single action) | Medium (templates) | Low (reactions) |
| **User Interaction** | Yes (dialogue) | Minimal | None | None |
| **State** | Maintains context | Stateless | Stateless | Stateless |

---

## Agents

### When to Create an Agent

✅ **Create an agent when:**
- You need a **domain expert** with specialized knowledge (Python, React, PostgreSQL)
- The task requires **multi-turn dialogue** and reasoning
- You want **consistent behavior** across conversations
- The assistant needs to **make decisions** within a domain
- Complex tasks that benefit from a **specific persona**

❌ **Don't create an agent when:**
- It's a simple one-shot action (use Command)
- You just need knowledge injection (use Skill)
- It's automated/triggered by events (use Hook)

### Agent Examples

| Good Agent | Why |
|------------|-----|
| `python-expert` | Domain expertise, multi-turn code review, architectural decisions |
| `postgres-architect` | Complex database design, query optimization, schema migrations |
| `security-auditor` | Systematic analysis, findings report, recommendations |

| Bad Agent | Better Alternative |
|-----------|-------------------|
| `run-tests-agent` | Command: `/test` |
| `format-code-agent` | Hook: PostToolUse on Write |
| `deploy-helper` | Command: `/deploy` |

### Agent Structure

```yaml
---
name: domain-expert
description: |
  Domain expert for X that helps with Y and Z.

  Example: "Review this database schema for performance issues"
  Example: "Help me design an API for user authentication"
model: sonnet
tools:
  - Read
  - Write
  - Bash(specific:commands)
max_turns: 100
---

[System prompt with domain expertise, principles, and approach]
```

---

## Commands

### When to Create a Command

✅ **Create a command when:**
- User needs a **quick, repeatable action**
- The task is **well-defined and bounded**
- Minimal or no decision-making required
- **Single execution** with clear output
- User explicitly triggers via `/name`

❌ **Don't create a command when:**
- It requires dialogue or clarification (use Agent)
- It's complex multi-step reasoning (use Agent)
- It should run automatically (use Hook)

### Command Examples

| Good Command | Why |
|--------------|-----|
| `/test` | Run tests - clear, bounded, repeatable |
| `/commit` | Create git commit - single action |
| `/deploy staging` | Deploy with argument - clear action |
| `/pr` | Create pull request - well-defined |

| Bad Command | Better Alternative |
|-------------|-------------------|
| `/code-review` | Agent: `code-review-expert` (needs dialogue) |
| `/architect-system` | Agent: `system-architect` (complex reasoning) |
| `/auto-format` | Hook: on file save |

### Command Structure

```yaml
---
description: Brief explanation for /help
argument-hint: <required> [optional]
allowed-tools: Read, Bash(git:*)
---

[Prompt template with $1, $2, $ARGUMENTS placeholders]
```

---

## Skills

### When to Create a Skill

✅ **Create a skill when:**
- Claude needs **domain knowledge** to apply consistently
- You have **templates, patterns, or guidelines** to inject
- Knowledge should **activate automatically** based on context
- Reusable across multiple conversations
- **No user invocation** needed

❌ **Don't create a skill when:**
- It needs to execute actions (use Command)
- It requires dialogue (use Agent)
- It's event-triggered (use Hook)

### Skill Examples

| Good Skill | Why |
|------------|-----|
| `joplin-research` | Formatting guidelines for Joplin notes |
| `api-design-patterns` | REST/GraphQL conventions |
| `testing-best-practices` | Test writing guidelines |
| `commit-message-format` | Commit message conventions |

| Bad Skill | Better Alternative |
|-----------|-------------------|
| `run-tests` | Command: `/test` |
| `postgres-expert` | Agent: `postgres-expert` |
| `auto-lint` | Hook: PostToolUse |

### Skill Structure

```
skills/my-skill/
├── SKILL.md           # Core instructions (auto-loaded)
├── examples/          # Example implementations
├── templates/         # Reusable templates
└── references/        # Reference documentation
```

---

## Hooks

### When to Create a Hook

✅ **Create a hook when:**
- Actions should happen **automatically**
- Triggered by **specific events** (tool calls, session events)
- No user decision needed
- **Side effects** (formatting, validation, logging)

❌ **Don't create a hook when:**
- User should decide when to run (use Command)
- It needs reasoning or dialogue (use Agent)
- It's knowledge injection (use Skill)

### Hook Examples

| Good Hook | Why |
|-----------|-----|
| `PostToolUse: Write → black/isort` | Auto-format Python files |
| `PreToolUse: Bash → validate` | Validate commands before execution |
| `PostSessionStart → load-context` | Initialize session state |

| Bad Hook | Better Alternative |
|----------|-------------------|
| `on-any-edit → review-code` | Agent: `code-review-expert` |
| `on-command → complex-workflow` | Command with explicit steps |

### Hook Structure

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": { "tool_name": "Write", "file_path": "*.py" },
      "command": "black $FILE && isort $FILE"
    }]
  }
}
```

---

## Decision Matrix

| Scenario | Agent | Command | Skill | Hook |
|----------|:-----:|:-------:|:-----:|:----:|
| Code review with feedback | ✅ | | | |
| Run test suite | | ✅ | | |
| Apply formatting guidelines | | | ✅ | |
| Auto-format on save | | | | ✅ |
| Database schema design | ✅ | | | |
| Deploy to environment | | ✅ | | |
| API design patterns | | | ✅ | |
| Security validation | ✅ | | | |
| Git commit creation | | ✅ | | |
| Code style conventions | | | ✅ | |
| Pre-commit checks | | | | ✅ |
| Architecture planning | ✅ | | | |

---

## Anti-Patterns

### 1. Agent That Should Be a Command

```markdown
# BAD: deploy-agent
---
name: deploy-agent
description: Deploys code to environments
---
Deploy to the specified environment...
```

**Why it's bad**: No dialogue needed, single action, user-triggered

**Better**: `/deploy <env>` command

### 2. Command That Should Be an Agent

```markdown
# BAD: /architect
---
description: Design system architecture
---
Design a complete system architecture for $ARGUMENTS
```

**Why it's bad**: Requires dialogue, complex reasoning, multi-turn

**Better**: `system-architect` agent

### 3. Skill That Should Be a Command

```markdown
# BAD: run-tests skill
When tests are mentioned, run the test suite...
```

**Why it's bad**: User should control when tests run

**Better**: `/test` command

### 4. Hook That Should Be an Agent

```json
// BAD: Complex code review on every edit
{
  "PostToolUse": [{
    "matcher": { "tool_name": "Write" },
    "command": "claude review-code $FILE"
  }]
}
```

**Why it's bad**: Code review needs reasoning and dialogue

**Better**: `code-review-expert` agent invoked explicitly

---

## Summary

| Resource | Key Question | Primary Use |
|----------|--------------|-------------|
| **Agent** | "Does this need expertise and dialogue?" | Domain specialists |
| **Command** | "Is this a quick, user-triggered action?" | One-shot tasks |
| **Skill** | "Is this knowledge Claude should apply?" | Guidelines, patterns |
| **Hook** | "Should this happen automatically?" | Side effects, automation |

When in doubt:
1. Start with **Command** for simple actions
2. Use **Agent** when dialogue is needed
3. Use **Skill** for knowledge injection
4. Use **Hook** for automation only
