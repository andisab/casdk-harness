"""Unit tests for configuration management."""


from harness.config import HarnessConfig


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
