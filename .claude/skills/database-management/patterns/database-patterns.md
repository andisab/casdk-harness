---
title: Database Patterns
description: Migration strategies, transaction management, connection pooling, sharding, and data architecture patterns
tags: [pattern, database, migrations, transactions, sharding, postgres]
type: pattern
version: "1.0.0"
category: data
---

# Database Patterns

## Overview

This pattern guide covers database architecture patterns including zero-downtime migrations, transaction management, connection pooling, sharding strategies, read replicas, and data retention policies. Use these patterns to build scalable, reliable, and maintainable data layers.

**When to use these patterns:**
- Managing database schema changes in production
- Handling high transaction volumes
- Scaling read-heavy applications
- Implementing data archival strategies
- Building multi-tenant applications
- Ensuring data consistency

## Patterns

### 1. Zero-Downtime Migrations

**Use Case:** Deploy database schema changes without service interruption

**Strategy: Expand-Contract Pattern**

**Phase 1 - Expand:**
```sql
-- Step 1: Add new column (nullable, with default)
ALTER TABLE users ADD COLUMN full_name VARCHAR(255) DEFAULT '';

-- Step 2: Backfill data (in batches)
UPDATE users
SET full_name = CONCAT(first_name, ' ', last_name)
WHERE full_name = ''
LIMIT 1000;

-- Step 3: Application code supports both old and new columns
-- (Deploy application version that writes to both columns)
```

**Phase 2 - Contract:**
```sql
-- Step 4: Make new column NOT NULL (after backfill complete)
ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;

-- Step 5: Remove old columns (after verifying new column works)
ALTER TABLE users DROP COLUMN first_name;
ALTER TABLE users DROP COLUMN last_name;
```

**Implementation:**

```python
# Alembic migration for zero-downtime schema change
"""Add full_name column

Revision ID: abc123
Revises: xyz789
Create Date: 2025-01-XX
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    """Expand phase."""
    # Add new column (nullable first)
    op.add_column(
        'users',
        sa.Column('full_name', sa.String(255), nullable=True, server_default='')
    )

    # Create index for new column
    op.create_index('ix_users_full_name', 'users', ['full_name'])

def downgrade():
    """Rollback expand phase."""
    op.drop_index('ix_users_full_name', table_name='users')
    op.drop_column('users', 'full_name')

# Backfill script (run separately)
async def backfill_full_name():
    """Backfill full_name column in batches."""
    batch_size = 1000
    offset = 0

    while True:
        # Process batch
        result = await db.execute(
            """
            UPDATE users
            SET full_name = CONCAT(first_name, ' ', last_name)
            WHERE full_name = ''
            AND id > :offset
            ORDER BY id
            LIMIT :batch_size
            RETURNING id
            """,
            {"offset": offset, "batch_size": batch_size}
        )

        rows = result.fetchall()
        if not rows:
            break

        offset = rows[-1][0]
        logger.info("backfill_progress", processed=len(rows), offset=offset)

        # Small delay to avoid overwhelming database
        await asyncio.sleep(0.1)

    logger.info("backfill_complete")
```

### 2. Transaction Management

**Use Case:** Ensure data consistency across multiple operations

**Implementation:**

```python
# SQLAlchemy transaction patterns
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

@asynccontextmanager
async def transaction(db: Session):
    """Context manager for transactions."""
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise

# Usage: Simple transaction
async def create_user_with_profile(user_data: dict):
    """Create user and profile in single transaction."""
    async with transaction(db):
        # Create user
        user = User(**user_data)
        db.add(user)
        await db.flush()  # Get user.id

        # Create profile
        profile = Profile(user_id=user.id, bio="")
        db.add(profile)

        # Both committed together
        return user

# Nested transactions with savepoints
async def create_order_with_items(order_data: dict):
    """Create order with multiple items using savepoints."""
    async with transaction(db) as tx:
        # Create order
        order = Order(user_id=order_data["user_id"], total=0)
        db.add(order)
        await db.flush()

        total = 0
        for item_data in order_data["items"]:
            try:
                # Savepoint for each item
                async with db.begin_nested():
                    # Validate product exists
                    product = await db.get(Product, item_data["product_id"])
                    if not product:
                        raise ValueError(f"Product {item_data['product_id']} not found")

                    # Create order item
                    item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=item_data["quantity"],
                        price=product.price
                    )
                    db.add(item)
                    total += product.price * item_data["quantity"]

            except ValueError as e:
                logger.warning("skip_invalid_item", error=str(e))
                continue  # Skip invalid item, rollback to savepoint

        # Update order total
        order.total = total
        return order

# Optimistic locking with version column
class Document(Base):
    """Document with optimistic locking."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    content = Column(Text)
    version = Column(Integer, default=1, nullable=False)

async def update_document_optimistic(doc_id: int, new_content: str, expected_version: int):
    """Update document with optimistic locking."""
    result = await db.execute(
        """
        UPDATE documents
        SET content = :content, version = version + 1
        WHERE id = :id AND version = :expected_version
        RETURNING id
        """,
        {"id": doc_id, "content": new_content, "expected_version": expected_version}
    )

    if not result.rowcount:
        raise HTTPException(
            status_code=409,
            detail="Document was modified by another user"
        )

# Pessimistic locking with SELECT FOR UPDATE
async def reserve_inventory_pessimistic(product_id: int, quantity: int):
    """Reserve inventory with pessimistic locking."""
    async with transaction(db):
        # Lock row for update
        inventory = await db.execute(
            """
            SELECT * FROM inventory
            WHERE product_id = :product_id
            FOR UPDATE
            """,
            {"product_id": product_id}
        ).first()

        if inventory.quantity < quantity:
            raise HTTPException(status_code=400, detail="Insufficient inventory")

        # Update quantity
        inventory.quantity -= quantity
        await db.commit()

        return inventory
```

