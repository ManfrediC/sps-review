"""Controller: orchestrates the full LLM classification flow for a paper.

Flow: manual-override check -> prepare -> classify -> validate ->
      adjudicate (if needed) -> validate again -> derive routing -> result.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from openai import APIError, APITimeoutError, RateLimitError

from src.pipelines._source_routing import bool_text
from src.pipelines.source_categorisation.adjudicate import adjudicate_paper, needs_adjudication
from src.pipelines.source_categorisation.classify import DEFAULT_MODEL, classify_paper
from src.pipelines.source_categorisation.models import (
    ClassificationResult,
    Confidence,
    EvidenceItem,
    LLMClassificationOutput,
    OriginalSpsData,
    SourceCategory,
)
from src.pipelines.source_categorisation.prepare import (
    PaperPayload,
    assemble_payload,
    load_text_json,
)
from src.pipelines.source_categorisation.validate import (
    Severity,
    apply_validator_effects,
    run_validators,
)

logger = logging.getLogger(__name__)

# Maximum retries on transient API errors.
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RATE_LIMIT_BASE_DELAY = 12.0  # Longer base for 429 — API window is ~60s at 30k TPM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relative_to_repo(path: Any, repo_root: Any) -> str:
    """Return a repo-relative path string with forward slashes."""
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except (ValueError, AttributeError):
        return str(path).replace("\\", "/")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_with_retry(
    payload: PaperPayload,
    *,
    model: str,
    api_key: str | None,
) -> tuple[LLMClassificationOutput, str]:
    """Call classify_paper with exponential backoff on transient errors."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return classify_paper(payload, model=model, api_key=api_key)
        except (RateLimitError, APITimeoutError, APIError) as exc:
            last_error = exc
            if isinstance(exc, APIError) and not isinstance(exc, RateLimitError) and exc.status_code and exc.status_code < 500:
                # Non-retryable client error (4xx except 429 rate limits).
                raise
            base = _RATE_LIMIT_BASE_DELAY if isinstance(exc, RateLimitError) else _RETRY_BASE_DELAY
            delay = base * (2**attempt)
            logger.warning(
                "API error for %s (attempt %d/%d), retrying in %.1fs: %s",
                payload.paper_id,
                attempt + 1,
                _MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)
    raise last_error  # type: ignore[misc]


