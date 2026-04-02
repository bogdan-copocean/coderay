"""Shared handler mixins for graph fact extraction."""

from coderay.graph.plugins.base.handlers.assignments import AssignmentMixin
from coderay.graph.plugins.base.handlers.calls import CallMixin
from coderay.graph.plugins.base.handlers.definitions import DefinitionMixin
from coderay.graph.plugins.base.handlers.type_resolution import TypeResolutionMixin

__all__ = [
    "AssignmentMixin",
    "CallMixin",
    "DefinitionMixin",
    "TypeResolutionMixin",
]
