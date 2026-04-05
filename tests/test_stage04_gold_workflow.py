from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.validation import _stage04_gold as gold
from src.validation import benchmark_stage04_gold as benchmark


class TestStage04GoldWorkflow(unittest.TestCase):
    def test_count_ambiguity_signals_flag_suspicious_count_patterns(self) -> None:
        signals = gold.count_ambiguity_signals(
            {
                "count_eligible": "true",
                "count_manual_review_required": "true",
                "count_confidence": "medium",
                "count_basis": "patient_label_count",
                "likely_case_count": "3",
                "patient_label_count": "2",
                "source_category": "single_case_report",
            }
        )

        self.assertIn("count_manual_review_required", signals)
        self.assertIn("count_non_high_confidence", signals)
        self.assertIn("count_differs_from_patient_labels", signals)
        self.assertIn("single_case_with_multi_count", signals)
        self.assertIn("count_basis=patient_label_count", signals)

    def test_next_round_directory_increments_existing_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            (root / "2026-04-05_round_01").mkdir()
            (root / "2026-04-05_round_02").mkdir()

            next_dir = gold.next_round_directory(root=root, date_label="2026-04-05")

        self.assertEqual(next_dir.name, "2026-04-05_round_03")

    def test_build_response_row_and_snapshot_fill_reviewed_values(self) -> None:
        queue_row = {
            "round_id": "2026-04-05_round_01",
            "paper_id": "123",
            "title": "Test paper",
            "selection_bucket": "count_ambiguity",
            "covidence_id": "123",
            "authors": "A Author",
            "published_year": "2024",
            "journal": "Neurology",
            "selection_signals": "count_non_high_confidence",
            "pdf_filename": "123_test.pdf",
            "pdf_path_relative": "data\\pdf_original\\123_test.pdf",
            "preferred_text_json_path": "data\\extraction_json\\text\\123.json",
            "preferred_text_source": "full_text",
            "preferred_start_page": "1",
            "proceedings_detected": "false",
            "trim_status": "",
            "predicted_source_category": "single_case_report",
            "predicted_source_subtype": "case_report",
            "predicted_confidence": "high",
            "predicted_likely_sps_case_count": "1",
            "predicted_count_confidence": "medium",
            "predicted_count_basis": "single_case_text_signal",
            "predicted_count_manual_review_required": "false",
            "predicted_count_reason": "count_basis=single_case_text_signal",
            "predicted_categorisation_reason": "case_markers=case report",
            "selection_created_at_utc": "2026-04-05T12:00:00+00:00",
        }
        response_row = gold.build_response_row(
            queue_row=queue_row,
            prediction_correct=False,
            reviewed_source_category="case_series_or_multi_case",
            reviewed_extractable_sps_case_count="2",
            pdf_content_alignment_tag="appears_matched",
            reviewer_notes="Two patients are described.",
            reviewer_id="reviewer_a",
        )

        snapshot_rows = gold.build_gold_snapshot_rows([queue_row], {"123": response_row})
        self.assertEqual(snapshot_rows[0]["review_status"], "reviewed")
        self.assertEqual(snapshot_rows[0]["reviewed_source_category"], "case_series_or_multi_case")
        self.assertEqual(snapshot_rows[0]["reviewed_extractable_sps_case_count"], "2")
        self.assertEqual(snapshot_rows[0]["prediction_correct"], "false")

    def test_build_response_row_uses_zero_when_prediction_is_accepted_with_blank_count(self) -> None:
        queue_row = {
            "round_id": "2026-04-05_round_01",
            "paper_id": "124",
            "title": "Blank count paper",
            "selection_bucket": "high_confidence_control",
            "predicted_source_category": "single_case_report",
            "predicted_likely_sps_case_count": "",
        }

        response_row = gold.build_response_row(
            queue_row=queue_row,
            prediction_correct=True,
            reviewed_source_category="single_case_report",
            reviewed_extractable_sps_case_count="0",
            pdf_content_alignment_tag="appears_matched",
            reviewer_notes="",
            reviewer_id="reviewer_a",
        )

        self.assertEqual(response_row["reviewed_extractable_sps_case_count"], "0")
        self.assertEqual(response_row["prediction_correct"], "true")

    def test_bucket_accuracy_summary_uses_exact_matches(self) -> None:
        summary = benchmark.summarise_bucket_accuracy(
            [
                {
                    "selection_bucket": "conference_edge",
                    "category_match": True,
                    "count_match": False,
                },
                {
                    "selection_bucket": "conference_edge",
                    "category_match": False,
                    "count_match": False,
                },
                {
                    "selection_bucket": "count_ambiguity",
                    "category_match": True,
                    "count_match": True,
                },
            ]
        )

        self.assertEqual(summary["conference_edge"]["rows"], 2)
        self.assertAlmostEqual(summary["conference_edge"]["category_accuracy"], 0.5)
        self.assertAlmostEqual(summary["conference_edge"]["count_accuracy"], 0.0)
        self.assertAlmostEqual(summary["count_ambiguity"]["category_accuracy"], 1.0)
        self.assertAlmostEqual(summary["count_ambiguity"]["count_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
