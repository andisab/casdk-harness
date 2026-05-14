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
from typing import TYPE_CHECKING

import structlog

from harness.monitoring import harness_eval_phase_duration_seconds
from harness.optimization._orchestrator_helpers import (
    AGENT_EVAL_ARCHITECT,
    classify_sdk_error,
    eval_phase_span,
    new_eval_task_id,
)
from harness.optimization.protocols.signals import SignalType

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


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

    resource_list = "\n".join(
        f"  - {r.path} (type: {r.resource_type})" for r in eligible
    )

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
        if eval_design_signals:
            logger.info(
                "EVAL_DESIGN: Complete",
                suite_path=str(suite_path),
            )
        else:
            logger.info(
                "EVAL_DESIGN: Suite created (no signal)",
                suite_path=str(suite_path),
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
