from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "03b_clean_text.py"


def load_module():
    spec = importlib.util.spec_from_file_location("clean_text_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_override_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["covidence_id", "enabled", "source_strategy", "cleanup_profile", "reason", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)


class TestCleanTextPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "text"
        self.backup_dir = self.tmp_path / "text_preclean"
        self.input_dir.mkdir()
        self.backup_dir.mkdir()
        self.override_path = self.tmp_path / "overrides.csv"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_text_json(self, paper_id: str, pages: list[str], **extra: object) -> Path:
        path = self.input_dir / f"{paper_id}.json"
        record = {
            "paper_id": paper_id,
            "source_filename": f"{paper_id}_example.pdf",
            "source_sha256": "source_sha256",
            "extractor": "pypdf",
            "extracted_at_utc": "2026-03-31T00:00:00+00:00",
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

    def test_load_cleanup_overrides_reads_enabled_rows_bom_safely(self) -> None:
        module = self.module
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "114",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "basic_spacing",
                    "reason": "Spacing artifacts",
                    "notes": "Apply cleanup.",
                },
                {
                    "covidence_id": "999",
                    "enabled": "false",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "basic_mojibake",
                    "reason": "Disabled",
                    "notes": "",
                },
            ],
        )

        overrides = module.load_cleanup_overrides(self.override_path)

        self.assertIn("114", overrides)
        self.assertNotIn("999", overrides)
        self.assertEqual(overrides["114"]["cleanup_profile"], "basic_spacing")

    def test_main_creates_preclean_backup_and_overwrites_canonical_json(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "114",
            [
                "Repeat Header\nUseful first page\nDownloaded from example.com",
                "Repeat Header\nUseful second page\nDownloaded from example.com",
                "Repeat Header\nUseful third page\nDownloaded from example.com",
            ],
        )
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "114",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "header_footer_light",
                    "reason": "Boundary boilerplate",
                    "notes": "Clean repeated header/footer noise.",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            paper_id=[],
            limit=0,
            force=False,
            skip_registry_refresh=False,
        )

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            module.main()

        backup_path = self.backup_dir / text_path.name
        cleaned_record = json.loads(text_path.read_text(encoding="utf-8"))
        raw_backup = json.loads(backup_path.read_text(encoding="utf-8"))

        self.assertTrue(backup_path.exists())
        self.assertEqual(raw_backup["pages"][1]["text"], "Repeat Header\nUseful second page\nDownloaded from example.com")
        self.assertTrue(cleaned_record["cleanup_applied"])
        self.assertEqual(cleaned_record["cleanup_profile"], "header_footer_light")
        self.assertEqual(cleaned_record["cleanup_source_strategy"], "json_cleanup")
        self.assertEqual(cleaned_record["cleanup_reason"], "Boundary boilerplate")
        self.assertEqual(cleaned_record["cleanup_notes"], "Clean repeated header/footer noise.")
        self.assertEqual(cleaned_record["cleanup_source_json_path"], module.relative_to_repo(backup_path))
        self.assertEqual(cleaned_record["pages"][0]["text"], "Repeat Header\nUseful first page")
        self.assertEqual(cleaned_record["pages"][1]["text"], "Useful second page")
        self.assertEqual(cleaned_record["page_char_counts"], [len(page["text"]) for page in cleaned_record["pages"]])
        subprocess_run.assert_called_once_with(
            [module.sys.executable, str(module.ARTIFACT_REGISTRY_SCRIPT)],
            check=True,
            cwd=str(module.REPO_ROOT),
        )

    def test_main_skips_already_cleaned_without_force(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "114",
            ["already clean"],
            cleanup_applied=True,
            cleanup_profile="basic_spacing",
        )
        self.make_text_json("999", ["not targeted"])
        (self.backup_dir / "114.json").write_text(
            json.dumps({"paper_id": "114", "pages": [{"page_index": 0, "text": "raw text"}]}),
            encoding="utf-8",
        )
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "114",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "basic_spacing",
                    "reason": "Spacing artifacts",
                    "notes": "",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            paper_id=[],
            limit=0,
            force=False,
            skip_registry_refresh=False,
        )

        original_text = text_path.read_text(encoding="utf-8")
        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            module.main()

        self.assertEqual(text_path.read_text(encoding="utf-8"), original_text)
        subprocess_run.assert_called_once()

    def test_force_rerun_uses_preclean_backup_not_current_canonical_record(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "114",
            ["already cleaned"],
            cleanup_applied=True,
            cleanup_profile="basic_spacing",
        )
        backup_record = {
            "paper_id": "114",
            "source_filename": "114_example.pdf",
            "pages": [{"page_index": 0, "text": "immuno-\ntherapy.TestCase"}],
        }
        (self.backup_dir / "114.json").write_text(json.dumps(backup_record, indent=2), encoding="utf-8")
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "114",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "basic_spacing",
                    "reason": "Spacing artifacts",
                    "notes": "",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            paper_id=[],
            limit=0,
            force=True,
            skip_registry_refresh=True,
        )

        with mock.patch.object(module, "parse_args", return_value=args):
            module.main()

        cleaned_record = json.loads(text_path.read_text(encoding="utf-8"))
        self.assertEqual(cleaned_record["pages"][0]["text"], "immunotherapy. Test Case")
        self.assertEqual(cleaned_record["cleanup_source_json_path"], module.relative_to_repo(self.backup_dir / "114.json"))

    def test_ensure_preclean_snapshot_raises_when_backup_is_missing_for_cleaned_json(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "114",
            ["already cleaned"],
            cleanup_applied=True,
            cleanup_profile="basic_spacing",
        )

        with self.assertRaises(ValueError):
            module.ensure_preclean_snapshot(text_path, self.backup_dir / "114.json")

    def test_main_raises_when_no_target_jsons_match_enabled_ids(self) -> None:
        module = self.module
        self.make_text_json("114", ["text"])
        write_override_csv(
            self.override_path,
            [
                {
                    "covidence_id": "999",
                    "enabled": "true",
                    "source_strategy": "json_cleanup",
                    "cleanup_profile": "basic_spacing",
                    "reason": "Different paper",
                    "notes": "",
                }
            ],
        )
        args = argparse.Namespace(
            input_dir=self.input_dir,
            backup_dir=self.backup_dir,
            override_path=self.override_path,
            paper_id=[],
            limit=0,
            force=False,
            skip_registry_refresh=False,
        )

        with mock.patch.object(module, "parse_args", return_value=args):
            with self.assertRaises(SystemExit) as exc:
                module.main()

        self.assertEqual(
            str(exc.exception),
            f"No text JSONs found in {self.input_dir} for enabled cleanup IDs.",
        )

    def test_apply_cleanup_to_record_can_use_pdftotext_source_strategy(self) -> None:
        module = self.module
        text_path = self.make_text_json(
            "114",
            ["Compressedtitleline"],
        )
        backup_path = self.backup_dir / "114.json"
        raw_record, raw_source_path = module.ensure_preclean_snapshot(text_path, backup_path)
        fake_pdf_dir = self.tmp_path / "pdfs"
        fake_pdf_dir.mkdir()
        fake_pdf_path = fake_pdf_dir / "114_example.pdf"
        fake_pdf_path.write_bytes(b"%PDF-1.4")

        with (
            mock.patch.object(module, "PDF_DIR", fake_pdf_dir),
            mock.patch.object(
                module,
                "extract_pages_and_counts_pdftotext",
                return_value=([{"page_index": 0, "text": "The stiff leg syndrome"}], [22]),
            ),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
        ):
            cleaned_record = module.apply_cleanup_to_record(
                raw_record,
                raw_source_path=raw_source_path,
                override_row={
                    "covidence_id": "114",
                    "source_strategy": "pdftotext_cleanup",
                    "cleanup_profile": "basic_spacing",
                    "reason": "Spacing artifacts",
                    "notes": "Prefer pdftotext source.",
                },
            )

        self.assertEqual(cleaned_record["extractor"], "pdftotext")
        self.assertEqual(cleaned_record["cleanup_source_strategy"], "pdftotext_cleanup")
        self.assertEqual(
            cleaned_record["cleanup_source_pdf_path"],
            module.relative_to_repo(fake_pdf_path),
        )
        self.assertEqual(cleaned_record["cleanup_original_extractor"], "pypdf")
        self.assertEqual(cleaned_record["cleanup_source_pdf_sha256"], "fake_sha256")
        self.assertEqual(cleaned_record["pages"][0]["text"], "The stiff leg syndrome")


if __name__ == "__main__":
    unittest.main()
