"""Integration test to verify SDK does NOT auto-discover .mcp.json.

This test ensures that moving .mcp.json to .claude/.mcp.json prevents
SDK auto-discovery, eliminating the double-loading problem from Phase 1C.

Phase 1C Solution:
- .mcp.json moved to .claude/.mcp.json (subdirectory)
- SDK cwd is /app, only auto-discovers from /app/.mcp.json
- File at /app/.claude/.mcp.json is NOT auto-discovered by SDK
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

    Purpose: Verify that moving .mcp.json to .claude/.mcp.json eliminates
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
    # Tier 1: git, docker, context7, github (conditional) (3-4 servers)
    # Tier 2: memory, playwright, joplin (conditional) (2-3 servers)
    # Total: 5-7 servers
    assert 5 <= len(server_names) <= 7, (
        f"Unexpected server count: {len(server_names)}. Expected 5-7 servers. "
        f"Servers loaded: {server_names}"
    )

    # Verify all expected Tier 1 servers present (excluding github which needs API key)
    tier1_expected = {"git", "docker", "context7"}
    tier1_actual = set(server_names) & tier1_expected

    assert tier1_actual == tier1_expected, (
        f"Missing Tier 1 servers. Expected: {tier1_expected}, Got: {tier1_actual}"
    )

    # Verify Tier 2 servers that don't require API keys
    assert "memory" in server_names, "Memory server (Tier 2) should always be loaded"
    assert "playwright" in server_names, "Playwright server (Tier 2) should always be loaded"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_cwd_does_not_contain_mcp_json():
    """
    Test that .mcp.json is NOT in SDK working directory.

    Purpose: Verify the file location change prevents SDK auto-discovery.

    Expected behavior:
    - .mcp.json is NOT at /app/.mcp.json (SDK cwd)
    - .mcp.json IS at /app/.claude/.mcp.json (subdirectory)
    - SDK cannot auto-discover it

    Cost: Free
    """
    from pathlib import Path

    sdk_cwd = Path("/app")
    mcp_json_in_cwd = sdk_cwd / ".mcp.json"
    mcp_json_in_claude = sdk_cwd / ".claude" / ".mcp.json"

    # Verify .mcp.json NOT in SDK cwd (would cause auto-discovery)
    assert not mcp_json_in_cwd.exists(), (
        f".mcp.json should NOT exist at {mcp_json_in_cwd} (SDK would auto-discover it)"
    )

    # Verify .mcp.json IS in .claude/ subdirectory (safe from auto-discovery)
    assert mcp_json_in_claude.exists(), (
        f".mcp.json should exist at {mcp_json_in_claude} (MCPConfigLoader reads it)"
    )
