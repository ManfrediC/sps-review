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
REVIEWED_ANNOTATION_SCHEMA_VERSION = "stage07_reviewed_annotation_v1"
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
class SourcePatientLabel:
    label: str
    start: int


@dataclass(frozen=True)
class RouteDecision:
    route: str
    warnings: tuple[str, ...] = ()
    diverged: bool = False
    recovered_target_labels: tuple[str, ...] = ()
    manual_review_reasons: tuple[str, ...] = ()


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
    review_reasons: list[str] | None = None
    span_adjustments: list[dict[str, Any]] | None = None
    rejected_spans: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.review_reasons is None:
            self.review_reasons = []
        if self.span_adjustments is None:
            self.span_adjustments = []
        if self.rejected_spans is None:
            self.rejected_spans = []

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.status = "failed"

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_review_reason(self, message: str) -> None:
        if message not in self.review_reasons:
            self.review_reasons.append(message)

    def add_span_adjustment(self, payload: dict[str, Any]) -> None:
        self.span_adjustments.append(payload)

    def add_rejected_span(self, payload: dict[str, Any]) -> None:
        self.rejected_spans.append(payload)


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


def spsd_label_pattern() -> str:
    return r"(?:SPSD|SPS|SMS|stiff[- ](?:person|man)|stiff-person|stiff-man)"


