from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tqdm import tqdm

from _proceedings_text import (
    LineRef,
    ProceedingsPattern,
    abstract_code,
    body_char_count,
    find_next_header_index,
    find_previous_header_index,
    flatten_lines,
    has_enough_body,
    header_boundary,
    header_start_indices,
    infer_proceedings_pattern,
    is_abstract_boundary,
    is_abstract_code_only,
    is_abstract_start,
    is_author_like,
    is_disclosure_detail_line,
    is_footer_like,
    is_header_preamble_line,
    is_institution_like,
    is_article_metadata_line,
    is_article_numbered_section,
    is_potential_title_line,
    is_retained_tail_metadata_line,
    is_section_heading,
    is_trimmable_tail_metadata_line,
    normalize_code,
    normalize_text,
    score_authors,
    score_title,
    strip_abstract_code,
    token_set,
)
from _source_routing import load_csv_rows_by_id, resolve_source_row


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"

INDEX_ENTRY_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5})\s*(?:[\.\|\:\-\)]\s*)?(?P<title>.+?)\s+(?P<page>\d{1,4})$"
)
INDEX_TRAILING_PAGE_RE = re.compile(r"^(?P<title>.+?)\s+(?P<page>\d{1,4})$")
PROGRAM_MARKERS = (
    "annual meeting",
    "program and abstracts",
    "program abstracts",
    "poster sessions",
    "poster presentations",
    "table of contents",
    "contents",
    "index",
)
ISOLATED_ABSTRACT_PAGE_MARKERS = (
    "first published",
    "authors info affiliations",
    "aan publications",
    "letters to the editor",
    "submit a letter for this article",
    "the most widely read and highly cited",
    "sign insubscribe",
    "latest articles",
    "current issue",
    "past issues",
    "manage cookie preferences",
)
EVENT_CODE_ONLY_RE = re.compile(r"^[A-Z]{3,5}\d{2,4}-\d{3,5}$", re.IGNORECASE)


# Define abstractblock.
@dataclass
class AbstractBlock:
    code: str
    start_index: int
    end_index: int
    start_page_index: int
    end_page_index: int
    title_text: str
    header_text: str
    preview_text: str
    line_refs: list[LineRef]
    title_score: float = 0.0
    author_score: float = 0.0
    match_score: float = 0.0
    trim_method: str = ""
    trim_mode: str = ""
    start_rule: str = ""
    end_rule: str = ""
    body_signal_count: int = 0
    spillover_flag: bool = False
    header_only_flag: bool = False
    index_detected: bool = False
    index_confidence: float = 0.0
    index_listed_page: str = ""
    index_prev_code: str = ""
    index_next_code: str = ""
    page_map_method: str = ""
    estimated_offset: float = 0.0
    offset_confidence: float = 0.0
    candidate_rank: int = 1
    fallback_triggered: bool = False


# Define indexentry.
@dataclass
class IndexEntry:
    code: str
    title: str
    listed_page: int | None
    index_page_index: int
    raw_text: str


# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim multi-abstract proceedings PDFs down to the target abstract only."
    )
    parser.add_argument(
        "--references-csv",
        type=Path,
        default=REFERENCES_CSV,
        help="Reference export CSV containing Covidence IDs, titles, and authors.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing full text extraction JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help="Directory for trimmed text JSON files.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="CSV registry describing trimming decisions.",
    )
    parser.add_argument(
        "--source-categorisation-path",
        type=Path,
        default=SOURCE_CATEGORISATION_PATH,
        help="Stage-04 source categorisation registry.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=SOURCE_MANUAL_REVIEW_PATH,
        help="Manual source categorisation overrides.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument(
        "--all-papers",
        action="store_true",
        help="Process all extracted papers instead of restricting to resolved proceedings category.",
    )
    parser.add_argument(
        "--include-already-trimmed",
        action="store_true",
        help="Also process proceedings entries already marked as trimmed_auto in the existing trim registry.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of text JSON files to process.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after trimming.",
    )
    return parser.parse_args()


# Build now utc iso.
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Convert a path to a repository-relative string.
def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


# Build bool text.
def bool_text(value: bool) -> str:
    return "true" if value else "false"


# Load reference rows.
def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


# Collect input paths.
def collect_input_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


# Filter to proceedings candidates.
def filter_to_proceedings_candidates(
    paths: list[Path],
    source_categorisation_path: Path,
    source_manual_review_path: Path,
    existing_trim_registry_path: Path,
    force_all_papers: bool,
    explicit_paper_ids: list[str],
    include_already_trimmed: bool,
) -> list[Path]:
    if force_all_papers:
        return paths
    if not source_categorisation_path.exists():
        return paths

    heuristic_rows = load_csv_rows_by_id(source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(source_manual_review_path, "paper_id")
    existing_trim_rows = load_csv_rows_by_id(existing_trim_registry_path, "paper_id")
    filtered: list[Path] = []
    for path in paths:
        paper_id = path.stem
        resolved = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        if (resolved.get("resolved_source_category") or "") != "conference_abstract":
            continue
        if not include_already_trimmed:
            existing_row = existing_trim_rows.get(paper_id, {})
            if (existing_row.get("trim_status") or "").strip() == "trimmed_auto":
                continue
        filtered.append(path)
    return filtered


# Load text record.
def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Build page match scores.
def page_match_scores(
    record: dict[str, Any],
    reference_title: str,
    reference_authors: str,
) -> tuple[int, float, float, float]:
    best_page_index = 0
    best_title_score = 0.0
    best_author_score = 0.0
    best_combined = 0.0
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "").strip()
        if not page_text:
            continue
        title_score = score_title(reference_title, page_text)
        author_score = score_authors(reference_authors, page_text)
        combined = (0.75 * title_score) + (0.25 * author_score)
        if combined > best_combined:
            best_page_index = page_index
            best_title_score = title_score
            best_author_score = author_score
            best_combined = combined
    return best_page_index, best_title_score, best_author_score, best_combined


# Build truncate at next header.
def truncate_at_next_header(
    lines: list[LineRef],
    expected_code: str,
    next_entry: IndexEntry | None,
    pattern: ProceedingsPattern,
) -> tuple[list[LineRef], bool, str]:
    if len(lines) < 5:
        return lines, False, "no_header_found"
    next_index, rule = find_next_header_index(
        lines=lines,
        start_index=0,
        pattern=pattern,
        expected_code=expected_code,
        next_code=next_entry.code if next_entry else "",
        min_gap=4,
    )
    if next_index is None:
        return lines, False, "no_header_found"
    return lines[:next_index], True, rule


