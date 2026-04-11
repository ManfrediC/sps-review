from __future__ import annotations

"""Frozen stage-05 benchmark.

Do not let the autoresearch loop modify this file, its scoring rules,
or its strict text normalisation. Otherwise the agent will optimise the
metric instead of the extraction.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.autoresearch.stage_05 import gold
from src.pipelines._proceedings_text import normalize_text
from src.pipelines._source_routing import load_csv_rows_by_id, resolve_source_row
from src.validation.evaluate_trimming_feedback import (
    REPORTS_DIR,
    ReportBundle,
    collapse_alnum,
    contains_normalised_text,
    discover_report_bundles,
    expected_end_variants,
    feedback_batch_id,
    feedback_id,
    load_feedback_payload,
    pick_report_bundle,
    resolve_workflow_stage,
    rows_by_id,
    start_anchor_matches,
    trimmed_output_path,
    trimmed_text_payload,
)


REPO_ROOT = gold.REPO_ROOT
TRIMMING_QA_DIR = gold.TRIMMING_QA_DIR
AUTORESEARCH_ROOT = gold.GOLD_STANDARD_DIR / "autoresearch"
REGRESSION_DIR = TRIMMING_QA_DIR / "regression"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
TRIMMER_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05_trim_proceedings_text_autoresearch.py"
QC_SCRIPT = REPO_ROOT / "src" / "pipelines" / "05b_validate_proceedings_text_autoresearch.py"
LABELS = ("missing_output", "spillover", "truncated", "exact_match", "wrong_abstract")


@dataclass(frozen=True)
class RegressionCase:
    paper_id: str
    regression_set_id: str
    batch_id: str
    workflow_stage: str
    case_payload: dict[str, Any]
    baseline_bundle_name: str
    baseline_trimmed_path: Path
    baseline_source_kind: str = "historical_report"


def now_utc_iso() -> str:
    return gold.now_utc_iso()


def strict_normalise_text(text: str) -> str:
    # Keep this strict and minimal: newline normalisation, whitespace collapse,
    # and optional soft-hyphen removal only.
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
    return " ".join(normalized.split()).strip()


def overlap_score(expected_text: str, actual_text: str) -> float:
    expected_norm = strict_normalise_text(expected_text)
    actual_norm = strict_normalise_text(actual_text)
    if not expected_norm or not actual_norm:
        return 0.0
    return SequenceMatcher(None, expected_norm, actual_norm).ratio()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bool_from_text(value: str) -> bool:
    return str(value or "").strip().lower() == "true"


def parse_int(value: Any, default: int = 10**9) -> int:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else default


def trim_command(paper_ids: list[str], trimmed_dir: Path, trim_registry_path: Path) -> list[str]:
    return [
        sys.executable,
        str(TRIMMER_SCRIPT),
        *[argument for paper_id in paper_ids for argument in ("--paper-id", paper_id)],
        "--all-papers",
        "--include-already-trimmed",
        "--output-dir",
        str(trimmed_dir),
        "--registry-path",
        str(trim_registry_path),
        "--skip-registry-refresh",
    ]


def qc_command(paper_ids: list[str], trimmed_dir: Path, trim_registry_path: Path, qc_registry_path: Path) -> list[str]:
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


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=str(REPO_ROOT))


def ensure_bundle(report_dir: Path) -> ReportBundle:
    return ReportBundle(
        name=report_dir.name,
        report_dir=report_dir,
        trim_rows=rows_by_id(report_dir / "text_trim_registry.csv"),
        qc_rows=rows_by_id(report_dir / "proceedings_text_qc_registry.csv"),
    )


def qc_indicates_spillover(qc_row: dict[str, str]) -> bool:
    return str(qc_row.get("qc_status") or "").strip() == "spillover_detected" or bool_from_text(
        qc_row.get("spillover_flag") or ""
    )


def qc_indicates_truncation(qc_row: dict[str, str]) -> bool:
    if str(qc_row.get("qc_status") or "").strip() == "partial_truncated":
        return True
    return parse_int(qc_row.get("meaningful_tail_gap_count"), default=0) > 0


def text_clearly_spills_over(gold_text: str, candidate_text: str) -> bool:
    gold_norm = strict_normalise_text(gold_text)
    candidate_norm = strict_normalise_text(candidate_text)
    if not gold_norm or not candidate_norm or candidate_norm == gold_norm:
        return False
    return candidate_norm.startswith(gold_norm) and len(candidate_norm) > len(gold_norm)


def text_clearly_truncated(gold_text: str, candidate_text: str) -> bool:
    gold_norm = strict_normalise_text(gold_text)
    candidate_norm = strict_normalise_text(candidate_text)
    if not gold_norm or not candidate_norm or candidate_norm == gold_norm:
        return False
    return gold_norm.startswith(candidate_norm) and len(gold_norm) > len(candidate_norm)


def classify_gold_result(
    *,
    gold_text: str,
    candidate_text: str,
    qc_row: dict[str, str],
    candidate_present: bool,
) -> str:
    # Fixed label precedence. Keep in sync with program.md and tests.
    if not candidate_present or not strict_normalise_text(candidate_text):
        return "missing_output"
    if qc_indicates_spillover(qc_row) or text_clearly_spills_over(gold_text, candidate_text):
        return "spillover"
    if qc_indicates_truncation(qc_row) or text_clearly_truncated(gold_text, candidate_text):
        return "truncated"
    if strict_normalise_text(candidate_text) == strict_normalise_text(gold_text):
        return "exact_match"
    return "wrong_abstract"


def compare_gold_result(
    *,
    paper_id: str,
    gold_path: Path,
    candidate_path: Path | None,
    qc_row: dict[str, str],
) -> dict[str, Any]:
    gold_text, gold_lines = gold.trimmed_text_payload(gold_path)
    candidate_present = candidate_path is not None and candidate_path.exists()
    candidate_text, candidate_lines = gold.trimmed_text_payload(candidate_path) if candidate_present else ("", [])
    label = classify_gold_result(
        gold_text=gold_text,
        candidate_text=candidate_text,
        qc_row=qc_row,
        candidate_present=candidate_present,
    )
    return {
        "paper_id": paper_id,
        "label": label,
        "gold_json_path": gold.display_path(gold_path),
        "candidate_json_path": gold.display_path(candidate_path) if candidate_present else "",
        "qc_status": str(qc_row.get("qc_status") or "").strip(),
        "manual_follow_up_required": str(qc_row.get("manual_follow_up_required") or "").strip(),
        "overlap_score": round(overlap_score(gold_text, candidate_text), 6),
        "normalised_text_equal": strict_normalise_text(gold_text) == strict_normalise_text(candidate_text),
        "spillover_detected": qc_indicates_spillover(qc_row) or text_clearly_spills_over(gold_text, candidate_text),
        "truncated_detected": qc_indicates_truncation(qc_row) or text_clearly_truncated(gold_text, candidate_text),
        "gold_first_line": gold_lines[0] if gold_lines else "",
        "gold_last_line": gold_lines[-1] if gold_lines else "",
        "candidate_first_line": candidate_lines[0] if candidate_lines else "",
        "candidate_last_line": candidate_lines[-1] if candidate_lines else "",
    }


def summary_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for result in results if result["label"] == label) for label in LABELS}


def run_gold_benchmark(
    *,
    output_dir: Path,
    manifest_path: Path = gold.MANIFEST_PATH,
    paper_ids: list[str] | None = None,
    include_regression: bool = False,
    regression_dir: Path = REGRESSION_DIR,
    reports_dir: Path = REPORTS_DIR,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
) -> dict[str, Any]:
    entries = gold.active_entries_by_id(manifest_path)
    requested_ids = {paper_id.strip() for paper_id in (paper_ids or []) if paper_id.strip()}
    active_entries = [
        entry
        for paper_id, entry in sorted(entries.items(), key=lambda item: parse_int(item[0]))
        if not requested_ids or paper_id in requested_ids
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    trimmed_dir = output_dir / "text_trimmed"
    trimmed_dir.mkdir(parents=True, exist_ok=True)
    trim_registry_path = output_dir / "text_trim_registry.csv"
    qc_registry_path = output_dir / "proceedings_text_qc_registry.csv"
    if active_entries:
        paper_id_list = [str(entry.get("paper_id") or "").strip() for entry in active_entries]
        run_command(trim_command(paper_id_list, trimmed_dir, trim_registry_path))
        run_command(qc_command(paper_id_list, trimmed_dir, trim_registry_path, qc_registry_path))

    bundle = ensure_bundle(output_dir)
    results = [
        compare_gold_result(
            paper_id=str(entry.get("paper_id") or "").strip(),
            gold_path=gold.resolve_repo_path(str(entry.get("gold_json_path") or "").strip()),
            candidate_path=trimmed_output_path(bundle.trim_rows.get(str(entry.get("paper_id") or "").strip(), {}), bundle, str(entry.get("paper_id") or "").strip()),
            qc_row=bundle.qc_rows.get(str(entry.get("paper_id") or "").strip(), {}),
        )
        for entry in active_entries
    ]
    counts = summary_counts(results)
    case_count = len(results)
    regression_failed_count = 0
    regression_summary_path = ""
    if include_regression:
        regression_summary = run_regression_benchmark(
            output_dir=output_dir / "regression_guard",
            regression_dir=regression_dir,
            reports_dir=reports_dir,
            source_registry_path=source_registry_path,
            source_manual_review_path=source_manual_review_path,
        )
        regression_failed_count = int(regression_summary.get("failed_count") or 0)
        regression_summary_path = gold.display_path((output_dir / "regression_guard" / "summary.json"))

    summary = {
        "generated_at_utc": now_utc_iso(),
        "mode": "gold",
        "case_count": case_count,
        "exact_match_rate": round((counts["exact_match"] / case_count), 6) if case_count else 0.0,
        "mean_overlap_score": round(
            (sum(float(result["overlap_score"]) for result in results) / case_count), 6
        ) if case_count else 0.0,
        "no_truncation_rate": round(
            (sum(1 for result in results if result["label"] != "truncated") / case_count), 6
        ) if case_count else 0.0,
        "no_spillover_rate": round(
            (sum(1 for result in results if result["label"] != "spillover") / case_count), 6
        ) if case_count else 0.0,
        "regression_failed_count": regression_failed_count,
        "regression_summary_path": regression_summary_path,
        "label_counts": counts,
        "results": results,
    }
    per_paper_dir = output_dir / "per_paper"
    for result in results:
        write_json(per_paper_dir / f"{result['paper_id']}.json", result)
    write_json(output_dir / "summary.json", summary)
    return summary


def historical_first_line(trimmed_lines: list[str]) -> str:
    return trimmed_lines[0] if trimmed_lines else ""


def historical_last_line(trimmed_lines: list[str]) -> str:
    return trimmed_lines[-1] if trimmed_lines else ""


def end_anchor_matches(trimmed_text: str, expected_end: str) -> tuple[bool, str]:
    if not trimmed_text or not expected_end:
        return False, ""
    for variant in expected_end_variants(expected_end):
        haystack_compact = collapse_alnum(trimmed_text)
        variant_compact = collapse_alnum(variant)
        if variant_compact:
            compact_start = haystack_compact.rfind(variant_compact)
            if compact_start >= 0:
                trailing_compact = len(haystack_compact) - (compact_start + len(variant_compact))
                if trailing_compact <= 12:
                    return True, variant
        variant_tokens = normalize_text(variant).split()
        haystack_tokens = normalize_text(trimmed_text).split()
        if not variant_tokens or not haystack_tokens:
            continue
        anchor_text = " ".join(variant_tokens)
        min_window = max(1, len(variant_tokens) - 3)
        max_window = min(len(haystack_tokens), len(variant_tokens) + 6)
        trailing_tolerance = 2
        search_start = max(0, len(haystack_tokens) - len(variant_tokens) - trailing_tolerance - 6)
        for start_index in range(search_start, len(haystack_tokens)):
            for window_size in range(min_window, max_window + 1):
                end_index = start_index + window_size
                if end_index > len(haystack_tokens):
                    break
                trailing_tokens = len(haystack_tokens) - end_index
                if trailing_tokens > trailing_tolerance:
                    continue
                candidate = " ".join(haystack_tokens[start_index:end_index])
                if SequenceMatcher(None, anchor_text, candidate).ratio() >= 0.9:
                    return True, variant
    return False, ""


def text_matches_historical(current_text: str, historical_text: str) -> bool:
    return strict_normalise_text(current_text) == strict_normalise_text(historical_text)


def source_label(explicit_value: str, fallback_label: str = "historical_json") -> str:
    return "feedback" if explicit_value else fallback_label


def failure_location(failed_start: bool, failed_end: bool, failed_other: bool) -> str:
    if failed_start and failed_end:
        return "both"
    if failed_start:
        return "abstract_start"
    if failed_end:
        return "abstract_end"
    if failed_other:
        return "other"
    return ""


def failure_reason(checks: list[dict[str, Any]]) -> str:
    failed = [str(check.get("name") or "").strip() for check in checks if not bool(check.get("passed"))]
    return ", ".join(name for name in failed if name)


def classify_failure(current_checks: list[dict[str, Any]], baseline_checks: list[dict[str, Any]]) -> str:
    failed_names = {
        str(check.get("name") or "").strip()
        for check in current_checks
        if not bool(check.get("passed"))
    }
    baseline_failed_names = {
        str(check.get("name") or "").strip()
        for check in baseline_checks
        if not bool(check.get("passed"))
    }
    if failed_names and failed_names.issubset(baseline_failed_names):
        return "unresolved_historical_problem"
    if not failed_names:
        return "none"
    return "true_regression"


def build_case_checks(
    *,
    case: RegressionCase,
    trim_row: dict[str, str],
    qc_row: dict[str, str],
    output_bundle_name: str,
    trimmed_path: Path | None,
    trimmed_text: str,
    trimmed_lines: list[str],
    historical_text: str,
    historical_lines: list[str],
    fallback_expectation_source: str = "historical_json",
) -> list[dict[str, Any]]:
    explicit_start = str(case.case_payload.get("expected_start_first_line") or "").strip()
    explicit_end = str(case.case_payload.get("expected_end_contains") or "").strip()
    expected_start = explicit_start or historical_first_line(historical_lines)
    expected_end = explicit_end or historical_last_line(historical_lines)
    expected_not_contains = [str(item or "").strip() for item in case.case_payload.get("expected_not_contains") or []]
    full_text_guard_enabled = not explicit_start and not explicit_end and not expected_not_contains

    end_match_passed, matched_end = end_anchor_matches(trimmed_text, expected_end)
    checks: list[dict[str, Any]] = [
        {
            "name": "trimmed_output_present",
            "passed": trimmed_path is not None and trimmed_path.exists(),
            "actual": gold.display_path(trimmed_path) if trimmed_path and trimmed_path.exists() else "",
        },
        {
            "name": "qc_confirmed_full",
            "passed": str(qc_row.get("qc_status") or "").strip() == "confirmed_full",
            "actual": str(qc_row.get("qc_status") or "").strip(),
        },
        {
            "name": "manual_follow_up_false",
            "passed": str(qc_row.get("manual_follow_up_required") or "").strip().lower() == "false",
            "actual": str(qc_row.get("manual_follow_up_required") or "").strip().lower(),
        },
        {
            "name": "start_anchor_matches",
            "passed": start_anchor_matches(trimmed_text, trimmed_lines, expected_start),
            "actual": trimmed_lines[0] if trimmed_lines else "",
            "expected": expected_start,
            "source": source_label(explicit_start, fallback_expectation_source),
        },
        {
            "name": "end_anchor_matches",
            "passed": end_match_passed,
            "actual": matched_end or (historical_last_line(trimmed_lines) if trimmed_lines else ""),
            "expected": expected_end,
            "source": source_label(explicit_end, fallback_expectation_source),
        },
    ]

    for forbidden_text in expected_not_contains:
        if not forbidden_text:
            continue
        checks.append(
            {
                "name": f"not_contains::{forbidden_text[:40]}",
                "passed": not contains_normalised_text(trimmed_text, forbidden_text),
                "actual": forbidden_text,
            }
        )

    if full_text_guard_enabled:
        checks.append(
            {
                "name": "matches_historical_text",
                "passed": text_matches_historical(trimmed_text, historical_text),
                "actual": output_bundle_name,
                "expected": gold.display_path(case.baseline_trimmed_path),
            }
        )
    return checks


def load_regression_cases(
    *,
    regression_dir: Path,
    reports_dir: Path,
    source_registry_path: Path,
    source_manual_review_path: Path,
    manifest_path: Path = gold.MANIFEST_PATH,
) -> list[RegressionCase]:
    bundles = discover_report_bundles(reports_dir)
    heuristic_rows = load_csv_rows_by_id(source_registry_path, "paper_id")
    manual_rows = load_csv_rows_by_id(source_manual_review_path, "paper_id")
    gold_entries = gold.active_entries_by_id(manifest_path)
    cases: list[RegressionCase] = []
    for feedback_path in sorted(regression_dir.glob("*.json")):
        payload = load_feedback_payload(feedback_path)
        payload_id = feedback_id(payload, feedback_path)
        for case_payload in payload.get("cases") or []:
            paper_id = str(case_payload.get("paper_id") or "").strip()
            if not paper_id:
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
            gold_entry = gold_entries.get(paper_id, {})
            gold_path_text = str(gold_entry.get("gold_json_path") or "").strip()
            if gold_path_text:
                baseline_trimmed_path = gold.resolve_repo_path(gold_path_text)
                baseline_bundle_name = "gold_standard"
                baseline_source_kind = "gold_standard"
            else:
                bundle = pick_report_bundle(paper_id, payload, workflow_stage, bundles)
                if bundle is None:
                    raise FileNotFoundError(f"No historical report bundle found for reviewed regression paper {paper_id}.")
                baseline_trimmed_path = trimmed_output_path(bundle.trim_rows.get(paper_id, {}), bundle, paper_id)
                if baseline_trimmed_path is None or not baseline_trimmed_path.exists():
                    raise FileNotFoundError(
                        f"Historical trimmed JSON not found for reviewed regression paper {paper_id} in bundle {bundle.name}."
                    )
                baseline_bundle_name = bundle.name
                baseline_source_kind = "historical_report"
            cases.append(
                RegressionCase(
                    paper_id=paper_id,
                    regression_set_id=payload_id,
                    batch_id=feedback_batch_id(payload),
                    workflow_stage=workflow_stage,
                    case_payload=dict(case_payload),
                    baseline_bundle_name=baseline_bundle_name,
                    baseline_trimmed_path=baseline_trimmed_path,
                    baseline_source_kind=baseline_source_kind,
                )
            )
    return cases


def chunked_cases(cases: list[RegressionCase], tranche_size: int) -> list[list[RegressionCase]]:
    return [cases[index : index + tranche_size] for index in range(0, len(cases), tranche_size)]


def evaluate_regression_case(case: RegressionCase, current_bundle: ReportBundle) -> dict[str, Any]:
    fallback_expectation_source = "gold_json" if case.baseline_source_kind == "gold_standard" else "historical_json"
    if case.baseline_source_kind == "gold_standard":
        baseline_bundle = ReportBundle(
            name=case.baseline_bundle_name,
            report_dir=case.baseline_trimmed_path.parent,
            trim_rows={},
            qc_rows={},
        )
        baseline_trim_row: dict[str, str] = {}
        baseline_qc_row = {"qc_status": "confirmed_full", "manual_follow_up_required": "false"}
    else:
        baseline_bundle = ReportBundle(
            name=case.baseline_bundle_name,
            report_dir=case.baseline_trimmed_path.parents[1],
            trim_rows=rows_by_id(case.baseline_trimmed_path.parents[1] / "text_trim_registry.csv"),
            qc_rows=rows_by_id(case.baseline_trimmed_path.parents[1] / "proceedings_text_qc_registry.csv"),
        )
        baseline_trim_row = baseline_bundle.trim_rows.get(case.paper_id, {})
        baseline_qc_row = baseline_bundle.qc_rows.get(case.paper_id, {})

    historical_text, historical_lines = trimmed_text_payload(case.baseline_trimmed_path)
    current_trim_row = current_bundle.trim_rows.get(case.paper_id, {})
    current_qc_row = current_bundle.qc_rows.get(case.paper_id, {})
    current_trimmed_path = trimmed_output_path(current_trim_row, current_bundle, case.paper_id)
    current_text, current_lines = trimmed_text_payload(current_trimmed_path)

    baseline_checks = build_case_checks(
        case=case,
        trim_row=baseline_trim_row,
        qc_row=baseline_qc_row,
        output_bundle_name=baseline_bundle.name,
        trimmed_path=case.baseline_trimmed_path,
        trimmed_text=historical_text,
        trimmed_lines=historical_lines,
        historical_text=historical_text,
        historical_lines=historical_lines,
        fallback_expectation_source=fallback_expectation_source,
    )
    current_checks = build_case_checks(
        case=case,
        trim_row=current_trim_row,
        qc_row=current_qc_row,
        output_bundle_name=current_bundle.name,
        trimmed_path=current_trimmed_path,
        trimmed_text=current_text,
        trimmed_lines=current_lines,
        historical_text=historical_text,
        historical_lines=historical_lines,
        fallback_expectation_source=fallback_expectation_source,
    )

    failed_names = {str(check.get("name") or "").strip() for check in current_checks if not bool(check.get("passed"))}
    result_passed = not failed_names
    failed_start = "start_anchor_matches" in failed_names
    failed_end = "end_anchor_matches" in failed_names or any(name.startswith("not_contains::") for name in failed_names)
    failed_other = bool(failed_names - {"start_anchor_matches", "end_anchor_matches"}) and not failed_end

    return {
        "paper_id": case.paper_id,
        "regression_set_id": case.regression_set_id,
        "baseline_bundle": case.baseline_bundle_name,
        "current_bundle": current_bundle.name,
        "baseline_trimmed_path": gold.display_path(case.baseline_trimmed_path),
        "current_trimmed_path": gold.display_path(current_trimmed_path) if current_trimmed_path else "",
        "baseline_source_kind": case.baseline_source_kind,
        "start_expectation_source": source_label(
            str(case.case_payload.get("expected_start_first_line") or "").strip(),
            fallback_expectation_source,
        ),
        "end_expectation_source": source_label(
            str(case.case_payload.get("expected_end_contains") or "").strip(),
            fallback_expectation_source,
        ),
        "passed": result_passed,
        "failure_reason": "" if result_passed else failure_reason(current_checks),
        "failure_location": "" if result_passed else failure_location(failed_start, failed_end, failed_other),
        "issue_classification": classify_failure(current_checks, baseline_checks),
        "checks": current_checks,
        "baseline_checks": baseline_checks,
    }


def run_regression_benchmark(
    *,
    output_dir: Path,
    regression_dir: Path = REGRESSION_DIR,
    reports_dir: Path = REPORTS_DIR,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    source_manual_review_path: Path = SOURCE_MANUAL_REVIEW_PATH,
    manifest_path: Path = gold.MANIFEST_PATH,
) -> dict[str, Any]:
    cases = load_regression_cases(
        regression_dir=regression_dir,
        reports_dir=reports_dir,
        source_registry_path=source_registry_path,
        source_manual_review_path=source_manual_review_path,
        manifest_path=manifest_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    trimmed_dir = output_dir / "text_trimmed"
    trimmed_dir.mkdir(parents=True, exist_ok=True)
    trim_registry_path = output_dir / "text_trim_registry.csv"
    qc_registry_path = output_dir / "proceedings_text_qc_registry.csv"
    paper_ids = [case.paper_id for case in cases]
    if paper_ids:
        run_command(trim_command(paper_ids, trimmed_dir, trim_registry_path))
        run_command(qc_command(paper_ids, trimmed_dir, trim_registry_path, qc_registry_path))

    current_bundle = ensure_bundle(output_dir)
    results = [evaluate_regression_case(case, current_bundle) for case in cases]
    summary = {
        "generated_at_utc": now_utc_iso(),
        "mode": "regression",
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "paper_ids": paper_ids,
        "results": results,
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen benchmark for stage-05 autoresearch outputs.")
    parser.add_argument("--mode", choices=("gold", "regression"), required=True, help="Benchmark mode.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=AUTORESEARCH_ROOT / "manual_run",
        help="Output directory for non-canonical benchmark artefacts.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict gold mode to one or more paper IDs.",
    )
    parser.add_argument(
        "--include-regression",
        action="store_true",
        help="When running gold mode, also run the regression guard and include its failed-count diagnostic.",
    )
    parser.add_argument("--manifest-path", type=Path, default=gold.MANIFEST_PATH, help="Gold manifest path.")
    parser.add_argument("--regression-dir", type=Path, default=REGRESSION_DIR, help="Regression fixtures directory.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Historical report bundles directory.")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "gold":
        summary = run_gold_benchmark(
            output_dir=args.output_dir,
            manifest_path=args.manifest_path,
            paper_ids=args.paper_id,
            include_regression=args.include_regression,
            regression_dir=args.regression_dir,
            reports_dir=args.reports_dir,
            source_registry_path=args.source_registry_path,
            source_manual_review_path=args.source_manual_review_path,
        )
    else:
        summary = run_regression_benchmark(
            output_dir=args.output_dir,
            regression_dir=args.regression_dir,
            reports_dir=args.reports_dir,
            source_registry_path=args.source_registry_path,
            source_manual_review_path=args.source_manual_review_path,
            manifest_path=args.manifest_path,
        )
    print(f"Mode: {summary['mode']}")
    print(f"Summary: {gold.display_path(args.output_dir / 'summary.json')}")


if __name__ == "__main__":
    main()
