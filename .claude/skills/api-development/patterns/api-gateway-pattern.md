---
title: API Gateway Pattern
description: API Gateway architecture with routing, authentication, rate limiting, and service orchestration
tags: [pattern, api-gateway, microservices, routing, security]
type: pattern
version: "1.0.0"
category: architecture
---

# API Gateway Pattern

## Overview

The API Gateway pattern provides a single entry point for client requests, handling cross-cutting concerns like authentication, rate limiting, routing, and request/response transformation. This pattern is essential for microservices architectures and distributed systems.

**When to use this pattern:**
- Building microservices architecture
- Implementing centralized authentication/authorization
- Managing API versioning across services
- Enforcing rate limiting and throttling
- Transforming requests/responses for different clients
- Aggregating data from multiple services

## Core Responsibilities

### 1. Request Routing
- Route requests to appropriate backend services
- Load balancing across service instances
- Service discovery integration
- Path-based and header-based routing

### 2. Authentication & Authorization
- Centralized authentication (JWT, OAuth 2.0)
- Token validation and refresh
- Role-based access control (RBAC)
- API key management

### 3. Rate Limiting & Throttling
- Per-client rate limits
- Burst handling
- Quota management
- DDoS protection

### 4. Request/Response Transformation
- Protocol translation (HTTP, WebSocket, gRPC)
- Request/response formatting
- Data aggregation from multiple services
- Versioning and backward compatibility

### 5. Cross-Cutting Concerns
- Logging and monitoring
- Circuit breaker implementation
- Request/response caching
- Error handling and retry logic

## Implementation Patterns

### 1. Custom FastAPI Gateway

**Use Case:** Lightweight gateway for Python microservices

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Dict, Optional
import time
from datetime import datetime, timedelta
from collections import defaultdict

app = FastAPI(title="API Gateway")

# Service registry
SERVICE_REGISTRY = {
    "users": "http://users-service:8001",
    "orders": "http://orders-service:8002",
    "products": "http://products-service:8003",
    "payments": "http://payments-service:8004"
}

