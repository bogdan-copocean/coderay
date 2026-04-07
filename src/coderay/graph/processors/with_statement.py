"""With-statement lowering (context manager instance typing)."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead
from coderay.graph.processors.type_lookup import TypeLookup
from coderay.parsing.base import TSNode


class WithStatementProcessor:
    """No-op for languages without with-statement typing."""

    def __init__(
        self,
        session: LoweringSession,
        syntax: SyntaxRead,
        type_lookup: TypeLookup,
    ) -> None:
        self._session = session
        self._syntax = syntax
        self._type_lookup = type_lookup

    def handle(self, node: TSNode, *, scope_stack: list[str]) -> None:
        """Process with node; default is no-op."""
        del node, scope_stack
