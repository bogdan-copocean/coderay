"""Lazy import helpers for Python fixture app."""

from __future__ import annotations

from collections import defaultdict as dd
from typing import Any


def to_json_line(payload: dict[str, Any]) -> str:
    """Serialize payload with a lazy import."""
    import json

    return json.dumps(payload, sort_keys=True)


def summarize_totals(values: list[int]) -> dict[str, int]:
    """Build grouped totals with local alias imports."""
    from itertools import chain as ch

    doubled = [v * 2 for v in values]
    grouped: dict[str, int] = dd(int)
    for value in ch(values, doubled):
        grouped["total"] += value
    return grouped
