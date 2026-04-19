from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        OpenAI,
        OpenAIError,
        PermissionDeniedError,
        RateLimitError,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests without OpenAI installed
    OpenAI = None

    class OpenAIError(Exception):
        """Fallback OpenAI base error used when the SDK is unavailable."""

    class APIConnectionError(OpenAIError):
        pass

    class APIStatusError(OpenAIError):
        pass

    class APITimeoutError(OpenAIError):
        pass

    class AuthenticationError(OpenAIError):
        pass

    class BadRequestError(OpenAIError):
        pass

    class NotFoundError(OpenAIError):
        pass

    class PermissionDeniedError(OpenAIError):
        pass

    class RateLimitError(OpenAIError):
        pass
from pydantic import BaseModel, Field

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _proceedings_text import (
    LineRef,
    collect_title_cluster,
    is_footer_like,
    is_header_noise,
    is_potential_title_line,
    is_uppercase_title_like,
    score_authors,
    score_title,
)
from _source_routing import load_csv_rows_by_id, resolve_source_row, truthy
from _sps_case_count_registry import (
    COUNT_TOKEN_TEXT_PATTERN,
    SPS_SUBGROUP_PAIR_RE,
    SPS_SUBGROUP_SUFFIX_RE,
    parse_count_token,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
STAGE07_UNITS_DIR = REPO_ROOT / "data" / "extraction_json" / "text_case_series_units"
STAGE07_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "case_series_split_registry.csv"
STAGE07_MANIFEST_DIR = REPO_ROOT / "results" / "stage07_unit_manifests"
SOURCE_CATEGORISATION_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
SOURCE_MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
SOURCE_CASE_COUNT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
REFERENCES_PATH = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
STAGE07_SCHEMA_VERSION = "stage07_units_v1"
MANIFEST_SCHEMA_VERSION = "stage07_unit_manifest_v1"
PIPELINE_ENTRYPOINT = "07_split_case_series.py"
DEFAULT_CANDIDATE_GENERATION_MODE = "heuristics_v1"
DEFAULT_ADJUDICATION_MODEL = "disabled"
DEFAULT_ADJUDICATION_MAX_OUTPUT_TOKENS = 4000
MIN_ADJUDICATED_UNIT_TEXT_LENGTH = 80
DEFAULT_OPENAI_ENV_FILE = REPO_ROOT / "env" / "openai_api_key.env"
OPENAI_DEPENDENCY_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    RateLimitError,
    BadRequestError,
    APIStatusError,
    OpenAIError,
)

STAGE07_ADJUDICATION_SYSTEM_PROMPT = """\
You prepare attribution-safe stage-07 split units for a systematic review of stiff person spectrum disorder (SPSD).

Your job is to recover publishable stage-07 units from the provided paper lines.

Critical rules:
- Use only the supplied line indices and supplied text. Never invent patients, groups, labels, counts, spans, or quotes.
- A published `individual` unit must contain only text that can be attributed to one specific patient.
- A published `group` unit must contain only text that can be attributed to one explicit, relevant subgroup.
- When a statement applies to multiple known units, put it in `shared_context_blocks`, not inside one unit's primary span.
- If the structure is not attribution-safe, prefer `manual_review_required` over a risky split.
- One output per individual.
- One output per relevant subgroup.
- Split antibody-defined groups only when the source makes them explicitly disjoint.
- Do not force fake patient splits for genuinely group-level papers.
- Ignore cited-literature summaries, references, acknowledgements, and obvious article metadata.

Span rules:
- Every unit must cite one or more inclusive `line_spans`.
- Prefer the smallest spans that preserve meaning.
- Unit spans must not overlap each other.
- Shared-context spans must not overlap primary unit spans.
- If a span would mix multiple individuals in a way that cannot be separated safely, do not publish it as an individual unit.

Decision rules:
- `publish_units` when you can identify one or more attribution-safe units.
- `manual_review_required` when the paper likely contains relevant material but the split is unsafe.
- `unable_to_determine` when the provided evidence is too weak to support any safe split.

Return JSON only and match the schema exactly.
"""


class Stage07LineSpan(BaseModel):
    start_global_index: int = Field(..., ge=0)
    end_global_index: int = Field(..., ge=0)


class Stage07AdjudicatedUnit(BaseModel):
    unit_type: Literal["individual", "group"]
    unit_label: str = Field(..., min_length=1)
    line_spans: list[Stage07LineSpan] = Field(..., min_length=1)
    evidence_summary: str = Field(..., min_length=1)
    group_name: str | None = None
    group_size: int | None = Field(None, ge=1)


class Stage07AdjudicatedSharedContext(BaseModel):
    context_label: str = Field(..., min_length=1)
    applies_to_unit_labels: list[str] = Field(..., min_length=2)
    line_spans: list[Stage07LineSpan] = Field(..., min_length=1)
    evidence_summary: str = Field(..., min_length=1)


class Stage07AdjudicationOutput(BaseModel):
    decision_type: Literal["publish_units", "manual_review_required", "unable_to_determine"]
    decision_summary: str = Field(..., min_length=1)
    units: list[Stage07AdjudicatedUnit] = Field(default_factory=list)
    shared_context_blocks: list[Stage07AdjudicatedSharedContext] = Field(default_factory=list)
    unresolved_remainder_reason: str = ""

CASE_MARKER_RE = re.compile(
    r"^(?P<lemma>case|patient)\b\s*(?:no\.?|number)?\s*(?P<num>\d+|[ivxlcdm]+|[a-z])\b[:.\-)]?",
    re.IGNORECASE,
)
INLINE_CASE_MARKER_RE = re.compile(
    r"(?:^|[.:;]\s+)(?P<lemma>case|patient)\b\s*(?:no\.?|number)?\s*(?P<num>\d+|[ivxlcdm]+|[a-z])\b[:.\-)]?",
    re.IGNORECASE,
)
ORDINAL_MARKER_RE = re.compile(
    r"^(?P<label>(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:case|patient))\b[:.\-)]?",
    re.IGNORECASE,
)
STOP_HEADING_RE = re.compile(
    r"^(?:discussion|conclusions?|references|acknowledg(?:e)?ments?|"
    r"legends?\b|supplementary\b|appendix\b|results\b|tables?\b)\b",
    re.IGNORECASE,
)
BOUNDED_SHARED_CONTEXT_RE = re.compile(
    rf"\b(?P<count>both|{COUNT_TOKEN_TEXT_PATTERN})\b\s+"
    r"(?:(?:individually|separately)\s+described\s+)?(?:patients?|cases?)\b",
    re.IGNORECASE,
)
ANTIBODY_PREFIX_RE = re.compile(
    rf"\b(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\b\s+"
    r"(?P<label>anti[- ]?(?:gad(?:65)?|amphiphysin|glyr|gaba[- ]?a(?: receptor)?|dppx|gephyrin)"
    r"(?:[- ]positive)?|seronegative)\s+(?:patients?|cases?)\b",
    re.IGNORECASE,
)
ANTIBODY_SUFFIX_RE = re.compile(
    r"\b(?P<label>anti[- ]?(?:gad(?:65)?|amphiphysin|glyr|gaba[- ]?a(?: receptor)?|dppx|gephyrin)"
    r"(?:[- ]positive)?|seronegative)\b\s*\(\s*(?:n\s*[=:]\s*)?"
    rf"(?P<count>{COUNT_TOKEN_TEXT_PATTERN})\b",
    re.IGNORECASE,
)
STRICT_AUTHOR_CREDENTIAL_RE = re.compile(
    r"\b(MD|M\.D\.|DO|D\.O\.|PHD|PH\.D\.|MSC|M\.S\.|MS|BS|B\.S\.|MBA|MBBS|MPH|RN|FRCPC|FAAN|FRCP|DPhil)\b",
    re.IGNORECASE,
)
STRICT_AUTHOR_PAIR_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+\b")

ORDINAL_TO_INT = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
ROMAN_TO_INT = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
}
LETTER_TO_INT = {letter: index for index, letter in enumerate("abcdefghijklmnopqrstuvwxyz", start=1)}

