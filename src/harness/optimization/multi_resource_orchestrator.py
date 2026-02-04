"""Multi-resource optimization orchestrator.

Coordinates the generative + iterative pipeline for multi-resource specs:
PLANNING → RESEARCH → GENERATE → ITERATE → VALIDATE → COMPLETE

Python is a thin state coordinator; agents do all the work.
State machine: spawn agent → agent outputs signal → Python parses signal → transition

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
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from harness.progress import (
    MultiResourceState,
    OptimizationPhase,
    ProgressManager,
    ResourceQuality,
    ResourceStatus,
)

from .multi_resource_spec import (
    MultiResourceSpec,
    is_multi_resource_spec,
    parse_multi_resource_spec,
)
from .quality_evaluator import QualityEvaluator

logger = structlog.get_logger(__name__)


def _versioned_path(resource_path: str | Path, version: int) -> Path:
    """Get versioned path preserving parent directory.

    Example: "agents/foo.md" + version=1 → "agents/foo-v1.md"

    Args:
        resource_path: Original resource path (e.g., "agents/iac-analyzer.md")
        version: Version number to append

    Returns:
        Path with version suffix, preserving parent directory
    """
    p = Path(resource_path)
    return p.parent / f"{p.stem}-v{version}{p.suffix}"


class PathViolationError(ValueError):
    """Raised when a file operation targets a path outside workspace."""

    pass


def validate_write_path(path: Path, workspace_root: Path) -> None:
    """Validate that a path is within the workspace root.

    Used to enforce that all file operations stay within the workspace
    directory, preventing accidental writes to the repository root or
    other system locations.

    Args:
        path: Path to validate (can be relative or absolute).
        workspace_root: Workspace root directory.

    Raises:
        PathViolationError: If path is outside workspace root.
    """
    resolved = path.resolve()
    root_resolved = workspace_root.resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathViolationError(
            f"Path violation: {path} is outside workspace {workspace_root}"
        ) from None


# Default configuration values
DEFAULT_QUALITY_THRESHOLD = 0.85
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_REFINEMENT = 1  # Reduced from 3 to limit refinement loops

# Agent names for delegation
AGENT_RESEARCH = "cgf-agents:cgf-research-lead"
AGENT_GENERATE = "context-engineering:context-engineer"
AGENT_ITERATE = "cgf-agents:cgf-prompt-optimizer"
AGENT_EVALUATE = "cgf-agents:cgf-result-evaluator"
AGENT_VALIDATE = "cgf-agents:cgf-coherence-validator"


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
    iterate_timeout: int = 600    # 10 minutes per iteration
    validate_timeout: int = 300   # 5 minutes
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


class MultiResourceOrchestrator:
    """Orchestrates multi-resource optimization pipeline via agent delegation.

    Core principle: Python is a thin state coordinator; agents do all the work.

    Pipeline phases:
    1. PLANNING - Parse SPEC.md, create initial state (Python only)
    2. RESEARCH - Delegate to cgf-research-lead (once for domain)
    3. GENERATE - Delegate to context-engineer (per resource)
    4. ITERATE - Delegate to cgf-prompt-optimizer (per resource)
    5. VALIDATE - Delegate to cgf-coherence-validator (once for all)
    6. COMPLETE - Final state update

    Each agent emits signals that Python parses to transition state.
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

        # Pre-populate resources from proposed structure if available
        for agent in self._spec.proposed_agents:
            state.add_resource(f"agents/{agent.name}.md", "agent")

        for skill in self._spec.proposed_skills:
            state.add_resource(f"skills/{skill.name}/SKILL.md", "skill")

        for command in self._spec.proposed_commands:
            name = command.name.lstrip("/")
            state.add_resource(f"commands/{name}.md", "command")

        # Save initial state
        if self._progress:
            self._progress.save_optimization_state(state)

        return state

    async def _run_pipeline(self) -> None:
        """Run the optimization pipeline from current phase."""
        if not self._state:
            raise RuntimeError("State not initialized")

        phase = self._state.current_phase

        while phase != OptimizationPhase.COMPLETE:
            logger.info("Running phase", phase=phase.name)

            if phase == OptimizationPhase.RESEARCH:
                if self.config.skip_research:
                    logger.info("Skipping RESEARCH phase (configured)")
                else:
                    await self._delegate_research()
                self._advance_phase(OptimizationPhase.QA)

            elif phase == OptimizationPhase.QA:
                if self.config.skip_qa:
                    logger.info("Skipping Q&A phase (configured)")
                else:
                    await self._run_qa_phase()
                self._advance_phase(OptimizationPhase.GENERATE)

            elif phase == OptimizationPhase.GENERATE:
                await self._delegate_generation()
                self._advance_phase(OptimizationPhase.ITERATE)

            elif phase == OptimizationPhase.ITERATE:
                await self._delegate_iteration()
                self._advance_phase(OptimizationPhase.VALIDATE)

            elif phase == OptimizationPhase.VALIDATE:
                await self._delegate_validation()
                # _delegate_validation handles phase transition
                # If transitioning to COMPLETE, finalize resources
                if self._state.current_phase == OptimizationPhase.COMPLETE:
                    self._finalize_resources()

            phase = self._state.current_phase

    def _advance_phase(self, next_phase: OptimizationPhase) -> None:
        """Advance to the next phase and save state."""
        if not self._state or not self._progress:
            return

        self._state.advance_phase(next_phase)
        self._progress.save_optimization_state(self._state)

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
        v0_path = workspace / _versioned_path(resource_path, 0)

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
            versioned = workspace / _versioned_path(resource_path, version)
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

    # -------------------------------------------------------------------------
    # Agent Delegation Methods
    # -------------------------------------------------------------------------

    async def _delegate_research(self) -> None:
        """Delegate research to cgf-research-lead agent.

        Spawns the research lead agent which decomposes optimization goals
        and spawns parallel researchers. Parses [RESEARCH_COMPLETE] signal.
        """
        if not self._spec or not self._state:
            return

        from harness.direct_agent import call_agent_simple

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
            )

        # Parse signal
        if "[RESEARCH_COMPLETE]" in response:
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

            # Extract eval_criteria_path if present
            match = re.search(r"eval_criteria_path:\s*(.+)", response)
            if match:
                self._state.research_findings_path = match.group(1).strip()

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

    async def _run_qa_phase(self) -> None:
        """Run Q&A phase - gather user input on structure decisions.

        For now, auto-accept proposed structure. In full implementation,
        this would use interactive Q&A via an initializer agent.
        """
        if not self._spec or not self._state:
            return

        logger.info("Q&A: Auto-accepting proposed structure")

        # Create decisions file
        workspace = self.config.workspace_dir
        sessions_dir = workspace / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        decisions_path = sessions_dir / "qa-decisions.json"

        # Validate path
        validate_write_path(decisions_path, workspace)

        import json

        decisions = {
            "spec_name": self._spec.name,
            "decided_at": datetime.now(UTC).isoformat(),
            "structure_accepted": True,
            "modifications": [],
            "notes": "Auto-accepted proposed structure (no Q&A required)",
        }

        with open(decisions_path, "w") as f:
            json.dump(decisions, f, indent=2)

        self._state.user_decisions_path = str(decisions_path)
        self._save_state()

        logger.info("Q&A: Complete", decisions_path=str(decisions_path))

    async def _delegate_generation(self) -> None:
        """Delegate resource generation to context-engineer agent.

        Spawns context-engineer for each pending resource.
        Parses [GENERATE_COMPLETE:{path}] signals.
        """
        if not self._spec or not self._state:
            return

        from harness.direct_agent import call_agent_simple

        workspace = self.config.workspace_dir
        pending = self._state.get_pending_resources()

        logger.info(
            "GENERATE: Creating resources",
            total=len(pending),
        )

        # Create directory structure
        (workspace / "agents").mkdir(parents=True, exist_ok=True)
        (workspace / "commands").mkdir(parents=True, exist_ok=True)
        (workspace / ".claude-plugin").mkdir(parents=True, exist_ok=True)

        # Create skill directories (skills/{name}/)
        for skill in self._spec.proposed_skills:
            (workspace / "skills" / skill.name).mkdir(parents=True, exist_ok=True)

        # Load research findings for context
        eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
        research_context = ""
        if eval_criteria_path.exists():
            research_context = f"\nEval criteria: {eval_criteria_path}"

        for resource in pending:
            # Backup original if it exists (for v0 preservation)
            self._backup_original_resource(resource.path)

            self._state.update_resource(resource.path, status="in_progress")
            self._save_state()

            # Find resource info from spec
            name = Path(resource.path).stem
            if resource.resource_type == "skill":
                name = Path(resource.path).parent.name

            purpose = self._get_resource_purpose(name, resource.resource_type)

            # Build resource-specific instructions
            resource_instructions = self._get_resource_instructions(
                name, resource.resource_type, purpose
            )

            prompt = f"""Generate a {resource.resource_type} for multi-resource plugin.

Workspace: {workspace}
Plugin: {self._spec.name}
Output path: {workspace / resource.path}

Resource Details:
- Name: {name}
- Type: {resource.resource_type}
- Purpose: {purpose}

{resource_instructions}

Constraints from SPEC.md:
{chr(10).join(f'- {c}' for c in self._spec.constraints[:5])}
{research_context}

Create the {resource.resource_type} following standard templates and best practices.
Write the file to {workspace / resource.path}.

When complete, emit signal:
[GENERATE_COMPLETE:{resource.path}]
resource_type: {resource.resource_type}
word_count: {{count}}
output_path: {workspace / resource.path}
"""

            logger.info(
                "GENERATE: Creating resource",
                path=resource.path,
                type=resource.resource_type,
                timeout=self.config.generate_timeout,
            )
            self._emit_progress("GENERATE", resource.path, "in_progress")

            try:
                # Pass timeout directly to agent
                response = await call_agent_simple(
                    AGENT_GENERATE,
                    prompt,
                    verbose=self.config.verbose or self.config.follow_logs,
                    timeout=float(self.config.generate_timeout),
                )

                # Parse signal
                if f"[GENERATE_COMPLETE:{resource.path}]" in response:
                    # Validate file actually exists before marking as generated
                    full_path = workspace / resource.path
                    if full_path.exists():
                        self._state.update_resource(
                            resource.path, status="generated", version=0
                        )
                        logger.info("GENERATE: Resource created", path=resource.path)
                        self._emit_progress("GENERATE", resource.path, "complete")
                    else:
                        logger.error(
                            "GENERATE: Signal received but file not found",
                            signal_path=resource.path,
                            expected_path=str(full_path),
                        )
                        self._state.update_resource(
                            resource.path,
                            status="failed",
                            error=f"Signal received but file not created at {full_path}",
                        )
                        self._emit_progress(
                            "GENERATE", resource.path, "failed - file not found"
                        )
                else:
                    # Check if file was created anyway
                    full_path = workspace / resource.path
                    if full_path.exists():
                        self._state.update_resource(
                            resource.path, status="generated", version=0
                        )
                        logger.info(
                            "GENERATE: Resource created (no signal)",
                            path=resource.path,
                        )
                    else:
                        self._state.update_resource(
                            resource.path,
                            status="failed",
                            error="Generation failed - file not created",
                        )
                        logger.warning(
                            "GENERATE: Resource not created",
                            path=resource.path,
                        )

            except TimeoutError:
                logger.error(
                    "GENERATE: Resource timed out",
                    path=resource.path,
                    timeout=self.config.generate_timeout,
                )
                self._state.update_resource(
                    resource.path,
                    status="failed",
                    error=f"Generation timed out after {self.config.generate_timeout}s",
                )
                self._emit_progress(
                    "GENERATE", resource.path,
                    f"timeout after {self.config.generate_timeout}s"
                )
            except Exception as e:
                logger.error(
                    "GENERATE: Resource failed",
                    path=resource.path,
                    error=str(e),
                )
                self._state.update_resource(
                    resource.path, status="failed", error=str(e)
                )

            # Retry once with simplified prompt if generation failed
            full_path = workspace / resource.path
            if (
                self._state.resources[resource.path].status == "failed"
                and not full_path.exists()
            ):
                logger.info(
                    "GENERATE: Retrying with simplified prompt",
                    path=resource.path,
                )
                self._emit_progress(
                    "GENERATE", resource.path, "retrying"
                )
                retry_prompt = (
                    f"Create {resource.resource_type} file.\n"
                    f"Write to: {full_path}\n"
                    f"Name: {name}\n"
                    f"Purpose: {purpose}\n"
                    f"Keep it focused and concise.\n"
                    f"When done, emit: "
                    f"[GENERATE_COMPLETE:{resource.path}]"
                )
                try:
                    await call_agent_simple(
                        AGENT_GENERATE,
                        retry_prompt,
                        verbose=self.config.verbose
                        or self.config.follow_logs,
                        timeout=float(self.config.generate_timeout),
                    )
                    if full_path.exists():
                        self._state.update_resource(
                            resource.path,
                            status="generated",
                            version=0,
                        )
                        logger.info(
                            "GENERATE: Resource created on retry",
                            path=resource.path,
                        )
                        self._emit_progress(
                            "GENERATE", resource.path, "complete"
                        )
                    else:
                        logger.warning(
                            "GENERATE: Retry also failed",
                            path=resource.path,
                        )
                except Exception as retry_err:
                    logger.error(
                        "GENERATE: Retry failed",
                        path=resource.path,
                        error=str(retry_err),
                    )

            self._save_state()

        # Generate plugin.json
        await self._generate_plugin_json()

        logger.info(
            "GENERATE: Complete",
            generated=len(self._state.get_generated_resources()),
            failed=len(self._state.get_failed_resources()),
        )

    def _get_resource_purpose(self, name: str, resource_type: str) -> str:
        """Get purpose for a resource from the spec."""
        if not self._spec:
            return ""

        if resource_type == "agent":
            for agent in self._spec.proposed_agents:
                if agent.name == name:
                    return agent.purpose
        elif resource_type == "skill":
            for skill in self._spec.proposed_skills:
                if skill.name == name:
                    return skill.purpose
        elif resource_type == "command":
            for cmd in self._spec.proposed_commands:
                if cmd.name.lstrip("/") == name:
                    return cmd.purpose
        return ""

    def _get_resource_instructions(
        self,
        name: str,
        resource_type: str,
        purpose: str,
    ) -> str:
        """Get resource-type-specific generation instructions.

        Args:
            name: Resource name.
            resource_type: Type of resource.
            purpose: Purpose from spec.

        Returns:
            Instruction text for the generation prompt.
        """
        if resource_type == "skill":
            # Get trigger terms if available
            triggers = []
            if self._spec:
                for skill in self._spec.proposed_skills:
                    if skill.name == name:
                        triggers = skill.triggers
                        break

            trigger_text = (
                f"Trigger terms: {', '.join(triggers)}"
                if triggers
                else "Determine appropriate trigger terms from purpose"
            )

            return f"""Skill-Specific Instructions:
- Create SKILL.md with proper YAML frontmatter (name, description)
- Description must include specific trigger terms for auto-activation
- Include "Activate when user mentions:" section
- Include "Use for:" and "Do NOT use for:" boundaries
- Keep SKILL.md under 5000 tokens (core instructions only)
- Use progressive disclosure: reference examples/ and templates/ directories
- {trigger_text}

Skill Directory Structure:
  skills/{name}/
  ├── SKILL.md          # Main skill (required)
  ├── examples/         # Usage examples (optional)
  └── templates/        # Code templates (optional)"""

        elif resource_type == "agent":
            return """Agent-Specific Instructions:
- Create agent with YAML frontmatter (name, description, tools, model)
- Description must include 2-4 concrete examples with commentary
- Use "Use PROACTIVELY when..." phrases for discovery optimization
- Specify minimal necessary tool access (least privilege)
- Include clear constraints and boundaries
- Add working code examples in the system prompt"""

        elif resource_type == "command":
            return """Command-Specific Instructions:
- Create command with YAML frontmatter (name, description, allowed_tools)
- Document all arguments ($1, $2, $ARGUMENTS)
- Provide default values for optional args (${2:-default})
- Include usage examples
- Specify allowed_tools appropriately"""

        return ""

    async def _generate_plugin_json(self) -> None:
        """Generate plugin.json metadata file."""
        if not self._spec:
            return

        import json

        plugin_json = {
            "name": self._spec.name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "description": self._spec.purpose[:200],
            "keywords": [
                self._spec.spec_type.name.lower(),
                *[cap.name.lower() for cap in self._spec.capabilities[:3]],
            ],
            "components": {
                "agents": [a.name for a in self._spec.proposed_agents],
                "skills": [s.name for s in self._spec.proposed_skills],
                "commands": [c.name for c in self._spec.proposed_commands],
            },
        }

        workspace = self.config.workspace_dir
        plugin_path = workspace / ".claude-plugin" / "plugin.json"

        # Validate path
        validate_write_path(plugin_path, workspace)

        with open(plugin_path, "w") as f:
            json.dump(plugin_json, f, indent=2)

        logger.info("GENERATE: Created plugin.json")

    async def _delegate_iteration(self) -> None:
        """Delegate resource iteration to cgf-prompt-optimizer agent.

        For each generated resource, spawns the optimizer agent.
        Parses [ITERATE_COMPLETE:{path}] signals and quality scores.
        Loops until quality >= threshold or max iterations reached.
        """
        if not self._state or not self._spec:
            return

        from harness.direct_agent import call_agent_simple

        workspace = self.config.workspace_dir

        # Get resources that need optimization
        resources_to_optimize = (
            self._state.get_generated_resources()
            + self._state.get_needs_refinement_resources()
        )

        logger.info(
            "ITERATE: Starting optimization",
            total=len(resources_to_optimize),
            threshold=self.config.quality_threshold,
        )

        for resource in resources_to_optimize:
            # Guard: skip resources with no file (e.g. failed generation)
            if resource.version == 0:
                resource_file = workspace / resource.path
                if not resource_file.exists():
                    logger.warning(
                        "ITERATE: Skipping - no file exists",
                        path=resource.path,
                    )
                    self._state.update_resource(
                        resource.path,
                        status="failed",
                        error="No file available for optimization",
                    )
                    self._save_state()
                    continue

            self._state.update_resource(resource.path, status="in_progress")
            self._save_state()

            iteration = 0
            current_quality = 0.0

            while iteration < self.config.max_iterations:
                iteration += 1

                # Build prompt for optimizer
                prompt = f"""Optimize resource for multi-resource plugin.

Workspace: {workspace}
Resource: {workspace / resource.path}
Resource type: {resource.resource_type}
Iteration: {iteration}/{self.config.max_iterations}
Quality threshold: {self.config.quality_threshold}

Plugin context:
- Name: {self._spec.name}
- Purpose: {self._spec.purpose}

Run agentic optimization (default mode).
Load eval_criteria from research/eval_criteria.yaml if available.
Apply research heuristics and self-critique.

Save optimized version to:
{workspace / _versioned_path(resource.path, resource.version + 1)}

When complete, emit signals:
[ITERATE_COMPLETE:{resource.path}]
version: {resource.version + 1}
quality_overall: {{0.0-1.0}}
quality_completeness: {{0.0-1.0}}
quality_accuracy: {{0.0-1.0}}
quality_clarity: {{0.0-1.0}}
word_count: {{count}}
[SUMMARY]
{{1-2 sentence summary of key improvements}}
[/SUMMARY]
"""

                logger.info(
                    "ITERATE: Running iteration",
                    path=resource.path,
                    iteration=iteration,
                    timeout=self.config.iterate_timeout,
                )
                self._emit_progress(
                    "ITERATE", resource.path, f"iteration {iteration}"
                )

                try:
                    # Pass timeout directly to agent
                    response = await call_agent_simple(
                        AGENT_ITERATE,
                        prompt,
                        verbose=self.config.verbose or self.config.follow_logs,
                        timeout=float(self.config.iterate_timeout),
                    )

                    # Parse signal and quality
                    if f"[ITERATE_COMPLETE:{resource.path}]" in response:
                        # Parse iteration result
                        result = self._parse_iteration_result(response)

                        # Get quality score with all dimensions
                        quality_full = None
                        if result["quality_overall"] is not None:
                            current_quality = result["quality_overall"]
                        else:
                            # Fallback: use evaluator for full quality
                            quality_full = await self._evaluate_resource_quality_full(
                                resource
                            )
                            current_quality = (
                                quality_full.overall if quality_full else 0.0
                            )

                        # Get word counts for CHANGELOG
                        workspace = self.config.workspace_dir
                        original_path = workspace / resource.path
                        word_count_before = self._get_word_count(original_path)
                        word_count_after = (
                            result["word_count"]
                            if result["word_count"]
                            else word_count_before
                        )

                        # Get quality before this iteration
                        quality_before = (
                            resource.quality.overall if resource.quality else 0.0
                        )

                        # Update CHANGELOG
                        self._update_changelog(
                            resource=resource,
                            iteration=iteration,
                            quality_before=quality_before,
                            quality_after=current_quality,
                            word_count_before=word_count_before,
                            word_count_after=word_count_after,
                            summary=result["summary"] or "",
                        )

                        # Update state with full quality dimensions
                        if quality_full:
                            quality = quality_full
                        else:
                            quality = ResourceQuality(
                                overall=current_quality,
                                completeness=result.get(
                                    "quality_completeness", 0.0
                                ),
                                accuracy=result.get("quality_accuracy", 0.0),
                                clarity=result.get("quality_clarity", 0.0),
                            )
                        self._state.update_resource(
                            resource.path,
                            version=resource.version + 1,
                            iterations=iteration,
                            quality=quality,
                        )
                        self._save_state()

                        logger.info(
                            "ITERATE: Iteration complete",
                            path=resource.path,
                            iteration=iteration,
                            quality=f"{current_quality:.2f}",
                        )

                        # Check threshold
                        if current_quality >= self.config.quality_threshold:
                            self._state.update_resource(
                                resource.path, status="optimized"
                            )
                            # Immediately finalize this resource
                            self._finalize_single_resource(resource.path)
                            logger.info(
                                "ITERATE: Resource meets threshold",
                                path=resource.path,
                                quality=f"{current_quality:.2f}",
                            )
                            self._emit_progress(
                                "ITERATE",
                                resource.path,
                                "complete",
                                current_quality,
                            )
                            break

                    else:
                        # Fallback: check if versioned file was created
                        versioned_path = workspace / _versioned_path(
                            resource.path, resource.version + 1
                        )
                        if versioned_path.exists():
                            # File exists - use evaluator for full quality
                            fallback_quality = (
                                await self._evaluate_resource_quality_full(resource)
                            )
                            current_quality = (
                                fallback_quality.overall if fallback_quality else 0.0
                            )

                            if current_quality > 0:
                                quality = (
                                    fallback_quality
                                    if fallback_quality
                                    else ResourceQuality(overall=current_quality)
                                )
                                self._state.update_resource(
                                    resource.path,
                                    version=resource.version + 1,
                                    iterations=iteration,
                                    quality=quality,
                                )
                                self._save_state()

                                logger.info(
                                    "ITERATE: File created (no signal)",
                                    path=resource.path,
                                    quality=f"{current_quality:.2f}",
                                )

                                if current_quality >= self.config.quality_threshold:
                                    self._state.update_resource(
                                        resource.path, status="optimized"
                                    )
                                    # Immediately finalize this resource
                                    self._finalize_single_resource(resource.path)
                                    break
                        else:
                            logger.warning(
                                "ITERATE: No completion signal or file",
                                path=resource.path,
                                iteration=iteration,
                            )

                except TimeoutError:
                    logger.error(
                        "ITERATE: Iteration timed out",
                        path=resource.path,
                        iteration=iteration,
                        timeout=self.config.iterate_timeout,
                    )
                    self._emit_progress(
                        "ITERATE", resource.path,
                        f"iteration {iteration} timeout"
                    )
                    break
                except Exception as e:
                    logger.error(
                        "ITERATE: Iteration failed",
                        path=resource.path,
                        iteration=iteration,
                        error=str(e),
                    )
                    break

            # Final status if not already optimized
            if self._state.resources[resource.path].status != "optimized":
                if current_quality > 0:
                    self._state.update_resource(
                        resource.path, status="needs_refinement"
                    )
                else:
                    self._state.update_resource(
                        resource.path,
                        status="failed",
                        error="Optimization failed to produce quality score",
                    )

            self._save_state()

        logger.info(
            "ITERATE: Complete",
            optimized=len(self._state.get_optimized_resources()),
            needs_refinement=len(self._state.get_needs_refinement_resources()),
            failed=len(self._state.get_failed_resources()),
        )

    async def _evaluate_resource_quality(
        self, resource: ResourceStatus
    ) -> float:
        """Evaluate resource quality using the quality evaluator.

        Args:
            resource: Resource to evaluate.

        Returns:
            Quality score (0.0-1.0).
        """
        quality = await self._evaluate_resource_quality_full(resource)
        return quality.overall if quality else 0.0

    async def _evaluate_resource_quality_full(
        self, resource: ResourceStatus
    ) -> ResourceQuality | None:
        """Evaluate resource quality and return full dimension scores.

        Args:
            resource: Resource to evaluate.

        Returns:
            ResourceQuality with all dimension scores, or None on failure.
        """
        if not self._evaluator or not self._spec:
            return None

        workspace = self.config.workspace_dir

        # Find latest version - preserve parent directory structure
        version = resource.version
        if version > 0:
            path = workspace / _versioned_path(resource.path, version)
        else:
            path = workspace / resource.path

        if not path.exists():
            return None

        content = path.read_text()

        score = await self._evaluator.evaluate(
            resource_content=content,
            resource_type=resource.resource_type,
            spec=self._spec,
            resource_name=Path(resource.path).stem,
        )

        # Map QualityScore to ResourceQuality
        return ResourceQuality(
            completeness=score.completeness,
            accuracy=score.accuracy,
            clarity=score.clarity,
            overall=score.overall,
        )

    # -------------------------------------------------------------------------
    # CHANGELOG Management Methods
    # -------------------------------------------------------------------------

    def _parse_iteration_result(self, response: str) -> dict[str, Any]:
        """Parse agent response for quality, word count, and summary.

        Args:
            response: Raw response from cgf-prompt-optimizer agent.

        Returns:
            Dict with keys: quality_overall, word_count, summary
        """
        result: dict[str, Any] = {
            "quality_overall": None,
            "word_count": None,
            "summary": None,
        }

        # Extract quality_overall: X.XX (multiple patterns for permissiveness)
        quality_patterns = [
            r"quality_overall:\s*([\d.]+)",
            r"quality:\s*([\d.]+)",
            r"overall[_\s]?score:\s*([\d.]+)",
            r"score:\s*([\d.]+)",
        ]
        for pattern in quality_patterns:
            quality_match = re.search(pattern, response, re.IGNORECASE)
            if quality_match:
                val = float(quality_match.group(1))
                # Ensure it's a valid quality score (0.0-1.0)
                if 0.0 <= val <= 1.0:
                    result["quality_overall"] = val
                    break

        # Extract dimension scores (completeness, accuracy, clarity)
        for dim in ["completeness", "accuracy", "clarity"]:
            for pattern in [
                rf"quality_{dim}:\s*([\d.]+)",
                rf"{dim}:\s*([\d.]+)",
            ]:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    val = float(match.group(1))
                    if 0.0 <= val <= 1.0:
                        result[f"quality_{dim}"] = val
                        break

        # Extract word_count: XXX
        word_match = re.search(r"word_count:\s*(\d+)", response)
        if word_match:
            result["word_count"] = int(word_match.group(1))

        # Extract [SUMMARY]...[/SUMMARY]
        summary_match = re.search(
            r"\[SUMMARY\]\s*(.*?)\s*\[/SUMMARY\]", response, re.DOTALL
        )
        if summary_match:
            result["summary"] = summary_match.group(1).strip()

        return result

    def _create_changelog_header(self, changelog_path: Path) -> None:
        """Create CHANGELOG.md with header.

        Args:
            changelog_path: Path to write CHANGELOG.md
        """
        if not self._spec:
            return

        # Determine resource counts from state
        resource_counts: dict[str, int] = {}
        if self._state:
            for resource in self._state.resources.values():
                rtype = resource.resource_type
                resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

        counts_str = ", ".join(
            f"{count} {rtype}{'s' if count > 1 else ''}"
            for rtype, count in sorted(resource_counts.items())
        )

        header = f"""# CGF Optimization Changelog: {self._spec.name}

**Plugin:** {self._spec.name}
**Resources:** {counts_str or 'TBD'}
**Mode:** agentic
**Started:** {datetime.now(UTC).strftime('%Y-%m-%d')}
**Status:** IN_PROGRESS

---
"""
        # Validate path
        validate_write_path(changelog_path, self.config.workspace_dir)

        changelog_path.write_text(header)
        logger.info("CHANGELOG: Created", path=str(changelog_path))

    def _format_iteration_entry(
        self,
        resource: ResourceStatus,
        iteration: int,
        quality_before: float,
        quality_after: float,
        word_count_before: int,
        word_count_after: int,
        summary: str,
    ) -> str:
        """Format a single iteration entry for CHANGELOG.

        Args:
            resource: The resource being optimized
            iteration: Iteration number
            quality_before: Quality score before this iteration
            quality_after: Quality score after this iteration
            word_count_before: Word count before
            word_count_after: Word count after
            summary: Summary of changes from agent

        Returns:
            Formatted markdown entry
        """
        # Calculate deltas
        quality_delta = quality_after - quality_before
        quality_pct = (
            f"+{quality_delta * 100:.0f}%"
            if quality_delta >= 0
            else f"{quality_delta * 100:.0f}%"
        )

        word_delta = word_count_after - word_count_before
        word_pct = (
            f"+{(word_delta / word_count_before * 100):.0f}%"
            if word_count_before > 0
            else "N/A"
        )

        version = resource.version + 1
        versioned = _versioned_path(resource.path, version)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        entry = f"""
### Iteration {iteration} ({date_str})

**Output:** {versioned}
**Quality:** {quality_before:.2f} → {quality_after:.2f} ({quality_pct})
**Words:** {word_count_before} → {word_count_after} ({word_pct})

#### Summary

{summary or 'No summary provided.'}

---
"""
        return entry

    def _insert_changelog_entry(
        self,
        changelog_path: Path,
        resource_path: str,
        entry: str,
    ) -> None:
        """Insert entry into appropriate resource section of CHANGELOG.

        For multi-resource, organizes entries by resource path.

        Args:
            changelog_path: Path to CHANGELOG.md
            resource_path: Resource path for section header
            entry: Formatted iteration entry
        """
        content = changelog_path.read_text()

        # Resource section header
        section_header = f"## Resource: {resource_path}"

        if section_header in content:
            # Insert after section header (before first ### Iteration)
            section_start = content.index(section_header)
            after_header = section_start + len(section_header)
            # Find the next line after section header
            next_newline = content.find("\n", after_header)
            if next_newline == -1:
                next_newline = len(content)
            insert_pos = next_newline + 1
            content = content[:insert_pos] + entry + content[insert_pos:]
        else:
            # Create new resource section
            # Insert before first resource section or at end of header
            first_resource = content.find("\n## Resource:")
            if first_resource != -1:
                # Insert before existing resource sections
                insert_pos = first_resource + 1
            else:
                # Insert after header separator
                header_end = content.find("---\n")
                if header_end != -1:
                    insert_pos = header_end + 4  # After "---\n"
                else:
                    insert_pos = len(content)

            new_section = f"\n{section_header}\n{entry}"
            content = content[:insert_pos] + new_section + content[insert_pos:]

        # Validate path
        validate_write_path(changelog_path, self.config.workspace_dir)

        changelog_path.write_text(content)
        logger.info(
            "CHANGELOG: Entry added",
            resource=resource_path,
            path=str(changelog_path),
        )

    def _update_changelog(
        self,
        resource: ResourceStatus,
        iteration: int,
        quality_before: float,
        quality_after: float,
        word_count_before: int,
        word_count_after: int,
        summary: str,
    ) -> None:
        """Update unified CHANGELOG.md with resource iteration entry.

        Creates header on first call. Appends to resource section on subsequent
        calls. For multi-resource, organizes entries by resource path.

        Args:
            resource: The resource being optimized
            iteration: Iteration number
            quality_before: Quality score before iteration
            quality_after: Quality score after iteration
            word_count_before: Word count before
            word_count_after: Word count after
            summary: Summary of improvements from agent
        """
        changelog_path = self.config.workspace_dir / "CHANGELOG.md"

        # Build iteration entry
        entry = self._format_iteration_entry(
            resource,
            iteration,
            quality_before,
            quality_after,
            word_count_before,
            word_count_after,
            summary,
        )

        if not changelog_path.exists():
            # Create with header
            self._create_changelog_header(changelog_path)

        # Insert entry into appropriate resource section
        self._insert_changelog_entry(changelog_path, resource.path, entry)

    def _get_word_count(self, path: Path) -> int:
        """Get word count from a file.

        Args:
            path: Path to file

        Returns:
            Word count, or 0 if file doesn't exist
        """
        if not path.exists():
            return 0
        content = path.read_text()
        return len(content.split())

    async def _delegate_validation(self) -> None:
        """Delegate coherence validation to cgf-coherence-validator agent.

        Spawns the validator for all optimized resources.
        Parses [VALIDATE_COMPLETE] or [VALIDATE_ISSUES:{count}] signals.
        On issues, loops affected resources back to ITERATE.
        """
        if not self._state or not self._spec:
            return

        from harness.direct_agent import call_agent_simple

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
        if "[VALIDATE_COMPLETE]" in response:
            # Extract coherence score
            score_match = re.search(r"coherence_score:\s*([\d.]+)", response)
            coherence_score = (
                float(score_match.group(1)) if score_match else 1.0
            )

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

        elif "[VALIDATE_ISSUES:" in response:
            # Extract issue count
            count_match = re.search(r"\[VALIDATE_ISSUES:(\d+)\]", response)
            issue_count = int(count_match.group(1)) if count_match else 0

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


