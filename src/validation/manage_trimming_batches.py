from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._source_routing import load_csv_rows_by_id, resolve_source_row


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
TRIMMING_QA_DIR = REPO_ROOT / "qa" / "trimming"
BATCHES_DIR = TRIMMING_QA_DIR / "batches"
FEEDBACK_DIR = TRIMMING_QA_DIR / "feedback"
REGRESSION_DIR = TRIMMING_QA_DIR / "regression"
REPORTS_DIR = TRIMMING_QA_DIR / "reports"
TRIMMER_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05_trim_proceedings_text.py"
QC_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05b_validate_proceedings_text.py"
OPEN_BATCH_STATUSES = {"prepared", "awaiting_feedback", "feedback_received", "patch_in_progress"}
RESOLVED_BATCH_STATUSES = {"resolved", "superseded", "archived"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a reproducible proceedings-trimming QA batch and run stage 05/05b on that subset."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of proceedings-detected files to include in the review batch.",
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=SOURCE_REGISTRY_PATH,
        help="Path to source_categorisation_registry.csv.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=SOURCE_MANUAL_REVIEW_PATH,
        help="Path to source_categorisation_manual_review.csv.",
    )
    parser.add_argument(
        "--batches-dir",
        type=Path,
        default=BATCHES_DIR,
        help="Directory containing batch manifests.",
    )
    parser.add_argument(
        "--feedback-dir",
        type=Path,
        default=FEEDBACK_DIR,
        help="Directory containing structured human feedback files.",
    )
    parser.add_argument(
        "--regression-dir",
        type=Path,
        default=REGRESSION_DIR,
        help="Directory containing frozen accepted regression fixtures.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Directory for per-batch non-canonical outputs and evaluation reports.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def ensure_required_directories(
    batches_dir: Path,
    feedback_dir: Path,
    regression_dir: Path,
    reports_dir: Path,
) -> None:
    for path in (batches_dir, feedback_dir, regression_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)


