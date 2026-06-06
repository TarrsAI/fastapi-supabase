from pydantic import BaseModel


class MeResponse(BaseModel):
    """Decoded session shape returned by GET /auth/me. Add server-side
    augmentation (role, plan tier, feature flags) here as your app
    grows — the frontend reads this to decide what to render without
    re-decoding the JWT itself."""

    id: str
    email: str | None
