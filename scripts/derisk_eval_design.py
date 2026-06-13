#!/usr/bin/env python3
"""Cheap EVAL_DESIGN probe for Phase A.5 (A1/A3/A5/A6).

Runs ONE eval-architect call against an existing multi-resource workspace
and reports whether the generated `eval/eval-suite.yaml` reflects the
discrimination-first changes — for ~$0.30 / a few minutes instead of a
full `make smoke` ($3-8 / 45-120 min). It does NOT exercise A2 (the
discrimination audit) or A4 (the cost floor); those fire during
EXECUTION_EVAL and need a fuller run — see the note printed at the end.

What it checks against the regenerated suite:
  A1 (routing)        tool_called / no_tool / ordering assertions on
                      content resources should be 0 (they're stripped /
                      the architect shouldn't author them); executable
                      resources may keep them.
  A3 (judge scale)    llm_judge rubrics should reference a 1-7 / 7-point
                      scale.
  A5 (discrimination) llm_judge / code graders should be well above the
                      contains-only baseline (run #8 had 0 llm_judge).

Usage (inside the harness container):
    docker compose exec main-agent \\
        python scripts/derisk_eval_design.py [workspace/iac-team]

Requires ANTHROPIC_API_KEY (the architect makes a real LLM call). Backs up
any existing eval-suite.yaml to eval-suite.yaml.bak-<n> before regenerating
so you can diff old vs new.
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

import yaml

# Ensure src/ is importable when run from the repo root.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from harness.optimization.eval_harness.grader_policy import (  # noqa: E402
    EXECUTION_ASSERTION_KINDS,
    eval_strategy_from_path,
    is_execution_strategy,
)
from harness.optimization.protocols.resource_types import (  # noqa: E402
    ResourceTypeRegistry,
)

_REGISTRY = ResourceTypeRegistry.default()


def _resource_strategy(target: str | None, state_resources: dict) -> str | None:
    """Resolve a scenario target's eval_strategy from state, then path."""
    if not target:
        return None
    res = state_resources.get(target)
    if res is not None:
        cfg = _REGISTRY.get_by_string(getattr(res, "resource_type", ""))
        if cfg is not None:
            return cfg.eval_strategy
    return eval_strategy_from_path(target, _REGISTRY)


def _iter_graders(graders: list[dict]):
    """Yield every grader, descending into composites."""
    for g in graders or []:
        yield g
        if g.get("type") == "composite":
            yield from _iter_graders(g.get("graders", []))


def analyze_suite(suite: dict, state_resources: dict) -> dict:
    """Pure analysis of a generated eval suite. Returns a report dict."""
    default_target = suite.get("target_resource")
    scenarios = suite.get("scenarios", []) or []

    grader_types: Counter = Counter()
    assertion_kinds: Counter = Counter()
    judge_rubrics: list[str] = []
    content_tool_call_assertions = 0
    exec_tool_call_assertions = 0
    resources_with_discriminating = set()

    for scn in scenarios:
        target = scn.get("target_resource") or default_target
        strategy = _resource_strategy(target, state_resources)
        is_exec = is_execution_strategy(strategy)
        has_discriminating = False
        for g in _iter_graders(scn.get("graders", [])):
            gtype = g.get("type")
            grader_types[gtype] += 1
            if gtype in ("llm_judge", "code"):
                has_discriminating = True
            if gtype == "llm_judge":
                judge_rubrics.append(g.get("rubric", ""))
            if gtype == "trajectory":
                for a in g.get("assertions", []) or []:
                    kind = a.get("kind")
                    assertion_kinds[kind] += 1
                    if kind in EXECUTION_ASSERTION_KINDS:
                        if is_exec:
                            exec_tool_call_assertions += 1
                        else:
                            content_tool_call_assertions += 1
                    elif kind == "constraint":
                        has_discriminating = True  # LLM-judged
        if has_discriminating and target:
            resources_with_discriminating.add(target)

    rubrics_1_7 = sum(
        1 for r in judge_rubrics if "1-7" in r or "1–7" in r or "7-point" in r.lower()
    )
    return {
        "scenarios": len(scenarios),
        "grader_types": dict(grader_types),
        "assertion_kinds": dict(assertion_kinds),
        "llm_judge_count": grader_types.get("llm_judge", 0),
        "rubrics_1_7": rubrics_1_7,
        "judge_rubrics": len(judge_rubrics),
        "content_tool_call_assertions": content_tool_call_assertions,
        "exec_tool_call_assertions": exec_tool_call_assertions,
        "resources_with_discriminating": len(resources_with_discriminating),
    }


