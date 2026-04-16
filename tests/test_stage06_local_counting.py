from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.local_ollama import (
    SYSTEM_PROMPT,
    ensure_ollama_model_available,
    parse_local_count_output,
    run_local_count_package,
)
from src.pipelines.stage06_counting.local_prepare import format_candidate_package_for_local_llm
from src.pipelines.stage06_counting.local_validate import validate_local_count_decision


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
        preferred_path=Path("data/extraction_json/text/214.json"),
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_review_package():
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
        preferred_path=Path("data/extraction_json/text/12720.json"),
        source_row={
            "source_category": "review_article",
            "source_subtype": "review",
        },
    )


def make_uncertain_package():
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
        preferred_path=Path("data/extraction_json/text/92.json"),
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_enumerated_subgroup_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "1937",
            "Title": "Prevalence of neurological anti-gad autoimmunity in martinique",
            "Authors": "Duclos S.; Cabre P.; Deligny C.; Signate A.",
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
        preferred_path=Path("data/extraction_json/text_proceedings_ready/1937.json"),
        source_row={
            "source_category": "conference_abstract",
            "source_subtype": "group_conference_abstract",
        },
    )


def make_single_case_suffix_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "427",
            "Title": "Stiff person syndrome and motor mononeuropathy with conduction block: a singular association.",
            "Authors": "La Spada, S; Negro, C; Nozzoli, C; De Marco, V; Passarella, B",
            "Abstract": (
                'The "Stiff person syndrome"(SPS) is a rare dysimmune chronic neurological disorder. '
                "We describe a singular association in one patient as affected with SPS (3)."
            ),
        },
        text_record={"paper_id": "427", "_path": "data/extraction_json/text/427.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        'The "Stiff person syndrome"(SPS) is a rare dysimmune chronic neurological disorder. '
                        "We describe a singular association in one patient as affected with SPS (3)."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text/427.json"),
        source_row={
            "source_category": "single_case_report",
            "source_subtype": "case_report",
        },
    )


def make_non_candidate_direct_sps_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "1805",
            "Title": "Possible link of genetic variants to autoimmunity in GAD-antibody-associated neurological disorders",
            "Authors": "Thaler F.S.; Bangol B.; Biljecki M.; Havla J.; Schumacher A.-M.; Kumpfel T.",
            "Abstract": (
                "RESULT(S): 19 patients with positive GAD-ab and the following neurological phenotypes were included: "
                "n = 8 cerebellar ataxia, n = 6 limbic encephalitis, n = 4 stiff person syndrome, "
                "n = 1 demyelinating CNS disease with recurrent optic neuritis."
            ),
        },
        text_record={"paper_id": "1805", "_path": "data/extraction_json/text/1805.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "RESULT(S): 19 patients with positive GAD-ab and the following neurological phenotypes were included: "
                        "n = 8 cerebellar ataxia, n = 6 limbic encephalitis, n = 4 stiff person syndrome, "
                        "n = 1 demyelinating CNS disease with recurrent optic neuritis."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text_trimmed/1805.json"),
        source_row={
            "source_category": "lab_heavy_clinical_or_translational",
            "source_subtype": "group_or_frequency_focused_lab_clinical_study",
        },
    )


def make_treatment_subset_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "12760",
            "Title": "Therapeutic Plasma Exchange in the Management of Stiff Person Syndrome Spectrum Disorders",
            "Authors": "Roy, S",
            "Abstract": (
                "Thirty-nine SPSD patients were treated with TPE. "
                "Twenty-four patients had classic SPS, 10 had SPS-plus, 2 had PERM, and 3 had CA. "
                "Before starting TPE, 30 patients had symptomatic treatment exposure."
            ),
        },
        text_record={"paper_id": "12760", "_path": "data/extraction_json/text/12760.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Thirty-nine SPSD patients were treated with TPE. "
                        "Twenty-four patients had classic SPS, 10 had SPS-plus, 2 had PERM, and 3 had CA. "
                        "Before starting TPE, 30 patients had symptomatic treatment exposure."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text/12760.json"),
        source_row={
            "source_category": "observational_group_study",
            "source_subtype": "retrospective_or_cohort_group_study",
        },
    )


def make_late_count_package():
    long_lead = " ".join(["background"] * 120)
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "1153",
            "Title": "A new clinical tool to monitor IVIg efficacy in patients with stiff person syndrome",
            "Authors": "Weerasinghe S.; Sadalage G.; Jacob S.",
            "Abstract": (
                f"{long_lead} We monitored 12 patients with stiff person syndrome receiving IVIg and recorded outcome scores."
            ),
        },
        text_record={"paper_id": "1153", "_path": "data/extraction_json/text/1153.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        f"{long_lead} We monitored 12 patients with stiff person syndrome receiving IVIg and recorded outcome scores."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text_proceedings_ready/1153.json"),
        source_row={
            "source_category": "conference_abstract",
            "source_subtype": "group_conference_abstract",
        },
    )


