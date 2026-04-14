from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from src.pipelines._proceedings_text import (
        LineRef,
        abstract_code,
        flatten_lines,
        is_footer_like,
        is_header_preamble_line,
        is_potential_title_line,
        normalize_code,
        normalize_text,
        strip_abstract_code,
    )
    from src.pipelines._proceedings_trim_llm import (
        _tail_metadata_trim_end,
        is_tail_metadata_like_line,
        line_refs_for_span,
    )
except ImportError:
    from _proceedings_text import (
        LineRef,
        abstract_code,
        flatten_lines,
        is_footer_like,
        is_header_preamble_line,
        is_potential_title_line,
        normalize_code,
        normalize_text,
        strip_abstract_code,
    )
    from _proceedings_trim_llm import _tail_metadata_trim_end, is_tail_metadata_like_line, line_refs_for_span


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIMMED_LLM_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed_llm"
TEXT_PROCEEDINGS_READY_DIR = REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready"
TEXT_TRIM_LLM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_llm_registry.csv"
TEXT_TRIM_LLM_CANDIDATE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_llm_candidate_registry.csv"
TEXT_PROCEEDINGS_READY_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_proceedings_ready_registry.csv"

ARTICLE_FRONTMATTER_MARKERS = (
    "this information is current as of",
    "located on the world wide web",
    "official journal",
    "correspondence to",
    "abstract",
    "glossary",
)
SESSION_TITLE_PREFIX_RE = re.compile(
    r"^\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:\s+\d{4})?\s*[-–—]\s*\d{1,5}[A-Z]?\s*[\.\|\:\-\)]\s*",
    re.IGNORECASE,
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = str(row.get(key_column) or "").strip()
            if key:
                rows[key] = row
    return rows


def load_ready_rows_by_id(path: Path = TEXT_PROCEEDINGS_READY_REGISTRY_PATH) -> dict[str, dict[str, str]]:
    return load_csv_rows_by_id(path, "paper_id")


def preferred_proceedings_text_path(
    source_path: Path,
    *,
    ready_dir: Path = TEXT_PROCEEDINGS_READY_DIR,
    fallback_trimmed_dir: Path = TEXT_TRIMMED_DIR,
) -> Path:
    ready_path = ready_dir / source_path.name
    if ready_path.exists():
        return ready_path
    trimmed_path = fallback_trimmed_dir / source_path.name
    if trimmed_path.exists():
        return trimmed_path
    return source_path


def preferred_proceedings_text_source(
    paper_id: str,
    *,
    ready_rows: dict[str, dict[str, str]] | None = None,
    ready_registry_path: Path = TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
) -> str:
    rows = ready_rows if ready_rows is not None else load_ready_rows_by_id(ready_registry_path)
    row = rows.get(paper_id, {})
    if row:
        mode = str(row.get("ready_text_mode") or "").strip()
        if mode == "full_text_passthrough":
            return "full_text"
        return "proceedings_ready"
    return "full_text"


def looks_like_full_article_frontmatter(record: dict[str, Any]) -> bool:
    lines = flatten_lines(record)[:48]
    normalized_lines = [normalize_text(line.text) for line in lines if normalize_text(line.text)]
    if not normalized_lines:
        return False
    marker_hits = sum(
        1
        for marker in ARTICLE_FRONTMATTER_MARKERS
        if any(marker in line for line in normalized_lines)
    )
    has_url = any("http" in line or "www" in line for line in normalized_lines)
    early_codes = sum(1 for line in lines[:10] if abstract_code(line.text))
    return marker_hits >= 3 and has_url and early_codes <= 1


def _title_match_start_index(
    window_lines: list[LineRef],
    matched_title: str,
) -> int | None:
    def normalise_title_fragment(text: str) -> str:
        stripped = strip_abstract_code(text).strip()
        stripped = SESSION_TITLE_PREFIX_RE.sub("", stripped)
        return normalize_text(stripped)

    normalized_title = normalise_title_fragment(matched_title)
    if not normalized_title:
        return None

    for offset, line_ref in enumerate(window_lines):
        line_title = normalise_title_fragment(line_ref.text)
        if not line_title:
            continue
        if (
            normalized_title == line_title
            or normalized_title.startswith(line_title)
            or line_title.startswith(normalized_title)
        ):
            if offset > 0:
                previous = window_lines[offset - 1]
                previous_code = normalize_code(abstract_code(previous.text))
                if previous_code or previous.text.strip().isdigit():
                    return previous.global_index
            return line_ref.global_index

        cluster_parts = [line_title]
        for cluster_offset in range(offset, min(len(window_lines), offset + 4)):
            if cluster_offset == offset:
                continue
            cluster_line = window_lines[cluster_offset]
            if not is_potential_title_line(cluster_line.text):
                break
            cluster_title = normalise_title_fragment(cluster_line.text)
            if not cluster_title:
                break
            cluster_parts.append(cluster_title)
            combined_title = " ".join(cluster_parts)
            if (
                normalized_title == combined_title
                or normalized_title.startswith(combined_title)
                or combined_title.startswith(normalized_title)
            ):
                if offset > 0:
                    previous = window_lines[offset - 1]
                    previous_code = normalize_code(abstract_code(previous.text))
                    if previous_code or previous.text.strip().isdigit():
                        return previous.global_index
                return line_ref.global_index
    return None


def refine_ready_start_index(
    lines: list[LineRef],
    *,
    start_index: int,
    end_index_exclusive: int,
    matched_code: str,
    matched_title: str,
    scan_limit: int = 24,
) -> int:
    window_end = min(end_index_exclusive, start_index + scan_limit)
    window_lines = line_refs_for_span(lines, start_index, window_end)
    if not window_lines:
        return start_index

    title_start = _title_match_start_index(window_lines, matched_title)
    if title_start is not None:
        return title_start

    target_code = normalize_code(matched_code)
    if target_code:
        for line_ref in window_lines:
            if normalize_code(abstract_code(line_ref.text)) == target_code:
                return line_ref.global_index

    for line_ref in window_lines:
        stripped = line_ref.text.strip()
        if (
            not stripped
            or is_footer_like(stripped)
            or is_header_preamble_line(stripped)
            or is_tail_metadata_like_line(stripped)
        ):
            continue
        if is_potential_title_line(stripped):
            return line_ref.global_index
    return start_index


def refine_ready_end_index(
    lines: list[LineRef],
    *,
    start_index: int,
    end_index_exclusive: int,
) -> int:
    trimmed_end = _tail_metadata_trim_end(lines, start_index, end_index_exclusive)
    return max(start_index + 1, trimmed_end)


def build_span_record(
    *,
    source_record: dict[str, Any],
    source_path: Path,
    start_index: int,
    end_index_exclusive: int,
    base_payload: dict[str, Any] | None = None,
    ready_source_kind: str,
    ready_text_mode: str,
    ready_source_detail: str,
    ready_reason: str,
) -> dict[str, Any]:
    source_lines = flatten_lines(source_record)
    span_lines = line_refs_for_span(source_lines, start_index, end_index_exclusive)
    if not span_lines:
        raise ValueError(f"Empty proceedings-ready span for {source_path}")

    pages: list[dict[str, Any]] = []
    current_page_index: int | None = None
    current_page_lines: list[str] = []
    for line_ref in span_lines:
        if current_page_index is None or line_ref.page_index != current_page_index:
            if current_page_index is not None:
                pages.append(
                    {
                        "page_index": current_page_index,
                        "text": "\n".join(current_page_lines).strip(),
                    }
                )
            current_page_index = line_ref.page_index
            current_page_lines = [line_ref.text]
        else:
            current_page_lines.append(line_ref.text)
    if current_page_index is not None:
        pages.append(
            {
                "page_index": current_page_index,
                "text": "\n".join(current_page_lines).strip(),
            }
        )

    payload = dict(base_payload or {})
    payload.update(
        {
            "paper_id": str(source_record.get("paper_id") or source_path.stem),
            "source_filename": str(source_record.get("source_filename") or ""),
            "source_sha256": str(source_record.get("source_sha256") or ""),
            "source_text_json_path": relative_to_repo(source_path),
            "n_pages": len(pages),
            "page_char_counts": [len(str(page.get("text") or "")) for page in pages],
            "pages": pages,
            "proceedings_ready_source_kind": ready_source_kind,
            "proceedings_ready_text_mode": ready_text_mode,
            "proceedings_ready_source_detail": ready_source_detail,
            "proceedings_ready_reason": ready_reason,
            "proceedings_ready_start_line_global_index": start_index,
            "proceedings_ready_end_line_global_index_exclusive": end_index_exclusive,
            "proceedings_ready_built_at_utc": now_utc_iso(),
        }
    )
    return payload
