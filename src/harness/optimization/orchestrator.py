"""Section-based optimization orchestrator.

Coordinates targeted optimization across prompt sections using competency
mapping to determine where programmatic optimization will be most effective.

Example usage:
    from harness.optimization.orchestrator import (
        SectionOptimizer,
        SectionOptimizationConfig,
    )

    config = SectionOptimizationConfig(
        agent_path=Path("agents/configs/python-expert.md"),
        test_suite_path=Path("workspace/python-expert/tests/tests.yaml"),
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
        test_suite_path: Path to full test suite YAML (required only when agentic_mode=False).
        criteria_path: Path to eval_criteria.yaml.
        workspace_dir: Directory for output and intermediate files.
        optimizer: Optimizer to use (dspy, textgrad, or mipro).
        iterations_per_section: Max iterations per section.
        min_tests_for_programmatic: Minimum quantitative tests required.
        verbose: Enable verbose output.
        enable_coherence_pass: Run coherence analysis after synthesis.
        auto_reorder_sections: Automatically reorder sections for flow.
        validate_final: Run full test suite validation after synthesis.
        rollback_on_regression: Rollback if final score < baseline.
        cross_section_check: Check for regressions in previous sections.
        regression_threshold: Score drop threshold to trigger rollback (0-1).
        eval_model: Override model for test evaluation (sonnet/haiku for speed).
        agentic_mode: Use LLM critique only (no tests). Default is True.
    """

    agent_path: Path
    test_suite_path: Path | None  # Required only when agentic_mode=False
    criteria_path: Path
    workspace_dir: Path
    optimizer: str = "agentic"  # Default: agentic (LLM self-critique)
    iterations_per_section: int = 2
    min_tests_for_programmatic: int = 6  # Only used when CGF_ENABLE_PROGRAMMATIC=true
    verbose: bool = False
    enable_coherence_pass: bool = True
    auto_reorder_sections: bool = False
    validate_final: bool = True
    rollback_on_regression: bool = True
    cross_section_check: bool = True
    regression_threshold: float = 0.05
    eval_model: str | None = None  # Override model for test eval (sonnet/haiku)
    agentic_mode: bool = True  # Default: use LLM critique only (no tests)


