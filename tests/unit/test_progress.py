"""Unit tests for progress tracking module."""

import tempfile
from pathlib import Path

import pytest

from harness.progress import (
    MAX_SESSIONS_KEPT,
    ProgressManager,
    ProgressState,
    QASession,
    SessionEntry,
    TaskItem,
    TaskList,
)


class TestQASession:
    """Tests for QASession dataclass."""

    def test_create_qa_session(self) -> None:
        """Test creating a QA session."""
        session = QASession(
            started_at="2025-12-04T10:00:00Z",
            spec_hash="abc123",
        )

        assert session.started_at == "2025-12-04T10:00:00Z"
        assert session.spec_hash == "abc123"
        assert session.total_questions == 0
        assert session.current_question == 0
        assert session.questions_asked == []
        assert session.answers_received == []
        assert session.conversation_history == []
        assert session.status == "in_progress"

    def test_qa_session_to_dict(self) -> None:
        """Test serialization to dictionary."""
        session = QASession(
            started_at="2025-12-04T10:00:00Z",
            spec_hash="abc123",
            total_questions=10,
            current_question=3,
        )

        data = session.to_dict()

        assert data["started_at"] == "2025-12-04T10:00:00Z"
        assert data["spec_hash"] == "abc123"
        assert data["total_questions"] == 10
        assert data["current_question"] == 3

    def test_qa_session_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "started_at": "2025-12-04T10:00:00Z",
            "spec_hash": "def456",
            "total_questions": 15,
            "current_question": 5,
            "questions_asked": ["Q1", "Q2"],
            "answers_received": ["A1", "A2"],
            "conversation_history": [
                {"role": "assistant", "content": "Q1"},
                {"role": "user", "content": "A1"},
            ],
            "status": "in_progress",
        }

        session = QASession.from_dict(data)

        assert session.spec_hash == "def456"
        assert session.total_questions == 15
        assert len(session.questions_asked) == 2
        assert len(session.conversation_history) == 2

    def test_add_exchange(self) -> None:
        """Test adding a Q&A exchange."""
        session = QASession(
            started_at="2025-12-04T10:00:00Z",
            spec_hash="abc123",
        )

        session.add_exchange("What framework should we use?", "Use FastAPI")

        assert len(session.questions_asked) == 1
        assert len(session.answers_received) == 1
        assert len(session.conversation_history) == 2
        assert session.questions_asked[0] == "What framework should we use?"
        assert session.answers_received[0] == "Use FastAPI"
        assert session.conversation_history[0]["role"] == "assistant"
        assert session.conversation_history[1]["role"] == "user"

    def test_is_resumable(self) -> None:
        """Test checking if session is resumable."""
        session = QASession(
            started_at="2025-12-04T10:00:00Z",
            spec_hash="abc123",
        )

        # Empty session is not resumable
        assert not session.is_resumable()

        # Session with conversation history is resumable
        session.add_exchange("Q1", "A1")
        assert session.is_resumable()

        # Completed session is not resumable
        session.status = "completed"
        assert not session.is_resumable()

    def test_round_trip_serialization(self) -> None:
        """Test that serialization and deserialization preserves data."""
        session = QASession(
            started_at="2025-12-04T10:00:00Z",
            spec_hash="abc123",
            total_questions=12,
            current_question=4,
        )
        session.add_exchange("Q1", "A1")
        session.add_exchange("Q2", "A2")

        # Serialize and deserialize
        data = session.to_dict()
        restored = QASession.from_dict(data)

        assert restored.started_at == session.started_at
        assert restored.spec_hash == session.spec_hash
        assert restored.total_questions == session.total_questions
        assert restored.current_question == session.current_question
        assert len(restored.questions_asked) == 2
        assert len(restored.conversation_history) == 4


