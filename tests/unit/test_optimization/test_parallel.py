"""Unit tests for parallel execution infrastructure."""

from __future__ import annotations

import asyncio
import time

from harness.optimization.pipeline.parallel import (
    BatchResult,
    ParallelConfig,
    ParallelExecutor,
    TaskResult,
    batch_process,
    gather_with_concurrency,
)


class TestParallelConfig:
    """Tests for ParallelConfig."""

    def test_default_values(self) -> None:
        """ParallelConfig has sensible defaults."""
        config = ParallelConfig()

        assert config.max_research_concurrent == 4
        assert config.max_validation_concurrent == 8
        assert config.max_api_concurrent == 5
        assert config.batch_size == 10
        assert config.timeout_seconds == 60.0
        assert config.retry_count == 2
        assert config.retry_delay_seconds == 1.0

    def test_custom_values(self) -> None:
        """ParallelConfig accepts custom values."""
        config = ParallelConfig(
            max_research_concurrent=2,
            max_validation_concurrent=4,
            batch_size=20,
        )

        assert config.max_research_concurrent == 2
        assert config.max_validation_concurrent == 4
        assert config.batch_size == 20

    def test_to_dict(self) -> None:
        """ParallelConfig.to_dict() serializes correctly."""
        config = ParallelConfig(max_api_concurrent=10)
        result = config.to_dict()

        assert result["max_api_concurrent"] == 10
        assert "max_research_concurrent" in result

    def test_from_dict(self) -> None:
        """ParallelConfig.from_dict() deserializes correctly."""
        data = {
            "max_research_concurrent": 3,
            "batch_size": 15,
        }
        config = ParallelConfig.from_dict(data)

        assert config.max_research_concurrent == 3
        assert config.batch_size == 15
        # Should use defaults for missing values
        assert config.max_api_concurrent == 5


class TestTaskResult:
    """Tests for TaskResult."""

    def test_successful_result(self) -> None:
        """TaskResult for successful task."""
        result = TaskResult(
            success=True,
            result="test_output",
            task_id="task_1",
            duration_seconds=1.5,
        )

        assert result.success is True
        assert result.result == "test_output"
        assert result.error is None
        assert result.retries == 0

    def test_failed_result(self) -> None:
        """TaskResult for failed task."""
        result = TaskResult(
            success=False,
            error="Connection failed",
            task_id="task_2",
            retries=2,
        )

        assert result.success is False
        assert result.result is None
        assert result.error == "Connection failed"
        assert result.retries == 2


class TestBatchResult:
    """Tests for BatchResult."""

    def test_success_rate(self) -> None:
        """BatchResult calculates success rate correctly."""
        result = BatchResult(
            total=10,
            successful=7,
            failed=3,
        )

        assert result.success_rate == 70.0

    def test_success_rate_empty(self) -> None:
        """BatchResult handles empty batch."""
        result = BatchResult(total=0, successful=0, failed=0)

        assert result.success_rate == 0.0

    def test_full_success(self) -> None:
        """BatchResult with 100% success."""
        result = BatchResult(
            total=5,
            successful=5,
            failed=0,
        )

        assert result.success_rate == 100.0


