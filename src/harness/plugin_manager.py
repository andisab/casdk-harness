"""Plugin lifecycle management for Claude Agent SDK Harness.

Consolidates all plugin loading logic with support for:
- Agents (with SDK workaround)
- Skills
- Commands (slash commands)
- Hooks (event triggers)
- MCP servers

Designed with SDK fallback in mind - when plugin limitation is fixed,
set PLUGIN_USE_SDK_ONLY=true to disable workarounds.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
import yaml
from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

logger = structlog.get_logger(__name__)


# Model name normalization map
MODEL_NORMALIZE_MAP: dict[str, str] = {
    "opus 4.1": "opus",
    "opus 4.5": "opus",
    "opus": "opus",
    "sonnet 4.5": "sonnet",
    "sonnet 4.0": "sonnet",
    "sonnet": "sonnet",
    "haiku 3.5": "haiku",
    "haiku": "haiku",
}


class HookEvent(Enum):
    """Supported hook event types matching SDK-canonical names.

    REFACTOR.md Part 2 Phase 2: renamed `POST_SESSION_START` → `SESSION_START`
    to match the SDK-canonical event name. Dropped the previously-unused
    `PRE_SESSION_START` (no SDK equivalent).
    """

    SESSION_START = "SessionStart"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    NOTIFICATION = "Notification"
    STOP = "Stop"


@dataclass
class PluginManifest:
    """Plugin manifest data from plugin.json."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    agents: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    mcp: str | None = None  # Path to .mcp.json relative to plugin root

    @classmethod
    def from_dict(cls, data: dict[str, Any], plugin_name: str) -> PluginManifest:
        """Create manifest from parsed JSON dict."""
        return cls(
            name=data.get("name", plugin_name),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            agents=data.get("agents", []),
            skills=data.get("skills", []),
            commands=data.get("commands", []),
            hooks=data.get("hooks", []),
            mcp=data.get("mcp"),
        )


@dataclass
class Plugin:
    """Represents a discovered plugin."""

    name: str
    path: Path
    manifest: PluginManifest
    loaded: bool = False
    error: str | None = None


@dataclass
class PluginCommand:
    """A slash command defined by a plugin."""

    name: str  # Full namespaced name: plugin:command
    description: str
    content: str  # Markdown content with placeholders ($1, $ARGUMENTS)
    plugin_name: str
    allowed_tools: list[str] | None = None
    argument_hint: str | None = None
    model: str | None = None


@dataclass
class PluginHook:
    """A hook event handler defined by a plugin."""

    event: HookEvent
    command: str  # Shell command to execute
    plugin_name: str
    matcher: dict[str, Any] | None = None  # Tool/file matchers
    timeout: int = 30


