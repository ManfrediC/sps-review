from __future__ import annotations

import json

from src.pipelines.stage06_counting.models import CountCandidatePackage


def _candidate_lines(package: CountCandidatePackage) -> list[str]:
    lines: list[str] = []
    for candidate in package.candidates[:6]:
        blockers = ", ".join(candidate.blockers) if candidate.blockers else "none"
        lines.extend(
            [
                f"- candidate_id: {candidate.candidate_id}",
                f"  proposed_count: {candidate.proposed_count}",
                f"  candidate_kind: {candidate.candidate_kind}",
                f"  count_basis: {candidate.count_basis}",
                f"  count_confidence: {candidate.count_confidence}",
                f"  manual_review_required: {candidate.manual_review_required}",
                f"  rationale: {candidate.rationale}",
                f"  blockers: {blockers}",
                "  evidence_quote:",
                f"  {candidate.evidence_text[:700].strip() or '[no evidence excerpt available]'}",
            ]
        )
    return lines


def format_candidate_package_for_local_llm(package: CountCandidatePackage) -> str:
    subgroup_lines = ["none"]
    if package.explicit_sps_subgroup_count is not None:
        subgroup_lines = [
            f"explicit_sps_subgroup_count: {package.explicit_sps_subgroup_count}",
            f"explicit_sps_subgroup_basis: {package.explicit_sps_subgroup_basis or 'unknown'}",
            *[
                f"evidence: {snippet}"
                for snippet in (package.explicit_sps_subgroup_evidence or ["[no subgroup evidence excerpt available]"])
            ],
        ]
    uncertainty_lines = package.sps_status_uncertainty_signals or ["none"]
    notes = package.candidate_generation_notes or ["none"]
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
        "## Evidence pack",
        package.llm_evidence_text or "[no evidence pack available]",
        "",
        "## Metadata abstract",
        package.abstract_text or "[no metadata abstract available]",
        "",
        "## Preferred text excerpt",
        package.early_body_text[:3600] or "[no preferred text excerpt available]",
        "",
        "## Explicit subgroup signals",
        *[f"- {line}" for line in subgroup_lines],
        "",
        "## SPS-status uncertainty signals",
        *[f"- {line}" for line in uncertainty_lines],
        "",
        "## Deterministic candidate hints",
        f"- preferred_candidate_id: {package.preferred_candidate_id}",
        f"- fallback_candidate_id: {package.fallback_candidate_id}",
        f"- candidate_generation_notes: {json.dumps(notes, ensure_ascii=False)}",
        "",
        "## Candidate list",
        *_candidate_lines(package),
    ]
    return "\n".join(parts)
