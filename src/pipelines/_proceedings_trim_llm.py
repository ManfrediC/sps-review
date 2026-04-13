from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from _proceedings_text import (
    LineRef,
    ProceedingsPattern,
    abstract_code,
    body_char_count,
    has_enough_body,
    header_boundary,
    is_author_like,
    is_disclosure_detail_line,
    is_footer_like,
    is_header_preamble_line,
    is_institution_like,
    is_potential_title_line,
    is_section_heading,
    is_trimmable_tail_metadata_line,
    normalize_text,
    strip_abstract_code,
)
from _proceedings_trim_core import AbstractBlock, REPO_ROOT, bool_text, now_utc_iso, relative_to_repo, title_cluster_score


TRIM_WORKFLOW_VERSION = "proceedings_llm_v1"
CANDIDATE_GENERATION_MODE = "strict_to_permissive_v1"
LLM_API_MODE = "responses_json_schema"
DEFAULT_PROMPT_VERSION = "proceedings_llm_trim_prompt_v1"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
END_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision_type": {
            "type": "string",
            "enum": ["candidate_exact", "line_within_overshoot", "unable_to_determine"],
        },
        "selected_candidate_id": {"type": ["string", "null"]},
        "last_abstract_line_number": {"type": ["integer", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "end_reason": {
            "type": "string",
            "enum": [
                "candidate_is_exact",
                "next_header_starts",
                "metadata_starts",
                "disclosure_starts",
                "correspondence_starts",
                "doi_tail",
                "other",
                "uncertain",
            ],
        },
        "explanation_short": {"type": "string"},
    },
    "required": [
        "decision_type",
        "selected_candidate_id",
        "last_abstract_line_number",
        "confidence",
        "end_reason",
        "explanation_short",
    ],
}

