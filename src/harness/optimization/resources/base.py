"""Base types and protocols for optimizable resources.

Provides the ResourceProtocol interface and base implementation for wrapping
agents, skills, prompts, and commands as optimizable resources.

Example usage:
    # Load an agent resource
    from harness.optimization.resources import AgentResource

    agent = AgentResource.load(Path(".claude/agents/python-expert.md"))
    print(agent.resource_id)    # "python-expert"
    print(agent.resource_type)  # "agent"

    # Save with modifications
    agent.save(Path(".claude/agents/python-expert.md"))

    # Check for differences
    original = AgentResource.load(path)
    modified = AgentResource.load(path)
    modified.metadata["version"] = 2
    diff = modified.diff(original)
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

import yaml


@dataclass
class ValidationError:
    """Validation error for a resource.

    Attributes:
        field: The field or section that failed validation.
        message: Description of the validation error.
        severity: Error severity ("error", "warning", "info").
    """

    field: str
    message: str
    severity: str = "error"

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


@runtime_checkable
class ResourceProtocol(Protocol):
    """Protocol for optimizable resources.

    All resource types (agents, skills, prompts, commands) implement this
    interface for unified handling in the optimization system.
    """

    @property
    def resource_id(self) -> str:
        """Unique identifier for the resource."""
        ...

    @property
    def resource_type(self) -> str:
        """Type of resource (agent, skill, prompt, command)."""
        ...

    @property
    def content(self) -> str:
        """Full content of the resource."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Resource metadata (parsed frontmatter, etc.)."""
        ...

    @classmethod
    def load(cls, path: Path) -> ResourceProtocol:
        """Load a resource from a file path.

        Args:
            path: Path to the resource file.

        Returns:
            Loaded resource instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid.
        """
        ...

    def save(self, path: Path) -> None:
        """Save the resource to a file path.

        Args:
            path: Path to save the resource to.
        """
        ...

    def diff(self, other: ResourceProtocol) -> str:
        """Compute a diff between this resource and another.

        Args:
            other: Resource to compare against.

        Returns:
            Unified diff string showing changes.
        """
        ...

    def validate(self) -> list[ValidationError]:
        """Validate the resource.

        Returns:
            List of validation errors (empty if valid).
        """
        ...


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Full file content with optional frontmatter.

    Returns:
        Tuple of (metadata dict, body content).

    Raises:
        ValueError: If frontmatter is malformed.
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        # No frontmatter, entire content is body
        return {}, content.strip()

    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    body = match.group(2).strip()
    return metadata, body


def serialize_frontmatter(metadata: dict[str, Any], body: str) -> str:
    """Serialize metadata and body back to frontmatter format.

    Args:
        metadata: Metadata dictionary.
        body: Body content.

    Returns:
        Full content string with frontmatter.
    """
    if not metadata:
        return body

    # Use default_flow_style=False for readable YAML
    yaml_str = yaml.dump(
        metadata,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    return f"---\n{yaml_str}\n---\n\n{body}\n"


def compute_content_hash(content: str) -> str:
    """Compute a hash of content for deduplication.

    Args:
        content: Content string to hash.

    Returns:
        16-character hex hash.
    """
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def compute_diff(content_a: str, content_b: str, label_a: str = "a", label_b: str = "b") -> str:
    """Compute a unified diff between two content strings.

    Args:
        content_a: Original content.
        content_b: Modified content.
        label_a: Label for original (default: "a").
        label_b: Label for modified (default: "b").

    Returns:
        Unified diff string.
    """
    import difflib

    lines_a = content_a.splitlines(keepends=True)
    lines_b = content_b.splitlines(keepends=True)

    diff = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=label_a,
        tofile=label_b,
    )

    return "".join(diff)


