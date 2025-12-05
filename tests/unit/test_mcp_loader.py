"""Unit tests for MCPConfigLoader."""

import json
import os
from unittest.mock import patch

import pytest

from harness.mcp_loader import MCPConfigLoader


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary directory for test configs."""
    return tmp_path


@pytest.fixture
def base_config(temp_config_dir):
    """Create a base .mcp.json configuration file.

    Note: git, docker, context7, github, memory are now in-process servers (Method A),
    so they are not included in the subprocess config.
    Only playwright and joplin remain as subprocess servers.
    """
    config = {
        "mcpServers": {
            "playwright": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-playwright"],
                "env": {}
            },
            "joplin": {
                "command": "npx",
                "args": ["-y", "@joplin/mcp-server"],
                "env": {
                    "JOPLIN_TOKEN": "${JOPLIN_API_TOKEN}",
                    "JOPLIN_BASE_URL": "http://localhost:41184"
                }
            }
        }
    }

    config_path = temp_config_dir / ".mcp.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


@pytest.fixture
def plugin_config(temp_config_dir):
    """Create a plugin .mcp.json configuration file."""
    plugin_dir = temp_config_dir / "test-plugin"
    plugin_dir.mkdir()

    config = {
        "mcpServers": {
            "playwright": {  # Override base config with custom args
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-playwright", "--headless"],
                "env": {}
            },
            "custom-plugin-server": {  # New server from plugin
                "command": "npx",
                "args": ["-y", "@custom/mcp-server"],
                "env": {}
            }
        }
    }

    config_path = plugin_dir / ".mcp.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return plugin_dir


@pytest.fixture
def loader():
    """Create MCPConfigLoader instance."""
    return MCPConfigLoader()


class TestLoadConfig:
    """Tests for load_config method."""

    def test_load_base_config_only(self, loader, base_config):
        """Test loading base configuration without plugins."""
        config = loader.load_config(base_config)

        assert "mcpServers" in config
        # Only subprocess servers remain in config
        assert "playwright" in config["mcpServers"]
        assert "joplin" in config["mcpServers"]
        # In-process servers (git, docker, context7, github, memory) not in subprocess config
        assert "git" not in config["mcpServers"]
        assert "docker" not in config["mcpServers"]
        assert "memory" not in config["mcpServers"]

    def test_load_base_config_not_found(self, loader, temp_config_dir):
        """Test loading non-existent base config raises error."""
        with pytest.raises(FileNotFoundError, match="Base MCP config not found"):
            loader.load_config(temp_config_dir / "nonexistent.json")

    def test_merge_plugin_config(self, loader, base_config, plugin_config):
        """Test merging plugin configuration with base."""
        config = loader.load_config(base_config, plugin_paths=[plugin_config])

        assert "mcpServers" in config
        # Base servers
        assert "joplin" in config["mcpServers"]
        # Plugin server (override with custom args)
        assert "playwright" in config["mcpServers"]
        assert "--headless" in config["mcpServers"]["playwright"]["args"]
        # New plugin server
        assert "custom-plugin-server" in config["mcpServers"]

    def test_skip_missing_plugin_config(self, loader, base_config, temp_config_dir):
        """Test gracefully skipping plugins without .mcp.json."""
        plugin_dir = temp_config_dir / "no-config-plugin"
        plugin_dir.mkdir()

        # Should not raise error
        config = loader.load_config(base_config, plugin_paths=[plugin_dir])
        assert "mcpServers" in config


class TestValidateConfig:
    """Tests for validate_config method."""

    def test_validate_valid_config(self, loader):
        """Test validating a valid configuration."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "args": ["-m", "src.mcp.git.server"],
                    "env": {}
                }
            }
        }
        # Should not raise
        loader.validate_config(config)

    def test_validate_missing_mcp_servers_key(self, loader):
        """Test validation fails for missing mcpServers key."""
        config = {"servers": {}}
        with pytest.raises(ValueError, match="missing 'mcpServers' key"):
            loader.validate_config(config)

    def test_validate_mcp_servers_not_dict(self, loader):
        """Test validation fails if mcpServers is not a dict."""
        config = {"mcpServers": []}
        with pytest.raises(ValueError, match="'mcpServers' must be a dictionary"):
            loader.validate_config(config)

    def test_validate_server_missing_command(self, loader):
        """Test validation fails if server missing command field."""
        config = {
            "mcpServers": {
                "git": {
                    "args": ["-m", "src.mcp.git.server"],
                    "env": {}
                }
            }
        }
        with pytest.raises(ValueError, match="missing 'command' field"):
            loader.validate_config(config)

    def test_validate_server_missing_args(self, loader):
        """Test validation fails if server missing args field."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "env": {}
                }
            }
        }
        with pytest.raises(ValueError, match="missing 'args' field"):
            loader.validate_config(config)

    def test_validate_server_args_not_list(self, loader):
        """Test validation fails if args is not a list."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "args": "not-a-list",
                    "env": {}
                }
            }
        }
        with pytest.raises(ValueError, match="'args' must be a list"):
            loader.validate_config(config)

    def test_validate_server_env_not_dict(self, loader):
        """Test validation fails if env is not a dict."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "args": ["-m", "src.mcp.git.server"],
                    "env": []
                }
            }
        }
        with pytest.raises(ValueError, match="'env' must be a dictionary"):
            loader.validate_config(config)

    def test_validate_env_field_optional(self, loader):
        """Test that env field is optional."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "args": ["-m", "src.mcp.git.server"]
                }
            }
        }
        # Should not raise
        loader.validate_config(config)