def trim_trailing_header_noise(lines: list[LineRef]) -> tuple[list[LineRef], bool]:
    if len(lines) < 7:
        return lines, False
    enough_body, section_hits, _ = has_enough_body(lines)
    if not enough_body and section_hits == 0:
        return lines, False
    saw_authorship = any(is_author_like(line.text) or is_institution_like(line.text) for line in lines[:8])
    saw_body_heading = False
    for index, line_ref in enumerate(lines):
        if is_author_like(line_ref.text) or is_institution_like(line_ref.text):
            saw_authorship = True
        if saw_authorship and is_section_heading(line_ref.text):
            normalized = normalize_text(line_ref.text)
            if normalized in {"case report", "case study", "case series"} and ":" not in line_ref.text:
                continue
            saw_body_heading = True
        if not saw_body_heading:
            continue
        if is_retained_tail_metadata_line(line_ref.text):
            continue
        if is_trimmable_tail_metadata_line(line_ref.text):
            return lines[:index], True
    return lines, False


def trim_leading_header_noise(lines: list[LineRef]) -> tuple[list[LineRef], bool]:
    if len(lines) < 2:
        return lines, False
    start_index = 0
    max_probe = min(len(lines), 6)
    while start_index < max_probe - 1:
        current = lines[start_index].text
        current_is_event_code = bool(EVENT_CODE_ONLY_RE.match(current.strip()))
        if is_abstract_start(current) is not None:
            break
        if is_abstract_code_only(current) is not None and not current_is_event_code:
            break
        if is_potential_title_line(current):
            break
        if not (
            is_footer_like(current)
            or is_header_preamble_line(current)
            or is_disclosure_detail_line(current)
            or current_is_event_code
        ):
            break
        lookahead = lines[start_index + 1 : min(len(lines), start_index + 5)]
        if not any(
            is_potential_title_line(line.text) or is_abstract_start(line.text) is not None
            for line in lookahead
        ):
            break
        start_index += 1
    if start_index == 0:
        return lines, False
    return lines[start_index:], True


# Parse index entries.
def parse_index_entries(record: dict[str, Any]) -> tuple[list[IndexEntry], bool]:
    entries: list[IndexEntry] = []
    index_page_count = 0
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        lines = [" ".join(raw.split()) for raw in page_text.splitlines() if raw.strip()]
        normalized_page = normalize_text(page_text)
        page_entries: list[IndexEntry] = []

        for line in lines:
            match = INDEX_ENTRY_RE.match(line)
            if match:
                listed_page = int(match.group("page")) if match.group("page").isdigit() else None
                page_entries.append(
                    IndexEntry(
                        code=match.group("code").strip(),
                        title=match.group("title").strip(),
                        listed_page=listed_page,
                        index_page_index=page_index,
                        raw_text=line,
                    )
                )

        for idx, line in enumerate(lines[:-1]):
            if INDEX_ENTRY_RE.match(line):
                continue
            if not is_abstract_boundary(line):
                continue
            next_line = lines[idx + 1]
            trailing_page_match = INDEX_TRAILING_PAGE_RE.match(next_line)
            if not trailing_page_match:
                continue
            listed_page = int(trailing_page_match.group("page")) if trailing_page_match.group("page").isdigit() else None
            title_text = strip_abstract_code(line)
            if trailing_page_match.group("title").strip():
                title_text = f"{title_text} {trailing_page_match.group('title').strip()}".strip()
            page_entries.append(
                IndexEntry(
                    code=abstract_code(line),
                    title=title_text,
                    listed_page=listed_page,
                    index_page_index=page_index,
                    raw_text=f"{line} {next_line}",
                )
            )

        likely_index_page = len(page_entries) >= 8 or (
            len(page_entries) >= 4
            and (
                "contents" in normalized_page
                or "table of contents" in normalized_page
                or "index" in normalized_page
                or "program and abstracts" in normalized_page
            )
        )
        if likely_index_page:
            index_page_count += 1
            entries.extend(page_entries)

    index_detected = index_page_count > 0 or len(entries) >= 16
    return entries, index_detected


# Build best index entry.
def best_index_entry(
    entries: list[IndexEntry],
    reference_title: str,
) -> tuple[IndexEntry | None, float, float]:
    if not entries:
        return None, 0.0, 0.0
    scored: list[tuple[float, IndexEntry]] = []
    for entry in entries:
        score = score_title(reference_title, entry.title)
        if normalize_code(entry.code):
            score = min(1.0, score + 0.03)
        scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best_entry = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    confidence = max(0.0, best_score - max(0.0, second - 0.08))
    return best_entry, confidence, second


# Build line matches code.
def line_matches_code(line: str, code: str) -> bool:
    if not code:
        return False
    line_code = abstract_code(line)
    if line_code and normalize_code(line_code) == normalize_code(code):
        return True
    normalized_line = normalize_code(line)
    return bool(normalized_line) and normalize_code(code) in normalized_line


