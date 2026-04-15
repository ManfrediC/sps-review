from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.controller import adjudicated_count_row
from src.pipelines.stage06_counting.models import CountEvidenceItem, LLMCountDecisionOutput
from src.pipelines.stage06_counting.prepare import format_candidate_package_for_llm
from src.pipelines.stage06_counting.validate import Severity, run_validators


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "214",
            "Title": "Plasma exchange in stiff-man syndrome.",
            "Authors": "Example, C",
            "Abstract": (
                "We report on the use of plasma exchange in 2 patients with stiff-man syndrome. "
                "One patient showed minimal clinical improvement while the second reported subjective improvement."
            ),
        },
        text_record={"paper_id": "214", "_path": "data/extraction_json/text/214.json"},
        preferred_record={"pages": [{"text": "Case 1 ... Case 2 ..."}]},
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "214.json",
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_724_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "724",
            "Title": "Glycine receptor antibodies in PERM and related syndromes: characteristics, clinical features and outcomes.",
            "Authors": "Carvajal-Gonzalez, Alexander",
            "Abstract": (
                "We identified prospectively 52 antibody-positive patients and collated their clinical features. "
                "Thirty-three patients were classified as progressive encephalomyelitis with rigidity and myoclonus, "
                "and two as stiff person syndrome; five had a limbic encephalitis or epileptic encephalopathy, "
                "two had brainstem features mainly, two had demyelinating optic neuropathies and one had an unclear diagnosis."
            ),
        },
        text_record={"paper_id": "724", "_path": "data/extraction_json/text/724.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "We identified prospectively 52 antibody-positive patients and collated their clinical features. "
                        "Thirty-three patients were classified as progressive encephalomyelitis with rigidity and myoclonus, "
                        "and two as stiff person syndrome; five had a limbic encephalitis or epileptic encephalopathy, "
                        "two had brainstem features mainly, two had demyelinating optic neuropathies and one had an unclear diagnosis."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "724.json",
        source_row={
            "source_category": "observational_group_study",
            "source_subtype": "retrospective_or_cohort_group_study",
        },
    )


def make_92_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "92",
            "Title": "Antiamphiphysin antibodies with small-cell lung carcinoma and paraneoplastic encephalomyelitis.",
            "Authors": "Dropcho, E J",
            "Abstract": (
                "Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients. "
                "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, "
                "though only 1 patient had clinical rigidity."
            ),
        },
        text_record={"paper_id": "92", "_path": "data/extraction_json/text/92.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, "
                        "though only 1 patient had clinical rigidity."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "92.json",
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_556_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "556",
            "Title": "GAD antibody-associated neurological illness and its relationship to gluten sensitivity",
            "Authors": "Hadjivassiliou, M",
            "Abstract": (
                "Results - Six of seven (86%) patients with SPS were positive for anti-GAD. "
                "Table 2 summarised evidence of gluten sensitivity in seven patients with stiff-person syndrome."
            ),
        },
        text_record={"paper_id": "556", "_path": "data/extraction_json/text/556.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Group 1 consisted of seven patients with clinical features and neurophysiological evidence of SPS. "
                        "Table 2 Evidence of gluten sensitivity with or without enteropathy in seven patients with stiff-person syndrome."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "556.json",
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_710_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "710",
            "Title": (
                "Encephalitis with refractory seizures, status epilepticus, and antibodies to the GABAA receptor: "
                "a case series, characterisation of the antigen, and analysis of the effects of antibodies."
            ),
            "Authors": "Petit-Pedrol, Mar",
            "Abstract": (
                "These 12 patients developed a broader spectrum of symptoms probably indicative of coexisting autoimmune disorders: "
                "six had encephalitis with seizures, four had stiff-person syndrome, and two had opsoclonus-myoclonus."
            ),
        },
        text_record={"paper_id": "710", "_path": "data/extraction_json/text/710.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "These 12 control patients with other diseases developed a broader spectrum of symptoms probably indicative "
                        "of coexisting autoimmune disorders: six had encephalitis with seizures, four had stiff-person syndrome, "
                        "and two had opsoclonus-myoclonus."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "710.json",
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_12584_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "12584",
            "Title": "Stiff person syndrome vs functional neurological disorder: two patients with hyperkinetic movement disorder",
            "Authors": "Garcia, J",
            "Abstract": "",
        },
        text_record={"paper_id": "12584", "_path": "data/extraction_json/text/12584.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Methods: We discuss two cases of patients who were admitted at the National Institute of Neurology and Neurosurgery. "
                        "The female patient was diagnosed with a FND based on the variability of her symptoms and the improvement with distraction. "
                        "The male patient was treated for SPS with an intravenous immunoglobulin course of 2 g/kg divided into five days and clonazepam, "
                        "with improvement of the symptoms."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready" / "12584.json",
        source_row={
            "source_category": "conference_abstract",
            "source_subtype": "single_case_conference_abstract",
        },
    )


