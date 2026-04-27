from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"
PDF_ACQUISITION_QUEUE_PATH = REPO_ROOT / "data" / "references" / "pdf_acquisition_queue.csv"
PROCEEDINGS_MANUAL_REVIEW_QUEUE_PATH = REPO_ROOT / "data" / "references" / "proceedings_manual_review_queue.csv"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
TEXT_TRIM_LLM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_llm_registry.csv"
PROCEEDINGS_QC_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "proceedings_text_qc_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
SOURCE_COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
CASE_SERIES_SPLIT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "case_series_split_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "paper_revisit_registry.csv"

BAD_ALIGNMENT_TAGS = {"incorrect_reference", "likely_wrong_pdf_attached"}
TRIM_REVISIT_STATUSES = {"manual_review_required", "header_only_source"}
PROCEEDINGS_QC_REVISIT_STATUSES = {
    "header_only_source",
    "mismatch",
    "partial_truncated",
    "spillover_detected",
}
UNRESOLVED_COUNT_STATUSES = {
    "excluded_bad_source_alignment",
    "llm_invalid_manual_review_required",
    "llm_manual_review_required",
    "llm_request_failed_manual_review_required",
    "llm_semantic_conflict_manual_review_required",
    "llm_unable_to_determine",
    "reference_heuristic_manual_review_required",
}


FIELDNAMES = [
    "issue_id",
    "paper_id",
    "covidence_id",
    "title",
    "authors",
    "published_year",
    "journal",
    "stage",
    "issue_type",
    "severity",
    "status",
    "source_registry",
    "source_field",
    "revisit_reason",
    "recommended_action",
    "blocking_downstream",
    "detected_at_utc",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_rows_by_id(path: Path, key_column: str = "paper_id") -> dict[str, dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = str(row.get(key_column) or "").strip()
        if key:
            rows_by_id[key] = dict(row)
    return rows_by_id


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    text = str(paper_id or "").strip()
    try:
        return int(text), text
    except ValueError:
        return 10**9, text


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def context_for_paper(
    paper_id: str,
    *,
    row: dict[str, str],
    artifact_rows: dict[str, dict[str, str]],
) -> dict[str, str]:
    artifact_row = artifact_rows.get(paper_id, {})
    return {
        "paper_id": paper_id,
        "covidence_id": first_non_empty(row.get("covidence_id"), row.get("Covidence"), artifact_row.get("covidence_id"), paper_id),
        "title": first_non_empty(row.get("title"), row.get("Title"), artifact_row.get("title")),
        "authors": first_non_empty(row.get("authors"), row.get("Authors"), artifact_row.get("authors")),
        "published_year": first_non_empty(row.get("published_year"), artifact_row.get("published_year")),
        "journal": first_non_empty(row.get("journal"), artifact_row.get("journal")),
    }


def make_issue(
    *,
    paper_id: str,
    row: dict[str, str],
    artifact_rows: dict[str, dict[str, str]],
    stage: str,
    issue_type: str,
    severity: str,
    status: str,
    source_registry: str,
    source_field: str,
    revisit_reason: str,
    recommended_action: str,
    blocking_downstream: bool,
    detected_at_utc: str = "",
) -> dict[str, str]:
    context = context_for_paper(paper_id, row=row, artifact_rows=artifact_rows)
    issue_id = "|".join([paper_id, stage, issue_type, source_registry])
    return {
        **context,
        "issue_id": issue_id,
        "stage": stage,
        "issue_type": issue_type,
        "severity": severity,
        "status": status,
        "source_registry": source_registry,
        "source_field": source_field,
        "revisit_reason": " ".join(str(revisit_reason or "").split()),
        "recommended_action": recommended_action,
        "blocking_downstream": bool_text(blocking_downstream),
        "detected_at_utc": detected_at_utc or now_utc_iso(),
    }


def add_issue(issues: dict[str, dict[str, str]], issue: dict[str, str]) -> None:
    issues[issue["issue_id"]] = {fieldname: str(issue.get(fieldname) or "") for fieldname in FIELDNAMES}


def collect_pdf_acquisition_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("covidence_id") or row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        download_status = str(row.get("download_status") or "").strip()
        manifest_status = str(row.get("manifest_status") or "").strip()
        manifest_error = str(row.get("manifest_error") or "").strip()
        if download_status not in {"failed", "missing"} and manifest_status != "failed" and not manifest_error:
            continue
        failed = download_status == "failed" or manifest_status == "failed" or bool(manifest_error)
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="01_pdf_acquisition",
                issue_type="pdf_acquisition_failed" if failed else "pdf_missing",
                severity="high" if failed else "medium",
                status=first_non_empty(manifest_status, download_status),
                source_registry=path.name,
                source_field="download_status",
                revisit_reason=first_non_empty(row.get("manifest_error"), row.get("queue_reason")),
                recommended_action="Acquire or retry the PDF, then rebuild PDF, text, source, and artefact registries.",
                blocking_downstream=True,
            ),
        )


