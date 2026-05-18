"""Multi-resource optimization orchestrator.

Coordinates the generative + iterative pipeline for multi-resource specs:
PLANNING → RESEARCH → DESIGN → QA → GENERATE → ITERATE → VALIDATE → COMPLETE

Python is a thin state coordinator; agents do all the work.
State machine: spawn agent → agent outputs signal → Python parses signal → transition

This file holds the :class:`MultiResourceOrchestrator` class skeleton plus
the dispatcher and cross-cutting helpers (state mgmt, finalization,
progress emission).  Per-phase logic lives under
:mod:`harness.optimization._orchestrator_phases` and is mounted onto the
class as methods via class-attribute assignment near the bottom of this
file.

The split is a pure-refactor cleanup of what was a single 2157-LoC file.
Behavior is unchanged.

Example usage:

    from harness.optimization.multi_resource_orchestrator import (
        MultiResourceOrchestrator,
        MultiResourceConfig,
    )

    config = MultiResourceConfig(
        workspace_dir=Path("workspace/iac-team"),
        quality_threshold=0.85,
        max_iterations=5,
        verbose=True,
    )

    orchestrator = MultiResourceOrchestrator(config)
    result = await orchestrator.run()

    if result.success:
        print(f"Generated {len(result.resources)} resources")
        for path, status in result.resources.items():
            print(f"  {path}: quality={status.quality.overall:.2f}")
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from harness.monitoring import (
    init_run_phases,
    record_phase_entry,
    record_run_config,
    record_run_path,
    record_run_start,
)
from harness.optimization._orchestrator_helpers import (
    AGENT_DESIGN,
    AGENT_EVAL_ARCHITECT,
    AGENT_EVALUATE,
    AGENT_GENERATE,
    AGENT_ITERATE,
    AGENT_RESEARCH,
    AGENT_VALIDATE,
    DEFAULT_EVAL_PROMOTION_EPSILON,
    DEFAULT_MAX_FEEDBACK_ITERATIONS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_REFINEMENT,
    DEFAULT_MAX_VALIDATE_REFINEMENTS,
    DEFAULT_QUALITY_THRESHOLD,
    PathViolationError,
    validate_write_path,
    versioned_path,
)
from harness.optimization._orchestrator_phases import (
    design as _design_phase,
)
from harness.optimization._orchestrator_phases import (
    eval_design as _eval_design_phase,
)
from harness.optimization._orchestrator_phases import (
    execution_eval as _execution_eval_phase,
)
from harness.optimization._orchestrator_phases import (
    generate as _generate_phase,
)
from harness.optimization._orchestrator_phases import (
    iterate as _iterate_phase,
)
from harness.optimization._orchestrator_phases import (
    qa as _qa_phase,
)
from harness.optimization._orchestrator_phases import (
    research as _research_phase,
)
from harness.optimization._orchestrator_phases import (
    validate as _validate_phase,
)
from harness.progress import (
    MultiResourceState,
    OptimizationPhase,
    ProgressManager,
    ResourceStatus,
)

from . import run_report
from .multi_resource_spec import (
    MultiResourceSpec,
    is_multi_resource_spec,
    parse_multi_resource_spec,
)
from .protocols.signals import SignalParser
from .quality_evaluator import QualityEvaluator

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Backward-compatible aliases for symbols that other modules / tests
# imported from this file before the helpers were extracted.  Do not
# change without updating callers.
# ---------------------------------------------------------------------------

_versioned_path = versioned_path  # noqa: F841 — public alias (used by tests)


# ---------------------------------------------------------------------------
# F22 — Subagent hang audit
# ---------------------------------------------------------------------------


def _audit_child_processes() -> set[int]:
    """Return PIDs of ``claude`` descendants of the current process.

    Pure observability — never raises.  When ``psutil`` is unavailable
    or the snapshot fails (permissions, race), returns an empty set so
    the caller's diff degrades to "no orphans detected" rather than
    breaking the phase.
    """
    try:
        import psutil  # imported here so missing dep doesn't break import
    except Exception:  # noqa: BLE001 — degrade silently
        return set()

    try:
        me = psutil.Process(os.getpid())
        return {
            p.pid
            for p in me.children(recursive=True)
            if "claude" in (p.name() or "").lower()
        }
    except Exception:  # noqa: BLE001 — psutil races / permission errors
        return set()


def _log_orphan_children(phase_name: str, before: set[int]) -> None:
    """Compare post-phase child PIDs to the pre-phase snapshot.

    A non-empty diff means the phase exited while ``claude`` subprocesses
    were still alive — likely a cancellation that didn't propagate into
    the underlying CLI.  Log a warning with the PIDs; do NOT kill (a
    soft-kill follow-up is gated behind a week of observability data).
    """
    try:
        after = _audit_child_processes()
        leaked = after - before
        if leaked:
            logger.warning(
                "Phase left subprocess descendants alive",
                phase=phase_name,
                leaked_pids=sorted(leaked),
                count=len(leaked),
                hint=(
                    "SDK cancellation may not have terminated the "
                    "underlying claude CLI subprocess; investigate "
                    "whether ITERATE/EVAL timeouts fired during this phase."
                ),
            )
    except Exception:  # noqa: BLE001 — observability must not break phases
        pass

__all__ = [
    "AGENT_DESIGN",
    "AGENT_EVAL_ARCHITECT",
    "AGENT_EVALUATE",
    "AGENT_GENERATE",
    "AGENT_ITERATE",
    "AGENT_RESEARCH",
    "AGENT_VALIDATE",
    "DEFAULT_EVAL_PROMOTION_EPSILON",
    "DEFAULT_MAX_FEEDBACK_ITERATIONS",
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_MAX_REFINEMENT",
    "DEFAULT_QUALITY_THRESHOLD",
    "MultiResourceConfig",
    "MultiResourceOrchestrator",
    "OrchestrationResult",
    "PathViolationError",
    "_versioned_path",
    "run_multi_resource_optimization",
    "validate_write_path",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MultiResourceConfig:
    """Configuration for multi-resource optimization.

    Attributes:
        workspace_dir: Directory containing SPEC.md and output files
        quality_threshold: Target quality score (0.0-1.0)
        max_iterations: Max iterations per resource
        max_refinements: Max refinement loops before escalation
        verbose: Enable verbose output
        skip_research: Skip research phase (use existing findings)
        skip_qa: Skip Q&A phase (use existing decisions or defaults)
        skip_refinement: Skip refinement loops entirely (fast mode)
        eval_model: Model for quality evaluation
        parallel_generation: Generate independent resources in parallel
        research_timeout: Timeout for research phase (seconds)
        generate_timeout: Timeout per resource generation (seconds)
        iterate_timeout: Timeout per optimization iteration (seconds)
        validate_timeout: Timeout for validation phase (seconds)
        design_timeout: Timeout for design phase (seconds)
        show_progress: Show phase transitions and progress updates
        follow_logs: Stream agent activity in real-time
    """

    workspace_dir: Path
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_refinements: int = DEFAULT_MAX_REFINEMENT
    verbose: bool = False
    skip_research: bool = False
    skip_qa: bool = False
    skip_refinement: bool = False
    eval_model: str | None = None
    parallel_generation: bool = True
    progress_callback: Callable[[str, str, str], None] | None = None
    # Phase-specific timeouts (seconds)
    research_timeout: int = 1800  # 30 minutes
    generate_timeout: int = 900   # 15 minutes per resource
    iterate_timeout: int = 1200   # 20 minutes per iteration (large SKILLs need it; F6)
    validate_timeout: int = 300   # 5 minutes
    design_timeout: int = 900     # 15 minutes for resource architecture
    eval_design_timeout: int = 1200  # 20 minutes — safety net; slim prompt should finish in &lt;3 min
    execution_eval_timeout: int = 1800  # 30 minutes for full eval run
    # Phase A.5 eval gate
    eval_promotion_epsilon: float | None = None  # None → use env / default
    max_feedback_iterations: int | None = None   # None → use env / default
    # F9: cap on VALIDATE → ITERATE loop-backs.  Distinct from
    # max_refinements (per-resource) — this is a pipeline-level safety
    # net.  When the validator keeps flagging the same files round after
    # round, we hit this cap and force COMPLETE with the issues recorded.
    max_validate_refinements: int = DEFAULT_MAX_VALIDATE_REFINEMENTS
    # Progress display settings
    show_progress: bool = True
    follow_logs: bool = True


@dataclass
class OrchestrationResult:
    """Result from multi-resource optimization.

    Attributes:
        success: Whether orchestration completed successfully
        spec: The parsed multi-resource spec
        resources: Final resource statuses
        phases_completed: List of completed phases
        total_duration_seconds: Total time taken
        error: Error message if failed
    """

    success: bool
    spec: MultiResourceSpec | None = None
    resources: dict[str, ResourceStatus] = field(default_factory=dict)
    phases_completed: list[OptimizationPhase] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "spec_name": self.spec.name if self.spec else None,
            "spec_type": self.spec.spec_type.name if self.spec else None,
            "resources": {
                path: status.to_dict() for path, status in self.resources.items()
            },
            "phases_completed": [p.name for p in self.phases_completed],
            "total_duration_seconds": self.total_duration_seconds,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class MultiResourceOrchestrator:
    """Orchestrates multi-resource optimization pipeline via agent delegation.

    Core principle: Python is a thin state coordinator; agents do all the work.

    Pipeline phases:
    1. PLANNING - Parse SPEC.md, create initial state (Python only)
    2. RESEARCH - Delegate to cgf-research-lead (once for domain)
    3. DESIGN - Delegate to cgf-resource-architect (once for plan)
    4. QA - Auto-accept structure (or interactive Q&A)
    5. GENERATE - Delegate to context-engineer (per resource)
    6. ITERATE - Delegate to cgf-prompt-optimizer (per resource)
    7. VALIDATE - Delegate to cgf-coherence-validator (once for all)
    8. COMPLETE - Final state update

    Each agent emits signals that Python parses to transition state.
    Per-phase implementation lives in
    :mod:`harness.optimization._orchestrator_phases`; this class owns
    state mgmt, dispatch, finalization, and progress emission.
    """

    def __init__(self, config: MultiResourceConfig) -> None:
        """Initialize the orchestrator.

        Args:
            config: Configuration for optimization.
        """
        self.config = config
        self._spec: MultiResourceSpec | None = None
        self._state: MultiResourceState | None = None
        self._progress: ProgressManager | None = None
        self._evaluator: QualityEvaluator | None = None
        self._signal_parser = SignalParser()
        # F4: serialize state-file writes across concurrent per-resource
        # coroutines.  Constructed eagerly so phase modules can reference
        # ``self._state_lock`` without checking for None.  asyncio.Lock()
        # is constructable outside an event loop in Python 3.10+; first
        # acquire bind it to the running loop.
        self._state_lock: asyncio.Lock = asyncio.Lock()

    # ----- public API -----

    async def run(self) -> OrchestrationResult:
        """Run the full multi-resource optimization pipeline.

        Returns:
            OrchestrationResult with success status and details.
        """
        start_time = time.time()

        logger.info(
            "Starting multi-resource optimization",
            workspace=str(self.config.workspace_dir),
            quality_threshold=self.config.quality_threshold,
            max_iterations=self.config.max_iterations,
        )

        try:
            # Initialize
            await self._initialize()

            # Check for existing state (for resumption)
            if self._progress and self._progress.has_optimization_state():
                self._state = self._progress.load_optimization_state()
                if self._state:
                    logger.info(
                        "Resuming from existing state",
                        current_phase=self._state.current_phase.name,
                        phases_completed=[
                            p.name for p in self._state.phases_completed
                        ],
                    )

            # Create new state if needed
            if not self._state:
                self._state = self._create_initial_state()

            # Run pipeline from current phase
            await self._run_pipeline()

            duration = time.time() - start_time

            logger.info(
                "Multi-resource optimization complete",
                spec=self._spec.name if self._spec else "unknown",
                phases_completed=[p.name for p in self._state.phases_completed],
                resources_optimized=len(self._state.get_optimized_resources()),
                total_duration=f"{duration:.1f}s",
            )

            return OrchestrationResult(
                success=True,
                spec=self._spec,
                resources=self._state.resources,
                phases_completed=self._state.phases_completed,
                total_duration_seconds=duration,
            )

        except Exception as e:
            logger.error("Multi-resource optimization failed", error=str(e))
            return OrchestrationResult(
                success=False,
                error=str(e),
                total_duration_seconds=time.time() - start_time,
            )

    # ----- initialization + state management -----

    async def _initialize(self) -> None:
        """Initialize the orchestrator with spec and progress manager."""
        workspace = self.config.workspace_dir

        # Find SPEC.md
        spec_path = workspace / "SPEC.md"
        if not spec_path.exists():
            raise FileNotFoundError(f"SPEC.md not found in {workspace}")

        # Check if multi-resource spec
        if not is_multi_resource_spec(spec_path):
            raise ValueError(
                f"SPEC.md at {spec_path} is not a multi-resource spec. "
                "Use single-resource CGF for this file."
            )

        # Parse spec
        self._spec = parse_multi_resource_spec(spec_path)

        # Initialize progress manager
        self._progress = ProgressManager(workspace)

        # Initialize quality evaluator
        model = self.config.eval_model or os.environ.get(
            "CGF_EVAL_MODEL", "claude-sonnet-4-20250514"
        )
        self._evaluator = QualityEvaluator(model=model)

        logger.info(
            "Initialized orchestrator",
            spec_name=self._spec.name,
            spec_type=self._spec.spec_type.name,
            proposed_resources=self._spec.total_proposed_resources,
        )

    def _create_initial_state(self) -> MultiResourceState:
        """Create initial optimization state."""
        if not self._spec:
            raise RuntimeError("Spec not loaded")

        state = MultiResourceState(
            spec_path=str(self._spec.source_path),
            spec_type=self._spec.spec_type.name,
            spec_hash=self._spec.content_hash,
            current_phase=OptimizationPhase.RESEARCH,
            quality_threshold=self.config.quality_threshold,
            max_iterations=self.config.max_iterations,
        )

        # NOTE: Resources are NOT pre-populated here.
        # The resource-architect agent determines what to build in the DESIGN phase.

        # Save initial state
        if self._progress:
            self._progress.save_optimization_state(state)

        # Emit a first run-report so the file exists from t=0.  Done
        # here (not via _update_run_report) because self._state isn't
        # bound yet at this point.
        if os.environ.get("CGF_RUN_REPORT", "1") != "0":
            try:
                run_report.write(self.config.workspace_dir)
            except Exception as exc:  # pragma: no cover
                logger.debug("initial run-report write failed", error=str(exc))

        # Seed run-phase gauge for Grafana from the very first phase
        try:
            ws = self.config.workspace_dir
            resource_label = ws.name if ws else "unknown"
        except Exception:
            resource_label = "unknown"
        record_run_path(resource_label, "multi")
        init_run_phases(resource_label)
        record_phase_entry(resource_label, state.current_phase.name.lower())
        record_run_start(resource_label)
        # Token budget is read at EvalHarness construction time from
        # CGF_EVAL_TOKEN_BUDGET; surface the same value here so the Grafana
        # run-config row matches what the eval pipeline will actually use.
        # `effort` is a placeholder until per-prompt effort tracking is wired.
        try:
            token_budget = int(os.environ.get("CGF_EVAL_TOKEN_BUDGET", "0"))
        except ValueError:
            token_budget = 0
        record_run_config(
            resource=resource_label,
            path="multi",
            mode="optimize",
            model=self.config.eval_model or "default",
            effort="default",
            eval_enabled=True,
            token_budget=token_budget,
            max_iterations=self.config.max_iterations,
        )

        return state

    async def _run_pipeline(self) -> None:
        """Run the optimization pipeline from current phase."""
        if not self._state:
            raise RuntimeError("State not initialized")

        phase = self._state.current_phase

        while phase != OptimizationPhase.COMPLETE:
            logger.info("Running phase", phase=phase.name)

            # F22: snapshot child PIDs before the phase runs.  Compared
            # against the post-phase snapshot to detect orphaned ``claude``
            # subprocesses left behind by SDK timeouts that didn't clean
            # up.  Pure observability — never blocks phase progress.
            children_before = _audit_child_processes()

            if phase == OptimizationPhase.RESEARCH:
                if self.config.skip_research:
                    logger.info("Skipping RESEARCH phase (configured)")
                else:
                    await self._delegate_research()
                self._advance_phase(OptimizationPhase.DESIGN)

            elif phase == OptimizationPhase.DESIGN:
                await self._delegate_design()
                self._advance_phase(OptimizationPhase.QA)

            elif phase == OptimizationPhase.QA:
                if self.config.skip_qa:
                    logger.info("Skipping Q&A phase (configured)")
                else:
                    await self._run_qa_phase()
                self._advance_phase(OptimizationPhase.GENERATE)

            elif phase == OptimizationPhase.GENERATE:
                await self._delegate_generation()
                self._advance_phase(OptimizationPhase.EVAL_DESIGN)

            elif phase == OptimizationPhase.EVAL_DESIGN:
                await self._delegate_eval_design()
                self._advance_phase(OptimizationPhase.ITERATE)

            elif phase == OptimizationPhase.ITERATE:
                await self._delegate_iteration()
                self._advance_phase(OptimizationPhase.EXECUTION_EVAL)

            elif phase == OptimizationPhase.EXECUTION_EVAL:
                await self._run_execution_eval()
                # _run_execution_eval handles its own phase transition:
                # - All promoted → advances to VALIDATE
                # - Regressions remain & under max_feedback → loops back to ITERATE
                # - Regressions remain & at max_feedback → escalates to VALIDATE
                # - Suite missing or no resources → falls through (advance below)
                if self._state.current_phase == OptimizationPhase.EXECUTION_EVAL:
                    # No transition handled internally → forward to VALIDATE
                    self._advance_phase(OptimizationPhase.VALIDATE)

            elif phase == OptimizationPhase.VALIDATE:
                await self._delegate_validation()
                # _delegate_validation handles phase transition
                # If transitioning to COMPLETE, finalize resources
                if self._state.current_phase == OptimizationPhase.COMPLETE:
                    self._finalize_resources()

            # F22: compare post-phase child PIDs against the pre-phase
            # snapshot.  A non-empty diff means the phase exited while
            # leaving SDK subprocesses alive — likely a cancellation
            # that didn't propagate into the underlying ``claude`` CLI.
            # Observability only; do not kill (yet).
            _log_orphan_children(
                phase_name=phase.name, before=children_before,
            )

            phase = self._state.current_phase

    def _advance_phase(self, next_phase: OptimizationPhase) -> None:
        """Advance to the next phase and save state."""
        if not self._state or not self._progress:
            return

        self._state.advance_phase(next_phase)
        self._progress.save_optimization_state(self._state)
        self._update_run_report()

        # Update Prometheus gauge for Grafana run-status panel
        try:
            ws = self.config.workspace_dir
            resource_label = ws.name if ws else "unknown"
        except Exception:
            resource_label = "unknown"
        record_phase_entry(resource_label, next_phase.name.lower())

        logger.info(
            "Phase complete",
            completed=self._state.phases_completed[-1].name,
            next_phase=next_phase.name,
        )

    def _save_state(self) -> None:
        """Save current state to disk."""
        if self._state and self._progress:
            self._state.updated_at = datetime.now(UTC).isoformat()
            self._progress.save_optimization_state(self._state)
            self._update_run_report()

    def _update_run_report(self) -> None:
        """Regenerate ``sessions/RUN_REPORT.md`` from current state.

        Pure derived view; safe to no-op on any failure.  Gated by
        ``CGF_RUN_REPORT`` (default on; set to ``0`` to disable).
        """
        if os.environ.get("CGF_RUN_REPORT", "1") == "0":
            return
        try:
            run_report.write(self.config.workspace_dir)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("run-report update failed", error=str(exc))

    # ----- cross-phase helpers -----

    def _validate_all_resources_exist(self) -> list[str]:
        """Validate all tracked resources have corresponding files.

        Returns:
            List of missing resource paths (empty if all exist).
        """
        if not self._state:
            return []

        missing = []
        workspace = self.config.workspace_dir

        for path, resource in self._state.resources.items():
            full_path = workspace / path
            if not full_path.exists():
                missing.append(path)
                logger.warning(
                    "VALIDATE: Resource file missing",
                    path=path,
                    status=resource.status,
                )

        return missing

    def _emit_progress(
        self, phase: str, resource: str, status: str, quality: float | None = None
    ) -> None:
        """Emit progress update via callback.

        Args:
            phase: Current phase (RESEARCH, GENERATE, ITERATE, VALIDATE).
            resource: Resource path or identifier.
            status: Status message (complete, in_progress, failed, etc.).
            quality: Optional quality score.
        """
        if self.config.progress_callback:
            if quality is not None:
                msg = f"[{phase}] {resource}: {status} (quality: {quality:.2f})"
            else:
                msg = f"[{phase}] {resource}: {status}"
            self.config.progress_callback(phase, resource, msg)
        # Also log for non-callback usage
        if self.config.verbose:
            if quality is not None:
                logger.info(
                    f"Progress: {phase}",
                    resource=resource,
                    status=status,
                    quality=f"{quality:.2f}",
                )
            else:
                logger.info(
                    f"Progress: {phase}",
                    resource=resource,
                    status=status,
                )

    def _backup_original_resource(self, resource_path: str) -> None:
        """Backup original resource to -v0 before generation.

        If a file exists at the resource path (e.g., from a previous run),
        rename it to {name}-v0.md to preserve the original.

        Args:
            resource_path: Relative path like "agents/iac-analyzer.md"

        Raises:
            PathViolationError: If path is outside workspace.
        """
        workspace = self.config.workspace_dir
        original = workspace / resource_path
        v0_path = workspace / versioned_path(resource_path, 0)

        # Validate paths are within workspace
        validate_write_path(original, workspace)
        validate_write_path(v0_path, workspace)

        if original.exists() and not v0_path.exists():
            import shutil

            shutil.copy2(original, v0_path)
            logger.info(
                "Backed up original resource",
                original=str(original),
                backup=str(v0_path),
            )

    def _finalize_single_resource(self, resource_path: str) -> None:
        """Copy latest versioned file to final resource path.

        Called immediately after a resource is marked as optimized.

        Args:
            resource_path: Relative path like "agents/iac-analyzer.md"

        Raises:
            PathViolationError: If path is outside workspace.
        """
        if not self._state:
            return

        import shutil

        resource = self._state.resources.get(resource_path)
        if not resource or resource.status != "optimized":
            return

        workspace = self.config.workspace_dir
        version = resource.version

        # Handle both version > 0 (versioned) and version == 0 (original)
        if version > 0:
            versioned = workspace / versioned_path(resource_path, version)
            final = workspace / resource_path

            # Validate paths
            validate_write_path(versioned, workspace)
            validate_write_path(final, workspace)

            if versioned.exists():
                shutil.copy2(versioned, final)
                logger.info(
                    "FINALIZE: Copied versioned to final",
                    versioned=str(versioned),
                    final=str(final),
                )
            else:
                logger.error(
                    "FINALIZE: Versioned file not found",
                    expected=str(versioned),
                )
        else:
            # Version 0 means original file should exist
            final = workspace / resource_path
            if not final.exists():
                logger.error(
                    "FINALIZE: Original file not found",
                    expected=str(final),
                )

    def _finalize_resources(self) -> None:
        """Copy latest versioned files to final resource paths.

        For each optimized resource, copies {resource}-v{N}.md to {resource}.md
        so that plugins load the final version.

        Called when pipeline reaches COMPLETE phase.

        Raises:
            PathViolationError: If any path is outside workspace.
        """
        if not self._state:
            return

        for path, resource in self._state.resources.items():
            if resource.status != "optimized":
                continue

            # Use single resource finalization
            self._finalize_single_resource(path)

    # ----- mounted phase methods -----
    #
    # Phase implementations live in
    # ``harness.optimization._orchestrator_phases``.  Mounting them as
    # class attributes makes them callable as ``self.<method>()``: when a
    # plain function is assigned to a class attribute, Python's
    # descriptor protocol binds ``self`` correctly on access.

    _delegate_research = _research_phase.delegate
    _delegate_design = _design_phase.delegate
    _load_resource_plan = _design_phase.load_resource_plan
    _run_qa_phase = _qa_phase.run_phase
    _delegate_generation = _generate_phase.delegate
    _setup_workspace_dirs = _generate_phase.setup_workspace_dirs
    _get_resource_purpose = _generate_phase.get_resource_purpose
    _get_resource_instructions = _generate_phase.get_resource_instructions
    _generate_plugin_json = _generate_phase.generate_plugin_json
    _delegate_eval_design = _eval_design_phase.delegate
    _delegate_iteration = _iterate_phase.delegate
    _evaluate_resource_quality = _iterate_phase.evaluate_resource_quality
    _evaluate_resource_quality_full = _iterate_phase.evaluate_resource_quality_full
    _parse_iteration_result = _iterate_phase.parse_iteration_result
    _create_changelog_header = _iterate_phase.create_changelog_header
    _format_iteration_entry = _iterate_phase.format_iteration_entry
    _insert_changelog_entry = _iterate_phase.insert_changelog_entry
    _update_changelog = _iterate_phase.update_changelog
    _get_word_count = _iterate_phase.get_word_count
    _write_summary_json = _iterate_phase.write_summary_json
    _run_execution_eval = _execution_eval_phase.run_phase
    _delegate_validation = _validate_phase.delegate


# ---------------------------------------------------------------------------
# Module-level convenience entrypoint
# ---------------------------------------------------------------------------


def _ensure_metrics_server(port: int = 9090) -> None:
    """Start a prometheus_client HTTP server on `port` if one isn't running.

    Long-running modes (interactive, autonomous) start the metrics server
    as part of AgentSession initialization. The standalone-script path used
    by `make optimize` instantiates the orchestrator directly without ever
    creating an AgentSession, so no HTTP server gets bound and every
    `harness_eval_*` / `harness_*` / `cgf_*` instrument records into an
    in-process registry that Prometheus has no way to scrape. The Phase A
    dashboard panels stay empty as a result.

    Idempotent: a second call (e.g., from a nested run) catches the
    address-already-in-use error and continues. Failures are logged but
    never raised — metrics exposure is an observability concern, not a
    pipeline-correctness concern.
    """
    try:
        from prometheus_client import start_http_server

        start_http_server(port)
        logger.info("Metrics HTTP server started", port=port)
    except OSError as exc:
        # EADDRINUSE (98 on Linux, 48 on macOS) — another process is already
        # listening, which is fine. Anything else is unexpected but
        # non-fatal for the orchestration itself.
        if exc.errno in (48, 98):
            logger.debug("Metrics server already listening", port=port)
        else:
            logger.warning(
                "Failed to start metrics server",
                port=port,
                error=str(exc),
            )
    except Exception as exc:  # noqa: BLE001 — defensive; never fail the run
        logger.warning(
            "Failed to start metrics server",
            port=port,
            error=str(exc),
        )


async def run_multi_resource_optimization(
    workspace_dir: str | Path,
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    max_iterations: int | None = None,
    verbose: bool = False,
    research_timeout: int | None = None,
    generate_timeout: int | None = None,
    iterate_timeout: int | None = None,
    validate_timeout: int | None = None,
) -> OrchestrationResult:
    """Convenience function to run multi-resource optimization.

    Timeouts are loaded from environment variables if not specified:
    - CGF_RESEARCH_TIMEOUT (default: 1800s / 30 min)
    - CGF_GENERATE_TIMEOUT (default: 900s / 15 min)
    - CGF_ITERATE_TIMEOUT (default: 1200s / 20 min)
    - CGF_VALIDATE_TIMEOUT (default: 300s / 5 min)

    ``max_iterations`` defaults to ``CGF_MAX_ITERATIONS`` env var (matching
    the single-resource cgf_session.py contract from Phase 1 hardening) or
    ``DEFAULT_MAX_ITERATIONS`` (5) if unset. Explicit kwarg overrides both.

    Args:
        workspace_dir: Directory containing SPEC.md.
        quality_threshold: Target quality score.
        max_iterations: Max iterations per resource. ``None`` reads
            CGF_MAX_ITERATIONS env var (fallback DEFAULT_MAX_ITERATIONS=5).
        verbose: Enable verbose output.
        research_timeout: Override research phase timeout (seconds).
        generate_timeout: Override generate phase timeout (seconds).
        iterate_timeout: Override iterate phase timeout (seconds).
        validate_timeout: Override validate phase timeout (seconds).

    Returns:
        OrchestrationResult with optimization details.
    """
    # Load timeouts from env vars with defaults
    def get_timeout(name: str, override: int | None, default: int) -> int:
        if override is not None:
            return override
        env_val = os.environ.get(name)
        if env_val:
            try:
                return int(env_val)
            except ValueError:
                pass
        return default

    # max_iterations: explicit kwarg > env var > built-in default
    if max_iterations is None:
        env_iter = os.environ.get("CGF_MAX_ITERATIONS", "")
        if env_iter:
            try:
                max_iterations = int(env_iter)
            except ValueError:
                max_iterations = DEFAULT_MAX_ITERATIONS
        else:
            max_iterations = DEFAULT_MAX_ITERATIONS

    config = MultiResourceConfig(
        workspace_dir=Path(workspace_dir),
        quality_threshold=quality_threshold,
        max_iterations=max_iterations,
        verbose=verbose,
        research_timeout=get_timeout("CGF_RESEARCH_TIMEOUT", research_timeout, 1800),
        generate_timeout=get_timeout("CGF_GENERATE_TIMEOUT", generate_timeout, 900),
        iterate_timeout=get_timeout("CGF_ITERATE_TIMEOUT", iterate_timeout, 1200),
        validate_timeout=get_timeout("CGF_VALIDATE_TIMEOUT", validate_timeout, 300),
        show_progress=os.environ.get("CGF_SHOW_PROGRESS", "true").lower() == "true",
        follow_logs=os.environ.get("CGF_FOLLOW_LOGS", "true").lower() == "true",
    )

    # Expose harness_* / cgf_* / harness_eval_* instruments to Prometheus.
    # Long-running modes get this for free via AgentSession; the standalone
    # orchestrator entry point has to start the server itself or the
    # Phase A telemetry stays trapped in-process. Override port via
    # HARNESS_METRICS_PORT (default 9090, matches the container's exposed
    # port and the Prometheus scrape target).
    metrics_port = int(os.environ.get("HARNESS_METRICS_PORT", "9090"))
    _ensure_metrics_server(metrics_port)

    orchestrator = MultiResourceOrchestrator(config)
    return await orchestrator.run()