DOI_LINE_RE = re.compile(r"^\s*doi\s*[: ]", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
DOWNLOADED_FROM_RE = re.compile(r"\bdownloaded from\b", re.IGNORECASE)
PROCEEDINGS_PAGE_SECTION_RE = re.compile(
    r"^\s*(?:\d+\s+)?(?:short communications|poster session|abstracts?)\b",
    re.IGNORECASE,
)
CONTACT_PREFIX_RE = re.compile(
    r"^(?:contact|contacts|email|e-mail|correspondence|corresponding author)\b",
    re.IGNORECASE,
)
REFERENCE_HEADING_RE = re.compile(r"^\s*references?\s*:?\s*$", re.IGNORECASE)
REFERENCE_INLINE_START_RE = re.compile(r"^\s*references?\s*:\s*.+$", re.IGNORECASE)
REFERENCE_CITATION_START_RE = re.compile(r"^\s*(?:\[\d+\]|\d+\.)\s*")

HEURISTIC_PRIORITY = {
    "tail_metadata_trim_end": 4,
    "last_non_metadata_end": 3,
    "next_confirmed_header_end": 2,
    "current_selected_end": 1,
}
FALLBACK_HEURISTIC_ORDER = (
    "tail_metadata_trim_end",
    "current_selected_end",
    "next_confirmed_header_end",
)


@dataclass
class EndCandidate:
    candidate_id: str
    heuristic_name: str
    rank: int
    start_index: int
    end_index_exclusive: int
    start_page_index: int
    end_page_index: int
    n_lines: int
    body_char_count: int
    contains_next_confirmed_header: bool
    contains_soft_boundary: bool
    contains_tail_metadata: bool
    confidence_class: str
    rationale: str


@dataclass
class LLMDecision:
    decision_type: str
    selected_candidate_id: str | None
    last_abstract_line_global_index: int | None
    confidence: str
    end_reason: str
    explanation_short: str


@dataclass
class CandidatePackage:
    paper_id: str
    source_text_json_path: str
    reference_title: str
    reference_authors: str
    matched_start_index: int
    matched_start_page_index: int
    matched_block_code: str
    matched_block_title: str
    start_rule: str
    candidate_generation_mode: str
    candidates: list[EndCandidate]
    overshoot_candidate_id: str
    baseline_candidate_id: str
    proceedings_signals: dict[str, Any]
    upstream_match_metadata: dict[str, Any]
    trim_workflow_version: str = TRIM_WORKFLOW_VERSION
    trim_workflow_stage: str = "candidate_generation"
    llm_routing_recommended: bool = True
    llm_routing_reason: str = ""


def _document_end_index(lines: list[LineRef]) -> int:
    if not lines:
        return 0
    return lines[-1].global_index + 1


def _global_to_position(lines: list[LineRef]) -> dict[int, int]:
    return {line.global_index: position for position, line in enumerate(lines)}


def line_refs_for_span(
    lines: list[LineRef],
    start_index: int,
    end_index_exclusive: int,
) -> list[LineRef]:
    if not lines or end_index_exclusive <= start_index:
        return []
    positions = _global_to_position(lines)
    start_position = positions.get(start_index)
    end_position = positions.get(end_index_exclusive - 1)
    if start_position is None or end_position is None or end_position < start_position:
        return []
    return lines[start_position : end_position + 1]


def candidate_by_id(package: CandidatePackage, candidate_id: str) -> EndCandidate | None:
    for candidate in package.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def _resolve_candidate_alias(package: CandidatePackage, candidate_id: str | None) -> str | None:
    if not candidate_id:
        return None
    if candidate_by_id(package, candidate_id) is not None:
        return candidate_id
    alias_match = re.fullmatch(r"cand[_-]?0*(\d{1,2})", candidate_id, re.IGNORECASE)
    if alias_match:
        rank = int(alias_match.group(1))
        for candidate in package.candidates:
            if candidate.rank == rank:
                return candidate.candidate_id
    return candidate_id


def _starts_reference_section(line: str) -> bool:
    stripped = line.strip()
    return bool(REFERENCE_HEADING_RE.match(stripped) or REFERENCE_INLINE_START_RE.match(stripped))


def _soft_boundary_hits(lines: list[LineRef], pattern: ProceedingsPattern, start_index: int, end_index_exclusive: int) -> bool:
    positions = _global_to_position(lines)
    start_position = positions.get(start_index)
    end_position = positions.get(end_index_exclusive - 1)
    if start_position is None or end_position is None:
        return False
    for position in range(start_position + 4, end_position):
        matched, _, reason, _ = header_boundary(lines, position, pattern, allow_soft=True)
        if matched and reason != "coded_boundary":
            return True
    return False


def is_tail_metadata_like_line(line: str) -> bool:
    stripped = line.strip()
    normalized = normalize_text(stripped)
    if not stripped or not normalized:
        return True
    if _starts_reference_section(stripped):
        return True
    if REFERENCE_CITATION_START_RE.match(stripped):
        return True
    if is_trimmable_tail_metadata_line(stripped):
        return True
    if is_disclosure_detail_line(stripped):
        return True
    if DOI_LINE_RE.match(stripped):
        return True
    if EMAIL_RE.search(stripped):
        return True
    if URL_RE.search(stripped):
        return True
    if DOWNLOADED_FROM_RE.search(stripped):
        return True
    if PROCEEDINGS_PAGE_SECTION_RE.match(stripped):
        return True
    if CONTACT_PREFIX_RE.match(stripped):
        return True
    if is_header_preamble_line(stripped):
        return True
    return False


def _explicit_tail_metadata_start(line: str) -> bool:
    stripped = line.strip()
    if _starts_reference_section(stripped):
        return True
    if is_footer_like(stripped):
        return True
    if is_trimmable_tail_metadata_line(stripped):
        return True
    if DOI_LINE_RE.match(stripped):
        return True
    if EMAIL_RE.search(stripped):
        return True
    if URL_RE.search(stripped):
        return True
    if DOWNLOADED_FROM_RE.search(stripped):
        return True
    if PROCEEDINGS_PAGE_SECTION_RE.match(stripped):
        return True
    return bool(CONTACT_PREFIX_RE.match(stripped))


def _candidate_id(rank: int, heuristic_name: str) -> str:
    return f"cand_{rank:02d}_{heuristic_name}"


def _build_end_candidate(
    lines: list[LineRef],
    pattern: ProceedingsPattern,
    *,
    heuristic_name: str,
    start_index: int,
    end_index_exclusive: int,
    next_confirmed_header_index: int | None,
    confidence_class: str,
    rationale: str,
) -> EndCandidate:
    span_lines = line_refs_for_span(lines, start_index, end_index_exclusive)
    if not span_lines:
        raise ValueError(f"Empty candidate span: {heuristic_name} {start_index}:{end_index_exclusive}")
    return EndCandidate(
        candidate_id="",
        heuristic_name=heuristic_name,
        rank=0,
        start_index=start_index,
        end_index_exclusive=end_index_exclusive,
        start_page_index=span_lines[0].page_index,
        end_page_index=span_lines[-1].page_index,
        n_lines=len(span_lines),
        body_char_count=body_char_count(span_lines),
        contains_next_confirmed_header=bool(
            next_confirmed_header_index is not None and end_index_exclusive > next_confirmed_header_index
        ),
        contains_soft_boundary=_soft_boundary_hits(lines, pattern, start_index, end_index_exclusive),
        contains_tail_metadata=any(is_tail_metadata_like_line(line.text) for line in span_lines[-5:]),
        confidence_class=confidence_class,
        rationale=rationale,
    )


def confirmed_header_start_indices(lines: list[LineRef], pattern: ProceedingsPattern) -> list[int]:
    starts: list[int] = []
    position = 0
    while position < len(lines):
        matched, end_position, reason, score = header_boundary(lines, position, pattern, allow_soft=True)
        if not matched:
            position += 1
            continue
        if reason == "coded_boundary":
            starts.append(lines[position].global_index)
            position = max(position + 1, end_position)
            continue

        lookahead = lines[end_position : min(len(lines), end_position + 5)]
        author_hit = any(is_author_like(line.text) for line in lookahead[:3])
        institution_hit = any(is_institution_like(line.text) for line in lookahead[:4])
        section_hit = any(is_section_heading(line.text) for line in lookahead[:4])
        title_score, _ = title_cluster_score(" ".join(line.text for line in lines[position : position + 2]), lines, position)
        current_line = lines[position].text
        strong_soft_header = (
            score >= 4
            and is_potential_title_line(current_line)
            and (author_hit or institution_hit or section_hit or title_score >= 0.75)
        )
        if strong_soft_header:
            starts.append(lines[position].global_index)
            position = max(position + 1, end_position)
            continue
        position += 1
    return starts


def first_confirmed_header_after_start(
    lines: list[LineRef],
    start_index: int,
    pattern: ProceedingsPattern,
    *,
    min_gap: int = 4,
) -> int | None:
    confirmed = confirmed_header_start_indices(lines, pattern)
    for candidate_start in confirmed:
        if candidate_start >= start_index + min_gap:
            return candidate_start
    return None


def candidate_generation_window(
    lines: list[LineRef],
    start_index: int,
    next_confirmed_header_index: int | None,
    *,
    max_pages_from_start: int,
    max_lines_from_start: int,
    max_chars_from_start: int,
) -> tuple[int, dict[str, Any]]:
    positions = _global_to_position(lines)
    start_position = positions.get(start_index)
    if start_position is None:
        raise ValueError(f"Unknown start index: {start_index}")
    start_line = lines[start_position]
    document_end_index = _document_end_index(lines)

    page_break_position = len(lines)
    if max_pages_from_start > 0:
        allowed_last_page = start_line.page_index + max_pages_from_start - 1
        for position in range(start_position + 1, len(lines)):
            if lines[position].page_index > allowed_last_page:
                page_break_position = position
                break
    page_cap = lines[page_break_position - 1].global_index + 1 if page_break_position > 0 else document_end_index

    line_break_position = min(len(lines), start_position + max(1, max_lines_from_start))
    line_cap = lines[line_break_position - 1].global_index + 1 if line_break_position > 0 else document_end_index

    char_total = 0
    char_break_position = len(lines)
    for position in range(start_position, len(lines)):
        projected = char_total + len(lines[position].text)
        if position > start_position and projected > max_chars_from_start:
            char_break_position = position
            break
        char_total = projected
    char_cap = lines[char_break_position - 1].global_index + 1 if char_break_position > 0 else document_end_index

    end_candidates: list[tuple[int, str]] = [
        (page_cap, "page_cap"),
        (line_cap, "line_cap"),
        (char_cap, "char_cap"),
        (document_end_index, "document_end"),
    ]
    if next_confirmed_header_index is not None:
        end_candidates.append((next_confirmed_header_index, "next_confirmed_header"))
    end_index = min(max(start_index + 1, value) for value, _ in end_candidates)
    bound_reasons = [reason for value, reason in end_candidates if value == end_index]
    return end_index, {
        "window_end_index_exclusive": end_index,
        "window_bound_reasons": bound_reasons,
        "next_confirmed_header_index": next_confirmed_header_index,
        "max_pages_from_start": max_pages_from_start,
        "max_lines_from_start": max_lines_from_start,
        "max_chars_from_start": max_chars_from_start,
    }


def _tail_metadata_trim_end(
    lines: list[LineRef],
    start_index: int,
    permissive_end_index_exclusive: int,
) -> int:
    span_lines = line_refs_for_span(lines, start_index, permissive_end_index_exclusive)
    if len(span_lines) < 6:
        return permissive_end_index_exclusive
    for offset, line_ref in enumerate(span_lines[4:], start=4):
        if _starts_reference_section(line_ref.text):
            return line_ref.global_index
        if not _explicit_tail_metadata_start(line_ref.text):
            continue
        suffix = span_lines[offset:]
        metadata_hits = sum(1 for line in suffix if is_tail_metadata_like_line(line.text))
        if metadata_hits >= max(1, len(suffix) - 1):
            return line_ref.global_index
    return permissive_end_index_exclusive


def _last_non_metadata_end(
    lines: list[LineRef],
    start_index: int,
    permissive_end_index_exclusive: int,
) -> int:
    span_lines = line_refs_for_span(lines, start_index, permissive_end_index_exclusive)
    if len(span_lines) < 6:
        return permissive_end_index_exclusive
    metadata_flags = [is_tail_metadata_like_line(line.text) for line in span_lines]
    trailing_run_start: int | None = None
    trailing_run_length = 0
    for offset in range(len(span_lines) - 1, -1, -1):
        if metadata_flags[offset]:
            trailing_run_start = offset
            trailing_run_length += 1
            continue
        break
    if trailing_run_start is not None and trailing_run_length >= 2 and trailing_run_start > 0:
        return span_lines[trailing_run_start].global_index

    tail_window_start = max(0, len(span_lines) - 5)
    tail_flags = metadata_flags[tail_window_start:]
    if sum(1 for flag in tail_flags if flag) >= 3:
        first_tail_metadata = next(
            (tail_window_start + offset for offset, flag in enumerate(tail_flags) if flag),
            None,
        )
        if first_tail_metadata is not None and first_tail_metadata > 0:
            return span_lines[first_tail_metadata].global_index
    return permissive_end_index_exclusive


def build_end_candidates(
    lines: list[LineRef],
    matched_block: AbstractBlock,
    pattern: ProceedingsPattern,
    next_confirmed_header_index: int | None,
    *,
    max_pages_from_start: int,
    max_lines_from_start: int,
    max_chars_from_start: int,
) -> tuple[list[EndCandidate], dict[str, Any]]:
    start_index = matched_block.start_index
    permissive_end_index_exclusive, window_metadata = candidate_generation_window(
        lines,
        start_index,
        next_confirmed_header_index,
        max_pages_from_start=max_pages_from_start,
        max_lines_from_start=max_lines_from_start,
        max_chars_from_start=max_chars_from_start,
    )

    baseline_end_index_exclusive = min(matched_block.end_index, permissive_end_index_exclusive)
    baseline_end_index_exclusive = max(start_index + 1, baseline_end_index_exclusive)
    tail_trim_end_index_exclusive = max(
        start_index + 1,
        _tail_metadata_trim_end(lines, start_index, permissive_end_index_exclusive),
    )
    last_non_metadata_end_index_exclusive = max(
        start_index + 1,
        _last_non_metadata_end(lines, start_index, permissive_end_index_exclusive),
    )

    candidates = [
        _build_end_candidate(
            lines,
            pattern,
            heuristic_name="current_selected_end",
            start_index=start_index,
            end_index_exclusive=baseline_end_index_exclusive,
            next_confirmed_header_index=next_confirmed_header_index,
            confidence_class="strict",
            rationale=f"Preserves the current deterministic stage-05 end ({matched_block.end_rule or 'unknown_end_rule'}).",
        ),
        _build_end_candidate(
            lines,
            pattern,
            heuristic_name="tail_metadata_trim_end",
            start_index=start_index,
            end_index_exclusive=tail_trim_end_index_exclusive,
            next_confirmed_header_index=next_confirmed_header_index,
            confidence_class="medium",
            rationale="Extends to the permissive window, then removes an explicit tail-metadata section when present.",
        ),
        _build_end_candidate(
            lines,
            pattern,
            heuristic_name="last_non_metadata_end",
            start_index=start_index,
            end_index_exclusive=last_non_metadata_end_index_exclusive,
            next_confirmed_header_index=next_confirmed_header_index,
            confidence_class="medium",
            rationale="Stops before a trailing run of metadata-like lines near the permissive window end.",
        ),
        _build_end_candidate(
            lines,
            pattern,
            heuristic_name="next_confirmed_header_end",
            start_index=start_index,
            end_index_exclusive=permissive_end_index_exclusive,
            next_confirmed_header_index=next_confirmed_header_index,
            confidence_class="permissive",
            rationale="Keeps the full permissive span up to the next confirmed header or the fixed search cap.",
        ),
    ]
    window_metadata["baseline_end_index_exclusive"] = baseline_end_index_exclusive
    window_metadata["overshoot_end_index_exclusive"] = permissive_end_index_exclusive
    return candidates, window_metadata


def dedupe_end_candidates(candidates: list[EndCandidate]) -> list[EndCandidate]:
    deduped: dict[tuple[int, int], EndCandidate] = {}
    for candidate in candidates:
        key = (candidate.start_index, candidate.end_index_exclusive)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            continue
        if HEURISTIC_PRIORITY.get(candidate.heuristic_name, 0) > HEURISTIC_PRIORITY.get(existing.heuristic_name, 0):
            deduped[key] = candidate

    ordered = sorted(deduped.values(), key=lambda candidate: (candidate.end_index_exclusive, candidate.heuristic_name))
    reassigned: list[EndCandidate] = []
    for rank, candidate in enumerate(ordered, start=1):
        reassigned.append(
            EndCandidate(
                candidate_id=_candidate_id(rank, candidate.heuristic_name),
                heuristic_name=candidate.heuristic_name,
                rank=rank,
                start_index=candidate.start_index,
                end_index_exclusive=candidate.end_index_exclusive,
                start_page_index=candidate.start_page_index,
                end_page_index=candidate.end_page_index,
                n_lines=candidate.n_lines,
                body_char_count=candidate.body_char_count,
                contains_next_confirmed_header=candidate.contains_next_confirmed_header,
                contains_soft_boundary=candidate.contains_soft_boundary,
                contains_tail_metadata=candidate.contains_tail_metadata,
                confidence_class=candidate.confidence_class,
                rationale=candidate.rationale,
            )
        )
    return reassigned


def resolve_candidate_id_by_end(
    candidates: list[EndCandidate],
    *,
    start_index: int,
    end_index_exclusive: int,
) -> str:
    for candidate in candidates:
        if candidate.start_index == start_index and candidate.end_index_exclusive == end_index_exclusive:
            return candidate.candidate_id
    raise ValueError(f"No candidate found for span {start_index}:{end_index_exclusive}")


def serialise_candidate_package(package: CandidatePackage) -> dict[str, Any]:
    return {
        "paper_id": package.paper_id,
        "trim_workflow_version": package.trim_workflow_version,
        "trim_workflow_stage": package.trim_workflow_stage,
        "source_text_json_path": package.source_text_json_path,
        "reference_title": package.reference_title,
        "reference_authors": package.reference_authors,
        "matched_start_index": package.matched_start_index,
        "matched_start_page_index": package.matched_start_page_index,
        "matched_block_code": package.matched_block_code,
        "matched_block_title": package.matched_block_title,
        "start_rule": package.start_rule,
        "candidate_generation_mode": package.candidate_generation_mode,
        "baseline_candidate_id": package.baseline_candidate_id,
        "overshoot_candidate_id": package.overshoot_candidate_id,
        "llm_routing_recommended": package.llm_routing_recommended,
        "llm_routing_reason": package.llm_routing_reason,
        "candidates": [asdict(candidate) for candidate in package.candidates],
        "proceedings_metadata": package.proceedings_signals,
        "upstream_match_metadata": package.upstream_match_metadata,
    }


def write_candidate_package(package: CandidatePackage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialise_candidate_package(package), ensure_ascii=False, indent=2), encoding="utf-8")


