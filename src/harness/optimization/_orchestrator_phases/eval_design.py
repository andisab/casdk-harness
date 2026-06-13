"""EVAL_DESIGN phase implementation (CGF Stage 3 Phase A.5 + EVAL_DESIGN v2).

EVAL_DESIGN v2 (L1.3, 2026-06-13): instead of one monolithic
``cgf-eval-architect`` call that reads every resource's v0+candidate pair and
writes the whole suite (17m54s / 74 turns at 18 resources — near the phase
timeout), the phase now **shards by resource**:

1. For each eligible resource, Python reads its v0 baseline + generated file and
   computes a concise ``capability_diff`` (L1.2) — the v0→v1 gap the scenarios
   must discriminate — and embeds it INLINE in a tight per-resource prompt.
2. Those per-resource architect calls run in parallel under a
   ``CGF_EVAL_DESIGN_CONCURRENCY`` semaphore, each capped at a small
   ``max_turns`` (L1.1 enforcement makes the cap bind), each writing a complete
   per-resource ``eval/shards/{slug}.yaml``.
3. Python merges the shard suites into ``eval/eval-suite.yaml``, stamping each
   scenario's ``target_resource`` from its shard (the merged top-level can name
   only one), de-duping scenario ids, then runs the A1 grader-policy
   enforcement + suite-hash + telemetry exactly as before.

A shard that fails contributes no scenarios (logged; pipeline continues); only
when ALL shards fail does the phase take the loud no-suite error path so
EXECUTION_EVAL never silently skips.

Function mounted onto :class:`MultiResourceOrchestrator` as
``_delegate_eval_design`` via class-attribute assignment in
``multi_resource_orchestrator.py``.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

from harness.monitoring import harness_eval_phase_duration_seconds
from harness.optimization._orchestrator_helpers import (
    AGENT_EVAL_ARCHITECT,
    capability_diff,
    classify_sdk_error,
    eval_phase_span,
    eval_suite_sha256,
    new_eval_task_id,
    versioned_path,
)
from harness.optimization.eval_harness.grader_policy import (
    enforce_suite,
    eval_strategy_from_path,
    policy_summary,
)
from harness.optimization.protocols.resource_types import ResourceTypeRegistry

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )
    from harness.progress import ResourceStatus

logger = structlog.get_logger(__name__)

# EVAL_DESIGN v2 defaults (overridable via env).
_DEFAULT_EVAL_DESIGN_CONCURRENCY = 5
_DEFAULT_SHARD_MAX_TURNS = 15


# ---------------------------------------------------------------------------
# Env-knob resolvers
# ---------------------------------------------------------------------------


def _resolve_eval_design_concurrency() -> int:
    """Max concurrent per-resource architect shards (``CGF_EVAL_DESIGN_CONCURRENCY``)."""
    raw = os.environ.get("CGF_EVAL_DESIGN_CONCURRENCY", "")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return _DEFAULT_EVAL_DESIGN_CONCURRENCY


def _resolve_shard_max_turns() -> int:
    """Per-shard architect turn cap (``CGF_EVAL_DESIGN_SHARD_MAX_TURNS``).

    Small by design: a shard reads the inline diff + at most a couple of
    optional files, writes one ``eval-suite.yaml``, emits the signal. The
    L1.1 harness-side enforcement makes this bind (the SDK ``--max-turns``
    alone did not).
    """
    raw = os.environ.get("CGF_EVAL_DESIGN_SHARD_MAX_TURNS", "")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return _DEFAULT_SHARD_MAX_TURNS


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested in test_eval_design_sharding.py)
# ---------------------------------------------------------------------------


def _shard_slug(resource_path: str) -> str:
    """Filesystem-safe slug for a resource's shard file.

    ``agents/iac-analyzer.md`` → ``agents-iac-analyzer``;
    ``skills/aws-eks/SKILL.md`` → ``skills-aws-eks-skill``. Collisions across a
    real resource plan are vanishingly unlikely; the caller still de-dupes
    shard paths defensively.
    """
    p = Path(resource_path)
    try:
        stem = p.with_suffix("").as_posix()
    except ValueError:
        # e.g. Path(".") / empty input — no name to strip a suffix from.
        stem = p.as_posix()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return slug or "resource"


def _load_resource_purposes(plan_path: Path) -> dict[str, str]:
    """Best-effort ``resource-path → purpose`` map from resource-plan.yaml.

    Defensive: returns ``{}`` on any parse error or shape mismatch. Used only
    to inline a short purpose hint into each shard prompt so the common case
    needs no plan read; the architect can always read the plan itself when the
    hint is absent. Keys are recorded under every identifier the entry exposes
    (``path`` / ``name`` / ``file`` / ``target``) so lookups by either the full
    path or the basename resolve.
    """
    try:
        data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — best-effort hint; never break the phase
        return {}
    if not isinstance(data, dict):
        return {}
    resources = data.get("resources")
    if not isinstance(resources, list):
        return {}
    out: dict[str, str] = {}
    for entry in resources:
        if not isinstance(entry, dict):
            continue
        purpose = (
            entry.get("purpose")
            or entry.get("description")
            or entry.get("role")
        )
        if not purpose:
            continue
        for key in ("path", "name", "file", "target"):
            val = entry.get(key)
            if isinstance(val, str) and val:
                out[val] = str(purpose)
    return out


def _build_shard_prompt(
    *,
    workspace: str,
    resource_path: str,
    resource_type: str,
    policy: str,
    purpose: str,
    diff: str,
    shard_path: str,
    generated_path: str,
    spec_path: str,
    criteria_path: str,
    plan_path: str,
) -> str:
    """Tight per-resource EVAL_DESIGN prompt.

    Everything needed to design 3 discriminating scenarios is INLINE (resource
    path/type, grader policy, purpose, v0→v1 diff). SPEC / criteria / plan / the
    full generated file are offered only as optional reads for when the diff is
    insufficient (truncated, or a new resource with no v0).
    """
    purpose_block = (
        purpose.strip()
        if purpose
        else "(not inlined — read resource-plan.yaml if you need it)"
    )
    return f"""Design the evaluation scenarios for ONE resource.

