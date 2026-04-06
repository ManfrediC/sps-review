from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.validation import _stage04_gold as gold
from src.validation.stage04_model_benchmark import _shared as shared


REVIEW_NOTES_FILENAME = "review_notes.csv"
DEFAULT_REVIEW_STATUS = "pending"
REVIEW_STATUS_OPTIONS = ("pending", "reviewed", "flagged")
MODEL_DISPLAY_ORDER = tuple(shared.BENCHMARK_MODELS)

display_path = gold.display_path
resolve_repo_path = gold.resolve_repo_path
load_text_page_entries = gold.load_text_page_entries
search_text_page_entries = gold.search_text_page_entries


def discover_benchmark_directories(root: Path = shared.BENCHMARK_ROOT) -> list[Path]:
    if not root.exists():
        return []
    benchmark_dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "benchmark_set.csv").exists()
    ]
    return sorted(benchmark_dirs)


def benchmark_label(path: Path) -> str:
    return path.name


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_predictions_by_model(paths: shared.BenchmarkPaths) -> dict[str, dict[str, dict[str, Any]]]:
    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    for model_name in MODEL_DISPLAY_ORDER:
        rows = load_jsonl_rows(paths.model_output_root / model_name / "predictions.jsonl")
        if rows:
            predictions[model_name] = {
                str(row.get("paper_id") or "").strip(): row
                for row in rows
                if str(row.get("paper_id") or "").strip()
            }
    return predictions


def review_notes_path(paths: shared.BenchmarkPaths) -> Path:
    return paths.benchmark_dir / REVIEW_NOTES_FILENAME


def load_review_notes_by_id(paths: shared.BenchmarkPaths) -> dict[str, dict[str, str]]:
    path = review_notes_path(paths)
    if not path.exists():
        return {}
    rows = shared.load_csv_rows(path)
    return {
        (row.get("paper_id") or "").strip(): row
        for row in rows
        if (row.get("paper_id") or "").strip()
    }


def write_review_notes(paths: shared.BenchmarkPaths, rows_by_id: dict[str, dict[str, str]]) -> None:
    fieldnames = [
        "benchmark_id",
        "paper_id",
        "review_status",
        "review_notes",
        "updated_at_utc",
    ]
    rows = [
        rows_by_id[paper_id]
        for paper_id in sorted(rows_by_id, key=lambda value: shared.parse_int(value, default=10**9))
    ]
    shared.write_csv_rows(review_notes_path(paths), rows, fieldnames)


def build_review_note_row(
    *,
    benchmark_id: str,
    paper_id: str,
    review_status: str,
    review_notes: str,
) -> dict[str, str]:
    return {
        "benchmark_id": benchmark_id,
        "paper_id": paper_id,
        "review_status": review_status,
        "review_notes": review_notes.strip(),
        "updated_at_utc": shared.now_utc_iso(),
    }


def note_status_counts(
    benchmark_rows: list[dict[str, str]],
    notes_by_id: dict[str, dict[str, str]],
) -> dict[str, int]:
    counts = {status: 0 for status in REVIEW_STATUS_OPTIONS}
    for row in benchmark_rows:
        paper_id = (row.get("paper_id") or "").strip()
        status = (
            (notes_by_id.get(paper_id, {}).get("review_status") or DEFAULT_REVIEW_STATUS)
            .strip()
            .lower()
        )
        if status not in counts:
            status = DEFAULT_REVIEW_STATUS
        counts[status] += 1
    return counts


def model_prediction_for_paper(
    predictions_by_model: dict[str, dict[str, dict[str, Any]]],
    *,
    model_name: str,
    paper_id: str,
) -> dict[str, Any] | None:
    return predictions_by_model.get(model_name, {}).get(paper_id)