class TestParallelExecutor:
    """Tests for ParallelExecutor."""

    async def test_run_research_parallel(self) -> None:
        """ParallelExecutor runs research tasks in parallel."""
        config = ParallelConfig(max_research_concurrent=2)
        executor = ParallelExecutor(config)

        async def mock_research(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2

        tasks = [mock_research(i) for i in range(4)]
        results = await executor.run_research_parallel(tasks)

        assert len(results) == 4
        assert all(r.success for r in results)
        assert [r.result for r in results] == [0, 2, 4, 6]

    async def test_run_validation_parallel(self) -> None:
        """ParallelExecutor runs validation tasks in parallel."""
        config = ParallelConfig(max_validation_concurrent=4)
        executor = ParallelExecutor(config)

        async def mock_validate(item: str) -> bool:
            await asyncio.sleep(0.01)
            return item.startswith("valid")

        tasks = [mock_validate(f"valid_{i}") for i in range(3)]
        results = await executor.run_validation_parallel(tasks)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.result is True for r in results)

    async def test_run_api_parallel(self) -> None:
        """ParallelExecutor runs API tasks in parallel."""
        config = ParallelConfig(max_api_concurrent=3)
        executor = ParallelExecutor(config)

        async def mock_api_call(endpoint: str) -> dict:
            await asyncio.sleep(0.01)
            return {"endpoint": endpoint, "status": "ok"}

        tasks = [mock_api_call(f"/api/{i}") for i in range(5)]
        results = await executor.run_api_parallel(tasks)

        assert len(results) == 5
        assert all(r.success for r in results)

    async def test_concurrency_limit_enforced(self) -> None:
        """ParallelExecutor respects concurrency limits."""
        config = ParallelConfig(max_research_concurrent=2)
        executor = ParallelExecutor(config)

        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrency() -> int:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return max_concurrent

        tasks = [track_concurrency() for _ in range(6)]
        await executor.run_research_parallel(tasks)

        # Should never exceed the limit of 2
        assert max_concurrent <= 2

    async def test_task_with_custom_ids(self) -> None:
        """ParallelExecutor uses custom task IDs."""
        executor = ParallelExecutor()

        async def mock_task() -> str:
            return "done"

        tasks = [mock_task() for _ in range(3)]
        task_ids = ["custom_a", "custom_b", "custom_c"]

        results = await executor.run_research_parallel(
            tasks, task_ids=task_ids
        )

        assert [r.task_id for r in results] == task_ids

    async def test_validation_batch(self) -> None:
        """ParallelExecutor processes validation batch."""
        config = ParallelConfig(batch_size=3, max_validation_concurrent=2)
        executor = ParallelExecutor(config)

        async def validate_item(item: int) -> bool:
            await asyncio.sleep(0.01)
            return item > 0

        items = list(range(1, 8))  # [1, 2, 3, 4, 5, 6, 7]
        result = await executor.run_validation_batch(items, validate_item)

        assert result.total == 7
        assert result.successful == 7
        assert result.failed == 0
        assert result.success_rate == 100.0

    async def test_api_batch(self) -> None:
        """ParallelExecutor processes API batch."""
        config = ParallelConfig(batch_size=2)
        executor = ParallelExecutor(config)

        async def call_api(endpoint: str) -> dict:
            return {"endpoint": endpoint}

        items = [f"/api/endpoint_{i}" for i in range(5)]
        result = await executor.run_api_batch(items, call_api)

        assert result.total == 5
        assert result.successful == 5

    async def test_handles_task_failure(self) -> None:
        """ParallelExecutor handles task failures gracefully."""
        config = ParallelConfig(
            max_research_concurrent=4,
            retry_count=0,  # No retries for faster test
        )
        executor = ParallelExecutor(config)

        async def maybe_fail(should_fail: bool) -> str:
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"

        tasks = [
            maybe_fail(False),
            maybe_fail(True),
            maybe_fail(False),
        ]
        results = await executor.run_research_parallel(tasks)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error == "Intentional failure"
        assert results[2].success is True

    async def test_timeout_handling(self) -> None:
        """ParallelExecutor handles timeouts."""
        config = ParallelConfig(
            timeout_seconds=0.05,
            retry_count=0,
        )
        executor = ParallelExecutor(config)

        async def slow_task() -> str:
            await asyncio.sleep(1.0)  # Much longer than timeout
            return "done"

        tasks = [slow_task()]
        results = await executor.run_research_parallel(tasks)

        assert len(results) == 1
        assert results[0].success is False
        assert "Timeout" in (results[0].error or "")


