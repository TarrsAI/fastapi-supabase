"""Two Supabase clients, two use cases.

`get_supabase_admin()`  — service-role key. Bypasses RLS. Use ONLY for
server-owned mutations where the auth check is enforced in code (after
`get_current_user`) and the action is allowed regardless of the caller
(system jobs, admin endpoints, materialized views).

`get_supabase_as(user)` — anon key + the caller's access token. RLS is
fully in effect. Use this for everything that maps 1:1 to a user action
(read their own posts, create a post under their user_id). Lets the
database enforce the auth rule and stops "I forgot the .eq('user_id',
user.id) filter" bugs at the schema level.

Rule of thumb: reach for `get_supabase_as` first. Only fall back to
`get_supabase_admin` when the rule you want can't be expressed as a
RLS policy.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.exceptions import HTTPError
from supabase import Client, create_client


@lru_cache
def get_supabase_admin() -> Client:
    """Singleton service-role client. Cached because supabase-py reuses
    its underlying httpx pool — making a fresh client per request would
    burn TCP connections needlessly."""
    settings = get_settings()
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def get_supabase_as(user: CurrentUser) -> Client:
    """Per-request user-scoped client. The user's Bearer token rides
    along on every PostgREST call, so RLS sees `auth.uid()` and policies
    fire as if the user themselves were querying.

    Requires SUPABASE_ANON_KEY in env — if absent we raise immediately
    with a clear message rather than silently fall back to the admin
    client (which would defeat RLS).
    """
    settings = get_settings()
    if not settings.SUPABASE_ANON_KEY:
        raise HTTPError(
            "SUPABASE_ANON_KEY is required for RLS-scoped queries — "
            "set it from Supabase project Settings → API → anon (public).",
            status_code=500,
            code="ERR_CONFIG",
        )
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    # supabase-py exposes the underlying postgrest client; we set the
    # auth header on it so every from(...) call carries the user's JWT.
    # `postgrest.auth` is the supported way to inject the bearer token.
    client.postgrest.auth(user.access_token)
    return client
