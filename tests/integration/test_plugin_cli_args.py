"""Test that plugin paths are correctly passed to the Claude CLI.

This test verifies that the SDK correctly builds --plugin-dir arguments
when plugins are specified in ClaudeAgentOptions.
"""

import tempfile
from pathlib import Path

import pytest
import structlog
from claude_agent_sdk import ClaudeAgentOptions

logger = structlog.get_logger(__name__)

# Path to our plugins
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


def test_sdk_builds_plugin_dir_args():
    """Verify SDK builds correct --plugin-dir CLI arguments."""
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    with tempfile.TemporaryDirectory(prefix="plugin_test_") as tmpdir:
        plugins = [
            {"type": "local", "path": str(PLUGIN_BASE / "context-engineering")},
            {"type": "local", "path": str(PLUGIN_BASE / "research-team")},
        ]

        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            permission_mode="bypassPermissions",
            max_turns=3,
            cwd=tmpdir,
            model="claude-sonnet-4-20250514",
            plugins=plugins,
        )

        # Create transport to inspect command building
        transport = SubprocessCLITransport(prompt="test", options=options)

        # Build the command
        cmd = transport._build_command()

        # Find --plugin-dir arguments
        plugin_dir_indices = [
            i for i, arg in enumerate(cmd) if arg == "--plugin-dir"
        ]

        logger.info(
            "Plugin dir arguments found",
            count=len(plugin_dir_indices),
            indices=plugin_dir_indices,
        )

        # Should have --plugin-dir for each plugin
        assert len(plugin_dir_indices) == 2, \
            f"Expected 2 --plugin-dir args, got {len(plugin_dir_indices)}"

        # Verify paths are correct
        for idx in plugin_dir_indices:
            plugin_path = cmd[idx + 1]
            assert Path(plugin_path).exists(), f"Plugin path should exist: {plugin_path}"

            # Should be one of our plugins
            plugin_name = Path(plugin_path).name
            assert plugin_name in ["context-engineering", "research-team"], \
                f"Unexpected plugin: {plugin_name}"

            logger.info("Plugin path verified", path=plugin_path)

        # Log full command for debugging
        logger.info(
            "Full CLI command",
            cmd=" ".join(cmd[:20]) + "..." if len(cmd) > 20 else " ".join(cmd),
        )


def test_plugin_dir_arg_format():
    """Verify --plugin-dir args have correct format."""
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    with tempfile.TemporaryDirectory(prefix="plugin_test_") as tmpdir:
        plugin_path = str(PLUGIN_BASE / "context-engineering")
        plugins = [{"type": "local", "path": plugin_path}]

        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            permission_mode="bypassPermissions",
            max_turns=3,
            cwd=tmpdir,
            model="claude-sonnet-4-20250514",
            plugins=plugins,
        )

        transport = SubprocessCLITransport(prompt="test", options=options)
        cmd = transport._build_command()

        # Find the --plugin-dir and its value
        found = False
        for i, arg in enumerate(cmd):
            if arg == "--plugin-dir" and i + 1 < len(cmd):
                assert cmd[i + 1] == plugin_path, \
                    f"Plugin path mismatch: {cmd[i + 1]} != {plugin_path}"
                found = True
                break

        assert found, "--plugin-dir not found in command"
        logger.info("Plugin dir format verified", path=plugin_path)


def test_multiple_plugins_order():
    """Verify multiple plugins maintain order."""
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    with tempfile.TemporaryDirectory(prefix="plugin_test_") as tmpdir:
        plugin_paths = [
            str(PLUGIN_BASE / "context-engineering"),
            str(PLUGIN_BASE / "research-team"),
        ]
        plugins = [{"type": "local", "path": p} for p in plugin_paths]

        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            permission_mode="bypassPermissions",
            max_turns=3,
            cwd=tmpdir,
            model="claude-sonnet-4-20250514",
            plugins=plugins,
        )

        transport = SubprocessCLITransport(prompt="test", options=options)
        cmd = transport._build_command()

        # Extract all plugin paths in order
        extracted_paths = []
        for i, arg in enumerate(cmd):
            if arg == "--plugin-dir" and i + 1 < len(cmd):
                extracted_paths.append(cmd[i + 1])

        assert extracted_paths == plugin_paths, \
            f"Plugin order not preserved: {extracted_paths} != {plugin_paths}"

        logger.info("Plugin order verified", paths=extracted_paths)