class TestTaskItem:
    """Tests for TaskItem dataclass."""

    def test_create_task_item(self) -> None:
        """Test creating a task item."""
        task = TaskItem(
            id="task-001",
            title="Implement user authentication",
            description="Add OAuth2 authentication flow",
            acceptance_criteria=["Users can log in", "Tokens are stored securely"],
            priority=1,
        )

        assert task.id == "task-001"
        assert task.title == "Implement user authentication"
        assert task.priority == 1
        assert len(task.acceptance_criteria) == 2

    def test_task_item_to_dict(self) -> None:
        """Test serialization to dictionary."""
        task = TaskItem(
            id="task-001",
            title="Test task",
            description="Description",
            acceptance_criteria=["Criterion 1"],
        )

        data = task.to_dict()

        assert data["id"] == "task-001"
        assert data["title"] == "Test task"
        assert data["priority"] == 1  # Default

    def test_task_item_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "id": "task-002",
            "title": "Another task",
            "description": "Another description",
            "acceptance_criteria": ["AC1", "AC2"],
            "priority": 2,
        }

        task = TaskItem.from_dict(data)

        assert task.id == "task-002"
        assert task.priority == 2
        assert len(task.acceptance_criteria) == 2


class TestTaskList:
    """Tests for TaskList dataclass."""

    def test_create_task_list(self) -> None:
        """Test creating a task list."""
        tasks = [
            TaskItem(
                id="task-001",
                title="Task 1",
                description="Desc 1",
                acceptance_criteria=["AC1"],
            ),
            TaskItem(
                id="task-002",
                title="Task 2",
                description="Desc 2",
                acceptance_criteria=["AC2"],
                priority=2,
            ),
        ]

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test Project",
            tasks=tasks,
        )

        assert task_list.version == "1.0"
        assert task_list.project_name == "Test Project"
        assert len(task_list.tasks) == 2

    def test_get_task(self) -> None:
        """Test getting a task by ID."""
        task = TaskItem(
            id="task-001",
            title="Task 1",
            description="Desc 1",
            acceptance_criteria=["AC1"],
        )
        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=[task],
        )

        result = task_list.get_task("task-001")
        assert result is not None
        assert result.id == "task-001"

        result = task_list.get_task("nonexistent")
        assert result is None

    def test_get_sorted_tasks(self) -> None:
        """Test sorting tasks by priority."""
        tasks = [
            TaskItem(id="t1", title="T1", description="D1", acceptance_criteria=[], priority=3),
            TaskItem(id="t2", title="T2", description="D2", acceptance_criteria=[], priority=1),
            TaskItem(id="t3", title="T3", description="D3", acceptance_criteria=[], priority=2),
        ]
        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=tasks,
        )

        sorted_tasks = task_list.get_sorted_tasks()

        assert sorted_tasks[0].id == "t2"  # Priority 1
        assert sorted_tasks[1].id == "t3"  # Priority 2
        assert sorted_tasks[2].id == "t1"  # Priority 3


class TestSessionEntry:
    """Tests for SessionEntry dataclass."""

    def test_create_session_entry(self) -> None:
        """Test creating a session entry."""
        session = SessionEntry(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            ended_at="2025-12-04T10:30:00Z",
            tasks_completed=["task-001"],
            total_turns=25,
            total_tokens=50000,
            total_cost_usd=0.15,
        )

        assert session.session_number == 1
        assert session.tasks_completed == ["task-001"]
        assert session.total_cost_usd == 0.15

    def test_session_entry_serialization(self) -> None:
        """Test session entry round-trip serialization."""
        session = SessionEntry(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            tasks_completed=["task-001"],
        )

        data = session.to_dict()
        restored = SessionEntry.from_dict(data)

        assert restored.session_number == session.session_number
        assert restored.tasks_completed == session.tasks_completed


class TestProgressState:
    """Tests for ProgressState dataclass."""

    def test_add_session_rotates_old(self) -> None:
        """Test that adding sessions rotates old ones."""
        state = ProgressState(task_list_version="1.0")

        # Add MAX_SESSIONS_KEPT + 2 sessions
        for i in range(MAX_SESSIONS_KEPT + 2):
            session = SessionEntry(
                session_number=i + 1,
                started_at=f"2025-12-04T{i:02d}:00:00Z",
            )
            state.add_session(session)

        # Should only keep MAX_SESSIONS_KEPT
        assert len(state.sessions) == MAX_SESSIONS_KEPT
        assert state.total_sessions == MAX_SESSIONS_KEPT + 2
        # First session should be session number 3 (1 and 2 rotated out)
        assert state.sessions[0].session_number == 3

    def test_mark_task_completed(self) -> None:
        """Test marking a task as completed."""
        state = ProgressState(task_list_version="1.0")
        state.current_task_id = "task-001"

        state.mark_task_completed("task-001")

        assert "task-001" in state.completed_task_ids
        assert state.current_task_id is None

    def test_mark_task_blocked(self) -> None:
        """Test marking a task as blocked."""
        state = ProgressState(task_list_version="1.0")
        state.current_task_id = "task-001"

        state.mark_task_blocked("task-001")

        assert "task-001" in state.blocked_task_ids
        assert state.current_task_id is None