class TestCheckApiKeys:
    """Tests for check_api_keys method with auto-discovery."""

    def test_check_no_env_section(self, loader):
        """Test servers with no env section (no keys required)."""
        server_config = {
            "command": "python",
            "args": ["-m", "src.mcp.git.server"]
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is True
        assert missing == []

    def test_check_hardcoded_values_not_required(self, loader):
        """Test that hardcoded env values (non-placeholders) are not validated."""
        server_config = {
            "command": "npx",
            "args": ["-y", "@joplin/mcp-server"],
            "env": {
                "JOPLIN_BASE_URL": "http://localhost:41184"  # Hardcoded, not ${...}
            }
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is True
        assert missing == []

    @patch.dict(os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"}, clear=False)
    def test_check_placeholder_keys_present(self, loader):
        """Test server with ${...} placeholder where env var is present."""
        server_config = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
            }
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is True
        assert missing == []

    @patch.dict(os.environ, {}, clear=True)
    def test_check_placeholder_keys_missing(self, loader):
        """Test server with ${...} placeholder where env var is missing."""
        server_config = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
            }
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is False
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in missing

    @patch.dict(os.environ, {"JOPLIN_API_TOKEN": "token"}, clear=True)
    def test_check_multiple_placeholders_partially_missing(self, loader):
        """Test server with multiple ${...} placeholders, some missing."""
        server_config = {
            "command": "npx",
            "args": ["-y", "@joplin/mcp-server"],
            "env": {
                "JOPLIN_TOKEN": "${JOPLIN_API_TOKEN}",  # Present
                "JOPLIN_URL": "${JOPLIN_BASE_URL}",  # Missing
                "JOPLIN_PORT": "41184"  # Hardcoded (not checked)
            }
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is False
        assert "JOPLIN_BASE_URL" in missing
        assert "JOPLIN_API_TOKEN" not in missing
        assert len(missing) == 1  # Only one missing

    @patch.dict(os.environ, {"MY_API_KEY": "secret", "MY_URL": "http://localhost:8080"}, clear=False)
    def test_check_auto_discovery_all_present(self, loader):
        """Test auto-discovery with all placeholders resolved."""
        server_config = {
            "command": "custom",
            "args": ["server"],
            "env": {
                "API_KEY": "${MY_API_KEY}",
                "BASE_URL": "${MY_URL}",
                "TIMEOUT": "30"  # Hardcoded (not checked)
            }
        }
        has_keys, missing = loader.check_api_keys(server_config)
        assert has_keys is True
        assert missing == []


class TestResolveEnvVars:
    """Tests for resolve_env_vars method."""

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test-token-123"}, clear=False)
    def test_resolve_env_var_placeholder(self, loader):
        """Test resolving ${VAR} placeholders."""
        config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
                    }
                }
            }
        }

        resolved = loader.resolve_env_vars(config)

        assert resolved["mcpServers"]["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "test-token-123"

    def test_resolve_no_placeholders(self, loader):
        """Test config with no placeholders passes through."""
        config = {
            "mcpServers": {
                "git": {
                    "command": "python",
                    "args": ["-m", "src.mcp.git.server"],
                    "env": {}
                }
            }
        }

        resolved = loader.resolve_env_vars(config)

        assert resolved == config

    @patch.dict(os.environ, {}, clear=True)
    def test_resolve_missing_var_for_server_with_required_keys(self, loader):
        """Test missing env var for server with required API keys (should keep placeholder)."""
        config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
                    }
                }
            }
        }

        # Should not raise - keeps placeholder for check_api_keys to handle
        resolved = loader.resolve_env_vars(config)
        assert "${GITHUB_PERSONAL_ACCESS_TOKEN}" in resolved["mcpServers"]["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"]

    @patch.dict(os.environ, {}, clear=True)
    def test_resolve_missing_var_keeps_placeholder(self, loader):
        """Test missing env var keeps placeholder (validation deferred to check_api_keys)."""
        config = {
            "mcpServers": {
                "custom": {
                    "command": "npx",
                    "args": ["-y", "@custom/server"],
                    "env": {
                        "CUSTOM_TOKEN": "${MISSING_VAR}"
                    }
                }
            }
        }

        # Should not raise - keeps placeholder for check_api_keys to handle
        resolved = loader.resolve_env_vars(config)
        assert "${MISSING_VAR}" in resolved["mcpServers"]["custom"]["env"]["CUSTOM_TOKEN"]


