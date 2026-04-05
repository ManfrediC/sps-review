from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._sps_case_counting import (
    CaseCountEstimate,
    estimate_sps_case_count,
    has_explicit_multi_case_signal,
    has_single_case_signal,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
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


def load_text_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def collect_text_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


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

    if (
        single_case_default_ok
        and estimate.likely_case_count == 0
    ):
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
        explicit_multi_case = has_explicit_multi_case_signal(" ".join([title, abstract]))
        diagnosis_specific_basis = estimate.count_basis.startswith("diagnosis_specific_")
        strong_group_basis = (
            estimate.count_basis in {"title_count_signal", "abstract_count_signal", "early_body_count_signal", "patient_label_count"}
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
        "count_version": "heuristic_v1",
        "counted_at_utc": now_utc_iso(),
    }


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate extractable SPS case counts as a separate post-categorisation stage."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--source-registry-path", type=Path, default=SOURCE_REGISTRY_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to process.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of papers to process.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing the count registry.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    source_rows = load_csv_rows_by_id(args.source_registry_path, "paper_id")

    rows: list[dict[str, str]] = []
    for text_path in collect_text_paths(args.input_dir, args.paper_id, args.limit):
        paper_id = text_path.stem
        preferred_path = args.trimmed_dir / text_path.name
        if not preferred_path.exists():
            preferred_path = text_path
        rows.append(
            build_case_count_record(
                reference_row=reference_rows.get(paper_id, {}),
                text_record=load_text_record(text_path),
                preferred_record=load_text_record(preferred_path),
                preferred_path=preferred_path,
                source_row=source_rows.get(paper_id, {}),
            )
        )

    write_rows(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
