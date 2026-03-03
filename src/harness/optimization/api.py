"""CGF Optimization API - Consolidated interface for agents.

This module provides:
1. Library functions for direct Python import
2. CLI entry points for agent Bash tool invocation
3. JSON output mode for structured responses

Usage from cgf-orchestrator (via Bash):
    python -m harness.optimization.api optimize \
        --resource workspace/agent/agent.md \
        --criteria workspace/agent/research/eval_criteria.yaml \
        --workspace workspace/agent \
        --output-json

Usage from Python:
    from harness.optimization.api import optimize_resource, evaluate_resource
    result = await optimize_resource(resource_path, criteria_path, workspace_dir)
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import click
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Models (JSON-serializable for CLI output)
# =============================================================================


@dataclass
class OptimizationResult:
    """Result from optimize_resource()."""

    success: bool
    output_path: str | None
    original_score: float | None
    final_score: float | None
    improvement_percent: float | None
    sections_optimized: int
    total_duration_seconds: float
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class EvaluationResult:
    """Result from evaluate_resource()."""

    success: bool
    score: float
    passed_tests: int
    failed_tests: int
    total_tests: int
    details: dict[str, Any]
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class AnalysisResult:
    """Result from analyze_resource()."""

    success: bool
    resource_type: str
    total_lines: int
    sections: list[str]
    competencies: list[str]
    coverage_summary: dict[str, Any]
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# =============================================================================
# Library Functions (for Python import)
# =============================================================================


async def optimize_resource(
    resource_path: Path,
    criteria_path: Path,
    workspace_dir: Path,
    test_suite_path: Path | None = None,
    iterations: int = 2,
    eval_model: str | None = None,
    verbose: bool = False,
) -> OptimizationResult:
    """Run CGF optimization on a resource.

    Args:
        resource_path: Path to agent/skill/command .md file
        criteria_path: Path to eval_criteria.yaml
        workspace_dir: Working directory for outputs
        test_suite_path: Optional path to tests.yaml for validation
        iterations: Max iterations per section
        eval_model: Override eval model (sonnet/haiku/opus)
        verbose: Enable verbose output

    Returns:
        OptimizationResult with success, paths, scores
    """
    from harness.optimization.orchestrator import (
        SectionOptimizationConfig,
        SectionOptimizer,
    )

    try:
        config = SectionOptimizationConfig(
            agent_path=resource_path,
            test_suite_path=test_suite_path,
            criteria_path=criteria_path,
            workspace_dir=workspace_dir,
            eval_model=eval_model,
            iterations_per_section=iterations,
            verbose=verbose,
        )

        orchestrator = SectionOptimizer(config)
        result = await orchestrator.run()

        # Extract scores from section results
        original_scores = [
            sr.original_score
            for sr in result.section_results
            if sr.original_score > 0
        ]
        final_scores = [
            sr.final_score for sr in result.section_results if sr.final_score > 0
        ]

        original_avg = sum(original_scores) / len(original_scores) if original_scores else None
        final_avg = sum(final_scores) / len(final_scores) if final_scores else None

        improvement_pct = None
        if original_avg and final_avg and original_avg > 0:
            improvement_pct = ((final_avg - original_avg) / original_avg) * 100

        return OptimizationResult(
            success=result.success,
            output_path=result.output_path,
            original_score=original_avg,
            final_score=final_avg,
            improvement_percent=improvement_pct,
            sections_optimized=len(result.section_results),
            total_duration_seconds=result.total_duration_seconds,
            error=result.error,
        )

    except Exception as e:
        logger.exception("Optimization failed")
        return OptimizationResult(
            success=False,
            output_path=None,
            original_score=None,
            final_score=None,
            improvement_percent=None,
            sections_optimized=0,
            total_duration_seconds=0.0,
            error=str(e),
        )


async def evaluate_resource(
    resource_path: Path,
    test_suite_path: Path,
    eval_model: str | None = None,
) -> EvaluationResult:
    """Evaluate a resource against a test suite.

    Args:
        resource_path: Path to resource .md file
        test_suite_path: Path to tests.yaml
        eval_model: Override eval model

    Returns:
        EvaluationResult with scores and test details
    """
    from harness.optimization.resources import AgentResource
    from harness.optimization.runners import BatchRunner, RunnerConfig
    from harness.optimization.testcases import TestSuiteLoader

    try:
        # Load resource and test suite
        resource = AgentResource(resource_path)
        suite = TestSuiteLoader.load(str(test_suite_path))

        config = RunnerConfig(
            agent_name=resource_path.stem,
            eval_model=eval_model,
        )
        runner = BatchRunner(config)

        result = await runner.run_suite(suite, resource=resource)

        # Count passed/failed
        passed = sum(1 for tr in result.test_results if tr.score >= 0.5)
        failed = len(result.test_results) - passed

        return EvaluationResult(
            success=True,
            score=result.average_score,
            passed_tests=passed,
            failed_tests=failed,
            total_tests=len(result.test_results),
            details={tr.test_case_id: tr.score for tr in result.test_results},
        )

    except Exception as e:
        logger.exception("Evaluation failed")
        return EvaluationResult(
            success=False,
            score=0.0,
            passed_tests=0,
            failed_tests=0,
            total_tests=0,
            details={},
            error=str(e),
        )


async def analyze_resource(
    resource_path: Path,
    test_suite_path: Path | None = None,
) -> AnalysisResult:
    """Analyze a resource file structure and test coverage.

    Args:
        resource_path: Path to resource .md file
        test_suite_path: Optional path to tests.yaml for coverage analysis

    Returns:
        AnalysisResult with structure and coverage info
    """
    from harness.optimization.analysis import (
        assess_coverage,
        map_tests_to_competencies,
    )
    from harness.optimization.resources import AgentResource
    from harness.optimization.testcases import TestSuiteLoader

    try:
        # Load resource
        resource = AgentResource(resource_path)
        sections = [s.name for s in resource.get_sections()]
        competencies = resource.get_competencies()

        coverage_summary: dict[str, Any] = {}

        if test_suite_path and test_suite_path.exists():
            suite = TestSuiteLoader.load(str(test_suite_path))
            # Map tests to competencies
            mapping = map_tests_to_competencies(suite.test_cases, competencies)
            coverage = assess_coverage(mapping, sections)

            coverage_summary = {
                "total_tests": len(suite.test_cases),
                "mapped_competencies": len(mapping),
                "sections_with_coverage": sum(
                    1 for c in coverage if c.strategy.value != "preserve"
                ),
            }

        return AnalysisResult(
            success=True,
            resource_type=resource.resource_type,
            total_lines=len(resource.content.splitlines()),
            sections=sections,
            competencies=competencies,
            coverage_summary=coverage_summary,
        )

    except Exception as e:
        logger.exception("Analysis failed")
        return AnalysisResult(
            success=False,
            resource_type="unknown",
            total_lines=0,
            sections=[],
            competencies=[],
            coverage_summary={},
            error=str(e),
        )


# =============================================================================
# CLI Entry Points (for agent Bash invocation)
# =============================================================================


@click.group()
def cli():
    """CGF Optimization API - Agent-callable commands."""
    pass


@cli.command()
@click.option("--resource", "-r", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--criteria", "-c", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--workspace", "-w", type=click.Path(path_type=Path), required=True)
@click.option("--test-suite", "-t", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--iterations", "-i", type=int, default=2, help="Max iterations per section")
@click.option("--eval-model", type=str, default=None, help="Override eval model")
@click.option("--verbose", "-v", is_flag=True, default=False)
@click.option("--output-json", is_flag=True, default=False, help="Output JSON format")
def optimize(
    resource: Path,
    criteria: Path,
    workspace: Path,
    test_suite: Path | None,
    iterations: int,
    eval_model: str | None,
    verbose: bool,
    output_json: bool,
):
    """Run CGF optimization on a resource."""
    result = asyncio.run(
        optimize_resource(
            resource_path=resource,
            criteria_path=criteria,
            workspace_dir=workspace,
            test_suite_path=test_suite,
            iterations=iterations,
            eval_model=eval_model,
            verbose=verbose,
        )
    )

    if output_json:
        print(result.to_json())
    else:
        print(f"Success: {result.success}")
        print(f"Output: {result.output_path}")
        print(f"Sections Optimized: {result.sections_optimized}")
        if result.improvement_percent:
            print(f"Improvement: {result.improvement_percent:.1f}%")
        if result.error:
            print(f"Error: {result.error}")

    sys.exit(0 if result.success else 1)


@cli.command()
@click.option("--resource", "-r", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--test-suite", "-t", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--eval-model", type=str, default=None, help="Override eval model")
@click.option("--output-json", is_flag=True, default=False, help="Output JSON format")
def evaluate(
    resource: Path,
    test_suite: Path,
    eval_model: str | None,
    output_json: bool,
):
    """Evaluate resource against test suite."""
    result = asyncio.run(
        evaluate_resource(
            resource_path=resource,
            test_suite_path=test_suite,
            eval_model=eval_model,
        )
    )

    if output_json:
        print(result.to_json())
    else:
        print(f"Score: {result.score:.2f}")
        print(f"Passed: {result.passed_tests}/{result.total_tests}")
        if result.error:
            print(f"Error: {result.error}")

    sys.exit(0 if result.success else 1)


@cli.command()
@click.option("--resource", "-r", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--test-suite", "-t", type=click.Path(path_type=Path), default=None)
@click.option("--output-json", is_flag=True, default=False, help="Output JSON format")
def analyze(
    resource: Path,
    test_suite: Path | None,
    output_json: bool,
):
    """Analyze resource structure and test coverage."""
    result = asyncio.run(
        analyze_resource(
            resource_path=resource,
            test_suite_path=test_suite,
        )
    )

    if output_json:
        print(result.to_json())
    else:
        print(f"Type: {result.resource_type}")
        print(f"Lines: {result.total_lines}")
        print(f"Sections: {', '.join(result.sections)}")
        print(f"Competencies: {len(result.competencies)}")
        if result.coverage_summary:
            print(f"Coverage: {result.coverage_summary}")
        if result.error:
            print(f"Error: {result.error}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    cli()
