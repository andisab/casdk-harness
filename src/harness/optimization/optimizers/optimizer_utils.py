"""Shared utilities for optimization modules.

Common functions used across DSPy, TextGrad, and other optimizers.
"""

from __future__ import annotations

import os

# Environment variable for iteration timeout (in seconds)
ITERATION_TIMEOUT_ENV_VAR = "CGF_ITERATION_TIMEOUT"
DEFAULT_ITERATION_TIMEOUT = 1800  # 30 minutes default


def get_iteration_timeout() -> float:
    """Get iteration timeout from environment or use default.

    The timeout can be configured via the CGF_ITERATION_TIMEOUT
    environment variable.

    Returns:
        Timeout in seconds (default 1800 = 30 minutes).
    """
    env_val = os.environ.get(ITERATION_TIMEOUT_ENV_VAR, "")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    return DEFAULT_ITERATION_TIMEOUT


def calculate_backoff_timeout(
    iteration: int,
    base_timeout: int = 300,
    max_timeout: int = 1800,
    multiplier: float = 1.5,
) -> int:
    """Calculate timeout with exponential backoff.

    Increases timeout for later iterations when early iterations
    may have already found good solutions.

    Args:
        iteration: Current iteration number (0-based).
        base_timeout: Base timeout in seconds.
        max_timeout: Maximum timeout cap.
        multiplier: Backoff multiplier per iteration.

    Returns:
        Timeout in seconds.
    """
    timeout = int(base_timeout * (multiplier ** iteration))
    return min(timeout, max_timeout)
