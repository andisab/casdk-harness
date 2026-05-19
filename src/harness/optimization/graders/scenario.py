"""Eval scenario data model (CGF Stage 3 Phase A.3).

Scenarios are produced by ``cgf-eval-architect`` (in YAML conforming to
``schemas/eval_suite.schema.json``) and consumed by the ``EvalHarness``
in EXECUTION_EVAL.  Graders receive the scenario alongside the agent
transcript so they can refer to the prompt, expected behavior, and
metadata when computing their verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Three eval levels — see docs/CGF-EVAL-FRAMEWORK.md § 3.A.1.
ScenarioLevel = Literal["unit", "trajectory", "e2e"]
Difficulty = Literal["easy", "medium", "hard"]


@dataclass
class SetupFile:
    """A file to materialize in the scenario workspace before the prompt runs."""

    path: str
    content: str


@dataclass
class ScenarioSetup:
    """Workspace setup for a single scenario."""

    files: list[SetupFile] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class EvalScenario:
    """One eval scenario.

    Mirrors the per-scenario shape in ``eval_suite.schema.json`` minus the
    ``graders`` field — graders are constructed separately by the factory
    in ``graders/__init__.py`` and held by the harness, not the scenario
    itself, since a single scenario may be re-graded by multiple graders.
    """

    id: str
    level: ScenarioLevel
    prompt: str
    target_resource: str | None = None
    description: str = ""
    setup: ScenarioSetup = field(default_factory=ScenarioSetup)
    tags: list[str] = field(default_factory=list)
    held_out: bool = False
    difficulty: Difficulty | None = None
    # Phase A refinement 4.3: per-scenario opt-out from the cost gate.
    # The scenario still counts for the quality gate; only its cost is
    # excluded from the per-arm ``cost_per_success`` aggregate.  Intended
    # for scenarios where verbose chain-of-thought / tool-trace logging
    # is intentional (resource-type-level fallback was rejected as an
    # anti-pattern; opt in per-scenario only).
    cost_gate_exempt: bool = False
