"""Expected chunk text bodies for Python fixture app chunking tests.

Uses triple-double-quoted literals; embedded docstring quote runs are backslash-escaped.
"""

# ruff: noqa: E501

MAIN_PY_MODULE_CHUNK = """\
\"\"\"Entry points for Python fixture app.\"\"\"
from __future__ import annotations
from pathlib import Path
from .api.controllers.user_controller import get_user_profile, get_user_profile_async
from .infra.repositories.user_repository import UserRepository
from .services.file_service import FileService
from .services.user_service import UserService
if __name__ == "__main__":
    root = Path(".")
    file_service = FileService()
    processed = file_service.process_payload({"root": str(root)})
    print(handle_request(1), processed)"""

MAIN_PY_HANDLE_REQUEST_CHUNK = """\
def handle_request(user_id: int) -> dict[str, object]:
    \"\"\"Handle a profile request.\"\"\"
    repository = UserRepository()
    service = UserService(repository)
    return get_user_profile(service, user_id)"""

MAIN_PY_HANDLE_REQUEST_ASYNC_CHUNK = """\
async def handle_request_async(user_id: int) -> dict[str, object]:
    \"\"\"Handle a profile request asynchronously.\"\"\"
    repository = UserRepository()
    service = UserService(repository)
    return await get_user_profile_async(service, user_id)"""

USER_SERVICE_PY_MODULE_CHUNK = """\
\"\"\"Service layer for Python fixture app.\"\"\"
from __future__ import annotations
from collections.abc import Callable
from typing import TypeVar
from app.services.internal.lazy_io import summarize_totals, to_json_line
from ..core.decorators import audit, trace
from ..infra.repositories.user_repository import UserRepository
from .file_service import FileService
from .internal.async_tasks import enrich_profile as ep
from .internal.formatters import format_public_name, format_score
T = TypeVar("T")"""

USER_SERVICE_PY_DECORATED_FORMATTER_CHUNK = """\
@audit
class DecoratedFormatter:
    \"\"\"Class-level decorated formatter.\"\"\"

    def format(self, value: str) -> str:
        \"\"\"Return formatted value.\"\"\"
        return value.upper()"""

USER_SERVICE_PY_FORMAT_CHUNK = """\
def format(self, value: str) -> str:
        \"\"\"Return formatted value.\"\"\"
        return value.upper()"""

USER_SERVICE_PY_DECORATED_MULTIPLIER_CHUNK = """\
@audit
@trace
def decorated_multiplier(a: int, b: int) -> int:
    \"\"\"Multiply two integers.\"\"\"
    return a * b"""

USER_SERVICE_PY_CHAIN_EMAIL_LOOKUP_CHUNK = """\
def chain_email_lookup(repo: UserRepository, user_id: int) -> str | None:
    \"\"\"Return email through chained method calls.\"\"\"
    user = repo.get_by_id(user_id)
    return user.to_dict().get("email") if user else None"""

USER_SERVICE_PY_USER_SERVICE_CHUNK = """\
class UserService:
    \"\"\"Orchestrate repository and formatter calls.\"\"\"

    def __init__(self, repository: UserRepository) -> None:
        \"\"\"Initialize with repository dependency.\"\"\"
        self._repository = repository
        self._file_service = FileService()
        self._decorated_formatter = DecoratedFormatter()

    def _build_formatter(self, suffix: str):
        \"\"\"Build a closure-based formatter.\"\"\"

        def formatter(value: str) -> str:
            \"\"\"Format a value with a suffix.\"\"\"
            return f"{value}{suffix}"

        return formatter

    @audit
    @trace
    def load_profile(self, user_id: int) -> dict[str, str] | None:
        \"\"\"Return profile payload for a user.\"\"\"
        user = self._repository.get_by_id(user_id)
        if user is None:
            return None
        project = self._build_formatter(" [fixture]")
        display_name = self._decorated_formatter.format(
            project(format_public_name(user))
        )
        profile = {"id": str(user.user_id), "display_name": display_name}
        profile["score"] = str(format_score(float(user.user_id)))
        profile["email"] = str(chain_email_lookup(self._repository, user_id))
        profile["multiplied"] = str(decorated_multiplier(user.user_id, 2))
        profile.update(
            {
                "totals": str(summarize_totals([user.user_id])),
                "processed": str(
                    self._file_service.process_payload({"id": user.user_id})
                ),
            }
        )
        profile["serialized"] = to_json_line(profile)
        return profile

    async def load_profile_async(self, user_id: int) -> dict[str, str] | None:
        \"\"\"Return asynchronously enriched profile.\"\"\"
        profile = self.load_profile(user_id)
        if profile is None:
            return None
        return await ep(profile)"""

USER_SERVICE_PY_INIT_CHUNK = """\
def __init__(self, repository: UserRepository) -> None:
        \"\"\"Initialize with repository dependency.\"\"\"
        self._repository = repository
        self._file_service = FileService()
        self._decorated_formatter = DecoratedFormatter()"""

USER_SERVICE_PY_BUILD_FORMATTER_CHUNK = """\
def _build_formatter(self, suffix: str):
        \"\"\"Build a closure-based formatter.\"\"\"

        def formatter(value: str) -> str:
            \"\"\"Format a value with a suffix.\"\"\"
            return f"{value}{suffix}"

        return formatter"""

USER_SERVICE_PY_FORMATTER_CHUNK = """\
def formatter(value: str) -> str:
            \"\"\"Format a value with a suffix.\"\"\"
            return f"{value}{suffix}\""""

USER_SERVICE_PY_LOAD_PROFILE_CHUNK = """\
@audit
    @trace
    def load_profile(self, user_id: int) -> dict[str, str] | None:
        \"\"\"Return profile payload for a user.\"\"\"
        user = self._repository.get_by_id(user_id)
        if user is None:
            return None
        project = self._build_formatter(" [fixture]")
        display_name = self._decorated_formatter.format(
            project(format_public_name(user))
        )
        profile = {"id": str(user.user_id), "display_name": display_name}
        profile["score"] = str(format_score(float(user.user_id)))
        profile["email"] = str(chain_email_lookup(self._repository, user_id))
        profile["multiplied"] = str(decorated_multiplier(user.user_id, 2))
        profile.update(
            {
                "totals": str(summarize_totals([user.user_id])),
                "processed": str(
                    self._file_service.process_payload({"id": user.user_id})
                ),
            }
        )
        profile["serialized"] = to_json_line(profile)
        return profile"""

USER_SERVICE_PY_LOAD_PROFILE_ASYNC_CHUNK = """\
async def load_profile_async(self, user_id: int) -> dict[str, str] | None:
        \"\"\"Return asynchronously enriched profile.\"\"\"
        profile = self.load_profile(user_id)
        if profile is None:
            return None
        return await ep(profile)"""

USER_SERVICE_PY_GET_FORMATTER_CHUNK = """\
def get_formatter() -> Callable[[str], str]:
    \"\"\"Return closure-based formatter callable.\"\"\"
    service = UserService(UserRepository())
    return service._build_formatter(" [public]")"""
