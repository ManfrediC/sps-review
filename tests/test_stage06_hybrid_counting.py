from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.hybrid import gpt_adjudication_needed, hybrid_count_row
from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput, LocalModelCallResult
from src.pipelines.stage06_counting.models import CountEvidenceItem, LLMCountDecisionOutput


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_enumerated_subgroup_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "1937",
            "Title": "Prevalence of neurological anti-GAD autoimmunity in Martinique",
            "Authors": "Duclos, S",
            "Abstract": (
                "Results: On January 1 2016, 21 patients had neurological syndromes associated with anti-GAD autoimmunity. "
                "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM."
            ),
        },
        text_record={"paper_id": "1937", "_path": "data/extraction_json/text/1937.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Results: On January 1 2016, 21 patients had neurological syndromes associated with anti-GAD autoimmunity. "
                        "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready" / "1937.json",
        source_row={
            "source_category": "conference_abstract",
            "source_subtype": "group_conference_abstract",
        },
    )


def make_zero_review_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "12720",
            "Title": "STIFF-MAN SYNDROME",
            "Authors": "TORO, C; JACOBWITZ, DM; HALLETT, M",
            "Abstract": "",
        },
        text_record={"paper_id": "12720", "_path": "data/extraction_json/text/12720.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Stiff-man syndrome is the term coined by Moersch and Woltmann. "
                        "A survey of the medical literature in 1967 identified 44 cases."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "12720.json",
        source_row={
            "source_category": "review_article",
            "source_subtype": "review",
        },
    )


def make_donor_material_package():
    donor_text = (
        "Methods: Purified GAD65-Ab from neurological patients and monoclonal GAD65-Ab with distinct epitope "
        "specificities were administered in vivo to rat cerebellum. Results: Intra-cerebellar administration of "
        "GAD65-Ab from a SPS patient (Ab SPS) impaired the NMDA-mediated turnover of glutamate, while Ab CA was "
        "derived from a patient with cerebellar ataxia."
    )
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "560",
            "Title": "Respective implications of glutamate decarboxylase antibodies in stiff person syndrome and cerebellar ataxia",
            "Authors": "Manto, M U; Hampe, C S; Rogemond, V; Honnorat, J",
            "Abstract": donor_text,
        },
        text_record={"paper_id": "560", "_path": "data/extraction_json/text/560.json"},
        preferred_record={"pages": [{"text": donor_text}]},
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text_trimmed" / "560.json",
        source_row={
            "source_category": "lab_heavy_clinical_or_translational",
            "source_subtype": "group_or_frequency_focused_lab_clinical_study",
        },
    )


