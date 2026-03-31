from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "03_extract_text.py"


def load_module():
    spec = importlib.util.spec_from_file_location("extract_text_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_paper_id_from_filename() -> None:
    module = load_module()
    assert module.paper_id_from_filename("11849_Stiff person syndrome.pdf") == "11849"
    assert module.paper_id_from_filename("12345.pdf") == "12345"


def test_collect_input_pdfs_filters_by_paper_id_and_limit(tmp_path: Path) -> None:
    module = load_module()

    (tmp_path / "100_a.pdf").touch()
    (tmp_path / "200_b.pdf").touch()
    (tmp_path / "300_c.pdf").touch()
    (tmp_path / "notes.txt").touch()

    pdfs = module.collect_input_pdfs(tmp_path, paper_ids=["200", "300"], limit=1)

    assert len(pdfs) == 1
    assert pdfs[0].name == "200_b.pdf"


def test_extract_pdf_text_without_ocr(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    pdf_path = tmp_path / "123_test.pdf"
    pdf_path.touch()

    def fake_extract_pages_and_counts(path: Path):
        assert path == pdf_path
        pages = [
            {"page_index": 0, "text": "This is a normal amount of extracted text."},
            {"page_index": 1, "text": "More normal extracted text on page two."},
        ]
        char_counts = [40, 39]
        return pages, char_counts

    monkeypatch.setattr(module, "extract_pages_and_counts", fake_extract_pages_and_counts)
    monkeypatch.setattr(module, "sha256_file", lambda path: "fake_sha256")
    monkeypatch.setattr(module, "ENABLE_OCR", True)

    record = module.extract_pdf_text(pdf_path)

    assert record["paper_id"] == "123"
    assert record["source_filename"] == "123_test.pdf"
    assert record["source_sha256"] == "fake_sha256"
    assert record["ocr_applied"] is False
    assert record["ocr_error"] is None
    assert record["ocr_trigger_reasons"] == []
    assert record["needs_ocr"] is False
    assert record["n_pages"] == 2


def test_extract_pdf_text_with_successful_ocr(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    pdf_path = tmp_path / "123_test.pdf"
    pdf_path.touch()

    call_count = {"n": 0}

    def fake_extract_pages_and_counts(path: Path):
        call_count["n"] += 1

        # First pass: poor extraction, should trigger OCR
        if call_count["n"] == 1:
            return (
                [
                    {"page_index": 0, "text": ""},
                    {"page_index": 1, "text": "tiny"},
                ],
                [0, 4],
            )

        # Second pass: after OCR, text is good
        return (
            [
                {"page_index": 0, "text": "This page now contains plenty of readable text after OCR."},
                {"page_index": 1, "text": "Second page also contains enough extracted text after OCR."},
            ],
            [57, 58],
        )

    ocr_calls = []

    def fake_run_ocr(input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
        ocr_calls.append(
            {
                "input_pdf": input_pdf,
                "output_pdf": output_pdf,
                "force_ocr": force_ocr,
            }
        )

    monkeypatch.setattr(module, "extract_pages_and_counts", fake_extract_pages_and_counts)
    monkeypatch.setattr(module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(module, "sha256_file", lambda path: "fake_sha256")
    monkeypatch.setattr(module, "ENABLE_OCR", True)

    record = module.extract_pdf_text(pdf_path)

    assert record["ocr_applied"] is True
    assert record["ocr_error"] is None
    assert record["ocr_trigger_reasons"] == ["low_text"]
    assert record["needs_ocr_before_ocr"] is True
    assert record["needs_ocr"] is False
    assert record["remaining_text_quality_flags"] == []
    assert record["ocr_mode"] == "skip-text"
    assert len(ocr_calls) == 1
    assert ocr_calls[0]["force_ocr"] is False


def test_extract_pdf_text_records_ocr_error(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    pdf_path = tmp_path / "123_test.pdf"
    pdf_path.touch()

    def fake_extract_pages_and_counts(path: Path):
        return (
            [
                {"page_index": 0, "text": ""},
                {"page_index": 1, "text": ""},
            ],
            [0, 0],
        )

    def fake_run_ocr(input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
        raise RuntimeError("OCR failed")

    monkeypatch.setattr(module, "extract_pages_and_counts", fake_extract_pages_and_counts)
    monkeypatch.setattr(module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(module, "sha256_file", lambda path: "fake_sha256")
    monkeypatch.setattr(module, "ENABLE_OCR", True)

    record = module.extract_pdf_text(pdf_path)

    assert record["ocr_applied"] is False
    assert record["ocr_error"] == "OCR failed"
    assert record["needs_ocr_before_ocr"] is True
    assert record["needs_ocr"] is True
    assert record["remaining_text_quality_flags"] == ["low_text"]


def test_text_quality_flags_detect_control_chars() -> None:
    module = load_module()

    pages = [
        {"page_index": 0, "text": "Normal text" + "\x01" * 12},
        {"page_index": 1, "text": "More normal text"},
    ]
    char_counts = [23, 16]

    flags = module.text_quality_flags(pages, char_counts)

    assert "low_text" in flags
    assert "control_chars" in flags