# Build estimate page offset.
def estimate_page_offset(record: dict[str, Any], entries: list[IndexEntry]) -> tuple[float, float, str]:
    offsets: list[float] = []
    pages = record.get("pages") or []
    if not pages or not entries:
        return 0.0, 0.0, "none"

    # Build a fast code->first_page map once per record.
    code_to_page: dict[str, int] = {}
    page_text_cache: list[tuple[int, str]] = []
    for page in pages:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        page_text_cache.append((page_index, page_text))
        for raw in page_text.splitlines():
            line = " ".join(raw.split())
            if not line:
                continue
            code_norm = normalize_code(abstract_code(line))
            if code_norm and code_norm not in code_to_page:
                code_to_page[code_norm] = page_index

    listed_entries = [entry for entry in entries if entry.listed_page is not None]
    if not listed_entries:
        return 0.0, 0.0, "insufficient_matches"

    # Prefer code-anchored offsets; they are cheaper and more stable than title scans.
    for entry in listed_entries[:120]:
        code_norm = normalize_code(entry.code)
        if not code_norm:
            continue
        matched_page = code_to_page.get(code_norm)
        if matched_page is not None:
            offsets.append(float(matched_page - int(entry.listed_page)))

    # Fall back to title anchors only if code anchors are sparse.
    if len(offsets) < 2:
        title_candidates = [
            entry for entry in listed_entries if len(token_set(entry.title, min_len=4)) >= 4
        ][:8]
        for entry in title_candidates:
            best_page = -1
            best_score = 0.0
            for page_index, page_text in page_text_cache:
                score = score_title(entry.title, page_text)
                if score > best_score:
                    best_page = page_index
                    best_score = score
            if best_page >= 0 and best_score >= 0.62:
                offsets.append(float(best_page - int(entry.listed_page)))

    if len(offsets) < 2:
        return 0.0, 0.0, "insufficient_matches"

    median_offset = statistics.median(offsets)
    mad = statistics.median([abs(value - median_offset) for value in offsets]) if offsets else 999.0
    confidence = min(1.0, (len(offsets) / 6.0)) * max(0.0, 1.0 - (mad / 5.0))
    method = "median_offset_code_anchor" if len(offsets) >= 2 else "insufficient_matches"
    return float(median_offset), float(confidence), method


# Build neighbor entries.
def neighbor_entries(entries: list[IndexEntry], target: IndexEntry) -> tuple[IndexEntry | None, IndexEntry | None]:
    if not entries:
        return None, None
    try:
        position = entries.index(target)
    except ValueError:
        return None, None
    prev_entry = entries[position - 1] if position > 0 else None
    next_entry = entries[position + 1] if position + 1 < len(entries) else None
    return prev_entry, next_entry


# Select search lines.
def select_search_lines(
    lines: list[LineRef],
    mapped_page_index: int | None,
    offset_confidence: float,
) -> tuple[list[LineRef], str]:
    if mapped_page_index is None:
        return lines, "global_fallback"
    if offset_confidence >= 0.72:
        radius = 3
        mode = "index_page_narrow_window"
    elif offset_confidence >= 0.45:
        radius = 8
        mode = "index_page_wide_window"
    else:
        radius = 12
        mode = "index_page_low_confidence_window"
    local = [line for line in lines if mapped_page_index - radius <= line.page_index <= mapped_page_index + radius]
    if not local:
        return lines, "global_fallback"
    return local, mode

# Build proceedings signals.
def proceedings_signals(record: dict[str, Any], lines: list[LineRef]) -> dict[str, Any]:
    first_window = [line for line in lines if line.page_index < 30]
    pattern = infer_proceedings_pattern(first_window or lines)
    first_pages_text = " ".join(line.text for line in lines if line.page_index < 5)
    normalized_first_pages = normalize_text(first_pages_text)
    header_starts = header_start_indices(first_window, pattern) if first_window else []
    title_like_count = sum(1 for line in first_window if is_potential_title_line(line.text))
    author_like_count = sum(1 for line in first_window if is_author_like(line.text))
    article_section_count = sum(1 for line in first_window if is_article_numbered_section(line.text))
    article_metadata_count = sum(1 for line in first_window if is_article_metadata_line(line.text))
    section_heading_count = sum(1 for line in first_window if is_section_heading(line.text))
    isolated_page_marker_count = sum(
        1 for marker in ISOLATED_ABSTRACT_PAGE_MARKERS if marker in normalized_first_pages
    )
    marker_text = " ".join(
        [
            str(record.get("source_filename") or ""),
            normalized_first_pages,
        ]
    )
    program_marker_count = sum(1 for marker in PROGRAM_MARKERS if marker in normalize_text(marker_text))
    n_pages = int(record.get("n_pages") or 0)
    signal_score = 0
    if n_pages >= 25:
        signal_score += 1
    if len(header_starts) >= 8:
        signal_score += 2
    elif len(header_starts) >= 4:
        signal_score += 1
    if title_like_count >= 20 and author_like_count >= 8:
        signal_score += 2
    elif title_like_count >= 12 and author_like_count >= 5:
        signal_score += 1
    if n_pages <= 3 and len(header_starts) >= 2 and author_like_count >= 4:
        signal_score += 3
    elif n_pages <= 2 and len(header_starts) >= 1 and author_like_count >= 4 and section_heading_count >= 2:
        signal_score += 3
    elif n_pages <= 2 and pattern.coded_header_count >= 2 and section_heading_count >= 2:
        signal_score += 3
    elif n_pages <= 2 and pattern.coded_header_count >= 1 and author_like_count >= 1 and section_heading_count >= 3:
        signal_score += 3
    if n_pages <= 2 and title_like_count >= 4 and author_like_count >= 1 and program_marker_count > 0:
        signal_score += 2
    if pattern.uncoded_header_count >= 4:
        signal_score += 1
    if program_marker_count > 0:
        signal_score += 2
    if article_section_count >= 2:
        signal_score -= 3
    if article_metadata_count >= 3:
        signal_score -= 3
    elif article_metadata_count >= 2:
        signal_score -= 2
    if n_pages <= 2 and program_marker_count == 0 and len(header_starts) <= 2:
        if isolated_page_marker_count >= 2:
            signal_score -= 4
        elif "first published" in normalized_first_pages:
            signal_score -= 3
    proceedings_detected = signal_score >= 3
    if program_marker_count == 0 and pattern.coded_header_count == 0 and (
        article_section_count >= 2 or article_metadata_count >= 3
    ):
        proceedings_detected = False
    if n_pages <= 2 and program_marker_count == 0 and len(header_starts) <= 2:
        if isolated_page_marker_count >= 2 or "first published" in normalized_first_pages:
            proceedings_detected = False
    return {
        "n_pages": n_pages,
        "abstract_block_count": len(header_starts),
        "title_like_line_count": title_like_count,
        "author_like_line_count": author_like_count,
        "program_marker_count": program_marker_count,
        "proceedings_signal_score": signal_score,
        "proceedings_detected": proceedings_detected,
    }


