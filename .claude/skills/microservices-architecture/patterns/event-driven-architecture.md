---
title: Event-Driven Architecture
description: Event sourcing, CQRS, pub/sub messaging, and event-driven microservices patterns
tags: [pattern, event-driven, event-sourcing, cqrs, messaging, pub-sub]
type: pattern
version: "1.0.0"
category: architecture
---

# Event-Driven Architecture

## Overview

Event-Driven Architecture (EDA) is an architectural pattern where services communicate through events rather than direct calls. This pattern guide covers event sourcing, CQRS, pub/sub messaging, event schemas, and best practices for building scalable, loosely-coupled event-driven systems.

**When to use these patterns:**
- Building microservices that need to stay loosely coupled
- Implementing audit trails and historical data tracking
- Handling high-throughput asynchronous workflows
- Building reactive systems
- Implementing complex business processes across services
- Need for eventual consistency

## Core Patterns

### 1. Event Sourcing

**Use Case:** Store state changes as sequence of events, enabling full audit trail and time travel

**Concept:**
- Instead of storing current state, store all state changes as events
- Reconstruct current state by replaying events
- Events are immutable and append-only

**Architecture:**
```
Command → Aggregate → Event → Event Store
                              ↓
                        Event Replay → Current State
```

**Implementation:**

```python
# Event definitions
from pydantic import BaseModel
from datetime import datetime
from typing import Literal
from uuid import uuid4

class Event(BaseModel):
    """Base event class."""
    event_id: str
    aggregate_id: str
    event_type: str
    timestamp: datetime
    version: int
    data: dict

class OrderCreatedEvent(BaseModel):
    """Order created event."""
    event_type: Literal["order.created"] = "order.created"
    order_id: str
    user_id: int
    items: list
    total_amount: float
    timestamp: datetime = datetime.utcnow()

class OrderPaidEvent(BaseModel):
    """Order paid event."""
    event_type: Literal["order.paid"] = "order.paid"
    order_id: str
    payment_id: str
    amount: float
    timestamp: datetime = datetime.utcnow()

class OrderShippedEvent(BaseModel):
    """Order shipped event."""
    event_type: Literal["order.shipped"] = "order.shipped"
    order_id: str
    tracking_number: str
    carrier: str
    timestamp: datetime = datetime.utcnow()

# Event store
class EventStore:
    """Event store for persisting events."""

    def __init__(self, db):
        self.db = db

    async def append(self, event: Event):
        """Append event to store."""
        await self.db.events.insert_one({
            "event_id": event.event_id,
            "aggregate_id": event.aggregate_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "version": event.version,
            "data": event.data
        })

    async def get_events(self, aggregate_id: str) -> list[Event]:
        """Get all events for an aggregate."""
        cursor = self.db.events.find(
            {"aggregate_id": aggregate_id}
        ).sort("version", 1)

        events = []
        async for doc in cursor:
            events.append(Event(**doc))

        return events

# Order aggregate
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Order:
    """Order aggregate reconstructed from events."""

    def __init__(self, order_id: str):
        self.order_id = order_id
        self.user_id: int = None
        self.items: list = []
        self.total_amount: float = 0
        self.status: OrderStatus = OrderStatus.PENDING
        self.payment_id: str = None
        self.tracking_number: str = None
        self.version: int = 0

    def apply_event(self, event: Event):
        """Apply event to aggregate state."""
        if event.event_type == "order.created":
            self._apply_order_created(event.data)
        elif event.event_type == "order.paid":
            self._apply_order_paid(event.data)
        elif event.event_type == "order.shipped":
            self._apply_order_shipped(event.data)

        self.version = event.version

    def _apply_order_created(self, data: dict):
        self.user_id = data["user_id"]
        self.items = data["items"]
        self.total_amount = data["total_amount"]
        self.status = OrderStatus.PENDING

    def _apply_order_paid(self, data: dict):
        self.payment_id = data["payment_id"]
        self.status = OrderStatus.PAID

    def _apply_order_shipped(self, data: dict):
        self.tracking_number = data["tracking_number"]
        self.status = OrderStatus.SHIPPED

# Repository with event sourcing
class OrderRepository:
    """Repository for order aggregate."""

    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    async def get_by_id(self, order_id: str) -> Order:
        """Reconstruct order from events."""
        events = await self.event_store.get_events(order_id)

        order = Order(order_id)
        for event in events:
            order.apply_event(event)

        return order

    async def save(self, order: Order, events: list[Event]):
        """Save new events for order."""
        for event in events:
            await self.event_store.append(event)

# Command handlers
@app.post("/orders")
async def create_order(order_data: OrderCreate):
    """Create order (event sourcing)."""
    order_id = str(uuid4())

    # Create event
    event = Event(
        event_id=str(uuid4()),
        aggregate_id=order_id,
        event_type="order.created",
        timestamp=datetime.utcnow(),
        version=1,
        data={
            "order_id": order_id,
            "user_id": order_data.user_id,
            "items": order_data.items,
            "total_amount": order_data.total_amount
        }
    )

    # Save event
    await event_store.append(event)

    # Publish event to message bus
    await event_bus.publish("order.created", event.data)

    return {"order_id": order_id}

# Query: Get order state
@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order by replaying events."""
    order = await order_repository.get_by_id(order_id)
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "items": order.items,
        "total_amount": order.total_amount,
        "status": order.status,
        "version": order.version
    }
```

