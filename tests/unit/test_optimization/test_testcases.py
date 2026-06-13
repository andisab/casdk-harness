"""Tests for the testcases module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from harness.optimization.testcases import (
    CodeExtractor,
    CodeLLMValidator,
    CodeSyntaxValidator,
    CodeValidator,
    CompositeValidator,
    ContainsValidator,
    ExactValidator,
    ExtractedCode,
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
    is_valid_python_syntax,
)
from harness.optimization.testcases import validators as _validators_module


@pytest.fixture(autouse=True)
def reset_shared_anthropic_client() -> None:
    """Reset the module-level shared AsyncAnthropic client between tests.

    `validators.get_shared_anthropic_client()` caches a singleton client. When
    a test patches `anthropic.AsyncAnthropic`, the resulting MagicMock gets
    cached, and subsequent tests' patches don't take effect — they receive
    the prior test's mock instead. Resetting here ensures each test starts
    with a clean slate so its patch installs properly.
    """
    _validators_module._shared_client = None


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

    def test_load_python_expert_tests_code_validation(self) -> None:
        """Test that code validation types are loaded correctly."""
        suite_path = Path(__file__).parent.parent.parent / "optimization" / "python_expert_tests.yaml"
        if suite_path.exists():
            suite = TestSuiteLoader.load(suite_path)
            # Check that code validation type is used
            sort_func = suite.get_by_id("sort-function")
            assert sort_func is not None
            assert sort_func.validation.type == ValidationType.CODE
            assert sort_func.validation.require_syntax_valid is True
            assert sort_func.validation.min_code_lines == 3
            assert sort_func.validation.language == "python"


# =============================================================================
# Code Extraction Tests
# =============================================================================


class TestExtractedCode:
    """Tests for ExtractedCode dataclass."""

    def test_is_empty_true(self) -> None:
        """Test is_empty returns True for empty code."""
        extracted = ExtractedCode(code="", language=None, source="raw", line_count=0)
        assert extracted.is_empty is True

    def test_is_empty_whitespace(self) -> None:
        """Test is_empty returns True for whitespace-only code."""
        extracted = ExtractedCode(code="   \n\t  ", language=None, source="raw", line_count=1)
        assert extracted.is_empty is True

    def test_is_empty_false(self) -> None:
        """Test is_empty returns False for non-empty code."""
        extracted = ExtractedCode(
            code="def foo(): pass",
            language="python",
            source="markdown_block",
            line_count=1,
        )
        assert extracted.is_empty is False


class TestCodeExtractor:
    """Tests for CodeExtractor."""

    @pytest.fixture
    def extractor(self) -> CodeExtractor:
        """Create a CodeExtractor instance."""
        return CodeExtractor()

    def test_extract_markdown_python_block(self, extractor: CodeExtractor) -> None:
        """Test extracting Python code from markdown block."""
        output = '''Here's a solution:
```python
def sort(lst):
    return sorted(lst)
```
'''
        result = extractor.extract(output)
        assert result.source == "markdown_block"
        assert result.language == "python"
        assert "def sort(lst):" in result.code
        assert result.line_count == 2

    def test_extract_markdown_no_language(self, extractor: CodeExtractor) -> None:
        """Test extracting code from markdown block without language."""
        output = '''```
def foo():
    pass
```'''
        result = extractor.extract(output)
        assert result.source == "markdown_block"
        assert result.language is None
        assert "def foo():" in result.code

    def test_extract_prefers_matching_language(self, extractor: CodeExtractor) -> None:
        """Test that extractor prefers blocks with matching language."""
        output = '''```javascript
console.log("hello");
```

```python
def hello():
    print("hello")
```'''
        result = extractor.extract(output, preferred_language="python")
        assert result.language == "python"
        assert "def hello():" in result.code

    def test_extract_indented_code(self, extractor: CodeExtractor) -> None:
        """Test extracting indented code when no markdown blocks."""
        output = '''Here's the code:

    def sort(lst):
        return sorted(lst)

That's all!'''
        result = extractor.extract(output)
        assert result.source == "indented"
        assert "def sort(lst):" in result.code

    def test_extract_raw_fallback(self, extractor: CodeExtractor) -> None:
        """Test raw fallback when no patterns match."""
        output = "def foo(): pass"
        result = extractor.extract(output)
        assert result.source == "raw"
        assert result.code == "def foo(): pass"

    def test_extract_empty_output(self, extractor: CodeExtractor) -> None:
        """Test extraction from empty output."""
        result = extractor.extract("")
        assert result.is_empty

    def test_extract_multiline_code_block(self, extractor: CodeExtractor) -> None:
        """Test extracting multiline code from markdown."""
        output = '''```python
def complex_function(x, y, z):
    """Docstring here."""
    if x > 0:
        return y + z
    return y - z
```'''
        result = extractor.extract(output)
        assert result.line_count == 5
        assert "def complex_function" in result.code
        assert "Docstring here" in result.code

    def test_extract_all_multiple_blocks(self, extractor: CodeExtractor) -> None:
        """Test extract_all with multiple code blocks."""
        output = '''```python
def first():
    pass
```

```python
def second():
    pass
```

```javascript
function third() {}
```'''
        results = extractor.extract_all(output, preferred_language="python")
        assert len(results) == 3
        # Python blocks should come first (sorted by preferred language)
        assert results[0].language == "python"
        assert results[1].language == "python"
        assert results[2].language == "javascript"


class TestIsValidPythonSyntax:
    """Tests for is_valid_python_syntax function."""

    def test_valid_function(self) -> None:
        """Test valid Python function."""
        code = """def sort(lst):
    return sorted(lst)
