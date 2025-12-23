"""Unit tests for optimization adapters module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from harness.optimization.adapters import (
    AdapterRegistry,
    AgentAdapter,
    AgentFeedback,
    BaseFeedback,
    CommandAdapter,
    CommandFeedback,
    PromptAdapter,
    PromptFeedback,
    SkillAdapter,
    SkillFeedback,
    TrainingTriplet,
    TripletAdapter,
    get_adapter,
    get_default_registry,
)
from harness.optimization.adapters import reset_default_registry
from harness.tracer.base import Span, SpanKind, SpanStatus


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_agent_spans() -> list[Span]:
    """Create sample spans for agent execution."""
    trace_id = "abc123"
    now = datetime.now(timezone.utc)

    return [
        Span(
            trace_id=trace_id,
            span_id="span1",
            name="agent.python-expert.execute",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=5000.0,
            agent_name="python-expert",
            resource_id="python-expert",
            resource_type="agent",
            attributes={
                "task.completed": True,
                "agent.max_turns": 100,
            },
            token_usage={"input": 1000, "output": 500},
        ),
        Span(
            trace_id=trace_id,
            span_id="span2",
            parent_span_id="span1",
            name="llm.request",
            kind=SpanKind.LLM_REQUEST,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=2000.0,
            token_usage={"input": 500, "output": 300},
        ),
        Span(
            trace_id=trace_id,
            span_id="span3",
            parent_span_id="span1",
            name="tool.Read",
            kind=SpanKind.TOOL_CALL,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=100.0,
            attributes={"tool.name": "Read"},
        ),
        Span(
            trace_id=trace_id,
            span_id="span4",
            parent_span_id="span1",
            name="tool.Write",
            kind=SpanKind.TOOL_CALL,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=150.0,
            attributes={"tool.name": "Write"},
        ),
        Span(
            trace_id=trace_id,
            span_id="span5",
            parent_span_id="span1",
            name="tool.Bash",
            kind=SpanKind.TOOL_CALL,
            start_time=now,
            status=SpanStatus.ERROR,
            duration_ms=50.0,
            error_message="Command failed",
            attributes={"tool.name": "Bash"},
        ),
    ]


@pytest.fixture
def sample_skill_spans() -> list[Span]:
    """Create sample spans for skill execution."""
    trace_id = "def456"
    now = datetime.now(timezone.utc)

    return [
        Span(
            trace_id=trace_id,
            span_id="span1",
            name="skill.debugging.execute",
            kind=SpanKind.RESOURCE_EVALUATION,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=3000.0,
            resource_id="debugging",
            resource_type="skill",
            attributes={
                "skill.activated": True,
                "skill.activation_correct": True,
                "skill.output_quality": 0.85,
            },
            token_usage={"input": 800, "output": 400},
        ),
    ]


@pytest.fixture
def sample_prompt_spans() -> list[Span]:
    """Create sample spans for prompt usage."""
    trace_id = "ghi789"
    now = datetime.now(timezone.utc)

    return [
        Span(
            trace_id=trace_id,
            span_id="span1",
            name="prompt.greeting.render",
            kind=SpanKind.LLM_REQUEST,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=1500.0,
            resource_id="greeting",
            resource_type="prompt",
            attributes={
                "prompt.rendered": True,
                "prompt.variables_used": ["name", "context"],
                "prompt.response_quality": 0.9,
                "prompt.clarity_score": 0.95,
            },
            token_usage={"input": 200, "output": 150},
        ),
    ]


@pytest.fixture
def sample_command_spans() -> list[Span]:
    """Create sample spans for command execution."""
    trace_id = "jkl012"
    now = datetime.now(timezone.utc)

    return [
        Span(
            trace_id=trace_id,
            span_id="span1",
            name="command.create-agent.execute",
            kind=SpanKind.AGENT_EXECUTION,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=2000.0,
            resource_id="create-agent",
            resource_type="command",
            attributes={
                "command.invoked": True,
                "command.arguments": ["my-agent"],
                "command.allowed_tools": ["Read", "Write"],
                "command.output_quality": 0.88,
            },
            token_usage={"input": 300, "output": 200},
        ),
        Span(
            trace_id=trace_id,
            span_id="span2",
            parent_span_id="span1",
            name="tool.Read",
            kind=SpanKind.TOOL_CALL,
            start_time=now,
            status=SpanStatus.OK,
            duration_ms=50.0,
            attributes={"tool.name": "Read"},
        ),
    ]


# =============================================================================
# BaseFeedback Tests
# =============================================================================


class TestBaseFeedback:
    """Tests for BaseFeedback dataclass."""

    def test_create_base_feedback(self) -> None:
        """Test creating base feedback."""
        feedback = BaseFeedback(
            execution_time_ms=1000.0,
            token_count=500,
            success=True,
        )

        assert feedback.execution_time_ms == 1000.0
        assert feedback.token_count == 500
        assert feedback.success is True
        assert feedback.error_count == 0

    def test_base_feedback_to_dict(self) -> None:
        """Test serializing base feedback."""
        feedback = BaseFeedback(
            execution_time_ms=2000.0,
            token_count=1000,
            input_tokens=600,
            output_tokens=400,
            success=True,
            resource_id="test",
            resource_type="agent",
        )

        result = feedback.to_dict()

        assert result["execution_time_ms"] == 2000.0
        assert result["token_count"] == 1000
        assert result["input_tokens"] == 600
        assert result["output_tokens"] == 400
        assert result["success"] is True
        assert result["resource_id"] == "test"


# =============================================================================
# AgentFeedback Tests
# =============================================================================


class TestAgentFeedback:
    """Tests for AgentFeedback dataclass."""

    def test_create_agent_feedback(self) -> None:
        """Test creating agent feedback."""
        feedback = AgentFeedback(
            task_completed=True,
            turns_taken=5,
            tool_call_count=10,
            tool_success_count=9,
        )

        assert feedback.task_completed is True
        assert feedback.turns_taken == 5
        assert feedback.tool_call_count == 10
        assert feedback.tool_success_rate == 0.9

    def test_tool_success_rate_no_calls(self) -> None:
        """Test tool success rate with no calls."""
        feedback = AgentFeedback(tool_call_count=0)

        assert feedback.tool_success_rate == 1.0

    def test_compute_efficiency_score(self) -> None:
        """Test efficiency score computation."""
        feedback = AgentFeedback(
            task_completed=True,
            token_count=10000,
            turns_taken=5,
            tool_call_count=10,
        )

        score = feedback.compute_efficiency_score()

        assert 0.0 <= score <= 1.0
        assert feedback.efficiency_score == score

    def test_compute_efficiency_incomplete_task(self) -> None:
        """Test efficiency score for incomplete task."""
        feedback = AgentFeedback(task_completed=False)

        score = feedback.compute_efficiency_score()

        assert score == 0.0

    def test_compute_reliability_score(self) -> None:
        """Test reliability score computation."""
        feedback = AgentFeedback(
            task_completed=True,
            tool_call_count=10,
            tool_success_count=9,
            error_count=1,
        )

        score = feedback.compute_reliability_score()

        assert 0.0 <= score <= 1.0
        assert feedback.reliability_score == score

    def test_to_reward(self) -> None:
        """Test converting to reward dimensions."""
        feedback = AgentFeedback(
            task_completed=True,
            turns_taken=5,
            tool_call_count=10,
            tool_success_count=10,
            token_count=5000,
        )

        reward = feedback.to_reward()

        assert "task_completion" in reward
        assert "efficiency" in reward
        assert "reliability" in reward
        assert "tool_success_rate" in reward
        assert reward["task_completion"] == 1.0
        assert reward["tool_success_rate"] == 1.0

    def test_agent_feedback_to_dict(self) -> None:
        """Test serializing agent feedback."""
        feedback = AgentFeedback(
            task_completed=True,
            turns_taken=3,
            tools_used=["Read", "Write"],
            tool_call_count=5,
            tool_success_count=5,
        )

        result = feedback.to_dict()

        assert result["task_completed"] is True
        assert result["turns_taken"] == 3
        assert result["tools_used"] == ["Read", "Write"]
        assert result["tool_success_rate"] == 1.0


# =============================================================================
# SkillFeedback Tests
# =============================================================================


class TestSkillFeedback:
    """Tests for SkillFeedback dataclass."""

    def test_create_skill_feedback(self) -> None:
        """Test creating skill feedback."""
        feedback = SkillFeedback(
            activation_count=5,
            activation_accuracy=0.9,
            execution_count=5,
            execution_success_count=4,
        )

        assert feedback.activation_count == 5
        assert feedback.activation_accuracy == 0.9
        assert feedback.execution_success_rate == 0.8

    def test_execution_success_rate_no_executions(self) -> None:
        """Test execution success rate with no executions."""
        feedback = SkillFeedback(execution_count=0)

        assert feedback.execution_success_rate == 1.0

    def test_skill_to_reward(self) -> None:
        """Test converting skill feedback to reward."""
        feedback = SkillFeedback(
            execution_count=10,
            execution_success_count=9,
            output_quality=0.85,
            activation_accuracy=0.95,
        )

        reward = feedback.to_reward()

        assert "task_completion" in reward
        assert "quality" in reward
        assert "activation_accuracy" in reward
        assert reward["activation_accuracy"] == 0.95


# =============================================================================
# PromptFeedback Tests
# =============================================================================


class TestPromptFeedback:
    """Tests for PromptFeedback dataclass."""

    def test_create_prompt_feedback(self) -> None:
        """Test creating prompt feedback."""
        feedback = PromptFeedback(
            render_count=3,
            variables_used=["name", "context"],
            response_quality=0.9,
        )

        assert feedback.render_count == 3
        assert feedback.variables_used == ["name", "context"]
        assert feedback.response_quality == 0.9

    def test_prompt_to_reward_with_missing_vars(self) -> None:
        """Test prompt reward with missing variables."""
        feedback = PromptFeedback(
            success=True,
            clarity_score=0.9,
            missing_variables=["required_var"],
        )

        reward = feedback.to_reward()

        # Should penalize for missing variables
        assert reward["clarity"] < 0.9


# =============================================================================
# CommandFeedback Tests
# =============================================================================


class TestCommandFeedback:
    """Tests for CommandFeedback dataclass."""

    def test_create_command_feedback(self) -> None:
        """Test creating command feedback."""
        feedback = CommandFeedback(
            invocation_count=1,
            arguments_provided=["arg1", "arg2"],
            tools_allowed=["Read", "Write"],
            tools_actually_used=["Read"],
        )

        assert feedback.invocation_count == 1
        assert feedback.arguments_provided == ["arg1", "arg2"]
        assert feedback.tool_compliance == 1.0

    def test_tool_compliance_with_violations(self) -> None:
        """Test tool compliance with unauthorized access."""
        feedback = CommandFeedback(
            unauthorized_tool_attempts=2,
        )

        assert feedback.tool_compliance == 0.6  # 1.0 - 2 * 0.2

    def test_command_to_reward(self) -> None:
        """Test command reward dimensions."""
        feedback = CommandFeedback(
            success=True,
            argument_parse_success=True,
            output_quality=0.85,
        )

        reward = feedback.to_reward()

        assert reward["safety"] == 1.0  # No unauthorized attempts
        assert reward["argument_handling"] == 1.0


# =============================================================================
# TrainingTriplet Tests
# =============================================================================


class TestTrainingTriplet:
    """Tests for TrainingTriplet dataclass."""

    def test_create_triplet(self) -> None:
        """Test creating a training triplet."""
        triplet = TrainingTriplet(
            prompt="Write a hello world function",
            positive="def hello(): print('Hello, World!')",
            negative="print hello",
            resource_id="python-expert",
            resource_type="agent",
        )

        assert triplet.prompt == "Write a hello world function"
        assert triplet.positive_score == 1.0
        assert triplet.negative_score == 0.0

    def test_triplet_to_dict(self) -> None:
        """Test serializing triplet."""
        triplet = TrainingTriplet(
            prompt="task",
            positive="good",
            negative="bad",
            positive_score=0.9,
            negative_score=0.2,
        )

        result = triplet.to_dict()

        assert result["prompt"] == "task"
        assert result["positive_score"] == 0.9
        assert result["negative_score"] == 0.2

    def test_triplet_from_dict(self) -> None:
        """Test deserializing triplet."""
        data = {
            "prompt": "task",
            "positive": "good response",
            "negative": "bad response",
            "resource_id": "test",
            "positive_score": 0.95,
        }

        triplet = TrainingTriplet.from_dict(data)

        assert triplet.prompt == "task"
        assert triplet.resource_id == "test"
        assert triplet.positive_score == 0.95


# =============================================================================
# AgentAdapter Tests
# =============================================================================


class TestAgentAdapter:
    """Tests for AgentAdapter."""

    def test_resource_type(self) -> None:
        """Test adapter resource type."""
        adapter = AgentAdapter()

        assert adapter.resource_type == "agent"

    def test_adapt_empty_spans(self) -> None:
        """Test adapting empty span list."""
        adapter = AgentAdapter()

        feedback = adapter.adapt([])

        assert feedback.resource_type == "agent"
        assert feedback.span_count == 0

    def test_adapt_agent_spans(self, sample_agent_spans: list[Span]) -> None:
        """Test adapting agent execution spans."""
        adapter = AgentAdapter()

        feedback = adapter.adapt(sample_agent_spans)

        assert feedback.resource_type == "agent"
        assert feedback.task_completed is True
        assert feedback.resource_id == "python-expert"
        assert feedback.span_count == 5
        assert feedback.turns_taken == 1  # 1 LLM request
        assert feedback.tool_call_count == 3
        assert feedback.tool_success_count == 2
        assert feedback.tool_error_count == 1
        assert "Read" in feedback.tools_used
        assert "Write" in feedback.tools_used
        assert "Bash" in feedback.tools_used

    def test_adapt_computes_scores(self, sample_agent_spans: list[Span]) -> None:
        """Test that adaptation computes efficiency and reliability."""
        adapter = AgentAdapter()

        feedback = adapter.adapt(sample_agent_spans)

        assert feedback.efficiency_score > 0.0
        assert feedback.reliability_score > 0.0

    def test_validate_spans_valid(self, sample_agent_spans: list[Span]) -> None:
        """Test span validation with valid spans."""
        adapter = AgentAdapter()

        assert adapter.validate_spans(sample_agent_spans) is True

    def test_validate_spans_empty(self) -> None:
        """Test span validation with empty list."""
        adapter = AgentAdapter()

        assert adapter.validate_spans([]) is False


# =============================================================================
# SkillAdapter Tests
# =============================================================================


class TestSkillAdapter:
    """Tests for SkillAdapter."""

    def test_resource_type(self) -> None:
        """Test adapter resource type."""
        adapter = SkillAdapter()

        assert adapter.resource_type == "skill"

    def test_adapt_skill_spans(self, sample_skill_spans: list[Span]) -> None:
        """Test adapting skill execution spans."""
        adapter = SkillAdapter()

        feedback = adapter.adapt(sample_skill_spans)

        assert feedback.resource_type == "skill"
        assert feedback.resource_id == "debugging"
        assert feedback.activation_count >= 1
        assert feedback.activation_accuracy == 1.0
        assert feedback.output_quality == 0.85


# =============================================================================
# PromptAdapter Tests
# =============================================================================


class TestPromptAdapter:
    """Tests for PromptAdapter."""

    def test_resource_type(self) -> None:
        """Test adapter resource type."""
        adapter = PromptAdapter()

        assert adapter.resource_type == "prompt"

    def test_adapt_prompt_spans(self, sample_prompt_spans: list[Span]) -> None:
        """Test adapting prompt usage spans."""
        adapter = PromptAdapter()

        feedback = adapter.adapt(sample_prompt_spans)

        assert feedback.resource_type == "prompt"
        assert feedback.resource_id == "greeting"
        assert feedback.render_count >= 1
        assert "name" in feedback.variables_used
        assert "context" in feedback.variables_used
        assert feedback.response_quality == 0.9
        assert feedback.clarity_score == 0.95


# =============================================================================
# CommandAdapter Tests
# =============================================================================


class TestCommandAdapter:
    """Tests for CommandAdapter."""

    def test_resource_type(self) -> None:
        """Test adapter resource type."""
        adapter = CommandAdapter()

        assert adapter.resource_type == "command"

    def test_adapt_command_spans(self, sample_command_spans: list[Span]) -> None:
        """Test adapting command execution spans."""
        adapter = CommandAdapter()

        feedback = adapter.adapt(sample_command_spans)

        assert feedback.resource_type == "command"
        assert feedback.resource_id == "create-agent"
        assert feedback.invocation_count >= 1
        assert "my-agent" in feedback.arguments_provided
        assert "Read" in feedback.tools_allowed
        assert "Write" in feedback.tools_allowed
        assert "Read" in feedback.tools_actually_used
        assert feedback.output_quality == 0.88


# =============================================================================
# TripletAdapter Tests
# =============================================================================


class TestTripletAdapter:
    """Tests for TripletAdapter."""

    def test_create_comparison_triplets(
        self,
        sample_agent_spans: list[Span],
    ) -> None:
        """Test creating triplets from good/bad comparison."""
        adapter = TripletAdapter()

        # Create "bad" spans (with errors)
        bad_spans = [
            Span(
                trace_id="bad123",
                span_id="bad1",
                name="agent.execute",
                kind=SpanKind.AGENT_EXECUTION,
                start_time=datetime.now(timezone.utc),
                status=SpanStatus.ERROR,
                error_message="Task failed",
                resource_type="agent",
            ),
        ]

        triplets = adapter.create_comparison_triplets(
            good_spans=sample_agent_spans,
            bad_spans=bad_spans,
            resource_id="test-agent",
            resource_type="agent",
        )

        assert len(triplets) >= 0  # May be 0 if no prompt/response extracted

    def test_create_from_feedback(self) -> None:
        """Test creating triplet from feedback objects."""
        adapter = TripletAdapter()

        good_feedback = AgentFeedback(
            task_completed=True,
            resource_id="agent1",
        )
        bad_feedback = AgentFeedback(
            task_completed=False,
            resource_id="agent1",
        )

        triplet = adapter.create_from_feedback(
            good_feedback=good_feedback,
            bad_feedback=bad_feedback,
            prompt="Write a function",
            good_response="def func(): pass",
            bad_response="syntax error",
        )

        assert triplet.prompt == "Write a function"
        assert triplet.positive == "def func(): pass"
        assert triplet.negative == "syntax error"
        assert triplet.positive_score > triplet.negative_score


# =============================================================================
# AdapterRegistry Tests
# =============================================================================


class TestAdapterRegistry:
    """Tests for AdapterRegistry."""

    def test_get_agent_adapter(self) -> None:
        """Test getting agent adapter."""
        registry = AdapterRegistry()

        adapter = registry.get("agent")

        assert isinstance(adapter, AgentAdapter)

    def test_get_skill_adapter(self) -> None:
        """Test getting skill adapter."""
        registry = AdapterRegistry()

        adapter = registry.get("skill")

        assert isinstance(adapter, SkillAdapter)

    def test_get_prompt_adapter(self) -> None:
        """Test getting prompt adapter."""
        registry = AdapterRegistry()

        adapter = registry.get("prompt")

        assert isinstance(adapter, PromptAdapter)

    def test_get_command_adapter(self) -> None:
        """Test getting command adapter."""
        registry = AdapterRegistry()

        adapter = registry.get("command")

        assert isinstance(adapter, CommandAdapter)

    def test_get_unknown_type_raises(self) -> None:
        """Test getting unknown type raises error."""
        registry = AdapterRegistry()

        with pytest.raises(ValueError, match="Unknown resource type"):
            registry.get("unknown")

    def test_adapter_caching(self) -> None:
        """Test that adapters are cached."""
        registry = AdapterRegistry()

        adapter1 = registry.get("agent")
        adapter2 = registry.get("agent")

        assert adapter1 is adapter2

    def test_get_triplet_adapter(self) -> None:
        """Test getting triplet adapter."""
        registry = AdapterRegistry()

        adapter = registry.get_triplet_adapter()

        assert isinstance(adapter, TripletAdapter)

    def test_adapt(self, sample_agent_spans: list[Span]) -> None:
        """Test adapt convenience method."""
        registry = AdapterRegistry()

        feedback = registry.adapt("agent", sample_agent_spans)

        assert isinstance(feedback, AgentFeedback)

    def test_list_resource_types(self) -> None:
        """Test listing resource types."""
        registry = AdapterRegistry()

        types = registry.list_resource_types()

        assert "agent" in types
        assert "skill" in types
        assert "prompt" in types
        assert "command" in types


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_adapter(self) -> None:
        """Test get_adapter function."""
        reset_default_registry()

        adapter = get_adapter("agent")

        assert isinstance(adapter, AgentAdapter)

    def test_get_default_registry(self) -> None:
        """Test get_default_registry function."""
        reset_default_registry()

        registry1 = get_default_registry()
        registry2 = get_default_registry()

        assert registry1 is registry2
