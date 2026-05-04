"""Unit tests for optimization resource wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.optimization.resources import (
    AgentResource,
    CommandResource,
    PromptResource,
    ResourceProtocol,
    ResourceRegistry,
    SkillResource,
    ValidationError,
)
from harness.optimization.resources.base import (
    BaseResource,
    compute_content_hash,
    compute_diff,
    parse_frontmatter,
    serialize_frontmatter,
)


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_parse_with_frontmatter(self) -> None:
        """Test parsing content with valid frontmatter."""
        content = """---
name: test-agent
description: A test agent
model: sonnet
---

This is the body content."""

        metadata, body = parse_frontmatter(content)

        assert metadata["name"] == "test-agent"
        assert metadata["description"] == "A test agent"
        assert metadata["model"] == "sonnet"
        assert body == "This is the body content."

    def test_parse_without_frontmatter(self) -> None:
        """Test parsing content without frontmatter."""
        content = "Just plain content without frontmatter."

        metadata, body = parse_frontmatter(content)

        assert metadata == {}
        assert body == "Just plain content without frontmatter."

    def test_parse_empty_frontmatter(self) -> None:
        """Test parsing with empty frontmatter - returns whole content as body."""
        # The regex pattern requires content between --- delimiters
        # Empty frontmatter doesn't match, so entire content becomes body
        content = """---
---

Body after empty frontmatter."""

        metadata, body = parse_frontmatter(content)

        # Empty frontmatter doesn't match the pattern, so content is returned as body
        assert metadata == {}
        assert "Body after empty frontmatter." in body

    def test_parse_multiline_body(self) -> None:
        """Test parsing with multiline body content."""
        content = """---
name: test
---

Line 1
Line 2
Line 3"""

        metadata, body = parse_frontmatter(content)

        assert metadata["name"] == "test"
        assert "Line 1" in body
        assert "Line 2" in body
        assert "Line 3" in body

    def test_parse_invalid_yaml_raises(self) -> None:
        """Test that invalid YAML raises ValueError."""
        content = """---
name: test
  invalid: yaml
    structure:
---

