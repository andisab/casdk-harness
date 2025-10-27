---
title: PostgreSQL Schema Template
description: Production-ready PostgreSQL database schema with best practices, triggers, indexes, and audit logging
tags: [template, postgresql, database, schema, sql]
type: template
version: "1.0.0"
category: data
---

# PostgreSQL Schema Template

## Overview

This template provides a production-ready PostgreSQL database schema with common patterns including UUID primary keys, timestamps, soft deletes, audit logging, full-text search, and JSONB support. Use this template as a foundation for building scalable database schemas.

**Features:**
- UUID primary keys with BIGSERIAL fallback
- Automatic timestamp management (created_at, updated_at)
- Soft delete pattern
- Audit logging
- Full-text search support
- JSONB for flexible data
- Proper indexes and constraints
- Database functions and triggers

## Complete Schema

### init.sql - Database Initialization

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- For GIN indexes

-- Create audit schema
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================================
-- BASE TABLES
-- ============================================================================

-- Users table
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create indexes
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_uuid ON users(uuid);
CREATE INDEX idx_users_created_at ON users(created_at DESC);
CREATE INDEX idx_users_active ON users(is_active) WHERE deleted_at IS NULL;

-- User profiles (one-to-one with users)
CREATE TABLE user_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    bio TEXT,
    avatar_url VARCHAR(500),
    phone VARCHAR(20),
    date_of_birth DATE,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT phone_format CHECK (phone ~ '^\+?[1-9]\d{1,14}$')
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_preferences ON user_profiles USING GIN (preferences);

-- Posts table
CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    author_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    published_at TIMESTAMP WITH TIME ZONE,
    view_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    search_vector tsvector,  -- Full-text search
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT status_values CHECK (status IN ('draft', 'published', 'archived'))
);

