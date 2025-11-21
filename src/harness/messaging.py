"""Redis-based messaging layer for cross-container agent communication.

This module provides a Redis Streams-based message broker that enables
reliable communication between agents running in different Docker containers.
"""

import json
import os
import time
from typing import Any

import redis
import structlog

logger = structlog.get_logger(__name__)


class RedisMessageBroker:
    """Redis Streams-based message broker for agent coordination."""

    def __init__(self, redis_url: str | None = None) -> None:
        """
        Initialize Redis message broker.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: redis.Redis | None = None
        self.connected = False

        logger.info("Redis message broker initialized", redis_url=self.redis_url)

    def connect(self) -> None:
        """Connect to Redis server."""
        try:
            self.client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,  # Automatically decode responses to str
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self.client.ping()
            self.connected = True
            logger.info("Connected to Redis server")
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error connecting to Redis", error=str(e), exc_info=True
            )
            raise

    def disconnect(self) -> None:
        """Disconnect from Redis server."""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("Disconnected from Redis server")

    def publish_result(
        self,
        agent_id: str,
        result: dict[str, Any],
        stream_name: str = "agent:results",
    ) -> str:
        """
        Publish agent result to Redis stream.

        Args:
            agent_id: ID of the agent publishing the result
            result: Result data to publish
            stream_name: Redis stream name (default: "agent:results")

        Returns:
            Message ID assigned by Redis

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        message_data = {
            "agent_id": agent_id,
            "content": json.dumps(result),
            "timestamp": time.time(),
        }

        try:
            message_id = self.client.xadd(stream_name, message_data)
            logger.info(
                "Published message to stream",
                agent_id=agent_id,
                stream=stream_name,
                message_id=message_id,
            )
            return message_id
        except Exception as e:
            logger.error(
                "Failed to publish message",
                agent_id=agent_id,
                stream=stream_name,
                error=str(e),
                exc_info=True,
            )
            raise

    def consume_results(
        self,
        stream_name: str = "agent:results",
        last_id: str = "0",
        count: int = 10,
        block: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Consume results from Redis stream.

        Args:
            stream_name: Redis stream name to read from
            last_id: ID of last consumed message (use "0" to read from beginning)
            count: Maximum number of messages to read
            block: Block for this many milliseconds if no messages (0 = forever)

        Returns:
            List of messages with parsed content

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        try:
            # XREAD returns: [(stream_name, [(message_id, {field: value})])]
            messages = self.client.xread(
                {stream_name: last_id}, count=count, block=block
            )

            results = []
            if messages:
                for stream, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        # Parse JSON content
                        content = json.loads(msg_data.get("content", "{}"))
                        results.append(
                            {
                                "message_id": msg_id,
                                "agent_id": msg_data.get("agent_id"),
                                "timestamp": float(msg_data.get("timestamp", 0)),
                                "content": content,
                            }
                        )

            logger.debug(
                "Consumed messages from stream",
                stream=stream_name,
                count=len(results),
            )
            return results

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse message content",
                stream=stream_name,
                error=str(e),
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to consume messages",
                stream=stream_name,
                error=str(e),
                exc_info=True,
            )
            raise

    def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        start_id: str = "0",
    ) -> bool:
        """
        Create a consumer group for processing messages.

        Args:
            stream_name: Redis stream name
            group_name: Consumer group name
            start_id: ID to start reading from (default: "0" = beginning)

        Returns:
            True if created, False if already exists

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        try:
            self.client.xgroup_create(stream_name, group_name, id=start_id, mkstream=True)
            logger.info(
                "Created consumer group",
                stream=stream_name,
                group=group_name,
            )
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(
                    "Consumer group already exists",
                    stream=stream_name,
                    group=group_name,
                )
                return False
            raise

    def read_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Read messages as part of a consumer group.

        Args:
            stream_name: Redis stream name
            group_name: Consumer group name
            consumer_name: Name of this consumer
            count: Maximum messages to read
            block: Block for this many milliseconds if no messages

        Returns:
            List of messages with parsed content

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        try:
            # XREADGROUP returns: [(stream_name, [(message_id, {field: value})])]
            messages = self.client.xreadgroup(
                group_name,
                consumer_name,
                {stream_name: ">"},  # ">" = undelivered messages
                count=count,
                block=block,
            )

            results = []
            if messages:
                for stream, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        content = json.loads(msg_data.get("content", "{}"))
                        results.append(
                            {
                                "message_id": msg_id,
                                "agent_id": msg_data.get("agent_id"),
                                "timestamp": float(msg_data.get("timestamp", 0)),
                                "content": content,
                            }
                        )

            logger.debug(
                "Read messages from consumer group",
                stream=stream_name,
                group=group_name,
                consumer=consumer_name,
                count=len(results),
            )
            return results

        except Exception as e:
            logger.error(
                "Failed to read from consumer group",
                stream=stream_name,
                group=group_name,
                error=str(e),
                exc_info=True,
            )
            raise

    def acknowledge_message(
        self,
        stream_name: str,
        group_name: str,
        message_id: str,
    ) -> None:
        """
        Acknowledge message processing completion.

        Args:
            stream_name: Redis stream name
            group_name: Consumer group name
            message_id: Message ID to acknowledge

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        try:
            self.client.xack(stream_name, group_name, message_id)
            logger.debug(
                "Acknowledged message",
                stream=stream_name,
                group=group_name,
                message_id=message_id,
            )
        except Exception as e:
            logger.error(
                "Failed to acknowledge message",
                stream=stream_name,
                group=group_name,
                message_id=message_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def get_stream_length(self, stream_name: str) -> int:
        """
        Get the number of messages in a stream.

        Args:
            stream_name: Redis stream name

        Returns:
            Number of messages in the stream

        Raises:
            redis.ConnectionError: If not connected to Redis
        """
        if not self.connected or not self.client:
            raise redis.ConnectionError("Not connected to Redis server")

        try:
            length = self.client.xlen(stream_name)
            return length
        except Exception as e:
            logger.error(
                "Failed to get stream length",
                stream=stream_name,
                error=str(e),
                exc_info=True,
            )
            raise

    def __enter__(self) -> "RedisMessageBroker":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.disconnect()
