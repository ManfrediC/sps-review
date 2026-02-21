from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from tqdm import tqdm

# Implement relative paths
# REPO_ROOT = Path.cwd()
REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ENABLE_OCR = True

# function to extract paper ID from filename (number preceding underscore)
def paper_id_from_filename(name: str) -> str:
    # e.g. "11849_Stiff person syndrome ....pdf" -> "11849"
    stem = Path(name).stem # stem: filename without final extension
    return stem.split("_", 1)[0] # #split max once, return initial[0] element of resulting list 

# function: checksums
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# function: detect weak text extraction quality
def needs_ocr_from_char_counts(char_counts: list[int]) -> bool:
    # heuristic: if most pages have little extracted text, OCR is likely needed
    small_pages = sum(1 for c in char_counts if c < 50)
    return len(char_counts) > 0 and (small_pages / len(char_counts)) > 0.5


def extract_pages_and_counts(pdf_path: Path) -> tuple[list[dict], list[int]]:
    # shared low-level extraction used before and after OCR
    reader = PdfReader(str(pdf_path))
    pages = []
    char_counts = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.replace("\u00a0", " ").strip()  # normalise NBSP
        pages.append({"page_index": i, "text": text})
        char_counts.append(len(text))

    return pages, char_counts


def run_ocr(input_pdf: Path, output_pdf: Path) -> None:
    # run OCRmyPDF via the current Python env to avoid PATH/venv mismatches
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ocrmypdf",
            "--skip-text",
            "--output-type",
            "pdf",
            "--rasterizer",
            "pypdfium",
            str(input_pdf),
            str(output_pdf),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


# function: extract PDF text
def extract_pdf_text(pdf_path: Path) -> dict:
    # first pass: try native PDF text extraction
    pages, char_counts = extract_pages_and_counts(pdf_path)
    initial_needs_ocr = needs_ocr_from_char_counts(char_counts)
    needs_ocr = initial_needs_ocr
    ocr_applied = False
    ocr_error = None

    if ENABLE_OCR and initial_needs_ocr:
        # OCR to a temp file, then re-extract text from OCR output
        with tempfile.TemporaryDirectory(prefix="ocr_") as tmp_dir:
            ocr_path = Path(tmp_dir) / f"{pdf_path.stem}_ocr.pdf"
            try:
                run_ocr(pdf_path, ocr_path)
                pages, char_counts = extract_pages_and_counts(ocr_path)
                needs_ocr = needs_ocr_from_char_counts(char_counts)
                ocr_applied = True
            except Exception as exc:
                ocr_error = str(exc)

    return {
        "paper_id": paper_id_from_filename(pdf_path.name),
        "source_filename": pdf_path.name,
        "source_sha256": sha256_file(pdf_path),
        "extractor": "pypdf",
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_pages": len(pages),
        # track OCR decision and result for debugging/auditing
        "needs_ocr_before_ocr": initial_needs_ocr,
        "page_char_counts": char_counts,
        "needs_ocr": needs_ocr,
        "ocr_applied": ocr_applied,
        "ocr_error": ocr_error,
        "pages": pages,
    }


def main() -> None:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in: {PDF_DIR}")

    for pdf_path in tqdm(pdfs, desc="Extracting PDF text"):
        record = extract_pdf_text(pdf_path)
        out_path = OUT_DIR / f"{record['paper_id']}.json"
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
