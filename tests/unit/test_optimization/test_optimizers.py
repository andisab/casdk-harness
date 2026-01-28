"""Unit tests for the optimization optimizers module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.optimization.optimizers import (
    MIPRO_AVAILABLE,
    PROGRAMMATIC_ENABLED,
    TEXTGRAD_AVAILABLE,
    BaseOptimizer,
    IterationResult,
    OptimizationConfig,
    OptimizationResult,
    OptimizerProtocol,
    OptimizerType,
    PromptCandidate,
)
from harness.optimization.optimizers.metrics import (
    MetricRegistry,
    aggregate_metrics,
    create_dspy_metric,
    create_suite_metric,
    execution_time_metric,
    get_metric,
    get_suite_metric,
    pass_fail_metric,
    register_metric,
    reward_composite_metric,
    suite_average_score,
    suite_composite_metric,
    suite_pass_rate,
    suite_weighted_score,
    validation_score_metric,
)
from harness.optimization.testcases import (
    SuiteResult,
    TestCase,
    TestResult,
    TestSuite,
    ValidationConfig,
    ValidationType,
)


class TestOptimizerType:
    """Tests for OptimizerType enum."""

    def test_dspy_type(self) -> None:
        """Test DSPy optimizer type."""
        assert OptimizerType.DSPY == "dspy"
        assert OptimizerType.DSPY.value == "dspy"

    def test_textgrad_type(self) -> None:
        """Test TextGrad optimizer type."""
        assert OptimizerType.TEXTGRAD == "textgrad"
        assert OptimizerType.TEXTGRAD.value == "textgrad"


class TestOptimizationConfig:
    """Tests for OptimizationConfig."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = OptimizationConfig()
        assert config.max_iterations == 10
        assert config.early_stopping_threshold == 0.01
        assert config.learning_rate == 0.1
        assert config.num_candidates == 5
        assert config.temperature == 0.7
        assert config.seed is None
        assert config.verbose is True
        assert config.metadata == {}

    def test_custom_values(self) -> None:
        """Test custom config values."""
        config = OptimizationConfig(
            max_iterations=20,
            early_stopping_threshold=0.05,
            num_candidates=10,
            temperature=0.5,
            seed=42,
            verbose=False,
            metadata={"key": "value"},
        )
        assert config.max_iterations == 20
        assert config.early_stopping_threshold == 0.05
        assert config.num_candidates == 10
        assert config.temperature == 0.5
        assert config.seed == 42
        assert config.verbose is False
        assert config.metadata == {"key": "value"}


class TestPromptCandidate:
    """Tests for PromptCandidate."""

    def test_creation(self) -> None:
        """Test candidate creation."""
        candidate = PromptCandidate(
            prompt="You are a helpful assistant.",
            score=0.85,
            iteration=2,
        )
        assert candidate.prompt == "You are a helpful assistant."
        assert candidate.score == 0.85
        assert candidate.iteration == 2
        assert candidate.metadata == {}

    def test_with_metadata(self) -> None:
        """Test candidate with metadata."""
        candidate = PromptCandidate(
            prompt="Test prompt",
            score=0.9,
            iteration=1,
            metadata={"variation_index": 3},
        )
        assert candidate.metadata == {"variation_index": 3}


class TestIterationResult:
    """Tests for IterationResult."""

    def test_creation(self) -> None:
        """Test iteration result creation."""
        candidates = [
            PromptCandidate(prompt="Prompt A", score=0.7, iteration=0),
            PromptCandidate(prompt="Prompt B", score=0.8, iteration=0),
        ]
        result = IterationResult(
            iteration=0,
            best_prompt="Prompt B",
            best_score=0.8,
            candidates=candidates,
            improvement=0.1,
            duration_seconds=5.5,
        )
        assert result.iteration == 0
        assert result.best_prompt == "Prompt B"
        assert result.best_score == 0.8
        assert len(result.candidates) == 2
        assert result.improvement == 0.1
        assert result.duration_seconds == 5.5

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        candidates = [
            PromptCandidate(prompt="Short prompt", score=0.75, iteration=1),
        ]
        result = IterationResult(
            iteration=1,
            best_prompt="Short prompt",
            best_score=0.75,
            candidates=candidates,
            improvement=0.05,
            duration_seconds=3.2,
        )
        data = result.to_dict()
        assert data["iteration"] == 1
        assert data["best_score"] == 0.75
        assert data["improvement"] == 0.05
        assert len(data["candidates"]) == 1


