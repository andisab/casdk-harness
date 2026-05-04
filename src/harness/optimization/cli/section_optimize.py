"""CLI for section-based prompt optimization.

Uses agentic (LLM critique) optimization for all sections.

Usage:
    python -m harness.optimization.cli.section_optimize \\
        --agent .claude/agents/python-expert.md \\
        --criteria workspace/python-expert/research/eval_criteria.yaml \\
        --workspace workspace/python-expert
"""

from __future__ import annotations

import asyncio
import json
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
    required=False,
    help="Path to test suite (YAML). Optional, used for validation.",
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
    "-i",
    "--iterations",
    type=int,
    default=2,
    help="Max iterations per section (default: 2)",
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
    help="Override model for test evaluation",
)
def cli(
    agent_path: Path,
    test_suite_path: Path | None,
    criteria_path: Path,
    workspace_dir: Path,
    iterations: int,
    verbose: bool,
    dry_run: bool,
    enable_coherence: bool,
    auto_reorder: bool,
    eval_model: str | None,
) -> None:
    """Run section-based prompt optimization.

    Uses agentic (LLM critique) optimization for all sections.
    """
    console.print(
        Panel.fit(
            "[bold]CGF Section-Based Optimizer[/bold]\n"
            "Mode: Agentic",
            border_style="yellow",
        )
    )

    # Display configuration
    table = Table(show_header=False, box=None)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Agent", str(agent_path))
    table.add_row(
        "Test Suite",
        str(test_suite_path) if test_suite_path else "(not required)",
    )
    table.add_row("Criteria", str(criteria_path))
    table.add_row("Workspace", str(workspace_dir))
    table.add_row("Mode", "Agentic")
    table.add_row("Iterations/Section", str(iterations))
    table.add_row("Coherence Pass", "Yes" if enable_coherence else "No")
    table.add_row("Auto-Reorder", "Yes" if auto_reorder else "No")
    console.print(table)
    console.print()

    # Create config
    config = SectionOptimizationConfig(
        agent_path=agent_path,
        test_suite_path=test_suite_path,
        criteria_path=criteria_path,
        workspace_dir=workspace_dir,
        iterations_per_section=iterations,
        verbose=verbose,
        enable_coherence_pass=enable_coherence,
        auto_reorder_sections=auto_reorder,
        eval_model=eval_model,
    )

    # Create orchestrator
    orchestrator = SectionOptimizer(config)

    if dry_run:
        console.print(
            "[bold]DRY RUN MODE[/bold] - "
            "Will use LLM critique for all sections...\n"
        )
        console.print(
            "[dim]All sections use LLM self-critique "
            "(no test-based strategies)[/dim]\n"
        )
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


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
