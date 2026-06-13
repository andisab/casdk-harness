"""Tests for grader-routing policy (Phase A.5 A1).

Covers the eval_strategy→policy mapping, path inference, and the
suite-enforcement pass that strips execution-only trajectory assertions
from content-resource scenarios (the iac-generator / mobile "unwinnable
0/0" class) while leaving executable resources and `constraint`
assertions untouched.
"""

from __future__ import annotations

from harness.optimization.eval_harness.grader_policy import (
    EXECUTION_ASSERTION_KINDS,
    EXECUTION_STRATEGIES,
    enforce_suite,
    eval_strategy_from_path,
    fallback_llm_judge,
    is_execution_strategy,
    policy_summary,
)
from harness.optimization.protocols.resource_types import ResourceTypeRegistry

REGISTRY = ResourceTypeRegistry.default()


# --- helpers ---------------------------------------------------------------


def _scn(scn_id: str, graders: list[dict], target: str | None = None, **extra):
    scn: dict = {
        "id": scn_id,
        "level": extra.pop("level", "unit"),
        "prompt": extra.pop("prompt", "do the thing"),
        "graders": graders,
    }
    if target is not None:
        scn["target_resource"] = target
    scn.update(extra)
    return scn


def _suite(scenarios: list[dict], target: str = "agents/x.md") -> dict:
    return {
        "version": "1.0",
        "target_resource": target,
        "scenarios": scenarios,
        "config": {},
    }


def _trajectory(*kinds: str) -> dict:
    assertions = []
    for k in kinds:
        if k == "tool_called":
            assertions.append({"kind": "tool_called", "tool": "Write"})
        elif k == "no_tool":
            assertions.append({"kind": "no_tool", "tool": "Bash"})
        elif k == "ordering":
            assertions.append({"kind": "ordering", "before": "Read", "after": "Write"})
        elif k == "constraint":
            assertions.append({"kind": "constraint", "text": "stays on topic"})
    return {"type": "trajectory", "assertions": assertions}


_CONTAINS = {"type": "contains", "needle": "kubectl"}


def _resolver(mapping: dict[str, str]):
    def resolve(path: str) -> str | None:
        return mapping.get(path)

    return resolve


# --- is_execution_strategy / policy_summary --------------------------------


def test_execution_strategies_are_executable_and_server():
    assert {"executable", "server"} == EXECUTION_STRATEGIES
    assert is_execution_strategy("executable")
    assert is_execution_strategy("server")


def test_content_strategies_are_not_execution():
    for s in ("content_only", "content_and_execution", "unknown", None):
        assert not is_execution_strategy(s)


def test_agent_is_content_and_execution_but_not_executed_in_eval():
    # The crux of the iac-generator fix: agents are content_and_execution,
    # but that strategy does NOT execute tools in the in-process eval runtime.
    cfg = REGISTRY.get_by_string("agent")
    assert cfg is not None
    assert cfg.eval_strategy == "content_and_execution"
    assert not is_execution_strategy(cfg.eval_strategy)


def test_policy_summary_wording():
    assert "ALLOWED" in policy_summary("executable")
    assert "NO tool-call" in policy_summary("content_only")
    assert "NO tool-call" in policy_summary(None)


def test_execution_assertion_kinds_excludes_constraint():
    assert {"tool_called", "no_tool", "ordering"} == EXECUTION_ASSERTION_KINDS
    assert "constraint" not in EXECUTION_ASSERTION_KINDS


# --- eval_strategy_from_path -----------------------------------------------


def test_path_inference_per_type():
    assert eval_strategy_from_path("agents/foo.md", REGISTRY) == "content_and_execution"
    assert eval_strategy_from_path("skills/foo/SKILL.md", REGISTRY) == "content_only"
    assert eval_strategy_from_path("commands/foo.md", REGISTRY) == "content_only"
    assert eval_strategy_from_path("hooks/foo.json", REGISTRY) == "content_only"
    assert eval_strategy_from_path("tools/foo.py", REGISTRY) == "executable"
    assert eval_strategy_from_path("mcp-servers/foo/", REGISTRY) == "server"


def test_path_inference_strips_leading_dot_slash():
    assert eval_strategy_from_path("./agents/foo.md", REGISTRY) == "content_and_execution"


def test_path_inference_unknown_path_returns_none():
    assert eval_strategy_from_path("random/file.txt", REGISTRY) is None
    # Plugin's empty prefix must not match everything.
    assert eval_strategy_from_path("anything.md", REGISTRY) is None


# --- fallback_llm_judge ----------------------------------------------------


def test_fallback_llm_judge_uses_description():
    g = fallback_llm_judge({"description": "produce a valid Dockerfile"})
    assert g["type"] == "llm_judge"
    assert "produce a valid Dockerfile" in g["rubric"]
    assert len(g["rubric"]) >= 10  # schema minLength
    assert g["pass_threshold"] == 0.7


def test_fallback_llm_judge_falls_back_to_prompt():
    g = fallback_llm_judge({"prompt": "write tests"})
    assert "write tests" in g["rubric"]


# --- enforce_suite: content resources --------------------------------------


def test_content_only_trajectory_grader_rerouted_to_llm_judge():
    suite = _suite([_scn("s1", [_trajectory("tool_called")], target="agents/g.md")])
    cleaned, actions = enforce_suite(
        suite, _resolver({"agents/g.md": "content_and_execution"})
    )
    assert actions, "expected an enforcement action"
    graders = cleaned["scenarios"][0]["graders"]
    assert len(graders) == 1
    assert graders[0]["type"] == "llm_judge"
    assert "rerouted" in actions[0]


