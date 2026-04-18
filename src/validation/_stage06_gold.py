from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_count_registry import count_eligible
from src.validation import _stage04_gold as gold
from src.validation import _stage06_review as review


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_STANDARD_ROOT = gold.GOLD_STANDARD_ROOT
GOLD_MASTER_PATH = gold.GOLD_MASTER_PATH
SOURCE_REGISTRY_PATH = gold.SOURCE_REGISTRY_PATH
COUNT_REGISTRY_PATH = gold.COUNT_REGISTRY_PATH
ARTIFACT_REGISTRY_PATH = gold.ARTIFACT_REGISTRY_PATH

STAGE06_GOLD_DIR = GOLD_STANDARD_ROOT / "stage06_count_gold"
GOLD_PAPERS_DIR = STAGE06_GOLD_DIR / "papers"
MANIFEST_PATH = STAGE06_GOLD_DIR / "manifest.json"

BAD_ALIGNMENT_TAGS = {"likely_wrong_pdf_attached", "incorrect_reference"}
GOLD_COUNT_VERSION = "gold_reviewed_stage06_v1"
GOLD_SCHEMA_VERSION = "stage06_count_gold_result_v1"
MANIFEST_SCHEMA_VERSION = "stage06_count_gold_manifest_v1"

display_path = gold.display_path
first_pipe_separated_value = gold.first_pipe_separated_value
load_csv_rows = gold.load_csv_rows
load_csv_rows_by_id = gold.load_csv_rows_by_id
now_utc_iso = gold.now_utc_iso
parse_int = gold.parse_int
resolve_repo_path = gold.resolve_repo_path
truthy = gold.truthy


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def normalise_space(text: str) -> str:
    return " ".join(str(text or "").split())


def first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def json_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reviewed_row_groups(master_path: Path = GOLD_MASTER_PATH) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_csv_rows(master_path):
        if str(row.get("review_status") or "").strip() != "reviewed":
            continue
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        grouped[paper_id].append(dict(row))
    return grouped


def review_signature(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        str(row.get("reviewed_source_category") or "").strip(),
        str(row.get("reviewed_extractable_sps_case_count") or "").strip(),
        str(row.get("pdf_content_alignment_tag") or "").strip(),
    )


def latest_review_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(
        rows,
        key=lambda row: (
            str(row.get("reviewed_at_utc") or "").strip(),
            str(row.get("round_id") or "").strip(),
        ),
    )


def gold_json_path(paper_id: str, gold_papers_dir: Path = GOLD_PAPERS_DIR) -> Path:
    return gold_papers_dir / f"{paper_id}.json"


def load_attached_run_payloads(paper_id: str) -> dict[str, Any]:
    attached_paths = review.latest_run_artifacts_for_paper(paper_id, root=review.RUN_ROOT)

    def _load(path_key: str) -> dict[str, Any] | None:
        raw_path = str(attached_paths.get(path_key) or "").strip()
        if not raw_path:
            return None
        payload = load_json(resolve_repo_path(raw_path))
        return payload or None

    return {
        "run_id": str(attached_paths.get("attached_run_id") or "").strip(),
        "result_json_path": str(attached_paths.get("attached_result_json_path") or "").strip(),
        "candidate_json_path": str(attached_paths.get("attached_candidate_json_path") or "").strip(),
        "count_decision_json_path": str(attached_paths.get("attached_count_decision_json_path") or "").strip(),
        "count_evidence_json_path": str(attached_paths.get("attached_count_evidence_json_path") or "").strip(),
        "result_payload": _load("attached_result_json_path"),
        "candidate_payload": _load("attached_candidate_json_path"),
        "count_decision_payload": _load("attached_count_decision_json_path"),
        "count_evidence_payload": _load("attached_count_evidence_json_path"),
    }