def load_json_objects(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    objects: list[dict[str, Any]] = []
    for json_path in sorted(path.rglob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            objects.append(payload)
    return objects


def extract_paper_ids(payload: Any) -> set[str]:
    paper_ids: set[str] = set()
    if isinstance(payload, dict):
        paper_id = str(payload.get("paper_id") or "").strip()
        if paper_id:
            paper_ids.add(paper_id)
        for value in payload.values():
            paper_ids.update(extract_paper_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            paper_ids.update(extract_paper_ids(item))
    return paper_ids


def reviewed_paper_ids(feedback_dir: Path, regression_dir: Path) -> set[str]:
    reviewed_ids: set[str] = set()
    for payload in load_json_objects(feedback_dir) + load_json_objects(regression_dir):
        reviewed_ids.update(extract_paper_ids(payload))
    return reviewed_ids


def load_batch_manifests(batches_dir: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if not batches_dir.exists():
        return manifests
    for path in sorted(batches_dir.glob("batch_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            manifests.append(payload)
    return manifests


def open_batches(batches_dir: Path) -> list[dict[str, Any]]:
    manifests = load_batch_manifests(batches_dir)
    open_items: list[dict[str, Any]] = []
    for manifest in manifests:
        status = str(manifest.get("status") or "").strip()
        if status in OPEN_BATCH_STATUSES or not status:
            open_items.append(manifest)
    return open_items


def next_batch_id(batches_dir: Path) -> str:
    numeric_ids: list[int] = []
    for path in batches_dir.glob("batch_*.json"):
        suffix = path.stem.replace("batch_", "", 1)
        if suffix.isdigit():
            numeric_ids.append(int(suffix))
    next_index = max(numeric_ids, default=0) + 1
    return f"batch_{next_index:03d}"


def resolved_conference_rows(
    source_registry_path: Path,
    source_manual_review_path: Path,
) -> list[dict[str, str]]:
    heuristic_rows = load_csv_rows_by_id(source_registry_path, "paper_id")
    manual_rows = load_csv_rows_by_id(source_manual_review_path, "paper_id")
    selected: list[dict[str, str]] = []
    for paper_id, heuristic_row in heuristic_rows.items():
        resolved = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_row,
            manual_row=manual_rows.get(paper_id, {}),
        )
        if (resolved.get("resolved_source_category") or "").strip() != "conference_abstract":
            continue
        selected.append(
            {
                "paper_id": paper_id,
                "title": (heuristic_row.get("title") or "").strip(),
                "authors": (heuristic_row.get("authors") or "").strip(),
                "source_category": (heuristic_row.get("source_category") or "").strip(),
                "resolved_source_subtype": (resolved.get("resolved_source_subtype") or "").strip(),
                "resolved_source_route_source": (resolved.get("resolved_source_route_source") or "").strip(),
            }
        )
    selected.sort(key=lambda row: int(row["paper_id"]))
    return selected


def select_unreviewed_batch(
    candidate_rows: list[dict[str, str]],
    reviewed_ids: set[str],
    batch_size: int,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in candidate_rows:
        if row["paper_id"] in reviewed_ids:
            continue
        selected.append(row)
        if len(selected) >= batch_size:
            break
    return selected


def proceedings_detected(trim_row: dict[str, str]) -> bool:
    return str(trim_row.get("proceedings_detected") or "").strip().lower() == "true"


def trim_command(
    paper_ids: list[str],
    trimmed_dir: Path,
    trim_registry_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(TRIMMER_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--output-dir",
        str(trimmed_dir),
        "--registry-path",
        str(trim_registry_path),
        "--skip-registry-refresh",
    ]


def qc_command(
    paper_ids: list[str],
    trimmed_dir: Path,
    trim_registry_path: Path,
    qc_registry_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(QC_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--trimmed-dir",
        str(trimmed_dir),
        "--text-trim-registry",
        str(trim_registry_path),
        "--output-path",
        str(qc_registry_path),
        "--skip-registry-refresh",
    ]


def screen_for_detected_batch(
    candidate_rows: list[dict[str, str]],
    batch_size: int,
    trimmed_dir: Path,
    trim_registry_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    screened_rows: list[dict[str, str]] = []
    selected_rows: list[dict[str, str]] = []
    for row in candidate_rows:
        paper_id = row["paper_id"]
        run_command(trim_command([paper_id], trimmed_dir, trim_registry_path))
        screened_rows.append(row)
        trim_row = rows_by_id(trim_registry_path).get(paper_id, {})
        if proceedings_detected(trim_row):
            selected_rows.append(row)
            if len(selected_rows) >= batch_size:
                break
    return screened_rows, selected_rows


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=str(REPO_ROOT))


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def rows_by_id(path: Path) -> dict[str, dict[str, str]]:
    return {
        (row.get("paper_id") or "").strip(): row
        for row in load_csv_rows(path)
        if (row.get("paper_id") or "").strip()
    }


def low_confidence_flag(trim_row: dict[str, str], qc_row: dict[str, str]) -> bool:
    if str(qc_row.get("manual_follow_up_required") or "").strip().lower() == "true":
        return True
    trim_status = str(trim_row.get("trim_status") or "").strip()
    if trim_status != "trimmed_auto":
        return True
    try:
        match_score = float(trim_row.get("match_score") or 0.0)
        title_score = float(trim_row.get("title_score") or 0.0)
        author_score = float(trim_row.get("author_score") or 0.0)
    except ValueError:
        return True
    return match_score < 0.75 or title_score < 0.75 or author_score < 0.35


def build_batch_report(
    batch_id: str,
    screened_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    trim_registry_path: Path,
    qc_registry_path: Path,
    trimmed_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    trim_rows = rows_by_id(trim_registry_path)
    qc_rows = rows_by_id(qc_registry_path)
    file_statuses: list[dict[str, Any]] = []
    for row in selected_rows:
        paper_id = row["paper_id"]
        trim_row = trim_rows.get(paper_id, {})
        qc_row = qc_rows.get(paper_id, {})
        trimmed_path = trimmed_dir / f"{paper_id}.json"
        file_statuses.append(
            {
                "paper_id": paper_id,
                "title": row["title"],
                "authors": row["authors"],
                "resolved_source_subtype": row["resolved_source_subtype"],
                "resolved_source_route_source": row["resolved_source_route_source"],
                "trim_status": (trim_row.get("trim_status") or "").strip(),
                "qc_status": (qc_row.get("qc_status") or "").strip(),
                "manual_follow_up_required": str(qc_row.get("manual_follow_up_required") or "").strip(),
                "low_confidence_flag": low_confidence_flag(trim_row, qc_row),
                "trimmed_text_json_path": repo_relative(trimmed_path) if trimmed_path.exists() else "",
                "match_score": (trim_row.get("match_score") or "").strip(),
                "title_score": (trim_row.get("title_score") or "").strip(),
                "author_score": (trim_row.get("author_score") or "").strip(),
                "trim_reason": (trim_row.get("trim_reason") or "").strip(),
                "qc_note": (qc_row.get("qc_note") or "").strip(),
            }
        )
    report = {
        "generated_at_utc": now_utc_iso(),
        "batch_id": batch_id,
        "file_count": len(selected_rows),
        "paper_ids": [row["paper_id"] for row in selected_rows],
        "screened_candidate_count": len(screened_rows),
        "screened_candidate_ids": [row["paper_id"] for row in screened_rows],
        "screened_out_paper_ids": [
            row["paper_id"] for row in screened_rows if row["paper_id"] not in {item["paper_id"] for item in selected_rows}
        ],
        "output_paths": {
            "trim_registry_path": repo_relative(trim_registry_path),
            "qc_registry_path": repo_relative(qc_registry_path),
            "trimmed_dir": repo_relative(trimmed_dir),
            "report_path": repo_relative(report_path),
        },
        "summary": {
            "trim_status_counts": dict(Counter(item["trim_status"] for item in file_statuses)),
            "qc_status_counts": dict(Counter(item["qc_status"] for item in file_statuses)),
            "manual_follow_up_count": sum(
                1 for item in file_statuses if str(item["manual_follow_up_required"]).lower() == "true"
            ),
            "low_confidence_count": sum(1 for item in file_statuses if item["low_confidence_flag"]),
        },
        "file_statuses": file_statuses,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def write_batch_manifest(
    manifest_path: Path,
    batch_id: str,
    screened_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    reviewed_ids: set[str],
    report_dir: Path,
    report_path: Path,
    trim_registry_path: Path,
    qc_registry_path: Path,
) -> None:
    payload = {
        "batch_id": batch_id,
        "created_at_utc": now_utc_iso(),
        "status": "awaiting_feedback",
        "paper_ids": [row["paper_id"] for row in selected_rows],
        "batch_size": len(selected_rows),
        "screened_candidate_count": len(screened_rows),
        "screened_candidate_ids": [row["paper_id"] for row in screened_rows],
        "reviewed_ids_excluded_count": len(reviewed_ids),
        "output_paths": {
            "report_dir": repo_relative(report_dir),
            "report_path": repo_relative(report_path),
            "trim_registry_path": repo_relative(trim_registry_path),
            "qc_registry_path": repo_relative(qc_registry_path),
        },
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_batch(args: argparse.Namespace) -> dict[str, Any]:
    ensure_required_directories(args.batches_dir, args.feedback_dir, args.regression_dir, args.reports_dir)
    active_batches = open_batches(args.batches_dir)
    if active_batches:
        batch_ids = ", ".join(str(item.get("batch_id") or "unknown") for item in active_batches)
        raise RuntimeError(f"Cannot open a new trimming batch while unresolved batches exist: {batch_ids}")

    reviewed_ids = reviewed_paper_ids(args.feedback_dir, args.regression_dir)
    candidate_rows = resolved_conference_rows(args.source_registry_path, args.source_manual_review_path)
    unreviewed_rows = select_unreviewed_batch(candidate_rows, reviewed_ids, len(candidate_rows))
    if not unreviewed_rows:
        raise RuntimeError("No unreviewed conference-abstract files remain for a new trimming batch.")

    batch_id = next_batch_id(args.batches_dir)
    report_dir = args.reports_dir / batch_id
    trimmed_dir = report_dir / "text_trimmed"
    trimmed_dir.mkdir(parents=True, exist_ok=True)
    trim_registry_path = report_dir / "text_trim_registry.csv"
    qc_registry_path = report_dir / "proceedings_text_qc_registry.csv"
    report_path = report_dir / "batch_report.json"
    manifest_path = args.batches_dir / f"{batch_id}.json"

    screened_rows, selected_rows = screen_for_detected_batch(
        candidate_rows=unreviewed_rows,
        batch_size=args.batch_size,
        trimmed_dir=trimmed_dir,
        trim_registry_path=trim_registry_path,
    )
    if len(selected_rows) < args.batch_size:
        raise RuntimeError(
            "Unable to prepare a full proceedings-detected trimming batch: "
            f"found {len(selected_rows)} detected files after screening {len(screened_rows)} candidates."
        )

    paper_ids = [row["paper_id"] for row in selected_rows]
    run_command(qc_command(paper_ids, trimmed_dir, trim_registry_path, qc_registry_path))
    report = build_batch_report(
        batch_id=batch_id,
        screened_rows=screened_rows,
        selected_rows=selected_rows,
        trim_registry_path=trim_registry_path,
        qc_registry_path=qc_registry_path,
        trimmed_dir=trimmed_dir,
        report_path=report_path,
    )
    write_batch_manifest(
        manifest_path=manifest_path,
        batch_id=batch_id,
        screened_rows=screened_rows,
        selected_rows=selected_rows,
        reviewed_ids=reviewed_ids,
        report_dir=report_dir,
        report_path=report_path,
        trim_registry_path=trim_registry_path,
        qc_registry_path=qc_registry_path,
    )
    return report


def main() -> None:
    args = parse_args()
    report = prepare_batch(args)
    print(f"Prepared {report['batch_id']} with {report['file_count']} files.")
    print(f"Report: {report['output_paths']['report_path']}")


if __name__ == "__main__":
    main()
