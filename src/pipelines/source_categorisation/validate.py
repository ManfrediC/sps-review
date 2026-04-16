"""Stage 3: Deterministic validation of LLM classification outputs.

Each validator returns an action (pass, warning, downgrade, reject) and a
flag string. Validators are applied in sequence; the most severe action wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

from src.pipelines.source_categorisation.models import (
    Confidence,
    LLMClassificationOutput,
    OriginalSpsData,
    SourceCategory,
)
from src.pipelines.source_categorisation.prepare import PaperPayload


# ---------------------------------------------------------------------------
# Validator action severity
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    PASS = 0
    WARNING = 1
    DOWNGRADE = 2
    REJECT = 3


@dataclass
class ValidatorResult:
    action: Severity
    flag: str


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def check_incorrect_reference(output: LLMClassificationOutput) -> ValidatorResult:
    """The LLM must never emit ``incorrect_reference``."""
    # The enum already excludes it, but guard against future schema drift.
    if output.source_type.value == "incorrect_reference":
        return ValidatorResult(Severity.REJECT, "LLM_EMITTED_INCORRECT_REFERENCE")
    return ValidatorResult(Severity.PASS, "")


def check_evidence_present(output: LLMClassificationOutput) -> ValidatorResult:
    """At least one evidence item with a non-empty quote."""
    if not output.evidence:
        return ValidatorResult(Severity.REJECT, "NO_EVIDENCE")
    if all(not (e.quote or "").strip() for e in output.evidence):
        return ValidatorResult(Severity.REJECT, "ALL_EVIDENCE_EMPTY")
    return ValidatorResult(Severity.PASS, "")


def check_high_confidence_evidence_count(output: LLMClassificationOutput) -> ValidatorResult:
    """High confidence requires at least 2 evidence items."""
    if output.confidence == Confidence.high and len(output.evidence) < 2:
        return ValidatorResult(Severity.DOWNGRADE, "HIGH_CONF_INSUFFICIENT_EVIDENCE")
    return ValidatorResult(Severity.PASS, "")


def check_review_with_original_data(output: LLMClassificationOutput) -> ValidatorResult:
    """Review / non-clinical should not claim original SPS data."""
    if output.source_type in {
        SourceCategory.review_article,
        SourceCategory.non_clinical_basic_science,
    } and output.original_sps_spectrum_data.value == "yes":
        return ValidatorResult(Severity.WARNING, "SKIP_CATEGORY_CLAIMS_ORIGINAL_DATA")
    return ValidatorResult(Severity.PASS, "")


def check_embedded_review_requirements(output: LLMClassificationOutput) -> ValidatorResult:
    """Embedded-cohort review papers must look like original-data papers."""
    if output.source_type != SourceCategory.review_format_with_embedded_original_cohort:
        return ValidatorResult(Severity.PASS, "")
    if output.original_sps_spectrum_data != OriginalSpsData.yes:
        return ValidatorResult(Severity.REJECT, "EMBEDDED_REVIEW_NO_ORIGINAL_DATA")
    if output.likely_sps_case_count <= 0:
        return ValidatorResult(Severity.REJECT, "EMBEDDED_REVIEW_NONPOSITIVE_COUNT")
    if not output.manual_review_required:
        return ValidatorResult(Severity.DOWNGRADE, "EMBEDDED_REVIEW_NO_MANUAL_REVIEW")
    return ValidatorResult(Severity.PASS, "")


def check_single_case_individual(output: LLMClassificationOutput) -> ValidatorResult:
    """Single case report must have individual-level data."""
    if (
        output.source_type == SourceCategory.single_case_report
        and not output.contains_individual_level_data
    ):
        return ValidatorResult(Severity.REJECT, "SINGLE_CASE_NO_INDIVIDUAL_DATA")
    return ValidatorResult(Severity.PASS, "")


def check_group_study_group_data(output: LLMClassificationOutput) -> ValidatorResult:
    """Observational / interventional studies must have group-level data."""
    if output.source_type in {
        SourceCategory.observational_group_study,
        SourceCategory.interventional_study,
    } and not output.contains_group_level_data:
        return ValidatorResult(Severity.REJECT, "GROUP_STUDY_NO_GROUP_DATA")
    return ValidatorResult(Severity.PASS, "")


def check_conference_metadata_support(
    output: LLMClassificationOutput,
    payload: PaperPayload,
) -> ValidatorResult:
    """Conference abstract should be backed by at least one metadata signal."""
    if output.source_type != SourceCategory.conference_abstract:
        return ValidatorResult(Severity.PASS, "")

    pages_str = (payload.metadata.get("pages") or "").strip()
    issue_str = (payload.metadata.get("issue") or "").strip()
    doi_str = (payload.metadata.get("doi") or "").strip()
    abstract_str = (payload.metadata.get("abstract") or "").strip()

    signals: list[bool] = [
        payload.proceedings_detected,
        bool(re.match(r"^[Ss]\d+", pages_str)),  # supplement page
        "suppl" in issue_str.lower(),
        bool(re.search(r"s\d+", doi_str.lower())),  # supplement DOI
    ]

    # Short page span (≤2 pages).
    page_match = re.match(r"(\d+)\s*[-–]\s*(\d+)", pages_str)
    if page_match:
        span = abs(int(page_match.group(2)) - int(page_match.group(1))) + 1
        signals.append(span <= 2)

    # Short abstract.
    if abstract_str:
        signals.append(len(abstract_str.split()) <= 450)

    # Short text.
    signals.append(payload.text_page_count <= 2)

    if not any(signals) and payload.text_page_count >= 4:
        return ValidatorResult(Severity.WARNING, "CONF_NO_METADATA_SUPPORT")
    return ValidatorResult(Severity.PASS, "")


def check_proceedings_trim_required(
    output: LLMClassificationOutput,
    payload: PaperPayload,
) -> ValidatorResult:
    """Force manual review when proceedings need manual trimming."""
    if payload.proceedings_detected and payload.trim_status == "manual_review_required":
        return ValidatorResult(Severity.DOWNGRADE, "PROCEEDINGS_TRIM_PENDING")
    return ValidatorResult(Severity.PASS, "")


def check_evidence_quality(output: LLMClassificationOutput) -> ValidatorResult:
    """Flag very short evidence quotes."""
    short = [e for e in output.evidence if len((e.quote or "").strip()) < 10]
    if short and len(short) == len(output.evidence):
        return ValidatorResult(Severity.WARNING, "EVIDENCE_TOO_SHORT")
    return ValidatorResult(Severity.PASS, "")


def check_evidence_pages(output: LLMClassificationOutput) -> ValidatorResult:
    """Warning-only: all evidence items lack page numbers."""
    if output.evidence and all(e.page is None for e in output.evidence):
        return ValidatorResult(Severity.WARNING, "EVIDENCE_NO_PAGES")
    return ValidatorResult(Severity.PASS, "")


def check_insufficient_input(
    output: LLMClassificationOutput,
    payload: PaperPayload,
) -> ValidatorResult:
    """Downgrade confidence when input is very thin."""
    abstract = (payload.metadata.get("abstract") or "").strip()
    if not abstract and not payload.text_content.strip():
        return ValidatorResult(Severity.DOWNGRADE, "INSUFFICIENT_INPUT")
    return ValidatorResult(Severity.PASS, "")


def check_count_without_original_data(output: LLMClassificationOutput) -> ValidatorResult:
    """A positive count implies original SPS-spectrum patient data."""
    if output.likely_sps_case_count > 0 and output.original_sps_spectrum_data != OriginalSpsData.yes:
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_WITHOUT_ORIGINAL_DATA")
    return ValidatorResult(Severity.PASS, "")


def check_single_case_count(output: LLMClassificationOutput) -> ValidatorResult:
    """Single-case reports should have count 1."""
    if output.source_type == SourceCategory.single_case_report and output.likely_sps_case_count != 1:
        return ValidatorResult(Severity.DOWNGRADE, "SINGLE_CASE_COUNT_MISMATCH")
    return ValidatorResult(Severity.PASS, "")


def check_skip_category_count(output: LLMClassificationOutput) -> ValidatorResult:
    """Review and non-clinical papers should normally not carry extractable counts."""
    if output.source_type in {
        SourceCategory.review_article,
        SourceCategory.non_clinical_basic_science,
    } and output.likely_sps_case_count > 0:
        return ValidatorResult(Severity.DOWNGRADE, "SKIP_CATEGORY_NONZERO_COUNT")
    return ValidatorResult(Severity.PASS, "")


def check_count_data_level_support(output: LLMClassificationOutput) -> ValidatorResult:
    """Positive counts should align with some patient-data signal."""
    if (
        output.likely_sps_case_count > 0
        and not output.contains_individual_level_data
        and not output.contains_group_level_data
    ):
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_WITHOUT_DATA_LEVEL_SIGNAL")
    return ValidatorResult(Severity.PASS, "")


def check_low_count_confidence_requires_review(output: LLMClassificationOutput) -> ValidatorResult:
    """Non-high count confidence should trigger count review."""
    if output.count_confidence != Confidence.high and not output.count_manual_review_required:
        return ValidatorResult(Severity.WARNING, "COUNT_NON_HIGH_CONF_NO_REVIEW")
    return ValidatorResult(Severity.PASS, "")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_VALIDATORS_OUTPUT_ONLY = [
    check_incorrect_reference,
    check_evidence_present,
    check_high_confidence_evidence_count,
    check_review_with_original_data,
    check_embedded_review_requirements,
    check_single_case_individual,
    check_group_study_group_data,
    check_evidence_quality,
    check_evidence_pages,
    check_count_without_original_data,
    check_single_case_count,
    check_skip_category_count,
    check_count_data_level_support,
    check_low_count_confidence_requires_review,
]

ALL_VALIDATORS_WITH_PAYLOAD = [
    check_conference_metadata_support,
    check_proceedings_trim_required,
    check_insufficient_input,
]


def run_validators(
    output: LLMClassificationOutput,
    payload: PaperPayload,
) -> tuple[list[str], Severity]:
    """Run all validators and return (flags, worst_severity).

    Side-effect free — does not mutate *output*.
    """
    flags: list[str] = []
    worst = Severity.PASS

    for validator in ALL_VALIDATORS_OUTPUT_ONLY:
        result = validator(output)
        if result.action > Severity.PASS:
            flags.append(result.flag)
            if result.action > worst:
                worst = result.action

    for validator in ALL_VALIDATORS_WITH_PAYLOAD:
        result = validator(output, payload)
        if result.action > Severity.PASS:
            flags.append(result.flag)
            if result.action > worst:
                worst = result.action

    return flags, worst


def apply_validator_effects(
    output: LLMClassificationOutput,
    flags: list[str],
    worst: Severity,
) -> LLMClassificationOutput:
    """Return a copy of *output* with validator effects applied.

    - ``DOWNGRADE``: lower confidence and/or force manual review.
    - ``REJECT``: force ``unclear_manual_review``.
    """
    data = output.model_dump()
    category_downgrade_flags = {
        "HIGH_CONF_INSUFFICIENT_EVIDENCE",
        "PROCEEDINGS_TRIM_PENDING",
        "INSUFFICIENT_INPUT",
    }
    count_downgrade_flags = {
        "COUNT_WITHOUT_ORIGINAL_DATA",
        "SINGLE_CASE_COUNT_MISMATCH",
        "SKIP_CATEGORY_NONZERO_COUNT",
        "COUNT_WITHOUT_DATA_LEVEL_SIGNAL",
        "COUNT_NON_HIGH_CONF_NO_REVIEW",
    }

    if worst >= Severity.REJECT:
        data["source_type"] = SourceCategory.unclear_manual_review.value
        data["manual_review_required"] = True
        data["confidence"] = Confidence.low.value
    elif any(flag in category_downgrade_flags for flag in flags):
        data["manual_review_required"] = True
        if data["confidence"] in {Confidence.high, Confidence.high.value}:
            data["confidence"] = Confidence.medium.value
        if "INSUFFICIENT_INPUT" in flags:
            data["confidence"] = Confidence.low.value

    if "EMBEDDED_REVIEW_NO_MANUAL_REVIEW" in flags:
        data["manual_review_required"] = True

    if any(flag in count_downgrade_flags for flag in flags):
        data["count_manual_review_required"] = True
        if data["count_confidence"] in {Confidence.high, Confidence.high.value}:
            data["count_confidence"] = Confidence.medium.value
        if "COUNT_WITHOUT_ORIGINAL_DATA" in flags:
            data["count_confidence"] = Confidence.low.value

    return LLMClassificationOutput.model_validate(data)
