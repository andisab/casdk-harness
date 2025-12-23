"""Unit tests for optimization store models."""

from datetime import datetime, timezone

import pytest

from harness.optimization.store.models import (
    EvaluationResult,
    EvaluationStatus,
    EvaluationTask,
    Resource,
    ResourceType,
    ResourceVersion,
    StoreMetrics,
    compute_content_hash,
    generate_evaluation_id,
    generate_version_id,
)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_generate_evaluation_id_format(self) -> None:
        """Test evaluation ID format."""
        eval_id = generate_evaluation_id()

        assert eval_id.startswith("eval-")
        assert len(eval_id) == 17  # "eval-" + 12 hex chars

    def test_generate_evaluation_id_unique(self) -> None:
        """Test evaluation IDs are unique."""
        ids = [generate_evaluation_id() for _ in range(100)]

        assert len(set(ids)) == 100

    def test_generate_version_id_format(self) -> None:
        """Test version ID format."""
        version_id = generate_version_id()

        assert version_id.startswith("v-")
        assert len(version_id) == 10  # "v-" + 8 hex chars

    def test_compute_content_hash_consistent(self) -> None:
        """Test content hash is consistent."""
        content = "test content"

        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_compute_content_hash_different_content(self) -> None:
        """Test different content produces different hash."""
        hash1 = compute_content_hash("content a")
        hash2 = compute_content_hash("content b")

        assert hash1 != hash2


class TestEvaluationStatus:
    """Tests for EvaluationStatus enum."""

    def test_all_status_values(self) -> None:
        """Test all status values are defined."""
        assert EvaluationStatus.PENDING.value == "pending"
        assert EvaluationStatus.IN_PROGRESS.value == "in_progress"
        assert EvaluationStatus.COMPLETED.value == "completed"
        assert EvaluationStatus.FAILED.value == "failed"
        assert EvaluationStatus.TIMEOUT.value == "timeout"
        assert EvaluationStatus.CANCELLED.value == "cancelled"


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_all_resource_types(self) -> None:
        """Test all resource types are defined."""
        assert ResourceType.AGENT.value == "agent"
        assert ResourceType.SKILL.value == "skill"
        assert ResourceType.PROMPT.value == "prompt"
        assert ResourceType.COMMAND.value == "command"


class TestResourceVersion:
    """Tests for ResourceVersion dataclass."""

    def test_create_resource_version(self) -> None:
        """Test creating a resource version."""
        version = ResourceVersion(
            version=1,
            content_hash="abc123",
            metadata={"author": "test"},
        )

        assert version.version == 1
        assert version.content_hash == "abc123"
        assert version.metadata == {"author": "test"}
        assert version.version_id.startswith("v-")

    def test_resource_version_to_dict(self) -> None:
        """Test serializing resource version."""
        now = datetime.now(timezone.utc)
        version = ResourceVersion(
            version=2,
            version_id="v-test123",
            content_hash="hash123",
            created_at=now,
            metadata={"key": "value"},
        )

        result = version.to_dict()

        assert result["version"] == 2
        assert result["version_id"] == "v-test123"
        assert result["content_hash"] == "hash123"
        assert result["created_at"] == now.isoformat()
        assert result["metadata"] == {"key": "value"}

    def test_resource_version_from_dict(self) -> None:
        """Test deserializing resource version."""
        now = datetime.now(timezone.utc)
        data = {
            "version": 3,
            "version_id": "v-abc12345",
            "content_hash": "hashvalue",
            "created_at": now.isoformat(),
            "metadata": {"test": True},
        }

        version = ResourceVersion.from_dict(data)

        assert version.version == 3
        assert version.version_id == "v-abc12345"
        assert version.content_hash == "hashvalue"
        assert version.metadata == {"test": True}

    def test_resource_version_from_dict_missing_optional(self) -> None:
        """Test deserializing with missing optional fields."""
        data = {"version": 1}

        version = ResourceVersion.from_dict(data)

        assert version.version == 1
        assert version.version_id.startswith("v-")
        assert version.content_hash == ""
        assert version.metadata == {}