class PluginManager:
    """Manages plugin discovery, loading, and resource access.

    Consolidates all plugin operations with consistent namespacing.
    Use `use_sdk_only=True` to disable workarounds when SDK is fixed.
    """

    def __init__(
        self,
        plugin_dirs: list[Path] | None = None,
        enabled_plugins: list[str] | None = None,
        use_sdk_only: bool = False,
    ) -> None:
        """Initialize plugin manager.

        Args:
            plugin_dirs: Directories to search for plugins.
                         Defaults to src/harness/plugins if not specified.
            enabled_plugins: List of plugin names to enable. None = all discovered.
            use_sdk_only: If True, skip workarounds and rely on SDK plugin loading.
        """
        if plugin_dirs is None:
            plugin_dirs = [Path(__file__).parent / "plugins"]
        self.plugin_dirs = plugin_dirs
        self.enabled_plugins = enabled_plugins
        self.use_sdk_only = use_sdk_only

        # Storage for discovered and loaded resources
        self._plugins: dict[str, Plugin] = {}
        self._agents: dict[str, SDKAgentDefinition] = {}
        self._skills: dict[str, dict[str, str]] = {}
        self._commands: dict[str, PluginCommand] = {}
        self._hooks: list[PluginHook] = []
        self._mcp_configs: list[Path] = []

    def discover_plugins(self) -> list[Plugin]:
        """Discover all plugins in configured directories.

        Returns:
            List of discovered Plugin objects.
        """
        discovered: list[Plugin] = []

        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                logger.debug("Plugin directory does not exist", path=str(plugin_dir))
                continue

            for plugin_path in plugin_dir.glob("*/"):
                if not plugin_path.is_dir():
                    continue

                plugin_name = plugin_path.name
                manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

                if not manifest_path.exists():
                    logger.debug(
                        "Plugin missing manifest, skipping",
                        plugin=plugin_name,
                        expected_path=str(manifest_path),
                    )
                    continue

                try:
                    manifest_data = json.loads(manifest_path.read_text())
                    manifest = PluginManifest.from_dict(manifest_data, plugin_name)

                    plugin = Plugin(
                        name=plugin_name,
                        path=plugin_path,
                        manifest=manifest,
                    )
                    discovered.append(plugin)
                    self._plugins[plugin_name] = plugin

                    logger.debug(
                        "Discovered plugin",
                        plugin=plugin_name,
                        version=manifest.version,
                        agents=len(manifest.agents),
                        skills=len(manifest.skills),
                        commands=len(manifest.commands),
                        hooks=len(manifest.hooks),
                    )

                except Exception as e:
                    logger.warning(
                        "Failed to parse plugin manifest",
                        plugin=plugin_name,
                        error=str(e),
                    )

        # Filter by enabled plugins if specified
        if self.enabled_plugins is not None:
            discovered = [p for p in discovered if p.name in self.enabled_plugins]
            self._plugins = {
                k: v for k, v in self._plugins.items() if k in self.enabled_plugins
            }

        logger.info(
            "Plugin discovery complete",
            discovered=len(discovered),
            plugins=list(self._plugins.keys()),
        )

        return discovered

    def load_plugin(self, name: str) -> Plugin:
        """Load a plugin and all its resources.

        Args:
            name: Plugin name to load.

        Returns:
            The loaded Plugin object.

        Raises:
            KeyError: If plugin not found.
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin not found: {name}")

        plugin = self._plugins[name]

        if plugin.loaded:
            return plugin

        try:
            # Load all resource types
            self._load_plugin_agents(plugin)
            self._load_plugin_skills(plugin)
            self._load_plugin_commands(plugin)
            self._load_plugin_hooks(plugin)
            self._load_plugin_mcp(plugin)

            plugin.loaded = True
            logger.debug("Plugin loaded successfully", plugin=name)

        except Exception as e:
            plugin.error = str(e)
            logger.error(
                "Failed to load plugin",
                plugin=name,
                error=str(e),
            )

        return plugin

    def load_all_plugins(self) -> None:
        """Load all discovered plugins."""
        for name in self._plugins:
            self.load_plugin(name)

    def _load_plugin_agents(self, plugin: Plugin) -> None:
        """Load agent definitions from a plugin."""
        if self.use_sdk_only:
            # Skip workaround - SDK will load agents
            return

        if not plugin.manifest.agents:
            return

        for agent_rel_path in plugin.manifest.agents:
            agents_dir = plugin.path / agent_rel_path.lstrip("./")

            if not agents_dir.exists():
                continue

            for agent_file in agents_dir.glob("*.md"):
                try:
                    content = agent_file.read_text()
                    agent_def = self._parse_agent_file(content, plugin.name, agent_file)

                    if agent_def:
                        agent_name, sdk_agent = agent_def
                        namespaced_key = f"{plugin.name}:{agent_name}"
                        self._agents[namespaced_key] = sdk_agent

                        logger.debug(
                            "Loaded plugin agent",
                            plugin=plugin.name,
                            agent=agent_name,
                            key=namespaced_key,
                        )

                except Exception as e:
                    logger.warning(
                        "Failed to load plugin agent",
                        plugin=plugin.name,
                        file=agent_file.name,
                        error=str(e),
                    )

    def _parse_agent_file(
        self, content: str, plugin_name: str, agent_file: Path
    ) -> tuple[str, SDKAgentDefinition] | None:
        """Parse an agent markdown file with YAML frontmatter.

        Returns:
            Tuple of (agent_name, SDKAgentDefinition) or None if parse fails.
        """
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            logger.warning(
                "Agent file missing frontmatter",
                plugin=plugin_name,
                file=agent_file.name,
            )
            return None

        metadata = yaml.safe_load(match.group(1))
        body = match.group(2).strip()

        agent_name = metadata.get("name", agent_file.stem)
        description = metadata.get("description", "")
        model = metadata.get("model", "sonnet")
        max_turns = metadata.get("max_turns", 100)
        tools_str = metadata.get("tools", "")
        tools = (
            [t.strip() for t in tools_str.split(",") if t.strip()]
            if tools_str
            else None
        )

        # Normalize model name
        normalized_model = MODEL_NORMALIZE_MAP.get(model.lower(), "sonnet")

        agent_def = SDKAgentDefinition(
            description=str(description) if description else "",
            prompt=body,
            tools=tools,
            model=normalized_model if normalized_model in ("sonnet", "opus", "haiku") else None,
        )
        # Store max_turns as an attribute (SDK may not have this field)
        agent_def.max_turns = max_turns  # type: ignore[attr-defined]

        return agent_name, agent_def

    def _load_plugin_skills(self, plugin: Plugin) -> None:
        """Load skill definitions from a plugin."""
        if not plugin.manifest.skills:
            return

        for skill_rel_path in plugin.manifest.skills:
            skills_dir = plugin.path / skill_rel_path.lstrip("./")

            if not skills_dir.exists():
                continue

            for skill_path in skills_dir.glob("*/SKILL.md"):
                skill_name = skill_path.parent.name
                namespaced_key = f"{plugin.name}:{skill_name}"

                self._skills[namespaced_key] = {
                    "source": "plugin",
                    "plugin": plugin.name,
                    "path": str(skill_path),
                }

                logger.debug(
                    "Loaded plugin skill",
                    plugin=plugin.name,
                    skill=skill_name,
                    key=namespaced_key,
                )

    def _load_plugin_commands(self, plugin: Plugin) -> None:
        """Load command definitions from a plugin."""
        if not plugin.manifest.commands:
            return

        for cmd_rel_path in plugin.manifest.commands:
            commands_dir = plugin.path / cmd_rel_path.lstrip("./")

            if not commands_dir.exists():
                continue

            for cmd_file in commands_dir.glob("*.md"):
                try:
                    content = cmd_file.read_text()
                    cmd = self._parse_command_file(content, plugin.name, cmd_file)

                    if cmd:
                        self._commands[cmd.name] = cmd

                        logger.debug(
                            "Loaded plugin command",
                            plugin=plugin.name,
                            command=cmd.name,
                        )

                except Exception as e:
                    logger.warning(
                        "Failed to load plugin command",
                        plugin=plugin.name,
                        file=cmd_file.name,
                        error=str(e),
                    )

    def _parse_command_file(
        self, content: str, plugin_name: str, cmd_file: Path
    ) -> PluginCommand | None:
        """Parse a command markdown file with YAML frontmatter.

        Command file format:
        ---
        description: Create a new agent definition
        allowed-tools: Read, Write, Edit
        argument-hint: <agent-type>
        ---

        Create a new agent of type $1...
        """
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            # Commands without frontmatter: use file content as-is
            cmd_name = cmd_file.stem
            return PluginCommand(
                name=f"{plugin_name}:{cmd_name}",
                description="",
                content=content.strip(),
                plugin_name=plugin_name,
            )

        metadata = yaml.safe_load(match.group(1))
        body = match.group(2).strip()

        cmd_name = metadata.get("name", cmd_file.stem)
        description = metadata.get("description", "")
        allowed_tools_str = metadata.get("allowed-tools", "")
        allowed_tools = (
            [t.strip() for t in allowed_tools_str.split(",") if t.strip()]
            if allowed_tools_str
            else None
        )
        argument_hint = metadata.get("argument-hint")
        model = metadata.get("model")

        return PluginCommand(
            name=f"{plugin_name}:{cmd_name}",
            description=str(description) if description else "",
            content=body,
            plugin_name=plugin_name,
            allowed_tools=allowed_tools,
            argument_hint=argument_hint,
            model=model,
        )

    def _load_plugin_hooks(self, plugin: Plugin) -> None:
        """Load hook definitions from a plugin."""
        if not plugin.manifest.hooks:
            return

        for hook_rel_path in plugin.manifest.hooks:
            hooks_path = plugin.path / hook_rel_path.lstrip("./")

            # Handle both directory and file paths
            if hooks_path.is_dir():
                # Look for settings.json or hooks.json in directory
                for hooks_file in ["settings.json", "hooks.json"]:
                    hooks_config_path = hooks_path / hooks_file
                    if hooks_config_path.exists():
                        self._parse_hooks_config(hooks_config_path, plugin.name)
            elif hooks_path.exists() and hooks_path.suffix == ".json":
                self._parse_hooks_config(hooks_path, plugin.name)

    def _parse_hooks_config(self, config_path: Path, plugin_name: str) -> None:
        """Parse a hooks configuration JSON file.

        Hook config format:
        {
          "hooks": {
            "PostToolUse": [{
              "matcher": {"tool_name": "Write", "file_path": "*.py"},
              "command": "ruff check --fix $FILE"
            }]
          }
        }
        """
        try:
            config = json.loads(config_path.read_text())
            hooks_data = config.get("hooks", {})

            for event_name, handlers in hooks_data.items():
                try:
                    hook_event = HookEvent(event_name)
                except ValueError:
                    logger.warning(
                        "Unknown hook event type",
                        plugin=plugin_name,
                        hook_event=event_name,
                    )
                    continue

                for handler in handlers:
                    if isinstance(handler, dict) and "command" in handler:
                        hook = PluginHook(
                            event=hook_event,
                            command=handler["command"],
                            plugin_name=plugin_name,
                            matcher=handler.get("matcher"),
                            timeout=handler.get("timeout", 30),
                        )
                        self._hooks.append(hook)

                        logger.debug(
                            "Loaded plugin hook",
                            plugin=plugin_name,
                            hook_event=event_name,
                            command=handler["command"][:50],
                        )

        except Exception as e:
            logger.warning(
                "Failed to parse hooks config",
                plugin=plugin_name,
                path=str(config_path),
                error=str(e),
            )

    def _load_plugin_mcp(self, plugin: Plugin) -> None:
        """Load MCP server configuration from a plugin."""
        if not plugin.manifest.mcp:
            return

        mcp_path = plugin.path / plugin.manifest.mcp.lstrip("./")

        if mcp_path.exists():
            self._mcp_configs.append(mcp_path)
            logger.debug(
                "Found plugin MCP config",
                plugin=plugin.name,
                path=str(mcp_path),
            )

    # Public accessor methods

    def get_all_agents(self) -> dict[str, SDKAgentDefinition]:
        """Get all loaded plugin agents.

        Returns:
            Dict mapping namespaced agent names to SDK AgentDefinition objects.
        """
        if self.use_sdk_only:
            return {}
        return self._agents.copy()

    def get_all_skills(self) -> dict[str, dict[str, str]]:
        """Get all loaded plugin skills.

        Returns:
            Dict mapping namespaced skill names to metadata dicts.
        """
        return self._skills.copy()

    def get_all_commands(self) -> dict[str, PluginCommand]:
        """Get all loaded plugin commands.

        Returns:
            Dict mapping namespaced command names to PluginCommand objects.
        """
        return self._commands.copy()

    def get_all_hooks(self) -> list[PluginHook]:
        """Get all loaded plugin hooks.

        Returns:
            List of PluginHook objects.
        """
        return self._hooks.copy()

    def get_mcp_configs(self) -> list[Path]:
        """Get paths to all plugin MCP configuration files.

        Returns:
            List of Path objects to .mcp.json files.
        """
        return self._mcp_configs.copy()

    def get_plugins(self) -> dict[str, Plugin]:
        """Get all discovered plugins.

        Returns:
            Dict mapping plugin names to Plugin objects.
        """
        return self._plugins.copy()

    def get_plugin_paths(self) -> list[dict[str, str]]:
        """Get plugin paths in SDK format.

        Returns:
            List of plugin path dicts for ClaudeAgentOptions.plugins
        """
        return [
            {"type": "local", "path": str(plugin.path)}
            for plugin in self._plugins.values()
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all loaded resources.

        Returns:
            Dict with counts and names of all resources.
        """
        return {
            "plugins": list(self._plugins.keys()),
            "agents": list(self._agents.keys()),
            "skills": list(self._skills.keys()),
            "commands": list(self._commands.keys()),
            "hooks_count": len(self._hooks),
            "mcp_configs_count": len(self._mcp_configs),
            "use_sdk_only": self.use_sdk_only,
        }