### 3. Connection Pooling

**Use Case:** Reuse database connections for better performance

```python
# SQLAlchemy connection pool configuration
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Production configuration
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    # Pool configuration
    pool_size=20,              # Number of connections to maintain
    max_overflow=10,           # Additional connections if pool exhausted
    pool_timeout=30,           # Seconds to wait for connection
    pool_recycle=3600,         # Recycle connections after 1 hour
    pool_pre_ping=True,        # Verify connections before using
    # Connection arguments
    connect_args={
        "application_name": "order-service",
        "options": "-c statement_timeout=5000"  # 5-second query timeout
    }
)

# Monitor pool status
def get_pool_status():
    """Get connection pool statistics."""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_connections": pool.size() + pool.overflow()
    }

# Connection pool events for monitoring
from sqlalchemy import event

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new connections."""
    logger.info("database_connection_created")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Monitor connection checkouts."""
    logger.debug("connection_checked_out")
```

### 4. Database Sharding

**Use Case:** Horizontally scale database across multiple servers

**Sharding Strategies:**

#### Horizontal Sharding by User ID
```python
# Shard key: user_id
def get_shard(user_id: int, num_shards: int = 4) -> int:
    """Determine shard for user."""
    return user_id % num_shards

# Shard configuration
SHARDS = {
    0: "postgresql://user:pass@shard0.db:5432/users",
    1: "postgresql://user:pass@shard1.db:5432/users",
    2: "postgresql://user:pass@shard2.db:5432/users",
    3: "postgresql://user:pass@shard3.db:5432/users"
}

# Create engines for each shard
shard_engines = {
    shard_id: create_engine(url)
    for shard_id, url in SHARDS.items()
}

def get_db_for_user(user_id: int):
    """Get database session for user's shard."""
    shard_id = get_shard(user_id, len(SHARDS))
    engine = shard_engines[shard_id]
    return Session(engine)

# Usage
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user from appropriate shard."""
    db = get_db_for_user(user_id)
    user = db.query(User).filter(User.id == user_id).first()
    return user

# Cross-shard queries (scatter-gather)
async def search_users_across_shards(email: str):
    """Search users across all shards."""
    tasks = []

    for shard_id, engine in shard_engines.items():
        async def query_shard(engine):
            db = Session(engine)
            return db.query(User).filter(User.email == email).first()

        tasks.append(query_shard(engine))

    # Execute queries in parallel
    results = await asyncio.gather(*tasks)

    # Filter out None results
    users = [user for user in results if user is not None]
    return users
```

#### Range-Based Sharding
```python
# Shard by date ranges (time-series data)
SHARD_RANGES = {
    "shard_2024_q1": (datetime(2024, 1, 1), datetime(2024, 4, 1)),
    "shard_2024_q2": (datetime(2024, 4, 1), datetime(2024, 7, 1)),
    "shard_2024_q3": (datetime(2024, 7, 1), datetime(2024, 10, 1)),
    "shard_2024_q4": (datetime(2024, 10, 1), datetime(2025, 1, 1))
}

def get_shard_for_date(date: datetime) -> str:
    """Get shard for given date."""
    for shard_name, (start, end) in SHARD_RANGES.items():
        if start <= date < end:
            return shard_name

    raise ValueError(f"No shard found for date {date}")
```

