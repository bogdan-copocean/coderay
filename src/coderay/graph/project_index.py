"""Repo-wide module path index for graph lowering (Python layout first)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProjectIndex(Protocol):
    """Maps logical module names to indexed file paths."""

    def resolve_module_to_file(self, mod_name: str) -> str | None:
        """Return file path for a dotted module name if indexed."""
        ...

    def indexed_file_paths(self) -> set[str]:
        """Return all file paths participating in the index."""
        ...


@dataclass
class PythonModuleIndex:
    """Dotted Python-style module name -> first seen file path."""

    _dotted_to_file: dict[str, str]

    def resolve_module_to_file(self, mod_name: str) -> str | None:
        return self._dotted_to_file.get(mod_name)

    def indexed_file_paths(self) -> set[str]:
        return set(self._dotted_to_file.values())


class EmptyProjectIndex:
    """No cross-file module resolution."""

    def resolve_module_to_file(self, mod_name: str) -> str | None:
        del mod_name
        return None

    def indexed_file_paths(self) -> set[str]:
        return set()
