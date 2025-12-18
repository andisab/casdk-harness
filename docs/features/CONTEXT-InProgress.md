# Agent and Skill System Optimization

**Date:** 2024-12-17
**Status:** Draft Specification
**Priority:** High
**Objective:** Improve discoverability, clarity, and performance of the agent/skill system

---

## Executive Summary

The current agent/skill system has clarity and discoverability issues that prevent optimal usage:

1. **Custom agents** (python-expert, k8s-engineer, etc.) exist but aren't discoverable in the system prompt
2. **Overlapping responsibilities** between skills and agents create confusion about when to use which
3. **No clear invocation mechanism** for custom agents through the Task tool
4. **Inconsistent metadata** across agent and skill definitions

This specification proposes a comprehensive reorganization and enhancement plan.

---

## Problem Analysis

### 1. Discovery Gap

**Current State:**
- System prompt lists base skills: `documentation`, `testing-strategies`, `api-development`, etc.
- Custom agents exist in `/app/src/harness/agents/configs/` but aren't listed
- Users don't know specialized agents like `python-expert` or `nodejs-expert` exist

**Impact:**
- Underutilization of specialized expertise
- Reliance on general-purpose problem solving when domain experts available
- Inconsistent quality of domain-specific responses

### 2. Invocation Mechanism Confusion

**Current Mechanisms:**
- Built-in agents: `Task(subagent_type="Explore", prompt="...")`
- Custom agents: **No clear invocation path** ❌
- Skills: `Skill(skill="debugging")` ✓

**Result:**
- Custom agents may be dead code if not invokable
- Unclear whether to create a skill vs agent for new capabilities

### 3. Overlapping Responsibilities

| Domain | Skill | Agent | Confusion Level |
|--------|-------|-------|-----------------|
| Code Review | `code-review` skill | `reviewer-agent` | High |
| Testing | `testing-strategies` skill | `testing-agent` | High |
| Debugging | `debugging` skill | None | Low |
| Python Development | None | `python-expert` | Medium |

### 4. Metadata Inconsistency

**Agent Definitions:**
```yaml
name: python-expert
description: >
  Long multi-line description with examples...
tools: Read, Write, MultiEdit, Bash, Grep, Glob, Context7
model: opus 4.1
color: "#458588"
```

**Skill Definitions:**
```yaml
---
name: debugging
description: Systematic debugging, troubleshooting, and problem-solving strategies
---
```

**Missing from both:**
- `when_to_use` criteria
- `when_not_to_use` anti-patterns
- `complexity` indicators
- `cost` considerations
- `auto_activate` triggers
- Consistent `related_skills` / `related_agents` links

---

## Proposed Solution

### Architecture: Three-Tier System

```
┌─────────────────────────────────────────────────────────┐
│                    Main Agent                           │
│              (General Conversational)                   │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Built-in   │  │   Domain     │  │  Reference   │
│  Subagents   │  │   Skills     │  │   Skills     │
│              │  │              │  │              │
│ • Explore    │  │ • python-dev │  │ • debugging  │
│ • Plan       │  │ • typescript │  │ • code-review│
│ • general    │  │ • kubernetes │  │ • git-flow   │
└──────────────┘  └──────────────┘  └──────────────┘
    (Task tool)    (Skill tool)      (Skill tool)
   Multi-step      Expert mode       Quick ref
   Autonomous      In conversation   Patterns
```

### Tier Definitions

#### Tier 1: Built-in Subagents (Task Tool)
**Purpose:** Autonomous multi-step work
**Invocation:** `Task(subagent_type="...", prompt="...")`
**Characteristics:**
- Can use tools independently
- Work in background
- Return results when complete
- Cost: Variable (haiku → opus)

**Available:**
- `general-purpose`: Complex multi-step tasks
- `Explore`: Fast codebase exploration
- `Plan`: Implementation planning

#### Tier 2: Domain Expert Skills (Skill Tool)
**Purpose:** Deep domain expertise during conversation
**Invocation:** `Skill(skill="...")`
**Characteristics:**
- Loads domain-specific context
- Used within main conversation
- Provides expert-level guidance
- Cost: Included in main conversation

