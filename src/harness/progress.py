"""Progress tracking for autonomous development sessions.

This module provides:
- WorkspaceState: Enum for detected workspace states
- WorkspaceConfig: Configuration for workspace type and branch management
- TaskItem: Individual task with id, title, description, acceptance_criteria, status
- TaskList: Collection of tasks with mutable status field
- SessionData: Complete session record including transcript
- ProgressManager: File I/O for task_list.json and session_N.json files
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal

from harness.monitoring import record_task_progress


class WorkspaceState(Enum):
    """Detected workspace states for autonomous mode.

    These states determine how the autonomous runner initializes
    and what actions are taken before entering initializer or
    continuation mode.
    """

    EMPTY = auto()  # State A: Empty or only SPEC.md
    WORK_IN_PROGRESS = auto()  # State B: task_list.json with incomplete tasks
    COMPLETED = auto()  # State C: task_list.json with all tasks done
    CONFLICT = auto()  # State D: Multiple SPEC.md or task_list.json
    EXTERNAL_REPO = auto()  # State E: Git repo without our files
    MIXED = auto()  # State F: Files present but no git repo


@dataclass
class WorkspaceConfig:
    """Workspace configuration stored in task_list.json.

    Tracks whether we're working on a local project or an external
    repository, and manages branch information for external repos.

    Attributes:
        type: "local" for new projects, "external" for cloned repos
        branch: Branch name for external repos (e.g., "casdk-feature-name")
        remote_url: Git remote URL for external repos
        initialized_from: Hash of SPEC.md when task list was created
    """

    type: Literal["local", "external"]
    branch: str | None = None
    remote_url: str | None = None
    initialized_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {"type": self.type}
        if self.branch is not None:
            result["branch"] = self.branch
        if self.remote_url is not None:
            result["remote_url"] = self.remote_url
        if self.initialized_from is not None:
            result["initialized_from"] = self.initialized_from
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceConfig":
        """Create WorkspaceConfig from dictionary."""
        return cls(
            type=data.get("type", "local"),
            branch=data.get("branch"),
            remote_url=data.get("remote_url"),
            initialized_from=data.get("initialized_from"),
        )


@dataclass
class QASession:
    """Tracks Tech Lead Q&A session state for persistence.

    This allows users to quit the Q&A session and resume later,
    maintaining context of questions asked and answers received.
    """

    started_at: str
    spec_hash: str  # Hash of SPEC.md to detect changes
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
            "spec_hash": self.spec_hash,
            "total_questions": self.total_questions,
            "current_question": self.current_question,
            "questions_asked": self.questions_asked,
            "answers_received": self.answers_received,
            "conversation_history": self.conversation_history,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QASession":
        """Create QASession from dictionary."""
        return cls(
            started_at=data["started_at"],
            spec_hash=data["spec_hash"],
            total_questions=data.get("total_questions", 0),
            current_question=data.get("current_question", 0),
            questions_asked=data.get("questions_asked", []),
            answers_received=data.get("answers_received", []),
            conversation_history=data.get("conversation_history", []),
            status=data.get("status", "in_progress"),
        )

    def add_exchange(self, question: str, answer: str) -> None:
        """Record a Q&A exchange."""
        self.questions_asked.append(question)
        self.answers_received.append(answer)
        self.conversation_history.append({"role": "assistant", "content": question})
        self.conversation_history.append({"role": "user", "content": answer})

    def is_resumable(self) -> bool:
        """Check if session can be resumed."""
        return self.status == "in_progress" and len(self.conversation_history) > 0


@dataclass
class TaskItem:
    """Individual task with acceptance criteria and status.

    Task definition fields (id, title, description, acceptance_criteria, priority)
    are immutable after creation. Only the status field can be updated.

    Status values:
    - None: Task not yet attempted
    - "PASS": Task completed successfully
    - "FAIL": Task failed/blocked
    """

    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int = 1  # 1 = highest priority
    status: Literal["PASS", "FAIL"] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "priority": self.priority,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskItem":
        """Create TaskItem from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            acceptance_criteria=data.get("acceptance_criteria", []),
            priority=data.get("priority", 1),
            status=data.get("status"),
        )


