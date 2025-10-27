---
title: Microservices Patterns
description: Service decomposition, communication patterns, database strategies, and distributed transaction handling
tags: [pattern, microservices, distributed-systems, architecture, saga]
type: pattern
version: "1.0.0"
category: architecture
---

# Microservices Patterns

## Overview

Microservices architecture decomposes applications into small, independent services that communicate over network protocols. This pattern guide covers service decomposition strategies, inter-service communication, database patterns, distributed transactions, and best practices for building scalable microservices.

**When to use these patterns:**
- Building large-scale distributed systems
- Teams working independently on different services
- Need for independent deployment and scaling
- Polyglot technology requirements
- High availability and fault tolerance needs

## Core Patterns

### 1. Service Decomposition

**Strategies:**

#### Decompose by Business Capability
```
E-commerce Application
├── User Service (authentication, profiles)
├── Product Catalog Service (inventory, search)
├── Order Service (order management, fulfillment)
├── Payment Service (transactions, billing)
├── Notification Service (email, SMS, push)
└── Shipping Service (logistics, tracking)
```

#### Decompose by Subdomain (DDD)
```
Domain: E-commerce
├── Core Subdomain: Order Management (competitive advantage)
├── Supporting Subdomain: Inventory Management
└── Generic Subdomain: Payment Processing (third-party)
```

**Implementation:**

```python
# User Service
from fastapi import FastAPI
from sqlalchemy.orm import Session

app = FastAPI(title="User Service", version="1.0.0")

@app.post("/api/v1/users")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user."""
    user = User(**user.dict())
    db.add(user)
    db.commit()

    # Publish event for other services
    await event_bus.publish("user.created", {
        "user_id": user.id,
        "email": user.email,
        "created_at": user.created_at.isoformat()
    })

    return user

@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

```python
# Order Service
from fastapi import FastAPI
import httpx

app = FastAPI(title="Order Service", version="1.0.0")

