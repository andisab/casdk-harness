"""Integration tests for Tier 1 + Tier 2 MCP server loading via SDK.

This module tests that MCP servers are properly loaded through the MCPConfigLoader
and accessible via the AgentSession.

Phase 1C Simplified Architecture: 2-tier structure with uniform subprocess handling.
- Tier 1 (Fast - 30s timeout): git, docker, context7, github (all subprocess via stdio)
- Tier 2 (Slow - 120s timeout): memory, playwright, joplin, excel-haris-musa (npx/uvx subprocess via stdio)

All servers treated uniformly as subprocess servers using stdio protocol.
Supports both npx (Node.js) and uvx (Python) package managers.

Cost: Free (no API calls, just initialization tests)
Duration: < 15 seconds total (npx/uvx may take a few seconds to start)
"""

import pytest

from harness.agent import AgentSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_session_initializes_with_tier1_and_tier2_servers():
    """
    Test that AgentSession initializes successfully with Tier 1 + Tier 2 MCP servers.

    Purpose: Verify MCPConfigLoader loads Tier 1 and Tier 2 servers and AgentSession
    can be created without errors or timeouts.

    Expected behavior:
    - AgentSession initialization succeeds
    - Tier 1 servers (git, docker, context7, github) are loaded
    - Tier 2 servers (memory, playwright, joplin) are loaded (if API keys present)
    - All servers loaded as stdio subprocess servers
    - No timeout errors during initialization

    Cost: Free
    """
    # Create agent session (loads Tier 1 + Tier 2 MCP servers via MCPConfigLoader)
    session = AgentSession(agent_name="test-tier1-2")

    # Verify session initialized
    assert session is not None
    assert session.agent_name == "test-tier1-2"

    # Verify servers loaded
    assert session.mcp_servers is not None
    assert isinstance(session.mcp_servers, dict)

    # Verify Tier 1 servers present (github conditional on API key)
    assert "git" in session.mcp_servers, "Git MCP server should be loaded (Tier 1)"
    assert "docker" in session.mcp_servers, "Docker MCP server should be loaded (Tier 1)"
    assert "context7" in session.mcp_servers, "Context7 MCP server should be loaded (Tier 1)"
    # Note: github requires API key, may be skipped

    # Verify Tier 2 servers present (memory and playwright have no API key requirements)
    assert "memory" in session.mcp_servers, "Memory MCP server should be loaded (Tier 2)"
    assert "playwright" in session.mcp_servers, "Playwright MCP server should be loaded (Tier 2)"
    # Note: joplin requires API keys, may be skipped


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_mcp_server_architecture():
    """
    Test that MCP servers use the correct transport type based on their loading method.

    Purpose: Verify the hybrid architecture where in-process servers use SDK transport
    and subprocess servers use stdio transport.

    Expected behavior (Phase 1C Hybrid Architecture):
    - In-process servers (Method A): type="sdk" with server instance
    - Subprocess servers (Method B): type="stdio" with command, args

    Cost: Free
    """
    session = AgentSession(agent_name="test-hybrid-architecture")

    # Check in-process servers (Method A) - type="sdk"
    inprocess_servers = ["git", "docker", "context7", "memory"]  # Always loaded

    for server_name in inprocess_servers:
        server_config = session.mcp_servers.get(server_name)
        assert server_config is not None, f"{server_name} server should be loaded"
        assert isinstance(server_config, dict), f"{server_name} should be a dict config"
        assert server_config.get("type") == "sdk", (
            f"{server_name} should be type 'sdk' (in-process), got '{server_config.get('type')}'"
        )
        assert "instance" in server_config, f"{server_name} should have 'instance' field"

    # Check subprocess servers (Method B) - type="stdio"
    subprocess_servers = ["playwright", "excel-haris-musa"]  # No API keys required

    for server_name in subprocess_servers:
        server_config = session.mcp_servers.get(server_name)
        assert server_config is not None, f"{server_name} server should be loaded"
        assert isinstance(server_config, dict), f"{server_name} should be a dict config"
        assert server_config.get("type") == "stdio", (
            f"{server_name} should be type 'stdio' (subprocess), got '{server_config.get('type')}'"
        )
        assert "command" in server_config, f"{server_name} should have 'command' field"
        assert "args" in server_config, f"{server_name} should have 'args' field"
        assert isinstance(server_config["args"], list), f"{server_name} args should be a list"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_loader_handles_missing_config_gracefully():
    """
    Test that MCPConfigLoader handles missing .mcp.json gracefully.

    Purpose: Verify that if .mcp.json is missing, the agent can still
    initialize with an empty mcp_servers dict (graceful degradation).

    Expected behavior:
    - AgentSession initialization succeeds even if .mcp.json missing
    - mcp_servers is empty dict
    - Warning logged but no exception raised

    Note: This test would need to mock the config file path to test,
    so we'll skip it for now. The actual handling is tested in unit tests.

    Cost: Free
    """
    # This behavior is tested in unit tests for MCPConfigLoader
    # and in agent.py:_load_mcp_servers_tier1 error handling
    pytest.skip("Graceful handling tested in unit tests")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tier1_and_tier2_loading_performance():
    """
    Test that Tier 1 + Tier 2 server loading is reasonably fast (< 15 seconds).

    Purpose: Verify Tier 1 + Tier 2 servers load without timeout issues.
    - Tier 1 (git, docker, context7, github) are subprocess via stdio
    - Tier 2 (memory, playwright, joplin) are subprocess via stdio
    - All servers may take a few seconds for npx/python subprocess startup

    Expected behavior:
    - AgentSession initialization completes in < 15 seconds
    - No timeout errors
    - 5-7 servers loaded (3-4 from Tier 1 + 2-3 from Tier 2, depending on API keys)

    Cost: Free
    """
    import time

    start_time = time.time()
    session = AgentSession(agent_name="test-tier1-2-performance")
    elapsed = time.time() - start_time

    # Tier 1 + Tier 2 should complete within 15 seconds
    # (subprocess startup may take several seconds, especially for npx servers)
    assert elapsed < 15.0, f"Tier 1 + 2 loading took {elapsed:.2f}s, expected < 15s"

    # Verify servers loaded
    # - Tier 1: 3-4 servers (git, docker, context7 always; github conditional on API key)
    # - Tier 2: 3-4 servers (memory, playwright, excel-haris-musa always; joplin conditional on API keys)
    assert len(session.mcp_servers) >= 6, f"Should have at least 6 servers (Tier 1 + Tier 2 no-key), got {len(session.mcp_servers)}"
    assert len(session.mcp_servers) <= 8, f"Should have at most 8 servers (all tiers), got {len(session.mcp_servers)}"

    # Verify we have Tier 1 servers that don't require API keys
    tier1_no_key = ["git", "docker", "context7"]
    tier1_count = sum(1 for s in tier1_no_key if s in session.mcp_servers)

    assert tier1_count == 3, f"Should have all 3 Tier 1 no-key servers, got {tier1_count}"

    # Verify we have Tier 2 servers that don't require API keys
    assert "memory" in session.mcp_servers, "Memory server (Tier 2) should always be loaded"
    assert "playwright" in session.mcp_servers, "Playwright server (Tier 2) should always be loaded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_uvx_based_server_initialization():
    """
    Test that uvx-based MCP servers (Python) are properly configured.

    Purpose: Verify that uvx (Python package manager) based servers are loaded
    with the correct structure, separate from npx (Node.js) servers.

    Expected behavior:
    - excel-haris-musa server is loaded (Tier 2, no API keys required)
    - Server uses 'uvx' command (not 'npx')
    - Server has standard stdio structure

    This validates that the MCP loader supports both npx and uvx package managers.

    Cost: Free
    """
    session = AgentSession(agent_name="test-uvx-server")

    # Verify excel-haris-musa (uvx-based) is loaded
    assert "excel-haris-musa" in session.mcp_servers, (
        "excel-haris-musa (uvx) server should be loaded (Tier 2, no API key required)"
    )

    # Get server config
    excel_config = session.mcp_servers["excel-haris-musa"]

    # Verify it's a stdio subprocess config
    assert isinstance(excel_config, dict), "excel-haris-musa should be a dict config"
    assert excel_config.get("type") == "stdio", "excel-haris-musa should be type 'stdio'"

    # Verify it uses uvx command (not npx)
    assert excel_config.get("command") == "uvx", (
        f"excel-haris-musa should use 'uvx' command, got '{excel_config.get('command')}'"
    )

    # Verify args structure
    assert "args" in excel_config, "excel-haris-musa should have 'args' field"
    assert isinstance(excel_config["args"], list), "excel-haris-musa args should be a list"
    assert "excel-mcp-server" in excel_config["args"], (
        "excel-haris-musa args should include 'excel-mcp-server' package"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mixed_npx_and_uvx_servers():
    """
    Test that both npx (Node.js) and uvx (Python) servers coexist properly.

    Purpose: Verify the MCP loader correctly handles a mix of package managers
    in the same session.

    Expected behavior:
    - npx servers (playwright) are loaded with 'npx' command
    - uvx servers (excel-haris-musa) are loaded with 'uvx' command
    - Both types use uniform stdio subprocess structure

    Cost: Free
    """
    session = AgentSession(agent_name="test-mixed-package-managers")

    # Verify both types of servers are present
    assert "playwright" in session.mcp_servers, "npx server (playwright) should be loaded"
    assert "excel-haris-musa" in session.mcp_servers, "uvx server (excel-haris-musa) should be loaded"

    # Get configs
    playwright_config = session.mcp_servers["playwright"]
    excel_config = session.mcp_servers["excel-haris-musa"]

    # Verify different package managers
    assert playwright_config.get("command") == "npx", "playwright should use 'npx'"
    assert excel_config.get("command") == "uvx", "excel-haris-musa should use 'uvx'"

    # Both should have uniform stdio structure
    for name, config in [("playwright", playwright_config), ("excel-haris-musa", excel_config)]:
        assert config.get("type") == "stdio", f"{name} should be stdio type"
        assert "args" in config, f"{name} should have args"
        assert isinstance(config["args"], list), f"{name} args should be a list"
