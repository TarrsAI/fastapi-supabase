from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.supabase import supabase

router = APIRouter()


class PostIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class Post(BaseModel):
    id: str
    title: str
    body: str
    author_id: str
    created_at: str


@router.get("/posts", response_model=list[Post])
async def list_posts(_user: CurrentUser = Depends(get_current_user)) -> list:
    return await supabase.select(
        "posts",
        columns="id, title, body, author_id, created_at",
        order="created_at.desc",
        limit=100,
    )


@router.post("/posts", response_model=Post, status_code=201)
async def create_post(
    payload: PostIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    return await supabase.insert(
        "posts",
        {
            "title": payload.title,
            "body": payload.body,
            "author_id": user.id,
        },
    )
