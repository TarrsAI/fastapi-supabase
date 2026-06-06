"""Streaming chat route.

Demonstrates the FastAPI single-process agent pattern: route handler
returns a StreamingResponse wrapping an async generator from
`app.agents.simple.run_agent`. No separate worker container needed —
the agent runs in this same uvicorn process, in the same coroutine
that handles the HTTP request.

Note that this route does NOT return the JSON envelope (other routes
do). SSE is a different content-type by design; the envelope only
makes sense for one-shot JSON responses.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.simple import run_agent
from app.core.auth import CurrentUser, get_current_user

router = APIRouter()


class ChatIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=8_000)


@router.post("/chat")
async def chat(
    payload: ChatIn,
    _user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        run_agent(payload.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
