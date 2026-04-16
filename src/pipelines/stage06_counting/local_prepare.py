from __future__ import annotations

import json
import re

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


def _clip(text: str, *, limit: int = 420) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _count_focused_clip(text: str, *, count: int | None, limit: int = 420) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    if count is None:
        return _clip(compact, limit=limit)

    match = re.search(rf"\b{re.escape(str(count))}\b", compact)
    if match is None:
        return _clip(compact, limit=limit)

    half = max(0, limit // 2)
    start = max(0, match.start() - half)
    end = min(len(compact), start + limit)
    if end - start < limit:
        start = max(0, end - limit)
    snippet = compact[start:end].strip()
    if start > 0:
        snippet = "..." + snippet.lstrip(".")
    if end < len(compact):
        snippet = snippet.rstrip(".") + "..."
    return snippet


def _candidate_count_values(package: CountCandidatePackage) -> list[int]:
    return sorted({candidate.proposed_count for candidate in package.candidates})


def _direct_named_sps_count_lines(package: CountCandidatePackage) -> list[str]:
    snippets = [
        package.abstract_text,
        package.early_body_text,
        *package.explicit_sps_subgroup_evidence,
        *package.sps_status_uncertainty_signals,
    ]
    matches: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        compact = _clip(snippet, limit=280)
        if not compact or not DIRECT_SPSD_COUNT_PATTERN.search(compact):
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        matches.append(compact)
    return matches


def _treatment_state_subset_lines(package: CountCandidatePackage) -> list[str]:
    snippets = [
        package.abstract_text,
        package.early_body_text,
        *package.explicit_sps_subgroup_evidence,
        *[candidate.evidence_text for candidate in package.candidates[:3]],
    ]
    matches: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        compact = _clip(snippet, limit=280)
        if not compact or not TREATMENT_STATE_PATTERN.search(compact):
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        matches.append(compact)
    return matches


def _preferred_candidate_summary_lines(package: CountCandidatePackage) -> list[str]:
    preferred = package.preferred_candidate()
    fallback = package.fallback_candidate()
    lines = [
        f"preferred_deterministic_count: {preferred.proposed_count}",
        f"preferred_deterministic_basis: {preferred.count_basis}",
        f"preferred_deterministic_confidence: {preferred.count_confidence}",
        f"preferred_deterministic_manual_review_required: {preferred.manual_review_required}",
        f"fallback_candidate_count: {fallback.proposed_count}",
        f"fallback_candidate_basis: {fallback.count_basis}",
    ]
    if preferred.evidence_text:
        lines.append(
            "preferred_deterministic_evidence: "
            + _count_focused_clip(preferred.evidence_text, count=preferred.proposed_count, limit=420)
        )
    if package.explicit_sps_subgroup_count is not None:
        subgroup_candidate = next(
            (
                candidate
                for candidate in package.candidates
                if candidate.proposed_count == package.explicit_sps_subgroup_count
                and candidate.count_basis.startswith("diagnosis_specific_")
            ),
            None,
        )
        if subgroup_candidate is not None:
            lines.extend(
                [
                    f"explicit_subgroup_candidate_count: {subgroup_candidate.proposed_count}",
                    f"explicit_subgroup_candidate_basis: {subgroup_candidate.count_basis}",
                    "preferred_vs_explicit_subgroup_status: "
                    + (
                        "aligned"
                        if subgroup_candidate.proposed_count == preferred.proposed_count
                        else "disagreement"
                    ),
                ]
            )
    if package.source_category == "single_case_report" or package.source_subtype == "single_case_conference_abstract":
        lines.append("single_case_expected_count: 1")
        if preferred.proposed_count != 1:
            lines.append("single_case_conflict_status: preferred_count_conflicts_with_single_case_routing")
    if package.explicit_sps_subgroup_basis == "diagnosis_specific_suffix_count":
        lines.append("suffix_count_conflict_status: suspicious_suffix_count_requires_stronger_support")
    return lines


def _explicit_subgroup_lines(package: CountCandidatePackage) -> list[str]:
    if package.explicit_sps_subgroup_count is None:
        return ["none"]

    lines = [
        f"explicit_sps_subgroup_count: {package.explicit_sps_subgroup_count}",
        f"explicit_sps_subgroup_basis: {package.explicit_sps_subgroup_basis or 'unknown'}",
    ]
    if package.explicit_sps_subgroup_basis in {
        "diagnosis_specific_enumerated_subgroup_count",
        "diagnosis_specific_group_breakdown_count",
    }:
        lines.append(
            "explicit_sps_subgroup_interpretation: This is the deterministic SPS-spectrum subtotal from a diagnosis breakdown; keep separately named SPS-spectrum diagnoses such as SPS and PERM unless overlap is explicitly stated."
        )
    lines.extend(
        [
            f"evidence: {_count_focused_clip(snippet, count=package.explicit_sps_subgroup_count, limit=420)}"
            for snippet in (
                package.explicit_sps_subgroup_evidence or ["[no subgroup evidence excerpt available]"]
            )
        ]
    )
    return lines


def _candidate_summary_lines(package: CountCandidatePackage) -> list[str]:
    lines: list[str] = []
    for candidate in package.candidates[:4]:
        blockers = ", ".join(candidate.blockers) if candidate.blockers else "none"
        lines.append(
            " | ".join(
                [
                    f"{candidate.candidate_id}",
                    f"count={candidate.proposed_count}",
                    f"basis={candidate.count_basis}",
                    f"confidence={candidate.count_confidence}",
                    f"review={candidate.manual_review_required}",
                    f"blockers={blockers}",
                ]
            )
        )
        if candidate.evidence_text:
            lines.append(
                "evidence: "
                + _count_focused_clip(candidate.evidence_text, count=candidate.proposed_count, limit=320)
            )
    return lines


def _local_safety_hint_lines(package: CountCandidatePackage) -> list[str]:
    candidate_counts = _candidate_count_values(package)
    direct_named_counts = _direct_named_sps_count_lines(package)
    treatment_subset_lines = _treatment_state_subset_lines(package)
    lines = [
        "If you mention any alternative count different from the top-level count, set needs_review=true.",
        "Never return alias keys such as count, evidence, or granularity.",
        "Never return string-only possibilities; each possibility must be a JSON object.",
        f"Prefer a top-level count from deterministic_candidate_counts={candidate_counts}.",
        "You may choose a different top-level count only when the evidence pack contains a direct SPS-spectrum subgroup quote that clearly supports that alternative number.",
        "If a sentence lists several different diagnoses, count only the explicitly SPS-spectrum diagnosis entries, not the full mixed-diagnosis total.",
        "Do not use pre-treatment, post-treatment, response, or medication-usage subsets as the cohort size unless the text explicitly says that subset is the full SPS-spectrum cohort.",
    ]
    if package.source_category == "single_case_report" or package.source_subtype == "single_case_conference_abstract":
        lines.append(
            "This paper is already routed as a single-case source. Prefer 1 unless the evidence explicitly reports more than one original SPS-spectrum patient in this paper."
        )
        if package.explicit_sps_subgroup_basis == "diagnosis_specific_suffix_count":
            lines.append(
                "A bare suffix count like SPS (3) is not enough to override single-case routing on its own."
            )
    if package.explicit_sps_subgroup_basis == "diagnosis_specific_enumerated_subgroup_count":
        lines.append(
            "When an enumerated subgroup list separately names SPS and PERM, count both SPS-spectrum diagnoses unless overlap is explicitly stated."
        )
    if package.source_category == "review_format_with_embedded_original_cohort":
        lines.append(
            "This is a review-format paper with an embedded original cohort. You may count the explicit cohort, but keep needs_review=true unless provenance overlap is clearly resolved."
        )
    if package.explicit_sps_subgroup_count is not None:
        lines.append(
            "An explicit deterministic SPS-spectrum subtotal is provided below. If you choose a different count, include that subtotal as an alternative and set needs_review=true."
        )
        subgroup_candidate = next(
            (
                candidate
                for candidate in package.candidates
                if candidate.proposed_count == package.explicit_sps_subgroup_count
                and candidate.count_basis.startswith("diagnosis_specific_")
            ),
            None,
        )
        if subgroup_candidate is not None and subgroup_candidate.proposed_count != package.preferred_candidate().proposed_count:
            lines.append(
                "The preferred broad-count candidate disagrees with the explicit SPS-spectrum subtotal, so treat this as a real conflict rather than silently collapsing to one number."
            )
    if package.explicit_sps_subgroup_basis == "diagnosis_specific_suffix_count":
        lines.append(
            "Parenthetical suffix counts can be citations or OCR artefacts. Do not trust them over clear case-report framing or explicit patient statements."
        )
    if direct_named_counts:
        lines.append(
            "A direct named SPS-spectrum subgroup quote is present below. That kind of quote can justify a non-candidate count if it is explicit and more specific than the broader totals."
        )
    if treatment_subset_lines:
        lines.append(
            "Treatment-state subset cues are present below. Treat them as state or treatment subsets unless the text explicitly says they define the full SPS-spectrum cohort."
        )
    if package.original_cohort_provenance_uncertain:
        lines.append(
            "Original-cohort provenance is uncertain in this paper, so keep needs_review=true even if the numeric count itself looks explicit."
        )
    if package.preferred_candidate().manual_review_required:
        lines.append(
            "The preferred deterministic candidate already requires review, so a confident no-review answer needs especially strong direct evidence."
        )
    return lines


def _key_evidence_lines(package: CountCandidatePackage) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    def _push(label: str, text: str, *, limit: int = 420, count: int | None = None) -> None:
        compact = _count_focused_clip(text, count=count, limit=limit)
        if not compact:
            return
        normalised = compact.lower()
        if normalised in seen:
            return
        seen.add(normalised)
        lines.append(f"{label}: {compact}")

    if package.abstract_text:
        _push("abstract", package.abstract_text, limit=420, count=package.preferred_candidate().proposed_count)
    for snippet in package.explicit_sps_subgroup_evidence:
        _push(
            "explicit_subgroup_evidence",
            snippet,
            limit=420,
            count=package.explicit_sps_subgroup_count,
        )
    for candidate in package.candidates[:3]:
        _push(
            f"{candidate.candidate_id}_evidence",
            candidate.evidence_text,
            limit=320,
            count=candidate.proposed_count,
        )
    for signal in package.sps_status_uncertainty_signals[:3]:
        _push("uncertainty_signal", signal, limit=280)
    if not lines and package.llm_evidence_text:
        for raw_line in str(package.llm_evidence_text).splitlines():
            stripped = raw_line.strip().lstrip("-").strip()
            if not stripped or stripped.endswith(":"):
                continue
            _push("llm_evidence", stripped, limit=320)
            if len(lines) >= 4:
                break
    return lines or ["none"]


def format_candidate_package_for_local_llm(package: CountCandidatePackage) -> str:
    subgroup_lines = _explicit_subgroup_lines(package)
    uncertainty_lines = package.sps_status_uncertainty_signals or ["none"]
    provenance_lines = package.original_cohort_provenance_signals or ["none"]
    guardrail_lines = package.confirmed_only_guardrail_signals or ["none"]
    notes = package.candidate_generation_notes or ["none"]
    direct_named_counts = _direct_named_sps_count_lines(package) or ["none"]
    treatment_subset_lines = _treatment_state_subset_lines(package) or ["none"]
    candidate_counts = _candidate_count_values(package)
    parts = [
        f"Paper ID: {package.paper_id}",
        "",
        "## Fixed routing context",
        f"- source_category: {package.source_category or 'unknown'}",
        f"- source_subtype: {package.source_subtype or 'unknown'}",
        f"- count_eligible: {package.count_eligible}",
        f"- preferred_text_source: {package.preferred_text_source}",
        f"- preferred_text_json_path: {package.preferred_text_json_path}",
        "",
        "## Metadata",
        f"- title: {package.title or '[missing title]'}",
        f"- authors: {package.authors or '[missing authors]'}",
        "",
        "## Deterministic anchors",
        *[f"- {line}" for line in _preferred_candidate_summary_lines(package)],
        "",
        "## Evidence pack",
        *[f"- {line}" for line in _key_evidence_lines(package)],
        "",
        "## Explicit subgroup signals",
        *[f"- {line}" for line in subgroup_lines],
        "",
        "## SPS-status uncertainty signals",
        *[f"- {line}" for line in uncertainty_lines],
        "",
        "## Original-cohort provenance signals",
        f"- original_cohort_provenance_uncertain: {package.original_cohort_provenance_uncertain}",
        *[f"- {line}" for line in provenance_lines],
        "",
        "## Confirmed-only guardrail signals",
        *[f"- {line}" for line in guardrail_lines],
        "",
        "## Direct named SPS-spectrum subgroup cues",
        *[f"- {line}" for line in direct_named_counts],
        "",
        "## Treatment-state subset cues",
        *[f"- {line}" for line in treatment_subset_lines],
        "",
        "## Deterministic candidate hints",
        f"- preferred_candidate_id: {package.preferred_candidate_id}",
        f"- fallback_candidate_id: {package.fallback_candidate_id}",
        f"- deterministic_candidate_counts: {candidate_counts}",
        f"- candidate_generation_notes: {json.dumps(notes, ensure_ascii=False)}",
        "",
        "## Local safety hints",
        *[f"- {line}" for line in _local_safety_hint_lines(package)],
        "",
        "## Required JSON output",
        "{",
        '  "n_spsd_patients": 0,',
        '  "evidence_span": "short direct quote",',
        '  "data_granularity": "individual-level|group-level|both|unclear",',
        '  "confidence": "high|medium|low",',
        '  "needs_review": true,',
        '  "reasoning_short": "one short sentence",',
        '  "possibilities": [',
        "    {",
        '      "n_spsd_patients": 0,',
        '      "evidence_span": "short direct quote",',
        '      "data_granularity": "individual-level|group-level|both|unclear",',
        '      "confidence": "high|medium|low",',
        '      "rationale_short": "why this alternative is plausible"',
        "    }",
        "  ]",
        "}",
        "",
        "## Candidate summary",
        *[f"- {line}" for line in _candidate_summary_lines(package)],
    ]
    return "\n".join(parts)
