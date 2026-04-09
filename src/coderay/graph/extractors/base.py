"""Shared graph extractor: two-pass DFS with binding and fact handler maps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Protocol

from coderay.graph.facts import Fact, ModuleInfo
from coderay.graph.language_plugin import get_plugin
from coderay.graph.lowering.callee_strategy import (
    CalleeStrategy,
    default_callee_strategy,
)
from coderay.graph.lowering.name_bindings import FileNameBindings, NameBindings
from coderay.graph.project_index import (
    EmptyProjectIndex,
    ProjectIndex,
    PythonModuleIndex,
)
from coderay.parsing.base import BaseTreeSitterParser, ParserContext, TSNode
from coderay.parsing.cst_kind import TraversalKind, classify_node

# ---------------------------------------------------------------------------
# Protocols — contract between extractors and per-node binders/emitters
# ---------------------------------------------------------------------------


class Binder(Protocol):
    """Pass 1 — register names into ``FileNameBindings``.

    May append to ``scope_stack`` when the node opens a new lexical scope.
    The DFS pops the pushed name after recursing into children.
    Must not emit facts — side effects on ``bindings`` and ``scope_stack`` only.
    """

    def register(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: FileNameBindings,
    ) -> None: ...


class Emitter(Protocol):
    """Pass 2 — emit facts from resolved bindings.

    Receives the same mutable ``scope_stack`` as Pass 1 (same DFS traversal).
    """

    def emit(
        self,
        node: TSNode,
        scope_stack: list[str],
        parser: BaseTreeSitterParser,
        bindings: NameBindings,
    ) -> list[Fact]: ...


# ---------------------------------------------------------------------------
# Handler wrappers and maps
# ---------------------------------------------------------------------------


@dataclass
class BindingHandler:
    """Wraps a Binder for Pass 1.

    order="post" — children visited before register() (rare for bindings).
    """

    processor: Binder
    order: Literal["pre", "post"] = "pre"


@dataclass
class FactHandler:
    """Wraps an Emitter for Pass 2.

    order="post" — children visited before emit() (used for decorators).
    """

    processor: Emitter
    order: Literal["pre", "post"] = "pre"


BindingHandlerMap = dict[TraversalKind, BindingHandler]
FactHandlerMap = dict[TraversalKind, FactHandler]


# ---------------------------------------------------------------------------
# Base extractor
# ---------------------------------------------------------------------------


class BaseGraphExtractor(ABC):
    """Lower a source file's CST to graph facts via two DFS passes.

    Pass 1 (binding pass) — Binders populate ``FileNameBindings``
    so that Pass 2 can resolve names.  No facts are emitted here.

    Pass 2 (fact pass)    — Emitters read the completed bindings and
    emit all facts: definitions, imports, inheritance, calls, decorators.

    Both passes share a mutable scope stack.  A binder that opens a new
    lexical scope appends to it; the DFS pops the name after recursing into
    children.  Pass 2 mirrors the same scope transitions automatically.

    Subclass contract: implement ``_build_binding_handlers()`` and
    ``_build_fact_handlers()``.
    """

    def __init__(
        self,
        context: ParserContext,
        *,
        project_index: ProjectIndex | None = None,
        module_index: dict[str, str] | None = None,
    ) -> None:
        if project_index is not None and module_index is not None:
            raise TypeError("pass only one of project_index or module_index")
        if module_index is not None:
            project_index = PythonModuleIndex(module_index)
        self._project_index: ProjectIndex = project_index or EmptyProjectIndex()
        self._parser = BaseTreeSitterParser(context)
        self._module_id: str = context.file_path
        self._bindings = FileNameBindings(self._project_index)

    @abstractmethod
    def _build_binding_handlers(self, bindings: FileNameBindings) -> BindingHandlerMap:
        """Declare Pass 1 handlers for this language."""

    @abstractmethod
    def _build_fact_handlers(self, resolver: CalleeStrategy) -> FactHandlerMap:
        """Declare Pass 2 handlers for this language."""

    def extract_facts_list(self) -> set[Fact]:
        tree = self._parser.get_tree()
        root = tree.root_node
        facts: set[Fact] = {
            ModuleInfo(
                file_path=self._parser.file_path,
                end_line=root.end_point[0] + 1,
            )
        }

        # Pass 1: populate bindings — no facts collected here.
        self._bindings = FileNameBindings(self._project_index)  # fresh per run
        binding_handlers = self._build_binding_handlers(self._bindings)
        scope_stack: list[str] = []
        self._dfs_binding(root, scope_stack=scope_stack, handlers=binding_handlers)

        # Pass 2: emit all facts using the completed bindings.
        # Reuse the same scope_stack (now empty again after Pass 1 completes).
        plugin = get_plugin(self._parser.lang_cfg.name)
        factory = (
            plugin.callee_strategy_factory
            if plugin and plugin.callee_strategy_factory
            else default_callee_strategy
        )
        resolver = factory(self._bindings, self._parser)
        fact_handlers = self._build_fact_handlers(resolver)
        self._dfs_fact(
            root, scope_stack=scope_stack, handlers=fact_handlers, facts=facts
        )

        return facts

    @property
    def _file_ctx(self) -> FileNameBindings:
        """Expose bindings for tests that inspect binding state post-extraction."""
        return self._bindings

    # ------------------------------------------------------------------
    # Pass 1: binding DFS — populates FileNameBindings, collects no facts
    # ------------------------------------------------------------------

    def _dfs_binding(
        self,
        node: TSNode,
        *,
        scope_stack: list[str],
        handlers: BindingHandlerMap,
    ) -> None:
        kind = classify_node(node.type, self._parser.lang_cfg)
        entry = handlers.get(kind)

        if entry is None:
            for child in node.children:
                self._dfs_binding(child, scope_stack=scope_stack, handlers=handlers)
            return

        if entry.order == "post":
            for child in node.children:
                self._dfs_binding(child, scope_stack=scope_stack, handlers=handlers)
            entry.processor.register(node, scope_stack, self._parser, self._bindings)
            return

        depth = len(scope_stack)
        entry.processor.register(node, scope_stack, self._parser, self._bindings)
        for child in node.children:
            self._dfs_binding(child, scope_stack=scope_stack, handlers=handlers)
        del scope_stack[depth:]  # pop any scope the binder pushed

    # ------------------------------------------------------------------
    # Pass 2: fact DFS — emits facts; bindings read-only;
    # ------------------------------------------------------------------

    def _dfs_fact(
        self,
        node: TSNode,
        *,
        scope_stack: list[str],
        handlers: FactHandlerMap,
        facts: set[Fact],
    ) -> None:
        kind = classify_node(node.type, self._parser.lang_cfg)
        entry = handlers.get(kind)

        if entry is None:
            for child in node.children:
                self._dfs_fact(
                    child, scope_stack=scope_stack, handlers=handlers, facts=facts
                )
            return

        if entry.order == "post":
            depth = len(scope_stack)
            for child in node.children:
                self._dfs_fact(
                    child, scope_stack=scope_stack, handlers=handlers, facts=facts
                )
            del scope_stack[depth:]
            facts.update(
                entry.processor.emit(node, scope_stack, self._parser, self._bindings)
            )
            return

        depth = len(scope_stack)
        facts.update(
            entry.processor.emit(node, scope_stack, self._parser, self._bindings)
        )
        for child in node.children:
            self._dfs_fact(
                child, scope_stack=scope_stack, handlers=handlers, facts=facts
            )
        del scope_stack[depth:]
