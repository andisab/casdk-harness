"""Plugin discovery for the Claude Agent SDK Harness.

Walks plugin source directories (swe-marketplace clone + in-tree fallback),
applies the `ENABLED_PLUGINS` filter, and produces three things the harness
needs from plugins:

1. ``get_plugin_paths()`` — ``[{"type": "local", "path": ...}]`` entries fed
   to ``ClaudeAgentOptions.plugins`` so the SDK auto-loads each plugin's
   commands, hooks, skills, and MCP servers from disk.
2. ``get_all_agents()`` — namespaced ``plugin:agent`` → ``SDKAgentDefinition``
   map. Workaround for an SDK gap: passing a plugin via ``plugins=`` does not
   expose its agents to the Task tool with ``plugin:agent`` namespacing, so
   the harness still has to register them programmatically. Tracked upstream
   (see Block 3 Step 5 in plans/).
3. ``get_all_skills()`` — skill metadata (``source``/``path``) used by the
   CLI to render the SystemMessage banner. Skill *invocation* itself goes
   through the SDK Skill tool independently.

Manual command/hook discovery has been dropped — those are SDK responsibilities
now (REFACTOR.md Part 2 Phase 2). Plugin commands and hooks are SDK-auto-loaded
directly via ``plugins=`` and surfaced through the CLI; no harness-side type
or registry remains for either.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml
from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

logger = structlog.get_logger(__name__)


_VALID_MODELS = {"sonnet", "opus", "haiku"}


@dataclass
class DiscoveredPlugin:
    """A plugin directory that has been discovered and accepted by the filter."""

    name: str
    path: Path


class PluginManager:
    """Discovers plugins on disk and registers their agents.

    First-match-wins on duplicate plugin names across ``plugin_dirs``. Callers
    typically pass marketplace path first and the in-tree fallback last so a
    locally-edited plugin shadows the marketplace version.
    """

    def __init__(
        self,
        plugin_dirs: list[Path],
        enabled_plugins: list[str] | None = None,
    ) -> None:
        self.plugin_dirs = plugin_dirs
        self.enabled_plugins = enabled_plugins
        self._plugins: dict[str, DiscoveredPlugin] = {}
        self._agents: dict[str, SDKAgentDefinition] = {}
        self._skills: dict[str, dict[str, str]] = {}

    def discover(self) -> None:
        """Walk plugin_dirs, register accepted plugins' agents and skills."""
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            for plugin_path in sorted(plugin_dir.iterdir()):
                if not plugin_path.is_dir():
                    continue
                manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
                if not manifest_path.exists():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text())
                except Exception as exc:
                    logger.warning(
                        "Failed to parse plugin manifest",
                        path=str(manifest_path),
                        error=str(exc),
                    )
                    continue
                name = manifest.get("name", plugin_path.name)
                if self.enabled_plugins is not None and name not in self.enabled_plugins:
                    continue
                if name in self._plugins:
                    continue  # first plugin_dir wins
                self._plugins[name] = DiscoveredPlugin(name=name, path=plugin_path)
                self._register_agents(name, plugin_path)
                self._register_skills(name, plugin_path)

        logger.info(
            "Plugin discovery complete",
            plugins=list(self._plugins.keys()),
            agents=len(self._agents),
            skills=len(self._skills),
        )

    def _register_agents(self, plugin_name: str, plugin_path: Path) -> None:
        agents_dir = plugin_path / "agents"
        if not agents_dir.is_dir():
            return
        for agent_file in sorted(agents_dir.glob("*.md")):
            parsed = _parse_agent_file(agent_file)
            if parsed is None:
                continue
            agent_name, sdk_agent = parsed
            self._agents[f"{plugin_name}:{agent_name}"] = sdk_agent

    def _register_skills(self, plugin_name: str, plugin_path: Path) -> None:
        skills_dir = plugin_path / "skills"
        if not skills_dir.is_dir():
            return
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            self._skills[f"{plugin_name}:{skill_md.parent.name}"] = {
                "source": "plugin",
                "plugin": plugin_name,
                "path": str(skill_md),
            }

    def get_plugin_paths(self) -> list[dict[str, str]]:
        return [{"type": "local", "path": str(p.path)} for p in self._plugins.values()]

    def get_all_agents(self) -> dict[str, SDKAgentDefinition]:
        return dict(self._agents)

    def get_all_skills(self) -> dict[str, dict[str, str]]:
        return dict(self._skills)

    def get_plugin_names(self) -> list[str]:
        return list(self._plugins.keys())

    def get_summary(self) -> dict[str, Any]:
        return {
            "plugins": list(self._plugins.keys()),
            "agents": list(self._agents.keys()),
            "skills": list(self._skills.keys()),
        }


def _parse_agent_file(
    agent_file: Path,
) -> tuple[str, SDKAgentDefinition] | None:
    """Parse an agent markdown file with YAML frontmatter into an SDK agent."""
    try:
        content = agent_file.read_text()
    except Exception as exc:
        logger.warning("Failed to read agent file", file=str(agent_file), error=str(exc))
        return None
    if not content.lstrip().startswith("---"):
        logger.warning("Agent file missing frontmatter", file=str(agent_file))
        return None
    try:
        _, frontmatter, body = content.split("---", 2)
        meta = yaml.safe_load(frontmatter) or {}
    except Exception as exc:
        logger.warning(
            "Failed to parse agent frontmatter", file=str(agent_file), error=str(exc)
        )
        return None
    name = meta.get("name", agent_file.stem)
    description = str(meta.get("description") or "")
    model_raw = str(meta.get("model") or "sonnet").lower().split()[0]
    model = model_raw if model_raw in _VALID_MODELS else "sonnet"
    tools_raw = meta.get("tools") or ""
    tools = [t.strip() for t in tools_raw.split(",") if t.strip()] if tools_raw else None
    sdk_agent = SDKAgentDefinition(
        description=description,
        prompt=body.strip(),
        tools=tools,
        model=model,
    )
    max_turns = meta.get("max_turns")
    if max_turns is not None:
        sdk_agent.max_turns = max_turns  # type: ignore[attr-defined]
    return name, sdk_agent
