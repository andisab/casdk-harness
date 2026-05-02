"""Unit tests for the optimization runners module."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from harness.optimization.runners import (
    AgentRunner,
    BaseRunner,
    BatchRunner,
    RunContext,
    RunnerConfig,
)
from harness.optimization.testcases import (
    TestCase,
    TestResult,
    TestSuite,
    ValidationConfig,
    ValidationType,
)


class TestRunnerConfig:
    """Tests for RunnerConfig."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = RunnerConfig(agent_name="test-agent")
        assert config.agent_name == "test-agent"
        assert config.permission_mode == "acceptEdits"
        assert config.cwd is None  # None means use current directory
        assert config.verbose is False
        assert config.collect_spans is True
        assert config.timeout_seconds == 300
        assert config.max_concurrent == 1

    def test_custom_values(self) -> None:
        """Test custom config values."""
        config = RunnerConfig(
            agent_name="python-expert",
            permission_mode="bypassPermissions",
            cwd="/app",
            verbose=True,
            collect_spans=False,
            timeout_seconds=60,
            max_concurrent=4,
        )
        assert config.agent_name == "python-expert"
        assert config.permission_mode == "bypassPermissions"
        assert config.cwd == "/app"
        assert config.verbose is True
        assert config.collect_spans is False
        assert config.timeout_seconds == 60
        assert config.max_concurrent == 4


class TestRunContext:
    """Tests for RunContext."""

    def test_context_creation(self) -> None:
        """Test run context creation."""
        context = RunContext(
            trace_id="trace-123",
            test_case_id="test-1",
            start_time=1234567890.0,
        )
        assert context.trace_id == "trace-123"
        assert context.test_case_id == "test-1"
        assert context.start_time == 1234567890.0
        assert context.system_prompt is None
        assert context.metadata == {}

    def test_context_with_all_fields(self) -> None:
        """Test run context with all fields."""
        context = RunContext(
            trace_id="trace-456",
            test_case_id="test-2",
            start_time=1234567890.0,
            system_prompt="Custom prompt",
            metadata={"key": "value"},
        )
        assert context.system_prompt == "Custom prompt"
        assert context.metadata == {"key": "value"}


class TestBaseRunner:
    """Tests for BaseRunner abstract class."""

    def test_validate_agent_name_match(self) -> None:
        """Test validation passes when agent names match."""

        class ConcreteRunner(BaseRunner):
            async def run_test_case(self, test_case, system_prompt_override=None):
                pass

            async def run_suite(self, suite, system_prompt_override=None):
                pass

        config = RunnerConfig(agent_name="python-expert")
        runner = ConcreteRunner(config)

        suite = TestSuite(
            name="Test Suite",
            agent_name="python-expert",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Test prompt",
                    expected_behavior="Expected",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="test",
                    ),
                )
            ],
        )

        # Should not raise
        runner._validate_agent_name(suite)

    def test_validate_agent_name_mismatch(self) -> None:
        """Test validation fails when agent names don't match."""

        class ConcreteRunner(BaseRunner):
            async def run_test_case(self, test_case, system_prompt_override=None):
                pass

            async def run_suite(self, suite, system_prompt_override=None):
                pass

        config = RunnerConfig(agent_name="python-expert")
        runner = ConcreteRunner(config)

        suite = TestSuite(
            name="Test Suite",
            agent_name="go-expert",  # Different agent
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Test prompt",
                    expected_behavior="Expected",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="test",
                    ),
                )
            ],
        )

        with pytest.raises(ValueError, match="Runner configured for 'python-expert'"):
            runner._validate_agent_name(suite)


