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
    content: str

    def line_range(self) -> tuple[int, int]:
        """Return (start_line, end_line) for this chunk."""
        return (self.start_line, self.end_line)


class NodeKind(str, Enum):
    """Kind of node in the code graph: module, class, or function."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(str, Enum):
    """Kind of directed edge: imports, defines, calls, or inherits."""

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
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "name": self.name,
            "qualified_name": self.qualified_name,
        }


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge in the code graph."""

    source: str
    target: str
    kind: EdgeKind
