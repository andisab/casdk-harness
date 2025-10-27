---
title: API Development
description: REST and GraphQL API design, development, versioning, and documentation best practices
tags: [skill, api, rest, graphql, design, development]
type: skill
version: "1.0.0"
category: backend-development
---

# API Development

## Overview

This skill provides comprehensive API development capabilities for designing, implementing, and documenting RESTful and GraphQL APIs. Use this skill for API design decisions, implementation patterns, versioning strategies, and API documentation.

**When to use this skill:**
- Designing new API endpoints
- Implementing REST or GraphQL APIs
- API versioning and backward compatibility
- Request/response schema design
- API documentation and client generation

## Key Concepts

### REST API Design Principles

**Resource-Oriented Design:**
- Resources are nouns (users, posts, comments)
- URLs represent resource hierarchies
- HTTP methods represent actions (GET, POST, PUT, PATCH, DELETE)

**URL Structure:**
```
GET    /api/v1/users              # List users
GET    /api/v1/users/{id}         # Get user by ID
POST   /api/v1/users              # Create user
PUT    /api/v1/users/{id}         # Replace user (full update)
PATCH  /api/v1/users/{id}         # Update user (partial)
DELETE /api/v1/users/{id}         # Delete user

# Nested resources
GET    /api/v1/users/{id}/posts   # Get user's posts
POST   /api/v1/users/{id}/posts   # Create post for user
```

**HTTP Status Codes:**
- `200 OK` - Successful GET, PUT, PATCH
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource conflict (e.g., duplicate)
- `422 Unprocessable Entity` - Semantic validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### GraphQL Design Principles

**Schema-First Design:**
```graphql
type User {
  id: ID!
  email: String!
  name: String!
  posts: [Post!]!
  createdAt: DateTime!
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
  publishedAt: DateTime
}

type Query {
  user(id: ID!): User
  users(limit: Int, offset: Int): [User!]!
  post(id: ID!): Post
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
  deleteUser(id: ID!): Boolean!
}

input CreateUserInput {
  email: String!
  name: String!
  password: String!
}
```

**Query Optimization:**
- Use DataLoader to prevent N+1 queries
- Implement pagination (cursor or offset-based)
- Add query depth limits to prevent abuse
- Implement field-level authorization

## Implementation

### REST API Implementation (FastAPI)

#### Basic CRUD Endpoints

```python
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="User API", version="1.0.0")

# Schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Endpoints
@app.get("/api/v1/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List users with pagination."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@app.get("/api/v1/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post(
    "/api/v1/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create new user."""
    # Check for existing email
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="User with this email already exists"
        )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        name=user_data.name,
        hashed_password=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.patch("/api/v1/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db)
):
    """Partially update user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update only provided fields
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user

@app.delete("/api/v1/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return None
```

#### Error Handling

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    """Handle validation errors with detailed messages."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors()
            }
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardized error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.detail.get("code", "ERROR"),
                "message": exc.detail if isinstance(exc.detail, str) else exc.detail.get("message"),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )
```

#### Authentication & Authorization

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Validate JWT token and return current user."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# Protected endpoint
@app.get("/api/v1/users/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user's profile."""
    return current_user

# Role-based authorization
def require_admin(current_user: User = Depends(get_current_user)):
    """Require admin role."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@app.delete("/api/v1/users/{user_id}")
async def delete_user_admin(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)."""
    # Implementation...
```

### GraphQL API Implementation (Strawberry)

```python
import strawberry
from typing import List, Optional
from datetime import datetime

# Types
@strawberry.type
class User:
    id: strawberry.ID
    email: str
    name: str
    created_at: datetime

@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    content: str
    author: User
    published_at: Optional[datetime]

# Input types
@strawberry.input
class CreateUserInput:
    email: str
    name: str
    password: str

