from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "03c_clean_text_stage2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("clean_text_stage2_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_override_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "covidence_id",
                "enabled",
                "source_strategy",
                "cleanup_profile",
                "source_page_start",
                "source_page_end",
                "ocr_dpi",
                "ocr_psm",
                "ocr_grayscale",
                "reason",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_substitution_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["covidence_id", "match_type", "match", "replacement", "page_index", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)


class TestCleanTextStage2Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "text"
        self.backup_dir = self.tmp_path / "text_preclean_stage2"
        self.input_dir.mkdir()
        self.backup_dir.mkdir()
        self.override_path = self.tmp_path / "overrides.csv"
        self.substitution_path = self.tmp_path / "substitutions.csv"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_text_json(self, paper_id: str, pages: list[str], **extra: object) -> Path:
        path = self.input_dir / f"{paper_id}.json"
        record = {
            "paper_id": paper_id,
            "source_filename": f"{paper_id}_example.pdf",
            "source_sha256": "source_sha256",
            "extractor": "pypdf",
            "extracted_at_utc": "2026-04-01T00:00:00+00:00",
            "n_pages": len(pages),
            "needs_ocr_before_ocr": False,
            "ocr_trigger_reasons": [],
            "page_char_counts": [len(text) for text in pages],
            "suspicious_control_chars": 0,
            "needs_ocr": False,
            "remaining_text_quality_flags": [],
            "ocr_applied": False,
            "ocr_mode": "",
            "ocr_error": None,
            "native_extraction_error": None,
            "processing_error": None,
            "pages": [
                {"page_index": index, "text": text}
                for index, text in enumerate(pages)
            ],
        }
        record.update(extra)
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return path

    def test_load_substitution_rules_reads_rows_bom_safely(self) -> None:
        module = self.module
        write_substitution_csv(
            self.substitution_path,
            [
                {
                    "covidence_id": "43",
                    "match_type": "literal",
                    "match": "Rvsl61",
                    "replacement": "Rvs161",
                    "page_index": "",
                    "notes": "Repair title token.",
                }
            ],
        )

        rules = module.load_substitution_rules(self.substitution_path)

        self.assertIn("43", rules)
        self.assertEqual(rules["43"][0].replacement, "Rvs161")
        self.assertIsNone(rules["43"][0].page_index)

    def test_apply_substitution_rules_supports_literal_and_regex(self) -> None:
        module = self.module
        pages = [
            {"page_index": 0, "text": "Rvsl61 and stiffman"},
            {"page_index": 1, "text": "Rvsl61 only"},
        ]
        rules = [
            module.SubstitutionRule("literal", "Rvsl61", "Rvs161", None, "repair token"),
            module.SubstitutionRule("regex", r"\bstiffman\b", "stiff-man", 0, "repair hyphen"),
        ]

        updated_pages, applied = module.apply_substitution_rules(pages, rules=rules)

        self.assertEqual(updated_pages[0]["text"], "Rvs161 and stiff-man")
        self.assertEqual(updated_pages[1]["text"], "Rvs161 only")
        self.assertEqual(len(applied), 2)
        self.assertEqual(applied[0]["count"], 2)
        self.assertEqual(applied[1]["changed_pages"], [0])

    def test_extract_pages_and_counts_pdftotext_stages_non_ascii_pdf_path(self) -> None:
        module = self.module
        pdf_path = self.tmp_path / "12751_Vázquez.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        def fake_run(command, **kwargs):
            staged_path = Path(command[1])
            self.assertTrue(staged_path.exists())
            self.assertTrue(str(staged_path).isascii())
            self.assertNotEqual(staged_path, pdf_path)
            return subprocess.CompletedProcess(command, 0, stdout="Stage2 page\f", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            pages, char_counts = module.extract_pages_and_counts_pdftotext(pdf_path)

        self.assertEqual(pages, [{"page_index": 0, "text": "Stage2 page"}])
        self.assertEqual(char_counts, [11])

    def test_extract_pages_and_counts_pdftotext_passes_page_window_and_preserves_page_index(self) -> None:
        module = self.module
        pdf_path = self.tmp_path / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        def fake_run(command, **kwargs):
            self.assertEqual(command[:5], ["pdftotext", "-f", "3", "-l", "4"])
            return subprocess.CompletedProcess(command, 0, stdout="Page three\fPage four\f", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            pages, char_counts = module.extract_pages_and_counts_pdftotext(
                pdf_path,
                start_page=3,
                end_page=4,
            )

        self.assertEqual(
            pages,
            [
                {"page_index": 2, "text": "Page three"},
                {"page_index": 3, "text": "Page four"},
            ],
        )
        self.assertEqual(char_counts, [10, 9])

    def test_apply_source_window_keeps_requested_page_range(self) -> None:
        module = self.module
        pages = [
            {"page_index": 0, "text": "cover"},
            {"page_index": 1, "text": "contents"},
            {"page_index": 2, "text": "article"},
        ]
        counts = [5, 8, 7]

        selected_pages, selected_counts = module.apply_source_window(
            pages,
            counts,
            window=module.SourceWindow(start_page=3, end_page=3),
        )

        self.assertEqual(selected_pages, [{"page_index": 2, "text": "article"}])
        self.assertEqual(selected_counts, [7])

    def test_main_creates_stage2_backup_and_overwrites_canonical_json(self) -> None:
        module = self.module
        text_path = self.make_text_json("155", ["stiV-man syndrome\nIFN-y"])
        fake_pdf_dir = self.tmp_path / "pdfs"
        fake_pdf_dir.mkdir()
        fake_pdf_path = fake_pdf_dir / "155_example.pdf"
        fake_pdf_path.write_bytes(b"%PDF-1.4")
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "155",
                    "enabled": "true",
                    "source_strategy": "ocr_cleanup",
                    "cleanup_profile": "combined_basic",
                    "source_page_start": "",
                    "source_page_end": "",
                    "ocr_dpi": "",
                    "ocr_psm": "",
                    "ocr_grayscale": "",
                    "reason": "Residual OCR substitutions",
                    "notes": "Use OCR source.",
                }
            ],
        )
        write_substitution_csv(
            self.substitution_path,
            [
                {
                    "covidence_id": "155",
                    "match_type": "literal",
                    "match": "IFN-y",
                    "replacement": "IFN-γ",
                    "page_index": "",
                    "notes": "Restore cytokine notation.",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            substitution_path=self.substitution_path,
            paper_id=[],
            limit=0,
            force=False,
            skip_registry_refresh=True,
        )

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module, "PDF_DIR", fake_pdf_dir),
            mock.patch.object(
                module,
                "extract_pages_and_counts_tesseract",
                return_value=([{"page_index": 0, "text": "stiffman syndrome\nIFN-y"}], [22]),
            ),
            mock.patch.object(module, "sha256_file", side_effect=lambda path: "pdf_sha256" if path == fake_pdf_path else "json_sha256"),
        ):
            module.main()

        backup_path = self.backup_dir / text_path.name
        cleaned_record = json.loads(text_path.read_text(encoding="utf-8"))
        raw_backup = json.loads(backup_path.read_text(encoding="utf-8"))

        self.assertTrue(backup_path.exists())
        self.assertEqual(raw_backup["pages"][0]["text"], "stiV-man syndrome\nIFN-y")
        self.assertTrue(cleaned_record["cleanup_stage2_applied"])
        self.assertEqual(cleaned_record["cleanup_stage2_source_strategy"], "ocr_cleanup")
        self.assertEqual(cleaned_record["cleanup_stage2_reason"], "Residual OCR substitutions")
        self.assertEqual(cleaned_record["cleanup_stage2_source_json_path"], module.relative_to_repo(backup_path))
        self.assertEqual(cleaned_record["pages"][0]["text"], "stiffman syndrome\nIFN-γ")
        self.assertEqual(cleaned_record["cleanup_stage2_substitutions_applied"][0]["count"], 1)

    def test_force_rerun_uses_stage2_backup_not_current_canonical_record(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "62",
            ["already stage2 cleaned"],
            cleanup_stage2_applied=True,
            cleanup_stage2_profile="combined_basic",
        )
        backup_record = {
            "paper_id": "62",
            "source_filename": "62_example.pdf",
            "pages": [{"page_index": 0, "text": "Rvsl61"}],
        }
        (self.backup_dir / "62.json").write_text(json.dumps(backup_record, indent=2), encoding="utf-8")
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "62",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "combined_basic",
                    "source_page_start": "",
                    "source_page_end": "",
                    "ocr_dpi": "",
                    "ocr_psm": "",
                    "ocr_grayscale": "",
                    "reason": "Residual token substitution",
                    "notes": "",
                }
            ],
        )
        write_substitution_csv(
            self.substitution_path,
            [
                {
                    "covidence_id": "62",
                    "match_type": "literal",
                    "match": "Rvsl61",
                    "replacement": "Rvs161",
                    "page_index": "",
                    "notes": "Repair title token.",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            substitution_path=self.substitution_path,
            paper_id=[],
            limit=0,
            force=True,
            skip_registry_refresh=True,
        )

        with mock.patch.object(module, "parse_args", return_value=args):
            module.main()

        cleaned_record = json.loads(text_path.read_text(encoding="utf-8"))
        self.assertEqual(cleaned_record["pages"][0]["text"], "Rvs161")
        self.assertEqual(cleaned_record["cleanup_stage2_source_json_path"], module.relative_to_repo(self.backup_dir / "62.json"))

    def test_apply_stage2_cleanup_to_record_can_use_pdftotext_source_strategy(self) -> None:
        module = self.module
        text_path = self.make_text_json("62", ["Compressedtitleline"])
        backup_path = self.backup_dir / "62.json"
        raw_record, raw_source_path = module.ensure_stage2_snapshot(text_path, backup_path)
        fake_pdf_dir = self.tmp_path / "pdfs"
        fake_pdf_dir.mkdir()
        fake_pdf_path = fake_pdf_dir / "62_example.pdf"
        fake_pdf_path.write_bytes(b"%PDF-1.4")

        with (
            mock.patch.object(module, "PDF_DIR", fake_pdf_dir),
            mock.patch.object(
                module,
                "extract_pages_and_counts_pdftotext",
                return_value=([{"page_index": 0, "text": "RvsI61"}], [6]),
            ),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
        ):
            cleaned_record = module.apply_stage2_cleanup_to_record(
                raw_record,
                raw_source_path=raw_source_path,
                override_row={
                    "covidence_id": "62",
                    "source_strategy": "pdftotext_cleanup",
                    "cleanup_profile": "combined_basic",
                    "source_page_start": "",
                    "source_page_end": "",
                    "ocr_dpi": "",
                    "ocr_psm": "",
                    "ocr_grayscale": "",
                    "reason": "Prefer pdftotext source.",
                    "notes": "",
                },
                substitution_rules=[
                    module.SubstitutionRule("literal", "RvsI61", "Rvs161", None, "repair token"),
                ],
            )

        self.assertEqual(cleaned_record["cleanup_stage2_source_strategy"], "pdftotext_cleanup")
        self.assertEqual(
            cleaned_record["cleanup_stage2_source_pdf_path"],
            module.relative_to_repo(fake_pdf_path),
        )
        self.assertEqual(cleaned_record["cleanup_stage2_source_pdf_sha256"], "fake_sha256")
        self.assertEqual(cleaned_record["pages"][0]["text"], "Rvs161")

    def test_apply_stage2_cleanup_to_record_can_limit_json_source_pages(self) -> None:
        module = self.module
        text_path = self.make_text_json("9182", ["cover", "borrower", "article body"])
        backup_path = self.backup_dir / "9182.json"
        raw_record, raw_source_path = module.ensure_stage2_snapshot(text_path, backup_path)

        cleaned_record = module.apply_stage2_cleanup_to_record(
            raw_record,
            raw_source_path=raw_source_path,
            override_row={
                "covidence_id": "9182",
                "source_strategy": "json_cleanup",
                "cleanup_profile": "combined_basic",
                "source_page_start": "3",
                "source_page_end": "3",
                "ocr_dpi": "",
                "ocr_psm": "",
                "ocr_grayscale": "",
                "reason": "Skip cover pages.",
                "notes": "",
            },
            substitution_rules=[],
        )

        self.assertEqual(cleaned_record["pages"], [{"page_index": 2, "text": "article body"}])
        self.assertEqual(cleaned_record["cleanup_stage2_source_page_start"], "3")
        self.assertEqual(cleaned_record["cleanup_stage2_source_page_end"], "3")

    def test_apply_stage2_cleanup_to_record_passes_custom_ocr_settings(self) -> None:
        module = self.module
        text_path = self.make_text_json("23", ["old ocr"])
        backup_path = self.backup_dir / "23.json"
        raw_record, raw_source_path = module.ensure_stage2_snapshot(text_path, backup_path)
        fake_pdf_dir = self.tmp_path / "pdfs"
        fake_pdf_dir.mkdir()
        fake_pdf_path = fake_pdf_dir / "23_example.pdf"
        fake_pdf_path.write_bytes(b"%PDF-1.4")

        with (
            mock.patch.object(module, "PDF_DIR", fake_pdf_dir),
            mock.patch.object(
                module,
                "extract_pages_and_counts_tesseract",
                return_value=([{"page_index": 0, "text": "clean title"}], [11]),
            ) as extract_mock,
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
        ):
            cleaned_record = module.apply_stage2_cleanup_to_record(
                raw_record,
                raw_source_path=raw_source_path,
                override_row={
                    "covidence_id": "23",
                    "source_strategy": "ocr_cleanup",
                    "cleanup_profile": "combined_basic",
                    "source_page_start": "",
                    "source_page_end": "",
                    "ocr_dpi": "400",
                    "ocr_psm": "6",
                    "ocr_grayscale": "true",
                    "reason": "Use stronger OCR settings.",
                    "notes": "",
                },
                substitution_rules=[],
            )

        extract_mock.assert_called_once_with(
            fake_pdf_path,
            dpi=400,
            grayscale=True,
            psm=6,
            start_page=None,
            end_page=None,
        )
        self.assertEqual(cleaned_record["cleanup_stage2_ocr_dpi"], "400")
        self.assertEqual(cleaned_record["cleanup_stage2_ocr_psm"], "6")
        self.assertEqual(cleaned_record["cleanup_stage2_ocr_grayscale"], "true")

    def test_apply_stage2_cleanup_to_record_passes_page_window_to_ocr_source(self) -> None:
        module = self.module
        text_path = self.make_text_json("1421", ["old proceedings text"])
        backup_path = self.backup_dir / "1421.json"
        raw_record, raw_source_path = module.ensure_stage2_snapshot(text_path, backup_path)
        fake_pdf_dir = self.tmp_path / "pdfs"
        fake_pdf_dir.mkdir()
        fake_pdf_path = fake_pdf_dir / "1421_example.pdf"
        fake_pdf_path.write_bytes(b"%PDF-1.4")

        with (
            mock.patch.object(module, "PDF_DIR", fake_pdf_dir),
            mock.patch.object(
                module,
                "extract_pages_and_counts_tesseract",
                return_value=([{"page_index": 186, "text": "localized abstract"}], [18]),
            ) as extract_mock,
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
        ):
            cleaned_record = module.apply_stage2_cleanup_to_record(
                raw_record,
                raw_source_path=raw_source_path,
                override_row={
                    "covidence_id": "1421",
                    "source_strategy": "ocr_cleanup",
                    "cleanup_profile": "combined_basic",
                    "source_page_start": "187",
                    "source_page_end": "187",
                    "ocr_dpi": "220",
                    "ocr_psm": "6",
                    "ocr_grayscale": "true",
                    "reason": "Localize proceedings abstract page.",
                    "notes": "",
                },
                substitution_rules=[],
            )

        extract_mock.assert_called_once_with(
            fake_pdf_path,
            dpi=220,
            grayscale=True,
            psm=6,
            start_page=187,
            end_page=187,
        )
        self.assertEqual(cleaned_record["pages"], [{"page_index": 186, "text": "localized abstract"}])
        self.assertEqual(cleaned_record["cleanup_stage2_source_page_start"], "187")
        self.assertEqual(cleaned_record["cleanup_stage2_source_page_end"], "187")


if __name__ == "__main__":
    unittest.main()