### 2. CQRS (Command Query Responsibility Segregation)

**Use Case:** Separate read and write models for scalability and flexibility

**Architecture:**
```
Commands → Write Model → Events → Event Store
                                    ↓
                            Event Handlers
                                    ↓
                            Read Model (Projections)
                                    ↓
Queries ───────────────────────────┘
```

**Implementation:**

```python
# Write model (commands)
from fastapi import FastAPI, Depends
from pydantic import BaseModel

class CreateOrderCommand(BaseModel):
    """Command to create order."""
    user_id: int
    items: list
    total_amount: float

class PayOrderCommand(BaseModel):
    """Command to pay for order."""
    order_id: str
    payment_id: str
    amount: float

# Command handlers (write side)
@app.post("/commands/orders/create")
async def handle_create_order(command: CreateOrderCommand):
    """Handle create order command."""
    order_id = str(uuid4())

    # Validate command
    if command.total_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Create event
    event = OrderCreatedEvent(
        order_id=order_id,
        user_id=command.user_id,
        items=command.items,
        total_amount=command.total_amount
    )

    # Save to event store
    await event_store.append(Event(
        event_id=str(uuid4()),
        aggregate_id=order_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        version=1,
        data=event.dict()
    ))

    # Publish event
    await event_bus.publish("order.created", event.dict())

    return {"order_id": order_id}

# Read model (projections)
class OrderReadModel(BaseModel):
    """Read-optimized order model."""
    order_id: str
    user_id: int
    user_email: str  # Denormalized
    user_name: str   # Denormalized
    items: list
    total_amount: float
    status: str
    created_at: datetime
    updated_at: datetime

# Event handlers update read model
@event_bus.subscribe("order.created")
async def update_order_projection(event_data: dict):
    """Update read model when order is created."""
    # Get user details (denormalize)
    user = await get_user(event_data["user_id"])

    # Create read model record
    await db.order_projections.insert_one({
        "order_id": event_data["order_id"],
        "user_id": event_data["user_id"],
        "user_email": user.email,
        "user_name": user.name,
        "items": event_data["items"],
        "total_amount": event_data["total_amount"],
        "status": "pending",
        "created_at": event_data["timestamp"],
        "updated_at": event_data["timestamp"]
    })

@event_bus.subscribe("order.paid")
async def update_order_paid_projection(event_data: dict):
    """Update read model when order is paid."""
    await db.order_projections.update_one(
        {"order_id": event_data["order_id"]},
        {
            "$set": {
                "status": "paid",
                "payment_id": event_data["payment_id"],
                "updated_at": datetime.utcnow()
            }
        }
    )

# Query handlers (read side)
@app.get("/queries/orders")
async def query_orders(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20
):
    """Query orders from read model."""
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if status:
        filters["status"] = status

    cursor = db.order_projections.find(filters).limit(limit)
    orders = await cursor.to_list(length=limit)

    return orders

@app.get("/queries/orders/{order_id}")
async def query_order(order_id: str):
    """Get single order from read model."""
    order = await db.order_projections.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order
```

### 3. Pub/Sub Messaging with RabbitMQ

**Use Case:** Asynchronous communication between services

```python
# Event bus implementation with RabbitMQ
import aio_pika
import asyncio
from typing import Callable, Dict

class EventBus:
    """Event bus for pub/sub messaging."""

    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.connection = None
        self.channel = None
        self.subscribers: Dict[str, list[Callable]] = {}

    async def connect(self):
        """Connect to RabbitMQ."""
        self.connection = await aio_pika.connect_robust(self.amqp_url)
        self.channel = await self.connection.channel()

        # Declare exchange
        self.exchange = await self.channel.declare_exchange(
            "events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

    async def publish(self, event_type: str, data: dict):
        """Publish event."""
        message = aio_pika.Message(
            body=json.dumps({
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await self.exchange.publish(
            message,
            routing_key=event_type
        )

        logger.info("event_published", event_type=event_type)

    def subscribe(self, event_type: str):
        """Decorator to subscribe to events."""
        def decorator(func: Callable):
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(func)
            return func
        return decorator

    async def start_consuming(self, service_name: str):
        """Start consuming events."""
        # Declare service-specific queue
        queue = await self.channel.declare_queue(
            f"{service_name}-queue",
            durable=True
        )

        # Bind to event types
        for event_type in self.subscribers.keys():
            await queue.bind(self.exchange, routing_key=event_type)

        # Consume messages
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        event = json.loads(message.body.decode())
                        event_type = event["event_type"]

                        # Call all subscribers for this event type
                        for handler in self.subscribers.get(event_type, []):
                            await handler(event["data"])

                    except Exception as e:
                        logger.error(
                            "event_processing_failed",
                            error=str(e),
                            event_type=event.get("event_type")
                        )

# Usage
event_bus = EventBus("amqp://guest:guest@rabbitmq/")

@event_bus.subscribe("order.created")
async def send_order_confirmation_email(event_data: dict):
    """Send email when order is created."""
    user = await get_user(event_data["user_id"])
    await email_service.send(
        to=user.email,
        subject="Order Confirmation",
        body=f"Your order {event_data['order_id']} has been received."
    )

@event_bus.subscribe("order.created")
async def update_inventory(event_data: dict):
    """Update inventory when order is created."""
    for item in event_data["items"]:
        await inventory_service.reserve(
            product_id=item["product_id"],
            quantity=item["quantity"]
        )

# Start event bus
@app.on_event("startup")
async def startup():
    await event_bus.connect()
    asyncio.create_task(event_bus.start_consuming("order-service"))
```