class TestOptimizationResult:
    """Tests for OptimizationResult."""

    @pytest.fixture
    def sample_result(self) -> OptimizationResult:
        """Create a sample optimization result."""
        return OptimizationResult(
            success=True,
            original_prompt="Original prompt",
            optimized_prompt="Improved prompt",
            original_score=0.6,
            final_score=0.85,
            improvement=0.25,
            improvement_percent=41.67,
            iterations=[
                IterationResult(
                    iteration=0,
                    best_prompt="Improved prompt",
                    best_score=0.85,
                    candidates=[],
                    improvement=0.25,
                    duration_seconds=10.0,
                )
            ],
            total_iterations=1,
            total_duration_seconds=10.0,
            config=OptimizationConfig(),
            agent_name="test-agent",
            suite_name="test-suite",
        )

    def test_creation(self, sample_result: OptimizationResult) -> None:
        """Test result creation."""
        assert sample_result.success is True
        assert sample_result.original_score == 0.6
        assert sample_result.final_score == 0.85
        assert sample_result.improvement == 0.25
        assert sample_result.improvement_percent == 41.67
        assert sample_result.agent_name == "test-agent"
        assert sample_result.suite_name == "test-suite"

    def test_to_dict(self, sample_result: OptimizationResult) -> None:
        """Test serialization to dict."""
        data = sample_result.to_dict()
        assert data["success"] is True
        assert data["original_score"] == 0.6
        assert data["final_score"] == 0.85
        assert data["improvement"] == 0.25
        assert data["agent_name"] == "test-agent"
        assert "timestamp" in data
        assert "config" in data

    def test_failed_result(self) -> None:
        """Test failed optimization result."""
        result = OptimizationResult(
            success=False,
            original_prompt="Test",
            optimized_prompt="Test",
            original_score=0.0,
            final_score=0.0,
            improvement=0.0,
            improvement_percent=0.0,
            iterations=[],
            total_iterations=0,
            total_duration_seconds=1.0,
            config=OptimizationConfig(),
            agent_name="test-agent",
            suite_name="test-suite",
            error="DSPy not installed",
        )
        assert result.success is False
        assert result.error == "DSPy not installed"


