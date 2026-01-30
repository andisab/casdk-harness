# Agent vs Skill Content Separation

Guidelines for deciding when content belongs in an agent definition vs a skill, based on Anthropic's official context engineering best practices.

---

## Key Research Sources

- [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Anthropic)
- [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) (Anthropic)
- [Complete Guide to Claude Skills](https://tylerfolkman.substack.com/p/the-complete-guide-to-claude-skills) (Tyler Folkman)
- [Prompt Engineering Overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)

---

## Core Principle: Progressive Disclosure

Context is loaded in three levels to minimize token usage:

| Level | Content | Tokens | When Loaded |
|-------|---------|--------|-------------|
| **1. Metadata** | Name + description only | ~30-50/skill | Session start |
| **2. Triggered** | Full SKILL.md | <5,000 | When Claude determines relevance |
| **3. Active** | examples/, templates/, references/ | Variable | On-demand |

**Key insight**: "You can make dozens of Skills available without bloating your context window."

---

## Decision Matrix: Agent vs Skill

| Content Type | Agent? | Skill? | Rationale |
|--------------|--------|--------|-----------|
| Role definition | Yes | No | Core identity, always loaded |
| Multi-turn reasoning | Yes | No | Requires persistent context |
| Tool selection logic | Yes | No | Part of agent orchestration |
| Handoff protocols | Yes | No | Coordination responsibility |
| 2-4 canonical examples | Yes | No | Discovery optimization |
| Multi-page code snippets | No | Yes | Reusable, token-heavy |
| API specifications | No | Yes/Ref | Reference on demand |
| Step-by-step procedures | No | Yes | Deterministic, reusable |
| Domain best practices | No | Yes | Shared across contexts |
| Code templates | No | Yes | Reference when needed |

---

## Agent Definition Guidelines

### DO Include

- **Clear role definition** (1-2 paragraphs)
- **Discovery-optimized description** with trigger phrases
- **2-4 canonical examples** with commentary
- **Tool access list** (least privilege)
- **Constraints and boundaries**
- **References to skills** for detailed patterns

### DO NOT Include

- Multi-page code examples (extract to skills)
- Complete API specifications (use references/)
- Step-by-step procedures with 10+ steps (use skills)
- Domain expertise that other agents could reuse

### Agent Reference Pattern

Replace embedded content with references:

```markdown
## Python Async Patterns

For detailed async/await patterns and examples, load skill: python-async

## Error Handling

See `examples/error-handling.md` for comprehensive patterns
```

### Token Budget

| Component | Target |
|-----------|--------|
| Frontmatter | ~100 tokens |
| System prompt | 500-2,000 tokens |
| With all references loaded | OK if mostly references |

**Agent length 500-1000+ lines is FINE** as long as:
- Content is role/responsibility focused
- Code snippets are brief (illustrative, not exhaustive)
- Detailed patterns are referenced, not embedded

---

## Skill Definition Guidelines

### Structure

```
skill-name/
├── SKILL.md              # Core instructions (<5k tokens)
│   └── YAML frontmatter:
│       - name: skill-identifier
│       - description: Task-focused triggers
├── examples/             # Detailed usage (Level 3)
│   ├── basic-usage.md
│   └── advanced-patterns.md
├── templates/            # Code scaffolding (Level 3)
│   └── code-template.py
└── references/           # Specifications, API docs (Level 3)
    └── api-reference.md
```

### SKILL.md Requirements

1. **Frontmatter** (~50 tokens):
   ```yaml
   ---
   name: terraform-modules
   description: >
     Terraform module patterns for AWS, GCP, Azure.

     Activate when user mentions: terraform module, tf module,
     infrastructure module, reusable terraform, module registry

     Use for: Creating, structuring, publishing Terraform modules
     Do NOT use for: One-off resources, Pulumi, CloudFormation
   ---
   ```

2. **Core Instructions** (<5,000 tokens):
   - Capabilities list
   - Usage workflow
   - Key patterns with brief examples
   - **References** to examples/templates (NOT embedded content)

3. **Progressive Disclosure References**:
   ```markdown
   ## Examples
   See `examples/` directory:
   - `examples/aws-vpc-module.md` - VPC module with subnets
   - `examples/gcp-gke-module.md` - GKE cluster module

   ## Templates
   See `templates/` directory:
   - `templates/module-scaffold/` - Starter structure
   ```

### Description Quality

> "Description quality directly impacts activation reliability. Make descriptions specific to when Skills should activate."

**Good description**:
```
PDF extraction, form filling, document merging.

Activate when user mentions: PDF, form filling, document parsing,
extract tables, fill forms, merge PDFs
```

**Bad description**:
```
Helps with documents
```

---

## Migration Checklist

When reviewing existing agents for extraction to skills:

### 1. Identify Extraction Candidates

- [ ] Code snippets > 50 lines
- [ ] Step-by-step procedures with 10+ steps
- [ ] Domain patterns that could be reused
- [ ] API documentation or specifications
- [ ] Configuration reference tables

### 2. Create Skill Structure

- [ ] Create `skills/{name}/` directory
- [ ] Write SKILL.md with proper frontmatter
- [ ] Move detailed content to examples/
- [ ] Move templates to templates/
- [ ] Move specifications to references/

### 3. Update Agent

- [ ] Replace embedded content with skill references
- [ ] Keep role definition and constraints
- [ ] Keep 2-4 illustrative examples
- [ ] Update description with skill mentions

### 4. Test Activation

- [ ] Verify skill activates on trigger terms
- [ ] Verify examples load on demand
- [ ] Verify agent still discovers correctly

---

## Examples

### Before: Embedded Content

```markdown
# Python Expert Agent

## Async Patterns

### Pattern 1: Connection Pooling
[50 lines of Python code]

### Pattern 2: Error Handling
[40 lines of Python code]

### Pattern 3: Retry Logic
[35 lines of Python code]

### Pattern 4: Rate Limiting
[45 lines of Python code]
...
```

**Problem**: 500+ lines of code embedded in agent = wasted tokens when not needed.

### After: Skill Reference

**Agent** (focused):
```markdown
# Python Expert Agent

## Async Patterns

For comprehensive async patterns including connection pooling, error handling,
retry logic, and rate limiting, load skill: python-async-patterns

Key principle: Use asyncio.gather for concurrent operations, but implement
proper error boundaries to prevent cascade failures.
```

**Skill** (`skills/python-async-patterns/SKILL.md`):
```markdown
---
name: python-async-patterns
description: >
  Python async/await patterns for production applications.

  Activate when user mentions: asyncio, async await, connection pool,
  concurrent python, async error handling

  Use for: Implementing async patterns, optimizing concurrent code
  Do NOT use for: Sync-only applications, basic Python
---

# Python Async Patterns

## Available Patterns

See `examples/` for detailed implementations:
- `examples/connection-pooling.md`
- `examples/error-handling.md`
- `examples/retry-logic.md`
- `examples/rate-limiting.md`
```

---

## Token Optimization Strategies

From Anthropic's context engineering guide:

1. **Compaction**: Summarize conversation history, preserve architectural decisions

2. **Structured note-taking**: Persistent external notes (NOTES.md) for cross-session coherence

3. **Multi-agent architectures**: Subagents return condensed summaries (1,000-2,000 tokens)

4. **Progressive disclosure**: Load details only when needed

> "Rather than loading all data upfront, agents should maintain lightweight references and retrieve details dynamically at runtime."

---

## Quality Checklist

### Agent Quality
- [ ] Discovery-optimized description with examples
- [ ] Focused single responsibility
- [ ] Minimal necessary tool access
- [ ] Clear constraints and boundaries
- [ ] References to skills, not embedded walls of code

### Skill Quality
- [ ] Specific trigger terms in description
- [ ] Clear "Use for" / "Do NOT use for"
- [ ] Progressive disclosure (SKILL.md → examples/)
- [ ] SKILL.md < 5,000 tokens
- [ ] Tested autonomous activation

---

## Related Patterns

- `progressive-disclosure.md` - Token management and three-level loading
- `multi-agent-orchestration.md` - Coordination between agents
- `tool-restriction-patterns.md` - Least privilege for tool access

## Related Templates

- `../templates/skill-template.md` - Skill structure template
- `../templates/subagent-template.md` - Agent structure template
- `../templates/resource-type-guide.md` - Complete resource selection guide
