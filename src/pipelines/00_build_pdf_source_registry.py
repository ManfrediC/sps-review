from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
DEFAULT_PDF_DIR = REPO_ROOT / "data" / "pdf_original"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "data" / "extraction_json" / "covidence" / "download_manifest.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "references" / "pdf_source_registry.csv"
PDF_ID_RE = re.compile(r"^(?P<covidence_id>\d+)_(?P<source_filename>.+\.pdf)$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a registry linking Covidence references to local PDF files."
    )
    parser.add_argument(
        "--references-csv",
        type=Path,
        default=DEFAULT_REFERENCES_CSV,
        help="Covidence reference export CSV.",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing downloaded PDFs.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Optional Covidence download manifest JSONL.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output CSV path for the PDF source registry.",
    )
    return parser.parse_args()


def load_manifest_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    latest: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            covidence_id = str(row.get("covidence_id", "")).strip()
            if covidence_id:
                latest[covidence_id] = row
    return latest


def load_local_pdfs_by_id(pdf_dir: Path) -> tuple[dict[str, list[Path]], list[Path]]:
    matched: dict[str, list[Path]] = {}
    unmatched: list[Path] = []

    for path in sorted(pdf_dir.glob("*.pdf")):
        match = PDF_ID_RE.match(path.name)
        if not match:
            unmatched.append(path)
            continue
        covidence_id = match.group("covidence_id")
        matched.setdefault(covidence_id, []).append(path)

    return matched, unmatched


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def join_paths(paths: list[Path], *, absolute: bool) -> str:
    values = [str(path.resolve()) if absolute else relative_to_repo(path) for path in paths]
    return " | ".join(values)


def join_names(paths: list[Path]) -> str:
    return " | ".join(path.name for path in paths)


def normalize_compare_text(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def compare_text_flag(left: str, right: str) -> str:
    if not left.strip() or not right.strip():
        return ""
    return "true" if normalize_compare_text(left) == normalize_compare_text(right) else "false"


def compare_year_flag(left: str, right: str) -> str:
    if not left.strip() or not right.strip():
        return ""
    return "true" if left.strip() == right.strip() else "false"


def download_status_for(local_paths: list[Path], manifest_row: dict[str, Any]) -> str:
    if len(local_paths) == 1:
        return "downloaded"
    if len(local_paths) > 1:
        return "multiple_local_files"
    manifest_status = str(manifest_row.get("status", "")).strip()
    if manifest_status:
        return manifest_status
    return "missing"


def registry_row(
    reference_row: dict[str, str],
    local_paths: list[Path],
    manifest_row: dict[str, Any],
) -> dict[str, str]:
    covidence_id = (reference_row.get("Covidence") or "").strip()
    export_title = (reference_row.get("Title") or "").strip()
    export_authors = (reference_row.get("Authors") or "").strip()
    export_year = (reference_row.get("Published Year") or "").strip()
    card_title = str(manifest_row.get("card_publication_title", "")).strip()
    card_authors = str(manifest_row.get("card_authors_full", "")).strip()
    card_year = str(manifest_row.get("card_year", "")).strip()
    return {
        "covidence_id": covidence_id,
        "ref": (reference_row.get("Ref") or "").strip(),
        "study": (reference_row.get("Study") or "").strip(),
        "title": export_title,
        "authors": export_authors,
        "published_year": export_year,
        "journal": (reference_row.get("Journal") or "").strip(),
        "doi": (reference_row.get("DOI") or "").strip(),
        "tags": (reference_row.get("Tags") or "").strip(),
        "card_identifier_text": str(manifest_row.get("card_identifier_text", "")).strip(),
        "card_first_author": str(manifest_row.get("card_first_author", "")).strip(),
        "card_year": card_year,
        "card_authors_full": card_authors,
        "card_publication_title": card_title,
        "card_title_matches_export": compare_text_flag(export_title, card_title),
        "card_authors_match_export": compare_text_flag(export_authors, card_authors),
        "card_year_matches_export": compare_year_flag(export_year, card_year),
        "pdf_filename": join_names(local_paths),
        "pdf_path_relative": join_paths(local_paths, absolute=False),
        "pdf_path_absolute": join_paths(local_paths, absolute=True),
        "local_file_count": str(len(local_paths)),
        "download_status": download_status_for(local_paths, manifest_row),
        "manifest_status": str(manifest_row.get("status", "")).strip(),
        "download_method": str(manifest_row.get("method", "")).strip(),
        "download_url": str(manifest_row.get("download_url", "")).strip(),
        "manifest_error": str(manifest_row.get("error", "")).strip(),
    }


def unmatched_row(path: Path, manifest_row: dict[str, Any]) -> dict[str, str]:
    match = PDF_ID_RE.match(path.name)
    covidence_id = match.group("covidence_id") if match else ""
    return {
        "covidence_id": covidence_id,
        "ref": "",
        "study": "",
        "title": "",
        "authors": "",
        "published_year": "",
        "journal": "",
        "doi": "",
        "tags": "",
        "card_identifier_text": str(manifest_row.get("card_identifier_text", "")).strip(),
        "card_first_author": str(manifest_row.get("card_first_author", "")).strip(),
        "card_year": str(manifest_row.get("card_year", "")).strip(),
        "card_authors_full": str(manifest_row.get("card_authors_full", "")).strip(),
        "card_publication_title": str(manifest_row.get("card_publication_title", "")).strip(),
        "card_title_matches_export": "",
        "card_authors_match_export": "",
        "card_year_matches_export": "",
        "pdf_filename": path.name,
        "pdf_path_relative": relative_to_repo(path),
        "pdf_path_absolute": str(path.resolve()),
        "local_file_count": "1",
        "download_status": "unmatched_local_file",
        "manifest_status": "",
        "download_method": "",
        "download_url": "",
        "manifest_error": "",
    }


def build_registry(args: argparse.Namespace) -> list[dict[str, str]]:
    manifest_by_id = load_manifest_by_id(args.manifest_path)
    local_pdfs_by_id, unmatched_local_pdfs = load_local_pdfs_by_id(args.pdf_dir)

    rows: list[dict[str, str]] = []
    with args.references_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for reference_row in reader:
            covidence_id = (reference_row.get("Covidence") or "").strip()
            local_paths = local_pdfs_by_id.pop(covidence_id, [])
            manifest_row = manifest_by_id.get(covidence_id, {})
            rows.append(registry_row(reference_row, local_paths, manifest_row))

    extra_paths = []
    for paths in local_pdfs_by_id.values():
        extra_paths.extend(paths)
    extra_paths.extend(unmatched_local_pdfs)

    for path in sorted(extra_paths):
        covidence_id = path.stem.split("_", 1)[0].strip()
        rows.append(unmatched_row(path, manifest_by_id.get(covidence_id, {})))

    return rows


def write_registry(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "covidence_id",
        "ref",
        "study",
        "title",
        "authors",
        "published_year",
        "journal",
        "doi",
        "tags",
        "card_identifier_text",
        "card_first_author",
        "card_year",
        "card_authors_full",
        "card_publication_title",
        "card_title_matches_export",
        "card_authors_match_export",
        "card_year_matches_export",
        "pdf_filename",
        "pdf_path_relative",
        "pdf_path_absolute",
        "local_file_count",
        "download_status",
        "manifest_status",
        "download_method",
        "download_url",
        "manifest_error",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = build_registry(args)
    write_registry(rows, args.output_path)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
