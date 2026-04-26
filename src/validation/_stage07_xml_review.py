from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE07_XML_ROOT = REPO_ROOT / "data" / "extraction_json" / "stage07_xml"
STAGE07_XML_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "stage07_xml_registry.csv"
GOLD_STANDARD_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_xml" / "gold_standard"
GOLD_MASTER_PATH = GOLD_STANDARD_ROOT / "07_xml_assignment_gold_standard.csv"
RESPONSES_FILENAME = "review_responses.csv"
QUEUE_FILENAME = "review_queue.csv"


TARGET_PALETTE = [
    ("#0072B2", "#D9ECF7", "#073B4C"),
    ("#D55E00", "#FCE6D6", "#5A2500"),
    ("#009E73", "#D8F0E8", "#063D2E"),
    ("#CC79A7", "#F6E2EE", "#4D1735"),
    ("#E69F00", "#FFF0C7", "#513900"),
    ("#56B4E9", "#E1F3FB", "#12445E"),
    ("#7A3E9D", "#EEE4F4", "#321345"),
    ("#6C6C6C", "#ECECEC", "#242424"),
]


QUEUE_FIELDNAMES = [
    "round_id",
    "row_type",
    "paper_id",
    "paper_title",
    "stage07_schema_version",
    "source_text_sha256",
    "prepared_source_sha256",
    "route_mode",
    "annotation_mode",
    "validation_status",
    "roundtrip_status",
    "manual_review_required",
    "manual_review_reasons",
    "segment_id",
    "logical_segment_id",
    "source_block_id",
    "source_start",
    "source_end",
    "predicted_targets",
    "predicted_target_labels",
    "predicted_role",
    "predicted_confidence",
    "predicted_evidence",
    "segment_text",
    "segment_text_sha256",
    "paper_issue_prompt",
    "paper_json_path",
    "segments_json_path",
    "annotated_text_path",
    "validation_json_path",
    "paper_html_path",
    "generated_at_utc",
]

REVIEW_FIELDNAMES = [
    "prediction_correct",
    "review_status",
    "reviewed_targets",
    "reviewed_role",
    "paper_level_issue",
    "reviewer_notes",
    "reviewer_id",
    "reviewed_at_utc",
]

RESPONSE_FIELDNAMES = QUEUE_FIELDNAMES + REVIEW_FIELDNAMES
GOLD_FIELDNAMES = RESPONSE_FIELDNAMES + ["gold_updated_at_utc"]


@dataclass(frozen=True)
class ReviewPaths:
    round_dir: Path
    papers_dir: Path
    index_html_path: Path
    queue_path: Path
    responses_path: Path
    gold_master_path: Path


