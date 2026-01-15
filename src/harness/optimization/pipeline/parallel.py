"""Parallel execution infrastructure for CGF optimization pipeline.

Provides configurable concurrency for:
- Research specialist invocations
- Test case validation
- Batch API calls
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class ParallelConfig:
    """Configuration for parallel execution.

    Attributes:
        max_research_concurrent: Max concurrent research invocations.
        max_validation_concurrent: Max concurrent test validations.
        max_api_concurrent: Max concurrent API calls.
        batch_size: Default batch size for batch operations.
        timeout_seconds: Default timeout for individual tasks.
        retry_count: Number of retries on failure.
        retry_delay_seconds: Delay between retries.
    """

    max_research_concurrent: int = 4
    max_validation_concurrent: int = 8
    max_api_concurrent: int = 5
    batch_size: int = 10
    timeout_seconds: float = 60.0
    retry_count: int = 2
    retry_delay_seconds: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_research_concurrent": self.max_research_concurrent,
            "max_validation_concurrent": self.max_validation_concurrent,
            "max_api_concurrent": self.max_api_concurrent,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParallelConfig:
        """Create from dictionary."""
        return cls(
            max_research_concurrent=data.get("max_research_concurrent", 4),
            max_validation_concurrent=data.get("max_validation_concurrent", 8),
            max_api_concurrent=data.get("max_api_concurrent", 5),
            batch_size=data.get("batch_size", 10),
            timeout_seconds=data.get("timeout_seconds", 60.0),
            retry_count=data.get("retry_count", 2),
            retry_delay_seconds=data.get("retry_delay_seconds", 1.0),
        )


@dataclass
class TaskResult:
    """Result of a parallel task execution.

    Attributes:
        success: Whether the task completed successfully.
        result: The result value if successful.
        error: Error message if failed.
        task_id: Identifier for the task.
        duration_seconds: Time taken to execute.
        retries: Number of retries needed.
    """

    success: bool
    result: Any = None
    error: str | None = None
    task_id: str | None = None
    duration_seconds: float = 0.0
    retries: int = 0


@dataclass
class BatchResult:
    """Result of a batch operation.

    Attributes:
        total: Total number of items processed.
        successful: Number of successful items.
        failed: Number of failed items.
        results: List of individual TaskResults.
        duration_seconds: Total time for the batch.
    """

    total: int = 0
    successful: int = 0
    failed: int = 0
    results: list[TaskResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100


class ParallelExecutor:
    """Executor for running tasks in parallel with concurrency control.

    Example:
        config = ParallelConfig(max_research_concurrent=4)
        executor = ParallelExecutor(config)

        # Run multiple research tasks
        tasks = [research_func(topic) for topic in topics]
        results = await executor.run_research_parallel(tasks)

        # Run validation batch
        results = await executor.run_validation_batch(
            items=test_cases,
            process_func=validate_test_case,
        )
    """

    def __init__(self, config: ParallelConfig | None = None) -> None:
        """Initialize the executor.

        Args:
            config: Parallel execution configuration.
        """
        self.config = config or ParallelConfig()
        self._research_semaphore = asyncio.Semaphore(
            self.config.max_research_concurrent
        )
        self._validation_semaphore = asyncio.Semaphore(
            self.config.max_validation_concurrent
        )
        self._api_semaphore = asyncio.Semaphore(
            self.config.max_api_concurrent
        )

    async def run_research_parallel(
        self,
        tasks: Sequence[Awaitable[T]],
        task_ids: Sequence[str] | None = None,
    ) -> list[TaskResult]:
        """Run research tasks in parallel with concurrency limit.

        Args:
            tasks: Sequence of coroutines to execute.
            task_ids: Optional identifiers for each task.

        Returns:
            List of TaskResults for each task.
        """
        return await self._run_with_semaphore(
            semaphore=self._research_semaphore,
            tasks=tasks,
            task_ids=task_ids,
            task_type="research",
        )

    async def run_validation_parallel(
        self,
        tasks: Sequence[Awaitable[T]],
        task_ids: Sequence[str] | None = None,
    ) -> list[TaskResult]:
        """Run validation tasks in parallel with concurrency limit.

        Args:
            tasks: Sequence of coroutines to execute.
            task_ids: Optional identifiers for each task.

        Returns:
            List of TaskResults for each task.
        """
        return await self._run_with_semaphore(
            semaphore=self._validation_semaphore,
            tasks=tasks,
            task_ids=task_ids,
            task_type="validation",
        )

    async def run_api_parallel(
        self,
        tasks: Sequence[Awaitable[T]],
        task_ids: Sequence[str] | None = None,
    ) -> list[TaskResult]:
        """Run API call tasks in parallel with concurrency limit.

        Args:
            tasks: Sequence of coroutines to execute.
            task_ids: Optional identifiers for each task.

        Returns:
            List of TaskResults for each task.
        """
        return await self._run_with_semaphore(
            semaphore=self._api_semaphore,
            tasks=tasks,
            task_ids=task_ids,
            task_type="api",
        )

    async def run_validation_batch(
        self,
        items: Sequence[T],
        process_func: Callable[[T], Awaitable[R]],
        batch_size: int | None = None,
    ) -> BatchResult:
        """Process items in batches with parallel execution.

        Args:
            items: Items to process.
            process_func: Async function to apply to each item.
            batch_size: Override default batch size.

        Returns:
            BatchResult with all results.
        """
        batch_size = batch_size or self.config.batch_size
        return await self._process_in_batches(
            items=items,
            process_func=process_func,
            semaphore=self._validation_semaphore,
            batch_size=batch_size,
            task_type="validation_batch",
        )

    async def run_api_batch(
        self,
        items: Sequence[T],
        process_func: Callable[[T], Awaitable[R]],
        batch_size: int | None = None,
    ) -> BatchResult:
        """Process API calls in batches with parallel execution.

        Args:
            items: Items to process.
            process_func: Async function to apply to each item.
            batch_size: Override default batch size.

        Returns:
            BatchResult with all results.
        """
        batch_size = batch_size or self.config.batch_size
        return await self._process_in_batches(
            items=items,
            process_func=process_func,
            semaphore=self._api_semaphore,
            batch_size=batch_size,
            task_type="api_batch",
        )

    async def _run_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        tasks: Sequence[Awaitable[T]],
        task_ids: Sequence[str] | None,
        task_type: str,
    ) -> list[TaskResult]:
        """Execute tasks with semaphore-based concurrency control.

        Args:
            semaphore: Semaphore for concurrency control.
            tasks: Coroutines to execute.
            task_ids: Optional identifiers.
            task_type: Type of task for logging.

        Returns:
            List of TaskResults.
        """
        if task_ids is None:
            task_ids = [f"{task_type}_{i}" for i in range(len(tasks))]

        logger.debug(
            "Starting parallel execution",
            task_type=task_type,
            count=len(tasks),
        )

        async def execute_with_retry(
            task: Awaitable[T],
            task_id: str,
        ) -> TaskResult:
            """Execute a single task with retry logic."""
            import time

            start_time = time.perf_counter()
            retries = 0
            last_error: str | None = None

            for attempt in range(self.config.retry_count + 1):
                try:
                    async with semaphore:
                        result = await asyncio.wait_for(
                            task,
                            timeout=self.config.timeout_seconds,
                        )
                        duration = time.perf_counter() - start_time
                        return TaskResult(
                            success=True,
                            result=result,
                            task_id=task_id,
                            duration_seconds=duration,
                            retries=retries,
                        )
                except TimeoutError:
                    timeout = self.config.timeout_seconds
                    last_error = f"Timeout after {timeout}s"
                    retries = attempt
                except Exception as e:
                    last_error = str(e)
                    retries = attempt

                if attempt < self.config.retry_count:
                    await asyncio.sleep(self.config.retry_delay_seconds)

            duration = time.perf_counter() - start_time
            logger.warning(
                "Task failed after retries",
                task_id=task_id,
                retries=retries,
                error=last_error,
            )
            return TaskResult(
                success=False,
                error=last_error,
                task_id=task_id,
                duration_seconds=duration,
                retries=retries,
            )

        results = await asyncio.gather(
            *[
                execute_with_retry(task, task_id)
                for task, task_id in zip(tasks, task_ids, strict=True)
            ]
        )

        successful = sum(1 for r in results if r.success)
        logger.debug(
            "Parallel execution complete",
            task_type=task_type,
            total=len(results),
            successful=successful,
            failed=len(results) - successful,
        )

        return list(results)

    async def _process_in_batches(
        self,
        items: Sequence[T],
        process_func: Callable[[T], Awaitable[R]],
        semaphore: asyncio.Semaphore,
        batch_size: int,
        task_type: str,
    ) -> BatchResult:
        """Process items in batches.

        Args:
            items: Items to process.
            process_func: Function to apply to each item.
            semaphore: Concurrency control.
            batch_size: Items per batch.
            task_type: Type for logging.

        Returns:
            BatchResult with all results.
        """
        import time

        start_time = time.perf_counter()
        all_results: list[TaskResult] = []

        # Process in batches
        for batch_start in range(0, len(items), batch_size):
            batch_end = min(batch_start + batch_size, len(items))
            batch = items[batch_start:batch_end]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(items) + batch_size - 1) // batch_size

            logger.debug(
                "Processing batch",
                task_type=task_type,
                batch=batch_num,
                total_batches=total_batches,
                batch_size=len(batch),
            )

            # Create tasks for this batch
            tasks = [process_func(item) for item in batch]
            task_ids = [
                f"{task_type}_{batch_start + i}"
                for i in range(len(batch))
            ]

            batch_results = await self._run_with_semaphore(
                semaphore=semaphore,
                tasks=tasks,
                task_ids=task_ids,
                task_type=task_type,
            )
            all_results.extend(batch_results)

        total_duration = time.perf_counter() - start_time
        successful = sum(1 for r in all_results if r.success)

        return BatchResult(
            total=len(all_results),
            successful=successful,
            failed=len(all_results) - successful,
            results=all_results,
            duration_seconds=total_duration,
        )


async def gather_with_concurrency[T](
    limit: int,
    tasks: Sequence[Awaitable[T]],
) -> list[T | BaseException]:
    """Run coroutines with a concurrency limit.

    A simpler helper for cases where you just need basic concurrency
    control without the full ParallelExecutor.

    Args:
        limit: Maximum concurrent tasks.
        tasks: Coroutines to execute.

    Returns:
        List of results (or exceptions).

    Example:
        results = await gather_with_concurrency(
            limit=5,
            tasks=[fetch(url) for url in urls],
        )
    """
    semaphore = asyncio.Semaphore(limit)

    async def with_semaphore(task: Awaitable[T]) -> T:
        async with semaphore:
            return await task

    return await asyncio.gather(
        *[with_semaphore(t) for t in tasks],
        return_exceptions=True,
    )


async def batch_process[T, R](
    items: Sequence[T],
    process_func: Callable[[T], Awaitable[R]],
    batch_size: int = 10,
    concurrency: int = 5,
) -> list[R | BaseException]:
    """Process items in batches with concurrency control.

    A simpler helper for batch processing without full ParallelExecutor.

    Args:
        items: Items to process.
        process_func: Async function to apply to each item.
        batch_size: Number of items per batch.
        concurrency: Max concurrent tasks within each batch.

    Returns:
        List of results (or exceptions).

    Example:
        results = await batch_process(
            items=test_cases,
            process_func=validate,
            batch_size=20,
            concurrency=10,
        )
    """
    all_results: list[R | BaseException] = []

    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start:batch_start + batch_size]
        tasks = [process_func(item) for item in batch]
        batch_results = await gather_with_concurrency(concurrency, tasks)
        all_results.extend(batch_results)

    return all_results
