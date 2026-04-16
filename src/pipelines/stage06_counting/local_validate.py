from __future__ import annotations

import re

from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput
from src.pipelines.stage06_counting.models import CountCandidatePackage


DIRECT_SPSD_COUNT_PATTERN = re.compile(
    r"(?:n\s*=\s*|^)(\d+)\s+"
    r"(?:classic\s+sps|stiff[- ]person\s+syndrome|sps-plus|spsd|sps-spectrum|"
    r"progressive\s+encephalomyelitis\s+with\s+rigidity\s+and\s+myoclonus|perm)\b",
    re.IGNORECASE,
)
TREATMENT_STATE_PATTERN = re.compile(
    r"\b(before starting|before treatment|after treatment|after tpe|previously received|"
    r"reported improvement|required fewer|response to|treated with|months after)\b",
    re.IGNORECASE,
)
DONOR_MATERIAL_PATTERN = re.compile(
    r"\b(?:sera?|serum|csf|igg(?:\s+fraction)?|gad65-?ab|specimen|sample|samples|antibod(?:y|ies))\b",
    re.IGNORECASE,
)
SUSPECTED_COHORT_PATTERN = re.compile(r"\b(?:suspected|referred specifically for)\b", re.IGNORECASE)


def _candidate_count_values(package: CountCandidatePackage) -> set[int]:
    return {candidate.proposed_count for candidate in package.candidates}


def _has_direct_named_sps_support(package: CountCandidatePackage, resolved_count: int) -> bool:
    snippets = [
        package.abstract_text,
        package.early_body_text,
        *package.explicit_sps_subgroup_evidence,
        *package.sps_status_uncertainty_signals,
    ]
    for snippet in snippets:
        for match in DIRECT_SPSD_COUNT_PATTERN.finditer(str(snippet or "")):
            if int(match.group(1)) == resolved_count:
                return True
    return False


def validate_local_count_decision(
    package: CountCandidatePackage,
    decision: LocalCountDecisionOutput,
) -> list[str]:
    flags: list[str] = []
    resolved_count = decision.n_spsd_patients
    candidate_counts = _candidate_count_values(package)
    evidence_span = str(decision.evidence_span or "")

    if package.source_category in {"review_article", "non_clinical_basic_science"} and resolved_count > 0:
        flags.append("LOCAL_SKIP_CATEGORY_NONZERO")
    if package.source_category == "single_case_report" and resolved_count != 1:
        flags.append("LOCAL_SINGLE_CASE_MISMATCH")
    if package.source_subtype == "single_case_conference_abstract" and resolved_count != 1:
        flags.append("LOCAL_SINGLE_CASE_CONFERENCE_MISMATCH")
    if package.explicit_sps_subgroup_count is not None and resolved_count > package.explicit_sps_subgroup_count:
        flags.append("LOCAL_COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP")
    if (
        package.explicit_sps_subgroup_basis
        in {
            "diagnosis_specific_enumerated_subgroup_count",
            "diagnosis_specific_group_breakdown_count",
        }
        and package.explicit_sps_subgroup_count is not None
        and resolved_count != package.explicit_sps_subgroup_count
    ):
        flags.append("LOCAL_ENUMERATED_SPS_SUBGROUP_MISMATCH")
    if resolved_count not in candidate_counts and not _has_direct_named_sps_support(package, resolved_count):
        flags.append("LOCAL_COUNT_NOT_IN_CANDIDATES")
    if (
        package.explicit_sps_subgroup_count is not None
        and resolved_count != package.explicit_sps_subgroup_count
        and TREATMENT_STATE_PATTERN.search(evidence_span)
    ):
        flags.append("LOCAL_TREATMENT_STATE_SUBSET_COUNT")
    if package.sps_status_uncertainty_signals and resolved_count > 0 and not decision.needs_review:
        flags.append("LOCAL_SPS_STATUS_UNCERTAIN_NO_REVIEW")
    if package.original_cohort_provenance_uncertain and not decision.needs_review:
        flags.append("LOCAL_PROVENANCE_UNCERTAIN_NO_REVIEW")
    if resolved_count > 0 and package.confirmed_only_guardrail_signals:
        if (
            any(DONOR_MATERIAL_PATTERN.search(signal or "") for signal in package.confirmed_only_guardrail_signals)
            and package.explicit_sps_subgroup_count is None
        ):
            flags.append("LOCAL_DONOR_MATERIAL_NONZERO")
        if any(SUSPECTED_COHORT_PATTERN.search(signal or "") for signal in package.confirmed_only_guardrail_signals):
            if package.explicit_sps_subgroup_count is None:
                flags.append("LOCAL_SUSPECTED_COHORT_NONZERO")
            elif resolved_count != package.explicit_sps_subgroup_count:
                flags.append("LOCAL_CONFIRMED_SUBGROUP_MISMATCH")
    if decision.confidence != "high" and not decision.needs_review:
        flags.append("LOCAL_NON_HIGH_CONFIDENCE_NO_REVIEW")
    return flags