def source_text_json_path(
    *,
    artifact_row: dict[str, str],
    gold_row: dict[str, str],
    count_row: dict[str, str],
) -> str:
    return first_non_empty(
        artifact_row.get("text_json_path"),
        gold_row.get("preferred_text_json_path"),
        count_row.get("preferred_text_json_path"),
    )


def preferred_text_json_path(
    *,
    gold_row: dict[str, str],
    count_row: dict[str, str],
    source_row: dict[str, str],
    fallback_source_text_json_path: str,
) -> str:
    return first_non_empty(
        gold_row.get("preferred_text_json_path"),
        count_row.get("preferred_text_json_path"),
        source_row.get("preferred_text_json_path"),
        source_row.get("text_json_path"),
        fallback_source_text_json_path,
    )


def reviewed_source_subtype(
    *,
    reviewed_source_category: str,
    gold_row: dict[str, str],
    count_row: dict[str, str],
    source_row: dict[str, str],
) -> str:
    for row in (count_row, source_row):
        category = str(row.get("source_category") or "").strip()
        subtype = str(row.get("source_subtype") or "").strip()
        if category == reviewed_source_category and subtype:
            return subtype
    predicted_category = str(gold_row.get("predicted_source_category") or "").strip()
    if predicted_category == reviewed_source_category:
        return str(gold_row.get("predicted_source_subtype") or "").strip()
    return ""


def build_count_reason(
    *,
    gold_row: dict[str, str],
    count_row: dict[str, str],
    reviewed_source_category: str,
    reviewed_count: str,
) -> str:
    prediction_correct = truthy(gold_row.get("prediction_correct") or "")
    predicted_count = first_non_empty(
        gold_row.get("predicted_likely_sps_case_count"),
        count_row.get("likely_sps_case_count"),
        reviewed_count,
    )
    predicted_source_category = first_non_empty(
        gold_row.get("predicted_source_category"),
        count_row.get("source_category"),
    )
    parts = [
        "count_basis=manual_gold_review",
        "count_confidence=high",
        f"round_id={str(gold_row.get('round_id') or '').strip()}",
        f"selection_bucket={str(gold_row.get('selection_bucket') or '').strip()}",
        f"prediction_correct={'true' if prediction_correct else 'false'}",
        f"reviewed_count={reviewed_count}",
        f"reviewed_source_category={reviewed_source_category}",
    ]
    if predicted_count:
        parts.append(f"predicted_count={predicted_count}")
    if predicted_source_category:
        parts.append(f"predicted_source_category={predicted_source_category}")
    reviewer_notes = normalise_space(str(gold_row.get("reviewer_notes") or ""))
    if reviewer_notes:
        parts.append(f"reviewer_notes={reviewer_notes}")
    return " | ".join(parts)


