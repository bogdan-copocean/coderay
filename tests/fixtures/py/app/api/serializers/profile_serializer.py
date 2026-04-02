"""Serializer utilities for Python fixture app."""

from __future__ import annotations


def to_http_response(profile: dict[str, str] | None) -> dict[str, object]:
    """Convert a profile payload to HTTP response shape."""
    if profile is None:
        return {"status": 404, "body": {"error": "not_found"}}
    return {"status": 200, "body": profile}
