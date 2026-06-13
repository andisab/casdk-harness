"""Synthesizer for merging optimized prompt sections.

Combines optimized sections with preserved sections to create a coherent
final prompt while maintaining template structure.

Example usage:
    from harness.optimization.analysis.synthesizer import PromptSynthesizer

    synthesizer = PromptSynthesizer(resource_type="agent")
    result = synthesizer.merge(
        original_prompt=original,
        optimized_sections={"core_approach": new_approach},
        preserved_sections=["constraints", "examples"],
    )
    if result.success:
        final_prompt = result.merged_prompt
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

from harness.optimization.analysis.competency_mapper import PromptSection
from harness.optimization.templates import TemplateInfo, get_template_loader

logger = structlog.get_logger(__name__)


# XML-style section tags used in agent prompts
SECTION_TAG_PATTERN = re.compile(
    r"<(\w+)>\s*(.*?)\s*</\1>",
    re.DOTALL | re.IGNORECASE,
)

# Markdown header pattern for sections
HEADER_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# YAML frontmatter pattern
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class ParsedPrompt:
    """A prompt parsed into structural components.

    Attributes:
        frontmatter: YAML frontmatter as dict.
        frontmatter_raw: Original frontmatter string.
        title: Main title (H1 header).
        sections: Dict mapping section names to content.
        section_order: Order of sections as they appear.
        tail: Any content after the last section.
    """

    frontmatter: dict[str, Any] = field(default_factory=dict)
    frontmatter_raw: str = ""
    title: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    section_order: list[str] = field(default_factory=list)
    tail: str = ""


@dataclass
class SynthesisResult:
    """Result of merging optimized sections.

    Attributes:
        success: Whether synthesis was successful.
        merged_prompt: The final merged prompt.
        sections_merged: Sections that were replaced with optimized versions.
        sections_preserved: Sections that were kept from original.
        validation_errors: List of validation errors if any.
        warnings: Non-fatal warnings about the merge.
    """

    success: bool
    merged_prompt: str = ""
    sections_merged: list[str] = field(default_factory=list)
    sections_preserved: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PromptSynthesizer:
    """Synthesizes optimized prompts from section components.

    Parses prompt structure, replaces optimized sections, validates
    integrity, and produces final merged prompt.
    """

    def __init__(
        self,
        resource_type: str = "agent",
        template: TemplateInfo | None = None,
    ) -> None:
        """Initialize the synthesizer.

        Args:
            resource_type: Type of resource (agent, skill, etc.).
            template: Optional template info for validation.
        """
        self.resource_type = resource_type

        if template is None:
            loader = get_template_loader()
            self.template = loader.get_template(resource_type)
        else:
            self.template = template

    def parse_prompt(self, prompt: str) -> ParsedPrompt:
        """Parse a prompt into structural components.

        Args:
            prompt: Raw prompt string.

        Returns:
            ParsedPrompt with parsed components.
        """
        result = ParsedPrompt()

        # Extract frontmatter
        fm_match = FRONTMATTER_PATTERN.match(prompt)
        if fm_match:
            result.frontmatter_raw = fm_match.group(1)
            try:
                result.frontmatter = yaml.safe_load(result.frontmatter_raw) or {}
            except yaml.YAMLError:
                result.frontmatter = {}
            prompt = prompt[fm_match.end():]

        # Extract title (first H1)
        title_match = re.match(r"^#\s+(.+)$", prompt.strip(), re.MULTILINE)
        if title_match:
            result.title = title_match.group(1).strip()

        # Extract XML-style sections
        for match in SECTION_TAG_PATTERN.finditer(prompt):
            section_name = match.group(1).lower()
            section_content = match.group(2).strip()

            result.sections[section_name] = section_content
            if section_name not in result.section_order:
                result.section_order.append(section_name)

        # If no XML sections found, try markdown headers
        if not result.sections:
            self._parse_markdown_sections(prompt, result)

        logger.debug(
            "Parsed prompt",
            frontmatter_fields=list(result.frontmatter.keys()),
            sections=result.section_order,
        )

        return result

    def _parse_markdown_sections(self, prompt: str, result: ParsedPrompt) -> None:
        """Parse markdown header-based sections.

        Args:
            prompt: Prompt content after frontmatter.
            result: ParsedPrompt to update.
        """
        headers = list(HEADER_PATTERN.finditer(prompt))
        if not headers:
            return

        for i, match in enumerate(headers):
            header_level = len(match.group(1))
            header_text = match.group(2).strip()

            # Only process H2 and H3 as sections
            if header_level not in (2, 3):
                continue

            # Section name is header text normalized
            section_name = header_text.lower().replace(" ", "_")

            # Content is text until next header of same or higher level
            start = match.end()
            end = len(prompt)

            for next_match in headers[i + 1:]:
                next_level = len(next_match.group(1))
                if next_level <= header_level:
                    end = next_match.start()
                    break

            content = prompt[start:end].strip()

            result.sections[section_name] = content
            result.section_order.append(section_name)

    def merge(
        self,
        original_prompt: str,
        optimized_sections: dict[str, str],
        preserved_sections: list[str] | None = None,
    ) -> SynthesisResult:
        """Merge optimized sections into original prompt.

        Args:
            original_prompt: Original prompt to modify.
            optimized_sections: Section name → new content mapping.
            preserved_sections: Sections to keep from original (optional).

        Returns:
            SynthesisResult with merged prompt and metadata.
        """
        result = SynthesisResult(success=True)

        # Parse original prompt
        parsed = self.parse_prompt(original_prompt)

        # Determine which sections to preserve
        if preserved_sections is None:
            preserved_sections = [
                s for s in parsed.section_order if s not in optimized_sections
            ]

        # Build section map: use optimized or original
        final_sections: dict[str, str] = {}

        for section_name in parsed.section_order:
            if section_name in optimized_sections:
                final_sections[section_name] = optimized_sections[section_name]
                result.sections_merged.append(section_name)
            else:
                final_sections[section_name] = parsed.sections.get(section_name, "")
                result.sections_preserved.append(section_name)

        # Handle any new sections not in original
        for section_name, content in optimized_sections.items():
            if section_name not in final_sections:
                final_sections[section_name] = content
                result.sections_merged.append(section_name)
                result.warnings.append(f"Added new section: {section_name}")

        # Reconstruct prompt
        result.merged_prompt = self._reconstruct_prompt(
            parsed, final_sections
        )

        # Validate result
        validation_errors = self.validate(result.merged_prompt)
        if validation_errors:
            result.validation_errors = validation_errors
            result.success = False

        logger.info(
            "Merged prompt sections",
            merged=result.sections_merged,
            preserved=result.sections_preserved,
            warnings=result.warnings,
            success=result.success,
        )

        return result

    def _reconstruct_prompt(
        self,
        parsed: ParsedPrompt,
        sections: dict[str, str],
    ) -> str:
        """Reconstruct prompt from parsed components and new sections.

        Args:
            parsed: Original parsed prompt for structure.
            sections: Final section content to use.

        Returns:
            Reconstructed prompt string.
        """
        parts = []

        # Frontmatter
        if parsed.frontmatter_raw:
            parts.append(f"---\n{parsed.frontmatter_raw}\n---\n")

        # Title
        if parsed.title:
            parts.append(f"# {parsed.title}\n")

        # Sections in original order
        for section_name in parsed.section_order:
            if section_name not in sections:
                continue

            content = sections[section_name]

            # Use XML-style tags for known sections
            if self._should_use_xml_tags(section_name):
                parts.append(f"\n<{section_name}>\n{content}\n</{section_name}>\n")
            else:
                # Use markdown header
                header_text = section_name.replace("_", " ").title()
                parts.append(f"\n## {header_text}\n\n{content}\n")

        # Tail content
        if parsed.tail:
            parts.append(f"\n{parsed.tail}")

        return "".join(parts)

    def _should_use_xml_tags(self, section_name: str) -> bool:
        """Determine if a section should use XML-style tags.

        Args:
            section_name: Name of the section.

        Returns:
            True if XML tags should be used.
        """
        # Known XML-tagged sections in agent prompts
        xml_sections = {
            "role_definition",
            "core_approach",
            "best_practices",
            "constraints",
            "examples",
            "output_format",
            "summary",
            "response_style",
            "workflow",
            "error_handling",
        }
        return section_name.lower() in xml_sections

    def validate(self, prompt: str) -> list[str]:
        """Validate a merged prompt against template requirements.

        Args:
            prompt: Merged prompt to validate.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        # Check frontmatter
        if not FRONTMATTER_PATTERN.match(prompt):
            errors.append("Missing YAML frontmatter")
        else:
            fm_match = FRONTMATTER_PATTERN.match(prompt)
            if fm_match:
                try:
                    frontmatter = yaml.safe_load(fm_match.group(1)) or {}

                    # Check required fields for resource type
                    if self.template:
                        for field_name in self.template.frontmatter_fields:
                            # Only error on truly required fields that are missing
                            if field_name not in frontmatter and field_name in (
                                "name",
                                "description",
                            ):
                                errors.append(
                                    f"Missing required frontmatter: {field_name}"
                                )
                except yaml.YAMLError as e:
                    errors.append(f"Invalid YAML frontmatter: {e}")

        # Check for required sections
        if self.template and self.template.structure_sections:
            parsed = self.parse_prompt(prompt)
            for section in self.template.structure_sections:
                section_key = section.lower().replace(" ", "_")
                if section_key not in parsed.sections:
                    # Warn but don't error - sections may be renamed
                    logger.debug(
                        "Expected section not found",
                        section=section,
                        found_sections=list(parsed.sections.keys()),
                    )

        # Check for balanced XML tags
        open_tags = re.findall(r"<(\w+)>", prompt)
        close_tags = re.findall(r"</(\w+)>", prompt)

        open_set = {tag.lower() for tag in open_tags}
        close_set = {tag.lower() for tag in close_tags}

        unmatched = open_set - close_set
        if unmatched:
            errors.append(f"Unmatched opening tags: {unmatched}")

        unmatched_close = close_set - open_set
        if unmatched_close:
            errors.append(f"Unmatched closing tags: {unmatched_close}")

        return errors


