from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from tqdm import tqdm

# Resolve repository-relative paths once for stable script behaviour.
REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Toggle OCR fallback for PDFs with poor native text extraction.
ENABLE_OCR = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract PDF text with OCR fallback."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PDF_DIR,
        help="Directory containing source PDFs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help="Directory where text extraction JSON files are written.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of PDFs to process.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing text JSON outputs.")
    return parser.parse_args()

# Extract paper ID from filename (digits before first underscore).
def paper_id_from_filename(name: str) -> str:
    # e.g. "11849_Stiff person syndrome ....pdf" -> "11849"
    stem = Path(name).stem  # stem: filename without final extension
    return stem.split("_", 1)[0]  # split once; return prefix before "_"

# Compute file checksum for provenance and deduplication checks.
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    # Stream file in chunks to avoid high memory usage on large PDFs.
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# Heuristic to decide whether OCR is likely needed.
def needs_ocr_from_char_counts(char_counts: list[int]) -> bool:
    # heuristic: if most pages have little extracted text, OCR is likely needed
    small_pages = sum(1 for c in char_counts if c < 50)
    return len(char_counts) > 0 and (small_pages / len(char_counts)) > 0.5


# Count suspicious embedded control characters in extracted text.
def suspicious_control_char_count(text: str) -> int:
    return sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")


# Detect native-text quality issues that justify an OCR retry.
def text_quality_flags(pages: list[dict], char_counts: list[int]) -> list[str]:
    flags: list[str] = []
    if needs_ocr_from_char_counts(char_counts):
        flags.append("low_text")

    full_text = "\n".join((page.get("text") or "") for page in pages)
    control_chars = suspicious_control_char_count(full_text)
    total_chars = sum(char_counts)
    if control_chars >= 10 or (control_chars > 0 and total_chars > 0 and (control_chars / total_chars) > 0.002):
        flags.append("control_chars")

    return flags


# Extract page text plus per-page character counts from one PDF.
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


# Run OCRmyPDF to produce a text-searchable PDF copy.
def run_ocr(input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
    # run OCRmyPDF via the current Python env to avoid PATH/venv mismatches
    command = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "--output-type",
        "pdf",
        "--rasterizer",
        "pypdfium",
    ]
    command.append("--force-ocr" if force_ocr else "--skip-text")
    command.extend([str(input_pdf), str(output_pdf)])
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


# Extract text record for one PDF, with optional OCR fallback.
def extract_pdf_text(pdf_path: Path) -> dict:
    # first pass: try native PDF text extraction
    pages, char_counts = extract_pages_and_counts(pdf_path)
    initial_quality_flags = text_quality_flags(pages, char_counts)
    initial_needs_ocr = bool(initial_quality_flags)
    needs_ocr = initial_needs_ocr
    ocr_applied = False
    ocr_error = None
    ocr_mode = ""

    if ENABLE_OCR and initial_needs_ocr:
        # OCR to a temp file, then re-extract text from OCR output
        with tempfile.TemporaryDirectory(prefix="ocr_") as tmp_dir:
            ocr_path = Path(tmp_dir) / f"{pdf_path.stem}_ocr.pdf"
            try:
                force_ocr = "control_chars" in initial_quality_flags
                ocr_mode = "force-ocr" if force_ocr else "skip-text"
                run_ocr(pdf_path, ocr_path, force_ocr=force_ocr)
                pages, char_counts = extract_pages_and_counts(ocr_path)
                ocr_applied = True
            except Exception as exc:
                ocr_error = str(exc)

    final_quality_flags = text_quality_flags(pages, char_counts)
    needs_ocr = bool(final_quality_flags)
    suspicious_control_chars = suspicious_control_char_count(
        "\n".join((page.get("text") or "") for page in pages)
    )

    return {
        "paper_id": paper_id_from_filename(pdf_path.name),
        "source_filename": pdf_path.name,
        "source_sha256": sha256_file(pdf_path),
        "extractor": "pypdf",
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_pages": len(pages),
        # track OCR decision and result for debugging/auditing
        "needs_ocr_before_ocr": initial_needs_ocr,
        "ocr_trigger_reasons": initial_quality_flags,
        "page_char_counts": char_counts,
        "suspicious_control_chars": suspicious_control_chars,
        "needs_ocr": needs_ocr,
        "remaining_text_quality_flags": final_quality_flags,
        "ocr_applied": ocr_applied,
        "ocr_mode": ocr_mode,
        "ocr_error": ocr_error,
        "pages": pages,
    }


def collect_input_pdfs(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    pdfs = sorted(input_dir.glob("*.pdf"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        pdfs = [pdf_path for pdf_path in pdfs if paper_id_from_filename(pdf_path.name) in wanted]
    if limit and limit > 0:
        pdfs = pdfs[:limit]
    return pdfs


# Batch all PDFs in PDF_DIR and write one JSON record per paper_id.
def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = collect_input_pdfs(args.input_dir, args.paper_id, args.limit)
    if not pdfs:
        raise SystemExit(f"No PDFs found in: {args.input_dir}")

    # Process every PDF and save a structured text extraction JSON.
    for pdf_path in tqdm(pdfs, desc="Extracting PDF text"):
        paper_id = paper_id_from_filename(pdf_path.name)
        out_path = args.output_dir / f"{paper_id}.json"
        if out_path.exists() and not args.force:
            continue
        record = extract_pdf_text(pdf_path)
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


# Standard Python entry point.
if __name__ == "__main__":
    main()