def build_gold_count_row(
    *,
    gold_row: dict[str, str],
    count_row: dict[str, str],
    source_row: dict[str, str],
    artifact_row: dict[str, str],
) -> dict[str, str]:
    reviewed_source_category = first_non_empty(
        gold_row.get("reviewed_source_category"),
        count_row.get("source_category"),
        source_row.get("source_category"),
        gold_row.get("predicted_source_category"),
    )
    reviewed_count = first_non_empty(
        gold_row.get("reviewed_extractable_sps_case_count"),
        count_row.get("likely_sps_case_count"),
        "0",
    )
    provenance_uncertain = (
        reviewed_source_category == "review_format_with_embedded_original_cohort"
        or truthy(count_row.get("count_original_cohort_provenance_uncertain") or "")
    )
    source_text_path = source_text_json_path(
        artifact_row=artifact_row,
        gold_row=gold_row,
        count_row=count_row,
    )
    preferred_text_path = preferred_text_json_path(
        gold_row=gold_row,
        count_row=count_row,
        source_row=source_row,
        fallback_source_text_json_path=source_text_path,
    )
    preferred_text_source_value = first_non_empty(
        gold_row.get("preferred_text_source"),
        count_row.get("preferred_text_source"),
        source_row.get("preferred_text_source"),
        "full_text",
    )
    return {
        "paper_id": str(gold_row.get("paper_id") or "").strip(),
        "covidence_id": first_non_empty(gold_row.get("covidence_id"), count_row.get("covidence_id")),
        "title": first_non_empty(gold_row.get("title"), count_row.get("title"), source_row.get("title")),
        "authors": first_non_empty(gold_row.get("authors"), count_row.get("authors"), source_row.get("authors")),
        "source_category": reviewed_source_category,
        "source_subtype": reviewed_source_subtype(
            reviewed_source_category=reviewed_source_category,
            gold_row=gold_row,
            count_row=count_row,
            source_row=source_row,
        ),
        "preferred_text_json_path": preferred_text_path,
        "preferred_text_source": preferred_text_source_value,
        "count_eligible": "true" if count_eligible(reviewed_source_category) else "false",
        "likely_sps_case_count": reviewed_count,
        "count_confidence": "high",
        "count_basis": "manual_gold_review",
        "count_manual_review_required": "false",
        "count_original_cohort_provenance_uncertain": "true" if provenance_uncertain else "false",
        "count_reason": build_count_reason(
            gold_row=gold_row,
            count_row=count_row,
            reviewed_source_category=reviewed_source_category,
            reviewed_count=reviewed_count,
        ),
        "count_version": GOLD_COUNT_VERSION,
        "counted_at_utc": first_non_empty(gold_row.get("reviewed_at_utc"), now_utc_iso()),
    }