class TestStage06LlmCounting(unittest.TestCase):
    def test_llm_prompt_includes_generic_evidence_pack(self) -> None:
        package = make_package()
        prompt = format_candidate_package_for_llm(package)
        self.assertIn("## Review evidence pack", prompt)
        self.assertIn("## SPS-spectrum subgroup signals", prompt)
        self.assertIn("## SPS-status uncertainty signals", prompt)
        self.assertIn("Metadata abstract:", prompt)
        self.assertTrue(
            "Preferred text count-salient snippets:" in prompt or "Preferred text excerpt:" in prompt
        )

    def test_validator_rejects_count_above_explicit_sps_subgroup(self) -> None:
        package = make_724_package()
        decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=52,
            count_confidence="medium",
            count_manual_review_required=False,
            count_reasoning_summary="The broader cohort size looks like the count.",
            evidence=[
                CountEvidenceItem(
                    quote="We identified prospectively 52 antibody-positive patients.",
                    page=1,
                    section="abstract",
                    supports="broader cohort size",
                )
            ],
        )
        flags, worst = run_validators(package, decision)
        self.assertIn("COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP", flags)
        self.assertEqual(worst, Severity.REJECT)

    def test_validator_rejects_confident_resolution_when_sps_status_is_uncertain(self) -> None:
        package = make_92_package()
        decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=3,
            count_confidence="medium",
            count_manual_review_required=False,
            count_reasoning_summary="The case series describes 3 original patients.",
            evidence=[
                CountEvidenceItem(
                    quote="Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients.",
                    page=1,
                    section="abstract",
                    supports="whole case-series size",
                )
            ],
        )
        flags, worst = run_validators(package, decision)
        self.assertIn("COUNT_SPS_STATUS_UNCERTAIN", flags)
        self.assertEqual(worst, Severity.REJECT)

    def test_validator_rejects_reasoning_selected_candidate_mismatch(self) -> None:
        package = make_12584_package()
        selected_candidate_id = next(
            candidate.candidate_id for candidate in package.candidates if candidate.proposed_count == 2
        )
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=selected_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary=(
                "The extractable SPS-spectrum count is 1, matching candidate cand02 rather than the title-based count of 2."
            ),
            evidence=[
                CountEvidenceItem(
                    quote="The male patient was treated for SPS.",
                    page=1,
                    section="results",
                    supports="only one patient is explicitly SPS",
                )
            ],
        )
        flags, worst = run_validators(package, decision)
        self.assertIn("COUNT_REASONING_SELECTED_CANDIDATE_MISMATCH", flags)
        self.assertEqual(worst, Severity.REJECT)

    def test_validator_rejects_candidate_exact_when_reasoning_requests_bounded_alternative(self) -> None:
        package = make_556_package()
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=package.preferred_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary=(
                "The stronger extractable SPS-spectrum cohort count is therefore 7, but cand01 (7) is not exact. "
                "Since no listed candidate exactly matches the explicit count, a bounded alternative is warranted."
            ),
            evidence=[
                CountEvidenceItem(
                    quote="Group 1 consisted of seven patients with clinical features and neurophysiological evidence of SPS.",
                    page=2,
                    section="methods",
                    supports="Explicit SPS cohort size is 7.",
                )
            ],
        )
        flags, worst = run_validators(package, decision)
        self.assertIn("COUNT_REASONING_DECISION_TYPE_CONTRADICTION", flags)
        self.assertEqual(worst, Severity.REJECT)

    def test_validator_rejects_confident_control_group_subgroup_without_review(self) -> None:
        package = make_710_package()
        decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=4,
            count_confidence="medium",
            count_manual_review_required=False,
            count_reasoning_summary="The abstract identifies four stiff-person syndrome patients in the mixed cohort.",
            evidence=[
                CountEvidenceItem(
                    quote=(
                        "These 12 control patients with other diseases developed a broader spectrum of symptoms "
                        "probably indicative of coexisting autoimmune disorders: six had encephalitis with seizures, "
                        "four had stiff-person syndrome, and two had opsoclonus-myoclonus."
                    ),
                    page=1,
                    section="abstract",
                    supports="Mixed cohort includes four SPS patients, but they come from a control subgroup.",
                )
            ],
        )
        flags, worst = run_validators(package, decision)
        self.assertIn("COUNT_SPS_STATUS_UNCERTAIN", flags)
        self.assertEqual(worst, Severity.REJECT)

    def test_adjudicated_count_row_uses_selected_candidate(self) -> None:
        package = make_package()
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=package.preferred_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The abstract explicitly reports two SPS patients.",
            evidence=[
                CountEvidenceItem(
                    quote="We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
                    page=1,
                    section="abstract",
                    supports="explicit patient count",
                ),
                CountEvidenceItem(
                    quote="Case 1 ... Case 2 ...",
                    page=1,
                    section="body",
                    supports="two individually linkable patients",
                ),
            ],
        )
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            return_value=(decision, "gpt-5.4-test"),
        ):
            row = adjudicated_count_row(package, candidate_json_path="results/stage06_count_runs/test/candidate_packages/214.json")
        self.assertEqual(row["likely_sps_case_count"], "2")
        self.assertEqual(row["count_verification_status"], "llm_candidate_exact")
        self.assertEqual(row["llm_selected_candidate_id"], package.preferred_candidate_id)
        self.assertEqual(row["heuristic_fallback_used"], "false")
        self.assertEqual(row["count_manual_review_required"], "false")

    def test_adjudicated_count_row_falls_back_when_candidate_is_invalid(self) -> None:
        package = make_package()
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id="missing_candidate",
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="An invalid candidate was chosen.",
            evidence=[
                CountEvidenceItem(
                    quote="We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
                    page=1,
                    section="abstract",
                    supports="explicit patient count",
                )
            ],
        )
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            return_value=(decision, "gpt-5.4-test"),
        ):
            row = adjudicated_count_row(package)
        self.assertEqual(row["likely_sps_case_count"], "2")
        self.assertEqual(row["count_verification_status"], "llm_invalid_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "true")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("manual_review_gate=true", row["count_reason"])

    def test_adjudicated_count_row_marks_contradictory_decision_reasoning_for_manual_review(self) -> None:
        package = make_package()
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=package.preferred_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The only listed candidate is not exact and this requires a bounded alternative.",
            evidence=[
                CountEvidenceItem(
                    quote="We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
                    page=1,
                    section="abstract",
                    supports="explicit patient count",
                )
            ],
        )
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            return_value=(decision, "gpt-5.4-test"),
        ):
            row = adjudicated_count_row(package)
        self.assertEqual(row["likely_sps_case_count"], "2")
        self.assertEqual(row["count_verification_status"], "llm_semantic_conflict_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "false")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("COUNT_REASONING_DECISION_TYPE_CONTRADICTION", row["count_validator_flags"])

    def test_adjudicated_count_row_marks_request_failures_as_manual_review_required(self) -> None:
        package = make_package()
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            side_effect=RuntimeError("transient api error"),
        ):
            row = adjudicated_count_row(package)
        self.assertEqual(row["count_verification_status"], "llm_request_failed_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "true")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("manual_review_gate=true", row["count_reason"])

    def test_adjudicated_count_row_uses_single_sps_case_fallback_when_reasoning_candidate_mismatch_is_rejected(self) -> None:
        package = make_12584_package()
        selected_candidate_id = next(
            candidate.candidate_id for candidate in package.candidates if candidate.proposed_count == 2
        )
        decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=selected_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary=(
                "The extractable SPS-spectrum count is 1, matching candidate cand02 rather than the title-based count of 2."
            ),
            evidence=[
                CountEvidenceItem(
                    quote="The male patient was treated for SPS.",
                    page=1,
                    section="results",
                    supports="only one patient is explicitly SPS",
                ),
                CountEvidenceItem(
                    quote="The female patient was diagnosed with a FND.",
                    page=1,
                    section="results",
                    supports="the other patient is not SPS",
                ),
            ],
        )
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            return_value=(decision, "gpt-5.4-test"),
        ):
            row = adjudicated_count_row(package)
        self.assertEqual(row["likely_sps_case_count"], "2")
        self.assertEqual(row["count_verification_status"], "llm_semantic_conflict_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "false")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("COUNT_REASONING_SELECTED_CANDIDATE_MISMATCH", row["count_validator_flags"])

    def test_adjudicated_count_row_preserves_llm_count_for_subgroup_conflicts(self) -> None:
        package = make_724_package()
        decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=52,
            count_confidence="medium",
            count_manual_review_required=False,
            count_reasoning_summary="The larger antibody-positive cohort seems to be the right count.",
            evidence=[
                CountEvidenceItem(
                    quote="We identified prospectively 52 antibody-positive patients.",
                    page=1,
                    section="abstract",
                    supports="whole cohort size",
                )
            ],
        )
        with mock.patch(
            "src.pipelines.stage06_counting.controller.adjudicate_count_package",
            return_value=(decision, "gpt-5.4-test"),
        ):
            row = adjudicated_count_row(package)
        self.assertEqual(row["likely_sps_case_count"], "52")
        self.assertEqual(row["llm_likely_sps_case_count"], "52")
        self.assertEqual(row["count_verification_status"], "llm_semantic_conflict_manual_review_required")
        self.assertEqual(row["heuristic_fallback_used"], "false")
        self.assertEqual(row["count_manual_review_required"], "true")
        self.assertIn("COUNT_EXCEEDS_EXPLICIT_SPS_SUBGROUP", row["count_validator_flags"])


if __name__ == "__main__":
    unittest.main()