### 5. Read Replicas

**Use Case:** Scale read operations using database replicas

```python
# Master-replica configuration
from sqlalchemy.orm import sessionmaker

# Master database (read/write)
master_engine = create_engine(
    "postgresql://user:pass@master.db:5432/app",
    pool_size=10
)

# Read replicas (read-only)
replica_engines = [
    create_engine(f"postgresql://user:pass@replica{i}.db:5432/app", pool_size=20)
    for i in range(1, 4)  # 3 replicas
]

# Session factories
MasterSession = sessionmaker(bind=master_engine)
ReplicaSession = sessionmaker(bind=replica_engines[0])

# Routing decorator
def use_replica_for_reads(func):
    """Route read queries to replicas."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Use replica for GET requests
        if request.method == "GET":
            # Round-robin load balancing
            replica_idx = hash(request.url.path) % len(replica_engines)
            db = Session(replica_engines[replica_idx])
        else:
            # Use master for writes
            db = MasterSession()

        return await func(db=db, *args, **kwargs)

    return wrapper

@app.get("/users")
@use_replica_for_reads
async def list_users(db: Session):
    """List users from read replica."""
    users = db.query(User).limit(100).all()
    return users

@app.post("/users")
async def create_user(user: UserCreate):
    """Create user on master database."""
    db = MasterSession()
    user = User(**user.dict())
    db.add(user)
    db.commit()
    return user
```

### 6. Data Archival and Retention

**Use Case:** Manage data lifecycle and comply with retention policies

```python
# Archival strategy
async def archive_old_orders():
    """Archive orders older than 2 years."""
    cutoff_date = datetime.utcnow() - timedelta(days=730)

    # Move to archive table
    await db.execute(
        """
        INSERT INTO orders_archive
        SELECT * FROM orders
        WHERE created_at < :cutoff_date
        """,
        {"cutoff_date": cutoff_date}
    )

    # Delete from main table
    result = await db.execute(
        """
        DELETE FROM orders
        WHERE created_at < :cutoff_date
        """,
        {"cutoff_date": cutoff_date}
    )

    logger.info("orders_archived", count=result.rowcount)

# Partitioning by date (PostgreSQL)
async def create_monthly_partition():
    """Create partition for current month."""
    now = datetime.utcnow()
    partition_name = f"orders_{now.year}_{now.month:02d}"

    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF orders
        FOR VALUES FROM ('{now.year}-{now.month:02d}-01')
        TO ('{now.year}-{now.month+1:02d}-01')
        """
    )

# Soft delete pattern
class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    deleted_at = Column(DateTime, nullable=True)

    @hybrid_property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        """Mark record as deleted."""
        self.deleted_at = datetime.utcnow()

# Query filter for soft deletes
@event.listens_for(Session, "do_orm_execute")
def _add_filtering_criteria(execute_state):
    """Automatically filter soft-deleted records."""
    if execute_state.is_select:
        for entity in execute_state.entities:
            if hasattr(entity, "deleted_at"):
                execute_state.statement = execute_state.statement.filter(
                    entity.deleted_at.is_(None)
                )
```

## Best Practices

### Migration Strategy

**Do:**
- ✅ Use version control for migrations (Alembic, Flyway)
- ✅ Test migrations on production-like data
- ✅ Make migrations backward compatible
- ✅ Run migrations in batches for large tables
- ✅ Have rollback plan for every migration
- ✅ Monitor migration progress

**Don't:**
- ❌ Drop columns immediately (use expand-contract)
- ❌ Run long-running migrations during peak hours
- ❌ Modify migrations after they've been deployed
- ❌ Skip migration testing

### Transaction Guidelines

- Use transactions for all write operations
- Keep transactions short and focused
- Avoid external API calls within transactions
- Use appropriate isolation levels
- Implement retry logic for deadlocks
- Monitor transaction duration

### Connection Pool Sizing

```python
# Formula: pool_size = (max_connections * 0.7) / num_instances
# Example: 100 max connections, 5 app instances
# pool_size = (100 * 0.7) / 5 = 14 connections per instance

# Leave headroom for:
# - Manual admin connections
# - Background jobs
# - Database maintenance
```

## Related Patterns & Skills

- [Database Management](../skills/database-management.md) - Database operations
- [Microservices Patterns](./microservices-patterns.md) - Database per service
- [Event-Driven Architecture](./event-driven-architecture.md) - Event sourcing
- [Performance Optimization](../skills/performance-optimization.md) - Query optimization

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
