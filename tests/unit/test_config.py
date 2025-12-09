"""Unit tests for configuration management."""


from harness.config import (
    HarnessConfig,
    MODEL_CONTEXT_WINDOWS,
    get_context_window,
)


def test_config_defaults() -> None:
    """Test default configuration values."""
    # Act
    config = HarnessConfig(anthropic_api_key="test-key")

    # Assert
    assert config.claude_model == "claude-sonnet-4-5-20250929"
    assert config.claude_permission_mode == "acceptEdits"
    assert config.claude_max_turns == 1000
    assert config.log_level == "INFO"


def test_redis_url() -> None:
    """Test Redis URL generation."""
    # Arrange
    config = HarnessConfig(
        anthropic_api_key="test-key",
        redis_host="localhost",
        redis_port=6379,
        redis_password="testpass",
    )

    # Act
    url = config.redis_url

    # Assert
    assert url == "redis://:testpass@localhost:6379/0"


def test_redis_url_no_password() -> None:
    """Test Redis URL without password."""
    # Arrange
    config = HarnessConfig(
        anthropic_api_key="test-key",
        redis_host="localhost",
        redis_port=6379,
        redis_password="",  # Explicitly set empty to override env
    )

    # Act
    url = config.redis_url

    # Assert
    assert url == "redis://localhost:6379/0"


def test_new_config_fields_defaults() -> None:
    """Test default values for new hardening config fields."""
    # Act
    config = HarnessConfig(anthropic_api_key="test-key")

    # Assert - API Timeout
    assert config.claude_api_timeout == 60

    # Assert - Checkpoint Configuration
    assert config.checkpoint_keep_count == 5

    # Assert - Redis Circuit Breaker Configuration
    assert config.redis_timeout == 5
    assert config.redis_circuit_breaker_threshold == 5
    assert config.redis_circuit_breaker_recovery == 30

    # Assert - Retry Configuration
    assert config.retry_attempts == 3
    assert config.retry_min_wait == 4
    assert config.retry_max_wait == 10

    # Assert - Health Check Configuration
    assert config.health_port == 8080

    # Assert - Shutdown Configuration
    assert config.shutdown_timeout == 5

    # Assert - Autonomous mode delay
    assert config.autonomous_delay_seconds == 5


def test_config_fields_customizable() -> None:
    """Test that new config fields can be customized."""
    # Arrange & Act
    config = HarnessConfig(
        anthropic_api_key="test-key",
        claude_api_timeout=120,
        checkpoint_keep_count=10,
        redis_timeout=10,
        redis_circuit_breaker_threshold=3,
        redis_circuit_breaker_recovery=60,
        retry_attempts=5,
        retry_min_wait=2,
        retry_max_wait=20,
        health_port=9000,
        shutdown_timeout=10,
        autonomous_delay_seconds=10,
    )

    # Assert
    assert config.claude_api_timeout == 120
    assert config.checkpoint_keep_count == 10
    assert config.redis_timeout == 10
    assert config.redis_circuit_breaker_threshold == 3
    assert config.redis_circuit_breaker_recovery == 60
    assert config.retry_attempts == 5
    assert config.retry_min_wait == 2
    assert config.retry_max_wait == 20
    assert config.health_port == 9000
    assert config.shutdown_timeout == 10
    assert config.autonomous_delay_seconds == 10


# Context Budget Configuration Tests


def test_get_context_window_known_model() -> None:
    """Test context window returned for known models."""
    # Assert known models return their specific context windows
    assert get_context_window("claude-sonnet-4-5-20250929") == 200_000
    assert get_context_window("claude-opus-4-5-20251101") == 200_000
    assert get_context_window("claude-3-5-sonnet-20241022") == 200_000
    assert get_context_window("claude-3-5-haiku-20241022") == 200_000


def test_get_context_window_extended_model() -> None:
    """Test context window for extended context model."""
    assert get_context_window("claude-3-5-sonnet-20241022-extended") == 1_000_000


def test_get_context_window_unknown_model() -> None:
    """Test default 200K returned for unknown models."""
    # Unknown models should return the default 200K
    assert get_context_window("unknown-model-xyz") == 200_000
    assert get_context_window("") == 200_000
    assert get_context_window("gpt-4") == 200_000


def test_model_context_windows_mapping() -> None:
    """Test MODEL_CONTEXT_WINDOWS mapping contains expected models."""
    # Verify mapping contains all expected Claude models
    expected_models = [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022-extended",
    ]
    for model in expected_models:
        assert model in MODEL_CONTEXT_WINDOWS


def test_context_budget_threshold_defaults() -> None:
    """Test default context budget threshold percentages."""
    config = HarnessConfig(anthropic_api_key="test-key")

    assert config.context_budget_warning_pct == 0.70
    assert config.context_budget_urgent_pct == 0.75
    assert config.context_budget_critical_pct == 0.85
    assert config.context_budget_override is None


def test_context_budget_threshold_customizable() -> None:
    """Test that context budget thresholds can be customized."""
    config = HarnessConfig(
        anthropic_api_key="test-key",
        context_budget_warning_pct=0.60,
        context_budget_urgent_pct=0.70,
        context_budget_critical_pct=0.80,
        context_budget_override=100_000,
    )

    assert config.context_budget_warning_pct == 0.60
    assert config.context_budget_urgent_pct == 0.70
    assert config.context_budget_critical_pct == 0.80
    assert config.context_budget_override == 100_000