def explicit_spsd_case_ids(text: str) -> set[str]:
    ids: set[str] = set()
    spsd_pattern = spsd_label_pattern()
    for match in re.finditer(
        rf"\b(?:case|patient)\s+(\d+)\b(?:(?!\b(?:case|patient)\s+\d+\b).){{0,180}}{spsd_pattern}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        ids.add(match.group(1))
    for match in re.finditer(
        rf"{spsd_pattern}(?:(?!\b(?:case|patient)\s+\d+\b).){{0,180}}\b(?:case|patient)\s+(\d+)\b",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        ids.add(match.group(1))
    for match in re.finditer(
        rf"\b(?:cases|patients)\s*\(?\s*(?:cases?|patients?)?\s*([0-9][0-9,\sand]*)\)?"
        rf"(?:(?!\.).){{0,220}}{spsd_pattern}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        ids.update(re.findall(r"\d+", match.group(1)))
    return ids


def normalise_source_label(kind: str, value: str) -> str:
    kind_label = "Patient" if kind.strip().casefold() == "patient" else "Case"
    return f"{kind_label} {value.strip()}".strip().rstrip(".,:;")


def source_patient_labels(text: str, *, include_headings: bool = True) -> list[SourcePatientLabel]:
    labels: list[SourcePatientLabel] = []
    seen: set[str] = set()
    label_token = r"(?:\d{1,3}|[A-Z][A-Za-z0-9-]{0,12})"
    label_kind = r"(?:Patient|PATIENT|patient|Case|CASE|case)"
    heading_pattern = re.compile(
        rf"(?m)^\s*({label_kind})\s+({label_token})(?=\s*(?:[.:]|\n|$))"
    )
    prose_patterns = [
        re.compile(
            rf"\b({label_kind})\s+({label_token})\b"
            rf"(?:(?!\b{label_kind}\s+{label_token}\b).){{0,180}}{spsd_label_pattern()}",
            flags=re.DOTALL,
        ),
        re.compile(
            rf"{spsd_label_pattern()}"
            r"(?:\s+|[- ]affected\s+)"
            rf"\b({label_kind})\s+({label_token})\b",
            flags=re.DOTALL,
        ),
    ]
    patterns = [heading_pattern, *prose_patterns] if include_headings else prose_patterns
    for pattern in patterns:
        for match in pattern.finditer(text):
            if match.group(2).casefold() in {"report", "reports", "presentation", "presentations"}:
                continue
            label = normalise_source_label(match.group(1), match.group(2))
            key = label.casefold()
            if key in seen:
                continue
            labels.append(SourcePatientLabel(label=label, start=match.start()))
            seen.add(key)
    return sorted(labels, key=lambda item: item.start)


def labels_for_explicit_spsd_ids(text: str, ids: set[str]) -> list[str]:
    if not ids:
        return []
    labels = source_patient_labels(text)
    matched: list[str] = []
    for label in labels:
        parts = label.label.split()
        if parts and parts[-1] in ids:
            matched.append(label.label)
    return matched


def has_embedded_single_spsd_case(prepared_source: PreparedSource) -> bool:
    return len(explicit_spsd_case_ids(prepared_source.source_text)) == 1


def resolve_route_decision(
    *,
    route: str,
    stage06_prior: Stage06Prior,
    prepared_source: PreparedSource,
) -> RouteDecision:
    if route != "group":
        return RouteDecision(route=route)

    text = prepared_source.source_text
    final_count = stage06_prior.final_count
    explicit_ids = explicit_spsd_case_ids(text)
    labels = source_patient_labels(text)
    spsd_context_labels = source_patient_labels(text, include_headings=False)
    if final_count == 1:
        recovered_labels = [label.label for label in spsd_context_labels]
        if not recovered_labels and len(explicit_ids) == 1:
            recovered_labels = labels_for_explicit_spsd_ids(text, explicit_ids)
        if not recovered_labels and len(labels) == 1:
            recovered_labels = [labels[0].label]
        if not recovered_labels:
            return RouteDecision(route=route)
        return RouteDecision(
            route="individual",
            warnings=("route_override:group_to_individual:embedded_single_spsd_case",),
            diverged=True,
            recovered_target_labels=tuple(recovered_labels[:1]),
        )

    if final_count is None or final_count < 2 or final_count > 20:
        return RouteDecision(route=route)

    if len(labels) == final_count:
        return RouteDecision(
            route="individual_case_split",
            warnings=("route_override:group_to_individual_case_split:source_labelled_patients",),
            diverged=True,
            recovered_target_labels=tuple(label.label for label in labels),
        )
    if labels:
        reason = f"ambiguous_route_recovery_label_count:{len(labels)}:{final_count}"
        return RouteDecision(route=route, warnings=(reason,), manual_review_reasons=(reason,))
    return RouteDecision(route=route)


def heuristic_route_override(
    *,
    route: str,
    stage06_prior: Stage06Prior,
    prepared_source: PreparedSource,
) -> tuple[str, list[str], bool]:
    decision = resolve_route_decision(
        route=route,
        stage06_prior=stage06_prior,
        prepared_source=prepared_source,
    )
    return decision.route, list(decision.warnings), decision.diverged


def initial_targets(
    *,
    route: str,
    stage06_prior: Stage06Prior,
    recovered_target_labels: list[str] | tuple[str, ...] | None = None,
) -> list[Target]:
    recovered_target_labels = list(recovered_target_labels or [])
    if route == "individual":
        label = recovered_target_labels[0] if recovered_target_labels else "Patient 1"
        source = "stage07_route_recovery" if recovered_target_labels else "stage06_single_patient_prior"
        return [Target("p1", "patient", label, source)]
    if route == "individual_case_split":
        count = len(recovered_target_labels) or stage06_prior.final_count
        if count is None or count < 1:
            return []
        return [
            Target(
                f"p{index}",
                "patient",
                recovered_target_labels[index - 1] if index <= len(recovered_target_labels) else f"Patient {index}",
                "stage07_route_recovery" if index <= len(recovered_target_labels) else "stage06_count_prior",
            )
            for index in range(1, count + 1)
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
    *,
    allow_annotation_patient_targets: bool = False,
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
                report.add_warning(f"source_backed_group_target_added:{target_id}")
                stage06_diverged = True
            elif target_kind == "patient" and allow_annotation_patient_targets:
                targets_by_id[target_id] = Target(target_id, target_kind, label, "stage07_annotation")
                if evidence:
                    report.add_warning(f"source_backed_patient_target_added:{target_id}")
                else:
                    report.add_warning(f"provisional_patient_target_added:{target_id}")
                stage06_diverged = True
            else:
                report.add_error(f"undeclared_target_without_source_evidence:{target_id}")
    return list(targets_by_id.values()), stage06_diverged


def source_range_to_span_payloads(
    prepared_source: PreparedSource,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for block in prepared_source.blocks:
        overlap_start = max(start, block.source_start)
        overlap_end = min(end, block.source_end)
        if overlap_start >= overlap_end:
            continue
        block_start = overlap_start - block.source_start
        block_end = overlap_end - block.source_start
        selected_text = prepared_source.source_text[overlap_start:overlap_end]
        if selected_text:
            spans.append(
                {
                    "block_id": block.block_id,
                    "start_offset": block_start,
                    "end_offset": block_end,
                    "selected_text": selected_text,
                }
            )
    return spans


def nth_index(value: str, needle: str, occurrence: int = 1, start: int = 0) -> int:
    if not needle:
        return -1
    cursor = start
    found = -1
    for _ in range(max(1, occurrence)):
        found = value.find(needle, cursor)
        if found < 0:
            return -1
        cursor = found + len(needle)
    return found


def reviewed_selection_range(
    prepared_source: PreparedSource,
    selection: dict[str, Any],
) -> tuple[int, int]:
    explicit_start = parse_int(selection.get("source_start"))
    explicit_end = parse_int(selection.get("source_end"))
    if explicit_start is None:
        explicit_start = parse_int(selection.get("start_offset"))
    if explicit_end is None:
        explicit_end = parse_int(selection.get("end_offset"))
    if explicit_start is not None or explicit_end is not None:
        if explicit_start is None or explicit_end is None:
            raise ValueError("Reviewed offset selections require both source_start and source_end.")
        if explicit_start < 0 or explicit_end < explicit_start or explicit_end > len(prepared_source.source_text):
            raise ValueError(
                f"Reviewed offset selection is outside prepared source bounds: {explicit_start}:{explicit_end}"
            )
        exact_text = str(selection.get("text") or "")
        if exact_text and prepared_source.source_text[explicit_start:explicit_end] != exact_text:
            raise ValueError(f"Reviewed offset selection text mismatch: {exact_text[:80]}")
        return explicit_start, explicit_end

    occurrence = parse_int(selection.get("occurrence")) or 1
    after_text = str(selection.get("after_text") or "")
    search_start = 0
    if after_text:
        after_index = nth_index(prepared_source.source_text, after_text, 1)
        if after_index < 0:
            raise ValueError(f"Reviewed selection after_text not found: {after_text[:80]}")
        search_start = after_index + len(after_text)

    exact_text = str(selection.get("text") or "")
    if exact_text:
        start = nth_index(prepared_source.source_text, exact_text, occurrence, search_start)
        if start < 0:
            raise ValueError(f"Reviewed selection text not found: {exact_text[:80]}")
        return start, start + len(exact_text)

    start_text = str(selection.get("start_text") or "")
    end_text = str(selection.get("end_text") or "")
    if not start_text or not end_text:
        raise ValueError("Reviewed selections require either text or start_text/end_text.")
    start = nth_index(prepared_source.source_text, start_text, occurrence, search_start)
    if start < 0:
        raise ValueError(f"Reviewed selection start_text not found: {start_text[:80]}")
    end_marker_start = prepared_source.source_text.find(end_text, start + len(start_text))
    if end_marker_start < 0:
        raise ValueError(f"Reviewed selection end_text not found after start: {end_text[:80]}")
    return start, end_marker_start + len(end_text)


def compile_reviewed_annotation_payload(
    *,
    reviewed_payload: dict[str, Any],
    prepared_source: PreparedSource,
) -> dict[str, Any]:
    if str(reviewed_payload.get("paper_id") or "") != prepared_source.paper_id:
        raise ValueError(f"Reviewed annotation paper_id mismatch for {prepared_source.paper_id}.")
    segments: list[dict[str, Any]] = []
    for segment in reviewed_payload.get("segments") or []:
        spans: list[dict[str, Any]] = []
        for selection in segment.get("selections") or []:
            start, end = reviewed_selection_range(prepared_source, selection)
            spans.extend(source_range_to_span_payloads(prepared_source, start, end))
        segments.append(
            {
                "targets": [str(target) for target in segment.get("targets") or []],
                "role": str(segment.get("role") or ""),
                "confidence": str(segment.get("confidence") or "reviewed"),
                "evidence": str(segment.get("evidence") or ""),
                "spans": spans,
            }
        )
    return {
        "annotation_mode": "reviewed_gold",
        "route_mode": str(reviewed_payload.get("route_mode") or ""),
        "targets": reviewed_payload.get("targets") or [],
        "segments": segments,
        "validation_warnings": list(reviewed_payload.get("validation_warnings") or []),
        "manual_review_reasons": list(reviewed_payload.get("manual_review_reasons") or []),
    }


def first_marker_index(text: str, markers: list[str], start: int = 0) -> int | None:
    found = [text.find(marker, start) for marker in markers]
    found = [index for index in found if index >= 0]
    if not found:
        return None
    return min(found)


def trim_source_range(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def merge_source_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def clinical_stop_index(text: str, start: int) -> int | None:
    return first_marker_index(
        text,
        [
            "\nTheCaseinContext",
            "\nThe Case in Context",
            "\nDiscussion",
            "\nDISCUSSION",
            "\nMethods",
            "\nMETHODS",
            "\nSelectedReading",
            "\nSelected Reading",
            "\nReferences",
            "\nREFERENCES",
            "\nAcknowledgment",
            "\nAcknowledgement",
            "\nDr.",
        ],
        start,
    )


def summary_clinical_range(text: str) -> tuple[int, int] | None:
    start = first_marker_index(text, ["Summary:", "Abstract", "ABSTRACT"])
    if start is None:
        return None
    nearby = text[start : min(len(text), start + 1800)]
    if not re.search(r"\b(?:patient|man|woman|boy|girl)\b", nearby, flags=re.IGNORECASE):
        return None
    if not re.search(spsd_label_pattern(), nearby, flags=re.IGNORECASE):
        return None
    end = first_marker_index(
        text,
        ["Key Words:", "Key words:", "\nKey Words", "\nStiff-person syndrome is", "\nIntroduction"],
        start + 1,
    )
    if end is None:
        end = clinical_stop_index(text, start + 1)
    if end is None:
        return None
    return trim_source_range(text, start, end)


def case_report_clinical_range(text: str) -> tuple[int, int] | None:
    start = first_marker_index(
        text,
        [
            "CasePresentation",
            "Case Presentation",
            "CASE PRESENTATION",
            "Case presentation",
            "CASE REPORT",
            "Case report",
            "Patient",
            "PATIENT",
            "Case ",
            "CASE ",
        ],
    )
    if start is None:
        return None
    end = clinical_stop_index(text, start + 1)
    if end is None:
        return None
    return trim_source_range(text, start, end)


def patient_discussion_clinical_range(text: str) -> tuple[int, int] | None:
    discussion_start = first_marker_index(text, ["\nDiscussion", "\nDISCUSSION"], 0)
    if discussion_start is None:
        return None
    body_end = first_marker_index(
        text,
        [
            "\nAcknowledgment",
            "\nAcknowledgement",
            "\nReferences",
            "\nREFERENCES",
            "\nAddress correspondence",
        ],
        discussion_start + 1,
    )
    if body_end is None:
        body_end = len(text)
    start = first_marker_index(
        text,
        [
            "The decreased tone",
            "This patient",
            "The patient",
            "Our patient",
            "This case",
            "In conclusion",
        ],
        discussion_start,
    )
    if start is None or start >= body_end:
        return None
    return trim_source_range(text, start, body_end)


def single_patient_clinical_ranges(prepared_source: PreparedSource) -> tuple[list[tuple[int, int]], bool]:
    text = prepared_source.source_text
    ranges = [
        item
        for item in [
            summary_clinical_range(text),
            case_report_clinical_range(text),
            patient_discussion_clinical_range(text),
        ]
        if item is not None
    ]
    if not ranges:
        return [(0, len(text))], False
    return merge_source_ranges(ranges), True


def single_patient_clinical_range(prepared_source: PreparedSource) -> tuple[int, int, bool]:
    ranges, confident = single_patient_clinical_ranges(prepared_source)
    return ranges[0][0], ranges[-1][1], confident


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
        ranges, confident = single_patient_clinical_ranges(prepared_source)
        spans: list[dict[str, Any]] = []
        for start, end in ranges:
            spans.extend(source_range_to_span_payloads(prepared_source, start, end))
        payload = {
            "annotation_mode": "deterministic_clinical_window" if confident else "deterministic_pass_through",
            "segments": [
                {
                    "targets": [target.target_id],
                    "role": role,
                    "confidence": "high" if confident else "low",
                    "evidence": (
                        "Deterministic clinical-window selection for single-patient route."
                        if confident
                        else "Deterministic pass-through used because clinical-window boundaries were uncertain."
                    ),
                    "spans": spans,
                }
            ],
        }
        if not confident:
            payload["validation_warnings"] = ["single_patient_clinical_window_uncertain"]
            payload["manual_review_reasons"] = ["single_patient_clinical_window_uncertain"]
        return payload
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


def unique_text_offsets(block_text: str, selected_text: str) -> tuple[int, int] | None:
    if not selected_text:
        return None
    first = block_text.find(selected_text)
    if first < 0:
        return None
    if block_text.find(selected_text, first + 1) >= 0:
        return None
    return first, first + len(selected_text)


def rejected_span_payload(
    *,
    report: ValidationReport,
    logical_segment_id: str,
    targets: list[str],
    role: str,
    confidence: str,
    evidence: str,
    block: SourceBlock | None,
    block_id: str,
    start: int | None,
    end: int | None,
    selected_text: str,
    reason: str,
) -> dict[str, Any]:
    requested_offsets: dict[str, Any] = {"start": start, "end": end}
    source_offsets: dict[str, Any] = {"start": "", "end": ""}
    if block is not None and start is not None and end is not None:
        source_offsets = {
            "start": block.source_start + start,
            "end": block.source_start + end,
        }
    return {
        "rejected_segment_id": f"r{len(report.rejected_spans or []) + 1:04d}",
        "logical_segment_id": logical_segment_id,
        "targets": targets,
        "role": role,
        "confidence": confidence,
        "evidence": evidence,
        "source_block_id": block_id,
        "requested_offsets": requested_offsets,
        "source_offsets": source_offsets,
        "selected_text": selected_text,
        "selected_text_sha256": sha256_text(selected_text),
        "reason": reason,
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
        targets_valid = True
        for target_id in targets:
            if target_id == "unknown":
                if role != "uncertain":
                    report.add_error(f"unknown_target_requires_uncertain_role:{logical_segment_id}")
                    targets_valid = False
                continue
            if target_id not in declared_ids:
                report.add_error(f"unknown_target:{logical_segment_id}:{target_id}")
                targets_valid = False
        confidence = str(item.get("confidence") or "").strip() or "unspecified"
        evidence = str(item.get("evidence") or "").strip()
        for span in item.get("spans") or []:
            block_id = str(span.get("block_id") or "").strip()
            block = blocks_by_id.get(block_id)
            if block is None:
                reason = f"unknown_block:{logical_segment_id}:{block_id}"
                report.add_error(reason)
                report.add_rejected_span(
                    rejected_span_payload(
                        report=report,
                        logical_segment_id=logical_segment_id,
                        targets=targets,
                        role=role,
                        confidence=confidence,
                        evidence=evidence,
                        block=None,
                        block_id=block_id,
                        start=parse_int(span.get("start_offset")),
                        end=parse_int(span.get("end_offset")),
                        selected_text=str(span.get("selected_text") or ""),
                        reason=reason,
                    )
                )
                continue
            start = parse_int(span.get("start_offset"))
            end = parse_int(span.get("end_offset"))
            selected_text = str(span.get("selected_text") or "")
            if start is None or end is None:
                reason = f"invalid_offsets:{logical_segment_id}:{block_id}"
                report.add_error(reason)
                report.add_rejected_span(
                    rejected_span_payload(
                        report=report,
                        logical_segment_id=logical_segment_id,
                        targets=targets,
                        role=role,
                        confidence=confidence,
                        evidence=evidence,
                        block=block,
                        block_id=block_id,
                        start=start,
                        end=end,
                        selected_text=selected_text,
                        reason=reason,
                    )
                )
                continue
            if start < 0 or end < start or end > len(block.text):
                relocated = unique_text_offsets(block.text, selected_text)
                if relocated is None:
                    reason = f"offsets_out_of_bounds:{logical_segment_id}:{block_id}:{start}:{end}"
                    report.add_error(reason)
                    report.add_rejected_span(
                        rejected_span_payload(
                            report=report,
                            logical_segment_id=logical_segment_id,
                            targets=targets,
                            role=role,
                            confidence=confidence,
                            evidence=evidence,
                            block=block,
                            block_id=block_id,
                            start=start,
                            end=end,
                            selected_text=selected_text,
                            reason=reason,
                        )
                    )
                    continue
                old_start, old_end = start, end
                start, end = relocated
                report.add_warning(
                    f"relocated_span:{logical_segment_id}:{block_id}:{old_start}:{old_end}->{start}:{end}"
                )
                report.add_span_adjustment(
                    {
                        "logical_segment_id": logical_segment_id,
                        "source_block_id": block_id,
                        "requested_offsets": {"start": old_start, "end": old_end},
                        "relocated_offsets": {"start": start, "end": end},
                        "selected_text_sha256": sha256_text(selected_text),
                    }
                )
            actual_text = block.text[start:end]
            if actual_text != selected_text:
                relocated = unique_text_offsets(block.text, selected_text)
                if relocated is None:
                    reason = f"offset_text_mismatch:{logical_segment_id}:{block_id}:{start}:{end}"
                    report.add_error(reason)
                    report.add_rejected_span(
                        rejected_span_payload(
                            report=report,
                            logical_segment_id=logical_segment_id,
                            targets=targets,
                            role=role,
                            confidence=confidence,
                            evidence=evidence,
                            block=block,
                            block_id=block_id,
                            start=start,
                            end=end,
                            selected_text=selected_text,
                            reason=reason,
                        )
                    )
                    continue
                old_start, old_end = start, end
                start, end = relocated
                actual_text = block.text[start:end]
                report.add_warning(
                    f"relocated_span:{logical_segment_id}:{block_id}:{old_start}:{old_end}->{start}:{end}"
                )
                report.add_span_adjustment(
                    {
                        "logical_segment_id": logical_segment_id,
                        "source_block_id": block_id,
                        "requested_offsets": {"start": old_start, "end": old_end},
                        "relocated_offsets": {"start": start, "end": end},
                        "selected_text_sha256": sha256_text(selected_text),
                    }
                )
            if not targets_valid:
                report.add_rejected_span(
                    rejected_span_payload(
                        report=report,
                        logical_segment_id=logical_segment_id,
                        targets=targets,
                        role=role,
                        confidence=confidence,
                        evidence=evidence,
                        block=block,
                        block_id=block_id,
                        start=start,
                        end=end,
                        selected_text=selected_text,
                        reason=f"invalid_targets:{logical_segment_id}",
                    )
                )
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

    physical_segments = apply_table_relevance_heuristics(
        prepared_source=prepared_source,
        segments=physical_segments,
        report=report,
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


def table_row_ranges_for_relevant_ids(
    *,
    block: SourceBlock,
    relevant_ids: set[str],
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for line in block.text.splitlines(keepends=True):
        stripped = line.strip()
        line_start = cursor
        line_end = cursor + len(line.rstrip("\n"))
        cursor += len(line)
        if not stripped:
            continue
        match = re.match(r"^(?:case\s*)?(\d+)\b", stripped, flags=re.IGNORECASE)
        direct_spsd = re.search(r"\b(?:SPSD|SPS|stiff[- ](?:person|man))\b", stripped, flags=re.IGNORECASE)
        has_row_content = bool(match and stripped[match.end() :].strip())
        direct_diagnosis_row = bool(direct_spsd and re.search(r"\d", stripped))
        if (match and match.group(1) in relevant_ids and has_row_content) or direct_diagnosis_row:
            ranges.append((line_start, line_end))
    return ranges


def apply_table_relevance_heuristics(
    *,
    prepared_source: PreparedSource,
    segments: list[PhysicalSegment],
    report: ValidationReport,
) -> list[PhysicalSegment]:
    relevant_ids = explicit_spsd_case_ids(prepared_source.source_text)
    if not relevant_ids:
        return segments
    blocks_by_id = {block.block_id: block for block in prepared_source.blocks}
    adjusted: list[PhysicalSegment] = []
    for segment in segments:
        if "table" not in segment.text.lower():
            adjusted.append(segment)
            continue
        block = blocks_by_id.get(segment.block_id)
        if block is None:
            adjusted.append(segment)
            continue
        row_ranges = table_row_ranges_for_relevant_ids(block=block, relevant_ids=relevant_ids)
        row_ranges = [
            (start, end)
            for start, end in row_ranges
            if segment.source_start <= block.source_start + start < block.source_start + end <= segment.source_end
        ]
        if not row_ranges:
            reason = f"ambiguous_table_row_mapping:{segment.segment_id}"
            report.add_warning(reason)
            report.add_review_reason(reason)
            adjusted.append(segment)
            continue
        report.add_warning(f"trimmed_table_to_relevant_rows:{segment.segment_id}")
        for start, end in row_ranges:
            adjusted.append(
                PhysicalSegment(
                    segment_id="",
                    logical_segment_id=segment.logical_segment_id,
                    targets=segment.targets,
                    role=segment.role,
                    text=block.text[start:end],
                    source_start=block.source_start + start,
                    source_end=block.source_start + end,
                    block_id=segment.block_id,
                    confidence=segment.confidence,
                    evidence=segment.evidence,
                )
            )
    return [
        PhysicalSegment(
            segment_id=f"s{index:04d}",
            logical_segment_id=segment.logical_segment_id,
            targets=segment.targets,
            role=segment.role,
            text=segment.text,
            source_start=segment.source_start,
            source_end=segment.source_end,
            block_id=segment.block_id,
            confidence=segment.confidence,
            evidence=segment.evidence,
        )
        for index, segment in enumerate(sorted(adjusted, key=lambda item: (item.source_start, item.source_end)), start=1)
    ]


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


def apply_group_patient_override(
    *,
    route: str,
    targets: list[Target],
    segments: list[PhysicalSegment],
    stage06_prior: Stage06Prior,
    report: ValidationReport,
) -> tuple[str, list[Target], bool]:
    if route != "group":
        return route, targets, False
    annotation_patients = [
        target
        for target in targets
        if target.target_kind == "patient" and target.source == "stage07_annotation"
    ]
    if not annotation_patients:
        return route, targets, False
    expected_count = stage06_prior.final_count
    if expected_count is not None and len(annotation_patients) != expected_count:
        report.add_error(
            f"stage07_patient_target_count_mismatch:{len(annotation_patients)}:{expected_count}"
        )
    group_targets_with_segments = [
        target
        for target in targets
        if target.target_kind == "group" and relevant_segments_for_target(target, segments)
    ]
    if group_targets_with_segments:
        report.add_warning("group_route_with_source_backed_patient_targets")
        return route, targets, True
    updated_targets = [
        target
        for target in targets
        if not (target.target_kind == "group" and target.source == "stage06_group_prior")
    ]
    report.add_warning("route_override:group_to_individual_case_split:source_backed_patient_targets")
    return "individual_case_split", updated_targets, True


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
        "manual_review_reasons": list(report.review_reasons or []),
        "span_adjustments": list(report.span_adjustments or []),
        "rejected_spans": list(report.rejected_spans or []),
    }


def annotation_uses_model(annotation_mode: str) -> bool:
    return annotation_mode not in {"deterministic_pass_through", "deterministic_clinical_window", "reviewed_gold"}


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

    route_decision = resolve_route_decision(
        route=route,
        stage06_prior=stage06_prior,
        prepared_source=prepared_source,
    )
    route = route_decision.route
    annotation_route_diverged = False
    if annotation_payload is not None:
        annotation_route = str(annotation_payload.get("route_mode") or "").strip()
        if annotation_route in {"individual", "individual_case_split", "group"} and annotation_route != route:
            route = annotation_route
            annotation_route_diverged = True

    base_targets = initial_targets(
        route=route,
        stage06_prior=stage06_prior,
        recovered_target_labels=route_decision.recovered_target_labels,
    )
    annotation_mode = "stage07_span_metadata"
    if annotation_payload is None:
        annotation_payload = deterministic_annotation_for_route(
            prepared_source=prepared_source,
            targets=base_targets,
            route=route,
        )
    annotation_mode = str(annotation_payload.get("annotation_mode") or annotation_mode).strip() or annotation_mode

    preliminary_report = ValidationReport()
    allow_annotation_patient_targets = (
        route == "group"
        and stage06_prior.final_count is not None
        and 1 < stage06_prior.final_count <= 20
    )
    targets, target_diverged = merge_declared_targets(
        base_targets,
        annotation_payload,
        preliminary_report,
        allow_annotation_patient_targets=allow_annotation_patient_targets,
    )
    segments, validation_report = validate_annotation_payload(
        annotation_payload=annotation_payload,
        prepared_source=prepared_source,
        declared_targets=targets,
    )
    for error in preliminary_report.errors or []:
        validation_report.add_error(error)
    for warning in preliminary_report.warnings or []:
        validation_report.add_warning(warning)
    for warning in route_decision.warnings:
        validation_report.add_warning(warning)
    for warning in annotation_payload.get("validation_warnings") or []:
        validation_report.add_warning(str(warning))
    for reason in route_decision.manual_review_reasons:
        validation_report.add_review_reason(reason)
    for reason in annotation_payload.get("manual_review_reasons") or []:
        validation_report.add_review_reason(str(reason))

    annotated_text = insert_xml_tags(prepared_source.source_text, segments)
    validate_roundtrip(prepared_source.source_text, annotated_text, validation_report)
    route, targets, route_diverged = apply_group_patient_override(
        route=route,
        targets=targets,
        segments=segments,
        stage06_prior=stage06_prior,
        report=validation_report,
    )
    coverage_reasons = missing_target_reasons(targets, segments)
    for reason in coverage_reasons:
        validation_report.add_warning(reason)
    manual_review_reasons = list(validation_report.errors or [])
    manual_review_reasons.extend(validation_report.review_reasons or [])
    manual_review_reasons.extend(coverage_reasons)
    paper_ready = not validation_report.failed and not coverage_reasons and not validation_report.review_reasons
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
    stage06_diverged = bool(
        target_diverged or route_diverged or route_decision.diverged or annotation_route_diverged
    )
    divergence_dimensions = ["target_inventory"]
    if route_diverged or route_decision.diverged or annotation_route_diverged:
        divergence_dimensions.append("route_mode")
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
        annotation_model=annotation_model if annotation_uses_model(annotation_mode) else "none",
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
            "annotation_model": annotation_model if annotation_uses_model(annotation_mode) else "none",
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
            "dimensions": divergence_dimensions,
            "reason": "Stage 07 declared source-backed targets beyond the Stage 06 route prior.",
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
