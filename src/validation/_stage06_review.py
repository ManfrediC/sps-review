from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipelines.stage06_counting import overrides
from src.validation import _stage04_gold as gold


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = REPO_ROOT / "results" / "stage06_count_runs"
COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"
REVIEW_ROOT = REPO_ROOT / "qa" / "validation" / "stage06_count_review"
OVERRIDE_LEDGER_PATH = overrides.MANUAL_REVIEW_LEDGER_PATH
RESPONSES_FILENAME = "responses.csv"
MANIFEST_FILENAME = "review_manifest.json"
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
    return gold.load_csv_rows_by_id(path, key_column)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    return (parse_int(paper_id, default=10**9), paper_id)


def discover_run_directories(root: Path = RUN_ROOT) -> list[Path]:
    if not root.exists():
        return []
    run_dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and ((path / "results").exists() or (path / "run_manifest.json").exists())
    ]
    return sorted(run_dirs, key=lambda path: path.name)


def latest_run_artifacts_for_paper(paper_id: str, root: Path = RUN_ROOT) -> dict[str, str]:
    resolved_paper_id = str(paper_id or "").strip()
    if not resolved_paper_id:
        return {}

    matched_runs: list[Path] = []
    for run_dir in discover_run_directories(root):
        if (run_dir / "results" / f"{resolved_paper_id}.json").exists():
            matched_runs.append(run_dir)
    if not matched_runs:
        return {}

    latest_run = matched_runs[-1]
    candidate_path = latest_run / "candidate_packages" / f"{resolved_paper_id}.json"
    decision_path = latest_run / "count_decisions" / f"{resolved_paper_id}.json"
    evidence_path = latest_run / "count_evidence" / f"{resolved_paper_id}.json"
    result_path = latest_run / "results" / f"{resolved_paper_id}.json"
    return {
        "attached_run_id": latest_run.name,
        "attached_result_json_path": display_path(result_path) if result_path.exists() else "",
        "attached_candidate_json_path": display_path(candidate_path) if candidate_path.exists() else "",
        "attached_count_decision_json_path": display_path(decision_path) if decision_path.exists() else "",
        "attached_count_evidence_json_path": display_path(evidence_path) if evidence_path.exists() else "",
    }


def infer_run_id_from_stage06_path(path_text: str) -> str:
    path = Path(str(path_text or "").strip())
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "stage06_count_runs" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def count_decision_path_from_row(row: dict[str, str]) -> str:
    paper_id = str(row.get("paper_id") or "").strip()
    evidence_path_text = str(row.get("count_evidence_json_path") or "").strip()
    if evidence_path_text:
        evidence_path = resolve_repo_path(evidence_path_text)
        candidate = evidence_path.parent.parent / "count_decisions" / f"{paper_id}.json"
        if candidate.exists():
            return display_path(candidate)

    candidate_path_text = str(row.get("count_candidate_json_path") or "").strip()
    run_id = infer_run_id_from_stage06_path(candidate_path_text)
    if run_id and paper_id:
        candidate = RUN_ROOT / run_id / "count_decisions" / f"{paper_id}.json"
        if candidate.exists():
            return display_path(candidate)
    return ""


def review_scope_id_for_run(run_dir: Path) -> str:
    return sanitize_scope_id(run_dir.name)


def review_scope_id_for_registry(registry_path: Path) -> str:
    if registry_path.resolve() == COUNT_REGISTRY_PATH.resolve():
        return "canonical_registry"
    return sanitize_scope_id(f"registry_{registry_path.parent.name}_{registry_path.stem}")


def sanitize_scope_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "").strip()).strip("_")
    return cleaned or "review_scope"


def review_dir_for_scope(scope_id: str, root: Path = REVIEW_ROOT) -> Path:
    return root / sanitize_scope_id(scope_id)


def review_manifest_path(review_dir: Path) -> Path:
    return review_dir / MANIFEST_FILENAME


def responses_path(review_dir: Path) -> Path:
    return review_dir / RESPONSES_FILENAME


def response_fieldnames() -> list[str]:
    return list(overrides.OVERRIDE_FIELDNAMES)


