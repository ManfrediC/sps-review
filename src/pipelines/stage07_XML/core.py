from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _source_routing import resolve_source_row, truthy


REPO_ROOT = Path(__file__).resolve().parents[3]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "extraction_json" / "stage07_xml"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "stage07_xml_registry.csv"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
SOURCE_CASE_COUNT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
STAGE07_XML_SCHEMA_VERSION = "stage07_xml_v1"
SEGMENTS_SCHEMA_VERSION = "stage07_xml_segments_v1"
TARGET_VIEW_SCHEMA_VERSION = "stage07_xml_target_view_v1"
MANIFEST_SCHEMA_VERSION = "stage07_xml_manifest_v1"
DEFAULT_ANNOTATION_MODEL = "gpt-5.5"
DEFAULT_MAX_BLOCK_CHARS = 3500
ALLOWED_ROLES = {
    "patient_specific",
    "shared",
    "group_summary",
    "group_specific",
    "uncertain",
    "background",
}


REGISTRY_FIELDNAMES = [
    "paper_id",
    "stage07_schema_version",
    "source_text_json_path",
    "source_text_sha256",
    "prepared_source_sha256",
    "prepared_source_character_count",
    "route_mode",
    "annotation_mode",
    "annotation_model",
    "validation_status",
    "roundtrip_status",
    "paper_json_path",
    "annotated_text_path",
    "segments_json_path",
    "target_views_dir",
    "validation_json_path",
    "n_expected_patients",
    "n_declared_patients",
    "n_declared_groups",
    "n_segments",
    "n_patient_specific_segments",
    "n_shared_segments",
    "n_group_specific_segments",
    "n_group_summary_segments",
    "n_uncertain_segments",
    "n_target_views",
    "n_ready_target_views",
    "ready_for_langextract",
    "manual_review_required",
    "manual_review_reasons",
    "stage06_diverged",
    "stage06_final_count",
    "stage06_count_confidence",
    "count_risk_band",
    "manifest_run_id",
    "generated_at_utc",
]


@dataclass(frozen=True)
class OutputPaths:
    root: Path
    papers_dir: Path
    annotated_text_dir: Path
    segments_dir: Path
    target_views_dir: Path
    validation_dir: Path
    manifests_dir: Path


@dataclass(frozen=True)
class SourceBlock:
    block_id: str
    text: str
    source_start: int
    source_end: int
    page_index: int | None


@dataclass(frozen=True)
class PreparedSource:
    paper_id: str
    source_text: str
    source_sha256: str
    source_text_json_path: str
    source_filename: str
    source_record_sha256: str
    blocks: list[SourceBlock]


@dataclass(frozen=True)
class Stage06Prior:
    final_count: int | None
    count_confidence: str
    count_basis: str
    manual_review_required: bool
    preferred_text_json_path: str


@dataclass(frozen=True)
class Target:
    target_id: str
    target_kind: str
    label: str
    source: str


@dataclass(frozen=True)
class PhysicalSegment:
    segment_id: str
    logical_segment_id: str
    targets: list[str]
    role: str
    text: str
    source_start: int
    source_end: int
    block_id: str
    confidence: str
    evidence: str


@dataclass
class ValidationReport:
    status: str = "passed"
    roundtrip_status: str = "not_run"
    errors: list[str] | None = None
    warnings: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.status = "failed"

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


@dataclass(frozen=True)
class ProcessResult:
    paper_id: str
    paper_payload: dict[str, Any]
    segments_payload: dict[str, Any]
    validation_payload: dict[str, Any]
    target_view_payloads: dict[str, dict[str, Any]]
    annotated_text: str
    registry_row: dict[str, str]
    manifest_records: list[dict[str, Any]]
    paths: dict[str, Path]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest_run_id(now_iso: str | None = None) -> str:
    now_value = datetime.now(timezone.utc) if now_iso is None else datetime.fromisoformat(now_iso)
    return now_value.strftime("%Y%m%dT%H%M%SZ_stage07_xml")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_repo(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def repo_path_from_relative(value: str) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            str(row.get(key_column) or "").strip(): row
            for row in reader
            if str(row.get(key_column) or "").strip()
        }


def output_paths(root: Path = DEFAULT_OUTPUT_ROOT) -> OutputPaths:
    return OutputPaths(
        root=root,
        papers_dir=root / "papers",
        annotated_text_dir=root / "annotated_text",
        segments_dir=root / "segments",
        target_views_dir=root / "target_views",
        validation_dir=root / "validation",
        manifests_dir=root / "manifests",
    )


