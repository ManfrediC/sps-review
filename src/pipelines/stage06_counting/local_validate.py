from __future__ import annotations

from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput
from src.pipelines.stage06_counting.models import CountCandidatePackage


def validate_local_count_decision(
    package: CountCandidatePackage,
    decision: LocalCountDecisionOutput,
) -> list[str]:
    flags: list[str] = []
    resolved_count = decision.n_spsd_patients

    if package.source_category in {"review_article", "non_clinical_basic_science"} and resolved_count > 0:
        flags.append("LOCAL_SKIP_CATEGORY_NONZERO")
    if package.source_category == "single_case_report" and resolved_count != 1:
        flags.append("LOCAL_SINGLE_CASE_MISMATCH")
    if package.source_subtype == "single_case_conference_abstract" and resolved_count != 1:
        flags.append("LOCAL_SINGLE_CASE_CONFERENCE_MISMATCH")
    if package.explicit_sps_subgroup_count is not None and resolved_count > package.explicit_sps_subgroup_count:
        flags.append("LOCAL_COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP")
    if package.sps_status_uncertainty_signals and resolved_count > 0 and not decision.needs_review:
        flags.append("LOCAL_SPS_STATUS_UNCERTAIN_NO_REVIEW")
    if decision.confidence != "high" and not decision.needs_review:
        flags.append("LOCAL_NON_HIGH_CONFIDENCE_NO_REVIEW")
    return flags
