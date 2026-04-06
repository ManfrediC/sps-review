from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from src.validation import _stage04_gold as gold


REPO_ROOT = gold.REPO_ROOT
LLM_SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
LLM_COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_PATH = gold.ARTIFACT_REGISTRY_PATH
TRIM_REGISTRY_PATH = gold.TRIM_REGISTRY_PATH
LLM_ROUND_ROOT = REPO_ROOT / "qa" / "validation" / "source_categorisation" / "llm_category_review"
GOLD_MASTER_PATH = gold.GOLD_MASTER_PATH
DEFAULT_SEED = 20260405
DEFAULT_BUCKET_QUOTAS = {
    "conference_edge": 3,
    "case_group_boundary": 3,
    "review_lab_edge": 2,
    "high_confidence_control": 2,
}
SOURCE_CATEGORY_OPTIONS = gold.SOURCE_CATEGORY_OPTIONS
PDF_ALIGNMENT_OPTIONS = gold.PDF_ALIGNMENT_OPTIONS
ROUND_QUEUE_FILENAME = "selection_queue.csv"
ROUND_RESPONSES_FILENAME = "responses.csv"
ROUND_MANIFEST_FILENAME = "selection_manifest.json"
DEFAULT_REVIEWER = gold.DEFAULT_REVIEWER
CONFIDENCE_PRIORITY = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


display_path = gold.display_path
resolve_repo_path = gold.resolve_repo_path
load_text_page_entries = gold.load_text_page_entries
search_text_page_entries = gold.search_text_page_entries
parse_int = gold.parse_int
truthy = gold.truthy
count_completed_reviews = gold.count_completed_reviews


def now_utc_iso() -> str:
    return gold.now_utc_iso()


def discover_round_directories(root: Path = LLM_ROUND_ROOT) -> list[Path]:
    if not root.exists():
        return []
    round_dirs = [path for path in root.iterdir() if path.is_dir() and (path / ROUND_QUEUE_FILENAME).exists()]
    return sorted(round_dirs)


