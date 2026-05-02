"""Token usage tracking and budget management for CGF optimization.

Provides utilities for:
- Tracking token usage across agent invocations
- Enforcing token budgets
- Estimating token counts from text
- Generating token usage reports
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Approximate tokens per character ratios for estimation
# Based on OpenAI tokenizer averages for English text
TOKENS_PER_CHAR_RATIO = 0.25  # ~4 chars per token average
TOKENS_PER_WORD_RATIO = 1.3  # ~1.3 tokens per word average


@dataclass
class TokenUsage:
    """Token usage for a single operation.

    Attributes:
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.
        total_tokens: Total tokens (input + output).
        operation: Description of the operation.
        timestamp: When the usage was recorded.
        model: Model used for the operation.
        cached: Whether this was a cache hit.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    operation: str = ""
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    cached: bool = False

    def __post_init__(self) -> None:
        """Calculate total if not provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "model": self.model,
            "cached": self.cached,
        }


@dataclass
class TokenBudget:
    """Token budget configuration.

    Attributes:
        max_total_tokens: Maximum total tokens allowed.
        max_input_tokens: Maximum input tokens allowed.
        max_output_tokens: Maximum output tokens allowed.
        warn_threshold: Percentage at which to warn (0.0-1.0).
        hard_limit: Whether to enforce hard limits.
    """

    max_total_tokens: int = 1_000_000  # 1M default
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    warn_threshold: float = 0.8
    hard_limit: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_total_tokens": self.max_total_tokens,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "warn_threshold": self.warn_threshold,
            "hard_limit": self.hard_limit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenBudget:
        """Create from dictionary."""
        return cls(
            max_total_tokens=data.get("max_total_tokens", 1_000_000),
            max_input_tokens=data.get("max_input_tokens"),
            max_output_tokens=data.get("max_output_tokens"),
            warn_threshold=data.get("warn_threshold", 0.8),
            hard_limit=data.get("hard_limit", False),
        )


class BudgetExceededError(Exception):
    """Raised when token budget is exceeded with hard limits enabled."""

    def __init__(
        self,
        message: str,
        current_usage: int,
        budget_limit: int,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message.
            current_usage: Current token usage.
            budget_limit: Budget limit that was exceeded.
        """
        super().__init__(message)
        self.current_usage = current_usage
        self.budget_limit = budget_limit


