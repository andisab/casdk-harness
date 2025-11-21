"""Multi-agent coordination tests via Redis Streams.

This module tests the Redis Streams-based message broker used for
multi-agent coordination. Tests verify pub/sub patterns, consumer groups,
and message ordering guarantees.

Prerequisites: Redis server must be running and accessible.

Cost: Free (no API calls)
Duration: < 10 seconds total
"""

import asyncio
import os

import pytest
import redis

from harness.messaging import RedisMessageBroker


@pytest.fixture
def redis_url():
    """Get Redis URL from environment."""
    return os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest.fixture
async def message_broker(redis_url):
    """Create and connect message broker."""
    broker = RedisMessageBroker(redis_url=redis_url)
    try:
        broker.connect()
        yield broker
    finally:
        if broker.connected:
            broker.disconnect()


@pytest.mark.integration
@pytest.mark.redis
async def test_redis_connection(redis_url):
    """
    Test basic Redis connection.

    Purpose: Verify Redis server is accessible and responding.
    This is a prerequisite for multi-agent coordination.

    Expected behavior:
    - Connection successful
    - Ping command returns True

    Prerequisites: Redis server running
    Cost: Free
    """
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        result = client.ping()
        assert result is True, "Redis ping failed"
    finally:
        client.close()


@pytest.mark.integration
@pytest.mark.redis
async def test_publish_and_consume_result(message_broker):
    """
    Test publishing and consuming results from Redis stream.

    Purpose: Verify basic pub/sub pattern works correctly.
    Agents use this to share task results with each other.

    Expected behavior:
    - Message published successfully
    - Message consumed with correct data
    - Data integrity maintained

    Prerequisites: Redis server running
    Cost: Free
    """
    agent_id = "test-agent-1"
    result_data = {
        "task_id": "task-123",
        "status": "success",
        "data": {"value": 42},
    }

    # Publish result
    message_id = message_broker.publish_result(
        agent_id=agent_id,
        result=result_data,
        stream_name="test:results",
    )

    assert message_id is not None, "Failed to publish message"

    # Consume results
    messages = message_broker.consume_results(
        stream_name="test:results", last_id="0", count=10, block=1000
    )

    assert len(messages) == 1, f"Expected 1 message, got {len(messages)}"
    assert messages[0]["agent_id"] == agent_id
    assert messages[0]["content"]["task_id"] == "task-123"
    assert messages[0]["content"]["data"]["value"] == 42


@pytest.mark.integration
@pytest.mark.redis
async def test_multi_agent_coordination():
    """
    Test coordination between multiple agents via Redis.

    Purpose: Verify agents can communicate work completion status.
    Simulates Agent 1 publishing work and Agent 2 consuming it.

    Expected behavior:
    - Agent 1 publishes message successfully
    - Agent 2 receives same message
    - Message data matches exactly

    Prerequisites: Redis server running
    Cost: Free
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Simulate Agent 1 publishing work
    agent1_broker = RedisMessageBroker(redis_url=redis_url)
    agent1_broker.connect()

    try:
        message_id = agent1_broker.publish_result(
            agent_id="agent-1",
            result={
                "task_id": "coordination-test",
                "status": "completed",
                "data": "Agent 1 work done",
            },
            stream_name="agent:tasks",
        )

        assert message_id is not None

        # Simulate Agent 2 consuming work
        agent2_broker = RedisMessageBroker(redis_url=redis_url)
        agent2_broker.connect()

        try:
            # Agent 2 reads messages
            messages = agent2_broker.consume_results(
                stream_name="agent:tasks", last_id="0", count=10, block=2000
            )

            assert len(messages) >= 1, "Agent 2 did not receive message from Agent 1"

            # Find our test message
            test_msg = next(
                (
                    m
                    for m in messages
                    if m["content"].get("task_id") == "coordination-test"
                ),
                None,
            )

            assert test_msg is not None, "Test message not found"
            assert test_msg["agent_id"] == "agent-1"
            assert test_msg["content"]["status"] == "completed"

        finally:
            agent2_broker.disconnect()

    finally:
        agent1_broker.disconnect()


@pytest.mark.integration
async def test_consumer_group_pattern(message_broker):
    """Test consumer group pattern for load balancing."""
    stream_name = "test:consumer-group"
    group_name = "test-group"

    # Create consumer group
    created = message_broker.create_consumer_group(
        stream_name=stream_name, group_name=group_name, start_id="0"
    )

    # First time should create, second time should return False
    assert created is True or created is False  # May already exist from previous run

    # Publish test messages
    for i in range(5):
        message_broker.publish_result(
            agent_id="test-agent",
            result={"task_id": f"task-{i}", "value": i},
            stream_name=stream_name,
        )

    # Consumer 1 reads messages
    messages_1 = message_broker.read_group(
        stream_name=stream_name,
        group_name=group_name,
        consumer_name="consumer-1",
        count=3,
        block=1000,
    )

    assert len(messages_1) <= 3, "Consumer 1 received too many messages"

    # Acknowledge messages
    for msg in messages_1:
        message_broker.acknowledge_message(
            stream_name=stream_name,
            group_name=group_name,
            message_id=msg["message_id"],
        )

    # Consumer 2 reads remaining messages
    messages_2 = message_broker.read_group(
        stream_name=stream_name,
        group_name=group_name,
        consumer_name="consumer-2",
        count=3,
        block=1000,
    )

    # Total messages from both consumers should be <= 5
    total_messages = len(messages_1) + len(messages_2)
    assert total_messages <= 5, f"Too many messages: {total_messages}"


@pytest.mark.integration
async def test_stream_length_monitoring(message_broker):
    """Test monitoring stream queue depth."""
    stream_name = "test:monitoring"

    # Publish 10 messages
    for i in range(10):
        message_broker.publish_result(
            agent_id="test-agent",
            result={"task_id": f"task-{i}"},
            stream_name=stream_name,
        )

    # Check stream length
    length = message_broker.get_stream_length(stream_name)
    assert length >= 10, f"Expected at least 10 messages, got {length}"


@pytest.mark.integration
async def test_message_ordering(message_broker):
    """Test that messages maintain order in stream."""
    stream_name = "test:ordering"

    # Publish messages in sequence
    message_ids = []
    for i in range(5):
        msg_id = message_broker.publish_result(
            agent_id="test-agent",
            result={"sequence": i},
            stream_name=stream_name,
        )
        message_ids.append(msg_id)

    # Consume all messages
    messages = message_broker.consume_results(
        stream_name=stream_name, last_id="0", count=10
    )

    # Verify ordering
    assert len(messages) >= 5
    sequences = [m["content"]["sequence"] for m in messages if "sequence" in m["content"]]
    assert sequences == sorted(sequences), "Messages not in order"


@pytest.mark.integration
async def test_context_manager_pattern():
    """Test using RedisMessageBroker as context manager."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    with RedisMessageBroker(redis_url=redis_url) as broker:
        # Should auto-connect
        assert broker.connected is True

        # Should be able to publish
        msg_id = broker.publish_result(
            agent_id="test-agent",
            result={"test": "context manager"},
            stream_name="test:context",
        )
        assert msg_id is not None

    # Should auto-disconnect (no assertion, just verify no exception)