class TestResource:
    """Tests for Resource dataclass."""

    def test_create_resource(self) -> None:
        """Test creating a resource."""
        version = ResourceVersion(version=1, content_hash="hash")
        resource = Resource(
            resource_id="test-agent",
            resource_type="agent",
            content="system prompt content",
            current_version=version,
        )

        assert resource.resource_id == "test-agent"
        assert resource.resource_type == "agent"
        assert resource.content == "system prompt content"
        assert resource.current_version.version == 1

    def test_resource_to_dict(self) -> None:
        """Test serializing resource."""
        now = datetime.now(timezone.utc)
        version = ResourceVersion(version=1, content_hash="hash", created_at=now)
        resource = Resource(
            resource_id="my-skill",
            resource_type="skill",
            content="skill content",
            current_version=version,
            metadata={"source": "test"},
            created_at=now,
            updated_at=now,
        )

        result = resource.to_dict()

        assert result["resource_id"] == "my-skill"
        assert result["resource_type"] == "skill"
        assert result["content"] == "skill content"
        assert result["current_version"]["version"] == 1
        assert result["metadata"] == {"source": "test"}

    def test_resource_from_dict(self) -> None:
        """Test deserializing resource."""
        now = datetime.now(timezone.utc)
        data = {
            "resource_id": "test-prompt",
            "resource_type": "prompt",
            "content": "prompt text",
            "current_version": {
                "version": 2,
                "content_hash": "abc",
                "created_at": now.isoformat(),
            },
            "metadata": {"key": "val"},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        resource = Resource.from_dict(data)

        assert resource.resource_id == "test-prompt"
        assert resource.resource_type == "prompt"
        assert resource.current_version.version == 2


class TestEvaluationTask:
    """Tests for EvaluationTask dataclass."""

    def test_create_evaluation_task(self) -> None:
        """Test creating an evaluation task."""
        task = EvaluationTask(
            resource_id="agent-1",
            resource_type="agent",
            config={"test_cases": ["test1"]},
            priority=5,
        )

        assert task.resource_id == "agent-1"
        assert task.resource_type == "agent"
        assert task.config == {"test_cases": ["test1"]}
        assert task.priority == 5
        assert task.status == EvaluationStatus.PENDING
        assert task.evaluation_id.startswith("eval-")

    def test_evaluation_task_to_dict(self) -> None:
        """Test serializing evaluation task."""
        now = datetime.now(timezone.utc)
        task = EvaluationTask(
            evaluation_id="eval-test123456",
            resource_id="skill-1",
            resource_type="skill",
            config={},
            priority=10,
            status=EvaluationStatus.IN_PROGRESS,
            runner_id="runner-1",
            created_at=now,
            started_at=now,
        )

        result = task.to_dict()

        assert result["evaluation_id"] == "eval-test123456"
        assert result["resource_id"] == "skill-1"
        assert result["status"] == "in_progress"
        assert result["runner_id"] == "runner-1"

    def test_evaluation_task_from_dict(self) -> None:
        """Test deserializing evaluation task."""
        now = datetime.now(timezone.utc)
        data = {
            "evaluation_id": "eval-abc123def4",
            "resource_id": "prompt-1",
            "resource_type": "prompt",
            "config": {"param": "value"},
            "priority": 3,
            "status": "completed",
            "runner_id": "worker-1",
            "created_at": now.isoformat(),
            "completed_at": now.isoformat(),
        }

        task = EvaluationTask.from_dict(data)

        assert task.evaluation_id == "eval-abc123def4"
        assert task.status == EvaluationStatus.COMPLETED
        assert task.runner_id == "worker-1"


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_create_evaluation_result(self) -> None:
        """Test creating an evaluation result."""
        result = EvaluationResult(
            evaluation_id="eval-test123456",
            resource_id="agent-1",
            reward={"accuracy": 0.9, "efficiency": 0.8},
        )

        assert result.evaluation_id == "eval-test123456"
        assert result.resource_id == "agent-1"
        assert result.reward == {"accuracy": 0.9, "efficiency": 0.8}
        # Composite score auto-computed
        assert result.composite_score == pytest.approx(0.85)

    def test_compute_composite_equal_weights(self) -> None:
        """Test composite score with equal weights."""
        result = EvaluationResult(
            evaluation_id="eval-1",
            resource_id="test",
            reward={"a": 1.0, "b": 0.5, "c": 0.25},
        )

        score = result.compute_composite()

        # (1.0 + 0.5 + 0.25) / 3 = 0.5833...
        assert score == pytest.approx(0.5833, rel=0.01)

    def test_compute_composite_custom_weights(self) -> None:
        """Test composite score with custom weights."""
        result = EvaluationResult(
            evaluation_id="eval-1",
            resource_id="test",
            reward={"a": 1.0, "b": 0.5},
        )

        score = result.compute_composite(weights={"a": 0.8, "b": 0.2})

        # (1.0 * 0.8 + 0.5 * 0.2) / 1.0 = 0.9
        assert score == pytest.approx(0.9)

    def test_compute_composite_empty_reward(self) -> None:
        """Test composite score with no rewards."""
        result = EvaluationResult(
            evaluation_id="eval-1",
            resource_id="test",
            reward={},
        )

        assert result.compute_composite() == 0.0

    def test_evaluation_result_to_dict(self) -> None:
        """Test serializing evaluation result."""
        result = EvaluationResult(
            evaluation_id="eval-test",
            resource_id="agent-1",
            resource_type="agent",
            resource_version=2,
            reward={"score": 0.75},
            metadata={"notes": "good"},
        )

        data = result.to_dict()

        assert data["evaluation_id"] == "eval-test"
        assert data["resource_type"] == "agent"
        assert data["resource_version"] == 2
        assert data["reward"] == {"score": 0.75}
        assert data["composite_score"] == pytest.approx(0.75)

    def test_evaluation_result_from_dict(self) -> None:
        """Test deserializing evaluation result."""
        now = datetime.now(timezone.utc)
        data = {
            "evaluation_id": "eval-abc",
            "resource_id": "skill-1",
            "resource_type": "skill",
            "resource_version": 3,
            "reward": {"quality": 0.9},
            "composite_score": 0.9,
            "metadata": {},
            "created_at": now.isoformat(),
        }

        result = EvaluationResult.from_dict(data)

        assert result.evaluation_id == "eval-abc"
        assert result.resource_type == "skill"
        assert result.composite_score == pytest.approx(0.9)


class TestStoreMetrics:
    """Tests for StoreMetrics dataclass."""

    def test_create_store_metrics(self) -> None:
        """Test creating store metrics."""
        metrics = StoreMetrics(
            span_count=100,
            resource_count=10,
            evaluation_count=50,
            result_count=45,
            queue_length=5,
            connected=True,
        )

        assert metrics.span_count == 100
        assert metrics.queue_length == 5
        assert metrics.connected is True

    def test_store_metrics_to_dict(self) -> None:
        """Test serializing store metrics."""
        metrics = StoreMetrics(
            span_count=50,
            resource_count=5,
            evaluation_count=20,
            result_count=15,
            queue_length=3,
        )

        data = metrics.to_dict()

        assert data["span_count"] == 50
        assert data["resource_count"] == 5
        assert data["queue_length"] == 3
        assert data["connected"] is True

    def test_store_metrics_defaults(self) -> None:
        """Test store metrics defaults."""
        metrics = StoreMetrics()

        assert metrics.span_count == 0
        assert metrics.resource_count == 0
        assert metrics.connected is True
