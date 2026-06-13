"""Unit tests for F12 — scenario parallelism inside EvalHarness.run.

Before F12, ``EvalHarness.run`` iterated scenarios strictly
sequentially: ``for scenario in suite.scenarios: await self.run_scenario(...)``.
54 scenarios × ~30s SDK call = 27 min per arm per resource.  At
``CGF_EXECUTION_EVAL_CONCURRENCY=2`` and 18 resources, that's ~8 hours.

F12 wraps the scenario loop in ``asyncio.gather`` under a semaphore.
Default concurrency 6 cuts wall time ~6×.  Additionally, the two arms
within each scenario now run concurrently (free 2x since they're
independent SDK calls).
"""

from __future__ import annotations

import asyncio

import pytest

from harness.optimization.eval_harness import runner as runner_module
from harness.optimization.eval_harness.runner import (
    DEFAULT_EVAL_SCENARIO_CONCURRENCY,
    _resolve_scenario_concurrency,
)


class TestResolveScenarioConcurrency:
    """The env-var resolver follows the same shape as the F4 resolvers."""

    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(
            "CGF_EVAL_SCENARIO_CONCURRENCY", raising=False
        )
        assert _resolve_scenario_concurrency() == 6
        assert DEFAULT_EVAL_SCENARIO_CONCURRENCY == 6

    def test_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CGF_EVAL_SCENARIO_CONCURRENCY", "12")
        assert _resolve_scenario_concurrency() == 12

    def test_kill_switch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting concurrency=1 restores strict-sequential behavior
        (useful for rate-limit debugging)."""
        monkeypatch.setenv("CGF_EVAL_SCENARIO_CONCURRENCY", "1")
        assert _resolve_scenario_concurrency() == 1

    def test_zero_clamps_to_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """0 or negative is nonsense — clamp to 1 (semaphore needs ≥1)."""
        monkeypatch.setenv("CGF_EVAL_SCENARIO_CONCURRENCY", "0")
        assert _resolve_scenario_concurrency() == 1

    def test_invalid_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "CGF_EVAL_SCENARIO_CONCURRENCY", "not-a-number"
        )
        assert _resolve_scenario_concurrency() == 6

    def test_empty_string_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CGF_EVAL_SCENARIO_CONCURRENCY", "")
        assert _resolve_scenario_concurrency() == 6


# ---------------------------------------------------------------------------
# Inter-scenario fan-out — gather + semaphore behavior
# ---------------------------------------------------------------------------


class TestScenarioParallelism:
    """The F12 contract: scenarios run concurrently but bounded.

    These tests use the same pattern as F4's concurrency tests —
    structural smokes that don't require the real SDK."""

    @pytest.mark.asyncio
    async def test_semaphore_bounds_concurrent_scenarios(self) -> None:
        bound = 4
        sem = asyncio.Semaphore(bound)
        in_flight = 0
        peak = 0

        async def fake_scenario() -> None:
            nonlocal in_flight, peak
            async with sem:
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1

        await asyncio.gather(*[fake_scenario() for _ in range(20)])
        assert peak <= bound
        assert peak >= 2  # actually parallel, not accidentally serial

    @pytest.mark.asyncio
    async def test_gather_preserves_order(self) -> None:
        """asyncio.gather returns results in input order, regardless of
        completion order.  Downstream aggregation (by_level / by_tag)
        depends on this for deterministic reports."""
        delays = [0.05, 0.01, 0.03, 0.02, 0.04]

        async def make_result(idx: int, delay: float) -> int:
            await asyncio.sleep(delay)
            return idx

        results = await asyncio.gather(
            *[make_result(i, d) for i, d in enumerate(delays)]
        )
        assert results == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Arm parallelism — baseline + candidate run concurrently
# ---------------------------------------------------------------------------


class TestArmParallelism:
    """``run_scenario`` now runs baseline and candidate arms in parallel.

    This is a free 2x — the arms are independent SDK calls and the
    only thing they share is the read-only scenario definition.
    """

    @pytest.mark.asyncio
    async def test_arms_run_concurrently(self) -> None:
        """Both arms in flight at the same time, not serial."""
        baseline_started = asyncio.Event()
        candidate_started = asyncio.Event()
        both_in_flight = False

        async def baseline_arm() -> str:
            nonlocal both_in_flight
            baseline_started.set()
            await asyncio.wait_for(candidate_started.wait(), timeout=1)
            both_in_flight = True
            return "baseline"

        async def candidate_arm() -> str:
            nonlocal both_in_flight
            candidate_started.set()
            await asyncio.wait_for(baseline_started.wait(), timeout=1)
            both_in_flight = True
            return "candidate"

        b, c = await asyncio.gather(baseline_arm(), candidate_arm())
        assert both_in_flight
        assert b == "baseline"
        assert c == "candidate"


# ---------------------------------------------------------------------------
# Source-inspection: F12 wired into runner.run + run_scenario
# ---------------------------------------------------------------------------


class TestRunnerSourceContract:
    """Pin the structural invariant — F12 must remain wired into the
    actual code, not just defined as a helper."""

    def test_run_uses_gather_with_semaphore(self) -> None:
        import inspect

        src = inspect.getsource(runner_module.EvalHarness.run)
        assert "asyncio.gather" in src, (
            "F12 regression: EvalHarness.run lost gather"
        )
        assert "Semaphore" in src, (
            "F12 regression: EvalHarness.run lost semaphore"
        )
        assert "_resolve_scenario_concurrency" in src, (
            "F12 regression: env-var concurrency knob not wired"
        )

    def test_run_scenario_parallelizes_arms(self) -> None:
        import inspect

        src = inspect.getsource(runner_module.EvalHarness.run_scenario)
        assert "asyncio.gather" in src, (
            "F12 regression: run_scenario lost arm-parallelism"
        )
