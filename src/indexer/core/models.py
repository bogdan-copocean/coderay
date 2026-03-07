"""Domain models shared across subpackages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass
class Chunk:
    """A single code chunk ready for embedding."""

    path: str
    start_line: int
    end_line: int
    symbol: str
    language: str
    content: str

    def line_range(self) -> tuple[int, int]:
        return (self.start_line, self.end_line)


class NodeKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(str, Enum):
    IMPORTS = "imports"
    DEFINES = "defines"
    CALLS = "calls"
    INHERITS = "inherits"


@dataclass(frozen=True)
class GraphNode:
    """A node in the code graph (module, class, or function)."""

    id: str
    kind: NodeKind
    file_path: str
    start_line: int
    end_line: int
    name: str
    qualified_name: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "name": self.name,
            "qualified_name": self.qualified_name,
        }

    @staticmethod
    def external(node_id: str) -> GraphNode:
        """Create a minimal node for an external/unresolved reference."""
        return GraphNode(
            id=node_id,
            kind=NodeKind.MODULE,
            file_path="",
            start_line=0,
            end_line=0,
            name=node_id,
            qualified_name=node_id,
        )


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge in the code graph."""

    source: str
    target: str
    kind: EdgeKind
