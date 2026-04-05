from __future__ import annotations

import unittest
from pathlib import Path

from src.validation.benchmark_stage04_gold import run_benchmark


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND_01_GOLD_PATH = (
    REPO_ROOT
    / "qa"
    / "validation"
    / "source_categorisation"
    / "gold_standard"
    / "2026-04-05_round_01"
    / "gold_standard_stage04_2026-04-05_round_01.csv"
)


class TestStage04GoldRegressions(unittest.TestCase):
    def test_round_01_gold_matches_current_stage04_outputs(self) -> None:
        results = run_benchmark(
            gold_path=ROUND_01_GOLD_PATH,
            include_likely_wrong_pdf=False,
            include_incorrect_reference=False,
        )
        self.assertEqual(results["reviewed_rows_available"], 10)
        self.assertEqual(results["evaluated_rows"], 10)
        self.assertEqual(results["category_accuracy"], 1.0)
        self.assertEqual(results["count_accuracy"], 1.0)
        self.assertEqual(results["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
