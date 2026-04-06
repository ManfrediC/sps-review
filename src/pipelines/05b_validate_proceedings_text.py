from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

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
SECTION_HEADING_MARKERS = (
    "background",
    "purpose",
    "objective",
    "objectives",
    "introduction",
    "case",
    "methods",
    "results",
    "discussion",
    "conclusion",
)
ABSTRACT_BOUNDARY_RE = re.compile(
    r"^(?P<code>(?:[A-Z]{1,3}-)?(?:[A-Z]{1,2})?\d{1,5})\s*(?:[\.\|\:\-\)]\s+|$)"
)


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


# Normalize text.
def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


# Build token set.
def token_set(text: str, min_len: int = 3) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= min_len}


# Score title.
def score_title(reference_title: str, candidate_text: str) -> float:
    ref_norm = normalize_text(reference_title)
    candidate_norm = normalize_text(candidate_text)
    if not ref_norm or not candidate_norm:
        return 0.0
    if ref_norm == candidate_norm:
        return 1.0
    sequence = SequenceMatcher(None, ref_norm, candidate_norm).ratio()
    ref_tokens = token_set(reference_title, min_len=4)
    candidate_tokens = token_set(candidate_text, min_len=4)
    overlap = len(ref_tokens & candidate_tokens) / max(1, len(ref_tokens))
    if ref_norm in candidate_norm or candidate_norm in ref_norm:
        overlap = max(overlap, 0.95)
    blended = (0.35 * sequence) + (0.65 * overlap)
    return max(min(sequence, overlap), blended)


# Parse reference surnames.
def parse_reference_surnames(authors: str) -> list[str]:
    surnames: list[str] = []
    for chunk in re.split(r";| and | & ", authors or "", flags=re.IGNORECASE):
        part = chunk.strip()
        if not part:
            continue
        part = re.sub(r"\b(MD|PhD|DO|MSc|MBBS|RN|FRCP|FAAN)\b\.?", "", part, flags=re.IGNORECASE).strip()
        if "," in part:
            surname = part.split(",", 1)[0].strip()
        else:
            tokens = [token for token in re.split(r"\s+", part) if token]
            if not tokens:
                continue
            surname = tokens[-1]
            if len(tokens) >= 2 and len(tokens[-1]) <= 2:
                surname = tokens[-2]
        normalized = normalize_text(surname)
        if len(normalized) <= 1:
            continue
        if normalized and normalized not in surnames:
            surnames.append(normalized)
    return surnames[:8]


# Score authors.
def score_authors(reference_authors: str, candidate_text: str) -> float:
    surnames = parse_reference_surnames(reference_authors)
    if not surnames:
        return 0.0
    normalized_candidate = normalize_text(candidate_text)
    candidate_tokens = token_set(candidate_text, min_len=3)
    matches = 0
    for surname in surnames:
        if surname in normalized_candidate:
            matches += 1
            continue
        surname_tokens = {token for token in surname.split() if len(token) >= 3}
        if surname_tokens and surname_tokens.issubset(candidate_tokens):
            matches += 1
    return matches / len(surnames)


# Check whether section heading.
def is_section_heading(line: str) -> bool:
    normalized = normalize_text(line)
    return any(normalized.startswith(marker) for marker in SECTION_HEADING_MARKERS)


# Check whether abstract boundary.
def is_abstract_boundary(line: str) -> bool:
    return ABSTRACT_BOUNDARY_RE.match(line.strip()) is not None


# Build body metrics.
def body_metrics(record: dict[str, Any]) -> tuple[int, int, bool]:
    lines: list[str] = []
    for page in record.get("pages") or []:
        page_text = str(page.get("text") or "")
        for raw in page_text.splitlines():
            line = " ".join(raw.split())
            if line:
                lines.append(line)
    if not lines:
        return 0, 0, True
    section_hits = sum(1 for line in lines if is_section_heading(line))
    body_text = " ".join(lines[min(6, len(lines)) :])
    body_chars = len(body_text)
    header_only = section_hits == 0 and body_chars < 280
    return section_hits, body_chars, header_only


# Build spillover detected.
def spillover_detected(record: dict[str, Any]) -> bool:
    lines: list[str] = []
    for page in record.get("pages") or []:
        page_text = str(page.get("text") or "")
        for raw in page_text.splitlines():
            line = " ".join(raw.split())
            if line:
                lines.append(line)
    if len(lines) < 8:
        return False
    # If another abstract boundary appears in the tail region, trimming likely leaked into a neighbour.
    for line in lines[5:]:
        if is_abstract_boundary(line):
            return True
    return False


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
        is_proceedings = (
            (resolved.get("resolved_source_category") or "") == "conference_abstract"
            or (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
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
        title_score = score_title(reference_title, page_text)
        author_score = score_authors(reference_authors, page_text)
        combined = (0.75 * title_score) + (0.25 * author_score)
        if combined > best_combined:
            best_page_index = page_index
            best_title_score = title_score
            best_author_score = author_score
            best_combined = combined
            best_excerpt = " ".join(page_text.split())[:500]
    return best_page_index, best_title_score, best_author_score, best_combined, best_excerpt


# Build derive qc status.
def derive_qc_status(
    trimmed_present: bool,
    title_score: float,
    author_score: float,
    combined_score: float,
    section_hits: int,
    body_chars: int,
    header_only: bool,
    spillover: bool,
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
    if spillover:
        return "spillover_detected", True, "Trim appears to include a neighbouring abstract boundary."
    if header_only:
        return "header_only_source", True, "Matched source appears to be a title/author listing without abstract body text."

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
    spillover: bool,
) -> dict[str, str]:
    status, manual_follow_up, note = derive_qc_status(
        trimmed_present=trimmed_path is not None,
        title_score=title_score,
        author_score=author_score,
        combined_score=combined_score,
        section_hits=section_hits,
        body_chars=body_chars,
        header_only=header_only,
        spillover=spillover,
    )
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
        "spillover_flag": bool_text(spillover),
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
        if not preferred_path.exists():
            continue
        reference_row = reference_rows.get(paper_id, {})
        resolved_source = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        record = load_text_record(preferred_path)
        best_page_index, title_score, author_score, combined_score, best_excerpt = page_matches(
            record=record,
            reference_title=(reference_row.get("Title") or "").strip(),
            reference_authors=(reference_row.get("Authors") or "").strip(),
        )
        section_hits, body_chars, header_only = body_metrics(record)
        spillover = spillover_detected(record) if trimmed_path.exists() else False
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
                spillover=spillover,
            )
        )

    write_registry(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