Workspace: {workspace}
Resource: {resource_path}  (type: {resource_type})
Grader policy: {policy}

Purpose:
{purpose_block}

What changed from the v0 baseline to the generated candidate. Design scenarios
the v0 baseline FAILS and the generated candidate PASSES — that gap is the whole
point (the discrimination mandate). If a scenario cannot name a criterion v0
fails, redesign it:

{diff}

WRITE one complete, schema-valid eval-suite.yaml for THIS resource to:
  {shard_path}

It MUST contain:
  - version: "1.0"
  - target_resource: "{resource_path}"
  - config: {{trials_per_scenario: 1, timeout_seconds: 300, held_out_fraction: 0.33}}
  - scenarios: exactly 3 (one easy, one medium, one hard) for THIS resource,
    each carrying at least one grader the v0 baseline is expected to FAIL.
    Mark the hard scenario held_out: true.

GRADER ROUTING (HARD CONSTRAINT): the resource above is annotated CONTENT-ONLY
or EXECUTES. CONTENT-ONLY resources load their file as a system prompt and never
dispatch tools during eval, so trajectory tool_called / no_tool / ordering
assertions score 0 on BOTH arms and are worthless — use llm_judge / contains /
regex / code (a trajectory `constraint`, LLM-judged, is fine). Reserve
tool_called / no_tool / ordering for resources marked EXECUTES.

Optional reads, ONLY if the inline diff is insufficient: the generated file
{generated_path}; SPEC.md {spec_path}; eval_criteria.yaml {criteria_path};
resource-plan.yaml {plan_path}.

