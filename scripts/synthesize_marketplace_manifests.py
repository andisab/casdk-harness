#!/usr/bin/env python3
"""Synthesize per-plugin .claude-plugin/plugin.json shims from a marketplace.json.

The swe-marketplace stores its plugin metadata in a single top-level
``.claude-plugin/marketplace.json``; individual plugin directories don't ship a
per-plugin manifest. The harness's ``PluginManager`` (pre-Phase-2 collapse)
expects ``<plugin>/.claude-plugin/plugin.json`` per plugin, so we synthesize
shim manifests after sync to bridge the gap.

This script is intentionally side-effect-only on the local clone (under
``.plugins/`` or ``/opt/plugins/``); it never writes inside the harness repo.

Usage:
    python3 scripts/synthesize_marketplace_manifests.py <marketplace_root>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def synthesize(marketplace_root: Path) -> int:
    manifest_file = marketplace_root / ".claude-plugin" / "marketplace.json"
    if not manifest_file.exists():
        print(f"error: marketplace.json not found at {manifest_file}", file=sys.stderr)
        return 1

    data = json.loads(manifest_file.read_text())
    plugins = data.get("plugins", [])
    written = 0

    for entry in plugins:
        name = entry.get("name")
        source = entry.get("source", f"./plugins/{name}")
        if not name:
            continue

        plugin_dir = (marketplace_root / source.lstrip("./")).resolve()
        if not plugin_dir.is_dir():
            print(f"warn: plugin source missing for '{name}' at {plugin_dir}", file=sys.stderr)
            continue

        shim = {
            "name": name,
            "version": entry.get("version", "0.0.0"),
            "description": entry.get("description", ""),
            "agents": entry.get("agents", []),
            "skills": entry.get("skills", []),
            "commands": entry.get("commands", []),
            "hooks": entry.get("hooks", []),
        }
        author = entry.get("author")
        if isinstance(author, dict) and author.get("name"):
            shim["author"] = author["name"]

        out = plugin_dir / ".claude-plugin" / "plugin.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(shim, indent=2) + "\n")
        written += 1

    print(f"Synthesized {written} plugin.json shim(s) in {marketplace_root}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: synthesize_marketplace_manifests.py <marketplace_root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(synthesize(Path(sys.argv[1])))
