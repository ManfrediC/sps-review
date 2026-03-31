from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "validation" / "export_text_json_to_txt.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_text_json_to_txt", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestExportTextJsonToTxt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.text_dir = self.tmp_path / "text"
        self.text_dir.mkdir()
        self.output_dir = self.tmp_path / "txt"
        self.selection_csv = self.tmp_path / "selection.csv"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_text_json(self, paper_id: str, *, page_text: str = "Extracted text") -> Path:
        path = self.text_dir / f"{paper_id}.json"
        payload = {
            "paper_id": paper_id,
            "source_filename": f"{paper_id}_Example.pdf",
            "source_sha256": "abc123",
            "extractor": "pypdf",
            "extracted_at_utc": "2026-03-31T12:00:00Z",
            "ocr_applied": False,
            "ocr_mode": None,
            "ocr_trigger_reasons": [],
            "needs_ocr_before_ocr": False,
            "needs_ocr": False,
            "remaining_text_quality_flags": [],
            "suspicious_control_chars": 0,
            "native_extraction_error": None,
            "ocr_error": None,
            "processing_error": None,
            "n_pages": 1,
            "pages": [
                {
                    "page_index": 0,
                    "text": page_text,
                }
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_parse_args_reads_selection_csv_as_path(self) -> None:
        argv = [
            "export_text_json_to_txt.py",
            "--output-dir",
            str(self.output_dir),
            "--selection-csv",
            str(self.selection_csv),
        ]

        with mock.patch.object(sys, "argv", argv):
            args = self.module.parse_args()

        self.assertIsInstance(args.selection_csv[0], Path)

    def test_render_txt_export_includes_registry_metadata_and_page_text(self) -> None:
        json_path = self.write_text_json("101", page_text="First page content")
        record = json.loads(json_path.read_text(encoding="utf-8"))
        registry_row = {
            "covidence_id": "101",
            "title": "Example SPS Paper",
            "authors": "Smith, Jane",
            "published_year": "2020",
            "journal": "Neurology",
            "doi": "10.1000/example",
        }

        rendered = self.module.render_txt_export(
            record,
            json_path=json_path,
            registry_row=registry_row,
        )

        self.assertIn("Paper ID: 101", rendered)
        self.assertIn("Title: Example SPS Paper", rendered)
        self.assertIn("Authors: Smith, Jane", rendered)
        self.assertIn("Journal: Neurology", rendered)
        self.assertIn("DOI: 10.1000/example", rendered)
        self.assertIn("Page 1 / 1 (page_index=0)", rendered)
        self.assertIn("First page content", rendered)

    def test_export_text_jsons_writes_filtered_outputs_and_skips_without_force(self) -> None:
        self.write_text_json("101", page_text="Paper 101 text")
        self.write_text_json("102", page_text="Paper 102 text")
        with self.selection_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["covidence_id"])
            writer.writeheader()
            writer.writerow({"covidence_id": "102"})

        registry_rows = {
            "101": {"covidence_id": "101", "title": "Title 101", "authors": "", "published_year": ""},
            "102": {"covidence_id": "102", "title": "Title 102", "authors": "", "published_year": ""},
        }
        selection_ids = self.module.load_selection_ids([self.selection_csv], column="covidence_id")
        input_paths = self.module.collect_input_paths(
            self.text_dir,
            paper_ids=["101"],
            selection_ids=selection_ids,
        )

        written = self.module.export_text_jsons(
            input_paths=input_paths,
            registry_rows=registry_rows,
            output_dir=self.output_dir,
            force=False,
        )

        self.assertEqual(written, 2)
        self.assertTrue((self.output_dir / "101.txt").exists())
        self.assertTrue((self.output_dir / "102.txt").exists())

        original = (self.output_dir / "101.txt").read_text(encoding="utf-8")
        skipped = self.module.export_text_jsons(
            input_paths=input_paths,
            registry_rows=registry_rows,
            output_dir=self.output_dir,
            force=False,
        )

        self.assertEqual(skipped, 0)
        self.assertEqual((self.output_dir / "101.txt").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
