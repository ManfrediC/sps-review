from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
DEFAULT_SEED = 20260405
DEFAULT_BUCKET_QUOTAS = {
    "conference_edge": 10,
    "case_group_boundary": 10,
    "review_lab_edge": 5,
    "high_confidence_control": 5,
}
CONFIDENCE_PRIORITY = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a stratified manual-review batch for source categorisation calibration."
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--manual-review-path",
        type=Path,
        default=MANUAL_REVIEW_PATH,
        help="Path to source_categorisation_manual_review.csv.",
    )
    parser.add_argument(
        "--count-registry-path",
        type=Path,
        default=COUNT_REGISTRY_PATH,
        help="Path to source_sps_case_count_registry.csv.",
    )
    parser.add_argument(
        "--references-csv",
        type=Path,
        default=REFERENCES_CSV,
        help="Reference export used to enrich review packets.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for reproducible within-bucket ordering.",
    )
    parser.add_argument(
        "--conference-edge-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["conference_edge"],
        help="Rows to sample for conference-edge review.",
    )
    parser.add_argument(
        "--case-group-boundary-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["case_group_boundary"],
        help="Rows to sample for case-series versus group-study review.",
    )
    parser.add_argument(
        "--review-lab-edge-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["review_lab_edge"],
        help="Rows to sample for review versus lab-heavy review.",
    )
    parser.add_argument(
        "--high-confidence-control-size",
        type=int,
        default=DEFAULT_BUCKET_QUOTAS["high_confidence_control"],
        help="Rows to sample as high-confidence controls.",
    )
    parser.add_argument(
        "--include-reviewed",
        action="store_true",
        help="Include papers already present in source_categorisation_manual_review.csv.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--review-csv-path",
        type=Path,
        default=None,
        help="Optional CSV review sheet path.",
    )
    parser.add_argument(
        "--text-output-dir",
        type=Path,
        default=None,
        help="Optional directory for preferred-text TXT packets.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    rows = {}
    for row in load_csv_rows(path):
        key = (row.get("Covidence") or "").strip()
        if key:
            rows[key] = row
    return rows


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


def load_reviewed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        (row.get("paper_id") or "").strip()
        for row in load_csv_rows(path)
        if (row.get("paper_id") or "").strip()
    }


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def resolve_repo_path(path_text: str) -> Path:
    path = Path(str(path_text or "").strip())
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def attach_case_count_fields(
    row: dict[str, str],
    *,
    count_row: dict[str, str],
) -> dict[str, str]:
    if not count_row:
        return {
            **row,
            "count_confidence": "",
            "count_basis": "",
            "count_manual_review_required": "",
            "count_reason": "",
        }
    return {
        **row,
        "likely_case_count": (count_row.get("likely_sps_case_count") or "").strip(),
        "count_confidence": (count_row.get("count_confidence") or "").strip(),
        "count_basis": (count_row.get("count_basis") or "").strip(),
        "count_manual_review_required": (count_row.get("count_manual_review_required") or "").strip(),
        "count_reason": (count_row.get("count_reason") or "").strip(),
    }


def signal_text(row: dict[str, str], signals: list[str]) -> str:
    return "; ".join(signals)


def conference_edge_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    conference_hits = parse_int(row.get("conference_marker_hits"))
    proceedings_detected = truthy(row.get("proceedings_detected"))
    manual_review_required = truthy(row.get("manual_review_required"))
    preferred_text_source = (row.get("preferred_text_source") or "").strip()
    trim_status = (row.get("trim_status") or "").strip()
    reason = (row.get("categorisation_reason") or "").lower()

    signals: list[str] = []
    if category == "conference_abstract":
        if confidence != "high":
            signals.append("conference_non_high_confidence")
        if manual_review_required:
            signals.append("conference_manual_review_required")
        if preferred_text_source == "full_text":
            signals.append("conference_using_full_text")
        if trim_status and trim_status not in {"trimmed_auto", "not_needed"}:
            signals.append(f"conference_trim_status={trim_status}")
    else:
        if proceedings_detected:
            signals.append("non_conference_with_proceedings_detected")
        if conference_hits > 0:
            signals.append("non_conference_with_conference_markers")
        if "conference_metadata_markers=" in reason:
            signals.append("non_conference_with_conference_metadata")
    return signals


