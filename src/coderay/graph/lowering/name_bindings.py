"""Protocols, composed binding stores, and ``FileNameBindings`` façade."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from coderay.parsing.conventions import is_init_file


@runtime_checkable
class NameBindings(Protocol):
    """Read-only name resolution — universal contract across all languages."""

    def resolve(self, name: str) -> str | None: ...
    def resolve_module(self, name: str) -> str | None: ...


class ModuleResolution:
    """Dotted module names -> indexed file paths and ``pkg::Sym`` lowering."""

    def __init__(self, module_index: dict[str, str] | None = None) -> None:
        self._module_index: dict[str, str] = module_index or {}

    def resolve_module_to_file(self, mod_name: str) -> str | None:
        """Return file path for ``mod_name`` if present in the index."""
        return self._module_index.get(mod_name)

    def resolve_qualified_import(self, mod_name: str, symbol: str) -> str:
        """Lower ``mod_name::symbol`` to a file-backed or logical target string."""
        submod_file = self._module_index.get(f"{mod_name}.{symbol}")
        if submod_file:
            return submod_file
        file_path = self._module_index.get(mod_name)
        if not file_path or is_init_file(file_path):
            return f"{mod_name}::{symbol}"
        return f"{file_path}::{symbol}"


class SymbolBindings:
    """Short names -> resolved targets (imports, aliases, node ids)."""

    def __init__(self) -> None:
        self._symbols: dict[str, str] = {}
        self._classes: set[str] = set()

    def bind_symbol(self, name: str, target: str) -> None:
        """Set symbol table entry (import resolution, alias)."""
        self._symbols[name] = target

    def register_definition(
        self, local_name: str, node_id: str, *, is_class: bool = False
    ) -> None:
        """Bind defined name to ``node_id``; record class names for ctor heuristics."""
        self._symbols[local_name] = node_id
        if is_class:
            self._classes.add(local_name)

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        """Map alias -> already-resolved target (no ``::`` splitting)."""
        self.bind_symbol(alias_name, qualified_name)

    def resolve(self, name: str) -> str | None:
        return self._symbols.get(name)

    def is_class(self, name: str) -> bool:
        return name in self._classes


class InstanceTyping:
    """Variable -> class ref(s) and per-class attribute types for attribute chains."""

    def __init__(self) -> None:
        self._instances: dict[str, str] = {}
        self._instance_unions: dict[str, list[str]] = {}
        self._class_attributes: dict[str, str] = {}

    def register_instance(self, var_name: str, class_ref: str) -> None:
        self._instances[var_name] = class_ref
        self._instance_unions.pop(var_name, None)

    def register_instance_union(self, var_name: str, class_refs: list[str]) -> None:
        if not class_refs:
            return
        self._instance_unions[var_name] = class_refs
        self._instances.pop(var_name, None)

    def register_class_attribute(
        self, class_qualified: str, attr_name: str, type_ref: str
    ) -> None:
        self._class_attributes[f"{class_qualified}.{attr_name}"] = type_ref

    def resolve_instance(self, var_name: str) -> str | None:
        return self._instances.get(var_name)

    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]:
        union_refs = self._instance_unions.get(obj_name)
        if union_refs:
            return [f"{ref}.{method_name}" for ref in union_refs]
        class_ref = self._instances.get(obj_name)
        if class_ref is None:
            return []
        return [f"{class_ref}.{method_name}"]

    def resolve_class_attribute(
        self, class_qualified: str, attr_name: str
    ) -> str | None:
        return self._class_attributes.get(f"{class_qualified}.{attr_name}")

    def union_targets(self, var_name: str) -> list[str] | None:
        """Return class refs for a union-typed name, or None if not a union."""
        u = self._instance_unions.get(var_name)
        return list(u) if u else None

    def resolve_chain(self, symbols: SymbolBindings, chain: str) -> list[str]:
        """Resolve ``a.b.c`` using instance typing and fall back to ``symbols``."""
        parts = chain.split(".")
        if not parts:
            return []
        first = parts[0]
        union_refs = self._instance_unions.get(first)
        if union_refs:
            current: list[str] = list(union_refs)
        elif r := self._instances.get(first) or symbols.resolve(first):
            current = [r]
        else:
            return []
        for attr in parts[1:]:
            next_refs = [
                attr_type
                for class_ref in current
                if (
                    attr_type := self.resolve_class_attribute(
                        class_ref.split("::", 1)[-1]
                        if "::" in class_ref
                        else class_ref,
                        attr,
                    )
                )
            ]
            if not next_refs:
                return []
            current = next_refs
        return current


class FileNameBindings:
    """Per-file binding façade: module index, symbol table, and instance typing.

    Writable during Pass 1 via ``register_*``; readable in both passes via
    ``resolve_*``. Processors stay stateless; one instance per extraction run.
    """

    def __init__(self, module_index: dict[str, str] | None = None) -> None:
        self._modules = ModuleResolution(module_index)
        self._symbols = SymbolBindings()
        self._typing = InstanceTyping()

    def register_import(self, local_name: str, qualified_name: str) -> None:
        if "::" in qualified_name:
            mod_part, sym_part = qualified_name.split("::", 1)
            # "pkg::Sym" -> file::Sym or pkg::Sym (see ModuleResolution).
            resolved = self._modules.resolve_qualified_import(mod_part, sym_part)
            self._symbols.bind_symbol(local_name, resolved)
        else:
            file_path = self._modules.resolve_module_to_file(qualified_name)
            # Bare module string -> repo file path if indexed, else dotted name.
            self._symbols.bind_symbol(
                local_name, file_path if file_path else qualified_name
            )

    def register_definition(
        self, local_name: str, node_id: str, *, is_class: bool = False
    ) -> None:
        self._symbols.register_definition(local_name, node_id, is_class=is_class)

    def register_instance(self, var_name: str, class_ref: str) -> None:
        self._typing.register_instance(var_name, class_ref)

    def register_instance_union(self, var_name: str, class_refs: list[str]) -> None:
        self._typing.register_instance_union(var_name, class_refs)

    def register_class_attribute(
        self, class_qualified: str, attr_name: str, type_ref: str
    ) -> None:
        self._typing.register_class_attribute(class_qualified, attr_name, type_ref)

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        self._symbols.register_alias(alias_name, qualified_name)

    def resolve(self, name: str) -> str | None:
        return self._symbols.resolve(name)

    def resolve_module(self, name: str) -> str | None:
        return self._modules.resolve_module_to_file(name)

    def resolve_instance(self, var_name: str) -> str | None:
        return self._typing.resolve_instance(var_name)

    def union_targets(self, var_name: str) -> list[str] | None:
        """Return resolved class refs for a union-typed binding (e.g. ``A | B``)."""
        return self._typing.union_targets(var_name)

    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]:
        return self._typing.resolve_method_calls(obj_name, method_name)

    def resolve_class_attribute(
        self, class_qualified: str, attr_name: str
    ) -> str | None:
        return self._typing.resolve_class_attribute(class_qualified, attr_name)

    def resolve_chain(self, chain: str) -> list[str]:
        return self._typing.resolve_chain(self._symbols, chain)

    def is_class(self, name: str) -> bool:
        return self._symbols.is_class(name)
