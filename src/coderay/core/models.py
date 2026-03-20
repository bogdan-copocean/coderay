from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass
class Chunk:
    """Code chunk ready for embedding."""

    path: str
    start_line: int
    end_line: int
    symbol: str
    content: str


class NodeKind(str, Enum):
    """Node kind: module, class, or function."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class EdgeKind(str, Enum):
    """Edge kind: imports, defines, calls, inherits."""

    IMPORTS = "imports"
    DEFINES = "defines"
    CALLS = "calls"
    INHERITS = "inherits"


@dataclass(frozen=True)
class GraphNode:
    """Node in code graph."""

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
    """Directed edge in code graph."""

    source: str
    target: str
    kind: EdgeKind


@dataclass(frozen=True)
class ImpactResult:
    """Impact-radius query result with diagnostics."""

    resolved_node: str | None
    nodes: list[GraphNode]
    hint: str | None = None
    resolution_warning: str | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        d: dict = {
            "resolved_node": self.resolved_node,
            "results": [n.to_dict() for n in self.nodes],
        }
        if self.hint:
            d["hint"] = self.hint
        if self.resolution_warning:
            d["resolution_warning"] = self.resolution_warning
        return d
