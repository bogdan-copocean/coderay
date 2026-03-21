"""Concrete resolution backends (scaffold for future tsconfig paths, etc.)."""

from __future__ import annotations

from coderay.graph.facts import Fact
from coderay.graph.plugin_protocol import ProjectIndex


class JsTsResolutionBackend:
    """Placeholder until path-alias / package resolution exists."""

    language_id = "javascript"

    def resolve(self, facts: list[Fact], project: ProjectIndex) -> list[Fact]:
        del project
        return facts
