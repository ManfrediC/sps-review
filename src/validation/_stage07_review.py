from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_PATH = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_CASE_COUNT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    return {
        (row.get(key_column) or "").strip(): row
        for row in load_csv_rows(path)
        if (row.get(key_column) or "").strip()
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sort_key_for_paper_id(paper_id: str) -> tuple[int, int | str]:
    stripped = str(paper_id or "").strip()
    if stripped.isdigit():
        return (0, int(stripped))
    return (1, stripped)


def preview_text(text: str, limit: int = 280) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def format_span_refs(span_refs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ref in span_refs:
        if (ref.get("ref_type") or "") == "line_range":
            parts.append(
                f"p{ref.get('page_index')}:{ref.get('line_start')}-{ref.get('line_end')}"
            )
    return " | ".join(parts)


def combined_fieldnames() -> list[str]:
    return [
        "paper_id",
        "title",
        "stage06_final_count",
        "stage06_count_confidence",
        "stage06_count_verification_status",
        "stage06_granularity",
        "source_contains_individual_level_data",
        "source_contains_group_level_data",
        "source_preferred_langextract_mode",
        "publication_status",
        "manual_review_required",
        "publication_reason_code",
        "publication_reason",
        "published_unit_count",
        "published_individual_count",
        "published_group_count",
        "shared_context_count",
        "has_unresolved_remainder",
        "unit_ids",
        "unit_types",
        "unit_labels",
        "unresolved_reason_code",
        "unresolved_preview",
        "source_text_json_path",
        "stage07_paper_json_path",
    ]


def write_csv_rows(rows: list[dict[str, str]], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_combined_row(item: dict[str, Any]) -> dict[str, str]:
    payload = item["stage07_payload"]
    decision = payload.get("publication_decision") or {}
    summary = payload.get("stage07_resolution_summary") or {}
    stage06_prior = payload.get("stage06_prior") or {}
    source_route = payload.get("source_route") or {}
    unresolved = payload.get("unresolved_remainder") or {}
    units = payload.get("units") or []
    return {
        "paper_id": item["paper_id"],
        "title": item["title"],
        "stage06_final_count": "" if stage06_prior.get("final_count") is None else str(stage06_prior.get("final_count")),
        "stage06_count_confidence": str(stage06_prior.get("count_confidence") or ""),
        "stage06_count_verification_status": str(stage06_prior.get("count_verification_status") or ""),
        "stage06_granularity": str(stage06_prior.get("granularity") or ""),
        "source_contains_individual_level_data": str(source_route.get("contains_individual_level_data") or ""),
        "source_contains_group_level_data": str(source_route.get("contains_group_level_data") or ""),
        "source_preferred_langextract_mode": str(source_route.get("preferred_langextract_mode") or ""),
        "publication_status": str(decision.get("status") or ""),
        "manual_review_required": str(decision.get("manual_review_required") or ""),
        "publication_reason_code": str(decision.get("reason_code") or ""),
        "publication_reason": str(decision.get("reason") or ""),
        "published_unit_count": str(summary.get("published_unit_count") or 0),
        "published_individual_count": str(summary.get("published_individual_count") or 0),
        "published_group_count": str(summary.get("published_group_count") or 0),
        "shared_context_count": str(summary.get("shared_context_count") or 0),
        "has_unresolved_remainder": str(summary.get("has_unresolved_remainder") or False),
        "unit_ids": " | ".join(str(unit.get("unit_id") or "") for unit in units),
        "unit_types": " | ".join(str(unit.get("unit_type") or "") for unit in units),
        "unit_labels": " | ".join(str(unit.get("unit_label") or "") for unit in units),
        "unresolved_reason_code": str(unresolved.get("reason_code") or ""),
        "unresolved_preview": preview_text(str(unresolved.get("text") or "")),
        "source_text_json_path": str(payload.get("source_text_json_path") or ""),
        "stage07_paper_json_path": item["stage07_paper_json_path"],
    }


def inspection_markdown(
    *,
    run_id: str,
    selection_path: Path,
    registry_path: Path,
    combined_csv_path: Path,
    review_comments_path: Path,
    items: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {run_id} Stage-07 Inspection Pack",
        "",
        f"- Selection JSON: `{display_path(selection_path)}`",
        f"- Stage-07 registry: `{display_path(registry_path)}`",
        f"- Combined QA CSV: `{display_path(combined_csv_path)}`",
        f"- Per-paper comments: `{display_path(review_comments_path)}`",
        "",
    ]
    for item in items:
        payload = item["stage07_payload"]
        decision = payload.get("publication_decision") or {}
        summary = payload.get("stage07_resolution_summary") or {}
        stage06_prior = payload.get("stage06_prior") or {}
        source_route = payload.get("source_route") or {}
        unresolved = payload.get("unresolved_remainder") or {}
        lines.extend(
            [
                f"## {item['paper_id']} - {item['title']}",
                f"- source_text_json_path: {payload.get('source_text_json_path') or ''}",
                f"- stage07_paper_json_path: {item['stage07_paper_json_path']}",
                f"- source_route: individual={source_route.get('contains_individual_level_data')} group={source_route.get('contains_group_level_data')} preferred_mode={source_route.get('preferred_langextract_mode') or ''}",
                f"- stage06_prior: count={stage06_prior.get('final_count')} confidence={stage06_prior.get('count_confidence') or ''} verification_status={stage06_prior.get('count_verification_status') or ''} granularity={stage06_prior.get('granularity') or ''}",
                f"- publication_decision: status={decision.get('status') or ''} manual_review_required={decision.get('manual_review_required')} reason_code={decision.get('reason_code') or ''}",
                f"- publication_reason: {decision.get('reason') or ''}",
                f"- resolution_summary: published={summary.get('published_unit_count') or 0} individual={summary.get('published_individual_count') or 0} group={summary.get('published_group_count') or 0} shared_context={summary.get('shared_context_count') or 0} unresolved={summary.get('has_unresolved_remainder') or False}",
                "- units:",
            ]
        )
        units = payload.get("units") or []
        if units:
            for unit in units:
                span_text = format_span_refs(unit.get("source_span_refs") or [])
                lines.append(
                    f"  - {unit.get('unit_id') or ''} | {unit.get('unit_type') or ''} | {unit.get('unit_label') or ''} | spans={span_text}"
                )
                if unit.get("group_size") is not None:
                    lines.append(f"    group_size={unit.get('group_size')}")
                if unit.get("linked_shared_context_ids"):
                    lines.append(
                        f"    shared_context={', '.join(str(value) for value in unit.get('linked_shared_context_ids') or [])}"
                    )
                lines.append(f"    text={preview_text(str(unit.get('unit_text') or ''), limit=420)}")
        else:
            lines.append("  - None")
        lines.append("- shared_context_blocks:")
        shared_blocks = payload.get("shared_context_blocks") or []
        if shared_blocks:
            for block in shared_blocks:
                span_text = format_span_refs(block.get("source_span_refs") or [])
                lines.append(
                    f"  - {block.get('context_id') or ''} | applies_to={', '.join(str(value) for value in block.get('applies_to_unit_ids') or [])} | spans={span_text}"
                )
                lines.append(f"    text={preview_text(str(block.get('text') or ''), limit=320)}")
        else:
            lines.append("  - None")
        lines.extend(
            [
                f"- unresolved_remainder_present: {unresolved.get('present') or False}",
                f"- unresolved_reason_code: {unresolved.get('reason_code') or ''}",
                f"- unresolved_text: {preview_text(str(unresolved.get('text') or ''), limit=420)}",
                "",
            ]
        )
    return "\n".join(lines)


def review_comments_fieldnames() -> list[str]:
    return [
        "paper_id",
        "title",
        "stage06_final_count",
        "stage07_publication_status",
        "stage07_reason_code",
        "published_unit_count",
        "assessment",
        "review_comment",
        "proposed_action",
        "review_status",
    ]


def review_comment_row(item: dict[str, Any]) -> dict[str, str]:
    payload = item["stage07_payload"]
    decision = payload.get("publication_decision") or {}
    summary = payload.get("stage07_resolution_summary") or {}
    stage06_prior = payload.get("stage06_prior") or {}
    return {
        "paper_id": item["paper_id"],
        "title": item["title"],
        "stage06_final_count": "" if stage06_prior.get("final_count") is None else str(stage06_prior.get("final_count")),
        "stage07_publication_status": str(decision.get("status") or ""),
        "stage07_reason_code": str(decision.get("reason_code") or ""),
        "published_unit_count": str(summary.get("published_unit_count") or 0),
        "assessment": "",
        "review_comment": "",
        "proposed_action": "",
        "review_status": "",
    }


def review_notes_markdown(
    *,
    run_id: str,
    selection_path: Path,
    registry_path: Path,
    combined_csv_path: Path,
    inspection_path: Path,
    review_comments_path: Path,
) -> str:
    return "\n".join(
        [
            f"# {run_id} Stage-07 Review Notes",
            "",
            f"- Selection JSON: `{display_path(selection_path)}`",
            f"- Stage-07 registry: `{display_path(registry_path)}`",
            f"- Combined QA CSV: `{display_path(combined_csv_path)}`",
            f"- Inspection pack: `{display_path(inspection_path)}`",
            f"- Per-paper comments: `{display_path(review_comments_path)}`",
            "",
            "## Review prompts",
            "",
            "- Check whether each published unit is attribution-safe.",
            "- Check whether shared-context blocks are linked to the correct units only.",
            "- Check whether any unresolved remainder contains information that should block automatic publication.",
            "- Record must-fix issues in `review_comments.csv` before any canonical rerun.",
        ]
    )


def load_review_items(run_root: Path) -> list[dict[str, Any]]:
    selection_path = run_root / "selection.json"
    registry_path = run_root / "case_series_split_registry.csv"
    units_dir = run_root / "text_case_series_units"
    selection_payload = load_json(selection_path)
    registry_rows = load_csv_rows_by_id(registry_path, "paper_id")
    stage06_rows = load_csv_rows_by_id(SOURCE_CASE_COUNT_PATH, "paper_id")
    source_rows = load_csv_rows_by_id(SOURCE_CATEGORISATION_PATH, "paper_id")
    reference_rows = load_csv_rows_by_id(REFERENCES_PATH, "Covidence")

    items: list[dict[str, Any]] = []
    for paper_id in sorted(selection_payload.get("paper_ids") or [], key=sort_key_for_paper_id):
        payload_path = units_dir / f"{paper_id}.json"
        if not payload_path.exists():
            continue
        reference_row = reference_rows.get(str(paper_id), {})
        items.append(
            {
                "paper_id": str(paper_id),
                "title": str(reference_row.get("Title") or ""),
                "source_row": source_rows.get(str(paper_id), {}),
                "stage06_row": stage06_rows.get(str(paper_id), {}),
                "stage07_registry_row": registry_rows.get(str(paper_id), {}),
                "stage07_payload": load_json(payload_path),
                "stage07_paper_json_path": display_path(payload_path),
            }
        )
    return items


def build_qa_pack(run_root: Path) -> dict[str, str]:
    run_id = run_root.name
    selection_path = run_root / "selection.json"
    registry_path = run_root / "case_series_split_registry.csv"
    combined_csv_path = run_root / f"{run_id}_combined.csv"
    inspection_path = run_root / f"{run_id}_inspection.md"
    review_comments_path = run_root / f"{run_id}_review_comments.csv"
    review_notes_path = run_root / f"{run_id}_review_notes.md"

    items = load_review_items(run_root)
    combined_rows = [build_combined_row(item) for item in items]
    write_csv_rows(combined_rows, combined_csv_path, combined_fieldnames())
    write_csv_rows(
        [review_comment_row(item) for item in items],
        review_comments_path,
        review_comments_fieldnames(),
    )
    inspection_path.write_text(
        inspection_markdown(
            run_id=run_id,
            selection_path=selection_path,
            registry_path=registry_path,
            combined_csv_path=combined_csv_path,
            review_comments_path=review_comments_path,
            items=items,
        ),
        encoding="utf-8",
    )
    review_notes_path.write_text(
        review_notes_markdown(
            run_id=run_id,
            selection_path=selection_path,
            registry_path=registry_path,
            combined_csv_path=combined_csv_path,
            inspection_path=inspection_path,
            review_comments_path=review_comments_path,
        ),
        encoding="utf-8",
    )
    return {
        "combined_csv_path": display_path(combined_csv_path),
        "inspection_md_path": display_path(inspection_path),
        "review_comments_csv_path": display_path(review_comments_path),
        "review_notes_md_path": display_path(review_notes_path),
    }
