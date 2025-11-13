---
title: Performance Optimization
description: Techniques for profiling, benchmarking, and optimizing application performance across database, API, and frontend
tags: [skill, performance, optimization, profiling, caching, monitoring]
type: skill
version: "1.0.0"
category: optimization
---

# Performance Optimization

## Overview

This skill provides comprehensive performance optimization techniques including profiling, database query optimization, caching strategies, frontend optimization, and monitoring. Use this skill to identify bottlenecks, improve response times, and scale applications efficiently.

**When to use this skill:**
- Diagnosing slow application performance
- Optimizing database queries
- Implementing caching strategies
- Reducing frontend bundle sizes
- Improving API response times
- Scaling applications for high traffic

## Key Concepts

### Performance Metrics

**Backend Metrics:**
- **Response Time**: Time to complete a request (target: <200ms for API)
- **Throughput**: Requests per second (RPS)
- **Database Query Time**: Time spent in database queries (target: <50ms)
- **CPU Usage**: Processor utilization (target: <70% average)
- **Memory Usage**: RAM consumption and garbage collection

**Frontend Metrics (Web Vitals):**
- **LCP (Largest Contentful Paint)**: <2.5s (good), <4s (needs improvement)
- **FID (First Input Delay)**: <100ms (good), <300ms (needs improvement)
- **CLS (Cumulative Layout Shift)**: <0.1 (good), <0.25 (needs improvement)
- **TTFB (Time to First Byte)**: <600ms
- **TTI (Time to Interactive)**: <3.8s

### Performance Optimization Process

1. **Measure**: Establish baseline metrics
2. **Identify**: Find bottlenecks through profiling
3. **Optimize**: Apply targeted optimizations
4. **Validate**: Measure improvements
5. **Monitor**: Continuous performance tracking

## Implementation

### Profiling and Benchmarking

```python
# Python profiling with cProfile
import cProfile
import pstats
from io import StringIO

def profile_function(func):
    """Decorator to profile a function."""
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        # Print stats
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        print(stream.getvalue())

        return result
    return wrapper

@profile_function
def slow_operation():
    # Your code here
    pass

# Line-by-line profiling with line_profiler
from line_profiler import LineProfiler

profiler = LineProfiler()
profiler.add_function(my_function)
profiler.enable()
my_function()
profiler.disable()
profiler.print_stats()

# Memory profiling
from memory_profiler import profile

@profile
def memory_intensive_function():
    large_list = [i for i in range(1000000)]
    return sum(large_list)
```

```javascript
// JavaScript performance measurement
console.time('operation');
// Your code here
console.timeEnd('operation');

// Performance API
const start = performance.now();
// Your code here
const end = performance.now();
console.log(`Operation took ${end - start}ms`);

// React Profiler
import { Profiler } from 'react';

function onRenderCallback(
  id,
  phase,
  actualDuration,
  baseDuration,
  startTime,
  commitTime
) {
  console.log(`${id} (${phase}) took ${actualDuration}ms`);
}

<Profiler id="MyComponent" onRender={onRenderCallback}>
  <MyComponent />
</Profiler>
```

### Database Optimization

```sql
-- EXPLAIN ANALYZE to understand query performance
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT p.*, u.name as author_name
FROM posts p
INNER JOIN users u ON p.user_id = u.id
WHERE p.status = 'published'
  AND p.created_at > NOW() - INTERVAL '7 days'
ORDER BY p.views DESC
LIMIT 20;

-- Identify missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
  AND n_distinct > 100  -- High cardinality
  AND correlation < 0.1  -- Low correlation with physical order
ORDER BY n_distinct DESC;

-- Find slow queries (PostgreSQL)
SELECT
  query,
  calls,
  total_time,
  mean_time,
  max_time,
  stddev_time
FROM pg_stat_statements
WHERE mean_time > 100  -- Queries averaging >100ms
ORDER BY mean_time DESC
LIMIT 20;

-- Optimize N+1 queries with joins
-- BAD: N+1 problem
SELECT * FROM posts;  -- 1 query
-- Then for each post:
SELECT * FROM comments WHERE post_id = ?;  -- N queries

-- GOOD: Single query with join
SELECT
  p.*,
  COALESCE(
    json_agg(
      json_build_object('id', c.id, 'content', c.content)
    ) FILTER (WHERE c.id IS NOT NULL),
    '[]'
  ) as comments
FROM posts p
LEFT JOIN comments c ON p.id = c.post_id
GROUP BY p.id;

-- Index optimization
CREATE INDEX CONCURRENTLY idx_posts_status_created
ON posts(status, created_at DESC)
WHERE deleted_at IS NULL;

-- Partial index for active records only
CREATE INDEX idx_active_users ON users(email)
WHERE is_active = true AND deleted_at IS NULL;
```

