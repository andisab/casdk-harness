# Resource Type Guide

Comprehensive guide for selecting and designing Claude Code resources. Use this guide when creating new resources or deciding between resource types for multi-resource specs.

---

## Quick Reference

| Resource | Use When | Scope | Invocation |
|----------|----------|-------|------------|
| **Agent** | Autonomous decision-making, multi-step workflows | Domain expertise | Task tool / direct_agent |
| **Skill** | Reusable domain knowledge, deterministic patterns | Specific capability | Auto-activation by context |
| **Command** | User entry points, workflow triggers | User action | `/command-name` |
| **Workflow** | Coordinated multi-agent pipelines | Multi-step process | Orchestrator-driven |
| **Plugin** | Bundled collection of components | Feature domain | Installation |
| **Hook** | Lifecycle events, automation triggers | Tool interception | Event-driven |
| **Template** | Reusable output schemas, starter patterns | Code generation | Reference/copy |

---

## Agent

### When to Use

- **Autonomous decision-making** that requires reasoning about multiple options
- **Multi-step workflows** with branching logic based on intermediate results
- **Domain expertise** that needs deep context and tool access
- **Orchestration** of other agents or complex tool sequences

### When NOT to Use

- Simple, deterministic transformations (use Skill instead)
- User-triggered one-shot actions (use Command instead)
- Passive knowledge reference (use Skill instead)
- Simple event responses (use Hook instead)

### Characteristics

| Aspect | Agent Behavior |
|--------|---------------|
| **Activation** | Explicit invocation via Task tool or direct_agent |
| **Context** | Isolated - receives task description, not full conversation |
| **Tools** | Has own tool access configured in definition |
| **Model** | Can specify different model than parent (sonnet/opus/haiku) |
| **Turns** | Can have multiple conversation turns (configurable max_turns) |
| **State** | No persistent state between invocations |

### Structure

```yaml
---
name: domain-expert
description: >
  [Domain] expert specializing in [specific capabilities].
  Use PROACTIVELY when [scenarios].

  Examples:
  <example>
  Context: User needs [specific task]
  user: "[Example request]"
  assistant: "I'll use the domain-expert agent to [specific action]"
  <commentary>
  [Why this agent is appropriate]
  </commentary>
  </example>

tools: Read, Write, Edit, Bash(git:*)
model: sonnet
max_turns: 100
---

# Domain Expert

You are a [role] specializing in [domain].

## Core Responsibilities

- [Specific responsibility 1]
- [Specific responsibility 2]

## Approach

When [scenario]:
1. [Step with example]
2. [Step with example]

## Constraints

- [Boundary 1]
- [Boundary 2]

## Examples

### [Scenario Name]

[Detailed example with input/output]
```

### Examples

- **iac-analyzer** - Analyzes repositories to understand structure and dependencies
- **cgf-orchestrator** - Coordinates multi-phase optimization workflows
- **research-lead** - Plans and coordinates research across multiple specialists

### Single vs Multiple

| Scenario | Recommendation |
|----------|----------------|
| One domain, focused task | Single agent |
| Related domains, shared context | Single agent with sections |
| Distinct domains, different tools | Multiple agents |
| Pipeline stages, handoff | Multiple agents |

---

## Skill

### When to Use

- **Reusable domain knowledge** that applies across multiple contexts
- **Deterministic patterns** with clear trigger conditions
- **Reference documentation** that should load on-demand
- **Code templates** or best practices that get applied consistently

### When NOT to Use

- Complex reasoning or multi-step decisions (use Agent instead)
- User-triggered explicit actions (use Command instead)
- Tool interception or automation (use Hook instead)
- Bundling multiple components (use Plugin instead)

### Characteristics

| Aspect | Skill Behavior |
|--------|----------------|
| **Activation** | Automatic when context matches trigger terms |
| **Context** | Injected into current conversation |
| **Tools** | Uses parent agent's tools |
| **Model** | Uses parent agent's model |
| **Turns** | Single injection, no separate turns |
| **State** | No state - pure context injection |

### Structure

```
skill-name/
├── SKILL.md              # Main skill definition (required)
├── examples/             # Usage examples (optional)
│   ├── basic-usage.md
│   └── advanced-patterns.md
├── templates/            # Code templates (optional)
│   └── code-template.py
└── references/           # Reference docs (optional)
    └── api-docs.md
```

**SKILL.md Format:**

```yaml
---
name: skill-name
description: >
  [What it does]

  Activate when user mentions: [trigger terms]

  Use for: [scenarios]
  Do NOT use for: [out of scope]
---

# Skill Name

## Capabilities

- [Capability 1]
- [Capability 2]

## Usage

1. [Instruction]
2. [Instruction]

## Patterns

### [Pattern Name]

[Pattern description with example]

## Examples

See `examples/` directory for detailed usage.
```

### Examples

- **kubernetes-native** - K8s manifest patterns and best practices
- **joplin-research** - Formatting guidelines for Joplin notes
- **agent-definition-creation** - Instructions for creating agents

### Single vs Multiple (Skill Sets)