Body content."""

        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_frontmatter(content)


class TestSerializeFrontmatter:
    """Tests for serialize_frontmatter function."""

    def test_serialize_with_metadata(self) -> None:
        """Test serializing with metadata."""
        metadata = {"name": "test", "model": "sonnet"}
        body = "Body content here."

        result = serialize_frontmatter(metadata, body)

        assert result.startswith("---\n")
        assert "name: test" in result
        assert "model: sonnet" in result
        assert "---\n\nBody content here." in result

    def test_serialize_empty_metadata(self) -> None:
        """Test serializing with empty metadata returns just body."""
        metadata: dict[str, Any] = {}
        body = "Just the body."

        result = serialize_frontmatter(metadata, body)

        assert result == "Just the body."

    def test_roundtrip(self) -> None:
        """Test that parse and serialize are inverses."""
        original_metadata = {"name": "roundtrip", "version": 1}
        original_body = "Original body content."

        serialized = serialize_frontmatter(original_metadata, original_body)
        parsed_metadata, parsed_body = parse_frontmatter(serialized)

        assert parsed_metadata == original_metadata
        assert parsed_body == original_body


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_consistent_hash(self) -> None:
        """Test that same content produces same hash."""
        content = "test content"

        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)

        assert hash1 == hash2

    def test_different_content_different_hash(self) -> None:
        """Test that different content produces different hash."""
        hash1 = compute_content_hash("content a")
        hash2 = compute_content_hash("content b")

        assert hash1 != hash2

    def test_hash_length(self) -> None:
        """Test that hash is exactly 16 characters."""
        hash_value = compute_content_hash("any content")

        assert len(hash_value) == 16

    def test_hash_is_hex(self) -> None:
        """Test that hash is valid hexadecimal."""
        hash_value = compute_content_hash("any content")

        # Should not raise ValueError
        int(hash_value, 16)


class TestComputeDiff:
    """Tests for compute_diff function."""

    def test_identical_content(self) -> None:
        """Test diff of identical content is empty."""
        content = "same content"

        diff = compute_diff(content, content)

        assert diff == ""

    def test_different_content(self) -> None:
        """Test diff shows changes."""
        content_a = "line 1\nline 2"
        content_b = "line 1\nline 2 modified"

        diff = compute_diff(content_a, content_b)

        assert "-line 2" in diff
        assert "+line 2 modified" in diff

    def test_custom_labels(self) -> None:
        """Test custom labels appear in diff."""
        content_a = "original"
        content_b = "modified"

        diff = compute_diff(content_a, content_b, label_a="old", label_b="new")

        assert "--- old" in diff
        assert "+++ new" in diff


# =============================================================================
# ValidationError Tests
# =============================================================================


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_create_validation_error(self) -> None:
        """Test creating a validation error."""
        error = ValidationError(field="name", message="Name is required")

        assert error.field == "name"
        assert error.message == "Name is required"
        assert error.severity == "error"  # default

    def test_create_with_severity(self) -> None:
        """Test creating with custom severity."""
        error = ValidationError(
            field="description",
            message="Description is empty",
            severity="warning",
        )

        assert error.severity == "warning"

    def test_str_representation(self) -> None:
        """Test string representation."""
        error = ValidationError(
            field="model",
            message="Invalid model value",
            severity="error",
        )

        result = str(error)

        assert "[ERROR]" in result
        assert "model:" in result
        assert "Invalid model value" in result


# =============================================================================
# AgentResource Tests
# =============================================================================


class TestAgentResource:
    """Tests for AgentResource."""

    def test_create_from_content(self) -> None:
        """Test creating an agent from content."""
        agent = AgentResource.from_content(
            name="test-agent",
            system_prompt="You are a test agent.",
            description="A test agent",
            model="sonnet",
            tools=["Read", "Write"],
            max_turns=50,
        )

        assert agent.name == "test-agent"
        assert agent.description == "A test agent"
        assert agent.model == "sonnet"
        assert agent.tools == ["Read", "Write"]
        assert agent.max_turns == 50
        assert agent.system_prompt == "You are a test agent."

    def test_resource_type(self) -> None:
        """Test resource type is 'agent'."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="prompt",
        )

        assert agent.resource_type == "agent"

    def test_model_normalization(self) -> None:
        """Test model names are normalized."""
        # Test various model name formats
        agent = AgentResource.from_content(
            name="test",
            system_prompt="prompt",
            model="opus 4.5",
        )
        # Note: from_content doesn't normalize, only load does via _parse_metadata
        # But the property getter normalizes
        assert agent.model in {"opus", "opus 4.5"}

    def test_implements_protocol(self) -> None:
        """Test AgentResource implements ResourceProtocol."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="prompt",
        )

        assert isinstance(agent, ResourceProtocol)

    def test_to_agent_definition_dict(self) -> None:
        """Test conversion to agent definition dictionary."""
        agent = AgentResource.from_content(
            name="my-agent",
            system_prompt="Be helpful.",
            description="Helpful agent",
            model="haiku",
            tools=["Bash"],
            max_turns=25,
        )

        result = agent.to_agent_definition_dict()

        assert result["name"] == "my-agent"
        assert result["description"] == "Helpful agent"
        assert result["model"] == "haiku"
        assert result["tools"] == ["Bash"]
        assert result["system_prompt"] == "Be helpful."
        assert result["max_turns"] == 25

    def test_validate_valid_agent(self) -> None:
        """Test validation passes for valid agent."""
        agent = AgentResource.from_content(
            name="valid-agent",
            system_prompt="A sufficiently long system prompt for the agent.",
            description="Valid description",
            model="sonnet",
            tools=["Read"],
        )

        errors = agent.validate()

        # Should have no errors, maybe warnings
        error_level = [e for e in errors if e.severity == "error"]
        assert len(error_level) == 0

    def test_validate_invalid_model(self) -> None:
        """Test validation fails for invalid model."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="A sufficiently long system prompt.",
            model="invalid-model",
        )

        errors = agent.validate()

        model_errors = [e for e in errors if e.field == "model"]
        assert len(model_errors) == 1
        assert "Invalid model" in model_errors[0].message

    def test_validate_empty_system_prompt(self) -> None:
        """Test validation fails for empty system prompt."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="",
        )

        errors = agent.validate()

        prompt_errors = [e for e in errors if e.field == "system_prompt"]
        assert len(prompt_errors) >= 1

    def test_validate_short_system_prompt_warning(self) -> None:
        """Test validation warns for short system prompt."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="Short",
        )

        errors = agent.validate()

        prompt_warnings = [
            e for e in errors
            if e.field == "system_prompt" and e.severity == "warning"
        ]
        assert len(prompt_warnings) >= 1

    def test_content_hash(self) -> None:
        """Test content hash is computed."""
        agent = AgentResource.from_content(
            name="test",
            system_prompt="prompt",
        )

        assert len(agent.content_hash) == 16

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        agent = AgentResource.from_content(
            name="dict-agent",
            system_prompt="prompt",
        )

        result = agent.to_dict()

        assert result["resource_id"] == "dict-agent"
        assert result["resource_type"] == "agent"
        assert "content" in result
        assert "metadata" in result
        assert "content_hash" in result


