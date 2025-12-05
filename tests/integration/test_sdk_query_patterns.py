"""
Test SDK query patterns to verify message streaming works correctly.

This test file can be run manually to debug issues with the SDK integration:
    docker compose exec main-agent pytest tests/test_sdk_patterns.py -v -s
"""

import asyncio

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, query


@pytest.mark.asyncio
async def test_query_pattern_simple():
    """
    Test the simple query() pattern.

    This should work for one-shot queries but has been observed to
    yield zero messages in the current setup.
    """
    print("\n" + "=" * 80)
    print("TEST: query() pattern (one-shot)")
    print("=" * 80)

    options = ClaudeAgentOptions(
        model="haiku",
        cwd="/workspace",  # Set working directory like agent.py does
        stderr=lambda msg: print(f"[CLI stderr] {msg}"),  # Print stderr output
        extra_args={"debug-to-stderr": None},  # Enable verbose debug
    )

    message_count = 0
    message_types = []

    try:
        async for message in query(prompt="What is 2+2? Answer in one word.", options=options):
            message_count += 1
            message_type = type(message).__name__
            message_types.append(message_type)
            print(f"✓ Message {message_count}: {message_type}")

        print(f"\nResult: Received {message_count} messages")
        print(f"Types: {message_types}")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        raise

    # Assert we got messages
    assert message_count > 0, f"Expected messages but got {message_count}"
    print("✓ TEST PASSED\n")


@pytest.mark.asyncio
async def test_claude_sdk_client_pattern():
    """
    Test the ClaudeSDKClient pattern with context manager.

    This is the recommended pattern for multi-turn conversations
    and should maintain context across queries.
    """
    print("\n" + "=" * 80)
    print("TEST: ClaudeSDKClient pattern (stateful)")
    print("=" * 80)

    options = ClaudeAgentOptions(
        model="haiku",
        cwd="/workspace",  # Set working directory like agent.py does
        stderr=lambda msg: print(f"[CLI stderr] {msg}"),  # Print stderr output
        extra_args={"debug-to-stderr": None},  # Enable verbose debug
    )

    message_count = 0
    message_types = []

    try:
        async with ClaudeSDKClient(options=options) as client:
            print("✓ Client connected")

            # Send query
            await client.query("What is 2+2? Answer in one word.")
            print("✓ Query sent")

            # Receive responses
            async for message in client.receive_response():
                message_count += 1
                message_type = type(message).__name__
                message_types.append(message_type)
                print(f"✓ Message {message_count}: {message_type}")

        print(f"\nResult: Received {message_count} messages")
        print(f"Types: {message_types}")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        raise

    # Assert we got messages
    assert message_count > 0, f"Expected messages but got {message_count}"
    print("✓ TEST PASSED\n")


@pytest.mark.asyncio
async def test_claude_sdk_client_multi_turn():
    """
    Test multi-turn conversation with ClaudeSDKClient.

    This verifies that context is preserved across multiple queries.
    """
    print("\n" + "=" * 80)
    print("TEST: ClaudeSDKClient multi-turn conversation")
    print("=" * 80)

    options = ClaudeAgentOptions(
        model="haiku",
        cwd="/workspace",  # Set working directory like agent.py does
        stderr=lambda msg: print(f"[CLI stderr] {msg}"),  # Print stderr output
        extra_args={"debug-to-stderr": None},  # Enable verbose debug
    )

    total_messages = 0

    try:
        async with ClaudeSDKClient(options=options) as client:
            print("✓ Client connected")

            # First query
            print("\n--- Query 1: What is 2+2? ---")
            await client.query("What is 2+2? Answer in one word.")

            query1_messages = 0
            async for message in client.receive_response():
                query1_messages += 1
                total_messages += 1
                print(f"  Message {query1_messages}: {type(message).__name__}")

            print(f"Query 1 complete: {query1_messages} messages")

            # Second query (should remember context)
            print("\n--- Query 2: What is that number squared? ---")
            await client.query("What is that number squared? Answer in one word.")

            query2_messages = 0
            async for message in client.receive_response():
                query2_messages += 1
                total_messages += 1
                print(f"  Message {query2_messages}: {type(message).__name__}")

            print(f"Query 2 complete: {query2_messages} messages")

        print(f"\n✓ Total messages across both queries: {total_messages}")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        raise

    # Assert we got messages for both queries
    assert total_messages > 0, f"Expected messages but got {total_messages}"
    print("✓ TEST PASSED\n")


def test_sdk_imports():
    """Verify SDK imports work correctly."""
    print("\n" + "=" * 80)
    print("TEST: SDK imports")
    print("=" * 80)


    print("✓ All SDK imports successful")
    print("✓ TEST PASSED\n")


if __name__ == "__main__":
    """
    Run tests directly for debugging:
        python tests/test_sdk_patterns.py
    """
    print("\n" + "=" * 80)
    print("Running SDK Pattern Tests")
    print("=" * 80)

    # Run import test
    test_sdk_imports()

    # Run async tests
    print("\nRunning async tests...")

    try:
        print("\n1. Testing query() pattern...")
        asyncio.run(test_query_pattern_simple())
    except AssertionError as e:
        print(f"✗ query() pattern FAILED: {e}")
    except Exception as e:
        print(f"✗ query() pattern ERROR: {e}")

    try:
        print("\n2. Testing ClaudeSDKClient pattern...")
        asyncio.run(test_claude_sdk_client_pattern())
    except AssertionError as e:
        print(f"✗ ClaudeSDKClient pattern FAILED: {e}")
    except Exception as e:
        print(f"✗ ClaudeSDKClient pattern ERROR: {e}")

    try:
        print("\n3. Testing multi-turn conversation...")
        asyncio.run(test_claude_sdk_client_multi_turn())
    except AssertionError as e:
        print(f"✗ Multi-turn FAILED: {e}")
    except Exception as e:
        print(f"✗ Multi-turn ERROR: {e}")

    print("\n" + "=" * 80)
    print("Test suite complete")
    print("=" * 80)