### Caching Strategies

```python
# Application-level caching (in-memory)
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=128)
def get_user_permissions(user_id: int):
    """Cache user permissions in memory."""
    return db.query(Permission).filter(
        Permission.user_id == user_id
    ).all()

# Redis distributed caching
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cached_data(key: str, ttl: int = 3600):
    """Get data from cache or compute if missing."""
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)

    # Cache miss - compute data
    data = expensive_computation()

    # Store in cache
    redis_client.setex(key, ttl, json.dumps(data))
    return data

# Cache invalidation
def invalidate_user_cache(user_id: int):
    """Invalidate all cache keys for a user."""
    pattern = f"user:{user_id}:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)

# Write-through cache pattern
def update_user(user_id: int, data: dict):
    """Update database and cache simultaneously."""
    # Update database
    user = db.query(User).filter(User.id == user_id).first()
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()

    # Update cache
    cache_key = f"user:{user_id}"
    redis_client.setex(cache_key, 3600, json.dumps(user.to_dict()))

    return user
```

```python
# FastAPI with response caching
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

app = FastAPI()

@app.on_event("startup")
async def startup():
    redis_client = redis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis_client), prefix="api-cache")

@app.get("/users")
@cache(expire=300)  # Cache for 5 minutes
async def list_users():
    return await get_users_from_db()

# Conditional caching based on query params
@app.get("/posts")
@cache(expire=60)
async def list_posts(status: str = "published"):
    return await get_posts_by_status(status)
```

### Frontend Optimization

```javascript
// Code splitting with React lazy loading
import { lazy, Suspense } from 'react';

const HeavyComponent = lazy(() => import('./HeavyComponent'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <HeavyComponent />
    </Suspense>
  );
}

// Route-based code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Profile = lazy(() => import('./pages/Profile'));

// Memoization to prevent unnecessary re-renders
import { memo, useMemo, useCallback } from 'react';

// memo: Prevent re-render if props haven't changed
const ExpensiveComponent = memo(({ data }) => {
  return <div>{data.map(item => <Item key={item.id} {...item} />)}</div>;
});

// useMemo: Cache expensive calculations
function DataTable({ items }) {
  const sortedItems = useMemo(
    () => items.sort((a, b) => b.score - a.score),
    [items]  // Only recalculate when items change
  );

  return <Table data={sortedItems} />;
}

// useCallback: Cache function references
function Parent() {
  const handleClick = useCallback((id) => {
    console.log('Clicked', id);
  }, []);  // Function reference stays stable

  return <Child onClick={handleClick} />;
}

// Virtual scrolling for large lists
import { FixedSizeList } from 'react-window';

function LargeList({ items }) {
  return (
    <FixedSizeList
      height={600}
      itemCount={items.length}
      itemSize={50}
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>{items[index].name}</div>
      )}
    </FixedSizeList>
  );
}

// Image optimization
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Hero"
  width={800}
  height={600}
  loading="lazy"  // Lazy load images
  placeholder="blur"  // Show placeholder while loading
  quality={75}  // Reduce quality for faster loading
/>

// Bundle size analysis
// package.json scripts:
{
  "analyze": "ANALYZE=true next build",
  "build": "next build"
}

// Webpack bundle analyzer
import { BundleAnalyzerPlugin } from 'webpack-bundle-analyzer';

module.exports = {
  plugins: [
    new BundleAnalyzerPlugin({
      analyzerMode: 'static',
      openAnalyzer: false,
      reportFilename: 'bundle-report.html'
    })
  ]
};
```