def merge_optimized_sections(
    original_prompt: str,
    optimized_sections: dict[PromptSection, str],
    resource_type: str = "agent",
) -> SynthesisResult:
    """Convenience function to merge optimized sections.

    Args:
        original_prompt: Original prompt text.
        optimized_sections: Mapping of section enum to optimized content.
        resource_type: Type of resource.

    Returns:
        SynthesisResult with merged prompt.
    """
    # Convert PromptSection enum keys to strings
    sections_dict = {
        section.value: content
        for section, content in optimized_sections.items()
    }

    synthesizer = PromptSynthesizer(resource_type)
    return synthesizer.merge(original_prompt, sections_dict)


def save_optimized_prompt(
    prompt: str,
    output_path: Path,
    backup_original: bool = True,
) -> Path:
    """Save optimized prompt to file.

    Args:
        prompt: Optimized prompt content.
        output_path: Path to save the prompt.
        backup_original: If True and file exists, create .bak backup.

    Returns:
        Path where prompt was saved.
    """
    # Create backup if needed
    if backup_original and output_path.exists():
        backup_path = output_path.with_suffix(output_path.suffix + ".bak")
        output_path.rename(backup_path)
        logger.info("Created backup", path=str(backup_path))

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write prompt
    output_path.write_text(prompt)

    logger.info("Saved optimized prompt", path=str(output_path))
    return output_path