class TestAgentRunner:
    """Tests for AgentRunner."""

    @pytest.fixture
    def runner(self) -> AgentRunner:
        """Create a runner for testing."""
        config = RunnerConfig(
            agent_name="python-expert",
            collect_spans=False,  # Disable tracing for simpler tests
            verbose=False,
        )
        return AgentRunner(config)

    @pytest.fixture
    def test_case(self) -> TestCase:
        """Create a test case for testing."""
        return TestCase(
            id="sort-function",
            prompt="Write a Python function that sorts a list.",
            expected_behavior="Returns a working sort function",
            validation=ValidationConfig(
                type=ValidationType.CONTAINS,
                criteria="def ",
            ),
            timeout_seconds=30,
            tags=["basic"],
        )

    @pytest.fixture
    def test_suite(self, test_case: TestCase) -> TestSuite:
        """Create a test suite for testing."""
        return TestSuite(
            name="python-expert-suite",
            agent_name="python-expert",
            test_cases=[test_case],
        )

    @pytest.mark.asyncio
    async def test_run_test_case_success(
        self, runner: AgentRunner, test_case: TestCase
    ) -> None:
        """Test running a single test case successfully."""
        mock_output = "def sort_list(lst): return sorted(lst)"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            result = await runner.run_test_case(test_case)

        assert result.test_case_id == "sort-function"
        assert result.output == mock_output
        assert result.score == 1.0  # Contains "def "
        assert result.success is True
        assert result.error is None
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_run_test_case_validation_fails(
        self, runner: AgentRunner, test_case: TestCase
    ) -> None:
        """Test running a test case where validation fails."""
        mock_output = "Here's the sort function: sorted(lst)"  # Missing "def "

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            result = await runner.run_test_case(test_case)

        assert result.test_case_id == "sort-function"
        assert result.output == mock_output
        assert result.score == 0.0  # Does not contain "def "
        assert result.success is False  # score < 0.5 means failure

    @pytest.mark.asyncio
    async def test_run_test_case_timeout(self, runner: AgentRunner) -> None:
        """Test test case timeout handling."""
        test_case = TestCase(
            id="slow-test",
            prompt="Do something slow",
            expected_behavior="Complete eventually",
            validation=ValidationConfig(
                type=ValidationType.CONTAINS,
                criteria="done",
            ),
            timeout_seconds=1,  # Very short timeout
        )

        async def slow_agent(*args: Any, **kwargs: Any) -> str:
            await asyncio.sleep(5)  # Longer than timeout
            return "done"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            side_effect=slow_agent,
        ):
            result = await runner.run_test_case(test_case)

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_run_test_case_error(self, runner: AgentRunner, test_case: TestCase) -> None:
        """Test error handling during test case execution."""
        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Agent failed"),
        ):
            result = await runner.run_test_case(test_case)

        assert result.success is False
        assert result.error == "Agent failed"
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_run_test_case_with_prompt_override(
        self, runner: AgentRunner, test_case: TestCase
    ) -> None:
        """Test running with a system prompt override."""
        mock_output = "def optimized_sort(lst): return sorted(lst)"
        custom_prompt = "You are an expert optimizer."

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ) as mock_call:
            result = await runner.run_test_case(
                test_case, system_prompt_override=custom_prompt
            )

        # Verify the override was passed
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs.get("system_prompt_override") == custom_prompt

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_run_suite(
        self, runner: AgentRunner, test_suite: TestSuite
    ) -> None:
        """Test running a complete test suite."""
        mock_output = "def sort_list(lst): return sorted(lst)"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            suite_result = await runner.run_suite(test_suite)

        assert suite_result.suite_name == "python-expert-suite"
        assert len(suite_result.results) == 1
        assert suite_result.passed_count == 1
        assert suite_result.failed_count == 0
        assert suite_result.total_score == 1.0
        assert suite_result.total_time_ms > 0

    @pytest.mark.asyncio
    async def test_run_suite_agent_mismatch(
        self, runner: AgentRunner
    ) -> None:
        """Test that suite with mismatched agent raises error."""
        suite = TestSuite(
            name="wrong-suite",
            agent_name="go-expert",  # Different from runner's config
            test_cases=[],
        )

        with pytest.raises(ValueError, match="Runner configured for"):
            await runner.run_suite(suite)


