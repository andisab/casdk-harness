"""CLI for section-based prompt optimization.

Default mode is agentic (LLM critique only, no tests required).
Set CGF_ENABLE_PROGRAMMATIC=true to enable test-based DSPy/TextGrad optimization.

Usage (default agentic mode):
    python -m harness.optimization.cli.section_optimize \\
        --agent agents/configs/python-expert.md \\
        --criteria workspace/python-expert/research/eval_criteria.yaml \\
        --workspace workspace/python-expert

Usage (programmatic mode - requires CGF_ENABLE_PROGRAMMATIC=true):
    CGF_ENABLE_PROGRAMMATIC=true python -m harness.optimization.cli.section_optimize \\
        --agent agents/configs/python-expert.md \\
        --test-suite workspace/python-expert/tests/tests.yaml \\
        --criteria workspace/python-expert/research/eval_criteria.yaml \\
        --workspace workspace/python-expert \\
        --optimizer mipro
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import click
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from harness.optimization.orchestrator import (
    SectionOptimizationConfig,
    SectionOptimizer,
)

logger = structlog.get_logger(__name__)
console = Console()


@click.command()
@click.option(
    "-a",
    "--agent",
    "agent_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to agent definition file (.md with YAML frontmatter)",
)
@click.option(
    "-t",
    "--test-suite",
    "test_suite_path",
    type=click.Path(exists=True, path_type=Path),
    required=False,  # Required only when CGF_ENABLE_PROGRAMMATIC=true
    help="Path to test suite (YAML). Required only with CGF_ENABLE_PROGRAMMATIC=true",
)
@click.option(
    "-c",
    "--criteria",
    "criteria_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to eval_criteria.yaml with competencies",
)
@click.option(
    "-w",
    "--workspace",
    "workspace_dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Workspace directory for output and intermediate files",
)
@click.option(
    "-o",
    "--optimizer",
    type=click.Choice(["agentic", "mipro", "textgrad"]),
    default="agentic",
    help="Optimizer: agentic (default, LLM critique), mipro (DSPy), textgrad (TGD). "
         "Note: mipro/textgrad require CGF_ENABLE_PROGRAMMATIC=true",
)
@click.option(
    "-i",
    "--iterations",
    type=int,
    default=2,
    help="Max iterations per section (default: 2)",
)
@click.option(
    "--min-tests",
    type=int,
    default=6,
    help="Minimum deterministic tests for programmatic optimization (default: 6)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Analyze and plan only, don't run optimization",
)
@click.option(
    "--coherence/--no-coherence",
    "enable_coherence",
    default=True,
    help="Enable/disable coherence analysis pass (default: enabled)",
)
@click.option(
    "--auto-reorder",
    is_flag=True,
    help="Automatically reorder sections based on coherence analysis",
)
@click.option(
    "--eval-model",
    type=click.Choice(["sonnet", "haiku", "opus"]),
    default=None,
    help="Override model for test evaluation (only used in programmatic mode)",
)
def cli(
    agent_path: Path,
    test_suite_path: Path | None,
    criteria_path: Path,
    workspace_dir: Path,
    optimizer: str,
    iterations: int,
    min_tests: int,
    verbose: bool,
    dry_run: bool,
    enable_coherence: bool,
    auto_reorder: bool,
    eval_model: str | None,
) -> None:
    """Run section-based prompt optimization.

    Default mode is agentic (LLM critique only, no tests required).
    This is faster and works without test suite generation.

    Programmatic Mode (CGF_ENABLE_PROGRAMMATIC=true):
        Enables DSPy/TextGrad optimization for sections with 6+ deterministic
        tests. Requires --test-suite to be provided.
    """
    # Check if programmatic mode is enabled via environment variable
    programmatic_enabled = os.environ.get("CGF_ENABLE_PROGRAMMATIC", "").lower() == "true"

    # Validate test_suite_path is provided when using programmatic mode
    if programmatic_enabled and test_suite_path is None:
        console.print(
            "[red]Error:[/red] --test-suite is required when "
            "CGF_ENABLE_PROGRAMMATIC=true"
        )
        sys.exit(1)

    # In agentic mode (default), we don't need tests
    agentic_mode = not programmatic_enabled
    mode_str = "Agentic (default)" if agentic_mode else "Programmatic"
    console.print(
        Panel.fit(
            f"[bold]CGF Section-Based Optimizer[/bold]\n"
            f"Mode: {mode_str}",
            border_style="yellow" if agentic_mode else "cyan",
        )
    )

    # Display configuration
    table = Table(show_header=False, box=None)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Agent", str(agent_path))
    table.add_row(
        "Test Suite",
        "(not required)" if agentic_mode else str(test_suite_path),
    )
    table.add_row("Criteria", str(criteria_path))
    table.add_row("Workspace", str(workspace_dir))
    table.add_row("Mode", mode_str)
    if not agentic_mode:
        table.add_row("Optimizer", optimizer)
        table.add_row("Min Tests", str(min_tests))
    table.add_row("Iterations/Section", str(iterations))
    table.add_row("Coherence Pass", "Yes" if enable_coherence else "No")
    table.add_row("Auto-Reorder", "Yes" if auto_reorder else "No")
    if not agentic_mode:
        table.add_row("Eval Model", eval_model or "(agent default)")
    console.print(table)
    console.print()

    # Create config
    config = SectionOptimizationConfig(
        agent_path=agent_path,
        test_suite_path=test_suite_path,
        criteria_path=criteria_path,
        workspace_dir=workspace_dir,
        optimizer=optimizer,
        iterations_per_section=iterations,
        min_tests_for_programmatic=min_tests,
        verbose=verbose,
        enable_coherence_pass=enable_coherence,
        auto_reorder_sections=auto_reorder,
        eval_model=eval_model,
        agentic_mode=agentic_mode,
    )

    # Create orchestrator
    orchestrator = SectionOptimizer(config)

    if dry_run:
        # Dry run - just analyze and plan
        if agentic_mode:
            console.print(
                "[bold]DRY RUN MODE (Agentic)[/bold] - "
                "Will use LLM critique for all sections...\n"
            )
            console.print(
                "[dim]In agentic mode (default), all sections use LLM "
                "self-critique (no test-based strategies)[/dim]\n"
            )
            return
        console.print("[bold]DRY RUN MODE (Programmatic)[/bold] - Analyzing...\n")
        asyncio.run(_run_analyze_only(orchestrator))
        return

    # Run full optimization
    with console.status("Running section-based optimization..."):
        result = asyncio.run(orchestrator.run())

    # Display results
    console.print()

    if result.success:
        console.print(Panel.fit(
            f"[bold green]Optimization Complete[/bold green]\n\n"
            f"Output: {result.output_path}\n"
            f"Duration: {result.total_duration_seconds:.1f}s",
            border_style="green",
        ))

        # Show section results
        table = Table(title="Section Results")
        table.add_column("Section")
        table.add_column("Strategy")
        table.add_column("Original")
        table.add_column("Final")
        table.add_column("Improvement")
        table.add_column("Duration")

        for sr in result.section_results:
            improvement_str = ""
            if sr.improvement > 0:
                improvement_str = f"[green]+{sr.improvement_percent:.1f}%[/green]"
            elif sr.error:
                improvement_str = f"[red]{sr.error[:20]}...[/red]"
            else:
                improvement_str = "-"

            table.add_row(
                sr.section.value,
                sr.strategy.value,
                f"{sr.original_score:.3f}" if sr.original_score else "-",
                f"{sr.final_score:.3f}" if sr.final_score else "-",
                improvement_str,
                f"{sr.duration_seconds:.1f}s" if sr.duration_seconds else "-",
            )

        console.print(table)

        # Save result summary to sessions/ folder
        sessions_dir = workspace_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        summary_path = sessions_dir / "section_optimization_summary.json"
        summary_path.write_text(json.dumps(result.to_dict(), indent=2))
        console.print(f"\nSummary saved to: {summary_path}")

    else:
        console.print(Panel.fit(
            f"[bold red]Optimization Failed[/bold red]\n\n"
            f"Error: {result.error}",
            border_style="red",
        ))
        sys.exit(1)


async def _run_analyze_only(orchestrator: SectionOptimizer) -> None:
    """Run analyze and plan phases only."""
    # Run analyze
    await orchestrator._analyze()

    console.print("[bold]Coverage Analysis:[/bold]")
    table = Table()
    table.add_column("Section")
    table.add_column("Strategy")
    table.add_column("Tests")
    table.add_column("Quantitative")
    table.add_column("Reason")

    for section in orchestrator._sections:
        strategy_color = {
            "programmatic": "green",
            "agentic": "yellow",
            "preserve": "dim",
        }.get(section.strategy.value, "white")

        table.add_row(
            section.section.value,
            f"[{strategy_color}]{section.strategy.value}[/{strategy_color}]",
            str(section.test_count),
            str(section.quantitative_count),
            section.reason,
        )

    console.print(table)

    # Count strategies
    programmatic = len([
        s for s in orchestrator._sections
        if s.strategy.value == "programmatic"
    ])
    agentic = len([
        s for s in orchestrator._sections
        if s.strategy.value == "agentic"
    ])
    preserve = len([
        s for s in orchestrator._sections
        if s.strategy.value == "preserve"
    ])

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Programmatic sections: {programmatic}")
    console.print(f"  Agentic sections: {agentic}")
    console.print(f"  Preserve sections: {preserve}")
    console.print(
        "\n[dim]Run without --dry-run to execute optimization[/dim]"
    )


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
