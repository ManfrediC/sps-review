from __future__ import annotations

import csv
from pathlib import Path


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get(key_column) or "").strip()
            if key:
                rows[key] = row
    return rows


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def normalize_category_subtype(category: str, subtype: str) -> tuple[str, str]:
    category = (category or "").strip()
    subtype = (subtype or "").strip()
    subtype_aliases = {
        "case_report": ("single_case_report", "case_report"),
        "paraneoplastic_case_report": ("single_case_report", "paraneoplastic_case_report"),
        "single_case_conference_abstract": ("conference_abstract", "single_case_conference_abstract"),
        "case_series_conference_abstract": ("conference_abstract", "case_series_conference_abstract"),
        "group_conference_abstract": ("conference_abstract", "group_conference_abstract"),
        "group_or_frequency_focused_lab_clinical_study": (
            "lab_heavy_clinical_or_translational",
            "group_or_frequency_focused_lab_clinical_study",
        ),
    }
    return subtype_aliases.get(category, (category, subtype if subtype else ""))


def infer_mode(category: str, subtype: str) -> str:
    category, subtype = normalize_category_subtype(category, subtype)
    if category == "single_case_report":
        return "individual"
    if category == "case_series_or_multi_case":
        return "individual_case_split"
    if category == "conference_abstract":
        if subtype == "single_case_conference_abstract":
            return "individual"
        if subtype == "case_series_conference_abstract":
            return "individual_case_split"
        if subtype == "group_conference_abstract":
            return "group"
        return "individual"
    if category in {"observational_group_study", "interventional_study", "lab_heavy_clinical_or_translational"}:
        return "group"
    if category in {"non_clinical_basic_science", "review_article"}:
        return "skip"
    return "manual_review"


def infer_eligibility(category: str, subtype: str) -> bool:
    return infer_mode(category, subtype) not in {"skip", "manual_review"}


def infer_case_split_candidate(category: str, subtype: str) -> bool:
    category, subtype = normalize_category_subtype(category, subtype)
    return category == "case_series_or_multi_case" or subtype == "case_series_conference_abstract"


def resolve_source_row(
    paper_id: str,
    heuristic_row: dict[str, str] | None,
    manual_row: dict[str, str] | None,
) -> dict[str, str]:
    heuristic_row = heuristic_row or {}
    manual_row = manual_row or {}
    manual_present = bool(manual_row)
    if manual_present:
        category = (manual_row.get("final_source_category") or "").strip()
        subtype = (manual_row.get("final_source_subtype") or "").strip()
        confidence = "reviewed"
        route_source = "manual_review"
        notes = (manual_row.get("review_decision_notes") or "").strip()
        alignment_tag = (manual_row.get("pdf_content_alignment_tag") or "").strip()
        review_batch = (manual_row.get("review_batch") or "").strip()
        reviewed_at_utc = (manual_row.get("reviewed_at_utc") or "").strip()
    else:
        category = (heuristic_row.get("source_category") or "").strip()
        subtype = (heuristic_row.get("source_subtype") or "").strip()
        confidence = (heuristic_row.get("classification_confidence") or "").strip()
        route_source = "heuristic"
        notes = (heuristic_row.get("categorisation_reason") or "").strip()
        alignment_tag = ""
        review_batch = ""
        reviewed_at_utc = ""

    category, subtype = normalize_category_subtype(category, subtype)
    mode = infer_mode(category, subtype)
    return {
        "paper_id": paper_id,
        "manual_override_present": bool_text(manual_present),
        "resolved_source_category": category,
        "resolved_source_subtype": subtype,
        "resolved_source_confidence": confidence,
        "resolved_source_route_source": route_source,
        "resolved_source_notes": notes,
        "resolved_source_alignment_tag": alignment_tag,
        "resolved_review_batch": review_batch,
        "resolved_reviewed_at_utc": reviewed_at_utc,
        "resolved_case_series_split_candidate": bool_text(infer_case_split_candidate(category, subtype)),
        "resolved_langextract_mode": mode,
        "resolved_langextract_eligible": bool_text(infer_eligibility(category, subtype)),
    }