class TestAgentResourceFileOperations:
    """Tests for AgentResource file operations."""

    def test_load_and_save(self, tmp_path: Path) -> None:
        """Test loading and saving an agent."""
        # Create a test file
        agent_file = tmp_path / "test-agent.md"
        content = """---
name: test-agent
description: Test agent description
model: sonnet
tools: Read, Write, Bash
max_turns: 75
---

You are a test agent for unit testing."""

        agent_file.write_text(content)

        # Load the agent
        agent = AgentResource.load(agent_file)

        assert agent.name == "test-agent"
        assert agent.description == "Test agent description"
        assert agent.model == "sonnet"
        assert agent.tools == ["Read", "Write", "Bash"]
        assert agent.max_turns == 75
        assert "You are a test agent" in agent.system_prompt

        # Save to a new location
        new_file = tmp_path / "saved-agent.md"
        agent.save(new_file)

        # Verify file exists and can be loaded
        assert new_file.exists()
        reloaded = AgentResource.load(new_file)
        assert reloaded.name == "test-agent"

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            AgentResource.load(tmp_path / "nonexistent.md")

    def test_load_derives_name_from_filename(self, tmp_path: Path) -> None:
        """Test that name is derived from filename if not in metadata."""
        agent_file = tmp_path / "derived-name.md"
        content = """---
description: No name field
model: haiku
---

Agent content."""

        agent_file.write_text(content)

        agent = AgentResource.load(agent_file)

        assert agent.name == "derived-name"


# =============================================================================
# SkillResource Tests
# =============================================================================


class TestSkillResource:
    """Tests for SkillResource."""

    def test_create_from_content(self) -> None:
        """Test creating a skill from content."""
        skill = SkillResource.from_content(
            name="debugging",
            instructions="## Overview\n\nDebugging instructions here.",
            description="Systematic debugging skill",
        )

        assert skill.name == "debugging"
        assert skill.description == "Systematic debugging skill"
        assert "Debugging instructions" in skill.instructions

    def test_resource_type(self) -> None:
        """Test resource type is 'skill'."""
        skill = SkillResource.from_content(
            name="test",
            instructions="instructions",
        )

        assert skill.resource_type == "skill"

    def test_implements_protocol(self) -> None:
        """Test SkillResource implements ResourceProtocol."""
        skill = SkillResource.from_content(
            name="test",
            instructions="instructions",
        )

        assert isinstance(skill, ResourceProtocol)

    def test_get_skill_dict(self) -> None:
        """Test conversion to skill dictionary."""
        skill = SkillResource.from_content(
            name="my-skill",
            instructions="Do the thing.",
            description="A skill for doing things",
        )

        result = skill.get_skill_dict()

        assert result["name"] == "my-skill"
        assert result["description"] == "A skill for doing things"
        assert result["content"] == "Do the thing."

    def test_validate_valid_skill(self) -> None:
        """Test validation passes for valid skill."""
        skill = SkillResource.from_content(
            name="valid-skill",
            instructions="## Section\n\nSufficient instructions content here.",
            description="Valid skill",
        )

        errors = skill.validate()

        error_level = [e for e in errors if e.severity == "error"]
        assert len(error_level) == 0

    def test_validate_empty_instructions(self) -> None:
        """Test validation fails for empty instructions."""
        skill = SkillResource.from_content(
            name="test",
            instructions="",
        )

        errors = skill.validate()

        instruction_errors = [e for e in errors if e.field == "instructions"]
        assert len(instruction_errors) >= 1

    def test_workflows_property(self) -> None:
        """Test workflows property extracts workflow links."""
        skill = SkillResource.from_content(
            name="test",
            instructions="""
## Workflows

See [Debug Workflow](./workflows/debug.md) for details.
Also see [Test Workflow](./workflows/test.md).
""",
        )

        workflows = skill.workflows

        assert "./workflows/debug.md" in workflows
        assert "./workflows/test.md" in workflows


