from __future__ import annotations

import csv
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.validation.build_source_categorisation_review_sample import (
    attach_case_count_fields,
    candidate_priority,
    case_group_boundary_signals,
    conference_edge_signals,
    high_confidence_control_signals,
    review_lab_edge_signals,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
ARTIFACT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"
TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
CASE_REPORT_FORM_CSV = REPO_ROOT / "examples" / "datasheet_examples_MC_Case_Report_Form.csv"
GOLD_STANDARD_ROOT = REPO_ROOT / "qa" / "validation" / "source_categorisation" / "gold_standard"
GOLD_MASTER_PATH = GOLD_STANDARD_ROOT / "stage04_gold_standard_master.csv"
DEFAULT_SEED = 20260405
DEFAULT_BUCKET_QUOTAS = {
    "conference_edge": 2,
    "case_group_boundary": 2,
    "review_lab_edge": 2,
    "count_ambiguity": 2,
    "high_confidence_control": 2,
}
SOURCE_CATEGORY_OPTIONS = (
    "single_case_report",
    "case_series_or_multi_case",
    "observational_group_study",
    "interventional_study",
    "conference_abstract",
    "lab_heavy_clinical_or_translational",
    "non_clinical_basic_science",
    "review_article",
    "unclear_manual_review",
)
PDF_ALIGNMENT_OPTIONS = (
    "appears_matched",
    "uncertain",
    "likely_wrong_pdf_attached",
    "incorrect_reference",
)
ROUND_QUEUE_FILENAME = "selection_queue.csv"
ROUND_RESPONSES_FILENAME = "responses.csv"
ROUND_MANIFEST_FILENAME = "selection_manifest.json"
DEFAULT_REVIEWER = "human_reviewer"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_utc_label() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


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


def first_pipe_separated_value(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split("|")]
    return next((part for part in parts if part), "")


def load_example_reference_ids(path: Path = CASE_REPORT_FORM_CSV) -> set[str]:
    ids: set[str] = set()
    for row in load_csv_rows(path):
        reference_id = (row.get("Reference") or "").strip()
        if reference_id:
            ids.add(reference_id)
    return ids


def load_manual_reviewed_ids(path: Path = MANUAL_REVIEW_PATH) -> set[str]:
    return {
        (row.get("paper_id") or "").strip()
        for row in load_csv_rows(path)
        if (row.get("paper_id") or "").strip()
    }


def discover_round_directories(root: Path = GOLD_STANDARD_ROOT) -> list[Path]:
    if not root.exists():
        return []
    round_dirs = [path for path in root.iterdir() if path.is_dir() and (path / ROUND_QUEUE_FILENAME).exists()]
    return sorted(round_dirs)


def load_gold_round_ids(root: Path = GOLD_STANDARD_ROOT) -> set[str]:
    paper_ids: set[str] = set()
    for round_dir in discover_round_directories(root):
        for row in load_csv_rows(round_dir / ROUND_QUEUE_FILENAME):
            paper_id = (row.get("paper_id") or "").strip()
            if paper_id:
                paper_ids.add(paper_id)
    return paper_ids


def load_gold_master_ids(path: Path = GOLD_MASTER_PATH) -> set[str]:
    return {
        (row.get("paper_id") or "").strip()
        for row in load_csv_rows(path)
        if (row.get("paper_id") or "").strip()
    }


def load_existing_gold_ids(root: Path = GOLD_STANDARD_ROOT, master_path: Path = GOLD_MASTER_PATH) -> set[str]:
    return load_gold_round_ids(root) | load_gold_master_ids(master_path)


def count_ambiguity_signals(row: dict[str, str]) -> list[str]:
    if not truthy(row.get("count_eligible")):
        return []

    source_category = (row.get("source_category") or "").strip()
    count_confidence = (row.get("count_confidence") or "").strip()
    count_basis = (row.get("count_basis") or "").strip()
    likely_case_count = parse_int(row.get("likely_case_count"))
    patient_label_count = parse_int(row.get("patient_label_count"))

    signals: list[str] = []
    if truthy(row.get("count_manual_review_required")):
        signals.append("count_manual_review_required")
    if count_confidence != "high":
        signals.append("count_non_high_confidence")
    if likely_case_count == 0 and source_category in {
        "single_case_report",
        "case_series_or_multi_case",
        "conference_abstract",
    }:
        signals.append("count_zero_for_extractable_source")
    if patient_label_count >= 2 and likely_case_count != patient_label_count:
        signals.append("count_differs_from_patient_labels")
    if source_category == "single_case_report" and likely_case_count not in {0, 1}:
        signals.append("single_case_with_multi_count")
    if count_basis in {
        "patient_label_count",
        "early_body_count_signal",
        "single_case_text_signal",
        "case_report_marker_single_case",
        "source_single_case_override",
    }:
        signals.append(f"count_basis={count_basis}")
    return signals


def build_bucket_candidates(rows: list[dict[str, str]]) -> dict[str, list[tuple[dict[str, str], list[str]]]]:
    buckets = {
        "conference_edge": [],
        "case_group_boundary": [],
        "review_lab_edge": [],
        "count_ambiguity": [],
        "high_confidence_control": [],
    }
    for row in rows:
        if signals := conference_edge_signals(row):
            buckets["conference_edge"].append((row, signals))
        if signals := case_group_boundary_signals(row):
            buckets["case_group_boundary"].append((row, signals))
        if signals := review_lab_edge_signals(row):
            buckets["review_lab_edge"].append((row, signals))
        if signals := count_ambiguity_signals(row):
            buckets["count_ambiguity"].append((row, signals))
        if signals := high_confidence_control_signals(row):
            buckets["high_confidence_control"].append((row, signals))
    return buckets


def prioritise_candidates(
    candidates: list[tuple[dict[str, str], list[str]]],
    *,
    rng: random.Random,
) -> list[tuple[dict[str, str], list[str]]]:
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda item: candidate_priority(item[0], item[1]))


