"""Test case infrastructure for agent optimization.

This module provides the test case loading and validation infrastructure
for the CGF optimization pipeline.

Example usage:
    from harness.optimization.testcases import (
        TestSuite,
        TestCase,
        TestResult,
        ValidationConfig,
        ValidationType,
        TestSuiteLoader,
        get_validator,
    )

    # Load a test suite
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    # Get validator for a test case
    validator = get_validator(suite.test_cases[0].validation)

    # Validate output
    score = await validator.validate(agent_output)
"""

from harness.optimization.testcases.loader import (
    TestSuiteLoader,
    TestSuiteLoaderError,
)
from harness.optimization.testcases.models import (
    SuiteResult,
    TestCase,
    TestResult,
    TestSuite,
    ValidationConfig,
    ValidationType,
)
from harness.optimization.testcases.validators import (
    CompositeValidator,
    ContainsValidator,
    ExactValidator,
    LLMJudgeValidator,
    RegexValidator,
    Validator,
    get_validator,
)

__all__ = [
    # Models
    "TestCase",
    "TestSuite",
    "TestResult",
    "SuiteResult",
    "ValidationConfig",
    "ValidationType",
    # Loader
    "TestSuiteLoader",
    "TestSuiteLoaderError",
    # Validators
    "Validator",
    "ExactValidator",
    "ContainsValidator",
    "RegexValidator",
    "LLMJudgeValidator",
    "CompositeValidator",
    "get_validator",
]
