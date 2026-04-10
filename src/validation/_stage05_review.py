from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipelines._source_routing import load_csv_rows_by_id
from src.validation import _stage04_gold as gold
from src.validation.evaluate_trimming_feedback import evaluate_feedback_files


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIMMING_QA_DIR = REPO_ROOT / "qa" / "trimming"
BATCHES_DIR = TRIMMING_QA_DIR / "batches"
FEEDBACK_DIR = TRIMMING_QA_DIR / "feedback"
REGRESSION_DIR = TRIMMING_QA_DIR / "regression"
REPORTS_DIR = TRIMMING_QA_DIR / "reports"
ARTIFACT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"

REVIEW_QUEUE_FILENAME = "review_queue.csv"
RESPONSES_FILENAME = "responses.csv"
FEEDBACK_FILENAME = "feedback.json"
MANUAL_OVERRIDES_FILENAME = "manual_overrides.csv"
ACCEPTANCE_REPORT_FILENAME = "acceptance_report.json"
PATCH_SUMMARY_FILENAME = "patch_review_summary.json"
DEFAULT_REVIEWER = "human_reviewer"

display_path = gold.display_path
first_pipe_separated_value = gold.first_pipe_separated_value
load_text_page_entries = gold.load_text_page_entries
parse_int = gold.parse_int
resolve_repo_path = gold.resolve_repo_path
search_text_page_entries = gold.search_text_page_entries
truthy = gold.truthy


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    return gold.load_csv_rows(path)


def rows_by_id(path: Path, key_column: str = "paper_id") -> dict[str, dict[str, str]]:
    return load_csv_rows_by_id(path, key_column)


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def batch_manifest_path(batch_id: str, batches_dir: Path = BATCHES_DIR) -> Path:
    return batches_dir / f"{batch_id}.json"


def report_dir_for_batch(batch_id: str, reports_dir: Path = REPORTS_DIR) -> Path:
    return reports_dir / batch_id


def review_queue_path(report_dir: Path) -> Path:
    return report_dir / REVIEW_QUEUE_FILENAME


def responses_path(report_dir: Path) -> Path:
    return report_dir / RESPONSES_FILENAME


def feedback_path(report_dir: Path) -> Path:
    return report_dir / FEEDBACK_FILENAME


def manual_overrides_path(report_dir: Path) -> Path:
    return report_dir / MANUAL_OVERRIDES_FILENAME


def acceptance_report_path(report_dir: Path) -> Path:
    return report_dir / ACCEPTANCE_REPORT_FILENAME


def patch_summary_path(report_dir: Path) -> Path:
    return report_dir / PATCH_SUMMARY_FILENAME


def regression_report_path(batch_id: str, reports_dir: Path = REPORTS_DIR) -> Path:
    return reports_dir / f"regression_evaluation_{batch_id}.json"


def review_queue_fieldnames() -> list[str]:
    return [
        "batch_id",
        "paper_id",
        "title",
        "authors",
        "resolved_source_subtype",
        "resolved_source_route_source",
        "workflow_stage",
        "pdf_filename",
        "pdf_path_relative",
        "source_text_json_path",
        "trimmed_text_json_path",
        "preferred_start_page",
        "best_match_page_index",
        "trim_status",
        "qc_status",
        "manual_follow_up_required",
        "match_score",
        "title_score",
        "author_score",
        "combined_score",
        "trim_reason",
        "qc_note",
        "selection_created_at_utc",
    ]


def response_fieldnames() -> list[str]:
    return [
        "batch_id",
        "paper_id",
        "title",
        "extraction_correct",
        "corrected_start_text",
        "corrected_end_text",
        "reviewer_comments",
        "reviewed_correct",
        "corrected_successfully",
        "review_status",
        "reviewer_id",
        "reviewed_at_utc",
        "updated_at_utc",
    ]


def manual_override_fieldnames() -> list[str]:
    return [
        "batch_id",
        "paper_id",
        "override_enabled",
        "corrected_start_text",
        "corrected_end_text",
        "reviewer_comments",
        "override_status",
        "override_applied_at_utc",
    ]


def empty_feedback_payload(batch_id: str) -> dict[str, Any]:
    return {
        "feedback_round_id": f"{batch_id}_feedback",
        "batch_id": batch_id,
        "received_at_utc": "",
        "cases": [],
    }


def empty_acceptance_report() -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "case_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "results": [],
    }


def load_review_queue_rows(report_dir: Path) -> list[dict[str, str]]:
    return load_csv_rows(review_queue_path(report_dir))


