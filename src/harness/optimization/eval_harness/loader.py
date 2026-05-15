"""Eval-suite YAML loader (Phase A.4).

Reads a YAML document conforming to ``eval_suite.schema.json``, validates
it via Draft-07, and returns a typed :class:`EvalSuite` with graders
already constructed via :func:`harness.optimization.graders.build_grader`.

Validation is fail-fast: any schema violation raises
:class:`EvalSuiteValidationError` with the path to the offending field
included, so the eval-architect agent's output gets surfaced
immediately rather than silently degrading.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError

from harness.optimization.eval_harness.models import (
    EvalConfig,
    EvalSuite,
    ScenarioWithGraders,
)
from harness.optimization.graders import (
    EvalScenario,
    ScenarioSetup,
    SetupFile,
    build_grader,
)

# Resolve schema path relative to repo layout: this file lives at
# src/harness/optimization/eval_harness/loader.py — the schema is at
# src/harness/plugins/cgf-agents/schemas/eval_suite.schema.json.
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "cgf-agents"
    / "schemas"
    / "eval_suite.schema.json"
)


class EvalSuiteValidationError(ValueError):
    """Raised when an eval-suite YAML doesn't conform to the schema."""


def load_eval_suite(path: str | Path) -> EvalSuite:
    """Load and validate an eval-suite YAML document.

    Args:
        path: Path to the YAML file.

    Returns:
        Fully-typed :class:`EvalSuite` with graders constructed.

    Raises:
        FileNotFoundError: When ``path`` doesn't exist.
        EvalSuiteValidationError: When the document fails schema validation
            or refers to an unknown grader/assertion type.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Eval suite not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw_doc = yaml.safe_load(raw_text)
    if not isinstance(raw_doc, dict):
        raise EvalSuiteValidationError(
            f"Eval suite must be a YAML mapping at top level, got {type(raw_doc).__name__}"
        )

    _validate_against_schema(raw_doc)

    try:
        return _build_suite(raw_doc)
    except (KeyError, ValueError) as exc:
        # build_grader / dataclass construction can raise on edge cases
        # the schema doesn't cover (e.g., regex compile error in tests).
        raise EvalSuiteValidationError(
            f"Failed to construct EvalSuite from {path}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _validate_against_schema(doc: dict[str, Any]) -> None:
    """Run Draft-07 validation; raise EvalSuiteValidationError on first
    failure with a JSON-pointer-ish path to the offending field."""
    with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    try:
        validator.validate(doc)
    except ValidationError as exc:
        location = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise EvalSuiteValidationError(
            f"Schema violation at {location}: {exc.message}"
        ) from exc


def _build_suite(doc: dict[str, Any]) -> EvalSuite:
    config = _build_config(doc.get("config") or {})
    scenarios = [_build_scenario(s) for s in doc["scenarios"]]
    return EvalSuite(
        version=str(doc["version"]),
        target_resource=str(doc["target_resource"]),
        scenarios=scenarios,
        config=config,
        description=str(doc.get("description") or ""),
        metadata=dict(doc.get("metadata") or {}),
    )


def _build_config(raw: dict[str, Any]) -> EvalConfig:
    return EvalConfig(
        trials_per_scenario=int(raw.get("trials_per_scenario", 3)),
        timeout_seconds=int(raw.get("timeout_seconds", 300)),
        eval_model=str(raw.get("eval_model", "claude-opus-4-5-20250929")),
        token_budget=(
            int(raw["token_budget"]) if "token_budget" in raw else None
        ),
        held_out_fraction=float(raw.get("held_out_fraction", 0.25)),
    )


def _build_scenario(raw: dict[str, Any]) -> ScenarioWithGraders:
    setup = _build_setup(raw.get("setup") or {})
    scenario = EvalScenario(
        id=raw["id"],
        level=raw["level"],
        prompt=raw["prompt"],
        target_resource=raw.get("target_resource"),
        description=str(raw.get("description") or ""),
        setup=setup,
        tags=list(raw.get("tags") or []),
        held_out=bool(raw.get("held_out", False)),
        difficulty=raw.get("difficulty"),
        cost_gate_exempt=bool(raw.get("cost_gate_exempt", False)),
    )
    graders = [build_grader(spec) for spec in raw["graders"]]
    return ScenarioWithGraders(scenario=scenario, graders=graders)


def _build_setup(raw: dict[str, Any]) -> ScenarioSetup:
    files = [
        SetupFile(path=str(f["path"]), content=str(f["content"]))
        for f in raw.get("files") or []
    ]
    env = {str(k): str(v) for k, v in (raw.get("env") or {}).items()}
    return ScenarioSetup(files=files, env=env)