async def run_multi_resource_optimization(
    workspace_dir: str | Path,
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
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
    - CGF_ITERATE_TIMEOUT (default: 600s / 10 min)
    - CGF_VALIDATE_TIMEOUT (default: 300s / 5 min)

    Args:
        workspace_dir: Directory containing SPEC.md.
        quality_threshold: Target quality score.
        max_iterations: Max iterations per resource.
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

    config = MultiResourceConfig(
        workspace_dir=Path(workspace_dir),
        quality_threshold=quality_threshold,
        max_iterations=max_iterations,
        verbose=verbose,
        research_timeout=get_timeout("CGF_RESEARCH_TIMEOUT", research_timeout, 1800),
        generate_timeout=get_timeout("CGF_GENERATE_TIMEOUT", generate_timeout, 900),
        iterate_timeout=get_timeout("CGF_ITERATE_TIMEOUT", iterate_timeout, 600),
        validate_timeout=get_timeout("CGF_VALIDATE_TIMEOUT", validate_timeout, 300),
        show_progress=os.environ.get("CGF_SHOW_PROGRESS", "true").lower() == "true",
        follow_logs=os.environ.get("CGF_FOLLOW_LOGS", "true").lower() == "true",
    )

    orchestrator = MultiResourceOrchestrator(config)
    return await orchestrator.run()
