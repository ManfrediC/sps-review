"""Registry CSV reader/writer for LLM-based source categorisation.

Reads and writes the ``source_categorisation_registry.csv`` schema so that
downstream stages can consume LLM output identically to heuristic output.
"""

from __future__ import annotations

import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Field order — must match the existing heuristic registry schema
# ---------------------------------------------------------------------------

REGISTRY_FIELDNAMES: list[str] = [
    "paper_id",
    "covidence_id",
    "title",
    "authors",
    "published_year",
    "journal",
    "tags",
    "notes",
    "text_json_path",
    "preferred_text_json_path",
    "preferred_text_source",
    "proceedings_detected",
    "trim_status",
    "source_category",
    "source_subtype",
    "classification_confidence",
    "likely_case_count",
    "contains_individual_level_data",
    "contains_group_level_data",
    "case_series_split_candidate",
    "preferred_langextract_mode",
    "langextract_eligible",
    "manual_review_required",
    "recommended_next_action",
    "conference_marker_hits",
    "review_marker_hits",
    "case_report_marker_hits",
    "multi_case_marker_hits",
    "observational_marker_hits",
    "interventional_marker_hits",
    "non_clinical_marker_hits",
    "translational_marker_hits",
    "patient_label_count",
    "categorisation_reason",
    "categorisation_version",
    "categorised_at_utc",
]


def write_registry(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write classification rows to a CSV matching the registry schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    """Load CSV rows keyed by *key_column*."""
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
