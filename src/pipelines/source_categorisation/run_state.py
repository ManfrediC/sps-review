"""Run-state helpers for resumable stage-04 LLM classification jobs."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from src.pipelines._sps_case_count_registry import write_count_rows
from src.pipelines.source_categorisation.io import write_registry


RUN_MANIFEST_FILENAME = "run_manifest.json"
RESULTS_JSONL_FILENAME = "results.jsonl"
ERRORS_CSV_FILENAME = "errors.csv"
PROGRESS_FILENAME = "progress.json"
SOURCE_SNAPSHOT_FILENAME = "source_categorisation_registry_snapshot.csv"
COUNT_SNAPSHOT_FILENAME = "source_sps_case_count_registry_snapshot.csv"

ERROR_FIELDNAMES = [
    "paper_id",
    "error_type",
    "error_message",
    "recorded_at_utc",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("stage04_llm_%Y%m%dT%H%M%SZ")


def run_dir_for(run_root: Path, run_id: str) -> Path:
    return run_root / run_id


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_manifest(
    *,
    run_id: str,
    paper_ids: list[str],
    references_csv: Path,
    input_dir: Path,
    trimmed_dir: Path,
    proceedings_ready_dir: Path,
    trim_registry_path: Path,
    proceedings_ready_registry_path: Path,
    manual_review_path: Path,
    model: str,
    skip_manual_overrides: bool,
    planned_manual_overrides: int,
    planned_llm_calls: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at_utc": now_utc_iso(),
        "paper_ids": paper_ids,
        "planned_total": len(paper_ids),
        "planned_manual_overrides": planned_manual_overrides,
        "planned_llm_calls": planned_llm_calls,
        "config": {
            "references_csv": str(references_csv),
            "input_dir": str(input_dir),
            "trimmed_dir": str(trimmed_dir),
            "proceedings_ready_dir": str(proceedings_ready_dir),
            "trim_registry_path": str(trim_registry_path),
            "proceedings_ready_registry_path": str(proceedings_ready_registry_path),
            "manual_review_path": str(manual_review_path),
            "model": model,
            "skip_manual_overrides": skip_manual_overrides,
        },
    }


def initialise_run(run_root: Path, manifest: dict[str, Any], *, resume: bool) -> Path:
    run_id = str(manifest["run_id"])
    run_dir = run_dir_for(run_root, run_id)
    manifest_path = run_dir / RUN_MANIFEST_FILENAME
    if resume:
        if not manifest_path.exists():
            raise SystemExit(f"Cannot resume missing run manifest: {manifest_path}")
        return run_dir

    if run_dir.exists():
        raise SystemExit(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(manifest_path, manifest)
    write_progress(run_dir, manifest=manifest, completed_paper_ids=[], error_count=0)
    return run_dir


def load_run_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / RUN_MANIFEST_FILENAME
    if not manifest_path.exists():
        raise SystemExit(f"Run manifest not found: {manifest_path}")
    return _read_json(manifest_path)


def append_result_record(run_dir: Path, payload: dict[str, Any]) -> None:
    output_path = run_dir / RESULTS_JSONL_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_result_records(run_dir: Path) -> list[dict[str, Any]]:
    output_path = run_dir / RESULTS_JSONL_FILENAME
    if not output_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with output_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def result_records_by_id(run_dir: Path) -> dict[str, dict[str, Any]]:
    records_by_id: dict[str, dict[str, Any]] = {}
    for record in load_result_records(run_dir):
        paper_id = str(record.get("paper_id") or "").strip()
        if paper_id:
            records_by_id[paper_id] = record
    return records_by_id


def completed_paper_ids(run_dir: Path) -> list[str]:
    return list(result_records_by_id(run_dir))


def append_error_row(
    run_dir: Path,
    *,
    paper_id: str,
    error_type: str,
    error_message: str,
) -> None:
    output_path = run_dir / ERRORS_CSV_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "paper_id": paper_id,
        "error_type": error_type,
        "error_message": error_message,
        "recorded_at_utc": now_utc_iso(),
    }
    write_header = not output_path.exists()
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ERROR_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def load_error_rows(run_dir: Path) -> list[dict[str, str]]:
    output_path = run_dir / ERRORS_CSV_FILENAME
    if not output_path.exists():
        return []
    with output_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def materialise_run_snapshots(
    run_dir: Path,
    *,
    manifest: dict[str, Any],
) -> None:
    ordered_ids = [str(paper_id) for paper_id in manifest.get("paper_ids", [])]
    records_by_id = result_records_by_id(run_dir)
    source_rows = [
        dict(records_by_id[paper_id]["source_row"])
        for paper_id in ordered_ids
        if paper_id in records_by_id
    ]
    count_rows = [
        dict(records_by_id[paper_id]["count_row"])
        for paper_id in ordered_ids
        if paper_id in records_by_id
    ]
    write_registry(source_rows, run_dir / SOURCE_SNAPSHOT_FILENAME)
    write_count_rows(count_rows, run_dir / COUNT_SNAPSHOT_FILENAME)


def write_progress(
    run_dir: Path,
    *,
    manifest: dict[str, Any],
    completed_paper_ids: list[str],
    error_count: int,
    last_completed_paper_id: str = "",
    published_at_utc: str = "",
) -> None:
    planned_ids = [str(paper_id) for paper_id in manifest.get("paper_ids", [])]
    payload = {
        "run_id": str(manifest.get("run_id") or ""),
        "updated_at_utc": now_utc_iso(),
        "planned_total": len(planned_ids),
        "completed_total": len(completed_paper_ids),
        "pending_total": max(len(planned_ids) - len(completed_paper_ids), 0),
        "error_total": error_count,
        "last_completed_paper_id": last_completed_paper_id,
        "published_at_utc": published_at_utc,
    }
    _write_json(run_dir / PROGRESS_FILENAME, payload)


def publish_run_outputs(
    *,
    run_dir: Path,
    manifest: dict[str, Any],
    output_path: Path,
    count_output_path: Path,
) -> tuple[int, int]:
    ordered_ids = [str(paper_id) for paper_id in manifest.get("paper_ids", [])]
    records_by_id = result_records_by_id(run_dir)
    completed_ids = set(records_by_id)
    planned_ids = set(ordered_ids)
    missing_ids = [paper_id for paper_id in ordered_ids if paper_id not in completed_ids]
    if missing_ids:
        raise SystemExit(
            "Cannot publish an incomplete run. Missing paper IDs: "
            + ", ".join(missing_ids[:10])
            + (" ..." if len(missing_ids) > 10 else "")
        )

    source_rows = [dict(records_by_id[paper_id]["source_row"]) for paper_id in ordered_ids]
    count_rows = [dict(records_by_id[paper_id]["count_row"]) for paper_id in ordered_ids]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count_output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=output_path.parent) as handle:
        temp_source_path = Path(handle.name)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=count_output_path.parent) as handle:
        temp_count_path = Path(handle.name)

    write_registry(source_rows, temp_source_path)
    write_count_rows(count_rows, temp_count_path)
    temp_source_path.replace(output_path)
    temp_count_path.replace(count_output_path)
    return len(source_rows), len(count_rows)
