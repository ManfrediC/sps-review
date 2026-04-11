from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.pipelines._source_routing import load_csv_rows_by_id, resolve_source_row
from src.validation import _stage04_gold as gold
from src.validation.evaluate_trimming_feedback import (
    REPORTS_DIR,
    discover_report_bundles,
    feedback_batch_id,
    load_feedback_payload,
    pick_report_bundle,
    resolve_workflow_stage,
    trimmed_output_path,
    trimmed_text_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIMMING_QA_DIR = REPO_ROOT / "qa" / "trimming"
FEEDBACK_DIR = TRIMMING_QA_DIR / "feedback"
REGRESSION_DIR = TRIMMING_QA_DIR / "regression"
GOLD_STANDARD_DIR = TRIMMING_QA_DIR / "gold_standard"
GOLD_PAPERS_DIR = GOLD_STANDARD_DIR / "papers"
TRANCHE_REPORTS_DIR = GOLD_STANDARD_DIR / "tranche_reports"
MANIFEST_PATH = GOLD_STANDARD_DIR / "manifest.json"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"

REVIEW_QUEUE_FILENAME = "review_queue.csv"
RESPONSES_FILENAME = "responses.csv"
ACCEPTANCE_REPORT_FILENAME = "acceptance_report.json"
REPORT_FEEDBACK_FILENAME = "feedback.json"

display_path = gold.display_path
parse_int = gold.parse_int
resolve_repo_path = gold.resolve_repo_path
truthy = gold.truthy


@dataclass(frozen=True)
class GoldCandidate:
    paper_id: str
    batch_id: str
    accepted_report_bundle: str
    source_trimmed_json_path: Path | None
    feedback_path: Path | None
    review_queue_row: dict[str, str]
    response_row: dict[str, str]
    acceptance_result: dict[str, Any]
    feedback_case: dict[str, Any]
    promotion_basis: str


def now_utc_iso() -> str:
    return gold.now_utc_iso()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    return gold.load_csv_rows(path)


def rows_by_id(path: Path, key_column: str = "paper_id") -> dict[str, dict[str, str]]:
    return gold.load_csv_rows_by_id(path, key_column)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gold_json_path(paper_id: str, gold_papers_dir: Path = GOLD_PAPERS_DIR) -> Path:
    return gold_papers_dir / f"{paper_id}.json"


def canonical_json_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def trim_text_hash(path: Path) -> str:
    trimmed_text, _ = trimmed_text_payload(path)
    normalized = " ".join(trimmed_text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def historical_first_line(path: Path) -> str:
    _, lines = trimmed_text_payload(path)
    return lines[0] if lines else ""


def historical_last_line(path: Path) -> str:
    _, lines = trimmed_text_payload(path)
    return lines[-1] if lines else ""


def empty_manifest() -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "paper_count": 0,
        "entries": [],
    }


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not manifest_path.exists():
        return empty_manifest()
    payload = load_json(manifest_path)
    if "entries" not in payload or not isinstance(payload.get("entries"), list):
        return empty_manifest()
    return payload


def active_entries_by_id(manifest_path: Path = MANIFEST_PATH) -> dict[str, dict[str, Any]]:
    payload = load_manifest(manifest_path)
    return {
        str(entry.get("paper_id") or "").strip(): entry
        for entry in payload.get("entries") or []
        if str(entry.get("paper_id") or "").strip() and str(entry.get("gold_status") or "").strip() == "active"
    }


def save_manifest(entries: list[dict[str, Any]], manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    ordered_entries = sorted(entries, key=lambda entry: parse_int(entry.get("paper_id"), default=10**9))
    payload = {
        "generated_at_utc": now_utc_iso(),
        "paper_count": sum(1 for entry in ordered_entries if str(entry.get("gold_status") or "") == "active"),
        "entries": ordered_entries,
    }
    write_json(manifest_path, payload)
    return payload


def tranche_report_path(name: str, tranche_reports_dir: Path = TRANCHE_REPORTS_DIR) -> Path:
    return tranche_reports_dir / f"{name}.json"


def resolve_feedback_path(batch_id: str, report_dir: Path) -> Path | None:
    for candidate in (
        REGRESSION_DIR / f"{batch_id}_feedback.json",
        FEEDBACK_DIR / f"{batch_id}_feedback.json",
        report_dir / REPORT_FEEDBACK_FILENAME,
    ):
        if candidate.exists():
            return candidate
    return None


def resolve_trimmed_path(queue_row: dict[str, str], report_dir: Path, paper_id: str) -> Path | None:
    raw_path = str(queue_row.get("trimmed_text_json_path") or "").strip()
    if raw_path:
        candidate = resolve_repo_path(raw_path)
        if candidate.exists():
            return candidate
    candidate = report_dir / "text_trimmed" / f"{paper_id}.json"
    if candidate.exists():
        return candidate
    return None


def feedback_case_by_id(feedback_path: Path | None) -> dict[str, dict[str, Any]]:
    if feedback_path is None or not feedback_path.exists():
        return {}
    payload = load_feedback_payload(feedback_path)
    return {
        str(case.get("paper_id") or "").strip(): dict(case)
        for case in payload.get("cases") or []
        if str(case.get("paper_id") or "").strip()
    }


def reviewed_stage05_candidates_from_reports(
    *,
    reports_dir: Path = REPORTS_DIR,
    batch_id_filter: str | None = None,
    paper_id_filter: set[str] | None = None,
) -> list[GoldCandidate]:
    candidates: list[GoldCandidate] = []
    paper_id_filter = {paper_id.strip() for paper_id in (paper_id_filter or set()) if paper_id.strip()}
    for report_dir in sorted(reports_dir.iterdir() if reports_dir.exists() else []):
        if not report_dir.is_dir():
            continue
        batch_id = report_dir.name
        if not batch_id.startswith("batch_"):
            continue
        if batch_id_filter and batch_id != batch_id_filter:
            continue

        queue_path = report_dir / REVIEW_QUEUE_FILENAME
        responses_path = report_dir / RESPONSES_FILENAME
        acceptance_path = report_dir / ACCEPTANCE_REPORT_FILENAME
        if not queue_path.exists() or not responses_path.exists() or not acceptance_path.exists():
            continue

        queue_rows = rows_by_id(queue_path)
        response_rows = rows_by_id(responses_path)
        acceptance_payload = load_json(acceptance_path)
        acceptance_results = {
            str(result.get("paper_id") or "").strip(): dict(result)
            for result in acceptance_payload.get("results") or []
            if str(result.get("paper_id") or "").strip()
        }
        feedback_path = resolve_feedback_path(batch_id, report_dir)
        feedback_cases = feedback_case_by_id(feedback_path)

        for paper_id, queue_row in sorted(queue_rows.items(), key=lambda item: parse_int(item[0], default=10**9)):
            if paper_id_filter and paper_id not in paper_id_filter:
                continue
            if str(queue_row.get("workflow_stage") or "").strip() != "stage05_trimming":
                continue
            response_row = response_rows.get(paper_id, {})
            if str(response_row.get("review_status") or "").strip() != "reviewed":
                continue
            acceptance_result = acceptance_results.get(paper_id, {})
            if not bool(acceptance_result.get("passed")):
                continue

            reviewed_correct = truthy(response_row.get("reviewed_correct") or "")
            corrected_successfully = truthy(response_row.get("corrected_successfully") or "")
            if reviewed_correct:
                promotion_basis = "copied_reviewed_correct"
            elif corrected_successfully:
                promotion_basis = "promoted_corrected_output"
            else:
                continue

            candidates.append(
                GoldCandidate(
                    paper_id=paper_id,
                    batch_id=batch_id,
                    accepted_report_bundle=batch_id,
                    source_trimmed_json_path=resolve_trimmed_path(queue_row, report_dir, paper_id),
                    feedback_path=feedback_path,
                    review_queue_row=dict(queue_row),
                    response_row=dict(response_row),
                    acceptance_result=dict(acceptance_result),
                    feedback_case=dict(feedback_cases.get(paper_id, {})),
                    promotion_basis=promotion_basis,
                )
            )
    return candidates


def acceptance_result_by_id(report_dir: Path) -> dict[str, dict[str, Any]]:
    acceptance_path = report_dir / ACCEPTANCE_REPORT_FILENAME
    if not acceptance_path.exists():
        return {}
    payload = load_json(acceptance_path)
    return {
        str(result.get("paper_id") or "").strip(): dict(result)
        for result in payload.get("results") or []
        if str(result.get("paper_id") or "").strip()
    }


def build_regression_candidate(
    *,
    paper_id: str,
    batch_id: str,
    accepted_report_bundle: str,
    case_payload: dict[str, Any],
    source_trimmed_json_path: Path | None,
    feedback_path: Path,
    acceptance_result: dict[str, Any],
) -> GoldCandidate | None:
    expected_verdict = str(case_payload.get("expected_verdict") or "").strip()
    if expected_verdict == "correct":
        promotion_basis = "copied_reviewed_correct"
        response_row = {
            "review_status": "reviewed",
            "reviewed_correct": "true",
            "corrected_successfully": "false",
        }
    elif expected_verdict == "wrong_abstract":
        promotion_basis = "promoted_corrected_output"
        response_row = {
            "review_status": "reviewed",
            "reviewed_correct": "false",
            "corrected_successfully": "true",
        }
    else:
        return None
    return GoldCandidate(
        paper_id=paper_id,
        batch_id=batch_id,
        accepted_report_bundle=accepted_report_bundle,
        source_trimmed_json_path=source_trimmed_json_path,
        feedback_path=feedback_path,
        review_queue_row={
            "paper_id": paper_id,
            "workflow_stage": "stage05_trimming",
            "qc_status": "confirmed_full",
            "manual_follow_up_required": "false",
        },
        response_row=response_row,
        acceptance_result=acceptance_result or {"paper_id": paper_id, "passed": True},
        feedback_case=dict(case_payload),
        promotion_basis=promotion_basis,
    )


def reviewed_stage05_candidates_from_regression(
    *,
    regression_dir: Path = REGRESSION_DIR,
    reports_dir: Path = REPORTS_DIR,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    batch_id_filter: str | None = None,
    paper_id_filter: set[str] | None = None,
) -> list[GoldCandidate]:
    bundles = discover_report_bundles(reports_dir)
    heuristic_rows = load_csv_rows_by_id(source_registry_path, "paper_id")
    manual_rows = load_csv_rows_by_id(source_manual_review_path, "paper_id")
    paper_id_filter = {paper_id.strip() for paper_id in (paper_id_filter or set()) if paper_id.strip()}
    acceptance_by_batch: dict[str, dict[str, dict[str, Any]]] = {}
    candidates: list[GoldCandidate] = []
    for feedback_path in sorted(regression_dir.glob("*.json")):
        payload = load_feedback_payload(feedback_path)
        batch_id = feedback_batch_id(payload)
        for case_payload in payload.get("cases") or []:
            paper_id = str(case_payload.get("paper_id") or "").strip()
            if not paper_id:
                continue
            if paper_id_filter and paper_id not in paper_id_filter:
                continue
            resolved = resolve_source_row(
                paper_id=paper_id,
                heuristic_row=heuristic_rows.get(paper_id, {}),
                manual_row=manual_rows.get(paper_id, {}),
            )
            workflow_stage = resolve_workflow_stage(
                case_payload,
                str(resolved.get("resolved_source_category") or "").strip(),
            )
            if workflow_stage != "stage05_trimming":
                continue
            bundle = pick_report_bundle(paper_id, payload, workflow_stage, bundles)
            candidate_batch_id = batch_id or (bundle.name if bundle is not None else feedback_path.stem.removesuffix("_feedback"))
            if batch_id_filter and candidate_batch_id != batch_id_filter:
                continue
            if candidate_batch_id not in acceptance_by_batch:
                acceptance_by_batch[candidate_batch_id] = acceptance_result_by_id(reports_dir / candidate_batch_id)
            if bundle is None:
                source_trimmed_json_path = None
                accepted_report_bundle = candidate_batch_id
            else:
                source_trimmed_json_path = trimmed_output_path(bundle.trim_rows.get(paper_id, {}), bundle, paper_id)
                accepted_report_bundle = bundle.name
            candidate = build_regression_candidate(
                paper_id=paper_id,
                batch_id=candidate_batch_id,
                accepted_report_bundle=accepted_report_bundle,
                case_payload=dict(case_payload),
                source_trimmed_json_path=source_trimmed_json_path,
                feedback_path=feedback_path,
                acceptance_result=acceptance_by_batch.get(candidate_batch_id, {}).get(paper_id, {}),
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def reviewed_stage05_candidates(
    *,
    reports_dir: Path = REPORTS_DIR,
    regression_dir: Path = REGRESSION_DIR,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    batch_id_filter: str | None = None,
    paper_id_filter: set[str] | None = None,
) -> list[GoldCandidate]:
    candidates_by_id: dict[str, GoldCandidate] = {}
    for candidate in reviewed_stage05_candidates_from_regression(
        regression_dir=regression_dir,
        reports_dir=reports_dir,
        source_registry_path=source_registry_path,
        source_manual_review_path=source_manual_review_path,
        batch_id_filter=batch_id_filter,
        paper_id_filter=paper_id_filter,
    ):
        candidates_by_id[candidate.paper_id] = candidate
    for candidate in reviewed_stage05_candidates_from_reports(
        reports_dir=reports_dir,
        batch_id_filter=batch_id_filter,
        paper_id_filter=paper_id_filter,
    ):
        candidates_by_id[candidate.paper_id] = candidate
    return [
        candidates_by_id[paper_id]
        for paper_id in sorted(candidates_by_id, key=lambda value: parse_int(value, default=10**9))
    ]


def manifest_entry_for_candidate(
    candidate: GoldCandidate,
    *,
    gold_status: str,
    gold_path: Path,
    source_hash: str = "",
    text_hash: str = "",
    promoted_at_utc: str = "",
) -> dict[str, Any]:
    explicit_start = str(candidate.feedback_case.get("expected_start_first_line") or "").strip()
    explicit_end = str(candidate.feedback_case.get("expected_end_contains") or "").strip()
    return {
        "paper_id": candidate.paper_id,
        "gold_status": gold_status,
        "promotion_basis": candidate.promotion_basis,
        "accepted_batch_id": candidate.batch_id,
        "source_report_bundle": candidate.accepted_report_bundle,
        "source_trimmed_json_path": (
            display_path(candidate.source_trimmed_json_path) if candidate.source_trimmed_json_path else ""
        ),
        "gold_json_path": display_path(gold_path) if gold_status == "active" else "",
        "feedback_path": display_path(candidate.feedback_path) if candidate.feedback_path else "",
        "explicit_start_anchor": explicit_start,
        "explicit_end_anchor": explicit_end,
        "start_expectation_source": "feedback" if explicit_start else "gold_json",
        "end_expectation_source": "feedback" if explicit_end else "gold_json",
        "historical_reviewed_json_path": (
            display_path(candidate.source_trimmed_json_path) if candidate.source_trimmed_json_path else ""
        ),
        "qc_status_at_promotion": str(candidate.review_queue_row.get("qc_status") or "").strip(),
        "manual_follow_up_required": str(
            candidate.review_queue_row.get("manual_follow_up_required") or ""
        ).strip(),
        "trim_text_hash": text_hash,
        "canonical_json_hash": source_hash,
        "promoted_at_utc": promoted_at_utc,
        "gold_first_line": historical_first_line(gold_path) if gold_status == "active" and gold_path.exists() else "",
        "gold_last_line": historical_last_line(gold_path) if gold_status == "active" and gold_path.exists() else "",
    }


def upsert_manifest_entry(entries: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    paper_id = str(entry.get("paper_id") or "").strip()
    remaining = [existing for existing in entries if str(existing.get("paper_id") or "").strip() != paper_id]
    remaining.append(entry)
    return remaining


def promote_candidate(
    candidate: GoldCandidate,
    *,
    entries: list[dict[str, Any]],
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
    dry_run: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_path = candidate.source_trimmed_json_path
    target_path = gold_json_path(candidate.paper_id, gold_papers_dir)
    existing_by_id = {
        str(entry.get("paper_id") or "").strip(): entry
        for entry in entries
        if str(entry.get("paper_id") or "").strip()
    }
    existing_entry = existing_by_id.get(candidate.paper_id)

    if source_path is None or not source_path.exists():
        manifest_entry = manifest_entry_for_candidate(
            candidate,
            gold_status="missing_source_json",
            gold_path=target_path,
        )
        entries = upsert_manifest_entry(entries, manifest_entry)
        return entries, {
            "paper_id": candidate.paper_id,
            "status": "missing_source_json",
            "promotion_basis": candidate.promotion_basis,
            "batch_id": candidate.batch_id,
            "source_trimmed_json_path": "",
            "gold_json_path": "",
            "failure_reason": "accepted reviewed JSON is missing",
        }

    source_hash = canonical_json_hash(source_path)
    existing_target_exists = target_path.exists()
    existing_target_hash = canonical_json_hash(target_path) if existing_target_exists else ""
    if existing_target_exists and existing_target_hash != source_hash:
        manifest_entry = manifest_entry_for_candidate(
            candidate,
            gold_status="conflict",
            gold_path=target_path,
            source_hash=source_hash,
            text_hash=trim_text_hash(source_path),
        )
        entries = upsert_manifest_entry(entries, manifest_entry)
        return entries, {
            "paper_id": candidate.paper_id,
            "status": "conflict",
            "promotion_basis": candidate.promotion_basis,
            "batch_id": candidate.batch_id,
            "source_trimmed_json_path": display_path(source_path),
            "gold_json_path": display_path(target_path),
            "failure_reason": "existing gold JSON differs from accepted source JSON",
        }

    if existing_entry and str(existing_entry.get("gold_status") or "").strip() == "active":
        existing_manifest_hash = str(existing_entry.get("canonical_json_hash") or "").strip()
        if existing_manifest_hash and existing_manifest_hash == source_hash and existing_target_exists:
            refreshed_entry = manifest_entry_for_candidate(
                candidate,
                gold_status="active",
                gold_path=target_path,
                source_hash=source_hash,
                text_hash=trim_text_hash(target_path),
                promoted_at_utc=str(existing_entry.get("promoted_at_utc") or now_utc_iso()).strip(),
            )
            entries = upsert_manifest_entry(entries, refreshed_entry)
            return entries, {
                "paper_id": candidate.paper_id,
                "status": "already_active",
                "promotion_basis": candidate.promotion_basis,
                "batch_id": candidate.batch_id,
                "source_trimmed_json_path": display_path(source_path),
                "gold_json_path": display_path(target_path),
                "failure_reason": "",
            }

    if not dry_run:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    live_target_path = target_path if not dry_run else source_path
    manifest_entry = manifest_entry_for_candidate(
        candidate,
        gold_status="active",
        gold_path=target_path,
        source_hash=source_hash,
        text_hash=trim_text_hash(live_target_path),
        promoted_at_utc=now_utc_iso(),
    )
    entries = upsert_manifest_entry(entries, manifest_entry)
    return entries, {
        "paper_id": candidate.paper_id,
        "status": "promoted" if not dry_run else "would_promote",
        "promotion_basis": candidate.promotion_basis,
        "batch_id": candidate.batch_id,
        "source_trimmed_json_path": display_path(source_path),
        "gold_json_path": display_path(target_path),
        "failure_reason": "",
    }


def chunked_candidates(candidates: list[GoldCandidate], tranche_size: int) -> list[list[GoldCandidate]]:
    return [candidates[index : index + tranche_size] for index in range(0, len(candidates), tranche_size)]


def bootstrap_gold_store(
    *,
    reports_dir: Path = REPORTS_DIR,
    regression_dir: Path = REGRESSION_DIR,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    batch_id: str | None = None,
    paper_ids: list[str] | None = None,
    tranche_size: int = 10,
    dry_run: bool = False,
    manifest_path: Path = MANIFEST_PATH,
    tranche_reports_dir: Path = TRANCHE_REPORTS_DIR,
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
) -> dict[str, Any]:
    candidates = reviewed_stage05_candidates(
        reports_dir=reports_dir,
        regression_dir=regression_dir,
        source_registry_path=source_registry_path,
        source_manual_review_path=source_manual_review_path,
        batch_id_filter=batch_id,
        paper_id_filter=set(paper_ids or []),
    )
    entries = list(load_manifest(manifest_path).get("entries") or [])
    tranche_summaries: list[dict[str, Any]] = []
    for tranche_index, tranche_candidates in enumerate(chunked_candidates(candidates, tranche_size), start=1):
        tranche_results: list[dict[str, Any]] = []
        for candidate in tranche_candidates:
            entries, result = promote_candidate(
                candidate,
                entries=entries,
                gold_papers_dir=gold_papers_dir,
                dry_run=dry_run,
            )
            tranche_results.append(result)
        if not dry_run:
            save_manifest(entries, manifest_path)
        tranche_payload = {
            "generated_at_utc": now_utc_iso(),
            "tranche_id": f"bootstrap_tranche_{tranche_index:03d}",
            "dry_run": dry_run,
            "case_count": len(tranche_results),
            "paper_ids": [candidate.paper_id for candidate in tranche_candidates],
            "promoted_count": sum(1 for result in tranche_results if result["status"] in {"promoted", "already_active"}),
            "missing_source_json_count": sum(1 for result in tranche_results if result["status"] == "missing_source_json"),
            "conflict_count": sum(1 for result in tranche_results if result["status"] == "conflict"),
            "results": tranche_results,
        }
        write_json(tranche_report_path(tranche_payload["tranche_id"], tranche_reports_dir), tranche_payload)
        tranche_summaries.append(
            {
                "tranche_id": tranche_payload["tranche_id"],
                "case_count": tranche_payload["case_count"],
                "promoted_count": tranche_payload["promoted_count"],
                "missing_source_json_count": tranche_payload["missing_source_json_count"],
                "conflict_count": tranche_payload["conflict_count"],
                "report_path": display_path(tranche_report_path(tranche_payload["tranche_id"], tranche_reports_dir)),
                "paper_ids": tranche_payload["paper_ids"],
            }
        )
    summary = {
        "generated_at_utc": now_utc_iso(),
        "dry_run": dry_run,
        "candidate_count": len(candidates),
        "tranche_size": tranche_size,
        "active_gold_count": sum(
            1
            for entry in (entries if dry_run else load_manifest(manifest_path).get("entries") or [])
            if str(entry.get("gold_status") or "").strip() == "active"
        ),
        "tranches": tranche_summaries,
    }
    write_json(tranche_report_path("bootstrap_summary", tranche_reports_dir), summary)
    return summary
