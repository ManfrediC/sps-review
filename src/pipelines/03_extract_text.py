from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from tqdm import tqdm

# Resolve repository-relative paths once for stable script behaviour.
REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OVERRIDE_PATH = REPO_ROOT / "config" / "extraction" / "text_extraction_overrides.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Toggle OCR fallback for PDFs with poor native text extraction.
ENABLE_OCR = True
ERROR_SNIPPET_LIMIT = 4000


# Parse command-line arguments.
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
        "--override-path",
        type=Path,
        default=OVERRIDE_PATH,
        help="CSV file containing per-paper extraction overrides.",
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


def load_extraction_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["covidence_id"].strip(): row
            for row in csv.DictReader(handle)
            if (row.get("covidence_id") or "").strip()
        }

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


def extract_pages_and_counts_pdftotext(pdf_path: Path) -> tuple[list[dict], list[int]]:
    proc = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw_text = proc.stdout or ""
    page_texts = raw_text.split("\f")
    if page_texts and page_texts[-1] == "":
        page_texts = page_texts[:-1]

    pages = []
    char_counts = []
    for i, text in enumerate(page_texts):
        cleaned = text.replace("\u00a0", " ").strip()
        pages.append({"page_index": i, "text": cleaned})
        char_counts.append(len(cleaned))

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


def truncate_output(text: str | None, *, limit: int = ERROR_SNIPPET_LIMIT) -> str | None:
    if not text:
        return None
    return text[-limit:]


def serialise_exception(exc: Exception) -> dict:
    details: dict[str, object] = {
        "exception_type": exc.__class__.__name__,
        "message": str(exc),
    }
    if isinstance(exc, subprocess.CalledProcessError):
        details["returncode"] = exc.returncode
        cmd = exc.cmd
        if isinstance(cmd, Sequence) and not isinstance(cmd, (str, bytes)):
            details["command"] = list(cmd)
        elif cmd is not None:
            details["command"] = str(cmd)
        stdout_tail = truncate_output(exc.stdout)
        stderr_tail = truncate_output(exc.stderr)
        if stdout_tail is not None:
            details["stdout_tail"] = stdout_tail
        if stderr_tail is not None:
            details["stderr_tail"] = stderr_tail
    return details


def base_record(pdf_path: Path) -> dict:
    return {
        "paper_id": paper_id_from_filename(pdf_path.name),
        "source_filename": pdf_path.name,
        "source_sha256": sha256_file(pdf_path),
        "extractor": "pypdf",
        "extraction_override_strategy": None,
        "extraction_override_notes": None,
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_pages": 0,
        # track OCR decision and result for debugging/auditing
        "needs_ocr_before_ocr": False,
        "ocr_trigger_reasons": [],
        "page_char_counts": [],
        "suspicious_control_chars": 0,
        "needs_ocr": False,
        "remaining_text_quality_flags": [],
        "ocr_applied": False,
        "ocr_mode": "",
        "ocr_error": None,
        "native_extraction_error": None,
        "processing_error": None,
        "pages": [],
    }


def finalise_record(record: dict, pages: list[dict], char_counts: list[int]) -> dict:
    final_quality_flags = text_quality_flags(pages, char_counts)
    record["n_pages"] = len(pages)
    record["page_char_counts"] = char_counts
    record["suspicious_control_chars"] = suspicious_control_char_count(
        "\n".join((page.get("text") or "") for page in pages)
    )
    record["needs_ocr"] = bool(final_quality_flags) or (
        (record["native_extraction_error"] is not None or record["ocr_error"] is not None)
        and not record["ocr_applied"]
    )
    record["remaining_text_quality_flags"] = final_quality_flags
    record["pages"] = pages
    return record


def build_processing_error_record(pdf_path: Path, exc: Exception) -> dict:
    record = base_record(pdf_path)
    record["processing_error"] = serialise_exception(exc)
    return record


def write_json_atomic(out_path: Path, record: dict) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=out_path.parent,
            prefix=f"{out_path.stem}_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(record, ensure_ascii=False, indent=2))
            tmp_path = Path(handle.name)
        tmp_path.replace(out_path)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def apply_override_metadata(record: dict, override: dict[str, str] | None) -> None:
    if not override:
        return
    strategy = (override.get("strategy") or "").strip()
    notes = (override.get("notes") or "").strip()
    record["extraction_override_strategy"] = strategy or None
    record["extraction_override_notes"] = notes or None