**Proposed (migrate from agents):**
- `python-development`: FastAPI, async, Pydantic, SQLAlchemy
- `typescript-development`: Advanced typing, type-level programming
- `nodejs-development`: Event-driven, streaming, clustering
- `react-development`: React 19+, hooks, concurrent rendering
- `go-development`: Concurrency, idioms, performance
- `kubernetes-operations`: K8s orchestration, deployments
- `docker-operations`: Container optimization, compose
- `postgres-operations`: Database optimization, queries
- `gitlab-ci-operations`: Pipeline configuration, optimization
- `gcp-architecture`: Cloud infrastructure, GCP services

#### Tier 3: Reference Skills (Skill Tool)
**Purpose:** Quick patterns, checklists, best practices
**Invocation:** `Skill(skill="...")`
**Characteristics:**
- Lightweight reference material
- Workflows and templates
- Decision trees
- Cost: Minimal context

**Current:**
- `documentation`: Doc generation workflows
- `testing-strategies`: Test planning patterns
- `api-development`: API patterns and templates
- `code-review`: Review checklists and feedback
- `git-workflow`: Branch and commit strategies
- `debugging`: Systematic troubleshooting

---

## Implementation Plan

### Phase 1: Consolidation (Priority: HIGH)

#### 1.1 Migrate Custom Agents to Domain Expert Skills

**Action Items:**
- [ ] Create `/workspace/migration-plan.md` with detailed mapping
- [ ] Convert agent definitions to skill format
- [ ] Preserve all expertise from agent prompts
- [ ] Add standardized metadata
- [ ] Test skill invocation

**Agents to Migrate:**

| Current Agent | New Skill Name | Location |
|---------------|----------------|----------|
| `python-expert` | `python-development` | `/app/src/harness/skills/python-development/` |
| `typescript-expert` | `typescript-development` | `/app/src/harness/skills/typescript-development/` |
| `nodejs-expert` | `nodejs-development` | `/app/src/harness/skills/nodejs-development/` |
| `react-expert` | `react-development` | `/app/src/harness/skills/react-development/` |
| `go-expert` | `go-development` | `/app/src/harness/skills/go-development/` |
| `k8s-engineer` | `kubernetes-operations` | `/app/src/harness/skills/kubernetes-operations/` |
| `docker-engineer` | `docker-operations` | `/app/src/harness/skills/docker-operations/` |
| `postgres-expert` | `postgres-operations` | `/app/src/harness/skills/postgres-operations/` |
| `sql-expert` | `sql-development` | `/app/src/harness/skills/sql-development/` |
| `gitlab-ci-expert` | `gitlab-ci-operations` | `/app/src/harness/skills/gitlab-ci-operations/` |
| `gcp-cloud-architect` | `gcp-architecture` | `/app/src/harness/skills/gcp-architecture/` |
| `reviewer-agent` | *Merge into `code-review` skill* | `/app/src/harness/skills/code-review/` |
| `testing-agent` | *Merge into `testing-strategies` skill* | `/app/src/harness/skills/testing-strategies/` |
| `refactor-agent` | `refactoring-strategies` | `/app/src/harness/skills/refactoring-strategies/` |

**Migration Template:**

```markdown
---
name: python-development
description: Expert Python development with FastAPI, async patterns, Pydantic, and SQLAlchemy 2.0
type: skill
tier: domain-expert
category: development
complexity: advanced
model_recommendation: opus
auto_activate:
  keywords: [fastapi, pydantic, sqlalchemy, async python, type hints]
  file_patterns: ["**/*.py", "**/pyproject.toml", "**/requirements.txt"]
when_to_use:
  - Building FastAPI applications with async patterns
  - Converting untyped code to Pydantic models
  - Implementing SQLAlchemy 2.0 async patterns
  - Designing type-safe Python architectures
  - Optimizing async/await performance
when_not_to_use:
  - Simple Python scripts without frameworks
  - Data science/ML projects (use separate skill)
  - Basic syntax questions (use general knowledge)
related_skills: [api-development, testing-strategies, debugging]
estimated_context_size: large
---

# Python Development Expert

[PRESERVED CONTENT FROM AGENT DEFINITION]

## Quick Reference

### Common Patterns
- FastAPI async endpoints
- Pydantic model definitions
- SQLAlchemy 2.0 async queries
- Type hint examples

### Decision Trees
**When to use async vs sync:**
- ✅ Async: I/O operations (DB, HTTP, file)
- ❌ Async: CPU-bound operations
- ⚠️ Sync routes: FastAPI auto-threads them

### Troubleshooting
**Common Issues:**
1. Event loop blocking → Check for sync operations in async functions
2. Type errors → Verify Pydantic model definitions
3. N+1 queries → Use eager loading with selectinload()
```

