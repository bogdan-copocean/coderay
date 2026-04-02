"""Entry points for Python fixture app."""

from __future__ import annotations

from pathlib import Path

from .api.controllers.user_controller import get_user_profile, get_user_profile_async
from .infra.repositories.user_repository import UserRepository
from .services.file_service import FileService
from .services.user_service import UserService


def handle_request(user_id: int) -> dict[str, object]:
    """Handle a profile request."""
    repository = UserRepository()
    service = UserService(repository)
    return get_user_profile(service, user_id)


async def handle_request_async(user_id: int) -> dict[str, object]:
    """Handle a profile request asynchronously."""
    repository = UserRepository()
    service = UserService(repository)
    return await get_user_profile_async(service, user_id)


if __name__ == "__main__":
    root = Path(".")
    file_service = FileService()
    processed = file_service.process_payload({"root": str(root)})
    print(handle_request(1), processed)
