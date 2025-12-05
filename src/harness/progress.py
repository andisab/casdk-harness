"""Progress tracking for autonomous development sessions.

This module provides:
- TaskItem: Individual task with id, title, description, acceptance_criteria
- TaskList: Immutable collection of tasks (created once by Tech Lead)
- SessionEntry: Single session record (turns, tokens, commits)
- ProgressState: Compact state with size limits (max 10 sessions, 100KB)
- ProgressManager: File I/O for task_list.json, progress.json, SESSION_n.md
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Size limits for progress state
MAX_SESSIONS_KEPT = 10
MAX_PROGRESS_SIZE_BYTES = 100 * 1024  # 100KB


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
    """Individual task with acceptance criteria.

    Once created in task_list.json, tasks are immutable.
    Only the completion status can change (tracked in progress.json).
    """
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int = 1  # 1 = highest priority

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "priority": self.priority,
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
        )


@dataclass
class TaskList:
    """Immutable collection of tasks.

    Created once by Tech Lead agent and never modified.
    The task_list.json file is read-only after initial creation.
    """
    version: str
    created_at: str
    project_name: str
    tasks: list[TaskItem]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "project_name": self.project_name,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskList":
        """Create TaskList from dictionary."""
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            project_name=data["project_name"],
            tasks=[TaskItem.from_dict(t) for t in data.get("tasks", [])],
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


@dataclass
class SessionEntry:
    """Record of a single autonomous session."""
    session_number: int
    started_at: str
    ended_at: str | None = None
    tasks_completed: list[str] = field(default_factory=list)
    tasks_blocked: list[str] = field(default_factory=list)
    git_commits: list[str] = field(default_factory=list)
    total_turns: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_number": self.session_number,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "tasks_completed": self.tasks_completed,
            "tasks_blocked": self.tasks_blocked,
            "git_commits": self.git_commits,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionEntry":
        """Create SessionEntry from dictionary."""
        return cls(
            session_number=data["session_number"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            tasks_completed=data.get("tasks_completed", []),
            tasks_blocked=data.get("tasks_blocked", []),
            git_commits=data.get("git_commits", []),
            total_turns=data.get("total_turns", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            notes=data.get("notes", ""),
        )


@dataclass
class ProgressState:
    """Compact progress state with automatic size management.

    Tracks:
    - Current task being worked on
    - Completed task IDs
    - Session history (limited to MAX_SESSIONS_KEPT)
    - Cumulative statistics
    """
    task_list_version: str
    current_task_id: str | None = None
    completed_task_ids: list[str] = field(default_factory=list)
    blocked_task_ids: list[str] = field(default_factory=list)
    sessions: list[SessionEntry] = field(default_factory=list)
    total_sessions: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_list_version": self.task_list_version,
            "current_task_id": self.current_task_id,
            "completed_task_ids": self.completed_task_ids,
            "blocked_task_ids": self.blocked_task_ids,
            "sessions": [s.to_dict() for s in self.sessions],
            "total_sessions": self.total_sessions,
            "total_cost_usd": self.total_cost_usd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressState":
        """Create ProgressState from dictionary."""
        return cls(
            task_list_version=data["task_list_version"],
            current_task_id=data.get("current_task_id"),
            completed_task_ids=data.get("completed_task_ids", []),
            blocked_task_ids=data.get("blocked_task_ids", []),
            sessions=[SessionEntry.from_dict(s) for s in data.get("sessions", [])],
            total_sessions=data.get("total_sessions", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
        )

    def add_session(self, session: SessionEntry) -> None:
        """Add a session entry, rotating old sessions if needed."""
        self.sessions.append(session)
        self.total_sessions += 1
        self.total_cost_usd += session.total_cost_usd

        # Rotate old sessions to stay within limits
        while len(self.sessions) > MAX_SESSIONS_KEPT:
            self.sessions.pop(0)

    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed."""
        if task_id not in self.completed_task_ids:
            self.completed_task_ids.append(task_id)
        if task_id in self.blocked_task_ids:
            self.blocked_task_ids.remove(task_id)
        if self.current_task_id == task_id:
            self.current_task_id = None

    def mark_task_blocked(self, task_id: str) -> None:
        """Mark a task as blocked."""
        if task_id not in self.blocked_task_ids:
            self.blocked_task_ids.append(task_id)
        if self.current_task_id == task_id:
            self.current_task_id = None

    def set_current_task(self, task_id: str) -> None:
        """Set the current task being worked on."""
        self.current_task_id = task_id


