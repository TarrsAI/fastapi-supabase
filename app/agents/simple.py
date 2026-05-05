"""Example streaming agent using the Anthropic SDK.

Single-process pattern: this module's `run_agent()` is an async
generator that yields SSE-formatted strings. A FastAPI route wraps
it in StreamingResponse — no separate worker container, no IPC. The
backend route handler IS the agent invocation.

Replace with LangChain / your own logic as needed. Pattern is the
same: define an async generator, yield SSE frames.
"""
import json
import os
from collections.abc import AsyncGenerator
from typing import Any

import httpx


ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"  # bump as needed


async def run_agent(prompt: str) -> AsyncGenerator[str, None]:
    """Stream Anthropic's response token-by-token as SSE frames.

    Yield format follows the Server-Sent Events spec:
        data: {json}\n\n

    Frontend (any EventSource-aware client) reads these as discrete
    events. Each frame here is one delta chunk plus a final `done`
    sentinel.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        yield _frame({"error": "ANTHROPIC_API_KEY not configured"})
        return

    payload: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": 1024,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            ANTHROPIC_API,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        ) as res:
            if res.status_code != 200:
                body = await res.aread()
                yield _frame(
                    {"error": f"upstream {res.status_code}: {body.decode()[:200]}"},
                )
                return
            async for line in res.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if not data:
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                # Forward token deltas as compact frames.
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        yield _frame({"text": text})
                elif event.get("type") == "message_stop":
                    yield _frame({"done": True})


def _frame(obj: dict[str, Any]) -> str:
    """Encode a dict as a single SSE event."""
    return f"data: {json.dumps(obj)}\n\n"
