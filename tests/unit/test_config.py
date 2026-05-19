"""Unit tests for configuration management."""


import pytest

from harness.config import (
    MODEL_CONTEXT_WINDOWS,
    MODEL_SHORTHAND_MAP,
    HarnessConfig,
    RuntimeConfig,
    get_context_window,
    resolve_model_name,
)


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default configuration values.

    Hermetic — clears env vars that BaseSettings would otherwise pull in
    from the container's ``.env`` file (e.g. local ``CLAUDE_MODEL``
    overrides).
    """
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_PERMISSION_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_MAX_TURNS", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    # _env_file=None disables loading from .env on disk, so the test
    # checks the actual dataclass defaults rather than .env contents.
    config = HarnessConfig(anthropic_api_key="test-key", _env_file=None)

    # Assert
    assert config.claude_model == "claude-sonnet-4-6"
    assert config.interactive_permission_mode == "acceptEdits"
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
    # _env_file=None bypasses .env loading so we test the code defaults, not whatever
    # the developer's local .env happens to set. Without this, a non-default value
    # like AUTONOMOUS_DELAY_SECONDS=3 in .env masks the canonical code default.
    config = HarnessConfig(anthropic_api_key="test-key", _env_file=None)

    # Assert - Inactivity Timeout (15 minutes)
    assert config.claude_api_timeout == 900

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
    # Verify mapping contains all expected Claude models — both the
    # current unversioned aliases and the historical pinned builds.
    expected_models = [
        # Current unversioned aliases (4.7 / 4.6 / 4.5 era)
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        # Pinned historical builds (kept for backcompat)
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


# Model Shorthand Tests


def test_model_shorthand_map() -> None:
    """Test MODEL_SHORTHAND_MAP contains expected models."""
    assert "sonnet" in MODEL_SHORTHAND_MAP
    assert "opus" in MODEL_SHORTHAND_MAP
    assert "haiku" in MODEL_SHORTHAND_MAP
    assert MODEL_SHORTHAND_MAP["sonnet"].startswith("claude-")


def test_resolve_model_name_shorthand() -> None:
    """Test resolve_model_name with shorthand names.

    Bump these when ``MODEL_SHORTHAND_MAP`` moves forward by a minor
    Anthropic version.  This test guards I14 — a stale local alias map
    inside ``llm_judge.py`` that drifts from the canonical map here.
    """
    assert resolve_model_name("sonnet") == "claude-sonnet-4-6"
    assert resolve_model_name("opus") == "claude-opus-4-7"
    assert resolve_model_name("haiku") == "claude-haiku-4-5"


def test_resolve_model_name_full() -> None:
    """Test resolve_model_name with full model names."""
    assert resolve_model_name("claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert resolve_model_name("claude-custom-model") == "claude-custom-model"


def test_resolve_model_name_unknown() -> None:
    """Test resolve_model_name with unknown names."""
    assert resolve_model_name("unknown") is None
    assert resolve_model_name("gpt-4") is None


# RuntimeConfig Tests


def test_runtime_config_from_harness_defaults() -> None:
    """Test RuntimeConfig uses HarnessConfig defaults."""
    config = HarnessConfig(anthropic_api_key="test-key")
    runtime = RuntimeConfig.from_harness_config(config)

    assert runtime.model == config.claude_model
    assert runtime.permission_mode == config.interactive_permission_mode
    assert runtime.max_turns == config.claude_max_turns
    assert runtime.quiet is False


def test_runtime_config_interactive_mode() -> None:
    """Test RuntimeConfig uses interactive permission mode."""
    config = HarnessConfig(
        anthropic_api_key="test-key",
        interactive_permission_mode="acceptEdits",
        autonomous_permission_mode="bypassPermissions",
    )
    runtime = RuntimeConfig.from_harness_config(config, mode="interactive")

    assert runtime.permission_mode == "acceptEdits"


def test_runtime_config_autonomous_mode() -> None:
    """Test RuntimeConfig uses autonomous permission mode."""
    config = HarnessConfig(
        anthropic_api_key="test-key",
        interactive_permission_mode="acceptEdits",
        autonomous_permission_mode="bypassPermissions",
    )
    runtime = RuntimeConfig.from_harness_config(config, mode="autonomous")

    assert runtime.permission_mode == "bypassPermissions"


def test_runtime_config_model_override() -> None:
    """Test RuntimeConfig respects model override."""
    config = HarnessConfig(anthropic_api_key="test-key")
    runtime = RuntimeConfig.from_harness_config(
        config,
        model_override="claude-opus-4-5-20251101",
    )

    assert runtime.model == "claude-opus-4-5-20251101"


def test_runtime_config_permission_override() -> None:
    """Test RuntimeConfig respects permission mode override."""
    config = HarnessConfig(anthropic_api_key="test-key")
    runtime = RuntimeConfig.from_harness_config(
        config,
        mode="interactive",
        permission_mode_override="plan",
    )

    assert runtime.permission_mode == "plan"


def test_runtime_config_quiet_mode() -> None:
    """Test RuntimeConfig quiet mode sets log level to CRITICAL."""
    config = HarnessConfig(anthropic_api_key="test-key", log_level="INFO")
    runtime = RuntimeConfig.from_harness_config(config, quiet=True)

    assert runtime.quiet is True
    assert runtime.log_level == "CRITICAL"


def test_runtime_config_immutable() -> None:
    """Test RuntimeConfig is immutable (frozen dataclass)."""
    config = HarnessConfig(anthropic_api_key="test-key")
    runtime = RuntimeConfig.from_harness_config(config)

    with pytest.raises(Exception):  # FrozenInstanceError
        runtime.model = "different-model"  # type: ignore[misc]
