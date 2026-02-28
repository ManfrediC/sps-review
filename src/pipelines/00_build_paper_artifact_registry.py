from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
PDF_DIR = REPO_ROOT / "data" / "pdf_original"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
LANGEXTRACT_DIR = REPO_ROOT / "data" / "extraction_json" / "langextract"
SUMMARY_DIR = REPO_ROOT / "data" / "extraction_json" / "summary"
QUALITY_RAW_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "raw"
QUALITY_RECORD_DIR = REPO_ROOT / "data" / "extraction_json" / "quality" / "records"
COVIENCE_MANIFEST_PATH = REPO_ROOT / "data" / "extraction_json" / "covidence" / "download_manifest.jsonl"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def join_values(values: list[str]) -> str:
    return " | ".join(value for value in values if value)


def sort_paper_ids(ids: set[str]) -> list[str]:
    def key(value: str) -> tuple[int, int | str]:
        stripped = value.strip()
        if stripped.isdigit():
            return (0, int(stripped))
        return (1, stripped)

    return sorted(ids, key=key)


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


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


def load_prefixed_pdfs(path: Path) -> dict[str, list[Path]]:
    pdfs_by_id: dict[str, list[Path]] = {}
    for pdf_path in sorted(path.glob("*.pdf")):
        paper_id = pdf_path.stem.split("_", 1)[0].strip()
        pdfs_by_id.setdefault(paper_id, []).append(pdf_path)
    return pdfs_by_id


def load_json_paths(path: Path) -> dict[str, Path]:
    if not path.exists():
        return {}
    return {file_path.stem: file_path for file_path in sorted(path.glob("*.json"))}


def load_json_record(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_types_present(row: dict[str, str]) -> str:
    present: list[str] = []
    checks = {
        "reference": row["reference_present"] == "true",
        "pdf": row["pdf_present"] == "true",
        "text": row["text_json_present"] == "true",
        "text_trimmed": row["text_trimmed_present"] == "true",
        "langextract": row["langextract_raw_present"] == "true",
        "summary": row["summary_json_present"] == "true",
        "quality_raw": row["quality_raw_present"] == "true",
        "quality_record": row["quality_record_present"] == "true",
    }
    for name, is_present in checks.items():
        if is_present:
            present.append(name)
    return "; ".join(present)


def download_status(pdf_paths: list[Path], manifest_row: dict[str, Any]) -> str:
    if pdf_paths:
        return "downloaded"
    status = str(manifest_row.get("status") or "").strip()
    return status or "missing"


def build_row(
    paper_id: str,
    reference_row: dict[str, str],
    manifest_row: dict[str, Any],
    pdf_paths: list[Path],
    text_record: dict[str, Any],
    text_path: Path | None,
    text_trim_record: dict[str, Any],
    text_trim_path: Path | None,
    text_trim_registry_row: dict[str, str],
    langextract_record: dict[str, Any],
    langextract_path: Path | None,
    summary_record: dict[str, Any],
    summary_path: Path | None,
    quality_raw_record: dict[str, Any],
    quality_raw_path: Path | None,
    quality_record: dict[str, Any],
    quality_record_path: Path | None,
) -> dict[str, str]:
    row = {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "reference_present": bool_text(bool(reference_row)),
        "reference_match_status": "matched_reference" if reference_row else "orphan_artifact",
        "ref": (reference_row.get("Ref") or "").strip(),
        "study": (reference_row.get("Study") or "").strip(),
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "published_year": (reference_row.get("Published Year") or "").strip(),
        "published_month": (reference_row.get("Published Month") or "").strip(),
        "journal": (reference_row.get("Journal") or "").strip(),
        "volume": (reference_row.get("Volume") or "").strip(),
        "issue": (reference_row.get("Issue") or "").strip(),
        "pages": (reference_row.get("Pages") or "").strip(),
        "accession_number": (reference_row.get("Accession Number") or "").strip(),
        "doi": (reference_row.get("DOI") or "").strip(),
        "notes": (reference_row.get("Notes") or "").strip(),
        "tags": (reference_row.get("Tags") or "").strip(),
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
        "text_source_filename": str(text_record.get("source_filename") or ""),
        "text_source_sha256": str(text_record.get("source_sha256") or ""),
        "text_extracted_at_utc": str(text_record.get("extracted_at_utc") or ""),
        "text_n_pages": str(text_record.get("n_pages") or ""),
        "text_needs_ocr": str(text_record.get("needs_ocr") or ""),
        "text_ocr_applied": str(text_record.get("ocr_applied") or ""),
        "text_ocr_error": str(text_record.get("ocr_error") or ""),
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


def build_registry_rows() -> list[dict[str, str]]:
    reference_rows = load_reference_rows(REFERENCES_CSV)
    manifest_by_id = load_latest_manifest_by_id(COVIENCE_MANIFEST_PATH)
    pdfs_by_id = load_prefixed_pdfs(PDF_DIR)
    text_paths = load_json_paths(TEXT_DIR)
    text_trimmed_paths = load_json_paths(TEXT_TRIMMED_DIR)
    text_trim_registry_rows = load_csv_rows_by_id(TEXT_TRIM_REGISTRY_PATH, "paper_id")
    langextract_paths = load_json_paths(LANGEXTRACT_DIR)
    summary_paths = load_json_paths(SUMMARY_DIR)
    quality_raw_paths = load_json_paths(QUALITY_RAW_DIR)
    quality_record_paths = load_json_paths(QUALITY_RECORD_DIR)

    all_ids = (
        set(reference_rows)
        | set(manifest_by_id)
        | set(pdfs_by_id)
        | set(text_paths)
        | set(text_trimmed_paths)
        | set(text_trim_registry_rows)
        | set(langextract_paths)
        | set(summary_paths)
        | set(quality_raw_paths)
        | set(quality_record_paths)
    )

    rows: list[dict[str, str]] = []
    for paper_id in sort_paper_ids(all_ids):
        text_path = text_paths.get(paper_id)
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
                text_trim_record=load_json_record(text_trim_path),
                text_trim_path=text_trim_path,
                text_trim_registry_row=text_trim_registry_rows.get(paper_id, {}),
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
        "text_source_filename",
        "text_source_sha256",
        "text_extracted_at_utc",
        "text_n_pages",
        "text_needs_ocr",
        "text_ocr_applied",
        "text_ocr_error",
        "text_trim_status",
        "text_trim_reason",
        "text_trimmed_present",
        "text_trimmed_path",
        "text_trim_method",
        "text_trim_match_score",
        "text_trim_start_page",
        "text_trim_end_page",
        "text_trim_source_text_json_path",
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


def main() -> None:
    rows = build_registry_rows()
    write_registry(rows, OUTPUT_PATH)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
