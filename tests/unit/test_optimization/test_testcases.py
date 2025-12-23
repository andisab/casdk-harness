"""Tests for the testcases module."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from harness.optimization.testcases import (
    CompositeValidator,
    ContainsValidator,
    ExactValidator,
    LLMJudgeValidator,
    RegexValidator,
    SuiteResult,
    TestCase,
    TestResult,
    TestSuite,
    TestSuiteLoader,
    TestSuiteLoaderError,
    ValidationConfig,
    ValidationType,
    get_validator,
)


class TestValidationConfig:
    """Tests for ValidationConfig."""

    def test_create_with_enum_type(self) -> None:
        """Test creation with ValidationType enum."""
        config = ValidationConfig(
            type=ValidationType.CONTAINS,
            criteria="def ",
        )
        assert config.type == ValidationType.CONTAINS
        assert config.criteria == "def "
        assert config.partial_credit is False

    def test_create_with_string_type(self) -> None:
        """Test creation with string type (auto-converts to enum)."""
        config = ValidationConfig(
            type="contains",
            criteria="def ",
        )
        assert config.type == ValidationType.CONTAINS

    def test_partial_credit_default_false(self) -> None:
        """Test partial_credit defaults to False."""
        config = ValidationConfig(type=ValidationType.EXACT, criteria="test")
        assert config.partial_credit is False

    def test_partial_credit_enabled(self) -> None:
        """Test partial_credit can be enabled."""
        config = ValidationConfig(
            type=ValidationType.LLM_JUDGE,
            criteria="Evaluate quality",
            partial_credit=True,
        )
        assert config.partial_credit is True


class TestTestCase:
    """Tests for TestCase."""

    def test_create_basic(self) -> None:
        """Test basic test case creation."""
        tc = TestCase(
            id="test-1",
            prompt="Write a function",
            expected_behavior="Returns a function",
            validation=ValidationConfig(type=ValidationType.CONTAINS, criteria="def"),
        )
        assert tc.id == "test-1"
        assert tc.prompt == "Write a function"
        assert tc.timeout_seconds == 300  # default
        assert tc.tags == []

    def test_create_with_dict_validation(self) -> None:
        """Test creation with validation as dict (auto-converts)."""
        tc = TestCase(
            id="test-1",
            prompt="Write a function",
            expected_behavior="Returns a function",
            validation={"type": "contains", "criteria": "def"},
        )
        assert isinstance(tc.validation, ValidationConfig)
        assert tc.validation.type == ValidationType.CONTAINS

    def test_create_with_tags(self) -> None:
        """Test creation with tags."""
        tc = TestCase(
            id="test-1",
            prompt="Write async code",
            expected_behavior="Async function",
            validation=ValidationConfig(type=ValidationType.CONTAINS, criteria="async"),
            tags=["async", "advanced"],
        )
        assert tc.tags == ["async", "advanced"]


class TestTestSuite:
    """Tests for TestSuite."""

    @pytest.fixture
    def sample_test_cases(self) -> list[TestCase]:
        """Create sample test cases."""
        return [
            TestCase(
                id="tc-1",
                prompt="Prompt 1",
                expected_behavior="Behavior 1",
                validation=ValidationConfig(type=ValidationType.CONTAINS, criteria="a"),
                tags=["basic"],
            ),
            TestCase(
                id="tc-2",
                prompt="Prompt 2",
                expected_behavior="Behavior 2",
                validation=ValidationConfig(type=ValidationType.REGEX, criteria=r"\d+"),
                tags=["advanced"],
            ),
        ]

    def test_create_suite(self, sample_test_cases: list[TestCase]) -> None:
        """Test suite creation."""
        suite = TestSuite(
            name="test-suite",
            agent_name="python-expert",
            test_cases=sample_test_cases,
        )
        assert suite.name == "test-suite"
        assert suite.agent_name == "python-expert"
        assert len(suite) == 2

    def test_iterate_suite(self, sample_test_cases: list[TestCase]) -> None:
        """Test iterating over suite."""
        suite = TestSuite(
            name="test-suite",
            agent_name="python-expert",
            test_cases=sample_test_cases,
        )
        ids = [tc.id for tc in suite]
        assert ids == ["tc-1", "tc-2"]

    def test_filter_by_tags(self, sample_test_cases: list[TestCase]) -> None:
        """Test filtering by tags."""
        suite = TestSuite(
            name="test-suite",
            agent_name="python-expert",
            test_cases=sample_test_cases,
        )
        basic = suite.filter_by_tags(["basic"])
        assert len(basic) == 1
        assert basic[0].id == "tc-1"

    def test_get_by_id(self, sample_test_cases: list[TestCase]) -> None:
        """Test getting test case by ID."""
        suite = TestSuite(
            name="test-suite",
            agent_name="python-expert",
            test_cases=sample_test_cases,
        )
        tc = suite.get_by_id("tc-2")
        assert tc is not None
        assert tc.id == "tc-2"

    def test_get_by_id_not_found(self, sample_test_cases: list[TestCase]) -> None:
        """Test getting non-existent test case."""
        suite = TestSuite(
            name="test-suite",
            agent_name="python-expert",
            test_cases=sample_test_cases,
        )
        tc = suite.get_by_id("nonexistent")
        assert tc is None


class TestTestSuiteLoader:
    """Tests for TestSuiteLoader."""

    @pytest.fixture
    def sample_suite_data(self) -> dict:
        """Create sample suite data."""
        return {
            "name": "test-suite",
            "description": "Test description",
            "agent_name": "python-expert",
            "version": "1.0",
            "test_cases": [
                {
                    "id": "tc-1",
                    "prompt": "Write a function",
                    "expected_behavior": "Returns function",
                    "validation": {"type": "contains", "criteria": "def"},
                }
            ],
        }

    def test_load_yaml(self, sample_suite_data: dict) -> None:
        """Test loading from YAML file."""
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            yaml.dump(sample_suite_data, f)
            f.flush()

            suite = TestSuiteLoader.load(f.name)
            assert suite.name == "test-suite"
            assert len(suite) == 1

    def test_load_json(self, sample_suite_data: dict) -> None:
        """Test loading from JSON file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as f:
            json.dump(sample_suite_data, f)
            f.flush()

            suite = TestSuiteLoader.load(f.name)
            assert suite.name == "test-suite"
            assert len(suite) == 1

    def test_load_file_not_found(self) -> None:
        """Test loading non-existent file."""
        with pytest.raises(FileNotFoundError):
            TestSuiteLoader.load("/nonexistent/path.yaml")

    def test_load_unsupported_format(self, sample_suite_data: dict) -> None:
        """Test loading unsupported file format."""
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False
        ) as f:
            f.write("some content")
            f.flush()

            with pytest.raises(TestSuiteLoaderError, match="Unsupported file format"):
                TestSuiteLoader.load(f.name)

    def test_load_missing_required_fields(self) -> None:
        """Test loading with missing required fields."""
        data = {"name": "test"}  # Missing agent_name and test_cases
        with pytest.raises(TestSuiteLoaderError, match="Missing required fields"):
            TestSuiteLoader.from_dict(data)

    def test_load_empty_test_cases(self) -> None:
        """Test loading with empty test_cases."""
        data = {
            "name": "test",
            "agent_name": "agent",
            "test_cases": [],
        }
        with pytest.raises(TestSuiteLoaderError, match="at least one test case"):
            TestSuiteLoader.from_dict(data)

    def test_from_dict(self, sample_suite_data: dict) -> None:
        """Test creating suite from dict."""
        suite = TestSuiteLoader.from_dict(sample_suite_data)
        assert suite.name == "test-suite"
        assert suite.agent_name == "python-expert"

    def test_save_yaml(self, sample_suite_data: dict) -> None:
        """Test saving to YAML."""
        suite = TestSuiteLoader.from_dict(sample_suite_data)
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            TestSuiteLoader.save(suite, f.name, format="yaml")

            # Reload and verify
            loaded = TestSuiteLoader.load(f.name)
            assert loaded.name == suite.name

    def test_save_json(self, sample_suite_data: dict) -> None:
        """Test saving to JSON."""
        suite = TestSuiteLoader.from_dict(sample_suite_data)
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as f:
            TestSuiteLoader.save(suite, f.name, format="json")

            # Reload and verify
            loaded = TestSuiteLoader.load(f.name)
            assert loaded.name == suite.name


