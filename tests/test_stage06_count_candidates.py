from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage06CountCandidates(unittest.TestCase):
    def test_candidate_package_preserves_proceedings_ready_metadata(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "1394",
                "Title": "Inpatient physiotherapy management for stiff person syndrome",
                "Authors": "Kahraman T.; Balci B.; Sengun I.S.",
                "Abstract": "The abstract describes a single 65-year-old female patient with SPS.",
            },
            text_record={"paper_id": "1394", "_path": "data/extraction_json/text/1394.json"},
            preferred_record={
                "pages": [{"text": "Case Presentation: The patient was a 65-year-old female with SPS."}],
                "proceedings_ready_source_kind": "published_ready_text",
                "proceedings_ready_text_mode": "trimmed_abstract",
                "proceedings_ready_reason": "Published active manually checked proceedings text.",
                "source_text_json_path": "data/extraction_json/text/1394.json",
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready" / "1394.json",
            source_row={
                "source_category": "conference_abstract",
                "source_subtype": "single_case_conference_abstract",
            },
            ready_rows={"1394": {"paper_id": "1394", "ready_text_mode": "trimmed_abstract"}},
        )
        self.assertEqual(package.preferred_text_source, "proceedings_ready")
        self.assertEqual(package.preferred_text_metadata["proceedings_ready_text_mode"], "trimmed_abstract")
        self.assertEqual(package.preferred_text_json_path, "data\\extraction_json\\text_proceedings_ready\\1394.json")

    def test_candidate_package_keeps_competing_single_case_and_body_label_counts(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "6073",
                "Title": "Detection of gephyrin antibody in stiff-person syndrome",
                "Authors": "Example, B",
                "Abstract": "",
            },
            text_record={"paper_id": "6073", "_path": "data/extraction_json/text/6073.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Poster session. Patient 1 had unrelated symptoms. Patient 2 had unrelated symptoms. "
                            "Patient 3 had unrelated symptoms."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "6073.json",
            source_row={
                "source_category": "conference_abstract",
                "source_subtype": "single_case_conference_abstract",
            },
        )
        proposed_counts = {candidate.proposed_count for candidate in package.candidates}
        self.assertIn(1, proposed_counts)
        self.assertIn(3, proposed_counts)
        self.assertTrue(package.llm_routing_recommended)
        self.assertEqual(package.preferred_candidate().proposed_count, 1)

    def test_unclear_manual_review_is_treated_as_uncertain_and_llm_routed(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "525",
                "Title": (
                    "Monozygotic twins with stiff person syndrome and autoimmune thyroiditis: "
                    "rituximab inefficacy in a double-blind, randomised, placebo controlled crossover study."
                ),
                "Authors": "Venhoff, N; Rizzi, M",
                "Abstract": "",
            },
            text_record={"paper_id": "525", "_path": "data/extraction_json/text/525.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "We report two identical twins with the rare combination of autoimmune thyroiditis "
                            "with stiff person syndrome. Twin A presented first. Twin B had less severe disease."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "525.json",
            source_row={
                "source_category": "unclear_manual_review",
                "source_subtype": "unclear",
            },
        )
        self.assertTrue(package.count_eligible)
        self.assertTrue(package.llm_routing_recommended)
        self.assertIn("count_eligibility_status=uncertain", package.candidate_generation_notes)
        self.assertNotIn("not_count_eligible", {candidate.count_basis for candidate in package.candidates})
        self.assertNotIn("twin_count_signal", {candidate.count_basis for candidate in package.candidates})
        self.assertIn(2, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn("two identical twins", package.llm_evidence_text.lower())
        self.assertIn("twin a presented first", package.llm_evidence_text.lower())

    def test_candidate_package_adds_explicit_sps_subgroup_candidate_for_mixed_perm_cohort(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "724",
                "Title": "Glycine receptor antibodies in PERM and related syndromes: characteristics, clinical features and outcomes.",
                "Authors": "Carvajal-Gonzalez, Alexander",
                "Abstract": (
                    "We identified prospectively 52 antibody-positive patients and collated their clinical features. "
                    "Thirty-three patients were classified as progressive encephalomyelitis with rigidity and myoclonus, "
                    "and two as stiff person syndrome; five had a limbic encephalitis or epileptic encephalopathy, "
                    "two had brainstem features mainly, two had demyelinating optic neuropathies and one had an unclear diagnosis. "
                    "Ten glycine receptor antibody positive samples were also identified in a retrospective cohort of 56 patients "
                    "with stiff person syndrome and related syndromes."
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
                            "two had brainstem features mainly, two had demyelinating optic neuropathies and one had an unclear diagnosis. "
                            "Ten glycine receptor antibody positive samples were also identified in a retrospective cohort of 56 patients "
                            "with stiff person syndrome and related syndromes."
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
        self.assertEqual(package.explicit_sps_subgroup_count, 35)
        self.assertEqual(package.fallback_candidate().proposed_count, 35)
        self.assertIn(35, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn(
            "diagnosis_specific_group_breakdown_count",
            {candidate.count_basis for candidate in package.candidates},
        )
        self.assertIn("explicit_sps_subgroup_count=35", package.candidate_generation_notes)

    def test_candidate_package_marks_subset_rigidity_series_as_uncertain(self) -> None:
        package = build_case_count_candidate_package(
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
        self.assertTrue(package.sps_status_uncertainty_signals)
        self.assertIn("only 1 patient had clinical rigidity", package.sps_status_uncertainty_signals[0].lower())
        self.assertTrue(
            any(note.startswith("sps_status_uncertainty_signals=") for note in package.candidate_generation_notes)
        )

    def test_candidate_package_marks_ocr_split_single_rigidity_patient_as_uncertain(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "92",
                "Title": "Antiamphiphysin antibodies with small-cell lung carcinoma and paraneoplastic encephalomyelitis.",
                "Authors": "Dropcho, E J",
                "Abstract": "",
            },
            text_record={"paper_id": "92", "_path": "data/extraction_json/text/92.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, "
                            "though only I pa- \ntient had clinical rigidity. Patient Histories Patient 1 ..."
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
        self.assertTrue(package.sps_status_uncertainty_signals)
        self.assertIn("only i patient had clinical rigidity", package.sps_status_uncertainty_signals[0].lower())

    def test_candidate_package_extracts_explicit_patient_label_subgroup_from_mixed_gad_series(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "967",
                "Title": "Clinical Heterogeneity in Patients with Glutamate Decarboxylase Antibody.",
                "Authors": "Huang, Jiehong",
                "Abstract": (
                    "Clinical data of a series of 5 patients positive for anti-GAD antibodies were retrospectively analyzed. "
                    "Their neurological symptoms included stiff-person syndrome (SPS), encephalitis, myelitis, cramp, visual loss, and paresthesia."
                ),
            },
            text_record={"paper_id": "967", "_path": "data/extraction_json/text/967.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Table 1. Data of 5 patients positive for GAD65 antibody. "
                            "Patient 1 encephalitis. Patient 2 SPS. Patient 3 loss of vision, facial sensory abnormalities. "
                            "Patient 4 painful spasm of the right lower extremity. Patient 5 myelitis. "
                            "Interestingly, in Patient 2, who had SPS with breast cancer and GAD antibodies, the tumor cells did not express GAD antibodies."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "967.json",
            source_row={
                "source_category": "case_series_or_multi_case",
                "source_subtype": "case_series",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 1)
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertTrue(package.sps_status_uncertainty_signals)
        self.assertIn(1, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn("potential sps-status uncertainty signals", package.llm_evidence_text.lower())

    def test_candidate_package_extracts_named_sps_cohort_from_group_definition(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "556",
                "Title": "GAD antibody-associated neurological illness and its relationship to gluten sensitivity",
                "Authors": "Hadjivassiliou, M",
                "Abstract": (
                    "Results - Six of seven (86%) patients with SPS were positive for anti-GAD, mean titre 109 U/ml. "
                    "This compared with 9/90 patients with idiopathic sporadic ataxia, 16/40 patients with gluten ataxia, "
                    "and 6/10 patients with type 1 diabetes only."
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
        self.assertEqual(package.explicit_sps_subgroup_count, 7)
        self.assertEqual(package.fallback_candidate().proposed_count, 7)
        self.assertIn(7, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn(
            "diagnosis_specific_named_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_marks_control_group_subgroup_counts_as_uncertain(self) -> None:
        package = build_case_count_candidate_package(
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
        self.assertEqual(package.explicit_sps_subgroup_count, 4)
        self.assertEqual(package.fallback_candidate().proposed_count, 4)
        self.assertTrue(package.sps_status_uncertainty_signals)
        self.assertIn(
            "diagnosis_specific_mixed_diagnosis_subgroup_count",
            {candidate.count_basis for candidate in package.candidates},
        )
        self.assertTrue(any("control" in signal.lower() for signal in package.sps_status_uncertainty_signals))

    def test_candidate_package_extracts_single_sps_case_from_mixed_two_patient_abstract(self) -> None:
        package = build_case_count_candidate_package(
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
        self.assertEqual(package.explicit_sps_subgroup_count, 1)
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertIn(
            "diagnosis_specific_patient_case_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_prefers_explicit_homogeneous_sps_cohort_over_single_patient_response_snippet(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "13064",
                "Title": "Efgartigimod beyond myasthenia gravis: the role of FcRn-targeting therapies in stiff-person syndrome",
                "Authors": "Di Stefano, V",
                "Abstract": (
                    "In this study, we report and describe the first data on treatment with efgartigimod in three patients "
                    "affected by both AChR-seropositive generalized MG and anti-GAD-seropositive SPS. "
                    "All patients showed an improvement in symptoms of both SPS and MG after 2 cycles of treatment."
                ),
            },
            text_record={"paper_id": "13064", "_path": "data/extraction_json/text/13064.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "In this study, we report and describe the first data on treatment with efgartigimod in three patients "
                            "affected by both AChR-seropositive generalized MG and anti-GAD-seropositive SPS. "
                            "Patient 3 showed a very good response on both MG and SPS scales."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "13064.json",
            source_row={
                "source_category": "case_series_or_multi_case",
                "source_subtype": "case_series",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 3)
        self.assertEqual(package.fallback_candidate().proposed_count, 3)
        self.assertIn(
            "diagnosis_specific_direct_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_non_extractable_review_article_suppresses_spurious_nonzero_alternatives(self) -> None:
        package = build_case_count_candidate_package(
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
                            "A survey of the medical literature in 1967 identified 44 cases. "
                            "Since then, more than 70 additional cases have been reported. "
                            "Steroid-responsive and dependent stiff-man syndrome: a clinical study of two cases."
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
        self.assertFalse(package.count_eligible)
        self.assertEqual(package.preferred_candidate().proposed_count, 0)
        self.assertEqual({candidate.proposed_count for candidate in package.candidates}, {0})
        self.assertEqual({candidate.count_basis for candidate in package.candidates}, {"not_count_eligible"})

    def test_stage06_defaults_to_llm_for_all_rows(self) -> None:
        count_mod = _load_module("case_count_module_stage06_defaults", CASE_COUNT_SCRIPT)
        original_argv = sys.argv
        try:
            sys.argv = ["06_extract_sps_case_counts.py"]
            args = count_mod.parse_args()
        finally:
            sys.argv = original_argv
        self.assertEqual(args.verification_mode, "always")
        self.assertTrue(
            count_mod._verification_needed(
                verification_mode="always",
                count_eligible=False,
                llm_routing_recommended=False,
            )
        )

    def test_stage06_detects_unresolved_manual_review_rows(self) -> None:
        count_mod = _load_module("case_count_module_stage06_unresolved", CASE_COUNT_SCRIPT)
        unresolved_ids = count_mod._unresolved_paper_ids(
            [
                {
                    "paper_id": "214",
                    "count_manual_review_required": "false",
                    "count_verification_status": "llm_candidate_exact",
                },
                {
                    "paper_id": "525",
                    "count_manual_review_required": "true",
                    "count_verification_status": "llm_semantic_conflict_manual_review_required",
                },
            ]
        )
        self.assertEqual(unresolved_ids, ["525"])


if __name__ == "__main__":
    unittest.main()
