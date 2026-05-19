"""Synthetic bare-model resource generator (Phase A refinement 4.2).

The "floor" baseline is the bare LLM — the same model the candidate
uses, but with no engineered system prompt.  The gate's first-promotion
stage checks that the candidate beats this floor by a margin; otherwise
the prompt engineering has net-negative value vs. doing nothing.

The floor "resource file" is synthetic — we never check it in.  Built
at runtime from the candidate's frontmatter so it inherits the same
``model``, ``tools``, and ``name`` but with an **empty system prompt
body**.  Materialized to a workspace tempdir so the EvalHarness can
parse it through its normal ``_parse_resource_file`` path with zero
special-case code.

Cache semantics: a floor result is valid for the lifetime of a
``(resource_path, CLAUDE_MODEL, spec_hash)`` triple.  We never re-run
the floor mid-branch because the model is the experimental control.
The cache is keyed in the orchestrator state, not here; this module
only produces the file.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def build_floor_resource(
    *,
    candidate_path: Path,
    output_dir: Path,
) -> Path:
    """Materialize a bare-model variant of ``candidate_path``.

    Reads YAML frontmatter from the candidate, copies ``name`` /
    ``description`` / ``model`` / ``tools`` / ``max_turns`` verbatim,
    and replaces the body with an empty string.  Writes the result to
    ``output_dir / f"{candidate_path.stem}-floor.md"`` and returns
    that path.

    The resulting file is a valid agent definition the SDK can invoke
    via ``EvalHarness._invoke_from_resource``; with no body, the SDK
    falls back to its default behavior — exactly what we want for the
    bare-model arm.

    When the candidate has no frontmatter (treated as "whole file is
    the prompt" by ``_parse_resource_file``), the floor variant has no
    frontmatter either; the body is just empty.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    text = candidate_path.read_text(encoding="utf-8")
    floor_path = output_dir / f"{candidate_path.stem}-floor.md"

    if not text.lstrip().startswith("---"):
        # No frontmatter — write a minimal file with empty body.  The
        # SDK invocation will fall back to model="sonnet" via
        # _parse_resource_file's no-frontmatter branch, which matches
        # what the candidate would do.  This is the rare path; most
        # CGF resources have frontmatter.
        floor_path.write_text("", encoding="utf-8")
        return floor_path

    try:
        _, frontmatter_raw, _body = text.split("---", 2)
        meta = yaml.safe_load(frontmatter_raw) or {}
    except (ValueError, yaml.YAMLError):
        # Corrupt frontmatter on the candidate — degrade to empty file
        # rather than guess.  Eval harness will surface the resulting
        # transcript anomaly.
        floor_path.write_text("", encoding="utf-8")
        return floor_path

    # Keep the keys that affect SDK invocation; strip anything else
    # that might inadvertently carry optimizer-side content (e.g., an
    # ``optimization_history`` block).  Whitelist over blacklist —
    # safer when frontmatter schema evolves.
    floor_meta = {
        k: meta[k]
        for k in ("name", "description", "model", "tools", "max_turns")
        if k in meta
    }
    # Tag the floor so downstream tooling can recognize it without
    # path-guessing.  Doesn't affect SDK behavior.
    floor_meta["_baseline"] = "floor"

    rendered = "---\n" + yaml.safe_dump(floor_meta, sort_keys=False) + "---\n\n"
    floor_path.write_text(rendered, encoding="utf-8")
    return floor_path