# Extract blocks.
def extract_blocks(lines: list[LineRef], pattern: ProceedingsPattern) -> list[AbstractBlock]:
    start_indices = header_start_indices(lines, pattern)
    blocks: list[AbstractBlock] = []
    for offset, start_index in enumerate(start_indices):
        end_index = start_indices[offset + 1] if offset + 1 < len(start_indices) else len(lines)
        block_lines = lines[start_index:end_index]
        block_lines, _ = trim_leading_header_noise(block_lines)
        block_lines, _ = trim_trailing_header_noise(block_lines)
        if not block_lines:
            continue
        title_parts = [strip_abstract_code(block_lines[0].text)]
        consumed = 1
        for line_ref in block_lines[1:5]:
            if is_abstract_start(line_ref.text) or is_author_like(line_ref.text) or is_institution_like(line_ref.text):
                break
            if is_footer_like(line_ref.text):
                break
            title_parts.append(line_ref.text)
            consumed += 1
        title_text = " ".join(part.strip() for part in title_parts if part.strip())
        header_lines = [line.text for line in block_lines[: min(len(block_lines), consumed + 4)]]
        preview_lines = [line.text for line in block_lines[: min(len(block_lines), 12)] if not is_footer_like(line.text)]
        match = is_abstract_start(block_lines[0].text)
        code_value = match.group("code") if match and match.groupdict().get("code") else abstract_code(block_lines[0].text)
        blocks.append(
            AbstractBlock(
                code=code_value,
                start_index=block_lines[0].global_index,
                end_index=block_lines[-1].global_index + 1,
                start_page_index=block_lines[0].page_index,
                end_page_index=block_lines[-1].page_index,
                title_text=title_text,
                header_text=" ".join(header_lines),
                preview_text=" ".join(preview_lines),
                line_refs=block_lines,
                trim_method="fuzzy_title_author_block_match",
                trim_mode="fuzzy_title_author_block_match",
            )
        )
    return blocks


# Build best matching block.
def best_matching_block(
    blocks: list[AbstractBlock],
    reference_title: str,
    reference_authors: str,
) -> AbstractBlock | None:
    best: AbstractBlock | None = None
    for block in blocks:
        block.title_score = score_title(reference_title, block.title_text)
        block.author_score = score_authors(reference_authors, block.preview_text)
        block.match_score = (0.75 * block.title_score) + (0.25 * block.author_score)
        enough_body, section_hits, header_only = has_enough_body(block.line_refs)
        block_body_chars = body_char_count(block.line_refs)
        block.body_signal_count = section_hits
        block.header_only_flag = header_only
        if best is None or block.match_score > best.match_score:
            best = block
            continue
        if best is None:
            continue
        best_body_chars = body_char_count(best.line_refs)
        if (
            abs(block.match_score - best.match_score) <= 0.10
            and not header_only
            and enough_body
            and best.header_only_flag
        ):
            best = block
            continue
        if (
            block.title_score >= 0.88
            and best.title_score >= 0.88
            and not header_only
            and enough_body
            and block_body_chars >= 220
            and best.header_only_flag
        ):
            best = block
            continue
        if (
            block.title_score + 0.02 >= best.title_score
            and block_body_chars >= max(240, int(best_body_chars * 1.25))
            and not header_only
            and best.header_only_flag
        ):
            best = block
    return best


# Join window text.
def join_window_text(window_lines: list[LineRef]) -> str:
    return " ".join(line.text for line in window_lines if not is_footer_like(line.text)).strip()


# Build title cluster score.
def title_cluster_score(reference_title: str, lines: list[LineRef], start_index: int) -> tuple[float, str]:
    best_score = 0.0
    best_text = ""
    for length in range(1, 5):
        cluster_lines = lines[start_index : start_index + length]
        if not cluster_lines:
            break
        if any(is_author_like(line.text) or is_institution_like(line.text) or is_footer_like(line.text) for line in cluster_lines):
            if length > 1:
                break
        cluster_text = " ".join(strip_abstract_code(line.text) for line in cluster_lines).strip()
        if not cluster_text:
            continue
        score = score_title(reference_title, cluster_text)
        if score > best_score:
            best_score = score
            best_text = cluster_text
        if cluster_lines[-1].text.endswith(".") or cluster_lines[-1].text.endswith(":"):
            break
    return best_score, best_text


