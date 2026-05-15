"""Unit tests for F4 — per-resource phase parallelism.

Covers:

- ``_resolve_concurrency`` env-var parsing (default / override / invalid /
  negative) for all three phase modules.
- ``_state_lock`` serializes concurrent ``_save_state`` calls so the
  on-disk JSON file never sees a partial write.
- A single failing resource coroutine does not abort the gather batch
  (per-coroutine exception isolation).
- Semaphore caps the in-flight concurrent calls at the configured
  bound — N+1 resources cannot exceed N concurrent slots.
- The F4 helpers all access ``self._state_lock`` from the
  ``MultiResourceOrchestrator`` instance (not a class-level singleton).

These tests use small mock objects rather than the real EvalHarness /
context-engineer agent: F4 is a structural change, not a behavior
change, so we exercise the new dispatch shape directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness.optimization._orchestrator_phases import execution_eval as _ee
from harness.optimization._orchestrator_phases import generate as _gen
from harness.optimization._orchestrator_phases import iterate as _iter

# ---------------------------------------------------------------------------
# _resolve_concurrency — env-var parsing
# ---------------------------------------------------------------------------


class TestResolveConcurrency:
    """Each phase module ships its own _resolve_concurrency helper.

    They share semantics, so the same parametrized tests run against all
    three to catch a future drift where one module's helper picks up
    different parsing rules than another.
    """

    @pytest.mark.parametrize(
        "resolver",
        [_gen._resolve_concurrency, _iter._resolve_concurrency, _ee._resolve_concurrency],
    )
    def test_unset_returns_default(
        self, resolver: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CGF_TEST_KNOB", raising=False)
        assert resolver("CGF_TEST_KNOB", 7) == 7

    @pytest.mark.parametrize(
        "resolver",
        [_gen._resolve_concurrency, _iter._resolve_concurrency, _ee._resolve_concurrency],
    )
    def test_valid_integer_override(
        self, resolver: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_TEST_KNOB", "12")
        assert resolver("CGF_TEST_KNOB", 4) == 12

    @pytest.mark.parametrize(
        "resolver",
        [_gen._resolve_concurrency, _iter._resolve_concurrency, _ee._resolve_concurrency],
    )
    def test_invalid_value_falls_back_to_default(
        self, resolver: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_TEST_KNOB", "not-a-number")
        assert resolver("CGF_TEST_KNOB", 4) == 4

    @pytest.mark.parametrize(
        "resolver",
        [_gen._resolve_concurrency, _iter._resolve_concurrency, _ee._resolve_concurrency],
    )
    def test_zero_or_negative_clamps_to_one(
        self, resolver: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """0 or -1 is nonsense; the resolver clamps to a minimum of 1
        so the semaphore is always constructable.  Kill-switch is =1,
        not =0."""
        monkeypatch.setenv("CGF_TEST_KNOB", "0")
        assert resolver("CGF_TEST_KNOB", 4) == 1
        monkeypatch.setenv("CGF_TEST_KNOB", "-5")
        assert resolver("CGF_TEST_KNOB", 4) == 1

    @pytest.mark.parametrize(
        "resolver",
        [_gen._resolve_concurrency, _iter._resolve_concurrency, _ee._resolve_concurrency],
    )
    def test_empty_string_returns_default(
        self, resolver: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_TEST_KNOB", "")
        assert resolver("CGF_TEST_KNOB", 4) == 4


# ---------------------------------------------------------------------------
# _state_lock — concurrent-write serialization
# ---------------------------------------------------------------------------


class TestStateLock:
    """Verify the lock attribute is present and serializes contention.

    Goal: when 20 coroutines hit the lock in parallel, the critical
    section runs strictly one at a time.  We don't try to detect race
    conditions in the JSON file directly (those are timing-sensitive and
    flaky); instead we measure that the lock acquires/releases form a
    well-ordered sequence.
    """

    def test_orchestrator_init_creates_lock(self) -> None:
        from pathlib import Path

        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceConfig,
            MultiResourceOrchestrator,
        )

        config = MultiResourceConfig(workspace_dir=Path("/tmp"))
        orch = MultiResourceOrchestrator(config)
        assert hasattr(orch, "_state_lock")
        assert isinstance(orch._state_lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_lock_serializes_contending_coroutines(self) -> None:
        from pathlib import Path

        from harness.optimization.multi_resource_orchestrator import (
            MultiResourceConfig,
            MultiResourceOrchestrator,
        )

        config = MultiResourceConfig(workspace_dir=Path("/tmp"))
        orch = MultiResourceOrchestrator(config)

        in_critical = 0
        max_observed = 0
        order: list[int] = []

        async def worker(i: int) -> None:
            nonlocal in_critical, max_observed
            async with orch._state_lock:
                in_critical += 1
                max_observed = max(max_observed, in_critical)
                # Yield to give other coroutines a chance to violate the
                # invariant; the lock should prevent it.
                await asyncio.sleep(0)
                order.append(i)
                in_critical -= 1

        await asyncio.gather(*[worker(i) for i in range(20)])

        # Lock invariant: at most one coroutine inside the critical
        # section at any given time.
        assert max_observed == 1
        # Every worker eventually ran (no deadlock).
        assert len(order) == 20
        assert set(order) == set(range(20))


# ---------------------------------------------------------------------------
# Gather batch — exception isolation
# ---------------------------------------------------------------------------


class TestExceptionIsolation:
    """When one per-resource coroutine raises, the gather batch must
    still collect every other coroutine's result.  Tests use a stripped-
    down imitation of the gen/iterate/eval dispatch pattern."""

    @pytest.mark.asyncio
    async def test_one_failure_does_not_abort_batch(self) -> None:
        semaphore = asyncio.Semaphore(4)
        completed: list[int] = []

        async def good(i: int) -> int:
            async with semaphore:
                await asyncio.sleep(0)
                completed.append(i)
                return i

        async def bad() -> int:
            async with semaphore:
                raise RuntimeError("intentional")

        # Mix one bad call with several good ones.
        tasks = [good(0), good(1), bad(), good(2), good(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All five tasks ran; the bad one returned an Exception object.
        assert len(results) == 5
        assert len([r for r in results if isinstance(r, Exception)]) == 1
        # The four good ones still produced values.
        assert sorted(completed) == [0, 1, 2, 3]

    @pytest.mark.asyncio
    async def test_generate_bounded_wrapper_isolates_exceptions(self) -> None:
        """Smoke the actual generate._bounded shape with a stub orchestrator.

        We don't call ``delegate`` directly (it pulls in too much
        infra); instead we replicate the wrapper pattern to assert that
        a coroutine raising RuntimeError lands in the per-resource
        failure path rather than propagating up the gather.
        """
        semaphore = asyncio.Semaphore(2)
        failures: list[str] = []

        async def fake_single(name: str) -> None:
            if name == "bad":
                raise RuntimeError("boom")
            await asyncio.sleep(0)

        async def bounded(name: str) -> None:
            async with semaphore:
                try:
                    await fake_single(name)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{name}: {exc}")

        await asyncio.gather(*[bounded(n) for n in ["a", "bad", "c"]])
        assert failures == ["bad: boom"]


# ---------------------------------------------------------------------------
# Semaphore — concurrency cap
# ---------------------------------------------------------------------------


class TestSemaphoreCap:
    """The semaphore must cap in-flight calls.  This is the headline
    F4 guarantee: 18 resources cannot fire 18 simultaneous API calls."""

    @pytest.mark.asyncio
    async def test_semaphore_bounds_concurrent_calls(self) -> None:
        bound = 3
        sem = asyncio.Semaphore(bound)
        in_flight = 0
        peak = 0

        async def worker() -> None:
            nonlocal in_flight, peak
            async with sem:
                in_flight += 1
                peak = max(peak, in_flight)
                # Hold the slot briefly so other workers genuinely
                # contend for it.
                await asyncio.sleep(0.01)
                in_flight -= 1

        await asyncio.gather(*[worker() for _ in range(12)])
        assert peak <= bound, f"peak={peak} exceeded bound={bound}"
        # Sanity: more than one worker actually ran at once (if peak == 1
        # we'd be testing pure serial code by accident).
        assert peak >= 2

    @pytest.mark.asyncio
    async def test_concurrency_one_serializes(self) -> None:
        """CGF_*_CONCURRENCY=1 is documented as the kill-switch back to
        sequential.  Verify the semaphore shape honors that."""
        sem = asyncio.Semaphore(1)
        in_flight = 0
        peak = 0

        async def worker() -> None:
            nonlocal in_flight, peak
            async with sem:
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1

        await asyncio.gather(*[worker() for _ in range(8)])
        assert peak == 1


# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------


class TestDefaults:
    """Pin the documented defaults (F18: generate=8, iterate=4, eval=4)."""

    def test_generate_default_is_eight(self) -> None:
        """F18: raised from 4 to 8 — per-resource generate is I/O-bound
        on the SDK API; 4-way left half the slots idle in run #5."""
        assert _gen.DEFAULT_GENERATE_CONCURRENCY == 8

    def test_iterate_default_is_four(self) -> None:
        assert _iter.DEFAULT_ITERATE_CONCURRENCY == 4

    def test_execution_eval_default_is_four(self) -> None:
        """F18: raised from 2 to 4 — eval is I/O-bound on the judge
        API, and 2-way left ~6 scenario slots idle in run #5i."""
        assert _ee.DEFAULT_EXECUTION_EVAL_CONCURRENCY == 4
