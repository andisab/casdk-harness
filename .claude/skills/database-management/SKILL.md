---
title: Database Management
description: Database schema design, migrations, query optimization, and data management best practices
tags: [skill, database, sql, postgresql, migrations, optimization, schema]
type: skill
version: "1.0.0"
category: backend-development
---

# Database Management

## Overview

This skill provides comprehensive database management capabilities including schema design, migration strategies, query optimization, indexing, and backup procedures. Use this skill for database architecture decisions, performance tuning, data integrity, and operational database management.

**When to use this skill:**
- Designing database schemas and relationships
- Creating and managing database migrations
- Optimizing slow database queries
- Implementing effective indexing strategies
- Managing database backups and disaster recovery
- Ensuring data integrity and consistency
- Scaling database operations

## Key Concepts

### Database Design Principles

**Normalization Levels:**
- **1NF (First Normal Form)**: Atomic values, no repeating groups
  - Each cell contains single value
  - Each record is unique

- **2NF (Second Normal Form)**: No partial dependencies on composite keys
  - Must be in 1NF
  - Non-key attributes depend on entire primary key

- **3NF (Third Normal Form)**: No transitive dependencies
  - Must be in 2NF
  - Non-key attributes depend only on primary key

**Strategic Denormalization:**
- Trade storage for query performance
- Use for read-heavy workloads
- Common in reporting/analytics tables
- Requires careful maintenance of redundant data

**Relationship Types:**

```
One-to-One:
User (1) ←→ (1) UserProfile

One-to-Many:
User (1) ←→ (N) Posts

Many-to-Many:
Posts (N) ←→ (N) Tags
  (requires junction table: post_tags)
```

**Data Type Selection Guide:**

```sql
-- Identity and Reference
id BIGSERIAL PRIMARY KEY,              -- Auto-incrementing, 8 bytes
uuid UUID NOT NULL DEFAULT gen_random_uuid(),  -- Distributed systems
user_id BIGINT NOT NULL,               -- Foreign key to BIGSERIAL

-- Text and Strings
email VARCHAR(255) NOT NULL,           -- Variable length with limit
name VARCHAR(100) NOT NULL,            -- Fixed max length
slug VARCHAR(100) NOT NULL,            -- URL-friendly identifier
description TEXT,                      -- Unlimited length
status VARCHAR(20) NOT NULL,           -- Small enum alternative
content TEXT NOT NULL,                 -- Long text content

-- Numbers
price DECIMAL(10,2) NOT NULL,          -- Exact monetary values (10 digits, 2 decimal)
quantity INTEGER NOT NULL,             -- Whole numbers
rating NUMERIC(3,2),                   -- Ratings like 4.50 (0.00-9.99)
views BIGINT NOT NULL DEFAULT 0,       -- Large counts

-- Dates and Times
created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),  -- Always use timezone
published_at TIMESTAMP WITH TIME ZONE,                       -- Nullable events
date_of_birth DATE,                                          -- Date only
duration INTERVAL,                                           -- Time spans

-- Boolean
is_active BOOLEAN NOT NULL DEFAULT true,
is_verified BOOLEAN NOT NULL DEFAULT false,

-- Semi-structured
metadata JSONB,                        -- JSON with indexing support
preferences JSONB,                     -- User preferences
tags TEXT[],                           -- Array of strings (PostgreSQL)

-- Special Types
ip_address INET,                       -- IP addresses
search_vector tsvector,                -- Full-text search
```

### Migration Strategies

**Types of Migrations:**

1. **Additive (Safe):**
   - Adding new tables
   - Adding nullable columns
   - Adding indexes (CONCURRENTLY)
   - Adding new constraints (NOT VALID)

2. **Transformative (Requires Care):**
   - Renaming columns
   - Changing data types
   - Moving data between columns
   - Splitting/merging tables

3. **Destructive (Dangerous):**
   - Dropping columns
   - Dropping tables
   - Removing constraints
   - Changing NOT NULL to nullable