class TestMetrics:
    """Tests for metric functions."""

    @pytest.fixture
    def test_result(self) -> TestResult:
        """Create a sample test result."""
        return TestResult(
            test_case_id="test-1",
            agent_name="test-agent",
            success=True,
            score=0.85,
            output="Test output",
            trace_id="trace-123",
            execution_time_ms=1500.0,
        )

    @pytest.fixture
    def suite_result(self) -> SuiteResult:
        """Create a sample suite result."""
        return SuiteResult(
            suite_name="test-suite",
            agent_name="test-agent",
            results=[
                TestResult(
                    test_case_id="test-1",
                    agent_name="test-agent",
                    success=True,
                    score=0.9,
                    output="Output 1",
                    trace_id="trace-1",
                    execution_time_ms=1000.0,
                ),
                TestResult(
                    test_case_id="test-2",
                    agent_name="test-agent",
                    success=True,
                    score=0.8,
                    output="Output 2",
                    trace_id="trace-2",
                    execution_time_ms=2000.0,
                ),
                TestResult(
                    test_case_id="test-3",
                    agent_name="test-agent",
                    success=False,
                    score=0.3,
                    output="Output 3",
                    trace_id="trace-3",
                    execution_time_ms=3000.0,
                ),
            ],
        )

    def test_validation_score_metric(self, test_result: TestResult) -> None:
        """Test validation score extraction."""
        score = validation_score_metric(test_result)
        assert score == 0.85

    def test_pass_fail_metric(self, test_result: TestResult) -> None:
        """Test binary pass/fail metric."""
        assert pass_fail_metric(test_result) == 1.0

        failed_result = TestResult(
            test_case_id="fail",
            agent_name="test",
            success=False,
            score=0.3,
            output="",
            trace_id="",
            execution_time_ms=100.0,
        )
        assert pass_fail_metric(failed_result) == 0.0

    def test_execution_time_metric_under_target(self, test_result: TestResult) -> None:
        """Test execution time metric when under target."""
        score = execution_time_metric(test_result, target_ms=5000.0)
        assert score == 1.0

    def test_execution_time_metric_over_target(self) -> None:
        """Test execution time metric penalty for slow execution."""
        slow_result = TestResult(
            test_case_id="slow",
            agent_name="test",
            success=True,
            score=1.0,
            output="",
            trace_id="",
            execution_time_ms=10000.0,  # 10 seconds
        )
        score = execution_time_metric(slow_result, target_ms=5000.0)
        assert score < 1.0
        assert score >= 0.5  # Should have penalty but capped

    def test_suite_average_score(self, suite_result: SuiteResult) -> None:
        """Test suite average score calculation."""
        score = suite_average_score(suite_result)
        expected = (0.9 + 0.8 + 0.3) / 3
        assert abs(score - expected) < 0.001

    def test_suite_pass_rate(self, suite_result: SuiteResult) -> None:
        """Test suite pass rate calculation."""
        rate = suite_pass_rate(suite_result)
        assert abs(rate - 2/3) < 0.001

    def test_suite_weighted_score(self, suite_result: SuiteResult) -> None:
        """Test weighted score calculation."""
        weights = {"test-1": 2.0, "test-2": 1.0, "test-3": 1.0}
        score = suite_weighted_score(suite_result, weights)
        # Weighted: (0.9 * 2 + 0.8 * 1 + 0.3 * 1) / 4 = 2.9 / 4 = 0.725
        assert abs(score - 0.725) < 0.001

    def test_suite_composite_metric(self, suite_result: SuiteResult) -> None:
        """Test composite metric calculation."""
        score = suite_composite_metric(suite_result)
        assert 0.0 <= score <= 1.0

    def test_aggregate_metrics_mean(self) -> None:
        """Test mean aggregation."""
        results = [
            TestResult("t1", "a", True, 0.8, "", "", 100.0),
            TestResult("t2", "a", True, 0.6, "", "", 100.0),
            TestResult("t3", "a", True, 0.7, "", "", 100.0),
        ]
        score = aggregate_metrics(results, validation_score_metric, "mean")
        assert abs(score - 0.7) < 0.001

    def test_aggregate_metrics_min(self) -> None:
        """Test min aggregation."""
        results = [
            TestResult("t1", "a", True, 0.8, "", "", 100.0),
            TestResult("t2", "a", True, 0.6, "", "", 100.0),
            TestResult("t3", "a", True, 0.7, "", "", 100.0),
        ]
        score = aggregate_metrics(results, validation_score_metric, "min")
        assert score == 0.6

    def test_aggregate_metrics_max(self) -> None:
        """Test max aggregation."""
        results = [
            TestResult("t1", "a", True, 0.8, "", "", 100.0),
            TestResult("t2", "a", True, 0.6, "", "", 100.0),
            TestResult("t3", "a", True, 0.7, "", "", 100.0),
        ]
        score = aggregate_metrics(results, validation_score_metric, "max")
        assert score == 0.8

    def test_aggregate_metrics_empty(self) -> None:
        """Test aggregation with empty list."""
        score = aggregate_metrics([], validation_score_metric, "mean")
        assert score == 0.0


