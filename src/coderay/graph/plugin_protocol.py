"""Language graph plugin and resolution contracts."""

from __future__ import annotations

from typing import Protocol

from coderay.core.models import GraphEdge, GraphNode
from coderay.graph.facts import Fact
from coderay.parsing.base import ParserContext

ModuleIndex = dict[str, str]


class ProjectIndex:
    """Per-build module path index and related inputs for resolvers."""

    def __init__(self, module_index: ModuleIndex) -> None:
        self.module_index = module_index


class LanguageGraphPlugin(Protocol):
    """Parse is shared; plugin lowers CST to facts and emits graph edges."""

    language_id: str

    def extract_facts(
        self,
        ctx: ParserContext,
        *,
        excluded_modules: frozenset[str],
        module_index: ModuleIndex,
    ) -> list[Fact]:
        """Lower CST to facts (file-local + resolved names like current extractor)."""

    def resolve_facts(
        self,
        facts: list[Fact],
        project: ProjectIndex,
    ) -> list[Fact]:
        """Patch facts before emit using project layout (aliases, roots).

        Return facts unchanged if extract_facts already resolved via FileContext.
        """

    def emit(
        self,
        facts: list[Fact],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Facts to storage model."""


class ResolutionBackend(Protocol):
    """Pluggable resolution for imports/calls (e.g. tsconfig paths later)."""

    language_id: str

    def resolve(
        self,
        facts: list[Fact],
        project: ProjectIndex,
    ) -> list[Fact]:
        """Return updated facts."""
