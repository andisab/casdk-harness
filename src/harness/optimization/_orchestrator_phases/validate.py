"""VALIDATE phase implementation.

Delegates to the ``cgf-coherence-validator`` agent for cross-resource
checks (terminology, references, dependency cycles, plugin manifest
consistency).  Parses ``[VALIDATE_COMPLETE]`` or
``[VALIDATE_ISSUES:{count}]`` and either advances to ``COMPLETE`` or
loops affected resources back to ``ITERATE`` (subject to
``max_refinements``).

Function mounted onto :class:`MultiResourceOrchestrator` as
``_delegate_validation``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from harness.optimization._orchestrator_helpers import AGENT_VALIDATE
from harness.optimization.protocols.signals import SignalType
from harness.progress import OptimizationPhase

if TYPE_CHECKING:
    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
    )

logger = structlog.get_logger(__name__)


async def delegate(self: MultiResourceOrchestrator) -> None:
    """Delegate coherence validation to cgf-coherence-validator agent.

    Spawns the validator for all optimized resources.
    Parses [VALIDATE_COMPLETE] or [VALIDATE_ISSUES:{count}] signals.
    On issues, loops affected resources back to ITERATE.
    """
    if not self._state or not self._spec:
        return

    from harness.subagent import call_agent_simple

    workspace = self.config.workspace_dir

    logger.info(
        "VALIDATE: Running cross-resource coherence check",
        resources=len(self._state.resources),
        timeout=self.config.validate_timeout,
    )
    self._emit_progress("VALIDATE", "all", "in_progress")

    prompt = f"""Validate coherence for multi-resource plugin.

Workspace: {workspace}
Plugin: {self._spec.name}

Check:
1. Terminology consistency across all resources
2. Cross-references between commands/agents/skills
3. Dependency ordering (no cycles)
4. Plugin structure (plugin.json matches filesystem)

Write report to research/reviews/coherence-report.md

If all checks pass:
[VALIDATE_COMPLETE]
coherence_score: {{0.85-1.00}}

If issues found:
[VALIDATE_ISSUES:{{count}}]
issue_1: {{description}}
affected_resources:
- {{path}}
"""

    try:
        # Pass timeout directly to agent
        response = await call_agent_simple(
            AGENT_VALIDATE,
            prompt,
            verbose=self.config.verbose or self.config.follow_logs,
            timeout=float(self.config.validate_timeout),
        )
    except TimeoutError:
        logger.error(
            "VALIDATE: Timed out",
            timeout=self.config.validate_timeout,
        )
        self._emit_progress(
            "VALIDATE", "all",
            f"timeout after {self.config.validate_timeout}s"
        )
        # On timeout, complete anyway since validation is the last phase
        logger.warning("VALIDATE: Completing with timeout, skipping validation")
        self._advance_phase(OptimizationPhase.COMPLETE)
        return

    # Parse signal
    signals = self._signal_parser.parse(response)
    validate_complete = [s for s in signals if s.type == SignalType.VALIDATE_COMPLETE]
    validate_issues = [s for s in signals if s.type == SignalType.VALIDATE_ISSUES]
    if validate_complete:
        # Extract coherence score from signal metadata
        score_str = validate_complete[0].metadata.get("coherence_score", "")
        coherence_score = float(score_str) if score_str else 1.0

        logger.info(
            "VALIDATE: Complete",
            coherence_score=f"{coherence_score:.2f}",
        )
        self._emit_progress(
            "VALIDATE", "all", "complete", coherence_score
        )

        # Pre-completion validation
        missing = self._validate_all_resources_exist()
        if missing:
            logger.error(
                "COMPLETE: Cannot finalize - missing resources",
                missing_count=len(missing),
                missing_paths=missing[:5],  # Show first 5
            )
            # Don't fail - log warning and continue
            # Resources can be regenerated in next run

        self._advance_phase(OptimizationPhase.COMPLETE)

    elif validate_issues:
        # Extract issue count from signal metadata
        issue_count = int(validate_issues[0].metadata.get("issue_count", 0))

        # Extract affected resources
        affected = re.findall(
            r"- ((?:agents|skills|commands)/[^\n]+)", response
        )

        # Check if there are FAIL-level issues (not just warnings)
        # Only refine for FAIL/ERROR/CRITICAL, not WARN
        has_fail_issues = any(
            level in response.upper()
            for level in ["FAIL", "ERROR", "CRITICAL", "SEVERITY: HIGH"]
        )

        logger.warning(
            "VALIDATE: Issues found",
            issue_count=issue_count,
            has_fail_issues=has_fail_issues,
            affected=affected,
        )

        # Skip refinement if configured or no FAIL-level issues
        if self.config.skip_refinement:
            logger.info(
                "VALIDATE: Skipping refinement (configured)"
            )
            self._advance_phase(OptimizationPhase.COMPLETE)
            return

        if not has_fail_issues:
            logger.info(
                "VALIDATE: Only WARN issues - completing without refinement"
            )
            self._advance_phase(OptimizationPhase.COMPLETE)
            return

        # Check refinement count
        can_refine = True
        for path in affected:
            if path in self._state.resources:
                resource = self._state.resources[path]
                if resource.refinement_count >= self.config.max_refinements:
                    can_refine = False
                    logger.warning(
                        "VALIDATE: Max refinements reached",
                        path=path,
                        refinement_count=resource.refinement_count,
                    )

        if can_refine and affected:
            # Loop affected resources back to ITERATE
            for path in affected:
                if path in self._state.resources:
                    resource = self._state.resources[path]
                    # Skip refinement for v0 failed resources
                    if (
                        resource.version == 0
                        and resource.status == "failed"
                    ):
                        logger.warning(
                            "VALIDATE: Skipping refinement for "
                            "failed resource",
                            path=path,
                        )
                        continue
                    self._state.update_resource(
                        path,
                        status="needs_refinement",
                        refinement_count=(
                            resource.refinement_count + 1
                        ),
                    )

            # Go back to ITERATE phase
            self._state.current_phase = OptimizationPhase.ITERATE
            self._save_state()
        else:
            # Complete with warnings
            logger.warning(
                "VALIDATE: Completing with unresolved issues",
                issue_count=issue_count,
            )
            self._advance_phase(OptimizationPhase.COMPLETE)

    else:
        logger.warning(
            "VALIDATE: No signal found, completing anyway",
            response_length=len(response),
        )
        self._advance_phase(OptimizationPhase.COMPLETE)