class TestValidators:
    """Tests for validators."""

    @pytest.mark.asyncio
    async def test_exact_validator_match(self) -> None:
        """Test exact validator with matching output."""
        config = ValidationConfig(type=ValidationType.EXACT, criteria="hello world")
        validator = ExactValidator(config)
        score = await validator.validate("hello world")
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_exact_validator_no_match(self) -> None:
        """Test exact validator with non-matching output."""
        config = ValidationConfig(type=ValidationType.EXACT, criteria="hello world")
        validator = ExactValidator(config)
        score = await validator.validate("hello there")
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_contains_validator_match(self) -> None:
        """Test contains validator with matching output."""
        config = ValidationConfig(type=ValidationType.CONTAINS, criteria="def ")
        validator = ContainsValidator(config)
        score = await validator.validate("def sort(lst): return sorted(lst)")
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_contains_validator_no_match(self) -> None:
        """Test contains validator with non-matching output."""
        config = ValidationConfig(type=ValidationType.CONTAINS, criteria="class ")
        validator = ContainsValidator(config)
        score = await validator.validate("def sort(lst): return sorted(lst)")
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_regex_validator_match(self) -> None:
        """Test regex validator with matching output."""
        config = ValidationConfig(
            type=ValidationType.REGEX, criteria=r"def\s+\w+\s*\("
        )
        validator = RegexValidator(config)
        score = await validator.validate("def sort(lst): return sorted(lst)")
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_regex_validator_no_match(self) -> None:
        """Test regex validator with non-matching output."""
        config = ValidationConfig(type=ValidationType.REGEX, criteria=r"class\s+\w+")
        validator = RegexValidator(config)
        score = await validator.validate("def sort(lst): return sorted(lst)")
        assert score == 0.0

    def test_regex_validator_invalid_pattern(self) -> None:
        """Test regex validator with invalid pattern."""
        config = ValidationConfig(type=ValidationType.REGEX, criteria="[invalid")
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            RegexValidator(config)

    @pytest.mark.asyncio
    async def test_partial_credit_enabled(self) -> None:
        """Test partial credit scoring."""
        config = ValidationConfig(
            type=ValidationType.CONTAINS,
            criteria="specific",
            partial_credit=True,
        )
        validator = ContainsValidator(config)
        # When partial_credit is True, score is returned as-is
        score = await validator.validate("not matching")
        assert score == 0.0  # Still 0 because no match

    @pytest.mark.asyncio
    async def test_get_validator_contains(self) -> None:
        """Test get_validator for contains type."""
        config = ValidationConfig(type=ValidationType.CONTAINS, criteria="test")
        validator = get_validator(config)
        assert isinstance(validator, ContainsValidator)

    @pytest.mark.asyncio
    async def test_get_validator_exact(self) -> None:
        """Test get_validator for exact type."""
        config = ValidationConfig(type=ValidationType.EXACT, criteria="test")
        validator = get_validator(config)
        assert isinstance(validator, ExactValidator)

    @pytest.mark.asyncio
    async def test_get_validator_regex(self) -> None:
        """Test get_validator for regex type."""
        config = ValidationConfig(type=ValidationType.REGEX, criteria=r"\w+")
        validator = get_validator(config)
        assert isinstance(validator, RegexValidator)

    @pytest.mark.asyncio
    async def test_get_validator_llm_judge(self) -> None:
        """Test get_validator for llm_judge type."""
        config = ValidationConfig(type=ValidationType.LLM_JUDGE, criteria="Evaluate")
        validator = get_validator(config)
        assert isinstance(validator, LLMJudgeValidator)