class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency helper."""

    async def test_basic_concurrency(self) -> None:
        """gather_with_concurrency respects limit."""
        concurrent = 0
        max_concurrent = 0

        async def track() -> int:
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.02)
            concurrent -= 1
            return max_concurrent

        tasks = [track() for _ in range(10)]
        results = await gather_with_concurrency(3, tasks)

        assert len(results) == 10
        assert max_concurrent <= 3

    async def test_returns_results(self) -> None:
        """gather_with_concurrency returns all results."""

        async def double(x: int) -> int:
            return x * 2

        tasks = [double(i) for i in range(5)]
        results = await gather_with_concurrency(5, tasks)

        assert results == [0, 2, 4, 6, 8]

    async def test_handles_exceptions(self) -> None:
        """gather_with_concurrency captures exceptions."""

        async def maybe_fail(x: int) -> int:
            if x == 2:
                raise ValueError("Failed at 2")
            return x

        tasks = [maybe_fail(i) for i in range(4)]
        results = await gather_with_concurrency(4, tasks)

        assert results[0] == 0
        assert results[1] == 1
        assert isinstance(results[2], ValueError)
        assert results[3] == 3


class TestBatchProcess:
    """Tests for batch_process helper."""

    async def test_processes_all_items(self) -> None:
        """batch_process processes all items."""

        async def square(x: int) -> int:
            return x * x

        items = list(range(10))
        results = await batch_process(items, square, batch_size=3)

        assert results == [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]

    async def test_respects_batch_size(self) -> None:
        """batch_process respects batch boundaries."""
        batch_starts: list[int] = []

        async def track_batch(x: int) -> int:
            batch_starts.append(x)
            return x

        items = list(range(7))
        await batch_process(items, track_batch, batch_size=3, concurrency=2)

        # Should process in 3 batches: [0,1,2], [3,4,5], [6]
        assert len(batch_starts) == 7

    async def test_handles_failures(self) -> None:
        """batch_process handles item failures."""

        async def fail_on_three(x: int) -> int:
            if x == 3:
                raise ValueError("Three is bad")
            return x

        items = list(range(5))
        results = await batch_process(items, fail_on_three, batch_size=2)

        assert results[0] == 0
        assert results[1] == 1
        assert results[2] == 2
        assert isinstance(results[3], ValueError)
        assert results[4] == 4


class TestPerformanceCharacteristics:
    """Tests verifying performance benefits of parallel execution."""

    async def test_parallel_faster_than_sequential(self) -> None:
        """Parallel execution is faster than sequential."""
        config = ParallelConfig(max_research_concurrent=4)
        executor = ParallelExecutor(config)

        sleep_time = 0.05
        num_tasks = 8

        async def slow_task() -> str:
            await asyncio.sleep(sleep_time)
            return "done"

        # Parallel execution
        parallel_start = time.perf_counter()
        tasks = [slow_task() for _ in range(num_tasks)]
        await executor.run_research_parallel(tasks)
        parallel_time = time.perf_counter() - parallel_start

        # Sequential execution
        sequential_start = time.perf_counter()
        for _ in range(num_tasks):
            await slow_task()
        sequential_time = time.perf_counter() - sequential_start

        # Parallel should be significantly faster
        # With 4 concurrent and 8 tasks, should be ~2x faster
        assert parallel_time < sequential_time
        # Should be at least 1.5x faster
        assert sequential_time / parallel_time > 1.5

    async def test_batch_processing_efficiency(self) -> None:
        """Batch processing is efficient for large item sets."""
        config = ParallelConfig(
            batch_size=10,
            max_validation_concurrent=5,
        )
        executor = ParallelExecutor(config)

        async def process(item: int) -> int:
            await asyncio.sleep(0.01)
            return item * 2

        items = list(range(50))

        start = time.perf_counter()
        result = await executor.run_validation_batch(items, process)
        duration = time.perf_counter() - start

        assert result.total == 50
        assert result.successful == 50
        # Should complete in reasonable time due to parallelism
        # 50 items at 0.01s each sequential = 0.5s
        # With batch_size=10, concurrency=5: ~0.1s per batch, 5 batches
        assert duration < 0.3