def load_responses_by_id(report_dir: Path) -> dict[str, dict[str, str]]:
    return rows_by_id(responses_path(report_dir))


def load_manual_overrides_by_id(report_dir: Path) -> dict[str, dict[str, str]]:
    return rows_by_id(manual_overrides_path(report_dir))


def count_completed_reviews(queue_rows: list[dict[str, str]], responses_by_id: dict[str, dict[str, str]]) -> int:
    return sum(
        1
        for queue_row in queue_rows
        if (responses_by_id.get((queue_row.get("paper_id") or "").strip(), {}).get("review_status") or "").strip() == "reviewed"
    )


def infer_workflow_stage(trimmed_text_json_path_text: str, trim_status: str) -> str:
    if str(trimmed_text_json_path_text or "").strip():
        return "stage05_trimming"
    if str(trim_status or "").strip() == "not_needed":
        return "stage05_not_needed"
    return "stage05_not_needed"


def preferred_start_page(qc_row: dict[str, str], trim_row: dict[str, str]) -> int:
    best_match_page = parse_int(qc_row.get("best_match_page_index"), default=-1)
    if best_match_page >= 0:
        return best_match_page + 1
    start_page_index = parse_int(trim_row.get("start_page_index"), default=-1)
    if start_page_index >= 0:
        return start_page_index + 1
    return 1


