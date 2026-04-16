from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.pipelines.stage06_counting import overrides


class TestStage06Overrides(unittest.TestCase):
    def test_upsert_override_row_writes_sorted_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            ledger_path = Path(tmp_dir_text) / "source_sps_case_count_manual_review.csv"
            overrides.upsert_override_row(
                {
                    "source_scope_id": "scope_b",
                    "source_scope_label": "scope_b",
                    "paper_id": "214",
                    "title": "Paper 214",
                    "predicted_count": "2",
                    "predicted_verification_status": "llm_candidate_exact",
                    "prediction_correct": "false",
                    "reviewed_count": "3",
                    "review_status": "reviewed",
                    "reviewer_notes": "Updated count.",
                    "reviewer_id": "tester",
                    "reviewed_at_utc": "2026-04-16T10:00:00+00:00",
                    "updated_at_utc": "2026-04-16T10:00:00+00:00",
                },
                path=ledger_path,
            )
            overrides.upsert_override_row(
                {
                    "source_scope_id": "scope_a",
                    "source_scope_label": "scope_a",
                    "paper_id": "71",
                    "title": "Paper 71",
                    "predicted_count": "3",
                    "predicted_verification_status": "llm_candidate_exact",
                    "prediction_correct": "true",
                    "reviewed_count": "3",
                    "review_status": "reviewed",
                    "reviewer_notes": "",
                    "reviewer_id": "tester",
                    "reviewed_at_utc": "2026-04-16T09:00:00+00:00",
                    "updated_at_utc": "2026-04-16T09:00:00+00:00",
                },
                path=ledger_path,
            )

            rows = overrides.load_override_rows(ledger_path)

        self.assertEqual([row["paper_id"] for row in rows], ["71", "214"])

    def test_apply_override_to_count_row_marks_review_override(self) -> None:
        overridden = overrides.apply_override_to_count_row(
            {
                "paper_id": "214",
                "likely_sps_case_count": "2",
                "count_confidence": "medium",
                "count_basis": "llm_bounded_alternative",
                "count_manual_review_required": "true",
                "count_reason": "verification_status=llm_manual_review_required",
                "count_version": "hybrid_v1_gpt-5.4",
                "count_audit_status": "hybrid_local_gpt",
                "count_verification_status": "llm_manual_review_required",
                "counted_at_utc": "2026-04-16T10:00:00+00:00",
            },
            {
                "source_scope_id": "hybrid_run",
                "source_scope_label": "hybrid_run",
                "paper_id": "214",
                "title": "Paper 214",
                "predicted_count": "2",
                "predicted_verification_status": "llm_manual_review_required",
                "prediction_correct": "false",
                "reviewed_count": "3",
                "review_status": "reviewed",
                "reviewer_notes": "Three original cases.",
                "reviewer_id": "tester",
                "reviewed_at_utc": "2026-04-16T10:05:00+00:00",
                "updated_at_utc": "2026-04-16T10:06:00+00:00",
            },
        )

        self.assertEqual(overridden["likely_sps_case_count"], "3")
        self.assertEqual(overridden["count_confidence"], "high")
        self.assertEqual(overridden["count_basis"], "manual_review_override")
        self.assertEqual(overridden["count_manual_review_required"], "false")
        self.assertEqual(overridden["count_verification_status"], "manual_review_override")
        self.assertEqual(overridden["count_audit_status"], "manual_review_override")
        self.assertEqual(overridden["counted_at_utc"], "2026-04-16T10:06:00+00:00")
        self.assertTrue(overridden["count_version"].endswith("+manual_review_override"))


if __name__ == "__main__":
    unittest.main()
