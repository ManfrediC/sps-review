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
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "00_build_paper_artifact_registry.py"


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
        help="Heuristic source categorisation registry.",
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


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return " ".join(ascii_text.split())


def token_set(text: str, min_len: int = 3) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) >= min_len}


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
    return max(sequence, (0.65 * sequence) + (0.35 * overlap))


def parse_reference_surnames(authors: str) -> list[str]:
    surnames: list[str] = []
    for chunk in re.split(r";", authors or ""):
        part = chunk.strip()
        if not part:
            continue
        surname = part.split(",", 1)[0].strip()
        normalized = normalize_text(surname)
        if normalized and normalized not in surnames:
            surnames.append(normalized)
    return surnames[:8]


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


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def derive_qc_status(
    trimmed_present: bool,
    title_score: float,
    author_score: float,
    combined_score: float,
) -> tuple[str, bool, str]:
    strong = title_score >= 0.72 and author_score >= 0.20
    moderate = combined_score >= 0.62 or title_score >= 0.58 or author_score >= 0.40
    if trimmed_present:
        if strong:
            return "trimmed_match_confirmed", False, "Trimmed proceedings text matches the target title/authors strongly."
        if moderate:
            return "trimmed_partial_match", True, "Trimmed text looks related but needs a manual check for completeness."
        return "trimmed_mismatch_suspected", True, "Trimmed text does not match the target abstract confidently."

    if strong:
        return "full_text_localised_untrimmed", True, "Target abstract appears localised in the proceedings text but no trimmed artifact exists."
    if moderate:
        return "full_text_partial_match", True, "Proceedings text contains a partial title/author match only."
    return "not_localised", True, "Could not localise the target abstract confidently in the proceedings text."


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
) -> dict[str, str]:
    status, manual_follow_up, note = derive_qc_status(
        trimmed_present=trimmed_path is not None,
        title_score=title_score,
        author_score=author_score,
        combined_score=combined_score,
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
        "best_match_excerpt": best_excerpt,
        "qc_note": note,
        "checked_at_utc": now_utc_iso(),
    }


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
        "best_match_excerpt",
        "qc_note",
        "checked_at_utc",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


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
            )
        )

    write_registry(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
