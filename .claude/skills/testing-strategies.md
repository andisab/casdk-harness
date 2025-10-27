---
title: Testing Strategies
description: Comprehensive testing approaches including unit, integration, E2E, and test automation best practices
tags: [skill, testing, tdd, unit-testing, integration-testing, e2e, pytest, jest]
type: skill
version: "1.0.0"
category: quality-assurance
---

# Testing Strategies

## Overview

This skill provides comprehensive testing strategies covering unit tests, integration tests, end-to-end tests, test-driven development (TDD), mocking patterns, and CI/CD integration. Use this skill to build robust test suites that ensure code quality and prevent regressions.

**When to use this skill:**
- Implementing test-driven development (TDD)
- Building comprehensive test suites
- Setting up test automation in CI/CD
- Creating test fixtures and mocks
- Debugging flaky tests
- Measuring and improving test coverage

## Key Concepts

### Testing Pyramid

```
       /\
      /  \     E2E Tests (Few)
     /----\    - Test complete user workflows
    /      \   - Slow, expensive, brittle
   /--------\  - Run on every release
  /          \
 /------------\ Integration Tests (Some)
/              \ - Test service interactions
----------------  - Moderate speed
                  - Run on every commit

================== Unit Tests (Many)
                  - Test individual functions
                  - Fast, isolated, deterministic
                  - Run on every save
```

**Recommended Distribution:**
- 70% Unit Tests
- 20% Integration Tests
- 10% End-to-End Tests

### Test-Driven Development (TDD)

**Red-Green-Refactor Cycle:**

1. **Red**: Write a failing test
   ```python
   def test_calculate_discount():
       assert calculate_discount(100, 0.20) == 80
   # Test fails - function doesn't exist yet
   ```

2. **Green**: Write minimum code to make it pass
   ```python
   def calculate_discount(price, discount_rate):
       return price - (price * discount_discount_rate)
   # Test passes
   ```

3. **Refactor**: Improve code while keeping tests green
   ```python
   def calculate_discount(price: Decimal, discount_rate: float) -> Decimal:
       """Calculate final price after applying discount."""
       if not 0 <= discount_rate <= 1:
           raise ValueError("Discount rate must be between 0 and 1")
       return price * (1 - discount_rate)
   # Tests still pass, code is better
   ```

### Test Coverage Metrics

**Types of Coverage:**
- **Line Coverage**: Percentage of code lines executed
- **Branch Coverage**: Percentage of conditional branches tested
- **Function Coverage**: Percentage of functions called
- **Statement Coverage**: Percentage of statements executed

**Coverage Targets:**
- Critical business logic: 90-100%
- API endpoints: 80-95%
- Utility functions: 75-90%
- Overall project: 80%+ (minimum)

**Note:** High coverage ≠ good tests. Focus on meaningful test cases, not just coverage percentage.

## Implementation

### Unit Testing (Python - Pytest)

