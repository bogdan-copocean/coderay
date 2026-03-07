"""Tests for structural boosting."""

from coderay.retrieval.boosting import StructuralBooster


class TestStructuralBooster:
    def _make_result(self, path: str, score: float) -> dict:
        return {"path": path, "score": score, "content": "x", "symbol": "x"}

    def test_default_rules_loaded(self):
        booster = StructuralBooster.from_config({})
        assert len(booster.penalties) > 0
        assert len(booster.bonuses) > 0

    def test_test_dir_penalized(self):
        booster = StructuralBooster.from_config({})
        results = [
            self._make_result("tests/test_foo.py", 1.0),
            self._make_result("src/foo.py", 1.0),
        ]
        boosted = booster.boost(results)
        src_result = next(r for r in boosted if r["path"] == "src/foo.py")
        test_result = next(r for r in boosted if r["path"] == "tests/test_foo.py")
        assert src_result["score"] > test_result["score"]

    def test_src_dir_boosted(self):
        booster = StructuralBooster.from_config({})
        results = [
            self._make_result("other/foo.py", 1.0),
            self._make_result("src/foo.py", 1.0),
        ]
        boosted = booster.boost(results)
        src_result = next(r for r in boosted if r["path"] == "src/foo.py")
        other_result = next(r for r in boosted if r["path"] == "other/foo.py")
        assert src_result["score"] > other_result["score"]

    def test_vendor_heavily_penalized(self):
        booster = StructuralBooster.from_config({})
        results = [
            self._make_result("vendor/lib.py", 1.0),
            self._make_result("src/main.py", 1.0),
        ]
        boosted = booster.boost(results)
        vendor = next(r for r in boosted if r["path"] == "vendor/lib.py")
        src = next(r for r in boosted if r["path"] == "src/main.py")
        assert src["score"] > vendor["score"]

    def test_conftest_penalized(self):
        booster = StructuralBooster.from_config({})
        results = [
            self._make_result("tests/conftest.py", 1.0),
            self._make_result("src/main.py", 1.0),
        ]
        boosted = booster.boost(results)
        conftest = next(r for r in boosted if "conftest" in r["path"])
        assert conftest["score"] < 1.0

    def test_raw_score_preserved(self):
        booster = StructuralBooster.from_config({})
        results = [self._make_result("tests/test_a.py", 0.5)]
        boosted = booster.boost(results)
        assert boosted[0]["raw_score"] == 0.5

    def test_custom_config_rules(self):
        config = {
            "search": {
                "boost_rules": {
                    "penalties": [{"pattern": r"special/", "factor": 0.1}],
                    "bonuses": [{"pattern": r"priority/", "factor": 2.0}],
                }
            }
        }
        booster = StructuralBooster.from_config(config)
        assert len(booster.penalties) == 1
        assert len(booster.bonuses) == 1

    def test_empty_results(self):
        booster = StructuralBooster.from_config({})
        assert booster.boost([]) == []

    def test_results_sorted_by_score(self):
        booster = StructuralBooster.from_config({})
        results = [
            self._make_result("vendor/a.py", 0.5),
            self._make_result("src/b.py", 0.5),
        ]
        boosted = booster.boost(results)
        assert boosted[0]["score"] >= boosted[-1]["score"]

    def test_does_not_mutate_input(self):
        booster = StructuralBooster.from_config({})
        results = [self._make_result("tests/test_a.py", 0.5)]
        original_score = results[0]["score"]
        booster.boost(results)
        assert results[0]["score"] == original_score
        assert "raw_score" not in results[0]