def select_gold_rows(
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
                    "selection_signals": "; ".join(signals),
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
                    "selection_signals": "; ".join(signals),
                }
            )
            if len(selected) >= target_total:
                break

    selected.sort(key=lambda row: (row["selection_bucket"], parse_int(row.get("paper_id"), default=10**9)))
    return selected, available_counts, selected_counts


def next_round_directory(root: Path = GOLD_STANDARD_ROOT, date_label: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    prefix = date_label or today_utc_label()
    existing = [path.name for path in root.iterdir() if path.is_dir() and path.name.startswith(f"{prefix}_round_")]
    highest = 0
    for name in existing:
        suffix = name.split("_round_")[-1]
        try:
            highest = max(highest, int(suffix))
        except ValueError:
            continue
    return root / f"{prefix}_round_{highest + 1:02d}"


def round_label_from_directory(round_dir: Path) -> str:
    return round_dir.name


def round_gold_snapshot_path(round_dir: Path) -> Path:
    return round_dir / f"gold_standard_stage04_{round_label_from_directory(round_dir)}.csv"


def load_selection_source_rows(
    *,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    count_registry_path: Path = COUNT_REGISTRY_PATH,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
    include_manual_reviewed: bool = False,
    exclude_example_ids: bool = True,
    exclude_gold_ids: bool = True,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    source_rows = load_csv_rows(source_registry_path)
    count_rows = load_csv_rows_by_id(count_registry_path, "paper_id")
    artifact_rows = load_csv_rows_by_id(artifact_registry_path, "paper_id")

    rows_with_count: list[dict[str, str]] = []
    for row in source_rows:
        paper_id = (row.get("paper_id") or "").strip()
        count_row = count_rows.get(paper_id, {})
        enriched_row = attach_case_count_fields(row, count_row=count_row)
        enriched_row["count_eligible"] = (count_row.get("count_eligible") or "").strip()
        rows_with_count.append(enriched_row)

    example_ids = load_example_reference_ids() if exclude_example_ids else set()
    manual_reviewed_ids = set() if include_manual_reviewed else load_manual_reviewed_ids()
    gold_ids = load_existing_gold_ids() if exclude_gold_ids else set()

    filtered_rows: list[dict[str, str]] = []
    for row in rows_with_count:
        paper_id = (row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if paper_id in example_ids or paper_id in manual_reviewed_ids or paper_id in gold_ids:
            continue

        artifact_row = artifact_rows.get(paper_id, {})
        if not truthy(artifact_row.get("pdf_present")):
            continue
        if not truthy(artifact_row.get("text_json_present")):
            continue
        if not first_pipe_separated_value(artifact_row.get("pdf_paths_relative")):
            continue

        filtered_rows.append(row)

    return filtered_rows, count_rows, artifact_rows


def preferred_start_page_for_paper(
    *,
    artifact_row: dict[str, str],
    trim_row: dict[str, str],
) -> int:
    for value in (
        artifact_row.get("text_trim_start_page"),
        trim_row.get("start_page_index"),
    ):
        page_index = parse_int(value, default=-1)
        if page_index >= 0:
            return page_index + 1
    return 1


def build_selection_queue_rows(
    selected_rows: list[dict[str, str]],
    *,
    artifact_rows: dict[str, dict[str, str]],
    trim_rows: dict[str, dict[str, str]],
    round_dir: Path,
) -> list[dict[str, str]]:
    round_id = round_label_from_directory(round_dir)
    created_at = now_utc_iso()
    queue_rows: list[dict[str, str]] = []
    for row in selected_rows:
        paper_id = (row.get("paper_id") or "").strip()
        artifact_row = artifact_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})
        queue_rows.append(
            {
                "round_id": round_id,
                "paper_id": paper_id,
                "covidence_id": (row.get("covidence_id") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "authors": (row.get("authors") or "").strip(),
                "published_year": (row.get("published_year") or "").strip(),
                "journal": (row.get("journal") or "").strip(),
                "selection_bucket": (row.get("selection_bucket") or "").strip(),
                "selection_signals": (row.get("selection_signals") or "").strip(),
                "pdf_filename": first_pipe_separated_value(artifact_row.get("pdf_filenames")),
                "pdf_path_relative": first_pipe_separated_value(artifact_row.get("pdf_paths_relative")),
                "preferred_text_json_path": (row.get("preferred_text_json_path") or "").strip(),
                "preferred_text_source": (row.get("preferred_text_source") or "").strip(),
                "preferred_start_page": str(
                    preferred_start_page_for_paper(
                        artifact_row=artifact_row,
                        trim_row=trim_row,
                    )
                ),
                "proceedings_detected": (row.get("proceedings_detected") or "").strip(),
                "trim_status": (row.get("trim_status") or "").strip(),
                "predicted_source_category": (row.get("source_category") or "").strip(),
                "predicted_source_subtype": (row.get("source_subtype") or "").strip(),
                "predicted_confidence": (row.get("classification_confidence") or "").strip(),
                "predicted_likely_sps_case_count": (row.get("likely_case_count") or "").strip(),
                "predicted_count_confidence": (row.get("count_confidence") or "").strip(),
                "predicted_count_basis": (row.get("count_basis") or "").strip(),
                "predicted_count_manual_review_required": (row.get("count_manual_review_required") or "").strip(),
                "predicted_count_reason": (row.get("count_reason") or "").strip(),
                "predicted_categorisation_reason": (row.get("categorisation_reason") or "").strip(),
                "selection_created_at_utc": created_at,
            }
        )
    return queue_rows


def build_selection_manifest(
    *,
    round_dir: Path,
    selected_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    bucket_quotas: dict[str, int],
    available_counts: dict[str, int],
    selected_counts: dict[str, int],
    seed: int,
) -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "round_id": round_label_from_directory(round_dir),
        "round_dir": display_path(round_dir),
        "seed": seed,
        "bucket_quotas": bucket_quotas,
        "available_bucket_counts": available_counts,
        "selected_primary_bucket_counts": selected_counts,
        "selected_bucket_counts": dict(Counter(row["selection_bucket"] for row in selected_rows)),
        "selected_category_counts": dict(Counter(row["source_category"] for row in selected_rows)),
        "selected_count_confidence_counts": dict(
            Counter((row.get("count_confidence") or "").strip() for row in selected_rows)
        ),
        "selected_rows": [
            {
                "paper_id": (row.get("paper_id") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "selection_bucket": (row.get("selection_bucket") or "").strip(),
                "selection_signals": (row.get("selection_signals") or "").strip(),
                "predicted_source_category": (row.get("source_category") or "").strip(),
                "predicted_likely_sps_case_count": (row.get("likely_case_count") or "").strip(),
            }
            for row in queue_rows
        ],
    }


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def selection_queue_fieldnames() -> list[str]:
    return [
        "round_id",
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "published_year",
        "journal",
        "selection_bucket",
        "selection_signals",
        "pdf_filename",
        "pdf_path_relative",
        "preferred_text_json_path",
        "preferred_text_source",
        "preferred_start_page",
        "proceedings_detected",
        "trim_status",
        "predicted_source_category",
        "predicted_source_subtype",
        "predicted_confidence",
        "predicted_likely_sps_case_count",
        "predicted_count_confidence",
        "predicted_count_basis",
        "predicted_count_manual_review_required",
        "predicted_count_reason",
        "predicted_categorisation_reason",
        "selection_created_at_utc",
    ]


def response_fieldnames() -> list[str]:
    return [
        "round_id",
        "paper_id",
        "title",
        "selection_bucket",
        "prediction_correct",
        "reviewed_source_category",
        "reviewed_extractable_sps_case_count",
        "pdf_content_alignment_tag",
        "reviewer_notes",
        "reviewer_id",
        "review_status",
        "reviewed_at_utc",
    ]


def gold_fieldnames() -> list[str]:
    return [
        "round_id",
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "published_year",
        "journal",
        "selection_bucket",
        "selection_signals",
        "pdf_filename",
        "pdf_path_relative",
        "preferred_text_json_path",
        "preferred_text_source",
        "preferred_start_page",
        "proceedings_detected",
        "trim_status",
        "predicted_source_category",
        "predicted_source_subtype",
        "predicted_confidence",
        "predicted_likely_sps_case_count",
        "predicted_count_confidence",
        "predicted_count_basis",
        "predicted_count_manual_review_required",
        "predicted_count_reason",
        "predicted_categorisation_reason",
        "selection_created_at_utc",
        "prediction_correct",
        "review_status",
        "reviewed_source_category",
        "reviewed_extractable_sps_case_count",
        "pdf_content_alignment_tag",
        "reviewer_notes",
        "reviewer_id",
        "reviewed_at_utc",
    ]


def ensure_empty_responses_file(round_dir: Path) -> Path:
    responses_path = round_dir / ROUND_RESPONSES_FILENAME
    if not responses_path.exists():
        write_csv_rows(responses_path, [], response_fieldnames())
    return responses_path


def load_round_queue_rows(round_dir: Path) -> list[dict[str, str]]:
    return load_csv_rows(round_dir / ROUND_QUEUE_FILENAME)


def load_round_responses_by_id(round_dir: Path) -> dict[str, dict[str, str]]:
    return load_csv_rows_by_id(round_dir / ROUND_RESPONSES_FILENAME, "paper_id")


def build_response_row(
    *,
    queue_row: dict[str, str],
    prediction_correct: bool,
    reviewed_source_category: str,
    reviewed_extractable_sps_case_count: str,
    pdf_content_alignment_tag: str,
    reviewer_notes: str,
    reviewer_id: str,
) -> dict[str, str]:
    predicted_source_category = (queue_row.get("predicted_source_category") or "").strip()
    predicted_count = (queue_row.get("predicted_likely_sps_case_count") or "").strip()
    final_category = predicted_source_category if prediction_correct else reviewed_source_category.strip()
    final_count = predicted_count if prediction_correct else reviewed_extractable_sps_case_count.strip()
    return {
        "round_id": (queue_row.get("round_id") or "").strip(),
        "paper_id": (queue_row.get("paper_id") or "").strip(),
        "title": (queue_row.get("title") or "").strip(),
        "selection_bucket": (queue_row.get("selection_bucket") or "").strip(),
        "prediction_correct": "true" if prediction_correct else "false",
        "reviewed_source_category": final_category,
        "reviewed_extractable_sps_case_count": final_count,
        "pdf_content_alignment_tag": pdf_content_alignment_tag.strip(),
        "reviewer_notes": reviewer_notes.strip(),
        "reviewer_id": reviewer_id.strip() or DEFAULT_REVIEWER,
        "review_status": "reviewed",
        "reviewed_at_utc": now_utc_iso(),
    }


def build_gold_snapshot_rows(
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    snapshot_rows: list[dict[str, str]] = []
    for queue_row in queue_rows:
        paper_id = (queue_row.get("paper_id") or "").strip()
        response_row = responses_by_id.get(paper_id, {})
        snapshot_rows.append(
            {
                **queue_row,
                "prediction_correct": (response_row.get("prediction_correct") or "").strip(),
                "review_status": (response_row.get("review_status") or "pending").strip(),
                "reviewed_source_category": (response_row.get("reviewed_source_category") or "").strip(),
                "reviewed_extractable_sps_case_count": (
                    response_row.get("reviewed_extractable_sps_case_count") or ""
                ).strip(),
                "pdf_content_alignment_tag": (response_row.get("pdf_content_alignment_tag") or "").strip(),
                "reviewer_notes": (response_row.get("reviewer_notes") or "").strip(),
                "reviewer_id": (response_row.get("reviewer_id") or "").strip(),
                "reviewed_at_utc": (response_row.get("reviewed_at_utc") or "").strip(),
            }
        )
    return snapshot_rows


def count_completed_reviews(snapshot_rows: list[dict[str, str]]) -> int:
    return sum(1 for row in snapshot_rows if (row.get("review_status") or "").strip() == "reviewed")


def write_round_outputs(
    *,
    round_dir: Path,
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    ordered_responses = [
        responses_by_id[paper_id]
        for paper_id in [(row.get("paper_id") or "").strip() for row in queue_rows]
        if paper_id in responses_by_id
    ]
    write_csv_rows(round_dir / ROUND_RESPONSES_FILENAME, ordered_responses, response_fieldnames())
    snapshot_rows = build_gold_snapshot_rows(queue_rows, responses_by_id)
    write_csv_rows(round_gold_snapshot_path(round_dir), snapshot_rows, gold_fieldnames())
    return snapshot_rows


def upsert_gold_master(snapshot_rows: list[dict[str, str]], master_path: Path = GOLD_MASTER_PATH) -> list[dict[str, str]]:
    completed_rows = [row for row in snapshot_rows if (row.get("review_status") or "").strip() == "reviewed"]
    existing_rows = load_csv_rows(master_path)
    merged_by_round_and_id: dict[tuple[str, str], dict[str, str]] = {}
    for row in existing_rows:
        key = ((row.get("round_id") or "").strip(), (row.get("paper_id") or "").strip())
        if key[0] and key[1]:
            merged_by_round_and_id[key] = row
    for row in completed_rows:
        key = ((row.get("round_id") or "").strip(), (row.get("paper_id") or "").strip())
        if key[0] and key[1]:
            merged_by_round_and_id[key] = row
    merged_rows = sorted(
        merged_by_round_and_id.values(),
        key=lambda row: ((row.get("round_id") or "").strip(), parse_int(row.get("paper_id"), default=10**9)),
    )
    write_csv_rows(master_path, merged_rows, gold_fieldnames())
    return merged_rows


def reviewed_gold_rows_from_path(path: Path) -> list[dict[str, str]]:
    return [row for row in load_csv_rows(path) if (row.get("review_status") or "").strip() == "reviewed"]


def resolve_round_dir_from_text(path_text: str) -> Path:
    round_dir = resolve_repo_path(path_text)
    if not round_dir.exists():
        raise FileNotFoundError(f"Round directory does not exist: {round_dir}")
    return round_dir
