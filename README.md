# FastAPI + Supabase API starter

A Tarrs-ready Python + FastAPI backend that talks to Supabase Postgres.
Async-first, OpenAPI auto-generated, ML/data-friendly.

## What's included

- FastAPI + Uvicorn (async, port 3000)
- httpx async Supabase REST client (no heavy `psycopg2` setup needed)
- JWT verification middleware (PyJWT)
- Pydantic v2 input validation
- Example `/api/posts` resource: list + create
- **Example `/api/chat` streaming agent** — Anthropic SSE in a single
  uvicorn process. No separate worker or multi-container; the route
  handler IS the agent invocation (async generator → StreamingResponse).
- OpenAPI docs at `/docs`

## How Tarrs uses this

Tarrs auto-injects:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (server uses this to bypass RLS)
- `SUPABASE_JWT_SECRET` (for verifying user JWTs from frontend)

For the chat example, also set `ANTHROPIC_API_KEY` via
Tarrs Settings → Sandbox secrets.

Sandbox runs `uvicorn` on port 3000.

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 3000
```

Apply the migration in `supabase/migrations/001_posts.sql` first.

OpenAPI: http://localhost:3000/docs

## Deploy

For prod, host on Tarrs sandbox (persistent mode) or Fly.io / Render.
Pair with `nextjs-supabase` on Vercel as the frontend.

## Endpoints

- `GET  /api/health`
- `GET  /api/posts`             — list (auth)
- `POST /api/posts`             — create (auth, validated)
- `POST /api/chat`              — SSE stream from Anthropic (auth)

## Agent pattern

The `/api/chat` example shows the **single-process agent pattern**:

```
HTTP request → FastAPI route → returns StreamingResponse(async generator)
                                                ↑
                                     `app/agents/simple.py`
                                     calls Anthropic / LangChain inline
```

No separate worker container, no IPC, no concurrently. The agent runs
in the same coroutine as the HTTP request. For more complex agents
(LangChain, multi-step tool use), keep the same pattern: define an
`async def run_agent(...) -> AsyncGenerator[str, None]` and yield SSE
frames as the work progresses.

## CORS

Set `CORS_ORIGINS=https://yourapp.com,https://staging.yourapp.com`
(comma-separated) before exposing this API to a different-origin
frontend. Empty = no cross-origin allowed.
