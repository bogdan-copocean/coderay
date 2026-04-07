"""Caller id from lexical scope (module vs qualified symbol)."""

from __future__ import annotations

from coderay.graph.lowering.session import LoweringSession
from coderay.graph.lowering.syntax_read import SyntaxRead


def caller_id_for_scope(
    session: LoweringSession,
    syntax: SyntaxRead,
    scope_stack: list[str],
) -> str:
    """Return graph node id for the current scope_stack."""
    fp = syntax.file_path
    if scope_stack:
        return f"{fp}::{'.'.join(scope_stack)}"
    return session.module_id
