from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.validation import benchmark_stage06_hybrid as benchmark


class TestStage06HybridBenchmark(unittest.TestCase):
    def test_score_workflow_counts_exact_manual_and_silent_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            workflow_path = root / "workflow.csv"
            with workflow_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "paper_id",
                        "likely_sps_case_count",
                        "count_manual_review_required",
                        "count_verification_status",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "paper_id": "11",
                            "likely_sps_case_count": "3",
                            "count_manual_review_required": "false",
                            "count_verification_status": "llm_candidate_exact",
                        },
                        {
                            "paper_id": "22",
                            "likely_sps_case_count": "2",
                            "count_manual_review_required": "false",
                            "count_verification_status": "llm_candidate_exact",
                        },
                        {
                            "paper_id": "29",
                            "likely_sps_case_count": "1",
                            "count_manual_review_required": "true",
                            "count_verification_status": "llm_manual_review_required",
                        },
                        {
                            "paper_id": "30",
                            "likely_sps_case_count": "3",
                            "count_manual_review_required": "false",
                            "count_verification_status": "manual_review_override",
                        },
                    ]
                )

            score = benchmark.score_workflow(
                workflow_label="hybrid",
                workflow_path=workflow_path,
                gold_counts={"11": 3, "22": 1, "29": 2, "30": 3},
            )

        self.assertEqual(score["exact"], 2)
        self.assertEqual(score["manual_review_rows"], 1)
        self.assertEqual(score["silent_wrong_auto_accepts"], 1)
        self.assertEqual(score["reviewed_override_rows"], 1)

    def test_selected_gold_counts_supports_selection_and_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            gold_papers_dir = root / "papers"
            gold_papers_dir.mkdir()
            manifest_path = root / "manifest.json"
            selection_path = root / "selection.json"
            exclude_path = root / "exclude.json"

            manifest_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"paper_id": "11", "gold_status": "active"},
                            {"paper_id": "22", "gold_status": "active"},
                            {"paper_id": "29", "gold_status": "active"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            selection_path.write_text(json.dumps({"paper_ids": ["11", "22"]}), encoding="utf-8")
            exclude_path.write_text(json.dumps({"paper_ids": ["22"]}), encoding="utf-8")
            for paper_id, count in (("11", 3), ("22", 1), ("29", 1)):
                (gold_papers_dir / f"{paper_id}.json").write_text(
                    json.dumps({"count_row": {"likely_sps_case_count": str(count)}}),
                    encoding="utf-8",
                )

            counts = benchmark.selected_gold_counts(
                manifest_path=manifest_path,
                gold_papers_dir=gold_papers_dir,
                selection_path=selection_path,
                exclude_selection_paths=[exclude_path],
            )

        self.assertEqual(counts, {"11": 3})


if __name__ == "__main__":
    unittest.main()
