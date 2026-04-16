from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.pipelines._sps_case_count_registry import count_row_from_resolution
from src.pipelines.stage06_counting.classify import DEFAULT_MODEL, adjudicate_count_package
from src.pipelines.stage06_counting.local_ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    run_local_count_package,
)
from src.pipelines.stage06_counting.local_validate import validate_local_count_decision
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


def _decision_json_path_to_repo(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _local_status(call_status: str, flags: list[str]) -> str:
    if call_status != "parsed_ok":
        return call_status
    if flags:
        return "parsed_with_flags"
    return "parsed_ok"


def _build_local_adviser_notes(
    *,
    local_model_name: str,
    local_model_status: str,
    local_model_error: str,
    local_flags: list[str],
    parsed_output: object | None,
) -> str:
    lines = [
        f"- local_model_name: {local_model_name}",
        f"- local_model_status: {local_model_status}",
    ]
    if local_model_error:
        lines.append(f"- local_model_error: {local_model_error}")
    if local_flags:
        lines.append(f"- local_validation_flags: {'; '.join(local_flags)}")
    if parsed_output is None:
        lines.append("- local_model_summary: unavailable")
        return "\n".join(lines)

    lines.extend(
        [
            f"- local_n_spsd_patients: {parsed_output.n_spsd_patients}",
            f"- local_confidence: {parsed_output.confidence}",
            f"- local_needs_review: {parsed_output.needs_review}",
            f"- local_data_granularity: {parsed_output.data_granularity}",
            f"- local_evidence_span: {parsed_output.evidence_span}",
            f"- local_reasoning_short: {parsed_output.reasoning_short}",
            f"- local_possibility_count: {len(parsed_output.possibilities)}",
        ]
    )
    for index, possibility in enumerate(parsed_output.possibilities, start=1):
        lines.append(
            "- local_possibility_"
            f"{index}: count={possibility.n_spsd_patients}; confidence={possibility.confidence}; "
            f"granularity={possibility.data_granularity}; evidence={possibility.evidence_span}"
        )
    return "\n".join(lines)


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


def _decision_payload(
    package: CountCandidatePackage,
    decision: LLMCountDecisionOutput,
    *,
    model_id: str,
    validator_flags: list[str],
    verification_status: str,
    decision_stage: str,
    challenge_reasons: list[str],
) -> dict[str, Any]:
    return {
        "paper_id": package.paper_id,
        "model_id": model_id,
        "verification_status": verification_status,
        "validator_flags": validator_flags,
        "decision_stage": decision_stage,
        "challenge_reasons": challenge_reasons,
        "decision": decision.model_dump(),
    }


def _challenge_reasons(
    package: CountCandidatePackage,
    *,
    local_parsed: object | None,
    local_flags: list[str],
    primary_decision: LLMCountDecisionOutput,
    primary_validator_flags: list[str],
    primary_validator_results: list[object],
) -> list[str]:
    reasons: list[str] = []
    primary_count = resolved_count_from_decision(package, primary_decision)
    _, semantic_reject_flags = split_reject_flags(primary_validator_results)

    if semantic_reject_flags:
        reasons.append(f"semantic_validator_reject={'; '.join(semantic_reject_flags)}")
    if (
        package.explicit_sps_subgroup_count is not None
        and primary_count is not None
        and primary_count != package.explicit_sps_subgroup_count
    ):
        reasons.append(
            "explicit_sps_subgroup_conflict="
            f"{primary_count} vs {package.explicit_sps_subgroup_count}"
        )
    if local_parsed is not None and primary_count is not None:
        if (
            local_parsed.needs_review
            and not primary_decision.count_manual_review_required
            and local_parsed.n_spsd_patients != primary_count
        ):
            reasons.append(
                "local_safer_abstention_conflict="
                f"{local_parsed.n_spsd_patients} vs {primary_count}"
            )
        if local_flags and local_parsed.n_spsd_patients != primary_count:
            reasons.append(
                "local_validation_conflict="
                f"{local_parsed.n_spsd_patients} vs {primary_count}"
            )
    if (
        "COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP" in primary_validator_flags
        and package.explicit_sps_subgroup_count is not None
    ):
        reasons.append(
            "broad_total_exceeds_explicit_subgroup="
            f"{primary_count} > {package.explicit_sps_subgroup_count}"
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return deduped


def _challenge_adviser_notes(
    *,
    base_adviser_notes: str,
    package: CountCandidatePackage,
    primary_decision: LLMCountDecisionOutput,
    primary_validator_flags: list[str],
    primary_count: int | None,
    challenge_reasons: list[str],
) -> str:
    explicit_subgroup = (
        "none"
        if package.explicit_sps_subgroup_count is None
        else str(package.explicit_sps_subgroup_count)
    )
    parts = [base_adviser_notes.strip()]
    parts.extend(
        [
            "",
            "## Challenge adjudication",
            "Re-evaluate the count because the primary GPT answer conflicts with deterministic or conservative evidence.",
            f"- primary_decision_type: {primary_decision.decision_type}",
            f"- primary_resolved_count: {'' if primary_count is None else primary_count}",
            f"- primary_count_confidence: {primary_decision.count_confidence}",
            f"- primary_manual_review_required: {primary_decision.count_manual_review_required}",
            f"- primary_selected_candidate_id: {primary_decision.selected_candidate_id or ''}",
            f"- primary_validator_flags: {'; '.join(primary_validator_flags) if primary_validator_flags else 'none'}",
            f"- explicit_sps_subgroup_count: {explicit_subgroup}",
            f"- challenge_reasons: {'; '.join(challenge_reasons)}",
            "- If the conflict is not fully resolved by explicit paper evidence, return `manual_review_required`.",
            "- Prefer the explicit SPS-spectrum subgroup over a broader mixed cohort unless the paper clearly states the broader cohort is entirely SPS-spectrum.",
        ]
    )
    return "\n".join(part for part in parts if part is not None)


def _verification_status_from_decision(decision: LLMCountDecisionOutput) -> tuple[str, bool]:
    verification_status = "llm_candidate_exact"
    manual_review_required = decision.count_manual_review_required
    if decision.decision_type == "bounded_alternative":
        verification_status = "llm_bounded_alternative"
    elif decision.decision_type == "manual_review_required":
        verification_status = "llm_manual_review_required"
        manual_review_required = True
    elif decision.decision_type == "unable_to_determine":
        verification_status = "llm_unable_to_determine"
        manual_review_required = True
    return verification_status, manual_review_required


def _fallback_row(
    package: CountCandidatePackage,
    *,
    fallback_reason_bits: list[str],
    count_version: str,
    candidate_json_path: str,
    count_evidence_json_path: str = "",
    llm_likely_sps_case_count: str = "",
    llm_count_confidence: str = "",
    llm_selected_candidate_id: str = "",
    count_validator_flags: list[str] | None = None,
) -> dict[str, str]:
    fallback_candidate = package.fallback_candidate()
    return count_row_from_resolution(
        package=package,
        final_count=fallback_candidate.proposed_count,
        final_confidence=fallback_candidate.count_confidence,
        final_basis=fallback_candidate.count_basis,
        final_manual_review_required=True,
        final_reason=" | ".join(fallback_reason_bits),
        count_version=count_version,
        count_verification_status="llm_invalid_manual_review_required",
        count_candidate_json_path=candidate_json_path,
        count_evidence_json_path=count_evidence_json_path,
        heuristic_fallback_used=True,
        llm_likely_sps_case_count=llm_likely_sps_case_count,
        llm_count_confidence=llm_count_confidence,
        llm_selected_candidate_id=llm_selected_candidate_id,
        count_validator_flags=count_validator_flags,
        count_audit_status="hybrid_local_gpt",
    )


def hybrid_count_row(
    package: CountCandidatePackage,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    run_dir: Path | None = None,
    count_version: str = "hybrid_v2_gpt-5.4",
    candidate_json_path: str = "",
    local_model: str = DEFAULT_OLLAMA_MODEL,
    local_base_url: str = DEFAULT_OLLAMA_BASE_URL,
    local_timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
) -> dict[str, str]:
    preferred_candidate = package.preferred_candidate()
    fallback_candidate = package.fallback_candidate()

    local_call = run_local_count_package(
        package,
        model=local_model,
        base_url=local_base_url,
        timeout_seconds=local_timeout_seconds,
    )
    local_flags = [] if local_call.parsed is None else validate_local_count_decision(package, local_call.parsed)
    local_model_status = _local_status(local_call.status, local_flags)

    local_result_json_path = ""
    if run_dir is not None:
        local_result_json_path = _write_json(
            run_dir / "local_model_results" / f"{package.paper_id}.json",
            {
                "paper_id": package.paper_id,
                "model_id": local_call.model_id,
                "status": local_model_status,
                "duration_seconds": round(local_call.duration_seconds, 3),
                "error": local_call.error,
                "validation_flags": local_flags,
                "parsed_output": None if local_call.parsed is None else local_call.parsed.model_dump(),
                "raw_output": local_call.raw_output,
                "response_payload": local_call.response_payload,
            },
        )

    adviser_notes = _build_local_adviser_notes(
        local_model_name=local_call.model_id,
        local_model_status=local_model_status,
        local_model_error=local_call.error,
        local_flags=local_flags,
        parsed_output=local_call.parsed,
    )

    primary_decision_json_path = ""
    evidence_json_path = ""
    challenge_json_path = ""
    try:
        primary_decision, primary_model_id = adjudicate_count_package(
            package,
            model=model,
            api_key=api_key,
            adviser_notes=adviser_notes,
        )
        primary_validator_results = collect_validator_results(package, primary_decision)
        primary_validator_flags, primary_worst = summarise_validator_results(primary_validator_results)
        primary_count = resolved_count_from_decision(package, primary_decision)
        challenge_reasons = _challenge_reasons(
            package,
            local_parsed=local_call.parsed,
            local_flags=local_flags,
            primary_decision=primary_decision,
            primary_validator_flags=primary_validator_flags,
            primary_validator_results=primary_validator_results,
        )

        final_decision = primary_decision
        final_model_id = primary_model_id
        final_validator_results = primary_validator_results
        final_validator_flags = primary_validator_flags
        final_worst = primary_worst
        decision_stage = "primary"

        if challenge_reasons:
            if run_dir is not None:
                primary_decision_json_path = _write_json(
                    run_dir / "count_decisions_primary" / f"{package.paper_id}.json",
                    _decision_payload(
                        package,
                        primary_decision,
                        model_id=primary_model_id,
                        validator_flags=primary_validator_flags,
                        verification_status="challenge_pending",
                        decision_stage="primary",
                        challenge_reasons=challenge_reasons,
                    ),
                )
            challenge_decision, challenge_model_id = adjudicate_count_package(
                package,
                model=model,
                api_key=api_key,
                adviser_notes=_challenge_adviser_notes(
                    base_adviser_notes=adviser_notes,
                    package=package,
                    primary_decision=primary_decision,
                    primary_validator_flags=primary_validator_flags,
                    primary_count=primary_count,
                    challenge_reasons=challenge_reasons,
                ),
            )
            final_decision = challenge_decision
            final_model_id = challenge_model_id
            final_validator_results = collect_validator_results(package, challenge_decision)
            final_validator_flags, final_worst = summarise_validator_results(final_validator_results)
            decision_stage = "challenge"
            if run_dir is not None:
                challenge_json_path = _write_json(
                    run_dir / "count_challenges" / f"{package.paper_id}.json",
                    {
                        "paper_id": package.paper_id,
                        "challenge_reasons": challenge_reasons,
                        "local_model_status": local_model_status,
                        "local_validation_flags": local_flags,
                        "primary_decision": primary_decision.model_dump(),
                        "primary_validator_flags": primary_validator_flags,
                        "primary_decision_json_path": _decision_json_path_to_repo(primary_decision_json_path),
                    },
                )

        final_count = resolved_count_from_decision(package, final_decision)
        final_basis = _resolved_basis_from_decision(package, final_decision)
        verification_status, final_manual_review_required = _verification_status_from_decision(final_decision)

        if run_dir is not None:
            _write_json(
                run_dir / "count_decisions" / f"{package.paper_id}.json",
                _decision_payload(
                    package,
                    final_decision,
                    model_id=final_model_id,
                    validator_flags=final_validator_flags,
                    verification_status=verification_status,
                    decision_stage=decision_stage,
                    challenge_reasons=challenge_reasons,
                ),
            )
            evidence_json_path = _write_json(
                run_dir / "count_evidence" / f"{package.paper_id}.json",
                {
                    "paper_id": package.paper_id,
                    "decision_stage": decision_stage,
                    "challenge_reasons": challenge_reasons,
                    "evidence": [item.model_dump() for item in final_decision.evidence],
                    "local_result_json_path": _decision_json_path_to_repo(local_result_json_path),
                    "challenge_json_path": _decision_json_path_to_repo(challenge_json_path),
                },
            )

        _, semantic_reject_flags = split_reject_flags(final_validator_results)
        if semantic_reject_flags and final_count is not None:
            use_conservative_fallback = requires_conservative_fallback_for_semantic_conflict(
                semantic_reject_flags
            )
            reasons = [
                "challenge_stage=" + decision_stage,
                f"llm_semantic_conflict={'; '.join(semantic_reject_flags)}",
                "manual_review_gate=true",
                f"llm_count_confidence={final_decision.count_confidence}",
            ]
            if use_conservative_fallback:
                reasons.extend(
                    [
                        f"conservative_fallback_candidate_id={fallback_candidate.candidate_id}",
                        f"conservative_fallback_basis={fallback_candidate.count_basis}",
                    ]
                )
            if challenge_reasons:
                reasons.append(f"challenge_reasons={'; '.join(challenge_reasons)}")
            if final_decision.selected_candidate_id:
                reasons.append(f"llm_selected_candidate_id={final_decision.selected_candidate_id}")
            if final_validator_flags:
                reasons.append(f"validator_flags={'; '.join(final_validator_flags)}")
            if final_decision.count_reasoning_summary:
                reasons.append(final_decision.count_reasoning_summary)
            resolved_final_count = final_count
            resolved_final_confidence = final_decision.count_confidence
            resolved_final_basis = final_basis
            if use_conservative_fallback:
                resolved_final_count = fallback_candidate.proposed_count
                resolved_final_confidence = fallback_candidate.count_confidence
                resolved_final_basis = fallback_candidate.count_basis
            return count_row_from_resolution(
                package=package,
                final_count=resolved_final_count,
                final_confidence=resolved_final_confidence,
                final_basis=resolved_final_basis,
                final_manual_review_required=True,
                final_reason=" | ".join(reasons),
                count_version=count_version,
                count_verification_status="llm_semantic_conflict_manual_review_required",
                count_candidate_json_path=candidate_json_path,
                count_evidence_json_path=_decision_json_path_to_repo(evidence_json_path),
                llm_likely_sps_case_count=str(final_count),
                llm_count_confidence=final_decision.count_confidence,
                llm_selected_candidate_id=final_decision.selected_candidate_id or "",
                count_validator_flags=final_validator_flags,
                count_audit_status="hybrid_local_gpt",
                heuristic_fallback_used=use_conservative_fallback,
            )

        if final_worst >= Severity.REJECT or final_count is None:
            reasons = [
                "challenge_stage=" + decision_stage,
                "manual_review_gate=true",
                f"provisional_fallback_candidate_id={fallback_candidate.candidate_id}",
                f"provisional_fallback_basis={fallback_candidate.count_basis}",
            ]
            if challenge_reasons:
                reasons.append(f"challenge_reasons={'; '.join(challenge_reasons)}")
            if final_validator_flags:
                reasons.append(f"validator_flags={'; '.join(final_validator_flags)}")
            if final_decision.count_reasoning_summary:
                reasons.append(final_decision.count_reasoning_summary)
            return _fallback_row(
                package,
                fallback_reason_bits=reasons,
                count_version=count_version,
                candidate_json_path=candidate_json_path,
                count_evidence_json_path=_decision_json_path_to_repo(evidence_json_path),
                llm_likely_sps_case_count="" if final_count is None else str(final_count),
                llm_count_confidence=final_decision.count_confidence,
                llm_selected_candidate_id=final_decision.selected_candidate_id or "",
                count_validator_flags=final_validator_flags,
            )

        reasons = [
            "challenge_stage=" + decision_stage,
            f"verification_status={verification_status}",
            f"llm_count_confidence={final_decision.count_confidence}",
        ]
        if challenge_reasons:
            reasons.append(f"challenge_reasons={'; '.join(challenge_reasons)}")
        if final_decision.selected_candidate_id:
            reasons.append(f"llm_selected_candidate_id={final_decision.selected_candidate_id}")
        if final_validator_flags:
            reasons.append(f"validator_flags={'; '.join(final_validator_flags)}")
        if final_decision.count_reasoning_summary:
            reasons.append(final_decision.count_reasoning_summary)

        preserve_heuristic_review_flag = bool(final_validator_flags) or verification_status in {
            "llm_manual_review_required",
            "llm_unable_to_determine",
        }
        return count_row_from_resolution(
            package=package,
            final_count=final_count,
            final_confidence=final_decision.count_confidence,
            final_basis=final_basis,
            final_manual_review_required=final_manual_review_required
            or (preferred_candidate.manual_review_required and preserve_heuristic_review_flag),
            final_reason=" | ".join(reasons),
            count_version=count_version,
            count_verification_status=verification_status,
            count_candidate_json_path=candidate_json_path,
            count_evidence_json_path=_decision_json_path_to_repo(evidence_json_path),
            llm_likely_sps_case_count=str(final_count),
            llm_count_confidence=final_decision.count_confidence,
            llm_selected_candidate_id=final_decision.selected_candidate_id or "",
            count_validator_flags=final_validator_flags,
            count_audit_status="hybrid_local_gpt",
        )
    except Exception as exc:
        reasons = [
            f"llm_request_failed={exc.__class__.__name__}",
            "manual_review_gate=true",
            f"provisional_fallback_candidate_id={fallback_candidate.candidate_id}",
            f"provisional_fallback_basis={fallback_candidate.count_basis}",
        ]
        if local_model_status:
            reasons.append(f"local_model_status={local_model_status}")
        if local_flags:
            reasons.append(f"local_validation_flags={'; '.join(local_flags)}")
        return _fallback_row(
            package,
            fallback_reason_bits=reasons,
            count_version=count_version,
            candidate_json_path=candidate_json_path,
        )


def gpt_adjudication_needed(package: CountCandidatePackage) -> bool:
    if (
        not package.count_eligible
        and package.preferred_candidate().proposed_count == 0
        and package.explicit_sps_subgroup_count is None
    ):
        return False
    return bool(
        package.count_eligible
        or package.llm_routing_recommended
        or package.preferred_candidate().proposed_count > 0
        or package.explicit_sps_subgroup_count is not None
    )
