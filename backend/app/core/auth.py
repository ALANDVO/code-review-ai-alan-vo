"""
Authentication middleware and JWT verification for the Code Review AI API.

Architecture: SPA PKCE client with bearer-only API.
- Tokens are issued by Keycloak OIDC.
- Access tokens stay in memory on the frontend (not localStorage).
- The API validates bearer tokens: signature, issuer, audience, expiry.
- Demo mode binds to localhost only and auto-issues a demo principal for testing.
- Demo mode MUST NOT be active when ENV=production (enforced at Settings.load()).

Roles: viewer (read-only), operator (can submit reviews/scans), admin (full access).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Roles ──────────────────────────────────────────────────────────────────────

class Role(str, Enum):
    viewer = "viewer"
    operator = "operator"
    admin = "admin"


ROLE_HIERARCHY = {
    Role.viewer: 0,
    Role.operator: 1,
    Role.admin: 2,
}


@dataclass
class Principal:
    user_id: str
    email: str
    role: Role
    demo: bool = False


# ── JWKS cache ─────────────────────────────────────────────────────────────────

_jwks_cache: Optional[dict] = None
_jwks_fetched_at: float = 0.0
_jwks_url = ""
_JWKS_TTL = 300.0  # 5 minutes


def _get_jwks(app_settings=settings) -> dict:
    global _jwks_cache, _jwks_fetched_at, _jwks_url
    now = time.monotonic()
    if _jwks_cache and _jwks_url == app_settings.oidc_jwks_url and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
            resp = client.get(app_settings.oidc_jwks_url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
            _jwks_url = app_settings.oidc_jwks_url
            return _jwks_cache
    except Exception as exc:
        if _jwks_cache and _jwks_url == app_settings.oidc_jwks_url and now - _jwks_fetched_at < 3600:
            logger.warning("JWKS refresh failed, using cached keys: %s", exc)
            return _jwks_cache
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot reach OIDC identity provider to validate tokens.",
        ) from exc


# ── Token verification ─────────────────────────────────────────────────────────

def _verify_token(token: str, app_settings=settings) -> dict:
    """Decode and validate a Keycloak-issued JWT. Returns the claims dict."""
    from jose import JWTError, jwt

    jwks = _get_jwks(app_settings)
    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=app_settings.oidc_audience,
            issuer=app_settings.oidc_issuer,
            options={"verify_exp": True, "verify_nbf": True, "require_exp": True, "require_sub": True, "require_aud": True, "require_iss": True},
        )
        return claims
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _claims_to_principal(claims: dict) -> Principal:
    """Extract role from Keycloak realm_access.roles claim."""
    realm_roles = claims.get("realm_access", {}).get("roles", [])
    if "admin" in realm_roles:
        role = Role.admin
    elif "operator" in realm_roles:
        role = Role.operator
    else:
        role = Role.viewer
    return Principal(
        user_id=claims.get("sub", "unknown"),
        email=claims.get("email", ""),
        role=role,
    )


# ── Demo principal ─────────────────────────────────────────────────────────────

_DEMO_PRINCIPAL = Principal(
    user_id="demo-user",
    email="demo@localhost",
    role=Role.operator,
    demo=True,
)


# ── FastAPI dependencies ───────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Principal:
    """
    Resolve the authenticated principal from the request.

    In demo mode (local-only): returns the demo principal if no bearer token is provided.
    In production: always requires a valid bearer token.
    """
    # Prefer per-app settings stored in app.state (enables testing with overrides)
    app_settings = getattr(request.app.state, "settings", settings)

    if credentials and credentials.scheme.lower() == "bearer":
        claims = _verify_token(credentials.credentials, app_settings)
        return _claims_to_principal(claims)

    if app_settings.demo_mode:
        return _DEMO_PRINCIPAL

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(minimum_role: Role):
    """Factory: returns a dependency that enforces a minimum role level."""

    def _check(principal: Principal = Depends(get_current_principal)) -> Principal:
        if ROLE_HIERARCHY.get(principal.role, -1) < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role.value}' or higher is required.",
            )
        return principal

    return _check


require_viewer = require_role(Role.viewer)
require_operator = require_role(Role.operator)
require_admin = require_role(Role.admin)
