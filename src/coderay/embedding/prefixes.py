from __future__ import annotations

from coderay.embedding.base import EmbedTask

# search_document / search_query prefix convention (Nomic, nomicai-modernbert).
SEARCH_PREFIXES: dict[EmbedTask, str] = {
    EmbedTask.DOCUMENT: "search_document: ",
    EmbedTask.QUERY: "search_query: ",
}

# Model name fragments that require asymmetric search prefixes.
_PREFIX_REQUIRED_FRAGMENTS = ("nomic-embed", "nomicai-modernbert", "nomic_ai")


def requires_prefix(model_id: str) -> bool:
    """Return True if the model requires asymmetric search_document/search_query prefixes."""  # noqa: E501
    m = model_id.lower().replace("-", "_")
    return any(f.replace("-", "_") in m for f in _PREFIX_REQUIRED_FRAGMENTS)
