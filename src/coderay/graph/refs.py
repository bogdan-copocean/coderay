"""Canonical graph target string shapes (node ids, module refs, phantoms)."""

from __future__ import annotations

from coderay.graph.facts import EdgeTargetKind

FILE_QUAL_SEP = "::"


def split_file_qual(s: str) -> tuple[str, str] | None:
    """Split ``file::qual`` at the first separator; return None if absent."""
    if FILE_QUAL_SEP not in s:
        return None
    left, _, right = s.partition(FILE_QUAL_SEP)
    if not left or not right:
        return None
    return (left, right)


def join_file_qual(file_path: str, qualified_tail: str) -> str:
    """Build ``file_path::qualified_tail``."""
    return f"{file_path}{FILE_QUAL_SEP}{qualified_tail}"


def target_starts_with_known_file(target: str, known_files: set[str]) -> bool:
    """Return True if target is a known file or ``file::…`` with known prefix."""
    if target in known_files:
        return True
    parts = split_file_qual(target)
    if parts is None:
        return False
    return parts[0] in known_files


def infer_call_target_kind(target: str) -> EdgeTargetKind:
    """Heuristic classification for CALLS edge targets."""
    if split_file_qual(target) is not None:
        return "resolved_node"
    if "." in target:
        return "module_ref"
    return "phantom"


def infer_import_target_kind(target: str) -> EdgeTargetKind:
    """Heuristic classification for IMPORTS edge targets."""
    if split_file_qual(target) is not None:
        return "resolved_node"
    if target.endswith((".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
        return "resolved_node"
    return "module_ref"


def infer_inherits_target_kind(target: str) -> EdgeTargetKind:
    """Heuristic classification for INHERITS edge targets."""
    if split_file_qual(target) is not None:
        return "resolved_node"
    if "." in target:
        return "module_ref"
    return "phantom"
