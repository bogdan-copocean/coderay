from __future__ import annotations

from coderay.embedding.base import EmbedTask

# Nomic asymmetric retrieval (ONNX nomic-embed-text-v1.5*, MLX nomicai-modernbert*).
NOMIC_PREFIXES: dict[EmbedTask, str] = {
    EmbedTask.DOCUMENT: "search_document: ",
    EmbedTask.QUERY: "search_query: ",
}


def nomic_prefix_for_task(task: EmbedTask) -> str:
    """Return prefix string for Nomic document vs query embedding."""
    return NOMIC_PREFIXES.get(task, "")


def is_nomic_model_id(model_id: str) -> bool:
    """Return True if model id expects Nomic search_document/search_query prefixes."""
    m = model_id.lower()
    return (
        "nomic-embed" in m
        or "nomicai-modernbert" in m
        or "nomic_ai" in m.replace("-", "_")
    )
