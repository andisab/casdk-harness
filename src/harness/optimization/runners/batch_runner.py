"""Batch runner for parallel test suite execution.

Executes multiple test cases concurrently with configurable parallelism,
aggregating results and providing progress feedback.

Example usage:
    from harness.optimization.runners import BatchRunner, RunnerConfig
    from harness.optimization.testcases import TestSuiteLoader

    config = RunnerConfig(
        agent_name="python-expert",
        max_concurrent=4,
    )
    runner = BatchRunner(config)

    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")
    result = await runner.run_suite(suite)
    print(f"Passed: {result.passed_count}/{len(result.results)}")
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Callable

import structlog

from harness.optimization.runners.agent_runner import AgentRunner
from harness.optimization.runners.base import BaseRunner, RunnerConfig
from harness.optimization.testcases.models import SuiteResult, TestResult

if TYPE_CHECKING:
    from harness.optimization.testcases import TestCase, TestSuite

logger = structlog.get_logger(__name__)


ProgressCallback = Callable[[int, int, TestResult], None]


class BatchRunner(BaseRunner):
    """Runner for parallel test suite execution.

    Extends AgentRunner with concurrent execution capability,
    using semaphores to control parallelism.

    Key features:
    - Concurrent test case execution
    - Configurable max parallelism
    - Progress callbacks
    - Graceful cancellation
    - Result aggregation
    """

    def __init__(
        self,
        config: RunnerConfig,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Initialize the batch runner.

        Args:
            config: Runner configuration with max_concurrent setting.
            on_progress: Optional callback for progress updates.
        """
        super().__init__(config)
        self._agent_runner = AgentRunner(config)
        self._on_progress = on_progress
        self._semaphore: asyncio.Semaphore | None = None

    async def run_test_case(
        self,
        test_case: TestCase,
        system_prompt_override: str | None = None,
    ) -> TestResult:
        """Run a single test case (delegates to AgentRunner).

        Args:
            test_case: The test case to execute.
            system_prompt_override: Optional system prompt override.

        Returns:
            TestResult with output, feedback, and score.
        """
        return await self._agent_runner.run_test_case(
            test_case, system_prompt_override
        )

    async def run_suite(
        self,
        suite: TestSuite,
        system_prompt_override: str | None = None,
    ) -> SuiteResult:
        """Run all test cases in a suite concurrently.

        Args:
            suite: The test suite to execute.
            system_prompt_override: Optional system prompt override.

        Returns:
            SuiteResult with all results and aggregated metrics.
        """
        self._validate_agent_name(suite)

        start_time = time.time()
        total = len(suite.test_cases)

        logger.info(
            "Starting batch execution",
            suite_name=suite.name,
            test_count=total,
            max_concurrent=self.config.max_concurrent,
        )

        # Create semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Track completed count for progress
        completed = 0
        results: list[TestResult] = [None] * total  # Pre-allocate for ordering

        async def run_with_semaphore(index: int, test_case: TestCase) -> None:
            """Run a test case with semaphore limiting."""
            nonlocal completed

            async with self._semaphore:
                result = await self._agent_runner.run_test_case(
                    test_case, system_prompt_override
                )
                results[index] = result

                completed += 1
                if self._on_progress:
                    self._on_progress(completed, total, result)

        # Create tasks for all test cases
        tasks = [
            asyncio.create_task(run_with_semaphore(i, tc))
            for i, tc in enumerate(suite.test_cases)
        ]

        # Wait for all to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out any None results (shouldn't happen but be safe)
        valid_results = [r for r in results if r is not None]

        duration_seconds = time.time() - start_time

        suite_result = SuiteResult(
            suite_name=suite.name,
            agent_name=self.config.agent_name,
            results=valid_results,
        )

        logger.info(
            "Batch execution completed",
            suite_name=suite.name,
            passed=suite_result.passed_count,
            failed=suite_result.failed_count,
            average_score=suite_result.total_score,
            duration=f"{duration_seconds:.2f}s",
        )

        return suite_result

    async def run_filtered(
        self,
        suite: TestSuite,
        tags: list[str] | None = None,
        ids: list[str] | None = None,
        system_prompt_override: str | None = None,
    ) -> SuiteResult:
        """Run only test cases matching filter criteria.

        Args:
            suite: The test suite to filter and execute.
            tags: Only run cases with any of these tags.
            ids: Only run cases with these IDs.
            system_prompt_override: Optional system prompt override.

        Returns:
            SuiteResult with filtered test results.
        """
        self._validate_agent_name(suite)

        # Filter test cases
        filtered = []
        for tc in suite.test_cases:
            if ids and tc.id not in ids:
                continue
            if tags:
                if not any(tag in tc.tags for tag in tags):
                    continue
            filtered.append(tc)

        if not filtered:
            logger.warning(
                "No test cases matched filter",
                tags=tags,
                ids=ids,
            )
            return SuiteResult(
                suite_name=suite.name,
                agent_name=self.config.agent_name,
                results=[],
            )

        logger.info(
            "Running filtered test cases",
            suite_name=suite.name,
            filtered_count=len(filtered),
            total_count=len(suite.test_cases),
        )

        # Create a temporary suite with filtered cases
        from harness.optimization.testcases import TestSuite

        filtered_suite = TestSuite(
            name=f"{suite.name} (filtered)",
            description=suite.description,
            agent_name=suite.agent_name,
            version=suite.version,
            test_cases=filtered,
            metadata=suite.metadata,
        )

        return await self.run_suite(filtered_suite, system_prompt_override)

    async def run_until_pass(
        self,
        suite: TestSuite,
        max_attempts: int = 3,
        system_prompt_override: str | None = None,
    ) -> tuple[SuiteResult, int]:
        """Run suite until all tests pass or max attempts reached.

        Retries failed tests in subsequent attempts.

        Args:
            suite: The test suite to execute.
            max_attempts: Maximum retry attempts.
            system_prompt_override: Optional system prompt override.

        Returns:
            Tuple of (final SuiteResult, attempts used).
        """
        self._validate_agent_name(suite)

        current_suite = suite
        all_results: dict[str, TestResult] = {}

        for attempt in range(1, max_attempts + 1):
            logger.info(
                "Running attempt",
                attempt=attempt,
                max_attempts=max_attempts,
                remaining_tests=len(current_suite.test_cases),
            )

            result = await self.run_suite(current_suite, system_prompt_override)

            # Update results map
            for r in result.results:
                all_results[r.test_case_id] = r

            # Check if all passed
            failed = [r for r in result.results if not r.success or r.score < 0.5]

            if not failed:
                logger.info("All tests passed", attempt=attempt)
                break

            if attempt < max_attempts:
                # Create suite with only failed tests for retry
                failed_ids = {r.test_case_id for r in failed}
                failed_cases = [tc for tc in current_suite.test_cases if tc.id in failed_ids]

                from harness.optimization.testcases import TestSuite

                current_suite = TestSuite(
                    name=f"{suite.name} (retry {attempt})",
                    description=suite.description,
                    agent_name=suite.agent_name,
                    version=suite.version,
                    test_cases=failed_cases,
                    metadata=suite.metadata,
                )

                logger.info(
                    "Retrying failed tests",
                    failed_count=len(failed_cases),
                )

        # Build final result from all attempts
        final_results = list(all_results.values())

        final_suite_result = SuiteResult(
            suite_name=suite.name,
            agent_name=self.config.agent_name,
            results=final_results,
        )

        return final_suite_result, attempt
