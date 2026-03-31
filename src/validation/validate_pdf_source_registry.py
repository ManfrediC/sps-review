from __future__ import annotations

import argparse
import csv
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "pdf_source_registry.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
DEFAULT_DOWNLOAD_STATUS = "downloaded"


# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate sampled pdf_source_registry rows against extracted or direct PDF text."
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="Path to data/references/pdf_source_registry.csv.",
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing OCR-backed text JSON files from 03_extract_text.py.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of eligible rows to sample when --paper-id is not provided.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260331,
        help="Random seed used for reproducible sampling.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID / Covidence ID to validate. Repeat for multiple IDs.",
    )
    parser.add_argument(
        "--download-status",
        default=DEFAULT_DOWNLOAD_STATUS,
        help="Restrict validation to rows with this download_status.",
    )
    parser.add_argument(
        "--title-overlap-threshold",
        type=float,
        default=0.75,
        help="Token-overlap threshold used for fuzzy title confirmation.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON output path for the validation report.",
    )
    return parser.parse_args()


# Normalize text for fuzzy matching.
def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


# Convert normalized text into a token set.
def token_set(text: str, *, min_len: int = 4) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= min_len}


# Parse first-author surname tokens from the exported author string.
def first_author_surname_tokens(authors: str) -> list[str]:
    first = (authors or "").split(";", 1)[0].strip()
    if not first:
        return []

    if "," in first:
        surname = first.split(",", 1)[0].strip()
    else:
        parts = [part for part in re.split(r"\s+", first) if part]
        if not parts:
            return []
        if len(parts) >= 2 and all(len(re.sub(r"[^A-Za-z]", "", part)) <= 2 for part in parts[1:]):
            surname = parts[0]
        else:
            surname = parts[-1]

    return sorted(token for token in token_set(surname, min_len=2) if len(token) >= 2)


# Score title token overlap against one text block.
def title_token_overlap(title: str, text: str) -> float:
    title_tokens = token_set(title)
    if not title_tokens:
        return 0.0
    text_tokens = token_set(text)
    return len(title_tokens & text_tokens) / len(title_tokens)


# Check whether all author surname tokens are present in the text.
def author_tokens_match(author_tokens: list[str], text: str) -> bool:
    if not author_tokens:
        return False
    text_tokens = token_set(text, min_len=2)
    return all(token in text_tokens for token in author_tokens)