def _adjudicate_with_retry(
    payload: PaperPayload,
    original: LLMClassificationOutput,
    flags: list[str],
    *,
    model: str,
    api_key: str | None,
) -> tuple[LLMClassificationOutput, str]:
    """Call adjudicate_paper with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return adjudicate_paper(payload, original, flags, model=model, api_key=api_key)
        except (RateLimitError, APITimeoutError, APIError) as exc:
            last_error = exc
            if isinstance(exc, APIError) and not isinstance(exc, RateLimitError) and exc.status_code and exc.status_code < 500:
                raise
            base = _RATE_LIMIT_BASE_DELAY if isinstance(exc, RateLimitError) else _RETRY_BASE_DELAY
            delay = base * (2**attempt)
            logger.warning(
                "Adjudication API error for %s (attempt %d/%d), retrying in %.1fs: %s",
                payload.paper_id,
                attempt + 1,
                _MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Manual override helpers
# ---------------------------------------------------------------------------


def _build_manual_override_result(
    paper_id: str,
    manual_row: dict[str, str],
) -> ClassificationResult:
    """Build a ClassificationResult from a manual review ledger row."""
    category = (manual_row.get("final_source_category") or "").strip()
    subtype = (manual_row.get("final_source_subtype") or "").strip()
    notes = (manual_row.get("review_decision_notes") or "").strip()

    # Map to the enum (incorrect_reference is not in the enum, handle specially).
    try:
        source_type = SourceCategory(category)
    except ValueError:
        # Covers incorrect_reference and any other non-LLM category.
        source_type = SourceCategory.unclear_manual_review

    # For incorrect_reference, force specific handling downstream.
    is_incorrect_ref = category == "incorrect_reference" or subtype == "incorrect_reference"

    return ClassificationResult(
        paper_id=paper_id,
        source_type=source_type,
        original_sps_spectrum_data=OriginalSpsData.unclear,
        contains_individual_level_data=False,
        contains_group_level_data=False,
        manual_review_required=False,
        confidence=Confidence.high,
        likely_sps_case_count=None,
        count_confidence=None,
        count_manual_review_required=False,
        count_reasoning_summary="",
        reasoning_summary=f"Manual review: {notes}" if notes else "Manual review override.",
        evidence=[],
        validator_flags=[],
        classification_source="manual_review",
        # Override the source_type value in the registry row for incorrect_reference.
        source_subtype=subtype if is_incorrect_ref else "",
    )


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_paper(
    *,
    paper_id: str,
    reference_row: dict[str, str],
    text_record: dict[str, Any],
    preferred_record: dict[str, Any] | None,
    preferred_text_source: str,
    trim_row: dict[str, str],
    manual_row: dict[str, str] | None,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
) -> ClassificationResult:
    """Process a single paper through the full classification flow.

    Returns a ``ClassificationResult`` with routing fields derived.
    """
    # 1. Manual override check.
    if manual_row:
        result = _build_manual_override_result(paper_id, manual_row)
        proceedings_detected = (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
        trim_status = (trim_row.get("trim_status") or "").strip()
        # For incorrect_reference, override source_type in the final row.
        cat_str = (manual_row.get("final_source_category") or "").strip()
        if cat_str == "incorrect_reference":
            result.derive_routing_fields(
                proceedings_detected=proceedings_detected,
                trim_status=trim_status,
            )
            # Manually fix the fields that derive_routing_fields cannot set for incorrect_reference.
            result.langextract_mode = "incorrect_reference"
            result.langextract_eligible = False
            result.recommended_next_action = "excluded_incorrect_reference"
        else:
            result.derive_routing_fields(
                proceedings_detected=proceedings_detected,
                trim_status=trim_status,
            )
        return result

    # 2. Assemble payload.
    payload = assemble_payload(
        paper_id=paper_id,
        reference_row=reference_row,
        text_record=text_record,
        preferred_record=preferred_record,
        preferred_text_source=preferred_text_source,
        trim_row=trim_row,
    )

    # 3. LLM classification (with retry).
    try:
        llm_output, model_id = _classify_with_retry(payload, model=model, api_key=api_key)
    except Exception as exc:
        logger.error("API failure for %s, cannot classify: %s", paper_id, exc)
        raise

    # 4. Validate.
    flags, worst = run_validators(llm_output, payload)
    validated_output = apply_validator_effects(llm_output, flags, worst)

    # 5. Adjudicate if needed.
    adjudicated = False
    if needs_adjudication(llm_output, worst):
        logger.info("Adjudicating %s (flags: %s)", paper_id, flags)
        try:
            adj_output, adj_model_id = _adjudicate_with_retry(
                payload, llm_output, flags, model=model, api_key=api_key
            )
            adjudicated = True
            model_id = adj_model_id
            # Re-validate the adjudicated output.
            adj_flags, adj_worst = run_validators(adj_output, payload)
            all_flags = flags + [f"ADJ:{f}" for f in adj_flags]
            if adj_worst >= Severity.REJECT:
                # Force unclear after failed adjudication.
                validated_output = apply_validator_effects(adj_output, all_flags, adj_worst)
            else:
                validated_output = apply_validator_effects(adj_output, all_flags, adj_worst)
            flags = all_flags
        except Exception as exc:
            logger.warning("Adjudication failed for %s: %s — using validated output", paper_id, exc)
            flags.append("ADJUDICATION_FAILED")

    # 6. Build result.
    proceedings_detected = payload.proceedings_detected
    trim_status = payload.trim_status

    result = ClassificationResult(
        paper_id=paper_id,
        source_type=validated_output.source_type,
        original_sps_spectrum_data=validated_output.original_sps_spectrum_data,
        contains_individual_level_data=validated_output.contains_individual_level_data,
        contains_group_level_data=validated_output.contains_group_level_data,
        manual_review_required=validated_output.manual_review_required,
        confidence=validated_output.confidence,
        likely_sps_case_count=validated_output.likely_sps_case_count,
        count_confidence=validated_output.count_confidence,
        count_manual_review_required=validated_output.count_manual_review_required,
        count_reasoning_summary=validated_output.count_reasoning_summary,
        reasoning_summary=validated_output.reasoning_summary,
        evidence=validated_output.evidence,
        validator_flags=flags,
        classification_source="llm",
        model_id=model_id,
        adjudicated=adjudicated,
    )
    result.derive_routing_fields(
        proceedings_detected=proceedings_detected,
        trim_status=trim_status,
    )
    return result


def result_to_registry_row(
    result: ClassificationResult,
    *,
    reference_row: dict[str, str],
    text_json_path: str,
    preferred_text_json_path: str,
    preferred_text_source: str,
    proceedings_detected: bool,
    trim_status: str,
    categorisation_version: str,
) -> dict[str, str]:
    """Convert a ClassificationResult to a flat registry-compatible row."""
    # For manual override incorrect_reference, use the raw category.
    source_category = result.source_type.value
    if result.classification_source == "manual_review" and result.langextract_mode == "incorrect_reference":
        source_category = "incorrect_reference"

    row = result.to_registry_row(
        covidence_id=(reference_row.get("Covidence") or "").strip(),
        title=(reference_row.get("Title") or "").strip(),
        authors=(reference_row.get("Authors") or "").strip(),
        published_year=(reference_row.get("Published Year") or "").strip(),
        journal=(reference_row.get("Journal") or "").strip(),
        tags=(reference_row.get("Tags") or "").strip(),
        notes=(reference_row.get("Notes") or "").strip(),
        text_json_path=text_json_path,
        preferred_text_json_path=preferred_text_json_path,
        preferred_text_source=preferred_text_source,
        proceedings_detected=proceedings_detected,
        trim_status=trim_status,
        categorisation_version=categorisation_version,
        categorised_at_utc=_now_utc_iso(),
    )
    # Override source_category for incorrect_reference.
    row["source_category"] = source_category
    return row


def result_to_count_registry_row(
    result: ClassificationResult,
    *,
    reference_row: dict[str, str],
    preferred_text_json_path: str,
    preferred_text_source: str,
    count_version: str,
) -> dict[str, str]:
    row = result.to_count_registry_row(
        covidence_id=(reference_row.get("Covidence") or "").strip(),
        title=(reference_row.get("Title") or "").strip(),
        authors=(reference_row.get("Authors") or "").strip(),
        preferred_text_json_path=preferred_text_json_path,
        preferred_text_source=preferred_text_source,
        count_version=count_version,
        counted_at_utc=_now_utc_iso(),
    )
    if result.classification_source == "manual_review" and result.langextract_mode == "incorrect_reference":
        row["source_category"] = "incorrect_reference"
    return row
