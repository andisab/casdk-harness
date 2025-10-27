---
title: Authentication Patterns
description: JWT, OAuth 2.0, session management, and secure authentication implementation patterns
tags: [pattern, authentication, security, jwt, oauth, sessions]
type: pattern
version: "1.0.0"
category: security
---

# Authentication Patterns

## Overview

This pattern guide covers authentication strategies including JWT tokens, OAuth 2.0/OIDC, session-based authentication, multi-factor authentication (MFA), and secure password management. Use these patterns to implement secure, scalable authentication systems.

**When to use these patterns:**
- Implementing user authentication
- Building OAuth providers or consumers
- Securing API endpoints
- Managing user sessions
- Implementing SSO (Single Sign-On)
- Adding multi-factor authentication

## Patterns

### 1. JWT (JSON Web Token) Authentication

**Use Case:** Stateless authentication for APIs, microservices, mobile apps

**Architecture:**
```
Client → Login → Server validates credentials
                 ↓
                 Server generates JWT token
                 ↓
Client ← JWT ← Server

Subsequent requests:
Client → Request + JWT in Header → Server validates JWT → Response
```

**Implementation:**

```python
# FastAPI JWT Authentication
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Validate JWT and return current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type
        if payload.get("type") != "access":
            raise credentials_exception

        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user

@app.post("/auth/login")
async def login(
    credentials: LoginCredentials,
    db: Session = Depends(get_db)
):
    """Login endpoint - returns access and refresh tokens."""
    # Verify credentials
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not pwd_context.verify(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/auth/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = payload.get("sub")

        # Create new access token
        access_token = create_access_token(data={"sub": user_id})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.get("/users/me")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Protected endpoint - requires valid JWT."""
    return current_user
```

**Best Practices:**
- ✅ Use short expiration for access tokens (15-30 minutes)
- ✅ Use longer expiration for refresh tokens (7-30 days)
- ✅ Store tokens securely (httpOnly cookies for web)
- ✅ Include token type in payload
- ✅ Implement token refresh mechanism
- ✅ Use strong secret keys (256-bit minimum)
- ✅ Validate token signature and expiration

### 2. OAuth 2.0 / OpenID Connect

**Use Case:** Third-party authentication (Login with Google, GitHub, etc.), SSO

**OAuth 2.0 Flow (Authorization Code):**
```
1. Client → Authorization Request → Authorization Server
2. User authenticates and authorizes
3. Authorization Server → Authorization Code → Client
4. Client → Authorization Code + Client Secret → Authorization Server
5. Authorization Server → Access Token → Client
6. Client → Access Token → Resource Server → Protected Resource
```

**Implementation:**

```python
# OAuth 2.0 with FastAPI and Authlib
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

config = Config('.env')
oauth = OAuth(config)

# Register OAuth providers
oauth.register(
    name='google',
    client_id=config('GOOGLE_CLIENT_ID'),
    client_secret=config('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

oauth.register(
    name='github',
    client_id=config('GITHUB_CLIENT_ID'),
    client_secret=config('GITHUB_CLIENT_SECRET'),
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'}
)

@app.get('/auth/{provider}')
async def oauth_login(request: Request, provider: str):
    """Initiate OAuth flow."""
    client = oauth.create_client(provider)
    redirect_uri = request.url_for('oauth_callback', provider=provider)
    return await client.authorize_redirect(request, redirect_uri)

@app.get('/auth/{provider}/callback')
async def oauth_callback(
    request: Request,
    provider: str,
    db: Session = Depends(get_db)
):
    """OAuth callback - exchange code for token."""
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)

    # Get user info from provider
    if provider == 'google':
        user_info = token.get('userinfo')
        email = user_info.get('email')
        name = user_info.get('name')
    elif provider == 'github':
        resp = await client.get('user', token=token)
        user_info = resp.json()
        email = user_info.get('email')
        name = user_info.get('name')

    # Find or create user
    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            email=email,
            name=name,
            oauth_provider=provider,
            oauth_id=user_info.get('sub') or user_info.get('id')
        )
        db.add(user)
        db.commit()

    # Create JWT for our application
    access_token = create_access_token(data={"sub": user.id})

    return RedirectResponse(
        url=f"/dashboard?token={access_token}",
        status_code=302
    )
```

### 3. Session-Based Authentication

**Use Case:** Traditional web applications, server-side rendered apps

