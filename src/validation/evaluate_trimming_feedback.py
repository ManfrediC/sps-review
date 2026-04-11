from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._source_routing import load_csv_rows_by_id, resolve_source_row
from src.pipelines._proceedings_text import normalize_text


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "qa" / "trimming" / "reports"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
UNINFORMATIVE_END_SECTION_RE = re.compile(r"\b(?:references?|disclosures?)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class ReportBundle:
    name: str
    report_dir: Path
    trim_rows: dict[str, dict[str, str]]
    qc_rows: dict[str, dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate proceedings-trimming batch outputs against stored human feedback fixtures."
    )
    parser.add_argument(
        "--feedback-path",
        action="append",
        required=True,
        help="Path to a structured feedback or regression JSON file. Repeat for multiple files.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Root directory containing per-batch trimming reports.",
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
        "--output-path",
        type=Path,
        required=True,
        help="JSON file to write the evaluation report to.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def discover_report_bundles(reports_dir: Path) -> dict[str, ReportBundle]:
    bundles: dict[str, ReportBundle] = {}
    if not reports_dir.exists():
        return bundles
    for child in sorted(reports_dir.iterdir()):
        if not child.is_dir():
            continue
        trim_registry_path = child / "text_trim_registry.csv"
        qc_registry_path = child / "proceedings_text_qc_registry.csv"
        if not trim_registry_path.exists() or not qc_registry_path.exists():
            continue
        bundles[child.name] = ReportBundle(
            name=child.name,
            report_dir=child,
            trim_rows=rows_by_id(trim_registry_path),
            qc_rows=rows_by_id(qc_registry_path),
        )
    return bundles


def normalise_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def collapse_alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(text))


def contains_normalised_text(haystack: str, needle: str) -> bool:
    haystack_norm = normalize_text(haystack)
    needle_norm = normalize_text(needle)
    if not needle_norm:
        return False
    if needle_norm in haystack_norm:
        return True
    haystack_compact = collapse_alnum(haystack)
    needle_compact = collapse_alnum(needle)
    return bool(needle_compact) and needle_compact in haystack_compact


def contains_approximate_text(haystack: str, needle: str) -> bool:
    if contains_normalised_text(haystack, needle):
        return True
    haystack_tokens = normalize_text(haystack).split()
    needle_norm = normalize_text(needle)
    needle_tokens = needle_norm.split()
    if not haystack_tokens or not needle_tokens:
        return False

    min_window = max(1, len(needle_tokens) - 3)
    max_window = min(len(haystack_tokens), len(needle_tokens) + 6)
    for start_index in range(len(haystack_tokens)):
        for window_size in range(min_window, max_window + 1):
            end_index = start_index + window_size
            if end_index > len(haystack_tokens):
                break
            candidate = " ".join(haystack_tokens[start_index:end_index])
            if SequenceMatcher(None, needle_norm, candidate).ratio() >= 0.88:
                return True
    return False


def expected_end_variants(expected_end: str) -> list[str]:
    cleaned = str(expected_end or "").strip()
    if not cleaned:
        return []
    variants = [cleaned]
    match = UNINFORMATIVE_END_SECTION_RE.search(cleaned)
    if match:
        prefix = cleaned[: match.start()].strip(" .;:-")
        if prefix:
            variants.append(prefix)
    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        normalized = normalize_text(variant)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(variant)
    return deduped


def display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_feedback_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def feedback_id(payload: dict[str, Any], path: Path) -> str:
    return (
        str(payload.get("regression_set_id") or "").strip()
        or str(payload.get("feedback_round_id") or "").strip()
        or path.stem
    )


def feedback_batch_id(payload: dict[str, Any]) -> str:
    return str(payload.get("batch_id") or "").strip()


def pick_report_bundle(
    paper_id: str,
    payload: dict[str, Any],
    workflow_stage: str,
    bundles: dict[str, ReportBundle],
) -> ReportBundle | None:
    preferred_name = feedback_batch_id(payload)
    if preferred_name and preferred_name in bundles:
        return bundles[preferred_name]

    candidates = [
        bundle
        for bundle in bundles.values()
        if paper_id in bundle.trim_rows or paper_id in bundle.qc_rows
    ]
    if workflow_stage == "stage05_trimming" and "regression_boundary_review" in bundles:
        boundary_bundle = bundles["regression_boundary_review"]
        if paper_id in boundary_bundle.trim_rows or paper_id in boundary_bundle.qc_rows:
            return boundary_bundle
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return sorted(candidates, key=lambda bundle: bundle.name)[0]
    return None


def resolve_workflow_stage(case: dict[str, Any], resolved_source_category: str) -> str:
    explicit_stage = str(case.get("workflow_stage") or "").strip()
    if explicit_stage:
        return explicit_stage
    expected_manual_review = bool(case.get("expected_manual_review"))
    if expected_manual_review and resolved_source_category != "conference_abstract":
        return "routing_gate"
    if expected_manual_review:
        return "stage05_not_needed"
    return "stage05_trimming"


def trimmed_text_payload(path: Path | None) -> tuple[str, list[str]]:
    if path is None or not path.exists():
        return "", []
    payload = json.loads(path.read_text(encoding="utf-8"))
    lines: list[str] = []
    chunks: list[str] = []
    for page in payload.get("pages") or []:
        page_text = str(page.get("text") or "")
        if page_text:
            chunks.append(page_text)
            lines.extend(line.strip() for line in page_text.splitlines() if line.strip())
    return "\n".join(chunks), lines


def start_anchor_matches(trimmed_text: str, trimmed_lines: list[str], expected_start: str) -> bool:
    if not expected_start:
        return False
    actual_start = trimmed_lines[0] if trimmed_lines else ""
    if actual_start == expected_start:
        return True
    start_region = " ".join(trimmed_lines[: min(len(trimmed_lines), 12)]) or trimmed_text
    variants = [expected_start]
    normalised_tokens = normalize_text(expected_start).split()
    for token_limit in (18, 12, 8):
        if len(normalised_tokens) >= token_limit:
            variants.append(" ".join(normalised_tokens[:token_limit]))
    return any(contains_approximate_text(start_region, variant) for variant in variants if variant)


def trimmed_output_path(trim_row: dict[str, str], bundle: ReportBundle | None, paper_id: str) -> Path | None:
    raw_path = str(trim_row.get("trimmed_text_json_path") or "").strip()
    if raw_path:
        return REPO_ROOT / raw_path
    if bundle is None:
        return None
    candidate = bundle.report_dir / "text_trimmed" / f"{paper_id}.json"
    return candidate if candidate.exists() else None


def bool_from_text(value: str) -> bool:
    return str(value or "").strip().lower() == "true"


def evaluate_routing_gate(
    resolved_source_category: str,
) -> list[dict[str, Any]]:
    return [
        {
            "name": "resolved_source_category_not_conference_abstract",
            "passed": resolved_source_category != "conference_abstract",
            "actual": resolved_source_category,
        }
    ]


def evaluate_not_needed(
    trim_row: dict[str, str],
    qc_row: dict[str, str],
    expected_manual_review: bool,
) -> list[dict[str, Any]]:
    trim_status = str(trim_row.get("trim_status") or "").strip()
    return [
        {
            "name": "trim_status_matches_not_needed",
            "passed": trim_status == "not_needed",
            "actual": trim_status,
        },
        {
            "name": "manual_follow_up_matches",
            "passed": bool_from_text(qc_row.get("manual_follow_up_required") or "") == expected_manual_review,
            "actual": bool_from_text(qc_row.get("manual_follow_up_required") or ""),
        },
    ]


def evaluate_trimmed_case(
    case: dict[str, Any],
    trim_row: dict[str, str],
    qc_row: dict[str, str],
    bundle: ReportBundle | None,
) -> list[dict[str, Any]]:
    paper_id = str(case.get("paper_id") or "").strip()
    trimmed_path = trimmed_output_path(trim_row, bundle, paper_id)
    trimmed_text, trimmed_lines = trimmed_text_payload(trimmed_path)
    flattened_text = normalise_whitespace(trimmed_text)
    checks: list[dict[str, Any]] = [
        {
            "name": "trimmed_output_present",
            "passed": trimmed_path is not None and trimmed_path.exists(),
            "actual": display_path(trimmed_path) if trimmed_path and trimmed_path.exists() else "",
        },
        {
            "name": "qc_confirmed_full",
            "passed": str(qc_row.get("qc_status") or "").strip() == "confirmed_full",
            "actual": str(qc_row.get("qc_status") or "").strip(),
        },
        {
            "name": "manual_follow_up_matches",
            "passed": bool_from_text(qc_row.get("manual_follow_up_required") or "") == bool(case.get("expected_manual_review")),
            "actual": bool_from_text(qc_row.get("manual_follow_up_required") or ""),
        },
    ]

    expected_start = str(case.get("expected_start_first_line") or "").strip()
    if expected_start:
        actual_start = trimmed_lines[0] if trimmed_lines else ""
        checks.append(
            {
                "name": "start_line_matches",
                "passed": start_anchor_matches(trimmed_text, trimmed_lines, expected_start),
                "actual": actual_start,
            }
        )

    expected_end = str(case.get("expected_end_contains") or "").strip()
    if expected_end:
        checks.append(
            {
                "name": "expected_end_present",
                "passed": any(
                    contains_approximate_text(trimmed_text, variant) for variant in expected_end_variants(expected_end)
                ),
                "actual": expected_end if flattened_text else "",
            }
        )

    for forbidden in case.get("expected_not_contains") or []:
        forbidden_text = str(forbidden or "").strip()
        if not forbidden_text:
            continue
        checks.append(
            {
                "name": f"not_contains::{forbidden_text[:40]}",
                "passed": not contains_normalised_text(trimmed_text, forbidden_text),
                "actual": forbidden_text,
            }
        )
    return checks


def evaluate_case(
    case: dict[str, Any],
    payload: dict[str, Any],
    bundles: dict[str, ReportBundle],
    heuristic_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    paper_id = str(case.get("paper_id") or "").strip()
    resolved = resolve_source_row(
        paper_id=paper_id,
        heuristic_row=heuristic_rows.get(paper_id, {}),
        manual_row=manual_rows.get(paper_id, {}),
    )
    resolved_source_category = str(resolved.get("resolved_source_category") or "").strip()
    workflow_stage = resolve_workflow_stage(case, resolved_source_category)
    bundle = pick_report_bundle(paper_id, payload, workflow_stage, bundles)
    trim_row = bundle.trim_rows.get(paper_id, {}) if bundle else {}
    qc_row = bundle.qc_rows.get(paper_id, {}) if bundle else {}

    if workflow_stage == "routing_gate":
        checks = evaluate_routing_gate(resolved_source_category)
    elif bool(case.get("expected_manual_review")):
        checks = evaluate_not_needed(trim_row, qc_row, bool(case.get("expected_manual_review")))
    else:
        checks = evaluate_trimmed_case(case, trim_row, qc_row, bundle)

    return {
        "paper_id": paper_id,
        "regression_set_id": feedback_id(payload, Path()),
        "workflow_stage": workflow_stage,
        "output_source": bundle.name if bundle else "",
        "passed": all(bool(check.get("passed")) for check in checks),
        "checks": checks,
    }


def evaluate_feedback_files(
    feedback_paths: list[Path],
    reports_dir: Path,
    source_registry_path: Path,
    source_manual_review_path: Path,
) -> dict[str, Any]:
    bundles = discover_report_bundles(reports_dir)
    heuristic_rows = load_csv_rows_by_id(source_registry_path, "paper_id")
    manual_rows = load_csv_rows_by_id(source_manual_review_path, "paper_id")
    results: list[dict[str, Any]] = []
    for feedback_path in feedback_paths:
        payload = load_feedback_payload(feedback_path)
        payload_id = feedback_id(payload, feedback_path)
        for case in payload.get("cases") or []:
            result = evaluate_case(case, payload, bundles, heuristic_rows, manual_rows)
            result["regression_set_id"] = payload_id
            results.append(result)
    return {
        "generated_at_utc": now_utc_iso(),
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "results": results,
    }


def main() -> None:
    args = parse_args()
    feedback_paths = [Path(raw_path) for raw_path in args.feedback_path]
    report = evaluate_feedback_files(
        feedback_paths=feedback_paths,
        reports_dir=args.reports_dir,
        source_registry_path=args.source_registry_path,
        source_manual_review_path=args.source_manual_review_path,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