def collect_proceedings_manual_queue_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        manual_status = str(row.get("manual_status") or "").strip()
        if manual_status in {"resolved", "reviewed", "not_needed"}:
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="05_proceedings_trim",
                issue_type="proceedings_manual_review_queue",
                severity="medium",
                status=manual_status or "queued",
                source_registry=path.name,
                source_field="manual_status",
                revisit_reason=first_non_empty(row.get("trim_reason"), "Proceedings trim was queued for manual review."),
                recommended_action="Review target abstract boundaries, record the manual decision, and rerun proceedings-ready publication.",
                blocking_downstream=True,
            ),
        )


def collect_text_trim_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        status = str(row.get("trim_status") or "").strip()
        if not paper_id or status not in TRIM_REVISIT_STATUSES:
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="05_proceedings_trim",
                issue_type="trim_manual_review_required",
                severity="high" if status == "header_only_source" else "medium",
                status=status,
                source_registry=path.name,
                source_field="trim_status",
                revisit_reason=str(row.get("trim_reason") or "").strip(),
                recommended_action="Revisit proceedings localisation and publish a safe proceedings-ready text layer.",
                blocking_downstream=True,
            ),
        )


def collect_text_trim_llm_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        trim_status = str(row.get("trim_status") or "").strip()
        validation_reason = str(row.get("llm_validation_reason") or "").strip()
        if not paper_id:
            continue
        if not trim_status.startswith("manual_review_required") and validation_reason in {"", "ok"}:
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="05b_proceedings_llm_validation",
                issue_type=(
                    "llm_trim_manual_review_required"
                    if trim_status.startswith("manual_review_required")
                    else "llm_trim_validation_fallback"
                ),
                severity="medium",
                status=first_non_empty(validation_reason, trim_status),
                source_registry=path.name,
                source_field="llm_validation_reason",
                revisit_reason=str(row.get("trim_reason") or "").strip(),
                recommended_action="Inspect LLM trim validation output and confirm or replace the proceedings-ready boundary.",
                blocking_downstream=True,
            ),
        )


def collect_proceedings_qc_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        status = str(row.get("qc_status") or "").strip()
        manual_follow_up = truthy(row.get("manual_follow_up_required"))
        if not paper_id or (status not in PROCEEDINGS_QC_REVISIT_STATUSES and not manual_follow_up):
            continue
        severity = "medium"
        if status in {"partial_truncated", "header_only_source", "spillover_detected"}:
            severity = "high"
        if status == "mismatch":
            severity = "blocker"
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="05b_proceedings_qc",
                issue_type="proceedings_qc_follow_up_required",
                severity=severity,
                status=status or "manual_follow_up_required",
                source_registry=path.name,
                source_field="qc_status",
                revisit_reason=first_non_empty(row.get("qc_note"), row.get("trim_reason")),
                recommended_action="Review proceedings QC, fix the target span if needed, and rerun proceedings-ready publication.",
                blocking_downstream=True,
                detected_at_utc=str(row.get("checked_at_utc") or "").strip(),
            ),
        )


