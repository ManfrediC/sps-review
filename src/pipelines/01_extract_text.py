from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from tqdm import tqdm


REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def paper_id_from_filename(name: str) -> str:
    # e.g. "11849_Stiff person syndrome ....pdf" -> "11849"
    stem = Path(name).stem
    return stem.split("_", 1)[0]


def extract_pdf_text(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    pages = []
    char_counts = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.replace("\u00a0", " ").strip()  # normalise NBSP
        pages.append({"page_index": i, "text": text})
        char_counts.append(len(text))

    small_pages = sum(1 for c in char_counts if c < 50)
    needs_ocr = len(char_counts) > 0 and (small_pages / len(char_counts)) > 0.5

    return {
        "paper_id": paper_id_from_filename(pdf_path.name),
        "source_filename": pdf_path.name,
        "source_sha256": sha256_file(pdf_path),
        "extractor": "pypdf",
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_pages": len(reader.pages),
        "page_char_counts": char_counts,
        "needs_ocr": needs_ocr,
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