| Scenario | Recommendation |
|----------|----------------|
| One cohesive capability | Single SKILL.md |
| Variants of same capability | Multiple skills (terraform-{aws,gcp,azure}) |
| Unrelated capabilities | Separate plugins or standalone skills |
| Progressive detail | Single skill with examples/ directory |

---

## Command

### When to Use

- **User-triggered actions** with explicit `/command` invocation
- **Workflow entry points** that kick off multi-step processes
- **Parameterized operations** with arguments
- **Shortcuts** for frequently-used agent invocations

### When NOT to Use

- Autonomous behavior based on context (use Skill instead)
- Complex multi-turn reasoning (use Agent instead)
- Event-driven automation (use Hook instead)

### Characteristics

| Aspect | Command Behavior |
|--------|-----------------|
| **Activation** | Explicit `/command-name` by user |
| **Context** | Full current conversation available |
| **Arguments** | $1, $2, $ARGUMENTS, @file, !command |
| **Tools** | Uses allowed_tools configuration |
| **Model** | Uses current agent's model |
| **Turns** | Expands to prompt, then normal turn |

### Structure

```yaml
---
name: command-name
description: Short description shown in /help
allowed_tools: Read, Edit, Bash(git:*)
---

# Command Template

When this command is invoked with: /command-name $ARGUMENTS

## Parameters

- `$1` - First argument (required): [description]
- `$2` - Second argument (optional): [description]
- `${2:-default}` - With default value

## Procedure

1. [Step 1]
2. [Step 2]

## Examples

### Example: /command-name arg1

[Expected behavior]
```

### Examples

- **/commit** - Create git commit with conventional format
- **/cgf** - Entry point for CGF optimization
- **/iac** - IaC generation workflow trigger

### Single vs Multiple

| Scenario | Recommendation |
|----------|----------------|
| One action, optional args | Single command |
| Related actions, shared context | Single command with subcommands |
| Distinct unrelated actions | Multiple commands |

---

## Workflow

### When to Use

- **Multi-stage pipelines** with ordered execution
- **Agent coordination** with handoff between specialists
- **Dependency management** between steps
- **Resumable processes** with checkpointing

### When NOT to Use

- Single-agent tasks (use Agent directly)
- Simple sequential commands (use Command instead)
- Parallel independent tasks (use multiple Agents instead)

### Characteristics

| Aspect | Workflow Behavior |
|--------|------------------|
| **Activation** | Orchestrator-driven or command-triggered |
| **Context** | Shared workspace, artifact-based communication |
| **Agents** | Coordinates multiple specialized agents |
| **State** | Persisted in task_list.json or similar |
| **Resumption** | Supports pause/resume at stage boundaries |

### Structure

```yaml
# workflow-spec.yaml
name: research-pipeline
description: Multi-stage research workflow

stages:
  - name: discovery
    agent: research-lead
    inputs:
      - topic
    outputs:
      - research-plan.yaml

  - name: investigation
    agent: research-specialist
    parallel: true
    inputs:
      - research-plan.yaml
    outputs:
      - findings/*.yaml

  - name: synthesis
    agent: report-writer
    depends_on:
      - investigation
    inputs:
      - findings/*.yaml
    outputs:
      - report.md

checkpoints:
  - after: discovery
  - after: investigation
```

### Examples

- **CGF optimization pipeline** - RESEARCH → Q&A → GENERATE → ITERATE → VALIDATE
- **Research pipeline** - Discovery → Investigation → Synthesis
- **Code review workflow** - Analyze → Review → Report

---

## Plugin

### When to Use

- **Bundling related components** (agents + skills + commands)
- **Distribution** of reusable functionality
- **Team standardization** of workflows
- **Domain packages** with cohesive capabilities

### When NOT to Use

- Single standalone component (just create that component)
- Temporary experimental features
- User-specific customizations (use settings instead)

### Characteristics

| Aspect | Plugin Behavior |
|--------|----------------|
| **Activation** | Installation registers all components |
| **Components** | Agents, skills, commands, hooks, templates |
| **Configuration** | Via plugin.json and settings |
| **Dependencies** | Can depend on other plugins |
| **Distribution** | npm, git, local path |

