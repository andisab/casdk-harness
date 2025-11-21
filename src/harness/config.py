"""Configuration management for Claude Agent SDK Harness."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database Configuration
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="claude_harness")
    postgres_user: str = Field(default="claude")
    postgres_password: str = Field(default="")

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

    # Cloud Provider Configuration
    claude_code_use_bedrock: bool = Field(default=False)
    aws_region: str = Field(default="us-east-1")
    claude_code_use_vertex: bool = Field(default=False)
    gcp_project_id: str = Field(default="")
    gcp_region: str = Field(default="us-central1")

    @property
    def database_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
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
