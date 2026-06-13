"""Unit tests for EVAL_DESIGN v2 sharding helpers (Phase A.5 L1.3).

Covers the pure functions in
``harness.optimization._orchestrator_phases.eval_design`` that the sharded
fan-out/merge relies on: slug derivation, the shard-prompt builder, the merge
that assembles per-resource shards into one suite, the best-effort purpose
loader, and the two env-knob resolvers. The LLM calls themselves are verified
out-of-band via ``scripts/derisk_eval_design.py``.
"""

from __future__ import annotations

from pathlib import Path

from harness.optimization._orchestrator_phases.eval_design import (
    _build_shard_prompt,
    _load_resource_purposes,
    _merge_shard_suites,
    _resolve_eval_design_concurrency,
    _resolve_shard_max_turns,
    _shard_slug,
)

# ---------------------------------------------------------------------------
# _shard_slug
# ---------------------------------------------------------------------------


class TestShardSlug:
    def test_nested_agent_path(self) -> None:
        assert _shard_slug("agents/iac-analyzer.md") == "agents-iac-analyzer"

    def test_skill_subdir_path(self) -> None:
        assert _shard_slug("skills/aws-eks/SKILL.md") == "skills-aws-eks-skill"

    def test_flat_command(self) -> None:
        assert _shard_slug("commands/c.md") == "commands-c"

    def test_distinct_resources_distinct_slugs(self) -> None:
        a = _shard_slug("skills/aws-eks/SKILL.md")
        b = _shard_slug("skills/gcp-gke/SKILL.md")
        assert a != b

    def test_empty_path_has_fallback(self) -> None:
        assert _shard_slug("") == "resource"

    def test_slug_is_filesystem_safe(self) -> None:
        slug = _shard_slug("mcp-servers/weird name (v2).py")
        # Only lowercase alnum + hyphen survive.
        assert all(c.islower() or c.isdigit() or c == "-" for c in slug)
        assert ".." not in slug and "/" not in slug


# ---------------------------------------------------------------------------
# _merge_shard_suites
# ---------------------------------------------------------------------------


def _shard(target: str, *scenario_ids: str) -> dict:
    return {
        "version": "1.0",
        "target_resource": target,
        "config": {"trials_per_scenario": 1},
        "scenarios": [
            {
                "id": sid,
                "level": "unit",
                "prompt": "p",
                "graders": [{"type": "contains", "needle": "x"}],
            }
            for sid in scenario_ids
        ],
    }


