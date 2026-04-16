from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import re

from src.pipelines.stage06_counting.models import CountCandidatePackage, LLMCountDecisionOutput


class Severity(IntEnum):
    PASS = 0
    WARNING = 1
    DOWNGRADE = 2
    REJECT = 3


@dataclass
class ValidatorResult:
    action: Severity
    flag: str


REASONING_MATCHED_CANDIDATE_RE = re.compile(
    r"\b(?:matching|matches|match(?:es)?|selected|select|choose|chose|prefers?|preferred)\s+candidate\s+(?P<id>cand\d+)\b",
    re.IGNORECASE,
)
REASONING_BOUNDED_ALTERNATIVE_RE = re.compile(
    r"\b(?:"
    r"no listed candidate is exact|"
    r"no listed candidate exactly matches|"
    r"requires? a bounded alternative|"
    r"bounded alternative is warranted|"
    r"bounded alternative warranted|"
    r"candidate\s+cand\d+\s+\(\d+\)\s+is\s+not\s+exact|"
    r"not exact"
    r")\b",
    re.IGNORECASE,
)

MECHANICAL_REJECT_FLAGS = frozenset(
    {
        "COUNT_DECISION_MISSING_CANDIDATE",
        "COUNT_DECISION_UNKNOWN_CANDIDATE",
        "COUNT_ALT_MISSING_VALUE",
        "COUNT_ALT_NO_EVIDENCE",
        "COUNT_DECISION_UNRESOLVED",
    }
)
DONOR_MATERIAL_RE = re.compile(
    r"\b(?:sera?|serum|csf|igg(?:\s+fraction)?|gad65-?ab|specimen|sample|samples|antibod(?:y|ies))\b",
    re.IGNORECASE,
)
SUSPECTED_COHORT_RE = re.compile(r"\b(?:suspected|referred specifically for)\b", re.IGNORECASE)
CONSERVATIVE_FALLBACK_SEMANTIC_FLAGS = frozenset(
    {
        "COUNT_DONOR_MATERIAL_ONLY",
        "COUNT_SUSPECTED_COHORT_WITHOUT_CONFIRMED_SUBGROUP",
        "COUNT_PREFERS_SUSPECTED_OVER_CONFIRMED_SUBGROUP",
        "COUNT_SKIP_CATEGORY_NONZERO",
    }
)