# Build local window candidate.
def local_window_candidate(
    lines: list[LineRef],
    record: dict[str, Any],
    reference_title: str,
    reference_authors: str,
    pattern: ProceedingsPattern,
    forced_page_index: int | None = None,
    preselected_lines: list[LineRef] | None = None,
    target_code: str = "",
    next_entry: IndexEntry | None = None,
    trim_mode: str = "page_local_sliding_window_match",
    index_detected: bool = False,
    index_confidence: float = 0.0,
    index_listed_page: str = "",
    index_prev_code: str = "",
    index_next_code: str = "",
    page_map_method: str = "",
    estimated_offset: float = 0.0,
    offset_confidence: float = 0.0,
    fallback_triggered: bool = False,
) -> AbstractBlock | None:
    if not lines:
        return None
    if preselected_lines is not None:
        local_lines = preselected_lines
    else:
        page_index = forced_page_index
        if page_index is None:
            page_index, _, _, _ = page_match_scores(record, reference_title, reference_authors)
        local_lines = [line for line in lines if page_index - 1 <= line.page_index <= page_index + 1]
    if not local_lines:
        return None

    best_match_score = 0.0
    best_window_end = 0
    best_anchor_index = 0
    best_title_text = ""
    best_author_score = 0.0
    best_title_score = 0.0

    for start_index in range(len(local_lines)):
        for window_size in (6, 8, 10, 12, 16, 20):
            end_index = min(len(local_lines), start_index + window_size)
            window_lines = local_lines[start_index:end_index]
            if len(window_lines) < 4:
                continue
            window_text = join_window_text(window_lines)
            if not window_text:
                continue
            window_title_score = score_title(reference_title, window_text)
            window_author_score = score_authors(reference_authors, window_text)

            anchor_index = start_index
            anchor_score = 0.0
            anchor_title_text = ""
            for local_index in range(start_index, min(end_index, start_index + 8)):
                cluster_score, cluster_text = title_cluster_score(reference_title, local_lines, local_index)
                if cluster_score > anchor_score:
                    anchor_score = cluster_score
                    anchor_index = local_index
                    anchor_title_text = cluster_text

            boundary_bonus = 1.0 if header_boundary(local_lines, start_index, pattern, allow_soft=True)[0] else 0.0
            code_bonus = 0.0
            if target_code and any(line_matches_code(line.text, target_code) for line in window_lines[:4]):
                code_bonus = 1.0
            combined = (
                (0.35 * window_title_score)
                + (0.25 * window_author_score)
                + (0.30 * anchor_score)
                + (0.05 * boundary_bonus)
                + (0.05 * code_bonus)
            )
            if combined > best_match_score:
                best_match_score = combined
                best_window_end = end_index
                best_anchor_index = anchor_index
                best_title_text = anchor_title_text or window_text
                best_author_score = window_author_score
                best_title_score = max(window_title_score, anchor_score)

    if best_match_score <= 0.0:
        return None

    start_index = best_anchor_index
    start_rule = "anchor_line"
    previous_header_index, previous_header_rule = find_previous_header_index(
        lines=local_lines,
        anchor_index=best_anchor_index,
        pattern=pattern,
        target_code=target_code,
        max_backtrack=12,
    )
    if previous_header_index is not None:
        start_index = previous_header_index
        start_rule = previous_header_rule
    else:
        for local_index in range(best_anchor_index, max(-1, best_anchor_index - 8), -1):
            cluster_score, _ = title_cluster_score(reference_title, local_lines, local_index)
            if cluster_score >= 0.70:
                start_index = local_index
                start_rule = "backtrack_title_cluster"

    end_index = min(len(local_lines), max(best_window_end, start_index + 8))
    end_rule = "window_extent_cap"
    next_header_index, next_header_rule = find_next_header_index(
        lines=local_lines,
        start_index=start_index,
        pattern=pattern,
        expected_code=target_code or abstract_code(local_lines[start_index].text),
        next_code=next_entry.code if next_entry else "",
        min_gap=4,
    )
    if next_header_index is not None:
        end_index = next_header_index
        end_rule = next_header_rule
    else:
        for local_index in range(start_index + 3, len(local_lines)):
            if local_lines[local_index].page_index > local_lines[start_index].page_index + 1:
                end_index = min(end_index, local_index)
                end_rule = "page_span_cap"
                break

    candidate_lines = local_lines[start_index:end_index]
    candidate_lines, spillover_flag, spillover_rule = truncate_at_next_header(
        candidate_lines,
        expected_code=abstract_code(candidate_lines[0].text) if candidate_lines else target_code,
        next_entry=next_entry,
        pattern=pattern,
    )
    if spillover_flag:
        end_rule = spillover_rule
    candidate_lines, leading_noise_trimmed = trim_leading_header_noise(candidate_lines)
    if leading_noise_trimmed:
        start_rule = "leading_header_noise_trimmed"
    candidate_lines, trailing_noise_trimmed = trim_trailing_header_noise(candidate_lines)
    if trailing_noise_trimmed:
        end_rule = "trailing_header_noise"
    if not candidate_lines:
        return None
    enough_body, section_hits, header_only_flag = has_enough_body(candidate_lines)
    # Keep candidate for downstream logic; guardrails are applied in process_record.
    _ = enough_body
    preview_lines = [line.text for line in candidate_lines[: min(len(candidate_lines), 14)] if not is_footer_like(line.text)]
    header_lines = [line.text for line in candidate_lines[: min(len(candidate_lines), 8)] if not is_footer_like(line.text)]
    start_line = candidate_lines[0].text
    return AbstractBlock(
        code=abstract_code(start_line),
        start_index=candidate_lines[0].global_index,
        end_index=candidate_lines[-1].global_index + 1,
        start_page_index=candidate_lines[0].page_index,
        end_page_index=candidate_lines[-1].page_index,
        title_text=best_title_text.strip() or strip_abstract_code(start_line),
        header_text=" ".join(header_lines),
        preview_text=" ".join(preview_lines),
        line_refs=candidate_lines,
        title_score=best_title_score,
        author_score=best_author_score,
        match_score=best_match_score,
        trim_method="page_local_sliding_window_match",
        trim_mode=trim_mode,
        start_rule=start_rule,
        end_rule=end_rule,
        body_signal_count=section_hits,
        spillover_flag=spillover_flag,
        header_only_flag=header_only_flag,
        index_detected=index_detected,
        index_confidence=index_confidence,
        index_listed_page=index_listed_page,
        index_prev_code=index_prev_code,
        index_next_code=index_next_code,
        page_map_method=page_map_method,
        estimated_offset=estimated_offset,
        offset_confidence=offset_confidence,
        fallback_triggered=fallback_triggered,
    )


# Build index assisted candidate.
def index_assisted_candidate(
    lines: list[LineRef],
    record: dict[str, Any],
    reference_title: str,
    reference_authors: str,
    pattern: ProceedingsPattern,
) -> tuple[AbstractBlock | None, dict[str, Any]]:
    entries, index_detected = parse_index_entries(record)
    diagnostics: dict[str, Any] = {
        "index_detected": index_detected,
        "index_confidence": 0.0,
        "index_listed_page": "",
        "index_prev_code": "",
        "index_next_code": "",
        "page_map_method": "",
        "estimated_offset": 0.0,
        "offset_confidence": 0.0,
        "fallback_triggered": False,
    }
    if not entries:
        diagnostics["fallback_triggered"] = True
        return None, diagnostics

    target_entry, confidence, _ = best_index_entry(entries, reference_title)
    diagnostics["index_confidence"] = round(confidence, 4)
    if target_entry is None or confidence < 0.55:
        diagnostics["fallback_triggered"] = True
        return None, diagnostics

    prev_entry, next_entry = neighbor_entries(entries, target_entry)
    diagnostics["index_listed_page"] = (
        str(target_entry.listed_page) if target_entry.listed_page is not None else ""
    )
    diagnostics["index_prev_code"] = prev_entry.code if prev_entry else ""
    diagnostics["index_next_code"] = next_entry.code if next_entry else ""

    estimated_offset, offset_confidence, page_map_method = estimate_page_offset(record, entries)
    diagnostics["page_map_method"] = page_map_method
    diagnostics["estimated_offset"] = round(estimated_offset, 3)
    diagnostics["offset_confidence"] = round(offset_confidence, 4)

    mapped_page_index: int | None = None
    if target_entry.listed_page is not None:
        if offset_confidence >= 0.40:
            mapped_page_index = max(0, int(round(float(target_entry.listed_page) + estimated_offset)))
        else:
            mapped_page_index = max(0, int(target_entry.listed_page))
    if mapped_page_index is None:
        diagnostics["fallback_triggered"] = True
        return None, diagnostics

    selected_lines, mode = select_search_lines(lines, mapped_page_index, offset_confidence)
    if len(selected_lines) > 3200:
        diagnostics["fallback_triggered"] = True
        return None, diagnostics
    candidate = local_window_candidate(
        lines=lines,
        record=record,
        reference_title=reference_title,
        reference_authors=reference_authors,
        pattern=pattern,
        forced_page_index=mapped_page_index,
        preselected_lines=selected_lines,
        target_code=target_entry.code,
        next_entry=next_entry,
        trim_mode=f"index_assisted::{mode}",
        index_detected=index_detected,
        index_confidence=confidence,
        index_listed_page=diagnostics["index_listed_page"],
        index_prev_code=diagnostics["index_prev_code"],
        index_next_code=diagnostics["index_next_code"],
        page_map_method=page_map_method,
        estimated_offset=estimated_offset,
        offset_confidence=offset_confidence,
        fallback_triggered=False,
    )
    if candidate is None:
        diagnostics["fallback_triggered"] = True
        return None, diagnostics
    candidate.candidate_rank = 1
    return candidate, diagnostics


