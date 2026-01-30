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

import os
import re
import time
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


# Default configuration values
DEFAULT_QUALITY_THRESHOLD = 0.85
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_REFINEMENT = 3

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
        eval_model: Model for quality evaluation
        parallel_generation: Generate independent resources in parallel
    """

    workspace_dir: Path
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_refinements: int = DEFAULT_MAX_REFINEMENT
    verbose: bool = False
    skip_research: bool = False
    skip_qa: bool = False
    eval_model: str | None = None
    parallel_generation: bool = True


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

Save findings to workspace/{self._spec.name}/research/notes/

When complete, output:
[RESEARCH_COMPLETE]
eval_criteria_path: research/eval_criteria.yaml
"""

        logger.info(
            "RESEARCH: Delegating to cgf-research-lead",
            workspace=str(workspace),
            capabilities=len(self._spec.capabilities),
        )

        response = await call_agent_simple(
            AGENT_RESEARCH,
            prompt,
            verbose=self.config.verbose,
        )

        # Parse signal
        if "[RESEARCH_COMPLETE]" in response:
            # Extract eval_criteria_path if present
            match = re.search(r"eval_criteria_path:\s*(.+)", response)
            if match:
                self._state.research_findings_path = match.group(1).strip()

            logger.info(
                "RESEARCH: Complete",
                findings_path=self._state.research_findings_path,
            )
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
        sessions_dir = self.config.workspace_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        decisions_path = sessions_dir / "qa-decisions.json"

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
        (workspace / "skills").mkdir(parents=True, exist_ok=True)
        (workspace / "commands").mkdir(parents=True, exist_ok=True)
        (workspace / ".claude-plugin").mkdir(parents=True, exist_ok=True)

        # Load research findings for context
        eval_criteria_path = workspace / "research" / "eval_criteria.yaml"
        research_context = ""
        if eval_criteria_path.exists():
            research_context = f"\nEval criteria: {eval_criteria_path}"

        for resource in pending:
            self._state.update_resource(resource.path, status="in_progress")
            self._save_state()

            # Find resource info from spec
            name = Path(resource.path).stem
            if resource.resource_type == "skill":
                name = Path(resource.path).parent.name

            purpose = self._get_resource_purpose(name, resource.resource_type)

            prompt = f"""Generate a {resource.resource_type} for multi-resource plugin.

Workspace: {workspace}
Plugin: {self._spec.name}
Output path: {workspace / resource.path}

Resource Details:
- Name: {name}
- Type: {resource.resource_type}
- Purpose: {purpose}

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
            )

            try:
                response = await call_agent_simple(
                    AGENT_GENERATE,
                    prompt,
                    verbose=self.config.verbose,
                )

                # Parse signal
                if f"[GENERATE_COMPLETE:{resource.path}]" in response:
                    self._state.update_resource(
                        resource.path, status="generated", version=0
                    )
                    logger.info("GENERATE: Resource created", path=resource.path)
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

            except Exception as e:
                logger.error(
                    "GENERATE: Resource failed",
                    path=resource.path,
                    error=str(e),
                )
                self._state.update_resource(
                    resource.path, status="failed", error=str(e)
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

        plugin_path = self.config.workspace_dir / ".claude-plugin" / "plugin.json"
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
word_count: {{count}}
[SUMMARY]
{{1-2 sentence summary of key improvements}}
[/SUMMARY]
"""

                logger.info(
                    "ITERATE: Running iteration",
                    path=resource.path,
                    iteration=iteration,
                )

                try:
                    response = await call_agent_simple(
                        AGENT_ITERATE,
                        prompt,
                        verbose=self.config.verbose,
                    )

                    # Parse signal and quality
                    if f"[ITERATE_COMPLETE:{resource.path}]" in response:
                        # Parse iteration result
                        result = self._parse_iteration_result(response)

                        if result["quality_overall"] is not None:
                            current_quality = result["quality_overall"]
                        else:
                            # Fallback: use evaluator
                            current_quality = (
                                await self._evaluate_resource_quality(resource)
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

                        # Update state
                        quality = ResourceQuality(overall=current_quality)
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
                            logger.info(
                                "ITERATE: Resource meets threshold",
                                path=resource.path,
                                quality=f"{current_quality:.2f}",
                            )
                            break

                    else:
                        logger.warning(
                            "ITERATE: No completion signal",
                            path=resource.path,
                            iteration=iteration,
                        )

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
        if not self._evaluator or not self._spec:
            return 0.0

        workspace = self.config.workspace_dir

        # Find latest version - preserve parent directory structure
        version = resource.version
        if version > 0:
            path = workspace / _versioned_path(resource.path, version)
        else:
            path = workspace / resource.path

        if not path.exists():
            return 0.0

        content = path.read_text()

        score = await self._evaluator.evaluate(
            resource_content=content,
            resource_type=resource.resource_type,
            spec=self._spec,
            resource_name=Path(resource.path).stem,
        )

        return score.overall

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

        # Extract quality_overall: X.XX
        quality_match = re.search(r"quality_overall:\s*([\d.]+)", response)
        if quality_match:
            result["quality_overall"] = float(quality_match.group(1))

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
        )

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

        response = await call_agent_simple(
            AGENT_VALIDATE,
            prompt,
            verbose=self.config.verbose,
        )

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

            self._advance_phase(OptimizationPhase.COMPLETE)

        elif "[VALIDATE_ISSUES:" in response:
            # Extract issue count
            count_match = re.search(r"\[VALIDATE_ISSUES:(\d+)\]", response)
            issue_count = int(count_match.group(1)) if count_match else 0

            # Extract affected resources
            affected = re.findall(r"- ((?:agents|skills|commands)/[^\n]+)", response)

            logger.warning(
                "VALIDATE: Issues found",
                issue_count=issue_count,
                affected=affected,
            )

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
                        self._state.update_resource(
                            path,
                            status="needs_refinement",
                            refinement_count=(
                                self._state.resources[path].refinement_count + 1
                            ),
                        )

                # Stay in VALIDATE phase (will re-run iteration)
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
) -> OrchestrationResult:
    """Convenience function to run multi-resource optimization.

    Args:
        workspace_dir: Directory containing SPEC.md.
        quality_threshold: Target quality score.
        max_iterations: Max iterations per resource.
        verbose: Enable verbose output.

    Returns:
        OrchestrationResult with optimization details.
    """
    config = MultiResourceConfig(
        workspace_dir=Path(workspace_dir),
        quality_threshold=quality_threshold,
        max_iterations=max_iterations,
        verbose=verbose,
    )

    orchestrator = MultiResourceOrchestrator(config)
    return await orchestrator.run()