def _print_report(rep: dict) -> None:
    def verdict(ok: bool) -> str:
        return "PASS" if ok else "CHECK"

    print("\n================  EVAL_DESIGN probe report  ================")
    print(f"scenarios:            {rep['scenarios']}")
    print(f"grader types:         {rep['grader_types']}")
    print(f"trajectory kinds:     {rep['assertion_kinds']}")
    print("-" * 60)
    a1_ok = rep["content_tool_call_assertions"] == 0
    print(
        f"A1 routing   [{verdict(a1_ok)}]  "
        f"tool-call assertions on CONTENT resources = "
        f"{rep['content_tool_call_assertions']} (want 0); "
        f"on executable = {rep['exec_tool_call_assertions']} (ok)"
    )
    a3_ok = rep["llm_judge_count"] == 0 or rep["rubrics_1_7"] > 0
    print(
        f"A3 scale     [{verdict(a3_ok)}]  "
        f"{rep['rubrics_1_7']}/{rep['judge_rubrics']} llm_judge rubrics "
        f"reference a 1-7 scale"
    )
    a5_ok = rep["llm_judge_count"] > 0
    print(
        f"A5 discrim.  [{verdict(a5_ok)}]  "
        f"llm_judge graders = {rep['llm_judge_count']} (run #8 had 0); "
        f"{rep['resources_with_discriminating']} resources have a "
        f"quality/judge grader"
    )
    print("-" * 60)
    print(
        "A2 (discrimination audit) and A4 (cost floor) fire during "
        "EXECUTION_EVAL, not this probe.\nRun `make smoke FIXTURE=<name>` "
        "for end-to-end coverage of those."
    )
    print("=" * 60)


async def _run(workspace: Path) -> int:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceConfig,
        MultiResourceOrchestrator,
    )

    suite_path = workspace / "eval" / "eval-suite.yaml"
    if suite_path.exists():
        n = 0
        while (bak := suite_path.with_suffix(f".yaml.bak-{n}")).exists():
            n += 1
        bak.write_text(suite_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"backed up existing suite -> {bak.name}")

    config = MultiResourceConfig(workspace_dir=workspace, verbose=True)
    orch = MultiResourceOrchestrator(config)
    await orch._initialize()  # noqa: SLF001 — probe uses internals deliberately
    if orch._progress and orch._progress.has_optimization_state():  # noqa: SLF001
        orch._state = orch._progress.load_optimization_state()  # noqa: SLF001
    if not orch._state:  # noqa: SLF001
        orch._state = orch._create_initial_state()  # noqa: SLF001

    state_resources = dict(orch._state.resources)  # noqa: SLF001
    print(
        f"running EVAL_DESIGN on {workspace} "
        f"({len(state_resources)} resources tracked)..."
    )
    await orch._delegate_eval_design()  # noqa: SLF001

    if not suite_path.exists():
        print("FAIL: architect did not write eval-suite.yaml")
        return 1
    suite = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    _print_report(analyze_suite(suite, state_resources))
    return 0


def main() -> int:
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workspace/iac-team")
    if not (workspace / "SPEC.md").exists():
        print(f"error: {workspace}/SPEC.md not found (need a completed multi-resource workspace)")
        return 2
    return asyncio.run(_run(workspace))


if __name__ == "__main__":
    raise SystemExit(main())
