"""Pydantic models for LLM-based source categorisation.

Defines the structured output schema that the LLM must conform to,
evidence items, and deterministic routing-field derivation.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.pipelines._source_routing import (
    bool_text,
    infer_case_split_candidate,
    infer_eligibility,
    infer_mode,
    normalize_category_subtype,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceCategory(str, Enum):
    """Valid LLM-emitted source categories.

    Note: ``incorrect_reference`` is intentionally excluded — it is only
    assigned via the manual override ledger, never by the LLM.
    """

    conference_abstract = "conference_abstract"
    review_article = "review_article"
    review_format_with_embedded_original_cohort = "review_format_with_embedded_original_cohort"
    single_case_report = "single_case_report"
    case_series_or_multi_case = "case_series_or_multi_case"
    observational_group_study = "observational_group_study"
    interventional_study = "interventional_study"
    lab_heavy_clinical_or_translational = "lab_heavy_clinical_or_translational"
    non_clinical_basic_science = "non_clinical_basic_science"
    unclear_manual_review = "unclear_manual_review"


class OriginalSpsData(str, Enum):
    yes = "yes"
    no = "no"
    unclear = "unclear"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of textual evidence supporting the classification."""

    quote: str = Field(..., description="Verbatim or near-verbatim text from the paper.")
    page: int | None = Field(None, description="Page number (1-indexed) if identifiable.")
    section: str | None = Field(None, description="Section name if identifiable.")
    supports: str = Field(
        ...,
        description="What this evidence supports, e.g. 'original cohort data', 'single patient'.",
    )


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------


class LLMClassificationOutput(BaseModel):
    """Structured output schema for the LLM classification call.

    This model is used both for Pydantic validation and as the source for
    the JSON Schema passed to the OpenAI Structured Outputs API.
    """

    source_type: SourceCategory = Field(
        ..., description="The assigned source category for this paper."
    )
    original_sps_spectrum_data: OriginalSpsData = Field(
        ...,
        description="Whether the paper contains original SPS-spectrum patient data.",
    )
    contains_individual_level_data: bool = Field(
        ...,
        description="Whether the paper reports individual-level (per-patient) clinical data.",
    )
    contains_group_level_data: bool = Field(
        ...,
        description="Whether the paper reports group-level (aggregated) clinical data.",
    )
    manual_review_required: bool = Field(
        ...,
        description="Whether this paper should be flagged for human review.",
    )
    confidence: Confidence = Field(
        ..., description="Confidence in the classification."
    )
    likely_sps_case_count: int = Field(
        ...,
        ge=0,
        description="Estimated count of original extractable SPS-spectrum patients in this paper.",
    )
    count_confidence: Confidence = Field(
        ...,
        description="Confidence in the SPS-spectrum patient count.",
    )
    count_manual_review_required: bool = Field(
        ...,
        description="Whether the SPS-spectrum patient count should be checked by a human reviewer.",
    )
    count_reasoning_summary: str = Field(
        ...,
        description="1-3 sentence explanation of how the SPS-spectrum patient count was derived.",
    )
    reasoning_summary: str = Field(
        ...,
        description="1-3 sentence explanation of the classification decision.",
    )
    evidence: list[EvidenceItem] = Field(
        ...,
        min_length=1,
        description="Textual evidence supporting the classification (minimum 1 item).",
    )


