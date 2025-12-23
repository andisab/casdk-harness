"""Prompt resource wrapper for optimization.

Wraps raw prompt template files (.md) as optimizable resources.

Example usage:
    from harness.optimization.resources import PromptResource

    # Load from file
    prompt = PromptResource.load(Path("prompts/tech-lead-agent.md"))

    # Access properties
    print(prompt.name)        # "tech-lead-agent"
    print(prompt.template)    # Full prompt template
    print(prompt.variables)   # ["user_input", "context"]

    # Validate
    errors = prompt.validate()
    if errors:
        for error in errors:
            print(error)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from harness.optimization.resources.base import BaseResource, ValidationError


@dataclass
class PromptResource(BaseResource):
    """Raw prompt template resource.

    Wraps prompt .md files which may or may not have frontmatter.
    The entire content (or body if frontmatter present) is the template.

    Supports variable placeholders like:
    - {variable_name}
    - {{variable_name}}
    - $variable_name
    - $1, $2, etc. (positional)
    """

    RESOURCE_TYPE: ClassVar[str] = "prompt"

    @property
    def name(self) -> str:
        """Prompt name."""
        return self._metadata.get("name", self._resource_id)

    @property
    def description(self) -> str:
        """Prompt description."""
        return self._metadata.get("description", "")

    @property
    def template(self) -> str:
        """Full prompt template content."""
        return self._body if self._body else self._content

    @property
    def variables(self) -> list[str]:
        """List of variable placeholders found in the template."""
        template = self.template
        variables: set[str] = set()

        # Find {variable_name} placeholders
        for match in re.findall(r"\{(\w+)\}", template):
            variables.add(match)

        # Find {{variable_name}} placeholders
        for match in re.findall(r"\{\{(\w+)\}\}", template):
            variables.add(match)

        # Find $variable_name placeholders (but not $1, $2, etc.)
        for match in re.findall(r"\$([a-zA-Z_]\w*)", template):
            variables.add(match)

        return sorted(variables)

    @property
    def positional_args(self) -> list[int]:
        """List of positional argument numbers ($1, $2, etc.) found."""
        template = self.template
        positions: set[int] = set()

        for match in re.findall(r"\$(\d+)", template):
            positions.add(int(match))

        return sorted(positions)

    @classmethod
    def _parse_metadata(
        cls,
        metadata: dict[str, Any],
        body: str,
        path: Path,
    ) -> dict[str, Any]:
        """Parse and normalize prompt metadata.

        Args:
            metadata: Raw frontmatter metadata.
            body: Body content.
            path: Source file path.

        Returns:
            Normalized metadata dictionary.
        """
        result: dict[str, Any] = {}

        # Name - derive from metadata or filename
        result["name"] = metadata.get("name", path.stem)

        # Description
        result["description"] = metadata.get("description", "")

        # Preserve any additional metadata
        for key, value in metadata.items():
            if key not in result:
                result[key] = value

        return result

    def _validate_specific(self) -> list[ValidationError]:
        """Validate prompt-specific requirements.

        Returns:
            List of validation errors.
        """
        errors: list[ValidationError] = []

        # Template validation
        if not self.template:
            errors.append(ValidationError(
                "template",
                "Prompt template is empty"
            ))
        elif len(self.template) < 10:
            errors.append(ValidationError(
                "template",
                "Prompt template seems very short (< 10 chars)",
                severity="warning"
            ))

        # Check for unbalanced braces
        template = self.template
        if template.count("{") != template.count("}"):
            errors.append(ValidationError(
                "template",
                "Unbalanced curly braces in template",
                severity="warning"
            ))

        # Check for common issues
        if "TODO" in template.upper() or "FIXME" in template.upper():
            errors.append(ValidationError(
                "template",
                "Template contains TODO/FIXME markers",
                severity="info"
            ))

        return errors

    def render(self, **kwargs: Any) -> str:
        """Render the template with provided variables.

        Args:
            **kwargs: Variable values to substitute.

        Returns:
            Rendered prompt string.
        """
        result = self.template

        # Replace {variable_name} placeholders
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"${key}", str(value))

        return result

    def render_positional(self, *args: str) -> str:
        """Render the template with positional arguments.

        Args:
            *args: Positional argument values.

        Returns:
            Rendered prompt string.
        """
        result = self.template

        for i, value in enumerate(args, start=1):
            result = result.replace(f"${i}", value)

        # Replace $ARGUMENTS with all args joined
        if "$ARGUMENTS" in result:
            result = result.replace("$ARGUMENTS", " ".join(args))

        return result

    @classmethod
    def from_content(
        cls,
        name: str,
        template: str,
        description: str = "",
    ) -> PromptResource:
        """Create a PromptResource from content.

        Args:
            name: Prompt name.
            template: Prompt template content.
            description: Prompt description.

        Returns:
            New PromptResource instance.
        """
        metadata = {
            "name": name,
            "description": description,
        }

        # Build content with frontmatter
        from harness.optimization.resources.base import serialize_frontmatter

        content = serialize_frontmatter(metadata, template)

        return cls(
            _resource_id=name,
            _content=content,
            _metadata=metadata,
            _body=template,
        )

    def get_prompt_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for prompt usage.

        Returns:
            Dictionary with name, description, template, variables.
        """
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "variables": self.variables,
            "positional_args": self.positional_args,
        }
