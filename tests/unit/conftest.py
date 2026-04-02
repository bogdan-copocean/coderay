from __future__ import annotations

from pathlib import Path

import pytest

UNIT_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items):
    """Tag collected unit tests as unit."""
    for item in items:
        item_path = Path(str(item.fspath)).resolve()
        if not item_path.is_relative_to(UNIT_DIR):
            continue
        if item.get_closest_marker("unit") is None:
            item.add_marker(pytest.mark.unit)
