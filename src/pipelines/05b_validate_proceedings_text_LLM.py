from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm

from _proceedings_text import flatten_lines
from _proceedings_trim_core import (
    REFERENCES_CSV,
    REPO_ROOT,
    TRIM_OVERRIDE_PATH,
    apply_trim_override,
    build_trimmed_record,
    candidate_quality_status,
    load_reference_rows,
    load_text_record,
    load_trim_override_rows,
    refresh_artifact_registry,
    sort_registry_rows,
)
from _proceedings_trim_llm import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_PROMPT_VERSION,
    LLMDecision,
    apply_llm_decision,
    call_llm_for_end_decision,
    final_registry_fieldnames,
    final_registry_row,
    heuristic_fallback_candidate,
    load_candidate_package,
    source_path_from_package,
    validate_llm_decision,
)
from _source_routing import load_csv_rows_by_id


CANDIDATE_INPUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed_llm_candidates"
FINAL_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed_llm"
FINAL_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_llm_registry.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate proceedings trim candidates with an OpenAI model and write final trimmed outputs."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--candidate-input-dir", type=Path, default=CANDIDATE_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=FINAL_OUT_DIR)
    parser.add_argument("--registry-path", type=Path, default=FINAL_REGISTRY_PATH)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument("--openai-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--openai-max-retries", type=int, default=2)
    parser.add_argument("--llm-mode", choices=("all", "recommended_only"), default="all")
    parser.add_argument("--prompt-version", default=DEFAULT_PROMPT_VERSION)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-registry-refresh", action="store_true")
    return parser.parse_args()


def _write_registry(rows: list[dict[str, str]], path: Path, preserve_existing: bool = False) -> None:
    fieldnames = final_registry_fieldnames()
    rows_to_write = sort_registry_rows(rows)
    if preserve_existing and path.exists():
        existing_rows = list(load_csv_rows_by_id(path, "paper_id").values())
        merged = {str(row.get("paper_id") or "").strip(): row for row in existing_rows if str(row.get("paper_id") or "").strip()}
        for row in rows_to_write:
            paper_id = str(row.get("paper_id") or "").strip()
            if paper_id:
                merged[paper_id] = row
        rows_to_write = sort_registry_rows(list(merged.values()))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)


def _candidate_package_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    paths = sorted(input_dir.glob("*.json"))
    if wanted:
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


def _empty_registry_row(
    *,
    paper_id: str,
    covidence_id: str,
    title: str,
    authors: str,
    source_filename: str,
    source_path: Path,
    candidate_path: Path,
    trim_status: str,
    trim_reason: str,
    llm_validation_reason: str,
) -> dict[str, str]:
    row = {field: "" for field in final_registry_fieldnames()}
    row.update(
        {
            "paper_id": paper_id,
            "covidence_id": covidence_id,
            "title": title,
            "authors": authors,
            "source_filename": source_filename,
            "source_text_json_path": str(source_path.relative_to(REPO_ROOT)) if source_path.is_relative_to(REPO_ROOT) else str(source_path),
            "candidate_source_json_path": str(candidate_path.relative_to(REPO_ROOT)) if candidate_path.is_relative_to(REPO_ROOT) else str(candidate_path),
            "trim_workflow_version": "proceedings_llm_v1",
            "trim_workflow_stage": "llm_validated",
            "trim_status": trim_status,
            "trim_reason": trim_reason,
            "llm_validation_passed": "false",
            "llm_validation_reason": llm_validation_reason,
        }
    )
    return row


def _prepare_openai_client(args: argparse.Namespace) -> OpenAI | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or args.dry_run:
        return None
    return OpenAI(
        api_key=api_key,
        timeout=args.openai_timeout_seconds,
        max_retries=args.openai_max_retries,
    )