def load_candidate_package(path: Path) -> CandidatePackage:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CandidatePackage(
        paper_id=str(payload.get("paper_id") or ""),
        source_text_json_path=str(payload.get("source_text_json_path") or ""),
        reference_title=str(payload.get("reference_title") or ""),
        reference_authors=str(payload.get("reference_authors") or ""),
        matched_start_index=int(payload.get("matched_start_index") or 0),
        matched_start_page_index=int(payload.get("matched_start_page_index") or 0),
        matched_block_code=str(payload.get("matched_block_code") or ""),
        matched_block_title=str(payload.get("matched_block_title") or ""),
        start_rule=str(payload.get("start_rule") or ""),
        candidate_generation_mode=str(payload.get("candidate_generation_mode") or CANDIDATE_GENERATION_MODE),
        candidates=[EndCandidate(**candidate_payload) for candidate_payload in payload.get("candidates") or []],
        overshoot_candidate_id=str(payload.get("overshoot_candidate_id") or ""),
        baseline_candidate_id=str(payload.get("baseline_candidate_id") or ""),
        proceedings_signals=dict(payload.get("proceedings_metadata") or {}),
        upstream_match_metadata=dict(payload.get("upstream_match_metadata") or {}),
        trim_workflow_version=str(payload.get("trim_workflow_version") or TRIM_WORKFLOW_VERSION),
        trim_workflow_stage=str(payload.get("trim_workflow_stage") or "candidate_generation"),
        llm_routing_recommended=bool(payload.get("llm_routing_recommended")),
        llm_routing_reason=str(payload.get("llm_routing_reason") or ""),
    )


