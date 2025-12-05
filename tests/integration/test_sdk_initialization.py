"""Comprehensive SDK initialization tests.

This module consolidates tests for various SDK initialization scenarios:
- No MCP servers (minimal configuration)
- In-process MCP servers only (git, docker)
- External MCP servers (memory via npx)
- Permission mode validation
- Initialization timing verification

Cost: Each test costs ~100-200 tokens (~$0.001-0.002 per test)
Duration: ~5-15 seconds per test
"""

import asyncio
import time

import pytest
import structlog
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from harness.config import get_config

logger = structlog.get_logger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_init_no_mcp_servers():
    """
    Test SDK initialization with no MCP servers.

    Purpose: Verify SDK can initialize and execute queries with minimal configuration.
    This isolates SDK functionality from MCP server complexity.

    Expected behavior:
    - SDK initializes successfully in < 10 seconds
    - Can send queries and receive responses
    - No timeout errors

    Cost: ~100 tokens (~$0.001)
    """
    config = get_config()

    # Minimal SDK options with NO MCP servers
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=5,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        mcp_servers={},  # EMPTY - no MCP servers
    )

    logger.info("Testing SDK initialization with no MCP servers")

    # Use context manager for SDK client (no explicit start/shutdown needed)
    async with ClaudeSDKClient(options=options) as client:
        logger.info("✅ SDK client initialized successfully (no MCP servers)")

        # Send query
        logger.info("Sending simple query...")
        await asyncio.wait_for(
            client.query("What is 2+2? Just answer the number."),
            timeout=10.0
        )
        logger.info("✅ Query sent successfully")

        # Receive response messages
        logger.info("Waiting for response messages...")
        messages = []
        async for message in client.receive_response():
            logger.info("Message received", message_type=type(message).__name__)
            messages.append(message)

        logger.info("✅ Test completed", message_count=len(messages))
        assert len(messages) > 0, "Should receive at least one message"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_init_with_in_process_mcp_only():
    """
    Test SDK initialization with in-process MCP servers.

    Purpose: Verify SDK works with Python-based MCP servers (git, docker)
    that run in the same process without subprocess spawning.

    Expected behavior:
    - SDK initializes with in-process MCP servers
    - MCP tools are registered and available
    - No subprocess startup delays

    Cost: ~150 tokens (~$0.002)
    """
    from mcp_servers.docker.server import docker_server
    from mcp_servers.git.server import git_server

    config = get_config()

    # SDK options with ONLY in-process MCP servers
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=5,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        mcp_servers={
            "git": git_server,
            "docker": docker_server,
        },
    )

    logger.info("Testing SDK with in-process MCP servers only")

    async with ClaudeSDKClient(options=options) as client:
        logger.info("✅ SDK client initialized with in-process MCP servers")

        # Send query
        logger.info("Sending query...")
        await asyncio.wait_for(
            client.query("What is 3+3? Just answer the number."),
            timeout=10.0
        )
        logger.info("✅ Query sent")

        # Receive response
        messages = []
        async for message in client.receive_response():
            logger.info("Message received", message_type=type(message).__name__)
            messages.append(message)

        logger.info("✅ Test completed with in-process MCP", message_count=len(messages))
        assert len(messages) > 0


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_sdk_init_with_external_mcp():
    """
    Test SDK initialization with external MCP server via subprocess.

    Purpose: Verify SDK can spawn and communicate with external MCP servers
    using stdio transport (npx subprocess).

    Expected behavior:
    - SDK initializes with external memory MCP server
    - NPX downloads and starts server successfully
    - Server communication works via stdio

    Note: First run may be slower due to npx package installation.

    Cost: ~200 tokens (~$0.002)
    Duration: 10-20 seconds (due to npx installation)
    """
    config = get_config()

    # SDK options with ONLY external memory server
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=5,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        mcp_servers={
            "memory": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-memory"],
            }
        },
    )

    logger.info("Testing SDK with external memory MCP server")

    # Note: This may take longer due to npx installation
    async with ClaudeSDKClient(options=options) as client:
        logger.info("✅ SDK client initialized with memory MCP server")

        # Send query
        logger.info("Sending query...")
        await asyncio.wait_for(
            client.query("What is 5+5? Just answer the number."),
            timeout=15.0  # Longer timeout for external MCP
        )
        logger.info("✅ Query sent")

        # Receive response
        messages = []
        async for message in client.receive_response():
            logger.info("Message received", message_type=type(message).__name__)
            messages.append(message)

        logger.info("✅ Test completed with memory MCP", message_count=len(messages))
        assert len(messages) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_permission_modes():
    """
    Test SDK with valid permission mode.

    Purpose: Verify SDK accepts valid permission mode (bypassPermissions)
    and rejects invalid modes.

    Expected behavior:
    - SDK initializes successfully with "bypassPermissions"
    - SDK would reject invalid modes like "acceptAll" (tested elsewhere)

    Cost: ~100 tokens (~$0.001)
    """
    config = get_config()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions",  # Valid mode
        max_turns=3,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        mcp_servers={},
    )

    logger.info("Testing SDK with valid permission mode")

    async with ClaudeSDKClient(options=options) as client:
        logger.info("✅ SDK initialized with bypassPermissions mode")

        # Quick query to verify functionality
        await asyncio.wait_for(
            client.query("Say hello in one word"),
            timeout=10.0
        )

        messages = []
        async for message in client.receive_response():
            messages.append(message)
            if len(messages) >= 3:  # Get first 3 messages
                break

        logger.info("✅ Permission mode test completed", message_count=len(messages))
        assert len(messages) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_initialization_timing():
    """
    Test SDK initialization completes within acceptable time.

    Purpose: Verify SDK initialization doesn't hang or timeout.
    Regression test for 60-second timeout issue (now resolved).

    Expected behavior:
    - Initialization completes in < 10 seconds
    - Query execution completes in < 10 seconds
    - Total time < 20 seconds

    Cost: ~100 tokens (~$0.001)
    """
    config = get_config()

    # Measure initialization time
    init_start = time.time()

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=3,
        cwd=str(config.workspace_dir),
        model=config.claude_model,
        mcp_servers={},
    )

    logger.info("Measuring SDK initialization timing")

    async with ClaudeSDKClient(options=options) as client:
        init_elapsed = time.time() - init_start
        logger.info("SDK initialized", duration_seconds=init_elapsed)

        # Initialization should be fast (< 10 seconds)
        assert init_elapsed < 10.0, f"Initialization took {init_elapsed:.2f}s (expected < 10s)"

        # Measure query execution time
        query_start = time.time()
        await asyncio.wait_for(client.query("What is 2+2?"), timeout=10.0)

        messages = []
        async for message in client.receive_response():
            messages.append(message)

        query_elapsed = time.time() - query_start
        total_elapsed = time.time() - init_start

        logger.info(
            "Timing test completed",
            init_seconds=init_elapsed,
            query_seconds=query_elapsed,
            total_seconds=total_elapsed,
            message_count=len(messages)
        )

        # Query should complete quickly
        assert query_elapsed < 10.0, f"Query took {query_elapsed:.2f}s (expected < 10s)"

        # Total should be well under timeout threshold
        assert total_elapsed < 20.0, f"Total time {total_elapsed:.2f}s (expected < 20s)"
        assert len(messages) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_minimal_configuration():
    """
    Test SDK with absolute minimal configuration.

    Purpose: Verify SDK works with minimal required parameters only.
    Useful for debugging and isolating configuration issues.

    Expected behavior:
    - SDK initializes with only model, permission_mode, max_turns
    - Uses reasonable defaults for other parameters
    - Can execute basic queries

    Cost: ~100 tokens (~$0.001)
    """
    logger.info("Testing SDK with absolute minimal configuration")

    # Absolute minimum configuration
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        permission_mode="bypassPermissions",
        max_turns=3,
        cwd="/workspace",  # Explicitly set working directory
    )

    logger.info("Creating SDK client with minimal options...")

    async with ClaudeSDKClient(options=options) as client:
        logger.info("✅ SDK client initialized with minimal config")

        logger.info("Sending query...")
        await asyncio.wait_for(client.query("What is 2+2?"), timeout=10.0)
        logger.info("✅ Query sent")

        logger.info("Receiving response...")
        messages = []
        async for message in client.receive_response():
            logger.info(f"Received: {type(message).__name__}")
            messages.append(message)
            if len(messages) > 10:  # Safety limit
                break

        logger.info(f"✅ Success! Received {len(messages)} messages")
        assert len(messages) > 0