# Load text pages from OCR-backed extraction JSON when available.
def load_text_json_pages(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    record = json.loads(path.read_text(encoding="utf-8"))
    pages = [
        {
            "page_index": int(page.get("page_index") or 0),
            "text": str(page.get("text") or ""),
        }
        for page in (record.get("pages") or [])
    ]
    metadata = {
        "content_source": "text_json",
        "text_json_path": str(path),
        "ocr_applied": bool(record.get("ocr_applied")),
        "source_filename": str(record.get("source_filename") or ""),
    }
    return pages, metadata


# Load text pages directly from the source PDF when no text JSON is available.
def load_pdf_pages(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages):
        pages.append(
            {
                "page_index": page_index,
                "text": (page.extract_text() or "").replace("\u00a0", " "),
            }
        )
    metadata = {
        "content_source": "pdf_direct",
        "text_json_path": "",
        "ocr_applied": False,
        "source_filename": path.name,
    }
    return pages, metadata


# Resolve the best available text source for a registry row.
def load_text_pages(row: dict[str, str], text_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paper_id = (row.get("covidence_id") or "").strip()
    text_json_path = text_dir / f"{paper_id}.json"
    if text_json_path.exists():
        return load_text_json_pages(text_json_path)

    pdf_path = Path((row.get("pdf_path_absolute") or "").strip())
    if pdf_path.exists():
        return load_pdf_pages(pdf_path)

    return [], {
        "content_source": "missing",
        "text_json_path": "",
        "ocr_applied": False,
        "source_filename": "",
    }


# Find pages containing the normalized query exactly.
def exact_match_pages(query: str, pages: list[dict[str, Any]]) -> list[int]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return []
    matched_pages: list[int] = []
    for page in pages:
        if normalized_query in normalize_text(str(page.get("text") or "")):
            matched_pages.append(int(page.get("page_index") or 0))
    return matched_pages


# Find pages containing all author surname tokens.
def author_match_pages(author_tokens: list[str], pages: list[dict[str, Any]]) -> list[int]:
    if not author_tokens:
        return []
    matched_pages: list[int] = []
    for page in pages:
        if author_tokens_match(author_tokens, str(page.get("text") or "")):
            matched_pages.append(int(page.get("page_index") or 0))
    return matched_pages


# Find the page with the strongest title token overlap.
def best_title_page(title: str, pages: list[dict[str, Any]]) -> tuple[int, float]:
    best_page_index = -1
    best_score = 0.0
    for page in pages:
        score = title_token_overlap(title, str(page.get("text") or ""))
        if score > best_score:
            best_score = score
            best_page_index = int(page.get("page_index") or 0)
    return best_page_index, best_score


# Find pages whose title-token overlap clears the fuzzy-match threshold.
def title_overlap_pages(title: str, pages: list[dict[str, Any]], *, threshold: float) -> list[int]:
    matched_pages: list[int] = []
    for page in pages:
        score = title_token_overlap(title, str(page.get("text") or ""))
        if score >= threshold:
            matched_pages.append(int(page.get("page_index") or 0))
    return matched_pages


# Build a short excerpt from the selected page.
def page_excerpt(pages: list[dict[str, Any]], page_index: int, *, max_chars: int = 320) -> str:
    if page_index < 0:
        return ""
    for page in pages:
        if int(page.get("page_index") or 0) != page_index:
            continue
        flattened = " ".join(str(page.get("text") or "").split())
        return flattened[:max_chars]
    return ""


# Limit verbose page-index arrays in the human-readable report.
def page_preview(pages: list[int], *, max_items: int = 5) -> list[int | str]:
    if len(pages) <= max_items:
        return pages
    return [*pages[:max_items], "...", pages[-1]]


# Prefer title/author evidence that appears on the same or adjacent pages.
def nearby_pages(left_pages: list[int], right_pages: list[int], *, max_distance: int = 1) -> list[int]:
    matched: list[int] = []
    for left_page in left_pages:
        if any(abs(left_page - right_page) <= max_distance for right_page in right_pages):
            matched.append(left_page)
    return matched


# Derive a validation status for one sampled row.
def validation_status_for(
    *,
    title_exact_pages: list[int],
    fuzzy_title_author_pages: list[int],
    best_title_overlap: float,
    author_pages: list[int],
    year_pages: list[int],
    threshold: float,
) -> str:
    title_confirmed = bool(title_exact_pages) or best_title_overlap >= threshold
    author_confirmed = bool(author_pages)
    if title_exact_pages and author_confirmed:
        if title_exact_pages:
            return "confirmed_exact"
    if fuzzy_title_author_pages:
        return "confirmed_fuzzy_title"
    if title_confirmed and year_pages:
        return "title_year_only"
    if author_confirmed and year_pages:
        return "author_year_only"
    if title_confirmed:
        return "title_only"
    if author_confirmed:
        return "author_only"
    return "no_match"


# Validate a single registry row against the best available text source.
def validate_row(row: dict[str, str], *, text_dir: Path, title_overlap_threshold: float) -> dict[str, Any]:
    pages, metadata = load_text_pages(row, text_dir)
    full_text = "\n".join(str(page.get("text") or "") for page in pages)
    title_exact_pages = exact_match_pages(row.get("title", ""), pages)
    title_fuzzy_pages = title_overlap_pages(
        row.get("title", ""),
        pages,
        threshold=title_overlap_threshold,
    )
    author_tokens = first_author_surname_tokens(row.get("authors", ""))
    author_pages = author_match_pages(author_tokens, pages)
    fuzzy_title_author_pages = nearby_pages(title_fuzzy_pages, author_pages)
    year_text = (row.get("published_year") or "").strip()
    year_pages = [
        int(page.get("page_index") or 0)
        for page in pages
        if year_text and year_text in str(page.get("text") or "")
    ]
    best_title_page_index, best_title_overlap = best_title_page(row.get("title", ""), pages)
    status = validation_status_for(
        title_exact_pages=title_exact_pages,
        fuzzy_title_author_pages=fuzzy_title_author_pages,
        best_title_overlap=best_title_overlap,
        author_pages=author_pages,
        year_pages=year_pages,
        threshold=title_overlap_threshold,
    )
    excerpt_page_index = (
        title_exact_pages[0]
        if title_exact_pages
        else (
            fuzzy_title_author_pages[0]
            if fuzzy_title_author_pages
            else (title_fuzzy_pages[0] if title_fuzzy_pages else (author_pages[0] if author_pages else best_title_page_index))
        )
    )
    return {
        "covidence_id": (row.get("covidence_id") or "").strip(),
        "ref": (row.get("ref") or "").strip(),
        "study": (row.get("study") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "authors": (row.get("authors") or "").strip(),
        "published_year": year_text,
        "pdf_filename": (row.get("pdf_filename") or "").strip(),
        "pdf_path_relative": (row.get("pdf_path_relative") or "").strip(),
        "download_status": (row.get("download_status") or "").strip(),
        "manifest_status": (row.get("manifest_status") or "").strip(),
        "content_source": metadata["content_source"],
        "text_json_path": metadata["text_json_path"],
        "ocr_applied": metadata["ocr_applied"],
        "source_filename": metadata["source_filename"],
        "n_pages": len(pages),
        "title_exact_pages": title_exact_pages,
        "title_fuzzy_pages": title_fuzzy_pages,
        "fuzzy_title_author_pages": fuzzy_title_author_pages,
        "best_title_page_index": best_title_page_index,
        "best_title_overlap": round(best_title_overlap, 3),
        "author_surname_tokens": author_tokens,
        "author_match_pages": author_pages,
        "year_match_pages": year_pages,
        "validation_status": status,
        "validation_excerpt": page_excerpt(pages, excerpt_page_index),
        "text_char_count": len(full_text),
    }


# Load registry rows.
def load_registry_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# Filter registry rows to a validation-eligible pool.
def eligible_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    explicit_ids = {paper_id.strip() for paper_id in args.paper_id if paper_id.strip()}
    filtered: list[dict[str, str]] = []
    for row in rows:
        covidence_id = (row.get("covidence_id") or "").strip()
        if explicit_ids and covidence_id not in explicit_ids:
            continue
        if not explicit_ids:
            if (row.get("download_status") or "").strip() != args.download_status:
                continue
            if (row.get("local_file_count") or "").strip() != "1":
                continue
        pdf_path = Path((row.get("pdf_path_absolute") or "").strip()) if (row.get("pdf_path_absolute") or "").strip() else None
        if pdf_path is not None and not pdf_path.exists():
            continue
        filtered.append(row)
    return filtered


# Select rows deterministically for audit.
def sampled_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    if args.paper_id:
        return rows
    ordered = list(rows)
    rng = random.Random(args.seed)
    rng.shuffle(ordered)
    return ordered[: max(0, args.sample_size)]


# Build a report payload for machine-readable storage.
def build_report(args: argparse.Namespace, eligible_count: int, sampled_count: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row.get("validation_status") or "") for row in rows)
    confirmed_count = sum(
        1
        for row in rows
        if str(row.get("validation_status") or "").startswith("confirmed_")
    )
    report = {
        "registry_path": str(args.registry_path),
        "text_dir": str(args.text_dir),
        "seed": args.seed,
        "sample_size_requested": args.sample_size,
        "eligible_count": eligible_count,
        "sampled_count": sampled_count,
        "download_status_filter": args.download_status,
        "title_overlap_threshold": args.title_overlap_threshold,
        "status_counts": dict(status_counts),
        "confirmed_fraction": (confirmed_count / sampled_count) if sampled_count else 0.0,
        "rows": rows,
    }
    return report


# Print a concise human-readable summary.
def print_report(report: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "eligible_count": report["eligible_count"],
                "sampled_count": report["sampled_count"],
                "seed": report["seed"],
                "status_counts": report["status_counts"],
                "confirmed_fraction": round(float(report["confirmed_fraction"]), 3),
            },
            ensure_ascii=True,
        )
    )
    for row in report["rows"]:
        compact = {
            "covidence_id": row["covidence_id"],
            "pdf_filename": row["pdf_filename"],
            "validation_status": row["validation_status"],
            "content_source": row["content_source"],
            "ocr_applied": row["ocr_applied"],
            "title_exact_pages": page_preview(row["title_exact_pages"]),
            "title_fuzzy_pages": page_preview(row["title_fuzzy_pages"]),
            "fuzzy_title_author_pages": page_preview(row["fuzzy_title_author_pages"]),
            "best_title_page_index": row["best_title_page_index"],
            "best_title_overlap": row["best_title_overlap"],
            "author_match_pages": page_preview(row["author_match_pages"]),
            "year_match_pages": page_preview(row["year_match_pages"]),
            "validation_excerpt": row["validation_excerpt"],
        }
        print(json.dumps(compact, ensure_ascii=True))


# Write JSON report when requested.
def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


# Run the validation entrypoint.
def main() -> None:
    args = parse_args()
    registry_rows = load_registry_rows(args.registry_path)
    filtered_rows = eligible_rows(registry_rows, args)
    selected_rows = sampled_rows(filtered_rows, args)
    validated_rows = [
        validate_row(
            row,
            text_dir=args.text_dir,
            title_overlap_threshold=args.title_overlap_threshold,
        )
        for row in selected_rows
    ]
    report = build_report(
        args,
        eligible_count=len(filtered_rows),
        sampled_count=len(validated_rows),
        rows=validated_rows,
    )
    print_report(report)
    if args.output_path is not None:
        write_report(report, args.output_path)


if __name__ == "__main__":
    main()
