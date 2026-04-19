from __future__ import annotations

import unittest

from src.validation import run_stage07_smoke


class TestRunStage07Smoke(unittest.TestCase):
    def test_select_finalised_split_papers_prefers_finalised_multi_patient_rows(self) -> None:
        source_rows = [
            {"paper_id": "10", "preferred_langextract_mode": "individual_case_split"},
            {"paper_id": "11", "preferred_langextract_mode": "individual"},
            {"paper_id": "12", "preferred_langextract_mode": "individual_case_split"},
            {"paper_id": "13", "preferred_langextract_mode": "individual_case_split"},
        ]
        stage06_rows = [
            {
                "paper_id": "10",
                "likely_sps_case_count": "2",
                "count_verification_status": "manual_review_override",
                "count_manual_review_required": "false",
            },
            {
                "paper_id": "11",
                "likely_sps_case_count": "4",
                "count_verification_status": "manual_review_override",
                "count_manual_review_required": "false",
            },
            {
                "paper_id": "12",
                "likely_sps_case_count": "1",
                "count_verification_status": "manual_review_override",
                "count_manual_review_required": "false",
            },
            {
                "paper_id": "13",
                "likely_sps_case_count": "3",
                "count_verification_status": "",
                "count_manual_review_required": "false",
            },
        ]

        selected = run_stage07_smoke.select_finalised_split_papers(
            source_rows=source_rows,
            stage06_rows=stage06_rows,
            limit=10,
            minimum_stage06_count=2,
        )

        self.assertEqual(selected, ["10"])


if __name__ == "__main__":
    unittest.main()