# Build candidate quality status.
def candidate_quality_status(
    block: AbstractBlock,
    reference_authors: str,
) -> tuple[str, str]:
    # Re-score authors on a larger slice; header-only captures can otherwise look stronger than they are.
    line_text = " ".join(line.text for line in block.line_refs[: min(len(block.line_refs), 24)])
    stronger_author_score = score_authors(reference_authors, line_text)
    block.author_score = max(block.author_score, stronger_author_score)

    enough_body, section_hits, header_only = has_enough_body(block.line_refs)
    block.body_signal_count = section_hits
    block.header_only_flag = header_only

    if block.spillover_flag:
        return "manual_review_required", "Candidate contains lines from a subsequent abstract boundary."

    identity_ok = block.title_score >= 0.62 or (
        block.title_score >= 0.55 and block.author_score >= 0.20 and block.match_score >= 0.58
    )
    if not identity_ok:
        return (
            "manual_review_required",
            "Proceedings detected, but the candidate did not match title/authors strongly enough.",
        )

    if header_only:
        return "header_only_source", "Matched entry appears to contain header-only listing without abstract body."

    if not enough_body:
        return "manual_review_required", "Matched entry appears truncated or lacks sufficient abstract body content."

    return "trimmed_auto", "Proceedings detected and candidate abstract passed identity and completeness guardrails."


# Build choose best candidate.
def choose_best_candidate(
    block_candidate: AbstractBlock | None,
    window_candidate: AbstractBlock | None,
) -> AbstractBlock | None:
    if block_candidate is None:
        return window_candidate
    if window_candidate is None:
        return block_candidate
    window_body_chars = body_char_count(window_candidate.line_refs)
    block_body_chars = body_char_count(block_candidate.line_refs)
    if (
        block_candidate.start_index == window_candidate.start_index
        and block_candidate.end_index > window_candidate.end_index
        and len(block_candidate.line_refs) > len(window_candidate.line_refs)
    ):
        if (
            window_candidate.end_rule in {"next_abstract_boundary", "next_index_code_boundary", "next_soft_header"}
            and window_candidate.title_score >= 0.90
            and window_candidate.author_score + 0.05 >= block_candidate.author_score
            and window_candidate.match_score + 0.12 >= block_candidate.match_score
        ):
            return window_candidate
        extra_tail = block_candidate.line_refs[len(window_candidate.line_refs) :]
        if extra_tail and all(
            is_header_preamble_line(line.text) or is_footer_like(line.text)
            for line in extra_tail
        ):
            return window_candidate
    if (
        window_candidate.header_only_flag
        and not block_candidate.header_only_flag
        and block_body_chars >= 220
        and block_candidate.title_score + 0.03 >= window_candidate.title_score
        and block_candidate.match_score + 0.10 >= window_candidate.match_score
    ):
        return block_candidate
    if (
        block_body_chars >= max(500, int(window_body_chars * 1.35))
        and block_candidate.match_score >= window_candidate.match_score - 0.06
        and block_candidate.title_score >= 0.55
    ):
        return block_candidate
    if window_candidate.trim_mode.startswith("index_assisted") and (
        window_candidate.match_score + 0.02 >= block_candidate.match_score
    ):
        return window_candidate
    if window_candidate.match_score > block_candidate.match_score + 0.05:
        return window_candidate
    if (
        window_candidate.title_score >= block_candidate.title_score
        and window_candidate.author_score >= block_candidate.author_score
        and window_candidate.match_score >= block_candidate.match_score
    ):
        return window_candidate
    return block_candidate


# Trim pages from block.
def trim_pages_from_block(block: AbstractBlock) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = {}
    for line_ref in block.line_refs:
        if is_footer_like(line_ref.text):
            continue
        grouped.setdefault(line_ref.page_index, []).append(line_ref.text)
    return [
        {"page_index": page_index, "text": "\n".join(lines).strip()}
        for page_index, lines in sorted(grouped.items())
        if "\n".join(lines).strip()
    ]


