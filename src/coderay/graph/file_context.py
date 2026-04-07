"""Per-file symbol bindings for graph extraction (Python/JS/TS).

Bindings are file-local only (no cross-file graph); a future project-wide
context may sit alongside this.

Instance typing: each variable name is either one known class ref or a union of
refs (e.g. ``A | B`` on a parameter). Those two shapes live in ``_instances`` vs
``_instance_unions`` — not duplicate indexes; ``register_instance`` /
``register_instance_union`` clear the other map for that name. Use
``resolve_instance`` for a single ref only; ``resolve_method_calls`` and
``resolve_chain`` consult unions first, then single refs.
"""

from __future__ import annotations

from coderay.graph._utils import is_init_file


class FileContext:
    """Track name bindings for imports, definitions, instances, aliases."""

    def __init__(self, module_index: dict[str, str] | None = None) -> None:
        self._symbols: dict[str, str] = {}
        # x known as instance of one class  ->  "file::Class" or resolved id
        self._instances: dict[str, str] = {}
        # union types: multiple class refs (exclusive with _instances per name)
        self._instance_unions: dict[str, list[str]] = {}
        self._class_attributes: dict[str, str] = {}
        self._classes: set[str] = set()
        self._module_index = module_index or {}

    def _resolve_module_to_file(self, mod_name: str) -> str | None:
        """Resolve dotted module name to file path."""
        return self._module_index.get(mod_name)

    def _resolve_qualified_import(self, mod_name: str, symbol: str) -> str:
        """Resolve from-module import to file-path-based target."""
        submod = f"{mod_name}.{symbol}"
        submod_file = self._resolve_module_to_file(submod)
        if submod_file:
            return submod_file

        file_path = self._resolve_module_to_file(mod_name)
        if not file_path:
            return f"{mod_name}::{symbol}"

        if is_init_file(file_path):
            return f"{mod_name}::{symbol}"

        return f"{file_path}::{symbol}"

    def register_import(self, local_name: str, qualified_name: str) -> None:
        """Register an imported symbol binding."""
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
        """Register a locally defined class or function."""
        self._symbols[local_name] = node_id
        if is_class:
            self._classes.add(local_name)

    def register_instance(self, var_name: str, class_ref: str) -> None:
        """Register a variable as an instance of a class."""
        self._instances[var_name] = class_ref
        self._instance_unions.pop(var_name, None)

    def register_instance_union(self, var_name: str, class_refs: list[str]) -> None:
        """Register a variable as an instance of a union of classes."""
        if not class_refs:
            return
        self._instance_unions[var_name] = class_refs
        self._instances.pop(var_name, None)

    def register_class_attribute(
        self, class_qualified: str, attr_name: str, type_ref: str
    ) -> None:
        """Register a class attribute's type for method resolution."""
        self._class_attributes[f"{class_qualified}.{attr_name}"] = type_ref

    def resolve_class_attribute(
        self, class_qualified: str, attr_name: str
    ) -> str | None:
        """Look up a class attribute's type (e.g. from @property return type)."""
        return self._class_attributes.get(f"{class_qualified}.{attr_name}")

    def register_alias(self, alias_name: str, qualified_name: str) -> None:
        """Register a name alias pointing to an already-qualified target."""
        self._symbols[alias_name] = qualified_name

    def resolve(self, name: str) -> str | None:
        """Look up a name in the unified symbol table."""
        return self._symbols.get(name)

    def resolve_instance(self, var_name: str) -> str | None:
        """Look up single class ref; None if name is union-only or unknown."""
        return self._instances.get(var_name)

    def resolve_method_call(self, obj_name: str, method_name: str) -> str | None:
        """Resolve obj.method() for tracked instance; first match for unions."""
        targets = self.resolve_method_calls(obj_name, method_name)
        return targets[0] if targets else None

    def resolve_method_calls(self, obj_name: str, method_name: str) -> list[str]:
        """Resolve obj.method() to all targets (handles unions)."""
        union_refs = self._instance_unions.get(obj_name)
        if union_refs:
            return [f"{ref}.{method_name}" for ref in union_refs]
        class_ref = self._instances.get(obj_name)
        if class_ref is None:
            return []
        return [f"{class_ref}.{method_name}"]

    def resolve_chain(self, chain: str) -> list[str]:
        # a.b.c  ->  start from instance/alias of a, walk class_attributes per segment
        """Resolve obj.attr1.attr2 to class refs for the final attribute."""
        parts = chain.split(".")
        if not parts:
            return []
        current: list[str] = []
        first = parts[0]
        union_refs = self._instance_unions.get(first)
        if union_refs:
            current = list(union_refs)
        else:
            ref = self._instances.get(first) or self._symbols.get(first)
            if ref:
                current = [ref]
        if not current:
            return []
        for attr in parts[1:]:
            next_refs: list[str] = []
            for class_ref in current:
                class_qualified = (
                    class_ref.split("::", 1)[-1] if "::" in class_ref else class_ref
                )
                attr_type = self.resolve_class_attribute(class_qualified, attr)
                if attr_type:
                    next_refs.append(attr_type)
            if not next_refs:
                return []
            current = next_refs
        return current

    def is_class(self, name: str) -> bool:
        """Check whether a simple name was registered as a class definition."""
        return name in self._classes
