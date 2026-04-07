"""Shared graph types (module index, project inputs for resolvers)."""

from __future__ import annotations

ModuleIndex = dict[str, str]


class ProjectIndex:
    """Per-build module path index and related inputs for resolvers.

    # TODO: build a project-level index to resolve cross-module graph edges.
    """

    def __init__(self, module_index: ModuleIndex) -> None:
        self.module_index = module_index
