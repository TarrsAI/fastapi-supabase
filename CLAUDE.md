# Architecture (locked)

When you add or change code in this repo, **follow these rules**. They
are not preferences — they are how this template is supposed to work.
Deviating is a bug.

## Stack — pinned

| Concern | Choice | Don't substitute |
|---|---|---|
| Data access | **`supabase-py`** (PostgREST client) | No SQLAlchemy / SQLModel / asyncpg / psycopg. The data layer is `supabase-py` because this template's value-add is the Supabase platform (RLS, realtime, storage). ORM-on-top defeats that. |
| Authorization | **RLS policies in `supabase/migrations/`** | Do NOT add `if post.author_id == user.id` checks in service code. The policy is the source of truth; an in-code duplicate drifts the day the policy changes. |
| Auth (Bearer JWT) | `PyJWT` (HS256, audience `"authenticated"`) | Don't switch to python-jose or write a custom verifier. |
| Migrations | `supabase/migrations/*.sql` via Supabase CLI | Don't add Alembic / dbmate. |
| Validation | Pydantic v2 (`schemas/`) | Don't add marshmallow / cattrs. |
| Response shape | `Envelope[T]` from `app.core.response` | Every JSON endpoint returns `Envelope[T]`. SSE / file-download endpoints are the only exception. |
| Errors | `HTTPError(status_code, code, expected)` from `app.core.exceptions` | Don't raise FastAPI's `HTTPException` directly from service code — the global handler maps `HTTPError` into the envelope with `code` + `expected` semantics. |
| Logging | `structlog` via `app.core.logging.get_logger()` | Don't use stdlib `logging` directly; you'll lose `request_id` auto-binding. |
| Settings | `app.core.config.get_settings()` | Don't read `os.environ` ad-hoc — go through Settings so a missing var crashes the process at boot, not at the first request. |

## Folder layout — what each layer is for

```
app/
  main.py              FastAPI app + middleware + exception handlers.
                       Nothing business-logic here.
  core/
    config.py          Settings (pydantic-settings). Boot-time validation.
    response.py        Envelope[T] + ok() helper.
    exceptions.py      HTTPError + global handlers.
    logging.py         structlog + request_id middleware.
    auth.py            Bearer JWT verify; `get_current_user` dep.
    supabase_client.py Two clients:
                         get_supabase_admin() — service role, bypasses RLS
                         get_supabase_as(user) — anon + user JWT, RLS enforced
  schemas/             Pydantic v2 request / response models. NO business
                       logic. NO imports from `services/` or `routers/`.
  services/            Business logic. The ONLY layer that touches
                       supabase-py. Throws HTTPError on failure (mapped
                       from PostgrestAPIError via _map_postgrest_error).
                       Takes CurrentUser + plain args; returns dicts /
                       plain values. NO `Request`, NO `FormData`, NO
                       FastAPI types here.
  routers/             Thin HTTP shell. Parse / validate via Pydantic,
                       call the service, wrap in `ok(...)`. NO direct
                       supabase-py calls. NO ownership checks (RLS owns
                       those).
  agents/              Streaming agent helpers (e.g. Anthropic SSE).
                       Optional; delete if your app doesn't need them.
supabase/
  migrations/          Raw SQL — table DDL + RLS policies. Apply via
                       `supabase db push`. This is the schema source of
                       truth; no auto-generated migrations.
```

## The 5-file recipe — adding a new resource

1. `supabase/migrations/00X_<thing>.sql` — table + RLS policies. The
   policies are the authoritative auth check; write them carefully.
2. `supabase db push` — apply.
3. `app/schemas/<thing>.py` — Pydantic `Create` / `Read` models.
4. `app/services/<thing>.py` — `list_<things>(user)`,
   `create_<thing>(user, ...)`, `delete_<thing>(user, id)`. All use
   `get_supabase_as(user)` so RLS fires. Map PostgrestAPIError to
   HTTPError via the same `_map_postgrest_error` pattern as `posts.py`.
5. `app/routers/<thing>.py` — Depends(`get_current_user`), call service,
   `ok(...)`.
6. Wire the router in `app/main.py` with `app.include_router(...)`.

## When to use `get_supabase_admin()` vs `get_supabase_as(user)`

**Default**: `get_supabase_as(user)`. The user's JWT rides through
PostgREST and `auth.uid()` resolves correctly; RLS does its job.

**Reach for admin (service-role) ONLY when**:
1. The operation has no user context (cron sweepers, system-only
   inserts triggered by a webhook).
2. The rule can't be expressed as an RLS policy (e.g. "any user with
   `role='admin'` can read everything" when role isn't a column on
   the target table).

When you DO use admin, write the in-code auth check **directly above**
the admin call, with a comment explaining why RLS isn't enough:

```python
# Admin-only: list raw counts across all projects. RLS can't express
# "any admin sees everything" because role isn't a column on posts.
if not user_is_admin(current_user):
    raise HTTPError("Admin only", 403)
res = get_supabase_admin().table("posts").select(...).execute()
```

## Error handling — `expected=True` semantics

When a 5xx is your fault → raise `HTTPError(..., 500)` (no `expected`).
The handler logs at ERROR with a stack and the client sees
`"Internal error"`.

When a 5xx is the upstream's fault → raise `HTTPError(..., 502,
expected=True)`. The handler logs at WARNING (no stack spam) and
forwards your message to the client. Use this for:
- Supabase 502 / 504 (PostgREST unreachable)
- Anthropic / OpenAI / Stripe upstream failures
- "Project paused" or other known states

`_map_postgrest_error` already does this for unknown postgrest codes.
You don't need to think about it for DB errors — only for OTHER
upstream calls you make.

## What NOT to do

- ❌ Don't add SQLAlchemy / SQLModel — use supabase-py.
- ❌ Don't re-check ownership in service code — RLS owns it.
- ❌ Don't call `supabase-py` from a router — go through `services/`.
- ❌ Don't raise FastAPI `HTTPException` from `services/` — use `HTTPError`.
- ❌ Don't `print()` or `logging.info(...)` — use `get_logger().info(...)`.
- ❌ Don't return raw dicts from routers — wrap in `ok(...)`.
- ❌ Don't read `os.environ` directly — go through `get_settings()`.
- ❌ Don't bypass `get_current_user` with a manual JWT decode in a router.
- ❌ Don't add Alembic. Migrations are SQL files.

## What to do when in doubt

Read `app/routers/posts.py` + `app/services/posts.py` —  they're the
canonical example.
