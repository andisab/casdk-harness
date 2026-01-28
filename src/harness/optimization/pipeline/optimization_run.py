"""End-to-end optimization run orchestrator.

Ties together resource loading, test suite execution, and optimizer invocation
to provide a complete optimization pipeline.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
import yaml


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time for display."""
    if seconds < 60:
        return f"{seconds:05.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}m{secs:02d}s"

from harness.optimization.optimizers import (
    MIPRO_AVAILABLE,
    PROGRAMMATIC_ENABLED,
    TEXTGRAD_AVAILABLE,
    MIPROv2AgentOptimizer,
    OptimizationResult,
    OptimizerType,
    TextGradAgentOptimizer,
)
from harness.optimization.pipeline.config import OutputFormat, PipelineConfig
from harness.optimization.resources import AgentResource
from harness.optimization.testcases import TestSuiteLoader

logger = structlog.get_logger(__name__)


class RunPhase(str, Enum):
    """Phases of an optimization run."""

    INIT = "init"
    LOAD_RESOURCES = "load_resources"
    VALIDATE = "validate"
    BASELINE = "baseline"
    OPTIMIZE = "optimize"
    SAVE = "save"
    COMPLETE = "complete"
    FAILED = "failed"


class RunStatus(str, Enum):
    """Status of an optimization run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunSummary:
    """Summary of an optimization run.

    Attributes:
        run_id: Unique identifier for the run.
        status: Current status of the run.
        phase: Current phase of the run.
        start_time: When the run started.
        end_time: When the run ended (if complete).
        duration_seconds: Total duration in seconds.
        agent_name: Name of the agent being optimized.
        suite_name: Name of the test suite.
        optimizer_type: Type of optimizer used.
        original_score: Score before optimization.
        final_score: Score after optimization.
        improvement: Absolute improvement.
        improvement_percent: Improvement as percentage.
        iterations_completed: Number of iterations run.
        output_path: Path where results were saved.
        error: Error message if failed.
    """

    run_id: str
    status: RunStatus
    phase: RunPhase
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    agent_name: str = ""
    suite_name: str = ""
    optimizer_type: str = ""
    original_score: float = 0.0
    final_score: float = 0.0
    improvement: float = 0.0
    improvement_percent: float = 0.0
    iterations_completed: int = 0
    output_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "phase": self.phase.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "agent_name": self.agent_name,
            "suite_name": self.suite_name,
            "optimizer_type": self.optimizer_type,
            "original_score": self.original_score,
            "final_score": self.final_score,
            "improvement": self.improvement,
            "improvement_percent": self.improvement_percent,
            "iterations_completed": self.iterations_completed,
            "output_path": self.output_path,
            "error": self.error,
        }


class OptimizationRun:
    """End-to-end optimization run orchestrator.

    Manages the complete lifecycle of an optimization run:
    1. Load agent resource
    2. Load test suite
    3. Validate configuration
    4. Run baseline evaluation
    5. Execute optimization
    6. Save results

    Example:
        config = PipelineConfig(
            agent_path="agents/configs/python-expert.md",
            test_suite_path="tests/optimization/python_expert_tests.yaml",
            optimizer_type=OptimizerType.DSPY,
        )

        run = OptimizationRun(config)
        result = await run.execute()

        if result.success:
            run.save_result()
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize the optimization run.

        Args:
            config: Pipeline configuration.
        """
        self.config = config
        self.run_id = self._generate_run_id()
        self.status = RunStatus.PENDING
        self.phase = RunPhase.INIT
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

        # Loaded resources
        self.resource: AgentResource | None = None
        self.test_suite = None
        self.optimizer = None
        self.result: OptimizationResult | None = None

        # Error tracking
        self.error: str | None = None

    def _generate_run_id(self) -> str:
        """Generate unique run identifier."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        agent_name = Path(self.config.agent_path).stem
        return f"opt_{agent_name}_{timestamp}"

    def _log_phase(self, phase_name: str, message: str = "") -> None:
        """Log phase progress if verbose mode is enabled."""
        if self.config.verbose:
            elapsed = time.time() - self._exec_start_time
            msg = f"[{_format_elapsed(elapsed)}] {phase_name}"
            if message:
                msg += f": {message}"
            print(msg, file=sys.stderr, flush=True)

    async def execute(self) -> OptimizationResult:
        """Execute the complete optimization pipeline.

        Returns:
            OptimizationResult with optimized prompt.

        Raises:
            RuntimeError: If optimization fails.
        """
        self.start_time = datetime.now()
        self._exec_start_time = time.time()
        self.status = RunStatus.RUNNING

        try:
            # Phase 1: Load resources
            self.phase = RunPhase.LOAD_RESOURCES
            self._log_phase("LOAD_RESOURCES", "Loading agent and test suite")
            logger.info(
                "Loading resources",
                run_id=self.run_id,
                agent_path=str(self.config.agent_path),
                suite_path=str(self.config.test_suite_path),
            )

            self.resource = AgentResource.load(self.config.agent_path)
            self.test_suite = TestSuiteLoader.load(str(self.config.test_suite_path))
            self._log_phase(
                "LOAD_RESOURCES",
                f"Loaded {self.resource.name} with "
                f"{len(self.test_suite.test_cases)} test cases"
            )

            # Preserve original agent in workspace (if not already present)
            self._preserve_original()

            # Phase 2: Validate
            self.phase = RunPhase.VALIDATE
            self._log_phase("VALIDATE", "Validating configuration")
            self._validate()

            # Register workspace agent for optimization
            # This allows workspace agents to be used with call_agent_simple()
            self._register_workspace_agent()

            if self.config.dry_run:
                self._log_phase("DRY_RUN", "Complete")
                logger.info("Dry run complete", run_id=self.run_id)
                self.phase = RunPhase.COMPLETE
                self.status = RunStatus.COMPLETED
                return self._create_dry_run_result()

            # Phase 3: Create optimizer
            self.phase = RunPhase.OPTIMIZE
            self._log_phase(
                "OPTIMIZE",
                f"Creating {self.config.optimizer_type.value} optimizer"
            )
            self._create_optimizer()

            # Phase 4: Run optimization
            self._log_phase(
                "OPTIMIZE",
                f"Starting optimization "
                f"(max_iterations={self.config.optimization_config.max_iterations})"
            )
            logger.info(
                "Starting optimization",
                run_id=self.run_id,
                optimizer=self.config.optimizer_type.value,
                max_iterations=self.config.optimization_config.max_iterations,
            )

            self.result = await self.optimizer.optimize(
                self.resource,
                self.test_suite,
                self.config.optimization_config,
            )

            # Phase 5: Save results
            self.phase = RunPhase.SAVE
            self._log_phase("SAVE", "Saving optimization results")
            if self.config.output_path or self.result.success:
                self._save_result()

            # Complete
            self.phase = RunPhase.COMPLETE
            self.status = RunStatus.COMPLETED
            self.end_time = datetime.now()

            self._log_phase(
                "COMPLETE",
                f"Success={self.result.success}, "
                f"improvement={self.result.improvement_percent:.1f}%"
            )
            logger.info(
                "Optimization complete",
                run_id=self.run_id,
                success=self.result.success,
                improvement_percent=f"{self.result.improvement_percent:.1f}%",
                duration_seconds=self.result.total_duration_seconds,
            )

            return self.result

        except Exception as e:
            self.phase = RunPhase.FAILED
            self.status = RunStatus.FAILED
            self.error = str(e)
            self.end_time = datetime.now()

            self._log_phase("FAILED", f"Error: {str(e)}")
            logger.error(
                "Optimization failed",
                run_id=self.run_id,
                phase=self.phase.value,
                error=str(e),
            )

            # Return failure result
            return OptimizationResult(
                success=False,
                original_prompt=self.resource.system_prompt if self.resource else "",
                optimized_prompt=self.resource.system_prompt if self.resource else "",
                original_score=0.0,
                final_score=0.0,
                improvement=0.0,
                improvement_percent=0.0,
                iterations=[],
                total_iterations=0,
                total_duration_seconds=(
                    (self.end_time - self.start_time).total_seconds()
                    if self.start_time else 0.0
                ),
                config=self.config.optimization_config,
                agent_name=self.resource.name if self.resource else "",
                suite_name=self.test_suite.name if self.test_suite else "",
                error=str(e),
            )

    def _validate(self) -> None:
        """Validate configuration and resources."""
        # Check optimizer availability
        if self.config.optimizer_type == OptimizerType.DSPY:
            if not PROGRAMMATIC_ENABLED:
                raise RuntimeError(
                    "DSPy/MIPRO optimizer requested but programmatic optimization "
                    "is disabled. Set CGF_ENABLE_PROGRAMMATIC=true to enable."
                )
            if not MIPRO_AVAILABLE:
                raise RuntimeError(
                    "DSPy optimizer requested but dspy-ai not installed. "
                    "Install with: pip install 'dspy-ai>=2.5.0'"
                )

        if self.config.optimizer_type == OptimizerType.TEXTGRAD:
            if not PROGRAMMATIC_ENABLED:
                raise RuntimeError(
                    "TextGrad optimizer requested but programmatic optimization "
                    "is disabled. Set CGF_ENABLE_PROGRAMMATIC=true to enable."
                )
            if not TEXTGRAD_AVAILABLE:
                raise RuntimeError(
                    "TextGrad optimizer requested but textgrad not installed. "
                    "Install with: pip install 'textgrad>=0.1.6'"
                )

        # Validate resource
        if not self.resource.system_prompt:
            raise ValueError("Agent resource has empty system prompt")

        # Validate test suite
        if len(self.test_suite.test_cases) == 0:
            raise ValueError("Test suite has no test cases")

        logger.info(
            "Validation passed",
            run_id=self.run_id,
            agent=self.resource.name,
            test_cases=len(self.test_suite.test_cases),
        )

    def _register_workspace_agent(self) -> None:
        """Register the workspace agent for optimization.

        This allows workspace agents (not in AGENT_DEFINITIONS) to be used
        with call_agent_simple() during test execution.
        """
        from harness.direct_agent import register_workspace_agent

        register_workspace_agent(
            name=self.resource.name,
            system_prompt=self.resource.system_prompt,
            description=self.resource.description,
            model=self.resource.model,
            tools=self.resource.tools,
            max_turns=self.resource.max_turns,
        )

        logger.info(
            "Registered workspace agent",
            agent=self.resource.name,
            model=self.resource.model,
        )

    def _create_optimizer(self) -> None:
        """Create the appropriate optimizer instance."""
        if self.config.optimizer_type == OptimizerType.DSPY:
            self.optimizer = MIPROv2AgentOptimizer(
                default_config=self.config.optimization_config
            )
        elif self.config.optimizer_type == OptimizerType.TEXTGRAD:
            self.optimizer = TextGradAgentOptimizer(
                default_config=self.config.optimization_config,
                learning_rate=self.config.optimization_config.learning_rate,
            )
        else:
            raise ValueError(f"Unknown optimizer type: {self.config.optimizer_type}")

    def _create_dry_run_result(self) -> OptimizationResult:
        """Create a result for dry run mode."""
        return OptimizationResult(
            success=True,
            original_prompt=self.resource.system_prompt,
            optimized_prompt=self.resource.system_prompt,
            original_score=0.0,
            final_score=0.0,
            improvement=0.0,
            improvement_percent=0.0,
            iterations=[],
            total_iterations=0,
            total_duration_seconds=0.0,
            config=self.config.optimization_config,
            agent_name=self.resource.name,
            suite_name=self.test_suite.name,
            metadata={"dry_run": True},
        )

    def _save_result(self) -> None:
        """Save optimization result to file."""
        if self.result is None:
            return

        output_path = self.config.get_output_path()

        if self.config.output_format == OutputFormat.MARKDOWN:
            self._save_markdown(output_path)
        elif self.config.output_format == OutputFormat.JSON:
            self._save_json(output_path)
        elif self.config.output_format == OutputFormat.YAML:
            self._save_yaml(output_path)

        logger.info("Result saved", path=str(output_path))

        # Always save run summary JSON for tracking
        self._save_run_summary(output_path)

        # Save iterations if requested
        if self.config.save_iterations and self.result.iterations:
            self._save_iterations()

    def _save_markdown(self, path: Path) -> None:
        """Save result as markdown file (optimized prompt).

        Preserves original frontmatter fields (description with examples,
        color, max_turns) while adding optimization metadata.
        """
        # Build metadata preserving original fields
        metadata: dict[str, Any] = {
            "name": f"{self.resource.name}-optimized",
        }

        # Preserve original description with examples (full_description)
        # This contains the <example> blocks needed for agent discovery
        full_desc = self.resource._metadata.get("full_description", "")
        if full_desc:
            metadata["description"] = full_desc
        else:
            metadata["description"] = self.resource.description

        # Preserve model and tools
        metadata["model"] = self.resource.model
        metadata["tools"] = self.resource.tools

        # Preserve optional fields if present
        if self.resource.max_turns != 100:  # Only include if non-default
            metadata["max_turns"] = self.resource.max_turns
        if self.resource.color:
            metadata["color"] = self.resource.color

        # Add optimization metadata
        metadata["optimization"] = {
            "original_score": self.result.original_score,
            "final_score": self.result.final_score,
            "improvement_percent": f"{self.result.improvement_percent:.1f}%",
            "iterations": self.result.total_iterations,
            "optimizer": self.config.optimizer_type.value,
        }

        content = f"""---
{yaml.dump(metadata, default_flow_style=False, sort_keys=False)}---

{self.result.optimized_prompt}
"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _save_json(self, path: Path) -> None:
        """Save result as JSON file."""
        data = self.result.to_dict()
        data["pipeline_config"] = self.config.to_dict()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def _save_yaml(self, path: Path) -> None:
        """Save result as YAML file."""
        data = self.result.to_dict()
        data["pipeline_config"] = self.config.to_dict()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(data, default_flow_style=False))

    def _preserve_original(self) -> None:
        """Copy original agent definition to workspace if not already present.

        Creates a copy named {agent}-orig.md in the workspace directory
        to preserve the original state before optimization.
        """
        if self.resource is None:
            return

        agent_name = Path(self.config.agent_path).stem
        workspace_dir = Path("workspace") / agent_name
        original_path = workspace_dir / f"{agent_name}-orig.md"

        # Only copy if not already present
        if original_path.exists():
            logger.debug("Original already preserved", path=str(original_path))
            return

        # Read original file content
        source_content = Path(self.config.agent_path).read_text()

        # Create workspace directory and copy
        workspace_dir.mkdir(parents=True, exist_ok=True)
        original_path.write_text(source_content)

        logger.info("Original preserved", path=str(original_path))

    def _save_run_summary(self, output_path: Path) -> None:
        """Save run summary as JSON in the sessions folder.

        Creates a file sessions/{resource}-v{N}.summary.json with metadata
        about the optimization run for tracking and analysis.

        Args:
            output_path: Path to the main output file.
        """
        if self.result is None:
            return

        # Save to sessions/ folder for machine consumption
        sessions_dir = output_path.parent / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # Create summary filename: {resource}-v{N}.summary.json (without .md)
        summary_filename = output_path.stem + ".summary.json"
        summary_path = sessions_dir / summary_filename
        summary_data = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "agent": {
                "name": self.resource.name if self.resource else "",
                "path": str(self.config.agent_path),
            },
            "test_suite": {
                "name": self.test_suite.name if self.test_suite else "",
                "path": str(self.config.test_suite_path),
                "test_count": len(self.test_suite.test_cases) if self.test_suite else 0,
            },
            "optimizer": self.config.optimizer_type.value,
            "scores": {
                "original": self.result.original_score,
                "final": self.result.final_score,
                "improvement": self.result.improvement,
                "improvement_percent": self.result.improvement_percent,
            },
            "iterations": self.result.total_iterations,
            "duration_seconds": self.result.total_duration_seconds,
            "output_path": str(output_path),
            "config": {
                "max_iterations": self.config.optimization_config.max_iterations if self.config.optimization_config else 10,
                "learning_rate": self.config.optimization_config.learning_rate if self.config.optimization_config else 0.1,
                "early_stopping_threshold": self.config.optimization_config.early_stopping_threshold if self.config.optimization_config else 0.01,
            },
        }

        summary_path.write_text(json.dumps(summary_data, indent=2))
        logger.info("Run summary saved", path=str(summary_path))

    def _save_iterations(self) -> None:
        """Save iteration results to separate files."""
        iterations_dir = self.config.get_iterations_dir()
        if iterations_dir is None:
            # Fallback if get_iterations_dir returns None (shouldn't happen if called correctly)
            iterations_dir = Path(f"{self.run_id}_iterations")

        iterations_dir.mkdir(parents=True, exist_ok=True)

        for iteration in self.result.iterations:
            iter_path = iterations_dir / f"iteration_{iteration.iteration:03d}.json"
            iter_data = {
                "iteration": iteration.iteration,
                "best_score": iteration.best_score,
                "improvement": iteration.improvement,
                "duration_seconds": iteration.duration_seconds,
                "best_prompt": iteration.best_prompt,
                "candidates": [
                    {
                        "prompt": c.prompt,  # Full prompt, no truncation
                        "score": c.score,
                        "metadata": c.metadata,
                    }
                    for c in iteration.candidates
                ],
            }
            iter_path.write_text(json.dumps(iter_data, indent=2))

        logger.info("Iterations saved", dir=str(iterations_dir), count=len(self.result.iterations))

    def get_summary(self) -> RunSummary:
        """Get summary of the optimization run.

        Returns:
            RunSummary with current run state.
        """
        duration = 0.0
        if self.start_time:
            end = self.end_time or datetime.now()
            duration = (end - self.start_time).total_seconds()

        return RunSummary(
            run_id=self.run_id,
            status=self.status,
            phase=self.phase,
            start_time=self.start_time or datetime.now(),
            end_time=self.end_time,
            duration_seconds=duration,
            agent_name=self.resource.name if self.resource else "",
            suite_name=self.test_suite.name if self.test_suite else "",
            optimizer_type=self.config.optimizer_type.value,
            original_score=self.result.original_score if self.result else 0.0,
            final_score=self.result.final_score if self.result else 0.0,
            improvement=self.result.improvement if self.result else 0.0,
            improvement_percent=self.result.improvement_percent if self.result else 0.0,
            iterations_completed=self.result.total_iterations if self.result else 0,
            output_path=str(self.config.get_output_path()) if self.result else None,
            error=self.error,
        )
