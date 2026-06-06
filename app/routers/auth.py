"""Auth router intentionally minimal.

Sign-in / sign-up are NOT proxied through this API — the frontend talks
to Supabase Auth directly using `supabase-js` (or `@supabase/ssr` in
Next.js). Putting register/login here would double-hop every auth call
and force this API to hold password material it doesn't need to see.

What lives here:
    GET /api/auth/me — surfaces whatever `get_current_user` decoded
    from the Bearer token. Frontends use this to confirm a session is
    still valid against the API's view of the world, and to fetch any
    server-side profile augmentation (role, plan tier, feature flags)
    that the JWT alone doesn't carry.
"""
from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.response import Envelope, ok
from app.schemas.auth import MeResponse

router = APIRouter()


@router.get("/auth/me", response_model=Envelope[MeResponse])
def me(user: CurrentUser = Depends(get_current_user)) -> Envelope[MeResponse]:
    return ok(MeResponse(id=user.id, email=user.email))