# Extract text record for one PDF, with optional OCR fallback.
def extract_pdf_text(pdf_path: Path, *, override: dict[str, str] | None = None) -> dict:
    record = base_record(pdf_path)
    apply_override_metadata(record, override)
    pages: list[dict] = []
    char_counts: list[int] = []
    strategy = (override or {}).get("strategy", "").strip()

    if strategy == "pdftotext":
        pages, char_counts = extract_pages_and_counts_pdftotext(pdf_path)
        record["extractor"] = "pdftotext"
        return finalise_record(record, pages, char_counts)

    if strategy == "force_ocr":
        record["needs_ocr_before_ocr"] = True
        record["ocr_trigger_reasons"] = ["override_force_ocr"]
        if ENABLE_OCR:
            with tempfile.TemporaryDirectory(prefix="ocr_") as tmp_dir:
                ocr_path = Path(tmp_dir) / f"{pdf_path.stem}_ocr.pdf"
                try:
                    record["ocr_mode"] = "force-ocr"
                    run_ocr(pdf_path, ocr_path, force_ocr=True)
                    pages, char_counts = extract_pages_and_counts_pdftotext(ocr_path)
                    record["extractor"] = "pdftotext"
                    record["ocr_applied"] = True
                except Exception as exc:
                    record["ocr_error"] = serialise_exception(exc)
        return finalise_record(record, pages, char_counts)

    try:
        # first pass: try native PDF text extraction
        pages, char_counts = extract_pages_and_counts(pdf_path)
    except Exception as exc:
        record["native_extraction_error"] = serialise_exception(exc)
        record["needs_ocr_before_ocr"] = True
        record["ocr_trigger_reasons"] = ["native_extraction_error"]

        if ENABLE_OCR:
            with tempfile.TemporaryDirectory(prefix="ocr_") as tmp_dir:
                ocr_path = Path(tmp_dir) / f"{pdf_path.stem}_ocr.pdf"
                try:
                    record["ocr_mode"] = "force-ocr"
                    run_ocr(pdf_path, ocr_path, force_ocr=True)
                    pages, char_counts = extract_pages_and_counts(ocr_path)
                    record["ocr_applied"] = True
                except Exception as ocr_exc:
                    record["ocr_error"] = serialise_exception(ocr_exc)

        return finalise_record(record, pages, char_counts)

    initial_quality_flags = text_quality_flags(pages, char_counts)
    record["needs_ocr_before_ocr"] = bool(initial_quality_flags)
    record["ocr_trigger_reasons"] = initial_quality_flags

    if ENABLE_OCR and initial_quality_flags:
        # OCR to a temp file, then re-extract text from OCR output
        with tempfile.TemporaryDirectory(prefix="ocr_") as tmp_dir:
            ocr_path = Path(tmp_dir) / f"{pdf_path.stem}_ocr.pdf"
            try:
                force_ocr = "control_chars" in initial_quality_flags
                record["ocr_mode"] = "force-ocr" if force_ocr else "skip-text"
                run_ocr(pdf_path, ocr_path, force_ocr=force_ocr)
                pages, char_counts = extract_pages_and_counts(ocr_path)
                record["ocr_applied"] = True
            except Exception as exc:
                record["ocr_error"] = serialise_exception(exc)

    return finalise_record(record, pages, char_counts)


# Collect input pdfs.
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

    overrides = load_extraction_overrides(args.override_path)
    failed_papers: list[str] = []

    # Process every PDF and save a structured text extraction JSON.
    for pdf_path in tqdm(pdfs, desc="Extracting PDF text"):
        paper_id = paper_id_from_filename(pdf_path.name)
        out_path = args.output_dir / f"{paper_id}.json"
        if out_path.exists() and not args.force:
            continue
        try:
            record = extract_pdf_text(pdf_path, override=overrides.get(paper_id))
        except Exception as exc:
            failed_papers.append(paper_id)
            record = build_processing_error_record(pdf_path, exc)
        else:
            if record["processing_error"] is not None:
                failed_papers.append(paper_id)
            elif record["native_extraction_error"] is not None and not record["ocr_applied"]:
                failed_papers.append(paper_id)
            elif record["ocr_error"] is not None and record["needs_ocr"]:
                failed_papers.append(paper_id)

        write_json_atomic(out_path, record)

    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )

    if failed_papers:
        raise SystemExit(f"Text extraction completed with {len(failed_papers)} failed PDF(s).")


# Standard Python entry point.
if __name__ == "__main__":
    main()
