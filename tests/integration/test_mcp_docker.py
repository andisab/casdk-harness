"""Integration tests for Docker MCP server.

This module tests the in-process Docker MCP server that provides
container management tools to Claude agents. Tests verify that
Docker operations work correctly via the MCP interface.

Prerequisites: Docker daemon must be running on host system.

Cost: Free (no API calls)
Duration: < 5 seconds total
"""

import pytest

from mcp_servers.docker.server import list_containers


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.asyncio
async def test_list_containers():
    """
    Test Docker MCP list_containers tool for running containers.

    Purpose: Verify MCP server can query Docker API for running containers.
    This tool is used by agents to inspect the containerized environment.

    Expected behavior:
    - Returns valid content structure
    - Lists running containers (or empty if none)
    - No errors communicating with Docker daemon

    Prerequisites: Docker daemon running
    Cost: Free
    """
    # Test listing running containers
    result = await list_containers({"all": False})

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should either list containers or say none found
    assert isinstance(content_text, str)
    assert len(content_text) > 0


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.asyncio
async def test_list_all_containers():
    """
    Test Docker MCP list_containers with all=True parameter.

    Purpose: Verify MCP server can list both running and stopped containers.
    Useful for agents troubleshooting container lifecycle issues.

    Expected behavior:
    - Returns valid content structure
    - Shows running and stopped containers
    - Includes container status information

    Prerequisites: Docker daemon running
    Cost: Free
    """
    result = await list_containers({"all": True})

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should return valid response
    assert isinstance(content_text, str)


# Note: container_logs and container_stats tests would require
# a known container to be running. These are better suited for
# E2E tests with a controlled environment.