class TestMergeShardSuites:
    def test_stamps_target_resource_per_scenario(self) -> None:
        shards = [
            ("agents/a.md", _shard("agents/a.md", "easy-a-01")),
            ("skills/b/SKILL.md", _shard("skills/b/SKILL.md", "easy-b-01")),
        ]
        merged = _merge_shard_suites(shards, source_resource_count=2)
        by_id = {s["id"]: s for s in merged["scenarios"]}
        # Every scenario carries its OWN shard's target, not the merged
        # top-level (which can only name the first resource).
        assert by_id["easy-a-01"]["target_resource"] == "agents/a.md"
        assert by_id["easy-b-01"]["target_resource"] == "skills/b/SKILL.md"

    def test_top_level_target_is_first_shard(self) -> None:
        shards = [
            ("agents/a.md", _shard("agents/a.md", "s1")),
            ("agents/b.md", _shard("agents/b.md", "s2")),
        ]
        merged = _merge_shard_suites(shards, source_resource_count=2)
        assert merged["target_resource"] == "agents/a.md"

    def test_duplicate_ids_disambiguated(self) -> None:
        # Two shards both emit "easy-01" — the merge must keep both.
        shards = [
            ("agents/a.md", _shard("agents/a.md", "easy-01")),
            ("agents/b.md", _shard("agents/b.md", "easy-01")),
        ]
        merged = _merge_shard_suites(shards, source_resource_count=2)
        ids = [s["id"] for s in merged["scenarios"]]
        assert len(ids) == 2
        assert len(set(ids)) == 2  # no collision survived

    def test_malformed_scenarios_dropped(self) -> None:
        bad = {
            "version": "1.0",
            "target_resource": "agents/a.md",
            "scenarios": [
                "not-a-dict",
                {"level": "unit"},  # missing id + graders
                {"id": "no-graders"},  # missing graders
                {
                    "id": "good-01",
                    "graders": [{"type": "contains", "needle": "x"}],
                },
            ],
        }
        merged = _merge_shard_suites(
            [("agents/a.md", bad)], source_resource_count=1
        )
        ids = [s["id"] for s in merged["scenarios"]]
        assert ids == ["good-01"]

    def test_non_dict_shard_skipped(self) -> None:
        merged = _merge_shard_suites(
            [("agents/a.md", _shard("agents/a.md", "s1")), ("x.md", None)],  # type: ignore[list-item]
            source_resource_count=2,
        )
        assert len(merged["scenarios"]) == 1

    def test_metadata_records_shape(self) -> None:
        shards = [("agents/a.md", _shard("agents/a.md", "s1"))]
        merged = _merge_shard_suites(shards, source_resource_count=4)
        meta = merged["metadata"]
        assert meta["design_mode"] == "sharded"
        assert meta["shard_count"] == 1
        assert meta["source_resource_count"] == 4

    def test_config_is_canonical(self) -> None:
        # Shard configs may disagree; the merge synthesizes one canonical config.
        shards = [("agents/a.md", _shard("agents/a.md", "s1"))]
        merged = _merge_shard_suites(shards, source_resource_count=1)
        assert merged["config"]["trials_per_scenario"] == 1
        assert merged["config"]["held_out_fraction"] == 0.33

    def test_preserves_scenario_fields(self) -> None:
        shard = {
            "version": "1.0",
            "target_resource": "agents/a.md",
            "scenarios": [
                {
                    "id": "hard-01",
                    "level": "e2e",
                    "prompt": "do the thing",
                    "graders": [{"type": "llm_judge", "rubric": "r" * 12}],
                    "held_out": True,
                    "difficulty": "hard",
                }
            ],
        }
        merged = _merge_shard_suites(
            [("agents/a.md", shard)], source_resource_count=1
        )
        sc = merged["scenarios"][0]
        assert sc["held_out"] is True
        assert sc["difficulty"] == "hard"
        assert sc["graders"][0]["type"] == "llm_judge"


# ---------------------------------------------------------------------------
# _build_shard_prompt
# ---------------------------------------------------------------------------


class TestBuildShardPrompt:
    def _prompt(self, *, purpose: str = "Analyze IaC repos") -> str:
        return _build_shard_prompt(
            workspace="/workspace/iac",
            resource_path="agents/iac-analyzer.md",
            resource_type="agent",
            policy="CONTENT-ONLY (loaded as system prompt; no tool dispatch)",
            purpose=purpose,
            diff="@@ -1 +1 @@\n-old\n+new karpenter guidance",
            shard_path="/workspace/iac/eval/shards/agents-iac-analyzer.yaml",
            generated_path="/workspace/iac/agents/iac-analyzer.md",
            spec_path="/workspace/iac/SPEC.md",
            criteria_path="/workspace/iac/research/eval_criteria.yaml",
            plan_path="/workspace/iac/resource-plan.yaml",
        )

    def test_contains_resource_identity(self) -> None:
        p = self._prompt()
        assert "agents/iac-analyzer.md" in p
        assert "type: agent" in p

    def test_embeds_diff_inline(self) -> None:
        p = self._prompt()
        assert "+new karpenter guidance" in p

    def test_names_shard_output_path(self) -> None:
        p = self._prompt()
        assert "eval/shards/agents-iac-analyzer.yaml" in p

    def test_carries_grader_policy(self) -> None:
        p = self._prompt()
        assert "CONTENT-ONLY" in p

    def test_demands_discrimination_and_signal(self) -> None:
        p = self._prompt()
        assert "FAIL" in p  # discrimination mandate
        assert "[EVAL_DESIGN_COMPLETE]" in p

    def test_inlines_purpose_when_given(self) -> None:
        assert "Analyze IaC repos" in self._prompt(purpose="Analyze IaC repos")

    def test_purpose_fallback_when_empty(self) -> None:
        p = self._prompt(purpose="")
        assert "resource-plan.yaml" in p  # tells the architect where to look


