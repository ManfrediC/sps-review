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
TEXT_PROCEEDINGS_READY_DIR = REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIMMED_LLM_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed_llm"
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
EXTERNAL_REPORT_LABEL_CONTEXT_RE = re.compile(
    r"^\W*in\s+(?:their|his|her|the|this|that)\s+reports?\b",
    re.IGNORECASE,
)
COMPARISON_LABEL_CONTEXT_RE = re.compile(
    r"(?:similar\s+to(?:\s+that\s+of)?|same\s+as|compared\s+(?:with|to)|unlike|as\s+in|that\s+of)\s*$",
    re.IGNORECASE,
)
EXTERNAL_REPORT_RE = re.compile(
    r"\b(?:previously\s+described|reported\s+by|case\s+\d+\s+of|literature\s+case|"
    r"previous\s+reports?|their\s+reports?)\b",
    re.IGNORECASE,
)
COMPARATOR_SCOPE_RE = re.compile(
    r"\b(?:control\s+(?:serum|sera|samples?|subjects?|patients?|group)|normal\s+subjects?|healthy\s+controls?|comparator|"
    r"other\s+patients?|patients\s+with\s+other\s+neurological\s+diseases)\b",
    re.IGNORECASE,
)
CURRENT_SAMPLE_RE = re.compile(
    r"\b(?:serum|sera|csf|cerebrospinal\s+fluid|sample|samples|specimen|specimens|"
    r"tissue|tumou?r|plasma)\b",
    re.IGNORECASE,
)
ASSAY_CONTEXT_RE = re.compile(
    r"\b(?:assay|tested|testing|western\s+blot|immunoblot|immuno|stain|staining|"
    r"antibod|elisa|recognised|recognized)\b",
    re.IGNORECASE,
)
GROUP_SCOPE_RE = re.compile(
    r"\b(?:all|both|the)\s+(?:\d+\s+)?(?:patients|cases)\b|"
    r"\b(?:the\s+)?(?:\d+|three|two|four|five)\s+(?:patients|cases)\b",
    re.IGNORECASE,
)
SUBSET_SCOPE_RE = re.compile(
    r"\b(?:patients?|cases?)\s+(?:\d+|[1Il|])(?:\s*(?:,|and|&)\s*(?:\d+|[1Il|]))+\b",
    re.IGNORECASE,
)
PATIENT_CASE_LABEL_RE = re.compile(
    r"\b(?:patient|case|pt|subject)\s*(?:no\.?|number)?\s*(?:\d{1,3}|[IVXivx]+|[Il|])\b",
    re.IGNORECASE,
)
OCR_DIGIT_PATTERNS = {
    "0": r"[0O]",
    "1": r"[1Il|]",
    "2": r"[2Z]",
    "5": r"[5S]",
}
ORDINAL_ALIASES = {
    1: ("first patient", "patient one", "first case", "case one"),
    2: ("second patient", "patient two", "second case", "case two"),
    3: ("third patient", "patient three", "third case", "case three"),
    4: ("fourth patient", "patient four", "fourth case", "case four"),
    5: ("fifth patient", "patient five", "fifth case", "case five"),
}
AUDIT_ONLY_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:abstract\s*)?(?:references?|bibliography|materials?\s+and\s+methods?|methods?|acknowledg(?:e)?ments?)(?:\s*[:.\-]\s+|\s*$)",
    re.IGNORECASE,
)
AGE_TOKEN_PATTERN = r"(?:y\s*e\s*a\s*r|y\s*r)s?"
AGE_ANCHOR_RE = re.compile(
    rf"\b(?:\d{{1,3}}\s*(?:[- ]\s*)?{AGE_TOKEN_PATTERN}\s*(?:[- ]\s*)?old"
    rf"|aged\s+\d{{1,3}}\s*{AGE_TOKEN_PATTERN}"
    rf"|(?:at\s+)?the\s+age\s+of\s+\d{{1,3}}\s*{AGE_TOKEN_PATTERN})\b",
    re.IGNORECASE,
)
CASE_HEADING_RE = re.compile(r"(?:^|\n)\s*Case\s+\d+\b", re.IGNORECASE)
PATIENT_HISTORY_HEADING_RE = re.compile(r"(?:^|\n)\s*(?:Patient|Case)\s+\d+\b", re.IGNORECASE)
SPSD_PHENOTYPE_RE = re.compile(
    r"\b(?:stiffness|rigidity|spasms?|myoclonus|hyperlordosis)\b",
    re.IGNORECASE,
)
AUTHOR_DEPARTMENT_RE = re.compile(
    r"\n[A-Z][A-Za-z .'\-]+,\s*(?:MD|M\.D\.|PhD|Ph\.D\.)\s*\nDepartment",
    re.IGNORECASE,
)
AUTHOR_CREDENTIAL_BLOCK_RE = re.compile(
    r"\n[A-Z][A-Za-z .'\-]+,\s*(?:MD|M\.D\.|PhD|Ph\.D\.)"
    r"\s*\n[A-Z][A-Za-z .'\-]+,\s*(?:MD|M\.D\.|PhD|Ph\.D\.)",
    re.IGNORECASE,
)
STAR_AUTHOR_DEPARTMENT_RE = re.compile(
    r"\n\*[A-Z][^\n]{0,120}\nDepartment",
    re.IGNORECASE,
)
LETTER_AUTHOR_DEPARTMENT_RE = re.compile(
    r"\n[A-Z]\s+[A-Z][A-Za-z.'\-]+[^\n]{0,100}\n"
    r"(?:[A-Z]\s+[A-Z][A-Za-z.'\-]+[^\n]{0,100}\n){0,4}Department of",
)
GENERIC_SPSD_DISCUSSION_RE = re.compile(
    r"(?:\n|\. )(?:Patients with SPS|P\s*ati\s*ents\s+wi\s*th\s+SP\s*S)\s+"
    r"(?:and\s+positive\s+anti-GAD\s+auto-?\s*antibodies\s+)?"
    r"(?:are|were|have|usually|typically|may|might|can|often|should|require)\b",
    re.IGNORECASE,
)


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
    "stage07_scope",
    "stage07_status",
    "unit_id",
    "unit_type",
    "unit_source",
    "defer_reason",
    "eligibility_basis",
    "text_path",
    "model_audit_status",
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
class SourceUnit:
    unit_id: str
    unit_type: str
    text: str
    source_start: int
    source_end: int
    page_index: int | None
    block_spans: list[dict[str, Any]]


@dataclass(frozen=True)
class UnitFeatures:
    unit_id: str
    section: str
    explicit_target_mentions: tuple[str, ...]
    candidate_targets: tuple[str, ...]
    role_hint: str
    confidence_hint: str
    reason_codes: tuple[str, ...]
    risk_flags: tuple[str, ...]


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
    source_unit_ids: tuple[str, ...] = ()


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


def source_text_from_json_path(path: Path) -> str:
    record = load_json(path)
    page_chunks = [
        normalise_page_text(str(page.get("text") or ""))
        for page in record.get("pages") or []
        if normalise_page_text(str(page.get("text") or "")).strip()
    ]
    return "\n\n".join(page_chunks).strip()


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


def truncated_trim_footer_interruption(text: str) -> bool:
    tail = text[-1200:]
    return bool(
        re.search(
            r"\b(?:were|was|are|is|with|and|or|of|to|from)\s*\n\*?(?:Dept\.|Department\b)",
            tail,
            flags=re.IGNORECASE,
        )
        and re.search(r"\bReceived\s*:", tail, flags=re.IGNORECASE)
    )


def truncated_trim_mid_case(text: str) -> bool:
    stripped = text.rstrip()
    if len(stripped) < 1500 or re.search(r"[.!?)]\s*$", stripped):
        return False
    return bool(
        re.search(r"\b(?:Case report|CASE REPORT|Case presentation|CASE DESCRIPTION)\b", stripped[:2500])
        and re.search(spsd_label_pattern(), stripped, flags=re.IGNORECASE)
    )


def full_text_replacement_for_incomplete_trim(paper_id: str, path: Path) -> Path | None:
    full_path = TEXT_DIR / f"{paper_id}.json"
    if not full_path.exists() or full_path.resolve() == path.resolve():
        return None
    if (
        paper_id == "5808"
        and path.parent.name == "text_proceedings_ready"
        and "Patient Case" in source_text_from_json_path(full_path)
        and "Patient Case" not in source_text_from_json_path(path)
    ):
        return full_path
    if path.parent.name != "text_trimmed":
        return None
    trimmed_text = source_text_from_json_path(path)
    full_text = source_text_from_json_path(full_path)
    if (
        paper_id == "1764"
        and "Rituximab improves not only back" in full_text
        and "2. 1. Case presentation" in full_text
        and "2. 1. Case presentation" not in trimmed_text
    ):
        return full_path
    if (
        paper_id == "1918"
        and "F59. Spasmodic reflex myoclonus" in full_text
        and "Results: The results demonstrated" in full_text
        and "Results: The results demonstrated" not in trimmed_text
    ):
        return full_path
    if (
        paper_id == "6796"
        and "Clinical and cell biology analysis of stiff person" in trimmed_text
        and "Results: Structure of the muscle tissue was normal" in full_text
        and "Results: Structure of the muscle tissue was normal" not in trimmed_text
    ):
        return full_path
    if (
        paper_id == "11903"
        and "Pediatric stiff limb syndrome with polyautoimmunity" in trimmed_text
        and "3. Case presentation" in full_text
        and "3. Case presentation" not in trimmed_text
    ):
        return full_path
    trim_is_title_fragment = (
        len(trimmed_text.strip()) <= 800
        and AGE_ANCHOR_RE.search(trimmed_text) is None
    )
    trim_is_abstract_only = (
        len(trimmed_text.strip()) <= 1200
        and re.search(r"\bAbstract\b", trimmed_text, flags=re.IGNORECASE)
        and AGE_ANCHOR_RE.search(trimmed_text) is None
    )
    trim_is_mid_case_truncation = truncated_trim_mid_case(trimmed_text)
    if not truncated_trim_footer_interruption(trimmed_text) and not trim_is_mid_case_truncation and not (
        (trim_is_title_fragment or trim_is_abstract_only)
        and len(full_text) > len(trimmed_text) + 2000
        and AGE_ANCHOR_RE.search(full_text)
        and re.search(spsd_label_pattern(), full_text, flags=re.IGNORECASE)
    ):
        return None
    if trim_is_mid_case_truncation and (
        len(full_text) <= len(trimmed_text) + 2000
        or not AGE_ANCHOR_RE.search(full_text)
        or not re.search(spsd_label_pattern(), full_text, flags=re.IGNORECASE)
    ):
        return None
    if len(full_text) <= len(trimmed_text) + 1000:
        return None
    return full_path


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
            full_text_replacement = full_text_replacement_for_incomplete_trim(paper_id, path)
            if full_text_replacement is not None:
                return full_text_replacement
            return path
    for fallback_dir in (
        TEXT_PROCEEDINGS_READY_DIR,
        TEXT_TRIMMED_LLM_DIR,
        TEXT_TRIMMED_DIR,
        TEXT_DIR,
    ):
        fallback = fallback_dir / f"{paper_id}.json"
        if fallback.exists():
            if paper_id == "5808":
                full_text_replacement = full_text_replacement_for_incomplete_trim(paper_id, fallback)
                if full_text_replacement is not None:
                    return full_text_replacement
            return fallback
    fallback = TEXT_DIR / f"{paper_id}.json"
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
    return (
        r"(?:\b(?:SPSD|SPS|SMS|SLS)\b|stiff[- ]?(?:person|man|limb|leg|trunk)"
        r"|stiff[- ]?three[- ]?limbs?"
        r"|stift[- ]man"
        r"|progressive\s+encephalomyelitis\s+with\s+rigidity"
        r"|sindrome\s+de\s+(?:la\s+)?persona\s+rigida)"
    )


def case_report_marker_count(text: str) -> int:
    return sum(
        1
        for marker in [
            "REPORT OF A CASE",
            "Report of a Case",
            "CASE REPORT",
            "Case Report",
            "Case report",
        ]
        for _ in re.finditer(re.escape(marker), text)
    )


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
    for index, item in enumerate(annotation_payload.get("targets") or [], start=1):
        if not isinstance(item, dict):
            target_reference = str(item or "").strip()
            if target_reference in targets_by_id:
                report.add_warning(f"ignored_declared_target_reference:{target_reference}")
            else:
                report.add_error(f"invalid_declared_target_payload:t{index}")
            continue
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


def compact_whitespace(value: str) -> str:
    return " ".join(str(value or "").split())


def ocr_digit_pattern(value: str) -> str:
    return "".join(OCR_DIGIT_PATTERNS.get(char, re.escape(char)) for char in str(value or ""))


def tolerant_label_pattern(label: str) -> str:
    """Build a patient-label regex that tolerates common OCR digit confusions."""

    parts: list[str] = []
    for token in str(label or "").strip().split():
        if token.isdigit():
            parts.append(ocr_digit_pattern(token))
        elif token == "1":
            parts.append(r"[1Il|]")
        elif token == "0":
            parts.append(r"[0O]")
        else:
            parts.append(re.escape(token))
    return r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)"


def target_alias_patterns(target: Target) -> list[re.Pattern[str]]:
    """Return OCR-tolerant aliases for a declared patient/case target."""

    label = str(target.label or "").strip()
    if not label:
        return []
    patterns = [tolerant_label_pattern(label)]
    parts = label.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        number = int(parts[-1])
        digit_pattern = ocr_digit_pattern(parts[-1])
        kind = re.escape(parts[0])
        patterns.extend(
            [
                rf"(?<!\w){kind}s?\s+{digit_pattern}(?!\w)",
                rf"(?<!\w)(?:Pt|Subject)\s*{digit_pattern}(?!\w)",
                rf"(?<!\w)Case\s+{digit_pattern}(?!\w)",
            ]
        )
        patterns.extend(rf"(?<!\w){re.escape(alias)}(?!\w)" for alias in ORDINAL_ALIASES.get(number, ()))
    return [re.compile(pattern, re.IGNORECASE) for pattern in dict.fromkeys(patterns)]


def label_mentions_current_target(text: str, target: Target) -> bool:
    return any(pattern.search(text) for pattern in target_alias_patterns(target))


def label_mentions_other_current_target(text: str, target: Target) -> bool:
    """Return true when text appears to leak another current-paper label."""

    for pattern in target_alias_patterns(target):
        for match in pattern.finditer(text):
            preceding_context = text[max(0, match.start() - 64) : match.start()]
            following_context = text[match.end() : match.end() + 64]
            if COMPARISON_LABEL_CONTEXT_RE.search(preceding_context):
                continue
            if EXTERNAL_REPORT_LABEL_CONTEXT_RE.search(following_context):
                continue
            return True
    return False


def non_empty_line_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^\r\n]+", text):
        line = match.group(0)
        stripped = line.strip()
        if not stripped:
            continue
        start = match.start() + len(line) - len(line.lstrip())
        end = match.end() - (len(line) - len(line.rstrip()))
        if start < end:
            spans.append((start, end, text[start:end]))
    return spans


def table_like_line(text: str) -> bool:
    stripped = compact_whitespace(text)
    if not stripped or len(stripped) < 12:
        return False
    if "\t" in text:
        return True
    if len(re.findall(r"\s{2,}", text)) >= 2:
        return True
    tokens = stripped.split()
    digit_tokens = sum(1 for token in tokens if any(char.isdigit() for char in token))
    return len(tokens) >= 5 and digit_tokens >= 2


def table_like_block(line_spans: list[tuple[int, int, str]]) -> bool:
    if len(line_spans) < 2:
        return False
    table_like_count = sum(1 for _, _, line in line_spans if table_like_line(line))
    if table_like_count < 3:
        return False
    return table_like_count / len(line_spans) >= 0.4


def heading_like_line(text: str) -> bool:
    stripped = compact_whitespace(text)
    if not stripped or len(stripped) > 90:
        return False
    if re.fullmatch(r"(?:case|patient)\s+\w+[:.\-]?", stripped, flags=re.IGNORECASE):
        return True
    if stripped.endswith("."):
        return False
    letters = [char for char in stripped if char.isalpha()]
    return bool(letters) and sum(1 for char in letters if char.isupper()) / len(letters) > 0.65


def table_heading_line(text: str) -> bool:
    stripped = compact_whitespace(text)
    return bool(re.match(r"^(?:table|fig(?:ure)?)\s+\d+\b", stripped, flags=re.IGNORECASE))


def article_metadata_line(text: str) -> bool:
    stripped = compact_whitespace(text)
    if not stripped:
        return False
    return bool(
        re.match(
            r"^(?:from the department|reprint requests?|address correspondence|movement disorders,?\s+vol\.)\b",
            stripped,
            flags=re.IGNORECASE,
        )
        or "©" in stripped
    )