class TestMetricRegistry:
    """Tests for MetricRegistry."""

    def test_default_metrics_registered(self) -> None:
        """Test that default metrics are registered."""
        registry = MetricRegistry()
        metrics = registry.list_metrics()
        assert "validation_score" in metrics
        assert "pass_fail" in metrics
        assert "execution_time" in metrics
        assert "reward_composite" in metrics

    def test_default_suite_metrics_registered(self) -> None:
        """Test that default suite metrics are registered."""
        registry = MetricRegistry()
        suite_metrics = registry.list_suite_metrics()
        assert "average_score" in suite_metrics
        assert "pass_rate" in suite_metrics
        assert "composite" in suite_metrics

    def test_register_and_get(self) -> None:
        """Test registering and retrieving custom metric."""
        registry = MetricRegistry()

        def custom_metric(result: TestResult) -> float:
            return result.score * 2

        registry.register("custom", custom_metric)
        retrieved = registry.get("custom")
        assert retrieved == custom_metric

    def test_get_unknown_raises(self) -> None:
        """Test that getting unknown metric raises KeyError."""
        registry = MetricRegistry()
        with pytest.raises(KeyError, match="Unknown metric"):
            registry.get("nonexistent")

    def test_global_registry(self) -> None:
        """Test global registry functions."""
        # Get default metric
        metric = get_metric("validation_score")
        assert metric == validation_score_metric

        # Get suite metric
        suite_metric = get_suite_metric("average_score")
        assert suite_metric == suite_average_score


class TestDSPyMetricCreation:
    """Tests for DSPy metric creation utilities."""

    def test_create_dspy_metric(self) -> None:
        """Test creating a DSPy-compatible metric."""
        metric = create_dspy_metric()

        # With test result
        prediction = {
            "test_result": TestResult(
                "test", "agent", True, 0.9, "", "", 100.0
            )
        }
        score = metric({}, prediction)
        assert score == 0.9

    def test_create_dspy_metric_with_output(self) -> None:
        """Test DSPy metric with output matching."""
        metric = create_dspy_metric()

        example = {"expected": "hello"}
        prediction = {"output": "Hello world!"}
        score = metric(example, prediction)
        assert score == 1.0

        prediction = {"output": "Goodbye!"}
        score = metric(example, prediction)
        assert score == 0.0

    def test_create_suite_metric(self) -> None:
        """Test creating a suite metric wrapper."""
        metric = create_suite_metric(suite_average_score)

        suite_result = SuiteResult(
            suite_name="test",
            agent_name="agent",
            results=[
                TestResult("t1", "a", True, 0.8, "", "", 100.0),
                TestResult("t2", "a", True, 0.6, "", "", 100.0),
            ],
        )
        score = metric(suite_result)
        assert abs(score - 0.7) < 0.001

    def test_create_suite_metric_empty(self) -> None:
        """Test suite metric with empty results."""
        metric = create_suite_metric(suite_average_score)

        suite_result = SuiteResult(
            suite_name="test",
            agent_name="agent",
            results=[],
        )
        score = metric(suite_result)
        assert score == 0.0


class TestMIPROOptimizerImport:
    """Tests for MIPRO optimizer availability."""

    def test_mipro_available_flag(self) -> None:
        """Test MIPRO_AVAILABLE flag is set."""
        # This test just verifies the flag exists
        assert isinstance(MIPRO_AVAILABLE, bool)

    def test_programmatic_enabled_flag(self) -> None:
        """Test PROGRAMMATIC_ENABLED flag is set."""
        assert isinstance(PROGRAMMATIC_ENABLED, bool)

    @pytest.mark.skipif(
        not PROGRAMMATIC_ENABLED or not MIPRO_AVAILABLE,
        reason="Programmatic optimization disabled or DSPy not installed"
    )
    def test_mipro_optimizer_import(self) -> None:
        """Test MIPRO optimizer can be imported when available."""
        from harness.optimization.optimizers import MIPROv2AgentOptimizer

        assert MIPROv2AgentOptimizer is not None