### API Performance Optimization

```python
# Response compression
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Pagination for large datasets
from fastapi import Query

@app.get("/posts")
async def list_posts(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Paginate to avoid large responses."""
    posts = db.query(Post).offset(offset).limit(limit).all()
    total = db.query(Post).count()

    return {
        "data": posts,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    }

# Field selection (sparse fieldsets)
@app.get("/users")
async def list_users(fields: str = None):
    """Allow clients to request only needed fields."""
    query = db.query(User)

    if fields:
        field_list = fields.split(',')
        columns = [getattr(User, f) for f in field_list if hasattr(User, f)]
        query = query.with_entities(*columns)

    return query.all()

# HTTP caching headers
from fastapi import Response

@app.get("/posts/{post_id}")
async def get_post(post_id: int, response: Response):
    """Set cache headers for GET endpoints."""
    post = db.query(Post).filter(Post.id == post_id).first()

    # Cache for 5 minutes
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["ETag"] = f'"{post.updated_at.timestamp()}"'

    return post

# Database connection pooling
engine = create_engine(
    database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Best Practices

### Database Performance

**Do:**
- ✅ Use EXPLAIN ANALYZE to understand query plans
- ✅ Create indexes on frequently queried columns
- ✅ Use connection pooling
- ✅ Implement pagination for large datasets
- ✅ Use database-level caching (PostgreSQL shared_buffers)
- ✅ Avoid SELECT \* (request only needed columns)
- ✅ Use appropriate data types
- ✅ Monitor slow queries

**Don't:**
- ❌ Create too many indexes (slows writes)
- ❌ Use OFFSET for large offsets (use cursor pagination)
- ❌ Perform calculations in WHERE clauses
- ❌ Use LIKE with leading wildcards (%search)
- ❌ Load entire tables into memory

### Caching Strategy

**Cache Hierarchy:**
1. **Browser Cache**: Static assets (CSS, JS, images)
2. **CDN Cache**: Global distribution of static content
3. **Application Cache**: In-memory (Redis, Memcached)
4. **Database Cache**: Query result caching

**Cache Invalidation Strategies:**
- **TTL (Time-to-Live)**: Automatic expiration
- **Event-based**: Invalidate on data changes
- **Versioned Keys**: Include version in cache key

### Frontend Performance

**Do:**
- ✅ Code split by route
- ✅ Lazy load non-critical components
- ✅ Optimize images (WebP, proper sizing)
- ✅ Use CDN for static assets
- ✅ Minimize bundle size
- ✅ Tree shake unused code
- ✅ Use production builds
- ✅ Implement virtual scrolling for large lists

**Don't:**
- ❌ Import entire libraries (import only what you need)
- ❌ Block main thread with heavy computation
- ❌ Cause unnecessary re-renders
- ❌ Load everything upfront

## Monitoring and Observability

```python
# Application Performance Monitoring (APM)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions
    profiles_sample_rate=0.1  # 10% profiling
)

# Custom metrics
from prometheus_client import Counter, Histogram, Gauge

# Request counter
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Response time histogram
response_time = Histogram(
    'http_response_time_seconds',
    'HTTP response time',
    ['endpoint']
)

# Active connections gauge
active_connections = Gauge(
    'active_db_connections',
    'Number of active database connections'
)

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    request_count.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    response_time.labels(endpoint=request.url.path).observe(duration)

    return response

# Structured logging
import structlog

logger = structlog.get_logger()

logger.info(
    "user_created",
    user_id=user.id,
    email=user.email,
    duration_ms=duration * 1000
)
```

## Related Skills & Conventions

- [Database Management](./database-management.md) - Query optimization
- [API Development](./api-development.md) - API performance patterns
- [Caching Strategies Pattern](../patterns/caching-strategies.md) - Caching architectures

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
