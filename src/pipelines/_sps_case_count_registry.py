from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_counting import (
    CaseCountEstimate,
    estimate_sps_case_count,
    has_explicit_multi_case_signal,
    has_single_case_signal,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
ADMINISTRATIVE_DATASET_MARKERS = (
    "nationwide readmission study",
    "nationwide study",
    "national inpatient sample",
    "inpatient care",
    "readmission study",
    "administrative database",
    "hospital discharge database",
    "claims database",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def record_text_window(record: dict[str, Any], *, use_all_pages: bool) -> str:
    pages = record.get("pages") or []
    selected = pages if use_all_pages else pages[:5]
    return "\n".join(str(page.get("text") or "") for page in selected)


def title_localised_window(
    text: str,
    title: str,
    *,
    min_prefix_skip: int = 1200,
    leading_chars: int = 200,
    trailing_chars: int = 4500,
) -> str:
    normalized_text = normalize_text(text)
    normalized_title = normalize_text(title)
    if not normalized_text or not normalized_title:
        return normalized_text

    title_tokens = normalized_title.split()
    for anchor_size in (12, 10, 8, 6):
        if len(title_tokens) < anchor_size:
            continue
        anchor = " ".join(title_tokens[:anchor_size])
        index = normalized_text.find(anchor)
        if index < 0:
            continue
        if index < min_prefix_skip:
            return normalized_text
        start = max(0, index - leading_chars)
        end = min(len(normalized_text), index + len(anchor) + trailing_chars)
        return normalized_text[start:end]
    return normalized_text


def prefer_single_case_default(
    *,
    source_category: str,
    source_subtype: str,
    title: str,
    abstract: str,
    early_body_text: str,
) -> bool:
    if source_category == "single_case_report":
        return True
    if source_subtype == "single_case_conference_abstract":
        return True
    explicit_multi_case = has_explicit_multi_case_signal(" ".join([title, abstract]))
    if explicit_multi_case:
        return False
    text_for_signal = " ".join([title, abstract, early_body_text[:1200]])
    return has_single_case_signal(text_for_signal)


def adjust_estimate_for_source_context(
    *,
    estimate: CaseCountEstimate,
    title: str,
    abstract: str,
    early_body_text: str,
    source_category: str,
    source_subtype: str,
    preferred_text_source: str,
) -> CaseCountEstimate:
    context_text = " ".join([title, abstract, early_body_text[:1200]]).lower()
    explicit_single_case = has_single_case_signal(context_text)
    if any(marker in context_text for marker in ADMINISTRATIVE_DATASET_MARKERS):
        return CaseCountEstimate(
            likely_case_count=0,
            count_confidence="low",
            count_basis="administrative_dataset_not_extractable",
            manual_review_required=False,
        )

    single_case_default_ok = prefer_single_case_default(
        source_category=source_category,
        source_subtype=source_subtype,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )

    if source_category == "conference_abstract" and preferred_text_source == "full_text":
        if estimate.count_basis in {"patient_label_count", "early_body_count_signal"}:
            estimate = estimate_sps_case_count(title=title, abstract=abstract, early_body_text="")

    if single_case_default_ok and estimate.likely_case_count == 0:
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="source_single_case_default",
            manual_review_required=False,
        )

    if (
        single_case_default_ok
        and estimate.likely_case_count > 1
        and estimate.count_basis in {"abstract_count_signal", "early_body_count_signal", "patient_label_count"}
    ):
        return CaseCountEstimate(
            likely_case_count=1,
            count_confidence="medium",
            count_basis="source_single_case_override",
            manual_review_required=False,
        )

    if source_category == "lab_heavy_clinical_or_translational":
        if estimate.count_basis == "abstract_count_signal":
            body_only_estimate = estimate_sps_case_count(
                title=title,
                abstract="",
                early_body_text=early_body_text,
            )
            if body_only_estimate.likely_case_count > 0 and body_only_estimate.likely_case_count < estimate.likely_case_count:
                estimate = body_only_estimate
        diagnosis_specific_basis = estimate.count_basis.startswith("diagnosis_specific_")
        explicit_multi_case = has_explicit_multi_case_signal(" ".join([title, abstract]))
        strong_group_basis = (
            estimate.count_basis in {
                "title_count_signal",
                "abstract_count_signal",
                "early_body_count_signal",
                "patient_label_count",
            }
            and estimate.likely_case_count >= 3
        )
        if not (diagnosis_specific_basis or (explicit_multi_case and strong_group_basis)):
            return CaseCountEstimate(
                likely_case_count=0,
                count_confidence="low",
                count_basis="lab_context_no_extractable_count",
                manual_review_required=False,
            )

    if source_category == "review_article" and explicit_single_case and estimate.likely_case_count == 1:
        return estimate

    if (
        source_category == "observational_group_study"
        and estimate.count_basis == "patient_label_count"
        and estimate.likely_case_count <= 2
    ):
        title_text = title.lower()
        if not any(marker in title_text for marker in ("stiff", "sps", "sms")) and any(
            marker in context_text for marker in ("autoantigen", "serologic", "serological evaluation")
        ):
            return CaseCountEstimate(
                likely_case_count=0,
                count_confidence="low",
                count_basis="observational_context_no_extractable_sps_count",
                manual_review_required=False,
            )

    return estimate


def build_case_count_record(
    *,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any],
    preferred_path: Path,
    source_row: dict[str, str],
    count_version: str = "heuristic_v1",
) -> dict[str, str]:
    title = (reference_row.get("Title") or "").strip()
    abstract = (reference_row.get("Abstract") or "").strip()
    authors = (reference_row.get("Authors") or "").strip()
    early_body_text = title_localised_window(
        record_text_window(preferred_record, use_all_pages=not abstract.strip()),
        title,
    )
    estimate = estimate_sps_case_count(
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
    )
    preferred_text_source = "trimmed" if preferred_path.parent == TEXT_TRIMMED_DIR else "full_text"
    source_category = (source_row.get("source_category") or "").strip()
    source_subtype = (source_row.get("source_subtype") or "").strip()
    estimate = adjust_estimate_for_source_context(
        estimate=estimate,
        title=title,
        abstract=abstract,
        early_body_text=early_body_text,
        source_category=source_category,
        source_subtype=source_subtype,
        preferred_text_source=preferred_text_source,
    )
    eligible_categories = {
        "single_case_report",
        "case_series_or_multi_case",
        "observational_group_study",
        "interventional_study",
        "lab_heavy_clinical_or_translational",
        "conference_abstract",
    }
    count_eligible = source_category in eligible_categories
    review_single_case_override = (
        source_category == "review_article"
        and estimate.likely_case_count == 1
        and has_single_case_signal(" ".join([title, abstract, early_body_text[:1200]]))
    )
    if source_category in {"review_article", "non_clinical_basic_science"} and not review_single_case_override:
        estimate = CaseCountEstimate(
            likely_case_count=0,
            count_confidence="low",
            count_basis="not_count_eligible",
            manual_review_required=False,
        )
    manual_review_required = count_eligible and estimate.manual_review_required

    reasons = [
        f"count_basis={estimate.count_basis}",
        f"count_confidence={estimate.count_confidence}",
    ]
    if source_category:
        reasons.append(f"source_category={source_category}")

    return {
        "paper_id": str(text_record.get("paper_id") or Path(str(text_record.get("_path") or "")).stem),
        "covidence_id": (reference_row.get("Covidence") or "").strip(),
        "title": title,
        "authors": authors,
        "source_category": source_category,
        "source_subtype": source_subtype,
        "preferred_text_json_path": relative_to_repo(preferred_path),
        "preferred_text_source": preferred_text_source,
        "count_eligible": bool_text(count_eligible),
        "likely_sps_case_count": str(estimate.likely_case_count),
        "count_confidence": estimate.count_confidence,
        "count_basis": estimate.count_basis,
        "count_manual_review_required": bool_text(manual_review_required),
        "count_reason": " | ".join(reasons),
        "count_version": count_version,
        "counted_at_utc": now_utc_iso(),
    }


def count_row_fieldnames() -> list[str]:
    return [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_category",
        "source_subtype",
        "preferred_text_json_path",
        "preferred_text_source",
        "count_eligible",
        "likely_sps_case_count",
        "count_confidence",
        "count_basis",
        "count_manual_review_required",
        "count_reason",
        "count_version",
        "counted_at_utc",
    ]


def write_count_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=count_row_fieldnames())
        writer.writeheader()
        writer.writerows(rows)
