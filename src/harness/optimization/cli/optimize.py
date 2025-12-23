"""CLI command for running optimization pipelines.

Usage:
    python -m harness.optimization.cli.optimize \\
        --agent agents/configs/python-expert.md \\
        --test-suite tests/optimization/python_expert_tests.yaml \\
        --optimizer dspy \\
        --output optimized_prompt.md \\
        --iterations 10
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from harness.optimization.optimizers import (
    DSPY_AVAILABLE,
    TEXTGRAD_AVAILABLE,
    OptimizationConfig,
    OptimizerType,
)
from harness.optimization.pipeline import OptimizationRun, OutputFormat, PipelineConfig

console = Console()


def print_banner() -> None:
    """Print the CLI banner."""
    console.print(
        Panel.fit(
            "[bold blue]CGF Optimization CLI[/bold blue]\n"
            "[dim]Single-Agent Prompt Optimization[/dim]",
            border_style="blue",
        )
    )


def print_availability() -> None:
    """Print optimizer availability status."""
    table = Table(title="Optimizer Availability", show_header=True)
    table.add_column("Optimizer", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Install Command", style="dim")

    dspy_status = "[green]✓ Available[/green]" if DSPY_AVAILABLE else "[red]✗ Not installed[/red]"
    textgrad_status = "[green]✓ Available[/green]" if TEXTGRAD_AVAILABLE else "[red]✗ Not installed[/red]"

    table.add_row("DSPy MIPROv2", dspy_status, "pip install 'dspy-ai>=2.5.0'")
    table.add_row("TextGrad TGD", textgrad_status, "pip install 'textgrad>=0.1.6'")

    console.print(table)


def print_result_summary(run: OptimizationRun) -> None:
    """Print optimization result summary."""
    result = run.result
    summary = run.get_summary()

    status_style = "green" if result.success else "red"
    status_text = "✓ Success" if result.success else "✗ Failed"

    table = Table(title="Optimization Results", show_header=False, box=None)
    table.add_column("Metric", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Status", f"[{status_style}]{status_text}[/{status_style}]")
    table.add_row("Agent", summary.agent_name)
    table.add_row("Test Suite", summary.suite_name)
    table.add_row("Optimizer", summary.optimizer_type)
    table.add_row("", "")
    table.add_row("Original Score", f"{result.original_score:.4f}")
    table.add_row("Final Score", f"{result.final_score:.4f}")

    improvement_style = "green" if result.improvement > 0 else "red" if result.improvement < 0 else "white"
    improvement_sign = "+" if result.improvement > 0 else ""
    table.add_row(
        "Improvement",
        f"[{improvement_style}]{improvement_sign}{result.improvement:.4f} ({improvement_sign}{result.improvement_percent:.1f}%)[/{improvement_style}]"
    )

    table.add_row("", "")
    table.add_row("Iterations", str(result.total_iterations))
    table.add_row("Duration", f"{result.total_duration_seconds:.1f}s")

    if summary.output_path:
        table.add_row("Output", summary.output_path)

    if result.error:
        table.add_row("Error", f"[red]{result.error}[/red]")

    console.print(table)


@click.command()
@click.option(
    "--agent", "-a",
    required=False,  # Made optional for --check-availability
    type=click.Path(exists=True, path_type=Path),
    help="Path to agent definition file (.md with YAML frontmatter)",
)
@click.option(
    "--test-suite", "-t",
    required=False,  # Made optional for --check-availability
    type=click.Path(exists=True, path_type=Path),
    help="Path to test suite file (YAML/JSON)",
)
@click.option(
    "--optimizer", "-o",
    type=click.Choice(["dspy", "textgrad"]),
    default="dspy",
    help="Optimizer to use (default: dspy)",
)
@click.option(
    "--output", "-O",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for optimized prompt",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["markdown", "json", "yaml"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--iterations", "-i",
    type=int,
    default=10,
    help="Maximum optimization iterations (default: 10)",
)
@click.option(
    "--candidates", "-c",
    type=int,
    default=5,
    help="Number of prompt candidates per iteration (default: 5)",
)
@click.option(
    "--learning-rate", "-l",
    type=float,
    default=0.1,
    help="Learning rate for optimization (default: 0.1)",
)
@click.option(
    "--early-stop",
    type=float,
    default=0.01,
    help="Early stopping threshold (default: 0.01)",
)
@click.option(
    "--temperature",
    type=float,
    default=0.7,
    help="Temperature for prompt generation (default: 0.7)",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility",
)
@click.option(
    "--save-iterations",
    is_flag=True,
    default=False,
    help="Save intermediate iteration results",
)
@click.option(
    "--iterations-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for iteration results",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate config without running optimization",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress all output except errors",
)
@click.option(
    "--check-availability",
    is_flag=True,
    default=False,
    help="Check optimizer availability and exit",
)
def cli(
    agent: Path,
    test_suite: Path,
    optimizer: str,
    output: Path | None,
    format: str,
    iterations: int,
    candidates: int,
    learning_rate: float,
    early_stop: float,
    temperature: float,
    seed: int | None,
    save_iterations: bool,
    iterations_dir: Path | None,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
    check_availability: bool,
) -> None:
    """Run single-agent prompt optimization.

    Optimizes an agent's system prompt using DSPy MIPROv2 or TextGrad TGD
    based on performance on a test suite.

    Examples:

        # Basic optimization with DSPy
        python -m harness.optimization.cli.optimize \\
            --agent agents/configs/python-expert.md \\
            --test-suite tests/optimization/python_expert_tests.yaml

        # TextGrad with custom iterations
        python -m harness.optimization.cli.optimize \\
            --agent agents/configs/python-expert.md \\
            --test-suite tests/optimization/python_expert_tests.yaml \\
            --optimizer textgrad \\
            --iterations 20

        # Save all intermediate results
        python -m harness.optimization.cli.optimize \\
            --agent agents/configs/python-expert.md \\
            --test-suite tests/optimization/python_expert_tests.yaml \\
            --save-iterations \\
            --iterations-dir ./optimization_history/
    """
    if not quiet:
        print_banner()

    if check_availability:
        print_availability()
        return

    # Validate required options when not checking availability
    if agent is None:
        console.print("[red]Error:[/red] --agent is required")
        sys.exit(1)
    if test_suite is None:
        console.print("[red]Error:[/red] --test-suite is required")
        sys.exit(1)

    # Create optimization config
    opt_config = OptimizationConfig(
        max_iterations=iterations,
        early_stopping_threshold=early_stop,
        learning_rate=learning_rate,
        num_candidates=candidates,
        temperature=temperature,
        seed=seed,
        verbose=verbose,
    )

    # Create pipeline config
    try:
        pipeline_config = PipelineConfig(
            agent_path=agent,
            test_suite_path=test_suite,
            optimizer_type=OptimizerType(optimizer),
            output_path=output,
            output_format=OutputFormat(format),
            optimization_config=opt_config,
            save_iterations=save_iterations,
            iterations_dir=iterations_dir,
            verbose=verbose,
            dry_run=dry_run,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    # Run optimization
    run = OptimizationRun(pipeline_config)

    if not quiet:
        console.print(f"\n[cyan]Run ID:[/cyan] {run.run_id}")
        console.print(f"[cyan]Agent:[/cyan] {agent}")
        console.print(f"[cyan]Test Suite:[/cyan] {test_suite}")
        console.print(f"[cyan]Optimizer:[/cyan] {optimizer}")
        console.print(f"[cyan]Max Iterations:[/cyan] {iterations}")
        console.print()

    try:
        if not quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running optimization...", total=None)
                result = asyncio.run(run.execute())
                progress.update(task, completed=True)
        else:
            result = asyncio.run(run.execute())

        if not quiet:
            console.print()
            print_result_summary(run)

        if not result.success:
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Optimization cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
