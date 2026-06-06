"""Posts business logic.

Two patterns to notice:

1. Authorization is layered. The RLS policies in
   `supabase/migrations/` are the source of truth ("only authors can
   update / delete their own posts"). The service layer uses the
   user-scoped client so those policies actually fire. We do NOT
   re-check `if post.author_id == user.id` in code — that's exactly
   what RLS does, and a second check drifts the day the policies
   change.

2. PostgrestAPIError is mapped to HTTPError BEFORE leaving the
   service. Routers should never see a raw postgrest exception.
"""
from __future__ import annotations

from typing import Any

from postgrest.exceptions import APIError as PostgrestAPIError

from app.core.auth import CurrentUser
from app.core.exceptions import HTTPError
from app.core.supabase_client import get_supabase_as

LIST_LIMIT = 100
POST_COLUMNS = "id, title, body, author_id, created_at"


def _map_postgrest_error(err: PostgrestAPIError) -> HTTPError:
    """Map a PostgrestAPIError to an HTTPError with the right status,
    structured code, and `expected` flag.

    Status mapping:
        PGRST116                 → 404 (no rows / .single() returned 0)
        23505 (unique_violation) → 409 (collision the user can fix)
        23503 (fk_violation)     → 409 (related row missing)
        23502 (not_null)         → 400 (missing required field)
        23514 (check_violation)  → 422 (constraint says no)
        42501 (insufficient_priv)→ 403 (RLS refused — message
                                       deliberately vague to not
                                       leak the policy shape)
        PGRST301 (jwt expired)   → 401
        anything else            → 502 expected=True (upstream)
    """
    code = err.code
    msg = err.message or "Database error"
    if code == "PGRST116":
        return HTTPError("Not found", 404, code="ERR_DB_NOT_FOUND")
    if code == "23505":
        return HTTPError(msg, 409, code="ERR_DB_CONFLICT")
    if code == "23503":
        return HTTPError(msg, 409, code="ERR_DB_FK")
    if code == "23502":
        return HTTPError(msg, 400, code="ERR_DB_NOT_NULL")
    if code == "23514":
        return HTTPError(msg, 422, code="ERR_DB_CHECK")
    if code == "42501":
        return HTTPError("Forbidden", 403, code="ERR_DB_RLS")
    if code == "PGRST301":
        return HTTPError("Session expired", 401, code="ERR_AUTH_EXPIRED")
    return HTTPError(msg, 502, code="ERR_DB_UPSTREAM", expected=True)


def _unwrap_list(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, list):
        return rows
    return [rows]


def list_posts(user: CurrentUser) -> list[dict[str, Any]]:
    """RLS-scoped list. The policy "read for any signed-in user" lets
    everyone see everyone's posts; tighten the policy if you only want
    authors to see their own."""
    try:
        res = (
            get_supabase_as(user)
            .table("posts")
            .select(POST_COLUMNS)
            .order("created_at", desc=True)
            .limit(LIST_LIMIT)
            .execute()
        )
    except PostgrestAPIError as err:
        raise _map_postgrest_error(err) from err
    return _unwrap_list(res.data)


def create_post(user: CurrentUser, title: str, body: str) -> dict[str, Any]:
    """RLS policy "insert own" enforces that author_id == auth.uid().
    If a client lies about author_id here, PostgREST returns 403 and we
    surface it as 403 via the error mapping."""
    try:
        res = (
            get_supabase_as(user)
            .table("posts")
            .insert({"title": title, "body": body, "author_id": user.id})
            .execute()
        )
    except PostgrestAPIError as err:
        raise _map_postgrest_error(err) from err
    rows = _unwrap_list(res.data)
    if not rows:
        raise HTTPError("Insert returned no row", 502, expected=True)
    return rows[0]


def delete_post(user: CurrentUser, post_id: str) -> None:
    """RLS does the actual gate ("delete own"); when the policy refuses,
    the rowcount is 0, which we surface as 404 — same shape as a real
    not-found (no leak of "exists but not yours")."""
    try:
        res = (
            get_supabase_as(user)
            .table("posts")
            .delete()
            .eq("id", post_id)
            .execute()
        )
    except PostgrestAPIError as err:
        raise _map_postgrest_error(err) from err
    if not _unwrap_list(res.data):
        raise HTTPError("Not found", 404, code="ERR_NOT_FOUND")
