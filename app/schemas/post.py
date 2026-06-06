from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    """Inbound shape for POST /api/posts. Length caps deliberately
    aggressive — pasted-in dumps belong in storage, not the posts row."""

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class PostRead(BaseModel):
    """Outbound shape. Mirrors the columns selected in
    `services/posts.py:POST_COLUMNS` — keep both in lockstep when adding
    fields so a renamed column doesn't fail silently as a 200 with a
    missing key."""

    id: str
    title: str
    body: str
    author_id: str
    created_at: datetime
