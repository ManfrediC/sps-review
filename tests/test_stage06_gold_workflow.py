from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.validation import _stage06_gold as gold
from src.validation import _stage06_review as review


class TestStage06GoldWorkflow(unittest.TestCase):
    def test_build_gold_payload_overrides_predicted_truth(self) -> None:
        gold_row = {
            "paper_id": "71",
            "covidence_id": "71",
            "title": "Example title",
            "authors": "Example Authors",
            "published_year": "1995",
            "journal": "Neurology",
            "round_id": "2026-04-05_round_01",
            "selection_bucket": "conference_edge",
            "selection_signals": "count_ambiguity",
            "preferred_text_json_path": r"data\extraction_json\text\71.json",
            "preferred_text_source": "full_text",
            "predicted_source_category": "observational_group_study",
            "predicted_source_subtype": "retrospective_or_cohort_group_study",
            "predicted_likely_sps_case_count": "9",
            "prediction_correct": "false",
            "reviewed_source_category": "review_article",
            "reviewed_extractable_sps_case_count": "0",
            "pdf_content_alignment_tag": "appears_matched",
            "reviewer_notes": "Review article, not an original cohort.",
            "reviewer_id": "tester",
            "reviewed_at_utc": "2026-04-15T10:00:00+00:00",
        }
        count_row = {
            "paper_id": "71",
            "covidence_id": "71",
            "title": "Example title",
            "authors": "Example Authors",
            "source_category": "observational_group_study",
            "source_subtype": "retrospective_or_cohort_group_study",
            "preferred_text_json_path": r"data\extraction_json\text\71.json",
            "preferred_text_source": "full_text",
            "likely_sps_case_count": "9",
        }
        source_row = {
            "paper_id": "71",
            "title": "Example title",
            "authors": "Example Authors",
            "source_category": "observational_group_study",
            "source_subtype": "retrospective_or_cohort_group_study",
        }
        artifact_row = {
            "text_json_path": r"data\extraction_json\text\71.json",
            "pdf_filenames": "71_example.pdf",
            "pdf_paths_relative": r"data\pdf_original\71_example.pdf",
        }
        attached_run_payloads = {
            "run_id": "stage06_llm_test_71",
            "result_json_path": r"results\stage06_count_runs\stage06_llm_test_71\results\71.json",
            "candidate_json_path": r"results\stage06_count_runs\stage06_llm_test_71\candidate_packages\71.json",
            "count_decision_json_path": "",
            "count_evidence_json_path": "",
            "result_payload": {"paper_id": "71"},
            "candidate_payload": {"paper_id": "71", "candidates": []},
            "count_decision_payload": None,
            "count_evidence_payload": None,
        }

        payload = gold.build_gold_payload(
            gold_row=gold_row,
            count_row=count_row,
            source_row=source_row,
            artifact_row=artifact_row,
            attached_run_payloads=attached_run_payloads,
        )

        self.assertEqual(payload["paper_id"], "71")
        self.assertEqual(payload["count_row"]["likely_sps_case_count"], "0")
        self.assertEqual(payload["count_row"]["source_category"], "review_article")
        self.assertEqual(payload["count_row"]["source_subtype"], "")
        self.assertEqual(payload["count_row"]["count_eligible"], "false")
        self.assertEqual(payload["count_row"]["count_basis"], "manual_gold_review")
        self.assertEqual(payload["gold_review"]["prediction_correct"], False)
        self.assertEqual(payload["attached_run_artifacts"]["run_id"], "stage06_llm_test_71")
        self.assertEqual(
            payload["prediction_snapshot"]["live_count_registry_row"]["likely_sps_case_count"],
            "9",
        )

    def test_bootstrap_stage06_gold_store_writes_active_json_and_flags_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            gold_master_path = root / "04_categorisation_gold_standard.csv"
            source_registry_path = root / "source_categorisation_registry.csv"
            count_registry_path = root / "source_sps_case_count_registry.csv"
            artifact_registry_path = root / "paper_artifact_registry.csv"
            output_dir = root / "stage06_count_gold"
            run_root = root / "stage06_count_runs"

            with gold_master_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "round_id",
                        "paper_id",
                        "covidence_id",
                        "title",
                        "authors",
                        "published_year",
                        "journal",
                        "selection_bucket",
                        "selection_signals",
                        "preferred_text_json_path",
                        "preferred_text_source",
                        "predicted_source_category",
                        "predicted_source_subtype",
                        "predicted_likely_sps_case_count",
                        "prediction_correct",
                        "review_status",
                        "reviewed_source_category",
                        "reviewed_extractable_sps_case_count",
                        "pdf_content_alignment_tag",
                        "reviewer_notes",
                        "reviewer_id",
                        "reviewed_at_utc",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "round_id": "round_01",
                        "paper_id": "71",
                        "covidence_id": "71",
                        "title": "Paper 71",
                        "authors": "Authors 71",
                        "published_year": "1995",
                        "journal": "Neurology",
                        "selection_bucket": "conference_edge",
                        "selection_signals": "count_ambiguity",
                        "preferred_text_json_path": r"data\extraction_json\text\71.json",
                        "preferred_text_source": "full_text",
                        "predicted_source_category": "observational_group_study",
                        "predicted_source_subtype": "retrospective",
                        "predicted_likely_sps_case_count": "9",
                        "prediction_correct": "false",
                        "review_status": "reviewed",
                        "reviewed_source_category": "observational_group_study",
                        "reviewed_extractable_sps_case_count": "3",
                        "pdf_content_alignment_tag": "appears_matched",
                        "reviewer_notes": "",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-15T10:00:00+00:00",
                    }
                )
                writer.writerow(
                    {
                        "round_id": "round_01",
                        "paper_id": "72",
                        "covidence_id": "72",
                        "title": "Paper 72",
                        "authors": "Authors 72",
                        "published_year": "1996",
                        "journal": "Journal 72",
                        "selection_bucket": "count_ambiguity",
                        "selection_signals": "count_ambiguity",
                        "preferred_text_json_path": r"data\extraction_json\text\72.json",
                        "preferred_text_source": "full_text",
                        "predicted_source_category": "conference_abstract",
                        "predicted_source_subtype": "conference",
                        "predicted_likely_sps_case_count": "1",
                        "prediction_correct": "false",
                        "review_status": "reviewed",
                        "reviewed_source_category": "conference_abstract",
                        "reviewed_extractable_sps_case_count": "1",
                        "pdf_content_alignment_tag": "appears_matched",
                        "reviewer_notes": "",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-15T10:05:00+00:00",
                    }
                )
                writer.writerow(
                    {
                        "round_id": "round_02",
                        "paper_id": "72",
                        "covidence_id": "72",
                        "title": "Paper 72",
                        "authors": "Authors 72",
                        "published_year": "1996",
                        "journal": "Journal 72",
                        "selection_bucket": "count_ambiguity",
                        "selection_signals": "count_ambiguity",
                        "preferred_text_json_path": r"data\extraction_json\text\72.json",
                        "preferred_text_source": "full_text",
                        "predicted_source_category": "conference_abstract",
                        "predicted_source_subtype": "conference",
                        "predicted_likely_sps_case_count": "1",
                        "prediction_correct": "false",
                        "review_status": "reviewed",
                        "reviewed_source_category": "conference_abstract",
                        "reviewed_extractable_sps_case_count": "2",
                        "pdf_content_alignment_tag": "appears_matched",
                        "reviewer_notes": "",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-15T10:06:00+00:00",
                    }
                )

            for path in (source_registry_path, count_registry_path):
                with path.open("w", encoding="utf-8", newline="") as handle:
                    if path == source_registry_path:
                        fieldnames = ["paper_id", "title", "authors", "source_category", "source_subtype"]
                        rows = [
                            {
                                "paper_id": "71",
                                "title": "Paper 71",
                                "authors": "Authors 71",
                                "source_category": "observational_group_study",
                                "source_subtype": "retrospective",
                            },
                            {
                                "paper_id": "72",
                                "title": "Paper 72",
                                "authors": "Authors 72",
                                "source_category": "conference_abstract",
                                "source_subtype": "conference",
                            },
                        ]
                    else:
                        fieldnames = [
                            "paper_id",
                            "covidence_id",
                            "title",
                            "authors",
                            "source_category",
                            "source_subtype",
                            "preferred_text_json_path",
                            "preferred_text_source",
                            "likely_sps_case_count",
                        ]
                        rows = [
                            {
                                "paper_id": "71",
                                "covidence_id": "71",
                                "title": "Paper 71",
                                "authors": "Authors 71",
                                "source_category": "observational_group_study",
                                "source_subtype": "retrospective",
                                "preferred_text_json_path": r"data\extraction_json\text\71.json",
                                "preferred_text_source": "full_text",
                                "likely_sps_case_count": "9",
                            },
                            {
                                "paper_id": "72",
                                "covidence_id": "72",
                                "title": "Paper 72",
                                "authors": "Authors 72",
                                "source_category": "conference_abstract",
                                "source_subtype": "conference",
                                "preferred_text_json_path": r"data\extraction_json\text\72.json",
                                "preferred_text_source": "full_text",
                                "likely_sps_case_count": "1",
                            },
                        ]
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["paper_id", "pdf_filenames", "pdf_paths_relative", "text_json_path"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "71",
                        "pdf_filenames": "71.pdf",
                        "pdf_paths_relative": r"data\pdf_original\71.pdf",
                        "text_json_path": r"data\extraction_json\text\71.json",
                    }
                )
                writer.writerow(
                    {
                        "paper_id": "72",
                        "pdf_filenames": "72.pdf",
                        "pdf_paths_relative": r"data\pdf_original\72.pdf",
                        "text_json_path": r"data\extraction_json\text\72.json",
                    }
                )

            run_dir = run_root / "stage06_demo"
            (run_dir / "results").mkdir(parents=True)
            (run_dir / "candidate_packages").mkdir()
            (run_dir / "results" / "71.json").write_text('{"paper_id":"71"}', encoding="utf-8")
            (run_dir / "candidate_packages" / "71.json").write_text('{"paper_id":"71"}', encoding="utf-8")

            original_run_root = review.RUN_ROOT
            try:
                review.RUN_ROOT = run_root
                manifest = gold.bootstrap_stage06_gold_store(
                    gold_master_path=gold_master_path,
                    source_registry_path=source_registry_path,
                    count_registry_path=count_registry_path,
                    artifact_registry_path=artifact_registry_path,
                    gold_papers_dir=output_dir / "papers",
                    manifest_path=output_dir / "manifest.json",
                )
            finally:
                review.RUN_ROOT = original_run_root

            self.assertEqual(manifest["active_paper_count"], 1)
            self.assertEqual(manifest["conflict_paper_count"], 1)
            self.assertTrue((output_dir / "papers" / "71.json").exists())
            self.assertFalse((output_dir / "papers" / "72.json").exists())

            written_payload = gold.load_json(output_dir / "papers" / "71.json")
            self.assertEqual(written_payload["count_row"]["likely_sps_case_count"], "3")
            self.assertEqual(written_payload["attached_run_artifacts"]["run_id"], "stage06_demo")


if __name__ == "__main__":
    unittest.main()