"""
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is True
        assert error is None

    def test_valid_class(self) -> None:
        """Test valid Python class."""
        code = """class User:
    def __init__(self, name):
        self.name = name
"""
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is True

    def test_invalid_syntax_missing_colon(self) -> None:
        """Test invalid syntax - missing colon."""
        code = "def foo()"  # Missing colon
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_syntax_bad_indent(self) -> None:
        """Test invalid syntax - bad indentation."""
        code = """def foo():
pass"""  # Missing indentation
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is False
        assert "SyntaxError" in error

    def test_valid_async_function(self) -> None:
        """Test valid async function."""
        code = """async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        return await session.get(url)
"""
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is True

    def test_valid_complex_code(self) -> None:
        """Test valid complex code with decorators and type hints."""
        code = '''from typing import List

@dataclass
class User:
    name: str
    age: int

def get_adults(users: List[User]) -> List[User]:
    return [u for u in users if u.age >= 18]
'''
        is_valid, error = is_valid_python_syntax(code)
        assert is_valid is True


# =============================================================================
# Code Validator Tests
# =============================================================================


class TestCodeSyntaxValidator:
    """Tests for CodeSyntaxValidator."""

    @pytest.mark.asyncio
    async def test_valid_python_in_markdown(self) -> None:
        """Test valid Python in markdown block."""
        config = ValidationConfig(
            type=ValidationType.CODE_SYNTAX,
            criteria="",
            language="python",
        )
        validator = CodeSyntaxValidator(config)
        output = '''```python
def sort(lst):
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_python_in_markdown(self) -> None:
        """Test invalid Python syntax in markdown block."""
        config = ValidationConfig(
            type=ValidationType.CODE_SYNTAX,
            criteria="",
            language="python",
        )
        validator = CodeSyntaxValidator(config)
        output = '''```python
def sort(lst)
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_empty_code_block(self) -> None:
        """Test empty code block returns 0."""
        config = ValidationConfig(type=ValidationType.CODE_SYNTAX, criteria="")
        validator = CodeSyntaxValidator(config)
        output = '''```python
```'''
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_min_code_lines_pass(self) -> None:
        """Test min_code_lines validation passes."""
        config = ValidationConfig(
            type=ValidationType.CODE_SYNTAX,
            criteria="",
            min_code_lines=3,
        )
        validator = CodeSyntaxValidator(config)
        output = '''```python
def sort(lst):
    """Sort a list."""
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_min_code_lines_fail(self) -> None:
        """Test min_code_lines validation fails."""
        config = ValidationConfig(
            type=ValidationType.CODE_SYNTAX,
            criteria="",
            min_code_lines=5,
        )
        validator = CodeSyntaxValidator(config)
        output = '''```python
def sort(lst):
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0


class TestCodeValidator:
    """Tests for CodeValidator."""

    @pytest.mark.asyncio
    async def test_valid_code_with_criteria(self) -> None:
        """Test valid code that contains criteria."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="def ",
            require_syntax_valid=True,
        )
        validator = CodeValidator(config)
        output = '''```python
def sort(lst):
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_valid_code_missing_criteria(self) -> None:
        """Test valid code that does not contain criteria."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="class ",  # Looking for class, not def
            require_syntax_valid=True,
        )
        validator = CodeValidator(config)
        output = '''```python
def sort(lst):
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_invalid_syntax_fails(self) -> None:
        """Test that invalid syntax fails even with correct criteria."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="def ",
            require_syntax_valid=True,
        )
        validator = CodeValidator(config)
        output = '''```python
