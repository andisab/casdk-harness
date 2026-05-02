"""Command resource wrapper for optimization.

Wraps command definition files (.md with YAML frontmatter) as optimizable resources.

Example usage:
    from harness.optimization.resources import CommandResource

    # Load from file
    cmd = CommandResource.load(Path("commands/create-agent.md"))

    # Access properties
    print(cmd.name)           # "create-agent"
    print(cmd.description)    # "Create a new agent..."
    print(cmd.allowed_tools)  # ["Read", "Write", "Edit"]
    print(cmd.argument_hint)  # "<agent-name>"
    print(cmd.instructions)   # Full command instructions

    # Validate
    errors = cmd.validate()
    if errors:
        for error in errors:
            print(error)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from harness.optimization.resources.base import BaseResource, ValidationError


@dataclass
class CommandResource(BaseResource):
    """Command definition resource.

    Wraps command .md files with YAML frontmatter containing:
    - description: What the command does
    - allowed-tools: List of tools the command can use
    - argument-hint: Help text for arguments (e.g., "<agent-name>")

    The body content contains instructions for executing the command.
    Supports argument substitution: $1, $2, $ARGUMENTS, $FILE.
    """

    RESOURCE_TYPE: ClassVar[str] = "command"

    @property
    def name(self) -> str:
        """Command name."""
        return self._metadata.get("name", self._resource_id)

    @property
    def description(self) -> str:
        """Command description."""
        return self._metadata.get("description", "")

    @property
    def allowed_tools(self) -> list[str]:
        """List of allowed tools."""
        return self._metadata.get("allowed_tools", [])

    @property
    def argument_hint(self) -> str:
        """Argument hint text."""
        return self._metadata.get("argument_hint", "")

    @property
    def instructions(self) -> str:
        """Command instructions (body content)."""
        return self._body

    @classmethod
    def _parse_metadata(
        cls,
        metadata: dict[str, Any],
        body: str,
        path: Path,
    ) -> dict[str, Any]:
        """Parse and normalize command metadata.

        Args:
            metadata: Raw frontmatter metadata.
            body: Body content.
            path: Source file path.

        Returns:
            Normalized metadata dictionary.
        """
        result: dict[str, Any] = {}

        # Name - derive from filename
        result["name"] = path.stem

        # Description
        result["description"] = metadata.get("description", "")

        # Allowed tools - parse from 'allowed-tools' with hyphen
        tools_str = metadata.get("allowed-tools", "")
        if isinstance(tools_str, str):
            result["allowed_tools"] = [t.strip() for t in tools_str.split(",") if t.strip()]
        elif isinstance(tools_str, list):
            result["allowed_tools"] = tools_str
        else:
            result["allowed_tools"] = []

        # Argument hint
        result["argument_hint"] = metadata.get("argument-hint", "")

        # Preserve any additional metadata
        for key, value in metadata.items():
            normalized_key = key.replace("-", "_")
            if normalized_key not in result:
                result[normalized_key] = value

        return result

    def _validate_specific(self) -> list[ValidationError]:
        """Validate command-specific requirements.

        Returns:
            List of validation errors.
        """
        errors: list[ValidationError] = []

        # Description validation
        if not self.description:
            errors.append(ValidationError(
                "description",
                "Description is required for commands"
            ))

        # Instructions validation
        if not self.instructions:
            errors.append(ValidationError(
                "instructions",
                "Command instructions (body) is empty"
            ))
        elif len(self.instructions) < 10:
            errors.append(ValidationError(
                "instructions",
                "Instructions seem very short (< 10 chars)",
                severity="warning"
            ))

        # Check for argument placeholders if hint suggests arguments
        if self.argument_hint:
            if "$1" not in self.instructions and "$ARGUMENTS" not in self.instructions:
                errors.append(ValidationError(
                    "instructions",
                    f"Argument hint '{self.argument_hint}' provided but no $1 or $ARGUMENTS in instructions",
                    severity="warning"
                ))

        return errors

    def render(self, *args: str, file_path: str | None = None) -> str:
        """Render the command instructions with provided arguments.

        Args:
            *args: Positional arguments.
            file_path: Optional file path for $FILE substitution.

        Returns:
            Rendered instructions string.
        """
        result = self.instructions

        # Replace positional arguments
        for i, value in enumerate(args, start=1):
            result = result.replace(f"${i}", value)

        # Replace $ARGUMENTS with all args joined
        if "$ARGUMENTS" in result:
            result = result.replace("$ARGUMENTS", " ".join(args))

        # Replace $FILE if provided
        if file_path and "$FILE" in result:
            result = result.replace("$FILE", file_path)

        return result

    @classmethod
    def from_content(
        cls,
        name: str,
        instructions: str,
        description: str = "",
        allowed_tools: list[str] | None = None,
        argument_hint: str = "",
    ) -> CommandResource:
        """Create a CommandResource from content.

        Args:
            name: Command name.
            instructions: Command instructions.
            description: Command description.
            allowed_tools: List of allowed tools.
            argument_hint: Argument hint text.

        Returns:
            New CommandResource instance.
        """
        allowed_tools = allowed_tools or []
        metadata = {
            "name": name,
            "description": description,
            "allowed_tools": allowed_tools,
            "argument_hint": argument_hint,
        }

        # Build content with frontmatter (using hyphenated keys)
        frontmatter_metadata = {
            "description": description,
            "allowed-tools": ", ".join(allowed_tools) if allowed_tools else "",
            "argument-hint": argument_hint,
        }

        from harness.optimization.resources.base import serialize_frontmatter

        content = serialize_frontmatter(frontmatter_metadata, instructions)

        return cls(
            _resource_id=name,
            _content=content,
            _metadata=metadata,
            _body=instructions,
        )

    def get_command_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for command registration.

        Returns:
            Dictionary with name, description, allowed_tools, argument_hint.
        """
        return {
            "name": self.name,
            "description": self.description,
            "allowed_tools": self.allowed_tools,
            "argument_hint": self.argument_hint,
            "instructions": self.instructions,
        }
