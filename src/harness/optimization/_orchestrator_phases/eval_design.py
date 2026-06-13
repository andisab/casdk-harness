"""EVAL_DESIGN phase implementation (CGF Stage 3 Phase A.5).

Delegates to the ``cgf-eval-architect`` agent which reads SPEC, research
findings, resource-plan, and the just-generated resource files; produces
``eval/eval-suite.yaml`` conforming to ``eval_suite.schema.json``.
Parses ``[EVAL_DESIGN_COMPLETE]`` and validates the suite file actually
landed on disk before signalling phase completion.

Function mounted onto :class:`MultiResourceOrchestrator` as
``_delegate_eval_design`` via class-attribute assignment in
``multi_resource_orchestrator.py``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

from harness.monitoring import harness_eval_phase_duration_seconds
from harness.optimization._orchestrator_helpers import (
    AGENT_EVAL_ARCHITECT,
    classify_sdk_error,
    eval_phase_span,
    eval_suite_sha256,
    new_eval_task_id,
)
from harness.optimization.eval_harness.grader_policy import (
    enforce_suite,
    eval_strategy_from_path,
    policy_summary,
)
from harness.optimization.protocols.resource_types import ResourceTypeRegistry
from harness.optimization.protocols.signals import SignalType

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


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
    """Delegate eval suite generation to cgf-eval-architect agent.

    Reads SPEC + research + resource-plan + generated resources; produces
    ``{workspace}/eval/eval-suite.yaml``.  Parses ``[EVAL_DESIGN_COMPLETE]``
    signal and validates the suite file exists before continuing.

    F11: skip only when NO resources exist (e.g., DESIGN failed entirely).
    Resources at any non-empty status (generated / optimized /
    needs_refinement) are eligible inputs to the eval-architect, which
    reads SPEC.md + resource-plan.yaml regardless.  The prior version
    skipped silently when resources were `optimized` (legitimate state
    on resume), causing every downstream EXECUTION_EVAL to silently
    skip too.
    """
    if not self._spec or not self._state:
        return

    phase_start = time.time()
    task_id = new_eval_task_id()

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir

    # F11: any resource the orchestrator is tracking is fair input
    # for the eval-architect.  The architect builds scenarios from
    # SPEC + resource-plan, not from per-resource state.  Failed
    # resources are excluded only so we don't ask for eval scenarios
    # on a file that never got generated.
    eligible = [
        r
        for r in self._state.resources.values()
        if r.status != "failed"
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

    # Ensure the eval/ directory exists for the architect to write into.
    eval_dir = workspace / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Build prompt with paths the architect needs to read.
    spec_path = workspace / self._spec.source_path
    eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
    resource_plan_path = workspace / "resource-plan.yaml"

    # Phase A.5 A1: resolve each resource's eval_strategy so the architect
    # is told, per resource, which grader types can actually discriminate
    # it. Content resources (skills/commands/hooks/plugins/agent-definition
    # files) run as content in eval and cannot satisfy tool-call assertions;
    # only executable/server resources can. resolve_strategy falls back to
    # path-prefix inference for any target not tracked in state.
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

    resource_list = "\n".join(
        f"  - {r.path} (type: {r.resource_type}) -- "
        f"{policy_summary(strat_by_path.get(r.path))}"
        for r in eligible
    )

    # Phase A refinement 4.1: STRICT isolation contract for the
    # eval-architect.  The architect designs the eval suite from inputs
    # the optimizer has not influenced — SPEC, plan, criteria, file
    # paths.  It MUST NOT see:
    #   - optimizer rationale or diff
    #   - iteration number / version
    #   - feedback history
    #   - per-resource gate verdicts from prior rounds
    #   - any other-resource scores
    # If you find yourself wanting to add any of those to this prompt,
    # stop — that is exactly the leak this contract prevents.  Anthropic's
    # *Three-Agent Harness* guidance: the agent designing the eval cannot
    # have seen the optimizer's diff, because the optimizer hasn't
    # produced one yet at EVAL_DESIGN time.
    prompt = f"""Design the evaluation suite for this multi-resource plugin.

Workspace: {workspace}

Inputs to read:
- SPEC.md: {spec_path}
- eval_criteria.yaml: {eval_criteria_path if eval_criteria_path.exists() else "(not present)"}
- resource-plan.yaml: {resource_plan_path if resource_plan_path.exists() else "(not present)"}
- Generated resources (read each one):
{resource_list}

Output: {workspace}/eval/eval-suite.yaml

The output MUST conform to ``schemas/eval_suite.schema.json``.
Apply the level mix per resource type, the 40/40/20 difficulty split,
and the 20-30% held_out: true selection rule from your system prompt.