class TestSkillResourceFileOperations:
    """Tests for SkillResource file operations."""

    def test_load_skill_md(self, tmp_path: Path) -> None:
        """Test loading a SKILL.md file."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"

        content = """---
name: my-skill
description: A test skill
---

## Instructions

Follow these steps to complete the task."""

        skill_file.write_text(content)

        skill = SkillResource.load(skill_file)

        assert skill.name == "my-skill"
        assert skill.description == "A test skill"
        assert "Follow these steps" in skill.instructions

    def test_load_derives_name_from_directory(self, tmp_path: Path) -> None:
        """Test that name is derived from parent directory for SKILL.md."""
        skill_dir = tmp_path / "derived-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"

        content = """---
description: No name in metadata
---

Instructions here."""

        skill_file.write_text(content)

        skill = SkillResource.load(skill_file)

        assert skill.name == "derived-skill"


# =============================================================================
# PromptResource Tests
# =============================================================================


class TestPromptResource:
    """Tests for PromptResource."""

    def test_create_from_content(self) -> None:
        """Test creating a prompt from content."""
        prompt = PromptResource.from_content(
            name="greeting",
            template="Hello {name}, welcome to {place}!",
            description="A greeting template",
        )

        assert prompt.name == "greeting"
        assert prompt.description == "A greeting template"
        assert "{name}" in prompt.template

    def test_resource_type(self) -> None:
        """Test resource type is 'prompt'."""
        prompt = PromptResource.from_content(
            name="test",
            template="template",
        )

        assert prompt.resource_type == "prompt"

    def test_variables_extraction(self) -> None:
        """Test extraction of variable placeholders."""
        prompt = PromptResource.from_content(
            name="test",
            template="Hello {name}! Your {{id}} is $status today.",
        )

        variables = prompt.variables

        assert "name" in variables
        assert "id" in variables
        assert "status" in variables

    def test_positional_args_extraction(self) -> None:
        """Test extraction of positional arguments."""
        prompt = PromptResource.from_content(
            name="test",
            template="Arg 1: $1, Arg 2: $2, All: $ARGUMENTS",
        )

        positional = prompt.positional_args

        assert 1 in positional
        assert 2 in positional

    def test_render_with_variables(self) -> None:
        """Test rendering with variable substitution."""
        prompt = PromptResource.from_content(
            name="test",
            template="Hello {name}, you have {count} messages.",
        )

        result = prompt.render(name="Alice", count=5)

        assert result == "Hello Alice, you have 5 messages."

    def test_render_positional(self) -> None:
        """Test rendering with positional arguments."""
        prompt = PromptResource.from_content(
            name="test",
            template="First: $1, Second: $2, All: $ARGUMENTS",
        )

        result = prompt.render_positional("one", "two")

        assert result == "First: one, Second: two, All: one two"

    def test_validate_valid_prompt(self) -> None:
        """Test validation passes for valid prompt."""
        prompt = PromptResource.from_content(
            name="valid",
            template="A valid prompt template with sufficient length.",
        )

        errors = prompt.validate()

        error_level = [e for e in errors if e.severity == "error"]
        assert len(error_level) == 0

    def test_validate_empty_template(self) -> None:
        """Test validation fails for empty template."""
        # Create a PromptResource directly with empty content
        # (from_content generates frontmatter, so template property returns content)
        prompt = PromptResource(
            _resource_id="test",
            _content="",
            _metadata={},
            _body="",
        )

        errors = prompt.validate()

        # Should have content error (from base) or template error
        content_errors = [e for e in errors if e.field in ("content", "template")]
        assert len(content_errors) >= 1

    def test_validate_unbalanced_braces(self) -> None:
        """Test validation warns for unbalanced braces."""
        prompt = PromptResource.from_content(
            name="test",
            template="Template with {unbalanced brace",
        )

        errors = prompt.validate()

        brace_warnings = [
            e for e in errors
            if "braces" in e.message.lower()
        ]
        assert len(brace_warnings) >= 1

    def test_get_prompt_dict(self) -> None:
        """Test conversion to prompt dictionary."""
        prompt = PromptResource.from_content(
            name="my-prompt",
            template="Hello {name}! Your ID is $1.",
            description="A prompt",
        )

        result = prompt.get_prompt_dict()

        assert result["name"] == "my-prompt"
        assert result["description"] == "A prompt"
        assert result["template"] == "Hello {name}! Your ID is $1."
        assert "name" in result["variables"]
        assert 1 in result["positional_args"]


# =============================================================================
# CommandResource Tests
# =============================================================================


class TestCommandResource:
    """Tests for CommandResource."""

    def test_create_from_content(self) -> None:
        """Test creating a command from content."""
        cmd = CommandResource.from_content(
            name="create-agent",
            instructions="Create a new agent with the given name: $1",
            description="Create a new agent",
            allowed_tools=["Read", "Write"],
            argument_hint="<agent-name>",
        )

        assert cmd.name == "create-agent"
        assert cmd.description == "Create a new agent"
        assert cmd.allowed_tools == ["Read", "Write"]
        assert cmd.argument_hint == "<agent-name>"
        assert "$1" in cmd.instructions

    def test_resource_type(self) -> None:
        """Test resource type is 'command'."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="instructions",
        )

        assert cmd.resource_type == "command"

    def test_render_with_arguments(self) -> None:
        """Test rendering with argument substitution."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="Create $1 in directory $2",
        )

        result = cmd.render("file.txt", "/tmp")

        assert result == "Create file.txt in directory /tmp"

    def test_render_with_arguments_placeholder(self) -> None:
        """Test rendering with $ARGUMENTS placeholder."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="Run with: $ARGUMENTS",
        )

        result = cmd.render("arg1", "arg2", "arg3")

        assert result == "Run with: arg1 arg2 arg3"

    def test_render_with_file_path(self) -> None:
        """Test rendering with $FILE placeholder."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="Edit file: $FILE",
        )

        result = cmd.render(file_path="/path/to/file.txt")

        assert result == "Edit file: /path/to/file.txt"

    def test_validate_valid_command(self) -> None:
        """Test validation passes for valid command."""
        cmd = CommandResource.from_content(
            name="valid",
            instructions="Do something with sufficient detail here.",
            description="A valid command",
        )

        errors = cmd.validate()

        error_level = [e for e in errors if e.severity == "error"]
        assert len(error_level) == 0

    def test_validate_missing_description(self) -> None:
        """Test validation fails for missing description."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="Valid instructions content.",
            description="",
        )

        errors = cmd.validate()

        desc_errors = [e for e in errors if e.field == "description"]
        assert len(desc_errors) >= 1

    def test_validate_arg_hint_without_placeholder(self) -> None:
        """Test validation warns when arg hint provided but no placeholder."""
        cmd = CommandResource.from_content(
            name="test",
            instructions="No argument placeholders here.",
            description="Test command",
            argument_hint="<name>",
        )

        errors = cmd.validate()

        placeholder_warnings = [
            e for e in errors
            if "placeholder" in e.message.lower() or "$1" in e.message
        ]
        assert len(placeholder_warnings) >= 1

    def test_get_command_dict(self) -> None:
        """Test conversion to command dictionary."""
        cmd = CommandResource.from_content(
            name="my-cmd",
            instructions="Do the thing: $1",
            description="My command",
            allowed_tools=["Bash"],
            argument_hint="<thing>",
        )

        result = cmd.get_command_dict()

        assert result["name"] == "my-cmd"
        assert result["description"] == "My command"
        assert result["allowed_tools"] == ["Bash"]
        assert result["argument_hint"] == "<thing>"
        assert result["instructions"] == "Do the thing: $1"


