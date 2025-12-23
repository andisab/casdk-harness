"""Configuration management for Claude Agent SDK Harness."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    pass  # For forward references

# Model shorthand mapping (centralized from interactive.py/autonomous.py)
MODEL_SHORTHAND_MAP: dict[str, str] = {
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
    "haiku": "claude-3-5-haiku-20241022",
}


def resolve_model_name(model_shorthand: str) -> str | None:
    """Resolve model shorthand to full model name.

    Args:
        model_shorthand: Short name (sonnet, opus, haiku) or full model name

    Returns:
        Full model name, or None if unrecognized shorthand
    """
    if model_shorthand in MODEL_SHORTHAND_MAP:
        return MODEL_SHORTHAND_MAP[model_shorthand]
    if model_shorthand.startswith("claude-"):
        return model_shorthand
    return None


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
    interactive_permission_mode: Literal[
        "acceptEdits", "bypassPermissions", "default", "dontAsk", "plan"
    ] = Field(
        default="acceptEdits",
        description="Permission mode for interactive agent actions",
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

    # Plugin Configuration
    enabled_plugins: str | None = Field(
        default=None,
        description="Comma-separated list of enabled plugin names (None = all discovered)",
    )
    plugin_use_sdk_only: bool = Field(
        default=False,
        description="Disable workarounds and rely only on SDK plugin loading",
    )

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
    autonomous_permission_mode: Literal[
        "acceptEdits", "bypassPermissions", "default", "dontAsk", "plan"
    ] = Field(
        default="bypassPermissions",
        description="Permission mode for autonomous mode (separate from interactive)",
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
        default=900,
        description="Inactivity timeout in seconds (15 minutes) - resets on each message",
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

    # CGF (ContextGrad Framework) Configuration
    cgf_enabled: bool = Field(
        default=False,
        description="Enable CGF infrastructure (tracing, optimization store, rewards)",
    )
    cgf_tracing_enabled: bool = Field(
        default=True,
        description="Enable span tracing when CGF is enabled",
    )
    cgf_exporter: Literal["memory", "redis", "file", "both"] = Field(
        default="memory",
        description=(
            "Span exporter: memory (testing, exports to memory store), "
            "redis (production, exports to Redis store), "
            "file (debugging, exports to JSON file), "
            "both (redis + file for production with debugging)"
        ),
    )
    cgf_span_retention_days: int = Field(
        default=7,
        description="Number of days to retain spans in storage",
    )
    cgf_span_buffer_size: int = Field(
        default=0,
        description="Number of spans to buffer before flushing (0 = immediate write)",
    )
    cgf_file_export_path: Path = Field(
        default=Path("/logs/spans"),
        description="Directory path for file span exports (when exporter=file or both)",
    )

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    @property
    def enabled_plugins_list(self) -> list[str] | None:
        """Get enabled plugins as a list.

        Returns:
            List of plugin names if enabled_plugins is set, None otherwise.
        """
        if self.enabled_plugins is None:
            return None
        return [p.strip() for p in self.enabled_plugins.split(",") if p.strip()]

    @property
    def checkpoint_dir(self) -> Path:
        """Get checkpoint directory path."""
        return self.memory_dir / "checkpoints"

    @property
    def context_dir(self) -> Path:
        """Get context directory path."""
        return self.memory_dir / "context"

    @property
    def cgf_store_backend(self) -> str:
        """Determine store backend from exporter setting.

        Returns:
            "redis" if exporter is redis or both, otherwise "memory".
        """
        if self.cgf_exporter in ("redis", "both"):
            return "redis"
        return "memory"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.workspace_dir,
            self.memory_dir,
            self.logs_dir,
            self.checkpoint_dir,
            self.context_dir,
        ]
        # Add CGF file export directory if CGF is enabled with file export
        if self.cgf_enabled and self.cgf_exporter in ("file", "both"):
            directories.append(self.cgf_file_export_path)

        for directory in directories:
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


@dataclass(frozen=True)
class RuntimeConfig:
    """Immutable runtime configuration for a session.

    Created from HarnessConfig + CLI overrides. The frozen=True ensures
    no mutation after creation.
    """

    model: str
    permission_mode: str
    max_turns: int
    api_timeout: int
    session_timeout: int
    checkpoint_interval: int
    log_level: str
    quiet: bool = False

    @classmethod
    def from_harness_config(
        cls,
        config: HarnessConfig,
        *,
        mode: Literal["interactive", "autonomous"] = "interactive",
        model_override: str | None = None,
        permission_mode_override: str | None = None,
        quiet: bool = False,
    ) -> "RuntimeConfig":
        """Create RuntimeConfig from HarnessConfig with optional overrides.

        Args:
            config: Base HarnessConfig (from .env or defaults)
            mode: Which mode to use for permission_mode default
            model_override: CLI override for model
            permission_mode_override: CLI override for permission mode
            quiet: Suppress logging output
        """
        effective_model = model_override or config.claude_model

        if permission_mode_override:
            effective_permission = permission_mode_override
        elif mode == "autonomous":
            effective_permission = config.autonomous_permission_mode
        else:
            effective_permission = config.interactive_permission_mode

        return cls(
            model=effective_model,
            permission_mode=effective_permission,
            max_turns=config.claude_max_turns,
            api_timeout=config.claude_api_timeout,
            session_timeout=config.claude_session_timeout,
            checkpoint_interval=config.claude_checkpoint_interval,
            log_level="CRITICAL" if quiet else config.log_level,
            quiet=quiet,
        )


def configure_logging(runtime: RuntimeConfig) -> None:
    """Configure logging based on runtime config.

    Args:
        runtime: RuntimeConfig with log_level and quiet settings
    """
    import logging

    import structlog

    level = (
        logging.CRITICAL
        if runtime.quiet
        else getattr(logging, runtime.log_level.upper())
    )
    logging.basicConfig(level=level, format="%(message)s", force=True)
    logging.getLogger().setLevel(level)
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))
