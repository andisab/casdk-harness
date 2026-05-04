"""CGF Resource Registry.

Provides unified access to optimizable resources (agents, skills, prompts, commands)
with automatic discovery and loading.

Usage:
    from harness.optimization.resources import (
        ResourceRegistry,
        AgentResource,
        SkillResource,
        PromptResource,
        CommandResource,
    )

    # Create registry with auto-discovery
    registry = ResourceRegistry.discover()

    # Get a specific resource
    agent = registry.get("python-expert", "agent")
    skill = registry.get("debugging", "skill")

    # List all resources of a type
    agents = registry.list_by_type("agent")

    # Load individual resource
    agent = AgentResource.load(Path(".claude/agents/python-expert.md"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

from harness.optimization.resources.agent_resource import AgentResource
from harness.optimization.resources.base import (
    BaseResource,
    ResourceProtocol,
    ValidationError,
    compute_content_hash,
    compute_diff,
    parse_frontmatter,
    serialize_frontmatter,
)
from harness.optimization.resources.command_resource import CommandResource
from harness.optimization.resources.prompt_resource import PromptResource
from harness.optimization.resources.skill_resource import SkillResource

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

__all__ = [
    # Base types
    "ResourceProtocol",
    "BaseResource",
    "ValidationError",
    # Resource types
    "AgentResource",
    "SkillResource",
    "PromptResource",
    "CommandResource",
    # Registry
    "ResourceRegistry",
    # Utilities
    "parse_frontmatter",
    "serialize_frontmatter",
    "compute_content_hash",
    "compute_diff",
]

# Type variable for resource types
T = TypeVar("T", bound=BaseResource)

# Resource type mapping
RESOURCE_TYPES: dict[str, type[BaseResource]] = {
    "agent": AgentResource,
    "skill": SkillResource,
    "prompt": PromptResource,
    "command": CommandResource,
}


@dataclass
class ResourceRegistry:
    """Registry for optimizable resources.

    Provides centralized access to all discovered resources with
    type-safe loading and lookup.
    """

    _resources: dict[str, dict[str, BaseResource]] = field(default_factory=dict)
    _source_paths: dict[str, Path] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize resource type dictionaries."""
        for resource_type in RESOURCE_TYPES:
            if resource_type not in self._resources:
                self._resources[resource_type] = {}

    def register(self, resource: BaseResource) -> None:
        """Register a resource.

        Args:
            resource: Resource to register.
        """
        resource_type = resource.resource_type
        resource_id = resource.resource_id

        if resource_type not in self._resources:
            self._resources[resource_type] = {}

        self._resources[resource_type][resource_id] = resource

        if resource.source_path:
            key = f"{resource_type}:{resource_id}"
            self._source_paths[key] = resource.source_path

        logger.debug(
            "Registered resource",
            resource_id=resource_id,
            resource_type=resource_type,
        )

    def get(
        self,
        resource_id: str,
        resource_type: str,
    ) -> BaseResource | None:
        """Get a resource by ID and type.

        Args:
            resource_id: Resource identifier.
            resource_type: Type of resource.

        Returns:
            Resource or None if not found.
        """
        return self._resources.get(resource_type, {}).get(resource_id)

    def get_agent(self, resource_id: str) -> AgentResource | None:
        """Get an agent resource by ID.

        Args:
            resource_id: Agent identifier.

        Returns:
            AgentResource or None if not found.
        """
        resource = self.get(resource_id, "agent")
        return resource if isinstance(resource, AgentResource) else None

    def get_skill(self, resource_id: str) -> SkillResource | None:
        """Get a skill resource by ID.

        Args:
            resource_id: Skill identifier.

        Returns:
            SkillResource or None if not found.
        """
        resource = self.get(resource_id, "skill")
        return resource if isinstance(resource, SkillResource) else None

    def get_prompt(self, resource_id: str) -> PromptResource | None:
        """Get a prompt resource by ID.

        Args:
            resource_id: Prompt identifier.

        Returns:
            PromptResource or None if not found.
        """
        resource = self.get(resource_id, "prompt")
        return resource if isinstance(resource, PromptResource) else None

    def get_command(self, resource_id: str) -> CommandResource | None:
        """Get a command resource by ID.

        Args:
            resource_id: Command identifier.

        Returns:
            CommandResource or None if not found.
        """
        resource = self.get(resource_id, "command")
        return resource if isinstance(resource, CommandResource) else None

    def list_by_type(self, resource_type: str) -> list[BaseResource]:
        """List all resources of a specific type.

        Args:
            resource_type: Type of resources to list.

        Returns:
            List of resources.
        """
        return list(self._resources.get(resource_type, {}).values())

    def list_agents(self) -> list[AgentResource]:
        """List all agent resources.

        Returns:
            List of AgentResource.
        """
        return [r for r in self.list_by_type("agent") if isinstance(r, AgentResource)]

    def list_skills(self) -> list[SkillResource]:
        """List all skill resources.

        Returns:
            List of SkillResource.
        """
        return [r for r in self.list_by_type("skill") if isinstance(r, SkillResource)]

    def list_prompts(self) -> list[PromptResource]:
        """List all prompt resources.

        Returns:
            List of PromptResource.
        """
        return [r for r in self.list_by_type("prompt") if isinstance(r, PromptResource)]

    def list_commands(self) -> list[CommandResource]:
        """List all command resources.

        Returns:
            List of CommandResource.
        """
        return [r for r in self.list_by_type("command") if isinstance(r, CommandResource)]

    def list_all(self) -> list[BaseResource]:
        """List all registered resources.

        Returns:
            List of all resources.
        """
        all_resources: list[BaseResource] = []
        for resources in self._resources.values():
            all_resources.extend(resources.values())
        return all_resources

    def count(self) -> dict[str, int]:
        """Count resources by type.

        Returns:
            Dictionary mapping resource type to count.
        """
        return {
            resource_type: len(resources)
            for resource_type, resources in self._resources.items()
        }

    def validate_all(self) -> dict[str, list[ValidationError]]:
        """Validate all registered resources.

        Returns:
            Dictionary mapping resource IDs to their validation errors.
        """
        results: dict[str, list[ValidationError]] = {}

        for resource in self.list_all():
            errors = resource.validate()
            if errors:
                key = f"{resource.resource_type}:{resource.resource_id}"
                results[key] = errors

        return results

    @classmethod
    def discover(
        cls,
        base_path: Path | None = None,
        include_plugins: bool = True,
    ) -> ResourceRegistry:
        """Discover and load all resources from standard locations.

        Args:
            base_path: Base path for discovery (defaults to harness package).
            include_plugins: Whether to include plugin resources.

        Returns:
            ResourceRegistry with discovered resources.
        """
        registry = cls()

        if base_path is None:
            # Default to repo root (where .claude/agents/ lives)
            # parents[4] from src/harness/optimization/resources/__init__.py → repo root
            base_path = Path(__file__).resolve().parents[4]

        # Discover agents (REFACTOR.md Part 2 Phase 1: moved from .claude/agents/ to .claude/agents/)
        agents_dir = base_path / ".claude" / "agents"
        if agents_dir.exists():
            for md_file in agents_dir.glob("*.md"):
                try:
                    agent = AgentResource.load(md_file)
                    registry.register(agent)
                except Exception as e:
                    logger.warning(
                        "Failed to load agent",
                        path=str(md_file),
                        error=str(e),
                    )

        # Discover skills
        skills_dir = base_path / "skills"
        if skills_dir.exists():
            for skill_file in skills_dir.glob("*/SKILL.md"):
                try:
                    skill = SkillResource.load(skill_file)
                    registry.register(skill)
                except Exception as e:
                    logger.warning(
                        "Failed to load skill",
                        path=str(skill_file),
                        error=str(e),
                    )

        # Discover prompts
        prompts_dir = base_path / "prompts"
        if prompts_dir.exists():
            for prompt_file in prompts_dir.glob("*.md"):
                try:
                    prompt = PromptResource.load(prompt_file)
                    registry.register(prompt)
                except Exception as e:
                    logger.warning(
                        "Failed to load prompt",
                        path=str(prompt_file),
                        error=str(e),
                    )

        # Discover plugin resources
        if include_plugins:
            plugins_dir = base_path / "plugins"
            if plugins_dir.exists():
                for plugin_dir in plugins_dir.iterdir():
                    if plugin_dir.is_dir():
                        registry._discover_plugin(plugin_dir)

        logger.info(
            "Resource discovery complete",
            counts=registry.count(),
        )

        return registry

    def _discover_plugin(self, plugin_dir: Path) -> None:
        """Discover resources from a plugin directory.

        Args:
            plugin_dir: Path to the plugin directory.
        """
        plugin_name = plugin_dir.name

        # Plugin agents
        agents_dir = plugin_dir / "agents"
        if agents_dir.exists():
            for md_file in agents_dir.glob("*.md"):
                try:
                    agent = AgentResource.load(md_file)
                    # Prefix with plugin name for namespacing
                    agent._resource_id = f"{plugin_name}:{agent.resource_id}"
                    self.register(agent)
                except Exception as e:
                    logger.warning(
                        "Failed to load plugin agent",
                        plugin=plugin_name,
                        path=str(md_file),
                        error=str(e),
                    )

        # Plugin skills
        skills_dir = plugin_dir / "skills"
        if skills_dir.exists():
            for skill_file in skills_dir.glob("*/SKILL.md"):
                try:
                    skill = SkillResource.load(skill_file)
                    skill._resource_id = f"{plugin_name}:{skill.resource_id}"
                    self.register(skill)
                except Exception as e:
                    logger.warning(
                        "Failed to load plugin skill",
                        plugin=plugin_name,
                        path=str(skill_file),
                        error=str(e),
                    )

        # Plugin commands
        commands_dir = plugin_dir / "commands"
        if commands_dir.exists():
            for cmd_file in commands_dir.glob("*.md"):
                try:
                    command = CommandResource.load(cmd_file)
                    command._resource_id = f"{plugin_name}:{command.resource_id}"
                    self.register(command)
                except Exception as e:
                    logger.warning(
                        "Failed to load plugin command",
                        plugin=plugin_name,
                        path=str(cmd_file),
                        error=str(e),
                    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the registry to a dictionary.

        Returns:
            Dictionary representation of all resources.
        """
        return {
            "counts": self.count(),
            "resources": {
                resource_type: {
                    resource_id: resource.to_dict()
                    for resource_id, resource in resources.items()
                }
                for resource_type, resources in self._resources.items()
            },
        }
