"""Unit tests for progress tracking module."""

import tempfile
from pathlib import Path

import pytest

from harness.progress import (
    ProgressManager,
    QASession,
    SessionData,
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
        assert task.status is None  # Default status

    def test_task_item_with_status(self) -> None:
        """Test creating a task item with status."""
        task = TaskItem(
            id="task-001",
            title="Test task",
            description="Description",
            acceptance_criteria=["Criterion 1"],
            status="PASS",
        )

        assert task.status == "PASS"

    def test_task_item_to_dict(self) -> None:
        """Test serialization to dictionary."""
        task = TaskItem(
            id="task-001",
            title="Test task",
            description="Description",
            acceptance_criteria=["Criterion 1"],
            status="FAIL",
        )

        data = task.to_dict()

        assert data["id"] == "task-001"
        assert data["title"] == "Test task"
        assert data["priority"] == 1  # Default
        assert data["status"] == "FAIL"

    def test_task_item_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "id": "task-002",
            "title": "Another task",
            "description": "Another description",
            "acceptance_criteria": ["AC1", "AC2"],
            "priority": 2,
            "status": "PASS",
        }

        task = TaskItem.from_dict(data)

        assert task.id == "task-002"
        assert task.priority == 2
        assert len(task.acceptance_criteria) == 2
        assert task.status == "PASS"

    def test_task_item_from_dict_no_status(self) -> None:
        """Test deserialization from dictionary without status field."""
        data = {
            "id": "task-002",
            "title": "Another task",
            "description": "Another description",
            "acceptance_criteria": ["AC1"],
        }

        task = TaskItem.from_dict(data)

        assert task.status is None


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

    def test_update_task_status(self) -> None:
        """Test updating task status."""
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

        # Update existing task
        result = task_list.update_task_status("task-001", "PASS")
        assert result is True
        assert task_list.get_task("task-001").status == "PASS"

        # Update to FAIL
        result = task_list.update_task_status("task-001", "FAIL")
        assert result is True
        assert task_list.get_task("task-001").status == "FAIL"

        # Update nonexistent task
        result = task_list.update_task_status("nonexistent", "PASS")
        assert result is False

    def test_get_next_task(self) -> None:
        """Test getting next task to work on."""
        tasks = [
            TaskItem(id="t1", title="T1", description="D1", acceptance_criteria=[], priority=2),
            TaskItem(id="t2", title="T2", description="D2", acceptance_criteria=[], priority=1),
            TaskItem(id="t3", title="T3", description="D3", acceptance_criteria=[], priority=3),
        ]
        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=tasks,
        )

        # Should return highest priority (lowest number) with no status
        next_task = task_list.get_next_task()
        assert next_task is not None
        assert next_task.id == "t2"  # Priority 1

        # Mark t2 as PASS, should return t1 (priority 2)
        task_list.update_task_status("t2", "PASS")
        next_task = task_list.get_next_task()
        assert next_task is not None
        assert next_task.id == "t1"

        # Mark t1 as FAIL, should return t3 (priority 3)
        task_list.update_task_status("t1", "FAIL")
        next_task = task_list.get_next_task()
        assert next_task is not None
        assert next_task.id == "t3"

        # Mark all, should return None
        task_list.update_task_status("t3", "PASS")
        next_task = task_list.get_next_task()
        assert next_task is None

    def test_get_completion_stats(self) -> None:
        """Test getting completion statistics."""
        tasks = [
            TaskItem(id="t1", title="T1", description="D1", acceptance_criteria=[], status="PASS"),
            TaskItem(id="t2", title="T2", description="D2", acceptance_criteria=[], status="FAIL"),
            TaskItem(id="t3", title="T3", description="D3", acceptance_criteria=[]),  # No status
        ]
        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
            tasks=tasks,
        )

        stats = task_list.get_completion_stats()

        assert stats["total_tasks"] == 3
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["remaining"] == 1
        assert stats["completion_percent"] == pytest.approx(33.33, rel=0.1)


