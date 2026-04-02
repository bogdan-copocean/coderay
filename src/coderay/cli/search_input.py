from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from coderay.core.config import Config
from coderay.core.index_workspace import IndexWorkspace
from coderay.retrieval.models import SearchRequestDTO, SearchResult


class SearchInput(BaseModel):
    """Validated search parameters from CLI or MCP.

    Validates repo aliases against config and resolves them — plus
    default_scope — into a path_prefix before handing off to SearchRequestDTO.
    """

    query: str
    top_k: int = 5
    repos: Annotated[
        list[str] | None,
        Field(
            description=(
                "Repo aliases to scope the search. Pass ['*'] for workspace-wide. "
                "Omit to use search.default_scope from config."
            )
        ),
    ] = None
    path_prefix: str | None = None
    include_tests: bool = True

    # Injected at construction time; excluded from serialisation.
    _config: Config

    def __init__(self, *, config: Config, **data):
        super().__init__(**data)
        object.__setattr__(self, "_config", config)

    @model_validator(mode="after")
    def _validate_repos(self) -> SearchInput:
        if not self.repos:
            return self
        if self.repos == ["*"]:
            return self
        known = {e.alias for e in self._config.index.roots if e.alias}
        unknown = [r for r in self.repos if r not in known]
        if unknown:
            raise ValueError(
                f"Unknown repo alias(es): {unknown}. "
                f"Configured aliases: {sorted(known)}"
            )
        return self

    def to_dto(self) -> SearchRequestDTO:
        """Resolve scope and return an internal SearchRequestDTO."""
        return SearchRequestDTO(
            query=self.query,
            top_k=self.top_k,
            path_prefix=self._resolve_prefix(),
            include_tests=self.include_tests,
        )

    def _resolve_prefix(self) -> str | None:
        # Explicit workspace-wide: no prefix filter.
        if self.repos == ["*"]:
            return None

        if self.repos:
            if len(self.repos) == 1:
                return self.repos[0] + "/"
            # The store filters by a single SQL LIKE prefix; it cannot express
            # OR across multiple aliases in one query.  Until Retrieval.search()
            # supports per-alias fan-out with result merging, multiple aliases
            # fall back to no prefix — results span all repos unfiltered.
            # TODO: fan out one query per alias and merge/re-rank results.
            return None

        # No repos given — apply default_scope from config.
        roots = self._config.index.roots
        if len(roots) <= 1 or self._config.search.default_scope == "*":
            return None
        for entry in roots:
            if entry.repo.strip() == ".":
                return (entry.alias or "") + "/"
        return None


def resolve_result_paths(
    results: list[SearchResult],
    workspace: IndexWorkspace,
) -> list[SearchResult]:
    """Return results with paths resolved to absolute.

    Logical keys (alias/rel/path.py) are resolved against the workspace so
    that editors and terminals can navigate directly to the file.  If a path
    cannot be resolved (e.g. a phantom entry) it is left as-is.
    """
    out = []
    for r in results:
        try:
            abs_path = str(workspace.resolve_logical(r.path))
            out.append(replace(r, path=abs_path))
        except (KeyError, ValueError):
            out.append(r)
    return out