def test_content_mixed_graders_drops_only_trajectory():
    suite = _suite(
        [_scn("s1", [dict(_CONTAINS), _trajectory("tool_called")], target="skills/a/SKILL.md")]
    )
    cleaned, actions = enforce_suite(
        suite, _resolver({"skills/a/SKILL.md": "content_only"})
    )
    assert actions
    types = [g["type"] for g in cleaned["scenarios"][0]["graders"]]
    assert types == ["contains"]


def test_constraint_assertion_kept_on_content():
    suite = _suite([_scn("s1", [_trajectory("constraint")], target="skills/a/SKILL.md")])
    cleaned, actions = enforce_suite(
        suite, _resolver({"skills/a/SKILL.md": "content_only"})
    )
    assert actions == []  # nothing changed
    assert cleaned["scenarios"][0]["graders"][0]["type"] == "trajectory"


def test_mixed_assertions_strip_execution_keep_constraint():
    suite = _suite(
        [_scn("s1", [_trajectory("tool_called", "constraint")], target="agents/g.md")]
    )
    cleaned, actions = enforce_suite(
        suite, _resolver({"agents/g.md": "content_and_execution"})
    )
    assert actions
    grader = cleaned["scenarios"][0]["graders"][0]
    assert grader["type"] == "trajectory"
    kinds = [a["kind"] for a in grader["assertions"]]
    assert kinds == ["constraint"]


# --- enforce_suite: executable resources -----------------------------------


def test_executable_resource_trajectory_untouched():
    suite = _suite([_scn("s1", [_trajectory("tool_called", "ordering")], target="tools/t.py")])
    cleaned, actions = enforce_suite(suite, _resolver({"tools/t.py": "executable"}))
    assert actions == []
    grader = cleaned["scenarios"][0]["graders"][0]
    assert [a["kind"] for a in grader["assertions"]] == ["tool_called", "ordering"]


def test_server_resource_trajectory_untouched():
    suite = _suite([_scn("s1", [_trajectory("tool_called")], target="mcp-servers/s/")])
    _, actions = enforce_suite(suite, _resolver({"mcp-servers/s/": "server"}))
    assert actions == []


# --- enforce_suite: composites ---------------------------------------------


def test_composite_drops_trajectory_child_keeps_rest():
    composite = {
        "type": "composite",
        "operator": "and",
        "graders": [dict(_CONTAINS), _trajectory("tool_called")],
    }
    suite = _suite([_scn("s1", [composite], target="agents/g.md")])
    cleaned, actions = enforce_suite(
        suite, _resolver({"agents/g.md": "content_and_execution"})
    )
    assert actions
    grader = cleaned["scenarios"][0]["graders"][0]
    assert grader["type"] == "composite"
    assert [g["type"] for g in grader["graders"]] == ["contains"]


def test_composite_all_children_invalid_drops_then_reroutes():
    composite = {
        "type": "composite",
        "operator": "and",
        "graders": [_trajectory("tool_called"), _trajectory("ordering")],
    }
    suite = _suite([_scn("s1", [composite], target="agents/g.md", description="X")])
    cleaned, actions = enforce_suite(
        suite, _resolver({"agents/g.md": "content_and_execution"})
    )
    assert actions
    # composite emptied → dropped → scenario empty → llm_judge fallback
    graders = cleaned["scenarios"][0]["graders"]
    assert len(graders) == 1
    assert graders[0]["type"] == "llm_judge"


# --- enforce_suite: resolution + no-op semantics ---------------------------


def test_unresolved_target_is_left_untouched():
    suite = _suite([_scn("s1", [_trajectory("tool_called")], target="weird/x")])
    cleaned, actions = enforce_suite(suite, _resolver({}))  # resolves to None
    assert actions == []
    assert cleaned["scenarios"][0]["graders"][0]["type"] == "trajectory"


def test_scenario_target_override_beats_suite_default():
    # suite default is an executable tool; the scenario overrides to an agent.
    suite = _suite(
        [_scn("s1", [_trajectory("tool_called")], target="agents/g.md")],
        target="tools/t.py",
    )
    cleaned, actions = enforce_suite(
        suite,
        _resolver({"agents/g.md": "content_and_execution", "tools/t.py": "executable"}),
    )
    assert actions  # the override (content agent) triggers enforcement
    assert cleaned["scenarios"][0]["graders"][0]["type"] == "llm_judge"


def test_scenario_falls_back_to_suite_target_when_no_override():
    suite = _suite([_scn("s1", [_trajectory("tool_called")])], target="tools/t.py")
    _, actions = enforce_suite(suite, _resolver({"tools/t.py": "executable"}))
    assert actions == []  # suite default is executable → trajectory allowed


def test_clean_suite_returns_no_actions_and_preserves_fields():
    suite = _suite(
        [_scn("s1", [dict(_CONTAINS)], target="skills/a/SKILL.md", held_out=True, difficulty="hard")]
    )
    cleaned, actions = enforce_suite(
        suite, _resolver({"skills/a/SKILL.md": "content_only"})
    )
    assert actions == []
    assert cleaned is suite  # unchanged → same object
    scn = cleaned["scenarios"][0]
    assert scn["held_out"] is True
    assert scn["difficulty"] == "hard"
