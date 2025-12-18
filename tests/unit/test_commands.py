"""Unit tests for CommandRegistry.

Tests command registration, lookup, and execution with argument substitution.
"""

import pytest
import structlog

from harness.commands import CommandRegistry
from harness.plugin_manager import PluginCommand

logger = structlog.get_logger(__name__)


@pytest.fixture
def sample_commands():
    """Create sample commands for testing."""
    return [
        PluginCommand(
            name="test-plugin:hello",
            description="Say hello",
            content="Hello, $1!",
            plugin_name="test-plugin",
        ),
        PluginCommand(
            name="test-plugin:greet",
            description="Greet with arguments",
            content="Greeting: $ARGUMENTS",
            plugin_name="test-plugin",
            argument_hint="<name> [message]",
        ),
        PluginCommand(
            name="other-plugin:hello",
            description="Another hello command",
            content="Hi from other plugin!",
            plugin_name="other-plugin",
        ),
        PluginCommand(
            name="test-plugin:format",
            description="Format with file",
            content="Formatting $FILE with options $2 $3",
            plugin_name="test-plugin",
            allowed_tools=["Read", "Write"],
        ),
    ]


class TestCommandRegistration:
    """Test command registration."""

    def test_register_command(self, sample_commands):
        """Test registering a single command."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])

        assert len(registry) == 1
        assert "test-plugin:hello" in registry

    def test_register_all(self, sample_commands):
        """Test registering multiple commands."""
        registry = CommandRegistry()
        commands_dict = {cmd.name: cmd for cmd in sample_commands}
        registry.register_all(commands_dict)

        assert len(registry) == 4

    def test_register_duplicate_warns(self, sample_commands, caplog):
        """Test that registering duplicate command warns."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])
        registry.register(sample_commands[0])

        # Should still have only one command
        assert len(registry) == 1


class TestCommandLookup:
    """Test command lookup."""

    def test_get_by_full_name(self, sample_commands):
        """Test getting command by full namespaced name."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        cmd = registry.get("test-plugin:hello")
        assert cmd is not None
        assert cmd.name == "test-plugin:hello"

    def test_get_by_short_name_unambiguous(self, sample_commands):
        """Test getting command by short name when unambiguous."""
        registry = CommandRegistry()
        # Only register one command
        registry.register(sample_commands[1])  # greet

        cmd = registry.get("greet")
        assert cmd is not None
        assert cmd.name == "test-plugin:greet"

    def test_get_by_short_name_ambiguous(self, sample_commands):
        """Test that ambiguous short name returns None."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        # "hello" is ambiguous (test-plugin:hello and other-plugin:hello)
        cmd = registry.get("hello")
        assert cmd is None

    def test_get_nonexistent(self, sample_commands):
        """Test getting nonexistent command returns None."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        cmd = registry.get("nonexistent")
        assert cmd is None


class TestCommandExecution:
    """Test command execution with argument substitution."""

    def test_execute_with_positional_arg(self, sample_commands):
        """Test executing command with $1 substitution."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])  # hello

        result = registry.execute("test-plugin:hello", ["World"])
        assert result == "Hello, World!"

    def test_execute_with_arguments(self, sample_commands):
        """Test executing command with $ARGUMENTS substitution."""
        registry = CommandRegistry()
        registry.register(sample_commands[1])  # greet

        result = registry.execute("test-plugin:greet", ["Alice", "how", "are", "you"])
        assert result == "Greeting: Alice how are you"

    def test_execute_with_file_alias(self, sample_commands):
        """Test executing command with $FILE substitution."""
        registry = CommandRegistry()
        registry.register(sample_commands[3])  # format

        result = registry.execute("test-plugin:format", ["test.py", "--check", "-v"])
        assert result == "Formatting test.py with options --check -v"

    def test_execute_with_leading_slash(self, sample_commands):
        """Test that leading slash is stripped."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])

        result = registry.execute("/test-plugin:hello", ["World"])
        assert result == "Hello, World!"

    def test_execute_no_args(self, sample_commands):
        """Test executing command without required args."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])

        result = registry.execute("test-plugin:hello", [])
        # $1 should be replaced with empty string and cleaned up
        assert result == "Hello, !"

    def test_execute_nonexistent(self, sample_commands):
        """Test executing nonexistent command returns None."""
        registry = CommandRegistry()
        registry.register(sample_commands[0])

        result = registry.execute("nonexistent", ["arg"])
        assert result is None


class TestCommandListing:
    """Test command listing methods."""

    def test_list_all(self, sample_commands):
        """Test listing all commands."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        all_cmds = registry.list_all()
        assert len(all_cmds) == 4

    def test_list_by_plugin(self, sample_commands):
        """Test listing commands by plugin."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        test_plugin_cmds = registry.list_by_plugin("test-plugin")
        assert len(test_plugin_cmds) == 3

        other_plugin_cmds = registry.list_by_plugin("other-plugin")
        assert len(other_plugin_cmds) == 1


class TestCommandHelpText:
    """Test help text generation."""

    def test_get_help_text_empty(self):
        """Test help text when no commands registered."""
        registry = CommandRegistry()
        help_text = registry.get_help_text()

        assert "No plugin commands registered" in help_text

    def test_get_help_text_with_commands(self, sample_commands):
        """Test help text with registered commands."""
        registry = CommandRegistry()
        registry.register_all({cmd.name: cmd for cmd in sample_commands})

        help_text = registry.get_help_text()

        assert "## Plugin Commands" in help_text
        assert "test-plugin" in help_text
        assert "other-plugin" in help_text
        assert "/test-plugin:hello" in help_text
        assert "<name> [message]" in help_text  # argument hint
