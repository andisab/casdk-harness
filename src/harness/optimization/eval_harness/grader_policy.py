"""Grader-routing policy by resource ``eval_strategy`` (Phase A.5 A1).

Wires the previously-dead ``eval_strategy`` field
(``protocols/resource_types.py``) into eval-suite construction so each
resource type gets the graders that can actually discriminate it.

**Why this exists.** Content-type resources — skills, commands, hooks,
plugins, and *agent-definition* files — are evaluated as *content*: their
file is loaded as a system prompt and run via the SDK ``query()`` path,
they do NOT dispatch tools as a live sub-agent. So trajectory assertions
that check real tool calls (``tool_called`` / ``no_tool`` / ``ordering``)
resolve to 0/0 on *both* arms — the "structurally unwinnable" class that
sank ``agents/iac-generator`` in iac-team run #8 and ~5 resources in the
2026-05-26 mobile-dev run. Only resources that genuinely execute in the
eval runtime (``mcp_tool`` → ``executable``, ``mcp_server`` → ``server``)
may use tool-call assertions.

A trajectory ``constraint`` assertion is LLM-judged, not execution-based,
so it is permitted on content resources and is left untouched.

This module is pure (operates on the parsed eval-suite dict). The
resource-path → ``eval_strategy`` resolution lives at the call site
(``_orchestrator_phases/eval_design.py``) because it needs orchestrator
state; :func:`eval_strategy_from_path` provides a registry-derived
fallback for paths not present in state.
"""

from __future__ import annotations

from collections.abc import Callable

from harness.optimization.protocols.resource_types import (
    ResourceType,
    ResourceTypeRegistry,
)

__all__ = [
    "EXECUTION_STRATEGIES",
    "EXECUTION_ASSERTION_KINDS",
    "is_execution_strategy",
    "policy_summary",
    "eval_strategy_from_path",
    "fallback_llm_judge",
    "enforce_suite",
]

# ``eval_strategy`` values whose resources run tools during eval. Only these
# may carry execution-dependent trajectory assertions.
EXECUTION_STRATEGIES: frozenset[str] = frozenset({"executable", "server"})

# Trajectory assertion kinds that require real tool execution. ``constraint``
# is intentionally excluded — it is verified via LLM-judge, not tool calls.
EXECUTION_ASSERTION_KINDS: frozenset[str] = frozenset(
    {"tool_called", "no_tool", "ordering"}
)


def is_execution_strategy(eval_strategy: str | None) -> bool:
    """True iff resources with this strategy execute tools during eval."""
    return eval_strategy in EXECUTION_STRATEGIES


def policy_summary(eval_strategy: str | None) -> str:
    """One-line allowed/forbidden grader guidance for the architect prompt."""
    if is_execution_strategy(eval_strategy):
        return (
            "EXECUTES tools in eval -> trajectory tool-call assertions "
            "(tool_called / no_tool / ordering) ALLOWED, plus outcome graders"
        )
    return (
        "CONTENT-ONLY in eval -> NO tool-call assertions "
        "(tool_called / no_tool / ordering); use llm_judge / contains / regex "
        "/ code, or a trajectory `constraint` (LLM-judged)"
    )


def eval_strategy_from_path(
    path: str, registry: ResourceTypeRegistry
) -> str | None:
    """Infer a resource's ``eval_strategy`` from its workspace path.

    Fallback for paths not tracked in orchestrator state. Matches the
    longest ``path_pattern`` prefix (``agents/``, ``skills/``, ...) from the
    registry — the single source of truth — so it stays correct if path
    patterns change. The plugin type (pattern ``{name}/`` → empty prefix) is
    skipped because it would match everything.
    """
    norm = path.strip()
    while norm.startswith("./"):
        norm = norm[2:]

    best: str | None = None
    best_len = -1
    for resource_type in ResourceType:
        cfg = registry.get(resource_type)
        if cfg is None:
            continue
        prefix = cfg.path_pattern.split("{name}", 1)[0]
        if prefix and norm.startswith(prefix) and len(prefix) > best_len:
            best = cfg.eval_strategy
            best_len = len(prefix)
    return best


