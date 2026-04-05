from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def load_module():
    pipeline_dir = str(SCRIPT_PATH.parent)
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)
    spec = importlib.util.spec_from_file_location("artifact_registry_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestBuildPaperArtifactRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.output_path = self.tmp_path / "paper_artifact_registry.csv"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_row_includes_text_cleanup_and_preclean_fields(self) -> None:
        module = self.module
        text_path = self.tmp_path / "text" / "114.json"
        preclean_path = self.tmp_path / "text_preclean" / "114.json"
        preclean_stage2_path = self.tmp_path / "text_preclean_stage2" / "114.json"
        text_path.parent.mkdir()
        preclean_path.parent.mkdir()
        preclean_stage2_path.parent.mkdir()
        text_path.write_text("{}", encoding="utf-8")
        preclean_path.write_text("{}", encoding="utf-8")
        preclean_stage2_path.write_text("{}", encoding="utf-8")

        row = module.build_row(
            paper_id="114",
            reference_row={
                "Covidence": "114",
                "Title": "The stiff leg syndrome",
                "Authors": "Brown, P",
                "Published Year": "1997",
            },
            manifest_row={},
            pdf_paths=[],
            text_record={
                "source_filename": "114_example.pdf",
                "source_sha256": "pdf_sha256",
                "extracted_at_utc": "2026-03-31T00:00:00+00:00",
                "n_pages": 3,
                "needs_ocr": False,
                "ocr_applied": False,
                "cleanup_applied": True,
                "cleanup_profile": "basic_spacing",
                "cleanup_applied_at_utc": "2026-03-31T01:00:00+00:00",
                "cleanup_source_strategy": "pdftotext_cleanup",
                "cleanup_original_extractor": "pypdf",
                "cleanup_changed_page_count": 2,
                "cleanup_source_json_path": "data/extraction_json/text_preclean/114.json",
                "cleanup_source_json_sha256": "preclean_sha256",
                "cleanup_source_pdf_path": "data/pdf_original/114_example.pdf",
                "cleanup_source_pdf_sha256": "pdf_sha256",
                "cleanup_stage2_applied": True,
                "cleanup_stage2_profile": "combined_basic",
                "cleanup_stage2_applied_at_utc": "2026-04-02T01:00:00+00:00",
                "cleanup_stage2_source_strategy": "ocr_cleanup",
                "cleanup_stage2_changed_page_count": 1,
                "cleanup_stage2_source_json_path": "data/extraction_json/text_preclean_stage2/114.json",
                "cleanup_stage2_source_json_sha256": "preclean_stage2_sha256",
                "cleanup_stage2_source_pdf_path": "data/pdf_original/114_example.pdf",
                "cleanup_stage2_source_pdf_sha256": "pdf_sha256",
                "cleanup_stage2_source_page_start": "2",
                "cleanup_stage2_source_page_end": "4",
                "cleanup_stage2_ocr_dpi": "220",
                "cleanup_stage2_ocr_psm": "3",
                "cleanup_stage2_ocr_grayscale": "true",
            },
            text_path=text_path,
            text_preclean_path=preclean_path,
            text_preclean_stage2_path=preclean_stage2_path,
            text_trim_record={},
            text_trim_path=None,
            text_trim_registry_row={},
            source_categorisation_row={},
            source_case_count_row={
                "count_eligible": "true",
                "likely_sps_case_count": "2",
                "count_confidence": "medium",
                "count_basis": "abstract_count_signal",
                "count_manual_review_required": "false",
                "count_reason": "count_basis=abstract_count_signal | count_confidence=medium",
                "count_version": "heuristic_v1",
                "counted_at_utc": "2026-04-05T12:00:00+00:00",
            },
            source_manual_review_row={},
            proceedings_qc_row={},
            case_series_split_row={},
            case_series_split_path=None,
            langextract_record={},
            langextract_path=None,
            summary_record={},
            summary_path=None,
            quality_raw_record={},
            quality_raw_path=None,
            quality_record={},
            quality_record_path=None,
        )

        self.assertEqual(row["text_preclean_json_present"], "true")
        self.assertEqual(row["text_preclean_stage2_json_present"], "true")
        self.assertEqual(row["text_cleanup_applied"], "true")
        self.assertEqual(row["text_cleanup_profile"], "basic_spacing")
        self.assertEqual(row["text_cleanup_source_strategy"], "pdftotext_cleanup")
        self.assertEqual(row["text_cleanup_original_extractor"], "pypdf")
        self.assertEqual(row["text_cleanup_changed_page_count"], "2")
        self.assertEqual(row["text_cleanup_source_json_path"], "data/extraction_json/text_preclean/114.json")
        self.assertEqual(row["text_cleanup_source_json_sha256"], "preclean_sha256")
        self.assertEqual(row["text_cleanup_source_pdf_path"], "data/pdf_original/114_example.pdf")
        self.assertEqual(row["text_cleanup_source_pdf_sha256"], "pdf_sha256")
        self.assertEqual(row["text_cleanup_stage2_applied"], "true")
        self.assertEqual(row["text_cleanup_stage2_profile"], "combined_basic")
        self.assertEqual(row["text_cleanup_stage2_source_strategy"], "ocr_cleanup")
        self.assertEqual(row["text_cleanup_stage2_source_page_start"], "2")
        self.assertEqual(row["text_cleanup_stage2_source_page_end"], "4")
        self.assertEqual(row["text_cleanup_stage2_ocr_psm"], "3")
        self.assertEqual(row["source_case_count_present"], "true")
        self.assertEqual(row["source_likely_sps_case_count"], "2")
        self.assertEqual(row["source_count_confidence"], "medium")
        self.assertIn("text_preclean", row["artifact_types_present"])
        self.assertIn("text_preclean_stage2", row["artifact_types_present"])
        self.assertIn("source_sps_case_count", row["artifact_types_present"])

        module.write_registry([row], self.output_path)

        with self.output_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        self.assertEqual(len(rows), 1)
        written_row = rows[0]
        self.assertIn("text_preclean_json_present", reader.fieldnames or [])
        self.assertIn("text_preclean_stage2_json_present", reader.fieldnames or [])
        self.assertIn("text_cleanup_applied", reader.fieldnames or [])
        self.assertIn("text_cleanup_stage2_applied", reader.fieldnames or [])
        self.assertIn("text_cleanup_source_strategy", reader.fieldnames or [])
        self.assertIn("source_case_count_present", reader.fieldnames or [])
        self.assertIn("source_likely_sps_case_count", reader.fieldnames or [])
        self.assertEqual(written_row["text_cleanup_profile"], "basic_spacing")
        self.assertEqual(written_row["text_cleanup_stage2_profile"], "combined_basic")
        self.assertEqual(written_row["source_count_basis"], "abstract_count_signal")


if __name__ == "__main__":
    unittest.main()