def next_round_directory(root: Path = LLM_ROUND_ROOT, date_label: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    day_label = date_label or gold.today_utc_label()
    prefix = f"stage04_llm_category_{day_label}"
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
    return round_dir / f"gold_standard_stage04_llm_category_{round_label_from_directory(round_dir)}.csv"


def first_pipe_separated_value(value: str) -> str:
    return gold.first_pipe_separated_value(value)


def preferred_start_page_for_paper(
    *,
    artifact_row: dict[str, str],
    trim_row: dict[str, str],
) -> int:
    return gold.preferred_start_page_for_paper(
        artifact_row=artifact_row,
        trim_row=trim_row,
    )


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    return gold.load_csv_rows(path)


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    return gold.load_csv_rows_by_id(path, key_column)


def conference_edge_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    proceedings_detected = truthy(row.get("proceedings_detected"))
    manual_review_required = truthy(row.get("manual_review_required"))
    preferred_text_source = (row.get("preferred_text_source") or "").strip()
    trim_status = (row.get("trim_status") or "").strip()

    signals: list[str] = []
    if category == "conference_abstract":
        signals.append("conference_predicted")
        if confidence != "high":
            signals.append("conference_non_high_confidence")
        if manual_review_required:
            signals.append("conference_manual_review_required")
        if preferred_text_source == "full_text":
            signals.append("conference_using_full_text")
        if trim_status and trim_status not in {"trimmed_auto", "not_needed"}:
            signals.append(f"conference_trim_status={trim_status}")
        return signals

    if proceedings_detected:
        signals.append("non_conference_with_proceedings_detected")
    if trim_status:
        signals.append(f"non_conference_trim_status={trim_status}")
    return signals


def case_group_boundary_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    manual_review_required = truthy(row.get("manual_review_required"))
    recommended_next_action = (row.get("recommended_next_action") or "").strip()
    contains_individual = truthy(row.get("contains_individual_level_data"))
    contains_group = truthy(row.get("contains_group_level_data"))

    if category not in {
        "single_case_report",
        "case_series_or_multi_case",
        "observational_group_study",
        "interventional_study",
        "lab_heavy_clinical_or_translational",
    }:
        return []

    signals: list[str] = []
    if confidence != "high":
        signals.append("group_boundary_non_high_confidence")
    if manual_review_required:
        signals.append("group_boundary_manual_review_required")
    if contains_individual and contains_group:
        signals.append("group_boundary_mixed_data_levels")
    if category in {
        "case_series_or_multi_case",
        "observational_group_study",
        "lab_heavy_clinical_or_translational",
    }:
        signals.append(f"group_boundary_category={category}")
    if recommended_next_action in {
        "split_cases_then_langextract",
        "review_source_category_then_split",
        "review_source_category_then_langextract",
    }:
        signals.append(f"group_boundary_action={recommended_next_action}")
    return signals


def review_lab_edge_signals(row: dict[str, str]) -> list[str]:
    category = (row.get("source_category") or "").strip()
    confidence = (row.get("classification_confidence") or "").strip()
    manual_review_required = truthy(row.get("manual_review_required"))
    reasoning = (row.get("categorisation_reason") or "").lower()

    if category not in {
        "review_article",
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
    if "review" in reasoning:
        signals.append("review_text_present")
    if any(token in reasoning for token in ("lab", "antibody", "assay", "science")):
        signals.append("lab_text_present")
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


def build_bucket_candidates(rows: list[dict[str, str]]) -> dict[str, list[tuple[dict[str, str], list[str]]]]:
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
    category = (row.get("source_category") or "").strip()
    return (
        0 if truthy(row.get("manual_review_required")) else 1,
        CONFIDENCE_PRIORITY.get(confidence, 1),
        -len(signals),
        0 if category == "unclear_manual_review" else 1,
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
            if not paper_id or paper_id in selected_ids:
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
                if paper_id and paper_id not in selected_ids:
                    remaining_candidates.append((row, signals, bucket_name))
        rng.shuffle(remaining_candidates)
        remaining_candidates.sort(key=lambda item: candidate_priority(item[0], item[1]))
        for row, signals, bucket_name in remaining_candidates:
            paper_id = (row.get("paper_id") or "").strip()
            if not paper_id or paper_id in selected_ids:
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

    selected.sort(key=lambda row: ((row.get("selection_bucket") or "").strip(), parse_int(row.get("paper_id"), default=10**9)))
    return selected, available_counts, selected_counts


def load_selection_source_rows(
    *,
    source_registry_path: Path = LLM_SOURCE_REGISTRY_PATH,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
    include_manual_reviewed: bool = False,
    exclude_gold_ids: bool = True,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    source_rows = load_csv_rows(source_registry_path)
    artifact_rows = load_csv_rows_by_id(artifact_registry_path, "paper_id")

    manual_reviewed_ids = set() if include_manual_reviewed else gold.load_manual_reviewed_ids()
    gold_ids = gold.load_existing_gold_ids() if exclude_gold_ids else set()

    filtered_rows: list[dict[str, str]] = []
    for row in source_rows:
        paper_id = (row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        if paper_id in manual_reviewed_ids or paper_id in gold_ids:
            continue

        artifact_row = artifact_rows.get(paper_id, {})
        if not truthy(artifact_row.get("pdf_present")):
            continue
        if not truthy(artifact_row.get("text_json_present")):
            continue
        if not first_pipe_separated_value(artifact_row.get("pdf_paths_relative")):
            continue

        filtered_rows.append(row)

    return filtered_rows, artifact_rows


def build_selection_queue_rows(
    selected_rows: list[dict[str, str]],
    *,
    artifact_rows: dict[str, dict[str, str]],
    count_rows: dict[str, dict[str, str]],
    trim_rows: dict[str, dict[str, str]],
    round_dir: Path,
) -> list[dict[str, str]]:
    round_id = round_label_from_directory(round_dir)
    created_at = now_utc_iso()
    queue_rows: list[dict[str, str]] = []
    for row in selected_rows:
        paper_id = (row.get("paper_id") or "").strip()
        artifact_row = artifact_rows.get(paper_id, {})
        count_row = count_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})
        selection_signals = [
            (row.get("selection_signals") or "").strip(),
            "prediction_origin=llm",
            f"prediction_version={(row.get('categorisation_version') or '').strip() or 'unknown'}",
        ]
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
                "selection_signals": "; ".join(signal for signal in selection_signals if signal),
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
                "predicted_likely_sps_case_count": (
                    (count_row.get("likely_sps_case_count") or "").strip()
                    or (row.get("likely_case_count") or "").strip()
                ),
                "predicted_count_confidence": (count_row.get("count_confidence") or "").strip(),
                "predicted_count_basis": (count_row.get("count_basis") or "").strip(),
                "predicted_count_manual_review_required": (
                    count_row.get("count_manual_review_required") or ""
                ).strip(),
                "predicted_count_reason": (count_row.get("count_reason") or "").strip(),
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
    source_registry_path: Path,
) -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "round_id": round_label_from_directory(round_dir),
        "round_dir": display_path(round_dir),
        "source_registry_path": display_path(source_registry_path),
        "seed": seed,
        "bucket_quotas": bucket_quotas,
        "available_bucket_counts": available_counts,
        "selected_primary_bucket_counts": selected_counts,
        "selected_bucket_counts": dict(Counter(row["selection_bucket"] for row in selected_rows)),
        "selected_category_counts": dict(Counter((row.get("source_category") or "").strip() for row in selected_rows)),
        "selected_confidence_counts": dict(
            Counter((row.get("classification_confidence") or "").strip() for row in selected_rows)
        ),
        "selected_rows": [
            {
                "paper_id": (row.get("paper_id") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "selection_bucket": (row.get("selection_bucket") or "").strip(),
                "selection_signals": (row.get("selection_signals") or "").strip(),
                "predicted_source_category": (row.get("predicted_source_category") or "").strip(),
                "predicted_confidence": (row.get("predicted_confidence") or "").strip(),
                "predicted_likely_sps_case_count": (
                    row.get("predicted_likely_sps_case_count") or ""
                ).strip(),
                "predicted_count_confidence": (row.get("predicted_count_confidence") or "").strip(),
            }
            for row in queue_rows
        ],
    }


def selection_queue_fieldnames() -> list[str]:
    return gold.selection_queue_fieldnames()


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


def ensure_empty_responses_file(round_dir: Path) -> Path:
    responses_path = round_dir / ROUND_RESPONSES_FILENAME
    if not responses_path.exists():
        gold.write_csv_rows(responses_path, [], response_fieldnames())
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
    reviewed_count = reviewed_extractable_sps_case_count.strip() or "0"
    predicted_count = predicted_count or reviewed_count
    final_category = predicted_source_category if prediction_correct else reviewed_source_category.strip()
    final_count = predicted_count if prediction_correct else reviewed_count
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


def response_has_complete_review(response_row: dict[str, str]) -> bool:
    if (response_row.get("review_status") or "").strip() != "reviewed":
        return False
    if not (response_row.get("reviewed_source_category") or "").strip():
        return False
    return (response_row.get("reviewed_extractable_sps_case_count") or "").strip() != ""


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
                "review_status": (
                    "reviewed" if response_has_complete_review(response_row) else "pending"
                ),
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
    gold.write_csv_rows(round_dir / ROUND_RESPONSES_FILENAME, ordered_responses, response_fieldnames())
    snapshot_rows = build_gold_snapshot_rows(queue_rows, responses_by_id)
    gold.write_csv_rows(round_gold_snapshot_path(round_dir), snapshot_rows, gold.gold_fieldnames())
    return snapshot_rows


def upsert_gold_master(snapshot_rows: list[dict[str, str]], master_path: Path = GOLD_MASTER_PATH) -> list[dict[str, str]]:
    return gold.upsert_gold_master(snapshot_rows, master_path=master_path)
