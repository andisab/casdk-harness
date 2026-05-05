"""De-risk script: minimal SDK plugin loading probe.

Bypasses the harness entirely to isolate whether the SDK's `plugins=`
field actually surfaces plugin agents/skills/commands to runtime
consumers. Configurable via env vars so we can run all three de-risk
tests without editing the script.

Usage (inside the container):

    DERISK_AGENTS_WORKAROUND=0 \
    DERISK_SETTING_SOURCES=project \
    DERISK_USE_PLUGINS=1 \
    DERISK_PROBE=task:cgf-agents:cgf-orchestrator \
    python /tmp/derisk_plugin_loading.py

Environment variables:
    DERISK_AGENTS_WORKAROUND: "1" registers plugin agents via agents=.
                              "0" leaves agents= empty (test the SDK).
    DERISK_SETTING_SOURCES:   comma-separated; e.g. "project" or "user,project".
                              Default: "project" (matches harness).
    DERISK_USE_PLUGINS:       "1" passes plugins=[<paths>]. "0" skips it
                              (test 3, install-flow comparison).
    DERISK_PROBE:             one of:
                                "task:<subagent_type>" — Task dispatch test
                                "skill:<plugin>:<skill>" — Skill tool test
                                "command:<slash-command>" — slash command test

Output: prints all received messages then a one-line VERDICT line.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import yaml
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AgentDefinition as SDKAgentDefinition

# Plugin source paths (mirrors harness's resolution)
MARKETPLACE = Path("/opt/plugins/swe-marketplace/plugins")
IN_TREE = Path("/app/src/harness/plugins")


def discover_plugin_paths() -> list[dict]:
    """Mimic the harness's plugin discovery to build the plugins= list."""
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


def parse_plugin_agents(plugin_paths: list[dict]) -> dict[str, SDKAgentDefinition]:
    """Mimic the harness's plugin-agent registration via agents=."""
    agents: dict[str, SDKAgentDefinition] = {}
    for entry in plugin_paths:
        plugin_path = Path(entry["path"])
        manifest = json.loads((plugin_path / ".claude-plugin" / "plugin.json").read_text())
        plugin_name = manifest.get("name", plugin_path.name)
        agents_dir = plugin_path / "agents"
        if not agents_dir.is_dir():
            continue
        for agent_file in sorted(agents_dir.glob("*.md")):
            content = agent_file.read_text()
            if not content.lstrip().startswith("---"):
                continue
            _, frontmatter, body = content.split("---", 2)
            meta = yaml.safe_load(frontmatter) or {}
            name = meta.get("name", agent_file.stem)
            model = str(meta.get("model") or "sonnet").lower().split()[0]
            if model not in ("sonnet", "opus", "haiku"):
                model = "sonnet"
            agents[f"{plugin_name}:{name}"] = SDKAgentDefinition(
                description=str(meta.get("description") or ""),
                prompt=body.strip(),
                tools=None,
                model=model,
            )
    return agents


def build_prompt(probe: str) -> str:
    if probe.startswith("task:"):
        subagent = probe.removeprefix("task:")
        return (
            f"Use the Task tool with subagent_type \"{subagent}\" "
            f"and prompt \"reply with exactly: hello from {subagent}\". "
            f"Don't do anything else."
        )
    if probe.startswith("skill:"):
        skill = probe.removeprefix("skill:")
        return f"Use the {skill} skill with args 'one-line description please'."
    if probe.startswith("command:"):
        return probe.removeprefix("command:")
    raise ValueError(f"Unknown probe form: {probe}")


async def main() -> int:
    workaround_on = os.environ.get("DERISK_AGENTS_WORKAROUND", "1") == "1"
    setting_sources_env = os.environ.get("DERISK_SETTING_SOURCES", "project")
    setting_sources = [s.strip() for s in setting_sources_env.split(",") if s.strip()]
    use_plugins = os.environ.get("DERISK_USE_PLUGINS", "1") == "1"
    probe = os.environ["DERISK_PROBE"]

    plugin_paths = discover_plugin_paths() if use_plugins else []
    workaround_agents = parse_plugin_agents(plugin_paths) if workaround_on else {}

    print(f"=== Probe: {probe}")
    print(f"=== plugins=          {[p['path'] for p in plugin_paths]}")
    print(f"=== agents= count:    {len(workaround_agents)} (workaround_on={workaround_on})")
    print(f"=== setting_sources=  {setting_sources}")
    print()

    options = ClaudeAgentOptions(
        plugins=plugin_paths,
        agents=workaround_agents,
        setting_sources=setting_sources,
        allowed_tools=["Read", "Bash", "Task", "Skill"],
        skills="all",
        model="claude-sonnet-4-5-20250929",
        cwd="/app",
        permission_mode="acceptEdits",
        system_prompt="You are a test probe. Follow instructions literally.",
    )

    prompt = build_prompt(probe)
    print(f"=== prompt: {prompt}")
    print()

    success = False
    error_signal = None
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            t = type(msg).__name__
            r = repr(msg)
            print(f"[{t}] {r[:300]}")
            # Detect success / failure signals
            if "tool_use_error" in r or "Unknown agent" in r or "Unknown skill" in r:
                error_signal = "tool_use_error"
            if t == "ResultMessage":
                # Inspect for zero-turn no-op (slash command silent failure)
                if "num_turns=0" in r and "is_error=False" in r:
                    error_signal = error_signal or "zero_turn_noop"
                else:
                    success = True

    print()
    if error_signal == "tool_use_error":
        print(f"VERDICT: FAIL ({probe}): tool_use_error — SDK rejected the resource")
        return 1
    if error_signal == "zero_turn_noop":
        print(f"VERDICT: SILENT_NOOP ({probe}): 0 turns, no error — slash command swallowed")
        return 2
    if success:
        print(f"VERDICT: PASS ({probe}): resource was reachable end-to-end")
        return 0
    print(f"VERDICT: AMBIGUOUS ({probe}): no clear success/failure signal — inspect log")
    return 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