def case_boundary_line(text: str) -> bool:
    stripped = compact_whitespace(text)
    return bool(
        re.fullmatch(
            r"[\"'“”‘’]*\s*(?:case|patient)\s+[A-Za-z0-9IVXivx]+[:.\-]?",
            stripped,
            flags=re.IGNORECASE,
        )
        or re.match(
            r"^[\"'“”‘’]*\s*(?:case|patient)\s+[A-Za-z0-9IVXivx]+[:.\-]\s+\S",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def scope_sensitive_text(text: str) -> bool:
    """Return true when a unit should be split for attribution clarity."""

    compact = compact_whitespace(text)
    if not compact:
        return False
    labels = {match.group(0).casefold() for match in PATIENT_CASE_LABEL_RE.finditer(compact)}
    has_target_label = bool(labels)
    has_group_scope = bool(GROUP_SCOPE_RE.search(compact))
    has_subset_scope = bool(SUBSET_SCOPE_RE.search(compact))
    has_comparator = bool(COMPARATOR_SCOPE_RE.search(compact))
    has_external = bool(EXTERNAL_REPORT_RE.search(compact))
    return bool(
        len(labels) >= 2
        or (has_target_label and has_external)
        or (has_group_scope and has_comparator)
        or (has_group_scope and has_subset_scope)
        or (has_subset_scope and has_comparator)
    )


def sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for match in re.finditer(r"(?<=[.!?])\s+", text):
        end = match.end()
        piece = text[cursor:end].strip()
        if piece:
            start = cursor + len(text[cursor:end]) - len(text[cursor:end].lstrip())
            finish = end - (len(text[cursor:end]) - len(text[cursor:end].rstrip()))
            spans.append((start, finish, text[start:finish]))
        cursor = end
    tail = text[cursor:].strip()
    if tail:
        start = cursor + len(text[cursor:]) - len(text[cursor:].lstrip())
        end = len(text) - (len(text[cursor:]) - len(text[cursor:].rstrip()))
        spans.append((start, end, text[start:end]))
    return spans


def semicolon_clause_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for match in re.finditer(r";\s+", text):
        end = match.start()
        piece = text[cursor:end].strip()
        if piece:
            start = cursor + len(text[cursor:end]) - len(text[cursor:end].lstrip())
            finish = end - (len(text[cursor:end]) - len(text[cursor:end].rstrip()))
            spans.append((start, finish, text[start:finish]))
        cursor = match.end()
    tail = text[cursor:].strip()
    if tail:
        start = cursor + len(text[cursor:]) - len(text[cursor:].lstrip())
        end = len(text) - (len(text[cursor:]) - len(text[cursor:].rstrip()))
        spans.append((start, end, text[start:end]))
    return spans


def grouped_text_spans(
    spans: list[tuple[int, int, str]],
    *,
    max_chars: int,
) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    group_start: int | None = None
    group_end: int | None = None
    for start, end, text in spans:
        if group_start is None:
            group_start = start
            group_end = end
            continue
        next_length = end - group_start
        if next_length <= max_chars:
            group_end = end
            continue
        groups.append((group_start, int(group_end)))
        group_start = start
        group_end = end
    if group_start is not None and group_end is not None:
        groups.append((group_start, group_end))
    return groups


def source_scope_subspans(text: str, *, max_chars: int) -> list[tuple[int, int]]:
    if not scope_sensitive_text(text):
        return [(0, len(text))]
    sentences = sentence_spans(text)
    if len(sentences) > 1:
        return [(start, end) for start, end, _ in sentences]
    clauses = semicolon_clause_spans(text)
    if len(clauses) > 1:
        return [(start, end) for start, end, _ in clauses]
    return [(0, len(text))]


def split_line_spans_for_units(
    spans: list[tuple[int, int, str]],
    *,
    consumed_indices: set[int],
) -> list[list[tuple[int, int, str]]]:
    groups: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    for index, span in enumerate(spans):
        if index in consumed_indices:
            if current:
                groups.append(current)
                current = []
            continue
        if current and case_boundary_line(span[2]):
            groups.append(current)
            current = []
        current.append(span)
    if current:
        groups.append(current)
    return groups


def build_source_units(
    prepared_source: PreparedSource,
    *,
    max_unit_chars: int = 900,
) -> list[SourceUnit]:
    units: list[SourceUnit] = []

    def append_unit(unit_type: str, start: int, end: int, page_index: int | None) -> None:
        if start >= end:
            return
        text = prepared_source.source_text[start:end]
        if not text.strip():
            return
        units.append(
            SourceUnit(
                unit_id=f"u{len(units) + 1:04d}",
                unit_type=unit_type,
                text=text,
                source_start=start,
                source_end=end,
                page_index=page_index,
                block_spans=source_range_to_span_payloads(prepared_source, start, end),
            )
        )

    def add_unit(unit_type: str, start: int, end: int, page_index: int | None) -> None:
        if start >= end:
            return
        text = prepared_source.source_text[start:end]
        if unit_type in {"paragraph", "line_group", "sentence_group"}:
            for rel_start, rel_end in source_scope_subspans(text, max_chars=max_unit_chars):
                sub_start, sub_end = trim_source_range(prepared_source.source_text, start + rel_start, start + rel_end)
                append_unit(unit_type, sub_start, sub_end, page_index)
            return
        append_unit(unit_type, start, end, page_index)

    for block in prepared_source.blocks:
        line_spans = non_empty_line_spans(block.text)
        if table_like_block(line_spans):
            for line_start, line_end, _ in line_spans:
                add_unit("table_row", block.source_start + line_start, block.source_start + line_end, block.page_index)
            continue

        if len(line_spans) >= 2:
            consumed_lines: set[int] = set()
            for index, (line_start, line_end, line_text) in enumerate(line_spans):
                if article_metadata_line(line_text):
                    add_unit("metadata", block.source_start + line_start, block.source_start + line_end, block.page_index)
                    consumed_lines.add(index)
                elif (heading_like_line(line_text) or table_heading_line(line_text)) and not case_boundary_line(line_text):
                    add_unit("heading", block.source_start + line_start, block.source_start + line_end, block.page_index)
                    consumed_lines.add(index)
            remaining_groups = split_line_spans_for_units(line_spans, consumed_indices=consumed_lines)
            if remaining_groups and block.source_end - block.source_start <= max_unit_chars and len(remaining_groups) == 1:
                remaining = remaining_groups[0]
                add_unit("paragraph", block.source_start + remaining[0][0], block.source_start + remaining[-1][1], block.page_index)
                continue
            for group in remaining_groups:
                for line_start, line_end in grouped_text_spans(group, max_chars=max_unit_chars):
                    add_unit("line_group", block.source_start + line_start, block.source_start + line_end, block.page_index)
            continue

        if len(block.text) <= max_unit_chars:
            add_unit("paragraph", block.source_start, block.source_end, block.page_index)
            continue
        for span_start, span_end in grouped_text_spans(sentence_spans(block.text), max_chars=max_unit_chars):
            add_unit("sentence_group", block.source_start + span_start, block.source_start + span_end, block.page_index)

    return units


def source_units_payload(
    units: list[SourceUnit],
    *,
    include_block_spans: bool = True,
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for unit in units:
        item = {
            "unit_id": unit.unit_id,
            "unit_type": unit.unit_type,
            "page_index": unit.page_index,
            "source_offsets": {"start": unit.source_start, "end": unit.source_end},
            "text": unit.text,
        }
        if include_block_spans:
            item["block_spans"] = unit.block_spans
        payload.append(item)
    return payload


def section_from_heading(text: str) -> str | None:
    compact = compact_whitespace(text).casefold()
    if not compact:
        return None
    if re.match(r"^(?:case|patient)\b", compact):
        return "case"
    if "abstract" == compact or compact.startswith("abstract"):
        return "abstract"
    if re.search(r"\b(?:materials?\s+and\s+methods?|methods?|patients\s+and\s+methods)\b", compact):
        return "methods"
    if re.search(r"\b(?:results?|findings?|western\s+blotting|immunohistochemistry)\b", compact):
        return "results"
    if re.search(r"\b(?:discussion|comment|conclusions?)\b", compact):
        return "discussion"
    if re.search(r"\b(?:references?|bibliography|acknowledg)", compact):
        return "references"
    return None


def all_current_target_ids(targets: list[Target], kind: str = "patient") -> tuple[str, ...]:
    return tuple(target.target_id for target in targets if target.target_kind == kind)


def explicit_target_mentions(text: str, targets: list[Target]) -> tuple[str, ...]:
    return tuple(
        target.target_id
        for target in targets
        if label_mentions_current_target(text, target)
    )


def current_patient_sample_context(text: str, targets: list[Target]) -> bool:
    if not CURRENT_SAMPLE_RE.search(text) or not ASSAY_CONTEXT_RE.search(text):
        return False
    if explicit_target_mentions(text, targets):
        return True
    return bool(GROUP_SCOPE_RE.search(text) and all_current_target_ids(targets, "patient"))


def comparator_only_context(text: str, targets: list[Target]) -> bool:
    return bool(COMPARATOR_SCOPE_RE.search(text) and not current_patient_sample_context(text, targets))


def unit_role_hint(candidate_targets: tuple[str, ...], targets: list[Target]) -> str:
    if not candidate_targets:
        return "exclude"
    target_kinds = {
        target.target_kind
        for target in targets
        if target.target_id in set(candidate_targets)
    }
    if target_kinds == {"group"}:
        return "group_specific" if len(candidate_targets) == 1 else "group_summary"
    if len(candidate_targets) > 1:
        return "shared"
    return "patient_specific"


def build_unit_features(
    units: list[SourceUnit],
    targets: list[Target],
) -> dict[str, UnitFeatures]:
    """Compute attribution hints once and share them across model paths."""

    features: dict[str, UnitFeatures] = {}
    current_section = "unknown"
    active_targets: tuple[str, ...] = ()
    patient_ids = all_current_target_ids(targets, "patient")
    for unit in units:
        heading_section = section_from_heading(unit.text) if unit.unit_type == "heading" else None
        if heading_section is not None:
            current_section = heading_section
        section = heading_section or current_section
        mentions = explicit_target_mentions(unit.text, targets)
        reason_codes: set[str] = set()
        risk_flags: set[str] = set()
        if unit.unit_type in {"metadata", "heading"}:
            reason_codes.add("low_value_unit")
        if case_boundary_line(unit.text):
            reason_codes.add("patient_boundary")
        if mentions:
            reason_codes.add("target_alias")
        if GROUP_SCOPE_RE.search(unit.text):
            reason_codes.add("group_scope")
        if SUBSET_SCOPE_RE.search(unit.text):
            reason_codes.add("subset_scope")
            risk_flags.add("group_subset_scope")
        if re.search(r"\bPatient\s+[Il|](?=\W|$)", unit.text, flags=re.IGNORECASE):
            risk_flags.add("ocr_patient_label")
        if len(mentions) >= 2:
            risk_flags.add("mixed_patient_labels")
        if EXTERNAL_REPORT_RE.search(unit.text):
            risk_flags.add("external_patient_mention")
        if COMPARATOR_SCOPE_RE.search(unit.text):
            risk_flags.add("comparator_context")
        if current_patient_sample_context(unit.text, targets):
            reason_codes.add("current_patient_sample_context")
            if COMPARATOR_SCOPE_RE.search(unit.text):
                risk_flags.add("current_sample_with_comparator_context")
        elif comparator_only_context(unit.text, targets):
            risk_flags.add("comparator_only")

        candidate_targets = mentions
        if not candidate_targets and GROUP_SCOPE_RE.search(unit.text) and patient_ids:
            candidate_targets = patient_ids
            reason_codes.add("all_current_patients")
        elif not candidate_targets and active_targets and section not in {"methods", "references"}:
            if re.search(r"\b(?:he|she|his|her|the\s+patient|the\s+case|this\s+patient|this\s+case)\b", unit.text, flags=re.IGNORECASE):
                candidate_targets = active_targets
                reason_codes.add("continuation")
                risk_flags.add("low_confidence_continuation")

        if mentions and len(mentions) == 1 and not EXTERNAL_REPORT_RE.search(unit.text):
            active_targets = mentions
        elif heading_section in {"methods", "results", "discussion", "references"}:
            active_targets = ()

        role_hint = unit_role_hint(candidate_targets, targets)
        confidence_hint = "high" if mentions else "medium" if candidate_targets else "low"
        if "low_confidence_continuation" in risk_flags or "external_patient_mention" in risk_flags:
            confidence_hint = "low"
        features[unit.unit_id] = UnitFeatures(
            unit_id=unit.unit_id,
            section=section,
            explicit_target_mentions=mentions,
            candidate_targets=candidate_targets,
            role_hint=role_hint,
            confidence_hint=confidence_hint,
            reason_codes=tuple(sorted(reason_codes)),
            risk_flags=tuple(sorted(risk_flags)),
        )
    return features


def allowed_roles_for_targets(targets: list[Target]) -> list[str]:
    kinds = {target.target_kind for target in targets}
    if kinds == {"patient"}:
        return ["patient_specific", "shared"] if len(targets) > 1 else ["patient_specific"]
    if kinds == {"group"}:
        return ["group_summary", "group_specific"]
    return ["patient_specific", "shared", "group_summary", "group_specific"]


def model_visible_source_unit(unit: SourceUnit, feature: UnitFeatures) -> bool:
    if unit.unit_type == "metadata":
        return False
    if unit.unit_type == "heading" and "patient_boundary" not in feature.reason_codes:
        return False
    return True


def featured_source_units_payload(
    units: list[SourceUnit],
    features: dict[str, UnitFeatures],
    *,
    selected_unit_ids: set[str] | None = None,
    tags_by_unit_id: dict[str, list[str]] | None = None,
    max_units: int | None = None,
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for unit in units:
        feature = features[unit.unit_id]
        forced = selected_unit_ids is not None and unit.unit_id in selected_unit_ids
        if not forced and not model_visible_source_unit(unit, feature):
            continue
        item: dict[str, Any] = {
            "id": unit.unit_id,
            "type": unit.unit_type,
            "p": unit.page_index,
            "sec": feature.section,
            "hint": list(feature.candidate_targets),
            "role_hint": feature.role_hint,
            "conf_hint": feature.confidence_hint,
            "why": list(feature.reason_codes),
            "risk": list(feature.risk_flags),
            "text": unit.text,
        }
        if selected_unit_ids is not None:
            item["selected"] = unit.unit_id in selected_unit_ids
        if tags_by_unit_id is not None:
            item["tags"] = tags_by_unit_id.get(unit.unit_id, [])
        payload.append(item)
        if max_units is not None and len(payload) >= max_units:
            break
    return payload


def compile_unit_selection_payload(
    *,
    selection_payload: dict[str, Any],
    prepared_source: PreparedSource,
    units: list[SourceUnit] | None = None,
) -> dict[str, Any]:
    source_units = units or build_source_units(prepared_source)
    units_by_id = {unit.unit_id: unit for unit in source_units}
    manual_review_reasons = [
        str(reason)
        for reason in selection_payload.get("manual_review_reasons") or []
        if str(reason).strip()
    ]
    segments: list[dict[str, Any]] = []
    occupied_units: dict[str, str] = {}

    for logical_index, segment in enumerate(selection_payload.get("segments") or [], start=1):
        logical_id = f"l{logical_index:04d}"
        unit_ids = [str(unit_id).strip() for unit_id in segment.get("unit_ids") or [] if str(unit_id).strip()]
        if not unit_ids:
            manual_review_reasons.append(f"missing_unit_ids:{logical_id}")
            continue
        seen: set[str] = set()
        duplicate_ids: set[str] = set()
        for unit_id in unit_ids:
            if unit_id in seen:
                duplicate_ids.add(unit_id)
            else:
                seen.add(unit_id)
        if duplicate_ids:
            manual_review_reasons.append(f"duplicate_unit_ids:{logical_id}:{'|'.join(sorted(duplicate_ids))}")
            continue
        unknown_ids = [unit_id for unit_id in unit_ids if unit_id not in units_by_id]
        if unknown_ids:
            manual_review_reasons.append(f"unknown_unit_ids:{logical_id}:{'|'.join(unknown_ids)}")
            continue
        overlaps = [unit_id for unit_id in unit_ids if unit_id in occupied_units]
        if overlaps:
            manual_review_reasons.append(f"overlapping_unit_ids:{logical_id}:{'|'.join(overlaps)}")
            continue

        spans: list[dict[str, Any]] = []
        for unit_id in unit_ids:
            occupied_units[unit_id] = logical_id
            spans.extend(units_by_id[unit_id].block_spans)
        segments.append(
            {
                "targets": [str(target).strip() for target in segment.get("targets") or [] if str(target).strip()],
                "role": str(segment.get("role") or ""),
                "confidence": str(segment.get("confidence") or "unspecified"),
                "evidence": str(segment.get("evidence") or ""),
                "source_unit_ids": unit_ids,
                "spans": spans,
            }
        )

    return {
        "annotation_mode": str(selection_payload.get("annotation_mode") or "unit_id_selection"),
        "route_mode": str(selection_payload.get("route_mode") or ""),
        "targets": selection_payload.get("targets") or [],
        "segments": segments,
        "validation_warnings": list(selection_payload.get("validation_warnings") or []),
        "manual_review_reasons": sorted(set(manual_review_reasons)),
        "source_unit_count": len(source_units),
    }


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


def first_regex_index(text: str, pattern: re.Pattern[str], start: int = 0) -> int | None:
    match = pattern.search(text, start)
    if match is None:
        return None
    return match.start()


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
    stop_candidates: list[int] = []
    marker_index = first_marker_index(
        text,
        [
            "\nTheCaseinContext",
            "\nThe Case in Context",
            "\nCase 11",
            "\nCase 2",
            "\nI DISCUSSION",
            "\nI Discussion",
            "\n3. Discussion",
            "\n3. DISCUSSION",
            "3. Discussion",
            "3. DISCUSSION",
            "\n4. Discussion",
            "\n4. DISCUSSION",
            "4. Discussion",
            "4. DISCUSSION",
            "\nDiscussion",
            "\nDISCUSSION",
            "\n3. Materials",
            "3. Materials",
            "\n3. Methods",
            "3. Methods",
            "\nMethods",
            "\nMETHODS",
            "\nAUTOANTIBODIES TO",
            "\nT CELL STIMULATION",
            "\nResults\n",
            "\nRESULTS\n",
            "\nResults.",
            "\nRESULTS.",
            "\nSelectedReading",
            "\nSelected Reading",
            "\nI REFERENCES",
            "\nReferences",
            "\nreferences",
            "\nREFERENCES",
            "REFERENCES",
            "\nBibliografia",
            "\nAcknowledgment",
            "\nAcknowledgement",
            "\nWe thank",
            "\nCompeting interests",
            "\nTable 1. Review",
        ],
        start,
    )
    if marker_index is not None:
        stop_candidates.append(marker_index)
    results_section_index = first_regex_index(text, re.compile(r"\nRESULTS\s{2,}", re.IGNORECASE), start)
    if results_section_index is not None:
        stop_candidates.append(results_section_index)
    for pattern in (
        AUTHOR_DEPARTMENT_RE,
        AUTHOR_CREDENTIAL_BLOCK_RE,
        STAR_AUTHOR_DEPARTMENT_RE,
        LETTER_AUTHOR_DEPARTMENT_RE,
    ):
        regex_index = first_regex_index(text, pattern, start)
        if regex_index is not None:
            stop_candidates.append(regex_index)
    return min(stop_candidates) if stop_candidates else None


def summary_clinical_range(text: str) -> tuple[int, int] | None:
    start = first_marker_index(text, ["Summary:", "Abstract", "ABSTRACT"])
    if start is None:
        return None
    end = first_marker_index(
        text,
        [
            "Key Words:",
            "Key words:",
            "Keywords:",
            "KEYWORDS",
            "\nKey Words",
            "Keywords",
            "Key words",
            "\nStiff-person syndrome is",
            "\nIntroduction",
            "\n1. Introduction",
            "1. Introduction",
            "\n2. Case report",
            "2. Case report",
            "\n2. Case history",
            "2. Case history",
            "\nCase report",
            "\nCase Report",
            "\nCASE REPORT",
            "\nHow to cite this article:",
            "\nFull Text",
            "\n| Introduction",
            "\n| Case Report",
            "\nCase description",
            "\nCase Description",
            "\nCASE DESCRIPTION",
            "\nMuscle Nerve",
        ],
        start + 1,
    )
    if end is None:
        end = clinical_stop_index(text, start + 1)
    if end is None:
        return None
    selected = text[start:end]
    if not re.search(spsd_label_pattern(), selected, flags=re.IGNORECASE):
        return None
    if not AGE_ANCHOR_RE.search(selected):
        if not re.search(
            r"\b(?:(?:a|the|this|our)\s+patient|case)\b",
            selected,
            flags=re.IGNORECASE,
        ):
            return None
        if re.search(r"\bbackground\b", selected, flags=re.IGNORECASE):
            return None
        if re.search(r"\b(?:Objectives|Methods|Results|Conclusions?)\s*[—:.-]", selected, flags=re.IGNORECASE):
            return None
    return trim_source_range(text, start, end)


def patient_history_clinical_range(text: str) -> tuple[int, int] | None:
    for marker in ["Patient history.", "Patient history", "Patient History"]:
        index = text.find(marker)
        if index < 0:
            continue
        nearby = text[max(0, index - 1200) : min(len(text), index + 2500)]
        if AGE_ANCHOR_RE.search(nearby) is None:
            continue
        if not re.search(spsd_label_pattern(), nearby, flags=re.IGNORECASE):
            continue
        end = clinical_stop_index(text, index + 1)
        if end is None:
            end = len(text)
        return trim_source_range(text, index, end)
    return None


def case_report_clinical_range(text: str) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    for marker in [
        "REPORT OF A CASE",
        "Report of a Case",
        "CasePresentation",
        "Case Presentation",
        "CASE PRESENTATION",
        "Case presentation",
        "2. Case history",
        "Case history",
        "CASE DESCRIPTION",
        "Case Description",
        "Case description",
        "CASE REPORT",
        "Case Report",
        "Case report",
        "case report",
        "CASE",
        "CASEREPORT",
        "CaseReport",
        "I CASEREPORT",
        "I CASE REPORT",
    ]:
        offset = 0
        while True:
            index = text.find(marker, offset)
            if index < 0:
                break
            offset = index + 1
            if text[index : index + len("CASE REPORTS")].upper() == "CASE REPORTS":
                continue
            line_start = text.rfind("\n", 0, index) + 1
            line_end = text.find("\n", index)
            line_end = len(text) if line_end < 0 else line_end
            marker_line = text[line_start:line_end]
            if re.search(r"\bDESIGN\s*:\s*Case report\b", marker_line, flags=re.IGNORECASE):
                continue
            if re.search(r"\bCASE REPORT\b.{0,80}\bET AL\b", marker_line):
                continue
            if marker.casefold() == "case report":
                following = text[index + len(marker) : index + len(marker) + 1]
                if following.isalpha():
                    continue
                if marker == "case report" and marker_line.strip().casefold() != "case report":
                    continue
            if marker.lower().startswith(("case description", "case history")) and not (
                marker_line.strip().lower().startswith(marker.lower())
            ):
                continue
            if marker == "CASE" and marker_line.strip().upper() != "CASE":
                continue
            age = AGE_ANCHOR_RE.search(text, index, min(len(text), index + 2200))
            if age is not None and re.search(r"\bAbstract\b", text[index : age.start()], flags=re.IGNORECASE):
                continue
            candidate_end = clinical_stop_index(text, index + 1)
            if candidate_end is None:
                candidate_end = min(len(text), index + 3000)
            forward_context = text[index:candidate_end]
            preceding_context = text[max(0, index - 500) : index]
            has_local_spsd_context = re.search(spsd_label_pattern(), forward_context, flags=re.IGNORECASE)
            if not has_local_spsd_context and not re.search(
                r"\nReferences\b|\nREFERENCES\b",
                preceding_context,
                flags=re.IGNORECASE,
            ):
                has_local_spsd_context = re.search(
                    spsd_label_pattern(),
                    preceding_context,
                    flags=re.IGNORECASE,
                )
            if age is not None:
                if has_local_spsd_context:
                    candidates.append((age.start() - index, index))
                continue
            if has_local_spsd_context:
                candidates.append((5000, index))
    if not candidates:
        return None
    _, start = min(candidates)
    end = clinical_stop_index(text, start + 1)
    if end is None:
        return None
    return trim_source_range(text, start, end)


def spsd_title_clinical_range(text: str) -> tuple[int, int] | None:
    title_pattern = re.compile(
        r"^\s*Stiff[- ]?Three[- ]?Limbs? Syndrome\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    candidates: list[tuple[int, int]] = []
    for title_match in title_pattern.finditer(text):
        search_end = min(len(text), title_match.end() + 4000)
        nearby = text[title_match.start() : search_end]
        age = AGE_ANCHOR_RE.search(nearby)
        if age is None:
            continue
        if re.search(r"\bAbstract\b", nearby[: age.start()], flags=re.IGNORECASE):
            continue
        if not re.search(
            r"\b(?:we|this|our)\s+(?:report|present|describe)|\bpatient\b",
            nearby,
            flags=re.IGNORECASE,
        ):
            continue
        end = clinical_stop_index(text, title_match.start() + age.end())
        if end is None:
            end = first_marker_index(text, ["\nReferences", "\nREFERENCES", "REFERENCES"], title_match.end())
        if end is None:
            end = min(len(text), title_match.start() + 6000)
        candidates.append((title_match.start(), end))
    if not candidates:
        return None
    return trim_source_range(text, *candidates[0])


def case_heading_clinical_range(text: str) -> tuple[int, int] | None:
    for case_match in CASE_HEADING_RE.finditer(text):
        age = AGE_ANCHOR_RE.search(text, case_match.end(), min(len(text), case_match.end() + 500))
        if age is None:
            continue
        next_case = first_regex_index(text, CASE_HEADING_RE, age.end())
        section_stop = clinical_stop_index(text, age.end())
        end_candidates = [item for item in [next_case, section_stop] if item is not None]
        end = min(end_candidates) if end_candidates else len(text)
        selected = text[case_match.start() : end]
        if not re.search(spsd_label_pattern(), selected, flags=re.IGNORECASE):
            continue
        return trim_source_range(text, case_match.start(), end)
    return None


def age_anchor_start_index(text: str, anchor_start: int) -> tuple[int, bool]:
    context_start = max(0, anchor_start - 250)
    case_matches = list(CASE_HEADING_RE.finditer(text, context_start, anchor_start))
    if case_matches:
        return case_matches[-1].start(), True
    line_start = text.rfind("\n", 0, anchor_start)
    sentence_start = text.rfind(". ", 0, anchor_start)
    start = max(line_start, sentence_start)
    return (0 if start < 0 else start + (2 if start == sentence_start else 1)), False


def age_anchor_clinical_range(text: str) -> tuple[int, int] | None:
    allow_phenotype_context = (
        len(PATIENT_HISTORY_HEADING_RE.findall(text)) < 2
        and case_report_marker_count(text) < 2
    )
    for match in AGE_ANCHOR_RE.finditer(text):
        age_line_start = text.rfind("\n", 0, match.start()) + 1
        if re.match(r"\s*METHODS\s*:", text[age_line_start : match.start()], flags=re.IGNORECASE):
            continue
        start, started_at_case_heading = age_anchor_start_index(text, match.start())
        end_candidates = [
            first_regex_index(text, CASE_HEADING_RE, match.end()),
            first_regex_index(text, AUTHOR_DEPARTMENT_RE, match.end()),
            first_regex_index(text, AUTHOR_CREDENTIAL_BLOCK_RE, match.end()),
            first_regex_index(text, STAR_AUTHOR_DEPARTMENT_RE, match.end()),
            first_marker_index(
                text,
                [
                    "\nSera from four patients",
                    " Sera from four patients",
                    "\nINCIDENCE OF CEREBRAL INFARCTION",
                    "\nMYASTHENIA GRAVIS AFTER",
                    "\nTREATMENT OF",
                    "\n2. 2.",
                    "\n2.2.",
                    "\n3. Results",
                    "\n3. RESULTS",
                    "\n3. Materials",
                    "3. Materials",
                    "\n3. Methods",
                    "3. Methods",
                    "\n3. Discussion",
                    "\n3. DISCUSSION",
                    "3. Discussion",
                    "3. DISCUSSION",
                    "\n4. Discussion",
                    "\n4. DISCUSSION",
                    "4. Discussion",
                    "4. DISCUSSION",
                    "\nRESULTS\n",
                    "\nResults\n",
                    "\nDISCUSSION",
                    "\nDiscussion",
                    "\nMovement Disorders",
                    "\nReferences",
                    "\nREFERENCES",
                    "\nI REFERENCES",
                    "REFERENCES",
                    "\nDownloaded From:",
                    "\nWe thank",
                    "\nTable 1. Review",
                ],
                match.end(),
            ),
            clinical_stop_index(text, match.end()),
        ]
        end_candidates = [item for item in end_candidates if item is not None and item > start]
        end = min(end_candidates) if end_candidates else len(text)
        selected = text[start:end]
        context = selected if started_at_case_heading else text[max(0, start - 300) : end]
        has_spsd_label = re.search(spsd_label_pattern(), context, flags=re.IGNORECASE)
        has_spsd_phenotype = (
            allow_phenotype_context
            and re.search(spsd_label_pattern(), text, flags=re.IGNORECASE)
            and SPSD_PHENOTYPE_RE.search(selected)
        )
        if not has_spsd_label and not has_spsd_phenotype:
            continue
        return trim_source_range(text, start, end)
    return None


def patient_discussion_clinical_range(text: str, start: int = 0) -> tuple[int, int] | None:
    discussion_start = first_marker_index(text, ["\nDiscussion", "\nDISCUSSION"], start)
    if discussion_start is None:
        return None
    body_end = first_marker_index(
        text,
        [
            "\nAcknowledgment",
            "\nAcknowledgement",
            "\nReferences",
            "\nREFERENCES",
            "REFERENCES",
            "\nBibliografia",
            "\nAddress correspondence",
        ],
        discussion_start + 1,
    )
    clinical_body_end = clinical_stop_index(text, discussion_start + 1)
    if clinical_body_end is not None:
        body_end = min(body_end, clinical_body_end) if body_end is not None else clinical_body_end
    generic_discussion = first_regex_index(text, GENERIC_SPSD_DISCUSSION_RE, discussion_start + 1)
    if generic_discussion is not None:
        body_end = min(body_end, generic_discussion) if body_end is not None else generic_discussion
    if body_end is None:
        body_end = len(text)
    discussion_intro = text[discussion_start : min(body_end, discussion_start + 2500)]
    if re.search(r"\bSeveral cases were reported\b", discussion_intro, flags=re.IGNORECASE):
        return None
    if re.search(r"\bBox\s+\d+\b|\bDIFFERENTIAL DIAGNOSIS\b|\bTREATMENT\b", discussion_intro):
        return None
    start = first_marker_index(
        text,
        [
            "The decreased tone",
            "This patient",
            "The patient",
            "Our patient",
            "This case",
            "The case presented here",
            "In conclusion",
        ],
        discussion_start,
    )
    if start is None or start >= body_end:
        return None
    next_article = first_marker_index(
        text,
        ["\nTO THE EDITOR", "\nA Case of Phenytoin-Induced"],
        discussion_start + 1,
    )
    if next_article is not None and start >= next_article:
        return None
    return trim_source_range(text, start, body_end)


def single_case_results_range(text: str, start: int = 0) -> tuple[int, int] | None:
    if len(PATIENT_HISTORY_HEADING_RE.findall(text)) >= 2:
        return None
    if re.search(r"\bcase\s+\d+\b", text, flags=re.IGNORECASE):
        return None
    result_start = first_marker_index(text, ["\nResults", "\nRESULTS"], start)
    if result_start is None:
        return None
    end = first_marker_index(
        text,
        [
            "\nDiscussion",
            "\nDISCUSSION",
            "\nAcknowledgment",
            "\nAcknowledgement",
            "\nReferences",
            "\nREFERENCES",
            "REFERENCES",
            "\nBibliografia",
        ],
        result_start + 1,
    )
    if end is None:
        return None
    selected = text[result_start:end]
    if re.search(r"\bCST3\b|\bAD onset\b", selected):
        return None
    if not re.search(
        r"\b(?:the patient|our patient|SMS patient|SPS patient|pathological study|GAD|Table)\b",
        selected,
        flags=re.IGNORECASE,
    ):
        return None
    return trim_source_range(text, result_start, end)


def single_case_late_table_range(text: str, start: int = 0) -> tuple[int, int] | None:
    for match in re.finditer(r"(?:^|\n)Table\b", text[start:], flags=re.IGNORECASE):
        table_start = start + match.start()
        preview = text[table_start : min(len(text), table_start + 1600)]
        if re.match(r"\s*Table\s+\d+\.?\s+Review\b", preview, flags=re.IGNORECASE):
            continue
        after_references = re.search(r"\bREFERENCES\b|\nReferences\b", text[start:table_start]) is not None
        if after_references and not re.search(
            r"\b(?:mother|newborn|Present Case|present patient|our patient)\b",
            preview,
            flags=re.IGNORECASE,
        ):
            continue
        if not re.search(
            r"\b(?:anti-GAD|GAD|SPS|stiff|mother|newborn|patient|Present Case)\b",
            preview,
            flags=re.IGNORECASE,
        ):
            continue
        end = first_marker_index(
            text,
            [
                "\nDOI ",
                "\nREFERENCES",
                "REFERENCES",
                "\nReferences",
                "\nThis information is current",
                "\nAuthors",
                "\nServices",
                "\nPermissions",
                "\nReprints",
                "\nOnline ISSN",
            ],
            table_start + 1,
        )
        page_header = first_regex_index(text, re.compile(r"\n\d{3,4}\s+NEUROLOGY\b"), table_start + 1)
        generic_page_header = first_regex_index(
            text,
            re.compile(r"\n\d{3,4}\s+[A-Z][A-Za-z, ]{2,80}\n"),
            table_start + 1,
        )
        end_candidates = [item for item in [end, page_header, generic_page_header] if item is not None]
        end = min(end_candidates) if end_candidates else len(text)
        return trim_source_range(text, table_start, end)
    return None


def source_specific_case_continuation_range(text: str, start: int = 0) -> tuple[int, int] | None:
    if "Paraneoplastic Encephalomyelitis, Stiff Person Syndrome\nand Breast Carcinoma" in text:
        continuation_start = first_marker_index(text, ["but with little effect on limb stiffness"], start)
        if continuation_start is not None:
            continuation_end = first_marker_index(text, ["\nDISCUSSION"], continuation_start + 1)
            if continuation_end is not None:
                return trim_source_range(text, continuation_start, continuation_end)
    return None


def source_specific_case_report_ranges(text: str) -> list[tuple[int, int]]:
    def add_between(
        ranges: list[tuple[int, int]],
        start_markers: list[str],
        end_markers: list[str],
        search_start: int = 0,
    ) -> None:
        start = first_marker_index(text, start_markers, search_start)
        if start is None:
            return
        end = first_marker_index(text, end_markers, start + 1)
        if end is not None and start < end:
            ranges.append(trim_source_range(text, start, end))

    if "Unusual presentation of stiff- person syndrome in a" in text and "Munipalli" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Here, we describe a woman"], ["\nBACKGROUND"])
        add_between(ranges, ["\nCASE PRESENTATION"], ["\nDISCUSSION"])
        add_between(ranges, ["I am feeling a little more secure"], ["\nLearning points"])
        if ranges:
            return ranges

    if (
        "A 52-year-old man was admitted" in text
        and "anti-GlyR antibody-associated PERM" in text
        and "inspiratory laryngeal stridor" in text
    ):
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case presentation: A 52-year-old"], ["\nKeywords:", "Keywords:"])
        add_between(ranges, ["Case description"], ["Discussion and conclusions"])
        add_between(ranges, ["Our patient had cyanosis"], ["In anti-GlyR-related PERM", "Table 1 Clinical features"])
        if ranges:
            return ranges

    if (
        "Stiff Person Syndrome and Encephalitis with" in text
        and "GAD Antibodies with Severe Anterograde" in text
        and "The patient is a 14-year-old girl" in text
    ):
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["A 14-year-old female"], ["\nreceived", "received\nJuly", "\nKeywords", "Keywords", "Case Report"])
        add_between(ranges, ["The patient is a 14-year-old girl"], ["Table 1 Reported cases"])
        add_between(ranges, ["There are considerable memory sequelae"], ["Discussion"])
        add_between(ranges, ["This case associated with the diagnosis"], ["SPS3 is", "In the 12 published cases"])
        if ranges:
            return ranges

    if "Severe dysautonomia in glycine receptor antibody-positive" in text and "We report a 59-year-old man" in text:
        start = first_marker_index(text, ["We report a 59-year-old man"])
        end = first_marker_index(text, ["Abbreviations:"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Progressive encephalomyelitis with rigidity and myoclonus" in text and "A 65- year- old man" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["We describe a 65- year- old man"], ["\nCASE REPORT"])
        add_between(ranges, ["\nCASE REPORT"], ["\nDISCUSSION"])
        if ranges:
            return ranges

    if "Progressive encephalomyelitis with rigidity: A Taiwanese case" in text and "A 46-year-old man" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["3.1. Case presentation"], ["3.2. Literature review"])
        add_between(ranges, ["We report a case with idiopathic"], ["Our most updated literature review"])
        if ranges:
            return ranges

    if "Diplopia management in a patient with stiff person syndrome" in text and "A 43-year-old African American male" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case report\nVisit 1"], ["Discussion"])
        add_between(ranges, ["The patient in this case experienced only strabismus"], ["Disclosure statement"])
        if ranges:
            return ranges

    if "Amphiphysin" in text and "Stiff-Limb" in text and "An 83-year-old white female" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["\nCASE PRESENTATION"], ["\nDISCUSSION"])
        if ranges:
            return ranges

    if "Stiff-person syndrome with sensorimotor polyneuropathy" in text and "CLINICAL CASE REPORT" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["CLINICAL CASE REPORT\nA 68-year-old", "A 68-year-old patient was admitted"], ["WST"])
        add_between(ranges, ["limbs, more pronounced on the left side"], ["nowotworu (Sarva"])
        add_between(ranges, ["There were no pathological symptoms"], ["na izbie"])
        add_between(ranges, ["the anti-GAD65 antibody test results"], ["DISCUSSION, DIAGNOSTIC CRITERIA"])
        add_between(ranges, ["Having been informed about possible treatment options"], ["So far, very few clinical trials"])
        add_between(ranges, ["We achieved significant symptom reduction"], ["Two smaller studies"])
        if ranges:
            return ranges

    if "Glycine Receptor" in text and "SARS-CoV-2" in text and "A 65-year-old man" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case Report\nA 65-year-old", "A 65-year-old man with no previous medical history"], ["1Department of Biomedical"])
        add_between(ranges, ["methylprednisolone) for 5 days"], ["Discussion"])
        add_between(ranges, ["In conclusion, PERM is a rare disease"], ["Acknowledgment"])
        if ranges:
            return ranges

    if "Paraneoplastic Stiff Person Syndrome With Anti-" in text and "Case Presentation\nA 64-year-old" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["We thus describe a case"], ["Categories:"])
        add_between(ranges, ["Case Presentation\nA 64-year-old"], ["Discussion"])
        if ranges:
            return ranges

    if "Aggressive Presentation" in text and "Mimicking Septic Shock" in text and "16-year-old previously healthy Chinese girl" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case Report\nA 16-year-old", "A 16-year-old previously healthy Chinese girl"], ["Discussion"])
        add_between(ranges, ["Compared with other variants of SPS"], ["In 2021, Chang"])
        add_between(ranges, ["In contrast to other pediatric cases, our patient"], ["According to our literature review"])
        if ranges:
            return ranges

    if "Syndrome de la personne raide associ" in text and "dermatite herp" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Patient et observation"], ["Perspective du patient"])
        if ranges:
            return ranges

    if "unilateral brainstem" in text and "anti-GlyR antibody" in text and "Current case 71, M" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case presentation: A /seven.tnum/one.tnum-year-old"], ["KEYWORDS"])
        add_between(ranges, ["Case presentation\nA 71-year-old"], ["Discussion and conclusions"])
        add_between(
            ranges,
            ["This case presented"],
            ["The R1 response is mediated", "Frontiers in Neurology /zero.tnum/three.tnum", "TABLE /one.tnum"],
        )
        add_between(ranges, ["Current case 71, M"], ["Frontiers in Neurology /zero.tnum/four.tnum"])
        add_between(ranges, ["In the present case, both R1 and R2"], ["A summary of published"])
        add_between(ranges, ["we administered immunotherapies"], ["In conclusion, this is a rare case"])
        add_between(ranges, ["In conclusion, this is a rare case"], ["Data availability statement"])
        if ranges:
            return ranges

    if "Stiff person syndrome in a Nepalese man" in text and "ketonuria" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["2 | CASE PRESENTATION"], ["Received:"])
        add_between(ranges, ["neck tightness and jerky limb movements"], ["3 | DISCUSSION"])
        add_between(ranges, ["Our patient was on oral anti-"], ["4 | CONCLUSIONS"])
        if ranges:
            return ranges

    if "Successful management of dyspnea" in text and "noninvasive positive-pressure ventilation" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Abstract"], ["Keywords:"])
        add_between(ranges, ["CASE REPORT"], ["Table 1: The Rating"])
        add_between(ranges, ["DISCUSSION In this case report"], ["Additionally, as reported"])
        add_between(ranges, ["Additionally, as reported"], ["In the current study"])
        add_between(ranges, ["In the current study, we reported"], ["However, because"])
        if ranges:
            return ranges

    if "Stiff-Man Syndrome\nReport of a Case" in text and "A 54-year-old woman" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["REPORT OF A CASE"], ["From the Division"])
        add_between(ranges, ["diazepam for management"], ["Stiff-man syndrome typically"])
        if ranges:
            return ranges

    if "Painful spasms during childhood: Stiff-person syndrome" in text and "10-year-old boy" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Painful spasms during childhood: Stiff-person syndrome"], ["http://dx.doi.org/10.1016/j.nmd.2021.07.376"])
        if ranges:
            return ranges

    if "Long-Term Effect of Gabapentin in Stiff Limb" in text and "The patient is a 39-year-old" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["The patient is a 39-year-old"], ["Received:"])
        add_between(ranges, ["Neurological examination revealed"], ["Dear Sir"])
        add_between(ranges, ["recognized sedation"], ["D i s c u s s i o n"])
        if ranges:
            return ranges

    if "Autoantibodies to GABAergic neurons" in text and "Case report. A 37-year-old woman" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case report. A 37-year-old woman"], ["From the Departments"])
        add_between(ranges, ["spasms of paraspinal"], ["Methods. Electrophysiologic techniques."])
        add_between(ranges, ["Results. Response to plasmapheresis."], ["Immunostaining. All samples"])
        if ranges:
            return ranges

    if "Successful treatment of stiff man syndrome with intravenous immunoglobulin" in text and "A 43 year old man" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["A 43 year old man"], ["The significant response to IVIg"])
        if ranges:
            return ranges

    if "Stiff-person Syndrome Associated with Anti-Yo1 Antibodies" in text and "Other: Toxic metabolic disorders" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Results: A 40-year-old"], ["Other: Toxic metabolic disorders"])
        if ranges:
            return ranges

    if "Persistent Elevation of Glutamic Acid Decarboxylase Antibodies" in text and "A 62-year-old African-American man" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["We report a case of a 62-year-old"], ["Key Words:"])
        add_between(ranges, ["CASE REPORT\nA 62-year-old"], ["From the Division"])
        add_between(ranges, ["titer was mildly elevated"], ["DISCUSSION"])
        if ranges:
            return ranges

    if "Standing Still: A Case of Stiff-person Syndrome" in text and "We present a 54-year-old" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["We present a 54-year-old"], ["This abstract is funded by:"])
        if ranges:
            return ranges

    if "A Case of Stiff Person Syndrome with Response to" in text and "We report a 57 yo woman" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["We report a 57 yo woman"], ["Disclosure:"])
        if ranges:
            return ranges

    if "Presentation of a Case With Repetitive Complex Discharges" in text and "A 41-year-old woman" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT", "CASE REPORT"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "basal ganglia disease ? Striatal" in text and "A 69-year-old woman came in for consultation" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case report\nA 69-year-old"], ["Figure 1 Fundoscopy"])
        add_between(ranges, ["the more symptomatic left side"], ["Discussion\nThe absence"])
        if ranges:
            return ranges

    if "A Case of Stiff Person Syndrome Complicated by Acute Interstitial" in text and "Case: A 49-year-old female" in text:
        ranges: list[tuple[int, int]] = []
        add_between(ranges, ["Case: A 49-year-old"], ["This abstract is funded by:"])
        if ranges:
            return ranges

    if "Stiff-person syndrome with paraneoplastic neurological" in text and "This SPS case report involves a 67-year-old" in text:
        ranges: list[tuple[int, int]] = []
        add_between(
            ranges,
            ["Case presentation: A 67-year"],
            ["In \naddition, we present a literature review", "In addition, we present a literature review", "Conclusions:"],
        )
        add_between(ranges, ["Case report\nThis SPS case report involves"], ["Discussion\nSPS is"])
        if ranges:
            return ranges

    if "Progressive" in text and "Rigidity Responsive to" in text and "Case Report" in text:
        case_start = first_marker_index(text, ["Case Report"])
        case_end = first_marker_index(text, ["\nReferences", "\nREFERENCES"], case_start or 0)
        if case_start is not None:
            if case_end is None:
                case_end = clinical_stop_index(text, case_start + 1)
            if case_end is None:
                case_end = len(text)
            return [trim_source_range(text, case_start, case_end)]

    if "Pediatric stiff limb syndrome with polyautoimmunity" in text and "3. Case presentation" in text:
        ranges: list[tuple[int, int]] = []
        case_start = first_marker_index(text, ["3. Case presentation"])
        discussion_start = first_marker_index(text, ["\n4. Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        table_start = first_marker_index(text, ["Table 1 \nResults of the CSF/serum autoimmune tests"])
        table_end = first_marker_index(text, ["\nD.A. Nie et al.", "\nTable 2"], table_start or 0)
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Keyords: Anti-GAD autoantibody; Stiff-man syndrome; Cerebella syndrome" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["Case report"])
        discussion_start = first_marker_index(
            text,
            ["\nDiscussion", "\n3. Discussion", "3. Discussion", "\n4. Discussion", "4. Discussion"],
            case_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "amphiphysin-associated paraneoplastic stiff-person syndrome" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["Case report. A 71-year-old woman"])
        discussion_start = first_marker_index(
            text,
            ["\nDiscussion", "\nDISCUSSION", "\n4. Discussion", "4. Discussion"],
            case_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Borrelia burgdorferi myelitis presenting as a partial stift man syndrome" in text:
        case_start = first_marker_index(text, ["Case report"])
        references_start = first_marker_index(
            text,
            ["\nAcknowledgements", "\nAcknowledgments", "\nReferences", "\nREFERENCES"],
            case_start or 0,
        )
        if case_start is not None and references_start is not None and case_start < references_start:
            return [trim_source_range(text, case_start, references_start)]

    if "Presentation of a Case With Repetitive Complex Discharges" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT"])
        references_start = first_marker_index(text, ["\nREFERENCES"], case_start or 0)
        if case_start is not None and references_start is not None and case_start < references_start:
            return [trim_source_range(text, case_start, references_start)]

    if "Case 1 (idiopathic PERM)" in text and "GlyR antibodies" in text:
        case_start = first_marker_index(text, ["Case 1 (idiopathic PERM)"])
        table_start = first_marker_index(text, ["Table 1 Summary of clinical features"], case_start or 0)
        continuation_start = first_marker_index(text, ["(Table 1). Thyroid"], table_start or 0)
        case2_start = first_marker_index(text, ["\nCase 2 (idiopathic OFS)"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and table_start is not None and case_start < table_start:
            ranges.append(trim_source_range(text, case_start, table_start))

        def add_table_fragment(start_marker: str, end_marker: str) -> None:
            if table_start is None:
                return
            start = first_marker_index(text, [start_marker], table_start)
            if start is None:
                return
            end = first_marker_index(text, [end_marker], start + len(start_marker))
            if end is None:
                end = start + len(start_marker)
            if start < end:
                ranges.append(trim_source_range(text, start, end))

        add_table_fragment("Table 1 Summary of clinical features, laboratory", "\nPatient no.")
        add_table_fragment("Patient no. Case 1", " Case 2")
        add_table_fragment("Age at onset/sex 61/F", " 41/F")
        add_table_fragment("Diagnosis Idiopathic PERM", " Idiopathic OFS")
        add_table_fragment(
            "Initial symptoms Hypogeusia, gait\ndisturbance, stiffness\nin lower limbs",
            "\nHeadache, vomiting,",
        )
        add_table_fragment("Ocular movements Horizontal gaze palsy,\ngaze-evoked\nnystagmus", "\nOcular")
        add_table_fragment("Myoclonus Moderate\n(lower limbs)", "\nNone Mild")
        add_table_fragment("Hyperreï¬‚exia Mild (lower limbs)", " None Moderate")
        add_table_fragment("Hyperekplexia None", " None None Mild")
        add_table_fragment("Rigidity, spasm,\nstiffness\nSevere (neck, face,\nlower limbs)", "\nNone None")
        add_table_fragment("Other features Dysphagia, stiff face,\nhyperesthesia,\nhypothyroidism", "\nNone None")
        add_table_fragment("MRI Normal", " Normal Normal")
        add_table_fragment("CSF 2 WBC per ll; protein\n52 mg/dl; OCB\npresent", "\n6 WBC")
        add_table_fragment("GlyR-Abs titer\na\n(serum/CSF)\n900/125", " nd/nd")
        add_table_fragment("GAD-Abs titer\n(U/ml)\n(serum/CSF)\n2,34,300/2,340", " nd/na")
        add_table_fragment("Other Abs TPO-Abs, Tg-Abs", " None None")
        add_table_fragment("Treatment IVMP, IVIg, CS, CYS", " IVMP, CS")
        add_table_fragment(
            "Outcome\n(observation\nperiods)\nInitially improved but\ntwice relapsed\n(40 months)",
            "\nImproved without",
        )
        if continuation_start is not None and case2_start is not None and continuation_start < case2_start:
            ranges.append(trim_source_range(text, continuation_start, case2_start))
        if ranges:
            return ranges

    if "A 14-year-old girl with hyperekplexia having GLRB mutations" in text:
        abstract_range = summary_clinical_range(text)
        if abstract_range is None:
            abstract_start = first_marker_index(text, ["Abstract"])
            keywords_start = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
            if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
                abstract_range = trim_source_range(text, abstract_start, keywords_start)
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        references_start = first_marker_index(text, ["\nReferences", "\nREFERENCES"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        case_end = discussion_start if discussion_start is not None else references_start
        if case_start is not None and case_end is not None and case_start < case_end:
            ranges.append(trim_source_range(text, case_start, case_end))
        if ranges:
            return ranges

    if "A case of childhood" in text and "person syndrome with striatal lesions" in text:
        abstract_range = summary_clinical_range(text)
        search_start = abstract_range[1] if abstract_range is not None else 0
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report", "\nCase report"], search_start)
        discussion_start = first_marker_index(text, ["\n3. Dis", "\n3. Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Paraneoplastic stiff person syndrome associated" in text and "worsened after capecitabine" in text:
        case_start = first_marker_index(text, ["Case presentation"])
        conclusion_start = first_marker_index(text, ["\nConclusions"], case_start or 0)
        if case_start is not None and conclusion_start is not None and case_start < conclusion_start:
            return [trim_source_range(text, case_start, conclusion_start)]

    if "RECURRENT THYMOMA WITH PARANEOPLASTIC DISORDERS" in text:
        case_start = first_marker_index(text, ["An 81-year-old woman"])
        comment_start = first_marker_index(text, ["\nComment"], case_start or 0)
        if case_start is not None and comment_start is not None and case_start < comment_start:
            return [trim_source_range(text, case_start, comment_start)]

    if "Stiff Person Syndrome: A Case Report" in text and "A.L." in text:
        initial_start = first_marker_index(text, ["64-year-old woman", "A \n64-year-old woman"])
        background_start = first_marker_index(text, ["\nStiff Person Syndrome \nSPS is"], initial_start or 0)
        treatment_start = first_marker_index(text, ["\nCase Report\nA.L. received"])
        table_start = first_marker_index(text, ["\nTABLE 1. Stiff Person Syndrome Treatment"], treatment_start or 0)
        continuation_start = first_marker_index(text, ["to focus. She had no recall"], table_start or 0)
        lessons_start = first_marker_index(text, ["\nLessons Learned"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if initial_start is not None and background_start is not None and initial_start < background_start:
            ranges.append(trim_source_range(text, initial_start, background_start))
        if treatment_start is not None and table_start is not None and treatment_start < table_start:
            ranges.append(trim_source_range(text, treatment_start, table_start))
        if continuation_start is not None and lessons_start is not None and continuation_start < lessons_start:
            ranges.append(trim_source_range(text, continuation_start, lessons_start))
        if ranges:
            return ranges

    if "Botulinum Toxin A Injection to Facial and Cervical" in text:
        abstract_range = summary_clinical_range(text)
        search_start = abstract_range[1] if abstract_range is not None else 1
        case_start = first_marker_index(
            text,
            ["\nCase Presentation\nA 48-year-old", "\nCase Presentation"],
            search_start,
        )
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Anesthesia in a patient with Stiff Person Syndrome" in text:
        abstract_start = first_marker_index(text, ["Abstract Stiff Person Syndrome"])
        abstract_end_candidates = [
            first_regex_index(
                text,
                re.compile(r"\n[^\n]{0,20}2013 Sociedade Brasileira", re.IGNORECASE),
                abstract_start or 0,
            ),
            first_marker_index(
                text,
                ["\nPALAVRAS-CHAVE", "\nIntroduction"],
                abstract_start or 0,
            ),
        ]
        abstract_end_candidates = [item for item in abstract_end_candidates if item is not None]
        abstract_end = min(abstract_end_candidates) if abstract_end_candidates else None
        abstract_range = (
            trim_source_range(text, abstract_start, abstract_end)
            if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end
            else summary_clinical_range(text)
        )
        case_start = first_marker_index(text, ["\nCase report\nA 46-year-old male patient"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff Person Syndrome Masquerading as Acute" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\nCASE REPORT\nA 41-year-old"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff person syndrome in South Asia" in text:
        case_start = first_marker_index(text, ["\nCase presentation\nA 55-year-old"], 2000)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Central Sleep Apnea and Stiff Person Syndrome" in text:
        case_start = first_marker_index(text, ["\nCase Report\nA 60-year-old"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "A 35-year-old woman with hyperstartling" in text:
        title_start = first_marker_index(text, ["A 35-year-old woman with hyperstartling"])
        questions_start = first_marker_index(text, ["\nQuestions for consideration"], title_start or 0)
        section3_match = re.search(r"\nSECTION 3\s*\n", text[questions_start or 0 :], flags=re.IGNORECASE)
        section3_start = (questions_start or 0) + section3_match.start() if section3_match is not None else None
        section3_stop = first_marker_index(
            text,
            [
                "\nAs Bakker et al.",
                "\nAUTHOR CONTRIBUTIONS",
                "\nSTUDY FUNDING",
                "\nDISCLOSURE",
                "\nReferences",
                "\nREFERENCES",
            ],
            section3_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if title_start is not None and questions_start is not None and title_start < questions_start:
            ranges.append(trim_source_range(text, title_start, questions_start))
        if section3_start is not None:
            section3_end = section3_stop if section3_stop is not None else len(text)
            if section3_start < section3_end:
                ranges.append(trim_source_range(text, section3_start, section3_end))
        if ranges:
            return ranges

    if "CASE REPORT OF A WOMAN WITH ANTI AMPHIPHYSIN" in text:
        case_start = first_marker_index(text, ["\nCase\nA 68 year old woman"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Treatment and Resolution of Filamentary Keratitis" in text:
        results_start = first_marker_index(text, ["Results: A 26-year-old"])
        conclusions_start = first_marker_index(text, ["\nConclusions:"], results_start or 0)
        case_start = first_marker_index(text, ["\nCASE REPORT\nA 26-year-old"])
        received_start = first_marker_index(text, ["\nReceived for publication"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if results_start is not None and conclusions_start is not None and results_start < conclusions_start:
            ranges.append(trim_source_range(text, results_start, conclusions_start))
        if case_start is not None and received_start is not None and case_start < received_start:
            ranges.append(trim_source_range(text, case_start, received_start))
        if ranges:
            return ranges

    if "Focal Myositis Secondary to Sustained Muscle Contraction" in text:
        abstract_range = summary_clinical_range(text)
        search_start = abstract_range[1] if abstract_range is not None else 1
        case_start = first_marker_index(text, ["\nCase Presentation\nA 36-year-old"], search_start)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff-person Syndrome with Waldenstr" in text and "Macroglobulinemia" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\nCase Report\nWe herein report a case"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Progressive Encephalomyelitis with Rigidity and Myoclonus" in text and "An Autopsy Case" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\nCase Report\nA 75-year-old"])
        end = first_marker_index(text, ["\nThe authors state", "\nAcknowledgement"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and end is not None and case_start < end:
            ranges.append(trim_source_range(text, case_start, end))
        if ranges:
            return ranges

    if "Longitudinal gait assessment in a stiff person syndrome" in text:
        case_start = first_marker_index(text, ["\nCase description\nThe patient was a 12-year-old"])
        footer_start = first_marker_index(text, ["\nCase report 377"], case_start or 0)
        continuation_start = first_marker_index(text, ["secondary causes, such as"], footer_start or 0)
        ethics_start = first_marker_index(
            text,
            ["\nAll procedures followed", "All procedures followed", "\nDiscussion"],
            continuation_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if case_start is not None and footer_start is not None and case_start < footer_start:
            ranges.append(trim_source_range(text, case_start, footer_start))
        if continuation_start is not None and ethics_start is not None and continuation_start < ethics_start:
            ranges.append(trim_source_range(text, continuation_start, ethics_start))
        if ranges:
            return ranges

    if "Stiff person syndrome with elevated titers of antibodies" in text and "literature review" in text:
        case_start = first_marker_index(text, ["\nCase report\nA 40-year male"])
        abstract_start = first_marker_index(text, ["\nAbstract\n"], case_start or 0)
        abstract_end = first_marker_index(text, ["\nKeywords:"], abstract_start or 0)
        split_history_start = first_marker_index(text, ["no recent history of trauma"], abstract_end or 0)
        consent_start = first_marker_index(text, ["\nThis study was", "This study was"], split_history_start or 0)
        continuation_start = first_marker_index(text, ["A week before admission"], consent_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and abstract_start is not None and case_start < abstract_start:
            ranges.append(trim_source_range(text, case_start, abstract_start))
        if split_history_start is not None and consent_start is not None and split_history_start < consent_start:
            ranges.append(trim_source_range(text, split_history_start, consent_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if ranges:
            return ranges

    if "A case report of rigidity and recurrent" in text and "Degeneffe" in text:
        abstract_case_start = first_marker_index(text, ["Case presentation: We report"])
        abstract_conclusions_start = first_marker_index(text, ["\nConclusions:"], abstract_case_start or 0)
        case_start = first_marker_index(text, ["\nCase presentation\nThe clinical story"])
        discussion_start = first_marker_index(text, ["\nDiscussion and conclusions"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if (
            abstract_case_start is not None
            and abstract_conclusions_start is not None
            and abstract_case_start < abstract_conclusions_start
        ):
            ranges.append(trim_source_range(text, abstract_case_start, abstract_conclusions_start))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Successful Anesthetic Management" in text and "Patient with Stiff Person Syndrome" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT\nA 53-year male"])
        footer_start = first_marker_index(text, ["\nJournal of the College of Physicians"], case_start or 0)
        continuation_start = first_marker_index(text, ["graphy were done and were normal"], footer_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSS"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and footer_start is not None and case_start < footer_start:
            ranges.append(trim_source_range(text, case_start, footer_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if ranges:
            return ranges

    if "Treatment of Possible PERM Underlying" in text and "Modified Electroconvulsive Therapy" in text:
        case_start = first_marker_index(text, ["We prescet a cate", "We present a case"])
        end = first_marker_index(text, ["\nCulay-Sumic", "\nwerw.ectjiournaloom", "\nCopyright"], case_start or 0)
        footer_start = first_marker_index(text, ["\n(4 Wbers Alwerr", "(4 Wbers Alwerr"], case_start or 0)
        continuation_start = first_marker_index(text, ["A therapeutic regimen"], footer_start or 0)
        ranges: list[tuple[int, int]] = []
        if (
            case_start is not None
            and footer_start is not None
            and case_start < footer_start
            and continuation_start is not None
            and continuation_start < (end or len(text))
        ):
            ranges.append(trim_source_range(text, case_start, footer_start))
            ranges.append(trim_source_range(text, continuation_start, end or len(text)))
        elif case_start is not None and end is not None and case_start < end:
            ranges.append(trim_source_range(text, case_start, end))
        if ranges:
            return ranges

    if "Stiff limb syndrome with lower limb myoclonus" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Atypical low back pain: stiff-person syndrome" in text:
        case_start = first_marker_index(text, ["\nCASE-REPORT", "CASE-REPORT"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Anaesthetic management of a patient with a unique" in text and "anti-N-methyl-D-aspartate" in text:
        summary_start = first_marker_index(text, ["\nSummary", "Summary"])
        background_start = first_marker_index(text, ["\nBaCkground", "\nBackground"], summary_start or 0)
        case_start = first_marker_index(text, ["\nCaSe preSenT aTion", "\nCase presentation"], background_start or 0)
        discussion_start = first_marker_index(text, ["\ndiSCuSSion", "\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if summary_start is not None and background_start is not None and summary_start < background_start:
            ranges.append(trim_source_range(text, summary_start, background_start))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff-man syndrome in\nchildhood" in text:
        continuation_start = first_marker_index(text, ["little affected. He could not get up"])
        comment_start = first_marker_index(text, ["\nCOMMENT"], continuation_start or 0)
        generic_start = first_marker_index(text, ["\nVarious subgroups"], comment_start or 0)
        ranges: list[tuple[int, int]] = []
        if continuation_start is not None and comment_start is not None and continuation_start < comment_start:
            ranges.append(trim_source_range(text, continuation_start, comment_start))
        if comment_start is not None and generic_start is not None and comment_start < generic_start:
            ranges.append(trim_source_range(text, comment_start, generic_start))
        if ranges:
            return ranges

    if "Effects of immunotherapy on motor cortex excitability" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\nCase report", "Case report"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        table_start = first_marker_index(text, ["Table 1 Neurophysiological variables"], discussion_start or 0)
        table_end = first_marker_index(text, ["\nJ Neurol (2010)", "\nacoustic startle"], table_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Reversible stiff person syndrome presenting as an initial symptom" in text:
        case_start = first_marker_index(text, ["An 82-year-old previously healthy woman"])
        generic_start = first_marker_index(
            text,
            ["\n272  Y.-L. Liu et al.", "\nStiff person syndrome is a rare neurologic"],
            case_start or 0,
        )
        if case_start is not None and generic_start is not None and case_start < generic_start:
            return [trim_source_range(text, case_start, generic_start)]

    if "Rituximab treatment of stiff-person syndrome in a patient with thymoma" in text:
        abstract_start = first_marker_index(text, ["abstract\nStiff-person syndrome", "abstract\r\nStiff-person syndrome"])
        abstract_end = first_marker_index(text, ["/C2112009 Elsevier", "\n* Corresponding author"], abstract_start or 0)
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        table_start = first_marker_index(text, ["\nTable 1\nChange in serum"], discussion_start or 0)
        table_end = first_marker_index(
            text,
            ["\nCase Reports / Journal of Clinical Neuroscience", "\nReferences"],
            table_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Stiff Person Syndrome as the Initial\nManifestation of Systemic Lupus" in text:
        case_start = first_marker_index(text, ["A 48-year-old woman with an 8-month history"])
        conflict_start = first_marker_index(
            text,
            ["\nPotential con", "\nPublished online"],
            case_start or 0,
        )
        continuation_start = first_marker_index(
            text,
            ["Screening for breast, lung, and ovarian malignancy"],
            conflict_start or case_start or 0,
        )
        generic_start = first_marker_index(
            text,
            ["\nThe co-occurrence", "\nIndeed, patients"],
            continuation_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if case_start is not None and conflict_start is not None and case_start < conflict_start:
            ranges.append(trim_source_range(text, case_start, conflict_start))
        if continuation_start is not None and generic_start is not None and continuation_start < generic_start:
            ranges.append(trim_source_range(text, continuation_start, generic_start))
        if ranges:
            return ranges

    if "Progressive encephalomyelitis with rigidity and myoclonus preceding otherwise" in text:
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Successful Treatment with Rituximab in a Patient" in text and "Dysthyroid Ophthalmopathy" in text:
        abstract_range = summary_clinical_range(text)
        search_start = abstract_range[1] if abstract_range is not None else 0
        case_start = first_marker_index(text, ["\nCase Report", "Case Report"], search_start)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Successful Immune Moderation Treatment for Progressive" in text:
        abstract_range = summary_clinical_range(text)
        case_start = first_marker_index(text, ["\nCase Report", "Case Report"], abstract_range[1] if abstract_range else 0)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff Young Woman" in text:
        case_start = first_marker_index(text, ["\nCase Description", "Case Description"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        figure3_start = first_marker_index(text, ["\nFig. 3 Ultrasonography"], discussion_start or 0)
        figure3_end = first_marker_index(text, ["\nDankerl P et al."], figure3_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if figure3_start is not None and figure3_end is not None and figure3_start < figure3_end:
            ranges.append(trim_source_range(text, figure3_start, figure3_end))
        if ranges:
            return ranges

    if "Role of Osteopathic Manipulative Treatment" in text and "Report of Case" in text:
        case_start = first_marker_index(text, ["\nReport of Case", "Report of Case"])
        conclusion_start = first_marker_index(text, ["\nConclusion"], case_start or 0)
        natural_follow_up_start = first_marker_index(text, ["\n The natural follow-up", "\nThe natural follow-up"], case_start or 0)
        case_end = natural_follow_up_start if natural_follow_up_start is not None else conclusion_start
        continuation_start = first_marker_index(text, ["crease in OMT frequency"], conclusion_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and case_end is not None and case_start < case_end:
            ranges.append(trim_source_range(text, case_start, case_end))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if ranges:
            return ranges

    if "A Case of Stiff Person Syndrome: Immunomodulatory Effect" in text:
        abstract_start = first_marker_index(text, ["Abstract:", "Abstract"])
        abstract_end = first_marker_index(text, ["\nINTRODUCTION", "\nIntroduction"], abstract_start or 0)
        abstract_range = (
            trim_source_range(text, abstract_start, abstract_end)
            if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end
            else summary_clinical_range(text)
        )
        case_start = first_marker_index(text, ["\nCASE PRESENTATION", "CASE PRESENTATION"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Pseudoobstruction, Autonomic Neuropathy, and Limb" in text and "Stiffness in a Nondiabetic Patient" in text:
        abstract_start = first_marker_index(text, ["Abstract:", "Abstract"])
        abstract_end = first_marker_index(text, ["\nINTRODUCTION", "\nIntroduction"], abstract_start or 0)
        abstract_range = (
            trim_source_range(text, abstract_start, abstract_end)
            if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end
            else summary_clinical_range(text)
        )
        case_start = first_marker_index(text, ["\nCASE REPORT", "CASE REPORT"], abstract_range[1] if abstract_range else 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_range is not None:
            ranges.append(abstract_range)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "A Rare Case of Childhood Stiff Person Syndrome" in text and "Pleuropulmonary Blastoma" in text:
        abstract_start = first_marker_index(text, ["\nabstract", "abstract"])
        abstract_end = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nPatient Description", "Patient Description"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff-arm syndrome" in text and "A 56-year-old woman experienced" in text:
        case_start = first_marker_index(text, ["A 56-year-old woman experienced"])
        author_start = first_marker_index(text, ["\nEnrique Urrea-Mendoza"], case_start or 0)
        figure_start = first_marker_index(text, ["\nFigure Limited range"], author_start or 0)
        figure_end = first_marker_index(text, ["\nVIDEO", "\nNEURO IMAGES"], figure_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and author_start is not None and case_start < author_start:
            ranges.append(trim_source_range(text, case_start, author_start))
        if figure_start is not None and figure_end is not None and figure_start < figure_end:
            ranges.append(trim_source_range(text, figure_start, figure_end))
        if ranges:
            return ranges

    if "Extremely rare coincidence of non-radiographic axial" in text and "Stiff Person Syndrome" in text:
        abstract_case_start = first_marker_index(text, ["Our 51-year-old female patient"])
        abstract_end = first_marker_index(text, ["\nAnti-GAD", "Anti-GAD"], abstract_case_start or 0)
        case_start = first_marker_index(text, ["A 51-year-old woman presented"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        continuation_start = first_marker_index(text, ["hemogram, routine biochemical analysis"], discussion_start or 0)
        conflict_start = first_marker_index(text, ["\nCoincidence of HLA", "\nConflict of interest"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_case_start is not None and abstract_end is not None and abstract_case_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_case_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if continuation_start is not None and conflict_start is not None and continuation_start < conflict_start:
            ranges.append(trim_source_range(text, continuation_start, conflict_start))
        if ranges:
            return ranges

    if "Multiple anesthetics for a patient with" in text and "stiff-person syndrome" in text:
        abstract_start = first_marker_index(text, ["\nAbstract Stiff-person syndrome", "Abstract Stiff-person syndrome"])
        copyright_start = first_regex_index(
            text,
            re.compile(r"\n.{0,8}2016 Elsevier Inc\. All rights reserved\.", re.IGNORECASE),
            abstract_start or 0,
        )
        abstract_end = copyright_start or first_marker_index(text, ["\n1. Introduction", "1. Introduction"], abstract_start or 0)
        case_start = first_marker_index(text, ["\n2. Case description", "2. Case description"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        table_start = first_marker_index(text, ["\nTable Neuromuscular monitoring", "Table Neuromuscular monitoring"], discussion_start or 0)
        table_end = first_marker_index(text, ["\n198 J.M. Cassavaugh", "\nblockade. In 3 studies"], table_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Anesthetic management of a parturient with Stiff" in text and "urgent cesarean delivery" in text:
        abstract_start = first_marker_index(text, ["\nABSTRACT", "ABSTRACT"])
        copyright_start = first_regex_index(
            text,
            re.compile(r"\n.{0,12}2016 Elsevier Ltd\. All rights reserved\.", re.IGNORECASE),
            abstract_start or 0,
        )
        abstract_end = copyright_start or first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
        introduction_start = first_marker_index(text, ["\nIntroduction", "Introduction"], abstract_end or abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase report", "Case report"], introduction_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Anesthetic Considerations of Stiff-Person" in text and "Case Summary" in text:
        case_start = first_marker_index(text, ["\nCase Summary", "Case Summary"])
        discussion_start = first_marker_index(text, ["\nD iscussion", "D iscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "bladder and anti-Ri antibodies" in text and "A 46-year-old man presented" in text:
        abstract_start = first_marker_index(text, ["\nABSTRACT", "ABSTRACT"])
        abstract_end = first_marker_index(text, ["\n1. Introduction", "1. Introduction"], abstract_start or 0)
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Anti-glutamic acid decarboxylase (GAD) positive cerebellar Ataxia" in text and "responsive to immunotherapy" in text:
        abstract_start = first_marker_index(text, ["\nABSTRACT", "ABSTRACT"])
        abstract_end = first_marker_index(text, ["\n1. Introduction", "1. Introduction"], abstract_start or 0)
        case_start = first_marker_index(text, ["\n3.1. Case report", "3.1. Case report"])
        case_discussion_start = first_marker_index(text, ["\n3.2. Case discussion", "3.2. Case discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and case_discussion_start is not None and case_start < case_discussion_start:
            ranges.append(trim_source_range(text, case_start, case_discussion_start))
        if ranges:
            return ranges

    if "Femur Neck Fracture in a Patient with" in text and "Stiff Person Syndrome" in text:
        abstract_start = first_marker_index(text, ["\nAbstract\nCase:", "Abstract\nCase:"])
        abstract_end = first_marker_index(text, ["\n\nS\n", "\nS\n\ntiff person syndrome"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase Report\n57-year-old", "Case Report\n57-year-old"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Chronic intestinal pseudo-obstruction with dilated biliary" in text and "nondiabetic patient" in text:
        abstract_start = first_marker_index(text, ["\nAbstract", "Abstract"])
        abstract_end = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase report\nA 44-year-old", "Case report\nA 44-year-old"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "A Case of Treatment Resistance and Complications" in text and "Cerebellar Ataxia" in text:
        case_start = first_marker_index(text, ["\nCase description\nThe patient first presented", "Case description\nThe patient first presented"])
        front_matter_start = first_marker_index(
            text,
            ["\nColumbia University Libraries\nFreely available online", "\nAbstract"],
            case_start or 0,
        )
        continuation_start = first_marker_index(text, ["There was no previous medical"], front_matter_start or case_start or 0)
        figure_start = first_marker_index(text, ["\nFigure 1. Schematic Timeline", "Figure 1. Schematic Timeline"], continuation_start or 0)
        final_case_start = first_marker_index(text, ["unsteadiness on the right"], figure_start or continuation_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion\nThis case illustrates", "\nDiscussion"], final_case_start or continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None:
            continuation_end = figure_start if figure_start is not None else discussion_start
            if continuation_end is not None and continuation_start < continuation_end:
                ranges.append(trim_source_range(text, continuation_start, continuation_end))
        if final_case_start is not None and discussion_start is not None and final_case_start < discussion_start:
            ranges.append(trim_source_range(text, final_case_start, discussion_start))
        if ranges:
            return ranges

    if "Stiff Person Syndrome and Type 1 Diabetes Mellitus" in text and "A 23-year-old Hispanic woman" in text:
        case_start = first_marker_index(text, ["\nCASE PRESENTATION", "CASE PRESENTATION"])
        received_start = first_marker_index(text, ["\nReceived May", "Received May"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Here, we report an insulin-na"], received_start or case_start or 0)
        figure_start = first_marker_index(text, ["\nT1DM SPS", "T1DM SPS", "\nFigure 2"], patient_discussion_start or 0)
        later_patient_start = first_marker_index(
            text,
            ["Our patient was diagnosed with SPS at 19 years old"],
            figure_start or patient_discussion_start or 0,
        )
        conclusion_start = first_marker_index(text, ["\nCONCLUSION", "CONCLUSION"], later_patient_start or patient_discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and received_start is not None and case_start < received_start:
            ranges.append(trim_source_range(text, case_start, received_start))
        if patient_discussion_start is not None and figure_start is not None and patient_discussion_start < figure_start:
            ranges.append(trim_source_range(text, patient_discussion_start, figure_start))
        if later_patient_start is not None and conclusion_start is not None and later_patient_start < conclusion_start:
            ranges.append(trim_source_range(text, later_patient_start, conclusion_start))
        if ranges:
            return ranges

    if "Intrathecal Baclofen Pump Placement in a Patient" in text and "Poster 90" in text:
        case_start = first_marker_index(text, ["\nCase Description:", "Case Description:"])
        next_poster_start = first_marker_index(text, ["\nPoster 91", "Poster 91"], case_start or 0)
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "Therapeutic Plasma Exchange in a Patient with" in text and "Paraneoplastic Variant of Stiff-Person Syndrome" in text:
        background_start = first_marker_index(text, ["Background/Case Studies:"])
        case_start = first_marker_index(text, ["We present a 75-y-old"], background_start or 0)
        methods_start = first_marker_index(text, ["\nStudy Design/Methods:", "Study Design/Methods:"], case_start or 0)
        disclosure_start = first_marker_index(text, ["\nDisclosure of Commercial Conflict of Interest"], background_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and methods_start is not None and case_start < methods_start:
            ranges.append(trim_source_range(text, case_start, methods_start))
        if methods_start is not None and disclosure_start is not None and methods_start < disclosure_start:
            ranges.append(trim_source_range(text, methods_start, disclosure_start))
        if ranges:
            return ranges

    if "EFFICACY OF LEVETIRACETAM IN A CASE OF STIFF-PERSON SYNDROME" in text:
        case_start = first_marker_index(text, ["She was a 50-year-old woman", "S he was a 50-year-old woman"], 0)
        case_end = first_marker_index(text, ["\nFigure 1", "\n3 DISCUSSION"], case_start or 0)
        if case_start is not None and case_end is not None and case_start < case_end:
            return [trim_source_range(text, case_start, case_end)]

    if "GlyR antibody" in text and "resection of a perianal" in text:
        case_start = first_marker_index(text, ["\nCASE DESCRIPTION", "CASE DESCRIPTION"])
        abstract_start = first_marker_index(
            text,
            ["\nProgressive encephalomyelitis with rigidity and myoclonus (PERM)"],
            case_start or 0,
        )
        if case_start is not None and abstract_start is not None and case_start < abstract_start:
            return [trim_source_range(text, case_start, abstract_start)]

    if "STIFF-PERSON SYNDROME ASSOCIATED WITH MYOTONIC DYSTROPHY TYPE 2" in text:
        abstract_case_start = first_marker_index(text, ["We describe a case study of a 46-year"])
        abstract_end = first_marker_index(text, ["\nSouhrn", "Souhrn"], abstract_case_start or 0)
        case_start = first_marker_index(text, ["\nCase report\nA 45-year", "Case report\nA 45-year"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_case_start is not None and abstract_end is not None and abstract_case_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_case_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Scoliosis in Childhood" in text and "posterior spinal fusion" in text:
        case_start = first_marker_index(text, ["A 20 years old African American woman"])
        support_start = first_marker_index(
            text,
            ["\nStudy Supported by:", "Study Supported by:", "Study \nSupported by:"],
            case_start or 0,
        )
        if case_start is not None and support_start is not None and case_start < support_start:
            return [trim_source_range(text, case_start, support_start)]

    if "Rhabdomyolysis in Stiff Person Syndrome: Case Report" in text:
        case_start = first_marker_index(text, ["DESIGN/METHODS:A 50-year-old", "DESIGN/METHODS: A 50-year-old"])
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], case_start or 0)
        if case_start is not None and disclosure_start is not None and case_start < disclosure_start:
            return [trim_source_range(text, case_start, disclosure_start)]

    if "Case report: The case of a female patient of 20 years" in text and "botulinum toxin type a" in text.lower():
        case_start = first_marker_index(text, ["Case report: The case of a female patient of 20 years"])
        unrelated_table_start = first_marker_index(text, ["\nGroupsa Male", "Groupsa Male"], case_start or 0)
        continuation_start = first_marker_index(text, ["kg every 2 months"], unrelated_table_start or case_start or 0)
        next_abstract_start = first_marker_index(text, ["\ndoi:10.1016/j.jns.2015.08.265", "doi:10.1016/j.jns.2015.08.265"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and unrelated_table_start is not None and case_start < unrelated_table_start:
            ranges.append(trim_source_range(text, case_start, unrelated_table_start))
        if continuation_start is not None and next_abstract_start is not None and continuation_start < next_abstract_start:
            ranges.append(trim_source_range(text, continuation_start, next_abstract_start))
        if ranges:
            return ranges

    if "Stiff person syndrome in a 64 year old male Filipino" in text:
        case_start = first_marker_index(text, ["A 64-year-old Filipino man"])
        next_abstract_start = first_marker_index(text, ["\ndoi:10.1016/j.jns.2015.08.91", "doi:10.1016/j.jns.2015.08.91"], case_start or 0)
        if case_start is not None and next_abstract_start is not None and case_start < next_abstract_start:
            return [trim_source_range(text, case_start, next_abstract_start)]

    if "Status spasticus and psoas muscle edema" in text and "anti-GAD antibody associated stiff-man syndrome" in text:
        case_start = first_marker_index(text, ["\nCase Report\nA 64-year-old man", "Case Report\nA 64-year-old man"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Case 3 is a 26 year-old female" in text and "stiff-person" in text:
        case_start = first_marker_index(text, ["Case 3 is a 26 year-old female"])
        conclusions_start = first_marker_index(text, ["\nCONCLUSIONS:", "CONCLUSIONS:"], case_start or 0)
        if case_start is not None and conclusions_start is not None and case_start < conclusions_start:
            return [trim_source_range(text, case_start, conclusions_start)]

    if "Bilateral Hip Fracture During Hospitalization" in text and "Spasm Exacerbation" in text:
        case_start = first_marker_index(text, ["Case/Program Description: The patient is a 47-year-old woman"])
        next_poster_start = first_marker_index(text, ["\nPoster 238", "Poster 238"], case_start or 0)
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "Acute Rehabilitation of a Patient with Stiff Person" in text and "GAD-Antibody Cerebellar Ataxia" in text:
        case_start = first_marker_index(text, ["Case/Program Description: The patient presented after months"])
        next_poster_start = first_marker_index(text, ["\nPoster 361", "Poster 361"], case_start or 0)
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "Case/Program Description: Patient is a 53-year-old man" in text and "botulinum toxin" in text.lower():
        case_start = first_marker_index(text, ["Case/Program Description: Patient is a 53-year-old man"])
        next_poster_start = first_marker_index(text, ["\nPoster 259", "Poster 259"], case_start or 0)
        if "A Novel Approach to the Treatment of" in text and "Stiff-Person-Syndrome with Botulinum Toxin" in text:
            discussion_start = first_marker_index(text, ["\nDiscussion:", "Discussion:"], case_start or 0)
            conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], discussion_start or case_start or 0)
            level_start = first_marker_index(text, ["\nLevel of Evidence", "Level of Evidence"], conclusions_start or case_start or 0)
            ranges: list[tuple[int, int]] = []
            if case_start is not None:
                case_end = discussion_start if discussion_start is not None else next_poster_start
                if case_end is not None and case_start < case_end:
                    ranges.append(trim_source_range(text, case_start, case_end))
            if conclusions_start is not None:
                conclusion_end = level_start if level_start is not None else next_poster_start
                if conclusion_end is not None and conclusions_start < conclusion_end:
                    ranges.append(trim_source_range(text, conclusions_start, conclusion_end))
            if ranges:
                return ranges
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "How a Flexible Differential Yielded an Elusive" in text and "A 48-year-old woman" in text:
        case_start = first_marker_index(text, ["Case/Program Description: A 48-year-old woman"])
        next_poster_start = first_marker_index(text, ["\nPoster 317", "Poster 317"], case_start or 0)
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "Case Report\nA 50-year-old man with recurrent episodes" in text and "CPK" in text:
        case_start = first_marker_index(text, ["\nCase Report\nA 50-year-old man", "Case Report\nA 50-year-old man"])
        discussion_start = first_marker_index(text, ["\nDiscussion and Conclusions", "Discussion and Conclusions"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Seronegative progressive encephalomyelitis" in text and "Design/Methods: A 75-year-old man" in text:
        case_start = first_marker_index(text, ["Design/Methods: A 75-year-old man"])
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], case_start or 0)
        if case_start is not None and disclosure_start is not None and case_start < disclosure_start:
            return [trim_source_range(text, case_start, disclosure_start)]

    if "Pediatric stiff" in text and "person syndrome with renal failure" in text:
        case_start = first_marker_index(text, ["\nCase Report\nAn 8", "Case Report\nAn 8"])
        address_start = first_marker_index(text, ["\nAddress for correspondence:", "Address for correspondence:"], case_start or 0)
        continuation_start = first_marker_index(text, ["His blood counts"], address_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], continuation_start or 0)
        table_start = first_marker_index(text, ["Table 1: Investigations results SPS"], discussion_start or continuation_start or 0)
        table_end = first_marker_index(text, ["\nKumar and Savida:", "Kumar and Savida:"], table_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and address_start is not None and case_start < address_start:
            ranges.append(trim_source_range(text, case_start, address_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Stiff-person Syndrome with Cerebellar Manifestations" in text and "2. Case report" in text:
        case_start = first_marker_index(text, ["\n2. Case report", "2. Case report"])
        author_note_start = first_marker_index(text, ["\nq All authors", "q All authors"], case_start or 0)
        if case_start is not None and author_note_start is not None and case_start < author_note_start:
            return [trim_source_range(text, case_start, author_note_start)]

    if "STIFF PERSON SYNDROME WITH NEGATIVE" in text and "ANTI-GAD65 ANTIBODIES" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT\nWe present a case", "CASE REPORT\nWe present a case"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Inpatient Physiotherapy Management for Stiff-Person Syndrome" in text:
        case_start = first_marker_index(text, ["\n2. Case Presentation", "2. Case Presentation"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "(Pseudo)hemidystonia associated" in text and "A 55-year-old woman" in text:
        case_start = first_marker_index(text, ["A 55-year-old woman"])
        disclosure_start = first_marker_index(text, ["\nDisclosure of", "Disclosure of"], case_start or 0)
        if case_start is not None and disclosure_start is not None and case_start < disclosure_start:
            return [trim_source_range(text, case_start, disclosure_start)]

    if "Acute lower limb spasticity: Stiff person syndrome" in text and "P.026" in text:
        case_start = first_marker_index(text, ["Herein we report a 15 year old female"])
        section_end = first_marker_index(text, ["\nPediatric  n eurosurGery", "Pediatric  n eurosurGery"], case_start or 0)
        next_abstract_start = first_marker_index(text, ["\nP.027", "P.027"], case_start or 0)
        if section_end is None or (next_abstract_start is not None and next_abstract_start < section_end):
            section_end = next_abstract_start
        if case_start is not None and section_end is not None and case_start < section_end:
            return [trim_source_range(text, case_start, section_end)]

    if "Spontaneous Bilateral Hip Fractures" in text and "Case/Program Description: A 46-year-old woman" in text:
        case_start = first_marker_index(text, ["Case/Program Description: A 46-year-old woman"])
        next_start = first_marker_index(text, ["\nLevel of Evidence:", "Level of Evidence:"], case_start or 0)
        if case_start is not None and next_start is not None and case_start < next_start:
            return [trim_source_range(text, case_start, next_start)]

    if "Stiff Person Syndrome Without Axial Stiffness" in text and "Case/Program Description: Ms. S" in text:
        case_start = first_marker_index(text, ["Case/Program Description: Ms. S"])
        next_start = first_marker_index(text, ["\nLevel of Evidence:", "Level of Evidence:"], case_start or 0)
        if case_start is not None and next_start is not None and case_start < next_start:
            return [trim_source_range(text, case_start, next_start)]

    if "Hodgkin" in text and "GlyR" in text and "A 60-year-old previously healthy man" in text:
        case_start = first_marker_index(text, ["A 60-year-old previously healthy man"])
        consent_start = first_marker_index(text, ["\nWritten informed consent", "Written informed consent"], case_start or 0)
        if case_start is not None and consent_start is not None and case_start < consent_start:
            return [trim_source_range(text, case_start, consent_start)]

    if "O-35 The Stiff Person Syndrome" in text and "Material and methods:" in text:
        case_start = first_marker_index(text, ["We present a male patient 28 y/o", "We present a 28-year-old male patient"])
        next_abstract_start = first_marker_index(text, ["\nO-36", "O-36"], case_start or 0)
        if case_start is not None and next_abstract_start is not None and case_start < next_abstract_start:
            return [trim_source_range(text, case_start, next_abstract_start)]

    if "Longitudinally Extensive Dorsal Column Lesion" in text and "In 2003, a 57-year-old man" in text:
        case_start = first_marker_index(text, ["In 2003, a 57-year-old man"])
        disclosure_start = first_marker_index(text, ["\nAuthors/Disclosures", "Authors/Disclosures"], case_start or 0)
        if case_start is not None and disclosure_start is not None and case_start < disclosure_start:
            return [trim_source_range(text, case_start, disclosure_start)]

    if "Double Hit and Excellent Treatment Response" in text and "A 29-year-old woman" in text:
        case_start = first_marker_index(text, ["Background: A 29-year-old woman", "A 29-year-old woman"])
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], case_start or 0)
        if case_start is not None and disclosure_start is not None and case_start < disclosure_start:
            return [trim_source_range(text, case_start, disclosure_start)]

    if "Bortezomib for the Treatment of Refractory Stiff Person Spectrum" in text:
        results_start = first_marker_index(text, ["Results: We report a 58-year-old woman"])
        conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], results_start or 0)
        if results_start is not None and conclusions_start is not None and results_start < conclusions_start:
            return [trim_source_range(text, results_start, conclusions_start)]

    if "A Rare Case of Non-Neoplastic Anti-GAD" in text and "Responsive to IVIG" in text:
        objective_start = first_marker_index(text, ["Objective: We present a case of a 65-year-old male"])
        background_start = first_marker_index(text, ["\nBackground:", "Background:"], objective_start or 0)
        results_start = first_marker_index(text, ["Results: A 65-year-old African American male"])
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], results_start or 0)
        ranges: list[tuple[int, int]] = []
        if objective_start is not None and background_start is not None and objective_start < background_start:
            ranges.append(trim_source_range(text, objective_start, background_start))
        if results_start is not None and disclosure_start is not None and results_start < disclosure_start:
            ranges.append(trim_source_range(text, results_start, disclosure_start))
        if ranges:
            return ranges

    if "Stiff Person Syndrome as a Mimic of Parkinsonism" in text and "44-year-old right handed woman" in text:
        case_start = first_marker_index(text, ["A previously healthy 44-year-old right handed woman"])
        methods_start = first_marker_index(text, ["\nDesign/Methods:", "Design/Methods:"], case_start or 0)
        conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], methods_start or case_start or 0)
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], conclusions_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and methods_start is not None and case_start < methods_start:
            ranges.append(trim_source_range(text, case_start, methods_start))
        if conclusions_start is not None and disclosure_start is not None and conclusions_start < disclosure_start:
            ranges.append(trim_source_range(text, conclusions_start, disclosure_start))
        if ranges:
            return ranges

    if "A Stiff Person Case Admitted Phsysical Medicine" in text and "Case Report\nA 26-year-old female" in text:
        abstract_case_start = first_marker_index(text, ["We report a case of SPS with Hashimoto"])
        abstract_end = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_case_start or 0)
        case_start = first_marker_index(text, ["\nCase Report\nA 26-year-old female", "Case Report\nA 26-year-old female"])
        consent_start = first_marker_index(text, ["\nFor case presentation", "For case presentation"], case_start or 0)
        patient_discussion_start = first_marker_index(
            text,
            [
                "The patient’s pain and stiffness decreased",
                "The patientâ€™s pain and stiffness decreased",
                "The patient's pain and stiffness decreased",
            ],
            consent_start or case_start or 0,
        )
        informed_start = first_marker_index(text, ["\nInformed Consent:", "Informed Consent:"], patient_discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_case_start is not None and abstract_end is not None and abstract_case_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_case_start, abstract_end))
        if case_start is not None and consent_start is not None and case_start < consent_start:
            ranges.append(trim_source_range(text, case_start, consent_start))
        if patient_discussion_start is not None and informed_start is not None and patient_discussion_start < informed_start:
            ranges.append(trim_source_range(text, patient_discussion_start, informed_start))
        if ranges:
            return ranges

    if "Anti-GAD antibody\nsyndrome with" in text and "42-year-old man initially presented" in text:
        case_start = first_marker_index(text, ["42-year-old man initially presented"])
        sidebar_start = first_marker_index(text, ["\nPractical\nImplications", "Practical\nImplications"], case_start or 0)
        continuation_start = first_marker_index(text, ["panel including voltage-gated potassium channel"], sidebar_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and sidebar_start is not None and case_start < sidebar_start:
            ranges.append(trim_source_range(text, case_start, sidebar_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if ranges:
            return ranges

    if "Anti-GAD65 Positive Stiff-Person Syndrome: Novel" in text and "Common Variable Immune" in text:
        case_start = first_marker_index(text, ["Here we report a case of a middle aged female"])
        conclusions_start = first_marker_index(text, ["\nCONCLUSIONS:", "CONCLUSIONS:"], case_start or 0)
        if case_start is not None and conclusions_start is not None and case_start < conclusions_start:
            return [trim_source_range(text, case_start, conclusions_start)]

    if "Progressive encephalomyelitis with rigidity and myoclonus with" in text and "R. Mahdi Aljedani" in text:
        case_start = first_marker_index(text, ["We report a case of severe PERM"])
        next_abstract_start = first_marker_index(text, ["\nP73", "P73"], case_start or 0)
        if case_start is not None and next_abstract_start is not None and case_start < next_abstract_start:
            return [trim_source_range(text, case_start, next_abstract_start)]

    if "Stiff Person Syndrome: An Elusive Diagnosis in a Pediatric Patient" in text:
        case_start = first_marker_index(text, ["A case is presented of a seventeen-year-old male"])
        methods_start = first_marker_index(text, ["\nDesign/Methods:", "Design/Methods:"], case_start or 0)
        if case_start is not None and methods_start is not None and case_start < methods_start:
            return [trim_source_range(text, case_start, methods_start)]

    if "A follow -up of a 59-year -old female patient with stiff person syndrome" in text:
        abstract_start = first_marker_index(text, ["A follow -up of a 59-year -old female patient"])
        keywords_start = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
        observation_start = first_marker_index(text, ["\nClinical observation", "Clinical observation"])
        table_start = first_marker_index(text, ["\nTable. Criteria", "Table. Criteria"], observation_start or 0)
        post_figure_start = first_marker_index(text, ["Thus, in the patient  with SPS"], table_start or observation_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], post_figure_start or observation_start or 0)
        diagnosis_start = first_marker_index(text, ["A diagnosis of S PS in the patient"], discussion_start or 0)
        muscle_generic_start = first_marker_index(text, ["The absence of necrosis"], diagnosis_start or 0)
        treatment_start = first_marker_index(text, ["In the course of treatment with GABAergic drugs"], muscle_generic_start or diagnosis_start or 0)
        pathogenesis_start = first_marker_index(text, ["Pathogenesis of phobia"], treatment_start or 0)
        mental_start = first_marker_index(text, ["When assessing mental status of the patient"], pathogenesis_start or treatment_start or 0)
        standard_start = first_marker_index(text, ["According to the current standards"], mental_start or 0)
        antidepressant_start = first_marker_index(text, ["It should be noted  that treatment with the use of"], standard_start or mental_start or 0)
        cbt_generic_start = first_marker_index(text, ["Cognitive -behavioral"], antidepressant_start or 0)
        final_start = first_marker_index(text, ["Thus, subsequent management  of the patie"], cbt_generic_start or antidepressant_start or 0)
        references_start = first_marker_index(text, ["\nREFERENCES", "REFERENCES"], final_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
            ranges.append(trim_source_range(text, abstract_start, keywords_start))
        if observation_start is not None and table_start is not None and observation_start < table_start:
            ranges.append(trim_source_range(text, observation_start, table_start))
        if post_figure_start is not None and discussion_start is not None and post_figure_start < discussion_start:
            ranges.append(trim_source_range(text, post_figure_start, discussion_start))
        if diagnosis_start is not None and muscle_generic_start is not None and diagnosis_start < muscle_generic_start:
            ranges.append(trim_source_range(text, diagnosis_start, muscle_generic_start))
        if treatment_start is not None and pathogenesis_start is not None and treatment_start < pathogenesis_start:
            ranges.append(trim_source_range(text, treatment_start, pathogenesis_start))
        if mental_start is not None and standard_start is not None and mental_start < standard_start:
            ranges.append(trim_source_range(text, mental_start, standard_start))
        if antidepressant_start is not None and cbt_generic_start is not None and antidepressant_start < cbt_generic_start:
            ranges.append(trim_source_range(text, antidepressant_start, cbt_generic_start))
        if final_start is not None and references_start is not None and final_start < references_start:
            ranges.append(trim_source_range(text, final_start, references_start))
        if ranges:
            return ranges

    if (
        (
            "Stiff person syndrome: An unusual paraneoplastic" in text
            or "stiff person syndrome An unusual paraneoplastic manifestation" in text
        )
        and "carcinoid tumour" in text
    ):
        abstract_start = first_marker_index(text, ["We report a 58 \nyear old Sri Lankan male"])
        keywords_start = first_marker_index(text, ["\nKeywords:", "Keywords:"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCASE REPORT\nA previously healthy 58 year old", "CASE REPORT\nA previously healthy 58 year old"])
        introduction_start = first_marker_index(text, ["\nINTRODUCTION", "INTRODUCTION"], case_start or 0)
        continuation_start = first_marker_index(text, ["were normal. Even though"], introduction_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], continuation_start or case_start or 0)
        patient_discussion_start = first_marker_index(
            text,
            ["In our patient with possible \nparaneoplastic SPS secondary"],
            discussion_start or 0,
        )
        reported_start = first_marker_index(text, ["SPS has never been previously reported"], patient_discussion_start or 0)
        patient_treatment_start = first_marker_index(text, ["In our patient, the primary site of the carcinoid"], reported_start or 0)
        disclosure_start = first_marker_index(text, ["\nDISCLOSURE", "DISCLOSURE"], patient_treatment_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
            ranges.append(trim_source_range(text, abstract_start, keywords_start))
        if case_start is not None and introduction_start is not None and case_start < introduction_start:
            ranges.append(trim_source_range(text, case_start, introduction_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if patient_discussion_start is not None and reported_start is not None and patient_discussion_start < reported_start:
            ranges.append(trim_source_range(text, patient_discussion_start, reported_start))
        if patient_treatment_start is not None and disclosure_start is not None and patient_treatment_start < disclosure_start:
            ranges.append(trim_source_range(text, patient_treatment_start, disclosure_start))
        if ranges:
            return ranges

    if "Stiff Person Syndrome Associated \nwith Compartment Syndrome" in text:
        abstract_start = first_marker_index(text, ["We describe \na patient", "We describe a patient"])
        introduction_start = first_marker_index(text, ["\nIntroduction", "Introduction"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase Report  \nA 66-year-old", "Case Report  \nA 66-year-old", "A 66-year-old Chinese"])
        first_download_start = first_marker_index(text, ["\nDownloaded from", "Downloaded from"], case_start or 0)
        treatment_start = first_marker_index(text, ["The patient was treated for SPS initially"], first_download_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], treatment_start or case_start or 0)
        conclusion_start = first_marker_index(text, ["\nConclusion", "Conclusion"], discussion_start or 0)
        ethics_start = first_marker_index(text, ["\nStatement of Ethics", "Statement of Ethics"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and introduction_start is not None and abstract_start < introduction_start:
            ranges.append(trim_source_range(text, abstract_start, introduction_start))
        if case_start is not None and first_download_start is not None and case_start < first_download_start:
            ranges.append(trim_source_range(text, case_start, first_download_start))
        if treatment_start is not None and discussion_start is not None and treatment_start < discussion_start:
            ranges.append(trim_source_range(text, treatment_start, discussion_start))
        if conclusion_start is not None and ethics_start is not None and conclusion_start < ethics_start:
            ranges.append(trim_source_range(text, conclusion_start, ethics_start))
        if ranges:
            return ranges

    if "We present a case of Stiff Person Syndrome in a 38-year old" in text:
        case_start = first_marker_index(text, ["We present a case of Stiff Person Syndrome in a 38-year old"])
        doi_start = first_marker_index(text, ["doi:10.1016/j.jns.2019.10.1 140"], case_start or 0)
        if case_start is not None and doi_start is not None and case_start < doi_start:
            return [trim_source_range(text, case_start, doi_start)]

    if "We report a 58 year old Sri\nLankan male with SPS" in text and "doi:10.1016/j.jns.2019.10.1336" in text:
        case_start = first_marker_index(text, ["We report a 58 year old Sri\nLankan male with SPS"])
        doi_start = first_marker_index(text, ["doi:10.1016/j.jns.2019.10.1336"], case_start or 0)
        if case_start is not None and doi_start is not None and case_start < doi_start:
            return [trim_source_range(text, case_start, doi_start)]

    if "Case Report: Stiff Person Syndrome with Thymoma" in text and "A 68-year-old man was referred" in text:
        abstract_start = first_marker_index(text, ["Case. We herein report a 68-year-old"])
        keywords_start = first_marker_index(text, ["\nKEY WORDS", "KEY WORDS"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCASE\nA 68-year-old", "CASE\nA 68-year-old"])
        department_start = first_marker_index(text, ["\nDepartment of Surgery", "Department of Surgery"], case_start or 0)
        table_start = first_marker_index(text, ["Table 1. Laboratory Findings on Admission"], department_start or case_start or 0)
        figure1_start = first_marker_index(text, ["Figure 1. Chest computed tomography"], table_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], figure1_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["This patient had neurological symptoms"], discussion_start or 0)
        generic_discussion_start = first_marker_index(text, ["SPS is a rare neurological syndrome"], patient_discussion_start or 0)
        conclusion_start = first_marker_index(text, ["\nCONCLUSION", "CONCLUSION"], generic_discussion_start or discussion_start or 0)
        conclusion_end = first_marker_index(text, ["\nAS iti", "AS iti", "\nREFERENCES", "REFERENCES"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
            ranges.append(trim_source_range(text, abstract_start, keywords_start))
        if case_start is not None and department_start is not None and case_start < department_start:
            ranges.append(trim_source_range(text, case_start, department_start))
        if table_start is not None and figure1_start is not None and table_start < figure1_start:
            ranges.append(trim_source_range(text, table_start, figure1_start))
        if figure1_start is not None and discussion_start is not None and figure1_start < discussion_start:
            ranges.append(trim_source_range(text, figure1_start, discussion_start))
        if patient_discussion_start is not None and generic_discussion_start is not None and patient_discussion_start < generic_discussion_start:
            ranges.append(trim_source_range(text, patient_discussion_start, generic_discussion_start))
        if conclusion_start is not None and conclusion_end is not None and conclusion_start < conclusion_end:
            ranges.append(trim_source_range(text, conclusion_start, conclusion_end))
        if ranges:
            return ranges

    if "Low-Dose Naltrexone" in text and "LF is a 59-year old woman" in text:
        abstract_start = first_marker_index(text, ["We present the case of a 59-year-old woman"])
        abstract_end = first_marker_index(text, ["We conclude"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase presentation\nLF is a 59-year old woman", "Case presentation\nLF is a 59-year old woman"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Trismus as a Presenting Symptom in a Case of Progressive" in text and "A 73-year-old woman" in text:
        abstract_start = first_marker_index(text, ["In this report we present a clinical case of trismus"])
        abstract_end = first_marker_index(text, ["\nDownloaded from", "Downloaded from"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase Presentation  \nA 73-year-old woman", "Case Presentation  \nA 73-year-old woman"])
        first_download_start = first_marker_index(text, ["\nDownloaded from", "Downloaded from"], case_start or 0)
        continuation_start = first_marker_index(text, ["breathing assistance. During"], first_download_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and first_download_start is not None and case_start < first_download_start:
            ranges.append(trim_source_range(text, case_start, first_download_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if ranges:
            return ranges

    if "Rituximab improves not only back" in text and "2. 1. Case presentation" in text:
        abstract_start = first_marker_index(text, ["Objective:"])
        introduction_start = first_marker_index(text, ["\n1. Introduction", "1. Introduction"], abstract_start or 0)
        figure1_start = first_marker_index(text, ["Fig. 1. The time course"], introduction_start or 0)
        generic_scale_start = first_marker_index(text, ["patients when a stiffness scale was used"], figure1_start or 0)
        case_start = first_marker_index(text, ["The patient was a 42-year-old"])
        figure2_start = first_marker_index(text, ["\n\nFig. 2.", "Fig. 2."], case_start or 0)
        results_start = first_marker_index(text, ["\n3. Results", "3. Results"])
        post_results_discussion_start = first_marker_index(text, ["neurotransmission. For example"], results_start or 0)
        figure4_start = first_marker_index(text, ["Fig. 4. The saccade velocity"], post_results_discussion_start or results_start or 0)
        conclusion_heading_start = first_marker_index(text, ["\n5. Conclusion", "5. Conclusion"], figure4_start or 0)
        conclusion_text_start = first_marker_index(text, ["Slow saccades were observed"], conclusion_heading_start or figure4_start or 0)
        references_start = first_marker_index(text, ["\n[1] L. M. Levy", "[1] L. M. Levy"], conclusion_text_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and introduction_start is not None and abstract_start < introduction_start:
            ranges.append(trim_source_range(text, abstract_start, introduction_start))
        if figure1_start is not None and generic_scale_start is not None and figure1_start < generic_scale_start:
            ranges.append(trim_source_range(text, figure1_start, generic_scale_start))
        if case_start is not None and figure2_start is not None and case_start < figure2_start:
            ranges.append(trim_source_range(text, case_start, figure2_start))
        if results_start is not None and post_results_discussion_start is not None and results_start < post_results_discussion_start:
            ranges.append(trim_source_range(text, results_start, post_results_discussion_start))
        if figure4_start is not None and conclusion_heading_start is not None and figure4_start < conclusion_heading_start:
            ranges.append(trim_source_range(text, figure4_start, conclusion_heading_start))
        if conclusion_text_start is not None and references_start is not None and conclusion_text_start < references_start:
            ranges.append(trim_source_range(text, conclusion_text_start, references_start))
        if ranges:
            return ranges

    if "anti-GAD antibody-associated sti" in text and "2.CaseReport" in text and "Table 1 shows evidence" in text:
        case_start = first_marker_index(text, ["2.CaseReport"])
        discussion_start = first_marker_index(text, ["3.Discussion"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["We report a young woman"], discussion_start or 0)
        generic_discussion_start = first_marker_index(text, ["Anti-GAD antibody syndromes encompass"], patient_discussion_start or 0)
        conclusion_start = first_marker_index(text, ["In this case report, we highlight"], generic_discussion_start or discussion_start or 0)
        conflict_start = first_marker_index(text, ["ConflictsofInterest"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if patient_discussion_start is not None and generic_discussion_start is not None and patient_discussion_start < generic_discussion_start:
            ranges.append(trim_source_range(text, patient_discussion_start, generic_discussion_start))
        if conclusion_start is not None and conflict_start is not None and conclusion_start < conflict_start:
            ranges.append(trim_source_range(text, conclusion_start, conflict_start))
        if ranges:
            return ranges

    if "Autoimmune musicogenic epilepsy associated with anti-glutamic" in text and "2 | CASE REPORT" in text:
        case_start = first_marker_index(text, ["2 | CASE REPORT"])
        front_matter_start = first_marker_index(text, ["\nReceived:", "Received:"], case_start or 0)
        continuation_start = first_marker_index(text, ["of 1280 nmol/L"], front_matter_start or case_start or 0)
        discussion_start = first_marker_index(text, ["3 | DISCUSSION"], continuation_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["We describe an association"], discussion_start or 0)
        generic_discussion_start = first_marker_index(text, ["Musicogenic epilepsy is a rare"], patient_discussion_start or 0)
        final_message_start = first_marker_index(text, ["Epileptic seizures should be suspected"], generic_discussion_start or discussion_start or 0)
        acknowledgments_start = first_marker_index(text, ["\nACKNOWLEDGMENTS", "ACKNOWLEDGMENTS"], final_message_start or 0)
        table_start = first_marker_index(text, ["TABLE 1 Overview of case reports"], acknowledgments_start or 0)
        next_case_start = first_marker_index(text, ["Falip et"], table_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if patient_discussion_start is not None and generic_discussion_start is not None and patient_discussion_start < generic_discussion_start:
            ranges.append(trim_source_range(text, patient_discussion_start, generic_discussion_start))
        if final_message_start is not None and acknowledgments_start is not None and final_message_start < acknowledgments_start:
            ranges.append(trim_source_range(text, final_message_start, acknowledgments_start))
        if table_start is not None and next_case_start is not None and table_start < next_case_start:
            ranges.append(trim_source_range(text, table_start, next_case_start))
        if ranges:
            return ranges

    if "stiff limb syndrome associated to anti-NMDAR antibodies" in text and "P11 PRECLINICAL" in text:
        case_start = first_marker_index(text, ["We report the case of a"])
        next_section_start = first_marker_index(text, ["\nP11 PRECLINICAL", "P11 PRECLINICAL"], case_start or 0)
        if case_start is not None and next_section_start is not None and case_start < next_section_start:
            return [trim_source_range(text, case_start, next_section_start)]

    if "Stiff-Person Syndrome and Limbic" in text and "A 29-year-old Chinese woman" in text:
        case_start = first_marker_index(text, ["A 29-year-old Chinese woman"])
        references_start = first_marker_index(text, ["\nReferences:", "References:"], case_start or 0)
        if case_start is not None and references_start is not None and case_start < references_start:
            return [trim_source_range(text, case_start, references_start)]

    if "Stiff Limb Syndrome Progressing to Stiff Man" in text and "A 52-year-old male" in text:
        case_start = first_marker_index(text, ["A 52-year-old male"])
        references_start = first_marker_index(text, ["\nReferences:", "References:"], case_start or 0)
        if case_start is not None and references_start is not None and case_start < references_start:
            return [trim_source_range(text, case_start, references_start)]

    if "Intranasal midazolam for treating acute" in text and "55-year-old woman affected by SPS" in text:
        case_start = first_marker_index(text, ["Here, we report the clinical history of a 55-year-old woman"])
        author_note_start = first_marker_index(text, ["\nFrom the Department", "From the Department"], case_start or 0)
        table_start = first_marker_index(text, ["Table Past or concurrent autoimmune comorbidities"], author_note_start or case_start or 0)
        treatment_continuation_start = first_marker_index(text, ["with azathioprine"], table_start or case_start or 0)
        evidence_start = first_marker_index(text, ["\nClassification of evidence", "Classification of evidence"], treatment_continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and author_note_start is not None and case_start < author_note_start:
            ranges.append(trim_source_range(text, case_start, author_note_start))
        if table_start is not None and treatment_continuation_start is not None and table_start < treatment_continuation_start:
            ranges.append(trim_source_range(text, table_start, treatment_continuation_start))
        if (
            treatment_continuation_start is not None
            and evidence_start is not None
            and treatment_continuation_start < evidence_start
        ):
            ranges.append(trim_source_range(text, treatment_continuation_start, evidence_start))
        if ranges:
            return ranges

    if "Effectiveness of Combined\nImmunoglobulin and Glucocorticoid" in text and "A 55-year-old female" in text:
        case_start = first_marker_index(text, ["\nCASE PRESENTATION\nA 55-year-old", "CASE PRESENTATION\nA 55-year-old"])
        table_start = first_marker_index(text, ["TABLE 1 | Paraneoplastic neurological antibody results."], case_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], table_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Although our patient"], discussion_start or 0)
        generic_discussion_start = first_marker_index(text, ["The age, history"], patient_discussion_start or 0)
        treatment_discussion_start = first_marker_index(text, ["Our patientâ€™s muscle spasms"], generic_discussion_start or discussion_start or 0)
        table2_start = first_marker_index(text, ["TABLE 2 | Reported cases"], treatment_discussion_start or 0)
        conclusion_start = first_marker_index(text, ["\nCONCLUSION", "CONCLUSION"], table2_start or discussion_start or 0)
        data_statement_start = first_marker_index(text, ["\nDATA AVAILABILITY", "DATA AVAILABILITY"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and table_start is not None and case_start < table_start:
            ranges.append(trim_source_range(text, case_start, table_start))
        if table_start is not None and discussion_start is not None and table_start < discussion_start:
            ranges.append(trim_source_range(text, table_start, discussion_start))
        if patient_discussion_start is not None and generic_discussion_start is not None and patient_discussion_start < generic_discussion_start:
            ranges.append(trim_source_range(text, patient_discussion_start, generic_discussion_start))
        if treatment_discussion_start is not None and table2_start is not None and treatment_discussion_start < table2_start:
            ranges.append(trim_source_range(text, treatment_discussion_start, table2_start))
        if conclusion_start is not None and data_statement_start is not None and conclusion_start < data_statement_start:
            ranges.append(trim_source_range(text, conclusion_start, data_statement_start))
        if ranges:
            return ranges

    if "Rehabilitation Challenges in a Rare Combination of Stiff-" in text and "33-year-old woman" in text:
        title_start = first_marker_index(text, ["Rehabilitation Challenges in a Rare Combination of Stiff-"])
        case_start = first_marker_index(text, ["Case/Program Description: A"], title_start or 0)
        next_poster_start = first_marker_index(text, ["\nPoster 264:", "Poster 264:"], case_start or 0)
        if case_start is not None and next_poster_start is not None and case_start < next_poster_start:
            return [trim_source_range(text, case_start, next_poster_start)]

    if "Surgical Treatment for Toe Deformities in" in text and "76-year-old woman visited" in text:
        abstract_start = first_marker_index(text, ["Case: Stiff-person syndrome"])
        abstract_end = first_marker_index(text, ["\nConclusion: For patients", "Conclusion: For patients"], abstract_start or 0)
        fig1_start = first_marker_index(text, ["Fig. 1-A"], abstract_end or 0)
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], fig1_start or 0)
        fig2_start = first_marker_index(text, ["Fig. 2-A"], disclosure_start or fig1_start or 0)
        fig2_end = first_marker_index(text, ["antiglutamic acid decarboxylase"], fig2_start or 0)
        case_start = first_marker_index(text, ["\nCase Report\n76-year-old woman visited", "Case Report\n76-year-old woman visited"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["The clinical manifestations in the present case"], discussion_start or 0)
        author_start = first_marker_index(text, ["\nRyutaro Takeda", "Ryutaro Takeda"], patient_discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if fig1_start is not None and disclosure_start is not None and fig1_start < disclosure_start:
            ranges.append(trim_source_range(text, fig1_start, disclosure_start))
        if fig2_start is not None and fig2_end is not None and fig2_start < fig2_end:
            ranges.append(trim_source_range(text, fig2_start, fig2_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if patient_discussion_start is not None and author_start is not None and patient_discussion_start < author_start:
            ranges.append(trim_source_range(text, patient_discussion_start, author_start))
        if ranges:
            return ranges

    if "Exogenous Insulin Injection-Induced" in text and "A 43-year-old man with body" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT\nA 43-year-old", "CASE REPORT\nA 43-year-old"])
        table1_start = first_marker_index(text, ["TABLE 1 | Results of laboratory tests."], case_start or 0)
        table2_start = first_marker_index(text, ["TABLE 2 | Main clinical features"], table1_start or case_start or 0)
        treatment_continuation_start = first_marker_index(text, ["Intravenous immunoglobulin (IVIG"], table2_start or table1_start or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], treatment_continuation_start or case_start or 0)
        conclusion_start = first_marker_index(text, ["\nCONCLUSION", "CONCLUSION"], discussion_start or 0)
        ethics_start = first_marker_index(text, ["\nETHICS STATEMENT", "ETHICS STATEMENT"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and table1_start is not None and case_start < table1_start:
            ranges.append(trim_source_range(text, case_start, table1_start))
        if table1_start is not None and table2_start is not None and table1_start < table2_start:
            ranges.append(trim_source_range(text, table1_start, table2_start))
        if treatment_continuation_start is not None and discussion_start is not None and treatment_continuation_start < discussion_start:
            ranges.append(trim_source_range(text, treatment_continuation_start, discussion_start))
        if conclusion_start is not None and ethics_start is not None and conclusion_start < ethics_start:
            ranges.append(trim_source_range(text, conclusion_start, ethics_start))
        if ranges:
            return ranges

    if "Stiff Person Syndrome and \nAcetylcholine Receptor Ganglionic" in text and "A 64 -year-old woman" in text:
        abstract_start = first_marker_index(text, ["We describe the case of a 64 -year-old"])
        introduction_start = first_marker_index(text, ["\nIntroduction", "Introduction"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase Report  \nA 64 -year-old", "Case Report  \nA 64 -year-old"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Until now, we have ruled"], discussion_start or 0)
        download_start = first_marker_index(text, ["\nDownloaded from", "Downloaded from"], patient_discussion_start or 0)
        antibody_start = first_marker_index(
            text,
            ["Our patient’s AChRGN Ab was positive", "AChRGN Ab was positive"],
            download_start or patient_discussion_start or 0,
        )
        final_discussion_end = first_marker_index(text, ["More studies should be done"], antibody_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and introduction_start is not None and abstract_start < introduction_start:
            ranges.append(trim_source_range(text, abstract_start, introduction_start))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if patient_discussion_start is not None and download_start is not None and patient_discussion_start < download_start:
            ranges.append(trim_source_range(text, patient_discussion_start, download_start))
        if antibody_start is not None and final_discussion_end is not None and antibody_start < final_discussion_end:
            ranges.append(trim_source_range(text, antibody_start, final_discussion_end))
        if ranges:
            return ranges

    if "Amphiphysin expression in a case of occult cancer" in text and "A 35-year-old woman" in text:
        case_start = first_marker_index(text, ["A 35-year-old woman"])
        prior_report_start = first_marker_index(text, ["Pittock et al."], case_start or 0)
        patient_discussion_start = first_marker_index(
            text,
            ["As far as we know, this is the first case"],
            prior_report_start or case_start or 0,
        )
        disclosure_start = first_marker_index(text, ["\nDISCLOSURE", "DISCLOSURE"], patient_discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and prior_report_start is not None and case_start < prior_report_start:
            ranges.append(trim_source_range(text, case_start, prior_report_start))
        if patient_discussion_start is not None and disclosure_start is not None and patient_discussion_start < disclosure_start:
            ranges.append(trim_source_range(text, patient_discussion_start, disclosure_start))
        if ranges:
            return ranges

    if "Multiple antibody positive autoimmune encephalomyelitis" in text and "70-year-old female" in text:
        results_start = first_marker_index(text, ["Results: A previously healthy 70-year-old female"])
        conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], results_start or 0)
        case_highlight_start = first_marker_index(text, ["This case highlights"], conclusions_start or 0)
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], results_start or 0)
        ranges: list[tuple[int, int]] = []
        if results_start is not None and conclusions_start is not None and results_start < conclusions_start:
            ranges.append(trim_source_range(text, results_start, conclusions_start))
        if case_highlight_start is not None and disclosure_start is not None and case_highlight_start < disclosure_start:
            ranges.append(trim_source_range(text, case_highlight_start, disclosure_start))
        if not ranges and results_start is not None and disclosure_start is not None and results_start < disclosure_start:
            ranges.append(trim_source_range(text, results_start, disclosure_start))
        if ranges:
            return ranges

    if "Spastic Dysarthria as a presenting sign" in text and "56 year old right handed female" in text:
        results_start = first_marker_index(text, ["Results: 56 year old right handed female"])
        conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], results_start or 0)
        cohort_start = first_marker_index(text, ["In one retrospective study"], conclusions_start or 0)
        malignancy_start = first_marker_index(text, ["Our \nmalignancy work up", "Our malignancy work up"], cohort_start or conclusions_start or 0)
        support_start = first_marker_index(text, ["\nStudy Supported by", "Study Supported by"], results_start or 0)
        ranges: list[tuple[int, int]] = []
        if results_start is not None and cohort_start is not None and results_start < cohort_start:
            ranges.append(trim_source_range(text, results_start, cohort_start))
        if (
            cohort_start is not None
            and malignancy_start is not None
            and support_start is not None
            and malignancy_start < support_start
        ):
            ranges.append(trim_source_range(text, malignancy_start, support_start))
        if not ranges and results_start is not None and support_start is not None and results_start < support_start:
            ranges.append(trim_source_range(text, results_start, support_start))
        if ranges:
            return ranges

    if "Improvement of Stiff Person Syndrome Symptoms During" in text and "A 23-year-old G1P0 woman" in text:
        results_start = first_marker_index(text, ["Results: A 23-year-old G1P0 woman"])
        conclusions_start = first_marker_index(text, ["\nConclusions:", "Conclusions:"], results_start or 0)
        generic_reports_start = first_marker_index(text, ["Four reports"], conclusions_start or 0)
        support_start = first_marker_index(text, ["\nStudy Supported by", "Study Supported by"], results_start or 0)
        ranges: list[tuple[int, int]] = []
        if results_start is not None and conclusions_start is not None and results_start < conclusions_start:
            ranges.append(trim_source_range(text, results_start, conclusions_start))
        if conclusions_start is not None:
            conclusion_end = generic_reports_start if generic_reports_start is not None else support_start
            if conclusion_end is not None and conclusions_start < conclusion_end:
                ranges.append(trim_source_range(text, conclusions_start, conclusion_end))
        if not ranges and results_start is not None and support_start is not None and results_start < support_start:
            ranges.append(trim_source_range(text, results_start, support_start))
        if ranges:
            return ranges

    if "F59. Spasmodic reflex myoclonus" in text and "anti-glutamic acid decarboxylase 65 antibodies was 164 IU" in text:
        results_start = first_marker_index(text, ["Results: The results demonstrated"])
        doi_start = first_marker_index(text, ["\ndoi: 10. 1016/j.clinph. 2018. 04. 222", "doi: 10. 1016/j.clinph. 2018. 04. 222"], results_start or 0)
        if results_start is not None and doi_start is not None and results_start < doi_start:
            return [trim_source_range(text, results_start, doi_start)]

    if "STIFF PERSON SYNDROME WITH REFLEX MYOCLONUS" in text and "39 years old worker" in text:
        methods_start = first_marker_index(text, ["Methods 39 years old worker"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion Progressively severe"], methods_start or 0)
        if methods_start is not None and discussion_start is not None and methods_start < discussion_start:
            return [trim_source_range(text, methods_start, discussion_start)]

    if "Stiff Young Woman" in text and "A 27-year-old young woman" in text:
        results_start = first_marker_index(text, ["Results: A 27-year-old young woman"])
        if results_start is not None:
            return [trim_source_range(text, results_start, len(text))]

    if "Stiff Limb Syndrome: A Rare Variant" in text and "A 79-year-old woman" in text:
        background_start = first_marker_index(text, ["Background: A 79-year-old woman"])
        disclosure_start = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], background_start or 0)
        if background_start is not None and disclosure_start is not None and background_start < disclosure_start:
            return [trim_source_range(text, background_start, disclosure_start)]

    if "clinical pilates-based physiotherapy training program" in text and "AE is a 43-year-old" in text:
        abstract_start = first_marker_index(text, ["The aim of the present report"])
        keywords_start = first_marker_index(text, ["\nKeywords", "Keywords"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCase presentation\nAE is a 43-year-old", "Case presentation\nAE is a 43-year-old"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        table1_start = first_marker_index(text, ["Table 1  Comparison of pre-test"], discussion_start or case_start or 0)
        table1_end = first_marker_index(text, ["\n83Acta Neurologica Belgica", "83Acta Neurologica Belgica"], table1_start or 0)
        table2_start = first_marker_index(text, ["Table 2  Comparison of pre-test"], table1_end or table1_start or 0)
        table3_start = first_marker_index(text, ["Table 3  Comparison of pre-test"], table2_start or table1_start or 0)
        table3_end = first_marker_index(text, ["\n84 Acta Neurologica Belgica", "84 Acta Neurologica Belgica"], table3_start or 0)
        conclusion_start = first_marker_index(text, ["\nConclusion", "Conclusion"], table3_end or discussion_start or 0)
        generic_conclusion_start = first_marker_index(text, ["Although we have promis", "Although we have promising"], conclusion_start or 0)
        compliance_start = first_marker_index(text, ["\nCompliance with ethical standards", "Compliance with ethical standards"], conclusion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
            ranges.append(trim_source_range(text, abstract_start, keywords_start))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if table1_start is not None and table1_end is not None and table1_start < table1_end:
            ranges.append(trim_source_range(text, table1_start, table1_end))
        if table2_start is not None and table3_start is not None and table2_start < table3_start:
            ranges.append(trim_source_range(text, table2_start, table3_start))
        if table3_start is not None and table3_end is not None and table3_start < table3_end:
            ranges.append(trim_source_range(text, table3_start, table3_end))
        if conclusion_start is not None:
            conclusion_end = generic_conclusion_start if generic_conclusion_start is not None else compliance_start
            if conclusion_end is not None and conclusion_start < conclusion_end:
                ranges.append(trim_source_range(text, conclusion_start, conclusion_end))
        if ranges:
            return ranges

    if "Paraneoplastic Stiff Person Syndrome in Breast Cancer" in text and "A 68 -year-old" in text:
        abstract_start = first_marker_index(text, ["We present the case of a patient with paraneoplastic SPS"])
        abstract_end = first_marker_index(
            text,
            [
                "Paraneoplastic SPS \nis a rare neurological disorder",
                "Paraneoplastic SPS is a rare neurological disorder",
                "\u00c2\u00a9 2020",
                "\u00a9 2020",
                "\nDownloaded from",
                "Downloaded from",
            ],
            abstract_start or 0,
        )
        case_start = first_marker_index(text, ["\nCase Presentation  \nA 68 -year-old", "Case Presentation  \nA 68 -year-old"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Here, we present the case of a female patient"], discussion_start or 0)
        acknowledgements_start = first_marker_index(text, ["\nAcknowledgements", "Acknowledgements"], patient_discussion_start or 0)
        table1_start = first_marker_index(text, ["Table 1. Drug dosage administered"], acknowledgements_start or discussion_start or 0)
        table_end = first_marker_index(text, ["\nDownloaded from", "Downloaded from"], table1_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if patient_discussion_start is not None and acknowledgements_start is not None and patient_discussion_start < acknowledgements_start:
            ranges.append(trim_source_range(text, patient_discussion_start, acknowledgements_start))
        if table1_start is not None and table_end is not None and table1_start < table_end:
            ranges.append(trim_source_range(text, table1_start, table_end))
        if ranges:
            return ranges

    if "Stiff-Person Syndrome Outpatient Rehabilitation" in text and "46-year-old female patient" in text:
        case_start = first_marker_index(text, ["\nCase Presentation\nHistory", "Case Presentation\nHistory"])
        irb_start = first_marker_index(text, ["\nInstitutional Review Board", "Institutional Review Board"], case_start or 0)
        if case_start is not None and irb_start is not None and case_start < irb_start:
            return [trim_source_range(text, case_start, irb_start)]

    if (
        ("associated with thymoma" in text or "With Thymoma" in text)
        and "A 60-year-old female" in text
        and "CASE PRESENTATION" in text
    ):
        case_start = first_marker_index(text, ["\nCASE PRESENTATION\nA 60-year-old", "CASE PRESENTATION\nA 60-year-old"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], case_start or 0)
        table_start = first_marker_index(text, ["\nTABLE 1", "TABLE 1"], case_start or 0)
        ends = [item for item in [discussion_start, table_start] if item is not None]
        if case_start is not None and ends:
            end = min(ends)
            if case_start < end:
                return [trim_source_range(text, case_start, end)]

    if "Levodopa-responsive progressive encephalomyelitis" in text and "This 41-year-old man" in text:
        case_start = first_marker_index(text, ["This 41-year-old man"])
        review_start = first_marker_index(text, ["This case prompted"], case_start or 0)
        novelty_start = first_marker_index(text, ["To the best of our knowledge"], review_start or case_start or 0)
        contents_start = first_marker_index(text, ["\nContents lists", "Contents lists"], novelty_start or 0)
        datscan_start = first_marker_index(text, ["negative DATscan favors"], contents_start or novelty_start or 0)
        consent_start = first_marker_index(text, ["\nInformed written consent", "Informed written consent"], datscan_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and review_start is not None and case_start < review_start:
            ranges.append(trim_source_range(text, case_start, review_start))
        if novelty_start is not None and contents_start is not None and novelty_start < contents_start:
            ranges.append(trim_source_range(text, novelty_start, contents_start))
        if datscan_start is not None and consent_start is not None and datscan_start < consent_start:
            ranges.append(trim_source_range(text, datscan_start, consent_start))
        if ranges:
            return ranges

    if "McArdle Disease" in text and "Stiff-Person Syndrome" in text and "A 41-year-old man" in text:
        case_start = first_marker_index(text, ["\nCASE DESCRIPTION\nA 41-year-old", "CASE DESCRIPTION\nA 41-year-old"])
        case_series_start = first_marker_index(text, ["In a case series consisting of 57"], case_start or 0)
        resume_start = first_marker_index(text, ["Regardless of whether"], case_series_start or case_start or 0)
        ethics_start = first_marker_index(text, ["\nETHICS STATEMENT", "ETHICS STATEMENT"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None:
            first_end = case_series_start if case_series_start is not None else ethics_start
            if first_end is not None and case_start < first_end:
                ranges.append(trim_source_range(text, case_start, first_end))
        if resume_start is not None and ethics_start is not None and resume_start < ethics_start:
            ranges.append(trim_source_range(text, resume_start, ethics_start))
        if ranges:
            return ranges

    if "Advanced Progression of Scoliosis After Intrathecal" in text and "This is a 59-year-old woman" in text:
        case_start = first_marker_index(text, ["\nThis is a 59-year-old woman", "This is a 59-year-old woman"])
        front_matter_start = first_marker_index(
            text,
            ["Stiff person syndrome is a neuroimmunological disorder"],
            case_start or 0,
        )
        continuation_start = first_marker_index(text, ["immunoglobulin (before SPS diagnosis)"], front_matter_start or case_start or 0)
        case_series_start = first_marker_index(text, ["Importantly, 2 case series"], continuation_start or case_start or 0)
        weakness_start = first_marker_index(text, ["An inherent weakness of our case study"], case_series_start or continuation_start or 0)
        generic_tail_start = first_marker_index(text, ["Further stud"], weakness_start or continuation_start or 0)
        disclosures_start = first_marker_index(text, ["\n E\n DISCLOSURES", "\nDISCLOSURES", "DISCLOSURES"], continuation_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None:
            first_end = case_series_start if case_series_start is not None else generic_tail_start or disclosures_start
            if first_end is not None and continuation_start < first_end:
                ranges.append(trim_source_range(text, continuation_start, first_end))
        if weakness_start is not None:
            weakness_end = generic_tail_start if generic_tail_start is not None else disclosures_start
            if weakness_end is not None and weakness_start < weakness_end:
                ranges.append(trim_source_range(text, weakness_start, weakness_end))
        if ranges:
            return ranges

    if "lower back pain: a case of stiff" in text and "Case description: A 61" in text:
        case_start = first_marker_index(text, ["Case description: A 61"])
        physiology_start = first_marker_index(text, ["Physiopathology and diagnosis"], case_start or 0)
        conclusion_start = first_marker_index(text, ["Conclusion: SPS"], physiology_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and physiology_start is not None and case_start < physiology_start:
            ranges.append(trim_source_range(text, case_start, physiology_start))
        if conclusion_start is not None:
            ranges.append(trim_source_range(text, conclusion_start, len(text)))
        if ranges:
            return ranges

    if "Variant form of stiff-man syndrome with neck pain" in text and "A 64-year-old man" in text:
        early_continuation_start = first_marker_index(text, ["continuous discharges at rest"])
        early_continuation_end = first_marker_index(text, ["\nKey words", "Key words"], early_continuation_start or 0)
        case_start = first_marker_index(text, ["\nCase report\nA 64-year-old", "Case report\nA 64-year-old"])
        correspondence_start = first_marker_index(text, ["Address correspondence"], case_start or 0)
        continuation_start = first_marker_index(text, ["The discharges on other muscles"], correspondence_start or case_start or 0)
        references_start = first_marker_index(text, ["\nReferences", "References"], continuation_start or case_start or 0)
        generic_summary_start = first_marker_index(text, ["Further study is desirable"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if (
            early_continuation_start is not None
            and early_continuation_end is not None
            and early_continuation_start < early_continuation_end
        ):
            ranges.append(trim_source_range(text, early_continuation_start, early_continuation_end))
        if case_start is not None and correspondence_start is not None and case_start < correspondence_start:
            ranges.append(trim_source_range(text, case_start, correspondence_start))
        if continuation_start is not None:
            continuation_end = generic_summary_start if generic_summary_start is not None else references_start
            if continuation_end is not None and continuation_start < continuation_end:
                ranges.append(trim_source_range(text, continuation_start, continuation_end))
        if ranges:
            return ranges

    if "A Patient With Atypical Stiff-Person" in text and "We describe a 34-year-old patient" in text:
        abstract_start = first_marker_index(text, ["We describe a patient with insulin-dependent"])
        abstract_end = first_marker_index(text, ["\nJ Clin Neuromusc", "J Clin Neuromusc"], abstract_start or 0)
        case_start = first_marker_index(text, ["We describe a 34-year-old patient"])
        front_matter_start = first_marker_index(text, ["\nFrom the Institute", "From the Institute"], case_start or 0)
        continuation_start = first_marker_index(text, ["using bipolar silver chloride electrodes"], front_matter_start or case_start or 0)
        references_start = first_marker_index(text, ["\nReferences", "References"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None and references_start is not None and continuation_start < references_start:
            ranges.append(trim_source_range(text, continuation_start, references_start))
        if ranges:
            return ranges

    if "Stiffness, Spasticity, or Both" in text and "The patient was a 41-year-old woman" in text:
        abstract_start = first_marker_index(text, ["We describe a\npatient", "We describe a patient"])
        abstract_end = first_marker_index(text, ["We review the clinical features", "\nJ Clin Neuromusc", "J Clin Neuromusc"], abstract_start or 0)
        case_start = first_marker_index(text, ["The patient was a 41-year-old woman"])
        front_matter_start = first_marker_index(text, ["\nFrom the *Department", "From the *Department"], case_start or 0)
        continuation_start = first_marker_index(text, ["normal head magnetic resonance image"], front_matter_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], continuation_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Our patient had most characteristics"], discussion_start or 0)
        generic_discussion_start = first_marker_index(text, ["Other diseases may resemble SPS"], patient_discussion_start or 0)
        treatment_patient_start = first_marker_index(text, ["In our patient, the response to"], generic_discussion_start or discussion_start or 0)
        references_start = first_marker_index(text, ["\nReferences", "References"], treatment_patient_start or discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if (
            patient_discussion_start is not None
            and generic_discussion_start is not None
            and patient_discussion_start < generic_discussion_start
        ):
            ranges.append(trim_source_range(text, patient_discussion_start, generic_discussion_start))
        if treatment_patient_start is not None and references_start is not None and treatment_patient_start < references_start:
            ranges.append(trim_source_range(text, treatment_patient_start, references_start))
        if ranges:
            return ranges

    if "Stiff limb syndrome: a case report" in text and "A 49-year-old man" in text:
        case_start = first_marker_index(text, ["\nCase presentation\nA 49-year-old", "Case presentation\nA 49-year-old"])
        correspondence_start = first_marker_index(text, ["\n* Correspondence", "* Correspondence"], case_start or 0)
        continuation_start = first_marker_index(text, ["HIV, syphilis"], correspondence_start or case_start or 0)
        consent_start = first_marker_index(text, ["\nConsent", "Consent"], continuation_start or case_start or 0)
        generic_discussion_start = first_marker_index(
            text,
            ["\nâ€œSLS", "â€œSLS", "\n\"SLS", "\"SLS", "\nSLS is a variant", "SLS is a variant", "is a variant of"],
            continuation_start or case_start or 0,
        )
        if generic_discussion_start is not None and text.startswith("is a variant of", generic_discussion_start):
            line_start = text.rfind("\n", 0, generic_discussion_start)
            if line_start >= 0:
                generic_discussion_start = line_start
        ranges: list[tuple[int, int]] = []
        if case_start is not None and correspondence_start is not None and case_start < correspondence_start:
            ranges.append(trim_source_range(text, case_start, correspondence_start))
        if continuation_start is not None:
            continuation_end = generic_discussion_start if generic_discussion_start is not None else consent_start
            if continuation_end is not None and continuation_start < continuation_end:
                ranges.append(trim_source_range(text, continuation_start, continuation_end))
        if ranges:
            return ranges

    if "sudden onset of shortness of breath" in text and "A 27-year-old Hispanic woman" in text:
        case_start = first_marker_index(text, ["\nCase presentation\nA 27-year-old", "Case presentation\nA 27-year-old"])
        correspondence_start = first_marker_index(text, ["\n* Correspondence", "* Correspondence"], case_start or 0)
        continuation_start = first_marker_index(text, ["palpitations and lightheadedness"], correspondence_start or case_start or 0)
        consent_start = first_marker_index(text, ["\nConsent", "Consent"], continuation_start or case_start or 0)
        generic_discussion_start = first_marker_index(
            text,
            ["\nThe GAD antibody is found", "The GAD antibody is found"],
            continuation_start or case_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if case_start is not None and correspondence_start is not None and case_start < correspondence_start:
            ranges.append(trim_source_range(text, case_start, correspondence_start))
        if continuation_start is not None:
            continuation_end = generic_discussion_start if generic_discussion_start is not None else consent_start
            if continuation_end is not None and continuation_start < continuation_end:
                ranges.append(trim_source_range(text, continuation_start, continuation_end))
        if ranges:
            return ranges

    if "stiff man syndrome and anaesthetic considerations" in text.lower() and "A 55 year old lady" in text:
        case_start = first_marker_index(text, ["\nCASE REPORT\nA 55 year old", "CASE REPORT\nA 55 year old"])
        correspondence_start = first_marker_index(
            text,
            ["\nDr. Harsha Shanthanna", "Dr. Harsha Shanthanna", "\nCorrespondence:", "Correspondence:"],
            case_start or 0,
        )
        continuation_start = first_marker_index(text, ["desired level; but adequate level"], correspondence_start or case_start or 0)
        references_start = first_marker_index(text, ["\nREFERENCES", "REFERENCES"], continuation_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and correspondence_start is not None and case_start < correspondence_start:
            ranges.append(trim_source_range(text, case_start, correspondence_start))
        if continuation_start is not None and references_start is not None and continuation_start < references_start:
            ranges.append(trim_source_range(text, continuation_start, references_start))
        if ranges:
            return ranges

    if "12-year-old right-handed Hispanic boy" in text and "rituximab" in text.lower():
        case_start = first_marker_index(text, ["The patient is a 12-year-old"])
        materials_start = first_marker_index(text, ["\nMaterials and Methods", "Materials and Methods"], case_start or 0)
        patient_discussion_start = first_marker_index(text, ["This childhood case demonstrates"], materials_start or case_start or 0)
        generic_trial_start = first_marker_index(text, ["Although a double-blind"], patient_discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and materials_start is not None and case_start < materials_start:
            ranges.append(trim_source_range(text, case_start, materials_start))
        if (
            patient_discussion_start is not None
            and generic_trial_start is not None
            and patient_discussion_start < generic_trial_start
        ):
            ranges.append(trim_source_range(text, patient_discussion_start, generic_trial_start))
        if ranges:
            return ranges

    if "Case Summary" in text and "A female in her 20s" in text and "Stiff Person Syndrome" in text:
        case_start = first_marker_index(text, ["A female in her 20s"])
        front_matter_start = first_marker_index(text, ["Clini Cal Medi Cine i nsights", "Clinical Medicine Insights"], case_start or 0)
        continuation_start = first_marker_index(text, ["and lower extremities, and the strengt"], front_matter_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nd iscussion", "d iscussion"], continuation_start or case_start or 0)
        patient_treatment_start = first_marker_index(text, ["Our patient did respond well"], discussion_start or 0)
        author_start = first_marker_index(text, ["\nAuthor Contributions", "Author Contributions"], patient_treatment_start or discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if patient_treatment_start is not None and author_start is not None and patient_treatment_start < author_start:
            ranges.append(trim_source_range(text, patient_treatment_start, author_start))
        if ranges:
            return ranges

    if "Stiff-Person Syndrome and Graves" in text and "9-year-old right-handed" in text:
        abstract_start = first_marker_index(text, ["A 9-year-old female child presented"])
        keywords_start = first_marker_index(text, ["\nKeywords", "Keywords"], abstract_start or 0)
        case_start = first_marker_index(text, ["A 9-year-old right-handed"])
        front_matter_start = first_marker_index(text, ["\n1 Department of Neurology", "1 Department of Neurology"], case_start or 0)
        continuation_start = first_marker_index(text, ["she had little clinical improvement"], front_matter_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], continuation_start or case_start or 0)
        conclusion_start = first_marker_index(text, ["In conclusion, this case highlights"], discussion_start or 0)
        author_start = first_marker_index(text, ["\nAuthor Contributions", "Author Contributions"], conclusion_start or discussion_start or 0)
        table_start = first_marker_index(text, ["Table 1. Results"], author_start or discussion_start or 0)
        table_end = first_marker_index(text, ["\n2 Child Neurology Open", "2 Child Neurology Open"], table_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and keywords_start is not None and abstract_start < keywords_start:
            ranges.append(trim_source_range(text, abstract_start, keywords_start))
        if case_start is not None and front_matter_start is not None and case_start < front_matter_start:
            ranges.append(trim_source_range(text, case_start, front_matter_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if conclusion_start is not None and author_start is not None and conclusion_start < author_start:
            ranges.append(trim_source_range(text, conclusion_start, author_start))
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "Therapeutic considerations in a case of progressive encephalomyelitis" in text and "A 63-year-old man" in text:
        case_start = first_marker_index(text, ["\n1. Case", "1. Case"])
        generic_discussion_start = first_marker_index(
            text,
            ["\nMore information is needed", "More information is needed"],
            case_start or 0,
        )
        acknowledgements_start = first_marker_index(text, ["\nAcknowledgements", "Acknowledgements"], case_start or 0)
        end = generic_discussion_start if generic_discussion_start is not None else acknowledgements_start
        if case_start is not None and end is not None and case_start < end:
            return [trim_source_range(text, case_start, end)]

    if "Mimicking Neuroleptic Malignant Syndrome" in text and "32-year-old male" in text:
        abstract_start = first_marker_index(text, ["We present a case of 32-year-old"])
        case_start = first_marker_index(text, ["A 32-year-old man"])
        if case_start is None:
            case_start = first_marker_index(text, ["CASE REPORT"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION"], case_start or abstract_start or 0)
        patient_discussion_start = first_marker_index(
            text,
            ["described in the literature. It is therefore"],
            discussion_start or case_start or abstract_start or 0,
        )
        conflicts_start = first_marker_index(text, ["\nConflicts of Interest", "Conflicts of Interest"], case_start or abstract_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None:
            abstract_end = case_start if case_start is not None else discussion_start
            if abstract_end is not None and abstract_start < abstract_end:
                ranges.append(trim_source_range(text, abstract_start, abstract_end))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if patient_discussion_start is not None and conflicts_start is not None and patient_discussion_start < conflicts_start:
            ranges.append(trim_source_range(text, patient_discussion_start, conflicts_start))
        if ranges:
            return ranges

    if "Why It Is Not Always Anxiety" in text and "A30-year-oldHaitianfemale" in text:
        case_start = first_marker_index(text, ["A30-year-oldHaitianfemale"])
        discussion_start = first_marker_index(text, ["\n2. Discussion", "2. Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            return [trim_source_range(text, case_start, discussion_start)]

    if "Difficult to Treat Focal" in text and "Ourpatientisa46-year-oldmale" in text:
        case_start = first_marker_index(text, ["\n2. Case Presentation", "2. Case Presentation"])
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        conclusion_start = first_marker_index(text, ["\n4. Conclusion", "4. Conclusion"], discussion_start or case_start or 0)
        conflicts_start = first_marker_index(text, ["\nConflicts of Interest", "Conflicts of Interest"], conclusion_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if conclusion_start is not None and conflicts_start is not None and conclusion_start < conflicts_start:
            ranges.append(trim_source_range(text, conclusion_start, conflicts_start))
        if ranges:
            return ranges

    if "Anti-glutamic acid decarboxylase" in text and "A 49-year-old plumber" in text:
        case_start = first_marker_index(text, ["\nCase Presentation", "Case Presentation"])
        additional_start = first_marker_index(text, ["\nAdditional Information", "Additional Information"], case_start or 0)
        if case_start is not None and additional_start is not None and case_start < additional_start:
            return [trim_source_range(text, case_start, additional_start)]

    if "Utility of Botulinum Injections in Stiff-Person Syndrome" in text:
        case_start = first_marker_index(text, ["A 38-year-old female"])
        next_case_start = first_marker_index(
            text,
            ["\nIn 2003", "In 2003", "\nLikewise", "Likewise", "\nSimilarly", "Similarly"],
            case_start or 0,
        )
        if case_start is not None and next_case_start is not None and case_start < next_case_start:
            return [trim_source_range(text, case_start, next_case_start)]

    if "Presenting Initially as Acute Peripheral" in text and "A 58-year-old previously healthy female" in text:
        case_start = first_marker_index(text, ["\nCase Presentation", "Case Presentation"])
        additional_start = first_marker_index(text, ["\nAdditional Information", "Additional Information"], case_start or 0)
        if case_start is not None and additional_start is not None and case_start < additional_start:
            return [trim_source_range(text, case_start, additional_start)]

    if "Therapeutic Plasma Exchange" in text and "A 68-year-old man presented" in text:
        case_start = first_marker_index(text, ["\nCase Presentation", "Case Presentation"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        patient_discussion_start = first_marker_index(
            text,
            ["In this patient with symptoms of severe uncontrolled SPS", "In this patient"],
            discussion_start or case_start or 0,
        )
        additional_start = first_marker_index(text, ["\nAdditional Information", "Additional Information"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None:
            case_end = discussion_start if discussion_start is not None else additional_start
            if case_end is not None and case_start < case_end:
                ranges.append(trim_source_range(text, case_start, case_end))
        if patient_discussion_start is not None and additional_start is not None and patient_discussion_start < additional_start:
            ranges.append(trim_source_range(text, patient_discussion_start, additional_start))
        if ranges:
            return ranges

    if (
        "A 57-year-old female" in text
        and ("vertical diplopia" in text or "Review of the Literature" in text)
    ):
        case_start = first_marker_index(text, ["\nPresentation\nA 57-year-old", "Presentation\nA 57-year-old"])
        duplicate_header_start = first_marker_index(text, ["\nSmith, J and Storey", "Smith, J and Storey"], case_start or 0)
        continuation_start = first_marker_index(text, ["After the onset"], duplicate_header_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], continuation_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["The patient discussed in this case report"], discussion_start or 0)
        generic_discussion_start = first_marker_index(
            text,
            ["SPS is a rare", "There is currently a paucity"],
            patient_discussion_start or discussion_start or 0,
        )
        literature_start = first_marker_index(
            text,
            ["(Table 2 )", "Table 2 )", "Several other neuro-ophthalmic", "\nTable 2: Reported", "Table 2: Reported"],
            discussion_start or case_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if case_start is not None:
            first_end = duplicate_header_start if duplicate_header_start is not None else discussion_start
            if first_end is not None and case_start < first_end:
                ranges.append(trim_source_range(text, case_start, first_end))
        if continuation_start is not None:
            continuation_end = discussion_start
            if continuation_end is not None and continuation_start < continuation_end:
                ranges.append(trim_source_range(text, continuation_start, continuation_end))
        if patient_discussion_start is not None:
            patient_discussion_end = generic_discussion_start if generic_discussion_start is not None else literature_start
            if patient_discussion_end is not None and patient_discussion_start < patient_discussion_end:
                ranges.append(trim_source_range(text, patient_discussion_start, patient_discussion_end))
        if ranges:
            return ranges

    if "Spasms and Myoclonus in a Young Woman" in text and "A 39-year-old woman" in text:
        case_start = first_marker_index(text, ["A 39-year-old woman"])
        footer_start = first_marker_index(text, ["\nJAMA Neurology May 2020", "JAMA Neurology May 2020"], case_start or 0)
        diagnosis_start = first_marker_index(text, ["\nDiagnosis\nD.", "Diagnosis\nD."], footer_start or case_start or 0)
        article_info_start = first_marker_index(text, ["\nARTICLE INFORMATION", "ARTICLE INFORMATION"], diagnosis_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and footer_start is not None and case_start < footer_start:
            ranges.append(trim_source_range(text, case_start, footer_start))
        if diagnosis_start is not None and article_info_start is not None and diagnosis_start < article_info_start:
            ranges.append(trim_source_range(text, diagnosis_start, article_info_start))
        if ranges:
            return ranges

    if "Involuntary movement in stiff-person syndrome" in text and "A 69-year-old man" in text:
        case_start = first_marker_index(text, ["\n2. Case presentation", "2. Case presentation"])
        editor_start = first_marker_index(text, ["\nEditor:", "Editor:"], case_start or 0)
        continuation_start = first_marker_index(text, ["toms disappeared after falling asleep"], editor_start or case_start or 0)
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], continuation_start or case_start or 0)
        patient_discussion_start = first_marker_index(text, ["Our patient"], discussion_start or 0)
        acknowledgments_start = first_marker_index(text, ["\nAcknowledgments", "Acknowledgments"], patient_discussion_start or discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and editor_start is not None and case_start < editor_start:
            ranges.append(trim_source_range(text, case_start, editor_start))
        if continuation_start is not None and discussion_start is not None and continuation_start < discussion_start:
            ranges.append(trim_source_range(text, continuation_start, discussion_start))
        if (
            patient_discussion_start is not None
            and acknowledgments_start is not None
            and patient_discussion_start < acknowledgments_start
        ):
            ranges.append(trim_source_range(text, patient_discussion_start, acknowledgments_start))
        if ranges:
            return ranges

    if "comorbid bipolar and panic disorders" in text and "The patient was a 58-year-old white female" in text:
        case_start = first_marker_index(text, ["\nCase Report\nThe patient was", "Case Report\nThe patient was"])
        references_start = first_marker_index(text, ["\nReferences", "References"], case_start or 0)
        if case_start is not None and references_start is not None and case_start < references_start:
            return [trim_source_range(text, case_start, references_start)]

    if "SeeingPastComorbiditiestoReachthe" in text and "2.CasePresentation" in text:
        case_start = first_marker_index(text, ["\n2.CasePresentation", "2.CasePresentation"])
        discussion_start = first_marker_index(text, ["\n3.Discussion", "3.Discussion"], case_start or 0)
        per_review_start = first_marker_index(
            text,
            ["Per\nreviewbyWitte", "Per\nreview by Witte", "Per review"],
            discussion_start or case_start or 0,
        )
        treatment_start = first_marker_index(text, ["Upon diagnosis of our patient"], discussion_start or case_start or 0)
        data_start = first_marker_index(text, ["\nDataAvailability", "DataAvailability"], treatment_start or discussion_start or case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if discussion_start is not None:
            discussion_end = per_review_start if per_review_start is not None else treatment_start
            if discussion_end is not None and discussion_start < discussion_end:
                ranges.append(trim_source_range(text, discussion_start, discussion_end))
        if treatment_start is not None and data_start is not None and treatment_start < data_start:
            ranges.append(trim_source_range(text, treatment_start, data_start))
        if ranges:
            return ranges

    if "Anti-Glutamic\nAcid Decarboxylase Autoimmune Encephalitis" in text and "CASE DESCRIPTION" in text:
        abstract_start = first_marker_index(text, ["Abstract A 34-year-old"])
        introduction_start = first_marker_index(text, ["\nINTRODUCTION", "INTRODUCTION"], abstract_start or 0)
        case_start = first_marker_index(text, ["\nCASE DESCRIPTION", "CASE DESCRIPTION"], introduction_start or 0)
        end = first_marker_index(text, ["\nConflict of interests", "Conflict of interests", "\nREFERENCES"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if abstract_start is not None and introduction_start is not None and abstract_start < introduction_start:
            ranges.append(trim_source_range(text, abstract_start, introduction_start))
        if case_start is not None and end is not None and case_start < end:
            ranges.append(trim_source_range(text, case_start, end))
        if ranges:
            return ranges

    if "Severe Chin-on-Chest Cervical Spine Deformity" in text and "he patient is a 64-year-old man" in text:
        case_start = first_marker_index(text, ["\nCase Report\nhe patient is", "Case Report\nhe patient is"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        case_discussion_start = first_marker_index(text, ["This case was complicated"], discussion_start or case_start or 0)
        author_start = first_marker_index(text, ["\nStephen R. Stephan", "Stephen R. Stephan, MD"], case_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None:
            case_end = discussion_start if discussion_start is not None else author_start
            if case_end is not None and case_start < case_end:
                ranges.append(trim_source_range(text, case_start, case_end))
        if case_discussion_start is not None and author_start is not None and case_discussion_start < author_start:
            ranges.append(trim_source_range(text, case_discussion_start, author_start))
        if ranges:
            return ranges

    if "Stiff-Man Syndrome with GAD-Like" in text and "Response of a Patient to" in text:
        title_start = first_marker_index(text, ["Stiff-Man Syndrome with GAD-Like"])
        next_abstract_start = first_marker_index(
            text,
            ["\n248P", "248P\nTreatment", "248P \nTreatment"],
            title_start or 0,
        )
        if title_start is not None and next_abstract_start is not None and title_start < next_abstract_start:
            return [trim_source_range(text, title_start, next_abstract_start)]

    if "A Fatal Case of Neuroleptic Malignant Syndrome" in text and "stiff leg syndrome" in text.lower():
        summary_start = first_marker_index(text, ["\nSummary\nStiff leg syndrome", "Summary\nStiff leg syndrome"])
        introduction_start = first_marker_index(text, ["\nIntroduction", "Introduction"], summary_start or 0)
        case_start = first_marker_index(text, ["\nCase Report\nAn 35-year-old", "Case Report\nAn 35-year-old", "\nCase report\n", "Case report\n"])
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], case_start or 0)
        criteria_start = first_marker_index(text, ["This patient met"], discussion_start or case_start or 0)
        criteria_end = first_marker_index(text, [" According to the DSM-IV criteria", "According to the DSM-IV criteria"], criteria_start or 0)
        risk_start = first_marker_index(text, ["Our patient had some of the risk factors"], discussion_start or case_start or 0)
        risk_end = first_marker_index(text, ["\nSuccessful treatment", "Successful treatment"], risk_start or 0)
        patient_mechanism_start = first_marker_index(
            text,
            ["No signs of autonomic hyperactivity were observed", "Altogether, disturbance"],
            risk_end or discussion_start or case_start or 0,
        )
        complication_start = first_marker_index(text, ["Complication of NMS", "Complications of NMS"], patient_mechanism_start or 0)
        ranges: list[tuple[int, int]] = []
        if summary_start is not None and introduction_start is not None and summary_start < introduction_start:
            ranges.append(trim_source_range(text, summary_start, introduction_start))
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if criteria_start is not None and criteria_end is not None and criteria_start < criteria_end:
            ranges.append(trim_source_range(text, criteria_start, criteria_end))
        if risk_start is not None and risk_end is not None and risk_start < risk_end:
            ranges.append(trim_source_range(text, risk_start, risk_end))
        if patient_mechanism_start is not None and complication_start is not None and patient_mechanism_start < complication_start:
            ranges.append(trim_source_range(text, patient_mechanism_start, complication_start))
        if ranges:
            return ranges

    if "Brainstem involvement as onset of stiff limb syndrome" in text and "Case Report: We describe the case" in text:
        start = first_marker_index(text, ["\nP738\nBrainstem involvement", "P738\nBrainstem involvement"])
        end = first_marker_index(text, ["\nP739\n", "P739\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Stiff-person syndrome presenting with asymmetric axial muscle" in text and "C. Chuang" in text:
        start = first_marker_index(text, ["\nP778\nStiff-person syndrome", "P778\nStiff-person syndrome"])
        end = first_marker_index(text, ["\nP779\n", "P779\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Rehabilitation and orthopedic management of Stiff Person" in text and "Objective: We report the case of a 71-year-old female" in text:
        start = first_marker_index(text, ["\nMo-352\nRehabilitation", "Mo-352\nRehabilitation"])
        end = first_marker_index(text, ["\nMo-353\n", "Mo-353\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "The Stiff Person Syndrome: A Single Case" in text and "36 year old lady" in text:
        start = first_marker_index(text, ["\nPOS.120\nThe Stiff Person", "POS.120\nThe Stiff Person"])
        end = first_marker_index(text, ["\nA376 NEUROLOGY", "A376 NEUROLOGY"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A Videography Documented Case Report" in text and "Antibody-Negative Stiff-Person Syndrome" in text:
        start = first_marker_index(text, ["\nPO5.115\nA Videography", "PO5.115\nA Videography"])
        end = first_marker_index(text, ["\nDisclosure: Dr. Fong", "Disclosure: Dr. Fong", "\nP05.116", "P05.116"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Comorbid Idiopathic Parkinson's Disease and Stiff Person" in text and "Case: A 67-" in text:
        start = first_marker_index(text, ["Case: A 67-"])
        end = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "TitlePartial Stiff Person Syndrome as a Stroke Mimic" in text and "Our patient is a 62 year old female" in text:
        start = first_marker_index(text, ["\nObjective", "Objective"])
        end = len(text)
        if start is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A CASE OF UNDIAGNOSED STIFF-PERSON" in text and "REQUIRING MECHANICAL" in text:
        start = first_marker_index(text, ["A 38 year-old women", "A 38 year-old woman"])
        end = first_marker_index(text, ["\n© 2012", "\nÂ© 2012", "© 2012", "Â© 2012"], start or 0)
        if start is not None:
            return [trim_source_range(text, start, end if end is not None else len(text))]

    if "Severe, Prolonged Baclofen Withdrawal" in text and "Patient Case" in text:
        start = first_marker_index(text, ["Patient Case"])
        end = first_marker_index(text, ["\nSevere, Prolonged Baclofen Withdrawal Following a Second"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A Rare Case of Amphiphysin-associated Stiff Person Syndrome" in text:
        start = first_marker_index(text, ["Results: A 53-year-old man"])
        end = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], start or 0)
        if start is not None:
            return [trim_source_range(text, start, end if end is not None else len(text))]

    if "Treatment resistant jerky stiff person syndrome" in text and "28 male" in text:
        start = first_marker_index(text, ["\nP380\nTreatment resistant", "P380\nTreatment resistant"])
        end = first_marker_index(text, ["\nP381\n", "P381\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "TherapeuticPlasmaExchange" in text and "Stiff-PersonSyndrome:CaseReport" in text:
        start = first_marker_index(text, ["\nCASE REPORT", "CASE REPORT"])
        end = first_marker_index(
            text,
            ["\nCONCLU SION", "CONCLU SION", "\nTurkiye Klinikleri J Med Sci 2012;32(6) 1765"],
            start or 0,
        )
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if (
        ("AUTOIMMUNE MYASTHENIA" in text or "Autoimmune myastenia gravis" in text)
        and "Case report" in text
        and "age of 54" in text
    ):
        start = first_marker_index(text, ["\nCase report", "Case report"])
        end = first_marker_index(text, ["\nAddress reprint requests", "Address reprint requests"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Stiff person syndrome (SPS)" in text and "We present a case of a 45-year-old black female" in text:
        start = first_marker_index(text, ["We present a case of a 45-year-old black female"])
        end = first_marker_index(text, ["\nAcknowledgement.", "Acknowledgement.", "\nReferences"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Stiff Person Syndrome (SPS): A Pediatric Case Report" in text and "Clinical evulation" in text:
        start = first_marker_index(text, ["Stiff Person Syndrome (SPS): A Pediatric Case Report"])
        end = first_marker_index(text, ["\nP-460", "P-460"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Purely Torsional Nystagmus in a Patient" in text and "Stiff-Man Syndrome" in text:
        start = first_marker_index(text, ["Purely Torsional Nystagmus in a Patient"])
        end = first_marker_index(text, ["\n268P", "268P"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "INTERACTN CASE SUMMARY" in text and "Diagnosis: Myasthenia Gravis-Stiff Person Syndrome" in text:
        start = first_marker_index(text, ["Case Summary"])
        end = first_marker_index(text, ["\nDiscussion", "Discussion"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Treatment with intravenous prednisone" in text and "progressive encephalomyelitis with" in text:
        start = first_marker_index(text, ["Treatment with intravenous prednisone"])
        end = first_marker_index(text, ["\nWe thank", "We thank", "\nJ A MOLINA", "J A MOLINA"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Stiff Limb Syndrome: A Case Report and Diagnostic Criteria" in text and "65 year old female" in text:
        case_start = first_marker_index(text, ["Case Description"])
        diagnostic_start = first_marker_index(text, ["\nDiagnostic Stiff Limb", "Diagnostic Stiff Limb"], case_start or 0)
        exam_start = first_marker_index(text, ["On exam she had increased tone"], diagnostic_start or case_start or 0)
        references_start = first_marker_index(text, ["\n1 Barker", "1 Barker"], exam_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and diagnostic_start is not None and case_start < diagnostic_start:
            ranges.append(trim_source_range(text, case_start, diagnostic_start))
        if exam_start is not None and references_start is not None and exam_start < references_start:
            ranges.append(trim_source_range(text, exam_start, references_start))
        if ranges:
            return ranges

    if "Anti-GAD antibody-positive myoclonic leg jerks" in text and "A 62-year-old man presented" in text:
        start = first_marker_index(text, ["\nCase report\nA 62-year-old", "Case report\nA 62-year-old"])
        end = first_marker_index(
            text,
            ["\nConï¬‚ict of interest", "Conï¬‚ict of interest", "\nConﬂict of interest", "Conﬂict of interest", "\nConflict of interest", "Conflict of interest", "\nReferences"],
            start or 0,
        )
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "IMMUNE SYSTEM MODULATION IN A PATIENT WITH STIFF-MAN" in text and "36 year old female patient" in text:
        start = first_marker_index(text, ["IMMUNE SYSTEM MODULATION IN A PATIENT WITH STIFF-MAN"])
        end = first_marker_index(text, ["\n101A", "101A"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "GLYCINE RECEPTOR ANTIBODY MEDIATED PROGRESSIVE" in text and "A 40-year-old man was intubated" in text:
        start = first_marker_index(text, ["A 40-year-old man was intubated"])
        end = first_marker_index(text, ["\nA8\n", "A8\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "STIFF PERSON SYNDROME IMPROVEMENT" in text and "CUTANEOUS T CELL LYMPHOMA" in text:
        start = first_marker_index(text, ["A 57-year-old Caucasian woman"])
        end = first_marker_index(text, ["\nFIGURE 1.", "FIGURE 1.", "\nGoran Rakocevic"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Objective: To investigate structure of muscle and cytoskeleton" in text and "A 49-year-old lady" in text:
        start = first_marker_index(text, ["Objective: To investigate structure of muscle and cytoskeleton"])
        end = first_marker_index(text, ["\n16 Short Communications", "16 Short Communications", "\nSC204", "SC204"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Spinal segmental myoclonus in both legs" in text and "A 69-year-old man was given a diagnosis" in text:
        case_start = first_marker_index(text, ["\nCase report\nA 69-year-old", "Case report\nA 69-year-old"])
        case_end = first_marker_index(text, ["\n*These authors", "*These authors"], case_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion\n", "Discussion\n"], case_end or case_start or 0)
        discussion_end = first_marker_index(text, ["\nAuthor contributions", "Author contributions"], discussion_start or 0)
        ranges: list[tuple[int, int]] = []
        if case_start is not None and case_end is not None and case_start < case_end:
            ranges.append(trim_source_range(text, case_start, case_end))
        if discussion_start is not None and discussion_end is not None and discussion_start < discussion_end:
            ranges.append(trim_source_range(text, discussion_start, discussion_end))
        if ranges:
            return ranges

    if "Our patient is the first reported" in text and "Serum anti-GAD level was 14 000 U/ml" in text:
        case_start = first_marker_index(text, ["\nCase report\nA 69-year-old", "Case report\nA 69-year-old"])
        page_break_start = first_marker_index(text, ["\nFigure 1 Fundoscopy of gyrate atrophy.", "Figure 1 Fundoscopy of gyrate atrophy."], case_start or 0)
        continuation_start = first_marker_index(text, ["\nthe more symptomatic left side)", "the more symptomatic left side)"], page_break_start or case_start or 0)
        end = first_marker_index(text, ["\nP L Guardado", "P L Guardado", "\nReferences"], continuation_start or case_start or 0)
        second_footer_start = first_marker_index(text, ["\n658 PostScript", "658 PostScript"], continuation_start or 0)
        post_footer_start = first_marker_index(
            text,
            ["\nand eye movement abnormalities without", "and eye movement abnormalities without"],
            second_footer_start or continuation_start or 0,
        )
        ranges: list[tuple[int, int]] = []
        if case_start is not None and page_break_start is not None and case_start < page_break_start:
            ranges.append(trim_source_range(text, case_start, page_break_start))
        if (
            continuation_start is not None
            and second_footer_start is not None
            and continuation_start < second_footer_start
        ):
            ranges.append(trim_source_range(text, continuation_start, second_footer_start))
        if post_footer_start is not None and end is not None and post_footer_start < end:
            ranges.append(trim_source_range(text, post_footer_start, end))
        elif continuation_start is not None and end is not None and continuation_start < end:
            ranges.append(trim_source_range(text, continuation_start, end))
        if ranges:
            return ranges

    if "Follow-up in Stiff Person Syndrome with immunoglobulin treatment" in text and "Objectives: To present the 4-year follow-up" in text:
        start = first_marker_index(text, ["\nP7.6\nFollow-up", "P7.6\nFollow-up", "Follow-up in Stiff Person Syndrome"])
        end = first_marker_index(text, ["\nP7.7\n", "P7.7\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Poster 278" in text and "Rehabilitation of Stiff Person Syndrome Presenting" in text:
        start = first_marker_index(text, ["\nPoster 278", "Poster 278"])
        end = first_marker_index(text, ["\nPoster 279", "Poster 279"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Poster 408" in text and "Severe Spasticity in a Patient With Stiff Person" in text:
        start = first_marker_index(text, ["\nPoster 408", "Poster 408"])
        end = first_marker_index(text, ["\nPoster 409", "Poster 409"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "1.313\nSTIFF PERSON SYNDROME ASSOCIATED WITH AUTOIMMUNE" in text:
        start = first_marker_index(text, ["\n1.313\nSTIFF PERSON", "1.313\nSTIFF PERSON"])
        end = first_marker_index(text, ["\n1.314\n", "1.314\n"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Relapsing Anti-Glycine Receptor Antibody Mediated Encephalitis" in text and "A 65 year old man presented" in text:
        start = first_marker_index(text, ["Objective: To describe a clinical case of PERM"])
        end = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "116. Stiff person syndrome improvement with chemotherapy" in text and "cutaneous T cell lymphoma" in text:
        start = first_marker_index(text, ["\n116. Stiff person syndrome", "116. Stiff person syndrome"])
        end = first_marker_index(text, ["\ndoi:10.1016/j.clinph.2011.11.198", "doi:10.1016/j.clinph.2011.11.198"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "We present a case of a 49year-old female with exacerbation of SPS" in text and "Therapeutic plasma exchange" in text:
        start = first_marker_index(text, ["Abstract: The stiff person syndrome"])
        end = first_marker_index(text, ["\nConflict of interests"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A 63-year-old man presented with recurrent generalized" in text and "nivolumab" in text and "PDE10A-IgG" in text:
        start = first_marker_index(text, ["Case report\nA 63-year-old man", "Case report\r\nA 63-year-old man"])
        end = first_marker_index(text, ["\nAvailability of data and material"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "citalopram in an 80-year-old-right handed woman" in text and "Author Roles" in text:
        ranges: list[tuple[int, int]] = []
        start = first_marker_index(text, ["Case Report\nWe report profound", "Case Report\r\nWe report profound"])
        contact_start = first_marker_index(text, ["\n*Correspondence to:", "*Correspondence to:"], start or 0)
        if start is not None and contact_start is not None and start < contact_start:
            ranges.append(trim_source_range(text, start, contact_start))
        continuation_start = first_marker_index(text, ["33% reduction"], contact_start or start or 0)
        literature_start = first_marker_index(text, ["\nDiscussion\n", "\nCitalopram, however"], continuation_start or 0)
        if continuation_start is not None and literature_start is not None and continuation_start < literature_start:
            ranges.append(trim_source_range(text, continuation_start, literature_start))
        table_start = first_marker_index(text, ["TABLE 1 The stiffness index"], literature_start or continuation_start or 0)
        table_end = first_marker_index(text, ["\nMOVEMENT DISORDERS CLINICAL PRACTICE"], table_start or 0)
        if table_start is not None and table_end is not None and table_start < table_end:
            ranges.append(trim_source_range(text, table_start, table_end))
        if ranges:
            return ranges

    if "25-year-old Vietnamese female patient with" in text and "anti-SOX1 antibodies" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Abstract\nStiff Person Syndrome", "Abstract\r\nStiff Person Syndrome"])
        abstract_end = first_marker_index(text, ["\nÂ© 2022", "\n© 2022", "\nReceived:"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        case_start = first_marker_index(text, ["Case Presentation\nA 25-year-old"])
        end = first_marker_index(text, ["\nAcknowledgments", "\nStatement of Ethics"], case_start or 0)
        if end is None:
            end = first_marker_index(text, ["\n243\nCase Rep Neurol", "\nCopyright."], case_start or 0)
        if case_start is not None and end is not None and case_start < end:
            ranges.append(trim_source_range(text, case_start, end))
        if ranges:
            return ranges

    if "Case report; In this report, we present a rare case of a 79-year-old woman" in text:
        start = first_marker_index(text, ["Case report; In this report"])
        end = first_marker_index(text, ["\nQ KEYWORDS:", "\nDeclaration of interest", "\nFunding"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Case report: A 38-year-old woman with stiff" in text and "intrathecal baclofen" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Case report: A 38-year-old"])
        abstract_end = first_marker_index(
            text,
            ["\nKey words:", "\nAccepted", "\nCorrespondence address:", "\nACKNOWLEDGEMENT", "\nACKNOWLEDGMENT"],
            abstract_start or 0,
        )
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        body_start = first_marker_index(text, ["\nT\n\nhis case describes", "\nThis case describes"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], body_start or 0)
        if body_start is not None and discussion_start is not None and body_start < discussion_start:
            ranges.append(trim_source_range(text, body_start, discussion_start))
        if ranges:
            return ranges

    if "A Case of Anti-GAD 65 Autoimmune Encephalitis Associated" in text and "2. Case Description" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Abstract: Glutamic acid decarboxylase"])
        abstract_end = first_marker_index(text, ["\nKeywords:", "\n1. Introduction"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        case_start = first_marker_index(text, ["\n2. Case Description", "2. Case Description"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\n3. Discussion", "3. Discussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "PT_he patient is a 50-year-old woman" in text and "3.Discussion" in text:
        start = first_marker_index(text, ["2.CasePresentation"])
        end = first_marker_index(text, ["\n3.Discussion"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Case presentation\nA 54-year-old male presented" in text and "amphiphysin-IgG" in text:
        start = first_marker_index(text, ["Case presentation\nA 54-year-old male"])
        end = first_marker_index(text, ["\nDiscussion"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "urothelial carcinoma" in text and "A 72-years-old Caucasian male" in text and "anti-glycine receptor" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Abstract \nBackground", "Abstract\nBackground"])
        abstract_end = first_marker_index(text, ["\nKeywords"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        case_start = first_marker_index(text, ["\nCase presentation\nA 72-years-old", "Case presentation\nA 72-years-old"], abstract_end or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Immunotherapy-Responsive" in text and "Glycine Receptor Autoantibodies" in text and "A 33-year-old woman" in text:
        start = first_marker_index(text, ["\nCase Report\nA 33-year-old woman", "Case Report\nA 33-year-old woman"])
        end = first_marker_index(text, ["\nDiscussion", "\nThis case suggests"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Thymoma-Related Stiff-Person Syndrome" in text and "A 26-year-old woman visited" in text:
        start = first_marker_index(text, ["Case Report\nA 26-year-old woman visited", "Case Report\r\nA 26-year-old woman visited"])
        end = first_marker_index(text, ["\nDiscussion"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Teaching Video NeuroImage: Hung-Up Reflex in Stiff Limb" in text:
        start = first_marker_index(text, ["A 45-year-old woman developed"])
        end = first_marker_index(text, ["\nAppendix Authors", "\nFootnote", "\nReferences"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Postoperative hypotonia in a patient with stiff person syndrome" in text and "A 46-yr-old female" in text:
        ranges: list[tuple[int, int]] = []
        case_heading = first_marker_index(text, ["\nCase report", "Case report"])
        start = first_marker_index(text, ["A 46-yr-old female"], case_heading or 0)
        table_start = first_marker_index(text, ["\nTable 1 Summary of case reports"], start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], start or 0)
        first_end_candidates = [index for index in [table_start, discussion_start] if index is not None]
        if start is not None and first_end_candidates:
            first_end = min(first_end_candidates)
            if start < first_end:
                ranges.append(trim_source_range(text, start, first_end))
        continuation_start = first_marker_index(
            text,
            ["\nThe option of a strictly regional/local anesthesia technique"],
            table_start or start or 0,
        )
        literature_start = first_marker_index(text, ["\nLiterature review"], continuation_start or 0)
        if continuation_start is not None and literature_start is not None and continuation_start < literature_start:
            ranges.append(trim_source_range(text, continuation_start, literature_start))
        if ranges:
            return ranges

    if "Glutamic acid decarboxylase (GAD) antibody- positive" in text and "mediastinal liposarcoma" in text:
        ranges: list[tuple[int, int]] = []
        summary_start = first_marker_index(text, ["SUMMARY"])
        background_start = first_marker_index(text, ["\nBACKGROUND"], summary_start or 0)
        if summary_start is not None and background_start is not None and summary_start < background_start:
            ranges.append(trim_source_range(text, summary_start, background_start))
        case_start = first_marker_index(text, ["CASE PRESENTATION"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Characterization of CD4+ T cells specific" in text and "patient with SPS who remained normoglycaemic" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Abstract\nBackground", "Abstract"])
        abstract_end = first_marker_index(text, ["\nKeywords"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        patient_start = first_marker_index(text, ["\nThe patient\nThe patient is a 33-year-old", "The patient is a 33-year-old"])
        patient_end = first_marker_index(text, ["\nPeripheral blood samples", "Peripheral blood samples"], patient_start or 0)
        if patient_start is not None and patient_end is not None and patient_start < patient_end:
            ranges.append(trim_source_range(text, patient_start, patient_end))
        results_start = first_marker_index(text, ["\nResults\nInhibition", "Results\nInhibition"], patient_end or patient_start or 0)
        discussion_start = first_marker_index(text, ["\nDiscussion", "Discussion"], results_start or 0)
        if results_start is not None and discussion_start is not None and results_start < discussion_start:
            ranges.append(trim_source_range(text, results_start, discussion_start))
        summary_start = first_marker_index(text, ["\nIn summary, this longitudinal study", "In summary, this longitudinal study"], discussion_start or results_start or 0)
        acknowledgement_start = first_marker_index(text, ["\nAcknowledgements", "Acknowledgements"], summary_start or 0)
        if summary_start is not None and acknowledgement_start is not None and summary_start < acknowledgement_start:
            ranges.append(trim_source_range(text, summary_start, acknowledgement_start))
        if ranges:
            return ranges

    if "The use of combined therapy with CFPE and IVIG" in text and "refractory standard therapy for stiff person syndrome" in text:
        start = first_marker_index(text, ["118836\nThe use of combined therapy", "The use of combined therapy"])
        end = first_marker_index(text, ["\ndoi:10.1016/j.jns.2021.1 18836", "\n118837"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "M207. Stiff Person Syndrome in a Patient with Atypical" in text and "Antiamphiphysin Antibodies: A Case Report" in text:
        start = first_marker_index(text, ["M207. Stiff Person Syndrome"])
        end = first_marker_index(text, ["\nM208. Synucleionopathy", "\nM208."], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Paraneoplastic stiff-person syndrome with" in text and "lung cancer: a case report and literature review" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["Abstract: Stiff person syndrome"])
        abstract_end = first_marker_index(text, ["\nKeywords:"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        case_start = first_marker_index(text, ["\nCase description", "Case description"])
        discussion_start = first_marker_index(text, ["\nDiscussion"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        if ranges:
            return ranges

    if "Antibodies to glutamic acid decarboxylase (GAD)" in text and "Case Presentation" in text and "A 46-year-old woman" in text:
        start = first_marker_index(text, ["Case Presentation"])
        end = first_marker_index(text, ["\n5. Discussion", "5. Discussion"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A 62-year-old Japanese man was transferred" in text and "ANTIBODY ASSAYS" in text:
        start = first_marker_index(text, ["CASE DESCRIPTION"])
        end = first_marker_index(text, ["\nDATA AVAILABILITY STATEMENT", "DATA AVAILABILITY STATEMENT"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Proprioceptive Stimuli" in text and "A healthy 74-year-old woman" in text and "Study Funding" in text:
        start = first_marker_index(text, ["VIDEO NEUROIMAGE", "Proprioceptive Stimuli"])
        end = first_marker_index(text, ["\nStudy Funding", "Study Funding"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "PERM Initiated as Facial Palsy" in text and "CASE PRESENTATION" in text and "A 61-year-old" in text:
        start = first_marker_index(text, ["CASE PRESENTATION"])
        end = first_marker_index(text, ["\nDISCUSSION", "DISCUSSION", "\nCONCLUSION", "CONCLUSION"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if (
        "A 75-year-old male patient" in text
        and "GlyR" in text
        and ("herpes zoster" in text or "varicella-zoster virus" in text)
    ):
        start = first_marker_index(text, ["A 75-year-old male patient"])
        end = first_marker_index(text, ["\nDiscussion", "Discussion", "\nData availability statement", "Data availability statement"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Table 6 Stiff-person syndrome" in text and "18F-FDG-PET" in text and "paraneoplastic neurological syndrome" in text:
        start = first_marker_index(text, ["Table 6 Stiff-person syndrome"])
        end = first_marker_index(text, ["\nTable 4 Salient findings", "Table 4 Salient findings"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "A 59-year-old patient" in text and "GlyR antibody" in text and "aHSCT" in text:
        start = first_marker_index(text, ["A 59-year-old patient"])
        end = first_marker_index(text, ["\nDisclosure:", "Disclosure:"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "040 RASH DECISIONS" in text and "72 year old woman" in text and "glycine receptor (GlyR) antibody positive" in text:
        start = first_marker_index(text, ["W e describe the case", "We describe the case"])
        footer_start = first_marker_index(
            text,
            ["\nJ Neurol Neurosurg Psychiatry 2013;84:e2 17 of 95", "J Neurol Neurosurg Psychiatry 2013;84:e2 17 of 95"],
            start or 0,
        )
        continuation_start = first_marker_index(text, ["\nRamsey", "Ramsey"], footer_start or start or 0)
        references_start = first_marker_index(text, ["\nREFERENCES", "REFERENCES"], continuation_start or start or 0)
        ranges: list[tuple[int, int]] = []
        if start is not None and footer_start is not None and start < footer_start:
            ranges.append(trim_source_range(text, start, footer_start))
        if continuation_start is not None and references_start is not None and continuation_start < references_start:
            ranges.append(trim_source_range(text, continuation_start, references_start))
        if ranges:
            return ranges

    if "Syndrome de « l’homme raide » traité par immunoglobulines intraveineuses" in text and "Cas 02/96. Un homme de 48 ans" in text:
        start = first_marker_index(text, ["Syndrome de « l’homme raide » traité"])
        end = first_marker_index(text, ["\nC. Sevrin", "C. Sevrin", "\nREFERENCES"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "STIFF-MAN SYNDROME : A CASE REPORT" in text and "MAQ, a 50-year-old male" in text:
        start = first_marker_index(text, ["\nCASE REPORT:\n\nMAQ", "CASE REPORT:\n\nMAQ"])
        end = first_marker_index(text, ["\nREFERENCES", "REFERENCES"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "STIFF PERSON SYNDROME WITH ATYPICAL FEATURES AND A FAVOURABLE" in text and "A forty year old male patient" in text:
        ranges: list[tuple[int, int]] = []
        abstract_start = first_marker_index(text, ["\nABSTRACT \nStiff Person Syndrome", "ABSTRACT \nStiff Person Syndrome"])
        abstract_end = first_marker_index(text, ["\nKeywords:"], abstract_start or 0)
        if abstract_start is not None and abstract_end is not None and abstract_start < abstract_end:
            ranges.append(trim_source_range(text, abstract_start, abstract_end))
        case_start = first_marker_index(text, ["\nA forty year old male patient", "A forty year old male patient"])
        discussion_start = first_marker_index(text, ["\nDISCUSSION"], case_start or 0)
        if case_start is not None and discussion_start is not None and case_start < discussion_start:
            ranges.append(trim_source_range(text, case_start, discussion_start))
        discussion_end = first_marker_index(text, ["It is not a must for every SPS patient"], discussion_start or 0)
        if discussion_start is not None and discussion_end is not None and discussion_start < discussion_end:
            ranges.append(trim_source_range(text, discussion_start, discussion_end))
        outcome_start = first_marker_index(text, ["Our patient produced a good response to steroids"])
        outcome_end = first_marker_index(text, ["Our report therefore", "\nREFERENCES"], outcome_start or 0)
        if outcome_start is not None and outcome_end is not None and outcome_start < outcome_end:
            ranges.append(trim_source_range(text, outcome_start, outcome_end))
        if ranges:
            return ranges

    if "Successfultreatmentofstiffman" in text and "A 43yearoldman developedlowback" in text:
        start = first_marker_index(text, ["Successfultreatmentofstiffman"])
        end = first_marker_index(text, ["\nROGER ABARKER", "ROGER ABARKER"], start or 0)
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Here,we report the case of a 69" in text and "Table 1 Synopsis of reported cases of the stiff-limb syndrome" in text:
        start = first_marker_index(text, ["Here,we report the case of a 69"])
        end = first_marker_index(
            text,
            [".Corresponding to the clinical", "\nLETTER TO THE EDITORS", "\nTable 1 Synopsis"],
            start or 0,
        )
        if start is not None and end is not None and start < end:
            return [trim_source_range(text, start, end)]

    if "Case Presentation\nA 41-year-old right-handed African-American woman" in text and "What Is the Differential\nDiagnosis of Muscle Stiffness?" in text:
        ranges: list[tuple[int, int]] = []
        case_start = first_marker_index(text, ["Case Presentation\nA 41-year-old"])
        differential_start = first_marker_index(text, ["\nWhat Is the Differential\nDiagnosis of Muscle Stiffness?"], case_start or 0)
        if case_start is not None and differential_start is not None and case_start < differential_start:
            ranges.append(trim_source_range(text, case_start, differential_start))
        diagnosis_start = first_marker_index(text, ["What Is the Diagnosis in the\nPresented Case?"])
        generic_sps_start = first_marker_index(text, ["\nWhat Is Stiff-person Syndrome?"], diagnosis_start or 0)
        if diagnosis_start is not None and generic_sps_start is not None and diagnosis_start < generic_sps_start:
            ranges.append(trim_source_range(text, diagnosis_start, generic_sps_start))
        course_start = first_marker_index(text, ["Clinical Course of the Presented\nCase"])
        summary_start = first_marker_index(text, ["\nSummary\n"], course_start or 0)
        if course_start is not None and summary_start is not None and course_start < summary_start:
            ranges.append(trim_source_range(text, course_start, summary_start))
        if ranges:
            return ranges

    if "A case ofprogressive encephalomyelitis with rigidity" in text and "A 50 year old woman first" in text:
        case_start = first_marker_index(text, ["\nCase report\nA 50 year old", "Case report\nA 50 year old"])
        acknowledgements_start = first_marker_index(
            text,
            ["\nSolilena\n\nand co-workers of", "Solilena\n\nand co-workers of", "\nWe are grateful", "We are grateful"],
            case_start or 0,
        )
        if case_start is not None and acknowledgements_start is not None and case_start < acknowledgements_start:
            return [trim_source_range(text, case_start, acknowledgements_start)]

    if "Case 27-2012: A 60-Year-Old Woman" in text and "Pr e sen tat ion  of  C a se" in text:
        case_start = first_marker_index(text, ["Pr e sen tat ion  of  C a se"])
        end = first_marker_index(
            text,
            ["\nPresented at the postgraduate course", "Presented at the postgraduate course", "\nNo potential conflict", "No potential conflict", "\nReferences"],
            case_start or 0,
        )
        if case_start is not None and end is not None and case_start < end:
            return [trim_source_range(text, case_start, end)]

    if "Pathological Findings in a Case of Stiff\nPerson Syndrome with Anti-GAD\nAntibodies" not in text:
        return []
    title_start = first_marker_index(
        text,
        ["Pathological Findings in a Case of Stiff\nPerson Syndrome with Anti-GAD\nAntibodies"],
    )
    if title_start is None:
        return []
    case_start = first_marker_index(text, ["A 69-year-old man"], title_start)
    footer_start = first_marker_index(text, ["\n------------------------------------------------------------\n*Correspondence to: Marios"], title_start)
    continuation_start = first_marker_index(text, ["vacuole into the vacuole itself"], footer_start or title_start)
    author_start = first_marker_index(text, ["\nJonathan Witherick, MRCP"], continuation_start or title_start)
    figure_start = first_marker_index(text, ["\nFIG. 1. a: Vacuolation"], author_start or title_start)

    ranges: list[tuple[int, int]] = []
    if case_start is not None and footer_start is not None and case_start < footer_start:
        ranges.append(trim_source_range(text, case_start, footer_start))
    if continuation_start is not None and author_start is not None and continuation_start < author_start:
        ranges.append(trim_source_range(text, continuation_start, author_start))
    if figure_start is not None:
        figure_end = first_marker_index(text, ["\nLETTERS: NEW OBSERVATIONS"], figure_start + 1)
        if figure_end is not None and figure_start < figure_end:
            ranges.append(trim_source_range(text, figure_start, figure_end))
    return ranges


def single_patient_clinical_ranges(
    prepared_source: PreparedSource,
    *,
    include_age_anchor_fallback: bool = False,
) -> tuple[list[tuple[int, int]], bool]:
    text = prepared_source.source_text
    source_specific_ranges = source_specific_case_report_ranges(text)
    case_heading_range = case_heading_clinical_range(text)
    patient_history_range = patient_history_clinical_range(text)
    if source_specific_ranges:
        ranges = source_specific_ranges
    elif patient_history_range is not None:
        ranges = [patient_history_range]
    else:
        ranges = [
            item
            for item in [
                summary_clinical_range(text),
                case_report_clinical_range(text),
                case_heading_range,
            ]
            if item is not None
        ]
        if not ranges and case_report_marker_count(text) == 0:
            title_range = spsd_title_clinical_range(text)
            if title_range is not None:
                ranges = [title_range]
    if (
        include_age_anchor_fallback
        and not source_specific_ranges
        and len(ranges) == 1
        and AGE_ANCHOR_RE.search(text[ranges[0][0] : ranges[0][1]]) is None
    ):
        age_range = age_anchor_clinical_range(text)
        if age_range is not None:
            ranges = [age_range]
    selected_ranges_text = "\n".join(text[start:end] for start, end in ranges)
    if (
        ranges
        and not source_specific_ranges
        and len(PATIENT_HISTORY_HEADING_RE.findall(selected_ranges_text)) < 2
        and (case_heading_range is None or len(PATIENT_HISTORY_HEADING_RE.findall(text)) < 2)
        and re.search(r"\bLITERATURE REVIEW\b", text[:6000], flags=re.IGNORECASE) is None
    ):
        patient_discussion_range = patient_discussion_clinical_range(
            text,
            start=max(end for _, end in ranges),
        )
        if patient_discussion_range is not None:
            ranges.append(patient_discussion_range)
    if include_age_anchor_fallback and not ranges:
        age_range = age_anchor_clinical_range(text)
        if age_range is not None:
            ranges.append(age_range)
    if not source_specific_ranges:
        results_range = single_case_results_range(
            text,
            start=max((end for _, end in ranges), default=0),
        )
        if results_range is not None:
            if not ranges or results_range[0] >= max(end for _, end in ranges):
                ranges.append(results_range)
        continuation_range = source_specific_case_continuation_range(
            text,
            start=0,
        )
        if continuation_range is not None:
            ranges.append(continuation_range)
        table_range = single_case_late_table_range(
            text,
            start=max((end for _, end in ranges), default=0),
        )
        if table_range is not None:
            ranges.append(table_range)
    if not ranges:
        return [(0, len(text))], False
    return merge_source_ranges(ranges), True


def single_patient_clinical_range(prepared_source: PreparedSource) -> tuple[int, int, bool]:
    ranges, confident = single_patient_clinical_ranges(prepared_source)
    return ranges[0][0], ranges[-1][1], confident


def subtract_source_ranges(
    text: str,
    ranges: list[tuple[int, int]],
    exclusions: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    kept = ranges
    for exclusion_start, exclusion_end in sorted(exclusions):
        next_kept: list[tuple[int, int]] = []
        for start, end in kept:
            if exclusion_end <= start or exclusion_start >= end:
                next_kept.append((start, end))
                continue
            if start < exclusion_start:
                next_kept.append(trim_source_range(text, start, max(start, exclusion_start)))
            if exclusion_end < end:
                next_kept.append(trim_source_range(text, min(end, exclusion_end), end))
        kept = [(start, end) for start, end in next_kept if start < end]
    return kept


def single_case_boilerplate_exclusion_ranges(text: str) -> list[tuple[int, int]]:
    exclusions: list[tuple[int, int]] = []
    for match in re.finditer(
        r"\nEditor:\s*N/A\..*?"
        r"http://dx\.doi\.org/10\.1097/MD\.[^\n]*\n"
        r"\s*Clinical Case Report Medicine\s*.*?\n\s*OPEN\s*\n?\s*\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nEditor:\s*[^\n]+\n.*?"
        r"DOI:\s*10\.1097/MD\.[^\n]*\n"
        r"\s*Medicine\s*.*?CLINICAL CASE REPORT\s*"
        r"Medicine /C15 Volume 94, Number [^\n]+\|\s*1\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,120}Medicine\s*/C15 Volume 94, Number [^\n]*\n"
        r"(?:\d+\s*\|\s*)?www\.md-journal\.com Copyright\s+#\s+2015 "
        r"Wolters Kluwer Health, Inc\. All rights reserved\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMedicine\s*/C15 Volume 94, Number [^\n]*\n"
        r"Copyright\s+#\s+2015 Wolters Kluwer Health, Inc\. All rights reserved\. "
        r"www\.md-journal\.com\s*\|\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nhttps?://doi\.org/10\.1016/[^\n]*\n"
        r"Received .*?Elsevier (?:Inc\.|B\.V\.) All rights reserved\.\s*(?:\nT\s*)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAccepted\s+May\s+\d{4}\s*"
        r"Correspondence to:.*?International Journal of Obstetric Anesthesia\s*\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nwww\.aana\.com/aanajournalonline\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*AAN\s*A Journal\s*[^\n]*June 2016[^\n]*Vol\.\s*84,\s*No\.\s*3\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nA\s*A\s*N\s*A\s+J\s*o\s*u\s*r\s*n\s*a\s*l\s+[^\n]*June 2016[^\n]*Vol\.\s*84,\s*No\.\s*3\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*\nhttp://www\.ismni\.org\s*\n"
        r"A\. Nguyen et al\.: Chronic intestinal pseudo-obstruction[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nn\s*e\s*u\s*r\s*o\s*l\s*o\s*g\s*i\s*a\s*i\s*n\s*e\s*u\s*r\s*o\s*c\s*h\s*i\s*r\s*u\s*r\s*g\s*i\s*a\s*p\s*o\s*l\s*s\s*k\s*a\s*[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nT\s*\n(?=renal failure\b)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJones LA, Baber W, Wardle M, et al\. Complications of Treatment in Stiff Person Syndrome\s*"
        r"Columbia University LibrariesTremor and Other Hyperkinetic Movements\s*"
        r"http://www\.tremorjournal\.org\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nproL[^\n]*\|\s*30\.6\.2023\s*"
        r"(?:\n\d+\s*)?"
        r"(?:\nSTIFF-PERSON SYNDROME ASSOCIATED WITH MYOTONIC DYSTROPHY TYPE 2[^\n]*)?"
        r"(?:\nCesk Slov Ne urol N 2014;[^\n]*)?"
        r"(?:\n\d+\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:\d+\s*\n)?"
        r"STIFF-PERSON SYNDROME ASSOCIATED WITH MYOTONIC DYSTROPHY TYPE 2[^\n]*\n"
        r"Cesk Slov Ne urol N 2014;[^\n]*\n"
        r"(?:\d+\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nS\d+\s*Abstracts\s*/\s*PM R 8 \(2016\) S151-S332\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nROMANIAN JOURNAL OF NEUROLOGY[^\n]*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nKahraman T et al\.\s*"
        r"(?:\nMiddle East J Rehabil Health\. 2016;3\(1\):e34793\s*)?"
        r"(?:\n\d+\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMiddle East J Rehabil Health\. 2016;3\(1\):e34793\s*\n\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nInformed consent was obtained from the patient for the\s+"
        r"description, data utilization, and publication of this report\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\* Correspondence and reprints\.\s*\nE-mail address:[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s+Gharedaghi MH, et al\. BMJ Case Rep 2018\."
        r"\s+doi:10\.1136/bcr-2017-223261\s*\n"
        r"reminder of important clinical lesson\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*by copyright\..*?Downloaded from\s*"
        r"\d+\s+Munipalli B, Shah JS\. BMJ Case Rep[^\n]*\nCase report\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*\d+\s*copyright\..*?Downloaded from\s*"
        r"Grech N, et al\. Pract Neurol[^\n]*\nNeurological rarities\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*Page\s+\d+\s+of\s+\d+\s*Yao et al\. BMC Neurology\s+\(2022\) 22:42\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*Neuropediatrics Vol\. 53 No\. 2/2022.*?Copyrighted material\.\s*"
        r"(?:Article published online:\s*\d{4}-\d{2}-\d{2}\s*)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*(?:Neuropediatrics Vol\.[^\n]*\s*)?"
        r"Downloaded by: UZH Hauptbibliothek / Zentralbibliothek ZÃ¼rich\."
        r"\s*Copyrighted material\.\s*"
        r"(?:Article published online:\s*\d{4}-\d{2}-\d{2}\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*\n\s*Christian Medical College Hospital, Vellore-632 004, Tamil Nadu, India\s*"
        r"Correspondence to: Dr T P Joseph, Department of Neurological Sciences\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJOURNAL\s*\n\s*OF\s*\n\s*THE ROYAL\s*\n\s*SOCIETY OF\s*\n\s*MEDICINE\s*\n\s*Volume\s*\n\s*94\s*\n\s*June\s*\n\s*2001\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJournal of the Neurological Sciences 291 \(2010\) 118\s*[^0-9A-Za-z]{1,8}\s*120\s*"
        r".*?journal homepage:\s*www\s*\.elsevier\.com/locate/jns\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}C\. Schmidt et al\. / Journal of the Neurological Sciences 291 \(2010\) 118\s*[^0-9A-Za-z]{1,8}\s*120\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDepartment of Medicine \(Neurology and Rheumatology\) , Shinshu University School of Medicine, Matsumoto\s*"
        r"Received for publication August 26, 2009; A ccepted for publication October 5, 2009\s*"
        r"Correspondence to Dr\. Masayuki Matsuda, matsuma@shinshu-u\.ac\.jp\s*"
        r"Inter Med 49: 237-241, 2010 DOI: 10\.2169 /internalmedicine\.49\.2821\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nInter Med 49: 237-241, 2010 DOI: 10\.2169 /internalmedicine\.49\.2821\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+after obtaining informed consent\. The Local\s+"
        r"Ethical Committee approved rituximab for use in this pa-\s*tient\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDepartment of Neurology, Juntendo University Urayasu Hospital, Japan,.*?"
        r"Intern Med 54: 219-221, 2015 DOI: 10\.\s*2169/internalmedicine\.54\.3760\s*\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nIntern Med 54: 219-221, 2015 DOI: 10\.\s*2169/internalmedicine\.54\.3760\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe Interesting Case 589\s*"
        r"Dankerl P et al\. Stiff Young Woman .*?"
        r"Downloaded by: Universite Laval\. Copyrighted material\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCASE REPORT\s*"
        r"The Journal of the American Osteopathic Association\s+June 2015\s+\|\s+Vol 115\s+\|\s+No\. 6\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCorrespondence to: Ivanka Marinovi.*?"
        r"imarinovic27@net\.hr; aljinovich@inet\.hr\s*"
        r"Extremely rare coincidence of non-radiographic axial\s*"
        r"spondyloarthropathy HLA-B27 positive and Stiff Person\s*"
        r"Syndrome.*?DOI 10\.\s*3109/14397595\.\s*2013\.\s*857837\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nOBSERVATION\s*\nFrom the Department\b.*?"
        r"\(REPRINTED\)\s+ARCH NEUROL /.*?"
        r"Downloaded From: https://jamanetwork\.com/.*?(?:\n|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\(REPRINTED\)\s+ARCH NEUROL /.*?"
        r"Downloaded From: https://jamanetwork\.com/.*?(?:\n|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMultiple neurological syndromes during Hodgkin lymphoma remission\n.*?"
        r"(?=\nPARANEOPLASTIC SYNDROME AND HODGKIN\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPARANEOPLASTIC SYNDROME AND HODGKIN\s+\d+\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\* Corresponding author\..*?PII S0168-8227\(98\)00072-2\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nI\.B\. Hirsch et al \. : Diabetes Research and Clinical Practice 41 \(1998\) 197[^\n]*\n",
        text,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCopyright r \d{4} by Lippincott Williams & Wilkins.*?"
        r"Downloaded from http://journals\.lww\.com/cogbehavneurol.*?(?:\n\s*\n|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCopyright r \d{4} by Lippincott Williams & Wilkins.*?"
        r"Cog Behav Neurol /C15Volume [^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCog Behav Neurol /C15Volume [^\n]*\n"
        r"r \d{4} Lippincott Williams & Wilkins \d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Received\s+27\s+Jun\s+1989\s+--\s+Accepted\s+30\s+October\s+1989\s+177\s*"
        r"\nThe Italian Journal of Neurological Sciences\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?Copyright[^\n]*John Wiley & Sons, Ltd\. Diabetes Metab Res Rev 2010;[^\n]*\n"
        r"DOI: 10\.1002/dmrr\s*"
        r"(?:\n[^\n]*(?:Stiff-Person Syndrome|A\.\s*H[^\n]*et al\.)\s+\d+\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nD\. Velardo \(&\).*?/C1A\..*?DOI 10\.1007/s10072-014-2058-0\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\* Dr\. Aziz Sonawalla,.*?Accepted: March 1, 1995\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAziz Sonawalla\s*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s*[^\n]*\n\s*Piotr F\. Czempik et al\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,12}\n\* Corresponding author: Piotr F\. Czempik,.*?"
        r"Keywords: glutamic acid decarboxylase, procedure efficacy, procedure safety, "
        r"stiff person syndrome, therapeutic plasma exchange\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\* Sara Mariotto\s*"
        r"sara\.mariotto@univr\.it.*?"
        r"Neurological Sciences \(2021\) 42:4289[^0-9]+4291\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nÂ© 2022 The Author\(s\)\..*?DOI:\s*10\.1159/000523988\s*\n\s*238\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,8}2022 The Author\(s\)\. Published by S\. Karger AG, Basel\s*"
        r"DOI:?\s*10\.1159/000523988\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s*\nCase Rep Neurol 2022;14:237[^\n]*\n"
        r"Nguyen et al\.: Stiff Person Syndrome: A Case Report from Vietnam\n"
        r"www\.karger\.com/crn\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nD\.A\. Nie et al\.\nJournal of Neuroimmunology 367 \(2022\) 577865\n\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFig\. 1\. Flow chart of literature searching and review\.\s*"
        r"D\.A\. Nie et al\.\s*"
        r"Journal of Neuroimmunology 367 \(2022\) 577865\s*"
        r"\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nBrain Sci\. 2023, 13, 369\. https://doi\.org/10\.3390/brainsci13020369 "
        r"https://www\.mdpi\.com/journal/brainsci\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nBrain Sci\. 2023, 13, (?:369|x FOR PEER REVIEW) \d+ of \d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"(?:\n|^)Brain Sci\. 2023, 13, x FOR PEER REVIEW \d+ of \d+[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThis is an open access article under the CC BY-NC license\. www\.medicaljournals\.se/jrm-cc\s*"
        r"Foundation of Rehabilitation Information\s*"
        r"doi:\s*10\.\s*2340/20030711-1000052\s*"
        r"p\.\s*2\s*of\s*5\s*"
        r"JRM[^\n]{0,8}CC\s*"
        r"B\. Zhang et al\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Journal of Neuro-Ophthalmology 2023;43:273.*?"
        r"Drs\. Hac, Murphy, and Gold:\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Introduction: Stiff-person syndrome \(SPS\) is a rare autoimmune neurological disorder\..*?"
        r"Sasaki A, et al\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPage\s+\d+\s+of\s+\d+\s*Ali et al\. Journal of Medical Case Reports\s+\(2023\) 17:330\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+(?:Tel:[^\n]*\n)?Email:\s*jiangyun@bjhmoh\.cn\s*"
        r"Cite this article: Jiang Y.*?"
        r"https://doi\.org/10\.1017/cjn\.2022\.51 Published online by Cambridge University Press\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Le Journal Canadien Des Sciences Neurologiques\s+\d+\s*"
        r"https://doi\.org/10\.1017/cjn\.2022\.51 Published online by Cambridge University Press\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\ncopyright\.\s*on .*?Downloaded from\s*"
        r"\n\s*\d+\s+Yohannan B, et al\. BMJ Case Rep 2022;15:e250639\. "
        r"doi:10\.1136/bcr-2022-250639\s*"
        r"Case report\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n123\s*\n1420 N\. Elsherbini et al\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTable 1 continued\s*Report Age.*?"
        r"123\s*\n1422 N\. Elsherbini et al\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAdditional Supporting Information may be found in the online\n"
        r"version of this article\..*?"
        r"Downloaded from https://movementdisorders\.onlinelibrary\.wiley\.com/.*?"
        r"Creative Commons License\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,80}Teive, MD, PhD\*.*?(?=\nReferences\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"In 1956, Moersch and Woltman.*?autoanti-\nbodies\.\s*4,5\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAddress correspondence to:.*?"
        r"K\. Yamamoto et al\.: Stiff-person syndrome and epidural anesthesia\s+\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAbstract\nWe report the successful management of anesthesia.*?"
        r"K\. Yamamoto et al\.: Stiff-person syndrome and epidural anesthesia\s+\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFrom the ENT Department and the \*Department of Neurology, San Raffaele Hospital.*?"
        r"Published online by Cambridge University Press\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nReceived: \d{1,2} \w+ \d{4}.*?GABA-A receptor\s*\n?\d{3,4}\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPublished online .*?Movement Disorders, Vol\.[^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if "vacuole into the vacuole itself" in match.group(0):
            continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:POSTER SESSION[^\n]*\n)?"
        r"(?:Movement Disorders, Vol\.[^\n]*\n)"
        r"(?:S\d+\s*\n)?"
        r"\s*15318257, .*?Creative Commons License\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n#9\s*"
        r"Please address correspondence to Ranka Baraba.*?"
        r"Encephalomyelitis With Rigidity 73\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n0303-8467/\$.*?Clinical Neurology and Neurosurgery\s+[0-9 ]+\(\d{4}\)[^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n0022-510X[^\n]*All rights reserved\.\s*\n"
        r"[^\n]*PII:\s*S\s*0022-510X\s*01\s*00602-5\s*\n\s*"
        r"[^\n]*H\. Hagiwara et al\. r Journal of the Neurological Sciences[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\(\)H\. Hagiwara et al\. r Journal of the Neurological Sciences 193 2001 59[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCase reports in the neurology litera-\s*ture mention that patients with Stiff.*?"
        r"(?=\nIn our case, the patient remained\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nN\. Haslam\s+K\. Price\s+Newcastle General Hospital,.*?\bE-mail:\s*\S+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nM\. Obara\s+S\. Sawamura\s+M\. Chinzei\s+K\. Komatsu\s+K\. Hanaoka\s+"
        r"Tokyo University School of Medicine,.*?\bE-mail:\s*\S+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPiccolo and\b.*?(?=\nPresent\s+40\s+F\s+SPS\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bIn\s+comparing the Nicholas.*?and is accompanied by MG\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bq\s+2001\s+Elsevier Science B\.V\. All rights reserved\.\s*(?:\n[^\n]{0,10})?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?[^\n]{0,30}Elsevier B\.V\s*\.?\s*All rights reserved\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n/C2112012 The Japanese Society of\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n0387-7604\s*/\$.*?"
        r"(?:www\.elsevie\s*r\.com/locate/\s*braindev\s*)?"
        r"Brain\s*&\s*Developme\s*nt\s+35\s+\(2013\)\s+\d+[^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s+[A-Z]\.[^\n]{0,100}/\s*Brain\s*&\s*Developme\s*nt\s+35\s+\(2013\)\s+\d+[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[A-Z]\.[^\n]{0,100}/\s*Brain\s*&\s*Development\s+35\s+\(2013\)\s+\d+[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,6}Corresponding author[^\n]*\n(?:[^\n]*\n){0,3}?E-mail address:[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*Key Words\s+(?=.{0,500}\bAutoimmune\b)(?=.{0,500}\bGlutamate decarboxylase\b).*?"
        r"Stiff-Person Syndrome and Pregnancy Gynecol Obstet Invest 2009;67:134.?136\s*135\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDownloaded from http://karger\.com/goi/[^\n]*\n\s*"
        r"Cerimagic\s+/Bilic\s+Gynecol Obstet Invest 2009;67:134.?136\s*136\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*References\s+\d+\s+Moersch FP.*?"
        r"(?:Downloaded from http://karger\.com/goi/[^\n]+(?:\n|$)|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Weatherby et al\..*?suffered a mild postpartum [^.!?]*[.!?]\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"By analogy with postpartum ad-\nministration of intravenous immunoglobulins.*?"
        r"prevent SPS exacerbation\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Increasing\nevidence from literature indicates.*?(?=\nPatients with SPS\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Only one case describing a patient with severe\ninsulin resistanc.*?"
        r"insulin resistance in such patients\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Prompt response\nto diazepam has been used.*?(?=In our patient, hiccup)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Bulbar muscles can be involved in stiff person syn-\ndrome\..*?"
        r"anxiety and fear \[9\]\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"On the other hand, many case studies of patients\nwith SPS.*?over 20 patients \[5\]\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"There are several diseases that are characterized by continuous muscular activity\..*?"
        r"carbamazepine and phenytoin\. 24\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Some\nauthors divide this syndrome into 2 types:.*?"
        r"autoimmune\ndiseases\. 13\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Use of surface electrodes causes no pain.*?"
        r"pyramidal findings, and brainstem symptoms\. 20\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCompeting interests\b.*?(?=\nDIABETIC\s+\n\s*Medicine Letters|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if (
            "Our patient is the first reported" in text
            and "MRI striatal abnormalities" in text
            and "first published as 10.1136/jnnp.2006.099705" in match.group(0)
        ):
            continue
        if "Our patient is the first reported" in text and "MRI striatal abnormalities" in text:
            continuation_start = first_marker_index(
                text,
                ["\nthe more symptomatic left side)", "the more symptomatic left side)"],
                match.start(),
            )
            if continuation_start is not None and match.start() < continuation_start < match.end():
                exclusions.append((match.start(), continuation_start))
                continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:Stiff Limb Syndrome\s+\d+|Misra et al\.\d+)\s*\n"
        r"Downloaded from https://academic\.oup\.com/painmedicine/[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nHow to cite this article:.*?\| Introduction\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:\d+\s*){0,6}Open Access Case\s*"
        r"Report\s*"
        r"DOI:\s*10\.7759/cureus\.[^\n]+"
        r"\s*How to cite this article:?.*?"
        r"DOI\s+10\.7759/cureus\.[^\s\n]+(?:\s*\n)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{4}\s+[^\n]{1,120}?\bet al\.\s+Cureus\s+\d+\(\d+\):\s+e\d+\.\s+"
        r"DOI\s+10\.7759/cureus\.\d+\s*"
        r"(?:\n\s*\d+\s*)?\n\s*of\s*\n\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nSmith and Storey:\s*Stiff-Person Syndrome\s*\n?\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMent Health Clin \[Internet\]\. 2020;10\(3\):95-9\. DOI: 10\.9740/mhc\.2020\.05\.095\s+\d+\s*"
        r"\nDownloaded from http://meridian\.allenpress\.com/mhc/[^\n]+(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTable 1: Diagnostic criteria of sti\S*-person syndrome.*?"
        r"\n\s*2\s+Case Reports in Neurological Medicine\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r",?\s*as outlined by Baizabal-Carvallo et al\.,\s*shown in Table 1 \[7\]\.",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Both of these are frequently\s*recommended as options for initial treatment,\s*"
        r"as outlined by\s*Dalakas et al\., shown in Table 2 \[13\]\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r",?\s*as stated in previous\s*reviews\[1,2\]\.",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"In summary, SPS is a rare and complicated disorder\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:\d+\s*d\s*)?STIFF-PERSON SYNDROME\s*d\s*"
        r"AWnYQp/Il QrHD3i3D0Od Ryi7TvSFl4Cf3VC4/OAVpDDa8KKGKV0Ymy\+78= on 05/29/2023\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFrom the Cattedra di Patologia Speciale Medica, Divisione di.*?"
        r"via del Pozzo 71, 41100 Modena, Italy\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nKEY WORDS:.*?(?=\nProgressive encephalomyelitis with rigidity)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCorrespondence to:\s*\n?Z\. Nur Baykara.*?(?=\nReferences\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFrom the Department of Neurology \(Drs\. Rosin and Meinck\).*?"
        r"94 Copyright 0 1998 by the American Academy of Neurology\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJanuary 1998 NEUROLOGY 50 97\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe New England Journal of Medicine\s*"
        r"\n\s*Downloaded from nejm\.org .*?All rights reserved\.\s*"
        r"\n\s*T h e\s+n e w\s+e ng l a n d\s+j o u r n a l\s+o f\s+m e d ic i n e\s*"
        r"\n\s*n engl j med [^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe Stiff Person Syndrome\s*"
        r"\n\s*The clinical presentation of the stiff person syn.*?"
        r"(?=\nTable 1\. Laboratory Data\.)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*Key Words\s+(?=.{0,500}\bSpinal cord stimulation\b)(?=.{0,500}\bStiff limb syndrome\b).*?"
        r"Downloaded from http://karger\.com/sfn/[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:Ughratdar/Sivakumar/Basu\s*\n\s*)?"
        r"Stereotact Funct Neurosurg 2010;88:183.{0,5}186\s+\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nSpinal Cord Stimulation for Stiff Limb\s*\nSyndrome\s*\n"
        r"Stereotact Funct Neurosurg 2010;88:183.{0,5}186\s+\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDownloaded from http://karger\.com/sfn/[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*Discussion\s+\n\s*SLS is a rare chronic.*?"
        r"(?=\n\s*I\s+n\s+o\s+u\s+r\s+r\s+e\s+p\s+o\s+r\s+t\s+a\s+n\s+u\s+m\s+b\s+e\s+r)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nControl systems\nInhibitory.*?(?=\n\s*(?:â€“|-)\s*The effect was rapid)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nControl systems\nInhibitory.*?\[16\]\s*\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*Naturally, the observations noted above.*?(?=\n\s*Conclusion\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*References\s+\d+\s+Barker RA.*?"
        r"(?:Downloaded from http://karger\.com/sfn/[^\n]+(?:\n|$)|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nINTRODUCTION\s+The wide varieties of thymic diseases.*?(?=\nCASE PRESENTATION\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:;[^\n]*Tennessee Medicine\s+)?TABLE 1\. Literature Review of All Reported Cases.*?"
        r"\+ www\.tnmed\.org \* MAY 2010\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTABLE 2\. Proposed Diagnostic Criteria\s+for SPS\.\*.*?"
        r"(?=In our patient, sur-\ngical therapy was not an option because)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nGLOSSARY:.*?\+ www\.tnmed\.org \* MAY 2010\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCURRENT STATE OF KNOWLEDGE AND\s+FUTURE RESEARCH NEEDS.*?"
        r"(?=In our\s+patient the early recognition)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nIn particular, the following pivotal is-\s*sues may need to be addressed.*\Z",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe prognosis for patients with SPS is.*?(?=\s*In our\s+patient the early recognition)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFrom the Division of Allergy/Immunology/Rheumatology, Loyola University.*?"
        r"JCR: Journal of Clinical Rheumatology[^\n]*(?:\n|$)\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMiguel Angel Arrabal-Polo\s+MD, Francisco Palao-Y ago MD\s+"
        r"and Armando Zuluaga-Gomez MD\s+Urology Department.*?arrabalp@ono\.com\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nInternational Journal of Urology .*?The Japanese Urological Association\s+\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAccepted \d{1,2} \w+ \d{4}\s+1 South Carolina Department of Mental Health.*?"
        r"University of South Carolina School of Medicine, Columbia,\s+South Carolina\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nA\. Piotrowicz \(.*?DOI 10\.1007/s00415-011-6078-x\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nStiff-person syndrome \(SPS\) is a neuroimmunological,.*?"
        r"(?=\nThus, as described in our patient,)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCon(?:\ufb02|ï¬‚|fl)ict of interest None\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPhysical Therapist Management of Stiff Person Syndrome\s*\n"
        r"[^\n]*Physical Therapy[^\n]*\n"
        r"Downloaded from https://academic\.oup\.com/ptj/[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe author thanks .*?DOI: 10\.2522/ptj\.20100303\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nVOL\. 118, NO\. 2, PART 2, AUGUST 2011 Goldkamp et al Stiff Person Syndrome 455\s*"
        r"Downloaded from http://journals\.lww\.com/greenjournal[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s+Goldkamp et al Stiff Person Syndrome OBSTETRICS & GYNECOLOGY\s*"
        r"Downloaded from http://journals\.lww\.com/greenjournal[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTwo case reports of three children born to moth(?:-?\s*ers|ers).*?"
        r"(?=Because of\s+concern for our patient)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAlthough our patient had a cesarean delivery, it\nwas secondary to her disease\. Weatherby et al.*?"
        r"(?=Although\nthe antibodies have been reported)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nBoth our patient and the patient with stiff limb\nsyndrome.*?(?=In conclu)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nEditorial, page 414.*?Copyright .*?AAN Enterprises, Inc\. \d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*\nhttps://doi\.org/10\. 1017/S0317167100018011 Published online by Cambridge University Press\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTO THE EDITOR\s+\nA Case of Phenytoin-Induced Encephalopathy.*\Z",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*\n\nTHE CANADIAN JOURNAL OF NEUROLOGICAL SCIENCES\s*\n\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJulie Lemieux, Louise Provencher,?.*?Quebec City, QC, Canada\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nGlutamic acid decarboxylase antibody-positive paraneoplastic stiff limb\.\.\. "
        r"https://www\.neurologyindia\.com/article\.asp[^\n]*\n\d+ of \d+ [^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*(?:Â»|»)\s*Discussion\s+Three distinct subtypes.*?(?=\n\s*(?:Â»|»)\s*References\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*(?:Â»|»)\s*References\s+\n\s*\d+\.\s+.*?"
        r"(?=\n(?:CURRENT STATE OF KNOWLEDGE|DisCussion)\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDisCussion\s+SPS was first described.*?(?=\nRefeRenCes\b|\Z)",
        text,
        flags=re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nRefeRenCes\b.*\Z",
        text,
        flags=re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\ndIscuss Ion\b.*\Z",
        text,
        flags=re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d+\s*o\s*f\s*3BMJ Case Reports[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[A-Z][A-Za-z-]+(?:\s+[A-Z]\.?)?,\s+et al\s*\.?\s+"
        r"BMJ Case Rep \d{4}\. doi:10\.1136/[^\n]*\s+\d+\n[^\n]{0,120}\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[A-Z][A-Za-z]+ et al\. World Journal of Surgical Oncology \d{4}, \d+:\d+ Page \d+ of \d+\n"
        r"http://www\.wjso\.com/content/[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nConsent\s+Written informed consent was obtained.*?"
        r"(?=\n(?:CASE REPORT|CASE PRESENTATION|CASE DESCRIPTION|CASE HISTORY|"
        r"REPORT OF A CASE|PATIENT DESCRIPTION|DISCUSSION|INTRODUCTION)\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAn additional movie file shows this in more detail \(see\s+Additional file 1\)\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s+SO\S*: LADA type diabetes, celiac diasease, cerebellar ataxia and stiff person syndrome\n"
        r"ABBREVIATIONS\b.*?"
        r"Az alÃ¡bbi dokumentumot.*?esik\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nmanhalter_UJ[^\n]*Page \d+\n"
        r"Az alÃ¡bbi dokumentumot.*?esik\.\s*"
        r"(?:\n(?:Ideggyogy Sz[^\n]*|\d{3}\s+Manhalter[^\n]*))?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s+SO\S*: LADA type diabetes, celiac diasease, cerebellar ataxia and stiff person syndrome\n"
        r"ABBREVIATIONS\b.*?"
        r"Az al.{1,12}bbi dokumentumot.*?esik\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nmanhalter_UJ[^\n]*Page \d+\n"
        r"Az al.{1,12}bbi dokumentumot.*?esik\.\s*"
        r"(?:\n(?:Ideggyogy Sz[^\n]*|\d{3}\s+Manhalter[^\n]*))?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJOURNAL OF THE NATIONAL MEDICAL ASSOCIATION VOL \d+,\s*NO \d+,\s*[A-Z]+ \d{4}\s+\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nOpen Access\s*\nBMC Research Notes\s*\n\*Correspondence:.*?"
        r"Page \d+ of \d+Chang et al\. BMC Res Notes[^\n]*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPM R 10 \(2018\) 1426-1430 www\.pmrjournal\.org\s*"
        r"1934-1482/\$.*?https://doi\.org/10\.1016/j\.pmrj\.2018\.04\.007\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{4}S\.-W\. No et al\. / PM R 10 \(2018\) 1426-1430\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\s*19341563, 2018, 12, Downloaded from https://onlinelibrary\.wiley\.com/doi/10\.1016/j\.pmrj\.2018\.04\.007.*?"
        r"Creative Commons License\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n[^\n]{0,8}\nDepartment of [^\n]+Hakodate City Hospital, Japan and.*?"
        r"Intern Med 57: 3313-3316, 2018 DOI: 10\.2169/internalmedicine\.1043-18\s*\n3314\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nIntern Med 57: \d+-\d+, 2018 DOI: 10\.2169/internalmedicine\.[^\n]*\n\d{4}\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s+International Journal of Rehabilitation Research 2018, Vol 41 No 4\n"
        r"Copyright r 2018 Wolters Kluwer Health, Inc\. All rights reserved\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDegeneffe et al\. BMC Neurology\s+\(2018\) 18:173 Page \d+ of 6\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nLearning points.*\Z",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:The Neurologist .*?July 2009|Jim.*Caballero|www\.theneurologist\.org\s*\|\s*\d+|"
        r"\d+\s*\|\s*www\.theneurologist\.org|[^\n]{0,20}2009 Lippincott Williams & Wilkins)[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJim[^\n]*Caballero The Neurologist[^\n]*\n"
        r"\d+\s*\|\s*www\.theneurologist\.org[^\n]*(?:\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAbbreviations: BMT, bone marrow transplant;.*?"
        r"MUSCLE & NERVE December 2008\s+\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nSuccessful Intrathecal Baclofen Therapy for Seronegative.*?"
        r"Acta Neurologica Taiwanica V ol 17 No 3 September 2008\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s*\nActa Neurologica Taiwanica V ol 17 No 3 September 2008\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(r"\n\d{4}\s+S\.-Y\. CHIA ET AL\.\s*", text):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(r"\n1364\s*(?=\n|$)", text):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bKEYWORDS\b(?=.{0,500}\bCME\b).*?www\.nature\.com/clinicalpractice/neuro\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bNature\s+Publishing Group.*?www\.nature\.com/clinicalpractice/neuro\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\b0952-8180/\$.*?Journal of Clinical Anesthesia "
        r"\(\d{4}\)\s+\d+,\s+\d+\s*(?:[^\dA-Za-z]\s*)+\d+\s+",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bAccepted\s+\d{1,2}\s+\w+\s+\d{4}\..*?e-mail:\s*\S+\s+\d+\s+",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAuthors.{0,8}affiliations:.*?Accepted for publication:\s*\d{1,2}\s+\w+\s+\d{4}\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\b[A-Z]\.\s+[A-Za-z]+ et al\.\s+\d+\s+(?=DISCUSSION\b)",
        text,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bTABLE\s+\d+\.?\s+Positive antiamphiphysin antibodies\b.*?"
        r"\d{3,4}\s+CLINICAL/SCIENTIFIC NOTES\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nRegional Anesthesia and Pain Medicine\s*&\s*Volume\s+38.*?"
        r"Downloaded from\s*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe literature reports only 5 cases of GAD.*?(?=\s*Our\s+patient completed\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Clearly, further re-\s*search needs.*?long-\s*term pump therapy\.?\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTable\s+2\s+Anesthesia Management in Patients with SPS\b.*?(?=\nIn the case presented\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nIn recent years, patients with other co-morbidities.*?"
        r"(?=\nIn the case presented, the patient presented\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nIn summary, MAC with IV anesthetics.*?M\.E\.J\. ANESTH \d+ \(\d+\), \d{4}\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nM\.E\.J\. ANESTH \d+ \(\d+\), \d{4}\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bhaematologica online \d{4}.*?(?=\bReferences\b|\nReferences\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bDownloaded from http://journals\.lww\.com/cmj\b.*?"
        r"(?:Chin Med J|Chinese Medical Journal)\s+\d{4};\s*\d+\([^)]*\):\d+-\d+\s+\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bNeurol Sci \(\d{4}\).*?Department of Psychiatry.*?Greece\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bAbstract\s+The\s+[\"“]Stiff person syndrome[\"”].*?"
        r"Parole chiavi:.*?sindrome dell.?uomo rigido\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFunding:\s*None\.\s*\n"
        r"Con[^\n]{0,20}ict of interest:\s*None\.\s*\n"
        r"Brief Communication\s*\n.*?Internal Medicine Journal [^\n]*\s+\d{3}(?:\n|$)\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nBrief Communication\s*\n.*?Internal Medicine Journal [^\n]*\s*\d{3}(?:\n|$)\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThe two main goals of treatment are to enhance\s+"
        r"GABA neurotransmission.*?(?=However, the combination of non-Hodgkin lymphoma)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nDiscussion\s+The etiology of SMS and PEMWRS is unknown.*?(?=\nOur patient)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nn engl j med\s+\d+;\s*\d+\s*\n\s*"
        r"nejm\.org\s*\n\s*[a-z]+\s+\d{1,2},\s+\d{4}\s*\n\s*"
        r"From the Departments\b.*?All rights reserved\.\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:\d{3,4}\s*\n\s*)?"
        r"(?:n engl j med\s+\d+;\s*\d+\s*\n\s*)?"
        r"nejm\.org\s*\n\s*[a-z]+\s+\d{1,2},\s+\d{4}\s*"
        r"(?:\n\s*\d{3,4}\s*)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:\d{3,4}\s*\n\s*)?n engl j med\s+\d+;\s*\d+\s*(?=\n)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s*From the First Department of Medicine, Hamamatsu University School of Medicine, Hamamatsu\s*"
        r"Received for publication.*?"
        r"Internal\s+Medicine Vol\. 40, No\. 9 \(September 2001\)\s*\n\s*"
        r"Cerebellar Ataxia and Stiff-person\s*\n\s*Syndrome\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAtaxia with Anti-GAD Antibodies\s*\n\s*"
        r"Internal\s+Medicine Vol\. 40, No\. 9 \(September 2001\)\s*\n\s*"
        r"Cerebellar Ataxia and Stiff-person\s*\n\s*Syndrome\b.*?"
        r"\nInternal\s+Medicine Vol\. 40, No\. 9 \(September 2001\)\s*\n\s*971\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bThe patients with cer\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nTable 1\. Clinical\s*\n\s*970\s*\n\s*Features of Cerebellar\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nInternal\s+Medicine Vol\. 40, No\. 9 \(September 2001\)\s*\n\s*"
        r"Cerebellar Ataxia and Stiff-person\s*\n\s*Syndrome\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nKey words: anti-GAD autoantibody, insulin-dependent diabe-\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\ntes mellitus, y-aminobutyric acid neuron, cerebel-\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nlum\s*(?=\nA complete blood)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    if "Cerebellar Ataxia and Stiff-person" in text:
        for match in re.finditer(
            r"\nIntroduction\s*\n",
            text,
            flags=re.IGNORECASE,
        ):
            exclusions.append((match.start(), match.end()))
    if "Borrelia burgdorferi myelitis presenting as a partial stift man syndrome" in text:
        for match in re.finditer(
            r"\nDiscussion\s*\n",
            text,
            flags=re.IGNORECASE,
        ):
            exclusions.append((match.start(), match.end()))
    if "Presentation of a Case With Repetitive Complex Discharges" in text:
        for match in re.finditer(
            r"\nDISCUSSION\s*\n",
            text,
            flags=re.IGNORECASE,
        ):
            exclusions.append((match.start(), match.end()))
        for match in re.finditer(
            r"\nFrom the Department\b.*?DOI:\s*10\.1097/NRL\.[^\n]*\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nGlutamic acid decarboxylase \(GAD\) is the main target.*?"
        r"\(Internal Medicine 40: 968-971, 2001\)\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(r"\nFrom the Department\b", text):
        table_match = re.search(r"\nTable\s+\d+\b", text[match.end() : match.end() + 1200], flags=re.IGNORECASE)
        if table_match is not None:
            exclusions.append((match.start(), match.end() + table_match.start()))
    for match in re.finditer(r"\n\*Correspondence to:.*?\n\s*\n", text, flags=re.IGNORECASE | re.DOTALL):
        if "vacuole into the vacuole itself" in match.group(0):
            continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\*Dept\..*?Received\s*:.*?(?:\n\s*\d{1,4})?\s*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"Downloaded from .*?Creative Commons License",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        start = text.rfind("\n", 0, match.start())
        if start < 0:
            start = match.start()
        previous_start = text.rfind("\n", 0, start)
        previous_line = text[previous_start + 1 : start] if previous_start >= 0 else ""
        if re.search(r"\b(?:Movement Disorders|MUSCLE & NERVE|Vol\.|Case of the Month)\b", previous_line):
            start = previous_start if previous_start >= 0 else start
        end = match.end()
        while end < len(text) and text[end] in " \t\r\n":
            end += 1
        next_line_end = text.find("\n", end)
        next_line = text[end : next_line_end if next_line_end >= 0 else len(text)].strip()
        if (
            next_line
            and len(next_line) <= 90
            and not re.match(r"(?i)^(?:table|fig(?:ure)?\.?)\b", next_line)
            and re.fullmatch(r"[A-Z0-9 .;&/'()\-]+", next_line)
        ):
            end = next_line_end + 1 if next_line_end >= 0 else len(text)
        exclusions.append((start, end))
    for match in re.finditer(
        r"\n?Downloaded from http://karger\.com/crn/[^\n]*\n\s*"
        r"Case Rep Neurol[^\n]*\n"
        r"DOI:[^\n]*\n"
        r"www\.karger\.com/crn\s*\n"
        r"Vacaras et al\.: Paraneoplastic Stiff Person Syndrome in Breast Cancer\s*"
        r"\n(?:\s*\n)*\s*\d{3}\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?Hindawi\n"
        r"Case Reports in Neurological Medicine\n"
        r"Volume 2017, Article ID \d+, 3 pages\n"
        r"https://doi\.org/10\.1155/2017/\d+\s*"
        r"\n\s*2 CaseReportsinNeurologicalMedicine\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{2,3}\s*Acta Neurologica Belgica \(\d{4}\) [^\n]*\n\s*1\s+3\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJ Neurosci Rural Pract [^\n]*\n"
        r"Case Report\n"
        r"Article published online: [^\n]*\n\s*"
        r"\d+\s*"
        r"Stiff-Person Syndrome Outpatient Rehabilitation\s+Khan et al\.\n"
        r"Journal of Neurosciences in Rural Practice[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJ Neurosci Rural Pract[^\n]*\n(?:[^\n]*\n){0,8}?"
        r"Journal of Neurosciences in Rural Practice[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s*\n"
        r"Stiff-Person Syndrome Outpatient Rehabilitation\s+Khan et al\.\n"
        r"Journal of Neurosciences in Rural Practice[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nFrontiers in Neurology \| www\.frontiersin\.org [^\n]*\n\s*"
        r"Godbe et al\.[^\n]*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nSu et al\. Progressive Encephalomyelitis With Rigidity\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?Downloaded from http://journals\.lww\.com/aacr\b.*?"
        r"Copyright [^\n]*International Anesthesia Research Society[^\n]*\n"
        r"(?:[^\n]{0,120}A & A PRACTICE\s*)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:ATYPICAL STIFF-PERSON SYNDROME\s+\d+\n)?"
        r"Downloaded from http://journals\.lww\.com/jcnmd\b[^\n]*\n"
        r"[^\n]*on \d{2}/\d{2}/\d{4}\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3,4}\s*\nwww\.[^\n]+\nby copyright\..*?Downloaded from\s*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nThis document is protected by international copyright laws\..*?"
        r"MINERVA MEDICA COPYRIGHT[^\n]*(?:\n[A-Z0-9 .\-]+){1,3}\s*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nA videotape accompanies this article\..*?"
        r"CLINICAL/SCIENTIFIC NOTES\s*\d+\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCLINICAL/SCIENTIFIC NOTES\s*\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAcknowledgements?\s*\nWe thank Dr\. Meiko Shiina.*?"
        r"(?=\n(?:FIG\.|Fig\.|Table\b|Case report\b)|\Z|\nReferences\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nMINERVA ANESTESIOLOGICA\s*\n\s*Novembre\s+2002\s*\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(r"\nPIOVANO\s*\n", text):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(r"Vol\. 68,\s*N\. 11\s*\n", text):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nACTA MEDICA \(Hradec [^)]+\) \d{4}; [^\n]+\n\n\d+\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n(?:J Neurol \(2012\) 259:[^\n]*\s+\d{4}|\d{4}\s+J Neurol \(2012\) 259:[^\n]*)\n123\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJ Neurol Neurosurg Psychiatry 2002;73:343.?350\s+345\s*\nwww\.jnnp\.com\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bSillevis\s+Smitt et al reported reversible cerebellar ataxia.*?(?=At present, however,)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    if "Case 27-2012: A 60-Year-Old Woman" in text:
        for match in re.finditer(r"\n(?:851|852|853|854|855|856|857)\s*(?=\n|$)", text):
            exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nPsychosomatics 43:\s*3,\s*May-June 2002\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\s+Psychosomatics 43:\s*3,\s*May-June 2002\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nReceived January 18, 2002;.*?Case Reports\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nLetters 939\s*\nwww\.annrheumdis\.com.*?active\s+juvenile onset SpA\.\s*"
        r"ACKNOWLEDGEMENT.*?(?=\nJournal of\s+CLINICAL|\nCorrespondence: M\. I\. Vicente|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJournal of\s+CLINICAL\s+NEUROMUSCULAR\s+DISEASE\s+Volume 14, Number 2.*?"
        r"Short Report72\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3}\s+Warren et al\.\s*\n"
        r"Journal of Clinical Neuroscience \(2002\) 9\(3\) & 2002 Published by Elsevier Science Ltd\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nM\. I\. Vicente-Valor\* PharmD,.*?Received 7 December 2011, Accepted 15 May 2012\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nCorrespondence: M\. I\. Vicente-Valor, Pharmacy Department.*?"
        r"Blackwell Publishing Ltd\s+71\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJournal of the Neurological Sciences \d+ \(\d{4}\) [^\n]+\n"
        r"Abbreviations:.*?journal homepage: www\.elsevier\.com/locate/jns\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJournal of the Neurological Sciences \d+ \(\d{4}\) [^\n]+\n"
        r"(?:[^\n]{0,140}Corresponding author[^\n]*\n)?"
        r"(?:E-mail address:[^\n]*\n)?"
        r"0022-510X/\$.*?"
        r"journal homepage: www\.elsevier\.com/locate/jns\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nJournal of the Neurological Sciences \d+ \(\d{4}\) [^\n]+\n"
        r"\s*0022-510\s*\n\s*http://dx\.doi\.org/10\.1016/j\.jns\.[^\n]+\n"
        r"Contents lists available at ScienceDirect\s*\n"
        r"Journal of the Neurological Sciences\s*\n"
        r"journal homepage: www\.elsevier\.com/locate/jns\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n\d{3,4}\s+[A-Z]\.[^\n]{0,100}/\s*Journal of the Neurological Sciences "
        r"\d+ \(\d{4}\) [^\n]+\n",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"The previous report\nreferred to a 65-year-old man with SPS where neuropatho-\n"
        r"logical examination revealed cytoplasmic vacuoles in the\n"
        r"motor neurons in the lumbar spinal cord\.\n5\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\d{3,4}Ann Thorac Surg CASE REPORT.*?FEATURE ARTICLES\s*\n",
        text,
        flags=re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAccepted for publication.*?FEATURE ARTICLES\s*\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if "An 81-year-old woman" in match.group(0):
            continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bAccepted for publication\b.*?\bAuthor contributions:.*?"
        r"(?=\bREFERENCES\b|\nREFERENCES\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\bAccepted for publication\b.*?(?=\bREFERENCES\b|\nREFERENCES\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if len(match.group(0)) > 1500:
            continue
        if re.search(r"\b(?:CASE REPORT|Fig\.|Figure\s+\d+\.?|Table\s+\d+\.?)\b", match.group(0), flags=re.IGNORECASE):
            continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAccepted for publication.*?(?=\d{3,4}Ann Thorac Surg CASE REPORT)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if "An 81-year-old woman" in match.group(0):
            continue
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\d{3,4}Ann Thorac Surg CASE REPORT[^\n]*(?:\n\d{4};[^\n]*)?\n",
        text,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAckno\s*wledg(?:e)?m\s*ents\s*\Z",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\nAckno\s*wledg(?:e)?m\s*ents\s*(?=\n|$)",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?e\d{3}\s+Copyright\s+©\s+\d{4}\s+American Academy of Neurology\s*"
        r"(?:\nCopyright\s+©\s+\d{4}\s+American Academy of Neurology\. Unauthorized reproduction of this article is prohibited\.)?",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    for match in re.finditer(
        r"\n?Copyright\s+©\s+\d{4}\s+American Academy of Neurology\. Unauthorized reproduction of this article is prohibited\.\s*",
        text,
        flags=re.IGNORECASE,
    ):
        exclusions.append((match.start(), match.end()))
    return exclusions


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
    # Group-route pass-through preserves source material for review, but it is
    # deliberately not considered LangExtract-ready. A whole-paper group view can
    # include methods, generic disease context, or non-SPSD comparator material.
    return {
        "annotation_mode": "deterministic_group_pass_through",
        "validation_warnings": ["deterministic_group_pass_through_requires_review"],
        "manual_review_reasons": ["deterministic_group_pass_through_requires_review"],
        "segments": [
            {
                "targets": [target.target_id],
                "role": role,
                "confidence": "high",
                "evidence": "Deterministic group pass-through retained for review, not direct LangExtract readiness.",
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


def single_case_passthrough_annotation(
    *,
    prepared_source: PreparedSource,
    target_id: str = "p1",
) -> dict[str, Any]:
    """Return a source-backed single-case annotation for Stage 07 v1.

    The batch workflow deliberately treats Stage 06 high-confidence count-1
    sources as one patient unit. Clinical-window detection is still used when
    it is confident, but uncertain boundaries do not block XML/JSON output:
    batch inspection and regression fixtures decide whether the compiled unit
    is accepted.
    """

    ranges, confident = single_patient_clinical_ranges(
        prepared_source,
        include_age_anchor_fallback=True,
    )
    defer_reasons: list[str] = []
    selected_text = "\n".join(
        prepared_source.source_text[start:end]
        for start, end in ranges
    )
    selected_has_multiple_patient_histories = len(PATIENT_HISTORY_HEADING_RE.findall(selected_text)) >= 2
    selected_has_specific_spsd_case = case_heading_clinical_range(selected_text) is not None
    source_has_multiple_patient_histories = len(PATIENT_HISTORY_HEADING_RE.findall(prepared_source.source_text)) >= 2
    source_has_sms_sample_cohort = (
        re.search(r"\bSMS sera\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(
            r"\b\d+/\d+\)\s+of SMS sera\b|\bSMS cerebrospinal fluid \(CSF\) samples\b",
            prepared_source.source_text,
            flags=re.IGNORECASE,
        )
        is not None
    )
    source_has_intrathecal_gad_group_cohort = (
        re.search(r"\bIntrathecal\b.{0,80}\bglutamic acid decarboxylase antibodies", prepared_source.source_text, flags=re.IGNORECASE | re.DOTALL)
        is not None
        and re.search(r"\bTotal patients\s*\(n\s*=\s*19\)", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
        and re.search(r"\bStiff-person syndrome\s+1\s*\(5\.3\)", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
    )
    source_has_scmusd_group_series = (
        re.search(r"\bSpontaneous continuous motor unit single discharges\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
        and re.search(r"\b(?:14|fourteen)\s+patients\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
        and re.search(r"\bstiff-?limb syndrome was diagnosed in\s+one patient\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
    )
    source_has_three_generation_gad_family = (
        re.search(r"\b3-generation family\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(r"\bSera from three family members\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(r"\bAll patients had high-titer anti-GAD antibodies\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
    )
    source_has_paraneoplastic_case_series = (
        re.search(r"\bcase series\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(r"\bWe identified\s+68\s+patients\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(r"\b1\s+case\s+stiff person syndrome\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
    )
    source_has_anti_gad_encephalitis_cohort = (
        re.search(r"\bAll\s+32\s+patients\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
        and re.search(r"\bseizure-free group\s*\(group\s+1,\s*n\s*=\s*11\)", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
        and re.search(r"\bTable\s+2\s+Treatments and outcome in anti-GAD encephalitis\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
    )
    source_has_serum_gad_retrospective_cohort = (
        re.search(r"\bSerum\s+glutamate\s+decarboxy\s*lase\s+antibodies\s+and\s+neurological\s+disorders\b", prepared_source.source_text, flags=re.IGNORECASE)
        is not None
        and re.search(r"\bA total of\s+173\s+patients\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
    )
    source_has_paraneoplastic_pet_cohort = (
        "18F-FDG-PET" in prepared_source.source_text
        and "paraneoplastic neurological syndrome" in prepared_source.source_text
        and "Table 6 Stiff-person syndrome" in prepared_source.source_text
        and re.search(r"\b(?:A total of|We reviewed)\s+19\s+patients\b", prepared_source.source_text, flags=re.IGNORECASE) is not None
    )
    source_has_header_only_abstract_book_listing = (
        "M207. Stiff Person Syndrome in a Patient with Atypical" in prepared_source.source_text
        and "Antiamphiphysin Antibodies: A Case Report" in prepared_source.source_text
        and len(selected_text) < 800
        and not re.search(r"\b(?:Background|Case|Results|Discussion)\s*:", selected_text, flags=re.IGNORECASE)
    )
    if selected_has_multiple_patient_histories and not selected_has_specific_spsd_case:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif not confident and source_has_multiple_patient_histories:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_sms_sample_cohort:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_intrathecal_gad_group_cohort:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_scmusd_group_series:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_three_generation_gad_family:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_paraneoplastic_case_series:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_anti_gad_encephalitis_cohort:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_serum_gad_retrospective_cohort:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_paraneoplastic_pet_cohort:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    elif source_has_header_only_abstract_book_listing:
        defer_reasons.append("not_single_case_for_stage07_singlecase")
    if not defer_reasons:
        ranges = subtract_source_ranges(
            prepared_source.source_text,
            ranges,
            single_case_boilerplate_exclusion_ranges(prepared_source.source_text),
        )
    spans: list[dict[str, Any]] = []
    for start, end in ranges:
        spans.extend(source_range_to_span_payloads(prepared_source, start, end))
    annotation_mode = "single_case_clinical_window" if confident else "single_case_passthrough"
    if defer_reasons:
        annotation_mode = "single_case_deferred_multi_case_source"
    return {
        "route_mode": "individual",
        "annotation_mode": annotation_mode,
        "targets": [
            {
                "id": target_id,
                "kind": "patient",
                "label": "Patient 1",
                "evidence": "Stage 06 high-confidence single-patient source.",
            }
        ],
        "segments": [
            {
                "targets": [target_id],
                "role": "patient_specific",
                "confidence": "high" if confident else "review_required",
                "evidence": (
                    "Deterministic clinical-window selection for Stage 07 single-case v1."
                    if confident
                    else (
                        "Source appears to contain multiple patient histories and is deferred "
                        "from the Stage 07 single-case workflow."
                        if defer_reasons
                        else "Full prepared source retained for Stage 07 single-case batch inspection."
                    )
                ),
                "spans": spans,
            }
        ],
        "validation_warnings": [] if confident else ["single_case_passthrough_requires_inspection"],
        "manual_review_reasons": defer_reasons,
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


@dataclass(frozen=True)
class TextOffsetMatch:
    start: int
    end: int
    strategy: str


@dataclass(frozen=True)
class NormalisedTextMap:
    text: str
    source_starts: tuple[int, ...]
    source_ends: tuple[int, ...]


def normalised_text_map(text: str) -> NormalisedTextMap:
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    in_whitespace = False
    for index, char in enumerate(text):
        if char.isspace():
            if in_whitespace:
                ends[-1] = index + 1
            else:
                chars.append(" ")
                starts.append(index)
                ends.append(index + 1)
                in_whitespace = True
            continue
        chars.append(char)
        starts.append(index)
        ends.append(index + 1)
        in_whitespace = False

    while chars and chars[0] == " ":
        chars.pop(0)
        starts.pop(0)
        ends.pop(0)
    while chars and chars[-1] == " ":
        chars.pop()
        starts.pop()
        ends.pop()
    return NormalisedTextMap(
        text="".join(chars),
        source_starts=tuple(starts),
        source_ends=tuple(ends),
    )


def unique_normalised_text_offsets(block_text: str, selected_text: str) -> tuple[int, int] | None:
    selected_map = normalised_text_map(selected_text)
    if not selected_map.text:
        return None
    block_map = normalised_text_map(block_text)
    first = block_map.text.find(selected_map.text)
    if first < 0:
        return None
    if block_map.text.find(selected_map.text, first + 1) >= 0:
        return None
    last = first + len(selected_map.text) - 1
    return block_map.source_starts[first], block_map.source_ends[last]


def recover_selected_text_offsets(block_text: str, selected_text: str) -> TextOffsetMatch | None:
    exact = unique_text_offsets(block_text, selected_text)
    if exact is not None:
        return TextOffsetMatch(start=exact[0], end=exact[1], strategy="exact_text")
    normalised = unique_normalised_text_offsets(block_text, selected_text)
    if normalised is not None:
        return TextOffsetMatch(start=normalised[0], end=normalised[1], strategy="normalised_whitespace")
    return None


def add_span_repair(
    report: ValidationReport,
    *,
    logical_segment_id: str,
    block_id: str,
    old_start: int,
    old_end: int,
    match: TextOffsetMatch,
    selected_text: str,
) -> None:
    if (old_start, old_end) == (match.start, match.end):
        report.add_warning(
            f"normalised_span_text_match:{logical_segment_id}:{block_id}:{old_start}:{old_end}"
        )
    else:
        report.add_warning(
            f"relocated_span:{logical_segment_id}:{block_id}:{old_start}:{old_end}->{match.start}:{match.end}"
        )
    report.add_span_adjustment(
        {
            "logical_segment_id": logical_segment_id,
            "source_block_id": block_id,
            "requested_offsets": {"start": old_start, "end": old_end},
            "relocated_offsets": {"start": match.start, "end": match.end},
            "match_strategy": match.strategy,
            "selected_text_sha256": sha256_text(selected_text),
        }
    )


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


def role_target_compatibility_error(
    *,
    role: str,
    targets: list[str],
    declared_targets: list[Target],
    logical_segment_id: str,
) -> str:
    if role in {"uncertain", "background"}:
        return ""
    declared_by_id = {target.target_id: target for target in declared_targets}
    known_targets = [declared_by_id[target_id] for target_id in targets if target_id in declared_by_id]
    if not known_targets:
        return ""
    kinds = {target.target_kind for target in known_targets}
    if role == "patient_specific":
        if len(known_targets) != 1 or kinds != {"patient"}:
            return f"role_target_mismatch:{logical_segment_id}:patient_specific"
    elif role == "shared":
        if len(known_targets) < 2 or kinds != {"patient"}:
            return f"role_target_mismatch:{logical_segment_id}:shared"
    elif role in {"group_summary", "group_specific"}:
        if kinds != {"group"}:
            return f"role_target_mismatch:{logical_segment_id}:{role}"
    return ""


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
        role_error = role_target_compatibility_error(
            role=role,
            targets=targets,
            declared_targets=declared_targets,
            logical_segment_id=logical_segment_id,
        )
        if role_error:
            report.add_error(role_error)
            targets_valid = False
        confidence = str(item.get("confidence") or "").strip() or "unspecified"
        evidence = str(item.get("evidence") or "").strip()
        source_unit_ids = tuple(
            str(unit_id).strip()
            for unit_id in item.get("source_unit_ids") or []
            if str(unit_id).strip()
        )
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
            accepted_normalised_text = False
            if start < 0 or end < start or end > len(block.text):
                recovered = recover_selected_text_offsets(block.text, selected_text)
                if recovered is None:
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
                start, end = recovered.start, recovered.end
                add_span_repair(
                    report,
                    logical_segment_id=logical_segment_id,
                    block_id=block_id,
                    old_start=old_start,
                    old_end=old_end,
                    match=recovered,
                    selected_text=selected_text,
                )
                accepted_normalised_text = recovered.strategy == "normalised_whitespace"
            actual_text = block.text[start:end]
            if actual_text != selected_text and not accepted_normalised_text:
                recovered = recover_selected_text_offsets(block.text, selected_text)
                if recovered is None:
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
                start, end = recovered.start, recovered.end
                actual_text = block.text[start:end]
                add_span_repair(
                    report,
                    logical_segment_id=logical_segment_id,
                    block_id=block_id,
                    old_start=old_start,
                    old_end=old_end,
                    match=recovered,
                    selected_text=selected_text,
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
                    source_unit_ids=source_unit_ids,
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


def audit_only_section_text(text: str) -> bool:
    """Return true for section text that should not feed target views."""

    return bool(AUDIT_ONLY_SECTION_HEADING_RE.search(str(text or "").strip()))


def text_mentions_target_label(text: str, label: str) -> bool:
    label_text = str(label or "").strip()
    if len(label_text) < 4:
        return False
    return bool(re.search(tolerant_label_pattern(label_text), text, flags=re.IGNORECASE))


def logical_segment_bundles(segments: list[PhysicalSegment]) -> dict[str, list[PhysicalSegment]]:
    bundles: dict[str, list[PhysicalSegment]] = {}
    for segment in segments:
        bundles.setdefault(segment.logical_segment_id, []).append(segment)
    return bundles


def apply_precision_safety_demotions(
    *,
    targets: list[Target],
    segments: list[PhysicalSegment],
    report: ValidationReport,
) -> list[PhysicalSegment]:
    """Demote segments that are useful for audit but unsafe for extraction.

    Stage 07 keeps the XML audit trail intact, but target views are downstream
    extraction inputs. If a segment is abstract Methods/Results text or a shared
    segment that mixes explicit patient labels, it should be visible to a human
    reviewer without being treated as ready per-target evidence.
    """

    targets_by_id = {target.target_id: target for target in targets}
    demotions: dict[str, tuple[str, str, list[str]]] = {}
    for logical_id, bundled_segments in logical_segment_bundles(segments).items():
        text = "\n\n".join(segment.text for segment in sorted(bundled_segments, key=lambda item: item.source_start))
        bundled_targets = sorted({target_id for segment in bundled_segments for target_id in segment.targets})
        bundled_roles = {segment.role for segment in bundled_segments}
        if audit_only_section_text(text) and not current_patient_sample_context(text, targets):
            demotions[logical_id] = (
                "unknown",
                "uncertain",
                [f"audit_only_unsafe_section_segment:{logical_id}"],
            )
            continue
        patient_targets = [
            targets_by_id[target_id]
            for target_id in bundled_targets
            if target_id in targets_by_id and targets_by_id[target_id].target_kind == "patient"
        ]
        mentioned_patient_targets = [
            target
            for target in patient_targets
            if text_mentions_target_label(text, target.label)
        ]
        if "shared" in bundled_roles and len(bundled_targets) > 1 and len(mentioned_patient_targets) >= 2:
            demotions[logical_id] = (
                "retain",
                "uncertain",
                [f"mixed_shared_patient_specific_segment:{logical_id}"],
            )

    if not demotions:
        return segments

    for _, _, reasons in demotions.values():
        for reason in reasons:
            report.add_warning(reason)
            report.add_review_reason(reason)

    adjusted: list[PhysicalSegment] = []
    for segment in segments:
        demotion = demotions.get(segment.logical_segment_id)
        if demotion is None:
            adjusted.append(segment)
            continue
        target_mode, role, _reasons = demotion
        adjusted.append(
            PhysicalSegment(
                segment_id=segment.segment_id,
                logical_segment_id=segment.logical_segment_id,
                targets=["unknown"] if target_mode == "unknown" else segment.targets,
                role=role,
                text=segment.text,
                source_start=segment.source_start,
                source_end=segment.source_end,
                block_id=segment.block_id,
                confidence=segment.confidence,
                evidence=segment.evidence,
                source_unit_ids=segment.source_unit_ids,
            )
        )
    return adjusted


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


def single_case_stage07_segment(segment: PhysicalSegment) -> bool:
    return "Stage 07 single-case v1" in segment.evidence


def present_case_table_range(segment: PhysicalSegment) -> tuple[int, int] | None:
    if not re.search(r"\btable\b", segment.text, flags=re.IGNORECASE):
        return None
    if not re.search(r"\bpresent\s+case\b", segment.text, flags=re.IGNORECASE):
        return None
    line_match = re.search(r"(?im)^\s*Present\s+Case\s*$", segment.text)
    if line_match is not None:
        return segment.source_start + line_match.start(), segment.source_end
    matches = list(re.finditer(r"\bPresent\s+Case\b", segment.text, flags=re.IGNORECASE))
    if not matches:
        return None
    match = matches[-1]
    return segment.source_start + match.start(), segment.source_end


def present_case_table_start(segment: PhysicalSegment, present_case_start: int) -> int:
    local_present_case_start = max(0, present_case_start - segment.source_start)
    table_matches = list(
        re.finditer(
            r"\btable\b",
            segment.text[:local_present_case_start],
            flags=re.IGNORECASE,
        )
    )
    if not table_matches:
        return present_case_start
    return segment.source_start + table_matches[-1].start()


def apply_table_relevance_heuristics(
    *,
    prepared_source: PreparedSource,
    segments: list[PhysicalSegment],
    report: ValidationReport,
) -> list[PhysicalSegment]:
    relevant_ids = explicit_spsd_case_ids(prepared_source.source_text)
    blocks_by_id = {block.block_id: block for block in prepared_source.blocks}
    adjusted: list[PhysicalSegment] = []
    for segment in segments:
        if not re.search(r"\btable\b", segment.text, flags=re.IGNORECASE):
            adjusted.append(segment)
            continue
        block = blocks_by_id.get(segment.block_id)
        if block is None:
            adjusted.append(segment)
            continue
        if single_case_stage07_segment(segment):
            present_case_range = present_case_table_range(segment)
            if present_case_range is not None:
                start, end = present_case_range
                table_start = present_case_table_start(segment, start)
                report.add_warning(f"trimmed_table_to_present_case_column:{segment.segment_id}")
                if segment.source_start < table_start:
                    prefix_start, prefix_end = trim_source_range(
                        prepared_source.source_text,
                        segment.source_start,
                        table_start,
                    )
                    if prefix_start < prefix_end:
                        adjusted.append(
                            PhysicalSegment(
                                segment_id="",
                                logical_segment_id=segment.logical_segment_id,
                                targets=segment.targets,
                                role=segment.role,
                                text=prepared_source.source_text[prefix_start:prefix_end],
                                source_start=prefix_start,
                                source_end=prefix_end,
                                block_id=segment.block_id,
                                confidence=segment.confidence,
                                evidence=segment.evidence,
                                source_unit_ids=segment.source_unit_ids,
                            )
                        )
                adjusted.append(
                    PhysicalSegment(
                        segment_id="",
                        logical_segment_id=segment.logical_segment_id,
                        targets=segment.targets,
                        role=segment.role,
                        text=prepared_source.source_text[start:end],
                        source_start=start,
                        source_end=end,
                        block_id=segment.block_id,
                        confidence=segment.confidence,
                        evidence=segment.evidence,
                        source_unit_ids=segment.source_unit_ids,
                    )
                )
                continue
            adjusted.append(segment)
            continue
        if not relevant_ids:
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
                    source_unit_ids=segment.source_unit_ids,
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
            source_unit_ids=segment.source_unit_ids,
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
            "source_unit_ids": list(segment.source_unit_ids),
            "confidence": segment.confidence,
            "evidence": segment.evidence,
        }
        for segment in sorted(segments, key=lambda item: (item.source_start, item.source_end))
    ]


def relevant_segments_for_target(
    target: Target,
    segments: list[PhysicalSegment],
) -> list[PhysicalSegment]:
    """Return segments that may be compiled into a target-specific view.

    Validation keeps uncertain and background segments in the annotated source
    for auditability, but target views are downstream extraction inputs. For
    precision-first Stage 07 behaviour, they must contain only attributable
    patient/group evidence.
    """

    selected: list[PhysicalSegment] = []
    for segment in segments:
        if target.target_id not in segment.targets:
            continue
        if "unknown" in segment.targets or segment.role in {"uncertain", "background"}:
            continue
        selected.append(segment)
    return sorted(selected, key=lambda item: (item.source_start, item.source_end))


def contamination_review_reasons(
    targets: list[Target],
    segments: list[PhysicalSegment],
) -> list[str]:
    """Flag background text that was still assigned to a declared target.

    Background is allowed as an annotation role because it helps reviewers see
    what the model classified as non-evidence. If it is targeted to a patient or
    group, the paper needs manual review even though the segment is excluded from
    target-view compilation.
    """

    known_target_ids = {target.target_id for target in targets}
    targets_by_id = {target.target_id: target for target in targets}
    reasons: list[str] = []
    for logical_id, bundled_segments in logical_segment_bundles(segments).items():
        text = "\n\n".join(segment.text for segment in sorted(bundled_segments, key=lambda item: item.source_start))
        bundled_targets = sorted({target_id for segment in bundled_segments for target_id in segment.targets})
        bundled_roles = {segment.role for segment in bundled_segments}
        if "background" in bundled_roles and known_target_ids.intersection(bundled_targets):
            reasons.append(f"targeted_background_segment:{logical_id}")
        if bundled_roles and bundled_roles <= {"background", "uncertain"}:
            continue
        if audit_only_section_text(text) and not current_patient_sample_context(text, targets):
            reasons.append(f"unsafe_section_text:{logical_id}")
        if comparator_only_context(text, targets) and not explicit_target_mentions(text, targets):
            reasons.append(f"comparator_only_leak:{logical_id}")
        for target_id in bundled_targets:
            if target_id not in targets_by_id:
                continue
            for other in targets:
                if other.target_id == target_id or other.target_id in bundled_targets:
                    continue
                if other.target_kind == "patient" and label_mentions_other_current_target(text, other):
                    reasons.append(
                        f"cross_target_label_leak:{target_id}:{other.target_id}:{logical_id}"
                    )
    return sorted(set(reasons))


def relation_to_target(target: Target, segment: PhysicalSegment) -> str:
    if len(segment.targets) > 1:
        return "shared"
    if target.target_kind == "group":
        return "group"
    return "direct"


def target_unit_source(*, target: Target, route: str, annotation_mode: str) -> str:
    if target.target_kind == "patient" and route == "individual" and (
        annotation_mode.startswith("single_case_") or annotation_mode.startswith("deterministic_")
    ):
        return "single_case_passthrough"
    if route == "individual_case_split":
        return "stage07_xml_case_series"
    if route == "group":
        return "stage07_xml_group"
    return "stage07_xml"


def build_target_views(
    *,
    paper_id: str,
    targets: list[Target],
    segments: list[PhysicalSegment],
    paper_ready: bool,
    manual_review_reasons: list[str],
    route: str,
    annotation_mode: str,
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
                    "source_unit_ids": list(segment.source_unit_ids),
                    "compiled_offsets": {"start": start, "end": end},
                }
            )
        input_text = "".join(compiled_parts)
        target_has_text = bool(input_text.strip())
        ready = bool(paper_ready and target_has_text)
        target_reasons = list(manual_review_reasons)
        if not target_has_text:
            target_reasons.append(f"missing_target_evidence:{target.target_id}")
        unit_id = f"{paper_id}::{target.target_id}"
        unit_type = "individual_patient" if target.target_kind == "patient" else "group"
        unit_source = target_unit_source(
            target=target,
            route=route,
            annotation_mode=annotation_mode,
        )
        views[target.target_id] = {
            "stage07_target_view_schema_version": TARGET_VIEW_SCHEMA_VERSION,
            "document_id": unit_id,
            "paper_id": paper_id,
            "target_id": target.target_id,
            "target_kind": target.target_kind,
            "target_label": target.label,
            "unit_id": unit_id,
            "unit_type": unit_type,
            "unit_source": unit_source,
            "unit_index": int(target.target_id[1:]) if target.target_id[1:].isdigit() else 1,
            "unit_count_within_paper": len(targets),
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
    rows_by_id: dict[str, dict[str, str]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                paper_id = str(row.get("paper_id") or "").strip()
                if paper_id:
                    rows_by_id[paper_id] = {
                        field: str(row.get(field) or "")
                        for field in REGISTRY_FIELDNAMES
                    }
    for row in rows:
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            rows_by_id[paper_id] = {
                field: str(row.get(field) or "")
                for field in REGISTRY_FIELDNAMES
            }
    merged_rows = [
        rows_by_id[paper_id]
        for paper_id in sorted(rows_by_id, key=sort_key)
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(merged_rows)


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
    only_view = next(iter(target_views.values())) if len(target_views) == 1 else {}
    clear_single_case = (
        stage06_prior.final_count == 1
        and stage06_prior.count_confidence == "high"
        and not stage06_prior.manual_review_required
    )
    stage07_scope = "single_case_v1" if clear_single_case and route == "individual" else ""
    stage07_status = "ready_for_langextract" if ready_for_langextract else "manual_review_required"
    defer_reason = "" if ready_for_langextract else "|".join(manual_review_reasons)
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
        "stage07_scope": stage07_scope,
        "stage07_status": stage07_status,
        "unit_id": str(only_view.get("unit_id") or ""),
        "unit_type": str(only_view.get("unit_type") or ""),
        "unit_source": str(only_view.get("unit_source") or ""),
        "defer_reason": defer_reason,
        "eligibility_basis": "stage06_clear_single_count" if clear_single_case else "",
        "text_path": prepared_source.source_text_json_path,
        "model_audit_status": "",
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
    return annotation_mode not in {
        "deterministic_pass_through",
        "deterministic_clinical_window",
        "single_case_clinical_window",
        "single_case_passthrough",
        "single_case_deferred_multi_case_source",
        "reviewed_gold",
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
    segments = apply_precision_safety_demotions(
        targets=targets,
        segments=segments,
        report=validation_report,
    )
    # Add contamination checks after payload validation so every accepted
    # physical segment has stable logical IDs for reviewer-facing reasons.
    for reason in contamination_review_reasons(targets, segments):
        validation_report.add_review_reason(reason)

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
        route=route,
        annotation_mode=annotation_mode,
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


def is_clear_stage06_single_case(row: dict[str, str]) -> bool:
    return (
        truthy(row.get("count_eligible") or "")
        and str(row.get("likely_sps_case_count") or "").strip() == "1"
        and str(row.get("count_confidence") or "").strip() == "high"
        and not truthy(row.get("count_manual_review_required") or "")
    )


def collect_single_case_candidate_ids(
    *,
    stage06_rows: dict[str, dict[str, str]],
    paper_ids: list[str],
    limit: int,
    start_index: int = 0,
) -> list[str]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    if wanted:
        return sorted_paper_ids(wanted)
    candidate_ids = [
        paper_id
        for paper_id, row in sorted(stage06_rows.items(), key=lambda item: sort_key(item[0]))
        if is_clear_stage06_single_case(row)
    ]
    if start_index > 0:
        candidate_ids = candidate_ids[start_index:]
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
