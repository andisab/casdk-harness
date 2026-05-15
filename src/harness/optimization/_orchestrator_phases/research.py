"""RESEARCH phase implementation.

Delegates to the ``cgf-research-lead`` agent which decomposes optimization
goals and spawns parallel researchers.  Parses ``[RESEARCH_COMPLETE]`` and
validates that findings files actually landed on disk before signalling
phase completion.

Function is mounted onto :class:`MultiResourceOrchestrator` as
``_delegate_research`` via class-attribute assignment in
``multi_resource_orchestrator.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from harness.optimization._orchestrator_helpers import AGENT_RESEARCH
from harness.optimization.protocols.signals import SignalType

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate research to cgf-research-lead agent.

    Spawns the research lead agent which decomposes optimization goals
    and spawns parallel researchers. Parses [RESEARCH_COMPLETE] signal.
    """
    if not self._spec or not self._state:
        return

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir
    research_dir = workspace / "research" / "notes"
    research_dir.mkdir(parents=True, exist_ok=True)

    # Build prompt for research lead
    capabilities_text = "\n".join(
        f"- {cap.name}: {cap.description}"
        for cap in self._spec.capabilities
    )
    topics_text = "\n".join(f"- {t}" for t in self._spec.research_topics)

    prompt = f"""Research for multi-resource optimization.

Workspace: {workspace}
Plugin/Workflow: {self._spec.name}
Purpose: {self._spec.purpose}

Capabilities to research:
{capabilities_text}

Research topics:
{topics_text or "- Determine from capabilities"}

Resource context: {self._spec.name}
Resource type: {self._spec.spec_type.name}

CRITICAL: Save findings to {workspace}/research/notes/
(Use this exact path - it's the workspace root)

When complete, output:
[RESEARCH_COMPLETE]
eval_criteria_path: research/eval_criteria.yaml
"""

    logger.info(
        "RESEARCH: Delegating to cgf-research-lead",
        workspace=str(workspace),
        capabilities=len(self._spec.capabilities),
        timeout=self.config.research_timeout,
    )

    self._emit_progress("RESEARCH", "all", "in_progress")

    try:
        # Pass timeout directly to agent - no need for outer asyncio.wait_for
        response = await call_agent_simple(
            AGENT_RESEARCH,
            prompt,
            verbose=self.config.verbose or self.config.follow_logs,
            timeout=float(self.config.research_timeout),
        )
    except TimeoutError:
        logger.error(
            "RESEARCH: Timed out",
            timeout=self.config.research_timeout,
        )
        self._emit_progress(
            "RESEARCH", "all",
            f"timeout after {self.config.research_timeout}s"
        )
        raise TimeoutError(
            f"Research phase timed out after {self.config.research_timeout}s. "
            "Increase CGF_RESEARCH_TIMEOUT or simplify the SPEC."
        ) from None

    # Parse signal
    signals = self._signal_parser.parse(response)
    research_signals = [s for s in signals if s.type == SignalType.RESEARCH_COMPLETE]
    if research_signals:
        signal = research_signals[0]
        # Validate research files actually exist
        research_notes = workspace / "research" / "notes"
        findings_files = list(research_notes.glob("*_findings.yaml"))

        if not findings_files:
            logger.error(
                "RESEARCH: Signal received but no findings files found",
                expected_path=str(research_notes),
            )
            self._emit_progress("RESEARCH", "all", "failed - no files")
            raise ValueError(
                "Research phase emitted [RESEARCH_COMPLETE] but no findings "
                f"files found in {research_notes}. Check researcher output."
            )

        logger.info(
            "RESEARCH: Validated findings exist",
            files_found=len(findings_files),
        )

        # Extract eval_criteria_path if present in signal metadata
        eval_path = signal.metadata.get("eval_criteria_path", "")
        if eval_path:
            self._state.research_findings_path = str(eval_path).strip()

        logger.info(
            "RESEARCH: Complete",
            findings_path=self._state.research_findings_path,
        )
        self._emit_progress("RESEARCH", "all", "complete")
    else:
        logger.warning(
            "RESEARCH: No completion signal found in response",
            response_length=len(response),
        )

    self._save_state()
