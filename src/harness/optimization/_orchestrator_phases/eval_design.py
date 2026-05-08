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

    Skips if no resources were generated (e.g., GENERATE phase failed for
    everything).  In that case the EXECUTION_EVAL phase will also skip.
    """
    if not self._spec or not self._state:
        return

    phase_start = time.time()
    task_id = new_eval_task_id()

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir
    generated = self._state.get_generated_resources()

    if not generated:
        logger.warning(
            "EVAL_DESIGN: No generated resources; skipping eval-suite design",
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
        f"  - {r.path} (type: {r.resource_type})" for r in generated
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
        resources=len(generated),
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

    # Parse signal
    signals = self._signal_parser.parse(response)
    eval_design_signals = [
        s for s in signals if s.type == SignalType.EVAL_DESIGN_COMPLETE
    ]

    suite_path = workspace / "eval" / "eval-suite.yaml"
    if eval_design_signals:
        if suite_path.exists():
            self._state.eval_suite_path = "eval/eval-suite.yaml"
            logger.info(
                "EVAL_DESIGN: Complete",
                suite_path=str(suite_path),
            )
            self._emit_progress("EVAL_DESIGN", "all", "complete")
        else:
            logger.error(
                "EVAL_DESIGN: Signal received but suite file not found",
                expected=str(suite_path),
            )
            self._emit_progress(
                "EVAL_DESIGN", "all", "failed - no suite file",
            )
            # Don't raise — EXECUTION_EVAL will skip when suite missing.
    else:
        # Check if file was created anyway.
        if suite_path.exists():
            self._state.eval_suite_path = "eval/eval-suite.yaml"
            logger.info(
                "EVAL_DESIGN: Suite created (no signal)",
                suite_path=str(suite_path),
            )
            self._emit_progress("EVAL_DESIGN", "all", "complete")
        else:
            logger.warning(
                "EVAL_DESIGN: No completion signal and no suite file",
                response_length=len(response),
            )

    self._save_state()
    harness_eval_phase_duration_seconds.labels(
        phase="EVAL_DESIGN"
    ).observe(time.time() - phase_start)
    # Final tracer span with outcome attribute.
    outcome = "success" if self._state.eval_suite_path else "no_suite_written"
    async with eval_phase_span(
        "eval.design",
        task_id=task_id,
        phase="EVAL_DESIGN",
        extra={
            "harness.eval.outcome": outcome,
            "harness.eval.resource_count": len(generated),
        },
    ):
        pass