class ProgressManager:
    """Manages progress files for autonomous sessions.

    File structure:
    - task_list.json: Immutable task list (created by Tech Lead)
    - progress.json: Compact progress state (rotated)
    - sessions/SESSION_n.md: Detailed session logs (all kept)
    """

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize progress manager.

        Args:
            workspace_dir: Base directory for progress files
        """
        self.workspace_dir = workspace_dir
        self.task_list_path = workspace_dir / "task_list.json"
        self.progress_path = workspace_dir / "progress.json"
        self.sessions_dir = workspace_dir / "sessions"

        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # --- Task List Operations (Immutable after creation) ---

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
                "Task lists are immutable after creation."
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

    # --- Progress State Operations ---

    def has_progress(self) -> bool:
        """Check if progress state exists."""
        return self.progress_path.exists()

    def load_progress(self) -> ProgressState | None:
        """Load progress state from file, or None if doesn't exist."""
        if not self.progress_path.exists():
            return None

        with open(self.progress_path) as f:
            data = json.load(f)

        return ProgressState.from_dict(data)

    def save_progress(self, state: ProgressState) -> None:
        """Save progress state to file with size enforcement."""
        data = state.to_dict()
        json_str = json.dumps(data, indent=2)

        # Check size and rotate if needed
        while len(json_str.encode()) > MAX_PROGRESS_SIZE_BYTES and len(state.sessions) > 1:
            state.sessions.pop(0)
            data = state.to_dict()
            json_str = json.dumps(data, indent=2)

        with open(self.progress_path, "w") as f:
            f.write(json_str)

    def init_progress(self, task_list_version: str) -> ProgressState:
        """Initialize new progress state."""
        state = ProgressState(task_list_version=task_list_version)
        self.save_progress(state)
        return state

    # --- Session Log Operations ---

    def get_session_count(self) -> int:
        """Get number of session log files."""
        return len(list(self.sessions_dir.glob("SESSION_*.md")))

    def get_next_session_number(self) -> int:
        """Get the next session number."""
        existing = list(self.sessions_dir.glob("SESSION_*.md"))
        if not existing:
            return 1

        numbers = []
        for path in existing:
            try:
                num = int(path.stem.split("_")[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue

        return max(numbers, default=0) + 1

    def write_session_log(self, session: SessionEntry, content: str) -> Path:
        """Write detailed session log to markdown file.

        Args:
            session: Session entry with metadata
            content: Detailed session content

        Returns:
            Path to created session file
        """
        session_file = self.sessions_dir / f"SESSION_{session.session_number}.md"

        header = f"""# Session {session.session_number}

**Started**: {session.started_at}
**Ended**: {session.ended_at or "In Progress"}
**Tasks Completed**: {", ".join(session.tasks_completed) or "None"}
**Tasks Blocked**: {", ".join(session.tasks_blocked) or "None"}
**Commits**: {", ".join(session.git_commits) or "None"}
**Turns**: {session.total_turns}
**Tokens**: {session.total_tokens:,}
**Cost**: ${session.total_cost_usd:.4f}

---

"""

        with open(session_file, "w") as f:
            f.write(header + content)

        return session_file

    def load_session_log(self, session_number: int) -> str | None:
        """Load session log content.

        Args:
            session_number: Session number to load

        Returns:
            Session log content or None if not found
        """
        session_file = self.sessions_dir / f"SESSION_{session_number}.md"
        if not session_file.exists():
            return None

        with open(session_file) as f:
            return f.read()

    # --- High-Level Operations ---

    def get_next_task(self, task_list: TaskList, progress: ProgressState) -> TaskItem | None:
        """Get the next task to work on.

        Priority:
        1. Current task (if set and not completed/blocked)
        2. Highest priority incomplete task

        Args:
            task_list: The task list
            progress: Current progress state

        Returns:
            Next task to work on, or None if all complete
        """
        # Check if current task is still valid
        if progress.current_task_id:
            if (
                progress.current_task_id not in progress.completed_task_ids
                and progress.current_task_id not in progress.blocked_task_ids
            ):
                return task_list.get_task(progress.current_task_id)

        # Find next incomplete task by priority
        done_or_blocked = set(progress.completed_task_ids) | set(progress.blocked_task_ids)

        for task in task_list.get_sorted_tasks():
            if task.id not in done_or_blocked:
                return task

        return None

    def get_completion_stats(
        self, task_list: TaskList, progress: ProgressState
    ) -> dict[str, Any]:
        """Get completion statistics.

        Returns:
            Dictionary with completion stats
        """
        total = len(task_list.tasks)
        completed = len(progress.completed_task_ids)
        blocked = len(progress.blocked_task_ids)
        remaining = total - completed - blocked

        return {
            "total_tasks": total,
            "completed": completed,
            "blocked": blocked,
            "remaining": remaining,
            "completion_percent": (completed / total * 100) if total > 0 else 0,
            "total_sessions": progress.total_sessions,
            "total_cost_usd": progress.total_cost_usd,
        }

    def start_session(self) -> SessionEntry:
        """Start a new session and return the entry."""
        session_number = self.get_next_session_number()
        now = datetime.now(UTC).isoformat()

        return SessionEntry(
            session_number=session_number,
            started_at=now,
        )

    def end_session(
        self,
        session: SessionEntry,
        progress: ProgressState,
        content: str = "",
    ) -> Path:
        """End a session, update progress, and write log.

        Args:
            session: Session entry to end
            progress: Progress state to update
            content: Detailed session content for log file

        Returns:
            Path to session log file
        """
        session.ended_at = datetime.now(UTC).isoformat()
        progress.add_session(session)
        self.save_progress(progress)

        return self.write_session_log(session, content)
