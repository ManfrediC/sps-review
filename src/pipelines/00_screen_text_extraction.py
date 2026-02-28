from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "text_screening_registry.csv"

ABSTRACT_CODE_RE = re.compile(r"\b(?:[A-Z]-)?[A-Z]?\d{2,3}\.")
WEBSITE_CHROME_MARKERS = (
    "home | login",
    "users online",
    "table of contents",
    "article access statistics",
    "search pubmed",
)
PROGRAM_MARKERS = (
    "annual meeting",
    "program",
    "poster sessions",
    "poster presentations",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


def load_text_records(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_path in sorted(path.glob("*.json")):
        record = json.loads(file_path.read_text(encoding="utf-8"))
        record["_path"] = file_path
        rows.append(record)
    return rows


def title_first_page(normalized_title: str, normalized_pages: list[str]) -> int:
    if not normalized_title:
        return -1
    for index, page_text in enumerate(normalized_pages):
        if normalized_title in page_text:
            return index
    return -1


def title_word_hits(normalized_title: str, normalized_full_text: str) -> tuple[int, int]:
    words = [word for word in normalized_title.split() if len(word) >= 5][:8]
    if not words:
        return 0, 0
    hits = sum(1 for word in words if word in normalized_full_text)
    return hits, len(words)


def suspicious_control_char_count(text: str) -> int:
    return sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")


def count_program_markers(normalized_pages: list[str], source_filename: str, journal: str) -> int:
    first_pages = " ".join(normalized_pages[:5])
    combined = " ".join([normalize_text(source_filename), normalize_text(journal), first_pages])
    return sum(1 for marker in PROGRAM_MARKERS if marker in combined)


def count_abstract_codes(normalized_pages: list[str]) -> int:
    window = "\n".join(normalized_pages[:40])
    return len(set(ABSTRACT_CODE_RE.findall(window)))


def has_website_chrome(normalized_pages: list[str]) -> bool:
    first_pages = " ".join(normalized_pages[:2])
    return any(marker in first_pages for marker in WEBSITE_CHROME_MARKERS)


def screen_status(
    n_pages: int,
    title_page_index: int,
    program_marker_count: int,
    abstract_code_count: int,
    control_char_count: int,
) -> tuple[str, str, str]:
    if n_pages >= 40 and title_page_index >= 5 and (program_marker_count > 0 or abstract_code_count >= 12):
        reason = (
            f"Large multi-abstract/program PDF; target title appears on page {title_page_index} "
            f"with {abstract_code_count} abstract-code markers."
        )
        return "manual_trim_recommended", "trim_to_target_pages", reason

    if control_char_count >= 5:
        reason = f"Text contains {control_char_count} suspicious control characters; review text quality."
        return "review_text_quality", "inspect_text_extraction", reason

    return "ok", "", ""


def build_row(record: dict[str, Any], reference_row: dict[str, str]) -> dict[str, str]:
    pages = record.get("pages") or []
    page_texts = [str(page.get("text") or "") for page in pages]
    normalized_pages = [normalize_text(text) for text in page_texts]
    normalized_full_text = " ".join(normalized_pages)

    title = (reference_row.get("Title") or "").strip()
    normalized_title = normalize_text(title)
    title_page_index = title_first_page(normalized_title, normalized_pages)
    title_hits, title_words = title_word_hits(normalized_title, normalized_full_text)
    control_char_count = suspicious_control_char_count("\n".join(page_texts))
    program_marker_count = count_program_markers(
        normalized_pages,
        str(record.get("source_filename") or ""),
        (reference_row.get("Journal") or "").strip(),
    )
    abstract_code_count = count_abstract_codes(normalized_pages)
    chrome_marker = has_website_chrome(normalized_pages)
    status, action, reason = screen_status(
        n_pages=int(record.get("n_pages") or 0),
        title_page_index=title_page_index,
        program_marker_count=program_marker_count,
        abstract_code_count=abstract_code_count,
        control_char_count=control_char_count,
    )

    return {
        "paper_id": str(record.get("paper_id") or record["_path"].stem),
        "covidence_id": (reference_row.get("Covidence") or str(record.get("paper_id") or "")).strip(),
        "title": title,
        "source_filename": str(record.get("source_filename") or ""),
        "n_pages": str(record.get("n_pages") or ""),
        "total_chars": str(sum(record.get("page_char_counts") or [])),
        "title_exact_match": "true" if title_page_index >= 0 else "false",
        "title_first_page": str(title_page_index if title_page_index >= 0 else ""),
        "title_word_hits": f"{title_hits}/{title_words}" if title_words else "",
        "program_marker_count": str(program_marker_count),
        "abstract_code_marker_count": str(abstract_code_count),
        "website_chrome_detected": "true" if chrome_marker else "false",
        "suspicious_control_char_count": str(control_char_count),
        "screen_status": status,
        "manual_action": action,
        "screen_reason": reason,
        "screened_at_utc": now_utc_iso(),
    }


def build_rows() -> list[dict[str, str]]:
    reference_rows = load_reference_rows(REFERENCES_CSV)
    text_records = load_text_records(TEXT_DIR)
    return [
        build_row(record, reference_rows.get(str(record.get("paper_id") or ""), {}))
        for record in text_records
    ]


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "title",
        "source_filename",
        "n_pages",
        "total_chars",
        "title_exact_match",
        "title_first_page",
        "title_word_hits",
        "program_marker_count",
        "abstract_code_marker_count",
        "website_chrome_detected",
        "suspicious_control_char_count",
        "screen_status",
        "manual_action",
        "screen_reason",
        "screened_at_utc",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_rows()
    write_rows(rows, OUTPUT_PATH)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
