from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation._stage05_gold import GOLD_PAPERS_DIR, MANIFEST_PATH, active_entries_by_id

from _proceedings_ready import (
    REPO_ROOT,
    TEXT_DIR,
    TEXT_PROCEEDINGS_READY_DIR,
    TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
    TEXT_TRIMMED_DIR,
    TEXT_TRIMMED_LLM_DIR,
    TEXT_TRIM_LLM_CANDIDATE_REGISTRY_PATH,
    TEXT_TRIM_LLM_REGISTRY_PATH,
    build_span_record,
    load_json,
    load_csv_rows_by_id,
    looks_like_full_article_frontmatter,
    now_utc_iso,
    refine_ready_end_index,
    refine_ready_start_index,
    relative_to_repo,
    write_json,
)
from _proceedings_text import flatten_lines
from _source_routing import resolve_source_row


REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish canonical proceedings-ready text JSONs from gold, LLM trims, and source-text pass-through cases."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--source-categorisation-path", type=Path, default=SOURCE_CATEGORISATION_PATH)
    parser.add_argument("--source-manual-review-path", type=Path, default=SOURCE_MANUAL_REVIEW_PATH)
    parser.add_argument("--source-text-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--legacy-trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--llm-trimmed-dir", type=Path, default=TEXT_TRIMMED_LLM_DIR)
    parser.add_argument("--llm-registry-path", type=Path, default=TEXT_TRIM_LLM_REGISTRY_PATH)
    parser.add_argument("--llm-candidate-registry-path", type=Path, default=TEXT_TRIM_LLM_CANDIDATE_REGISTRY_PATH)
    parser.add_argument("--gold-manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--gold-papers-dir", type=Path, default=GOLD_PAPERS_DIR)
    parser.add_argument("--output-dir", type=Path, default=TEXT_PROCEEDINGS_READY_DIR)
    parser.add_argument("--output-path", type=Path, default=TEXT_PROCEEDINGS_READY_REGISTRY_PATH)
    parser.add_argument("--paper-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-registry-refresh", action="store_true")
    return parser.parse_args()


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("Covidence") or "").strip(): row
            for row in csv.DictReader(handle)
            if str(row.get("Covidence") or "").strip()
        }


def sort_paper_ids(ids: set[str]) -> list[str]:
    def key(value: str) -> tuple[int, int | str]:
        stripped = value.strip()
        if stripped.isdigit():
            return (0, int(stripped))
        return (1, stripped)

    return sorted(ids, key=key)


def document_end_index(record: dict[str, Any]) -> int:
    lines = flatten_lines(record)
    if not lines:
        return 0
    return lines[-1].global_index + 1


def add_ready_metadata(
    payload: dict[str, Any],
    *,
    ready_source_kind: str,
    ready_text_mode: str,
    ready_source_detail: str,
    ready_reason: str,
) -> dict[str, Any]:
    updated = dict(payload)
    updated["proceedings_ready_source_kind"] = ready_source_kind
    updated["proceedings_ready_text_mode"] = ready_text_mode
    updated["proceedings_ready_source_detail"] = ready_source_detail
    updated["proceedings_ready_reason"] = ready_reason
    updated["proceedings_ready_built_at_utc"] = now_utc_iso()
    return updated


def rebuild_from_source(
    *,
    source_record: dict[str, Any],
    source_path: Path,
    start_index: int,
    end_index_exclusive: int,
    matched_code: str,
    matched_title: str,
    base_payload: dict[str, Any] | None,
    ready_source_kind: str,
    ready_text_mode: str,
    ready_source_detail: str,
    ready_reason: str,
) -> dict[str, Any]:
    source_lines = flatten_lines(source_record)
    clean_start_index = refine_ready_start_index(
        source_lines,
        start_index=start_index,
        end_index_exclusive=end_index_exclusive,
        matched_code=matched_code,
        matched_title=matched_title,
    )
    clean_end_index = refine_ready_end_index(
        source_lines,
        start_index=clean_start_index,
        end_index_exclusive=end_index_exclusive,
    )
    return build_span_record(
        source_record=source_record,
        source_path=source_path,
        start_index=clean_start_index,
        end_index_exclusive=clean_end_index,
        base_payload=base_payload,
        ready_source_kind=ready_source_kind,
        ready_text_mode=ready_text_mode,
        ready_source_detail=ready_source_detail,
        ready_reason=ready_reason,
    )