def llm_routing_recommendation(package: CandidatePackage) -> tuple[bool, str]:
    if len(package.candidates) >= 2:
        return True, "multiple_end_candidates"
    baseline = candidate_by_id(package, package.baseline_candidate_id)
    overshoot = candidate_by_id(package, package.overshoot_candidate_id)
    end_rule = str(package.upstream_match_metadata.get("end_rule") or "")
    if baseline is not None and overshoot is not None:
        if overshoot.end_index_exclusive - baseline.end_index_exclusive >= 6:
            return True, "overshoot_substantially_longer_than_baseline"
    if end_rule in {"window_extent_cap", "page_span_cap", "next_soft_header", "trailing_header_noise"}:
        return True, f"baseline_end_rule_{end_rule}"
    if overshoot is not None and overshoot.contains_tail_metadata:
        return True, "tail_metadata_detected_near_permissive_end"
    if str(package.upstream_match_metadata.get("candidate_quality_status") or "") == "manual_review_required":
        return True, "baseline_candidate_requires_manual_review"
    return False, "single_candidate_without_additional_risk_signals"


def candidate_registry_fieldnames() -> list[str]:
    return [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_filename",
        "source_text_json_path",
        "candidate_json_path",
        "n_pages",
        "abstract_block_count",
        "title_like_line_count",
        "author_like_line_count",
        "program_marker_count",
        "proceedings_signal_score",
        "proceedings_detected",
        "trim_workflow_version",
        "trim_workflow_stage",
        "trim_status",
        "trim_reason",
        "trim_method",
        "trim_mode",
        "matched_block_code",
        "matched_block_title",
        "title_score",
        "author_score",
        "match_score",
        "start_rule",
        "end_rule",
        "start_page_index",
        "end_page_index",
        "start_line_global_index",
        "end_line_global_index_exclusive",
        "candidate_count",
        "baseline_candidate_id",
        "overshoot_candidate_id",
        "candidate_ids",
        "candidate_heuristics",
        "candidate_end_indices",
        "candidate_end_pages",
        "llm_routing_recommended",
        "llm_routing_reason",
        "created_at_utc",
    ]