**Implementation:**

```python
# Session-based authentication with FastAPI
from fastapi import FastAPI, Depends, Cookie, Response
from starlette.middleware.sessions import SessionMiddleware
import secrets

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# In-memory session store (use Redis in production)
sessions = {}

def create_session(user_id: int) -> str:
    """Create new session."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }
    return session_id

def get_session_user(session_id: str = Cookie(None)) -> Optional[User]:
    """Get user from session."""
    if not session_id or session_id not in sessions:
        return None

    session = sessions[session_id]

    # Check session expiry (30 minutes idle timeout)
    if datetime.utcnow() - session["last_activity"] > timedelta(minutes=30):
        del sessions[session_id]
        return None

    # Update last activity
    session["last_activity"] = datetime.utcnow()

    return db.query(User).filter(User.id == session["user_id"]).first()

@app.post("/login")
async def login(credentials: LoginCredentials, response: Response):
    """Login and create session."""
    user = authenticate_user(credentials.email, credentials.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session
    session_id = create_session(user.id)

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="lax",
        max_age=3600  # 1 hour
    )

    return {"message": "Login successful"}

@app.post("/logout")
async def logout(
    response: Response,
    session_id: str = Cookie(None)
):
    """Logout and destroy session."""
    if session_id in sessions:
        del sessions[session_id]

    response.delete_cookie("session_id")
    return {"message": "Logout successful"}
```

### 4. Multi-Factor Authentication (MFA)

**Implementation:**

```python
# TOTP-based MFA
import pyotp
import qrcode
from io import BytesIO
import base64

def generate_mfa_secret(user: User) -> str:
    """Generate MFA secret for user."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.commit()
    return secret

def generate_qr_code(user: User) -> str:
    """Generate QR code for MFA setup."""
    totp = pyotp.TOTP(user.mfa_secret)
    uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="MyApp"
    )

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return f"data:image/png;base64,{img_str}"

@app.post("/mfa/enable")
async def enable_mfa(current_user: User = Depends(get_current_user)):
    """Enable MFA for user."""
    secret = generate_mfa_secret(current_user)
    qr_code = generate_qr_code(current_user)

    return {
        "secret": secret,
        "qr_code": qr_code
    }

@app.post("/mfa/verify")
async def verify_mfa(
    code: str,
    current_user: User = Depends(get_current_user)
):
    """Verify MFA code and activate MFA."""
    totp = pyotp.TOTP(current_user.mfa_secret)

    if totp.verify(code, valid_window=1):
        current_user.mfa_enabled = True
        db.commit()
        return {"message": "MFA enabled successfully"}

    raise HTTPException(status_code=400, detail="Invalid MFA code")

@app.post("/login/mfa")
async def login_with_mfa(credentials: MFALoginCredentials):
    """Login with email, password, and MFA code."""
    # Verify email and password
    user = authenticate_user(credentials.email, credentials.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify MFA code if enabled
    if user.mfa_enabled:
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(credentials.mfa_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
```

## Best Practices

### Password Security

**Do:**
- ✅ Use bcrypt or Argon2 for password hashing
- ✅ Enforce minimum password length (12+ characters)
- ✅ Require mix of characters (uppercase, lowercase, numbers, symbols)
- ✅ Implement rate limiting on login attempts
- ✅ Use password strength meter
- ✅ Implement account lockout after failed attempts
- ✅ Require password change on first login

**Don't:**
- ❌ Store passwords in plain text
- ❌ Use MD5 or SHA1 for passwords
- ❌ Send passwords in URL parameters
- ❌ Email passwords to users
- ❌ Implement custom encryption algorithms

### Token Security

**Do:**
- ✅ Use HTTPS for all authentication endpoints
- ✅ Implement token rotation
- ✅ Store tokens securely (httpOnly cookies for web)
- ✅ Include token expiration
- ✅ Implement token revocation
- ✅ Use separate access and refresh tokens

**Don't:**
- ❌ Store tokens in localStorage (XSS vulnerable)
- ❌ Send tokens in URL parameters
- ❌ Use weak secrets for JWT signing
- ❌ Allow unlimited token lifetime

## Related Patterns & Skills

- [API Development](../skills/api-development.md) - Securing API endpoints
- [Error Handling Patterns](./error-handling-patterns.md) - Auth error responses
- [Security Hardening](../workflows/security-hardening.md) - Security audits

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
