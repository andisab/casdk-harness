"""Agent resource wrapper for optimization.

Wraps agent definition files (.md with YAML frontmatter) as optimizable resources.

Example usage:
    from harness.optimization.resources import AgentResource

    # Load from file
    agent = AgentResource.load(Path(".claude/agents/python-expert.md"))

    # Access properties
    print(agent.name)           # "python-expert"
    print(agent.model)          # "opus"
    print(agent.tools)          # ["Read", "Write", ...]
    print(agent.system_prompt)  # Full system prompt content

    # Validate
    errors = agent.validate()
    if errors:
        for error in errors:
            print(error)

    # Save modifications
    agent.metadata["model"] = "sonnet"
    agent.save(Path(".claude/agents/python-expert.md"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from harness.optimization.resources.base import BaseResource, ValidationError


# Model name mapping for normalization
MODEL_MAP: dict[str, str] = {
    "opus 4.1": "opus",
    "opus 4.5": "opus",
    "sonnet 4.5": "sonnet",
    "sonnet 4.0": "sonnet",
    "haiku 3.5": "haiku",
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
}

# Valid models
VALID_MODELS = {"sonnet", "opus", "haiku"}


@dataclass
class AgentResource(BaseResource):
    """Agent definition resource.

    Wraps agent .md files with YAML frontmatter containing:
    - name: Agent identifier
    - description: What the agent does
    - model: Model to use (sonnet, opus, haiku)
    - tools: Comma-separated list of allowed tools
    - max_turns: Maximum conversation turns (optional)
    - color: Display color (optional)

    The body content becomes the system prompt.
    """

    RESOURCE_TYPE: ClassVar[str] = "agent"

    @property
    def name(self) -> str:
        """Agent name."""
        return self._metadata.get("name", self._resource_id)

    @property
    def description(self) -> str:
        """Agent description."""
        return self._metadata.get("description", "")

    @property
    def model(self) -> str:
        """Model to use (normalized)."""
        raw_model = self._metadata.get("model", "sonnet")
        return MODEL_MAP.get(raw_model, raw_model)

    @property
    def tools(self) -> list[str]:
        """List of allowed tools."""
        return self._metadata.get("tools", [])

    @property
    def max_turns(self) -> int:
        """Maximum conversation turns."""
        return self._metadata.get("max_turns", 100)

    @property
    def system_prompt(self) -> str:
        """System prompt (body content)."""
        return self._body

    @property
    def color(self) -> str | None:
        """Optional display color."""
        return self._metadata.get("color")

    @classmethod
    def _parse_metadata(
        cls,
        metadata: dict[str, Any],
        body: str,
        path: Path,
    ) -> dict[str, Any]:
        """Parse and normalize agent metadata.

        Args:
            metadata: Raw frontmatter metadata.
            body: Body content.
            path: Source file path.

        Returns:
            Normalized metadata dictionary.
        """
        result: dict[str, Any] = {}

        # Name - required
        result["name"] = metadata.get("name", path.stem)

        # Description - normalize multiline
        description = metadata.get("description", "")
        if isinstance(description, str):
            # Take first sentence/line for short description
            lines = description.strip().split("\n")
            short_desc = lines[0].strip() if lines else ""
            if len(short_desc) > 200:
                short_desc = short_desc[:197] + "..."
            result["description"] = short_desc
            result["full_description"] = description.strip()
        else:
            result["description"] = str(description)
            result["full_description"] = str(description)

        # Model - normalize
        raw_model = metadata.get("model", "sonnet")
        result["model"] = MODEL_MAP.get(raw_model, raw_model)

        # Tools - parse comma-separated string
        tools_str = metadata.get("tools", "")
        if isinstance(tools_str, str):
            result["tools"] = [t.strip() for t in tools_str.split(",") if t.strip()]
        elif isinstance(tools_str, list):
            result["tools"] = tools_str
        else:
            result["tools"] = []

        # Max turns
        result["max_turns"] = metadata.get("max_turns", 100)

        # Color (optional)
        if "color" in metadata:
            result["color"] = metadata["color"]

        return result

    def _validate_specific(self) -> list[ValidationError]:
        """Validate agent-specific requirements.

        Returns:
            List of validation errors.
        """
        errors: list[ValidationError] = []

        # Name validation
        if not self.name:
            errors.append(ValidationError("name", "Agent name is required"))

        # Model validation
        if self.model not in VALID_MODELS:
            errors.append(ValidationError(
                "model",
                f"Invalid model '{self.model}'. Must be one of: {VALID_MODELS}"
            ))

        # Tools validation
        if not self.tools:
            errors.append(ValidationError(
                "tools",
                "No tools specified - agent won't be able to use any tools",
                severity="warning"
            ))

        # System prompt validation
        if not self.system_prompt:
            errors.append(ValidationError(
                "system_prompt",
                "System prompt (body) is empty"
            ))
        elif len(self.system_prompt) < 50:
            errors.append(ValidationError(
                "system_prompt",
                "System prompt seems very short (< 50 chars)",
                severity="warning"
            ))

        # Description validation
        if not self.description:
            errors.append(ValidationError(
                "description",
                "Description is empty - helps with agent selection",
                severity="warning"
            ))

        return errors

    def to_agent_definition_dict(self) -> dict[str, Any]:
        """Convert to a dictionary compatible with AgentDefinition.

        Returns:
            Dictionary with name, description, model, tools, system_prompt, max_turns.
        """
        return {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "tools": self.tools,
            "system_prompt": self.system_prompt,
            "max_turns": self.max_turns,
        }

    @classmethod
    def from_content(
        cls,
        name: str,
        system_prompt: str,
        description: str = "",
        model: str = "sonnet",
        tools: list[str] | None = None,
        max_turns: int = 100,
    ) -> AgentResource:
        """Create an AgentResource from content.

        Args:
            name: Agent name.
            system_prompt: System prompt content.
            description: Agent description.
            model: Model to use.
            tools: List of allowed tools.
            max_turns: Maximum conversation turns.

        Returns:
            New AgentResource instance.
        """
        tools = tools or []
        metadata = {
            "name": name,
            "description": description,
            "model": model,
            "tools": tools,
            "max_turns": max_turns,
        }

        # Build content with frontmatter
        from harness.optimization.resources.base import serialize_frontmatter

        content = serialize_frontmatter(metadata, system_prompt)

        return cls(
            _resource_id=name,
            _content=content,
            _metadata=metadata,
            _body=system_prompt,
        )