### 4. Event Schema and Versioning

```python
# Event schema versioning
from typing import Union

class OrderCreatedEventV1(BaseModel):
    """Order created event version 1."""
    event_type: Literal["order.created"] = "order.created"
    version: Literal[1] = 1
    order_id: str
    user_id: int
    items: list
    total_amount: float

class OrderCreatedEventV2(BaseModel):
    """Order created event version 2 (added discount field)."""
    event_type: Literal["order.created"] = "order.created"
    version: Literal[2] = 2
    order_id: str
    user_id: int
    items: list
    total_amount: float
    discount_amount: float = 0  # New field

# Event upcasting (convert old events to new format)
def upcast_event(event: dict) -> Union[OrderCreatedEventV1, OrderCreatedEventV2]:
    """Convert old event versions to new format."""
    if event["version"] == 1:
        # Add default discount for v1 events
        return OrderCreatedEventV2(
            **event,
            discount_amount=0,
            version=2
        )
    return OrderCreatedEventV2(**event)

# Event handlers support multiple versions
@event_bus.subscribe("order.created")
async def handle_order_created(event_data: dict):
    """Handle order created event (any version)."""
    # Upcast to latest version
    event = upcast_event(event_data)

    # Process using latest schema
    await process_order(event)
```

## Best Practices

### Event Design Principles

**Do:**
- ✅ Events are immutable (past tense: "OrderCreated", not "CreateOrder")
- ✅ Events are facts that happened (cannot be rejected)
- ✅ Include all necessary data in event (avoid lookups)
- ✅ Use event versioning from the start
- ✅ Keep events small and focused
- ✅ Include metadata (timestamp, correlation ID, causation ID)
- ✅ Use unique event IDs for idempotency

**Don't:**
- ❌ Include sensitive data in events (encrypt if necessary)
- ❌ Delete or modify events (append-only)
- ❌ Make events too coarse-grained
- ❌ Couple event schema to internal implementation

### Event Naming Conventions

```python
# Good event names (past tense, domain language)
"order.created"
"payment.processed"
"user.registered"
"inventory.reserved"
"shipment.dispatched"

# Bad event names
"create_order"          # Command, not event
"OrderCreatedEvent"     # Include "Event" in code, not name
"order_create"          # Not past tense
```

### Handling Eventual Consistency

```python
# Eventual consistency example
@app.post("/orders")
async def create_order(order_data: OrderCreate):
    """Create order with eventual consistency."""
    order_id = str(uuid4())

    # Publish event (async)
    await event_bus.publish("order.created", {
        "order_id": order_id,
        "user_id": order_data.user_id,
        "items": order_data.items
    })

    # Return immediately (read model will be updated async)
    return {
        "order_id": order_id,
        "status": "processing",
        "message": "Order is being processed"
    }

# Client should poll or use WebSocket for updates
@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str):
    """Get order processing status."""
    order = await db.order_projections.find_one({"order_id": order_id})

    return {
        "order_id": order_id,
        "status": order["status"] if order else "processing"
    }
```

### Error Handling and Replay

```python
# Event replay for rebuilding projections
async def rebuild_projection(projection_name: str):
    """Rebuild projection from event store."""
    # Clear existing projection
    await db[projection_name].delete_many({})

    # Replay all events
    cursor = db.events.find({}).sort("timestamp", 1)

    async for event in cursor:
        # Apply event to projection
        await apply_event_to_projection(event, projection_name)

    logger.info("projection_rebuilt", projection=projection_name)
```

## Related Patterns & Skills

- [Microservices Patterns](./microservices-patterns.md) - Service communication
- [Error Handling Patterns](./error-handling-patterns.md) - Event processing errors
- [Database Patterns](./database-patterns.md) - Event store implementation

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
