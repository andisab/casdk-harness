"""MCP Server Configuration Loader.

Handles loading, merging, and validating MCP server configurations from multiple
sources with tiered loading and API key validation.
"""

import json
import os
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MCPConfigLoader:
    """Load and merge MCP server configurations with tiered loading support."""

    # Tier definitions for progressive loading with different timeout strategies
    # All fast servers (git, docker, context7, github, memory) are now loaded as in-process
    # servers (Method A). See agent.py _load_inprocess_servers() for those servers.
    TIER_1_SERVERS: set[str] = set()  # Empty - all fast servers now in-process (Method A)
    TIER_2_SERVERS = {"playwright", "joplin", "excel-haris-musa"}  # Subprocess servers (npx/uvx), 120s timeout

    def __init__(self):
        """Initialize the MCP configuration loader."""
        self.logger = logger.bind(component="mcp_loader")

    def load_config(
        self, base_path: str | Path, plugin_paths: list[Path] | None = None
    ) -> dict[str, Any]:
        """Load and merge MCP configurations from base and plugin paths.

        Args:
            base_path: Path to base .mcp.json file
            plugin_paths: Optional list of plugin directories to scan for .mcp.json files

        Returns:
            Merged configuration dictionary with 'mcpServers' key

        Raises:
            FileNotFoundError: If base config file not found
            ValueError: If configuration is invalid
        """
        base_path = Path(base_path)

        # Load base configuration
        if not base_path.exists():
            raise FileNotFoundError(f"Base MCP config not found: {base_path}")

        self.logger.info("Loading base MCP configuration", path=str(base_path))
        with open(base_path) as f:
            base_config = json.load(f)

        # Validate base config structure
        if "mcpServers" not in base_config:
            raise ValueError(f"Invalid MCP config: missing 'mcpServers' key in {base_path}")

        merged_servers = base_config["mcpServers"].copy()

        # Load and merge plugin configurations
        if plugin_paths:
            for plugin_path in plugin_paths:
                plugin_mcp_path = plugin_path / ".mcp.json"
                if plugin_mcp_path.exists():
                    self.logger.info(
                        "Loading plugin MCP configuration", plugin=plugin_path.name
                    )
                    with open(plugin_mcp_path) as f:
                        plugin_config = json.load(f)

                    if "mcpServers" in plugin_config:
                        # Merge plugin servers (plugin overrides base if conflict)
                        for server_name, server_config in plugin_config["mcpServers"].items():
                            if server_name in merged_servers:
                                self.logger.warning(
                                    "Plugin overriding base MCP server",
                                    server=server_name,
                                    plugin=plugin_path.name,
                                )
                            merged_servers[server_name] = server_config

        # Validate merged configuration
        self.validate_config({"mcpServers": merged_servers})

        return {"mcpServers": merged_servers}

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate MCP server configuration structure.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration is invalid
        """
        if "mcpServers" not in config:
            raise ValueError("Invalid MCP config: missing 'mcpServers' key")

        servers = config["mcpServers"]
        if not isinstance(servers, dict):
            raise ValueError("Invalid MCP config: 'mcpServers' must be a dictionary")

        # Validate each server definition
        for server_name, server_config in servers.items():
            if not isinstance(server_config, dict):
                raise ValueError(
                    f"Invalid server config for '{server_name}': must be a dictionary"
                )

            # Check required fields
            if "command" not in server_config:
                raise ValueError(
                    f"Invalid server config for '{server_name}': missing 'command' field"
                )

            if "args" not in server_config:
                raise ValueError(
                    f"Invalid server config for '{server_name}': missing 'args' field"
                )

            if not isinstance(server_config["args"], list):
                raise ValueError(
                    f"Invalid server config for '{server_name}': 'args' must be a list"
                )

            # env field is optional but must be dict if present
            if "env" in server_config and not isinstance(server_config["env"], dict):
                raise ValueError(
                    f"Invalid server config for '{server_name}': 'env' must be a dictionary"
                )

        self.logger.debug("MCP configuration validated successfully", server_count=len(servers))

    def check_api_keys(self, server_config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Check if required API keys are present based on env placeholders in config.

        Auto-discovers required env vars by looking for ${VAR_NAME} patterns in
        the server's env section. Values without placeholders are treated as
        defaults and not validated.

        Args:
            server_config: MCP server configuration dictionary

        Returns:
            Tuple of (has_all_keys, missing_keys)
        """
        if "env" not in server_config:
            return True, []  # No env vars required

        missing = []
        for _key, value in server_config["env"].items():
            # Check if value is a ${...} placeholder (indicates required env var)
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var_name = value[2:-1]  # Extract "VAR_NAME" from "${VAR_NAME}"
                if not os.getenv(env_var_name):
                    missing.append(env_var_name)

        if missing:
            self.logger.warning(
                "MCP server missing required env vars - will skip",
                server=server_config.get("command"),
                missing_keys=missing,
            )
            return False, missing

        self.logger.debug(
            "MCP server API keys validated",
            server=server_config.get("command"),
            env_vars_checked=len([v for v in server_config.get("env", {}).values()
                                 if isinstance(v, str) and v.startswith("${")]),
        )
        return True, []

    def resolve_env_vars(self, config: dict[str, Any]) -> dict[str, Any]:
        """Resolve environment variable placeholders in configuration.

        Replaces ${VAR_NAME} placeholders with actual environment variable values.

        Args:
            config: Configuration dictionary with potential ${VAR} placeholders

        Returns:
            Configuration with resolved environment variables

        Raises:
            ValueError: If required environment variable is not set
        """
        resolved_config = {"mcpServers": {}}

        for server_name, server_config in config["mcpServers"].items():
            resolved_server = server_config.copy()

            # Resolve env vars in the 'env' field
            if "env" in server_config:
                resolved_env = {}
                for key, value in server_config["env"].items():
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        # Extract variable name
                        var_name = value[2:-1]  # Remove ${ and }
                        env_value = os.getenv(var_name)

                        if env_value is None:
                            # Skip this server - will be caught by check_api_keys
                            self.logger.debug(
                                "Environment variable not set for MCP server",
                                server=server_name,
                                var=var_name,
                            )
                            resolved_env[key] = value  # Keep placeholder
                        else:
                            resolved_env[key] = env_value
                    else:
                        resolved_env[key] = value

                resolved_server["env"] = resolved_env

            resolved_config["mcpServers"][server_name] = resolved_server

        return resolved_config

    def get_tier(self, server_name: str) -> int:
        """Get the tier number for a server.

        Args:
            server_name: Name of the MCP server

        Returns:
            Tier number (1 or 2)
        """
        if server_name in self.TIER_1_SERVERS:
            return 1
        elif server_name in self.TIER_2_SERVERS:
            return 2
        else:
            # Unknown servers default to Tier 1 (fast servers)
            self.logger.warning(
                "Unknown MCP server, defaulting to Tier 1", server=server_name
            )
            return 1

    def filter_by_tier(
        self, config: dict[str, Any], tier: int, check_keys: bool = True
    ) -> dict[str, Any]:
        """Filter configuration to only include servers from specified tier.

        Args:
            config: Full MCP configuration
            tier: Tier number to filter (1, 2, or 3)
            check_keys: If True, skip servers with missing API keys

        Returns:
            Filtered configuration with only specified tier servers
        """
        filtered_servers = {}

        for server_name, server_config in config["mcpServers"].items():
            server_tier = self.get_tier(server_name)

            if server_tier == tier:
                # Check API keys if requested
                if check_keys:
                    has_keys, missing = self.check_api_keys(server_config)
                    if not has_keys:
                        self.logger.info(
                            "Skipping MCP server due to missing API keys",
                            server=server_name,
                            tier=tier,
                            missing_keys=missing,
                        )
                        continue

                filtered_servers[server_name] = server_config

        self.logger.info(
            "Filtered MCP servers by tier",
            tier=tier,
            server_count=len(filtered_servers),
            servers=list(filtered_servers.keys()),
        )

        return {"mcpServers": filtered_servers}

    def load_tier(
        self,
        base_path: str | Path,
        plugin_paths: list[Path] | None = None,
        tier: int = 1,
        check_keys: bool = True,
    ) -> dict[str, Any]:
        """Load and return configuration for a specific tier.

        Convenience method that combines load_config, resolve_env_vars, and filter_by_tier.

        Args:
            base_path: Path to base .mcp.json file
            plugin_paths: Optional list of plugin directories
            tier: Tier number to load (1, 2, or 3)
            check_keys: If True, skip servers with missing API keys

        Returns:
            Filtered and resolved configuration for the specified tier
        """
        # Load and merge all configs
        merged_config = self.load_config(base_path, plugin_paths)

        # Resolve environment variables
        resolved_config = self.resolve_env_vars(merged_config)

        # Filter to specified tier
        tier_config = self.filter_by_tier(resolved_config, tier, check_keys)

        return tier_config
