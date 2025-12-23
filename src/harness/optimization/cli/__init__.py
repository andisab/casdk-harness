"""CLI module for optimization commands.

Provides command-line interface for running optimization pipelines.

Usage:
    python -m harness.optimization.cli.optimize \\
        --agent agents/configs/python-expert.md \\
        --test-suite tests/optimization/python_expert_tests.yaml \\
        --optimizer dspy \\
        --output optimized_prompt.md \\
        --iterations 10
"""

from harness.optimization.cli.optimize import cli, main

__all__ = ["cli", "main"]
