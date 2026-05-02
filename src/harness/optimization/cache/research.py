"""Research cache for CGF optimization pipeline.

Caches research artifacts like eval_criteria.yaml to avoid
repeating research phase for identical resource+goal combinations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.cache.base import BaseCache

logger = structlog.get_logger(__name__)


@dataclass
class ResearchCacheKey:
    """Key components for research cache lookup.

    Attributes:
        resource_id: Unique identifier for the resource being optimized.
        resource_type: Type of resource (agent, skill, command, etc.).
        goal: Optimization goal string.
        resource_content_hash: Hash of the resource content.
    """

    resource_id: str
    resource_type: str
    goal: str
    resource_content_hash: str

    def to_cache_key(self) -> str:
        """Generate cache key string."""
        return f"research_{self.resource_id}_{self.resource_type}"


@dataclass
class EvalCriteria:
    """Cached evaluation criteria from research phase.

    Attributes:
        competencies: List of competency areas to evaluate.
        criteria: Detailed evaluation criteria per competency.
        rubrics: Scoring rubrics for evaluation.
        research_summary: Summary of research findings.
        metadata: Additional metadata from research.
    """

    competencies: list[dict[str, Any]]
    criteria: dict[str, Any]
    rubrics: dict[str, Any]
    research_summary: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "competencies": self.competencies,
            "criteria": self.criteria,
            "rubrics": self.rubrics,
            "research_summary": self.research_summary,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCriteria:
        """Deserialize from dictionary."""
        return cls(
            competencies=data.get("competencies", []),
            criteria=data.get("criteria", {}),
            rubrics=data.get("rubrics", {}),
            research_summary=data.get("research_summary", ""),
            metadata=data.get("metadata"),
        )


class ResearchCache(BaseCache[EvalCriteria]):
    """Cache for research phase artifacts.

    Stores eval_criteria.yaml content keyed by resource+goal combination.
    Uses content hash to invalidate when resource changes.

    Example:
        cache = ResearchCache(cache_dir=Path("workspace/.cache"))

        # Check cache before research
        key = ResearchCacheKey(
            resource_id="python-expert",
            resource_type="agent",
            goal="improve async handling",
            resource_content_hash=compute_hash(resource_content),
        )

        cached = cache.get_criteria(key)
        if cached:
            # Use cached eval criteria
            pass
        else:
            # Run research and cache result
            criteria = run_research(resource, goal)
            cache.put_criteria(key, criteria)
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: float | None = 86400 * 7,  # 7 days default
    ) -> None:
        """Initialize research cache.

        Args:
            cache_dir: Directory for cache files.
            ttl_seconds: Time-to-live (default 7 days).
        """
        super().__init__(
            cache_dir=cache_dir / "research",
            ttl_seconds=ttl_seconds,
            max_entries=100,  # Keep up to 100 research results
        )

    def _serialize(self, value: EvalCriteria) -> Any:
        """Serialize EvalCriteria for storage."""
        return value.to_dict()

    def _deserialize(self, data: Any) -> EvalCriteria:
        """Deserialize EvalCriteria from storage."""
        return EvalCriteria.from_dict(data)

    def get_criteria(
        self,
        key: ResearchCacheKey,
    ) -> EvalCriteria | None:
        """Get cached eval criteria.

        Args:
            key: Research cache key.

        Returns:
            Cached EvalCriteria if valid, None otherwise.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.resource_type,
            key.goal,
            key.resource_content_hash,
        ]
        return self.get(cache_key, inputs=inputs)

    def put_criteria(
        self,
        key: ResearchCacheKey,
        criteria: EvalCriteria,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store eval criteria in cache.

        Args:
            key: Research cache key.
            criteria: EvalCriteria to cache.
            metadata: Additional metadata to store.
        """
        cache_key = key.to_cache_key()
        inputs = [
            key.resource_id,
            key.resource_type,
            key.goal,
            key.resource_content_hash,
        ]
        self.put(cache_key, criteria, inputs=inputs, metadata=metadata)

        goal_preview = (
            key.goal[:50] + "..." if len(key.goal) > 50 else key.goal
        )
        logger.info(
            "Cached research criteria",
            resource_id=key.resource_id,
            goal_preview=goal_preview,
        )

    def invalidate_resource(
        self, resource_id: str, resource_type: str
    ) -> bool:
        """Invalidate all cache entries for a resource.

        Args:
            resource_id: Resource identifier.
            resource_type: Type of resource.

        Returns:
            True if any entries were invalidated.
        """
        cache_key = f"research_{resource_id}_{resource_type}"
        return self.invalidate(cache_key)