#### 1.2 Enhance Reference Skills

**Action Items:**
- [ ] Add `when_to_use` / `when_not_to_use` sections
- [ ] Create quick reference sections
- [ ] Add decision trees
- [ ] Include troubleshooting guides
- [ ] Standardize metadata

**Skills to Enhance:**
- `debugging`
- `code-review`
- `testing-strategies`
- `api-development`
- `git-workflow`
- `documentation`

#### 1.3 Update System Prompt

**Location:** `/app/src/harness/.system/runtime-context.md`

**Add Section:**

```markdown
## Available Expertise

### Built-in Subagents (Task Tool)

Use for autonomous multi-step work:

- **general-purpose**: Complex tasks requiring research, planning, and implementation
  - *Example:* "Implement authentication system with tests"
- **Explore**: Fast codebase exploration and search
  - *Example:* "Find all API endpoints using FastAPI"
- **Plan**: Implementation planning before coding
  - *Example:* "Design architecture for caching layer"

### Domain Expert Skills (Skill Tool)

Use for deep expertise during conversation:

**Development:**
- **python-development**: FastAPI, Pydantic, SQLAlchemy, async patterns
- **typescript-development**: Advanced typing, generics, type-level programming
- **nodejs-development**: Node.js performance, event-driven architecture
- **react-development**: React 19+, hooks, concurrent rendering
- **go-development**: Concurrency, idioms, interface design
- **sql-development**: Complex queries, optimization, indexing

**Infrastructure:**
- **kubernetes-operations**: K8s orchestration, deployments, scaling
- **docker-operations**: Container optimization, multi-stage builds
- **postgres-operations**: PostgreSQL tuning, replication, optimization
- **gitlab-ci-operations**: CI/CD pipeline configuration
- **gcp-architecture**: Google Cloud infrastructure and services

### Reference Skills (Skill Tool)

Use for quick patterns and best practices:

- **debugging**: Systematic troubleshooting workflows
- **code-review**: Review checklists and feedback techniques
- **testing-strategies**: Test planning and implementation patterns
- **api-development**: REST/GraphQL API patterns
- **git-workflow**: Branch strategies and commit conventions
- **documentation**: Documentation generation workflows

## Decision Tree: Choosing the Right Tool

### Use Task Tool (Subagents) When:
- ✅ User asks to **implement** or **build** something
- ✅ Work requires **multiple files** and **multiple steps**
- ✅ Need to **search, analyze, plan, then execute**
- ✅ Can work **autonomously** in background
- ❌ NOT for: Simple questions, code review, quick advice

### Use Skill Tool When:
- ✅ Need **domain expertise** during conversation
- ✅ Want to **review or improve** existing code
- ✅ Need **patterns, examples, or best practices**
- ✅ Require **specialized knowledge** (e.g., FastAPI, K8s)
- ❌ NOT for: Multi-step implementation work

### Examples:

| User Request | Tool Choice | Reasoning |
|--------------|-------------|-----------|
| "Implement user authentication" | Task(general-purpose) | Multi-step implementation |
| "Find all async functions" | Task(Explore) | Codebase search |
| "Review this FastAPI code" | Skill(python-development) | Expert review needed |
| "Show me K8s deployment pattern" | Skill(kubernetes-operations) | Quick reference |
| "Fix this bug in user login" | Neither → Direct work | Simple focused task |
```

### Phase 2: Standardization (Priority: MEDIUM)

#### 2.1 Create Metadata Schema

