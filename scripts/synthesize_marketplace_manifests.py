#!/usr/bin/env python3
"""Synthesize per-plugin .claude-plugin/plugin.json shims from a marketplace.json.

The swe-marketplace stores its plugin metadata in a single top-level
``.claude-plugin/marketplace.json``; individual plugin directories don't ship a
per-plugin manifest. The Claude Code CLI (which loads plugins via
``--plugin-dir``) expects ``<plugin>/.claude-plugin/plugin.json`` per plugin,
so we lift each marketplace entry into a per-plugin shim after sync.

Each marketplace entry is already in the CLI's expected schema — agents and
skills as explicit file/sub-dir paths, author as an object, etc. We just strip
the marketplace-only ``source`` field and write the rest verbatim. This is
intentionally lossless: the harness's own ``PluginManager`` walks plugin
directories directly and ignores manifest fields, so any transformation here
would only risk breaking the CLI's stricter ``plugin validate`` schema.

Usage:
    python3 scripts/synthesize_marketplace_manifests.py <marketplace_root>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# Fields the marketplace uses internally that are not part of the per-plugin
# plugin.json schema. Strip them when synthesizing the shim.
_MARKETPLACE_ONLY_FIELDS = {"source", "category", "strict"}


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
        if not name:
            continue
        source = entry.get("source", f"./plugins/{name}")

        plugin_dir = (marketplace_root / source.lstrip("./")).resolve()
        if not plugin_dir.is_dir():
            print(f"warn: plugin source missing for '{name}' at {plugin_dir}", file=sys.stderr)
            continue

        shim = {k: v for k, v in entry.items() if k not in _MARKETPLACE_ONLY_FIELDS}

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
