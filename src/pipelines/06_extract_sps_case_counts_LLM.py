from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._proceedings_ready import (
    TEXT_PROCEEDINGS_READY_DIR,
    TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
    load_ready_rows_by_id,
    preferred_proceedings_text_path,
)
from src.pipelines._sps_case_count_registry import (
    HEURISTIC_VERSION,
    build_case_count_candidate_package,
    count_row_from_resolution,
    count_row_fieldnames,
    relative_to_repo,
)
from src.pipelines.stage06_counting.classify import DEFAULT_MODEL as DEFAULT_GPT_MODEL
from src.pipelines.stage06_counting.controller import adjudicated_count_row
from src.pipelines.stage06_counting.local_ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    ensure_ollama_model_available,
    run_local_count_package,
)
from src.pipelines.stage06_counting.local_prepare import format_candidate_package_for_local_llm
from src.pipelines.stage06_counting.local_validate import validate_local_count_decision


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
RUN_ROOT = REPO_ROOT / "results" / "stage06_count_llm_runs"
QA_OUTPUT_DIR = REPO_ROOT / "qa" / "validation" / "stage06_llm"

LOCAL_EXTRA_FIELDNAMES = [
    "local_model_name",
    "local_model_status",
    "local_model_duration_seconds",
    "local_model_error",
    "local_n_spsd_patients",
    "local_confidence",
    "local_needs_review",
    "local_data_granularity",
    "local_evidence_span",
    "local_reasoning_short",
    "local_possibility_count",
    "local_validation_flags",
    "local_result_json_path",
    "gpt_ran",
    "local_vs_gpt_status",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("stage06_count_llm_%Y%m%dT%H%M%SZ")


def default_output_path(run_id: str) -> Path:
    return QA_OUTPUT_DIR / f"{run_id}.csv"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = (row.get("Covidence") or "").strip()
        if key:
            rows[key] = row
    return rows


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


def load_text_record(path: Path) -> dict[str, object]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def collect_text_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [*count_row_fieldnames(), *LOCAL_EXTRA_FIELDNAMES]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _estimate_summary(packages: list[tuple[Path, object, object, object]]) -> None:
    total = len(packages)
    count_eligible = sum(1 for _, package, _, _ in packages if package.count_eligible)
    llm_recommended = sum(1 for _, package, _, _ in packages if package.llm_routing_recommended)
    print(f"Stage 06 LLM calibration estimate at {now_utc_iso()}")
    print(f"Selected papers: {total}")
    print(f"Count-eligible papers: {count_eligible}")
    print(f"Heuristic packages recommending GPT adjudication: {llm_recommended}")
    print(f"Local model calls planned: {total}")
    print(f"GPT calls planned: {total}")


def _local_status(call_status: str, flags: list[str]) -> str:
    if call_status != "parsed_ok":
        return call_status
    if flags:
        return "parsed_with_flags"
    return "parsed_ok"


def local_decision_count_row(
    package: object,
    *,
    local_model_status: str,
    local_model_error: str,
    local_flags: list[str],
    local_parsed: object | None,
    candidate_json_path: str,
    count_version: str,
) -> dict[str, str]:
    if local_parsed is None:
        fallback_candidate = package.fallback_candidate()
        reasons = [f"local_model_status={local_model_status}"]
        if local_model_error:
            reasons.append(f"local_model_error={local_model_error}")
        if local_flags:
            reasons.append(f"local_validation_flags={'; '.join(local_flags)}")
        return count_row_from_resolution(
            package=package,
            final_count=fallback_candidate.proposed_count,
            final_confidence=fallback_candidate.count_confidence,
            final_basis=fallback_candidate.count_basis,
            final_manual_review_required=True,
            final_reason=" | ".join(reasons),
            count_version=count_version,
            count_verification_status="local_model_invalid_manual_review_required",
            count_candidate_json_path=candidate_json_path,
            heuristic_fallback_used=True,
            count_validator_flags=local_flags,
            count_audit_status="local_only",
        )

    matching_candidate = next(
        (candidate for candidate in package.candidates if candidate.proposed_count == local_parsed.n_spsd_patients),
        None,
    )
    final_basis = "local_llm_direct_count"
    if matching_candidate is not None:
        final_basis = matching_candidate.count_basis
    elif local_flags:
        final_basis = "local_llm_non_candidate_count"

    reasons = [
        f"local_model_status={local_model_status}",
        f"local_confidence={local_parsed.confidence}",
        local_parsed.reasoning_short,
    ]
    if local_flags:
        reasons.append(f"local_validation_flags={'; '.join(local_flags)}")
    return count_row_from_resolution(
        package=package,
        final_count=local_parsed.n_spsd_patients,
        final_confidence=local_parsed.confidence,
        final_basis=final_basis,
        final_manual_review_required=local_parsed.needs_review or bool(local_flags),
        final_reason=" | ".join(reason for reason in reasons if reason),
        count_version=count_version,
        count_verification_status="local_model_only",
        count_candidate_json_path=candidate_json_path,
        count_validator_flags=local_flags,
        count_audit_status="local_only",
    )


def build_local_adviser_notes(
    *,
    local_model_name: str,
    local_model_status: str,
    local_model_error: str,
    local_flags: list[str],
    parsed_output: object | None,
) -> str:
    lines = [
        f"- local_model_name: {local_model_name}",
        f"- local_model_status: {local_model_status}",
    ]
    if local_model_error:
        lines.append(f"- local_model_error: {local_model_error}")
    if local_flags:
        lines.append(f"- local_validation_flags: {'; '.join(local_flags)}")
    if parsed_output is None:
        lines.append("- local_model_summary: unavailable")
        return "\n".join(lines)

    lines.extend(
        [
            f"- local_n_spsd_patients: {parsed_output.n_spsd_patients}",
            f"- local_confidence: {parsed_output.confidence}",
            f"- local_needs_review: {parsed_output.needs_review}",
            f"- local_data_granularity: {parsed_output.data_granularity}",
            f"- local_evidence_span: {parsed_output.evidence_span}",
            f"- local_reasoning_short: {parsed_output.reasoning_short}",
            f"- local_possibility_count: {len(parsed_output.possibilities)}",
        ]
    )
    for index, possibility in enumerate(parsed_output.possibilities, start=1):
        lines.append(
            "- local_possibility_"
            f"{index}: count={possibility.n_spsd_patients}; confidence={possibility.confidence}; "
            f"granularity={possibility.data_granularity}; evidence={possibility.evidence_span}"
        )
    return "\n".join(lines)


def compare_local_to_final_row(local_parsed: object | None, final_row: dict[str, str], local_model_status: str) -> str:
    if local_parsed is None:
        return local_model_status

    final_count = int((final_row.get("likely_sps_case_count") or "0").strip() or 0)
    final_review = (final_row.get("count_manual_review_required") or "").strip().lower() == "true"
    if local_parsed.n_spsd_patients == final_count and local_parsed.needs_review == final_review:
        return "agree"
    if local_parsed.n_spsd_patients == final_count and local_parsed.needs_review and not final_review:
        return "local_more_conservative_same_count"
    if local_parsed.n_spsd_patients == final_count and not local_parsed.needs_review and final_review:
        return "gpt_more_conservative_same_count"
    if local_parsed.n_spsd_patients != final_count and local_parsed.needs_review == final_review:
        return "count_conflict_same_review"
    if local_parsed.n_spsd_patients != final_count and local_parsed.needs_review:
        return "count_conflict_local_more_conservative"
    return "count_conflict_gpt_more_conservative"


def augment_calibration_row(
    final_row: dict[str, str],
    *,
    gpt_ran: bool,
    local_model_name: str,
    local_model_status: str,
    local_duration_seconds: float,
    local_model_error: str,
    local_flags: list[str],
    local_result_json_path: str,
    local_parsed: object | None,
) -> dict[str, str]:
    augmented = dict(final_row)
    augmented.update(
        {
            "local_model_name": local_model_name,
            "local_model_status": local_model_status,
            "local_model_duration_seconds": f"{local_duration_seconds:.3f}",
            "local_model_error": local_model_error,
            "local_n_spsd_patients": "" if local_parsed is None else str(local_parsed.n_spsd_patients),
            "local_confidence": "" if local_parsed is None else local_parsed.confidence,
            "local_needs_review": "" if local_parsed is None else str(local_parsed.needs_review).lower(),
            "local_data_granularity": "" if local_parsed is None else local_parsed.data_granularity,
            "local_evidence_span": "" if local_parsed is None else local_parsed.evidence_span,
            "local_reasoning_short": "" if local_parsed is None else local_parsed.reasoning_short,
            "local_possibility_count": "0" if local_parsed is None else str(len(local_parsed.possibilities)),
            "local_validation_flags": "; ".join(local_flags),
            "local_result_json_path": local_result_json_path,
            "gpt_ran": str(gpt_ran).lower(),
            "local_vs_gpt_status": (
                compare_local_to_final_row(local_parsed, final_row, local_model_status)
                if gpt_ran
                else "not_run"
            ),
        }
    )
    return augmented


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QA-only stage-06 calibration runner using Gemma locally and GPT-5.4 on every row."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--source-registry-path", type=Path, default=SOURCE_REGISTRY_PATH)
    parser.add_argument("--run-root", type=Path, default=RUN_ROOT)
    parser.add_argument("--run-id", type=str, default="", help="Optional run ID for artefact output.")
    parser.add_argument("--output-path", type=Path, default=None, help="QA CSV output path. Defaults under qa/validation/stage06_llm/.")
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to process.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of papers to process.")
    parser.add_argument("--estimate-only", action="store_true", help="Estimate the run without local or paid model calls.")
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Required before any GPT-5.4 calibration call is made.",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Run only the local Gemma adviser and write a comparable QA CSV without any GPT calls.",
    )
    parser.add_argument("--local-model", default=DEFAULT_OLLAMA_MODEL, help="Ollama model for the local first pass.")
    parser.add_argument("--local-base-url", default=DEFAULT_OLLAMA_BASE_URL, help="Base URL for the local Ollama server.")
    parser.add_argument(
        "--local-timeout-seconds",
        type=float,
        default=DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        help="Timeout in seconds for each local-model request.",
    )
    parser.add_argument("--gpt-model", default=DEFAULT_GPT_MODEL, help="OpenAI model for the calibration adjudicator.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or default_run_id()
    output_path = args.output_path or default_output_path(run_id)

    reference_rows = load_reference_rows(args.references_csv)
    source_rows = load_csv_rows_by_id(args.source_registry_path, "paper_id")
    ready_rows = load_ready_rows_by_id(TEXT_PROCEEDINGS_READY_REGISTRY_PATH)

    packages: list[tuple[Path, object, object, object]] = []
    for text_path in collect_text_paths(args.input_dir, args.paper_id, args.limit):
        preferred_path = preferred_proceedings_text_path(
            text_path,
            ready_dir=TEXT_PROCEEDINGS_READY_DIR,
            fallback_trimmed_dir=args.trimmed_dir,
        )
        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)
        package = build_case_count_candidate_package(
            reference_row=reference_rows.get(text_path.stem, {}),
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            source_row=source_rows.get(text_path.stem, {}),
            ready_rows=ready_rows,
            heuristic_version=HEURISTIC_VERSION,
        )
        packages.append((text_path, package, text_record, preferred_record))

    if args.estimate_only:
        _estimate_summary(packages)
        return

    if packages and not args.allow_paid_run and not args.local_only:
        raise SystemExit(
            "Refusing to start a paid GPT calibration run without --allow-paid-run. "
            "Re-run with --estimate-only first if you want to inspect the selection."
        )

    ensure_ollama_model_available(model=args.local_model, base_url=args.local_base_url)

    run_dir = args.run_root / run_id
    if run_dir.exists():
        raise SystemExit(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "created_at_utc": now_utc_iso(),
            "local_model": args.local_model,
            "local_base_url": args.local_base_url,
            "gpt_model": args.gpt_model,
            "local_only": args.local_only,
            "output_path": str(output_path),
            "paper_ids": [path.stem for path, _, _, _ in packages],
        },
    )

    rows: list[dict[str, str]] = []
    local_status_counts: Counter[str] = Counter()
    compare_counts: Counter[str] = Counter()
    verification_counts: Counter[str] = Counter()

    for text_path, package, _, _ in packages:
        candidate_path = run_dir / "candidate_packages" / f"{package.paper_id}.json"
        _write_json(candidate_path, package.to_dict())
        candidate_json_path = relative_to_repo(candidate_path)

        local_call = run_local_count_package(
            package,
            model=args.local_model,
            base_url=args.local_base_url,
            timeout_seconds=args.local_timeout_seconds,
        )
        local_flags = [] if local_call.parsed is None else validate_local_count_decision(package, local_call.parsed)
        local_model_status = _local_status(local_call.status, local_flags)
        local_prompt_text = format_candidate_package_for_local_llm(package)
        local_result_path = run_dir / "local_model_results" / f"{package.paper_id}.json"
        _write_json(
            local_result_path,
            {
                "paper_id": package.paper_id,
                "model_id": local_call.model_id,
                "status": local_model_status,
                "duration_seconds": round(local_call.duration_seconds, 3),
                "error": local_call.error,
                "validation_flags": local_flags,
                "prompt_text": local_prompt_text,
                "parsed_output": None if local_call.parsed is None else local_call.parsed.model_dump(),
                "raw_output": local_call.raw_output,
                "response_payload": local_call.response_payload,
            },
        )

        adviser_notes = build_local_adviser_notes(
            local_model_name=local_call.model_id,
            local_model_status=local_model_status,
            local_model_error=local_call.error,
            local_flags=local_flags,
            parsed_output=local_call.parsed,
        )
        if args.local_only:
            final_row = local_decision_count_row(
                package,
                local_model_status=local_model_status,
                local_model_error=local_call.error,
                local_flags=local_flags,
                local_parsed=local_call.parsed,
                candidate_json_path=candidate_json_path,
                count_version=f"llm_local_only_v1_{args.local_model}",
            )
        else:
            final_row = adjudicated_count_row(
                package,
                model=args.gpt_model,
                run_dir=run_dir,
                count_version=f"llm_calibration_v1_{args.gpt_model}",
                candidate_json_path=candidate_json_path,
                adviser_notes=adviser_notes,
            )
        augmented_row = augment_calibration_row(
            final_row,
            gpt_ran=not args.local_only,
            local_model_name=local_call.model_id,
            local_model_status=local_model_status,
            local_duration_seconds=local_call.duration_seconds,
            local_model_error=local_call.error,
            local_flags=local_flags,
            local_result_json_path=relative_to_repo(local_result_path),
            local_parsed=local_call.parsed,
        )
        rows.append(augmented_row)
        local_status_counts[local_model_status] += 1
        compare_counts[augmented_row["local_vs_gpt_status"]] += 1
        verification_counts[augmented_row["count_verification_status"]] += 1

        _write_json(
            run_dir / "results" / f"{package.paper_id}.json",
            {
                "paper_id": package.paper_id,
                "count_row": augmented_row,
                "source_text_json_path": relative_to_repo(text_path),
                "preferred_text_json_path": package.preferred_text_json_path,
            },
        )

    _write_rows(rows, output_path)
    _write_json(
        run_dir / "summary.json",
        {
            "run_id": run_id,
            "completed_at_utc": now_utc_iso(),
            "output_path": str(output_path),
            "row_count": len(rows),
            "local_status_counts": dict(local_status_counts),
            "local_vs_gpt_status_counts": dict(compare_counts),
            "count_verification_status_counts": dict(verification_counts),
        },
    )
    print(f"Wrote {len(rows)} calibration rows to {output_path}")
    print(f"Local status counts: {dict(local_status_counts)}")
    print(f"Local vs GPT status counts: {dict(compare_counts)}")
    print(f"Verification status counts: {dict(verification_counts)}")


if __name__ == "__main__":
    main()
