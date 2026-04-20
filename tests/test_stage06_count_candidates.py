from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from src.pipelines._sps_case_counting import estimate_sps_case_count
from src.pipelines._sps_case_count_registry import build_case_count_candidate_package, count_row_from_resolution


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_COUNT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_text_record(path: Path) -> dict[str, object]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


class TestStage06CountCandidates(unittest.TestCase):
    def test_estimate_sps_case_count_does_not_treat_percentages_as_counts(self) -> None:
        estimate = estimate_sps_case_count(
            title="Brain and Muscle Metabolic Changes by FDG-PET in Stiff Person Syndrome Spectrum Disorders.",
            abstract=(
                "Results: Of the patients, 82% had SPS (majority being classic phenotype), and 18% had CA."
            ),
            early_body_text="",
        )
        self.assertNotEqual(estimate.likely_case_count, 82)

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

    def test_candidate_package_promotes_explicit_group_conference_cohort_over_single_case_default(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "12554",
                "Title": "Clinical profile of seropositive stiff person syndrome",
                "Authors": "Example, A",
                "Abstract": "",
            },
            text_record={"paper_id": "12554", "_path": "data/extraction_json/text/12554.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Retrospective analysis of seropositive SPS patients. "
                            "Twenty SPS patients were included."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "12554.json",
            source_row={
                "source_category": "conference_abstract",
                "source_subtype": "group_conference_abstract",
            },
        )
        self.assertEqual(package.preferred_candidate().proposed_count, 20)
        self.assertEqual(package.preferred_candidate().count_basis, "diagnosis_specific_direct_cohort_count")
        self.assertIn("explicit_sps_subgroup_promoted_over_ambiguous_primary", package.candidate_generation_notes)

    def test_candidate_package_promotes_explicit_lab_cohort_over_zero_fallback(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "12613",
                "Title": "Metabolic imaging in stiff-person spectrum disorder",
                "Authors": "Example, B",
                "Abstract": "",
            },
            text_record={"paper_id": "12613", "_path": "data/extraction_json/text/12613.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "For serum analysis, twelve SPS patients were included and compared with controls."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "12613.json",
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.preferred_candidate().proposed_count, 12)
        self.assertEqual(package.preferred_candidate().count_basis, "diagnosis_specific_direct_cohort_count")
        self.assertNotEqual(package.preferred_candidate().count_basis, "lab_context_no_extractable_count")

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

    def test_candidate_package_prefers_identified_sms_methods_cohort_over_hla_subgroup(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "43",
                "Title": (
                    "Higher autoantibody levels and recognition of a linear NH2-terminal epitope in the "
                    "autoantigen GAD65, distinguish stiff-man syndrome from insulin-dependent diabetes mellitus."
                ),
                "Authors": "Kim, J",
                "Abstract": (
                    "Here we report the characterization of humoral autoimmune responses to GAD65 in 35 SMS patients, "
                    "of whom 13 also had IDDM. Nine of nine individuals who were HLA-haplotyped in this group carried "
                    "an IDDM susceptibility haplotype."
                ),
            },
            text_record={"paper_id": "43", "_path": "data/extraction_json/text/43.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Materials and Methods. Antisera. Sera were obtained with informed consent from 33 SMS "
                            "patients identified at the Mayo Clinic during the period of 1989-1992, and from two "
                            "patients who attended the UCSF Neurology Clinic during the period of 1991-1993. "
                            "The patients were diagnosed using uniform standardized criteria."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "43.json",
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 33)
        self.assertEqual(package.fallback_candidate().proposed_count, 33)
        self.assertIn(
            "diagnosis_specific_direct_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_uses_fuzzy_title_anchor_for_stitched_issue_case_report(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "180.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "180",
                "Title": "Paraneoplastic stiff limb syndrome.",
                "Authors": "Silverman, I E",
                "Abstract": "",
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "unclear_manual_review",
                "source_subtype": "unclear",
            },
        )
        self.assertIn("we present a patient clinically consistent", package.early_body_text)
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertIn(1, {candidate.proposed_count for candidate in package.candidates})

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

    def test_candidate_package_extracts_fraction_style_sps_subgroup_count(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "11893",
                "Title": "Brain and Muscle Metabolic Changes by FDG-PET in Stiff Person Syndrome Spectrum Disorders.",
                "Authors": "Wang Y",
                "Abstract": (
                    "Retrospective cohort study identified 170 individuals with SPS or cerebellar ataxia. "
                    "Fifty-one underwent FDG-PET, with 50 involving the body. "
                    "Of the patients, 82% had SPS and 18% had CA."
                ),
            },
            text_record={"paper_id": "11893", "_path": "data/extraction_json/text/11893.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Clinical phenotype within the cohort was SPS (41/50, 82%), "
                            "remaining participants had pure CA (9/50, 18%)."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "11893.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        proposed_counts = {candidate.proposed_count for candidate in package.candidates}
        self.assertEqual(package.explicit_sps_subgroup_count, 41)
        self.assertIn(41, proposed_counts)
        self.assertNotIn(82, proposed_counts)

    def test_candidate_package_extracts_parenthetical_n_equals_sps_subgroup(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "11923",
                "Title": (
                    "Seizure semiology and predictors of outcomes in Chinese patients with "
                    "glutamic acid decarboxylase antibody-associated neurological syndrome."
                ),
                "Authors": "Lin N",
                "Abstract": (
                    "Concomitant neurological syndromes were observed in 22 patients, including "
                    "limbic encephalitis (n = 20), stiff-person syndrome (SPS, n = 1), "
                    "and cerebellar ataxia (n = 1)."
                ),
            },
            text_record={"paper_id": "11923", "_path": "data/extraction_json/text/11923.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Concomitant neurological syndromes were observed in 22 patients, including "
                            "limbic encephalitis (n = 20), stiff-person syndrome (SPS, n = 1), "
                            "and cerebellar ataxia (n = 1)."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "11923.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 1)
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertIn(1, {candidate.proposed_count for candidate in package.candidates})

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
                    "six had encephalitis with seizures (one with status epilepticus needing pharmacologically induced coma; "
                    "one with epilepsia partialis continua), four had stiff-person syndrome (one with seizures and limbic involvement), "
                    "and two had opsoclonus-myoclonus."
                ),
            },
            text_record={"paper_id": "710", "_path": "data/extraction_json/text/710.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "These 12 control patients with other diseases developed a broader spectrum of symptoms probably indicative "
                            "of coexisting autoimmune disorders: six had encephalitis with seizures (one with status epilepticus "
                            "needing pharmacologically induced coma; one with epilepsia partialis continua), four had stiff-person syndrome "
                            "(one with seizures and limbic involvement), and two had opsoclonus-myoclonus."
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
        self.assertFalse(package.sps_status_uncertainty_signals)
        self.assertIn(
            "diagnosis_specific_mixed_diagnosis_subgroup_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_extracts_singleton_suffix_subgroup_from_mixed_pns_cohort(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "227",
                "Title": "Spectrum of paraneoplastic neurologic disorders in women with breast and gynecologic cancer.",
                "Authors": "Rojas-Marcos, Inigo",
                "Abstract": (
                    "We retrospectively reviewed 92 patients whose serum was sent to our laboratories. "
                    "Other PNSs were opsoclonus-myoclonus syndrome (4 cases), sensorimotor neuropathy (4 cases), "
                    "paraneoplastic encephalomyelitis (4 cases), stiff-person syndrome (1 with amphiphysin-ab), "
                    "and limbic encephalitis (1 case)."
                ),
            },
            text_record={"paper_id": "227", "_path": "data/extraction_json/text/227.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Table 1. Clinical and immunologic characteristics of 92 patients. "
                            "Stiff-person syndrome 1 Amphiphysin (1)."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "227.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertEqual(package.explicit_sps_subgroup_count, 1)
        self.assertIn(1, {candidate.proposed_count for candidate in package.candidates})
        self.assertTrue(
            {
                "diagnosis_specific_suffix_count",
                "diagnosis_specific_table_row_count",
            }
            & {candidate.count_basis for candidate in package.candidates}
        )
        self.assertFalse(package.sps_status_uncertainty_signals)

    def test_candidate_package_skips_previously_described_sps_subgroup_counts(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "62",
                "Title": (
                    "Autoimmunity in stiff-Man syndrome with breast cancer is targeted to the C-terminal "
                    "region of human amphiphysin, a protein similar to the yeast proteins, Rvs167 and Rvs161."
                ),
                "Authors": "David, C; Solimena, M; De Camilli, P",
                "Abstract": (
                    "Amphiphysin, a neuronal protein first identified in chicken synaptic membranes, is the "
                    "autoantigen of Stiff-Man Syndrome (SMS) associated with breast cancer."
                ),
            },
            text_record={"paper_id": "62", "_path": "data/extraction_json/text/62.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Sera from four patients with SMS and breast cancer were previously described "
                            "(patients 2-5) [8, 9]. In two of these patients, an infiltrating ductal "
                            "adenocarcinoma was searched for, and found, only after the identification of the "
                            "anti-amphiphysin antibodies ([8] and our most recent case (patient 1 of this study))."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "62.json",
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertIsNone(package.explicit_sps_subgroup_count)
        self.assertNotIn(4, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn("potential non-original or reused-cohort signals", package.llm_evidence_text.lower())

    def test_candidate_package_extracts_table_row_subgroup_from_mixed_neurology_cohort(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "990",
                "Title": "Therapeutic plasma exchange in treatment of neuroimmunologic disorders: Review of 92 cases",
                "Authors": "Sorgun M.H.; Erdogan S.; Bay M.; Ayyildiz E.; Yucemen N.; IIhan O.; Yucesan C.",
                "Abstract": (
                    "Therapeutic plasma exchange (TPE) is a procedure that reduces amount of circulating antibodies "
                    "in patients through filtration for the treatment of neurologic diseases in which autoimmunity "
                    "plays a major role. We reviewed the medical records of 92 neurologic patients who had been "
                    "consecutively treated by TPE. Neurological indications included myastehia gravis (MG, 16 "
                    "patients), Guillain-Barre syndrome (GBS, 37 patients) and miscellaneous diseases (39 patients)."
                ),
            },
            text_record={"paper_id": "990", "_path": "data/extraction_json/text/990.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "The results of the treatment are summarized in Table 2. Table 1 Indications of "
                            "plasmapheresis and demographic details of the patients. Diagnosis No. of the patients "
                            "Mean age (Range) Sex (F/M) Total number of TPE procedures Mean number of TPE (Range) "
                            "MG 16 41(19-73) 11/5 16 5(3-8) GBS 37 50(16-77) 21/16 37 4(1-6) Stiff person syndrome "
                            "1 59(59) 1/0 1 5"
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "990.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 1)
        self.assertEqual(package.fallback_candidate().proposed_count, 1)
        self.assertIn(1, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn(
            "diagnosis_specific_table_row_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_extracts_no_of_cases_table_row_subgroup(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "252",
                "Title": "The spectrum of antineuronal autoantibodies in a series of neurological patients.",
                "Authors": "Vianello, M",
                "Abstract": (
                    "The records of 882 patients were reviewed and their sera and cerebrospinal fluids tested for "
                    "antineuronal antibodies."
                ),
            },
            text_record={"paper_id": "252", "_path": "data/extraction_json/text/252.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Table 1 Groups of patients No. of cases "
                            "Patients with neurological disorder and systemic autoimmune disease "
                            "Stiff-Person syndrome 18 Connective tissue diseases 38"
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "252.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 18)
        self.assertEqual(package.fallback_candidate().proposed_count, 18)
        self.assertIn(18, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn(
            "diagnosis_specific_table_row_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_prefers_stiff_man_phenomena_table_row_count(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "432",
                "Title": "Glutamic acid decarboxylase autoimmunity with brainstem, extrapyramidal, and spinal cord dysfunction.",
                "Authors": "Pittock, S J",
                "Abstract": "This retrospective study describes 62 patients incidentally found to have GAD65 autoimmunity.",
            },
            text_record={"paper_id": "432", "_path": "data/extraction_json/text/432.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "TABLE 1. Neurological Manifestations in 62 Patients Seropositive for GAD65 Antibody "
                            "No. (%) Level involved of patients Signs and symptoms Miscellaneous "
                            "Extrapyramidal 10 (16) Axial or neck rigidity (8); parkinsonism (4) "
                            "Stiff-man phenomena 16 (26) Leg or arm spasms (14); stiff-man syndrome (2)"
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "432.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 16)
        self.assertEqual(package.fallback_candidate().proposed_count, 16)
        self.assertIn(16, {candidate.proposed_count for candidate in package.candidates})

    def test_candidate_package_ignores_citation_like_suffix_count(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "404",
                "Title": (
                    "Intravenous immunoglobulin in patients with anti-GAD antibody-associated neurological diseases "
                    "and patients with inflammatory myopathies: effects on clinicopathological features and "
                    "immunoregulatory genes."
                ),
                "Authors": "Dalakas, Marinos C",
                "Abstract": (
                    "The following patients were randomised in three separate trials: "
                    "(a) 16 patients with anti-GAD antibody-positive SPS; "
                    "(b) 15 patients with dermatomyositis; and (c) 19 patients with IBM."
                ),
            },
            text_record={"paper_id": "404", "_path": "data/extraction_json/text/404.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "In this article, the efficacy of IVIg on two groups of autoimmune neurological disorders, "
                            "anti-glutamic acid decarboxylase-positive SPS and inflammatory myopathies, is summarised. "
                            "SPS (19,20), we performed a randomised trial. "
                            "The following patients were randomised in three separate trials: "
                            "(a) 16 patients with anti-GAD antibody-positive SPS; "
                            "(b) 15 patients with dermatomyositis; and (c) 19 patients with IBM."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "404.json",
            source_row={
                "source_category": "interventional_study",
                "source_subtype": "controlled_or_therapeutic_group_study",
            },
        )
        self.assertEqual(package.preferred_candidate().proposed_count, 16)
        self.assertEqual(package.fallback_candidate().proposed_count, 16)
        self.assertNotIn(19, {candidate.proposed_count for candidate in package.candidates})
        self.assertNotEqual(package.explicit_sps_subgroup_count, 19)

    def test_candidate_package_extracts_sms_subgroup_with_control_subjects(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "264",
                "Title": "Hyperekplexia and stiff-man syndrome: abnormal brainstem reflexes suggest a physiological relationship.",
                "Authors": "Khasani, S",
                "Abstract": (
                    "Using four-channel EMG, we examined four trigeminal brainstem reflexes in five patients with "
                    "familial hyperekplexia, two with acquired hyperekplexia, 10 with SMS, and 15 healthy control subjects."
                ),
            },
            text_record={"paper_id": "264", "_path": "data/extraction_json/text/264.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Patients and controls: we investigated five patients with FH, two patients with AH, "
                            "10 patients with SMS, and 15 healthy control subjects."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "264.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 10)
        self.assertEqual(package.explicit_sps_subgroup_basis, "diagnosis_specific_mixed_diagnosis_subgroup_count")
        self.assertEqual(package.sps_status_uncertainty_signals, [])

    def test_candidate_package_ignores_control_comparison_when_explicit_sps_cohort_exists(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "288",
                "Title": "Brain gamma-aminobutyric acid changes in stiff-person syndrome.",
                "Authors": "Levy, Lucien M",
                "Abstract": (
                    "Patients: Eight patients with SPS with high titers of circulating anti-glutamic acid decarboxylase "
                    "antibodies and 16 control subjects. Results: GABA levels were reduced in patients with SPS relative "
                    "to controls."
                ),
            },
            text_record={"paper_id": "288", "_path": "data/extraction_json/text/288.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "Methods: We studied 8 patients with SPS and 16 age-matched healthy volunteers as control "
                            "subjects. Results: GABA levels were reduced in patients with SPS relative to controls."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "288.json",
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 8)
        self.assertEqual(package.sps_status_uncertainty_signals, [])

    def test_candidate_package_does_not_treat_suspected_exacerbation_as_suspected_cohort(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "411",
                "Title": "Prevention of an acute severe exacerbation of Stiff-person syndrome during surgery.",
                "Authors": "Gros, Albert J Jr",
                "Abstract": "",
            },
            text_record={"paper_id": "411", "_path": "data/extraction_json/text/411.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "We present a case of a woman with SPS who had an acute exacerbation during surgery. "
                            "There was a high suspicion that the seizure-like activity reported by the patient was an "
                            "acute exacerbation of SPS."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "411.json",
            source_row={
                "source_category": "single_case_report",
                "source_subtype": "case_report",
            },
        )
        self.assertEqual(package.confirmed_only_guardrail_signals, [])

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
        self.assertTrue(
            {
                "diagnosis_specific_patient_case_count",
                "diagnosis_specific_patient_label_count",
            }
            & {candidate.count_basis for candidate in package.candidates}
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

    def test_candidate_package_sums_enumerated_sps_spectrum_subgroups(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "1937",
                "Title": "Prevalence of neurological anti-GAD autoimmunity in Martinique",
                "Authors": "Duclos, S",
                "Abstract": (
                    "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM."
                ),
            },
            text_record={"paper_id": "1937", "_path": "data/extraction_json/text/1937.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
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
        self.assertEqual(package.explicit_sps_subgroup_count, 14)
        self.assertEqual(package.fallback_candidate().proposed_count, 14)
        self.assertTrue(
            {
                "diagnosis_specific_enumerated_subgroup_count",
                "diagnosis_specific_group_breakdown_count",
            }
            & {candidate.count_basis for candidate in package.candidates}
        )

    def test_candidate_package_counts_extended_sps_spectrum_breakdown_aliases(self) -> None:
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "1528",
                "Title": "Expanded SPS-spectrum phenotypes in glycine receptor autoimmunity",
                "Authors": "Example, C",
                "Abstract": (
                    "SPS spectrum phenotypes included progressive encephalomyelitis with rigidity and myoclonus (8), "
                    "classic SPS (5), stiff limb (5), stiff trunk (1), and isolated exaggerated startle (1)."
                ),
            },
            text_record={"paper_id": "1528", "_path": "data/extraction_json/text/1528.json"},
            preferred_record={
                "pages": [
                    {
                        "text": (
                            "SPS spectrum phenotypes included progressive encephalomyelitis with rigidity and "
                            "myoclonus (8), classic SPS (5), stiff limb (5), stiff trunk (1), and isolated "
                            "exaggerated startle (1)."
                        )
                    }
                ]
            },
            preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "1528.json",
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 20)
        self.assertIn(20, {candidate.proposed_count for candidate in package.candidates})
        self.assertTrue(
            {
                "diagnosis_specific_group_breakdown_count",
                "diagnosis_specific_enumerated_subgroup_count",
            }
            & {candidate.count_basis for candidate in package.candidates}
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

    def test_candidate_package_excludes_reused_case_label_leak_from_mixed_trial(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "12137.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "12137",
                "Title": "Therapeutic Trial of Milacemide in Patients With Myoclonus and Other Intractable Movement Disorders",
                "Authors": "Gordon, M F; Diaz-Olivo, R; Hunt, A L; Fahn, S",
                "Abstract": (
                    "We performed a therapeutic trial with milacemide on 10 patients with intractable movement disorders. "
                    "Six had myoclonus of various etiologies and one each had progressive supranuclear palsy, Filipino "
                    "X-linked dystonia with parkinsonism, painful legs and moving toes, and stiff-person syndrome."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "interventional_study",
                "source_subtype": "controlled_or_therapeutic_group_study",
            },
        )
        self.assertEqual(package.preferred_candidate().proposed_count, 1)
        self.assertEqual(package.preferred_candidate().count_basis, "diagnosis_specific_list_count")
        self.assertNotIn(2, {candidate.proposed_count for candidate in package.candidates})
        self.assertIn(
            "diagnosis_specific_list_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_keeps_lab_heavy_donor_material_paper_at_zero(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "560.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "560",
                "Title": "Respective implications of glutamate decarboxylase antibodies in stiff person syndrome and cerebellar ataxia",
                "Authors": "Manto, M U; Hampe, C S; Rogemond, V; Honnorat, J",
                "Abstract": (
                    "To investigate whether stiff-person syndrome and cerebellar ataxia are associated with distinct "
                    "GAD65-Ab epitope specificities and neuronal effects."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.preferred_candidate().proposed_count, 0)
        self.assertEqual(package.preferred_candidate().count_basis, "lab_context_no_extractable_count")
        self.assertTrue(package.confirmed_only_guardrail_signals)

    def test_candidate_package_prefers_confirmed_subset_in_suspected_sms_cohort(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "270.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "270",
                "Title": "Markedly elevated GAD antibodies in SPS",
                "Authors": "Murinson, B B; Butler, M; Marfurt, K; Gleason, S; De Camilli, P; Solimena, M",
                "Abstract": (
                    "Five hundred seventy-six patients with suspected stiff-person syndrome underwent immunocytochemistry. "
                    "Of these, 286 underwent radioimmunoassay for glutamic acid decarboxylase antibodies; 116 were GAD "
                    "antibody positive by one or both tests. Marked elevations were characteristic of ICC-confirmed SPS."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 107)
        self.assertEqual(package.fallback_candidate().proposed_count, 107)
        self.assertIn(
            "diagnosis_specific_confirmed_subset_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_prefers_total_then_sps_subgroup_in_mixed_gad_cohort(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "491.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "491",
                "Title": (
                    "Spectrum of neurological syndromes associated with glutamic acid decarboxylase "
                    "antibodies: diagnostic clues for this association."
                ),
                "Authors": (
                    "Saiz, Albert; Blanco, Yolanda; Sabater, Lidia; Gonzalez, Felix; Bataller, Luis; "
                    "Casamitjana, Roser; Ramio-Torrenta, Lluis; Graus, Francesc"
                ),
                "Abstract": (
                    "High GAD-ab levels were identified in 61 patients, 22 (36%) had SPS, 17 (28%) "
                    "cerebellar ataxia, 11 (18%) other neurological disorders, and 11 (18%) isolated DM1."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 22)
        self.assertEqual(package.preferred_candidate().proposed_count, 22)
        self.assertEqual(
            package.preferred_candidate().count_basis,
            "diagnosis_specific_total_then_sps_subgroup_count",
        )
        self.assertEqual({candidate.proposed_count for candidate in package.candidates}, {22, 61})

    def test_candidate_package_sums_distinct_antibody_defined_sps_groups(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "499.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "499",
                "Title": "Stiff-person syndrome with amphiphysin antibodies: distinctive features of a rare disease.",
                "Authors": "Murinson, Beth B; Guarnaccia, Joseph B",
                "Abstract": (
                    "Records associated with 845 sera tested in the Yale SPS project were examined, and 621 patients "
                    "with clinically suspected SPS were included in the study. Results: In all, 116 patients had GAD "
                    "antibodies and 11 patients had amphiphysin Ab; some clinical information was available for 112 "
                    "and 11 of these patients, respectively."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 127)
        self.assertEqual(package.preferred_candidate().proposed_count, 127)
        self.assertIn(
            "diagnosis_specific_antibody_group_total",
            {candidate.count_basis for candidate in package.candidates},
        )
        self.assertIn(116, {candidate.proposed_count for candidate in package.candidates})

    def test_candidate_package_extracts_sms_phenotype_cohort_total(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "659.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "659",
                "Title": "Glycine receptor autoimmune spectrum with stiff-man syndrome phenotype.",
                "Authors": (
                    "McKeon, Andrew; Martinez-Hernandez, Eugenia; Lancaster, Eric; Matsumoto, Joseph Y; "
                    "Harvey, Robert J; McEvoy, Kathleen M; Pittock, Sean J; Lennon, Vanda A; Dalmau, Josep"
                ),
                "Abstract": (
                    "OBJECTIVES: To determine whether glycine receptor alpha1 subunit-specific autoantibodies "
                    "(GlyRalpha1-IgG) occur in a broader spectrum of brainstem and spinal hyperexcitability "
                    "disorders than the progressive encephalomyelitis with rigidity and myoclonus phenotype "
                    "recognized to date, and to ascertain disease specificity. PATIENTS: Eighty-one patients "
                    "with stiff-man syndrome phenotype, 80 neurologic control subjects, and 20 healthy control "
                    "subjects. RESULTS: Seropositive cases (12% of cases) included 9 with stiff-man syndrome "
                    "(4 classic; 5 variant; 66% were glutamic acid decarboxylase 65-IgG positive) and 1 with "
                    "progressive encephalomyelitis with rigidity and myoclonus."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 81)
        self.assertEqual(package.fallback_candidate().proposed_count, 81)
        self.assertIn(
            "diagnosis_specific_phenotype_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_extracts_parenthetical_sps_cohort_total(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "667.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "667",
                "Title": "Characteristics of in-vitro phenotypes of glutamic acid decarboxylase 65 autoantibodies in high-titre individuals.",
                "Authors": "Cheramy, M; Hampe, C S; Ludvigsson, J; Casas, R",
                "Abstract": (
                    "This study aimed to analyse GADA levels in four cohorts with very high GADA titres: "
                    "T1D patients (n = 7), GAD-alum-treated T1D patients (n = 9), T1D high-risk individuals "
                    "(n = 6) and SPS patients (n = 12)."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "lab_heavy_clinical_or_translational",
                "source_subtype": "group_or_frequency_focused_lab_clinical_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 12)
        self.assertEqual(package.fallback_candidate().proposed_count, 12)
        self.assertIn(
            "diagnosis_specific_parenthetical_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_extracts_sps_count_from_table_title(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "723.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "723",
                "Title": "Cerebellar ataxia and glutamic acid decarboxylase antibodies: immunologic profile and long-term effect of immunotherapy.",
                "Authors": (
                    "Arino, Helena; Gresa-Arribas, Nuria; Blanco, Yolanda; Martinez-Hernandez, Eugenia; "
                    "Sabater, Lidia; Petit-Pedrol, Mar; Rouco, Idoia; Bataller, Luis; Dalmau, Josep O; "
                    "Saiz, Albert; Graus, Francesc"
                ),
                "Abstract": (
                    "IMPORTANCE: Current clinical and immunologic knowledge on cerebellar ataxia (CA) with "
                    "glutamic acid decarboxylase 65 antibodies (GAD65-Abs) is based on case reports and small "
                    "series with short-term follow-up data. DESIGN, SETTING, AND PARTICIPANTS: Retrospective "
                    "cohort study and laboratory investigations among 34 patients with CA and GAD65-Abs. "
                    "Twenty-eight patients with stiff person syndrome and GAD65-Abs served as controls. "
                    "Nine patients had coexisting stiff person syndrome symptoms."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 9)
        self.assertEqual(package.fallback_candidate().proposed_count, 9)
        self.assertIn(
            "diagnosis_specific_table_title_cohort_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_candidate_package_counts_sps_rows_in_final_diagnosis_table(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "800.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "800",
                "Title": "Neuronal autoantibodies: differentiating clinically relevant and clinically irrelevant results.",
                "Authors": (
                    "Abboud, Hesham; Rossman, Ian; Mealy, Maureen A; Hill, Eddie; Thompson, Nicolas; "
                    "Banerjee, Aditya; Probasco, John; Levy, Michael"
                ),
                "Abstract": (
                    "We reviewed 401 neurological patients who were tested for the Mayo-Clinic paraneoplastic "
                    "panel. Fifty-three patients tested positive for one or more neuronal autoantibodies. "
                    "There were 17 clinically relevant, 33 clinically irrelevant, and 3 indeterminate patients."
                ),
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "observational_group_study",
                "source_subtype": "retrospective_or_cohort_group_study",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 5)
        self.assertEqual(package.fallback_candidate().proposed_count, 5)
        self.assertIn(
            "diagnosis_specific_case_table_diagnosis_count",
            {candidate.count_basis for candidate in package.candidates},
        )

    def test_count_row_marks_embedded_review_provenance_as_manual_review(self) -> None:
        path = REPO_ROOT / "data" / "extraction_json" / "text" / "184.json"
        package = build_case_count_candidate_package(
            reference_row={
                "Covidence": "184",
                "Title": "The Stiff-Person Syndrome: An Autoimmune Disorder Affecting Neurotransmission of Gamma-Aminobutyric Acid",
                "Authors": "Levy, L M; Dalakas, M C; Floeter, M K",
                "Abstract": "",
            },
            text_record=_load_text_record(path),
            preferred_record=_load_text_record(path),
            preferred_path=path,
            source_row={
                "source_category": "review_format_with_embedded_original_cohort",
                "source_subtype": "embedded_original_cohort",
            },
        )
        self.assertEqual(package.explicit_sps_subgroup_count, 20)
        self.assertTrue(package.original_cohort_provenance_uncertain)

        row = count_row_from_resolution(
            package=package,
            final_count=20,
            final_confidence="high",
            final_basis="diagnosis_specific_series_cohort_count",
            final_manual_review_required=False,
            final_reason="count_basis=diagnosis_specific_series_cohort_count",
            count_version="test_v1",
            count_verification_status="heuristic_only",
        )
        self.assertEqual(row["likely_sps_case_count"], "20")
        self.assertEqual(row["count_original_cohort_provenance_uncertain"], "true")
        self.assertEqual(row["count_manual_review_required"], "true")

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
