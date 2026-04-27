from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._sps_case_count_registry import (
    HEURISTIC_VERSION,
    build_case_count_candidate_package,
    count_row_fieldnames,
    count_row_from_resolution,
    relative_to_repo,
    write_count_rows,
)
from src.pipelines.stage06_counting.overrides import (
    MANUAL_REVIEW_LEDGER_PATH,
    apply_override_to_count_row,
    reviewed_override_rows_by_id,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
INPUT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
OUTPUT_REGISTRY_PATH = INPUT_REGISTRY_PATH
GOLD_MANIFEST_PATH = (
    REPO_ROOT
    / "qa"
    / "validation"
    / "source_categorisation"
    / "gold_standard"
    / "stage06_count_gold"
    / "manifest.json"
)
GOLD_PAPERS_DIR = GOLD_MANIFEST_PATH.parent / "papers"
DEFAULT_HYBRID_OUTPUT_GLOBS = [
    str(REPO_ROOT / "qa" / "validation" / "stage06_llm" / "stage06_backfill_*_combined.csv"),
    str(REPO_ROOT / "qa" / "validation" / "stage06_llm" / "stage06_*_hybrid_refresh_*.csv"),
]
DEFAULT_REPORT_PATH = REPO_ROOT / "qa" / "validation" / "stage06_llm" / "stage06_publish_report_20260427.json"
REFERENCE_HEURISTIC_VERSION = "stage06_publish_v1_reference_heuristic"
BAD_ALIGNMENT_TAGS = {"incorrect_reference", "likely_wrong_pdf_attached"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_rows_by_id(path: Path, key_column: str = "paper_id") -> dict[str, dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = str(row.get(key_column) or "").strip()
        if key:
            rows_by_id[key] = dict(row)
    return rows_by_id


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_int(value: object, *, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    text = str(paper_id or "").strip()
    try:
        return int(text), text
    except ValueError:
        return 10**9, text


def complete_count_row(row: dict[str, str]) -> dict[str, str]:
    return {fieldname: str(row.get(fieldname) or "").strip() for fieldname in count_row_fieldnames()}


def overlay_count_row(base_row: dict[str, str], overlay_row: dict[str, str]) -> dict[str, str]:
    row = complete_count_row(base_row)
    for fieldname in count_row_fieldnames():
        value = str(overlay_row.get(fieldname) or "").strip()
        if value:
            row[fieldname] = value
    return row


def select_hybrid_rows(patterns: list[str]) -> tuple[dict[str, dict[str, str]], list[str]]:
    selected_rows: dict[str, dict[str, str]] = {}
    selected_sources: dict[str, str] = {}
    paths: list[str] = []
    for pattern in patterns:
        paths.extend(glob.glob(pattern))

    def score(row: dict[str, str], path: str) -> tuple[str, int, int, str]:
        return (
            str(row.get("counted_at_utc") or ""),
            1 if str(row.get("count_evidence_json_path") or "").strip() else 0,
            1 if str(row.get("likely_sps_case_count") or "").strip() else 0,
            path,
        )

    for path in sorted(set(paths)):
        for row in load_csv_rows(Path(path)):
            paper_id = str(row.get("paper_id") or "").strip()
            if not paper_id:
                continue
            existing = selected_rows.get(paper_id)
            if existing is None or score(row, path) > score(existing, selected_sources[paper_id]):
                selected_rows[paper_id] = complete_count_row(row)
                selected_sources[paper_id] = path
    return selected_rows, sorted(set(paths))


def load_gold_rows(
    *,
    manifest_path: Path,
    gold_papers_dir: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    manifest = load_json(manifest_path)
    active_rows: dict[str, dict[str, str]] = {}
    excluded_entries: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("entries") or []:
        paper_id = str(entry.get("paper_id") or "").strip()
        if not paper_id:
            continue
        status = str(entry.get("gold_status") or "").strip()
        if status == "active":
            json_path_text = str(entry.get("gold_json_path") or "").strip()
            json_path = REPO_ROOT / json_path_text if json_path_text else gold_papers_dir / f"{paper_id}.json"
            payload = load_json(json_path)
            count_row = payload.get("count_row") if isinstance(payload.get("count_row"), dict) else {}
            if count_row:
                active_rows[paper_id] = complete_count_row(
                    {
                        **count_row,
                        "count_audit_status": "manual_gold_review",
                        "count_verification_status": "manual_gold_review",
                    }
                )
        elif status == "excluded":
            excluded_entries[paper_id] = dict(entry)
    return active_rows, excluded_entries


def bad_alignment_rows_by_id(
    *,
    source_manual_review_path: Path,
    excluded_gold_entries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(source_manual_review_path):
        paper_id = str(row.get("paper_id") or "").strip()
        alignment_tag = str(row.get("pdf_content_alignment_tag") or "").strip()
        if paper_id and alignment_tag in BAD_ALIGNMENT_TAGS:
            rows[paper_id] = {
                "paper_id": paper_id,
                "title": str(row.get("title") or "").strip(),
                "source_category": str(row.get("final_source_category") or "unclear_manual_review").strip(),
                "source_subtype": str(row.get("final_source_subtype") or alignment_tag).strip(),
                "alignment_tag": alignment_tag,
                "reviewer_notes": str(row.get("review_decision_notes") or "").strip(),
                "reviewed_at_utc": str(row.get("reviewed_at_utc") or "").strip(),
            }
    for paper_id, entry in excluded_gold_entries.items():
        rows.setdefault(
            paper_id,
            {
                "paper_id": paper_id,
                "title": "",
                "source_category": str(entry.get("reviewed_source_category") or "unclear_manual_review").strip(),
                "source_subtype": str(entry.get("pdf_content_alignment_tag") or "bad_alignment").strip(),
                "alignment_tag": str(entry.get("pdf_content_alignment_tag") or "").strip(),
                "reviewer_notes": str(entry.get("reason") or "").strip(),
                "reviewed_at_utc": str(entry.get("reviewed_at_utc") or "").strip(),
            },
        )
    return rows


def exclusion_row(base_row: dict[str, str], review_row: dict[str, str]) -> dict[str, str]:
    paper_id = str(base_row.get("paper_id") or review_row.get("paper_id") or "").strip()
    alignment_tag = str(review_row.get("alignment_tag") or "bad_alignment").strip()
    reason_bits = [
        "source_linkage_blocked=true",
        f"alignment_tag={alignment_tag}",
    ]
    notes = str(review_row.get("reviewer_notes") or "").strip()
    if notes:
        reason_bits.append(f"reviewer_notes={notes}")
    row = complete_count_row(base_row)
    row.update(
        {
            "paper_id": paper_id,
            "source_category": str(review_row.get("source_category") or "unclear_manual_review").strip(),
            "source_subtype": str(review_row.get("source_subtype") or alignment_tag).strip(),
            "count_eligible": "false",
            "likely_sps_case_count": "0",
            "count_confidence": "low",
            "count_basis": "source_linkage_exclusion",
            "count_manual_review_required": "true",
            "count_original_cohort_provenance_uncertain": "true",
            "count_reason": " | ".join(reason_bits),
            "count_version": "stage06_publish_v1+source_linkage_exclusion",
            "count_audit_status": "source_linkage_blocked",
            "count_verification_status": "excluded_bad_source_alignment",
            "count_validator_flags": alignment_tag,
            "counted_at_utc": str(review_row.get("reviewed_at_utc") or now_utc_iso()).strip(),
        }
    )
    return row


def reference_rows_by_id(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        paper_id = str(row.get("Covidence") or "").strip()
        if paper_id:
            rows[paper_id] = dict(row)
    return rows


def preferred_path_for_reference_fallback(
    *,
    base_row: dict[str, str],
    source_row: dict[str, str],
    paper_id: str,
) -> Path:
    path_text = (
        str(base_row.get("preferred_text_json_path") or "").strip()
        or str(source_row.get("preferred_text_json_path") or "").strip()
        or str(source_row.get("text_json_path") or "").strip()
        or f"data/extraction_json/text/{paper_id}.json"
    )
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def build_reference_heuristic_row(
    *,
    paper_id: str,
    base_row: dict[str, str],
    reference_row: dict[str, str],
    source_row: dict[str, str],
) -> dict[str, str]:
    preferred_path = preferred_path_for_reference_fallback(
        base_row=base_row,
        source_row=source_row,
        paper_id=paper_id,
    )
    package = build_case_count_candidate_package(
        reference_row=reference_row,
        text_record={"paper_id": paper_id, "_path": str(preferred_path), "pages": []},
        preferred_record={"paper_id": paper_id, "_path": str(preferred_path), "pages": []},
        preferred_path=preferred_path,
        source_row=source_row,
        heuristic_version=HEURISTIC_VERSION,
    )
    preferred_candidate = package.preferred_candidate()
    reason_bits = [
        "reference_only_publish_fallback=true",
        f"count_basis={preferred_candidate.count_basis}",
        f"count_confidence={preferred_candidate.count_confidence}",
    ]
    if package.candidate_generation_notes:
        reason_bits.append(f"candidate_notes={'; '.join(package.candidate_generation_notes)}")
    row = count_row_from_resolution(
        package=package,
        final_count=preferred_candidate.proposed_count,
        final_confidence=preferred_candidate.count_confidence,
        final_basis=preferred_candidate.count_basis,
        final_manual_review_required=True,
        final_reason=" | ".join(reason_bits),
        count_version=REFERENCE_HEURISTIC_VERSION,
        count_verification_status="reference_heuristic_manual_review_required",
        count_audit_status="reference_heuristic_publish_fallback",
    )
    row["preferred_text_json_path"] = relative_to_repo(preferred_path)
    return overlay_count_row(base_row, row)


def row_needs_reference_fallback(row: dict[str, str]) -> bool:
    if str(row.get("likely_sps_case_count") or "").strip():
        return False
    return truthy(row.get("count_eligible"))


def validate_rows(
    *,
    rows: list[dict[str, str]],
    gold_rows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    rows_by_id = {str(row.get("paper_id") or "").strip(): row for row in rows}
    blank_count_paper_ids = [
        paper_id
        for paper_id, row in rows_by_id.items()
        if truthy(row.get("count_eligible")) and not str(row.get("likely_sps_case_count") or "").strip()
    ]
    gold_mismatches: list[dict[str, Any]] = []
    silent_wrong_gold_paper_ids: list[str] = []
    for paper_id, gold_row in gold_rows.items():
        row = rows_by_id.get(paper_id, {})
        predicted = parse_int(row.get("likely_sps_case_count"), default=-1)
        expected = parse_int(gold_row.get("likely_sps_case_count"), default=-1)
        if predicted == expected:
            continue
        requires_review = truthy(row.get("count_manual_review_required"))
        if not requires_review:
            silent_wrong_gold_paper_ids.append(paper_id)
        gold_mismatches.append(
            {
                "paper_id": paper_id,
                "expected": expected,
                "predicted": predicted,
                "count_manual_review_required": requires_review,
                "count_verification_status": str(row.get("count_verification_status") or "").strip(),
            }
        )
    return {
        "blank_count_paper_ids": sorted(blank_count_paper_ids, key=sort_key_for_paper_id),
        "gold_mismatches": sorted(gold_mismatches, key=lambda item: sort_key_for_paper_id(str(item["paper_id"]))),
        "silent_wrong_gold_paper_ids": sorted(silent_wrong_gold_paper_ids, key=sort_key_for_paper_id),
    }


def publish_rows(
    *,
    input_registry_path: Path = INPUT_REGISTRY_PATH,
    references_csv: Path = REFERENCES_CSV,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    manual_review_path: Path = MANUAL_REVIEW_LEDGER_PATH,
    gold_manifest_path: Path = GOLD_MANIFEST_PATH,
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
    hybrid_output_globs: list[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    base_rows = load_csv_rows_by_id(input_registry_path)
    reference_rows = reference_rows_by_id(references_csv)
    source_rows = load_csv_rows_by_id(source_registry_path)
    hybrid_rows, hybrid_paths = select_hybrid_rows(hybrid_output_globs or DEFAULT_HYBRID_OUTPUT_GLOBS)
    manual_rows = reviewed_override_rows_by_id(manual_review_path)
    gold_rows, excluded_gold_entries = load_gold_rows(
        manifest_path=gold_manifest_path,
        gold_papers_dir=gold_papers_dir,
    )
    bad_alignment_rows = bad_alignment_rows_by_id(
        source_manual_review_path=source_manual_review_path,
        excluded_gold_entries=excluded_gold_entries,
    )

    all_paper_ids = set(base_rows) | set(source_rows)
    rows_by_id = {paper_id: complete_count_row(base_rows.get(paper_id, {})) for paper_id in all_paper_ids}
    layer_counts = {
        "base_rows": len(base_rows),
        "hybrid_rows_available": len(hybrid_rows),
        "manual_override_rows_available": len(manual_rows),
        "active_gold_rows_available": len(gold_rows),
        "bad_alignment_rows_available": len(bad_alignment_rows),
    }
    applied = {
        "hybrid": [],
        "manual_override": [],
        "active_gold": [],
        "bad_alignment_exclusion": [],
        "reference_heuristic_fallback": [],
    }

    for paper_id, hybrid_row in hybrid_rows.items():
        if paper_id not in rows_by_id:
            continue
        rows_by_id[paper_id] = overlay_count_row(rows_by_id[paper_id], hybrid_row)
        applied["hybrid"].append(paper_id)

    for paper_id, manual_row in manual_rows.items():
        if paper_id not in rows_by_id:
            continue
        rows_by_id[paper_id] = apply_override_to_count_row(rows_by_id[paper_id], manual_row)
        applied["manual_override"].append(paper_id)

    for paper_id, gold_row in gold_rows.items():
        if paper_id not in rows_by_id:
            continue
        rows_by_id[paper_id] = overlay_count_row(rows_by_id[paper_id], gold_row)
        applied["active_gold"].append(paper_id)

    for paper_id, review_row in bad_alignment_rows.items():
        if paper_id not in rows_by_id:
            continue
        rows_by_id[paper_id] = exclusion_row(rows_by_id[paper_id], review_row)
        applied["bad_alignment_exclusion"].append(paper_id)

    for paper_id in sorted(rows_by_id, key=sort_key_for_paper_id):
        row = rows_by_id[paper_id]
        if not row_needs_reference_fallback(row):
            continue
        reference_row = reference_rows.get(paper_id, {})
        source_row = source_rows.get(paper_id, {})
        if not reference_row or not source_row:
            continue
        rows_by_id[paper_id] = build_reference_heuristic_row(
            paper_id=paper_id,
            base_row=row,
            reference_row=reference_row,
            source_row=source_row,
        )
        applied["reference_heuristic_fallback"].append(paper_id)

    ordered_rows = [
        complete_count_row(rows_by_id[paper_id])
        for paper_id in sorted(rows_by_id, key=sort_key_for_paper_id)
    ]
    validation = validate_rows(rows=ordered_rows, gold_rows=gold_rows)
    report = {
        "generated_at_utc": now_utc_iso(),
        "schema_version": "stage06_publish_report_v1",
        "input_registry_path": relative_to_repo(input_registry_path),
        "output_registry_path": relative_to_repo(OUTPUT_REGISTRY_PATH),
        "hybrid_output_paths": [relative_to_repo(Path(path)) for path in hybrid_paths],
        "row_count": len(ordered_rows),
        "layer_counts": layer_counts,
        "applied_counts": {layer: len(ids) for layer, ids in applied.items()},
        "applied_paper_ids": {
            layer: sorted(ids, key=sort_key_for_paper_id)
            for layer, ids in applied.items()
        },
        "validation": validation,
        "manual_review_required_count": sum(
            1 for row in ordered_rows if truthy(row.get("count_manual_review_required"))
        ),
    }
    return ordered_rows, report


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the canonical stage-06 SPS case-count registry from reviewed gold, manual overrides, and hybrid QA outputs."
    )
    parser.add_argument("--input-registry-path", type=Path, default=INPUT_REGISTRY_PATH)
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--source-registry-path", type=Path, default=SOURCE_REGISTRY_PATH)
    parser.add_argument("--source-manual-review-path", type=Path, default=SOURCE_MANUAL_REVIEW_PATH)
    parser.add_argument("--manual-review-path", type=Path, default=MANUAL_REVIEW_LEDGER_PATH)
    parser.add_argument("--gold-manifest-path", type=Path, default=GOLD_MANIFEST_PATH)
    parser.add_argument("--gold-papers-dir", type=Path, default=GOLD_PAPERS_DIR)
    parser.add_argument("--hybrid-output-glob", action="append", default=None)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_REGISTRY_PATH)
    parser.add_argument("--report-json-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-validation-errors",
        action="store_true",
        help="Write outputs even if blank count rows or unflagged gold mismatches remain.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, report = publish_rows(
        input_registry_path=args.input_registry_path,
        references_csv=args.references_csv,
        source_registry_path=args.source_registry_path,
        source_manual_review_path=args.source_manual_review_path,
        manual_review_path=args.manual_review_path,
        gold_manifest_path=args.gold_manifest_path,
        gold_papers_dir=args.gold_papers_dir,
        hybrid_output_globs=args.hybrid_output_glob,
    )
    validation = report["validation"]
    validation_errors = bool(validation["blank_count_paper_ids"] or validation["silent_wrong_gold_paper_ids"])
    if validation_errors and not args.allow_validation_errors:
        raise SystemExit(
            "Refusing to publish stage 06 because validation errors remain: "
            f"blank_count_paper_ids={validation['blank_count_paper_ids']}; "
            f"silent_wrong_gold_paper_ids={validation['silent_wrong_gold_paper_ids']}."
        )
    if not args.dry_run:
        write_count_rows(rows, args.output_path)
        report["output_registry_path"] = relative_to_repo(args.output_path)
        write_report(report, args.report_json_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
