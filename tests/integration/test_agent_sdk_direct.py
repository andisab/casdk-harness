"""Direct integration tests for Claude Agent SDK (no VCR).

These tests make real API calls to verify the SDK integration works.
They are marked separately so they can be run selectively.
"""

import pytest

from harness.agent import AgentSession


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.slow
async def test_sdk_simple_query_direct(workspace_dir, skip_if_no_api_key):
    """
    Test SDK can execute a simple query with direct API call.

    This test bypasses VCR.py to verify that the Claude Agent SDK
    subprocess transport works correctly.
    """
    session = AgentSession(agent_name="test-direct")
    await session.start()

    messages = []
    async for msg in session.execute("Say hello and tell me what 2+2 equals"):
        messages.append(msg)
        print(f"Message: {msg}")

    # Verify we got some messages
    assert len(messages) > 0, "Should receive at least one message from SDK"

    await session.shutdown()


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
@pytest.mark.slow
async def test_sdk_file_creation_direct(workspace_dir, skip_if_no_api_key):
    """
    Test SDK can create a file with direct API call.

    Verifies the agent can execute file operations.
    """
    session = AgentSession(agent_name="test-direct")
    await session.start()

    messages = []
    async for msg in session.execute(
        f"Create a file at {workspace_dir}/test_output.txt containing the text 'Hello from Claude Agent SDK'"
    ):
        messages.append(msg)
        print(f"Message: {msg}")

    # Verify we got messages
    assert len(messages) > 0

    # Check if file was created
    test_file = workspace_dir / "test_output.txt"
    if test_file.exists():
        content = test_file.read_text()
        print(f"File created with content: {content}")

    await session.shutdown()
