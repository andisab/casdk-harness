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
    "research_iterate",  # Agentic optimization using research
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
    ) -> None:
        """Initialize the CGF session runner.

        Args:
            agent_name: Name of the agent to optimize (legacy mode)
            workspace_base: Base directory for workspaces (default: /workspace)
            workspace_path: Explicit workspace path (overrides discovery)
            goal: Optional optimization goal (bypasses Q&A if provided)
            model: Claude model to use (defaults to config)
            quiet: Suppress system logs
        """
        self.agent_name = agent_name
        self.workspace_base = workspace_base or Path("/workspace")
        self.workspace_path_override = workspace_path
        self.workspace_dir: Path | None = None  # Set during discovery
        self.goal = goal
        self.model_override = model
        self.quiet = quiet
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
                "plugins/cgf-agents/agents/cgf-orchestrator"
            )
        except FileNotFoundError:
            # Try alternate path
            orchestrator_path = (
                Path("src/harness/plugins/cgf-agents/agents/cgf-orchestrator.md")
            )
            if orchestrator_path.exists():
                orchestrator_prompt = orchestrator_path.read_text()
            else:
                raise FileNotFoundError(
                    "cgf-orchestrator.md not found in prompts or plugins"
                )

        # Read current resource content
        resource_content = spec.resource_path.read_text()

        prompt = f"""{orchestrator_prompt}

---

## Loaded CGF Specification

The following specification was created during the Q&A phase:

```yaml
{yaml.safe_dump(spec.to_dict(), default_flow_style=False)}
```

## Current Resource Content

**File**: {spec.resource_path}

```markdown
{resource_content}
```

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
        elif phase == "research_iterate":
            return (
                f"Resume from RESEARCH_ITERATE phase (iteration {iteration}). "
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

                while not self._shutdown_requested:
                    phase_transitioned = False
                    accumulated_content = ""

                    async for message in agent_session.execute(current_message):
                        content = self._extract_content_str(message)
                        accumulated_content += content
                        parse_and_print_message(message, self.console)

                        # Check for terminal signals first
                        if "[OPTIMIZATION_COMPLETE]" in content:
                            task_list.current_phase = "complete"
                            task_list.add_checkpoint(
                                "complete",
                                str(self.workspace_dir),
                                "Optimization completed successfully",
                            )
                            task_list.save(self.workspace_dir)
                            self.console.print(
                                "\n[bold green]Optimization completed![/bold green]"
                            )
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
                            task_list.current_phase = (
                                "test_gen"
                                if spec.optimizer_mode in ("python", "both")
                                else "research_iterate"
                            )
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
                            task_list.current_phase = "optimize"
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
                            task_list.iteration += 1
                            task_list.save(self.workspace_dir)

                            # Prompt for iteration review if enabled
                            if spec.iteration_review:
                                # Use resource_name for versioned files
                                version_file = (
                                    f"{self.resource_name}-v{task_list.iteration}.md"
                                )
                                choice = await self._prompt_checkpoint(
                                    f"iteration {task_list.iteration}",
                                    str(self.workspace_dir / version_file),
                                )
                                if choice == "abort":
                                    return False
                                elif choice == "edit":
                                    current_message = (
                                        "User edited the resource. "
                                        "Continue with next iteration."
                                    )
                                else:
                                    current_message = "Continue with next iteration."
                            else:
                                current_message = "Continue with next iteration."
                            phase_transitioned = True
                            break

                        if "[EVALUATE_COMPLETE]" in content:
                            task_list.current_phase = "finalize"
                            task_list.save(self.workspace_dir)

                            choice = await self._prompt_checkpoint(
                                "evaluate",
                                str(self.workspace_dir / "reviews"),
                            )
                            if choice == "abort":
                                return False
                            current_message = "Continue to FINALIZE phase."
                            phase_transitioned = True
                            break

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