def ready_registry_row(
    *,
    paper_id: str,
    reference_row: dict[str, str],
    resolved_source: dict[str, str],
    ready_path: Path,
    ready_source_kind: str,
    ready_text_mode: str,
    ready_source_detail: str,
    ready_source_input_path: Path | None,
    source_text_path: Path | None,
    llm_candidate_path: Path | None,
    llm_trimmed_path: Path | None,
    gold_json_path: Path | None,
    ready_payload: dict[str, Any],
    final_row: dict[str, str],
    ready_reason: str,
) -> dict[str, str]:
    return {
        "paper_id": paper_id,
        "covidence_id": (reference_row.get("Covidence") or paper_id).strip(),
        "title": (reference_row.get("Title") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "resolved_source_category": str(resolved_source.get("resolved_source_category") or ""),
        "resolved_source_subtype": str(resolved_source.get("resolved_source_subtype") or ""),
        "ready_text_json_path": relative_to_repo(ready_path),
        "ready_source_kind": ready_source_kind,
        "ready_text_mode": ready_text_mode,
        "ready_source_detail": ready_source_detail,
        "ready_source_input_path": relative_to_repo(ready_source_input_path),
        "source_text_json_path": relative_to_repo(source_text_path),
        "llm_candidate_json_path": relative_to_repo(llm_candidate_path),
        "llm_trimmed_json_path": relative_to_repo(llm_trimmed_path),
        "gold_json_path": relative_to_repo(gold_json_path),
        "ready_start_line_global_index": str(
            ready_payload.get("proceedings_ready_start_line_global_index")
            or ready_payload.get("start_line_global_index")
            or ""
        ),
        "ready_end_line_global_index_exclusive": str(
            ready_payload.get("proceedings_ready_end_line_global_index_exclusive")
            or ready_payload.get("end_line_global_index_exclusive")
            or ""
        ),
        "llm_trim_status": str(final_row.get("trim_status") or ""),
        "llm_validation_passed": str(final_row.get("llm_validation_passed") or ""),
        "llm_validation_reason": str(final_row.get("llm_validation_reason") or ""),
        "ready_reason": ready_reason,
        "published_at_utc": now_utc_iso(),
    }


def write_registry(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "resolved_source_category",
        "resolved_source_subtype",
        "ready_text_json_path",
        "ready_source_kind",
        "ready_text_mode",
        "ready_source_detail",
        "ready_source_input_path",
        "source_text_json_path",
        "llm_candidate_json_path",
        "llm_trimmed_json_path",
        "gold_json_path",
        "ready_start_line_global_index",
        "ready_end_line_global_index_exclusive",
        "llm_trim_status",
        "llm_validation_passed",
        "llm_validation_reason",
        "ready_reason",
        "published_at_utc",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def main() -> None:
    args = parse_args()
    reference_rows = load_reference_rows(args.references_csv)
    source_rows = load_csv_rows_by_id(args.source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(args.source_manual_review_path, "paper_id")
    candidate_rows = load_csv_rows_by_id(args.llm_candidate_registry_path, "paper_id")
    final_rows = load_csv_rows_by_id(args.llm_registry_path, "paper_id")
    gold_entries = active_entries_by_id(args.gold_manifest_path)
    legacy_trimmed_ids = {
        path.stem
        for path in args.legacy_trimmed_dir.glob("*.json")
    }

    all_ids = set(source_rows) | set(manual_rows) | set(candidate_rows) | set(final_rows) | set(gold_entries) | legacy_trimmed_ids
    wanted = {paper_id.strip() for paper_id in args.paper_id if paper_id.strip()}

    output_rows: list[dict[str, str]] = []
    unresolved: list[str] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for paper_id in sort_paper_ids(all_ids):
        if wanted and paper_id not in wanted:
            continue
        resolved_source = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=source_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        if (resolved_source.get("resolved_source_category") or "") != "conference_abstract":
            continue

        source_text_path = args.source_text_dir / f"{paper_id}.json"
        legacy_trimmed_path = args.legacy_trimmed_dir / f"{paper_id}.json"
        llm_trimmed_path = args.llm_trimmed_dir / f"{paper_id}.json"
        llm_candidate_path = args.llm_trimmed_dir.parent / "text_trimmed_llm_candidates" / f"{paper_id}.json"
        gold_path = args.gold_papers_dir / f"{paper_id}.json"
        reference_row = reference_rows.get(paper_id, {})
        candidate_row = candidate_rows.get(paper_id, {})
        final_row = final_rows.get(paper_id, {})
        heuristic_row = source_rows.get(paper_id, {})
        ready_path = args.output_dir / f"{paper_id}.json"

        ready_payload: dict[str, Any] | None = None
        ready_source_kind = ""
        ready_text_mode = ""
        ready_source_detail = ""
        ready_source_input_path: Path | None = None
        ready_reason = ""

        if gold_entries.get(paper_id) and gold_path.exists():
            ready_payload = add_ready_metadata(
                load_json(gold_path),
                ready_source_kind="gold_manual",
                ready_text_mode="trimmed_abstract",
                ready_source_detail="active_gold_manifest",
                ready_reason="Published active manually checked gold-standard proceedings trim.",
            )
            ready_source_kind = "gold_manual"
            ready_text_mode = "trimmed_abstract"
            ready_source_detail = "active_gold_manifest"
            ready_source_input_path = gold_path
            ready_reason = "Published active manually checked gold-standard proceedings trim."
        elif candidate_row.get("trim_status") == "not_needed" and source_text_path.exists():
            source_record = load_json(source_text_path)
            ready_payload = rebuild_from_source(
                source_record=source_record,
                source_path=source_text_path,
                start_index=0,
                end_index_exclusive=document_end_index(source_record),
                matched_code="",
                matched_title=(reference_row.get("Title") or "").strip(),
                base_payload=source_record,
                ready_source_kind="source_text_passthrough",
                ready_text_mode="full_text_passthrough",
                ready_source_detail="candidate_not_needed",
                ready_reason=str(candidate_row.get("trim_reason") or "Document did not need proceedings trimming."),
            )
            ready_source_kind = "source_text_passthrough"
            ready_text_mode = "full_text_passthrough"
            ready_source_detail = "candidate_not_needed"
            ready_source_input_path = source_text_path
            ready_reason = str(candidate_row.get("trim_reason") or "Document did not need proceedings trimming.")
        elif final_row.get("llm_validation_passed") == "true" and llm_trimmed_path.exists():
            ready_payload = add_ready_metadata(
                load_json(llm_trimmed_path),
                ready_source_kind="llm_validated",
                ready_text_mode="trimmed_abstract",
                ready_source_detail="text_trimmed_llm",
                ready_reason=str(final_row.get("trim_reason") or "Validated proceedings trim."),
            )
            ready_source_kind = "llm_validated"
            ready_text_mode = "trimmed_abstract"
            ready_source_detail = "text_trimmed_llm"
            ready_source_input_path = llm_trimmed_path
            ready_reason = str(final_row.get("trim_reason") or "Validated proceedings trim.")
        elif source_text_path.exists():
            source_record = load_json(source_text_path)
            if looks_like_full_article_frontmatter(source_record):
                ready_payload = rebuild_from_source(
                    source_record=source_record,
                    source_path=source_text_path,
                    start_index=0,
                    end_index_exclusive=document_end_index(source_record),
                    matched_code=str(final_row.get("matched_block_code") or candidate_row.get("matched_block_code") or ""),
                    matched_title=str(final_row.get("matched_block_title") or candidate_row.get("matched_block_title") or reference_row.get("Title") or ""),
                    base_payload=source_record,
                    ready_source_kind="source_text_passthrough",
                    ready_text_mode="full_text_passthrough",
                    ready_source_detail="article_frontmatter_passthrough",
                    ready_reason="Proceedings trim fallback resembled journal-article front matter; published cleaned full text instead.",
                )
                ready_source_kind = "source_text_passthrough"
                ready_text_mode = "full_text_passthrough"
                ready_source_detail = "article_frontmatter_passthrough"
                ready_source_input_path = source_text_path
                ready_reason = "Proceedings trim fallback resembled journal-article front matter; published cleaned full text instead."
            elif final_row.get("llm_last_abstract_line_global_index"):
                end_index_exclusive = int(final_row["llm_last_abstract_line_global_index"]) + 1
                base_payload = load_json(llm_trimmed_path) if llm_trimmed_path.exists() else {}
                ready_payload = rebuild_from_source(
                    source_record=source_record,
                    source_path=source_text_path,
                    start_index=int(final_row.get("start_line_global_index") or candidate_row.get("start_line_global_index") or 0),
                    end_index_exclusive=end_index_exclusive,
                    matched_code=str(final_row.get("matched_block_code") or candidate_row.get("matched_block_code") or ""),
                    matched_title=str(final_row.get("matched_block_title") or candidate_row.get("matched_block_title") or reference_row.get("Title") or ""),
                    base_payload=base_payload,
                    ready_source_kind="llm_decision_rebuilt",
                    ready_text_mode="trimmed_abstract",
                    ready_source_detail="llm_decision_span",
                    ready_reason="Published a rebuilt proceedings trim from the LLM-selected boundary to remove residual footer spillover.",
                )
                ready_source_kind = "llm_decision_rebuilt"
                ready_text_mode = "trimmed_abstract"
                ready_source_detail = "llm_decision_span"
                ready_source_input_path = source_text_path
                ready_reason = "Published a rebuilt proceedings trim from the LLM-selected boundary to remove residual footer spillover."
            elif (
                str(heuristic_row.get("trim_status") or "").strip() == "not_needed"
                or str(heuristic_row.get("proceedings_detected") or "").strip().lower() == "false"
            ):
                ready_payload = rebuild_from_source(
                    source_record=source_record,
                    source_path=source_text_path,
                    start_index=0,
                    end_index_exclusive=document_end_index(source_record),
                    matched_code=str(candidate_row.get("matched_block_code") or final_row.get("matched_block_code") or ""),
                    matched_title=str(
                        candidate_row.get("matched_block_title")
                        or final_row.get("matched_block_title")
                        or reference_row.get("Title")
                        or ""
                    ),
                    base_payload=source_record,
                    ready_source_kind="source_text_passthrough",
                    ready_text_mode="full_text_passthrough",
                    ready_source_detail="single_abstract_passthrough",
                    ready_reason="Resolved conference abstract did not require proceedings trimming; published the source abstract text as-is.",
                )
                ready_source_kind = "source_text_passthrough"
                ready_text_mode = "full_text_passthrough"
                ready_source_detail = "single_abstract_passthrough"
                ready_source_input_path = source_text_path
                ready_reason = "Resolved conference abstract did not require proceedings trimming; published the source abstract text as-is."
            elif legacy_trimmed_path.exists():
                ready_payload = add_ready_metadata(
                    load_json(legacy_trimmed_path),
                    ready_source_kind="legacy_trimmed",
                    ready_text_mode="trimmed_abstract",
                    ready_source_detail="text_trimmed",
                    ready_reason="Fell back to the legacy proceedings trim because no LLM-ready publication source was available.",
                )
                ready_source_kind = "legacy_trimmed"
                ready_text_mode = "trimmed_abstract"
                ready_source_detail = "text_trimmed"
                ready_source_input_path = legacy_trimmed_path
                ready_reason = "Fell back to the legacy proceedings trim because no LLM-ready publication source was available."

        if ready_payload is None:
            unresolved.append(paper_id)
            continue

        write_json(ready_path, ready_payload)
        output_rows.append(
            ready_registry_row(
                paper_id=paper_id,
                reference_row=reference_row,
                resolved_source=resolved_source,
                ready_path=ready_path,
                ready_source_kind=ready_source_kind,
                ready_text_mode=ready_text_mode,
                ready_source_detail=ready_source_detail,
                ready_source_input_path=ready_source_input_path,
                source_text_path=source_text_path if source_text_path.exists() else None,
                llm_candidate_path=llm_candidate_path if llm_candidate_path.exists() else None,
                llm_trimmed_path=llm_trimmed_path if llm_trimmed_path.exists() else None,
                gold_json_path=gold_path if gold_path.exists() else None,
                ready_payload=ready_payload,
                final_row=final_row,
                ready_reason=ready_reason,
            )
        )

    if args.limit and args.limit > 0:
        output_rows = output_rows[: args.limit]

    if unresolved:
        raise SystemExit(f"Unresolved proceedings-ready papers: {', '.join(unresolved)}")

    write_registry(output_rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Published {len(output_rows)} proceedings-ready JSONs to {args.output_dir}")


if __name__ == "__main__":
    main()
