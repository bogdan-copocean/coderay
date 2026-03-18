"""Handler mixins for graph extraction.

Each mixin provides handlers for a specific AST node category. The main
parser (GraphTreeSitterParser) composes them via multiple inheritance.
Mixin order: Import, TypeResolution, Definition, Assignment, Call, BaseParser.
TypeResolution must come before Definition and Assignment (they use its methods).
"""

from coderay.graph._handlers.assignments import AssignmentHandlerMixin
from coderay.graph._handlers.calls import CallHandlerMixin
from coderay.graph._handlers.definitions import DefinitionHandlerMixin
from coderay.graph._handlers.imports import ImportHandlerMixin
from coderay.graph._handlers.type_resolution import TypeResolutionMixin

__all__ = [
    "AssignmentHandlerMixin",
    "CallHandlerMixin",
    "DefinitionHandlerMixin",
    "ImportHandlerMixin",
    "TypeResolutionMixin",
]