def case_group_boundary_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    likely_case_count = parse_int(row.get("likely_case_count"))
    patient_label_count = parse_int(row.get("patient_label_count"))
    manual_review_required = truthy(row.get("manual_review_required"))
    recommended_next_action = (row.get("recommended_next_action") or "").strip()

    if category not in {
        "case_series_or_multi_case",
        "observational_group_study",
        "lab_heavy_clinical_or_translational",
    }:
        return []

    signals: list[str] = []
    if confidence != "high":
        signals.append("group_boundary_non_high_confidence")
    if manual_review_required:
        signals.append("group_boundary_manual_review_required")
    if 2 <= likely_case_count <= 20:
        signals.append("group_boundary_small_or_mid_case_count")
    if likely_case_count >= 20 and category == "case_series_or_multi_case":
        signals.append("group_boundary_large_case_count_for_split")
    if patient_label_count > 0:
        signals.append("group_boundary_patient_labels_present")
    if recommended_next_action in {"split_cases_then_langextract", "review_source_category_then_split"}:
        signals.append(f"group_boundary_action={recommended_next_action}")
    return signals


def review_lab_edge_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    manual_review_required = truthy(row.get("manual_review_required"))
    review_hits = parse_int(row.get("review_marker_hits"))
    non_clinical_hits = parse_int(row.get("non_clinical_marker_hits"))

    if category not in {
        "review_article",
        "review_format_with_embedded_original_cohort",
        "lab_heavy_clinical_or_translational",
        "non_clinical_basic_science",
        "unclear_manual_review",
    }:
        return []

    signals: list[str] = []
    if category == "unclear_manual_review":
        signals.append("unclear_routing_bucket")
    if confidence != "high":
        signals.append("review_lab_non_high_confidence")
    if manual_review_required:
        signals.append("review_lab_manual_review_required")
    if review_hits > 0:
        signals.append("review_markers_present")
    if non_clinical_hits > 0:
        signals.append("non_clinical_markers_present")
    return signals


def high_confidence_control_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    manual_review_required = truthy(row.get("manual_review_required"))

    if manual_review_required or confidence != "high":
        return []
    if category not in {
        "single_case_report",
        "conference_abstract",
        "observational_group_study",
        "interventional_study",
    }:
        return []
    return ["high_confidence_control"]


def build_bucket_candidates(
    rows: list[dict[str, str]],
) -> dict[str, list[tuple[dict[str, str], list[str]]]]:
    buckets = {
        "conference_edge": [],
        "case_group_boundary": [],
        "review_lab_edge": [],
        "high_confidence_control": [],
    }
    for row in rows:
        if signals := conference_edge_signals(row):
            buckets["conference_edge"].append((row, signals))
        if signals := case_group_boundary_signals(row):
            buckets["case_group_boundary"].append((row, signals))
        if signals := review_lab_edge_signals(row):
            buckets["review_lab_edge"].append((row, signals))
        if signals := high_confidence_control_signals(row):
            buckets["high_confidence_control"].append((row, signals))
    return buckets


def candidate_priority(row: dict[str, str], signals: list[str]) -> tuple[int, int, int, int, int]:
    confidence = (row.get("classification_confidence") or "").strip()
    return (
        0 if truthy(row.get("manual_review_required")) else 1,
        CONFIDENCE_PRIORITY.get(confidence, 1),
        -len(signals),
        0 if (row.get("source_category") or "").strip() == "unclear_manual_review" else 1,
        parse_int(row.get("paper_id"), default=10**9),
    )


def prioritise_candidates(
    candidates: list[tuple[dict[str, str], list[str]]],
    *,
    rng: random.Random,
) -> list[tuple[dict[str, str], list[str]]]:
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda item: candidate_priority(item[0], item[1]))


