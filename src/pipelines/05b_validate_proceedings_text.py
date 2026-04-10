from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _proceedings_text import (
    flatten_lines,
    find_next_header_index,
    has_enough_body,
    header_boundary,
    infer_proceedings_pattern,
    is_abstract_code_only,
    is_header_preamble_line,
    is_footer_like,
    normalize_text,
    score_authors,
    score_title,
)
from _source_routing import load_csv_rows_by_id, resolve_source_row


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "proceedings_text_qc_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
TAIL_NOISE_PREFIXES = ("corresponding author", "keywords", "disclosure")
TAIL_NOISE_BLOCK_PREFIXES = TAIL_NOISE_PREFIXES + ("full disclosures", "disclosure of interest")


# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate proceedings-derived extracted text against reference title and authors."
    )
    parser.add_argument(
        "--references-csv",
        type=Path,
        default=REFERENCES_CSV,
        help="Reference export CSV containing titles and authors.",
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing full extracted text JSON files.",
    )
    parser.add_argument(
        "--trimmed-dir",
        type=Path,
        default=TEXT_TRIMMED_DIR,
        help="Directory containing proceedings-trimmed text JSON files.",
    )
    parser.add_argument(
        "--text-trim-registry",
        type=Path,
        default=TEXT_TRIM_REGISTRY_PATH,
        help="Registry from the proceedings trimmer.",
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
        "--output-path",
        type=Path,
        default=OUTPUT_PATH,
        help="QC registry output path.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to validate. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of proceedings papers to inspect.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing QC output.",
    )
    return parser.parse_args()


# Build now utc iso.
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Build bool text.
def bool_text(value: bool) -> str:
    return "true" if value else "false"


# Convert a path to a repository-relative string.
def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


# Build body metrics.
def body_metrics(record: dict[str, Any]) -> tuple[int, int, bool]:
    lines = [line for line in flatten_lines(record) if not is_footer_like(line.text)]
    if not lines:
        return 0, 0, True
    _, section_hits, header_only = has_enough_body(lines)
    body_chars = sum(len(line.text) for line in lines[min(6, len(lines)) :])
    return section_hits, body_chars, header_only


# Load reference rows.
def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


# Load text record.
def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# Collect candidate IDs.
def collect_candidate_ids(
    text_dir: Path,
    trim_registry_rows: dict[str, dict[str, str]],
    heuristic_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    paper_ids: list[str],
    limit: int,
) -> list[str]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    candidates: list[str] = []
    for path in sorted(text_dir.glob("*.json")):
        paper_id = path.stem
        if wanted and paper_id not in wanted:
            continue
        trim_row = trim_registry_rows.get(paper_id, {})
        resolved = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        resolved_category = (resolved.get("resolved_source_category") or "").strip()
        manual_override_present = (resolved.get("manual_override_present") or "").strip().lower() == "true"
        if manual_override_present and resolved_category != "conference_abstract":
            continue
        is_proceedings = (
            resolved_category == "conference_abstract"
            or (
                not manual_override_present
                and (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
            )
        )
        if is_proceedings:
            candidates.append(paper_id)
    if limit and limit > 0:
        return candidates[:limit]
    return candidates


# Build page matches.
def page_matches(record: dict[str, Any], reference_title: str, reference_authors: str) -> tuple[int, float, float, float, str]:
    best_page_index = -1
    best_title_score = 0.0
    best_author_score = 0.0
    best_combined = 0.0
    best_excerpt = ""
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "").strip()
        if not page_text:
            continue
        page_lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        header_slice = " ".join(page_lines[:8])
        title_score = max(score_title(reference_title, page_text), score_title(reference_title, header_slice))
        author_score = max(score_authors(reference_authors, page_text), score_authors(reference_authors, header_slice))
        combined = (0.75 * title_score) + (0.25 * author_score)
        if combined > best_combined:
            best_page_index = page_index
            best_title_score = title_score
            best_author_score = author_score
            best_combined = combined
            best_excerpt = " ".join(page_text.split())[:500]
    return best_page_index, best_title_score, best_author_score, best_combined, best_excerpt


