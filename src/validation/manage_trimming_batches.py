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
CANDIDATE_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05_trim_proceedings_text_LLM.py"
VALIDATE_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05b_validate_proceedings_text_LLM.py"
PUBLISH_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05c_publish_proceedings_ready.py"
PROCESSING_BATCH_STATUSES = {
    "candidate_generation_running",
    "llm_validation_running",
    "publish_running",
    "override_in_progress",
}
REVIEW_BATCH_STATUSES = {"awaiting_review", "feedback_received", "resolved"}
OPEN_BATCH_STATUSES = PROCESSING_BATCH_STATUSES | {"awaiting_review", "feedback_received"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a resumable stage-05 LLM proceedings batch and publish batch-local ready outputs."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of proceedings candidate packages to include in the review batch.",
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
        help="Directory containing structured human feedback files used to exclude already reviewed papers.",
    )
    parser.add_argument(
        "--regression-dir",
        type=Path,
        default=REGRESSION_DIR,
        help="Directory containing frozen accepted regression fixtures used to exclude already reviewed papers.",
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
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


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
    return [
        manifest
        for manifest in manifests
        if str(manifest.get("status") or "").strip() in OPEN_BATCH_STATUSES or not str(manifest.get("status") or "").strip()
    ]


def next_batch_id(batches_dir: Path) -> str:
    numeric_ids: list[int] = []
    for path in batches_dir.glob("batch_*.json"):
        suffix = path.stem.replace("batch_", "", 1)
        if suffix.isdigit():
            numeric_ids.append(int(suffix))
    return f"batch_{max(numeric_ids, default=0) + 1:03d}"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def rows_by_id(path: Path) -> dict[str, dict[str, str]]:
    return {
        str(row.get("paper_id") or "").strip(): row
        for row in load_csv_rows(path)
        if str(row.get("paper_id") or "").strip()
    }


def candidate_package_created(candidate_row: dict[str, str]) -> bool:
    return str(candidate_row.get("trim_status") or "").strip() == "candidate_package_created"


def candidate_command(
    paper_ids: list[str],
    candidate_dir: Path,
    candidate_registry_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(CANDIDATE_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--candidate-output-dir",
        str(candidate_dir),
        "--candidate-registry-path",
        str(candidate_registry_path),
        "--skip-registry-refresh",
    ]


def validate_command(
    paper_ids: list[str],
    candidate_dir: Path,
    llm_dir: Path,
    llm_registry_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(VALIDATE_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--candidate-input-dir",
        str(candidate_dir),
        "--output-dir",
        str(llm_dir),
        "--registry-path",
        str(llm_registry_path),
        "--skip-registry-refresh",
    ]


def publish_command(
    paper_ids: list[str],
    candidate_registry_path: Path,
    llm_dir: Path,
    llm_registry_path: Path,
    ready_dir: Path,
    ready_registry_path: Path,
) -> list[str]:
    return [
        sys.executable,
        str(PUBLISH_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--llm-candidate-registry-path",
        str(candidate_registry_path),
        "--llm-trimmed-dir",
        str(llm_dir),
        "--llm-registry-path",
        str(llm_registry_path),
        "--output-dir",
        str(ready_dir),
        "--output-path",
        str(ready_registry_path),
        "--skip-registry-refresh",
    ]


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=str(REPO_ROOT))


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


def manifest_output_paths(
    *,
    report_dir: Path,
    report_path: Path,
    candidate_dir: Path,
    candidate_registry_path: Path,
    llm_dir: Path,
    llm_registry_path: Path,
    ready_dir: Path,
    ready_registry_path: Path,
) -> dict[str, str]:
    return {
        "report_dir": repo_relative(report_dir),
        "report_path": repo_relative(report_path),
        "candidate_output_dir": repo_relative(candidate_dir),
        "candidate_registry_path": repo_relative(candidate_registry_path),
        "llm_output_dir": repo_relative(llm_dir),
        "llm_registry_path": repo_relative(llm_registry_path),
        "ready_output_dir": repo_relative(ready_dir),
        "ready_registry_path": repo_relative(ready_registry_path),
    }


def initial_manifest_payload(
    *,
    batch_id: str,
    batch_size: int,
    reviewed_ids: set[str],
    report_dir: Path,
    report_path: Path,
    candidate_dir: Path,
    candidate_registry_path: Path,
    llm_dir: Path,
    llm_registry_path: Path,
    ready_dir: Path,
    ready_registry_path: Path,
) -> dict[str, Any]:
    now = now_utc_iso()
    return {
        "batch_id": batch_id,
        "created_at_utc": now,
        "last_updated_at_utc": now,
        "status": "candidate_generation_running",
        "batch_size_target": batch_size,
        "batch_size": 0,
        "paper_ids": [],
        "screened_candidate_ids": [],
        "screened_candidate_count": 0,
        "reviewed_ids_excluded_count": len(reviewed_ids),
        "llm_completed_paper_ids": [],
        "published_paper_ids": [],
        "output_paths": manifest_output_paths(
            report_dir=report_dir,
            report_path=report_path,
            candidate_dir=candidate_dir,
            candidate_registry_path=candidate_registry_path,
            llm_dir=llm_dir,
            llm_registry_path=llm_registry_path,
            ready_dir=ready_dir,
            ready_registry_path=ready_registry_path,
        ),
    }


def write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    payload["last_updated_at_utc"] = now_utc_iso()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_manifest(
    manifest_path: Path,
    payload: dict[str, Any],
    *,
    status: str | None = None,
    screened_candidate_ids: list[str] | None = None,
    paper_ids: list[str] | None = None,
    llm_completed_paper_ids: list[str] | None = None,
    published_paper_ids: list[str] | None = None,
) -> dict[str, Any]:
    if status is not None:
        payload["status"] = status
    if screened_candidate_ids is not None:
        payload["screened_candidate_ids"] = screened_candidate_ids
        payload["screened_candidate_count"] = len(screened_candidate_ids)
    if paper_ids is not None:
        payload["paper_ids"] = paper_ids
        payload["batch_size"] = len(paper_ids)
    if llm_completed_paper_ids is not None:
        payload["llm_completed_paper_ids"] = llm_completed_paper_ids
    if published_paper_ids is not None:
        payload["published_paper_ids"] = published_paper_ids
    write_manifest(manifest_path, payload)
    return payload


def screen_for_candidate_batch(
    *,
    candidate_rows: list[dict[str, str]],
    batch_size: int,
    candidate_dir: Path,
    candidate_registry_path: Path,
    manifest_path: Path,
    manifest_payload: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    candidate_by_id = {row["paper_id"]: row for row in candidate_rows}
    screened_candidate_ids = list(manifest_payload.get("screened_candidate_ids") or [])
    screened_set = set(screened_candidate_ids)
    selected_paper_ids = list(manifest_payload.get("paper_ids") or [])
    selected_set = set(selected_paper_ids)

    for row in candidate_rows:
        paper_id = row["paper_id"]
        if len(selected_paper_ids) >= batch_size:
            break
        if paper_id in screened_set:
            continue
        run_command(candidate_command([paper_id], candidate_dir, candidate_registry_path))
        screened_candidate_ids.append(paper_id)
        screened_set.add(paper_id)
        candidate_row = rows_by_id(candidate_registry_path).get(paper_id, {})
        if candidate_package_created(candidate_row) and paper_id not in selected_set:
            selected_paper_ids.append(paper_id)
            selected_set.add(paper_id)
        manifest_payload = update_manifest(
            manifest_path,
            manifest_payload,
            status="candidate_generation_running",
            screened_candidate_ids=screened_candidate_ids,
            paper_ids=selected_paper_ids,
        )

    screened_rows = [candidate_by_id[paper_id] for paper_id in screened_candidate_ids if paper_id in candidate_by_id]
    selected_rows = [candidate_by_id[paper_id] for paper_id in selected_paper_ids if paper_id in candidate_by_id]
    return screened_rows, selected_rows, manifest_payload


def run_incremental_validation_and_publish(
    *,
    selected_rows: list[dict[str, str]],
    candidate_dir: Path,
    candidate_registry_path: Path,
    llm_dir: Path,
    llm_registry_path: Path,
    ready_dir: Path,
    ready_registry_path: Path,
    manifest_path: Path,
    manifest_payload: dict[str, Any],
) -> dict[str, Any]:
    llm_completed_ids = list(manifest_payload.get("llm_completed_paper_ids") or [])
    llm_completed_set = set(llm_completed_ids)
    published_ids = list(manifest_payload.get("published_paper_ids") or [])
    published_set = set(published_ids)
    existing_llm_rows = rows_by_id(llm_registry_path)
    existing_ready_rows = rows_by_id(ready_registry_path)

    for row in selected_rows:
        paper_id = row["paper_id"]
        if paper_id not in llm_completed_set and paper_id not in existing_llm_rows:
            run_command(validate_command([paper_id], candidate_dir, llm_dir, llm_registry_path))
            llm_completed_ids.append(paper_id)
            llm_completed_set.add(paper_id)
            manifest_payload = update_manifest(
                manifest_path,
                manifest_payload,
                status="llm_validation_running",
                llm_completed_paper_ids=llm_completed_ids,
            )
        elif paper_id not in llm_completed_set:
            llm_completed_ids.append(paper_id)
            llm_completed_set.add(paper_id)

        if paper_id not in published_set and paper_id not in existing_ready_rows:
            run_command(
                publish_command(
                    [paper_id],
                    candidate_registry_path,
                    llm_dir,
                    llm_registry_path,
                    ready_dir,
                    ready_registry_path,
                )
            )
            published_ids.append(paper_id)
            published_set.add(paper_id)
            manifest_payload = update_manifest(
                manifest_path,
                manifest_payload,
                status="publish_running",
                published_paper_ids=published_ids,
            )
        elif paper_id not in published_set:
            published_ids.append(paper_id)
            published_set.add(paper_id)

    return update_manifest(
        manifest_path,
        manifest_payload,
        status="publish_running",
        llm_completed_paper_ids=llm_completed_ids,
        published_paper_ids=published_ids,
    )


def build_batch_report(
    batch_id: str,
    screened_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    candidate_registry_path: Path,
    llm_registry_path: Path,
    ready_registry_path: Path,
    candidate_dir: Path,
    llm_dir: Path,
    ready_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    candidate_rows = rows_by_id(candidate_registry_path)
    final_rows = rows_by_id(llm_registry_path)
    ready_rows = rows_by_id(ready_registry_path)
    file_statuses: list[dict[str, Any]] = []
    for row in selected_rows:
        paper_id = row["paper_id"]
        candidate_row = candidate_rows.get(paper_id, {})
        final_row = final_rows.get(paper_id, {})
        ready_row = ready_rows.get(paper_id, {})
        candidate_json_path = candidate_dir / f"{paper_id}.json"
        llm_json_path = llm_dir / f"{paper_id}.json"
        ready_json_path = ready_dir / f"{paper_id}.json"
        file_statuses.append(
            {
                "paper_id": paper_id,
                "title": row["title"],
                "authors": row["authors"],
                "resolved_source_subtype": row["resolved_source_subtype"],
                "resolved_source_route_source": row["resolved_source_route_source"],
                "source_text_json_path": str(candidate_row.get("source_text_json_path") or "").strip(),
                "candidate_trim_status": str(candidate_row.get("trim_status") or "").strip(),
                "candidate_count": str(candidate_row.get("candidate_count") or "").strip(),
                "candidate_json_path": repo_relative(candidate_json_path) if candidate_json_path.exists() else "",
                "candidate_heuristics": str(candidate_row.get("candidate_heuristics") or "").strip(),
                "final_trim_status": str(final_row.get("trim_status") or "").strip(),
                "final_trimmed_text_json_path": repo_relative(llm_json_path) if llm_json_path.exists() else "",
                "llm_validation_passed": str(final_row.get("llm_validation_passed") or "").strip(),
                "llm_validation_reason": str(final_row.get("llm_validation_reason") or "").strip(),
                "heuristic_fallback_used": str(final_row.get("heuristic_fallback_used") or "").strip(),
                "ready_text_json_path": repo_relative(ready_json_path) if ready_json_path.exists() else "",
                "ready_source_kind": str(ready_row.get("ready_source_kind") or "").strip(),
                "ready_text_mode": str(ready_row.get("ready_text_mode") or "").strip(),
                "ready_reason": str(ready_row.get("ready_reason") or "").strip(),
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
            "candidate_registry_path": repo_relative(candidate_registry_path),
            "llm_registry_path": repo_relative(llm_registry_path),
            "ready_registry_path": repo_relative(ready_registry_path),
            "candidate_output_dir": repo_relative(candidate_dir),
            "llm_output_dir": repo_relative(llm_dir),
            "ready_output_dir": repo_relative(ready_dir),
            "report_path": repo_relative(report_path),
        },
        "summary": {
            "candidate_trim_status_counts": dict(Counter(item["candidate_trim_status"] for item in file_statuses)),
            "final_trim_status_counts": dict(Counter(item["final_trim_status"] for item in file_statuses)),
            "ready_source_kind_counts": dict(Counter(item["ready_source_kind"] for item in file_statuses)),
            "llm_validation_passed_counts": dict(Counter(item["llm_validation_passed"] for item in file_statuses)),
        },
        "file_statuses": file_statuses,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def resume_or_prepare_batch(
    *,
    args: argparse.Namespace,
    manifest_payload: dict[str, Any],
    manifest_path: Path,
    candidate_rows: list[dict[str, str]],
) -> dict[str, Any]:
    batch_id = str(manifest_payload.get("batch_id") or "").strip()
    report_dir = args.reports_dir / batch_id
    candidate_dir = report_dir / "text_trimmed_llm_candidates"
    llm_dir = report_dir / "text_trimmed_llm"
    ready_dir = report_dir / "text_proceedings_ready"
    for path in (candidate_dir, llm_dir, ready_dir):
        path.mkdir(parents=True, exist_ok=True)
    candidate_registry_path = report_dir / "text_trim_llm_candidate_registry.csv"
    llm_registry_path = report_dir / "text_trim_llm_registry.csv"
    ready_registry_path = report_dir / "text_proceedings_ready_registry.csv"
    report_path = report_dir / "batch_report.json"

    screened_rows, selected_rows, manifest_payload = screen_for_candidate_batch(
        candidate_rows=candidate_rows,
        batch_size=args.batch_size,
        candidate_dir=candidate_dir,
        candidate_registry_path=candidate_registry_path,
        manifest_path=manifest_path,
        manifest_payload=manifest_payload,
    )
    if len(selected_rows) < args.batch_size:
        raise RuntimeError(
            "Unable to prepare a full stage-05 LLM review batch: "
            f"found {len(selected_rows)} candidate packages after screening {len(screened_rows)} conference abstracts."
        )

    manifest_payload = update_manifest(
        manifest_path,
        manifest_payload,
        status="llm_validation_running",
        paper_ids=[row["paper_id"] for row in selected_rows],
        screened_candidate_ids=[row["paper_id"] for row in screened_rows],
    )
    manifest_payload = run_incremental_validation_and_publish(
        selected_rows=selected_rows,
        candidate_dir=candidate_dir,
        candidate_registry_path=candidate_registry_path,
        llm_dir=llm_dir,
        llm_registry_path=llm_registry_path,
        ready_dir=ready_dir,
        ready_registry_path=ready_registry_path,
        manifest_path=manifest_path,
        manifest_payload=manifest_payload,
    )
    report = build_batch_report(
        batch_id=batch_id,
        screened_rows=screened_rows,
        selected_rows=selected_rows,
        candidate_registry_path=candidate_registry_path,
        llm_registry_path=llm_registry_path,
        ready_registry_path=ready_registry_path,
        candidate_dir=candidate_dir,
        llm_dir=llm_dir,
        ready_dir=ready_dir,
        report_path=report_path,
    )
    update_manifest(
        manifest_path,
        manifest_payload,
        status="awaiting_review",
        paper_ids=report["paper_ids"],
        screened_candidate_ids=report["screened_candidate_ids"],
        published_paper_ids=report["paper_ids"],
    )
    return report


def prepare_batch(args: argparse.Namespace) -> dict[str, Any]:
    ensure_required_directories(args.batches_dir, args.feedback_dir, args.regression_dir, args.reports_dir)
    active_batches = open_batches(args.batches_dir)
    if len(active_batches) > 1:
        batch_ids = ", ".join(str(item.get("batch_id") or "unknown") for item in active_batches)
        raise RuntimeError(f"Cannot continue trimming while multiple unresolved batches exist: {batch_ids}")

    reviewed_ids = reviewed_paper_ids(args.feedback_dir, args.regression_dir)
    conference_rows = resolved_conference_rows(args.source_registry_path, args.source_manual_review_path)
    unreviewed_rows = select_unreviewed_batch(conference_rows, reviewed_ids, len(conference_rows))
    if not unreviewed_rows:
        raise RuntimeError("No unreviewed conference-abstract files remain for a new trimming batch.")

    if active_batches:
        active_batch = active_batches[0]
        active_status = str(active_batch.get("status") or "").strip()
        if active_status in PROCESSING_BATCH_STATUSES or not active_status:
            manifest_path = args.batches_dir / f"{active_batch['batch_id']}.json"
            return resume_or_prepare_batch(
                args=args,
                manifest_payload=active_batch,
                manifest_path=manifest_path,
                candidate_rows=unreviewed_rows,
            )
        batch_ids = ", ".join(str(item.get("batch_id") or "unknown") for item in active_batches)
        raise RuntimeError(f"Cannot open a new trimming batch while unresolved batches exist: {batch_ids}")

    batch_id = next_batch_id(args.batches_dir)
    report_dir = args.reports_dir / batch_id
    candidate_dir = report_dir / "text_trimmed_llm_candidates"
    llm_dir = report_dir / "text_trimmed_llm"
    ready_dir = report_dir / "text_proceedings_ready"
    for path in (candidate_dir, llm_dir, ready_dir):
        path.mkdir(parents=True, exist_ok=True)
    candidate_registry_path = report_dir / "text_trim_llm_candidate_registry.csv"
    llm_registry_path = report_dir / "text_trim_llm_registry.csv"
    ready_registry_path = report_dir / "text_proceedings_ready_registry.csv"
    report_path = report_dir / "batch_report.json"
    manifest_path = args.batches_dir / f"{batch_id}.json"
    manifest_payload = initial_manifest_payload(
        batch_id=batch_id,
        batch_size=args.batch_size,
        reviewed_ids=reviewed_ids,
        report_dir=report_dir,
        report_path=report_path,
        candidate_dir=candidate_dir,
        candidate_registry_path=candidate_registry_path,
        llm_dir=llm_dir,
        llm_registry_path=llm_registry_path,
        ready_dir=ready_dir,
        ready_registry_path=ready_registry_path,
    )
    write_manifest(manifest_path, manifest_payload)
    return resume_or_prepare_batch(
        args=args,
        manifest_payload=manifest_payload,
        manifest_path=manifest_path,
        candidate_rows=unreviewed_rows,
    )


def main() -> None:
    args = parse_args()
    report = prepare_batch(args)
    print(f"Prepared {report['batch_id']} with {report['file_count']} files.")
    print(f"Report: {report['output_paths']['report_path']}")


if __name__ == "__main__":
    main()