def select_rows(
    rows: list[dict[str, str]],
    *,
    bucket_quotas: dict[str, int],
    seed: int,
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, int]]:
    rng = random.Random(seed)
    bucket_candidates = build_bucket_candidates(rows)
    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()
    available_counts = {bucket: len(items) for bucket, items in bucket_candidates.items()}
    selected_counts = {bucket: 0 for bucket in bucket_quotas}

    for bucket_name, quota in bucket_quotas.items():
        ordered = prioritise_candidates(bucket_candidates[bucket_name], rng=rng)
        for row, signals in ordered:
            paper_id = (row.get("paper_id") or "").strip()
            if paper_id in selected_ids:
                continue
            selected_ids.add(paper_id)
            selected.append(
                {
                    **row,
                    "selection_bucket": bucket_name,
                    "selection_signals": signal_text(row, signals),
                }
            )
            selected_counts[bucket_name] += 1
            if selected_counts[bucket_name] >= quota:
                break

    target_total = sum(bucket_quotas.values())
    if len(selected) < target_total:
        remaining_candidates: list[tuple[dict[str, str], list[str], str]] = []
        for bucket_name, items in bucket_candidates.items():
            for row, signals in items:
                paper_id = (row.get("paper_id") or "").strip()
                if paper_id not in selected_ids:
                    remaining_candidates.append((row, signals, bucket_name))
        rng.shuffle(remaining_candidates)
        remaining_candidates.sort(key=lambda item: candidate_priority(item[0], item[1]))
        for row, signals, bucket_name in remaining_candidates:
            paper_id = (row.get("paper_id") or "").strip()
            if paper_id in selected_ids:
                continue
            selected_ids.add(paper_id)
            selected.append(
                {
                    **row,
                    "selection_bucket": f"{bucket_name}_overflow",
                    "selection_signals": signal_text(row, signals),
                }
            )
            if len(selected) >= target_total:
                break

    selected.sort(key=lambda row: (row["selection_bucket"], parse_int(row.get("paper_id"))))
    return selected, available_counts, selected_counts


def load_preferred_text_record(row: dict[str, str]) -> tuple[dict[str, Any], Path]:
    preferred_path = resolve_repo_path(row.get("preferred_text_json_path") or "")
    if not preferred_path.exists():
        preferred_path = resolve_repo_path(row.get("text_json_path") or "")
    record = json.loads(preferred_path.read_text(encoding="utf-8"))
    return record, preferred_path


def render_text_packet(
    *,
    row: dict[str, str],
    reference_row: dict[str, str],
    record: dict[str, Any],
    preferred_path: Path,
) -> str:
    pages = record.get("pages") or []
    header_lines = [
        f"Paper ID: {(row.get('paper_id') or '').strip()}",
        f"Title: {(row.get('title') or '').strip()}",
        f"Authors: {(row.get('authors') or '').strip()}",
        f"Published year: {(row.get('published_year') or '').strip()}",
        f"Journal: {(row.get('journal') or '').strip()}",
        f"Pages: {(reference_row.get('Pages') or '').strip() or 'Unknown'}",
        f"Tags: {(row.get('tags') or '').strip() or 'None'}",
        f"Notes: {(row.get('notes') or '').strip() or 'None'}",
        f"Selection bucket: {(row.get('selection_bucket') or '').strip()}",
        f"Selection signals: {(row.get('selection_signals') or '').strip() or 'None'}",
        f"Predicted category: {(row.get('source_category') or '').strip()}",
        f"Predicted subtype: {(row.get('source_subtype') or '').strip()}",
        f"Predicted confidence: {(row.get('classification_confidence') or '').strip()}",
        f"Likely case count: {(row.get('likely_case_count') or '').strip() or 'Unknown'}",
        f"Count confidence: {(row.get('count_confidence') or '').strip() or 'Unknown'}",
        f"Count basis: {(row.get('count_basis') or '').strip() or 'Unknown'}",
        f"Preferred text source: {(row.get('preferred_text_source') or '').strip()}",
        f"Preferred text JSON path: {display_path(preferred_path)}",
        f"Recommended next action: {(row.get('recommended_next_action') or '').strip()}",
        f"Categorisation reason: {(row.get('categorisation_reason') or '').strip()}",
        f"Count reason: {(row.get('count_reason') or '').strip() or 'None'}",
        f"Reference abstract: {(reference_row.get('Abstract') or '').strip() or 'None'}",
    ]

    sections = ["\n".join(header_lines)]
    for index, page in enumerate(pages, start=1):
        page_num = page.get("page_num")
        if page_num in {None, ""}:
            page_num = page.get("page_index")
            if isinstance(page_num, int):
                page_num += 1
            elif str(page_num or "").isdigit():
                page_num = int(str(page_num)) + 1
            else:
                page_num = index
        sections.append(
            "\n".join(
                [
                    "=" * 100,
                    f"Page {page_num}",
                    "-" * 100,
                    str(page.get("text") or ""),
                ]
            )
        )

    return "\n\n".join(sections).strip() + "\n"


