"""Language-agnostic graph facts before emission to GraphNode/GraphEdge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from coderay.core.models import NodeKind

__all__ = [
    "CallsEdge",
    "Fact",
    "ImportsEdge",
    "InheritsEdge",
    "ModuleInfo",
    "SymbolDefinition",
]


@dataclass(frozen=True)
class ModuleInfo:
    """One module (file) boundary."""

    file_path: str
    end_line: int


@dataclass(frozen=True)
class SymbolDefinition:
    """Defined class or function."""

    file_path: str
    scope_stack: tuple[str, ...]
    name: str
    kind: NodeKind
    start_line: int
    end_line: int
    definer_id: str


@dataclass(frozen=True)
class ImportsEdge:
    """IMPORTS edge (resolved target string)."""

    source_id: str
    target: str


@dataclass(frozen=True)
class CallsEdge:
    """CALLS edge (target may be phantom)."""

    source_id: str
    target: str


@dataclass(frozen=True)
class InheritsEdge:
    """INHERITS edge."""

    source_id: str
    target: str


Fact = Union[ModuleInfo, SymbolDefinition, ImportsEdge, CallsEdge, InheritsEdge]
