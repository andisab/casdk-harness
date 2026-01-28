"""DSPy MIPROv2 optimizer for agent prompt optimization.

Leverages DSPy's MIPROv2 teleprompter for Bayesian optimization of prompts,
including instruction optimization and few-shot example selection.

This optimizer is more efficient than the custom DSPy wrapper because it uses:
- Tree-structured Parzen Estimator (TPE) for hyperparameter search
- Few-shot example optimization from training data
- Demo bootstrapping for better instruction generation

Example usage:
    from harness.optimization.optimizers import MIPROv2AgentOptimizer
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuiteLoader

    resource = AgentResource.load(Path("agents/configs/python-expert.md"))
    suite = TestSuiteLoader.load("tests/optimization/tests.yaml")

    optimizer = MIPROv2AgentOptimizer()
    result = await optimizer.optimize(resource, suite)
    print(f"Improvement: {result.improvement_percent:.1f}%")
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from harness.optimization.optimizers.dspy_metrics import (
    TestSuiteMetric,
    create_trainset_from_suite,
)
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

    MIPRO_AVAILABLE = True
except ImportError:
    MIPRO_AVAILABLE = False
    dspy = None  # type: ignore
    MIPROv2 = None  # type: ignore


@dataclass
class MIPROv2Config:
    """Configuration specific to MIPROv2 optimizer.

    Attributes:
        num_candidates: Number of instruction candidates to generate.
        init_temperature: Initial temperature for sampling.
        num_threads: Number of threads for parallel evaluation.
        max_bootstrapped_demos: Max bootstrapped demonstrations.
        max_labeled_demos: Max labeled demonstrations to use.
        verbose: Enable verbose output.
    """

    num_candidates: int = 7
    init_temperature: float = 1.0
    num_threads: int = 4
    max_bootstrapped_demos: int = 3
    max_labeled_demos: int = 5
    verbose: bool = False


class AgentTaskSignature(dspy.Signature if MIPRO_AVAILABLE else object):
    """Signature for agent task execution.

    MIPROv2 optimizes the instructions field of this signature,
    which becomes the system prompt guidance for the agent.
    """

    task: str = dspy.InputField(
        desc="The task or prompt for the agent to handle"
    ) if MIPRO_AVAILABLE else ""
    solution: str = dspy.OutputField(
        desc="The agent's response following system prompt guidelines"
    ) if MIPRO_AVAILABLE else ""


class PromptOptimizerModule(dspy.Module if MIPRO_AVAILABLE else object):
    """DSPy module that wraps prompt-based evaluation.

    This module is designed to be optimized by MIPROv2. It takes
    a task prompt and produces output that can be validated.

    MIPROv2 optimization flow:
    1. Bootstrapping: Collect successful traces for few-shot examples
    2. Grounded proposal: Draft instructions from task data
    3. Discrete search: Bayesian TPE optimization
    """

    def __init__(
        self,
        system_prompt: str,
        agent_description: str = "",
    ) -> None:
        """Initialize with system prompt.

        Args:
            system_prompt: The system prompt to use for generation.
            agent_description: Description of what the agent should do.
        """
        if not MIPRO_AVAILABLE:
            raise ImportError("DSPy not installed")

        super().__init__()
        self.system_prompt = system_prompt
        self.agent_description = agent_description

        # Use ChainOfThought for reasoning-heavy tasks
        self.solver = dspy.ChainOfThought(AgentTaskSignature)

        # Set initial instructions from system prompt summary
        if hasattr(self.solver, 'signature') and self.system_prompt:
            # Extract key guidance from system prompt for instructions
            instructions = self._extract_instructions(system_prompt)
            self.solver.signature = self.solver.signature.with_instructions(
                instructions
            )

    def _extract_instructions(self, prompt: str) -> str:
        """Extract key instructions from system prompt.

        Takes the first meaningful section as instructions for the
        signature, allowing MIPROv2 to optimize it.

        Args:
            prompt: Full system prompt.

        Returns:
            Extracted instruction string.
        """
        # Take first 500 chars or first major section
        lines = prompt.strip().split('\n')
        instruction_lines = []
        char_count = 0

        for line in lines:
            if char_count > 500:
                break
            if line.startswith('#') and len(instruction_lines) > 3:
                # Stop at next major section
                break
            instruction_lines.append(line)
            char_count += len(line)

        return '\n'.join(instruction_lines)

    def forward(self, task: str) -> dspy.Prediction:
        """Execute the module with the given task.

        Args:
            task: The task prompt to solve.

        Returns:
            DSPy Prediction with solution.
        """
        return self.solver(task=task)


class MIPROv2AgentOptimizer(BaseOptimizer):
    """MIPROv2-based optimizer for agent system prompts.

    Uses DSPy's MIPROv2 teleprompter which implements:
    - Bayesian optimization with TPE
    - Instruction optimization
    - Few-shot example optimization
    - Demo bootstrapping

    This is more efficient than the custom DSPy optimizer because
    it uses principled search rather than random exploration.
    """

    def __init__(
        self,
        default_config: OptimizationConfig | None = None,
        mipro_config: MIPROv2Config | None = None,
    ) -> None:
        """Initialize the optimizer.

        Args:
            default_config: Default optimization configuration.
            mipro_config: MIPROv2-specific configuration.
        """
        super().__init__(default_config)
        self.mipro_config = mipro_config or MIPROv2Config()
        self._eval_model: str | None = None  # Set during optimize()

        if not MIPRO_AVAILABLE:
            logger.warning(
                "DSPy/MIPROv2 not available",
                hint="Install with: pip install 'dspy-ai>=3.0.0'",
            )

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
        config: OptimizationConfig | None = None,
    ) -> OptimizationResult:
        """Optimize agent prompt using MIPROv2.

        Args:
            resource: The agent resource to optimize.
            test_suite: Test cases for evaluation.
            config: Optimization configuration.

        Returns:
            OptimizationResult with improved prompt.
        """
        if not MIPRO_AVAILABLE:
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
                error="MIPROv2 not installed. pip install 'dspy-ai>=3.0.0'",
            )

        effective_config = self._get_config(config)
        self._eval_model = effective_config.eval_model  # Store for evaluate()
        start_time = time.time()

        logger.info(
            "Starting MIPROv2 optimization",
            agent=resource.name,
            suite=test_suite.name,
            iterations=effective_config.max_iterations,
            candidates=self.mipro_config.num_candidates,
        )

        try:
            # Configure DSPy LM
            self._configure_dspy_lm()

            # Create trainset from test suite
            trainset = self._convert_to_trainset(test_suite)

            logger.info(
                "Created trainset",
                examples=len(trainset),
            )

            # Get baseline score
            baseline_score, baseline_result = await self._evaluate_prompt(
                resource.system_prompt, test_suite
            )

            logger.info(
                "Baseline evaluation complete",
                score=baseline_score,
                passed=baseline_result.passed_count,
                failed=baseline_result.failed_count,
            )

            # Create base module
            base_module = PromptOptimizerModule(resource.system_prompt)

            # Create metric function
            metric = self._create_metric(test_suite, resource)

            # Run MIPROv2 optimization
            optimized_prompt, iterations = await self._run_mipro_optimization(
                base_module=base_module,
                trainset=trainset,
                metric=metric,
                effective_config=effective_config,
                resource=resource,
                test_suite=test_suite,
            )

            # Evaluate final result
            final_score, _ = await self._evaluate_prompt(
                optimized_prompt, test_suite
            )

            total_duration = time.time() - start_time

            # Calculate improvement
            improvement = final_score - baseline_score
            improvement_percent = (
                (improvement / baseline_score * 100)
                if baseline_score > 0 else 0.0
            )

            logger.info(
                "MIPROv2 optimization complete",
                original_score=baseline_score,
                final_score=final_score,
                improvement=improvement,
                improvement_percent=f"{improvement_percent:.1f}%",
                duration=f"{total_duration:.1f}s",
            )

            return OptimizationResult(
                success=True,
                original_prompt=resource.system_prompt,
                optimized_prompt=optimized_prompt,
                original_score=baseline_score,
                final_score=final_score,
                improvement=improvement,
                improvement_percent=improvement_percent,
                iterations=iterations,
                total_iterations=len(iterations),
                total_duration_seconds=total_duration,
                config=effective_config,
                agent_name=resource.name,
                suite_name=test_suite.name,
            )

        except Exception as e:
            logger.error("MIPROv2 optimization failed", error=str(e))
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

    def _configure_dspy_lm(self) -> None:
        """Configure DSPy's language model."""
        if dspy.settings.lm is not None:
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            lm = dspy.LM("anthropic/claude-sonnet-4-20250514", api_key=api_key)
            dspy.configure(lm=lm)
            logger.info("Configured DSPy with Claude Sonnet")
        else:
            logger.warning("No ANTHROPIC_API_KEY found for DSPy")

    def _convert_to_trainset(
        self, test_suite: TestSuite
    ) -> list[dspy.Example]:
        """Convert test suite to DSPy trainset.

        Uses the centralized create_trainset_from_suite helper which
        properly formats test cases as DSPy Examples.

        Args:
            test_suite: Test suite with test cases.

        Returns:
            List of DSPy Examples for training.
        """
        return create_trainset_from_suite(test_suite, include_expected=True)

    def _create_metric(
        self,
        test_suite: TestSuite,
        resource: AgentResource,
    ) -> TestSuiteMetric:
        """Create metric function for MIPROv2.

        Uses TestSuiteMetric to bridge CGF validators to DSPy metrics.
        This provides proper validation using our test infrastructure.

        Args:
            test_suite: Test suite for validation lookup.
            resource: Agent resource for context.

        Returns:
            TestSuiteMetric compatible with MIPROv2.
        """
        return TestSuiteMetric(
            test_suite=test_suite,
            resource=resource,
            pass_threshold=0.5,
            cache_validators=True,
        )

    async def _run_mipro_optimization(
        self,
        base_module: PromptOptimizerModule,
        trainset: list[dspy.Example],
        metric: TestSuiteMetric,
        effective_config: OptimizationConfig,
        resource: AgentResource,
        test_suite: TestSuite,
    ) -> tuple[str, list[IterationResult]]:
        """Run the MIPROv2 optimization loop.

        Args:
            base_module: Base DSPy module to optimize.
            trainset: Training examples.
            metric: TestSuiteMetric for validation.
            effective_config: Optimization configuration.
            resource: Agent resource.
            test_suite: Test suite for evaluation.

        Returns:
            Tuple of (optimized_prompt, iteration_results).
        """
        iterations: list[IterationResult] = []
        best_prompt = resource.system_prompt
        best_score = 0.0

        # Create MIPROv2 teleprompter
        teleprompter = MIPROv2(
            metric=metric,
            num_candidates=self.mipro_config.num_candidates,
            init_temperature=self.mipro_config.init_temperature,
            verbose=self.mipro_config.verbose,
            num_threads=self.mipro_config.num_threads,
            max_bootstrapped_demos=self.mipro_config.max_bootstrapped_demos,
            max_labeled_demos=self.mipro_config.max_labeled_demos,
        )

        # Run optimization in iterations
        for iteration in range(effective_config.max_iterations):
            iteration_start = time.time()

            logger.info(
                "MIPROv2 iteration",
                iteration=iteration + 1,
                max_iterations=effective_config.max_iterations,
            )

            try:
                # MIPROv2 compile is synchronous, run in executor
                loop = asyncio.get_event_loop()
                optimized_module = await loop.run_in_executor(
                    None,
                    lambda: teleprompter.compile(
                        base_module,
                        trainset=trainset,
                        num_batches=1,  # One batch per iteration
                        requires_permission_to_run=False,
                    ),
                )

                # Extract optimized prompt from module
                # MIPROv2 optimizes the signature's instructions
                optimized_prompt = self._extract_optimized_prompt(
                    optimized_module, resource.system_prompt
                )

                # Evaluate the optimized prompt
                score, _ = await self._evaluate_prompt(
                    optimized_prompt, test_suite
                )

                # Track candidates
                candidates = [
                    PromptCandidate(
                        prompt=optimized_prompt,
                        score=score,
                        iteration=iteration,
                        metadata={"source": "mipro_v2"},
                    )
                ]

                # Update best if improved
                improvement = score - best_score
                if score > best_score:
                    best_prompt = optimized_prompt
                    best_score = score

                iteration_duration = time.time() - iteration_start

                iterations.append(
                    IterationResult(
                        iteration=iteration,
                        best_prompt=best_prompt,
                        best_score=best_score,
                        candidates=candidates,
                        improvement=improvement,
                        duration_seconds=iteration_duration,
                    )
                )

                logger.info(
                    "MIPROv2 iteration complete",
                    iteration=iteration + 1,
                    score=score,
                    best_score=best_score,
                    duration=f"{iteration_duration:.1f}s",
                )

                # Early stopping
                if improvement < effective_config.early_stopping_threshold:
                    if iteration > 0:
                        threshold = effective_config.early_stopping_threshold
                        logger.info(
                            "Early stopping",
                            improvement=improvement,
                            threshold=threshold,
                        )
                        break

            except Exception as e:
                logger.error(
                    "MIPROv2 iteration failed",
                    iteration=iteration + 1,
                    error=str(e),
                )
                iterations.append(
                    IterationResult(
                        iteration=iteration,
                        best_prompt=best_prompt,
                        best_score=best_score,
                        candidates=[],
                        improvement=0.0,
                        duration_seconds=time.time() - iteration_start,
                    )
                )

        return best_prompt, iterations

    def _extract_optimized_prompt(
        self,
        optimized_module: Any,
        original_prompt: str,
    ) -> str:
        """Extract the optimized prompt from MIPROv2 module.

        MIPROv2 optimizes the signature's instructions. We extract
        these and combine with the original prompt structure.

        Args:
            optimized_module: The optimized DSPy module.
            original_prompt: Original system prompt for structure.

        Returns:
            Optimized prompt string.
        """
        try:
            # Try to extract optimized instructions from the predictor
            if hasattr(optimized_module, 'solver'):
                solver = optimized_module.solver
                if hasattr(solver, 'signature'):
                    sig = solver.signature
                    # Get instructions if available
                    if hasattr(sig, 'instructions'):
                        instructions = sig.instructions
                        if instructions:
                            # Combine with original prompt
                            return f"{original_prompt}\n\n{instructions}"

            # If no optimized instructions found, return original
            return original_prompt

        except Exception as e:
            logger.debug("Could not extract optimized prompt", error=str(e))
            return original_prompt

    async def _evaluate_prompt(
        self,
        prompt: str,
        test_suite: TestSuite,
    ) -> tuple[float, SuiteResult]:
        """Evaluate a prompt against the test suite.

        Args:
            prompt: System prompt to evaluate.
            test_suite: Test suite for evaluation.

        Returns:
            Tuple of (score, suite_result).
        """
        runner_config = RunnerConfig(
            agent_name=test_suite.agent_name,
            collect_spans=False,
            max_concurrent=self.mipro_config.num_threads,
            verbose=self.mipro_config.verbose,
            eval_model=self._eval_model,
        )
        runner = BatchRunner(runner_config)

        result = await runner.run_suite(
            test_suite, system_prompt_override=prompt
        )
        score = suite_average_score(result)

        return score, result


def get_mipro_optimizer(
    config: OptimizationConfig | None = None,
    mipro_config: MIPROv2Config | None = None,
) -> MIPROv2AgentOptimizer:
    """Factory function to create a MIPROv2 optimizer.

    Args:
        config: Optional optimization configuration.
        mipro_config: Optional MIPROv2-specific configuration.

    Returns:
        Configured MIPROv2AgentOptimizer.
    """
    return MIPROv2AgentOptimizer(
        default_config=config,
        mipro_config=mipro_config,
    )
