from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tqdm import tqdm

from _proceedings_text import flatten_lines, infer_proceedings_pattern
from _proceedings_trim_core import (
    REFERENCES_CSV,
    REPO_ROOT,
    SOURCE_CATEGORISATION_PATH,
    SOURCE_MANUAL_REVIEW_PATH,
    TEXT_DIR,
    best_matching_block,
    candidate_quality_status,
    choose_best_candidate,
    collect_input_paths,
    extract_blocks,
    filter_to_proceedings_candidates,
    index_assisted_candidate,
    load_reference_rows,
    load_text_record,
    local_window_candidate,
    proceedings_signals,
    refresh_artifact_registry,
    sort_registry_rows,
)
from _proceedings_trim_llm import (
    CANDIDATE_GENERATION_MODE,
    CandidatePackage,
    build_end_candidates,
    candidate_registry_fieldnames,
    candidate_registry_row,
    dedupe_end_candidates,
    first_confirmed_header_after_start,
    llm_routing_recommendation,
    resolve_candidate_id_by_end,
    write_candidate_package,
)
from _source_routing import load_csv_rows_by_id


CANDIDATE_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed_llm_candidates"
CANDIDATE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_llm_candidate_registry.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ordered LLM candidate packages for proceedings abstract trimming."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--candidate-output-dir", type=Path, default=CANDIDATE_OUT_DIR)
    parser.add_argument("--candidate-registry-path", type=Path, default=CANDIDATE_REGISTRY_PATH)
    parser.add_argument("--source-categorisation-path", type=Path, default=SOURCE_CATEGORISATION_PATH)
    parser.add_argument("--source-manual-review-path", type=Path, default=SOURCE_MANUAL_REVIEW_PATH)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--all-papers", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-pages-from-start", type=int, default=2)
    parser.add_argument("--max-lines-from-start", type=int, default=140)
    parser.add_argument("--max-chars-from-start", type=int, default=7000)
    parser.add_argument(
        "--route-all-to-llm",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Route all candidate packages to the LLM validation stage in v1.",
    )
    parser.add_argument("--skip-registry-refresh", action="store_true")
    return parser.parse_args()


def _write_registry(rows: list[dict[str, str]], path: Path, preserve_existing: bool = False) -> None:
    fieldnames = candidate_registry_fieldnames()
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


def _empty_registry_row(
    *,
    paper_id: str,
    reference_row: dict[str, str],
    source_record: dict[str, object],
    source_path: Path,
    trim_status: str,
    trim_reason: str,
) -> dict[str, str]:
    row = {field: "" for field in candidate_registry_fieldnames()}
    row.update(
        {
            "paper_id": paper_id,
            "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
            "title": (reference_row.get("Title") or "").strip(),
            "authors": (reference_row.get("Authors") or "").strip(),
            "source_filename": str(source_record.get("source_filename") or ""),
            "source_text_json_path": str(source_path.relative_to(REPO_ROOT)) if source_path.is_relative_to(REPO_ROOT) else str(source_path),
            "n_pages": str(source_record.get("n_pages") or 0),
            "trim_workflow_version": "proceedings_llm_v1",
            "trim_workflow_stage": "candidate_generation",
            "trim_status": trim_status,
            "trim_reason": trim_reason,
        }
    )
    return row