class TestBatchRunner:
    """Tests for BatchRunner."""

    @pytest.fixture
    def runner(self) -> BatchRunner:
        """Create a batch runner for testing."""
        config = RunnerConfig(
            agent_name="python-expert",
            collect_spans=False,
            verbose=False,
            max_concurrent=2,
        )
        return BatchRunner(config)

    @pytest.fixture
    def test_suite(self) -> TestSuite:
        """Create a test suite with multiple test cases."""
        return TestSuite(
            name="python-expert-suite",
            agent_name="python-expert",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Write a sort function",
                    expected_behavior="Sort function",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="def ",
                    ),
                    tags=["basic"],
                ),
                TestCase(
                    id="test-2",
                    prompt="Write a search function",
                    expected_behavior="Search function",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="def ",
                    ),
                    tags=["basic"],
                ),
                TestCase(
                    id="test-3",
                    prompt="Write an async function",
                    expected_behavior="Async function",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="async def",
                    ),
                    tags=["async"],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_run_suite_concurrent(
        self, runner: BatchRunner, test_suite: TestSuite
    ) -> None:
        """Test concurrent test suite execution."""
        mock_output = "def function(): pass"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            suite_result = await runner.run_suite(test_suite)

        assert suite_result.suite_name == "python-expert-suite"
        assert len(suite_result.results) == 3
        # test-1 and test-2 should pass (contain "def "), test-3 should fail (needs "async def")
        assert suite_result.passed_count == 2
        assert suite_result.failed_count == 1

    @pytest.mark.asyncio
    async def test_run_filtered_by_tags(
        self, runner: BatchRunner, test_suite: TestSuite
    ) -> None:
        """Test filtering test cases by tags."""
        mock_output = "async def function(): pass"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            suite_result = await runner.run_filtered(
                test_suite, tags=["async"]
            )

        assert len(suite_result.results) == 1
        assert suite_result.results[0].test_case_id == "test-3"

    @pytest.mark.asyncio
    async def test_run_filtered_by_ids(
        self, runner: BatchRunner, test_suite: TestSuite
    ) -> None:
        """Test filtering test cases by IDs."""
        mock_output = "def function(): pass"

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            suite_result = await runner.run_filtered(
                test_suite, ids=["test-1", "test-2"]
            )

        assert len(suite_result.results) == 2
        result_ids = {r.test_case_id for r in suite_result.results}
        assert result_ids == {"test-1", "test-2"}

    @pytest.mark.asyncio
    async def test_run_filtered_no_match(
        self, runner: BatchRunner, test_suite: TestSuite
    ) -> None:
        """Test filtering with no matching test cases."""
        suite_result = await runner.run_filtered(
            test_suite, tags=["nonexistent"]
        )

        assert len(suite_result.results) == 0
        assert suite_result.total_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_progress_callback(
        self, runner: BatchRunner, test_suite: TestSuite
    ) -> None:
        """Test progress callback is called."""
        mock_output = "def function(): pass"
        progress_calls: list[tuple[int, int, TestResult]] = []

        def on_progress(completed: int, total: int, result: TestResult) -> None:
            progress_calls.append((completed, total, result))

        runner._on_progress = on_progress

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value=mock_output,
        ):
            await runner.run_suite(test_suite)

        assert len(progress_calls) == 3
        # Should have called with increasing completed count
        completed_counts = [c[0] for c in progress_calls]
        assert sorted(completed_counts) == [1, 2, 3]


class TestRunnerProtocol:
    """Tests for RunnerProtocol compliance."""

    def test_agent_runner_implements_protocol(self) -> None:
        """Verify AgentRunner implements RunnerProtocol."""
        config = RunnerConfig(agent_name="test")
        runner = AgentRunner(config)

        # Check that required methods exist
        assert hasattr(runner, "run_test_case")
        assert hasattr(runner, "run_suite")
        assert callable(runner.run_test_case)
        assert callable(runner.run_suite)

    def test_batch_runner_implements_protocol(self) -> None:
        """Verify BatchRunner implements RunnerProtocol."""
        config = RunnerConfig(agent_name="test")
        runner = BatchRunner(config)

        # Check that required methods exist
        assert hasattr(runner, "run_test_case")
        assert hasattr(runner, "run_suite")
        assert callable(runner.run_test_case)
        assert callable(runner.run_suite)