class TestGetTier:
    """Tests for get_tier method.

    Note: context7 and github are now in-process servers (Method A),
    so they're no longer in the subprocess tier definitions.
    """

    def test_tier1_servers(self, loader):
        """Test Tier 1 server identification (Fast subprocess - 30s timeout)."""
        assert loader.get_tier("git") == 1
        assert loader.get_tier("docker") == 1
        # context7 and github are now in-process, not in tier defs

    def test_tier2_servers(self, loader):
        """Test Tier 2 server identification (Slow subprocess - 120s timeout)."""
        # Only playwright and joplin remain as subprocess servers
        assert loader.get_tier("playwright") == 2
        assert loader.get_tier("joplin") == 2

    def test_unknown_server_defaults_to_tier1(self, loader):
        """Test unknown servers default to Tier 1."""
        assert loader.get_tier("unknown-server") == 1
        # All these are now in-process servers, so they default to tier 1
        # when checked against subprocess tiers
        assert loader.get_tier("git") == 1  # In-process, defaults to tier 1
        assert loader.get_tier("docker") == 1  # In-process, defaults to tier 1
        assert loader.get_tier("memory") == 1  # In-process, defaults to tier 1
        assert loader.get_tier("context7") == 1  # In-process, defaults to tier 1
        assert loader.get_tier("github") == 1  # In-process, defaults to tier 1