def process_candidate_package(
    path: Path,
    reference_rows: dict[str, dict[str, str]],
    override_rows: dict[str, dict[str, str]],
    client: OpenAI | None,
    args: argparse.Namespace,
) -> dict[str, str]:
    package = load_candidate_package(path)
    source_path = source_path_from_package(package)
    source_record = load_text_record(source_path)
    source_lines = flatten_lines(source_record)
    reference_row = reference_rows.get(package.paper_id, {})
    final_path = args.output_dir / f"{package.paper_id}.json"

    llm_requested = not args.dry_run and (
        args.llm_mode == "all" or (args.llm_mode == "recommended_only" and package.llm_routing_recommended)
    )
    llm_used = False
    llm_validation_passed = False
    llm_validation_reason = "llm_not_requested"
    heuristic_fallback_used = False
    decision: LLMDecision | None = None
    end_selection_mode = "heuristic_only"
    final_block = None

    if llm_requested and client is not None:
        try:
            decision = call_llm_for_end_decision(
                package,
                source_lines,
                client,
                model_name=args.openai_model,
                prompt_version=args.prompt_version,
            )
            llm_used = True
            llm_validation_passed, llm_validation_reason = validate_llm_decision(package, decision, source_lines)
            if llm_validation_passed:
                final_block = apply_llm_decision(package, decision, source_lines)
                if decision.decision_type == "candidate_exact":
                    end_selection_mode = "llm_candidate_exact"
                elif decision.decision_type == "line_within_overshoot":
                    end_selection_mode = "llm_line_within_overshoot"
        except Exception as exc:
            llm_validation_reason = f"llm_request_failed::{exc.__class__.__name__}"

    elif llm_requested and client is None:
        llm_validation_reason = "openai_api_key_missing_or_dry_run"

    if final_block is None:
        fallback_candidate = heuristic_fallback_candidate(package)
        if fallback_candidate is not None:
            heuristic_fallback_used = True
            end_selection_mode = "llm_fallback" if llm_used else "heuristic_only"
            fallback_decision = LLMDecision(
                decision_type="unable_to_determine",
                selected_candidate_id=None,
                last_abstract_line_global_index=None,
                confidence="low",
                end_reason="uncertain",
                explanation_short="No valid LLM decision was available.",
            )
            final_block = apply_llm_decision(
                package,
                fallback_decision,
                source_lines,
            )

    if final_block is not None:
        final_block = apply_trim_override(final_block, override_rows.get(package.paper_id, {}), source_lines)
        quality_status, quality_reason = candidate_quality_status(
            final_block,
            (reference_row.get("Authors") or package.reference_authors).strip(),
        )
        if quality_status == "manual_review_required":
            final_block = None
            trim_status = (
                "manual_review_required_llm_invalid_output" if llm_used and not llm_validation_passed else "manual_review_required_llm_uncertain"
            )
            trim_reason = quality_reason
        elif quality_status == "header_only_source":
            trim_status = "header_only_source"
            trim_reason = quality_reason
        elif end_selection_mode == "llm_candidate_exact":
            trim_status = "trimmed_auto_llm_candidate_exact"
            trim_reason = "LLM selected an existing end candidate as the exact abstract boundary."
        elif end_selection_mode == "llm_line_within_overshoot":
            trim_status = "trimmed_auto_llm_line_within_overshoot"
            trim_reason = "LLM selected a line inside the overshoot candidate as the abstract end."
        else:
            trim_status = "trimmed_auto_llm_fallback_heuristic"
            fallback_candidate = heuristic_fallback_candidate(package)
            heuristic_name = fallback_candidate.heuristic_name if fallback_candidate is not None else "unknown"
            if llm_used and not llm_validation_passed:
                trim_reason = f"LLM output failed validation ({llm_validation_reason}); used heuristic fallback {heuristic_name}."
            else:
                trim_reason = f"Used heuristic fallback {heuristic_name} without an LLM decision."
    else:
        trim_status = (
            "manual_review_required_llm_invalid_output" if llm_used and not llm_validation_passed else "manual_review_required_llm_uncertain"
        )
        trim_reason = "No valid heuristic fallback was available after the LLM stage."

    if final_block is None:
        if final_path.exists():
            final_path.unlink()
        return _empty_registry_row(
            paper_id=package.paper_id,
            covidence_id=(reference_row.get("Covidence") or package.paper_id).strip(),
            title=(reference_row.get("Title") or package.reference_title).strip(),
            authors=(reference_row.get("Authors") or package.reference_authors).strip(),
            source_filename=str(source_record.get("source_filename") or ""),
            source_path=source_path,
            candidate_path=path,
            trim_status=trim_status,
            trim_reason=trim_reason,
            llm_validation_reason=llm_validation_reason,
        )

    trimmed_record = build_trimmed_record(source_record, source_path, final_block, reference_row)
    trimmed_record.update(
        {
            "trim_status": trim_status,
            "trim_reason": trim_reason,
            "trim_workflow_version": package.trim_workflow_version,
            "trim_workflow_stage": "llm_validated",
            "end_selection_mode": end_selection_mode,
            "candidate_source_json_path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            "baseline_candidate_id": package.baseline_candidate_id,
            "overshoot_candidate_id": package.overshoot_candidate_id,
            "candidate_count": len(package.candidates),
            "candidate_ids": [candidate.candidate_id for candidate in package.candidates],
            "llm_used": llm_used,
            "llm_model": args.openai_model if llm_used else "",
            "llm_api_mode": "responses_json_schema" if llm_used else "",
            "llm_prompt_version": args.prompt_version if llm_used else "",
            "llm_decision_type": decision.decision_type if decision else "",
            "llm_selected_candidate_id": decision.selected_candidate_id if decision else "",
            "llm_last_abstract_line_global_index": decision.last_abstract_line_global_index if decision else None,
            "llm_confidence": decision.confidence if decision else "",
            "llm_end_reason": decision.end_reason if decision else "",
            "llm_explanation_short": decision.explanation_short if decision else "",
            "llm_validation_passed": llm_validation_passed,
            "llm_validation_reason": llm_validation_reason,
            "heuristic_fallback_used": heuristic_fallback_used,
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(trimmed_record, ensure_ascii=False, indent=2), encoding="utf-8")
    return final_registry_row(
        package=package,
        reference_row=reference_row,
        source_record=source_record,
        source_path=source_path,
        candidate_path=path,
        trimmed_path=final_path,
        trim_status=trim_status,
        trim_reason=trim_reason,
        final_block=final_block,
        end_selection_mode=end_selection_mode,
        llm_used=llm_used,
        llm_model=args.openai_model if llm_used else "",
        prompt_version=args.prompt_version,
        decision=decision,
        llm_validation_passed=llm_validation_passed,
        llm_validation_reason=llm_validation_reason,
        heuristic_fallback_used=heuristic_fallback_used,
    )


def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    override_rows = load_trim_override_rows(TRIM_OVERRIDE_PATH)
    candidate_paths = _candidate_package_paths(args.candidate_input_dir, args.paper_id, args.limit)
    client = _prepare_openai_client(args)
    print(f"Proceedings LLM validation count: {len(candidate_paths)}")
    rows: list[dict[str, str]] = []
    for path in tqdm(candidate_paths, desc="Proceedings LLM validate"):
        rows.append(process_candidate_package(path, reference_rows, override_rows, client, args))
    _write_registry(rows, args.registry_path, preserve_existing=bool(args.paper_id or args.limit))
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.registry_path}")


if __name__ == "__main__":
    main()
