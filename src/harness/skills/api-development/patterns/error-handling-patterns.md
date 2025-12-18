---
title: Error Handling Patterns
description: Structured error responses, retry strategies, circuit breakers, and resilient error management
tags: [pattern, error-handling, resilience, retry, circuit-breaker]
type: pattern
version: "1.0.0"
category: reliability
---

# Error Handling Patterns

## Overview

This pattern guide covers error handling strategies including structured error responses, retry mechanisms, circuit breakers, graceful degradation, and error monitoring. Use these patterns to build resilient applications that handle failures gracefully and provide clear error feedback.

**When to use these patterns:**
- Building production APIs and services
- Implementing retry logic for external services
- Preventing cascading failures
- Providing clear error messages to users
- Implementing fault-tolerant distributed systems
- Managing transient failures

## Patterns

### 1. Structured Error Responses

**Use Case:** Consistent, informative error responses across application

**Implementation:**

```python
# Structured error response model
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class ErrorCode(str, Enum):
    """Error codes for classification."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

class ErrorDetail(BaseModel):
    """Detailed error information."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None

class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str  # Error code
    message: str  # User-friendly message
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime
    path: str
    request_id: str
    documentation_url: Optional[str] = None

# Custom exceptions
class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int,
        details: Optional[List[ErrorDetail]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)

class ValidationException(AppException):
    """Validation error exception."""

    def __init__(self, message: str, details: List[ErrorDetail] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            details=details
        )

class AuthenticationException(AppException):
    """Authentication error exception."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            status_code=401,
            details=None
        )

# Global exception handler
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid

app = FastAPI()

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle application exceptions."""
    logger.error(
        "application_error",
        error_code=exc.error_code,
        message=exc.message,
        path=request.url.path,
        method=request.method
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": [d.dict() for d in exc.details],
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "request_id": str(uuid.uuid4()),
            "documentation_url": f"https://docs.example.com/errors/{exc.error_code}"
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    details = [
        ErrorDetail(
            field=".".join(str(loc) for loc in error["loc"]),
            message=error["msg"],
            code=error["type"]
        )
        for error in exc.errors()
    ]

    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors()
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "details": [d.dict() for d in details],
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "request_id": str(uuid.uuid4())
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": ErrorCode.INTERNAL_ERROR,
            "message": "An internal error occurred",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "request_id": str(uuid.uuid4())
        }
    )
```

### 2. Retry Strategies

**Use Case:** Handle transient failures in external service calls

**Implementation:**

```python
# Exponential backoff with jitter
import asyncio
import random
from typing import TypeVar, Callable, Optional
from functools import wraps

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        if self.jitter:
            # Add random jitter (0-100% of delay)
            delay = delay * (0.5 + random.random() * 0.5)

        return delay

def retry_async(
    config: RetryConfig = RetryConfig(),
    retry_on: tuple = (Exception,),
    exclude: tuple = ()
):
    """Async retry decorator with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except exclude:
                    # Don't retry these exceptions
                    raise

                except retry_on as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=config.max_attempts,
                            delay=delay,
                            error=str(e)
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=config.max_attempts,
                            error=str(e)
                        )

            raise last_exception

        return wrapper
    return decorator

# Usage
import httpx

@retry_async(
    config=RetryConfig(max_attempts=3, initial_delay=1.0, max_delay=10.0),
    retry_on=(httpx.TimeoutException, httpx.ConnectError),
    exclude=(httpx.HTTPStatusError,)  # Don't retry 4xx/5xx errors
)
async def call_external_api(url: str) -> dict:
    """Call external API with retry logic."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### 3. Circuit Breaker Pattern

**Use Case:** Prevent cascading failures when external services are down

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Optional
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Service failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        expected_exceptions: tuple = (Exception,)
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.expected_exceptions = expected_exceptions

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open", function=func.__name__)
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for {func.__name__}"
                )

        try:
            result = await func(*args, **kwargs)

            # Success
            self._on_success()
            return result

        except self.expected_exceptions as e:
            # Expected failure
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._reset()

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.failure_count >= self.failure_threshold:
            self._open()

    def _open(self):
        """Open circuit breaker."""
        self.state = CircuitState.OPEN
        self.success_count = 0
        logger.error(
            "circuit_breaker_opened",
            failures=self.failure_count,
            timeout=self.timeout
        )

    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("circuit_breaker_closed")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt recovery."""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout

class CircuitBreakerOpenError(Exception):
    """Circuit breaker is open."""
    pass

# Usage
payment_circuit = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60
)

async def process_payment(order_id: int, amount: float):
    """Process payment with circuit breaker."""
    async def make_payment():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://payment-service/api/v1/charges",
                json={"order_id": order_id, "amount": amount}
            )
            response.raise_for_status()
            return response.json()

    return await payment_circuit.call(make_payment)
```

### 4. Dead Letter Queue Pattern

**Use Case:** Handle messages that cannot be processed after retries

