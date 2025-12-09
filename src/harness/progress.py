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
