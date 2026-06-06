from fastapi import APIRouter, Depends, Path

from app.core.auth import CurrentUser, get_current_user
from app.core.response import Envelope, ok
from app.schemas.post import PostCreate, PostRead
from app.services import posts as posts_service

router = APIRouter()


@router.get("/posts", response_model=Envelope[list[PostRead]])
def list_posts(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[list[PostRead]]:
    rows = posts_service.list_posts(user)
    return ok([PostRead(**r) for r in rows])


@router.post("/posts", response_model=Envelope[PostRead], status_code=201)
def create_post(
    payload: PostCreate,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[PostRead]:
    row = posts_service.create_post(user, payload.title, payload.body)
    return ok(PostRead(**row), message="Post created")


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: str = Path(min_length=36, max_length=36),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    posts_service.delete_post(user, post_id)