```python
# Message processing with dead letter queue
import aio_pika
import json

async def process_message_with_dlq(message: aio_pika.IncomingMessage):
    """Process message with dead letter queue support."""
    max_retries = 3
    retry_count = message.headers.get("x-retry-count", 0)

    try:
        # Process message
        data = json.loads(message.body.decode())
        await handle_order(data)

        # Acknowledge successful processing
        await message.ack()

    except Exception as e:
        logger.error(
            "message_processing_failed",
            error=str(e),
            retry_count=retry_count,
            message_id=message.message_id
        )

        if retry_count < max_retries:
            # Retry: requeue with incremented counter
            await message.reject(requeue=True)

            # Update retry count (in production, use message properties)
            message.headers["x-retry-count"] = retry_count + 1

        else:
            # Max retries exceeded: send to dead letter queue
            await send_to_dlq(message, str(e))
            await message.ack()

async def send_to_dlq(message: aio_pika.IncomingMessage, error: str):
    """Send failed message to dead letter queue."""
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")

    async with connection:
        channel = await connection.channel()
        dlq_exchange = await channel.declare_exchange("dlq", aio_pika.ExchangeType.DIRECT)

        dlq_message = aio_pika.Message(
            body=message.body,
            headers={
                **message.headers,
                "x-original-exchange": message.exchange,
                "x-original-routing-key": message.routing_key,
                "x-failure-reason": error,
                "x-failure-timestamp": datetime.utcnow().isoformat()
            }
        )

        await dlq_exchange.publish(
            dlq_message,
            routing_key="failed_messages"
        )
```

### 5. Graceful Degradation

**Use Case:** Provide limited functionality when dependencies fail

```python
# Fallback mechanisms
async def get_user_recommendations(user_id: int) -> List[dict]:
    """Get user recommendations with fallback."""
    try:
        # Try ML recommendation service
        return await ml_service.get_recommendations(user_id)

    except CircuitBreakerOpenError:
        logger.warning("ml_service_unavailable_using_fallback", user_id=user_id)

        # Fallback: return popular items
        return await get_popular_items(limit=10)

    except Exception as e:
        logger.error("recommendation_error", error=str(e), user_id=user_id)

        # Fallback: return empty list
        return []

# Cache-aside with error handling
async def get_product(product_id: int) -> Optional[dict]:
    """Get product with cache fallback."""
    try:
        # Try cache first
        cached = await cache.get(f"product:{product_id}")
        if cached:
            return cached

    except redis.RedisError as e:
        logger.warning("cache_unavailable", error=str(e))
        # Continue to database

    try:
        # Get from database
        product = await db.query(Product).filter(Product.id == product_id).first()

        # Try to cache (don't fail if cache is down)
        try:
            await cache.set(f"product:{product_id}", product.dict(), ttl=3600)
        except redis.RedisError:
            pass

        return product

    except Exception as e:
        logger.error("product_fetch_failed", error=str(e), product_id=product_id)
        raise
```

## Best Practices

### Error Response Guidelines

**Do:**
- ✅ Use consistent error response format across application
- ✅ Include correlation/request IDs for tracking
- ✅ Provide user-friendly error messages
- ✅ Log detailed errors server-side
- ✅ Use appropriate HTTP status codes
- ✅ Document error codes and responses
- ✅ Include links to documentation

**Don't:**
- ❌ Expose internal implementation details
- ❌ Return stack traces to clients
- ❌ Use generic error messages ("Something went wrong")
- ❌ Log sensitive data (passwords, tokens, PII)

### HTTP Status Codes

```python
# Common HTTP status codes
STATUS_CODES = {
    # 2xx Success
    200: "OK",
    201: "Created",
    204: "No Content",

    # 4xx Client Errors
    400: "Bad Request",           # Validation error
    401: "Unauthorized",          # Authentication required
    403: "Forbidden",             # Insufficient permissions
    404: "Not Found",             # Resource doesn't exist
    409: "Conflict",              # Resource conflict (duplicate)
    422: "Unprocessable Entity",  # Semantic validation error
    429: "Too Many Requests",     # Rate limit exceeded

    # 5xx Server Errors
    500: "Internal Server Error", # Unexpected error
    502: "Bad Gateway",           # Upstream service error
    503: "Service Unavailable",   # Service down/overloaded
    504: "Gateway Timeout"        # Upstream timeout
}
```

### Retry Strategy Guidelines

- Retry only idempotent operations
- Use exponential backoff with jitter
- Set maximum retry attempts (3-5)
- Don't retry 4xx errors (client errors)
- Implement circuit breakers for external services
- Log all retry attempts

### Monitoring and Alerting

```python
# Error metrics
from prometheus_client import Counter, Histogram

error_counter = Counter(
    'application_errors_total',
    'Total application errors',
    ['error_code', 'endpoint']
)

error_duration = Histogram(
    'error_handling_duration_seconds',
    'Time spent handling errors',
    ['error_type']
)

# Middleware for error tracking
@app.middleware("http")
async def error_tracking_middleware(request: Request, call_next):
    try:
        response = await call_next(request)

        if response.status_code >= 400:
            error_counter.labels(
                error_code=response.status_code,
                endpoint=request.url.path
            ).inc()

        return response

    except Exception as e:
        error_counter.labels(
            error_code=500,
            endpoint=request.url.path
        ).inc()
        raise
```

## Related Patterns & Skills

- [API Development](../skills/api-development.md) - API error handling
- [Microservices Patterns](./microservices-patterns.md) - Distributed error handling
- [Performance Optimization](../skills/performance-optimization.md) - Error impact on performance

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
