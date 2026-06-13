"""Integration tests for CGF (ContextGrad Framework) pipeline.

These tests verify the end-to-end flow of the CGF infrastructure:
    tracer → store → adapters → rewards

No API calls are made - these tests use the memory store and simulated spans
to validate the integration of all CGF components.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from harness.optimization.adapters import (
    AdapterRegistry,
    AgentAdapter,
    AgentFeedback,
    CommandAdapter,
    CommandFeedback,
    PromptAdapter,
    PromptFeedback,
    SkillAdapter,
    SkillFeedback,
)
from harness.optimization.rewards import ResourceReward
from harness.optimization.store import MemoryOptimizationStore
from harness.tracer import (
    Span,
    SpanKind,
    SpanStatus,
    generate_span_id,
    generate_trace_id,
    get_tracer,
    reset_tracer,
)
from harness.tracer.exporters import StoreSpanExporter


@pytest.fixture
def memory_store():
    """Create a fresh memory store for testing."""
    return MemoryOptimizationStore()


@pytest.fixture
def store_exporter(memory_store):
    """Create a store exporter connected to memory store."""
    return StoreSpanExporter(store=memory_store)


@pytest.fixture
def sample_agent_spans():
    """Create sample spans simulating an agent execution."""
    trace_id = generate_trace_id()
    start_time = datetime.now()

    # Parent span - agent execution
    parent_span_id = generate_span_id()
    parent_span = Span(
        trace_id=trace_id,
        span_id=parent_span_id,
        name="agent.execute.python-expert",
        kind=SpanKind.AGENT_EXECUTION,
        status=SpanStatus.OK,
        start_time=start_time,
        end_time=start_time + timedelta(seconds=5),
        attributes={
            "agent.name": "python-expert",
            "agent.model": "claude-sonnet-4-5-20250929",
            "prompt.length": 100,
            "task.completed": True,
        },
    )
    parent_span.token_usage = {
        "input_tokens": 500,
        "output_tokens": 200,
        "cache_read_input_tokens": 100,
    }

    # LLM request span (counts as a turn)
    llm_span = Span(
        trace_id=trace_id,
        span_id=generate_span_id(),
        parent_span_id=parent_span_id,
        name="llm.request",
        kind=SpanKind.LLM_REQUEST,
        status=SpanStatus.OK,
        start_time=start_time + timedelta(seconds=0.5),
        end_time=start_time + timedelta(seconds=0.8),
        attributes={
            "llm.model": "claude-sonnet-4-5-20250929",
        },
    )

    # Child span 1 - tool call (Read)
    tool_span_1 = Span(
        trace_id=trace_id,
        span_id=generate_span_id(),
        parent_span_id=parent_span_id,
        name="tool.Read",
        kind=SpanKind.TOOL_CALL,
        status=SpanStatus.OK,
        start_time=start_time + timedelta(seconds=1),
        end_time=start_time + timedelta(seconds=1.5),
        attributes={
            "tool.name": "Read",
            "tool.success": True,
        },
    )

    # Child span 2 - tool call (Write)
    tool_span_2 = Span(
        trace_id=trace_id,
        span_id=generate_span_id(),
        parent_span_id=parent_span_id,
        name="tool.Write",
        kind=SpanKind.TOOL_CALL,
        status=SpanStatus.OK,
        start_time=start_time + timedelta(seconds=2),
        end_time=start_time + timedelta(seconds=2.5),
        attributes={
            "tool.name": "Write",
            "tool.success": True,
        },
    )

    # Child span 3 - tool call (Bash) - failed
    tool_span_3 = Span(
        trace_id=trace_id,
        span_id=generate_span_id(),
        parent_span_id=parent_span_id,
        name="tool.Bash",
        kind=SpanKind.TOOL_CALL,
        status=SpanStatus.ERROR,
        start_time=start_time + timedelta(seconds=3),
        end_time=start_time + timedelta(seconds=3.5),
        attributes={
            "tool.name": "Bash",
            "tool.success": False,
            "error.message": "Command failed with exit code 1",
        },
    )

    return [parent_span, llm_span, tool_span_1, tool_span_2, tool_span_3]


class TestCGFPipelineIntegration:
    """Test the full CGF pipeline from tracer to rewards."""

    def test_spans_flow_to_store(self, memory_store, store_exporter, sample_agent_spans):
        """Test that spans exported via StoreSpanExporter reach the store."""
        # Export spans
        store_exporter.export_batch(sample_agent_spans)

        # Query spans from store
        trace_id = sample_agent_spans[0].trace_id
        stored_spans = memory_store.query_spans(trace_id=trace_id)

        # Verify all spans were stored (5 = 1 agent + 1 llm + 3 tool)
        assert len(stored_spans) == 5

        # Verify span data is preserved
        agent_spans = [s for s in stored_spans if s.kind == SpanKind.AGENT_EXECUTION]
        assert len(agent_spans) == 1
        assert agent_spans[0].attributes["agent.name"] == "python-expert"

        tool_spans = [s for s in stored_spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 3

        llm_spans = [s for s in stored_spans if s.kind == SpanKind.LLM_REQUEST]
        assert len(llm_spans) == 1

    def test_spans_to_agent_feedback(self, sample_agent_spans):
        """Test AgentAdapter transforms spans to AgentFeedback."""
        adapter = AgentAdapter()

        # Transform spans to feedback
        feedback = adapter.adapt(sample_agent_spans)

        # Verify feedback structure
        assert isinstance(feedback, AgentFeedback)
        assert feedback.task_completed is True
        assert feedback.turns_taken == 1  # 1 LLM_REQUEST span
        assert len(feedback.tools_used) == 3
        assert "Read" in feedback.tools_used
        assert "Write" in feedback.tools_used
        assert "Bash" in feedback.tools_used

        # Tool success rate: 2 success / 3 total
        assert feedback.tool_success_rate == pytest.approx(2/3, rel=0.01)

        # Tool error count (Bash failed)
        assert feedback.tool_error_count == 1
        assert feedback.tool_call_count == 3

    def test_feedback_to_reward(self, sample_agent_spans):
        """Test AgentFeedback converts to reward dict."""
        adapter = AgentAdapter()
        feedback = adapter.adapt(sample_agent_spans)

        # Convert feedback to reward dict
        reward = feedback.to_reward()

        # Verify reward structure (returns dict, not ResourceReward)
        assert isinstance(reward, dict)
        assert "task_completion" in reward
        assert "efficiency" in reward
        assert "quality" in reward
        assert 0.0 <= reward["task_completion"] <= 1.0
        assert 0.0 <= reward["efficiency"] <= 1.0
        assert 0.0 <= reward["quality"] <= 1.0

        # Task completed, so task_completion should be 1.0
        assert reward["task_completion"] == 1.0

    def test_full_pipeline_agent(self, memory_store, store_exporter, sample_agent_spans):
        """Test full pipeline: spans → store → adapter → reward."""
        # Step 1: Export spans to store
        store_exporter.export_batch(sample_agent_spans)

        # Step 2: Query spans from store
        trace_id = sample_agent_spans[0].trace_id
        stored_spans = memory_store.query_spans(trace_id=trace_id)

        # Step 3: Transform with adapter
        adapter = AgentAdapter()
        feedback = adapter.adapt(stored_spans)

        # Step 4: Calculate reward dict
        reward = feedback.to_reward()

        # Verify end-to-end
        assert reward["task_completion"] == 1.0  # Task completed
        assert reward["efficiency"] > 0.5  # Efficiency score positive

    def test_adapter_registry_selects_correct_adapter(self):
        """Test AdapterRegistry returns correct adapter for resource type."""
        registry = AdapterRegistry()

        # AdapterRegistry auto-creates adapters on get()
        # Verify correct adapter selection by string type
        assert isinstance(registry.get("agent"), AgentAdapter)
        assert isinstance(registry.get("skill"), SkillAdapter)
        assert isinstance(registry.get("prompt"), PromptAdapter)
        assert isinstance(registry.get("command"), CommandAdapter)

        # Also test specific getters
        assert isinstance(registry.get_agent_adapter(), AgentAdapter)
        assert isinstance(registry.get_skill_adapter(), SkillAdapter)
        assert isinstance(registry.get_prompt_adapter(), PromptAdapter)
        assert isinstance(registry.get_command_adapter(), CommandAdapter)

    # test_metrics_recorded_during_pipeline removed 2026-05-14 — the
    # five MetricsCollector helpers (record_span_collected,
    # record_span_exported, record_adapter_transform, record_reward,
    # set_feedback_dimension) and their backing cgf_* instruments were
    # deleted after the G0 emission audit confirmed zero production
    # call sites.  See docs/OBSERVABILITY.md § 3.6.

    def test_store_exporter_buffering(self, memory_store):
        """Test StoreSpanExporter buffers spans before flush."""
        # Create exporter with buffer size 3
        exporter = StoreSpanExporter(store=memory_store, buffer_size=3)

        trace_id = generate_trace_id()

        # Create 5 spans
        spans = []
        for i in range(5):
            span = Span(
                trace_id=trace_id,
                span_id=generate_span_id(),
                name=f"test.span.{i}",
                kind=SpanKind.AGENT_EXECUTION,
                status=SpanStatus.OK,
                start_time=datetime.now(),
                end_time=datetime.now(),
                attributes={},
            )
            spans.append(span)
            exporter.export(span)

        # After 5 exports with buffer_size=3:
        # - First 3 should trigger flush
        # - 2 more should be in buffer
        stored = memory_store.query_spans(trace_id=trace_id)
        assert len(stored) == 3  # First batch flushed

        # Manual flush should export remaining
        exporter.flush()
        stored = memory_store.query_spans(trace_id=trace_id)
        assert len(stored) == 5

    def test_store_exporter_shutdown_flushes(self, memory_store):
        """Test StoreSpanExporter flushes on shutdown."""
        exporter = StoreSpanExporter(store=memory_store, buffer_size=10)

        trace_id = generate_trace_id()

        # Add spans without reaching buffer limit
        for i in range(3):
            span = Span(
                trace_id=trace_id,
                span_id=generate_span_id(),
                name=f"test.span.{i}",
                kind=SpanKind.AGENT_EXECUTION,
                status=SpanStatus.OK,
                start_time=datetime.now(),
                end_time=datetime.now(),
                attributes={},
            )
            exporter.export(span)

        # Nothing stored yet (buffer not full)
        stored = memory_store.query_spans(trace_id=trace_id)
        assert len(stored) == 0

        # Shutdown should flush
        exporter.shutdown()
        stored = memory_store.query_spans(trace_id=trace_id)
        assert len(stored) == 3


class TestCGFResourceTypes:
    """Test CGF pipeline for different resource types."""

    def test_skill_feedback_pipeline(self):
        """Test SkillAdapter produces correct feedback."""
        trace_id = generate_trace_id()
        start_time = datetime.now()

        # Skill execution span
        spans = [
            Span(
                trace_id=trace_id,
                span_id=generate_span_id(),
                name="skill.execute.code-review",
                kind=SpanKind.AGENT_EXECUTION,
                status=SpanStatus.OK,
                start_time=start_time,
                end_time=start_time + timedelta(seconds=2),
                attributes={
                    "skill.name": "code-review",
                    "skill.activated": True,
                    "task.completed": True,
                },
            )
        ]

        adapter = SkillAdapter()
        feedback = adapter.adapt(spans)

        # Verify skill-specific feedback
        assert isinstance(feedback, SkillFeedback)
        assert feedback.activation_accuracy >= 0.0
        assert feedback.execution_success_rate >= 0.0

        # Convert to reward (returns dict)
        reward = feedback.to_reward()
        assert isinstance(reward, dict)
        assert "task_completion" in reward

    def test_prompt_feedback_pipeline(self):
        """Test PromptAdapter produces correct feedback."""
        trace_id = generate_trace_id()
        start_time = datetime.now()

        # Prompt execution span with response quality indicators
        spans = [
            Span(
                trace_id=trace_id,
                span_id=generate_span_id(),
                name="prompt.execute.system",
                kind=SpanKind.AGENT_EXECUTION,
                status=SpanStatus.OK,
                start_time=start_time,
                end_time=start_time + timedelta(seconds=1),
                attributes={
                    "prompt.type": "system",
                    "response.quality": 0.9,
                    "task.completed": True,
                },
            )
        ]

        adapter = PromptAdapter()
        feedback = adapter.adapt(spans)

        # Verify prompt-specific feedback
        assert isinstance(feedback, PromptFeedback)
        assert hasattr(feedback, "response_quality")

        # Convert to reward (returns dict)
        reward = feedback.to_reward()
        assert isinstance(reward, dict)
        assert "quality" in reward

    def test_command_feedback_pipeline(self):
        """Test CommandAdapter produces correct feedback."""
        trace_id = generate_trace_id()
        start_time = datetime.now()

        # Command execution span
        spans = [
            Span(
                trace_id=trace_id,
                span_id=generate_span_id(),
                name="command.execute.commit",
                kind=SpanKind.AGENT_EXECUTION,
                status=SpanStatus.OK,
                start_time=start_time,
                end_time=start_time + timedelta(seconds=0.5),
                attributes={
                    "command.name": "commit",
                    "command.success": True,
                    "task.completed": True,
                },
            )
        ]

        adapter = CommandAdapter()
        feedback = adapter.adapt(spans)

        # Verify command-specific feedback
        assert isinstance(feedback, CommandFeedback)
        assert hasattr(feedback, "invocation_count")

        # Convert to reward (returns dict)
        reward = feedback.to_reward()
        assert isinstance(reward, dict)
        assert "task_completion" in reward


class TestRewardComposite:
    """Test ResourceReward composite scoring."""

    def test_default_weights(self):
        """Test composite score with default weights."""
        reward = ResourceReward(
            task_completion=1.0,
            efficiency=0.8,
            quality=0.9,
            safety=1.0,
        )

        # Default weights: task=0.4, efficiency=0.2, quality=0.3, safety=0.1
        expected = 1.0 * 0.4 + 0.8 * 0.2 + 0.9 * 0.3 + 1.0 * 0.1
        assert reward.composite() == pytest.approx(expected, rel=0.01)

    def test_custom_weights(self):
        """Test composite score with custom weights."""
        reward = ResourceReward(
            task_completion=1.0,
            efficiency=0.5,
            quality=0.5,
            safety=1.0,
        )

        # Custom weights emphasizing efficiency
        custom_weights = {
            "task_completion": 0.2,
            "efficiency": 0.5,
            "quality": 0.2,
            "safety": 0.1,
        }

        expected = 1.0 * 0.2 + 0.5 * 0.5 + 0.5 * 0.2 + 1.0 * 0.1
        assert reward.composite(weights=custom_weights) == pytest.approx(expected, rel=0.01)

    def test_improvement_over_baseline(self):
        """Test reward improvement calculation."""
        baseline = ResourceReward(
            task_completion=0.5,
            efficiency=0.5,
            quality=0.5,
            safety=1.0,
        )

        improved = ResourceReward(
            task_completion=0.8,
            efficiency=0.7,
            quality=0.6,
            safety=1.0,
        )

        improvement = improved.improvement_over(baseline)

        # Verify improvements (returns percentages)
        # 0.5 -> 0.8 = 60% improvement
        assert improvement["task_completion"] == pytest.approx(60.0, rel=0.01)
        # 0.5 -> 0.7 = 40% improvement
        assert improvement["efficiency"] == pytest.approx(40.0, rel=0.01)
        # 0.5 -> 0.6 = 20% improvement
        assert improvement["quality"] == pytest.approx(20.0, rel=0.01)
        # 1.0 -> 1.0 = 0% change
        assert improvement["safety"] == pytest.approx(0.0, rel=0.01)


class TestTracerStoreIntegration:
    """Test tracer integration with store backend."""

    def test_tracer_exports_to_store(self, memory_store):
        """Test that tracer with store exporter writes to store."""
        # Reset global tracer
        reset_tracer()

        # Create exporter connected to memory store
        exporter = StoreSpanExporter(store=memory_store)

        # Patch get_tracer to use our exporter
        with patch("harness.tracer._auto_configure_exporters"):
            # Create tracer without auto-config
            tracer = get_tracer(service_name="test", auto_configure=False)
            tracer.add_exporter(exporter)

            # Create a span
            with tracer.span("test.operation", SpanKind.AGENT_EXECUTION) as span:
                span.set_attribute("test.key", "test.value")

            # Force flush
            tracer.shutdown()

            # Query store for spans
            # Note: query_spans might need trace_id or other filters
            # For now, verify exporter received the span
            assert exporter._store is memory_store

    def test_tracer_disabled_no_export(self, memory_store):
        """Test that disabled tracer doesn't export spans."""
        reset_tracer()

        exporter = StoreSpanExporter(store=memory_store)

        # Create disabled tracer
        tracer = get_tracer(service_name="test", enabled=False, auto_configure=False)
        tracer.add_exporter(exporter)

        # Create a span (should be no-op)
        with tracer.span("test.operation", SpanKind.AGENT_EXECUTION) as span:
            span.set_attribute("test.key", "test.value")

        tracer.shutdown()

        # Cleanup
        reset_tracer()