def candidate_registry_row(
    *,
    package: CandidatePackage,
    source_record: dict[str, Any],
    source_path: Path,
    candidate_path: Path | None,
    reference_row: dict[str, str],
    trim_status: str,
    trim_reason: str,
) -> dict[str, str]:
    candidate_ids = [candidate.candidate_id for candidate in package.candidates]
    candidate_heuristics = [candidate.heuristic_name for candidate in package.candidates]
    candidate_end_indices = [str(candidate.end_index_exclusive) for candidate in package.candidates]
    candidate_end_pages = [str(candidate.end_page_index) for candidate in package.candidates]
    upstream = package.upstream_match_metadata
    signals = package.proceedings_signals
    return {
        "paper_id": package.paper_id,
        "covidence_id": (reference_row.get("Covidence") or package.paper_id).strip(),
        "title": package.reference_title,
        "authors": package.reference_authors,
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "candidate_json_path": relative_to_repo(candidate_path) if candidate_path else "",
        "n_pages": str(signals.get("n_pages") or source_record.get("n_pages") or 0),
        "abstract_block_count": str(signals.get("abstract_block_count") or 0),
        "title_like_line_count": str(signals.get("title_like_line_count") or 0),
        "author_like_line_count": str(signals.get("author_like_line_count") or 0),
        "program_marker_count": str(signals.get("program_marker_count") or 0),
        "proceedings_signal_score": str(signals.get("proceedings_signal_score") or ""),
        "proceedings_detected": bool_text(bool(signals.get("proceedings_detected"))),
        "trim_workflow_version": package.trim_workflow_version,
        "trim_workflow_stage": package.trim_workflow_stage,
        "trim_status": trim_status,
        "trim_reason": trim_reason,
        "trim_method": str(upstream.get("trim_method") or ""),
        "trim_mode": str(upstream.get("trim_mode") or ""),
        "matched_block_code": package.matched_block_code,
        "matched_block_title": package.matched_block_title,
        "title_score": str(upstream.get("title_score") or ""),
        "author_score": str(upstream.get("author_score") or ""),
        "match_score": str(upstream.get("match_score") or ""),
        "start_rule": package.start_rule,
        "end_rule": str(upstream.get("end_rule") or ""),
        "start_page_index": str(package.matched_start_page_index),
        "end_page_index": str(upstream.get("matched_end_page_index") or ""),
        "start_line_global_index": str(package.matched_start_index),
        "end_line_global_index_exclusive": str(upstream.get("matched_end_index_exclusive") or ""),
        "candidate_count": str(len(package.candidates)),
        "baseline_candidate_id": package.baseline_candidate_id,
        "overshoot_candidate_id": package.overshoot_candidate_id,
        "candidate_ids": "|".join(candidate_ids),
        "candidate_heuristics": "|".join(candidate_heuristics),
        "candidate_end_indices": "|".join(candidate_end_indices),
        "candidate_end_pages": "|".join(candidate_end_pages),
        "llm_routing_recommended": bool_text(package.llm_routing_recommended),
        "llm_routing_reason": package.llm_routing_reason,
        "created_at_utc": now_utc_iso(),
    }


