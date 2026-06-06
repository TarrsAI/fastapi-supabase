# FastAPI + Supabase API starter

A Tarrs-ready Python + FastAPI backend that talks to Supabase via
`supabase-py`, with the same architectural discipline as the
`express-supabase` template (controller / service / data, response
envelope, structured errors, request observability, RLS-first
authorization).

If you want a different ORM or your own Postgres, see
`fastapi-postgres` (coming) or pair with `nextjs-standalone`.

## What's included

- FastAPI + Uvicorn (async, port 8080)
- **`supabase-py`** with two clients (`get_supabase_admin`,
  `get_supabase_as(user)`) — admin is for server-owned ops, the
  user-scoped one triggers RLS
- **Controller (router) → Service → supabase-py** layering — routers
  stay thin, business logic lives in `app/services/`
- **Response envelope**: every JSON endpoint returns
  `{success, message, data, code?}` via `app.core.response.Envelope[T]`
- **Structured errors**: `HTTPError(status_code, code, expected)`; the
  `expected=True` flag downgrades known upstream 5xx to WARN logs +
  forwards the message to the client
- **PostgrestAPIError mapping**: `_map_postgrest_error()` turns
  postgrest exceptions into `HTTPError` with the right code
  (`PGRST116 → 404`, `23505 → 409`, `42501 → 403`, unknown → 502 expected)
- **Request observability**: `structlog` + a middleware that tags every
  request with a short `request_id` via `contextvars` — every
  `get_logger().info(...)` inside the handler picks it up automatically;
  emits START / END / SLOW / ERROR lines
- `pydantic-settings`-validated config (fails at boot, not first request)
- Bearer JWT verification via `PyJWT` (Supabase HS256 + `audience="authenticated"`)
- Sample `/api/posts` resource: GET list + POST create + DELETE — all RLS-driven, no in-code `author_id` check
- Streaming `/api/chat` SSE agent (Anthropic) — kept from the previous
  version because the single-process agent pattern is genuinely useful
- OpenAPI docs at `/docs`

## Layout

```
app/
  main.py                # FastAPI app + middleware + handler wiring
  core/
    config.py            # Settings via pydantic-settings
    response.py          # Envelope[T] + ok()
    exceptions.py        # HTTPError + global handlers
    logging.py           # structlog + request_id middleware
    auth.py              # Bearer JWT verify + CurrentUser dep
    supabase_client.py   # admin + user-scoped clients
  schemas/               # Pydantic v2 request / response models
  services/              # business logic (only layer that touches supabase-py)
  routers/               # thin HTTP shell
  agents/                # streaming agent example
supabase/
  migrations/            # raw SQL with RLS policies
```

See `CLAUDE.md` for the architectural rules the AI scaffolding new
endpoints must follow.

## RLS-first authorization

Supabase RLS policies are the source of truth. The service layer uses
`get_supabase_as(user)` so those policies actually fire on every
read/write. We deliberately do NOT re-check `if post.author_id ==
user.id` in service code — that's exactly what the policy does, and a
duplicated check drifts the day the policy changes.

When you DO write an in-code check, use `get_supabase_admin()` (which
bypasses RLS) and explain in a comment why RLS isn't enough.

## Auth model

Sign-in / sign-up is NOT proxied through this API. The frontend talks
to Supabase Auth directly (`@supabase/ssr` in Next.js, `supabase-js`
elsewhere). The frontend sends `Authorization: Bearer <access_token>`
on every API call here; `get_current_user` decodes + verifies the JWT
and stashes the raw token on `CurrentUser.access_token` so
`get_supabase_as(user)` can forward it to PostgREST.

`GET /api/auth/me` is the only auth-shaped endpoint on this server,
returning the decoded JWT plus any server-side augmentation you choose
to add (role, plan tier, feature flags).

## How Tarrs uses this

Tarrs auto-injects:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `ANTHROPIC_API_KEY` (for the chat example)

Sandbox runs `uvicorn` on port 8080 (Tarrs convention: frontend :3000,
Node backend :4000, Python/agent :8080).

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# fill the SUPABASE_* values + ANTHROPIC_API_KEY (for /api/chat)
uvicorn app.main:app --reload --port 8080
```

Apply the migration first:

```bash
supabase link --project-ref <ref>
supabase db push
```

OpenAPI: http://localhost:8080/docs

## Adding a new resource — the recipe

See `CLAUDE.md`. Six steps: migration → push → schema → service →
router → wire.

## Streaming agent pattern

`/api/chat` shows the **single-process agent pattern** — async generator
producing SSE frames, wrapped in a `StreamingResponse`. No separate
worker container, no IPC. Replace `app/agents/simple.py` with LangChain
/ your own logic; the route handler stays the same.

## CORS

Set `CORS_ORIGINS=https://yourapp.com,https://staging.yourapp.com`
(comma-separated) before exposing this API to a different-origin
frontend. Empty = no cross-origin allowed. Dev (NODE_ENV != production)
auto-allows localhost regardless.

## Endpoints

- `GET    /api/health`           — liveness (envelope)
- `GET    /api/auth/me`          — decoded session (envelope)
- `GET    /api/posts`            — list (RLS-scoped, envelope)
- `POST   /api/posts`            — create (RLS-scoped, envelope)
- `DELETE /api/posts/:id`        — delete (RLS-scoped, 404 if not yours)
- `POST   /api/chat`             — SSE stream from Anthropic (NOT envelope)