# ---------------------------------------------------------------------------
# Validated result (post-validator enrichment)
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """Full classification result including LLM output, validator flags,
    and deterministically derived routing fields.
    """

    paper_id: str
    source_type: SourceCategory
    original_sps_spectrum_data: OriginalSpsData
    contains_individual_level_data: bool
    contains_group_level_data: bool
    manual_review_required: bool
    confidence: Confidence
    likely_sps_case_count: int | None = None
    count_confidence: Confidence | None = None
    count_manual_review_required: bool = False
    count_reasoning_summary: str = ""
    reasoning_summary: str
    evidence: list[EvidenceItem]
    validator_flags: list[str] = Field(default_factory=list)
    classification_source: Literal["llm", "manual_review", "heuristic_fallback"] = "llm"
    model_id: str = ""
    adjudicated: bool = False

    # -- Derived routing fields (populated by derive_routing_fields) --------
    source_subtype: str = ""
    case_series_split_candidate: bool = False
    langextract_mode: str = ""
    langextract_eligible: bool = False
    recommended_next_action: str = ""

    def count_eligible(self) -> bool:
        return self.source_type.value in {
            "single_case_report",
            "case_series_or_multi_case",
            "observational_group_study",
            "interventional_study",
            "lab_heavy_clinical_or_translational",
            "conference_abstract",
            "review_format_with_embedded_original_cohort",
        }

    def derive_routing_fields(
        self,
        proceedings_detected: bool = False,
        trim_status: str = "",
    ) -> None:
        """Populate downstream routing fields from the classification."""
        category = self.source_type.value
        # Derive subtype from category + data-level flags.
        self.source_subtype = _derive_subtype(
            category, self.contains_individual_level_data, self.contains_group_level_data
        )
        cat_norm, sub_norm = normalize_category_subtype(category, self.source_subtype)
        self.case_series_split_candidate = infer_case_split_candidate(cat_norm, sub_norm)
        self.langextract_mode = infer_mode(cat_norm, sub_norm)
        self.langextract_eligible = infer_eligibility(cat_norm, sub_norm)
        self.recommended_next_action = _derive_next_action(
            category=cat_norm,
            subtype=sub_norm,
            langextract_mode=self.langextract_mode,
            langextract_eligible=self.langextract_eligible,
            manual_review_required=self.manual_review_required,
            proceedings_detected=proceedings_detected,
            trim_status=trim_status,
        )

    def to_registry_row(
        self,
        *,
        covidence_id: str = "",
        title: str = "",
        authors: str = "",
        published_year: str = "",
        journal: str = "",
        tags: str = "",
        notes: str = "",
        text_json_path: str = "",
        preferred_text_json_path: str = "",
        preferred_text_source: str = "",
        proceedings_detected: bool = False,
        trim_status: str = "",
        categorisation_version: str = "",
        categorised_at_utc: str = "",
    ) -> dict[str, str]:
        """Convert to a flat dictionary matching the registry CSV schema."""
        reason_parts: list[str] = []
        if self.validator_flags:
            reason_parts.append(f"validator_flags={'; '.join(self.validator_flags)}")
        if self.reasoning_summary:
            reason_parts.append(self.reasoning_summary)

        return {
            "paper_id": self.paper_id,
            "covidence_id": covidence_id,
            "title": title,
            "authors": authors,
            "published_year": published_year,
            "journal": journal,
            "tags": tags,
            "notes": notes,
            "text_json_path": text_json_path,
            "preferred_text_json_path": preferred_text_json_path,
            "preferred_text_source": preferred_text_source,
            "proceedings_detected": bool_text(proceedings_detected),
            "trim_status": trim_status,
            "source_category": self.source_type.value,
            "source_subtype": self.source_subtype,
            "classification_confidence": self.confidence.value,
            "likely_case_count": (
                "" if self.likely_sps_case_count is None else str(self.likely_sps_case_count)
            ),
            "contains_individual_level_data": bool_text(self.contains_individual_level_data),
            "contains_group_level_data": bool_text(self.contains_group_level_data),
            "case_series_split_candidate": bool_text(self.case_series_split_candidate),
            "preferred_langextract_mode": self.langextract_mode,
            "langextract_eligible": bool_text(self.langextract_eligible),
            "manual_review_required": bool_text(self.manual_review_required),
            "recommended_next_action": self.recommended_next_action,
            "conference_marker_hits": "",
            "review_marker_hits": "",
            "case_report_marker_hits": "",
            "multi_case_marker_hits": "",
            "observational_marker_hits": "",
            "interventional_marker_hits": "",
            "non_clinical_marker_hits": "",
            "translational_marker_hits": "",
            "patient_label_count": "",
            "categorisation_reason": " | ".join(reason_parts),
            "categorisation_version": categorisation_version,
            "categorised_at_utc": categorised_at_utc,
        }

    def to_count_registry_row(
        self,
        *,
        covidence_id: str = "",
        title: str = "",
        authors: str = "",
        preferred_text_json_path: str = "",
        preferred_text_source: str = "",
        count_version: str = "",
        counted_at_utc: str = "",
    ) -> dict[str, str]:
        reason_parts: list[str] = []
        if self.count_reasoning_summary:
            reason_parts.append(self.count_reasoning_summary)
        if self.validator_flags:
            reason_parts.append(f"validator_flags={'; '.join(self.validator_flags)}")

        return {
            "paper_id": self.paper_id,
            "covidence_id": covidence_id,
            "title": title,
            "authors": authors,
            "source_category": self.source_type.value,
            "source_subtype": self.source_subtype,
            "preferred_text_json_path": preferred_text_json_path,
            "preferred_text_source": preferred_text_source,
            "count_eligible": bool_text(self.count_eligible()),
            "likely_sps_case_count": (
                "" if self.likely_sps_case_count is None else str(self.likely_sps_case_count)
            ),
            "count_confidence": "" if self.count_confidence is None else self.count_confidence.value,
            "count_basis": "llm_joint_extraction" if self.likely_sps_case_count is not None else "",
            "count_manual_review_required": bool_text(self.count_manual_review_required),
            "count_reason": " | ".join(reason_parts),
            "count_version": count_version,
            "counted_at_utc": counted_at_utc,
        }


