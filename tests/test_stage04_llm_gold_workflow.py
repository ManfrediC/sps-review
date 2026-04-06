from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.validation import _stage04_llm_gold as llm_gold


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestStage04LlmGoldWorkflow(unittest.TestCase):
    def test_next_round_directory_uses_llm_category_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            (root / "stage04_llm_category_2026-04-05_round_01").mkdir()
            (root / "stage04_llm_category_2026-04-05_round_02").mkdir()

            next_dir = llm_gold.next_round_directory(root=root, date_label="2026-04-05")

        self.assertEqual(next_dir.name, "stage04_llm_category_2026-04-05_round_03")

    def test_load_selection_source_rows_excludes_reviewed_gold_and_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            source_registry_path = root / "source_registry.csv"
            artifact_registry_path = root / "artifact_registry.csv"
            write_csv(
                source_registry_path,
                [
                    {
                        "paper_id": "101",
                        "source_category": "single_case_report",
                        "classification_confidence": "high",
                    },
                    {
                        "paper_id": "102",
                        "source_category": "review_article",
                        "classification_confidence": "medium",
                    },
                    {
                        "paper_id": "103",
                        "source_category": "conference_abstract",
                        "classification_confidence": "low",
                    },
                    {
                        "paper_id": "104",
                        "source_category": "observational_group_study",
                        "classification_confidence": "high",
                    },
                ],
            )
            write_csv(
                artifact_registry_path,
                [
                    {
                        "paper_id": "101",
                        "pdf_present": "true",
                        "text_json_present": "true",
                        "pdf_paths_relative": "data\\pdf_original\\101.pdf",
                    },
                    {
                        "paper_id": "102",
                        "pdf_present": "true",
                        "text_json_present": "true",
                        "pdf_paths_relative": "data\\pdf_original\\102.pdf",
                    },
                    {
                        "paper_id": "103",
                        "pdf_present": "false",
                        "text_json_present": "true",
                        "pdf_paths_relative": "",
                    },
                    {
                        "paper_id": "104",
                        "pdf_present": "true",
                        "text_json_present": "true",
                        "pdf_paths_relative": "data\\pdf_original\\104.pdf",
                    },
                ],
            )

            with (
                mock.patch.object(llm_gold.gold, "load_manual_reviewed_ids", return_value={"101"}),
                mock.patch.object(llm_gold.gold, "load_existing_gold_ids", return_value={"102"}),
            ):
                rows, artifact_rows = llm_gold.load_selection_source_rows(
                    source_registry_path=source_registry_path,
                    artifact_registry_path=artifact_registry_path,
                )

        self.assertEqual([row["paper_id"] for row in rows], ["104"])
        self.assertIn("104", artifact_rows)

    def test_build_selection_queue_rows_joins_joint_count_prediction(self) -> None:
        selected_rows = [
            {
                "paper_id": "301",
                "covidence_id": "301",
                "title": "Joint prediction paper",
                "authors": "A Author",
                "published_year": "2024",
                "journal": "Neurology",
                "selection_bucket": "case_group_boundary",
                "selection_signals": "prediction_origin=llm",
                "preferred_text_json_path": "data/extraction_json/text/301.json",
                "preferred_text_source": "full_text",
                "proceedings_detected": "false",
                "trim_status": "",
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
                "classification_confidence": "high",
                "likely_case_count": "11",
                "categorisation_reason": "Category reasoning.",
                "categorisation_version": "llm_v1_gpt4.1",
            }
        ]
        artifact_rows = {
            "301": {
                "pdf_filenames": "301_test.pdf",
                "pdf_paths_relative": "data\\pdf_original\\301_test.pdf",
            }
        }
        count_rows = {
            "301": {
                "likely_sps_case_count": "12",
                "count_confidence": "medium",
                "count_basis": "llm_joint_extraction",
                "count_manual_review_required": "true",
                "count_reason": "Twelve original SPS-spectrum patients.",
            }
        }
        trim_rows: dict[str, dict[str, str]] = {}

        queue_rows = llm_gold.build_selection_queue_rows(
            selected_rows,
            artifact_rows=artifact_rows,
            count_rows=count_rows,
            trim_rows=trim_rows,
            round_dir=Path("qa/validation/source_categorisation/llm_category_review/stage04_llm_category_2026-04-05_round_99"),
        )

        self.assertEqual(len(queue_rows), 1)
        self.assertEqual(queue_rows[0]["predicted_source_category"], "observational_group_study")
        self.assertEqual(queue_rows[0]["predicted_likely_sps_case_count"], "12")
        self.assertEqual(queue_rows[0]["predicted_count_confidence"], "medium")
        self.assertEqual(queue_rows[0]["predicted_count_basis"], "llm_joint_extraction")
        self.assertEqual(queue_rows[0]["predicted_count_manual_review_required"], "true")
        self.assertEqual(queue_rows[0]["predicted_count_reason"], "Twelve original SPS-spectrum patients.")

    def test_build_gold_snapshot_rows_include_reviewed_count(self) -> None:
        queue_row = {
            "round_id": "stage04_llm_category_2026-04-05_round_01",
            "paper_id": "201",
            "covidence_id": "201",
            "title": "Test paper",
            "authors": "A Author",
            "published_year": "2024",
            "journal": "Neurology",
            "selection_bucket": "review_lab_edge",
            "selection_signals": "prediction_origin=llm",
            "pdf_filename": "201_test.pdf",
            "pdf_path_relative": "data\\pdf_original\\201_test.pdf",
            "preferred_text_json_path": "data\\extraction_json\\text\\201.json",
            "preferred_text_source": "full_text",
            "preferred_start_page": "1",
            "proceedings_detected": "false",
            "trim_status": "",
            "predicted_source_category": "review_article",
            "predicted_source_subtype": "review",
            "predicted_confidence": "medium",
            "predicted_likely_sps_case_count": "",
            "predicted_count_confidence": "",
            "predicted_count_basis": "",
            "predicted_count_manual_review_required": "",
            "predicted_count_reason": "",
            "predicted_categorisation_reason": "LLM reasoning.",
            "selection_created_at_utc": "2026-04-05T12:00:00+00:00",
        }
        response_row = llm_gold.build_response_row(
            queue_row=queue_row,
            prediction_correct=False,
            reviewed_source_category="non_clinical_basic_science",
            reviewed_extractable_sps_case_count="0",
            pdf_content_alignment_tag="appears_matched",
            reviewer_notes="Not a review.",
            reviewer_id="reviewer_a",
        )

        snapshot_rows = llm_gold.build_gold_snapshot_rows([queue_row], {"201": response_row})
        self.assertEqual(snapshot_rows[0]["review_status"], "reviewed")
        self.assertEqual(snapshot_rows[0]["reviewed_source_category"], "non_clinical_basic_science")
        self.assertEqual(snapshot_rows[0]["reviewed_extractable_sps_case_count"], "0")

    def test_build_gold_snapshot_rows_reopen_old_category_only_responses(self) -> None:
        queue_row = {
            "round_id": "stage04_llm_category_2026-04-05_round_01",
            "paper_id": "202",
            "covidence_id": "202",
            "title": "Legacy review row",
            "authors": "A Author",
            "published_year": "2024",
            "journal": "Neurology",
            "selection_bucket": "review_lab_edge",
            "selection_signals": "prediction_origin=llm",
            "pdf_filename": "202_test.pdf",
            "pdf_path_relative": "data\\pdf_original\\202_test.pdf",
            "preferred_text_json_path": "data\\extraction_json\\text\\202.json",
            "preferred_text_source": "full_text",
            "preferred_start_page": "1",
            "proceedings_detected": "false",
            "trim_status": "",
            "predicted_source_category": "review_article",
            "predicted_source_subtype": "review",
            "predicted_confidence": "medium",
            "predicted_likely_sps_case_count": "3",
            "predicted_count_confidence": "high",
            "predicted_count_basis": "llm_joint_extraction",
            "predicted_count_manual_review_required": "false",
            "predicted_count_reason": "Three original SPS patients.",
            "predicted_categorisation_reason": "LLM reasoning.",
            "selection_created_at_utc": "2026-04-05T12:00:00+00:00",
        }
        legacy_response_row = {
            "round_id": queue_row["round_id"],
            "paper_id": queue_row["paper_id"],
            "title": queue_row["title"],
            "selection_bucket": queue_row["selection_bucket"],
            "prediction_correct": "true",
            "reviewed_source_category": "review_article",
            "pdf_content_alignment_tag": "appears_matched",
            "reviewer_notes": "",
            "reviewer_id": "reviewer_a",
            "review_status": "reviewed",
            "reviewed_at_utc": "2026-04-05T12:05:00+00:00",
        }

        snapshot_rows = llm_gold.build_gold_snapshot_rows([queue_row], {"202": legacy_response_row})
        self.assertEqual(snapshot_rows[0]["review_status"], "pending")
        self.assertEqual(snapshot_rows[0]["reviewed_source_category"], "review_article")
        self.assertEqual(snapshot_rows[0]["reviewed_extractable_sps_case_count"], "")


if __name__ == "__main__":
    unittest.main()
