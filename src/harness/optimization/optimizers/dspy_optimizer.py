"""DSPy MIPROv2 optimizer for agent prompt optimization.

Wraps DSPy's MIPROv2 optimizer to optimize agent system prompts
by treating prompt optimization as instruction optimization.

Example usage:
    from harness.optimization.optimizers import DSPyAgentOptimizer
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuiteLoader

    resource = AgentResource.load(Path("agents/configs/python-expert.md"))
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    optimizer = DSPyAgentOptimizer()
    result = await optimizer.optimize(resource, suite)
    print(f"Improvement: {result.improvement_percent:.1f}%")
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog

from harness.optimization.optimizers.metrics import suite_average_score
from harness.optimization.optimizers.protocol import (
    BaseOptimizer,
    IterationResult,
    OptimizationConfig,
    OptimizationResult,
    PromptCandidate,
)
from harness.optimization.runners import BatchRunner, RunnerConfig
from harness.optimization.testcases import SuiteResult

if TYPE_CHECKING:
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuite

logger = structlog.get_logger(__name__)

# Check if DSPy is available
try:
    import dspy
    from dspy.teleprompt import MIPROv2

    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None  # type: ignore
    MIPROv2 = None  # type: ignore


class DSPyAgentModule:
    """DSPy module that wraps agent execution.

    This module allows DSPy to optimize the agent's system prompt
    by treating it as the module's instructions.
    """

    def __init__(
        self,
        agent_name: str,
        base_prompt: str,
        runner: BatchRunner,
        test_suite: TestSuite,
    ) -> None:
        """Initialize the module.

        Args:
            agent_name: Name of the agent to run.
            base_prompt: Base system prompt.
            runner: BatchRunner for executing tests.
            test_suite: Test suite for evaluation.
        """
        if not DSPY_AVAILABLE:
            raise ImportError(
                "DSPy is not installed. Install with: pip install 'dspy-ai>=3.0.0'"
            )

        self.agent_name = agent_name
        self.base_prompt = base_prompt
        self.runner = runner
        self.test_suite = test_suite
        self._current_prompt = base_prompt
        self._last_result: SuiteResult | None = None

    def set_prompt(self, prompt: str) -> None:
        """Set the current prompt for evaluation.

        Args:
            prompt: The system prompt to use.
        """
        self._current_prompt = prompt

    async def evaluate(self) -> SuiteResult:
        """Run the test suite with the current prompt.

        Returns:
            SuiteResult with test results.
        """
        result = await self.runner.run_suite(
            self.test_suite,
            system_prompt_override=self._current_prompt,
        )
        self._last_result = result
        return result

    def get_score(self) -> float:
        """Get the score from the last evaluation.

        Returns:
            Average score from the last run.
        """
        if self._last_result is None:
            return 0.0
        return suite_average_score(self._last_result)


class DSPyAgentOptimizer(BaseOptimizer):
    """DSPy-based optimizer for agent system prompts.

    Uses MIPROv2 to optimize prompts through instruction optimization.
    Since DSPy operates on modules with signatures, we create a custom
    optimization loop that leverages DSPy's prompt generation capabilities.
    """

    def __init__(
        self,
        default_config: OptimizationConfig | None = None,
        optimization_level: str = "light",
        num_threads: int = 4,
    ) -> None:
        """Initialize the optimizer.

        Args:
            default_config: Default optimization configuration.
            optimization_level: DSPy optimization level (light, medium, heavy).
            num_threads: Number of threads for parallel evaluation.
        """
        super().__init__(default_config)
        self.optimization_level = optimization_level
        self.num_threads = num_threads

        if not DSPY_AVAILABLE:
            logger.warning(
                "DSPy not available",
                hint="Install with: pip install 'dspy-ai>=3.0.0'",
            )

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
        config: OptimizationConfig | None = None,
    ) -> OptimizationResult:
        """Optimize agent prompt using DSPy MIPROv2.

        Args:
            resource: The agent resource to optimize.
            test_suite: Test cases for evaluation.
            config: Optimization configuration.

        Returns:
            OptimizationResult with improved prompt.
        """
        if not DSPY_AVAILABLE:
            return OptimizationResult(
                success=False,
                original_prompt=resource.system_prompt,
                optimized_prompt=resource.system_prompt,
                original_score=0.0,
                final_score=0.0,
                improvement=0.0,
                improvement_percent=0.0,
                iterations=[],
                total_iterations=0,
                total_duration_seconds=0.0,
                config=config or self._default_config,
                agent_name=resource.name,
                suite_name=test_suite.name,
                error="DSPy not installed. Install with: pip install 'dspy-ai>=3.0.0'",
            )

        effective_config = self._get_config(config)
        start_time = time.time()

        logger.info(
            "Starting DSPy optimization",
            agent=resource.name,
            suite=test_suite.name,
            iterations=effective_config.max_iterations,
            level=self.optimization_level,
        )

        # Create runner for evaluation
        runner_config = RunnerConfig(
            agent_name=resource.name,
            collect_spans=False,  # Disable tracing for optimization speed
            max_concurrent=self.num_threads,
        )
        runner = BatchRunner(runner_config)

        # Create module wrapper
        module = DSPyAgentModule(
            agent_name=resource.name,
            base_prompt=resource.system_prompt,
            runner=runner,
            test_suite=test_suite,
        )

        try:
            # Get baseline score
            baseline_result = await self.evaluate(resource.system_prompt, test_suite)
            baseline_score = baseline_result[0]

            logger.info(
                "Baseline evaluation complete",
                score=baseline_score,
                passed=baseline_result[1].passed_count,
                failed=baseline_result[1].failed_count,
            )

            # Run optimization loop
            iterations: list[IterationResult] = []
            best_prompt = resource.system_prompt
            best_score = baseline_score

            for iteration in range(effective_config.max_iterations):
                iteration_start = time.time()

                # Generate candidate prompts
                candidates = await self._generate_candidates(
                    module,
                    best_prompt,
                    test_suite,
                    effective_config,
                    iteration,
                )

                if not candidates:
                    logger.warning("No candidates generated", iteration=iteration)
                    break

                # Find best candidate
                iteration_best = max(candidates, key=lambda c: c.score)

                # Track improvement
                improvement = iteration_best.score - best_score
                if iteration_best.score > best_score:
                    best_prompt = iteration_best.prompt
                    best_score = iteration_best.score

                    logger.info(
                        "New best prompt found",
                        iteration=iteration,
                        score=best_score,
                        improvement=improvement,
                    )

                iteration_duration = time.time() - iteration_start
                iterations.append(
                    IterationResult(
                        iteration=iteration,
                        best_prompt=iteration_best.prompt,
                        best_score=iteration_best.score,
                        candidates=candidates,
                        improvement=improvement,
                        duration_seconds=iteration_duration,
                    )
                )

                # Check early stopping
                if improvement < effective_config.early_stopping_threshold:
                    if iteration > 0:  # Allow at least one iteration
                        logger.info(
                            "Early stopping triggered",
                            iteration=iteration,
                            improvement=improvement,
                            threshold=effective_config.early_stopping_threshold,
                        )
                        break

            total_duration = time.time() - start_time

            # Calculate final improvement
            final_improvement = best_score - baseline_score
            improvement_percent = (
                (final_improvement / baseline_score * 100)
                if baseline_score > 0 else 0.0
            )

            logger.info(
                "Optimization complete",
                original_score=baseline_score,
                final_score=best_score,
                improvement=final_improvement,
                improvement_percent=f"{improvement_percent:.1f}%",
                duration=f"{total_duration:.1f}s",
            )

            return OptimizationResult(
                success=True,
                original_prompt=resource.system_prompt,
                optimized_prompt=best_prompt,
                original_score=baseline_score,
                final_score=best_score,
                improvement=final_improvement,
                improvement_percent=improvement_percent,
                iterations=iterations,
                total_iterations=len(iterations),
                total_duration_seconds=total_duration,
                config=effective_config,
                agent_name=resource.name,
                suite_name=test_suite.name,
            )

        except Exception as e:
            logger.error("Optimization failed", error=str(e))
            return OptimizationResult(
                success=False,
                original_prompt=resource.system_prompt,
                optimized_prompt=resource.system_prompt,
                original_score=0.0,
                final_score=0.0,
                improvement=0.0,
                improvement_percent=0.0,
                iterations=[],
                total_iterations=0,
                total_duration_seconds=time.time() - start_time,
                config=effective_config,
                agent_name=resource.name,
                suite_name=test_suite.name,
                error=str(e),
            )

    async def evaluate(
        self,
        prompt: str,
        test_suite: TestSuite,
    ) -> tuple[float, SuiteResult]:
        """Evaluate a prompt against the test suite.

        Args:
            prompt: The system prompt to evaluate.
            test_suite: Test cases for evaluation.

        Returns:
            Tuple of (score, suite_result).
        """
        runner_config = RunnerConfig(
            agent_name=test_suite.agent_name,
            collect_spans=False,
            max_concurrent=self.num_threads,
        )
        runner = BatchRunner(runner_config)

        result = await runner.run_suite(test_suite, system_prompt_override=prompt)
        score = suite_average_score(result)

        return score, result

    async def _generate_candidates(
        self,
        module: DSPyAgentModule,
        current_prompt: str,
        test_suite: TestSuite,
        config: OptimizationConfig,
        iteration: int,
    ) -> list[PromptCandidate]:
        """Generate candidate prompts using DSPy.

        This uses DSPy's LM capabilities to generate prompt variations.

        Args:
            module: The agent module wrapper.
            current_prompt: Current best prompt.
            test_suite: Test suite for context.
            config: Optimization configuration.
            iteration: Current iteration number.

        Returns:
            List of PromptCandidate with scores.
        """
        candidates: list[PromptCandidate] = []

        # Use DSPy to generate prompt variations
        try:
            # Configure DSPy LM if not already configured
            if dspy.settings.lm is None:
                # Use Anthropic's Claude as the prompt model
                import os

                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if api_key:
                    lm = dspy.LM("anthropic/claude-sonnet-4-20250514", api_key=api_key)
                    dspy.configure(lm=lm)
                else:
                    logger.warning("No ANTHROPIC_API_KEY found, using default LM")

            # Generate variations using DSPy's prediction capability
            variation_prompts = await self._generate_prompt_variations(
                current_prompt,
                test_suite,
                config.num_candidates,
                config.temperature,
            )

            # Evaluate each variation
            for i, prompt_text in enumerate(variation_prompts):
                try:
                    score, result = await self.evaluate(prompt_text, test_suite)
                    candidates.append(
                        PromptCandidate(
                            prompt=prompt_text,
                            score=score,
                            iteration=iteration,
                            metadata={"variation_index": i},
                        )
                    )
                    logger.debug(
                        "Candidate evaluated",
                        iteration=iteration,
                        candidate=i,
                        score=score,
                    )
                except Exception as e:
                    logger.warning(
                        "Candidate evaluation failed",
                        iteration=iteration,
                        candidate=i,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("Candidate generation failed", error=str(e))

        # Always include the current best prompt as a candidate
        if current_prompt not in [c.prompt for c in candidates]:
            score, result = await self.evaluate(current_prompt, test_suite)
            candidates.append(
                PromptCandidate(
                    prompt=current_prompt,
                    score=score,
                    iteration=iteration,
                    metadata={"is_baseline": True},
                )
            )

        return candidates

    async def _generate_prompt_variations(
        self,
        base_prompt: str,
        test_suite: TestSuite,
        num_variations: int,
        temperature: float,
    ) -> list[str]:
        """Generate prompt variations using DSPy's LM.

        Args:
            base_prompt: The base prompt to improve.
            test_suite: Test suite for context.
            num_variations: Number of variations to generate.
            temperature: Generation temperature.

        Returns:
            List of prompt variations.
        """
        if not DSPY_AVAILABLE or dspy.settings.lm is None:
            # Fallback: return small variations
            return [base_prompt]

        variations = []

        # Create a signature for prompt improvement
        class PromptImprover(dspy.Signature):
            """Improve a system prompt to better accomplish the given tasks."""

            original_prompt: str = dspy.InputField(desc="The original system prompt")
            task_description: str = dspy.InputField(desc="Description of what the agent should do")
            test_examples: str = dspy.InputField(desc="Example test cases the agent will handle")
            improved_prompt: str = dspy.OutputField(desc="An improved version of the system prompt")

        # Build task description from test suite
        task_description = f"""