def collect_source_alignment_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        alignment_tag = str(row.get("pdf_content_alignment_tag") or "").strip()
        if not paper_id or alignment_tag not in BAD_ALIGNMENT_TAGS:
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="02_source_linkage",
                issue_type="source_alignment_failed",
                severity="blocker",
                status=alignment_tag,
                source_registry=path.name,
                source_field="pdf_content_alignment_tag",
                revisit_reason=str(row.get("review_decision_notes") or "").strip(),
                recommended_action="Recover the correct PDF or abstract, rerun extraction and downstream stages from the fixed source.",
                blocking_downstream=True,
                detected_at_utc=str(row.get("reviewed_at_utc") or "").strip(),
            ),
        )


def collect_source_categorisation_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
) -> None:
    for paper_id, row in artifact_rows.items():
        if not truthy(row.get("source_manual_review_required")):
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="04_source_categorisation",
                issue_type="source_category_manual_review_required",
                severity="medium",
                status=first_non_empty(row.get("source_recommended_next_action"), "manual_review_required"),
                source_registry=ARTIFACT_REGISTRY_PATH.name,
                source_field="source_manual_review_required",
                revisit_reason=str(row.get("source_categorisation_reason") or "").strip(),
                recommended_action="Review source category/routing and update the source categorisation manual-review ledger.",
                blocking_downstream=True,
                detected_at_utc=str(row.get("source_categorised_at_utc") or "").strip(),
            ),
        )


def collect_stage06_count_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id:
            continue
        manual_review_required = truthy(row.get("count_manual_review_required"))
        status = str(row.get("count_verification_status") or "").strip()
        basis = str(row.get("count_basis") or "").strip()
        if not manual_review_required and status not in UNRESOLVED_COUNT_STATUSES:
            continue
        if status == "excluded_bad_source_alignment" or basis == "source_linkage_exclusion":
            issue_type = "source_linkage_exclusion"
            severity = "blocker"
            action = "Recover the correct source text/PDF before using any positive count for this paper."
        elif status == "reference_heuristic_manual_review_required":
            issue_type = "reference_heuristic_count_needs_review"
            severity = "medium"
            action = "Review the source or restore run artefacts, then replace the reference-only fallback with reviewed evidence."
        else:
            issue_type = "case_count_manual_review_required"
            severity = "medium"
            action = "Review the count evidence, update the count manual-review ledger or gold corpus, and rerun the stage-06 publish step."
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="06_sps_case_count",
                issue_type=issue_type,
                severity=severity,
                status=first_non_empty(status, "manual_review_required"),
                source_registry=path.name,
                source_field="count_manual_review_required",
                revisit_reason=str(row.get("count_reason") or "").strip(),
                recommended_action=action,
                blocking_downstream=True,
                detected_at_utc=str(row.get("counted_at_utc") or "").strip(),
            ),
        )


def collect_case_series_split_issues(
    *,
    issues: dict[str, dict[str, str]],
    artifact_rows: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        status = str(row.get("split_status") or "").strip()
        if not paper_id or (status != "manual_review_required" and not truthy(row.get("manual_review_required"))):
            continue
        add_issue(
            issues,
            make_issue(
                paper_id=paper_id,
                row=row,
                artifact_rows=artifact_rows,
                stage="07_case_series_split",
                issue_type="case_series_split_manual_review_required",
                severity="medium",
                status=status or "manual_review_required",
                source_registry=path.name,
                source_field="split_status",
                revisit_reason=str(row.get("split_reason") or "").strip(),
                recommended_action="Review case boundaries manually or mark the paper unsuitable for case-level splitting.",
                blocking_downstream=True,
                detected_at_utc=str(row.get("split_at_utc") or "").strip(),
            ),
        )


def build_revisit_rows(
    *,
    artifact_registry_path: Path = ARTIFACT_REGISTRY_PATH,
    pdf_acquisition_queue_path: Path = PDF_ACQUISITION_QUEUE_PATH,
    proceedings_manual_review_queue_path: Path = PROCEEDINGS_MANUAL_REVIEW_QUEUE_PATH,
    text_trim_registry_path: Path = TEXT_TRIM_REGISTRY_PATH,
    text_trim_llm_registry_path: Path = TEXT_TRIM_LLM_REGISTRY_PATH,
    proceedings_qc_registry_path: Path = PROCEEDINGS_QC_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    source_count_registry_path: Path = SOURCE_COUNT_REGISTRY_PATH,
    case_series_split_registry_path: Path = CASE_SERIES_SPLIT_REGISTRY_PATH,
) -> list[dict[str, str]]:
    artifact_rows = load_csv_rows_by_id(artifact_registry_path)
    issues: dict[str, dict[str, str]] = {}
    collect_pdf_acquisition_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=pdf_acquisition_queue_path,
    )
    collect_proceedings_manual_queue_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=proceedings_manual_review_queue_path,
    )
    collect_text_trim_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=text_trim_registry_path,
    )
    collect_text_trim_llm_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=text_trim_llm_registry_path,
    )
    collect_proceedings_qc_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=proceedings_qc_registry_path,
    )
    collect_source_alignment_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=source_manual_review_path,
    )
    collect_source_categorisation_issues(
        issues=issues,
        artifact_rows=artifact_rows,
    )
    collect_stage06_count_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=source_count_registry_path,
    )
    collect_case_series_split_issues(
        issues=issues,
        artifact_rows=artifact_rows,
        path=case_series_split_registry_path,
    )
    return sorted(
        issues.values(),
        key=lambda row: (
            sort_key_for_paper_id(row["paper_id"]),
            row["stage"],
            row["issue_type"],
            row["source_registry"],
        ),
    )


