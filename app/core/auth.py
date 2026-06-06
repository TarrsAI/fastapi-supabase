"""Verify Supabase-issued JWTs from `Authorization: Bearer ...`.

Supabase signs every user JWT with the project's HS256 secret
(Settings → API → JWT Settings). The token's `aud` claim is fixed at
`"authenticated"` for any session-bearing user — that's the audience
we validate against.

This dep is the ONLY thing protecting routes; mount it via
`Depends(get_current_user)` on every authenticated endpoint, or via
`Depends(require_user)` if you want a stricter signature (raises if
absent vs. returns None).

A 401 with "Invalid or expired token" is most often a JWT-secret
mismatch — the secret in your .env must match the one in the Supabase
dashboard.
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.exceptions import HTTPError

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Decoded user from the Bearer JWT. `access_token` is preserved so
    `get_supabase_as(user)` can forward it to PostgREST and trigger
    RLS."""

    id: str
    email: str | None
    access_token: str


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Decode + validate the Bearer token. Raises 401 on missing /
    invalid / expired."""
    if creds is None or not creds.credentials:
        raise HTTPError(
            "Missing bearer token",
            status_code=401,
            code="ERR_AUTH_REQUIRED",
        )
    settings = get_settings()
    try:
        decoded = jwt.decode(
            creds.credentials,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPError(
            "Session expired",
            status_code=401,
            code="ERR_AUTH_EXPIRED",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPError(
            "Invalid token",
            status_code=401,
            code="ERR_AUTH_INVALID",
        ) from exc

    sub = decoded.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPError(
            "Token missing sub",
            status_code=401,
            code="ERR_AUTH_INVALID",
        )

    email = decoded.get("email")
    return CurrentUser(
        id=sub,
        email=email if isinstance(email, str) else None,
        access_token=creds.credentials,
    )