class TestFilterByTier:
    """Tests for filter_by_tier method.

    Note: git, docker, context7, github, memory are now in-process servers (Method A).
    Only playwright and joplin remain as subprocess servers (Tier 2).
    Tier 1 is empty.
    """

    def test_filter_tier1_only(self, loader):
        """Test filtering for Tier 1 - now empty since all fast servers are in-process."""
        config = {
            "mcpServers": {
                "playwright": {"command": "npx", "args": [], "env": {}},
                "joplin": {"command": "npx", "args": [], "env": {}},
                "unknown-server": {"command": "npx", "args": [], "env": {}},
            }
        }

        filtered = loader.filter_by_tier(config, tier=1, check_keys=False)

        # Only unknown servers default to tier 1
        assert len(filtered["mcpServers"]) == 1
        assert "unknown-server" in filtered["mcpServers"]
        assert "playwright" not in filtered["mcpServers"]
        assert "joplin" not in filtered["mcpServers"]

    def test_filter_tier2_only(self, loader):
        """Test filtering for Tier 2 subprocess servers only (Slow - 120s)."""
        config = {
            "mcpServers": {
                "playwright": {"command": "npx", "args": [], "env": {}},
                "joplin": {"command": "npx", "args": [], "env": {}},
                "unknown-server": {"command": "npx", "args": [], "env": {}},
            }
        }

        filtered = loader.filter_by_tier(config, tier=2, check_keys=False)

        # Only playwright and joplin are tier 2
        assert len(filtered["mcpServers"]) == 2
        assert "playwright" in filtered["mcpServers"]
        assert "joplin" in filtered["mcpServers"]
        assert "unknown-server" not in filtered["mcpServers"]

    @patch.dict(os.environ, {}, clear=True)
    def test_filter_with_missing_api_keys_skips_server(self, loader):
        """Test filtering with check_keys=True skips servers with missing keys."""
        config = {
            "mcpServers": {
                "playwright": {"command": "npx", "args": [], "env": {}},
                "joplin": {
                    "command": "npx",
                    "args": [],
                    "env": {"JOPLIN_TOKEN": "${JOPLIN_API_TOKEN}"}
                },
            }
        }

        filtered = loader.filter_by_tier(config, tier=2, check_keys=True)

        # Joplin should be skipped due to missing API key
        assert len(filtered["mcpServers"]) == 1
        assert "playwright" in filtered["mcpServers"]
        assert "joplin" not in filtered["mcpServers"]

    @patch.dict(os.environ, {"JOPLIN_API_TOKEN": "test-token"}, clear=False)
    def test_filter_with_api_keys_present_includes_server(self, loader):
        """Test filtering with check_keys=True includes servers with keys present."""
        config = {
            "mcpServers": {
                "joplin": {
                    "command": "npx",
                    "args": [],
                    "env": {"JOPLIN_TOKEN": "${JOPLIN_API_TOKEN}"}
                },
            }
        }

        filtered = loader.filter_by_tier(config, tier=2, check_keys=True)

        assert len(filtered["mcpServers"]) == 1
        assert "joplin" in filtered["mcpServers"]


class TestLoadTier:
    """Tests for load_tier convenience method.

    Note: git, docker, context7, github, memory are now in-process servers (Method A).
    Only playwright and joplin remain as subprocess servers in Tier 2.
    Tier 1 is empty.
    """

    @patch.dict(os.environ, {}, clear=False)
    def test_load_tier1_complete_workflow(self, loader, base_config):
        """Test complete workflow for loading Tier 1 - now empty."""
        tier1_config = loader.load_tier(base_config, tier=1, check_keys=True)

        assert "mcpServers" in tier1_config
        # Tier 1 is empty - all fast servers are now in-process
        assert len(tier1_config["mcpServers"]) == 0

    @patch.dict(os.environ, {"JOPLIN_API_TOKEN": "test-token"}, clear=False)
    def test_load_tier_with_env_vars_resolved(self, loader, base_config):
        """Test that load_tier resolves environment variables."""
        # Load Tier 2 (includes joplin which requires API key)
        tier2_config = loader.load_tier(base_config, tier=2, check_keys=True)

        assert "joplin" in tier2_config["mcpServers"]
        # Env var should be resolved, not placeholder
        assert tier2_config["mcpServers"]["joplin"]["env"]["JOPLIN_TOKEN"] == "test-token"

    def test_load_tier_with_plugins(self, loader, base_config, plugin_config):
        """Test loading tier with plugin configuration merged."""
        # Plugin overrides playwright with custom args
        # Load Tier 2 to check plugin servers
        tier2_config = loader.load_tier(
            base_config,
            plugin_paths=[plugin_config],
            tier=2,
            check_keys=False
        )

        # Should have playwright from plugin with override (has --headless arg)
        assert "playwright" in tier2_config["mcpServers"]
        assert "--headless" in tier2_config["mcpServers"]["playwright"]["args"]

        # Should have joplin from base
        assert "joplin" in tier2_config["mcpServers"]