def final_registry_fieldnames() -> list[str]:
    return [
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "source_filename",
        "source_text_json_path",
        "candidate_source_json_path",
        "trimmed_text_json_path",
        "trim_workflow_version",
        "trim_workflow_stage",
        "trim_status",
        "trim_reason",
        "trim_method",
        "trim_mode",
        "matched_block_code",
        "matched_block_title",
        "title_score",
        "author_score",
        "match_score",
        "start_rule",
        "end_rule",
        "start_page_index",
        "end_page_index",
        "start_line_global_index",
        "end_line_global_index_exclusive",
        "end_selection_mode",
        "candidate_count",
        "baseline_candidate_id",
        "overshoot_candidate_id",
        "candidate_ids",
        "llm_used",
        "llm_model",
        "llm_api_mode",
        "llm_prompt_version",
        "llm_decision_type",
        "llm_selected_candidate_id",
        "llm_last_abstract_line_global_index",
        "llm_confidence",
        "llm_end_reason",
        "llm_explanation_short",
        "llm_validation_passed",
        "llm_validation_reason",
        "heuristic_fallback_used",
        "trimmed_at_utc",
    ]


def final_registry_row(
    *,
    package: CandidatePackage,
    reference_row: dict[str, str],
    source_record: dict[str, Any],
    source_path: Path,
    candidate_path: Path,
    trimmed_path: Path | None,
    trim_status: str,
    trim_reason: str,
    final_block: AbstractBlock | None,
    end_selection_mode: str,
    llm_used: bool,
    llm_model: str,
    prompt_version: str,
    decision: LLMDecision | None,
    llm_validation_passed: bool,
    llm_validation_reason: str,
    heuristic_fallback_used: bool,
) -> dict[str, str]:
    candidate_ids = [candidate.candidate_id for candidate in package.candidates]
    upstream = package.upstream_match_metadata
    return {
        "paper_id": package.paper_id,
        "covidence_id": (reference_row.get("Covidence") or package.paper_id).strip(),
        "title": (reference_row.get("Title") or package.reference_title).strip(),
        "authors": (reference_row.get("Authors") or package.reference_authors).strip(),
        "source_filename": str(source_record.get("source_filename") or ""),
        "source_text_json_path": relative_to_repo(source_path),
        "candidate_source_json_path": relative_to_repo(candidate_path),
        "trimmed_text_json_path": relative_to_repo(trimmed_path) if trimmed_path else "",
        "trim_workflow_version": package.trim_workflow_version,
        "trim_workflow_stage": "llm_validated",
        "trim_status": trim_status,
        "trim_reason": trim_reason,
        "trim_method": final_block.trim_method if final_block else str(upstream.get("trim_method") or ""),
        "trim_mode": final_block.trim_mode if final_block else str(upstream.get("trim_mode") or ""),
        "matched_block_code": package.matched_block_code,
        "matched_block_title": package.matched_block_title,
        "title_score": f"{final_block.title_score:.4f}" if final_block else str(upstream.get("title_score") or ""),
        "author_score": f"{final_block.author_score:.4f}" if final_block else str(upstream.get("author_score") or ""),
        "match_score": f"{final_block.match_score:.4f}" if final_block else str(upstream.get("match_score") or ""),
        "start_rule": final_block.start_rule if final_block else package.start_rule,
        "end_rule": final_block.end_rule if final_block else "",
        "start_page_index": str(final_block.start_page_index) if final_block else str(package.matched_start_page_index),
        "end_page_index": str(final_block.end_page_index) if final_block else "",
        "start_line_global_index": str(final_block.start_index) if final_block else str(package.matched_start_index),
        "end_line_global_index_exclusive": str(final_block.end_index) if final_block else "",
        "end_selection_mode": end_selection_mode,
        "candidate_count": str(len(package.candidates)),
        "baseline_candidate_id": package.baseline_candidate_id,
        "overshoot_candidate_id": package.overshoot_candidate_id,
        "candidate_ids": "|".join(candidate_ids),
        "llm_used": bool_text(llm_used),
        "llm_model": llm_model,
        "llm_api_mode": LLM_API_MODE if llm_used else "",
        "llm_prompt_version": prompt_version if llm_used else "",
        "llm_decision_type": decision.decision_type if decision else "",
        "llm_selected_candidate_id": decision.selected_candidate_id or "" if decision else "",
        "llm_last_abstract_line_global_index": (
            "" if decision is None or decision.last_abstract_line_global_index is None else str(decision.last_abstract_line_global_index)
        ),
        "llm_confidence": decision.confidence if decision else "",
        "llm_end_reason": decision.end_reason if decision else "",
        "llm_explanation_short": decision.explanation_short if decision else "",
        "llm_validation_passed": bool_text(llm_validation_passed),
        "llm_validation_reason": llm_validation_reason,
        "heuristic_fallback_used": bool_text(heuristic_fallback_used),
        "trimmed_at_utc": now_utc_iso() if trimmed_path else "",
    }


def _reference_from_package_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def source_path_from_package(package: CandidatePackage) -> Path:
    return _reference_from_package_path(package.source_text_json_path)


def _overshoot_span_lines(package: CandidatePackage, source_lines: list[LineRef]) -> list[LineRef]:
    overshoot_candidate = candidate_by_id(package, package.overshoot_candidate_id)
    if overshoot_candidate is None:
        return []
    return line_refs_for_span(
        source_lines,
        package.matched_start_index,
        overshoot_candidate.end_index_exclusive,
    )