def is_tail_noise(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return True
    if is_footer_like(line):
        return True
    if "nothing to disclose" in normalized:
        return True
    return any(normalized.startswith(prefix) for prefix in TAIL_NOISE_PREFIXES)


def meaningful_tail_gap_count(trailing_lines: list[Any]) -> int:
    count = 0
    tail_noise_block_open = False
    for line in trailing_lines:
        normalized = normalize_text(line.text)
        if not normalized:
            continue
        if tail_noise_block_open:
            continue
        if any(normalized.startswith(prefix) for prefix in TAIL_NOISE_BLOCK_PREFIXES):
            tail_noise_block_open = True
            continue
        if is_tail_noise(line.text):
            continue
        count += 1
    return count


def locate_trimmed_span(
    source_record: dict[str, Any],
    trimmed_record: dict[str, Any],
) -> tuple[int | None, int | None, str]:
    source_lines = flatten_lines(source_record)
    if not source_lines:
        return None, None, "source_empty"

    start_value = str(trimmed_record.get("start_line_global_index") or "").strip()
    end_value = str(trimmed_record.get("end_line_global_index_exclusive") or "").strip()
    if start_value.isdigit() and end_value.isdigit():
        start_index = int(start_value)
        end_index = int(end_value)
        if 0 <= start_index < end_index <= len(source_lines):
            return start_index, end_index, "trim_record_indices"

    source_filtered = [line for line in source_lines if not is_footer_like(line.text)]
    trimmed_filtered = [line for line in flatten_lines(trimmed_record) if not is_footer_like(line.text)]
    if not source_filtered or not trimmed_filtered:
        return None, None, "empty_after_footer_filter"

    source_texts = [line.text for line in source_filtered]
    trimmed_texts = [line.text for line in trimmed_filtered]
    max_start = len(source_texts) - len(trimmed_texts) + 1
    for start_offset in range(max(0, max_start)):
        if source_texts[start_offset] != trimmed_texts[0]:
            continue
        if source_texts[start_offset : start_offset + len(trimmed_texts)] != trimmed_texts:
            continue
        start_index = source_filtered[start_offset].global_index
        end_index = source_filtered[start_offset + len(trimmed_texts) - 1].global_index + 1
        return start_index, end_index, "exact_footer_filtered_subsequence"
    return None, None, "trim_span_not_found"


def validate_trimmed_segmentation(
    source_record: dict[str, Any],
    trimmed_record: dict[str, Any],
) -> dict[str, Any]:
    source_lines = flatten_lines(source_record)
    pattern = infer_proceedings_pattern(source_lines)
    start_global_index, end_global_index_exclusive, detection_method = locate_trimmed_span(source_record, trimmed_record)
    diagnostics: dict[str, Any] = {
        "span_located": False,
        "span_detection_method": detection_method,
        "start_boundary_ok": False,
        "leading_spillover": False,
        "spillover": False,
        "truncated_by_gap": False,
        "meaningful_tail_gap_count": 0,
        "start_boundary_rule": "",
        "next_header_rule": "",
    }
    if start_global_index is None or end_global_index_exclusive is None or not source_lines:
        return diagnostics

    diagnostics["span_located"] = True
    global_to_position = {line.global_index: idx for idx, line in enumerate(source_lines)}
    start_position = global_to_position.get(start_global_index)
    end_position_exclusive = global_to_position.get(end_global_index_exclusive - 1)
    if start_position is None or end_position_exclusive is None:
        diagnostics["span_located"] = False
        return diagnostics
    end_position_exclusive += 1

    start_boundary_ok, _, start_rule, _ = header_boundary(source_lines, start_position, pattern, allow_soft=True)
    if not start_boundary_ok and start_position > 0:
        current_line = source_lines[start_position]
        for previous_position in range(max(0, start_position - 3), start_position):
            previous_line = source_lines[previous_position]
            intervening_lines = source_lines[previous_position + 1 : start_position]
            if previous_line.page_index != current_line.page_index:
                continue
            if is_abstract_code_only(previous_line.text) is None:
                continue
            if not intervening_lines:
                start_boundary_ok = True
                start_rule = "after_coded_boundary"
                break
            if all(
                line.page_index == current_line.page_index and is_header_preamble_line(line.text)
                for line in intervening_lines
            ):
                start_boundary_ok = True
                start_rule = "after_coded_boundary_preamble"
                break
    diagnostics["start_boundary_ok"] = start_boundary_ok
    diagnostics["start_boundary_rule"] = start_rule
    if not start_boundary_ok:
        lookahead_limit = min(len(source_lines), start_position + 8)
        for offset in range(start_position + 1, lookahead_limit):
            matched, _, _, _ = header_boundary(source_lines, offset, pattern, allow_soft=True)
            if matched:
                diagnostics["leading_spillover"] = True
                break

    next_header_position, next_header_rule = find_next_header_index(
        lines=source_lines,
        start_index=start_position,
        pattern=pattern,
        expected_code=str(trimmed_record.get("matched_block_code") or ""),
        next_code="",
        min_gap=4,
    )
    diagnostics["next_header_rule"] = next_header_rule
    if next_header_position is None:
        return diagnostics

    diagnostics["spillover"] = end_position_exclusive > next_header_position
    if diagnostics["spillover"]:
        return diagnostics

    trailing_lines = source_lines[end_position_exclusive:next_header_position]
    gap_count = meaningful_tail_gap_count(trailing_lines)
    diagnostics["meaningful_tail_gap_count"] = gap_count
    diagnostics["truncated_by_gap"] = gap_count >= 2
    return diagnostics


# Build derive qc status.
def derive_qc_status(
    trimmed_present: bool,
    title_score: float,
    author_score: float,
    combined_score: float,
    section_hits: int,
    body_chars: int,
    header_only: bool,
    segmentation: dict[str, Any] | None,
) -> tuple[str, bool, str]:
    identity_strong = title_score >= 0.72 and author_score >= 0.20
    identity_moderate = combined_score >= 0.62 or title_score >= 0.60
    identity_ok = identity_strong or identity_moderate

    if not identity_ok:
        return "mismatch", True, "Title/author alignment is too weak for a reliable proceedings match."
    if not trimmed_present:
        if header_only:
            return "header_only_source", True, "Matched source appears to be a title/author listing without abstract body text."
        return "untrimmed_localised", True, "Target appears localised in full proceedings text; trimming/manual review is still required."
    segmentation = segmentation or {}
    if not segmentation.get("span_located", False):
        return "mismatch", True, "Trimmed text could not be mapped back to the full proceedings source."
    if segmentation.get("leading_spillover", False):
        return "spillover_detected", True, "Trim starts before the detected proceedings header."
    if not segmentation.get("start_boundary_ok", False):
        return "partial_truncated", True, "Trim does not start at a detected proceedings header."
    if segmentation.get("spillover", False):
        return "spillover_detected", True, "Trim appears to include text from the subsequent proceedings entry."
    if header_only:
        return "header_only_source", True, "Matched source appears to be a title/author listing without abstract body text."
    if segmentation.get("truncated_by_gap", False):
        return "partial_truncated", True, "Trim stops before the next detected proceedings header."

    enough_body = body_chars >= 420 or (section_hits >= 3 and body_chars >= 160) or (section_hits >= 1 and body_chars >= 220)
    if enough_body:
        return "confirmed_full", False, "Trimmed proceedings text matches and appears complete."

    return "partial_truncated", True, "Matched text appears related but likely incomplete/truncated."


# Build qc row.
def qc_row(
    paper_id: str,
    reference_row: dict[str, str],
    resolved_source: dict[str, str],
    trim_row: dict[str, str],
    source_path: Path,
    trimmed_path: Path | None,
    best_page_index: int,
    title_score: float,
    author_score: float,
    combined_score: float,
    best_excerpt: str,
    section_hits: int,
    body_chars: int,
    header_only: bool,
    segmentation: dict[str, Any] | None,
) -> dict[str, str]:
    status, manual_follow_up, note = derive_qc_status(
        trimmed_present=trimmed_path is not None,
        title_score=title_score,
        author_score=author_score,
        combined_score=combined_score,
        section_hits=section_hits,
        body_chars=body_chars,
        header_only=header_only,
        segmentation=segmentation,
    )
    segmentation = segmentation or {}
    return {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "resolved_source_category": resolved_source.get("resolved_source_category") or "",
        "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
        "resolved_source_route_source": resolved_source.get("resolved_source_route_source") or "",
        "source_text_json_path": relative_to_repo(source_path),
        "trimmed_text_json_path": relative_to_repo(trimmed_path),
        "validated_text_json_path": relative_to_repo(trimmed_path or source_path),
        "preferred_text_source": "trimmed_text" if trimmed_path else "full_text",
        "proceedings_detected": trim_row.get("proceedings_detected") or "",
        "trim_status": trim_row.get("trim_status") or "",
        "trim_reason": trim_row.get("trim_reason") or "",
        "qc_status": status,
        "manual_follow_up_required": bool_text(manual_follow_up),
        "best_match_page_index": "" if best_page_index < 0 else str(best_page_index),
        "title_score": f"{title_score:.4f}",
        "author_score": f"{author_score:.4f}",
        "combined_score": f"{combined_score:.4f}",
        "section_heading_count": str(section_hits),
        "body_char_count": str(body_chars),
        "header_only_flag": bool_text(header_only),
        "spillover_flag": bool_text(bool(segmentation.get("spillover") or segmentation.get("leading_spillover"))),
        "span_located": bool_text(bool(segmentation.get("span_located"))),
        "span_detection_method": str(segmentation.get("span_detection_method") or ""),
        "start_boundary_ok": bool_text(bool(segmentation.get("start_boundary_ok"))),
        "start_boundary_rule": str(segmentation.get("start_boundary_rule") or ""),
        "next_header_rule": str(segmentation.get("next_header_rule") or ""),
        "meaningful_tail_gap_count": str(segmentation.get("meaningful_tail_gap_count") or 0),
        "best_match_excerpt": best_excerpt,
        "qc_note": note,
        "checked_at_utc": now_utc_iso(),
    }


# Write registry.
def write_registry(rows: list[dict[str, str]], path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "resolved_source_category",
        "resolved_source_subtype",
        "resolved_source_route_source",
        "source_text_json_path",
        "trimmed_text_json_path",
        "validated_text_json_path",
        "preferred_text_source",
        "proceedings_detected",
        "trim_status",
        "trim_reason",
        "qc_status",
        "manual_follow_up_required",
        "best_match_page_index",
        "title_score",
        "author_score",
        "combined_score",
        "section_heading_count",
        "body_char_count",
        "header_only_flag",
        "spillover_flag",
        "span_located",
        "span_detection_method",
        "start_boundary_ok",
        "start_boundary_rule",
        "next_header_rule",
        "meaningful_tail_gap_count",
        "best_match_excerpt",
        "qc_note",
        "checked_at_utc",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# Build refresh artifact registry.
def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


# Run the pipeline entrypoint.
def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    trim_registry_rows = load_csv_rows_by_id(args.text_trim_registry, "paper_id")
    heuristic_rows = load_csv_rows_by_id(args.source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(args.source_manual_review_path, "paper_id")
    rows: list[dict[str, str]] = []

    for paper_id in collect_candidate_ids(
        text_dir=args.text_dir,
        trim_registry_rows=trim_registry_rows,
        heuristic_rows=heuristic_rows,
        manual_rows=manual_rows,
        paper_ids=args.paper_id,
        limit=args.limit,
    ):
        source_path = args.text_dir / f"{paper_id}.json"
        trimmed_path = args.trimmed_dir / f"{paper_id}.json"
        preferred_path = trimmed_path if trimmed_path.exists() else source_path
        if not preferred_path.exists() or not source_path.exists():
            continue
        reference_row = reference_rows.get(paper_id, {})
        resolved_source = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        source_record = load_text_record(source_path)
        record = load_text_record(preferred_path)
        best_page_index, title_score, author_score, combined_score, best_excerpt = page_matches(
            record=record,
            reference_title=(reference_row.get("Title") or "").strip(),
            reference_authors=(reference_row.get("Authors") or "").strip(),
        )
        section_hits, body_chars, header_only = body_metrics(record)
        segmentation = (
            validate_trimmed_segmentation(source_record, record)
            if trimmed_path.exists()
            else None
        )
        rows.append(
            qc_row(
                paper_id=paper_id,
                reference_row=reference_row,
                resolved_source=resolved_source,
                trim_row=trim_registry_rows.get(paper_id, {}),
                source_path=source_path,
                trimmed_path=trimmed_path if trimmed_path.exists() else None,
                best_page_index=best_page_index,
                title_score=title_score,
                author_score=author_score,
                combined_score=combined_score,
                best_excerpt=best_excerpt,
                section_hits=section_hits,
                body_chars=body_chars,
                header_only=header_only,
                segmentation=segmentation,
            )
        )

    write_registry(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