**Zero-Downtime Migration Pattern:**

```python
# Step 1: Add new column (nullable)
def upgrade_step_1():
    op.add_column('users', sa.Column('full_name', sa.String(200), nullable=True))

# Deploy code that writes to both 'name' and 'full_name'

# Step 2: Backfill data
def upgrade_step_2():
    op.execute("UPDATE users SET full_name = name WHERE full_name IS NULL")

# Step 3: Make new column NOT NULL
def upgrade_step_3():
    op.alter_column('users', 'full_name', nullable=False)

# Deploy code that reads from 'full_name', still writes to both

# Step 4: Remove old column (next release)
def upgrade_step_4():
    op.drop_column('users', 'name')

# Deploy code that only uses 'full_name'
```

## Implementation

### Comprehensive PostgreSQL Schema Design

```sql
-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE users (
    -- Primary identification
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    -- Authentication
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,

    -- Profile information
    name VARCHAR(100) NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(500),

    -- Status and roles
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    is_admin BOOLEAN NOT NULL DEFAULT false,

    -- Soft delete
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Indexes for users table
CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_uuid ON users(uuid);
CREATE INDEX ix_users_active ON users(is_active) WHERE is_active = true AND deleted_at IS NULL;
CREATE INDEX ix_users_created_at ON users(created_at DESC);

-- Email case-insensitive unique index
CREATE UNIQUE INDEX ix_users_email_lower ON users(LOWER(email)) WHERE deleted_at IS NULL;

-- ============================================================================
-- POSTS TABLE
-- ============================================================================
CREATE TABLE posts (
    -- Primary identification
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    -- Relationships
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Content
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    excerpt VARCHAR(500),

    -- Status and visibility
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    is_featured BOOLEAN NOT NULL DEFAULT false,

    -- Engagement metrics
    views BIGINT NOT NULL DEFAULT 0,
    likes_count INTEGER NOT NULL DEFAULT 0,
    comments_count INTEGER NOT NULL DEFAULT 0,

    -- SEO and metadata
    seo_title VARCHAR(70),
    seo_description VARCHAR(160),
    metadata JSONB,

    -- Publishing
    published_at TIMESTAMP WITH TIME ZONE,

    -- Soft delete
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT status_check CHECK (status IN ('draft', 'published', 'archived', 'scheduled')),
    CONSTRAINT slug_format CHECK (slug ~* '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    CONSTRAINT published_at_check CHECK (
        (status = 'published' AND published_at IS NOT NULL) OR
        (status != 'published')
    )
);

-- Indexes for posts table
CREATE INDEX ix_posts_user_id ON posts(user_id);
CREATE INDEX ix_posts_status ON posts(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_posts_slug ON posts(slug) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ix_posts_user_slug ON posts(user_id, slug) WHERE deleted_at IS NULL;
CREATE INDEX ix_posts_published_at ON posts(published_at DESC) WHERE published_at IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_posts_featured ON posts(is_featured, published_at DESC) WHERE is_featured = true AND deleted_at IS NULL;

-- GIN index for JSONB metadata
CREATE INDEX ix_posts_metadata_gin ON posts USING GIN (metadata);

-- Full-text search
ALTER TABLE posts ADD COLUMN search_vector tsvector;

CREATE INDEX ix_posts_search_vector ON posts USING GIN(search_vector);

CREATE OR REPLACE FUNCTION posts_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.excerpt, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER posts_search_update
BEFORE INSERT OR UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION posts_search_trigger();

-- ============================================================================
-- TAGS TABLE (Many-to-Many with Posts)
-- ============================================================================
CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT slug_format CHECK (slug ~* '^[a-z0-9]+(?:-[a-z0-9]+)*$')
);

CREATE INDEX ix_tags_slug ON tags(slug);
CREATE INDEX ix_tags_usage_count ON tags(usage_count DESC);

-- Junction table for posts and tags
CREATE TABLE post_tags (
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, tag_id)
);

CREATE INDEX ix_post_tags_post_id ON post_tags(post_id);
CREATE INDEX ix_post_tags_tag_id ON post_tags(tag_id);

-- ============================================================================
-- COMMENTS TABLE (Hierarchical/Nested)
-- ============================================================================
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,

    content TEXT NOT NULL,

    is_edited BOOLEAN NOT NULL DEFAULT false,
    is_deleted BOOLEAN NOT NULL DEFAULT false,

    likes_count INTEGER NOT NULL DEFAULT 0,

    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT content_min_length CHECK (LENGTH(content) >= 1)
);

CREATE INDEX ix_comments_post_id ON comments(post_id, created_at DESC);
CREATE INDEX ix_comments_user_id ON comments(user_id);
CREATE INDEX ix_comments_parent_id ON comments(parent_id);

-- ============================================================================
-- AUDIT LOG TABLE
-- ============================================================================
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,

    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT NOT NULL,

    old_values JSONB,
    new_values JSONB,

    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT action_check CHECK (action IN ('create', 'update', 'delete', 'login', 'logout'))
);

CREATE INDEX ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX ix_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at DESC);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Updated_at trigger function (reusable)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_posts_updated_at BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_comments_updated_at BEFORE UPDATE ON comments
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Tag usage count trigger
CREATE OR REPLACE FUNCTION update_tag_usage_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE tags SET usage_count = usage_count + 1 WHERE id = NEW.tag_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE tags SET usage_count = usage_count - 1 WHERE id = OLD.tag_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tag_usage_on_post_tag_change
AFTER INSERT OR DELETE ON post_tags
FOR EACH ROW EXECUTE FUNCTION update_tag_usage_count();

-- Post metrics update trigger
CREATE OR REPLACE FUNCTION update_post_comment_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.deleted_at IS NULL THEN
        UPDATE posts SET comments_count = comments_count + 1 WHERE id = NEW.post_id;
    ELSIF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL) THEN
        UPDATE posts SET comments_count = comments_count - 1 WHERE id = COALESCE(NEW.post_id, OLD.post_id);
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_post_comment_count_trigger
AFTER INSERT OR UPDATE OR DELETE ON comments
FOR EACH ROW EXECUTE FUNCTION update_post_comment_count();
```