def write_text_packets(
    selected_rows: list[dict[str, str]],
    *,
    reference_rows: dict[str, dict[str, str]],
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_paths: dict[str, str] = {}
    for row in selected_rows:
        paper_id = (row.get("paper_id") or "").strip()
        record, preferred_path = load_preferred_text_record(row)
        rendered = render_text_packet(
            row=row,
            reference_row=reference_rows.get(paper_id, {}),
            record=record,
            preferred_path=preferred_path,
        )
        out_path = output_dir / f"{paper_id}.txt"
        out_path.write_text(rendered, encoding="utf-8")
        packet_paths[paper_id] = display_path(out_path)
    return packet_paths


def build_review_rows(selected_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in selected_rows:
        paper_id = (row.get("paper_id") or "").strip()
        rows.append(
            {
                "ID": paper_id,
                "selection_bucket": (row.get("selection_bucket") or "").strip(),
                "selection_signals": (row.get("selection_signals") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "authors": (row.get("authors") or "").strip(),
                "predicted_source_category": (row.get("source_category") or "").strip(),
                "predicted_source_subtype": (row.get("source_subtype") or "").strip(),
                "predicted_confidence": (row.get("classification_confidence") or "").strip(),
                "likely_case_count": (row.get("likely_case_count") or "").strip(),
                "review_status": "",
                "reviewer_correct_sps_patient_count": "",
                "reviewer_final_category": "",
                "reviewer_final_subtype": "",
                "reviewer_alignment": "",
                "reviewer_notes": "",
            }
        )
    return rows


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    *,
    selected_rows: list[dict[str, str]],
    available_counts: dict[str, int],
    selected_counts: dict[str, int],
    bucket_quotas: dict[str, int],
    include_reviewed: bool,
    seed: int,
) -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "seed": seed,
        "include_reviewed": include_reviewed,
        "bucket_quotas": bucket_quotas,
        "available_bucket_counts": available_counts,
        "selected_bucket_counts": dict(Counter(row["selection_bucket"] for row in selected_rows)),
        "selected_primary_bucket_counts": selected_counts,
        "selected_category_counts": dict(Counter(row["source_category"] for row in selected_rows)),
        "selected_confidence_counts": dict(Counter(row["classification_confidence"] for row in selected_rows)),
        "selected_rows": [
            {
                "paper_id": (row.get("paper_id") or "").strip(),
                "selection_bucket": (row.get("selection_bucket") or "").strip(),
                "selection_signals": (row.get("selection_signals") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "source_category": (row.get("source_category") or "").strip(),
                "source_subtype": (row.get("source_subtype") or "").strip(),
                "classification_confidence": (row.get("classification_confidence") or "").strip(),
            }
            for row in selected_rows
        ],
    }


def main() -> None:
    args = parse_args()
    bucket_quotas = {
        "conference_edge": args.conference_edge_size,
        "case_group_boundary": args.case_group_boundary_size,
        "review_lab_edge": args.review_lab_edge_size,
        "high_confidence_control": args.high_confidence_control_size,
    }
    source_rows = load_csv_rows(args.source_registry_path)
    count_rows = load_csv_rows_by_id(args.count_registry_path, "paper_id")
    source_rows = [
        attach_case_count_fields(
            row,
            count_row=count_rows.get((row.get("paper_id") or "").strip(), {}),
        )
        for row in source_rows
    ]
    if not args.include_reviewed:
        reviewed_ids = load_reviewed_ids(args.manual_review_path)
        source_rows = [row for row in source_rows if (row.get("paper_id") or "").strip() not in reviewed_ids]

    selected_rows, available_counts, selected_counts = select_rows(
        source_rows,
        bucket_quotas=bucket_quotas,
        seed=args.seed,
    )
    reference_rows = load_reference_rows(args.references_csv)

    packet_paths: dict[str, str] = {}
    if args.text_output_dir is not None:
        packet_paths = write_text_packets(
            selected_rows,
            reference_rows=reference_rows,
            output_dir=args.text_output_dir,
        )

    if args.review_csv_path is not None:
        write_review_csv(
            args.review_csv_path,
            build_review_rows(selected_rows),
        )

    report = build_report(
        selected_rows=selected_rows,
        available_counts=available_counts,
        selected_counts=selected_counts,
        bucket_quotas=bucket_quotas,
        include_reviewed=args.include_reviewed,
        seed=args.seed,
    )
    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Selected {len(selected_rows)} source-categorisation review rows.")
    print(f"Bucket quotas: {bucket_quotas}")
    print(f"Available bucket counts: {available_counts}")
    print(f"Selected bucket counts: {report['selected_bucket_counts']}")
    print(f"Selected category counts: {report['selected_category_counts']}")
    print(f"Selected confidence counts: {report['selected_confidence_counts']}")


if __name__ == "__main__":
    main()
