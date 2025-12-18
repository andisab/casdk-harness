"""Redis-based messaging layer for cross-container agent communication.

This module provides a Redis Streams-based message broker that enables
reliable communication between agents running in different Docker containers.

Features:
- Circuit breaker pattern for resilience
- Exponential backoff retry with tenacity
- Configurable timeouts from HarnessConfig
"""

import json
import time
from enum import Enum
from typing import Any

import redis
import structlog
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from harness.config import HarnessConfig, get_config

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery, allowing limited requests


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    pass


class CircuitBreaker:
    """Circuit breaker for protecting against cascade failures.

    The circuit breaker pattern prevents repeated calls to a failing service,
    allowing it time to recover while providing fast failure to callers.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: After threshold failures, block all requests
    - HALF_OPEN: After recovery timeout, test with single request
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        name: str = "redis",
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            name: Name for logging purposes
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: float | None = None

        # Debug-level logging for circuit breaker initialization
        # (included in Redis connection summary at info level)

    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests).

        Also handles transition from OPEN to HALF_OPEN after recovery timeout.
        """
        if self.state == CircuitState.CLOSED:
            return False

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    logger.info(
                        "Circuit breaker transitioning to half-open",
                        name=self.name,
                        elapsed_seconds=elapsed,
                    )
                    self.state = CircuitState.HALF_OPEN
                    return False
            return True

        # HALF_OPEN allows request through for testing
        return False

    def record_success(self) -> None:
        """Record successful operation, reset failures if in HALF_OPEN."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(
                "Circuit breaker closing after successful recovery",
                name=self.name,
            )
            self.state = CircuitState.CLOSED
            self.failures = 0
            self.last_failure_time = None
        elif self.state == CircuitState.CLOSED:
            self.failures = 0

    def record_failure(self) -> None:
        """Record failed operation, potentially open circuit."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test, reopen circuit
            logger.warning(
                "Circuit breaker reopening after failed recovery attempt",
                name=self.name,
            )
            self.state = CircuitState.OPEN
        elif self.failures >= self.failure_threshold:
            logger.warning(
                "Circuit breaker opening due to failure threshold",
                name=self.name,
                failures=self.failures,
                threshold=self.failure_threshold,
            )
            self.state = CircuitState.OPEN

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
        }


class RedisMessageBroker:
    """Redis Streams-based message broker for agent coordination.

    Features:
    - Circuit breaker for resilience against Redis failures
    - Retry with exponential backoff
    - Configurable timeouts from HarnessConfig
    """

    def __init__(
        self,
        redis_url: str | None = None,
        config: HarnessConfig | None = None,
    ) -> None:
        """
        Initialize Redis message broker.

        Args:
            redis_url: Redis connection URL (overrides config.redis_url)
            config: Harness configuration (defaults to global config)
        """
        self.config = config or get_config()
        self.redis_url = redis_url or self.config.redis_url
        self.client: redis.Redis | None = None
        self.connected = False

        # Initialize circuit breaker with config values
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.redis_circuit_breaker_threshold,
            recovery_timeout=self.config.redis_circuit_breaker_recovery,
            name="redis",
        )

        # Connection will be logged after successful connect()
        # to avoid duplicate logging

    def connect(self) -> None:
        """Connect to Redis server with circuit breaker protection."""
        # Check circuit breaker first
        if self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open, Redis unavailable. "
                f"Will retry in {self.circuit_breaker.recovery_timeout}s"
            )

        try:
            self._connect_with_retry()
            self.circuit_breaker.record_success()
        except RetryError as e:
            self.circuit_breaker.record_failure()
            logger.error(
                "Redis connection failed after retries",
                error=str(e),
                circuit_state=self.circuit_breaker.get_state(),
            )
            raise
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                "Unexpected error connecting to Redis",
                error=str(e),
                circuit_state=self.circuit_breaker.get_state(),
                exc_info=True,
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def _connect_with_retry(self) -> None:
        """Internal connection method with retry logic."""
        try:
            self.client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=self.config.redis_timeout,
                socket_timeout=self.config.redis_timeout,
            )
            # Test connection
            self.client.ping()
            self.connected = True
            logger.debug("Redis ping successful")
        except redis.ConnectionError as e:
            logger.warning("Redis connection attempt failed", error=str(e))
            raise
        except Exception as e:
            logger.warning("Unexpected error in Redis connection", error=str(e))
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
                for _stream, msg_list in messages:
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
                for _stream, msg_list in messages:
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

    def get_circuit_breaker_state(self) -> dict[str, Any]:
        """Get circuit breaker state for monitoring.

        Returns:
            Dict with circuit breaker state information
        """
        return self.circuit_breaker.get_state()

    def is_available(self) -> bool:
        """Check if Redis is available (connected and circuit not open).

        Returns:
            True if Redis is available for operations
        """
        return self.connected and not self.circuit_breaker.is_open()

    def __enter__(self) -> "RedisMessageBroker":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.disconnect()