# ---------------------------------------------------------------------------
# Subtype derivation
# ---------------------------------------------------------------------------


def _derive_subtype(category: str, individual: bool, group: bool) -> str:
    """Derive the source subtype from category and data-level flags."""
    mapping: dict[str, str] = {
        "single_case_report": "case_report",
        "case_series_or_multi_case": "case_series",
        "observational_group_study": "retrospective_or_cohort_group_study",
        "interventional_study": "controlled_or_therapeutic_group_study",
        "lab_heavy_clinical_or_translational": "group_or_frequency_focused_lab_clinical_study",
        "non_clinical_basic_science": "basic_science_or_mechanistic",
        "review_article": "review",
        "review_format_with_embedded_original_cohort": "embedded_original_cohort",
        "unclear_manual_review": "unclear",
    }
    if category == "conference_abstract":
        if individual and not group:
            return "single_case_conference_abstract"
        if group and not individual:
            return "group_conference_abstract"
        if individual and group:
            return "case_series_conference_abstract"
        return "single_case_conference_abstract"
    return mapping.get(category, "")


# ---------------------------------------------------------------------------
# Next-action derivation
# ---------------------------------------------------------------------------


def _derive_next_action(
    *,
    category: str,
    subtype: str,
    langextract_mode: str,
    langextract_eligible: bool,
    manual_review_required: bool,
    proceedings_detected: bool,
    trim_status: str,
) -> str:
    """Derive the recommended next action for a classified paper."""
    if category == "unclear_manual_review":
        return "review_source_category"
    if not langextract_eligible:
        return "skip_langextract"
    if manual_review_required:
        if langextract_mode in {"individual", "group"}:
            return "review_source_category_then_langextract"
        if langextract_mode == "individual_case_split":
            return "review_source_category_then_split"
        return "review_source_category"
    if proceedings_detected and trim_status == "manual_review_required":
        return "trim_or_review_proceedings"
    if langextract_mode == "individual_case_split":
        return "split_cases_then_langextract"
    if langextract_mode == "individual":
        return "run_langextract_individual"
    if langextract_mode == "group":
        return "run_langextract_group"
    return "review_source_category"
