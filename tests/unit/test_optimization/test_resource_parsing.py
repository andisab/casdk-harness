"""Unit tests for ``_parse_resource_file`` — the YAML frontmatter parser
the eval harness uses to extract ``model``, ``tools``, ``max_turns``,
and the system prompt body from a resource markdown file.

Phase A refinement (post-cgf-eval-ab review): the parser must accept
``tools:`` in either of two conventional forms:

- YAML sequence (the canonical Anthropic-plugin / CGF form)::

    tools:
      - Read
      - Grep
      - Bash(git:*, terraform:*)

- Comma-separated string (legacy form)::

    tools: Read, Grep, Bash

The pre-fix code only handled comma-strings, so list-form ``tools:``
silently parsed to ``None`` → ``allowed_tools=[]`` in the SDK call →
the agent had no tools and every iac-team scenario scored 0/0,
tripping the F21 unwinnable detector across every resource.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.optimization.eval_harness.runner import _parse_resource_file

# ---------------------------------------------------------------------------
# tools: parsing
# ---------------------------------------------------------------------------


class TestToolsFrontmatterParsing:
    """``tools:`` accepts list, comma-string, or absent forms."""

    def test_yaml_list_form_parsed(self, tmp_path: Path) -> None:
        """The conventional CGF / Anthropic-plugin form: YAML sequence.

        This is the form used by every iac-team agent and most
        marketplace plugins.  Pre-fix this returned ``None``.
        """
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: iac-analyzer\n"
            "model: sonnet\n"
            "tools:\n"
            "  - Read\n"
            "  - Grep\n"
            "  - Glob\n"
            "  - Bash(git:*, terraform:*, kubectl:*)\n"
            "---\n"
            "Body content.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] == [
            "Read",
            "Grep",
            "Glob",
            "Bash(git:*, terraform:*, kubectl:*)",
        ]

    def test_comma_string_form_parsed(self, tmp_path: Path) -> None:
        """The legacy form: comma-separated string."""
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: legacy-agent\n"
            "model: sonnet\n"
            "tools: Read, Write, Bash\n"
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] == ["Read", "Write", "Bash"]

    def test_absent_tools_returns_none(self, tmp_path: Path) -> None:
        """A skill or agent with no ``tools:`` key → ``None`` (no
        restriction). Downstream ``_invoke_from_resource`` translates
        ``None`` to ``[]`` for the SDK (per F10)."""
        f = tmp_path / "skill.md"
        f.write_text(
            "---\n"
            "name: bare-skill\n"
            "model: sonnet\n"
            "---\n"
            "Skill body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] is None

    def test_empty_string_tools_returns_none(self, tmp_path: Path) -> None:
        """``tools: ""`` (empty string) is treated identically to absent."""
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: empty-tools\n"
            "model: sonnet\n"
            'tools: ""\n'
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] is None

    def test_empty_list_tools_returns_none(self, tmp_path: Path) -> None:
        """``tools: []`` collapses to ``None`` so the downstream caller
        treats it identically to "no tools declared" (no surprise empty
        list propagating into the SDK options diff)."""
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: empty-list-tools\n"
            "model: sonnet\n"
            "tools: []\n"
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] is None

    def test_list_form_strips_whitespace_and_drops_blanks(
        self, tmp_path: Path
    ) -> None:
        """Whitespace-only entries should be filtered (e.g., a trailing
        ``- `` from a hand-edited file), not silently kept as the empty
        string."""
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: padded-tools\n"
            "model: sonnet\n"
            "tools:\n"
            '  - "  Read  "\n'
            '  - ""\n'
            "  - Grep\n"
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] == ["Read", "Grep"]

    def test_dict_form_falls_back_to_none(self, tmp_path: Path) -> None:
        """Defensive: an unexpected dict shape (rare but possible) must
        not crash; fall through to ``None`` so the SDK call still
        composes."""
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: dict-tools\n"
            "model: sonnet\n"
            "tools:\n"
            "  Read: true\n"
            "  Bash: false\n"
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["tools"] is None


# ---------------------------------------------------------------------------
# Other frontmatter fields — light coverage to pin the contract
# ---------------------------------------------------------------------------


class TestOtherFrontmatterFields:
    """Sanity coverage for the other fields ``_parse_resource_file`` returns."""

    def test_no_frontmatter_uses_whole_file_as_prompt(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "raw.md"
        body = "Just a plain markdown body, no frontmatter."
        f.write_text(body, encoding="utf-8")
        spec = _parse_resource_file(f)
        assert spec["name"] == "raw"
        assert spec["model"] == "sonnet"
        assert spec["tools"] is None
        assert spec["max_turns"] == 100
        assert spec["prompt"] == body

    def test_invalid_model_falls_back_to_sonnet(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text(
            "---\n"
            "name: typo\n"
            "model: gpt-4\n"
            "---\n"
            "Body.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["model"] == "sonnet"

    @pytest.mark.parametrize("model_in,expected", [
        ("sonnet", "sonnet"),
        ("opus", "opus"),
        ("haiku", "haiku"),
        ("Sonnet", "sonnet"),  # case insensitive
        ("opus 4.1", "opus"),  # space-stripped
    ])
    def test_model_normalization(
        self, tmp_path: Path, model_in: str, expected: str
    ) -> None:
        f = tmp_path / "agent.md"
        f.write_text(
            f"---\nname: m\nmodel: {model_in}\n---\nBody.\n",
            encoding="utf-8",
        )
        spec = _parse_resource_file(f)
        assert spec["model"] == expected
