"""Controller layer for Python fixture app."""

from __future__ import annotations

from app.api.serializers.profile_serializer import to_http_response
from app.services.user_service import UserService


def get_user_profile(user_service: UserService, user_id: int) -> dict[str, object]:
    """Return HTTP response for profile endpoint."""
    profile = user_service.load_profile(user_id)
    return to_http_response(profile)


async def get_user_profile_async(
    user_service: UserService, user_id: int
) -> dict[str, object]:
    """Return async HTTP response for profile endpoint."""
    profile = await user_service.load_profile_async(user_id)
    return to_http_response(profile)
