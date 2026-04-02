"""Repository layer for Python fixture app."""

from __future__ import annotations

from app.domain.models import User
from app.infra.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Load users from in-memory storage."""

    def __init__(self) -> None:
        """Initialize with seeded records."""
        super().__init__()
        self.add(1, User(user_id=1, name="Ada", email="ada@example.com"))
        self.add(2, User(user_id=2, name="Linus", email="linus@example.com"))

    def get_by_id(self, user_id: int) -> User | None:
        """Return a user by ID."""
        return self.get(user_id)