def ensure_output_dirs(paths: OutputPaths) -> None:
    for path in (
        paths.papers_dir,
        paths.annotated_text_dir,
        paths.segments_dir,
        paths.target_views_dir,
        paths.validation_dir,
        paths.manifests_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def parse_stage06_prior(row: dict[str, str]) -> Stage06Prior:
    count_text = str(row.get("likely_sps_case_count") or "").strip()
    return Stage06Prior(
        final_count=int(count_text) if count_text.isdigit() else None,
        count_confidence=str(row.get("count_confidence") or "").strip(),
        count_basis=str(row.get("count_basis") or "").strip(),
        manual_review_required=truthy(row.get("count_manual_review_required") or ""),
        preferred_text_json_path=str(row.get("preferred_text_json_path") or "").strip(),
    )


def resolve_source_json_path(
    *,
    paper_id: str,
    source_row: dict[str, str],
    stage06_prior: Stage06Prior,
) -> Path:
    for raw_path in (
        stage06_prior.preferred_text_json_path,
        str(source_row.get("preferred_text_json_path") or "").strip(),
    ):
        path = repo_path_from_relative(raw_path)
        if path is not None and path.exists():
            return path
    fallback = TEXT_DIR / f"{paper_id}.json"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Preferred text JSON missing for paper {paper_id}: {fallback}")


def normalise_page_text(page_text: str) -> str:
    return str(page_text or "").strip("\n")


def prepare_source(
    *,
    paper_id: str,
    source_path: Path,
    max_block_chars: int = DEFAULT_MAX_BLOCK_CHARS,
) -> PreparedSource:
    record = load_json(source_path)
    page_chunks: list[tuple[int | None, str]] = []
    for page in record.get("pages") or []:
        text = normalise_page_text(str(page.get("text") or ""))
        if text.strip():
            page_chunks.append((page.get("page_index"), text))
    source_text = "\n\n".join(text for _, text in page_chunks).strip()
    blocks = build_blocks(source_text, page_chunks, max_block_chars=max_block_chars)
    source_record_text = source_path.read_text(encoding="utf-8")
    return PreparedSource(
        paper_id=paper_id,
        source_text=source_text,
        source_sha256=sha256_text(source_text),
        source_text_json_path=relative_to_repo(source_path),
        source_filename=str(record.get("source_filename") or ""),
        source_record_sha256=sha256_text(source_record_text),
        blocks=blocks,
    )


def build_blocks(
    source_text: str,
    page_chunks: list[tuple[int | None, str]],
    *,
    max_block_chars: int = DEFAULT_MAX_BLOCK_CHARS,
) -> list[SourceBlock]:
    blocks: list[SourceBlock] = []
    search_start = 0
    for page_index, page_text in page_chunks:
        page_start = source_text.find(page_text, search_start)
        if page_start < 0:
            continue
        search_start = page_start + len(page_text)
        paragraph_spans = paragraph_relative_spans(page_text)
        for paragraph_start, paragraph_end in paragraph_spans:
            absolute_start = page_start + paragraph_start
            absolute_end = page_start + paragraph_end
            blocks.extend(
                split_block(
                    source_text=source_text,
                    start=absolute_start,
                    end=absolute_end,
                    page_index=int(page_index) if page_index is not None else None,
                    next_index=len(blocks) + 1,
                    max_block_chars=max_block_chars,
                )
            )
    return renumber_blocks(blocks)


def paragraph_relative_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\S(?:.*?)(?=\n\s*\n|\Z)", text, flags=re.DOTALL):
        start = match.start()
        end = match.end()
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append((start, end))
    if not spans and text.strip():
        start = len(text) - len(text.lstrip())
        end = len(text.rstrip())
        spans.append((start, end))
    return spans


def split_block(
    *,
    source_text: str,
    start: int,
    end: int,
    page_index: int | None,
    next_index: int,
    max_block_chars: int,
) -> list[SourceBlock]:
    if end - start <= max_block_chars:
        return [
            SourceBlock(
                block_id=f"b{next_index:04d}",
                text=source_text[start:end],
                source_start=start,
                source_end=end,
                page_index=page_index,
            )
        ]

    blocks: list[SourceBlock] = []
    cursor = start
    index = next_index
    while cursor < end:
        split_end = min(cursor + max_block_chars, end)
        if split_end < end:
            newline = source_text.rfind("\n", cursor, split_end)
            if newline > cursor:
                split_end = newline
        while split_end > cursor and source_text[split_end - 1].isspace():
            split_end -= 1
        if split_end <= cursor:
            split_end = min(cursor + max_block_chars, end)
        blocks.append(
            SourceBlock(
                block_id=f"b{index:04d}",
                text=source_text[cursor:split_end],
                source_start=cursor,
                source_end=split_end,
                page_index=page_index,
            )
        )
        cursor = split_end
        while cursor < end and source_text[cursor].isspace():
            cursor += 1
        index += 1
    return blocks


def renumber_blocks(blocks: list[SourceBlock]) -> list[SourceBlock]:
    return [
        SourceBlock(
            block_id=f"b{index:04d}",
            text=block.text,
            source_start=block.source_start,
            source_end=block.source_end,
            page_index=block.page_index,
        )
        for index, block in enumerate(blocks, start=1)
    ]


def source_blocks_payload(blocks: list[SourceBlock]) -> list[dict[str, Any]]:
    return [
        {
            "block_id": block.block_id,
            "source_offsets": {"start": block.source_start, "end": block.source_end},
            "page_index": block.page_index,
            "text": block.text,
        }
        for block in blocks
    ]


def count_risk_band(stage06_prior: Stage06Prior) -> str:
    count = stage06_prior.final_count
    if count is None:
        return "unknown_count"
    if count > 20:
        return "high_count"
    if count > 10:
        return "moderate_count"
    return "standard_count"


def route_mode(source_row: dict[str, str], resolved_source: dict[str, str]) -> str:
    resolved_mode = str(resolved_source.get("resolved_langextract_mode") or "").strip()
    if resolved_mode in {"individual", "individual_case_split", "group"}:
        return resolved_mode
    return str(source_row.get("preferred_langextract_mode") or "").strip() or resolved_mode


def initial_targets(
    *,
    route: str,
    stage06_prior: Stage06Prior,
) -> list[Target]:
    if route == "individual":
        return [Target("p1", "patient", "Patient 1", "stage06_single_patient_prior")]
    if route == "individual_case_split":
        if stage06_prior.final_count is None or stage06_prior.final_count < 1:
            return []
        return [
            Target(f"p{index}", "patient", f"Patient {index}", "stage06_count_prior")
            for index in range(1, stage06_prior.final_count + 1)
        ]
    if route == "group":
        return [Target("g1", "group", "SPSD group", "stage06_group_prior")]
    return []


def target_payload(targets: list[Target]) -> list[dict[str, str]]:
    return [
        {
            "id": target.target_id,
            "kind": target.target_kind,
            "label": target.label,
            "source": target.source,
        }
        for target in targets
    ]


def merge_declared_targets(
    base_targets: list[Target],
    annotation_payload: dict[str, Any],
    report: ValidationReport,
) -> tuple[list[Target], bool]:
    targets_by_id = {target.target_id: target for target in base_targets}
    stage06_diverged = False
    for item in annotation_payload.get("targets") or []:
        target_id = str(item.get("id") or "").strip()
        target_kind = str(item.get("kind") or "").strip()
        label = str(item.get("label") or target_id).strip()
        evidence = str(item.get("evidence") or "").strip()
        if not re.fullmatch(r"[pg]\d+", target_id):
            report.add_error(f"invalid_declared_target_id:{target_id}")
            continue
        if target_kind not in {"patient", "group"}:
            report.add_error(f"invalid_declared_target_kind:{target_id}:{target_kind}")
            continue
        if target_id not in targets_by_id:
            if target_kind == "group" and evidence:
                targets_by_id[target_id] = Target(target_id, target_kind, label, "stage07_annotation")
                stage06_diverged = True
            else:
                report.add_error(f"undeclared_target_without_source_evidence:{target_id}")
    return list(targets_by_id.values()), stage06_diverged


def deterministic_annotation_for_route(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    route: str,
) -> dict[str, Any]:
    if not targets or not prepared_source.blocks:
        return {"segments": []}
    target = targets[0]
    if route == "individual":
        role = "patient_specific"
    elif route == "group":
        role = "group_summary"
    else:
        return {"segments": []}
    return {
        "segments": [
            {
                "targets": [target.target_id],
                "role": role,
                "confidence": "high",
                "evidence": "Deterministic pass-through for attribution-safe route.",
                "spans": [
                    {
                        "block_id": block.block_id,
                        "start_offset": 0,
                        "end_offset": len(block.text),
                        "selected_text": block.text,
                    }
                    for block in prepared_source.blocks
                ],
            }
        ]
    }


def validate_annotation_payload(
    *,
    annotation_payload: dict[str, Any],
    prepared_source: PreparedSource,
    declared_targets: list[Target],
) -> tuple[list[PhysicalSegment], ValidationReport]:
    report = ValidationReport()
    blocks_by_id = {block.block_id: block for block in prepared_source.blocks}
    declared_ids = {target.target_id for target in declared_targets}
    physical_segments: list[PhysicalSegment] = []

    for logical_index, item in enumerate(annotation_payload.get("segments") or [], start=1):
        logical_segment_id = f"l{logical_index:04d}"
        role = str(item.get("role") or "").strip()
        if role not in ALLOWED_ROLES:
            report.add_error(f"invalid_role:{logical_segment_id}:{role}")
            continue
        targets = [str(target).strip() for target in item.get("targets") or [] if str(target).strip()]
        if not targets:
            report.add_error(f"missing_targets:{logical_segment_id}")
            continue
        for target_id in targets:
            if target_id == "unknown":
                if role != "uncertain":
                    report.add_error(f"unknown_target_requires_uncertain_role:{logical_segment_id}")
                continue
            if target_id not in declared_ids:
                report.add_error(f"unknown_target:{logical_segment_id}:{target_id}")
        confidence = str(item.get("confidence") or "").strip() or "unspecified"
        evidence = str(item.get("evidence") or "").strip()
        for span in item.get("spans") or []:
            block_id = str(span.get("block_id") or "").strip()
            block = blocks_by_id.get(block_id)
            if block is None:
                report.add_error(f"unknown_block:{logical_segment_id}:{block_id}")
                continue
            start = parse_int(span.get("start_offset"))
            end = parse_int(span.get("end_offset"))
            selected_text = str(span.get("selected_text") or "")
            if start is None or end is None:
                report.add_error(f"invalid_offsets:{logical_segment_id}:{block_id}")
                continue
            if start < 0 or end < start or end > len(block.text):
                report.add_error(f"offsets_out_of_bounds:{logical_segment_id}:{block_id}:{start}:{end}")
                continue
            actual_text = block.text[start:end]
            if actual_text != selected_text:
                report.add_error(f"offset_text_mismatch:{logical_segment_id}:{block_id}:{start}:{end}")
                continue
            segment_id = f"s{len(physical_segments) + 1:04d}"
            physical_segments.append(
                PhysicalSegment(
                    segment_id=segment_id,
                    logical_segment_id=logical_segment_id,
                    targets=targets,
                    role=role,
                    text=prepared_source.source_text[block.source_start + start : block.source_start + end],
                    source_start=block.source_start + start,
                    source_end=block.source_start + end,
                    block_id=block_id,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

    validate_segment_overlaps(physical_segments, report)
    for segment in physical_segments:
        if "unknown" in segment.targets or segment.role == "uncertain":
            report.add_warning(f"uncertain_segment_excluded_from_ready_views:{segment.segment_id}")
    return physical_segments, report


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_segment_overlaps(segments: list[PhysicalSegment], report: ValidationReport) -> None:
    ordered = sorted(segments, key=lambda item: (item.source_start, item.source_end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.source_start < previous.source_end:
            report.add_error(f"overlapping_segments:{previous.segment_id}:{current.segment_id}")


def seg_open_tag(segment: PhysicalSegment) -> str:
    targets = " ".join(segment.targets)
    attrs = {
        "id": segment.segment_id,
        "group": segment.logical_segment_id,
        "targets": targets,
        "role": segment.role,
    }
    rendered = " ".join(
        f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs.items()
    )
    return f"<seg {rendered}>"


def insert_xml_tags(source_text: str, segments: list[PhysicalSegment]) -> str:
    annotated = source_text
    for segment in sorted(segments, key=lambda item: (item.source_start, item.source_end), reverse=True):
        annotated = annotated[: segment.source_end] + "</seg>" + annotated[segment.source_end :]
        annotated = annotated[: segment.source_start] + seg_open_tag(segment) + annotated[segment.source_start :]
    return annotated


def strip_stage07_tags(annotated_text: str) -> str:
    return re.sub(r"</?seg\b[^>]*>", "", annotated_text)


def validate_roundtrip(source_text: str, annotated_text: str, report: ValidationReport) -> None:
    stripped = strip_stage07_tags(annotated_text)
    if stripped == source_text:
        report.roundtrip_status = "passed"
    else:
        report.roundtrip_status = "failed"
        report.add_error("roundtrip_failed")


def segment_payloads(segments: list[PhysicalSegment]) -> list[dict[str, Any]]:
    return [
        {
            "segment_id": segment.segment_id,
            "logical_segment_id": segment.logical_segment_id,
            "targets": segment.targets,
            "role": segment.role,
            "text": segment.text,
            "source_offsets": {"start": segment.source_start, "end": segment.source_end},
            "source_block_id": segment.block_id,
            "confidence": segment.confidence,
            "evidence": segment.evidence,
        }
        for segment in sorted(segments, key=lambda item: (item.source_start, item.source_end))
    ]


def relevant_segments_for_target(
    target: Target,
    segments: list[PhysicalSegment],
) -> list[PhysicalSegment]:
    selected: list[PhysicalSegment] = []
    for segment in segments:
        if target.target_id not in segment.targets:
            continue
        if "unknown" in segment.targets or segment.role == "uncertain":
            continue
        selected.append(segment)
    return sorted(selected, key=lambda item: (item.source_start, item.source_end))


def relation_to_target(target: Target, segment: PhysicalSegment) -> str:
    if len(segment.targets) > 1:
        return "shared"
    if target.target_kind == "group":
        return "group"
    return "direct"


def build_target_views(
    *,
    paper_id: str,
    targets: list[Target],
    segments: list[PhysicalSegment],
    paper_ready: bool,
    manual_review_reasons: list[str],
) -> dict[str, dict[str, Any]]:
    views: dict[str, dict[str, Any]] = {}
    for target in targets:
        selected = relevant_segments_for_target(target, segments)
        compiled_parts: list[str] = []
        source_blocks: list[dict[str, Any]] = []
        cursor = 0
        for block_order, segment in enumerate(selected, start=1):
            if compiled_parts:
                compiled_parts.append("\n\n")
                cursor += 2
            start = cursor
            compiled_parts.append(segment.text)
            cursor += len(segment.text)
            end = cursor
            source_blocks.append(
                {
                    "block_id": f"tb{block_order:04d}",
                    "segment_id": segment.segment_id,
                    "logical_segment_id": segment.logical_segment_id,
                    "relation_to_target": relation_to_target(target, segment),
                    "role": segment.role,
                    "shared_with": [
                        target_id
                        for target_id in segment.targets
                        if target_id != target.target_id and target_id != "unknown"
                    ],
                    "source_offsets": {"start": segment.source_start, "end": segment.source_end},
                    "compiled_offsets": {"start": start, "end": end},
                }
            )
        input_text = "".join(compiled_parts)
        target_has_text = bool(input_text.strip())
        ready = bool(paper_ready and target_has_text)
        target_reasons = list(manual_review_reasons)
        if not target_has_text:
            target_reasons.append(f"missing_target_evidence:{target.target_id}")
        views[target.target_id] = {
            "stage07_target_view_schema_version": TARGET_VIEW_SCHEMA_VERSION,
            "document_id": f"{paper_id}::{target.target_id}",
            "paper_id": paper_id,
            "target_id": target.target_id,
            "target_kind": target.target_kind,
            "target_label": target.label,
            "ready_for_langextract": ready,
            "input_text": input_text,
            "source_blocks": source_blocks,
            "manual_review": {
                "manual_review_required": not ready,
                "reasons": target_reasons,
            },
        }
    return views


def missing_target_reasons(targets: list[Target], segments: list[PhysicalSegment]) -> list[str]:
    reasons: list[str] = []
    for target in targets:
        if not relevant_segments_for_target(target, segments):
            reasons.append(f"missing_target_evidence:{target.target_id}")
    return reasons


def build_manifest_records(
    *,
    manifest_run_id: str,
    paper_id: str,
    target_views: dict[str, dict[str, Any]],
    paths: dict[str, Path],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for target_id, view in sorted(target_views.items()):
        records.append(
            {
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                "manifest_run_id": manifest_run_id,
                "paper_id": paper_id,
                "document_id": view["document_id"],
                "target_id": target_id,
                "target_kind": view["target_kind"],
                "target_label": view["target_label"],
                "input_json_path": relative_to_repo(paths["target_views_dir"] / f"{target_id}.json"),
                "paper_json_path": relative_to_repo(paths["paper_json_path"]),
                "segments_json_path": relative_to_repo(paths["segments_json_path"]),
                "annotated_text_path": relative_to_repo(paths["annotated_text_path"]),
                "ready_for_langextract": view["ready_for_langextract"],
                "manual_review_required": view["manual_review"]["manual_review_required"],
                "manual_review_reasons": view["manual_review"]["reasons"],
            }
        )
    return records


def write_manifest(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def write_registry(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_registry_row(
    *,
    paper_id: str,
    prepared_source: PreparedSource,
    targets: list[Target],
    segments: list[PhysicalSegment],
    target_views: dict[str, dict[str, Any]],
    validation_report: ValidationReport,
    paths: dict[str, Path],
    route: str,
    annotation_mode: str,
    annotation_model: str,
    stage06_prior: Stage06Prior,
    stage06_diverged: bool,
    manifest_run_id: str,
    generated_at_utc: str,
    manual_review_reasons: list[str],
) -> dict[str, str]:
    declared_patients = sum(1 for target in targets if target.target_kind == "patient")
    declared_groups = sum(1 for target in targets if target.target_kind == "group")
    ready_count = sum(1 for view in target_views.values() if view["ready_for_langextract"])
    ready_for_langextract = bool(target_views) and ready_count == len(target_views) and not validation_report.failed
    return {
        "paper_id": paper_id,
        "stage07_schema_version": STAGE07_XML_SCHEMA_VERSION,
        "source_text_json_path": prepared_source.source_text_json_path,
        "source_text_sha256": prepared_source.source_record_sha256,
        "prepared_source_sha256": prepared_source.source_sha256,
        "prepared_source_character_count": str(len(prepared_source.source_text)),
        "route_mode": route,
        "annotation_mode": annotation_mode,
        "annotation_model": annotation_model,
        "validation_status": validation_report.status,
        "roundtrip_status": validation_report.roundtrip_status,
        "paper_json_path": relative_to_repo(paths["paper_json_path"]),
        "annotated_text_path": relative_to_repo(paths["annotated_text_path"]),
        "segments_json_path": relative_to_repo(paths["segments_json_path"]),
        "target_views_dir": relative_to_repo(paths["target_views_dir"]),
        "validation_json_path": relative_to_repo(paths["validation_json_path"]),
        "n_expected_patients": "" if stage06_prior.final_count is None else str(stage06_prior.final_count),
        "n_declared_patients": str(declared_patients),
        "n_declared_groups": str(declared_groups),
        "n_segments": str(len(segments)),
        "n_patient_specific_segments": str(sum(1 for item in segments if item.role == "patient_specific")),
        "n_shared_segments": str(sum(1 for item in segments if item.role == "shared")),
        "n_group_specific_segments": str(sum(1 for item in segments if item.role == "group_specific")),
        "n_group_summary_segments": str(sum(1 for item in segments if item.role == "group_summary")),
        "n_uncertain_segments": str(sum(1 for item in segments if item.role == "uncertain")),
        "n_target_views": str(len(target_views)),
        "n_ready_target_views": str(ready_count),
        "ready_for_langextract": bool_text(ready_for_langextract),
        "manual_review_required": bool_text(not ready_for_langextract),
        "manual_review_reasons": "|".join(manual_review_reasons),
        "stage06_diverged": bool_text(stage06_diverged),
        "stage06_final_count": "" if stage06_prior.final_count is None else str(stage06_prior.final_count),
        "stage06_count_confidence": stage06_prior.count_confidence,
        "count_risk_band": count_risk_band(stage06_prior),
        "manifest_run_id": manifest_run_id,
        "generated_at_utc": generated_at_utc,
    }


def build_error_result(
    *,
    paper_id: str,
    error_message: str,
    paths: OutputPaths,
    manifest_run_id: str,
    route: str,
    annotation_model: str,
) -> ProcessResult:
    generated_at_utc = now_utc_iso()
    paper_paths = paper_output_paths(paths, paper_id)
    report = ValidationReport(status="failed", roundtrip_status="not_run")
    report.add_error(error_message)
    prepared_source = PreparedSource(
        paper_id=paper_id,
        source_text="",
        source_sha256="",
        source_text_json_path="",
        source_filename="",
        source_record_sha256="",
        blocks=[],
    )
    stage06_prior = Stage06Prior(None, "", "", False, "")
    paper_payload = {
        "paper_id": paper_id,
        "stage07_schema_version": STAGE07_XML_SCHEMA_VERSION,
        "stage07_method": {
            "annotation_mode": "error",
            "annotation_model": annotation_model,
            "manifest_run_id": manifest_run_id,
            "generated_at_utc": generated_at_utc,
        },
        "manual_review": {"manual_review_required": True, "reasons": [error_message]},
    }
    segments_payload = {
        "paper_id": paper_id,
        "stage07_segments_schema_version": SEGMENTS_SCHEMA_VERSION,
        "segments": [],
        "validation": report_payload(report),
    }
    validation_payload = report_payload(report)
    registry_row = build_registry_row(
        paper_id=paper_id,
        prepared_source=prepared_source,
        targets=[],
        segments=[],
        target_views={},
        validation_report=report,
        paths=paper_paths,
        route=route,
        annotation_mode="error",
        annotation_model=annotation_model,
        stage06_prior=stage06_prior,
        stage06_diverged=False,
        manifest_run_id=manifest_run_id,
        generated_at_utc=generated_at_utc,
        manual_review_reasons=[error_message],
    )
    return ProcessResult(
        paper_id=paper_id,
        paper_payload=paper_payload,
        segments_payload=segments_payload,
        validation_payload=validation_payload,
        target_view_payloads={},
        annotated_text="",
        registry_row=registry_row,
        manifest_records=[],
        paths=paper_paths,
    )


def paper_output_paths(paths: OutputPaths, paper_id: str) -> dict[str, Path]:
    target_views_dir = paths.target_views_dir / paper_id
    return {
        "paper_json_path": paths.papers_dir / f"{paper_id}.json",
        "annotated_text_path": paths.annotated_text_dir / f"{paper_id}.annotated.txt",
        "segments_json_path": paths.segments_dir / f"{paper_id}.segments.json",
        "target_views_dir": target_views_dir,
        "validation_json_path": paths.validation_dir / f"{paper_id}.validation.json",
    }


def report_payload(report: ValidationReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "roundtrip_status": report.roundtrip_status,
        "errors": list(report.errors or []),
        "warnings": list(report.warnings or []),
    }


def process_paper(
    *,
    paper_id: str,
    source_row: dict[str, str],
    manual_row: dict[str, str],
    stage06_row: dict[str, str],
    paths: OutputPaths,
    manifest_run_id: str,
    annotation_model: str,
    annotation_payload: dict[str, Any] | None,
    max_block_chars: int = DEFAULT_MAX_BLOCK_CHARS,
) -> ProcessResult:
    generated_at_utc = now_utc_iso()
    paper_paths = paper_output_paths(paths, paper_id)
    resolved_source = resolve_source_row(
        paper_id=paper_id,
        heuristic_row=source_row,
        manual_row=manual_row,
    )
    stage06_prior = parse_stage06_prior(stage06_row)
    route = route_mode(source_row, resolved_source)
    try:
        source_path = resolve_source_json_path(
            paper_id=paper_id,
            source_row=source_row,
            stage06_prior=stage06_prior,
        )
        prepared_source = prepare_source(
            paper_id=paper_id,
            source_path=source_path,
            max_block_chars=max_block_chars,
        )
    except FileNotFoundError as exc:
        return build_error_result(
            paper_id=paper_id,
            error_message=str(exc),
            paths=paths,
            manifest_run_id=manifest_run_id,
            route=route,
            annotation_model=annotation_model,
        )

    base_targets = initial_targets(route=route, stage06_prior=stage06_prior)
    annotation_mode = "stage07_span_metadata"
    if annotation_payload is None:
        annotation_payload = deterministic_annotation_for_route(
            prepared_source=prepared_source,
            targets=base_targets,
            route=route,
        )
        annotation_mode = "deterministic_pass_through"

    preliminary_report = ValidationReport()
    targets, target_diverged = merge_declared_targets(base_targets, annotation_payload, preliminary_report)
    segments, validation_report = validate_annotation_payload(
        annotation_payload=annotation_payload,
        prepared_source=prepared_source,
        declared_targets=targets,
    )
    for error in preliminary_report.errors or []:
        validation_report.add_error(error)
    for warning in preliminary_report.warnings or []:
        validation_report.add_warning(warning)

    annotated_text = insert_xml_tags(prepared_source.source_text, segments)
    validate_roundtrip(prepared_source.source_text, annotated_text, validation_report)
    coverage_reasons = missing_target_reasons(targets, segments)
    for reason in coverage_reasons:
        validation_report.add_warning(reason)
    manual_review_reasons = list(validation_report.errors or [])
    manual_review_reasons.extend(coverage_reasons)
    paper_ready = not validation_report.failed and not coverage_reasons
    target_views = build_target_views(
        paper_id=paper_id,
        targets=targets,
        segments=segments,
        paper_ready=paper_ready,
        manual_review_reasons=manual_review_reasons,
    )

    validation_payload = report_payload(validation_report)
    segments_payload = {
        "paper_id": paper_id,
        "stage07_segments_schema_version": SEGMENTS_SCHEMA_VERSION,
        "source": {
            "source_text_json_path": prepared_source.source_text_json_path,
            "source_text_sha256": prepared_source.source_record_sha256,
            "prepared_source_sha256": prepared_source.source_sha256,
            "prepared_source_character_count": len(prepared_source.source_text),
        },
        "entities": target_payload(targets),
        "source_blocks": source_blocks_payload(prepared_source.blocks),
        "segments": segment_payloads(segments),
        "validation": validation_payload,
    }
    stage06_diverged = bool(target_diverged)
    registry_row = build_registry_row(
        paper_id=paper_id,
        prepared_source=prepared_source,
        targets=targets,
        segments=segments,
        target_views=target_views,
        validation_report=validation_report,
        paths=paper_paths,
        route=route,
        annotation_mode=annotation_mode,
        annotation_model=annotation_model if annotation_mode != "deterministic_pass_through" else "none",
        stage06_prior=stage06_prior,
        stage06_diverged=stage06_diverged,
        manifest_run_id=manifest_run_id,
        generated_at_utc=generated_at_utc,
        manual_review_reasons=manual_review_reasons,
    )
    manifest_records = build_manifest_records(
        manifest_run_id=manifest_run_id,
        paper_id=paper_id,
        target_views=target_views,
        paths=paper_paths,
    )
    paper_payload = {
        "paper_id": paper_id,
        "stage07_schema_version": STAGE07_XML_SCHEMA_VERSION,
        "source": {
            "source_text_json_path": prepared_source.source_text_json_path,
            "source_text_sha256": prepared_source.source_record_sha256,
            "prepared_source_sha256": prepared_source.source_sha256,
            "prepared_source_character_count": len(prepared_source.source_text),
            "source_filename": prepared_source.source_filename,
        },
        "source_route": {
            "resolved_source_category": resolved_source.get("resolved_source_category") or "",
            "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
            "resolved_langextract_mode": route,
        },
        "stage06_prior": {
            "final_count": stage06_prior.final_count,
            "count_confidence": stage06_prior.count_confidence,
            "count_basis": stage06_prior.count_basis,
            "manual_review_required": stage06_prior.manual_review_required,
            "count_risk_band": count_risk_band(stage06_prior),
        },
        "annotation": {
            "annotation_mode": annotation_mode,
            "annotation_model": annotation_model if annotation_mode != "deterministic_pass_through" else "none",
            "annotated_text_path": relative_to_repo(paper_paths["annotated_text_path"]),
            "roundtrip_status": validation_report.roundtrip_status,
            "validation_status": validation_report.status,
        },
        "entities": target_payload(targets),
        "segment_output": {
            "segments_json_path": relative_to_repo(paper_paths["segments_json_path"]),
            "n_segments": len(segments),
        },
        "target_views": [
            {
                "target_id": view["target_id"],
                "target_kind": view["target_kind"],
                "target_label": view["target_label"],
                "target_view_path": relative_to_repo(
                    paper_paths["target_views_dir"] / f"{target_id}.json"
                ),
                "ready_for_langextract": view["ready_for_langextract"],
            }
            for target_id, view in sorted(target_views.items())
        ],
        "manual_review": {
            "manual_review_required": bool(manual_review_reasons),
            "reasons": manual_review_reasons,
        },
        "stage07_method": {
            "pipeline_entrypoint": "stage07_XML/run_stage07_xml.py",
            "manifest_run_id": manifest_run_id,
            "generated_at_utc": generated_at_utc,
        },
    }
    if stage06_diverged:
        paper_payload["stage06_divergence"] = {
            "diverged": True,
            "dimensions": ["target_inventory"],
            "reason": "Stage 07 declared source-backed group targets beyond the Stage 06 prior.",
        }

    return ProcessResult(
        paper_id=paper_id,
        paper_payload=paper_payload,
        segments_payload=segments_payload,
        validation_payload=validation_payload,
        target_view_payloads=target_views,
        annotated_text=annotated_text,
        registry_row=registry_row,
        manifest_records=manifest_records,
        paths=paper_paths,
    )


def write_process_result(result: ProcessResult) -> None:
    write_json(result.paths["paper_json_path"], result.paper_payload)
    result.paths["annotated_text_path"].parent.mkdir(parents=True, exist_ok=True)
    result.paths["annotated_text_path"].write_text(result.annotated_text, encoding="utf-8")
    write_json(result.paths["segments_json_path"], result.segments_payload)
    write_json(result.paths["validation_json_path"], result.validation_payload)
    result.paths["target_views_dir"].mkdir(parents=True, exist_ok=True)
    for target_id, payload in result.target_view_payloads.items():
        write_json(result.paths["target_views_dir"] / f"{target_id}.json", payload)


def collect_candidate_ids(
    *,
    source_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    paper_ids: list[str],
    limit: int,
    route_filter: str,
) -> list[str]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    if wanted:
        return sorted_paper_ids(wanted)
    allowed_modes = {"individual", "individual_case_split", "group"}
    if route_filter != "all":
        allowed_modes = {route_filter}
    candidate_ids: list[str] = []
    for paper_id, row in sorted(source_rows.items(), key=lambda item: sort_key(item[0])):
        resolved = resolve_source_row(
            paper_id=paper_id,
            heuristic_row=row,
            manual_row=manual_rows.get(paper_id, {}),
        )
        mode = route_mode(row, resolved)
        eligible = truthy(resolved.get("resolved_langextract_eligible") or row.get("langextract_eligible") or "")
        if eligible and mode in allowed_modes:
            candidate_ids.append(paper_id)
    if limit > 0:
        candidate_ids = candidate_ids[:limit]
    return candidate_ids


def sort_key(value: str) -> tuple[int, int | str]:
    stripped = value.strip()
    if stripped.isdigit():
        return (0, int(stripped))
    return (1, stripped)


def sorted_paper_ids(values: set[str]) -> list[str]:
    return sorted(values, key=sort_key)
