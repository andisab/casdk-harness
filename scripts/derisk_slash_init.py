"""De-risk add-on: inspect system/init.slash_commands list.

Anthropic's SDK doc says the system/init message lists the commands
available in the session. We never inspected that field. This script
opens a session and prints the entire slash_commands list so we can
see whether plugin-shipped slash commands (e.g. /cgf from cgf-agents)
are present or absent.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

MARKETPLACE = Path("/opt/plugins/swe-marketplace/plugins")
IN_TREE = Path("/app/src/harness/plugins")


def discover_plugin_paths() -> list[dict]:
    enabled = {"research-team", "context-engineering", "cgf-agents"}
    out: list[dict] = []
    for base in (MARKETPLACE, IN_TREE):
        if not base.exists():
            continue
        for plugin_dir in sorted(base.iterdir()):
            if not plugin_dir.is_dir():
                continue
            manifest = plugin_dir / ".claude-plugin" / "plugin.json"
            if not manifest.exists():
                continue
            name = json.loads(manifest.read_text()).get("name", plugin_dir.name)
            if name not in enabled:
                continue
            if any(p["path"].rstrip("/").endswith(plugin_dir.name) for p in out):
                continue
            out.append({"type": "local", "path": str(plugin_dir)})
    return out


async def main() -> int:
    options = ClaudeAgentOptions(
        plugins=discover_plugin_paths(),
        agents={},
        setting_sources=["project"],
        allowed_tools=["Read", "Bash", "Task", "Skill"],
        skills="all",
        model="claude-sonnet-4-5-20250929",
        cwd="/app",
        permission_mode="acceptEdits",
        system_prompt="You are a probe.",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("hi")
        async for msg in client.receive_response():
            if type(msg).__name__ == "SystemMessage":
                data = msg.data if hasattr(msg, "data") else {}
                if data.get("subtype") == "init":
                    slash_commands = data.get("slash_commands", [])
                    print(f"=== slash_commands list ({len(slash_commands)} entries):")
                    for cmd in sorted(slash_commands):
                        print(f"  {cmd}")
                    # Also look for cgf, research-team, context-engineering
                    for needle in ("/cgf", "/research", "/context-engineering",
                                   "cgf-agents", "research-team"):
                        hits = [c for c in slash_commands if needle in c]
                        if hits:
                            print(f"=== matches for '{needle}': {hits}")
                        else:
                            print(f"=== matches for '{needle}': NONE")
                    return 0
            if type(msg).__name__ == "ResultMessage":
                break
    return 0


if __name__ == "__main__":
    asyncio.run(main())