# Queries
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> Optional[User]:
        """Get user by ID."""
        # Implementation with DataLoader to prevent N+1
        return await user_loader.load(id)

    @strawberry.field
    async def users(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """List users with pagination."""
        return await get_users(limit=limit, offset=offset)

# Mutations
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_user(self, input: CreateUserInput) -> User:
        """Create new user."""
        user = await create_user_in_db(
            email=input.email,
            name=input.name,
            password=input.password
        )
        return user

# Schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
```

### API Versioning

#### URL Versioning (Recommended for REST)

```python
# v1 API
@app.get("/api/v1/users/{user_id}")
async def get_user_v1(user_id: int):
    return {"id": user_id, "name": "John"}

# v2 API with breaking changes
@app.get("/api/v2/users/{user_id}")
async def get_user_v2(user_id: int):
    return {
        "id": user_id,
        "profile": {"name": "John", "avatar": "url"}
    }
```

#### Header Versioning

```python
from fastapi import Header

@app.get("/api/users/{user_id}")
async def get_user(
    user_id: int,
    api_version: str = Header(default="1", alias="X-API-Version")
):
    if api_version == "2":
        return {"id": user_id, "profile": {"name": "John"}}
    return {"id": user_id, "name": "John"}
```

## Best Practices

### REST API Design

**Do:**
- ✅ Use nouns for resources, not verbs
- ✅ Use HTTP methods correctly (GET for read, POST for create, etc.)
- ✅ Return appropriate HTTP status codes
- ✅ Version your API from day one
- ✅ Use pagination for list endpoints
- ✅ Implement filtering, sorting, field selection
- ✅ Document with OpenAPI/Swagger
- ✅ Use consistent error response format

**Don't:**
- ❌ Use verbs in URLs (`/api/getUser` ❌ → `/api/users/{id}` ✅)
- ❌ Return 200 for errors
- ❌ Break backward compatibility without versioning
- ❌ Return entire database in list endpoints
- ❌ Ignore HTTP standards
- ❌ Use inconsistent naming (camelCase vs snake_case)

### Request/Response Design

**Good Request Schema:**
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "preferences": {
    "newsletter": true,
    "notifications": false
  }
}
```

**Good Response Schema:**
```json
{
  "id": 123,
  "email": "user@example.com",
  "name": "John Doe",
  "preferences": {
    "newsletter": true,
    "notifications": false
  },
  "created_at": "2025-10-25T12:00:00Z",
  "updated_at": "2025-10-25T12:00:00Z"
}
```

**Good Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ],
    "timestamp": "2025-10-25T12:00:00Z",
    "request_id": "abc-123-def"
  }
}
```

### Pagination

**Offset-based (simple):**
```
GET /api/v1/users?limit=20&offset=40
```

**Cursor-based (recommended for large datasets):**
```
GET /api/v1/users?limit=20&cursor=eyJpZCI6MTIzfQ==

Response:
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTQzfQ==",
    "has_more": true
  }
}
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/search")
@limiter.limit("10/minute")
async def search(request: Request, query: str):
    """Rate limited to 10 requests per minute."""
    return {"results": []}
```

### API Documentation

**OpenAPI/Swagger (FastAPI auto-generates):**
```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="API for managing users and posts",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

@app.get(
    "/api/v1/users/{user_id}",
    summary="Get user by ID",
    description="Retrieve detailed user information by user ID",
    response_description="User details",
    tags=["users"]
)
async def get_user(user_id: int):
    """
    Get user by ID.

    - **user_id**: Unique user identifier

    Returns user object with all details.
    """
    pass
```

## Examples

### Complete REST API Endpoint

```python
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

@app.get("/api/v1/posts", response_model=PaginatedPostsResponse)
async def list_posts(
    # Pagination
    limit: int = Query(default=20, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),

    # Filtering
    author_id: Optional[int] = Query(default=None, description="Filter by author"),
    status: Optional[str] = Query(default=None, description="published|draft"),

    # Sorting
    sort_by: str = Query(default="created_at", description="Field to sort by"),
    order: str = Query(default="desc", description="asc|desc"),

    # Field selection
    fields: Optional[str] = Query(default=None, description="Comma-separated fields"),

    # Auth
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List posts with filtering, sorting, and pagination.

    **Query Parameters:**
    - limit: Maximum items to return (default: 20, max: 100)
    - offset: Number of items to skip (default: 0)
    - author_id: Filter posts by author
    - status: Filter by publication status (published|draft)
    - sort_by: Field to sort by (default: created_at)
    - order: Sort order (asc|desc, default: desc)
    - fields: Comma-separated list of fields to return

    **Example:**
    ```
    GET /api/v1/posts?limit=10&author_id=5&status=published&sort_by=views&order=desc
    ```
    """
    query = db.query(Post)

    # Apply filters
    if author_id:
        query = query.filter(Post.author_id == author_id)
    if status:
        query = query.filter(Post.status == status)

    # Apply sorting
    if order == "desc":
        query = query.order_by(desc(getattr(Post, sort_by)))
    else:
        query = query.order_by(asc(getattr(Post, sort_by)))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    posts = query.offset(offset).limit(limit).all()

    return {
        "data": posts,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    }
```

## Related Skills & Conventions

- [Database Management](./database-management.md) - Database operations and migrations
- [Testing Strategies](./testing-strategies.md) - API testing approaches
- [Authentication Patterns](../patterns/authentication-patterns.md) - JWT, OAuth implementation
- [Error Handling Patterns](../patterns/error-handling-patterns.md) - Robust error handling

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
