"""Test plugin loading and configuration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from harness.agent import AgentSession
from harness.config import HarnessConfig

# Get the correct plugin base path
PLUGIN_BASE_PATH = (
    Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"
)

# In-tree plugin names. After Step 2b, only cgf-agents stays in-tree;
# context-engineering and research-team are consumed from swe-marketplace.
PLUGINS = ["cgf-agents"]


def test_plugin_paths_exist():
    """Verify all plugin directories exist."""
    for plugin in PLUGINS:
        plugin_path = PLUGIN_BASE_PATH / plugin
        assert plugin_path.exists(), f"Plugin directory not found: {plugin_path}"


def test_plugin_manifests_exist():
    """Verify all plugin manifests exist."""
    for plugin in PLUGINS:
        manifest_path = PLUGIN_BASE_PATH / plugin / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), f"Plugin manifest not found: {manifest_path}"


def test_plugin_manifests_valid():
    """Verify plugin manifests have required fields."""
    required_fields = ["name", "version", "description", "author"]

    for plugin in PLUGINS:
        manifest_path = PLUGIN_BASE_PATH / plugin / ".claude-plugin" / "plugin.json"
        with open(manifest_path) as f:
            data = json.load(f)

        for field in required_fields:
            assert field in data, (
                f"Plugin {plugin} missing required field: {field}"
            )


def test_agent_session_plugin_configuration(tmp_path: Path):
    """Verify AgentSession includes plugin configuration.

    Stubs out ``swe_marketplace_resolved_path`` so the assertion verifies the
    in-tree plugin set independently of whether a local swe-marketplace clone
    exists at .plugins/swe-marketplace.
    """
    # Create required temp directories
    (tmp_path / "workspace").mkdir(exist_ok=True)
    (tmp_path / "memory").mkdir(exist_ok=True)

    mock_config = HarnessConfig(
        workspace_dir=tmp_path / "workspace",
        memory_dir=tmp_path / "memory",
    )

    with (
        patch("harness.agent.RedisMessageBroker") as mock_redis,
        patch("harness.agent.docker_server"),
        patch("harness.agent.context7_server"),
        patch("harness.agent.memory_server"),
        patch.object(
            type(mock_config),
            "swe_marketplace_resolved_path",
            new_callable=PropertyMock,
            return_value=None,
        ),
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.connect.side_effect = ConnectionError(
            "Test: Redis not available"
        )
        mock_redis_instance.connected = False
        mock_redis.return_value = mock_redis_instance

        session = AgentSession(agent_name="test", config=mock_config)

        assert hasattr(session, "plugins"), "AgentSession missing plugins attribute"
        assert len(session.plugins) == 1, (
            f"Expected 1 in-tree plugin (cgf-agents), got {len(session.plugins)}"
        )

        # Verify plugin paths are absolute and valid
        for plugin_config in session.plugins:
            assert plugin_config["type"] == "local"
            plugin_path = Path(plugin_config["path"])
            assert plugin_path.is_absolute(), (
                f"Plugin path not absolute: {plugin_path}"
            )
            assert plugin_path.exists(), f"Plugin path does not exist: {plugin_path}"


def test_plugin_names_in_manifests():
    """Verify plugin names match directory names."""
    for dir_name in PLUGINS:
        manifest_path = (
            PLUGIN_BASE_PATH / dir_name / ".claude-plugin" / "plugin.json"
        )
        with open(manifest_path) as f:
            data = json.load(f)

        assert data["name"] == dir_name, (
            f"Plugin name mismatch: directory={dir_name}, "
            f"manifest name={data['name']}"
        )


def test_plugin_versions_valid():
    """Verify all plugins have valid semantic versions."""
    for plugin in PLUGINS:
        manifest_path = PLUGIN_BASE_PATH / plugin / ".claude-plugin" / "plugin.json"
        with open(manifest_path) as f:
            data = json.load(f)

        version = data.get("version")
        assert version, f"Plugin {plugin} missing version"

        # Basic semantic version check (X.Y.Z)
        parts = version.split(".")
        assert len(parts) == 3, f"Plugin {plugin} version not semantic: {version}"
        assert all(
            p.isdigit() for p in parts
        ), f"Plugin {plugin} version has non-numeric parts: {version}"