Emit [EVAL_DESIGN_COMPLETE] after the file is written.
"""


def _merge_shard_suites(
    shards: list[tuple[str, dict]],
    *,
    source_resource_count: int,
) -> dict:
    """Merge per-resource shard suites into one eval-suite dict.

    ``shards`` is a list of ``(resource_path, parsed_shard_suite)`` pairs, one
    per successfully-designed resource. Each scenario is stamped with its
    shard's ``target_resource`` (the merged top-level names only the first
    resource, so per-scenario targets must be authoritative or scenarios from
    other shards would be graded against the wrong file). Scenario ids are
    de-duped across shards. Malformed scenarios (non-dict, or missing
    ``id`` / ``graders``) are dropped. Returns a dict ready to dump to
    ``eval-suite.yaml``.
    """
    merged_scenarios: list[dict] = []
    seen_ids: set[str] = set()
    first_target = shards[0][0] if shards else ""

    for idx, (resource_path, suite) in enumerate(shards):
        if not isinstance(suite, dict):
            continue
        scenarios = suite.get("scenarios")
        if not isinstance(scenarios, list):
            continue
        for raw in scenarios:
            if not isinstance(raw, dict):
                continue
            if "id" not in raw or "graders" not in raw:
                continue
            sc = dict(raw)
            # Authoritative per-scenario target: the merged top-level
            # target_resource can name only one resource, so a scenario from
            # any other shard would otherwise grade against the wrong file.
            sc["target_resource"] = resource_path
            sid = str(sc.get("id"))
            if sid in seen_ids:
                sid = f"{sid}-s{idx}"[:80]  # schema maxLength on id
                sc["id"] = sid
            seen_ids.add(sid)
            merged_scenarios.append(sc)

    return {
        "version": "1.0",
        "target_resource": first_target,
        "description": (
            f"Eval suite merged from {len(shards)} per-resource shards "
            f"({source_resource_count} resources eligible)"
        ),
        "config": {
            "trials_per_scenario": 1,
            "timeout_seconds": 300,
            "held_out_fraction": 0.33,
        },
        "scenarios": merged_scenarios,
        "metadata": {
            "generator": "cgf-eval-architect",
            "generated_from": "resource-plan.yaml",
            "design_mode": "sharded",
            "source_resource_count": source_resource_count,
            "shard_count": len(shards),
        },
    }


def _enforce_grader_policy(
    suite_path: Path, resolve_strategy: Callable[[str], str | None]
) -> list[str]:
    """Strip execution-only trajectory assertions from content-resource
    scenarios (Phase A.5 A1).

    Rewrites the suite file only when something changed. Never raises —
    enforcement is best-effort and must not block the pipeline.
    """
    try:
        suite = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "EVAL_DESIGN: grader-policy enforcement could not parse suite",
            error=str(exc)[:200],
        )
        return []
    if not isinstance(suite, dict):
        return []
    cleaned, actions = enforce_suite(suite, resolve_strategy)
    if actions:
        try:
            suite_path.write_text(
                yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "EVAL_DESIGN: grader-policy could not rewrite suite",
                error=str(exc)[:200],
            )
            return []
        logger.warning(
            "EVAL_DESIGN: grader-policy rerouted graders on content resources",
            action_count=len(actions),
            actions=actions[:20],
        )
    return actions


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate eval-suite generation to cgf-eval-architect, sharded by resource.

    Fans out one tight per-resource architect call (inline v0→v1 diff, capped
    ``max_turns``) per eligible resource under a concurrency semaphore, then
    merges the per-resource shard suites into ``{workspace}/eval/eval-suite.yaml``.

    F11: skip only when NO resources exist (e.g. DESIGN failed entirely).
    Resources at any non-empty status (generated / optimized /
    needs_refinement) are eligible inputs.
    """
    if not self._spec or not self._state:
        return

    phase_start = time.time()
    task_id = new_eval_task_id()

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir

    # F11: any non-failed resource is fair input. Failed resources are excluded
    # only so we don't ask for scenarios on a file that never got generated.
    eligible = [
        r for r in self._state.resources.values() if r.status != "failed"
    ]

    if not eligible:
        logger.warning(
            "EVAL_DESIGN: No eligible resources; skipping eval-suite design",
        )
        async with eval_phase_span(
            "eval.design",
            task_id=task_id,
            phase="EVAL_DESIGN",
            extra={"harness.eval.outcome": "skipped"},
        ):
            pass
        return

    # Ensure eval/ and eval/shards/ exist for the architects to write into.
    eval_dir = workspace / "eval"
    shards_dir = eval_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)

    spec_path = workspace / self._spec.source_path
    eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
    resource_plan_path = workspace / "resource-plan.yaml"

    # Phase A.5 A1: resolve each resource's eval_strategy so we can annotate
    # the shard prompt (CONTENT-ONLY vs EXECUTES) and run post-design
    # enforcement. resolve_strategy falls back to path-prefix inference for any
    # target not tracked in state.
    registry = ResourceTypeRegistry.default()
    strat_by_path: dict[str, str] = {}
    for r in eligible:
        cfg = registry.get_by_string(r.resource_type)
        if cfg is not None:
            strat_by_path[r.path] = cfg.eval_strategy

    def resolve_strategy(path: str) -> str | None:
        if path in strat_by_path:
            return strat_by_path[path]
        return eval_strategy_from_path(path, registry)

    purposes = _load_resource_purposes(resource_plan_path)

    concurrency = _resolve_eval_design_concurrency()
    shard_max_turns = _resolve_shard_max_turns()
    per_shard_timeout = float(self.config.eval_design_timeout)
    sem = asyncio.Semaphore(concurrency)
    seen_slugs: dict[str, int] = {}

    def _unique_shard_path(resource_path: str) -> Path:
        base = _shard_slug(resource_path)
        n = seen_slugs.get(base, 0)
        seen_slugs[base] = n + 1
        name = base if n == 0 else f"{base}-{n}"
        return shards_dir / f"{name}.yaml"

    # Pre-assign shard paths serially (keeps slug de-dup deterministic).
    shard_targets: list[tuple[ResourceStatus, Path]] = [
        (r, _unique_shard_path(r.path)) for r in eligible
    ]

    async def _design_one(
        r: ResourceStatus, shard_path: Path
    ) -> tuple[str, dict | None]:
        """Design scenarios for one resource; return (path, parsed_suite|None)."""
        rpath: str = r.path
        gen_path = workspace / rpath
        if not gen_path.exists():
            logger.warning(
                "EVAL_DESIGN: generated file missing; skipping shard",
                resource=rpath,
            )
            return (rpath, None)
        try:
            gen_text = gen_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "EVAL_DESIGN: cannot read generated file; skipping shard",
                resource=rpath,
                error=str(exc)[:200],
            )
            return (rpath, None)

        v0_path = workspace / versioned_path(rpath, 0)
        v0_text: str | None = None
        if v0_path.exists():
            try:
                v0_text = v0_path.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001 — diff degrades to "new resource"
                v0_text = None

        diff = capability_diff(v0_text, gen_text, label=rpath)
        prompt = _build_shard_prompt(
            workspace=str(workspace),
            resource_path=rpath,
            resource_type=r.resource_type,
            policy=policy_summary(strat_by_path.get(rpath)),
            purpose=purposes.get(rpath) or purposes.get(Path(rpath).name) or "",
            diff=diff,
            shard_path=str(shard_path),
            generated_path=str(gen_path),
            spec_path=str(spec_path),
            criteria_path=(
                str(eval_criteria_path)
                if eval_criteria_path.exists()
                else "(not present)"
            ),
            plan_path=(
                str(resource_plan_path)
                if resource_plan_path.exists()
                else "(not present)"
            ),
        )

        async with sem:
            try:
                await call_agent_simple(
                    AGENT_EVAL_ARCHITECT,
                    prompt,
                    verbose=self.config.verbose or self.config.follow_logs,
                    timeout=per_shard_timeout,
                    max_turns=shard_max_turns,
                )
            except TimeoutError:
                logger.error(
                    "EVAL_DESIGN: shard timed out",
                    resource=rpath,
                    timeout=per_shard_timeout,
                )
                return (rpath, None)
            except Exception as exc:  # noqa: BLE001 — one shard must not abort fan-out
                category, friendly = classify_sdk_error(exc)
                logger.error(
                    "EVAL_DESIGN: shard architect call failed",
                    resource=rpath,
                    error_category=category,
                    error=friendly,
                )
                return (rpath, None)

        if not shard_path.exists():
            logger.warning(
                "EVAL_DESIGN: shard produced no file",
                resource=rpath,
                expected=str(shard_path),
            )
            return (rpath, None)
        try:
            shard_data = yaml.safe_load(shard_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "EVAL_DESIGN: shard file unparseable",
                resource=rpath,
                error=str(exc)[:200],
            )
            return (rpath, None)
        if not isinstance(shard_data, dict) or not shard_data.get("scenarios"):
            logger.warning(
                "EVAL_DESIGN: shard wrote no scenarios", resource=rpath
            )
            return (rpath, None)
        return (rpath, shard_data)

    logger.info(
        "EVAL_DESIGN: sharded fan-out to cgf-eval-architect",
        workspace=str(workspace),
        resources=len(eligible),
        concurrency=concurrency,
        shard_max_turns=shard_max_turns,
    )
    self._emit_progress("EVAL_DESIGN", "all", "in_progress")

    raw_results = await asyncio.gather(
        *(_design_one(r, sp) for (r, sp) in shard_targets),
        return_exceptions=True,
    )

    successful: list[tuple[str, dict]] = []
    for (r, _sp), res in zip(shard_targets, raw_results, strict=True):
        if isinstance(res, BaseException):
            logger.warning(
                "EVAL_DESIGN: shard raised unexpectedly",
                resource=r.path,
                error=str(res)[:200],
            )
            continue
        rpath, data = res
        if data is not None:
            successful.append((rpath, data))

    suite_path = eval_dir / "eval-suite.yaml"

    if not successful:
        # All shards failed — phase deliverable missing. Fail loudly rather
        # than letting EXECUTION_EVAL silently skip (false-positive "complete"
        # run with no eval data). Mirrors the monolithic no-suite error path.
        err_msg = (
            f"EVAL_DESIGN: all {len(eligible)} per-resource shards failed to "
            f"produce scenarios. No eval-suite.yaml written. Expected file: "
            f"{suite_path}."
        )
        logger.error(err_msg, shards_total=len(eligible), shards_succeeded=0)
        self._emit_progress("EVAL_DESIGN", "all", "failed - no shards succeeded")
        harness_eval_phase_duration_seconds.labels(
            phase="EVAL_DESIGN"
        ).observe(time.time() - phase_start)
        async with eval_phase_span(
            "eval.design",
            task_id=task_id,
            phase="EVAL_DESIGN",
            extra={
                "harness.eval.outcome": "no_suite_written",
                "harness.eval.resource_count": len(eligible),
                "harness.eval.shards_total": len(eligible),
                "harness.eval.shards_succeeded": 0,
            },
        ):
            pass
        self._save_state()
        raise ValueError(err_msg)

    # Merge shard suites into the canonical eval-suite.yaml.
    merged = _merge_shard_suites(successful, source_resource_count=len(eligible))
    suite_path.write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    self._state.eval_suite_path = "eval/eval-suite.yaml"
    # Phase A.5 A1: enforce grader-routing policy BEFORE the hash is taken, so
    # the suite-hash baseline reflects the enforced suite. Only rewrites the
    # file when something changed.
    _enforce_grader_policy(suite_path, resolve_strategy)
    # Phase A refinement 4.4.a: single chokepoint where the suite-hash baseline
    # is set; EXECUTION_EVAL checks against this each round and aborts on
    # mismatch. Don't mutate eval-suite.yaml elsewhere without recomputing.
    self._state.eval_suite_hash = eval_suite_sha256(suite_path)

    scenario_count = len(merged["scenarios"])
    logger.info(
        "EVAL_DESIGN: merged sharded suite complete",
        suite_path=str(suite_path),
        shards_total=len(eligible),
        shards_succeeded=len(successful),
        scenarios=scenario_count,
        suite_hash=self._state.eval_suite_hash[:16] + "...",
    )
    if len(successful) < len(eligible):
        logger.warning(
            "EVAL_DESIGN: some resources have no scenarios",
            missing=len(eligible) - len(successful),
            total=len(eligible),
        )
    self._emit_progress("EVAL_DESIGN", "all", "complete")

    self._save_state()
    harness_eval_phase_duration_seconds.labels(
        phase="EVAL_DESIGN"
    ).observe(time.time() - phase_start)
    async with eval_phase_span(
        "eval.design",
        task_id=task_id,
        phase="EVAL_DESIGN",
        extra={
            "harness.eval.outcome": "success",
            "harness.eval.resource_count": len(eligible),
            "harness.eval.shards_total": len(eligible),
            "harness.eval.shards_succeeded": len(successful),
            "harness.eval.scenario_count": scenario_count,
        },
    ):
        pass