def _candidate_package_for_block(
    *,
    paper_id: str,
    source_path: Path,
    reference_row: dict[str, str],
    signals: dict[str, object],
    lines,
    pattern,
    block,
    index_diagnostics: dict[str, object],
    args: argparse.Namespace,
) -> CandidatePackage:
    baseline_status, baseline_reason = candidate_quality_status(block, (reference_row.get("Authors") or "").strip())
    next_confirmed_header_index = first_confirmed_header_after_start(lines, block.start_index, pattern)
    raw_candidates, window_metadata = build_end_candidates(
        lines,
        block,
        pattern,
        next_confirmed_header_index,
        max_pages_from_start=args.max_pages_from_start,
        max_lines_from_start=args.max_lines_from_start,
        max_chars_from_start=args.max_chars_from_start,
    )
    candidates = dedupe_end_candidates(raw_candidates)
    baseline_candidate_id = resolve_candidate_id_by_end(
        candidates,
        start_index=block.start_index,
        end_index_exclusive=int(window_metadata["baseline_end_index_exclusive"]),
    )
    overshoot_candidate_id = resolve_candidate_id_by_end(
        candidates,
        start_index=block.start_index,
        end_index_exclusive=int(window_metadata["overshoot_end_index_exclusive"]),
    )
    upstream_match_metadata = {
        "trim_method": block.trim_method,
        "trim_mode": block.trim_mode,
        "title_score": round(block.title_score, 4),
        "author_score": round(block.author_score, 4),
        "match_score": round(block.match_score, 4),
        "end_rule": block.end_rule,
        "matched_end_index_exclusive": block.end_index,
        "matched_end_page_index": block.end_page_index,
        "body_signal_count": block.body_signal_count,
        "header_only_flag": block.header_only_flag,
        "spillover_flag": block.spillover_flag,
        "index_detected": block.index_detected,
        "index_confidence": round(block.index_confidence, 4),
        "index_listed_page": block.index_listed_page,
        "index_prev_code": block.index_prev_code,
        "index_next_code": block.index_next_code,
        "page_map_method": block.page_map_method,
        "estimated_offset": round(block.estimated_offset, 3),
        "offset_confidence": round(block.offset_confidence, 4),
        "fallback_triggered": block.fallback_triggered,
        "candidate_quality_status": baseline_status,
        "candidate_quality_reason": baseline_reason,
        **window_metadata,
        **index_diagnostics,
    }
    package = CandidatePackage(
        paper_id=paper_id,
        source_text_json_path=str(source_path.relative_to(REPO_ROOT)) if source_path.is_relative_to(REPO_ROOT) else str(source_path),
        reference_title=(reference_row.get("Title") or "").strip(),
        reference_authors=(reference_row.get("Authors") or "").strip(),
        matched_start_index=block.start_index,
        matched_start_page_index=block.start_page_index,
        matched_block_code=block.code,
        matched_block_title=block.title_text,
        start_rule=block.start_rule,
        candidate_generation_mode=CANDIDATE_GENERATION_MODE,
        candidates=candidates,
        overshoot_candidate_id=overshoot_candidate_id,
        baseline_candidate_id=baseline_candidate_id,
        proceedings_signals=dict(signals),
        upstream_match_metadata=upstream_match_metadata,
    )
    routed, routing_reason = (True, "route_all_to_llm_v1") if args.route_all_to_llm else llm_routing_recommendation(package)
    package.llm_routing_recommended = routed
    package.llm_routing_reason = routing_reason
    return package