@dataclass
class TaskList:
    """Collection of tasks with mutable status field.

    Task definitions are created once by Tech Lead agent.
    Only the status field on individual tasks can be updated.

    Attributes:
        version: Schema version
        created_at: ISO timestamp when created
        project_name: Name of the project
        tasks: List of TaskItem objects
        workspace: Optional workspace configuration for external repos
    """

    version: str
    created_at: str
    project_name: str
    tasks: list[TaskItem]
    workspace: WorkspaceConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "version": self.version,
            "created_at": self.created_at,
            "project_name": self.project_name,
            "tasks": [task.to_dict() for task in self.tasks],
        }
        if self.workspace is not None:
            result["workspace"] = self.workspace.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskList":
        """Create TaskList from dictionary."""
        workspace = None
        if "workspace" in data:
            workspace = WorkspaceConfig.from_dict(data["workspace"])
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            project_name=data["project_name"],
            tasks=[TaskItem.from_dict(t) for t in data.get("tasks", [])],
            workspace=workspace,
        )

    def get_task(self, task_id: str) -> TaskItem | None:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_sorted_tasks(self) -> list[TaskItem]:
        """Get tasks sorted by priority (1 = highest)."""
        return sorted(self.tasks, key=lambda t: t.priority)

    def update_task_status(self, task_id: str, status: Literal["PASS", "FAIL"]) -> bool:
        """Update the status of a task.

        Args:
            task_id: ID of the task to update
            status: New status ("PASS" or "FAIL")

        Returns:
            True if task was found and updated, False otherwise
        """
        task = self.get_task(task_id)
        if task is None:
            return False
        task.status = status
        return True

    def get_next_task(self) -> TaskItem | None:
        """Get the next task to work on.

        Returns the highest priority task that has no status (not yet attempted).

        Returns:
            Next task to work on, or None if all tasks have been attempted
        """
        for task in self.get_sorted_tasks():
            if task.status is None:
                return task
        return None

    def get_completion_stats(self) -> dict[str, Any]:
        """Get completion statistics for the task list.

        Returns:
            Dictionary with completion stats
        """
        total = len(self.tasks)
        passed = sum(1 for t in self.tasks if t.status == "PASS")
        failed = sum(1 for t in self.tasks if t.status == "FAIL")
        remaining = total - passed - failed

        return {
            "total_tasks": total,
            "passed": passed,
            "failed": failed,
            "remaining": remaining,
            "completion_percent": (passed / total * 100) if total > 0 else 0,
        }