def ensure_review_workspace(
    review_dir: Path,
    *,
    source_scope_id: str,
    source_scope_label: str,
    source_kind: str,
    source_path_text: str,
) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    overrides.ensure_override_ledger(OVERRIDE_LEDGER_PATH)
    manifest_path = review_manifest_path(review_dir)
    manifest = {
        "source_scope_id": source_scope_id,
        "source_scope_label": source_scope_label,
        "source_kind": source_kind,
        "source_path": source_path_text,
        "created_at_utc": now_utc_iso(),
    }
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not responses_path(review_dir).exists():
        with responses_path(review_dir).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=response_fieldnames())
            writer.writeheader()


def load_responses_by_id(review_dir: Path) -> dict[str, dict[str, str]]:
    return rows_by_id(responses_path(review_dir), "paper_id")


def ordered_response_rows(
    review_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in review_rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id and paper_id in responses_by_id:
            ordered.append(responses_by_id[paper_id])
            seen.add(paper_id)
    for paper_id in sorted(set(responses_by_id) - seen, key=sort_key_for_paper_id):
        ordered.append(responses_by_id[paper_id])
    return ordered


def save_response_row(
    review_dir: Path,
    review_rows: list[dict[str, str]],
    response_row: dict[str, str],
    *,
    override_ledger_path: Path = OVERRIDE_LEDGER_PATH,
) -> dict[str, dict[str, str]]:
    responses_by_id = load_responses_by_id(review_dir)
    paper_id = str(response_row.get("paper_id") or "").strip()
    if not paper_id:
        raise ValueError("Response row is missing paper_id.")
    responses_by_id[paper_id] = response_row
    ordered_rows = ordered_response_rows(review_rows, responses_by_id)
    with responses_path(review_dir).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=response_fieldnames())
        writer.writeheader()
        writer.writerows(ordered_rows)
    overrides.upsert_override_row(response_row, path=override_ledger_path)
    return responses_by_id


