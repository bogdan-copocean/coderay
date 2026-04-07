from __future__ import annotations

from dataclasses import dataclass, field

from coderay.graph.facts import Fact
from coderay.graph.file_context import FileContext


@dataclass
class LoweringSession:
    """Facts, file-local symbol state, and module id for one extraction run."""

    facts: set[Fact] = field(default_factory=set)
    file_ctx: FileContext = field(default_factory=FileContext)
    module_id: str = ""  # file_path; caller id when scope_stack is empty
