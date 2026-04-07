"""Import CST lowering to IMPORTS facts and FileContext bindings."""

from __future__ import annotations

from typing import Protocol

from coderay.graph.facts import ImportsEdge
from coderay.graph.lowering.session import LoweringSession
from coderay.parsing.base import TSNode


class ImportProcessor(Protocol):
    """Single import node handler."""

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> str | None:
        """Lower one import node; return None (imports never push scope)."""


def append_import_edge(session: LoweringSession, source: str, target: str) -> None:
    """Append an IMPORTS fact."""
    session.facts.add(ImportsEdge(source_id=source, target=target))