def fallback_llm_judge(scenario: dict) -> dict:
    """Build an llm_judge grader from a scenario's description/prompt.

    Used when policy enforcement strips a content scenario's only graders
    (they were all execution-only tool-call checks). Keeps the scenario —
    now judge-graded — rather than dropping coverage. The rubric easily
    clears the schema's ``minLength: 10`` on ``rubric``.
    """
    desc = (
        scenario.get("description")
        or scenario.get("prompt")
        or "the requested task"
    ).strip()
    rubric = (
        "Score on a 1-5 scale how correctly and completely the response "
        "accomplishes the following (5 = fully correct and complete, "
        f"1 = fails or is irrelevant): {desc}"
    )
    return {"type": "llm_judge", "rubric": rubric, "pass_threshold": 0.7}


def _clean_grader(
    grader: dict, *, allow_execution: bool
) -> tuple[dict | None, list[str]]:
    """Return ``(cleaned_grader | None, actions)``. ``None`` → drop it.

    Recurses into composites. On content resources, strips
    execution-dependent assertions from trajectory graders and drops a
    trajectory grader (or composite) left empty.
    """
    if allow_execution:
        return grader, []

    gtype = grader.get("type")
    actions: list[str] = []

    if gtype == "trajectory":
        assertions = grader.get("assertions", []) or []
        kept = [
            a
            for a in assertions
            if a.get("kind") not in EXECUTION_ASSERTION_KINDS
        ]
        dropped = [
            a.get("kind")
            for a in assertions
            if a.get("kind") in EXECUTION_ASSERTION_KINDS
        ]
        if not dropped:
            return grader, actions
        if not kept:
            return None, [
                f"dropped trajectory grader (execution assertions {dropped} "
                "invalid on content resource)"
            ]
        return (
            {**grader, "assertions": kept},
            [f"stripped trajectory assertions {dropped} (content resource)"],
        )

    if gtype == "composite":
        children = grader.get("graders", []) or []
        new_children: list[dict] = []
        for child in children:
            cleaned, child_actions = _clean_grader(
                child, allow_execution=allow_execution
            )
            actions.extend(child_actions)
            if cleaned is not None:
                new_children.append(cleaned)
        if not new_children:
            return None, actions + [
                "dropped composite grader (all children invalid on content "
                "resource)"
            ]
        return {**grader, "graders": new_children}, actions

    return grader, actions


def _enforce_scenario(
    scenario: dict, eval_strategy: str
) -> tuple[dict, list[str]]:
    """Apply the grader policy to one scenario's grader list."""
    allow = is_execution_strategy(eval_strategy)
    if allow:
        return scenario, []

    cleaned: list[dict] = []
    actions: list[str] = []
    for grader in scenario.get("graders", []) or []:
        cg, acts = _clean_grader(grader, allow_execution=allow)
        actions.extend(acts)
        if cg is not None:
            cleaned.append(cg)

    if not cleaned:
        cleaned = [fallback_llm_judge(scenario)]
        actions.append(
            "scenario had only tool-call graders; rerouted to llm_judge "
            "built from its description"
        )

    if not actions:
        return scenario, []
    return {**scenario, "graders": cleaned}, actions


def enforce_suite(
    suite: dict, resolve_strategy: Callable[[str], str | None]
) -> tuple[dict, list[str]]:
    """Enforce grader-routing policy across an eval-suite dict.

    Args:
        suite: Parsed ``eval-suite.yaml`` as a dict.
        resolve_strategy: Maps a resource path to its ``eval_strategy``
            (or ``None`` when unresolvable — those scenarios are skipped so
            a failed lookup never strips a legitimately-executable grader).

    Returns:
        ``(possibly_rewritten_suite, actions)``. ``actions`` is empty when
        nothing changed — callers should only rewrite the file then.
    """
    default_target = suite.get("target_resource")
    scenarios = suite.get("scenarios", []) or []

    new_scenarios: list[dict] = []
    all_actions: list[str] = []
    for scenario in scenarios:
        target = scenario.get("target_resource") or default_target
        strategy = resolve_strategy(target) if target else None
        if strategy is None:
            new_scenarios.append(scenario)
            continue
        new_scenario, acts = _enforce_scenario(scenario, strategy)
        new_scenarios.append(new_scenario)
        if acts:
            sid = scenario.get("id", "?")
            all_actions.append(f"{sid} [{target}]: " + "; ".join(acts))

    if not all_actions:
        return suite, []
    return {**suite, "scenarios": new_scenarios}, all_actions
