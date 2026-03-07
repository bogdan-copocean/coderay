"""Structural boosting: adjust search relevance scores based on file paths.

Deprioritizes tests, mocks, and generated files while boosting core source
directories. Rules are configurable via config.yaml under search.boost_rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_PENALTIES: list[dict[str, Any]] = [
    {"pattern": r"(^|/)tests?/", "factor": 0.5},
    {"pattern": r"(^|/)test_[^/]+\.py$", "factor": 0.5},
    {"pattern": r"(^|/)(mock|fixture|conftest)", "factor": 0.4},
    {"pattern": r"(^|/)(generated|vendor|third_party)/", "factor": 0.3},
    {"pattern": r"(^|/)docs?/", "factor": 0.6},
    {"pattern": r"(^|/)examples?/", "factor": 0.7},
]

DEFAULT_BONUSES: list[dict[str, Any]] = [
    {"pattern": r"(^|/)src/", "factor": 1.1},
    {"pattern": r"(^|/)lib/", "factor": 1.1},
    {"pattern": r"(^|/)app/", "factor": 1.1},
]


@dataclass
class BoostRule:
    regex: re.Pattern[str]
    factor: float


@dataclass
class StructuralBooster:
    """Applies path-based score multipliers to search results."""

    penalties: list[BoostRule] = field(default_factory=list)
    bonuses: list[BoostRule] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> StructuralBooster:
        """Build from config dict. Falls back to defaults if not specified."""
        search_cfg = config.get("search") or {}
        boost_cfg = search_cfg.get("boost_rules") or {}

        raw_penalties = boost_cfg.get("penalties") or DEFAULT_PENALTIES
        raw_bonuses = boost_cfg.get("bonuses") or DEFAULT_BONUSES

        return cls(
            penalties=[
                BoostRule(regex=re.compile(r["pattern"]), factor=r["factor"])
                for r in raw_penalties
            ],
            bonuses=[
                BoostRule(regex=re.compile(r["pattern"]), factor=r["factor"])
                for r in raw_bonuses
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
        """Apply score multipliers and re-sort by boosted score.

        Returns a NEW list of dicts (does not mutate the input).
        LanceDB returns L2 distances (lower = more similar), so we *divide*
        by the multiplier: bonus paths get smaller scores (better rank),
        penalty paths get larger scores (worse rank).
        """
        boosted = []
        for r in results:
            row = dict(r)
            path = row.get("path", "")
            mult = self._compute_multiplier(path)
            raw_score = row.get("score", 0.0)
            row["raw_score"] = raw_score
            row["score"] = raw_score / mult if mult > 0 else raw_score
            boosted.append(row)
        boosted.sort(key=lambda r: r["score"])
        return boosted