# Build trimmed record.
def build_trimmed_record(
    source_record: dict[str, Any],
    source_path: Path,
    block: AbstractBlock,
    reference_row: dict[str, str],
) -> dict[str, Any]:
    pages = trim_pages_from_block(block)
    kept_line_refs = [line_ref for line_ref in block.line_refs if not is_footer_like(line_ref.text)]
    if kept_line_refs:
        start_page_index = kept_line_refs[0].page_index
        end_page_index = kept_line_refs[-1].page_index
        start_line_global_index = kept_line_refs[0].global_index
        end_line_global_index_exclusive = kept_line_refs[-1].global_index + 1
    else:
        start_page_index = block.start_page_index
        end_page_index = block.end_page_index
        start_line_global_index = block.start_index
        end_line_global_index_exclusive = block.end_index
    return {
        "paper_id": str(source_record.get("paper_id") or source_path.stem),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_sha256": str(source_record.get("source_sha256") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "trim_status": "trimmed_auto",
        "trim_method": block.trim_method or "fuzzy_title_author_block_match",
        "trim_mode": block.trim_mode or block.trim_method or "fuzzy_title_author_block_match",
        "proceedings_detected": True,
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "matched_block_code": block.code,
        "matched_block_title": block.title_text,
        "match_score": round(block.match_score, 4),
        "title_score": round(block.title_score, 4),
        "author_score": round(block.author_score, 4),
        "start_page_index": start_page_index,
        "end_page_index": end_page_index,
        "start_line_global_index": start_line_global_index,
        "end_line_global_index_exclusive": end_line_global_index_exclusive,
        "start_rule": block.start_rule,
        "end_rule": block.end_rule,
        "body_signal_count": block.body_signal_count,
        "spillover_flag": block.spillover_flag,
        "header_only_flag": block.header_only_flag,
        "index_detected": block.index_detected,
        "index_confidence": round(block.index_confidence, 4),
        "index_listed_page": block.index_listed_page,
        "index_prev_code": block.index_prev_code,
        "index_next_code": block.index_next_code,
        "page_map_method": block.page_map_method,
        "estimated_offset": round(block.estimated_offset, 3),
        "offset_confidence": round(block.offset_confidence, 4),
        "candidate_rank": block.candidate_rank,
        "fallback_triggered": block.fallback_triggered,
        "original_n_pages": int(source_record.get("n_pages") or 0),
        "n_pages": len(pages),
        "page_char_counts": [len(page["text"]) for page in pages],
        "trimmed_at_utc": now_utc_iso(),
        "pages": pages,
    }


# Build decision row.
def decision_row(
    paper_id: str,
    reference_row: dict[str, str],
    source_record: dict[str, Any],
    source_path: Path,
    trimmed_path: Path | None,
    signals: dict[str, Any],
    trim_status: str,
    trim_reason: str,
    block: AbstractBlock | None,
    diagnostics: dict[str, Any] | None,
) -> dict[str, str]:
    diagnostics = diagnostics or {}
    index_detected = bool(diagnostics.get("index_detected")) if block is None else bool(block.index_detected)
    index_confidence = (
        float(diagnostics.get("index_confidence") or 0.0) if block is None else float(block.index_confidence)
    )
    index_listed_page = str(diagnostics.get("index_listed_page") or "") if block is None else block.index_listed_page
    index_prev_code = str(diagnostics.get("index_prev_code") or "") if block is None else block.index_prev_code
    index_next_code = str(diagnostics.get("index_next_code") or "") if block is None else block.index_next_code
    page_map_method = str(diagnostics.get("page_map_method") or "") if block is None else block.page_map_method
    estimated_offset = (
        float(diagnostics.get("estimated_offset") or 0.0) if block is None else float(block.estimated_offset)
    )
    offset_confidence = (
        float(diagnostics.get("offset_confidence") or 0.0) if block is None else float(block.offset_confidence)
    )
    fallback_triggered = bool(diagnostics.get("fallback_triggered")) if block is None else bool(block.fallback_triggered)
    return {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "trimmed_text_json_path": relative_to_repo(trimmed_path) if trimmed_path else "",
        "n_pages": str(signals["n_pages"]),
        "abstract_block_count": str(signals["abstract_block_count"]),
        "title_like_line_count": str(signals["title_like_line_count"]),
        "author_like_line_count": str(signals["author_like_line_count"]),
        "program_marker_count": str(signals["program_marker_count"]),
        "proceedings_signal_score": str(signals.get("proceedings_signal_score", "")),
        "proceedings_detected": bool_text(bool(signals["proceedings_detected"])),
        "index_detected": bool_text(index_detected),
        "index_confidence": f"{index_confidence:.4f}" if index_confidence else "",
        "index_listed_page": index_listed_page,
        "index_prev_code": index_prev_code,
        "index_next_code": index_next_code,
        "page_map_method": page_map_method,
        "estimated_offset": f"{estimated_offset:.3f}" if estimated_offset else "",
        "offset_confidence": f"{offset_confidence:.4f}" if offset_confidence else "",
        "fallback_triggered": bool_text(fallback_triggered),
        "trim_status": trim_status,
        "trim_reason": trim_reason,
        "trim_method": block.trim_method if trim_status in {"trimmed_auto", "header_only_source"} and block else "",
        "trim_mode": block.trim_mode if block else "",
        "matched_block_code": block.code if block else "",
        "matched_block_title": block.title_text if block else "",
        "title_score": f"{block.title_score:.4f}" if block else "",
        "author_score": f"{block.author_score:.4f}" if block else "",
        "match_score": f"{block.match_score:.4f}" if block else "",
        "start_rule": block.start_rule if block else "",
        "end_rule": block.end_rule if block else "",
        "body_signal_count": str(block.body_signal_count) if block else "",
        "spillover_flag": bool_text(block.spillover_flag) if block else "",
        "header_only_flag": bool_text(block.header_only_flag) if block else "",
        "candidate_rank": str(block.candidate_rank) if block else "",
        "start_page_index": str(block.start_page_index) if block else "",
        "end_page_index": str(block.end_page_index) if block else "",
        "start_line_global_index": str(block.start_index) if block else "",
        "end_line_global_index_exclusive": str(block.end_index) if block else "",
        "trimmed_at_utc": now_utc_iso() if trim_status in {"trimmed_auto", "header_only_source"} else "",
    }


# Define registry fieldnames.
def registry_fieldnames() -> list[str]:
    return [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_filename",
        "source_text_json_path",
        "trimmed_text_json_path",
        "n_pages",
        "abstract_block_count",
        "title_like_line_count",
        "author_like_line_count",
        "program_marker_count",
        "proceedings_signal_score",
        "proceedings_detected",
        "index_detected",
        "index_confidence",
        "index_listed_page",
        "index_prev_code",
        "index_next_code",
        "page_map_method",
        "estimated_offset",
        "offset_confidence",
        "fallback_triggered",
        "trim_status",
        "trim_reason",
        "trim_method",
        "trim_mode",
        "matched_block_code",
        "matched_block_title",
        "title_score",
        "author_score",
        "match_score",
        "start_rule",
        "end_rule",
        "body_signal_count",
        "spillover_flag",
        "header_only_flag",
        "candidate_rank",
        "start_page_index",
        "end_page_index",
        "start_line_global_index",
        "end_line_global_index_exclusive",
        "trimmed_at_utc",
    ]


