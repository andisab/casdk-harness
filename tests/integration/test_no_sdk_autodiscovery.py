"""Integration test to verify SDK does NOT auto-discover .mcp.json.

This test ensures that .mcp.json in src/harness/config/ prevents
SDK auto-discovery, eliminating the double-loading problem from Phase 1C.

Phase 1C Solution (consolidated in Phase 5):
- .mcp.json located at src/harness/config/.mcp.json
- SDK cwd is /app, only auto-discovers from /app/.mcp.json
- File at /app/src/harness/config/.mcp.json is NOT auto-discovered by SDK
- Only MCPConfigLoader reads it and passes servers via mcp_servers parameter

Cost: Free (no API calls, just initialization)
Duration: < 5 seconds
"""

import pytest

from harness.agent import AgentSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_duplicate_servers_from_sdk_autodiscovery():
    """
    Test that SDK does NOT auto-discover .mcp.json, preventing double-loading.

    Purpose: Verify that .mcp.json at src/harness/config/ eliminates
    SDK auto-discovery and we only see servers loaded via MCPConfigLoader.

    Expected behavior:
    - AgentSession loads exactly the expected number of servers
    - No duplicate server entries
    - Each server name appears exactly once
    - Server count matches expected Tier 1 + Tier 2 count

    If SDK auto-discovered .mcp.json AND we loaded via MCPConfigLoader,
    we would see duplicate entries or unexpected server counts.

    Cost: Free
    """
    session = AgentSession(agent_name="test-no-autodiscovery")

    # Count server entries
    server_names = list(session.mcp_servers.keys())
    unique_servers = set(server_names)

    # Verify no duplicates (each server name appears exactly once)
    assert len(server_names) == len(unique_servers), (
        f"Found duplicate servers! This indicates SDK auto-discovery conflict. "
        f"Servers: {server_names}, Unique: {unique_servers}"
    )

    # Verify expected server count
    # In-process (Method A): docker, context7, memory (3 servers)
    # Subprocess (Method B): playwright (1 server)
    # Total: 4 servers
    assert len(server_names) == 4, (
        f"Unexpected server count: {len(server_names)}. Expected 4 servers. "
        f"Servers loaded: {server_names}"
    )

    # Verify all expected in-process servers present
    inprocess_expected = {"docker", "context7", "memory"}
    inprocess_actual = set(server_names) & inprocess_expected

    assert inprocess_actual == inprocess_expected, (
        f"Missing in-process servers. Expected: {inprocess_expected}, Got: {inprocess_actual}"
    )

    # Verify subprocess servers
    assert "playwright" in server_names, "Playwright server (subprocess) should always be loaded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_cwd_does_not_contain_mcp_json():
    """
    Test that .mcp.json is NOT in SDK working directory.

    Purpose: Verify the file location change prevents SDK auto-discovery.

    Expected behavior:
    - .mcp.json is NOT at /app/.mcp.json (SDK cwd)
    - .mcp.json IS at /app/src/harness/config/.mcp.json (subdirectory)
    - SDK cannot auto-discover it

    Cost: Free
    """
    from pathlib import Path

    sdk_cwd = Path("/app")
    mcp_json_in_cwd = sdk_cwd / ".mcp.json"
    mcp_json_in_harness = sdk_cwd / "src" / "harness" / "config" / ".mcp.json"

    # Verify .mcp.json NOT in SDK cwd (would cause auto-discovery)
    assert not mcp_json_in_cwd.exists(), (
        f".mcp.json should NOT exist at {mcp_json_in_cwd} (SDK would auto-discover it)"
    )

    # Verify .mcp.json IS in src/harness/config/ (safe from auto-discovery)
    assert mcp_json_in_harness.exists(), (
        f".mcp.json should exist at {mcp_json_in_harness} (MCPConfigLoader reads it)"
    )
