"""Per-file name bindings: protocols and the single concrete implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from coderay.parsing.conventions import is_init_file


@runtime_checkable
class NameBindings(Protocol):
    """Read-only name resolution — universal contract across all languages."""

    def resolve(self, name: str) -> str | None: ...
    def resolve_module(self, name: str) -> str | None: ...


@runtime_checkable
class OONameBindings(NameBindings, Protocol):
    """Name resolution extended for class-based (OO) languages."""

    def resolve_instance(self, var_name: str) -> str | None: ...
    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]: ...
    def resolve_class_attribute(self, class_qualified: str, attr_name: str) -> str | None: ...
    def resolve_chain(self, chain: str) -> list[str]: ...
    def is_class(self, name: str) -> bool: ...


class FileNameBindings:
    """Per-file name binding store for one extraction run.

    Writable during Pass 1 (binding pass) via ``register_*`` methods.
    Readable in both passes via ``resolve_*`` methods.

    A single instance is used throughout — no frozen copy needed because
    processors are stateless (bindings are passed as a parameter, never stored).
    """

    def __init__(self, module_index: dict[str, str] | None = None) -> None:
        self._symbols: dict[str, str] = {}
        self._instances: dict[str, str] = {}
        self._instance_unions: dict[str, list[str]] = {}
        self._class_attributes: dict[str, str] = {}
        self._classes: set[str] = set()
        self._module_index: dict[str, str] = module_index or {}

    # ------------------------------------------------------------------
    # Module resolution (internal helper used by register_import)
    # ------------------------------------------------------------------

    def _resolve_module_to_file(self, mod_name: str) -> str | None:
        return self._module_index.get(mod_name)

    def _resolve_qualified_import(self, mod_name: str, symbol: str) -> str:
        submod_file = self._resolve_module_to_file(f"{mod_name}.{symbol}")
        if submod_file:
            return submod_file
        file_path = self._resolve_module_to_file(mod_name)
        if not file_path or is_init_file(file_path):
            return f"{mod_name}::{symbol}"
        return f"{file_path}::{symbol}"

    # ------------------------------------------------------------------
    # Write (Pass 1 only by convention)
    # ------------------------------------------------------------------

    def register_import(self, local_name: str, qualified_name: str) -> None:
        if "::" in qualified_name:
            mod_part, sym_part = qualified_name.split("::", 1)
            resolved = self._resolve_qualified_import(mod_part, sym_part)
            self._symbols[local_name] = resolved
        else:
            file_path = self._resolve_module_to_file(qualified_name)
            self._symbols[local_name] = file_path if file_path else qualified_name

    def register_definition(
        self, local_name: str, node_id: str, *, is_class: bool = False
    ) -> None:
        self._symbols[local_name] = node_id
        if is_class:
            self._classes.add(local_name)

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

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        self._symbols[alias_name] = qualified_name

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def resolve(self, name: str) -> str | None:
        return self._symbols.get(name)

    def resolve_module(self, name: str) -> str | None:
        return self._resolve_module_to_file(name)

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

    def resolve_chain(self, chain: str) -> list[str]:
        parts = chain.split(".")
        if not parts:
            return []
        first = parts[0]
        union_refs = self._instance_unions.get(first)
        if union_refs:
            current: list[str] = list(union_refs)
        elif r := self._instances.get(first) or self._symbols.get(first):
            current = [r]
        else:
            return []
        for attr in parts[1:]:
            next_refs = [
                attr_type
                for class_ref in current
                if (
                    attr_type := self.resolve_class_attribute(
                        class_ref.split("::", 1)[-1] if "::" in class_ref else class_ref,
                        attr,
                    )
                )
            ]
            if not next_refs:
                return []
            current = next_refs
        return current

    def is_class(self, name: str) -> bool:
        return name in self._classes