class TestStage06HybridCounting(unittest.TestCase):
    def test_gpt_adjudication_needed_skips_clear_zero_review_rows(self) -> None:
        self.assertFalse(gpt_adjudication_needed(make_zero_review_package()))

    def test_hybrid_count_row_preserves_manual_review_for_non_count_eligible_rows(self) -> None:
        package = make_zero_review_package()
        local_call = LocalModelCallResult(
            model_id="gemma4:e4b",
            status="parsed_ok",
            raw_output="{}",
            response_payload={},
            parsed=LocalCountDecisionOutput.model_validate(
                {
                    "n_spsd_patients": 0,
                    "evidence_span": "A survey of the medical literature in 1967 identified 44 cases.",
                    "data_granularity": "unclear",
                    "confidence": "low",
                    "needs_review": True,
                    "reasoning_short": "This looks like a review article rather than an extractable cohort.",
                    "possibilities": [],
                }
            ),
            duration_seconds=0.5,
        )
        decision = LLMCountDecisionOutput(
            decision_type="manual_review_required",
            selected_candidate_id=None,
            alternative_count=None,
            count_confidence="low",
            count_manual_review_required=True,
            count_reasoning_summary="The paper discusses prior literature rather than a clean original cohort.",
            evidence=[
                CountEvidenceItem(
                    quote="A survey of the medical literature in 1967 identified 44 cases.",
                    page=1,
                    section="review context",
                    supports="This is literature background, not an extractable original cohort count.",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_dir = Path(tmp_dir_text)
            with (
                mock.patch("src.pipelines.stage06_counting.hybrid.run_local_count_package", return_value=local_call),
                mock.patch(
                    "src.pipelines.stage06_counting.hybrid.adjudicate_count_package",
                    return_value=(decision, "gpt-5.4-primary"),
                ),
            ):
                row = hybrid_count_row(
                    package,
                    run_dir=run_dir,
                    candidate_json_path="results/stage06_count_runs/test/candidate_packages/12720.json",
                )

        self.assertEqual(row["count_verification_status"], "llm_manual_review_required")
        self.assertEqual(row["count_manual_review_required"], "true")

    def test_hybrid_count_row_runs_challenge_on_subgroup_conflict(self) -> None:
        package = make_enumerated_subgroup_package()
        local_parsed = LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 14,
                "evidence_span": "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                "data_granularity": "group-level",
                "confidence": "high",
                "needs_review": True,
                "reasoning_short": "The explicit SPS-spectrum subtotal is 14.",
                "possibilities": [],
            }
        )
        local_call = LocalModelCallResult(
            model_id="gemma4:e4b",
            status="parsed_ok",
            raw_output="{}",
            response_payload={},
            parsed=local_parsed,
            duration_seconds=0.5,
        )
        primary_decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=package.preferred_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The broader anti-GAD cohort seems to be the count.",
            evidence=[
                CountEvidenceItem(
                    quote="21 patients had neurological syndromes associated with anti-GAD autoimmunity.",
                    page=1,
                    section="abstract",
                    supports="broader cohort size",
                ),
                CountEvidenceItem(
                    quote="Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                    page=1,
                    section="abstract",
                    supports="diagnosis breakdown",
                ),
            ],
        )
        challenge_decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=14,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The explicit SPS plus PERM subtotal is the correct SPS-spectrum count.",
            evidence=[
                CountEvidenceItem(
                    quote="Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                    page=1,
                    section="abstract",
                    supports="explicit SPS-spectrum subtotal",
                ),
                CountEvidenceItem(
                    quote="21 patients had neurological syndromes associated with anti-GAD autoimmunity.",
                    page=1,
                    section="abstract",
                    supports="broader cohort that should not be used directly",
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_dir = Path(tmp_dir_text)
            with (
                mock.patch("src.pipelines.stage06_counting.hybrid.run_local_count_package", return_value=local_call),
                mock.patch(
                    "src.pipelines.stage06_counting.hybrid.adjudicate_count_package",
                    side_effect=[(primary_decision, "gpt-5.4-primary"), (challenge_decision, "gpt-5.4-challenge")],
                ),
            ):
                row = hybrid_count_row(
                    package,
                    run_dir=run_dir,
                    candidate_json_path="results/stage06_count_runs/test/candidate_packages/1937.json",
                )

        self.assertEqual(row["likely_sps_case_count"], "14")
        self.assertEqual(row["count_verification_status"], "llm_bounded_alternative")
        self.assertEqual(row["count_manual_review_required"], "false")
        self.assertIn("challenge_stage=challenge", row["count_reason"])
        self.assertIn("challenge_reasons=", row["count_reason"])

    def test_hybrid_count_row_uses_conservative_fallback_for_donor_material_conflict(self) -> None:
        package = make_donor_material_package()
        local_parsed = LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 0,
                "evidence_span": "Purified GAD65-Ab from neurological patients",
                "data_granularity": "unclear",
                "confidence": "low",
                "needs_review": True,
                "reasoning_short": "The paper uses donor material but does not report an extractable clinical cohort.",
                "possibilities": [],
            }
        )
        local_call = LocalModelCallResult(
            model_id="gemma4:e4b",
            status="parsed_ok",
            raw_output="{}",
            response_payload={},
            parsed=local_parsed,
            duration_seconds=0.5,
        )
        selected_candidate_id = next(
            candidate.candidate_id for candidate in package.candidates if candidate.proposed_count == 1
        )
        primary_decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=selected_candidate_id,
            alternative_count=None,
            count_confidence="medium",
            count_manual_review_required=True,
            count_reasoning_summary=(
                "The abstract mentions GAD65-Ab from a SPS patient, so one SPS-spectrum patient contributed material."
            ),
            evidence=[
                CountEvidenceItem(
                    quote="Purified GAD65-Ab from neurological patients were administered in vivo to rat cerebellum.",
                    page=1,
                    section="methods",
                    supports="patient-derived antibody material",
                ),
                CountEvidenceItem(
                    quote="Intra-cerebellar administration of GAD65-Ab from a SPS patient (Ab SPS) impaired glutamate turnover.",
                    page=1,
                    section="results",
                    supports="one SPS-labelled donor source",
                ),
            ],
        )
        challenge_decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=selected_candidate_id,
            alternative_count=None,
            count_confidence="medium",
            count_manual_review_required=True,
            count_reasoning_summary=(
                "The donor source still indicates one SPS-spectrum patient, but manual review is appropriate."
            ),
            evidence=primary_decision.evidence,
        )

        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_dir = Path(tmp_dir_text)
            with (
                mock.patch("src.pipelines.stage06_counting.hybrid.run_local_count_package", return_value=local_call),
                mock.patch(
                    "src.pipelines.stage06_counting.hybrid.adjudicate_count_package",
                    side_effect=[(primary_decision, "gpt-5.4-primary"), (challenge_decision, "gpt-5.4-challenge")],
                ),
            ):
                row = hybrid_count_row(
                    package,
                    run_dir=run_dir,
                    candidate_json_path="results/stage06_count_runs/test/candidate_packages/560.json",
                )

        self.assertEqual(row["likely_sps_case_count"], "0")
        self.assertEqual(row["llm_likely_sps_case_count"], "1")
        self.assertEqual(row["count_verification_status"], "llm_semantic_conflict_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "true")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("COUNT_DONOR_MATERIAL_ONLY", row["count_validator_flags"])


if __name__ == "__main__":
    unittest.main()