class TestStage06LocalCounting(unittest.TestCase):
    def test_local_system_prompt_defines_spsd_scope(self) -> None:
        self.assertIn("classic stiff person syndrome (SPS)", SYSTEM_PROMPT)
        self.assertIn("partial or focal SPS, including stiff limb syndrome", SYSTEM_PROMPT)
        self.assertIn("SPS-plus", SYSTEM_PROMPT)
        self.assertIn("jerking SPS", SYSTEM_PROMPT)
        self.assertIn("progressive encephalomyelitis with rigidity and myoclonus (PERM)", SYSTEM_PROMPT)
        self.assertIn("Stiff man syndrome (SMS)", SYSTEM_PROMPT)

    def test_local_prompt_includes_evidence_and_candidates(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_package())
        self.assertIn("## Deterministic anchors", prompt)
        self.assertIn("## Evidence pack", prompt)
        self.assertIn("## Explicit subgroup signals", prompt)
        self.assertIn("## Direct named SPS-spectrum subgroup cues", prompt)
        self.assertIn("## Treatment-state subset cues", prompt)
        self.assertIn("## Deterministic candidate hints", prompt)
        self.assertIn("## Required JSON output", prompt)
        self.assertIn('"n_spsd_patients"', prompt)
        self.assertIn("preferred_candidate_id", prompt)
        self.assertIn("preferred_deterministic_count", prompt)
        self.assertIn("deterministic_candidate_counts", prompt)

    def test_local_prompt_highlights_explicit_subgroup_total(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_enumerated_subgroup_package())
        self.assertIn("explicit_sps_subgroup_count: 14", prompt)
        self.assertIn(
            "explicit_sps_subgroup_interpretation: This is the deterministic SPS-spectrum subtotal from a diagnosis breakdown",
            prompt,
        )
        self.assertIn("explicit_subgroup_candidate_count: 14", prompt)
        self.assertIn("preferred_vs_explicit_subgroup_status: disagreement", prompt)
        self.assertIn("An explicit deterministic SPS-spectrum subtotal is provided below.", prompt)
        self.assertIn(
            "The preferred broad-count candidate disagrees with the explicit SPS-spectrum subtotal",
            prompt,
        )

    def test_local_prompt_highlights_single_case_suffix_conflict(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_single_case_suffix_package())
        self.assertIn("single_case_expected_count: 1", prompt)
        self.assertIn("preferred_vs_explicit_subgroup_status: disagreement", prompt)
        self.assertIn(
            "suffix_count_conflict_status: suspicious_suffix_count_requires_stronger_support",
            prompt,
        )
        self.assertIn(
            "A bare suffix count like SPS (3) is not enough to override single-case routing on its own.",
            prompt,
        )

    def test_local_prompt_highlights_direct_named_subgroup_exception(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_non_candidate_direct_sps_package())
        self.assertIn("n = 4 stiff person syndrome", prompt)
        self.assertIn(
            "You may choose a different top-level count only when the evidence pack contains a direct SPS-spectrum subgroup quote",
            prompt,
        )

    def test_local_prompt_highlights_treatment_state_subset_warning(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_treatment_subset_package())
        self.assertIn("Before starting TPE", prompt)
        self.assertIn(
            "Do not use pre-treatment, post-treatment, response, or medication-usage subsets as the cohort size",
            prompt,
        )

    def test_local_prompt_keeps_late_count_visible_in_evidence_snippet(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_late_count_package())
        self.assertIn("12 patients with stiff person syndrome", prompt)

    def test_parse_local_output_handles_fenced_json(self) -> None:
        parsed = parse_local_count_output(
            """```json
            {
              "n_spsd_patients": 2,
              "evidence_span": "We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
              "data_granularity": "individual-level",
              "confidence": "high",
              "needs_review": false,
              "reasoning_short": "The abstract explicitly reports two original SPS patients.",
              "possibilities": []
            }
            ```"""
        )
        self.assertEqual(parsed.n_spsd_patients, 2)
        self.assertEqual(parsed.data_granularity, "individual-level")
        self.assertFalse(parsed.needs_review)

    def test_parse_local_output_handles_compact_gemma_json(self) -> None:
        parsed = parse_local_count_output(
            """{
              "count": 13,
              "needs_review": false,
              "possibilities": ["14"]
            }"""
        )
        self.assertEqual(parsed.n_spsd_patients, 13)
        self.assertEqual(parsed.data_granularity, "unclear")
        self.assertEqual(parsed.confidence, "low")
        self.assertTrue(parsed.needs_review)
        self.assertEqual(len(parsed.possibilities), 1)
        self.assertEqual(parsed.possibilities[0].n_spsd_patients, 14)

    def test_parse_local_output_handles_compact_possibility_dicts(self) -> None:
        parsed = parse_local_count_output(
            """{
              "count": 1,
              "possibilities": [
                {"count": 3, "reason": "suffix count might be relevant"}
              ]
            }"""
        )
        self.assertEqual(parsed.n_spsd_patients, 1)
        self.assertEqual(parsed.possibilities[0].n_spsd_patients, 3)
        self.assertTrue(parsed.needs_review)

    def test_parse_local_output_handles_answer_alias_and_numeric_confidence(self) -> None:
        parsed = parse_local_count_output(
            """{
              "answer": "35",
              "reasoning": "This is the best available cohort-size estimate.",
              "confidence": 0.9
            }"""
        )
        self.assertEqual(parsed.n_spsd_patients, 35)
        self.assertEqual(parsed.confidence, "high")
        self.assertEqual(parsed.data_granularity, "unclear")
        self.assertTrue(parsed.needs_review)

    def test_validate_local_decision_flags_review_article_nonzero(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 44,
              "evidence_span": "A survey of the medical literature in 1967 identified 44 cases.",
              "data_granularity": "group-level",
              "confidence": "medium",
              "needs_review": true,
              "reasoning_short": "The paper discusses 44 cases.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_review_package(), parsed)
        self.assertIn("LOCAL_SKIP_CATEGORY_NONZERO", flags)

    def test_validate_local_decision_flags_uncertain_positive_without_review(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 3,
              "evidence_span": "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin.",
              "data_granularity": "group-level",
              "confidence": "high",
              "needs_review": false,
              "reasoning_short": "The series contains three original patients.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_uncertain_package(), parsed)
        self.assertIn("LOCAL_SPS_STATUS_UNCERTAIN_NO_REVIEW", flags)

    def test_validate_local_decision_flags_enumerated_subgroup_mismatch(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 13,
              "evidence_span": "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
              "data_granularity": "group-level",
              "confidence": "high",
              "needs_review": true,
              "reasoning_short": "The clearest SPS count is 13.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_enumerated_subgroup_package(), parsed)
        self.assertIn("LOCAL_ENUMERATED_SPS_SUBGROUP_MISMATCH", flags)

    def test_validate_local_decision_flags_non_candidate_without_direct_support(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 16,
              "evidence_span": "In this study, we examined the reactivity of anti-GAD-containing sera from 7 patients with IDDM, 4 patients with SMS, and 5 patients with APS I.",
              "data_granularity": "group-level",
              "confidence": "high",
              "needs_review": true,
              "reasoning_short": "The explicit evidence lists three groups.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_treatment_subset_package(), parsed)
        self.assertIn("LOCAL_COUNT_NOT_IN_CANDIDATES", flags)

    def test_validate_local_decision_allows_direct_named_subgroup_non_candidate(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 4,
              "evidence_span": "n = 4 stiff person syndrome",
              "data_granularity": "group-level",
              "confidence": "medium",
              "needs_review": true,
              "reasoning_short": "This is the direct SPS subgroup.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_non_candidate_direct_sps_package(), parsed)
        self.assertNotIn("LOCAL_COUNT_NOT_IN_CANDIDATES", flags)

    def test_validate_local_decision_flags_treatment_subset_drift(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 30,
              "evidence_span": "Before starting TPE, 30 patients had symptomatic treatment exposure.",
              "data_granularity": "group-level",
              "confidence": "high",
              "needs_review": true,
              "reasoning_short": "This seems like the cohort size.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_treatment_subset_package(), parsed)
        self.assertIn("LOCAL_TREATMENT_STATE_SUBSET_COUNT", flags)

    def test_ensure_ollama_model_available_checks_model_list(self) -> None:
        with mock.patch("src.pipelines.stage06_counting.local_ollama.requests.get") as get_mock:
            get_mock.return_value.json.return_value = {"data": [{"id": "gemma4:e4b"}]}
            get_mock.return_value.raise_for_status.return_value = None
            ensure_ollama_model_available(model="gemma4:e4b", base_url="http://localhost:11434")

    def test_run_local_count_package_records_parse_failure(self) -> None:
        package = make_package()
        with mock.patch("src.pipelines.stage06_counting.local_ollama.requests.post") as post_mock:
            post_mock.return_value.json.return_value = {
                "model": "gemma4:e4b",
                "message": {"content": "not json"},
            }
            post_mock.return_value.raise_for_status.return_value = None
            result = run_local_count_package(package, base_url="http://localhost:11434", timeout_seconds=1)
        self.assertEqual(result.status, "parse_failed")
        self.assertIsNone(result.parsed)
        self.assertIn("Unable to parse", result.error)


if __name__ == "__main__":
    unittest.main()