def sort(lst)  # Missing colon
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_syntax_check_disabled(self) -> None:
        """Test that syntax check can be disabled."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="def ",
            require_syntax_valid=False,  # Disable syntax check
        )
        validator = CodeValidator(config)
        output = '''```python
def sort(lst)  # Missing colon - invalid syntax
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 1.0  # Passes because syntax check is disabled

    @pytest.mark.asyncio
    async def test_criteria_in_explanation_not_code(self) -> None:
        """Test criteria found in explanation but not in code fails."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="async def",
            require_syntax_valid=True,
        )
        validator = CodeValidator(config)
        # "async def" is in the explanation, not the code
        output = '''Here's an async def function example:
```python
def sort(lst):
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_min_lines_and_criteria(self) -> None:
        """Test combined min_code_lines and criteria validation."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="return",
            require_syntax_valid=True,
            min_code_lines=5,
        )
        validator = CodeValidator(config)
        output = '''```python
def complex_sort(lst):
    """Sort with logging."""
    print("Sorting...")
    result = sorted(lst)
    return result
```'''
        score = await validator.validate(output)
        assert score == 1.0


class TestCodeLLMValidator:
    """Tests for CodeLLMValidator."""

    @pytest.mark.asyncio
    async def test_llm_judge_success(self) -> None:
        """Test LLM judge with mocked response."""
        config = ValidationConfig(
            type=ValidationType.CODE_LLM,
            criteria="Evaluate if this is a valid sorting function",
            partial_credit=True,
        )
        validator = CodeLLMValidator(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="0.95")]

        with patch("anthropic.AsyncAnthropic") as mock:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock.return_value = mock_client

            output = '''```python
def sort(lst):
    return sorted(lst)
```'''
            score = await validator.validate(output)
            assert score == 0.95

    @pytest.mark.asyncio
    async def test_llm_judge_with_syntax_validation(self) -> None:
        """Test LLM judge with syntax validation enabled."""
        config = ValidationConfig(
            type=ValidationType.CODE_LLM,
            criteria="Check code quality",
            require_syntax_valid=True,
        )
        validator = CodeLLMValidator(config)

        # Invalid syntax should fail before reaching LLM
        output = '''```python
def sort(lst)  # Missing colon
    return sorted(lst)
```'''
        score = await validator.validate(output)
        assert score == 0.0  # Failed due to syntax, not LLM

    @pytest.mark.asyncio
    async def test_llm_judge_empty_code(self) -> None:
        """Test LLM judge with empty code extraction."""
        config = ValidationConfig(
            type=ValidationType.CODE_LLM,
            criteria="Evaluate code",
        )
        validator = CodeLLMValidator(config)

        output = "This is just text with no code."
        score = await validator.validate(output)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_llm_judge_parse_error(self) -> None:
        """Test LLM judge with unparseable response."""
        config = ValidationConfig(
            type=ValidationType.CODE_LLM,
            criteria="Check quality",
            partial_credit=True,
        )
        validator = CodeLLMValidator(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="The score is 0.8 out of 1.0")]

        with patch("anthropic.AsyncAnthropic") as mock:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock.return_value = mock_client

            output = '''```python
def foo(): pass
```'''
            score = await validator.validate(output)
            # Should extract 0.8 from the text
            assert score == 0.8


class TestGetValidatorCodeTypes:
    """Tests for get_validator with code validation types."""

    def test_get_validator_code(self) -> None:
        """Test get_validator for CODE type."""
        config = ValidationConfig(type=ValidationType.CODE, criteria="def ")
        validator = get_validator(config)
        assert isinstance(validator, CodeValidator)

    def test_get_validator_code_syntax(self) -> None:
        """Test get_validator for CODE_SYNTAX type."""
        config = ValidationConfig(type=ValidationType.CODE_SYNTAX, criteria="")
        validator = get_validator(config)
        assert isinstance(validator, CodeSyntaxValidator)

    def test_get_validator_code_llm(self) -> None:
        """Test get_validator for CODE_LLM type."""
        config = ValidationConfig(type=ValidationType.CODE_LLM, criteria="Evaluate")
        validator = get_validator(config)
        assert isinstance(validator, CodeLLMValidator)

    def test_get_validator_code_with_all_options(self) -> None:
        """Test get_validator with all code-specific options."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="async def",
            partial_credit=True,
            language="python",
            require_syntax_valid=True,
            min_code_lines=5,
        )
        validator = get_validator(config)
        assert isinstance(validator, CodeValidator)
        # Verify config was passed correctly
        assert validator.config.language == "python"
        assert validator.config.require_syntax_valid is True
        assert validator.config.min_code_lines == 5


class TestValidationConfigCodeOptions:
    """Tests for ValidationConfig code-specific options."""

    def test_default_code_options(self) -> None:
        """Test default values for code options."""
        config = ValidationConfig(type=ValidationType.CODE, criteria="def ")
        assert config.language == "python"
        assert config.require_syntax_valid is True
        assert config.min_code_lines == 0

    def test_custom_code_options(self) -> None:
        """Test custom values for code options."""
        config = ValidationConfig(
            type=ValidationType.CODE,
            criteria="def ",
            language="javascript",
            require_syntax_valid=False,
            min_code_lines=10,
        )
        assert config.language == "javascript"
        assert config.require_syntax_valid is False
        assert config.min_code_lines == 10

    def test_code_options_from_dict(self) -> None:
        """Test code options loaded from dict."""
        tc = TestCase(
            id="test-1",
            prompt="Write code",
            expected_behavior="Returns code",
            validation={
                "type": "code",
                "criteria": "def ",
                "language": "python",
                "require_syntax_valid": True,
                "min_code_lines": 5,
            },
        )
        assert tc.validation.type == ValidationType.CODE
        assert tc.validation.language == "python"
        assert tc.validation.require_syntax_valid is True
        assert tc.validation.min_code_lines == 5
