"""Phase A refinement 4.2 — synthetic floor resource generator.

The floor "resource" is a bare-model variant of the candidate: same
``model`` / ``tools`` / ``max_turns`` in frontmatter, empty body.
This pins the build function's behaviour against the
``EvalHarness._invoke_from_resource`` contract (which parses YAML
frontmatter and uses the body as the system prompt).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from harness.optimization._orchestrator_phases._baseline_floor import (
    build_floor_resource,
)


def _read_floor(path: Path) -> tuple[dict, str]:
    """Helper: split a generated floor file into (frontmatter, body)."""
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        return {}, text
    _, frontmatter_raw, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter_raw) or {}
    return meta, body.strip()


class TestFrontmatterCases:
    def test_copies_invocation_fields(self, tmp_path: Path) -> None:
        """``name`` / ``model`` / ``tools`` / ``max_turns`` carry through —
        these are what the SDK uses for the bare-model invocation."""
        candidate = tmp_path / "agent.md"
        candidate.write_text(
            "---\n"
            "name: my-agent\n"
            "description: original description\n"
            "model: opus\n"
            "tools: Read, Bash\n"
            "max_turns: 50\n"
            "---\n\n"
            "You are a senior IaC architect.  Use Terraform 1.7+ idioms.",
            encoding="utf-8",
        )

        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        meta, body = _read_floor(floor_path)

        assert meta["name"] == "my-agent"
        assert meta["model"] == "opus"
        assert meta["tools"] == "Read, Bash"
        assert meta["max_turns"] == 50
        # Body is empty — that's the whole point.  Bare model invocation.
        assert body == ""

    def test_floor_marker_in_frontmatter(self, tmp_path: Path) -> None:
        """``_baseline: floor`` lets downstream tooling distinguish a
        floor resource from a regular one without path parsing."""
        candidate = tmp_path / "agent.md"
        candidate.write_text(
            "---\nname: x\nmodel: sonnet\n---\nbody", encoding="utf-8"
        )
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        meta, _ = _read_floor(floor_path)
        assert meta.get("_baseline") == "floor"

    def test_strips_non_invocation_fields(self, tmp_path: Path) -> None:
        """Anything outside the whitelist must NOT carry through —
        defends against accidental optimizer-side content leaks (e.g.,
        an ``optimization_history`` block in frontmatter)."""
        candidate = tmp_path / "agent.md"
        candidate.write_text(
            "---\n"
            "name: x\n"
            "model: sonnet\n"
            "optimization_history:\n"
            "  - v1: improved async\n"
            "  - v2: added error handling\n"
            "custom_metadata: leaky\n"
            "---\n\n"
            "body",
            encoding="utf-8",
        )
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        meta, _ = _read_floor(floor_path)
        assert "optimization_history" not in meta
        assert "custom_metadata" not in meta

    def test_partial_frontmatter_kept(self, tmp_path: Path) -> None:
        """Only ``name`` + ``model`` present — both should carry."""
        candidate = tmp_path / "skill.md"
        candidate.write_text(
            "---\nname: aws-cli\nmodel: haiku\n---\n# Skill body",
            encoding="utf-8",
        )
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        meta, body = _read_floor(floor_path)
        assert meta == {"name": "aws-cli", "model": "haiku", "_baseline": "floor"}
        assert body == ""


class TestEdgeCases:
    def test_no_frontmatter(self, tmp_path: Path) -> None:
        """Candidate has no frontmatter at all — the floor file is just
        empty.  ``_parse_resource_file`` will fall through to its
        no-frontmatter branch and use the default model."""
        candidate = tmp_path / "x.md"
        candidate.write_text("just a body, no frontmatter", encoding="utf-8")
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        assert floor_path.exists()
        assert floor_path.read_text() == ""

    def test_corrupt_frontmatter(self, tmp_path: Path) -> None:
        """YAML parse failure → degrade to empty file rather than guess."""
        candidate = tmp_path / "x.md"
        candidate.write_text(
            "---\nthis: is: not: valid: yaml:\n---\nbody",
            encoding="utf-8",
        )
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        assert floor_path.exists()
        # No frontmatter = empty body either way; both are valid SDK input.
        body = floor_path.read_text()
        assert "this:" not in body  # corrupt data did not pass through

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        """Nested output dirs are created on demand."""
        candidate = tmp_path / "x.md"
        candidate.write_text("---\nname: x\nmodel: sonnet\n---\nbody", encoding="utf-8")
        out = tmp_path / "deep" / "nested" / "floor"
        floor_path = build_floor_resource(candidate_path=candidate, output_dir=out)
        assert floor_path.parent == out
        assert floor_path.exists()

    def test_filename_pattern(self, tmp_path: Path) -> None:
        """Floor file name is ``{candidate_stem}-floor.md``."""
        candidate = tmp_path / "iac-analyzer-v3.md"
        candidate.write_text(
            "---\nname: iac\nmodel: sonnet\n---\nbody", encoding="utf-8"
        )
        floor_path = build_floor_resource(
            candidate_path=candidate, output_dir=tmp_path / "floor"
        )
        assert floor_path.name == "iac-analyzer-v3-floor.md"


# ---------------------------------------------------------------------------
# ResourceStatus.from_dict migration (last_promoted_version)
# ---------------------------------------------------------------------------
#
# Post-cgf-eval-ab fix: state files written before ``last_promoted_version``
# existed don't carry it.  On resume, an already-promoted resource must
# not be treated as if it had never been promoted — that would re-run
# the first-time-promotion floor arm, burning ~1 full eval per resource
# for no information gain.


class TestResourceStatusFromDictMigration:
    """``ResourceStatus.from_dict`` infers ``last_promoted_version`` when
    the field is missing from a legacy state file."""

    def test_explicit_value_wins(self) -> None:
        """Explicit ``last_promoted_version`` in the dict is honoured
        verbatim, even when it contradicts the inference rule."""
        from harness.progress import ResourceStatus

        # status=optimized + version=3 would infer 3; explicit 1 wins.
        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "optimized",
                "version": 3,
                "last_promoted_version": 1,
            }
        )
        assert r.last_promoted_version == 1

    def test_inferred_for_optimized_resource_when_missing(self) -> None:
        """Legacy state file: status=optimized, version=2, no
        last_promoted_version key.  Migration infers value=2."""
        from harness.progress import ResourceStatus

        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "optimized",
                "version": 2,
            }
        )
        assert r.last_promoted_version == 2

    def test_zero_for_pending_resource_when_missing(self) -> None:
        """Pending resource → 0 (never promoted)."""
        from harness.progress import ResourceStatus

        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "pending",
                "version": 0,
            }
        )
        assert r.last_promoted_version == 0

    def test_zero_for_needs_refinement_when_missing(self) -> None:
        """needs_refinement: tried but never promoted, so stay at 0.
        The floor arm SHOULD run on the next attempt — that's the
        whole point of the first-promotion gate."""
        from harness.progress import ResourceStatus

        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "needs_refinement",
                "version": 1,
            }
        )
        assert r.last_promoted_version == 0

    def test_zero_for_failed_when_missing(self) -> None:
        """failed: GENERATE aborted; never promoted."""
        from harness.progress import ResourceStatus

        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "failed",
                "version": 1,
            }
        )
        assert r.last_promoted_version == 0

    def test_explicit_zero_preserved(self) -> None:
        """Explicit 0 in the dict is preserved — distinct from "missing
        key" because new state files may legitimately write 0."""
        from harness.progress import ResourceStatus

        r = ResourceStatus.from_dict(
            {
                "path": "a.md",
                "resource_type": "agent",
                "status": "optimized",
                "version": 2,
                "last_promoted_version": 0,  # explicit, surprising, honoured
            }
        )
        assert r.last_promoted_version == 0
