---
title: Caching Strategies
description: Application-level, distributed, and CDN caching patterns with implementation guidance
tags: [pattern, caching, redis, performance, cdn]
type: pattern
version: "1.0.0"
category: performance
---

# Caching Strategies

## Overview

This pattern guide covers caching architectures including application-level caching, distributed caching with Redis/Memcached, CDN strategies, cache invalidation patterns, and eviction policies. Use these patterns to improve application performance, reduce database load, and scale effectively.

**When to use these patterns:**
- Reducing database query load
- Improving API response times
- Scaling read-heavy applications
- Handling expensive computations
- Serving static assets globally
- Managing session data

## Patterns

### 1. Application-Level Caching (In-Memory)

**Use Case:** Cache expensive function results, frequently accessed data

**Implementation:**

```python
# Python in-memory caching with LRU cache
from functools import lru_cache
from typing import List, Dict
import time

@lru_cache(maxsize=128)
def get_user_permissions(user_id: int) -> List[str]:
    """Cache user permissions in memory."""
    # Expensive database query
    permissions = db.query(Permission).filter(
        Permission.user_id == user_id
    ).all()
    return [p.name for p in permissions]

# Custom cache implementation with TTL
class TTLCache:
    """Time-to-live cache implementation."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl_seconds

    def get(self, key: str):
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value):
        """Store value in cache with timestamp."""
        self.cache[key] = (value, time.time())

    def delete(self, key: str):
        """Remove key from cache."""
        self.cache.pop(key, None)

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()

# Usage
cache = TTLCache(ttl_seconds=300)  # 5-minute TTL

def get_trending_posts():
    cached = cache.get("trending_posts")
    if cached:
        return cached

    # Expensive query
    posts = db.query(Post).order_by(Post.views.desc()).limit(10).all()
    cache.set("trending_posts", posts)
    return posts
```

**Pros:**
- ✅ Extremely fast (nanosecond access)
- ✅ No network latency
- ✅ Simple implementation
- ✅ No external dependencies

**Cons:**
- ❌ Not shared across application instances
- ❌ Lost on restart
- ❌ Memory constrained
- ❌ No persistence

### 2. Distributed Caching (Redis)

**Use Case:** Shared cache across multiple application instances, session storage

**Architecture:**
```
App Instance 1 ──┐
App Instance 2 ──┼──> Redis Cluster
App Instance 3 ──┘
```

**Implementation:**

```python
# Redis distributed caching with FastAPI
import redis
import json
from typing import Optional
from fastapi import FastAPI, Depends

app = FastAPI()

# Redis connection pool
redis_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    max_connections=10,
    decode_responses=True
)

def get_redis() -> redis.Redis:
    """Dependency for Redis connection."""
    return redis.Redis(connection_pool=redis_pool)

class CacheService:
    """Distributed cache service."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def get(self, key: str) -> Optional[dict]:
        """Get value from cache."""
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    def set(self, key: str, value: dict, ttl: int = 3600):
        """Store value in cache with TTL (seconds)."""
        self.redis.setex(key, ttl, json.dumps(value))

    def delete(self, key: str):
        """Delete key from cache."""
        self.redis.delete(key)

    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.redis.exists(key) > 0

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    cache: CacheService = Depends(lambda: CacheService(get_redis()))
):
    """Get user with caching."""
    cache_key = f"user:{user_id}"

    # Try cache first
    cached_user = cache.get(cache_key)
    if cached_user:
        return {"data": cached_user, "source": "cache"}

    # Cache miss - fetch from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Store in cache
    user_dict = user.to_dict()
    cache.set(cache_key, user_dict, ttl=3600)  # 1 hour

    return {"data": user_dict, "source": "database"}
```

### 3. Cache Patterns

#### Cache-Aside (Lazy Loading)

**Pattern:** Application manages cache explicitly

```python
def get_product(product_id: int):
    """Cache-aside pattern."""
    cache_key = f"product:{product_id}"

    # 1. Try to get from cache
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 2. Cache miss - load from database
    product = db.query(Product).filter(Product.id == product_id).first()

    # 3. Store in cache
    if product:
        cache.set(cache_key, product.to_dict(), ttl=3600)

    return product
```

#### Write-Through Cache

**Pattern:** Update cache and database simultaneously

```python
def update_product(product_id: int, data: dict):
    """Write-through cache pattern."""
    # 1. Update database
    product = db.query(Product).filter(Product.id == product_id).first()
    for key, value in data.items():
        setattr(product, key, value)
    db.commit()

    # 2. Update cache immediately
    cache_key = f"product:{product_id}"
    cache.set(cache_key, product.to_dict(), ttl=3600)

    return product
```

#### Write-Behind (Write-Back) Cache

**Pattern:** Update cache immediately, database asynchronously

```python
from celery import Celery

celery_app = Celery('tasks', broker='redis://localhost:6379')

@celery_app.task
def persist_to_database(product_id: int, data: dict):
    """Asynchronous database write."""
    product = db.query(Product).filter(Product.id == product_id).first()
    for key, value in data.items():
        setattr(product, key, value)
    db.commit()

def update_product_write_behind(product_id: int, data: dict):
    """Write-behind cache pattern."""
    # 1. Update cache immediately (fast response)
    cache_key = f"product:{product_id}"
    cache.set(cache_key, data, ttl=3600)

    # 2. Queue database update asynchronously
    persist_to_database.delay(product_id, data)

    return {"status": "accepted", "product_id": product_id}
```

### 4. Cache Invalidation Strategies