def build_gold_payload(
    *,
    gold_row: dict[str, str],
    count_row: dict[str, str],
    source_row: dict[str, str],
    artifact_row: dict[str, str],
    attached_run_payloads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attached_run_payloads = attached_run_payloads or load_attached_run_payloads(str(gold_row.get("paper_id") or "").strip())
    count_payload = build_gold_count_row(
        gold_row=gold_row,
        count_row=count_row,
        source_row=source_row,
        artifact_row=artifact_row,
    )
    source_text_path = source_text_json_path(
        artifact_row=artifact_row,
        gold_row=gold_row,
        count_row=count_row,
    )
    preferred_text_path = str(count_payload.get("preferred_text_json_path") or "").strip()
    return {
        "schema_version": GOLD_SCHEMA_VERSION,
        "generated_at_utc": now_utc_iso(),
        "paper_id": str(gold_row.get("paper_id") or "").strip(),
        "count_row": count_payload,
        "source_text_json_path": source_text_path,
        "preferred_text_json_path": preferred_text_path,
        "paper_context": {
            "covidence_id": first_non_empty(gold_row.get("covidence_id"), count_row.get("covidence_id")),
            "title": first_non_empty(gold_row.get("title"), count_row.get("title"), source_row.get("title")),
            "authors": first_non_empty(gold_row.get("authors"), count_row.get("authors"), source_row.get("authors")),
            "published_year": str(gold_row.get("published_year") or source_row.get("published_year") or "").strip(),
            "journal": str(gold_row.get("journal") or source_row.get("journal") or "").strip(),
            "pdf_filename": first_pipe_separated_value(artifact_row.get("pdf_filenames") or gold_row.get("pdf_filename") or ""),
            "pdf_path_relative": first_non_empty(
                gold_row.get("pdf_path_relative"),
                first_pipe_separated_value(artifact_row.get("pdf_paths_relative") or ""),
            ),
        },
        "gold_review": {
            "round_id": str(gold_row.get("round_id") or "").strip(),
            "selection_bucket": str(gold_row.get("selection_bucket") or "").strip(),
            "selection_signals": str(gold_row.get("selection_signals") or "").strip(),
            "prediction_correct": truthy(gold_row.get("prediction_correct") or ""),
            "reviewed_source_category": str(gold_row.get("reviewed_source_category") or "").strip(),
            "reviewed_extractable_sps_case_count": str(
                gold_row.get("reviewed_extractable_sps_case_count") or ""
            ).strip(),
            "pdf_content_alignment_tag": str(gold_row.get("pdf_content_alignment_tag") or "").strip(),
            "reviewer_notes": str(gold_row.get("reviewer_notes") or "").strip(),
            "reviewer_id": str(gold_row.get("reviewer_id") or "").strip(),
            "reviewed_at_utc": str(gold_row.get("reviewed_at_utc") or "").strip(),
            "source_gold_master_path": display_path(GOLD_MASTER_PATH),
        },
        "prediction_snapshot": {
            "gold_master_row": dict(gold_row),
            "live_count_registry_row": dict(count_row),
            "live_source_registry_row": dict(source_row),
        },
        "attached_run_artifacts": attached_run_payloads,
    }


def manifest_entry(
    *,
    paper_id: str,
    status: str,
    gold_row: dict[str, str],
    payload: dict[str, Any] | None,
    attached_run_payloads: dict[str, Any],
    reason: str = "",
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
) -> dict[str, Any]:
    json_path = gold_json_path(paper_id, gold_papers_dir)
    return {
        "paper_id": paper_id,
        "gold_status": status,
        "reason": reason,
        "gold_json_path": display_path(json_path) if status == "active" else "",
        "canonical_json_hash": json_sha256(payload) if payload is not None else "",
        "round_id": str(gold_row.get("round_id") or "").strip(),
        "selection_bucket": str(gold_row.get("selection_bucket") or "").strip(),
        "prediction_correct": str(gold_row.get("prediction_correct") or "").strip(),
        "reviewed_source_category": str(gold_row.get("reviewed_source_category") or "").strip(),
        "reviewed_extractable_sps_case_count": str(gold_row.get("reviewed_extractable_sps_case_count") or "").strip(),
        "pdf_content_alignment_tag": str(gold_row.get("pdf_content_alignment_tag") or "").strip(),
        "reviewer_id": str(gold_row.get("reviewer_id") or "").strip(),
        "reviewed_at_utc": str(gold_row.get("reviewed_at_utc") or "").strip(),
        "attached_run_id": str(attached_run_payloads.get("run_id") or "").strip(),
        "has_attached_result_payload": attached_run_payloads.get("result_payload") is not None,
        "has_attached_candidate_payload": attached_run_payloads.get("candidate_payload") is not None,
        "has_attached_count_decision_payload": attached_run_payloads.get("count_decision_payload") is not None,
        "has_attached_count_evidence_payload": attached_run_payloads.get("count_evidence_payload") is not None,
    }


def empty_manifest() -> dict[str, Any]:
    return {
        "generated_at_utc": now_utc_iso(),
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_gold_master_path": display_path(GOLD_MASTER_PATH),
        "active_paper_count": 0,
        "excluded_paper_count": 0,
        "conflict_paper_count": 0,
        "entries": [],
    }


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not manifest_path.exists():
        return empty_manifest()
    payload = load_json(manifest_path)
    if not isinstance(payload, dict):
        return empty_manifest()
    return payload


def save_manifest(entries: list[dict[str, Any]], manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    ordered_entries = sorted(entries, key=lambda entry: parse_int(str(entry.get("paper_id") or ""), default=10**9))
    payload = {
        "generated_at_utc": now_utc_iso(),
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_gold_master_path": display_path(GOLD_MASTER_PATH),
        "active_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "active"),
        "excluded_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "excluded"),
        "conflict_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "conflict"),
        "entries": ordered_entries,
    }
    write_json(manifest_path, payload)
    return payload


def merge_preserved_manifest_entries(
    *,
    existing_entries: list[dict[str, Any]],
    updated_entries: list[dict[str, Any]],
    replaced_paper_ids: set[str],
) -> list[dict[str, Any]]:
    merged_by_paper_id: dict[str, dict[str, Any]] = {}
    for entry in existing_entries:
        paper_id = str(entry.get("paper_id") or "").strip()
        if not paper_id or paper_id in replaced_paper_ids:
            continue
        merged_by_paper_id[paper_id] = dict(entry)
    for entry in updated_entries:
        paper_id = str(entry.get("paper_id") or "").strip()
        if not paper_id:
            continue
        merged_by_paper_id[paper_id] = dict(entry)
    return list(merged_by_paper_id.values())


def bootstrap_stage06_gold_store(
    *,
    gold_master_path: Path = GOLD_MASTER_PATH,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    count_registry_path: Path = COUNT_REGISTRY_PATH,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
    gold_papers_dir: Path = GOLD_PAPERS_DIR,
    manifest_path: Path = MANIFEST_PATH,
    paper_ids: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    paper_id_filter = {paper_id.strip() for paper_id in (paper_ids or []) if paper_id.strip()}
    source_rows = load_csv_rows_by_id(source_registry_path, "paper_id")
    count_rows = load_csv_rows_by_id(count_registry_path, "paper_id")
    artifact_rows = load_csv_rows_by_id(artifact_registry_path, "paper_id")
    review_groups = reviewed_row_groups(gold_master_path)

    entries: list[dict[str, Any]] = []
    for paper_id in sorted(review_groups, key=lambda value: parse_int(value, default=10**9)):
        if paper_id_filter and paper_id not in paper_id_filter:
            continue

        grouped_rows = review_groups[paper_id]
        signatures = {review_signature(row) for row in grouped_rows}
        chosen_row = latest_review_row(grouped_rows)
        attached_payloads = load_attached_run_payloads(paper_id)

        if len(signatures) > 1:
            entries.append(
                manifest_entry(
                    paper_id=paper_id,
                    status="conflict",
                    gold_row=chosen_row,
                    payload=None,
                    attached_run_payloads=attached_payloads,
                    reason="multiple_distinct_reviewed_truth_rows",
                    gold_papers_dir=gold_papers_dir,
                )
            )
            continue

        alignment_tag = str(chosen_row.get("pdf_content_alignment_tag") or "").strip()
        if alignment_tag in BAD_ALIGNMENT_TAGS:
            entries.append(
                manifest_entry(
                    paper_id=paper_id,
                    status="excluded",
                    gold_row=chosen_row,
                    payload=None,
                    attached_run_payloads=attached_payloads,
                    reason=f"bad_alignment:{alignment_tag}",
                    gold_papers_dir=gold_papers_dir,
                )
            )
            continue

        count_row = dict(count_rows.get(paper_id, {}))
        source_row = dict(source_rows.get(paper_id, {}))
        artifact_row = dict(artifact_rows.get(paper_id, {}))
        payload = build_gold_payload(
            gold_row=chosen_row,
            count_row=count_row,
            source_row=source_row,
            artifact_row=artifact_row,
            attached_run_payloads=attached_payloads,
        )
        if not dry_run:
            write_json(gold_json_path(paper_id, gold_papers_dir), payload)
        entries.append(
            manifest_entry(
                paper_id=paper_id,
                status="active",
                gold_row=chosen_row,
                payload=payload,
                attached_run_payloads=attached_payloads,
                gold_papers_dir=gold_papers_dir,
            )
        )

    if dry_run:
        ordered_entries = sorted(entries, key=lambda entry: parse_int(str(entry.get("paper_id") or ""), default=10**9))
        return {
            "generated_at_utc": now_utc_iso(),
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "source_gold_master_path": display_path(gold_master_path),
            "active_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "active"),
            "excluded_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "excluded"),
            "conflict_paper_count": sum(1 for entry in ordered_entries if entry.get("gold_status") == "conflict"),
            "entries": ordered_entries,
        }
    if paper_id_filter:
        existing_entries = list(load_manifest(manifest_path).get("entries") or [])
        entries = merge_preserved_manifest_entries(
            existing_entries=existing_entries,
            updated_entries=entries,
            replaced_paper_ids=paper_id_filter,
        )
    return save_manifest(entries, manifest_path)