```python
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from myapp.services import UserService, PaymentService
from myapp.models import User
from myapp.exceptions import InsufficientFundsError

# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Provide a test database session with rollback."""
    # Setup
    session = TestSessionLocal()
    try:
        yield session
    finally:
        # Teardown
        session.rollback()
        session.close()

@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed_password_123"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def user_service(db_session):
    """Provide UserService instance with test database."""
    return UserService(db=db_session)

# ============================================================================
# UNIT TESTS - UserService
# ============================================================================

class TestUserService:
    """Test suite for UserService."""

    def test_create_user_success(self, user_service, db_session):
        """Test successful user creation."""
        # Arrange
        user_data = {
            "email": "newuser@example.com",
            "name": "New User",
            "password": "SecureP@ss123"
        }

        # Act
        user = user_service.create_user(**user_data)

        # Assert
        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.name == "New User"
        assert user.hashed_password != "SecureP@ss123"  # Password should be hashed
        assert user.is_active is True
        assert user.created_at is not None

        # Verify in database
        db_user = db_session.query(User).filter(User.id == user.id).first()
        assert db_user is not None
        assert db_user.email == user.email

    def test_create_user_duplicate_email(self, user_service, sample_user):
        """Test user creation fails with duplicate email."""
        # Arrange
        user_data = {
            "email": sample_user.email,  # Duplicate email
            "name": "Another User",
            "password": "password123"
        }

        # Act & Assert
        with pytest.raises(ValueError, match="Email already exists"):
            user_service.create_user(**user_data)

    def test_create_user_invalid_email(self, user_service):
        """Test user creation fails with invalid email."""
        # Arrange
        user_data = {
            "email": "invalid-email",  # Invalid format
            "name": "Test User",
            "password": "password123"
        }

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid email format"):
            user_service.create_user(**user_data)

    @pytest.mark.parametrize("password,should_pass", [
        ("short", False),                    # Too short
        ("NoNumber!", False),                # No number
        ("nospecial1", False),               # No special char
        ("ValidP@ss1", True),                # Valid
        ("AnotherGood123!", True),           # Valid
    ])
    def test_password_validation(self, user_service, password, should_pass):
        """Test password validation with various inputs."""
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "password": password
        }

        if should_pass:
            user = user_service.create_user(**user_data)
            assert user is not None
        else:
            with pytest.raises(ValueError, match="Password"):
                user_service.create_user(**user_data)

    def test_get_user_by_email(self, user_service, sample_user):
        """Test retrieving user by email."""
        # Act
        user = user_service.get_user_by_email(sample_user.email)

        # Assert
        assert user is not None
        assert user.id == sample_user.id
        assert user.email == sample_user.email

    def test_get_user_by_email_not_found(self, user_service):
        """Test retrieving non-existent user returns None."""
        # Act
        user = user_service.get_user_by_email("nonexistent@example.com")

        # Assert
        assert user is None

    def test_update_user_profile(self, user_service, sample_user):
        """Test updating user profile information."""
        # Arrange
        updates = {
            "name": "Updated Name",
            "bio": "New bio text"
        }

        # Act
        updated_user = user_service.update_user(sample_user.id, **updates)

        # Assert
        assert updated_user.name == "Updated Name"
        assert updated_user.bio == "New bio text"
        assert updated_user.email == sample_user.email  # Unchanged
        assert updated_user.updated_at > updated_user.created_at

    def test_delete_user_soft_delete(self, user_service, sample_user, db_session):
        """Test soft delete sets deleted_at timestamp."""
        # Act
        user_service.delete_user(sample_user.id)

        # Assert
        db_session.refresh(sample_user)
        assert sample_user.deleted_at is not None
        assert sample_user.is_active is False

# ============================================================================
# MOCKING EXTERNAL SERVICES
# ============================================================================

class TestPaymentService:
    """Test payment processing with mocked external services."""

    @pytest.fixture
    def payment_service(self, db_session):
        """Provide PaymentService with mocked Stripe."""
        return PaymentService(db=db_session)

    @pytest.fixture
    def mock_stripe(self, monkeypatch):
        """Mock Stripe API calls."""
        class MockStripe:
            @staticmethod
            def create_payment_intent(amount, currency="usd"):
                return {
                    "id": "pi_test_123",
                    "amount": amount,
                    "status": "succeeded"
                }

            @staticmethod
            def create_refund(payment_intent_id):
                return {
                    "id": "re_test_123",
                    "status": "succeeded"
                }

        monkeypatch.setattr("myapp.services.stripe", MockStripe())
        return MockStripe

    def test_process_payment_success(
        self,
        payment_service,
        sample_user,
        mock_stripe,
        db_session
    ):
        """Test successful payment processing."""
        # Arrange
        amount = Decimal("99.99")

        # Act
        payment = payment_service.process_payment(
            user_id=sample_user.id,
            amount=amount,
            description="Test payment"
        )

        # Assert
        assert payment.id is not None
        assert payment.user_id == sample_user.id
        assert payment.amount == amount
        assert payment.status == "succeeded"
        assert payment.stripe_payment_id == "pi_test_123"

    def test_process_refund(
        self,
        payment_service,
        sample_user,
        mock_stripe,
        db_session
    ):
        """Test payment refund processing."""
        # Arrange - Create a payment first
        payment = payment_service.process_payment(
            user_id=sample_user.id,
            amount=Decimal("50.00"),
            description="Test payment"
        )

        # Act
        refund = payment_service.refund_payment(payment.id)

        # Assert
        assert refund.id is not None
        assert refund.payment_id == payment.id
        assert refund.status == "succeeded"

        # Verify payment is marked as refunded
        db_session.refresh(payment)
        assert payment.is_refunded is True

# ============================================================================
# ASYNC TESTING
# ============================================================================

@pytest.mark.asyncio
async def test_async_user_creation():
    """Test async user creation endpoint."""
    async with AsyncTestClient() as client:
        # Arrange
        user_data = {
            "email": "async@example.com",
            "name": "Async User",
            "password": "SecureP@ss1!"
        }

        # Act
        response = await client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "async@example.com"
        assert "password" not in data  # Sensitive data not returned
```

