"""DESIGN phase implementation.

Delegates to the ``cgf-resource-architect`` agent which produces
``resource-plan.yaml`` from SPEC + research findings.  Parses
``[DESIGN_COMPLETE]`` and loads the plan into orchestrator state.

Functions are mounted onto :class:`MultiResourceOrchestrator` as
``_delegate_design`` and ``_load_resource_plan`` via class-attribute
assignment in ``multi_resource_orchestrator.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from harness.optimization._orchestrator_helpers import AGENT_DESIGN
from harness.optimization.protocols.signals import SignalType

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate resource architecture to cgf-resource-architect agent.

    The architect analyzes SPEC + research findings and produces
    resource-plan.yaml defining what to build, why, and in what order.
    Parses [DESIGN_COMPLETE] signal and loads the plan into state.
    """
    if not self._spec or not self._state:
        return

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir

    # Build prompt with SPEC content and research findings
    spec_content = workspace / self._spec.source_path
    spec_text = spec_content.read_text() if spec_content.exists() else ""

    # Load research findings if available
    research_summary = ""
    eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
    if eval_criteria_path.exists():
        research_summary = eval_criteria_path.read_text()

    prompt = f"""Design the optimal resource architecture for this SPEC.

Workspace: {workspace}

SPEC.md content:
{spec_text}

Research findings (eval_criteria.yaml):
{research_summary}

Write resource-plan.yaml to: {workspace}/resource-plan.yaml

Follow the resource_plan.schema.json schema.
Emit [DESIGN_COMPLETE] when done.
"""

    logger.info(
        "DESIGN: Delegating to resource-architect",
        workspace=str(workspace),
        timeout=self.config.design_timeout,
    )
    self._emit_progress("DESIGN", "all", "in_progress")

    try:
        response = await call_agent_simple(
            AGENT_DESIGN,
            prompt,
            verbose=self.config.verbose or self.config.follow_logs,
            timeout=float(self.config.design_timeout),
        )
    except TimeoutError:
        logger.error("DESIGN: Timed out", timeout=self.config.design_timeout)
        self._emit_progress(
            "DESIGN", "all", f"timeout after {self.config.design_timeout}s"
        )
        raise TimeoutError(
            f"Design phase timed out after {self.config.design_timeout}s."
        ) from None

    # Parse signal
    signals = self._signal_parser.parse(response)
    design_signals = [s for s in signals if s.type == SignalType.DESIGN_COMPLETE]
    if design_signals:
        plan_path = workspace / "resource-plan.yaml"
        if plan_path.exists():
            self._load_resource_plan(plan_path)
            self._state.resource_plan_path = "resource-plan.yaml"
            logger.info(
                "DESIGN: Complete",
                resources=len(self._state.resources),
                plan_path="resource-plan.yaml",
            )
            self._emit_progress("DESIGN", "all", "complete")
        else:
            logger.error("DESIGN: Signal received but plan file not found")
            self._emit_progress("DESIGN", "all", "failed - no plan file")
            raise ValueError(
                "Design phase emitted [DESIGN_COMPLETE] but resource-plan.yaml "
                f"not found at {plan_path}."
            )
    else:
        logger.warning(
            "DESIGN: No completion signal found",
            response_length=len(response),
        )

    self._save_state()


def load_resource_plan(self: MultiResourceOrchestrator, plan_path: Path) -> None:
    """Load resource-plan.yaml and populate state with resources.

    Args:
        plan_path: Absolute path to resource-plan.yaml
    """
    import yaml

    with open(plan_path) as f:
        plan = yaml.safe_load(f)

    if not plan or "resources" not in plan:
        raise ValueError(f"Invalid resource plan: {plan_path}")

    # Add resources to state in generation_order
    generation_order = plan.get("generation_order", [])
    resources_by_path = {r["path"]: r for r in plan["resources"]}

    # First add in generation_order (dependency-respecting order)
    for path in generation_order:
        if path in resources_by_path:
            r = resources_by_path[path]
            status = self._state.add_resource(path, r["type"])
            status.depends_on = r.get("depends_on", [])

    # Then add any remaining (not in generation_order)
    for r in plan["resources"]:
        if r["path"] not in self._state.resources:
            status = self._state.add_resource(r["path"], r["type"])
            status.depends_on = r.get("depends_on", [])

    # Save updated state
    if self._progress:
        self._progress.save_optimization_state(self._state)

    logger.info(
        "DESIGN: Loaded resource plan",
        total_resources=len(self._state.resources),
        generation_order=generation_order,
    )