@dataclass
class BaseResource(ABC):
    """Abstract base class for optimizable resources.

    Provides common functionality for all resource types including
    serialization, validation, and diffing.

    Subclasses must implement:
        - resource_type property
        - _parse_metadata() method
        - _validate_specific() method
    """

    # Class-level resource type
    RESOURCE_TYPE: ClassVar[str] = "base"

    # Instance attributes
    _resource_id: str
    _content: str
    _metadata: dict[str, Any] = field(default_factory=dict)
    _body: str = ""
    _source_path: Path | None = None
    _loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def resource_id(self) -> str:
        """Unique identifier for the resource."""
        return self._resource_id

    @property
    def resource_type(self) -> str:
        """Type of resource (agent, skill, prompt, command)."""
        return self.RESOURCE_TYPE

    @property
    def content(self) -> str:
        """Full content of the resource."""
        return self._content

    @property
    def metadata(self) -> dict[str, Any]:
        """Resource metadata (parsed frontmatter, etc.)."""
        return self._metadata

    @property
    def body(self) -> str:
        """Body content (without frontmatter)."""
        return self._body

    @property
    def source_path(self) -> Path | None:
        """Path the resource was loaded from."""
        return self._source_path

    @property
    def content_hash(self) -> str:
        """Content hash for deduplication."""
        return compute_content_hash(self._content)

    @classmethod
    @abstractmethod
    def _parse_metadata(cls, metadata: dict[str, Any], body: str, path: Path) -> dict[str, Any]:
        """Parse and normalize metadata for this resource type.

        Args:
            metadata: Raw frontmatter metadata.
            body: Body content.
            path: Source file path.

        Returns:
            Normalized metadata dictionary.
        """
        ...

    @classmethod
    def load(cls, path: Path) -> BaseResource:
        """Load a resource from a file path.

        Args:
            path: Path to the resource file.

        Returns:
            Loaded resource instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Resource file not found: {path}")

        content = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)

        # Parse type-specific metadata
        parsed_metadata = cls._parse_metadata(metadata, body, path)

        # Derive resource_id from metadata or filename
        resource_id = parsed_metadata.get("name") or path.stem

        return cls(
            _resource_id=resource_id,
            _content=content,
            _metadata=parsed_metadata,
            _body=body,
            _source_path=path,
        )

    def save(self, path: Path) -> None:
        """Save the resource to a file path.

        Args:
            path: Path to save the resource to.
        """
        # Rebuild content from metadata and body
        content = serialize_frontmatter(self._metadata, self._body)

        # Update internal content
        self._content = content
        self._source_path = path

        # Write to file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def diff(self, other: ResourceProtocol) -> str:
        """Compute a diff between this resource and another.

        Args:
            other: Resource to compare against.

        Returns:
            Unified diff string showing changes.
        """
        return compute_diff(
            other.content,
            self.content,
            label_a=f"{other.resource_id} (original)",
            label_b=f"{self.resource_id} (modified)",
        )

    @abstractmethod
    def _validate_specific(self) -> list[ValidationError]:
        """Validate type-specific requirements.

        Returns:
            List of validation errors specific to this resource type.
        """
        ...

    def validate(self) -> list[ValidationError]:
        """Validate the resource.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[ValidationError] = []

        # Common validations
        if not self._resource_id:
            errors.append(ValidationError("resource_id", "Resource ID is required"))

        if not self._content:
            errors.append(ValidationError("content", "Content is empty"))

        if not self._body:
            errors.append(ValidationError(
                "body",
                "Body content is empty",
                severity="warning"
            ))

        # Type-specific validations
        errors.extend(self._validate_specific())

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize the resource to a dictionary.

        Returns:
            Dictionary representation of the resource.
        """
        return {
            "resource_id": self._resource_id,
            "resource_type": self.resource_type,
            "content": self._content,
            "metadata": self._metadata,
            "body": self._body,
            "source_path": str(self._source_path) if self._source_path else None,
            "content_hash": self.content_hash,
            "loaded_at": self._loaded_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"resource_id={self._resource_id!r}, "
            f"resource_type={self.resource_type!r})"
        )
