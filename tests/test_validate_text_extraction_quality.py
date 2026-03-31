from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "validation" / "validate_text_extraction_quality.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_text_extraction_quality", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestValidateTextExtractionQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.text_dir = self.tmp_path / "text"
        self.text_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_text_json(
        self,
        paper_id: str,
        *,
        source_filename: str,
        title: str,
        authors: str,
        year: str,
        ocr_applied: bool = False,
        n_pages: int = 1,
        suspicious_control_chars: int = 0,
        remaining_flags: list[str] | None = None,
        text: str = "",
    ) -> dict[str, str]:
        path = self.text_dir / f"{paper_id}.json"
        payload = {
            "paper_id": paper_id,
            "source_filename": source_filename,
            "ocr_applied": ocr_applied,
            "ocr_mode": "skip-text" if ocr_applied else "",
            "ocr_trigger_reasons": ["low_text"] if ocr_applied else [],
            "n_pages": n_pages,
            "suspicious_control_chars": suspicious_control_chars,
            "remaining_text_quality_flags": remaining_flags or [],
            "native_extraction_error": None,
            "ocr_error": None,
            "processing_error": None,
            "pages": [
                {
                    "page_index": 0,
                    "text": text or title,
                }
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "covidence_id": paper_id,
            "title": title,
            "authors": authors,
            "published_year": year,
        }

    def test_load_text_record_detects_proceedings_and_mojibake(self) -> None:
        registry_row = self.write_text_json(
            "101",
            source_filename="101_Annual Meeting Abstracts.pdf",
            title="Interesting SPS abstract",
            authors="Smith, Jane",
            year="2020",
            text="Interesting SPS abstract with ï¬ ligature issue",
        )

        record = self.module.load_text_record(
            self.text_dir / "101.json",
            registry_row,
            long_page_threshold=20,
        )

        self.assertTrue(record["proceedings_like"])
        self.assertGreater(record["mojibake_marker_count"], 0)
        self.assertFalse(record["long_document"])

    def test_sample_records_oversamples_high_risk_buckets_without_duplicates(self) -> None:
        records = []
        for paper_id in range(1, 31):
            record = {
                "covidence_id": str(paper_id),
                "text_json_path": f"{paper_id}.json",
                "source_filename": f"{paper_id}.pdf",
                "title": f"Title {paper_id}",
                "authors": "Smith, Jane",
                "published_year": "2020",
                "ocr_applied": paper_id <= 6,
                "ocr_mode": "skip-text" if paper_id <= 6 else "",
                "ocr_trigger_reasons": [],
                "n_pages": 25 if 7 <= paper_id <= 12 else 4,
                "suspicious_control_chars": 1 if 13 <= paper_id <= 18 else 0,
                "remaining_text_quality_flags": ["control_chars"] if 13 <= paper_id <= 18 else [],
                "native_extraction_error": None,
                "ocr_error": None,
                "processing_error": None,
                "mojibake_marker_count": 0,
                "proceedings_like": 19 <= paper_id <= 24,
                "long_document": 7 <= paper_id <= 12,
                "first_page_excerpt": "",
            }
            records.append(record)

        sampled, quotas, actual_counts = self.module.sample_records(records, sample_size=20, seed=7)

        self.assertEqual(len(sampled), 20)
        self.assertEqual(len({row["covidence_id"] for row in sampled}), 20)
        self.assertEqual(quotas["baseline_random"], 10)
        self.assertEqual(quotas["ocr_applied"], 4)
        self.assertEqual(quotas["long_or_proceedings"], 3)
        self.assertEqual(quotas["text_artifacts"], 3)
        self.assertEqual(actual_counts["ocr_applied"], 4)
        self.assertEqual(actual_counts["long_or_proceedings"], 3)
        self.assertEqual(actual_counts["text_artifacts"], 3)
        self.assertEqual(actual_counts["baseline_random"], 10)

    def test_write_review_csv_includes_manual_review_columns(self) -> None:
        rows = [
            {
                "covidence_id": "101",
                "sample_bucket": "baseline_random",
                "risk_tags": "",
                "title": "Title",
                "authors": "Smith, Jane",
                "published_year": "2020",
                "source_filename": "101.pdf",
                "text_json_path": "text/101.json",
                "ocr_applied": False,
                "ocr_mode": "",
                "ocr_trigger_reasons": "",
                "n_pages": 1,
                "proceedings_like": False,
                "long_document": False,
                "suspicious_control_chars": 0,
                "mojibake_marker_count": 0,
                "remaining_text_quality_flags": "",
                "first_page_excerpt": "Excerpt",
                "review_status": "",
                "review_notes": "",
            }
        ]
        out_path = self.tmp_path / "review.csv"

        self.module.write_review_csv(out_path, rows)

        with out_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            loaded_rows = list(reader)

        self.assertEqual(len(loaded_rows), 1)
        self.assertIn("review_status", reader.fieldnames or [])
        self.assertIn("review_notes", reader.fieldnames or [])
        self.assertEqual(loaded_rows[0]["covidence_id"], "101")


if __name__ == "__main__":
    unittest.main()
