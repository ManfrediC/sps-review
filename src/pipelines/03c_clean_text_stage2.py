from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
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
TEXT_PRECLEAN_STAGE2_DIR = REPO_ROOT / "data" / "extraction_json" / "text_preclean_stage2"
OVERRIDE_PATH = REPO_ROOT / "config" / "extraction" / "text_cleanup_stage2_overrides.csv"
SUBSTITUTION_PATH = REPO_ROOT / "config" / "extraction" / "text_cleanup_stage2_substitutions.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


@dataclass(frozen=True)
class SubstitutionRule:
    match_type: str
    match: str
    replacement: str
    page_index: int | None
    notes: str


@dataclass(frozen=True)
class SourceWindow:
    start_page: int | None
    end_page: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply a reviewed stage-2 text cleanup pass to selected extracted text JSON records."
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
        default=TEXT_PRECLEAN_STAGE2_DIR,
        help="Directory where stage-2 pre-clean JSON backups are stored.",
    )
    parser.add_argument(
        "--override-path",
        type=Path,
        default=OVERRIDE_PATH,
        help="CSV file containing per-paper stage-2 cleanup overrides.",
    )
    parser.add_argument(
        "--substitution-path",
        type=Path,
        default=SUBSTITUTION_PATH,
        help="CSV file containing reviewed per-paper substitutions.",
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
        help="Rebuild stage-2 cleaned JSON files from their stage-2 pre-clean backup when available.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after stage-2 cleanup.",
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


def parse_optional_int(value: str) -> int | None:
    stripped = str(value or "").strip()
    if not stripped:
        return None
    return int(stripped)


def parse_optional_bool(value: str) -> bool | None:
    stripped = str(value or "").strip()
    if not stripped:
        return None
    return truthy(stripped)


def load_substitution_rules(path: Path) -> dict[str, list[SubstitutionRule]]:
    grouped: dict[str, list[SubstitutionRule]] = {}
    if not path.exists():
        return grouped
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            paper_id = str(row.get("covidence_id") or "").strip()
            match = str(row.get("match") or "")
            if not paper_id or not match:
                continue
            grouped.setdefault(paper_id, []).append(
                SubstitutionRule(
                    match_type=(row.get("match_type") or "literal").strip() or "literal",
                    match=match,
                    replacement=str(row.get("replacement") or ""),
                    page_index=parse_optional_int(row.get("page_index") or ""),
                    notes=str(row.get("notes") or "").strip(),
                )
            )
    return grouped


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


def suspicious_control_char_count(text: str) -> int:
    return sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")


def parse_source_window(override_row: dict[str, str]) -> SourceWindow:
    return SourceWindow(
        start_page=parse_optional_int(override_row.get("source_page_start") or ""),
        end_page=parse_optional_int(override_row.get("source_page_end") or ""),
    )


def apply_source_window(
    pages: list[dict[str, Any]],
    char_counts: list[int],
    *,
    window: SourceWindow,
) -> tuple[list[dict[str, Any]], list[int]]:
    if window.start_page is None and window.end_page is None:
        return pages, char_counts

    start_index = 0 if window.start_page is None else max(window.start_page - 1, 0)
    end_index = len(pages) if window.end_page is None else min(window.end_page, len(pages))
    if start_index >= end_index:
        raise ValueError(
            f"Invalid source page window: start={window.start_page!r}, end={window.end_page!r}"
        )
    return pages[start_index:end_index], char_counts[start_index:end_index]


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


@contextmanager
def staged_pdf_for_external_tool(pdf_path: Path):
    resolved = pdf_path.resolve()
    if str(resolved).isascii():
        yield resolved
        return

    with tempfile.TemporaryDirectory() as temp_dir_name:
        staged_path = Path(temp_dir_name) / f"staged_input{resolved.suffix or '.pdf'}"
        shutil.copy2(resolved, staged_path)
        yield staged_path


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


def ensure_stage2_snapshot(text_path: Path, backup_path: Path) -> tuple[dict[str, Any], Path]:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.exists():
        return load_json_record(backup_path), backup_path

    source_record = load_json_record(text_path)
    if source_record.get("cleanup_stage2_applied"):
        raise ValueError(
            f"Canonical text JSON is already stage-2 cleaned but no stage-2 pre-clean backup exists: {text_path}"
        )
    write_json_atomic(backup_path, source_record)
    return source_record, backup_path


def extract_pages_and_counts_pdftotext(
    pdf_path: Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    with staged_pdf_for_external_tool(pdf_path) as tool_pdf_path:
        command = ["pdftotext"]
        if start_page is not None:
            command.extend(["-f", str(start_page)])
        if end_page is not None:
            command.extend(["-l", str(end_page)])
        command.extend([str(tool_pdf_path), "-"])
        proc = subprocess.run(
            command,
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
    page_index_offset = 0 if start_page is None else max(start_page - 1, 0)
    for index, text in enumerate(page_texts):
        cleaned = text.replace("\u00a0", " ").strip()
        pages.append({"page_index": page_index_offset + index, "text": cleaned})
        char_counts.append(len(cleaned))
    return pages, char_counts


def extract_pages_and_counts_tesseract(
    pdf_path: Path,
    *,
    dpi: int = 300,
    grayscale: bool = False,
    psm: int | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    with staged_pdf_for_external_tool(pdf_path) as tool_pdf_path:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            image_prefix = temp_dir / "page"
            pdftoppm_cmd = ["pdftoppm", "-r", str(dpi)]
            if grayscale:
                pdftoppm_cmd.append("-gray")
            if start_page is not None:
                pdftoppm_cmd.extend(["-f", str(start_page)])
            if end_page is not None:
                pdftoppm_cmd.extend(["-l", str(end_page)])
            pdftoppm_cmd.extend([str(tool_pdf_path), str(image_prefix)])
            subprocess.run(
                pdftoppm_cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            image_paths = sorted(path for path in temp_dir.glob("page-*") if path.is_file())
            if not image_paths:
                raise ValueError(f"pdftoppm produced no page images for: {pdf_path}")

            pages: list[dict[str, Any]] = []
            char_counts: list[int] = []
            page_index_offset = 0 if start_page is None else max(start_page - 1, 0)
            for index, image_path in enumerate(image_paths):
                tesseract_cmd = ["tesseract", str(image_path), "stdout"]
                if psm is not None:
                    tesseract_cmd.extend(["--psm", str(psm)])
                proc = subprocess.run(
                    tesseract_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                text = (proc.stdout or "").replace("\r\n", "\n").strip()
                pages.append({"page_index": page_index_offset + index, "text": text})
                char_counts.append(len(text))
            return pages, char_counts


def build_cleanup_source_record(
    raw_record: dict[str, Any],
    *,
    override_row: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    source_strategy = (override_row.get("source_strategy") or "json_cleanup").strip() or "json_cleanup"
    source_window = parse_source_window(override_row)

    if source_strategy == "json_cleanup":
        pages = [dict(page) for page in raw_record.get("pages") or []]
        char_counts = [len(str(page.get("text") or "")) for page in pages]
        pages, char_counts = apply_source_window(pages, char_counts, window=source_window)
        source_record = dict(raw_record)
        source_record["pages"] = pages
        source_record["n_pages"] = len(pages)
        source_record["page_char_counts"] = char_counts
        source_record["suspicious_control_chars"] = suspicious_control_char_count(
            "\n".join(str(page.get("text") or "") for page in pages)
        )
        return source_record, {
            "cleanup_stage2_source_strategy": source_strategy,
            "cleanup_stage2_source_pdf_path": "",
            "cleanup_stage2_source_pdf_sha256": "",
            "cleanup_stage2_source_page_start": "" if source_window.start_page is None else str(source_window.start_page),
            "cleanup_stage2_source_page_end": "" if source_window.end_page is None else str(source_window.end_page),
            "cleanup_stage2_ocr_dpi": "",
            "cleanup_stage2_ocr_psm": "",
            "cleanup_stage2_ocr_grayscale": "",
        }

    source_filename = str(raw_record.get("source_filename") or "").strip()
    if not source_filename:
        raise ValueError(f"Text JSON is missing source_filename for stage-2 strategy: {source_strategy}")
    pdf_path = PDF_DIR / source_filename
    if not pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found for stage-2 cleanup: {pdf_path}")

    if source_strategy == "pdftotext_cleanup":
        pages, char_counts = extract_pages_and_counts_pdftotext(
            pdf_path,
            start_page=source_window.start_page,
            end_page=source_window.end_page,
        )
    elif source_strategy == "ocr_cleanup":
        ocr_dpi = parse_optional_int(override_row.get("ocr_dpi") or "") or 300
        ocr_psm = parse_optional_int(override_row.get("ocr_psm") or "")
        ocr_grayscale = parse_optional_bool(override_row.get("ocr_grayscale") or "")
        pages, char_counts = extract_pages_and_counts_tesseract(
            pdf_path,
            dpi=ocr_dpi,
            grayscale=bool(ocr_grayscale),
            psm=ocr_psm,
            start_page=source_window.start_page,
            end_page=source_window.end_page,
        )
    else:
        raise ValueError(f"Unsupported stage-2 cleanup source strategy: {source_strategy}")

    if not pages:
        raise ValueError(f"Stage-2 source strategy returned no pages for: {pdf_path}")

    source_record = dict(raw_record)
    source_record["pages"] = pages
    source_record["n_pages"] = len(pages)
    source_record["page_char_counts"] = char_counts
    source_record["suspicious_control_chars"] = suspicious_control_char_count(
        "\n".join(str(page.get("text") or "") for page in pages)
    )
    return source_record, {
        "cleanup_stage2_source_strategy": source_strategy,
        "cleanup_stage2_source_pdf_path": relative_to_repo(pdf_path),
        "cleanup_stage2_source_pdf_sha256": sha256_file(pdf_path),
        "cleanup_stage2_source_page_start": "" if source_window.start_page is None else str(source_window.start_page),
        "cleanup_stage2_source_page_end": "" if source_window.end_page is None else str(source_window.end_page),
        "cleanup_stage2_ocr_dpi": str(ocr_dpi) if source_strategy == "ocr_cleanup" else "",
        "cleanup_stage2_ocr_psm": "" if source_strategy != "ocr_cleanup" or ocr_psm is None else str(ocr_psm),
        "cleanup_stage2_ocr_grayscale": "" if source_strategy != "ocr_cleanup" or ocr_grayscale is None else str(bool(ocr_grayscale)).lower(),
    }


def apply_substitution_rules(
    pages: list[dict[str, Any]],
    *,
    rules: list[SubstitutionRule],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rules:
        return [dict(page) for page in pages], []

    updated_pages = [dict(page) for page in pages]
    applied: list[dict[str, Any]] = []
    for rule in rules:
        total_count = 0
        changed_pages: list[int] = []
        for page in updated_pages:
            page_index = int(page.get("page_index", 0) or 0)
            if rule.page_index is not None and page_index != rule.page_index:
                continue
            text = str(page.get("text") or "")
            if rule.match_type == "literal":
                count = text.count(rule.match)
                if count:
                    page["text"] = text.replace(rule.match, rule.replacement)
            elif rule.match_type == "regex":
                replaced_text, count = re.subn(rule.match, rule.replacement, text)
                if count:
                    page["text"] = replaced_text
            else:
                raise ValueError(f"Unsupported substitution match_type: {rule.match_type}")
            if count:
                total_count += count
                changed_pages.append(page_index)
        if total_count:
            applied.append(
                {
                    "match_type": rule.match_type,
                    "match": rule.match,
                    "replacement": rule.replacement,
                    "page_index": rule.page_index,
                    "count": total_count,
                    "changed_pages": changed_pages,
                    "notes": rule.notes,
                }
            )
    return updated_pages, applied


def apply_stage2_cleanup_to_record(
    raw_record: dict[str, Any],
    *,
    raw_source_path: Path,
    override_row: dict[str, str],
    substitution_rules: list[SubstitutionRule],
) -> dict[str, Any]:
    source_record, source_metadata = build_cleanup_source_record(raw_record, override_row=override_row)
    pages = source_record.get("pages") or []
    if not isinstance(pages, list):
        raise ValueError("Text JSON does not contain a valid pages list.")

    profile = (override_row.get("cleanup_profile") or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    cleanup_result = clean_document_pages(pages, profile=profile)
    final_pages, applied_substitutions = apply_substitution_rules(
        cleanup_result.pages,
        rules=substitution_rules,
    )

    cleaned_record = dict(source_record)
    cleaned_record["pages"] = final_pages
    cleaned_record["n_pages"] = len(final_pages)
    cleaned_record["page_char_counts"] = [
        len(str(page.get("text") or ""))
        for page in final_pages
    ]
    cleaned_record["suspicious_control_chars"] = suspicious_control_char_count(
        "\n".join(str(page.get("text") or "") for page in final_pages)
    )
    cleaned_record["cleanup_stage2_applied"] = True
    cleaned_record["cleanup_stage2_profile"] = profile
    cleaned_record["cleanup_stage2_rules_applied"] = list(cleanup_result.rules_applied)
    cleaned_record["cleanup_stage2_applied_at_utc"] = datetime.now(timezone.utc).isoformat()
    cleaned_record["cleanup_stage2_source_json_path"] = relative_to_repo(raw_source_path)
    cleaned_record["cleanup_stage2_source_json_sha256"] = sha256_file(raw_source_path)
    cleaned_record["cleanup_stage2_source_strategy"] = source_metadata["cleanup_stage2_source_strategy"]
    cleaned_record["cleanup_stage2_source_pdf_path"] = source_metadata["cleanup_stage2_source_pdf_path"]
    cleaned_record["cleanup_stage2_source_pdf_sha256"] = source_metadata["cleanup_stage2_source_pdf_sha256"]
    cleaned_record["cleanup_stage2_source_page_start"] = source_metadata["cleanup_stage2_source_page_start"]
    cleaned_record["cleanup_stage2_source_page_end"] = source_metadata["cleanup_stage2_source_page_end"]
    cleaned_record["cleanup_stage2_ocr_dpi"] = source_metadata["cleanup_stage2_ocr_dpi"]
    cleaned_record["cleanup_stage2_ocr_psm"] = source_metadata["cleanup_stage2_ocr_psm"]
    cleaned_record["cleanup_stage2_ocr_grayscale"] = source_metadata["cleanup_stage2_ocr_grayscale"]
    cleaned_record["cleanup_stage2_changed_page_count"] = sum(
        1
        for source_page, final_page in zip(source_record["pages"], final_pages, strict=False)
        if str(source_page.get("text") or "") != str(final_page.get("text") or "")
    )
    cleaned_record["cleanup_stage2_artifact_counts_before"] = cleanup_result.artifact_counts_before
    cleaned_record["cleanup_stage2_artifact_counts_after"] = cleanup_result.artifact_counts_after
    cleaned_record["cleanup_stage2_reason"] = (override_row.get("reason") or "").strip()
    cleaned_record["cleanup_stage2_notes"] = (override_row.get("notes") or "").strip()
    cleaned_record["cleanup_stage2_substitutions_applied"] = applied_substitutions
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
    substitution_rules = load_substitution_rules(args.substitution_path)
    enabled_ids = set(overrides)
    target_paths = collect_target_json_paths(
        args.input_dir,
        enabled_ids=enabled_ids,
        paper_ids=args.paper_id,
        limit=args.limit,
    )
    if not target_paths:
        raise SystemExit(
            f"No text JSONs found in {args.input_dir} for enabled stage-2 cleanup IDs."
        )

    cleaned_count = 0
    skipped_count = 0
    for text_path in target_paths:
        current_record = load_json_record(text_path)
        backup_path = args.backup_dir / text_path.name
        if current_record.get("cleanup_stage2_applied") and not args.force:
            if not backup_path.exists():
                raise ValueError(
                    f"Canonical text JSON is already stage-2 cleaned but no stage-2 pre-clean backup exists: {text_path}"
                )
            skipped_count += 1
            continue

        # Stage 2 always rebuilds from the preserved stage-2 pre-clean snapshot so
        # reruns stay deterministic and do not compound substitutions over time.
        raw_record, raw_source_path = ensure_stage2_snapshot(text_path, backup_path)
        cleaned_record = apply_stage2_cleanup_to_record(
            raw_record,
            raw_source_path=raw_source_path,
            override_row=overrides[text_path.stem],
            substitution_rules=substitution_rules.get(text_path.stem, []),
        )
        write_json_atomic(text_path, cleaned_record)
        cleaned_count += 1

    refresh_artifact_registry(args.skip_registry_refresh)
    print(
        f"Stage-2 cleaned {cleaned_count} text JSON(s) in {args.input_dir}"
        + (f"; skipped {skipped_count} already-cleaned file(s)." if skipped_count else ".")
    )


if __name__ == "__main__":
    main()
