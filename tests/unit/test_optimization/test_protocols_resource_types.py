"""Tests for the resource type registry protocol layer.

Covers:
    - ResourceType enum members and values
    - ResourceTypeConfig creation and path resolution
    - ResourceTypeRegistry default factory, lookup, and custom registration
"""

from __future__ import annotations

import pytest

from harness.optimization.protocols.resource_types import (
    ResourceType,
    ResourceTypeConfig,
    ResourceTypeRegistry,
)


class TestResourceType:
    """Verify all 7 resource types exist with lowercase string values."""

    @pytest.mark.parametrize(
        ("member_name", "expected_value"),
        [
            ("AGENT", "agent"),
            ("SKILL", "skill"),
            ("COMMAND", "command"),
            ("HOOK", "hook"),
            ("MCP_TOOL", "mcp_tool"),
            ("MCP_SERVER", "mcp_server"),
            ("PLUGIN", "plugin"),
        ],
    )
    def test_enum_member_exists_with_lowercase_value(
        self, member_name: str, expected_value: str
    ) -> None:
        member = ResourceType[member_name]
        assert member.value == expected_value

    def test_enum_has_exactly_seven_members(self) -> None:
        assert len(ResourceType) == 7

    def test_enum_values_are_all_strings(self) -> None:
        for member in ResourceType:
            assert isinstance(member.value, str)


class TestResourceTypeConfig:
    """Test config creation and path resolution."""

    def test_create_agent_config(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.AGENT,
            path_pattern="agents/{name}.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="agent-dev",
            eval_strategy="content_and_execution",
            supports_versioning=True,
        )
        assert config.type == ResourceType.AGENT
        assert config.path_pattern == "agents/{name}.md"
        assert config.generator_agent == "context-engineering:context-engineer"
        assert config.generator_skill == "agent-dev"
        assert config.eval_strategy == "content_and_execution"
        assert config.supports_versioning is True

    def test_create_mcp_tool_config(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.MCP_TOOL,
            path_pattern="tools/{name}.py",
            generator_agent="context-engineering:context-engineer",
            generator_skill="mcp-tool-dev",
            eval_strategy="executable",
            supports_versioning=True,
        )
        assert config.type == ResourceType.MCP_TOOL
        assert config.eval_strategy == "executable"

    def test_resolve_path_agent(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.AGENT,
            path_pattern="agents/{name}.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="agent-dev",
            eval_strategy="content_and_execution",
            supports_versioning=True,
        )
        resolved = config.resolve_path("iac-analyzer")
        assert resolved == "agents/iac-analyzer.md"

    def test_resolve_path_skill(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.SKILL,
            path_pattern="skills/{name}/SKILL.md",
            generator_agent="context-engineering:context-engineer",
            generator_skill="skill-dev",
            eval_strategy="content_only",
            supports_versioning=True,
        )
        resolved = config.resolve_path("code-review")
        assert resolved == "skills/code-review/SKILL.md"

    def test_config_is_frozen(self) -> None:
        config = ResourceTypeConfig(
            type=ResourceType.HOOK,
            path_pattern="hooks/{name}.json",
            generator_agent="context-engineering:context-engineer",
            generator_skill="hook-dev",
            eval_strategy="content_only",
            supports_versioning=False,
        )
        with pytest.raises(AttributeError):
            config.type = ResourceType.AGENT  # type: ignore[misc]


class TestResourceTypeRegistry:
    """Test registry default factory, lookup, and custom registration."""

    def test_default_has_configs_for_all_types(self) -> None:
        registry = ResourceTypeRegistry.default()
        for resource_type in ResourceType:
            config = registry.get(resource_type)
            assert config is not None, f"Missing config for {resource_type}"
            assert config.type == resource_type

    def test_get_by_string(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get_by_string("agent")
        assert config is not None
        assert config.type == ResourceType.AGENT

    def test_get_by_string_case_insensitive(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get_by_string("MCP_TOOL")
        assert config is not None
        assert config.type == ResourceType.MCP_TOOL

    def test_get_by_string_unknown_returns_none(self) -> None:
        registry = ResourceTypeRegistry.default()
        result = registry.get_by_string("unknown_type")
        assert result is None

    def test_register_custom_type(self) -> None:
        registry = ResourceTypeRegistry.default()
        custom_config = ResourceTypeConfig(
            type=ResourceType.AGENT,
            path_pattern="custom-agents/{name}.md",
            generator_agent="custom:agent",
            generator_skill="custom-skill",
            eval_strategy="content_only",
            supports_versioning=False,
        )
        registry.register(custom_config)
        config = registry.get(ResourceType.AGENT)
        assert config is not None
        assert config.path_pattern == "custom-agents/{name}.md"
        assert config.generator_agent == "custom:agent"

    def test_resolve_path_via_registry(self) -> None:
        registry = ResourceTypeRegistry.default()
        resolved = registry.resolve_path(ResourceType.AGENT, "iac-analyzer")
        assert resolved == "agents/iac-analyzer.md"

    def test_resolve_path_via_registry_unknown_type_raises(self) -> None:
        registry = ResourceTypeRegistry()
        with pytest.raises(KeyError):
            registry.resolve_path(ResourceType.AGENT, "test")

    def test_default_agent_config_values(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get(ResourceType.AGENT)
        assert config is not None
        assert config.generator_agent == "context-engineering:context-engineer"
        assert config.generator_skill == "agent-dev"
        assert config.path_pattern == "agents/{name}.md"
        assert config.eval_strategy == "content_and_execution"
        assert config.supports_versioning is True

    def test_default_skill_config_values(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get(ResourceType.SKILL)
        assert config is not None
        assert config.generator_skill == "skill-dev"
        assert config.path_pattern == "skills/{name}/SKILL.md"
        assert config.eval_strategy == "content_only"
        assert config.supports_versioning is True

    def test_default_hook_config_no_versioning(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get(ResourceType.HOOK)
        assert config is not None
        assert config.supports_versioning is False

    def test_default_plugin_config_no_versioning(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get(ResourceType.PLUGIN)
        assert config is not None
        assert config.supports_versioning is False

    def test_default_mcp_server_config(self) -> None:
        registry = ResourceTypeRegistry.default()
        config = registry.get(ResourceType.MCP_SERVER)
        assert config is not None
        assert config.eval_strategy == "server"
        assert config.path_pattern == "mcp-servers/{name}/"
        assert config.supports_versioning is True
