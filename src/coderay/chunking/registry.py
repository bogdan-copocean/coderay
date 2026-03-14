from __future__ import annotations

"""Backwards-compatible re-export of language configuration symbols.

This module exists to preserve existing import paths for language configuration
while the canonical definitions live in ``coderay.parsing.languages``.
"""

from coderay.parsing.languages import (  # noqa: F401
    GO_CONFIG,
    JAVASCRIPT_CONFIG,
    LANGUAGE_REGISTRY,
    PYTHON_CONFIG,
    TYPESCRIPT_CONFIG,
    LanguageConfig,
    get_init_filenames,
    get_language_for_file,
    get_resolution_suffixes,
    get_supported_extensions,
)
