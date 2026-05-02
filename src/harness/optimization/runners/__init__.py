"""Agent runners for test case execution with tracing.

This module provides infrastructure for executing agents on test cases,
collecting execution spans, and computing validation scores.

Example usage:
    from harness.optimization.runners import (
        AgentRunner,
        BatchRunner,
        RunnerConfig,
    )
    from harness.optimization.testcases import TestSuiteLoader

    # Load test suite
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    # Create runner
    config = RunnerConfig(agent_name="python-expert")
    runner = AgentRunner(config)

    # Run single test case
    result = await runner.run_test_case(suite.test_cases[0])
    print(f"Score: {result.validation_score}")

    # Run entire suite
    suite_result = await runner.run_suite(suite)
    print(f"Average score: {suite_result.average_score}")

    # Run with parallel execution
    batch_config = RunnerConfig(agent_name="python-expert", max_concurrent=4)
    batch_runner = BatchRunner(batch_config)
    suite_result = await batch_runner.run_suite(suite)

    # Run with custom system prompt
    result = await runner.run_test_case(
        suite.test_cases[0],
        system_prompt_override="You are a Python expert focused on writing clean code.",
    )
"""

from harness.optimization.runners.agent_runner import AgentRunner
from harness.optimization.runners.base import (
    BaseRunner,
    RunContext,
    RunnerConfig,
    RunnerProtocol,
)
from harness.optimization.runners.batch_runner import BatchRunner, ProgressCallback

__all__ = [
    # Config
    "RunnerConfig",
    "RunContext",
    # Protocol
    "RunnerProtocol",
    # Base
    "BaseRunner",
    # Runners
    "AgentRunner",
    "BatchRunner",
    # Callbacks
    "ProgressCallback",
]