# Rate limiting store (use Redis in production)
rate_limit_store: Dict[str, list] = defaultdict(list)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RateLimiter:
    """Rate limiter with sliding window algorithm."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        rate_limit_store[client_id] = [
            req_time for req_time in rate_limit_store[client_id]
            if req_time > window_start
        ]

        # Check limit
        if len(rate_limit_store[client_id]) >= self.requests_per_minute:
            return False

        # Record request
        rate_limit_store[client_id].append(now)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """Get seconds until rate limit resets."""
        if not rate_limit_store[client_id]:
            return 0

        oldest_request = min(rate_limit_store[client_id])
        retry_after = int(oldest_request + self.window_seconds - time.time())
        return max(0, retry_after)

rate_limiter = RateLimiter(requests_per_minute=100)

async def verify_api_key(api_key: str = Header(None)) -> str:
    """Verify API key and return client ID."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Verify against database/cache (simplified)
    client_id = api_key  # In production, lookup client ID from API key

    # Check rate limit
    if not rate_limiter.is_allowed(client_id):
        retry_after = rate_limiter.get_retry_after(client_id)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

    return client_id

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and responses."""
    start_time = time.time()

    # Log request
    logger.info(
        "gateway_request",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None
    )

    # Process request
    response = await call_next(request)

    # Log response
    duration = time.time() - start_time
    logger.info(
        "gateway_response",
        status=response.status_code,
        duration_ms=duration * 1000
    )

    # Add custom headers
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    response.headers["X-Gateway-Version"] = "1.0.0"

    return response

@app.get("/health")
async def health_check():
    """Gateway health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(
    service: str,
    path: str,
    request: Request,
    client_id: str = Depends(verify_api_key)
):
    """
    Proxy requests to backend services.

    Example:
      GET /users/v1/profile/123 → http://users-service:8001/v1/profile/123
    """
    # Check if service exists
    if service not in SERVICE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")

    # Build target URL
    backend_url = f"{SERVICE_REGISTRY[service]}/{path}"

    # Get query parameters
    query_params = dict(request.query_params)

    # Get request body if present
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Forward headers (exclude hop-by-hop headers)
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "connection", "keep-alive"]
    }

    # Add gateway-specific headers
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Client-ID"] = client_id
    headers["X-Gateway"] = "api-gateway/1.0"

    try:
        # Make request to backend service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=backend_url,
                params=query_params,
                content=body,
                headers=headers
            )

        # Return response with original status code and headers
        return JSONResponse(
            content=response.json() if response.text else None,
            status_code=response.status_code,
            headers=dict(response.headers)
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error("gateway_proxy_error", error=str(e), service=service)
        raise HTTPException(status_code=500, detail="Internal gateway error")

@app.get("/api/v1/aggregate/user/{user_id}")
async def aggregate_user_data(
    user_id: int,
    client_id: str = Depends(verify_api_key)
):
    """
    Aggregate data from multiple services.

    Combines user profile, orders, and preferences into single response.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Make parallel requests to multiple services
        user_response, orders_response, prefs_response = await asyncio.gather(
            client.get(f"{SERVICE_REGISTRY['users']}/v1/users/{user_id}"),
            client.get(f"{SERVICE_REGISTRY['orders']}/v1/users/{user_id}/orders"),
            client.get(f"{SERVICE_REGISTRY['users']}/v1/users/{user_id}/preferences"),
            return_exceptions=True
        )

        # Aggregate responses
        result = {
            "user": user_response.json() if not isinstance(user_response, Exception) else None,
            "orders": orders_response.json() if not isinstance(orders_response, Exception) else [],
            "preferences": prefs_response.json() if not isinstance(prefs_response, Exception) else {}
        }

        return result
```

### 2. Circuit Breaker Pattern

**Use Case:** Prevent cascading failures in distributed systems

```python
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        recovery_timeout: int = 30
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        # Check if circuit should transition to half-open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise HTTPException(
                    status_code=503,
                    detail="Circuit breaker open - service unavailable"
                )

        try:
            # Execute function
            result = await func(*args, **kwargs)

            # Success - reset circuit if half-open
            if self.state == CircuitState.HALF_OPEN:
                self._reset()

            return result

        except Exception as e:
            # Record failure
            self._record_failure()

            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    failures=self.failure_count,
                    service=func.__name__
                )

            raise e

    def _record_failure(self):
        """Record service failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("circuit_breaker_closed")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt recovery."""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

# Usage with service calls
users_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

async def call_users_service(user_id: int):
    """Call users service with circuit breaker."""
    async def make_request():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVICE_REGISTRY['users']}/users/{user_id}")
            response.raise_for_status()
            return response.json()

    return await users_circuit.call(make_request)
```

### 3. Request Transformation

```python
class RequestTransformer:
    """Transform requests for different API versions."""

    @staticmethod
    def v1_to_v2(request_data: dict) -> dict:
        """Transform v1 request format to v2."""
        return {
            "user_email": request_data.get("email"),
            "full_name": request_data.get("name"),
            "contact_info": {
                "phone": request_data.get("phone"),
                "address": request_data.get("address")
            },
            "preferences": {
                "newsletter": request_data.get("newsletter", False)
            }
        }

    @staticmethod
    def v2_to_v1(response_data: dict) -> dict:
        """Transform v2 response format to v1."""
        return {
            "email": response_data.get("user_email"),
            "name": response_data.get("full_name"),
            "phone": response_data.get("contact_info", {}).get("phone"),
            "address": response_data.get("contact_info", {}).get("address"),
            "newsletter": response_data.get("preferences", {}).get("newsletter")
        }

@app.post("/api/v1/users")
async def create_user_v1(request: Request):
    """v1 endpoint that uses v2 backend."""
    request_data = await request.json()

    # Transform v1 request to v2 format
    v2_request = RequestTransformer.v1_to_v2(request_data)

    # Call v2 backend
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVICE_REGISTRY['users']}/v2/users",
            json=v2_request
        )

    # Transform v2 response back to v1 format
    v2_response = response.json()
    v1_response = RequestTransformer.v2_to_v1(v2_response)

    return v1_response
```

## Best Practices

### Gateway Design Principles

**Do:**
- ✅ Keep gateway stateless (use external cache/database)
- ✅ Implement circuit breakers for all external calls
- ✅ Use connection pooling for backend requests
- ✅ Cache authentication/authorization decisions
- ✅ Log all requests with correlation IDs
- ✅ Implement health checks for all services
- ✅ Use service discovery (Consul, etcd, Kubernetes DNS)
- ✅ Version your gateway API

**Don't:**
- ❌ Implement business logic in gateway
- ❌ Make the gateway a single point of failure
- ❌ Bypass gateway in internal service communication
- ❌ Store session state in gateway
- ❌ Make synchronous calls to multiple services sequentially

### Security Best Practices

```python
# JWT validation example
from jose import jwt, JWTError

async def validate_jwt(token: str = Header(None, alias="Authorization")):
    """Validate JWT token."""
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = token.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Performance Optimization

- Use async/await for I/O operations
- Implement request/response compression
- Cache frequently accessed data (user permissions, service configs)
- Use HTTP/2 for backend communication
- Implement connection pooling
- Set appropriate timeouts for backend calls

## Related Patterns & Skills

- [Microservices Patterns](./microservices-patterns.md) - Service communication
- [Authentication Patterns](./authentication-patterns.md) - Auth strategies
- [Caching Strategies](./caching-strategies.md) - Gateway caching
- [API Development](../skills/api-development.md) - API design

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