### Integration Testing (FastAPI)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from myapp.main import app
from myapp.database import Base, get_db

# ============================================================================
# TEST DATABASE SETUP
# ============================================================================

# Use SQLite for testing (faster than PostgreSQL)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """Provide test client with test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

# ============================================================================
# INTEGRATION TESTS - API ENDPOINTS
# ============================================================================

class TestUserAPI:
    """Integration tests for User API endpoints."""

    def test_create_user_endpoint(self, client):
        """Test POST /api/v1/users endpoint."""
        # Arrange
        user_data = {
            "email": "api@example.com",
            "name": "API User",
            "password": "SecureP@ss1!"
        }

        # Act
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "api@example.com"
        assert data["name"] == "API User"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_create_user_duplicate_email_returns_409(self, client):
        """Test creating user with duplicate email returns 409 Conflict."""
        # Arrange - Create first user
        user_data = {
            "email": "duplicate@example.com",
            "name": "First User",
            "password": "Password1!"
        }
        client.post("/api/v1/users", json=user_data)

        # Act - Try to create duplicate
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == 409
        error = response.json()
        assert "error" in error
        assert "already exists" in error["error"]["message"].lower()

    def test_get_user_by_id(self, client):
        """Test GET /api/v1/users/{user_id} endpoint."""
        # Arrange - Create user first
        create_response = client.post("/api/v1/users", json={
            "email": "getme@example.com",
            "name": "Get Me",
            "password": "Password1!"
        })
        user_id = create_response.json()["id"]

        # Act
        response = client.get(f"/api/v1/users/{user_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "getme@example.com"

    def test_get_nonexistent_user_returns_404(self, client):
        """Test getting non-existent user returns 404."""
        # Act
        response = client.get("/api/v1/users/99999")

        # Assert
        assert response.status_code == 404

    def test_update_user(self, client):
        """Test PATCH /api/v1/users/{user_id} endpoint."""
        # Arrange - Create and authenticate
        create_response = client.post("/api/v1/users", json={
            "email": "update@example.com",
            "name": "Original Name",
            "password": "Password1!"
        })
        user_id = create_response.json()["id"]

        # Get auth token
        login_response = client.post("/api/v1/auth/login", json={
            "email": "update@example.com",
            "password": "Password1!"
        })
        token = login_response.json()["access_token"]

        # Act
        response = client.patch(
            f"/api/v1/users/{user_id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "update@example.com"  # Unchanged

    def test_list_users_with_pagination(self, client):
        """Test GET /api/v1/users with pagination."""
        # Arrange - Create multiple users
        for i in range(25):
            client.post("/api/v1/users", json={
                "email": f"user{i}@example.com",
                "name": f"User {i}",
                "password": "Password1!"
            })

        # Act
        response = client.get("/api/v1/users?limit=10&offset=0")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
        assert data["pagination"]["total"] == 25
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 0
        assert data["pagination"]["has_more"] is True

class TestAuthenticationFlow:
    """Integration tests for authentication workflow."""

    def test_complete_auth_flow(self, client):
        """Test registration → login → access protected route."""
        # Step 1: Register
        register_response = client.post("/api/v1/users", json={
            "email": "auth@example.com",
            "name": "Auth User",
            "password": "SecureP@ss1!"
        })
        assert register_response.status_code == 201

        # Step 2: Login
        login_response = client.post("/api/v1/auth/login", json={
            "email": "auth@example.com",
            "password": "SecureP@ss1!"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        assert token is not None

        # Step 3: Access protected route
        profile_response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert profile_response.status_code == 200
        assert profile_response.json()["email"] == "auth@example.com"

    def test_access_protected_route_without_token(self, client):
        """Test accessing protected route without authentication."""
        # Act
        response = client.get("/api/v1/users/me")

        # Assert
        assert response.status_code == 401
```

### End-to-End Testing (Playwright)

```python
import pytest
from playwright.sync_api import Page, expect

# ============================================================================
# E2E TESTS - User Registration and Login Flow
# ============================================================================

@pytest.mark.e2e
def test_user_registration_flow(page: Page):
    """Test complete user registration workflow."""
    # Navigate to registration page
    page.goto("http://localhost:3000/register")

    # Fill in registration form
    page.fill('input[name="email"]', "e2e@example.com")
    page.fill('input[name="name"]', "E2E Test User")
    page.fill('input[name="password"]', "SecureP@ss1!")
    page.fill('input[name="confirmPassword"]', "SecureP@ss1!")

    # Submit form
    page.click('button[type="submit"]')

    # Verify redirect to dashboard
    expect(page).to_have_url("http://localhost:3000/dashboard")

    # Verify welcome message
    expect(page.locator("h1")).to_contain_text("Welcome, E2E Test User")

@pytest.mark.e2e
def test_login_and_create_post(page: Page):
    """Test login and creating a blog post."""
    # Login
    page.goto("http://localhost:3000/login")
    page.fill('input[name="email"]', "existing@example.com")
    page.fill('input[name="password"]', "Password1!")
    page.click('button[type="submit"]')

    # Wait for dashboard
    page.wait_for_url("**/dashboard")

    # Navigate to create post
    page.click("text=New Post")

    # Fill post form
    page.fill('input[name="title"]', "E2E Test Post")
    page.fill('textarea[name="content"]', "This is test content")
    page.select_option('select[name="status"]', "published")

    # Submit
    page.click('button:has-text("Publish")')

    # Verify success message
    expect(page.locator(".toast")).to_contain_text("Post published successfully")

    # Verify post appears in list
    page.goto("http://localhost:3000/posts")
    expect(page.locator("article")).to_contain_text("E2E Test Post")
```

## Best Practices

### Unit Testing Best Practices

**Do:**
- ✅ Test one thing per test
- ✅ Use descriptive test names (test_create_user_with_duplicate_email_raises_error)
- ✅ Follow AAA pattern: Arrange, Act, Assert
- ✅ Use fixtures for common setup
- ✅ Mock external dependencies
- ✅ Test edge cases and error conditions
- ✅ Keep tests independent (can run in any order)
- ✅ Make tests fast (<100ms per test)

**Don't:**
- ❌ Test implementation details (test behavior, not internals)
- ❌ Have tests that depend on each other
- ❌ Use sleep() or arbitrary waits
- ❌ Test external services directly (use mocks)
- ❌ Write tests that are flaky
- ❌ Ignore failing tests

### Integration Testing Best Practices

**Do:**
- ✅ Use test database (isolated from development/production)
- ✅ Reset database state between tests
- ✅ Test API contracts (request/response formats)
- ✅ Test authentication and authorization
- ✅ Test error responses (4xx, 5xx)
- ✅ Test pagination, filtering, sorting
- ✅ Use test client (don't make real HTTP requests in tests)

**Don't:**
- ❌ Use production database for tests
- ❌ Share state between tests
- ❌ Skip teardown/cleanup
- ❌ Test only happy paths

### E2E Testing Best Practices

**Do:**
- ✅ Test critical user workflows
- ✅ Use stable selectors (data-testid, not CSS classes)
- ✅ Wait for elements explicitly
- ✅ Test across different browsers
- ✅ Run E2E tests in CI/CD
- ✅ Take screenshots on failures
- ✅ Keep E2E tests minimal (expensive to maintain)

**Don't:**
- ❌ Test every possible scenario with E2E
- ❌ Use brittle selectors
- ❌ Hard-code timeouts
- ❌ Skip cleanup between tests

## Related Skills & Conventions

- [Code Review Techniques](./code-review-techniques.md) - Reviewing test quality
- [CI/CD Workflows](./deployment-operations.md) - Running tests in pipelines
- [Testing QA Orchestration](../workflows/testing-qa-orchestration.md) - Multi-agent testing workflow

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
