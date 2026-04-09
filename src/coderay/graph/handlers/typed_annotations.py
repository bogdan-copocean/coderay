"""Annotation string parsing for typed OOP languages (Python, TypeScript).

Pure string functions — no CST, no bindings.  Not applicable to languages
without inline type annotation syntax (Go, Rust, C).
"""

from __future__ import annotations

from collections.abc import Callable


def is_bare_self_annotation(type_text: str | None) -> bool:
    """True if annotation text is exactly ``Self`` (handles forward-ref quotes)."""
    if not type_text:
        return False
    text = type_text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    return text == "Self"


def resolve_annotation_type_texts(
    type_text: str | None,
    *,
    file_path: str,
    resolve: Callable[[str], str | None],
    use_self_semantics: bool = False,
    enclosing_class_qualified: str | None = None,
) -> list[str]:
    """Resolve annotation text to a list of qualified class refs.

    "Foo | Bar" -> ["path/a.py::Foo", "path/b.py::Bar"]
    With use_self_semantics=True, bare "Self" -> ["path/a.py::EnclosingClass"].
    """
    if not type_text:
        return []
    text = type_text.strip()
    if not text:
        return []
    # Strip forward-reference quotes: "Foo" -> Foo
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    if use_self_semantics and text == "Self":
        if enclosing_class_qualified:
            return [f"{file_path}::{enclosing_class_qualified}"]
        return []
    parts = [p.strip() for p in text.split("|")]
    result: list[str] = []
    for part in parts:
        if not part or part in ("None", "NoneType"):
            continue
        if "." in part and not part[0].isupper():
            # module.ClassName alias: resolve the module prefix.
            alias, _, attr = part.partition(".")
            if attr and attr[0].isupper():
                resolved_alias = resolve(alias)
                if resolved_alias:
                    result.append(f"{resolved_alias}::{attr}")
            continue
        if not part[0].isupper():
            continue  # skip builtins, lowercase names
        resolved = resolve(part)
        result.append(resolved or f"{file_path}::{part}")
    return result


def resolve_annotation_type_text(
    type_text: str | None,
    *,
    file_path: str,
    resolve: Callable[[str], str | None],
) -> str | None:
    """First result from resolve_annotation_type_texts, or None."""
    refs = resolve_annotation_type_texts(
        type_text, file_path=file_path, resolve=resolve
    )
    return refs[0] if refs else None