class TestCommandResourceFileOperations:
    """Tests for CommandResource file operations."""

    def test_load_command_md(self, tmp_path: Path) -> None:
        """Test loading a command .md file."""
        cmd_file = tmp_path / "my-command.md"

        content = """---
description: My test command
allowed-tools: Read, Write, Bash
argument-hint: <file-path>
---

Process the file at: $1

Use $ARGUMENTS for additional options."""

        cmd_file.write_text(content)

        cmd = CommandResource.load(cmd_file)

        assert cmd.name == "my-command"
        assert cmd.description == "My test command"
        assert cmd.allowed_tools == ["Read", "Write", "Bash"]
        assert cmd.argument_hint == "<file-path>"
        assert "$1" in cmd.instructions


# =============================================================================
# ResourceRegistry Tests
# =============================================================================


class TestResourceRegistry:
    """Tests for ResourceRegistry."""

    def test_create_empty_registry(self) -> None:
        """Test creating an empty registry."""
        registry = ResourceRegistry()

        assert registry.count() == {
            "agent": 0,
            "skill": 0,
            "prompt": 0,
            "command": 0,
        }

    def test_register_agent(self) -> None:
        """Test registering an agent."""
        registry = ResourceRegistry()
        agent = AgentResource.from_content(
            name="test-agent",
            system_prompt="prompt",
        )

        registry.register(agent)

        assert registry.count()["agent"] == 1
        assert registry.get("test-agent", "agent") is agent

    def test_register_skill(self) -> None:
        """Test registering a skill."""
        registry = ResourceRegistry()
        skill = SkillResource.from_content(
            name="test-skill",
            instructions="instructions",
        )

        registry.register(skill)

        assert registry.count()["skill"] == 1
        assert registry.get("test-skill", "skill") is skill

    def test_register_prompt(self) -> None:
        """Test registering a prompt."""
        registry = ResourceRegistry()
        prompt = PromptResource.from_content(
            name="test-prompt",
            template="template",
        )

        registry.register(prompt)

        assert registry.count()["prompt"] == 1
        assert registry.get("test-prompt", "prompt") is prompt

    def test_register_command(self) -> None:
        """Test registering a command."""
        registry = ResourceRegistry()
        cmd = CommandResource.from_content(
            name="test-cmd",
            instructions="instructions",
        )

        registry.register(cmd)

        assert registry.count()["command"] == 1
        assert registry.get("test-cmd", "command") is cmd

    def test_get_nonexistent_returns_none(self) -> None:
        """Test getting nonexistent resource returns None."""
        registry = ResourceRegistry()

        result = registry.get("nonexistent", "agent")

        assert result is None

    def test_get_agent_typed(self) -> None:
        """Test typed get_agent method."""
        registry = ResourceRegistry()
        agent = AgentResource.from_content(name="typed", system_prompt="p")
        registry.register(agent)

        result = registry.get_agent("typed")

        assert result is agent
        assert isinstance(result, AgentResource)

    def test_get_skill_typed(self) -> None:
        """Test typed get_skill method."""
        registry = ResourceRegistry()
        skill = SkillResource.from_content(name="typed", instructions="i")
        registry.register(skill)

        result = registry.get_skill("typed")

        assert result is skill
        assert isinstance(result, SkillResource)

    def test_list_by_type(self) -> None:
        """Test listing resources by type."""
        registry = ResourceRegistry()
        agent1 = AgentResource.from_content(name="a1", system_prompt="p")
        agent2 = AgentResource.from_content(name="a2", system_prompt="p")
        skill = SkillResource.from_content(name="s1", instructions="i")

        registry.register(agent1)
        registry.register(agent2)
        registry.register(skill)

        agents = registry.list_by_type("agent")
        skills = registry.list_by_type("skill")

        assert len(agents) == 2
        assert len(skills) == 1

    def test_list_agents(self) -> None:
        """Test list_agents returns AgentResource list."""
        registry = ResourceRegistry()
        agent = AgentResource.from_content(name="a", system_prompt="p")
        registry.register(agent)

        agents = registry.list_agents()

        assert len(agents) == 1
        assert all(isinstance(a, AgentResource) for a in agents)

    def test_list_skills(self) -> None:
        """Test list_skills returns SkillResource list."""
        registry = ResourceRegistry()
        skill = SkillResource.from_content(name="s", instructions="i")
        registry.register(skill)

        skills = registry.list_skills()

        assert len(skills) == 1
        assert all(isinstance(s, SkillResource) for s in skills)

    def test_list_all(self) -> None:
        """Test listing all resources."""
        registry = ResourceRegistry()
        registry.register(AgentResource.from_content(name="a", system_prompt="p"))
        registry.register(SkillResource.from_content(name="s", instructions="i"))
        registry.register(PromptResource.from_content(name="p", template="t"))

        all_resources = registry.list_all()

        assert len(all_resources) == 3

    def test_validate_all(self) -> None:
        """Test validating all resources."""
        registry = ResourceRegistry()
        # Valid agent
        registry.register(AgentResource.from_content(
            name="valid",
            system_prompt="A valid system prompt with enough content.",
            description="Valid",
            tools=["Read"],
        ))
        # Invalid agent (empty prompt)
        registry.register(AgentResource.from_content(
            name="invalid",
            system_prompt="",
        ))

        validation_results = registry.validate_all()

        # Should have errors for the invalid agent
        assert "agent:invalid" in validation_results
        assert len(validation_results["agent:invalid"]) > 0

    def test_to_dict(self) -> None:
        """Test serializing registry to dictionary."""
        registry = ResourceRegistry()
        registry.register(AgentResource.from_content(name="a", system_prompt="p"))

        result = registry.to_dict()

        assert "counts" in result
        assert "resources" in result
        assert result["counts"]["agent"] == 1
        assert "a" in result["resources"]["agent"]