@dataclass(frozen=True)
class ReviewItem:
    paper_id: str
    registry_row: dict[str, str]
    paper_payload: dict[str, Any]
    segments_payload: dict[str, Any]
    validation_payload: dict[str, Any]
    annotated_text: str
    paper_json_path: Path
    segments_json_path: Path
    annotated_text_path: Path
    validation_json_path: Path


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def resolve_repo_path(value: str | Path | None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_stage07_tags(annotated_text: str) -> str:
    return re.sub(r"</?seg\b[^>]*>", "", annotated_text)


def sort_key_for_paper_id(paper_id: str) -> tuple[int, int | str]:
    text = str(paper_id or "").strip()
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def html_escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def first_present(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text:
            return text
    return ""


def target_colour_assignments(entities: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    assignments: dict[str, dict[str, str]] = {}
    for index, entity in enumerate(entities):
        target_id = str(entity.get("id") or entity.get("target_id") or "").strip()
        if not target_id:
            continue
        border, background, text_colour = TARGET_PALETTE[index % len(TARGET_PALETTE)]
        assignments[target_id] = {
            "border": border,
            "background": background,
            "text": text_colour,
            "index": str(index + 1),
        }
    return assignments


def next_round_id(root: Path = GOLD_STANDARD_ROOT, today: date | None = None) -> str:
    day = today or date.today()
    prefix = f"{day.isoformat()}_round_"
    existing = [
        int(path.name.removeprefix(prefix))
        for path in root.glob(f"{prefix}*")
        if path.is_dir() and path.name.removeprefix(prefix).isdigit()
    ]
    return f"{prefix}{max(existing, default=0) + 1:02d}"


def review_paths(round_id: str, gold_root: Path = GOLD_STANDARD_ROOT) -> ReviewPaths:
    round_dir = gold_root / round_id
    return ReviewPaths(
        round_dir=round_dir,
        papers_dir=round_dir / "papers",
        index_html_path=round_dir / "index.html",
        queue_path=round_dir / QUEUE_FILENAME,
        responses_path=round_dir / RESPONSES_FILENAME,
        gold_master_path=gold_root / GOLD_MASTER_PATH.name,
    )


def registry_rows_or_discovered(
    *,
    stage07_root: Path,
    registry_path: Path,
) -> list[dict[str, str]]:
    rows = load_csv_rows(registry_path)
    if rows:
        return rows
    discovered: list[dict[str, str]] = []
    for paper_json_path in sorted((stage07_root / "papers").glob("*.json")):
        paper_id = paper_json_path.stem
        discovered.append(
            {
                "paper_id": paper_id,
                "paper_json_path": display_path(paper_json_path),
                "segments_json_path": display_path(stage07_root / "segments" / f"{paper_id}.segments.json"),
                "annotated_text_path": display_path(stage07_root / "annotated_text" / f"{paper_id}.annotated.txt"),
                "validation_json_path": display_path(stage07_root / "validation" / f"{paper_id}.validation.json"),
            }
        )
    return discovered


def default_output_path(stage07_root: Path, paper_id: str, kind: str) -> Path:
    if kind == "paper":
        return stage07_root / "papers" / f"{paper_id}.json"
    if kind == "segments":
        return stage07_root / "segments" / f"{paper_id}.segments.json"
    if kind == "annotated_text":
        return stage07_root / "annotated_text" / f"{paper_id}.annotated.txt"
    if kind == "validation":
        return stage07_root / "validation" / f"{paper_id}.validation.json"
    raise ValueError(f"Unknown Stage 07 XML output kind: {kind}")


def load_review_items(
    *,
    stage07_root: Path = STAGE07_XML_ROOT,
    registry_path: Path = STAGE07_XML_REGISTRY_PATH,
    paper_ids: set[str] | None = None,
) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    for row in registry_rows_or_discovered(stage07_root=stage07_root, registry_path=registry_path):
        paper_id = str(row.get("paper_id") or "").strip()
        if not paper_id or (paper_ids is not None and paper_id not in paper_ids):
            continue
        paper_json_path = resolve_repo_path(row.get("paper_json_path")) or default_output_path(stage07_root, paper_id, "paper")
        segments_json_path = resolve_repo_path(row.get("segments_json_path")) or default_output_path(stage07_root, paper_id, "segments")
        annotated_text_path = resolve_repo_path(row.get("annotated_text_path")) or default_output_path(stage07_root, paper_id, "annotated_text")
        validation_json_path = resolve_repo_path(row.get("validation_json_path")) or default_output_path(stage07_root, paper_id, "validation")
        if not paper_json_path.exists():
            continue
        items.append(
            ReviewItem(
                paper_id=paper_id,
                registry_row=dict(row),
                paper_payload=load_json_if_exists(paper_json_path),
                segments_payload=load_json_if_exists(segments_json_path),
                validation_payload=load_json_if_exists(validation_json_path),
                annotated_text=annotated_text_path.read_text(encoding="utf-8") if annotated_text_path.exists() else "",
                paper_json_path=paper_json_path,
                segments_json_path=segments_json_path,
                annotated_text_path=annotated_text_path,
                validation_json_path=validation_json_path,
            )
        )
    return sorted(items, key=lambda item: sort_key_for_paper_id(item.paper_id))


def entities_for_item(item: ReviewItem) -> list[dict[str, Any]]:
    entities = item.segments_payload.get("entities") or item.paper_payload.get("entities") or []
    return [dict(entity) for entity in entities if str(entity.get("id") or entity.get("target_id") or "").strip()]


def target_label_lookup(entities: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for entity in entities:
        target_id = str(entity.get("id") or entity.get("target_id") or "").strip()
        label = str(entity.get("label") or entity.get("target_label") or target_id).strip()
        if target_id:
            labels[target_id] = label
    return labels


def source_text_for_item(item: ReviewItem) -> str:
    if item.annotated_text:
        return strip_stage07_tags(item.annotated_text)
    blocks = sorted(
        item.segments_payload.get("source_blocks") or [],
        key=lambda block: int((block.get("source_offsets") or {}).get("start") or 0),
    )
    pieces: list[str] = []
    cursor = 0
    for block in blocks:
        offsets = block.get("source_offsets") or {}
        start = int(offsets.get("start") or cursor)
        end = int(offsets.get("end") or start + len(str(block.get("text") or "")))
        if start > cursor:
            pieces.append("\n" * (start - cursor))
        text = str(block.get("text") or "")
        pieces.append(text)
        cursor = max(end, start + len(text))
    return "".join(pieces)


def manual_review_reasons(item: ReviewItem) -> list[str]:
    reasons = item.paper_payload.get("manual_review", {}).get("reasons") or []
    if not reasons:
        raw = str(item.registry_row.get("manual_review_reasons") or "")
        reasons = [part for part in raw.split("|") if part]
    return [str(reason) for reason in reasons]


def rejected_spans_for_item(item: ReviewItem) -> list[dict[str, Any]]:
    validation_sources = [
        item.validation_payload,
        item.segments_payload.get("validation") or {},
    ]
    for validation in validation_sources:
        spans = validation.get("rejected_spans") or []
        if spans:
            return [dict(span) for span in spans]
    return []


def span_adjustments_for_item(item: ReviewItem) -> list[dict[str, Any]]:
    validation_sources = [
        item.validation_payload,
        item.segments_payload.get("validation") or {},
    ]
    for validation in validation_sources:
        adjustments = validation.get("span_adjustments") or []
        if adjustments:
            return [dict(adjustment) for adjustment in adjustments]
    return []


def paper_title(item: ReviewItem) -> str:
    return str(item.paper_payload.get("title") or item.registry_row.get("title") or "").strip()


def chip_html(target_id: str, labels: dict[str, str], colours: dict[str, dict[str, str]]) -> str:
    colour = colours.get(target_id, {"border": "#666666", "background": "#eeeeee", "text": "#222222", "index": "?"})
    label = labels.get(target_id, target_id)
    style = (
        f"--chip-border:{colour['border']};"
        f"--chip-bg:{colour['background']};"
        f"--chip-text:{colour['text']};"
    )
    return (
        f'<span class="target-chip" style="{style}">'
        f'<span class="target-chip-id">{html_escape(target_id)}</span>'
        f"{html_escape(label)}</span>"
    )


def chips_html(target_ids: list[str], labels: dict[str, str], colours: dict[str, dict[str, str]]) -> str:
    return "".join(chip_html(target_id, labels, colours) for target_id in target_ids)


def segment_style(segment: dict[str, Any], colours: dict[str, dict[str, str]]) -> str:
    role = str(segment.get("role") or "").strip()
    targets = [str(target) for target in segment.get("targets") or []]
    if role in {"shared", "background"} or len(targets) > 1:
        return "--seg-bg:#fff8dc;--seg-border:#6b7280;--seg-text:#1f2937;"
    if role == "uncertain" or "unknown" in targets:
        return "--seg-bg:#f1f5f9;--seg-border:#64748b;--seg-text:#334155;"
    if targets:
        colour = colours.get(targets[0])
        if colour:
            return (
                f"--seg-bg:{colour['background']};"
                f"--seg-border:{colour['border']};"
                f"--seg-text:{colour['text']};"
            )
    return "--seg-bg:#eef2ff;--seg-border:#4f46e5;--seg-text:#312e81;"


def render_source_html(
    source_text: str,
    segments: list[dict[str, Any]],
    labels: dict[str, str],
    colours: dict[str, dict[str, str]],
) -> str:
    ordered = sorted(
        segments,
        key=lambda segment: int((segment.get("source_offsets") or {}).get("start") or 0),
    )
    cursor = 0
    parts: list[str] = []
    for segment in ordered:
        offsets = segment.get("source_offsets") or {}
        start = max(0, int(offsets.get("start") or 0))
        end = max(start, int(offsets.get("end") or start))
        if start < cursor:
            continue
        parts.append(html_escape(source_text[cursor:start]))
        targets = [str(target) for target in segment.get("targets") or []]
        target_label = " ".join(targets) if targets else "unassigned"
        role = str(segment.get("role") or "").strip()
        source_slice = source_text[start:end] if end <= len(source_text) else str(segment.get("text") or "")
        parts.append(
            '<span class="source-segment '
            f'role-{html_escape(role)}" '
            f'id="src-{html_escape(str(segment.get("segment_id") or ""))}" '
            f'data-segment="{html_escape(str(segment.get("segment_id") or ""))}" '
            f'data-label="{html_escape(target_label)} {html_escape(role)}" '
            f'style="{segment_style(segment, colours)}">'
            f"{html_escape(source_slice)}</span>"
        )
        cursor = end
    parts.append(html_escape(source_text[cursor:]))
    return "".join(parts)


def text_preview(value: str, limit: int = 220) -> str:
    normalised = " ".join(str(value or "").split())
    if len(normalised) <= limit:
        return normalised
    return normalised[: limit - 3].rstrip() + "..."


def render_segment_table(
    segments: list[dict[str, Any]],
    labels: dict[str, str],
    colours: dict[str, dict[str, str]],
) -> str:
    rows: list[str] = []
    for segment in sorted(segments, key=lambda item: int((item.get("source_offsets") or {}).get("start") or 0)):
        offsets = segment.get("source_offsets") or {}
        targets = [str(target) for target in segment.get("targets") or []]
        rows.append(
            "<tr>"
            f'<td><a href="#src-{html_escape(segment.get("segment_id"))}">{html_escape(segment.get("segment_id"))}</a></td>'
            f"<td>{html_escape(segment.get('logical_segment_id'))}</td>"
            f"<td>{html_escape(segment.get('role'))}</td>"
            f"<td>{chips_html(targets, labels, colours)}</td>"
            f"<td>{html_escape(offsets.get('start'))}-{html_escape(offsets.get('end'))}</td>"
            f"<td>{html_escape(segment.get('confidence'))}</td>"
            f"<td>{html_escape(text_preview(str(segment.get('evidence') or ''), 120))}</td>"
            f"<td>{html_escape(text_preview(str(segment.get('text') or ''), 180))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="8">No predicted segments were generated for this paper.</td></tr>')
    return (
        '<table class="segment-table">'
        "<thead><tr>"
        "<th>Segment</th><th>Group</th><th>Role</th><th>Targets</th>"
        "<th>Offsets</th><th>Confidence</th><th>Evidence</th><th>Text</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_rejected_span_table(
    rejected_spans: list[dict[str, Any]],
    labels: dict[str, str],
    colours: dict[str, dict[str, str]],
) -> str:
    if not rejected_spans:
        return ""
    rows: list[str] = []
    for span in rejected_spans:
        requested = span.get("requested_offsets") or {}
        source_offsets = span.get("source_offsets") or {}
        targets = [str(target) for target in span.get("targets") or []]
        rows.append(
            "<tr>"
            f"<td>{html_escape(span.get('rejected_segment_id'))}</td>"
            f"<td>{html_escape(span.get('logical_segment_id'))}</td>"
            f"<td>{html_escape(span.get('role'))}</td>"
            f"<td>{chips_html(targets, labels, colours)}</td>"
            f"<td>{html_escape(span.get('source_block_id'))}</td>"
            f"<td>{html_escape(requested.get('start'))}-{html_escape(requested.get('end'))}</td>"
            f"<td>{html_escape(source_offsets.get('start'))}-{html_escape(source_offsets.get('end'))}</td>"
            f"<td>{html_escape(span.get('reason'))}</td>"
            f"<td>{html_escape(text_preview(str(span.get('selected_text') or ''), 180))}</td>"
            "</tr>"
        )
    return (
        '<table class="segment-table rejected-table">'
        "<thead><tr>"
        "<th>Rejected</th><th>Group</th><th>Role</th><th>Targets</th>"
        "<th>Block</th><th>Requested Offsets</th><th>Requested Source Offsets</th><th>Reason</th><th>Selected Text</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_span_adjustment_table(span_adjustments: list[dict[str, Any]]) -> str:
    if not span_adjustments:
        return ""
    rows: list[str] = []
    for adjustment in span_adjustments:
        requested = adjustment.get("requested_offsets") or {}
        relocated = adjustment.get("relocated_offsets") or {}
        rows.append(
            "<tr>"
            f"<td>{html_escape(adjustment.get('logical_segment_id'))}</td>"
            f"<td>{html_escape(adjustment.get('source_block_id'))}</td>"
            f"<td>{html_escape(requested.get('start'))}-{html_escape(requested.get('end'))}</td>"
            f"<td>{html_escape(relocated.get('start'))}-{html_escape(relocated.get('end'))}</td>"
            f"<td>{html_escape(adjustment.get('selected_text_sha256'))}</td>"
            "</tr>"
        )
    return (
        '<table class="segment-table">'
        "<thead><tr>"
        "<th>Group</th><th>Block</th><th>Requested Offsets</th><th>Relocated Offsets</th><th>Selected Text SHA256</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def render_target_summary(
    entities: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    labels: dict[str, str],
    colours: dict[str, dict[str, str]],
) -> str:
    blocks: list[str] = []
    for entity in entities:
        target_id = str(entity.get("id") or entity.get("target_id") or "").strip()
        if not target_id:
            continue
        related = [
            str(segment.get("segment_id") or "")
            for segment in segments
            if target_id in [str(target) for target in segment.get("targets") or []]
        ]
        related_text = ", ".join(related) if related else "No assigned segment"
        kind = str(entity.get("kind") or entity.get("target_kind") or "").strip()
        blocks.append(
            '<div class="target-summary">'
            f"{chip_html(target_id, labels, colours)}"
            f'<span class="target-kind">{html_escape(kind)}</span>'
            f'<span class="target-related">{html_escape(related_text)}</span>'
            "</div>"
        )
    return "".join(blocks) or '<p class="muted">No declared patients or groups.</p>'


def html_document(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html_escape(title)}</title>\n"
        "<style>\n"
        + STYLE_CSS
        + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        + body
        + "\n</body>\n</html>\n"
    )


STYLE_CSS = """
:root {
  color-scheme: light;
  font-family: Arial, Helvetica, sans-serif;
  background: #f7f8fa;
  color: #1f2937;
}
body {
  margin: 0;
}
main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}
h1, h2 {
  letter-spacing: 0;
}
h1 {
  font-size: 28px;
  margin: 0 0 8px;
}
h2 {
  font-size: 18px;
  margin-top: 28px;
}
.meta, .muted {
  color: #53606f;
}
.top-links {
  margin-bottom: 18px;
}
.status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 20px;
}
.badge {
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 4px 8px;
  background: #ffffff;
  font-size: 13px;
}
.badge.warn {
  border-color: #d97706;
  background: #fff7ed;
  color: #7c2d12;
}
.target-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin: 2px 4px 2px 0;
  padding: 2px 7px;
  border-left: 5px solid var(--chip-border);
  background: var(--chip-bg);
  color: var(--chip-text);
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}
.target-chip-id {
  font-weight: 700;
}
.source-text {
  white-space: pre-wrap;
  line-height: 1.65;
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  padding: 18px;
  overflow-x: auto;
}
.source-segment {
  position: relative;
  padding: 2px 3px;
  margin: 0 1px;
  background: var(--seg-bg);
  color: var(--seg-text);
  border-bottom: 3px solid var(--seg-border);
  border-radius: 3px;
}
.source-segment::before {
  content: attr(data-label);
  font-size: 10px;
  font-weight: 700;
  background: #ffffff;
  border: 1px solid var(--seg-border);
  color: var(--seg-text);
  border-radius: 3px;
  padding: 0 3px;
  margin-right: 4px;
}
.role-shared,
.role-background {
  outline: 1px dashed #6b7280;
}
.role-uncertain {
  outline: 1px dotted #475569;
}
.segment-table,
.index-table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  border: 1px solid #d8dee8;
}
th, td {
  border-bottom: 1px solid #e5e7eb;
  padding: 8px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}
th {
  background: #eef2f7;
}
.warning-list {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 6px;
  padding: 12px 18px;
}
.rejected-table {
  border-color: #fecaca;
}
.rejected-table th {
  background: #fff1f2;
}
.target-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
}
.target-kind {
  color: #53606f;
  min-width: 70px;
}
.target-related {
  font-size: 13px;
}
a {
  color: #0f5f95;
}
"""


def render_paper_html(item: ReviewItem, paper_html_path: Path) -> str:
    entities = entities_for_item(item)
    labels = target_label_lookup(entities)
    colours = target_colour_assignments(entities)
    segments = [dict(segment) for segment in item.segments_payload.get("segments") or []]
    rejected_spans = rejected_spans_for_item(item)
    span_adjustments = span_adjustments_for_item(item)
    source_text = source_text_for_item(item)
    reasons = manual_review_reasons(item)
    warning_html = ""
    if reasons:
        warning_html = (
            "<h2>Validation Warnings</h2>"
            '<ul class="warning-list">'
            + "".join(f"<li>{html_escape(reason)}</li>" for reason in reasons)
            + "</ul>"
        )
    span_adjustment_html = render_span_adjustment_table(span_adjustments)
    if not span_adjustment_html:
        span_adjustment_html = '<p class="muted">No span relocations were applied.</p>'
    rejected_span_html = render_rejected_span_table(rejected_spans, labels, colours)
    if not rejected_span_html:
        rejected_span_html = '<p class="muted">No rejected span proposals.</p>'
    body = (
        "<main>"
        '<p class="top-links"><a href="../index.html">Back to index</a></p>'
        f"<h1>Paper {html_escape(item.paper_id)}</h1>"
        f'<p class="meta">{html_escape(paper_title(item))}</p>'
        '<div class="status-row">'
        f'<span class="badge">Route: {html_escape(first_present(item.paper_payload.get("source_route", {}).get("resolved_langextract_mode"), item.registry_row.get("route_mode")))}</span>'
        f'<span class="badge">Validation: {html_escape(first_present(item.paper_payload.get("annotation", {}).get("validation_status"), item.registry_row.get("validation_status")))}</span>'
        f'<span class="badge">Round-trip: {html_escape(first_present(item.paper_payload.get("annotation", {}).get("roundtrip_status"), item.registry_row.get("roundtrip_status")))}</span>'
        f'<span class="badge warn">Manual review: {html_escape(first_present(item.paper_payload.get("manual_review", {}).get("manual_review_required"), item.registry_row.get("manual_review_required")))}</span>'
        "</div>"
        f"{warning_html}"
        "<h2>Targets</h2>"
        f"{render_target_summary(entities, segments, labels, colours)}"
        "<h2>Source Text</h2>"
        f'<div class="source-text">{render_source_html(source_text, segments, labels, colours)}</div>'
        "<h2>Segments</h2>"
        f"{render_segment_table(segments, labels, colours)}"
        "<h2>Relocated Spans</h2>"
        f"{span_adjustment_html}"
        "<h2>Rejected Proposals</h2>"
        f"{rejected_span_html}"
        "<h2>Artefacts</h2>"
        "<p class=\"meta\">"
        f"Paper JSON: {html_escape(display_path(item.paper_json_path))}<br>"
        f"Segments JSON: {html_escape(display_path(item.segments_json_path))}<br>"
        f"Annotated text: {html_escape(display_path(item.annotated_text_path))}<br>"
        f"Validation JSON: {html_escape(display_path(item.validation_json_path))}"
        "</p>"
        "</main>"
    )
    return html_document(f"Stage 07 XML Review {item.paper_id}", body)


def normalise_targets(targets: Any) -> list[str]:
    return [str(target).strip() for target in targets or [] if str(target).strip()]


def queue_row_for_segment(
    *,
    round_id: str,
    item: ReviewItem,
    segment: dict[str, Any],
    labels: dict[str, str],
    paper_html_path: Path,
    generated_at_utc: str,
) -> dict[str, str]:
    targets = normalise_targets(segment.get("targets"))
    offsets = segment.get("source_offsets") or {}
    source = item.segments_payload.get("source") or item.paper_payload.get("source") or {}
    target_labels = " | ".join(labels.get(target_id, target_id) for target_id in targets)
    segment_text = str(segment.get("text") or "")
    return {
        "round_id": round_id,
        "row_type": "segment",
        "paper_id": item.paper_id,
        "paper_title": paper_title(item),
        "stage07_schema_version": str(item.paper_payload.get("stage07_schema_version") or ""),
        "source_text_sha256": str(source.get("source_text_sha256") or ""),
        "prepared_source_sha256": str(source.get("prepared_source_sha256") or ""),
        "route_mode": first_present(item.paper_payload.get("source_route", {}).get("resolved_langextract_mode"), item.registry_row.get("route_mode")),
        "annotation_mode": first_present(item.paper_payload.get("annotation", {}).get("annotation_mode"), item.registry_row.get("annotation_mode")),
        "validation_status": first_present(item.paper_payload.get("annotation", {}).get("validation_status"), item.registry_row.get("validation_status")),
        "roundtrip_status": first_present(item.paper_payload.get("annotation", {}).get("roundtrip_status"), item.registry_row.get("roundtrip_status")),
        "manual_review_required": first_present(item.paper_payload.get("manual_review", {}).get("manual_review_required"), item.registry_row.get("manual_review_required")),
        "manual_review_reasons": " | ".join(manual_review_reasons(item)),
        "segment_id": str(segment.get("segment_id") or ""),
        "logical_segment_id": str(segment.get("logical_segment_id") or ""),
        "source_block_id": str(segment.get("source_block_id") or ""),
        "source_start": csv_value(offsets.get("start")),
        "source_end": csv_value(offsets.get("end")),
        "predicted_targets": " ".join(targets),
        "predicted_target_labels": target_labels,
        "predicted_role": str(segment.get("role") or ""),
        "predicted_confidence": str(segment.get("confidence") or ""),
        "predicted_evidence": str(segment.get("evidence") or ""),
        "segment_text": segment_text,
        "segment_text_sha256": sha256_text(segment_text),
        "paper_issue_prompt": "",
        "paper_json_path": display_path(item.paper_json_path),
        "segments_json_path": display_path(item.segments_json_path),
        "annotated_text_path": display_path(item.annotated_text_path),
        "validation_json_path": display_path(item.validation_json_path),
        "paper_html_path": display_path(paper_html_path),
        "generated_at_utc": generated_at_utc,
    }


def queue_row_for_rejected_span(
    *,
    round_id: str,
    item: ReviewItem,
    rejected_span: dict[str, Any],
    labels: dict[str, str],
    paper_html_path: Path,
    generated_at_utc: str,
) -> dict[str, str]:
    targets = normalise_targets(rejected_span.get("targets"))
    offsets = rejected_span.get("source_offsets") or {}
    source = item.segments_payload.get("source") or item.paper_payload.get("source") or {}
    target_labels = " | ".join(labels.get(target_id, target_id) for target_id in targets)
    segment_text = str(rejected_span.get("selected_text") or "")
    return {
        "round_id": round_id,
        "row_type": "rejected_segment",
        "paper_id": item.paper_id,
        "paper_title": paper_title(item),
        "stage07_schema_version": str(item.paper_payload.get("stage07_schema_version") or ""),
        "source_text_sha256": str(source.get("source_text_sha256") or ""),
        "prepared_source_sha256": str(source.get("prepared_source_sha256") or ""),
        "route_mode": first_present(item.paper_payload.get("source_route", {}).get("resolved_langextract_mode"), item.registry_row.get("route_mode")),
        "annotation_mode": first_present(item.paper_payload.get("annotation", {}).get("annotation_mode"), item.registry_row.get("annotation_mode")),
        "validation_status": first_present(item.paper_payload.get("annotation", {}).get("validation_status"), item.registry_row.get("validation_status")),
        "roundtrip_status": first_present(item.paper_payload.get("annotation", {}).get("roundtrip_status"), item.registry_row.get("roundtrip_status")),
        "manual_review_required": first_present(item.paper_payload.get("manual_review", {}).get("manual_review_required"), item.registry_row.get("manual_review_required")),
        "manual_review_reasons": " | ".join(manual_review_reasons(item)),
        "segment_id": str(rejected_span.get("rejected_segment_id") or ""),
        "logical_segment_id": str(rejected_span.get("logical_segment_id") or ""),
        "source_block_id": str(rejected_span.get("source_block_id") or ""),
        "source_start": csv_value(offsets.get("start")),
        "source_end": csv_value(offsets.get("end")),
        "predicted_targets": " ".join(targets),
        "predicted_target_labels": target_labels,
        "predicted_role": str(rejected_span.get("role") or ""),
        "predicted_confidence": str(rejected_span.get("confidence") or ""),
        "predicted_evidence": str(rejected_span.get("evidence") or ""),
        "segment_text": segment_text,
        "segment_text_sha256": sha256_text(segment_text),
        "paper_issue_prompt": f"Rejected proposal: {rejected_span.get('reason') or ''}",
        "paper_json_path": display_path(item.paper_json_path),
        "segments_json_path": display_path(item.segments_json_path),
        "annotated_text_path": display_path(item.annotated_text_path),
        "validation_json_path": display_path(item.validation_json_path),
        "paper_html_path": display_path(paper_html_path),
        "generated_at_utc": generated_at_utc,
    }


def paper_issue_queue_row(
    *,
    round_id: str,
    item: ReviewItem,
    paper_html_path: Path,
    generated_at_utc: str,
) -> dict[str, str]:
    source = item.segments_payload.get("source") or item.paper_payload.get("source") or {}
    return {
        "round_id": round_id,
        "row_type": "paper",
        "paper_id": item.paper_id,
        "paper_title": paper_title(item),
        "stage07_schema_version": str(item.paper_payload.get("stage07_schema_version") or ""),
        "source_text_sha256": str(source.get("source_text_sha256") or ""),
        "prepared_source_sha256": str(source.get("prepared_source_sha256") or ""),
        "route_mode": first_present(item.paper_payload.get("source_route", {}).get("resolved_langextract_mode"), item.registry_row.get("route_mode")),
        "annotation_mode": first_present(item.paper_payload.get("annotation", {}).get("annotation_mode"), item.registry_row.get("annotation_mode")),
        "validation_status": first_present(item.paper_payload.get("annotation", {}).get("validation_status"), item.registry_row.get("validation_status")),
        "roundtrip_status": first_present(item.paper_payload.get("annotation", {}).get("roundtrip_status"), item.registry_row.get("roundtrip_status")),
        "manual_review_required": first_present(item.paper_payload.get("manual_review", {}).get("manual_review_required"), item.registry_row.get("manual_review_required")),
        "manual_review_reasons": " | ".join(manual_review_reasons(item)),
        "segment_id": "__paper__",
        "logical_segment_id": "__paper__",
        "source_block_id": "",
        "source_start": "",
        "source_end": "",
        "predicted_targets": "",
        "predicted_target_labels": "",
        "predicted_role": "",
        "predicted_confidence": "",
        "predicted_evidence": "",
        "segment_text": "",
        "segment_text_sha256": "",
        "paper_issue_prompt": "Record missing assignments, global concerns, or target-inventory corrections for this paper.",
        "paper_json_path": display_path(item.paper_json_path),
        "segments_json_path": display_path(item.segments_json_path),
        "annotated_text_path": display_path(item.annotated_text_path),
        "validation_json_path": display_path(item.validation_json_path),
        "paper_html_path": display_path(paper_html_path),
        "generated_at_utc": generated_at_utc,
    }


def response_row_from_queue(row: dict[str, str]) -> dict[str, str]:
    response = {fieldname: str(row.get(fieldname) or "") for fieldname in QUEUE_FIELDNAMES}
    if row.get("row_type") in {"segment", "rejected_segment"}:
        response["reviewed_targets"] = str(row.get("predicted_targets") or "")
        response["reviewed_role"] = str(row.get("predicted_role") or "")
    else:
        response["reviewed_targets"] = ""
        response["reviewed_role"] = ""
    response.update(
        {
            "prediction_correct": "",
            "review_status": "",
            "paper_level_issue": "",
            "reviewer_notes": "",
            "reviewer_id": "",
            "reviewed_at_utc": "",
        }
    )
    return response


def build_queue_rows(
    *,
    round_id: str,
    items: list[ReviewItem],
    paths: ReviewPaths,
    generated_at_utc: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        paper_html_path = paths.papers_dir / f"{item.paper_id}.html"
        entities = entities_for_item(item)
        labels = target_label_lookup(entities)
        segments = [dict(segment) for segment in item.segments_payload.get("segments") or []]
        rejected_spans = rejected_spans_for_item(item)
        for segment in segments:
            rows.append(
                queue_row_for_segment(
                    round_id=round_id,
                    item=item,
                    segment=segment,
                    labels=labels,
                    paper_html_path=paper_html_path,
                    generated_at_utc=generated_at_utc,
                )
            )
        for rejected_span in rejected_spans:
            rows.append(
                queue_row_for_rejected_span(
                    round_id=round_id,
                    item=item,
                    rejected_span=rejected_span,
                    labels=labels,
                    paper_html_path=paper_html_path,
                    generated_at_utc=generated_at_utc,
                )
            )
        if not segments or manual_review_reasons(item):
            rows.append(
                paper_issue_queue_row(
                    round_id=round_id,
                    item=item,
                    paper_html_path=paper_html_path,
                    generated_at_utc=generated_at_utc,
                )
            )
    return rows


def render_index_html(round_id: str, items: list[ReviewItem], paths: ReviewPaths) -> str:
    rows: list[str] = []
    for item in items:
        segments = item.segments_payload.get("segments") or []
        entities = entities_for_item(item)
        reasons = manual_review_reasons(item)
        paper_path = paths.papers_dir / f"{item.paper_id}.html"
        rows.append(
            "<tr>"
            f'<td><a href="papers/{html_escape(paper_path.name)}">{html_escape(item.paper_id)}</a></td>'
            f"<td>{html_escape(paper_title(item))}</td>"
            f"<td>{html_escape(first_present(item.paper_payload.get('source_route', {}).get('resolved_langextract_mode'), item.registry_row.get('route_mode')))}</td>"
            f"<td>{len(entities)}</td>"
            f"<td>{len(segments)}</td>"
            f"<td>{html_escape(first_present(item.paper_payload.get('manual_review', {}).get('manual_review_required'), item.registry_row.get('manual_review_required')))}</td>"
            f"<td>{html_escape(' | '.join(reasons))}</td>"
            "</tr>"
        )
    body = (
        "<main>"
        f"<h1>Stage 07 XML Review Pack: {html_escape(round_id)}</h1>"
        '<p class="meta">Static verification pack for patient/group assignment before LangExtract.</p>'
        '<div class="status-row">'
        f'<span class="badge">Papers: {len(items)}</span>'
        f'<span class="badge">Review queue: {html_escape(display_path(paths.queue_path))}</span>'
        f'<span class="badge">Responses: {html_escape(display_path(paths.responses_path))}</span>'
        f'<span class="badge">Gold ledger: {html_escape(display_path(paths.gold_master_path))}</span>'
        "</div>"
        '<table class="index-table">'
        "<thead><tr><th>Paper</th><th>Title</th><th>Route</th><th>Targets</th><th>Segments</th><th>Manual Review</th><th>Reasons</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
        "</main>"
    )
    return html_document(f"Stage 07 XML Review Pack {round_id}", body)


def build_review_pack(
    *,
    round_id: str | None = None,
    stage07_root: Path = STAGE07_XML_ROOT,
    registry_path: Path = STAGE07_XML_REGISTRY_PATH,
    gold_root: Path = GOLD_STANDARD_ROOT,
    paper_ids: set[str] | None = None,
    force: bool = False,
) -> dict[str, str]:
    resolved_round_id = round_id or next_round_id(gold_root)
    paths = review_paths(resolved_round_id, gold_root)
    if paths.round_dir.exists() and not force:
        raise FileExistsError(f"Review round already exists: {display_path(paths.round_dir)}")

    items = load_review_items(stage07_root=stage07_root, registry_path=registry_path, paper_ids=paper_ids)
    if not items:
        raise ValueError("No Stage 07 XML outputs were found for the requested review pack.")

    paths.papers_dir.mkdir(parents=True, exist_ok=True)
    for item in items:
        paper_html_path = paths.papers_dir / f"{item.paper_id}.html"
        paper_html_path.write_text(render_paper_html(item, paper_html_path), encoding="utf-8")

    paths.index_html_path.write_text(render_index_html(resolved_round_id, items, paths), encoding="utf-8")
    generated_at_utc = now_utc_iso()
    queue_rows = build_queue_rows(
        round_id=resolved_round_id,
        items=items,
        paths=paths,
        generated_at_utc=generated_at_utc,
    )
    write_csv_rows(paths.queue_path, queue_rows, QUEUE_FIELDNAMES)
    write_csv_rows(paths.responses_path, [response_row_from_queue(row) for row in queue_rows], RESPONSE_FIELDNAMES)
    gold_path = refresh_gold_standard(gold_root=gold_root)
    return {
        "round_id": resolved_round_id,
        "index_html_path": display_path(paths.index_html_path),
        "review_queue_path": display_path(paths.queue_path),
        "review_responses_path": display_path(paths.responses_path),
        "gold_master_path": display_path(gold_path),
        "paper_count": str(len(items)),
        "review_row_count": str(len(queue_rows)),
    }


def response_sort_key(row: dict[str, str]) -> tuple[tuple[int, int | str], str, str, int, str]:
    source_start = str(row.get("source_start") or "")
    try:
        start_value = int(source_start)
    except ValueError:
        start_value = -1
    return (
        sort_key_for_paper_id(str(row.get("paper_id") or "")),
        str(row.get("row_type") or ""),
        str(row.get("segment_id") or ""),
        start_value,
        str(row.get("round_id") or ""),
    )


def reviewed_response_rows(gold_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for responses_path in sorted(gold_root.glob(f"*/{RESPONSES_FILENAME}")):
        for row in load_csv_rows(responses_path):
            if str(row.get("review_status") or "").strip() == "reviewed":
                rows.append({fieldname: str(row.get(fieldname) or "") for fieldname in RESPONSE_FIELDNAMES})
    return rows


def gold_dedupe_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("paper_id") or ""),
        str(row.get("row_type") or ""),
        str(row.get("segment_id") or ""),
        str(row.get("source_start") or ""),
        str(row.get("source_end") or ""),
        str(row.get("prepared_source_sha256") or ""),
    )


def refresh_gold_standard(*, gold_root: Path = GOLD_STANDARD_ROOT) -> Path:
    gold_root.mkdir(parents=True, exist_ok=True)
    updated_at = now_utc_iso()
    rows_by_key: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    for row in reviewed_response_rows(gold_root):
        gold_row = {fieldname: str(row.get(fieldname) or "") for fieldname in RESPONSE_FIELDNAMES}
        gold_row["gold_updated_at_utc"] = updated_at
        rows_by_key[gold_dedupe_key(row)] = gold_row
    ordered_rows = sorted(rows_by_key.values(), key=response_sort_key)
    master_path = gold_root / GOLD_MASTER_PATH.name
    write_csv_rows(master_path, ordered_rows, GOLD_FIELDNAMES)
    return master_path
