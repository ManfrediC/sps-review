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


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "03_extract_text.py"


def load_module():
    spec = importlib.util.spec_from_file_location("extract_text_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestExtractText(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.input_dir = self.tmp_path / "pdfs"
        self.output_dir = self.tmp_path / "text"
        self.input_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_pdf(self, name: str) -> Path:
        path = self.input_dir / name
        path.touch()
        return path

    def test_paper_id_from_filename(self) -> None:
        module = self.module

        self.assertEqual(module.paper_id_from_filename("11849_Stiff person syndrome.pdf"), "11849")
        self.assertEqual(module.paper_id_from_filename("12345.pdf"), "12345")

    def test_extract_pages_and_counts_pdftotext_stages_non_ascii_pdf_path(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("12751_Vázquez.pdf")

        def fake_run(command, **kwargs):
            staged_path = Path(command[1])
            self.assertTrue(staged_path.exists())
            self.assertTrue(str(staged_path).isascii())
            self.assertNotEqual(staged_path, pdf_path)
            return subprocess.CompletedProcess(command, 0, stdout="Page one\f", stderr="")

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            pages, char_counts = module.extract_pages_and_counts_pdftotext(pdf_path)

        self.assertEqual(pages, [{"page_index": 0, "text": "Page one"}])
        self.assertEqual(char_counts, [8])

    def test_collect_input_pdfs_filters_by_paper_id_and_limit(self) -> None:
        module = self.module

        self.make_pdf("100_a.pdf")
        self.make_pdf("200_b.pdf")
        self.make_pdf("300_c.pdf")
        (self.input_dir / "notes.txt").touch()

        pdfs = module.collect_input_pdfs(self.input_dir, paper_ids=["200", "300"], limit=1)

        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0].name, "200_b.pdf")

    def test_load_extraction_overrides_reads_bom_safe_csv(self) -> None:
        module = self.module
        override_path = self.tmp_path / "overrides.csv"
        with override_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["covidence_id", "strategy", "notes"])
            writer.writeheader()
            writer.writerow(
                {
                    "covidence_id": "633",
                    "strategy": "force_ocr",
                    "notes": "Broken native encoding.",
                }
            )

        overrides = module.load_extraction_overrides(override_path)

        self.assertEqual(overrides["633"]["strategy"], "force_ocr")
        self.assertEqual(overrides["633"]["notes"], "Broken native encoding.")

    def test_extract_pdf_text_without_ocr(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")

        pages = [
            {"page_index": 0, "text": "This page contains enough extracted text to avoid OCR entirely."},
            {"page_index": 1, "text": "Second page also contains enough readable extracted text for the heuristic."},
        ]
        char_counts = [61, 71]

        with (
            mock.patch.object(module, "extract_pages_and_counts", return_value=(pages, char_counts)),
            mock.patch.object(module, "run_ocr", side_effect=AssertionError("OCR should not run")),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertEqual(record["paper_id"], "123")
        self.assertEqual(record["source_filename"], "123_test.pdf")
        self.assertEqual(record["source_sha256"], "fake_sha256")
        self.assertFalse(record["ocr_applied"])
        self.assertIsNone(record["ocr_error"])
        self.assertIsNone(record["native_extraction_error"])
        self.assertIsNone(record["processing_error"])
        self.assertEqual(record["ocr_trigger_reasons"], [])
        self.assertEqual(record["remaining_text_quality_flags"], [])
        self.assertEqual(record["ocr_mode"], "")
        self.assertFalse(record["needs_ocr_before_ocr"])
        self.assertFalse(record["needs_ocr"])
        self.assertEqual(record["n_pages"], 2)

    def test_extract_pdf_text_with_successful_skip_text_ocr(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")

        initial_pages = [
            {"page_index": 0, "text": ""},
            {"page_index": 1, "text": "tiny"},
        ]
        ocr_pages = [
            {"page_index": 0, "text": "This page now contains plenty of readable text after OCR."},
            {"page_index": 1, "text": "Second page also contains enough extracted text after OCR."},
        ]
        ocr_calls: list[dict[str, object]] = []

        def fake_extract_pages_and_counts(path: Path):
            if path == pdf_path:
                return initial_pages, [0, 4]
            return ocr_pages, [57, 58]

        def fake_run_ocr(input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
            ocr_calls.append(
                {
                    "input_pdf": input_pdf,
                    "output_pdf": output_pdf,
                    "force_ocr": force_ocr,
                }
            )

        with (
            mock.patch.object(module, "extract_pages_and_counts", side_effect=fake_extract_pages_and_counts),
            mock.patch.object(module, "run_ocr", side_effect=fake_run_ocr),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertTrue(record["ocr_applied"])
        self.assertIsNone(record["ocr_error"])
        self.assertIsNone(record["native_extraction_error"])
        self.assertEqual(record["ocr_trigger_reasons"], ["low_text"])
        self.assertTrue(record["needs_ocr_before_ocr"])
        self.assertFalse(record["needs_ocr"])
        self.assertEqual(record["remaining_text_quality_flags"], [])
        self.assertEqual(record["ocr_mode"], "skip-text")
        self.assertEqual(len(ocr_calls), 1)
        self.assertFalse(ocr_calls[0]["force_ocr"])

    def test_extract_pdf_text_uses_force_ocr_for_control_chars(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")

        noisy_text = ("Readable text " * 20) + ("\x01" * 12)
        initial_pages = [{"page_index": 0, "text": noisy_text}]
        ocr_pages = [{"page_index": 0, "text": "Clean OCR text " * 20}]
        ocr_calls: list[dict[str, object]] = []

        def fake_extract_pages_and_counts(path: Path):
            if path == pdf_path:
                return initial_pages, [len(noisy_text)]
            return ocr_pages, [len(ocr_pages[0]["text"])]

        def fake_run_ocr(input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
            ocr_calls.append(
                {
                    "input_pdf": input_pdf,
                    "output_pdf": output_pdf,
                    "force_ocr": force_ocr,
                }
            )

        with (
            mock.patch.object(module, "extract_pages_and_counts", side_effect=fake_extract_pages_and_counts),
            mock.patch.object(module, "run_ocr", side_effect=fake_run_ocr),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertEqual(record["ocr_trigger_reasons"], ["control_chars"])
        self.assertEqual(record["ocr_mode"], "force-ocr")
        self.assertTrue(record["ocr_applied"])
        self.assertIsNone(record["native_extraction_error"])
        self.assertEqual(record["remaining_text_quality_flags"], [])
        self.assertEqual(len(ocr_calls), 1)
        self.assertTrue(ocr_calls[0]["force_ocr"])

    def test_extract_pdf_text_honours_force_ocr_override(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("633_test.pdf")
        ocr_pages = [{"page_index": 0, "text": "Readable OCR text for paper 633."}]

        with (
            mock.patch.object(
                module,
                "extract_pages_and_counts",
                side_effect=AssertionError("Native pypdf extraction should be skipped"),
            ),
            mock.patch.object(
                module,
                "extract_pages_and_counts_pdftotext",
                return_value=(ocr_pages, [len(ocr_pages[0]["text"])]),
            ) as extract_pdftotext,
            mock.patch.object(module, "run_ocr") as run_ocr,
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(
                pdf_path,
                override={"covidence_id": "633", "strategy": "force_ocr", "notes": "Broken native encoding."},
            )

        self.assertTrue(record["ocr_applied"])
        self.assertEqual(record["ocr_mode"], "force-ocr")
        self.assertEqual(record["ocr_trigger_reasons"], ["override_force_ocr"])
        self.assertEqual(record["extractor"], "pdftotext")
        self.assertEqual(record["extraction_override_strategy"], "force_ocr")
        self.assertEqual(record["extraction_override_notes"], "Broken native encoding.")
        run_ocr.assert_called_once()
        extract_pdftotext.assert_called_once()

    def test_extract_pdf_text_honours_pdftotext_override(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("861_test.pdf")
        text_pages = [{"page_index": 0, "text": "Readable pdftotext output for paper 861."}]

        with (
            mock.patch.object(
                module,
                "extract_pages_and_counts",
                side_effect=AssertionError("Native pypdf extraction should be skipped"),
            ),
            mock.patch.object(
                module,
                "extract_pages_and_counts_pdftotext",
                return_value=(text_pages, [len(text_pages[0]["text"])]),
            ) as extract_pdftotext,
            mock.patch.object(module, "run_ocr", side_effect=AssertionError("OCR should not run")),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
        ):
            record = module.extract_pdf_text(
                pdf_path,
                override={"covidence_id": "861", "strategy": "pdftotext", "notes": "Use pdftotext directly."},
            )

        self.assertFalse(record["ocr_applied"])
        self.assertEqual(record["extractor"], "pdftotext")
        self.assertEqual(record["extraction_override_strategy"], "pdftotext")
        self.assertEqual(record["extraction_override_notes"], "Use pdftotext directly.")
        extract_pdftotext.assert_called_once_with(pdf_path)

    def test_extract_pdf_text_records_ocr_error(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")

        with (
            mock.patch.object(
                module,
                "extract_pages_and_counts",
                return_value=(
                    [
                        {"page_index": 0, "text": ""},
                        {"page_index": 1, "text": ""},
                    ],
                    [0, 0],
                ),
            ),
            mock.patch.object(
                module,
                "run_ocr",
                side_effect=subprocess.CalledProcessError(
                    returncode=7,
                    cmd=["python", "-m", "ocrmypdf", "input.pdf", "output.pdf"],
                    stderr="ocr stderr output",
                    output="ocr stdout output",
                ),
            ),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertFalse(record["ocr_applied"])
        self.assertEqual(record["ocr_error"]["exception_type"], "CalledProcessError")
        self.assertEqual(record["ocr_error"]["returncode"], 7)
        self.assertEqual(
            record["ocr_error"]["command"],
            ["python", "-m", "ocrmypdf", "input.pdf", "output.pdf"],
        )
        self.assertEqual(record["ocr_error"]["stderr_tail"], "ocr stderr output")
        self.assertEqual(record["ocr_error"]["stdout_tail"], "ocr stdout output")
        self.assertTrue(record["needs_ocr_before_ocr"])
        self.assertTrue(record["needs_ocr"])
        self.assertEqual(record["remaining_text_quality_flags"], ["low_text"])

    def test_extract_pdf_text_uses_ocr_when_native_extraction_fails(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")
        ocr_pages = [{"page_index": 0, "text": "Recovered OCR text " * 10}]

        def fake_extract_pages_and_counts(path: Path):
            if path == pdf_path:
                raise RuntimeError("malformed pdf")
            return ocr_pages, [len(ocr_pages[0]["text"])]

        with (
            mock.patch.object(module, "extract_pages_and_counts", side_effect=fake_extract_pages_and_counts),
            mock.patch.object(module, "run_ocr"),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", True),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertTrue(record["ocr_applied"])
        self.assertEqual(record["ocr_mode"], "force-ocr")
        self.assertEqual(record["ocr_trigger_reasons"], ["native_extraction_error"])
        self.assertEqual(record["native_extraction_error"]["exception_type"], "RuntimeError")
        self.assertEqual(record["native_extraction_error"]["message"], "malformed pdf")
        self.assertIsNone(record["ocr_error"])
        self.assertFalse(record["needs_ocr"])
        self.assertEqual(record["n_pages"], 1)

    def test_extract_pdf_text_keeps_needs_ocr_when_ocr_disabled(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")

        with (
            mock.patch.object(
                module,
                "extract_pages_and_counts",
                return_value=(
                    [
                        {"page_index": 0, "text": ""},
                        {"page_index": 1, "text": "tiny"},
                    ],
                    [0, 4],
                ),
            ),
            mock.patch.object(module, "run_ocr", side_effect=AssertionError("OCR should not run")),
            mock.patch.object(module, "sha256_file", return_value="fake_sha256"),
            mock.patch.object(module, "ENABLE_OCR", False),
        ):
            record = module.extract_pdf_text(pdf_path)

        self.assertFalse(record["ocr_applied"])
        self.assertIsNone(record["ocr_error"])
        self.assertIsNone(record["native_extraction_error"])
        self.assertTrue(record["needs_ocr_before_ocr"])
        self.assertTrue(record["needs_ocr"])
        self.assertEqual(record["remaining_text_quality_flags"], ["low_text"])

    def test_text_quality_flags_detect_control_chars_without_low_text(self) -> None:
        module = self.module

        pages = [
            {"page_index": 0, "text": ("Normal text " * 15) + ("\x01" * 12)},
            {"page_index": 1, "text": "More normal text " * 10},
        ]
        char_counts = [177, 170]

        flags = module.text_quality_flags(pages, char_counts)

        self.assertIn("control_chars", flags)
        self.assertNotIn("low_text", flags)

    def test_main_writes_json_and_refreshes_registry(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")
        override_path = self.tmp_path / "overrides.csv"
        args = argparse.Namespace(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            override_path=override_path,
            paper_id=["123"],
            limit=0,
            force=False,
        )
        record = {
            "paper_id": "123",
            "source_filename": pdf_path.name,
            "source_sha256": "fake_sha256",
            "extractor": "pypdf",
            "extracted_at_utc": "2026-03-31T00:00:00+00:00",
            "n_pages": 1,
            "needs_ocr_before_ocr": False,
            "ocr_trigger_reasons": [],
            "page_char_counts": [100],
            "suspicious_control_chars": 0,
            "needs_ocr": False,
            "remaining_text_quality_flags": [],
            "ocr_applied": False,
            "ocr_mode": "",
            "ocr_error": None,
            "native_extraction_error": None,
            "processing_error": None,
            "pages": [{"page_index": 0, "text": "example text"}],
        }

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module, "collect_input_pdfs", return_value=[pdf_path]),
            mock.patch.object(module, "load_extraction_overrides", return_value={"123": {"strategy": "pdftotext"}}),
            mock.patch.object(module, "extract_pdf_text", return_value=record) as extract_pdf_text,
            mock.patch.object(module, "tqdm", side_effect=lambda items, **_: items),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            module.main()

        output_path = self.output_dir / "123.json"
        self.assertTrue(output_path.exists())
        self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), record)
        extract_pdf_text.assert_called_once_with(pdf_path, override={"strategy": "pdftotext"})
        subprocess_run.assert_called_once_with(
            [module.sys.executable, str(module.ARTIFACT_REGISTRY_SCRIPT)],
            check=True,
            cwd=str(module.REPO_ROOT),
        )

    def test_main_skips_existing_output_without_force(self) -> None:
        module = self.module
        pdf_path = self.make_pdf("123_test.pdf")
        output_path = self.output_dir / "123.json"
        output_path.write_text('{"status": "existing"}', encoding="utf-8")
        args = argparse.Namespace(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            override_path=self.tmp_path / "overrides.csv",
            paper_id=["123"],
            limit=0,
            force=False,
        )

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module, "collect_input_pdfs", return_value=[pdf_path]),
            mock.patch.object(module, "load_extraction_overrides", return_value={}),
            mock.patch.object(module, "extract_pdf_text") as extract_pdf_text,
            mock.patch.object(module, "tqdm", side_effect=lambda items, **_: items),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            module.main()

        extract_pdf_text.assert_not_called()
        self.assertEqual(output_path.read_text(encoding="utf-8"), '{"status": "existing"}')
        subprocess_run.assert_called_once()

    def test_write_json_atomic_replaces_existing_file(self) -> None:
        module = self.module
        out_path = self.output_dir / "123.json"
        out_path.write_text('{"status":"old"}', encoding="utf-8")
        record = {
            "paper_id": "123",
            "source_filename": "123_test.pdf",
            "pages": [{"page_index": 0, "text": "fresh text"}],
        }

        module.write_json_atomic(out_path, record)

        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8")), record)
        self.assertEqual(list(self.output_dir.glob("*.tmp")), [])

    def test_main_continues_after_processing_error_and_exits_nonzero(self) -> None:
        module = self.module
        bad_pdf = self.make_pdf("123_bad.pdf")
        good_pdf = self.make_pdf("456_good.pdf")
        args = argparse.Namespace(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            override_path=self.tmp_path / "overrides.csv",
            paper_id=[],
            limit=0,
            force=True,
        )
        good_record = {
            "paper_id": "456",
            "source_filename": good_pdf.name,
            "source_sha256": "good_sha256",
            "extractor": "pypdf",
            "extracted_at_utc": "2026-03-31T00:00:00+00:00",
            "n_pages": 1,
            "needs_ocr_before_ocr": False,
            "ocr_trigger_reasons": [],
            "page_char_counts": [120],
            "suspicious_control_chars": 0,
            "needs_ocr": False,
            "remaining_text_quality_flags": [],
            "ocr_applied": False,
            "ocr_mode": "",
            "ocr_error": None,
            "native_extraction_error": None,
            "processing_error": None,
            "pages": [{"page_index": 0, "text": "good text"}],
        }

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module, "collect_input_pdfs", return_value=[bad_pdf, good_pdf]),
            mock.patch.object(module, "load_extraction_overrides", return_value={}),
            mock.patch.object(
                module,
                "extract_pdf_text",
                side_effect=[RuntimeError("boom"), good_record],
            ),
            mock.patch.object(module, "tqdm", side_effect=lambda items, **_: items),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            with self.assertRaises(SystemExit) as exc:
                module.main()

        self.assertEqual(str(exc.exception), "Text extraction completed with 1 failed PDF(s).")
        bad_output = json.loads((self.output_dir / "123.json").read_text(encoding="utf-8"))
        good_output = json.loads((self.output_dir / "456.json").read_text(encoding="utf-8"))
        self.assertEqual(bad_output["processing_error"]["exception_type"], "RuntimeError")
        self.assertEqual(bad_output["processing_error"]["message"], "boom")
        self.assertEqual(good_output, good_record)
        subprocess_run.assert_called_once()

    def test_main_raises_when_no_pdfs_found(self) -> None:
        module = self.module
        args = argparse.Namespace(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            override_path=self.tmp_path / "overrides.csv",
            paper_id=[],
            limit=0,
            force=False,
        )

        with (
            mock.patch.object(module, "parse_args", return_value=args),
            mock.patch.object(module, "collect_input_pdfs", return_value=[]),
            mock.patch.object(module.subprocess, "run") as subprocess_run,
        ):
            with self.assertRaises(SystemExit) as exc:
                module.main()

        self.assertEqual(str(exc.exception), f"No PDFs found in: {self.input_dir}")
        subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
