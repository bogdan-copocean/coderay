"""Pure type annotation string resolution (no CST)."""

from __future__ import annotations

from collections.abc import Callable


def is_bare_self_annotation(type_text: str | None) -> bool:
    """True if annotation is exactly ``Self`` (strip + quote unwrap)."""
    if not type_text:
        return False
    text = type_text.strip()
    if not text:
        return False
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
    """Resolve annotation text to qualified class refs.

    ``use_self_semantics`` when True: bare ``Self`` uses ``enclosing_class_qualified``
    (empty yields ``[]``). When False, ``Self`` is resolved like any other name.
    """
    if not type_text:
        return []
    text = type_text.strip()
    if not text:
        return []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    if use_self_semantics and text == "Self":
        if enclosing_class_qualified:
            return [f"{file_path}::{enclosing_class_qualified}"]
        return []
    parts = [p.strip() for p in text.split("|")]
    result: list[str] = []
    for part in parts:
        if not part:
            continue
        if part in ("None", "NoneType"):
            continue
        if "." in part and not part[0].isupper():
            alias, _, attr = part.partition(".")
            if attr and attr[0].isupper():
                resolved_alias = resolve(alias)
                if resolved_alias:
                    result.append(f"{resolved_alias}::{attr}")
            continue
        if not part[0].isupper():
            continue
        resolved = resolve(part)
        result.append(resolved or f"{file_path}::{part}")
    return result


def resolve_annotation_type_text(
    type_text: str | None,
    *,
    file_path: str,
    resolve: Callable[[str], str | None],
) -> str | None:
    """Return first qualified ref from ``resolve_annotation_type_texts``."""
    refs = resolve_annotation_type_texts(
        type_text, file_path=file_path, resolve=resolve
    )
    return refs[0] if refs else None
