from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _source_routing import load_csv_rows_by_id, resolve_source_row, truthy


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
SPLIT_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "text_case_series_split"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
PROCEEDINGS_QC_PATH = REPO_ROOT / "data" / "references" / "proceedings_text_qc_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "case_series_split_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"

CASE_MARKER_RE = re.compile(
    r"^(?P<lemma>case|patient)\b\s*(?:no\.?|number)?\s*(?P<num>\d+|[ivxlcdm]+|[a-z])\b[:.\-)]?",
    re.IGNORECASE,
)
ORDINAL_MARKER_RE = re.compile(
    r"^(?P<label>(?:first|second|third|fourth|fifth|sixth)\s+(?:case|patient))\b[:.\-)]?",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split reviewed case-series papers into case-level text segments for downstream LangExtract."
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing full extracted text JSON files.",
    )
    parser.add_argument(
        "--trimmed-dir",
        type=Path,
        default=TEXT_TRIMMED_DIR,
        help="Directory containing proceedings-trimmed text JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SPLIT_OUT_DIR,
        help="Directory for per-paper case-series split JSON files.",
    )
    parser.add_argument(
        "--source-categorisation-path",
        type=Path,
        default=SOURCE_CATEGORISATION_PATH,
        help="Heuristic source categorisation registry.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=SOURCE_MANUAL_REVIEW_PATH,
        help="Manual source categorisation overrides.",
    )
    parser.add_argument(
        "--proceedings-qc-path",
        type=Path,
        default=PROCEEDINGS_QC_PATH,
        help="Proceedings QC registry used to gate conference-abstract case splitting.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=OUTPUT_PATH,
        help="CSV registry output path.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of candidate papers to inspect.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing split outputs.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_candidate_ids(
    text_dir: Path,
    heuristic_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    paper_ids: list[str],
    limit: int,
) -> list[str]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    candidates: list[str] = []
    for path in sorted(text_dir.glob("*.json")):
        paper_id = path.stem
        if wanted and paper_id not in wanted:
            continue
        resolved = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        if truthy(resolved.get("resolved_case_series_split_candidate")):
            candidates.append(paper_id)
    if limit and limit > 0:
        return candidates[:limit]
    return candidates


