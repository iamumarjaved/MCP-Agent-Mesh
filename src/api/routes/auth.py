"""JWT authentication routes.

Provides login, token verification, and role-based access control for
the MCP Agent Mesh API.  Uses HS256 JWTs with configurable expiration.

IMPORTANT: The ``DEMO_USERS`` dict is for development only.  In
production, replace with a proper user store and hashed passwords.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

_security = HTTPBearer()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Credentials for obtaining a JWT."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Successful authentication response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    """Current user identity extracted from the JWT."""
    user_id: str
    role: str
    exp: datetime


# ---------------------------------------------------------------------------
# Demo user store (development only)
# ---------------------------------------------------------------------------

DEMO_USERS: dict[str, dict[str, str]] = {
    "admin": {"password": "admin123", "role": "admin"},
    "analyst": {"password": "analyst123", "role": "analyst"},
    "viewer": {"password": "viewer123", "role": "viewer"},
}


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_token(user_id: str, role: str) -> str:
    """Create a signed JWT for the given user.

    The token carries ``sub`` (user ID), ``role``, ``iat``, and ``exp``
    claims.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.jwt_expiration_minutes)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict[str, Any]:
    """FastAPI dependency that validates a Bearer token.

    Returns the decoded JWT payload dict on success.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(roles: list[str]):
    """Return a FastAPI dependency that enforces one of the given roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(["admin"]))])
        async def admin_endpoint(): ...
    """

    def _check(payload: dict[str, Any] = Depends(verify_token)) -> dict[str, Any]:
        user_role = payload.get("role", "")
        if user_role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role(s): {', '.join(roles)}",
            )
        return payload

    return _check


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate with username/password and receive a JWT.

    Returns an access token, its type, and the number of seconds until
    expiration.
    """
    user = DEMO_USERS.get(request.username)
    if user is None or user["password"] != request.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    token = create_token(user_id=request.username, role=user["role"])
    expires_in = settings.jwt_expiration_minutes * 60

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    payload: dict[str, Any] = Depends(verify_token),
) -> UserInfo:
    """Return identity information for the currently authenticated user."""
    return UserInfo(
        user_id=payload["sub"],
        role=payload["role"],
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