class TestMIPROOptimizerWithMock:
    """Tests for MIPROv2AgentOptimizer with mocked DSPy."""

    @pytest.fixture
    def test_suite(self) -> TestSuite:
        """Create a test suite for optimization."""
        return TestSuite(
            name="test-optimization-suite",
            agent_name="python-expert",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Write a function",
                    expected_behavior="Function code",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="def ",
                    ),
                ),
            ],
        )

    @pytest.fixture
    def mock_agent_resource(self) -> MagicMock:
        """Create a mock agent resource."""
        resource = MagicMock()
        resource.name = "python-expert"
        resource.system_prompt = "You are a Python expert."
        return resource

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not PROGRAMMATIC_ENABLED or not MIPRO_AVAILABLE,
        reason="Programmatic optimization disabled or DSPy not installed"
    )
    async def test_optimizer_evaluate(
        self,
        test_suite: TestSuite,
    ) -> None:
        """Test optimizer evaluate method."""
        from harness.optimization.optimizers import MIPROv2AgentOptimizer

        optimizer = MIPROv2AgentOptimizer()

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value="def my_function(): pass",
        ):
            score, result = await optimizer.evaluate(
                "Test prompt",
                test_suite,
            )

        assert score > 0.0
        assert isinstance(result, SuiteResult)

    @pytest.mark.asyncio
    async def test_optimizer_not_available(
        self,
        mock_agent_resource: MagicMock,
        test_suite: TestSuite,
    ) -> None:
        """Test optimizer returns error when MIPRO not available."""
        # Force MIPRO_AVAILABLE to False for this test
        with patch(
            "harness.optimization.optimizers.dspy_mipro_optimizer.DSPY_AVAILABLE",
            False,
        ):
            from harness.optimization.optimizers.dspy_mipro_optimizer import (
                MIPROv2AgentOptimizer,
            )

            optimizer = MIPROv2AgentOptimizer()
            result = await optimizer.optimize(mock_agent_resource, test_suite)

            assert result.success is False
            assert "DSPy not installed" in result.error


class TestOptimizerProtocol:
    """Tests for OptimizerProtocol compliance."""

    @pytest.mark.skipif(
        not PROGRAMMATIC_ENABLED or not MIPRO_AVAILABLE,
        reason="Programmatic optimization disabled or DSPy not installed"
    )
    def test_mipro_optimizer_implements_protocol(self) -> None:
        """Verify MIPROv2AgentOptimizer implements OptimizerProtocol."""
        from harness.optimization.optimizers import MIPROv2AgentOptimizer

        optimizer = MIPROv2AgentOptimizer()

        # Check required methods exist
        assert hasattr(optimizer, "optimize")
        assert hasattr(optimizer, "evaluate")
        assert callable(optimizer.optimize)
        assert callable(optimizer.evaluate)

    @pytest.mark.skipif(not TEXTGRAD_AVAILABLE, reason="TextGrad not installed")
    def test_textgrad_optimizer_implements_protocol(self) -> None:
        """Verify TextGradAgentOptimizer implements OptimizerProtocol."""
        from harness.optimization.optimizers import TextGradAgentOptimizer

        optimizer = TextGradAgentOptimizer()

        # Check required methods exist
        assert hasattr(optimizer, "optimize")
        assert hasattr(optimizer, "evaluate")
        assert callable(optimizer.optimize)
        assert callable(optimizer.evaluate)


class TestTextGradOptimizerImport:
    """Tests for TextGrad optimizer availability."""

    def test_textgrad_available_flag(self) -> None:
        """Test TEXTGRAD_AVAILABLE flag is set."""
        # This test just verifies the flag exists
        assert isinstance(TEXTGRAD_AVAILABLE, bool)

    @pytest.mark.skipif(not TEXTGRAD_AVAILABLE, reason="TextGrad not installed")
    def test_textgrad_optimizer_import(self) -> None:
        """Test TextGrad optimizer can be imported when available."""
        from harness.optimization.optimizers import TextGradAgentOptimizer

        assert TextGradAgentOptimizer is not None