### Structure

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json           # Required: metadata
├── agents/                   # Optional
│   └── *.md
├── skills/                   # Optional
│   └── */SKILL.md
├── commands/                 # Optional
│   └── *.md
├── hooks/                    # Optional
│   └── hooks-config.json
├── templates/                # Optional
│   └── */
├── patterns/                 # Optional
│   └── *.md
└── README.md                 # Recommended
```

### Examples

- **context-engineering** - Agent + skills for resource creation
- **research-team** - Multiple coordinated research agents
- **cgf-agents** - Optimization pipeline agents

---

## Hook

### When to Use

- **Lifecycle automation** (pre/post tool execution)
- **Tool interception** for filtering or validation
- **Notification** on specific events
- **Code quality** automation (formatting, linting)

### When NOT to Use

- Complex conditional logic (use Agent instead)
- User-triggered actions (use Command instead)
- Content injection (use Skill instead)

### Characteristics

| Aspect | Hook Behavior |
|--------|--------------|
| **Activation** | Event-driven (PreToolUse, PostToolUse, etc.) |
| **Execution** | Shell command or script |
| **Blocking** | PreToolUse can block tool execution |
| **Matchers** | tool_name, file patterns, arg patterns |
| **Security** | Runs with user permissions |

### Structure

```json
{
  "hooks": [
    {
      "event": "PostToolUse",
      "matchers": [
        { "tool_name": "Write", "file_path": "*.py" }
      ],
      "command": "black $FILE_PATH"
    }
  ]
}
```

### Events

| Event | Trigger | Can Block |
|-------|---------|-----------|
| PreToolUse | Before tool execution | Yes |
| PostToolUse | After tool execution | No |
| Notification | Custom events | No |
| Stop | Session end | No |

### Examples

- **Auto-format** - Format code after Write/Edit
- **Pre-commit** - Run checks before git commit
- **Security scan** - Block writes to sensitive files

---

## Template

### When to Use

- **Reusable output schemas** for generated content
- **Starter patterns** users can copy and customize
- **Code scaffolding** for new projects
- **Report formats** with consistent structure

### When NOT to Use

- Active code generation (use Agent or Skill instead)
- User documentation (put in README/docs instead)
- Configuration (use config files instead)

### Characteristics

| Aspect | Template Behavior |
|--------|------------------|
| **Activation** | Referenced by agents/skills during generation |
| **Execution** | None - pure reference material |
| **Variables** | May include placeholders for substitution |
| **Location** | templates/ directory in plugins |

### Structure

```
templates/
├── report-template/
│   ├── README.md          # How to use this template
│   ├── template.md        # The template with placeholders
│   └── example.md         # Example of filled template
└── code-scaffold/
    ├── README.md
    └── files/
        ├── src/
        │   └── main.py
        ├── tests/
        │   └── test_main.py
        └── pyproject.toml
```

---

## Decision Matrix

Use this matrix to select the right resource type:

| Need | Autonomous? | Multi-turn? | User-triggered? | → Resource |
|------|-------------|-------------|-----------------|------------|
| Domain expertise | Yes | Yes | No | **Agent** |
| Pattern reference | No | No | No | **Skill** |
| User action | No | Maybe | Yes | **Command** |
| Multi-step pipeline | Yes | Yes | Maybe | **Workflow** |
| Component bundle | - | - | - | **Plugin** |
| Event automation | No | No | No | **Hook** |
| Reusable structure | No | No | No | **Template** |

### Complex Scenarios

**"I need expertise that activates automatically"**
→ Use **Skill** for context injection, or **Agent** with discovery-optimized description

**"I need a multi-agent pipeline"**
→ Use **Workflow** to define stages, each stage uses an **Agent**

**"I need user-triggered complex reasoning"**
→ Use **Command** that invokes an **Agent**

**"I need to bundle everything for my team"**
→ Create a **Plugin** containing agents, skills, commands

**"I need post-save formatting"**
→ Use **Hook** with PostToolUse event

---

## Multi-Resource Patterns

### Plugin Pattern

When creating a multi-resource plugin:

1. **Identify core capabilities** → Map to agents
2. **Extract shared knowledge** → Map to skills
3. **Define entry points** → Map to commands
4. **Add automation** → Map to hooks
5. **Bundle together** → Create plugin

### Skill Set Pattern

When creating related skills:

1. **Identify base capability** → Core skill
2. **Identify variants** → Variant skills (aws, gcp, azure)
3. **Share common content** → Use references/
4. **Link together** → Same plugin or directory

### Workflow Pattern

When creating a pipeline:

1. **Define stages** → Each stage = one agent
2. **Define artifacts** → Outputs that flow between stages
3. **Define dependencies** → Which stages block others
4. **Add checkpoints** → Where to save state
5. **Add entry command** → How users trigger it

---

## Quality Checklist

### Agent Quality

- [ ] Discovery-optimized description with examples
- [ ] Focused single responsibility
- [ ] Minimal necessary tool access
- [ ] Clear constraints and boundaries
- [ ] Working code examples

### Skill Quality

- [ ] Specific trigger terms in description
- [ ] Clear "Use for" / "Do NOT use for"
- [ ] Progressive disclosure (SKILL.md → examples/)
- [ ] Patterns with concrete examples
- [ ] Tested autonomous activation

### Command Quality

- [ ] Clear argument documentation
- [ ] Default values for optional args
- [ ] Error handling guidance
- [ ] Usage examples
- [ ] Appropriate allowed_tools

### Plugin Quality

- [ ] Complete plugin.json
- [ ] README with installation instructions
- [ ] All components properly namespaced
- [ ] No naming conflicts
- [ ] Documented dependencies

---

## References

- `templates/subagent-template.md` - Agent structure
- `templates/skill-template.md` - Skill structure
- `templates/slash-command-template.md` - Command structure
- `templates/plugin-structure.md` - Plugin layout
- `templates/hook-configuration-template.md` - Hook examples
- `patterns/progressive-disclosure.md` - Token management
- `patterns/multi-agent-orchestration.md` - Agent coordination
