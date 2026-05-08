"""Tests for eval_suite.schema.json (CGF Stage 3 Phase A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError

# Schema file path: src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = (
    _REPO_ROOT
    / "src"
    / "harness"
    / "plugins"
    / "cgf-agents"
    / "schemas"
    / "eval_suite.schema.json"
)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    """Load the eval_suite JSON Schema from disk."""
    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft7Validator:
    """Build a Draft-07 validator. Verifies the schema itself is valid Draft-07."""
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def _minimal_suite() -> dict[str, Any]:
    """Smallest possible valid eval suite."""
    return {
        "version": "1.0",
        "target_resource": "agents/example.md",
        "config": {},
        "scenarios": [
            {
                "id": "smoke-1",
                "level": "unit",
                "prompt": "Say hello.",
                "graders": [{"type": "contains", "needle": "hello"}],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Schema-level tests
# ---------------------------------------------------------------------------


class TestSchemaItself:
    """The schema document itself must be valid Draft-07."""

    def test_schema_file_exists(self) -> None:
        assert _SCHEMA_PATH.exists(), f"Schema not found at {_SCHEMA_PATH}"

    def test_schema_is_valid_draft07(self, schema: dict[str, Any]) -> None:
        Draft7Validator.check_schema(schema)

    def test_schema_has_expected_top_level_required(
        self, schema: dict[str, Any]
    ) -> None:
        assert set(schema["required"]) == {
            "version",
            "target_resource",
            "scenarios",
            "config",
        }

    def test_schema_defines_all_grader_subtypes(
        self, schema: dict[str, Any]
    ) -> None:
        defs = schema["definitions"]
        assert "grader_exact" in defs
        assert "grader_contains" in defs
        assert "grader_regex" in defs
        assert "grader_code" in defs
        assert "grader_trajectory" in defs
        assert "grader_llm_judge" in defs
        assert "grader_composite" in defs

    def test_schema_defines_all_trajectory_assertion_subtypes(
        self, schema: dict[str, Any]
    ) -> None:
        defs = schema["definitions"]
        assert "trajectory_tool_called" in defs
        assert "trajectory_no_tool" in defs
        assert "trajectory_ordering" in defs
        assert "trajectory_constraint" in defs


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------


class TestValidSuites:
    def test_minimal_suite_validates(self, validator: Draft7Validator) -> None:
        validator.validate(_minimal_suite())

    def test_suite_with_full_config(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["config"] = {
            "trials_per_scenario": 5,
            "timeout_seconds": 600,
            "eval_model": "claude-opus-4-5-20250929",
            "token_budget": 2_000_000,
            "held_out_fraction": 0.3,
        }
        validator.validate(suite)

    def test_suite_with_all_simple_grader_types(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "exact", "expected": "hello world"},
            {"type": "contains", "needle": "world", "case_insensitive": True},
            {"type": "regex", "pattern": r"\d+", "flags": ["IGNORECASE"]},
            {"type": "code", "code": "assert 'x' in transcript.final_output"},
        ]
        validator.validate(suite)

    def test_trajectory_grader_with_all_assertion_kinds(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "trajectory",
                "assertions": [
                    {"kind": "tool_called", "tool": "Read", "min_count": 2},
                    {"kind": "no_tool", "tool": "Bash"},
                    {"kind": "ordering", "before": "Read", "after": "Write"},
                    {
                        "kind": "constraint",
                        "text": "Agent did not modify files outside /tmp",
                    },
                ],
            }
        ]
        validator.validate(suite)

    def test_llm_judge_grader_with_pairwise(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "llm_judge",
                "rubric": "Score 1-5 on technical accuracy and clarity.",
                "pass_threshold": 0.6,
                "eval_model": "claude-sonnet-4-5-20250929",
                "pairwise": True,
            }
        ]
        validator.validate(suite)

    def test_composite_grader_nesting(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "composite",
                "operator": "and",
                "graders": [
                    {"type": "contains", "needle": "ok"},
                    {
                        "type": "composite",
                        "operator": "or",
                        "graders": [
                            {"type": "regex", "pattern": "yes|no"},
                            {"type": "exact", "expected": "maybe"},
                        ],
                    },
                ],
            }
        ]
        validator.validate(suite)

    def test_held_out_scenario(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["held_out"] = True
        validator.validate(suite)

    def test_setup_with_files_and_env(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["setup"] = {
            "files": [
                {"path": "input.txt", "content": "hello"},
                {"path": "subdir/data.json", "content": "{}"},
            ],
            "env": {"FOO": "bar"},
        }
        validator.validate(suite)

    def test_all_scenario_levels(self, validator: Draft7Validator) -> None:
        for level in ("unit", "trajectory", "e2e"):
            suite = _minimal_suite()
            suite["scenarios"][0]["level"] = level
            validator.validate(suite)

    def test_difficulty_optional(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["difficulty"] = "hard"
        validator.validate(suite)


# ---------------------------------------------------------------------------
# Invalid documents — each captures one rule
# ---------------------------------------------------------------------------


class TestInvalidSuites:
    def test_missing_version_rejected(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        del suite["version"]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_missing_scenarios_rejected(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        del suite["scenarios"]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_empty_scenarios_rejected(self, validator: Draft7Validator) -> None:
        suite = _minimal_suite()
        suite["scenarios"] = []
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_invalid_version_format_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["version"] = "v1"
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_unknown_top_level_property_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["unexpected_field"] = "boom"
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_scenario_id_uppercase_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["id"] = "BadID"
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_scenario_invalid_level_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["level"] = "integration"
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_scenario_no_graders_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = []
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_grader_unknown_type_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [{"type": "ai_overlord", "data": "x"}]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_grader_extra_property_rejected(
        self, validator: Draft7Validator
    ) -> None:
        # Each grader subtype has additionalProperties: false
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "contains", "needle": "x", "extra_garbage": True}
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_exact_grader_missing_expected_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [{"type": "exact"}]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_regex_grader_invalid_flag_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "regex", "pattern": ".+", "flags": ["NOT_A_FLAG"]}
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_trajectory_grader_no_assertions_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "trajectory", "assertions": []}
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_trajectory_assertion_unknown_kind_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "trajectory",
                "assertions": [{"kind": "telepathy", "tool": "Read"}],
            }
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_llm_judge_threshold_out_of_range_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "llm_judge",
                "rubric": "Score it carefully.",
                "pass_threshold": 1.5,
            }
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_llm_judge_rubric_too_short_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "llm_judge", "rubric": "ok"}
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_composite_invalid_operator_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {
                "type": "composite",
                "operator": "xor",
                "graders": [{"type": "contains", "needle": "x"}],
            }
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_composite_empty_graders_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["graders"] = [
            {"type": "composite", "operator": "and", "graders": []}
        ]
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_setup_file_with_path_traversal_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["setup"] = {
            "files": [{"path": "../escape.txt", "content": "boom"}]
        }
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_setup_file_absolute_path_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["scenarios"][0]["setup"] = {
            "files": [{"path": "/etc/passwd", "content": "boom"}]
        }
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_config_trials_below_minimum_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["config"]["trials_per_scenario"] = 0
        with pytest.raises(ValidationError):
            validator.validate(suite)

    def test_config_extra_property_rejected(
        self, validator: Draft7Validator
    ) -> None:
        suite = _minimal_suite()
        suite["config"]["unknown"] = True
        with pytest.raises(ValidationError):
            validator.validate(suite)
