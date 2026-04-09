"""Callee resolution strategy protocol (per-language wiring)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from coderay.graph.lowering.callee_resolver import CalleeResolver
    from coderay.graph.lowering.name_bindings import FileNameBindings
    from coderay.parsing.base import BaseTreeSitterParser


class CalleeStrategy(Protocol):
    """Resolve raw callee text to qualified target strings."""

    def resolve(self, raw: str, scope_stack: list[str]) -> list[str]: ...


def default_callee_strategy(
    bindings: FileNameBindings, parser: BaseTreeSitterParser
) -> CalleeResolver:
    """Default Tree-sitter lowering (Python and JS/TS graph configs)."""
    from coderay.graph.lowering.callee_resolver import CalleeResolver

    return CalleeResolver(bindings, parser)
