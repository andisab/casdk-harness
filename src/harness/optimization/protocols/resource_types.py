"""Resource type registry for multi-resource optimization pipeline.

Maps each resource type to its creation agent, skill, path pattern,
and evaluation strategy.  The registry is the single source of truth
for how resources are discovered, generated, and evaluated.

Usage:
    from harness.optimization.protocols import (
        ResourceType,
        ResourceTypeConfig,
        ResourceTypeRegistry,
    )

    registry = ResourceTypeRegistry.default()
    config = registry.get(ResourceType.AGENT)
    path = config.resolve_path("iac-analyzer")  # "agents/iac-analyzer.md"
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):
    """Supported resource types in the optimization pipeline.

    Values are lowercase strings used for serialization and lookup.
    """

    AGENT = "agent"
    SKILL = "skill"
    COMMAND = "command"
    HOOK = "hook"
    MCP_TOOL = "mcp_tool"
    MCP_SERVER = "mcp_server"
    PLUGIN = "plugin"


@dataclass(frozen=True)
class ResourceTypeConfig:
    """Configuration for a single resource type.

    Attributes:
        type: The resource type this config describes.
        path_pattern: Path template with ``{name}`` placeholder.
        generator_agent: Fully-qualified agent name (``plugin:agent``).
        generator_skill: Skill name used by the generator agent.
        eval_strategy: One of ``content_only``, ``content_and_execution``,
            ``executable``, or ``server``.
        supports_versioning: Whether optimized versions are kept as
            ``{name}-v1.md``, ``{name}-v2.md``, etc.
    """

    type: ResourceType
    path_pattern: str
    generator_agent: str
    generator_skill: str
    eval_strategy: str
    supports_versioning: bool

    def resolve_path(self, name: str) -> str:
        """Substitute ``{name}`` in the path pattern.

        Args:
            name: Resource name to insert into the pattern.

        Returns:
            Resolved path string.
        """
        return self.path_pattern.replace("{name}", name)


class ResourceTypeRegistry:
    """Registry mapping resource types to their configurations.

    Use :meth:`default` to obtain a registry pre-populated with the
    standard 7 resource types.
    """

    def __init__(self) -> None:
        self._configs: dict[ResourceType, ResourceTypeConfig] = {}

    # -- mutators ----------------------------------------------------------

    def register(self, config: ResourceTypeConfig) -> None:
        """Register (or override) a resource type configuration.

        Args:
            config: The configuration to register.  Its ``type`` field
                determines the key.
        """
        self._configs[config.type] = config

    # -- queries -----------------------------------------------------------

    def get(self, resource_type: ResourceType) -> ResourceTypeConfig | None:
        """Look up a config by enum member.

        Returns:
            The config, or ``None`` if not registered.
        """
        return self._configs.get(resource_type)

    def get_by_string(self, type_string: str) -> ResourceTypeConfig | None:
        """Look up a config by its string value (case-insensitive).

        Args:
            type_string: E.g. ``"agent"``, ``"MCP_TOOL"``.

        Returns:
            The config, or ``None`` if no matching type exists.
        """
        normalized = type_string.lower()
        try:
            resource_type = ResourceType(normalized)
        except ValueError:
            return None
        return self._configs.get(resource_type)

    def resolve_path(self, resource_type: ResourceType, name: str) -> str:
        """Resolve a resource path by type and name.

        Args:
            resource_type: The resource type enum member.
            name: Resource name to substitute into the path pattern.

        Returns:
            Resolved path string.

        Raises:
            KeyError: If the resource type is not registered.
        """
        config = self._configs.get(resource_type)
        if config is None:
            raise KeyError(f"No config registered for {resource_type!r}")
        return config.resolve_path(name)

    # -- factory -----------------------------------------------------------

    @classmethod
    def default(cls) -> ResourceTypeRegistry:
        """Create a registry with all 7 default resource type configs.

        All types use ``context-engineering:context-engineer`` as the
        generator agent.
        """
        registry = cls()
        agent = "context-engineering:context-engineer"

        defaults: list[ResourceTypeConfig] = [
            ResourceTypeConfig(
                type=ResourceType.AGENT,
                path_pattern="agents/{name}.md",
                generator_agent=agent,
                generator_skill="agent-dev",
                eval_strategy="content_and_execution",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.SKILL,
                path_pattern="skills/{name}/SKILL.md",
                generator_agent=agent,
                generator_skill="skill-dev",
                eval_strategy="content_only",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.COMMAND,
                path_pattern="commands/{name}.md",
                generator_agent=agent,
                generator_skill="command-dev",
                eval_strategy="content_only",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.HOOK,
                path_pattern="hooks/{name}.json",
                generator_agent=agent,
                generator_skill="hook-dev",
                eval_strategy="content_only",
                supports_versioning=False,
            ),
            ResourceTypeConfig(
                type=ResourceType.MCP_TOOL,
                path_pattern="tools/{name}.py",
                generator_agent=agent,
                generator_skill="mcp-tool-dev",
                eval_strategy="executable",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.MCP_SERVER,
                path_pattern="mcp-servers/{name}/",
                generator_agent=agent,
                generator_skill="mcp-server-dev",
                eval_strategy="server",
                supports_versioning=True,
            ),
            ResourceTypeConfig(
                type=ResourceType.PLUGIN,
                path_pattern="{name}/",
                generator_agent=agent,
                generator_skill="plugin-dev",
                eval_strategy="content_only",
                supports_versioning=False,
            ),
        ]

        for config in defaults:
            registry.register(config)

        return registry