class TestTextGradOptimizerWithMock:
    """Tests for TextGradAgentOptimizer with mocked TextGrad."""

    @pytest.fixture
    def test_suite(self) -> TestSuite:
        """Create a test suite for optimization."""
        return TestSuite(
            name="test-optimization-suite",
            agent_name="python-expert",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Write a function",
                    expected_behavior="Function code",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="def ",
                    ),
                ),
            ],
        )

    @pytest.fixture
    def mock_agent_resource(self) -> MagicMock:
        """Create a mock agent resource."""
        resource = MagicMock()
        resource.name = "python-expert"
        resource.system_prompt = "You are a Python expert."
        return resource

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TEXTGRAD_AVAILABLE, reason="TextGrad not installed")
    async def test_optimizer_evaluate(
        self,
        test_suite: TestSuite,
    ) -> None:
        """Test optimizer evaluate method."""
        from harness.optimization.optimizers import TextGradAgentOptimizer

        optimizer = TextGradAgentOptimizer()

        with patch(
            "harness.direct_agent.call_agent_simple",
            new_callable=AsyncMock,
            return_value="def my_function(): pass",
        ):
            score, result = await optimizer.evaluate(
                "Test prompt",
                test_suite,
            )

        assert score > 0.0
        assert isinstance(result, SuiteResult)

    @pytest.mark.asyncio
    async def test_optimizer_not_available(
        self,
        mock_agent_resource: MagicMock,
        test_suite: TestSuite,
    ) -> None:
        """Test optimizer returns error when TextGrad not available."""
        # Force TEXTGRAD_AVAILABLE to False for this test
        with patch(
            "harness.optimization.optimizers.textgrad_optimizer.TEXTGRAD_AVAILABLE",
            False,
        ):
            from harness.optimization.optimizers.textgrad_optimizer import (
                TextGradAgentOptimizer,
            )

            optimizer = TextGradAgentOptimizer()
            result = await optimizer.optimize(mock_agent_resource, test_suite)

            assert result.success is False
            assert "TextGrad not installed" in result.error

    @pytest.mark.skipif(not TEXTGRAD_AVAILABLE, reason="TextGrad not installed")
    def test_textgrad_loss_text_creation(self) -> None:
        """Test loss text generation for TextGrad backward pass."""
        from harness.optimization.optimizers.textgrad_optimizer import (
            TextGradAgentOptimizer,
        )

        optimizer = TextGradAgentOptimizer()

        # Create a sample suite result with failures
        suite_result = SuiteResult(
            suite_name="test-suite",
            agent_name="test-agent",
            results=[
                TestResult(
                    test_case_id="test-1",
                    agent_name="test-agent",
                    success=True,
                    score=0.9,
                    output="Good output",
                    trace_id="trace-1",
                    execution_time_ms=100.0,
                ),
                TestResult(
                    test_case_id="test-2",
                    agent_name="test-agent",
                    success=False,
                    score=0.3,
                    output="Bad output",
                    trace_id="trace-2",
                    execution_time_ms=100.0,
                    error="Validation failed",
                ),
            ],
        )

        test_suite = TestSuite(
            name="test-suite",
            agent_name="test-agent",
            test_cases=[
                TestCase(
                    id="test-1",
                    prompt="Write code",
                    expected_behavior="Working code",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="def",
                    ),
                ),
                TestCase(
                    id="test-2",
                    prompt="Write async code",
                    expected_behavior="Working async code",
                    validation=ValidationConfig(
                        type=ValidationType.CONTAINS,
                        criteria="async def",
                    ),
                ),
            ],
        )

        loss_text = optimizer._create_loss_text(suite_result, test_suite)

        # Verify loss text contains failure information
        assert "1 passed" in loss_text
        assert "1 failed" in loss_text
        assert "test-2" in loss_text
        assert "Improve the system prompt" in loss_text
