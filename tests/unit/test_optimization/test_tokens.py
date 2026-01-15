"""Unit tests for token usage tracking and budget management."""

from __future__ import annotations

import pytest

from harness.optimization.profiling.tokens import (
    BudgetExceededError,
    PromptCache,
    TokenBudget,
    TokenTracker,
    TokenUsage,
    estimate_tokens,
    estimate_tokens_from_messages,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_creation_with_tokens(self) -> None:
        """TokenUsage calculates total from input/output."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            operation="test_op",
        )

        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.total_tokens == 1500

    def test_explicit_total(self) -> None:
        """TokenUsage uses explicit total if provided."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=200,  # Different from sum
        )

        assert usage.total_tokens == 200

    def test_to_dict(self) -> None:
        """TokenUsage.to_dict() serializes correctly."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            operation="api_call",
            model="claude-3-sonnet",
            cached=True,
        )

        result = usage.to_dict()

        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["operation"] == "api_call"
        assert result["model"] == "claude-3-sonnet"
        assert result["cached"] is True


class TestTokenBudget:
    """Tests for TokenBudget."""

    def test_default_budget(self) -> None:
        """TokenBudget has sensible defaults."""
        budget = TokenBudget()

        assert budget.max_total_tokens == 1_000_000
        assert budget.warn_threshold == 0.8
        assert budget.hard_limit is False

    def test_custom_budget(self) -> None:
        """TokenBudget accepts custom values."""
        budget = TokenBudget(
            max_total_tokens=50000,
            max_input_tokens=30000,
            warn_threshold=0.9,
            hard_limit=True,
        )

        assert budget.max_total_tokens == 50000
        assert budget.max_input_tokens == 30000
        assert budget.hard_limit is True

    def test_to_dict(self) -> None:
        """TokenBudget.to_dict() serializes correctly."""
        budget = TokenBudget(max_total_tokens=100000)
        result = budget.to_dict()

        assert result["max_total_tokens"] == 100000
        assert "warn_threshold" in result

    def test_from_dict(self) -> None:
        """TokenBudget.from_dict() deserializes correctly."""
        data = {"max_total_tokens": 50000, "hard_limit": True}
        budget = TokenBudget.from_dict(data)

        assert budget.max_total_tokens == 50000
        assert budget.hard_limit is True


class TestTokenTracker:
    """Tests for TokenTracker."""

    def test_record_usage(self) -> None:
        """TokenTracker records token usage."""
        tracker = TokenTracker()

        usage = TokenUsage(input_tokens=100, output_tokens=50)
        tracker.record(usage)

        assert len(tracker.usages) == 1
        assert tracker.get_total_tokens() == 150

    def test_multiple_usages(self) -> None:
        """TokenTracker accumulates multiple usages."""
        tracker = TokenTracker()

        tracker.record(TokenUsage(input_tokens=100, output_tokens=50))
        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))
        tracker.record(TokenUsage(input_tokens=150, output_tokens=75))

        assert tracker.get_total_tokens() == 675
        assert tracker.get_total_input_tokens() == 450
        assert tracker.get_total_output_tokens() == 225

    def test_tracks_by_operation(self) -> None:
        """TokenTracker groups usage by operation."""
        tracker = TokenTracker()

        tracker.record(TokenUsage(
            input_tokens=100, output_tokens=50, operation="research"
        ))
        tracker.record(TokenUsage(
            input_tokens=200, output_tokens=100, operation="optimize"
        ))
        tracker.record(TokenUsage(
            input_tokens=150, output_tokens=75, operation="research"
        ))

        by_op = tracker.get_usage_by_operation()

        assert "research" in by_op
        assert by_op["research"]["count"] == 2
        assert by_op["research"]["total_tokens"] == 375

        assert "optimize" in by_op
        assert by_op["optimize"]["count"] == 1
        assert by_op["optimize"]["total_tokens"] == 300

    def test_tracks_by_model(self) -> None:
        """TokenTracker groups usage by model."""
        tracker = TokenTracker()

        tracker.record(
            TokenUsage(input_tokens=100, output_tokens=50, model="sonnet")
        )
        tracker.record(
            TokenUsage(input_tokens=200, output_tokens=100, model="haiku")
        )

        by_model = tracker.get_usage_by_model()

        assert "sonnet" in by_model
        assert "haiku" in by_model

    def test_remaining_budget(self) -> None:
        """TokenTracker calculates remaining budget."""
        budget = TokenBudget(max_total_tokens=1000)
        tracker = TokenTracker(budget=budget)

        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))

        assert tracker.get_remaining_budget() == 700

    def test_over_budget_detection(self) -> None:
        """TokenTracker detects when over budget."""
        budget = TokenBudget(max_total_tokens=500)
        tracker = TokenTracker(budget=budget)

        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))
        assert not tracker.is_over_budget()

        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))
        assert tracker.is_over_budget()

    def test_near_budget_warning(self) -> None:
        """TokenTracker detects when near budget threshold."""
        budget = TokenBudget(max_total_tokens=1000, warn_threshold=0.8)
        tracker = TokenTracker(budget=budget)

        tracker.record(TokenUsage(input_tokens=300, output_tokens=200))
        assert not tracker.is_near_budget()  # 50%

        tracker.record(TokenUsage(input_tokens=300, output_tokens=100))
        assert tracker.is_near_budget()  # 90%

    def test_hard_limit_enforcement(self) -> None:
        """TokenTracker raises error with hard limits."""
        budget = TokenBudget(
            max_total_tokens=500,
            hard_limit=True,
        )
        tracker = TokenTracker(budget=budget)

        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))

        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.record(TokenUsage(input_tokens=200, output_tokens=100))

        assert exc_info.value.current_usage == 600
        assert exc_info.value.budget_limit == 500

    def test_hard_limit_input_only(self) -> None:
        """TokenTracker enforces input token limits."""
        budget = TokenBudget(
            max_total_tokens=10000,
            max_input_tokens=300,
            hard_limit=True,
        )
        tracker = TokenTracker(budget=budget)

        tracker.record(TokenUsage(input_tokens=200, output_tokens=100))

        with pytest.raises(BudgetExceededError):
            tracker.record(TokenUsage(input_tokens=200, output_tokens=100))

    def test_cached_tokens_tracking(self) -> None:
        """TokenTracker tracks cached tokens separately."""
        tracker = TokenTracker()

        tracker.record(TokenUsage(input_tokens=100, output_tokens=50))
        tracker.record(
            TokenUsage(input_tokens=100, output_tokens=50, cached=True)
        )

        assert tracker.get_cached_tokens() == 150
        assert tracker.get_total_tokens() == 300

    def test_get_summary(self) -> None:
        """TokenTracker.get_summary() returns comprehensive data."""
        budget = TokenBudget(max_total_tokens=1000)
        tracker = TokenTracker(budget=budget)

        tracker.record(
            TokenUsage(
                input_tokens=100,
                output_tokens=50,
                operation="test",
                model="sonnet",
            )
        )

        summary = tracker.get_summary()

        assert summary["total_tokens"] == 150
        assert summary["input_tokens"] == 100
        assert summary["output_tokens"] == 50
        assert summary["operation_count"] == 1
        assert summary["budget"]["max_total"] == 1000
        assert summary["budget"]["remaining"] == 850
        assert "by_operation" in summary
        assert "by_model" in summary

    def test_to_dict(self) -> None:
        """TokenTracker.to_dict() serializes completely."""
        tracker = TokenTracker()
        tracker.record(TokenUsage(input_tokens=100, output_tokens=50))

        result = tracker.to_dict()

        assert "budget" in result
        assert "usages" in result
        assert "summary" in result
        assert len(result["usages"]) == 1


class TestPromptCache:
    """Tests for PromptCache."""

    def test_cache_miss(self) -> None:
        """PromptCache returns miss for new content."""
        cache = PromptCache()

        assert not cache.has("test content")

    def test_cache_hit(self) -> None:
        """PromptCache returns hit for cached content."""
        cache = PromptCache()

        cache.put("test content", token_count=100)
        assert cache.has("test content")

    def test_get_cached_data(self) -> None:
        """PromptCache returns cached data."""
        cache = PromptCache()

        cache.put("test content", token_count=100, metadata={"key": "value"})
        result = cache.get("test content")

        assert result is not None
        assert result["token_count"] == 100
        assert result["metadata"]["key"] == "value"

    def test_eviction_on_capacity(self) -> None:
        """PromptCache evicts old entries at capacity."""
        cache = PromptCache(max_entries=5)

        for i in range(10):
            cache.put(f"content_{i}", token_count=100)

        # Should have evicted some entries
        assert len(cache._cache) <= 5

    def test_cache_stats(self) -> None:
        """PromptCache tracks statistics."""
        cache = PromptCache()

        cache.put("content1", token_count=100)
        cache.has("content1")  # Hit
        cache.has("content2")  # Miss
        cache.has("content1")  # Hit

        stats = cache.get_stats()

        assert stats["entries"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] > 0

    def test_clear_cache(self) -> None:
        """PromptCache.clear() removes all entries."""
        cache = PromptCache()

        cache.put("content1", token_count=100)
        cache.put("content2", token_count=200)

        cache.clear()

        assert not cache.has("content1")
        assert not cache.has("content2")


class TestEstimateTokens:
    """Tests for token estimation functions."""

    def test_empty_text(self) -> None:
        """estimate_tokens handles empty text."""
        assert estimate_tokens("") == 0

    def test_short_text(self) -> None:
        """estimate_tokens works for short text."""
        result = estimate_tokens("Hello world")

        # Should be reasonable estimate (2-3 tokens)
        assert 1 <= result <= 5

    def test_longer_text(self) -> None:
        """estimate_tokens scales with text length."""
        short = estimate_tokens("Hello")
        long_text = estimate_tokens("Hello " * 100)

        assert long_text > short * 50  # Should scale roughly linearly

    def test_estimate_from_messages(self) -> None:
        """estimate_tokens_from_messages handles chat format."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = estimate_tokens_from_messages(messages)

        # Should account for all messages plus overhead
        assert result > 0
        assert result > estimate_tokens("Hello!")  # Includes overhead

    def test_estimate_messages_empty_list(self) -> None:
        """estimate_tokens_from_messages handles empty list."""
        result = estimate_tokens_from_messages([])

        assert result == 0


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_error_attributes(self) -> None:
        """BudgetExceededError has correct attributes."""
        error = BudgetExceededError(
            "Budget exceeded",
            current_usage=1500,
            budget_limit=1000,
        )

        assert error.current_usage == 1500
        assert error.budget_limit == 1000
        assert "Budget exceeded" in str(error)

    def test_error_message(self) -> None:
        """BudgetExceededError has descriptive message."""
        error = BudgetExceededError(
            "Token limit reached: 1500 > 1000",
            current_usage=1500,
            budget_limit=1000,
        )

        assert "1500" in str(error)
        assert "1000" in str(error)
