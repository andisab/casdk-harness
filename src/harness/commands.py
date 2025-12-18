"""Command registry for plugin slash commands.

Manages registration and execution of slash commands defined by plugins.
Commands are exposed to the agent via system prompt and can be invoked
using the /command syntax.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from harness.plugin_manager import PluginCommand

logger = structlog.get_logger(__name__)


class CommandRegistry:
    """Registry for plugin slash commands.

    Commands are registered with namespaced names (plugin:command) and can
    be executed with argument substitution.
    """

    def __init__(self) -> None:
        """Initialize empty command registry."""
        self._commands: dict[str, PluginCommand] = {}

    def register(self, command: PluginCommand) -> None:
        """Register a command.

        Args:
            command: PluginCommand to register.
        """
        if command.name in self._commands:
            logger.warning(
                "Command already registered, overwriting",
                name=command.name,
                plugin=command.plugin_name,
            )

        self._commands[command.name] = command
        logger.debug(
            "Registered command",
            name=command.name,
            plugin=command.plugin_name,
            has_hint=bool(command.argument_hint),
        )

    def register_all(self, commands: dict[str, PluginCommand]) -> None:
        """Register multiple commands.

        Args:
            commands: Dict mapping command names to PluginCommand objects.
        """
        for command in commands.values():
            self.register(command)

    def get(self, name: str) -> PluginCommand | None:
        """Get a command by name.

        Supports both full namespaced names (plugin:command) and
        short names (command) if unambiguous.

        Args:
            name: Command name to look up.

        Returns:
            PluginCommand if found, None otherwise.
        """
        # Try exact match first
        if name in self._commands:
            return self._commands[name]

        # Try short name match (command part only)
        matches = [
            cmd for cmd_name, cmd in self._commands.items()
            if cmd_name.split(":")[-1] == name
        ]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            logger.warning(
                "Ambiguous command name, use full namespaced name",
                name=name,
                matches=[m.name for m in matches],
            )

        return None

    def execute(self, name: str, args: list[str] | None = None) -> str | None:
        """Execute a command with argument substitution.

        Substitution patterns:
        - $1, $2, $3... : Positional arguments
        - $ARGUMENTS : All arguments joined with spaces
        - $FILE : First argument (alias for $1)

        Args:
            name: Command name (with or without leading /).
            args: List of arguments to pass to command.

        Returns:
            Expanded command content, or None if command not found.
        """
        # Strip leading slash if present
        name = name.lstrip("/")

        command = self.get(name)
        if command is None:
            logger.debug("Command not found", name=name)
            return None

        args = args or []
        content = command.content

        # Substitute positional arguments ($1, $2, $3, etc.)
        for i, arg in enumerate(args, start=1):
            content = content.replace(f"${i}", arg)

        # Substitute $ARGUMENTS (all args joined)
        content = content.replace("$ARGUMENTS", " ".join(args))

        # Substitute $FILE (alias for $1)
        if args:
            content = content.replace("$FILE", args[0])
        else:
            content = content.replace("$FILE", "")

        # Clean up any remaining unused placeholders
        content = re.sub(r"\$\d+", "", content)

        logger.debug(
            "Executed command",
            name=command.name,
            args=args,
            content_length=len(content),
        )

        return content

    def list_all(self) -> list[PluginCommand]:
        """Get all registered commands.

        Returns:
            List of all PluginCommand objects.
        """
        return list(self._commands.values())

    def list_by_plugin(self, plugin_name: str) -> list[PluginCommand]:
        """Get commands for a specific plugin.

        Args:
            plugin_name: Plugin name to filter by.

        Returns:
            List of PluginCommand objects from that plugin.
        """
        return [
            cmd for cmd in self._commands.values()
            if cmd.plugin_name == plugin_name
        ]

    def get_help_text(self) -> str:
        """Generate help text listing all commands.

        Returns:
            Formatted help text for display.
        """
        if not self._commands:
            return "No plugin commands registered."

        lines = ["## Plugin Commands\n"]

        # Group by plugin
        by_plugin: dict[str, list[PluginCommand]] = {}
        for cmd in self._commands.values():
            if cmd.plugin_name not in by_plugin:
                by_plugin[cmd.plugin_name] = []
            by_plugin[cmd.plugin_name].append(cmd)

        for plugin_name, commands in sorted(by_plugin.items()):
            lines.append(f"### {plugin_name}\n")
            for cmd in sorted(commands, key=lambda c: c.name):
                hint = f" {cmd.argument_hint}" if cmd.argument_hint else ""
                desc = f" - {cmd.description}" if cmd.description else ""
                lines.append(f"- `/{cmd.name}{hint}`{desc}")
            lines.append("")

        return "\n".join(lines)

    def __len__(self) -> int:
        """Return number of registered commands."""
        return len(self._commands)

    def __contains__(self, name: str) -> bool:
        """Check if a command is registered."""
        return self.get(name) is not None
