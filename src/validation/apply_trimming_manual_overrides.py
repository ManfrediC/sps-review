from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._proceedings_text import flatten_lines, normalize_text
from src.validation import _stage05_review as review


REPO_ROOT = Path(__file__).resolve().parents[2]
QC_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05b_validate_proceedings_text.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply fallback per-paper manual overrides for a reviewed stage-05 batch and re-run QC."
    )
    parser.add_argument(
        "--batch-id",
        required=True,
        help="Batch identifier such as batch_009.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=review.REPORTS_DIR,
        help="Root directory containing per-batch stage-05 reports.",
    )
    parser.add_argument(
        "--batches-dir",
        type=Path,
        default=review.BATCHES_DIR,
        help="Directory containing batch manifests.",
    )
    parser.add_argument(
        "--only-enabled",
        action="store_true",
        help="Only apply rows where override_enabled is true.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def collapse_alnum(text: str) -> str:
    return "".join(ch for ch in normalize_text(text) if ch.isalnum())


def anchor_matches(line_text: str, anchor_text: str) -> bool:
    normal_line = normalize_text(line_text)
    normal_anchor = normalize_text(anchor_text)
    if not normal_anchor:
        return False
    if normal_anchor in normal_line or normal_line in normal_anchor:
        return True
    compact_line = collapse_alnum(line_text)
    compact_anchor = collapse_alnum(anchor_text)
    if compact_anchor and (compact_anchor in compact_line or compact_line in compact_anchor):
        return True
    return SequenceMatcher(None, normal_line, normal_anchor).ratio() >= 0.88


def locate_anchor_index(lines: list[Any], anchor_text: str, *, start_index: int = 0) -> int | None:
    if not anchor_text.strip():
        return None
    for index in range(start_index, len(lines)):
        if anchor_matches(lines[index].text, anchor_text):
            return index
    return None


def build_trimmed_pages(source_record: dict[str, Any], selected_lines: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = {}
    source_pages = {int(page.get("page_index") or 0): page for page in source_record.get("pages") or []}
    for line in selected_lines:
        grouped.setdefault(int(line.page_index), []).append(line.text)
    pages: list[dict[str, Any]] = []
    for page_index in sorted(grouped):
        source_page = source_pages.get(page_index, {})
        pages.append(
            {
                "page_index": page_index,
                "page_num": source_page.get("page_num"),
                "text": "\n".join(grouped[page_index]),
            }
        )
    return pages


def build_manual_trimmed_record(
    *,
    source_record: dict[str, Any],
    source_path: Path,
    queue_row: dict[str, str],
    selected_lines: list[Any],
) -> dict[str, Any]:
    start_line = selected_lines[0]
    end_line = selected_lines[-1]
    return {
        "paper_id": str(source_record.get("paper_id") or source_path.stem),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_sha256": str(source_record.get("source_sha256") or ""),
        "n_pages": len({int(line.page_index) for line in selected_lines}),
        "pages": build_trimmed_pages(source_record, selected_lines),
        "trim_status": "trimmed_manual_override",
        "trim_reason": "Manual override derived from reviewed stage-05 anchors.",
        "trim_method": "manual_override",
        "trim_mode": "manual_override",
        "matched_block_code": "",
        "matched_block_title": str(queue_row.get("title") or "").strip(),
        "match_score": 1.0,
        "title_score": 1.0,
        "author_score": 1.0,
        "start_page_index": int(start_line.page_index),
        "end_page_index": int(end_line.page_index),
        "start_line_global_index": int(start_line.global_index),
        "end_line_global_index_exclusive": int(end_line.global_index) + 1,
        "start_rule": "manual_override_start_anchor",
        "end_rule": "manual_override_end_anchor",
        "body_signal_count": "",
        "spillover_flag": False,
        "header_only_flag": False,
        "trimmed_at_utc": now_utc_iso(),
    }


def load_csv_with_fieldnames(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv_with_fieldnames(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_trim_registry_row(
    trim_registry_path: Path,
    *,
    paper_id: str,
    trimmed_path: Path,
    start_page_index: int,
    end_page_index: int,
    start_line_index: int,
    end_line_index_exclusive: int,
) -> None:
    fieldnames, rows = load_csv_with_fieldnames(trim_registry_path)
    if not rows:
        raise FileNotFoundError(f"Trim registry not found or empty: {trim_registry_path}")
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("paper_id") or "").strip() == paper_id:
            row = {
                **row,
                "trimmed_text_json_path": repo_relative(trimmed_path),
                "trim_status": "trimmed_manual_override",
                "trim_reason": "Manual override derived from reviewed stage-05 anchors.",
                "trim_method": "manual_override",
                "trim_mode": "manual_override",
                "start_page_index": str(start_page_index),
                "end_page_index": str(end_page_index),
                "start_line_global_index": str(start_line_index),
                "end_line_global_index_exclusive": str(end_line_index_exclusive),
                "trimmed_at_utc": now_utc_iso(),
            }
        updated_rows.append(row)
    write_csv_with_fieldnames(trim_registry_path, fieldnames, updated_rows)


def update_override_rows(
    overrides_path: Path,
    statuses: dict[str, tuple[str, str]],
) -> None:
    fieldnames, rows = load_csv_with_fieldnames(overrides_path)
    if not fieldnames:
        fieldnames = review.manual_override_fieldnames()
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id in statuses:
            override_status, applied_at = statuses[paper_id]
            row = {
                **row,
                "override_status": override_status,
                "override_applied_at_utc": applied_at,
            }
        updated_rows.append(row)
    write_csv_with_fieldnames(overrides_path, fieldnames, updated_rows)


def update_manifest_status(manifest_path: Path, status: str) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["status"] = status
    payload["last_updated_at_utc"] = now_utc_iso()
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def qc_command(paper_id: str, report_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(QC_SCRIPT),
        "--paper-id",
        paper_id,
        "--trimmed-dir",
        str(report_dir / "text_trimmed"),
        "--text-trim-registry",
        str(report_dir / "text_trim_registry.csv"),
        "--output-path",
        str(report_dir / "proceedings_text_qc_registry.csv"),
        "--skip-registry-refresh",
    ]


def apply_override_for_row(
    queue_row: dict[str, str],
    override_row: dict[str, str],
    report_dir: Path,
) -> tuple[bool, str]:
    source_text_json_path = str(queue_row.get("source_text_json_path") or "").strip()
    if not source_text_json_path:
        return False, "Missing source text JSON path."
    source_path = review.resolve_repo_path(source_text_json_path)
    if not source_path.exists():
        return False, f"Source text JSON not found: {source_text_json_path}"

    source_record = json.loads(source_path.read_text(encoding="utf-8"))
    source_lines = flatten_lines(source_record)
    corrected_start_text = str(override_row.get("corrected_start_text") or "").strip()
    corrected_end_text = str(override_row.get("corrected_end_text") or "").strip()
    if not corrected_start_text or not corrected_end_text:
        return False, "Both corrected start and corrected end anchors are required."

    start_index = locate_anchor_index(source_lines, corrected_start_text)
    if start_index is None:
        return False, "Could not locate the corrected start anchor in the source text."
    end_index = locate_anchor_index(source_lines, corrected_end_text, start_index=start_index)
    if end_index is None:
        return False, "Could not locate the corrected end anchor in the source text."
    if end_index < start_index:
        return False, "Corrected end anchor appears before the corrected start anchor."

    selected_lines = source_lines[start_index : end_index + 1]
    if not selected_lines:
        return False, "Manual override selected an empty span."

    trimmed_record = build_manual_trimmed_record(
        source_record=source_record,
        source_path=source_path,
        queue_row=queue_row,
        selected_lines=selected_lines,
    )
    paper_id = str(queue_row.get("paper_id") or "").strip()
    trimmed_path = report_dir / "text_trimmed" / f"{paper_id}.json"
    trimmed_path.parent.mkdir(parents=True, exist_ok=True)
    trimmed_path.write_text(json.dumps(trimmed_record, ensure_ascii=False, indent=2), encoding="utf-8")
    update_trim_registry_row(
        report_dir / "text_trim_registry.csv",
        paper_id=paper_id,
        trimmed_path=trimmed_path,
        start_page_index=int(selected_lines[0].page_index),
        end_page_index=int(selected_lines[-1].page_index),
        start_line_index=int(selected_lines[0].global_index),
        end_line_index_exclusive=int(selected_lines[-1].global_index) + 1,
    )
    return True, ""


def main() -> None:
    args = parse_args()
    report_dir = args.reports_dir / args.batch_id
    manifest_path = args.batches_dir / f"{args.batch_id}.json"
    queue_rows = review.load_review_queue_rows(report_dir)
    override_rows_by_id = review.load_manual_overrides_by_id(report_dir)
    queue_by_id = {str(row.get("paper_id") or "").strip(): row for row in queue_rows}

    update_manifest_status(manifest_path, "override_in_progress")
    override_statuses: dict[str, tuple[str, str]] = {}
    rerun_paper_ids: list[str] = []

    for paper_id, override_row in override_rows_by_id.items():
        if args.only_enabled and not review.truthy(override_row.get("override_enabled") or ""):
            continue
        queue_row = queue_by_id.get(paper_id, {})
        if not queue_row:
            override_statuses[paper_id] = ("missing_queue_row", now_utc_iso())
            continue
        ok, error_message = apply_override_for_row(queue_row, override_row, report_dir)
        if ok:
            rerun_paper_ids.append(paper_id)
            override_statuses[paper_id] = ("applied", now_utc_iso())
        else:
            override_statuses[paper_id] = (error_message, now_utc_iso())

    update_override_rows(review.manual_overrides_path(report_dir), override_statuses)

    for paper_id in rerun_paper_ids:
        subprocess.run(qc_command(paper_id, report_dir), check=True, cwd=str(REPO_ROOT))

    review.refresh_review_materials(batch_id=args.batch_id, report_dir=report_dir)
    update_manifest_status(manifest_path, "feedback_received")

    print(f"Applied overrides for {len(rerun_paper_ids)} paper(s) in {args.batch_id}.")
    print(f"Acceptance: {review.display_path(review.acceptance_report_path(report_dir))}")


if __name__ == "__main__":
    main()