def build_review_queue_rows(
    *,
    batch_id: str,
    batch_report: dict[str, Any],
    trim_rows: dict[str, dict[str, str]],
    qc_rows: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    queue_rows: list[dict[str, str]] = []
    for file_status in batch_report.get("file_statuses") or []:
        paper_id = str(file_status.get("paper_id") or "").strip()
        if not paper_id:
            continue
        trim_row = trim_rows.get(paper_id, {})
        qc_row = qc_rows.get(paper_id, {})
        artifact_row = artifact_rows.get(paper_id, {})
        trimmed_path_text = (
            str(qc_row.get("trimmed_text_json_path") or "").strip()
            or str(file_status.get("trimmed_text_json_path") or "").strip()
        )
        trim_status = str(trim_row.get("trim_status") or file_status.get("trim_status") or "").strip()
        queue_rows.append(
            {
                "batch_id": batch_id,
                "paper_id": paper_id,
                "title": str(file_status.get("title") or "").strip(),
                "authors": str(file_status.get("authors") or "").strip(),
                "resolved_source_subtype": str(file_status.get("resolved_source_subtype") or "").strip(),
                "resolved_source_route_source": str(file_status.get("resolved_source_route_source") or "").strip(),
                "workflow_stage": infer_workflow_stage(trimmed_path_text, trim_status),
                "pdf_filename": first_pipe_separated_value(artifact_row.get("pdf_filenames") or ""),
                "pdf_path_relative": first_pipe_separated_value(artifact_row.get("pdf_paths_relative") or ""),
                "source_text_json_path": (
                    str(qc_row.get("source_text_json_path") or "").strip()
                    or str(artifact_row.get("text_json_path") or "").strip()
                ),
                "trimmed_text_json_path": trimmed_path_text,
                "preferred_start_page": str(preferred_start_page(qc_row, trim_row)),
                "best_match_page_index": str(qc_row.get("best_match_page_index") or "").strip(),
                "trim_status": trim_status,
                "qc_status": str(qc_row.get("qc_status") or file_status.get("qc_status") or "").strip(),
                "manual_follow_up_required": str(
                    qc_row.get("manual_follow_up_required") or file_status.get("manual_follow_up_required") or ""
                ).strip(),
                "match_score": str(trim_row.get("match_score") or file_status.get("match_score") or "").strip(),
                "title_score": str(qc_row.get("title_score") or file_status.get("title_score") or "").strip(),
                "author_score": str(qc_row.get("author_score") or file_status.get("author_score") or "").strip(),
                "combined_score": str(qc_row.get("combined_score") or "").strip(),
                "trim_reason": str(trim_row.get("trim_reason") or file_status.get("trim_reason") or "").strip(),
                "qc_note": str(qc_row.get("qc_note") or file_status.get("qc_note") or "").strip(),
                "selection_created_at_utc": str(batch_report.get("generated_at_utc") or now_utc_iso()).strip(),
            }
        )
    return queue_rows


def ensure_response_files(report_dir: Path, batch_id: str) -> None:
    if not responses_path(report_dir).exists():
        write_csv_rows(responses_path(report_dir), [], response_fieldnames())
    if not manual_overrides_path(report_dir).exists():
        write_csv_rows(manual_overrides_path(report_dir), [], manual_override_fieldnames())
    if not feedback_path(report_dir).exists():
        write_json(feedback_path(report_dir), empty_feedback_payload(batch_id))


def response_defaults(queue_row: dict[str, str], response_row: dict[str, str]) -> tuple[bool, str, str, str]:
    if response_row:
        return (
            truthy(response_row.get("extraction_correct") or response_row.get("reviewed_correct") or ""),
            str(response_row.get("corrected_start_text") or "").strip(),
            str(response_row.get("corrected_end_text") or "").strip(),
            str(response_row.get("reviewer_comments") or "").strip(),
        )
    return True, "", "", ""


def build_response_row(
    *,
    queue_row: dict[str, str],
    extraction_correct: bool,
    corrected_start_text: str,
    corrected_end_text: str,
    reviewer_comments: str,
    reviewer_id: str,
    existing_row: dict[str, str] | None = None,
) -> dict[str, str]:
    existing_row = existing_row or {}
    return {
        "batch_id": str(queue_row.get("batch_id") or "").strip(),
        "paper_id": str(queue_row.get("paper_id") or "").strip(),
        "title": str(queue_row.get("title") or "").strip(),
        "extraction_correct": "true" if extraction_correct else "false",
        "corrected_start_text": corrected_start_text.strip(),
        "corrected_end_text": corrected_end_text.strip(),
        "reviewer_comments": reviewer_comments.strip(),
        "reviewed_correct": "true" if extraction_correct else "false",
        "corrected_successfully": str(existing_row.get("corrected_successfully") or "false").strip() or "false",
        "review_status": "reviewed",
        "reviewer_id": reviewer_id.strip() or str(existing_row.get("reviewer_id") or DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER,
        "reviewed_at_utc": str(existing_row.get("reviewed_at_utc") or now_utc_iso()).strip(),
        "updated_at_utc": now_utc_iso(),
    }


def ordered_response_rows(queue_rows: list[dict[str, str]], responses_by_id: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    ordered: list[dict[str, str]] = []
    for queue_row in queue_rows:
        paper_id = str(queue_row.get("paper_id") or "").strip()
        if paper_id in responses_by_id:
            ordered.append(responses_by_id[paper_id])
    return ordered


def save_response_row(report_dir: Path, response_row: dict[str, str]) -> dict[str, dict[str, str]]:
    batch_id = str(response_row.get("batch_id") or "").strip()
    ensure_response_files(report_dir, batch_id)
    responses_by_id = load_responses_by_id(report_dir)
    paper_id = str(response_row.get("paper_id") or "").strip()
    if not paper_id:
        raise ValueError("Response row is missing paper_id.")
    responses_by_id[paper_id] = response_row
    queue_rows = load_review_queue_rows(report_dir)
    if queue_rows:
        rows_to_write = ordered_response_rows(queue_rows, responses_by_id)
    else:
        rows_to_write = sorted(
            responses_by_id.values(),
            key=lambda row: int(str(row.get("paper_id") or "0") or "0"),
        )
    write_csv_rows(responses_path(report_dir), rows_to_write, response_fieldnames())
    return responses_by_id


def build_feedback_case(queue_row: dict[str, str], response_row: dict[str, str]) -> dict[str, Any]:
    paper_id = str(queue_row.get("paper_id") or "").strip()
    extraction_correct = truthy(response_row.get("extraction_correct") or response_row.get("reviewed_correct") or "")
    corrected_start = str(response_row.get("corrected_start_text") or "").strip()
    corrected_end = str(response_row.get("corrected_end_text") or "").strip()
    reviewer_comments = str(response_row.get("reviewer_comments") or "").strip()
    workflow_stage = str(queue_row.get("workflow_stage") or "").strip() or "stage05_trimming"

    if extraction_correct:
        if workflow_stage == "stage05_not_needed":
            case = {
                "paper_id": paper_id,
                "workflow_stage": "stage05_not_needed",
                "expected_verdict": "should_manual_review",
                "expected_manual_review": True,
            }
            if reviewer_comments:
                case["notes"] = reviewer_comments
            return case
        case = {
            "paper_id": paper_id,
            "workflow_stage": "stage05_trimming",
            "expected_verdict": "correct",
            "expected_manual_review": False,
        }
        if corrected_start:
            case["expected_start_first_line"] = corrected_start
        if corrected_end:
            case["expected_end_contains"] = corrected_end
        if reviewer_comments:
            case["notes"] = reviewer_comments
        return case

    if corrected_start or corrected_end:
        case = {
            "paper_id": paper_id,
            "workflow_stage": "stage05_trimming",
            "expected_verdict": "wrong_abstract",
            "expected_manual_review": False,
        }
        if corrected_start:
            case["expected_start_first_line"] = corrected_start
        if corrected_end:
            case["expected_end_contains"] = corrected_end
        if reviewer_comments:
            case["notes"] = reviewer_comments
        return case

    case = {
        "paper_id": paper_id,
        "workflow_stage": "stage05_not_needed",
        "expected_verdict": "should_manual_review",
        "expected_manual_review": True,
    }
    if reviewer_comments:
        case["notes"] = reviewer_comments
    return case


def build_feedback_payload(
    batch_id: str,
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    reviewed_timestamps = [
        str(response_row.get("updated_at_utc") or "").strip()
        for response_row in responses_by_id.values()
        if (response_row.get("review_status") or "").strip() == "reviewed"
    ]
    for queue_row in queue_rows:
        paper_id = str(queue_row.get("paper_id") or "").strip()
        response_row = responses_by_id.get(paper_id, {})
        if (response_row.get("review_status") or "").strip() != "reviewed":
            continue
        cases.append(build_feedback_case(queue_row, response_row))
    payload = empty_feedback_payload(batch_id)
    payload["cases"] = cases
    payload["received_at_utc"] = max(reviewed_timestamps, default="")
    return payload


def sync_manual_overrides(
    report_dir: Path,
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    existing_rows = load_manual_overrides_by_id(report_dir)
    synced_rows: list[dict[str, str]] = []
    for queue_row in queue_rows:
        paper_id = str(queue_row.get("paper_id") or "").strip()
        response_row = responses_by_id.get(paper_id, {})
        if not response_row or truthy(response_row.get("reviewed_correct") or ""):
            continue
        existing_row = existing_rows.get(paper_id, {})
        synced_rows.append(
            {
                "batch_id": str(queue_row.get("batch_id") or "").strip(),
                "paper_id": paper_id,
                "override_enabled": str(existing_row.get("override_enabled") or "false").strip() or "false",
                "corrected_start_text": str(response_row.get("corrected_start_text") or "").strip(),
                "corrected_end_text": str(response_row.get("corrected_end_text") or "").strip(),
                "reviewer_comments": str(response_row.get("reviewer_comments") or "").strip(),
                "override_status": str(existing_row.get("override_status") or "pending_review").strip() or "pending_review",
                "override_applied_at_utc": str(existing_row.get("override_applied_at_utc") or "").strip(),
            }
        )
    write_csv_rows(manual_overrides_path(report_dir), synced_rows, manual_override_fieldnames())
    return synced_rows


def build_patch_summary(
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    incorrect_cases: list[dict[str, str]] = []
    grouped_statuses: dict[str, list[str]] = defaultdict(list)
    grouped_comments: dict[str, list[str]] = defaultdict(list)
    queue_by_id = {str(row.get("paper_id") or "").strip(): row for row in queue_rows}
    for paper_id, response_row in responses_by_id.items():
        if truthy(response_row.get("reviewed_correct") or ""):
            continue
        queue_row = queue_by_id.get(paper_id, {})
        trim_status = str(queue_row.get("trim_status") or "").strip()
        qc_status = str(queue_row.get("qc_status") or "").strip()
        grouped_statuses[f"{trim_status}|{qc_status}"].append(paper_id)
        comment = " ".join(str(response_row.get("reviewer_comments") or "").split()).strip()
        if comment:
            grouped_comments[comment].append(paper_id)
        incorrect_cases.append(
            {
                "paper_id": paper_id,
                "trim_status": trim_status,
                "qc_status": qc_status,
                "corrected_start_text": str(response_row.get("corrected_start_text") or "").strip(),
                "corrected_end_text": str(response_row.get("corrected_end_text") or "").strip(),
                "reviewer_comments": comment,
            }
        )
    return {
        "generated_at_utc": now_utc_iso(),
        "incorrect_case_count": len(incorrect_cases),
        "incorrect_cases": incorrect_cases,
        "status_clusters": [
            {"status_pair": key, "paper_ids": value, "count": len(value)}
            for key, value in sorted(grouped_statuses.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
        "comment_clusters": [
            {"comment": key, "paper_ids": value, "count": len(value)}
            for key, value in sorted(grouped_comments.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
    }


def apply_acceptance_to_responses(
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
    acceptance_report: dict[str, Any],
) -> dict[str, dict[str, str]]:
    result_by_id = {
        str(result.get("paper_id") or "").strip(): bool(result.get("passed"))
        for result in acceptance_report.get("results") or []
        if str(result.get("paper_id") or "").strip()
    }
    updated: dict[str, dict[str, str]] = {}
    for queue_row in queue_rows:
        paper_id = str(queue_row.get("paper_id") or "").strip()
        response_row = dict(responses_by_id.get(paper_id, {}))
        if not response_row:
            continue
        if not truthy(response_row.get("reviewed_correct") or ""):
            response_row["corrected_successfully"] = "true" if result_by_id.get(paper_id, False) else "false"
        updated[paper_id] = response_row
    return updated


def build_review_snapshot(
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    snapshot_rows: list[dict[str, str]] = []
    for queue_row in queue_rows:
        paper_id = str(queue_row.get("paper_id") or "").strip()
        response_row = responses_by_id.get(paper_id, {})
        snapshot_rows.append(
            {
                **queue_row,
                "review_status": str(response_row.get("review_status") or "pending").strip(),
                "reviewed_correct": str(response_row.get("reviewed_correct") or "").strip(),
                "corrected_successfully": str(response_row.get("corrected_successfully") or "").strip(),
                "reviewer_comments": str(response_row.get("reviewer_comments") or "").strip(),
                "reviewed_at_utc": str(response_row.get("reviewed_at_utc") or "").strip(),
            }
        )
    return snapshot_rows


def refresh_review_materials(
    *,
    batch_id: str,
    report_dir: Path,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
    feedback_dir: Path = FEEDBACK_DIR,
    regression_dir: Path = REGRESSION_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    batch_report_path = report_dir / "batch_report.json"
    trim_registry_path = report_dir / "text_trim_registry.csv"
    qc_registry_path = report_dir / "proceedings_text_qc_registry.csv"
    if not batch_report_path.exists():
        raise FileNotFoundError(f"Batch report not found: {batch_report_path}")

    batch_report = json.loads(batch_report_path.read_text(encoding="utf-8"))
    trim_rows = rows_by_id(trim_registry_path)
    qc_rows = rows_by_id(qc_registry_path)
    artifact_rows = rows_by_id(artifact_registry_path)
    queue_rows = build_review_queue_rows(
        batch_id=batch_id,
        batch_report=batch_report,
        trim_rows=trim_rows,
        qc_rows=qc_rows,
        artifact_rows=artifact_rows,
    )
    write_csv_rows(review_queue_path(report_dir), queue_rows, review_queue_fieldnames())
    ensure_response_files(report_dir, batch_id)

    responses_by_id = load_responses_by_id(report_dir)
    write_csv_rows(responses_path(report_dir), ordered_response_rows(queue_rows, responses_by_id), response_fieldnames())
    synced_override_rows = sync_manual_overrides(report_dir, queue_rows, responses_by_id)

    feedback_payload = build_feedback_payload(batch_id, queue_rows, responses_by_id)
    write_json(feedback_path(report_dir), feedback_payload)
    write_json(patch_summary_path(report_dir), build_patch_summary(queue_rows, responses_by_id))

    acceptance_report = empty_acceptance_report()
    regression_report = empty_acceptance_report()
    if feedback_payload["cases"]:
        acceptance_report = evaluate_feedback_files(
            feedback_paths=[feedback_path(report_dir)],
            reports_dir=reports_dir,
            source_registry_path=source_registry_path,
            source_manual_review_path=source_manual_review_path,
        )
        regression_feedback_paths = sorted(regression_dir.rglob("*.json")) + [feedback_path(report_dir)]
        regression_report = evaluate_feedback_files(
            feedback_paths=regression_feedback_paths,
            reports_dir=reports_dir,
            source_registry_path=source_registry_path,
            source_manual_review_path=source_manual_review_path,
        )

    responses_by_id = apply_acceptance_to_responses(queue_rows, responses_by_id, acceptance_report)
    write_csv_rows(responses_path(report_dir), ordered_response_rows(queue_rows, responses_by_id), response_fieldnames())
    write_json(acceptance_report_path(report_dir), acceptance_report)
    write_json(regression_report_path(batch_id, reports_dir), regression_report)

    snapshot_rows = build_review_snapshot(queue_rows, responses_by_id)
    return {
        "queue_rows": queue_rows,
        "responses_by_id": responses_by_id,
        "manual_override_rows": synced_override_rows,
        "feedback_payload": feedback_payload,
        "acceptance_report": acceptance_report,
        "regression_report": regression_report,
        "snapshot_rows": snapshot_rows,
        "completed_review_count": count_completed_reviews(queue_rows, responses_by_id),
    }