**File:** `/app/src/harness/.system/metadata-schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Skill/Agent Metadata Schema",
  "type": "object",
  "required": ["name", "description", "type", "tier", "category"],
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z0-9-]+$",
      "description": "Kebab-case identifier"
    },
    "description": {
      "type": "string",
      "maxLength": 200,
      "description": "One-line summary"
    },
    "type": {
      "enum": ["skill", "agent"],
      "description": "Resource type"
    },
    "tier": {
      "enum": ["builtin-agent", "domain-expert", "reference"],
      "description": "Capability tier"
    },
    "category": {
      "enum": ["development", "infrastructure", "testing", "collaboration", "research"],
      "description": "Domain category"
    },
    "complexity": {
      "enum": ["simple", "moderate", "advanced", "expert"],
      "description": "Skill complexity level"
    },
    "model_recommendation": {
      "enum": ["haiku", "sonnet", "opus"],
      "description": "Recommended model for optimal performance"
    },
    "auto_activate": {
      "type": "object",
      "properties": {
        "keywords": {
          "type": "array",
          "items": {"type": "string"}
        },
        "file_patterns": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "when_to_use": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3
    },
    "when_not_to_use": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 2
    },
    "related_skills": {
      "type": "array",
      "items": {"type": "string"}
    },
    "estimated_context_size": {
      "enum": ["small", "medium", "large", "xlarge"],
      "description": "Approximate token size"
    },
    "examples": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["context", "user_request", "expected_action"],
        "properties": {
          "context": {"type": "string"},
          "user_request": {"type": "string"},
          "expected_action": {"type": "string"},
          "reasoning": {"type": "string"}
        }
      }
    }
  }
}
```

#### 2.2 Create Validation Script

**File:** `/workspace/scripts/validate-metadata.py`

```python
#!/usr/bin/env python3
"""Validate skill and agent metadata against schema."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jsonschema import validate, ValidationError


def load_schema() -> Dict[str, Any]:
    """Load metadata schema."""
    schema_path = Path("/app/src/harness/.system/metadata-schema.json")
    return json.loads(schema_path.read_text())


def extract_frontmatter(content: str) -> Dict[str, Any]:
    """Extract YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    return yaml.safe_load(parts[1])


def validate_skill_file(file_path: Path, schema: Dict[str, Any]) -> List[str]:
    """Validate a single skill/agent file."""
    errors = []

    try:
        content = file_path.read_text()
        metadata = extract_frontmatter(content)

        if not metadata:
            errors.append(f"No frontmatter found in {file_path}")
            return errors

        validate(instance=metadata, schema=schema)

    except ValidationError as e:
        errors.append(f"{file_path}: {e.message}")
    except Exception as e:
        errors.append(f"{file_path}: {str(e)}")

    return errors


def main():
    """Validate all skills and agents."""
    schema = load_schema()

    # Find all SKILL.md files
    harness_path = Path("/app/src/harness")
    skill_files = list(harness_path.glob("**/SKILL.md"))
    agent_files = list(harness_path.glob("agents/configs/*.md"))

    all_errors = []

    for file_path in skill_files + agent_files:
        errors = validate_skill_file(file_path, schema)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Validation failed:\n")
        for error in all_errors:
            print(f"  • {error}")
        sys.exit(1)
    else:
        print(f"✅ All {len(skill_files) + len(agent_files)} files validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

#### 2.3 Create Auto-Activation Logic

**File:** `/workspace/scripts/auto-activate-skills.py`

```python
#!/usr/bin/env python3
"""Auto-activate skills based on context."""

import re
from pathlib import Path
from typing import Dict, List, Set

import yaml


def load_all_skills() -> Dict[str, Dict]:
    """Load all skill metadata with auto_activate settings."""
    skills = {}
    harness = Path("/app/src/harness")

    for skill_file in harness.glob("**/SKILL.md"):
        content = skill_file.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            metadata = yaml.safe_load(parts[1])
            if "auto_activate" in metadata:
                skills[metadata["name"]] = metadata["auto_activate"]

    return skills


def detect_keywords(text: str, keywords: List[str]) -> bool:
    """Check if any keywords present in text."""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def detect_file_patterns(files: List[str], patterns: List[str]) -> bool:
    """Check if any files match patterns."""
    for file_path in files:
        for pattern in patterns:
            if Path(file_path).match(pattern):
                return True
    return False


def recommend_skills(user_message: str, context_files: List[str] = None) -> Set[str]:
    """Recommend skills to activate based on context."""
    skills = load_all_skills()
    recommended = set()
    context_files = context_files or []

    for skill_name, auto_config in skills.items():
        # Check keywords
        if "keywords" in auto_config:
            if detect_keywords(user_message, auto_config["keywords"]):
                recommended.add(skill_name)

        # Check file patterns
        if "file_patterns" in auto_config and context_files:
            if detect_file_patterns(context_files, auto_config["file_patterns"]):
                recommended.add(skill_name)

    return recommended


