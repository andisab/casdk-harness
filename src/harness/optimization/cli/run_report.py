"""CLI entry for regenerating ``sessions/RUN_REPORT.md``.

Useful for re-rendering a finished workspace, or after a kill, or while
iterating on the report template itself.  Reads only existing state
files — never re-runs the pipeline.

Usage:

    python -m harness.optimization.cli.run_report --workspace workspace/iac-team

Or via the Makefile:

    make report SPEC=workspace/iac-team
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from harness.optimization import run_report


@click.command()
@click.option(
    "-w",
    "--workspace",
    "workspace_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
    help="Workspace directory containing SPEC.md + sessions/. "
    "If omitted, auto-discovers a single SPEC.md under ./workspace/.",
)
@click.option(
    "--stdout",
    is_flag=True,
    default=False,
    help="Print rendered report to stdout instead of writing to disk.",
)
def main(workspace_dir: Path | None, stdout: bool) -> None:
    """Re-render the run report for a CGF workspace."""
    if workspace_dir is None:
        workspace_dir = _auto_discover()
    workspace_dir = workspace_dir.resolve()

    if stdout:
        click.echo(run_report.render(workspace_dir))
        return

    target = run_report.write(workspace_dir)
    if target is None:
        click.echo(
            f"No sessions/ directory under {workspace_dir} — "
            "has the pipeline run yet?",
            err=True,
        )
        sys.exit(1)
    click.echo(f"Wrote {target}")


def _auto_discover() -> Path:
    """Find a single SPEC.md under ./workspace/ and return its parent."""
    candidates = list(Path("workspace").glob("**/SPEC.md"))
    if not candidates:
        click.echo(
            "No SPEC.md found under ./workspace/. Pass --workspace explicitly.",
            err=True,
        )
        sys.exit(1)
    if len(candidates) > 1:
        click.echo(
            "Multiple SPEC.md files found; pass --workspace explicitly:",
            err=True,
        )
        for c in candidates:
            click.echo(f"  - {c}", err=True)
        sys.exit(1)
    return candidates[0].parent


if __name__ == "__main__":
    main()
