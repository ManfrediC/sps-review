from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.pipelines.stage06_counting import overrides
from src.validation import _stage06_backfill as backfill
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

    def test_load_review_rows_from_run_does_not_attach_latest_foreign_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_root = root / "stage06_count_runs"
            run_dir = run_root / "stage06_demo"
            later_run_dir = run_root / "stage06_later"
            (run_dir / "results").mkdir(parents=True)
            (later_run_dir / "results").mkdir(parents=True)
            (later_run_dir / "candidate_packages").mkdir()
            (later_run_dir / "count_decisions").mkdir()
            (later_run_dir / "count_evidence").mkdir()

            artifact_registry_path = root / "paper_artifact_registry.csv"
            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "pdf_paths_relative", "text_json_path"])
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "71",
                        "pdf_paths_relative": r"data\pdf_original\71_test.pdf",
                        "text_json_path": r"data\extraction_json\text\71.json",
                    }
                )

            (run_dir / "results" / "71.json").write_text(
                json.dumps(
                    {
                        "paper_id": "71",
                        "count_row": {
                            "paper_id": "71",
                            "title": "Example paper",
                            "likely_sps_case_count": "3",
                            "count_verification_status": "llm_candidate_exact",
                            "count_candidate_json_path": r"results\stage06_count_runs\stage06_demo\candidate_packages\71.json",
                        },
                        "source_text_json_path": r"data\extraction_json\text\71.json",
                        "preferred_text_json_path": r"data\extraction_json\text\71.json",
                    }
                ),
                encoding="utf-8",
            )
            (later_run_dir / "results" / "71.json").write_text("{}", encoding="utf-8")
            (later_run_dir / "candidate_packages" / "71.json").write_text("{}", encoding="utf-8")
            (later_run_dir / "count_decisions" / "71.json").write_text("{}", encoding="utf-8")
            (later_run_dir / "count_evidence" / "71.json").write_text("{}", encoding="utf-8")

            original_run_root = review.RUN_ROOT
            try:
                review.RUN_ROOT = run_root
                rows = review.load_review_rows_from_run(run_dir, artifact_registry_path=artifact_registry_path)
            finally:
                review.RUN_ROOT = original_run_root

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["run_id"], "stage06_demo")
        self.assertEqual(row["count_decision_json_path"], "")
        self.assertEqual(row["count_evidence_json_path"], "")
        self.assertEqual(row.get("attached_run_id", ""), "")

    def test_save_response_row_preserves_review_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            review_dir = root / "review_scope"
            override_ledger_path = root / "source_sps_case_count_manual_review.csv"
            review.ensure_review_workspace(
                review_dir,
                source_scope_id="demo_scope",
                source_scope_label="demo_scope",
                source_kind="run_directory",
                source_path_text="results/stage06_count_runs/demo_scope",
            )
            review_rows = [
                {
                    "paper_id": "71",
                    "title": "Paper 71",
                    "likely_sps_case_count": "3",
                    "count_verification_status": "llm_candidate_exact",
                    "count_original_cohort_provenance_uncertain": "true",
                },
                {
                    "paper_id": "214",
                    "title": "Paper 214",
                    "likely_sps_case_count": "2",
                    "count_verification_status": "llm_candidate_exact",
                    "count_original_cohort_provenance_uncertain": "false",
                },
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

            review.save_response_row(
                review_dir,
                review_rows,
                row_214,
                override_ledger_path=override_ledger_path,
            )
            responses_by_id = review.save_response_row(
                review_dir,
                review_rows,
                row_71,
                override_ledger_path=override_ledger_path,
            )

            saved_rows = review.load_csv_rows(review.responses_path(review_dir))
            override_rows = overrides.load_override_rows(override_ledger_path)

        self.assertEqual(list(responses_by_id), ["214", "71"])
        self.assertEqual([row["paper_id"] for row in saved_rows], ["71", "214"])
        self.assertEqual(saved_rows[0]["reviewed_count"], "3")
        self.assertEqual(saved_rows[0]["predicted_original_cohort_provenance_uncertain"], "true")
        self.assertEqual(saved_rows[0]["reviewed_original_cohort_provenance_uncertain"], "true")
        self.assertEqual(saved_rows[1]["review_status"], "needs_follow_up")
        self.assertEqual([row["paper_id"] for row in override_rows], ["71", "214"])
        self.assertEqual(override_rows[0]["review_status"], "reviewed")

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

    def test_build_review_comments_rows_seeds_competing_count_commentary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            candidate_path = root / "404_candidates.json"
            decision_path = root / "404_decision.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "cand01",
                                "proposed_count": 19,
                                "count_basis": "diagnosis_specific_suffix_count",
                                "evidence_text": "SPS (19,20), we performed a randomized trial.",
                            },
                            {
                                "candidate_id": "cand02",
                                "proposed_count": 16,
                                "count_basis": "abstract_count_signal",
                                "evidence_text": "The following patients were randomised: (a) 16 patients with anti-GAD antibody-positive SPS.",
                            },
                            {
                                "candidate_id": "cand03",
                                "proposed_count": 16,
                                "count_basis": "early_body_count_signal",
                                "evidence_text": "At enrolment, all 16 patients were receiving treatment for SPS.",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            decision_path.write_text(
                json.dumps(
                    {
                        "decision": {
                            "decision_type": "candidate_exact",
                            "count_confidence": "medium",
                        }
                    }
                ),
                encoding="utf-8",
            )

            rows = backfill.build_review_comments_rows(
                [
                    {
                        "paper_id": "404",
                        "title": "Example 404",
                        "likely_sps_case_count": "19",
                        "count_verification_status": "llm_manual_review_required",
                        "count_manual_review_required": "true",
                        "count_candidate_json_path": str(candidate_path),
                        "count_decision_json_path": str(decision_path),
                    }
                ]
            )

        self.assertEqual(len(rows), 1)
        comment = rows[0]["review_comment"]
        self.assertIn("Pipeline output: 19.", comment)
        self.assertIn("Extracted counts seen: 19 (diagnosis_specific_suffix_count), 16 (abstract_count_signal; early_body_count_signal).", comment)
        self.assertIn("Review trigger: verification_status=llm_manual_review_required.", comment)
        self.assertIn("GPT decision: candidate_exact; medium.", comment)
        self.assertIn("16 looks likelier because 19 only comes from a citation-like suffix snippet.", comment)

    def test_build_review_comments_rows_prefers_manual_override_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_scope_id",
                        "source_scope_label",
                        "paper_id",
                        "title",
                        "predicted_count",
                        "predicted_original_cohort_provenance_uncertain",
                        "predicted_verification_status",
                        "prediction_correct",
                        "reviewed_count",
                        "reviewed_original_cohort_provenance_uncertain",
                        "review_status",
                        "reviewer_notes",
                        "reviewer_id",
                        "reviewed_at_utc",
                        "updated_at_utc",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "source_scope_id": "stage06_backfill_demo",
                        "source_scope_label": "stage06_backfill_demo",
                        "paper_id": "214",
                        "title": "Example 214",
                        "predicted_count": "1",
                        "predicted_original_cohort_provenance_uncertain": "true",
                        "predicted_verification_status": "llm_manual_review_required",
                        "prediction_correct": "false",
                        "reviewed_count": "4",
                        "reviewed_original_cohort_provenance_uncertain": "false",
                        "review_status": "reviewed",
                        "reviewer_notes": "Table 1 supports four SPS patients.",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-18T10:00:00Z",
                        "updated_at_utc": "2026-04-18T10:00:00Z",
                    }
                )

            rows = backfill.build_review_comments_rows(
                [
                    {
                        "paper_id": "214",
                        "title": "Example 214",
                        "likely_sps_case_count": "4",
                        "count_verification_status": "manual_review_override",
                        "count_manual_review_required": "false",
                    }
                ],
                manual_review_path=manual_review_path,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_comment"], "Table 1 supports four SPS patients.")

    def test_build_review_comments_rows_includes_model_rationale_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            candidate_path = root / "472_candidates.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "cand01",
                                "proposed_count": 20,
                                "count_basis": "abstract_count_signal",
                                "evidence_text": "The sera were derived from 20 well-characterized SPS patients and 20 controls.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows = backfill.build_review_comments_rows(
                [
                    {
                        "paper_id": "472",
                        "title": "Example 472",
                        "likely_sps_case_count": "20",
                        "count_verification_status": "llm_bounded_alternative",
                        "count_manual_review_required": "true",
                        "count_candidate_json_path": str(candidate_path),
                        "count_reason": (
                            "challenge_stage=primary | verification_status=llm_bounded_alternative | "
                            "llm_count_confidence=medium | The paper explicitly reports that the sera were "
                            "derived from 20 well-characterized SPS patients and 20 controls, so the "
                            "extractable SPS-spectrum cohort is 20 rather than 0."
                        ),
                    }
                ]
            )

        self.assertEqual(len(rows), 1)
        comment = rows[0]["review_comment"]
        self.assertIn("Pipeline output: 20.", comment)
        self.assertIn("Model rationale: The paper explicitly reports that the sera were derived from 20 well-characterized SPS patients and 20 controls, so the extractable SPS-spectrum cohort is 20 rather than 0.", comment)

    def test_build_review_comments_rows_refreshes_prior_auto_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            candidate_path = root / "472_candidates.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "cand01",
                                "proposed_count": 20,
                                "count_basis": "abstract_count_signal",
                                "evidence_text": "The sera were derived from 20 well-characterized SPS patients and 20 controls.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows = backfill.build_review_comments_rows(
                [
                    {
                        "paper_id": "472",
                        "title": "Example 472",
                        "likely_sps_case_count": "20",
                        "count_verification_status": "llm_bounded_alternative",
                        "count_manual_review_required": "true",
                        "count_candidate_json_path": str(candidate_path),
                        "count_reason": (
                            "challenge_stage=primary | verification_status=llm_bounded_alternative | "
                            "llm_count_confidence=medium | The paper explicitly reports that the sera were "
                            "derived from 20 well-characterized SPS patients and 20 controls, so the "
                            "extractable SPS-spectrum cohort is 20 rather than 0."
                        ),
                    }
                ],
                existing_rows_by_id={
                    "472": {
                        "paper_id": "472",
                        "title": "Example 472",
                        "review_comment": "Pipeline output: 20. Extracted counts seen: 20 (abstract_count_signal).",
                        "assessment": "",
                        "failure_modes": "",
                    }
                },
            )

        self.assertEqual(len(rows), 1)
        self.assertIn("Model rationale:", rows[0]["review_comment"])

    def test_build_review_comments_rows_keeps_zero_count_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            candidate_path = root / "472_zero_candidates.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "cand01",
                                "proposed_count": 0,
                                "count_basis": "lab_context_no_extractable_count",
                                "evidence_text": "The sera analyzed were derived from 20 well-characterized SPS patients and 20 controls.",
                            },
                            {
                                "candidate_id": "cand02",
                                "proposed_count": 0,
                                "count_basis": "no_reliable_count_signal",
                                "evidence_text": "The sera analyzed were derived from 20 well-characterized SPS patients and 20 controls.",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows = backfill.build_review_comments_rows(
                [
                    {
                        "paper_id": "472",
                        "title": "Example 472",
                        "likely_sps_case_count": "20",
                        "count_verification_status": "llm_bounded_alternative",
                        "count_manual_review_required": "true",
                        "count_candidate_json_path": str(candidate_path),
                        "count_reason": (
                            "challenge_stage=primary | verification_status=llm_bounded_alternative | "
                            "llm_count_confidence=medium | The paper explicitly reports that the sera were "
                            "derived from 20 well-characterized SPS patients and 20 controls, so the "
                            "extractable SPS-spectrum cohort is 20 rather than 0."
                        ),
                    }
                ]
            )

        self.assertEqual(len(rows), 1)
        comment = rows[0]["review_comment"]
        self.assertIn("Extracted counts seen: 0 (lab_context_no_extractable_count; no_reliable_count_signal).", comment)
        self.assertIn("Model rationale:", comment)
        self.assertNotIn("looks likelier because", comment)

    def test_review_notes_markdown_ignores_plain_candidate_exact_manual_flag_without_hard_conflict(self) -> None:
        notes = backfill.review_notes_markdown(
            batch_manifest={
                "batch_id": "b001",
                "combined_output_csv_path": "qa/demo_combined.csv",
                "inspection_md_path": "qa/demo_inspection.md",
                "review_comments_csv_path": "qa/demo_review_comments.csv",
            },
            review_rows=[
                {
                    "paper_id": "71",
                    "title": "Example 71",
                    "likely_sps_case_count": "1",
                    "count_verification_status": "llm_candidate_exact",
                    "count_manual_review_required": "true",
                    "count_reason": "verification_status=llm_candidate_exact",
                },
                {
                    "paper_id": "214",
                    "title": "Example 214",
                    "likely_sps_case_count": "1",
                    "count_verification_status": "llm_manual_review_required",
                    "count_manual_review_required": "true",
                    "count_reason": (
                        "verification_status=llm_manual_review_required | "
                        "explicit_sps_subgroup_conflict=4 vs 1"
                    ),
                },
            ],
        )

        self.assertIn("Likely clean on first pass: 71", notes)
        self.assertIn("Must review: 214", notes)
        self.assertNotIn("`71`: Pipeline output", notes)
        self.assertIn("`214`: Pipeline output: 1.", notes)
        self.assertIn("Review trigger: verification_status=llm_manual_review_required; explicit_sps_subgroup_conflict=4 vs 1.", notes)


if __name__ == "__main__":
    unittest.main()