-- Indexes for posts
CREATE INDEX idx_posts_author_id ON posts(author_id);
CREATE INDEX idx_posts_slug ON posts(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_posts_status ON posts(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_posts_published_at ON posts(published_at DESC) WHERE status = 'published';
CREATE INDEX idx_posts_search_vector ON posts USING GIN(search_vector);
CREATE INDEX idx_posts_metadata ON posts USING GIN(metadata);

-- Comments table
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_edited BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_author_id ON comments(author_id);
CREATE INDEX idx_comments_parent ON comments(parent_comment_id);
CREATE INDEX idx_comments_created_at ON comments(created_at DESC);

-- Tags table (many-to-many with posts)
CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_slug ON tags(slug);

-- Post tags junction table
CREATE TABLE post_tags (
    post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (post_id, tag_id)
);

CREATE INDEX idx_post_tags_post_id ON post_tags(post_id);
CREATE INDEX idx_post_tags_tag_id ON post_tags(tag_id);

-- ============================================================================
-- AUDIT LOGGING
-- ============================================================================

CREATE TABLE audit.audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    record_id BIGINT NOT NULL,
    action VARCHAR(10) NOT NULL,  -- INSERT, UPDATE, DELETE
    old_data JSONB,
    new_data JSONB,
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT action_values CHECK (action IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE INDEX idx_audit_log_table_record ON audit.audit_log(table_name, record_id);
CREATE INDEX idx_audit_log_changed_by ON audit.audit_log(changed_by);
CREATE INDEX idx_audit_log_changed_at ON audit.audit_log(changed_at DESC);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to all relevant tables
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_comments_updated_at
    BEFORE UPDATE ON comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function: Update full-text search vector
CREATE OR REPLACE FUNCTION update_post_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_posts_search_vector
    BEFORE INSERT OR UPDATE OF title, content ON posts
    FOR EACH ROW
    EXECUTE FUNCTION update_post_search_vector();

-- Function: Audit log trigger
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    -- Get current user ID from session variable (set by application)
    v_user_id := NULLIF(current_setting('app.current_user_id', TRUE), '')::BIGINT;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit.audit_log (table_name, record_id, action, new_data, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', to_jsonb(NEW), v_user_id);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit.audit_log (table_name, record_id, action, old_data, new_data, changed_by)
        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW), v_user_id);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit.audit_log (table_name, record_id, action, old_data, changed_by)
        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', to_jsonb(OLD), v_user_id);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers
CREATE TRIGGER audit_users
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_posts
    AFTER INSERT OR UPDATE OR DELETE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- ============================================================================
-- USEFUL FUNCTIONS
-- ============================================================================

-- Function: Generate unique slug
CREATE OR REPLACE FUNCTION generate_unique_slug(base_slug TEXT, table_name TEXT, column_name TEXT)
RETURNS TEXT AS $$
DECLARE
    new_slug TEXT;
    counter INTEGER := 0;
BEGIN
    new_slug := base_slug;

    LOOP
        IF counter > 0 THEN
            new_slug := base_slug || '-' || counter;
        END IF;

        -- Check if slug exists
        EXECUTE format('SELECT 1 FROM %I WHERE %I = $1', table_name, column_name)
        USING new_slug;

        IF NOT FOUND THEN
            RETURN new_slug;
        END IF;

        counter := counter + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function: Soft delete
CREATE OR REPLACE FUNCTION soft_delete(table_name TEXT, record_id BIGINT)
RETURNS VOID AS $$
BEGIN
    EXECUTE format('UPDATE %I SET deleted_at = CURRENT_TIMESTAMP WHERE id = $1', table_name)
    USING record_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Posts with author information
CREATE OR REPLACE VIEW posts_with_authors AS
SELECT
    p.id,
    p.uuid,
    p.title,
    p.slug,
    p.content,
    p.status,
    p.published_at,
    p.view_count,
    p.created_at,
    p.updated_at,
    u.id AS author_id,
    u.email AS author_email,
    u.full_name AS author_name,
    up.avatar_url AS author_avatar
FROM posts p
INNER JOIN users u ON p.author_id = u.id
LEFT JOIN user_profiles up ON u.id = up.user_id
WHERE p.deleted_at IS NULL;

-- View: Post statistics
CREATE OR REPLACE VIEW post_statistics AS
SELECT
    p.id,
    p.title,
    COUNT(DISTINCT c.id) AS comment_count,
    COUNT(DISTINCT pt.tag_id) AS tag_count,
    p.view_count
FROM posts p
LEFT JOIN comments c ON p.id = c.post_id AND c.deleted_at IS NULL
LEFT JOIN post_tags pt ON p.id = pt.post_id
WHERE p.deleted_at IS NULL
GROUP BY p.id, p.title, p.view_count;

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- Full-text search
/*
SELECT id, title, ts_rank(search_vector, query) AS rank
FROM posts, to_tsquery('english', 'database & postgresql') query
WHERE search_vector @@ query AND deleted_at IS NULL
ORDER BY rank DESC;
*/

-- JSONB queries
/*
-- Get users with specific preference
SELECT * FROM user_profiles
WHERE preferences @> '{"theme": "dark"}'::jsonb;

-- Update JSONB field
UPDATE user_profiles
SET preferences = preferences || '{"notifications": true}'::jsonb
WHERE user_id = 1;
*/

-- Recursive query for comment threads
/*
WITH RECURSIVE comment_tree AS (
    -- Base case: top-level comments
    SELECT id, post_id, author_id, parent_comment_id, content, 1 AS depth
    FROM comments
    WHERE parent_comment_id IS NULL AND post_id = 1 AND deleted_at IS NULL

    UNION ALL

    -- Recursive case: replies
    SELECT c.id, c.post_id, c.author_id, c.parent_comment_id, c.content, ct.depth + 1
    FROM comments c
    INNER JOIN comment_tree ct ON c.parent_comment_id = ct.id
    WHERE c.deleted_at IS NULL
)
SELECT * FROM comment_tree ORDER BY depth, id;
*/

-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Vacuum and analyze
-- VACUUM ANALYZE;

-- Reindex
-- REINDEX DATABASE current_database();

-- Check table sizes
/*
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
*/
```

## Alembic Migration

### versions/001_initial_schema.py

```python
"""Initial schema

Revision ID: 001
Create Date: 2025-01-XX
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None

def upgrade():
    # Load and execute SQL file
    with open('init.sql', 'r') as f:
        sql = f.read()
        op.execute(sql)

def downgrade():
    op.execute('DROP SCHEMA IF EXISTS audit CASCADE')
    op.execute('DROP TABLE IF EXISTS post_tags CASCADE')
    op.execute('DROP TABLE IF EXISTS tags CASCADE')
    op.execute('DROP TABLE IF EXISTS comments CASCADE')
    op.execute('DROP TABLE IF EXISTS posts CASCADE')
    op.execute('DROP TABLE IF EXISTS user_profiles CASCADE')
    op.execute('DROP TABLE IF EXISTS users CASCADE')
```

## Usage Examples

```python
# Set current user for audit logging
await db.execute("SET app.current_user_id = :user_id", {"user_id": 123})

# Full-text search
posts = await db.execute("""
    SELECT id, title, ts_rank(search_vector, query) AS rank
    FROM posts, to_tsquery('english', :search_query) query
    WHERE search_vector @@ query AND deleted_at IS NULL
    ORDER BY rank DESC
    LIMIT 20
""", {"search_query": "postgresql & performance"})

# JSONB operations
await db.execute("""
    UPDATE user_profiles
    SET preferences = preferences || :new_prefs::jsonb
    WHERE user_id = :user_id
""", {"user_id": 123, "new_prefs": '{"theme": "dark"}'})
```

## Related Templates & Skills

- [Database Management](../skills/database-management.md) - Database operations
- [Database Patterns](../patterns/database-patterns.md) - Migration and transaction patterns
- [FastAPI Starter](./fastapi-starter.md) - Backend integration

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
