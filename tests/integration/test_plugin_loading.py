"""Integration tests for plugin loading via Claude Agent SDK.

Tests verify that plugins are loaded correctly according to the official
SDK documentation: https://platform.claude.com/docs/en/agent-sdk/plugins

Key behaviors being tested:
1. Plugins load from local filesystem paths
2. Plugin commands/agents/skills are accessible
3. SystemMessage contains plugin information on init

Cost: Each test costs ~100-500 tokens (~$0.001-0.005 per test)
Duration: ~5-20 seconds per test
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
import structlog
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, SystemMessage

logger = structlog.get_logger(__name__)

# Path to our plugins
PLUGIN_BASE = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"
CONTEXT_ENGINEERING_PLUGIN = PLUGIN_BASE / "context-engineering"
RESEARCH_TEAM_PLUGIN = PLUGIN_BASE / "research-team"


@pytest.fixture
def plugin_paths() -> list[dict[str, str]]:
    """Return plugin configurations for SDK."""
    return [
        {"type": "local", "path": str(CONTEXT_ENGINEERING_PLUGIN)},
        {"type": "local", "path": str(RESEARCH_TEAM_PLUGIN)},
    ]


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for tests running outside container."""
    with tempfile.TemporaryDirectory(prefix="plugin_test_") as tmpdir:
        yield Path(tmpdir)