REGISTRY_FIELDNAMES = [
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
    "publication_status",
    "publication_reason_code",
    "published_unit_count",
    "published_individual_count",
    "published_group_count",
    "shared_context_count",
    "has_unresolved_remainder",
    "stage06_preferred_text_json_path",
    "stage06_final_count",
    "stage06_count_confidence",
    "stage06_count_verification_status",
    "stage06_granularity",
    "stage06_granularity_is_provisional",
    "stage06_diverged",
    "manifest_run_id",
]


@dataclass
class Stage07ProcessResult:
    paper_id: str
    paper_payload: dict[str, Any]
    manifest_records: list[dict[str, Any]]
    registry_row: dict[str, str]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest_run_id(now_iso: str | None = None) -> str:
    now_value = datetime.now(timezone.utc) if now_iso is None else datetime.fromisoformat(now_iso)
    return now_value.strftime("%Y%m%dT%H%M%SZ_stage07")


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
    raw = (value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def strip_wrapping_quotes(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def resolve_openai_api_key(
    api_key: str | None = None,
    *,
    env_file: Path = DEFAULT_OPENAI_ENV_FILE,
) -> str:
    explicit_key = str(api_key or "").strip()
    if explicit_key:
        return explicit_key
    if not env_file.exists():
        raise RuntimeError(
            f"Stage 07 requires an OpenAI key at {env_file.as_posix()}, but that file does not exist."
        )
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("OPENAI_API_KEY="):
            continue
        _, value = line.split("=", 1)
        key = strip_wrapping_quotes(value)
        if key:
            return key
        break
    raise RuntimeError(
        f"Stage 07 requires OPENAI_API_KEY=... in {env_file.as_posix()}, but no usable value was found."
    )


def is_openai_dependency_error(exc: BaseException) -> bool:
    return isinstance(exc, OPENAI_DEPENDENCY_EXCEPTIONS)


def preflight_openai(
    *,
    model: str,
    api_key: str | None = None,
    env_file: Path = DEFAULT_OPENAI_ENV_FILE,
) -> dict[str, str]:
    if OpenAI is None:
        raise RuntimeError(
            "Stage 07 OpenAI preflight cannot run because the openai package is not installed."
        )
    resolved_key = resolve_openai_api_key(api_key, env_file=env_file)
    client = OpenAI(api_key=resolved_key)
    try:
        client.responses.create(
            model=model,
            store=False,
            input=[{"role": "user", "content": "Reply with OK."}],
            max_output_tokens=16,
        )
    except OPENAI_DEPENDENCY_EXCEPTIONS as exc:
        raise RuntimeError(
            "Stage 07 OpenAI preflight failed before the run started: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc
    return {
        "status": "available",
        "model": model,
        "credential_source": "explicit_api_key" if api_key else "env/openai_api_key.env",
        "env_file_path": str(env_file),
    }


@lru_cache(maxsize=1)
def load_reference_rows() -> dict[str, dict[str, str]]:
    if not REFERENCES_PATH.exists():
        return {}
    with REFERENCES_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row.get("Covidence") or "").strip(): row
            for row in reader
            if (row.get("Covidence") or "").strip()
        }


def reference_row_for_paper(paper_id: str) -> dict[str, str]:
    return load_reference_rows().get(str(paper_id or "").strip(), {})


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_lines(record: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    global_index = 0
    for page in record.get("pages") or []:
        page_index = int(page.get("page_index") or 0)
        page_text = str(page.get("text") or "")
        for line_index, raw_line in enumerate(page_text.splitlines()):
            line = " ".join(raw_line.split())
            if not line:
                continue
            lines.append(
                {
                    "page_index": page_index,
                    "line_index": line_index,
                    "global_index": global_index,
                    "text": line,
                }
            )
            global_index += 1
    return lines


def to_line_refs(lines: list[dict[str, Any]]) -> list[LineRef]:
    return [
        LineRef(
            global_index=int(line["global_index"]),
            page_index=int(line["page_index"]),
            line_index=int(line["line_index"]),
            text=str(line["text"]),
        )
        for line in lines
    ]


def strict_author_line(line_text: str) -> bool:
    stripped = line_text.strip()
    if not stripped or len(stripped) > 220:
        return False
    if STRICT_AUTHOR_CREDENTIAL_RE.search(stripped):
        return True
    if ";" in stripped and STRICT_AUTHOR_PAIR_RE.search(stripped):
        return True
    if stripped.count(",") >= 1 and re.search(r"\b[A-Z]\.", stripped):
        return True
    if stripped.count(",") >= 2 and len(STRICT_AUTHOR_PAIR_RE.findall(stripped)) >= 2:
        return True
    return False


def affiliation_like_line(line_text: str) -> bool:
    normalized = " ".join(line_text.strip().lower().split())
    if not normalized:
        return False
    if normalized.startswith(
        (
            "* correspondence",
            "correspondence:",
            "full list of author information",
            "doi ",
            "doi:",
            "© the author",
        )
    ):
        return True
    if normalized.startswith(("1department", "2department", "3department", "1service", "2service", "3service")):
        return True
    return any(
        marker in normalized
        for marker in (
            "department of",
            "service of",
            "division of",
            "university",
            "hospital",
            "institute",
            "centre",
            "center",
            "school of medicine",
        )
    )


def article_metadata_line(line_text: str) -> bool:
    normalized = " ".join(line_text.strip().lower().split())
    if not normalized:
        return False
    return (
        normalized.startswith("from the ")
        or normalized.startswith("received ")
        or normalized.startswith("address correspondence")
        or normalized.startswith("copyright ")
        or normalized.startswith("doi:")
        or normalized.startswith("© ")
    )


def ignorable_noise_line(line_text: str) -> bool:
    if is_footer_like(line_text):
        return True
    if article_metadata_line(line_text):
        return True
    if affiliation_like_line(line_text):
        return True
    normalized = " ".join(line_text.strip().lower().split())
    return normalized.startswith(("supported in part by", "presented at the "))


def find_article_anchor(
    lines: list[dict[str, Any]],
    *,
    reference_title: str,
    reference_authors: str,
) -> tuple[int, float, float] | None:
    if not reference_title.strip():
        return None

    line_refs = to_line_refs(lines)
    best_index: int | None = None
    best_title_score = 0.0
    best_combined = 0.0

    def consider_indices(candidate_indices: list[int]) -> None:
        nonlocal best_index, best_title_score, best_combined
        for index in candidate_indices:
            line_ref = line_refs[index]
            if is_header_noise(line_ref.text):
                continue
            cluster = collect_title_cluster(line_refs, index, max_lines=4)
            candidate_texts = []
            if cluster:
                candidate_texts.append(" ".join(item.text for item in cluster).strip())
            candidate_texts.append(line_ref.text)
            running_parts: list[str] = []
            for next_index in range(index, min(len(line_refs), index + 4)):
                next_text = line_refs[next_index].text
                if next_index > index and (strict_author_line(next_text) or article_metadata_line(next_text)):
                    break
                running_parts.append(next_text)
                combined_text = " ".join(running_parts).strip()
                if combined_text and combined_text not in candidate_texts:
                    candidate_texts.append(combined_text)

            author_window = " ".join(
                item.text for item in line_refs[max(0, index - 2) : min(len(line_refs), index + 6)]
            )
            author_score = score_authors(reference_authors, author_window)
            for candidate_text in candidate_texts:
                title_score = score_title(reference_title, candidate_text)
                if title_score < 0.45:
                    continue
                combined = (0.8 * title_score) + (0.2 * author_score)
                if combined > best_combined:
                    best_index = index
                    best_title_score = title_score
                    best_combined = combined

    candidate_indices = [
        index
        for index, line_ref in enumerate(line_refs)
        if is_potential_title_line(line_ref.text)
        and not strict_author_line(line_ref.text)
        and not article_metadata_line(line_ref.text)
    ]
    consider_indices(candidate_indices)
    if best_index is None:
        consider_indices(list(range(len(line_refs))))

    if best_index is None:
        return None
    return best_index, best_title_score, best_combined


def find_next_article_header_index(
    lines: list[dict[str, Any]],
    *,
    start_index: int,
    reference_title: str,
) -> int | None:
    line_refs = to_line_refs(lines)
    dynamic_gap = min(80, max(4, len(line_refs) // 4))
    lower_bound = max(0, start_index + dynamic_gap)
    upper_bound = min(len(line_refs), start_index + 1200)
    for index in range(lower_bound, upper_bound):
        line_text = line_refs[index].text
        if affiliation_like_line(line_text) or article_metadata_line(line_text):
            continue
        if not is_potential_title_line(line_text):
            continue
        if is_header_noise(line_text):
            continue
        if line_text.endswith(".") and not is_uppercase_title_like(line_text):
            continue

        cluster = collect_title_cluster(line_refs, index, max_lines=4)
        if not cluster:
            continue
        cluster_text = " ".join(item.text for item in cluster).strip()
        if score_title(reference_title, cluster_text) >= 0.72:
            continue

        lookahead = line_refs[index + len(cluster) : min(len(line_refs), index + len(cluster) + 6)]
        if any(strict_author_line(item.text) for item in lookahead):
            return index
    return None


def restrict_to_article_window(
    lines: list[dict[str, Any]],
    *,
    reference_row: dict[str, str],
) -> list[dict[str, Any]]:
    reference_title = str(reference_row.get("Title") or "").strip()
    reference_authors = str(reference_row.get("Authors") or "").strip()
    if not reference_title:
        return lines

    anchor = find_article_anchor(
        lines,
        reference_title=reference_title,
        reference_authors=reference_authors,
    )
    if anchor is None:
        return lines

    anchor_index, title_score, combined_score = anchor
    if title_score < 0.78 and combined_score < 0.74:
        return lines

    next_header_index = find_next_article_header_index(
        lines,
        start_index=anchor_index,
        reference_title=reference_title,
    )
    end_index = next_header_index if next_header_index is not None else len(lines)
    return lines[anchor_index:end_index]


def render_lines(lines: list[dict[str, Any]]) -> str:
    return "\n".join(line["text"] for line in lines).strip()


def build_line_range_refs(
    lines: list[dict[str, Any]],
    *,
    role: str,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not lines:
        return refs

    current_page = int(lines[0]["page_index"])
    current_start = int(lines[0]["line_index"])
    current_end = int(lines[0]["line_index"])
    for line in lines[1:]:
        page_index = int(line["page_index"])
        line_index = int(line["line_index"])
        if page_index == current_page and line_index == current_end + 1:
            current_end = line_index
            continue
        refs.append(
            {
                "ref_type": "line_range",
                "role": role,
                "page_index": current_page,
                "line_start": current_start,
                "line_end": current_end,
            }
        )
        current_page = page_index
        current_start = line_index
        current_end = line_index

    refs.append(
        {
            "ref_type": "line_range",
            "role": role,
            "page_index": current_page,
            "line_start": current_start,
            "line_end": current_end,
        }
    )
    return refs


def parse_case_marker(line: str) -> str | None:
    stripped = line.strip()
    if len(stripped) > 220:
        return None
    match = CASE_MARKER_RE.match(stripped)
    if match:
        return f"{match.group('lemma').title()} {match.group('num').upper()}"
    inline_match = INLINE_CASE_MARKER_RE.search(stripped)
    if inline_match:
        return f"{inline_match.group('lemma').title()} {inline_match.group('num').upper()}"
    ordinal_match = ORDINAL_MARKER_RE.match(stripped)
    if ordinal_match:
        label = ordinal_match.group("label")
        parts = label.split(maxsplit=1)
        return f"{parts[0].title()} {parts[1].lower()}"
    return None


def marker_sort_value(label: str) -> int | None:
    parts = label.lower().split()
    if not parts:
        return None
    token = parts[-1]
    if token.isdigit():
        return int(token)
    if token in ROMAN_TO_INT:
        return ROMAN_TO_INT[token]
    if token in LETTER_TO_INT:
        return LETTER_TO_INT[token]
    if parts[0] in ORDINAL_TO_INT:
        return ORDINAL_TO_INT[parts[0]]
    return None


def unique_markers(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    seen_values: set[int] = set()
    for index, line in enumerate(lines):
        label = parse_case_marker(line["text"])
        if not label:
            continue
        value = marker_sort_value(label)
        if value is None or value in seen_values:
            continue
        seen_values.add(value)
        markers.append(
            {
                "label": label,
                "value": value,
                "start_index": index,
                "page_index": line["page_index"],
                "line_text": line["text"],
            }
        )
    return markers


def markers_are_sequential(markers: list[dict[str, Any]]) -> bool:
    if not markers:
        return False
    values = [int(marker["value"]) for marker in markers]
    expected = list(range(values[0], values[0] + len(values)))
    return values == expected


def first_marker_is_first_case(markers: list[dict[str, Any]]) -> bool:
    if not markers:
        return False
    return int(markers[0]["value"]) == 1


def find_stop_heading_index(
    lines: list[dict[str, Any]],
    *,
    start_index: int,
    default_end_index: int,
) -> int:
    for offset in range(start_index + 1, default_end_index):
        if STOP_HEADING_RE.match(lines[offset]["text"]):
            return offset
    return default_end_index


def infer_stage06_artefact_paths(row: dict[str, str], paper_id: str) -> dict[str, str]:
    artefact_paths: dict[str, str] = {}
    candidate_path = (row.get("count_candidate_json_path") or "").strip()
    evidence_path = (row.get("count_evidence_json_path") or "").strip()
    if candidate_path:
        artefact_paths["count_candidate_json_path"] = candidate_path
    if evidence_path:
        artefact_paths["count_evidence_json_path"] = evidence_path

    anchor_path = repo_path_from_relative(candidate_path or evidence_path)
    if anchor_path is None:
        return artefact_paths

    run_root = anchor_path.parent.parent
    decision_path = run_root / "count_decisions" / f"{paper_id}.json"
    local_result_path = run_root / "local_model_results" / f"{paper_id}.json"
    if decision_path.exists():
        artefact_paths["count_decision_json_path"] = relative_to_repo(decision_path)
    if local_result_path.exists():
        artefact_paths["local_result_json_path"] = relative_to_repo(local_result_path)
    return artefact_paths


def load_optional_json(relative_path: str) -> dict[str, Any]:
    path = repo_path_from_relative(relative_path)
    if path is None or not path.exists():
        return {}
    return load_json(path)


def stage06_granularity(local_result_payload: dict[str, Any]) -> tuple[str, bool]:
    parsed_output = local_result_payload.get("parsed_output") or {}
    granularity = str(parsed_output.get("data_granularity") or "").strip()
    return granularity, bool(granularity)


def build_stage06_prior(paper_id: str, row: dict[str, str]) -> dict[str, Any]:
    final_count_text = (row.get("likely_sps_case_count") or "").strip()
    final_count = int(final_count_text) if final_count_text.isdigit() else None
    prior: dict[str, Any] = {
        "preferred_text_json_path": (row.get("preferred_text_json_path") or "").strip(),
        "final_count": final_count,
        "count_confidence": (row.get("count_confidence") or "").strip(),
        "count_basis": (row.get("count_basis") or "").strip(),
        "manual_review_required": truthy(row.get("count_manual_review_required") or ""),
        "count_verification_status": (row.get("count_verification_status") or "").strip(),
        "original_cohort_provenance_uncertain": truthy(
            row.get("count_original_cohort_provenance_uncertain") or ""
        ),
    }
    artefact_paths = infer_stage06_artefact_paths(row, paper_id)
    if artefact_paths:
        prior["artefact_paths"] = artefact_paths
        local_result_payload = load_optional_json(artefact_paths.get("local_result_json_path", ""))
        granularity, has_granularity = stage06_granularity(local_result_payload)
        if has_granularity:
            prior["granularity"] = granularity
            prior["granularity_source"] = "stage06_local_model_results"
            prior["granularity_is_provisional"] = True
        candidate_payload = load_optional_json(artefact_paths.get("count_candidate_json_path", ""))
        explicit_subgroup_count = candidate_payload.get("explicit_sps_subgroup_count")
        explicit_subgroup_basis = str(candidate_payload.get("explicit_sps_subgroup_basis") or "").strip()
        if explicit_subgroup_count is not None:
            prior["explicit_sps_subgroup_count"] = explicit_subgroup_count
        if explicit_subgroup_basis:
            prior["explicit_sps_subgroup_basis"] = explicit_subgroup_basis
    return prior


def build_source_route(
    *,
    resolved_source: dict[str, str],
    source_row: dict[str, str],
) -> dict[str, Any]:
    return {
        "resolved_source_category": resolved_source.get("resolved_source_category") or "",
        "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
        "resolved_source_route_source": resolved_source.get("resolved_source_route_source") or "",
        "contains_individual_level_data": truthy(source_row.get("contains_individual_level_data") or ""),
        "contains_group_level_data": truthy(source_row.get("contains_group_level_data") or ""),
        "preferred_langextract_mode": (source_row.get("preferred_langextract_mode") or "").strip(),
        "recommended_next_action": (source_row.get("recommended_next_action") or "").strip(),
    }


def line_payload_for_adjudication(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "global_index": int(line["global_index"]),
            "page_index": int(line["page_index"]),
            "line_index": int(line["line_index"]),
            "text": str(line["text"]),
        }
        for line in lines
    ]


def span_sort_key(span: Stage07LineSpan) -> tuple[int, int]:
    return (span.start_global_index, span.end_global_index)


def materialise_span_lines(
    *,
    lines_by_global_index: dict[int, dict[str, Any]],
    spans: list[Stage07LineSpan],
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    for span in sorted(spans, key=span_sort_key):
        if span.end_global_index < span.start_global_index:
            raise ValueError(
                f"Invalid adjudicated span {span.start_global_index}-{span.end_global_index}: end before start."
            )
        for global_index in range(span.start_global_index, span.end_global_index + 1):
            line = lines_by_global_index.get(global_index)
            if line is None:
                raise ValueError(f"Adjudicated span references unknown line index {global_index}.")
            if global_index in seen_indices:
                continue
            collected.append(line)
            seen_indices.add(global_index)
    return collected


def unit_span_summary(unit: dict[str, Any]) -> dict[str, Any]:
    line_indices = [int(index) for index in unit.get("_line_indices", [])]
    if not line_indices:
        return {
            "unit_label": unit["unit_label"],
            "unit_type": unit["unit_type"],
            "line_spans": [],
        }
    ordered_indices = sorted(line_indices)
    spans: list[dict[str, int]] = []
    start_index = ordered_indices[0]
    end_index = ordered_indices[0]
    for line_index in ordered_indices[1:]:
        if line_index == end_index + 1:
            end_index = line_index
            continue
        spans.append({"start_global_index": start_index, "end_global_index": end_index})
        start_index = line_index
        end_index = line_index
    spans.append({"start_global_index": start_index, "end_global_index": end_index})
    summary = {
        "unit_label": unit["unit_label"],
        "unit_type": unit["unit_type"],
        "line_spans": spans,
    }
    if unit["unit_type"] == "group":
        summary["group_name"] = unit.get("group_name") or unit["unit_label"]
        summary["group_size"] = unit.get("group_size")
    return summary


def build_adjudication_user_message(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    source_route: dict[str, Any],
    stage06_prior: dict[str, Any],
    heuristic_individual_units: list[dict[str, Any]],
    heuristic_group_units: list[dict[str, Any]],
    heuristic_status: str,
    heuristic_reason_code: str,
    heuristic_reason: str,
) -> str:
    prompt_payload = {
        "paper_id": paper_id,
        "goal": "Produce attribution-safe stage-07 units for downstream LangExtract processing.",
        "source_route": source_route,
        "stage06_prior": stage06_prior,
        "heuristic_split_summary": {
            "status": heuristic_status,
            "reason_code": heuristic_reason_code,
            "reason": heuristic_reason,
            "individual_units": [unit_span_summary(unit) for unit in heuristic_individual_units],
            "group_units": [unit_span_summary(unit) for unit in heuristic_group_units],
        },
        "article_lines": line_payload_for_adjudication(lines),
        "output_expectation": {
            "decision_type_allowed_values": ["publish_units", "manual_review_required", "unable_to_determine"],
            "unit_type_allowed_values": ["individual", "group"],
            "shared_context_rule": "Use shared_context_blocks only for statements that clearly apply to a bounded known set of units.",
        },
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def adjudicate_stage07_units(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    source_route: dict[str, Any],
    stage06_prior: dict[str, Any],
    heuristic_individual_units: list[dict[str, Any]],
    heuristic_group_units: list[dict[str, Any]],
    heuristic_status: str,
    heuristic_reason_code: str,
    heuristic_reason: str,
    model: str,
    api_key: str | None = None,
    max_output_tokens: int = DEFAULT_ADJUDICATION_MAX_OUTPUT_TOKENS,
) -> tuple[Stage07AdjudicationOutput, str]:
    if OpenAI is None:
        raise RuntimeError(
            "Stage 07 adjudication cannot run because the openai package is not installed."
        )
    client = OpenAI(api_key=resolve_openai_api_key(api_key))
    user_message = build_adjudication_user_message(
        paper_id=paper_id,
        lines=lines,
        source_route=source_route,
        stage06_prior=stage06_prior,
        heuristic_individual_units=heuristic_individual_units,
        heuristic_group_units=heuristic_group_units,
        heuristic_status=heuristic_status,
        heuristic_reason_code=heuristic_reason_code,
        heuristic_reason=heuristic_reason,
    )
    response = client.responses.parse(
        model=model,
        temperature=0,
        max_output_tokens=max_output_tokens,
        instructions=STAGE07_ADJUDICATION_SYSTEM_PROMPT,
        input=[{"role": "user", "content": user_message}],
        text_format=Stage07AdjudicationOutput,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise ValueError(
            f"Structured adjudication parsing returned None for paper {paper_id}. "
            f"Output text: {response.output_text!r}"
        )
    model_id = response.model or model
    return parsed, model_id


def renumber_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for order, unit in enumerate(
        sorted(
            units,
            key=lambda item: (
                min(item.get("_line_indices", [10**9])),
                0 if item["unit_type"] == "individual" else 1,
                item["unit_label"].lower(),
            ),
        ),
        start=1,
    ):
        unit["unit_order"] = order
    return units


def build_units_from_adjudication(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    stage06_prior: dict[str, Any],
    adjudication: Stage07AdjudicationOutput,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines_by_global_index = {int(line["global_index"]): line for line in lines}
    units: list[dict[str, Any]] = []
    primary_occupied: set[int] = set()
    type_counters = {"individual": 0, "group": 0}
    seen_labels: set[str] = set()

    for proposed_unit in adjudication.units:
        unit_label = " ".join(proposed_unit.unit_label.split()).strip()
        if not unit_label:
            raise ValueError("Adjudicated unit label is blank.")
        if unit_label in seen_labels:
            raise ValueError(f"Duplicate adjudicated unit label: {unit_label}")
        selected_lines = [
            line
            for line in materialise_span_lines(
                lines_by_global_index=lines_by_global_index,
                spans=proposed_unit.line_spans,
            )
            if not ignorable_noise_line(line["text"])
        ]
        if not selected_lines:
            raise ValueError(f"Adjudicated unit {unit_label} contains no usable text lines.")
        line_indices = [int(line["global_index"]) for line in selected_lines]
        overlap = primary_occupied.intersection(line_indices)
        if overlap:
            raise ValueError(
                f"Adjudicated unit {unit_label} overlaps existing unit spans at indices {sorted(overlap)!r}."
            )
        unit_text = render_lines(selected_lines)
        if len(unit_text) < MIN_ADJUDICATED_UNIT_TEXT_LENGTH:
            raise ValueError(
                f"Adjudicated unit {unit_label} is too short after filtering ({len(unit_text)} chars)."
            )
        primary_occupied.update(line_indices)
        type_counters[proposed_unit.unit_type] += 1
        unit_id = f"{paper_id}__{proposed_unit.unit_type}__{type_counters[proposed_unit.unit_type]:03d}"
        unit_payload: dict[str, Any] = {
            "unit_id": unit_id,
            "unit_order": 0,
            "unit_type": proposed_unit.unit_type,
            "unit_label": unit_label,
            "source_mode": "mixed_evidence" if len(proposed_unit.line_spans) > 1 else (
                "group_summary_block" if proposed_unit.unit_type == "group" else "narrative_block"
            ),
            "unit_text": unit_text,
            "source_span_refs": build_line_range_refs(selected_lines, role="primary"),
            "linked_shared_context_ids": [],
            "stage06_unit_prior": {
                "expected_unit_type": proposed_unit.unit_type,
                "paper_level_granularity": stage06_prior.get("granularity") or "",
            },
            "_line_indices": line_indices,
            "_adjudication_evidence_summary": proposed_unit.evidence_summary,
        }
        if proposed_unit.unit_type == "group":
            if proposed_unit.group_size is None:
                raise ValueError(f"Adjudicated group unit {unit_label} is missing group_size.")
            unit_payload["group_name"] = (proposed_unit.group_name or unit_label).strip()
            unit_payload["group_size"] = proposed_unit.group_size
        units.append(unit_payload)
        seen_labels.add(unit_label)

    shared_context_blocks: list[dict[str, Any]] = []
    unit_lookup = {unit["unit_label"]: unit for unit in units}
    shared_occupied: set[int] = set()
    for offset, proposed_block in enumerate(adjudication.shared_context_blocks, start=1):
        missing_labels = [
            label for label in proposed_block.applies_to_unit_labels if " ".join(label.split()).strip() not in unit_lookup
        ]
        if missing_labels:
            raise ValueError(
                "Adjudicated shared-context block references unknown unit labels: "
                + ", ".join(sorted(missing_labels))
            )
        selected_lines = [
            line
            for line in materialise_span_lines(
                lines_by_global_index=lines_by_global_index,
                spans=proposed_block.line_spans,
            )
            if not ignorable_noise_line(line["text"])
        ]
        if not selected_lines:
            raise ValueError(
                f"Adjudicated shared-context block {proposed_block.context_label!r} contains no usable text lines."
            )
        line_indices = [int(line["global_index"]) for line in selected_lines]
        primary_overlap = primary_occupied.intersection(line_indices)
        if primary_overlap:
            raise ValueError(
                "Adjudicated shared-context block overlaps unit primary spans at indices "
                f"{sorted(primary_overlap)!r}."
            )
        duplicate_overlap = shared_occupied.intersection(line_indices)
        if duplicate_overlap:
            raise ValueError(
                "Adjudicated shared-context blocks overlap each other at indices "
                f"{sorted(duplicate_overlap)!r}."
            )
        shared_occupied.update(line_indices)
        context_id = f"{paper_id}__shared__{offset:03d}"
        applies_to_unit_ids = [
            unit_lookup[" ".join(label.split()).strip()]["unit_id"] for label in proposed_block.applies_to_unit_labels
        ]
        shared_context_blocks.append(
            {
                "context_id": context_id,
                "context_type": "shared_context",
                "text": render_lines(selected_lines),
                "applies_to_unit_ids": applies_to_unit_ids,
                "source_span_refs": build_line_range_refs(selected_lines, role="supporting_context"),
                "attribution_status": "bounded_multi_unit",
                "_line_indices": line_indices,
                "_adjudication_context_label": proposed_block.context_label,
                "_adjudication_evidence_summary": proposed_block.evidence_summary,
            }
        )
        for unit_id in applies_to_unit_ids:
            for unit in units:
                if unit["unit_id"] == unit_id and context_id not in unit["linked_shared_context_ids"]:
                    unit["linked_shared_context_ids"].append(context_id)

    return renumber_units(units), shared_context_blocks


def build_stage07_resolution(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    stage06_prior: dict[str, Any],
    source_route: dict[str, Any],
    units: list[dict[str, Any]],
    manual_review_reason: str = "",
    shared_context_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    individual_units = [unit for unit in units if unit["unit_type"] == "individual"]
    group_units = [unit for unit in units if unit["unit_type"] == "group"]
    status, reason_code, reason, manual_review_required, diverged = publication_decision(
        stage06_prior=stage06_prior,
        source_route=source_route,
        individual_units=individual_units,
        group_units=group_units,
    )
    if status == "manual_review_required" and manual_review_reason:
        reason = manual_review_reason
    published_units = units if status != "manual_review_required" else []
    if status == "manual_review_required":
        resolution_shared_context: list[dict[str, Any]] = []
    else:
        resolution_shared_context = (
            build_shared_context_blocks(paper_id=paper_id, lines=lines, units=published_units)
            if shared_context_blocks is None
            else shared_context_blocks
        )
    unresolved_remainder = build_unresolved_remainder(
        lines=lines,
        units=published_units,
        shared_context_blocks=resolution_shared_context,
        publication_status=status,
        reason_code=reason_code,
        reason=reason,
    )
    if status == "publish_all_units" and unresolved_remainder["present"]:
        status = "partial_publish_with_unresolved_remainder"
        manual_review_required = True
    clean_units = clean_units_for_output(published_units)
    clean_shared_context = clean_shared_context_blocks(resolution_shared_context)
    resolution_summary = {
        "published_unit_count": len(clean_units),
        "published_individual_count": sum(1 for unit in clean_units if unit["unit_type"] == "individual"),
        "published_group_count": sum(1 for unit in clean_units if unit["unit_type"] == "group"),
        "shared_context_count": len(clean_shared_context),
        "has_unresolved_remainder": bool(unresolved_remainder["present"]),
    }
    return {
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "manual_review_required": manual_review_required,
        "diverged": diverged,
        "clean_units": clean_units,
        "clean_shared_context": clean_shared_context,
        "unresolved_remainder": unresolved_remainder,
        "resolution_summary": resolution_summary,
    }


def resolution_rank(resolution: dict[str, Any]) -> tuple[int, int, int, int]:
    status_rank = {
        "manual_review_required": 0,
        "partial_publish_with_unresolved_remainder": 1,
        "publish_all_units": 2,
    }
    summary = resolution["resolution_summary"]
    return (
        status_rank.get(str(resolution["status"]), 0),
        int(summary["published_unit_count"]),
        int(summary["published_group_count"]) + int(summary["published_individual_count"]),
        -int(bool(summary["has_unresolved_remainder"])),
    )


def build_individual_units(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    stage06_prior: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    markers = unique_markers(lines)
    if len(markers) < 2:
        return [], "Could not find at least two distinct explicit case or patient headings."
    if not markers_are_sequential(markers):
        return [], "Case or patient headings were found, but the numbering was not sequential."
    if not first_marker_is_first_case(markers):
        return [], "Case headings do not begin with the first case, so the leading case block is not safely isolated."

    units: list[dict[str, Any]] = []
    for offset, marker in enumerate(markers):
        default_end = markers[offset + 1]["start_index"] if offset + 1 < len(markers) else len(lines)
        end_index = find_stop_heading_index(
            lines,
            start_index=marker["start_index"],
            default_end_index=default_end,
        )
        segment_lines = [
            line
            for line in lines[marker["start_index"] : end_index]
            if not ignorable_noise_line(line["text"])
        ]
        unit_text = render_lines(segment_lines)
        if len(unit_text) < 160:
            continue
        unit_order = len(units) + 1
        units.append(
            {
                "unit_id": f"{paper_id}__individual__{unit_order:03d}",
                "unit_order": unit_order,
                "unit_type": "individual",
                "unit_label": marker["label"],
                "source_mode": "narrative_block",
                "unit_text": unit_text,
                "source_span_refs": build_line_range_refs(segment_lines, role="primary"),
                "linked_shared_context_ids": [],
                "stage06_unit_prior": {
                    "expected_unit_type": "individual",
                    "paper_level_granularity": stage06_prior.get("granularity") or "",
                },
                "_line_indices": [line["global_index"] for line in segment_lines],
            }
        )

    if len(units) < 2:
        return [], "Case headings were found, but the segmented case blocks were too short or unstable."
    return units, ""


def canonicalise_group_label(raw_label: str) -> str:
    lowered = raw_label.lower().replace("  ", " ").strip()
    lowered = lowered.replace("positive", "positive").replace("_", " ")
    if lowered.startswith("anti "):
        lowered = lowered.replace("anti ", "anti-")
    if lowered.startswith("anti-") and not lowered.endswith("group"):
        return f"{lowered} group"
    if lowered == "perm":
        return "perm group"
    if lowered == "stiff person syndrome":
        return "sps group"
    return f"{lowered} group"


def build_group_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for line in lines:
        text = line["text"]
        for pattern in (SPS_SUBGROUP_PAIR_RE, SPS_SUBGROUP_SUFFIX_RE, ANTIBODY_PREFIX_RE, ANTIBODY_SUFFIX_RE):
            for match in pattern.finditer(text):
                count = parse_count_token(match.group("count"))
                raw_label = str(match.group("diagnosis") if "diagnosis" in match.groupdict() else match.group("label"))
                if count is None or count <= 0:
                    continue
                label = canonicalise_group_label(raw_label)
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                candidates.append(
                    {
                        "unit_label": label,
                        "group_size": count,
                        "text": text,
                        "line_indices": [line["global_index"]],
                        "source_span_refs": build_line_range_refs([line], role="primary"),
                    }
                )
    return candidates


def build_group_units(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    stage06_prior: dict[str, Any],
    source_route: dict[str, Any],
) -> list[dict[str, Any]]:
    should_attempt = bool(
        source_route.get("contains_group_level_data")
        or stage06_prior.get("granularity") in {"group-level", "both", "group", "both-level"}
        or stage06_prior.get("explicit_sps_subgroup_count")
    )
    if not should_attempt:
        return []

    candidates = build_group_candidates(lines)
    units: list[dict[str, Any]] = []
    for offset, candidate in enumerate(candidates, start=1):
        units.append(
            {
                "unit_id": f"{paper_id}__group__{offset:03d}",
                "unit_order": offset,
                "unit_type": "group",
                "unit_label": candidate["unit_label"],
                "group_name": candidate["unit_label"],
                "group_size": candidate["group_size"],
                "source_mode": "group_summary_block",
                "unit_text": candidate["text"],
                "source_span_refs": candidate["source_span_refs"],
                "linked_shared_context_ids": [],
                "stage06_unit_prior": {
                    "expected_unit_type": "group",
                    "paper_level_granularity": stage06_prior.get("granularity") or "",
                },
                "_line_indices": candidate["line_indices"],
            }
        )
    return units


def bounded_shared_context_count(block_text: str) -> int | None:
    match = BOUNDED_SHARED_CONTEXT_RE.search(block_text)
    if not match:
        return None
    token = match.group("count").lower()
    if token == "both":
        return 2
    return parse_count_token(token)


def build_shared_context_blocks(
    *,
    paper_id: str,
    lines: list[dict[str, Any]],
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not units or any(unit["unit_type"] != "individual" for unit in units):
        return []
    occupied = {index for unit in units for index in unit.get("_line_indices", [])}
    candidate_lines = [
        line
        for line in lines
        if line["global_index"] not in occupied and not ignorable_noise_line(line["text"])
    ]
    blocks: list[dict[str, Any]] = []
    for line in candidate_lines:
        bounded_count = bounded_shared_context_count(line["text"])
        if bounded_count != len(units):
            continue
        context_order = len(blocks) + 1
        context_id = f"{paper_id}__shared__{context_order:03d}"
        blocks.append(
            {
                "context_id": context_id,
                "context_type": "shared_context",
                "text": line["text"],
                "applies_to_unit_ids": [unit["unit_id"] for unit in units],
                "source_span_refs": build_line_range_refs([line], role="supporting_context"),
                "attribution_status": "bounded_multi_unit",
                "_line_indices": [line["global_index"]],
            }
        )
    if not blocks:
        return []
    for unit in units:
        unit["linked_shared_context_ids"] = [block["context_id"] for block in blocks]
    return blocks


def build_unresolved_remainder(
    *,
    lines: list[dict[str, Any]],
    units: list[dict[str, Any]],
    shared_context_blocks: list[dict[str, Any]],
    publication_status: str,
    reason_code: str,
    reason: str,
) -> dict[str, Any]:
    occupied = {index for unit in units for index in unit.get("_line_indices", [])}
    occupied |= {index for block in shared_context_blocks for index in block.get("_line_indices", [])}
    if not units:
        unresolved_lines = lines
    else:
        scope_start = min(index for unit in units for index in unit.get("_line_indices", []))
        scope_end = max(index for unit in units for index in unit.get("_line_indices", [])) + 1
        scope_end = find_stop_heading_index(
            lines,
            start_index=scope_end - 1,
            default_end_index=len(lines),
        )
        unresolved_lines = [
            line
            for line in lines[scope_start:scope_end]
            if line["global_index"] not in occupied
            and not STOP_HEADING_RE.match(line["text"])
            and not ignorable_noise_line(line["text"])
        ]
    if publication_status == "manual_review_required" and not unresolved_lines:
        unresolved_lines = lines
    if not unresolved_lines:
        return {
            "present": False,
            "reason_code": "",
            "reason": "",
            "source_span_refs": [],
            "text": "",
        }
    return {
        "present": True,
        "reason_code": reason_code,
        "reason": reason,
        "source_span_refs": build_line_range_refs(unresolved_lines, role="supporting_context"),
        "text": render_lines(unresolved_lines),
    }


def publication_decision(
    *,
    stage06_prior: dict[str, Any],
    source_route: dict[str, Any],
    individual_units: list[dict[str, Any]],
    group_units: list[dict[str, Any]],
) -> tuple[str, str, str, bool, bool]:
    stage06_final_count = stage06_prior.get("final_count")
    count_confidence = str(stage06_prior.get("count_confidence") or "").strip().lower()
    granularity = str(stage06_prior.get("granularity") or "").strip().lower()
    has_individuals = bool(individual_units)
    has_groups = bool(group_units)
    diverged = False

    if has_individuals and not has_groups:
        published_individual_count = len(individual_units)
        if stage06_final_count in {None, 0}:
            return (
                "publish_all_units",
                "individual_units_no_stage06_count",
                "Explicit individual unit headings supported a stable patient-level split.",
                False,
                diverged,
            )
        if published_individual_count == stage06_final_count:
            return (
                "publish_all_units",
                "individual_units_match_stage06_count",
                "Explicit individual unit headings matched the stage-06 patient-count prior.",
                False,
                diverged,
            )
        if count_confidence == "low":
            diverged = True
            return (
                "publish_all_units",
                "individual_units_override_low_confidence_stage06_count",
                "Explicit individual unit headings overrode a low-confidence stage-06 count prior.",
                False,
                diverged,
            )
        return (
            "manual_review_required",
            "individual_unit_count_mismatch",
            "Explicit individual unit headings were found, but the published unit count did not match the trusted stage-06 count prior.",
            True,
            diverged,
        )

    if has_groups and not has_individuals:
        if granularity in {"group-level", "group"} or (
            source_route.get("contains_group_level_data") and not source_route.get("contains_individual_level_data")
        ):
            return (
                "publish_all_units",
                "group_units_match_group_routing",
                "Explicit subgroup statements supported a stable group-level split.",
                False,
                diverged,
            )
        if count_confidence == "low":
            diverged = True
            return (
                "publish_all_units",
                "group_units_override_low_confidence_stage06_prior",
                "Explicit subgroup statements overrode a low-confidence stage-06 prior.",
                False,
                diverged,
            )
        return (
            "manual_review_required",
            "group_structure_unclear",
            "Group-level evidence was detected, but the stage-06 prior did not support safe automatic group publication.",
            True,
            diverged,
        )

    if has_individuals and has_groups:
        if granularity == "both":
            return (
                "publish_all_units",
                "mixed_units_match_stage06_both",
                "Explicit individual and group units were both detected and matched the stage-06 mixed-granularity prior.",
                False,
                diverged,
            )
        return (
            "manual_review_required",
            "mixed_units_without_clear_both_prior",
            "Both individual and group units were detected, but the paper needs review before mixed publication.",
            True,
            diverged,
        )

    return (
        "manual_review_required",
        "no_stable_units_found",
        "Stage 07 could not isolate attribution-safe units from the current source text.",
        True,
        diverged,
    )


def stage06_divergence_payload(
    *,
    stage06_prior: dict[str, Any],
    stage07_resolution_summary: dict[str, Any],
    publication_reason: str,
) -> dict[str, Any]:
    return {
        "diverged": True,
        "dimensions": ["count"],
        "stage06_summary": {
            "final_count": stage06_prior.get("final_count"),
            "count_confidence": stage06_prior.get("count_confidence") or "",
            "granularity": stage06_prior.get("granularity") or "",
            "count_verification_status": stage06_prior.get("count_verification_status") or "",
        },
        "stage07_summary": {
            "published_unit_count": stage07_resolution_summary.get("published_unit_count"),
            "published_individual_count": stage07_resolution_summary.get("published_individual_count"),
            "published_group_count": stage07_resolution_summary.get("published_group_count"),
        },
        "reason": publication_reason,
        "review_status": "stage07_override_low_confidence_prior",
    }


def clean_units_for_output(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for unit in units:
        cleaned_unit = {key: value for key, value in unit.items() if not key.startswith("_")}
        cleaned.append(cleaned_unit)
    return cleaned


def clean_shared_context_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for block in blocks:
        cleaned.append({key: value for key, value in block.items() if not key.startswith("_")})
    return cleaned


def build_input_blocks(
    unit: dict[str, Any],
    shared_context_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocks = [
        {
            "block_order": 1,
            "block_role": "primary_unit_text",
            "source_object_id": unit["unit_id"],
            "text": unit["unit_text"],
            "source_span_refs": unit["source_span_refs"],
        }
    ]
    block_order = 2
    linked_context_ids = set(unit.get("linked_shared_context_ids") or [])
    for block in shared_context_blocks:
        if block["context_id"] not in linked_context_ids:
            continue
        blocks.append(
            {
                "block_order": block_order,
                "block_role": "shared_context",
                "source_object_id": block["context_id"],
                "text": block["text"],
                "source_span_refs": block["source_span_refs"],
            }
        )
        block_order += 1
    return blocks


def derive_manifest_records(
    *,
    manifest_run_id: str,
    paper_json_path: Path,
    paper_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    shared_context_by_id = {
        block["context_id"]: block for block in paper_payload.get("shared_context_blocks") or []
    }
    records: list[dict[str, Any]] = []
    for unit in paper_payload.get("units") or []:
        shared_blocks = [
            shared_context_by_id[context_id]
            for context_id in unit.get("linked_shared_context_ids") or []
            if context_id in shared_context_by_id
        ]
        input_blocks = build_input_blocks(unit, shared_blocks)
        langextract_input_text = "\n\n".join(block["text"] for block in input_blocks if block["text"]).strip()
        record = {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "manifest_run_id": manifest_run_id,
            "paper_id": paper_payload["paper_id"],
            "stage07_paper_json_path": relative_to_repo(paper_json_path),
            "source_text_json_path": paper_payload["source_text_json_path"],
            "source_route": paper_payload["source_route"],
            "paper_publication_status": paper_payload["publication_decision"]["status"],
            "unit_id": unit["unit_id"],
            "unit_order": unit["unit_order"],
            "unit_type": unit["unit_type"],
            "unit_label": unit["unit_label"],
            "prompt_mode": "individual" if unit["unit_type"] == "individual" else "group",
            "input_blocks": input_blocks,
            "langextract_input_text": langextract_input_text,
            "unit_text": unit["unit_text"],
            "linked_shared_context_ids": unit.get("linked_shared_context_ids") or [],
            "shared_context_blocks": shared_blocks,
            "source_span_refs": unit["source_span_refs"],
            "stage06_prior": paper_payload["stage06_prior"],
        }
        if "group_name" in unit:
            record["group_name"] = unit["group_name"]
        if "group_size" in unit:
            record["group_size"] = unit["group_size"]
        if "stage06_divergence" in paper_payload:
            record["stage06_divergence"] = paper_payload["stage06_divergence"]
        records.append(record)
    return records


def build_registry_row(
    *,
    paper_id: str,
    resolved_source: dict[str, str],
    source_text_json_path: str,
    paper_json_path: Path,
    used_preferred_text: bool,
    paper_payload: dict[str, Any],
    manifest_run_id: str,
) -> dict[str, str]:
    units = paper_payload.get("units") or []
    first_pages = []
    last_pages = []
    for unit in units:
        refs = unit.get("source_span_refs") or []
        if refs:
            first_pages.append(str(refs[0].get("page_index", "")))
            last_pages.append(str(refs[-1].get("page_index", "")))
    publication_decision_payload = paper_payload["publication_decision"]
    summary = paper_payload["stage07_resolution_summary"]
    stage06_prior = paper_payload["stage06_prior"]
    split_status = "split_auto" if publication_decision_payload["status"] != "manual_review_required" else "manual_review_required"
    return {
        "paper_id": paper_id,
        "resolved_source_category": resolved_source.get("resolved_source_category") or "",
        "resolved_source_subtype": resolved_source.get("resolved_source_subtype") or "",
        "resolved_source_route_source": resolved_source.get("resolved_source_route_source") or "",
        "source_text_json_path": source_text_json_path,
        "split_text_json_path": relative_to_repo(paper_json_path),
        "used_trimmed_text": bool_text(used_preferred_text),
        "split_status": split_status,
        "split_reason": publication_decision_payload["reason"],
        "split_method": paper_payload["stage07_method"]["candidate_generation_mode"],
        "case_count": str(summary["published_unit_count"]),
        "case_labels": " | ".join(unit["unit_label"] for unit in units),
        "start_page_indices": " | ".join(first_pages),
        "end_page_indices": " | ".join(last_pages),
        "manual_review_required": bool_text(publication_decision_payload["manual_review_required"]),
        "split_at_utc": paper_payload["stage07_method"]["generated_at_utc"],
        "publication_status": publication_decision_payload["status"],
        "publication_reason_code": publication_decision_payload["reason_code"],
        "published_unit_count": str(summary["published_unit_count"]),
        "published_individual_count": str(summary["published_individual_count"]),
        "published_group_count": str(summary["published_group_count"]),
        "shared_context_count": str(summary["shared_context_count"]),
        "has_unresolved_remainder": bool_text(summary["has_unresolved_remainder"]),
        "stage06_preferred_text_json_path": stage06_prior.get("preferred_text_json_path") or "",
        "stage06_final_count": "" if stage06_prior.get("final_count") is None else str(stage06_prior["final_count"]),
        "stage06_count_confidence": stage06_prior.get("count_confidence") or "",
        "stage06_count_verification_status": stage06_prior.get("count_verification_status") or "",
        "stage06_granularity": stage06_prior.get("granularity") or "",
        "stage06_granularity_is_provisional": bool_text(bool(stage06_prior.get("granularity_is_provisional"))),
        "stage06_diverged": bool_text("stage06_divergence" in paper_payload),
        "manifest_run_id": manifest_run_id,
    }


def process_paper(
    *,
    paper_id: str,
    source_row: dict[str, str],
    manual_row: dict[str, str],
    stage06_row: dict[str, str],
    paper_output_dir: Path,
    manifest_run_id: str,
    candidate_generation_mode: str,
    adjudication_model: str,
    adjudication_api_key: str | None = None,
) -> Stage07ProcessResult:
    resolved_source = resolve_source_row(
        paper_id=paper_id,
        heuristic_row=source_row,
        manual_row=manual_row,
    )
    stage06_prior = build_stage06_prior(paper_id, stage06_row)
    source_route = build_source_route(
        resolved_source=resolved_source,
        source_row=source_row,
    )
    preferred_text_path = repo_path_from_relative(stage06_prior.get("preferred_text_json_path") or "")
    if preferred_text_path is None or not preferred_text_path.exists():
        preferred_text_path = repo_path_from_relative(source_row.get("preferred_text_json_path") or "")
    if preferred_text_path is None or not preferred_text_path.exists():
        preferred_text_path = TEXT_DIR / f"{paper_id}.json"
    if not preferred_text_path.exists():
        raise FileNotFoundError(f"Preferred text JSON missing for paper {paper_id}: {preferred_text_path}")

    record = load_json(preferred_text_path)
    reference_row = reference_row_for_paper(paper_id)
    lines = restrict_to_article_window(
        flatten_lines(record),
        reference_row=reference_row,
    )
    source_text_json_path = relative_to_repo(preferred_text_path)
    used_preferred_text = source_text_json_path != relative_to_repo(TEXT_DIR / f"{paper_id}.json")

    individual_units, individual_reason = build_individual_units(
        paper_id=paper_id,
        lines=lines,
        stage06_prior=stage06_prior,
    )
    group_units = build_group_units(
        paper_id=paper_id,
        lines=lines,
        stage06_prior=stage06_prior,
        source_route=source_route,
    )
    heuristic_resolution = build_stage07_resolution(
        paper_id=paper_id,
        lines=lines,
        stage06_prior=stage06_prior,
        source_route=source_route,
        units=renumber_units(individual_units + group_units),
        manual_review_reason=individual_reason,
    )
    final_resolution = heuristic_resolution
    adjudication_trace: dict[str, Any] | None = None
    if adjudication_model != DEFAULT_ADJUDICATION_MODEL:
        try:
            adjudication_output, adjudication_model_id = adjudicate_stage07_units(
                paper_id=paper_id,
                lines=lines,
                source_route=source_route,
                stage06_prior=stage06_prior,
                heuristic_individual_units=individual_units,
                heuristic_group_units=group_units,
                heuristic_status=heuristic_resolution["status"],
                heuristic_reason_code=heuristic_resolution["reason_code"],
                heuristic_reason=heuristic_resolution["reason"],
                model=adjudication_model,
                api_key=adjudication_api_key,
            )
            adjudication_trace = {
                "requested_model": adjudication_model,
                "model_id": adjudication_model_id,
                "decision_type": adjudication_output.decision_type,
                "decision_summary": adjudication_output.decision_summary,
                "unresolved_remainder_reason": adjudication_output.unresolved_remainder_reason,
                "validation_status": "model_abstained",
            }
            if adjudication_output.decision_type == "publish_units":
                if not adjudication_output.units:
                    raise ValueError("Adjudication returned publish_units without any units.")
                adjudicated_units, adjudicated_shared_context = build_units_from_adjudication(
                    paper_id=paper_id,
                    lines=lines,
                    stage06_prior=stage06_prior,
                    adjudication=adjudication_output,
                )
                adjudicated_resolution = build_stage07_resolution(
                    paper_id=paper_id,
                    lines=lines,
                    stage06_prior=stage06_prior,
                    source_route=source_route,
                    units=adjudicated_units,
                    manual_review_reason=adjudication_output.decision_summary,
                    shared_context_blocks=adjudicated_shared_context,
                )
                adjudication_trace["adjudicated_resolution"] = {
                    "status": adjudicated_resolution["status"],
                    "reason_code": adjudicated_resolution["reason_code"],
                    "published_unit_count": adjudicated_resolution["resolution_summary"]["published_unit_count"],
                }
                if resolution_rank(adjudicated_resolution) > resolution_rank(heuristic_resolution):
                    final_resolution = adjudicated_resolution
                    adjudication_trace["validation_status"] = "selected"
                else:
                    adjudication_trace["validation_status"] = "valid_but_not_selected"
            else:
                adjudication_trace["validation_status"] = "model_abstained"
        except Exception as exc:
            if is_openai_dependency_error(exc):
                raise RuntimeError(
                    f"OpenAI adjudication failed for paper {paper_id}: {exc.__class__.__name__}: {exc}"
                ) from exc
            adjudication_trace = {
                "requested_model": adjudication_model,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                "validation_status": "error_fallback_to_heuristics",
            }

    generated_at_utc = now_utc_iso()
    paper_payload: dict[str, Any] = {
        "paper_id": paper_id,
        "stage07_schema_version": STAGE07_SCHEMA_VERSION,
        "source_text_json_path": source_text_json_path,
        "source_filename": record.get("source_filename") or "",
        "source_sha256": record.get("source_sha256") or "",
        "source_route": source_route,
        "stage06_prior": stage06_prior,
        "stage07_method": {
            "candidate_generation_mode": candidate_generation_mode,
            "adjudication_model": adjudication_model,
            "pipeline_entrypoint": PIPELINE_ENTRYPOINT,
            "generated_at_utc": generated_at_utc,
        },
        "stage07_resolution_summary": final_resolution["resolution_summary"],
        "publication_decision": {
            "status": final_resolution["status"],
            "manual_review_required": final_resolution["manual_review_required"],
            "reason_code": final_resolution["reason_code"],
            "reason": final_resolution["reason"],
        },
        "shared_context_blocks": final_resolution["clean_shared_context"],
        "units": final_resolution["clean_units"],
        "unresolved_remainder": final_resolution["unresolved_remainder"],
    }
    if adjudication_trace is not None:
        paper_payload["stage07_adjudication"] = adjudication_trace
    if final_resolution["diverged"]:
        paper_payload["stage06_divergence"] = stage06_divergence_payload(
            stage06_prior=stage06_prior,
            stage07_resolution_summary=final_resolution["resolution_summary"],
            publication_reason=final_resolution["reason"],
        )

    paper_json_path = paper_output_dir / f"{paper_id}.json"
    manifest_records = derive_manifest_records(
        manifest_run_id=manifest_run_id,
        paper_json_path=paper_json_path,
        paper_payload=paper_payload,
    )
    registry_row = build_registry_row(
        paper_id=paper_id,
        resolved_source=resolved_source,
        source_text_json_path=source_text_json_path,
        paper_json_path=paper_json_path,
        used_preferred_text=used_preferred_text,
        paper_payload=paper_payload,
        manifest_run_id=manifest_run_id,
    )
    return Stage07ProcessResult(
        paper_id=paper_id,
        paper_payload=paper_payload,
        manifest_records=manifest_records,
        registry_row=registry_row,
    )


def write_registry(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def collect_candidate_ids(
    *,
    source_rows: dict[str, dict[str, str]],
    paper_ids: list[str],
    limit: int,
) -> list[str]:
    wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
    def sort_key(item: tuple[str, dict[str, str]]) -> tuple[int, int | str]:
        paper_id = item[0]
        if paper_id.isdigit():
            return (0, int(paper_id))
        return (1, paper_id)

    candidate_ids = [
        paper_id
        for paper_id, row in sorted(source_rows.items(), key=sort_key)
        if (row.get("preferred_langextract_mode") or "").strip() == "individual_case_split"
    ]
    if wanted:
        candidate_ids = [paper_id for paper_id in candidate_ids if paper_id in wanted]
    if limit > 0:
        candidate_ids = candidate_ids[:limit]
    return candidate_ids


def load_stage07_inputs() -> tuple[
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
]:
    return (
        load_csv_rows_by_id(SOURCE_CATEGORISATION_PATH, "paper_id"),
        load_csv_rows_by_id(SOURCE_MANUAL_REVIEW_PATH, "paper_id"),
        load_csv_rows_by_id(SOURCE_CASE_COUNT_PATH, "paper_id"),
    )