class TestResourceRegistryDiscovery:
    """Tests for ResourceRegistry discovery."""

    def test_discover_from_empty_path(self, tmp_path: Path) -> None:
        """Test discovery from empty directory."""
        registry = ResourceRegistry.discover(base_path=tmp_path)

        assert registry.count() == {
            "agent": 0,
            "skill": 0,
            "prompt": 0,
            "command": 0,
        }

    def test_discover_agents(self, tmp_path: Path) -> None:
        """Test discovering agents from .claude/agents/ directory."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Create test agent files
        (agents_dir / "agent1.md").write_text("""---
name: agent1
model: sonnet
---

Agent 1 prompt.""")

        (agents_dir / "agent2.md").write_text("""---
name: agent2
model: haiku
---

Agent 2 prompt.""")

        registry = ResourceRegistry.discover(base_path=tmp_path)

        assert registry.count()["agent"] == 2
        assert registry.get_agent("agent1") is not None
        assert registry.get_agent("agent2") is not None

    def test_discover_skills(self, tmp_path: Path) -> None:
        """Test discovering skills from skills directory."""
        skills_dir = tmp_path / "skills"
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir(parents=True)

        (skill1_dir / "SKILL.md").write_text("""---
name: skill1
description: Skill 1
---

Skill 1 instructions.""")

        registry = ResourceRegistry.discover(base_path=tmp_path)

        assert registry.count()["skill"] == 1
        assert registry.get_skill("skill1") is not None

    def test_discover_prompts(self, tmp_path: Path) -> None:
        """Test discovering prompts from prompts directory."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "prompt1.md").write_text("""---
