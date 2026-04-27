from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_count_registry import count_row_from_resolution
from src.pipelines.stage06_counting.classify import DEFAULT_MODEL, adjudicate_count_package
from src.pipelines.stage06_counting.models import CountCandidatePackage, LLMCountDecisionOutput
from src.pipelines.stage06_counting.validate import (
    Severity,
    collect_validator_results,
    requires_conservative_fallback_for_semantic_conflict,
    resolved_count_from_decision,
    split_reject_flags,
    summarise_validator_results,
)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def heuristic_count_row(
    package: CountCandidatePackage,
    *,
    count_version: str,
    candidate_json_path: str = "",
) -> dict[str, str]:
    preferred_candidate = package.preferred_candidate()
    reasons = [
        f"count_basis={preferred_candidate.count_basis}",
        f"count_confidence={preferred_candidate.count_confidence}",
    ]
    if package.source_category:
        reasons.append(f"source_category={package.source_category}")
    if package.candidate_generation_notes:
        reasons.append(f"candidate_notes={'; '.join(package.candidate_generation_notes)}")
    return count_row_from_resolution(
        package=package,
        final_count=preferred_candidate.proposed_count,
        final_confidence=preferred_candidate.count_confidence,
        final_basis=preferred_candidate.count_basis,
        final_manual_review_required=preferred_candidate.manual_review_required,
        final_reason=" | ".join(reasons),
        count_version=count_version,
        count_verification_status="heuristic_only",
        count_candidate_json_path=candidate_json_path,
    )


def _decision_to_payload(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
    *,
    model_id: str,
    validator_flags: list[str],
    verification_status: str,
) -> dict[str, Any]:
    return {
        "paper_id": package.paper_id,
        "model_id": model_id,
        "verification_status": verification_status,
        "validator_flags": validator_flags,
        "decision": decision.model_dump(),
    }


def _provisional_fallback_reasons(
    *,
    package: CountCandidatePackage,
    fallback_candidate_id: str,
    fallback_basis: str,
) -> list[str]:
    reasons = [
        "manual_review_gate=true",
        f"provisional_fallback_candidate_id={fallback_candidate_id}",
        f"provisional_fallback_basis={fallback_basis}",
    ]
    if package.candidate_generation_notes:
        reasons.append(f"candidate_notes={'; '.join(package.candidate_generation_notes)}")
    return reasons


def _resolved_basis_from_decision(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
) -> str:
    final_basis = package.preferred_candidate().count_basis
    if decision.decision_type == "bounded_alternative":
        return "llm_bounded_alternative"
    if decision.decision_type == "candidate_exact" and decision.selected_candidate_id:
        for candidate in package.candidates:
            if candidate.candidate_id == decision.selected_candidate_id:
                return candidate.count_basis
    return final_basis