class TestLLMJudgeValidator:
    """Tests for LLMJudgeValidator."""

    @pytest.mark.asyncio
    async def test_llm_judge_success(self) -> None:
        """Test LLM judge with mocked response."""
        config = ValidationConfig(
            type=ValidationType.LLM_JUDGE,
            criteria="Check if output is valid Python",
            partial_credit=True,  # Enable to get actual score
        )
        validator = LLMJudgeValidator(config)

        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="0.85")]

        with patch("anthropic.AsyncAnthropic") as mock:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock.return_value = mock_client

            score = await validator.validate("def foo(): pass")
            assert score == 0.85

    @pytest.mark.asyncio
    async def test_llm_judge_parse_error(self) -> None:
        """Test LLM judge with unparseable response."""
        config = ValidationConfig(
            type=ValidationType.LLM_JUDGE,
            criteria="Check quality",
            partial_credit=True,  # Enable to get actual score
        )
        validator = LLMJudgeValidator(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="The score is 0.7")]

        with patch("anthropic.AsyncAnthropic") as mock:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock.return_value = mock_client

            score = await validator.validate("test output")
            # Should extract 0.7 from the text
            assert score == 0.7

    @pytest.mark.asyncio
    async def test_llm_judge_error_handling(self) -> None:
        """Test LLM judge error handling."""
        config = ValidationConfig(
            type=ValidationType.LLM_JUDGE,
            criteria="Check quality",
        )
        validator = LLMJudgeValidator(config)

        with patch("anthropic.AsyncAnthropic") as mock:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )
            mock.return_value = mock_client

            score = await validator.validate("test output")
            assert score == 0.0  # Returns 0 on error


