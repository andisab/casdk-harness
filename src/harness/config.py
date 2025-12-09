"""Configuration management for Claude Agent SDK Harness."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Model context window sizes (tokens)
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # Claude 4 models
    "claude-sonnet-4-5-20250929": 200_000,
    "claude-opus-4-5-20251101": 200_000,
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    # Extended context models
    "claude-3-5-sonnet-20241022-extended": 1_000_000,
}


def get_context_window(model: str) -> int:
    """Get context window size for a model.

    Args:
        model: The model identifier string.

    Returns:
        Context window size in tokens. Defaults to 200,000 if model unknown.
    """
    return MODEL_CONTEXT_WINDOWS.get(model, 200_000)


class HarnessConfig(BaseSettings):
    """Main configuration for the harness."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    claude_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Claude model to use",
    )

    # Agent Behavior
    # Valid modes: acceptEdits, bypassPermissions, default, dontAsk, plan
    claude_permission_mode: Literal[
        "acceptEdits", "bypassPermissions", "default", "dontAsk", "plan"
    ] = Field(
        default="acceptEdits",
        description="Permission mode for agent actions",
    )
    claude_max_turns: int = Field(
        default=1000,
        description="Maximum conversation turns",
    )
    claude_session_timeout: int = Field(
        default=72000,
        description="Session timeout in seconds (20 hours)",
    )
    claude_checkpoint_interval: int = Field(
        default=3600,
        description="Checkpoint interval in seconds (1 hour)",
    )

    # Paths
    workspace_dir: Path = Field(
        default=Path("/workspace"),
        description="Agent workspace directory",
    )
    memory_dir: Path = Field(
        default=Path("/memory"),
        description="Memory and checkpoint directory",
    )
    logs_dir: Path = Field(
        default=Path("/logs"),
        description="Logs directory",
    )
    config_dir: Path = Field(
        default=Path("/app/config"),
        description="Configuration directory",
    )

    # Redis Configuration
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="")

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_format: Literal["json", "text"] = Field(default="json")

    # Feature Flags
    debug: bool = Field(default=False)
    hot_reload: bool = Field(default=False)
    enable_profiling: bool = Field(default=False)
    enable_auto_scaling: bool = Field(default=False)
    enable_cost_optimization: bool = Field(default=True)

    # Autonomous Mode Configuration
    autonomous_delay_seconds: int = Field(
        default=5,
        description="Delay between autonomous sessions in seconds",
    )
    autonomous_max_sessions: int = Field(
        default=100,
        description="Maximum number of autonomous sessions",
    )
    autonomous_task_timeout: int = Field(
        default=1800,
        description="Timeout per task in seconds (30 min)",
    )
    bash_allow_all: bool = Field(
        default=False,
        description="Bypass bash command security checks (dangerous)",
    )

    # Cloud Provider Configuration
    claude_code_use_bedrock: bool = Field(default=False)
    aws_region: str = Field(default="us-east-1")
    claude_code_use_vertex: bool = Field(default=False)
    gcp_project_id: str = Field(default="")
    gcp_region: str = Field(default="us-central1")

    # API Timeout Configuration
    claude_api_timeout: int = Field(
        default=60,
        description="API request timeout in seconds",
    )

    # Checkpoint Configuration
    checkpoint_keep_count: int = Field(
        default=5,
        description="Number of checkpoint files to keep",
    )

    # Redis Circuit Breaker Configuration
    redis_timeout: int = Field(
        default=5,
        description="Redis socket timeout in seconds",
    )
    redis_circuit_breaker_threshold: int = Field(
        default=5,
        description="Consecutive failures before circuit opens",
    )
    redis_circuit_breaker_recovery: int = Field(
        default=30,
        description="Seconds to wait before testing recovery",
    )

    # Retry Configuration
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for operations",
    )
    retry_min_wait: int = Field(
        default=4,
        description="Minimum wait time between retries in seconds",
    )
    retry_max_wait: int = Field(
        default=10,
        description="Maximum wait time between retries in seconds",
    )

    # Health Check Configuration
    health_port: int = Field(
        default=8080,
        description="Port for health check HTTP server",
    )

    # Shutdown Configuration
    shutdown_timeout: int = Field(
        default=5,
        description="Timeout for graceful shutdown in seconds",
    )

    # Context Budget Configuration
    context_budget_warning_pct: float = Field(
        default=0.70,
        description="Warning threshold as percentage of context window (0.70 = 70%)",
    )
    context_budget_urgent_pct: float = Field(
        default=0.75,
        description="Urgent threshold as percentage of context window (0.75 = 75%)",
    )
    context_budget_critical_pct: float = Field(
        default=0.85,
        description="Critical threshold as percentage of context window (0.85 = 85%)",
    )
    context_budget_override: int | None = Field(
        default=None,
        description="Override context window size (useful for testing)",
    )

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    @property
    def checkpoint_dir(self) -> Path:
        """Get checkpoint directory path."""
        return self.memory_dir / "checkpoints"

    @property
    def context_dir(self) -> Path:
        """Get context directory path."""
        return self.memory_dir / "context"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for directory in [
            self.workspace_dir,
            self.memory_dir,
            self.logs_dir,
            self.checkpoint_dir,
            self.context_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: HarnessConfig | None = None


def get_config() -> HarnessConfig:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = HarnessConfig()
        _config.ensure_directories()
    return _config


def reload_config() -> HarnessConfig:
    """Force reload configuration from environment."""
    global _config
    _config = HarnessConfig()
    _config.ensure_directories()
    return _config
