from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from coderay.core.config import get_config


@dataclass
class BoostRule:
    """Single path-based score multiplier rule (regex pattern + factor)."""

    regex: re.Pattern[str]
    factor: float


@dataclass
class StructuralBooster:
    """Applies path-based score multipliers to search results."""

    penalties: list[BoostRule] = field(default_factory=list)
    bonuses: list[BoostRule] = field(default_factory=list)

    @classmethod
    def from_config(cls) -> StructuralBooster:
        """Build a booster from the application config.

        Returns:
            StructuralBooster with path-based rules from config.
        """
        boosting = get_config().semantic_search.boosting
        return cls(
            penalties=[
                BoostRule(regex=re.compile(r.pattern), factor=r.factor)
                for r in boosting.penalties
            ],
            bonuses=[
                BoostRule(regex=re.compile(r.pattern), factor=r.factor)
                for r in boosting.bonuses
            ],
        )

    def _compute_multiplier(self, path: str) -> float:
        multiplier = 1.0
        for rule in self.penalties:
            if rule.regex.search(path):
                multiplier *= rule.factor
        for rule in self.bonuses:
            if rule.regex.search(path):
                multiplier *= rule.factor
        return multiplier

    def boost(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply path-based score multipliers and re-sort results."""
        boosted = []
        for r in results:
            row = dict(r)
            path = row.get("path", "")
            mult = self._compute_multiplier(path)
            raw_score = row.get("score", 0.0)
            row["raw_score"] = raw_score
            row["score"] = raw_score * mult
            boosted.append(row)
        boosted.sort(key=lambda r: r["score"], reverse=True)
        return boosted