def adjudicated_count_row(
    package: CountCandidatePackage,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    run_dir: Path | None = None,
    count_version: str = "hybrid_v1_gpt5.4",
    candidate_json_path: str = "",
    adviser_notes: str = "",
) -> dict[str, str]:
    preferred_candidate = package.preferred_candidate()
    fallback_candidate = package.fallback_candidate()
    evidence_json_path = ""
    try:
        decision, model_id = adjudicate_count_package(
            package,
            model=model,
            api_key=api_key,
            adviser_notes=adviser_notes,
        )
        validator_results = collect_validator_results(package, decision)
        validator_flags, worst = summarise_validator_results(validator_results)
        _, semantic_reject_flags = split_reject_flags(validator_results)
        resolved_count = resolved_count_from_decision(package, decision)
        final_basis = _resolved_basis_from_decision(package, decision)

        if semantic_reject_flags and resolved_count is not None:
            use_conservative_fallback = requires_conservative_fallback_for_semantic_conflict(
                semantic_reject_flags
            )
            reasons = [
                f"llm_semantic_conflict={'; '.join(semantic_reject_flags)}",
                "manual_review_gate=true",
                f"llm_count_confidence={decision.count_confidence}",
            ]
            if use_conservative_fallback:
                reasons.extend(
                    [
                        f"conservative_fallback_candidate_id={fallback_candidate.candidate_id}",
                        f"conservative_fallback_basis={fallback_candidate.count_basis}",
                    ]
                )
            if decision.selected_candidate_id:
                reasons.append(f"llm_selected_candidate_id={decision.selected_candidate_id}")
            if validator_flags:
                reasons.append(f"validator_flags={'; '.join(validator_flags)}")
            if decision.count_reasoning_summary:
                reasons.append(decision.count_reasoning_summary)
            if run_dir is not None:
                _write_json(
                    run_dir / "count_decisions" / f"{package.paper_id}.json",
                    _decision_to_payload(
                        package,
                        decision,
                        model_id=model_id,
                        validator_flags=validator_flags,
                        verification_status="llm_semantic_conflict_manual_review_required",
                    ),
                )
                evidence_json_path = _write_json(
                    run_dir / "count_evidence" / f"{package.paper_id}.json",
                    {"paper_id": package.paper_id, "evidence": [item.model_dump() for item in decision.evidence]},
                )
            final_count = resolved_count
            final_confidence = decision.count_confidence
            if use_conservative_fallback:
                final_count = fallback_candidate.proposed_count
                final_confidence = fallback_candidate.count_confidence
                final_basis = fallback_candidate.count_basis
            return count_row_from_resolution(
                package=package,
                final_count=final_count,
                final_confidence=final_confidence,
                final_basis=final_basis,
                final_manual_review_required=True,
                final_reason=" | ".join(reasons),
                count_version=count_version,
                count_verification_status="llm_semantic_conflict_manual_review_required",
                count_candidate_json_path=candidate_json_path,
                count_evidence_json_path=decision_json_path_to_repo(evidence_json_path),
                llm_likely_sps_case_count=str(resolved_count),
                llm_count_confidence=decision.count_confidence,
                llm_selected_candidate_id=decision.selected_candidate_id or "",
                count_validator_flags=validator_flags,
                heuristic_fallback_used=use_conservative_fallback,
            )

        if worst >= Severity.REJECT:
            reasons = [
                f"llm_validation_failed={'; '.join(validator_flags)}",
                *_provisional_fallback_reasons(
                    package=package,
                    fallback_candidate_id=fallback_candidate.candidate_id,
                    fallback_basis=fallback_candidate.count_basis,
                ),
            ]
            if decision.count_reasoning_summary:
                reasons.append(decision.count_reasoning_summary)
            if run_dir is not None:
                _write_json(
                    run_dir / "count_decisions" / f"{package.paper_id}.json",
                    _decision_to_payload(
                        package,
                        decision,
                        model_id=model_id,
                        validator_flags=validator_flags,
                        verification_status="llm_invalid_manual_review_required",
                    ),
                )
                evidence_json_path = _write_json(
                    run_dir / "count_evidence" / f"{package.paper_id}.json",
                    {"paper_id": package.paper_id, "evidence": [item.model_dump() for item in decision.evidence]},
                )
            return count_row_from_resolution(
                package=package,
                final_count=fallback_candidate.proposed_count,
                final_confidence=fallback_candidate.count_confidence,
                final_basis=fallback_candidate.count_basis,
                final_manual_review_required=True,
                final_reason=" | ".join(reasons),
                count_version=count_version,
                count_verification_status="llm_invalid_manual_review_required",
                count_candidate_json_path=candidate_json_path,
                count_evidence_json_path=decision_json_path_to_repo(evidence_json_path),
                heuristic_fallback_used=True,
                llm_likely_sps_case_count="" if resolved_count_from_decision(package, decision) is None else str(resolved_count_from_decision(package, decision)),
                llm_count_confidence=decision.count_confidence,
                llm_selected_candidate_id=decision.selected_candidate_id or "",
                count_validator_flags=validator_flags,
            )

        if resolved_count is None:
            raise ValueError("LLM decision did not resolve to a count.")
        verification_status = "llm_candidate_exact"
        final_manual_review_required = decision.count_manual_review_required
        if decision.decision_type == "bounded_alternative":
            verification_status = "llm_bounded_alternative"
        elif decision.decision_type == "manual_review_required":
            verification_status = "llm_manual_review_required"
            final_manual_review_required = True
        elif decision.decision_type == "unable_to_determine":
            verification_status = "llm_unable_to_determine"
            final_manual_review_required = True

        reasons = [
            f"verification_status={verification_status}",
            f"llm_count_confidence={decision.count_confidence}",
        ]
        if decision.selected_candidate_id:
            reasons.append(f"llm_selected_candidate_id={decision.selected_candidate_id}")
        if validator_flags:
            reasons.append(f"validator_flags={'; '.join(validator_flags)}")
        if decision.count_reasoning_summary:
            reasons.append(decision.count_reasoning_summary)

        if run_dir is not None:
            _write_json(
                run_dir / "count_decisions" / f"{package.paper_id}.json",
                _decision_to_payload(
                    package,
                    decision,
                    model_id=model_id,
                    validator_flags=validator_flags,
                    verification_status=verification_status,
                ),
            )
            evidence_json_path = _write_json(
                run_dir / "count_evidence" / f"{package.paper_id}.json",
                {"paper_id": package.paper_id, "evidence": [item.model_dump() for item in decision.evidence]},
            )

        preserve_heuristic_review_flag = bool(validator_flags) or verification_status in {
            "llm_manual_review_required",
            "llm_unable_to_determine",
        }

        return count_row_from_resolution(
            package=package,
            final_count=resolved_count,
            final_confidence=decision.count_confidence,
            final_basis=final_basis,
            final_manual_review_required=final_manual_review_required
            or (preferred_candidate.manual_review_required and preserve_heuristic_review_flag),
            final_reason=" | ".join(reasons),
            count_version=count_version,
            count_verification_status=verification_status,
            count_candidate_json_path=candidate_json_path,
            count_evidence_json_path=decision_json_path_to_repo(evidence_json_path),
            llm_likely_sps_case_count=str(resolved_count),
            llm_count_confidence=decision.count_confidence,
            llm_selected_candidate_id=decision.selected_candidate_id or "",
            count_validator_flags=validator_flags,
        )
    except Exception as exc:
        reasons = [
            f"llm_request_failed={exc.__class__.__name__}",
            *_provisional_fallback_reasons(
                package=package,
                fallback_candidate_id=fallback_candidate.candidate_id,
                fallback_basis=fallback_candidate.count_basis,
            ),
        ]
        return count_row_from_resolution(
            package=package,
            final_count=fallback_candidate.proposed_count,
            final_confidence=fallback_candidate.count_confidence,
            final_basis=fallback_candidate.count_basis,
            final_manual_review_required=True,
            final_reason=" | ".join(reasons),
            count_version=count_version,
            count_verification_status="llm_request_failed_manual_review_required",
            count_candidate_json_path=candidate_json_path,
            heuristic_fallback_used=True,
        )


def decision_json_path_to_repo(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)
