"""Integration tests for Docker MCP server."""

import pytest

from mcp_servers.docker.server import list_containers


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.asyncio
async def test_list_containers():
    """
    Test Docker MCP list_containers tool.

    Requires Docker to be running on the host system.
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
    Test Docker MCP list_containers with all=True.

    Shows both running and stopped containers.
    """
    result = await list_containers({"all": True})

    assert "content" in result
    content_text = result["content"][0]["text"]

    # Should return valid response
    assert isinstance(content_text, str)


# Note: container_logs and container_stats tests would require
# a known container to be running. These are better suited for
# E2E tests with a controlled environment.