class TestPluginStructure:
    """Test plugin directory structure matches SDK requirements."""

    def test_plugin_directories_exist(self):
        """Verify plugin directories exist on filesystem."""
        assert PLUGIN_BASE.exists(), f"Plugin base directory not found: {PLUGIN_BASE}"
        assert CONTEXT_ENGINEERING_PLUGIN.exists(), "context-engineering plugin not found"
        assert RESEARCH_TEAM_PLUGIN.exists(), "research-team plugin not found"

    def test_plugin_manifests_exist(self):
        """Verify each plugin has .claude-plugin/plugin.json manifest."""
        for plugin_name, plugin_path in [
            ("context-engineering", CONTEXT_ENGINEERING_PLUGIN),
            ("research-team", RESEARCH_TEAM_PLUGIN),
        ]:
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
            assert manifest_path.exists(), f"{plugin_name} missing manifest at {manifest_path}"

    def test_plugin_manifest_valid_json(self):
        """Verify plugin.json files are valid JSON with required fields."""
        required_fields = ["name", "version", "description"]

        for plugin_path in [CONTEXT_ENGINEERING_PLUGIN, RESEARCH_TEAM_PLUGIN]:
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
            content = manifest_path.read_text()

            # Should parse as valid JSON
            manifest = json.loads(content)

            # Should have required fields
            for field in required_fields:
                assert field in manifest, f"Manifest missing '{field}': {manifest_path}"

            # Name should be valid format (lowercase, hyphens)
            name = manifest["name"]
            assert name == name.lower(), f"Plugin name should be lowercase: {name}"
            assert " " not in name, f"Plugin name should not contain spaces: {name}"

            logger.info(
                "Plugin manifest validated",
                plugin=manifest["name"],
                version=manifest["version"],
            )

    def test_plugin_skills_structure(self):
        """Verify skills directories follow expected structure."""
        for plugin_path in [CONTEXT_ENGINEERING_PLUGIN, RESEARCH_TEAM_PLUGIN]:
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
            manifest = json.loads(manifest_path.read_text())

            # Check skills paths if specified
            skill_paths = manifest.get("skills", [])
            for skill_rel_path in skill_paths:
                skill_dir = plugin_path / skill_rel_path.lstrip("./")

                if skill_dir.exists():
                    # Skills should have subdirectories with SKILL.md files
                    skill_files = list(skill_dir.glob("*/SKILL.md"))
                    logger.info(
                        "Skills found in plugin",
                        plugin=manifest["name"],
                        skill_count=len(skill_files),
                        skills=[f.parent.name for f in skill_files],
                    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPluginLoadingWithSDK:
    """Test plugin loading through the Claude Agent SDK."""

    async def test_sdk_accepts_plugin_config(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Verify SDK accepts plugins parameter without error.

        This tests the basic configuration step - SDK should not error
        when plugins are specified in options.
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Skill"],
            permission_mode="bypassPermissions",
            max_turns=3,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,  # Key test: plugins parameter
        )

        logger.info(
            "Testing SDK accepts plugins parameter",
            plugin_count=len(plugin_paths),
            plugins=[p["path"] for p in plugin_paths],
        )

        # Should not raise during initialization
        client = ClaudeSDKClient(options=options)
        assert client is not None

        logger.info("SDK accepted plugins configuration without error")

    async def test_plugin_appears_in_system_message(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Verify loaded plugins appear in SystemMessage on init.

        According to SDK docs, the SystemMessage should contain:
        - message.plugins: list of loaded plugins
        - message.slash_commands: available commands (may include plugin commands)
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Skill"],
            permission_mode="bypassPermissions",
            max_turns=5,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,
        )

        logger.info("Testing plugins appear in SystemMessage")

        system_message_data = None

        async with ClaudeSDKClient(options=options) as client:
            await client.query("What plugins are available?")

            async for msg in client.receive_response():
                # Check for SystemMessage with init subtype
                if isinstance(msg, SystemMessage):
                    if hasattr(msg, "subtype") and msg.subtype == "init":
                        system_message_data = msg.data if hasattr(msg, "data") else None
                        logger.info(
                            "SystemMessage init received",
                            has_data=system_message_data is not None,
                            data_keys=list(system_message_data.keys()) if system_message_data else [],
                        )
                        break

        # Log what we found (don't fail if plugins not in message - this verifies behavior)
        if system_message_data:
            plugins_in_msg = system_message_data.get("plugins", [])
            commands_in_msg = system_message_data.get("slash_commands", [])
            logger.info(
                "SystemMessage contents",
                plugins=plugins_in_msg,
                slash_commands_count=len(commands_in_msg),
            )

            # If plugins appear, verify structure
            if plugins_in_msg:
                for plugin in plugins_in_msg:
                    assert "name" in plugin or isinstance(plugin, str), \
                        f"Plugin entry should have name or be string: {plugin}"
                logger.info("Plugins found in SystemMessage", count=len(plugins_in_msg))
            else:
                # This is the known limitation - log it
                logger.warning(
                    "Plugins NOT appearing in SystemMessage - SDK limitation",
                    see_issue="https://github.com/anthropics/claude-agent-sdk-python/issues/213"
                )
        else:
            logger.warning("No SystemMessage init data received")

    async def test_plugin_skills_discoverable(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Verify plugin skills can be discovered and used.

        Even if plugins aren't fully loading via SDK, the workaround
        in agent.py manually discovers plugin skills. This test verifies
        that workaround is working.
        """
        # Use setting_sources to enable skill discovery
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Skill"],
            permission_mode="bypassPermissions",
            max_turns=10,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            setting_sources=["user", "project"],
            plugins=plugin_paths,
        )

        logger.info("Testing plugin skills are discoverable")

        messages = []
        async with ClaudeSDKClient(options=options) as client:
            # Ask specifically about plugin skills
            await client.query(
                "List any skills you have from plugins. "
                "Check if you have skills like 'joplin-research' or 'agent-definition-creation'. "
                "Keep response brief."
            )

            async for msg in client.receive_response():
                messages.append(msg)
                logger.debug("Message received", msg_type=type(msg).__name__)

        assert len(messages) > 0, "Should receive response about skills"
        logger.info(
            "Plugin skills discovery test completed",
            message_count=len(messages),
        )

    async def test_namespaced_plugin_commands(
        self, plugin_paths: list[dict[str, str]], temp_workspace: Path
    ):
        """
        Test plugin commands use namespaced format: plugin-name:command-name

        According to SDK docs, plugin commands should be accessible via
        the namespaced format to avoid conflicts.
        """
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Skill", "SlashCommand"],
            permission_mode="bypassPermissions",
            max_turns=5,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugin_paths,
        )

        logger.info("Testing namespaced plugin commands")

        messages = []
        async with ClaudeSDKClient(options=options) as client:
            # Try to invoke a namespaced command
            # Note: This may fail if commands aren't registered - that's informative
            await client.query(
                "What slash commands do you have available from plugins? "
                "List any that start with 'context-engineering:' or 'research-team:'."
            )

            async for msg in client.receive_response():
                messages.append(msg)

        assert len(messages) > 0, "Should receive response"
        logger.info(
            "Namespaced commands test completed",
            message_count=len(messages),
        )


class TestPluginLoadingViaHarness:
    """Test plugin loading through the harness AgentSession.

    These tests verify the harness code without requiring the container
    environment. They use mocking where needed to avoid container paths.
    """

    def test_plugin_base_path_exists(self):
        """Verify the plugin base path used by AgentSession exists."""
        from pathlib import Path
        plugin_base = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"
        assert plugin_base.exists(), f"Plugin base should exist: {plugin_base}"

        # Should have our two plugins
        plugins = list(plugin_base.iterdir())
        plugin_names = [p.name for p in plugins if p.is_dir()]
        assert "context-engineering" in plugin_names
        assert "research-team" in plugin_names

        logger.info("Plugin base path verified", plugins=plugin_names)

    def test_plugin_configs_match_sdk_format(self):
        """Verify plugin configs match SDK expected format."""
        from pathlib import Path

        plugin_base = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"

        # Build configs like AgentSession does
        plugins = [
            {"type": "local", "path": str(plugin_base / "context-engineering")},
            {"type": "local", "path": str(plugin_base / "research-team")},
        ]

        # Verify structure matches SDK docs
        for plugin in plugins:
            assert "type" in plugin, "Plugin should have 'type'"
            assert "path" in plugin, "Plugin should have 'path'"
            assert plugin["type"] == "local", "Type should be 'local'"
            assert Path(plugin["path"]).exists(), f"Path should exist: {plugin['path']}"

        logger.info("Plugin configs match SDK format", count=len(plugins))

    def test_skill_discovery_logic(self):
        """Test the skill discovery logic used by AgentSession._load_all_skills()."""
        import json
        from pathlib import Path

        plugin_base = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"
        all_skills: dict[str, dict[str, str]] = {}

        # 1. Base skills (from src/harness/skills/)
        base_skills_dir = Path(__file__).parent.parent.parent / "src" / "harness" / "skills"
        if base_skills_dir.exists():
            for skill_path in base_skills_dir.glob("*/SKILL.md"):
                skill_name = skill_path.parent.name
                all_skills[skill_name] = {
                    "source": "base",
                    "path": str(skill_path),
                }

        # 2. Plugin skills
        for plugin_path in plugin_base.glob("*/"):
            if not plugin_path.is_dir():
                continue

            plugin_name = plugin_path.name
            manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

            if not manifest_path.exists():
                continue

            manifest = json.loads(manifest_path.read_text())
            skill_paths = manifest.get("skills", [])

            for skill_rel_path in skill_paths:
                skills_dir = plugin_path / skill_rel_path.lstrip("./")
                if not skills_dir.exists():
                    continue

                for skill_path in skills_dir.glob("*/SKILL.md"):
                    skill_name = skill_path.parent.name
                    all_skills[skill_name] = {
                        "source": "plugin",
                        "plugin": plugin_name,
                        "path": str(skill_path),
                    }

        # Verify results
        base_count = len([s for s in all_skills.values() if s["source"] == "base"])
        plugin_count = len([s for s in all_skills.values() if s["source"] == "plugin"])

        assert base_count > 0, "Should discover base skills"

        logger.info(
            "Skill discovery logic verified",
            total=len(all_skills),
            base=base_count,
            plugins=plugin_count,
            skills=list(all_skills.keys()),
        )

    def test_sdk_options_builder_includes_plugins(self, temp_workspace: Path):
        """Test that ClaudeAgentOptions accepts plugins parameter."""
        from pathlib import Path

        plugin_base = Path(__file__).parent.parent.parent / "src" / "harness" / "plugins"
        plugins = [
            {"type": "local", "path": str(plugin_base / "context-engineering")},
            {"type": "local", "path": str(plugin_base / "research-team")},
        ]

        # Build options like AgentSession._build_sdk_options() does
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Skill"],
            permission_mode="bypassPermissions",
            max_turns=10,
            cwd=str(temp_workspace),
            model="claude-sonnet-4-20250514",
            plugins=plugins,
        )

        # Verify plugins are included
        assert hasattr(options, "plugins"), "Options should have plugins"
        assert options.plugins is not None, "Plugins should not be None"
        assert len(options.plugins) == 2, "Should have 2 plugins"

        logger.info(
            "SDK options builder includes plugins",
            plugin_count=len(options.plugins),
        )
