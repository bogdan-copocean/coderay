from __future__ import annotations

from coderay.graph._utils import is_init_file


class FileContext:
    """Per-file name bindings: imports, definitions, instances, aliases.

    Instance typing: each var is either one class ref (_instances) or a union
    (_instance_unions) — the two maps are mutually exclusive per name.
    resolve_instance returns only single refs; resolve_method_calls and
    resolve_chain handle unions.
    """

    def __init__(self, module_index: dict[str, str] | None = None) -> None:
        self._symbols: dict[str, str] = {}
        self._instances: dict[str, str] = {}  # var -> single class ref
        self._instance_unions: dict[str, list[str]] = {}  # var -> union refs
        self._class_attributes: dict[str, str] = {}  # "Class.attr" -> type ref
        self._classes: set[str] = set()
        self._module_index = module_index or {}

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

    def resolve_class_attribute(
        self, class_qualified: str, attr_name: str
    ) -> str | None:
        return self._class_attributes.get(f"{class_qualified}.{attr_name}")

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        self._symbols[alias_name] = qualified_name

    def resolve(self, name: str) -> str | None:
        return self._symbols.get(name)

    def resolve_instance(self, var_name: str) -> str | None:
        # None if union-only or unknown
        return self._instances.get(var_name)

    def resolve_method_call(self, obj_name: str, method_name: str) -> str | None:
        targets = self.resolve_method_calls(obj_name, method_name)
        return targets[0] if targets else None

    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]:
        union_refs = self._instance_unions.get(obj_name)
        if union_refs:
            return [f"{ref}.{method_name}" for ref in union_refs]
        class_ref = self._instances.get(obj_name)
        if class_ref is None:
            return []
        return [f"{class_ref}.{method_name}"]

    def resolve_chain(self, chain: str) -> list[str]:
        # a.b.c -> walk from instance/alias of a through class_attributes per segment
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

    def is_class(self, name: str) -> bool:
        return name in self._classes