def build_llm_prompt(
    package: CandidatePackage,
    source_lines: list[LineRef],
    *,
    prompt_version: str,
) -> tuple[str, str]:
    overshoot_lines = _overshoot_span_lines(package, source_lines)
    candidate_end_lines: dict[int, list[str]] = {}
    candidate_summaries: list[str] = []
    for candidate in package.candidates:
        relative_end_line = candidate.end_index_exclusive - package.matched_start_index
        candidate_end_lines.setdefault(relative_end_line, []).append(candidate.candidate_id)
        summary = f"- {candidate.candidate_id} {candidate.heuristic_name} -> ends at line {relative_end_line}"
        if candidate.candidate_id == package.overshoot_candidate_id:
            summary += " (overshoot candidate)"
        candidate_summaries.append(summary)

    line_list: list[str] = []
    for line_number, line_ref in enumerate(overshoot_lines, start=1):
        markers = candidate_end_lines.get(line_number, [])
        marker_text = f" <<< {'; '.join(markers)} ends here" if markers else ""
        line_list.append(f"[{line_number:03d}] {line_ref.text}{marker_text}")

    matched_code = package.matched_block_code or "N/A"
    developer_instructions = (
        "You are deciding the end of one conference abstract. "
        "Use only the provided lines. Prefer an exact existing candidate when possible. "
        "Otherwise choose the last abstract line within the overshoot candidate. "
        "Do not invent text outside the provided span. Return only schema-compliant JSON."
    )
    user_payload = "\n".join(
        [
            f"Prompt version: {prompt_version}",
            f"Paper ID: {package.paper_id}",
            f"Reference title: {package.reference_title}",
            f"Reference authors: {package.reference_authors}",
            f"Matched code: {matched_code}",
            "",
            "Candidates:",
            *candidate_summaries,
            "",
            "Decide whether:",
            "1. one candidate already ends exactly at the last abstract line",
            "2. none is exact, but the last abstract line lies inside the overshoot candidate",
            "3. the boundary cannot be determined confidently",
            "",
            "The last abstract line is the last line belonging to the target abstract before metadata or the next abstract header begins.",
            "",
            "Line list:",
            *line_list,
        ]
    )
    return developer_instructions, user_payload


def parse_llm_decision(
    package: CandidatePackage,
    payload: dict[str, Any],
    source_lines: list[LineRef],
) -> LLMDecision:
    decision_type = str(payload.get("decision_type") or "unable_to_determine")
    selected_candidate_id = payload.get("selected_candidate_id")
    if selected_candidate_id is not None:
        selected_candidate_id = _resolve_candidate_alias(package, str(selected_candidate_id).strip() or None)

    overshoot_lines = _overshoot_span_lines(package, source_lines)
    last_abstract_line_global_index: int | None = None
    if decision_type == "candidate_exact" and selected_candidate_id:
        selected_candidate = candidate_by_id(package, selected_candidate_id)
        if selected_candidate is not None:
            last_abstract_line_global_index = selected_candidate.end_index_exclusive - 1
    elif decision_type == "line_within_overshoot":
        relative_line_number = payload.get("last_abstract_line_number")
        if isinstance(relative_line_number, int) and 1 <= relative_line_number <= len(overshoot_lines):
            last_abstract_line_global_index = overshoot_lines[relative_line_number - 1].global_index
        if not selected_candidate_id:
            selected_candidate_id = package.overshoot_candidate_id

    return LLMDecision(
        decision_type=decision_type,
        selected_candidate_id=selected_candidate_id,
        last_abstract_line_global_index=last_abstract_line_global_index,
        confidence=str(payload.get("confidence") or "low"),
        end_reason=str(payload.get("end_reason") or "uncertain"),
        explanation_short=str(payload.get("explanation_short") or "").strip(),
    )


def heuristic_fallback_candidate(package: CandidatePackage) -> EndCandidate | None:
    by_name = {candidate.heuristic_name: candidate for candidate in package.candidates}
    for heuristic_name in FALLBACK_HEURISTIC_ORDER:
        candidate = by_name.get(heuristic_name)
        if candidate is not None:
            return candidate
    if package.candidates:
        return sorted(package.candidates, key=lambda candidate: candidate.end_index_exclusive)[0]
    return None


def _build_block_from_end_index(
    package: CandidatePackage,
    source_lines: list[LineRef],
    *,
    end_index_exclusive: int,
    end_rule: str,
) -> AbstractBlock | None:
    span_lines = line_refs_for_span(source_lines, package.matched_start_index, end_index_exclusive)
    if not span_lines:
        return None
    enough_body, section_hits, header_only = has_enough_body(span_lines)
    _ = enough_body
    upstream = package.upstream_match_metadata
    header_lines = [line.text for line in span_lines[: min(len(span_lines), 8)] if not is_footer_like(line.text)]
    preview_lines = [line.text for line in span_lines[: min(len(span_lines), 14)] if not is_footer_like(line.text)]
    first_line = span_lines[0].text
    title_text = package.matched_block_title.strip() or strip_abstract_code(first_line)
    return AbstractBlock(
        code=package.matched_block_code or abstract_code(first_line),
        start_index=span_lines[0].global_index,
        end_index=span_lines[-1].global_index + 1,
        start_page_index=span_lines[0].page_index,
        end_page_index=span_lines[-1].page_index,
        title_text=title_text,
        header_text=" ".join(header_lines),
        preview_text=" ".join(preview_lines),
        line_refs=span_lines,
        title_score=float(upstream.get("title_score") or 0.0),
        author_score=float(upstream.get("author_score") or 0.0),
        match_score=float(upstream.get("match_score") or 0.0),
        trim_method=str(upstream.get("trim_method") or "llm_validated_proceedings_trim"),
        trim_mode=str(upstream.get("trim_mode") or "llm_validated_proceedings_trim"),
        start_rule=package.start_rule,
        end_rule=end_rule,
        body_signal_count=section_hits,
        spillover_flag=False,
        header_only_flag=header_only,
        index_detected=bool(upstream.get("index_detected")),
        index_confidence=float(upstream.get("index_confidence") or 0.0),
        index_listed_page=str(upstream.get("index_listed_page") or ""),
        index_prev_code=str(upstream.get("index_prev_code") or ""),
        index_next_code=str(upstream.get("index_next_code") or ""),
        page_map_method=str(upstream.get("page_map_method") or ""),
        estimated_offset=float(upstream.get("estimated_offset") or 0.0),
        offset_confidence=float(upstream.get("offset_confidence") or 0.0),
        candidate_rank=1,
        fallback_triggered=bool(upstream.get("fallback_triggered")),
    )


