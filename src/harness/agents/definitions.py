"""Subagent definitions for multi-agent coordination.

This module defines the available subagents that can be delegated to
via the SDK Task tool during autonomous development.

Agent definitions are loaded dynamically from .md files in `.claude/agents/`
at the repo root (canonical Anthropic location). Each .md file uses YAML
frontmatter for metadata and markdown body for system prompt. SDK filesystem
auto-discovery (via `setting_sources=["project"]`) reads the same files; this
loader continues to populate `agents=` programmatically so the existing
logical-name → filename alias mapping in `_load_all_agents()` keeps working.

Usage:
    from harness.agents.definitions import get_agent_definition, AGENT_DEFINITIONS

    # Get a specific agent
    python_agent = get_agent_definition("python-expert")

    # List all agents
    for name, agent in AGENT_DEFINITIONS.items():
        print(f"{name}: {agent.description}")
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Repo-root .claude/agents/ — canonical Anthropic location (REFACTOR.md Part 2 Phase 1)
# parents[3] from src/harness/agents/definitions.py → repo root
CONFIGS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "agents"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class AgentDefinition:
    """Definition of a subagent for Task tool delegation.

    Attributes:
        name: Unique identifier for the agent
        description: Short description of agent purpose
        model: Model to use (sonnet, opus, haiku)
        tools: List of allowed tools
        system_prompt: System prompt for the agent
        max_turns: Maximum conversation turns (default: 100)
    """
    name: str
    description: str
    model: str
    tools: list[str]
    system_prompt: str
    max_turns: int = 100


def _load_prompt_if_exists(prompt_name: str) -> str:
    """Load a prompt file if it exists, otherwise return empty string."""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if prompt_path.exists():
        with open(prompt_path) as f:
            return f.read()
    return ""


def parse_agent_md_file(filepath: Path) -> dict[str, Any]:
    """Parse YAML frontmatter and markdown body from agent .md file.

    Args:
        filepath: Path to the .md file

    Returns:
        Dictionary with parsed metadata and body

    Raises:
        ValueError: If no frontmatter found
    """
    content = filepath.read_text()
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter found in {filepath}")

    metadata = yaml.safe_load(match.group(1))
    tools_str = metadata.get("tools", "")
    tools = [t.strip() for t in tools_str.split(",") if t.strip()]

    # Extract just the first paragraph of description for the short description
    description = metadata.get("description", "").strip()
    # Take first sentence or line for short description
    short_desc = description.split("\n")[0].strip()
    if len(short_desc) > 200:
        short_desc = short_desc[:197] + "..."

    return {
        "name": metadata.get("name"),
        "description": short_desc,
        "tools": tools,
        "model": metadata.get("model", "sonnet"),
        "max_turns": metadata.get("max_turns", 100),
        "body": match.group(2).strip(),
    }


def load_agent_from_md(filename: str) -> AgentDefinition:
    """Load agent definition from .md file.

    Args:
        filename: Filename without .md extension

    Returns:
        AgentDefinition loaded from file

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    md_file = CONFIGS_DIR / f"{filename}.md"
    if not md_file.exists():
        raise FileNotFoundError(f"Agent file not found: {md_file}")

    parsed = parse_agent_md_file(md_file)

    return AgentDefinition(
        name=parsed["name"],
        description=parsed["description"],
        model=parsed["model"],
        tools=parsed["tools"],
        system_prompt=parsed["body"],
        max_turns=parsed["max_turns"],
    )


# Tech Lead loads from prompts directory (used directly by autonomous.py)
def _load_tech_lead() -> AgentDefinition:
    """Load tech-lead agent from prompt file."""
    prompt = _load_prompt_if_exists("tech-lead-agent")
    if not prompt:
        logger.warning("tech-lead-agent.md not found, using fallback prompt")
        prompt = "You are a senior technical lead for spec refinement and task planning."
    return AgentDefinition(
        name="tech-lead",
        description="Senior technical lead for spec refinement and task planning",
        model="sonnet",
        tools=["Read", "Write", "Bash", "Glob", "Grep"],
        system_prompt=prompt,
        max_turns=100,
    )


TECH_LEAD = _load_tech_lead()


def _load_all_agents() -> dict[str, AgentDefinition]:
    """Auto-discover all agent definitions from `.claude/agents/`.

    REFACTOR.md Phase 3 Step 2 (verified 2026-05-04): the previous
    logical-name → filename alias dict has been removed. Each agent's
    YAML `name:` field IS the canonical name now (Phase 3 Step 1 renamed
    files and YAML to ensure name == canonical short form, e.g.
    `database-expert`, `gcp-architect`, `code-review-expert`, `sdet-expert`).

    Returns:
        Dict mapping each agent's YAML `name:` to its AgentDefinition.
    """
    agents: dict[str, AgentDefinition] = {}

    # Tech-lead is loaded inline from src/harness/prompts/tech-lead-agent.md
    # (used directly by autonomous.py; not a `.claude/agents/` file).
    agents["tech-lead"] = TECH_LEAD

    if not CONFIGS_DIR.exists():
        logger.warning(f"Agent configs dir not found: {CONFIGS_DIR}")
        return agents

    for md_file in sorted(CONFIGS_DIR.glob("*.md")):
        try:
            parsed = parse_agent_md_file(md_file)
            name = parsed["name"]
            if not name:
                logger.warning(f"Skipping {md_file.name}: missing 'name' in YAML frontmatter")
                continue
            agents[name] = AgentDefinition(
                name=name,
                description=parsed["description"],
                model=parsed["model"],
                tools=parsed["tools"],
                system_prompt=parsed["body"],
                max_turns=parsed["max_turns"],
            )
            logger.debug(f"Loaded agent: {name} from {md_file.name}")
        except Exception as e:
            logger.warning(f"Failed to load agent from {md_file.name}: {e}")

    return agents


# Load all agents at module import
AGENT_DEFINITIONS: dict[str, AgentDefinition] = _load_all_agents()


def get_agent_definition(name: str) -> AgentDefinition | None:
    """Get an agent definition by name.

    Args:
        name: Agent name (e.g., 'python-expert')

    Returns:
        AgentDefinition or None if not found
    """
    return AGENT_DEFINITIONS.get(name)


def list_agents() -> list[str]:
    """List all available agent names.

    Returns:
        List of agent names
    """
    return list(AGENT_DEFINITIONS.keys())


def get_agents_by_model(model: str) -> list[AgentDefinition]:
    """Get all agents that use a specific model.

    Args:
        model: Model name (sonnet, opus, haiku)

    Returns:
        List of matching agent definitions
    """
    return [
        agent for agent in AGENT_DEFINITIONS.values()
        if agent.model == model
    ]


def reload_agents() -> None:
    """Reload all agent definitions from disk.

    Useful for development when agent configs are modified.
    """
    global AGENT_DEFINITIONS
    AGENT_DEFINITIONS = _load_all_agents()
    logger.info(f"Reloaded {len(AGENT_DEFINITIONS)} agent definitions")