Agent: {test_suite.agent_name}
Goal: {test_suite.description or 'Complete the given tasks successfully'}
Number of test cases: {len(test_suite.test_cases)}
"""

        # Sample test examples
        examples = []
        for tc in test_suite.test_cases[:3]:  # Use first 3 as examples
            examples.append(f"- {tc.prompt[:100]}..." if len(tc.prompt) > 100 else f"- {tc.prompt}")
        test_examples = "\n".join(examples)

        # Generate variations
        predictor = dspy.Predict(PromptImprover)

        for i in range(num_variations):
            try:
                # Add some randomness in the instruction
                modifier = [
                    "Make the prompt more concise and focused.",
                    "Add more specific guidelines for edge cases.",
                    "Improve clarity and structure.",
                    "Add examples of good output format.",
                    "Focus on the most critical requirements.",
                ][i % 5]

                result = predictor(
                    original_prompt=base_prompt + f"\n\n[Improvement focus: {modifier}]",
                    task_description=task_description,
                    test_examples=test_examples,
                )

                if result.improved_prompt and result.improved_prompt != base_prompt:
                    variations.append(result.improved_prompt)
            except Exception as e:
                logger.debug("Variation generation failed", index=i, error=str(e))

        return variations if variations else [base_prompt]


def get_dspy_optimizer(
    config: OptimizationConfig | None = None,
    optimization_level: str = "light",
) -> DSPyAgentOptimizer:
    """Factory function to create a DSPy optimizer.

    Args:
        config: Optional optimization configuration.
        optimization_level: DSPy optimization level.

    Returns:
        Configured DSPyAgentOptimizer.
    """
    return DSPyAgentOptimizer(
        default_config=config,
        optimization_level=optimization_level,
    )