### Advanced Query Optimization

```sql
-- ============================================================================
-- QUERY OPTIMIZATION EXAMPLES
-- ============================================================================

-- BAD: N+1 Query Problem
SELECT * FROM posts WHERE status = 'published';
-- Then for each post in application code:
SELECT * FROM users WHERE id = post.user_id;
SELECT * FROM post_tags WHERE post_id = post.id;

-- GOOD: Single query with JOINs and aggregation
SELECT
    p.*,
    u.name AS author_name,
    u.avatar_url AS author_avatar,
    COALESCE(
        json_agg(
            json_build_object('id', t.id, 'name', t.name, 'slug', t.slug)
        ) FILTER (WHERE t.id IS NOT NULL),
        '[]'::json
    ) AS tags
FROM posts p
INNER JOIN users u ON p.user_id = u.id
LEFT JOIN post_tags pt ON p.id = pt.post_id
LEFT JOIN tags t ON pt.tag_id = t.id
WHERE p.status = 'published' AND p.deleted_at IS NULL
GROUP BY p.id, u.id
ORDER BY p.published_at DESC
LIMIT 20;

-- ============================================================================
-- Pagination: Cursor-based (better for large datasets)
-- ============================================================================

-- Get first page
SELECT id, title, created_at
FROM posts
WHERE status = 'published' AND deleted_at IS NULL
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Get next page (using last id and created_at from previous page)
SELECT id, title, created_at
FROM posts
WHERE status = 'published'
    AND deleted_at IS NULL
    AND (created_at, id) < ('2025-10-25 12:00:00', 12345)
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- ============================================================================
-- Full-Text Search (PostgreSQL)
-- ============================================================================

-- Search posts by title and content
SELECT
    id,
    title,
    excerpt,
    ts_rank(search_vector, query) AS rank
FROM posts,
    to_tsquery('english', 'fastapi & python') AS query
WHERE search_vector @@ query
    AND status = 'published'
    AND deleted_at IS NULL
ORDER BY rank DESC, published_at DESC
LIMIT 20;

-- Search with headline (highlighted snippets)
SELECT
    id,
    title,
    ts_headline('english', content, query, 'MaxWords=50, MinWords=25') AS snippet,
    ts_rank(search_vector, query) AS rank
FROM posts,
    to_tsquery('english', 'fastapi | python') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;

-- ============================================================================
-- Aggregation with Window Functions
-- ============================================================================

-- Get posts with running total of views
SELECT
    id,
    title,
    views,
    SUM(views) OVER (ORDER BY created_at) AS cumulative_views,
    AVG(views) OVER (PARTITION BY user_id) AS author_avg_views,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY views DESC) AS rank_in_author
FROM posts
WHERE deleted_at IS NULL;

-- ============================================================================
-- JSON Query (JSONB)
-- ============================================================================

-- Query by JSON field
SELECT * FROM posts
WHERE metadata->>'category' = 'tutorial'
    AND (metadata->'settings'->>'featured')::boolean = true;

-- Update JSON field
UPDATE posts
SET metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{reading_time}',
    '5'::jsonb
)
WHERE id = 123;

-- Add to JSON array
UPDATE posts
SET metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{related_posts}',
    COALESCE(metadata->'related_posts', '[]'::jsonb) || '456'::jsonb
)
WHERE id = 123;
```

