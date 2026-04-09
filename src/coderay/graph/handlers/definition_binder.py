"""Definition binding: register function/class names into bindings (Pass 1)."""

from __future__ import annotations

from coderay.core.models import NodeKind
from coderay.graph.lowering.cst_helpers import node_id
from coderay.graph.lowering.name_bindings import FileNameBindings
from coderay.parsing.base import BaseTreeSitterParser, TSNode


class DefinitionBinder:
    """Register a function or class name into ``FileNameBindings`` (Pass 1).

    Appends the definition name to ``scope_stack`` so the DFS recurses into
    the body under the correct scope.  No facts emitted.
    """

    def __init__(self, module_id: str, kind: NodeKind) -> None:
        self._module_id = module_id
        self._kind = kind

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None:
        name = parser.identifier_from_node(node)
        if not name:
            return
        # With name: (file, scope_stack, name) -> file::scope.name (see node_id).
        nid = node_id(parser.file_path, scope_stack, name)
        qualified = ".".join([*scope_stack, name])
        if self._kind == NodeKind.CLASS:
            # Class: short name key -> nid.
            bindings.register_definition(name, nid, is_class=True)
        else:
            # Nested def: qualified key; module scope: short name.
            bindings.register_definition(qualified if scope_stack else name, nid)
        scope_stack.append(name)