class TestCompositeValidator:
    """Tests for CompositeValidator."""

    @pytest.mark.asyncio
    async def test_composite_weighted_average(self) -> None:
        """Test composite validator with weighted average."""
        config1 = ValidationConfig(type=ValidationType.CONTAINS, criteria="def")
        config2 = ValidationConfig(type=ValidationType.CONTAINS, criteria="return")

        validator = CompositeValidator([
            (ContainsValidator(config1), 0.6),
            (ContainsValidator(config2), 0.4),
        ])

        # Both match
        score = await validator.validate("def foo(): return 1")
        assert score == pytest.approx(1.0)

        # Only first matches
        score = await validator.validate("def foo(): pass")
        assert score == pytest.approx(0.6)


class TestTestResult:
    """Tests for TestResult."""

    def test_create_result(self) -> None:
        """Test creating a test result."""
        result = TestResult(
            test_case_id="tc-1",
            agent_name="python-expert",
            success=True,
            score=0.9,
            output="def sort(lst): return sorted(lst)",
            trace_id="trace-123",
            execution_time_ms=1500.0,
        )
        assert result.test_case_id == "tc-1"
        assert result.success is True
        assert result.score == 0.9

    def test_to_dict(self) -> None:
        """Test converting result to dict."""
        result = TestResult(
            test_case_id="tc-1",
            agent_name="python-expert",
            success=True,
            score=0.9,
            output="output",
            trace_id="trace-123",
            execution_time_ms=1500.0,
        )
        d = result.to_dict()
        assert d["test_case_id"] == "tc-1"
        assert d["success"] is True
        assert d["score"] == 0.9


class TestSuiteResult:
    """Tests for SuiteResult."""

    @pytest.fixture
    def sample_results(self) -> list[TestResult]:
        """Create sample test results."""
        return [
            TestResult(
                test_case_id="tc-1",
                agent_name="python-expert",
                success=True,
                score=0.9,
                output="output 1",
                trace_id="trace-1",
                execution_time_ms=1000.0,
            ),
            TestResult(
                test_case_id="tc-2",
                agent_name="python-expert",
                success=False,
                score=0.3,
                output="output 2",
                trace_id="trace-2",
                execution_time_ms=2000.0,
            ),
        ]

    def test_total_score(self, sample_results: list[TestResult]) -> None:
        """Test total score calculation."""
        result = SuiteResult(
            suite_name="test-suite",
            agent_name="python-expert",
            results=sample_results,
        )
        assert result.total_score == pytest.approx(0.6)

    def test_pass_rate(self, sample_results: list[TestResult]) -> None:
        """Test pass rate calculation."""
        result = SuiteResult(
            suite_name="test-suite",
            agent_name="python-expert",
            results=sample_results,
        )
        assert result.pass_rate == pytest.approx(0.5)

    def test_total_time(self, sample_results: list[TestResult]) -> None:
        """Test total time calculation."""
        result = SuiteResult(
            suite_name="test-suite",
            agent_name="python-expert",
            results=sample_results,
        )
        assert result.total_time_ms == 3000.0

    def test_get_failed_results(self, sample_results: list[TestResult]) -> None:
        """Test getting failed results."""
        result = SuiteResult(
            suite_name="test-suite",
            agent_name="python-expert",
            results=sample_results,
        )
        failed = result.get_failed_results()
        assert len(failed) == 1
        assert failed[0].test_case_id == "tc-2"

    def test_empty_results(self) -> None:
        """Test empty results handling."""
        result = SuiteResult(
            suite_name="test-suite",
            agent_name="python-expert",
            results=[],
        )
        assert result.total_score == 0.0
        assert result.pass_rate == 0.0
        assert result.total_time_ms == 0.0


class TestLoadSampleSuite:
    """Test loading the sample test suite file."""

    def test_load_python_expert_tests(self) -> None:
        """Test loading the python-expert test suite."""
        suite_path = Path(__file__).parent.parent.parent / "optimization" / "python_expert_tests.yaml"
        if suite_path.exists():
            suite = TestSuiteLoader.load(suite_path)
            assert suite.name == "python-expert-optimization-suite"
            assert suite.agent_name == "python-expert"
            assert len(suite) >= 6