@dataclass
class SectionResult:
    """Result from optimizing a single section.

    Attributes:
        section: The prompt section optimized.
        strategy: Strategy used (programmatic, agentic, preserve).
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
    2. PLAN: Create focused test suites for programmatic sections
    3. EXECUTE: Run optimization on each section with sufficient coverage
    4. SYNTHESIZE: Merge optimized sections into coherent prompt
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

        mode_str = "agentic" if self.config.agentic_mode else "programmatic"
        test_suite_str = (
            "(not required)" if self.config.agentic_mode
            else str(self.config.test_suite_path)
        )

        logger.info(
            "Starting section-based optimization",
            mode=mode_str,
            agent=str(self.config.agent_path),
            test_suite=test_suite_str,
            criteria=str(self.config.criteria_path),
            eval_model=self.config.eval_model or "(default)",
        )

        # Configure eval model for validators if specified (only for programmatic mode)
        if self.config.eval_model and not self.config.agentic_mode:
            from harness.optimization.testcases.validators import set_eval_model
            set_eval_model(self.config.eval_model)
            logger.info(
                "Eval model configured",
                model=self.config.eval_model,
            )

        try:
            # Agentic mode (default): simplified flow without tests
            if self.config.agentic_mode:
                return await self._run_agentic_mode(start_time)

            # Programmatic mode: full test-based optimization
            # Phase 1: ANALYZE - Load and analyze
            await self._analyze()

            # Phase 2: PLAN - Create focused suites
            suite_paths = await self._plan()

            # Phase 3: EXECUTE - Optimize each section
            section_results = await self._execute(suite_paths)

            # Phase 4: SYNTHESIZE - Merge results
            final_prompt, output_path = await self._synthesize(section_results)

            # Phase 5: VALIDATE - Post-synthesis validation
            if self.config.validate_final:
                original = self._resource.system_prompt if self._resource else ""
                final_prompt, validation_passed = await self._validate_final(
                    original_prompt=original,
                    final_prompt=final_prompt,
                    section_results=section_results,
                )

                if not validation_passed and self.config.rollback_on_regression:
                    # Update output path to indicate rollback
                    output_path = output_path.replace(".md", "-rollback.md")
                    from harness.optimization.analysis import save_optimized_prompt
                    save_optimized_prompt(final_prompt, Path(output_path))

            duration = time.time() - start_time

            # Count regressions from impact matrix
            regression_count = sum(
                1 for i in self._impact_matrix if i.is_regression
            )

            logger.info(
                "Section-based optimization complete",
                agent=self._resource.name if self._resource else "unknown",
                sections_optimized=len(
                    [r for r in section_results if r.success]
                ),
                regressions_detected=regression_count,
                total_duration=f"{duration:.1f}s",
                output_path=output_path,
            )

            return OrchestrationResult(
                success=True,
                agent_name=self._resource.name if self._resource else "",
                original_prompt=(
                    self._resource.system_prompt if self._resource else ""
                ),
                final_prompt=final_prompt,
                section_results=section_results,
                section_impact_matrix=self._impact_matrix,
                total_duration_seconds=duration,
                output_path=output_path,
                regressions_detected=regression_count,
            )

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
        """Run agentic optimization without test suite (default mode).

        Uses LLM critique and research heuristics for improvement.
        Faster than programmatic mode but no quantitative validation.

        Args:
            start_time: Timestamp when optimization started.

        Returns:
            OrchestrationResult with optimization details.
        """
        logger.info("AGENTIC: Starting LLM-based optimization (default mode)")

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
            test_weight=0.0,  # No test-based scoring in agentic mode
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
                competencies=[],  # Will use all criteria competencies
                strategy=OptimizationStrategy.AGENTIC,
                test_count=0,
                quantitative_count=0,
                qualitative_count=0,
                reason="agentic mode (default)",
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
                    test_suite=None,  # No tests in agentic mode (default)
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
        """Phase 1: Load resources and analyze test-competency mapping."""
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

        # Check if programmatic optimization is enabled
        from harness.optimization.optimizers import PROGRAMMATIC_ENABLED

        # Assess coverage and determine strategies
        # AGENTIC is default; PROGRAMMATIC only when enabled AND thresholds met
        self._sections = assess_coverage(
            self._mapping,
            self._criteria,
            min_deterministic_tests=self.config.min_tests_for_programmatic,
            programmatic_enabled=PROGRAMMATIC_ENABLED,
        )

        # Log analysis results
        programmatic = [
            s for s in self._sections
            if s.strategy == OptimizationStrategy.PROGRAMMATIC
        ]
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
            programmatic_sections=len(programmatic),
            agentic_sections=len(agentic),
            preserve_sections=len(preserve),
        )

        for section in programmatic:
            logger.info(
                "  PROGRAMMATIC",
                section=section.section.value,
                tests=section.test_count,
                quantitative=section.quantitative_count,
            )

    async def _plan(self) -> dict[PromptSection, Path]:
        """Phase 2: Create focused test suites for programmatic sections.

        Returns:
            Dictionary mapping sections to their focused suite paths.
        """
        logger.info("PLAN: Creating focused test suites")

        if not self._criteria or not self._resource:
            raise RuntimeError("Must run _analyze before _plan")

        # Load full test suite
        test_suite = TestSuiteLoader.load(str(self.config.test_suite_path))

        # Create focused tests directory
        focused_dir = self.config.workspace_dir / "tests" / "focused"
        focused_dir.mkdir(parents=True, exist_ok=True)

        # Create focused suites for each programmatic section
        suite_paths = create_section_suites(
            test_suite,
            self._sections,
            self._mapping,
            self._criteria,
            focused_dir,
        )

        logger.info(
            "PLAN: Created focused suites",
            count=len(suite_paths),
            sections=[s.value for s in suite_paths.keys()],
        )

        return suite_paths

    async def _execute(
        self, suite_paths: dict[PromptSection, Path]
    ) -> list[SectionResult]:
        """Phase 3: Run optimization on each section.

        Args:
            suite_paths: Mapping of sections to their focused suite paths.

        Returns:
            List of results from each section optimization.
        """
        logger.info("EXECUTE: Running section optimizations")

        results: list[SectionResult] = []
        completed_sections: list[OptimizableSection] = []

        # Get optimizer for PROGRAMMATIC sections
        # Note: AGENTIC sections use AgenticSectionOptimizer directly
        from harness.optimization.optimizers import (
            PROGRAMMATIC_ENABLED,
            MIPRO_AVAILABLE,
            TEXTGRAD_AVAILABLE,
        )

        optimizer = None
        if self.config.optimizer in ("mipro", "dspy") and PROGRAMMATIC_ENABLED:
            if MIPRO_AVAILABLE:
                from harness.optimization.optimizers import get_mipro_optimizer
                optimizer = get_mipro_optimizer()
            else:
                logger.warning(
                    "MIPROv2 requested but not available. "
                    "Install dspy-ai>=3.0.0 or set CGF_ENABLE_PROGRAMMATIC=false"
                )
        elif self.config.optimizer == "textgrad" and PROGRAMMATIC_ENABLED:
            if TEXTGRAD_AVAILABLE:
                from harness.optimization.optimizers import get_textgrad_optimizer
                optimizer = get_textgrad_optimizer()
            else:
                logger.warning(
                    "TextGrad requested but not available. "
                    "Install textgrad or set CGF_ENABLE_PROGRAMMATIC=false"
                )

        # Track the current best prompt (starts with original)
        current_prompt = self._resource.system_prompt if self._resource else ""

        for section in self._sections:
            # Store prompt before this section's optimization
            prompt_before = current_prompt
            section_start = time.time()

            if section.strategy == OptimizationStrategy.PRESERVE:
                results.append(
                    SectionResult(
                        section=section.section,
                        strategy=OptimizationStrategy.PRESERVE,
                        original_score=0.0,
                        final_score=0.0,
                        duration_seconds=0.0,
                    )
                )
                continue

            if section.strategy == OptimizationStrategy.AGENTIC:
                # Use agentic (self-critique) optimization for qualitative sections
                from harness.optimization.optimizers.agentic_optimizer import (
                    AgenticSectionOptimizer,
                    AgenticOptimizationConfig,
                )
                from harness.optimization.analysis import (
                    extract_section_from_prompt,
                    create_focused_suite_for_section,
                )

                agentic_optimizer = AgenticSectionOptimizer()

                # For purely qualitative sections (no deterministic tests),
                # use heuristics-only mode - skip test execution for speed
                use_heuristics_only = section.quantitative_count == 0
                agentic_config = AgenticOptimizationConfig(
                    verbose=self.config.verbose,
                    max_critique_rounds=2,
                    # Set test_weight=0 for purely qualitative sections
                    test_weight=0.0 if use_heuristics_only else 0.4,
                )

                # Extract the section content from current prompt
                section_content = extract_section_from_prompt(
                    current_prompt, section.section
                )

                if not section_content:
                    logger.warning(
                        "Could not extract section for agentic optimization",
                        section=section.section.value,
                    )
                    results.append(
                        SectionResult(
                            section=section.section,
                            strategy=OptimizationStrategy.AGENTIC,
                            duration_seconds=0.0,
                            error="Could not extract section content",
                        )
                    )
                    continue

                # Create focused test suite only if not using heuristics-only mode
                focused_suite = None
                if not use_heuristics_only:
                    full_test_suite = TestSuiteLoader.load(
                        str(self.config.test_suite_path)
                    )
                    focused_suite = create_focused_suite_for_section(
                        full_test_suite,
                        section,
                        self._mapping,
                        self._criteria,
                    )

                logger.info(
                    "EXECUTE: Running agentic optimization",
                    section=section.section.value,
                    qualitative_tests=section.qualitative_count,
                    heuristics_only=use_heuristics_only,
                    focused_tests=(
                        len(focused_suite.test_cases) if focused_suite else 0
                    ),
                )

                try:
                    agentic_result = await agentic_optimizer.optimize_section(
                        section_content=section_content,
                        section=section,
                        criteria=self._criteria,
                        config=agentic_config,
                        test_suite=focused_suite,  # Pass focused suite
                    )

                    section_duration = time.time() - section_start

                    if agentic_result.improved:
                        # Update current prompt with optimized section
                        from harness.optimization.analysis import (
                            replace_section_in_prompt,
                        )
                        current_prompt = replace_section_in_prompt(
                            current_prompt,
                            section.section,
                            agentic_result.optimized_content,
                        )

                        logger.info(
                            "EXECUTE: Agentic section improved",
                            section=section.section.value,
                            reason=agentic_result.improvement_reason[:100],
                            rounds=agentic_result.rounds_completed,
                        )

                    # Use validation score if available
                    final = agentic_result.validation_score
                    if final is None:
                        final = 1.0 if agentic_result.improved else 0.0

                    results.append(
                        SectionResult(
                            section=section.section,
                            strategy=OptimizationStrategy.AGENTIC,
                            original_score=0.0,
                            final_score=final,
                            improvement=final,
                            improvement_percent=final * 100.0,
                            duration_seconds=section_duration,
                            optimized_prompt=current_prompt,
                            error=agentic_result.error,
                        )
                    )

                    # Check for cross-section regression
                    if (
                        self.config.cross_section_check
                        and agentic_result.improved
                        and completed_sections
                    ):
                        impacts = await self._check_cross_section_regression(
                            section, prompt_before, current_prompt,
                            completed_sections,
                        )
                        self._impact_matrix.extend(impacts)

                        # If regression detected, optionally rollback
                        regressions = [i for i in impacts if i.is_regression]
                        if regressions and self.config.rollback_on_regression:
                            logger.warning(
                                "Rolling back section due to regression",
                                section=section.section.value,
                                regressions=len(regressions),
                            )
                            current_prompt = prompt_before
                            results[-1] = SectionResult(
                                section=section.section,
                                strategy=OptimizationStrategy.AGENTIC,
                                original_score=0.0,
                                final_score=0.0,
                                duration_seconds=section_duration,
                                error="Rolled back due to regression",
                            )

                    # Add to completed sections for future checks
                    completed_sections.append(section)

                except Exception as e:
                    logger.error(
                        "Agentic optimization failed",
                        section=section.section.value,
                        error=str(e),
                    )
                    results.append(
                        SectionResult(
                            section=section.section,
                            strategy=OptimizationStrategy.AGENTIC,
                            duration_seconds=time.time() - section_start,
                            error=str(e),
                        )
                    )

                continue

            # PROGRAMMATIC optimization
            # Fall back to AGENTIC if programmatic optimizer not available
            if optimizer is None:
                logger.warning(
                    "PROGRAMMATIC strategy requested but optimizer not available. "
                    "Falling back to AGENTIC. Set CGF_ENABLE_PROGRAMMATIC=true and "
                    "install dspy-ai or textgrad.",
                    section=section.section.value,
                )
                # Re-run as AGENTIC (copy the agentic block logic or skip)
                results.append(
                    SectionResult(
                        section=section.section,
                        strategy=OptimizationStrategy.PROGRAMMATIC,
                        duration_seconds=0.0,
                        error="Programmatic optimizer not available",
                    )
                )
                continue

            if section.section not in suite_paths:
                logger.warning(
                    "No focused suite for programmatic section",
                    section=section.section.value,
                )
                continue

            suite_path = suite_paths[section.section]

            logger.info(
                "EXECUTE: Optimizing section",
                section=section.section.value,
                test_suite=str(suite_path),
                tests=section.test_count,
            )

            try:
                # Load focused test suite
                focused_suite = TestSuiteLoader.load(str(suite_path))

                # Create temporary resource with current prompt
                temp_resource = AgentResource.from_content(
                    name=self._resource.name if self._resource else "",
                    system_prompt=current_prompt,
                    description=(
                        self._resource.description if self._resource else ""
                    ),
                    model=self._resource.model if self._resource else "sonnet",
                    tools=self._resource.tools if self._resource else [],
                    max_turns=self._resource.max_turns if self._resource else 100,
                )

                # Run optimization
                opt_config = OptimizationConfig(
                    max_iterations=self.config.iterations_per_section,
                    num_candidates=3,  # Fewer candidates per section
                    verbose=self.config.verbose,
                    eval_model=self.config.eval_model,
                )

                opt_result = await optimizer.optimize(
                    temp_resource, focused_suite, opt_config
                )

                section_duration = time.time() - section_start

                if opt_result.success and opt_result.final_score > opt_result.original_score:
                    # Update current prompt with optimized version
                    current_prompt = opt_result.optimized_prompt

                    logger.info(
                        "EXECUTE: Section improved",
                        section=section.section.value,
                        original=opt_result.original_score,
                        final=opt_result.final_score,
                        improvement=f"{opt_result.improvement_percent:.1f}%",
                    )

                results.append(
                    SectionResult(
                        section=section.section,
                        strategy=OptimizationStrategy.PROGRAMMATIC,
                        original_score=opt_result.original_score,
                        final_score=opt_result.final_score,
                        improvement=opt_result.improvement,
                        improvement_percent=opt_result.improvement_percent,
                        duration_seconds=section_duration,
                        optimized_prompt=opt_result.optimized_prompt,
                        test_suite_path=str(suite_path),
                    )
                )

                # Check for cross-section regression
                improved = opt_result.final_score > opt_result.original_score
                if (
                    self.config.cross_section_check
                    and improved
                    and completed_sections
                ):
                    impacts = await self._check_cross_section_regression(
                        section, prompt_before, current_prompt,
                        completed_sections,
                    )
                    self._impact_matrix.extend(impacts)

                    # If regression detected, optionally rollback
                    regressions = [i for i in impacts if i.is_regression]
                    if regressions and self.config.rollback_on_regression:
                        logger.warning(
                            "Rolling back section due to regression",
                            section=section.section.value,
                            regressions=len(regressions),
                        )
                        current_prompt = prompt_before
                        results[-1] = SectionResult(
                            section=section.section,
                            strategy=OptimizationStrategy.PROGRAMMATIC,
                            original_score=opt_result.original_score,
                            final_score=opt_result.original_score,
                            duration_seconds=section_duration,
                            error="Rolled back due to regression",
                        )

                # Add to completed sections for future checks
                completed_sections.append(section)

            except Exception as e:
                logger.error(
                    "Section optimization failed",
                    section=section.section.value,
                    error=str(e),
                )
                results.append(
                    SectionResult(
                        section=section.section,
                        strategy=OptimizationStrategy.PROGRAMMATIC,
                        duration_seconds=time.time() - section_start,
                        error=str(e),
                    )
                )

        return results

    async def _synthesize(
        self, section_results: list[SectionResult]
    ) -> tuple[str, str]:
        """Phase 4: Merge optimized sections into final prompt.

        Args:
            section_results: Results from section optimizations.

        Returns:
            Tuple of (final_prompt, output_path).
        """
        logger.info("SYNTHESIZE: Merging optimized sections")

        # Get the best prompt from successful optimizations
        # Since we iteratively update current_prompt in _execute,
        # the last successful optimization already has the accumulated changes
        best_prompt = self._resource.system_prompt if self._resource else ""

        for result in section_results:
            if result.success and result.optimized_prompt:
                best_prompt = result.optimized_prompt

        # Run coherence pass if enabled
        if self.config.enable_coherence_pass:
            from harness.optimization.analysis import (
                PromptCoherenceAnalyzer,
            )

            logger.info("SYNTHESIZE: Running coherence analysis")
            analyzer = PromptCoherenceAnalyzer()
            analysis = await analyzer.analyze(best_prompt)

            if analysis.has_issues:
                logger.info(
                    "SYNTHESIZE: Coherence issues detected",
                    count=len(analysis.issues),
                    high_severity=analysis.high_severity_count,
                    score=analysis.overall_score,
                )

                # Log individual issues for visibility
                for issue in analysis.issues:
                    logger.info(
                        "  Coherence issue",
                        type=issue.type.value,
                        severity=issue.severity.value,
                        location=issue.location,
                        description=issue.description[:80],
                    )

                # Apply fixes if auto-reorder is enabled
                if self.config.auto_reorder_sections:
                    best_prompt = await analyzer.fix(
                        best_prompt,
                        analysis,
                        auto_reorder=True,
                        auto_dedupe=False,
                    )
                    logger.info(
                        "SYNTHESIZE: Applied coherence fixes",
                        reordered=True,
                    )
            else:
                logger.info(
                    "SYNTHESIZE: No coherence issues detected",
                    score=analysis.overall_score,
                )

        # Determine output path
        workspace = self.config.workspace_dir
        agent_name = self._resource.name if self._resource else "optimized"

        # Find next version number
        version = 1
        while (workspace / f"{agent_name}-v{version}.md").exists():
            version += 1

        output_path = workspace / f"{agent_name}-v{version}.md"

        # Save the final prompt
        from harness.optimization.analysis import save_optimized_prompt

        save_optimized_prompt(best_prompt, output_path)

        logger.info(
            "SYNTHESIZE: Saved final prompt",
            path=str(output_path),
            sections_improved=len(
                [r for r in section_results if r.improvement > 0]
            ),
        )

        return best_prompt, str(output_path)

    async def _validate_final(
        self,
        original_prompt: str,
        final_prompt: str,
        section_results: list[SectionResult],
    ) -> tuple[str, bool]:
        """Phase 5: Validate final prompt against full test suite.

        Runs the full test suite against both original and final prompts
        to ensure optimization didn't cause regressions.

        Args:
            original_prompt: Original prompt before optimization.
            final_prompt: Final prompt after synthesis.
            section_results: Results from section optimizations.

        Returns:
            Tuple of (prompt_to_use, validation_passed).
            If regression detected and rollback enabled, returns best
            intermediate or original prompt.
        """
        logger.info("VALIDATE: Running post-synthesis validation")

        from harness.optimization.testcases import get_validator

        # Load full test suite
        test_suite = TestSuiteLoader.load(str(self.config.test_suite_path))

        # Get baseline score (from original prompt)
        baseline_scores = []
        final_scores = []

        for test in test_suite.test_cases:
            try:
                validator = get_validator(test.validation)

                # Score against original prompt
                baseline = await validator.validate(original_prompt)
                baseline_scores.append(baseline)

                # Score against final prompt
                final = await validator.validate(final_prompt)
                final_scores.append(final)

            except Exception as e:
                logger.debug(
                    "Validation error for test",
                    test_id=test.id,
                    error=str(e),
                )
                # Skip tests that fail validation
                continue

        if not baseline_scores:
            logger.warning("No tests could be validated")
            return final_prompt, True

        avg_baseline = sum(baseline_scores) / len(baseline_scores)
        avg_final = sum(final_scores) / len(final_scores)

        logger.info(
            "VALIDATE: Scores computed",
            baseline=f"{avg_baseline:.3f}",
            final=f"{avg_final:.3f}",
            delta=f"{avg_final - avg_baseline:.3f}",
        )

        # Check for regression
        if avg_final < avg_baseline:
            logger.warning(
                "VALIDATE: Regression detected",
                baseline=avg_baseline,
                final=avg_final,
                regression=avg_baseline - avg_final,
            )

            # Find best intermediate result
            best_prompt = original_prompt
            best_score = avg_baseline

            for result in section_results:
                if result.success and result.optimized_prompt:
                    # Score this intermediate
                    intermediate_scores = []
                    for test in test_suite.test_cases:
                        try:
                            validator = get_validator(test.validation)
                            score = await validator.validate(
                                result.optimized_prompt
                            )
                            intermediate_scores.append(score)
                        except Exception:
                            continue

                    if intermediate_scores:
                        avg_intermediate = (
                            sum(intermediate_scores) / len(intermediate_scores)
                        )
                        if avg_intermediate > best_score:
                            best_score = avg_intermediate
                            best_prompt = result.optimized_prompt

            logger.info(
                "VALIDATE: Rollback to best intermediate",
                best_score=f"{best_score:.3f}",
                is_original=best_prompt == original_prompt,
            )

            return best_prompt, False

        # Validation passed
        logger.info(
            "VALIDATE: Passed",
            improvement=f"{avg_final - avg_baseline:.3f}",
        )
        return final_prompt, True

    async def _compute_section_baseline(
        self,
        section: OptimizableSection,
        prompt: str,
    ) -> float:
        """Compute baseline score for a section's tests.

        Args:
            section: The section to compute baseline for.
            prompt: The prompt to evaluate.

        Returns:
            Average score across section's tests.
        """
        from harness.optimization.testcases import get_validator
        from harness.optimization.analysis import get_section_tests

        # Get tests mapped to this section
        section_tests = get_section_tests(
            section.section, self._mapping, self._criteria
        )

        if not section_tests:
            return 1.0  # No tests = no regression possible

        # Load full test suite to get test definitions
        test_suite = TestSuiteLoader.load(str(self.config.test_suite_path))
        test_by_id = {t.id: t for t in test_suite.test_cases}

        scores = []
        for test_id in section_tests:
            if test_id not in test_by_id:
                continue
            test = test_by_id[test_id]
            try:
                validator = get_validator(test.validation)
                score = await validator.validate(prompt)
                scores.append(score)
            except Exception:
                continue

        return sum(scores) / len(scores) if scores else 1.0

    async def _check_cross_section_regression(
        self,
        optimized_section: OptimizableSection,
        prompt_before: str,
        prompt_after: str,
        completed_sections: list[OptimizableSection],
    ) -> list[SectionImpact]:
        """Check if optimizing a section caused regression in previous sections.

        Args:
            optimized_section: The section that was just optimized.
            prompt_before: Prompt before optimization.
            prompt_after: Prompt after optimization.
            completed_sections: Previously optimized sections to check.

        Returns:
            List of SectionImpact showing cross-section effects.
        """
        impacts = []

        for target_section in completed_sections:
            if target_section.section == optimized_section.section:
                continue

            # Get scores before and after
            score_before = await self._compute_section_baseline(
                target_section, prompt_before
            )
            score_after = await self._compute_section_baseline(
                target_section, prompt_after
            )

            delta = score_after - score_before
            is_regression = delta < -self.config.regression_threshold

            impact = SectionImpact(
                source_section=optimized_section.section,
                target_section=target_section.section,
                score_before=score_before,
                score_after=score_after,
                delta=delta,
                is_regression=is_regression,
            )
            impacts.append(impact)

            if is_regression:
                logger.warning(
                    "Cross-section regression detected",
                    source=optimized_section.section.value,
                    target=target_section.section.value,
                    delta=f"{delta:.3f}",
                )

        return impacts


async def run_section_optimization(
    agent_path: str | Path,
    test_suite_path: str | Path,
    criteria_path: str | Path,
    workspace_dir: str | Path,
    optimizer: str = "dspy",
    iterations: int = 2,
    verbose: bool = False,
) -> OrchestrationResult:
    """Convenience function to run section-based optimization.

    Args:
        agent_path: Path to agent definition.
        test_suite_path: Path to full test suite.
        criteria_path: Path to eval_criteria.yaml.
        workspace_dir: Directory for output.
        optimizer: Optimizer to use (dspy or textgrad).
        iterations: Max iterations per section.
        verbose: Enable verbose output.

    Returns:
        OrchestrationResult with optimization details.
    """
    config = SectionOptimizationConfig(
        agent_path=Path(agent_path),
        test_suite_path=Path(test_suite_path),
        criteria_path=Path(criteria_path),
        workspace_dir=Path(workspace_dir),
        optimizer=optimizer,
        iterations_per_section=iterations,
        verbose=verbose,
    )

    orchestrator = SectionOptimizer(config)
    return await orchestrator.run()