@dataclass
class TokenTracker:
    """Tracks token usage across operations with budget enforcement.

    Example:
        budget = TokenBudget(max_total_tokens=100000)
        tracker = TokenTracker(budget=budget)

        # Record usage
        tracker.record(TokenUsage(input_tokens=1000, output_tokens=500))

        # Check budget
        if tracker.is_over_budget():
            print("Budget exceeded!")

        # Get summary
        summary = tracker.get_summary()
        print(f"Total tokens: {summary['total_tokens']:,}")
    """

    budget: TokenBudget = field(default_factory=TokenBudget)
    usages: list[TokenUsage] = field(default_factory=list)
    _by_operation: dict[str, list[TokenUsage]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _by_model: dict[str, list[TokenUsage]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def record(self, usage: TokenUsage) -> None:
        """Record token usage.

        Args:
            usage: Token usage to record.

        Raises:
            BudgetExceededError: If hard limits enabled and budget exceeded.
        """
        self.usages.append(usage)
        self._by_operation[usage.operation].append(usage)
        self._by_model[usage.model].append(usage)

        # Check budget limits
        self._check_budget()

    def _check_budget(self) -> None:
        """Check if budget limits are exceeded.

        Raises:
            BudgetExceededError: If hard limits enabled and exceeded.
        """
        total = self.get_total_tokens()
        total_input = self.get_total_input_tokens()
        total_output = self.get_total_output_tokens()

        # Check warnings
        if total >= self.budget.max_total_tokens * self.budget.warn_threshold:
            remaining = self.budget.max_total_tokens - total
            logger.warning(
                "Token budget warning",
                total_used=total,
                budget=self.budget.max_total_tokens,
                remaining=remaining,
                percent_used=total / self.budget.max_total_tokens * 100,
            )

        # Check hard limits
        if self.budget.hard_limit:
            if total > self.budget.max_total_tokens:
                raise BudgetExceededError(
                    f"Total token budget exceeded: "
                    f"{total:,} > {self.budget.max_total_tokens:,}",
                    current_usage=total,
                    budget_limit=self.budget.max_total_tokens,
                )

            if (
                self.budget.max_input_tokens
                and total_input > self.budget.max_input_tokens
            ):
                raise BudgetExceededError(
                    f"Input token budget exceeded: "
                    f"{total_input:,} > {self.budget.max_input_tokens:,}",
                    current_usage=total_input,
                    budget_limit=self.budget.max_input_tokens,
                )

            if (
                self.budget.max_output_tokens
                and total_output > self.budget.max_output_tokens
            ):
                raise BudgetExceededError(
                    f"Output token budget exceeded: "
                    f"{total_output:,} > {self.budget.max_output_tokens:,}",
                    current_usage=total_output,
                    budget_limit=self.budget.max_output_tokens,
                )

    def get_total_tokens(self) -> int:
        """Get total tokens used."""
        return sum(u.total_tokens for u in self.usages)

    def get_total_input_tokens(self) -> int:
        """Get total input tokens used."""
        return sum(u.input_tokens for u in self.usages)

    def get_total_output_tokens(self) -> int:
        """Get total output tokens used."""
        return sum(u.output_tokens for u in self.usages)

    def get_cached_tokens(self) -> int:
        """Get total cached tokens (cache hits)."""
        return sum(u.total_tokens for u in self.usages if u.cached)

    def get_remaining_budget(self) -> int:
        """Get remaining token budget."""
        return max(0, self.budget.max_total_tokens - self.get_total_tokens())

    def is_over_budget(self) -> bool:
        """Check if over total token budget."""
        return self.get_total_tokens() > self.budget.max_total_tokens

    def is_near_budget(self) -> bool:
        """Check if near budget warning threshold."""
        total = self.get_total_tokens()
        threshold = self.budget.max_total_tokens * self.budget.warn_threshold
        return total >= threshold

    def get_usage_by_operation(self) -> dict[str, dict[str, int]]:
        """Get token usage breakdown by operation.

        Returns:
            Dictionary mapping operation to usage stats.
        """
        result = {}
        for op, usages in self._by_operation.items():
            result[op] = {
                "count": len(usages),
                "input_tokens": sum(u.input_tokens for u in usages),
                "output_tokens": sum(u.output_tokens for u in usages),
                "total_tokens": sum(u.total_tokens for u in usages),
                "cached_count": sum(1 for u in usages if u.cached),
            }
        return result

    def get_usage_by_model(self) -> dict[str, dict[str, int]]:
        """Get token usage breakdown by model.

        Returns:
            Dictionary mapping model to usage stats.
        """
        result = {}
        for model, usages in self._by_model.items():
            result[model] = {
                "count": len(usages),
                "input_tokens": sum(u.input_tokens for u in usages),
                "output_tokens": sum(u.output_tokens for u in usages),
                "total_tokens": sum(u.total_tokens for u in usages),
            }
        return result

    def get_summary(self) -> dict[str, Any]:
        """Get comprehensive usage summary.

        Returns:
            Dictionary with usage statistics and budget status.
        """
        total = self.get_total_tokens()
        cached = self.get_cached_tokens()
        cache_savings = cached if self.usages else 0

        return {
            "total_tokens": total,
            "input_tokens": self.get_total_input_tokens(),
            "output_tokens": self.get_total_output_tokens(),
            "cached_tokens": cached,
            "cache_savings_percent": (
                (cache_savings / total * 100) if total > 0 else 0
            ),
            "operation_count": len(self.usages),
            "budget": {
                "max_total": self.budget.max_total_tokens,
                "used": total,
                "remaining": self.get_remaining_budget(),
                "percent_used": (
                    total / self.budget.max_total_tokens * 100
                    if self.budget.max_total_tokens > 0 else 0
                ),
                "over_budget": self.is_over_budget(),
                "near_budget": self.is_near_budget(),
            },
            "by_operation": self.get_usage_by_operation(),
            "by_model": self.get_usage_by_model(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert tracker to dictionary for serialization."""
        return {
            "budget": self.budget.to_dict(),
            "usages": [u.to_dict() for u in self.usages],
            "summary": self.get_summary(),
        }


class PromptCache:
    """Simple cache for prompt/context to avoid re-tokenization.

    Example:
        cache = PromptCache(max_entries=100)

        # Check and use cached context
        if cache.has(system_prompt):
            print("Using cached prompt")
        else:
            cache.put(system_prompt, token_count=500)
            print(f"Cached prompt with {cache.get_stats()['entries']} entries")
    """

    def __init__(self, max_entries: int = 1000) -> None:
        """Initialize the cache.

        Args:
            max_entries: Maximum number of entries to cache.
        """
        self.max_entries = max_entries
        self._cache: dict[str, dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0

    def _hash_content(self, content: str) -> str:
        """Create hash of content for cache key."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def has(self, content: str) -> bool:
        """Check if content is in cache.

        Args:
            content: Content to check.

        Returns:
            True if cached.
        """
        key = self._hash_content(content)
        if key in self._cache:
            self._hits += 1
            self._cache[key]["last_access"] = time.time()
            return True
        self._misses += 1
        return False

    def get(self, content: str) -> dict[str, Any] | None:
        """Get cached entry for content.

        Args:
            content: Content to lookup.

        Returns:
            Cached data if found, None otherwise.
        """
        key = self._hash_content(content)
        if key in self._cache:
            self._hits += 1
            self._cache[key]["last_access"] = time.time()
            return self._cache[key]
        self._misses += 1
        return None

    def put(
        self,
        content: str,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add content to cache.

        Args:
            content: Content to cache.
            token_count: Optional pre-computed token count.
            metadata: Optional additional metadata.
        """
        # Evict oldest entries if at capacity
        if len(self._cache) >= self.max_entries:
            self._evict_oldest()

        key = self._hash_content(content)
        self._cache[key] = {
            "token_count": token_count or estimate_tokens(content),
            "created": time.time(),
            "last_access": time.time(),
            "metadata": metadata or {},
        }

    def _evict_oldest(self) -> None:
        """Evict oldest entries to make room."""
        if not self._cache:
            return

        # Remove oldest 10% of entries
        to_remove = max(1, len(self._cache) // 10)
        entries = sorted(
            self._cache.items(),
            key=lambda x: x[1]["last_access"],
        )

        for key, _ in entries[:to_remove]:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        total_requests = self._hits + self._misses
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (
                self._hits / total_requests * 100
                if total_requests > 0 else 0
            ),
            "total_cached_tokens": sum(
                e["token_count"] for e in self._cache.values()
            ),
        }


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Uses a simple heuristic based on character/word counts.
    For accurate counts, use a tokenizer.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0

    # Use character-based estimate
    char_estimate = int(len(text) * TOKENS_PER_CHAR_RATIO)

    # Use word-based estimate
    words = text.split()
    word_estimate = int(len(words) * TOKENS_PER_WORD_RATIO)

    # Return average of both methods
    return (char_estimate + word_estimate) // 2


def estimate_tokens_from_messages(
    messages: list[dict[str, str]],
) -> int:
    """Estimate token count from a list of chat messages.

    Args:
        messages: List of message dicts with 'role' and 'content'.

    Returns:
        Estimated total token count.
    """
    total = 0
    for msg in messages:
        # Add tokens for role/structure overhead (~4 tokens per message)
        total += 4
        content = msg.get("content", "")
        total += estimate_tokens(content)
    return total
