---
title: FastAPI Starter Template
description: Production-ready FastAPI project structure with SQLModel, PostgreSQL, authentication, and testing
tags: [template, fastapi, python, sqlmodel, postgresql, docker]
type: template
version: "1.0.0"
category: backend
---

# FastAPI Starter Template

## Overview

This template provides a production-ready FastAPI application structure with SQLModel, PostgreSQL, JWT authentication, Docker support, and comprehensive testing setup. Use this template as a starting point for building scalable REST APIs.

**Features:**
- FastAPI with async/await
- SQLModel for database models
- PostgreSQL with Alembic migrations
- JWT authentication
- Docker and Docker Compose
- Pytest testing setup
- Environment-based configuration
- API documentation (OpenAPI/Swagger)
- Structured logging

## Project Structure

```
fastapi-starter/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── config.py               # Configuration management
│   ├── database.py             # Database connection
│   ├── dependencies.py         # FastAPI dependencies
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py            # User model
│   │   └── post.py            # Post model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py            # User schemas
│   │   └── post.py            # Post schemas
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # API router
│   │   │   ├── auth.py        # Authentication endpoints
│   │   │   ├── users.py       # User endpoints
│   │   │   └── posts.py       # Post endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py    # Authentication logic
│   │   └── user_service.py    # User business logic
│   └── core/
│       ├── __init__.py
│       ├── security.py        # Password hashing, JWT
│       └── logging.py         # Logging configuration
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures
│   ├── test_auth.py
│   └── test_users.py
├── alembic/
│   ├── versions/              # Migration files
│   └── env.py
├── .env.example               # Environment variables template
├── .gitignore
├── alembic.ini               # Alembic configuration
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml            # Poetry dependencies
├── pytest.ini
└── README.md
```

## Core Files

### 1. main.py - Application Entry Point

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("application_startup", version="1.0.0")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("application_shutdown")
```

### 2. config.py - Configuration Management

```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Application settings."""

    # Project
    PROJECT_NAME: str = "FastAPI Starter"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str
    DB_ECHO_LOG: bool = False

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### 3. database.py - Database Configuration

```python
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO_LOG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session
```

### 4. models/user.py - User Model

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    """User model."""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    posts: List["Post"] = Relationship(back_populates="author")
```

### 5. schemas/user.py - User Schemas

```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    """User creation schema."""
    password: str

class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    """User response schema."""
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

### 6. api/v1/auth.py - Authentication Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from app.database import get_session
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_session)
):
    """Register new user."""
    auth_service = AuthService(db)
    user = await auth_service.register(user_data)
    return user

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session)
):
    """Login and get access token."""
    auth_service = AuthService(db)
    tokens = await auth_service.login(form_data.username, form_data.password)
    return tokens

@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_session)
):
    """Refresh access token."""
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_token(refresh_token)
    return tokens
```

### 7. core/security.py - Security Utilities

```python
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

### 8. Docker Setup

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Copy application
COPY . .

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/app
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    volumes:
      - .:/app

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 9. Testing Setup

**conftest.py:**
```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.database import get_session

@pytest.fixture(name="session")
def session_fixture():
    """Create test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
```

**test_auth.py:**
```python
def test_register_user(client):
    """Test user registration."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "password123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_login(client):
    """Test user login."""
    # Register user first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "password123"
        }
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
```

### 10. Dependencies

**pyproject.toml:**
```toml
[tool.poetry]
name = "fastapi-starter"
version = "1.0.0"
description = "FastAPI starter template"
authors = ["Your Name <you@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
sqlmodel = "^0.0.14"
psycopg2-binary = "^2.9.9"
alembic = "^1.13.1"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.6"
pydantic-settings = "^2.1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.4"
pytest-asyncio = "^0.23.3"
httpx = "^0.26.0"
```

## Environment Variables

**.env.example:**
```bash
# Project
PROJECT_NAME="FastAPI Starter"
API_V1_PREFIX="/api/v1"

# Database
DATABASE_URL="postgresql://user:password@localhost:5432/app"
DB_ECHO_LOG=false

# Security
SECRET_KEY="your-secret-key-here-change-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Environment
ENVIRONMENT="development"
```

## Getting Started

```bash
# 1. Clone template
git clone <repository-url> my-fastapi-app
cd my-fastapi-app

# 2. Install dependencies
poetry install

# 3. Create .env file
cp .env.example .env
# Edit .env with your configuration

# 4. Run with Docker
docker-compose up -d

# 5. Run migrations
alembic upgrade head

# 6. Access API
# API: http://localhost:8000
# Docs: http://localhost:8000/api/v1/docs

# 7. Run tests
pytest
```

## Related Templates & Skills

- [API Development](../skills/api-development.md) - API design patterns
- [Database Management](../skills/database-management.md) - Database setup
- [Testing Strategies](../skills/testing-strategies.md) - Testing approaches

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