def flatten_lines(record: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        for line_index, raw_line in enumerate(page_text.splitlines()):
            line = " ".join(raw_line.split())
            if line:
                lines.append(
                    {
                        "page_index": page_index,
                        "line_index": line_index,
                        "text": line,
                    }
                )
    return lines


def parse_case_marker(line: str) -> str | None:
    stripped = line.strip()
    if len(stripped) > 120:
        return None
    match = CASE_MARKER_RE.match(stripped)
    if match:
        return f"{match.group('lemma')} {match.group('num')}"
    ordinal_match = ORDINAL_MARKER_RE.match(stripped)
    if ordinal_match:
        return ordinal_match.group("label")
    return None


def unique_markers(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for index, line in enumerate(lines):
        label = parse_case_marker(line["text"])
        if not label:
            continue
        normalized_label = label.lower().strip()
        if normalized_label in seen_labels:
            continue
        seen_labels.add(normalized_label)
        markers.append(
            {
                "label": label,
                "normalized_label": normalized_label,
                "start_index": index,
                "page_index": line["page_index"],
                "line_text": line["text"],
            }
        )
    return markers


def build_segments(lines: list[dict[str, Any]], markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for offset, marker in enumerate(markers):
        end_index = markers[offset + 1]["start_index"] if offset + 1 < len(markers) else len(lines)
        segment_lines = lines[marker["start_index"] : end_index]
        text = "\n".join(line["text"] for line in segment_lines).strip()
        if len(text) < 200:
            continue
        segments.append(
            {
                "case_index": len(segments) + 1,
                "case_label": marker["label"],
                "marker_text": marker["line_text"],
                "start_page_index": segment_lines[0]["page_index"],
                "end_page_index": segment_lines[-1]["page_index"],
                "text": text,
            }
        )
    return segments


def shared_context_text(lines: list[dict[str, Any]], first_marker_index: int) -> str:
    prefix_lines = lines[:first_marker_index]
    if not prefix_lines:
        return ""
    context_lines = [line["text"] for line in prefix_lines[-24:]]
    return "\n".join(context_lines).strip()


def first_marker_is_first_case(markers: list[dict[str, Any]]) -> bool:
    if not markers:
        return False
    first_label = markers[0]["normalized_label"]
    return first_label in {
        "case 1",
        "patient 1",
        "case i",
        "patient i",
        "case a",
        "patient a",
        "first case",
        "first patient",
    }


def split_reason_for_qc_failure(proceedings_qc_row: dict[str, str], resolved_source: dict[str, str]) -> str:
    if (resolved_source.get("resolved_source_category") or "") != "conference_abstract":
        return ""
    status = (proceedings_qc_row.get("qc_status") or "").strip()
    if not status:
        return "Conference abstract case-series candidate has not yet been proceedings-QC checked."
    if status not in {"trimmed_match_confirmed", "trimmed_partial_match", "full_text_localised_untrimmed"}:
        return f"Conference abstract proceedings QC status '{status}' is not safe for auto-splitting."
    return ""


def registry_row(
    paper_id: str,
    resolved_source: dict[str, str],
    source_path: Path,
    split_path: Path | None,
    used_trimmed_text: bool,
    split_status: str,
    split_reason: str,
    segments: list[dict[str, Any]],
) -> dict[str, str]:
    return {
        "paper_id": paper_id,
        "resolved_source_category": resolved_source.get("resolved_source_category") or "",
        "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
        "resolved_source_route_source": resolved_source.get("resolved_source_route_source") or "",
        "source_text_json_path": relative_to_repo(source_path),
        "split_text_json_path": relative_to_repo(split_path),
        "used_trimmed_text": bool_text(used_trimmed_text),
        "split_status": split_status,
        "split_reason": split_reason,
        "split_method": "explicit_case_heading_segmentation" if split_status == "split_auto" else "",
        "case_count": str(len(segments)),
        "case_labels": " | ".join(segment["case_label"] for segment in segments),
        "start_page_indices": " | ".join(str(segment["start_page_index"]) for segment in segments),
        "end_page_indices": " | ".join(str(segment["end_page_index"]) for segment in segments),
        "manual_review_required": bool_text(split_status != "split_auto"),
        "split_at_utc": now_utc_iso() if split_status == "split_auto" else "",
    }


def write_registry(rows: list[dict[str, str]], path: Path) -> None:
    fieldnames = [
        "paper_id",
        "resolved_source_category",
        "resolved_source_subtype",
        "resolved_source_route_source",
        "source_text_json_path",
        "split_text_json_path",
        "used_trimmed_text",
        "split_status",
        "split_reason",
        "split_method",
        "case_count",
        "case_labels",
        "start_page_indices",
        "end_page_indices",
        "manual_review_required",
        "split_at_utc",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
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
    heuristic_rows = load_csv_rows_by_id(args.source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(args.source_manual_review_path, "paper_id")
    proceedings_qc_rows = load_csv_rows_by_id(args.proceedings_qc_path, "paper_id")
    rows: list[dict[str, str]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for paper_id in collect_candidate_ids(
        text_dir=args.text_dir,
        heuristic_rows=heuristic_rows,
        manual_rows=manual_rows,
        paper_ids=args.paper_id,
        limit=args.limit,
    ):
        resolved_source = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=heuristic_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
        )
        source_path = args.text_dir / f"{paper_id}.json"
        trimmed_path = args.trimmed_dir / f"{paper_id}.json"
        preferred_path = trimmed_path if trimmed_path.exists() else source_path
        split_path = args.output_dir / f"{paper_id}.json"

        qc_failure_reason = split_reason_for_qc_failure(
            proceedings_qc_row=proceedings_qc_rows.get(paper_id, {}),
            resolved_source=resolved_source,
        )
        if qc_failure_reason:
            if split_path.exists():
                split_path.unlink()
            rows.append(
                registry_row(
                    paper_id=paper_id,
                    resolved_source=resolved_source,
                    source_path=preferred_path,
                    split_path=None,
                    used_trimmed_text=trimmed_path.exists(),
                    split_status="manual_review_required",
                    split_reason=qc_failure_reason,
                    segments=[],
                )
            )
            continue

        if not preferred_path.exists():
            continue
        record = load_text_record(preferred_path)
        lines = flatten_lines(record)
        markers = unique_markers(lines)
        if len(markers) < 2:
            if split_path.exists():
                split_path.unlink()
            rows.append(
                registry_row(
                    paper_id=paper_id,
                    resolved_source=resolved_source,
                    source_path=preferred_path,
                    split_path=None,
                    used_trimmed_text=trimmed_path.exists(),
                    split_status="manual_review_required",
                    split_reason="Could not find at least two distinct explicit case/patient headings.",
                    segments=[],
                )
            )
            continue

        segments = build_segments(lines, markers)
        if not first_marker_is_first_case(markers):
            if split_path.exists():
                split_path.unlink()
            rows.append(
                registry_row(
                    paper_id=paper_id,
                    resolved_source=resolved_source,
                    source_path=preferred_path,
                    split_path=None,
                    used_trimmed_text=trimmed_path.exists(),
                    split_status="manual_review_required",
                    split_reason="Case headings do not begin with the first case, so the leading case block is not safely isolated.",
                    segments=[],
                )
            )
            continue
        if len(segments) < 2:
            if split_path.exists():
                split_path.unlink()
            rows.append(
                registry_row(
                    paper_id=paper_id,
                    resolved_source=resolved_source,
                    source_path=preferred_path,
                    split_path=None,
                    used_trimmed_text=trimmed_path.exists(),
                    split_status="manual_review_required",
                    split_reason="Case headings were found, but the segmented case blocks were too short or unstable.",
                    segments=[],
                )
            )
            continue

        split_payload = {
            "paper_id": paper_id,
            "source_filename": record.get("source_filename"),
            "source_sha256": record.get("source_sha256"),
            "source_text_json_path": relative_to_repo(preferred_path),
            "used_trimmed_text": trimmed_path.exists(),
            "resolved_source_category": resolved_source.get("resolved_source_category") or "",
            "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
            "split_status": "split_auto",
            "split_method": "explicit_case_heading_segmentation",
            "shared_context_text": shared_context_text(lines, markers[0]["start_index"]),
            "case_count": len(segments),
            "split_at_utc": now_utc_iso(),
            "cases": segments,
        }
        split_path.write_text(json.dumps(split_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(
            registry_row(
                paper_id=paper_id,
                resolved_source=resolved_source,
                source_path=preferred_path,
                split_path=split_path,
                used_trimmed_text=trimmed_path.exists(),
                split_status="split_auto",
                split_reason="Explicit case/patient headings supported a stable case-level split.",
                segments=segments,
            )
        )

    write_registry(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
