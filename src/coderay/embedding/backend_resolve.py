from __future__ import annotations

import importlib.util
import platform
import sys


def _mlx_runtime_available() -> bool:
    """Return True if MLX embedder can run on this machine."""
    if sys.platform != "darwin":
        return False
    if platform.machine().lower() != "arm64":
        return False
    return importlib.util.find_spec("mlx_embeddings") is not None


def resolved_embedder_backend(config_value: str | None) -> str:
    """Map backend config to 'fastembed' or 'mlx' (handles 'auto')."""
    raw = (config_value or "auto").strip().lower()
    if raw in ("fastembed", "mlx"):
        return raw
    if raw != "auto":
        raise ValueError(
            f"Unknown embedder.backend {config_value!r}; "
            "use 'auto', 'fastembed', or 'mlx'."
        )
    if _mlx_runtime_available():
        return "mlx"
    return "fastembed"
