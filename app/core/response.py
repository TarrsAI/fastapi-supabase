"""Response envelope used by every router.

Stable shape on the wire means the frontend never needs to special-case
"success with data" vs "error with message" — there's exactly one parse
path:

    {
        "success": true | false,
        "message": str | None,
        "data": T | None,
        "code": str | None       # structured error code, only on errors
    }
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Single response shape. Used both at success (via `ok()`) and on
    error (via the exception handler in `core.exceptions`)."""

    success: bool
    message: str | None = None
    data: T | None = None
    code: str | None = None


def ok(data: T | None = None, message: str | None = None) -> Envelope[T]:
    """Wrap a success payload."""
    return Envelope[T](success=True, message=message, data=data)