def resolved_count_from_decision(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> int | None:
    if decision.decision_type == "candidate_exact":
        for candidate in package.candidates:
            if candidate.candidate_id == decision.selected_candidate_id:
                return candidate.proposed_count
        return None
    if decision.decision_type == "bounded_alternative":
        return decision.alternative_count
    if decision.decision_type in {"manual_review_required", "unable_to_determine"}:
        return package.preferred_candidate().proposed_count
    return None


def check_candidate_exact_has_selected_candidate(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if decision.decision_type != "candidate_exact":
        return ValidatorResult(Severity.PASS, "")
    if not decision.selected_candidate_id:
        return ValidatorResult(Severity.REJECT, "COUNT_DECISION_MISSING_CANDIDATE")
    if all(candidate.candidate_id != decision.selected_candidate_id for candidate in package.candidates):
        return ValidatorResult(Severity.REJECT, "COUNT_DECISION_UNKNOWN_CANDIDATE")
    return ValidatorResult(Severity.PASS, "")


def check_bounded_alternative_has_count_and_evidence(
    _: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if decision.decision_type != "bounded_alternative":
        return ValidatorResult(Severity.PASS, "")
    if decision.alternative_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_ALT_MISSING_VALUE")
    if not decision.evidence:
        return ValidatorResult(Severity.REJECT, "COUNT_ALT_NO_EVIDENCE")
    return ValidatorResult(Severity.PASS, "")


def check_high_confidence_evidence_count(
    _: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if decision.count_confidence == "high" and len(decision.evidence) < 2:
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_HIGH_CONF_INSUFFICIENT_EVIDENCE")
    return ValidatorResult(Severity.PASS, "")


def check_manual_review_decisions_mark_review(
    _: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if decision.decision_type in {"manual_review_required", "unable_to_determine"} and not decision.count_manual_review_required:
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_DECISION_NO_REVIEW_FLAG")
    return ValidatorResult(Severity.PASS, "")


def check_reasoning_consistent_with_decision_type(
    _: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    summary = str(decision.count_reasoning_summary or "").lower()
    if decision.decision_type == "candidate_exact" and REASONING_BOUNDED_ALTERNATIVE_RE.search(summary):
        return ValidatorResult(Severity.REJECT, "COUNT_REASONING_DECISION_TYPE_CONTRADICTION")
    return ValidatorResult(Severity.PASS, "")


def check_reasoning_consistent_with_selected_candidate(
    _: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if decision.decision_type != "candidate_exact" or not decision.selected_candidate_id:
        return ValidatorResult(Severity.PASS, "")
    summary = str(decision.count_reasoning_summary or "")
    matched_ids = {
        match.group("id").lower()
        for match in REASONING_MATCHED_CANDIDATE_RE.finditer(summary)
        if match.group("id")
    }
    if matched_ids and decision.selected_candidate_id.lower() not in matched_ids:
        return ValidatorResult(Severity.REJECT, "COUNT_REASONING_SELECTED_CANDIDATE_MISMATCH")
    return ValidatorResult(Severity.PASS, "")


def check_fixed_category_constraints(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    resolved_count = resolved_count_from_decision(package, decision)
    if resolved_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_DECISION_UNRESOLVED")
    if package.source_category in {"review_article", "non_clinical_basic_science"} and resolved_count > 0:
        return ValidatorResult(Severity.REJECT, "COUNT_SKIP_CATEGORY_NONZERO")
    if package.source_category == "single_case_report" and resolved_count != 1:
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_SINGLE_CASE_MISMATCH")
    if package.source_subtype == "single_case_conference_abstract" and resolved_count != 1:
        return ValidatorResult(Severity.DOWNGRADE, "COUNT_SINGLE_CASE_CONFERENCE_MISMATCH")
    return ValidatorResult(Severity.PASS, "")


def check_resolved_count_not_above_explicit_sps_subgroup(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if package.explicit_sps_subgroup_count is None:
        return ValidatorResult(Severity.PASS, "")
    resolved_count = resolved_count_from_decision(package, decision)
    if resolved_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_DECISION_UNRESOLVED")
    if resolved_count > package.explicit_sps_subgroup_count:
        return ValidatorResult(Severity.REJECT, "COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP")
    return ValidatorResult(Severity.PASS, "")


def check_uncertain_sps_status_requires_review(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if not package.sps_status_uncertainty_signals:
        return ValidatorResult(Severity.PASS, "")
    resolved_count = resolved_count_from_decision(package, decision)
    if resolved_count is None or resolved_count <= 0:
        return ValidatorResult(Severity.PASS, "")
    if decision.count_manual_review_required:
        return ValidatorResult(Severity.PASS, "")
    return ValidatorResult(Severity.REJECT, "COUNT_SPS_STATUS_UNCERTAIN")


def check_original_cohort_provenance_requires_review(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if not package.original_cohort_provenance_uncertain:
        return ValidatorResult(Severity.PASS, "")
    if decision.count_manual_review_required:
        return ValidatorResult(Severity.PASS, "")
    return ValidatorResult(Severity.REJECT, "COUNT_PROVENANCE_UNCERTAIN")


def check_confirmed_only_guardrail_conflicts(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> ValidatorResult:
    if not package.confirmed_only_guardrail_signals:
        return ValidatorResult(Severity.PASS, "")
    resolved_count = resolved_count_from_decision(package, decision)
    if resolved_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_DECISION_UNRESOLVED")
    if resolved_count <= 0:
        return ValidatorResult(Severity.PASS, "")

    has_donor_material_signal = any(
        DONOR_MATERIAL_RE.search(signal or "") for signal in package.confirmed_only_guardrail_signals
    )
    has_suspected_cohort_signal = any(
        SUSPECTED_COHORT_RE.search(signal or "") for signal in package.confirmed_only_guardrail_signals
    )

    if has_donor_material_signal and package.explicit_sps_subgroup_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_DONOR_MATERIAL_ONLY")
    if has_suspected_cohort_signal and package.explicit_sps_subgroup_count is None:
        return ValidatorResult(Severity.REJECT, "COUNT_SUSPECTED_COHORT_WITHOUT_CONFIRMED_SUBGROUP")
    if (
        has_suspected_cohort_signal
        and package.explicit_sps_subgroup_count is not None
        and resolved_count != package.explicit_sps_subgroup_count
    ):
        return ValidatorResult(Severity.REJECT, "COUNT_PREFERS_SUSPECTED_OVER_CONFIRMED_SUBGROUP")
    return ValidatorResult(Severity.PASS, "")


ALL_VALIDATORS = [
    check_candidate_exact_has_selected_candidate,
    check_bounded_alternative_has_count_and_evidence,
    check_high_confidence_evidence_count,
    check_manual_review_decisions_mark_review,
    check_reasoning_consistent_with_decision_type,
    check_reasoning_consistent_with_selected_candidate,
    check_resolved_count_not_above_explicit_sps_subgroup,
    check_uncertain_sps_status_requires_review,
    check_original_cohort_provenance_requires_review,
    check_confirmed_only_guardrail_conflicts,
    check_fixed_category_constraints,
]


def collect_validator_results(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> list[ValidatorResult]:
    return [validator(package, decision) for validator in ALL_VALIDATORS]


def split_reject_flags(results: list[ValidatorResult]) -> tuple[list[str], list[str]]:
    mechanical_flags: list[str] = []
    semantic_flags: list[str] = []
    for result in results:
        if result.action < Severity.REJECT or not result.flag:
            continue
        if result.flag in MECHANICAL_REJECT_FLAGS:
            mechanical_flags.append(result.flag)
        else:
            semantic_flags.append(result.flag)
    return mechanical_flags, semantic_flags


def run_validators(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> tuple[list[str], Severity]:
    return summarise_validator_results(collect_validator_results(package, decision))


def summarise_validator_results(results: list[ValidatorResult]) -> tuple[list[str], Severity]:
    flags: list[str] = []
    worst = Severity.PASS
    for result in results:
        if result.action > Severity.PASS:
            flags.append(result.flag)
            if result.action > worst:
                worst = result.action
    return flags, worst


def requires_conservative_fallback_for_semantic_conflict(flags: list[str]) -> bool:
    return any(flag in CONSERVATIVE_FALLBACK_SEMANTIC_FLAGS for flag in flags)
