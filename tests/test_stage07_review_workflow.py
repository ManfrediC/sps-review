from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.validation import _stage07_review as review


class TestStage07ReviewWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.run_root = self.tmp_path / "20260419T120000Z_stage07_smoke"
        self.run_root.mkdir(parents=True)
        (self.run_root / "text_case_series_units").mkdir()

        self.references_path = self.tmp_path / "references.csv"
        self.source_path = self.tmp_path / "source.csv"
        self.stage06_path = self.tmp_path / "stage06.csv"

        self._old_references_path = review.REFERENCES_PATH
        self._old_source_path = review.SOURCE_CATEGORISATION_PATH
        self._old_stage06_path = review.SOURCE_CASE_COUNT_PATH
        review.REFERENCES_PATH = self.references_path
        review.SOURCE_CATEGORISATION_PATH = self.source_path
        review.SOURCE_CASE_COUNT_PATH = self.stage06_path

    def tearDown(self) -> None:
        review.REFERENCES_PATH = self._old_references_path
        review.SOURCE_CATEGORISATION_PATH = self._old_source_path
        review.SOURCE_CASE_COUNT_PATH = self._old_stage06_path
        self.temp_dir.cleanup()

    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_qa_pack_writes_combined_csv_and_review_scaffold(self) -> None:
        selection_path = self.run_root / "selection.json"
        selection_path.write_text(
            json.dumps({"paper_ids": ["9001"]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.write_csv(
            self.run_root / "case_series_split_registry.csv",
            ["paper_id", "publication_status", "published_unit_count"],
            [{"paper_id": "9001", "publication_status": "publish_all_units", "published_unit_count": "2"}],
        )
        payload = {
            "paper_id": "9001",
            "source_text_json_path": "data/extraction_json/text/9001.json",
            "source_route": {
                "contains_individual_level_data": True,
                "contains_group_level_data": False,
                "preferred_langextract_mode": "individual_case_split",
            },
            "stage06_prior": {
                "final_count": 2,
                "count_confidence": "high",
                "count_verification_status": "manual_review_override",
                "granularity": "individual-level",
            },
            "publication_decision": {
                "status": "publish_all_units",
                "manual_review_required": False,
                "reason_code": "individual_units_match_stage06_count",
                "reason": "Explicit individual unit headings matched the stage-06 patient-count prior.",
            },
            "stage07_resolution_summary": {
                "published_unit_count": 2,
                "published_individual_count": 2,
                "published_group_count": 0,
                "shared_context_count": 1,
                "has_unresolved_remainder": False,
            },
            "shared_context_blocks": [
                {
                    "context_id": "9001__shared__001",
                    "applies_to_unit_ids": ["9001__individual__001", "9001__individual__002"],
                    "source_span_refs": [
                        {"ref_type": "line_range", "page_index": 0, "line_start": 1, "line_end": 1}
                    ],
                    "text": "Both patients had axial stiffness.",
                }
            ],
            "units": [
                {
                    "unit_id": "9001__individual__001",
                    "unit_type": "individual",
                    "unit_label": "Patient 1",
                    "unit_text": "Patient 1 had axial rigidity and painful spasms.",
                    "source_span_refs": [
                        {"ref_type": "line_range", "page_index": 0, "line_start": 10, "line_end": 12}
                    ],
                    "linked_shared_context_ids": ["9001__shared__001"],
                },
                {
                    "unit_id": "9001__individual__002",
                    "unit_type": "individual",
                    "unit_label": "Patient 2",
                    "unit_text": "Patient 2 had progressive stiffness with startle-provoked spasms.",
                    "source_span_refs": [
                        {"ref_type": "line_range", "page_index": 0, "line_start": 14, "line_end": 16}
                    ],
                    "linked_shared_context_ids": ["9001__shared__001"],
                },
            ],
            "unresolved_remainder": {"present": False, "reason_code": "", "text": ""},
        }
        (self.run_root / "text_case_series_units" / "9001.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.write_csv(
            self.references_path,
            ["Covidence", "Title"],
            [{"Covidence": "9001", "Title": "Example case series"}],
        )
        self.write_csv(
            self.source_path,
            [
                "paper_id",
                "contains_individual_level_data",
                "contains_group_level_data",
                "preferred_langextract_mode",
            ],
            [
                {
                    "paper_id": "9001",
                    "contains_individual_level_data": "true",
                    "contains_group_level_data": "false",
                    "preferred_langextract_mode": "individual_case_split",
                }
            ],
        )
        self.write_csv(
            self.stage06_path,
            [
                "paper_id",
                "likely_sps_case_count",
                "count_confidence",
                "count_verification_status",
            ],
            [
                {
                    "paper_id": "9001",
                    "likely_sps_case_count": "2",
                    "count_confidence": "high",
                    "count_verification_status": "manual_review_override",
                }
            ],
        )

        paths = review.build_qa_pack(self.run_root)

        combined_csv_path = self.run_root / f"{self.run_root.name}_combined.csv"
        inspection_path = self.run_root / f"{self.run_root.name}_inspection.md"
        review_comments_path = self.run_root / f"{self.run_root.name}_review_comments.csv"
        self.assertEqual(paths["combined_csv_path"], review.display_path(combined_csv_path))
        self.assertTrue(combined_csv_path.exists())
        self.assertTrue(inspection_path.exists())
        self.assertTrue(review_comments_path.exists())

        with combined_csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["paper_id"], "9001")
        self.assertEqual(rows[0]["publication_status"], "publish_all_units")
        self.assertEqual(rows[0]["unit_labels"], "Patient 1 | Patient 2")

        inspection_text = inspection_path.read_text(encoding="utf-8")
        self.assertIn("Patient 1", inspection_text)
        self.assertIn("Both patients had axial stiffness.", inspection_text)


if __name__ == "__main__":
    unittest.main()
