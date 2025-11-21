# Agent Implementation Reference

**Last Updated**: 2025-11-18
**Status**: Reference Material for Future Development

---

## Overview

This document contains reference material and alternative implementations for agent configuration in the Claude Agent SDK Harness. While **docs/IMPLEMENTATION.md** contains the chosen implementation plan (Phases 1-3), this document preserves research, alternative approaches, and implementation options that may be useful for future development. This document can be disregarded for current implementation effort and is mostly for informational and archival purposes. 

 ### Purpose

- **Preserve research** - Document all investigated approaches
- **Inform future decisions** - Provide context for architectural choices
- **Enable experimentation** - Reference implementations for alternative strategies
- **Support evolution** - Path forward for dynamic agent configuration

### Quick Links

- [**IMPLEMENTATION.md**](./AGENT_ARCH.md) - Current implementation plan (Phases 1-3)
- [**Custom Agent Loader**](#custom-agent-loader-implementation) - Alternative to hard-coded agents
- [**Alternative Approaches**](#alternative-approaches) - 5 additional implementation strategies
- [**Comparison Matrix**](#comparison-matrix) - Tradeoff analysis
- [**Recommendations**](#recommendations) - Decision criteria and guidance

---

## Table of Contents

- [Custom Agent Loader Implementation](#custom-agent-loader-implementation)
- [Alternative Approaches](#alternative-approaches)
  - [Alternative 1: SDK's Native agents Parameter](#alternative-1-sdks-native-agents-parameter)
  - [Alternative 2: Agents as Reference Documentation](#alternative-2-agents-as-reference-documentation)
  - [Alternative 3: Compile All Agents into Mega-Prompt](#alternative-3-compile-all-agents-into-mega-prompt)
  - [Alternative 4: Dynamic Loading on Demand](#alternative-4-dynamic-loading-on-demand)
  - [Alternative 5: Convert Agents to Skills](#alternative-5-convert-agents-to-skills)
- [Comparison Matrix](#comparison-matrix)
- [Recommendations](#recommendations)

---

## Custom Agent Loader Implementation

**Timeline**: 2-3 hours
**Complexity**: Medium
**Risk**: Low-Medium

### Overview

Create a parser to load agent definitions from `.claude/agents/*.md` files and make them available to the running agent. This enables all 44 existing agent definitions to be used with runtime selection.

**Note**: This approach was considered but **not chosen** for the Phase 1-3 implementation. The hard-coded approach (Alternative 6 in IMPLEMENTATION.md) was selected instead for better SDK alignment. This implementation is preserved here for reference and potential future use.

### Architecture

```
.claude/agents/*.md
    ↓
AgentDefinitionLoader.load_all()
    ↓
Parse YAML frontmatter + markdown body
    ↓
Store in runtime registry
    ↓
Agent selects definition at runtime
```

### Implementation Steps

#### 1. Create Agent Definition Parser

**File**: `src/harness/agents/parser.py`

```python
"""Agent definition parser for .claude/agents/*.md files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import yaml


@dataclass
class AgentDefinition:
    """Parsed agent definition from .claude/agents/*.md file."""

    name: str
    description: str
    tools: List[str]
    model: str
    system_prompt: str
    color: Optional[str] = None
    source_file: Optional[Path] = None


class AgentDefinitionLoader:
    """Load and parse agent definitions from markdown files."""

    def __init__(self, agents_dir: Path):
        """Initialize loader with agents directory."""
        self.agents_dir = agents_dir
        self._definitions: Dict[str, AgentDefinition] = {}

    def load_all(self) -> Dict[str, AgentDefinition]:
        """Load all agent definitions from .claude/agents/*.md files."""
        if self._definitions:
            return self._definitions

        for md_file in self.agents_dir.glob("*.md"):
            try:
                definition = self._parse_agent_file(md_file)
                self._definitions[definition.name] = definition
            except Exception as e:
                # Log but don't fail - skip invalid files
                print(f"Warning: Failed to parse {md_file}: {e}")

        return self._definitions

    def get_definition(self, name: str) -> Optional[AgentDefinition]:
        """Get agent definition by name."""
        if not self._definitions:
            self.load_all()
        return self._definitions.get(name)

    def list_agents(self) -> List[str]:
        """List all available agent names."""
        if not self._definitions:
            self.load_all()
        return sorted(self._definitions.keys())

    def _parse_agent_file(self, file_path: Path) -> AgentDefinition:
        """Parse a single agent definition markdown file."""
        content = file_path.read_text()

        # Split frontmatter and body
        if not content.startswith("---"):
            raise ValueError(f"No YAML frontmatter in {file_path}")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid frontmatter format in {file_path}")

        # Parse YAML frontmatter
        frontmatter = yaml.safe_load(parts[1])
        system_prompt = parts[2].strip()

        # Extract required fields
        return AgentDefinition(
            name=frontmatter["name"],
            description=frontmatter["description"],
            tools=frontmatter.get("tools", "").split(", ") if isinstance(frontmatter.get("tools"), str) else frontmatter.get("tools", []),
            model=frontmatter.get("model", "sonnet"),
            system_prompt=system_prompt,
            color=frontmatter.get("color"),
            source_file=file_path,
        )
```

#### 2. Create Agent Registry

**File**: `src/harness/agents/registry.py`

```python
"""Runtime agent registry for managing loaded agent definitions."""

from pathlib import Path
from typing import Dict, Optional
import structlog

from .parser import AgentDefinition, AgentDefinitionLoader

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """Global registry for agent definitions."""

    _instance: Optional["AgentRegistry"] = None

    def __init__(self, agents_dir: Path):
        """Initialize registry with agents directory."""
        self.agents_dir = agents_dir
        self.loader = AgentDefinitionLoader(agents_dir)
        self._definitions: Dict[str, AgentDefinition] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls, agents_dir: Optional[Path] = None) -> "AgentRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            if agents_dir is None:
                agents_dir = Path.cwd() / ".claude" / "agents"
            cls._instance = cls(agents_dir)
        return cls._instance

    def load_agents(self) -> None:
        """Load all agent definitions from disk."""
        if self._loaded:
            return

        logger.info("Loading agent definitions", agents_dir=str(self.agents_dir))
        self._definitions = self.loader.load_all()
        self._loaded = True

        logger.info(
            "Agent definitions loaded",
            count=len(self._definitions),
            agents=list(self._definitions.keys())
        )

    def get_definition(self, name: str) -> Optional[AgentDefinition]:
        """Get agent definition by name."""
        if not self._loaded:
            self.load_agents()
        return self._definitions.get(name)

    def list_agents(self) -> list[str]:
        """List all available agent names."""
        if not self._loaded:
            self.load_agents()
        return sorted(self._definitions.keys())

    def get_all_definitions(self) -> Dict[str, AgentDefinition]:
        """Get all loaded agent definitions."""
        if not self._loaded:
            self.load_agents()
        return self._definitions.copy()
```

#### 3. Update AgentSession to Use Registry

**File**: `src/harness/agent.py`

**Add at top**:
```python
from harness.agents.registry import AgentRegistry
```

**Update __init__ method**:
```python
def __init__(
    self,
    agent_name: str = "main",
    config: HarnessConfig | None = None,
    checkpoint_manager: CheckpointManager | None = None,
    metrics_collector: MetricsCollector | None = None,
) -> None:
    """Initialize agent session with definition loading."""
    self.agent_name = agent_name
    self.config = config or get_config()

    # Load agent registry
    self.registry = AgentRegistry.get_instance(
        agents_dir=Path(self.config.workspace_dir).parent / ".claude" / "agents"
    )
    self.registry.load_agents()

    # Get agent definition
    self.agent_definition = self.registry.get_definition(agent_name)
    if self.agent_definition is None:
        logger.warning(
            "No agent definition found, using defaults",
            agent=agent_name,
            available=self.registry.list_agents()
        )

    # ... rest of __init__
```

**Update _execute_with_retry to use agent definition**:
```python
async def _execute_with_retry(
    self,
    prompt: str,
    **kwargs: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute with agent-specific configuration."""

    # Get system prompt from agent definition
    system_prompt = None
    if self.agent_definition:
        system_prompt = self.agent_definition.system_prompt

    # Configure options
    options = ClaudeAgentOptions(
        allowed_tools=self.agent_definition.tools if self.agent_definition else ["Read", "Write", "Bash", "Grep", "Glob", "WebFetch", "Skill"],
        permission_mode=self.config.claude_permission_mode,
        max_turns=self.config.claude_max_turns,
        cwd=str(self.config.workspace_dir),
        model=self.agent_definition.model if self.agent_definition else self.config.claude_model,
        mcp_servers=self.mcp_servers,
        setting_sources=["user", "project"],
        system_prompt=system_prompt,
    )

    # ... rest of method
```

#### 4. Update Interactive Mode for Agent Selection

**File**: `src/harness/interactive.py`

**Add agent selection at startup**:
```python
def select_agent(console: Console, registry: AgentRegistry) -> str:
    """Prompt user to select an agent."""
    agents = registry.list_agents()

    if not agents:
        console.print("[yellow]No agent definitions found, using 'main'[/yellow]")
        return "main"

    console.print("\n[bold cyan]Available Agents:[/bold cyan]")
    for i, agent_name in enumerate(agents, 1):
        definition = registry.get_definition(agent_name)
        desc = definition.description[:80] + "..." if len(definition.description) > 80 else definition.description
        console.print(f"  {i}. [green]{agent_name}[/green]: {desc}")

    console.print("\nEnter agent name or number (default: main): ", end="")
    choice = input().strip()

    if not choice:
        return "main"

    # Parse choice
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(agents):
            return agents[idx]

    if choice in agents:
        return choice

    console.print(f"[yellow]Unknown agent '{choice}', using 'main'[/yellow]")
    return "main"


async def main(model: str | None = None, show_stats: bool = False, quiet: bool = False) -> None:
    """Run interactive session with agent selection."""
    # ... setup ...

    # Agent selection
    registry = AgentRegistry.get_instance()
    registry.load_agents()
    agent_name = select_agent(console, registry)

    # Create session with selected agent
    session = AgentSession(agent_name=agent_name, config=config)
    # ... rest of main ...
```

### Testing

```python
# tests/unit/test_agent_parser.py
import pytest
from pathlib import Path
from harness.agents.parser import AgentDefinitionLoader


def test_load_all_agents():
    """Test loading all agent definitions."""
    loader = AgentDefinitionLoader(Path(".claude/agents"))
    definitions = loader.load_all()

    assert len(definitions) > 0
    assert "python-expert" in definitions

    python_expert = definitions["python-expert"]
    assert python_expert.name == "python-expert"
    assert "Python" in python_expert.description
    assert len(python_expert.tools) > 0


def test_parse_agent_file():
    """Test parsing a single agent file."""
    loader = AgentDefinitionLoader(Path(".claude/agents"))
    definition = loader._parse_agent_file(Path(".claude/agents/dev-python-expert.md"))

    assert definition.name == "python-expert"
    assert definition.model in ["sonnet", "opus", "haiku"]
    assert definition.system_prompt.startswith("# ")
```

### Benefits

- ✅ All 44 existing agent definitions become usable
- ✅ Preserves existing markdown format
- ✅ Runtime agent selection in interactive mode
- ✅ Minimal changes to existing code

### Downsides

- ⚠️ Custom parsing code to maintain
- ⚠️ Not using SDK's native agent system
- ⚠️ Manual state management

### When to Use

Consider this implementation if:
- You MUST use all 44 existing agent definitions
- You want runtime agent selection in interactive mode
- You're comfortable maintaining custom parsing code
- SDK alignment is less important than preserving existing work

---

## Alternative Approaches

### Alternative 1: SDK's Native `agents` Parameter

**Description**: Use SDK's built-in multi-agent system with hard-coded AgentDefinition objects.

#### Implementation

```python
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

# Define 3-6 core agents
agents = {
    "python-expert": AgentDefinition(
        description="Expert Python developer for code review and implementation",
        tools=["Read", "Write", "MultiEdit", "Bash", "Grep", "Glob"],
        prompt="""You are an expert Python developer...""",
        model="sonnet"
    ),
    "devops-expert": AgentDefinition(
        description="Infrastructure and deployment specialist",
        tools=["Read", "Bash", "mcp__docker", "mcp__git"],
        prompt="""You are a DevOps specialist...""",
        model="haiku"
    ),
    "reviewer": AgentDefinition(
        description="Code review and security audit specialist",
        tools=["Read", "Grep", "Glob"],
        prompt="""You are a code reviewer...""",
        model="sonnet"
    ),
}

# Lead agent delegates via Task tool
options = ClaudeAgentOptions(
    system_prompt="You are a lead software architect. Delegate tasks to specialized agents using the Task tool.",
    allowed_tools=["Task"],  # Only delegation
    agents=agents,
    setting_sources=["project"],
    model="sonnet"
)
```

#### Pros

- ✅ Uses SDK's native multi-agent system
- ✅ Automatic delegation via Task tool
- ✅ No custom parsing required
- ✅ Follows official SDK patterns
- ✅ Clear separation of concerns

#### Cons

- ❌ Doesn't use existing 44 agent definitions
- ❌ Limited to 2-5 agents (SDK design constraint)
- ❌ Requires rewriting agent prompts
- ❌ Loses existing agent library

#### When to Use

- Starting fresh without existing agent definitions
- Need true multi-agent collaboration
- Want maximum SDK compatibility
- Prefer hard-coded, version-controlled agent configs

---

### Alternative 2: Agents as Reference Documentation

**Description**: Don't parse agents at all - let the agent READ them on-demand.

#### Implementation

```python
# No parsing - just use Read tool
options = ClaudeAgentOptions(
    system_prompt="""
    You have access to 44 specialized agent definitions in .claude/agents/.
    When you need specialized expertise, READ the appropriate agent file
    and adopt that persona and capabilities.

    Example: If asked about Python, read .claude/agents/dev-python-expert.md
    and follow its guidelines.
    """,
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "Skill"],
    setting_sources=["project"],
)
```

#### Pros

- ✅ Zero code changes required
- ✅ Uses existing agent definitions as-is
- ✅ Maximum flexibility
- ✅ No parsing/loading overhead

#### Cons

- ❌ Requires agent to remember to read files
- ❌ Uses input tokens for every agent switch
- ❌ No structured agent selection UI
- ❌ Relies on agent following instructions

#### When to Use

- Want immediate solution with zero code changes
- Have large token budget
- Trust agent to follow meta-instructions
- Prefer simplicity over structure

---

### Alternative 3: Compile All Agents into Mega-Prompt

**Description**: Concatenate all 44 agent definitions into one massive system prompt.

#### Implementation

```python
from pathlib import Path

def load_all_agents_as_prompt() -> str:
    """Load all agent definitions into one prompt."""
    agents_dir = Path(".claude/agents")
    sections = []

    for md_file in sorted(agents_dir.glob("*.md")):
        content = md_file.read_text()
        sections.append(f"## Agent: {md_file.stem}\n\n{content}")

    return "\n\n---\n\n".join(sections)


mega_prompt = f"""
You are a versatile AI agent with access to 44 specialized personas.
Choose the appropriate persona based on the task.

{load_all_agents_as_prompt()}

Select the most appropriate agent persona for each task and adopt their
tools, model preferences, and system prompt.
"""

options = ClaudeAgentOptions(
    system_prompt=mega_prompt,
    allowed_tools=["Read", "Write", "Bash", "Grep", "Glob", "Skill"],
)
```

#### Pros

- ✅ All agents available instantly
- ✅ No runtime parsing
- ✅ Simple implementation

#### Cons

- ❌ Massive system prompt (44 agents × ~500 tokens each = 22,000 tokens)
- ❌ Expensive cache creation on first use
- ❌ May confuse agent with too many options
- ❌ Wastes tokens on agents not being used

#### When to Use

- Have unlimited token budget
- Need all agents available instantly
- Don't care about context window efficiency
- Rarely switch between agents

**Recommendation**: **Avoid this approach** - wastes tokens and pollutes context window.

---

### Alternative 4: Dynamic Loading on Demand

**Description**: Load agent definitions only when explicitly requested.

#### Implementation

```python
class DynamicAgentLoader:
    """Load agents on-demand during conversation."""

    def __init__(self):
        self.loaded_agents = {}

    def load_agent(self, agent_name: str) -> str:
        """Load agent definition and return as prompt."""
        if agent_name in self.loaded_agents:
            return self.loaded_agents[agent_name]

        file_path = Path(f".claude/agents/{agent_name}.md")
        if not file_path.exists():
            return f"Agent '{agent_name}' not found"

        content = file_path.read_text()
        self.loaded_agents[agent_name] = content
        return content


# In conversation loop
loader = DynamicAgentLoader()

def handle_agent_switch(agent_name: str):
    """Switch to different agent on-the-fly."""
    agent_prompt = loader.load_agent(agent_name)

    # Append to conversation
    return f"""
    SWITCHING TO AGENT: {agent_name}

    {agent_prompt}

    Continue conversation as this agent.
    """
```

#### Pros

- ✅ Efficient token usage (only load what's needed)
- ✅ All 44 agents available
- ✅ Can switch agents mid-conversation

#### Cons

- ❌ Requires conversation state management
- ❌ Complex switching logic
- ❌ May confuse agent identity across switches
- ❌ Not using SDK's agent system

#### When to Use

- Need agent switching in long conversations
- Want token efficiency
- Have complex multi-step workflows
- Don't mind custom state management

---

### Alternative 5: Convert Agents to Skills

**Description**: Restructure `.claude/agents/` as `.claude/skills/` directories.

#### Implementation

**Before** (`.claude/agents/dev-python-expert.md`):
```yaml
---
name: python-expert
description: Expert Python developer
tools: Read, Write, Bash
---

# Python Development Expert
...
```

**After** (`.claude/skills/python-expert/SKILL.md`):
```yaml
---
title: Python Development Expert
description: Expert Python development guidance
tags: [skill, python, development]
type: skill
---

# Python Development Expert
...
```

**Restructure**:
```bash
# Convert agents to skills
for agent in .claude/agents/*.md; do
  name=$(basename "$agent" .md)
  mkdir -p ".claude/skills/$name"

  # Convert YAML frontmatter format
  # ... conversion logic ...

  mv "$agent" ".claude/skills/$name/SKILL.md"
done
```

#### Pros

- ✅ Uses SDK's native skill system
- ✅ Auto-discovery built-in
- ✅ All 44 agents become skills
- ✅ No custom loading code

#### Cons

- ❌ Loses agent-specific metadata (model, color)
- ❌ Skills are reference docs, not personas
- ❌ Mixing concepts (agent ≠ skill)
- ❌ One-time migration effort

#### When to Use

- Want to use SDK's skill system exclusively
- Don't need agent personas, just reference docs
- Willing to restructure repository
- Prefer skills over agents conceptually

---

## Comparison Matrix

| Approach | SDK Alignment | Complexity | Uses Existing Agents | Extensibility | Maintenance | Recommended |
|----------|---------------|------------|---------------------|---------------|-------------|-------------|
| **Custom Loader** | ⚠️ Medium | Medium | ✅ All 44 | ✅ High | ⚠️ Custom code | ⭐⭐⭐ |
| **Alt 1: Native SDK** | ✅ High | Low | ❌ None | ⚠️ Limited | ✅ Low | ⭐⭐⭐⭐ |
| **Alt 2: Reference Docs** | ⚠️ Medium | Very Low | ✅ All 44 | ✅ High | ✅ None | ⭐⭐ |
| **Alt 3: Mega-Prompt** | ❌ Low | Low | ✅ All 44 | ❌ Low | ⚠️ Token waste | ⭐ |
| **Alt 4: Dynamic Loading** | ❌ Low | High | ✅ All 44 | ✅ High | ❌ Complex state | ⭐⭐ |
| **Alt 5: Convert to Skills** | ✅ High | Medium | ⚠️ Repurposed | ⚠️ Locked-in | ✅ Low | ⭐⭐⭐ |
| **Hard-Coded (Chosen)** | ✅ Very High | Medium | ⚠️ 6 + 38 ref | ✅ High | ✅ Low | ⭐⭐⭐⭐⭐ |

**Legend**:
- ✅ Excellent
- ⚠️ Moderate
- ❌ Poor
- ⭐⭐⭐⭐⭐ Highly Recommended
- ⭐⭐⭐⭐ Recommended
- ⭐⭐⭐ Acceptable
- ⭐⭐ Use with caution
- ⭐ Not recommended

---

## Recommendations

### Recommended Path: Phases 1 + Hard-Coded Agents

**Phase 1** (30 minutes):
- Enable native skill support immediately
- All 12 skills become available
- Zero risk, maximum SDK alignment

**Phase 2: Hard-Coded Agents** (2 hours):
- Implement hard-coded agent definitions following reference pattern
- Extract prompts from 6 core agents to separate `.txt` files
- Lead agent orchestrates via Task tool
- Remaining 38 agents accessible via Read tool when needed

**Total Time**: ~2.5 hours
**Total Value**: Native skills + multi-agent system + SDK best practices

See **docs/IMPLEMENTATION.md** for the complete implementation plan.

### Decision Criteria

**Choose Custom Loader (this document) if**:
- You MUST use all 44 existing agent definitions
- You want runtime agent selection in interactive mode
- You're comfortable maintaining custom parsing code
- SDK alignment is less important than preserving existing work

**Choose Hard-Coded Agents (AGENT_ARCH.md Phase 2) if**:
- You want maximum SDK alignment
- You value maintainability and professionalism
- 6 core agents + 38 reference agents is acceptable
- You want to follow proven patterns (research-agent)

**Choose Alternative 2 (Reference Docs) if**:
- You need immediate solution (zero code changes)
- Token budget is not a concern
- You trust the agent to read files on-demand
- Simplicity > structure

**Avoid Alternative 3 (Mega-Prompt)**:
- Wastes tokens
- Context window pollution
- Not scalable

**Avoid Alternative 4 (Dynamic Loading)**:
- Complex state management
- Not using SDK's agent system
- High maintenance burden

### Hybrid Approach (Best of Both Worlds)

Combine **Skills** + **Hard-Coded Agents** + **Reference Docs**:

```python
# Lead agent prompt with hybrid capabilities
"""
You are the Lead Software Architect with three capabilities:

1. **Core Agents** - Delegate via Task tool to 6 specialists:
   - python-expert, typescript-expert, docker-expert,
     postgres-expert, code-reviewer, doc-writer

2. **Skills** - Access 12 pre-built workflows via Skill tool:
   - /skill api-development, /skill code-review, etc.

3. **Extended Agent Library** - READ from .claude/agents/ for specialized needs:
   - 38 additional agents for languages (Julia, Rust, Go, etc.)
   - Use when core agents don't fit the task
"""
```

**Benefits**:
- ✅ 6 hard-coded agents for common tasks (fast delegation)
- ✅ 12 skills for workflow patterns (SDK native)
- ✅ 38 reference agents for edge cases (on-demand)
- ✅ Maximum flexibility with minimal code
