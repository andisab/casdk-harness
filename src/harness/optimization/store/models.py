"""Data models for the CGF Optimization Store.

This module defines the core data structures used by the optimization store
for tracking resources, evaluations, and results.

Example usage:
    # Create an evaluation task
    task = EvaluationTask(
        evaluation_id="eval-123",
        resource_id="agent-python-expert",
        resource_type="agent",
        config={"test_cases": ["test1", "test2"]},
    )

    # Create an evaluation result
    result = EvaluationResult(
        evaluation_id="eval-123",
        resource_id="agent-python-expert",
        reward={"task_completion": 0.9, "efficiency": 0.8},
    )
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EvaluationStatus(Enum):
    """Status of an evaluation task."""

    PENDING = "pending"
    """Task is queued and waiting for a runner."""

    IN_PROGRESS = "in_progress"
    """Task has been claimed by a runner."""

    COMPLETED = "completed"
    """Task finished successfully."""

    FAILED = "failed"
    """Task failed with an error."""

    TIMEOUT = "timeout"
    """Task exceeded its time limit."""

    CANCELLED = "cancelled"
    """Task was cancelled before completion."""


class ResourceType(Enum):
    """Types of optimizable resources."""

    AGENT = "agent"
    """Agent definition (system prompt, tools, etc.)."""

    SKILL = "skill"
    """Skill definition (activation, execution)."""

    PROMPT = "prompt"
    """Raw prompt template."""

    COMMAND = "command"
    """Command definition."""


def generate_evaluation_id() -> str:
    """Generate a unique evaluation ID."""
    return f"eval-{uuid.uuid4().hex[:12]}"


def generate_version_id() -> str:
    """Generate a unique version ID."""
    return f"v-{uuid.uuid4().hex[:8]}"


def compute_content_hash(content: str) -> str:
    """Compute a hash of content for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ResourceVersion:
    """Version information for a resource.

    Tracks when a resource version was created and its content hash
    for detecting duplicate content.

    Attributes:
        version: Version number (1-indexed, increments with each update).
        version_id: Unique version identifier.
        content_hash: Hash of the resource content.
        created_at: When this version was created.
        metadata: Version-specific metadata.
    """

    version: int
    version_id: str = field(default_factory=generate_version_id)
    content_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "version_id": self.version_id,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceVersion:
        """Deserialize from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            version=data["version"],
            version_id=data.get("version_id", generate_version_id()),
            content_hash=data.get("content_hash", ""),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class Resource:
    """An optimizable resource (agent, skill, prompt, command).

    Resources are versioned, allowing tracking of changes over time
    and comparison of different versions' performance.

    Attributes:
        resource_id: Unique identifier for the resource.
        resource_type: Type of resource (agent, skill, prompt, command).
        content: The resource content (definition text, prompt, etc.).
        current_version: Current version information.
        metadata: Resource metadata (source path, description, etc.).
        created_at: When the resource was first registered.
        updated_at: When the resource was last updated.
    """

    resource_id: str
    resource_type: str
    content: str
    current_version: ResourceVersion
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "content": self.content,
            "current_version": self.current_version.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Resource:
        """Deserialize from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now(timezone.utc)

        return cls(
            resource_id=data["resource_id"],
            resource_type=data["resource_type"],
            content=data["content"],
            current_version=ResourceVersion.from_dict(data["current_version"]),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class EvaluationTask:
    """A queued evaluation task.

    Represents a request to evaluate a resource, with configuration
    for how the evaluation should be performed.

    Attributes:
        evaluation_id: Unique evaluation identifier.
        resource_id: The resource to evaluate.
        resource_type: Type of resource being evaluated.
        config: Evaluation configuration (test cases, parameters).
        priority: Higher priority = processed first.
        status: Current status of the evaluation.
        runner_id: ID of the runner processing this task (if claimed).
        created_at: When the task was created.
        started_at: When the task was claimed by a runner.
        completed_at: When the task finished.
        timeout_at: When the task will timeout if not completed.
        error_message: Error details if failed.
    """

    evaluation_id: str = field(default_factory=generate_evaluation_id)
    resource_id: str = ""
    resource_type: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    status: EvaluationStatus = EvaluationStatus.PENDING
    runner_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout_at: datetime | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "evaluation_id": self.evaluation_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "config": self.config,
            "priority": self.priority,
            "status": self.status.value,
            "runner_id": self.runner_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "timeout_at": self.timeout_at.isoformat() if self.timeout_at else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationTask:
        """Deserialize from dictionary."""

        def parse_datetime(value: str | datetime | None) -> datetime | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value)

        created_at = parse_datetime(data.get("created_at"))
        if created_at is None:
            created_at = datetime.now(timezone.utc)

        status = data.get("status", "pending")
        if isinstance(status, str):
            status = EvaluationStatus(status)

        return cls(
            evaluation_id=data.get("evaluation_id", generate_evaluation_id()),
            resource_id=data.get("resource_id", ""),
            resource_type=data.get("resource_type", ""),
            config=data.get("config", {}),
            priority=data.get("priority", 0),
            status=status,
            runner_id=data.get("runner_id"),
            created_at=created_at,
            started_at=parse_datetime(data.get("started_at")),
            completed_at=parse_datetime(data.get("completed_at")),
            timeout_at=parse_datetime(data.get("timeout_at")),
            error_message=data.get("error_message"),
        )