# Example usage
if __name__ == "__main__":
    test_message = "Help me build a FastAPI endpoint with Pydantic validation"
    test_files = ["app/main.py", "app/models.py"]

    recommended = recommend_skills(test_message, test_files)
    print(f"Recommended skills: {', '.join(recommended)}")
```

### Phase 3: Documentation (Priority: MEDIUM)

#### 3.1 Create Comprehensive Guide

**File:** `/workspace/docs/agent-skill-system-guide.md`

**Contents:**
- System architecture overview
- When to use Task vs Skill
- Complete reference of all capabilities
- Decision trees with examples
- Migration guide from agents to skills
- Troubleshooting common issues

#### 3.2 Create Visual Diagrams

**Files:**
- `/workspace/docs/diagrams/system-architecture.mmd` (Mermaid)
- `/workspace/docs/diagrams/decision-tree.mmd` (Mermaid)
- `/workspace/docs/diagrams/skill-relationships.mmd` (Mermaid)

#### 3.3 Create Quick Reference Card

**File:** `/workspace/docs/quick-reference.md`

One-page cheat sheet for developers.

### Phase 4: Testing & Validation (Priority: HIGH)

#### 4.1 Integration Tests

**File:** `/workspace/tests/test_skill_invocation.py`

```python
"""Test skill invocation and auto-activation."""

import pytest
from unittest.mock import Mock, patch


class TestSkillInvocation:
    """Test skill invocation mechanisms."""

    def test_python_skill_activates_on_fastapi_keyword(self):
        """Python skill should activate when FastAPI mentioned."""
        message = "Help me build a FastAPI application"
        skills = recommend_skills(message)
        assert "python-development" in skills

    def test_kubernetes_skill_activates_on_yaml_files(self):
        """K8s skill should activate for k8s YAML files."""
        files = ["deployment.yaml", "service.yaml"]
        skills = recommend_skills("Deploy this", files)
        assert "kubernetes-operations" in skills

    def test_no_duplicate_skills(self):
        """Should not recommend same skill multiple times."""
        message = "Python FastAPI Python async Python Pydantic"
        skills = recommend_skills(message)
        skill_list = list(skills)
        assert len(skill_list) == len(set(skill_list))


class TestMetadataValidation:
    """Test metadata validation."""

    def test_all_skills_have_required_fields(self):
        """All skills must have required metadata fields."""
        schema = load_schema()
        required = schema["required"]

        for skill_file in Path("/app/src/harness").glob("**/SKILL.md"):
            metadata = extract_frontmatter(skill_file.read_text())
            for field in required:
                assert field in metadata, f"{skill_file} missing {field}"

    def test_when_to_use_has_minimum_items(self):
        """when_to_use must have at least 3 examples."""
        for skill_file in Path("/app/src/harness").glob("**/SKILL.md"):
            metadata = extract_frontmatter(skill_file.read_text())
            if "when_to_use" in metadata:
                assert len(metadata["when_to_use"]) >= 3
```

#### 4.2 Manual Test Cases

**File:** `/workspace/tests/manual-test-cases.md`

```markdown
# Manual Test Cases

## Test Case 1: Python Expert Skill
**User:** "Review this FastAPI code for performance issues"
**Expected:** Skill(skill="python-development") invoked
**Validates:** Auto-activation, domain expertise

## Test Case 2: Kubernetes Deployment
**User:** "Help me deploy this app to Kubernetes"
**Expected:** Skill(skill="kubernetes-operations") invoked
**Validates:** Infrastructure expertise selection

## Test Case 3: Multi-Step Implementation
**User:** "Implement a complete authentication system with tests"
**Expected:** Task(subagent_type="general-purpose") launched
**Validates:** Task vs Skill distinction

## Test Case 4: Codebase Exploration
**User:** "Find all places where we make database queries"
**Expected:** Task(subagent_type="Explore") launched
**Validates:** Exploration agent usage