# Sort registry rows by paper_id for stable output.
def sort_registry_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def sort_key(row: dict[str, str]) -> tuple[int, int | str]:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id.isdigit():
            return (0, int(paper_id))
        return (1, paper_id)

    return sorted(rows, key=sort_key)


# Merge updated rows into an existing registry snapshot.
def merge_registry_rows(
    existing_rows: list[dict[str, str]],
    updated_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    merged = {str(row.get("paper_id") or "").strip(): row for row in existing_rows if str(row.get("paper_id") or "").strip()}
    for row in updated_rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            merged[paper_id] = row
    return sort_registry_rows(list(merged.values()))


# Write registry.
def write_registry(rows: list[dict[str, str]], path: Path, preserve_existing: bool = False) -> None:
    fieldnames = registry_fieldnames()
    rows_to_write = sort_registry_rows(rows)
    if preserve_existing and path.exists():
        existing_rows = list(load_csv_rows_by_id(path, "paper_id").values())
        rows_to_write = merge_registry_rows(existing_rows, rows_to_write)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)


# Build refresh artifact registry.
def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


# Build process record.
def process_record(
    path: Path,
    reference_rows: dict[str, dict[str, str]],
    output_dir: Path,
) -> dict[str, str]:
    record = load_text_record(path)
    paper_id = str(record.get("paper_id") or path.stem)
    reference_row = reference_rows.get(paper_id, {})
    lines = flatten_lines(record)
    pattern = infer_proceedings_pattern(lines)
    signals = proceedings_signals(record, lines)
    trimmed_path = output_dir / f"{paper_id}.json"
    reference_title = (reference_row.get("Title") or "").strip()
    reference_authors = (reference_row.get("Authors") or "").strip()

    if not signals["proceedings_detected"]:
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status="not_needed",
            trim_reason="Document does not look like a large proceedings/program PDF.",
            block=None,
            diagnostics=None,
        )

    blocks = extract_blocks(lines, pattern)
    block_candidate = best_matching_block(
        blocks=blocks,
        reference_title=reference_title,
        reference_authors=reference_authors,
    )
    index_candidate, index_diagnostics = index_assisted_candidate(
        lines=lines,
        record=record,
        reference_title=reference_title,
        reference_authors=reference_authors,
        pattern=pattern,
    )
    fallback_window_candidate = local_window_candidate(
        lines=lines,
        record=record,
        reference_title=reference_title,
        reference_authors=reference_authors,
        pattern=pattern,
        trim_mode="page_local_sliding_window_match",
        fallback_triggered=index_candidate is None,
    )
    window_candidate = index_candidate if index_candidate is not None else fallback_window_candidate
    if window_candidate is not None and window_candidate.trim_mode.startswith("index_assisted"):
        window_candidate.fallback_triggered = False
    elif window_candidate is not None:
        window_candidate.fallback_triggered = True
    if block_candidate is not None and not block_candidate.trim_mode:
        block_candidate.trim_mode = "fuzzy_title_author_block_match"

    block = choose_best_candidate(block_candidate, window_candidate)
    if block is None and index_candidate is not None:
        # If index-assisted failed due candidate competition, keep fallback status explicit.
        index_diagnostics["fallback_triggered"] = True
    if block is not None and not block.index_detected:
        block.index_detected = bool(index_diagnostics.get("index_detected"))
    if block is not None and block.index_confidence == 0.0:
        block.index_confidence = float(index_diagnostics.get("index_confidence") or 0.0)
    if block is not None and not block.index_listed_page:
        block.index_listed_page = str(index_diagnostics.get("index_listed_page") or "")
    if block is not None and not block.index_prev_code:
        block.index_prev_code = str(index_diagnostics.get("index_prev_code") or "")
    if block is not None and not block.index_next_code:
        block.index_next_code = str(index_diagnostics.get("index_next_code") or "")
    if block is not None and not block.page_map_method:
        block.page_map_method = str(index_diagnostics.get("page_map_method") or "")
    if block is not None and block.estimated_offset == 0.0:
        block.estimated_offset = float(index_diagnostics.get("estimated_offset") or 0.0)
    if block is not None and block.offset_confidence == 0.0:
        block.offset_confidence = float(index_diagnostics.get("offset_confidence") or 0.0)
    if block is not None:
        block.fallback_triggered = bool(index_diagnostics.get("fallback_triggered")) and not (
            block.trim_mode.startswith("index_assisted")
        )

    if block is None:
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status="manual_review_required",
            trim_reason="No abstract block could be segmented from the proceedings text.",
            block=None,
            diagnostics=index_diagnostics,
        )

    trim_status, trim_reason = candidate_quality_status(block, reference_authors)
    if trim_status == "manual_review_required":
        if trimmed_path.exists():
            trimmed_path.unlink()
        return decision_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trimmed_path=None,
            signals=signals,
            trim_status=trim_status,
            trim_reason=trim_reason,
            block=block,
            diagnostics=index_diagnostics,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    trimmed_record = build_trimmed_record(record, path, block, reference_row)
    trimmed_record["trim_status"] = trim_status
    trimmed_record["trim_reason"] = trim_reason
    trimmed_path.write_text(
        json.dumps(trimmed_record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return decision_row(
        paper_id=paper_id,
        reference_row=reference_row,
        source_record=record,
        source_path=path,
        trimmed_path=trimmed_path,
        signals=signals,
        trim_status=trim_status,
        trim_reason=trim_reason,
        block=block,
        diagnostics=index_diagnostics,
    )


# Run the pipeline entrypoint.
def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    input_paths = collect_input_paths(args.input_dir, args.paper_id, args.limit)
    input_paths = filter_to_proceedings_candidates(
        paths=input_paths,
        source_categorisation_path=args.source_categorisation_path,
        source_manual_review_path=args.source_manual_review_path,
        existing_trim_registry_path=args.registry_path,
        force_all_papers=args.all_papers,
        explicit_paper_ids=args.paper_id,
        include_already_trimmed=args.include_already_trimmed,
    )
    print(f"Proceedings trim candidate count: {len(input_paths)}")
    rows: list[dict[str, str]] = []
    for path in tqdm(input_paths, desc="Proceedings trim"):
        rows.append(process_record(path, reference_rows, args.output_dir))
    write_registry(rows, args.registry_path, preserve_existing=bool(args.paper_id or args.limit))
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.registry_path}")


if __name__ == "__main__":
    main()