### Connection Pooling & Transaction Management

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Database Engine with Connection Pooling
# ============================================================================

engine = create_engine(
    "postgresql://user:password@localhost:5432/mydb",

    # Connection pooling
    poolclass=QueuePool,
    pool_size=20,                    # Normal pool size
    max_overflow=10,                 # Extra connections when pool exhausted
    pool_timeout=30,                 # Seconds to wait for connection
    pool_recycle=3600,               # Recycle connections after 1 hour
    pool_pre_ping=True,              # Test connection before use

    # Query execution
    echo=False,                      # Log SQL queries (set True for debugging)
    echo_pool=False,                 # Log pool checkouts/returns

    # Connection options
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=utc"
    }
)

# Connection pool event listeners
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Execute on new connection."""
    logger.debug("New database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Execute when connection checked out from pool."""
    logger.debug("Connection checked out from pool")

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Don't expire objects after commit
)

# ============================================================================
# Session Management for FastAPI
# ============================================================================

def get_db() -> Session:
    """
    Dependency for FastAPI endpoints.
    Yields database session and ensures proper cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# Transaction Context Manager
# ============================================================================

@contextmanager
def transaction(db: Session, auto_commit: bool = True):
    """
    Context manager for database transactions.

    Usage:
        with transaction(db):
            # Your database operations
            db.add(user)
            db.add(post)
        # Auto-commits on success, rolls back on exception
    """
    try:
        yield db
        if auto_commit:
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed: {str(e)}")
        raise
    finally:
        db.flush()

# ============================================================================
# Advanced Transaction Patterns
# ============================================================================

async def transfer_funds_with_locking(
    from_user_id: int,
    to_user_id: int,
    amount: Decimal,
    db: Session
):
    """
    Transfer funds between users with pessimistic locking.
    Uses SELECT FOR UPDATE to prevent race conditions.
    """
    with transaction(db):
        # Lock rows to prevent concurrent modifications
        sender = db.query(User).filter(
            User.id == from_user_id
        ).with_for_update().first()

        if not sender:
            raise ValueError("Sender not found")

        if sender.balance < amount:
            raise ValueError("Insufficient funds")

        recipient = db.query(User).filter(
            User.id == to_user_id
        ).with_for_update().first()

        if not recipient:
            raise ValueError("Recipient not found")

        # Perform transfer
        sender.balance -= amount
        recipient.balance += amount

        # Log transaction
        transaction_log = TransactionLog(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount,
            type="transfer"
        )
        db.add(transaction_log)

        logger.info(
            f"Transferred {amount} from user {from_user_id} "
            f"to user {to_user_id}"
        )
```

## Best Practices

### Schema Design Best Practices

**Do:**
- ✅ Choose appropriate data types for columns
- ✅ Add NOT NULL constraints where data is required
- ✅ Create indexes on foreign keys
- ✅ Use check constraints for data validation at database level
- ✅ Add updated_at triggers for audit trails
- ✅ Use UUID for distributed systems or public IDs
- ✅ Implement soft deletes (deleted_at) for important data
- ✅ Use TIMESTAMP WITH TIME ZONE for all timestamps
- ✅ Add comments to tables and columns for documentation

**Don't:**
- ❌ Store calculated/derived values (use views or compute on query)
- ❌ Use VARCHAR without length limits
- ❌ Forget to index foreign keys (causes slow JOINs)
- ❌ Over-normalize (leads to complex joins and slow queries)
- ❌ Store binary files in database (use object storage like S3)
- ❌ Use reserved keywords as table/column names
- ❌ Mix snake_case and camelCase naming

### Migration Best Practices

**Do:**
- ✅ Version control all schema changes
- ✅ Make migrations reversible with downgrade functions
- ✅ Test migrations on production-like data first
- ✅ Use database transactions for migrations
- ✅ Create indexes concurrently in PostgreSQL (doesn't lock table)
- ✅ Document breaking changes in migration comments
- ✅ Review migrations in code review process
- ✅ Keep migrations small and focused

**Don't:**
- ❌ Modify existing migrations after they've been applied
- ❌ Drop columns without data migration plan
- ❌ Add NOT NULL constraints without default value or backfill
- ❌ Create indexes without CONCURRENTLY in production (locks table)
- ❌ Deploy application code before running migrations
- ❌ Combine data migrations with schema migrations

### Indexing Strategy Best Practices

**When to Create an Index:**
- Foreign key columns (for JOIN performance)
- Columns frequently used in WHERE clauses
- Columns used in ORDER BY
- Columns used in GROUP BY
- Columns used in JOIN conditions

**When NOT to Index:**
- Tables with very few rows (< 1000)
- Columns with low cardinality (few unique values)
- Columns rarely queried
- Write-heavy tables (indexes slow down inserts/updates)

**Index Types and Use Cases:**

```sql
-- B-tree (default) - Most common, handles =, <, >, <=, >=, BETWEEN, ORDER BY
CREATE INDEX idx_users_email ON users(email);

-- Partial Index - Smaller, faster for subset
CREATE INDEX idx_active_users ON users(email) WHERE is_active = true AND deleted_at IS NULL;

-- Composite Index - Multiple columns (order matters!)
CREATE INDEX idx_posts_user_status ON posts(user_id, status, published_at DESC);

-- Unique Index - Enforces uniqueness
CREATE UNIQUE INDEX idx_users_email_unique ON users(LOWER(email));

-- GIN Index - For JSONB, arrays, full-text search
CREATE INDEX idx_posts_metadata ON posts USING GIN(metadata);
CREATE INDEX idx_posts_tags ON posts USING GIN(tags);

-- GiST Index - For geometric data, full-text search
CREATE INDEX idx_posts_search ON posts USING GiST(search_vector);

-- Concurrent Index Creation - No lock on table (PostgreSQL)
CREATE INDEX CONCURRENTLY idx_posts_created_at ON posts(created_at DESC);
```

## Related Skills & Conventions

- [API Development](./api-development.md) - Integrating databases with APIs
- [Performance Optimization](./performance-optimization.md) - Query optimization techniques
- [Database Patterns](../patterns/database-patterns.md) - Advanced database patterns
- [PostgreSQL Schema Template](../templates/postgres-schema-template.md) - Ready-to-use schema

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
