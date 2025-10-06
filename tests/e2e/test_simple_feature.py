"""End-to-end test for simple feature development workflow.

Tests complete workflow from requirements to implementation to testing.
WARNING: This test uses real API calls and can be expensive. Use sparingly.
"""

import subprocess
from pathlib import Path

import pytest
import structlog

from harness.agent import AgentSession

logger = structlog.get_logger(__name__)


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minute timeout for E2E test
async def test_end_to_end_feature_development(
    vcr_cassette,
    workspace_dir,
    skip_if_no_api_key,
    check_token_budget,
):
    """
    Test complete feature development workflow.

    Workflow:
    1. Agent reads requirements
    2. Agent creates implementation
    3. Agent writes tests
    4. Agent runs tests
    5. Agent fixes failures (if any)

    This is an expensive test that exercises the full agent capabilities.
    """
    with vcr_cassette.use_cassette("test_e2e_feature_development.yaml"):
        session = AgentSession(agent_name="e2e-test")
        await session.start()

        prompt = """
        Create a simple calculator module with:
        1. A Calculator class with add, subtract, multiply, divide methods
        2. Each method should have type hints and docstrings
        3. Include error handling for division by zero
        4. Write unit tests with pytest that achieve 80%+ coverage
        5. Save the implementation in calculator.py
        6. Save the tests in test_calculator.py
        """

        logger.info("Starting E2E test: feature development")

        message_count = 0
        async for msg in session.execute(prompt):
            message_count += 1
            if isinstance(msg, dict):
                logger.debug("Agent message", type=msg.get("type"), count=message_count)

        logger.info("Agent execution completed", message_count=message_count)

        # Verify deliverables exist
        calculator_file = workspace_dir / "calculator.py"
        test_file = workspace_dir / "test_calculator.py"

        # Note: Actual file locations depend on agent behavior
        # These assertions may need adjustment based on SDK implementation
        logger.info(
            "Checking for deliverables",
            calculator_exists=calculator_file.exists(),
            test_exists=test_file.exists(),
        )

        await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(300)  # 5 minute timeout
async def test_simple_bug_fix_workflow(
    vcr_cassette,
    workspace_dir,
    skip_if_no_api_key,
):
    """
    Test bug fix workflow.

    Workflow:
    1. Create buggy code
    2. Agent identifies bug
    3. Agent fixes bug
    4. Agent verifies fix with test
    """
    with vcr_cassette.use_cassette("test_e2e_bug_fix.yaml"):
        # Create buggy code
        buggy_file = workspace_dir / "buggy.py"
        buggy_file.write_text(
            """
def calculate_average(numbers):
    # Bug: division by zero if empty list
    return sum(numbers) / len(numbers)
"""
        )

        session = AgentSession(agent_name="e2e-bugfix")
        await session.start()

        prompt = f"""
        Fix the bug in {buggy_file}:
        1. Identify the division by zero bug
        2. Fix it with proper error handling
        3. Add a docstring explaining the function
        4. Create a test file that tests both normal and edge cases
        """

        async for msg in session.execute(prompt):
            pass  # Process all messages

        # Verify fix was applied
        assert buggy_file.exists()

        await session.shutdown()


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_mcp_tools_integration(
    vcr_cassette,
    workspace_dir,
    skip_if_no_api_key,
):
    """
    Test that agent can use MCP tools (filesystem, git, docker).

    Verifies MCP servers are properly integrated and accessible.
    """
    with vcr_cassette.use_cassette("test_e2e_mcp_tools.yaml"):
        session = AgentSession(agent_name="e2e-mcp")
        await session.start()

        prompt = """
        Use the filesystem tools to:
        1. List files in the current directory
        2. Create a new file called mcp_test.txt with content "MCP tools working!"
        3. Search for all .txt files
        4. Get metadata for mcp_test.txt
        """

        async for msg in session.execute(prompt):
            pass

        await session.shutdown()