def extract_section_from_prompt(prompt: str, section: PromptSection) -> str | None:
    """Extract a specific section from a prompt.

    Args:
        prompt: Full prompt content.
        section: Section to extract.

    Returns:
        Section content or None if not found.
    """
    synthesizer = PromptSynthesizer()
    parsed = synthesizer.parse_prompt(prompt)
    return parsed.sections.get(section.value)


def extract_all_sections_from_prompt(
    prompt: str,
) -> dict[PromptSection, str]:
    """Extract all sections from a prompt.

    Args:
        prompt: Full prompt content.

    Returns:
        Dictionary mapping PromptSection to content.
    """
    synthesizer = PromptSynthesizer()
    parsed = synthesizer.parse_prompt(prompt)

    result: dict[PromptSection, str] = {}
    for section_name, content in parsed.sections.items():
        try:
            section = PromptSection(section_name)
            result[section] = content
        except ValueError:
            # Unknown section name, skip
            continue

    return result


def replace_section_in_prompt(
    prompt: str,
    section: PromptSection,
    new_content: str,
) -> str:
    """Replace a single section in a prompt.

    Args:
        prompt: Full prompt content.
        section: Section to replace.
        new_content: New content for the section.

    Returns:
        Prompt with section replaced.
    """
    result = merge_optimized_sections(
        prompt,
        {section: new_content},
    )
    return result.merged_prompt
