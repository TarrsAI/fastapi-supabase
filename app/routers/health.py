from fastapi import APIRouter

from app.core.response import Envelope, ok

router = APIRouter()


@router.get("/health", response_model=Envelope[dict[str, str]])
def health() -> Envelope[dict[str, str]]:
    return ok({"status": "ok"})