def count_completed_reviews(
    review_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> int:
    return sum(
        1
        for row in review_rows
        if (responses_by_id.get((row.get("paper_id") or "").strip(), {}).get("review_status") or "").strip() == "reviewed"
    )


def build_response_row(
    *,
    source_scope_id: str,
    source_scope_label: str,
    review_row: dict[str, str],
    prediction_correct: bool,
    reviewed_count: str,
    review_status: str,
    reviewer_notes: str,
    reviewer_id: str,
    existing_row: dict[str, str] | None = None,
) -> dict[str, str]:
    existing_row = existing_row or {}
    reviewed_count_text = str(reviewed_count or "").strip()
    if prediction_correct and not reviewed_count_text:
        reviewed_count_text = str(review_row.get("likely_sps_case_count") or "0").strip() or "0"

    reviewed_at_utc = str(existing_row.get("reviewed_at_utc") or "").strip()
    if review_status in {"reviewed", "needs_follow_up"} and not reviewed_at_utc:
        reviewed_at_utc = now_utc_iso()

    return {
        "source_scope_id": source_scope_id,
        "source_scope_label": source_scope_label,
        "paper_id": str(review_row.get("paper_id") or "").strip(),
        "title": str(review_row.get("title") or "").strip(),
        "predicted_count": str(review_row.get("likely_sps_case_count") or "").strip(),
        "predicted_verification_status": str(review_row.get("count_verification_status") or "").strip(),
        "prediction_correct": "true" if prediction_correct else "false",
        "reviewed_count": reviewed_count_text,
        "review_status": str(review_status or "pending").strip() or "pending",
        "reviewer_notes": str(reviewer_notes or "").strip(),
        "reviewer_id": str(reviewer_id or "").strip() or DEFAULT_REVIEWER,
        "reviewed_at_utc": reviewed_at_utc,
        "updated_at_utc": now_utc_iso(),
    }


def load_candidate_package(path_text: str) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {}
    return load_json(resolve_repo_path(path_text))


def load_decision_payload(path_text: str) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {}
    return load_json(resolve_repo_path(path_text))


def load_evidence_payload(path_text: str) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {}
    return load_json(resolve_repo_path(path_text))


def _stringify_row(row: dict[str, Any]) -> dict[str, str]:
    return {str(key): "" if value is None else str(value) for key, value in row.items()}


def _enrich_review_row(
    row: dict[str, str],
    *,
    artifact_rows: dict[str, dict[str, str]],
    run_id: str,
    source_scope_label: str,
) -> dict[str, str]:
    paper_id = str(row.get("paper_id") or "").strip()
    artifact_row = artifact_rows.get(paper_id, {})
    enriched = dict(row)
    attached_run = latest_run_artifacts_for_paper(paper_id)
    if attached_run:
        enriched.update({key: value for key, value in attached_run.items() if value})
    enriched["run_id"] = run_id
    enriched["source_scope_label"] = source_scope_label
    enriched["pdf_path_relative"] = first_pipe_separated_value(artifact_row.get("pdf_paths_relative") or "")
    enriched["source_text_json_path"] = str(
        row.get("source_text_json_path")
        or artifact_row.get("text_json_path")
        or ""
    ).strip()
    enriched["preferred_text_json_path"] = str(row.get("preferred_text_json_path") or "").strip()
    enriched["count_decision_json_path"] = str(row.get("count_decision_json_path") or "").strip()
    if not enriched["count_decision_json_path"]:
        enriched["count_decision_json_path"] = count_decision_path_from_row(enriched)
    if not str(enriched.get("count_candidate_json_path") or "").strip():
        enriched["count_candidate_json_path"] = str(enriched.get("attached_candidate_json_path") or "").strip()
    if not str(enriched.get("count_evidence_json_path") or "").strip():
        enriched["count_evidence_json_path"] = str(enriched.get("attached_count_evidence_json_path") or "").strip()
    if not enriched["count_decision_json_path"]:
        enriched["count_decision_json_path"] = str(enriched.get("attached_count_decision_json_path") or "").strip()
    if not enriched["run_id"]:
        enriched["run_id"] = str(enriched.get("attached_run_id") or "").strip()
    return enriched


def load_review_rows_from_registry(
    registry_path: Path,
    *,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
) -> list[dict[str, str]]:
    artifact_rows = rows_by_id(artifact_registry_path)
    source_scope_label = display_path(registry_path)
    rows: list[dict[str, str]] = []
    for raw_row in sorted(load_csv_rows(registry_path), key=lambda row: sort_key_for_paper_id(str(row.get("paper_id") or ""))):
        row = _stringify_row(raw_row)
        run_id = infer_run_id_from_stage06_path(row.get("count_candidate_json_path") or "")
        rows.append(
            _enrich_review_row(
                row,
                artifact_rows=artifact_rows,
                run_id=run_id,
                source_scope_label=source_scope_label,
            )
        )
    return rows


def load_review_rows_from_run(
    run_dir: Path,
    *,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
) -> list[dict[str, str]]:
    artifact_rows = rows_by_id(artifact_registry_path)
    rows: list[dict[str, str]] = []
    results_dir = run_dir / "results"
    for result_path in sorted(results_dir.glob("*.json"), key=lambda path: sort_key_for_paper_id(path.stem)):
        payload = load_json(result_path)
        count_row = _stringify_row(payload.get("count_row") or {})
        if not count_row:
            continue
        if not count_row.get("paper_id"):
            count_row["paper_id"] = result_path.stem
        count_row["source_text_json_path"] = str(payload.get("source_text_json_path") or count_row.get("source_text_json_path") or "").strip()
        count_row["preferred_text_json_path"] = str(
            payload.get("preferred_text_json_path") or count_row.get("preferred_text_json_path") or ""
        ).strip()
        count_row["count_decision_json_path"] = display_path(run_dir / "count_decisions" / f"{count_row['paper_id']}.json")
        if not (run_dir / "count_decisions" / f"{count_row['paper_id']}.json").exists():
            count_row["count_decision_json_path"] = ""
        rows.append(
            _enrich_review_row(
                count_row,
                artifact_rows=artifact_rows,
                run_id=run_dir.name,
                source_scope_label=run_dir.name,
            )
        )
    return rows
