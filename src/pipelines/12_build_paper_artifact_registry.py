from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _source_routing import resolve_source_row


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_PRECLEAN_DIR = REPO_ROOT / "data" / "extraction_json" / "text_preclean"
TEXT_PRECLEAN_STAGE2_DIR = REPO_ROOT / "data" / "extraction_json" / "text_preclean_stage2"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
CASE_SERIES_SPLIT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_case_series_split"
LANGEXTRACT_DIR = REPO_ROOT / "data" / "extraction_json" / "langextract"
SUMMARY_DIR = REPO_ROOT / "data" / "extraction_json" / "summary"
QUALITY_RAW_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "raw"
QUALITY_RECORD_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "records"
COVIENCE_MANIFEST_PATH = REPO_ROOT / "data" / "extraction_json" / "covidence" / "download_manifest.jsonl"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_CASE_COUNT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
PROCEEDINGS_QC_PATH = REPO_ROOT / "data" / "references" / "proceedings_text_qc_registry.csv"
CASE_SERIES_SPLIT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "case_series_split_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"


# Build now utc iso.
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Convert a path to a repository-relative string.
def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


# Build bool text.
def bool_text(value: bool) -> str:
    return "true" if value else "false"


# Join values.
def join_values(values: list[str]) -> str:
    return " | ".join(value for value in values if value)


# Normalize compare text.
def normalize_compare_text(value: str) -> str:
    lowered = value.strip().lower()
    return " ".join("".join(char if char.isalnum() else " " for char in lowered).split())


# Compare text flag.
def compare_text_flag(left: str, right: str) -> str:
    if not left.strip() or not right.strip():
        return ""
    normalized_left = normalize_compare_text(left)
    normalized_right = normalize_compare_text(right)
    return "true" if normalized_left == normalized_right else "false"


# Compare year flag.
def compare_year_flag(left: str, right: str) -> str:
    if not left.strip() or not right.strip():
        return ""
    return "true" if left.strip() == right.strip() else "false"


# Build sort paper IDs.
def sort_paper_ids(ids: set[str]) -> list[str]:
    # Build key.
    def key(value: str) -> tuple[int, int | str]:
        stripped = value.strip()
        if stripped.isdigit():
            return (0, int(stripped))
        return (1, stripped)

    return sorted(ids, key=key)


# Load reference rows.
def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


# Load latest manifest by ID.
def load_latest_manifest_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    latest: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            covidence_id = str(row.get("covidence_id") or "").strip()
            if covidence_id:
                latest[covidence_id] = row
    return latest


# Load CSV rows by ID.
def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        latest: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get(key_column) or "").strip()
            if key:
                latest[key] = row
    return latest


# Load prefixed pdfs.
def load_prefixed_pdfs(path: Path) -> dict[str, list[Path]]:
    pdfs_by_id: dict[str, list[Path]] = {}
    for pdf_path in sorted(path.glob("*.pdf")):
        paper_id = pdf_path.stem.split("_", 1)[0].strip()
        pdfs_by_id.setdefault(paper_id, []).append(pdf_path)
    return pdfs_by_id


# Load JSON paths.
def load_json_paths(path: Path) -> dict[str, Path]:
    if not path.exists():
        return {}
    return {file_path.stem: file_path for file_path in sorted(path.glob("*.json"))}


