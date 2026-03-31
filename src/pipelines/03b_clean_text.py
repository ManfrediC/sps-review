from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.text_cleanup import DEFAULT_PROFILE, clean_document_pages  # noqa: E402


PDF_DIR = REPO_ROOT / "data" / "pdf_original"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_PRECLEAN_DIR = REPO_ROOT / "data" / "extraction_json" / "text_preclean"
OVERRIDE_PATH = REPO_ROOT / "config" / "extraction" / "text_cleanup_overrides.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply deterministic cleanup to selected extracted text JSON records."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing canonical text extraction JSON files.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=TEXT_PRECLEAN_DIR,
        help="Directory where pre-clean raw JSON backups are stored.",
    )
    parser.add_argument(
        "--override-path",
        type=Path,
        default=OVERRIDE_PATH,
        help="CSV file containing per-paper text cleanup overrides.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of JSON files to process.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild cleaned JSON files from their pre-clean backup when available.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after cleanup.",
    )
    return parser.parse_args()


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def load_cleanup_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["covidence_id"].strip(): row
            for row in csv.DictReader(handle)
            if (row.get("covidence_id") or "").strip() and truthy(row.get("enabled") or "")
        }


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_pages_and_counts_pdftotext(pdf_path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    # Some born-digital PDFs have a usable text layer that `pypdf` mangles badly.
    # This path re-extracts directly from the source PDF so cleanup starts from the
    # cleaner text stream rather than from already-corrupted JSON content.
    proc = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw_text = proc.stdout or ""
    page_texts = raw_text.split("\f")
    if page_texts and page_texts[-1] == "":
        page_texts = page_texts[:-1]

    pages: list[dict[str, Any]] = []
    char_counts: list[int] = []
    for index, text in enumerate(page_texts):
        cleaned = text.replace("\u00a0", " ").strip()
        pages.append({"page_index": index, "text": cleaned})
        char_counts.append(len(cleaned))
    return pages, char_counts


def write_json_atomic(out_path: Path, record: dict[str, Any]) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=out_path.parent,
            prefix=f"{out_path.stem}_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(record, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        tmp_path.replace(out_path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def sort_paper_ids(ids: set[str]) -> list[str]:
    def key(value: str) -> tuple[int, int | str]:
        stripped = value.strip()
        if stripped.isdigit():
            return (0, int(stripped))
        return (1, stripped)

    return sorted(ids, key=key)


def collect_target_json_paths(
    input_dir: Path,
    *,
    enabled_ids: set[str],
    paper_ids: list[str],
    limit: int,
) -> list[Path]:
    requested = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    path_by_id = {
        path.stem: path
        for path in input_dir.glob("*.json")
        if path.stem in enabled_ids and (not requested or path.stem in requested)
    }
    candidates = [path_by_id[paper_id] for paper_id in sort_paper_ids(set(path_by_id))]
    if limit > 0:
        return candidates[:limit]
    return candidates


def ensure_preclean_snapshot(text_path: Path, backup_path: Path) -> tuple[dict[str, Any], Path]:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.exists():
        return load_json_record(backup_path), backup_path

    source_record = load_json_record(text_path)
    # `03b` overwrites the canonical JSON in `data/extraction_json/text/`, so every
    # first cleanup pass must preserve the pre-clean state for provenance and reruns.
    if source_record.get("cleanup_applied"):
        raise ValueError(
            f"Canonical text JSON is already cleaned but no pre-clean backup exists: {text_path}"
        )
    write_json_atomic(backup_path, source_record)
    return source_record, backup_path


def suspicious_control_char_count(text: str) -> int:
    return sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")


def build_cleanup_source_record(
    raw_record: dict[str, Any],
    *,
    override_row: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    source_strategy = (override_row.get("source_strategy") or "json_cleanup").strip() or "json_cleanup"
    if source_strategy == "json_cleanup":
        return dict(raw_record), {
            "cleanup_source_strategy": source_strategy,
            "cleanup_source_pdf_path": "",
            "cleanup_source_pdf_sha256": "",
        }
    if source_strategy == "pdftotext_cleanup":
        source_filename = str(raw_record.get("source_filename") or "").strip()
        if not source_filename:
            raise ValueError("Raw text JSON is missing source_filename for pdftotext cleanup.")
        pdf_path = PDF_DIR / source_filename
        if not pdf_path.exists():
            raise FileNotFoundError(f"Source PDF not found for pdftotext cleanup: {pdf_path}")
        pages, char_counts = extract_pages_and_counts_pdftotext(pdf_path)
        if not pages:
            raise ValueError(f"pdftotext returned no pages for: {pdf_path}")
        source_record = dict(raw_record)
        source_record["pages"] = pages
        source_record["n_pages"] = len(pages)
        source_record["page_char_counts"] = char_counts
        # Keep the rest of the raw JSON metadata, but explicitly mark that the cleaned
        # text was rebuilt from a fresh `pdftotext` pass over the source PDF.
        source_record["suspicious_control_chars"] = suspicious_control_char_count(
            "\n".join(str(page.get("text") or "") for page in pages)
        )
        source_record["extractor"] = "pdftotext"
        return source_record, {
            "cleanup_source_strategy": source_strategy,
            "cleanup_source_pdf_path": relative_to_repo(pdf_path),
            "cleanup_source_pdf_sha256": sha256_file(pdf_path),
        }
    raise ValueError(f"Unsupported cleanup source strategy: {source_strategy}")


def apply_cleanup_to_record(
    raw_record: dict[str, Any],
    *,
    raw_source_path: Path,
    override_row: dict[str, str],
) -> dict[str, Any]:
    source_record, source_metadata = build_cleanup_source_record(raw_record, override_row=override_row)
    pages = source_record.get("pages") or []
    if not isinstance(pages, list):
        raise ValueError("Text JSON does not contain a valid pages list.")

    profile = (override_row.get("cleanup_profile") or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    cleanup_result = clean_document_pages(pages, profile=profile)
    cleaned_record = dict(source_record)
    cleaned_record["pages"] = cleanup_result.pages
    cleaned_record["n_pages"] = len(cleanup_result.pages)
    cleaned_record["page_char_counts"] = [
        len(str(page.get("text") or ""))
        for page in cleanup_result.pages
    ]
    cleaned_record["suspicious_control_chars"] = suspicious_control_char_count(
        "\n".join(str(page.get("text") or "") for page in cleanup_result.pages)
    )
    cleaned_record["cleanup_applied"] = True
    cleaned_record["cleanup_profile"] = profile
    cleaned_record["cleanup_rules_applied"] = list(cleanup_result.rules_applied)
    cleaned_record["cleanup_applied_at_utc"] = datetime.now(timezone.utc).isoformat()
    cleaned_record["cleanup_source_json_path"] = relative_to_repo(raw_source_path)
    cleaned_record["cleanup_source_json_sha256"] = sha256_file(raw_source_path)
    cleaned_record["cleanup_source_strategy"] = source_metadata["cleanup_source_strategy"]
    cleaned_record["cleanup_source_pdf_path"] = source_metadata["cleanup_source_pdf_path"]
    cleaned_record["cleanup_source_pdf_sha256"] = source_metadata["cleanup_source_pdf_sha256"]
    cleaned_record["cleanup_original_extractor"] = str(raw_record.get("extractor") or "")
    cleaned_record["cleanup_changed_page_count"] = cleanup_result.changed_page_count
    cleaned_record["cleanup_artifact_counts_before"] = cleanup_result.artifact_counts_before
    cleaned_record["cleanup_artifact_counts_after"] = cleanup_result.artifact_counts_after
    cleaned_record["cleanup_reason"] = (override_row.get("reason") or "").strip()
    cleaned_record["cleanup_notes"] = (override_row.get("notes") or "").strip()
    return cleaned_record


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def main() -> None:
    args = parse_args()
    overrides = load_cleanup_overrides(args.override_path)
    enabled_ids = set(overrides)
    target_paths = collect_target_json_paths(
        args.input_dir,
        enabled_ids=enabled_ids,
        paper_ids=args.paper_id,
        limit=args.limit,
    )
    if not target_paths:
        raise SystemExit(
            f"No text JSONs found in {args.input_dir} for enabled cleanup IDs."
        )

    cleaned_count = 0
    skipped_count = 0
    for text_path in target_paths:
        current_record = load_json_record(text_path)
        backup_path = args.backup_dir / text_path.name
        if current_record.get("cleanup_applied") and not args.force:
            if not backup_path.exists():
                raise ValueError(
                    f"Canonical text JSON is already cleaned but no pre-clean backup exists: {text_path}"
                )
            skipped_count += 1
            continue

        # `--force` always rebuilds from the preserved pre-clean snapshot so reruns stay
        # deterministic and never stack cleanup on top of already-cleaned text.
        raw_record, raw_source_path = ensure_preclean_snapshot(text_path, backup_path)
        cleaned_record = apply_cleanup_to_record(
            raw_record,
            raw_source_path=raw_source_path,
            override_row=overrides[text_path.stem],
        )
        write_json_atomic(text_path, cleaned_record)
        cleaned_count += 1

    refresh_artifact_registry(args.skip_registry_refresh)
    print(
        f"Cleaned {cleaned_count} text JSON(s) in {args.input_dir}"
        + (f"; skipped {skipped_count} already-cleaned file(s)." if skipped_count else ".")
    )


if __name__ == "__main__":
    main()
