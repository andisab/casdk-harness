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
