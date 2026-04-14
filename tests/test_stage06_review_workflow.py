from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.validation import _stage06_review as review


class TestStage06ReviewWorkflow(unittest.TestCase):
    def test_infer_run_id_from_stage06_path(self) -> None:
        self.assertEqual(
            review.infer_run_id_from_stage06_path(
                r"results\stage06_count_runs\stage06_llm_test_71\candidate_packages\71.json"
            ),
            "stage06_llm_test_71",
        )
        self.assertEqual(review.infer_run_id_from_stage06_path(r"data\references\source_sps_case_count_registry.csv"), "")

    def test_load_review_rows_from_run_enriches_artifact_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_dir = root / "stage06_demo"
            results_dir = run_dir / "results"
            decisions_dir = run_dir / "count_decisions"
            results_dir.mkdir(parents=True)
            decisions_dir.mkdir(parents=True)

            artifact_registry_path = root / "paper_artifact_registry.csv"
            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "pdf_paths_relative", "text_json_path"])
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "71",
                        "pdf_paths_relative": r"data\pdf_original\71_test.pdf|data\pdf_original\71_alt.pdf",
                        "text_json_path": r"data\extraction_json\text\71.json",
                    }
                )

            (decisions_dir / "71.json").write_text("{}", encoding="utf-8")
            (results_dir / "71.json").write_text(
                json.dumps(
                    {
                        "paper_id": "71",
                        "count_row": {
                            "paper_id": "71",
                            "title": "Example paper",
                            "likely_sps_case_count": "3",
                            "count_verification_status": "llm_candidate_exact",
                            "count_candidate_json_path": r"results\stage06_count_runs\stage06_demo\candidate_packages\71.json",
                            "count_evidence_json_path": r"results\stage06_count_runs\stage06_demo\count_evidence\71.json",
                        },
                        "source_text_json_path": r"data\extraction_json\text\71.json",
                        "preferred_text_json_path": r"data\extraction_json\text\71.json",
                    }
                ),
                encoding="utf-8",
            )

            rows = review.load_review_rows_from_run(run_dir, artifact_registry_path=artifact_registry_path)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], "stage06_demo")
        self.assertEqual(row["paper_id"], "71")
        self.assertEqual(row["pdf_path_relative"], r"data\pdf_original\71_test.pdf")
        self.assertEqual(row["source_text_json_path"], r"data\extraction_json\text\71.json")
        self.assertTrue(row["count_decision_json_path"].endswith(r"stage06_demo\count_decisions\71.json"))

    def test_save_response_row_preserves_review_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            review_dir = root / "review_scope"
            review.ensure_review_workspace(
                review_dir,
                source_scope_id="demo_scope",
                source_scope_label="demo_scope",
                source_kind="run_directory",
                source_path_text="results/stage06_count_runs/demo_scope",
            )
            review_rows = [
                {"paper_id": "71", "title": "Paper 71", "likely_sps_case_count": "3", "count_verification_status": "llm_candidate_exact"},
                {"paper_id": "214", "title": "Paper 214", "likely_sps_case_count": "2", "count_verification_status": "llm_candidate_exact"},
            ]

            row_214 = review.build_response_row(
                source_scope_id="demo_scope",
                source_scope_label="demo_scope",
                review_row=review_rows[1],
                prediction_correct=False,
                reviewed_count="4",
                review_status="needs_follow_up",
                reviewer_notes="Needs another check.",
                reviewer_id="tester",
            )
            row_71 = review.build_response_row(
                source_scope_id="demo_scope",
                source_scope_label="demo_scope",
                review_row=review_rows[0],
                prediction_correct=True,
                reviewed_count="",
                review_status="reviewed",
                reviewer_notes="Looks correct.",
                reviewer_id="tester",
            )

            review.save_response_row(review_dir, review_rows, row_214)
            responses_by_id = review.save_response_row(review_dir, review_rows, row_71)

            saved_rows = review.load_csv_rows(review.responses_path(review_dir))

        self.assertEqual(list(responses_by_id), ["214", "71"])
        self.assertEqual([row["paper_id"] for row in saved_rows], ["71", "214"])
        self.assertEqual(saved_rows[0]["reviewed_count"], "3")
        self.assertEqual(saved_rows[1]["review_status"], "needs_follow_up")

    def test_registry_row_without_paths_attaches_latest_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_root = root / "stage06_count_runs"
            latest_run = run_root / "stage06_llm_test_711"
            (latest_run / "results").mkdir(parents=True)
            (latest_run / "candidate_packages").mkdir()
            (latest_run / "count_decisions").mkdir()
            (latest_run / "count_evidence").mkdir()
            (latest_run / "results" / "711.json").write_text("{}", encoding="utf-8")
            (latest_run / "candidate_packages" / "711.json").write_text("{}", encoding="utf-8")
            (latest_run / "count_decisions" / "711.json").write_text("{}", encoding="utf-8")
            (latest_run / "count_evidence" / "711.json").write_text("{}", encoding="utf-8")

            artifact_registry_path = root / "paper_artifact_registry.csv"
            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "pdf_paths_relative", "text_json_path"])
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "711",
                        "pdf_paths_relative": r"data\pdf_original\711_test.pdf",
                        "text_json_path": r"data\extraction_json\text\711.json",
                    }
                )

            registry_path = root / "source_sps_case_count_registry.csv"
            with registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["paper_id", "title", "likely_sps_case_count", "count_verification_status", "preferred_text_json_path"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "711",
                        "title": "Example 711",
                        "likely_sps_case_count": "9",
                        "count_verification_status": "llm_joint_extraction",
                        "preferred_text_json_path": r"data\extraction_json\text\711.json",
                    }
                )

            original_run_root = review.RUN_ROOT
            try:
                review.RUN_ROOT = run_root
                rows = review.load_review_rows_from_registry(registry_path, artifact_registry_path=artifact_registry_path)
            finally:
                review.RUN_ROOT = original_run_root

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], "stage06_llm_test_711")
        self.assertTrue(row["count_candidate_json_path"].endswith(r"stage06_llm_test_711\candidate_packages\711.json"))
        self.assertTrue(row["count_decision_json_path"].endswith(r"stage06_llm_test_711\count_decisions\711.json"))
        self.assertTrue(row["count_evidence_json_path"].endswith(r"stage06_llm_test_711\count_evidence\711.json"))


if __name__ == "__main__":
    unittest.main()
