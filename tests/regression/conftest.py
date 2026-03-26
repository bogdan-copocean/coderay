from __future__ import annotations

from pathlib import Path

import pytest

REGRESSION_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items):
    """Tag collected tests under this package as regression."""
    for item in items:
        item_path = Path(str(item.fspath)).resolve()
        if not item_path.is_relative_to(REGRESSION_DIR):
            continue
        if item.get_closest_marker("regression") is None:
            item.add_marker(pytest.mark.regression)
