from __future__ import annotations

import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_REVIEW_LEDGER_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_manual_review.csv"

OVERRIDE_FIELDNAMES = [
    "source_scope_id",
    "source_scope_label",
    "paper_id",
    "title",
    "predicted_count",
    "predicted_original_cohort_provenance_uncertain",
    "predicted_verification_status",
    "prediction_correct",
    "reviewed_count",
    "reviewed_original_cohort_provenance_uncertain",
    "review_status",
    "reviewer_notes",
    "reviewer_id",
    "reviewed_at_utc",
    "updated_at_utc",
]


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    text = str(paper_id or "").strip()
    try:
        return int(text), text
    except ValueError:
        return 10**9, text


def ensure_override_ledger(path: Path = MANUAL_REVIEW_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OVERRIDE_FIELDNAMES)
        writer.writeheader()


def load_override_rows(path: Path = MANUAL_REVIEW_LEDGER_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_override_rows_by_id(path: Path = MANUAL_REVIEW_LEDGER_PATH) -> dict[str, dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in load_override_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            rows_by_id[paper_id] = dict(row)
    return rows_by_id


def reviewed_override_rows_by_id(path: Path = MANUAL_REVIEW_LEDGER_PATH) -> dict[str, dict[str, str]]:
    return {
        paper_id: row
        for paper_id, row in load_override_rows_by_id(path).items()
        if str(row.get("review_status") or "").strip() == "reviewed"
    }


def upsert_override_row(
    row: dict[str, str],
    *,
    path: Path = MANUAL_REVIEW_LEDGER_PATH,
) -> dict[str, dict[str, str]]:
    ensure_override_ledger(path)
    paper_id = str(row.get("paper_id") or "").strip()
    if not paper_id:
        raise ValueError("Override row is missing paper_id.")

    rows_by_id = load_override_rows_by_id(path)
    rows_by_id[paper_id] = {
        fieldname: str(row.get(fieldname) or "").strip()
        for fieldname in OVERRIDE_FIELDNAMES
    }
    ordered_rows = [
        rows_by_id[candidate_paper_id]
        for candidate_paper_id in sorted(rows_by_id, key=sort_key_for_paper_id)
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OVERRIDE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(ordered_rows)
    return rows_by_id


def override_reviewed_count(row: dict[str, str]) -> str:
    reviewed_count = str(row.get("reviewed_count") or "").strip()
    if reviewed_count:
        return reviewed_count
    if str(row.get("prediction_correct") or "").strip() == "true":
        return str(row.get("predicted_count") or "").strip()
    return ""


def _override_count_version(existing: str) -> str:
    base = str(existing or "").strip()
    if not base:
        return "manual_review_override_v1"
    if base.endswith("+manual_review_override"):
        return base
    return f"{base}+manual_review_override"


def _root_prior_reason(existing: str) -> str:
    reason = str(existing or "").strip()
    while reason.startswith("manual_review_override_applied=true") and " | prior_reason=" in reason:
        reason = reason.split(" | prior_reason=", 1)[1].strip()
    if reason.startswith("manual_review_override_applied=true"):
        return ""
    return reason


def apply_override_to_count_row(
    count_row: dict[str, str],
    override_row: dict[str, str],
) -> dict[str, str]:
    reviewed_count = override_reviewed_count(override_row)
    if not reviewed_count:
        raise ValueError("Reviewed override row is missing reviewed_count.")

    overridden = dict(count_row)
    prior_reason = _root_prior_reason(str(count_row.get("count_reason") or ""))
    reason_bits = [
        "manual_review_override_applied=true",
        f"source_scope_id={str(override_row.get('source_scope_id') or '').strip()}",
        f"predicted_count={str(override_row.get('predicted_count') or '').strip()}",
        f"prediction_correct={str(override_row.get('prediction_correct') or '').strip()}",
        f"reviewed_count={reviewed_count}",
    ]
    reviewer_notes = str(override_row.get("reviewer_notes") or "").strip()
    if reviewer_notes:
        reason_bits.append(f"reviewer_notes={reviewer_notes}")
    if prior_reason:
        reason_bits.append(f"prior_reason={prior_reason}")

    overridden.update(
        {
            "likely_sps_case_count": reviewed_count,
            "count_confidence": "high",
            "count_basis": "manual_review_override",
            "count_manual_review_required": "false",
            "count_original_cohort_provenance_uncertain": str(
                override_row.get("reviewed_original_cohort_provenance_uncertain")
                or override_row.get("predicted_original_cohort_provenance_uncertain")
                or count_row.get("count_original_cohort_provenance_uncertain")
                or "false"
            ).strip(),
            "count_reason": " | ".join(reason_bits),
            "count_version": _override_count_version(str(count_row.get("count_version") or "")),
            "count_audit_status": "manual_review_override",
            "count_verification_status": "manual_review_override",
            "counted_at_utc": str(
                override_row.get("updated_at_utc")
                or override_row.get("reviewed_at_utc")
                or count_row.get("counted_at_utc")
                or ""
            ).strip(),
        }
    )
    return overridden


def apply_reviewed_overrides_to_rows(
    rows: list[dict[str, str]],
    override_rows: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    updated_rows: list[dict[str, str]] = []
    applied_paper_ids: list[str] = []
    for row in rows:
        paper_id = str(row.get("paper_id") or "").strip()
        override_row = override_rows.get(paper_id)
        if override_row is None:
            updated_rows.append(dict(row))
            continue
        updated_rows.append(apply_override_to_count_row(row, override_row))
        applied_paper_ids.append(paper_id)
    return updated_rows, applied_paper_ids
