"""Formatter helpers for Python fixture app."""

from __future__ import annotations

import math as m

from ...domain.models import User


def format_public_name(user: User) -> str:
    """Return display name for a user."""
    return f"{user.name} <{user.email}>"


def format_score(raw: float) -> float:
    """Round a score using aliased math import."""
    area = m.pi * raw**2
    return round(area, 2)
