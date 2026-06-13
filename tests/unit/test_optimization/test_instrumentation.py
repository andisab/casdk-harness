"""Unit tests for optimization instrumentation (timeouts, progress logging)."""

from __future__ import annotations

import os
from unittest.mock import patch

from harness.optimization.optimizers.optimizer_utils import (
    DEFAULT_ITERATION_TIMEOUT,
    ITERATION_TIMEOUT_ENV_VAR,
    get_iteration_timeout,
)
from harness.optimization.runners.batch_runner import _format_elapsed


class TestIterationTimeout:
    """Tests for iteration timeout configuration."""

    def test_default_iteration_timeout(self) -> None:
        """Test default iteration timeout value."""
        with patch.dict(os.environ, {}, clear=True):
            if ITERATION_TIMEOUT_ENV_VAR in os.environ:
                del os.environ[ITERATION_TIMEOUT_ENV_VAR]

            timeout = get_iteration_timeout()
            assert timeout == DEFAULT_ITERATION_TIMEOUT
            assert timeout == 1800  # 30 minutes

    def test_custom_iteration_timeout_from_env(self) -> None:
        """Test custom iteration timeout from environment variable."""
        with patch.dict(os.environ, {ITERATION_TIMEOUT_ENV_VAR: "600"}):
            timeout = get_iteration_timeout()
            assert timeout == 600.0

    def test_invalid_iteration_timeout_uses_default(self) -> None:
        """Test invalid timeout value falls back to default."""
        with patch.dict(os.environ, {ITERATION_TIMEOUT_ENV_VAR: "invalid"}):
            timeout = get_iteration_timeout()
            assert timeout == DEFAULT_ITERATION_TIMEOUT

    def test_empty_env_var_uses_default(self) -> None:
        """Test empty env var uses default timeout."""
        with patch.dict(os.environ, {ITERATION_TIMEOUT_ENV_VAR: ""}):
            timeout = get_iteration_timeout()
            assert timeout == DEFAULT_ITERATION_TIMEOUT


class TestProgressFormatting:
    """Tests for progress logging formatting."""

    def test_format_elapsed_seconds(self) -> None:
        """Test formatting elapsed time in seconds."""
        assert _format_elapsed(0.0) == "000.0s"
        assert _format_elapsed(5.5) == "005.5s"
        assert _format_elapsed(45.2) == "045.2s"
        assert _format_elapsed(59.9) == "059.9s"

    def test_format_elapsed_minutes(self) -> None:
        """Test formatting elapsed time in minutes."""
        assert _format_elapsed(60) == "01m00s"
        assert _format_elapsed(90) == "01m30s"
        assert _format_elapsed(125) == "02m05s"
        assert _format_elapsed(3600) == "60m00s"

    def test_format_elapsed_boundary(self) -> None:
        """Test formatting at the minute boundary."""
        assert _format_elapsed(59.9) == "059.9s"
        assert _format_elapsed(60.0) == "01m00s"


class TestTimeoutEnvVarConsistency:
    """Tests for env var consistency."""

    def test_env_var_name(self) -> None:
        """Test the timeout env var name."""
        assert ITERATION_TIMEOUT_ENV_VAR == "CGF_ITERATION_TIMEOUT"

    def test_default_timeout(self) -> None:
        """Test the default timeout value."""
        assert DEFAULT_ITERATION_TIMEOUT == 1800