GRADER ROUTING (HARD CONSTRAINT). Each resource above is annotated with its
eval grader policy. Resources marked CONTENT-ONLY are run as content (their
file is loaded as a system prompt) and do NOT dispatch tools during eval, so
trajectory `tool_called` / `no_tool` / `ordering` assertions on them score 0
on BOTH arms and are worthless. For CONTENT-ONLY resources use llm_judge /
contains / regex / code graders (a trajectory `constraint`, which is
LLM-judged, is also fine). Reserve `tool_called` / `no_tool` / `ordering`
assertions for resources marked EXECUTES tools. Violations are stripped
automatically after design — but author them correctly so each scenario keeps
a grader that actually discriminates the candidate from the baseline.

Emit [EVAL_DESIGN_COMPLETE] when done.
"""

    logger.info(
        "EVAL_DESIGN: Delegating to cgf-eval-architect",
        workspace=str(workspace),
        resources=len(eligible),
        timeout=self.config.eval_design_timeout,
    )
    self._emit_progress("EVAL_DESIGN", "all", "in_progress")

    try:
        response = await call_agent_simple(
            AGENT_EVAL_ARCHITECT,
            prompt,
            verbose=self.config.verbose or self.config.follow_logs,
            timeout=float(self.config.eval_design_timeout),
        )
    except TimeoutError:
        logger.error(
            "EVAL_DESIGN: Timed out",
            timeout=self.config.eval_design_timeout,
        )
        self._emit_progress(
            "EVAL_DESIGN", "all",
            f"timeout after {self.config.eval_design_timeout}s",
        )
        # Don't raise — let EXECUTION_EVAL skip if no suite file exists.
        return
    except Exception as exc:
        category, friendly = classify_sdk_error(exc)
        logger.error(
            "EVAL_DESIGN: Architect call failed (retries exhausted)",
            error_category=category,
            error=friendly,
            raw_error=str(exc)[:300],
        )
        self._emit_progress(
            "EVAL_DESIGN", "all", f"failed - {category}"
        )
        # Don't raise — let EXECUTION_EVAL skip; orchestrator surfaces the
        # missing eval-suite.yaml as the visible failure mode below.
        response = ""

    # Parse signal
    signals = self._signal_parser.parse(response)
    eval_design_signals = [
        s for s in signals if s.type == SignalType.EVAL_DESIGN_COMPLETE
    ]

    suite_path = workspace / "eval" / "eval-suite.yaml"
    suite_exists = suite_path.exists()

    # The agent may emit the signal inline in prose, in a code block, or
    # alongside the YAML literal — all are signal-positive.  The
    # authoritative success criterion is the suite file actually landing
    # on disk; the signal is just an early hint.
    if suite_exists:
        self._state.eval_suite_path = "eval/eval-suite.yaml"
        # Phase A.5 A1: enforce grader-routing policy BEFORE the hash is
        # taken, so the suite-hash baseline reflects the enforced suite.
        # Strips execution-only trajectory assertions from content resources
        # (the iac-generator / mobile "unwinnable 0/0" class) and reroutes a
        # scenario left grader-less to an llm_judge built from its
        # description. Only rewrites the file when something changed.
        _enforce_grader_policy(suite_path, resolve_strategy)
        # Phase A refinement 4.4.a: capture suite hash here.  EXECUTION_EVAL
        # checks against this on every round; mismatch → hard abort.  This
        # is the single chokepoint where the suite-hash baseline is set;
        # don't mutate eval-suite.yaml elsewhere without recomputing.
        self._state.eval_suite_hash = eval_suite_sha256(suite_path)
        if eval_design_signals:
            logger.info(
                "EVAL_DESIGN: Complete",
                suite_path=str(suite_path),
                suite_hash=self._state.eval_suite_hash[:16] + "...",
            )
        else:
            logger.info(
                "EVAL_DESIGN: Suite created (no signal)",
                suite_path=str(suite_path),
                suite_hash=self._state.eval_suite_hash[:16] + "...",
            )
        self._emit_progress("EVAL_DESIGN", "all", "complete")
    else:
        # No suite on disk — phase deliverable missing.  Fail loudly
        # rather than letting EXECUTION_EVAL silently skip, which
        # produces a false-positive "phases complete" run with no
        # eval data and no Phase A telemetry.  The orchestrator's
        # error handler will surface this as a phase failure.
        if eval_design_signals:
            err_msg = (
                "EVAL_DESIGN: cgf-eval-architect emitted "
                "[EVAL_DESIGN_COMPLETE] but no eval-suite.yaml on disk. "
                "The agent likely described the suite inline instead of "
                "using the Write tool. Expected file: "
                f"{suite_path}. Response length: {len(response)} chars."
            )
        else:
            err_msg = (
                "EVAL_DESIGN: cgf-eval-architect produced no completion "
                "signal AND no eval-suite.yaml on disk. The agent failed "
                "to deliver. Expected file: "
                f"{suite_path}. Response length: {len(response)} chars."
            )
        logger.error(err_msg, signals_seen=len(eval_design_signals))
        self._emit_progress("EVAL_DESIGN", "all", "failed - no suite file")
        # Record the phase-duration metric and outcome span before raising,
        # so the failure shows up in telemetry.
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
            },
        ):
            pass
        self._save_state()
        raise ValueError(err_msg)

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
        },
    ):
        pass
