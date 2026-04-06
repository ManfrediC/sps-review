"""Stage 1: Input assembly for LLM-based source categorisation.

Builds one input payload per paper from metadata, extracted text, and
trim registry data. This is a deterministic packaging step — no
classification happens here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Approximate token budget for text content (~4 chars per token).
_TEXT_CHAR_BUDGET = 24_000  # ~6,000 tokens
_PROMPT_METADATA_KEYS = (
    "title",
    "abstract",
    "journal",
    "issue",
    "pages",
    "doi",
    "abstract_note",
)
_BACK_MATTER_HEADING_RE = re.compile(r"(?im)^\s*(acknowledg?ments?|references)\b.*$")


@dataclass
class PaperPayload:
    """Assembled input for one paper, ready for the LLM call."""

    paper_id: str
    metadata: dict[str, str] = field(default_factory=dict)
    text_content: str = ""
    text_source: str = "full_text"
    proceedings_detected: bool = False
    trim_status: str = ""
    text_page_count: int = 0


def load_text_json(path: Path) -> dict[str, Any]:
    """Load a text JSON file, returning an empty dict on failure."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _extract_text_pages(record: dict[str, Any], char_budget: int) -> tuple[str, int]:
    """Extract text from pages within a character budget.

    Returns the assembled text and the number of pages used.
    """
    pages = record.get("pages") or []
    parts: list[str] = []
    chars_used = 0
    pages_used = 0
    for page in pages:
        page_text = str(page.get("text") or "").strip()
        if not page_text:
            continue
        if chars_used + len(page_text) > char_budget and parts:
            break
        parts.append(page_text)
        chars_used += len(page_text)
        pages_used += 1
    return "\n\n".join(parts), pages_used


def _truncate_back_matter(text: str) -> str:
    """Drop acknowledgments/references sections from extracted text."""
    match = _BACK_MATTER_HEADING_RE.search(text)
    if not match:
        return text
    return text[: match.start()].rstrip()


def _normalise_for_overlap(text: str) -> str:
    """Normalise text for conservative duplicate checks."""
    cleaned = str(text or "").replace("-\n", "").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned.casefold())
    cleaned = re.sub(r"[^0-9a-z ]+", "", cleaned)
    return cleaned.strip()


def _abstract_is_duplicated_in_text(abstract: str, text_content: str) -> bool:
    """Return True when the metadata abstract clearly duplicates the text body."""
    abstract_norm = _normalise_for_overlap(abstract)
    if len(abstract_norm) < 80:
        return False

    # The duplicate, when present, is typically near the start of the extracted text.
    text_excerpt_norm = _normalise_for_overlap(text_content[:6_000])
    if not text_excerpt_norm:
        return False

    return abstract_norm[:300] in text_excerpt_norm


def assemble_payload(
    *,
    paper_id: str,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any] | None,
    preferred_text_source: str,
    trim_row: dict[str, str],
) -> PaperPayload:
    """Assemble one input payload for a paper.

    Parameters
    ----------
    paper_id:
        The paper's unique identifier (Covidence ID).
    reference_row:
        Row from ``sps_references_export.csv``.
    text_record:
        Full-text JSON record from ``data/extraction_json/text/{paper_id}.json``.
    preferred_record:
        Trimmed text JSON if available, else ``None`` (falls back to *text_record*).
    preferred_text_source:
        ``"trimmed"`` or ``"full_text"``.
    trim_row:
        Row from ``text_trim_registry.csv`` (may be empty dict).
    """
    metadata = {
        "title": (reference_row.get("Title") or "").strip(),
        "abstract": (reference_row.get("Abstract") or "").strip(),
        "authors": (reference_row.get("Authors") or "").strip(),
        "journal": (reference_row.get("Journal") or "").strip(),
        "published_year": (reference_row.get("Published Year") or "").strip(),
        "volume": (reference_row.get("Volume") or "").strip(),
        "issue": (reference_row.get("Issue") or "").strip(),
        "pages": (reference_row.get("Pages") or "").strip(),
        "doi": (reference_row.get("DOI") or "").strip(),
        "tags": (reference_row.get("Tags") or "").strip(),
        "notes": (reference_row.get("Notes") or "").strip(),
    }

    # Use the preferred text source (trimmed if available).
    source_record = preferred_record if preferred_record else text_record
    text_content, pages_used = _extract_text_pages(source_record, _TEXT_CHAR_BUDGET)
    text_content = _truncate_back_matter(text_content)

    proceedings_detected = (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
    trim_status = (trim_row.get("trim_status") or "").strip()

    # Note missing abstract explicitly.
    if not metadata["abstract"]:
        metadata["abstract_note"] = "No abstract available in metadata."

    return PaperPayload(
        paper_id=paper_id,
        metadata=metadata,
        text_content=text_content,
        text_source=preferred_text_source,
        proceedings_detected=proceedings_detected,
        trim_status=trim_status,
        text_page_count=pages_used,
    )


def format_payload_for_llm(payload: PaperPayload) -> str:
    """Format a payload as a user-message string for the LLM call."""
    parts: list[str] = []
    duplicate_abstract = _abstract_is_duplicated_in_text(
        payload.metadata.get("abstract", ""),
        payload.text_content,
    )

    parts.append(f"Paper ID: {payload.paper_id}")
    parts.append("")

    parts.append("## Metadata")
    for key in _PROMPT_METADATA_KEYS:
        if key == "abstract" and duplicate_abstract:
            continue
        value = payload.metadata.get(key, "")
        if value:
            parts.append(f"- {key}: {value}")
    parts.append("")

    parts.append("## Source information")
    parts.append(f"- Text source: {payload.text_source}")
    parts.append(f"- Pages in text: {payload.text_page_count}")
    parts.append(f"- Proceedings detected: {payload.proceedings_detected}")
    if payload.trim_status:
        parts.append(f"- Trim status: {payload.trim_status}")
    parts.append("")

    if payload.text_content:
        parts.append("## Extracted text")
        parts.append(payload.text_content)
    else:
        parts.append("## Extracted text")
        parts.append("[No extracted text available.]")

    return "\n".join(parts)
