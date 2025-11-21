"""Pytest configuration and shared fixtures for test suite.

Provides fixtures for:
- Workspace directory management
- Token budget tracking
- API key handling
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Token budget tracking (1M token limit per test session)
_token_budget = {"used": 0, "limit": 1_000_000}


@pytest.fixture
def api_key() -> str | None:
    """
    Get Anthropic API key from environment.

    Returns:
        API key if set, None otherwise
    """
    return os.getenv("ANTHROPIC_API_KEY")


@pytest.fixture
def workspace_dir() -> Generator[Path, None, None]:
    """
    Create temporary workspace directory for tests.

    Yields:
        Path to temporary workspace directory

    Cleanup:
        Removes temporary directory after test
    """
    with tempfile.TemporaryDirectory(prefix="claude_test_") as tmpdir:
        workspace_path = Path(tmpdir)
        yield workspace_path
        # Cleanup happens automatically


@pytest.fixture(scope="session")
def token_budget() -> dict:
    """
    Track token usage across test session.

    Returns:
        Dictionary with 'used' and 'limit' keys
    """
    return _token_budget


@pytest.fixture
def skip_if_no_api_key(api_key: str | None) -> None:
    """
    Skip test if ANTHROPIC_API_KEY is not set.

    Args:
        api_key: API key from environment

    Raises:
        pytest.skip: If API key not available
    """
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set - skipping test requiring API access")


@pytest.fixture
def check_token_budget(token_budget: dict) -> None:
    """
    Check if token budget has been exceeded.

    Args:
        token_budget: Token budget dictionary

    Raises:
        pytest.fail: If token budget exceeded
    """
    if token_budget["used"] >= token_budget["limit"]:
        pytest.fail(
            f"Token budget exceeded: {token_budget['used']}/{token_budget['limit']}"
        )


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest with custom markers and settings.

    Args:
        config: Pytest configuration object
    """
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests with real API calls",
    )
    config.addinivalue_line(
        "markers",
        "e2e: marks tests as end-to-end tests",
    )
    config.addinivalue_line(
        "markers",
        "requires_api_key: marks tests that require ANTHROPIC_API_KEY",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (taking >30 seconds)",
    )
    config.addinivalue_line(
        "markers",
        "docker: marks tests that require Docker daemon to be running",
    )
    config.addinivalue_line(
        "markers",
        "redis: marks tests that require Redis server to be running",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """
    Modify test collection to handle markers.

    Args:
        config: Pytest configuration
        items: List of test items
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    for item in items:
        # Skip tests requiring API key if not set
        if "requires_api_key" in item.keywords and not api_key:
            item.add_marker(
                pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
            )