## Test Case 5: No Skill Needed
**User:** "What's the difference between list and tuple?"
**Expected:** Direct response, no skill/agent invoked
**Validates:** Avoiding unnecessary invocations
```

### Phase 5: Performance Optimization (Priority: LOW)

#### 5.1 Lazy Loading

Implement lazy loading for large skills to reduce initial context size.

#### 5.2 Skill Caching

Cache frequently used skill content to reduce load times.

#### 5.3 Context Size Monitoring

Add telemetry to track:
- Skill activation frequency
- Average context size per skill
- Performance impact on response time

---

## Success Metrics

### Primary Metrics
- **Discoverability:** System prompt lists all available capabilities ✅
- **Clarity:** Decision tree reduces confusion about Task vs Skill ✅
- **Consistency:** All skills/agents have standardized metadata ✅
- **Invocability:** All capabilities have clear invocation paths ✅

### Secondary Metrics
- **Activation Rate:** % of relevant queries that auto-activate skills
- **Accuracy:** % of skill invocations that are appropriate
- **Performance:** Average response time with skill activation
- **Coverage:** % of domain areas with expert skills

### Quality Indicators
- [ ] Zero ambiguity in Task vs Skill usage
- [ ] All skills pass metadata validation
- [ ] Documentation complete and accurate
- [ ] Integration tests pass 100%
- [ ] Manual test cases verified

---

## Risk Assessment

### High Risk
- **Breaking Changes:** Migration may break existing workflows
  - *Mitigation:* Maintain backward compatibility during transition
  - *Mitigation:* Thorough testing before deployment

### Medium Risk
- **Context Bloat:** Adding metadata increases context size
  - *Mitigation:* Lazy loading for large skills
  - *Mitigation:* Monitor token usage

### Low Risk
- **Learning Curve:** Users need to learn new system
  - *Mitigation:* Clear documentation with examples
  - *Mitigation:* Decision trees and quick reference

---

## Timeline

### Week 1: Consolidation
- Days 1-2: Migrate agents to skills
- Days 3-4: Update system prompt
- Day 5: Initial testing

### Week 2: Standardization
- Days 1-2: Create metadata schema
- Days 3-4: Apply to all skills
- Day 5: Validation scripts

### Week 3: Documentation & Testing
- Days 1-2: Write comprehensive guide
- Days 3-4: Integration tests
- Day 5: Manual testing

### Week 4: Optimization & Launch
- Days 1-2: Performance optimization
- Days 3-4: Final validation
- Day 5: Deployment

---

## Appendix

### A. Complete Skill Inventory

**Domain Expert Skills (Tier 2):**
1. python-development
2. typescript-development
3. nodejs-development
4. react-development
5. go-development
6. sql-development
7. kubernetes-operations
8. docker-operations
9. postgres-operations
10. gitlab-ci-operations
11. gcp-architecture

**Reference Skills (Tier 3):**
1. debugging
2. code-review
3. testing-strategies
4. api-development
5. git-workflow
6. documentation
7. refactoring-strategies

**Plugin Skills:**
1. context-engineering:hook-configuration
2. context-engineering:skill-creation
3. context-engineering:plugin-development
4. context-engineering:agent-definition-creation
5. context-engineering:command-creation
6. research-team:joplin-research

### B. Deprecated Agents

These agents will be deprecated after migration:
- python-expert → python-development skill
- typescript-expert → typescript-development skill
- nodejs-expert → nodejs-development skill
- react-expert → react-development skill
- go-expert → go-development skill
- k8s-engineer → kubernetes-operations skill
- docker-engineer → docker-operations skill
- postgres-expert → postgres-operations skill
- sql-expert → sql-development skill
- gitlab-ci-expert → gitlab-ci-operations skill
- gcp-cloud-architect → gcp-architecture skill
- reviewer-agent → merged into code-review skill
- testing-agent → merged into testing-strategies skill
- refactor-agent → refactoring-strategies skill

### C. Example Migration

**Before (Agent):**
```
/app/src/harness/agents/configs/dev-python-expert.md
```

**After (Skill):**
```
/app/src/harness/skills/python-development/
├── SKILL.md (main definition with enhanced metadata)
├── patterns/
│   ├── async-patterns.md
│   ├── pydantic-models.md
│   └── sqlalchemy-queries.md
├── workflows/
│   ├── api-development.md
│   └── database-migration.md
└── templates/
    ├── fastapi-starter.md
    └── pydantic-model-template.md
```

### D. References

- [Claude Agent SDK Documentation](https://docs.anthropic.com/)
- [Skill System Architecture](./docs/skill-architecture.md)
- [Task Tool Documentation](./docs/task-tool.md)
- [Metadata Schema](../src/harness/.system/metadata-schema.json)

---

**Document Version:** 1.0
**Last Updated:** 2024-12-17
**Next Review:** After Phase 1 completion
