"""FastAPI app entry point."""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, health, posts

load_dotenv()


def parse_origins(raw: str | None) -> list[str]:
    """Comma-separated CORS_ORIGINS env → list. Empty / unset → no CORS."""
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


# Explicit origins, comma-separated. Default empty (no cross-origin
# requests allowed). `allow_origins=["*"]` is incompatible with
# `allow_credentials=True` per CORS spec — browsers reject it — and
# is a phishing risk anyway. Set CORS_ORIGINS=https://yourapp.com.
ALLOWED_ORIGINS = parse_origins(os.environ.get("CORS_ORIGINS"))

app = FastAPI(title="My API", version="0.1.0")

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(health.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
