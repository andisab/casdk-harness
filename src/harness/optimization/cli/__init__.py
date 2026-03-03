"""CLI module for optimization commands.

Provides command-line interface for running section-based optimization.

Usage:
    python -m harness.optimization.cli.section_optimize \\
        --agent agents/configs/python-expert.md \\
        --workspace workspace/python-expert \\
        --iterations 2
"""

from harness.optimization.cli.section_optimize import cli, main

__all__ = ["cli", "main"]
