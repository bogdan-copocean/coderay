"""Async helpers for Python fixture app."""

from __future__ import annotations

import asyncio


async def enrich_profile(profile: dict[str, str]) -> dict[str, str]:
    """Enrich profile payload asynchronously."""
    await asyncio.sleep(0)
    return {**profile, "source": "async"}