def process_record(
    path: Path,
    reference_rows: dict[str, dict[str, str]],
    args: argparse.Namespace,
) -> dict[str, str]:
    record = load_text_record(path)
    paper_id = str(record.get("paper_id") or path.stem)
    reference_row = reference_rows.get(paper_id, {})
    candidate_path = args.candidate_output_dir / f"{paper_id}.json"

    lines = flatten_lines(record)
    pattern = infer_proceedings_pattern(lines)
    signals = proceedings_signals(record, lines)
    if not signals["proceedings_detected"]:
        if candidate_path.exists():
            candidate_path.unlink()
        return _empty_registry_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trim_status="not_needed",
            trim_reason="Document does not look like a proceedings source.",
        )

    block_candidate = best_matching_block(
        extract_blocks(lines, pattern),
        (reference_row.get("Title") or "").strip(),
        (reference_row.get("Authors") or "").strip(),
    )
    index_candidate, index_diagnostics = index_assisted_candidate(
        lines=lines,
        record=record,
        reference_title=(reference_row.get("Title") or "").strip(),
        reference_authors=(reference_row.get("Authors") or "").strip(),
        pattern=pattern,
    )
    fallback_window_candidate = local_window_candidate(
        lines=lines,
        record=record,
        reference_title=(reference_row.get("Title") or "").strip(),
        reference_authors=(reference_row.get("Authors") or "").strip(),
        pattern=pattern,
        trim_mode="page_local_sliding_window_match",
        fallback_triggered=index_candidate is None,
    )
    window_candidate = index_candidate if index_candidate is not None else fallback_window_candidate
    if window_candidate is not None and window_candidate.trim_mode.startswith("index_assisted"):
        window_candidate.fallback_triggered = False
    elif window_candidate is not None:
        window_candidate.fallback_triggered = True
    if block_candidate is not None and not block_candidate.trim_mode:
        block_candidate.trim_mode = "fuzzy_title_author_block_match"

    block = choose_best_candidate(block_candidate, window_candidate)
    if block is None:
        if candidate_path.exists():
            candidate_path.unlink()
        return _empty_registry_row(
            paper_id=paper_id,
            reference_row=reference_row,
            source_record=record,
            source_path=path,
            trim_status="manual_review_required",
            trim_reason="No abstract block could be segmented from the proceedings text.",
        )

    block.index_detected = block.index_detected or bool(index_diagnostics.get("index_detected"))
    if block.index_confidence == 0.0:
        block.index_confidence = float(index_diagnostics.get("index_confidence") or 0.0)
    if not block.index_listed_page:
        block.index_listed_page = str(index_diagnostics.get("index_listed_page") or "")
    if not block.index_prev_code:
        block.index_prev_code = str(index_diagnostics.get("index_prev_code") or "")
    if not block.index_next_code:
        block.index_next_code = str(index_diagnostics.get("index_next_code") or "")
    if not block.page_map_method:
        block.page_map_method = str(index_diagnostics.get("page_map_method") or "")
    if block.estimated_offset == 0.0:
        block.estimated_offset = float(index_diagnostics.get("estimated_offset") or 0.0)
    if block.offset_confidence == 0.0:
        block.offset_confidence = float(index_diagnostics.get("offset_confidence") or 0.0)
    block.fallback_triggered = bool(index_diagnostics.get("fallback_triggered")) and not block.trim_mode.startswith(
        "index_assisted"
    )

    package = _candidate_package_for_block(
        paper_id=paper_id,
        source_path=path,
        reference_row=reference_row,
        signals=signals,
        lines=lines,
        pattern=pattern,
        block=block,
        index_diagnostics=index_diagnostics,
        args=args,
    )
    write_candidate_package(package, candidate_path)
    return candidate_registry_row(
        package=package,
        source_record=record,
        source_path=path,
        candidate_path=candidate_path,
        reference_row=reference_row,
        trim_status="candidate_package_created",
        trim_reason=(
            f"Wrote LLM candidate package with {len(package.candidates)} ordered end candidates. "
            f"Baseline candidate quality: {package.upstream_match_metadata.get('candidate_quality_status') or 'unknown'}."
        ),
    )


def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    input_paths = collect_input_paths(args.input_dir, args.paper_id, args.limit)
    input_paths = filter_to_proceedings_candidates(
        paths=input_paths,
        source_categorisation_path=args.source_categorisation_path,
        source_manual_review_path=args.source_manual_review_path,
        existing_trim_registry_path=args.candidate_registry_path,
        force_all_papers=args.all_papers,
        explicit_paper_ids=args.paper_id,
        include_already_trimmed=False,
    )
    print(f"Proceedings LLM candidate count: {len(input_paths)}")
    rows: list[dict[str, str]] = []
    for path in tqdm(input_paths, desc="Proceedings LLM trim"):
        rows.append(process_record(path, reference_rows, args))
    _write_registry(rows, args.candidate_registry_path, preserve_existing=bool(args.paper_id or args.limit))
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.candidate_registry_path}")


if __name__ == "__main__":
    main()