@app.post("/api/v1/orders")
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Create new order with saga pattern."""
    # Step 1: Validate user exists (call User Service)
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            f"http://user-service/api/v1/users/{order.user_id}"
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid user")

    # Step 2: Create order
    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()

    # Step 3: Publish event for downstream services
    await event_bus.publish("order.created", {
        "order_id": db_order.id,
        "user_id": db_order.user_id,
        "total_amount": db_order.total_amount
    })

    return db_order
```

### 2. Database Per Service Pattern

**Principle:** Each microservice owns its database and no other service accesses it directly

**Architecture:**
```
User Service → PostgreSQL (users DB)
Order Service → PostgreSQL (orders DB)
Product Service → PostgreSQL (products DB)
Inventory Service → MongoDB (inventory DB)
```

**Benefits:**
- Service independence
- Technology flexibility (polyglot persistence)
- Easier scaling
- Fault isolation

**Challenges:**
- No ACID transactions across services
- Data consistency requires eventual consistency
- Complex queries require API composition

**Implementation:**

```python
# Each service has its own database connection
# User Service database config
USER_DATABASE_URL = "postgresql://user:pass@user-db:5432/users"
user_engine = create_engine(USER_DATABASE_URL)

# Order Service database config
ORDER_DATABASE_URL = "postgresql://user:pass@order-db:5432/orders"
order_engine = create_engine(ORDER_DATABASE_URL)

# No cross-database joins - use API calls instead
@app.get("/api/v1/orders/{order_id}/details")
async def get_order_details(order_id: int):
    """Get order with user details (API composition)."""
    # Get order from Order Service database
    order = db.query(Order).filter(Order.id == order_id).first()

    # Get user details from User Service API
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            f"http://user-service/api/v1/users/{order.user_id}"
        )
        user = user_response.json()

    return {
        "order": order,
        "user": user
    }
```

### 3. Saga Pattern (Distributed Transactions)

**Use Case:** Maintain data consistency across services without distributed transactions

#### Choreography-Based Saga

**Pattern:** Services listen for events and react

```python
# Order Service - Initiates saga
@app.post("/api/v1/orders")
async def create_order(order: OrderCreate):
    """Create order and start saga."""
    # Create order
    db_order = Order(status="pending", **order.dict())
    db.add(db_order)
    db.commit()

    # Publish event
    await event_bus.publish("order.created", {
        "order_id": db_order.id,
        "user_id": db_order.user_id,
        "items": order.items,
        "total_amount": db_order.total_amount
    })

    return db_order

# Inventory Service - Reacts to order.created
@event_bus.subscribe("order.created")
async def reserve_inventory(event_data: dict):
    """Reserve inventory for order."""
    try:
        # Reserve items
        for item in event_data["items"]:
            inventory = db.query(Inventory).filter(
                Inventory.product_id == item["product_id"]
            ).first()

            if inventory.quantity < item["quantity"]:
                raise InsufficientInventoryError()

            inventory.quantity -= item["quantity"]

        db.commit()

        # Publish success event
        await event_bus.publish("inventory.reserved", {
            "order_id": event_data["order_id"]
        })

    except InsufficientInventoryError:
        # Publish failure event
        await event_bus.publish("inventory.reservation_failed", {
            "order_id": event_data["order_id"],
            "reason": "insufficient_inventory"
        })

# Payment Service - Reacts to inventory.reserved
@event_bus.subscribe("inventory.reserved")
async def process_payment(event_data: dict):
    """Process payment for order."""
    try:
        # Process payment
        payment = await payment_gateway.charge(
            order_id=event_data["order_id"],
            amount=event_data["total_amount"]
        )

        await event_bus.publish("payment.completed", {
            "order_id": event_data["order_id"],
            "payment_id": payment.id
        })

    except PaymentError as e:
        # Publish failure - trigger compensating transactions
        await event_bus.publish("payment.failed", {
            "order_id": event_data["order_id"],
            "reason": str(e)
        })

# Order Service - Listen for completion or failure
@event_bus.subscribe("payment.completed")
async def complete_order(event_data: dict):
    """Mark order as completed."""
    order = db.query(Order).filter(Order.id == event_data["order_id"]).first()
    order.status = "completed"
    db.commit()

@event_bus.subscribe("payment.failed")
async def cancel_order(event_data: dict):
    """Cancel order and trigger compensating transactions."""
    order = db.query(Order).filter(Order.id == event_data["order_id"]).first()
    order.status = "cancelled"
    db.commit()

    # Trigger inventory compensation
    await event_bus.publish("order.cancelled", {
        "order_id": event_data["order_id"]
    })

# Inventory Service - Compensating transaction
@event_bus.subscribe("order.cancelled")
async def release_inventory(event_data: dict):
    """Release reserved inventory (compensation)."""
    order = await get_order_items(event_data["order_id"])

    for item in order.items:
        inventory = db.query(Inventory).filter(
            Inventory.product_id == item["product_id"]
        ).first()
        inventory.quantity += item["quantity"]

    db.commit()
```

#### Orchestration-Based Saga

**Pattern:** Central orchestrator coordinates saga

```python
from enum import Enum
from typing import List, Dict

class SagaStep(Enum):
    CREATE_ORDER = "create_order"
    RESERVE_INVENTORY = "reserve_inventory"
    PROCESS_PAYMENT = "process_payment"
    SEND_NOTIFICATION = "send_notification"
    COMPLETE_ORDER = "complete_order"

class OrderSagaOrchestrator:
    """Orchestrate order creation saga."""

    def __init__(self):
        self.steps = [
            SagaStep.CREATE_ORDER,
            SagaStep.RESERVE_INVENTORY,
            SagaStep.PROCESS_PAYMENT,
            SagaStep.SEND_NOTIFICATION,
            SagaStep.COMPLETE_ORDER
        ]

    async def execute(self, order_data: dict) -> dict:
        """Execute saga steps sequentially."""
        saga_state = {
            "order_id": None,
            "completed_steps": [],
            "status": "in_progress"
        }

        try:
            for step in self.steps:
                result = await self._execute_step(step, order_data, saga_state)
                saga_state["completed_steps"].append(step)

                if step == SagaStep.CREATE_ORDER:
                    saga_state["order_id"] = result["order_id"]

            saga_state["status"] = "completed"
            return saga_state

        except Exception as e:
            # Execute compensating transactions in reverse order
            saga_state["status"] = "failed"
            saga_state["error"] = str(e)
            await self._compensate(saga_state)
            raise

    async def _execute_step(self, step: SagaStep, order_data: dict, state: dict):
        """Execute individual saga step."""
        if step == SagaStep.CREATE_ORDER:
            return await self._create_order(order_data)
        elif step == SagaStep.RESERVE_INVENTORY:
            return await self._reserve_inventory(state["order_id"], order_data["items"])
        elif step == SagaStep.PROCESS_PAYMENT:
            return await self._process_payment(state["order_id"], order_data["total"])
        elif step == SagaStep.SEND_NOTIFICATION:
            return await self._send_notification(state["order_id"])
        elif step == SagaStep.COMPLETE_ORDER:
            return await self._complete_order(state["order_id"])

    async def _compensate(self, state: dict):
        """Execute compensating transactions."""
        for step in reversed(state["completed_steps"]):
            try:
                if step == SagaStep.RESERVE_INVENTORY:
                    await self._release_inventory(state["order_id"])
                elif step == SagaStep.PROCESS_PAYMENT:
                    await self._refund_payment(state["order_id"])
                elif step == SagaStep.CREATE_ORDER:
                    await self._cancel_order(state["order_id"])
            except Exception as e:
                logger.error(f"Compensation failed for {step}: {e}")

    async def _create_order(self, order_data: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://order-service/api/v1/orders",
                json=order_data
            )
            return response.json()

    async def _reserve_inventory(self, order_id: int, items: List[dict]):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://inventory-service/api/v1/reservations",
                json={"order_id": order_id, "items": items}
            )
            return response.json()

    async def _process_payment(self, order_id: int, amount: float):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://payment-service/api/v1/charges",
                json={"order_id": order_id, "amount": amount}
            )
            return response.json()

# Usage
orchestrator = OrderSagaOrchestrator()

@app.post("/api/v1/orders/saga")
async def create_order_with_saga(order: OrderCreate):
    """Create order using saga orchestrator."""
    result = await orchestrator.execute(order.dict())
    return result
```

### 4. Inter-Service Communication

#### Synchronous Communication (REST)

```python
# Service-to-service communication with retry and timeout
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_user_service(user_id: int) -> dict:
    """Call user service with retry logic."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"http://user-service/api/v1/users/{user_id}"
        )
        response.raise_for_status()
        return response.json()