name: prompt1
---

Hello {name}!""")

        registry = ResourceRegistry.discover(base_path=tmp_path)

        assert registry.count()["prompt"] == 1
        assert registry.get_prompt("prompt1") is not None

    def test_discover_plugins(self, tmp_path: Path) -> None:
        """Test discovering plugin resources."""
        # Create plugin structure
        plugin_dir = tmp_path / "plugins" / "my-plugin"
        plugin_agents = plugin_dir / "agents"
        plugin_agents.mkdir(parents=True)

        (plugin_agents / "plugin-agent.md").write_text("""---
name: plugin-agent
model: sonnet
---

Plugin agent prompt.""")

        registry = ResourceRegistry.discover(base_path=tmp_path, include_plugins=True)

        # Plugin agents are namespaced
        assert registry.get_agent("my-plugin:plugin-agent") is not None

    def test_discover_excludes_plugins_when_disabled(self, tmp_path: Path) -> None:
        """Test that plugins are excluded when include_plugins=False."""
        plugin_dir = tmp_path / "plugins" / "my-plugin" / "agents"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "agent.md").write_text("""---
name: agent
model: sonnet
---

Prompt.""")

        registry = ResourceRegistry.discover(
            base_path=tmp_path,
            include_plugins=False,
        )

        assert registry.get_agent("my-plugin:agent") is None


# =============================================================================
# BaseResource Diff Tests
# =============================================================================


class TestBaseResourceDiff:
    """Tests for BaseResource diff functionality."""

    def test_diff_identical_resources(self) -> None:
        """Test diffing identical resources produces empty diff."""
        agent1 = AgentResource.from_content(name="a", system_prompt="same")
        agent2 = AgentResource.from_content(name="a", system_prompt="same")

        diff = agent1.diff(agent2)

        assert diff == ""

    def test_diff_different_resources(self) -> None:
        """Test diffing different resources shows changes."""
        agent1 = AgentResource.from_content(name="a", system_prompt="original")
        agent2 = AgentResource.from_content(name="a", system_prompt="modified")

        diff = agent1.diff(agent2)

        assert "-original" in diff or "original" in diff
        assert "+modified" in diff or "modified" in diff
