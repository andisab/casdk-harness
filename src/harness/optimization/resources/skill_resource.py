"""Skill resource wrapper for optimization.

Wraps skill definition files (SKILL.md with YAML frontmatter) as optimizable resources.

Example usage:
    from harness.optimization.resources import SkillResource

    # Load from file
    skill = SkillResource.load(Path("skills/debugging/SKILL.md"))

    # Access properties
    print(skill.name)           # "debugging"
    print(skill.description)    # "Systematic debugging..."
    print(skill.instructions)   # Full instructions content

    # Validate
    errors = skill.validate()
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
class SkillResource(BaseResource):
    """Skill definition resource.

    Wraps skill SKILL.md files with YAML frontmatter containing:
    - name: Skill identifier
    - description: What the skill does

    The body content contains instructions, workflows, and guidelines.
    """

    RESOURCE_TYPE: ClassVar[str] = "skill"

    @property
    def name(self) -> str:
        """Skill name."""
        return self._metadata.get("name", self._resource_id)

    @property
    def description(self) -> str:
        """Skill description."""
        return self._metadata.get("description", "")

    @property
    def instructions(self) -> str:
        """Full instructions (body content)."""
        return self._body

    @property
    def workflows(self) -> list[str]:
        """List of workflow file references found in the content."""
        # Parse workflow links from content
        import re

        pattern = r"\[([^\]]+)\]\(([^)]+\.md)\)"
        matches = re.findall(pattern, self._body)
        return [match[1] for match in matches if "workflow" in match[1].lower()]

    @classmethod
    def _parse_metadata(
        cls,
        metadata: dict[str, Any],
        body: str,
        path: Path,
    ) -> dict[str, Any]:
        """Parse and normalize skill metadata.

        Args:
            metadata: Raw frontmatter metadata.
            body: Body content.
            path: Source file path.

        Returns:
            Normalized metadata dictionary.
        """
        result: dict[str, Any] = {}

        # Name - derive from metadata or parent directory
        if "name" in metadata:
            result["name"] = metadata["name"]
        else:
            # For skills, the parent directory is typically the skill name
            # e.g., skills/debugging/SKILL.md -> debugging
            result["name"] = path.parent.name if path.name == "SKILL.md" else path.stem

        # Description
        result["description"] = metadata.get("description", "")

        # Preserve any additional metadata
        for key, value in metadata.items():
            if key not in result:
                result[key] = value

        return result

    def _validate_specific(self) -> list[ValidationError]:
        """Validate skill-specific requirements.

        Returns:
            List of validation errors.
        """
        errors: list[ValidationError] = []

        # Name validation
        if not self.name:
            errors.append(ValidationError("name", "Skill name is required"))

        # Description validation
        if not self.description:
            errors.append(ValidationError(
                "description",
                "Description is empty",
                severity="warning"
            ))

        # Instructions validation
        if not self.instructions:
            errors.append(ValidationError(
                "instructions",
                "Instructions (body) is empty"
            ))
        elif len(self.instructions) < 20:
            errors.append(ValidationError(
                "instructions",
                "Instructions seem very short (< 20 chars)",
                severity="warning"
            ))

        # Check for structure
        if self.instructions and "##" not in self.instructions:
            errors.append(ValidationError(
                "structure",
                "No markdown sections found - consider adding ## headers",
                severity="info"
            ))

        return errors

    @classmethod
    def from_content(
        cls,
        name: str,
        instructions: str,
        description: str = "",
    ) -> SkillResource:
        """Create a SkillResource from content.

        Args:
            name: Skill name.
            instructions: Instructions content.
            description: Skill description.

        Returns:
            New SkillResource instance.
        """
        metadata = {
            "name": name,
            "description": description,
        }

        # Build content with frontmatter
        from harness.optimization.resources.base import serialize_frontmatter

        content = serialize_frontmatter(metadata, instructions)

        return cls(
            _resource_id=name,
            _content=content,
            _metadata=metadata,
            _body=instructions,
        )

    def get_skill_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for skill registration.

        Returns:
            Dictionary with name, description, content.
        """
        return {
            "name": self.name,
            "description": self.description,
            "content": self.instructions,
        }