@dataclass
class EvaluationResult:
    """Result of an evaluation.

    Captures the multi-dimensional reward scores from evaluating
    a resource, along with metadata about the evaluation.

    Attributes:
        evaluation_id: The evaluation this result is for.
        resource_id: The evaluated resource.
        resource_type: Type of resource evaluated.
        resource_version: Version of the resource that was evaluated.
        reward: Multi-dimensional reward scores (0.0 - 1.0 each).
        composite_score: Weighted composite score.
        metadata: Additional evaluation metadata.
        created_at: When the result was recorded.
    """

    evaluation_id: str
    resource_id: str
    resource_type: str = ""
    resource_version: int = 1
    reward: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Compute composite score if not set."""
        if self.composite_score == 0.0 and self.reward:
            self.composite_score = self.compute_composite()

    def compute_composite(
        self,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Compute weighted composite score.

        Args:
            weights: Optional custom weights. Defaults to equal weighting.

        Returns:
            Weighted average of reward dimensions.
        """
        if not self.reward:
            return 0.0

        if weights is None:
            # Default: equal weighting
            weights = {k: 1.0 for k in self.reward}

        total_weight = sum(weights.get(k, 0.0) for k in self.reward)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            self.reward[k] * weights.get(k, 0.0) for k in self.reward
        )
        return weighted_sum / total_weight

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "evaluation_id": self.evaluation_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "resource_version": self.resource_version,
            "reward": self.reward,
            "composite_score": self.composite_score,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        """Deserialize from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            evaluation_id=data["evaluation_id"],
            resource_id=data["resource_id"],
            resource_type=data.get("resource_type", ""),
            resource_version=data.get("resource_version", 1),
            reward=data.get("reward", {}),
            composite_score=data.get("composite_score", 0.0),
            metadata=data.get("metadata", {}),
            created_at=created_at,
        )


@dataclass
class StoreMetrics:
    """Metrics about the optimization store.

    Attributes:
        span_count: Total number of stored spans.
        resource_count: Total number of registered resources.
        evaluation_count: Total number of evaluations.
        result_count: Total number of stored results.
        queue_length: Current evaluation queue length.
        connected: Whether the store is connected.
    """

    span_count: int = 0
    resource_count: int = 0
    evaluation_count: int = 0
    result_count: int = 0
    queue_length: int = 0
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "span_count": self.span_count,
            "resource_count": self.resource_count,
            "evaluation_count": self.evaluation_count,
            "result_count": self.result_count,
            "queue_length": self.queue_length,
            "connected": self.connected,
        }
