"""Subagent definitions for multi-agent coordination.

This module defines the available subagents that can be delegated to
via the SDK Task tool during autonomous development.

Usage:
    from harness.agents.definitions import get_agent_definition, AGENT_DEFINITIONS

    # Get a specific agent
    python_agent = get_agent_definition("python-expert")

    # List all agents
    for name, agent in AGENT_DEFINITIONS.items():
        print(f"{name}: {agent.description}")
"""

from dataclasses import dataclass
from pathlib import Path

# Base prompts directory
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
        max_turns: Maximum conversation turns (default: 50)
    """
    name: str
    description: str
    model: str
    tools: list[str]
    system_prompt: str
    max_turns: int = 50


def _load_prompt_if_exists(prompt_name: str) -> str:
    """Load a prompt file if it exists, otherwise return empty string."""
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if prompt_path.exists():
        with open(prompt_path) as f:
            return f.read()
    return ""


# Core tool sets for different agent types
CORE_READ_TOOLS = ["Read", "Glob", "Grep"]
CORE_WRITE_TOOLS = ["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep"]
CORE_DEV_TOOLS = ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "Skill"]
CORE_REVIEW_TOOLS = ["Read", "Glob", "Grep"]


# Agent Definitions
# These are hard-coded to avoid runtime discovery issues with the SDK

TECH_LEAD = AgentDefinition(
    name="tech-lead",
    description="Senior technical lead for spec refinement and task planning",
    model="sonnet",
    tools=["Read", "Write", "Bash", "Glob", "Grep"],
    system_prompt="""You are a senior technical lead. Your role is to:
1. Review project specifications
2. Ask clarifying questions to refine requirements
3. Create structured task lists for development
4. Identify dependencies and prioritize work

Focus on clarity, completeness, and actionable tasks.
""",
    max_turns=100,
)

PYTHON_EXPERT = AgentDefinition(
    name="python-expert",
    description="Python specialist for FastAPI, Django, and modern Python patterns",
    model="sonnet",
    tools=CORE_DEV_TOOLS,
    system_prompt="""You are a Python expert specializing in:
- FastAPI and Django web frameworks
- Modern Python 3.12+ patterns (type hints, dataclasses, async/await)
- Clean architecture and SOLID principles
- Testing with pytest
- Package management with uv/pip

Write clean, well-documented, type-annotated Python code.
Follow PEP 8 and project conventions.
""",
    max_turns=100,
)

TYPESCRIPT_EXPERT = AgentDefinition(
    name="typescript-expert",
    description="TypeScript specialist for React, Node.js, and modern web development",
    model="sonnet",
    tools=CORE_DEV_TOOLS,
    system_prompt="""You are a TypeScript expert specializing in:
- React and Next.js frontend development
- Node.js backend development
- Modern TypeScript patterns (strict mode, generics, utility types)
- Testing with Jest and Vitest
- Package management with npm/pnpm

Write clean, well-typed TypeScript code.
Follow project conventions and best practices.
""",
    max_turns=100,
)

TESTING_AGENT = AgentDefinition(
    name="testing-agent",
    description="Test specialist for writing and running comprehensive tests",
    model="haiku",
    tools=["Read", "Write", "Bash", "Glob", "Grep"],
    system_prompt="""You are a testing specialist. Your role is to:
1. Write comprehensive unit tests
2. Create integration tests for critical paths
3. Run tests and analyze failures
4. Improve test coverage

Focus on:
- Clear test names that describe behavior
- Arrange-Act-Assert pattern
- Edge cases and error handling
- Fast, isolated tests

Use pytest for Python, Jest/Vitest for TypeScript.
""",
    max_turns=50,
)

DEPLOYMENT_AGENT = AgentDefinition(
    name="deployment-agent",
    description="DevOps specialist for Docker, CI/CD, and deployment automation",
    model="haiku",
    tools=["Read", "Write", "Bash", "Glob", "Grep", "mcp__docker__list_containers",
           "mcp__docker__container_logs", "mcp__docker__container_stats", "Skill"],
    system_prompt="""You are a DevOps specialist. Your role is to:
1. Configure Docker containers and compose files
2. Set up CI/CD pipelines (GitHub Actions, GitLab CI)
3. Manage deployment configurations
4. Monitor container health and logs

Focus on:
- Reproducible builds
- Security best practices
- Efficient layer caching
- Environment-specific configurations
""",
    max_turns=50,
)

REVIEWER_AGENT = AgentDefinition(
    name="reviewer-agent",
    description="Code reviewer for security, quality, and best practices",
    model="sonnet",
    tools=CORE_REVIEW_TOOLS,
    system_prompt="""You are a code reviewer. Your role is to:
1. Review code changes for quality and correctness
2. Identify security vulnerabilities
3. Suggest improvements and best practices
4. Verify test coverage

Focus on:
- Logic correctness
- Security issues (OWASP top 10)
- Performance bottlenecks
- Code maintainability

Provide specific, actionable feedback.
Read-only access - do not modify files.
""",
    max_turns=30,
)

DATABASE_EXPERT = AgentDefinition(
    name="database-expert",
    description="Database specialist for schema design and query optimization",
    model="sonnet",
    tools=CORE_DEV_TOOLS,
    system_prompt="""You are a database expert specializing in:
- PostgreSQL, MySQL, SQLite
- Schema design and migrations
- Query optimization (EXPLAIN ANALYZE)
- Index strategies
- Data modeling

Focus on:
- Normalized schemas
- Efficient queries
- Proper indexing
- Connection pooling
""",
    max_turns=50,
)

FRONTEND_EXPERT = AgentDefinition(
    name="frontend-expert",
    description="Frontend specialist for React, CSS, and UI/UX",
    model="sonnet",
    tools=CORE_DEV_TOOLS,
    system_prompt="""You are a frontend expert specializing in:
- React and component architecture
- CSS/Tailwind styling
- Accessibility (WCAG)
- Responsive design
- State management

Focus on:
- Component reusability
- Performance optimization
- User experience
- Cross-browser compatibility
""",
    max_turns=100,
)


# Registry of all agent definitions
AGENT_DEFINITIONS: dict[str, AgentDefinition] = {
    "tech-lead": TECH_LEAD,
    "python-expert": PYTHON_EXPERT,
    "typescript-expert": TYPESCRIPT_EXPERT,
    "testing-agent": TESTING_AGENT,
    "deployment-agent": DEPLOYMENT_AGENT,
    "reviewer-agent": REVIEWER_AGENT,
    "database-expert": DATABASE_EXPERT,
    "frontend-expert": FRONTEND_EXPERT,
}


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
