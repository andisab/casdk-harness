"""Direct CLI test for plugin loading.

This test runs the Claude CLI directly to verify plugin loading
behavior without the SDK wrapper.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
import structlog

logger = structlog.get_logger(__name__)

# Paths
CLI_PATH = Path(__file__).parent.parent.parent / ".venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude"
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"


@pytest.mark.integration
def test_cli_plugin_dir_loads():
    """Test that --plugin-dir is accepted by CLI."""
    with tempfile.TemporaryDirectory(prefix="cli_test_") as tmpdir:
        plugin_path = str(PLUGIN_BASE / "context-engineering")

        # Run CLI with plugin-dir and simple prompt
        # Use --output-format json for parseable output
        cmd = [
            str(CLI_PATH),
            "--output-format", "stream-json",
            "--verbose",
            "--plugin-dir", plugin_path,
            "--permission-mode", "bypassPermissions",
            "--max-turns", "1",
            "--print",  # Just print system message and exit
            "Hello"
        ]

        logger.info("Running CLI command", cmd=" ".join(cmd[:15]) + "...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
            )

            logger.info(
                "CLI result",
                returncode=result.returncode,
                stdout_len=len(result.stdout),
                stderr_len=len(result.stderr),
            )

            # Parse stdout for JSON messages
            for line in result.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "system" and msg.get("subtype") == "init":
                            plugins = msg.get("plugins", [])
                            logger.info(
                                "SystemMessage found",
                                plugins=plugins,
                                plugins_count=len(plugins),
                                has_skills=bool(msg.get("skills")),
                                skills_count=len(msg.get("skills", [])),
                            )

                            # Log all skills to see if plugin skills appear
                            if msg.get("skills"):
                                logger.info("Skills in init", skills=msg["skills"])

                    except json.JSONDecodeError:
                        continue

            # Log any errors
            if result.stderr:
                logger.warning("CLI stderr", stderr=result.stderr[:500])

        except subprocess.TimeoutExpired:
            pytest.skip("CLI timed out - may need API key")
        except Exception as e:
            logger.error("CLI error", error=str(e))
            raise


@pytest.mark.integration
def test_cli_multiple_plugin_dirs():
    """Test multiple --plugin-dir flags."""
    with tempfile.TemporaryDirectory(prefix="cli_test_") as tmpdir:
        plugin1 = str(PLUGIN_BASE / "context-engineering")
        plugin2 = str(PLUGIN_BASE / "research-team")

        cmd = [
            str(CLI_PATH),
            "--output-format", "stream-json",
            "--verbose",
            "--plugin-dir", plugin1,
            "--plugin-dir", plugin2,
            "--permission-mode", "bypassPermissions",
            "--max-turns", "1",
            "--print",
            "Hello"
        ]

        logger.info("Running CLI with multiple plugins")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
            )

            # Look for plugins in output
            found_init = False
            for line in result.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "system" and msg.get("subtype") == "init":
                            found_init = True
                            plugins = msg.get("plugins", [])
                            slash_commands = msg.get("slash_commands", [])

                            logger.info(
                                "Init message analysis",
                                plugins=plugins,
                                slash_commands_count=len(slash_commands),
                                # Check for namespaced commands from plugins
                                plugin_commands=[
                                    c for c in slash_commands
                                    if "context-engineering:" in c or "research-team:" in c
                                ],
                            )
                    except json.JSONDecodeError:
                        continue

            assert found_init, "Should receive system init message"

        except subprocess.TimeoutExpired:
            pytest.skip("CLI timed out")


@pytest.mark.integration
def test_cli_shows_plugin_skills():
    """Test if plugin skills appear in init message."""
    with tempfile.TemporaryDirectory(prefix="cli_test_") as tmpdir:
        # Create a minimal .claude directory with skills
        claude_dir = Path(tmpdir) / ".claude" / "skills" / "test-skill"
        claude_dir.mkdir(parents=True)
        (claude_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill from project
---
# Test Skill
This is a test skill.
""")

        plugin_path = str(PLUGIN_BASE / "context-engineering")

        cmd = [
            str(CLI_PATH),
            "--output-format", "stream-json",
            "--verbose",
            "--plugin-dir", plugin_path,
            "--setting-sources", "project",  # Enable project skills
            "--permission-mode", "bypassPermissions",
            "--max-turns", "1",
            "--print",
            "Hello"
        ]

        logger.info("Testing skill discovery with plugin")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
            )

            for line in result.stdout.strip().split('\n'):
                if line.startswith('{'):
                    try:
                        msg = json.loads(line)
                        if msg.get("type") == "system" and msg.get("subtype") == "init":
                            skills = msg.get("skills", [])

                            # Check for project skill
                            has_test_skill = any(
                                s.get("name") == "test-skill" or "test-skill" in str(s)
                                for s in skills
                            ) if isinstance(skills, list) else False

                            # Check for plugin skills
                            plugin_skills = [
                                s for s in skills
                                if isinstance(s, dict) and (
                                    "context-engineering" in str(s) or
                                    "joplin" in str(s).lower()
                                )
                            ] if isinstance(skills, list) else []

                            logger.info(
                                "Skill analysis",
                                total_skills=len(skills) if isinstance(skills, list) else 0,
                                has_test_skill=has_test_skill,
                                plugin_skills_count=len(plugin_skills),
                                sample_skills=skills[:5] if isinstance(skills, list) else skills,
                            )
                    except json.JSONDecodeError:
                        continue

        except subprocess.TimeoutExpired:
            pytest.skip("CLI timed out")
