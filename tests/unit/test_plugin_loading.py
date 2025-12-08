"""Test plugin loading and configuration."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.agent import AgentSession
from harness.config import HarnessConfig


def test_plugin_paths_exist():
    """Verify all plugin directories exist."""
    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    plugins = ["arch", "context-engineering", "research-team"]
    for plugin in plugins:
        plugin_path = base_path / plugin
        assert plugin_path.exists(), f"Plugin directory not found: {plugin_path}"


def test_plugin_manifests_exist():
    """Verify all plugin manifests exist."""
    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    plugins = ["arch", "context-engineering", "research-team"]
    for plugin in plugins:
        manifest_path = base_path / plugin / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), f"Plugin manifest not found: {manifest_path}"


def test_plugin_manifests_valid():
    """Verify plugin manifests have required fields."""
    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    required_fields = ["name", "version", "description", "author"]

    plugins = ["arch", "context-engineering", "research-team"]
    for plugin in plugins:
        manifest_path = base_path / plugin / ".claude-plugin" / "plugin.json"
        with open(manifest_path) as f:
            data = json.load(f)

        for field in required_fields:
            assert field in data, f"Plugin {plugin} missing required field: {field}"


def test_agent_session_plugin_configuration(tmp_path: Path):
    """Verify AgentSession includes plugin configuration."""
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
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.connect.side_effect = ConnectionError("Test: Redis not available")
        mock_redis_instance.connected = False
        mock_redis.return_value = mock_redis_instance

        session = AgentSession(agent_name="test", config=mock_config)

        assert hasattr(session, "plugins"), "AgentSession missing plugins attribute"
        assert len(session.plugins) == 3, f"Expected 3 plugins, got {len(session.plugins)}"

        # Verify plugin paths are absolute and valid
        for plugin_config in session.plugins:
            assert plugin_config["type"] == "local"
            plugin_path = Path(plugin_config["path"])
            assert plugin_path.is_absolute(), f"Plugin path not absolute: {plugin_path}"
            assert plugin_path.exists(), f"Plugin path does not exist: {plugin_path}"


def test_plugin_names_in_manifests():
    """Verify plugin names match directory names."""
    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    expected_names = {
        "arch": "arch",
        "context-engineering": "context-engineering",
        "research-team": "research-team",
    }

    for dir_name, expected_name in expected_names.items():
        manifest_path = base_path / dir_name / ".claude-plugin" / "plugin.json"
        with open(manifest_path) as f:
            data = json.load(f)

        assert data["name"] == expected_name, (
            f"Plugin name mismatch: directory={dir_name}, "
            f"manifest name={data['name']}, expected={expected_name}"
        )


def test_plugin_versions_valid():
    """Verify all plugins have valid semantic versions."""
    base_path = Path(__file__).parent.parent.parent / ".claude" / "plugins"

    plugins = ["arch", "context-engineering", "research-team"]
    for plugin in plugins:
        manifest_path = base_path / plugin / ".claude-plugin" / "plugin.json"
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
