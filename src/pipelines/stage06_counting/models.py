from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class CountCandidate:
    candidate_id: str
    proposed_count: int
    candidate_kind: str
    count_basis: str
    count_confidence: str
    manual_review_required: bool
    score: int
    rationale: str
    evidence_text: str
    evidence_section: str = ""
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CountCandidatePackage:
    paper_id: str
    covidence_id: str
    title: str
    authors: str
    source_category: str
    source_subtype: str
    preferred_text_json_path: str
    preferred_text_source: str
    preferred_text_metadata: dict[str, Any]
    count_eligible: bool
    heuristic_version: str
    abstract_text: str
    early_body_text: str
    llm_evidence_text: str
    candidate_generation_notes: list[str]
    candidates: list[CountCandidate]
    preferred_candidate_id: str
    fallback_candidate_id: str
    llm_routing_recommended: bool
    llm_routing_reason: str
    explicit_sps_subgroup_count: int | None = None
    explicit_sps_subgroup_basis: str = ""
    explicit_sps_subgroup_evidence: list[str] = field(default_factory=list)
    sps_status_uncertainty_signals: list[str] = field(default_factory=list)

    def preferred_candidate(self) -> CountCandidate:
        for candidate in self.candidates:
            if candidate.candidate_id == self.preferred_candidate_id:
                return candidate
        return self.candidates[0]

    def fallback_candidate(self) -> CountCandidate:
        for candidate in self.candidates:
            if candidate.candidate_id == self.fallback_candidate_id:
                return candidate
        return self.preferred_candidate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "covidence_id": self.covidence_id,
            "title": self.title,
            "authors": self.authors,
            "source_category": self.source_category,
            "source_subtype": self.source_subtype,
            "preferred_text_json_path": self.preferred_text_json_path,
            "preferred_text_source": self.preferred_text_source,
            "preferred_text_metadata": dict(self.preferred_text_metadata),
            "count_eligible": self.count_eligible,
            "heuristic_version": self.heuristic_version,
            "abstract_text": self.abstract_text,
            "early_body_text": self.early_body_text,
            "llm_evidence_text": self.llm_evidence_text,
            "candidate_generation_notes": list(self.candidate_generation_notes),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "preferred_candidate_id": self.preferred_candidate_id,
            "fallback_candidate_id": self.fallback_candidate_id,
            "llm_routing_recommended": self.llm_routing_recommended,
            "llm_routing_reason": self.llm_routing_reason,
            "explicit_sps_subgroup_count": self.explicit_sps_subgroup_count,
            "explicit_sps_subgroup_basis": self.explicit_sps_subgroup_basis,
            "explicit_sps_subgroup_evidence": list(self.explicit_sps_subgroup_evidence),
            "sps_status_uncertainty_signals": list(self.sps_status_uncertainty_signals),
        }


class CountEvidenceItem(BaseModel):
    quote: str = Field(..., description="Verbatim or near-verbatim evidence from the paper.")
    page: int | None = Field(None, description="1-indexed page number when identifiable.")
    section: str | None = Field(None, description="Section or local context label when identifiable.")
    supports: str = Field(..., description="What this evidence supports.")


class LLMCountDecisionOutput(BaseModel):
    decision_type: Literal[
        "candidate_exact",
        "bounded_alternative",
        "manual_review_required",
        "unable_to_determine",
    ] = Field(..., description="How the model resolved the candidate package.")
    selected_candidate_id: str | None = Field(
        None,
        description="Selected heuristic candidate ID when decision_type is candidate_exact.",
    )
    alternative_count: int | None = Field(
        None,
        ge=0,
        description="Explicit count proposed by the model when no candidate is exact.",
    )
    count_confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description="Confidence in the final count decision.",
    )
    count_manual_review_required: bool = Field(
        ...,
        description="Whether this count should be checked by a human reviewer.",
    )
    count_reasoning_summary: str = Field(
        ...,
        description="1-3 sentence explanation of the selected count.",
    )
    evidence: list[CountEvidenceItem] = Field(
        ...,
        min_length=1,
        description="Evidence items supporting the decision.",
    )
