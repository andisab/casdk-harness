"""Template loader for structure-aware optimization.

Loads templates from the context-engineering plugin to guide prompt optimization,
ensuring optimized prompts follow the expected structure for each resource type.

Example usage:
    from harness.optimization.templates import get_template_loader

    loader = get_template_loader()

    # Get template for agent optimization
    template = loader.get_template("agent")
    print(template.structure_guidance)

    # Get all available templates
    for resource_type in loader.available_types():
        print(f"{resource_type}: {loader.get_template(resource_type).name}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import structlog

logger = structlog.get_logger(__name__)


# Map resource types to template files
TEMPLATE_MAP: dict[str, str] = {
    "agent": "subagent-template.md",
    "skill": "skill-template.md",
    "command": "slash-command-template.md",
    "hook": "hook-configuration-template.md",
}

# Default template directory.
#
# After Step 2b, the canonical templates live in the swe-marketplace
# context-engineering plugin (loaded via the SWE_MARKETPLACE_PATH /
# SWE_MARKETPLACE_REF env vars; see config.HarnessConfig). We resolve at
# import time so the path is stable for tests; runtime callers should
# prefer ``get_template_loader(template_dir=...)`` for explicit overrides.
def _resolve_default_template_dir() -> Path:
    """Pick the canonical template directory.

    Priority:
      1. Marketplace context-engineering/templates (post-Step 2b canonical).
      2. Legacy in-tree path (pre-Step 2b; kept as a transitional fallback
         for tests that have not migrated yet — will be dropped once all
         callers point at marketplace).
    """
    try:
        from harness.config import HarnessConfig

        config = HarnessConfig()
        marketplace = config.swe_marketplace_resolved_path
        if marketplace is not None:
            candidate = marketplace / "plugins" / "context-engineering" / "templates"
            if candidate.exists():
                return candidate
    except Exception:
        pass

    # Fallback: legacy in-tree path. Returned even if it does not exist —
    # the loader logs a warning when files are missing. Removed in Step 2b
    # finalize.
    return Path(__file__).parent.parent.parent / "plugins" / "context-engineering" / "templates"


DEFAULT_TEMPLATE_DIR = _resolve_default_template_dir()


@dataclass
class TemplateInfo:
    """Information about a resource template.

    Attributes:
        resource_type: Type of resource (agent, skill, command, hook).
        name: Template name from filename.
        path: Path to the template file.
        content: Full template content.
        frontmatter_fields: Required/optional YAML frontmatter fields.
        structure_sections: Expected sections in the prompt body.
        structure_guidance: Condensed guidance for optimizers.
    """

    resource_type: str
    name: str
    path: Path
    content: str = ""
    frontmatter_fields: dict[str, str] = field(default_factory=dict)
    structure_sections: list[str] = field(default_factory=list)
    structure_guidance: str = ""

    # Section markers by resource type
    AGENT_SECTIONS: ClassVar[list[str]] = [
        "Core Responsibilities",
        "Approach",
        "Best Practices",
        "Constraints",
        "Success Criteria",
    ]

    SKILL_SECTIONS: ClassVar[list[str]] = [
        "Overview",
        "Capabilities",
        "Usage",
        "Output Format",
        "Examples",
        "Limitations",
    ]

    COMMAND_SECTIONS: ClassVar[list[str]] = [
        # Commands are simpler, mostly prompt content
    ]

    @classmethod
    def from_file(cls, resource_type: str, path: Path) -> TemplateInfo:
        """Load template info from a file.

        Args:
            resource_type: Type of resource.
            path: Path to template file.

        Returns:
            TemplateInfo with parsed content.
        """
        content = path.read_text()

        # Parse frontmatter
        frontmatter_fields = cls._parse_frontmatter_fields(content, resource_type)

        # Get expected sections
        if resource_type == "agent":
            structure_sections = cls.AGENT_SECTIONS.copy()
        elif resource_type == "skill":
            structure_sections = cls.SKILL_SECTIONS.copy()
        else:
            structure_sections = []

        # Generate structure guidance for optimizers
        structure_guidance = cls._generate_guidance(
            resource_type, frontmatter_fields, structure_sections
        )

        return cls(
            resource_type=resource_type,
            name=path.stem,
            path=path,
            content=content,
            frontmatter_fields=frontmatter_fields,
            structure_sections=structure_sections,
            structure_guidance=structure_guidance,
        )

    @staticmethod
    def _parse_frontmatter_fields(content: str, resource_type: str) -> dict[str, str]:
        """Extract frontmatter field definitions from template.

        Args:
            content: Template content.
            resource_type: Type of resource.

        Returns:
            Dict mapping field names to descriptions.
        """
        fields: dict[str, str] = {}

        # Common fields by resource type
        if resource_type == "agent":
            fields = {
                "name": "Agent identifier (lowercase, hyphens)",
                "description": "What the agent does with <example> blocks for discovery",
                "tools": "Comma-separated list of allowed tools (optional)",
                "model": "Model to use: sonnet, opus, haiku (optional)",
                "color": "Hex color for UI (optional)",
                "max_turns": "Maximum conversation turns (optional)",
            }
        elif resource_type == "skill":
            fields = {
                "name": "Skill identifier (lowercase, hyphens)",
                "description": "What the skill does with trigger terms",
                "allowed-tools": "Comma-separated list of allowed tools (optional)",
            }
        elif resource_type == "command":
            fields = {
                "description": "Brief description shown in /help",
                "argument-hint": "Argument syntax hint",
                "allowed-tools": "Comma-separated list of allowed tools (optional)",
                "model": "Model to use (optional)",
            }
        elif resource_type == "hook":
            fields = {
                "name": "Hook identifier",
                "event": "Hook event type",
                "command": "Command to execute",
            }

        return fields

    @staticmethod
    def _generate_guidance(
        resource_type: str,
        frontmatter_fields: dict[str, str],
        structure_sections: list[str],
    ) -> str:
        """Generate concise structure guidance for optimizers.

        Args:
            resource_type: Type of resource.
            frontmatter_fields: Required frontmatter fields.
            structure_sections: Expected sections.

        Returns:
            Guidance string for optimizer prompts.
        """
        lines = [f"## {resource_type.title()} Definition Structure\n"]

        # Frontmatter guidance
        lines.append("### YAML Frontmatter (preserve these fields):")
        for field_name, desc in frontmatter_fields.items():
            lines.append(f"- `{field_name}`: {desc}")

        # Section guidance
        if structure_sections:
            lines.append("\n### Required Sections (use ## headers):")
            for section in structure_sections:
                lines.append(f"- {section}")

        # Resource-specific guidance
        if resource_type == "agent":
            lines.extend([
                "\n### Agent-Specific Requirements:",
                "- Start with role definition: 'You are a [role] specializing in [domain]'",
                "- Include concrete examples with code snippets",
                "- Define clear boundaries in Constraints section",
                "- Keep description field with <example> blocks for discovery",
            ])
        elif resource_type == "skill":
            lines.extend([
                "\n### Skill-Specific Requirements:",
                "- Include trigger terms in description",
                "- Define step-by-step usage instructions",
                "- Provide output format examples",
                "- List what the skill should NOT be used for",
            ])

        return "\n".join(lines)


class TemplateLoader:
    """Loads and caches templates for optimization.

    Provides access to context-engineering templates for structure-aware
    prompt optimization. Templates are loaded lazily and cached.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize the loader.

        Args:
            template_dir: Directory containing templates.
                         Defaults to context-engineering/templates/.
        """
        self.template_dir = template_dir or DEFAULT_TEMPLATE_DIR
        self._cache: dict[str, TemplateInfo] = {}

        if not self.template_dir.exists():
            logger.warning(
                "Template directory not found",
                path=str(self.template_dir),
            )

    def available_types(self) -> list[str]:
        """Get list of available resource types.

        Returns:
            List of resource types with templates.
        """
        available = []
        for resource_type, filename in TEMPLATE_MAP.items():
            template_path = self.template_dir / filename
            if template_path.exists():
                available.append(resource_type)
        return available

    def get_template(self, resource_type: str) -> TemplateInfo | None:
        """Get template info for a resource type.

        Args:
            resource_type: Type of resource (agent, skill, command, hook).

        Returns:
            TemplateInfo if template exists, None otherwise.
        """
        # Check cache first
        if resource_type in self._cache:
            return self._cache[resource_type]

        # Get template filename
        filename = TEMPLATE_MAP.get(resource_type)
        if filename is None:
            logger.warning(
                "Unknown resource type",
                resource_type=resource_type,
                available=list(TEMPLATE_MAP.keys()),
            )
            return None

        # Load template
        template_path = self.template_dir / filename
        if not template_path.exists():
            logger.warning(
                "Template file not found",
                resource_type=resource_type,
                path=str(template_path),
            )
            return None

        try:
            template = TemplateInfo.from_file(resource_type, template_path)
            self._cache[resource_type] = template

            logger.debug(
                "Template loaded",
                resource_type=resource_type,
                sections=len(template.structure_sections),
            )

            return template

        except Exception as e:
            logger.error(
                "Failed to load template",
                resource_type=resource_type,
                error=str(e),
            )
            return None

    def get_structure_guidance(self, resource_type: str) -> str:
        """Get condensed structure guidance for an optimizer.

        Args:
            resource_type: Type of resource.

        Returns:
            Structure guidance string, or empty string if not available.
        """
        template = self.get_template(resource_type)
        if template is None:
            return ""
        return template.structure_guidance

    def get_frontmatter_fields(self, resource_type: str) -> dict[str, str]:
        """Get required frontmatter fields for a resource type.

        Args:
            resource_type: Type of resource.

        Returns:
            Dict mapping field names to descriptions.
        """
        template = self.get_template(resource_type)
        if template is None:
            return {}
        return template.frontmatter_fields

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()


# Module-level singleton
_loader: TemplateLoader | None = None


def get_template_loader(template_dir: Path | None = None) -> TemplateLoader:
    """Get the template loader singleton.

    Args:
        template_dir: Optional custom template directory.

    Returns:
        TemplateLoader instance.
    """
    global _loader

    if _loader is None or template_dir is not None:
        _loader = TemplateLoader(template_dir)

    return _loader