def _overshoot_remainder_contains_resumed_body(
    package: CandidatePackage,
    source_lines: list[LineRef],
    *,
    final_end_index_exclusive: int,
    overshoot_end_index_exclusive: int,
) -> bool:
    remainder_lines = line_refs_for_span(source_lines, final_end_index_exclusive, overshoot_end_index_exclusive)
    continuation_hits = 0
    for line in remainder_lines:
        stripped = line.text.strip()
        normalized = normalize_text(stripped)
        if not stripped or not normalized:
            continue
        line_code = abstract_code(stripped)
        if line_code and line_code != package.matched_block_code:
            return False
        if is_footer_like(stripped) or is_header_preamble_line(stripped):
            continue
        if is_tail_metadata_like_line(stripped):
            continue
        if package.matched_block_code and line_code == package.matched_block_code:
            continue
        token_count = len(normalized.split())
        if is_section_heading(stripped):
            return True
        if token_count >= 4:
            continuation_hits += 1
            if continuation_hits >= 2:
                return True
    return False


def validate_llm_decision(
    package: CandidatePackage,
    decision: LLMDecision,
    source_lines: list[LineRef],
) -> tuple[bool, str]:
    overshoot_candidate = candidate_by_id(package, package.overshoot_candidate_id)
    if overshoot_candidate is None:
        return False, "missing_overshoot_candidate"

    if decision.decision_type == "candidate_exact":
        if not decision.selected_candidate_id:
            return False, "candidate_exact_missing_candidate_id"
        selected_candidate = candidate_by_id(package, decision.selected_candidate_id)
        if selected_candidate is None:
            return False, "candidate_exact_unknown_candidate_id"
        final_end_index_exclusive = selected_candidate.end_index_exclusive
    elif decision.decision_type == "line_within_overshoot":
        if decision.last_abstract_line_global_index is None:
            return False, "missing_last_abstract_line_number"
        final_end_index_exclusive = decision.last_abstract_line_global_index + 1
    elif decision.decision_type == "unable_to_determine":
        return False, "llm_unable_to_determine"
    else:
        return False, "unknown_decision_type"

    if final_end_index_exclusive <= package.matched_start_index:
        return False, "final_end_precedes_start"
    if final_end_index_exclusive > overshoot_candidate.end_index_exclusive:
        return False, "final_end_exceeds_overshoot"
    if decision.decision_type == "line_within_overshoot" and _overshoot_remainder_contains_resumed_body(
        package,
        source_lines,
        final_end_index_exclusive=final_end_index_exclusive,
        overshoot_end_index_exclusive=overshoot_candidate.end_index_exclusive,
    ):
        return False, "overshoot_contains_resumed_body_after_page_noise"

    span_lines = line_refs_for_span(source_lines, package.matched_start_index, final_end_index_exclusive)
    if not span_lines:
        return False, "empty_final_span"
    enough_body, _, _ = has_enough_body(span_lines)
    if not enough_body:
        return False, "span_failed_body_guardrail"
    if len(span_lines) < 4 or body_char_count(span_lines) < 160:
        return False, "span_implausibly_short"
    return True, "ok"


def apply_llm_decision(
    package: CandidatePackage,
    decision: LLMDecision,
    source_lines: list[LineRef],
) -> AbstractBlock | None:
    if decision.decision_type == "candidate_exact" and decision.selected_candidate_id:
        candidate = candidate_by_id(package, decision.selected_candidate_id)
        if candidate is None:
            return None
        return _build_block_from_end_index(
            package,
            source_lines,
            end_index_exclusive=candidate.end_index_exclusive,
            end_rule=f"llm_candidate_exact::{candidate.heuristic_name}",
        )
    if decision.decision_type == "line_within_overshoot" and decision.last_abstract_line_global_index is not None:
        return _build_block_from_end_index(
            package,
            source_lines,
            end_index_exclusive=decision.last_abstract_line_global_index + 1,
            end_rule=f"llm_line_within_overshoot::{decision.end_reason}",
        )
    fallback_candidate = heuristic_fallback_candidate(package)
    if fallback_candidate is None:
        return None
    return _build_block_from_end_index(
        package,
        source_lines,
        end_index_exclusive=fallback_candidate.end_index_exclusive,
        end_rule=f"heuristic_fallback::{fallback_candidate.heuristic_name}",
    )


def call_llm_for_end_decision(
    package: CandidatePackage,
    source_lines: list[LineRef],
    client: Any,
    *,
    model_name: str,
    prompt_version: str,
) -> LLMDecision:
    developer_instructions, user_payload = build_llm_prompt(
        package,
        source_lines,
        prompt_version=prompt_version,
    )
    response = client.responses.create(
        model=model_name,
        store=False,
        instructions=developer_instructions,
        input=[{"role": "user", "content": user_payload}],
        text={
            "format": {
                "type": "json_schema",
                "name": "abstract_end_decision",
                "strict": True,
                "schema": END_DECISION_SCHEMA,
            }
        },
    )
    output_text = str(getattr(response, "output_text", "") or "").strip()
    if not output_text:
        raise ValueError(f"Empty structured output for paper {package.paper_id}")
    payload = json.loads(output_text)
    return parse_llm_decision(package, payload, source_lines)
