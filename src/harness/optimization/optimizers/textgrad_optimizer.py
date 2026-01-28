"""TextGrad optimizer for agent prompt optimization.

Uses TextGrad's textual gradient descent (TGD) to optimize agent system prompts
through gradient-based textual feedback.

Example usage:
    from harness.optimization.optimizers import TextGradAgentOptimizer
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuiteLoader

    resource = AgentResource.load(Path("agents/configs/python-expert.md"))
    suite = TestSuiteLoader.load("tests/optimization/python_expert_tests.yaml")

    optimizer = TextGradAgentOptimizer()
    result = await optimizer.optimize(resource, suite)
    print(f"Improvement: {result.improvement_percent:.1f}%")
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog

from harness.optimization.optimizers.metrics import suite_average_score
from harness.optimization.optimizers.optimizer_utils import get_iteration_timeout
from harness.optimization.optimizers.protocol import (
    BaseOptimizer,
    IterationResult,
    OptimizationConfig,
    OptimizationResult,
    PromptCandidate,
)
from harness.optimization.runners import BatchRunner, RunnerConfig
from harness.optimization.templates import get_template_loader
from harness.optimization.testcases import SuiteResult

if TYPE_CHECKING:
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuite

logger = structlog.get_logger(__name__)

# Check if TextGrad is available
try:
    import textgrad as tg

    TEXTGRAD_AVAILABLE = True
except ImportError:
    TEXTGRAD_AVAILABLE = False
    tg = None  # type: ignore


class TextGradAgentOptimizer(BaseOptimizer):
    """TextGrad-based optimizer for agent system prompts.

    Uses Textual Gradient Descent (TGD) to optimize prompts through
    iterative textual feedback that mimics gradient-based optimization.

    Key concepts:
    - Variables: Trainable text elements (like the system prompt)
    - Loss: Text-based evaluation of quality
    - Gradients: LLM-generated suggestions for improvement
    - Optimizer: TGD updates prompts based on gradients
    """

    def __init__(
        self,
        default_config: OptimizationConfig | None = None,
        learning_rate: float = 0.1,
    ) -> None:
        """Initialize the optimizer.

        Args:
            default_config: Default optimization configuration.
            learning_rate: Learning rate for TGD (affects update magnitude).
        """
        super().__init__(default_config)
        self.learning_rate = learning_rate
        self._eval_model: str | None = None  # Set during optimize()

        if not TEXTGRAD_AVAILABLE:
            logger.warning(
                "TextGrad not available",
                hint="Install with: pip install 'textgrad>=0.1.6'",
            )

    async def optimize(
        self,
        resource: AgentResource,
        test_suite: TestSuite,
        config: OptimizationConfig | None = None,
    ) -> OptimizationResult:
        """Optimize agent prompt using TextGrad TGD.

        Args:
            resource: The agent resource to optimize.
            test_suite: Test cases for evaluation.
            config: Optimization configuration.

        Returns:
            OptimizationResult with improved prompt.
        """
        if not TEXTGRAD_AVAILABLE:
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
                error="TextGrad not installed. Install with: pip install 'textgrad>=0.1.6'",
            )

        effective_config = self._get_config(config)
        self._eval_model = effective_config.eval_model  # Store for evaluate()
        start_time = time.time()

        logger.info(
            "Starting TextGrad optimization",
            agent=resource.name,
            suite=test_suite.name,
            iterations=effective_config.max_iterations,
        )

        try:
            # Configure TextGrad LLM engine
            import os

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable required")

            # Create TextGrad engine using Anthropic
            engine = tg.get_engine("claude-3-5-sonnet-20241022")
            tg.set_backward_engine(engine)

            # Get baseline score
            baseline_result = await self.evaluate(resource.system_prompt, test_suite)
            baseline_score = baseline_result[0]

            logger.info(
                "Baseline evaluation complete",
                score=baseline_score,
                passed=baseline_result[1].passed_count,
                failed=baseline_result[1].failed_count,
            )

            # Get structure guidance for template-aware optimization
            loader = get_template_loader()
            structure_guidance = loader.get_structure_guidance(resource.RESOURCE_TYPE)

            # Build role description with structure requirements
            base_role = (
                "System prompt for the AI agent that should be optimized "
                "to improve task completion, code quality, and accuracy."
            )
            if structure_guidance:
                role_description = (
                    f"{base_role}\n\n"
                    "IMPORTANT: Preserve the following structure during optimization:\n"
                    f"{structure_guidance}"
                )
            else:
                role_description = base_role

            # Create trainable prompt variable
            system_prompt_var = tg.Variable(
                resource.system_prompt,
                requires_grad=True,
                role_description=role_description,
            )

            # Create TGD optimizer
            optimizer = tg.TGD(parameters=[system_prompt_var])

            # Track optimization progress with iteration timeout
            iterations: list[IterationResult] = []
            best_prompt = resource.system_prompt
            best_score = baseline_score
            previous_score = baseline_score
            iteration_timeout = get_iteration_timeout()

            for iteration in range(effective_config.max_iterations):
                iteration_start = time.time()

                logger.info(
                    "Starting iteration",
                    iteration=iteration,
                    max_iterations=effective_config.max_iterations,
                    current_best_score=best_score,
                    timeout_seconds=iteration_timeout,
                )

                # Initialize variables for this iteration
                candidates = []
                iteration_best_prompt = best_prompt
                iteration_best_score = best_score
                improvement = 0.0
                suite_result = None

                try:
                    async with asyncio.timeout(iteration_timeout):
                        # Zero gradients
                        optimizer.zero_grad()

                        # Get current prompt value
                        current_prompt = system_prompt_var.value

                        # Evaluate current prompt
                        score, suite_result = await self.evaluate(
                            current_prompt, test_suite
                        )

                        # Compute loss (inverse of score for minimization)
                        # Create loss variable for backward pass
                        loss_text = self._create_loss_text(
                            suite_result, test_suite, structure_guidance
                        )
                        loss_var = tg.Variable(
                            loss_text,
                            requires_grad=False,
                            role_description="Evaluation feedback on agent performance",
                        )

                        # Backward pass generates textual gradients
                        # The gradient will contain suggestions for improving the prompt
                        try:
                            loss_var.backward()

                            # Apply optimizer step
                            optimizer.step()

                            # Get updated prompt
                            updated_prompt = system_prompt_var.value

                            # Evaluate updated prompt
                            updated_score, updated_result = await self.evaluate(
                                updated_prompt, test_suite
                            )

                        except Exception as e:
                            logger.warning(
                                "Backward pass failed, keeping current prompt",
                                iteration=iteration,
                                error=str(e),
                            )
                            updated_prompt = current_prompt
                            updated_score = score

                        # Create candidates for this iteration
                        candidates = [
                            PromptCandidate(
                                prompt=current_prompt,
                                score=score,
                                iteration=iteration,
                                metadata={"type": "current"},
                            ),
                            PromptCandidate(
                                prompt=updated_prompt,
                                score=updated_score,
                                iteration=iteration,
                                metadata={"type": "updated"},
                            ),
                        ]

                        # Revert if performance decreased (validation revert)
                        if updated_score < score:
                            logger.info(
                                "Reverting update (performance decreased)",
                                iteration=iteration,
                                before=score,
                                after=updated_score,
                            )
                            system_prompt_var.set_value(current_prompt)
                            iteration_best_prompt = current_prompt
                            iteration_best_score = score
                        else:
                            iteration_best_prompt = updated_prompt
                            iteration_best_score = updated_score

                        # Track global best
                        improvement = iteration_best_score - previous_score
                        if iteration_best_score > best_score:
                            best_prompt = iteration_best_prompt
                            best_score = iteration_best_score
                            logger.info(
                                "New best prompt found",
                                iteration=iteration,
                                score=best_score,
                                improvement=improvement,
                            )

                except TimeoutError:
                    iteration_duration = time.time() - iteration_start
                    logger.error(
                        "Iteration timed out",
                        iteration=iteration,
                        timeout_seconds=iteration_timeout,
                        elapsed_seconds=iteration_duration,
                    )
                    # Record the timeout in iteration results
                    iterations.append(
                        IterationResult(
                            iteration=iteration,
                            best_prompt=best_prompt,
                            best_score=best_score,
                            candidates=[],
                            improvement=0.0,
                            duration_seconds=iteration_duration,
                        )
                    )
                    # Continue to next iteration or stop
                    if iteration == 0:
                        logger.error(
                            "First iteration timed out, stopping optimization",
                            iteration=iteration,
                        )
                        break
                    continue

                previous_score = iteration_best_score
                iteration_duration = time.time() - iteration_start

                logger.info(
                    "Iteration completed",
                    iteration=iteration,
                    duration_seconds=f"{iteration_duration:.1f}",
                    best_score=iteration_best_score,
                    candidates_evaluated=len(candidates),
                )

                iterations.append(
                    IterationResult(
                        iteration=iteration,
                        best_prompt=iteration_best_prompt,
                        best_score=iteration_best_score,
                        candidates=candidates,
                        suite_result=suite_result,
                        improvement=improvement,
                        duration_seconds=iteration_duration,
                    )
                )

                # Check early stopping
                if abs(improvement) < effective_config.early_stopping_threshold:
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
        verbose: bool = False,
    ) -> tuple[float, SuiteResult]:
        """Evaluate a prompt against the test suite.

        Args:
            prompt: The system prompt to evaluate.
            test_suite: Test cases for evaluation.
            verbose: Whether to show progress output.

        Returns:
            Tuple of (score, suite_result).
        """
        runner_config = RunnerConfig(
            agent_name=test_suite.agent_name,
            collect_spans=False,
            max_concurrent=4,
            verbose=verbose,
            eval_model=self._eval_model,
        )
        runner = BatchRunner(runner_config)

        result = await runner.run_suite(test_suite, system_prompt_override=prompt)
        score = suite_average_score(result)

        return score, result

    def _create_loss_text(
        self,
        suite_result: SuiteResult,
        test_suite: TestSuite,
        structure_guidance: str = "",
    ) -> str:
        """Create textual loss description from test results.

        This provides the feedback signal for TextGrad's backward pass.

        Args:
            suite_result: Results from evaluating the current prompt.
            test_suite: The test suite being used.
            structure_guidance: Optional structure requirements to preserve.

        Returns:
            Text describing failures and areas for improvement.
        """
        failed_results = suite_result.get_failed_results()

        # Build structure reminder if available
        structure_reminder = ""
        if structure_guidance:
            structure_reminder = (
                "\n\nIMPORTANT: Any improvements must preserve the required "
                "structure (YAML frontmatter fields, section headers, example blocks)."
            )

        if not failed_results:
            return (
                f"The agent performed well on all {len(suite_result.results)} tests. "
                f"Average score: {suite_result.total_score:.2f}. "
                "Consider if the prompt could be made more concise while "
                f"maintaining quality.{structure_reminder}"
            )

        loss_parts = [
            f"Evaluation Results: {suite_result.passed_count} passed, "
            f"{suite_result.failed_count} failed out of {len(suite_result.results)} tests.",
            f"Average score: {suite_result.total_score:.2f}",
            "",
            "Failed test cases requiring improvement:",
        ]

        for result in failed_results[:5]:  # Limit to 5 failures for context
            # Get the original test case for context
            test_case = test_suite.get_by_id(result.test_case_id)
            if test_case:
                loss_parts.append(f"\n- Test: {result.test_case_id}")
                loss_parts.append(f"  Task: {test_case.prompt[:100]}...")
                loss_parts.append(f"  Expected: {test_case.expected_behavior}")
                loss_parts.append(f"  Score: {result.score:.2f}")
                if result.error:
                    loss_parts.append(f"  Error: {result.error}")

        loss_parts.append("\n")
        loss_parts.append(
            "Improve the system prompt to better handle these failure cases. "
            "Focus on clearer instructions, edge case handling, and output format."
        )

        if structure_guidance:
            loss_parts.append(
                "\nIMPORTANT: Preserve required structure (YAML frontmatter, "
                "section headers, example blocks) during optimization."
            )

        return "\n".join(loss_parts)


def get_textgrad_optimizer(
    config: OptimizationConfig | None = None,
    learning_rate: float = 0.1,
) -> TextGradAgentOptimizer:
    """Factory function to create a TextGrad optimizer.

    Args:
        config: Optional optimization configuration.
        learning_rate: Learning rate for TGD.

    Returns:
        Configured TextGradAgentOptimizer.
    """
    return TextGradAgentOptimizer(
        default_config=config,
        learning_rate=learning_rate,
    )
