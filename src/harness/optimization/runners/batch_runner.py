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
import hashlib
import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from harness.optimization.runners.agent_runner import AgentRunner
from harness.optimization.runners.base import BaseRunner, RunnerConfig
from harness.optimization.testcases.models import SuiteResult, TestResult


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time for display."""
    if seconds < 60:
        return f"{seconds:05.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}m{secs:02d}s"

if TYPE_CHECKING:
    from harness.optimization.testcases import TestCase, TestSuite

logger = structlog.get_logger(__name__)


class TestResultCache:
    """In-memory cache for test execution results.

    Caches results based on test case ID and system prompt hash
    to avoid re-running identical tests.
    """

    def __init__(self, enabled: bool = True, max_size: int = 1000) -> None:
        """Initialize the cache.

        Args:
            enabled: Whether caching is enabled.
            max_size: Maximum number of entries to store.
        """
        self._enabled = enabled
        self._max_size = max_size
        self._cache: dict[str, TestResult] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, test_id: str, prompt_hash: str) -> str:
        """Create cache key from test ID and prompt hash."""
        return f"{test_id}:{prompt_hash}"

    def _hash_prompt(self, prompt: str) -> str:
        """Create hash of system prompt for cache key."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def get(
        self,
        test_id: str,
        system_prompt: str,
    ) -> TestResult | None:
        """Get cached result if available.

        Args:
            test_id: Test case identifier.
            system_prompt: System prompt used for test.

        Returns:
            Cached TestResult or None if not cached.
        """
        if not self._enabled:
            return None

        prompt_hash = self._hash_prompt(system_prompt)
        key = self._make_key(test_id, prompt_hash)

        result = self._cache.get(key)
        if result:
            self._hits += 1
            logger.debug("Cache hit", test_id=test_id, prompt_hash=prompt_hash)
        else:
            self._misses += 1

        return result

    def put(
        self,
        test_id: str,
        system_prompt: str,
        result: TestResult,
    ) -> None:
        """Store test result in cache.

        Args:
            test_id: Test case identifier.
            system_prompt: System prompt used for test.
            result: Test result to cache.
        """
        if not self._enabled:
            return

        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            # Simple FIFO eviction - remove first 10%
            keys_to_remove = list(self._cache.keys())[: self._max_size // 10]
            for key in keys_to_remove:
                del self._cache[key]

        prompt_hash = self._hash_prompt(system_prompt)
        key = self._make_key(test_id, prompt_hash)
        self._cache[key] = result

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": len(self._cache),
        }

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Global cache instance (shared across runner instances)
_global_cache = TestResultCache()


def get_test_result_cache() -> TestResultCache:
    """Get the global test result cache."""
    return _global_cache


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
        cache: TestResultCache | None = None,
    ) -> None:
        """Initialize the batch runner.

        Args:
            config: Runner configuration with max_concurrent setting.
            on_progress: Optional callback for progress updates.
            cache: Optional test result cache (uses global cache if None).
        """
        super().__init__(config)
        self._agent_runner = AgentRunner(config)
        self._on_progress = on_progress
        self._semaphore: asyncio.Semaphore | None = None
        self._cache = cache if cache is not None else get_test_result_cache()

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
        verbose = self.config.verbose

        logger.info(
            "Starting batch execution",
            suite_name=suite.name,
            test_count=total,
            max_concurrent=self.config.max_concurrent,
            verbose=verbose,
        )

        if verbose:
            print(
                f"\n[Batch] Starting {total} tests "
                f"(max_concurrent={self.config.max_concurrent})",
                file=sys.stderr,
                flush=True,
            )

        # Create semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Track completed count for progress
        completed = 0
        results: list[TestResult] = [None] * total  # Pre-allocate for ordering

        async def run_with_semaphore(index: int, test_case: TestCase) -> None:
            """Run a test case with semaphore limiting and caching."""
            nonlocal completed

            test_start = time.time()
            prompt = system_prompt_override or ""
            from_cache = False

            # Check cache first
            cached_result = self._cache.get(test_case.id, prompt)
            if cached_result:
                result = cached_result
                from_cache = True
            else:
                if verbose:
                    elapsed = _format_elapsed(time.time() - start_time)
                    print(
                        f"[{elapsed}] Test {index + 1}/{total}: "
                        f"{test_case.id} - evaluating...",
                        file=sys.stderr,
                        flush=True,
                    )

                async with self._semaphore:
                    result = await self._agent_runner.run_test_case(
                        test_case, system_prompt_override
                    )
                    # Store in cache
                    self._cache.put(test_case.id, prompt, result)

            results[index] = result
            completed += 1

            if verbose:
                elapsed = _format_elapsed(time.time() - start_time)
                test_duration = time.time() - test_start
                status = "✓" if result.success else "✗"
                cache_indicator = " (cached)" if from_cache else ""
                print(
                    f"[{elapsed}] Test {completed}/{total}: "
                    f"{test_case.id} - {status} score={result.score:.2f}"
                    f"{cache_indicator} ({test_duration:.1f}s)",
                    file=sys.stderr,
                    flush=True,
                )

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

        if verbose:
            elapsed = _format_elapsed(duration_seconds)
            print(
                f"[{elapsed}] Batch complete: "
                f"{suite_result.passed_count}/{total} passed, "
                f"avg_score={suite_result.total_score:.2f}",
                file=sys.stderr,
                flush=True,
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
            if tags and not any(tag in tc.tags for tag in tags):
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