class TestSessionData:
    """Tests for SessionData dataclass."""

    def test_create_session_data(self) -> None:
        """Test creating session data."""
        session = SessionData(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            ended_at="2025-12-04T10:30:00Z",
            tasks_worked=["task-001"],
            tasks_passed=["task-001"],
            total_turns=25,
            total_tokens=50000,
            total_cost_usd=0.15,
        )

        assert session.session_number == 1
        assert session.tasks_worked == ["task-001"]
        assert session.tasks_passed == ["task-001"]
        assert session.tasks_failed == []
        assert session.git_commits == []
        assert session.total_cost_usd == 0.15
        assert session.transcript == []

    def test_session_data_to_dict(self) -> None:
        """Test serialization to dictionary."""
        session = SessionData(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            tasks_worked=["task-001"],
            tasks_passed=["task-001"],
            git_commits=["abc123"],
        )

        data = session.to_dict()

        assert data["session_number"] == 1
        assert data["tasks_worked"] == ["task-001"]
        assert data["tasks_passed"] == ["task-001"]
        assert data["tasks_failed"] == []
        assert data["git_commits"] == ["abc123"]

    def test_session_data_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "session_number": 2,
            "started_at": "2025-12-04T11:00:00Z",
            "ended_at": "2025-12-04T11:30:00Z",
            "tasks_worked": ["task-001", "task-002"],
            "tasks_passed": ["task-001"],
            "tasks_failed": ["task-002"],
            "git_commits": ["abc123", "def456"],
            "total_turns": 50,
            "total_tokens": 100000,
            "total_cost_usd": 0.30,
            "notes": "Some notes",
            "transcript": [{"role": "system", "content": "test"}],
        }

        session = SessionData.from_dict(data)

        assert session.session_number == 2
        assert len(session.tasks_worked) == 2
        assert len(session.tasks_passed) == 1
        assert len(session.tasks_failed) == 1
        assert len(session.git_commits) == 2
        assert len(session.transcript) == 1

    def test_add_message(self) -> None:
        """Test adding a message to transcript."""
        session = SessionData(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
        )

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")

        assert len(session.transcript) == 2
        assert session.transcript[0]["role"] == "user"
        assert session.transcript[0]["content"] == "Hello"


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

    def test_save_task_list(self, temp_workspace: Path) -> None:
        """Test saving task list with status updates."""
        manager = ProgressManager(temp_workspace)

        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
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

        # Update status and save
        task_list.update_task_status("task-001", "PASS")
        manager.save_task_list(task_list)

        # Load and verify
        loaded = manager.load_task_list()
        assert loaded.get_task("task-001").status == "PASS"

    def test_session_json_lifecycle(self, temp_workspace: Path) -> None:
        """Test session JSON writing and reading."""
        manager = ProgressManager(temp_workspace)

        session = SessionData(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            ended_at="2025-12-04T10:30:00Z",
            tasks_worked=["task-001"],
            tasks_passed=["task-001"],
            transcript=[{"role": "system", "content": "Session content"}],
        )

        # Save session
        path = manager.save_session(session)

        assert path.exists()
        assert "session_1.json" in str(path)

        # Load session
        loaded = manager.load_session(1)
        assert loaded is not None
        assert loaded.session_number == 1
        assert loaded.tasks_passed == ["task-001"]
        assert len(loaded.transcript) == 1

    def test_load_nonexistent_session(self, temp_workspace: Path) -> None:
        """Test loading a session that doesn't exist."""
        manager = ProgressManager(temp_workspace)

        loaded = manager.load_session(999)
        assert loaded is None

    def test_load_all_sessions(self, temp_workspace: Path) -> None:
        """Test loading all sessions."""
        manager = ProgressManager(temp_workspace)

        # Create multiple sessions
        for i in range(1, 4):
            session = SessionData(
                session_number=i,
                started_at=f"2025-12-04T{i:02d}:00:00Z",
            )
            manager.save_session(session)

        sessions = manager.load_all_sessions()

        assert len(sessions) == 3
        assert sessions[0].session_number == 1
        assert sessions[2].session_number == 3

    def test_get_totals(self, temp_workspace: Path) -> None:
        """Test computing totals from session files."""
        manager = ProgressManager(temp_workspace)

        # Create sessions with different stats
        session1 = SessionData(
            session_number=1,
            started_at="2025-12-04T10:00:00Z",
            total_turns=50,
            total_tokens=10000,
            total_cost_usd=0.10,
            git_commits=["abc123"],
        )
        session2 = SessionData(
            session_number=2,
            started_at="2025-12-04T11:00:00Z",
            total_turns=75,
            total_tokens=15000,
            total_cost_usd=0.15,
            git_commits=["def456", "ghi789"],
        )

        manager.save_session(session1)
        manager.save_session(session2)

        totals = manager.get_totals()

        assert totals["total_sessions"] == 2
        assert totals["total_turns"] == 125
        assert totals["total_tokens"] == 25000
        assert totals["total_cost_usd"] == 0.25
        assert len(totals["all_commits"]) == 3

    def test_start_session(self, temp_workspace: Path) -> None:
        """Test starting a new session."""
        manager = ProgressManager(temp_workspace)

        session = manager.start_session()

        assert session.session_number == 1
        assert session.started_at is not None
        assert session.ended_at is None

        # Start another session
        manager.save_session(session)
        session2 = manager.start_session()

        assert session2.session_number == 2

    def test_end_session(self, temp_workspace: Path) -> None:
        """Test ending a session saves both task list and session."""
        manager = ProgressManager(temp_workspace)

        # Create task list first
        task_list = TaskList(
            version="1.0",
            created_at="2025-12-04T00:00:00Z",
            project_name="Test",
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

        # Start session and update task status
        session = manager.start_session()
        task_list.update_task_status("task-001", "PASS")

        # End session
        path = manager.end_session(session, task_list)

        # Verify session was saved
        assert path.exists()

        # Verify task list was saved with status
        loaded_tasks = manager.load_task_list()
        assert loaded_tasks.get_task("task-001").status == "PASS"

        # Verify session has ended_at set
        loaded_session = manager.load_session(session.session_number)
        assert loaded_session.ended_at is not None

    def test_get_session_count(self, temp_workspace: Path) -> None:
        """Test counting session files."""
        manager = ProgressManager(temp_workspace)

        assert manager.get_session_count() == 0

        # Create sessions
        for i in range(1, 4):
            session = SessionData(session_number=i, started_at="2025-12-04T00:00:00Z")
            manager.save_session(session)

        assert manager.get_session_count() == 3

    def test_get_next_session_number(self, temp_workspace: Path) -> None:
        """Test getting next session number."""
        manager = ProgressManager(temp_workspace)

        # First session should be 1
        assert manager.get_next_session_number() == 1

        # After saving session 1, next should be 2
        session = SessionData(session_number=1, started_at="2025-12-04T00:00:00Z")
        manager.save_session(session)

        assert manager.get_next_session_number() == 2

        # Skip some numbers, next should still work
        session = SessionData(session_number=5, started_at="2025-12-04T00:00:00Z")
        manager.save_session(session)

        assert manager.get_next_session_number() == 6
