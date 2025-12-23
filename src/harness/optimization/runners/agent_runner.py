"""Agent runner for single test case execution with tracing.

Executes individual test cases against an agent, collecting execution spans
and computing validation scores for optimization feedback.

Example usage:
    from harness.optimization.runners import AgentRunner, RunnerConfig
    from harness.optimization.testcases import TestSuiteLoader

    config = RunnerConfig(agent_name="python-expert")
    runner = AgentRunner(config)

    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")
    result = await runner.run_test_case(suite.test_cases[0])
    print(f"Score: {result.validation_score}")
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from harness.optimization.runners.base import BaseRunner, RunContext, RunnerConfig
from harness.optimization.testcases.models import SuiteResult, TestResult
from harness.optimization.testcases.validators import get_validator

if TYPE_CHECKING:
    from harness.optimization.adapters import AgentFeedback
    from harness.optimization.testcases import TestCase, TestSuite
    from harness.tracer import Span

logger = structlog.get_logger(__name__)


class AgentRunner(BaseRunner):
    """Runner for executing agents on test cases with full tracing.

    Integrates with the CGF tracing infrastructure to collect spans
    during agent execution, then transforms them to feedback.

    Key features:
    - Automatic span collection during execution
    - Validation score computation
    - Feedback extraction via adapters
    - Timeout handling
    - System prompt override for optimization
    """

    def __init__(self, config: RunnerConfig) -> None:
        """Initialize the agent runner.

        Args:
            config: Runner configuration including agent name,
                   permission mode, and tracing settings.
        """
        super().__init__(config)
        self._tracer = None
        self._store = None
        self._adapter = None

    def _get_tracer(self):
        """Lazily initialize the tracer."""
        if self._tracer is None:
            from harness.tracer import get_tracer

            self._tracer = get_tracer()
        return self._tracer

    def _get_store(self):
        """Lazily initialize the store."""
        if self._store is None:
            from harness.optimization.store import get_store

            self._store = get_store()
        return self._store

    def _get_adapter(self):
        """Lazily initialize the agent adapter."""
        if self._adapter is None:
            from harness.optimization.adapters import get_adapter

            self._adapter = get_adapter("agent")
        return self._adapter

    async def run_test_case(
        self,
        test_case: TestCase,
        system_prompt_override: str | None = None,
    ) -> TestResult:
        """Run a single test case against the configured agent.

        Args:
            test_case: The test case to execute.
            system_prompt_override: Optional system prompt to use instead
                of the agent's default prompt.

        Returns:
            TestResult with output, feedback, validation score, and metrics.
        """
        start_time = time.time()
        tracer = self._get_tracer() if self.config.collect_spans else None
        trace_id = None
        spans: list[Span] = []
        output = ""
        error_message = None
        feedback = None

        # Create run context
        context = RunContext(
            trace_id=tracer.generate_trace_id() if tracer else "",
            test_case_id=test_case.id,
            start_time=start_time,
            system_prompt=system_prompt_override,
        )

        logger.info(
            "Running test case",
            test_case_id=test_case.id,
            agent=self.config.agent_name,
            has_prompt_override=system_prompt_override is not None,
        )

        try:
            # Execute with timeout
            timeout = test_case.timeout_seconds or self.config.timeout_seconds
            output = await asyncio.wait_for(
                self._execute_agent(test_case, system_prompt_override, context),
                timeout=timeout,
            )

            # Collect spans if tracing enabled
            if tracer and context.trace_id:
                store = self._get_store()
                spans = store.get_trace_spans(context.trace_id)

                # Transform spans to feedback
                if spans:
                    adapter = self._get_adapter()
                    feedback = adapter.adapt(spans)

        except asyncio.TimeoutError:
            error_message = f"Test case timed out after {timeout}s"
            logger.warning(
                "Test case timeout",
                test_case_id=test_case.id,
                timeout=timeout,
            )
        except Exception as e:
            error_message = str(e)
            logger.error(
                "Test case execution failed",
                test_case_id=test_case.id,
                error=error_message,
            )

        # Compute validation score
        validation_score = 0.0
        if output and not error_message:
            try:
                validator = get_validator(test_case.validation)
                validation_score = await validator.validate(output)
            except Exception as e:
                logger.error(
                    "Validation failed",
                    test_case_id=test_case.id,
                    error=str(e),
                )

        # Calculate duration
        duration_seconds = time.time() - start_time
        execution_time_ms = duration_seconds * 1000

        result = TestResult(
            test_case_id=test_case.id,
            agent_name=self.config.agent_name,
            output=output,
            score=validation_score,
            feedback=feedback,
            execution_time_ms=execution_time_ms,
            success=error_message is None and validation_score >= 0.5,
            error=error_message,
            trace_id=context.trace_id if context.trace_id else "",
        )

        logger.info(
            "Test case completed",
            test_case_id=test_case.id,
            score=validation_score,
            duration=f"{duration_seconds:.2f}s",
            success=result.success,
        )

        return result

    async def _execute_agent(
        self,
        test_case: TestCase,
        system_prompt_override: str | None,
        context: RunContext,
    ) -> str:
        """Execute the agent on a test case prompt.

        Args:
            test_case: The test case to execute.
            system_prompt_override: Optional prompt override.
            context: The run context for tracing.

        Returns:
            The agent's text output.
        """
        from harness.direct_agent import call_agent_simple

        tracer = self._get_tracer() if self.config.collect_spans else None

        # Execute with tracing span
        if tracer:
            from harness.tracer import SpanKind

            async with tracer.async_span(
                "agent.evaluate",
                SpanKind.RESOURCE_EVALUATION,
            ) as span:
                span.set_attribute("agent.name", self.config.agent_name)
                span.set_attribute("test_case.id", test_case.id)
                span.set_attribute("trace.id", context.trace_id)

                output = await call_agent_simple(
                    agent_name=self.config.agent_name,
                    prompt=test_case.prompt,
                    permission_mode=self.config.permission_mode,
                    cwd=self.config.cwd,
                    verbose=self.config.verbose,
                    system_prompt_override=system_prompt_override,
                )

                span.set_attribute("output.length", len(output))
                return output
        else:
            # No tracing
            return await call_agent_simple(
                agent_name=self.config.agent_name,
                prompt=test_case.prompt,
                permission_mode=self.config.permission_mode,
                cwd=self.config.cwd,
                verbose=self.config.verbose,
                system_prompt_override=system_prompt_override,
            )

    async def run_suite(
        self,
        suite: TestSuite,
        system_prompt_override: str | None = None,
    ) -> SuiteResult:
        """Run all test cases in a suite sequentially.

        For parallel execution, use BatchRunner instead.

        Args:
            suite: The test suite to execute.
            system_prompt_override: Optional system prompt to use.

        Returns:
            SuiteResult with all test results and aggregated metrics.
        """
        self._validate_agent_name(suite)

        start_time = time.time()
        results: list[TestResult] = []

        logger.info(
            "Running test suite",
            suite_name=suite.name,
            test_count=len(suite.test_cases),
        )

        for test_case in suite.test_cases:
            result = await self.run_test_case(test_case, system_prompt_override)
            results.append(result)

        duration_seconds = time.time() - start_time

        suite_result = SuiteResult(
            suite_name=suite.name,
            agent_name=self.config.agent_name,
            results=results,
        )

        logger.info(
            "Test suite completed",
            suite_name=suite.name,
            passed=suite_result.passed_count,
            failed=suite_result.failed_count,
            average_score=suite_result.total_score,
            duration=f"{duration_seconds:.2f}s",
        )

        return suite_result