```

#### Asynchronous Communication (Message Queue)

```python
# RabbitMQ producer
import aio_pika

async def publish_event(event_type: str, data: dict):
    """Publish event to message queue."""
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")

    async with connection:
        channel = await connection.channel()

        # Declare exchange
        exchange = await channel.declare_exchange(
            "events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        # Publish message
        message = aio_pika.Message(
            body=json.dumps(data).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await exchange.publish(
            message,
            routing_key=event_type
        )

# RabbitMQ consumer
async def consume_events():
    """Consume events from message queue."""
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        # Declare queue
        queue = await channel.declare_queue("order-service-queue", durable=True)

        # Bind to exchange
        exchange = await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC)
        await queue.bind(exchange, routing_key="order.*")

        # Consume messages
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    event_data = json.loads(message.body.decode())
                    await handle_event(message.routing_key, event_data)
```

## Best Practices

### Service Design Principles

**Do:**
- ✅ Design services around business capabilities
- ✅ Keep services loosely coupled
- ✅ Use asynchronous messaging for non-critical operations
- ✅ Implement circuit breakers for all external calls
- ✅ Use API versioning from the start
- ✅ Implement comprehensive logging and tracing
- ✅ Design for failure (assume services will fail)
- ✅ Use correlation IDs to track requests across services

**Don't:**
- ❌ Share databases between services
- ❌ Create too many microservices (nano-services)
- ❌ Use distributed transactions (use sagas instead)
- ❌ Make synchronous calls in a chain (A → B → C)
- ❌ Deploy all services together

### Data Consistency

- Use eventual consistency for non-critical operations
- Implement saga pattern for distributed transactions
- Use event sourcing for audit trails
- Implement idempotency for all operations
- Version your events and messages

### Testing Strategy

```python
# Contract testing with Pact
from pact import Consumer, Provider

# Consumer test (Order Service)
pact = Consumer("OrderService").has_pact_with(Provider("UserService"))

pact.given("user 123 exists").upon_receiving(
    "a request for user 123"
).with_request(
    method="GET",
    path="/api/v1/users/123"
).will_respond_with(200, body={
    "id": 123,
    "email": "user@example.com"
})

# Integration testing
async def test_order_creation_saga():
    """Test complete order creation saga."""
    # Create order
    order_response = await client.post("/api/v1/orders/saga", json={
        "user_id": 123,
        "items": [{"product_id": 1, "quantity": 2}],
        "total_amount": 100.0
    })

    assert order_response.status_code == 200
    order = order_response.json()

    # Verify saga completion
    await asyncio.sleep(2)  # Wait for async saga completion

    # Check order status
    order_status = await client.get(f"/api/v1/orders/{order['order_id']}")
    assert order_status.json()["status"] == "completed"
```

## Related Patterns & Skills

- [API Gateway Pattern](./api-gateway-pattern.md) - Single entry point
- [Event-Driven Architecture](./event-driven-architecture.md) - Event patterns
- [Database Patterns](./database-patterns.md) - Data management
- [Deployment Operations](../skills/deployment-operations.md) - Service deployment

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