# Load JSON record.
def load_json_record(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# Build artifact types present.
def artifact_types_present(row: dict[str, str]) -> str:
    present: list[str] = []
    checks = {
        "reference": row["reference_present"] == "true",
        "pdf": row["pdf_present"] == "true",
        "text": row["text_json_present"] == "true",
        "text_preclean": row["text_preclean_json_present"] == "true",
        "text_preclean_stage2": row["text_preclean_stage2_json_present"] == "true",
        "text_trimmed": row["text_trimmed_present"] == "true",
        "source_categorisation": row["source_categorisation_present"] == "true",
        "source_sps_case_count": row["source_case_count_present"] == "true",
        "proceedings_qc": row["proceedings_qc_present"] == "true",
        "case_series_split": row["case_series_split_present"] == "true",
        "langextract": row["langextract_raw_present"] == "true",
        "summary": row["summary_json_present"] == "true",
        "quality_raw": row["quality_raw_present"] == "true",
        "quality_record": row["quality_record_present"] == "true",
    }
    for name, is_present in checks.items():
        if is_present:
            present.append(name)
    return "; ".join(present)


# Download status.
def download_status(pdf_paths: list[Path], manifest_row: dict[str, Any]) -> str:
    if pdf_paths:
        return "downloaded"
    status = str(manifest_row.get("status") or "").strip()
    return status or "missing"


# Build row.
def build_row(
    paper_id: str,
    reference_row: dict[str, str],
    manifest_row: dict[str, Any],
    pdf_paths: list[Path],
    text_record: dict[str, Any],
    text_path: Path | None,
    text_preclean_path: Path | None,
    text_preclean_stage2_path: Path | None,
    text_trim_record: dict[str, Any],
    text_trim_path: Path | None,
    text_trim_registry_row: dict[str, str],
    source_categorisation_row: dict[str, str],
    source_case_count_row: dict[str, str],
    source_manual_review_row: dict[str, str],
    proceedings_qc_row: dict[str, str],
    case_series_split_row: dict[str, str],
    case_series_split_path: Path | None,
    langextract_record: dict[str, Any],
    langextract_path: Path | None,
    summary_record: dict[str, Any],
    summary_path: Path | None,
    quality_raw_record: dict[str, Any],
    quality_raw_path: Path | None,
    quality_record: dict[str, Any],
    quality_record_path: Path | None,
) -> dict[str, str]:
    export_title = (reference_row.get("Title") or "").strip()
    export_authors = (reference_row.get("Authors") or "").strip()
    export_year = (reference_row.get("Published Year") or "").strip()
    card_title = str(manifest_row.get("card_publication_title") or "").strip()
    card_authors = str(manifest_row.get("card_authors_full") or "").strip()
    card_year = str(manifest_row.get("card_year") or "").strip()
    resolved_source = resolve_source_row(
        paper_id=paper_id,
        heuristic_row=source_categorisation_row,
        manual_row=source_manual_review_row,
    )
    row = {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "reference_present": bool_text(bool(reference_row)),
        "reference_match_status": "matched_reference" if reference_row else "orphan_artifact",
        "ref": (reference_row.get("Ref") or "").strip(),
        "study": (reference_row.get("Study") or "").strip(),
        "title": export_title,
        "authors": export_authors,
        "published_year": export_year,
        "published_month": (reference_row.get("Published Month") or "").strip(),
        "journal": (reference_row.get("Journal") or "").strip(),
        "volume": (reference_row.get("Volume") or "").strip(),
        "issue": (reference_row.get("Issue") or "").strip(),
        "pages": (reference_row.get("Pages") or "").strip(),
        "accession_number": (reference_row.get("Accession Number") or "").strip(),
        "doi": (reference_row.get("DOI") or "").strip(),
        "notes": (reference_row.get("Notes") or "").strip(),
        "tags": (reference_row.get("Tags") or "").strip(),
        "card_identifier_text": str(manifest_row.get("card_identifier_text") or "").strip(),
        "card_first_author": str(manifest_row.get("card_first_author") or "").strip(),
        "card_year": card_year,
        "card_authors_full": card_authors,
        "card_publication_title": card_title,
        "card_title_matches_export": compare_text_flag(export_title, card_title),
        "card_authors_match_export": compare_text_flag(export_authors, card_authors),
        "card_year_matches_export": compare_year_flag(export_year, card_year),
        "pdf_present": bool_text(bool(pdf_paths)),
        "pdf_file_count": str(len(pdf_paths)),
        "pdf_filenames": join_values([path.name for path in pdf_paths]),
        "pdf_paths_relative": join_values([relative_to_repo(path) for path in pdf_paths]),
        "download_status": download_status(pdf_paths, manifest_row),
        "download_manifest_status": str(manifest_row.get("status") or "").strip(),
        "download_method": str(manifest_row.get("method") or "").strip(),
        "download_error": str(manifest_row.get("error") or "").strip(),
        "download_finished_at_utc": str(manifest_row.get("finished_at_utc") or "").strip(),
        "text_json_present": bool_text(bool(text_path)),
        "text_json_path": relative_to_repo(text_path) if text_path else "",
        "text_preclean_json_present": bool_text(bool(text_preclean_path)),
        "text_preclean_json_path": relative_to_repo(text_preclean_path) if text_preclean_path else "",
        "text_preclean_stage2_json_present": bool_text(bool(text_preclean_stage2_path)),
        "text_preclean_stage2_json_path": (
            relative_to_repo(text_preclean_stage2_path) if text_preclean_stage2_path else ""
        ),
        "text_source_filename": str(text_record.get("source_filename") or ""),
        "text_source_sha256": str(text_record.get("source_sha256") or ""),
        "text_extracted_at_utc": str(text_record.get("extracted_at_utc") or ""),
        "text_n_pages": str(text_record.get("n_pages") or ""),
        "text_needs_ocr": str(text_record.get("needs_ocr") or ""),
        "text_ocr_applied": str(text_record.get("ocr_applied") or ""),
        "text_ocr_error": str(text_record.get("ocr_error") or ""),
        "text_cleanup_applied": (
            bool_text(bool(text_record.get("cleanup_applied")))
            if "cleanup_applied" in text_record
            else ""
        ),
        "text_cleanup_profile": str(text_record.get("cleanup_profile") or ""),
        "text_cleanup_applied_at_utc": str(text_record.get("cleanup_applied_at_utc") or ""),
        "text_cleanup_source_strategy": str(text_record.get("cleanup_source_strategy") or ""),
        "text_cleanup_original_extractor": str(text_record.get("cleanup_original_extractor") or ""),
        "text_cleanup_changed_page_count": str(text_record.get("cleanup_changed_page_count") or ""),
        "text_cleanup_source_json_path": str(text_record.get("cleanup_source_json_path") or ""),
        "text_cleanup_source_json_sha256": str(text_record.get("cleanup_source_json_sha256") or ""),
        "text_cleanup_source_pdf_path": str(text_record.get("cleanup_source_pdf_path") or ""),
        "text_cleanup_source_pdf_sha256": str(text_record.get("cleanup_source_pdf_sha256") or ""),
        "text_cleanup_stage2_applied": (
            bool_text(bool(text_record.get("cleanup_stage2_applied")))
            if "cleanup_stage2_applied" in text_record
            else ""
        ),
        "text_cleanup_stage2_profile": str(text_record.get("cleanup_stage2_profile") or ""),
        "text_cleanup_stage2_applied_at_utc": str(text_record.get("cleanup_stage2_applied_at_utc") or ""),
        "text_cleanup_stage2_source_strategy": str(text_record.get("cleanup_stage2_source_strategy") or ""),
        "text_cleanup_stage2_changed_page_count": str(text_record.get("cleanup_stage2_changed_page_count") or ""),
        "text_cleanup_stage2_source_json_path": str(text_record.get("cleanup_stage2_source_json_path") or ""),
        "text_cleanup_stage2_source_json_sha256": str(text_record.get("cleanup_stage2_source_json_sha256") or ""),
        "text_cleanup_stage2_source_pdf_path": str(text_record.get("cleanup_stage2_source_pdf_path") or ""),
        "text_cleanup_stage2_source_pdf_sha256": str(text_record.get("cleanup_stage2_source_pdf_sha256") or ""),
        "text_cleanup_stage2_source_page_start": str(text_record.get("cleanup_stage2_source_page_start") or ""),
        "text_cleanup_stage2_source_page_end": str(text_record.get("cleanup_stage2_source_page_end") or ""),
        "text_cleanup_stage2_ocr_dpi": str(text_record.get("cleanup_stage2_ocr_dpi") or ""),
        "text_cleanup_stage2_ocr_psm": str(text_record.get("cleanup_stage2_ocr_psm") or ""),
        "text_cleanup_stage2_ocr_grayscale": str(text_record.get("cleanup_stage2_ocr_grayscale") or ""),
        "text_trim_status": str(text_trim_registry_row.get("trim_status") or ""),
        "text_trim_reason": str(text_trim_registry_row.get("trim_reason") or ""),
        "text_trimmed_present": bool_text(bool(text_trim_path)),
        "text_trimmed_path": relative_to_repo(text_trim_path) if text_trim_path else "",
        "text_trim_method": str(text_trim_record.get("trim_method") or text_trim_registry_row.get("trim_method") or ""),
        "text_trim_match_score": str(text_trim_record.get("match_score") or text_trim_registry_row.get("match_score") or ""),
        "text_trim_start_page": str(text_trim_record.get("start_page_index") or text_trim_registry_row.get("start_page_index") or ""),
        "text_trim_end_page": str(text_trim_record.get("end_page_index") or text_trim_registry_row.get("end_page_index") or ""),
        "text_trim_source_text_json_path": str(
            text_trim_record.get("source_text_json_path") or text_trim_registry_row.get("source_text_json_path") or ""
        ),
        "source_categorisation_present": bool_text(bool(source_categorisation_row)),
        "source_category": str(source_categorisation_row.get("source_category") or ""),
        "source_subtype": str(source_categorisation_row.get("source_subtype") or ""),
        "source_classification_confidence": str(source_categorisation_row.get("classification_confidence") or ""),
        "source_likely_case_count": str(source_categorisation_row.get("likely_case_count") or ""),
        "source_case_count_present": bool_text(bool(source_case_count_row)),
        "source_count_eligible": str(source_case_count_row.get("count_eligible") or ""),
        "source_likely_sps_case_count": str(source_case_count_row.get("likely_sps_case_count") or ""),
        "source_count_confidence": str(source_case_count_row.get("count_confidence") or ""),
        "source_count_basis": str(source_case_count_row.get("count_basis") or ""),
        "source_count_manual_review_required": str(
            source_case_count_row.get("count_manual_review_required") or ""
        ),
        "source_count_reason": str(source_case_count_row.get("count_reason") or ""),
        "source_count_version": str(source_case_count_row.get("count_version") or ""),
        "source_counted_at_utc": str(source_case_count_row.get("counted_at_utc") or ""),
        "source_contains_individual_level_data": str(source_categorisation_row.get("contains_individual_level_data") or ""),
        "source_contains_group_level_data": str(source_categorisation_row.get("contains_group_level_data") or ""),
        "source_case_series_split_candidate": str(source_categorisation_row.get("case_series_split_candidate") or ""),
        "source_preferred_langextract_mode": str(source_categorisation_row.get("preferred_langextract_mode") or ""),
        "source_langextract_eligible": str(source_categorisation_row.get("langextract_eligible") or ""),
        "source_manual_review_required": str(source_categorisation_row.get("manual_review_required") or ""),
        "source_recommended_next_action": str(source_categorisation_row.get("recommended_next_action") or ""),
        "source_categorisation_reason": str(source_categorisation_row.get("categorisation_reason") or ""),
        "source_categorised_at_utc": str(source_categorisation_row.get("categorised_at_utc") or ""),
        "source_manual_override_present": str(resolved_source.get("manual_override_present") or ""),
        "resolved_source_category": str(resolved_source.get("resolved_source_category") or ""),
        "resolved_source_subtype": str(resolved_source.get("resolved_source_subtype") or ""),
        "resolved_source_confidence": str(resolved_source.get("resolved_source_confidence") or ""),
        "resolved_source_route_source": str(resolved_source.get("resolved_source_route_source") or ""),
        "resolved_source_notes": str(resolved_source.get("resolved_source_notes") or ""),
        "resolved_source_alignment_tag": str(resolved_source.get("resolved_source_alignment_tag") or ""),
        "resolved_review_batch": str(resolved_source.get("resolved_review_batch") or ""),
        "resolved_reviewed_at_utc": str(resolved_source.get("resolved_reviewed_at_utc") or ""),
        "resolved_case_series_split_candidate": str(resolved_source.get("resolved_case_series_split_candidate") or ""),
        "resolved_langextract_mode": str(resolved_source.get("resolved_langextract_mode") or ""),
        "resolved_langextract_eligible": str(resolved_source.get("resolved_langextract_eligible") or ""),
        "proceedings_qc_present": bool_text(bool(proceedings_qc_row)),
        "proceedings_qc_status": str(proceedings_qc_row.get("qc_status") or ""),
        "proceedings_qc_manual_follow_up_required": str(
            proceedings_qc_row.get("manual_follow_up_required") or ""
        ),
        "proceedings_qc_validated_text_json_path": str(
            proceedings_qc_row.get("validated_text_json_path") or ""
        ),
        "proceedings_qc_best_match_page_index": str(proceedings_qc_row.get("best_match_page_index") or ""),
        "proceedings_qc_title_score": str(proceedings_qc_row.get("title_score") or ""),
        "proceedings_qc_author_score": str(proceedings_qc_row.get("author_score") or ""),
        "proceedings_qc_combined_score": str(proceedings_qc_row.get("combined_score") or ""),
        "proceedings_qc_checked_at_utc": str(proceedings_qc_row.get("checked_at_utc") or ""),
        "case_series_split_present": bool_text(bool(case_series_split_path)),
        "case_series_split_status": str(case_series_split_row.get("split_status") or ""),
        "case_series_split_reason": str(case_series_split_row.get("split_reason") or ""),
        "case_series_split_method": str(case_series_split_row.get("split_method") or ""),
        "case_series_split_case_count": str(case_series_split_row.get("case_count") or ""),
        "case_series_split_text_json_path": relative_to_repo(case_series_split_path) if case_series_split_path else "",
        "langextract_raw_present": bool_text(bool(langextract_path)),
        "langextract_raw_path": relative_to_repo(langextract_path) if langextract_path else "",
        "langextract_model_id": str(langextract_record.get("model_id") or ""),
        "langextract_generated_at_utc": str(langextract_record.get("generated_at_utc") or ""),
        "langextract_total_extraction_count": str(langextract_record.get("total_extraction_count") or ""),
        "summary_json_present": bool_text(bool(summary_path)),
        "summary_json_path": relative_to_repo(summary_path) if summary_path else "",
        "summary_model_id": str(summary_record.get("model_id") or ""),
        "summary_generated_at_utc": str(summary_record.get("generated_at_utc") or ""),
        "summary_total_extraction_count": str(summary_record.get("total_extraction_count") or ""),
        "quality_raw_present": bool_text(bool(quality_raw_path)),
        "quality_raw_path": relative_to_repo(quality_raw_path) if quality_raw_path else "",
        "quality_model_id": str(quality_raw_record.get("model_id") or ""),
        "quality_generated_at_utc": str(quality_raw_record.get("generated_at_utc") or ""),
        "quality_publication_type": str(quality_raw_record.get("publication_type") or ""),
        "quality_extraction_count": str(quality_raw_record.get("extraction_count") or ""),
        "quality_record_present": bool_text(bool(quality_record_path)),
        "quality_record_path": relative_to_repo(quality_record_path) if quality_record_path else "",
        "quality_record_model_id": str(quality_record.get("model_id") or ""),
        "quality_record_generated_at_utc": str(quality_record.get("generated_at_utc") or ""),
        "quality_record_publication_type": str(quality_record.get("publication_type") or ""),
        "quality_missing_field_count": str(len(quality_record.get("missing_fields") or [])),
        "registry_updated_at_utc": now_utc_iso(),
    }
    row["artifact_types_present"] = artifact_types_present(row)
    return row


# Build registry rows.
def build_registry_rows() -> list[dict[str, str]]:
    reference_rows = load_reference_rows(REFERENCES_CSV)
    manifest_by_id = load_latest_manifest_by_id(COVIENCE_MANIFEST_PATH)
    pdfs_by_id = load_prefixed_pdfs(PDF_DIR)
    text_paths = load_json_paths(TEXT_DIR)
    text_preclean_paths = load_json_paths(TEXT_PRECLEAN_DIR)
    text_preclean_stage2_paths = load_json_paths(TEXT_PRECLEAN_STAGE2_DIR)
    text_trimmed_paths = load_json_paths(TEXT_TRIMMED_DIR)
    case_series_split_paths = load_json_paths(CASE_SERIES_SPLIT_DIR)
    text_trim_registry_rows = load_csv_rows_by_id(TEXT_TRIM_REGISTRY_PATH, "paper_id")
    source_categorisation_rows = load_csv_rows_by_id(SOURCE_CATEGORISATION_PATH, "paper_id")
    source_case_count_rows = load_csv_rows_by_id(SOURCE_CASE_COUNT_PATH, "paper_id")
    source_manual_review_rows = load_csv_rows_by_id(SOURCE_MANUAL_REVIEW_PATH, "paper_id")
    proceedings_qc_rows = load_csv_rows_by_id(PROCEEDINGS_QC_PATH, "paper_id")
    case_series_split_rows = load_csv_rows_by_id(CASE_SERIES_SPLIT_REGISTRY_PATH, "paper_id")
    langextract_paths = load_json_paths(LANGEXTRACT_DIR)
    summary_paths = load_json_paths(SUMMARY_DIR)
    quality_raw_paths = load_json_paths(QUALITY_RAW_DIR)
    quality_record_paths = load_json_paths(QUALITY_RECORD_DIR)

    all_ids = (
        set(reference_rows)
        | set(manifest_by_id)
        | set(pdfs_by_id)
        | set(text_paths)
        | set(text_preclean_paths)
        | set(text_preclean_stage2_paths)
        | set(text_trimmed_paths)
        | set(case_series_split_paths)
        | set(text_trim_registry_rows)
        | set(source_categorisation_rows)
        | set(source_case_count_rows)
        | set(source_manual_review_rows)
        | set(proceedings_qc_rows)
        | set(case_series_split_rows)
        | set(langextract_paths)
        | set(summary_paths)
        | set(quality_raw_paths)
        | set(quality_record_paths)
    )

    rows: list[dict[str, str]] = []
    for paper_id in sort_paper_ids(all_ids):
        text_path = text_paths.get(paper_id)
        text_preclean_path = text_preclean_paths.get(paper_id)
        text_preclean_stage2_path = text_preclean_stage2_paths.get(paper_id)
        text_trim_path = text_trimmed_paths.get(paper_id)
        langextract_path = langextract_paths.get(paper_id)
        summary_path = summary_paths.get(paper_id)
        quality_raw_path = quality_raw_paths.get(paper_id)
        quality_record_path = quality_record_paths.get(paper_id)
        rows.append(
            build_row(
                paper_id=paper_id,
                reference_row=reference_rows.get(paper_id, {}),
                manifest_row=manifest_by_id.get(paper_id, {}),
                pdf_paths=pdfs_by_id.get(paper_id, []),
                text_record=load_json_record(text_path),
                text_path=text_path,
                text_preclean_path=text_preclean_path,
                text_preclean_stage2_path=text_preclean_stage2_path,
                text_trim_record=load_json_record(text_trim_path),
                text_trim_path=text_trim_path,
                text_trim_registry_row=text_trim_registry_rows.get(paper_id, {}),
                source_categorisation_row=source_categorisation_rows.get(paper_id, {}),
                source_case_count_row=source_case_count_rows.get(paper_id, {}),
                source_manual_review_row=source_manual_review_rows.get(paper_id, {}),
                proceedings_qc_row=proceedings_qc_rows.get(paper_id, {}),
                case_series_split_row=case_series_split_rows.get(paper_id, {}),
                case_series_split_path=case_series_split_paths.get(paper_id),
                langextract_record=load_json_record(langextract_path),
                langextract_path=langextract_path,
                summary_record=load_json_record(summary_path),
                summary_path=summary_path,
                quality_raw_record=load_json_record(quality_raw_path),
                quality_raw_path=quality_raw_path,
                quality_record=load_json_record(quality_record_path),
                quality_record_path=quality_record_path,
            )
        )
    return rows


# Write registry.
def write_registry(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "reference_present",
        "reference_match_status",
        "ref",
        "study",
        "title",
        "authors",
        "published_year",
        "published_month",
        "journal",
        "volume",
        "issue",
        "pages",
        "accession_number",
        "doi",
        "notes",
        "tags",
        "card_identifier_text",
        "card_first_author",
        "card_year",
        "card_authors_full",
        "card_publication_title",
        "card_title_matches_export",
        "card_authors_match_export",
        "card_year_matches_export",
        "pdf_present",
        "pdf_file_count",
        "pdf_filenames",
        "pdf_paths_relative",
        "download_status",
        "download_manifest_status",
        "download_method",
        "download_error",
        "download_finished_at_utc",
        "text_json_present",
        "text_json_path",
        "text_preclean_json_present",
        "text_preclean_json_path",
        "text_preclean_stage2_json_present",
        "text_preclean_stage2_json_path",
        "text_source_filename",
        "text_source_sha256",
        "text_extracted_at_utc",
        "text_n_pages",
        "text_needs_ocr",
        "text_ocr_applied",
        "text_ocr_error",
        "text_cleanup_applied",
        "text_cleanup_profile",
        "text_cleanup_applied_at_utc",
        "text_cleanup_source_strategy",
        "text_cleanup_original_extractor",
        "text_cleanup_changed_page_count",
        "text_cleanup_source_json_path",
        "text_cleanup_source_json_sha256",
        "text_cleanup_source_pdf_path",
        "text_cleanup_source_pdf_sha256",
        "text_cleanup_stage2_applied",
        "text_cleanup_stage2_profile",
        "text_cleanup_stage2_applied_at_utc",
        "text_cleanup_stage2_source_strategy",
        "text_cleanup_stage2_changed_page_count",
        "text_cleanup_stage2_source_json_path",
        "text_cleanup_stage2_source_json_sha256",
        "text_cleanup_stage2_source_pdf_path",
        "text_cleanup_stage2_source_pdf_sha256",
        "text_cleanup_stage2_source_page_start",
        "text_cleanup_stage2_source_page_end",
        "text_cleanup_stage2_ocr_dpi",
        "text_cleanup_stage2_ocr_psm",
        "text_cleanup_stage2_ocr_grayscale",
        "text_trim_status",
        "text_trim_reason",
        "text_trimmed_present",
        "text_trimmed_path",
        "text_trim_method",
        "text_trim_match_score",
        "text_trim_start_page",
        "text_trim_end_page",
        "text_trim_source_text_json_path",
        "source_categorisation_present",
        "source_category",
        "source_subtype",
        "source_classification_confidence",
        "source_likely_case_count",
        "source_case_count_present",
        "source_count_eligible",
        "source_likely_sps_case_count",
        "source_count_confidence",
        "source_count_basis",
        "source_count_manual_review_required",
        "source_count_reason",
        "source_count_version",
        "source_counted_at_utc",
        "source_contains_individual_level_data",
        "source_contains_group_level_data",
        "source_case_series_split_candidate",
        "source_preferred_langextract_mode",
        "source_langextract_eligible",
        "source_manual_review_required",
        "source_recommended_next_action",
        "source_categorisation_reason",
        "source_categorised_at_utc",
        "source_manual_override_present",
        "resolved_source_category",
        "resolved_source_subtype",
        "resolved_source_confidence",
        "resolved_source_route_source",
        "resolved_source_notes",
        "resolved_source_alignment_tag",
        "resolved_review_batch",
        "resolved_reviewed_at_utc",
        "resolved_case_series_split_candidate",
        "resolved_langextract_mode",
        "resolved_langextract_eligible",
        "proceedings_qc_present",
        "proceedings_qc_status",
        "proceedings_qc_manual_follow_up_required",
        "proceedings_qc_validated_text_json_path",
        "proceedings_qc_best_match_page_index",
        "proceedings_qc_title_score",
        "proceedings_qc_author_score",
        "proceedings_qc_combined_score",
        "proceedings_qc_checked_at_utc",
        "case_series_split_present",
        "case_series_split_status",
        "case_series_split_reason",
        "case_series_split_method",
        "case_series_split_case_count",
        "case_series_split_text_json_path",
        "langextract_raw_present",
        "langextract_raw_path",
        "langextract_model_id",
        "langextract_generated_at_utc",
        "langextract_total_extraction_count",
        "summary_json_present",
        "summary_json_path",
        "summary_model_id",
        "summary_generated_at_utc",
        "summary_total_extraction_count",
        "quality_raw_present",
        "quality_raw_path",
        "quality_model_id",
        "quality_generated_at_utc",
        "quality_publication_type",
        "quality_extraction_count",
        "quality_record_present",
        "quality_record_path",
        "quality_record_model_id",
        "quality_record_generated_at_utc",
        "quality_record_publication_type",
        "quality_missing_field_count",
        "artifact_types_present",
        "registry_updated_at_utc",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# Run the pipeline entrypoint.
def main() -> None:
    rows = build_registry_rows()
    write_registry(rows, OUTPUT_PATH)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