@dataclass
class SessionData:
    """Complete record of a single autonomous session.

    Stored as session_N.json in the sessions directory.
    Includes all metadata and the full conversation transcript.
    """

    session_number: int
    started_at: str
    ended_at: str | None = None
    tasks_worked: list[str] = field(default_factory=list)
    tasks_passed: list[str] = field(default_factory=list)
    tasks_failed: list[str] = field(default_factory=list)
    git_commits: list[str] = field(default_factory=list)
    total_turns: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    notes: str = ""
    transcript: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_number": self.session_number,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "tasks_worked": self.tasks_worked,
            "tasks_passed": self.tasks_passed,
            "tasks_failed": self.tasks_failed,
            "git_commits": self.git_commits,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "notes": self.notes,
            "transcript": self.transcript,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionData":
        """Create SessionData from dictionary."""
        return cls(
            session_number=data["session_number"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            tasks_worked=data.get("tasks_worked", []),
            tasks_passed=data.get("tasks_passed", []),
            tasks_failed=data.get("tasks_failed", []),
            git_commits=data.get("git_commits", []),
            total_turns=data.get("total_turns", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            notes=data.get("notes", ""),
            transcript=data.get("transcript", []),
        )

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the transcript."""
        self.transcript.append({"role": role, "content": content})


class ProgressManager:
    """Manages progress files for autonomous sessions.

    File structure:
    - task_list.json: Tasks with mutable status field (PASS/FAIL/null)
    - sessions/session_N.json: Complete session data including transcript
    """

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize progress manager.

        Args:
            workspace_dir: Base directory for progress files
        """
        self.workspace_dir = workspace_dir
        self.task_list_path = workspace_dir / "task_list.json"
        self.sessions_dir = workspace_dir / "sessions"

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # --- Task List Operations ---

    def has_task_list(self) -> bool:
        """Check if task list exists."""
        return self.task_list_path.exists()

    def create_task_list(self, task_list: TaskList) -> None:
        """Create new task list (fails if already exists).

        Raises:
            FileExistsError: If task list already exists
        """
        if self.task_list_path.exists():
            raise FileExistsError(
                f"Task list already exists at {self.task_list_path}. "
                "Delete it first if you want to recreate."
            )

        with open(self.task_list_path, "w") as f:
            json.dump(task_list.to_dict(), f, indent=2)

    def load_task_list(self) -> TaskList:
        """Load task list from file.

        Raises:
            FileNotFoundError: If task list doesn't exist
        """
        if not self.task_list_path.exists():
            raise FileNotFoundError(
                f"Task list not found at {self.task_list_path}. "
                "Run initializer mode first to create task list."
            )

        with open(self.task_list_path) as f:
            data = json.load(f)

        return TaskList.from_dict(data)

    def save_task_list(self, task_list: TaskList) -> None:
        """Save task list to file (updates status fields).

        Args:
            task_list: Task list to save
        """
        with open(self.task_list_path, "w") as f:
            json.dump(task_list.to_dict(), f, indent=2)

        # Surface live task counts to Prometheus for the Grafana D65
        # (Mode: Autonomous) task-progress panels.  Maps TaskItem.status
        # PASS → completed, FAIL → failed, None → pending.
        counts = {"completed": 0, "failed": 0, "pending": 0}
        for item in task_list.tasks:
            if item.status == "PASS":
                counts["completed"] += 1
            elif item.status == "FAIL":
                counts["failed"] += 1
            else:
                counts["pending"] += 1
        record_task_progress(counts)

    # --- Session Operations ---

    def get_session_count(self) -> int:
        """Get number of session files."""
        return len(list(self.sessions_dir.glob("session_*.json")))

    def get_next_session_number(self) -> int:
        """Get the next session number."""
        existing = list(self.sessions_dir.glob("session_*.json"))
        if not existing:
            return 1

        numbers = []
        for path in existing:
            try:
                # Extract number from "session_N.json"
                num = int(path.stem.split("_")[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue

        return max(numbers, default=0) + 1

    def save_session(self, session: SessionData) -> Path:
        """Save session data to JSON file.

        Args:
            session: Session data to save

        Returns:
            Path to created session file
        """
        session_file = self.sessions_dir / f"session_{session.session_number}.json"

        with open(session_file, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

        return session_file

    def load_session(self, session_number: int) -> SessionData | None:
        """Load session data from file.

        Args:
            session_number: Session number to load

        Returns:
            SessionData or None if not found
        """
        session_file = self.sessions_dir / f"session_{session_number}.json"
        if not session_file.exists():
            return None

        with open(session_file) as f:
            data = json.load(f)

        return SessionData.from_dict(data)

    def load_all_sessions(self) -> list[SessionData]:
        """Load all session data files.

        Returns:
            List of SessionData sorted by session number
        """
        sessions = []
        for path in self.sessions_dir.glob("session_*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                sessions.append(SessionData.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(sessions, key=lambda s: s.session_number)

    def get_totals(self) -> dict[str, Any]:
        """Compute aggregate totals from all session files.

        Returns:
            Dictionary with total_sessions, total_cost_usd, total_tokens,
            total_turns, and all_commits
        """
        sessions = self.load_all_sessions()

        return {
            "total_sessions": len(sessions),
            "total_cost_usd": sum(s.total_cost_usd for s in sessions),
            "total_tokens": sum(s.total_tokens for s in sessions),
            "total_turns": sum(s.total_turns for s in sessions),
            "all_commits": [c for s in sessions for c in s.git_commits],
        }

    # --- High-Level Operations ---

    def start_session(self) -> SessionData:
        """Start a new session and return the data object."""
        session_number = self.get_next_session_number()
        now = datetime.now(UTC).isoformat()

        return SessionData(
            session_number=session_number,
            started_at=now,
        )

    def end_session(self, session: SessionData, task_list: TaskList) -> Path:
        """End a session, save task list status, and write session file.

        Args:
            session: Session data to end
            task_list: Task list with updated status fields

        Returns:
            Path to session file
        """
        session.ended_at = datetime.now(UTC).isoformat()

        # Save updated task list (with any status changes)
        self.save_task_list(task_list)

        # Save session data
        return self.save_session(session)

    # --- Multi-Resource Optimization State ---

    def get_optimization_state_path(self) -> Path:
        """Get path to multi-resource optimization state file."""
        return self.sessions_dir / "optimization-state.json"

    def has_optimization_state(self) -> bool:
        """Check if multi-resource optimization state exists."""
        return self.get_optimization_state_path().exists()

    def load_optimization_state(self) -> "MultiResourceState | None":
        """Load multi-resource optimization state.

        Returns:
            MultiResourceState or None if not found.
        """
        state_path = self.get_optimization_state_path()
        if not state_path.exists():
            return None

        with open(state_path) as f:
            data = json.load(f)

        return MultiResourceState.from_dict(data)

    def save_optimization_state(self, state: "MultiResourceState") -> None:
        """Save multi-resource optimization state.

        Args:
            state: State to save.
        """
        state_path = self.get_optimization_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(state_path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)


# --- Multi-Resource Optimization State Classes ---


class OptimizationPhase(Enum):
    """Phase in multi-resource optimization pipeline.

    The pipeline progresses through these phases:
    RESEARCH -> DESIGN -> QA -> GENERATE -> EVAL_DESIGN -> ITERATE -> EXECUTION_EVAL -> VALIDATE -> COMPLETE
    """

    RESEARCH = auto()  # Gather domain knowledge
    DESIGN = auto()  # Resource architecture decision
    QA = auto()  # Gather user input on decisions
    GENERATE = auto()  # Create resources based on plan
    EVAL_DESIGN = auto()  # Generate evaluation suite
    ITERATE = auto()  # Quality-based improvement of each resource
    EXECUTION_EVAL = auto()  # Sandboxed execution evaluation
    VALIDATE = auto()  # Cross-resource coherence check
    COMPLETE = auto()  # Pipeline finished


@dataclass
class ResourceQuality:
    """Quality scores for a single resource.

    Attributes:
        completeness: Coverage of required capabilities (0.0-1.0)
        accuracy: Correctness of patterns/examples (0.0-1.0)
        clarity: Organization and readability (0.0-1.0)
        overall: Weighted average score
    """

    completeness: float = 0.0
    accuracy: float = 0.0
    clarity: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "clarity": self.clarity,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceQuality":
        """Create from dictionary."""
        return cls(
            completeness=data.get("completeness", 0.0),
            accuracy=data.get("accuracy", 0.0),
            clarity=data.get("clarity", 0.0),
            overall=data.get("overall", 0.0),
        )


@dataclass
class ResourceStatus:
    """Status of a single resource in multi-resource optimization.

    Attributes:
        path: Relative path to resource (e.g., "agents/iac-analyzer.md")
        resource_type: Type of resource (agent, skill, command)
        status: Current status (pending, in_progress, generated, optimized,
            needs_refinement, failed, unwinnable). ``unwinnable`` (F21)
            means baseline+candidate both scored 0 on every scenario in
            round 1; the orchestrator skips feedback rounds for these.
        version: Current version number (0 = original, 1+ = optimized)
        last_evaluated_version: Last version of this resource that was
            scored by EXECUTION_EVAL (F17). EXECUTION_EVAL skips
            resources whose ``version`` has not advanced past this number,
            avoiding redundant re-evals during feedback rounds.
        last_promoted_version: Most recent version that cleared the
            promotion gate (Phase A refinement 4.2). 0 means no version
            has ever promoted; the gate uses this to detect the
            "first-time promotion" regime where the floor arm runs
            (bare-model sanity check). Once any version promotes, the
            floor arm is never run again within this branch — the model
            is the experimental control and does not change mid-branch.
        quality: Quality scores (None if not yet evaluated)
        iterations: Number of optimization iterations completed
        refinement_count: Number of targeted refinement loops
        depends_on: List of resource paths this resource depends on
        depended_by: List of resource paths that depend on this resource
        error: Error message if failed
    """

    path: str
    resource_type: str
    status: Literal[
        "pending",
        "in_progress",
        "generated",
        "optimized",
        "needs_refinement",
        "failed",
        "unwinnable",
    ] = "pending"
    version: int = 0
    last_evaluated_version: int = 0
    last_promoted_version: int = 0
    quality: ResourceQuality | None = None
    iterations: int = 0
    refinement_count: int = 0
    depends_on: list[str] = field(default_factory=list)
    depended_by: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "resource_type": self.resource_type,
            "status": self.status,
            "version": self.version,
            "last_evaluated_version": self.last_evaluated_version,
            "last_promoted_version": self.last_promoted_version,
            "quality": self.quality.to_dict() if self.quality else None,
            "iterations": self.iterations,
            "refinement_count": self.refinement_count,
            "depends_on": self.depends_on,
            "depended_by": self.depended_by,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceStatus":
        """Create from dictionary."""
        quality = None
        if data.get("quality"):
            quality = ResourceQuality.from_dict(data["quality"])

        return cls(
            path=data["path"],
            resource_type=data["resource_type"],
            status=data.get("status", "pending"),
            version=data.get("version", 0),
            last_evaluated_version=data.get("last_evaluated_version", 0),
            last_promoted_version=data.get("last_promoted_version", 0),
            quality=quality,
            iterations=data.get("iterations", 0),
            refinement_count=data.get("refinement_count", 0),
            depends_on=data.get("depends_on", []),
            depended_by=data.get("depended_by", []),
            error=data.get("error", ""),
        )


@dataclass
class MultiResourceState:
    """State for multi-resource optimization pipeline.

    Tracks progress through the optimization pipeline including:
    - Current phase and completed phases
    - Per-resource status, version, and quality scores
    - References to artifacts (research findings, user decisions, plans, evals)

    Attributes:
        spec_path: Path to SPEC.md file
        spec_type: Type of spec (plugin, skill-set, workflow)
        spec_hash: Hash of SPEC.md for change detection
        current_phase: Current pipeline phase
        phases_completed: List of completed phases
        resources: Dictionary mapping resource path to status
        research_findings_path: Path to research findings YAML
        user_decisions_path: Path to Q&A decisions JSON
        resource_plan_path: Path to resource-plan.yaml from DESIGN phase
        eval_suite_path: Path to eval-suite.yaml from EVAL_DESIGN phase
        eval_results_path: Path to eval-results.json from EXECUTION_EVAL phase
        feedback_history: Execution feedback entries for the optimizer
        quality_threshold: Target quality score (default: 0.85)
        max_iterations: Max iterations per resource (default: 5)
        started_at: ISO timestamp when optimization started
        updated_at: ISO timestamp of last update
    """

    spec_path: str
    spec_type: str
    spec_hash: str
    current_phase: OptimizationPhase
    phases_completed: list[OptimizationPhase] = field(default_factory=list)
    resources: dict[str, ResourceStatus] = field(default_factory=dict)
    research_findings_path: str = ""
    user_decisions_path: str = ""
    resource_plan_path: str = ""
    eval_suite_path: str = ""
    # Phase A refinement 4.4.a: SHA-256 of eval-suite.yaml bytes captured
    # at EVAL_DESIGN exit.  EXECUTION_EVAL refuses to run if the live
    # suite hash differs — guards against mid-loop scenario rewrites
    # (intentional or accidental) leaking optimizer-side reasoning into
    # the gate.  Empty string = no hash recorded yet.
    eval_suite_hash: str = ""
    eval_results_path: str = ""
    feedback_history: list[dict[str, Any]] = field(default_factory=list)
    quality_threshold: float = 0.85
    max_iterations: int = 5
    # F9: count of VALIDATE → ITERATE loop-backs.  Capped by
    # config.max_validate_refinements so a flaky coherence-validator
    # (or an upstream defect that VALIDATE keeps flagging) can't spin
    # the pipeline indefinitely.
    validate_refinement_count: int = 0
    started_at: str = ""
    updated_at: str = ""
    # Per-phase wall-clock timings keyed by phase name (RESEARCH, DESIGN,
    # ...).  Drives RUN_REPORT.md's Mermaid gantt + per-phase table.
    # Backward-compatible: missing field on disk → empty dict on load.
    # Multi-round phases (ITERATE, EXECUTION_EVAL) overwrite each round;
    # cross-round detail is reconstructed from feedback_history.
    phase_timings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now(UTC).isoformat()
        if not self.started_at:
            self.started_at = now
        if not self.updated_at:
            self.updated_at = now
        # Seed phase_timings for the initial phase so the run-report
        # renderer has a started_at to show even before the first
        # advance_phase() call.
        phase_name = self.current_phase.name
        if phase_name not in self.phase_timings:
            self.phase_timings[phase_name] = {
                "started_at": now,
                "completed_at": None,
                "duration_s": None,
            }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_path": self.spec_path,
            "spec_type": self.spec_type,
            "spec_hash": self.spec_hash,
            "current_phase": self.current_phase.name,
            "phases_completed": [p.name for p in self.phases_completed],
            "resources": {path: status.to_dict() for path, status in self.resources.items()},
            "research_findings_path": self.research_findings_path,
            "user_decisions_path": self.user_decisions_path,
            "resource_plan_path": self.resource_plan_path,
            "eval_suite_path": self.eval_suite_path,
            "eval_suite_hash": self.eval_suite_hash,
            "eval_results_path": self.eval_results_path,
            "feedback_history": self.feedback_history,
            "quality_threshold": self.quality_threshold,
            "max_iterations": self.max_iterations,
            "validate_refinement_count": self.validate_refinement_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "phase_timings": self.phase_timings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MultiResourceState":
        """Create from dictionary."""
        return cls(
            spec_path=data["spec_path"],
            spec_type=data["spec_type"],
            spec_hash=data["spec_hash"],
            current_phase=OptimizationPhase[data["current_phase"]],
            phases_completed=[OptimizationPhase[p] for p in data.get("phases_completed", [])],
            resources={
                path: ResourceStatus.from_dict(status)
                for path, status in data.get("resources", {}).items()
            },
            research_findings_path=data.get("research_findings_path", ""),
            user_decisions_path=data.get("user_decisions_path", ""),
            resource_plan_path=data.get("resource_plan_path", ""),
            eval_suite_path=data.get("eval_suite_path", ""),
            eval_suite_hash=data.get("eval_suite_hash", ""),
            eval_results_path=data.get("eval_results_path", ""),
            feedback_history=data.get("feedback_history", []),
            quality_threshold=data.get("quality_threshold", 0.85),
            max_iterations=data.get("max_iterations", 5),
            validate_refinement_count=data.get("validate_refinement_count", 0),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
            phase_timings=data.get("phase_timings", {}),
        )

    def advance_phase(self, next_phase: OptimizationPhase) -> None:
        """Advance to the next phase.

        Args:
            next_phase: Phase to advance to.
        """
        now_iso = datetime.now(UTC).isoformat()
        now_dt = datetime.now(UTC)

        # Close out the current phase's timing entry.
        current_name = self.current_phase.name
        current_entry = self.phase_timings.get(current_name)
        if current_entry and current_entry.get("started_at"):
            current_entry["completed_at"] = now_iso
            try:
                started = datetime.fromisoformat(current_entry["started_at"])
                current_entry["duration_s"] = (now_dt - started).total_seconds()
            except (TypeError, ValueError):
                current_entry["duration_s"] = None
        else:
            # Phase entry never opened (e.g. resumed state w/o seed) —
            # record a zero-duration placeholder so the renderer still
            # has something to show.
            self.phase_timings[current_name] = {
                "started_at": now_iso,
                "completed_at": now_iso,
                "duration_s": 0.0,
            }

        if self.current_phase not in self.phases_completed:
            self.phases_completed.append(self.current_phase)
        self.current_phase = next_phase
        self.updated_at = now_iso

        # Open a timing entry for the new phase.  Backward transitions
        # (EXECUTION_EVAL → ITERATE, VALIDATE → ITERATE) overwrite the
        # previous round's timing for that phase; the renderer
        # reconstructs round-1 vs round-2 history from feedback_history
        # rather than from this dict.
        self.phase_timings[next_phase.name] = {
            "started_at": now_iso,
            "completed_at": None,
            "duration_s": None,
        }

    def add_resource(
        self,
        path: str,
        resource_type: str,
    ) -> ResourceStatus:
        """Add a resource to track.

        Args:
            path: Relative path to resource.
            resource_type: Type of resource.

        Returns:
            Created ResourceStatus.
        """
        status = ResourceStatus(path=path, resource_type=resource_type)
        self.resources[path] = status
        self.updated_at = datetime.now(UTC).isoformat()
        return status

    def update_resource(
        self,
        path: str,
        status: Literal[
            "pending",
            "in_progress",
            "generated",
            "optimized",
            "needs_refinement",
            "failed",
            "unwinnable",
        ]
        | None = None,
        version: int | None = None,
        last_evaluated_version: int | None = None,
        last_promoted_version: int | None = None,
        quality: ResourceQuality | None = None,
        iterations: int | None = None,
        refinement_count: int | None = None,
        depends_on: list[str] | None = None,
        depended_by: list[str] | None = None,
        error: str | None = None,
    ) -> ResourceStatus | None:
        """Update a resource's status.

        Args:
            path: Resource path.
            status: New status.
            version: New version number.
            last_evaluated_version: Last EXECUTION_EVAL'd version (F17).
            quality: New quality scores.
            iterations: Number of iterations.
            refinement_count: Number of refinement loops.
            depends_on: List of dependencies.
            depended_by: List of dependents.
            error: Error message.

        Returns:
            Updated ResourceStatus or None if not found.
        """
        if path not in self.resources:
            return None

        resource = self.resources[path]
        if status is not None:
            resource.status = status
            # Clear error on successful status transitions
            if status in ("generated", "optimized") and error is None:
                resource.error = ""
        if version is not None:
            resource.version = version
        if last_evaluated_version is not None:
            resource.last_evaluated_version = last_evaluated_version
        if last_promoted_version is not None:
            resource.last_promoted_version = last_promoted_version
        if quality is not None:
            resource.quality = quality
        if iterations is not None:
            resource.iterations = iterations
        if refinement_count is not None:
            resource.refinement_count = refinement_count
        if depends_on is not None:
            resource.depends_on = depends_on
        if depended_by is not None:
            resource.depended_by = depended_by
        if error is not None:
            resource.error = error

        self.updated_at = datetime.now(UTC).isoformat()
        return resource

    def get_pending_resources(self) -> list[ResourceStatus]:
        """Get resources that haven't been processed yet."""
        return [r for r in self.resources.values() if r.status == "pending"]

    def get_in_progress_resources(self) -> list[ResourceStatus]:
        """Get resources currently being processed."""
        return [r for r in self.resources.values() if r.status == "in_progress"]

    def get_optimized_resources(self) -> list[ResourceStatus]:
        """Get resources that have been optimized."""
        return [r for r in self.resources.values() if r.status == "optimized"]

    def get_failed_resources(self) -> list[ResourceStatus]:
        """Get resources that failed optimization."""
        return [r for r in self.resources.values() if r.status == "failed"]

    def all_resources_complete(self) -> bool:
        """Check if all resources are optimized or failed."""
        return all(
            r.status in ("optimized", "failed") for r in self.resources.values()
        )

    def get_generated_resources(self) -> list[ResourceStatus]:
        """Get resources that have been generated but not yet optimized."""
        return [r for r in self.resources.values() if r.status == "generated"]

    def get_needs_refinement_resources(self) -> list[ResourceStatus]:
        """Get resources that need targeted refinement."""
        return [r for r in self.resources.values() if r.status == "needs_refinement"]

    def all_resources_generated(self) -> bool:
        """Check if all resources have been generated (status >= generated)."""
        generated_states = ("generated", "in_progress", "optimized", "needs_refinement")
        return all(
            r.status in generated_states or r.status == "failed"
            for r in self.resources.values()
        )

    def get_resources_by_status(self, status: str) -> list[ResourceStatus]:
        """Get resources with a specific status."""
        return [r for r in self.resources.values() if r.status == status]

    def add_dependency(self, resource_path: str, depends_on_path: str) -> bool:
        """Add a dependency relationship between resources.

        Args:
            resource_path: The resource that has the dependency.
            depends_on_path: The resource being depended upon.

        Returns:
            True if dependency was added, False if resources not found.
        """
        if resource_path not in self.resources or depends_on_path not in self.resources:
            return False

        resource = self.resources[resource_path]
        target = self.resources[depends_on_path]

        if depends_on_path not in resource.depends_on:
            resource.depends_on.append(depends_on_path)
        if resource_path not in target.depended_by:
            target.depended_by.append(resource_path)

        self.updated_at = datetime.now(UTC).isoformat()
        return True

    def get_completion_stats(self) -> dict[str, Any]:
        """Get completion statistics."""
        total = len(self.resources)
        optimized = len(self.get_optimized_resources())
        failed = len(self.get_failed_resources())
        pending = len(self.get_pending_resources())
        in_progress = len(self.get_in_progress_resources())
        generated = len(self.get_generated_resources())
        needs_refinement = len(self.get_needs_refinement_resources())

        return {
            "total": total,
            "optimized": optimized,
            "failed": failed,
            "pending": pending,
            "in_progress": in_progress,
            "generated": generated,
            "needs_refinement": needs_refinement,
            "completion_percent": (optimized / total * 100) if total > 0 else 0,
        }
