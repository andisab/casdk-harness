"""CGF Optimization session entry point.

This module provides the main orchestration for CGF optimization sessions.
It manages the two-phase workflow:
1. Q&A Phase: cgf-initializer agent gathers requirements interactively
2. Optimization Phase: cgf-orchestrator runs autonomous optimization

Usage:
    # Discover workspace by finding SPEC.md
    python -m harness.cgf_session

    # Explicit path when multiple SPEC.md exist
    python -m harness.cgf_session --path workspace/python-expert

    # Legacy mode (agent name)
    python -m harness.cgf_session --agent python-expert [--goal "..."]

Workspace Structure (SPEC.md location = workspace root):
    {workspace_root}/                  # Directory containing SPEC.md
    ├── SPEC.md                        # Optimization spec (user OR Q&A-generated)
    ├── {resource}.md                  # Original resource (never modified)
    ├── {resource}-v1.md               # First optimization
    ├── {resource}-v2.md               # Second optimization (if REFINE)
    ├── research/                      # Created during RESEARCH phase
    │   ├── notes/
    │   │   └── *.yaml                 # Research findings
    │   ├── eval_criteria.yaml         # Evaluation criteria
    │   └── reviews/                   # Created during EVALUATE phase
    │       └── v1_review.md
    └── sessions/                      # Runtime state (delete to reset)
        ├── task_list.json             # Phase tracking
        └── qa_session.json            # Q&A history

Key Principle:
    SPEC.md location defines the workspace root. All files are created
    relative to its location. User chooses where to create SPEC.md.
    CGF discovers it and uses that directory.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from harness.agent import AgentSession
from harness.cli import parse_and_print_message
from harness.config import (
    RuntimeConfig,
    get_config,
)
from harness.monitoring import (
    init_run_phases,
    record_iteration,
    record_phase_entry,
    record_run_path,
)

# Load prompts from files
PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = structlog.get_logger(__name__)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt from the prompts directory.

    Args:
        prompt_name: Name of prompt file (without .md extension)

    Returns:
        Prompt content as string
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    with open(prompt_path) as f:
        return f.read()


@dataclass
class CGFSpec:
    """Optimization specification from Q&A phase.

    Defaults read from environment variables (can be overridden in Q&A).
    """

    resource_path: Path
    resource_type: str  # agent, skill, command
    optimization_goal: str
    target_sections: list[str] | None = None
    target_competencies: list[str] | None = None

    # Defaults from .env (can be overridden in Q&A)
    optimizer_mode: str = field(
        default_factory=lambda: os.environ.get("CGF_OPTIMIZER_MODE", "agentic")
    )
    max_iterations: int = field(
        default_factory=lambda: int(os.environ.get("CGF_ITERATIONS", "10"))
    )
    iteration_review: bool = field(
        default_factory=lambda: os.environ.get("CGF_ITERATION_REVIEW", "").lower()
        == "true"
    )
    eval_model: str = field(
        default_factory=lambda: os.environ.get("CGF_EVAL_MODEL", "sonnet")
    )
    verbose: bool = field(
        default_factory=lambda: os.environ.get("CGF_VERBOSE", "true").lower() == "true"
    )

    @property
    def needs_tests(self) -> bool:
        """Whether this mode requires test suite generation."""
        return self.optimizer_mode in ("python", "both")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "resource_path": str(self.resource_path),
            "resource_type": self.resource_type,
            "optimization_goal": self.optimization_goal,
            "optimizer_mode": self.optimizer_mode,
            "max_iterations": self.max_iterations,
            "iteration_review": self.iteration_review,
            "eval_model": self.eval_model,
            "verbose": self.verbose,
        }
        if self.target_sections:
            result["target_sections"] = self.target_sections
        if self.target_competencies:
            result["target_competencies"] = self.target_competencies
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CGFSpec":
        """Create CGFSpec from dictionary."""
        return cls(
            resource_path=Path(data["resource_path"]),
            resource_type=data["resource_type"],
            optimization_goal=data["optimization_goal"],
            target_sections=data.get("target_sections"),
            target_competencies=data.get("target_competencies"),
            optimizer_mode=data.get(
                "optimizer_mode", os.environ.get("CGF_OPTIMIZER_MODE", "agentic")
            ),
            max_iterations=data.get(
                "max_iterations", int(os.environ.get("CGF_ITERATIONS", "10"))
            ),
            iteration_review=data.get(
                "iteration_review",
                os.environ.get("CGF_ITERATION_REVIEW", "").lower() == "true",
            ),
            eval_model=data.get(
                "eval_model", os.environ.get("CGF_EVAL_MODEL", "sonnet")
            ),
            verbose=data.get(
                "verbose", os.environ.get("CGF_VERBOSE", "true").lower() == "true"
            ),
        )

    def save(self, workspace_dir: Path) -> Path:
        """Save spec to workspace directory.

        Args:
            workspace_dir: Directory to save cgf_spec.yaml

        Returns:
            Path to saved file
        """
        spec_path = workspace_dir / "cgf_spec.yaml"
        with open(spec_path, "w") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        logger.info("CGF spec saved", path=str(spec_path))
        return spec_path

    @classmethod
    def load(cls, workspace_dir: Path) -> "CGFSpec | None":
        """Load spec from workspace directory.

        Args:
            workspace_dir: Directory containing cgf_spec.yaml

        Returns:
            CGFSpec if found, None otherwise
        """
        spec_path = workspace_dir / "cgf_spec.yaml"
        if not spec_path.exists():
            return None

        with open(spec_path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    @classmethod
    def from_spec_md(cls, spec_md_path: Path) -> "CGFSpec | None":
        """Parse CGFSpec from a SPEC.md file.

        SPEC.md is a user-written or Q&A-generated markdown file that
        defines optimization parameters in a human-readable format.

        Args:
            spec_md_path: Path to SPEC.md file

        Returns:
            CGFSpec if parseable, None otherwise
        """
        if not spec_md_path.exists():
            return None

        content = spec_md_path.read_text()
        workspace_dir = spec_md_path.parent

        # Extract resource file from ## Resource section
        resource_match = re.search(
            r"\*\*File:\*\*\s*([^\n]+)", content
        )
        if not resource_match:
            # Try alternate format
            resource_match = re.search(
                r"- \*\*File:\*\*\s*([^\n]+)", content
            )

        # Extract resource type
        type_match = re.search(
            r"\*\*Type:\*\*\s*(\w+)", content
        )
        resource_type = type_match.group(1).lower() if type_match else "agent"

        # Extract optimization goal from ## Optimization Goals section
        goal_match = re.search(
            r"## Optimization Goals?\n+((?:- [^\n]+\n?)+)",
            content,
            re.MULTILINE
        )
        if goal_match:
            # Parse bullet points into goal string
            goals = goal_match.group(1).strip()
            goal_lines = [
                line.lstrip("- ").strip()
                for line in goals.split("\n")
                if line.strip().startswith("-")
            ]
            optimization_goal = "; ".join(goal_lines)
        else:
            # Try single-line goal format
            single_goal = re.search(
                r"\*\*Goal:\*\*\s*([^\n]+)", content
            )
            optimization_goal = (
                single_goal.group(1).strip() if single_goal else "General optimization"
            )

        # Determine resource path
        if resource_match:
            resource_file = resource_match.group(1).strip()
            # Handle relative or absolute paths
            if resource_file.startswith("/"):
                resource_path = Path(resource_file)
            else:
                resource_path = workspace_dir / resource_file
        else:
            # Try to find any .md file that's not SPEC.md
            md_files = [
                f for f in workspace_dir.glob("*.md")
                if f.name != "SPEC.md" and not f.name.endswith("-orig.md")
                and not re.match(r".*-v\d+\.md$", f.name)
            ]
            if md_files:
                resource_path = md_files[0]
            else:
                return None

        # Extract Q&A session settings if present
        optimizer_mode = os.environ.get("CGF_OPTIMIZER_MODE", "agentic")
        max_iterations = int(os.environ.get("CGF_ITERATIONS", "10"))
        iteration_review = os.environ.get(
            "CGF_ITERATION_REVIEW", ""
        ).lower() == "true"
        eval_model = os.environ.get("CGF_EVAL_MODEL", "sonnet")

        # Parse Q&A Session Results section if present
        qa_section = re.search(
            r"## Q&A Session Results(.*?)(?=^## |\Z)",
            content,
            re.MULTILINE | re.DOTALL
        )
        if qa_section:
            qa_content = qa_section.group(1)

            # Extract mode from Q&A
            mode_match = re.search(
                r"\*\*Mode:\*\*\s*(\w+)", qa_content
            )
            if mode_match:
                optimizer_mode = mode_match.group(1).lower()

            # Extract iterations
            iter_match = re.search(
                r"max_iterations:\s*(\d+)", qa_content
            )
            if iter_match:
                max_iterations = int(iter_match.group(1))

            # Extract review setting
            review_match = re.search(
                r"iteration_review:\s*(true|false)", qa_content, re.IGNORECASE
            )
            if review_match:
                iteration_review = review_match.group(1).lower() == "true"

        # Extract target sections from ## Target Improvements
        target_sections = None
        target_match = re.search(
            r"## Target (?:Improvements|Sections)\n+((?:- \[.\] [^\n]+\n?)+)",
            content,
            re.MULTILINE
        )
        if target_match:
            # Parse checkbox items
            items = target_match.group(1).strip()
            target_sections = [
                re.sub(r"^- \[.\]\s*", "", line).strip()
                for line in items.split("\n")
                if line.strip()
            ]

        return cls(
            resource_path=resource_path,
            resource_type=resource_type,
            optimization_goal=optimization_goal,
            target_sections=target_sections,
            optimizer_mode=optimizer_mode,
            max_iterations=max_iterations,
            iteration_review=iteration_review,
            eval_model=eval_model,
        )


@dataclass
class CGFQASession:
    """Tracks CGF Q&A session state for persistence.

    Allows users to quit the Q&A session and resume later,
    maintaining context of questions asked and answers received.
    """

    started_at: str
    resource_hash: str  # Hash of resource file to detect changes
    total_questions: int = 0
    current_question: int = 0
    questions_asked: list[str] = field(default_factory=list)
    answers_received: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    status: str = "in_progress"  # "in_progress" | "completed"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "started_at": self.started_at,
            "resource_hash": self.resource_hash,
            "total_questions": self.total_questions,
            "current_question": self.current_question,
            "questions_asked": self.questions_asked,
            "answers_received": self.answers_received,
            "conversation_history": self.conversation_history,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CGFQASession":
        """Create CGFQASession from dictionary."""
        return cls(
            started_at=data["started_at"],
            resource_hash=data["resource_hash"],
            total_questions=data.get("total_questions", 0),
            current_question=data.get("current_question", 0),
            questions_asked=data.get("questions_asked", []),
            answers_received=data.get("answers_received", []),
            conversation_history=data.get("conversation_history", []),
            status=data.get("status", "in_progress"),
        )

    def is_resumable(self) -> bool:
        """Check if session can be resumed."""
        return self.status == "in_progress" and len(self.conversation_history) > 0

    def add_exchange(self, question: str, answer: str) -> None:
        """Record a Q&A exchange."""
        self.questions_asked.append(question)
        self.answers_received.append(answer)
        self.conversation_history.append({"role": "assistant", "content": question})
        self.conversation_history.append({"role": "user", "content": answer})
        self.current_question += 1


# Valid CGF phases (state machine states)
CGF_PHASES = (
    "qa",  # Q&A phase (gathering requirements)
    "research",  # Research phase (domain knowledge)
    "iterate",  # Agentic optimization using research
    "evaluate",  # Result evaluation
    "finalize",  # Final review and acceptance
    "complete",  # Terminal state
)


@dataclass
class CGFTaskList:
    """Runtime state for CGF optimization (stored as task_list.json).

    This replaces run_state.json and run_config.yaml with a single state file
    that references cgf_spec.yaml (immutable Q&A output) rather than duplicating
    its fields.

    Named task_list.json for consistency with autonomous mode (different structure).
    """

    # Immutable reference to spec (no duplication)
    spec_path: str  # Path to cgf_spec.yaml

    # State machine (phase-based, not task-based)
    current_phase: str  # One of CGF_PHASES

    # Progress tracking
    iteration: int = 0
    total_iterations: int = 0

    # Checkpoints (recorded phase completions)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    # Format: {"phase": str, "timestamp": str, "artifact": str, "description": str}

    # Error tracking
    error: str | None = None

    # Baseline integrity (P0.1): SHA-256 of the pristine resource file,
    # captured at the start of _run_optimization_phase.  Re-checked before
    # each phase signal is processed; mismatch hard-fails the run.
    baseline_hash: str | None = None

    # Last evaluator recommendation (P0.4): parsed from
    # reviews/v{N}_review.md after each [EVALUATE_COMPLETE].
    # One of: ACCEPT, REFINE, REJECT, or None (before first evaluation).
    last_recommendation: str | None = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_path": self.spec_path,
            "current_phase": self.current_phase,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
            "checkpoints": self.checkpoints,
            "error": self.error,
            "baseline_hash": self.baseline_hash,
            "last_recommendation": self.last_recommendation,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CGFTaskList":
        """Create CGFTaskList from dictionary."""
        return cls(
            spec_path=data["spec_path"],
            current_phase=data["current_phase"],
            iteration=data.get("iteration", 0),
            total_iterations=data.get("total_iterations", 0),
            checkpoints=data.get("checkpoints", []),
            error=data.get("error"),
            baseline_hash=data.get("baseline_hash"),
            last_recommendation=data.get("last_recommendation"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", ""),
        )

    def save(self, workspace: Path) -> None:
        """Save to sessions/task_list.json in workspace directory."""
        self.updated_at = datetime.now(UTC).isoformat()
        sessions_path = workspace / "sessions"
        sessions_path.mkdir(parents=True, exist_ok=True)
        task_list_path = sessions_path / "task_list.json"
        with open(task_list_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.debug(
            "CGF task list saved",
            path=str(task_list_path),
            phase=self.current_phase
        )

    @classmethod
    def load(cls, workspace: Path) -> "CGFTaskList | None":
        """Load from sessions/task_list.json in workspace directory.

        Args:
            workspace: Directory containing sessions/task_list.json

        Returns:
            CGFTaskList if found, None otherwise
        """
        task_list_path = workspace / "sessions" / "task_list.json"
        if not task_list_path.exists():
            # Check legacy location for backwards compatibility
            legacy_path = workspace / "task_list.json"
            if legacy_path.exists():
                with open(legacy_path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            return None

        with open(task_list_path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def add_checkpoint(self, phase: str, artifact: str, description: str) -> None:
        """Record a phase checkpoint.

        Args:
            phase: The phase that completed
            artifact: Path to the artifact produced
            description: Human-readable description
        """
        self.checkpoints.append({
            "phase": phase,
            "timestamp": datetime.now(UTC).isoformat(),
            "artifact": artifact,
            "description": description,
        })

    def is_complete(self) -> bool:
        """Check if optimization has completed."""
        return self.current_phase == "complete"

    def is_resumable(self) -> bool:
        """Check if optimization can be resumed."""
        return self.current_phase not in ("complete", "qa")


class CGFSessionRunner:
    """Orchestrates CGF optimization sessions.

    Supports two modes:
    1. SPEC.md discovery: Find SPEC.md in workspace and use its parent as root
    2. Agent name (legacy): Create workspace at workspace/{agent_name}/
    """

    def __init__(
        self,
        agent_name: str | None = None,
        workspace_base: Path | None = None,  # Defaults to /workspace in container
        workspace_path: Path | None = None,  # Explicit path (overrides discovery)
        goal: str | None = None,
        model: str | None = None,
        quiet: bool = False,
        non_interactive: bool = False,
    ) -> None:
        """Initialize the CGF session runner.

        Args:
            agent_name: Name of the agent to optimize (legacy mode)
            workspace_base: Base directory for workspaces (default: /workspace)
            workspace_path: Explicit workspace path (overrides discovery)
            goal: Optional optimization goal (bypasses Q&A if provided)
            model: Claude model to use (defaults to config)
            quiet: Suppress system logs
            non_interactive: Auto-continue at every phase checkpoint (no stdin prompts)
        """
        self.agent_name = agent_name
        self.workspace_base = workspace_base or Path("/workspace")
        self.workspace_path_override = workspace_path
        self.workspace_dir: Path | None = None  # Set during discovery
        self.goal = goal
        self.model_override = model
        self.quiet = quiet
        self.non_interactive = non_interactive or os.environ.get(
            "CGF_NON_INTERACTIVE", ""
        ).lower() in ("1", "true", "yes")
        self.config = get_config()
        self._shutdown_requested = False
        self._shutdown_event: asyncio.Event | None = None
        self.console = Console()
        self.resource_name: str | None = None  # Derived from resource file

    def _create_runtime_config(
        self, permission_mode: str = "acceptEdits"
    ) -> RuntimeConfig:
        """Create RuntimeConfig for CGF session."""
        return RuntimeConfig.from_harness_config(
            self.config,
            mode="autonomous",
            model_override=self.model_override,
            quiet=self.quiet,
            permission_mode_override=permission_mode,
        )

    def _discover_workspace(self) -> Path | None:
        """Discover workspace by finding SPEC.md.

        SPEC.md location defines the workspace root. This method searches
        for SPEC.md files and uses the parent directory as workspace.

        Returns:
            Path to workspace directory if found, None otherwise
        """
        # If explicit path provided, use it
        if self.workspace_path_override:
            if self.workspace_path_override.is_dir():
                return self.workspace_path_override
            elif self.workspace_path_override.name == "SPEC.md":
                return self.workspace_path_override.parent
            return None

        # Search for SPEC.md files in workspace_base
        spec_files = list(self.workspace_base.rglob("SPEC.md"))

        if len(spec_files) == 0:
            return None
        elif len(spec_files) == 1:
            return spec_files[0].parent
        else:
            # Multiple found - show list and return None
            self.console.print(
                "[yellow]Multiple SPEC.md files found:[/yellow]"
            )
            for path in spec_files:
                rel_path = path.parent.relative_to(self.workspace_base)
                self.console.print(f"  - {rel_path}/")
            self.console.print(
                "\n[dim]Use --path to specify which workspace to use[/dim]"
            )
            return None

    def _get_sessions_path(self) -> Path:
        """Get sessions directory for runtime state files.

        The sessions/ directory contains runtime state that can be
        deleted to reset the optimization without losing artifacts.

        Returns:
            Path to sessions/ directory (creates if needed)
        """
        if self.workspace_dir is None:
            raise RuntimeError("workspace_dir not set")
        sessions_path = self.workspace_dir / "sessions"
        sessions_path.mkdir(parents=True, exist_ok=True)
        return sessions_path

    def _get_research_path(self) -> Path:
        """Get research directory for artifacts.

        Returns:
            Path to research/ directory (creates if needed)
        """
        if self.workspace_dir is None:
            raise RuntimeError("workspace_dir not set")
        research_path = self.workspace_dir / "research"
        research_path.mkdir(parents=True, exist_ok=True)
        return research_path

    def _derive_resource_name(self, resource_path: Path) -> str:
        """Derive resource name from file path.

        Args:
            resource_path: Path to resource file

        Returns:
            Resource name (filename without extension)
        """
        name = resource_path.stem
        # Handle SKILL.md -> use parent directory name
        if name.upper() == "SKILL":
            name = resource_path.parent.name
        return name

    def _setup_signal_handlers(self) -> None:
        """Set up async signal handlers in the running event loop."""
        loop = asyncio.get_running_loop()

        # Only handle SIGTERM - let SIGINT use default KeyboardInterrupt behavior
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(self._handle_signal(signal.SIGTERM)),
        )
        logger.debug("Async signal handlers installed", signals=["SIGTERM"])

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signals asynchronously."""
        sig_name = sig.name if hasattr(sig, "name") else str(sig)
        logger.info("Shutdown signal received", signal=sig_name)
        self._shutdown_requested = True

        if self._shutdown_event is not None:
            self._shutdown_event.set()

    async def _interruptible_delay(self, seconds: int) -> bool:
        """Wait with Ctrl+C interrupt capability.

        Args:
            seconds: Number of seconds to wait

        Returns:
            True if interrupted (shutdown requested), False if timeout elapsed
        """
        self.console.print(
            f"[dim]Continuing in {seconds}s... (Ctrl+C to pause)[/dim]"
        )
        try:
            if self._shutdown_event is None:
                await asyncio.sleep(seconds)
                return False
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=seconds,
            )
            # If we get here, shutdown was requested
            return True
        except TimeoutError:
            # Normal timeout, continue
            return False

    async def _prompt_checkpoint(
        self, phase: str, artifact_path: str | None = None
    ) -> str:
        """Prompt user at phase checkpoint.

        Displays phase completion status and prompts for action.

        Args:
            phase: The phase that just completed
            artifact_path: Optional path to the artifact produced

        Returns:
            User's choice: "continue", "edit", or "abort"
        """
        self.console.print()
        self.console.print(
            Panel(
                f"[bold green]{phase.upper()}[/bold green] phase complete",
                border_style="cyan",
                padding=(0, 2),
            )
        )

        if artifact_path:
            self.console.print(f"  [dim]Artifact: {artifact_path}[/dim]")

        if self.non_interactive:
            self.console.print("  [dim](non-interactive: auto-continue)[/dim]")
            return "continue"

        self.console.print()
        self.console.print("  [bold cyan][C][/bold cyan]ontinue to next phase")
        self.console.print("  [bold cyan][E][/bold cyan]dit resource file first")
        self.console.print("  [bold cyan][A][/bold cyan]bort (can resume later)")
        self.console.print()

        try:
            choice = Prompt.ask(
                "[bold]Choice[/bold]",
                choices=["c", "e", "a", "continue", "edit", "abort"],
                default="c",
            )
            # Normalize to full word
            if choice == "c":
                return "continue"
            elif choice == "e":
                return "edit"
            elif choice == "a":
                return "abort"
            return choice
        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[yellow]Interrupted. Saving state...[/yellow]")
            return "abort"

    def _patch_summary_iterations(self, iteration: int) -> None:
        """Overwrite agent-reported `iterations` in the latest *.summary.json
        with the state-machine's `task_list.iteration`.

        The orchestrator agent currently self-reports iteration counts that
        can disagree with the state machine — CHANGELOG, summary.json, and
        task_list.json have shown three different numbers for the same run.
        Python owns this field at write-time so there is a single source of
        truth.
        """
        if self.workspace_dir is None:
            return
        sessions_dir = self.workspace_dir / "sessions"
        if not sessions_dir.exists():
            return
        try:
            summaries = sorted(
                sessions_dir.glob("*.summary.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not summaries:
                return
            latest = summaries[0]
            data = json.loads(latest.read_text())
            if data.get("iterations") != iteration:
                logger.info(
                    "Patching summary.json iterations",
                    file=str(latest),
                    agent_reported=data.get("iterations"),
                    state_machine=iteration,
                )
                data["iterations"] = iteration
                data["_iterations_source"] = "task_list.iteration (state machine)"
                latest.write_text(json.dumps(data, indent=2))
        except Exception as e:  # pragma: no cover — never fail the run on this
            logger.warning("Failed to patch summary.json iterations", error=str(e))

    def _find_resource_path(self) -> Path | None:
        """Find the resource file in the workspace.

        Search order:
        1. SPEC.md resource reference (if exists)
        2. {agent_name}.md (if agent_name provided)
        3. Any .md file that's not SPEC.md, *-orig.md, or *-vN.md

        Returns:
            Path to resource file if found, None otherwise
        """
        if self.workspace_dir is None:
            return None

        # Try SPEC.md first for resource reference
        spec_md = self.workspace_dir / "SPEC.md"
        if spec_md.exists():
            spec = CGFSpec.from_spec_md(spec_md)
            if spec and spec.resource_path.exists():
                return spec.resource_path

        # Try agent name if provided
        if self.agent_name:
            agent_path = self.workspace_dir / f"{self.agent_name}.md"
            if agent_path.exists():
                return agent_path

        # Find any resource .md file
        md_files = [
            f for f in self.workspace_dir.glob("*.md")
            if f.name != "SPEC.md"
            and not f.name.endswith("-orig.md")
            and not re.match(r".*-v\d+\.md$", f.name)
        ]
        if md_files:
            # Prefer SKILL.md for skills
            skill_files = [f for f in md_files if f.name == "SKILL.md"]
            if skill_files:
                return skill_files[0]
            return md_files[0]

        return None

    def _get_resource_hash(self, path: Path) -> str:
        """Get hash of resource file content."""
        content = path.read_text()
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def _baseline_hash_check_enabled() -> bool:
        """Whether P0.1 baseline-hash protection is active.

        Default ON; disable with ``CGF_BASELINE_HASH_CHECK=0`` for tests
        or experimental runs.
        """
        return os.environ.get("CGF_BASELINE_HASH_CHECK", "1").lower() not in (
            "0", "false", "no", "off"
        )

    @staticmethod
    def _signal_strict() -> bool:
        """Whether the P1.4 signal watchdog hard-fails on drift.

        Default OFF (warn-only).  Enable with ``CGF_SIGNAL_STRICT=1``.
        """
        return os.environ.get("CGF_SIGNAL_STRICT", "0").lower() in (
            "1", "true", "yes", "on"
        )

    @staticmethod
    def _max_iterations_cap() -> int:
        """P0.3 hard cap on iteration count (refuses ITERATION_COMPLETE
        beyond this).  Default 3.

        This is distinct from ``CGF_ITERATIONS`` (the spec-level
        max_iterations the orchestrator agent reads), and acts as a
        Python-side hard ceiling to prevent runaway cost.
        """
        try:
            return max(1, int(os.environ.get("CGF_MAX_ITERATIONS", "3")))
        except (ValueError, TypeError):
            return 3

    def _parse_review_recommendation(
        self, review_path: Path
    ) -> tuple[str | None, dict[str, list[str]]]:
        """Parse RECOMMENDATION + refinement directives from a review file.

        The evaluator's contract is to emit a ``<cgf_directive>`` XML
        block at the top of the file (canonical form).  We also accept
        a handful of legacy markdown shapes as fallbacks, because early
        runs surfaced them in the wild before the contract was
        tightened — see the test file for the exact list.

        Args:
            review_path: Path to ``reviews/v{N}_review.md``.

        Returns:
            ``(recommendation, hints_dict)`` where ``hints_dict`` may
            contain keys ``target_sections``, ``target_competencies``,
            ``refinement_hints`` (each a list of strings).  Returns
            ``(None, {})`` if the file is missing or unparseable.
        """
        if not review_path.exists():
            return None, {}
        try:
            content = review_path.read_text()
        except OSError:
            return None, {}

        # ---- Form 1 (canonical): <cgf_directive> XML block ----
        recommendation, hints = self._parse_directive_xml(content)
        if recommendation is not None:
            return recommendation, hints

        # ---- Fallback forms (legacy markdown) ----
        # Form 2: line-anchored `RECOMMENDATION: ACCEPT|REFINE|REJECT`
        #   Also matches:  **RECOMMENDATION:** X / **RECOMMENDATION**: X /
        #                  - **Recommendation:** X
        m = re.search(
            r"^[ \t\-\*]*\*{0,2}\s*RECOMMENDATION\s*\*{0,2}\s*[:=]\s*\*{0,2}\s*(ACCEPT|REFINE|REJECT)\b",
            content,
            re.MULTILINE | re.IGNORECASE,
        )
        if m:
            recommendation = m.group(1).upper()

        # Form 3: markdown table cell  | Recommendation | **REFINE** |
        if recommendation is None:
            m = re.search(
                r"^\s*\|\s*Recommendation\s*\|\s*\*{0,2}\s*(ACCEPT|REFINE|REJECT)\s*\*{0,2}\s*\|",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            if m:
                recommendation = m.group(1).upper()

        # Form 4: `## Recommendation` header followed by standalone bold value.
        if recommendation is None:
            m = re.search(
                r"^#{1,6}\s+Recommendation\s*$"
                r"(?:[ \t]*\n){1,3}"
                r"^[ \t]*\*{0,2}\s*(ACCEPT|REFINE|REJECT)\s*\*{0,2}\s*$",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            if m:
                recommendation = m.group(1).upper()

        # Legacy hint blocks (TARGET_SECTIONS: / dash-bullets).  Only
        # populated if XML directive wasn't found.
        legacy_hints: dict[str, list[str]] = {}
        for label, key in (
            ("TARGET_SECTIONS", "target_sections"),
            ("TARGET_COMPETENCIES", "target_competencies"),
            ("REFINEMENT_HINTS", "refinement_hints"),
        ):
            block = re.search(
                rf"^[ \t]*\*?\*?{label}\*?\*?\s*[:=]?\s*\n((?:[ \t]*-[^\n]+\n?)+)",
                content,
                re.MULTILINE,
            )
            if block:
                items = [
                    re.sub(r"^[ \t]*-\s*", "", line).strip()
                    for line in block.group(1).splitlines()
                    if line.strip().startswith("-")
                ]
                if items:
                    legacy_hints[key] = items

        return recommendation, legacy_hints

    @staticmethod
    def _parse_directive_xml(
        content: str,
    ) -> tuple[str | None, dict[str, list[str]]]:
        """Extract recommendation + refinement directives from a
        ``<cgf_directive>...</cgf_directive>`` block.

        Returns ``(None, {})`` if no block is found or the recommendation
        tag is missing/invalid.  Uses regex (not a real XML parser) so it
        tolerates surrounding markdown and unrelated angle brackets in
        prose elsewhere in the file.
        """
        block_match = re.search(
            r"<cgf_directive>(.*?)</cgf_directive>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if not block_match:
            return None, {}
        block = block_match.group(1)

        rec_match = re.search(
            r"<recommendation>\s*(ACCEPT|REFINE|REJECT)\s*</recommendation>",
            block,
            re.IGNORECASE,
        )
        if not rec_match:
            return None, {}
        recommendation = rec_match.group(1).upper()

        hints: dict[str, list[str]] = {}
        for parent_tag, item_tag, key in (
            ("target_sections", "section", "target_sections"),
            ("target_competencies", "competency", "target_competencies"),
            ("refinement_hints", "hint", "refinement_hints"),
        ):
            parent = re.search(
                rf"<{parent_tag}>(.*?)</{parent_tag}>",
                block,
                re.DOTALL | re.IGNORECASE,
            )
            if not parent:
                continue
            items = [
                m.group(1).strip()
                for m in re.finditer(
                    rf"<{item_tag}>(.*?)</{item_tag}>",
                    parent.group(1),
                    re.DOTALL | re.IGNORECASE,
                )
                if m.group(1).strip()
            ]
            if items:
                hints[key] = items

        return recommendation, hints

    def _verify_baseline(
        self,
        task_list: "CGFTaskList",
        resource_path: Path,
    ) -> str | None:
        """Re-hash the resource file and compare against the recorded baseline.

        Returns ``None`` if the file is intact (or if checking is disabled
        / no baseline recorded).  Returns an error message if the hash
        differs.  Caller is responsible for marking the run failed.
        """
        if not self._baseline_hash_check_enabled():
            return None
        if not task_list.baseline_hash:
            return None
        if not resource_path.exists():
            return (
                f"Baseline file vanished mid-run: {resource_path} "
                "(expected SHA-256 prefix "
                f"{task_list.baseline_hash}, file no longer exists)."
            )
        current = self._get_resource_hash(resource_path)
        if current != task_list.baseline_hash:
            return (
                "Baseline integrity violation: "
                f"{resource_path} was modified during the run. "
                f"Expected SHA-256 prefix {task_list.baseline_hash}, "
                f"observed {current}.  The original resource file MUST NOT "
                "be modified — optimized versions belong in "
                "{resource}-v{N}.md.  Set CGF_BASELINE_HASH_CHECK=0 to "
                "disable this check."
            )
        return None

    def _has_spec(self) -> bool:
        """Check if SPEC.md or cgf_spec.yaml exists.

        Returns:
            True if either spec format exists
        """
        if self.workspace_dir is None:
            return False
        spec_md = self.workspace_dir / "SPEC.md"
        spec_yaml = self.workspace_dir / "cgf_spec.yaml"
        return spec_md.exists() or spec_yaml.exists()

    def _has_completed_qa(self) -> bool:
        """Check if Q&A phase has been completed.

        Q&A is complete if either:
        - SPEC.md exists with Q&A Session Results section
        - cgf_spec.yaml exists (legacy format)
        """
        if self.workspace_dir is None:
            return False

        # Check for legacy format
        spec_yaml = self.workspace_dir / "cgf_spec.yaml"
        if spec_yaml.exists():
            return True

        # Check SPEC.md for Q&A results
        spec_md = self.workspace_dir / "SPEC.md"
        if spec_md.exists():
            content = spec_md.read_text()
            # Q&A appends "## Q&A Session Results" section
            return "## Q&A Session Results" in content

        return False

    def _load_qa_session(self) -> CGFQASession | None:
        """Load Q&A session state from sessions/ directory."""
        if self.workspace_dir is None:
            return None
        qa_path = self._get_sessions_path() / "qa_session.json"
        if not qa_path.exists():
            return None

        with open(qa_path) as f:
            data = json.load(f)
        return CGFQASession.from_dict(data)

    def _save_qa_session(self, qa_session: CGFQASession) -> None:
        """Save Q&A session state to sessions/ directory."""
        if self.workspace_dir is None:
            raise RuntimeError("workspace_dir not set")
        qa_path = self._get_sessions_path() / "qa_session.json"
        with open(qa_path, "w") as f:
            json.dump(qa_session.to_dict(), f, indent=2)
        logger.debug("Q&A session saved", path=str(qa_path))

    async def run(self) -> bool:
        """Run the CGF optimization session.

        Supports two modes:
        1. SPEC.md discovery: Find SPEC.md and use its parent as workspace
        2. Legacy mode: Use agent_name to determine workspace path

        Returns:
            True if successful, False otherwise
        """
        self._setup_signal_handlers()
        self._shutdown_event = asyncio.Event()

        # Step 1: Discover or set workspace directory
        if self.workspace_path_override or not self.agent_name:
            # SPEC.md discovery mode
            discovered = self._discover_workspace()
            if discovered:
                self.workspace_dir = discovered
                self.console.print(
                    f"[cyan]Using workspace: {self.workspace_dir}[/cyan]"
                )
            elif self.agent_name:
                # Fallback to legacy mode
                self.workspace_dir = self.workspace_base / self.agent_name
            else:
                # No workspace found and no agent name
                self.console.print(
                    "[yellow]No SPEC.md found in workspace.[/yellow]"
                )
                self.console.print(
                    "\n[dim]To start optimization:[/dim]"
                )
                self.console.print(
                    "  1. Create a workspace directory"
                )
                self.console.print(
                    "  2. Create SPEC.md with optimization goals"
                )
                self.console.print(
                    "  3. Copy resource file to workspace"
                )
                self.console.print(
                    "\nOr use: make optimize AGENT=<name>"
                )
                return False
        else:
            # Legacy agent_name mode
            self.workspace_dir = self.workspace_base / self.agent_name

        # Create workspace directory
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Check for existing task_list.json (resume capability)
        existing_task_list = CGFTaskList.load(self.workspace_dir)

        if existing_task_list and existing_task_list.is_resumable():
            # Resume from existing state
            self.console.print(
                f"[cyan]Resuming from {existing_task_list.current_phase} phase "
                f"(iteration {existing_task_list.iteration}/"
                f"{existing_task_list.total_iterations})[/cyan]"
            )

            # Load spec and continue
            spec = self._load_spec()
            if spec is None:
                self.console.print(
                    "[red]Error: Could not load spec for resume[/red]"
                )
                return False

            # Set resource name for versioning
            self.resource_name = self._derive_resource_name(spec.resource_path)

            return await self._run_optimization_phase(spec, existing_task_list)

        # Find resource path
        resource_path = self._find_resource_path()
        if resource_path is None:
            if self.agent_name:
                expected_path = self.workspace_dir / f"{self.agent_name}.md"
                self.console.print(
                    f"[red]Error: Could not find agent resource: "
                    f"{self.agent_name}[/red]"
                )
                self.console.print(
                    f"\n[dim]Expected file at: {expected_path}[/dim]"
                )
                self.console.print(
                    "\n[yellow]To set up optimization:[/yellow]\n"
                    f"  1. Create directory: mkdir -p {self.workspace_dir}\n"
                    f"  2. Copy agent file: cp <source> {expected_path}\n"
                    f"  3. Run: make optimize AGENT={self.agent_name}"
                )
            else:
                self.console.print(
                    "[red]Error: No resource file found in workspace[/red]"
                )
                self.console.print(
                    f"\n[dim]Workspace: {self.workspace_dir}[/dim]"
                )
                self.console.print(
                    "\n[yellow]Add a .md resource file to the workspace[/yellow]"
                )
            return False

        # Set resource name for versioning
        self.resource_name = self._derive_resource_name(resource_path)

        logger.info(
            "Starting CGF session",
            resource=str(resource_path),
            workspace=str(self.workspace_dir),
        )

        # Phase 1: Q&A or SPEC.md (if no spec exists and no goal provided)
        if not self._has_completed_qa():
            if self.goal:
                # Skip Q&A, create spec directly from goal
                spec = CGFSpec(
                    resource_path=resource_path,
                    resource_type="agent",  # TODO: auto-detect
                    optimization_goal=self.goal,
                )
                spec.save(self.workspace_dir)
                self.console.print(
                    f"[green]Created spec from goal: {self.goal}[/green]"
                )
            else:
                # Try to load from SPEC.md first
                spec = self._load_spec()
                if spec is None:
                    spec = await self._run_qa_phase(resource_path)
                    if spec is None:
                        self.console.print(
                            "[yellow]Q&A phase not completed. "
                            "Run again to resume.[/yellow]"
                        )
                        return False
                else:
                    self.console.print(
                        f"[green]Loaded spec from SPEC.md: "
                        f"{spec.optimization_goal}[/green]"
                    )
        else:
            spec = self._load_spec()
            if spec is None:
                self.console.print(
                    "[red]Error: Could not load existing spec[/red]"
                )
                return False
            self.console.print(
                f"[green]Loaded existing spec: "
                f"{spec.optimization_goal}[/green]"
            )

        # Phase 2: Optimization
        success = await self._run_optimization_phase(spec)

        return success

    def _load_spec(self) -> CGFSpec | None:
        """Load specification from SPEC.md or cgf_spec.yaml.

        Prefers SPEC.md (new format) over cgf_spec.yaml (legacy).

        Returns:
            CGFSpec if found, None otherwise
        """
        if self.workspace_dir is None:
            return None

        # Try SPEC.md first (new format)
        spec_md = self.workspace_dir / "SPEC.md"
        if spec_md.exists():
            spec = CGFSpec.from_spec_md(spec_md)
            if spec:
                return spec

        # Fallback to cgf_spec.yaml (legacy format)
        return CGFSpec.load(self.workspace_dir)

    def _build_initializer_prompt(
        self, resource_path: Path, qa_session: CGFQASession | None = None
    ) -> str:
        """Build the prompt for Q&A phase.

        Args:
            resource_path: Path to the resource file
            qa_session: Optional QA session for resume context
        """
        try:
            initializer_prompt = load_prompt("cgf-initializer-agent")
        except FileNotFoundError:
            # Use fallback prompt if file doesn't exist yet
            initializer_prompt = self._get_fallback_initializer_prompt()

        # Read resource content
        resource_content = resource_path.read_text()

        prompt = f"""{initializer_prompt}

---

## Resource to Optimize

**File**: {resource_path.name}
**Full Path**: {resource_path}

```markdown
{resource_content}
```

---

## Environment Defaults

These values are read from the environment and can be overridden in your answers:

- **CGF_ITERATIONS**: {os.environ.get("CGF_ITERATIONS", "10")}
- **CGF_ITERATION_REVIEW**: {os.environ.get("CGF_ITERATION_REVIEW", "false")}
- **CGF_EVAL_MODEL**: {os.environ.get("CGF_EVAL_MODEL", "sonnet")}
- **CGF_VERBOSE**: {os.environ.get("CGF_VERBOSE", "true")}

"""
        # Add resume context if available
        if qa_session and qa_session.is_resumable():
            prompt += f"""
---

## Resuming Previous Session

A previous Q&A session was interrupted. Here is the conversation history:

**Progress**: Question {qa_session.current_question}/{qa_session.total_questions}

### Previous Conversation

"""
            for msg in qa_session.conversation_history:
                role = "CGF Initializer" if msg["role"] == "assistant" else "User"
                prompt += f"**{role}**: {msg['content']}\n\n"

            prompt += """---

Continue from where you left off. Do NOT re-ask questions that were already answered.
Resume with the next question in the sequence.
"""

        return prompt

    def _get_fallback_initializer_prompt(self) -> str:
        """Get fallback prompt if cgf-initializer-agent.md doesn't exist yet."""
        return """# CGF Initializer Agent

You help users define their optimization objectives through structured Q&A.

## Workflow

### Step 1: Resource Analysis
- Read the resource file
- Auto-detect type from content (agent/skill/command)
- Summarize current state (sections, competencies, line count)

### Step 2: Clarifying Questions

Ask sequentially (use **Question X/Y** format):

1. **Optimization Goal**: "What do you want to improve about this resource?"
   - Examples: "async programming guidance", "better error handling", "clearer examples"

2. **Focus Areas** (optional): "Any specific sections or competencies to focus on?"
   - If yes, list detected sections and ask which to prioritize
   - If no, optimize all sections

3. **Iteration Review**: "Review and provide feedback after each iteration?"
   - If yes, pause after each optimization round for user feedback
   - If no (default), run all iterations autonomously

4. **Constraints** (optional): "How many optimization iterations?" (default: from .env)

### Step 3: Generate Specification

When user confirms, output the specification in YAML format:

```yaml
resource_path: <path>
resource_type: <agent|skill|command>
optimization_goal: "<goal>"
target_sections:
  - <section1>
  - <section2>
iteration_review: <true|false>
max_iterations: <number>
eval_model: <sonnet|haiku|opus>
```

Then output: [SPEC_READY]
"""

    async def _run_qa_phase(self, resource_path: Path) -> CGFSpec | None:
        """Interactive Q&A with cgf-initializer agent.

        Args:
            resource_path: Path to the resource file

        Returns:
            CGFSpec if completed, None if interrupted
        """
        agent_name = "cgf-initializer"

        # Load or create Q&A session
        qa_session = self._load_qa_session()
        resource_hash = self._get_resource_hash(resource_path)

        if qa_session is None or qa_session.resource_hash != resource_hash:
            # New session or resource changed
            qa_session = CGFQASession(
                started_at=datetime.now(UTC).isoformat(),
                resource_hash=resource_hash,
            )
        else:
            logger.info("Resuming Q&A session", progress=qa_session.current_question)

        # Build prompt
        prompt = self._build_initializer_prompt(resource_path, qa_session)

        # Display header
        is_resuming = qa_session.is_resumable()
        if is_resuming:
            title = "CGF Optimization Q&A (Resuming)"
            subtitle = f"Progress: Question {qa_session.current_question}"
        else:
            title = "CGF Optimization Q&A"
            subtitle = "Answer questions to define optimization objectives"

        header_panel = Panel(
            "",
            title=f"[bold white]{title}[/]",
            subtitle=f"[dim]{subtitle}[/]" if subtitle else None,
            border_style="bold cyan",
            expand=True,
            padding=(0, 0),
        )
        self.console.print()
        self.console.print(header_panel)
        self.console.print()

        spec_ready = False
        last_agent_response = ""

        try:
            runtime = self._create_runtime_config(permission_mode="acceptEdits")
            async with AgentSession(
                agent_name=agent_name,
                config=self.config,
                runtime_config=runtime,
                system_prompt=prompt,
            ) as agent_session:
                # Start message
                if is_resuming:
                    current_message = (
                        f"Continue from Question {qa_session.current_question + 1}. "
                        "Do not repeat questions already answered."
                    )
                else:
                    current_message = "Begin resource analysis and Q&A."

                while not spec_ready and not self._shutdown_requested:
                    # Execute and collect response
                    last_agent_response = ""
                    async for message in agent_session.execute(current_message):
                        content = self._extract_content_str(message)
                        if content:
                            last_agent_response += content
                            # Display response
                            parse_and_print_message(message, self.console)

                    # Check for spec ready signal
                    if "[SPEC_READY]" in last_agent_response:
                        spec_ready = True
                        qa_session.status = "completed"
                        self._save_qa_session(qa_session)

                        # Parse and save spec from response
                        spec = self._parse_spec_from_response(
                            last_agent_response, resource_path
                        )
                        if spec:
                            spec.save(self.workspace_dir)
                            return spec
                        else:
                            self.console.print(
                                "[red]Error: Could not parse spec from response[/red]"
                            )
                            return None

                    # Get user input
                    self.console.print()
                    try:
                        user_response = Prompt.ask("[bold cyan]Your response[/]")
                    except (KeyboardInterrupt, EOFError):
                        self.console.print("\n[yellow]Session interrupted.[/yellow]")
                        self._save_qa_session(qa_session)
                        return None

                    # Record exchange and save
                    qa_session.add_exchange(last_agent_response, user_response)
                    self._save_qa_session(qa_session)

                    current_message = user_response

        except Exception as e:
            logger.error("Q&A phase error", error=str(e))
            self._save_qa_session(qa_session)
            raise

        return None

    def _parse_spec_from_response(
        self, response: str, resource_path: Path
    ) -> CGFSpec | None:
        """Parse CGFSpec from agent response containing YAML."""
        # Find YAML block in response
        yaml_match = re.search(r"```ya?ml\n(.*?)```", response, re.DOTALL)
        if not yaml_match:
            # Try finding raw YAML-like content
            yaml_match = re.search(
                r"resource_path:.*?(?=\n\n|\[SPEC_READY\]|$)", response, re.DOTALL
            )
            if yaml_match:
                yaml_content = yaml_match.group(0)
            else:
                return None
        else:
            yaml_content = yaml_match.group(1)

        try:
            # Handle escaped newlines from string serialization
            if "\\n" in yaml_content:
                yaml_content = yaml_content.replace("\\n", "\n")

            data = yaml.safe_load(yaml_content)
            # Ensure resource_path is set correctly
            data["resource_path"] = str(resource_path)
            return CGFSpec.from_dict(data)
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML spec", error=str(e), yaml=yaml_content[:200])
            return None

    def _iter_tool_use_blocks(self, message: object) -> list[object]:
        """Yield ToolUseBlock-like blocks from a message.

        Returns blocks that have both ``name`` and ``input`` attributes.
        Tolerant of message types that don't expose ``content`` (returns []).
        """
        raw_content = getattr(message, "content", None)
        if not isinstance(raw_content, list):
            return []
        return [
            b for b in raw_content
            if hasattr(b, "name") and hasattr(b, "input")
        ]

    def _extract_content_str(self, message: object) -> str:
        """Extract string content from a message object."""
        raw_content = getattr(message, "content", None)
        if raw_content is None:
            return ""
        elif isinstance(raw_content, list):
            parts = []
            for block in raw_content:
                # SDK TextBlock has .text attribute
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, str):
                    parts.append(block)
                # Skip non-text blocks (tool use, etc.)
            return "\n".join(parts)
        elif isinstance(raw_content, str):
            return raw_content
        else:
            return ""

    def _build_orchestrator_prompt(self, spec: CGFSpec) -> str:
        """Build prompt for cgf-orchestrator with spec context."""
        try:
            orchestrator_prompt = load_prompt(
                "plugins/cgf-agents/agents/design/cgf-orchestrator"
            )
        except FileNotFoundError:
            # Try alternate path
            orchestrator_path = (
                Path("src/harness/plugins/cgf-agents/agents/design/cgf-orchestrator.md")
            )
            if orchestrator_path.exists():
                orchestrator_prompt = orchestrator_path.read_text()
            else:
                raise FileNotFoundError(
                    "cgf-orchestrator.md not found in prompts or plugins"
                )

        # NOTE: we deliberately do NOT embed the resource content here.
        # Linux's MAX_ARG_STRLEN (per-argv limit) is 128KB, and the SDK
        # passes the entire system_prompt as one argv element to the
        # bundled `claude` CLI.  A 49KB orchestrator prompt + an 82KB
        # resource = E2BIG ([Errno 7] Argument list too long).  The
        # orchestrator has the Read tool — point it at the file and let
        # it pull the content on demand.  This also fixes a correctness
        # bug: the resource changes across iterations, so embedding a
        # stale snapshot at session start misleads the agent.
        prompt = f"""{orchestrator_prompt}

---

## Loaded CGF Specification

The following specification was created during the Q&A phase:

```yaml
{yaml.safe_dump(spec.to_dict(), default_flow_style=False)}
```

## Current Resource (read on demand)

**File**: {spec.resource_path}

The resource file is NOT inlined here — it would push this system
prompt past the OS per-arg limit for moderately sized resources.
Use the Read tool to load it when (and only when) you need its
content.  Note that during ITERATE phases, candidate versions
(`{spec.resource_path.stem}-v{{N}}.md` in the same directory) will be
written by the optimizer subagent — Read those as needed too.

---

## Instructions

1. Initialize using the loaded spec (skip INIT Q&A - spec already exists)
2. Transition to RESEARCH phase immediately
3. Use workspace directory: {self.workspace_dir}
4. Follow the optimization mode: {spec.optimizer_mode}
5. Max iterations: {spec.max_iterations}
6. Iteration review: {spec.iteration_review}

Begin optimization now.
"""
        return prompt

    def _build_resume_message(self, task_list: CGFTaskList) -> str:
        """Build a message to resume optimization from current phase.

        Args:
            task_list: Current task list state

        Returns:
            Message to send to orchestrator for resume
        """
        phase = task_list.current_phase
        iteration = task_list.iteration

        if phase == "research":
            return "Resume from RESEARCH phase. Continue gathering domain knowledge."
        elif phase == "iterate":
            return (
                f"Resume from ITERATE phase (iteration {iteration}). "
                "Continue agentic optimization using research findings."
            )
        elif phase == "evaluate":
            return "Resume from EVALUATE phase. Continue evaluating results."
        elif phase == "finalize":
            return "Resume from FINALIZE phase. Complete the optimization."
        else:
            return "Begin optimization with the loaded specification."

    async def _run_optimization_phase(
        self, spec: CGFSpec, task_list: CGFTaskList | None = None
    ) -> bool:
        """Autonomous optimization with cgf-orchestrator.

        Args:
            spec: Optimization specification from Q&A phase
            task_list: Optional existing task list for resume

        Returns:
            True if successful, False otherwise
        """
        # Create or use existing task list
        if task_list is None:
            task_list = CGFTaskList(
                spec_path=str(self.workspace_dir / "cgf_spec.yaml"),
                current_phase="research",
                total_iterations=spec.max_iterations,
            )
            task_list.save(self.workspace_dir)
        self.task_list = task_list

        # P0.1: Capture SHA-256 of the pristine resource file so we can detect
        # any mid-run mutation (e.g. orchestrator overwriting the original
        # with iteration content).  Only set on the first entry — resumes
        # MUST trust the originally-recorded hash.
        if (
            task_list.baseline_hash is None
            and spec.resource_path.exists()
            and self._baseline_hash_check_enabled()
        ):
            task_list.baseline_hash = self._get_resource_hash(spec.resource_path)
            logger.info(
                "Baseline integrity hash captured",
                resource=str(spec.resource_path),
                sha256_prefix=task_list.baseline_hash,
            )
            task_list.save(self.workspace_dir)

        # Initialize run-status gauges (label value used in Grafana panels)
        resource_label = self.resource_name or "unknown"
        record_run_path(resource_label, "single")
        init_run_phases(resource_label)
        record_phase_entry(resource_label, task_list.current_phase)
        record_iteration(resource_label, task_list.iteration)

        # Display header
        is_resuming = task_list.iteration > 0 or task_list.current_phase != "research"
        title = "CGF Optimization Phase"
        if is_resuming:
            title += f" (Resuming from {task_list.current_phase})"

        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Goal:[/bold] {spec.optimization_goal}\n"
                f"[bold]Mode:[/bold] {spec.optimizer_mode}\n"
                f"[bold]Iterations:[/bold] {spec.max_iterations}\n"
                f"[bold]Review:[/bold] {spec.iteration_review}\n"
                f"[bold]Phase:[/bold] {task_list.current_phase}",
                title=f"[bold white]{title}[/]",
                border_style="bold green",
            )
        )
        self.console.print()

        try:
            prompt = self._build_orchestrator_prompt(spec)

            # Use bypassPermissions for autonomous optimization
            runtime = self._create_runtime_config(
                permission_mode="bypassPermissions"
            )

            async with AgentSession(
                agent_name="cgf-agents:cgf-orchestrator",
                config=self.config,
                runtime_config=runtime,
                system_prompt=prompt,
            ) as agent_session:
                # Build initial message (start or resume)
                current_message = self._build_resume_message(task_list)

                # Hard-contract enforcement: track how many of each signal the
                # orchestrator agent emits this run.  `[OPTIMIZATION_COMPLETE]`
                # is rejected if `iterate` or `evaluate` count == 0 — see
                # CLAUDE.md "TODOs / hardening" for rationale.
                #
                # Seeded from the persisted task_list so resumes don't lose
                # state.  `iterate` is authoritative from task_list.iteration;
                # `evaluate` is reconstructed from prior checkpoints.
                signal_counts = {
                    "research": 0,
                    "test_gen": 0,
                    "iterate": task_list.iteration,
                    "evaluate": sum(
                        1 for cp in task_list.checkpoints
                        if cp.get("phase") == "evaluate"
                    ),
                }

                # P0.3 hard iteration cap (defense-in-depth: complements the
                # spec.max_iterations the orchestrator agent self-polices).
                iteration_cap = self._max_iterations_cap()

                max_iters_str = (
                    f"{iteration_cap} (Python cap) / "
                    f"{spec.max_iterations} (spec)"
                )
                logger.info(
                    "CGF optimization phase starting",
                    resource=resource_label,
                    iteration_cap=iteration_cap,
                    max_iters=max_iters_str,
                )

                # P0.4: when the latest evaluation produced ACCEPT or REJECT,
                # the next signal MUST be terminal — refuse another
                # ITERATION_COMPLETE.  Restored from task_list on resume.
                terminal_required: bool = task_list.last_recommendation in (
                    "ACCEPT", "REJECT"
                )

                # P1.4 signal watchdog state.  Reset at the start of every
                # agent turn (every execute() iteration).
                # Tracks Write tool calls to *-v{N}.md and whether
                # [ITERATION_COMPLETE] fired in the same turn.
                pending_iteration_signal: int | None = None

                while not self._shutdown_requested:
                    phase_transitioned = False
                    accumulated_content = ""
                    pending_iteration_signal = None

                    async for message in agent_session.execute(current_message):
                        content = self._extract_content_str(message)
                        accumulated_content += content
                        parse_and_print_message(message, self.console)

                        # P1.4 signal watchdog: detect Write tool calls
                        # targeting versioned files like ``foo-v2.md``.
                        # If the same turn also emits ITERATION_COMPLETE
                        # we clear the flag; otherwise we warn/fail.
                        for block in self._iter_tool_use_blocks(message):
                            name = getattr(block, "name", "")
                            if name != "Write":
                                continue
                            block_input = getattr(block, "input", None) or {}
                            file_path = block_input.get("file_path", "") if isinstance(block_input, dict) else ""
                            m = re.search(r"-v(\d+)\.md$", str(file_path))
                            if m:
                                pending_iteration_signal = int(m.group(1))
                                logger.debug(
                                    "Watchdog: pending iteration signal",
                                    version=pending_iteration_signal,
                                    file=file_path,
                                )

                        # P0.1 baseline integrity check — performed BEFORE
                        # acting on any phase signal.  If the pristine
                        # resource file has been mutated, hard-fail.
                        if any(
                            sig in content for sig in (
                                "[RESEARCH_COMPLETE]",
                                "[TEST_GEN_COMPLETE]",
                                "[ITERATION_COMPLETE]",
                                "[EVALUATE_COMPLETE]",
                                "[OPTIMIZATION_COMPLETE]",
                            )
                        ):
                            integrity_err = self._verify_baseline(
                                task_list, spec.resource_path,
                            )
                            if integrity_err:
                                logger.error(
                                    "CGF baseline integrity violation",
                                    error=integrity_err,
                                )
                                task_list.error = integrity_err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — "
                                    "baseline integrity violation[/bold red]\n"
                                    f"[red]{integrity_err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                        # Check for terminal signals first
                        if "[OPTIMIZATION_COMPLETE]" in content:
                            # Enforce signal-sequence contract.  Skipping the
                            # iterate/evaluate phases means the dashboard,
                            # iteration counter, and CHANGELOG all go dark.
                            missing = [
                                k for k in ("iterate", "evaluate")
                                if signal_counts[k] == 0
                            ]
                            if missing:
                                err = (
                                    "Contract violation: [OPTIMIZATION_COMPLETE] "
                                    f"fired without prior signals: {missing}. "
                                    f"Counts so far: {signal_counts}. "
                                    "The orchestrator agent must emit at least "
                                    "one [ITERATION_COMPLETE] AND one "
                                    "[EVALUATE_COMPLETE] (see cgf-orchestrator.md "
                                    "§ Phase Completion Signals)."
                                )
                                logger.error("CGF contract violation", missing=missing, counts=signal_counts)
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    f"\n[bold red]Run failed — contract violation[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                # Record on dashboard so failure is visible
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            task_list.current_phase = "complete"
                            record_phase_entry(resource_label, "complete")
                            task_list.add_checkpoint(
                                "complete",
                                str(self.workspace_dir),
                                f"Optimization completed successfully (signals: {signal_counts})",
                            )
                            task_list.save(self.workspace_dir)
                            self._patch_summary_iterations(task_list.iteration)
                            self.console.print(
                                "\n[bold green]Optimization completed![/bold green]"
                            )
                            # Hold the metrics endpoint open long enough for
                            # Prometheus (15s scrape interval) to capture the
                            # final `complete=1` state. Otherwise the dashboard
                            # ends up showing whichever phase was scraped just
                            # before this transition.
                            await asyncio.sleep(20)
                            return True

                        if "[OPTIMIZATION_FAILED]" in content:
                            task_list.error = "Optimization failed"
                            task_list.save(self.workspace_dir)
                            self.console.print(
                                "\n[bold red]Optimization failed.[/bold red]"
                            )
                            return False

                        # Check for phase transition signals
                        if "[RESEARCH_COMPLETE]" in content:
                            signal_counts["research"] += 1
                            task_list.current_phase = (
                                "test_gen"
                                if spec.optimizer_mode in ("python", "both")
                                else "iterate"
                            )
                            record_phase_entry(resource_label, task_list.current_phase)
                            task_list.add_checkpoint(
                                "research",
                                str(self.workspace_dir / "research"),
                                "Research phase completed",
                            )
                            task_list.save(self.workspace_dir)

                            # Prompt user at checkpoint
                            choice = await self._prompt_checkpoint(
                                "research",
                                str(self.workspace_dir / "research" / "eval_criteria.yaml"),
                            )
                            if choice == "abort":
                                return False
                            elif choice == "edit":
                                current_message = (
                                    "User edited the resource. "
                                    "Continue with optimization."
                                )
                            else:
                                current_message = (
                                    f"Continue to {task_list.current_phase} phase."
                                )
                            phase_transitioned = True
                            break

                        if "[TEST_GEN_COMPLETE]" in content:
                            signal_counts["test_gen"] += 1
                            task_list.current_phase = "optimize"
                            record_phase_entry(resource_label, "optimize")
                            task_list.add_checkpoint(
                                "test_gen",
                                str(self.workspace_dir / "tests" / "test_suite.yaml"),
                                "Test generation completed",
                            )
                            task_list.save(self.workspace_dir)

                            choice = await self._prompt_checkpoint(
                                "test_gen",
                                str(self.workspace_dir / "tests" / "test_suite.yaml"),
                            )
                            if choice == "abort":
                                return False
                            current_message = "Continue to OPTIMIZE phase."
                            phase_transitioned = True
                            break

                        if "[ITERATION_COMPLETE]" in content:
                            prospective_iter = signal_counts["iterate"] + 1

                            # P0.4: ACCEPT/REJECT means the last evaluator
                            # decided the run was done.  Refuse another
                            # iteration in that case.
                            if terminal_required:
                                err = (
                                    "Contract violation: [ITERATION_COMPLETE] "
                                    "fired after the evaluator returned "
                                    f"RECOMMENDATION: {task_list.last_recommendation}. "
                                    "Only [OPTIMIZATION_COMPLETE] (or [OPTIMIZATION_FAILED]) "
                                    "is permitted after a terminal recommendation."
                                )
                                logger.error(
                                    "CGF iteration after terminal recommendation",
                                    recommendation=task_list.last_recommendation,
                                )
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — iteration after "
                                    "terminal recommendation[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            # P0.2: pair-wise iter ↔ eval contract.  After
                            # this ITERATION_COMPLETE, iter_count must not
                            # exceed eval_count + 1 (each iteration must be
                            # followed by an evaluation before the next).
                            if prospective_iter > signal_counts["evaluate"] + 1:
                                err = (
                                    "Contract violation: [ITERATION_COMPLETE] "
                                    f"#{prospective_iter} fired without a prior "
                                    "[EVALUATE_COMPLETE] for the previous "
                                    "iteration.  Counts: "
                                    f"iterate={prospective_iter}, "
                                    f"evaluate={signal_counts['evaluate']}.  "
                                    "Protocol: write v{N}.md → "
                                    "[ITERATION_COMPLETE] → dispatch evaluator "
                                    "→ write reviews/v{N}_review.md → "
                                    "[EVALUATE_COMPLETE] → only then v{N+1}.md."
                                )
                                logger.error(
                                    "CGF pair-wise violation",
                                    prospective_iter=prospective_iter,
                                    eval_count=signal_counts["evaluate"],
                                )
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — "
                                    "pair-wise contract violation[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            # P0.3: hard iteration cap (Python-side ceiling).
                            if prospective_iter > iteration_cap:
                                err = (
                                    "Contract violation: [ITERATION_COMPLETE] "
                                    f"#{prospective_iter} exceeds CGF_MAX_ITERATIONS "
                                    f"cap of {iteration_cap}.  The orchestrator "
                                    "agent must emit [OPTIMIZATION_COMPLETE] "
                                    "(or [OPTIMIZATION_FAILED]) once the cap is "
                                    "reached.  Set CGF_MAX_ITERATIONS higher to "
                                    "permit more iterations."
                                )
                                logger.error(
                                    "CGF iteration cap exceeded",
                                    prospective_iter=prospective_iter,
                                    cap=iteration_cap,
                                )
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — iteration cap "
                                    f"exceeded ({iteration_cap})[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            signal_counts["iterate"] = prospective_iter
                            task_list.iteration = prospective_iter
                            record_iteration(resource_label, task_list.iteration)
                            task_list.save(self.workspace_dir)

                            # P1.4: a Write to v{N}.md preceded this signal —
                            # clear the watchdog flag.
                            pending_iteration_signal = None

                            # Pair-wise contract enforcement at the
                            # protocol layer: after each [ITERATION_COMPLETE]
                            # the orchestrator MUST dispatch the evaluator
                            # and emit [EVALUATE_COMPLETE] before the next
                            # iteration.  We saw orchestrator drift in
                            # smoke run #5 where back-to-back
                            # [ITERATION_COMPLETE] signals fired with no
                            # evaluation in between (P0.2 caught it but
                            # the prompt clearly wasn't direct enough).
                            # The post-signal message tells the agent
                            # explicitly what to do next.
                            iter_n = task_list.iteration
                            eval_directive = (
                                f"Iteration {iter_n} complete (v{iter_n}.md written). "
                                "You MUST now do the following — in this order, "
                                "before any further work:\n\n"
                                f"1. Dispatch `cgf-agents:cgf-result-evaluator` "
                                "via the Task tool, passing the v"
                                f"{iter_n}.md path and the SPEC.md path as "
                                "inputs.\n"
                                f"2. Wait for the evaluator to write "
                                f"`workspace/{self.resource_name}/reviews/"
                                f"v{iter_n}_review.md` "
                                "containing a `<cgf_directive>` XML block at "
                                "the top.\n"
                                f"3. Emit `[EVALUATE_COMPLETE]` on its own "
                                "line.\n\n"
                                "DO NOT write `v"
                                f"{iter_n + 1}.md` until "
                                "`[EVALUATE_COMPLETE]` fires.  Pair-wise "
                                "contract is enforced by the Python runner: "
                                "back-to-back `[ITERATION_COMPLETE]` signals "
                                "hard-fail the run."
                            )

                            # Prompt for iteration review if enabled
                            if spec.iteration_review:
                                version_file = (
                                    f"{self.resource_name}-v{iter_n}.md"
                                )
                                choice = await self._prompt_checkpoint(
                                    f"iteration {iter_n}",
                                    str(self.workspace_dir / version_file),
                                )
                                if choice == "abort":
                                    return False
                                elif choice == "edit":
                                    current_message = (
                                        "User edited the resource v"
                                        f"{iter_n}.md. " + eval_directive
                                    )
                                else:
                                    current_message = eval_directive
                            else:
                                current_message = eval_directive
                            phase_transitioned = True
                            break

                        if "[EVALUATE_COMPLETE]" in content:
                            # P0.4: require the review file to exist on disk
                            # at the iteration we just completed.  The agent
                            # CANNOT self-report a recommendation — it must
                            # land in workspace/{resource}/reviews/v{N}_review.md
                            # so Python can parse the authoritative source.
                            review_iter = task_list.iteration
                            review_path = (
                                self.workspace_dir
                                / "reviews"
                                / f"v{review_iter}_review.md"
                            )
                            # Brief grace period in case the agent emitted the
                            # signal while a Task subagent's filesystem write
                            # is still flushing.  Polls every 0.5s up to 10s.
                            # If the agent emitted the signal BEFORE
                            # dispatching the evaluator (the actual contract
                            # violation), the grace period is bounded — we
                            # still fail the run, just not on a filesystem
                            # race.
                            if not review_path.exists():
                                for _ in range(20):  # 20 * 0.5 = 10s max
                                    await asyncio.sleep(0.5)
                                    if review_path.exists():
                                        break
                            if not review_path.exists():
                                err = (
                                    "Contract violation: [EVALUATE_COMPLETE] "
                                    f"fired but review file missing on disk. "
                                    f"Expected: {review_path}.  The evaluator "
                                    "subagent must Write the review BEFORE "
                                    "the orchestrator emits the signal."
                                )
                                logger.error(
                                    "CGF missing review file",
                                    expected=str(review_path),
                                    iteration=review_iter,
                                )
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — review file "
                                    "missing on disk[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            recommendation, hints = self._parse_review_recommendation(
                                review_path
                            )
                            if recommendation is None:
                                err = (
                                    "Contract violation: review file "
                                    f"{review_path} is missing a parseable "
                                    "'RECOMMENDATION: ACCEPT|REFINE|REJECT' "
                                    "line.  The evaluator must include this "
                                    "on its own line in the review."
                                )
                                logger.error(
                                    "CGF malformed review file",
                                    path=str(review_path),
                                )
                                task_list.error = err
                                task_list.save(self.workspace_dir)
                                self.console.print(
                                    "\n[bold red]Run failed — malformed review "
                                    "file[/bold red]\n"
                                    f"[red]{err}[/red]"
                                )
                                record_phase_entry(resource_label, "failed")
                                await asyncio.sleep(20)
                                return False

                            signal_counts["evaluate"] += 1
                            task_list.current_phase = "finalize"
                            task_list.last_recommendation = recommendation
                            record_phase_entry(resource_label, "finalize")
                            task_list.add_checkpoint(
                                "evaluate",
                                str(review_path),
                                f"Evaluation v{review_iter}: {recommendation}",
                            )
                            # Stash hints on the checkpoint so the next
                            # iteration prompt can reference them.
                            if task_list.checkpoints:
                                task_list.checkpoints[-1]["recommendation"] = (
                                    recommendation
                                )
                                if hints:
                                    task_list.checkpoints[-1]["hints"] = hints
                            task_list.save(self.workspace_dir)

                            # ACCEPT / REJECT → terminal required.
                            terminal_required = recommendation in (
                                "ACCEPT", "REJECT"
                            )

                            self.console.print(
                                f"\n[bold cyan]Evaluator recommendation:[/bold cyan] "
                                f"[bold]{recommendation}[/bold]"
                            )
                            if recommendation == "REFINE" and hints:
                                self.console.print(
                                    "[dim]Refinement hints will be passed to "
                                    "the next iteration.[/dim]"
                                )

                            choice = await self._prompt_checkpoint(
                                "evaluate",
                                str(review_path),
                            )
                            if choice == "abort":
                                return False

                            # Build the next-message prompt.  For REFINE,
                            # inject the structured hints so the orchestrator
                            # can't ignore them.  For ACCEPT/REJECT, prompt
                            # terminal signal explicitly.
                            if recommendation == "REFINE" and hints:
                                lines = [
                                    "Continue to FINALIZE / next iteration.",
                                    "",
                                    f"Evaluator returned RECOMMENDATION: REFINE "
                                    f"for v{review_iter}.  Apply the following "
                                    "structured refinement directives in the "
                                    "next iteration:",
                                ]
                                for label, key in (
                                    ("TARGET_SECTIONS", "target_sections"),
                                    ("TARGET_COMPETENCIES", "target_competencies"),
                                    ("REFINEMENT_HINTS", "refinement_hints"),
                                ):
                                    items = hints.get(key) or []
                                    if items:
                                        lines.append("")
                                        lines.append(f"{label}:")
                                        for item in items:
                                            lines.append(f"  - {item}")
                                current_message = "\n".join(lines)
                            elif recommendation == "ACCEPT":
                                current_message = (
                                    "Evaluator returned RECOMMENDATION: ACCEPT. "
                                    "Emit [OPTIMIZATION_COMPLETE] now — do NOT "
                                    "start another iteration."
                                )
                            elif recommendation == "REJECT":
                                current_message = (
                                    "Evaluator returned RECOMMENDATION: REJECT. "
                                    "Emit [OPTIMIZATION_FAILED] now (or "
                                    "[OPTIMIZATION_COMPLETE] if you choose to "
                                    "preserve the original) — do NOT start "
                                    "another iteration."
                                )
                            else:
                                current_message = "Continue to FINALIZE phase."
                            phase_transitioned = True
                            break

                    # P1.4 signal watchdog: at the end of the turn, if the
                    # orchestrator wrote a versioned file but never emitted
                    # [ITERATION_COMPLETE], either warn or hard-fail.
                    if pending_iteration_signal is not None:
                        wd_msg = (
                            "Signal watchdog: orchestrator wrote "
                            f"-v{pending_iteration_signal}.md but did not "
                            "emit [ITERATION_COMPLETE] in the same turn.  "
                            "This breaks the iteration counter, dashboard, "
                            "and pair-wise contract."
                        )
                        if self._signal_strict():
                            logger.error(
                                "CGF signal watchdog (strict)",
                                version=pending_iteration_signal,
                            )
                            task_list.error = wd_msg
                            task_list.save(self.workspace_dir)
                            self.console.print(
                                "\n[bold red]Run failed — signal watchdog "
                                "(strict mode)[/bold red]\n"
                                f"[red]{wd_msg}[/red]"
                            )
                            record_phase_entry(resource_label, "failed")
                            await asyncio.sleep(20)
                            return False
                        else:
                            logger.warning(
                                "CGF signal watchdog (warn)",
                                version=pending_iteration_signal,
                            )
                            self.console.print(
                                f"\n[yellow]{wd_msg}[/yellow]\n"
                                "[dim]Set CGF_SIGNAL_STRICT=1 to hard-fail "
                                "on this drift.[/dim]"
                            )

                    # If no phase transition occurred, the agent finished
                    # its response without a signal - continue with a prompt
                    if not phase_transitioned and not self._shutdown_requested:
                        # Small delay before continuing
                        interrupted = await self._interruptible_delay(2)
                        if interrupted:
                            break
                        current_message = "Continue."

            # If we exited the loop due to shutdown, save state
            if self._shutdown_requested:
                task_list.save(self.workspace_dir)
                self.console.print(
                    "\n[yellow]Session interrupted. State saved for resume.[/yellow]"
                )
                return False

            return True

        except Exception as e:
            logger.error("Optimization phase error", error=str(e))
            if hasattr(self, "task_list"):
                self.task_list.error = str(e)
                self.task_list.save(self.workspace_dir)
            self.console.print(f"[red]Error during optimization: {e}[/red]")
            return False


async def main() -> int:
    """Main entry point for CGF optimization sessions.

    Supports two invocation modes:
    1. SPEC.md discovery: python -m harness.cgf_session [--path PATH]
    2. Agent name (legacy): python -m harness.cgf_session --agent NAME
    """
    parser = argparse.ArgumentParser(
        description="Run CGF optimization session",
        epilog="""
Examples:
  # Discover SPEC.md automatically
  python -m harness.cgf_session

  # Specify workspace path explicitly
  python -m harness.cgf_session --path workspace/python-expert

  # Legacy mode with agent name
  python -m harness.cgf_session --agent python-expert --goal "async patterns"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--agent",
        "-a",
        help="Name of the agent to optimize (legacy mode)",
    )
    parser.add_argument(
        "--path",
        "-p",
        type=Path,
        help="Explicit workspace path (overrides discovery)",
    )
    parser.add_argument(
        "--goal",
        "-g",
        help="Optimization goal (skips Q&A if provided)",
    )
    parser.add_argument(
        "--model",
        "-m",
        help="Claude model to use (defaults to CLAUDE_MODEL env var)",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path("/workspace"),
        help="Base workspace directory (default: /workspace)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress system logs",
    )
    parser.add_argument(
        "--non-interactive",
        "--yes",
        "-y",
        action="store_true",
        help="Auto-continue at every phase checkpoint (no stdin prompts). "
        "Also enabled via CGF_NON_INTERACTIVE=1.",
    )

    args = parser.parse_args()

    # Configure logging
    import logging
    import structlog

    log_level = os.environ.get("LOG_LEVEL", "INFO")
    if args.quiet:
        log_level = "WARNING"
    level = getattr(logging, log_level.upper())
    logging.basicConfig(level=level, format="%(message)s", force=True)
    logging.getLogger().setLevel(level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level)
    )

    # Create and run session
    runner = CGFSessionRunner(
        agent_name=args.agent,
        workspace_base=args.workspace,
        workspace_path=args.path,
        goal=args.goal,
        model=args.model,
        quiet=args.quiet,
        non_interactive=args.non_interactive,
    )

    try:
        success = await runner.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        Console().print("\n[yellow]Session interrupted by user.[/yellow]")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        Console().print(f"[red]Fatal error: {e}[/red]")
        logger.exception("Fatal error in CGF session")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