```python
# Strategy 1: Time-based invalidation (TTL)
cache.set("user:123", user_data, ttl=3600)  # Expires in 1 hour

# Strategy 2: Event-based invalidation
def update_user(user_id: int, data: dict):
    """Invalidate cache on update."""
    user = update_user_in_db(user_id, data)

    # Invalidate related caches
    cache.delete(f"user:{user_id}")
    cache.delete_pattern(f"user:{user_id}:*")

    return user

# Strategy 3: Versioned keys
def get_user_v2(user_id: int, version: int = 1):
    """Use version in cache key."""
    cache_key = f"user:{user_id}:v{version}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    user = fetch_user_from_db(user_id)
    cache.set(cache_key, user, ttl=86400)  # 24 hours
    return user

# Strategy 4: Cache tagging
class TaggedCache:
    """Cache with tag-based invalidation."""

    def set_with_tags(self, key: str, value: dict, tags: List[str], ttl: int):
        """Store value with associated tags."""
        # Store value
        self.redis.setex(key, ttl, json.dumps(value))

        # Associate with tags
        for tag in tags:
            self.redis.sadd(f"tag:{tag}", key)
            self.redis.expire(f"tag:{tag}", ttl)

    def invalidate_tag(self, tag: str):
        """Invalidate all keys with given tag."""
        keys = self.redis.smembers(f"tag:{tag}")
        if keys:
            self.redis.delete(*keys)
            self.redis.delete(f"tag:{tag}")

# Usage
tagged_cache.set_with_tags(
    "product:123",
    product_data,
    tags=["products", "category:electronics", "brand:apple"],
    ttl=3600
)

# Invalidate all products in category
tagged_cache.invalidate_tag("category:electronics")
```

### 5. CDN Caching

**Use Case:** Global distribution of static assets

**Implementation:**

```python
# FastAPI with cache headers
from fastapi import Response
from datetime import datetime, timedelta

@app.get("/api/posts/{post_id}")
async def get_post(post_id: int, response: Response):
    """API endpoint with HTTP caching."""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404)

    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
    response.headers["ETag"] = f'"{post.updated_at.timestamp()}"'
    response.headers["Last-Modified"] = post.updated_at.strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    return post

# Conditional requests support
@app.get("/images/{image_id}")
async def get_image(image_id: str, if_none_match: str = Header(None)):
    """Serve image with ETag support."""
    image = get_image_from_storage(image_id)
    etag = f'"{image.hash}"'

    # Return 304 if client has current version
    if if_none_match == etag:
        return Response(status_code=304)

    return Response(
        content=image.data,
        media_type="image/jpeg",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=31536000"  # 1 year
        }
    )
```

**CDN Configuration (Cloudflare example):**

```yaml
# Cloudflare Page Rules
patterns:
  # Cache static assets aggressively
  - pattern: "*.example.com/static/*"
    cache_level: "cache_everything"
    edge_cache_ttl: 2592000  # 30 days
    browser_cache_ttl: 2592000

  # Cache API responses briefly
  - pattern: "api.example.com/v1/public/*"
    cache_level: "cache_everything"
    edge_cache_ttl: 300  # 5 minutes
    browser_cache_ttl: 300

  # Don't cache dynamic content
  - pattern: "api.example.com/v1/users/*"
    cache_level: "bypass"
```

## Best Practices

### Cache Design Principles

**Do:**
- ✅ Use appropriate cache hierarchy (in-memory → Redis → CDN)
- ✅ Set reasonable TTL values based on data volatility
- ✅ Implement cache warming for critical data
- ✅ Monitor cache hit rates (target: >80%)
- ✅ Use cache keys consistently (namespace:id:attribute)
- ✅ Handle cache failures gracefully (fallback to database)
- ✅ Compress large cached values

**Don't:**
- ❌ Cache user-specific sensitive data without encryption
- ❌ Use unbounded cache sizes (set max memory limits)
- ❌ Cache data that changes frequently (< 1 minute volatility)
- ❌ Ignore cache stampede problem (use locking)
- ❌ Cache everything (be selective)

### Cache Key Naming Conventions

```python
# Good cache key patterns
"user:{user_id}"                      # user:12345
"user:{user_id}:profile"              # user:12345:profile
"posts:trending:page:{page}"          # posts:trending:page:1
"product:{id}:reviews:count"          # product:456:reviews:count

# Avoid
"user12345"                           # Hard to pattern match
"u_12345"                             # Unclear namespace
"user:profile:12345"                  # Inconsistent ordering
```

### Cache Stampede Prevention

```python
import threading

class StampedeProtectedCache:
    """Cache with stampede protection using locks."""

    def __init__(self, cache_service, redis_client):
        self.cache = cache_service
        self.redis = redis_client

    def get_or_compute(self, key: str, compute_func, ttl: int = 3600):
        """Get from cache or compute with lock protection."""
        # Try cache first
        cached = self.cache.get(key)
        if cached:
            return cached

        # Acquire distributed lock
        lock_key = f"lock:{key}"
        lock = self.redis.set(lock_key, "1", nx=True, ex=10)  # 10-second lock

        if lock:
            # This instance won the lock - compute value
            try:
                value = compute_func()
                self.cache.set(key, value, ttl=ttl)
                return value
            finally:
                self.redis.delete(lock_key)
        else:
            # Another instance is computing - wait and retry
            time.sleep(0.1)
            return self.get_or_compute(key, compute_func, ttl)
```

## Related Patterns & Skills

- [Performance Optimization](../skills/performance-optimization.md) - Optimization strategies
- [API Development](../skills/api-development.md) - API caching patterns
- [Database Management](../skills/database-management.md) - Database query optimization

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