# ---------------------------------------------------------------------------
# _load_resource_purposes
# ---------------------------------------------------------------------------


class TestLoadResourcePurposes:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _load_resource_purposes(tmp_path / "nope.yaml") == {}

    def test_parses_path_and_name_keys(self, tmp_path: Path) -> None:
        plan = tmp_path / "resource-plan.yaml"
        plan.write_text(
            "resources:\n"
            "  - path: agents/a.md\n"
            "    name: a\n"
            "    purpose: Does the A thing\n"
        )
        out = _load_resource_purposes(plan)
        assert out["agents/a.md"] == "Does the A thing"
        assert out["a"] == "Does the A thing"  # also keyed by name

    def test_description_and_role_fallbacks(self, tmp_path: Path) -> None:
        plan = tmp_path / "resource-plan.yaml"
        plan.write_text(
            "resources:\n"
            "  - path: x.md\n"
            "    description: from description\n"
            "  - path: y.md\n"
            "    role: from role\n"
        )
        out = _load_resource_purposes(plan)
        assert out["x.md"] == "from description"
        assert out["y.md"] == "from role"

    def test_non_dict_yaml_returns_empty(self, tmp_path: Path) -> None:
        plan = tmp_path / "resource-plan.yaml"
        plan.write_text("- just\n- a\n- list\n")
        assert _load_resource_purposes(plan) == {}

    def test_resources_not_a_list_returns_empty(self, tmp_path: Path) -> None:
        plan = tmp_path / "resource-plan.yaml"
        plan.write_text("resources: not-a-list\n")
        assert _load_resource_purposes(plan) == {}

    def test_entry_without_purpose_skipped(self, tmp_path: Path) -> None:
        plan = tmp_path / "resource-plan.yaml"
        plan.write_text("resources:\n  - path: a.md\n    type: agent\n")
        assert _load_resource_purposes(plan) == {}


# ---------------------------------------------------------------------------
# env-knob resolvers
# ---------------------------------------------------------------------------


class TestEnvResolvers:
    def test_concurrency_default(self, monkeypatch) -> None:
        monkeypatch.delenv("CGF_EVAL_DESIGN_CONCURRENCY", raising=False)
        assert _resolve_eval_design_concurrency() == 5

    def test_concurrency_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("CGF_EVAL_DESIGN_CONCURRENCY", "8")
        assert _resolve_eval_design_concurrency() == 8

    def test_concurrency_bad_value_falls_back(self, monkeypatch) -> None:
        monkeypatch.setenv("CGF_EVAL_DESIGN_CONCURRENCY", "not-a-number")
        assert _resolve_eval_design_concurrency() == 5

    def test_concurrency_clamped_to_at_least_one(self, monkeypatch) -> None:
        monkeypatch.setenv("CGF_EVAL_DESIGN_CONCURRENCY", "0")
        assert _resolve_eval_design_concurrency() == 1

    def test_shard_max_turns_default(self, monkeypatch) -> None:
        monkeypatch.delenv("CGF_EVAL_DESIGN_SHARD_MAX_TURNS", raising=False)
        assert _resolve_shard_max_turns() == 15

    def test_shard_max_turns_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("CGF_EVAL_DESIGN_SHARD_MAX_TURNS", "25")
        assert _resolve_shard_max_turns() == 25

    def test_shard_max_turns_bad_value_falls_back(self, monkeypatch) -> None:
        monkeypatch.setenv("CGF_EVAL_DESIGN_SHARD_MAX_TURNS", "")
        assert _resolve_shard_max_turns() == 15