class TestProgressManager:
    """Tests for ProgressManager class."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_and_load_task_list(self, temp_workspace: Path) -> None:
        """Test creating and loading a task list."""
        manager = ProgressManager(temp_workspace)

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test Project",
            tasks=[
                TaskItem(
                    id="task-001",
                    title="Task 1",
                    description="Desc 1",
                    acceptance_criteria=["AC1"],
                ),
            ],
        )

        manager.create_task_list(task_list)

        assert manager.has_task_list()

        loaded = manager.load_task_list()
        assert loaded.version == "1.0"
        assert loaded.project_name == "Test Project"
        assert len(loaded.tasks) == 1

    def test_create_task_list_fails_if_exists(self, temp_workspace: Path) -> None:
        """Test that creating a task list fails if one exists."""
        manager = ProgressManager(temp_workspace)

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=[],
        )

        manager.create_task_list(task_list)

        with pytest.raises(FileExistsError):
            manager.create_task_list(task_list)

    def test_progress_state_lifecycle(self, temp_workspace: Path) -> None:
        """Test progress state save and load."""
        manager = ProgressManager(temp_workspace)

        # Initialize progress
        state = manager.init_progress("1.0")
        assert state.task_list_version == "1.0"

        # Update and save
        state.mark_task_completed("task-001")
        manager.save_progress(state)

        # Load and verify
        loaded = manager.load_progress()
        assert loaded is not None
        assert "task-001" in loaded.completed_task_ids

    def test_get_next_task(self, temp_workspace: Path) -> None:
        """Test getting the next task to work on."""
        manager = ProgressManager(temp_workspace)

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=[
                TaskItem(id="t1", title="T1", description="D1", acceptance_criteria=[], priority=2),
                TaskItem(id="t2", title="T2", description="D2", acceptance_criteria=[], priority=1),
            ],
        )

        state = ProgressState(task_list_version="1.0")

        # Should return highest priority (lowest number)
        next_task = manager.get_next_task(task_list, state)
        assert next_task is not None
        assert next_task.id == "t2"  # Priority 1

        # Mark t2 completed, should return t1
        state.mark_task_completed("t2")
        next_task = manager.get_next_task(task_list, state)
        assert next_task is not None
        assert next_task.id == "t1"

        # Mark t1 completed, should return None
        state.mark_task_completed("t1")
        next_task = manager.get_next_task(task_list, state)
        assert next_task is None

    def test_session_log_lifecycle(self, temp_workspace: Path) -> None:
        """Test session log writing and reading."""
        manager = ProgressManager(temp_workspace)

        session = SessionEntry(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            ended_at="2025-12-04T10:30:00Z",
            tasks_completed=["task-001"],
        )

        # Write session log
        path = manager.write_session_log(session, "Session content here")

        assert path.exists()
        assert "SESSION_1.md" in str(path)

        # Read session log
        content = manager.load_session_log(1)
        assert content is not None
        assert "Session 1" in content
        assert "task-001" in content

    def test_get_completion_stats(self, temp_workspace: Path) -> None:
        """Test getting completion statistics."""
        manager = ProgressManager(temp_workspace)

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=[
                TaskItem(id="t1", title="T1", description="D1", acceptance_criteria=[]),
                TaskItem(id="t2", title="T2", description="D2", acceptance_criteria=[]),
                TaskItem(id="t3", title="T3", description="D3", acceptance_criteria=[]),
            ],
        )

        state = ProgressState(task_list_version="1.0")
        state.mark_task_completed("t1")
        state.mark_task_blocked("t2")

        stats = manager.get_completion_stats(task_list, state)

        assert stats["total_tasks"] == 3
        assert stats["completed"] == 1
        assert stats["blocked"] == 1
        assert stats["remaining"] == 1
        assert stats["completion_percent"] == pytest.approx(33.33, rel=0.1)
