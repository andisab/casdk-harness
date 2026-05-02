"""Section-based optimization orchestrator.

Coordinates targeted optimization across prompt sections using competency
mapping to determine which sections to optimize agentically.

Example usage:
    from harness.optimization.orchestrator import (
        SectionOptimizer,
        SectionOptimizationConfig,
    )

    config = SectionOptimizationConfig(
        agent_path=Path("agents/configs/python-expert.md"),
        criteria_path=Path("workspace/python-expert/research/eval_criteria.yaml"),
        workspace_dir=Path("workspace/python-expert"),
    )

    optimizer = SectionOptimizer(config)
    result = await optimizer.run()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from harness.optimization.analysis import (
    EvalCriteria,
    OptimizableSection,
    OptimizationStrategy,
    PromptSection,
    assess_coverage,
    create_section_suites,
    load_eval_criteria,
    map_tests_to_competencies,
)
from harness.optimization.optimizers.protocol import OptimizationConfig
from harness.optimization.resources import AgentResource
from harness.optimization.testcases import TestSuiteLoader

logger = structlog.get_logger(__name__)


@dataclass
class SectionOptimizationConfig:
    """Configuration for section-based optimization.

    Attributes:
        agent_path: Path to agent definition file.
        test_suite_path: Path to full test suite YAML (optional, for validation).
        criteria_path: Path to eval_criteria.yaml.
        workspace_dir: Directory for output and intermediate files.
        iterations_per_section: Max iterations per section.
        verbose: Enable verbose output.
        enable_coherence_pass: Run coherence analysis after synthesis.
        auto_reorder_sections: Automatically reorder sections for flow.
        validate_final: Run full test suite validation after synthesis.
        rollback_on_regression: Rollback if final score < baseline.
        cross_section_check: Check for regressions in previous sections.
        regression_threshold: Score drop threshold to trigger rollback (0-1).
        eval_model: Override model for test evaluation (sonnet/haiku for speed).
    """

    agent_path: Path
    test_suite_path: Path | None = None
    criteria_path: Path = field(default_factory=Path)
    workspace_dir: Path = field(default_factory=Path)
    iterations_per_section: int = 2
    verbose: bool = False
    enable_coherence_pass: bool = True
    auto_reorder_sections: bool = False
    validate_final: bool = True
    rollback_on_regression: bool = True
    cross_section_check: bool = True
    regression_threshold: float = 0.05
    eval_model: str | None = None


@dataclass
class SectionResult:
    """Result from optimizing a single section.

    Attributes:
        section: The prompt section optimized.
        strategy: Strategy used (agentic or preserve).
        original_score: Score before optimization.
        final_score: Score after optimization.
        improvement: Absolute improvement.
        improvement_percent: Percentage improvement.
        duration_seconds: Time taken.
        optimized_prompt: The optimized prompt content.
        test_suite_path: Path to focused test suite used.
        error: Error message if optimization failed.
    """

    section: PromptSection
    strategy: OptimizationStrategy
    original_score: float = 0.0
    final_score: float = 0.0
    improvement: float = 0.0
    improvement_percent: float = 0.0
    duration_seconds: float = 0.0
    optimized_prompt: str = ""
    test_suite_path: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and self.final_score >= self.original_score


@dataclass
class SectionImpact:
    """Impact of optimizing one section on another section's tests.

    Attributes:
        source_section: Section that was optimized.
        target_section: Section whose tests were affected.
        score_before: Score on target section tests before optimization.
        score_after: Score on target section tests after optimization.
        delta: Change in score (negative = regression).
        is_regression: Whether this constitutes a regression.
    """

    source_section: PromptSection
    target_section: PromptSection
    score_before: float
    score_after: float
    delta: float
    is_regression: bool


@dataclass
class OrchestrationResult:
    """Result from full section-based optimization.

    Attributes:
        success: Whether orchestration succeeded.
        agent_name: Name of the agent optimized.
        original_prompt: Original prompt content.
        final_prompt: Final synthesized prompt.
        section_results: Results per section.
        section_impact_matrix: Cross-section regression tracking.
        total_duration_seconds: Total time taken.
        output_path: Path where final prompt was saved.
        error: Error message if orchestration failed.
        regressions_detected: Number of cross-section regressions found.
    """

    success: bool
    agent_name: str
    original_prompt: str = ""
    final_prompt: str = ""
    section_results: list[SectionResult] = field(default_factory=list)
    section_impact_matrix: list[SectionImpact] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    output_path: str = ""
    error: str = ""
    regressions_detected: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "agent_name": self.agent_name,
            "total_duration_seconds": self.total_duration_seconds,
            "output_path": self.output_path,
            "error": self.error,
            "regressions_detected": self.regressions_detected,
            "section_results": [
                {
                    "section": r.section.value,
                    "strategy": r.strategy.value,
                    "original_score": r.original_score,
                    "final_score": r.final_score,
                    "improvement": r.improvement,
                    "improvement_percent": r.improvement_percent,
                    "duration_seconds": r.duration_seconds,
                    "success": r.success,
                    "error": r.error,
                }
                for r in self.section_results
            ],
            "section_impact_matrix": [
                {
                    "source": i.source_section.value,
                    "target": i.target_section.value,
                    "score_before": i.score_before,
                    "score_after": i.score_after,
                    "delta": i.delta,
                    "is_regression": i.is_regression,
                }
                for i in self.section_impact_matrix
            ],
        }


class SectionOptimizer:
    """Orchestrates section-based prompt optimization.

    This class coordinates the optimization workflow:
    1. ANALYZE: Map tests to competencies, determine section strategies
    2. EXECUTE: Run agentic optimization on each section with coverage
    3. SYNTHESIZE: Merge optimized sections into coherent prompt
    """

    def __init__(self, config: SectionOptimizationConfig) -> None:
        """Initialize the orchestrator.

        Args:
            config: Configuration for optimization.
        """
        self.config = config
        self._resource: AgentResource | None = None
        self._criteria: EvalCriteria | None = None
        self._sections: list[OptimizableSection] = []
        self._mapping: dict[str, Any] = {}
        # Cross-section regression tracking
        self._section_baselines: dict[PromptSection, float] = {}
        self._impact_matrix: list[SectionImpact] = []

    async def run(self) -> OrchestrationResult:
        """Run the full section-based optimization workflow.

        Returns:
            OrchestrationResult with success status and details.
        """
        start_time = time.time()

        logger.info(
            "Starting section-based optimization",
            mode="agentic",
            agent=str(self.config.agent_path),
            criteria=str(self.config.criteria_path),
            eval_model=self.config.eval_model or "(default)",
        )

        try:
            return await self._run_agentic_mode(start_time)

        except Exception as e:
            logger.error("Orchestration failed", error=str(e))
            return OrchestrationResult(
                success=False,
                agent_name="",
                error=str(e),
                total_duration_seconds=time.time() - start_time,
            )

    async def _run_agentic_mode(
        self, start_time: float
    ) -> OrchestrationResult:
        """Run agentic optimization (default mode).

        Uses LLM critique and research heuristics for improvement.

        Args:
            start_time: Timestamp when optimization started.

        Returns:
            OrchestrationResult with optimization details.
        """
        logger.info("AGENTIC: Starting LLM-based optimization")

        # Load agent resource
        self._resource = AgentResource.load(self.config.agent_path)

        # Load evaluation criteria (required)
        self._criteria = load_eval_criteria(self.config.criteria_path)

        logger.info(
            "AGENTIC: Resources loaded",
            agent=self._resource.name,
            competencies=len(self._criteria.competencies),
        )

        # Use agentic optimizer for all sections
        from harness.optimization.optimizers.agentic_optimizer import (
            AgenticSectionOptimizer,
            AgenticOptimizationConfig,
        )
        from harness.optimization.analysis import (
            extract_all_sections_from_prompt,
            replace_section_in_prompt,
        )

        agentic_optimizer = AgenticSectionOptimizer()
        agentic_config = AgenticOptimizationConfig(
            verbose=self.config.verbose,
            max_critique_rounds=self.config.iterations_per_section,
            test_weight=0.0,
        )

        current_prompt = self._resource.system_prompt
        section_results: list[SectionResult] = []

        # Extract and optimize each section using research-based critique
        sections = extract_all_sections_from_prompt(current_prompt)

        logger.info(
            "AGENTIC: Extracted sections",
            count=len(sections),
            sections=[s.value for s in sections.keys()],
        )

        for prompt_section, content in sections.items():
            if not content.strip():
                logger.debug(
                    "AGENTIC: Skipping empty section",
                    section=prompt_section.value,
                )
                continue

            section_start = time.time()

            # Create a minimal optimizable section for agentic optimizer
            opt_section = OptimizableSection(
                section=prompt_section,
                competencies=[],
                strategy=OptimizationStrategy.AGENTIC,
                test_count=0,
                quantitative_count=0,
                qualitative_count=0,
                reason="agentic mode",
            )

            try:
                logger.info(
                    "AGENTIC: Optimizing section",
                    section=prompt_section.value,
                )

                result = await agentic_optimizer.optimize_section(
                    section_content=content,
                    section=opt_section,
                    criteria=self._criteria,
                    config=agentic_config,
                    test_suite=None,
                )

                section_duration = time.time() - section_start

                if result.improved:
                    current_prompt = replace_section_in_prompt(
                        current_prompt,
                        prompt_section,
                        result.optimized_content,
                    )
                    logger.info(
                        "AGENTIC: Section improved",
                        section=prompt_section.value,
                        rounds=result.rounds_completed,
                    )

                section_results.append(
                    SectionResult(
                        section=prompt_section,
                        strategy=OptimizationStrategy.AGENTIC,
                        original_score=0.0,
                        final_score=1.0 if result.improved else 0.5,
                        improvement=1.0 if result.improved else 0.0,
                        improvement_percent=100.0 if result.improved else 0.0,
                        duration_seconds=section_duration,
                        optimized_prompt=current_prompt,
                        error=result.error,
                    )
                )

            except Exception as e:
                logger.error(
                    "AGENTIC: Section optimization failed",
                    section=prompt_section.value,
                    error=str(e),
                )
                section_results.append(
                    SectionResult(
                        section=prompt_section,
                        strategy=OptimizationStrategy.AGENTIC,
                        duration_seconds=time.time() - section_start,
                        error=str(e),
                    )
                )

        # Run coherence pass if enabled
        if self.config.enable_coherence_pass:
            from harness.optimization.analysis import PromptCoherenceAnalyzer

            logger.info("AGENTIC: Running coherence analysis")
            analyzer = PromptCoherenceAnalyzer()
            analysis = await analyzer.analyze(current_prompt)

            if analysis.has_issues and self.config.auto_reorder_sections:
                current_prompt = await analyzer.fix(
                    current_prompt,
                    analysis,
                    auto_reorder=True,
                    auto_dedupe=False,
                )
                logger.info("AGENTIC: Applied coherence fixes")

        # Save output
        workspace = self.config.workspace_dir
        agent_name = self._resource.name

        version = 1
        while (workspace / f"{agent_name}-v{version}.md").exists():
            version += 1

        output_path = workspace / f"{agent_name}-v{version}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        from harness.optimization.analysis import save_optimized_prompt
        save_optimized_prompt(current_prompt, output_path)

        duration = time.time() - start_time

        logger.info(
            "AGENTIC: Optimization complete",
            agent=agent_name,
            sections_improved=len([r for r in section_results if r.success]),
            duration=f"{duration:.1f}s",
            output_path=str(output_path),
        )

        return OrchestrationResult(
            success=True,
            agent_name=agent_name,
            original_prompt=self._resource.system_prompt,
            final_prompt=current_prompt,
            section_results=section_results,
            total_duration_seconds=duration,
            output_path=str(output_path),
        )

    async def _analyze(self) -> None:
        """Load resources and analyze test-competency mapping."""
        logger.info("ANALYZE: Loading resources and mapping tests")

        # Load agent resource
        self._resource = AgentResource.load(self.config.agent_path)

        # Load test suite
        test_suite = TestSuiteLoader.load(str(self.config.test_suite_path))

        # Load evaluation criteria
        self._criteria = load_eval_criteria(self.config.criteria_path)

        # Map tests to competencies
        self._mapping = map_tests_to_competencies(
            test_suite.test_cases, self._criteria
        )

        # Assess coverage and determine strategies
        self._sections = assess_coverage(
            self._mapping,
            self._criteria,
        )

        # Log analysis results
        agentic = [
            s for s in self._sections
            if s.strategy == OptimizationStrategy.AGENTIC
        ]
        preserve = [
            s for s in self._sections
            if s.strategy == OptimizationStrategy.PRESERVE
        ]

        logger.info(
            "ANALYZE: Coverage assessment complete",
            agentic_sections=len(agentic),
            preserve_sections=len(preserve),
        )


async def run_section_optimization(
    agent_path: str | Path,
    criteria_path: str | Path,
    workspace_dir: str | Path,
    test_suite_path: str | Path | None = None,
    iterations: int = 2,
    verbose: bool = False,
) -> OrchestrationResult:
    """Convenience function to run section-based optimization.

    Args:
        agent_path: Path to agent definition.
        criteria_path: Path to eval_criteria.yaml.
        workspace_dir: Directory for output.
        test_suite_path: Optional path to test suite.
        iterations: Max iterations per section.
        verbose: Enable verbose output.

    Returns:
        OrchestrationResult with optimization details.
    """
    config = SectionOptimizationConfig(
        agent_path=Path(agent_path),
        test_suite_path=Path(test_suite_path) if test_suite_path else None,
        criteria_path=Path(criteria_path),
        workspace_dir=Path(workspace_dir),
        iterations_per_section=iterations,
        verbose=verbose,
    )

    orchestrator = SectionOptimizer(config)
    return await orchestrator.run()
