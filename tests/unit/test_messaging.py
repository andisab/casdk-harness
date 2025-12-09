"""Unit tests for Redis messaging layer with circuit breaker."""

import time
from unittest.mock import MagicMock, patch

import pytest

from harness.messaging import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    RedisMessageBroker,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_states_defined(self) -> None:
        """Test all expected circuit states are defined."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker()

        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0
        assert cb.is_open() is False

    def test_custom_thresholds(self) -> None:
        """Test circuit breaker accepts custom thresholds."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name="test")

        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 60
        assert cb.name == "test"

    def test_record_success_resets_failures(self) -> None:
        """Test recording success resets failure count."""
        cb = CircuitBreaker()
        cb.failures = 3

        cb.record_success()

        assert cb.failures == 0

    def test_record_failure_increments_count(self) -> None:
        """Test recording failure increments failure count."""
        cb = CircuitBreaker()

        cb.record_failure()
        assert cb.failures == 1

        cb.record_failure()
        assert cb.failures == 2

    def test_circuit_opens_after_threshold(self) -> None:
        """Test circuit opens after failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures up to threshold
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()  # Third failure triggers open
        assert cb.state == CircuitState.OPEN
        assert cb.is_open() is True

    def test_is_open_returns_true_when_open(self) -> None:
        """Test is_open returns True when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        assert cb.is_open() is True

    def test_half_open_after_recovery_timeout(self) -> None:
        """Test circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

        # Open the circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing beyond recovery timeout
        cb.last_failure_time = time.time() - 2  # 2 seconds ago

        # Check is_open - should transition to half-open
        assert cb.is_open() is False
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self) -> None:
        """Test circuit closes from half-open on success."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.state = CircuitState.HALF_OPEN

        cb.record_success()

        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0
        assert cb.last_failure_time is None

    def test_half_open_reopens_on_failure(self) -> None:
        """Test circuit reopens from half-open on failure."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.state = CircuitState.HALF_OPEN

        cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_get_state_returns_monitoring_info(self) -> None:
        """Test get_state returns comprehensive monitoring information."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30, name="redis")
        cb.failures = 2
        cb.last_failure_time = 12345.0

        state = cb.get_state()

        assert state["name"] == "redis"
        assert state["state"] == "closed"
        assert state["failures"] == 2
        assert state["failure_threshold"] == 5
        assert state["recovery_timeout"] == 30
        assert state["last_failure_time"] == 12345.0


class TestRedisMessageBroker:
    """Tests for RedisMessageBroker class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = MagicMock()
        config.redis_url = "redis://localhost:6379/0"
        config.redis_timeout = 5
        config.redis_circuit_breaker_threshold = 5
        config.redis_circuit_breaker_recovery = 30
        return config

    def test_broker_initialization(self, mock_config) -> None:
        """Test broker initializes with config values."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        assert broker.redis_url == "redis://localhost:6379/0"
        assert broker.connected is False
        assert broker.client is None
        assert broker.circuit_breaker is not None

    def test_broker_uses_custom_url(self, mock_config) -> None:
        """Test broker can use custom Redis URL."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker(redis_url="redis://custom:6380/1")

        assert broker.redis_url == "redis://custom:6380/1"

    def test_connect_raises_when_circuit_open(self, mock_config) -> None:
        """Test connect raises CircuitBreakerOpenError when circuit is open."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()
            broker.circuit_breaker.state = CircuitState.OPEN
            broker.circuit_breaker.last_failure_time = time.time()  # Recent failure

        with pytest.raises(CircuitBreakerOpenError):
            broker.connect()

    def test_is_available_checks_connection_and_circuit(self, mock_config) -> None:
        """Test is_available checks both connection and circuit state."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        # Not connected
        assert broker.is_available() is False

        # Connected but circuit open
        broker.connected = True
        broker.circuit_breaker.state = CircuitState.OPEN
        broker.circuit_breaker.last_failure_time = time.time()
        assert broker.is_available() is False

        # Connected and circuit closed
        broker.circuit_breaker.state = CircuitState.CLOSED
        assert broker.is_available() is True

    def test_get_circuit_breaker_state(self, mock_config) -> None:
        """Test get_circuit_breaker_state returns circuit breaker info."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        state = broker.get_circuit_breaker_state()

        assert "name" in state
        assert "state" in state
        assert "failures" in state

    def test_disconnect_resets_connection(self, mock_config) -> None:
        """Test disconnect properly resets connection state."""
        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        # Mock a connected state
        mock_client = MagicMock()
        broker.client = mock_client
        broker.connected = True

        broker.disconnect()

        assert broker.connected is False
        mock_client.close.assert_called_once()

    def test_publish_result_requires_connection(self, mock_config) -> None:
        """Test publish_result raises when not connected."""
        import redis

        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        with pytest.raises(redis.ConnectionError):
            broker.publish_result("agent-1", {"result": "data"})

    def test_consume_results_requires_connection(self, mock_config) -> None:
        """Test consume_results raises when not connected."""
        import redis

        with patch("harness.messaging.get_config", return_value=mock_config):
            broker = RedisMessageBroker()

        with pytest.raises(redis.ConnectionError):
            broker.consume_results()


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_exception_is_raised_with_message(self) -> None:
        """Test exception can be raised with custom message."""
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            raise CircuitBreakerOpenError("Circuit is open")

        assert "Circuit is open" in str(exc_info.value)
