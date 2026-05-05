#!/usr/bin/env python3
"""Synthesize per-plugin .claude-plugin/plugin.json shims as a fallback.

As of swe-marketplace 2026-05-05, each plugin in the marketplace ships
its own ``<plugin>/.claude-plugin/plugin.json`` file directly — so most
modern marketplace clones don't need synthesis at all. This script
remains as a fallback for older marketplace pins that predate that
change, and for any custom marketplace that ships only a top-level
``.claude-plugin/marketplace.json``.

Behavior:

- For each plugin entry in ``marketplace.json``, check if the plugin
  directory already has a ``.claude-plugin/plugin.json``. If yes,
  **skip** — the upstream-shipped manifest wins.
- Only synthesize for plugins that lack a manifest. Lift the marketplace
  entry verbatim (minus marketplace-only fields ``source`` /
  ``category`` / ``strict``) into the per-plugin path.

This is intentionally lossless: the harness's own ``PluginManager``
walks plugin directories directly and doesn't depend on these
manifests, so the only consumer that sees them is the SDK CLI. Keeping
this script additive ensures upstream-shipped manifests aren't
clobbered by an older synthesis output.

Usage:
    python3 scripts/synthesize_marketplace_manifests.py <marketplace_root>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# Fields the marketplace uses internally that are not part of the per-plugin
# plugin.json schema. Strip them when synthesizing a shim.
_MARKETPLACE_ONLY_FIELDS = {"source", "category", "strict"}


def synthesize(marketplace_root: Path) -> int:
    manifest_file = marketplace_root / ".claude-plugin" / "marketplace.json"
    if not manifest_file.exists():
        print(f"error: marketplace.json not found at {manifest_file}", file=sys.stderr)
        return 1

    data = json.loads(manifest_file.read_text())
    plugins = data.get("plugins", [])
    written = 0
    skipped = 0

    for entry in plugins:
        name = entry.get("name")
        if not name:
            continue
        source = entry.get("source", f"./plugins/{name}")

        plugin_dir = (marketplace_root / source.lstrip("./")).resolve()
        if not plugin_dir.is_dir():
            print(f"warn: plugin source missing for '{name}' at {plugin_dir}", file=sys.stderr)
            continue

        out = plugin_dir / ".claude-plugin" / "plugin.json"
        if out.exists():
            # Upstream-shipped manifest wins — never overwrite it.
            skipped += 1
            continue

        shim = {k: v for k, v in entry.items() if k not in _MARKETPLACE_ONLY_FIELDS}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(shim, indent=2) + "\n")
        written += 1

    print(
        f"Synthesized {written} plugin.json shim(s) in {marketplace_root}; "
        f"skipped {skipped} (already shipped upstream)."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: synthesize_marketplace_manifests.py <marketplace_root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(synthesize(Path(sys.argv[1])))