def write_revisit_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = Path(handle.name)
    temp_path.replace(output_path)


def write_summary(rows: list[dict[str, str]], summary_path: Path) -> None:
    by_stage: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    paper_ids = {row["paper_id"] for row in rows}
    for row in rows:
        by_stage[row["stage"]] = by_stage.get(row["stage"], 0) + 1
        by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + 1
    payload = {
        "generated_at_utc": now_utc_iso(),
        "schema_version": "paper_revisit_summary_v1",
        "issue_count": len(rows),
        "paper_count": len(paper_ids),
        "by_stage": dict(sorted(by_stage.items())),
        "by_severity": dict(sorted(by_severity.items())),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the cross-stage registry of papers that failed QC/processing or require manual revisit."
    )
    parser.add_argument("--artifact-registry-path", type=Path, default=ARTIFACT_REGISTRY_PATH)
    parser.add_argument("--pdf-acquisition-queue-path", type=Path, default=PDF_ACQUISITION_QUEUE_PATH)
    parser.add_argument("--proceedings-manual-review-queue-path", type=Path, default=PROCEEDINGS_MANUAL_REVIEW_QUEUE_PATH)
    parser.add_argument("--text-trim-registry-path", type=Path, default=TEXT_TRIM_REGISTRY_PATH)
    parser.add_argument("--text-trim-llm-registry-path", type=Path, default=TEXT_TRIM_LLM_REGISTRY_PATH)
    parser.add_argument("--proceedings-qc-registry-path", type=Path, default=PROCEEDINGS_QC_REGISTRY_PATH)
    parser.add_argument("--source-manual-review-path", type=Path, default=SOURCE_MANUAL_REVIEW_PATH)
    parser.add_argument("--source-count-registry-path", type=Path, default=SOURCE_COUNT_REGISTRY_PATH)
    parser.add_argument("--case-series-split-registry-path", type=Path, default=CASE_SERIES_SPLIT_REGISTRY_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--summary-json-path", type=Path, default=OUTPUT_PATH.with_suffix(".summary.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_revisit_rows(
        artifact_registry_path=args.artifact_registry_path,
        pdf_acquisition_queue_path=args.pdf_acquisition_queue_path,
        proceedings_manual_review_queue_path=args.proceedings_manual_review_queue_path,
        text_trim_registry_path=args.text_trim_registry_path,
        text_trim_llm_registry_path=args.text_trim_llm_registry_path,
        proceedings_qc_registry_path=args.proceedings_qc_registry_path,
        source_manual_review_path=args.source_manual_review_path,
        source_count_registry_path=args.source_count_registry_path,
        case_series_split_registry_path=args.case_series_split_registry_path,
    )
    write_revisit_rows(rows, args.output_path)
    write_summary(rows, args.summary_json_path)
    print(f"Wrote {len(rows)} revisit issues for {len({row['paper_id'] for row in rows})} papers to {args.output_path}")


if __name__ == "__main__":
    main()
