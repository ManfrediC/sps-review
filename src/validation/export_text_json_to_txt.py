from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "pdf_source_registry.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert text extraction JSON files into human-readable TXT exports."
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing text extraction JSON files.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="Optional registry path used to enrich TXT headers with title and author metadata.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where TXT exports will be written.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to export. Repeat for multiple IDs.",
    )
    parser.add_argument(
        "--selection-csv",
        type=Path,
        action="append",
        default=[],
        help="CSV file containing a covidence_id column to select exports. Repeat to combine multiple CSVs.",
    )
    parser.add_argument(
        "--selection-column",
        default="covidence_id",
        help="Column name used when reading --selection-csv files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing TXT exports.",
    )
    return parser.parse_args()


def load_registry_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["covidence_id"]: row for row in csv.DictReader(handle)}


def load_selection_ids(csv_paths: list[Path], *, column: str) -> set[str]:
    selected: set[str] = set()
    for csv_path in csv_paths:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                value = (row.get(column) or "").strip()
                if value:
                    selected.add(value)
    return selected


def collect_input_paths(
    text_dir: Path,
    *,
    paper_ids: list[str],
    selection_ids: set[str],
) -> list[Path]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    wanted |= selection_ids
    all_paths = sorted(text_dir.glob("*.json"))
    if not wanted:
        return all_paths
    return [path for path in all_paths if path.stem in wanted]


def format_value(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "[]"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def render_txt_export(
    record: dict[str, Any],
    *,
    json_path: Path,
    registry_row: dict[str, str] | None,
) -> str:
    pages = record.get("pages") or []
    title = (registry_row or {}).get("title", "")
    authors = (registry_row or {}).get("authors", "")
    published_year = (registry_row or {}).get("published_year", "")
    journal = (registry_row or {}).get("journal", "")
    doi = (registry_row or {}).get("doi", "")

    header_lines = [
        f"Paper ID: {record.get('paper_id') or json_path.stem}",
        f"Title: {title or 'Unknown'}",
        f"Authors: {authors or 'Unknown'}",
        f"Published year: {published_year or 'Unknown'}",
        f"Journal: {journal or 'Unknown'}",
        f"DOI: {doi or 'Unknown'}",
        f"Source filename: {record.get('source_filename') or 'Unknown'}",
        f"Text JSON path: {display_path(json_path)}",
        f"Source SHA256: {record.get('source_sha256') or 'Unknown'}",
        f"Extractor: {record.get('extractor') or 'Unknown'}",
        f"Extracted at UTC: {record.get('extracted_at_utc') or 'Unknown'}",
        f"OCR applied: {format_value(record.get('ocr_applied'))}",
        f"OCR mode: {record.get('ocr_mode') or 'None'}",
        f"OCR trigger reasons: {format_value(record.get('ocr_trigger_reasons'))}",
        f"Needs OCR before OCR: {format_value(record.get('needs_ocr_before_ocr'))}",
        f"Needs OCR after extraction: {format_value(record.get('needs_ocr'))}",
        f"Remaining text quality flags: {format_value(record.get('remaining_text_quality_flags'))}",
        f"Suspicious control chars: {format_value(record.get('suspicious_control_chars'))}",
        f"Native extraction error: {format_value(record.get('native_extraction_error'))}",
        f"OCR error: {format_value(record.get('ocr_error'))}",
        f"Processing error: {format_value(record.get('processing_error'))}",
        f"Page count: {format_value(record.get('n_pages'))}",
    ]

    sections = ["\n".join(header_lines)]
    for page in pages:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        sections.append(
            "\n".join(
                [
                    "=" * 100,
                    f"Page {page_index + 1} / {len(pages)} (page_index={page_index})",
                    "-" * 100,
                    page_text,
                ]
            )
        )

    return "\n\n".join(sections).strip() + "\n"


def export_text_jsons(
    *,
    input_paths: list[Path],
    registry_rows: dict[str, dict[str, str]],
    output_dir: Path,
    force: bool,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for json_path in input_paths:
        out_path = output_dir / f"{json_path.stem}.txt"
        if out_path.exists() and not force:
            continue
        record = json.loads(json_path.read_text(encoding="utf-8"))
        rendered = render_txt_export(
            record,
            json_path=json_path,
            registry_row=registry_rows.get(json_path.stem),
        )
        out_path.write_text(rendered, encoding="utf-8")
        written += 1
    return written


def main() -> None:
    args = parse_args()
    registry_rows = load_registry_rows(args.registry_path)
    selection_ids = load_selection_ids(args.selection_csv, column=args.selection_column)
    input_paths = collect_input_paths(
        args.text_dir,
        paper_ids=args.paper_id,
        selection_ids=selection_ids,
    )
    written = export_text_jsons(
        input_paths=input_paths,
        registry_rows=registry_rows,
        output_dir=args.output_dir,
        force=args.force,
    )
    print(f"Exported {written} TXT files to {args.output_dir}")


if __name__ == "__main__":
    main()
